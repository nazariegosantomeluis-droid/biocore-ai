"""Neuro academy: EEG educational helpers and bandpower computations."""
from __future__ import annotations
from typing import Tuple, Dict
import numpy as np


def band_powers(eeg: np.ndarray, fs: int) -> Dict[str, float]:
    """Compute relative band powers (Delta/Theta/Alpha/Beta/Gamma) using FFT."""
    n = eeg.size
    if n == 0:
        return {k: 0.0 for k in ('delta','theta','alpha','beta','gamma')}
    freqs = np.fft.rfftfreq(n, 1.0 / fs)
    spec = np.abs(np.fft.rfft(eeg - np.mean(eeg)))
    bands = {
        'delta': (0.5, 4),
        'theta': (4, 8),
        'alpha': (8, 13),
        'beta': (13, 30),
        'gamma': (30, 50),
    }
    total = spec.sum() + 1e-9
    out = {}
    for name, (lo, hi) in bands.items():
        mask = (freqs >= lo) & (freqs < hi)
        out[name] = float(spec[mask].sum() / total)
    return out


def example_eeg_patterns(fs: int = 100, duration: float = 10.0) -> Dict[str, Tuple[np.ndarray,int]]:
    t = np.linspace(0, duration, int(fs * duration), endpoint=False)
    patterns = {
        'sleep_delta': (0.5 * np.sin(2 * np.pi * 1.5 * t), fs),
        'alpha_relax': (0.3 * np.sin(2 * np.pi * 10 * t), fs),
        'beta_alert': (0.2 * np.sin(2 * np.pi * 20 * t), fs),
    }
    return patterns
