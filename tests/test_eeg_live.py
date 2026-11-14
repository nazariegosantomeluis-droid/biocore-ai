"""EEG en vivo (2026-11-14): catálogo, conexiones, simulador, calidad, servicio, montaje y la página.

Verificación por ejecución (regla 2): las conexiones se prueban con módulos falsos de BrainFlow y pylsl y, cuando
están instalados, también con el tablero sintético de BrainFlow y un flujo LSL real en esta misma máquina; la
página se recorre con AppTest hasta el guardado al gemelo.
"""

from __future__ import annotations

import time
import types
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from streamlit.testing.v1 import AppTest

from hardware.eeg_live import (DEVICES, NO_VERIFICABLE, SENSOR_REAL, SIMULACION, Backend, BackendError,
                               BrainFlowBackend, EegLiveService, LiveConfig, LiveState, LslBackend, LslStreamChoice,
                               SimulatedEegDevice, SimulatorBackend, StreamDescription, assess_channels,
                               backend_unavailable_reason, get_device, prepare)
from hardware.eeg_live.backends import explain_brainflow_error, unit_scales
from hardware.eeg_live.montage import POSITIONS, SPHERE
from hardware.eeg_live.service import _Ring
from hardware.eeg_live.simulator import BLINK_PEAK_UV, BLINK_WEIGHTS, CHANNELS
from src.signals.eeg import EegAnalyzer

FS = 250.0
HAS_BRAINFLOW = backend_unavailable_reason('brainflow') is None
HAS_PYLSL = backend_unavailable_reason('lsl') is None


class FastClock:
    """Reloj que corre `speed` veces más rápido: el simulador entrega segundos de señal en décimas."""

    def __init__(self, speed: float = 10.0) -> None:
        self.speed, self.t0 = speed, time.monotonic()

    def __call__(self) -> float:
        return (time.monotonic() - self.t0) * self.speed


def fast_sim(**kw) -> SimulatedEegDevice:
    return SimulatedEegDevice(fs=FS, clock=FastClock(), **kw)


