"""Fuente «sensor en vivo» genérica de la barra lateral, para cualquier sensor de la placa ESP32 (2026-11-14).

Dos modos: la placa real por USB (la busca sola en los puertos) o la práctica con la placa simulada. Muestra el
estado, el motivo cuando no hay señal, la procedencia y las muestras perdidas. Sin señal en vivo devuelve None y la
página lo dice: no hay señal de respaldo (Art. I).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, Optional

import numpy as np
import streamlit as st

from app.supermodules.biosensors import live_service
from hardware.biosensors import BioSensor
from hardware.eeg_live.devices import SENSOR_REAL, SIMULACION

MODES = ('Placa real (ESP32 por USB)', 'Práctica (placa simulada)')
MAINS_OPTIONS = {'60 Hz (México)': 60.0, '50 Hz (Europa)': 50.0, 'Sin filtro': None}
STATE_ICONS = {'transmitiendo': '🟢', 'conectando': '🟡', 'sin datos': '🟠', 'sin conexión': '🔴', 'detenido': '⚪'}
PROVENANCE_TEXT = {
    SENSOR_REAL: '🟢 PROCEDENCIA: SENSOR_REAL — {detail}, mandando datos ahora mismo.',
    SIMULACION: '🟡 PROCEDENCIA: SIMULACIÓN — {detail}; no es un sensor.',
}
LOSS_WARNING_FRACTION = 0.9


@dataclass
class BoardSignal:
    """Los últimos segundos de la placa, en unidades físicas, y de dónde salen."""

    data: np.ndarray                 # (canales, muestras)
    fs: float
    label: str
    provenance: str
    detail: str
    mains_hz: Optional[float]
    status: Dict[str, object] = field(default_factory=dict)


def state_line(snap) -> str:
    return f"{STATE_ICONS.get(snap['state'], '⚪')} **{snap['state'].capitalize()}** — {snap['message']}"


def render_board_source(sensor: BioSensor, duration_s: float, prefix: str, min_seconds: float,
                        controls: Optional[Callable] = None, tutorial_hint: str = '') -> Optional[BoardSignal]:
    """Controles en la barra lateral. Devuelve los últimos `duration_s` (desde `min_seconds`) o None."""
    sb = st.sidebar
    sb.markdown('### Sensor en vivo')
    sb.caption(sensor.connection + (f' {tutorial_hint}' if tutorial_hint else ''))
    practice = sb.radio('Placa', MODES, key=f'{prefix}_mode') == MODES[1]
    if practice:
        prac = live_service.get_practice(sensor.key)
        service = prac.service
        if controls is not None:
            controls(prac.board, sb, f'{prefix}_sim')
    else:
        service = live_service.get_board_service(sensor.key)
    mains_hz = MAINS_OPTIONS[sb.radio('Filtro de la red eléctrica', list(MAINS_OPTIONS), key=f'{prefix}_mains',
                                      help='Quita el zumbido de los aparatos y contactos cercanos (filtro notch).')]
    if service.is_running:
        if sb.button('⏹ Soltar el puerto' if not practice else '⏹ Detener la práctica', key=f'{prefix}_stop'):
            service.stop()
            st.rerun()
    elif sb.button('▶ Buscar la placa' if not practice else '▶ Conectar la placa simulada', key=f'{prefix}_start'):
        service.start()
        st.rerun()
    sb.button('🔄 Leer los últimos segundos', key=f'{prefix}_refresh')

    snap = service.snapshot(seconds=duration_s)
    if not service.is_running and snap['state'] == 'detenido':
        st.info('Sensor en vivo: pulsa «▶ Buscar la placa» en la barra lateral (o elige la práctica). Sin placa no hay '
                'señal que analizar: no se usa una señal de respaldo.')
        return None
    sb.markdown(state_line(snap))
    if snap['state'] != 'transmitiendo':
        if snap['warnings']:
            sb.warning('Último aviso: ' + snap['warnings'][-1])
        st.info(f"Sin señal en vivo ({snap['state']}): {snap['message']} No se analiza nada mientras tanto.")
        return None
    if snap['seconds_available'] < min_seconds:
        st.info(f"Juntando señal: {snap['seconds_available']:.0f} de {min_seconds:.0f} s. Pulsa «🔄 Leer los últimos "
                "segundos» en un momento.")
        return None
    fs = float(snap['fs'])
    status = snap.get('backend_status') or {}
    lost = int(status.get('perdidas_en_el_cable', 0)) + int(status.get('perdidas_en_la_placa', 0))
    if lost:
        sb.warning(f'Se han perdido {lost} muestras (en el cable o porque la placa se atrasó). El análisis trata la '
                   'señal como continua.')
    eff = snap['effective_fs']
    if eff is not None and eff < LOSS_WARNING_FRACTION * fs:
        sb.warning(f'Llegan {eff:.0f} muestras por segundo de {fs:.0f}.')
    for aviso in status.get('avisos', []):
        sb.caption(f'La placa dice: {aviso}')
    provenance = snap['provenance']
    (sb.success if provenance == SENSOR_REAL else sb.warning)(PROVENANCE_TEXT[provenance].format(detail=snap['detail']))
    sb.caption('Unidades: ' + snap['unit_note'])
    label = f"{snap['detail']} ({'SENSOR_REAL' if provenance == SENSOR_REAL else 'SIMULACIÓN'})"
    return BoardSignal(snap['data'], fs, label, provenance, snap['detail'], mains_hz, status)
