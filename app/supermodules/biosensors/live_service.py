"""Servicios de la placa de sensores ESP32 (2026-11-14): uno para la placa real y uno para la práctica, por sensor.

Ambos son `st.cache_resource` (uno por proceso, es decir, por persona: BIOCORE corre en la computadora de cada
quien), como `app/supermodules/ecg_live/service.py`. La práctica usa la placa simulada por el mismo camino que la
real (lista de puertos → handshake → bloques), así que nunca abre un puerto de verdad.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import streamlit as st

from hardware.biosensors import SerialBioBackend, SimulatedBioBoard, get_sensor
from hardware.eeg_live import EegLiveService, LiveConfig

# La práctica reacciona rápido para que se vean los estados.
PRACTICE_CONFIG = LiveConfig(data_timeout_s=1.5, reconnect_after_s=4.0, retry_s=1.5)
# La temperatura llega una vez por segundo y se mira en minutos: búfer de 15 min, ventana de 30 s para estimar cuántas
# muestras llegan por segundo (con 5 s, una lectura de más o de menos parecería una pérdida de 20 %) y, en la
# práctica, 3 s sin lecturas antes de decir «sin datos».
SENSOR_CONFIG = {'temp': dict(buffer_seconds=900.0, rate_window_s=30.0)}
PRACTICE_SENSOR_CONFIG = {'temp': dict(buffer_seconds=900.0, rate_window_s=30.0, data_timeout_s=3.0,
                                       reconnect_after_s=8.0)}


def live_config(sensor_key: str, practice: bool = False) -> LiveConfig:
    base = PRACTICE_CONFIG if practice else LiveConfig()
    return replace(base, **(PRACTICE_SENSOR_CONFIG if practice else SENSOR_CONFIG).get(sensor_key, {}))


@dataclass
class BoardPractice:
    board: SimulatedBioBoard
    service: EegLiveService


def make_practice(sensor_key: str, board: SimulatedBioBoard = None) -> BoardPractice:
    sensor = get_sensor(sensor_key)
    board = board or SimulatedBioBoard(sensor_key)
    service = EegLiveService(
        sensor, lambda: SerialBioBackend(sensor, list_ports=board.list_ports, open_transport=board.open_transport,
                                         probe_timeout_s=1.5),
        live_config(sensor_key, practice=True), key=f'practica:{sensor_key}')
    return BoardPractice(board, service)


@st.cache_resource
def get_board_service(sensor_key: str) -> EegLiveService:
    sensor = get_sensor(sensor_key)
    return EegLiveService(sensor, lambda: SerialBioBackend(sensor), live_config(sensor_key), key=f'placa:{sensor_key}')


@st.cache_resource
def get_practice(sensor_key: str) -> BoardPractice:
    return make_practice(sensor_key)
