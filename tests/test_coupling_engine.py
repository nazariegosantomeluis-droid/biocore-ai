"""
Conexión entre sistemas, Paso 1b -- motor de acoplamiento fisiológico.

La ÚNICA regla de ejemplo de este archivo (`hipoxia_taquicardia_refleja`)
existe exclusivamente para probar mecánicamente que el motor evalúa
condiciones y efectos -- no es una regla real cargada en ningún flujo vivo,
y nace `enabled=False` como cualquier `CouplingRule`. Ningún módulo de
producción la importa.
"""

from datetime import datetime, timezone

import pytest

from app.engines.digital_twin_organism import DigitalTwinOrganism
from domain.physiology.coupling import (
    COUPLABLE_DESCRIPTORS,
    ComparisonOperator,
    CouplingCondition,
    CouplingEffect,
    CouplingRule,
    EffectDirection,
    ProposedCoupling,
    ValidationStatus,
    evaluate,
)
from domain.physiology.state import Provenance, from_digital_twin_organism
from domain.physiology.state.schema import DomainState, UnifiedPhysiologicalState


def _example_rule(enabled: bool = False) -> CouplingRule:
    """La única regla de ejemplo permitida por el brief -- marcada como tal,
    nunca importada fuera de este archivo de tests."""
    return CouplingRule(
        rule_id="EJEMPLO_NO_VALIDADO_NO_USAR__hipoxia_taquicardia_refleja",
        condition=CouplingCondition(
            domain="respiratory", descriptor="spo2",
            operator=ComparisonOperator.LESS_THAN, threshold=90.0, unit="%",
        ),
        effect=CouplingEffect(
            domain="cardiovascular", descriptor="heart_rate",
            direction=EffectDirection.AUMENTA,
            magnitude_hint="respuesta compensatoria, magnitud no cuantificada en la fuente",
        ),
        source="Guyton & Hall, Tratado de Fisiología Médica, 13a ed., cap. 41, p. 511",
        validation_status=ValidationStatus.TRANSCRITO_SIN_VALIDAR,
        enabled=enabled,
        notes="Quimiorreceptores periféricos detectan PO2 baja y estimulan taquicardia refleja.",
    )


# --- Validación estructural del formato de regla ---------------------------

def test_rule_requires_a_source():
    with pytest.raises(ValueError, match="source"):
        CouplingRule(
            rule_id="x",
            condition=_example_rule().condition,
            effect=_example_rule().effect,
            source="",
            validation_status=ValidationStatus.TRANSCRITO_SIN_VALIDAR,
        )


def test_rule_requires_a_rule_id():
    with pytest.raises(ValueError, match="rule_id"):
        CouplingRule(
            rule_id="",
            condition=_example_rule().condition,
            effect=_example_rule().effect,
            source="Guyton, cap. 41",
            validation_status=ValidationStatus.TRANSCRITO_SIN_VALIDAR,
        )


def test_rule_defaults_to_disabled():
    rule = _example_rule()
    assert rule.enabled is False


def test_condition_rejects_domain_the_ups_does_not_model():
    with pytest.raises(ValueError, match="dominio"):
        CouplingCondition(
            domain="nervioso", descriptor="cortisol",
            operator=ComparisonOperator.GREATER_THAN, threshold=1.0, unit="ug/dL",
        )


def test_condition_rejects_derived_index_not_a_primary_signal():
    """health_score es un índice que BIOCORE deriva, no una señal primaria
    de un libro de fisiología -- no debe ser acoplable."""
    with pytest.raises(ValueError, match="derivados"):
        CouplingCondition(
            domain="cardiovascular", descriptor="health_score",
            operator=ComparisonOperator.LESS_THAN, threshold=50.0, unit="0-100",
        )


def test_effect_rejects_non_couplable_descriptor():
    with pytest.raises(ValueError, match="derivados"):
        CouplingEffect(domain="respiratory", descriptor="hypoxia_risk", direction=EffectDirection.AUMENTA)


def test_couplable_descriptors_are_exactly_the_four_primary_signals():
    assert COUPLABLE_DESCRIPTORS == {
        "cardiovascular": frozenset({"heart_rate", "hrv"}),
        "respiratory": frozenset({"respiratory_rate", "spo2"}),
    }


# --- ComparisonOperator ------------------------------------------------------

