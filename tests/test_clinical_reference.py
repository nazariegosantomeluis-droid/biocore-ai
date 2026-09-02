"""
Presión arterial, Paso 1+2 (2026-07-18) — `ClinicalReferenceValue` y su
persistencia, la tabla de datos transcritos, y la conexión con
`run_rich_scenario()` + el modelo de riesgo real.
"""

import dataclasses

import pytest
import sqlalchemy.exc

from app.engines.digital_twin_organism import DigitalTwinOrganism
from app.engines.simulation_engine import SimulationScenario
from domain.physiology.state import (
    BLOOD_PRESSURE_REFERENCES,
    ClinicalReferenceValue,
    Provenance,
    create_clinical_reference,
    create_patient,
    estimate_map,
    from_digital_twin_organism,
    get_clinical_references_for_patient,
    get_clinical_references_for_snapshot,
    init_db,
    make_engine,
    make_session_factory,
    save_state,
)
from domain.physiology.scenarios.rich_engine import create_ephemeral_basal_patient, run_rich_scenario
from domain.physiology.ml.risk_context import build_risk_features
from src.ai.patient_analytics import PatientRiskPredictor


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "clinical_reference_test.db"


def _session_factory(path):
    engine = make_engine(path)
    init_db(engine)
    return make_session_factory(engine)


# --- Validación estructural del tipo -----------------------------------------

def test_reference_value_has_no_provenance_or_confidence_field():
    field_names = {f.name for f in dataclasses.fields(ClinicalReferenceValue)}
    assert "provenance" not in field_names
    assert "confidence" not in field_names
    assert field_names == {"scenario", "domain", "descriptor", "value", "unit", "citation", "phase_note"}


def test_reference_value_requires_citation():
    with pytest.raises(ValueError, match="citation"):
        ClinicalReferenceValue(
            scenario="sepsis", domain="cardiovascular", descriptor="systolic_bp",
            value=85.0, unit="mmHg", citation="",
        )


def test_reference_value_requires_scenario_and_descriptor():
    with pytest.raises(ValueError, match="scenario"):
        ClinicalReferenceValue(scenario="", domain="cardiovascular", descriptor="systolic_bp", value=85.0, unit="mmHg", citation="Sepsis-3")
    with pytest.raises(ValueError, match="descriptor"):
        ClinicalReferenceValue(scenario="sepsis", domain="cardiovascular", descriptor="", value=85.0, unit="mmHg", citation="Sepsis-3")


def test_provenance_referencia_clinica_exists_but_has_no_confidence_band():
    from domain.physiology.state.schema import CONFIDENCE_REFERENCE
    assert Provenance.REFERENCIA_CLINICA in Provenance
    assert Provenance.REFERENCIA_CLINICA not in CONFIDENCE_REFERENCE


def test_estimate_map_formula():
    # PAM ~ DBP + 1/3(SBP-DBP)
    assert estimate_map(120.0, 80.0) == pytest.approx(93.333, abs=0.01)
    assert estimate_map(85.0, 55.0) == pytest.approx(65.0, abs=0.01)  # coherente con sepsis (Sepsis-3: PAM<65)


# --- Persistencia --------------------------------------------------------------

def test_create_and_retrieve_reference_round_trip(db_path):
    SessionLocal = _session_factory(db_path)
    with SessionLocal() as session:
        patient_id = create_patient(session, display_name="Paciente Referencia")
        organism = DigitalTwinOrganism()
        organism.create_patient_scenario("sepsis")
        state = from_digital_twin_organism(organism, patient_id, Provenance.SIMULACION, 0.9)
        snapshot_id = save_state(session, state)

        ref = ClinicalReferenceValue(
            scenario="sepsis", domain="cardiovascular", descriptor="systolic_bp",
            value=85.0, unit="mmHg", citation="Sepsis-3", phase_note="Shock séptico.",
        )
        create_clinical_reference(session, snapshot_id=snapshot_id, patient_id=patient_id, reference=ref)

    SessionLocal2 = _session_factory(db_path)
    with SessionLocal2() as session:
        by_snapshot = get_clinical_references_for_snapshot(session, snapshot_id)
        by_patient = get_clinical_references_for_patient(session, patient_id)

    assert len(by_snapshot) == 1
    assert by_snapshot[0].value == pytest.approx(85.0)
    assert by_snapshot[0].citation == "Sepsis-3"
    assert by_snapshot[0].phase_note == "Shock séptico."
    assert len(by_patient) == 1


