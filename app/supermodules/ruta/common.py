"""Lo que comparten las unidades de la Ruta (T4, 2026-11-18): la estación 0 (un paciente nuevo desde un escenario del
simulador), la práctica con un banco firmado y el cierre con el mismo paciente.

Se movió de `corazon.py` (T3) sin cambiar su comportamiento; cada unidad lo llama con su clave, su título y su prefijo.
"""

from __future__ import annotations

from typing import Optional, Sequence

import streamlit as st

from app.supermodules.ruta import model as M

# Escenarios del simulador para la estación 0 de Corazón e Integración (diseño: «sano, hipertensión o sepsis»; los tres
# con lazo cerrado). Cada unidad elige los suyos de `SCENARIO_LABELS` (T4): todos son escenarios de `SimulationScenario`.
SCENARIOS = {"healthy": "Sano", "hypertension": "Hipertensión", "sepsis": "Sepsis"}
SCENARIO_LABELS = {**SCENARIOS, "hypoxia": "Hipoxia", "apnea": "Apnea", "copd": "EPOC", "stress": "Estrés",
                   "anxiety": "Ansiedad", "fatigue": "Fatiga"}
SCENARIO_SEED = 0          # la instancia de «sano» se declara con su semilla, como en el gemelo
SAVED_NOW_KEY = "ruta_saved_now"

START_NOTE = ("El paciente se crea nuevo con el escenario elegido y pasa a ser el paciente activo de toda la app (el "
              "banner, el gemelo y las páginas de Explorar lo verán). Todos sus valores son simulación: el simulador "
              "los calcula en 6 horizontes (ahora, 5 min, 30 min, 2 h, 24 h y 7 días) y el último es el que queda.")


# ───────────────────────────── estación 0 ─────────────────────────────

def create_unit_patient(unit_key: str, unit_title: str, prefix: str, scenario_key: str) -> None:
    from app.engines.digital_twin_organism import DigitalTwinOrganism
    from app.engines.simulation_engine import SimulationScenario
    from app.utils.patient_banner import HORIZON_ES, INPUT_SOURCE_KEY
    from app.utils.patient_session import _DISPLAY_NAME_KEY, get_active_session_factory, set_active_patient_id
    from domain.physiology.scenarios.rich_engine import run_rich_scenario
    from domain.physiology.state import create_patient, horizon_of

    name = f"{unit_title} · {SCENARIO_LABELS[scenario_key]}"
    rows = []
    with get_active_session_factory()() as session:
        patient_id = create_patient(session, display_name=name)
        for step in run_rich_scenario(session, patient_id, SimulationScenario(scenario_key), DigitalTwinOrganism(),
                                      start_from_current_state=False, seed=SCENARIO_SEED):
            hr = step.state.cardiovascular.get("heart_rate")
            rr = step.state.respiratory.get("respiratory_rate")
            spo2 = step.state.respiratory.get("spo2")
            horizon = horizon_of(hr.source_detail) if hr is not None else None
            rows.append({"Horizonte": HORIZON_ES.get(horizon, horizon) or "—",
                         "FC (lpm)": None if hr is None else round(hr.value),
                         "FR (rpm)": None if rr is None else round(rr.value),
                         "SpO₂ (%)": None if spo2 is None else round(spo2.value)})
    set_active_patient_id(patient_id)
    st.session_state[_DISPLAY_NAME_KEY] = name
    # Revisión final de la T3: el organismo en memoria del gemelo y su «fuente activa» eran del paciente anterior (p.
    # ej. una arritmia aplicada allí). Sin quitarlos, el ECG de este paciente declinaba «ritmo no modelado» y el banner
    # decía una fuente que no es la suya. El gemelo los vuelve a crear al abrirse, con los sliders desde este paciente.
    st.session_state.pop(INPUT_SOURCE_KEY, None)
    st.session_state.pop("twin_shell_organism", None)
    last = rows[-1] if rows else {}
    M.reset_unit(unit_key, prefix, keep=(f"{prefix}scenario", f"{prefix}start"))
    M.progress(unit_key).update(
        patient_id=patient_id, scenario=scenario_key, trajectory=rows,
        start={"hr": last.get("FC (lpm)"), "rr": last.get("FR (rpm)"), "spo2": last.get("SpO₂ (%)")})


