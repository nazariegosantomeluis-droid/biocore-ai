"""Frente cardiovascular, Fase 1, PARTE B (2026-11-12, Art. I): el organismo cardiaco no calcula con defaults.

Decisiones firmadas: (1) sin health_score cardiaco ni myocardial_stress; (2) sin complexity ni rhythm_stability;
(3) cardiac_output «no modelado»; (4) el riesgo cardiaco son los puntos NEWS2 del pulso; (7) CardiacDetail eliminado.
Cierre de la fase 0 (2026-11-13): los índices globales (salud, riesgo numérico, coherencia, resiliencia, acoplamientos
Cerebro↔Corazón/Cerebro↔Músculos) y los estados transversales se retiraron; ver tests/test_fase0_*.py.
"""

import json
import re
from datetime import timedelta

import pytest

from app.engines import digital_twin_organism as dto
from app.engines.digital_twin_organism import NO_DATA, NOT_MODELED, DigitalTwinOrganism
from domain.physiology.state import Provenance, from_digital_twin_organism


def _heart(sensors):
    organism = DigitalTwinOrganism()
    organism.update_from_sensors(sensors)
    return organism, organism.organs["heart"]


# ------------------------------------------------------------------------------------------ sin datos
def test_an_organism_without_data_shows_no_data_for_the_whole_heart_and_no_number_anywhere():
    organism = DigitalTwinOrganism()
    heart = organism.organs["heart"]
    m = heart.metrics
    assert (m.health_score, m.risk_points, m.rr_points, m.spo2_points) == (None, None, None, None)
    assert m.signals == {} and heart.status is None
    assert heart.color == dto.NO_DATA_COLOR == "#64748b"                      # el gris del Cuerpo Digital
    # tras una actualización vacía (nadie midió nada) sigue sin número: ni 50, ni «BAJO», ni un total NEWS2
    organism.update_from_sensors({})
    g = organism.global_state
    assert not g["news2_partial"].available and g["hr_rr_ratio"] is None
    assert g["alerts"] == [] and g["anomalies"] == []
    for key in ("global_health_score", "global_risk_score", "system_coherence", "resilience_index", "risk_level",
                "neurocardiac_coupling", "cardiorespiratory_coupling", "neuromuscular_coupling"):
        assert key not in g, key                                              # retirados (fase 0, decisión 1)
    for organ in organism.organs.values():
        assert organ.metrics.health_score is None and organ.status is None and organ.color == dto.NO_DATA_COLOR


def test_the_summary_and_the_json_of_an_unfed_organism_have_no_cardiac_number():
    organism = DigitalTwinOrganism()
    summary = organism.generate_clinical_summary()
    cardio = summary.split("🫀 SISTEMA CARDIOVASCULAR:")[1].split("🧠")[0]
    assert not re.search(r"\d", cardio.replace("NEWS2", "")), cardio          # ningún número en el bloque cardiaco
    assert f"Frecuencia Cardíaca: {NO_DATA}" in cardio and f"Gasto Cardíaco: {NOT_MODELED}" in cardio
    assert "0.0 bpm" not in summary and "5.0 L/min" not in summary
    assert organism.explain_state().count(NO_DATA) == 2                        # NEWS2 parcial y razón FC:FR
    exported = json.loads(organism.to_json())
    assert exported["organs"]["heart"] == {"signals": {}, "news2_pulse_points": NO_DATA, "cardiac_output": NOT_MODELED}
    assert exported["global_state"]["news2_partial"]["components"] == NO_DATA
    assert exported["global_state"]["news2_partial"]["total"].startswith("nunca")


# --------------------------------------------------------------------------------------------- solo FC
def test_heart_rate_only_gives_the_news2_points_and_nothing_else():
    organism, heart = _heart({"ecg": {"heart_rate": 72.0}})
    m = heart.metrics
    assert m.risk_points == 0 and m.health_score is None
    assert m.signals == {"heart_rate": 72.0}                                   # ni hrv_modulation ni defaults
    assert heart.color == "#39ffbe"
    # sin pulmones no hay razón FC:FR (ya no sale de FR = 16 por defecto) y el NEWS2 parcial solo tiene el pulso
    assert organism.global_state["hr_rr_ratio"] is None
    assert organism.global_state["news2_partial"].components == {"Pulso": 0}


@pytest.mark.parametrize("hr, points", [
    (40, 3), (40.4, 3), (40.5, 1), (41, 1), (50, 1), (50.4, 1), (50.5, 0), (51, 0), (90, 0), (90.4, 0), (90.5, 1),
    (91, 1), (110, 1), (110.4, 1), (110.5, 2), (111, 2), (130, 2), (130.4, 2), (130.5, 3), (131, 3),
])
def test_the_organism_uses_the_news2_pulse_bands_with_half_up_rounding(hr, points):
    _, heart = _heart({"ecg": {"heart_rate": float(hr)}})
    assert heart.metrics.risk_points == points


def test_atrial_fibrillation_at_138_bpm_is_3_points_not_healthy():
    organism, heart = _heart({"ecg": {"heart_rate": 138.0}})
    assert heart.metrics.risk_points == 3 and heart.color == "#ff3333"
    assert heart.status is None                                                # ya no existe el «Óptimo» por FC 138
    assert any("3 puntos NEWS2" in a for a in organism.global_state["alerts"])
    assert any("3 puntos NEWS2" in a for a in organism.global_state["anomalies"])


