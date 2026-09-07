"""
Acoplamientos, Sub-fase A -- el puente `apply_couplings()` es HONESTO E
INERTE con CERO reglas activas.

Cubre las 4 pruebas del brief:
  1. inerte con catálogo vacío -> el snapshot no cambia
  2. `Provenance.DERIVADO_ACOPLAMIENTO` viaja de punta a punta (persiste y
     se recupera con su procedencia/confianza)
  3. el nombrado `_acoplado` coexiste con el medido sin sobrescritura
  4. `build_context()` citaría un descriptor `_acoplado` sin tocar el narrador

Más: el guard de escenario, el mapeo de confianza, y la ruta completa una
sola vez con una regla de ejemplo SOLO-TEST (nunca importada fuera de aquí,
como `_example_rule` en test_coupling_engine.py).
"""

import pytest

from app.engines.digital_twin_organism import DigitalTwinOrganism
from domain.physiology.coupling import (
    COUPLING_CONFIDENCE_TRANSCRITO,
    COUPLING_CONFIDENCE_VALIDADO,
    COUPLING_DISABLED_SCENARIOS,
    ComparisonOperator,
    CouplingCondition,
    CouplingEffect,
    CouplingRule,
    CouplingScenarioBlockedError,
    EffectDirection,
    ValidationStatus,
    apply_couplings,
    confidence_for_validation_status,
)
from domain.physiology.narrator.context import build_context
from domain.physiology.state import (
    CONFIDENCE_REFERENCE,
    PhysiologicalDescriptor,
    Provenance,
    create_patient,
    from_digital_twin_organism,
    get_state_by_snapshot_id,
    init_db,
    make_engine,
    make_session_factory,
    save_state,
)
from domain.physiology.state.repository import append_descriptors


@pytest.fixture
def session_factory(tmp_path):
    engine = make_engine(tmp_path / "coupling_bridge_test.db")
    init_db(engine)
    return make_session_factory(engine)


def _persist_neuro_and_ecg_snapshot(session):
    """Un snapshot real: el organismo recibe EEG (beta alto) + ECG, se
    construye y se persiste. Devuelve (patient_id, snapshot_id)."""
    patient_id = create_patient(session, display_name="Paciente Acoplamiento A")
    organism = DigitalTwinOrganism()
    organism.update_from_sensors({
        "ecg": {"heart_rate": 70.0, "hrv": 45.0},
        "eeg": {"alpha_power": 8.0, "beta_power": 30.0, "theta_power": 4.0,
                "delta_power": 2.0, "gamma_power": 3.0},
    })
    state = from_digital_twin_organism(organism, patient_id, Provenance.SIMULACION, 0.85)
    snapshot_id = save_state(session, state)
    return patient_id, snapshot_id


def _test_only_rule(*, enabled: bool, magnitude_delta=None,
                    status=ValidationStatus.TRANSCRITO_SIN_VALIDAR) -> CouplingRule:
    """Regla SOLO-TEST -- nunca importada fuera de este archivo, nace del
    brief como andamio mecánico. NO es una regla real (esa es la Sub-fase B,
    con el experto)."""
    return CouplingRule(
        rule_id="EJEMPLO_TEST_NO_USAR__arousal_bar_taquicardia",
        condition=CouplingCondition(
            domain="neurological", descriptor="bar",
            operator=ComparisonOperator.GREATER_THAN, threshold=1.8, unit="ratio (adimensional)",
        ),
        effect=CouplingEffect(
            domain="cardiovascular", descriptor="heart_rate",
            direction=EffectDirection.AUMENTA,
            magnitude_hint="andamio de test, magnitud no citada de ninguna fuente",
            magnitude_delta=magnitude_delta,
        ),
        source="ANDAMIO DE TEST -- sin fuente real (Sub-fase B trae la cita de Guyton)",
        validation_status=status,
        enabled=enabled,
    )


# --- 1. INERTE con catálogo vacío -------------------------------------------

def test_apply_couplings_is_inert_with_empty_ruleset(session_factory):
    with session_factory() as session:
        _, snapshot_id = _persist_neuro_and_ecg_snapshot(session)
        before = get_state_by_snapshot_id(session, snapshot_id)
        before_cv = dict(before.cardiovascular.descriptors)

        applied = apply_couplings(session, snapshot_id, [])

        assert applied == []
        after = get_state_by_snapshot_id(session, snapshot_id)
        assert set(after.cardiovascular.descriptors) == set(before_cv)
        assert not any(name.endswith("_acoplado") for name in after.cardiovascular.descriptors)
        assert after.cardiovascular.get("heart_rate").value == before_cv["heart_rate"].value


