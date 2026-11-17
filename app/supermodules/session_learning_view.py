"""«Tu aprendizaje en esta sesión» (Practicar, 2026-11-17).

Lee SOLO `app.utils.session_learning.get_session_log()`, el registro de la sesión que escriben los ejercicios
conectados a ella (contrato de `session_learning.py`, que este módulo no modifica), y muestra:

- aciertos por concepto, para los 8 de `CONCEPTS`, con el número de respuestas;
- calibración: confianza promedio frente a acierto real por tramos de confianza (0–49, 50–69, 70–89, 90–100) y el
  puntaje de Brier de la sesión;
- el veredicto de exceso o falta de confianza.

Un solo criterio de calibración en pantalla (2026-11-17): el veredicto y el Brier salen de
`educational/confidence_calibration.py` (intervalo de Wilson al 95 % [WILSON1927]; Brier binario [BRIER1950]), los
mismos del panel «Tu calibración en esta sesión» del quiz. Se retiró el margen heurístico de 10 puntos.

Art. I: sin respuestas no se muestra ningún número (estado vacío). El cálculo (`summarize`) no usa Streamlit, para
probarlo con un registro sintético.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Mapping, Optional, Sequence, Tuple

from app.utils.session_learning import CONCEPTS
from educational import confidence_calibration as cc

PAGE_TITLE = "Tu aprendizaje en esta sesión"
PRIVACY_NOTICE = "Se borra al cerrar la sesión; no se guarda ningún dato personal"
EMPTY_MESSAGE = "Todavía no hay respuestas registradas en esta sesión"
EMPTY_ACTION = "aparecen aquí en cuanto respondes un ejercicio conectado al registro de la sesión"

# Rótulos en pantalla de los conceptos del contrato (las claves no se traducen; una prueba exige las 8).
CONCEPT_LABELS = {
    "frecuencia_cardiaca": "Frecuencia cardiaca",
    "ritmo_y_conduccion": "Ritmo y conducción",
    "derivaciones_e_isquemia": "Derivaciones e isquemia",
    "news2": "NEWS2",
    "respiracion_y_apnea": "Respiración y apnea",
    "hemodinamica": "Hemodinámica",
    "emg": "EMG",
    "hrv": "HRV",
}

# Tramos de confianza, en puntos de 0 a 100 (ambos extremos incluidos).
CONFIDENCE_BANDS: Tuple[Tuple[int, int], ...] = ((0, 49), (50, 69), (70, 89), (90, 100))



@dataclass(frozen=True)
class ConceptRow:
    concept: str
    label: str
    answers: int
    correct: int


@dataclass(frozen=True)
class BandRow:
    low: int
    high: int
    answers: int
    mean_confidence: Optional[float]   # puntos 0–100; None sin respuestas en el tramo
    accuracy: Optional[float]          # fracción 0–1; None sin respuestas en el tramo

    @property
    def label(self) -> str:
        return f"{self.low}–{self.high}"


@dataclass(frozen=True)
class SessionSummary:
    total: int
    concepts: Tuple[ConceptRow, ...]
    bands: Tuple[BandRow, ...]
    confident_answers: int
    mean_confidence: Optional[float]
    accuracy_confident: Optional[float]
    brier: Optional[float]            # `confidence_calibration.brier` (forma binaria [BRIER1950])
    calibration: Optional[str]        # veredicto de `confidence_calibration` (exceso | falta | calibrada) o None
    calibracion: Optional["cc.Calibracion"] = None   # el resultado completo, para la misma frase y el mismo Brier


def _band_of(confidence: int) -> Optional[Tuple[int, int]]:
    return next(((lo, hi) for lo, hi in CONFIDENCE_BANDS if lo <= confidence <= hi), None)


def summarize(log: Sequence[Mapping]) -> SessionSummary:
    entries = [e for e in log if e.get("concept") in CONCEPTS]
    concepts = tuple(
        ConceptRow(c, CONCEPT_LABELS[c], sum(1 for e in entries if e["concept"] == c),
                   sum(1 for e in entries if e["concept"] == c and e["correct"]))
        for c in CONCEPTS
    )
    confident = [e for e in entries if e.get("confidence") is not None]
    bands: List[BandRow] = []
    for lo, hi in CONFIDENCE_BANDS:
        inside = [e for e in confident if _band_of(e["confidence"]) == (lo, hi)]
        if inside:
            bands.append(BandRow(lo, hi, len(inside), sum(e["confidence"] for e in inside) / len(inside),
                                 sum(1 for e in inside if e["correct"]) / len(inside)))
        else:
            bands.append(BandRow(lo, hi, 0, None, None))
    mean_conf = sum(e["confidence"] for e in confident) / len(confident) if confident else None
    acc_conf = sum(1 for e in confident if e["correct"]) / len(confident) if confident else None
    calibracion = cc.calibrar(entries)
    verdict = calibracion.total.veredicto if calibracion.hay_datos else None
    return SessionSummary(len(entries), concepts, tuple(bands), len(confident), mean_conf, acc_conf,
                          calibracion.brier, verdict, calibracion)


def calibration_message(summary: SessionSummary) -> Optional[str]:
    """La misma frase del panel del quiz (`confidence_calibration.frase`), o None sin respuestas con confianza."""
    if summary.calibracion is None or not summary.calibracion.hay_datos:
        return None
    return cc.frase(summary.calibracion.total)


# ───────────────────────────── página ─────────────────────────────

def render_session_learning_page() -> None:
    import pandas as pd
    import streamlit as st

    from app.utils.design_system import render_empty_state, render_module_header
    from app.utils.session_learning import get_session_log

    render_module_header(PAGE_TITLE, icon="📊")
    st.caption(PRIVACY_NOTICE)

    summary = summarize(get_session_log())
    if summary.total == 0:
        render_empty_state(EMPTY_MESSAGE, action=EMPTY_ACTION)
        return

    st.markdown("#### Aciertos por concepto")
    st.dataframe(pd.DataFrame([
        {"Concepto": row.label,
         "Respuestas": str(row.answers) if row.answers else "Sin respuestas",
         "Aciertos": f"{row.correct} de {row.answers}" if row.answers else "Sin respuestas"}
        for row in summary.concepts
    ]), hide_index=True, use_container_width=True)

    st.markdown("#### Calibración de tu confianza")
    if summary.confident_answers == 0:
        st.caption("Ninguna respuesta de esta sesión pidió tu confianza: no hay calibración que mostrar.")
        return
    st.dataframe(pd.DataFrame([
        {"Confianza declarada": band.label,
         "Respuestas": str(band.answers) if band.answers else "Sin respuestas",
         "Confianza promedio": f"{band.mean_confidence:.0f} %" if band.answers else "Sin respuestas",
         "Acierto real": f"{band.accuracy * 100:.0f} %" if band.answers else "Sin respuestas"}
        for band in summary.bands
    ]), hide_index=True, use_container_width=True)
    from app.utils.confidence import brier_text

    st.markdown(brier_text(summary.calibracion))
    st.markdown(calibration_message(summary))
    st.caption(f"Rango probable del acierto: intervalo de 95 % de Wilson. {cc.WILSON_1927}")
