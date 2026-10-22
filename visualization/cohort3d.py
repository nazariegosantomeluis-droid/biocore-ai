"""Figura 3D del mapa de pacientes (PCA + grupos + atípicos), 2026-10-21."""

from __future__ import annotations

from typing import Optional, Sequence

import numpy as np

# Paleta categórica validada (dataviz, modo oscuro) -- la misma de la app.
SERIES = ("#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767")
INK, INK_2, LINE = "#e0e7ff", "#b6c2e2", "#5d6b92"


def cohort_figure(cm, *, color_by: str = "cluster", labels: Optional[Sequence[str]] = None,
                  highlight: Optional[int] = None, height: int = 560):
    """`color_by`: "cluster" (grupos de K-means), "target" (usa `labels`) u
    "outlier". Los atípicos siempre se marcan con un rombo."""
    import plotly.graph_objects as go

    xyz = np.asarray(cm.coords)
    if color_by == "target" and labels is not None:
        cats = [str(v) for v in labels]
        names = sorted(set(cats))
        groups = {n: np.array([c == n for c in cats]) for n in names}
    elif color_by == "outlier":
        groups = {"Típico": ~cm.outlier, "Atípico (Isolation Forest)": cm.outlier}
    else:
        groups = {f"Grupo {g + 1}": cm.clusters == g for g in sorted(set(cm.clusters.tolist()))}
    fig = go.Figure()
    for i, (name, mask) in enumerate(groups.items()):
        if not mask.any():
            continue
        idx = np.nonzero(mask)[0]
        sym = ["diamond" if cm.outlier[j] else "circle" for j in idx]
        fig.add_trace(go.Scatter3d(
            x=xyz[idx, 0], y=xyz[idx, 1], z=xyz[idx, 2], mode="markers", name=name,
            marker=dict(size=4.5, color=SERIES[i % len(SERIES)], symbol=sym, opacity=0.9,
                        line=dict(color="#0b1426", width=0.5)),
            text=[cm.row_ids[j] for j in idx],
            hovertemplate="<b>%{text}</b><br>" + name + "<extra></extra>"))
    if highlight is not None and 0 <= highlight < len(xyz):
        p = xyz[highlight]
        fig.add_trace(go.Scatter3d(x=[p[0]], y=[p[1]], z=[p[2]], mode="markers+text",
                                   marker=dict(size=11, color="rgba(0,0,0,0)", line=dict(color=INK, width=3)),
                                   text=[cm.row_ids[highlight]], textposition="top center",
                                   textfont=dict(color=INK, size=13), name="Paciente elegido",
                                   hoverinfo="skip"))
    ev = cm.explained

    def ax(i: int) -> dict:
        return dict(title=dict(text=f"CP{i + 1} ({ev[i]:.0%})", font=dict(color=INK_2, size=12)),
                    showbackground=False, gridcolor="rgba(148,163,209,.18)", zerolinecolor=LINE,
                    tickfont=dict(color=INK_2, size=10), showspikes=False)

    fig.update_layout(
        height=height, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=0.0, x=0.0, font=dict(color=INK_2)),
        scene=dict(xaxis=ax(0), yaxis=ax(1), zaxis=ax(2), aspectmode="cube", bgcolor="rgba(0,0,0,0)",
                   camera=dict(eye=dict(x=1.5, y=1.4, z=0.9))),
        hoverlabel=dict(bgcolor="#111d36", bordercolor=LINE, font=dict(color=INK)),
        uirevision="cohort3d",
    )
    return fig


def importance_figure(importances, *, height: int = 340):
    """Barras horizontales ordenadas de mayor a menor (la primera arriba):
    cuánto AUC se pierde al barajar cada variable."""
    import plotly.graph_objects as go

    names = list(importances)
    vals = [float(importances[n]) for n in names]
    fig = go.Figure(go.Bar(
        x=vals, y=names, orientation="h", text=[f"{v:.3f}" for v in vals], textposition="outside",
        cliponaxis=False, hovertemplate="%{y}: el AUC baja %{x:.4f}<extra></extra>",
    ))
    fig.update_layout(
        height=height, margin=dict(l=8, r=48, t=8, b=36), showlegend=False,
        xaxis=dict(title="AUC que se pierde al barajar la variable", rangemode="tozero"),
        yaxis=dict(autorange="reversed", automargin=True),
    )
    return fig