def wait(predicate, timeout=8.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return predicate()


# ================================================================ catálogo
def test_catalog_keys_and_provenance():
    keys = [d.key for d in DEVICES]
    assert len(keys) == len(set(keys))
    by_key = {d.key: d for d in DEVICES}
    for key in ('cyton', 'cyton_daisy', 'ganglion', 'muse_2', 'muse_s', 'unicorn'):
        assert by_key[key].provenance == SENSOR_REAL
        assert by_key[key].source, f'{key} sin fuente de sus pasos de conexión'
    assert by_key['practica'].provenance == SIMULACION
    assert by_key['brainflow_sintetico'].provenance == SIMULACION
    assert by_key['lsl'].provenance == NO_VERIFICABLE
    for d in DEVICES:
        assert d.steps, f'{d.key} sin pasos para el tutorial'
        assert d.connection
        assert set(d.default_channels) <= set(d.channels), d.key


@pytest.mark.skipif(not HAS_BRAINFLOW, reason='BrainFlow no instalado')
def test_catalog_matches_brainflow_descriptors():
    from brainflow.board_shim import BoardIds, BoardShim

    for d in DEVICES:
        if d.backend != 'brainflow':
            continue
        board_id = getattr(BoardIds, d.board).value
        assert BoardShim.get_sampling_rate(board_id) == d.fs, d.key
        assert len(BoardShim.get_eeg_channels(board_id)) == len(d.channels), d.key
        try:
            names = tuple(BoardShim.get_eeg_names(board_id))
        except Exception:
            names = ()
        if names:
            assert names == d.channels, d.key
        else:
            assert d.channels == tuple(f'Canal {i}' for i in range(1, len(d.channels) + 1)), d.key


def test_missing_library_is_reported_not_raised():
    backend_unavailable_reason.cache_clear()
    try:
        with patch('importlib.import_module', side_effect=ImportError('no module')):
            reason = backend_unavailable_reason('brainflow')
            assert 'pip install brainflow' in reason
            assert 'pip install pylsl' in backend_unavailable_reason('lsl')
        assert backend_unavailable_reason('simulador') is None
    finally:
        backend_unavailable_reason.cache_clear()


# ================================================================ BrainFlow
class FakeBrainFlowError(Exception):
    def __init__(self, message, exit_code):
        super().__init__(message)
        self.exit_code = exit_code


def fake_shim(fail_code=None, names=('Fp1', 'Fp2'), rows=(1, 2), fs=250):
    calls = []

    class Board:
        def __init__(self, board_id, params):
            self.params = params
            calls.append(('crear', board_id, dict(vars(params))))

        def prepare_session(self):
            calls.append('prepare')
            if fail_code is not None:
                raise FakeBrainFlowError(f'ERROR:{fail_code}', fail_code)

        def start_stream(self):
            calls.append('start')

        def get_board_data(self):
            data = np.zeros((4, 5))
            data[1], data[2] = 11.0, 22.0
            return data

        def stop_stream(self):
            calls.append('stop')
            raise RuntimeError('ya estaba detenido')       # close() no debe propagarlo

        def release_session(self):
            calls.append('release')

        disable_board_logger = staticmethod(lambda: None)
        get_eeg_channels = staticmethod(lambda board_id: list(rows))
        get_sampling_rate = staticmethod(lambda board_id: fs)

        @staticmethod
        def get_eeg_names(board_id):
            if names is None:
                raise FakeBrainFlowError('sin nombres', 17)
            return list(names)

    ids = types.SimpleNamespace(**{d.board: types.SimpleNamespace(value=i) for i, d in enumerate(DEVICES) if d.board})
    module = types.SimpleNamespace(BoardShim=Board, BoardIds=ids, BrainFlowInputParams=types.SimpleNamespace,
                                   BrainFlowError=FakeBrainFlowError)
    return module, calls


def test_brainflow_requires_the_serial_port_before_touching_brainflow():
    shim, calls = fake_shim()
    with pytest.raises(BackendError, match='puerto serial del dongle'):
        BrainFlowBackend(get_device('cyton'), {'serial_port': '  '}, shim=shim).open()
    assert calls == []


def test_brainflow_open_read_close_with_fake_module():
    shim, calls = fake_shim()
    backend = BrainFlowBackend(get_device('cyton'), {'serial_port': 'COM9', 'mac_address': ''}, shim=shim)
    desc = backend.open()
    assert desc.channels == ('Fp1', 'Fp2') and desc.fs == 250.0
    assert desc.provenance == SENSOR_REAL and desc.detail == 'OpenBCI Cyton (8 canales) en COM9'
    assert calls[0][2] == {'serial_port': 'COM9'}           # los campos vacíos no se mandan
    data = backend.read()
    assert data.shape == (2, 5) and np.all(data[0] == 11.0) and np.all(data[1] == 22.0)
    backend.close()
    backend.close()
    assert calls[-2:] == ['stop', 'release']


def test_brainflow_names_fall_back_when_the_board_has_none():
    shim, _ = fake_shim(names=None, rows=(1, 2, 3, 4))
    desc = BrainFlowBackend(get_device('ganglion'), shim=shim).open()
    assert desc.channels == ('Canal 1', 'Canal 2', 'Canal 3', 'Canal 4')


def test_brainflow_failure_releases_and_explains():
    shim, calls = fake_shim(fail_code=7)
    with pytest.raises(BackendError, match='interruptor esté en PC'):
        BrainFlowBackend(get_device('cyton'), {'serial_port': 'COM9'}, shim=shim).open()
    assert calls[-1] == 'release'


@pytest.mark.parametrize('code,key,params,text', [
    (2, 'cyton', {'serial_port': 'COM4'}, 'No se pudo abrir el puerto COM4'),
    (2, 'muse_2', {}, 'Bluetooth de la computadora'),
    (7, 'muse_s', {}, 'no respondió'),
    (13, 'cyton', {}, 'el puerto serial del dongle'),
    (1, 'cyton', {}, 'otra sesión o por otro programa'),
    (17, 'unicorn', {}, 'emparejado con el dongle'),
    (99, 'ganglion', {}, 'código 99'),
])
def test_brainflow_error_messages(code, key, params, text):
    assert text in explain_brainflow_error(code, get_device(key), params)


@pytest.mark.skipif(not HAS_BRAINFLOW, reason='BrainFlow no instalado')
def test_brainflow_synthetic_board_end_to_end():
    backend = BrainFlowBackend(get_device('brainflow_sintetico'))
    desc = backend.open()
    try:
        assert desc.channels[:3] == ('Fz', 'C3', 'Cz') and desc.provenance == SIMULACION
        time.sleep(0.6)
        data = backend.read()
        assert data.shape[0] == 16 and data.shape[1] > 50
    finally:
        backend.close()


# ================================================================ LSL
def test_unit_scales():
    scales, note = unit_scales(['microvolts', 'millivolts', 'volts', 'µV'])
    assert list(scales) == [1.0, 1e3, 1e6, 1.0] and 'convertidos' in note
    scales, note = unit_scales(['', 'parsecs'])
    assert list(scales) == [1.0, 1.0] and 'se asumen µV' in note and 'parsecs' in note


class _FakeChannel:
    def __init__(self, rows, i=0):
        self.rows, self.i = rows, i

    def empty(self):
        return self.i >= len(self.rows)

    def child_value(self, key):
        return self.rows[self.i].get(key, '')

    def next_sibling(self):
        return _FakeChannel(self.rows, self.i + 1)


class _FakeInfo:
    def __init__(self, rows, srate=250.0, fmt=1, name='flujo', source_id='id-1'):
        self.rows, self.srate, self.fmt, self._name, self._sid = rows, srate, fmt, name, source_id

    def name(self): return self._name
    def type(self): return 'EEG'
    def source_id(self): return self._sid
    def hostname(self): return 'aula'
    def channel_count(self): return len(self.rows)
    def nominal_srate(self): return self.srate
    def channel_format(self): return self.fmt

    def desc(self):
        rows = self.rows
        return types.SimpleNamespace(child=lambda _: types.SimpleNamespace(child=lambda __: _FakeChannel(rows)))


def fake_pylsl(info, chunk):
    class Inlet:
        def __init__(self, i, max_buflen=60, recover=True):
            self.closed = False

        def info(self, timeout=None): return info
        def open_stream(self, timeout=None): pass
        def pull_chunk(self, timeout=0.0, max_samples=0): return chunk, [0.0] * len(chunk)
        def close_stream(self): self.closed = True

    return types.SimpleNamespace(resolve_byprop=lambda prop, value, minimum, timeout: [info],
                                 resolve_streams=lambda wait: [info], StreamInlet=Inlet, cf_string=3)


def test_lsl_keeps_eeg_channels_and_converts_units():
    rows = [{'label': 'O1', 'unit': 'microvolts', 'type': 'EEG'}, {'label': 'O2', 'unit': 'millivolts', 'type': 'EEG'},
            {'label': 'AUX', 'unit': '', 'type': 'AUX'}]
    info = _FakeInfo(rows)
    backend = LslBackend(LslStreamChoice('flujo', 'EEG', 'id-1', 'aula', 3, 250.0), fake_pylsl(info, [[5.0, 0.002, 9.0]] * 4))
    desc = backend.open()
    assert desc.channels == ('O1', 'O2') and desc.provenance == NO_VERIFICABLE
    assert desc.detail == 'flujo LSL «flujo» (tipo EEG) desde aula'
    data = backend.read()
    assert data.shape == (2, 4) and np.allclose(data[0], 5.0) and np.allclose(data[1], 2.0)


def test_lsl_without_labels_names_channels():
    info = _FakeInfo([{}, {}])
    backend = LslBackend(LslStreamChoice('flujo', 'EEG', 'id-1', 'aula', 2, 250.0), fake_pylsl(info, []))
    desc = backend.open()
    assert desc.channels == ('Canal 1', 'Canal 2') and 'se asumen µV' in desc.unit_note
    assert backend.read().shape == (2, 0)


@pytest.mark.parametrize('kwargs,text', [({'srate': 0.0}, 'irregular'), ({'fmt': 3}, 'texto')])
def test_lsl_rejects_streams_that_cannot_be_analyzed(kwargs, text):
    info = _FakeInfo([{'label': 'O1'}], **kwargs)
    with pytest.raises(BackendError, match=text):
        LslBackend(LslStreamChoice('flujo', 'EEG', 'id-1', 'aula', 1, 0.0), fake_pylsl(info, [])).open()


def test_lsl_missing_stream_is_explained():
    module = types.SimpleNamespace(resolve_byprop=lambda *a: [])
    with pytest.raises(BackendError, match='No aparece el flujo LSL'):
        LslBackend(LslStreamChoice('flujo', 'EEG', 'id-1', 'aula', 1, 250.0), module).open()


@pytest.mark.skipif(not HAS_PYLSL, reason='pylsl no disponible')
def test_lsl_real_round_trip_on_this_machine():
    import pylsl

    from hardware.eeg_live import discover_lsl_streams

    info = pylsl.StreamInfo('BIOCORE-prueba-pytest', 'EEG', 2, 250, 'float32', 'biocore-pytest-1')
    channels = info.desc().append_child('channels')
    for label in ('C3', 'C4'):
        ch = channels.append_child('channel')
        ch.append_child_value('label', label)
        ch.append_child_value('unit', 'microvolts')
    outlet = pylsl.StreamOutlet(info)
    found = [c for c in discover_lsl_streams(1.5) if c.name == 'BIOCORE-prueba-pytest']
    if not found:
        pytest.skip('LSL no resuelve flujos en esta máquina (red sin multicast)')
    backend = LslBackend(found[0])
    desc = backend.open()
    try:
        assert desc.channels == ('C3', 'C4')
        for _ in range(5):
            outlet.push_chunk([[1.0, 2.0]] * 20)
            time.sleep(0.05)
        assert wait(lambda: backend.read().shape[1] > 0, 3.0)
    finally:
        backend.close()
        del outlet


# ================================================================ simulador
def test_simulator_reads_follow_the_clock_and_stop_when_unplugged():
    now = [0.0]
    sim = SimulatedEegDevice(fs=FS, clock=lambda: now[0])
    sim.start_session()
    now[0] = 0.1
    assert sim.read().shape == (8, 25)
    now[0] = 0.1 + 1.0 / 500             # media muestra: se guarda para la siguiente lectura
    assert sim.read().shape == (8, 0)
    now[0] += 1.0 / 500
    assert sim.read().shape == (8, 1)
    now[0] += 30.0                       # una lectura muy atrasada no inventa 30 s
    assert sim.read().shape == (8, int(2 * FS))
    sim.unplug()
    now[0] += 1.0
    assert sim.read().shape == (8, 0)


def test_simulator_is_deterministic_and_continuous():
    a, b = SimulatedEegDevice(fs=FS, seed=1), SimulatedEegDevice(fs=FS, seed=1)
    whole = a.generate(500)
    pieces = np.concatenate([b.generate(123), b.generate(377)], axis=1)
    assert np.allclose(whole, pieces)


def _alpha(signal):
    return EegAnalyzer(fs=FS).analyze(prepare(signal[None, :], FS, 60.0)[0]).band_power['alpha']


def test_simulator_alpha_is_posterior_and_reactive_to_eye_closure():
    sim = SimulatedEegDevice(fs=FS, seed=2)
    sim.generate(int(2 * FS))
    opened = sim.generate(int(8 * FS))
    sim.set_eyes_closed(True)
    sim.generate(int(2 * FS))            # la transición de medio segundo ya pasó
    closed = sim.generate(int(8 * FS))
    o1, fp1 = CHANNELS.index('O1'), CHANNELS.index('Fp1')
    assert _alpha(closed[o1]) > 5 * _alpha(opened[o1])
    assert _alpha(closed[o1]) > 10 * _alpha(closed[fp1])


def test_simulator_blink_is_the_lab_pulse_on_frontopolar_electrodes():
    clean, blinked = SimulatedEegDevice(fs=FS, seed=3), SimulatedEegDevice(fs=FS, seed=3)
    clean.generate(100)
    blinked.generate(100)
    blinked.blink()
    diff = blinked.generate(50) - clean.generate(50)
    from src.signals.eeg import EegSignalGenerator
    lab_pulse = EegSignalGenerator(sampling_rate=FS).generate_blink_artifact(0.2, rate=0.5)
    assert np.allclose(diff[CHANNELS.index('Fp1')], lab_pulse[:50])          # el mismo pulso que el generador
    peaks = np.max(np.abs(diff), axis=1)
    assert peaks[0] == pytest.approx(np.max(lab_pulse)) and np.max(lab_pulse) <= BLINK_PEAK_UV
    assert np.allclose(peaks, BLINK_WEIGHTS * peaks[0])
    assert peaks[CHANNELS.index('O1')] == 0.0


def test_simulator_loose_electrode_is_flagged_only_on_that_channel():
    sim = SimulatedEegDevice(fs=FS, seed=4)
    sim.set_loose('O1')
    sim.generate(int(FS))
    raw = sim.generate(int(8 * FS))
    quality = assess_channels(raw, prepare(raw, FS, 60.0), FS, CHANNELS, 60.0)
    assert set(quality['O1'].issues) == {'distinto', 'red'}
    assert all(quality[c].ok for c in CHANNELS if c != 'O1')
    with pytest.raises(ValueError):
        sim.set_loose('Cz')


# ================================================================ calidad
def test_prepare_removes_trend_and_mains():
    t = np.arange(int(10 * FS)) / FS
    raw = np.vstack([500.0 + 30.0 * t + 20 * np.sin(2 * np.pi * 10 * t) + 50 * np.sin(2 * np.pi * 60 * t)])
    out = prepare(raw, FS, 60.0)[0]
    spectrum = np.abs(np.fft.rfft(out * np.hanning(out.size)))
    freqs = np.fft.rfftfreq(out.size, 1 / FS)
    assert abs(out.mean()) < 1.0
    assert spectrum[np.argmin(abs(freqs - 60))] < 0.01 * spectrum[np.argmin(abs(freqs - 10))]
    assert np.allclose(prepare(raw, FS, None)[0], raw[0] - np.polyval(np.polyfit(t, raw[0], 1), t), atol=1e-6)


def test_flat_channel_and_mains_check_off():
    rng = np.random.default_rng(0)
    raw = np.vstack([rng.normal(0, 10, 2500), np.full(2500, 187500.0), rng.normal(0, 10, 2500)])
    quality = assess_channels(raw, prepare(raw, FS, None), FS, ('A', 'B', 'C'), None)
    assert quality['B'].issues == ('plano',) and quality['B'].mains_rms_uv is None
    assert quality['A'].ok and 'contacto' in quality['B'].messages[0]


# ================================================================ servicio
class ScriptedBackend(Backend):
    """Backend de prueba: falla `fail_times` veces al abrir y luego entrega lo que se le pida."""

    opens = 0

    def __init__(self, fail_times=0, channels=('A', 'B'), provenance=SENSOR_REAL, chunk=None):
        self.fail_times, self.channels, self.provenance, self.chunk = fail_times, channels, provenance, chunk

    def open(self):
        ScriptedBackend.opens += 1
        if ScriptedBackend.opens <= self.fail_times:
            raise BackendError('No se encontró el equipo de prueba.')
        return StreamDescription(self.channels, FS, 'equipo de prueba', 'µV', self.provenance)

    def read(self):
        return self.chunk if self.chunk is not None else np.ones((len(self.channels), 10))


QUICK = dict(poll_s=0.01, data_timeout_s=0.3, reconnect_after_s=0.8, retry_s=0.2, rate_window_s=0.5)


def test_service_streams_simulator_and_survives_unplug_and_replug():
    sim = fast_sim()
    service = EegLiveService(get_device('practica'), lambda: SimulatorBackend(sim), LiveConfig(**QUICK)).start()
    try:
        assert service.wait_for(LiveState.STREAMING, 5)
        assert wait(lambda: service.snapshot()['seconds_available'] >= 2.0)
        snap = service.snapshot(seconds=1.0)
        assert snap['provenance'] == SIMULACION and snap['channels'] == CHANNELS
        assert snap['data'].shape == (8, 250)
        sim.unplug()
        assert service.wait_for(LiveState.NO_DATA, 3)
        assert service.snapshot()['provenance'] is None           # un búfer viejo no es señal en vivo
        assert service.wait_for(LiveState.FAILED, 3)
        assert 'Reconectar el cable' in service.snapshot()['message'] or 'no mandó datos' in service.snapshot()['message']
        sim.plug()
        assert service.wait_for(LiveState.STREAMING, 5)
        assert service.snapshot()['connections'] >= 2
    finally:
        service.stop()
    snap = service.snapshot()
    assert snap['state'] == 'detenido' and snap['provenance'] is None and not service.is_running


def test_service_reports_open_failures_and_retries():
    ScriptedBackend.opens = 0
    service = EegLiveService(get_device('cyton'), lambda: ScriptedBackend(fail_times=2), LiveConfig(**QUICK)).start()
    try:
        assert service.wait_for(LiveState.FAILED, 3)
        assert 'No se encontró el equipo de prueba.' in service.snapshot()['warnings']
        assert service.wait_for(LiveState.STREAMING, 5)
        assert ScriptedBackend.opens == 3
        assert service.snapshot()['provenance'] == SENSOR_REAL
    finally:
        service.stop()


def test_service_closes_a_session_with_the_wrong_channel_count():
    ScriptedBackend.opens = 0
    service = EegLiveService(get_device('cyton'), lambda: ScriptedBackend(chunk=np.ones((3, 5))),
                             LiveConfig(**QUICK)).start()
    try:
        assert service.wait_for(LiveState.FAILED, 3)
        assert 'mandó 3 canales y se esperaban 2' in service.snapshot()['message']
    finally:
        service.stop()


def test_service_effective_rate_and_start_is_idempotent():
    sim = fast_sim()
    service = EegLiveService(get_device('practica'), lambda: SimulatorBackend(sim), LiveConfig(**QUICK))
    assert service.start() is service.start()
    try:
        assert service.wait_for(LiveState.STREAMING, 5)
        assert wait(lambda: service.snapshot()['effective_fs'] is not None, 3)
        assert service.snapshot()['effective_fs'] > 5 * FS          # el reloj del simulador corre 10 veces más rápido
    finally:
        service.stop()


def test_ring_buffer_wraps_and_returns_the_latest_samples():
    ring = _Ring(2, 5)
    for start in range(0, 12, 3):
        chunk = np.vstack([np.arange(start, start + 3), -np.arange(start, start + 3)]).astype(float)
        ring.extend(chunk)
    assert ring.total == 12
    assert list(ring.last(5)[0]) == [7, 8, 9, 10, 11] and list(ring.last(2)[1]) == [-10, -11]
    ring.extend(np.arange(20.0).reshape(2, 10))
    assert list(ring.last(5)[0]) == [5, 6, 7, 8, 9]


# ================================================================ montaje
def test_montage_follows_the_ten_twenty_rules():
    assert POSITIONS['Cz'] == (0.0, 0.0)
    assert POSITIONS['T7'] == pytest.approx((-0.8, 0.0))
    assert POSITIONS['Fz'] == pytest.approx((0.0, 0.4))
    assert POSITIONS['Oz'] == pytest.approx((0.0, -0.8))
    for left, right in (('F3', 'F4'), ('C3', 'C4'), ('P3', 'P4'), ('O1', 'O2'), ('TP9', 'TP10'), ('PO7', 'PO8'),
                        ('AF7', 'AF8'), ('F5', 'F6')):
        assert POSITIONS[left][0] == pytest.approx(-POSITIONS[right][0])
        assert POSITIONS[left][1] == pytest.approx(POSITIONS[right][1])
        assert POSITIONS[left][0] < 0           # impares a la izquierda

    def arc(a, b):
        return np.degrees(np.arccos(np.clip(np.dot(SPHERE[a], SPHERE[b]), -1, 1)))

    steps = [arc(a, b) for a, b in (('F7', 'F5'), ('F5', 'F3'), ('F3', 'F1'), ('F1', 'Fz'))]
    assert max(steps) - min(steps) < 1e-9
    for d in DEVICES:
        for name in d.channels:
            assert name in POSITIONS or name.startswith('Canal'), f'{d.key}: {name} sin posición'


# ================================================================ helpers de la página
def test_twin_provenance_and_findings_filter():
    from app.supermodules.eeg_neuro_lab.live_source import (LiveData, save_blocker, twin_provenance,
                                                            visible_findings)
    from domain.physiology.state import Provenance
    from hardware.eeg_live import ChannelQuality

    def live(prov, issues=()):
        q = {'O1': ChannelQuality('O1', 10.0, 1.0, tuple(issues))}
        return LiveData({}, np.array([]), FS, 'x', prov, 'equipo', q)

    assert twin_provenance(None)[0] == Provenance.SIMULACION
    assert twin_provenance(live(SENSOR_REAL))[0] == Provenance.SENSOR_REAL
    assert twin_provenance(live(SIMULACION))[0] == Provenance.SIMULACION
    prov, note = twin_provenance(live(NO_VERIFICABLE))
    assert prov == Provenance.SIMULACION and 'no puede verificar' in note
    assert save_blocker(live(SENSOR_REAL), 'O1') is None
    assert 'problemas de calidad' in save_blocker(live(SENSOR_REAL, ('red',)), 'O1')
    findings = {'Dominant Band': 'DELTA', 'Classification': 'Sueño profundo', 'Clinical Note': 'x', 'Alert': 'y',
                'Delta Power': '1.0'}
    assert visible_findings(findings, True) == findings
    assert visible_findings(findings, False) == {'Dominant Band': 'DELTA', 'Delta Power': '1.0'}


def test_old_fabricating_hardware_path_is_gone():
    page = Path('app/supermodules/eeg_neuro_lab/page_content.py').read_text(encoding='utf-8')
    for ghost in ('expand_hardware_eeg_to_channels', '"Simular si no hay hardware conectado"', 'ESP32SignalSource(',
                  '"Habilitar análisis en tiempo real"', 'señal de respaldo sintética'):
        assert ghost not in page, ghost              # las etiquetas de los widgets retirados, entre comillas


# ================================================================ AppTest
@pytest.fixture
def eeg_ups(tmp_path):
    from domain.physiology.state import create_patient, init_db, make_engine, make_session_factory

    engine = make_engine(Path(str(tmp_path / 'eeg_live_test.db')))
    init_db(engine)
    sf = make_session_factory(engine)
    with sf() as s:
        pid = create_patient(s, display_name='Paciente EEG en vivo (test)')
    return sf, pid


def _page():
    import app.supermodules.eeg_neuro_lab.pages as m
    m.run()


def _apptest(eeg_ups):
    sf, pid = eeg_ups
    at = AppTest.from_function(_page)
    at.session_state['twin_shell_ups_session_factory'] = sf
    at.session_state['twin_shell_ups_patient_id'] = pid
    return at


def _live(at, device_name):
    at.run(timeout=60)
    next(r for r in at.sidebar.radio if r.label == 'Origen de datos').set_value('Hardware EEG en vivo').run(timeout=60)
    next(s for s in at.sidebar.selectbox if s.label == 'Dispositivo EEG').set_value(device_name).run(timeout=60)
    return at


def _click(at, label, where='sidebar'):
    buttons = at.sidebar.button if where == 'sidebar' else at.main.button
    next(b for b in buttons if b.label == label).click().run(timeout=60)


def _texts(elements):
    return ' '.join(e.value for e in elements)


@pytest.fixture
def practice():
    from app.supermodules.eeg_neuro_lab import live_service

    sim = fast_sim()
    prac = live_service.Practice(sim, EegLiveService(get_device('practica'), lambda: SimulatorBackend(sim),
                                                     LiveConfig(**QUICK), key='practica'))
    with patch.object(live_service, 'get_practice', lambda: prac):
        yield prac
    prac.service.stop()


def test_synthetic_source_keeps_its_interpretation(eeg_ups):
    at = _apptest(eeg_ups)
    at.run(timeout=60)
    assert at.exception == []
    assert [t.label for t in at.tabs] == ['Clínica', 'EEG en vivo (tutorial)']
    markdown = _texts(at.main.markdown)
    assert 'Clasificación' in markdown and 'no se traduce a un estado' not in markdown
    assert 'Interpretación:' in markdown                 # el generador sí trae su traducción banda → estado


def test_live_source_without_connection_analyzes_nothing(eeg_ups):
    at = _live(_apptest(eeg_ups), 'OpenBCI Cyton (8 canales)')
    assert at.exception == []
    assert 'no se usa una señal de respaldo' in _texts(at.main.info)
    assert 'No hay datos EEG válidos.' in _texts(at.main.warning)
    assert 'Canal Fp1' not in _texts(at.main.markdown)
    assert 'Puerto del dongle' in [s.label for s in at.sidebar.selectbox]


def test_practice_source_streams_analyzes_and_saves_as_simulation(eeg_ups, practice):
    from domain.physiology.state import Provenance, get_latest_state

    at = _live(_apptest(eeg_ups), 'Simulador de práctica de BIOCORE')
    _click(at, '▶ Conectar')
    assert wait(lambda: practice.service.snapshot()['seconds_available'] >= 5)
    _click(at, '🔄 Leer los últimos segundos')
    assert at.exception == []
    markdown = _texts(at.main.markdown)
    assert '**Fuente de datos:** Simulador de práctica de BIOCORE (SIMULACIÓN)' in markdown
    assert 'Canal Fp1' in markdown and 'no se traduce a un estado' in markdown
    assert 'Interpretación:' not in markdown and 'Banda con más potencia' in markdown
    assert 'PROCEDENCIA: SIMULACIÓN' in _texts(at.sidebar.warning)
    _click(at, '💾 Guardar estado al gemelo', where='main')
    assert 'Estado guardado al gemelo' in _texts(at.main.success)
    sf, pid = eeg_ups
    with sf() as s:
        alpha = get_latest_state(s, pid).neurological.descriptors['alpha_power']
    assert alpha.provenance == Provenance.SIMULACION
    assert 'Simulador de práctica de BIOCORE' in alpha.source_detail


class FakeRealBackend(Backend):
    """Un «Cyton» de prueba: datos del simulador, procedencia de equipo real."""

    def __init__(self, sim, flat=None):
        self.sim, self.flat = sim, flat

    def open(self):
        self.sim.start_session()
        return StreamDescription(CHANNELS, FS, 'OpenBCI Cyton (8 canales) en COM9', 'µV', SENSOR_REAL)

    def read(self):
        data = self.sim.read()
        if self.flat is not None and data.shape[1]:
            data[CHANNELS.index(self.flat)] = 187500.0
        return data


@pytest.fixture
def fake_cyton():
    from app.supermodules.eeg_neuro_lab import live_service, live_source

    state = {'flat': None}
    manager = live_service.LiveManager()

    def connect(device, params=None, lsl_choice=None):
        sim = fast_sim()
        manager.service = EegLiveService(device, lambda: FakeRealBackend(sim, state['flat']), LiveConfig(**QUICK),
                                         key='cyton-prueba').start()
        return manager.service

    manager.connect = connect
    with patch.object(live_service, 'get_manager', lambda: manager), \
            patch.object(live_source, 'backend_unavailable_reason', lambda backend: None):
        yield manager, state
    manager.disconnect()


def _connect_fake_cyton(at, manager):
    next(s for s in at.sidebar.selectbox if s.label == 'Puerto del dongle').set_value('Escribir el puerto…').run(timeout=60)
    next(t for t in at.sidebar.text_input if t.label.startswith('Puerto (COM3')).set_value('COM9').run(timeout=60)
    _click(at, '▶ Conectar')
    assert wait(lambda: manager.service.snapshot()['seconds_available'] >= 5)
    _click(at, '🔄 Leer los últimos segundos')


def test_real_device_is_sensor_real_and_saves_as_sensor_real(eeg_ups, fake_cyton):
    from domain.physiology.state import Provenance, get_latest_state

    manager, _ = fake_cyton
    at = _live(_apptest(eeg_ups), 'OpenBCI Cyton (8 canales)')
    _connect_fake_cyton(at, manager)
    assert at.exception == []
    assert 'PROCEDENCIA: SENSOR_REAL' in _texts(at.sidebar.success)
    _click(at, '💾 Guardar estado al gemelo', where='main')
    sf, pid = eeg_ups
    with sf() as s:
        alpha = get_latest_state(s, pid).neurological.descriptors['alpha_power']
    assert alpha.provenance == Provenance.SENSOR_REAL
    assert 'OpenBCI Cyton (8 canales) en COM9 (SENSOR_REAL)' in alpha.source_detail


def test_a_flat_live_channel_is_not_saved_to_the_twin(eeg_ups, fake_cyton):
    from domain.physiology.state import get_latest_state

    manager, state = fake_cyton
    state['flat'] = 'Fp1'
    at = _live(_apptest(eeg_ups), 'OpenBCI Cyton (8 canales)')
    _connect_fake_cyton(at, manager)
    assert 'Fp1: Señal plana' in _texts(at.sidebar.warning)
    _click(at, '💾 Guardar estado al gemelo', where='main')
    assert 'No se guarda al gemelo: El canal Fp1 tiene problemas de calidad' in _texts(at.main.warning)
    sf, pid = eeg_ups
    with sf() as s:
        assert get_latest_state(s, pid) is None


def test_tutorial_tab_renders_and_runs_the_practice(eeg_ups, practice):
    at = _apptest(eeg_ups)
    at.run(timeout=60)
    labels = [e.label for e in at.expander]
    for title in ('1. Elige tu equipo', '3. Dónde va cada electrodo', '4. Conecta tu equipo',
                  '6. Calidad de la señal', '7. Qué puedes y qué no puedes concluir'):
        assert title in labels
    markdown = _texts(at.main.markdown)
    assert 'GPIO 6' in markdown and 'aria-label="Electrodos de OpenBCI Cyton' in markdown
    _click(at, '▶ Empezar práctica', where='main')
    assert practice.service.is_running
    assert wait(lambda: practice.service.snapshot()['seconds_available'] >= 3)
    at.run(timeout=60)
    assert at.exception == []
    assert any(b.label == '😌 Cerrar los ojos' for b in at.main.button)
    _click(at, '😌 Cerrar los ojos', where='main')
    assert practice.device.eyes_closed
