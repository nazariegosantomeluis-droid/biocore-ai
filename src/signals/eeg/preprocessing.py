"""Basic EEG preprocessing for simple clinical-simulated education."""

from typing import Dict, Tuple

import numpy as np
from scipy.signal import butter, filtfilt


def preprocess_eeg(signal: np.ndarray, fs: float, lowcut: float = 0.5, highcut: float = 40.0) -> Tuple[np.ndarray, Dict[str, float]]:
    if signal.ndim != 1:
        signal = signal.flatten()

    nyquist = 0.5 * fs
    low = lowcut / nyquist
    high = highcut / nyquist
    b, a = butter(2, [low, high], btype='band')
    filtered = filtfilt(b, a, signal)

    metrics = {
        'fs': fs,
        'signal_std': float(np.std(filtered)),
        'duration_sec': len(filtered) / fs,
    }
    return filtered, metrics
