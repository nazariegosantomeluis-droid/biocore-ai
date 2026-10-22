"""Verificación de clinical/calculators.py contra ejemplos resueltos a mano y
bordes de cada tabla publicada (NEWS2, Berlín, OMS, AHA/ACCF/HRS)."""
import math

import pytest

from clinical import calculators as c


# ─── QTc ─────────────────────────────────────────────────────────────────

def test_all_qtc_formulas_agree_at_60_bpm():
    for name, value in c.qtc_all(400, 60).items():
        assert value == pytest.approx(400.0), name


def test_qtc_formulas_at_100_bpm():
    q = c.qtc_all(360, 100)  # RR = 0.6 s
    assert q["Bazett"] == pytest.approx(360 / math.sqrt(0.6))          # 464.8
    assert q["Fridericia"] == pytest.approx(360 / 0.6 ** (1 / 3))      # 426.8
    assert q["Framingham"] == pytest.approx(360 + 154 * 0.4)           # 421.6
    assert q["Hodges"] == pytest.approx(360 + 1.75 * 40)               # 430.0


@pytest.mark.parametrize("qtc,sex,level", [
    (420, "M", "normal"), (455, "M", "leve"), (455, "F", "normal"), (465, "F", "leve"),
    (450, "M", "leve"), (460, "F", "leve"), (510, "M", "severo"), (380, "F", "leve"),
])
def test_classify_qtc_thresholds(qtc, sex, level):
    assert c.classify_qtc(qtc, sex)[0] == level


def test_qtc_rejects_non_positive_inputs():
    with pytest.raises(ValueError):
        c.qtc_bazett(0, 1.0)
    with pytest.raises(ValueError):
        c.qtc_all(400, 0)


# ─── FC y eje ────────────────────────────────────────────────────────────

def test_heart_rate_from_paper_and_rr():
    assert c.hr_from_ecg_paper(large_squares=4) == pytest.approx(75)
    assert c.hr_from_ecg_paper(small_squares=20) == pytest.approx(75)
    assert c.hr_six_second_method(8) == pytest.approx(80)
    assert c.hr_from_rr_ms(800) == pytest.approx(75)
    assert [c.classify_heart_rate(h)[0] for h in (55, 72, 120)] == ["leve", "normal", "leve"]


@pytest.mark.parametrize("di,avf,deg,level", [
    (5, 5, 45, "normal"), (5, 0, 0, "normal"), (0, 5, 90, "normal"),
    (5, -5, -45, "leve"), (-5, 5, 135, "leve"), (-5, -5, -135, "severo"),
])
def test_qrs_axis(di, avf, deg, level):
    axis = c.qrs_axis_degrees(di, avf)
    assert axis == pytest.approx(deg)
    assert c.classify_qrs_axis(axis)[0] == level


def test_qrs_axis_undefined_when_both_zero():
    with pytest.raises(ValueError):
        c.qrs_axis_degrees(0, 0)


# ─── Hemodinamia ─────────────────────────────────────────────────────────

def test_map_pulse_pressure_and_shock_index():
    assert c.mean_arterial_pressure(120, 80) == pytest.approx(93.333, abs=1e-3)
    assert c.pulse_pressure(120, 80) == 40
    assert c.classify_map(64.9)[0] == "severo"
    assert c.classify_map(65)[0] == "normal"
    assert c.shock_index(120, 100) == pytest.approx(1.2)
    assert [c.classify_shock_index(v)[0] for v in (0.58, 0.85, 1.0)] == ["normal", "leve", "severo"]
    with pytest.raises(ValueError):
        c.mean_arterial_pressure(80, 120)


def test_cardiac_output_and_index():
    co = c.cardiac_output_l_min(70, 70)
    assert co == pytest.approx(4.9)
    assert c.cardiac_index(co, 2.0) == pytest.approx(2.45)
    assert [c.classify_cardiac_index(v)[0] for v in (2.1, 2.45, 3.0, 4.5)] == ["severo", "leve", "normal", "leve"]


# ─── Antropometría ───────────────────────────────────────────────────────

def test_bmi_and_who_categories():
    assert c.body_mass_index(70, 175) == pytest.approx(22.857, abs=1e-3)
    labels = [c.classify_bmi(b)[1] for b in (18.4, 18.5, 24.99, 25.0, 30.0, 35.0, 40.0)]
    assert labels[0].startswith("bajo peso")
    assert labels[1].startswith("peso normal") and labels[2].startswith("peso normal")
    assert labels[3].startswith("sobrepeso")
    assert "clase I " in labels[4] + " " and "clase II " in labels[5] + " " and "clase III" in labels[6]


def test_body_surface_area_formulas():
    assert c.bsa_mosteller(180, 80) == pytest.approx(2.0)
    assert c.bsa_mosteller(170, 70) == pytest.approx(1.818, abs=1e-3)
    assert c.bsa_dubois(170, 70) == pytest.approx(1.810, abs=2e-3)


# ─── Oxigenación ─────────────────────────────────────────────────────────

def test_barometric_pressure_and_alveolar_gas():
    assert c.barometric_pressure_mmhg(0) == pytest.approx(760.0)
    p_cdmx = c.barometric_pressure_mmhg(c.CITY_ALTITUDES_M["Ciudad de México"])
    assert p_cdmx == pytest.approx(578.7, abs=1.0)
    assert c.alveolar_po2(0.21, 40, 760) == pytest.approx(99.73, abs=0.01)
    assert c.aa_gradient(0.21, 90, 40, 760) == pytest.approx(9.73, abs=0.01)
    # En la Ciudad de México la PAO₂ en aire ambiente es mucho menor:
    assert c.alveolar_po2(0.21, 40, p_cdmx) == pytest.approx(0.21 * (p_cdmx - 47) - 50)
    assert c.expected_aa_gradient(40) == pytest.approx(14.0)


