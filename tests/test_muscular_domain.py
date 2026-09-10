"""
Capa 5A, dominio muscular Tanda 2 (2026-09-10) -- el cuarto dominio del UPS.

Espejo de los tests del dominio neurológico (`test_ups_state.py`
`test_neurological_domain_*`): mismo gate anti-órgano-fantasma, misma
disciplina de procedencia, mismo round-trip de persistencia. Lo que cambia:
la señal primaria del músculo es `activation` (derivable de cualquier sEMG
real), `fatigue_index` está DIFERIDO (no se persiste como descriptor --
generador demo roto, ver `_muscular_state()`), y los tres campos fantasma
(`recruitment_pattern`, `motor_symmetry`, `power_output`) nunca se escriben.
"""

import pytest

from app.engines.digital_twin_organism import DigitalTwinOrganism
from domain.physiology.state import (
    EventSeverity,
    EventType,
    Provenance,
    create_patient,
    from_digital_twin_organism,
    get_latest_state,
    init_db,
    make_engine,
    make_session_factory,
    save_state,
)


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "ups_muscular_test.db"


def _session_factory(path):
    engine = make_engine(path)
    init_db(engine)
    return make_session_factory(engine)


def test_muscular_domain_gate_prevents_ghost_muscle(db_path):
    """La prueba que importa: un escritor que NO pasa `activation` no debe
    sembrar un músculo fantasma con los defaults de `MusculoskeletalDetail`
    (recruitment_pattern=50.0, neuromuscular_efficiency=80.0, ...) ni con
    `health_score`/`risk_score` en su valor de fábrica. Sin `activation` ->
    `muscular.descriptors == {}`. Espejo exacto del gate del neuro."""
    SessionLocal = _session_factory(db_path)

    with SessionLocal() as session:
        patient_id = create_patient(session, display_name="Paciente Gate Muscular")

        # Solo cardio -> muscular debe quedar vacío.
        cardio_organism = DigitalTwinOrganism()
        cardio_organism.update_from_sensors({"ecg": {"heart_rate": 88.0, "hrv": 45.0}})
        cardio_state = from_digital_twin_organism(cardio_organism, patient_id, Provenance.SIMULACION, 0.9)

        assert cardio_state.cardiovascular.descriptors  # sí hay datos cardíacos
        assert cardio_state.muscular.descriptors == {}  # músculo NO fabricado

        # Solo EMG -> muscular poblado, el resto vacío.
        emg_organism = DigitalTwinOrganism()
        emg_organism.update_from_sensors({
            "emg": {"activation": 45.0, "median_frequency": 110.0, "efficiency": 72.0}
        })
        emg_state = from_digital_twin_organism(emg_organism, patient_id, Provenance.SIMULACION, 0.9)

        assert emg_state.muscular.descriptors  # sí hay datos musculares
        assert emg_state.cardiovascular.descriptors == {}  # corazón NO fabricado
        assert emg_state.respiratory.descriptors == {}  # pulmón NO fabricado
        assert emg_state.neurological.descriptors == {}  # cerebro NO fabricado


def test_muscular_domain_persists_only_the_honest_descriptors(db_path):
    """`activation` + `median_frequency` con la procedencia del llamador;
    `health_score`/`risk_score`/`neuromuscular_efficiency`/`movement_smoothness`
    como `DERIVADO`. NADA más -- ni `fatigue_index` (diferido), ni los tres
    fantasma."""
    SessionLocal = _session_factory(db_path)

    with SessionLocal() as session:
        patient_id = create_patient(session, display_name="Paciente Descriptores Musculares")

        organism = DigitalTwinOrganism()
        organism.update_from_sensors({
            "emg": {"activation": 45.0, "median_frequency": 110.0, "efficiency": 72.0}
        })
        state = from_digital_twin_organism(organism, patient_id, Provenance.SIMULACION, 0.9)

        assert set(state.muscular.descriptors.keys()) == {
            "activation", "median_frequency",
            "health_score", "risk_score",
            "neuromuscular_efficiency", "movement_smoothness",
        }

        # Señales primarias: procedencia del llamador, unidad honesta.
        assert state.muscular.get("activation").value == pytest.approx(45.0)
        assert state.muscular.get("activation").provenance == Provenance.SIMULACION
        assert state.muscular.get("activation").unit == "%"
        assert state.muscular.get("median_frequency").value == pytest.approx(110.0)
        assert state.muscular.get("median_frequency").provenance == Provenance.SIMULACION
        assert state.muscular.get("median_frequency").unit == "Hz"

        # Derivados por el organismo: DERIVADO, sin importar la procedencia de origen.
        assert state.muscular.get("health_score").provenance == Provenance.DERIVADO
        assert state.muscular.get("risk_score").provenance == Provenance.DERIVADO
        assert state.muscular.get("neuromuscular_efficiency").provenance == Provenance.DERIVADO
        assert state.muscular.get("movement_smoothness").provenance == Provenance.DERIVADO


