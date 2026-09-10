"""EMG signal support: preprocessing + activation/fatigue analysis."""
from .preprocessing import preprocess_emg
from .emg_analyzer import (
    EmgAnalysis,
    EmgAnalyzer,
    MDF_BASELINE_HZ,
    MDF_SPAN_HZ,
    fatigue_index_from_mdf,
    median_frequency,
)

__all__ = [
    'preprocess_emg',
    'EmgAnalyzer', 'EmgAnalysis',
    'median_frequency', 'fatigue_index_from_mdf',
    'MDF_BASELINE_HZ', 'MDF_SPAN_HZ',
]
