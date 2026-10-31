"""
Cardiovascular profundo, sub-arco A (2026-10-19): el barorreflejo (brazo
vascular) hecho visible -- la traza del lazo cerrado (Rd, PAM, gasto), la
saturación del efector y la convergencia, para los 3 escenarios con
validación experta completa del motor hemodinámico.

CAPA DE LECTURA, CERO FÍSICA: llama a `run_closed_loop()` y a
`run_pathological_baroreflex()` tal cual y dibuja lo que ya devuelven. Los
límites de Rd y la PAM objetivo se leen del motor (override patológico del
escenario / resultado del reflejo), no se copian aquí.

Por qué no `closed_loop_comparison.py`: vuelve a correr el escenario
completo escribiendo un paciente efímero en la BD, y su `pending_validation`
es la bandera del retorno venoso (ya False), no la de la compliancia C
(`PHYSIOLOGICAL_PARAMETERS_PENDING_VALIDATION`, aún True) -- la vista
mentiría por omisión sobre el PENDING que sí aplica.

Dos rótulos de honestidad: (1) los ticks son ITERACIONES de convergencia
hacia el equilibrio, no segundos -- el motor no tiene dinámica temporal
latido a latido; (2) la compliancia C sigue PENDIENTE: la PA sistólica/
diastólica la hereda. La PAM, la Rd y el gasto de la traza no dependen de C
(verificado: C x0.5 / x2 deja PAM y Rd idénticas, ver tests).

El brazo cardíaco (FC <- PAM) NO está modelado: la FC es una entrada del
lazo (el slider), el reflejo no la modifica. Es el sub-arco B, que cambia
la física del motor y requiere firma del experto.
"""

from typing import Dict

import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from app.utils.design_system import PALETTE, render_metric_card, render_validation_marker
from src.clinical import sepsis_trajectory
from domain.physiology.hemodynamics import (
    BAROREFLEX_MAX_RD,
    BAROREFLEX_MECHANISM_CITATION,
    BAROREFLEX_MIN_RD,
    HEMODYNAMIC_MODEL_ENABLED_SCENARIOS,
    PATHOLOGICAL_TONE_OVERRIDES,
    PHYSIOLOGICAL_PARAMETERS_PENDING_VALIDATION,
    STROKE_VOLUME_REFERENCE_ML,
    ClosedLoopResult,
    run_closed_loop,
    run_pathological_baroreflex,
)

ITERATION_AXIS_LABEL = "Iteración hacia el equilibrio (no segundos)"

ITERATION_NOTE = (
    "**Eje = iteración (no segundos).** Cada punto es un paso del lazo hacia su equilibrio, no un "
    "instante de tiempo: el modelo calcula el estado estacionario que el reflejo alcanza, no la "
    "respuesta latido a latido (no tiene latencia ni constantes de tiempo)."
)

COMPLIANCE_PENDING_NOTE = (
    "**Compliancia C pendiente de validación** (`PHYSIOLOGICAL_PARAMETERS_PENDING_VALIDATION`): la PA "
    "sistólica/diastólica mostrada depende de la compliancia arterial C del módulo 1, aún sin firma del "
    "experto, y hereda ese PENDING. La PAM, la Rd y el gasto de la traza no dependen de C (verificado: "
    "con C a la mitad o al doble, PAM y Rd idénticas)."
)

CARDIAC_ARM_NOTE = (
    "Solo el **brazo vascular** está modelado: la FC es una entrada que tú fijas, el reflejo no la "
    "cambia. El brazo cardíaco (taquicardia/bradicardia refleja) cambiaría la física del motor y "
    "requiere firma del experto (sub-arco B)."
)

VASCULAR_ARM_VALIDATION_DETAIL = (
    "Brazo vascular del barorreflejo: mecanismo citado (Guyton & Hall, Cap. 18); ganancia k, límites "
    "de Rd y PAM objetivo validados por el experto (Rondas 1-2, 2026-07-30/31)."
)

# Los tres puntos fijos validados del lazo (`tests/test_hemodynamics_closed_loop_stability.py`,
# misma traza de demostración que `closed_loop.py::__main__`) -- solo el valor inicial del slider.
# La FC de sepsis es el punto de shock de la trayectoria canónica (`src/clinical/sepsis_trajectory.py`), no un número propio.
_FIXED_POINT_HR_BPM: Dict[str, float] = {
    "healthy": 72.0, "hypertension": 85.0, "sepsis": sepsis_trajectory.horizon_vitals("24h")["hr"],
}
# Rango barrido: los 3 escenarios convergen sin oscilar en 40-220 lpm (2026-10-19).
_HR_MIN_BPM, _HR_MAX_BPM = 40, 220