def test_reference_requires_a_real_existing_snapshot(db_path):
    SessionLocal = _session_factory(db_path)
    with SessionLocal() as session:
        patient_id = create_patient(session, display_name="Paciente Huerfano")
        ref = ClinicalReferenceValue(
            scenario="sepsis", domain="cardiovascular", descriptor="systolic_bp",
            value=85.0, unit="mmHg", citation="Sepsis-3",
        )
        with pytest.raises(sqlalchemy.exc.IntegrityError):
            create_clinical_reference(session, snapshot_id="snapshot-inventado", patient_id=patient_id, reference=ref)


# --- Integridad de la tabla de datos transcritos --------------------------------

def test_blood_pressure_references_only_cover_real_scenarios():
    valid_scenario_values = {s.value for s in SimulationScenario}
    assert set(BLOOD_PRESSURE_REFERENCES.keys()).issubset(valid_scenario_values)


def test_fatigue_and_copd_have_no_reference_honest_gap():
    assert "fatigue" not in BLOOD_PRESSURE_REFERENCES
    assert "copd" not in BLOOD_PRESSURE_REFERENCES


def test_ten_scenarios_have_data():
    assert len(BLOOD_PRESSURE_REFERENCES) == 10


def test_every_reference_value_has_a_non_empty_citation():
    for scenario, values in BLOOD_PRESSURE_REFERENCES.items():
        for v in values:
            assert v.citation.strip(), f"{scenario}/{v.descriptor} sin cita"


def test_bifasic_scenarios_carry_a_phase_note():
    bifasic = ["sepsis", "hypoxia", "apnea", "seizure", "arrhythmia", "stress", "anxiety"]
    for scenario in bifasic:
        for v in BLOOD_PRESSURE_REFERENCES[scenario]:
            assert v.phase_note, f"{scenario}/{v.descriptor} sin nota de fase"


def test_healthy_and_hypertension_have_full_triplet():
    for scenario in ["healthy", "hypertension", "sepsis", "apnea", "seizure", "hypoxia", "arrhythmia"]:
        descriptors = {v.descriptor for v in BLOOD_PRESSURE_REFERENCES[scenario]}
        assert descriptors == {"systolic_bp", "diastolic_bp", "map"}, scenario


def test_exercise_stress_anxiety_only_have_systolic_honest_gap():
    for scenario in ["exercise", "stress", "anxiety"]:
        descriptors = {v.descriptor for v in BLOOD_PRESSURE_REFERENCES[scenario]}
        assert descriptors == {"systolic_bp"}, f"{scenario}: {descriptors}"


# --- Conexión con run_rich_scenario ---------------------------------------------

def test_run_rich_scenario_attaches_reference_to_final_snapshot_for_sourced_scenario(db_path):
    SessionLocal = _session_factory(db_path)
    with SessionLocal() as session:
        organism = DigitalTwinOrganism()
        patient_id = create_ephemeral_basal_patient(session, SimulationScenario.SEPSIS)
        list(run_rich_scenario(session, patient_id, SimulationScenario.SEPSIS, organism, start_from_current_state=False))
        references = get_clinical_references_for_patient(session, patient_id)

    assert len(references) == 3  # systolic, diastolic, map
    descriptors = {r.descriptor: r.value for r in references}
    assert descriptors["systolic_bp"] == pytest.approx(85.0)
    assert descriptors["diastolic_bp"] == pytest.approx(55.0)
    assert descriptors["map"] == pytest.approx(65.0, abs=0.1)


def test_run_rich_scenario_attaches_nothing_for_unsourced_scenario(db_path):
    SessionLocal = _session_factory(db_path)
    with SessionLocal() as session:
        organism = DigitalTwinOrganism()
        patient_id = create_ephemeral_basal_patient(session, SimulationScenario.FATIGUE)
        list(run_rich_scenario(session, patient_id, SimulationScenario.FATIGUE, organism, start_from_current_state=False))
        references = get_clinical_references_for_patient(session, patient_id)

    assert references == []


def test_run_rich_scenario_attaches_only_to_final_snapshot_not_all_six(db_path):
    """PA estática -- una fotografía, no una trayectoria por horizonte. Si se
    adjuntara a los 6 snapshots del escenario (uno por horizonte), el total de
    referencias para el paciente sería 3*6=18, no 3."""
    SessionLocal = _session_factory(db_path)
    with SessionLocal() as session:
        organism = DigitalTwinOrganism()
        patient_id = create_ephemeral_basal_patient(session, SimulationScenario.HEALTHY)
        steps = list(run_rich_scenario(session, patient_id, SimulationScenario.HEALTHY, organism, start_from_current_state=False))
        assert len(steps) == 6  # los 6 horizontes de siempre, sin cambios

        references = get_clinical_references_for_patient(session, patient_id)

    assert len(references) == 3  # systolic_bp, diastolic_bp, map -- una sola vez


