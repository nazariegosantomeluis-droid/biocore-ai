"""EEG signal support for basic brainwave analysis."""
from .preprocessing import preprocess_eeg
from .eeg_generator import EegSignalGenerator, EegPattern
from .eeg_analyzer import EegAnalyzer, EegAnalysis

__all__ = ['preprocess_eeg', 'EegSignalGenerator', 'EegPattern', 'EegAnalyzer', 'EegAnalysis']
