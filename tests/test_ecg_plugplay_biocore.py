"""El adaptador BiocoreAnalyzer contra el motor real de BIOCORE (clinical/, qrs_delineation, reglas)."""

import sys
import threading
import time
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

import numpy as np  # noqa: E402

from hardware.ecg_plugplay import (AcquisitionConfig, BiocoreAnalyzer, CompositeAnalyzer, ConnectionState,
                                   ECGAcquisitionService, ECGWindow, ModelAnalyzer, SimulatedECGDevice,
                                   WindowQuality)
from hardware.ecg_plugplay.preprocessing import StreamingFilter, normalize_for_model
from hardware.ecg_plugplay.simulator import beats_to_mv


def _primer_resultado_valido(analizador, hr=72.0):
    resultados = []
    listo = threading.Event()

    def recibir(r):
        if r.valid:
            resultados.append(r)
            listo.set()

    svc = ECGAcquisitionService(AcquisitionConfig(), analizador, simulator=SimulatedECGDevice(speed=8.0, hr_bpm=hr),
                                on_result=recibir)
    with svc:
        assert svc.wait_for(ConnectionState.CONNECTED, 5.0)
        assert listo.wait(15.0), 'no llegó ninguna ventana válida'
    return resultados[0]


def _ordenadas(latido):
    return [latido[k]['index'] for k in ('P', 'Q', 'R', 'S', 'T') if k in latido]


@pytest.mark.parametrize('hr', [60.0, 72.0, 110.0])
def test_bpm_y_ondas_en_vivo(hr):
    r = _primer_resultado_valido(BiocoreAnalyzer(fs=250.0), hr)
    assert r.bpm is not None and abs(r.bpm - hr) < 0.06 * hr     # el simulador mete 3 % de variabilidad RR
    assert r.labels['bpm'] == 'Detector TKEO de BIOCORE (ECG Lab)'
    assert r.labels['waves'] == BiocoreAnalyzer.WAVES_LABEL and 'no validada' in r.labels['waves']
    latidos = list(r.waves.values())
    assert len(latidos) >= int(4.0 * hr / 60.0) - 2               # menos los cortados por los bordes
    assert all(_ordenadas(b) == sorted(_ordenadas(b)) and 'QRS' in b for b in latidos)
    assert any({'P', 'R', 'S', 'T'} <= set(b) for b in latidos)
    assert r.prediction is None                                    # sin pattern=True, la predicción es de tu modelo


def _ventana(senal):
    q = WindowQuality(samples=senal.size)
    return ECGWindow(0, 250.0, 0, senal, senal, np.zeros(senal.size, np.uint8), q,
                     normalize_for_model(senal, AcquisitionConfig()), 'SIMULACION', 'prueba', time.time())


def _ecg_72(ruido_uv, semilla=1):
    t = np.arange(1000) / 250.0
    senal = beats_to_mv(t, 0.35 + np.arange(6) * (60 / 72)) + ruido_uv / 1000 * np.random.default_rng(semilla).standard_normal(1000)
    return StreamingFilter(250.0, (0.5, 40), 2, 60.0).process(senal)


def test_ondas_en_su_lugar():
    # 8 s filtrados y se analiza la segunda mitad, como en vivo (filtro ya asentado).
    rr = 60 / 72
    t = np.arange(2000) / 250.0
    picos = 0.35 + np.arange(10) * rr
    x = StreamingFilter(250.0, (0.5, 40), 2, 60.0).process(beats_to_mv(t, picos))[1000:]
    verdaderas = picos[(picos >= 4.0) & (picos < 8.0)] - 4.0
    latidos = list(BiocoreAnalyzer(fs=250.0)(_ventana(x))['waves'].values())
    assert len(latidos) >= 4
    for b in latidos:
        r = b['R']['index'] / 250.0
        r_real = verdaderas[np.argmin(np.abs(verdaderas - r))]
        assert abs(r - r_real) < 0.015                              # el filtro causal retrasa unos ms
        assert abs(b['S']['index'] / 250.0 - r - 0.035) < 0.015     # el simulador pone S a +35 ms
        assert abs(b['P']['index'] / 250.0 - r + 0.200) < 0.030     # P a -200 ms
        assert abs(b['T']['index'] / 250.0 - r - 0.280) < 0.040     # T a +280 ms
        assert 60 <= b['QRS']['duration_ms'] <= 130


