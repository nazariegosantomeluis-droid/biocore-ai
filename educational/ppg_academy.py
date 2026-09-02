"""PPG Academy: PPG signal generation and simple feature extraction.

Includes simple PPG waveform generator, HR and HRV estimators and perfusion
index proxy to be used in educational content and quizzes.
"""
from __future__ import annotations
from typing import Tuple, Dict, Any
import numpy as np


def generate_ppg_signal(fs: int = 100, duration: float = 30.0, hr: int = 70) -> Tuple[np.ndarray, int]:
    """Generate a pedagogical PPG-like waveform using sine harmonics and peaks."""
    t = np.linspace(0, duration, int(fs * duration), endpoint=False)
    base = 0.5 * (1 + np.sin(2 * np.pi * (hr / 60.0) * t))
    # add harmonics to shape the pulse
    base += 0.05 * np.sin(2 * np.pi * 2 * (hr / 60.0) * t)
    # respiration modulation
    base *= 1 + 0.02 * np.sin(2 * np.pi * 0.25 * t)
    base += np.random.normal(0, 0.01, size=base.shape)
    return base.astype(float), fs


def compute_hr_from_ppg(ppg: np.ndarray, fs: int) -> float:
    """Simple peak-based HR estimation from PPG."""
    if ppg.size == 0:
        return 0.0
    # naive peak detection
    threshold = np.mean(ppg) + 0.5 * np.std(ppg)
    peaks = []
    refractory = int(0.4 * fs)
    i = 1
    while i < ppg.size - 1:
        if ppg[i] > threshold and ppg[i] > ppg[i-1] and ppg[i] > ppg[i+1]:
            peaks.append(i)
            i += refractory
        else:
            i += 1
    if len(peaks) < 2:
        return 0.0
    rr = np.diff(peaks) / float(fs)
    hr = 60.0 / np.mean(rr)
    return float(hr)


def perfusion_index(ppg: np.ndarray) -> float:
    """Proxy of perfusion index: ratio between AC and DC components."""
    if ppg.size == 0:
        return 0.0
    dc = np.mean(ppg)
    ac = np.std(ppg)
    if dc == 0:
        return 0.0
    return float((ac / dc) * 100.0)


def respiratory_rate_from_ppg(ppg: np.ndarray, fs: int) -> float:
    """Very rough estimate of respiratory rate from low-frequency modulation."""
    if ppg.size == 0:
        return 0.0
    # bandpass and pick dominant low freq - placeholder using FFT
    n = ppg.size
    freqs = np.fft.rfftfreq(n, 1.0 / fs)
    spec = np.abs(np.fft.rfft(ppg - np.mean(ppg)))
    # typical respiratory band 0.1-0.5 Hz
    mask = (freqs >= 0.08) & (freqs <= 0.6)
    if not np.any(mask):
        return 0.0
    idx = np.argmax(spec[mask])
    resp_freq = freqs[mask][idx]
    return float(resp_freq * 60.0)


def compute_hrv_metrics(rr_intervals: np.ndarray) -> Dict[str, float]:
    """Compute simple time-domain HRV metrics from RR intervals in seconds."""
    out: Dict[str, float] = {}
    if rr_intervals.size == 0:
        return {'sdnn': 0.0, 'rmssd': 0.0}
    out['sdnn'] = float(np.std(rr_intervals))
    out['rmssd'] = float(np.sqrt(np.mean(np.diff(rr_intervals) ** 2)))
    return out
