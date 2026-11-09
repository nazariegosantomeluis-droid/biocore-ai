"""Arco respiratorio, fase 3 (2026-11-07, Art. I): golden tests del detector reparado (E1-E20 y E24).

Las entradas son sintéticas con verdad exacta, construidas con numpy y SIN el generador (salvo las pruebas
de integración, que comparan el detector con el ground truth del generador). Las tolerancias salen de la
fase 1. Criterios firmados por Luis (D1, D2, D4, D5, E11); todo umbral técnico fuera de ellos es HEURISTIC y
está declarado en `HEURISTICS` del analizador.
"""

import numpy as np
import pytest

from clinical.calculators import _news2_rr
from src.signals.respiration import RespiratoryAnalyzer, RespiratoryPattern, RespiratorySignalGenerator
from src.signals.respiration.respiratory_analyzer import HEURISTICS, round_half_up

FS = 100


# --------------------------------------------------------------------------------------- entradas sintéticas
def tidal(rr, dur=120.0, tv=0.5, insp=1.0, noise=0.02, seed=0, gaps=(), drops=(), effort_gaps=None, effort_noise=0.01):
    """Respiración tidal (inspiración seno positivo, espiración -0.5 seno) con silencios exactos en `gaps`
    [(inicio, duración)], caídas parciales `drops` [(inicio, duración, fracción)] y canal de esfuerzo
    (por defecto el esfuerzo sigue a la respiración y se apaga en los `gaps`; `effort_gaps` lo sobreescribe)."""
    rng = np.random.default_rng(seed)
    t = np.arange(int(dur * FS)) / FS
    cyc = 60.0 / rr
    ph = np.mod(t / cyc, 1.0)
    fi = insp / cyc
    x = np.where(ph < fi, np.sin(np.pi * ph / fi), -0.5 * np.sin(np.pi * (ph - fi) / (1 - fi))) * tv * rr
    chest = np.sin(2 * np.pi * t / cyc) * tv
    for s, d in gaps:
        w = (t >= s) & (t < s + d)
        x[w] = 0.0
        chest[w] = 0.0
    for s, d, f in drops:
        w = (t >= s) & (t < s + d)
        x[w] *= (1 - f)
        chest[w] *= (1 - f)
    if effort_gaps is not None:
        chest = np.sin(2 * np.pi * t / cyc) * tv
        for s, d in effort_gaps:
            chest[(t >= s) & (t < s + d)] = 0.0
    return t, x + rng.normal(0, noise, len(t)), chest + rng.normal(0, effort_noise, len(t))


def alternating(dur=120.0, noise=0.02, seed=0):
    """Ciclos alternados de 3 s y 5 s (media 4 s = 15/min, desviación 1 s)."""
    rng = np.random.default_rng(seed)
    t = np.arange(int(dur * FS)) / FS
    x = np.zeros_like(t)
    cur, k = 0.0, 0
    while cur < dur:
        c = 3.0 if k % 2 == 0 else 5.0
        m = (t >= cur) & (t < cur + c)
        x[m] = np.sin(2 * np.pi * (t[m] - cur) / c) * 3.0
        cur += c
        k += 1
    return t, x + rng.normal(0, noise, len(t))


def n_breaths(n, rr=15, noise=0.02, seed=0):
    """Exactamente n inspiraciones (n cestas) separadas por el ciclo; sin respiraciones alrededor."""
    t, x, c = tidal(rr, dur=(n + 1) * 60.0 / rr, noise=noise, seed=seed)
    cyc = 60.0 / rr
    keep = t < n * cyc
    x = np.where(keep, x, 0.0)
    return t, x + 0.0, c


def run(t, x, chest=None, spo2=None):
    spo2 = np.full_like(x, 98.0) if spo2 is None else spo2
    return RespiratoryAnalyzer(FS).analyze_respiration(airflow=x, time=t, spo2=spo2, respiratory_effort=chest)


def gen_run(pattern, rr=15, dur=300, seed=0, **kw):
    d = RespiratorySignalGenerator(FS).generate_respiration(
        duration=dur, params=RespiratoryPattern(respiratory_rate=rr, pattern_type=pattern, **kw), seed=seed)
    return d, RespiratoryAnalyzer(FS).analyze_respiration(
        airflow=d["airflow"], time=d["time"], spo2=d["spo2"], respiratory_effort=d["chest_wall"])


