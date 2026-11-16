"""Pruebas del servicio completo con el simulador (cualquier sistema operativo).

El simulador corre 8 veces más rápido que el tiempo real para que una ventana
de 4 s salga cada 0.25 s; los tiempos de espera del servicio (2 s sin datos)
siguen siendo reales.
"""

import sys
import threading
import time
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hardware.ecg_plugplay import (AcquisitionConfig, ConnectionState, ECGAcquisitionService, ModelAnalyzer,
                                   SimulatedECGDevice, latest_clean_segment)


class Registro:
    """Junta lo que el servicio manda por callbacks."""

    def __init__(self):
        self.estados, self.resultados, self.avisos, self.trozos = [], [], [], 0
        self.lock = threading.RLock()

    def estado(self, e):
        with self.lock:
            self.estados.append(e)

    def resultado(self, r):
        with self.lock:
            self.resultados.append(r)

    def aviso(self, a):
        with self.lock:
            self.avisos.append(a)

    def senal(self, chunk):
        with self.lock:
            self.trozos += 1

    def esperar(self, condicion, timeout):
        fin = time.monotonic() + timeout
        while time.monotonic() < fin:
            with self.lock:
                if condicion(self):
                    return True
            time.sleep(0.02)
        return False


class MiClaseML:
    """Modelo de prueba: comprueba la forma de la entrada y cuenta llamadas."""

    def __init__(self, demora=0.0, falla_en=None):
        self.llamadas = 0
        self.demora = demora
        self.falla_en = falla_en

    def procesar_ventana(self, datos_ecg):
        self.llamadas += 1
        assert datos_ecg.shape == (1, 1000) and datos_ecg.dtype == np.float32
        assert 0.0 <= float(datos_ecg.min()) and float(datos_ecg.max()) <= 1.0
        if self.falla_en is not None and self.llamadas == self.falla_en:
            raise RuntimeError('fallo a propósito')
        time.sleep(self.demora)
        return {'prediccion': 'ok', 'llamada': self.llamadas}


def _servicio(sim, modelo=None, **cfg):
    reg = Registro()
    config = AcquisitionConfig(**cfg)
    svc = ECGAcquisitionService(config, ModelAnalyzer(modelo or MiClaseML()), simulator=sim,
                                on_state=reg.estado, on_result=reg.resultado, on_warning=reg.aviso,
                                on_signal=reg.senal)
    return svc, reg


@pytest.fixture
def sim():
    return SimulatedECGDevice(speed=8.0)


def test_detecta_conecta_y_entrega_ventanas_al_modelo(sim):
    svc, reg = _servicio(sim)
    with svc:
        assert svc.wait_for(ConnectionState.CONNECTED, 5.0)
        assert reg.esperar(lambda r: len(r.resultados) >= 4, 5.0)
    estados = [e.state for e in reg.estados]
    assert estados[:3] == [ConnectionState.SEARCHING, ConnectionState.PROBING, ConnectionState.CONNECTED]
    r = reg.resultados[-1]
    assert r.valid and r.prediction == 'ok' and r.window.provenance == 'SIMULACION'
    assert r.window.ecg_mv.shape == (1000,) and r.labels['prediction'] == 'MiClaseML.procesar_ventana'
    inicios = [x.window.start_seq for x in reg.resultados]
    assert all(b - a == 500 for a, b in zip(inicios, inicios[1:]))     # solape del 50 %
    assert reg.trozos > 0                                              # la señal en vivo también llega
    assert 'SIMULACIÓN' in reg.estados[2].message                       # nunca se presenta como sensor real


def test_electrodo_suelto_descarta_ventanas_con_motivo_y_no_llama_al_modelo(sim):
    modelo = MiClaseML()
    svc, reg = _servicio(sim, modelo)
    with svc:
        assert reg.esperar(lambda r: any(x.valid for x in r.resultados), 6.0)
        sim.set_leadoff(1)
        assert reg.esperar(lambda r: sum(not x.valid for x in r.resultados) >= 3, 5.0)
        llamadas = modelo.llamadas
        sim.set_leadoff(0)
        n = len(reg.resultados)
        assert reg.esperar(lambda r: any(x.valid for x in r.resultados[n:]), 6.0)
        snap = svc.snapshot()
    malas = [x for x in reg.resultados if not x.valid]
    # Al volver a pegar el electrodo el filtro se reinicia: la ventana que solo alcanza ese
    # reinicio se descarta por eso, con su propio motivo.
    assert all('electrodo suelto' in x.reasons[0] or 'estabilizando' in x.reasons[0] for x in malas)
    assert sum('electrodo suelto' in x.reasons[0] for x in malas) >= 3
    assert all(x.prediction is None and x.window.model_input is None for x in malas)
    assert modelo.llamadas >= llamadas                       # el modelo no vio las ventanas malas
    assert snap['counters']['descartadas'] >= 3


def _evento(reg, estado, desde=0.0):
    """Primer evento `estado` registrado después de `desde` (time.time())."""
    with reg.lock:
        return next((e for e in reg.estados if e.state == estado and e.time >= desde), None)


def test_cable_fuera_cierra_limpia_avisa_y_vuelve_a_buscar(sim):
    svc, reg = _servicio(sim)
    with svc:
        assert reg.esperar(lambda r: len(r.resultados) >= 2, 6.0)
        t0 = time.time()
        sim.unplug()
        assert reg.esperar(lambda r: _evento(r, ConnectionState.SEARCHING, t0) is not None, 3.0)
        desconexion = _evento(reg, ConnectionState.DISCONNECTED, t0)
        snap = svc.snapshot()
        assert snap['last_result'] is None and snap['signal_mv'].size == 0 and snap['buffer_fill'][0] == 0
        sim.plug()
        assert svc.wait_for(ConnectionState.CONNECTED, 5.0)
        n = len(reg.resultados)
        assert reg.esperar(lambda r: len(r.resultados) > n and r.resultados[-1].valid, 8.0)
    assert desconexion.time - t0 < 1.0                               # reacciona al instante, no a los 2 s
    assert 'Se desconectó el dispositivo' in desconexion.message and 'se vuelve a buscar' in desconexion.message
    assert svc.snapshot()['counters']['conexiones'] == 2


