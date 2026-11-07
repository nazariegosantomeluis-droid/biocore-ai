"""Arco respiratorio, fase 2a (2026-11-07, Art. I): el generador respiratorio como ground truth.

Fija cuatro cosas:
1. Con los parámetros por defecto el generador sigue produciendo lo de siempre (huellas congeladas
   de la versión anterior: FR efectiva por patrón y ventanas de evento no cambian).
2. `generate_respiration()` devuelve `'ground_truth'` con lo que la señal REALMENTE contiene (E21),
   y esa FR coincide con la medida de forma independiente sobre el flujo crudo.
3. La misma semilla produce la misma señal bit a bit y el generador no toca el estado global de
   numpy (E22).
4. `apnea_duration`, `apnea_onset`, `apnea_period` y `expiration_time` mueven la señal de verdad, y los
   parámetros imposibles fallan con un error explícito en vez de dibujar una señal sin espiración.

No toca el detector (respiratory_analyzer.py) ni la fórmula de la SpO2 (fase 2b).
"""

import warnings

import numpy as np
import pytest
from scipy.ndimage import uniform_filter1d

from src.signals.respiration import RespiratoryPattern, RespiratorySignalGenerator

FS = 100
PATTERNS = ("normal", "tachypnea", "bradypnea", "apnea_central", "apnea_obstructive", "cheyne_stokes", "ataxic")


class _NullRng:
    """Mismo contrato que `Generator.normal`, sin ruido: aísla la parte determinista de la señal."""

    def normal(self, loc=0.0, scale=1.0, size=None):
        return np.zeros(size if size is not None else ())


@pytest.fixture
def no_noise(monkeypatch):
    monkeypatch.setattr(np.random, "default_rng", lambda seed=None: _NullRng())


def _gen(pattern, rr=15, duration=120, seed=0, **kw):
    params = RespiratoryPattern(respiratory_rate=rr, pattern_type=pattern, **kw)
    return RespiratorySignalGenerator(FS).generate_respiration(duration=duration, params=params, seed=seed)


def _fr_spectrum(x, lo=3.0, hi=60.0):
    """FR (resp/min) como pico espectral con interpolación parabólica: medida independiente de la anotación."""
    x = x - x.mean()
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    f = np.fft.rfftfreq(len(x), 1 / FS) * 60
    i = int(np.argmax(np.where((f >= lo) & (f <= hi), spec, 0)))
    a, b, c = spec[i - 1], spec[i], spec[i + 1]
    d = 0.5 * (a - c) / (a - 2 * b + c) if (a - 2 * b + c) != 0 else 0.0
    return f[i] + d * (f[1] - f[0])


def _fr_crossings(x):
    """FR por cruces ascendentes por cero del flujo suavizado, solo donde hay respiración (no ruido de apnea)."""
    s = uniform_filter1d(x, int(0.25 * FS))
    env = uniform_filter1d(np.abs(s), int(3 * FS))
    gate = env > 0.3 * np.percentile(env, 95)
    up = np.where((s[:-1] < 0) & (s[1:] >= 0) & gate[1:])[0]
    return 60.0 / np.median(np.diff(up / FS))


def _quiet_segments(x, min_s=5.0):
    """Tramos contiguos de flujo ~0 (suavizado) de al menos min_s: [(inicio_s, duracion_s)]."""
    quiet = np.abs(uniform_filter1d(x, int(0.25 * FS))) < 0.15
    segs, i, n = [], 0, len(quiet)
    while i < n:
        if quiet[i]:
            j = i
            while j + 1 < n and quiet[j + 1]:
                j += 1
            if (j - i + 1) / FS >= min_s:
                segs.append((i / FS, (j - i + 1) / FS))
            i = j + 1
        else:
            i += 1
    return segs


def _expected_fr(pattern, rr):
    if pattern == "tachypnea":
        return min(rr * 1.5, 40)
    if pattern == "bradypnea":
        return max(rr * 0.5, 6)
    return float(rr)


