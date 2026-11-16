"""Pruebas unitarias del módulo Plug & Play de ECG (sin hardware y sin hilos de adquisición)."""

import sys
import threading
import time
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hardware.ecg_plugplay import (FLAG_INTERPOLATED, FLAG_LEADOFF, FLAG_MISSING, FLAG_SATURATED, FLAG_SETTLING,
                                   AcquisitionConfig, CompositeAnalyzer, ECGWindow, InferenceBridge,
                                   ModelAnalyzer, QualityHeuristics, WindowQuality)
from hardware.ecg_plugplay.ports import PortInfo, candidate_ports, explain_serial_error
from hardware.ecg_plugplay.preprocessing import (AdcParams, SamplePipeline, StreamingFilter, assess_window,
                                                 normalize_for_model)
from hardware.ecg_plugplay.protocol import DataBlock, DeviceMessage, Hello, LegacySample, LineReader, parse_line
from hardware.ecg_plugplay.ring_buffer import SlidingWindowBuffer
from hardware.ecg_plugplay.simulator import beats_to_mv, mv_to_counts

FS = 250.0


# ----------------------------------------------------------------------------- protocolo
def test_handshake_y_bloques():
    h = parse_line('ECG:HELLO,fw=1.0,fs=250,bits=12,vref=3.3,gain=1100,blk=10,raro=x')
    assert isinstance(h, Hello) and h.fs == 250 and h.bits == 12 and h.firmware == '1.0' and h.gain == 1100
    assert not h.prefiltered and parse_line('ECG:HELLO,filt=1').prefiltered
    d = parse_line('ECG:D,120,2,2048,2050,2047\r')
    assert d == DataBlock(120, 2, (2048.0, 2050.0, 2047.0))
    assert parse_line('ECG:2048') == DataBlock(None, 0, (2048.0,))
    assert parse_line('ECG:2048,1') == DataBlock(None, 1, (2048.0,))
    assert parse_line('ECG:E,adc lento') == DeviceMessage('adc lento')


def test_lineas_que_no_son_ecg():
    assert parse_line('ECG:D,1,0,') .kind == 'corrupta'
    assert parse_line('ECG:D,x,0,10').kind == 'corrupta'
    assert parse_line('>>> ').kind == 'repl'
    assert parse_line('Traceback (most recent call last):').kind == 'traceback'
    assert parse_line('rst:0x1 (POWERON_RESET),boot:0x13').kind == 'arranque'
    assert parse_line('MicroPython v1.23.0 on 2024-06-02').kind == 'banner'
    assert parse_line('').kind == 'vacia'
    # El formato viejo de BIOCORE solo se acepta si se pide.
    assert parse_line('1234.5,512').kind == 'numerica'
    assert parse_line('1234.5,512', accept_legacy=True) == LegacySample(1234.5, 512.0)
    assert parse_line('{"ack": 3, "t_ms": 10}').kind == 'desconocida'   # las líneas JSON de otra placa no se confunden con ECG


def test_lector_de_lineas_arma_trozos_y_descarta_basura():
    r = LineReader(max_line=50)
    assert r.feed(b'ECG:D,0,0,1') == []
    assert r.feed(b',2\r\nECG:HE') == ['ECG:D,0,0,1,2']
    assert r.feed(b'LLO\n') == ['ECG:HELLO']
    assert r.feed(bytes(range(200, 256)) * 2) == [] and r.overflows == 1   # basura sin fin de línea


# ----------------------------------------------------------------------------- buffer circular
def test_ventanas_con_solape_del_50_por_ciento():
    buf = SlidingWindowBuffer(1000, 500, {'x': np.int64})
    salidas = []
    for inicio in range(0, 3000, 7):                     # trozos de 7: cruzan los límites a destiempo
        trozo = np.arange(inicio, min(inicio + 7, 3000))
        salidas += buf.extend(x=trozo)
    assert [int(w['start']) for w in salidas] == [0, 500, 1000, 1500, 2000]
    for w in salidas:
        assert np.array_equal(w['x'], np.arange(w['start'], w['start'] + 1000))
    buf.clear()
    assert buf.filled == 0 and buf.extend(x=np.arange(999)) == []


def test_un_trozo_grande_entrega_varias_ventanas():
    buf = SlidingWindowBuffer(1000, 250, {'x': np.int64})
    ventanas = buf.extend(x=np.arange(2000))
    assert [int(w['start']) for w in ventanas] == [0, 250, 500, 750, 1000]


# ----------------------------------------------------------------------------- filtro y limpieza
def _seno(f, n, amp=1.0):
    return amp * np.sin(2 * np.pi * f * np.arange(n) / FS)


def _ganancia(filt, f):
    y = filt.process(_seno(f, 5000))
    return np.std(y[2500:]) / np.std(_seno(f, 5000)[2500:])


