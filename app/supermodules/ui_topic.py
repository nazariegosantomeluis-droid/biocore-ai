"""Página de tema con la estructura de una ficha de producto de Apple (2026-11-17).

Título grande y chips arriba; a la izquierda un carrusel (Explicación, Teoría, Hallazgos, Quiz final); a la derecha la
calculadora del tema y la variabilidad clínica del paciente activo.

Art. I: la explicación y la teoría son los temas firmados tal cual; los hallazgos son un registro real o los valores
del UPS con su procedencia; las calculadoras usan las funciones citadas de `clinical/calculators.py` y no traen
valores por defecto (un campo vacío no calcula). La confianza del quiz se declara o queda «sin declarar», nunca 50.
"""

from __future__ import annotations

from typing import Optional

import streamlit as st

from app.supermodules import ui_catalog as C

SLIDES = ("Explicación", "Teoría", "Hallazgos", "Quiz final")
NOT_DECLARED = "Sin declarar"
CONFIDENCE_OPTIONS = (NOT_DECLARED, *range(0, 101, 10))
NEWS2_FIELDS = {"Pulso": "hr", "Frecuencia respiratoria": "rr", "SpO₂ (escala 1)": "spo2"}


def _num(label: str, key: str, lo: float, hi: float):
    """Campo numérico vacío por defecto (un campo vacío no calcula). Si «Usar en la calculadora» ya llenó la clave, no se
    le pasa `value` (Streamlit avisaría que recibió dos valores)."""
    if key in st.session_state:
        return st.number_input(label, min_value=lo, max_value=hi, key=key)
    return st.number_input(label, min_value=lo, max_value=hi, value=None, key=key)


def _slide_key(topic: C.Topic) -> str:
    return f"bc_slide_{topic.key}"


def _step(topic_key: str, delta: int) -> None:
    key = f"bc_slide_{topic_key}"
    current = st.session_state.get(key) or SLIDES[0]
    st.session_state[key] = SLIDES[(SLIDES.index(current) + delta) % len(SLIDES)]


def _dots(active: str) -> str:
    spans = "".join(f"<span class='{'on' if s == active else ''}'></span>" for s in SLIDES)
    return (f"<div class='bc-dots' role='img' aria-label='Sección {SLIDES.index(active) + 1} de {len(SLIDES)}'>"
            f"{spans}</div>")


# ───────────────────────────── diapositivas ─────────────────────────────

def _slide_explanation(topic: C.Topic) -> None:
    st.markdown(f"### {topic.theory.idea or 'Sin idea firmada para este tema.'}")
    if topic.theory.source:
        st.caption(f"Fuente: {topic.theory.source}")


def _slide_theory(topic: C.Topic) -> None:
    if topic.theory.mechanism:
        st.markdown("**Mecanismo**")
        st.markdown(topic.theory.mechanism)
    if topic.theory.detail:
        st.markdown("**Detalle con fuente**")
        if callable(topic.theory.detail):
            topic.theory.detail()
        else:
            st.markdown(topic.theory.detail)
    if not (topic.theory.mechanism or topic.theory.detail):
        st.caption("Este tema no tiene más capas firmadas.")
    if topic.theory.source:
        st.caption(f"Fuente: {topic.theory.source}")


def _slide_findings(topic: C.Topic) -> None:
    from app.supermodules.ui_home import render_recording_info

    organ = C.ORGAN_BY_KEY[topic.organ]
    render_recording_info(organ, key_prefix=f"bc_topic_{topic.key}")
    if topic.calculator == "news2":
        _render_patient_news2()


def _render_patient_news2() -> None:
    from app.utils.patient_banner import read_active_vitals
    from clinical import calculators as calc

    vitals = read_active_vitals()
    st.markdown("**El paciente activo, con los puntos NEWS2 de cada componente**")
    if vitals.patient_id is None:
        st.caption("Sin paciente activo.")
        return
    raw = {k: (d.value if d is not None else None) for k, d in vitals.values.items()}
    partial = calc.news2_partial(pulse=raw["hr"], respiratory_rate=raw["rr"], spo2=raw["spo2"])
    for component, points in partial.components.items():
        st.markdown(f"- {component}: {points} {'punto' if points == 1 else 'puntos'}")
    st.caption(f"No hay total: faltan {', '.join(calc.NEWS2_PARAMETERS_NOT_MODELED)} ({calc.NEWS2_CITATION}).")


