"""Frente cardiovascular, Fase 1, PARTE C (2026-11-12, Art. I): PredictionEngine e índices globales sin defaults.

Decisión 4: el riesgo cardiovascular son los puntos NEWS2 del pulso; se purgan 40/140, 50/120, HRV 10/25 y
complexity < 30. Decisión 5: un sistema sin señal es «sin dato», nunca «rutinario».
"""

import re
from pathlib import Path

import pytest

from app.engines.digital_twin_organism import NO_DATA, DigitalTwinOrganism
from app.engines.prediction_engine import PredictionEngine


def _sensor_data(organism):
    """Lo que la página le pasa al motor: solo las señales ACTUALES de cada órgano."""
    return {
        "ecg": organism.current_signals("heart"), "respiratory": organism.current_signals("lungs"),
        "eeg": organism.current_signals("brain"), "emg": organism.current_signals("muscles"),
    }


def _assess(organism):
    return PredictionEngine().assess_global_risk(organism, _sensor_data(organism), organism.timestamp.isoformat())


def test_a_respiratory_only_organism_has_no_cardiovascular_risk_and_no_couplings():
    organism = DigitalTwinOrganism()
    organism.update_from_sensors({"respiratory": {"respiratory_rate": 14.0, "spo2": 97.0}})
    assessment = _assess(organism)
    cardio = assessment.system_risks["cardiovascular"]
    assert cardio.risk_level == NO_DATA and cardio.risk_score is None and cardio.news2_points is None
    assert "rutinario" not in cardio.recommendation.lower() and "BAJO" not in cardio.recommendation
    assert assessment.system_risks["respiratory"].has_data
    assert assessment.system_risks["autonomic"].risk_level == NO_DATA              # sin HRV ni cerebro: no «balance adecuado»
    # ningún índice global con número si falta un órgano del que depende
    assert assessment.global_risk_score is None and assessment.risk_level == NO_DATA
    assert assessment.monitoring_frequency == NO_DATA and "sin dato en" in assessment.reason
    g = organism.global_state
    assert g["cardiorespiratory_coupling"] is None and g["neurocardiac_coupling"] is None
    assert g["global_health_score"] is None and g["global_risk_score"] is None and g["risk_level"] == NO_DATA


def test_cardiovascular_risk_is_the_news2_pulse_points_with_no_home_made_thresholds():
    engine = PredictionEngine()
    expected = {35: 3, 40: 3, 41: 1, 50: 1, 51: 0, 72: 0, 90: 0, 91: 1, 110: 1, 111: 2, 130: 2, 131: 3, 138: 3, 150: 3}
    for hr, points in expected.items():
        risk = engine.assess_cardiovascular_risk({"heart_rate": float(hr)})
        assert risk.news2_points == points, hr
        assert risk.risk_score is None and risk.risk_level == f"NEWS2 pulso: {points} punto(s)"
    # HRV, complejidad y el resto ya no entran: solo la FC
    only_hrv = engine.assess_cardiovascular_risk({"hrv": 5.0, "complexity": 10})
    assert only_hrv.risk_level == NO_DATA
    assert engine.assess_cardiovascular_risk({"heart_rate": 72.0, "hrv": 5.0, "complexity": 10}).news2_points == 0


def test_a_system_without_a_signal_is_no_data_never_routine():
    engine = PredictionEngine()
    for assess in (engine.assess_respiratory_risk, engine.assess_neurological_risk, engine.assess_muscular_risk,
                   engine.assess_cardiovascular_risk):
        risk = assess({})
        assert risk.risk_level == NO_DATA and risk.risk_score is None and risk.key_factors == []
        assert "rutinario" not in risk.recommendation.lower() and "adecuad" not in risk.recommendation.lower()
    assessment = _assess(DigitalTwinOrganism())
    assert all(not r.has_data for r in assessment.system_risks.values())
    assert assessment.global_risk_score is None and assessment.risk_level == NO_DATA