# --- Huellas de la versión anterior (señales SIN ruido; congeladas antes de editar el generador) -----------
LEGACY_FINGERPRINTS = [
    ('normal', {'rr': 8, 'dur': 300}, {'airflow': (43289.242306, 84000.0, 4.0, -2.0), 'chest_wall': (9549.240735, 3750.0, 0.499995614, -0.499995614), 'spo2': (2691011.989161, 241441640.08055, 95.637019247, 87.413170702)}),
    ('normal', {'rr': 15, 'dur': 300}, {'airflow': (89521.219323, 369140.625, 7.5, -3.75), 'chest_wall': (9549.100235, 3750.0, 0.5, -0.5), 'spo2': (2705474.951722, 244007518.446458, 95.637019247, 89.049435665)}),
    ('normal', {'rr': 30, 'dur': 300}, {'airflow': (214841.501425, 2109375.0, 15.0, -7.5), 'chest_wall': (9548.511174, 3750.0, 0.5, -0.5), 'spo2': (2736463.246929, 249626796.504211, 95.637019247, 90.058052897)}),
    ('tachypnea', {'rr': 8, 'dur': 300}, {'airflow': (37812.826719, 63180.0, 3.6, -1.8), 'chest_wall': (5729.502553, 1350.0, 0.3, -0.3), 'spo2': (2686869.519761, 240674113.594381, 94.603654165, 88.396539861)}),
    ('tachypnea', {'rr': 15, 'dur': 300}, {'airflow': (76565.873472, 267259.71806, 6.75, -3.375), 'chest_wall': (5729.548499, 1350.0, 0.3, -0.3), 'spo2': (2697720.142829, 242591555.072001, 94.726151204, 89.721332069)}),
    ('tachypnea', {'rr': 20, 'dur': 300}, {'airflow': (107413.092278, 531562.5, 9.0, -4.5), 'chest_wall': (5729.106705, 1350.0, 0.3, -0.3), 'spo2': (2705437.017844, 243980683.261534, 94.821182612, 89.96942343)}),
    ('bradypnea', {'rr': 15, 'dur': 300}, {'airflow': (63846.397223, 186009.403668, 5.625, -2.8125), 'chest_wall': (14323.871247, 8437.5, 0.75, -0.75), 'spo2': (2697813.954103, 242698819.367104, 95.278439191, 87.262924576)}),
    ('bradypnea', {'rr': 30, 'dur': 300}, {'airflow': (147711.852717, 1008544.921875, 11.25, -5.625), 'chest_wall': (14323.650353, 8437.5, 0.75, -0.75), 'spo2': (2721012.804409, 246862427.408225, 95.278439191, 89.119655198)}),
    ('apnea_central', {'rr': 8, 'dur': 300}, {'airflow': (28848.581977, 56972.164125, 4.0, -2.0), 'chest_wall': (6415.679612, 2532.209922, 0.499995614, -0.499995614), 'spo2': (2644095.466749, 233221570.867481, 95.637019247, 85.0)}),
    ('apnea_central', {'rr': 12, 'dur': 300}, {'airflow': (45835.209873, 144000.0, 6.0, -3.0), 'chest_wall': (6366.113948, 2500.0, 0.5, -0.5), 'spo2': (2649647.196714, 234204798.220893, 95.637019247, 85.0)}),
    ('apnea_central', {'rr': 30, 'dur': 300}, {'airflow': (143227.667616, 1406250.0, 15.0, -7.5), 'chest_wall': (6365.674116, 2500.0, 0.5, -0.5), 'spo2': (2674468.22059, 238688587.363542, 95.637019247, 85.0)}),
    ('apnea_obstructive', {'rr': 8, 'dur': 300}, {'airflow': (28848.581977, 56972.164125, 4.0, -2.0), 'chest_wall': (9549.240735, 3750.0, 0.499995614, -0.499995614), 'spo2': (2644095.466749, 233221570.867481, 95.637019247, 85.0)}),
    ('apnea_obstructive', {'rr': 30, 'dur': 300}, {'airflow': (143227.667616, 1406250.0, 15.0, -7.5), 'chest_wall': (9548.511174, 3750.0, 0.5, -0.5), 'spo2': (2674468.22059, 238688587.363542, 95.637019247, 85.0)}),
    ('cheyne_stokes', {'rr': 12, 'dur': 300}, {'airflow': (34376.407405, 72076.652392, 5.9, -2.802884989), 'chest_wall': (4774.585461, 1248.680714, 0.479348569, -0.479348569), 'spo2': (2626212.506161, 229973702.375418, 91.597973081, 85.064789617)}),
    ('cheyne_stokes', {'rr': 30, 'dur': 300}, {'airflow': (107420.750712, 703006.26423, 14.75, -7.375), 'chest_wall': (4774.255587, 1249.788914, 0.491666667, -0.491666667), 'spo2': (2645143.307907, 233330739.175529, 92.264405664, 85.080453663)}),
    ('normal', {'rr': 15, 'dur': 120, 'tv': 0.1}, {'airflow': (7161.697546, 5906.25, 1.5, -0.75), 'chest_wall': (763.928019, 60.0, 0.1, -0.1), 'spo2': (1082372.883627, 97636637.392318, 95.637019247, 89.049435665)}),
    ('normal', {'rr': 15, 'dur': 120, 'tv': 1.5}, {'airflow': (107425.463187, 1328906.25, 22.5, -11.25), 'chest_wall': (11458.920282, 13500.0, 1.5, -1.5), 'spo2': (1082372.883627, 97636637.392318, 95.637019247, 89.049435665)}),
    ('tachypnea', {'rr': 40, 'dur': 120}, {'airflow': (61102.931074, 432000.0, 12.0, -6.0), 'chest_wall': (2291.496068, 540.0, 0.299934205, -0.299934205), 'spo2': (1086465.015817, 98368046.45023, 94.946973138, 90.377208268)}),
    ('cheyne_stokes', {'rr': 15, 'dur': 180, 'cs': 30.0}, {'airflow': (26856.365797, 73799.635446, 7.251420095, -3.632817291), 'chest_wall': (2868.20966, 752.026757, 0.5, -0.5), 'spo2': (1578612.460357, 138491670.881204, 91.681613171, 85.099734327)}),
    ('apnea_central', {'rr': 15, 'dur': 120, 'b': 95, 'd': 70}, {'airflow': (23872.325153, 98437.5, 7.5, -3.75), 'chest_wall': (2546.426729, 1000.0, 0.5, -0.5), 'spo2': (920223.600488, 70851157.964475, 90.455806245, 70.0)}),
    ('apnea_obstructive', {'rr': 20, 'dur': 100, 'tv': 0.3}, {'airflow': (20625.39676, 73800.0, 6.0, -3.0), 'chest_wall': (1912.046836, 450.896481, 0.3, -0.3), 'spo2': (894885.342379, 80135911.796737, 95.667353345, 85.0)}),
    ('apnea_central', {'rr': 15, 'dur': 110}, {'airflow': (23872.325153, 98437.5, 7.5, -3.75), 'chest_wall': (2546.426729, 1000.0, 0.5, -0.5), 'spo2': (976716.272254, 86788454.776646, 95.637019247, 85.0)}),
    ('apnea_central', {'rr': 15, 'dur': 45}, {'airflow': (11936.162576, 49218.75, 7.5, -3.75), 'chest_wall': (1273.213365, 500.0, 0.5, -0.5), 'spo2': (403526.923788, 36199985.822981, 95.637019247, 85.0)}),
]

