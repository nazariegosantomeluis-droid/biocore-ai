"""Pulso por luz con la placa ESP32 + MAX30102, en la vista «Sensores en vivo» del Multisensor Fusion Lab
(2026-11-16).

- `render_ppg_measure()`: la placa real o la práctica en la barra lateral; la onda de pulso, la frecuencia de pulso,
  el índice de perfusión y R. La SpO₂ dice «no disponible» con el motivo (Art. I).
- `render_ppg_tutorial()`: el tutorial del sensor, con una práctica que pasa por el mismo protocolo, el mismo servicio
  y el mismo analizador que la placa real.

Nada de esto se guarda al gemelo: el gemelo recibe la frecuencia cardíaca solo por la compuerta validada del ECG Lab.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np
import streamlit as st

from app.supermodules.biosensors import live_service
from app.supermodules.biosensors.source import (BoardSignal, render_board_source, render_cable_control, rerun,
                                                 state_line)
from app.supermodules.biosensors.tutorial import render_sensor_tutorial
from app.utils.design_system import BADGES, PALETTE, render_metric_card
from clinical.ppg_references import BEURTON_2019, ELGENDI_2013
from hardware.biosensors import PPG
from hardware.biosensors.quality import PPG_ISSUE_TEXT, ppg_quality
from src.signals.ppg import PpgAnalysis, analyze_ppg

TITLE = 'Pulso por luz (MAX30102)'
TUTORIAL_TITLE = 'Pulso por luz (MAX30102): tutorial'
WINDOW_S = 10.0
MIN_SECONDS = 5.0
RATES = (('🫀 Pulso en reposo (65 lpm)', 65.0), ('🏃 Pulso después de correr (110 lpm)', 110.0))
SPO2_REASON = ('No disponible: un oxímetro convierte R en SpO₂ con una curva calibrada contra mediciones directas de '
               'la saturación arterial (Jubran 2015), y este sensor no la tiene.')
NOT_SAVED = ('No se guarda al gemelo: el gemelo recibe la frecuencia cardíaca solo por la compuerta validada del ECG '
             'Lab, y la frecuencia de pulso de este sensor no ha pasado por ella.')

ORIGIN_TABLE = [
    ('Frecuencia de pulso', 'Picos sistólicos del infrarrojo (método de Elgendi et al. 2013); 60 entre la mediana de '
                            'los intervalos', 'Método publicado; aquí coincidió con HeartPy en sus grabaciones de '
                                              'ejemplo, pero no se ha validado con este sensor'),
    ('Índice de perfusión', 'Parte pulsátil entre parte no pulsátil del infrarrojo, en % (definición de Beurton et '
                            'al. 2019)', 'Cálculo estándar; depende del sitio, la presión y el sensor'),
    ('R (rojo / infrarrojo)', '(AC/DC del rojo) entre (AC/DC del infrarrojo), latido a latido', 'Cálculo estándar; '
                                                                                                 'sin curva no es SpO₂'),
    ('SpO₂', 'No se calcula', 'No disponible: falta la curva de calibración (Jubran 2015)'),
    ('Avisos de calidad', 'Comprobaciones del equipo: sin dedo, luz saturada, sin pulso o intervalos dispersos',
     'Solo avisan si la señal sirve; no son un juicio clínico'),
]
INTRO = (
    'Con un MAX30102 y una ESP32 puedes ver tu propia onda de pulso: la luz roja e infrarroja que atraviesa el dedo '
    'baja un poco en cada latido, porque entra más sangre. De ahí salen la frecuencia de pulso, el índice de '
    'perfusión y el cociente R. La saturación de oxígeno no: para eso hace falta una calibración que este sensor no '
    'trae. Sigue los pasos en orden; al final puedes practicar con una placa simulada.'
)
PRACTICE_INTRO = (
    'La placa simulada habla el mismo protocolo que el firmware y pasa por el mismo servicio y el mismo analizador '
    'que la real. Todo lo que ves aquí es **SIMULACIÓN**. Es la misma placa que el modo «Práctica» de la vista de '
    'medición.'
)
PRACTICE_OBSERVE = [
    '**Cambia el pulso.** La frecuencia sigue al simulador en unos segundos: la app usa la mediana de los intervalos '
    'de los últimos 10 s.',
    '**Muévete.** El movimiento cambia la luz más que el pulso: aparecen picos de más y la app avisa que los '
    'intervalos varían mucho. El PPG no distingue el movimiento de un ritmo irregular.',
    '**Quita el dedo.** Solo queda la luz ambiente y la app lo dice; no inventa un pulso.',
    '**Desconecta el cable.** El estado pasa a «sin conexión» y la app reintenta sola.',
]
PRACTICE_SIM_NOTE = (
    'Qué imita la placa simulada: 120 000 cuentas de luz infrarroja de fondo con el dedo puesto, un índice de '
    'perfusión de 2 %, R = 0.55 y la respiración moviendo un poco la línea de base y el ritmo. Son elecciones del '
    'simulador, no un PPG registrado.'
)


@dataclass
class PpgLive:
    analysis: PpgAnalysis
    label: str
    provenance: str
    issues: Tuple[str, ...]


# ---------------------------------------------------------------- controles de la placa simulada
def render_ppg_controls(board, container, prefix: str, fragment: bool = False) -> None:
    ppg = board.model
    container.caption(f"Placa simulada: {ppg.rate_bpm:.0f} lpm · dedo {'puesto' if ppg.finger else 'fuera'} · "
                      f"{'moviéndose' if ppg.motion else 'quieto'} · cable "
                      f"{'conectado' if board.plugged else 'desconectado'}.")
    for label, bpm in RATES:
        if container.button(label, key=f'{prefix}_rate{int(bpm)}'):
            ppg.set_rate(bpm)
            rerun(fragment)
    if container.button('☝️ Poner el dedo' if not ppg.finger else '🖐️ Quitar el dedo', key=f'{prefix}_finger'):
        ppg.set_finger(not ppg.finger)
        rerun(fragment)
    if container.button('🤚 Mover la mano' if not ppg.motion else '🧘 Quedarse quieto', key=f'{prefix}_motion'):
        ppg.set_motion(not ppg.motion)
        rerun(fragment)
    render_cable_control(board, container, prefix, fragment)


# ---------------------------------------------------------------- análisis y tarjetas
def _counts(value: float) -> str:
    return f'{value:,.0f}'.replace(',', ' ')


def ppg_live(board: BoardSignal) -> PpgLive:
    analysis = analyze_ppg(board.data[0], board.data[1], board.fs)
    return PpgLive(analysis, board.label, board.provenance, ppg_quality(analysis))


def wave_figure(analysis: PpgAnalysis, height: int = 260, show_peaks: bool = True):
    """La onda de pulso con los picos sistólicos que encontró el detector: se ve qué contó como latido. Sin dedo no se
    marcan: serían picos del ruido."""
    import plotly.graph_objects as go

    wave = analysis.wave
    t = (np.arange(wave.size) - wave.size + 1) / analysis.fs
    fig = go.Figure(go.Scatter(x=t, y=wave, mode='lines', name='Onda de pulso', line=dict(width=1.5)))
    if show_peaks and analysis.peaks.size:
        fig.add_trace(go.Scatter(x=t[analysis.peaks], y=wave[analysis.peaks], mode='markers', name='Pico sistólico',
                                 marker=dict(size=8, color=PALETTE.WARNING)))
    fig.update_layout(template='plotly_dark', height=height, showlegend=False, margin=dict(l=50, r=10, t=10, b=40),
                      xaxis_title='s (0 = ahora)', yaxis_title='cuentas, filtrada e invertida')
    return fig


def _render_wave(analysis: PpgAnalysis, issues: Tuple[str, ...], height: int = 260) -> None:
    st.plotly_chart(wave_figure(analysis, height, show_peaks='sin dedo' not in issues), use_container_width=True)


SATURATED_REASON = 'No disponible: la señal está saturada (ver el aviso de arriba); no es una señal válida.'


def render_ppg_cards(analysis: PpgAnalysis, issues: Tuple[str, ...]) -> None:
    for issue in issues:                       # primero los avisos: dicen si los números de abajo valen
        st.warning(PPG_ISSUE_TEXT[issue])
    # 2026-11-16 (Art. I): con la señal saturada tampoco hay números: lo que queda bajo el tope no es una onda de pulso
    # completa, y antes salía una frecuencia.
    saturated = 'saturada' in issues
    usable = 'sin dedo' not in issues and not saturated
    rate = analysis.pulse_rate_bpm if usable else None
    cols = st.columns(4)
    with cols[0]:
        render_metric_card('Frecuencia de pulso', None if rate is None else f'{rate:.0f} lpm',
                           provenance=BADGES.PENDING, citation=ELGENDI_2013,
                           unavailable_reason=SATURATED_REASON if saturated else
                           'No disponible: no se encontraron al menos 3 intervalos de pulso plausibles en la ventana.')
    with cols[1]:
        pi = analysis.perfusion_index_pct if usable else None
        render_metric_card('Índice de perfusión (IR)', None if pi is None else f'{pi:.2f} %',
                           provenance=BADGES.PENDING, citation=BEURTON_2019,
                           unavailable_reason=SATURATED_REASON if saturated else
                           'No disponible: sin pulsos medibles no hay parte pulsátil.')
    with cols[2]:
        ratio = analysis.ratio_r if usable else None
        render_metric_card('R (rojo / infrarrojo)', None if ratio is None else f'{ratio:.3f}',
                           provenance=BADGES.PENDING,
                           unavailable_reason=SATURATED_REASON if saturated else
                           'No disponible: sin pulsos medibles en las dos luces.')
    with cols[3]:
        render_metric_card('SpO₂', None, unavailable_reason=SPO2_REASON)


# ---------------------------------------------------------------- medición
def render_ppg_measure() -> Optional[PpgLive]:
    board = render_board_source(PPG, WINDOW_S, 'msl_ppg', MIN_SECONDS, controls=render_ppg_controls,
                                tutorial_hint='¿Primera vez? Elige «Tutorial».', mains_filter=False)
    if board is None:
        return None
    live = ppg_live(board)
    st.markdown(f'#### Últimos {board.data.shape[1] / board.fs:.0f} s')
    _render_wave(live.analysis, live.issues)
    background = (f'Luz de fondo: {_counts(live.analysis.dc_ir)} cuentas en el infrarrojo y '
                  f'{_counts(live.analysis.dc_red)} en el rojo.')
    if 'sin dedo' in live.issues:
        st.caption('Luz infrarroja recibida, filtrada de 0.5 a 8 Hz e invertida. Sin dedo es solo ruido: no se marcan '
                   'picos. ' + background)
    else:
        st.caption(f'Luz infrarroja recibida, filtrada de 0.5 a 8 Hz e invertida: cada punto amarillo es un pico '
                   f'sistólico que contó el detector ({live.analysis.peaks.size} en la ventana). ' + background)
    render_ppg_cards(live.analysis, live.issues)
    st.caption(NOT_SAVED)
    return live


# ---------------------------------------------------------------- práctica
def _practice_body(service, board) -> None:
    snap = service.snapshot(seconds=WINDOW_S)
    st.markdown(state_line(snap))
    st.caption('PROCEDENCIA: SIMULACIÓN — placa simulada; no es un sensor.')
    render_ppg_controls(board, st, 'msl_ppg_tut_sim', fragment=True)
    data, fs = snap['data'], snap['fs']
    if snap['state'] != 'transmitiendo' or not fs or data.shape[-1] < int(MIN_SECONDS * fs):
        return
    analysis = analyze_ppg(data[0], data[1], fs)
    issues = ppg_quality(analysis)
    _render_wave(analysis, issues, height=220)
    render_ppg_cards(analysis, issues)


_fragment = getattr(st, 'fragment', None)
_practice_panel = _fragment(run_every=1.0)(_practice_body) if _fragment is not None else _practice_body


def _render_practice() -> None:
    practice = live_service.get_practice(PPG.key)
    service, board = practice.service, practice.board
    st.markdown(PRACTICE_INTRO)
    if not service.is_running:
        if st.button('▶ Empezar práctica', key='msl_ppg_tut_start'):
            board.plug()
            service.start()
            st.rerun()
        st.caption(PRACTICE_SIM_NOTE)
        return
    if st.button('⏹ Terminar práctica', key='msl_ppg_tut_stop'):
        service.stop()
        st.rerun()
    _practice_panel(service, board)
    if _fragment is None:
        st.button('🔄 Actualizar', key='msl_ppg_tut_refresh')
    st.markdown('**Qué observar**\n\n' + '\n'.join(f'- {item}' for item in PRACTICE_OBSERVE))
    st.caption(PRACTICE_SIM_NOTE)


def render_ppg_tutorial() -> None:
    render_sensor_tutorial(PPG, TUTORIAL_TITLE, 'msl_ppg_tutorial', INTRO, ORIGIN_TABLE, 'MAX30102', _render_practice)
