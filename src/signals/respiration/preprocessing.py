"""Respiration preprocessing for chest belt and airflow sensors."""

from typing import Dict, Tuple

import numpy as np
from scipy.signal import butter, filtfilt


def preprocess_respiration(signal: np.ndarray, fs: float, lowcut: float = 0.05, highcut: float = 2.0) -> Tuple[np.ndarray, Dict[str, float]]:
    if signal.ndim != 1:
        signal = signal.flatten()

    nyquist = 0.5 * fs
    low = lowcut / nyquist
    high = highcut / nyquist
    b, a = butter(2, [low, high], btype='band')
    filtered = filtfilt(b, a, signal)

    breath_cycles = np.sum(np.diff(np.signbit(filtered)) != 0)
    metrics = {
        'fs': fs,
        'signal_std': float(np.std(filtered)),
        'estimated_rr': float(breath_cycles * 30 / len(filtered)) if len(filtered) > 0 else float('nan'),
    }
    return filtered, metrics
