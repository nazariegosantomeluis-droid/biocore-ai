"""ECG preprocessing utilities for real-world clinical data."""

from typing import Dict, Tuple

import numpy as np
from scipy.signal import butter, filtfilt, detrend


def preprocess_ecg(signal: np.ndarray, fs: float, lowcut: float = 0.5, highcut: float = 40.0) -> Tuple[np.ndarray, Dict[str, float]]:
    """Filter ECG signal and remove baseline wander."""
    if signal.ndim != 1:
        signal = signal.flatten()

    # Detrend slow baseline drift
    detrended = detrend(signal)

    # Design Butterworth bandpass filter
    nyquist = 0.5 * fs
    low = lowcut / nyquist
    high = highcut / nyquist
    if not 0 < low < high < 1:
        raise ValueError('Invalid ECG filter band')

    b, a = butter(2, [low, high], btype='band')
    filtered = filtfilt(b, a, detrended)

    metadata = {
        'fs': fs,
        'lowcut': lowcut,
        'highcut': highcut,
        'duration_sec': len(filtered) / fs,
        'signal_mean': float(np.mean(filtered)),
        'signal_std': float(np.std(filtered)),
    }
    return filtered, metadata
