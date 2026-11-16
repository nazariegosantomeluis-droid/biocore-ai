"""Servicios de adquisición que comparte el ECG Lab.

- `get_live_service()`: la placa real. Un solo servicio por proceso, porque un
  puerto serial no se puede abrir dos veces. Arranca la primera vez que alguien
  elige la fuente «Hardware ESP32 en vivo»; después solo lo detienen o lo
  reanudan los botones de la barra lateral.
- `get_practice()`: la práctica del tutorial, con la placa simulada. Nunca abre
  un puerto (con `simulator=` el servicio solo ve al simulador), siempre sale
  como SIMULACIÓN y no arranca hasta que la persona pulsa «Empezar práctica».

Los dos son `st.cache_resource`: BIOCORE corre en la computadora de cada quien,
así que «uno por proceso» es uno por persona.
"""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

from hardware.ecg_plugplay import AcquisitionConfig, BiocoreAnalyzer, ECGAcquisitionService, SimulatedECGDevice

FS = 250.0


@st.cache_resource
def get_live_service() -> ECGAcquisitionService:
    """Servicio de la placa real, ya buscando la placa en segundo plano."""
    return ECGAcquisitionService(AcquisitionConfig(), BiocoreAnalyzer(fs=FS)).start()


@dataclass
class Practice:
    """Servicio de práctica y la placa simulada que controla el tutorial."""

    service: ECGAcquisitionService
    device: SimulatedECGDevice


@st.cache_resource
def get_practice() -> Practice:
    device = SimulatedECGDevice(fs=FS)
    return Practice(ECGAcquisitionService(AcquisitionConfig(), BiocoreAnalyzer(fs=FS), simulator=device), device)
