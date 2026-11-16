"""Pulso por luz (MAX30102) y temperatura (DS18B20) con la placa ESP32 (2026-11-16): analizador de la onda de pulso,
firmware, placa simulada, calidad, servicio y la vista «Sensores en vivo» del Multisensor Fusion Lab.

Verificación por ejecución (regla 2): los firmwares de MicroPython corren en la computadora contra un MAX30102 a nivel
de registros (`biosensor_testkit.Max30102Double`) y sondas DS18B20 simuladas, y se leen por un pseudo-terminal con
pyserial de verdad. El analizador se probó además contra las grabaciones de ejemplo de HeartPy (fuera del repo, por su
licencia): 24 de 24 latidos iguales en la limpia.
"""

from __future__ import annotations

import sys
import time
from unittest.mock import patch

import numpy as np
import pytest
from streamlit.testing.v1 import AppTest

from biosensor_testkit import FastClock, Max30102Double, ScriptTransport, firmware_running, wait
from clinical.ppg_references import BEURTON_2019, ELGENDI_2013, JUBRAN_2015
from hardware.biosensors import PPG, SENSORS, TEMP, SerialBioBackend, SimulatedBioBoard
from hardware.biosensors.quality import (PPG_ISSUE_TEXT, TEMP_POWER_ON_C, is_stable, ppg_quality, temp_quality,
                                         temp_trend, valid_temperatures)
from hardware.biosensors.simulator import PPG_PI_IR, PPG_RATIO_R, TEMP_SKIN_C
from hardware.ecg_plugplay.ports import PortInfo
from hardware.eeg_live import EegLiveService, LiveConfig, LiveState
from hardware.eeg_live.devices import SENSOR_REAL, SIMULACION
from src.signals.ppg import analyze_ppg, preprocess_ppg, pulse_wave, systolic_peaks
from src.signals.ppg import analysis as ppg_analysis

QUICK = dict(poll_s=0.01, data_timeout_s=0.5, reconnect_after_s=1.5, retry_s=0.2, rate_window_s=0.5)
PORT = PortInfo('COM9', 'CP2102', vid=0x10C4, pid=0xEA60)


class Clock:
    """Reloj que solo avanza cuando la prueba lo dice: la placa simulada produce exactamente lo que corresponde."""

    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def synthetic_ppg(bpm=72.0, seconds=20.0, fs=100.0, pi=0.02, ratio=0.55, diastolic=0.45, seed=0, jitter=0.0):
    """Luz recibida (rojo, infrarrojo) con latidos de forma conocida: baja en cada latido."""
    rng = np.random.default_rng(seed)
    n = int(seconds * fs)
    beats = np.cumsum(60.0 / bpm * (1.0 + jitter * rng.uniform(-1, 1, int(seconds * bpm / 60) + 5)))
    t = np.arange(n) / fs
    pulse = np.zeros(n)
    for b in beats:
        pulse += np.exp(-0.5 * ((t - b - 0.15) / 0.06) ** 2) + diastolic * np.exp(-0.5 * ((t - b - 0.40) / 0.09) ** 2)
    pulse /= np.ptp(pulse[int(2 * fs):-int(2 * fs)])
    red = 95000.0 * (1 - pi * ratio * pulse) + rng.normal(0, 10, n)
    ir = 120000.0 * (1 - pi * pulse) + rng.normal(0, 10, n)
    return red, ir, beats


def port_for(device):
    return lambda: [PortInfo(device, 'CP2102 simulado', vid=0x10C4, pid=0xEA60)]


# ================================================================ analizador de la onda de pulso
def test_elgendi_parameters_are_the_published_ones():
    assert ppg_analysis.BAND_HZ == (0.5, 8.0)
    assert (ppg_analysis.PEAK_WINDOW_S, ppg_analysis.BEAT_WINDOW_S, ppg_analysis.BETA) == (0.111, 0.667, 0.02)
    assert 'e76585' in ELGENDI_2013 and 's13054-019-2306-z' in BEURTON_2019 and 's13054-015-0984-8' in JUBRAN_2015


def test_analyzer_recovers_rate_perfusion_and_ratio_of_a_known_wave():
    red, ir, beats = synthetic_ppg(bpm=72.0, pi=0.02, ratio=0.55)
    a = analyze_ppg(red, ir, 100.0)
    assert a.pulse_rate_bpm == pytest.approx(72.0, abs=1.0)
    assert a.perfusion_index_pct == pytest.approx(2.0, rel=0.1)
    assert a.ratio_r == pytest.approx(0.55, rel=0.05)
    assert a.irregular_fraction == 0.0 and ppg_quality(a) == ()