_SPEC_KEYS = {"rr": "respiratory_rate", "tv": "tidal_volume", "insp": "inspiration_time", "b": "baseline_spo2",
              "d": "desaturation_level", "cs": "cheyne_stokes_cycle"}


@pytest.mark.parametrize("pattern,spec,fingerprint", LEGACY_FINGERPRINTS)
def test_default_parameters_reproduce_the_legacy_signal(no_noise, pattern, spec, fingerprint):
    kwargs = {_SPEC_KEYS[k]: v for k, v in spec.items() if k in _SPEC_KEYS}
    params = RespiratoryPattern(pattern_type=pattern, **kwargs)
    d = RespiratorySignalGenerator(FS).generate_respiration(duration=spec["dur"], params=params)
    for key, (s_abs, s_sq, mx, mn) in fingerprint.items():
        x = d[key]
        assert np.sum(np.abs(x)) == pytest.approx(s_abs, rel=1e-8, abs=1e-5), (pattern, spec, key)
        assert np.sum(x ** 2) == pytest.approx(s_sq, rel=1e-8, abs=1e-5), (pattern, spec, key)
        assert x.max() == pytest.approx(mx, rel=1e-8, abs=1e-8), (pattern, spec, key)
        assert x.min() == pytest.approx(mn, rel=1e-8, abs=1e-8), (pattern, spec, key)