# --------------------------------------------------------------------------------------------------- D1 / E1-E4
NEWS2_POINTS = {6: 3, 8: 3, 9: 1, 11: 1, 12: 0, 15: 0, 20: 0, 21: 2, 24: 2, 25: 3, 30: 3, 40: 3}


@pytest.mark.parametrize("rr", sorted(NEWS2_POINTS))
def test_e1_respiratory_rate_from_the_time_between_inspirations_and_its_news2_band(rr):
    t, x, _ = tidal(rr, 120.0)
    a = run(t, x)
    assert a.respiratory_rate == pytest.approx(rr, abs=0.5)      # prototipo: error <= 0.03
    assert a.respiratory_rate_rounded == rr
    assert a.respiratory_rate != 60.0 or rr == 60                # el bug histórico
    assert _news2_rr(a.respiratory_rate_rounded) == NEWS2_POINTS[rr]


def test_e2_the_rate_is_the_mean_of_the_intervals_not_their_median_or_their_indices():
    t, x = alternating()
    a = run(t, x)
    assert a.respiratory_rate == pytest.approx(15.0, abs=0.5)    # media 4 s; la mediana habría dado 17
    assert a.rr_variability == pytest.approx(1.0, abs=0.05)      # DE de los intervalos (s)
    assert a.cycle_duration_s == pytest.approx(4.0, abs=0.1)


@pytest.mark.parametrize("tv", [0.1, 0.5, 1.5])
def test_e3_the_rate_does_not_depend_on_the_amplitude(tv):
    t, x, _ = tidal(15, 120.0, tv=tv)
    assert run(t, x).respiratory_rate == pytest.approx(15.0, abs=0.5)


def test_e4_fewer_than_three_breaths_is_not_available_never_zero():
    for n in (1, 2):
        t, x, _ = n_breaths(n)
        a = run(t, x)
        assert a.respiratory_rate is None and a.respiratory_rate_rounded is None and a.cycle_duration_s is None
        assert a.signal_status == "datos_insuficientes"
    t, x, _ = n_breaths(3)
    a = run(t, x)
    assert len(a.breaths) == 3 and a.respiratory_rate == pytest.approx(15.0, abs=0.5)


@pytest.mark.parametrize("value,expected", [(11.5, 12), (12.5, 13), (8.5, 9), (20.5, 21), (24.5, 25), (11.49, 11), (0.5, 1)])
def test_half_up_rounding_is_explicit_and_not_pythons_round(value, expected):
    assert round_half_up(value) == expected
    assert round(12.5) == 12 and round_half_up(12.5) == 13   # por qué no se usa round()


# ----------------------------------------------------------------------------------------------- D2 / E5-E11
def one_event(analysis):
    assert len(analysis.apnea_events) == 1, analysis.apnea_events
    return analysis.apnea_events[0]


@pytest.mark.parametrize("rr", [8, 15, 30])
@pytest.mark.parametrize("gap", [5.0, 8.0, 9.0, 9.5])
def test_e5_a_silence_shorter_than_10_s_is_not_an_apnea(rr, gap):
    for seed in range(3):
        t, x, c = tidal(rr, 120.0, gaps=[(40.0, gap)], seed=seed)
        assert run(t, x, c).apnea_count == 0


@pytest.mark.parametrize("rr", [8, 15, 30])
@pytest.mark.parametrize("gap", [10.5, 11.0, 15.0, 20.0])
def test_e6_e7_a_silence_of_at_least_10_s_is_one_apnea_located_within_half_a_second(rr, gap):
    for seed in range(3):
        t, x, c = tidal(rr, 120.0, gaps=[(40.0, gap)], seed=seed)
        a = run(t, x, c)
        ev = one_event(a)
        assert ev["start_time"] == pytest.approx(40.0, abs=0.5)
        assert ev["duration"] == pytest.approx(gap, abs=0.5)    # prototipo: <= 0.24 s
        assert not ev["truncated"]


@pytest.mark.parametrize("drop", [0.50, 0.70, 0.85, 0.88])
def test_e8_a_drop_below_90_percent_is_not_an_apnea(drop):
    t, x, c = tidal(15, 120.0, drops=[(40.0, 12.0, drop)])
    assert run(t, x, c).apnea_count == 0


@pytest.mark.parametrize("drop", [0.92, 0.95, 1.0])
def test_e9_a_drop_of_at_least_90_percent_for_12_s_is_an_apnea(drop):
    t, x, c = tidal(15, 120.0, drops=[(40.0, 12.0, drop)])
    ev = one_event(run(t, x, c))
    assert ev["duration"] == pytest.approx(12.0, abs=0.5)


