"""Arco respiratorio, fase 2b (2026-11-07, Art. I): SpO2 fisiológica y patrones fieles en el generador.

Criterios firmados por Luis: la SpO2 es estable sin eventos (basal + ruido); cada apnea anotada produce un
nadir en fin del evento + Tc (Tc = 15 s por defecto, rango 5-30, "Valor BIOCORE"), con profundidad
r·T (r = 0.30 %/s, Howarth 2026), recuperación en rampa a tasa CONSTANTE de 0.70 %/s (Howarth 2026) y
`desaturation_level` como piso. Atáxica: duración y profundidad aleatorias por respiración (HEURISTIC).
Cheyne-Stokes: apnea central de >= 10 s en cada valle, anotada.

E23, E25-E33 (SpO2) + las pruebas de atáxica y Cheyne-Stokes. No toca el detector.
"""

import numpy as np
import pytest
from scipy.ndimage import uniform_filter1d
from scipy.signal import find_peaks

from src.signals.respiration import RespiratoryPattern, RespiratorySignalGenerator
from src.signals.respiration.respiratory_generator import ImpossibleParameters

FS = 100
TC, R_DES, R_RES = 15.0, 0.30, 0.70


class _NullRng:
    def normal(self, loc=0.0, scale=1.0, size=None):
        return np.zeros(size if size is not None else ())


@pytest.fixture
def no_noise(monkeypatch):
    monkeypatch.setattr(np.random, "default_rng", lambda seed=None: _NullRng())


def _gen(pattern, rr=15, duration=150, seed=0, **kw):
    params = RespiratoryPattern(respiratory_rate=rr, pattern_type=pattern, **kw)
    return RespiratorySignalGenerator(FS).generate_respiration(duration=duration, params=params, seed=seed)


# --- E23: estable sin eventos ----------------------------------------------------------------------------------

@pytest.mark.parametrize("rr", [8, 12, 15, 20, 30])
@pytest.mark.parametrize("pattern", ["normal", "tachypnea", "bradypnea"])
def test_e23_spo2_is_stable_during_normal_breathing_at_any_rate(pattern, rr):
    for seed in range(3):
        s = _gen(pattern, rr, 300, seed)["spo2"]
        assert s.min() >= 98 - 2.5          # sin caídas por cruce por cero (el generador anterior llegaba a ~87)
        assert s.mean() == pytest.approx(98.0, abs=0.5)
        assert np.sum(s < 90) == 0 and np.sum(s < 95) == 0
        assert s.std() == pytest.approx(0.5, abs=0.1)  # ruido de oxímetro (valor heredado)


def test_e29_no_desaturation_episodes_without_events():
    for rr in (8, 15, 30):
        s = uniform_filter1d(_gen("normal", rr, 300)["spo2"], 100)  # suavizado de 1 s: el ruido (sd 0.5) cae a 0.05
        assert np.sum((98 - s) >= 3) == 0


# --- E25-E28: cinética del evento (señal sin ruido) --------------------------------------------------------------

def _single_event(T=20.0, **kw):
    d = _gen("apnea_central", 15, 200, apnea_duration=T, apnea_period=120.0, **kw)
    return d["time"], d["spo2"], d["ground_truth"]["events"][0]


def test_e25_nadir_arrives_at_the_end_of_the_event_plus_tc(no_noise):
    t, s, ev = _single_event()
    assert t[int(np.argmin(s))] == pytest.approx(ev["start_s"] + ev["duration_s"] + TC, abs=1.0)  # 40 + 20 + 15 = 75
    assert ev["spo2_nadir_time_s"] == pytest.approx(75.0)


@pytest.mark.parametrize("tc", [5.0, 15.0, 30.0])
def test_circulation_delay_shifts_the_whole_response(no_noise, tc):
    _, s, ev = _single_event(circulation_delay=tc)
    t = np.arange(len(s)) / FS
    assert t[int(np.argmin(s))] == pytest.approx(40.0 + 20.0 + tc, abs=1.0)
    assert ev["spo2_nadir_time_s"] == pytest.approx(60.0 + tc)


