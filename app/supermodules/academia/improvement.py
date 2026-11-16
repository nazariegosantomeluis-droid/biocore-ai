"""«Mejora continua» de la Academia (2026-11-16): práctica adaptativa con el modelo de Elo y revisión del banco de
preguntas con el análisis clásico de ítems (`educational/learning_analytics.py`).

Todo se calcula en la computadora con las respuestas guardadas en la base local; nada se manda a ningún servicio.
El modelo no cambia el banco: solo dice qué practicar y qué revisar. Corregir una pregunta es trabajo de una
persona, con su fuente.
"""

from __future__ import annotations

from typing import List

import pandas as pd
import streamlit as st

from app.utils.design_system import render_section_header
from app.utils.learning_log import learner_id
from educational import learning_analytics as LA
from educational.quiz_bank import ACADEMIA_QUESTIONS

BANK = "academia"
BANK_LABELS = {"academia": "Academia", "ecg12": "12 Derivaciones", "eeg": "EEG Neuro Lab"}
ADAPTIVE_N = 5
ADAPTIVE_LESSON = "Práctica adaptativa"
ADAPTIVE_CAPTION = (
    f"Elige {ADAPTIVE_N} preguntas que el modelo estima que aciertas cerca de 3 de cada 4 veces: ni tan fáciles que "
    "no enseñen, ni tan difíciles que desanimen. Modelo de Elo para educación (Pelánek 2016), ajustado con las "
    "respuestas guardadas en esta computadora; sin respuestas tuyas todavía, todas las preguntas empiezan igual."
)


def adaptive_questions() -> List:
    state = LA.fit_elo(LA.load_answers(bank=BANK))
    return LA.suggest_questions(state, learner_id(), ACADEMIA_QUESTIONS, BANK, n=ADAPTIVE_N)


def render_learner_progress() -> None:
    rows = LA.learner_summary(LA.fit_elo(LA.load_answers()), learner_id())
    if not rows:
        st.info(f"Todavía no hay respuestas de «{learner_id()}». Responde un cuestionario y vuelve aquí.")
        return
    st.dataframe(pd.DataFrame([{"Tema": category, "Acertarías (estimado)": f"{p * 100:.0f} %", "Respuestas": n}
                               for category, p, n in rows]), hide_index=True)
    st.caption(
        "«Acertarías» es la probabilidad que estima el modelo de Elo de que aciertes una pregunta de dificultad "
        "media de ese tema (Pelánek 2016). Es una estimación que cambia con cada respuesta, no una calificación; "
        "con pocas respuestas es poco precisa. Los temas van del más débil al más fuerte. Fuente: " + LA.PELANEK_2016
    )


def _discrimination_text(item) -> str:
    if item.discrimination is None:
        return ""
    low, high = item.discrimination_ci
    return f"{item.discrimination:+.2f} ({low:+.2f} a {high:+.2f})"


def review_table() -> pd.DataFrame:
    questions = LA.load_questions()
    stats = LA.item_statistics(LA.load_answers(), LA.load_reports(),
                               {qid: q["correct_choice"] for qid, q in questions.items()})
    rows = []
    for qid, item in stats.items():
        question = questions.get(qid, {})
        notes = [LA.FLAG_TEXT[flag] for flag in item.flags]
        if item.responses < LA.MIN_RESPONSES:
            notes.append(f"Pocos datos: {item.responses} de {LA.MIN_RESPONSES} respuestas para calcular los índices.")
        rows.append({
            "Revisar": "⚠️" if item.needs_review else "",
            "Banco": BANK_LABELS.get(question.get("bank"), question.get("bank")),
            "Tema": question.get("category"),
            "Pregunta": question.get("prompt"),
            "Respuesta marcada como correcta": question.get("correct_choice"),
            "Respuestas": item.responses,
            "% aciertos": None if item.difficulty is None else round(100 * item.difficulty),
            "Discriminación (IC 95 %)": _discrimination_text(item),
            "Avisos": " ".join(notes),
            "Reportes": " | ".join(item.reports),
        })
    columns = ["Revisar", "Banco", "Tema", "Pregunta", "Respuesta marcada como correcta", "Respuestas", "% aciertos",
               "Discriminación (IC 95 %)", "Avisos", "Reportes"]
    table = pd.DataFrame(rows, columns=columns)
    if not table.empty:
        table = table.sort_values(["Revisar", "Respuestas"], ascending=[False, False], kind="stable")
    return table.reset_index(drop=True)


def render_bank_review() -> None:
    table = review_table()
    if table.empty:
        st.info("Todavía no hay respuestas ni reportes guardados en esta computadora.")
        return
    flagged = int((table["Revisar"] == "⚠️").sum())
    st.markdown(f"**{flagged}** de {len(table)} preguntas con respuestas o reportes piden revisión.")
    st.dataframe(table, hide_index=True)
    st.download_button("⬇ Descargar la revisión (CSV)", table.to_csv(index=False).encode("utf-8"),
                       file_name="revision_banco_de_preguntas.csv", mime="text/csv", key="academia_review_csv")
    st.caption(
        "Cómo se calcula: «% aciertos» es el índice de dificultad; «Discriminación» es la correlación punto-biserial "
        "entre acertar la pregunta y el resto del mismo intento, con su intervalo de confianza de 95 %. Dificultad "
        f"moderada entre 40 y 80 % de aciertos, y una discriminación menor de {LA.LOW_DISCRIMINATION:g} pide revisión "
        "(Ali & Ruit 2015). Criterio BIOCORE: con pocos datos la discriminación es ruido, así que solo se marca "
        "cuando todo el intervalo queda por debajo del corte; si queda por debajo de 0, o si el grupo alto elige un "
        "distractor más que la opción marcada (prueba binomial, p < 0.05), se pide revisar la clave. Cuenta la "
        f"primera respuesta de cada pregunta en cada intento, y con menos de {LA.MIN_RESPONSES} respuestas no se "
        "calcula nada. Nada cambia solo: cada corrección la hace una persona, con su fuente. Fuente: "
        + LA.ALI_RUIT_2015
    )


def render_continuous_improvement() -> None:
    st.markdown("---")
    render_section_header("📈 Mejora continua")
    st.caption("Calculado en esta computadora con las respuestas guardadas aquí (base local, fuera del repositorio); "
               "no se manda a ningún servicio.")
    with st.expander(f"Tu dominio estimado por tema — {learner_id()}", expanded=False):
        render_learner_progress()
    with st.expander("Revisión del banco de preguntas (para quien revisa el contenido)", expanded=False):
        render_bank_review()
