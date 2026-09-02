"""Respiratory academy: simulate respiratory waveforms and compute RR and patterns."""
from __future__ import annotations
from typing import Tuple
import numpy as np


def generate_respiration_wave(fs: int = 50, duration: float = 30.0, rr: float = 16.0) -> Tuple[np.ndarray, int]:
    t = np.linspace(0, duration, int(fs * duration), endpoint=False)
    signal = np.sin(2 * np.pi * (rr / 60.0) * t) * 0.5
    # add pattern variations (Cheyne-Stokes)
    if rr < 6:
        signal *= np.sin(2 * np.pi * 0.05 * t) * 0.6 + 0.4
    signal += np.random.normal(0, 0.02, size=signal.shape)
    return signal.astype(float), fs


def estimate_rr_from_resp(signal: np.ndarray, fs: int) -> float:
    from numpy.fft import rfftfreq, rfft
    if signal.size == 0:
        return 0.0
    freqs = rfftfreq(signal.size, 1.0 / fs)
    spec = np.abs(rfft(signal - np.mean(signal)))
    mask = (freqs >= 0.05) & (freqs <= 0.8)
    if not np.any(mask):
        return 0.0
    idx = mask.nonzero()[0][np.argmax(spec[mask])]
    return float(freqs[idx] * 60.0)
