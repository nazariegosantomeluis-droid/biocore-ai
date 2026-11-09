"""Respiration signal support for breathing and chest sensors."""
from .preprocessing import preprocess_respiration

# Respiratory Lab components. Arco respiratorio, fase 3 (2026-11-07): se eliminó el `try/except ImportError`
# que silenciaba cualquier fallo de importación y dejaba el paquete a medias sin avisar.
from .respiratory_generator import (
    RespiratorySignalGenerator,
    RespiratoryPattern,
    ImpossibleParameters,
    demo_respiratory_patterns,
)
from .respiratory_analyzer import (
    RespiratoryAnalyzer,
    BreathDetection,
    RespiratoryAnalysis,
)

__all__ = [
    'preprocess_respiration',
    'RespiratorySignalGenerator',
    'RespiratoryPattern',
    'ImpossibleParameters',
    'RespiratoryAnalyzer',
    'BreathDetection',
    'RespiratoryAnalysis',
    'demo_respiratory_patterns',
]