@pytest.mark.parametrize("hr", [40, 150, 35])
def test_the_old_home_made_health_score_that_saturated_at_100_is_gone(hr):
    _, heart = _heart({"ecg": {"heart_rate": float(hr), "hrv": 20.0}})
    assert heart.metrics.health_score is None


def test_hrv_alone_does_not_invent_a_heart_rate_or_a_risk():
    _, heart = _heart({"ecg": {"hrv": 15.0}})                                   # antes: hr = 70 por defecto, riesgo 50
    assert heart.metrics.risk_points is None
    assert heart.metrics.signals == {"hrv": 15.0}


# ------------------------------------------------------------------- CardiacDetail / retirados / propagación
def test_cardiac_detail_and_the_retired_fields_are_gone_from_the_module():
    for gone in ("CardiacDetail", "NeurologicalDetail", "RespiratoryDetail", "MusculoskeletalDetail", "AutonomicDetail",
                 "StressState", "RecoveryState", "PerformanceState"):
        assert not hasattr(dto, gone), gone
    organism = DigitalTwinOrganism()
    assert not hasattr(organism.organs["heart"], "detail") and not hasattr(organism, "derived_signals")
    source = open(dto.__file__, encoding="utf-8").read()
    for retired in ("rhythm_stability", "myocardial_stress", "complexity", "risk_score", "activity_level"):
        assert not re.search(rf"\b{retired}\b\s*[:=]", source), retired        # ningún campo ni asignación
    exported = json.loads(organism.to_json())
    assert "rhythm_stability" not in json.dumps(exported) and exported["organs"]["heart"]["cardiac_output"] == NOT_MODELED


def test_propagation_no_longer_injects_derived_keys_into_signals():
    organism = DigitalTwinOrganism()
    organism.update_from_sensors({
        "ecg": {"heart_rate": 72.0, "hrv": 50.0},
        "eeg": {"stress_level": 35.0, "alpha_power": 50.0},
        "respiratory": {"respiratory_rate": 16.0, "spo2": 98.0},
        "emg": {"fatigue_index": 20.0, "efficiency": 80.0},
    })
    for organ_id in ("heart", "lungs", "autonomic", "brain", "muscles"):
        keys = set(organism.organs[organ_id].metrics.signals)
        assert not ({"hrv_modulation", "rr_modulation", "recovery_need"} & keys), (organ_id, keys)
    assert organism.organs["heart"].metrics.signals == {"heart_rate": 72.0, "hrv": 50.0}      # exactamente lo que llegó
    assert organism.organs["autonomic"].metrics.signals == {"hrv": 50.0}                       # la HRV como HRV


# --------------------------------------------------------------------------------- entradas viejas (organismo)
def test_an_old_input_does_not_count_for_the_ratio_or_the_autonomic_view():
    organism = DigitalTwinOrganism()
    organism.update_from_sensors({"ecg": {"heart_rate": 72.0, "hrv": 50.0}})
    organism.update_from_sensors({"respiratory": {"respiratory_rate": 16.0, "spo2": 98.0}})
    assert organism.inputs_are_current("lungs") and not organism.inputs_are_current("heart")
    g = organism.global_state
    assert g["hr_rr_ratio"] is None                                             # el corazón ya no es una entrada actual
    assert "Pulso" not in g["news2_partial"].components and "pulso" in g["news2_partial"].missing
    assert not organism.inputs_are_current("autonomic")                        # la HRV vieja no es actual
    # al llegar ambos en la misma actualización, la razón existe y sale de entradas reales
    organism.update_from_sensors({"ecg": {"heart_rate": 64.0}, "respiratory": {"respiratory_rate": 16.0}})
    assert organism.global_state["hr_rr_ratio"] == pytest.approx(4.0)                      # 64/16 = 4:1 exacto


def test_the_gate_beyond_which_an_old_input_does_not_exist_is_the_compositors():
    organism = DigitalTwinOrganism()
    organism.update_from_sensors({"ecg": {"heart_rate": 150.0}})
    organism.update_from_sensors({"respiratory": {"respiratory_rate": 16.0, "spo2": 98.0}})
    organism.organs["heart"].metrics.signals_at -= timedelta(seconds=121)
    state = from_digital_twin_organism(organism, "p", provenance=Provenance.SIMULACION)
    assert state.cardiovascular.descriptors == {} and state.respiratory.get("spo2") is not None


# ------------------------------------------------------------------------------------- sepsis / gasto cardiaco
def test_sepsis_cardiac_output_is_not_modeled_the_engine_value_is_not_shown_or_written():
    from app.engines.simulation_engine import SimulationEngine, SimulationScenario

    engine_co = [s.cardiac_output for s in SimulationEngine(seed=0).simulate_scenario(SimulationScenario.SEPSIS)]
    assert engine_co[0] == pytest.approx(4.0) and engine_co[-1] == pytest.approx(2.0)     # el motor de escenarios: 4.0 → 2.0
    organism = DigitalTwinOrganism()
    organism.apply_sepsis("7d")
    summary = organism.generate_clinical_summary()
    assert f"Gasto Cardíaco: {NOT_MODELED}" in summary                           # el motor de escenarios NO es svZeroD
    assert "4.0 L/min" not in summary and "2.0 L/min" not in summary and "5.0 L/min" not in summary
    assert "cardiac_output" not in from_digital_twin_organism(organism, "p").cardiovascular.descriptors
    assert organism.organs["heart"].metrics.risk_points == 3                      # sepsis tardía: FC 150
    assert organism.input_provenance.startswith("simulación")
