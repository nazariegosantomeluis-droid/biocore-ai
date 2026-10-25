"""Calculadoras clínicas (Tanda 2C, 2026-10-24): verdad de referencia INDEPENDIENTE.

Reemplaza los tests del aporte, que calculaban el esperado con la misma fórmula
bajo prueba (p. ej. `assert bazett == 360 / sqrt(0.6)`): un test así pasa aunque
la fórmula esté mal escrita en los dos lados. Aquí cada esperado sale de:

- la tabla o el corte publicado del estándar (NEWS2 RCP 2017, Berlín 2012,
  OMS 2000, AHA/ACCF/HRS 2009, Sepsis-3, ISA/ISO 2533), transcrito como literal;
- un caso canónico de libro (PAO₂ ≈ 100 mmHg al nivel del mar, PAM ≈ 93 con 120/80);
- un cálculo manual escrito como número, con la aritmética en el comentario;
- para el eje: un vector cardíaco de ángulo conocido, la regla de la derivación
  isoeléctrica y la regla de signos (mismo enfoque que test_qrs_axis_einthoven.py).
"""
import inspect
import math

import numpy as np
import pytest

from clinical import calculators as c


# ═══ QTc ════════════════════════════════════════════════════════════════════

def test_every_qtc_correction_is_the_identity_at_60_bpm():
    """Definición: las cuatro normalizan a RR = 1 s (FC 60), así que ahí QTc = QT."""
    for name, value in c.qtc_all(400, 60).items():
        assert value == pytest.approx(400.0), name


@pytest.mark.parametrize("qt,hr,expected", [
    # FC 100 -> RR 0.6 s. √0.6 = 0.774597; ∛0.6 = 0.843433
    (360, 100, {"Bazett": 464.76, "Fridericia": 426.83,
                "Framingham": 421.60,   # 360 + 154·0.4
                "Hodges": 430.00}),     # 360 + 1.75·40
    # FC 50 -> RR 1.2 s. √1.2 = 1.095445; ∛1.2 = 1.062659
    (440, 50, {"Bazett": 401.66, "Fridericia": 414.06,
               "Framingham": 409.20,    # 440 − 154·0.2
               "Hodges": 422.50}),      # 440 − 1.75·10
])
def test_qtc_against_hand_computed_values(qt, hr, expected):
    got = c.qtc_all(qt, hr)
    for name, value in expected.items():
        assert got[name] == pytest.approx(value, abs=0.01), name


def test_bazett_overcorrects_fast_and_undercorrects_slow_rates():
    """Hecho clínico citado por la misma guía AHA 2009 (independiente de la fórmula)."""
    fast, slow = c.qtc_all(360, 100), c.qtc_all(440, 50)
    assert fast["Bazett"] > fast["Fridericia"] and slow["Bazett"] < slow["Fridericia"]


@pytest.mark.parametrize("qtc,sex,level", [
    # AHA/ACCF/HRS 2009: prolongado ≥450 ms (hombres) / ≥460 ms (mujeres); corto ≤390
    (449, "M", "normal"), (450, "M", "leve"), (459, "F", "normal"), (460, "F", "leve"),
    (391, "M", "normal"), (390, "M", "leve"), (390, "F", "leve"),
    # Drew 2010: >500 ms
    (500, "M", "leve"), (501, "M", "severo"), (501, "F", "severo"),
])
def test_qtc_thresholds_are_the_guideline_numbers(qtc, sex, level):
    assert c.classify_qtc(qtc, sex)[0] == level


def test_qtc_rejects_non_positive_inputs():
    with pytest.raises(ValueError):
        c.qtc_bazett(0, 1.0)
    with pytest.raises(ValueError):
        c.qtc_all(400, 0)


# ═══ FC desde el papel ═══════════════════════════════════════════════════════

