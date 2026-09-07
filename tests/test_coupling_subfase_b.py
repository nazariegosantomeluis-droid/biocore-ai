"""
Acoplamientos, Sub-fase B -- la primera regla validada por el experto.
Dos sistemas conversan honestamente: el arousal cortical (BAR>1.8) acelera
el corazón, declarado como DERIVADO_ACOPLAMIENTO, nunca fingido como medido.

Cubre:
  - el BAR en el EegAnalyzer, con el borde alpha~0 -> None
  - el BAR persistido como descriptor neuro, con la procedencia de origen
  - la regla AROUSAL_TAQUICARDIA_BAR (VALIDADO_POR_FUENTE, +15 bpm, BAR>1.8)
  - la prueba central por ejecución: BAR alto -> acoplado; BAR bajo -> sin
    acoplar; BAR indefinido -> sin acoplar; escenario estrés -> bloqueado;
    el narrador lo cita
"""

import numpy as np
import pytest

from app.engines.digital_twin_organism import DigitalTwinOrganism
from domain.physiology.coupling import (
    AROUSAL_TAQUICARDIA_BAR,
    COUPLING_CONFIDENCE_VALIDADO,
    VALIDATED_RULES,
    CouplingScenarioBlockedError,
    apply_couplings,
)
from domain.physiology.coupling.rules import EffectDirection, ValidationStatus
from domain.physiology.narrator.context import build_context
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
from src.signals.eeg.eeg_analyzer import (
    BAR_AROUSAL_THRESHOLD,
    EegAnalyzer,
    beta_alpha_ratio,
)


@pytest.fixture
def session_factory(tmp_path):
    engine = make_engine(tmp_path / "coupling_b.db")
    init_db(engine)
    return make_session_factory(engine)


# --- El BAR en el analizador ---------------------------------------------------

def test_beta_alpha_ratio_is_dimensionless_and_scale_free():
    # el mismo cociente para señales escaladas x1000 -- por eso el experto lo
    # eligió sobre beta_power crudo
    assert beta_alpha_ratio(30.0, 10.0) == pytest.approx(3.0)
    assert beta_alpha_ratio(30_000.0, 10_000.0) == pytest.approx(3.0)


def test_beta_alpha_ratio_is_none_when_no_alpha_rhythm():
    assert beta_alpha_ratio(10.0, 0.0) is None
    assert beta_alpha_ratio(10.0, 1e-15) is None
    assert beta_alpha_ratio(np.inf, 5.0) is None
    assert beta_alpha_ratio(5.0, np.nan) is None


def test_analyzer_bar_high_for_beta_dominant_signal():
    fs = 256.0
    t = np.arange(0, 4, 1 / fs)
    beta_dominant = 3.0 * np.sin(2 * np.pi * 20 * t) + 0.3 * np.sin(2 * np.pi * 10 * t)
    a = EegAnalyzer(fs=fs).analyze(beta_dominant)
    assert a.bar is not None and a.bar > BAR_AROUSAL_THRESHOLD


def test_analyzer_bar_low_for_alpha_dominant_signal():
    fs = 256.0
    t = np.arange(0, 4, 1 / fs)
    alpha_dominant = 3.0 * np.sin(2 * np.pi * 10 * t) + 0.3 * np.sin(2 * np.pi * 20 * t)
    a = EegAnalyzer(fs=fs).analyze(alpha_dominant)
    assert a.bar is not None and a.bar < BAR_AROUSAL_THRESHOLD


# --- El BAR persistido como descriptor neuro ---------------------------------

def test_bar_persists_with_the_band_power_provenance(session_factory):
    with session_factory() as session:
        patient_id = create_patient(session, display_name="bar-prov")
        o = DigitalTwinOrganism()
        o.update_from_sensors({"eeg": {"alpha_power": 10.0, "beta_power": 25.0,
                                       "theta_power": 3.0, "delta_power": 2.0, "gamma_power": 1.0}})
        state = from_digital_twin_organism(o, patient_id, Provenance.SIMULACION, 0.85)
        bar = state.neurological.get("bar")
        assert bar is not None
        assert bar.value == pytest.approx(25.0 / 10.0)
        assert bar.provenance == Provenance.SIMULACION          # la de origen, NO derivado
        assert bar.unit == "ratio (adimensional)"
        assert "beta_alpha_ratio" in bar.source_detail and "Schutter" in bar.source_detail


def test_bar_absent_when_no_neuro_input(session_factory):
    with session_factory() as session:
        patient_id = create_patient(session, display_name="bar-gate")
        o = DigitalTwinOrganism()
        o.update_from_sensors({"ecg": {"heart_rate": 72.0}})
        state = from_digital_twin_organism(o, patient_id, Provenance.SIMULACION, 0.85)
        assert state.neurological.descriptors == {}            # gate anti-fachada intacto


def test_bar_absent_when_alpha_is_zero(session_factory):
    with session_factory() as session:
        patient_id = create_patient(session, display_name="bar-undef")
        o = DigitalTwinOrganism()
        o.update_from_sensors({"eeg": {"alpha_power": 0.0, "beta_power": 20.0}})
        state = from_digital_twin_organism(o, patient_id, Provenance.SIMULACION, 0.85)
        assert "beta_power" in state.neurological.descriptors   # band power sí
        assert "bar" not in state.neurological.descriptors      # cociente indefinido -> no se persiste


# --- La regla validada -------------------------------------------------------