def test_dataclass_defaults_keep_the_historical_behavior():
    p = RespiratoryPattern()
    assert p.expiration_time is None  # la espiración ocupa el resto del ciclo
    assert (p.apnea_onset, p.apnea_period, p.apnea_duration) == (40.0, 60.0, 20.0)


# --- E21: ground truth de eventos y FR efectiva ---------------------------------------------------------------

@pytest.mark.parametrize("pattern,kind", [("apnea_central", "central"), ("apnea_obstructive", "obstructive")])
@pytest.mark.parametrize("duration,expected", [
    (60, [(40.0, 20.0)]),
    (120, [(40.0, 20.0), (100.0, 20.0)]),
    (300, [(40.0, 20.0), (100.0, 20.0), (160.0, 20.0), (220.0, 20.0), (280.0, 20.0)]),
])
def test_e21_apnea_annotations_are_the_events_of_each_minute(pattern, kind, duration, expected):
    gt = _gen(pattern, 15, duration)["ground_truth"]
    assert [(e["start_s"], e["duration_s"]) for e in gt["events"]] == expected
    assert {e["type"] for e in gt["events"]} == {kind}
    assert not any(e["truncated"] for e in gt["events"])


@pytest.mark.parametrize("pattern", ["apnea_central", "apnea_obstructive"])
@pytest.mark.parametrize("rr", [8, 15, 30])
def test_e21_annotated_events_match_the_silences_in_the_raw_flow(pattern, rr):
    d = _gen(pattern, rr, 300)
    measured = _quiet_segments(d["airflow"], min_s=5.0)
    truth = [(e["start_s"], e["duration_s"]) for e in d["ground_truth"]["events"]]
    assert len(measured) == len(truth)
    for (ms, md), (ts, td) in zip(measured, truth):
        assert ms == pytest.approx(ts, abs=0.5) and md == pytest.approx(td, abs=0.5)


@pytest.mark.parametrize("pattern", ["normal", "tachypnea", "bradypnea", "cheyne_stokes", "ataxic"])
def test_patterns_without_apnea_annotate_no_events(pattern):
    assert _gen(pattern, 15, 300)["ground_truth"]["events"] == []


@pytest.mark.parametrize("pattern", PATTERNS)
@pytest.mark.parametrize("rr", [8, 12, 15, 20, 30])
def test_annotated_effective_rate_is_what_the_raw_flow_contains(pattern, rr):
    d = _gen(pattern, rr, 300)
    gt = d["ground_truth"]
    assert gt["effective_respiratory_rate"] == pytest.approx(_expected_fr(pattern, rr))
    assert gt["requested_respiratory_rate"] == rr
    assert _fr_spectrum(d["airflow"]) == pytest.approx(gt["effective_respiratory_rate"], abs=0.5)
    if pattern != "ataxic":  # segundo método, independiente del primero
        assert _fr_crossings(d["airflow"]) == pytest.approx(gt["effective_respiratory_rate"], abs=0.5)