def test_heart_rate_from_paper_follows_the_25_mm_s_grid():
    """A 25 mm/s: cuadro grande = 0.20 s, pequeño = 0.04 s. 4 grandes = 0.8 s → 75 lpm."""
    assert c.hr_from_ecg_paper(large_squares=4) == pytest.approx(75)
    assert c.hr_from_ecg_paper(large_squares=3) == pytest.approx(100)    # 0.6 s
    assert c.hr_from_ecg_paper(small_squares=20) == pytest.approx(75)    # 0.8 s
    assert c.hr_from_ecg_paper(small_squares=25) == pytest.approx(60)    # 1.0 s
    for n in (2, 3, 4, 6):  # un cuadro grande son 5 pequeños
        assert c.hr_from_ecg_paper(large_squares=n) == pytest.approx(c.hr_from_ecg_paper(small_squares=5 * n))
    assert c.hr_six_second_method(8) == pytest.approx(80)
    assert c.hr_from_rr_ms(800) == pytest.approx(75) and c.hr_from_rr_ms(1000) == pytest.approx(60)
    assert [c.classify_heart_rate(h)[0] for h in (59, 60, 100, 101)] == ["leve", "normal", "normal", "leve"]


# ═══ Eje QRS: la fórmula de main, no la del aporte ═══════════════════════════

def _leads(theta_deg):
    """Vector de ángulo conocido: I y II por proyección (0° y +60°); aVF como la
    deriva un electrocardiógrafo, aVF = II − I/2."""
    t = math.radians(theta_deg)
    lead_i, lead_ii = math.cos(t), math.cos(t - math.radians(60))
    return lead_i, lead_ii, lead_ii - lead_i / 2


def _wrap(d):
    return (d + 180.0) % 360.0 - 180.0


def test_axis_recovers_the_angle_of_a_known_vector():
    for theta in np.arange(-179.0, 180.0, 1.0):
        lead_i, _, avf = _leads(theta)
        assert _wrap(c.qrs_axis(lead_i, avf).axis_degrees - theta) == pytest.approx(0.0, abs=1e-9), theta


def test_axis_is_identical_to_the_twelve_lead_analyzer():
    from src.signals.ecg.twelve_lead_analyzer import TwelveLeadEcgAnalyzer

    analyzer = TwelveLeadEcgAnalyzer()
    for theta in np.arange(-179.5, 180.0, 0.5):
        lead_i, lead_ii, avf = _leads(theta)
        ref = analyzer._determine_qrs_axis(np.array([lead_i]), np.array([avf]), np.array([lead_ii]))
        got = c.qrs_axis(lead_i, avf)
        assert got.axis_degrees == pytest.approx(ref.axis_degrees, abs=1e-12) and got.category == ref.category


@pytest.mark.parametrize("theta", [-30.5, -31.0, -32.0, -33.0, -33.5])
def test_mild_left_deviation_is_not_called_normal(theta):
    lead_i, lead_ii, avf = _leads(theta)
    assert lead_ii < 0  # la regla de signos ya dice "izquierda": II negativa
    old = math.degrees(math.atan2(avf, lead_i))  # la fórmula del aporte
    assert old > -30.0, "el caso sí está en la zona que el bug llamaba normal"
    axis = c.qrs_axis(lead_i, avf)
    assert axis.category == "LAD"
    level, label, _ = c.classify_qrs_axis(axis)
    assert level == "leve" and "izquierda" in label


@pytest.mark.parametrize("name,lead_i,lead_ii,expected", [
    # El eje es perpendicular a la derivación isoeléctrica (regla de libro).
    ("II isoeléctrica", 1.0, 0.0, -30.0),
    ("aVF isoeléctrica", 1.0, 0.5, 0.0),     # aVF = II − I/2 = 0
    ("III isoeléctrica", 1.0, 1.0, 30.0),    # III = II − I = 0
    ("aVL isoeléctrica", 1.0, 2.0, 60.0),    # aVL = I − II/2 = 0
    ("I isoeléctrica", 0.0, 1.0, 90.0),
    ("aVR isoeléctrica", 1.0, -1.0, -60.0),  # aVR = −(I + II)/2 = 0
])
def test_isoelectric_lead_rule(name, lead_i, lead_ii, expected):
    assert c.qrs_axis(lead_i, lead_ii - lead_i / 2).axis_degrees == pytest.approx(expected, abs=1e-9), name


