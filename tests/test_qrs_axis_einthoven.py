"""
Eje QRS de `TwelveLeadEcgAnalyzer._determine_qrs_axis` contra verdad de
referencia INDEPENDIENTE (2026-10-22).

Ningún esperado sale de la función bajo prueba ni de una arcotangente sobre
I/aVF (esa circularidad es la que ocultó `atan2(aVF, I)`). Las tres fuentes
de verdad:

1. Un vector cardíaco de ángulo conocido: las derivaciones salen de la
   física (proyección sobre los ejes de I y II, Einthoven) y aVF como lo
   deriva un electrocardiógrafo (Goldberger: aVF = II − I/2). El esperado es
   el ángulo con que se construyó el vector.
2. La regla clínica de la derivación isoeléctrica: el eje es perpendicular a
   la derivación con área neta cero, hacia el lado positivo de la otra.
3. La regla clínica de los signos de I, II y aVF (sin ningún ángulo).
"""

from __future__ import annotations

import numpy as np
import pytest

from src.signals.ecg.twelve_lead_analyzer import TwelveLeadEcgAnalyzer

FS = 500
T = np.arange(0, 1.0, 1 / FS)
R = np.exp(-((T - 0.30) / 0.012) ** 2)                                     # R positiva, área > 0
W = np.exp(-((T - 0.28) / 0.01) ** 2) - np.exp(-((T - 0.32) / 0.01) ** 2)  # bifásica, área 0


def _from_vector(theta_deg):
    """I, II, aVF de un QRS cuyo vector instantáneo gira (no es una sola
    forma escalada) pero cuyo vector MEDIO apunta exactamente a theta_deg."""
    th = np.radians(theta_deg)
    hx = R * np.cos(th) - 0.6 * W * np.sin(th)   # izquierda (+) del paciente
    hy = R * np.sin(th) + 0.6 * W * np.cos(th)   # inferior (+)
    lead_i = hx                                  # eje de I: 0°
    lead_ii = hx * 0.5 + hy * np.sqrt(3) / 2     # eje de II: +60°
    return lead_i, lead_ii, lead_ii - lead_i / 2


def _from_amplitudes(a_i, a_ii):
    """Derivaciones con área neta dada en I y II (aVF por Goldberger)."""
    return R * a_i, R * a_ii, R * (a_ii - a_i / 2)


def _axis(lead_i, lead_ii, avf):
    return TwelveLeadEcgAnalyzer()._determine_qrs_axis(lead_i, avf, lead_ii)


def _three_lead_rule(lead_i, lead_ii, avf):
    """Clasificación de cabecera por signos del área neta, sin ángulos:
    I+ aVF+ normal; I+ aVF− II+ normal (0° a −30°); I+ aVF− II− izquierda;
    I− aVF+ derecha; I− aVF− extrema."""
    i, ii, f = np.mean(lead_i), np.mean(lead_ii), np.mean(avf)
    if i > 0:
        return "Normal" if (f >= 0 or ii > 0) else "LAD"
    return "RAD" if f > 0 else "Extreme"


def _wrap(d):
    return (d + 180.0) % 360.0 - 180.0


# --- 1. Casos canónicos ----------------------------------------------------

@pytest.mark.parametrize("theta, category", [
    (60, "Normal"), (0, "Normal"), (-45, "LAD"), (120, "RAD"), (-135, "Extreme"),
])
def test_canonical_axes(theta, category):
    leads = _from_vector(theta)
    axis = _axis(*leads)
    assert abs(_wrap(axis.axis_degrees - theta)) < 0.01
    assert axis.category == category == _three_lead_rule(*leads)


# --- 2. El caso que la fórmula vieja clasificaba mal -------------------------

@pytest.mark.parametrize("theta", [-30.5, -31.0, -32.0, -33.0, -33.5])
def test_mild_left_axis_deviation_is_no_longer_called_normal(theta):
    lead_i, lead_ii, avf = _from_vector(theta)
    old = np.degrees(np.arctan2(np.mean(avf), np.mean(lead_i)))  # la fórmula del bug, solo como testigo
    assert old > -30, "este caso discrimina: con atan2(aVF, I) salía normal"
    assert np.mean(lead_ii) < 0, "II negativa con I positiva: desviación izquierda por definición"

    axis = _axis(lead_i, lead_ii, avf)
    assert axis.category == "LAD"
    assert abs(axis.axis_degrees - theta) < 0.01


