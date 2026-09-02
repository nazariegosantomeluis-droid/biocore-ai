"""Respiration signal support for breathing and chest sensors."""
from .preprocessing import preprocess_respiration

# Phase 2: Respiratory Lab components
try:
    from .respiratory_generator import (
        RespiratorySignalGenerator,
        RespiratoryPattern,
        demo_respiratory_patterns
    )
    from .respiratory_analyzer import (
        RespiratoryAnalyzer,
        BreathDetection,
        RespiratoryAnalysis,
        create_respiratory_summary
    )
    
    __all__ = [
        'preprocess_respiration',
        'RespiratorySignalGenerator',
        'RespiratoryPattern',
        'RespiratoryAnalyzer',
        'BreathDetection',
        'RespiratoryAnalysis',
        'create_respiratory_summary',
        'demo_respiratory_patterns'
    ]
except ImportError:
    __all__ = ['preprocess_respiration']

