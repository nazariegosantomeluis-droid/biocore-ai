"""Referencias y quiz del EEG Neuro Lab (tanda 1 de la fase 1: viven aquí, fuera de `page_content.py`, para que
Aprender y Practicar los monten solos).

Integración (2026-11-16, Art. I):
- Referencias: antes cinco líneas sin fuente («Gamma: procesamiento cognitivo integrado», «Beta: alerta y
  concentración»...). Ahora el glosario IFCN 2017 (Kane 2017) al lado de los bordes que de verdad usa este laboratorio
  (`EegAnalyzer._band_powers`), que difieren un poco del glosario.
- Quiz: el banco vive en `educational/quiz_bank.py::EEG_QUESTIONS`, con su fuente. Antes la pregunta de crisis se
  respondía sola («crisis epiléptica» → «Seizure»). Contención de la tanda 1: ninguna opción preseleccionada y
  «Calcular puntuación» deshabilitado hasta que se responden todas. Cada envío distinto es un intento para la mejora
  continua (`app/utils/learning_log.py`); volver a pulsar sin cambiar nada no lo repite.
"""

import streamlit as st

from app.utils.learning_log import log_answer, render_report_box
from educational.learning_analytics import new_attempt
from educational.quiz_bank import EEG_QUESTIONS, KANE_2017

BANK = "eeg"


def render_eeg_references() -> None:
    st.markdown("---")
    st.markdown("## 📚 Referencias EEG")
    st.markdown(
        "| Banda | Glosario IFCN 2017 | Este laboratorio |\n"
        "|---|---|---|\n"
        "| Delta | 0.1 a menos de 4 Hz | 0.5–3.5 Hz |\n"
        "| Theta | 4 a menos de 8 Hz | 4–7.5 Hz |\n"
        "| Alfa | 8–13 Hz | 8–12 Hz |\n"
        "| Beta | 14–30 Hz | 13–30 Hz |\n"
        "| Gamma | más de 30, hasta 80 Hz | 30–45 Hz |"
    )
    st.markdown(
        "- **Delta:** el sueño profundo (NREM N3) está dominado (≥ 20 %) por ondas delta de 0.5–2 Hz y "
        "más de 75 µV. En la práctica, el límite inferior es 0.5 Hz.\n"
        "- **Alfa:** ritmo de vigilia sobre las regiones posteriores; se ve mejor con los ojos cerrados y se "
        "bloquea con la atención, sobre todo visual.\n"
        "- **Beta:** en vigilia, sobre todo fronto-central; si es difuso puede deberse a fármacos (alcohol, "
        "barbitúricos, benzodiacepinas, anestésicos intravenosos)."
    )
    st.caption(f"Fuente: {KANE_2017}")


def render_eeg_quiz(expanded: bool = False) -> None:
    with st.expander("🧪 Quiz interactivo EEG", expanded=expanded):
        user_answers = []
        for idx, item in enumerate(EEG_QUESTIONS, start=1):
            user_answers.append(st.radio(item.prompt, item.display_choices(), index=None, key=f"eeg_quiz_{idx}"))

        missing = any(a is None for a in user_answers)
        if st.button("Calcular puntuación", key="submit_eeg_quiz", disabled=missing):
            if st.session_state.get("eeg_quiz_logged") != tuple(user_answers):
                attempt = new_attempt()
                for item, answer in zip(EEG_QUESTIONS, user_answers):
                    log_answer(BANK, item, answer, attempt)
                st.session_state["eeg_quiz_logged"] = tuple(user_answers)
            score = sum(1 for answer, item in zip(user_answers, EEG_QUESTIONS) if item.is_correct(answer))
            st.success(f"Has respondido {score} de {len(EEG_QUESTIONS)} correctamente.")
            for item, answer in zip(EEG_QUESTIONS, user_answers):
                st.write(f"**Pregunta:** {item.prompt}")
                if item.is_correct(answer):
                    st.write(f"- ✅ Correcto: {answer}")
                else:
                    st.write(f"- ❌ Incorrecto: elegiste {answer}; la correcta es {item.correct_choice}")
                st.write(f"- Explicación: {item.explanation}")
                st.caption(f"Fuente: {item.source}")
                st.write("---")
        elif missing:
            st.caption(f"Responde las {len(EEG_QUESTIONS)} preguntas para calcular la puntuación.")
        render_report_box(BANK, EEG_QUESTIONS, key="eeg_quiz_report", in_expander=True)
