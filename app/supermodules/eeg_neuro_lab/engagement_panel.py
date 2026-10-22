"""
Panel de Engagement Index (β/(α+θ), Pope 1995) del EEG Neuro Lab: controles
del bloque de tarea en el sidebar y la medición relativa al reposo del propio
sujeto. Gramática neutra (marco accent, nunca semáforo): es una métrica de
rendimiento operativo de sesión, no un diagnóstico. Aislado del UPS, igual
que el panel de ERD.

`EngagementTaskEvent` es el dueño único de la temporización: el sidebar lo
construye, el generador lo consume, y aquí se traduce a las ventanas del
detector. El gráfico dibuja la curva, las ventanas y el nivel de baseline
que devuelve `EngagementResult` -- no una copia recalculada.
"""

from typing import Optional

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from app.utils.design_system import PALETTE, GRAMMAR_NEUTRAL_STATE, render_error_state, render_metric_card
from src.signals.eeg.eeg_generator import EngagementTaskEvent

# Import guardado, mismo patrón que `mu_erd_panel.py`: si el detector no
# resuelve, el resto del EEG Lab sigue en pie. Uso por atributo para que un
# parche sobre el módulo origen llegue aquí.
try:
    from src.signals.eeg import engagement_detector
    engagement_detector_import_error = None
except ImportError as e:
    engagement_detector = None
    engagement_detector_import_error = e

ENGAGEMENT_TASK_LABEL = "Engagement (reposo → tarea)"

# Al menos 2.5s de reposo antes (2s limpios mínimos por ventana + 0.5s de
# entrada), y el bloque completo más medio segundo antes del final. El tope
# del slider nunca baja de `_LATEST_TASK_FLOOR_S` (> mínimo): con una señal
# corta (10s) el bloque no cabe, el slider sigue siendo válido y el detector
# declina con motivo -- antes min == max tumbaba la página entera.
_EARLIEST_TASK_S = 3.0
_LATEST_TASK_FLOOR_S = 4.0
_POST_TASK_REST_S = 0.5


def render_engagement_sidebar(pattern: str, duration: float) -> Optional[EngagementTaskEvent]:
    """Los dos parámetros honestos del bloque: cambio de engagement (lo que
    el detector debe recuperar) e inicio de la tarea. `None` si el patrón
    elegido no es el de engagement."""
    if pattern != ENGAGEMENT_TASK_LABEL:
        return None

    defaults = EngagementTaskEvent()
    st.sidebar.markdown("#### Bloque de tarea (Engagement)")
    change_pct = st.sidebar.slider(
        "Cambio de engagement (%)", min_value=-50, max_value=150, value=int(defaults.change_pct), step=10,
        help="Cambio del índice β/(α+θ) durante la tarea respecto al reposo del propio sujeto "
             "(Pope 1995). Positivo: mayor enganche; negativo: desatención. Es el valor que el "
             "detector debe recuperar.",
    )
    latest_task_s = max(_LATEST_TASK_FLOOR_S, float(duration) - defaults.total_span_s - _POST_TASK_REST_S)
    t_task = st.sidebar.slider(
        "Inicio de la tarea (s)", min_value=_EARLIEST_TASK_S, max_value=latest_task_s,
        value=min(defaults.t_task, latest_task_s), step=1.0,
        help="Instante en que empieza la tarea simulada. Deja reposo antes (baseline) y espacio "
             f"después (transición + tarea + recuperación, ~{defaults.total_span_s:.0f}s).",
    )
    return EngagementTaskEvent(t_task=t_task, change_pct=change_pct)


