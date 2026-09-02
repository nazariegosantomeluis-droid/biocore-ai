"""
Fase 1.2 — Simulador de escenarios clínicos que alimenta el UPS.

Cubre el criterio de aceptación de PLAN.md: el UPS evoluciona en el
tiempo de forma fisiológicamente coherente y consultable (histórico, no
solo el último valor).
"""

from app.engines.digital_twin_organism import DigitalTwinOrganism
from domain.physiology.scenarios import available_scenarios, run_scenario
from domain.physiology.state import (
    EventType,
    Provenance,
    create_patient,
    get_events,
    get_value_history,
    init_db,
    make_engine,
    make_session_factory,
)


def _session_factory(path):
    engine = make_engine(path)
    init_db(engine)
    return make_session_factory(engine)


def test_available_scenarios_include_the_documented_examples():
    scenarios = available_scenarios()
    assert "fibrilacion_estres" in scenarios
    assert "hipoxia_progresiva" in scenarios


def test_fibrilacion_estres_trajectory_is_monotonic_and_persisted(tmp_path):
    db_path = tmp_path / "scenario_test.db"
    SessionLocal = _session_factory(db_path)

    with SessionLocal() as session:
        patient_id = create_patient(session, display_name="Paciente Escenario")
        organism = DigitalTwinOrganism()
        steps = list(run_scenario(session, patient_id, "fibrilacion_estres", steps=8, organism=organism))

    assert len(steps) == 8
    # Todos los valores medidos/simulados deben quedar etiquetados como tal —
    # nunca presentados como si vinieran de un sensor real.
    for step in steps:
        hr = step.state.cardiovascular.get("heart_rate")
        assert hr.provenance == Provenance.SIMULACION
        assert step.state.cardiovascular.get("health_score").provenance == Provenance.DERIVADO

    # Trayectoria determinista y fisiológicamente coherente: HR sube, HRV baja
    # de forma monótona (interpolación de waypoints, no ruido aleatorio).
    hr_series = [s.state.cardiovascular.get("heart_rate").value for s in steps]
    hrv_series = [s.state.cardiovascular.get("hrv").value for s in steps]
    assert hr_series == sorted(hr_series)
    assert hrv_series == sorted(hrv_series, reverse=True)

    # Consultable como histórico persistido, no solo "el último valor" en memoria.
    with SessionLocal() as session:
        history = get_value_history(session, patient_id, "cardiovascular", "heart_rate")
    assert len(history) == 8
    assert [v for _, v in history] == hr_series


def test_hipoxia_progresiva_generates_events_as_it_worsens(tmp_path):
    db_path = tmp_path / "scenario_hipoxia.db"
    SessionLocal = _session_factory(db_path)

    with SessionLocal() as session:
        patient_id = create_patient(session, display_name="Paciente Hipoxia")
        organism = DigitalTwinOrganism()
        steps = list(run_scenario(session, patient_id, "hipoxia_progresiva", steps=10, organism=organism))

    spo2_series = [s.state.respiratory.get("spo2").value for s in steps]
    assert spo2_series == sorted(spo2_series, reverse=True)
    assert spo2_series[-1] < 90  # el escenario termina en hipoxia crítica

    with SessionLocal() as session:
        events = get_events(session, patient_id)

    event_types = {e.event_type for e in events}
    assert EventType.HYPOXIA_SPO2_CRITICAL in event_types or EventType.HYPOXIA_SPO2_LOW in event_types


def test_run_scenario_rejects_unknown_scenario_and_too_few_steps(tmp_path):
    db_path = tmp_path / "scenario_errors.db"
    SessionLocal = _session_factory(db_path)

    with SessionLocal() as session:
        patient_id = create_patient(session, display_name="Paciente Errores")

        try:
            list(run_scenario(session, patient_id, "no_existe", steps=5))
            assert False, "debía lanzar ValueError para un escenario desconocido"
        except ValueError:
            pass

        try:
            list(run_scenario(session, patient_id, "hipoxia_progresiva", steps=1))
            assert False, "debía lanzar ValueError con menos de 2 pasos"
        except ValueError:
            pass
