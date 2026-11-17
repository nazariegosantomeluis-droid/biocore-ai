"""🔎 Detective fisiológico (integración, 2026-11-17).

Un caso simulado del banco de casos (`generate_case`, el mismo de «Caso ciego») con el diagnóstico OCULTO. A diferencia
del caso ciego, que enseña todo de golpe, aquí el estudiante PIDE las pistas una por una, decide cuándo basta, diagnostica
con la confianza que siente y escribe su justificación. Luego la corrección (determinista, sin IA) y su recorrido.

Art. I — solo lo que el UPS tiene de verdad:
- Las pistas son exactamente lo que el caso trae: signos vitales (FC, FR, SpO₂) con sus puntos NEWS2 (RCP 2017, la misma
  tabla del gemelo: `clinical.calculators`), HRV (el UPS guarda «hrv, ms» sin decir qué índice es), eventos del UPS y la
  PA CALCULADA solo donde el lazo cerrado está habilitado (sano, hipertensión, sepsis; en el resto, «no modelada»). En
  la sepsis esa PA lleva «en revisión clínica», como en el gemelo: depende de la capacitancia venosa 2× (Criterio
  BIOCORE, sin cita; `SEPSIS_MODEL_DECLARATION`).
- NO hay ECG, EEG ni EMG como pista: el UPS guarda escalares, no la onda, y la morfología propia de cada escenario no
  está modelada. Tampoco el índice por hora de sueño (`ahi`: el organismo lo calcula en 0 por defecto, una fachada).
- La justificación NO se califica (no hay con qué: no existe una explicación clínica por escenario con fuente firmada;
  `CASE_EXPLANATION_PENDING`). Se muestra junto a la evidencia, para que el estudiante la compare él mismo.
- La corrección es determinista: la respuesta es el escenario que generó el caso. Ninguna IA interviene.
- Registro de la sesión (`app.utils.session_learning`): cada diagnóstico, UNA vez por caso, con
  `log_session_answer("detective:<paciente>", "detective", concepto, correcto, confianza)`. El concepto sale de
  `SCENARIO_CONCEPT`; un escenario que no encaja en ningún concepto de `CONCEPTS` (convulsión) no se registra: no se
  inventan conceptos. El resumen de la página es un conteo, no una medida de dominio.
"""
from __future__ import annotations

from typing import Optional

import streamlit as st

from app.engines.simulation_engine import SimulationScenario
from app.supermodules.twin_shell.baroreflex_panel import pa_model_label
from app.supermodules.twin_shell.pages import (
    CASE_EVIDENCE_ROWS,
    CASE_EXPLANATION_PENDING,
    RICH_SCENARIO_LABELS,
    _attach_calculated_pa_to_case,
    _dedupe_events,
    _diagnostic_options,
    case_evidence,
    render_sepsis_model_declaration,
)
from app.utils.design_system import BADGES, render_metric_card, render_module_header, render_no_data
from app.utils.patient_session import get_shared_ups_engine
from app.utils.session_learning import get_session_log, log_session_answer
from clinical.calculators import NEWS2_CITATION, news2_points_text
from domain.physiology.scenarios.case_bank import generate_case
from domain.physiology.state import EventSeverity, make_session_factory

SOURCE = "detective"
PREFIX = "detective_"
PROVENANCE_ES = {"simulacion": "Simulación", "derivado": "Derivado"}

# Identificadores de pista, en el orden en que se ofrecen (el estudiante elige el suyo).
CLUE_VITALS, CLUE_HRV, CLUE_PA, CLUE_EVENTS = "vitales", "hrv", "pa", "eventos"
CLUES = (
    (CLUE_VITALS, "🩺 Signos vitales y puntos NEWS2"),
    (CLUE_HRV, "📈 Variabilidad cardíaca (HRV)"),
    (CLUE_PA, "🧮 Presión arterial calculada"),
    (CLUE_EVENTS, "🚨 Eventos del UPS"),
)

