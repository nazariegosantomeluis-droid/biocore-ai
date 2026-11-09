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

    # Arco respiratorio, fase 3 (2026-11-07): se enterró la "FR estimada" que vivía aquí (cruces por cero x 30 / n,
    # SIN fs: daba una FR errónea por el factor fs y nadie la usaba). La FR se mide en `RespiratoryAnalyzer`.
    metrics = {
        'fs': fs,
        'signal_std': float(np.std(filtered)),
    }
    return filtered, metrics