def pa_model_label() -> str:
    """Rótulo de la PA calculada por el lazo cerrado donde se muestre (Digital
    Twin OS, Academia) -- lee la bandera de la compliancia: deja de decir
    "pendiente" solo cuando el experto la baje."""
    if PHYSIOLOGICAL_PARAMETERS_PENDING_VALIDATION:
        return "lazo cerrado; barorreflejo validado, S/D con compliancia C pendiente de validación"
    return "lazo cerrado, validado"


def rd_limits(scenario: str) -> tuple:
    """(min_rd, max_rd) efectivos del escenario -- los mismos que aplica
    `run_pathological_baroreflex()`: el override patológico si existe, si no
    los del Módulo 2."""
    override = PATHOLOGICAL_TONE_OVERRIDES.get(scenario)
    max_rd = override.max_rd if override is not None and override.max_rd is not None else BAROREFLEX_MAX_RD
    return BAROREFLEX_MIN_RD, max_rd


def describe_loop_outcome(result: ClosedLoopResult, target_map: float) -> str:
    """El comportamiento del lazo en una frase -- hallazgo fisiológico, no
    error. La saturación se lee del candidato del controlador (lo que el
    reflejo COMANDA), igual que `ClosedLoopResult`."""
    gap = target_map - result.final_map
    if not result.converged:
        if result.oscillated:
            return f"Sin equilibrio: el lazo oscila tras {len(result.ticks)} iteraciones."
        return f"Sin equilibrio en {len(result.ticks)} iteraciones: el lazo sigue derivando."
    if result.clamped_at_max_rd:
        return (
            f"Equilibrio con el efector saturado: Rd clavada en su techo de vasoconstricción. La PAM se "
            f"estabiliza en {result.final_map:.0f} mmHg, {gap:.0f} mmHg por debajo del objetivo -- el reflejo "
            "ya no puede compensar (descompensación)."
        )
    if result.clamped_at_min_rd:
        return (
            f"Equilibrio con el efector saturado: Rd en su vasodilatación máxima. La PAM se estabiliza en "
            f"{result.final_map:.0f} mmHg, {-gap:.0f} mmHg por encima del objetivo."
        )
    return (
        f"Equilibrio alcanzado en {len(result.ticks)} iteraciones: el reflejo cerró el error "
        f"(PAM {result.final_map:.1f} mmHg, objetivo {target_map:.1f})."
    )


def build_loop_figure(result: ClosedLoopResult, target_map: float, rd_min: float, rd_max: float) -> go.Figure:
    """Rd, PAM y gasto (VS x FC) por iteración. Líneas de referencia: los
    límites de Rd del escenario y la PAM objetivo. Las iteraciones donde el
    controlador comanda el límite se marcan. Sin colores de semáforo: es el
    comportamiento del lazo, no un nivel de riesgo."""
    x = [t.tick for t in result.ticks]
    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.07,
        subplot_titles=("Resistencia distal Rd (mmHg·s/mL)", "PAM (mmHg)", "Gasto cardíaco VS×FC (L/min)"),
    )
    line = dict(color=PALETTE.ACCENT_ON_DARK, width=2)
    marker = dict(size=6, color=PALETTE.ACCENT_ON_DARK)
    fig.add_trace(go.Scatter(x=x, y=[t.rd_after for t in result.ticks], name="Rd", mode="lines+markers",
                             line=line, marker=marker), row=1, col=1)
    fig.add_trace(go.Scatter(x=x, y=[t.map for t in result.ticks], name="PAM", mode="lines+markers",
                             line=line, marker=marker), row=2, col=1)
    fig.add_trace(go.Scatter(x=x, y=[t.stroke_volume_ml * result.heart_rate_bpm / 1000.0 for t in result.ticks],
                             name="Gasto", mode="lines+markers", line=line, marker=marker), row=3, col=1)

    saturated = [t for t in result.ticks if t.clamped_at_max_rd or t.clamped_at_min_rd]
    if saturated:
        fig.add_trace(go.Scatter(
            x=[t.tick for t in saturated], y=[t.rd_after for t in saturated], mode="markers",
            name="reflejo comanda el límite", marker=dict(symbol="x", size=10, color=PALETTE.TEXT),
        ), row=1, col=1)

    for y, text in ((rd_min, "vasodilatación máx."), (rd_max, "techo de vasoconstricción")):
        fig.add_hline(y=y, line_dash="dot", line_color=PALETTE.NEUTRAL, annotation_text=text,
                      annotation_position="top right", row=1, col=1)
    fig.add_hline(y=target_map, line_dash="dash", line_color=PALETTE.TEXT, annotation_text="PAM objetivo",
                  annotation_position="bottom right", row=2, col=1)

    fig.update_xaxes(title_text=ITERATION_AXIS_LABEL, row=3, col=1, dtick=1)
    fig.update_layout(
        height=620, showlegend=False,
        paper_bgcolor=PALETTE.BACKGROUND, plot_bgcolor=PALETTE.BACKGROUND, font=dict(color=PALETTE.TEXT),
    )
    return fig


