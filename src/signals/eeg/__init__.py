"""EEG signal support for basic brainwave analysis."""
from .preprocessing import preprocess_eeg
from .eeg_generator import EegSignalGenerator, EegPattern
from .eeg_analyzer import (
    BAR_AROUSAL_THRESHOLD,
    BAR_BASELINE_RANGE,
    BAR_CITATION,
    EegAnalysis,
    EegAnalyzer,
    beta_alpha_ratio,
)

__all__ = [
    'preprocess_eeg', 'EegSignalGenerator', 'EegPattern', 'EegAnalyzer', 'EegAnalysis',
    'beta_alpha_ratio', 'BAR_AROUSAL_THRESHOLD', 'BAR_BASELINE_RANGE', 'BAR_CITATION',
]
