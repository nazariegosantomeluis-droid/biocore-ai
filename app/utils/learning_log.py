"""Registro local de respuestas y reportes de los cuestionarios, para la mejora continua (2026-11-16).

Lo usan la Academia, el Desafío Educativo de 12 Derivaciones y el quiz del EEG Neuro Lab. Todo se guarda en la base
local de `educational/learning_analytics.py`; no sale de la computadora. El acierto lo decide el banco de preguntas
(`QuizQuestion.is_correct`), nunca el modelo.
"""

from __future__ import annotations

from typing import Sequence

import streamlit as st

from educational import learning_analytics as LA

LEARNER_KEY = "academia_student_id"          # el «ID del estudiante» de la Academia
DEFAULT_LEARNER = "estudiante_demo"          # el mismo valor inicial que muestra la Academia
_LOGGED = "biocore_learning_logged"


def learner_id() -> str:
    return (st.session_state.get(LEARNER_KEY) or "").strip() or DEFAULT_LEARNER


def session_attempt(key: str) -> str:
    """Un intento que dura toda la sesión: para los cuestionarios de una pregunta a la vez."""
    if key not in st.session_state:
        st.session_state[key] = LA.new_attempt()
    return st.session_state[key]


def log_answer(bank: str, question, chosen: str, attempt: str) -> None:
    """Guarda una respuesta una sola vez por intento (volver a pulsar el botón no la repite)."""
    logged = st.session_state.setdefault(_LOGGED, set())
    mark = (bank, attempt, question.prompt)
    if mark in logged:
        return
    try:
        LA.record_answer(bank, question, chosen, attempt, learner_id())
        logged.add(mark)
    except Exception as exc:          # una base bloqueada o sin espacio no debe tumbar el cuestionario
        st.caption(f"No se pudo guardar la respuesta para la mejora continua ({type(exc).__name__}).")


def render_report_box(bank: str, questions: Sequence, key: str, in_expander: bool = False) -> None:
    """«¿Algo está mal en esta pregunta?»: el reporte va a la cola de revisión; nada cambia hasta que una persona lo
    revise. Dentro de otro expander (`in_expander=True`) se dibuja sin el suyo: Streamlit no permite anidarlos."""
    title = "🚩 ¿Algo está mal en esta pregunta?" if len(questions) == 1 else "🚩 ¿Algo está mal en alguna pregunta?"
    if in_expander:
        st.markdown(f"**{title}**")
        _report_form(bank, questions, key)
    else:
        with st.expander(title):
            _report_form(bank, questions, key)


def _report_form(bank: str, questions: Sequence, key: str) -> None:
    question = questions[0]
    if len(questions) > 1:
        index = st.selectbox("Pregunta", range(len(questions)), format_func=lambda i: questions[i].prompt,
                             key=f"{key}_which")
        question = questions[index]
    text = st.text_area("Qué está mal: la respuesta marcada como correcta, la explicación, la fuente o la redacción.",
                        key=f"{key}_text")
    if not st.button("Enviar a revisión", key=f"{key}_send"):
        return
    if not (text or "").strip():
        st.warning("Escribe qué está mal antes de enviar.")
        return
    try:
        LA.record_report(bank, question, text, learner_id())
    except Exception as exc:
        st.error(f"No se pudo guardar el reporte ({type(exc).__name__}).")
        return
    st.success("Gracias: quedó en la cola de revisión del banco. La pregunta no cambia hasta que una persona lo revise "
               "con su fuente.")
