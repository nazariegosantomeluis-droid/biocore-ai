"""Registro de respuestas de ESTA sesión, para Detective, What If? y la calibración de la confianza.

Art. I: vive solo en la sesión del navegador y se borra al cerrarla; no guarda datos personales
ni escribe en ninguna base. Es independiente de app/utils/learning_log.py (mejora continua de
los bancos), que no se modifica.
"""
from __future__ import annotations

from datetime import datetime, timezone

import streamlit as st

_KEY = "session_learning_log"

# Vocabulario único de conceptos (no inventar otros sin acordarlo).
CONCEPTS = (
    "frecuencia_cardiaca",
    "ritmo_y_conduccion",
    "derivaciones_e_isquemia",
    "news2",
    "respiracion_y_apnea",
    "hemodinamica",
    "emg",
    "hrv",
)

SOURCES = ("quiz", "caso_guiado", "detective", "what_if")


def log_session_answer(item_id: str, source: str, concept: str, correct: bool,
                       confidence: int | None = None) -> None:
    """Registra una respuesta en la sesión. confidence: 0–100, o None si no se pidió."""
    if source not in SOURCES:
        raise ValueError(f"source desconocido: {source}")
    if concept not in CONCEPTS:
        raise ValueError(f"concepto desconocido: {concept}")
    if confidence is not None and not 0 <= confidence <= 100:
        raise ValueError("confidence debe estar entre 0 y 100")
    st.session_state.setdefault(_KEY, []).append({
        "item_id": item_id,
        "source": source,
        "concept": concept,
        "correct": bool(correct),
        "confidence": confidence,
        "ts": datetime.now(timezone.utc).isoformat(),
    })


def get_session_log() -> list[dict]:
    """Copia del registro de la sesión."""
    return list(st.session_state.get(_KEY, []))