def test_e10_two_silences_separated_by_5_s_of_breathing_are_two_events():
    t, x, c = tidal(15, 120.0, gaps=[(30.0, 12.0), (47.0, 12.0)])
    a = run(t, x, c)
    assert a.apnea_count == 2
    assert [round(e["start_time"]) for e in a.apnea_events] == [30, 47]


def test_e11_an_event_in_progress_at_the_start_is_not_evaluable_and_does_not_count():
    t, x, c = tidal(15, 120.0, gaps=[(0.0, 12.0)])
    a = run(t, x, c)
    assert a.apnea_count == 0 and a.apnea_events == []
    assert len(a.non_evaluable_events) == 1 and "inicio del registro" in a.non_evaluable_events[0]["reason"]


def test_e11_an_event_reaching_the_end_counts_only_with_10_s_inside_and_is_marked_truncated():
    t, x, c = tidal(15, 120.0, gaps=[(108.0, 12.0)])
    ev = one_event(run(t, x, c))
    assert ev["truncated"] is True and ev["duration"] == pytest.approx(12.0, abs=0.5)
    t, x, c = tidal(15, 120.0, gaps=[(111.0, 9.0)])
    assert run(t, x, c).apnea_count == 0                       # sólo 9 s dentro del registro


def test_the_baseline_is_declared_in_every_event_and_short_records_say_so():
    t, x, c = tidal(15, 120.0, gaps=[(40.0, 12.0)])
    b = one_event(run(t, x, c))["baseline"]
    assert b["n_breaths"] >= 8 and b["declared_short"] is True and "respiraciones previas" in b["rule"]
    t, x, c = tidal(15, 300.0, gaps=[(200.0, 12.0)])
    assert one_event(run(t, x, c))["baseline"]["declared_short"] is False   # 120 s previos disponibles


def test_an_unstable_baseline_uses_the_three_largest_breaths():
    t, x, c = tidal(15, 120.0, gaps=[(100.0, 12.0)])
    x = x.copy()
    for k, f in enumerate(np.linspace(0.2, 1.0, 20)):           # amplitudes muy variables antes del evento
        w = (t >= 4.0 * k) & (t < 4.0 * k + 4.0)
        x[w] *= f
    assert "3 mayores" in one_event(run(t, x, c))["baseline"]["rule"]


# ----------------------------------------------------------------------------------------- señal / ruido E12-E14
def test_e12_a_flat_signal_is_no_signal_not_zero_apneas():
    t = np.arange(int(120 * FS)) / FS
    x = np.random.default_rng(1).normal(0, 0.02, len(t))
    a = run(t, x)
    assert a.respiratory_rate is None and a.signal_status == "sin_senal_respiratoria"
    assert a.apnea_count is None and a.equivalent_rate_per_hour is None   # "no evaluable", no "0 apneas"


def test_e13_strong_white_noise_has_no_rate_and_no_invented_breaths():
    t = np.arange(int(120 * FS)) / FS
    for seed, sd in ((0, 1.0), (1, 5.0)):
        a = run(t, np.random.default_rng(seed).normal(0, sd, len(t)))
        assert a.respiratory_rate is None and len(a.breaths) == 0


@pytest.mark.parametrize("noise", [0.02, 0.5, 1.0, 2.0, 3.0])
def test_e14_the_rate_survives_noise_down_to_an_amplitude_to_noise_ratio_of_2_5(noise):
    for seed in range(3):
        t, x, _ = tidal(15, 120.0, noise=noise, seed=seed)       # amplitud pico 7.5: SNR = 375 ... 2.5
        assert run(t, x).respiratory_rate == pytest.approx(15.0, abs=0.5)


def test_e14_below_that_it_either_refuses_or_is_right_never_confidently_wrong():
    for seed in range(3):
        t, x, _ = tidal(15, 120.0, noise=5.0, seed=seed)         # SNR 1.5
        fr = run(t, x).respiratory_rate
        assert fr is None or abs(fr - 15.0) <= 0.5


def test_the_amplitude_gate_is_relative_the_same_signal_at_any_scale_gives_the_same_result():
    for scale in (0.01, 1.0, 1000.0):
        t, x, c = tidal(15, 120.0, gaps=[(40.0, 12.0)])
        a = run(t, x * scale, c)
        assert a.respiratory_rate == pytest.approx(15.0, abs=0.5) and a.apnea_count == 1


