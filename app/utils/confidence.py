"""Confianza declarada en los cuestionarios y su calibración en la sesión (2026-11-17).

- `render_confidence_input`: antes de verificar, el estudiante puede decir qué tan seguro está (25, 50, 75 o 100 %).
  Es opcional y empieza sin elegir: una confianza por defecto sería un dato que el estudiante no dio (Art. I).
- `record_quiz_answer`: guarda la respuesta en el registro de la sesión de Luis (`app/utils/session_learning.py`),
  una sola vez por intento, solo si la pregunta tiene concepto (`quiz_bank.CONCEPT_BY_PROMPT`).
- `render_calibration_panel`: el veredicto de `educational/confidence_calibration.py` y la tabla de respuestas.

Todo vive en la sesión del navegador; nada se escribe en una base.
"""
from __future__ import annotations

from typing import Optional

import streamlit as st

from app.utils.session_learning import get_session_log, log_session_answer
from educational import confidence_calibration as cc
from educational.learning_analytics import question_id
from educational.quiz_bank import CONCEPT_BY_PROMPT

CONFIDENCE_LEVELS = (25, 50, 75, 100)
CONFIDENCE_LABELS = {25: "25 % (estoy adivinando)", 50: "50 %", 75: "75 %", 100: "100 % (estoy seguro)"}
CONFIDENCE_QUESTION = "¿Qué tan seguro estás de tu respuesta? (opcional)"
CONFIDENCE_FIRST_HINT = "Aquí la respuesta se corrige al elegirla: indica primero tu confianza."
PANEL_TITLE = "Tu calibración en esta sesión"
PANEL_INTRO = ("Compara qué tan seguro dijiste estar con qué tanto acertaste. Solo cuentan las respuestas en las que "
               "indicaste tu confianza antes de verificar, y solo las preguntas con concepto asignado. Se borra al "
               "cerrar el navegador.")
_RECORDED = "confidence_recorded_answers"
_LABELS = "confidence_item_labels"
# Los bancos que piden confianza; su `question_id` permite mostrar el enunciado en «errores con más confianza».
QUIZ_BANKS = ("academia", "ecg12")
_PROMPT_BY_ID = {question_id(bank, prompt): prompt for bank in QUIZ_BANKS for prompt in CONCEPT_BY_PROMPT}


def render_confidence_input(key: str) -> Optional[int]:
    return st.radio(CONFIDENCE_QUESTION, CONFIDENCE_LEVELS, index=None, horizontal=True,
                    format_func=CONFIDENCE_LABELS.get, key=key)


def record_answer(item_id: str, concept: str, correct: bool, confidence: Optional[int], mark: tuple,
                  label: Optional[str] = None) -> None:
    """Registra una respuesta en la sesión UNA sola vez por `mark`: la confianza que cuenta es la que había al
    responder; cambiarla después, ya con el resultado a la vista, no la modifica. `label` = el texto que el panel
    muestra en «errores con más confianza»."""
    recorded = st.session_state.setdefault(_RECORDED, set())
    if mark in recorded:
        return
    log_session_answer(item_id, "quiz", concept, correct, confidence)
    recorded.add(mark)
    if label:
        st.session_state.setdefault(_LABELS, {})[item_id] = label


def record_quiz_answer(bank: str, question, selected: str, confidence: Optional[int], attempt: str) -> bool:
    """Una pregunta de un banco (`QuizQuestion`). Devuelve False si no tiene concepto (no se registra)."""
    concept = CONCEPT_BY_PROMPT.get(question.prompt)
    if concept is None:
        return False
    record_answer(question_id(bank, question.prompt), concept, question.is_correct(selected), confidence,
                  mark=(bank, attempt, question.prompt), label=question.prompt)
    return True


def render_calibration_panel(expanded: bool = False) -> None:
    calibracion = cc.calibrar(get_session_log())
    with st.expander(PANEL_TITLE, expanded=expanded):
        st.caption(PANEL_INTRO)
        st.markdown(cc.frase(calibracion.total))
        if not calibracion.hay_datos:
            return

        if len(calibracion.por_concepto) > 1:
            st.markdown("**Por concepto**")
            for concepto, grupo in calibracion.por_concepto.items():
                st.markdown(f"- **{cc.CONCEPT_LABELS.get(concepto, concepto)}.** {cc.frase(grupo)}")

        st.markdown("**Por nivel de confianza**")
        st.table([{"Confianza": f"{nivel} %", "Respuestas": g.n, "Aciertos": g.aciertos,
                   "Acierto": f"{round(100 * g.acierto)} %"} for nivel, g in calibracion.por_nivel.items()])

        if calibracion.errores_mas_seguros:
            st.markdown("**Tus errores con más confianza** (repásalos primero)")
            for r in calibracion.errores_mas_seguros:
                enunciado = (st.session_state.get(_LABELS, {}).get(r["item_id"]) or _PROMPT_BY_ID.get(r["item_id"])
                             or cc.CONCEPT_LABELS.get(r["concept"], r["concept"]))
                st.markdown(f"- {enunciado} (dijiste {r['confidence']} %)")
        if calibracion.sin_confianza:
            st.caption(f"{calibracion.sin_confianza} respuesta(s) de esta sesión no llevan confianza y no cuentan aquí.")
        st.caption(f"Rango probable del acierto: intervalo de 95 % de Wilson [{cc.WILSON_KEY}]. {cc.WILSON_1927}")