def test_fio2_must_be_a_fraction():
    with pytest.raises(ValueError):
        c.pf_ratio(80, 40)        # 40 % escrito como porcentaje
    with pytest.raises(ValueError):
        c.alveolar_po2(0.1, 40)


@pytest.mark.parametrize("pf,level,word", [
    (301, "normal", "fuera"), (300, "leve", "leve"), (201, "leve", "leve"),
    (200, "leve", "moderado"), (101, "leve", "moderado"), (100, "severo", "grave"),
])
def test_pf_ratio_berlin_bands(pf, level, word):
    lvl, label, _ = c.classify_pf_ratio(pf)
    assert lvl == level and word in label
    assert c.pf_ratio(80, 0.4) == pytest.approx(200)


# ─── NEWS2 ───────────────────────────────────────────────────────────────

_NORMAL = dict(respiratory_rate=16, spo2=98, on_oxygen=False, systolic_bp=120, pulse=72,
               alert=True, temperature_c=37.0)


def _news(**overrides):
    return c.news2_score(**{**_NORMAL, **overrides})


def test_news2_normal_patient_scores_zero():
    r = _news()
    assert r.total == 0 and r.risk == "bajo" and not r.any_single_3


def test_news2_single_red_parameter_is_low_medium():
    r = _news(respiratory_rate=7)
    assert r.total == 3 and r.any_single_3 and r.risk == "bajo-medio"


def test_news2_medium_and_high_bands():
    medium = _news(respiratory_rate=22, spo2=95, systolic_bp=105, pulse=95)   # 2+1+1+1
    assert medium.total == 5 and medium.risk == "medio"
    high = _news(respiratory_rate=26, spo2=90, on_oxygen=True, systolic_bp=85, pulse=135,
                 alert=False, temperature_c=34.5)                             # 3+3+2+3+3+3+3
    assert high.total == 20 and high.risk == "alto"


@pytest.mark.parametrize("field,value,points", [
    ("respiratory_rate", 8, 3), ("respiratory_rate", 9, 1), ("respiratory_rate", 11, 1),
    ("respiratory_rate", 12, 0), ("respiratory_rate", 20, 0), ("respiratory_rate", 21, 2),
    ("respiratory_rate", 24, 2), ("respiratory_rate", 25, 3),
    ("systolic_bp", 90, 3), ("systolic_bp", 91, 2), ("systolic_bp", 101, 1), ("systolic_bp", 111, 0),
    ("systolic_bp", 219, 0), ("systolic_bp", 220, 3),
    ("pulse", 40, 3), ("pulse", 41, 1), ("pulse", 50, 1), ("pulse", 51, 0), ("pulse", 90, 0),
    ("pulse", 91, 1), ("pulse", 110, 1), ("pulse", 111, 2), ("pulse", 130, 2), ("pulse", 131, 3),
    ("temperature_c", 35.0, 3), ("temperature_c", 35.1, 1), ("temperature_c", 36.0, 1),
    ("temperature_c", 36.1, 0), ("temperature_c", 38.0, 0), ("temperature_c", 38.1, 1),
    ("temperature_c", 39.0, 1), ("temperature_c", 39.1, 2),
    ("spo2", 91, 3), ("spo2", 92, 2), ("spo2", 93, 2), ("spo2", 94, 1), ("spo2", 95, 1), ("spo2", 96, 0),
])
def test_news2_band_edges(field, value, points):
    assert _news(**{field: value}).total == points


@pytest.mark.parametrize("spo2,on_o2,points", [
    (83, False, 3), (84, False, 2), (85, False, 2), (86, False, 1), (87, False, 1), (88, False, 0),
    (92, False, 0), (93, False, 0), (99, False, 0),
    (93, True, 1 + 2), (94, True, 1 + 2), (95, True, 2 + 2), (96, True, 2 + 2), (97, True, 3 + 2),
])
def test_news2_spo2_scale_2(spo2, on_o2, points):
    assert _news(spo2=spo2, on_oxygen=on_o2, spo2_scale=2).total == points


# ─── qSOFA y Glasgow ─────────────────────────────────────────────────────

def test_qsofa():
    assert c.qsofa_score(respiratory_rate=22, systolic_bp=100, altered_mentation=True) == 3
    assert c.qsofa_score(respiratory_rate=21, systolic_bp=101, altered_mentation=False) == 0
    assert c.classify_qsofa(2)[0] == "severo" and c.classify_qsofa(1)[0] == "normal"


def test_glasgow():
    assert c.glasgow_coma_scale(4, 5, 6) == 15
    assert c.classify_gcs(15)[0] == "normal"
    assert "leve" in c.classify_gcs(c.glasgow_coma_scale(3, 4, 6))[1]
    assert "moderada" in c.classify_gcs(c.glasgow_coma_scale(2, 3, 4))[1]
    assert c.classify_gcs(c.glasgow_coma_scale(1, 1, 1))[0] == "severo"
    with pytest.raises(ValueError):
        c.glasgow_coma_scale(5, 5, 6)


def test_every_unavailable_classification_is_neutral():
    for fn in (c.classify_qtc, ):
        assert fn(None, "M")[0] == "no_disponible"
    for fn in (c.classify_heart_rate, c.classify_qrs_axis, c.classify_map, c.classify_shock_index,
               c.classify_cardiac_index, c.classify_bmi, c.classify_pf_ratio, c.classify_news2,
               c.classify_qsofa, c.classify_gcs):
        assert fn(None) == ("no_disponible", "no disponible", "")
