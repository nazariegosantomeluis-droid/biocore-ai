"""Vectocardiograma 3D (2026-10-21): figura Plotly de las asas P, QRS y T.

Recibe el latido mediano en la convención de Frank (`src/signals/ecg/vcg.py`)
y lo dibuja orientado como el cuerpo (de frente: la izquierda del paciente
a tu derecha), con:
- las tres asas en colores distintos (paleta categórica validada);
- sus "sombras" en los planos frontal, horizontal y sagital, como en los
  visores clínicos de VCG;
- los vectores medios de QRS y de T como flechas desde el origen (entre
  ellos se mide el ángulo QRS-T espacial);
- opcionalmente, un segundo latido de comparación (p. ej., el VCG real de
  Frank frente al reconstruido con Kors).
"""

from __future__ import annotations

from typing import Dict, Optional

import numpy as np

from src.signals.ecg.vcg import LoopMeasures, MedianBeat, segment_masks, to_anatomical

SEGMENT_COLORS = {"P": "#199e70", "QRS": "#3987e5", "T": "#d95926"}
SEGMENT_LABELS = {"P": "Asa P", "QRS": "Asa QRS", "T": "Asa T"}
INK, INK_2, INK_3, LINE = "#e0e7ff", "#b6c2e2", "#94a3c8", "#5d6b92"


def _axis_arrows(r: float):
    import plotly.graph_objects as go

    traces = []
    for vec, label in (((-r, 0, 0), "Izquierda"), ((0, r, 0), "Anterior"), ((0, 0, r), "Superior")):
        traces.append(go.Scatter3d(x=[0, vec[0]], y=[0, vec[1]], z=[0, vec[2]], mode="lines",
                                   line=dict(color=LINE, width=3), hoverinfo="skip", showlegend=False))
        traces.append(go.Scatter3d(x=[vec[0] * 1.12], y=[vec[1] * 1.12], z=[vec[2] * 1.12], mode="text",
                                   text=[label], textfont=dict(color=INK_3, size=12), hoverinfo="skip",
                                   showlegend=False))
    return traces


def vcg_figure(beat: MedianBeat, measures: LoopMeasures, *, compare: Optional[MedianBeat] = None,
               compare_label: str = "Comparación", height: int = 560, shadows: bool = True):
    import plotly.graph_objects as go

    xyz = to_anatomical(beat.xyz - np.median(beat.xyz[(beat.t_ms > -150) & (beat.t_ms < -90)], axis=0))
    seg = segment_masks(beat, measures)
    r = float(np.max(np.abs(xyz[seg["QRS"] | seg["T"]]))) or 1.0
    lim = r * 1.25
    fig = go.Figure()
    if shadows:
        planes = (("frontal", 1, -lim), ("horizontal", 2, -lim), ("sagital", 0, lim))
        for _, axis, value in planes:
            for name in ("QRS", "T"):
                p = xyz[seg[name]].copy()
                p[:, axis] = value
                fig.add_trace(go.Scatter3d(x=p[:, 0], y=p[:, 1], z=p[:, 2], mode="lines",
                                           line=dict(color=SEGMENT_COLORS[name], width=2), opacity=0.35,
                                           hoverinfo="skip", showlegend=False))
    for trace in _axis_arrows(lim * 0.8):
        fig.add_trace(trace)
    if compare is not None:
        cx = to_anatomical(compare.xyz - np.median(compare.xyz[(compare.t_ms > -150) & (compare.t_ms < -90)], axis=0))
        m = (compare.t_ms >= measures.qrs_on_ms - 220) & (compare.t_ms <= measures.t_off_ms)
        fig.add_trace(go.Scatter3d(x=cx[m, 0], y=cx[m, 1], z=cx[m, 2], mode="lines",
                                   line=dict(color=INK_2, width=3, dash="dot"), name=compare_label,
                                   hovertemplate=f"{compare_label}<extra></extra>"))
    for name in ("P", "QRS", "T"):
        p = xyz[seg[name]]
        t = beat.t_ms[seg[name]]
        fig.add_trace(go.Scatter3d(
            x=p[:, 0], y=p[:, 1], z=p[:, 2], mode="lines", name=SEGMENT_LABELS[name],
            line=dict(color=SEGMENT_COLORS[name], width=6 if name == "QRS" else 5),
            customdata=t, hovertemplate=f"{SEGMENT_LABELS[name]}<br>%{{customdata:.0f}} ms<extra></extra>"))
    for vec, name in ((measures.qrs_mean_vector, "QRS"), (measures.t_mean_vector, "T")):
        v = to_anatomical(np.array([vec]))[0]
        n = np.linalg.norm(v) or 1.0
        tip = v / n * r * 0.9
        fig.add_trace(go.Scatter3d(x=[0, tip[0]], y=[0, tip[1]], z=[0, tip[2]], mode="lines+markers",
                                   line=dict(color=SEGMENT_COLORS[name], width=9),
                                   marker=dict(size=[0, 6], color=SEGMENT_COLORS[name]),
                                   name=f"Vector medio {name}",
                                   hovertemplate=f"Vector medio {name}: {np.linalg.norm(vec):.2f} mV<extra></extra>"))
    axis = dict(visible=False, range=[-lim, lim], showbackground=False)
    fig.update_layout(
        height=height, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=0.0, x=0.0, font=dict(color=INK_2)),
        scene=dict(xaxis=axis, yaxis=axis, zaxis=axis, aspectmode="cube", bgcolor="rgba(0,0,0,0)",
                   camera=dict(eye=dict(x=-0.9, y=1.5, z=0.55), up=dict(x=0, y=0, z=1))),
        hoverlabel=dict(bgcolor="#111d36", bordercolor=LINE, font=dict(color=INK)),
        uirevision="vcg3d",
    )
    return fig


def measures_table(m: LoopMeasures) -> Dict[str, str]:
    return {
        "Duración del QRS": f"{m.qrs_duration_ms:.0f} ms",
        "Ángulo QRS-T espacial": f"{m.qrs_t_angle_deg:.0f}°",
        "Magnitud máxima del QRS": f"{m.qrs_peak_mv:.2f} mV",
        "Vector QRS medio": f"acimut {m.qrs_azimuth_deg:.0f}°, elevación {m.qrs_elevation_deg:.0f}°",
    }
