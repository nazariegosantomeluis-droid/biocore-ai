"""EEG signal support for basic brainwave analysis."""
from .preprocessing import preprocess_eeg
from .eeg_generator import EegSignalGenerator, EegPattern
from .eeg_analyzer import (
    BAR_AROUSAL_THRESHOLD,
    BAR_BASELINE_RANGE,
    BAR_CITATION,
    DAR_CITATION,
    DAR_THRESHOLDS,
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
]