# Concepto que registra cada escenario en `session_learning.CONCEPTS`. CRITERIO BIOCORE (sin cita; pendiente de la firma
# de Luis): el concepto con que el escenario se relaciona más de cerca. None = el escenario no encaja en ningún concepto
# del vocabulario y el caso NO se registra (2026-11-17: la convulsión estaba en «news2», que no es lo que el caso evalúa).
SCENARIO_CONCEPT = {
    SimulationScenario.HEALTHY: "frecuencia_cardiaca",
    SimulationScenario.EXERCISE: "frecuencia_cardiaca",
    SimulationScenario.STRESS: "frecuencia_cardiaca",
    SimulationScenario.ANXIETY: "frecuencia_cardiaca",
    SimulationScenario.ARRHYTHMIA_AFIB: "ritmo_y_conduccion",
    SimulationScenario.ARRHYTHMIA_AFLUTTER: "ritmo_y_conduccion",
    SimulationScenario.ARRHYTHMIA_SVT: "ritmo_y_conduccion",
    SimulationScenario.ARRHYTHMIA_SBRADY: "ritmo_y_conduccion",
    SimulationScenario.HYPOXIA: "respiracion_y_apnea",
    SimulationScenario.APNEA: "respiracion_y_apnea",
    SimulationScenario.COPD: "respiracion_y_apnea",
    SimulationScenario.FATIGUE: "emg",
    SimulationScenario.SEIZURE: None,
    SimulationScenario.SEPSIS: "hemodinamica",
    SimulationScenario.HYPERTENSION: "hemodinamica",
}

MIN_CLUES_TO_DIAGNOSE = 1


def _k(name: str) -> str:
    return PREFIX + name


def _descriptors(state) -> dict:
    return {d.name: d for domain in state.all_domains().values() for d in domain.descriptors.values()}


# La PA de la sepsis depende de la capacitancia venosa 2× (Criterio BIOCORE, sin cita): el gemelo la declara «en revisión
# clínica» (`SEPSIS_MODEL_DECLARATION`); aquí, la misma etiqueta y el mismo motivo.
PA_IN_REVIEW_LABEL = "en revisión clínica"
SEPSIS_PA_IN_REVIEW = ("En revisión clínica: en la sepsis esta presión depende de la capacitancia venosa 2× (Criterio "
                       "BIOCORE, sin cita), como declara el gemelo.")


def concept_for(scenario: SimulationScenario) -> Optional[str]:
    """El concepto del caso, o None si no encaja en ninguno de `CONCEPTS` (entonces no se registra)."""
    return SCENARIO_CONCEPT[scenario]


def clue_available(clue: str, state, events) -> bool:
    """¿El caso trae esta pista con datos? Una pista sin datos no se inventa: se muestra como «sin dato» con el motivo."""
    d = _descriptors(state)
    if clue == CLUE_VITALS:
        return any(key in d for key, *_ in CASE_EVIDENCE_ROWS)
    if clue == CLUE_HRV:
        return "hrv" in d
    if clue == CLUE_PA:
        return state.cardiovascular.get("map_modelo") is not None
    return bool(events)


def render_clue(clue: str, state, events, references_pa, scenario: Optional[SimulationScenario] = None) -> None:
    d = _descriptors(state)
    if clue == CLUE_VITALS:
        columns = st.columns(len(CASE_EVIDENCE_ROWS))
        for column, (value_key, points_key, label, unit) in zip(columns, CASE_EVIDENCE_ROWS):
            with column:
                value, points = d.get(value_key), d.get(points_key)
                render_metric_card(
                    label,
                    None if value is None else f"{value.value:.0f} {unit}",
                    provenance=BADGES.SIMULATION,
                    unavailable_reason="el caso no trae este valor",
                )
                if points is not None:
                    st.caption(f"NEWS2: {news2_points_text(int(points.value))}")
        st.caption(f"Criterio: {NEWS2_CITATION}. Sin total NEWS2: faltan presión, temperatura, consciencia y oxígeno.")
    elif clue == CLUE_HRV:
        hrv = d.get("hrv")
        if hrv is None:
            render_no_data("HRV", "el caso no trae variabilidad cardíaca")
        else:
            render_metric_card("HRV", f"{hrv.value:.0f} {hrv.unit}", provenance=BADGES.SIMULATION)
            st.caption("El UPS guarda este valor como «hrv, ms» sin decir qué índice es (SDNN, RMSSD…): compáralo con "
                       "la FC y los demás datos del caso, no con un valor de referencia.")
    elif clue == CLUE_PA:
        map_modelo = state.cardiovascular.get("map_modelo")
        if map_modelo is None:
            render_no_data("Presión arterial", "no modelada para este escenario: el lazo cerrado hemodinámico solo "
                                               "está habilitado en sano, hipertensión y sepsis")
        else:
            sys_m = state.cardiovascular.get("systolic_bp_modelo")
            dia_m = state.cardiovascular.get("diastolic_bp_modelo")
            ref_map = next((r for r in (references_pa or []) if r.descriptor == "map"), None)
            in_review = scenario == SimulationScenario.SEPSIS
            st.markdown(
                f"**PA calculada ({pa_model_label()})"
                + (f" — {PA_IN_REVIEW_LABEL}" if in_review else "")
                + f":** {sys_m.value:.0f}/{dia_m.value:.0f} mmHg (PAM {map_modelo.value:.0f} mmHg)"
                + (f" — referencia clínica citada: PAM {ref_map.value:.0f} mmHg" if ref_map else ""))
            if in_review:
                st.caption(SEPSIS_PA_IN_REVIEW)
            st.caption("CALCULADA por el modelo a partir de la FC del caso: no es una medición. Solo existe en sano, "
                       "hipertensión y sepsis; que en otro caso no aparezca no dice nada sobre el diagnóstico.")
    elif clue == CLUE_EVENTS:
        if not events:       # no es «sin dato»: el UPS sí miró y no registró ninguno (también es una pista)
            st.caption("El UPS no registró ningún evento en este momento del caso.")
        for event in events:
            icon = "🔴" if event.severity == EventSeverity.CRITICAL else "🟡"
            st.caption(f"{icon} {event.description}")


