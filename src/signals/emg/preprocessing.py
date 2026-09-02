"""Basic EMG preprocessing for artifact reduction and amplitude normalization."""

from typing import Dict, Tuple

import numpy as np
from scipy.signal import butter, filtfilt


def preprocess_emg(signal: np.ndarray, fs: float, lowcut: float = 20.0, highcut: float = 450.0) -> Tuple[np.ndarray, Dict[str, float]]:
    if signal.ndim != 1:
        signal = signal.flatten()

    nyquist = 0.5 * fs
    low = lowcut / nyquist
    high = highcut / nyquist
    if high >= 1.0:
        high = 0.99
    b, a = butter(2, [low, high], btype='band')
    filtered = filtfilt(b, a, signal)
    rectified = np.abs(filtered)
    metrics = {
        'fs': fs,
        'signal_std': float(np.std(filtered)),
        'mean_rectified': float(np.mean(rectified)),
    }
    return filtered, metrics
