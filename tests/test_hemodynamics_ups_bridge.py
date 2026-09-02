"""
"La película" — Paso 2 (2026-07-19): conexión del módulo R-RCR fisiológico
(`domain/physiology/hemodynamics/`) al UPS vivo.

Cubre las tres decisiones aprobadas por el usuario en el Paso 1 de esta
tanda: SV_ref citado (no el campo fingido del organismo), segundo set de
parámetros R/Rp/Rd/C fisiológicos marcado pendiente de validación, y
`Provenance.MODELO_HEMODINAMICO` con banda de confianza 0.30-0.55. Y la
coexistencia del Paso 2: la PA calculada no sobrescribe la PA de
referencia clínica (`ClinicalReferenceValue`), ambas conviven en el mismo
snapshot con procedencia propia.
"""

import pytest

from app.engines.digital_twin_organism import DigitalTwinOrganism
from app.engines.simulation_engine import SimulationScenario
from domain.physiology.hemodynamics import (
    PHYSIOLOGICAL_PARAMETERS_PENDING_VALIDATION,
    PHYSIOLOGICAL_RRCR_PARAMETERS,
    STROKE_VOLUME_REFERENCE_ML,
    RRCRParameters,
    compute_and_attach_calculated_pressure,
    compute_calculated_pressure,
    physiological_pulsatile_flow,
    run_scenario_pressure_comparison,
)
from domain.physiology.scenarios.rich_engine import create_ephemeral_basal_patient, run_rich_scenario
from domain.physiology.state import (
    Provenance,
    CONFIDENCE_REFERENCE,
    get_clinical_references_for_patient,
    get_latest_snapshot_id,
    get_latest_state,
    init_db,
    make_engine,
    make_session_factory,
)


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "hemodynamics_bridge_test.db"


def _session_factory(path):
    engine = make_engine(path)
    init_db(engine)
    return make_session_factory(engine)


# --- Provenance.MODELO_HEMODINAMICO -----------------------------------------


def test_modelo_hemodinamico_confidence_band_ceiling_stays_below_simulacion():
    """Banda ensanchada 2026-08-01 (Conexión al UPS de los 3 escenarios
    validados): el techo subió de 0.55 a 0.80 para darle espacio a
    `closed_loop_ups_bridge.py` (confianza ~0.75 para los 3 escenarios
    validados) sin inventar una segunda procedencia -- pero el techo
    (0.80) sigue, deliberadamente, por debajo del techo de SIMULACION
    (0.90): ni el caso más validado de este modelo compite con un dato
    derivado directamente del organismo."""
    band = CONFIDENCE_REFERENCE[Provenance.MODELO_HEMODINAMICO]
    assert band.low == pytest.approx(0.30)
    assert band.high == pytest.approx(0.80)
    simulacion_band = CONFIDENCE_REFERENCE[Provenance.SIMULACION]
    assert band.high < simulacion_band.high
    assert band.high > simulacion_band.low  # se permite solaparse -- ver docstring de Provenance


def test_physiological_parameters_marked_pending_validation():
    assert PHYSIOLOGICAL_PARAMETERS_PENDING_VALIDATION is True


def test_physiological_parameters_are_a_separate_set_from_validated_test_case():
    """El set fisiológico NO debe ser el mismo objeto/valores que el caso de
    prueba oficial validado matemáticamente en r_rcr.py -- son dos
    conjuntos deliberadamente distintos."""
    official = RRCRParameters()
    assert PHYSIOLOGICAL_RRCR_PARAMETERS != official
    assert PHYSIOLOGICAL_RRCR_PARAMETERS.rd != official.rd
    assert PHYSIOLOGICAL_RRCR_PARAMETERS.c != official.c


# --- Flujo de entrada honesto -------------------------------------------------


def test_physiological_pulsatile_flow_period_matches_real_heart_rate():
    _, period_s = physiological_pulsatile_flow(heart_rate_bpm=60.0)
    assert period_s == pytest.approx(1.0)

    _, period_s_120 = physiological_pulsatile_flow(heart_rate_bpm=120.0)
    assert period_s_120 == pytest.approx(0.5)