def test_apply_couplings_is_inert_with_only_disabled_rules(session_factory):
    with session_factory() as session:
        _, snapshot_id = _persist_neuro_and_ecg_snapshot(session)
        rule = _test_only_rule(enabled=False, magnitude_delta=15.0)  # dispararía si estuviera enabled

        applied = apply_couplings(session, snapshot_id, [rule])

        assert applied == []
        after = get_state_by_snapshot_id(session, snapshot_id)
        assert not any(name.endswith("_acoplado") for name in after.cardiovascular.descriptors)


def test_enabled_rule_without_magnitude_writes_nothing(session_factory):
    """Regla habilitada y disparada, pero sin `magnitude_delta` -- no hay
    número citado, no se puede escribir un valor acoplado honesto."""
    with session_factory() as session:
        _, snapshot_id = _persist_neuro_and_ecg_snapshot(session)
        rule = _test_only_rule(enabled=True, magnitude_delta=None)

        applied = apply_couplings(session, snapshot_id, [rule])

        assert applied == []
        after = get_state_by_snapshot_id(session, snapshot_id)
        assert not any(name.endswith("_acoplado") for name in after.cardiovascular.descriptors)


# --- 2. La procedencia nueva viaja de punta a punta ------------------------

def test_derivado_acoplamiento_roundtrips(session_factory):
    with session_factory() as session:
        _, snapshot_id = _persist_neuro_and_ecg_snapshot(session)
        desc = PhysiologicalDescriptor(
            name="heart_rate_acoplado", value=88.0, unit="bpm",
            provenance=Provenance.DERIVADO_ACOPLAMIENTO, confidence=0.35,
            source_detail="acoplamiento:TEST | fuente | disparo: beta_power=30 | heart_rate base=70",
        )
        append_descriptors(session, snapshot_id=snapshot_id, domain="cardiovascular", descriptors=[desc])

        recovered = get_state_by_snapshot_id(session, snapshot_id).cardiovascular.get("heart_rate_acoplado")
        assert recovered is not None
        assert recovered.value == pytest.approx(88.0)
        assert recovered.provenance == Provenance.DERIVADO_ACOPLAMIENTO
        assert recovered.confidence == pytest.approx(0.35)
        assert "disparo: beta_power=30" in recovered.source_detail


def test_derivado_acoplamiento_has_a_confidence_band_below_simulacion():
    band = CONFIDENCE_REFERENCE[Provenance.DERIVADO_ACOPLAMIENTO]
    assert (band.low, band.high) == (0.30, 0.80)
    assert band.high < CONFIDENCE_REFERENCE[Provenance.SIMULACION].high  # 0.80 < 0.90


def test_confidence_for_validation_status_maps_explicitly_within_band():
    band = CONFIDENCE_REFERENCE[Provenance.DERIVADO_ACOPLAMIENTO]
    c_transcrito = confidence_for_validation_status(ValidationStatus.TRANSCRITO_SIN_VALIDAR)
    c_validado = confidence_for_validation_status(ValidationStatus.VALIDADO_POR_FUENTE)
    assert c_transcrito == COUPLING_CONFIDENCE_TRANSCRITO
    assert c_validado == COUPLING_CONFIDENCE_VALIDADO
    assert band.low <= c_transcrito < c_validado <= band.high
    assert c_validado < CONFIDENCE_REFERENCE[Provenance.SIMULACION].high


# --- 3. El nombrado _acoplado coexiste con el medido ----------------------

def test_measured_and_coupled_heart_rate_coexist(session_factory):
    with session_factory() as session:
        _, snapshot_id = _persist_neuro_and_ecg_snapshot(session)
        coupled = PhysiologicalDescriptor(
            name="heart_rate_acoplado", value=85.0, unit="bpm",
            provenance=Provenance.DERIVADO_ACOPLAMIENTO, confidence=0.35,
            source_detail="acoplamiento:TEST",
        )
        append_descriptors(session, snapshot_id=snapshot_id, domain="cardiovascular", descriptors=[coupled])

        cv = get_state_by_snapshot_id(session, snapshot_id).cardiovascular
        assert cv.get("heart_rate").value == pytest.approx(70.0)          # medido, intacto
        assert cv.get("heart_rate").provenance == Provenance.SIMULACION
        assert cv.get("heart_rate_acoplado").value == pytest.approx(85.0)  # calculado, fila aparte
        assert cv.get("heart_rate_acoplado").provenance == Provenance.DERIVADO_ACOPLAMIENTO


