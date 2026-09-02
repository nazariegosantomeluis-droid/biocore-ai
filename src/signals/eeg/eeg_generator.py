"""
EEG Signal Generator - Simulated brainwave activity for Neuro Lab

Generates multi-channel EEG with clinical patterns:
- Alpha (8-12 Hz)
- Beta (13-30 Hz)
- Theta (4-7 Hz)
- Delta (0.5-3 Hz)
- Sleep spindles
- Seizure-like spikes
- Blink/artifact noise
"""

import numpy as np
from dataclasses import dataclass
from typing import Dict, Tuple, List


@dataclass
class EegPattern:
    pattern_type: str = "alpha"
    duration: float = 20.0
    fs: float = 256.0
    amplitude: float = 40.0
    noise_level: float = 0.25
    seizure_frequency: float = 6.0
    blink_rate: float = 0.5
    channels: int = 4


class EegSignalGenerator:
    """Generate simulated EEG activity for educational neuro lab."""

    def __init__(self, sampling_rate: float = 256.0):
        self.fs = sampling_rate
        self.dt = 1.0 / sampling_rate

    def generate_eeg(self, params: EegPattern) -> Tuple[Dict[str, np.ndarray], np.ndarray]:
        n_samples = int(params.duration * self.fs)
        time = np.arange(n_samples) * self.dt
        leads = ['Fp1', 'Fp2', 'C3', 'C4'][: params.channels]
        eeg = {lead: self._generate_channel(time, params, i) for i, lead in enumerate(leads)}
        eeg['time'] = time
        return eeg, time

    def _generate_channel(self, time: np.ndarray, params: EegPattern, channel_index: int) -> np.ndarray:
        base = np.zeros_like(time)
        if params.pattern_type == 'alpha':
            base = self._band_signal(time, 10.0, params.amplitude * 0.8)
        elif params.pattern_type == 'beta':
            base = self._band_signal(time, 20.0, params.amplitude * 0.6)
        elif params.pattern_type == 'theta':
            base = self._band_signal(time, 5.5, params.amplitude * 1.0)
        elif params.pattern_type == 'delta':
            base = self._band_signal(time, 1.5, params.amplitude * 1.2)
        elif params.pattern_type == 'sleep_spindle':
            base = self._band_signal(time, 10.5, params.amplitude * 0.7)
            base += self._spindle_bursts(time)
        elif params.pattern_type == 'seizure':
            base = self._band_signal(time, 6.0, params.amplitude * 1.0)
            base += self._seizure_spikes(time, params.seizure_frequency)
        elif params.pattern_type == 'artifact':
            base = self._band_signal(time, 10.0, params.amplitude * 0.5)
            base += self._blink_artifacts(time, params.blink_rate)
        else:
            base = self._band_signal(time, 10.0, params.amplitude * 0.8)

        noise = np.random.normal(0, params.amplitude * params.noise_level, len(time))
        return base + noise

    def _band_signal(self, time: np.ndarray, center_hz: float, amplitude: float) -> np.ndarray:
        phase = 2 * np.pi * center_hz * time
        return amplitude * np.sin(phase) * np.exp(-time / (len(time) * self.dt * 2))

    def _seizure_spikes(self, time: np.ndarray, frequency: float) -> np.ndarray:
        spikes = np.zeros_like(time)
        period = int(self.fs / frequency)
        for idx in range(0, len(time), max(1, period)):
            width = int(self.fs * 0.02)
            end = min(idx + width, len(time))
            spikes[idx:end] += np.linspace(0, 70.0, end - idx)
        return spikes

    def _spindle_bursts(self, time: np.ndarray) -> np.ndarray:
        bursts = np.zeros_like(time)
        for start in range(0, len(time), int(self.fs * 3.0)):
            end = min(start + int(self.fs * 0.5), len(time))
            bursts[start:end] += 30.0 * np.sin(2 * np.pi * 12.0 * time[start:end])
        return bursts

    def _blink_artifacts(self, time: np.ndarray, rate: float) -> np.ndarray:
        artifacts = np.zeros_like(time)
        interval = int(self.fs / max(rate, 0.1))
        for start in range(0, len(time), interval):
            width = int(self.fs * 0.05)
            end = min(start + width, len(time))
            artifacts[start:end] += np.hanning(end - start) * 80.0
        return artifacts
