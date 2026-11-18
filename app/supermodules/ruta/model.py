"""Estaciones y avance de la ruta (T3, 2026-11-18).

El avance vive en `st.session_state` y se dice en pantalla que se pierde al cerrar: no hay identidad ni persistencia
de estudiantes (decisión 1 firmada). Una estación cuenta como visitada; nunca como «dominada».
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

import streamlit as st

PROGRESS_KEY = "ruta_progress"
PROGRESS_NOTE = ("Tu avance en la ruta vive solo en esta sesión del navegador: se pierde al cerrar. Una estación cuenta "
                 "como visitada, no como dominada.")

# Tipos de estación del diseño firmado («La ruta (T3 y T4)»).
KIND_LABELS = {"paciente": "Tu paciente", "concepto": "Concepto", "observa": "Observa", "mide": "Mide",
               "practica": "Practica", "altera": "Altera", "cierre": "Cierre"}


@dataclass(frozen=True)
class Station:
    key: str
    kind: str                       # una clave de KIND_LABELS
    title: str
    render: Callable[[], None]
    needs_patient: bool = True      # sin el paciente de la unidad, la estación dice «sin dato» y no se dibuja


@dataclass(frozen=True)
class Unit:
    key: str
    title: str
    stations: tuple
    pending: tuple = ()             # (estación, qué le falta): una estación sin contenido firmado no se dibuja


def progress(unit_key: str) -> dict:
    """El avance de la unidad en esta sesión (se crea vacío la primera vez)."""
    all_units = st.session_state.setdefault(PROGRESS_KEY, {})
    return all_units.setdefault(unit_key, {"station": 0, "visited": {0}, "patient_id": None, "scenario": None,
                                           "start": {}, "trajectory": []})


def go_to(unit_key: str, index: int) -> None:
    p = progress(unit_key)
    p["station"] = index
    p["visited"].add(index)


def unit_patient_id(unit_key: str) -> Optional[str]:
    return progress(unit_key).get("patient_id")