def test_each_factor_needs_its_own_input_instead_of_a_default():
    engine = PredictionEngine()
    only_spo2 = engine.assess_respiratory_risk({"spo2": 98.0})
    assert only_spo2.risk_score == 0 and only_spo2.risk_level == "BAJO"           # evaluó solo lo que llegó
    assert engine.assess_respiratory_risk({"spo2": 88.0}).risk_level == "ALTO"     # hipoxemia severa 50
    assert engine.assess_respiratory_risk({"respiratory_rate": 40.0}).risk_score == 35
    assert engine.assess_muscular_risk({"fatigue_index": 85.0}).risk_score == 40
    assert engine.assess_neurological_risk({"stress_level": 85.0}).risk_score == 35


def test_the_global_risk_is_not_an_average_of_different_scales_or_of_missing_systems():
    organism = DigitalTwinOrganism()
    organism.update_from_sensors({
        "ecg": {"heart_rate": 72.0, "hrv": 40.0}, "respiratory": {"respiratory_rate": 16.0, "spo2": 98.0, "ahi": 1.0},
        "eeg": {"stress_level": 30.0, "relaxation_level": 60.0, "alpha_power": 40.0},
        "emg": {"fatigue_index": 20.0, "efficiency": 80.0},
    })
    assessment = _assess(organism)
    assert all(r.has_data for r in assessment.system_risks.values())                  # los 5 sistemas tienen datos...
    assert assessment.global_risk_score is None                                        # ...pero el cardio está en puntos NEWS2
    assert "escala distinta" in assessment.reason and "cardiovascular" in assessment.reason
    assert assessment.risk_level == NO_DATA
    assert PredictionEngine().predict_decompensation_risk(organism) is None            # sin dos riesgos globales reales


def test_an_old_input_is_not_assessed():
    organism = DigitalTwinOrganism()
    organism.update_from_sensors({"ecg": {"heart_rate": 150.0, "hrv": 8.0}})
    organism.update_from_sensors({"respiratory": {"respiratory_rate": 16.0, "spo2": 98.0}})
    assessment = _assess(organism)
    assert assessment.system_risks["cardiovascular"].risk_level == NO_DATA             # la FC 150 es de una actualización vieja
    assert assessment.system_risks["autonomic"].risk_level == NO_DATA


# ----------------------------------------------------------------------------------------------- grep final
FORBIDDEN = (
    r"""get\(\s*["']heart_rate["']\s*,\s*\d""", r"""get\(\s*["']hrv["']\s*,\s*\d""", r"""get\(\s*["']complexity["']""",
    r"hr\s*>\s*120", r"hr\s*<\s*40", r"hr\s*>\s*140", r"hr\s*<\s*50", r"hrv\s*<\s*20", r"hrv\s*<\s*10", r"hrv\s*<\s*25",
    r"complexity\s*<\s*30", r"hr\s*=\s*70\b", r"hrv\s*=\s*50\b", r"complexity\s*=\s*50\b", r"cardiac_output_low",
)


@pytest.mark.parametrize("path", ["app/engines/digital_twin_organism.py", "app/engines/prediction_engine.py"])
def test_no_default_cardiac_inputs_or_home_made_thresholds_remain(path):
    source = Path(path).read_text(encoding="utf-8")
    code = "\n".join(line for line in source.splitlines() if not line.lstrip().startswith("#"))
    # los docstrings que EXPLICAN lo purgado pueden nombrarlo; el código ejecutable no
    code = re.sub(r'"""[\s\S]*?"""', "", code)
    for pattern in FORBIDDEN:
        assert not re.search(pattern, code), (path, pattern)


def test_predict_physiological_events_is_buried_and_had_no_callers():
    assert not hasattr(DigitalTwinOrganism, "predict_physiological_events")
    for root in ("app", "domain", "src", "clinical", "visualization", "tests"):
        for p in Path(root).rglob("*.py"):
            if p.name == "test_prediction_engine_phase1.py":
                continue
            assert "predict_physiological_events" not in p.read_text(encoding="utf-8"), p
