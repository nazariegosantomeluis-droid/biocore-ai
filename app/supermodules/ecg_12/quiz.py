"""Desafío educativo de ECG-12 (tanda 1 de la fase 1: vive aquí para que Practicar lo monte solo).

Integración (2026-11-16): el banco de preguntas es `educational/quiz_bank.py::ECG12_QUESTIONS`, cada pregunta con su
explicación y su fuente (antes vivía aquí, sin fuentes y con errores: la pericarditis al revés, «derivadas sintéticas»
desde una sola derivación, un SNR sin unidades, el patrón de HVI llamado «pseudo-infarto»; ver CHANGELOG.md). Las
opciones salen en el orden de `display_choices()`.

Contención (Art. I): ninguna opción preseleccionada y «Verificar respuesta» deshabilitado hasta que se elige una; la
corrección solo aparece después de verificar. La primera respuesta de cada pregunta en la sesión va a la base local
de la mejora continua (`app/utils/learning_log.py`), y cada pregunta tiene su caja para reportar un problema.
"""

import streamlit as st

from app.utils.confidence import record_quiz_answer, render_confidence_input
from app.utils.learning_log import log_answer, render_report_box, session_attempt
from educational.quiz_bank import ECG12_QUESTIONS

BANK = "ecg12"


def render_ecg12_quiz(key_prefix: str = "") -> None:
    question_index = st.selectbox(
        "Selecciona la pregunta:",
        list(range(1, len(ECG12_QUESTIONS) + 1)),
        format_func=lambda x: f"Pregunta {x}",
        key=f"{key_prefix}ecglab_12_quiz_question",
    )
    current_question = ECG12_QUESTIONS[question_index - 1]

    st.write(f"**Pregunta {question_index}:** {current_question.prompt}")
    selected_answer = st.radio(
        "Respuesta:", current_question.display_choices(), index=None,
        key=f"{key_prefix}ecglab_12_quiz_{question_index}",
    )
    # 2026-11-17: confianza opcional, antes de verificar (calibración; `app/utils/confidence.py`).
    confidence = render_confidence_input(key=f"{key_prefix}ecglab_12_confidence_{question_index}")

    if st.button("Verificar respuesta", key=f"{key_prefix}ecglab_12_quiz_verify", disabled=selected_answer is None):
        attempt = session_attempt("ecglab_12_quiz_attempt")
        log_answer(BANK, current_question, selected_answer, attempt)
        record_quiz_answer(BANK, current_question, selected_answer, confidence, attempt)
        if current_question.is_correct(selected_answer):
            st.success(f"✅ Correcto. {current_question.explanation}")
        else:
            st.error(
                f"❌ Incorrecto: la respuesta es **{current_question.correct_choice}**. "
                f"{current_question.explanation}"
            )
        st.caption(f"Fuente: {current_question.source}")
    render_report_box(BANK, [current_question], key=f"{key_prefix}ecglab_12_report_{question_index}")
