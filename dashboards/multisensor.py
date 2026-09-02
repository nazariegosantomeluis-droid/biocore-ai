"""Multisensorial biomedical platform for integrated physiological analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any

import numpy as np


@dataclass
class BiosignalChannel:
    """Single biosignal channel with metadata."""
    name: str
    signal: np.ndarray
    fs: float
    unit: str
    signal_type: str  # 'ecg', 'ppg', 'spo2', 'respiration', 'temperature', 'bp_sys', 'bp_dia', 'emg', 'eeg'
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def duration(self) -> float:
        """Duration in seconds."""
        return len(self.signal) / self.fs if self.fs > 0 else 0
    
    def resample_to(self, target_fs: float) -> BiosignalChannel:
        """Resample signal to target frequency."""
        from scipy import signal as sp_signal
        
        if target_fs == self.fs:
            return BiosignalChannel(
                name=self.name,
                signal=self.signal.copy(),
                fs=target_fs,
                unit=self.unit,
                signal_type=self.signal_type,
                metadata=self.metadata.copy()
            )
        
        num_samples = int(len(self.signal) * target_fs / self.fs)
        resampled = sp_signal.resample(self.signal, num_samples)
        
        return BiosignalChannel(
            name=self.name,
            signal=resampled,
            fs=target_fs,
            unit=self.unit,
            signal_type=self.signal_type,
            metadata={**self.metadata, 'resampled': True}
        )


class MultisensoralRecord:
    """Container for multiple simultaneous biosignals."""
    
    def __init__(self, channels: List[BiosignalChannel], patient_id: Optional[str] = None):
        """
        Initialize multisensorial record.
        
        Parameters
        ----------
        channels : List[BiosignalChannel]
            List of biosignal channels
        patient_id : str, optional
            Patient identifier
        """
        self.channels = {ch.name: ch for ch in channels}
        self.patient_id = patient_id or 'anonymous'
        self.created_at = None
        self._validate_synchronization()
    
    def _validate_synchronization(self):
        """Verify all signals are synchronized in time."""
        if len(self.channels) < 2:
            return
        
        durations = [ch.duration for ch in self.channels.values()]
        if not np.allclose(durations, durations[0], rtol=0.01):
            max_dur = max(durations)
            for name, ch in self.channels.items():
                if ch.duration < max_dur:
                    max_samples = int(max_dur * ch.fs)
                    ch.signal = np.pad(ch.signal, (0, max_samples - len(ch.signal)))
    
    def get_channel(self, name: str) -> BiosignalChannel:
        """Get a channel by name."""
        return self.channels.get(name)
    
    def add_channel(self, channel: BiosignalChannel):
        """Add a new channel."""
        self.channels[channel.name] = channel
        self._validate_synchronization()
    
    def synchronize_to_fs(self, target_fs: float):
        """Resample all channels to common frequency."""
        for name, ch in self.channels.items():
            self.channels[name] = ch.resample_to(target_fs)
    
    def get_signal_names(self) -> List[str]:
        """Get list of available signals."""
        return list(self.channels.keys())
    
    def get_signals_by_type(self, signal_type: str) -> List[BiosignalChannel]:
        """Get all channels of a specific type."""
        return [ch for ch in self.channels.values() if ch.signal_type == signal_type]
    
    def correlate_channels(self, ch1: str, ch2: str) -> Tuple[float, float]:
        """
        Compute correlation between two channels.
        
        Returns
        -------
        correlation : float
            Pearson correlation coefficient
        lag : float
            Time lag in seconds where correlation is maximum
        """
        signal1 = self.channels[ch1].signal
        signal2 = self.channels[ch2].signal
        
        if len(signal1) != len(signal2):
            min_len = min(len(signal1), len(signal2))
            signal1 = signal1[:min_len]
            signal2 = signal2[:min_len]
        
        correlation = float(np.corrcoef(signal1, signal2)[0, 1])
        
        cross_corr = np.correlate(signal1 - np.mean(signal1), signal2 - np.mean(signal2), mode='full')
        lag_idx = np.argmax(np.abs(cross_corr)) - len(signal1) + 1
        fs1 = self.channels[ch1].fs
        lag = lag_idx / fs1 if fs1 > 0 else 0
        
        return correlation, lag
    
    def compute_physiological_indices(self) -> Dict[str, float]:
        """
        Compute integrated physiological metrics.
        
        Computa índices compuestos que combinan múltiples señales.
        """
        indices = {}
        
        ecg_signals = self.get_signals_by_type('ecg')
        if ecg_signals:
            ecg = ecg_signals[0]
            from scipy.signal import find_peaks
            # `height` añadido (2026-08-20, Capa 2 Fase 2.2): sin umbral de
            # altura, find_peaks contaba máximos de ruido, no picos R reales
            # -- verificado por ejecución directa: sobre una señal sintética,
            # detectaba el mismo conteo de picos (y el mismo HR estimado,
            # ~178bpm) sin importar la frecuencia cardíaca objetivo. Mismo
            # patrón de umbral que ya usa el resto del repo (p.ej.
            # `src/signals/ecg/feature_extraction.py`,
            # `src/clinical/ecg_interpreter.py`): media + 0.3*desviación.
            peaks, _ = find_peaks(
                ecg.signal, distance=int(0.3 * ecg.fs),
                height=np.mean(ecg.signal) + 0.3 * np.std(ecg.signal),
            )
            if len(peaks) > 1:
                rr_intervals = np.diff(peaks) / ecg.fs
                indices['heart_rate'] = 60.0 / np.mean(rr_intervals) if len(rr_intervals) > 0 else 0
                indices['heart_rate_variability'] = float(np.std(rr_intervals))
        
        spo2_signals = self.get_signals_by_type('spo2')
        if spo2_signals:
            spo2 = spo2_signals[0]
            indices['spo2_mean'] = float(np.mean(spo2.signal))
            indices['spo2_min'] = float(np.min(spo2.signal))
            indices['spo2_variability'] = float(np.std(spo2.signal))
        
        temp_signals = self.get_signals_by_type('temperature')
        if temp_signals:
            temp = temp_signals[0]
            indices['temperature'] = float(np.mean(temp.signal))
        
        resp_signals = self.get_signals_by_type('respiration')
        if resp_signals:
            resp = resp_signals[0]
            indices['respiration_rate'] = float(np.mean(resp.signal))
        
        return indices
    
    def health_score(self) -> Dict[str, float]:
        """
        Compute integrated health score combining multiple signals.
        
        Returns
        -------
        dict
            Scores: 'overall', 'cardiovascular', 'autonomic', 'oxygenation', 'recovery'
        """
        indices = self.compute_physiological_indices()
        scores = {
            'cardiovascular': 50.0,
            'autonomic': 50.0,
            'oxygenation': 50.0,
            'recovery': 50.0,
            'overall': 50.0
        }
        
        if 'heart_rate' in indices:
            hr = indices['heart_rate']
            if 60 <= hr <= 100:
                scores['cardiovascular'] = 100
            elif 50 <= hr < 60 or 100 < hr <= 120:
                scores['cardiovascular'] = 80
            else:
                scores['cardiovascular'] = max(20, 100 - abs(hr - 70) / 2)
        
        if 'heart_rate_variability' in indices:
            hrv = indices['heart_rate_variability']
            if hrv > 0.05:
                scores['autonomic'] = min(100, 50 + hrv * 1000)
            else:
                scores['autonomic'] = max(20, 50 - (0.05 - hrv) * 1000)
        
        if 'spo2_mean' in indices:
            spo2 = indices['spo2_mean']
            if spo2 >= 95:
                scores['oxygenation'] = 100
            elif spo2 >= 90:
                scores['oxygenation'] = 80
            else:
                scores['oxygenation'] = max(20, 100 - (95 - spo2) * 10)
        
        scores['overall'] = np.mean([
            scores['cardiovascular'],
            scores['autonomic'],
            scores['oxygenation'],
            scores['recovery']
        ])
        
        return scores
    
    def detect_physiological_inconsistencies(self) -> List[str]:
        """Detect inconsistencies or anomalies in multisensorial data."""
        anomalies = []
        indices = self.compute_physiological_indices()
        
        if 'heart_rate' in indices and 'respiration_rate' in indices:
            hr = indices['heart_rate']
            rr = indices['respiration_rate']
            if hr > 0 and rr > 0:
                if hr / rr < 2 or hr / rr > 8:
                    anomalies.append('Abnormal HR/RR ratio')
        
        if 'spo2_mean' in indices and 'heart_rate' in indices:
            spo2 = indices['spo2_mean']
            hr = indices['heart_rate']
            if spo2 < 90 and hr > 100:
                anomalies.append('Hypoxemia with tachycardia')
        
        if 'temperature' in indices:
            temp = indices['temperature']
            if temp > 38.5:
                anomalies.append('Fever detected')
            elif temp < 36.0:
                anomalies.append('Hypothermia detected')
        
        return anomalies