def test_three_lead_sign_rule_every_half_degree():
    """Sin ángulos: signos de I, II y aVF → zona. Paso desplazado 0.25° para no
    caer justo donde una derivación vale 0."""
    for theta in np.arange(-179.75, 180.0, 0.5):
        lead_i, lead_ii, avf = _leads(theta)
        if lead_i > 0 and (avf > 0 or lead_ii > 0):
            expected = "Normal"
        elif lead_i > 0:
            expected = "LAD"
        elif avf > 0:
            expected = "RAD"
        else:
            expected = "Extreme"
        assert c.qrs_axis(lead_i, avf).category == expected, theta


def test_calculator_has_no_axis_formula_of_its_own():
    from src.signals.ecg import twelve_lead_analyzer as tla

    src = inspect.getsource(c)  # la cita sí NOMBRA la fórmula; lo que no debe haber es una llamada
    assert "math.atan2(" not in src and "arctan2(" not in src and "math.degrees(" not in src
    assert c.qrs_axis_from_net is tla.qrs_axis_from_net


def test_axis_undefined_when_both_leads_are_zero():
    with pytest.raises(ValueError):
        c.qrs_axis(0, 0)
    assert c.classify_qrs_axis(None)[0] == "no_disponible"


# ═══ Hemodinamia ═════════════════════════════════════════════════════════════

def test_map_and_pulse_pressure_textbook_values():
    assert c.mean_arterial_pressure(120, 80) == pytest.approx(93.33, abs=0.01)  # 80 + 40/3
    assert c.mean_arterial_pressure(90, 60) == pytest.approx(70.0)              # 60 + 30/3
    assert c.pulse_pressure(120, 80) == 40
    # Surviving Sepsis 2021: objetivo inicial PAM 65 mmHg
    assert c.classify_map(64.9)[0] == "severo" and c.classify_map(65)[0] == "normal"
    with pytest.raises(ValueError):
        c.mean_arterial_pressure(80, 120)


def test_shock_index_cutoffs_are_cited():
    assert c.shock_index(120, 100) == pytest.approx(1.2) and c.shock_index(60, 120) == pytest.approx(0.5)
    # Allgöwer 1967: normal 0.5–0.7. Mutschler 2013: grupo III empieza en ≥1.0.
    levels = {si: c.classify_shock_index(si)[0] for si in (0.5, 0.7, 0.71, 0.99, 1.0, 1.4)}
    assert levels == {0.5: "normal", 0.7: "normal", 0.71: "leve", 0.99: "leve", 1.0: "severo", 1.4: "severo"}
    assert "Mutschler 2013" in c.classify_shock_index(1.0)[1] and "trauma" in c.classify_shock_index(1.0)[1]
    assert "Mutschler" in c.SHOCK_INDEX_CITATION and "Crit Care 2013;17:R172" in c.SHOCK_INDEX_CITATION


def test_cardiac_index_forrester_cut_and_orientative_range():
    assert c.cardiac_output_l_min(70, 70) == pytest.approx(4.9)   # 70 lpm × 70 ml
    assert c.cardiac_index(5.0, 2.0) == pytest.approx(2.5)
    expected = {2.19: "severo", 2.2: "leve", 2.49: "leve", 2.5: "normal", 4.0: "normal", 4.01: "leve"}
    assert {ci: c.classify_cardiac_index(ci)[0] for ci in expected} == expected
    assert "Forrester 1976" in c.classify_cardiac_index(2.0)[1]
    for ci in (2.3, 3.0, 4.5):  # el rango sin cita se declara como tal en la etiqueta
        assert "orientativo" in c.classify_cardiac_index(ci)[1] and "sin cita firme" in c.classify_cardiac_index(ci)[1]
    assert "orientativo, sin cita firme" in c.FORRESTER_CITATION


# ═══ Antropometría ═══════════════════════════════════════════════════════════

def test_bmi_hand_values():
    assert c.body_mass_index(70, 175) == pytest.approx(22.857, abs=1e-3)   # 70 / 1.75²
    assert c.body_mass_index(100, 200) == pytest.approx(25.0)              # 100 / 4


