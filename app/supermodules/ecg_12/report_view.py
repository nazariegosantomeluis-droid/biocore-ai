"""Vista del análisis de 12 derivaciones (2026-11-14, Art. I).

Separa lo medido (🟣 método BIOCORE) de lo que cumple un criterio publicado (🟢, con su fuente)
y de lo que no se pudo evaluar (con el motivo). Reemplaza el banner de «diagnóstico principal»
y las «recomendaciones» de `TwelveLeadEcgAnalyzer`, que no salían de ninguna medición. Vive
aparte de `page_content.py` para poder probarla sola.
"""

from __future__ import annotations

from typing import Optional

import streamlit as st

from src.signals.ecg.twelve_lead_measure import LEADS, METHOD_NOTE, TwelveLeadReport
from src.signals.ecg.twelve_lead_synth import TwelveLeadTruth

STATUS_TEXT = {True: "Cumple", False: "No cumple", None: "No evaluable"}
NORMAL_WHEN_MET = ("sinus", "t_wave")      # criterios que describen lo normal: se muestran en otro lugar
P_TEXT = {
    "sinusal": "sinusal (positiva en I, II y aVF)",
    "presente": "presente en II (faltan I o aVF para ver su polaridad)",
    "no sinusal": "hay actividad auricular, pero no es una P sinusal",
    "ausente": "sin onda P constante antes del QRS",
    "no evaluable": "no evaluable (falta II)",
}


def _ms(value: Optional[float]) -> str:
    return "no disponible" if value is None else f"{value:.0f} ms"


def _mm(value_mv: float) -> str:
    return f"{round(value_mv * 10, 1) + 0.0:+.1f}"      # + 0.0: sin «−0.0»


def findings(report: TwelveLeadReport) -> list:
    """Hallazgos: criterios cumplidos (salvo los que describen lo normal) y la onda T anormal."""
    out = [c for c in report.criteria if c.met is True and c.key not in NORMAL_WHEN_MET]
    out += [c for c in report.criteria if c.key == "t_wave" and c.met is False]
    return out


def finding_title(c) -> str:
    return "Onda T negativa donde se espera positiva" if c.key == "t_wave" and c.met is False else c.title


def render_twelve_lead_report(report: TwelveLeadReport, truth: Optional[TwelveLeadTruth] = None) -> None:
    st.caption("🟣 " + METHOD_NOTE + " No es un diagnóstico.")
    if report.n_beats == 0:
        st.warning("No se pudo analizar este registro: " + " ".join(report.unavailable))
        return

    found = findings(report)
    summary = ", ".join(finding_title(c) for c in found) if found else "ninguno de los criterios evaluados se cumple"
    st.markdown(f"> **Hallazgos automáticos:** {summary}.")

    st.markdown(f"**Mediciones** 🟣 (latido mediano de {report.n_beats} latidos)")
    rhythm = "regulares" if report.regular else "irregulares"
    axis = "no disponible" if report.axis is None else f"{report.axis.axis_degrees:.0f}°"
    rows = [
        ("Frecuencia cardiaca", f"{report.heart_rate_bpm:.0f} lpm"),
        ("Intervalos RR", f"{rhythm} (coeficiente de variación {report.rr_cv * 100:.0f} %)"),
        ("Onda P", P_TEXT.get(report.p_wave, report.p_wave)),
        ("PR", _ms(report.pr_ms)),
        ("QRS", _ms(report.qrs_ms)),
        ("QT", _ms(report.qt_ms)),
        ("QTc (Bazett)", _ms(report.qtc_ms)),
        ("Eje del QRS", axis),
    ]
    st.markdown("| Medida | Valor |\n|---|---|\n" + "\n".join(f"| {k} | {v} |" for k, v in rows))
    if report.st_j_mv:
        st.caption("ST en el punto J (mm, 1 mm = 0.1 mV): "
                   + " · ".join(f"{ld} {_mm(report.st_j_mv[ld])}" for ld in LEADS if ld in report.st_j_mv))

    st.markdown("**Hallazgos que cumplen un criterio publicado** 🟢")
    if not found:
        st.write("Ninguno.")
    for c in found:
        st.markdown(f"- **{finding_title(c)}.** {c.detail}")
        st.caption(f"Fuente: {c.source}")

    undetermined = [c for c in report.criteria if c.met is None]
    if undetermined:
        st.markdown("**No evaluables en este registro**")
        for c in undetermined:
            st.markdown(f"- **{c.title}.** {c.detail}")
            st.caption(f"Fuente: {c.source}")

    with st.expander("Criterios evaluados que no se cumplen"):
        for c in report.criteria:
            if c.met is False and c.key not in NORMAL_WHEN_MET:
                st.markdown(f"- **{c.title}.** {c.detail}")
                st.caption(f"Fuente: {c.source}")

    if report.unavailable:
        st.caption("Límites de este registro: " + " ".join(report.unavailable))

    if truth is not None:
        with st.expander("Lo que construyó el generador (para comparar; el analizador no lo lee)"):
            st.markdown(
                "| Medida | Construido |\n|---|---|\n"
                f"| Ritmo | {truth.rhythm} |\n"
                f"| FC | {truth.heart_rate_bpm:.0f} lpm |\n"
                f"| PR | {_ms(truth.pr_ms)} |\n"
                f"| QRS | {_ms(truth.qrs_ms)} |\n"
                f"| QT / QTc | {_ms(truth.qt_ms)} / {_ms(truth.qtc_bazett_ms)} |\n"
                f"| Eje | {truth.axis_deg:.0f}° |\n"
                f"| Bloqueo de rama | {truth.bundle_branch_block or 'no'} |\n"
                f"| Preexcitación | {'sí' if truth.preexcitation else 'no'} |\n"
                f"| S en V1 + R en V5/V6 | {truth.sokolow_lyon_mv:.2f} mV |"
            )
            st.caption("ST en el punto J construido (mm): "
                       + " · ".join(f"{ld} {_mm(truth.st_j_mv[ld])}" for ld in LEADS))
            st.caption("Trazado sintético: las amplitudes son ilustrativas; los tiempos y los rasgos de cada escenario "
                       "se construyen para cumplir (o no) los criterios citados.")