def _log_once(topic: C.Topic, bank: str, question, correct: bool, confidence: Optional[int]) -> None:
    from app.utils.session_learning import log_session_answer
    from educational.learning_analytics import question_id

    item = f"{bank}:{question_id(bank, question.prompt)}"
    logged = st.session_state.setdefault("bc_logged_items", set())
    if topic.concept is None or item in logged:
        return
    log_session_answer(item, "quiz", topic.concept, correct, confidence)
    logged.add(item)


def _slide_quiz(topic: C.Topic) -> None:
    questions = C.quiz_questions(topic)
    if not questions:
        st.caption("Este tema todavía no tiene preguntas con fuente.")
        return
    if topic.concept is None:
        st.caption("Las respuestas de este tema no entran a «Tu aprendizaje en esta sesión»: no tiene concepto en el "
                   "registro de la sesión.")
    for i, q in enumerate(questions):
        base = f"bc_q_{topic.key}_{i}"
        with st.container(key=f"bc_card_{base}"):
            st.markdown(f"**{q.prompt}**")
            choice = st.radio("Opciones", q.display_choices(), index=None, key=f"{base}_choice",
                              label_visibility="collapsed")
            conf = st.select_slider("Tu confianza (0 a 100)", CONFIDENCE_OPTIONS, value=NOT_DECLARED,
                                    key=f"{base}_conf")
            if st.button("Comprobar", key=f"{base}_check", disabled=choice is None):
                st.session_state[f"{base}_done"] = (choice, conf)
            done = st.session_state.get(f"{base}_done")
            if done:
                ok = q.is_correct(done[0])
                st.markdown("**Correcto.**" if ok else f"**Todavía no.** La respuesta es: {q.correct_choice}")
                if q.explanation:
                    st.caption(q.explanation)
                if q.source:
                    st.caption(f"Fuente: {q.source}")
                _log_once(topic, topic.quiz_bank, q, ok, None if done[1] == NOT_DECLARED else int(done[1]))


# ───────────────────────────── panel derecho ─────────────────────────────

def _use_patient(kind: str) -> None:
    from app.utils.patient_banner import read_active_vitals

    v = {k: (d.value if d is not None else None) for k, d in read_active_vitals().values.items()}
    if kind == "fc" and v["hr"]:
        st.session_state["bc_calc_rr"] = float(round(60000.0 / v["hr"]))
    elif kind == "qtc" and v["hr"]:
        st.session_state["bc_calc_qtc_hr"] = float(round(v["hr"]))
    elif kind == "news2":
        for key, field in (("hr", "bc_calc_n_hr"), ("rr", "bc_calc_n_rr"), ("spo2", "bc_calc_n_spo2")):
            if v[key] is not None:
                st.session_state[field] = float(round(v[key]))


def _render_calculator(topic: C.Topic) -> None:
    from app.supermodules.bibliography import cite
    from app.utils.design_system import BADGES, render_metric_card
    from app.utils.evidence_passport import render_evidence_passport
    from clinical import calculators as calc

    with st.container(key="bc_card_calc"):
        st.markdown("<span class='bc-eyebrow'>Calculadora</span>", unsafe_allow_html=True)
        st.markdown("#### Ingresar datos")
        if topic.calculator == "fc":
            rr = _num("Intervalo RR (ms)", "bc_calc_rr", 200.0, 3000.0)
            if rr is not None:
                render_metric_card("Frecuencia cardiaca", f"{calc.hr_from_rr_ms(rr):.0f} lpm", provenance=BADGES.CLINICAL,
                                   citation=f"{cite('MCM')} 60 / intervalo RR (tema 2 firmado)")
        elif topic.calculator == "qtc":
            qt = _num("QT (ms)", "bc_calc_qtc_qt", 200.0, 700.0)
            hr = _num("FC (lpm)", "bc_calc_qtc_hr", 20.0, 250.0)
            if qt is not None and hr is not None:
                for name, value in calc.qtc_all(qt, hr).items():
                    render_metric_card(f"QTc {name}", f"{value:.0f} ms", provenance=BADGES.CLINICAL)
                    render_evidence_passport(f"calculadoras.qtc_{name}", f"{value:.0f} ms", key=f"bc_pp_qtc_{name}")
        elif topic.calculator == "news2":
            hr = _num("FC (lpm)", "bc_calc_n_hr", 20.0, 250.0)
            rr = _num("FR (resp/min)", "bc_calc_n_rr", 2.0, 80.0)
            spo2 = _num("SpO₂ (%)", "bc_calc_n_spo2", 50.0, 100.0)
            partial = calc.news2_partial(pulse=hr, respiratory_rate=rr, spo2=spo2)
            for component, points in partial.components.items():
                shown = f"{points} {'punto' if points == 1 else 'puntos'}"
                render_metric_card(f"{component} NEWS2", shown, provenance=BADGES.CLINICAL)
                render_evidence_passport(f"calculadoras.news2_paciente_{NEWS2_FIELDS[component]}", shown,
                                         key=f"bc_pp_news2_{NEWS2_FIELDS[component]}")
            if not partial.components:
                st.caption("Escribe al menos un valor para calcular sus puntos.")
            st.caption(f"Sin total: faltan {', '.join(calc.NEWS2_PARAMETERS_NOT_MODELED)}.")
        else:
            st.caption("Este tema no tiene calculadora.")