@pytest.mark.parametrize("bmi,level,words", [
    # OMS 2000 (TRS 894): clase de IMC y riesgo de comorbilidades
    (18.49, "leve", "bajo peso"), (18.5, "normal", "peso normal"), (24.99, "normal", "peso normal"),
    (25.0, "leve", "aumentado"), (29.99, "leve", "sobrepeso"),
    (30.0, "leve", "clase I (30.0–34.9) — riesgo de comorbilidades moderado"), (34.99, "leve", "clase I "),
    (35.0, "severo", "clase II (35.0–39.9) — riesgo de comorbilidades severo"),
    (40.0, "severo", "muy severo"),
])
def test_bmi_who_classes_and_their_risk(bmi, level, words):
    got_level, label, _ = c.classify_bmi(bmi)
    assert got_level == level and words in label


def test_obesity_class_one_is_no_longer_red():
    level, _, badge = c.classify_bmi(32.0)
    assert level != "severo" and badge != "🔴"


def test_body_surface_area_by_hand():
    assert c.bsa_mosteller(180, 80) == pytest.approx(2.0)                 # √(180·80/3600) = √4
    assert c.bsa_mosteller(170, 70) == pytest.approx(1.8181, abs=1e-4)    # √3.30556
    # Du Bois 170 cm / 70 kg: 70^0.425 = 6.0837; 170^0.725 = 41.4072; × 0.007184 = 1.8097
    assert c.bsa_dubois(170, 70) == pytest.approx(1.8097, abs=5e-4)


# ═══ Oxigenación ═════════════════════════════════════════════════════════════

@pytest.mark.parametrize("altitude_m,mmhg", [
    # Atmósfera estándar ISO 2533, presión tabulada (Pa / 133.322 = mmHg)
    (0, 760.0), (1000, 674.1), (2000, 596.3), (3000, 525.9), (5000, 405.2),
])
def test_barometric_pressure_matches_the_isa_table(altitude_m, mmhg):
    assert c.barometric_pressure_mmhg(altitude_m) == pytest.approx(mmhg, abs=0.5)


def test_alveolar_gas_canonical_sea_level_values():
    # PIO₂ = 0.21·(760 − 47) = 149.7 (≈150 de los libros); PAO₂ = 149.7 − 40/0.8 = 99.7
    assert c.alveolar_po2(0.21, 40, 760) == pytest.approx(99.73, abs=0.01)
    assert c.alveolar_po2(1.0, 40, 760) == pytest.approx(663.0)          # 713 − 50
    assert c.aa_gradient(0.21, 90, 40, 760) == pytest.approx(9.73, abs=0.01)
    assert c.expected_aa_gradient(40) == pytest.approx(14.0)             # regla edad/4 + 4
    cdmx = c.barometric_pressure_mmhg(c.CITY_ALTITUDES_M["Ciudad de México"])
    assert 525.9 < cdmx < 596.3  # entre los valores ISA de 3000 y 2000 m


def test_fio2_must_be_a_fraction():
    with pytest.raises(ValueError):
        c.pf_ratio(80, 40)        # 40 % escrito como porcentaje
    with pytest.raises(ValueError):
        c.alveolar_po2(0.1, 40)


@pytest.mark.parametrize("pf,level,word", [
    # Berlín 2012: leve 200 < P/F ≤ 300; moderado 100 < P/F ≤ 200; grave ≤ 100
    (301, "normal", "fuera"), (300, "leve", "leve"), (201, "leve", "leve"),
    (200, "leve", "moderado"), (101, "leve", "moderado"), (100, "severo", "grave"),
])
def test_pf_ratio_berlin_bands(pf, level, word):
    got_level, label, _ = c.classify_pf_ratio(pf)
    assert got_level == level and word in label


def test_pf_ratio_hand_value():
    assert c.pf_ratio(80, 0.40) == pytest.approx(200.0)


# ═══ NEWS2: la tabla del RCP 2017, transcrita aparte y barrida entera ════════

