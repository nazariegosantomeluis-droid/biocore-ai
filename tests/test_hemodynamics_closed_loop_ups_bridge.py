"""
"La película" — Conexión al UPS: los 3 escenarios validados, en
coexistencia (2026-08-01). El paso final -- primera escritura real del
motor hemodinámico al UPS.

Cubre: la restricción ESTRUCTURAL a `HEMODYNAMIC_MODEL_ENABLED_SCENARIOS`
(lanza, nunca omite en silencio), la confianza validada (0.75, dentro de
la banda ensanchada de MODELO_HEMODINAMICO), y la coexistencia real —
extendida del trabajo aislado (`test_hemodynamics_closed_loop_comparison.py`)
al flujo vivo equivalente: `run_rich_scenario()` (que ya adjunta la
`ClinicalReferenceValue`) seguido de `compute_and_attach_closed_loop_pressure()`
sobre el MISMO snapshot, consultado en una sola sesión — ambas fuentes
deben sobrevivir juntas.
"""

import pytest

from app.engines.digital_twin_organism import DigitalTwinOrganism
from app.engines.simulation_engine import SimulationScenario
from domain.physiology.hemodynamics import (
    HEMODYNAMIC_MODEL_ENABLED_SCENARIOS,
    HEMODYNAMIC_MODEL_VALIDATED_CONFIDENCE,
    HemodynamicModelNotEnabledError,
    compute_and_attach_closed_loop_pressure,
    run_closed_loop,
)
from domain.physiology.scenarios.rich_engine import create_ephemeral_basal_patient, run_rich_scenario
from domain.physiology.state import (
    CONFIDENCE_REFERENCE,
    Provenance,
    get_clinical_references_for_patient,
    get_latest_snapshot_id,
    get_latest_state,
    init_db,
    make_engine,
    make_session_factory,
)


def _session_factory(path):
    engine = make_engine(path)
    init_db(engine)
    return make_session_factory(engine)


# --- Paso 1: restricción estructural ---------------------------------------------


def test_enabled_scenarios_are_exactly_the_three_validated_ones():
    assert HEMODYNAMIC_MODEL_ENABLED_SCENARIOS == frozenset({"healthy", "hypertension", "sepsis"})
    assert isinstance(HEMODYNAMIC_MODEL_ENABLED_SCENARIOS, frozenset)  # inmutable


@pytest.mark.parametrize(
    "excluded_scenario",
    ["exercise", "stress", "anxiety", "arrhythmia", "hypoxia", "apnea", "fatigue", "seizure", "copd"],
)
def test_all_nine_excluded_scenarios_raise_structurally(excluded_scenario):
    """No hay forma de sortear la restricción -- se lanza ANTES de tocar
    la sesión o calcular nada (verificado pasando `session=None`: si la
    función intentara usar la sesión antes de este chequeo, esto crashearía
    con un error distinto a HemodynamicModelNotEnabledError)."""
    with pytest.raises(HemodynamicModelNotEnabledError):
        compute_and_attach_closed_loop_pressure(
            session=None, snapshot_id="fake", scenario=excluded_scenario, heart_rate_bpm=90.0
        )


def test_healthy_hypertension_sepsis_do_not_raise():
    for scenario in HEMODYNAMIC_MODEL_ENABLED_SCENARIOS:
        # No debe lanzar HemodynamicModelNotEnabledError -- fallará más adelante
        # (sesión falsa) por otra razón, lo cual confirma que pasó el gate.
        with pytest.raises(Exception) as exc_info:
            compute_and_attach_closed_loop_pressure(
                session=None, snapshot_id="fake", scenario=scenario, heart_rate_bpm=90.0
            )
        assert not isinstance(exc_info.value, HemodynamicModelNotEnabledError)


# --- Paso 2: confianza validada ---------------------------------------------------


def test_validated_confidence_is_within_the_widened_band():
    band = CONFIDENCE_REFERENCE[Provenance.MODELO_HEMODINAMICO]
    assert band.low <= HEMODYNAMIC_MODEL_VALIDATED_CONFIDENCE <= band.high
    assert HEMODYNAMIC_MODEL_VALIDATED_CONFIDENCE == pytest.approx(0.75)
    assert HEMODYNAMIC_MODEL_VALIDATED_CONFIDENCE > 0.55  # por encima del techo ANTIGUO (no validado)
    simulacion_band = CONFIDENCE_REFERENCE[Provenance.SIMULACION]
    assert HEMODYNAMIC_MODEL_VALIDATED_CONFIDENCE < simulacion_band.high  # nunca alcanza el techo de SIMULACION