def test_the_validated_rule_is_the_expert_signed_arousal_rule():
    assert VALIDATED_RULES == (AROUSAL_TAQUICARDIA_BAR,)
    r = AROUSAL_TAQUICARDIA_BAR
    assert r.enabled is True
    assert r.validation_status == ValidationStatus.VALIDADO_POR_FUENTE
    assert r.condition.domain == "neurological" and r.condition.descriptor == "bar"
    assert r.condition.threshold == pytest.approx(1.8)
    assert r.effect.domain == "cardiovascular" and r.effect.descriptor == "heart_rate"
    assert r.effect.direction == EffectDirection.AUMENTA
    assert r.effect.magnitude_delta == pytest.approx(15.0)
    assert "Guyton" in r.source and "Schutter" in r.source and "cap. 61" in r.source


# --- helpers para la prueba central ---------------------------------------

def _snapshot_with_hr_and_eeg(session, *, beta: float, alpha: float, hr: float = 72.0):
    patient_id = create_patient(session, display_name="conversa")
    o = DigitalTwinOrganism()
    o.update_from_sensors({
        "ecg": {"heart_rate": hr, "hrv": 45.0},
        "eeg": {"alpha_power": alpha, "beta_power": beta,
                "theta_power": 3.0, "delta_power": 2.0, "gamma_power": 1.0},
    })
    state = from_digital_twin_organism(o, patient_id, Provenance.SIMULACION, 0.85)
    return patient_id, save_state(session, state)


# --- PRUEBA CENTRAL: dos sistemas conversan honestamente ------------------

def test_bar_high_couples_the_heart_rate(session_factory):
    """BAR = 40/10 = 4.0 > 1.8 -> el corazón se acelera +15, declarado."""
    with session_factory() as session:
        patient_id, snap = _snapshot_with_hr_and_eeg(session, beta=40.0, alpha=10.0, hr=72.0)

        applied = apply_couplings(session, snap, VALIDATED_RULES, scenario=None)

        assert len(applied) == 1
        ac = applied[0]
        assert ac.rule_id == "AROUSAL_TAQUICARDIA_BAR"
        assert ac.base_value == pytest.approx(72.0)
        assert ac.coupled_value == pytest.approx(72.0 + 15.0)
        assert ac.observed_value == pytest.approx(4.0)
        assert ac.provenance == Provenance.DERIVADO_ACOPLAMIENTO
        assert ac.confidence == pytest.approx(COUPLING_CONFIDENCE_VALIDADO)  # 0.70

        cv = get_state_by_snapshot_id(session, snap).cardiovascular
        # el medido, INTACTO
        assert cv.get("heart_rate").value == pytest.approx(72.0)
        assert cv.get("heart_rate").provenance == Provenance.SIMULACION
        # el acoplado, fila aparte
        d = cv.get("heart_rate_acoplado")
        assert d.value == pytest.approx(87.0)
        assert d.provenance == Provenance.DERIVADO_ACOPLAMIENTO
        assert d.confidence == pytest.approx(0.70)
        assert "AROUSAL_TAQUICARDIA_BAR" in d.source_detail
        assert "Guyton" in d.source_detail and "Schutter" in d.source_detail
        assert "disparo: bar=4" in d.source_detail
        assert "heart_rate base=72" in d.source_detail


def test_bar_low_does_not_couple(session_factory):
    """BAR = 5/25 = 0.2 < 1.8 -> la condición no se cumple, nada fabricado."""
    with session_factory() as session:
        _, snap = _snapshot_with_hr_and_eeg(session, beta=5.0, alpha=25.0, hr=72.0)
        applied = apply_couplings(session, snap, VALIDATED_RULES, scenario=None)
        assert applied == []
        cv = get_state_by_snapshot_id(session, snap).cardiovascular
        assert "heart_rate_acoplado" not in cv.descriptors
        assert cv.get("heart_rate").value == pytest.approx(72.0)


def test_bar_undefined_does_not_couple(session_factory):
    """alpha_power ~0 -> BAR None -> no hay descriptor `bar` -> la regla no
    dispara (no compara None > 1.8). Sin fila acoplada."""
    with session_factory() as session:
        _, snap = _snapshot_with_hr_and_eeg(session, beta=30.0, alpha=0.0, hr=72.0)
        state = get_state_by_snapshot_id(session, snap)
        assert "bar" not in state.neurological.descriptors
        applied = apply_couplings(session, snap, VALIDATED_RULES, scenario=None)
        assert applied == []
        assert "heart_rate_acoplado" not in state.cardiovascular.descriptors


def test_stress_scenario_is_blocked_no_double_counting(session_factory):
    """Un escritor de escenario `stress` -> CouplingScenarioBlockedError,
    sin fila acoplada (la FC del escenario ya incluye la descarga simpática)."""
    with session_factory() as session:
        _, snap = _snapshot_with_hr_and_eeg(session, beta=40.0, alpha=10.0, hr=120.0)
        with pytest.raises(CouplingScenarioBlockedError, match="doble contabilidad"):
            apply_couplings(session, snap, VALIDATED_RULES, scenario="stress")
        cv = get_state_by_snapshot_id(session, snap).cardiovascular
        assert "heart_rate_acoplado" not in cv.descriptors     # nada se escribió


def test_narrator_context_cites_the_coupled_heart_rate(session_factory):
    with session_factory() as session:
        patient_id, snap = _snapshot_with_hr_and_eeg(session, beta=40.0, alpha=10.0, hr=72.0)
        apply_couplings(session, snap, VALIDATED_RULES, scenario=None)

        ctx = build_context(session, patient_id)
        names = {d.name: d for d in ctx.descriptors}
        assert "heart_rate" in names                            # medido
        assert "heart_rate_acoplado" in names                   # acoplado, citado sin tocar el narrador
        coupled = names["heart_rate_acoplado"]
        assert coupled.domain == "cardiovascular"
        assert coupled.provenance == Provenance.DERIVADO_ACOPLAMIENTO.value
        assert coupled.value == pytest.approx(87.0)