def test_ground_truth_flags_what_it_does_not_claim():
    gt = _gen("cheyne_stokes", 15, 120, cheyne_stokes_cycle=45.0)["ground_truth"]
    assert gt["modulation_period_s"] == 45.0 and gt["events"] == []
    assert gt["spo2"]["is_ground_truth"] is False and gt["spo2"]["recovery_time_applied"] is False
    assert _gen("normal", 15, 60)["ground_truth"]["modulation_period_s"] is None
    atax = _gen("ataxic", 15, 120)["ground_truth"]
    assert atax["pattern"] == "ataxic" and atax["rate_is_regular"] is True
    assert _gen("no_existe", 15, 60)["ground_truth"]["pattern"] == "normal"  # el generador cae a 'normal'


def test_event_truncated_by_the_end_of_the_record_is_declared():
    events = _gen("apnea_central", 15, 110)["ground_truth"]["events"]
    assert [(e["start_s"], e["duration_s"], e["truncated"]) for e in events] == [(40.0, 20.0, False), (100.0, 10.0, True)]
    short = _gen("apnea_central", 15, 45)["ground_truth"]["events"]
    assert [(e["start_s"], e["duration_s"], e["truncated"]) for e in short] == [(40.0, 5.0, True)]


# --- E22: reproducibilidad --------------------------------------------------------------------------------------

@pytest.mark.parametrize("pattern", PATTERNS)
def test_e22_same_seed_same_signal_bit_for_bit(pattern):
    a, b = _gen(pattern, 15, 60, seed=7), _gen(pattern, 15, 60, seed=7)
    for key in ("airflow", "chest_wall", "abdomen", "spo2", "time"):
        assert np.array_equal(a[key], b[key]), (pattern, key)
    assert not np.array_equal(a["airflow"], _gen(pattern, 15, 60, seed=8)["airflow"])


def test_generator_does_not_consume_the_global_numpy_state():
    np.random.seed(123)
    expected = np.random.rand(3)
    np.random.seed(123)
    _gen("ataxic", 15, 30, seed=1)
    _gen("apnea_central", 15, 30, seed=None)
    assert np.array_equal(np.random.rand(3), expected)


# --- parametros que ahora tienen efecto real --------------------------------------------------------------------

@pytest.mark.parametrize("pattern", ["apnea_central", "apnea_obstructive"])
def test_apnea_duration_changes_the_event(pattern):
    d = _gen(pattern, 15, 120, apnea_duration=12.0)
    assert [(e["start_s"], e["duration_s"]) for e in d["ground_truth"]["events"]] == [(40.0, 12.0), (100.0, 12.0)]
    measured = _quiet_segments(d["airflow"], min_s=5.0)
    assert len(measured) == 2
    for (ms, md), start in zip(measured, (40.0, 100.0)):
        assert ms == pytest.approx(start, abs=0.5) and md == pytest.approx(12.0, abs=0.5)
    # y la señal es otra que con el valor por defecto (20 s)
    assert not np.array_equal(d["airflow"], _gen(pattern, 15, 120)["airflow"])


def test_apnea_calendar_can_be_moved():
    d = _gen("apnea_central", 15, 100, apnea_onset=10.0, apnea_period=30.0, apnea_duration=8.0)
    assert [(e["start_s"], e["duration_s"]) for e in d["ground_truth"]["events"]] == [
        (10.0, 8.0), (40.0, 8.0), (70.0, 8.0)]
    assert len(_quiet_segments(d["airflow"], min_s=5.0)) == 3