# --- Paso 3: coexistencia -- extendida al flujo vivo equivalente ----------------


@pytest.mark.parametrize("scenario_enum,heart_rate_hint", [
    (SimulationScenario.HEALTHY, 72.0),
    (SimulationScenario.HYPERTENSION, 85.0),
    (SimulationScenario.SEPSIS, 150.0),
])
def test_calculated_pa_and_clinical_reference_coexist_on_the_live_flow(tmp_path, scenario_enum, heart_rate_hint):
    """Flujo vivo equivalente al de render_ups_scenario_simulator(): corre
    run_rich_scenario (que ya adjunta la ClinicalReferenceValue al último
    snapshot), luego adjunta la PA calculada al MISMO snapshot -- ambas
    deben sobrevivir en la misma consulta, ninguna sobrescribe a la otra."""
    db_path = tmp_path / f"live_flow_{scenario_enum.value}.db"
    SessionLocal = _session_factory(db_path)

    with SessionLocal() as session:
        organism = DigitalTwinOrganism()
        patient_id = create_ephemeral_basal_patient(session, scenario_enum)
        list(run_rich_scenario(session, patient_id, scenario_enum, organism, start_from_current_state=False))

        snapshot_id = get_latest_snapshot_id(session, patient_id)
        state_before = get_latest_state(session, patient_id)
        real_heart_rate = state_before.cardiovascular.get("heart_rate").value

        result = compute_and_attach_closed_loop_pressure(
            session, snapshot_id=snapshot_id, scenario=scenario_enum.value, heart_rate_bpm=real_heart_rate,
            source_detail="test:live_flow_equivalent",
        )

        # Misma consulta, ambas fuentes presentes -- la prueba central de coexistencia.
        state_after = get_latest_state(session, patient_id)
        references = get_clinical_references_for_patient(session, patient_id)

    # La PA calculada está en el snapshot.
    for name in ("systolic_bp_modelo", "diastolic_bp_modelo", "map_modelo"):
        descriptor = state_after.cardiovascular.get(name)
        assert descriptor is not None, name
        assert descriptor.provenance == Provenance.MODELO_HEMODINAMICO
        assert descriptor.confidence == pytest.approx(HEMODYNAMIC_MODEL_VALIDATED_CONFIDENCE)

    assert state_after.cardiovascular.get("map_modelo").value == pytest.approx(result.final_map)

    # La ClinicalReferenceValue SIGUE ahí, sin tocar -- coexistencia real, no una carrera.
    scenario_references = [r for r in references if r.scenario == scenario_enum.value]
    assert len(scenario_references) == 3  # systolic_bp, diastolic_bp, map -- ver blood_pressure_references.py

    # Ningún descriptor medido/simulado previo se borró (aditivo).
    assert state_after.cardiovascular.get("heart_rate") is not None
    assert state_after.cardiovascular.get("heart_rate").value == pytest.approx(real_heart_rate)


def test_calculated_pa_matches_run_closed_loop_directly_no_drift(tmp_path):
    """El valor persistido debe ser EXACTAMENTE el que produce
    run_closed_loop() por su cuenta -- el puente no debe recalcular ni
    redondear de forma distinta."""
    db_path = tmp_path / "no_drift.db"
    SessionLocal = _session_factory(db_path)

    with SessionLocal() as session:
        organism = DigitalTwinOrganism()
        patient_id = create_ephemeral_basal_patient(session, SimulationScenario.SEPSIS)
        list(run_rich_scenario(session, patient_id, SimulationScenario.SEPSIS, organism, start_from_current_state=False))

        snapshot_id = get_latest_snapshot_id(session, patient_id)
        heart_rate = get_latest_state(session, patient_id).cardiovascular.get("heart_rate").value

        bridge_result = compute_and_attach_closed_loop_pressure(
            session, snapshot_id=snapshot_id, scenario="sepsis", heart_rate_bpm=heart_rate
        )

    direct_result = run_closed_loop("sepsis", heart_rate)
    assert bridge_result.final_map == pytest.approx(direct_result.final_map)
    assert bridge_result.final_systolic_bp == pytest.approx(direct_result.final_systolic_bp)
