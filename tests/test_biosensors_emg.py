"""EMG en vivo con la placa ESP32 + MyoWare 2.0 (2026-11-14): protocolo, conversión, conexión, firmware, simulador,
calidad, servicio y el EMG Muscle Lab.

Verificación por ejecución (regla 2): el firmware de MicroPython corre en la computadora con `machine` simulado y
habla por un pseudo-terminal que se lee con pyserial de verdad; la placa simulada entra por el mismo camino; la
página se recorre con AppTest hasta el guardado al gemelo.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from streamlit.testing.v1 import AppTest

from hardware.biosensors import (EMG, DataBlock, DeviceMessage, Hello, Other, SerialBioBackend, SimulatedBioBoard,
                                 data_line, hello_line, parse_line)
from hardware.biosensors.quality import EMG_RAIL_MV, emg_quality, prepare, rms_mv
from hardware.biosensors.sensors import emg_to_mv
from hardware.ecg_plugplay.ports import PortError, PortInfo
from hardware.eeg_live import BackendError, EegLiveService, LiveConfig, LiveState
from hardware.eeg_live.devices import SENSOR_REAL, SIMULACION
from hardware.eeg_live.quality import mains_line_rms

from biosensor_testkit import RAIZ, FastClock, ScriptTransport, firmware_running, wait  # noqa: E402
QUICK = dict(poll_s=0.01, data_timeout_s=0.5, reconnect_after_s=1.5, retry_s=0.2, rate_window_s=0.5)


def sim_backend(board, **kw):
    return SerialBioBackend(EMG, list_ports=board.list_ports, open_transport=board.open_transport,
                            probe_timeout_s=kw.pop('probe_timeout_s', 1.5), **kw)


# ================================================================ protocolo
def test_protocol_frames():
    hello = parse_line('BIO:HELLO,sensor=EMG,fw=1.0,fs=1000,ch=EMG,unit=adc,bits=12,vref=3.3,gain=200,sim=0,raro=x')
    assert isinstance(hello, Hello) and hello.sensor == 'emg' and hello.fs == 1000.0
    assert hello.channels == ('EMG',) and hello.number('gain') == 200.0 and not hello.simulated
    block = parse_line('BIO:D,40,2048,2050,2047')
    assert isinstance(block, DataBlock) and block.seq == 40 and block.samples == ((2048.0,), (2050.0,), (2047.0,))
    multi = parse_line('BIO:D,0,10;20,11;21')
    assert multi.samples == ((10.0, 20.0), (11.0, 21.0))
    assert isinstance(parse_line('BIO:E,sensor sin respuesta'), DeviceMessage)
    for line, kind in (('BIO:D,1,10;20,11', 'corrupta'), ('BIO:D,x,1', 'corrupta'), ('BIO:D,-3,1', 'corrupta'),
                       ('ECG:D,0,0,2048', 'ecg'), ('>>> ', 'repl'), ('Traceback (most recent call last):', 'traceback'),
                       ('rst:0x1 (POWERON_RESET)', 'arranque'), ('hola', 'desconocida'), ('', 'vacia')):
        frame = parse_line(line)
        assert isinstance(frame, Other) and frame.kind == kind, line
    again = parse_line(data_line(7, [[1], [2.5]]))
    assert again.seq == 7 and again.samples == ((1.0,), (2.5,))
    assert parse_line(hello_line(sensor='emg', fs=500)).fs == 500.0


def test_emg_counts_to_mv_follow_the_myoware_datasheet():
    hello = Hello({'bits': '12', 'vref': '3.3', 'gain': '200'})
    mv = emg_to_mv(np.array([[0.0, 2047.5, 4095.0]]), hello)
    assert mv[0] == pytest.approx([-EMG_RAIL_MV, 0.0, EMG_RAIL_MV])        # ±1.65 V / 200 = ±8.25 mV
    assert EMG_RAIL_MV == pytest.approx(8.25)


# ================================================================ conexión
PORT = PortInfo('COM9', 'CP2102', vid=0x10C4, pid=0xEA60)
HELLO = 'BIO:HELLO,sensor=emg,fw=1.0,fs=1000,ch=EMG,unit=adc,bits=12,vref=3.3,gain=200,blk=3,sim=0'


def scripted_backend(lines, **kw):
    transport = ScriptTransport(lines, **kw)
    return SerialBioBackend(EMG, list_ports=lambda: [PORT], open_transport=lambda p: transport,
                            probe_timeout_s=0.3), transport


def test_backend_accepts_the_hello_converts_and_counts_lost_samples():
    backend, transport = scripted_backend([HELLO, 'BIO:D,0,2048,2048,2048', 'BIO:D,3,4095,0,2048',
                                           'BIO:D,10,2048,2048,2048', 'BIO:E,ADC caliente'])
    desc = backend.open()
    assert desc.provenance == SENSOR_REAL and desc.fs == 1000.0 and desc.channels == ('EMG',)
    assert desc.detail == 'placa EMG en COM9 (firmware 1.0)' and transport.written[0] == b'BIO?\n'
    data = np.concatenate([backend.read() for _ in range(5)], axis=1)
    assert data.shape == (1, 9)
    assert data[0, 3] == pytest.approx(EMG_RAIL_MV, abs=0.01) and data[0, 4] == pytest.approx(-EMG_RAIL_MV, abs=0.01)
    status = backend.status()
    assert status['perdidas'] == 4 and status['avisos'] == ['ADC caliente']


def test_backend_marks_the_simulator_as_simulation():
    backend, _ = scripted_backend([HELLO.replace('sim=0', 'sim=1')])
    assert backend.open().provenance == SIMULACION


@pytest.mark.parametrize('lines,text', [
    (['BIO:HELLO,sensor=ppg,fs=100,ch=ROJO;IR'], 'es una placa de Pulso por luz .*, no de EMG'),
    (['BIO:HELLO,sensor=eda,fs=10,ch=EDA'], 'es una placa de «eda», no de EMG'),
    (['ECG:HELLO,fw=1.0,fs=250', 'ECG:D,0,0,2048'], 'es la placa de ECG de BIOCORE'),
    (['>>> '], 'MicroPython esperando órdenes'),
    (['Traceback (most recent call last):'], 'se detuvo con un error'),
    (['basura'], 'no respondió como una placa de EMG'),
])
def test_backend_explains_what_else_is_on_the_port(lines, text):
    backend, _ = scripted_backend(lines)
    with pytest.raises(BackendError, match=text):
        backend.open()


def test_backend_without_ports_or_with_a_busy_port():
    with pytest.raises(BackendError, match='No hay ninguna placa conectada por USB'):
        SerialBioBackend(EMG, list_ports=lambda: []).open()

    def busy(port):
        raise PortError('ocupado', port.device, f'{port.device} está ocupado por otro programa. Cierra Thonny…')

    with pytest.raises(BackendError, match='ocupado por otro programa'):
        SerialBioBackend(EMG, list_ports=lambda: [PORT], open_transport=busy).open()


def test_backend_rejects_a_hello_without_fs_and_reports_a_lost_cable():
    backend, _ = scripted_backend(['BIO:HELLO,sensor=emg,ch=EMG'])
    with pytest.raises(BackendError, match='frecuencia de muestreo'):
        backend.open()
    backend, _ = scripted_backend([HELLO], closed_after=1)
    backend.open()
    with pytest.raises(BackendError, match='se desconectó'):
        backend.read()


# ================================================================ firmware de MicroPython
@pytest.mark.skipif(sys.platform.startswith('win'), reason='usa un pseudo-terminal')
def test_firmware_end_to_end_through_a_real_serial_port():
    def prepare():
        import machine
        machine.ADC.fuente = lambda: 2048 + 400                # +400 cuentas sobre el centro

    with firmware_running(EMG.firmware_path, prepare) as (_, port):
        backend = SerialBioBackend(EMG, list_ports=lambda: [PortInfo(port, 'CP2102 simulado', vid=0x10C4, pid=0xEA60)])
        try:
            desc = backend.open()
            got = []
            assert wait(lambda: got.append(backend.read()) or sum(g.shape[1] for g in got) > 200, 5.0)
        finally:
            backend.close()
    assert desc.provenance == SENSOR_REAL and desc.fs == 1000.0       # el firmware real no se declara simulador
    data = np.concatenate(got, axis=1)
    assert np.allclose(data, (2448 / 4095 * 3.3 - 1.65) / 200 * 1000, atol=1e-6)


def test_firmware_declares_what_the_pc_needs():
    text = EMG.firmware_path.read_text(encoding='utf-8')
    for piece in ('sensor=emg', 'fs=%d', 'ch=EMG', 'unit=adc', 'gain=%d', 'sim=0', "'BIO:D,%d,%s'", "'BIO?' in pedido"):
        assert piece in text, piece


# ================================================================ placa simulada y calidad
def test_simulated_board_rms_follows_the_contraction_and_flags_a_loose_electrode():
    board = SimulatedBioBoard('emg', clock=FastClock())
    backend = sim_backend(board)
    assert backend.open().provenance == SIMULACION

    def collect(seconds):
        chunks, n = [], 0
        while n < seconds * 1000:
            x = backend.read()
            chunks.append(x)
            n += x.shape[1]
        return np.concatenate(chunks, axis=1)[0]

    collect(0.5)
    rest = collect(2.0)
    board.model.set_level(0.8)
    collect(0.5)
    strong = collect(2.0)
    board.model.set_electrode_off(True)
    loose = collect(2.0)
    assert rms_mv(rest, 1000.0) == pytest.approx(0.0093, rel=0.25)          # 10 µV en la banda de 20-450 Hz
    assert rms_mv(strong, 1000.0) == pytest.approx(0.4, rel=0.25)           # 0.5 mV × 0.8
    assert emg_quality(rest, 1000.0, 60.0) == () and emg_quality(strong, 1000.0, 60.0) == ()
    assert 'red' in emg_quality(loose, 1000.0, 60.0)
    board.unplug()
    with pytest.raises(BackendError):
        backend.read()


def test_simulated_board_skips_ahead_like_the_firmware_when_nobody_reads():
    now = [0.0]
    board = SimulatedBioBoard('emg', clock=lambda: now[0])
    transport = board.open_transport(board.port)
    first = transport.read(0.0).decode().splitlines()
    assert first[0].startswith('BIO:HELLO') and 'sim=1' in first[0]
    now[0] = 5.0                                                   # 5 s sin leer
    lines = transport.read(0.0).decode().splitlines()
    seqs = [parse_line(line).seq for line in lines if line.startswith('BIO:D')]
    assert seqs and seqs[0] > 2000 and 'perdidas=' in board._hello()


def test_quality_flags_flat_and_saturated_signals():
    rng = np.random.default_rng(0)
    assert emg_quality(np.full(2000, -EMG_RAIL_MV), 1000.0, None) == ('saturada', 'plana')
    clipped = np.clip(rng.normal(0, 10, 2000), -EMG_RAIL_MV, EMG_RAIL_MV)
    assert 'saturada' in emg_quality(clipped, 1000.0, None)
    t = np.arange(2000) / 1000.0
    hum = 0.2 * np.sin(2 * np.pi * 50 * t) + rng.normal(0, 0.01, 2000)
    assert emg_quality(hum, 1000.0, 50.0) == ('red',) and emg_quality(hum, 1000.0, 60.0) == ()
    assert np.std(prepare(hum, 1000.0, 50.0)) < 0.05


def test_mains_check_tells_a_strong_contraction_from_hum():
    """Regresión: medir solo 58-62 Hz marcaba «red» en una contracción fuerte, porque el EMG también tiene potencia
    ahí (con 1 mV de RMS, en casi todas las ventanas). El zumbido se mide como una línea sobre el piso del espectro."""
    from scipy.signal import butter, lfilter
    fs, t = 1000.0, np.arange(2000) / 1000.0
    b, a = butter(2, [20 / 500, 450 / 500], btype='band')
    for seed in range(20):
        x = lfilter(b, a, np.random.default_rng(seed).normal(0, 1, t.size))
        strong = x / np.std(x)                                              # 1 mV de RMS: contracción fuerte
        assert emg_quality(strong, fs, 60.0) == ()
        assert emg_quality(strong + 0.5 * np.sqrt(2) * np.sin(2 * np.pi * 60 * t), fs, 60.0) == ('red',)
    hum = 0.1 * np.sqrt(2) * np.sin(2 * np.pi * 60 * t) + np.random.default_rng(0).normal(0, 0.01, t.size)
    assert mains_line_rms(hum, fs, 60.0) == pytest.approx(0.1, rel=0.02)
    assert mains_line_rms(hum, fs, 50.0) == 0.0
    assert mains_line_rms(hum[:1500], fs, 60.0) is None                     # menos de 2 s: no se mide


# ================================================================ servicio
def test_service_streams_the_simulated_board_and_recovers_from_unplugging():
    board = SimulatedBioBoard('emg', clock=FastClock())
    service = EegLiveService(EMG, lambda: sim_backend(board), LiveConfig(**QUICK)).start()
    try:
        assert service.wait_for(LiveState.STREAMING, 5)
        assert wait(lambda: service.snapshot()['seconds_available'] >= 2)
        snap = service.snapshot(seconds=1.0)
        assert snap['provenance'] == SIMULACION and snap['data'].shape == (1, 1000)
        assert snap['backend_status']['firmware'] == 'sim-1.0'
        board.unplug()
        assert service.wait_for(LiveState.FAILED, 3)
        assert service.snapshot()['provenance'] is None and service.snapshot()['backend_status'] == {}
        board.plug()
        assert service.wait_for(LiveState.STREAMING, 5)
    finally:
        service.stop()


# ================================================================ la página
def test_emg_twin_helpers():
    from app.supermodules.biosensors.emg import EmgLive, save_blocker, twin_provenance
    from domain.physiology.state import Provenance

    real = EmgLive(np.zeros(10), 1000.0, 'placa EMG en COM9', SENSOR_REAL, (), 0.1)
    assert twin_provenance(None)[0] == Provenance.SIMULACION
    assert twin_provenance(real)[0] == Provenance.SENSOR_REAL
    sim = EmgLive(np.zeros(10), 1000.0, 'placa simulada', SIMULACION, (), 0.1)
    assert twin_provenance(sim)[0] == Provenance.SIMULACION
    assert save_blocker(real) is None
    noisy = EmgLive(np.zeros(10), 1000.0, 'placa EMG en COM9', SENSOR_REAL, ('red',), 0.1)
    assert 'zumbido de la red' in save_blocker(noisy)


def test_old_emg_live_path_is_gone():
    main = (RAIZ / 'app' / 'main.py').read_text(encoding='utf-8')
    for ghost in ("['Demo','CSV','Live Hardware']", "source == 'Live Hardware'", 'EMGStreamer(',
                  'usando demo mientras se conecta', 'SensorManager()'):
        assert ghost not in main, ghost              # el código retirado; los comentarios históricos pueden nombrarlo


@pytest.fixture
def ups(tmp_path):
    from domain.physiology.state import create_patient, init_db, make_engine, make_session_factory

    engine = make_engine(Path(str(tmp_path / 'emg_live_test.db')))
    init_db(engine)
    sf = make_session_factory(engine)
    with sf() as s:
        pid = create_patient(s, display_name='Paciente EMG en vivo (test)')
    return sf, pid


def _page():
    import app.main as m
    m.render_emg_page()


def _apptest(ups):
    sf, pid = ups
    at = AppTest.from_function(_page)
    at.session_state['twin_shell_ups_session_factory'] = sf
    at.session_state['twin_shell_ups_patient_id'] = pid
    return at


def _texts(elements):
    return ' '.join(str(e.value) for e in elements)


def _click(at, label, where='sidebar'):
    buttons = at.sidebar.button if where == 'sidebar' else at.button
    next(b for b in buttons if b.label == label).click().run(timeout=60)


class RealLookingBoard(SimulatedBioBoard):
    """Doble de prueba de una placa real: el mismo simulador, pero su HELLO dice sim=0."""

    def _hello(self):
        return super()._hello().replace('sim=1', 'sim=0')


@pytest.fixture
def boards():
    from app.supermodules.biosensors import live_service

    practice = live_service.make_practice('emg', SimulatedBioBoard('emg', clock=FastClock()))
    real_board = RealLookingBoard('emg', clock=FastClock())
    real = EegLiveService(EMG, lambda: sim_backend(real_board), LiveConfig(**QUICK), key='placa:emg')
    with patch.object(live_service, 'get_practice', lambda key: practice), \
            patch.object(live_service, 'get_board_service', lambda key: real):
        yield practice, real, real_board
    practice.service.stop()
    real.stop()


def _live(at):
    at.run(timeout=60)
    next(r for r in at.radio if r.label == 'Origen EMG').set_value('Sensor en vivo (ESP32 + MyoWare)').run(timeout=60)
    return at


def test_demo_source_keeps_working_with_honest_texts(ups):
    at = _apptest(ups)
    at.run(timeout=60)
    assert at.exception == []
    markdown = _texts(at.markdown)
    assert 'Activación muscular' in markdown and 'RMS del EMG (20-450 Hz)' in markdown
    assert 'riesgo de lesión' not in markdown and 'no es el porcentaje de la contracción máxima' in markdown.lower()


def test_live_source_without_a_board_analyzes_nothing(ups, boards):
    at = _live(_apptest(ups))
    assert at.exception == []
    assert 'no se usa una señal de respaldo' in _texts(at.info)
    assert not any(b.key == 'emg_lab_save_to_ups' for b in at.button)


def test_practice_board_is_analyzed_and_saved_as_simulation(ups, boards):
    from domain.physiology.state import Provenance, get_latest_state

    practice, _, _ = boards
    at = _live(_apptest(ups))
    next(r for r in at.sidebar.radio if r.label == 'Placa').set_value('Práctica (placa simulada)').run(timeout=60)
    _click(at, '▶ Conectar la placa simulada')
    assert wait(lambda: practice.service.snapshot()['seconds_available'] >= 16, 20)
    _click(at, '🔄 Leer los últimos segundos')
    assert at.exception == []
    assert 'PROCEDENCIA: SIMULACIÓN' in _texts(at.sidebar.warning)
    assert ' mV' in _texts(at.markdown)
    _click(at, '💾 Guardar estado al gemelo', where='main')
    sf, pid = ups
    with sf() as s:
        activation = get_latest_state(s, pid).muscular.descriptors['activation']
    assert activation.provenance == Provenance.SIMULACION and 'SIMULACIÓN' in activation.source_detail


def test_real_board_saves_as_sensor_real_and_a_loose_electrode_blocks_it(ups, boards):
    from domain.physiology.state import Provenance, get_latest_state

    _, real, real_board = boards
    at = _live(_apptest(ups))
    _click(at, '▶ Buscar la placa')
    assert wait(lambda: real.snapshot()['seconds_available'] >= 16, 20)
    _click(at, '🔄 Leer los últimos segundos')
    assert 'PROCEDENCIA: SENSOR_REAL' in _texts(at.sidebar.success)
    _click(at, '💾 Guardar estado al gemelo', where='main')
    sf, pid = ups
    with sf() as s:
        activation = get_latest_state(s, pid).muscular.descriptors['activation']
    assert activation.provenance == Provenance.SENSOR_REAL and 'SENSOR_REAL' in activation.source_detail
    real_board.model.set_electrode_off(True)
    time.sleep(1.0)
    _click(at, '🔄 Leer los últimos segundos')
    assert 'No se guarda al gemelo' in _texts(at.warning)
    assert not any(b.key == 'emg_lab_save_to_ups' for b in at.button)


def test_tutorial_view_renders_and_runs_the_practice(ups, boards):
    practice, _, _ = boards
    at = _apptest(ups)
    at.run(timeout=60)
    next(r for r in at.radio if 'Clínica' in r.options).set_value('Sensor en vivo (tutorial)').run(timeout=60)
    assert at.exception == []
    labels = [e.label for e in at.expander]
    for title in ('1. Qué necesitas', '3. Conecta MyoWare 2.0 a la ESP32', '4. Carga el firmware en la ESP32',
                  '5. Coloca el sensor', '8. Qué puedes y qué no puedes concluir'):
        assert title in labels
    assert 'GPIO34' in _texts(at.markdown) and 'paralela a las fibras' in _texts(at.markdown)
    _click(at, '▶ Empezar práctica', where='main')
    assert practice.service.is_running
    assert wait(lambda: practice.service.snapshot()['seconds_available'] >= 3)
    at.run(timeout=60)
    assert at.exception == []
    _click(at, '💪 Contraer fuerte (80 %)', where='main')
    assert practice.board.model.level == 0.8


def test_mains_notch_leaves_no_false_oscillation_at_the_window_edges():
    t = np.arange(3000) / 1000.0
    hum = 3.0 * np.sin(2 * np.pi * 60 * t) + np.random.default_rng(0).normal(0, 0.01, t.size)
    out = prepare(hum, 1000.0, 60.0)
    assert np.max(np.abs(out[:300])) < 2 * np.max(np.abs(out[1000:2000]))      # antes: 1.37 mV en el borde
