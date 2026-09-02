"""ECG Academy: lessons, step-by-step assistant and arrhythmia simulator.

This module provides educational helpers for teaching ECG interpretation, simple
synthetic ECG generation for common rhythms, and a stepwise diagnostic assistant
that can be integrated into Streamlit lesson pages.

The implementations are intentionally compact and well-typed so they can be
expanded later with physiological models or imported signal libraries.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple, Any
import numpy as np


def lead_explanations() -> Dict[str, Dict[str, str]]:
    """Return textual explanation for each 12-lead ECG.

    Keys: 'I','II','III','aVR','aVL','aVF','V1'..'V6'
    Values include what is observed, wall represented, and typical arteries.
    """
    mapping: Dict[str, Dict[str, str]] = {
        'I': {'observes': 'Actividad eléctrica lateral izquierda', 'wall': 'Lateral', 'artery': 'Circunfleja (LCx)'},
        'II': {'observes': 'Actividad inferoposterior y ritmo', 'wall': 'Inferior', 'artery': 'Descendente posterior / RCA'},
        'III': {'observes': 'Apoya II para inferior', 'wall': 'Inferior', 'artery': 'RCA'},
        'aVR': {'observes': 'Véase inversión: referencia global', 'wall': 'No aplica', 'artery': 'No aplica'},
        'aVL': {'observes': 'Lateral alto', 'wall': 'Lateral', 'artery': 'LCx'},
        'aVF': {'observes': 'Inferior', 'wall': 'Inferior', 'artery': 'RCA'},
        'V1': {'observes': 'Septal / RV', 'wall': 'Septal', 'artery': 'DA (LAD)'},
        'V2': {'observes': 'Septal', 'wall': 'Septal', 'artery': 'DA (LAD)'},
        'V3': {'observes': 'Anterior', 'wall': 'Anterior', 'artery': 'LAD'},
        'V4': {'observes': 'Anterior/Septal', 'wall': 'Anterior', 'artery': 'LAD'},
        'V5': {'observes': 'Lateral', 'wall': 'Lateral', 'artery': 'LCx/LAD'},
        'V6': {'observes': 'Lateral', 'wall': 'Lateral', 'artery': 'LCx'},
    }
    return mapping


def generate_synthetic_ecg(rhythm: str = 'normal', fs: int = 250, duration: float = 10.0) -> Tuple[np.ndarray, int]:
    """Generate a simple synthetic ECG-like signal for teaching purposes.

    This is not a physiological simulator but provides waveforms that illustrate
    rate and rhythm differences for demos and quizzes.

    Returns (signal, fs).
    """
    t = np.linspace(0, duration, int(fs * duration), endpoint=False)
    # Base heartbeat frequency
    if rhythm == 'normal':
        hr = 70
    elif rhythm == 'tachycardia':
        hr = 140
    elif rhythm == 'bradycardia':
        hr = 45
    elif rhythm == 'afib':
        hr = 110
    elif rhythm == 'pvcs':
        hr = 75
    else:
        hr = 70

    # simple sinusoid as baseline
    signal = 0.5 * np.sin(2 * np.pi * (hr / 60.0) * t)

    # Add sharper QRS-like spikes
    qrs_rate = hr / 60.0
    spike_train = np.zeros_like(t)
    beat_times = np.arange(0, duration, 1.0 / qrs_rate)
    for bt in beat_times:
        idx = int(bt * fs)
        if 0 <= idx < spike_train.size:
            spike_train[idx : idx + max(1, int(0.02 * fs))] += np.hanning(max(1, int(0.02 * fs))) * 3.0

    # Add arrhythmia variability
    if rhythm == 'afib':
        jitter = np.random.normal(0, 0.1, size=signal.shape)
        signal += jitter
    elif rhythm == 'pvcs':
        # insert premature large spike occasionally
        for n, bt in enumerate(beat_times):
            if np.random.rand() < 0.1:
                idx = int(bt * fs)
                if idx + 5 < signal.size:
                    signal[idx:idx+5] -= 1.5

    ecg = signal + spike_train
    # small gaussian noise
    ecg += np.random.normal(0, 0.02, size=ecg.shape)
    return ecg.astype(float), fs


def simple_peak_detector(signal: np.ndarray, fs: int) -> np.ndarray:
    """Very small R-peak detector by threshold + refractory period for demos."""
    if signal.size == 0:
        return np.array([], dtype=int)
    thresh = np.mean(signal) + 0.6 * np.std(signal)
    refractory = int(0.25 * fs)
    peaks = []
    i = 1
    while i < signal.size - 1:
        if signal[i] > thresh and signal[i] > signal[i-1] and signal[i] > signal[i+1]:
            peaks.append(i)
            i += refractory
        else:
            i += 1
    return np.array(peaks, dtype=int)


def step_by_step_assistant(signal: np.ndarray, fs: int) -> Dict[str, Any]:
    """Run a sequence of simple checks and return teaching hints for each step.

    Steps implemented: HR, rhythm regularity, simple QRS width proxy, QT proxy.
    """
    res: Dict[str, Any] = {}
    peaks = simple_peak_detector(signal, fs)
    if peaks.size >= 2:
        rr_intervals = np.diff(peaks) / float(fs)
        hr = 60.0 / np.mean(rr_intervals) if rr_intervals.size else 0.0
        res['heart_rate_bpm'] = float(round(hr, 1))
        res['rhythm_regular'] = float(np.std(rr_intervals)) < 0.08
    else:
        res['heart_rate_bpm'] = None
        res['rhythm_regular'] = None

    # QRS proxy: short local width estimation at peaks
    qrs_estimates = []
    for p in peaks:
        left = max(0, p - int(0.03 * fs))
        right = min(len(signal) - 1, p + int(0.03 * fs))
        qrs_estimates.append(np.sum(np.abs(signal[left:right])))
    res['qrs_proxy'] = float(np.mean(qrs_estimates)) if qrs_estimates else None

    # QT proxy: very rough duration estimation based on envelope (placeholder)
    res['qt_proxy_ms'] = None

    # Diagnostic hint (very simple)
    if res.get('heart_rate_bpm'):
        hr = res['heart_rate_bpm']
        if hr > 100:
            res['teaching_hint'] = 'Taquicardia: revisa ritmo sinusal vs taquicardia supraventricular.'
        elif hr < 60:
            res['teaching_hint'] = 'Bradicardia: considera causas fisiológicas o bloqueo AV.'
        else:
            res['teaching_hint'] = 'Frecuencia en rango normal.'
    else:
        res['teaching_hint'] = 'Se necesitan más datos para estimar frecuencia.'

    return res


def arrhythmia_examples(fs: int = 250, duration: float = 10.0) -> Dict[str, Dict[str, Any]]:
    """Return a set of labelled synthetic arrhythmia examples for training/demo."""
    rhythms = [
        ('normal', 'Ritmo sinusal normal'),
        ('tachycardia', 'Taquicardia sinusal'),
        ('bradycardia', 'Bradicardia'),
        ('afib', 'Fibrilación auricular'),
        ('pvcs', 'Extrasístoles ventriculares (PVC)'),
    ]
    out: Dict[str, Dict[str, Any]] = {}
    for key, descr in rhythms:
        sig, sfs = generate_synthetic_ecg(rhythm=key, fs=fs, duration=duration)
        out[key] = {'signal': sig, 'fs': sfs, 'description': descr}
    return out