def test_filtro_quita_60hz_y_deriva_y_deja_el_qrs():
    assert _ganancia(StreamingFilter(FS, (0.5, 40), 2, 60.0), 60.0) < 0.05
    assert _ganancia(StreamingFilter(FS, (0.5, 40), 2, 60.0), 0.1) < 0.1
    assert 0.9 < _ganancia(StreamingFilter(FS, (0.5, 40), 2, 60.0), 10.0) < 1.1


def test_filtrar_por_trozos_es_igual_que_de_un_golpe():
    x = _seno(10, 2000) + _seno(60, 2000, 0.3) + 0.5
    a = StreamingFilter(FS, (0.5, 40), 2, 60.0).process(x)
    f = StreamingFilter(FS, (0.5, 40), 2, 60.0)
    b = np.concatenate([f.process(x[i:i + 10]) for i in range(0, 2000, 10)])
    assert np.allclose(a, b)


def _pipeline():
    cfg = AcquisitionConfig()
    filt = StreamingFilter(cfg.fs, cfg.bandpass_hz, cfg.bandpass_order, cfg.notch_hz, cfg.notch_q)
    return SamplePipeline(cfg.fs, AdcParams(), cfg.heuristics, filt, max_fill=cfg.window_size)


def test_huecos_cortos_se_interpolan_y_los_largos_se_marcan():
    p = _pipeline()
    p.push([2048] * 10, seq=0)
    corto = p.push([2050] * 10, seq=12)                 # faltaron 2 muestras
    assert corto['flags'][:2].tolist() == [FLAG_INTERPOLATED] * 2 and corto['seq'][0] == 10
    largo = p.push([2050] * 10, seq=100)                # se esperaba la 22: faltaron 78
    assert np.count_nonzero(largo['flags'] & FLAG_MISSING) == 78 and np.isnan(largo['mv'][:78]).all()
    assert (largo['flags'][78:] & FLAG_SETTLING).all()  # tras el hueco, el filtro se reinicia y se estabiliza
    assert p.stats == {'recibidas': 30, 'perdidas': 78, 'interpoladas': 2, 'reinicios_placa': 0}


def test_electrodo_suelto_y_saturacion_se_marcan():
    p = _pipeline()
    p.push([2048] * 10, seq=0)
    lo = p.push([4095] * 10, seq=10, leadoff=1)
    assert (lo['flags'] & FLAG_LEADOFF).all() and np.isnan(lo['mv']).all()
    sat = p.push([2048, 0, 4095, 2048, 2048, 2048, 2048, 2048, 2048, 2048], seq=20)
    assert (sat['flags'][1:3] & FLAG_SATURATED).all() and not (sat['flags'][3:] & FLAG_SATURATED).any()


def test_placa_reiniciada_no_inventa_muestras():
    p = _pipeline()
    p.push([2048] * 10, seq=500)
    out = p.push([2048] * 10, seq=0)
    assert out['seq'][0] == 0 and len(out['mv']) == 10 and p.stats['reinicios_placa'] == 1


def test_revision_de_ventana_explica_cada_motivo():
    h = QualityHeuristics()
    bien = np.sin(np.linspace(0, 20, 1000))
    assert assess_window(bien, np.zeros(1000, np.uint8), h).ok
    flags = np.zeros(1000, np.uint8)
    flags[:50] = FLAG_LEADOFF
    q = assess_window(bien, flags, h)
    assert not q.ok and 'electrodo suelto' in q.reasons[0]
    flags = np.zeros(1000, np.uint8)
    flags[:20] = FLAG_SATURATED
    assert 'saturó' in assess_window(bien, flags, h).reasons[0]
    flags = np.zeros(1000, np.uint8)
    flags[5] = FLAG_MISSING
    assert 'faltan 1 muestras' in assess_window(bien, flags, h).reasons[0]
    assert 'plana' in assess_window(bien * 0.001, np.zeros(1000, np.uint8), h).reasons[0]


def test_normalizacion_para_el_modelo():
    cfg = AcquisitionConfig()
    x = normalize_for_model(np.sin(np.linspace(0, 30, 1000)) * 2 + 5, cfg)
    assert x.shape == (1, 1000) and x.dtype == np.float32 and x.min() == 0.0 and x.max() == 1.0
    cfg.normalization = 'robust'
    senal = np.sin(np.linspace(0, 30, 1000))
    senal[500] = 100.0                                              # un artefacto aislado
    y = normalize_for_model(senal, cfg)
    assert y.shape == (1, 1000) and y.min() == 0.0 and y.max() == 1.0
    assert np.ptp(y[0, :400]) > 0.9                                 # no aplasta el resto de la ventana
    with pytest.raises(ValueError):
        normalize_for_model(np.ones(1000), AcquisitionConfig())


