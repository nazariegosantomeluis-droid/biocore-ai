"""PPG preprocessing utilities for pulse and SpO2 sensors.

2026-11-16: `pulse_rate` contaba las muestras por encima del promedio, no los latidos: daba 60·fs latidos por minuto
(3029 con una onda de 72 a 100 Hz). Ahora cuenta los picos sistólicos con el método de Elgendi et al. 2013
(`analysis.systolic_peaks`) sobre la señal filtrada, que se supone con el pulso hacia arriba.
"""

from typing import Dict, Tuple

import numpy as np
from scipy.signal import butter, filtfilt

from .analysis import MIN_INTERVALS, plausible_intervals, systolic_peaks


def preprocess_ppg(signal: np.ndarray, fs: float, lowcut: float = 0.5, highcut: float = 8.0) -> Tuple[np.ndarray, Dict[str, float]]:
    if signal.ndim != 1:
        signal = signal.flatten()

    nyquist = 0.5 * fs
    low = lowcut / nyquist
    high = highcut / nyquist
    b, a = butter(2, [low, high], btype='band')
    filtered = filtfilt(b, a, signal)

    intervals = plausible_intervals(systolic_peaks(filtered, fs), fs)
    metrics = {
        'fs': fs,
        'signal_std': float(np.std(filtered)),
        'pulse_rate': float(60.0 / np.median(intervals)) if intervals.size >= MIN_INTERVALS else float('nan'),
    }
    return filtered, metrics
