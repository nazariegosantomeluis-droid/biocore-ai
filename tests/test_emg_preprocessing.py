import numpy as np

from src.signals.emg.preprocessing import preprocess_emg
from app.main import compute_emg_median_frequency, compute_emg_fatigue_index


def test_preprocess_emg_returns_filtered_and_metrics():
    fs = 1000.0
    t = np.arange(0, 1.0, 1.0 / fs)
    # Simulate an EMG-like burst
    signal = 0.8 * np.random.randn(len(t)) * (0.5 + 0.5 * np.sin(2 * np.pi * 2 * t))
    filtered, metrics = preprocess_emg(signal, fs)
    assert isinstance(filtered, np.ndarray)
    assert 'mean_rectified' in metrics
    assert metrics['fs'] == fs


def test_median_frequency_and_fatigue_index():
    fs = 1000.0
    # create a signal centered at ~150 Hz
    t = np.arange(0, 1.0, 1.0 / fs)
    sig = np.sin(2 * np.pi * 150.0 * t) + 0.5 * np.random.randn(len(t))
    median = compute_emg_median_frequency(sig, fs)
    fatigue = compute_emg_fatigue_index(median)
    assert 0.0 <= median <= fs / 2
    assert 0.0 <= fatigue <= 100.0