# ----------------------------------------------------------------------------------- tipo de apnea E15-E17
@pytest.mark.parametrize("tv", [0.1, 0.3, 0.5, 1.5])
def test_e15_an_obstructive_apnea_is_obstructive_at_any_tidal_volume(tv):
    # el flujo se corta pero el esfuerzo (tórax) continúa al 100 %
    t, x, c = tidal(15, 120.0, tv=tv, gaps=[(40.0, 14.0)], effort_gaps=[])
    ev = one_event(run(t, x, c))
    assert ev["type"] == "obstructive" and ev["type_label"] == "Criterio BIOCORE" and ev["mixed_pending"] is False


@pytest.mark.parametrize("tv", [0.1, 0.5, 1.5])
def test_e16_a_central_apnea_has_the_effort_dropped_at_least_90_percent(tv):
    t, x, c = tidal(15, 120.0, tv=tv, gaps=[(40.0, 14.0)])       # flujo y esfuerzo ausentes
    assert one_event(run(t, x, c))["type"] == "central"
    if tv >= 0.5:  # con tv 0.1 el 10 % del esfuerzo (0.01) queda a la altura del ruido del canal (sd 0.01): no es resoluble
        c2 = c.copy()
        w = (t >= 40.0) & (t < 54.0)
        c2[w] = c[w] + 0.08 * np.sin(2 * np.pi * t[w] / 4.0) * tv     # esfuerzo residual del 8 %: sigue siendo caída >= 90 %
        assert one_event(run(t, x, c2))["type"] == "central"


def test_e17_a_mixed_apnea_is_computed_and_marked_pending_validation():
    t, x, c = tidal(15, 120.0, gaps=[(40.0, 20.0)], effort_gaps=[(40.0, 10.0)])
    ev = one_event(run(t, x, c))
    assert ev["type"] == "mixed" and ev["mixed_pending"] is True


def test_without_an_effort_channel_the_type_is_unknown_not_guessed():
    t, x, _ = tidal(15, 120.0, gaps=[(40.0, 14.0)])
    ev = one_event(run(t, x, None))
    assert ev["type"] == "unknown" and ev["mixed_pending"] is False


# --------------------------------------------------------------------------------------------- D4 / E19-E20
@pytest.mark.parametrize("dur,gaps", [(120.0, [(40.0, 12.0)]), (120.0, [(30.0, 12.0), (80.0, 15.0)]), (300.0, [(50.0, 11.0), (150.0, 12.0), (250.0, 20.0)])])
def test_e19_count_total_time_and_extrapolated_rate_per_hour_of_record(dur, gaps):
    t, x, c = tidal(15, dur, gaps=gaps)
    a = run(t, x, c)
    assert a.apnea_count == len(gaps)
    assert a.equivalent_rate_per_hour == pytest.approx(len(gaps) * 3600.0 / dur, abs=0.01)
    assert a.apnea_total_time_s == pytest.approx(sum(g[1] for g in gaps), abs=0.5 * len(gaps))
    assert a.record_duration_s == dur


def test_there_is_no_severity_category_and_no_index_per_sleep_hour_in_the_result():
    t, x, c = tidal(15, 120.0, gaps=[(40.0, 12.0)])
    a = run(t, x, c)
    assert a.severity is None and a.breathing_pattern is None and a.clinical_notes == [] and a.oxygen_desaturation_index is None
    assert not hasattr(a, "apnea_hypopnea_index")


def test_e20_cheyne_stokes_the_valleys_recover_the_modulation_period_and_it_is_not_evaluable_in_a_short_record():
    d, a = gen_run("cheyne_stokes", 15, 300)
    assert a.event_period_s == pytest.approx(60.0, abs=3.0)
    assert all(e["type"] == "central" for e in a.apnea_events)
    assert a.cheyne_stokes_evaluable is False and "2 horas" in a.cheyne_stokes_note and "Berry 2012" in a.cheyne_stokes_note


# ------------------------------------------------------- integración con el ground truth del generador (E21/E24)
PATTERNS = ("normal", "tachypnea", "bradypnea", "apnea_central", "apnea_obstructive", "cheyne_stokes", "ataxic")


@pytest.mark.parametrize("pattern", PATTERNS)
@pytest.mark.parametrize("rr", [8, 12, 15, 20, 30])
def test_e24_the_rate_matches_the_generators_effective_rate_and_is_never_60_by_construction(pattern, rr):
    d, a = gen_run(pattern, rr, 300)
    truth = d["ground_truth"]["effective_respiratory_rate"]
    assert a.respiratory_rate == pytest.approx(truth, abs=0.5)
    if truth < 55:
        assert a.respiratory_rate != 60.0 and a.respiratory_rate_rounded != 60