def test_systolic_peaks_skip_the_diastolic_wave_and_land_on_the_systole():
    for bpm in (50.0, 72.0, 120.0, 170.0):
        red, ir, beats = synthetic_ppg(bpm=bpm, diastolic=0.6, seconds=30.0)
        peaks = systolic_peaks(pulse_wave(ir, 100.0), 100.0)
        inner = [b + 0.15 for b in beats if 2.0 < b + 0.15 < 28.0]
        found = [p / 100.0 for p in peaks if 2.0 < p / 100.0 < 28.0]
        assert len(found) == len(inner), bpm                                  # uno por latido, ni dos ni cero
        assert np.max(np.abs(np.array(found) - np.array(inner))) < 0.05, bpm   # en la sístole (±50 ms)


def test_preprocess_ppg_counts_beats_not_samples():
    """Regresión: `pulse_rate` daba 60·fs (3029 con una onda de 72 a 100 Hz)."""
    t = np.arange(3000) / 100.0
    _, metrics = preprocess_ppg(np.sin(2 * np.pi * 1.2 * t) + 0.3 * np.sin(4 * np.pi * 1.2 * t), 100.0)
    assert metrics['pulse_rate'] == pytest.approx(72.0, abs=1.0)


def test_quality_flags_irregular_intervals_missing_finger_and_saturation():
    red, ir, _ = synthetic_ppg(bpm=70.0, jitter=0.45, seconds=30.0, seed=3)
    assert ppg_quality(analyze_ppg(red, ir, 100.0)) == ('irregular',)
    rng = np.random.default_rng(1)
    dark = analyze_ppg(2000 + rng.normal(0, 15, 1000), 2500 + rng.normal(0, 15, 1000), 100.0)
    assert ppg_quality(dark) == ('sin dedo',)
    rail = np.full(1000, float((1 << 18) - 1))
    assert ppg_quality(analyze_ppg(rail, rail, 100.0)) == ('saturada', 'sin pulso')
    assert 'ECG' in PPG_ISSUE_TEXT['irregular']


# ================================================================ firmware de MicroPython
def ppg_light(t):
    phase = (72.0 / 60.0 * t) % 1.0
    pulse = np.exp(-0.5 * ((phase - 0.22) / 0.07) ** 2) + 0.45 * np.exp(-0.5 * ((phase - 0.5) / 0.11) ** 2)
    return int(95000 * (1 - 0.011 * pulse)), int(120000 * (1 - 0.02 * pulse))


@pytest.mark.skipif(sys.platform.startswith('win'), reason='usa un pseudo-terminal')
def test_ppg_firmware_configures_the_max30102_and_streams_its_fifo():
    double = Max30102Double(ppg_light)

    def prepare():
        import machine
        machine.I2C.dispositivos = {0x57: double}

    with firmware_running(PPG.firmware_path, prepare) as (_, port):
        backend = SerialBioBackend(PPG, list_ports=port_for(port))
        try:
            desc = backend.open()
            got = []
            assert wait(lambda: got.append(backend.read()) or sum(g.shape[1] for g in got) >= 600, 12.0)
            double.pause = 0.6                         # el ciclo se atrasa: 60 muestras y la FIFO tiene 32
            assert wait(lambda: backend.read().size >= 0 and backend.lost_in_transit > 0, 6.0)
        finally:
            backend.close()
    assert desc.provenance == SENSOR_REAL and desc.fs == 100.0 and desc.channels == ('ROJO', 'IR')
    assert double.regs == {0x08: 0x1F, 0x0A: 0x27, 0x0C: 0x24, 0x0D: 0x24, 0x09: 0x03}   # hoja de datos
    data = np.concatenate(got, axis=1)
    a = analyze_ppg(data[0], data[1], desc.fs)
    assert a.pulse_rate_bpm == pytest.approx(72.0, abs=1.5)
    assert a.perfusion_index_pct == pytest.approx(2.0, rel=0.1) and a.ratio_r == pytest.approx(0.55, rel=0.05)
    assert backend.lost_in_transit == double.thrown > 0           # lo que tiró el sensor, ni una más ni una menos