# --- Modelo de riesgo real, encendido -------------------------------------------

def test_risk_features_reads_real_bp_for_sourced_scenario(db_path):
    SessionLocal = _session_factory(db_path)
    with SessionLocal() as session:
        organism = DigitalTwinOrganism()
        patient_id = create_ephemeral_basal_patient(session, SimulationScenario.HYPERTENSION)
        list(run_rich_scenario(session, patient_id, SimulationScenario.HYPERTENSION, organism, start_from_current_state=False))

        features = build_risk_features(session, patient_id)

    assert features is not None
    assert features.systolic_bp == pytest.approx(130.0)
    assert features.diastolic_bp == pytest.approx(80.0)


def test_risk_features_keeps_using_clinical_reference_not_calculated_pa(db_path):
    """Conexión al UPS de los 3 escenarios validados (2026-08-01), decisión
    explícita: aunque el snapshot tenga AMBAS fuentes de PA (calculada por
    el lazo cerrado Y referencia clínica citada), `build_risk_features()`
    debe seguir leyendo la referencia -- la calculada es valor didáctico/
    comparativo, no la fuente del score de riesgo. Ver
    `domain/physiology/ml/risk_context.py` para el razonamiento completo."""
    from domain.physiology.hemodynamics import compute_and_attach_closed_loop_pressure
    from domain.physiology.state import get_latest_snapshot_id, get_latest_state

    SessionLocal = _session_factory(db_path)
    with SessionLocal() as session:
        organism = DigitalTwinOrganism()
        patient_id = create_ephemeral_basal_patient(session, SimulationScenario.HYPERTENSION)
        list(run_rich_scenario(session, patient_id, SimulationScenario.HYPERTENSION, organism, start_from_current_state=False))

        snapshot_id = get_latest_snapshot_id(session, patient_id)
        heart_rate = get_latest_state(session, patient_id).cardiovascular.get("heart_rate").value
        calculated = compute_and_attach_closed_loop_pressure(
            session, snapshot_id=snapshot_id, scenario="hypertension", heart_rate_bpm=heart_rate
        )

        features = build_risk_features(session, patient_id)

    # La PA calculada realmente difiere de la referencia (si no, la prueba no probaría nada).
    assert calculated.final_systolic_bp != pytest.approx(130.0, abs=0.5)

    # build_risk_features sigue devolviendo la REFERENCIA (130/80), no la calculada.
    assert features.systolic_bp == pytest.approx(130.0)
    assert features.diastolic_bp == pytest.approx(80.0)


def test_risk_features_stays_none_for_unsourced_scenario(db_path):
    SessionLocal = _session_factory(db_path)
    with SessionLocal() as session:
        organism = DigitalTwinOrganism()
        patient_id = create_ephemeral_basal_patient(session, SimulationScenario.COPD)
        list(run_rich_scenario(session, patient_id, SimulationScenario.COPD, organism, start_from_current_state=False))

        features = build_risk_features(session, patient_id)

    assert features is not None
    assert features.systolic_bp is None
    assert features.diastolic_bp is None


def test_real_risk_predictor_stops_omitting_blood_pressure_factor(db_path):
    """Cruce con el predictor REAL (src/ai/patient_analytics.py), no un mock --
    confirma que el peso de 0.25 deja de omitirse cuando hay PA real."""
    SessionLocal = _session_factory(db_path)
    with SessionLocal() as session:
        organism = DigitalTwinOrganism()
        patient_id = create_ephemeral_basal_patient(session, SimulationScenario.SEPSIS)
        list(run_rich_scenario(session, patient_id, SimulationScenario.SEPSIS, organism, start_from_current_state=False))
        features = build_risk_features(session, patient_id)

    predictor = PatientRiskPredictor()
    result = predictor.calculate_risk_score(
        heart_rate=features.heart_rate,
        systolic_bp=features.systolic_bp,
        diastolic_bp=features.diastolic_bp,
        ecg_pattern=features.ecg_pattern,
        hrv_sdnn=features.hrv_sdnn,
        trend_data=features.trend_data,
    )

    assert "blood_pressure" not in result["factors_omitted"]
    assert "blood_pressure" in result["factors_used"]