def render_baroreflex_panel(scenario_labels: Dict[str, str]) -> None:
    """`scenario_labels`: `{valor_de_escenario: etiqueta}` para los escenarios
    habilitados (lo pasa `pages.py`, dueño de `RICH_SCENARIO_LABELS`)."""
    st.markdown("#### 🔁 Barorreflejo: el lazo cerrado por dentro")
    render_validation_marker("VALIDATED", VASCULAR_ARM_VALIDATION_DETAIL)
    st.caption(
        "Cuando la PAM se aleja de su punto de ajuste, el reflejo cambia el tono arteriolar (Rd); eso "
        "cambia el retorno venoso, el volumen sistólico y otra vez la PAM -- hasta que el lazo se "
        "asienta. Aquí ves cada vuelta de ese lazo."
    )

    scenarios = [s for s in ("healthy", "hypertension", "sepsis") if s in HEMODYNAMIC_MODEL_ENABLED_SCENARIOS]
    scenario = st.selectbox(
        "Escenario del lazo", scenarios, format_func=lambda s: scenario_labels.get(s, s), key="baroreflex_scenario",
    )
    hr = float(st.slider(
        "FC de entrada (lpm)", _HR_MIN_BPM, _HR_MAX_BPM, int(_FIXED_POINT_HR_BPM[scenario]),
        key=f"baroreflex_hr_{scenario}",
        help="La FC entra al lazo; el reflejo modelado no la modifica (sin brazo cardíaco).",
    ))

    loop = run_closed_loop(scenario, hr)
    isolated = run_pathological_baroreflex(scenario, hr)
    rd_min, rd_max = rd_limits(scenario)

    st.info(ITERATION_NOTE)
    if PHYSIOLOGICAL_PARAMETERS_PENDING_VALIDATION:
        st.warning(COMPLIANCE_PENDING_NOTE)

    st.plotly_chart(build_loop_figure(loop, isolated.target_map, rd_min, rd_max), width="stretch")
    st.markdown(f"**Comportamiento del lazo:** {describe_loop_outcome(loop, isolated.target_map)}")

    col_rd, col_conv, col_pa = st.columns(3)
    with col_rd:
        saturation = (
            "saturada en el techo" if loop.clamped_at_max_rd
            else "saturada en la vasodilatación máx." if loop.clamped_at_min_rd else "dentro de sus límites"
        )
        render_metric_card("Rd final", f"{loop.final_rd:.3f} mmHg·s/mL", citation=f"{saturation} [{rd_min:.2f}-{rd_max:.2f}]")
    with col_conv:
        convergence = "converge" if loop.converged else ("oscila" if loop.oscillated else "no converge")
        render_metric_card("Convergencia", convergence, citation=f"{len(loop.ticks)} iteraciones")
    with col_pa:
        render_metric_card(
            "PA final", f"{loop.final_systolic_bp:.0f}/{loop.final_diastolic_bp:.0f} mmHg",
            citation=f"PAM {loop.final_map:.1f} · S/D hereda el PENDING de la compliancia"
            if PHYSIOLOGICAL_PARAMETERS_PENDING_VALIDATION else f"PAM {loop.final_map:.1f}",
        )

    st.markdown(
        f"**Reflejo aislado vs. lazo completo** -- con el mismo motor: el reflejo solo, con volumen "
        f"sistólico fijo en {STROKE_VOLUME_REFERENCE_ML:.0f} mL (sin retorno venoso), deja la PAM en "
        f"**{isolated.final_map:.1f} mmHg** (Rd {isolated.final_rd:.3f}); el lazo completo, con retorno "
        f"venoso y Frank-Starling, en **{loop.final_map:.1f} mmHg** (Rd {loop.final_rd:.3f}). Si difieren, "
        "la diferencia la pone el retorno venoso, no el reflejo."
    )
    st.caption(CARDIAC_ARM_NOTE)
    st.caption(f"Mecanismo: {BAROREFLEX_MECHANISM_CITATION}")