def test_fatigue_index_is_deferred_even_when_present_in_signals(db_path):
    """`fatigue_index` puede venir en `muscles.metrics.signals` (slider de
    Twin OS, o `simulate_intervention('exercise')`), pero NO se persiste
    como descriptor en esta tanda -- el generador demo lo clava en 0 y
    persistir una constante disfrazada de medición viola el Art. I."""
    SessionLocal = _session_factory(db_path)

    with SessionLocal() as session:
        patient_id = create_patient(session, display_name="Paciente Fatiga Diferida")

        organism = DigitalTwinOrganism()
        organism.update_from_sensors({
            "emg": {"activation": 50.0, "median_frequency": 95.0, "fatigue_index": 65.0}
        })
        state = from_digital_twin_organism(organism, patient_id, Provenance.SIMULACION, 0.9)

        assert "fatigue_index" not in state.muscular.descriptors


def test_muscular_phantom_detail_fields_are_never_persisted(db_path):
    """`recruitment_pattern`/`motor_symmetry`/`power_output`
    (`MusculoskeletalDetail`) nunca los asigna `_update_muscles()` -- se
    quedan en su default de dataclass. No deben aparecer como descriptor
    (análogo a `frontal_activity`/`temporal_activity` en el neuro)."""
    SessionLocal = _session_factory(db_path)

    with SessionLocal() as session:
        patient_id = create_patient(session, display_name="Paciente Fantasmas Musculares")

        organism = DigitalTwinOrganism()
        organism.update_from_sensors({"emg": {"activation": 45.0, "median_frequency": 110.0}})
        state = from_digital_twin_organism(organism, patient_id, Provenance.SIMULACION, 0.9)

        assert "recruitment_pattern" not in state.muscular.descriptors
        assert "motor_symmetry" not in state.muscular.descriptors
        assert "power_output" not in state.muscular.descriptors


def test_muscular_domain_survives_persistence_round_trip(db_path):
    """El dominio muscular persiste y se recupera igual que los otros tres
    -- confirma que `all_domains()`/`save_state()`/`get_latest_state()` lo
    incluyen de punta a punta, no solo en memoria."""
    SessionLocal = _session_factory(db_path)

    with SessionLocal() as session:
        patient_id = create_patient(session, display_name="Paciente Muscular Roundtrip")
        organism = DigitalTwinOrganism()
        organism.update_from_sensors({"emg": {"activation": 38.0, "median_frequency": 120.0}})
        state = from_digital_twin_organism(organism, patient_id, Provenance.SIMULACION, 0.9)
        save_state(session, state)

    with SessionLocal() as session:  # sesión distinta -- simula proceso nuevo
        latest = get_latest_state(session, patient_id)
        assert latest is not None
        assert "muscular" in latest.all_domains()
        assert latest.muscular.get("activation").value == pytest.approx(38.0)
        assert latest.muscular.get("median_frequency").value == pytest.approx(120.0)
        assert "fatigue_index" not in latest.muscular.descriptors


def test_severe_muscle_fatigue_event_uses_same_threshold_as_organism(db_path):
    """El evento muscular reutiliza el umbral que YA vive en
    `DigitalTwinOrganism._update_muscles()` (`fatigue > 80` -> tier más alto
    de `risk_score`) -- no un umbral clínico inventado aquí. El evento lee
    `fatigue_index` de la señal cruda del organismo aunque ese valor NO se
    persista como descriptor (igual que `HIGH_STRESS_EEG` lee `stress_level`)."""
    SessionLocal = _session_factory(db_path)

    with SessionLocal() as session:
        patient_id = create_patient(session, display_name="Paciente Fatiga Severa EMG")

        fatigued_organism = DigitalTwinOrganism()
        fatigued_organism.update_from_sensors({
            "emg": {"activation": 60.0, "median_frequency": 55.0, "fatigue_index": 90.0}
        })
        fatigued_state = from_digital_twin_organism(fatigued_organism, patient_id, Provenance.SIMULACION, 0.9)

        fatigue_events = [
            e for e in fatigued_state.events if e.event_type == EventType.SEVERE_MUSCLE_FATIGUE_EMG
        ]
        assert len(fatigue_events) == 1
        assert fatigue_events[0].domain == "muscular"
        assert fatigue_events[0].severity == EventSeverity.WARNING
        assert fatigue_events[0].related_descriptor == "movement_smoothness"

        # Bajo el umbral -> sin evento.
        ok_organism = DigitalTwinOrganism()
        ok_organism.update_from_sensors({
            "emg": {"activation": 40.0, "median_frequency": 115.0, "fatigue_index": 30.0}
        })
        ok_state = from_digital_twin_organism(ok_organism, patient_id, Provenance.SIMULACION, 0.9)
        assert not [
            e for e in ok_state.events if e.event_type == EventType.SEVERE_MUSCLE_FATIGUE_EMG
        ]
