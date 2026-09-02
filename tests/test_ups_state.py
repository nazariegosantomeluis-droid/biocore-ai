"""
Fase 1.1 — Unified Physiological State.

Cubre el criterio de aceptación de PLAN.md:
(a) crear un paciente, escribir su estado y recuperarlo entre sesiones;
(b) guardar y recuperar una serie temporal de estados, y consultar cómo
    cambió un valor concreto (HRV) entre dos momentos.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.engines.digital_twin_organism import DigitalTwinOrganism
from domain.physiology.state import (
    DomainState,
    EventSeverity,
    EventType,
    PhysiologicalDescriptor,
    Provenance,
    UnifiedPhysiologicalState,
    create_patient,
    from_digital_twin_organism,
    get_events,
    get_latest_state,
    get_snapshot_id_at,
    get_state_by_snapshot_id,
    get_value_history,
    init_db,
    make_engine,
    make_session_factory,
    save_state,
)


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "ups_test.db"


def _session_factory(path):
    """Crea un engine + sessionmaker nuevos apuntando al mismo archivo —
    simula un proceso/sesión distinto leyendo lo que otro ya persistió."""
    engine = make_engine(path)
    init_db(engine)
    return make_session_factory(engine)


def test_create_patient_write_state_and_recover_across_sessions(db_path):
    # "Sesión" 1: crea paciente y escribe su estado a partir de un escenario simulado.
    SessionA = _session_factory(db_path)
    with SessionA() as session:
        patient_id = create_patient(session, display_name="Paciente Demo", external_id="demo-1")

        organism = DigitalTwinOrganism()
        organism.create_patient_scenario("healthy")
        state = from_digital_twin_organism(
            organism,
            patient_id=patient_id,
            provenance=Provenance.SIMULACION,
            confidence=0.9,
            source_detail="escenario:healthy",
        )
        save_state(session, state)

    # "Sesión" 2: nuevo engine/sessionmaker sobre el mismo archivo — sin memoria
    # compartida con la sesión anterior (equivalente a reiniciar la app).
    SessionB = _session_factory(db_path)
    with SessionB() as session:
        recovered = get_latest_state(session, patient_id)

    assert recovered is not None
    assert recovered.patient_id == patient_id

    hr = recovered.cardiovascular.get("heart_rate")
    assert hr is not None
    assert hr.value == pytest.approx(72.0)
    assert hr.provenance == Provenance.SIMULACION
    assert hr.confidence == pytest.approx(0.9)
    assert hr.source_detail == "escenario:healthy"

    spo2 = recovered.respiratory.get("spo2")
    assert spo2 is not None
    assert spo2.value == pytest.approx(98.0)
    assert spo2.provenance == Provenance.SIMULACION

    # Los valores calculados por el organismo (no medidos/simulados) siempre
    # se marcan como derivados, sin importar la procedencia del resto.
    health_score = recovered.cardiovascular.get("health_score")
    assert health_score is not None
    assert health_score.provenance == Provenance.DERIVADO


def test_temporal_query_hrv_between_two_moments(db_path):
    SessionLocal = _session_factory(db_path)

    t0 = datetime(2026, 7, 2, 8, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(minutes=10)
    t2 = t0 + timedelta(minutes=20)
    hrv_values = {t0: 60.0, t1: 45.0, t2: 20.0}  # trayectoria: estrés autonómico creciente

    with SessionLocal() as session:
        patient_id = create_patient(session, display_name="Paciente Temporal")

        for ts, hrv in hrv_values.items():
            state = UnifiedPhysiologicalState(
                patient_id=patient_id,
                timestamp=ts,
                cardiovascular=DomainState(
                    domain="cardiovascular",
                    descriptors={
                        "hrv": PhysiologicalDescriptor(
                            "hrv", hrv, "ms", Provenance.SIMULACION, 0.9, "escenario:estres_progresivo"
                        ),
                    },
                ),
                respiratory=DomainState(domain="respiratory", descriptors={}),
            )
            save_state(session, state)

    with SessionLocal() as session:
        full_history = get_value_history(session, patient_id, "cardiovascular", "hrv")
        windowed = get_value_history(session, patient_id, "cardiovascular", "hrv", start=t1, end=t2)

    assert [v for _, v in full_history] == [60.0, 45.0, 20.0]
    assert [ts for ts, _ in full_history] == [t0, t1, t2]

    assert [v for _, v in windowed] == [45.0, 20.0]


def test_events_are_first_class_and_persisted(db_path):
    SessionLocal = _session_factory(db_path)

    with SessionLocal() as session:
        patient_id = create_patient(session, display_name="Paciente Eventos")

        cardio_organism = DigitalTwinOrganism()
        cardio_organism.create_patient_scenario("arrhythmia")  # hr=95, hrv=15 -> HRV bajo
        cardio_state = from_digital_twin_organism(cardio_organism, patient_id, Provenance.SIMULACION, 0.9)
        save_state(session, cardio_state)

        resp_organism = DigitalTwinOrganism()
        resp_organism.create_patient_scenario("copd")  # spo2=88 -> hipoxia crítica
        resp_state = from_digital_twin_organism(
            resp_organism, patient_id, Provenance.SIMULACION, 0.9, source_detail="escenario:copd"
        )
        save_state(session, resp_state)

    assert any(e.event_type == EventType.LOW_HRV_AUTONOMIC_STRESS for e in cardio_state.events)
    assert any(e.event_type == EventType.HYPOXIA_SPO2_CRITICAL for e in resp_state.events)

    with SessionLocal() as session:
        persisted_events = get_events(session, patient_id)

    event_types = {e.event_type for e in persisted_events}
    assert EventType.LOW_HRV_AUTONOMIC_STRESS in event_types
    assert EventType.HYPOXIA_SPO2_CRITICAL in event_types

    hypoxia_event = next(e for e in persisted_events if e.event_type == EventType.HYPOXIA_SPO2_CRITICAL)
    assert hypoxia_event.severity == EventSeverity.CRITICAL
    assert hypoxia_event.domain == "respiratory"
    assert hypoxia_event.related_descriptor == "spo2"


def test_get_snapshot_id_at_and_get_state_by_snapshot_id_resolve_a_non_latest_snapshot(db_path):
    """Conexión PA calculada al caso clínico de Academia (2026-08-06): el
    horizonte que `case_bank.generate_case()` elige no es necesariamente
    el último snapshot persistido -- `get_latest_snapshot_id()`/
    `get_latest_state()` darían el snapshot equivocado. Verifica que
    `get_snapshot_id_at()` resuelve el snapshot EXACTO de un timestamp
    intermedio, y que `get_state_by_snapshot_id()` lo relee completo."""
    SessionLocal = _session_factory(db_path)

    t0 = datetime(2026, 8, 6, 8, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(minutes=5)
    t2 = t0 + timedelta(minutes=30)

    with SessionLocal() as session:
        patient_id = create_patient(session, display_name="Paciente Snapshot Intermedio")
        snapshot_ids = {}
        for ts, hr in ((t0, 72.0), (t1, 85.0), (t2, 150.0)):
            state = UnifiedPhysiologicalState(
                patient_id=patient_id,
                timestamp=ts,
                cardiovascular=DomainState(
                    domain="cardiovascular",
                    descriptors={
                        "heart_rate": PhysiologicalDescriptor(
                            "heart_rate", hr, "bpm", Provenance.SIMULACION, 0.9, "escenario:trayectoria"
                        ),
                    },
                ),
                respiratory=DomainState(domain="respiratory", descriptors={}),
            )
            snapshot_ids[ts] = save_state(session, state)

    with SessionLocal() as session:
        # t1 es el horizonte "intermedio" (5 min) -- NO el más reciente (t2, 30 min).
        resolved_id = get_snapshot_id_at(session, patient_id, t1)
        assert resolved_id == snapshot_ids[t1]
        assert resolved_id != snapshot_ids[t2]  # confirma que no cae al último por accidente

        reread = get_state_by_snapshot_id(session, resolved_id)
        assert reread is not None
        assert reread.cardiovascular.get("heart_rate").value == pytest.approx(85.0)

        # snapshot_id inexistente -> None, no una excepción.
        assert get_state_by_snapshot_id(session, "no-existe") is None
        assert get_snapshot_id_at(session, patient_id, t0 + timedelta(days=1)) is None


def test_neurological_domain_gate_prevents_ghost_brain(db_path):
    """Capa 5A, Sub-fase 1 (2026-08-30): mismo gate anti-órgano-fantasma
    que cardiovascular/respiratorio (Fase 2.4), aplicado al tercer dominio.
    Un escritor que solo pasa datos cardíacos NO debe sembrar un cerebro
    fantasma con los defaults de `NeurologicalDetail` (mental_workload=40.0,
    etc.) — y viceversa: solo-EEG no debe fabricar corazón/pulmones."""
    SessionLocal = _session_factory(db_path)

    with SessionLocal() as session:
        patient_id = create_patient(session, display_name="Paciente Gate Neuro")

        # Solo cardio -> neurological debe quedar vacío.
        cardio_organism = DigitalTwinOrganism()
        cardio_organism.update_from_sensors({"ecg": {"heart_rate": 88.0, "hrv": 45.0}})
        cardio_state = from_digital_twin_organism(cardio_organism, patient_id, Provenance.SIMULACION, 0.9)

        assert cardio_state.cardiovascular.descriptors  # sí hay datos cardíacos
        assert cardio_state.neurological.descriptors == {}  # cerebro NO fabricado
        assert cardio_state.respiratory.descriptors == {}  # pulmón tampoco (gate ya existente, sigue igual)

        # Solo EEG -> cardiovascular/respiratory deben quedar vacíos.
        eeg_organism = DigitalTwinOrganism()
        eeg_organism.update_from_sensors({
            "eeg": {"alpha_power": 12.5, "beta_power": 7.2, "theta_power": 3.1, "delta_power": 1.1, "gamma_power": 0.9}
        })
        eeg_state = from_digital_twin_organism(eeg_organism, patient_id, Provenance.SIMULACION, 0.9)

        assert eeg_state.neurological.descriptors  # sí hay datos neuro
        assert eeg_state.cardiovascular.descriptors == {}  # corazón NO fabricado
        assert eeg_state.respiratory.descriptors == {}  # pulmón NO fabricado

        # Los 5 band power + los 5 detail + health_score/risk_score = 12.
        assert set(eeg_state.neurological.descriptors.keys()) == {
            "delta_power", "theta_power", "alpha_power", "beta_power", "gamma_power",
            "health_score", "risk_score",
            "mental_workload", "cognitive_fatigue", "attention", "stress_perception", "sleepiness",
        }
        assert eeg_state.neurological.get("alpha_power").value == pytest.approx(12.5)
        assert eeg_state.neurological.get("alpha_power").provenance == Provenance.SIMULACION
        assert eeg_state.neurological.get("health_score").provenance == Provenance.DERIVADO

        # `frontal_activity`/`temporal_activity` (NeurologicalDetail) nunca
        # se asignan en `_update_brain()` -- no deben aparecer como
        # descriptor (evitar persistir una constante disfrazada de dato).
        assert "frontal_activity" not in eeg_state.neurological.descriptors
        assert "temporal_activity" not in eeg_state.neurological.descriptors


def test_neurological_domain_survives_persistence_round_trip(db_path):
    """El dominio neuro persiste y se recupera igual que cardio/respiratorio
    -- confirma que `all_domains()`/`get_latest_state()` lo incluyen de
    punta a punta, no solo en memoria."""
    SessionLocal = _session_factory(db_path)

    with SessionLocal() as session:
        patient_id = create_patient(session, display_name="Paciente Neuro Roundtrip")
        organism = DigitalTwinOrganism()
        organism.update_from_sensors({"eeg": {"alpha_power": 20.0, "beta_power": 4.0}})
        state = from_digital_twin_organism(organism, patient_id, Provenance.SIMULACION, 0.9)
        save_state(session, state)

    with SessionLocal() as session:  # sesión distinta -- simula proceso nuevo
        latest = get_latest_state(session, patient_id)
        assert latest is not None
        assert "neurological" in latest.all_domains()
        assert latest.neurological.get("alpha_power").value == pytest.approx(20.0)


def test_high_stress_eeg_event_uses_same_threshold_as_organism(db_path):
    """El evento neuro reutiliza el umbral que YA vive en
    `DigitalTwinOrganism._update_brain()` (`stress_level > 75`, el tier más
    alto que ese método define) -- no un umbral clínico inventado aquí."""
    SessionLocal = _session_factory(db_path)

    with SessionLocal() as session:
        patient_id = create_patient(session, display_name="Paciente Estrés EEG")

        stressed_organism = DigitalTwinOrganism()
        stressed_organism.update_from_sensors({"eeg": {"alpha_power": 5.0, "beta_power": 20.0, "stress_level": 90.0}})
        stressed_state = from_digital_twin_organism(stressed_organism, patient_id, Provenance.SIMULACION, 0.9)

        stress_events = [e for e in stressed_state.events if e.event_type == EventType.HIGH_STRESS_EEG]
        assert len(stress_events) == 1
        assert stress_events[0].domain == "neurological"
        assert stress_events[0].severity == EventSeverity.WARNING
        assert stress_events[0].related_descriptor == "stress_perception"

        # Bajo el umbral -> sin evento.
        calm_organism = DigitalTwinOrganism()
        calm_organism.update_from_sensors({"eeg": {"alpha_power": 15.0, "beta_power": 5.0, "stress_level": 30.0}})
        calm_state = from_digital_twin_organism(calm_organism, patient_id, Provenance.SIMULACION, 0.9)
        assert not [e for e in calm_state.events if e.event_type == EventType.HIGH_STRESS_EEG]