# --- 4. El narrador lo citaría, sin tocar el narrador ---------------------

def test_build_context_would_cite_a_coupled_descriptor(session_factory):
    with session_factory() as session:
        patient_id, snapshot_id = _persist_neuro_and_ecg_snapshot(session)
        append_descriptors(
            session, snapshot_id=snapshot_id, domain="cardiovascular",
            descriptors=[PhysiologicalDescriptor(
                name="heart_rate_acoplado", value=86.0, unit="bpm",
                provenance=Provenance.DERIVADO_ACOPLAMIENTO, confidence=0.35,
                source_detail="acoplamiento:TEST",
            )],
        )

        ctx = build_context(session, patient_id)
        coupled = [d for d in ctx.descriptors if d.name == "heart_rate_acoplado"]
        assert len(coupled) == 1
        assert coupled[0].domain == "cardiovascular"
        assert coupled[0].provenance == Provenance.DERIVADO_ACOPLAMIENTO.value
        # y el medido sigue estando, por separado
        assert any(d.name == "heart_rate" for d in ctx.descriptors)


# --- El guard de escenario (doble contabilidad) --------------------------

def test_apply_couplings_blocks_a_correlation_cooking_scenario(session_factory):
    with session_factory() as session:
        _, snapshot_id = _persist_neuro_and_ecg_snapshot(session)
        with pytest.raises(CouplingScenarioBlockedError, match="doble contabilidad"):
            apply_couplings(session, snapshot_id, [], scenario="stress")


def test_disabled_scenarios_are_the_documented_set():
    assert COUPLING_DISABLED_SCENARIOS == frozenset({"stress", "anxiety", "seizure"})


def test_apply_couplings_runs_for_a_non_scenario_writer(session_factory):
    """`scenario=None` (EEG Lab / escritor solo-EEG) no se bloquea."""
    with session_factory() as session:
        _, snapshot_id = _persist_neuro_and_ecg_snapshot(session)
        assert apply_couplings(session, snapshot_id, [], scenario=None) == []


# --- La ruta completa una sola vez (regla SOLO-TEST con magnitud) --------

def test_full_path_once_with_test_only_rule_and_explicit_magnitude(session_factory):
    """Ejercita el cuerpo del bucle: regla SOLO-TEST habilitada, bar
    (30/8 = 3.75) sobre umbral (1.8), magnitude_delta=+18 -> una fila
    heart_rate_acoplado = 70 + 18 = 88, DERIVADO_ACOPLAMIENTO, confianza
    del extremo bajo (TRANSCRITO_SIN_VALIDAR). El medido no se toca."""
    with session_factory() as session:
        _, snapshot_id = _persist_neuro_and_ecg_snapshot(session)
        rule = _test_only_rule(enabled=True, magnitude_delta=18.0,
                               status=ValidationStatus.TRANSCRITO_SIN_VALIDAR)

        applied = apply_couplings(session, snapshot_id, [rule])

        assert len(applied) == 1
        ac = applied[0]
        assert ac.coupled_descriptor == "heart_rate_acoplado"
        assert ac.base_value == pytest.approx(70.0)
        assert ac.coupled_value == pytest.approx(88.0)
        assert ac.observed_value == pytest.approx(30.0 / 8.0)  # bar = beta/alpha
        assert ac.provenance == Provenance.DERIVADO_ACOPLAMIENTO
        assert ac.confidence == pytest.approx(COUPLING_CONFIDENCE_TRANSCRITO)

        cv = get_state_by_snapshot_id(session, snapshot_id).cardiovascular
        assert cv.get("heart_rate").value == pytest.approx(70.0)  # intacto
        d = cv.get("heart_rate_acoplado")
        assert d.value == pytest.approx(88.0)
        assert d.unit == "bpm"
        assert "EJEMPLO_TEST_NO_USAR__arousal_bar_taquicardia" in d.source_detail
        assert "heart_rate base=70" in d.source_detail


def test_effect_rejects_magnitude_delta_that_contradicts_direction():
    with pytest.raises(ValueError, match="contradice direction=AUMENTA"):
        CouplingEffect(
            domain="cardiovascular", descriptor="heart_rate",
            direction=EffectDirection.AUMENTA, magnitude_delta=-5.0,
        )
