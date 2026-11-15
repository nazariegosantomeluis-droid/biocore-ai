"""Referencias y quiz del EEG Neuro Lab (tanda 1 de la fase 1: movidos aquí desde `page_content.py` SIN cambiar el
contenido, para que Aprender y Practicar los monten solos). Contención (Art. I): las opciones del quiz ya no vienen
preseleccionadas (antes «Calcular puntuación» calificaba la primera opción de cada pregunta aunque el estudiante no
hubiera elegido nada) y cada pregunta dice «Correcto»/«Incorrecto» con su explicación. Nombres de patrón en español
(decisión 7): «Sleep Spindle», «Seizure» y «Artifact» pasan a «Huso de sueño», «Crisis (espigas)» y «Artefacto»."""

import streamlit as st

EEG_QUIZ = [
    {
        "question": "¿Qué banda EEG se asocia con sueño profundo?",
        "options": ["Alfa", "Beta", "Theta", "Delta"],
        "answer": "Delta",
        "explanation": "Delta es la banda más lenta y se observa en sueño profundo.",
    },
    {
        "question": "¿Qué banda es típica en un estado de concentración y alerta?",
        "options": ["Alfa", "Beta", "Theta", "Delta"],
        "answer": "Beta",
        "explanation": "Beta aumenta durante la atención activa y la cognición.",
    },
    {
        "question": "¿Cuál es la banda predominante en relajación con los ojos cerrados?",
        "options": ["Alfa", "Beta", "Theta", "Gamma"],
        "answer": "Alfa",
        "explanation": "Alfa es común con ojos cerrados y estados relajados.",
    },
    {
        "question": "¿Qué patrón EEG puede corresponder a una crisis epiléptica simulada?",
        "options": ["Alfa", "Huso de sueño", "Crisis (espigas)", "Artefacto"],
        "answer": "Crisis (espigas)",
        "explanation": "Las espigas de alto voltaje y frecuencia son típicas de crisis.",
    },
    {
        "question": "¿Qué banda se relaciona con somnolencia ligera y transición al sueño?",
        "options": ["Alfa", "Beta", "Theta", "Delta"],
        "answer": "Theta",
        "explanation": "Theta se observa en somnolencia y sueño ligero.",
    },
]


def render_eeg_references() -> None:
    st.markdown("---")
    st.markdown("## 📚 Referencias EEG")
    st.write("**Banda Delta:** sueño profundo, 0.5-4 Hz")
    st.write("**Banda Theta:** somnolencia, 4-8 Hz")
    st.write("**Banda Alfa:** relajación con ojos cerrados, 8-12 Hz")
    st.write("**Banda Beta:** alerta y concentración, 13-30 Hz")
    st.write("**Banda Gamma:** procesamiento cognitivo integrado, 30-45 Hz")


def render_eeg_quiz(expanded: bool = False) -> None:
    with st.expander("🧪 Quiz interactivo EEG", expanded=expanded):
        user_answers = []
        for idx, item in enumerate(EEG_QUIZ, start=1):
            user_answers.append(st.radio(item["question"], item["options"], index=None, key=f"quiz_{idx}"))

        if st.button("Calcular puntuación", key="submit_eeg_quiz", disabled=any(a is None for a in user_answers)):
            score = sum(1 for answer, item in zip(user_answers, EEG_QUIZ) if answer == item["answer"])
            st.success(f"Has respondido {score} de {len(EEG_QUIZ)} correctamente.")
            for item, answer in zip(EEG_QUIZ, user_answers):
                st.write(f"**Pregunta:** {item['question']}")
                if answer == item["answer"]:
                    st.write(f"- ✅ Correcto: {answer}")
                else:
                    st.write(f"- ❌ Incorrecto: elegiste {answer}; la correcta es {item['answer']}")
                st.write(f"- Explicación: {item['explanation']}")
                st.write("---")
        elif any(a is None for a in user_answers):
            st.caption("Responde las cinco preguntas para calcular la puntuación.")
