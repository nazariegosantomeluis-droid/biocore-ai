"""Papel ECG: el ÚNICO componente que dibuja un ECG en la app (pulido profesional, 2026-11-16).

Lo usan el Monitoreo y 12 Derivaciones del Laboratorio de ECG. Estándar de registro [MCM]: a 25 mm/s, 1 mm = 0.04 s y
5 mm = 0.2 s; a 10 mm/mV, 1 mm = 0.1 mV. Todo va en UN eje con proporción fija (`scaleratio` = 10/25): 0.04 s en
horizontal ocupan los mismos píxeles que 0.1 mV en vertical, a cualquier ancho. Cada tira empieza con el pulso de
calibración de 1 mV (10 mm) y lleva rotuladas la velocidad, la ganancia, el muestreo y el filtro.

12 derivaciones: formato tradicional de 4 columnas (I, II, III · aVR, aVL, aVF · V1–V3 · V4–V6), cada columna un
tramo consecutivo de 2.5 s, más una tira de ritmo de 10 s de II debajo [K2007].
"""

from __future__ import annotations

from typing import Dict, Optional, Sequence

import numpy as np

from app.utils.design_system import PALETTE

MM_PER_S = 25.0                      # velocidad del papel [MCM]
MM_PER_MV = 10.0                     # ganancia [MCM]
MINOR_S, MAJOR_S = 1 / MM_PER_S, 5 / MM_PER_S        # 0.04 s y 0.2 s
MINOR_MV, MAJOR_MV = 1 / MM_PER_MV, 5 / MM_PER_MV    # 0.1 mV y 0.5 mV
CAL_MV = 1.0                         # pulso de calibración: 1 mV = 10 mm
CAL_WIDTH_S = MAJOR_S                # 5 mm de ancho
LEAD_IN_S = 0.4                      # margen antes de t = 0 donde va el pulso
SCALE_LABEL = "25 mm/s · 10 mm/mV"
# Filtro (Parte A): con un corte superior < 150 Hz el filtro es de monitoreo, no diagnóstico [K2007].
MONITOR_FILTER_LABEL = "filtro de monitoreo 0.5–40 Hz, no diagnóstico [K2007]"
NO_FILTER_LABEL = "sin filtro de BIOCORE (la señal tal como viene)"

TWELVE_LEAD_COLUMNS = (("I", "II", "III"), ("aVR", "aVL", "aVF"), ("V1", "V2", "V3"), ("V4", "V5", "V6"))
RHYTHM_LEAD = "II"
STRIP_S = 10.0                       # tira de ritmo de 10 s [K2007]
ROW_MV = 3.0                         # distancia entre filas del formato 3×4 (30 mm)

# Ancho típico del contenido (Parte B: máximo ~1200 px). La altura se calcula para ese ancho; a otro ancho Plotly
# conserva la proporción alargando el papel, nunca deformando la escala.
_DESIGN_WIDTH_PX = 1150

VARIANTS = {
    "papel": dict(paper=PALETTE.ECG_PAPER, major=PALETTE.ECG_GRID_MAJOR, minor=PALETTE.ECG_GRID_MINOR,
                  trace=PALETTE.ECG_TRACE, label=PALETTE.ECG_LABEL),
    "oscuro": dict(paper=PALETTE.ECG_PAPER_DARK, major=PALETTE.ECG_GRID_MAJOR_DARK, minor=PALETTE.ECG_GRID_MINOR_DARK,
                   trace=PALETTE.ECG_TRACE_DARK, label=PALETTE.ECG_LABEL_DARK),
}
DEFAULT_VARIANT = "papel"            # la que cumple AA con más margen (ver PALETTE)


def scale_caption(fs: float, filter_label: str, gain_note: Optional[str] = None) -> str:
    """Rótulo de cada tira: velocidad, ganancia, muestreo y filtro (con lo que no se sabe dicho)."""
    gain = SCALE_LABEL if gain_note is None else f"25 mm/s · 10 mm por unidad ({gain_note})"
    return f"{gain} · {fs:g} muestras/s · {filter_label}"


def _calibration(x0: float, baseline: float):
    """Pulso de 1 mV × 0.2 s que empieza en x0 (escalón de calibración)."""
    x = [x0, x0 + 0.08, x0 + 0.08, x0 + 0.08 + CAL_WIDTH_S, x0 + 0.08 + CAL_WIDTH_S, x0 + 0.08 + CAL_WIDTH_S + 0.08]
    y = [baseline, baseline, baseline + CAL_MV, baseline + CAL_MV, baseline, baseline]
    return x, y


def _paper(fig, x_range, y_range, caption: str, colors: dict) -> None:
    """Cuadrícula de 1 mm y 5 mm, proporción fija y rótulo de escala."""
    # `constrain="domain"`: para mantener la proporción Plotly achica el área dibujada, nunca estira el rango. Con
    # "range" guardaba el rango estirado tras el primer dibujo y lo volvía a estirar al cambiar el ancho (medido en el
    # navegador: la tira de 10 s quedaba en 17.9 s de papel).
    grid = dict(showgrid=True, gridwidth=1, zeroline=False, showticklabels=False, ticks="", tick0=0,
                constrain="domain")
    fig.update_xaxes(range=list(x_range), dtick=MAJOR_S, gridcolor=colors["major"],
                     minor=dict(dtick=MINOR_S, showgrid=True, gridcolor=colors["minor"], gridwidth=0.5), **grid)
    fig.update_yaxes(range=list(y_range), dtick=MAJOR_MV, gridcolor=colors["major"],
                     minor=dict(dtick=MINOR_MV, showgrid=True, gridcolor=colors["minor"], gridwidth=0.5),
                     scaleanchor="x", scaleratio=MM_PER_MV / MM_PER_S, constraintoward="top", **grid)
    width_mm = (x_range[1] - x_range[0]) * MM_PER_S
    height_mm = (y_range[1] - y_range[0]) * MM_PER_MV
    top, bottom = 34, 6
    fig.update_layout(
        height=int(round(height_mm * _DESIGN_WIDTH_PX / width_mm)) + top + bottom,
        margin=dict(l=4, r=4, t=top, b=bottom),
        plot_bgcolor=colors["paper"], paper_bgcolor=colors["paper"], showlegend=False,
        title=dict(text=caption, font=dict(color=colors["label"], size=12), x=0.01, y=0.99, yanchor="top"),
        font=dict(color=colors["label"]), dragmode="pan",
    )


