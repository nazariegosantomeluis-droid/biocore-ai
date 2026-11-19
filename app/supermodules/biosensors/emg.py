"""Lo propio del EMG Muscle Lab con la placa ESP32 + MyoWare 2.0 (2026-11-14).

- `render_emg_source()`: la fuente «Sensor en vivo (ESP32 + MyoWare)». Reemplaza la rama «Live Hardware», que sin
  datos de hardware caía en silencio a la señal demo («usando demo mientras se conecta») y usaba un lector
  (`hardware/emg_stream.py`) sin firmware en el repo. Aquí sin placa transmitiendo no hay análisis.
- `twin_provenance()` / `save_blocker()`: SENSOR_REAL solo con la placa real transmitiendo y sin avisos de calidad.
- `render_emg_tutorial()`: la vista «Sensor en vivo (tutorial)», con una práctica que pasa por el mismo protocolo,
  el mismo servicio y el mismo analizador que la placa real.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np
import pandas as pd
import streamlit as st

from app.supermodules.biosensors import live_service
from app.supermodules.biosensors.source import (MAINS_OPTIONS, BoardSignal, render_board_source,
                                                 render_cable_control, rerun, state_line)
from app.supermodules.biosensors.tutorial import render_sensor_tutorial
from domain.physiology.state import Provenance
from hardware.biosensors import EMG
from hardware.biosensors.quality import ISSUE_TEXT, emg_quality, prepare, rms_mv
from hardware.eeg_live.devices import SENSOR_REAL

try:
    from src.signals.emg import EmgAnalyzer
except ImportError:                       # el tutorial no depende del analizador
    EmgAnalyzer = None

SOURCE_LABEL = 'Sensor en vivo (ESP32 + MyoWare)'
TUTORIAL_VIEW = 'Sensor en vivo (tutorial)'
MIN_SECONDS = 2.0
LEVELS = (('💪 Contraer suave (30 %)', 0.3), ('💪 Contraer fuerte (80 %)', 0.8))

ORIGIN_TABLE = [
    ('RMS del EMG', 'Raíz cuadrática media de la señal entre 20 y 450 Hz (la banda de `EmgAnalyzer`), en mV',
     'Cálculo estándar; los mV son aproximados (ganancia del sensor y ADC sin calibrar)'),
    ('Frecuencia mediana (MDF)', '`EmgAnalyzer`: espectro de Welch de la señal filtrada', 'Cálculo estándar; no se ha '
                                                                                          'validado con placas reales'),
    ('«Activación muscular» del laboratorio', 'Cociente entre el promedio y el pico del EMG rectificado',
     'No es %MVC: no mide cuánto contraes'),
    ('Avisos de calidad', 'Comprobaciones del equipo: señal pegada al límite, plana o con zumbido de la red',
     'Solo avisan si la señal sirve; no son un juicio clínico'),
]
INTRO = (
    'Con un MyoWare 2.0 y una ESP32 puedes ver tu propio EMG de superficie en el Laboratorio de EMG: la señal, su RMS y su '
    'frecuencia mediana. Sigue los pasos en orden; al final puedes practicar todo el flujo con una placa simulada.'
)
PRACTICE_INTRO = (
    'La placa simulada habla el mismo protocolo que el firmware y pasa por el mismo servicio, el mismo filtro y el '
    'mismo analizador que la real. Todo lo que ves aquí es **SIMULACIÓN**. Es la misma placa que el modo «Práctica» '
    'de la fuente en vivo del laboratorio.'
)
PRACTICE_OBSERVE = [
    # Teoría citada 2 (2026-11-17, Art. I): decía «El RMS sube con la fuerza que elijas»; el simulador sube el RMS con el
    # nivel elegido porque así está programado, pero en un músculo la amplitud no dice la fuerza (A1, A9).
    '**Contrae y relaja.** El RMS sube con el nivel que elijas (así está programada la placa simulada) y vuelve al piso '
    'de ruido (unos 10 µV) al relajar; la «activación muscular» del laboratorio casi no cambia, porque es un cociente '
    'entre el promedio y el pico. En un músculo de verdad, la amplitud del EMG de superficie indica la **excitación** '
    'del músculo, no su fuerza [V2018].',
    '**Despega un electrodo.** Entra el zumbido de la red y una deriva lenta: la calidad lo marca y el guardado al '
    'gemelo se bloquea.',
    '**Desconecta el cable.** El estado pasa a «sin conexión» al instante y la app reintenta sola; al reconectar, '
    'vuelve con el búfer vacío.',
]
PRACTICE_SIM_NOTE = (
    'Qué imita la placa simulada: ruido de 10 µV en reposo y, al contraer, ruido filtrado de 30 a 200 Hz con un RMS '
    'de hasta 0.5 mV, convertido a cuentas como la salida RAW del MyoWare a 3.3 V. Son elecciones del simulador, no '
    'un EMG registrado.'
)


@dataclass
class EmgLive:
    signal: np.ndarray            # mV en la piel, sin media y sin red
    fs: float
    label: str
    provenance: str
    issues: Tuple[str, ...]
    rms_mv: Optional[float]


# ---------------------------------------------------------------- controles de la placa simulada
def render_emg_controls(board, container, prefix: str, fragment: bool = False) -> None:
    """Botones (no casillas): así no muestran un estado viejo si la misma placa se movió desde otra vista."""
    emg = board.model
    fuerza = f'{emg.level * 100:.0f} %' if emg.level else 'relajado'
    container.caption(f"Placa simulada: {fuerza} · electrodo {'despegado' if emg.electrode_off else 'pegado'} · "
                      f"cable {'conectado' if board.plugged else 'desconectado'}.")
    for label, level in LEVELS:
        if container.button(label, key=f'{prefix}_lvl{int(level * 100)}'):
            emg.set_level(level)
            rerun(fragment)
    if container.button('😌 Relajar', key=f'{prefix}_relax'):
        emg.set_level(0.0)
        rerun(fragment)
    if emg.electrode_off:
        if container.button('🩹 Volver a pegar el electrodo', key=f'{prefix}_stick'):
            emg.set_electrode_off(False)
            rerun(fragment)
    elif container.button('✋ Despegar un electrodo', key=f'{prefix}_unstick'):
        emg.set_electrode_off(True)
        rerun(fragment)
    render_cable_control(board, container, prefix, fragment)


# ---------------------------------------------------------------- fuente del laboratorio
def render_emg_source(duration_s: float) -> Optional[EmgLive]:
    board = render_board_source(EMG, duration_s, 'emglab_live', MIN_SECONDS, controls=render_emg_controls,
                                tutorial_hint=f'¿Primera vez? Elige la vista «{TUTORIAL_VIEW}».')
    if board is None:
        return None
    return _emg_live(board)


def _emg_live(board: BoardSignal) -> EmgLive:
    raw = board.data[0]
    issues = emg_quality(raw, board.fs, board.mains_hz)
    for issue in issues:
        st.sidebar.warning(ISSUE_TEXT[issue])
    signal = prepare(raw, board.fs, board.mains_hz)
    return EmgLive(signal, board.fs, board.label, board.provenance, issues, rms_mv(signal, board.fs))


def twin_provenance(live: Optional[EmgLive]) -> Tuple[Provenance, str]:
    if live is None:
        return Provenance.SIMULACION, 'Procedencia: simulación (señal generada o archivo cargado, no un sensor en vivo).'
    if live.provenance == SENSOR_REAL:
        return Provenance.SENSOR_REAL, f'Procedencia: SENSOR_REAL ({live.label}, mandando datos en este momento).'
    return Provenance.SIMULACION, f'Procedencia: simulación ({live.label}).'


def save_blocker(live: Optional[EmgLive]) -> Optional[str]:
    if live is None or not live.issues:
        return None
    return 'la señal en vivo tiene avisos de calidad: ' + ' '.join(ISSUE_TEXT[i] for i in live.issues)


# ---------------------------------------------------------------- práctica
def _practice_body(service, board) -> None:
    snap = service.snapshot(seconds=3.0)
    st.markdown(state_line(snap))
    st.caption('PROCEDENCIA: SIMULACIÓN — placa simulada; no es un sensor.')
    render_emg_controls(board, st, 'emglab_tut_sim', fragment=True)
    data, fs = snap['data'], snap['fs']
    if snap['state'] != 'transmitiendo' or not fs or data.shape[-1] < int(MIN_SECONDS * fs):
        return
    mains = MAINS_OPTIONS['60 Hz (México)']
    raw = data[0]
    clean = prepare(raw, fs, mains)
    t = np.round((np.arange(clean.size) - clean.size + 1) / fs, 3)
    st.line_chart(pd.DataFrame({'EMG (mV)': clean}, index=t), height=220)
    last = clean[-int(0.5 * fs):]
    cols = st.columns(2)
    rms = rms_mv(last, fs)
    cols[0].metric('RMS, último medio segundo', '—' if rms is None else f'{rms * 1000:.0f} µV')
    if EmgAnalyzer is not None:
        mdf = EmgAnalyzer(fs).analyze(clean[-int(2 * fs):]).median_frequency_hz
        cols[1].metric('Frecuencia mediana, últimos 2 s', f'{mdf:.0f} Hz')
    issues = emg_quality(raw, fs, mains)
    st.caption('Calidad: ' + ('✓ sin avisos' if not issues else ' '.join(ISSUE_TEXT[i] for i in issues)))


_fragment = getattr(st, 'fragment', None)
_practice_panel = _fragment(run_every=1.0)(_practice_body) if _fragment is not None else _practice_body


def _render_practice() -> None:
    practice = live_service.get_practice(EMG.key)
    service, board = practice.service, practice.board
    st.markdown(PRACTICE_INTRO)
    if not service.is_running:
        if st.button('▶ Empezar práctica', key='emglab_tut_start'):
            board.plug()
            service.start()
            st.rerun()
        st.caption(PRACTICE_SIM_NOTE)
        return
    if st.button('⏹ Terminar práctica', key='emglab_tut_stop'):
        service.stop()
        st.rerun()
    _practice_panel(service, board)
    if _fragment is None:
        st.button('🔄 Actualizar', key='emglab_tut_refresh')
    st.markdown('**Qué observar**\n\n' + '\n'.join(f'- {item}' for item in PRACTICE_OBSERVE))
    st.caption(PRACTICE_SIM_NOTE)


def render_emg_tutorial() -> None:
    render_sensor_tutorial(EMG, TUTORIAL_VIEW, 'emglab_tutorial', INTRO, ORIGIN_TABLE, 'MyoWare 2.0', _render_practice)