_RCP_CHART = {  # (mín, máx, puntos), bordes incluidos, tal cual la tabla publicada
    "respiratory_rate": [(-1, 8, 3), (9, 11, 1), (12, 20, 0), (21, 24, 2), (25, 999, 3)],
    "spo2": [(-1, 91, 3), (92, 93, 2), (94, 95, 1), (96, 100, 0)],          # escala 1
    "systolic_bp": [(-1, 90, 3), (91, 100, 2), (101, 110, 1), (111, 219, 0), (220, 999, 3)],
    "pulse": [(-1, 40, 3), (41, 50, 1), (51, 90, 0), (91, 110, 1), (111, 130, 2), (131, 999, 3)],
    "temperature_c": [(-1, 35.0, 3), (35.1, 36.0, 1), (36.1, 38.0, 0), (38.1, 39.0, 1), (39.1, 99, 2)],
}
_BASELINE = dict(respiratory_rate=16, spo2=98, on_oxygen=False, systolic_bp=120, pulse=72,
                 alert=True, temperature_c=37.0)


def _chart_points(field, value):
    return next(p for lo, hi, p in _RCP_CHART[field] if lo <= value <= hi)


def _news(**overrides):
    return c.news2_score(**{**_BASELINE, **overrides})


@pytest.mark.parametrize("field,values", [
    ("respiratory_rate", range(3, 61)),
    ("spo2", range(70, 101)),
    ("systolic_bp", range(50, 261)),
    ("pulse", range(20, 201)),
    ("temperature_c", [round(33.0 + 0.1 * k, 1) for k in range(91)]),
])
def test_news2_every_value_matches_the_rcp_chart(field, values):
    for v in values:
        assert _news(**{field: v}).total == _chart_points(field, v), (field, v)


@pytest.mark.parametrize("spo2,on_o2,points", [
    # Escala 2 (RCP 2017): ≤83 →3, 84–85 →2, 86–87 →1, 88–92 →0, ≥93 en aire →0;
    # con oxígeno: 93–94 →1, 95–96 →2, ≥97 →3 (más 2 por el oxígeno)
    (83, False, 3), (84, False, 2), (85, False, 2), (86, False, 1), (87, False, 1),
    (88, False, 0), (92, False, 0), (93, False, 0), (100, False, 0),
    (93, True, 1 + 2), (94, True, 1 + 2), (95, True, 2 + 2), (96, True, 2 + 2), (97, True, 3 + 2),
])
def test_news2_spo2_scale_2(spo2, on_o2, points):
    assert _news(spo2=spo2, on_oxygen=on_o2, spo2_scale=2).total == points


@pytest.mark.parametrize("overrides,total,risk", [
    ({}, 0, "bajo"),
    ({"respiratory_rate": 25}, 3, "bajo-medio"),                        # un parámetro en 3
    ({"alert": False}, 3, "bajo-medio"),                                 # CVPU
    ({"on_oxygen": True}, 2, "bajo"),
    ({"respiratory_rate": 22, "pulse": 95, "temperature_c": 38.5}, 4, "bajo"),         # 2+1+1
    ({"respiratory_rate": 22, "pulse": 115, "temperature_c": 38.5}, 5, "medio"),       # 2+2+1
    ({"respiratory_rate": 22, "pulse": 115, "systolic_bp": 105, "temperature_c": 38.5,
      "spo2": 95}, 7, "alto"),                                                          # 2+2+1+1+1
    ({"respiratory_rate": 26, "spo2": 91, "on_oxygen": True}, 8, "alto"),              # 3+3+2
])
def test_news2_hand_scored_vignettes(overrides, total, risk):
    r = _news(**overrides)
    assert (r.total, r.risk) == (total, risk)


# ═══ qSOFA y Glasgow ═════════════════════════════════════════════════════════

@pytest.mark.parametrize("rr,sbp,mental,score", [
    # Sepsis-3 (Seymour 2016): FR ≥22, PAS ≤100, alteración mental -- 1 punto cada uno
    (21, 101, False, 0), (22, 101, False, 1), (21, 100, False, 1), (21, 101, True, 1),
    (22, 100, False, 2), (22, 101, True, 2), (21, 100, True, 2), (22, 100, True, 3),
])
def test_qsofa_truth_table(rr, sbp, mental, score):
    assert c.qsofa_score(respiratory_rate=rr, systolic_bp=sbp, altered_mentation=mental) == score
    assert c.classify_qsofa(score)[0] == ("severo" if score >= 2 else "normal")