@pytest.mark.skipif(sys.platform.startswith('win'), reason='usa un pseudo-terminal')
@pytest.mark.parametrize('devices,text', [
    ({}, 'No se encontró el MAX30102 en el bus I2C'),
    ({0x57: Max30102Double(ppg_light, part_id=0x11)}, 'hay otro sensor (PART_ID 0x11), no un MAX30102'),
])
def test_ppg_firmware_says_why_there_is_no_sensor(devices, text):
    def prepare():
        import machine
        machine.I2C.dispositivos = dict(devices)

    with firmware_running(PPG.firmware_path, prepare) as (_, port):
        backend = SerialBioBackend(PPG, list_ports=port_for(port))
        try:
            backend.open()
            assert wait(lambda: backend.read().shape[1] == 0 and bool(backend.messages), 5.0)
        finally:
            backend.close()
    assert text in backend.messages[-1]


@pytest.mark.skipif(sys.platform.startswith('win'), reason='usa un pseudo-terminal')
def test_temperature_firmware_sends_celsius_once_a_second_and_explains_a_missing_probe():
    def no_probe():
        import ds18x20
        ds18x20.DS18X20.sondas, ds18x20.DS18X20.falla = [], None

    with firmware_running(TEMP.firmware_path, no_probe) as (_, port):
        backend = SerialBioBackend(TEMP, list_ports=port_for(port))
        try:
            backend.open()
            assert wait(lambda: backend.read().shape[1] == 0 and bool(backend.messages), 5.0)
        finally:
            backend.close()
    assert 'No se encontró ningún DS18B20 en GPIO4' in backend.messages[-1]

    def probe():
        import ds18x20
        ds18x20.DS18X20.sondas, ds18x20.DS18X20.falla = [bytearray(b'\x28' + bytes(7))], None
        ds18x20.DS18X20.fuente = lambda: 33.31

    with firmware_running(TEMP.firmware_path, probe) as (_, port):
        backend = SerialBioBackend(TEMP, list_ports=port_for(port))
        try:
            desc = backend.open()
            got, t0 = [], time.monotonic()
            assert wait(lambda: got.append(backend.read()) or sum(g.shape[1] for g in got) >= 3, 8.0)
            elapsed = time.monotonic() - t0
        finally:
            backend.close()
    assert desc.provenance == SENSOR_REAL and desc.fs == 1.0 and desc.channels == ('TEMP',)
    assert np.allclose(np.concatenate(got, axis=1), 33.3125) and 1.5 < elapsed < 5.0   # 12 bits, una por segundo


def test_firmware_files_declare_what_the_pc_needs():
    ppg = PPG.firmware_path.read_text(encoding='utf-8')
    for piece in ('sensor=ppg', 'ch=ROJO;IR', 'unit=cuentas', 'bits=18', 'sim=0', "'BIO:D,%d,%s'", "'BIO?' in pedido",
                  'DIRECCION = 0x57', 'PART_ID = 0x15', 'SPO2_CFG = 0x27', 'MASCARA = 0x3FFFF'):
        assert piece in ppg, piece
    temp = TEMP.firmware_path.read_text(encoding='utf-8')
    for piece in ('sensor=temp', 'ch=TEMP', 'unit=C', 'sim=0', "'BIO:D,%d,%.4f'", "'BIO?' in pedido",
                  'CONVERSION_MS = 750', 'PIN_DATOS = 4'):
        assert piece in temp, piece
    assert {s.key for s in SENSORS} == {'emg', 'ppg', 'temp'} and all(s.firmware_path.exists() for s in SENSORS)


# ================================================================ placa simulada, calidad y servicio
def sim_backend(board, sensor, clock):
    return SerialBioBackend(sensor, list_ports=board.list_ports, open_transport=board.open_transport,
                            probe_timeout_s=1.0, clock=clock)