def _negative_lobe_seconds(x, rr):
    """Duración media del lóbulo espiratorio (flujo < 0) por ciclo, sobre la señal sin ruido."""
    cyc = 60.0 / rr
    n_cycles = int(len(x) / FS // cyc)
    return float(np.sum(x[: int(n_cycles * cyc * FS)] < 0) / FS / n_cycles)


@pytest.mark.parametrize("exp,expected", [(None, 3.0), (2.0, 2.0), (1.0, 1.0), (0.5, 0.5)])
@pytest.mark.parametrize("pattern", ["normal", "apnea_central"])
def test_expiration_time_sets_the_measured_expiratory_phase(no_noise, pattern, exp, expected):
    duration = 40 if pattern == "apnea_central" else 120  # solo respiración, sin entrar en el evento (desde 40 s)
    d = _gen(pattern, 15, duration, expiration_time=exp)
    # ciclo de 4 s, inspiración de 1 s: la espiración sin acotar dura 3 s
    assert _negative_lobe_seconds(d["airflow"], 15) == pytest.approx(expected, abs=0.03)


def test_expiration_time_changes_the_signal_and_leaves_a_pause():
    base = _gen("normal", 15, 60)["airflow"]
    short = _gen("normal", 15, 60, expiration_time=1.0)["airflow"]
    assert not np.allclose(base, short)
    # ciclo 4 s = 1 s inspiración + 1 s espiración + 2 s de pausa: ~50 % del tiempo con flujo casi nulo
    assert np.mean(np.abs(uniform_filter1d(short, 5)) < 0.15) > 0.45


def test_tachypnea_and_bradypnea_scale_expiration_with_the_rest():
    d = _gen("tachypnea", 15, 60, expiration_time=0.6)  # efectivo: FR 22.5 (ciclo 2.67 s), insp 0.5, esp 0.3
    assert d["ground_truth"]["effective_respiratory_rate"] == pytest.approx(22.5)
    assert np.isfinite(d["airflow"]).all()


# --- parametros imposibles: error explicito, nunca una senal sin espiracion --------------------------------------

@pytest.mark.parametrize("kw", [
    dict(pattern_type="normal", respiratory_rate=40, inspiration_time=3.0),
    dict(pattern_type="normal", respiratory_rate=25, inspiration_time=2.4),  # ciclo 2.4 s: no queda espiración
    dict(pattern_type="normal", respiratory_rate=40, inspiration_time=1.0, expiration_time=1.0),
    dict(pattern_type="tachypnea", respiratory_rate=40, inspiration_time=3.0),  # efectivo: insp 1.5 s en ciclo 1.5 s
    dict(pattern_type="apnea_central", respiratory_rate=15, apnea_duration=25.0),  # 40 + 25 > 60
    dict(pattern_type="normal", respiratory_rate=15, expiration_time=-1.0),
])
def test_impossible_parameters_fail_loudly(kw):
    with pytest.raises(ValueError):
        RespiratorySignalGenerator(FS).generate_respiration(duration=30, params=RespiratoryPattern(**kw))


def test_the_old_silent_failure_is_gone_and_valid_extremes_still_work():
    # FR 40 con inspiración 3.0 s producía en silencio una señal sin ningún flujo espiratorio
    with pytest.raises(ValueError, match="no cabe en el ciclo"):
        _gen("normal", 40, 30, inspiration_time=3.0)
    d = _gen("normal", 40, 30, inspiration_time=1.0)  # ciclo 1.5 s, inspiración 1.0 s: válido
    assert (d["airflow"] < -0.5).any()


def test_recovery_time_is_declared_inert_instead_of_silently_ignored():
    with pytest.warns(UserWarning, match="recovery_time no tiene efecto"):
        _gen("apnea_central", 15, 60, recovery_time=60.0)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        _gen("apnea_central", 15, 60)  # el valor por defecto no avisa