def test_glasgow_components_and_bands():
    # Teasdale 1974: ocular 1–4, verbal 1–5, motora 1–6 → total 3–15
    assert c.glasgow_coma_scale(4, 5, 6) == 15 and c.glasgow_coma_scale(1, 1, 1) == 3
    assert c.glasgow_coma_scale(3, 4, 5) == 12
    for bad in ((5, 5, 6), (4, 6, 6), (4, 5, 7), (0, 5, 6)):
        with pytest.raises(ValueError):
            c.glasgow_coma_scale(*bad)
    # Bandas habituales en TCE: grave 3–8, moderada 9–12, leve 13–15
    expected = {3: "severo", 8: "severo", 9: "leve", 12: "leve", 13: "leve", 14: "leve", 15: "normal"}
    assert {t: c.classify_gcs(t)[0] for t in expected} == expected
    assert "moderada" in c.classify_gcs(9)[1] and "grave" in c.classify_gcs(8)[1]


def test_every_unavailable_classification_is_neutral():
    assert c.classify_qtc(None, "M")[0] == "no_disponible"
    for fn in (c.classify_heart_rate, c.classify_qrs_axis, c.classify_map, c.classify_shock_index,
               c.classify_cardiac_index, c.classify_bmi, c.classify_pf_ratio, c.classify_news2,
               c.classify_qsofa, c.classify_gcs):
        assert fn(None) == ("no_disponible", "no disponible", "")


# ═══ UI: citas visibles, eje de main en pantalla, gemelo, navegación ═════════

def _page():
    from app.supermodules.calculators.pages import run
    run()


def _text(at):
    return "\n".join([m.value for m in at.markdown] + [x.value for x in at.caption])


def test_page_shows_every_citation():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_page, default_timeout=60).run()
    assert not at.exception, at.exception
    text = _text(at)
    citations = {n: getattr(c, n) for n in dir(c) if n.endswith("_CITATION")}
    assert len(citations) == 20
    missing = [n for n, v in citations.items() if v not in text]
    assert not missing, missing


def test_page_axis_uses_the_corrected_formula():
    """DI 8.5, aVF −4.5: Einthoven da −31° (desviación izquierda); el aporte daba −28° (normal)."""
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_page, default_timeout=60).run()
    next(n for n in at.number_input if n.key == "calc_axis_i").set_value(8.5)
    next(n for n in at.number_input if n.key == "calc_axis_avf").set_value(-4.5)
    at.run()
    assert not at.exception, at.exception
    text = _text(at)
    assert "-31°" in text and "desviación izquierda" in text


def test_twin_vitals_are_imported_labelled_as_simulation():
    from streamlit.testing.v1 import AppTest

    from app.engines.digital_twin_organism import DigitalTwinOrganism

    at = AppTest.from_function(_page, default_timeout=60).run()
    assert "todavía no tiene signos vitales" in _text(at)  # sin gemelo no se inventa nada

    organism = DigitalTwinOrganism()
    organism.update_from_sensors({"ecg": {"heart_rate": 88}, "respiratory": {"respiratory_rate": 18, "spo2": 95}})
    at.session_state["twin_shell_organism"] = organism
    at.run()
    assert "Valores SIMULADOS por el gemelo" in _text(at)
    next(b for b in at.button if b.key == "calc_use_twin").click().run()
    assert not at.exception, at.exception
    assert at.session_state["calc_news_pulse"] == 88 and at.session_state["calc_qtc_hr"] == 88
    assert at.session_state["calc_news_rr"] == 18 and at.session_state["calc_news_spo2"] == 95


def test_calculators_are_routed_from_the_clinical_hub(monkeypatch):
    import app.main as m

    assert "🧮 Calculadoras Clínicas" in m.HUBS["Clinical Hub"]
    called = []
    monkeypatch.setattr(m, "render_calculators_page", lambda: called.append(True))
    m.render_page_content("🧮 Calculadoras Clínicas")
    assert called == [True]


def test_no_unaudited_art_in_the_calculators():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    for path in ("clinical/calculators.py", "app/supermodules/calculators/pages.py"):
        src = (root / path).read_text(encoding="utf-8")
        assert "visualization.art" not in src and "render_plate(" not in src and "ollama" not in src.lower(), path