def render_patient_station(unit_key: str, unit_title: str, prefix: str, scenarios: Sequence[str] = tuple(SCENARIOS),
                           note: Optional[str] = None) -> None:
    """`note`: lo que el escenario NO fija de esta unidad (p. ej. el simulador no genera EEG ni EMG)."""
    from app.engines.simulation_engine import SimulationEngine, SimulationScenario
    from src.clinical import sepsis_trajectory

    p = M.progress(unit_key)
    if p["patient_id"]:
        st.markdown(f"**Tu paciente:** {unit_title} · {SCENARIO_LABELS[p['scenario']]} (`{p['patient_id'][:8]}`), "
                    "simulación del escenario.")
        st.dataframe(p["trajectory"], hide_index=True, width="stretch")
        st.caption("Valores que calculó el simulador en cada horizonte; el último es el estado de tu paciente.")
    st.markdown("Elige el escenario del simulador con el que empieza tu paciente.")
    options = list(scenarios)
    # El selector no se dibuja en las demás estaciones y Streamlit olvida su valor: vuelve al escenario del paciente.
    current = options.index(p["scenario"]) if p["scenario"] in options else 0
    choice = st.radio("Escenario del simulador", options, index=current, format_func=SCENARIO_LABELS.get,
                      horizontal=True, key=f"{prefix}scenario")
    if choice == "healthy":
        st.info(SimulationEngine(seed=SCENARIO_SEED).instance_declaration(SimulationScenario.HEALTHY))
    elif choice == "sepsis":
        st.info(sepsis_trajectory.declare_trajectory())
    else:
        st.caption("Trayectoria del simulador de escenarios (SimulationEngine): simulación.")
    st.caption(START_NOTE)
    if note:
        st.caption(note)
    label = "Empezar con este paciente" if not p["patient_id"] else "Empezar de nuevo con este escenario"
    if st.button(label, key=f"{prefix}start", type="primary"):
        with st.spinner("Calculando los 6 horizontes del escenario…"):
            create_unit_patient(unit_key, unit_title, prefix, choice)
        st.rerun()


def saved_now(snapshot_id: Optional[str]) -> None:
    """Una estación guardó: la franja lo dice en la pasada siguiente, y la página se vuelve a dibujar para que el hilo
    y la estación ya lean el valor nuevo."""
    if snapshot_id:
        st.session_state[SAVED_NOW_KEY] = snapshot_id
        st.rerun()


def out_of_control_range(vitals, ranges) -> list:
    """Qué valor del paciente no cabe en los controles de un instrumento (entonces el instrumento no empieza en él y
    la estación no ofrece guardar: no se le escribe al paciente un valor que no es el suyo). `ranges`: tuplas
    `(clave de VITALS, rótulo, unidad, (mínimo, máximo))`. Revisión final de la T4."""
    problems = []
    for key, label, unit, (lo, hi) in ranges:
        d = vitals.values[key]
        if d is not None and not lo <= round(d.value) <= hi:
            problems.append(f"La {label} de tu paciente ({d.value:.0f} {unit}) está fuera del rango de la simulación "
                            f"({lo}–{hi} {unit})")
    return problems


def render_out_of_range(problems: list) -> None:
    st.warning("; ".join(problems) + ". La simulación empieza en otro valor, así que esta estación no ofrece guardar: "
               "no se le escribe a tu paciente un valor que no es el suyo.")


# ───────────────────────────── práctica con un banco firmado ─────────────────────────────