def _render_patient_variability(topic: C.Topic) -> None:
    from app.utils.patient_banner import NO_DATA_TEXT, VITALS, read_active_vitals, provenance_label, UNIT_ES

    vitals = read_active_vitals()
    with st.container(key="bc_card_patient"):
        st.markdown("<span class='bc-eyebrow'>Variabilidad clínica</span>", unsafe_allow_html=True)
        st.markdown("#### Paciente activo")
        if vitals.patient_id is None:
            st.caption("Sin paciente activo: abre el gemelo digital para crearlo.")
            return
        for key, label, *_rest in VITALS:
            d = vitals.values[key]
            st.markdown(f"**{label}** · " + (NO_DATA_TEXT if d is None else
                        f"{d.value:.0f} {UNIT_ES.get(d.unit, d.unit)} · {provenance_label(d)}"))
        if topic.calculator:
            st.button("Usar en la calculadora", key=f"bc_use_patient_{topic.key}", icon=":material/input:",
                      on_click=_use_patient, args=(topic.calculator,))


def render_topic_page() -> None:
    keys = [t.key for t in C.TOPICS]
    if st.session_state.get(C.SELECTED_TOPIC_KEY) not in keys:
        st.session_state[C.SELECTED_TOPIC_KEY] = keys[0]
    topic_key = st.selectbox("Tema", keys, key=C.SELECTED_TOPIC_KEY,
                             format_func=lambda k: C.TOPIC_BY_KEY[k].theory.title)
    topic = C.TOPIC_BY_KEY[topic_key]
    organ = C.ORGAN_BY_KEY[topic.organ]

    st.markdown(f"<span class='bc-eyebrow'>{organ.label}</span><div class='bc-hero'>{topic.theory.title}</div>",
                unsafe_allow_html=True)
    chips = [f"<span class='bc-chip'><b>●</b> Teoría firmada{f' · {topic.theory.source}' if topic.theory.source else ''}</span>",
             f"<span class='bc-chip'><b>●</b> {'Registro real' if organ.recording else 'Sin registro real'}</span>",
             f"<span class='bc-chip'><b>●</b> {'Calculadora' if topic.calculator else 'Sin calculadora'}</span>"]
    st.markdown("".join(chips), unsafe_allow_html=True)

    left, right = st.columns([2, 1], gap="large")
    with left:
        with st.container(key="bc_card_slides"):
            key = _slide_key(topic)
            slide = st.segmented_control("Sección", SLIDES, key=key, label_visibility="collapsed",
                                         default=None if key in st.session_state else SLIDES[0]) or SLIDES[0]
            {"Explicación": _slide_explanation, "Teoría": _slide_theory, "Hallazgos": _slide_findings,
             "Quiz final": _slide_quiz}[slide](topic)
            st.markdown(_dots(slide), unsafe_allow_html=True)
            prev, _, nxt = st.columns([1, 2, 1])
            prev.button("Anterior", key=f"bc_prev_{topic.key}", icon=":material/chevron_left:",
                        on_click=_step, args=(topic.key, -1))
            nxt.button("Siguiente", key=f"bc_next_{topic.key}", icon=":material/chevron_right:",
                       on_click=_step, args=(topic.key, 1))
    with right:
        _render_calculator(topic)
        _render_patient_variability(topic)
        if topic.lab:
            from app.utils import navigation as nav

            nav.link(topic.lab, "Abrir el laboratorio del tema", icon=":material/arrow_forward:")
