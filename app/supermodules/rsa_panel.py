"""
Acoplamiento cardiopulmonar (RSA) en el HRV Lab -- 2026-10-19,
cardiovascular profundo, sub-arco RSA.

`simulate_rsa_rr()` es la cadena completa dentro de UN generador:
respiración -> FC modulada -> ECG (`DynamicECGGenerator`) -> picos R por
TKEO (`ECGAnalyzer.detect_r_peaks_tkeo`, el detector consolidado) -> RR.
Es la fuente "Simulación" del HRV Lab: sus RR salen de verdad de un ECG,
a diferencia del antiguo "Demo (ECG-derived)", que era `mean_rr + ruido
gaussiano` sin ningún ECG detrás.

Gramática neutra: demostración del fenómeno, sin umbrales clínicos de tono
vagal firmados. No lee el UPS ni otro laboratorio.
"""

from typing import Optional, Tuple

import numpy as np
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from app.utils.design_system import PALETTE, render_metric_card
from src.signals.ecg.rsa import RSA_CITATION, RSAResult, RsaParams, RsaSignals, generate_rsa_signals

RSA_SOURCE_LABEL = "Simulación: acoplamiento cardiopulmonar (ECG con RSA → picos R por TKEO)"
ECG_FS_HZ = 250.0


def simulate_rsa_rr(params: RsaParams, duration_s: float, ECGAnalyzerCls) -> Tuple[RsaSignals, np.ndarray]:
    """`(señales, instantes de los picos R en s)` -- los picos los detecta
    el TKEO sobre el ECG generado, no se leen del generador."""
    signals = generate_rsa_signals(params, duration_s, fs=ECG_FS_HZ)
    peaks = ECGAnalyzerCls(fs=ECG_FS_HZ).detect_r_peaks_tkeo(signals.ecg)
    return signals, np.asarray(peaks, dtype=float) / ECG_FS_HZ


def build_rsa_figure(result: RSAResult, signals: RsaSignals) -> go.Figure:
    """FC latido a latido medida (60/RR) sobre el volumen pulmonar: el ritmo
    acelera en inspiración y frena en espiración. Vista inicial de 30 s."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(
        x=signals.time, y=signals.respiration, name="Volumen pulmonar (normalizado)",
        line=dict(color=PALETTE.NEUTRAL, width=1.5),
    ), secondary_y=True)
    fig.add_trace(go.Scatter(
        x=result.beat_times_s, y=result.beat_hr_bpm, name="FC latido a latido (60/RR)", mode="lines+markers",
        line=dict(color=PALETTE.ACCENT_ON_DARK, width=2), marker=dict(size=5, color=PALETTE.ACCENT_ON_DARK),
    ), secondary_y=False)
    fig.update_xaxes(title_text="Tiempo (s)", range=[0, min(30.0, float(signals.time[-1]))])
    fig.update_yaxes(title_text="FC (lpm)", secondary_y=False)
    fig.update_yaxes(title_text="Volumen (u.a.)", secondary_y=True, showgrid=False)
    fig.update_layout(
        height=340, legend=dict(orientation="h"),
        paper_bgcolor=PALETTE.BACKGROUND, plot_bgcolor=PALETTE.BACKGROUND, font=dict(color=PALETTE.TEXT),
    )
    return fig


def render_rsa_panel(result: RSAResult, signals: Optional[RsaSignals], injected: Optional[RsaParams]) -> None:
    st.markdown("### 🫁❤️ Acoplamiento cardiopulmonar (RSA)")
    st.markdown(
        "Arritmia sinusal respiratoria: al inspirar se retira el freno vagal y la FC sube; al espirar "
        "vuelve el freno y baja. En la serie RR aparece como potencia concentrada en la frecuencia "
        "respiratoria, dentro de la banda HF."
    )
    st.warning(f"**Alcance:** {result.scope_note}")

    if not result.available:
        st.info(f"RSA no disponible: {result.reason}")
        render_metric_card("Amplitud de la RSA", None, unavailable_reason=result.reason)
        return

    if signals is not None:
        st.plotly_chart(build_rsa_figure(result, signals), width="stretch")

    injected_txt = f" · inyectada {injected.rsa_amplitude_bpm:.1f} lpm" if injected is not None else ""
    render_metric_card(
        "Amplitud de la RSA", f"{result.rsa_amplitude_bpm:.2f} lpm",
        citation=f"oscilación de la FC latido a latido en la frecuencia respiratoria{injected_txt}",
    )
    render_metric_card("Potencia HF", f"{result.hf_power_ms2:.0f} ms²", citation=RSA_CITATION)
    render_metric_card(
        "Frecuencia respiratoria", f"{result.respiratory_freq_hz * 60:.1f} rpm",
        citation=f"{result.hf_peak_fraction:.0%} de la variabilidad RR cae en esta frecuencia",
    )
    render_metric_card(
        "Fase FC ↔ respiración", f"{result.phase_deg:+.0f}°",
        citation="0° = la FC sube y baja en fase con el volumen pulmonar",
    )
    st.caption(
        "La amplitud medida es la de la FC promediada latido a latido (lo que contiene una serie RR): "
        "queda algo por debajo de la inyectada, más cuanto más rápida es la respiración frente a la FC."
    )
