"""Unidad Corazón (T3 de la ruta integrada, 2026-11-18).

Cada estación usa contenido que ya existe y está firmado (diseño, tabla «Unidad · Contenido firmado que ya existe»):
los temas 1–5 de `teoria_citada.md`, el registro real PTB s0010, el instrumento `ecg_trazo`, la calculadora de QTc
(`clinical/calculators.py`), el quiz del tema «Frecuencia cardiaca» y «¿Qué pasa si…?». Lo único que se escribe aquí
son rótulos de interfaz y frases que describen los datos del paciente; ningún texto médico nuevo.

El paciente de la unidad sale de un escenario del simulador (`run_rich_scenario`, procedencia simulación) en un
paciente NUEVO que pasa a ser el paciente activo de toda la app: es el que late en el ECG, el que carga la calculadora
y el que se cierra al final.
"""

from __future__ import annotations

import streamlit as st

from app.supermodules.ruta import model as M

UNIT_KEY = "corazon"
UNIT_TITLE = "Unidad Corazón"
PREFIX = "ruta_corazon_"

# Escenarios del simulador para la estación 0 (diseño: «sano, hipertensión o sepsis en Corazón»).
SCENARIOS = {"healthy": "Sano", "hypertension": "Hipertensión", "sepsis": "Sepsis"}
SCENARIO_SEED = 0          # la instancia de «sano» se declara con su semilla, como en el gemelo

START_NOTE = ("El paciente se crea nuevo con el escenario elegido y pasa a ser el paciente activo de toda la app (el "
              "banner, el gemelo y las páginas de Explorar lo verán). Todos sus valores son simulación: el simulador "
              "los calcula en 6 horizontes (ahora, 5 min, 30 min, 2 h, 24 h y 7 días) y el último es el que queda.")
MIDE_NOTE = ("Con la fuente «Paciente activo» esta estación solo lee: el trazo se dibuja a la FC que el UPS ya tiene de "
             "tu paciente, y guardarlo no añadiría ningún dato. Para guardar una FC medida, elige un caso clínico, "
             "MIT-BIH o PTB-XL: si la compuerta la acepta, esa FC pasa a ser la de tu paciente en las estaciones "
             "siguientes.")
ALTERA_NOTE = ("Los casos parten de la FC de referencia del motor de lazo cerrado para el escenario de tu paciente (no "
               "de su FC actual): así se califica contra lo que calcula el modelo.")
CLOSING_CASE_NOTE = "El caso guiado usa un trazado simulado propio, no el de tu paciente."
# Conceptos de la sesión que practica esta unidad (`app.utils.session_learning.CONCEPTS`).
UNIT_CONCEPTS = ("frecuencia_cardiaca", "ritmo_y_conduccion", "derivaciones_e_isquemia", "hemodinamica")


# ───────────────────────────── 0 · Tu paciente ─────────────────────────────

def _create_unit_patient(scenario_key: str) -> None:
    from app.engines.digital_twin_organism import DigitalTwinOrganism
    from app.engines.simulation_engine import SimulationScenario
    from app.utils.patient_banner import HORIZON_ES
    from app.utils.patient_session import _DISPLAY_NAME_KEY, get_active_session_factory, set_active_patient_id
    from domain.physiology.scenarios.rich_engine import run_rich_scenario
    from domain.physiology.state import create_patient, horizon_of

    name = f"{UNIT_TITLE} · {SCENARIOS[scenario_key]}"
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
    from app.utils.patient_banner import INPUT_SOURCE_KEY

    st.session_state.pop(INPUT_SOURCE_KEY, None)
    st.session_state.pop("twin_shell_organism", None)
    last = rows[-1] if rows else {}
    p = M.progress(UNIT_KEY)
    p.update(patient_id=patient_id, scenario=scenario_key, trajectory=rows,
             start={"hr": last.get("FC (lpm)"), "rr": last.get("FR (rpm)"), "spo2": last.get("SpO₂ (%)")})


def station_patient() -> None:
    from app.engines.simulation_engine import SimulationEngine, SimulationScenario
    from src.clinical import sepsis_trajectory

    p = M.progress(UNIT_KEY)
    if p["patient_id"]:
        st.markdown(f"**Tu paciente:** {UNIT_TITLE} · {SCENARIOS[p['scenario']]} (`{p['patient_id'][:8]}`), "
                    "simulación del escenario.")
        st.dataframe(p["trajectory"], hide_index=True, width="stretch")
        st.caption("Valores que calculó el simulador en cada horizonte; el último es el estado de tu paciente.")
    st.markdown("Elige el escenario del simulador con el que empieza tu paciente.")
    choice = st.radio("Escenario del simulador", list(SCENARIOS), format_func=SCENARIOS.get, horizontal=True,
                      key=f"{PREFIX}scenario")
    if choice == "healthy":
        st.info(SimulationEngine(seed=SCENARIO_SEED).instance_declaration(SimulationScenario.HEALTHY))
    elif choice == "sepsis":
        st.info(sepsis_trajectory.declare_trajectory())
    else:
        st.caption("Trayectoria del simulador de escenarios (SimulationEngine): simulación.")
    st.caption(START_NOTE)
    label = "Empezar con este paciente" if not p["patient_id"] else "Empezar de nuevo con este escenario"
    if st.button(label, key=f"{PREFIX}start", type="primary"):
        with st.spinner("Calculando los 6 horizontes del escenario…"):
            _create_unit_patient(choice)
        st.rerun()


# ───────────────────────────── estaciones ─────────────────────────────

def _theory(*topics) -> None:
    from app.utils.design_system import render_theory_topic

    for topic in topics:
        render_theory_topic(topic)