def test_e26_spo2_stays_at_baseline_until_the_event_reaches_the_finger(no_noise):
    t, s, _ = _single_event()
    assert np.all(s[t < 40.0 + TC - 0.05] == 98.0)  # sin latencia L: empieza a caer en inicio + Tc
    assert s[int((40.0 + TC + 1.0) * FS)] < 98.0


@pytest.mark.parametrize("T", [10.0, 20.0, 30.0, 45.0])
def test_e27_depth_grows_with_the_duration_of_the_event(no_noise, T):
    _, s, ev = _single_event(T=T, desaturation_level=60.0)  # piso lejos: 98 - 0.30*45 = 84.5 caería bajo el piso por defecto (85)
    assert 98.0 - s.min() == pytest.approx(R_DES * T, abs=0.5)
    assert ev["spo2_depth_points"] == pytest.approx(R_DES * T)
    assert ev["spo2_nadir"] == pytest.approx(98.0 - R_DES * T)


def test_e27_depth_is_monotone_in_duration(no_noise):
    depths = [98.0 - _single_event(T=T, desaturation_level=60.0)[1].min() for T in (10.0, 20.0, 30.0, 45.0)]
    assert depths == sorted(depths) and len(set(depths)) == 4


@pytest.mark.parametrize("T", [12.0, 20.0, 30.0])
def test_e28_recovery_is_a_ramp_at_constant_rate_whose_duration_follows_from_the_depth(no_noise, T):
    t, s, ev = _single_event(T=T)
    depth = ev["spo2_depth_points"]
    i_nadir, i_end = int(round(ev["spo2_nadir_time_s"] * FS)), int(round(ev["spo2_recovered_time_s"] * FS))
    ramp = s[i_nadir:i_end]
    slope = np.polyfit(t[i_nadir:i_end], ramp, 1)[0]  # la SpO2 SUBE a tasa constante
    assert slope == pytest.approx(R_RES, abs=0.05)
    assert ev["spo2_recovered_time_s"] - ev["spo2_nadir_time_s"] == pytest.approx(depth / R_RES, abs=0.01)
    assert s[i_end + 5] == pytest.approx(98.0)


def test_e30_two_events_do_not_accumulate(no_noise):
    d = _gen("apnea_central", 15, 200)
    s, t = d["spo2"], d["time"]
    first, second = s[(t >= 40) & (t < 95)].min(), s[(t >= 100) & (t < 155)].min()
    assert first == pytest.approx(second, abs=0.01)
    assert s[(t >= 90) & (t < 100)].mean() == pytest.approx(98.0, abs=0.01)  # entre eventos vuelve a la basal


def test_e31_desaturation_episodes_match_the_annotated_events_that_are_deep_enough():
    # profundidad >= 3 puntos <=> T >= 3 / 0.30 = 10 s
    for T, expected in ((8.0, 0), (9.0, 0), (12.0, 1), (20.0, 1)):
        d = _gen("apnea_central", 15, 150, apnea_duration=T, apnea_period=120.0)  # un solo evento (el 2.º empezaría en 160 s)
        s = uniform_filter1d(d["spo2"], 100)
        peaks, _ = find_peaks(98 - s, prominence=3.0)  # prominencia: robusta al ruido en el umbral
        assert len(peaks) == expected, T
    d = _gen("apnea_central", 15, 300)
    s = uniform_filter1d(d["spo2"], 100)
    peaks, _ = find_peaks(98 - s, prominence=3.0)
    events = d["ground_truth"]["events"]
    visible = [e for e in events if e["spo2_nadir_time_s"] <= 300.0]  # el 5.º (280 s) llega al dedo en 315 s: fuera del registro
    assert len(events) == 5 and len(peaks) == len(visible) == 4


def test_e32_floor_and_ceiling():
    d = _gen("apnea_central", 15, 200, apnea_duration=30.0, apnea_period=120.0, desaturation_level=94.0)
    s = d["spo2"]
    assert s.min() >= 94.0 and s.max() <= 100.0
    assert d["ground_truth"]["events"][0]["spo2_nadir"] == pytest.approx(94.0)  # 98 - 0.30*30 = 89 -> piso 94
    assert d["ground_truth"]["events"][0]["spo2_depth_points"] == pytest.approx(4.0)
    # techo: con basal 100 el ruido no supera 100
    assert _gen("normal", 15, 60, baseline_spo2=100).get("spo2").max() <= 100.0