def test_simulated_ppg_board_rate_perfusion_ratio_motion_and_finger():
    clock = Clock()
    board = SimulatedBioBoard('ppg', clock=clock)
    backend = sim_backend(board, PPG, clock)
    assert backend.open().provenance == SIMULACION

    def collect(seconds):
        out = []
        for _ in range(int(seconds * 10)):
            clock.t += 0.1
            out.append(backend.read())
        return np.concatenate(out, axis=1)

    collect(2)
    x = collect(12)
    a = analyze_ppg(x[0], x[1], 100.0)
    assert a.pulse_rate_bpm == pytest.approx(65.0, abs=2.0)
    assert a.perfusion_index_pct == pytest.approx(PPG_PI_IR * 100, rel=0.1)
    assert a.ratio_r == pytest.approx(PPG_RATIO_R, rel=0.05) and ppg_quality(a) == ()
    board.model.set_rate(110.0)
    collect(3)
    x = collect(12)
    assert analyze_ppg(x[0], x[1], 100.0).pulse_rate_bpm == pytest.approx(110.0, abs=3.0)
    board.model.set_motion(True)
    x = collect(12)
    assert 'irregular' in ppg_quality(analyze_ppg(x[0], x[1], 100.0))
    board.model.set_motion(False)
    board.model.set_finger(False)
    x = collect(12)
    assert ppg_quality(analyze_ppg(x[0], x[1], 100.0)) == ('sin dedo',)


def test_simulated_temperature_board_warms_up_and_then_reads_stable():
    clock = Clock()
    board = SimulatedBioBoard('temp', clock=clock)
    backend = sim_backend(board, TEMP, clock)
    backend.open()

    def collect(seconds):
        out = []
        for _ in range(int(seconds)):
            clock.t += 1.0
            out.append(backend.read())
        return np.concatenate(out, axis=1)[0]

    air = collect(60)
    assert air[-1] == pytest.approx(24.0, abs=0.1) and np.allclose(air / 0.0625, np.round(air / 0.0625))
    board.model.set_on_skin(True)
    skin = collect(300)
    assert not is_stable(temp_trend(skin[:120], 1.0))                 # a los 2 min todavía sube
    assert is_stable(temp_trend(skin, 1.0)) and skin[-1] == pytest.approx(TEMP_SKIN_C, abs=0.1)
    assert temp_trend(skin[:30], 1.0) is None                          # menos de un minuto: no hay tendencia


def test_temperature_power_on_value_is_flagged_and_left_out():
    x = np.array([TEMP_POWER_ON_C] + [33.0] * 70)
    assert temp_quality(x) == ('arranque',) and temp_quality(x[1:]) == ()
    assert TEMP_POWER_ON_C not in valid_temperatures(x)
    assert temp_trend(x, 1.0) == pytest.approx(0.0, abs=1e-9)


def test_lost_samples_are_not_counted_twice():
    """Regresión: la interfaz sumaba los saltos de `seq` y el contador `perdidas` del HELLO, que ya los incluye."""
    hello = 'BIO:HELLO,sensor=temp,fw=1.0,fs=1,ch=TEMP,unit=C,blk=1,sim=0,perdidas={}'
    transport = ScriptTransport([hello.format(0), 'BIO:D,0,33.0', 'BIO:D,1,33.0', 'BIO:D,6,33.1', hello.format(4)])
    backend = SerialBioBackend(TEMP, list_ports=lambda: [PORT], open_transport=lambda p: transport,
                               probe_timeout_s=0.3)
    backend.open()
    for _ in range(5):
        backend.read()
    status = backend.status()
    assert status['perdidas'] == 4 and status['perdidas_desde_el_arranque'] == 4


def test_service_says_what_the_board_reports_when_no_samples_arrive():
    lines = ['BIO:HELLO,sensor=temp,fw=1.0,fs=1,ch=TEMP,unit=C,blk=1,sim=0'] + \
            ['BIO:E,No se encontró ningún DS18B20 en GPIO4: revisa el cable de datos.'] * 3
    service = EegLiveService(TEMP, lambda: SerialBioBackend(TEMP, list_ports=lambda: [PORT],
                                                            open_transport=lambda p: ScriptTransport(list(lines)),
                                                            probe_timeout_s=0.3),
                             LiveConfig(**QUICK), key='prueba:temp')
    service.start()
    try:
        assert wait(lambda: 'La placa dice' in service.snapshot()['message'], 5.0)
        assert 'No se encontró ningún DS18B20' in service.snapshot()['message']
        assert wait(lambda: service.snapshot()['state'] == LiveState.FAILED.value, 5.0)
        assert 'La placa dice: «No se encontró ningún DS18B20' in service.snapshot()['message']
    finally:
        service.stop()


# ================================================================ vista «Sensores en vivo» (AppTest)
def _page():
    import app.main as m
    m.render_multisensor_page()


def _texts(elements):
    return ' '.join(str(e.value) for e in elements)


