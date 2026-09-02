"""Feature extraction tools for ECG signals."""

from typing import Dict

import numpy as np
from scipy.signal import find_peaks


def extract_ecg_features(signal: np.ndarray, fs: float) -> Dict[str, float]:
    """Extract basic ECG features for clinical analysis."""
    if signal.ndim != 1:
        signal = signal.flatten()

    peaks, properties = find_peaks(signal, distance=int(fs*0.3), height=np.mean(signal) + 0.35 * np.std(signal))
    rr_intervals = np.diff(peaks) / fs if len(peaks) > 1 else np.array([])
    bpm = float(60.0 / np.mean(rr_intervals)) if rr_intervals.size > 0 else np.nan

    features = {
        'bpm': bpm,
        'num_beats': int(peaks.size),
        'mean_rr': float(np.mean(rr_intervals)) if rr_intervals.size > 0 else np.nan,
        'sdnn': float(np.std(rr_intervals)) if rr_intervals.size > 0 else np.nan,
        'qt_estimate': float(np.median(rr_intervals) * 0.36) if rr_intervals.size > 0 else np.nan,
        'signal_std': float(np.std(signal)),
        'peak_prominence': float(np.mean(properties['prominences'])) if properties.get('prominences') is not None and properties['prominences'].size > 0 else np.nan,
    }
    return features