def test_spo2_depends_on_the_events_not_on_the_airflow(no_noise):
    a, b = _gen("apnea_central", 15, 200), _gen("apnea_obstructive", 8, 200)
    assert np.array_equal(a["spo2"], b["spo2"])  # mismos eventos => misma SpO2 (la FR y el tipo no la mueven)
    assert np.array_equal(_gen("normal", 8, 120)["spo2"], _gen("tachypnea", 30, 120)["spo2"])


def test_e33_same_seed_same_spo2_bit_for_bit():
    for pattern in ("normal", "apnea_central", "cheyne_stokes", "ataxic"):
        assert np.array_equal(_gen(pattern, 15, 120, 5)["spo2"], _gen(pattern, 15, 120, 5)["spo2"])


@pytest.mark.parametrize("kw", [
    dict(circulation_delay=4.9), dict(circulation_delay=30.1), dict(desaturation_rate=0.0), dict(resaturation_rate=-1.0),
    dict(desaturation_level=98.0), dict(desaturation_level=99.0),
])
def test_impossible_spo2_parameters_name_the_affected_control(kw):
    with pytest.raises(ImpossibleParameters) as exc:
        _gen("apnea_central", 15, 60, **kw)
    assert exc.value.control in ("circulation_delay", "desaturation_rate", "desaturation_level")


def test_the_impossible_parameter_error_carries_the_control_to_highlight():
    with pytest.raises(ImpossibleParameters) as exc:
        _gen("normal", 40, 30, inspiration_time=3.0)
    assert exc.value.control == "inspiration_time" and isinstance(exc.value, ValueError)


# --- unidades de la señal de flujo -----------------------------------------------------------------------------

@pytest.mark.parametrize("rr,vt", [(8, 0.5), (15, 0.5), (30, 0.5), (15, 1.0)])
def test_airflow_is_flow_its_peak_grows_with_the_rate_like_pi_f_vt(no_noise, rr, vt):
    d = _gen("normal", rr, 240, tidal_volume=vt)
    physical_peak = np.pi * (rr / 60) * vt * 60  # L/min de un flujo sinusoidal con ese volumen y frecuencia
    assert d["airflow"].max() / physical_peak == pytest.approx(1 / np.pi, rel=1e-3)  # la escala del generador es constante
    assert "L/min" in d["ground_truth"]["airflow_units"]