@pytest.mark.parametrize("pattern", ["apnea_central", "apnea_obstructive"])
@pytest.mark.parametrize("rr", [8, 15, 30])
@pytest.mark.parametrize("dur", [60, 120, 300])
def test_the_detected_events_are_the_annotated_ones(pattern, rr, dur):
    d, a = gen_run(pattern, rr, dur)
    truth = d["ground_truth"]["events"]
    assert a.apnea_count == len(truth) >= 1
    kind = truth[0]["type"]
    for det, ann in zip(a.apnea_events, truth):
        assert det["start_time"] == pytest.approx(ann["start_s"], abs=0.5)
        assert det["duration"] == pytest.approx(ann["duration_s"], abs=0.5)
        assert det["type"] == kind                                   # central / obstructiva por el esfuerzo
        # "recortado" = el evento llega al final del registro (no se observó la recuperación)
        assert det["truncated"] == (ann["truncated"] or ann["start_s"] + ann["duration_s"] >= dur - 0.01)


def test_cheyne_stokes_valleys_are_detected_as_central_apneas_with_the_ramp_tolerance():
    d, a = gen_run("cheyne_stokes", 15, 300)
    truth = d["ground_truth"]["events"]
    assert a.apnea_count == len(truth) == 5
    for det, ann in zip(a.apnea_events, truth):
        # con una envolvente que crece desde 0 el tramo con caída >= 90 % rodea la apnea anotada: la CONTIENE y
        # se extiende unos segundos por lado (rampa + la espiración de la última respiración notable)
        assert det["start_time"] <= ann["start_s"] + 0.5
        assert det["start_time"] + det["duration"] >= ann["start_s"] + ann["duration_s"] - 0.5
        assert ann["duration_s"] <= det["duration"] <= ann["duration_s"] + 10.0
        assert det["type"] == "central"


def test_the_false_positive_apnea_of_tachypnea_at_rate_8_is_gone():
    """Con el detector anterior, taquipnea con FR 8 (efectiva 12/min) contaba 1 apnea falsa a los 60, 120 y 300 s."""
    for dur in (60, 120, 300):
        for seed in range(3):
            d, a = gen_run("tachypnea", 8, dur, seed)
            assert a.apnea_count == 0 and a.equivalent_rate_per_hour == 0.0


@pytest.mark.parametrize("pattern", ["normal", "tachypnea", "bradypnea", "ataxic"])
def test_no_pattern_without_a_real_apnea_reports_one(pattern):
    for seed in range(5):  # varias semillas: la atáxica es aleatoria
        for rr in (8, 15, 30):
            d, a = gen_run(pattern, rr, 300, seed)
            assert a.apnea_count == 0, (pattern, rr, seed)


def test_e22_the_detector_is_deterministic():
    d = RespiratorySignalGenerator(FS).generate_respiration(duration=120, params=RespiratoryPattern(pattern_type="apnea_central"), seed=3)
    an = RespiratoryAnalyzer(FS)
    a = an.analyze_respiration(d["airflow"], d["time"], d["spo2"], d["chest_wall"])
    b = an.analyze_respiration(d["airflow"], d["time"], d["spo2"], d["chest_wall"])
    assert a == b


def test_ataxic_irregular_breathing_is_measured_with_its_variability():
    d, a = gen_run("ataxic", 15, 300)
    assert a.respiratory_rate == pytest.approx(d["ground_truth"]["effective_respiratory_rate"], abs=0.5)
    assert a.rr_variability / a.cycle_duration_s > 0.12         # la irregularidad (CV pedido 0.20) se ve en la variabilidad


# ----------------------------------------------------------------------------- heurísticas declaradas y bugs 12/13
def test_every_technical_threshold_outside_the_signed_criteria_is_declared_as_heuristic():
    assert len(HEURISTICS) >= 10
    for name, (value, calibration) in HEURISTICS.items():
        assert calibration.strip(), name       # cada una lleva su calibración documentada


def test_bug_12_the_dead_estimated_rr_is_buried():
    import inspect

    from src.signals.respiration import preprocessing

    assert "estimated_rr" not in inspect.getsource(preprocessing)


def test_bug_13_the_package_import_no_longer_hides_failures():
    import ast
    import pathlib

    src = pathlib.Path("src/signals/respiration/__init__.py").read_text(encoding="utf-8")
    assert not any(isinstance(n, ast.Try) for n in ast.walk(ast.parse(src)))