def render_bank_practice(questions: Sequence, bank: str, key_prefix: str, unit_key: str) -> None:
    """Preguntas de un banco firmado con la confianza declarada (o «sin declarar»), con la misma tarjeta y la misma
    retroalimentación del quiz de Temas.

    Dos registros distintos (revisión final de la T4):
    - la SESIÓN: cada pregunta una sola vez en toda la sesión, con su concepto (`quiz_bank.CONCEPT_BY_PROMPT`; sin
      concepto no se registra), como en Temas (`bc_logged_items`);
    - la UNIDAD: cada pregunta una vez por recorrido (`answered` del avance, que «Empezar de nuevo» vacía); es lo que
      cuenta el cierre. Antes, tras empezar de nuevo, la sesión no volvía a registrar la pregunta y el cierre decía que
      no había respuestas."""
    from app.supermodules.ui_topic import CONFIDENCE_OPTIONS, NOT_DECLARED, render_answer_feedback
    from app.utils.session_learning import log_session_answer
    from educational.learning_analytics import question_id
    from educational.quiz_bank import CONCEPT_BY_PROMPT

    p = M.progress(unit_key)
    for i, q in enumerate(questions):
        base = f"{key_prefix}q_{i}"
        with st.container(key=f"bc_card_{base}"):
            st.markdown(f"**{q.prompt}**")
            choice = st.radio("Opciones", q.display_choices(), index=None, key=f"{base}_choice",
                              label_visibility="collapsed")
            conf = st.select_slider("Tu confianza (0 a 100)", CONFIDENCE_OPTIONS, value=NOT_DECLARED,
                                    key=f"{base}_conf")
            if st.button("Comprobar", key=f"{base}_check", disabled=choice is None):
                st.session_state[f"{base}_done"] = (choice, conf)
            done = st.session_state.get(f"{base}_done")
            if not done:
                continue
            ok = q.is_correct(done[0])
            render_answer_feedback(q, ok)
            item = f"{bank}:{question_id(bank, q.prompt)}"
            concept = CONCEPT_BY_PROMPT.get(q.prompt)
            confidence = None if done[1] == NOT_DECLARED else int(done[1])
            logged = st.session_state.setdefault("bc_logged_items", set())
            if concept is not None and item not in logged:
                log_session_answer(item, "quiz", concept, ok, confidence)
                logged.add(item)
            answered = p.setdefault("answered", set())
            if item not in answered:
                answered.add(item)
                p.setdefault("answers", []).append({"item_id": item, "source": "quiz", "concept": concept,
                                                    "correct": bool(ok), "confidence": confidence})


# ───────────────────────────── cierre ─────────────────────────────

def render_closing_summary(unit_key: str, unit_title: str) -> None:
    """Tu paciente al final: el mismo paciente, sus valores ahora y al empezar (cada uno con su procedencia) y lo que se
    practicó en las estaciones de la unidad."""
    from app.utils import navigation as nav
    from app.utils.patient_banner import UNIT_ES, VITALS, read_active_vitals, vital_provenance_text

    p = M.progress(unit_key)
    vitals = read_active_vitals()
    st.markdown(f"#### Tu paciente al final · {unit_title} · {SCENARIO_LABELS[p['scenario']]} (`{p['patient_id'][:8]}`)")
    now, start = [], []
    for key, label, *_rest in VITALS:
        d = vitals.values[key]
        now.append(f"{label} sin dato" if d is None else
                   f"{label} {d.value:.0f} {UNIT_ES.get(d.unit, d.unit)} "
                   f"({vital_provenance_text(d, vitals.origins.get(key))})")
        s = p["start"].get(key)
        unit = {"hr": "lpm", "rr": "rpm", "spo2": "%"}[key]
        start.append(f"{label} sin dato" if s is None else f"{label} {s:.0f} {unit}")
    st.markdown("**Ahora:** " + " · ".join(now))
    st.markdown("**Al empezar (estación 0):** " + " · ".join(start))
    st.caption("Si un valor cambió, es porque algo guardó una medición nueva de tu paciente (una estación de la ruta "
               "u otra página, como Variabilidad cardiaca o el gemelo); su procedencia dice de dónde salió.")

    answers = p.get("answers", [])
    if answers:
        correct = sum(bool(r.get("correct")) for r in answers)
        st.markdown(f"**Lo que practicaste en esta unidad:** {len(answers)} "
                    f"{'respuesta' if len(answers) == 1 else 'respuestas'}, {correct} "
                    f"{'correcta' if correct == 1 else 'correctas'} (solo las de sus estaciones, desde que empezaste).")
    else:
        st.markdown("**Lo que practicaste en esta unidad:** todavía no hay respuestas en sus estaciones.")
    nav.link("mi-sesion", "Tu aprendizaje en esta sesión")


def render_theory(*topics) -> None:
    from app.utils.design_system import render_theory_topic

    for topic in topics:
        render_theory_topic(topic)