def _ventanas_del_generador_de_biocore():
    from scipy.signal import butter, sosfiltfilt

    from src.signals.ecg.dynamic_ecg_generator import DynamicECGGenerator

    ecg = sosfiltfilt(butter(2, [0.5, 40], btype='band', fs=250.0, output='sos'),
                      DynamicECGGenerator(fs=250.0).generate(duration=20, hr=72))
    return [ecg[i:i + 1000] for i in range(0, ecg.size - 1000 + 1, 500)]


def test_nunca_se_cae_con_el_generador_de_biocore():
    # Con estas mismas ventanas, classify_ecg_signal de BIOCORE lanza ValueError en algunas
    # (measure_intervals con la primera R pegada al borde). El adaptador nunca se cae.
    analizador = BiocoreAnalyzer(fs=250.0, pattern=True)
    for w in _ventanas_del_generador_de_biocore():
        out = analizador(_ventana(w))
        assert out['bpm'] is not None and abs(out['bpm'] - 72) < 8
        for b in (out['waves'] or {}).values():
            assert _ordenadas(b) == sorted(_ordenadas(b))
            if 'P' in b:
                assert 0.08 <= (b['R']['index'] - b['P']['index']) / 250.0 <= 0.30
            if 'T' in b:
                assert 0.15 <= (b['T']['index'] - b['R']['index']) / 250.0 <= 0.45
        if out['prediction'] is None:
            assert out['notes'][-1].startswith('Patrón no disponible')
        else:
            assert not any(' 0 ms' in linea for linea in out['prediction']['razonamiento'])


def test_patron_de_reglas_solo_si_es_confiable():
    for x in (_ecg_72(0), _ecg_72(20)):
        out = BiocoreAnalyzer(fs=250.0, pattern=True)(_ventana(x))
        assert abs(out['bpm'] - 72) < 1
        if out['prediction'] is None:
            assert out['notes'][-1].startswith('Patrón no disponible')
        else:
            assert out['labels']['prediction'] == 'Reglas de ECGAnalyzer (no es un modelo de ML)'
            assert not any(' 0 ms' in linea for linea in out['prediction']['razonamiento'])
    # Con 20 µV de ruido el detector de las reglas cuenta una T como latido; sin este filtro
    # el patrón saldría «AFib» sobre un ritmo sinusal.
    ruidoso = BiocoreAnalyzer(fs=250.0, pattern=True)(_ventana(_ecg_72(20)))
    assert ruidoso['prediction'] is None and 'otro detector de picos' in ruidoso['notes'][-1]


def test_si_una_parte_falla_las_demas_se_entregan():
    analizador = BiocoreAnalyzer(fs=250.0, pattern=True)

    class ReglasQueFallan(analizador._analyzer_cls):
        def measure_intervals(self, signal):
            raise ValueError('attempt to get argmax of an empty sequence')

    analizador._analyzer_cls = ReglasQueFallan
    out = analizador(_ventana(_ecg_72(0)))
    assert out['prediction'] is None and 'fallaron en esta ventana (ValueError' in out['notes'][-1]
    assert abs(out['bpm'] - 72) < 1 and out['waves']

    def delineador_que_falla(*args):
        raise IndexError('fuera de rango')

    analizador = BiocoreAnalyzer(fs=250.0)
    analizador._delineate = delineador_que_falla
    out = analizador(_ventana(_ecg_72(0)))
    assert out['waves'] is None and 'el delineador falló' in out['notes'][-1] and abs(out['bpm'] - 72) < 1


def test_tu_modelo_mas_el_bpm_de_biocore():
    class MiClaseML:
        def procesar_ventana(self, datos_ecg):
            return {'prediccion': 'clase de mi modelo'}

    analizador = CompositeAnalyzer([BiocoreAnalyzer(fs=250.0, pattern=False), ModelAnalyzer(MiClaseML())])
    r = _primer_resultado_valido(analizador)
    assert r.prediction == 'clase de mi modelo' and r.labels['prediction'] == 'MiClaseML.procesar_ventana'
    assert abs(r.bpm - 72.0) < 5 and r.labels['bpm'].startswith('Detector TKEO')