def test_physiological_pulsatile_flow_scales_with_stroke_volume_reference():
    flow_fn, period_s = physiological_pulsatile_flow(heart_rate_bpm=60.0, sv_ref_ml=STROKE_VOLUME_REFERENCE_ML)
    # Media del flujo a lo largo de un periodo == CO_medio = HR/60 * SV_ref
    import numpy as np

    t = np.linspace(0.0, period_s, 2001)
    q = np.array([flow_fn(x) for x in t])
    mean_q = np.trapezoid(q, t) / period_s
    expected_co = (60.0 / 60.0) * STROKE_VOLUME_REFERENCE_ML
    assert mean_q == pytest.approx(expected_co, rel=1e-3)


def test_physiological_pulsatile_flow_rejects_non_positive_heart_rate():
    with pytest.raises(ValueError):
        physiological_pulsatile_flow(heart_rate_bpm=0.0)


# --- Cálculo de presión --------------------------------------------------------


def test_compute_calculated_pressure_systolic_above_diastolic():
    result = compute_calculated_pressure(heart_rate_bpm=72.0)
    assert result["systolic_bp"] > result["diastolic_bp"]
    assert result["heart_rate_bpm"] == pytest.approx(72.0)


def test_compute_calculated_pressure_diastolic_below_map_below_systolic():
    result = compute_calculated_pressure(heart_rate_bpm=72.0)
    assert result["diastolic_bp"] < result["map"] < result["systolic_bp"]


def test_compute_calculated_pressure_order_of_magnitude_is_plausible_mmhg():
    """Sanity check de orden de magnitud (no una validación fisiológica --
    esa es la Paso 3, para el validador). Con parámetros de RPT ~1 PRU y
    CO fisiológico, el resultado debe caer en un rango de mmHg humano
    (no en los ~10000 del caso de prueba de r_rcr.py, ni en valores
    absurdos de otros órdenes de magnitud)."""
    result = compute_calculated_pressure(heart_rate_bpm=72.0)
    assert 20.0 < result["diastolic_bp"] < 300.0
    assert 20.0 < result["systolic_bp"] < 300.0


# --- Persistencia con Provenance.MODELO_HEMODINAMICO, coexistencia --------------


def test_compute_and_attach_persists_three_descriptors_with_modelo_provenance(db_path):
    SessionLocal = _session_factory(db_path)
    with SessionLocal() as session:
        organism = DigitalTwinOrganism()
        patient_id = create_ephemeral_basal_patient(session, SimulationScenario.HEALTHY)
        list(run_rich_scenario(session, patient_id, SimulationScenario.HEALTHY, organism, start_from_current_state=False))

        snapshot_id = get_latest_snapshot_id(session, patient_id)
        pressures = compute_and_attach_calculated_pressure(session, snapshot_id=snapshot_id, heart_rate_bpm=72.0)

        state = get_latest_state(session, patient_id)

    for name in ("systolic_bp_modelo", "diastolic_bp_modelo", "map_modelo"):
        descriptor = state.cardiovascular.get(name)
        assert descriptor is not None, name
        assert descriptor.provenance == Provenance.MODELO_HEMODINAMICO
        # Valor EXACTO (no solo "dentro de la banda"): confirma que este puente
        # (Módulo 1, sin validar) preserva su confianza histórica 0.425 pese a
        # que la banda de MODELO_HEMODINAMICO se ensanchó (2026-08-01) para dar
        # espacio al puente del lazo cerrado validado (closed_loop_ups_bridge.py).
        assert descriptor.confidence == pytest.approx(0.425)

    assert state.cardiovascular.get("systolic_bp_modelo").value == pytest.approx(pressures["systolic_bp"])


