"""EEG signal support for basic brainwave analysis.

NOTA (Arco 2C/2D): este `__init__.py` deliberadamente NO reexporta nada de
`spectral_model.py` (chi aperiódico) -- ese módulo importa `fooof`, una
dependencia que Arco 2B/2C mantienen desacoplada de `eeg_analyzer.py`/
`eeg_generator.py` a propósito (ver `test_spectral_model_import_surface_
matches_arco_2c_wiring`). Reexportarlo aquí forzaría esa dependencia sobre
CUALQUIER importador de `src.signals.eeg` (el paquete completo), incluso
uno que solo necesite el motor Welch -- rompería el aislamiento. Los
consumidores de chi (`builder.py`, `page_content.py` del EEG Lab,
`ups_body_visual.py`) importan `spectral_model` directamente."""
from .preprocessing import preprocess_eeg
from .eeg_generator import EegSignalGenerator, EegPattern
from .eeg_analyzer import (
    ARTIFACT_GRADIENT_THRESHOLD_UV_PER_S,
    ARTIFACT_WINDOW_S,
    BAR_AROUSAL_THRESHOLD,
    BAR_BASELINE_RANGE,
    BAR_CITATION,
    DAR_CITATION,
    DAR_THRESHOLDS,
    MIN_CLEAN_EEG_DURATION_S,
    TBR_CITATION,
    TBR_THRESHOLDS,
    EegAnalysis,
    EegAnalyzer,
    beta_alpha_ratio,
    classify_dar,
    classify_tbr,
    delta_alpha_ratio,
    theta_beta_ratio,
)

__all__ = [
    'preprocess_eeg', 'EegSignalGenerator', 'EegPattern', 'EegAnalyzer', 'EegAnalysis',
    'beta_alpha_ratio', 'BAR_AROUSAL_THRESHOLD', 'BAR_BASELINE_RANGE', 'BAR_CITATION',
    'delta_alpha_ratio', 'DAR_CITATION', 'DAR_THRESHOLDS', 'classify_dar',
    'theta_beta_ratio', 'TBR_CITATION', 'TBR_THRESHOLDS', 'classify_tbr',
    'ARTIFACT_WINDOW_S', 'ARTIFACT_GRADIENT_THRESHOLD_UV_PER_S', 'MIN_CLEAN_EEG_DURATION_S',
]
