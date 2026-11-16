"""Servicios de la placa de sensores ESP32 (2026-11-14): uno para la placa real y uno para la práctica, por sensor.

Ambos son `st.cache_resource` (uno por proceso, es decir, por persona: BIOCORE corre en la computadora de cada
quien), como `app/supermodules/ecg_live/service.py`. La práctica usa la placa simulada por el mismo camino que la
real (lista de puertos → handshake → bloques), así que nunca abre un puerto de verdad.
"""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

from hardware.biosensors import SerialBioBackend, SimulatedBioBoard, get_sensor
from hardware.eeg_live import EegLiveService, LiveConfig

# La práctica reacciona rápido para que se vean los estados.
PRACTICE_CONFIG = LiveConfig(data_timeout_s=1.5, reconnect_after_s=4.0, retry_s=1.5)


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
        PRACTICE_CONFIG, key=f'practica:{sensor_key}')
    return BoardPractice(board, service)


@st.cache_resource
def get_board_service(sensor_key: str) -> EegLiveService:
    sensor = get_sensor(sensor_key)
    return EegLiveService(sensor, lambda: SerialBioBackend(sensor), key=f'placa:{sensor_key}')


@st.cache_resource
def get_practice(sensor_key: str) -> BoardPractice:
    return make_practice(sensor_key)
