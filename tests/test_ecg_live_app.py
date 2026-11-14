"""ECG Plug & Play dentro del ECG Lab (AppTest de la app completa).

La fuente «Hardware ESP32 en vivo» del Monitoreo y la pestaña «Placa en vivo
(tutorial)» con su práctica. Ninguna prueba abre un puerto real: los servicios se
reemplazan por otros con la placa simulada (8 veces más rápida) y se detienen al
terminar. La base es la temporal de `conftest.py`.
"""

import sys
import time
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
MAIN = str((RAIZ / 'app' / 'main.py').resolve())

from app.supermodules.ecg_live import service as live_service  # noqa: E402
from app.supermodules.ecg_live.monitor_source import TUTORIAL_TAB  # noqa: E402
from app.supermodules.ecg_live.tutorial import FIRMWARE_PATH  # noqa: E402
from hardware.ecg_plugplay import (AcquisitionConfig, BiocoreAnalyzer, ConnectionState,  # noqa: E402
                                   ECGAcquisitionService, PortInfo, SimulatedECGDevice)
from hardware.ecg_plugplay.simulator import SimulatedTransport  # noqa: E402

CP2102 = dict(vid=0x10C4, pid=0xEA60)


class _ComoSensor(SimulatedTransport):
    """Transporte de prueba que se presenta como sensor: solo ejercita la rama SENSOR_REAL de la UI."""

    provenance = 'SENSOR_REAL'


def _servicio(tipo):
    analizador = BiocoreAnalyzer(fs=250.0)
    if tipo == 'simulador':
        return ECGAcquisitionService(AcquisitionConfig(), analizador, simulator=SimulatedECGDevice(speed=8.0))
    if tipo == 'como_sensor':
        placa = SimulatedECGDevice(speed=8.0, send_hello=False)       # sin HELLO no hay sim=1
        return ECGAcquisitionService(AcquisitionConfig(), analizador,
                                     list_ports_fn=lambda: [PortInfo('COM9', 'CP2102', **CP2102)],
                                     transport_factory=lambda port: _ComoSensor(placa))
    return ECGAcquisitionService(AcquisitionConfig(), analizador, list_ports_fn=lambda: [])   # sin placa


@pytest.fixture
def en_vivo(monkeypatch, request):
    svc = _servicio(request.param)
    monkeypatch.setattr(live_service, 'get_live_service', lambda: svc)
    svc.start()
    yield svc
    svc.stop()


def _ecg_lab():
    at = AppTest.from_file(MAIN, default_timeout=240)
    at.session_state['biocore_ai_entry_done'] = True
    at.session_state['selected_hub'] = 'Clinical Hub'
    at.session_state['selected_page'] = '🫀 ECG Lab'
    at.run()
    return at


def _monitoreo_con_hardware():
    at = _ecg_lab()
    next(r for r in at.sidebar.radio if r.label == 'ECG Source').set_value('Hardware ESP32 en vivo').run()
    return at


def _textos(*grupos):
    return ' '.join(x.value for grupo in grupos for x in grupo)


@pytest.mark.parametrize('en_vivo', ['simulador', 'como_sensor'], indirect=True)
def test_monitoreo_analiza_la_senal_de_la_placa(en_vivo, request):
    assert en_vivo.wait_for(ConnectionState.CONNECTED, 5.0)
    time.sleep(1.0)                                   # 8 s simulados: más que los 4 s limpios que pide la rama
    at = _monitoreo_con_hardware()
    assert at.exception == [], at.exception
    barra = _textos(at.sidebar.success, at.sidebar.warning, at.sidebar.info)
    if request.node.callspec.params['en_vivo'] == 'como_sensor':
        assert 'PROCEDENCIA: SENSOR_REAL' in barra and 'SIMULACIÓN' not in barra
    else:
        assert 'PROCEDENCIA: SIMULACIÓN' in barra and 'SENSOR_REAL' not in barra
    assert not [s for s in at.sidebar.slider if s.label == 'Demo HR (bpm)']   # no cayó a la demo
    pagina = _textos(at.main.markdown)
    assert '**Heart Rate**' in pagina


