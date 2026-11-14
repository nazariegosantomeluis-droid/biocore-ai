"""Frente cardiovascular, Fase 1, PARTE C (2026-11-12, Art. I): PredictionEngine sin defaults.

Decisión 4: el riesgo cardiovascular son los puntos NEWS2 del pulso; se purgan 40/140, 50/120, HRV 10/25 y
complexity < 30. Decisión 5: un sistema sin señal es «sin dato», nunca «rutinario». Cierre de la fase 0 (2026-11-13):
también se retiraron los umbrales no cardiacos y el riesgo global numérico (ver tests/test_fase0_globales.py).
"""

import re
from pathlib import Path

import pytest

from app.engines.digital_twin_organism import NO_DATA, DigitalTwinOrganism
from app.engines.prediction_engine import NO_SOURCED_CRITERION, PredictionEngine


def _sensor_data(organism):
    """Lo que la página le pasa al motor: solo las señales ACTUALES de cada órgano."""
    return {
        "ecg": organism.current_signals("heart"), "respiratory": organism.current_signals("lungs"),
        "eeg": organism.current_signals("brain"), "emg": organism.current_signals("muscles"),
    }


def _assess(organism):
    return PredictionEngine().assess_global_risk(organism, _sensor_data(organism), organism.timestamp.isoformat())


def test_a_respiratory_only_organism_has_no_cardiovascular_risk_and_no_ratio():
    organism = DigitalTwinOrganism()
    organism.update_from_sensors({"respiratory": {"respiratory_rate": 14.0, "spo2": 97.0}})
    assessment = _assess(organism)
    cardio = assessment.system_risks["cardiovascular"]
    assert cardio.risk_level == NO_DATA and not cardio.has_data and cardio.news2_points == {}
    assert "rutinario" not in cardio.recommendation.lower() and "BAJO" not in cardio.recommendation
    assert assessment.system_risks["respiratory"].news2_points == {"Frecuencia respiratoria": 0, "SpO₂ (escala 1)": 0}
    assert assessment.system_risks["autonomic"].risk_level == NO_DATA              # sin HRV: no «balance adecuado»
    # el riesgo global ya no es un número: NEWS2 parcial sin total
    assert not hasattr(assessment, "global_risk_score")
    assert assessment.news2_partial.components == {"Frecuencia respiratoria": 0, "SpO₂ (escala 1)": 0}
    assert "pulso" in assessment.news2_partial.missing and "sin total" in assessment.reason
    assert organism.global_state["hr_rr_ratio"] is None


def test_cardiovascular_risk_is_the_news2_pulse_points_with_no_home_made_thresholds():
    engine = PredictionEngine()
    expected = {35: 3, 40: 3, 41: 1, 50: 1, 51: 0, 72: 0, 90: 0, 91: 1, 110: 1, 111: 2, 130: 2, 131: 3, 138: 3, 150: 3}
    for hr, points in expected.items():
        risk = engine.assess_cardiovascular_risk({"heart_rate": float(hr)})
        assert risk.news2_points == {"Pulso": points}, hr
        assert risk.risk_level == f"NEWS2 pulso: {points} punto(s)"
    # HRV, complejidad y el resto ya no entran: solo la FC
    only_hrv = engine.assess_cardiovascular_risk({"hrv": 5.0, "complexity": 10})
    assert only_hrv.risk_level == NO_DATA
    assert engine.assess_cardiovascular_risk({"heart_rate": 72.0, "hrv": 5.0, "complexity": 10}).news2_points == {"Pulso": 0}


def test_a_system_without_a_signal_is_no_data_never_routine():
    engine = PredictionEngine()
    for assess in (engine.assess_respiratory_risk, engine.assess_neurological_risk, engine.assess_muscular_risk,
                   engine.assess_cardiovascular_risk):
        risk = assess({})
        assert risk.risk_level == NO_DATA and not risk.has_data and risk.key_factors == []
        assert "rutinario" not in risk.recommendation.lower() and "adecuad" not in risk.recommendation.lower()
    assessment = _assess(DigitalTwinOrganism())
    assert all(not r.has_data for r in assessment.system_risks.values())
    assert not assessment.news2_partial.available and assessment.reason.startswith(NO_DATA)