# --- 3. Fronteras de las zonas -----------------------------------------------

@pytest.mark.parametrize("theta, category", [
    (-29.5, "Normal"), (-30.5, "LAD"),
    (89.5, "Normal"), (90.5, "RAD"),
    (-89.5, "LAD"), (-90.5, "Extreme"),
    (179.5, "RAD"), (-179.5, "Extreme"),
])
def test_zone_boundaries(theta, category):
    leads = _from_vector(theta)
    assert _axis(*leads).category == category == _three_lead_rule(*leads)


@pytest.mark.parametrize("name, a_i, a_ii, expected", [
    ("II isoeléctrica, I positiva", 1.0, 0.0, -30.0),     # eje de II +60° -> perpendicular -30°
    ("aVF isoeléctrica, I positiva", 1.0, 0.5, 0.0),      # aVF = II - I/2 = 0
    ("III isoeléctrica, I positiva", 1.0, 1.0, 30.0),     # III = II - I = 0; eje de III +120°
    ("aVL isoeléctrica, II positiva", 1.0, 2.0, 60.0),    # aVL = I - II/2 = 0; eje de aVL -30°
    ("I isoeléctrica, aVF positiva", 0.0, 1.0, 90.0),
    ("aVR isoeléctrica, III positiva", -1.0, 1.0, 120.0),  # aVR = -(I+II)/2 = 0; eje de aVR -150°
    ("I isoeléctrica, aVF negativa", 0.0, -1.0, -90.0),
])
def test_isoelectric_lead_rule(name, a_i, a_ii, expected):
    axis = _axis(*_from_amplitudes(a_i, a_ii))
    assert abs(axis.axis_degrees - expected) < 1e-6, name


def test_avl_isoelectric_is_exactly_plus_60_not_56():
    """El clásico de libro: aVL isoeléctrica -> +60°. La fórmula vieja daba 56°."""
    lead_i, lead_ii, avf = _from_amplitudes(1.0, 2.0)
    assert round(np.degrees(np.arctan2(np.mean(avf), np.mean(lead_i)))) == 56
    assert round(_axis(lead_i, lead_ii, avf).axis_degrees) == 60


# --- 4. Barrido completo contra la regla de los signos ----------------------

def test_every_half_degree_matches_the_three_lead_rule():
    for theta in np.arange(-179.5, 180.0, 1.0):
        leads = _from_vector(theta)
        axis = _axis(*leads)
        assert abs(_wrap(axis.axis_degrees - theta)) < 0.01, theta
        assert axis.category == _three_lead_rule(*leads), theta


# --- 5. Lo que ve el usuario: el análisis completo ---------------------------

def test_full_analysis_reports_lad_and_its_differentials_at_minus_32():
    lead_i, lead_ii, avf = _from_vector(-32.0)
    lead_iii = lead_ii - lead_i
    signals = {
        "time": T, "I": lead_i, "II": lead_ii, "III": lead_iii,
        "aVR": -(lead_i + lead_ii) / 2, "aVL": lead_i - lead_ii / 2, "aVF": avf,
        **{f"V{k}": R * (k - 3) / 3 for k in range(1, 7)},
    }
    interp = TwelveLeadEcgAnalyzer().analyze_12lead(signals)
    assert interp.qrs_axis.category == "LAD"
    assert interp.qrs_axis.description == "Left Axis Deviation: -32°"
    assert "Left anterior fascicular block" in interp.differential_diagnoses


def test_extreme_axis_gets_no_left_axis_differentials():
    leads = _from_vector(-135.0)
    interp_axis = _axis(*leads)
    assert interp_axis.category == "Extreme"
    diffs = TwelveLeadEcgAnalyzer()._generate_differential_diagnoses([], [], interp_axis)
    assert "Left anterior fascicular block" not in diffs


def test_missing_leads_still_unknown():
    assert TwelveLeadEcgAnalyzer()._determine_qrs_axis(None, None, None).category == "Unknown"