@pytest.mark.parametrize('en_vivo', ['sin_placa'], indirect=True)
def test_sin_placa_dice_por_que_y_usa_la_demo(en_vivo):
    at = _monitoreo_con_hardware()
    assert at.exception == [], at.exception
    assert 'Buscando un dispositivo de ECG' in _textos(at.sidebar.info)
    assert [s for s in at.sidebar.slider if s.label == 'Demo HR (bpm)']     # la página cae a la demo
    assert 'SENSOR_REAL' not in _textos(at.sidebar.success, at.sidebar.warning)


@pytest.mark.parametrize('en_vivo', ['simulador'], indirect=True)
def test_soltar_el_puerto_y_volver_a_buscar(en_vivo):
    assert en_vivo.wait_for(ConnectionState.CONNECTED, 5.0)
    at = _monitoreo_con_hardware()
    next(b for b in at.sidebar.button if b.key == 'ecglab_monitor_pp_stop').click().run()
    assert not en_vivo.is_running and en_vivo.state == ConnectionState.STOPPED
    assert 'Detenido.' in _textos(at.sidebar.info)
    next(b for b in at.sidebar.button if b.key == 'ecglab_monitor_pp_start').click().run()
    assert en_vivo.is_running and en_vivo.wait_for(ConnectionState.CONNECTED, 5.0)
    assert at.exception == [], at.exception


def test_el_tutorial_se_dibuja_completo():
    at = _ecg_lab()
    assert at.exception == [], at.exception
    assert TUTORIAL_TAB in [t.label for t in at.tabs]
    pagina = _textos(at.markdown)
    for texto in ('De dónde sale cada número', 'GPIO34', 'Soltar el puerto', 'Qué significa cada estado',
                  'Electrodo suelto', 'no respondió como placa de ECG', 'Una sola derivación', 'Kligfield',
                  'Practica sin placa'):
        assert texto in pagina, texto
    assert '<svg' in pagina                                       # diagrama de conexiones
    assert 'computadora va con batería' in _textos(at.warning)
    titulos = [e.label for e in at.expander]
    assert '2. Seguridad (léelo antes de pegar los electrodos)' in titulos and len(titulos) >= 8
    assert any(b.key == 'ecglab_tutorial_start' for b in at.button)
    descargas = at.get('download_button')
    assert descargas and FIRMWARE_PATH.exists()


@pytest.fixture
def practica(monkeypatch):
    placa = SimulatedECGDevice(speed=8.0)
    p = live_service.Practice(ECGAcquisitionService(AcquisitionConfig(), BiocoreAnalyzer(fs=250.0),
                                                    simulator=placa), placa)
    monkeypatch.setattr(live_service, 'get_practice', lambda: p)
    yield p
    p.service.stop()


def _boton(at, key):
    return next(b for b in at.button if b.key == key)


def test_practica_conecta_mide_y_reacciona(practica):
    at = _ecg_lab()
    _boton(at, 'ecglab_tutorial_start').click().run()
    assert practica.service.wait_for(ConnectionState.CONNECTED, 5.0)
    time.sleep(1.2)
    at.run()
    assert at.exception == [], at.exception
    assert 'PROCEDENCIA: SIMULACIÓN' in _textos(at.caption)
    medida = next(m for m in at.metric if m.label == 'Frecuencia medida (TKEO)')
    assert abs(float(medida.value.split()[0]) - 72) <= 5
    # Despegar un electrodo: la ventana se descarta con su motivo.
    _boton(at, 'ecglab_tutorial_lo_on').click().run()
    assert practica.device.leadoff
    time.sleep(1.2)
    at.run()
    assert 'electrodo suelto' in _textos(at.warning)
    _boton(at, 'ecglab_tutorial_lo_off').click().run()
    # Desconectar el cable: la práctica lo detecta y vuelve a buscar.
    _boton(at, 'ecglab_tutorial_unplug').click().run()
    assert practica.service.wait_for(ConnectionState.SEARCHING, 3.0)
    _boton(at, 'ecglab_tutorial_plug').click().run()
    assert practica.service.wait_for(ConnectionState.CONNECTED, 5.0)
    _boton(at, 'ecglab_tutorial_stop').click().run()
    assert not practica.service.is_running
    assert any(b.key == 'ecglab_tutorial_start' for b in at.button)
    assert at.exception == [], at.exception
