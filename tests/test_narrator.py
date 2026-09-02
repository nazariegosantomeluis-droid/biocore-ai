"""
Fase 1.3 — Narrador clínico.

Cubre lo que es determinista y no requiere red: construcción del contexto
estructurado desde el UPS (incluida la comparación temporal antes/ahora) y
construcción del prompt (system prompt con reglas de anclaje + mensaje de
usuario con el contexto como datos, no prosa). La llamada real a la API de
Anthropic (streaming) se verifica manualmente en la UI — no hay mock de red
aquí, ver PLAN.md para el registro de esa verificación.
"""

import json

from app.engines.digital_twin_organism import DigitalTwinOrganism
from domain.physiology.narrator import (
    DepthLevel,
    build_context,
    build_request,
    build_system_prompt,
)
from domain.physiology.scenarios import run_scenario
from domain.physiology.state import (
    Provenance,
    create_patient,
    from_digital_twin_organism,
    init_db,
    make_engine,
    make_session_factory,
    save_state,
)


def _session_factory(path):
    engine = make_engine(path)
    init_db(engine)
    return make_session_factory(engine)


def test_build_context_includes_temporal_comparison_after_trajectory(tmp_path):
    db_path = tmp_path / "narrator_test.db"
    SessionLocal = _session_factory(db_path)

    with SessionLocal() as session:
        patient_id = create_patient(session, display_name="Paciente Narrador")
        organism = DigitalTwinOrganism()
        list(run_scenario(session, patient_id, "fibrilacion_estres", steps=6, organism=organism))

    with SessionLocal() as session:
        context = build_context(session, patient_id)

    hr = next(d for d in context.descriptors if d.name == "heart_rate")
    # Trayectoria de 6 pasos ya persistida -> debe existir un "antes" real,
    # no fabricado, distinto del valor actual.
    assert hr.before_value is not None
    assert hr.before_value != hr.value
    assert hr.window_snapshot_count >= 2

    hrv = next(d for d in context.descriptors if d.name == "hrv")
    assert hrv.before_value is not None
    assert hrv.before_value > hrv.value  # hrv desciende en este escenario

    # Procedencia y confianza viajan intactas -- la regla "simulación no es
    # dato falso" debe sobrevivir hasta el contexto que ve el modelo.
    assert hr.provenance == Provenance.SIMULACION.value
    assert 0.0 <= hr.confidence <= 1.0

    health_score = next(d for d in context.descriptors if d.name == "health_score")
    assert health_score.provenance == Provenance.DERIVADO.value

    # Los eventos de este escenario (HR/HRV extremos) deben estar presentes
    # y citables por su event_type exacto.
    event_types = {e.event_type for e in context.events}
    assert event_types  # el escenario empeora lo suficiente para generar al menos uno


def test_build_context_without_history_has_no_fabricated_before_value(tmp_path):
    db_path = tmp_path / "narrator_no_history.db"
    SessionLocal = _session_factory(db_path)

    with SessionLocal() as session:
        patient_id = create_patient(session, display_name="Paciente Sin Historia")
        organism = DigitalTwinOrganism()
        organism.create_patient_scenario("healthy")
        state = from_digital_twin_organism(organism, patient_id, Provenance.SIMULACION, 0.9)
        save_state(session, state)

    with SessionLocal() as session:
        context = build_context(session, patient_id)

    hr = next(d for d in context.descriptors if d.name == "heart_rate")
    assert hr.before_value is None
    assert hr.before_timestamp is None
    assert hr.window_snapshot_count == 1


def test_build_context_raises_for_unknown_patient(tmp_path):
    db_path = tmp_path / "narrator_unknown.db"
    SessionLocal = _session_factory(db_path)

    with SessionLocal() as session:
        try:
            build_context(session, "no-existe")
            assert False, "debía lanzar ValueError para un paciente sin estado UPS"
        except ValueError:
            pass


def test_prompt_carries_data_not_prose_and_enforces_grounding_rules(tmp_path):
    db_path = tmp_path / "narrator_prompt.db"
    SessionLocal = _session_factory(db_path)

    with SessionLocal() as session:
        patient_id = create_patient(session, display_name="Paciente Prompt")
        organism = DigitalTwinOrganism()
        list(run_scenario(session, patient_id, "hipoxia_progresiva", steps=5, organism=organism))

    with SessionLocal() as session:
        context = build_context(session, patient_id)

    system_prompt, messages = build_request(context, DepthLevel.RESIDENTE)

    # El system prompt exige anclaje a descriptores/eventos y prohíbe inventar valores.
    assert "event_type" in system_prompt
    assert "no la hagas" in system_prompt or "no inventes" in system_prompt.lower()

    # El mensaje de usuario contiene el contexto como JSON parseable -- datos, no prosa.
    assert len(messages) == 1
    user_content = messages[0]["content"]
    json_start = user_content.index("```json\n") + len("```json\n")
    json_end = user_content.index("\n```", json_start)
    payload = json.loads(user_content[json_start:json_end])

    assert payload["patient_id"] == patient_id
    assert any(d["descriptor"] == "spo2" for d in payload["descriptors"])


def test_system_prompt_changes_with_depth_level():
    student = build_system_prompt(DepthLevel.ESTUDIANTE)
    expert = build_system_prompt(DepthLevel.EXPERTO)
    assert "ESTUDIANTE" in student
    assert "EXPERTO" in expert
    assert student != expert


def test_calculated_pa_surfaces_in_context_with_modelo_hemodinamico_provenance(tmp_path):
    """Conexión al UPS (2026-08-01): la PA calculada por el lazo cerrado
    (Provenance.MODELO_HEMODINAMICO) viaja hasta el contexto del narrador
    igual que cualquier otro descriptor -- build_context() no distingue
    procedencias, las expone todas. Verifica que el system prompt sabe
    tratarla honestamente (declararla como cálculo, no medición)."""
    from app.engines.simulation_engine import SimulationScenario
    from domain.physiology.hemodynamics import compute_and_attach_closed_loop_pressure
    from domain.physiology.scenarios.rich_engine import create_ephemeral_basal_patient, run_rich_scenario
    from domain.physiology.state import get_latest_snapshot_id, get_latest_state

    db_path = tmp_path / "narrator_modelo_hemodinamico.db"
    SessionLocal = _session_factory(db_path)

    with SessionLocal() as session:
        organism = DigitalTwinOrganism()
        patient_id = create_ephemeral_basal_patient(session, SimulationScenario.HEALTHY)
        list(run_rich_scenario(session, patient_id, SimulationScenario.HEALTHY, organism, start_from_current_state=False))

        snapshot_id = get_latest_snapshot_id(session, patient_id)
        heart_rate = get_latest_state(session, patient_id).cardiovascular.get("heart_rate").value
        compute_and_attach_closed_loop_pressure(session, snapshot_id=snapshot_id, scenario="healthy", heart_rate_bpm=heart_rate)

    with SessionLocal() as session:
        context = build_context(session, patient_id)

    map_modelo = next(d for d in context.descriptors if d.name == "map_modelo")
    assert map_modelo.provenance == Provenance.MODELO_HEMODINAMICO.value
    assert 0.70 <= map_modelo.confidence <= 0.80

    system_prompt = build_system_prompt(DepthLevel.ESTUDIANTE)
    assert "modelo_hemodinamico" in system_prompt
    assert "calculada" in system_prompt.lower()
    assert "no es una medición" in system_prompt or "no la confundas" in system_prompt
