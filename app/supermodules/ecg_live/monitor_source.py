"""La fuente «Hardware ESP32 en vivo» de la pestaña Monitoreo del ECG Lab.

Reemplaza a la rama que usaba `ESP32SignalSource` (ver CHANGELOG, 2026-11-13).
Esa rama elegía el primer puerto con «com» en el nombre (también los de
Bluetooth) y, si se desconectaba el cable, `is_hardware_present()` seguía en
True: la pantalla decía SENSOR_REAL sobre un búfer congelado (fachada, Art. I).
Aquí la placa se busca sola en segundo plano, el puerto se cierra al
desconectarse y la procedencia es SENSOR_REAL solo mientras una placa real
está mandando datos.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

import numpy as np
import streamlit as st

from app.supermodules.ecg_live import service as live_service
from hardware.ecg_plugplay import latest_clean_segment

MIN_SECONDS = 4.0
TUTORIAL_TAB = 'Placa en vivo (tutorial)'


def render_live_source() -> Optional[Tuple[np.ndarray, float, Dict[str, str]]]:
    """Dibuja los controles de la placa en la barra lateral.

    Devuelve (señal en mV, fs, metadata) con el tramo limpio más reciente (de 4 a
    10 s, sin NaN: `validate_signal` rechaza la señal entera con uno solo), o None
    mientras no lo haya; con None la página cae a la demo, como con las demás
    fuentes. «demo» en la etiqueta de una placa que se declara simulador hace que
    nunca escriba la FC al gemelo, igual que la fuente Demo.
    """
    servicio = live_service.get_live_service()
    if servicio.is_running and st.sidebar.button('⏹ Soltar el puerto (para usar Thonny)',
                                                 key='ecglab_monitor_pp_stop'):
        servicio.stop()
        st.rerun()
    if not servicio.is_running and st.sidebar.button('▶ Buscar la placa', key='ecglab_monitor_pp_start'):
        servicio.start()
        st.rerun()
    st.sidebar.button('🔄 Leer los últimos segundos', key='ecglab_monitor_pp_refresh')
    st.sidebar.caption(f'¿Primera vez con la placa? Abre la pestaña «{TUTORIAL_TAB}».')

    snap = servicio.snapshot()
    limpia, motivo = latest_clean_segment(snap, min_seconds=MIN_SECONDS)
    if snap['state'] == 'conectado':
        st.sidebar.caption(snap['message'])
    elif snap['warnings']:
        st.sidebar.warning('Último aviso: ' + snap['warnings'][-1])
    if limpia is None:
        st.sidebar.info(motivo)
        return None
    if snap['provenance'] == 'SENSOR_REAL':
        st.sidebar.success('🟢 PROCEDENCIA: SENSOR_REAL — placa de ECG mandando datos ahora mismo.')
        metadata = {'source': f"ESP32 + AD8232 en {snap['port']} (SENSOR_REAL)"}
    else:
        st.sidebar.warning('🟡 PROCEDENCIA: SIMULACIÓN — la placa se declaró simulador; no es un sensor.')
        metadata = {'source': 'ESP32 simulado (demo, SIMULACIÓN)'}
    st.sidebar.caption('Una derivación, filtro de monitoreo de 0.5 a 40 Hz y mV aproximados: sirve para ritmo y '
                       'frecuencia, no para el ST ni para amplitudes. Detalles en el tutorial.')
    return limpia, float(snap['fs']), metadata
