"""Servicios de EEG en vivo que comparte el EEG Neuro Lab (2026-11-14).

- `get_manager()`: el dispositivo de verdad (o el tablero sintético de BrainFlow, o un flujo LSL). Uno solo a
  la vez: un puerto serial o un equipo Bluetooth no se pueden abrir dos veces. Conectar otro dispositivo cierra
  el anterior.
- `get_practice()`: el simulador de práctica. Nunca abre un puerto. Lo usan la práctica del tutorial y la
  fuente «Simulador de práctica» de la pestaña Clínica, así los controles de un lado mueven la señal del otro.

Los dos son `st.cache_resource`: BIOCORE corre en la computadora de cada quien, así que «uno por proceso» es
uno por persona (mismo criterio que `app/supermodules/ecg_live/service.py`).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Callable, Mapping, Optional

import streamlit as st

from hardware.eeg_live import (BrainFlowBackend, EegDevice, EegLiveService, LiveConfig, LslBackend, LslStreamChoice,
                               SimulatedEegDevice, SimulatorBackend, get_device)

# La práctica reacciona rápido para que se vean los estados: «sin datos» al segundo y medio de quitar el cable.
PRACTICE_CONFIG = LiveConfig(data_timeout_s=1.5, reconnect_after_s=4.0, retry_s=1.5)


def connection_key(device: EegDevice, params: Optional[Mapping[str, str]] = None,
                   lsl_choice: Optional[LslStreamChoice] = None) -> str:
    parts = [device.key] + [f'{k}={v}' for k, v in sorted((params or {}).items()) if v]
    if lsl_choice is not None:
        parts.append(lsl_choice.key)
    return '|'.join(parts)


class LiveManager:
    """Guarda el único servicio de hardware y lo cambia cuando se pide otro dispositivo."""

    def __init__(self) -> None:
        self.service: Optional[EegLiveService] = None
        self._lock = threading.Lock()

    def connect(self, device: EegDevice, params: Optional[Mapping[str, str]] = None,
                lsl_choice: Optional[LslStreamChoice] = None) -> EegLiveService:
        key = connection_key(device, params, lsl_choice)
        factory: Callable
        if device.backend == 'lsl':
            if lsl_choice is None:
                raise ValueError('Falta elegir el flujo LSL.')
            factory = lambda: LslBackend(lsl_choice)          # noqa: E731
        else:
            clean = dict(params or {})
            factory = lambda: BrainFlowBackend(device, clean)  # noqa: E731
        with self._lock:
            current = self.service
            if current is not None:
                if current.key == key and current.is_running:
                    return current
                current.stop()
            self.service = EegLiveService(device, factory, key=key).start()
            return self.service

    def disconnect(self) -> None:
        with self._lock:
            if self.service is not None:
                self.service.stop()


@dataclass
class Practice:
    device: SimulatedEegDevice
    service: EegLiveService


@st.cache_resource
def get_manager() -> LiveManager:
    return LiveManager()


@st.cache_resource
def get_practice() -> Practice:
    sim = SimulatedEegDevice(fs=250.0)
    service = EegLiveService(get_device('practica'), lambda: SimulatorBackend(sim), PRACTICE_CONFIG, key='practica')
    return Practice(sim, service)