def _trace(fig, x, y, name: str, colors: dict) -> None:
    import plotly.graph_objects as go

    fig.add_trace(go.Scatter(x=x, y=y, mode="lines", name=name, hoverinfo="skip",
                             line=dict(color=colors["trace"], width=1.2)))


def _label(fig, x: float, y: float, text: str, colors: dict) -> None:
    fig.add_annotation(x=x, y=y, text=f"<b>{text}</b>", showarrow=False, xanchor="left", yanchor="bottom",
                       font=dict(color=colors["label"], size=12))


def strip_figure(signal: np.ndarray, fs: float, *, lead: str = "ECG", start_s: float = 0.0,
                 duration_s: float = STRIP_S, filter_label: str, gain_note: Optional[str] = None,
                 variant: str = DEFAULT_VARIANT):
    """Una tira de `duration_s` desde `start_s` (s), con el pulso de calibración al inicio. Amplitud en mV."""
    import plotly.graph_objects as go

    colors = VARIANTS[variant]
    signal = np.asarray(signal, dtype=float)
    i0 = max(0, int(round(start_s * fs)))
    seg = signal[i0:i0 + int(round(duration_s * fs))]
    t = np.arange(seg.size) / fs
    seg = seg - (np.median(seg) if seg.size else 0.0)   # línea de base en 0 mV (desplazamiento vertical, no filtra)
    lo = min(-1.0, np.floor((seg.min() if seg.size else 0) / MAJOR_MV) * MAJOR_MV - MAJOR_MV)
    hi = max(CAL_MV + MAJOR_MV, np.ceil((seg.max() if seg.size else 0) / MAJOR_MV) * MAJOR_MV + MAJOR_MV)
    fig = go.Figure()
    _trace(fig, *_calibration(-LEAD_IN_S + 0.04, 0.0), "Calibración 1 mV", colors)
    _trace(fig, t, seg, lead, colors)
    _label(fig, 0.05, CAL_MV, lead, colors)
    _paper(fig, (-LEAD_IN_S, max(duration_s, t[-1] if t.size else duration_s)), (lo, hi),
           scale_caption(fs, filter_label, gain_note), colors)
    return fig


def twelve_lead_figure(leads: Dict[str, np.ndarray], fs: float, *, filter_label: str,
                       variant: str = DEFAULT_VARIANT, missing: Sequence[str] = ()):
    """Formato 3×4 + tira de ritmo de 10 s de II [K2007], todo en un solo papel. `missing`: derivaciones que no
    vienen en el registro (se rotulan «no viene», no se dibujan planas)."""
    import plotly.graph_objects as go

    colors = VARIANTS[variant]
    n = int(round(STRIP_S * fs))
    col_s = STRIP_S / len(TWELVE_LEAD_COLUMNS)
    t = np.arange(n) / fs
    fig = go.Figure()
    for row in range(4):
        baseline = (3 - row) * ROW_MV
        _trace(fig, *_calibration(-LEAD_IN_S + 0.04, baseline), "Calibración 1 mV", colors)
    for c, column in enumerate(TWELVE_LEAD_COLUMNS):
        a, b = int(round(c * col_s * fs)), int(round((c + 1) * col_s * fs))
        for r, name in enumerate(column):
            baseline = (3 - r) * ROW_MV
            _label(fig, c * col_s + 0.05, baseline + 1.0, name if name not in missing else f"{name}: no viene", colors)
            if name in missing or name not in leads:
                continue
            seg = np.asarray(leads[name], dtype=float)[:n]
            seg = seg - np.median(seg)
            _trace(fig, t[a:b][:seg[a:b].size], seg[a:b] + baseline, name, colors)
    rhythm = np.asarray(leads.get(RHYTHM_LEAD, np.zeros(0)), dtype=float)[:n]
    _label(fig, 0.05, 1.0, f"{RHYTHM_LEAD} (tira de ritmo, 10 s)", colors)
    if rhythm.size:
        _trace(fig, t[:rhythm.size], rhythm - np.median(rhythm), f"{RHYTHM_LEAD} ritmo", colors)
    for c in range(1, len(TWELVE_LEAD_COLUMNS)):          # marca de cambio de derivación entre columnas
        for r in range(3):
            baseline = (3 - r) * ROW_MV
            fig.add_shape(type="line", x0=c * col_s, x1=c * col_s, y0=baseline - 0.3, y1=baseline + 0.3,
                          line=dict(color=colors["trace"], width=1.2))
    _paper(fig, (-LEAD_IN_S, STRIP_S), (-1.5, 3 * ROW_MV + 1.8), scale_caption(fs, filter_label), colors)
    return fig


def render(fig, key: str) -> None:
    """Dibuja el papel a todo el ancho del contenedor (Parte B: las tiras pueden usar el ancho completo)."""
    import streamlit as st

    st.plotly_chart(fig, use_container_width=True, key=key, config={"displaylogo": False, "scrollZoom": False})