def test_the_integrated_inspired_volume_is_not_the_tidal_volume_and_the_scale_is_declared():
    x = _gen("normal", 15, 240)["airflow"]
    n = int(240 // 4.0)
    v_in = x[: n * 4 * FS][x[: n * 4 * FS] > 0].sum() / FS / 60 / n
    assert v_in == pytest.approx(0.08, abs=0.005) and abs(v_in - 0.5) > 0.3  # por eso se rotula "escala del generador"


# --- Atáxica ---------------------------------------------------------------------------------------------------

def _peak_intervals(x):
    s = uniform_filter1d(x, int(0.25 * FS))
    pk, _ = find_peaks(s, prominence=0.3 * np.percentile(np.abs(s), 95), distance=int(1.0 * FS))
    return np.diff(pk / FS)


@pytest.mark.parametrize("seed", range(5))
def test_ataxic_breaths_have_their_own_duration_and_depth(seed):
    d = _gen("ataxic", 15, 300, seed)
    gt = d["ground_truth"]
    assert gt["rate_is_regular"] is False and gt["irregularity"] == 0.20 and gt["irregularity_label"] == "HEURISTIC"
    assert gt["cycle_cv"] > 0.12                                   # anotado (el CV pedido es 0.20)
    iv = _peak_intervals(d["airflow"])
    assert iv.std(ddof=1) / iv.mean() > 0.12                       # medido sobre el flujo crudo
    assert 60.0 / iv.mean() == pytest.approx(gt["effective_respiratory_rate"], abs=0.5)
    onsets = np.array(gt["breath_onsets_s"])
    assert onsets[0] == 0.0 and np.all(np.diff(onsets) >= 1.2) and onsets[-1] < 300.0
    assert gt["effective_respiratory_rate"] == pytest.approx(60.0 / np.mean(np.diff(onsets)))


def test_ataxic_depth_varies_breath_to_breath_and_the_frequency_is_not_a_fixed_carrier():
    d = _gen("ataxic", 15, 300, 0)
    s = uniform_filter1d(d["airflow"], int(0.25 * FS))
    pk, _ = find_peaks(s, prominence=0.3 * np.percentile(np.abs(s), 95), distance=FS)
    amps = s[pk]
    assert amps.std() / amps.mean() > 0.12
    f = np.fft.rfftfreq(len(d["airflow"]), 1 / FS) * 60
    spec = np.abs(np.fft.rfft(d["airflow"] - d["airflow"].mean()))
    top = f[np.argsort(spec)[-5:]]
    assert not (np.abs(spec[(f > 14.9) & (f < 15.1)].max() > 0.9 * spec.max()) and np.ptp(top) < 0.3)  # ya no hay pico único


def test_ataxic_irregularity_zero_is_regular_and_validated():
    gt = _gen("ataxic", 15, 120, irregularity=0.0)["ground_truth"]
    assert gt["rate_is_regular"] is True and gt["cycle_cv"] == pytest.approx(0.0, abs=1e-9)
    with pytest.raises(ImpossibleParameters):
        _gen("ataxic", 15, 60, irregularity=1.5)


# --- Cheyne-Stokes ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("rr", [8, 15, 30])
def test_cheyne_stokes_has_a_central_apnea_of_at_least_10_s_in_every_valley(rr):
    d = _gen("cheyne_stokes", rr, 300)
    gt = d["ground_truth"]
    assert [(e["start_s"], e["duration_s"], e["type"]) for e in gt["events"]] == [
        (40.0, 20.0, "central"), (100.0, 20.0, "central"), (160.0, 20.0, "central"), (220.0, 20.0, "central"),
        (280.0, 20.0, "central")]
    assert all(e["duration_s"] >= 10.0 for e in gt["events"])
    x, c, t = d["airflow"], d["chest_wall"], d["time"]
    for e in gt["events"]:
        w = (t >= e["start_s"]) & (t < e["start_s"] + e["duration_s"])
        assert np.abs(uniform_filter1d(x, 25)[w]).max() < 0.15           # flujo ausente
        assert np.abs(uniform_filter1d(c, 25)[w]).max() < 0.05           # esfuerzo ausente (apnea CENTRAL)
    assert gt["modulation_period_s"] == 60.0


def test_cheyne_stokes_waxes_and_wanes_between_the_apneas(no_noise):
    d = _gen("cheyne_stokes", 15, 120)
    x, t = d["airflow"], d["time"]
    first, mid, last = (np.abs(x[(t >= a) & (t < b)]).max() for a, b in ((0, 5), (17, 23), (35, 40)))
    assert mid > 3 * first and mid > 3 * last      # crescendo-decrescendo, no una amplitud constante


def test_cheyne_stokes_desaturates_after_each_valley(no_noise):
    d = _gen("cheyne_stokes", 15, 150)
    ev = d["ground_truth"]["events"][0]
    assert d["spo2"].min() == pytest.approx(98.0 - R_DES * 20.0)
    assert d["time"][int(np.argmin(d["spo2"]))] == pytest.approx(ev["start_s"] + 20.0 + TC, abs=0.2)


@pytest.mark.parametrize("kw", [dict(apnea_duration=8.0), dict(cheyne_stokes_cycle=20.0), dict(cheyne_stokes_cycle=15.0, apnea_duration=15.0)])
def test_cheyne_stokes_rejects_valleys_that_are_not_valid_apneas(kw):
    with pytest.raises(ImpossibleParameters):
        _gen("cheyne_stokes", 15, 60, **kw)