def test_dos_segundos_sin_datos_es_una_desconexion(sim):
    svc, reg = _servicio(sim, not_ecg_retry_s=0.5)
    with svc:
        assert reg.esperar(lambda r: len(r.resultados) >= 1, 6.0)
        t0 = time.time()
        sim.set_frozen(True)
        assert reg.esperar(lambda r: _evento(r, ConnectionState.DISCONNECTED, t0) is not None, 4.0)
        desconexion = _evento(reg, ConnectionState.DISCONNECTED, t0)
        sim.set_frozen(False)
        assert reg.esperar(lambda r: _evento(r, ConnectionState.CONNECTED, desconexion.time) is not None, 8.0)
    assert 1.9 <= desconexion.time - t0 <= 2.6
    assert 'No llegan datos' in desconexion.message


def test_un_modelo_lento_no_frena_la_adquisicion(sim):
    modelo = MiClaseML(demora=1.0)
    svc, reg = _servicio(sim, modelo)
    with svc:
        assert svc.wait_for(ConnectionState.CONNECTED, 5.0)
        time.sleep(3.0)
        snap = svc.snapshot()
    # 3 s a 8x = ~6000 muestras: la lectura siguió a tiempo aunque el modelo tarde 1 s por ventana.
    assert snap['stats']['recibidas'] > 4500
    assert snap['counters']['descartadas_por_lentitud'] >= 3
    assert 1 <= modelo.llamadas <= 4


def test_un_error_del_modelo_no_tumba_el_servicio(sim):
    svc, reg = _servicio(sim, MiClaseML(falla_en=1))
    with svc:
        assert reg.esperar(lambda r: len(r.resultados) >= 3, 6.0)
        assert svc.state == ConnectionState.CONNECTED
    assert reg.resultados[0].error == 'El análisis falló: RuntimeError: fallo a propósito'
    assert reg.resultados[-1].valid and reg.resultados[-1].prediction == 'ok'


def test_sin_handshake_lo_reconoce_por_las_tramas():
    sim = SimulatedECGDevice(speed=8.0, send_hello=False)
    svc, reg = _servicio(sim)
    with svc:
        assert svc.wait_for(ConnectionState.CONNECTED, 5.0)
        assert reg.esperar(lambda r: len(r.resultados) >= 1, 5.0)
    assert 'sin ECG:HELLO' in [e for e in reg.estados if e.state == ConnectionState.CONNECTED][0].message


def test_frecuencia_distinta_a_la_del_modelo_se_avisa_y_no_se_analiza():
    sim = SimulatedECGDevice(speed=8.0, fs=500.0)
    modelo = MiClaseML()
    svc, reg = _servicio(sim, modelo)
    with svc:
        assert reg.esperar(lambda r: len(r.resultados) >= 2, 6.0)
    assert modelo.llamadas == 0
    assert all('500 Hz' in x.reasons[0] for x in reg.resultados)
    assert any('500 Hz' in a for a in reg.avisos)


def test_tramo_limpio_para_pantallas_que_no_aceptan_nan(sim):
    svc, reg = _servicio(sim)
    assert latest_clean_segment(svc.snapshot()) == (None, 'Detenido.')
    with svc:
        assert reg.esperar(lambda r: any(x.valid for x in r.resultados), 6.0)
        senal, motivo = latest_clean_segment(svc.snapshot())
        assert senal is not None and senal.size >= 1000 and np.isfinite(senal).all() and motivo == ''
        sim.set_leadoff(1)
        time.sleep(0.3)
        senal, motivo = latest_clean_segment(svc.snapshot())
        assert senal is None and 'electrodo suelto' in motivo
        sim.set_leadoff(0)
        time.sleep(0.2)
        senal, motivo = latest_clean_segment(svc.snapshot())
        assert senal is None and motivo.startswith('Juntando señal limpia')    # no muestra lo de antes del problema
        assert reg.esperar(lambda r: latest_clean_segment(svc.snapshot())[0] is not None, 3.0)


def test_volver_a_arrancar_empieza_de_cero():
    sim = SimulatedECGDevice(speed=8.0, fs=500.0)          # frecuencia distinta: deja descartes y un aviso
    svc, reg = _servicio(sim)
    with svc:
        assert reg.esperar(lambda r: len(r.resultados) >= 2, 6.0)
    viejo = svc.snapshot()
    assert viejo['counters']['descartadas'] >= 2 and viejo['warnings']
    sim.unplug()                                            # que no vuelva a conectarse durante la prueba
    with svc:
        time.sleep(0.3)
        nuevo = svc.snapshot()
    assert nuevo['counters']['descartadas'] == 0 and nuevo['counters']['conexiones'] == 0
    assert list(nuevo['warnings']) == [] and nuevo['state'] == 'buscando'


def test_detener_cierra_todo():
    sim = SimulatedECGDevice(speed=8.0)
    svc, reg = _servicio(sim)
    svc.start()
    assert svc.wait_for(ConnectionState.CONNECTED, 5.0)
    svc.stop()
    assert svc.state == ConnectionState.STOPPED and not svc.is_running
    assert not [t for t in threading.enumerate() if t.name.startswith('ecg-') and t.is_alive()]