def station_concept_basics() -> None:
    from app.supermodules import learn_theory as LT

    _theory(LT.SIGNED_ECG_PAPER, LT.SIGNED_HEART_RATE, LT.SIGNED_WAVES)


def station_observe() -> None:
    from app.supermodules import ui_catalog as C
    from app.supermodules.ui_home import render_recording_info

    render_recording_info(C.ORGAN_BY_KEY["corazon"], key_prefix=f"{PREFIX}obs")
    st.caption("Un trazo real, con su procedencia. En la estación «Mide» verás el de tu paciente sobre el mismo papel.")


def station_measure() -> None:
    from app.instruments import ecg_trazo
    from app.instruments.base import station_context
    from app.utils.design_system import BADGES, render_metric_card, render_no_data
    from app.utils.patient_banner import read_active_vitals, vital_provenance_text
    from clinical import calculators as calc

    trace = ecg_trazo.render(station_context(f"{PREFIX}mide"))
    if trace is not None and trace.saved_snapshot_id:
        st.session_state[SAVED_NOW_KEY] = trace.saved_snapshot_id      # la franja lo dice al final de esta pasada
    st.caption(MIDE_NOTE)

    st.markdown("#### QTc con la FC de tu paciente")
    vitals = read_active_vitals()
    hr = vitals.values["hr"]
    if hr is None:
        render_no_data("FC del paciente", "el UPS no tiene una FC de este paciente")
        return
    st.markdown(f"FC del paciente: {hr.value:.0f} lpm · {vital_provenance_text(hr, vitals.origins.get('hr'))}")
    qt = st.number_input("QT (ms)", min_value=200.0, max_value=700.0, value=None, key=f"{PREFIX}qt",
                         help="Mídelo en el trazo de arriba o en cualquier ECG; la FC es la de tu paciente.")
    if qt is None:
        st.caption("Escribe el QT para calcular el QTc.")
        return
    citations = {"Bazett": calc.BAZETT_CITATION, "Fridericia": calc.FRIDERICIA_CITATION,
                 "Framingham": calc.FRAMINGHAM_QTC_CITATION, "Hodges": calc.HODGES_CITATION}   # las de Calculadoras
    for name, value in calc.qtc_all(qt, hr.value).items():
        render_metric_card(f"QTc {name}", f"{value:.0f} ms", provenance=BADGES.CLINICAL, citation=citations[name])


def station_practice() -> None:
    from app.supermodules import ui_catalog as C
    from app.supermodules.ui_topic import render_topic_quiz

    topic = C.TOPIC_BY_KEY["fc"]
    st.markdown(f"#### Preguntas · {topic.theory.title}")
    render_topic_quiz(topic)


def station_alter() -> None:
    from app.instruments.base import station_context
    from app.supermodules import what_if as W

    scenario = M.progress(UNIT_KEY)["scenario"]
    cases = tuple(c for c in W.CASES if c.scenario == scenario)
    if not cases:
        st.info(f"El escenario de tu paciente ({SCENARIOS.get(scenario, scenario)}) no está en la lista cerrada de "
                "«¿Qué pasa si…?».")
        st.caption(W.EXCLUDED_NOTE)
        return
    st.caption(ALTERA_NOTE)
    W.render_what_if_page(station_context(f"{PREFIX}altera"), cases=cases)


def station_concept_twelve() -> None:
    from app.supermodules import learn_theory as LT

    _theory(LT.SIGNED_TWELVE_LEADS, LT.SIGNED_ISCHEMIA)


def station_closing() -> None:
    from app.utils import navigation as nav
    from app.utils.patient_banner import UNIT_ES, VITALS, read_active_vitals, vital_provenance_text
    from app.utils.session_learning import get_session_log

    p = M.progress(UNIT_KEY)
    vitals = read_active_vitals()
    st.markdown(f"#### Tu paciente al final · {UNIT_TITLE} · {SCENARIOS[p['scenario']]} (`{p['patient_id'][:8]}`)")
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

    answers = [r for r in get_session_log() if r.get("concept") in UNIT_CONCEPTS]
    if answers:
        correct = sum(bool(r.get("correct")) for r in answers)
        st.markdown(f"**Lo que practicaste en esta sesión** (frecuencia cardiaca, ritmo, derivaciones e isquemia, "
                    f"hemodinámica): {len(answers)} respuestas, {correct} correctas.")
    else:
        st.markdown("**Lo que practicaste en esta sesión:** todavía no hay respuestas de esta unidad.")
    nav.link("mi-sesion", "Tu aprendizaje en esta sesión")

    st.markdown("#### Caso de cierre")
    st.caption(CLOSING_CASE_NOTE)
    nav.link("caso-guiado", "Caso guiado de ECG: elevación del ST (firmado)")
    nav.link("desafio-ecg", "Desafío ECG de 12 derivaciones")


SAVED_NOW_KEY = "ruta_saved_now"

UNIT = M.Unit(UNIT_KEY, UNIT_TITLE, (
    M.Station("paciente", "paciente", "Tu paciente", station_patient, needs_patient=False),
    M.Station("concepto", "concepto", "El ECG en papel, la frecuencia y las ondas", station_concept_basics,
              needs_patient=False),
    M.Station("observa", "observa", "Un ECG real", station_observe, needs_patient=False),
    M.Station("mide", "mide", "El ECG de tu paciente", station_measure),
    M.Station("practica", "practica", "Preguntas de frecuencia cardiaca", station_practice, needs_patient=False),
    M.Station("altera", "altera", "¿Qué pasa si cambia la FC?", station_alter),
    M.Station("concepto_12", "concepto", "Las 12 derivaciones y la isquemia", station_concept_twelve,
              needs_patient=False),
    M.Station("cierre", "cierre", "Tu paciente al final", station_closing),
))