def build_engagement_figure(result, lead: str) -> go.Figure:
    """Curva β/(α+θ) por ventana + tramos de baseline/tarea
    (`result.baseline_window`/`result.task_window`) + línea en
    `result.baseline_value`, para que se vea el cambio RELATIVO. Gramática
    neutra: curva accent, sin colores de semáforo. Los huecos (`NaN`) son
    ventanas rechazadas, no se interpolan."""
    fig = go.Figure()
    fig.add_vrect(
        x0=result.baseline_window[0], x1=result.baseline_window[1],
        fillcolor=PALETTE.NEUTRAL, opacity=0.2, line_width=0,
        annotation_text="Baseline (reposo)", annotation_position="top left",
    )
    fig.add_vrect(
        x0=result.task_window[0], x1=result.task_window[1],
        fillcolor=PALETTE.PRIMARY, opacity=0.2, line_width=0,
        annotation_text="Tarea", annotation_position="top left",
    )
    fig.add_hline(
        y=result.baseline_value, line_dash="dash", line_color=PALETTE.TEXT,
        annotation_text="nivel de baseline", annotation_position="bottom right",
    )
    fig.add_trace(go.Scatter(
        x=result.curve_time, y=result.engagement_curve, name=f"β/(α+θ) ({lead})",
        mode="lines+markers", connectgaps=False,
        line=dict(color=PALETTE.ACCENT_ON_DARK, width=1.5), marker=dict(size=4, color=PALETTE.ACCENT_ON_DARK),
    ))
    fig.update_layout(
        height=320,
        paper_bgcolor=PALETTE.BACKGROUND, plot_bgcolor=PALETTE.BACKGROUND, font=dict(color=PALETTE.TEXT),
        xaxis_title="Tiempo (s)", yaxis_title="Engagement β/(α+θ) por ventana de 1s",
    )
    return fig


def render_engagement_panel(signal: np.ndarray, lead: str, fs: float, event: EngagementTaskEvent) -> None:
    st.markdown("## 🎯 Engagement Index (β/(α+θ))")
    st.markdown(
        "Índice de enganche atencional del sistema biocibernético de Pope: la razón β/(α+θ) sube "
        "con la concentración activa y baja con la desatención o la somnolencia. Se mide como "
        "cambio durante la tarea respecto al reposo del mismo sujeto, no como valor absoluto."
    )

    if engagement_detector is None:
        render_error_state(
            "El detector de Engagement (engagement_detector.py) no está disponible en este entorno.",
            exception=engagement_detector_import_error,
        )
        return

    windows = event.measurement_windows()
    result = engagement_detector.detect_engagement(
        signal, fs, t_task=event.t_task,
        baseline_duration_s=windows.baseline_duration_s,
        task_offset_s=windows.event_offset_s,
        task_duration_s=windows.event_duration_s,
    )

    # Cláusula de alcance SIEMPRE visible, disponible o no la medición.
    st.warning(f"**Alcance de esta medición:** {result.scope_note}")

    # Una sola llamada al detector por render: curva, ventanas y % vienen en
    # el mismo resultado. Sin medición (`engagement_curve=None`) no hay
    # gráfico -- solo el motivo de abajo, nunca una curva vacía o plana.
    if result.engagement_curve is not None:
        st.plotly_chart(build_engagement_figure(result, lead), width="stretch")

    if result.available:
        pct = result.engagement_relative_pct
        render_metric_card(
            'Engagement relativo al baseline', f'{pct:+.1f}% respecto al reposo',
            classification=engagement_detector.classify_engagement_change(pct),
            grammar=GRAMMAR_NEUTRAL_STATE, citation=engagement_detector.ENGAGEMENT_CITATION,
        )
        st.caption(
            f"Canal {lead} · baseline [{result.baseline_window[0]:.1f}s, {result.baseline_window[1]:.1f}s) "
            f"β/(α+θ)={result.baseline_value:.3f} · tarea [{result.task_window[0]:.1f}s, "
            f"{result.task_window[1]:.1f}s) β/(α+θ)={result.task_value:.3f}"
        )
    else:
        st.info(f"Engagement no disponible: {result.reason}")
        render_metric_card('Engagement relativo al baseline', None, unavailable_reason=result.reason)
