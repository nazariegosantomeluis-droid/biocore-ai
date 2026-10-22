"""Cuerpo 3D del gemelo coloreado por el UPS (Pieza 2, 2026-10-22).

Segundo renderizador de la MISMA fuente que el cuerpo SVG: el color de cada
órgano sale de `organ_visual_state(state)` (`ups_body_visual.py`), y
`render_ups_body(state, with_3d=True)` dibuja ambos con el mismo `state`. No
pueden contradecirse (Art. IV).

Solo corazón, pulmones (con tráquea) y cerebro tienen estado; vasos, médula
y abdomen no tienen dominio en el UPS y van en color de tejido atenuado. Dos
neutros distintos: gris = órgano modelado sin dato; tejido atenuado =
anatomía sin dominio. La geometría es de un sujeto de referencia y no se
anima: el latido y la respiración están en el cuerpo SVG.
"""

from __future__ import annotations

from typing import Optional

import streamlit as st

from domain.physiology.state import UnifiedPhysiologicalState

from .ups_body_visual import NEUTRAL_COLOR, SEVERITY_COLOR, STABLE_COLOR, organ_visual_state

UPS_BODY_3D_NOTE = (
    "Color según el estado del UPS; geometría de un sujeto de referencia, sin animación "
    "(el latido y la respiración se ven en el cuerpo SVG)."
)
ORGAN_NAMES = {"heart": "Corazón", "lungs": "Pulmones", "brain": "Cerebro"}


def legend_entries():
    """Las 5 entradas de la leyenda: (color, texto). La última es el tejido
    atenuado tal como se dibuja (arteria de muestra)."""
    from domain.physiology.state import EventSeverity
    from visualization import anatomy3d as A3

    unmodeled = A3._blend(A3.TISSUE_COLOR["arteries"], A3.UNMODELED_TOWARD, A3.UNMODELED_BLEND)
    return [
        (STABLE_COLOR, "Sin evento"),
        (SEVERITY_COLOR[EventSeverity.WARNING], "Aviso"),
        (SEVERITY_COLOR[EventSeverity.CRITICAL], "Crítico"),
        (NEUTRAL_COLOR, "Sin dato (órgano modelado, espera un dato)"),
        (unmodeled, "Tejido atenuado: anatomía sin dominio en el UPS"),
    ]


def render_ups_body_3d(state: Optional[UnifiedPhysiologicalState], key: str) -> None:
    from visualization import anatomy3d as A3

    if not A3.assets_available():
        st.caption("Cuerpo 3D no disponible: faltan las mallas de data/anatomy3d/.")
        return
    visuals = organ_visual_state(state)
    colors = {organ: v.color for organ, v in visuals.items()}
    notes = {organ: f"{ORGAN_NAMES[organ]}: {v.label} (según el UPS)" for organ, v in visuals.items()}
    fig = A3.body_figure(systems=A3.DEFAULT_SYSTEMS, organ_colors=colors, organ_notes=notes, height=560)
    st.plotly_chart(fig, width="stretch", key=f"ups_body_3d_{key}",
                    config={"displaylogo": False, "scrollZoom": True})
    legend = "".join(
        f"<span style='margin-right:14px;white-space:nowrap;'><span style='display:inline-block;width:11px;"
        f"height:11px;border-radius:2px;background:{color};margin-right:5px;vertical-align:middle;'></span>"
        f"{text}</span>"
        for color, text in legend_entries()
    )
    st.markdown(f"<div class='biocore-ups-3d-legend' style='font-size:0.85rem;'>{legend}</div>",
                unsafe_allow_html=True)
    st.caption(UPS_BODY_3D_NOTE)
