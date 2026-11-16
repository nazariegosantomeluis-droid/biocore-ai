"""12 Derivaciones rehecha (2026-11-14, Art. I): generador con verdad conocida y analizador que la recupera.

Antes, en el escenario «Normal», la página decía «✅ LBBB» y «Q wave in II: pathological_q»: el generador
hacía un QRS de 160 ms aun en «Normal» y el analizador decidía bloqueo de rama por la amplitud de la R.
Aquí:
- El generador cumple Einthoven/Goldberger y construye cada escenario con valores que cumplen (o no) los
  criterios citados; su verdad sale aparte.
- El analizador mide sobre el latido mediano sin leer esa verdad, y lo que mide cae dentro de una
  tolerancia de la verdad (golden test), también con el ruido de la «captura de dispositivo».
- Cada escenario cumple exactamente los criterios que nombra, y nada más (sin falsos «hallazgos»).
- Lo que no se puede evaluar se dice: derivaciones que faltan, bloqueo de rama (ESC 2023), sin línea
  isoeléctrica (flutter), QT con QRS ancho (Rautaharju 2009).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from streamlit.testing.v1 import AppTest

from src.signals.ecg.twelve_lead_measure import POPULATIONS, analyze_twelve_lead
from src.signals.ecg.twelve_lead_synth import LEADS, SCENARIOS, generate_twelve_lead

ROOT = Path(__file__).resolve().parents[1]
HR = {"tachycardia": 120.0, "bradycardia": 45.0, "af": 130.0, "flutter": 150.0}
EXPECTED = {
    "normal": set(), "tachycardia": {"sinus_tachycardia"}, "bradycardia": {"sinus_bradycardia"},
    "anterior_stemi": {"stemi"}, "inferior_stemi": {"stemi"}, "lateral_stemi": {"stemi"}, "rbbb": {"rbbb"},
    "lbbb": {"lbbb"}, "lvh": {"lvh"}, "af": {"af"}, "flutter": set(), "wpw": {"preexcitation"},
    "long_qt": {"qtc", "qtc_500"},
}
NORMAL_WHEN_MET = {"sinus", "t_wave"}


def _met(report):
    return {c.key for c in report.criteria if c.met is True} - NORMAL_WHEN_MET


# --- el generador ----------------------------------------------------------------------------------------

@pytest.mark.parametrize("scenario", SCENARIOS)
def test_limb_leads_follow_einthoven_and_goldberger_even_with_noise(scenario):
    leads, _ = generate_twelve_lead(scenario, HR.get(scenario, 75.0), seed=3, noise_mv=0.02)
    i, ii = leads["I"], leads["II"]
    for name, expected in (("III", ii - i), ("aVR", -(i + ii) / 2), ("aVL", i - ii / 2), ("aVF", ii - i / 2)):
        assert np.allclose(leads[name], expected, atol=1e-12), name


def test_each_scenario_is_built_to_meet_its_criteria():
    t = {sc: generate_twelve_lead(sc, HR.get(sc, 75.0))[1] for sc in SCENARIOS}
    assert t["normal"].qrs_ms < 110 and 120 <= t["normal"].pr_ms <= 200 and 390 < t["normal"].qtc_bazett_ms < 450
    assert t["rbbb"].qrs_ms >= 120 and t["lbbb"].qrs_ms >= 120
    assert t["wpw"].pr_ms < 120 and t["wpw"].qrs_ms > 120 and t["wpw"].preexcitation
    assert t["long_qt"].qtc_bazett_ms >= 500
    assert t["lvh"].sokolow_lyon_mv >= 3.5 and t["normal"].sokolow_lyon_mv < 3.5
    st = {sc: t[sc].st_j_mv for sc in ("anterior_stemi", "inferior_stemi", "lateral_stemi")}
    assert min(st["anterior_stemi"][ld] for ld in ("V2", "V3")) >= 0.25            # el umbral más alto de V2–V3
    assert min(st["inferior_stemi"][ld] for ld in ("II", "III", "aVF")) >= 0.1
    assert min(st["lateral_stemi"][ld] for ld in ("I", "aVL")) >= 0.1
    assert max(abs(v) for v in t["normal"].st_j_mv.values()) < 0.01
    assert t["af"].rhythm == "fa" and t["af"].pr_ms is None
    rr = np.diff(t["af"].qrs_onsets_s)
    assert np.std(rr) / np.mean(rr) >= 0.08 and t["af"].heart_rate_bpm == pytest.approx(130.0, abs=1.0)
    assert t["flutter"].atrial_rate_bpm == 300.0 and t["flutter"].heart_rate_bpm == pytest.approx(150.0)
    assert t["flutter"].pr_ms is None


def test_the_analyzer_never_reads_the_generator_truth():
    src = (ROOT / "src/signals/ecg/twelve_lead_measure.py").read_text(encoding="utf-8")
    assert "twelve_lead_synth" not in src and "truth" not in src.lower().replace("ground truth", "")


# --- lo medido contra la verdad (golden test) --------------------------------------------------------------

def _check(scenario, hr, seed, noise_mv, wander_mv, tol):
    leads, truth = generate_twelve_lead(scenario, hr, seed=seed, noise_mv=noise_mv, baseline_wander_mv=wander_mv)
    rep = analyze_twelve_lead(leads)
    assert rep.n_beats >= 5
    assert abs(rep.heart_rate_bpm - truth.heart_rate_bpm) <= 2.0, (scenario, rep.heart_rate_bpm)
    assert abs(rep.qrs_ms - truth.qrs_ms) <= tol["qrs"], (scenario, rep.qrs_ms, truth.qrs_ms)
    assert -tol["qt"] <= rep.qt_ms - truth.qt_ms <= 8.0, (scenario, rep.qt_ms, truth.qt_ms)
    if truth.pr_ms is not None:
        assert rep.p_wave == "sinusal" and abs(rep.pr_ms - truth.pr_ms) <= tol["pr"], (scenario, rep.pr_ms)
    if scenario == "flutter":                       # ondas F: sin segmento isoeléctrico no hay eje ni ST
        assert rep.axis is None and rep.criterion("stemi").met is None
    else:
        assert abs(rep.axis.axis_degrees - truth.axis_deg) <= 5.0, (scenario, rep.axis, truth.axis_deg)
        assert max(abs(rep.st_j_mv[ld] - truth.st_j_mv[ld]) for ld in LEADS) <= tol["st"], scenario
    assert _met(rep) == EXPECTED[scenario], (scenario, sorted(_met(rep)))
    return rep


@pytest.mark.parametrize("scenario", SCENARIOS)
@pytest.mark.parametrize("seed", [0, 4])
def test_measurements_recover_the_truth_and_only_the_named_criteria_are_met(scenario, seed):
    for hr in ([HR[scenario]] if scenario in HR else [55.0, 90.0]):
        _check(scenario, hr, seed, 0.01, 0.0, {"qrs": 8.0, "pr": 12.0, "qt": 15.0, "st": 0.03})


@pytest.mark.parametrize("scenario", ["normal", "anterior_stemi", "inferior_stemi", "rbbb", "lbbb", "lvh", "af", "wpw"])
def test_same_with_the_noise_and_drift_of_the_simulated_device_capture(scenario):
    _check(scenario, HR.get(scenario, 80.0), 2, 0.025, 0.05, {"qrs": 10.0, "pr": 15.0, "qt": 25.0, "st": 0.04})


# --- criterios: umbrales que dependen del sexo y la edad, exclusiones y derivaciones que faltan -----------

def test_st_threshold_in_v2_v3_depends_on_sex_and_age():
    leads, truth = generate_twelve_lead("anterior_stemi", 75.0, st_elevation_mv=0.15, noise_mv=0.005)
    assert 0.16 <= truth.st_j_mv["V3"] <= 0.19 and truth.st_j_mv["V4"] >= 0.12
    mixed = analyze_twelve_lead(leads).criterion("stemi")
    assert mixed.met is None and "cumple para mujer" in mixed.detail.lower() and "no cumple para hombre" in mixed.detail
    assert analyze_twelve_lead(leads, population="mujer").criterion("stemi").met is True
    assert analyze_twelve_lead(leads, population="hombre_40_o_mas").criterion("stemi").met is False
    assert analyze_twelve_lead(leads, population="hombre_menor_40").criterion("stemi").met is False
    with pytest.raises(ValueError):
        analyze_twelve_lead(leads, population="otro")
    assert set(POPULATIONS) == {"mujer", "hombre_40_o_mas", "hombre_menor_40"}


def test_lowering_the_st_elevation_below_the_threshold_turns_the_stemi_criterion_off():
    leads, _ = generate_twelve_lead("inferior_stemi", 75.0, st_elevation_mv=0.05)
    assert analyze_twelve_lead(leads).criterion("stemi").met is False


def test_bundle_branch_block_makes_st_and_qtc_not_evaluable_with_the_reason():
    rep = analyze_twelve_lead(generate_twelve_lead("lbbb", 75.0)[0])
    stemi, qtc = rep.criterion("stemi"), rep.criterion("qtc")
    assert stemi.met is None and "ESC 2023" in stemi.detail and "IAMCEST" in stemi.detail
    assert "Byrne" in stemi.source and "3.2.1" in stemi.source
    assert qtc.met is None and "ajuste por la duración del QRS" in qtc.detail and "Rautaharju" in qtc.source


def test_only_lead_ii_says_what_cannot_be_evaluated():
    leads, _ = generate_twelve_lead("normal", 75.0)
    rep = analyze_twelve_lead({"II": leads["II"], "time": leads["time"]})
    assert rep.axis is None and rep.p_wave == "presente" and rep.criterion("sinus").met is None
    assert rep.criterion("rbbb").met is None and rep.criterion("lbbb").met is None
    assert rep.criterion("stemi").met is None and "contiguas" in rep.criterion("stemi").detail
    assert rep.criterion("lvh") is None and any("HVI" in u for u in rep.unavailable)
    assert abs(rep.qrs_ms - 90.0) <= 10 and abs(rep.heart_rate_bpm - 75.0) <= 2


def test_eight_independent_leads_are_completed_by_einthoven_and_goldberger():
    leads, _ = generate_twelve_lead("anterior_stemi", 75.0)
    eight = {k: leads[k] for k in ("I", "II", "V1", "V2", "V3", "V4", "V5", "V6", "time")}
    full, partial = analyze_twelve_lead(leads), analyze_twelve_lead(eight)
    assert _met(partial) == _met(full) == {"stemi"}
    assert any("III, aVR, aVL, aVF" in u for u in partial.unavailable)


def test_flutter_is_not_called_anything_the_analyzer_cannot_identify():
    rep = analyze_twelve_lead(generate_twelve_lead("flutter", 150.0)[0])
    assert rep.criterion("af").met is False and rep.criterion("rhythm_unidentified").met is None
    assert "ondas F" in rep.criterion("rhythm_unidentified").detail
    assert rep.criterion("t_wave").met is None


def test_too_short_or_empty_records_do_not_invent_values():
    assert analyze_twelve_lead({}).n_beats == 0
    leads, _ = generate_twelve_lead("normal", 75.0, duration_s=2.0)
    rep = analyze_twelve_lead(leads)
    assert rep.n_beats == 0 and rep.criteria == () and rep.unavailable


# --- lo que se ve ------------------------------------------------------------------------------------------

def test_the_report_view_separates_findings_from_measurements_and_cites():
    from app.supermodules.ecg_12.report_view import findings

    leads, truth = generate_twelve_lead("rbbb", 75.0)
    rep = analyze_twelve_lead(leads)
    assert [c.key for c in findings(rep)] == ["rbbb"]

    def _script():
        from src.signals.ecg.twelve_lead_measure import analyze_twelve_lead as analyze
        from src.signals.ecg.twelve_lead_synth import generate_twelve_lead as gen
        from app.supermodules.ecg_12.report_view import render_twelve_lead_report

        lds, tr = gen("rbbb", 75.0)
        render_twelve_lead_report(analyze(lds), tr)

    at = AppTest.from_function(_script, default_timeout=120).run()
    assert not at.exception, at.exception
    text = " ".join(m.value for m in at.markdown)
    assert "Hallazgos automáticos:** Bloqueo de rama derecha completo" in text
    assert "✅" not in text and "Recomendaciones" not in text
    assert any("Surawicz" in c.value for c in at.caption)
    assert any("construyó el generador" in e.label for e in at.expander)


def _page():
    def _script():
        from app.supermodules.ecg_12.pages import render_views
        render_views()

    at = AppTest.from_function(_script, default_timeout=180).run()
    assert not at.exception, at.exception
    return at


def _select(at, part):
    box = next(b for b in at.selectbox if "Escenario" in b.label)
    box.set_value(next(o for o in box.options if part in o))
    next(b for b in at.button if "Generar ECG" in b.label).click()
    at.run()
    assert not at.exception, at.exception
    return at


def test_the_page_no_longer_calls_a_normal_ecg_lbbb():
    at = _page()
    text = " ".join(m.value for m in at.markdown)
    assert "Hallazgos automáticos:** ninguno de los criterios evaluados se cumple" in text
    assert "LBBB" not in text and "pathological_q" not in text and "Recomendaciones Clínicas" not in text
    assert set(k for k in at.session_state["ecg_data"] if k != "time") == set(LEADS)
    assert next(s for s in at.slider if s.key == "ecglab_12_st_slider").disabled


def test_the_page_finds_what_each_scenario_names():
    at = _page()
    for part, title in (("STEMI Anterior", "Elevación del ST en el punto J"), ("izquierda (LBBB)", "Bloqueo de rama izquierda"),
                        ("WPW", "Preexcitación ventricular"), ("QT largo", "QTc prolongado")):
        _select(at, part)
        summary = next(m.value for m in at.markdown if "Hallazgos automáticos" in m.value)
        assert title in summary, (part, summary)
    _select(at, "derecha (RBBB)")
    assert next(s for s in at.slider if s.key == "ecglab_12_qrs_duration_slider").disabled


def test_the_st_slider_moves_the_stemi_criterion():
    at = _select(_page(), "STEMI Inferior")
    assert "Elevación del ST" in next(m.value for m in at.markdown if "Hallazgos automáticos" in m.value)
    next(s for s in at.slider if s.key == "ecglab_12_st_slider").set_value(0.05)
    next(b for b in at.button if "Generar ECG" in b.label).click()
    at.run()
    assert "Elevación del ST" not in next(m.value for m in at.markdown if "Hallazgos automáticos" in m.value)


def test_the_old_analyzer_class_is_gone_and_the_axis_formula_stays():
    import src.signals.ecg.twelve_lead_analyzer as old

    assert not hasattr(old, "TwelveLeadEcgAnalyzer") and hasattr(old, "qrs_axis_from_net")
    page = (ROOT / "app/supermodules/ecg_12/page_content.py").read_text(encoding="utf-8")
    assert "TwelveLeadEcgGenerator(" not in page and "AdvancedEcgPatterns." not in page
    assert "'aVR': -base" not in page and "'aVR': -signal" not in page        # ya no se copian señales
