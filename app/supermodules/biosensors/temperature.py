"""Temperatura con la placa ESP32 + DS18B20, en la vista «Sensores en vivo» del Multisensor Fusion Lab (2026-11-16).

- `render_temp_measure()`: la placa real o la práctica en la barra lateral; la curva de los últimos minutos, la última
  lectura con su exactitud (±0.5 °C, hoja de datos), la tendencia del último minuto y si ya se estabilizó.
- `render_temp_tutorial()`: el tutorial del sensor, con una práctica por el mismo camino que la placa real.

No hay ninguna lectura de fiebre: la sonda mide piel, no temperatura central (Taylor 2014), y no es un termómetro
clínico. Nada se guarda al gemelo: el gemelo no tiene un campo de temperatura.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import streamlit as st

from app.supermodules.biosensors import live_service
from app.supermodules.biosensors.source import (BoardSignal, render_board_source, render_cable_control, rerun,
                                                 state_line)
from app.supermodules.biosensors.tutorial import render_sensor_tutorial
from app.utils.design_system import BADGES, render_metric_card
from hardware.biosensors import TEMP
from hardware.biosensors.quality import (STABLE_SLOPE_C_PER_MIN, STABLE_WINDOW_S, TEMP_ISSUE_TEXT, is_stable,
                                         temp_quality, temp_trend, valid_temperatures)

TITLE = 'Temperatura (DS18B20)'
TUTORIAL_TITLE = 'Temperatura (DS18B20): tutorial'
WINDOW_S = 600.0                 # la curva muestra hasta 10 minutos
MIN_SECONDS = 5.0
ACCURACY = '±0.5 °C entre −10 y +85 °C (hoja de datos del DS18B20), sin calibrar contra un termómetro clínico'
NOT_SAVED = 'No se guarda al gemelo: el gemelo no tiene un campo de temperatura.'

ORIGIN_TABLE = [
    ('Temperatura', 'La última lectura del DS18B20 (12 bits: pasos de 0.0625 °C)', '±0.5 °C según la hoja de datos; '
                                                                                  'sin calibrar aquí'),
    ('Tendencia', 'Pendiente de una recta por mínimos cuadrados sobre el último minuto, en °C por minuto',
     'Cálculo estándar'),
    ('«Estable»', f'La tendencia cambia menos de {STABLE_SLOPE_C_PER_MIN:g} °C por minuto', 'Heurística, sin criterio '
                                                                                            'clínico citado'),
    ('Fiebre', 'No se evalúa', 'La sonda mide piel, no temperatura central (Taylor 2014)'),
]
INTRO = (
    'Con un DS18B20 y una ESP32 puedes ver cómo una sonda se iguala con tu piel: sube rápido al principio y cada vez '
    'más despacio. Esa espera es la primera lección de cualquier termómetro. Sigue los pasos en orden; al final '
    'puedes practicar con una placa simulada.'
)
PRACTICE_INTRO = (
    'La placa simulada habla el mismo protocolo que el firmware y pasa por el mismo servicio que la real. Todo lo que '
    'ves aquí es **SIMULACIÓN**, en tiempo real: igualarse con la piel tarda unos minutos, como con una sonda de '
    'verdad.'
)
PRACTICE_OBSERVE = [
    '**Pon la sonda en la axila.** La curva sube rápido y luego cada vez más despacio. La app dice «estable» cuando '
    f'cambia menos de {STABLE_SLOPE_C_PER_MIN:g} °C en un minuto: en el simulador tarda unos 3 minutos.',
    '**Sácala al aire.** Baja hacia la temperatura del cuarto. Una lectura tomada antes de estabilizarse depende de '
    'cuánto esperaste, no solo de la persona.',
    '**Desconecta el cable.** El estado pasa a «sin conexión» y la app reintenta sola.',
]
PRACTICE_SIM_NOTE = (
    'Qué imita la placa simulada: una sonda que se acerca a 35.6 °C en la axila o a 24 °C en el aire, con una '
    'constante de tiempo de 30 s y pasos de 0.0625 °C. Son elecciones del simulador, no una medición.'
)


# ---------------------------------------------------------------- controles de la placa simulada
def render_temp_controls(board, container, prefix: str, fragment: bool = False) -> None:
    temp = board.model
    container.caption(f"Placa simulada: sonda {'en la axila' if temp.on_skin else 'al aire'} · cable "
                      f"{'conectado' if board.plugged else 'desconectado'}.")
    label = '🌬️ Sacar la sonda al aire' if temp.on_skin else '📍 Poner la sonda en la axila'
    if container.button(label, key=f'{prefix}_skin'):
        temp.set_on_skin(not temp.on_skin)
        rerun(fragment)
    render_cable_control(board, container, prefix, fragment)


# ---------------------------------------------------------------- curva y tarjetas
def temperature_figure(x_c: np.ndarray, fs: float, height: int = 260):
    """La curva sin forzar el eje en cero: así se ve cómo la sonda se acerca a la temperatura de la piel."""
    import plotly.graph_objects as go

    minutes = (np.arange(x_c.size) - x_c.size + 1) / fs / 60.0
    fig = go.Figure(go.Scatter(x=minutes, y=x_c, mode='lines', name='Temperatura', line=dict(width=2)))
    fig.update_layout(template='plotly_dark', height=height, showlegend=False, margin=dict(l=50, r=10, t=10, b=40),
                      xaxis_title='minutos (0 = ahora)', yaxis_title='°C, sonda')
    return fig


def render_temp_view(x_c: np.ndarray, fs: float, height: int = 260) -> None:
    issues = temp_quality(x_c)
    for issue in issues:
        st.warning(TEMP_ISSUE_TEXT[issue])
    x = valid_temperatures(x_c)
    if x.size == 0:
        st.info('Todavía no llega ninguna lectura válida.')
        return
    st.plotly_chart(temperature_figure(x, fs, height), use_container_width=True)
    trend = temp_trend(x, fs)
    cols = st.columns(3)
    with cols[0]:
        render_metric_card('Última lectura', f'{x[-1]:.2f} °C', citation=ACCURACY)
    with cols[1]:
        render_metric_card('Tendencia (último minuto)', None if trend is None else f'{trend:+.2f} °C/min',
                           unavailable_reason=f'No disponible todavía: hacen falta {STABLE_WINDOW_S:.0f} s de lecturas.')
    with cols[2]:
        if trend is None:
            state = 'Juntando un minuto de lecturas'
        elif is_stable(trend):
            state = 'Estable'
        else:
            state = 'Todavía cambia: espera'
        render_metric_card('¿Ya se puede leer?', state, provenance=BADGES.HEURISTIC)


# ---------------------------------------------------------------- medición
def render_temp_measure() -> Optional[BoardSignal]:
    board = render_board_source(TEMP, WINDOW_S, 'msl_temp', MIN_SECONDS, controls=render_temp_controls,
                                tutorial_hint='¿Primera vez? Elige «Tutorial».', mains_filter=False)
    if board is None:
        return None
    st.markdown(f'#### Últimos {board.data.shape[1] / board.fs / 60.0:.1f} min')
    render_temp_view(board.data[0], board.fs)
    st.caption('La sonda mide la temperatura de la piel donde la pongas, no la temperatura central: no la uses para '
               'decir si alguien tiene fiebre. ' + NOT_SAVED)
    return board


# ---------------------------------------------------------------- práctica
def _practice_body(service, board) -> None:
    snap = service.snapshot(seconds=WINDOW_S)
    st.markdown(state_line(snap))
    st.caption('🟡 PROCEDENCIA: SIMULACIÓN — placa simulada; no es un sensor.')
    render_temp_controls(board, st, 'msl_temp_tut_sim', fragment=True)
    data, fs = snap['data'], snap['fs']
    if snap['state'] != 'transmitiendo' or not fs or data.shape[-1] < int(MIN_SECONDS * fs):
        return
    render_temp_view(data[0], fs, height=220)


_fragment = getattr(st, 'fragment', None)
_practice_panel = _fragment(run_every=1.0)(_practice_body) if _fragment is not None else _practice_body


def _render_practice() -> None:
    practice = live_service.get_practice(TEMP.key)
    service, board = practice.service, practice.board
    st.markdown(PRACTICE_INTRO)
    if not service.is_running:
        if st.button('▶ Empezar práctica', key='msl_temp_tut_start'):
            board.plug()
            service.start()
            st.rerun()
        st.caption(PRACTICE_SIM_NOTE)
        return
    if st.button('⏹ Terminar práctica', key='msl_temp_tut_stop'):
        service.stop()
        st.rerun()
    _practice_panel(service, board)
    if _fragment is None:
        st.button('🔄 Actualizar', key='msl_temp_tut_refresh')
    st.markdown('**Qué observar**\n\n' + '\n'.join(f'- {item}' for item in PRACTICE_OBSERVE))
    st.caption(PRACTICE_SIM_NOTE)


def render_temp_tutorial() -> None:
    render_sensor_tutorial(TEMP, TUTORIAL_TITLE, 'msl_temp_tutorial', INTRO, ORIGIN_TABLE, 'DS18B20', _render_practice)