@pytest.mark.parametrize(
    "operator,threshold,value,expected",
    [
        (ComparisonOperator.LESS_THAN, 90.0, 85.0, True),
        (ComparisonOperator.LESS_THAN, 90.0, 90.0, False),
        (ComparisonOperator.LESS_THAN_OR_EQUAL, 90.0, 90.0, True),
        (ComparisonOperator.GREATER_THAN, 100.0, 120.0, True),
        (ComparisonOperator.GREATER_THAN, 100.0, 100.0, False),
        (ComparisonOperator.GREATER_THAN_OR_EQUAL, 100.0, 100.0, True),
    ],
)
def test_condition_is_triggered_by(operator, threshold, value, expected):
    condition = CouplingCondition(domain="respiratory", descriptor="spo2", operator=operator, threshold=threshold, unit="%")
    assert condition.is_triggered_by(value) is expected


# --- El motor, dormido -------------------------------------------------------

def _state_with_spo2(value: float) -> UnifiedPhysiologicalState:
    organism = DigitalTwinOrganism()
    organism.create_patient_scenario("healthy")
    state = from_digital_twin_organism(organism, "paciente-test", Provenance.SIMULACION, 0.9)
    # Reemplaza solo el descriptor spo2 del snapshot en memoria, sin tocar la
    # lógica del organismo -- para probar el motor con un valor de umbral exacto.
    respiratory = state.respiratory
    spo2_descriptor = respiratory.get("spo2")
    new_descriptors = dict(respiratory.descriptors)
    new_descriptors["spo2"] = spo2_descriptor.__class__(
        name="spo2", value=value, unit="%",
        provenance=spo2_descriptor.provenance, confidence=spo2_descriptor.confidence,
    )
    return UnifiedPhysiologicalState(
        patient_id=state.patient_id,
        timestamp=state.timestamp,
        cardiovascular=state.cardiovascular,
        respiratory=DomainState(domain="respiratory", descriptors=new_descriptors),
        events=state.events,
    )


def test_engine_with_empty_ruleset_is_completely_inert():
    state = _state_with_spo2(80.0)  # cruzaría el umbral de la regla de ejemplo si estuviera activa
    proposals = evaluate(state, [])
    assert proposals == []


def test_engine_with_no_rules_at_all_does_not_fail():
    """El conjunto de reglas real de este proyecto hoy -- vacío. Nunca debe fallar."""
    organism = DigitalTwinOrganism()
    organism.create_patient_scenario("hypoxia")
    state = from_digital_twin_organism(organism, "paciente-real", Provenance.SIMULACION, 0.9)
    assert evaluate(state, []) == []


def test_disabled_example_rule_never_fires_even_if_condition_would_match():
    rule = _example_rule(enabled=False)
    state = _state_with_spo2(80.0)  # muy por debajo del umbral (90%)
    proposals = evaluate(state, [rule])
    assert proposals == []


def test_enabled_example_rule_fires_when_condition_is_met():
    rule = _example_rule(enabled=True)
    state = _state_with_spo2(85.0)  # < 90 -> dispara
    proposals = evaluate(state, [rule])

    assert len(proposals) == 1
    proposal = proposals[0]
    assert isinstance(proposal, ProposedCoupling)
    assert proposal.rule is rule
    assert proposal.observed_value == pytest.approx(85.0)
    assert proposal.effect.descriptor == "heart_rate"
    assert proposal.effect.direction == EffectDirection.AUMENTA
    assert proposal.source == "Guyton & Hall, Tratado de Fisiología Médica, 13a ed., cap. 41, p. 511"


def test_enabled_example_rule_does_not_fire_when_condition_is_not_met():
    rule = _example_rule(enabled=True)
    state = _state_with_spo2(97.0)  # >= 90 -> no dispara
    assert evaluate(state, [rule]) == []


def test_evaluate_never_mutates_the_input_state():
    rule = _example_rule(enabled=True)
    state = _state_with_spo2(85.0)
    hr_before = state.cardiovascular.get("heart_rate").value

    evaluate(state, [rule])

    assert state.cardiovascular.get("heart_rate").value == hr_before
    assert state.respiratory.get("spo2").value == pytest.approx(85.0)


def test_rule_missing_descriptor_in_state_does_not_fire_or_fail():
    """Un organismo que nunca recibió la señal de la condición -- la regla
    simplemente no se dispara, no se inventa un valor."""
    rule = _example_rule(enabled=True)
    empty_respiratory = DomainState(domain="respiratory", descriptors={})
    organism = DigitalTwinOrganism()
    organism.create_patient_scenario("healthy")
    base_state = from_digital_twin_organism(organism, "paciente-vacio", Provenance.SIMULACION, 0.9)
    state = UnifiedPhysiologicalState(
        patient_id=base_state.patient_id,
        timestamp=base_state.timestamp,
        cardiovascular=base_state.cardiovascular,
        respiratory=empty_respiratory,
        events=[],
    )
    assert evaluate(state, [rule]) == []
