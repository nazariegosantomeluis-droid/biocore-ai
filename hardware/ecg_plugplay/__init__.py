"""Módulo Plug & Play de ECG: detecta la placa, adquiere, limpia y entrega ventanas al modelo.

Uso mínimo:

    from hardware.ecg_plugplay import AcquisitionConfig, ECGAcquisitionService, ModelAnalyzer

    svc = ECGAcquisitionService(AcquisitionConfig(), ModelAnalyzer(MiClaseML(), 'procesar_ventana'),
                                on_state=print, on_result=print)
    svc.start()          # busca la placa en segundo plano; no bloquea
    ...
    svc.stop()

Ver README.md para el protocolo, la conexión de la placa y la integración con BIOCORE.
"""

from .config import KNOWN_USB_IDS, AcquisitionConfig, QualityHeuristics
from .inference import (BiocoreAnalyzer, CompositeAnalyzer, ECGWindow, InferenceBridge, ModelAnalyzer,
                        WindowResult)
from .ports import PortError, PortInfo
from .preprocessing import (FLAG_INTERPOLATED, FLAG_LEADOFF, FLAG_MISSING, FLAG_SATURATED, FLAG_SETTLING,
                            WindowQuality)
from .service import ConnectionState, ECGAcquisitionService, SignalChunk, StatusEvent, latest_clean_segment
from .simulator import SimulatedECGDevice

__all__ = [
    'AcquisitionConfig', 'QualityHeuristics', 'KNOWN_USB_IDS',
    'ECGAcquisitionService', 'ConnectionState', 'StatusEvent', 'SignalChunk', 'latest_clean_segment',
    'ECGWindow', 'WindowResult', 'WindowQuality', 'InferenceBridge',
    'ModelAnalyzer', 'BiocoreAnalyzer', 'CompositeAnalyzer',
    'SimulatedECGDevice', 'PortInfo', 'PortError',
    'FLAG_LEADOFF', 'FLAG_SATURATED', 'FLAG_MISSING', 'FLAG_INTERPOLATED', 'FLAG_SETTLING',
]