def test_configuracion_invalida_se_explica():
    with pytest.raises(ValueError, match='model_input_shape'):
        AcquisitionConfig(model_input_shape=(1, 500)).check()
    with pytest.raises(ValueError, match='pasa-banda'):
        AcquisitionConfig(bandpass_hz=(0.5, 200)).check()
    assert AcquisitionConfig(overlap=0.75).hop == 250


# ----------------------------------------------------------------------------- puertos
def test_nunca_se_sondean_puertos_bluetooth_ni_sin_usb():
    puertos = [
        PortInfo('COM4', 'Standard Serial over Bluetooth link (COM4)', hwid='BTHENUM\\{00001101}'),
        PortInfo('COM1', 'Communications Port (COM1)'),
        PortInfo('COM7', 'USB Serial Device', vid=0x2E8A, pid=0x0005),
        PortInfo('COM3', 'Silicon Labs CP210x USB to UART Bridge', vid=0x10C4, pid=0xEA60),
    ]
    elegidos = candidate_ports(puertos, AcquisitionConfig())
    assert [p.device for p in elegidos] == ['COM3', 'COM7']          # el chip conocido primero
    assert elegidos[0].label == 'Silicon Labs CP210x'
    assert [p.device for p in candidate_ports(puertos, AcquisitionConfig(port='COM9'))] == ['COM9']


def test_errores_de_windows_y_linux_se_traducen():
    assert explain_serial_error(Exception("could not open port 'COM3': PermissionError(13, 'Access is denied.', None, 5)"), 'COM3').kind == 'ocupado'
    assert explain_serial_error(Exception("OSError(22, 'The semaphore timeout period has expired.', None, 121)"), 'COM4').kind == 'no_responde'
    assert explain_serial_error(Exception("FileNotFoundError(2, 'The system cannot find the file specified.')"), 'COM5').kind == 'no_existe'
    assert explain_serial_error(Exception("[Errno 13] Permission denied: '/dev/ttyUSB0'"), '/dev/ttyUSB0').kind == 'permiso'
    assert 'Thonny' in explain_serial_error(Exception('Access is denied'), 'COM3').message


# ----------------------------------------------------------------------------- puente de inferencia
def _ventana(i=0, valida=True):
    mv = beats_to_mv(np.arange(1000) / FS, np.array([0.5, 1.33, 2.16, 2.99, 3.82]))
    q = WindowQuality(samples=1000) if valida else WindowQuality(samples=1000, reasons=['electrodo suelto'])
    entrada = normalize_for_model(mv, AcquisitionConfig()) if valida else None
    return ECGWindow(i, FS, i * 500, mv, mv_to_counts(mv).astype(float), np.zeros(1000, np.uint8), q, entrada,
                     'SIMULACION', 'prueba', time.time())


def test_modelo_con_claves_en_espanol():
    class MiClaseML:
        def procesar_ventana(self, datos_ecg):
            assert datos_ecg.shape == (1, 1000) and datos_ecg.dtype == np.float32
            return {'prediccion': 'ritmo sinusal', 'bpm': 72.0, 'ondas': {'R': [125]}}

    out = ModelAnalyzer(MiClaseML())(_ventana())
    assert out['prediction'] == 'ritmo sinusal' and out['bpm'] == 72.0 and out['waves'] == {'R': [125]}
    assert out['labels']['prediction'] == 'MiClaseML.procesar_ventana'


def test_composicion_de_analizadores():
    a = lambda w: {'bpm': 70.0, 'labels': {'bpm': 'A'}, 'notes': ['nota A']}
    b = lambda w: {'prediction': 'X', 'bpm': None, 'labels': {'prediction': 'B'}}
    out = CompositeAnalyzer([a, b])(_ventana())
    assert out['bpm'] == 70.0 and out['prediction'] == 'X' and out['labels'] == {'bpm': 'A', 'prediction': 'B'}


def test_puente_se_queda_con_la_ventana_mas_nueva_y_sobrevive_errores():
    resultados = []
    listo = threading.Event()

    def lento(w):
        if w.index == 3:
            raise RuntimeError('modelo roto')
        time.sleep(0.3)
        return {'prediccion': f'v{w.index}'}

    def recibir(r):
        resultados.append(r)
        if r.window.index == 9:
            listo.set()

    puente = InferenceBridge(lento, recibir)
    puente.start()
    for i in range(10):
        puente.submit(_ventana(i))
        time.sleep(0.02)
    assert listo.wait(3.0)
    puente.stop()
    indices = [r.window.index for r in resultados]
    assert indices[-1] == 9 and puente.dropped >= 5          # las viejas se descartaron, no se encolaron
    assert resultados[-1].prediction == 'v9'
    errores = puente.analyze(_ventana(3))
    assert errores.error.startswith('El análisis falló: RuntimeError') and errores.prediction is None
    invalida = puente.analyze(_ventana(4, valida=False))
    assert not invalida.valid and invalida.reasons == ['electrodo suelto']
