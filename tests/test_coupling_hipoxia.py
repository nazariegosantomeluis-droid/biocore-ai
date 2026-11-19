"""Ficha 1 · HIPOXIA_TAQUICARDIA, firmada por Luis el 2026-11-18 («firmo las dos fichas de acoplamiento»): las
propuestas de `docs/contenido/fichas_acoplamientos.md` transcritas al catálogo.

- Ancla `spo2 ≤ 91 %` (banda de 3 puntos NEWS2, escala 1), +13 lpm fijos, `VALIDADO_POR_FUENTE` (0.70).
- Bloqueada por regla en los escenarios que ya modelan la FC con la caída de SpO₂ (hipoxia, apnea, EPOC, sepsis),
  además de la lista global (convulsión, estrés, ansiedad).
- Sin política de combinación firmada: si dos reglas mueven la misma señal en el mismo snapshot, no se escribe ninguna.
"""

import pytest

from app.engines.digital_twin_organism import DigitalTwinOrganism
from domain.physiology.coupling import (
    AROUSAL_TAQUICARDIA_BAR,
    HIPOXIA_TAQUICARDIA,
    VALIDATED_RULES,
    apply_couplings,
)
from domain.physiology.coupling.rules import ComparisonOperator, ValidationStatus
from domain.physiology.state import (
    Provenance,
    create_patient,
    from_digital_twin_organism,
    get_state_by_snapshot_id,
    init_db,
    make_engine,
    make_session_factory,
    save_state,
)


@pytest.fixture
def session_factory(tmp_path):
    engine = make_engine(tmp_path / "hipoxia.db")
    init_db(engine)
    return make_session_factory(engine)


def _snapshot(session_factory, sensors):
    with session_factory() as session:
        patient_id = create_patient(session, display_name="hipoxia")
        o = DigitalTwinOrganism()
        o.update_from_sensors(sensors)
        state = from_digital_twin_organism(o, patient_id, Provenance.SIMULACION, 0.85)
        return save_state(session, state)


def test_la_regla_firmada_es_la_propuesta_de_la_ficha_1():
    r = HIPOXIA_TAQUICARDIA
    assert VALIDATED_RULES == (AROUSAL_TAQUICARDIA_BAR, HIPOXIA_TAQUICARDIA)
    assert r.enabled and r.validation_status == ValidationStatus.VALIDADO_POR_FUENTE
    assert (r.condition.domain, r.condition.descriptor) == ("respiratory", "spo2")
    assert r.condition.operator == ComparisonOperator.LESS_THAN_OR_EQUAL and r.condition.threshold == 91
    assert (r.effect.domain, r.effect.descriptor, r.effect.magnitude_delta) == ("cardiovascular", "heart_rate", 13.0)
    assert "Halliwill" in r.source and "10.1113/jphysiol.2003.050708" in r.source
    assert set(r.blocked_scenarios) == {"hypoxia", "apnea", "copd", "sepsis"}


def test_spo2_en_91_acopla_13_lpm_con_confianza_070(session_factory):
    snap = _snapshot(session_factory, {"ecg": {"heart_rate": 70.0}, "respiratory": {"spo2": 91.0}})
    with session_factory() as session:
        applied = apply_couplings(session, snap, VALIDATED_RULES, scenario=None)
        assert [a.rule_id for a in applied] == ["HIPOXIA_TAQUICARDIA"]
        coupled = get_state_by_snapshot_id(session, snap).cardiovascular.get("heart_rate_acoplado")
    assert coupled.value == pytest.approx(83.0) and coupled.provenance == Provenance.DERIVADO_ACOPLAMIENTO
    assert coupled.confidence == pytest.approx(0.70)


def test_spo2_en_92_no_acopla(session_factory):
    snap = _snapshot(session_factory, {"ecg": {"heart_rate": 70.0}, "respiratory": {"spo2": 92.0}})
    with session_factory() as session:
        assert apply_couplings(session, snap, VALIDATED_RULES, scenario=None) == []


@pytest.mark.parametrize("scenario", ["hypoxia", "apnea", "copd", "sepsis"])
def test_bloqueada_en_los_escenarios_que_ya_modelan_la_fc(session_factory, scenario):
    snap = _snapshot(session_factory, {"ecg": {"heart_rate": 70.0}, "respiratory": {"spo2": 85.0}})
    with session_factory() as session:
        assert apply_couplings(session, snap, VALIDATED_RULES, scenario=scenario) == []
        assert get_state_by_snapshot_id(session, snap).cardiovascular.get("heart_rate_acoplado") is None


def test_dos_reglas_sobre_la_misma_senal_no_escriben_ninguna(session_factory):
    """Sin política de combinación firmada no se suma ni se elige: no se escribe un valor acoplado."""
    snap = _snapshot(session_factory, {"ecg": {"heart_rate": 70.0}, "respiratory": {"spo2": 85.0},
                                       "eeg": {"alpha_power": 10.0, "beta_power": 30.0}})
    with session_factory() as session:
        state = get_state_by_snapshot_id(session, snap)
        assert state.neurological.get("bar").value > 1.8          # las dos condiciones se cumplen
        assert apply_couplings(session, snap, VALIDATED_RULES, scenario=None) == []
        assert get_state_by_snapshot_id(session, snap).cardiovascular.get("heart_rate_acoplado") is None