def clue_label(clue: str) -> str:
    return dict(CLUES)[clue]


def _new_case() -> None:
    if _k("session_factory") not in st.session_state:
        st.session_state[_k("session_factory")] = make_session_factory(get_shared_ups_engine())
    factory = st.session_state[_k("session_factory")]
    with factory() as session:
        case = generate_case(session)
        state, references = _attach_calculated_pa_to_case(
            session, case.patient_id, case.scenario.value, case.state, source_detail="detective_case")
    for name, value in {
        "patient_id": case.patient_id, "scenario": case.scenario, "state": state,
        "events": _dedupe_events(case.events), "references_pa": references,
        "options": _diagnostic_options(case.scenario), "revealed": [], "answered": False, "selected": None,
        "confidence": None, "justification": None, "parametros": case.parametros, "logged": False,
    }.items():
        st.session_state[_k(name)] = value


def _render_session_summary() -> None:
    """Lo que esta sesión lleva con el Detective: contado, sin umbrales ni «dominio» (pocas respuestas no lo miden)."""
    log = [r for r in get_session_log() if r["source"] == SOURCE]
    if not log:
        return
    st.markdown("#### Tu sesión con el Detective")
    rows = []
    for concept in dict.fromkeys(r["concept"] for r in log):
        mine = [r for r in log if r["concept"] == concept]
        confidences = [r["confidence"] for r in mine if r["confidence"] is not None]
        rows.append({
            "Concepto": concept.replace("_", " "),
            "Casos": len(mine),
            "Aciertos": sum(r["correct"] for r in mine),
            "Confianza media declarada (%)": round(sum(confidences) / len(confidences)) if confidences else None,
        })
    st.dataframe(rows, hide_index=True, width="stretch")
    right = [r["confidence"] for r in log if r["correct"] and r["confidence"] is not None]
    wrong = [r["confidence"] for r in log if not r["correct"] and r["confidence"] is not None]
    if right and wrong:
        st.caption(f"Tu confianza media declarada fue {sum(right) / len(right):.0f} % cuando acertaste y "
                   f"{sum(wrong) / len(wrong):.0f} % cuando no.")
    st.caption("Es un conteo de esta sesión (se borra al cerrarla), no una medida de dominio: con pocos casos no "
               "dice cuánto sabes.")


