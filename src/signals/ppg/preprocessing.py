"""PPG preprocessing utilities for pulse and SpO2 sensors."""

from typing import Dict, Tuple

import numpy as np
from scipy.signal import butter, filtfilt


def preprocess_ppg(signal: np.ndarray, fs: float, lowcut: float = 0.5, highcut: float = 8.0) -> Tuple[np.ndarray, Dict[str, float]]:
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
        'pulse_rate': float(60.0 / np.mean(np.diff(np.where(filtered > np.mean(filtered))[0] / fs))) if np.count_nonzero(filtered > np.mean(filtered)) > 2 else float('nan'),
    }
    return filtered, metrics