def test_systems_without_a_sourced_criterion_say_so_even_with_inputs():
    engine = PredictionEngine()
    assert engine.assess_neurological_risk({"stress_level": 85.0}).risk_level == NO_SOURCED_CRITERION
    assert engine.assess_muscular_risk({"fatigue_index": 85.0}).risk_level == NO_SOURCED_CRITERION
    organism = DigitalTwinOrganism()
    organism.update_from_sensors({"ecg": {"heart_rate": 72.0, "hrv": 8.0}})
    assert engine.assess_autonomic_risk(organism).risk_level == NO_SOURCED_CRITERION     # HRV 8 ya no es «ALTO»


def test_an_old_input_is_not_assessed():
    organism = DigitalTwinOrganism()
    organism.update_from_sensors({"ecg": {"heart_rate": 150.0, "hrv": 8.0}})
    organism.update_from_sensors({"respiratory": {"respiratory_rate": 16.0, "spo2": 98.0}})
    assessment = _assess(organism)
    assert assessment.system_risks["cardiovascular"].risk_level == NO_DATA             # la FC 150 es de una actualización vieja
    assert assessment.system_risks["autonomic"].risk_level == NO_DATA
    assert "Pulso" not in assessment.news2_partial.components


# ----------------------------------------------------------------------------------------------- grep final
FORBIDDEN = (
    r"""get\(\s*["']heart_rate["']\s*,\s*\d""", r"""get\(\s*["']hrv["']\s*,\s*\d""", r"""get\(\s*["']complexity["']""",
    r"hr\s*>\s*120", r"hr\s*<\s*40", r"hr\s*>\s*140", r"hr\s*<\s*50", r"hrv\s*<\s*20", r"hrv\s*<\s*10", r"hrv\s*<\s*25",
    r"complexity\s*<\s*30", r"hr\s*=\s*70\b", r"hrv\s*=\s*50\b", r"complexity\s*=\s*50\b", r"cardiac_output_low",
    # fase 0: defaults y umbrales caseros no cardiacos
    r"""get\(\s*["'](ahi|respiratory_rate|spo2|stress_level|relaxation_level|efficiency|fatigue_index|activation|alpha_power|beta_power)["']\s*,\s*\d""",
    r"ahi\s*=\s*0\b", r"relaxation\s*=\s*65", r"stress\w*\s*=\s*35\b", r"efficiency\s*=\s*70", r"fatigue\w*\s*=\s*20\b",
    r"spo2\s*<\s*9\d", r"rr\s*[<>]\s*\d", r"ahi\s*>\s*\d", r"stress_level\s*>\s*[68]0", r"cognitive_state\s*<\s*\d",
    r"fatigue\s*>\s*[68]0", r"efficiency\s*<\s*\d", r"activation\s*>\s*90", r"hrv\s*<\s*(15|30)\b",
)


@pytest.mark.parametrize("path", ["app/engines/digital_twin_organism.py", "app/engines/prediction_engine.py"])
def test_no_default_inputs_or_home_made_thresholds_remain(path):
    source = Path(path).read_text(encoding="utf-8")
    code = "\n".join(line for line in source.splitlines() if not line.lstrip().startswith("#"))
    # los docstrings que EXPLICAN lo purgado pueden nombrarlo; el código ejecutable no
    code = re.sub(r'"""[\s\S]*?"""', "", code)
    for pattern in FORBIDDEN:
        assert not re.search(pattern, code), (path, pattern)


def test_predict_physiological_events_and_decompensation_risk_are_buried():
    assert not hasattr(DigitalTwinOrganism, "predict_physiological_events")
    assert not hasattr(PredictionEngine, "predict_decompensation_risk")
    for root in ("app", "domain", "src", "clinical", "visualization", "tests"):
        for p in Path(root).rglob("*.py"):
            if p.name == "test_prediction_engine_phase1.py":
                continue
            text = p.read_text(encoding="utf-8")
            assert "predict_physiological_events" not in text and "predict_decompensation_risk" not in text, p