def render_detective_page() -> None:
    render_module_header(
        "Detective fisiológico", icon="🔎",
        subtitle="Un paciente simulado con el diagnóstico oculto: pide las pistas que quieras, diagnostica y justifica.")
    st.caption(
        "🧪 El caso es una **simulación** del banco de casos de BIOCORE, no un paciente real. Es un paciente aparte: no "
        "toca el paciente activo de tus laboratorios. Solo hay pistas de lo que el UPS guarda; no hay ECG, EEG ni EMG "
        "porque el UPS guarda valores, no la onda.")

    if st.button("🆕 Nuevo caso", key=_k("new")):
        _new_case()
        st.rerun()

    patient_id = st.session_state.get(_k("patient_id"))
    if patient_id is None:
        st.caption("Sin caso todavía: pulsa «Nuevo caso» para empezar.")
        _render_session_summary()
        return

    state, events = st.session_state[_k("state")], st.session_state[_k("events")]
    references = st.session_state[_k("references_pa")]
    revealed = st.session_state[_k("revealed")]
    answered = st.session_state[_k("answered")]

    st.markdown("#### Pistas")
    if not answered:
        columns = st.columns(len(CLUES))
        for column, (clue, label) in zip(columns, CLUES):
            with column:
                if st.button(label, key=_k(f"clue_{clue}_{patient_id}"), disabled=clue in revealed, width="stretch"):
                    revealed.append(clue)
                    st.rerun()
    if not revealed:
        st.caption("Aún no pediste ninguna pista. Cada una dice de dónde sale y qué criterio la acompaña.")
    for clue in revealed:
        with st.container(border=True):
            st.markdown(f"**{clue_label(clue)}**")
            render_clue(clue, state, events, references, st.session_state[_k("scenario")])

    if not answered:
        st.markdown("#### Tu diagnóstico")
        enough = len(revealed) >= MIN_CLUES_TO_DIAGNOSE
        if not enough:
            st.caption("Pide al menos una pista antes de diagnosticar: sin ninguna sería adivinar.")
        choice = st.radio("¿Cuál es el diagnóstico?", st.session_state[_k("options")], index=None,
                          format_func=lambda s: RICH_SCENARIO_LABELS[s], key=_k(f"radio_{patient_id}"))
        confidence = st.slider("¿Qué tan seguro estás? (0 = adivino, 100 = seguro)", 0, 100, 50, step=5,
                               key=_k(f"confidence_{patient_id}"))
        justification = st.text_area("¿En qué pista te apoyas? (obligatorio; no se califica, la comparas tú después)",
                                     key=_k(f"justification_{patient_id}"))
        ready = enough and choice is not None and bool(justification.strip())
        if st.button("✅ Confirmar diagnóstico", key=_k(f"confirm_{patient_id}"), disabled=not ready):
            hidden = st.session_state[_k("scenario")]
            st.session_state[_k("selected")] = choice
            st.session_state[_k("confidence")] = confidence
            st.session_state[_k("justification")] = justification.strip()
            st.session_state[_k("answered")] = True
            concept = concept_for(hidden)
            if concept is not None and not st.session_state.get(_k("logged")):    # UNA vez por caso
                log_session_answer(f"{SOURCE}:{patient_id}", SOURCE, concept, choice == hidden, confidence)
                st.session_state[_k("logged")] = True
            st.rerun()
        if not ready and enough:
            st.caption("Elige un diagnóstico y escribe tu justificación para confirmar.")
        _render_session_summary()
        return

    # ── Corrección determinista ────────────────────────────────────────────────────────────────────────────────────
    selected, hidden = st.session_state[_k("selected")], st.session_state[_k("scenario")]
    if selected == hidden:
        st.success(f"✅ Correcto. El caso era: {RICH_SCENARIO_LABELS[hidden]}")
    else:
        st.error(f"❌ Elegiste {RICH_SCENARIO_LABELS[selected]}; el caso era {RICH_SCENARIO_LABELS[hidden]}")
    st.markdown("**Tu justificación** (no se califica):")
    st.markdown(f"> {st.session_state[_k('justification')]}")
    st.caption(f"Tu confianza declarada: {st.session_state[_k('confidence')]} %.")
    st.markdown("**Lo que mostró el caso, con su criterio citado:**")
    for line in case_evidence(state, events):
        st.markdown(f"- {line}")
    st.caption(f"Criterio: {NEWS2_CITATION}. {CASE_EXPLANATION_PENDING}")
    if hidden == SimulationScenario.SEPSIS:
        with st.expander("Cómo está construido este caso (sepsis)"):
            render_sepsis_model_declaration()

    st.markdown("**Tu recorrido** (descriptivo, sin puntaje):")
    st.markdown(f"Pediste {len(revealed)} de {len(CLUES)} pistas, en este orden: "
                + " → ".join(clue_label(c) for c in revealed) + ".")
    missed = [c for c, _ in CLUES if c not in revealed]
    if missed:
        with st.expander("Pistas que no pediste"):
            for clue in missed:
                st.markdown(f"**{clue_label(clue)}**")
                render_clue(clue, state, events, references, hidden)
    parametros = st.session_state[_k("parametros")]
    st.caption(f"🧪 Recordatorio: simulación del banco de casos (`{parametros['escenario']}`, horizonte "
               f"`{parametros['horizonte_elegido']}`), no un paciente real.")
    _render_session_summary()
