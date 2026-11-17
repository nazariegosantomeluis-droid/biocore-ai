"""«Tu aprendizaje en esta sesión» (Practicar, 2026-11-17).

Lee SOLO `app.utils.session_learning.get_session_log()`, el registro de la sesión que escriben los ejercicios
conectados a ella (contrato de `session_learning.py`, que este módulo no modifica), y muestra:

- aciertos por concepto, para los 8 de `CONCEPTS`, con el número de respuestas;
- calibración: confianza promedio frente a acierto real por tramos de confianza (0–49, 50–69, 70–89, 90–100) y el
  puntaje de Brier de la sesión;
- un mensaje de exceso o falta de confianza, solo con `MIN_CONFIDENT_ANSWERS` o más respuestas con confianza.

Art. I: sin respuestas no se muestra ningún número (estado vacío). El margen del mensaje es heurístico y se rotula
así. El cálculo (`summarize`) no usa Streamlit, para probarlo con un registro sintético.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Mapping, Optional, Sequence, Tuple

from app.utils.session_learning import CONCEPTS

PAGE_TITLE = "Tu aprendizaje en esta sesión"
PRIVACY_NOTICE = "Se borra al cerrar la sesión; no se guarda ningún dato personal"
EMPTY_MESSAGE = "Todavía no hay respuestas registradas en esta sesión"

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

MIN_CONFIDENT_ANSWERS = 5     # la especificación: el mensaje solo con 5 o más respuestas con confianza
# HEURISTIC (sin cita): diferencia, en puntos porcentuales, entre la confianza promedio y el acierto a partir de la
# cual el mensaje habla de exceso o de falta de confianza. En pantalla lleva la etiqueta «Heurística».
CALIBRATION_MARGIN_PTS = 10

# Brier GW. Verification of forecasts expressed in terms of probability. Mon Weather Rev 1950;78(1):1–3.
# Se usa la forma binaria (media de (p − o)², de 0 a 1); la formulación original suma las dos categorías y va de 0 a 2.
BRIER_FORMULA = "promedio de (confianza/100 − acierto)², con acierto = 1 si respondiste bien y 0 si no"


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
    brier: Optional[float]
    calibration: Optional[str]        # "exceso" | "falta" | "dentro" | None (menos de MIN_CONFIDENT_ANSWERS)


def _band_of(confidence: int) -> Optional[Tuple[int, int]]:
    return next(((lo, hi) for lo, hi in CONFIDENCE_BANDS if lo <= confidence <= hi), None)


def brier_score(entries: Iterable[Mapping]) -> Optional[float]:
    """Forma binaria del puntaje de Brier sobre las respuestas con confianza; None si no hay ninguna."""
    terms = [(e["confidence"] / 100.0 - (1.0 if e["correct"] else 0.0)) ** 2
             for e in entries if e.get("confidence") is not None]
    return sum(terms) / len(terms) if terms else None


def calibration_verdict(mean_confidence: float, accuracy: float) -> str:
    gap = mean_confidence - accuracy * 100.0
    if gap > CALIBRATION_MARGIN_PTS:
        return "exceso"
    if gap < -CALIBRATION_MARGIN_PTS:
        return "falta"
    return "dentro"


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
    verdict = (calibration_verdict(mean_conf, acc_conf)
               if len(confident) >= MIN_CONFIDENT_ANSWERS and mean_conf is not None else None)
    return SessionSummary(len(entries), concepts, tuple(bands), len(confident), mean_conf, acc_conf,
                          brier_score(confident), verdict)


def calibration_message(summary: SessionSummary) -> Optional[str]:
    """El texto del mensaje, o None si todavía no hay suficientes respuestas con confianza."""
    if summary.calibration is None:
        return None
    conf = f"{summary.mean_confidence:.0f} %"
    acc = f"{summary.accuracy_confident * 100:.0f} %"
    if summary.calibration == "exceso":
        return (f"Exceso de confianza: tu confianza promedio ({conf}) supera tu acierto ({acc}) por más de "
                f"{CALIBRATION_MARGIN_PTS} puntos.")
    if summary.calibration == "falta":
        return (f"Falta de confianza: tu acierto ({acc}) supera tu confianza promedio ({conf}) por más de "
                f"{CALIBRATION_MARGIN_PTS} puntos.")
    return (f"Tu confianza promedio ({conf}) y tu acierto ({acc}) están a {CALIBRATION_MARGIN_PTS} puntos o menos "
            "uno del otro.")


# ───────────────────────────── página ─────────────────────────────

def render_session_learning_page() -> None:
    import pandas as pd
    import streamlit as st

    from app.utils.design_system import BADGES, badge_html, render_empty_state, render_module_header
    from app.utils.session_learning import get_session_log

    render_module_header(PAGE_TITLE, icon="📊")
    st.caption(PRIVACY_NOTICE)

    summary = summarize(get_session_log())
    if summary.total == 0:
        render_empty_state(EMPTY_MESSAGE)
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
    st.markdown(f"**Puntaje de Brier de la sesión:** {summary.brier:.2f} "
                f"({summary.confident_answers} respuestas con confianza)")
    st.caption(f"Puntaje de Brier, forma binaria: {BRIER_FORMULA}. Va de 0 a 1; 0 es dar confianza 100 a lo que aciertas y "
               "0 a lo que fallas. Brier GW, Mon Weather Rev 1950;78(1):1–3.")

    message = calibration_message(summary)
    if message is None:
        st.caption(f"El mensaje de exceso o falta de confianza aparece con {MIN_CONFIDENT_ANSWERS} o más respuestas "
                   f"con confianza; llevas {summary.confident_answers}.")
        return
    st.markdown(message)
    st.markdown(f"{badge_html(BADGES.HEURISTIC)} &nbsp;Margen de {CALIBRATION_MARGIN_PTS} puntos: criterio de "
                "ingeniería, sin cita.", unsafe_allow_html=True)
