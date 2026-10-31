"""
HRV no lineal en el HRV Lab -- 2026-10-31, sub-arco HRV no lineal.

Muestra SampEn, DFA α1 y Poincaré (SD1/SD2) de la serie RR junto a los de su
SUSTITUTO BARAJADO (mismos valores, orden al azar, semilla fija): barajar
conserva la distribución y destruye la estructura temporal, así que el
contraste serie vs. sustituto es exactamente lo que miden estas métricas y no
requiere inventar otra fuente de datos.

Gramática neutra: demostración, sin umbrales de riesgo. Se marca
`PENDING_VALIDATION` con un aviso de sección (no con `render_validation_marker`:
el HRV Lab ya lleva el marcador VALIDATED del dominio temporal y una prueba
fija que sea el único): los métodos son citables y se validan contra ground
truth sintético, pero la interpretación clínica de la complejidad no tiene
firma del experto.
"""

import numpy as np
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from app.utils.design_system import PALETTE, render_metric_card
from src.signals.ecg.hrv_nonlinear import (
    DFA_CITATION, POINCARE_CITATION, SAMPEN_CITATION, HrvNonlinearResult, analyze_hrv_nonlinear,
)

SURROGATE_SEED = 0
_VALIDATION_DETAIL = (
    "PENDING_VALIDATION: métodos citados y validados contra ground truth sintético (ruido blanco, 1/f, "
    "SD1 = RMSSD/√2); la interpretación clínica de la complejidad autonómica no tiene firma del experto."
)


def build_poincare_figure(rr_ms: np.ndarray, surrogate_ms: np.ndarray) -> go.Figure:
    """Nubes (RR_n, RR_n+1) de la serie y de su sustituto barajado, mismos ejes, con la diagonal de identidad."""
    lo, hi = float(min(rr_ms.min(), surrogate_ms.min())), float(max(rr_ms.max(), surrogate_ms.max()))
    pad = 0.05 * (hi - lo) + 1.0
    fig = make_subplots(rows=1, cols=2, subplot_titles=("Serie", "Sustituto barajado"), shared_yaxes=True)
    for col, series, color in ((1, rr_ms, PALETTE.ACCENT_ON_DARK), (2, surrogate_ms, PALETTE.NEUTRAL)):
        fig.add_trace(go.Scatter(
            x=series[:-1], y=series[1:], mode="markers", name="RR_n+1 vs RR_n",
            marker=dict(size=5, color=color, opacity=0.7), showlegend=False,
        ), row=1, col=col)
        fig.add_trace(go.Scatter(
            x=[lo - pad, hi + pad], y=[lo - pad, hi + pad], mode="lines", showlegend=False,
            line=dict(color=PALETTE.TEXT, width=1, dash="dot"),
        ), row=1, col=col)
        fig.update_xaxes(title_text="RR_n (ms)", range=[lo - pad, hi + pad], row=1, col=col)
    fig.update_yaxes(title_text="RR_n+1 (ms)", range=[lo - pad, hi + pad], row=1, col=1)
    fig.update_layout(
        title_text="Gráfico de Poincaré", height=420, paper_bgcolor=PALETTE.BACKGROUND, plot_bgcolor=PALETTE.BACKGROUND, font=dict(color=PALETTE.TEXT),
    )
    return fig


def _render_metrics(result: HrvNonlinearResult) -> None:
    s, a, p = result.sampen, result.alpha1, result.poincare
    render_metric_card(
        "SampEn", f"{s.value:.2f}" if s.available else None, citation=SAMPEN_CITATION, unavailable_reason=s.reason,
    )
    render_metric_card(
        "DFA α1", f"{a.value:.2f}" if a.available else None, citation=DFA_CITATION, unavailable_reason=a.reason,
    )
    render_metric_card(
        "SD1 (corto plazo)", f"{p.sd1_ms:.1f} ms" if p.available else None, citation=POINCARE_CITATION,
        unavailable_reason=p.reason,
    )
    render_metric_card(
        "SD2 (largo plazo)", f"{p.sd2_ms:.1f} ms" if p.available else None, citation=POINCARE_CITATION,
        unavailable_reason=p.reason,
    )
    if result.structure_note:
        st.markdown(f"*{result.structure_note}*")


def render_nonlinear_panel(rr_ms: np.ndarray) -> None:
    rr_ms = np.asarray(rr_ms, dtype=float)
    surrogate = np.random.default_rng(SURROGATE_SEED).permutation(rr_ms)
    real, noise = analyze_hrv_nonlinear(rr_ms), analyze_hrv_nonlinear(surrogate)

    st.markdown("### 〰️ HRV no lineal (complejidad)")
    st.markdown(
        "La RSA y el resto de la variabilidad dejan **estructura** en el orden de los latidos. Estas métricas la "
        "miden y el sustituto barajado (los mismos RR en orden al azar) muestra cómo se ve una serie sin ella: "
        "SampEn alta y DFA α1 cerca de 0.5 (el ruido blanco da ~0.58 en estas escalas cortas)."
    )
    st.warning(f"**Alcance:** {real.scope_note}")
    st.info(_VALIDATION_DETAIL)

    left, right = st.columns(2)
    with left:
        st.markdown("**Serie RR**")
        _render_metrics(real)
    with right:
        st.markdown("**Sustituto barajado (ruido)**")
        _render_metrics(noise)

    if real.poincare.available:
        st.plotly_chart(build_poincare_figure(rr_ms, surrogate), width="stretch")
    st.markdown(f"*DFA {real.alpha2_note}.*")