def test_attaching_calculated_pressure_does_not_remove_existing_descriptors(db_path):
    """Aditivo: heart_rate/hrv/health_score etc. (ya persistidos por
    run_rich_scenario) siguen ahí después de adjuntar la PA calculada."""
    SessionLocal = _session_factory(db_path)
    with SessionLocal() as session:
        organism = DigitalTwinOrganism()
        patient_id = create_ephemeral_basal_patient(session, SimulationScenario.HEALTHY)
        list(run_rich_scenario(session, patient_id, SimulationScenario.HEALTHY, organism, start_from_current_state=False))

        state_before = get_latest_state(session, patient_id)
        heart_rate_before = state_before.cardiovascular.get("heart_rate").value

        snapshot_id = get_latest_snapshot_id(session, patient_id)
        compute_and_attach_calculated_pressure(session, snapshot_id=snapshot_id, heart_rate_bpm=heart_rate_before)

        state_after = get_latest_state(session, patient_id)

    assert state_after.cardiovascular.get("heart_rate").value == pytest.approx(heart_rate_before)
    assert state_after.cardiovascular.get("heart_rate").provenance == Provenance.SIMULACION


def test_calculated_pressure_coexists_with_clinical_reference_neither_overwrites_other(db_path):
    """El escenario 'healthy' tiene entrada en BLOOD_PRESSURE_REFERENCES
    (PA de referencia citada). Tras adjuntar la PA calculada, ambas deben
    seguir presentes, con procedencia distinta, sin que ninguna reemplace
    a la otra."""
    SessionLocal = _session_factory(db_path)
    with SessionLocal() as session:
        organism = DigitalTwinOrganism()
        patient_id = create_ephemeral_basal_patient(session, SimulationScenario.HEALTHY)
        list(run_rich_scenario(session, patient_id, SimulationScenario.HEALTHY, organism, start_from_current_state=False))

        snapshot_id = get_latest_snapshot_id(session, patient_id)
        compute_and_attach_calculated_pressure(session, snapshot_id=snapshot_id, heart_rate_bpm=72.0)

        state = get_latest_state(session, patient_id)
        references = get_clinical_references_for_patient(session, patient_id)

    # PA de referencia clínica intacta (3 valores: systolic_bp/diastolic_bp/map, sin sufijo)
    ref_descriptors = {r.descriptor: r.value for r in references}
    assert ref_descriptors == {"systolic_bp": pytest.approx(120.0), "diastolic_bp": pytest.approx(80.0), "map": pytest.approx(93.33, abs=0.1)}

    # PA calculada presente, con nombre y procedencia distintos, sin tocar la de referencia
    assert state.cardiovascular.get("systolic_bp_modelo") is not None
    assert state.cardiovascular.get("systolic_bp_modelo").provenance == Provenance.MODELO_HEMODINAMICO
    # Los nombres reservados para un futuro descriptor medido/derivado real siguen sin usarse aquí
    assert state.cardiovascular.get("systolic_bp") is None


# --- Paso 3: comparación en contexto -----------------------------------------


def test_run_scenario_pressure_comparison_end_to_end(db_path):
    comparison = run_scenario_pressure_comparison(SimulationScenario.HEALTHY, db_path=db_path)

    assert comparison.scenario == "healthy"
    assert comparison.pending_validation is True
    assert comparison.calculated["systolic_bp"] > comparison.calculated["diastolic_bp"]
    assert len(comparison.reference) == 3

    rows = comparison.as_table_rows()
    assert len(rows) == 3
    descriptors = {row[0] for row in rows}
    assert descriptors == {"systolic_bp", "diastolic_bp", "map"}
    for _, calc_value, ref_value, _citation in rows:
        assert calc_value is not None
        assert ref_value is not None  # 'healthy' sí tiene referencia


def test_run_scenario_pressure_comparison_handles_scenario_without_reference(db_path):
    """'fatigue' no tiene entrada en BLOOD_PRESSURE_REFERENCES -- la
    comparación debe seguir funcionando, mostrando ausencia de
    referencia honestamente (None), no un valor inventado."""
    comparison = run_scenario_pressure_comparison(SimulationScenario.FATIGUE, db_path=db_path)

    assert comparison.reference == []
    rows = comparison.as_table_rows()
    for _, calc_value, ref_value, citation in rows:
        assert calc_value is not None
        assert ref_value is None
        assert citation == "sin referencia para este escenario"