def _click(at, label, where='sidebar'):
    buttons = at.sidebar.button if where == 'sidebar' else at.button
    next(b for b in buttons if b.label == label).click().run(timeout=60)


def _open_view(sensor_title, mode='Medir'):
    at = AppTest.from_function(_page)
    at.run(timeout=60)
    next(r for r in at.radio if 'Clínica' in r.options).set_value('Sensores en vivo').run(timeout=60)
    at.radio(key='msl_live_sensor').set_value(sensor_title).run(timeout=60)
    at.radio(key='msl_live_mode').set_value(mode).run(timeout=60)
    return at


@pytest.fixture
def ppg_boards():
    from app.supermodules.biosensors import live_service

    practice = live_service.make_practice('ppg', SimulatedBioBoard('ppg', clock=FastClock()))
    real = EegLiveService(PPG, lambda: SerialBioBackend(PPG, list_ports=lambda: []), LiveConfig(**QUICK),
                          key='placa:ppg')
    with patch.object(live_service, 'get_practice', lambda key: practice), \
            patch.object(live_service, 'get_board_service', lambda key: real):
        yield practice, real
    practice.service.stop()
    real.stop()


@pytest.fixture
def temp_practice():
    from app.supermodules.biosensors import live_service

    practice = live_service.make_practice('temp', SimulatedBioBoard('temp', clock=FastClock(speed=20.0)))
    with patch.object(live_service, 'get_practice', lambda key: practice):
        yield practice
    practice.service.stop()


def test_ppg_without_a_board_analyzes_nothing(ppg_boards):
    at = _open_view('Pulso por luz (MAX30102)')
    assert at.exception == []
    assert 'no se usa una señal de respaldo' in _texts(at.info)
    assert 'Frecuencia de pulso' not in _texts(at.markdown)


def test_ppg_practice_measures_pulse_and_says_spo2_is_not_available(ppg_boards):
    practice, _ = ppg_boards
    at = _open_view('Pulso por luz (MAX30102)')
    at.radio(key='msl_ppg_mode').set_value('Práctica (placa simulada)').run(timeout=60)
    _click(at, '▶ Conectar la placa simulada')
    assert wait(lambda: practice.service.snapshot()['seconds_available'] >= 8)
    _click(at, '🔄 Leer los últimos segundos')
    assert at.exception == []
    page = _texts(at.markdown) + ' ' + _texts(at.caption)
    assert 'Frecuencia de pulso' in page and 'lpm' in page and 'Índice de perfusión (IR)' in page
    assert 'curva calibrada contra mediciones directas' in page           # la SpO₂: no disponible, con el motivo
    assert 'No se guarda al gemelo' in page
    assert 'SIMULACIÓN' in _texts(at.sidebar.warning)


def test_ppg_tutorial_explains_the_sensor_and_runs_the_practice(ppg_boards):
    practice, _ = ppg_boards
    at = _open_view('Pulso por luz (MAX30102)', 'Tutorial')
    assert at.exception == []
    labels = [e.label for e in at.expander]
    for title in ('1. Qué necesitas', '3. Conecta MAX30102 a la ESP32', '7. Si algo falla',
                  '8. Qué puedes y qué no puedes concluir'):
        assert title in labels
    text = _texts(at.markdown)
    assert 'GPIO21' in text and 'No mide la SpO₂' in text and 'MAX30100' in text
    _click(at, '▶ Empezar práctica', where='main')
    assert wait(lambda: practice.service.snapshot()['seconds_available'] >= 6)
    at.run(timeout=60)
    assert at.exception == []
    _click(at, '🖐️ Quitar el dedo', where='main')
    assert practice.board.model.finger is False


def test_temperature_tutorial_runs_the_practice_without_any_fever_reading(temp_practice):
    at = _open_view('Temperatura (DS18B20)', 'Tutorial')
    assert at.exception == []
    text = _texts(at.markdown)
    assert 'GPIO4' in text and '4.7 kΩ' in text and 'Taylor 2014' in text
    assert 'fiebre' in text.lower()                                     # dice que NO sirve para eso
    _click(at, '▶ Empezar práctica', where='main')
    _click(at, '📍 Poner la sonda en la axila', where='main')
    assert temp_practice.board.model.on_skin is True
    assert wait(lambda: temp_practice.service.snapshot()['seconds_available'] >= 8)
    at.run(timeout=60)
    assert at.exception == []
    assert 'Última lectura' in _texts(at.markdown) + _texts(at.caption)
