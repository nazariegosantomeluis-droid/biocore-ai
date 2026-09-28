"""
Panel de desincronización mu (ERD) del EEG Neuro Lab: controles del evento
motor en el sidebar y la curva temporal de potencia mu con la medición del
detector. Demostrador del principio del BCI, mono-canal, sin lateralidad --
aislado del UPS (demostración de fenómeno, no escritor del organismo).

`MotorImageryEvent` es el dueño único de la temporización: el sidebar lo
construye, el generador lo consume, y aquí se traduce a las ventanas del
detector. El gráfico dibuja las ventanas que devuelve `ErdResult`, no una
copia recalculada -- el dibujo no puede desviarse de la medición.
"""

from typing import Optional

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from app.utils.design_system import (
    BADGES,
    GRAMMAR_NEUTRAL_STATE,
    PALETTE,
    render_error_state,
    render_metric_card,
)
from src.signals.eeg.eeg_generator import MotorImageryEvent

# Import guardado: si el detector no resuelve, el resto del EEG Lab sigue
# funcionando y este panel declara la ausencia en vez de crashear. Se usa
# por atributo (`erd_detector.detect_mu_erd`) para que un parche sobre el
# módulo origen llegue aquí.
try:
    from src.signals.eeg import erd_detector
    erd_detector_import_error = None
except ImportError as e:
    erd_detector = None
    erd_detector_import_error = e

MOTOR_IMAGERY_LABEL = "Motor Imagery (ERD)"

# Límites del slider "Momento del evento": al menos 2s de reposo antes, y
# todo el evento (`total_span_s`) más medio segundo de reposo antes del
# final de la señal.
_EARLIEST_EVENT_S = 2.0
_LATEST_EVENT_FLOOR_S = 3.0
_DEFAULT_EVENT_S = 10.0
_POST_RECOVERY_REST_S = 0.5


def render_mu_erd_sidebar(pattern: str, duration: float) -> Optional[MotorImageryEvent]:
    """Los dos únicos parámetros honestos del evento motor: profundidad (lo
    que el detector debe recuperar) y momento. Transición/meseta/
    recuperación quedan en el default de `MotorImageryEvent`. `None` si el
    patrón elegido no es el de imaginación motora."""
    if pattern != MOTOR_IMAGERY_LABEL:
        return None

    defaults = MotorImageryEvent()
    st.sidebar.markdown("#### Evento motor (ERD)")
    depth_pct = st.sidebar.slider(
        "Profundidad del ERD (%)", min_value=10, max_value=90, value=int(defaults.depth_pct), step=5,
        help="Caída de POTENCIA en banda mu durante el evento, respecto al reposo -- la fórmula de "
             "Pfurtscheller (ERD% = (baseline-evento)/baseline·100). Este es el valor que el detector "
             "debe recuperar.",
    )
    latest_event_s = max(_LATEST_EVENT_FLOOR_S, float(duration) - defaults.total_span_s - _POST_RECOVERY_REST_S)
    t_event = st.sidebar.slider(
        "Momento del evento (s)", min_value=_EARLIEST_EVENT_S, max_value=latest_event_s,
        value=min(_DEFAULT_EVENT_S, latest_event_s), step=1.0,
        help="Instante en que empieza la desincronización simulada. Deja reposo antes (baseline) y "
             f"espacio después (transición + evento + recuperación, ~{defaults.total_span_s:.0f}s con los defaults).",
    )
    return MotorImageryEvent(t_event=t_event, depth_pct=depth_pct)


def build_erd_figure(result, time: np.ndarray, lead: str) -> go.Figure:
    """Curva de potencia mu + marca del evento; si el detector midió, las
    ventanas de baseline/evento son exactamente `result.baseline_window`/
    `result.event_window`."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=time, y=result.power_curve, name=f"Potencia mu ({lead})",
        line=dict(color=PALETTE.ACCENT_ON_DARK, width=1.5),
    ))
    fig.add_vline(
        x=result.t_event, line_dash="dash", line_color=PALETTE.WARNING,
        annotation_text="Evento motor", annotation_position="top",
    )
    if result.available:
        fig.add_vrect(
            x0=result.baseline_window[0], x1=result.baseline_window[1],
            fillcolor=PALETTE.STABLE, opacity=0.15, line_width=0,
            annotation_text="Baseline", annotation_position="top left",
        )
        fig.add_vrect(
            x0=result.event_window[0], x1=result.event_window[1],
            fillcolor=PALETTE.CRITICAL, opacity=0.15, line_width=0,
            annotation_text="ERD", annotation_position="top",
        )
    fig.update_layout(
        template='plotly_dark', height=320,
        paper_bgcolor=PALETTE.BACKGROUND, plot_bgcolor=PALETTE.BACKGROUND, font=dict(color=PALETTE.TEXT),
        xaxis_title="Tiempo (s)", yaxis_title="Potencia instantánea banda mu (µV²)",
    )
    return fig


def render_mu_erd_panel(signal: np.ndarray, lead: str, fs: float, time: np.ndarray, event: MotorImageryEvent) -> None:
    """El ERD es TEMPORAL: se muestra la curva de potencia mu en el tiempo,
    no un solo valor. Una sola llamada al detector por render -- la curva y
    las ventanas vienen en el mismo `ErdResult`."""
    st.markdown("## 🧠🖐️ Desincronización de banda Mu (ERD)")
    st.markdown(
        "Demostrador del principio del BCI (interfaz cerebro-computadora): la potencia de la "
        "banda mu (8-13Hz) cae alrededor de un evento motor y se recupera después -- la "
        "desincronización que un sistema BCI real detecta para inferir intención de movimiento."
    )

    if erd_detector is None:
        render_error_state(
            "El detector de ERD (erd_detector.py) no está disponible en este entorno.",
            exception=erd_detector_import_error,
        )
        return

    windows = event.measurement_windows()
    result = erd_detector.detect_mu_erd(
        signal, fs, t_event=event.t_event,
        baseline_duration_s=windows.baseline_duration_s,
        event_offset_s=windows.event_offset_s,
        event_duration_s=windows.event_duration_s,
    )

    # Rótulo de alcance SIEMPRE visible (disponible o no la medición), con
    # peso de aviso -- `st.warning`, no `st.caption`.
    st.warning(f"**Alcance de esta demostración:** {result.scope_note}")
    # Sin curva (señal demasiado corta para filtrar) no hay gráfico que
    # dibujar -- solo el motivo de abajo, nunca una curva de relleno.
    if result.power_curve is not None:
        st.plotly_chart(build_erd_figure(result, time, lead), use_container_width=True)
        st.caption(f"Canal mostrado: {lead} -- demostración MONO-CANAL (ver rótulo de alcance arriba).")

    # Degradación honesta: el motivo, nunca un ERD% fabricado.
    if result.available:
        render_metric_card(
            'ERD (mu) recuperado', f'{result.erd_percent:.1f}%',
            # METHOD: demostración de fenómeno con fórmula real
            # (Pfurtscheller), no score clínico ni heurística sobre datos reales.
            provenance=BADGES.METHOD, grammar=GRAMMAR_NEUTRAL_STATE,
            citation=result.scope_note,
        )
        st.caption(
            f"Evento en t={result.t_event:.1f}s · potencia baseline="
            f"{result.baseline_power:.1f} · potencia durante el evento="
            f"{result.event_power:.1f}"
        )
    else:
        st.info(f"ERD no disponible: {result.reason}")
        render_metric_card('ERD (mu) recuperado', None, unavailable_reason=result.reason)
