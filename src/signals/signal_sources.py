"""Unified biomedical signal source abstraction for demo, PhysioNet and ESP32 hardware."""

from __future__ import annotations

import collections
import logging
import time
from abc import ABC, abstractmethod
from typing import Deque, Dict, List, Optional, Tuple

import numpy as np
from scipy.signal import butter, filtfilt

try:
    from hardware.esp32_stream import ESP32ECGStreamer
except ImportError:  # pragma: no cover
    ESP32ECGStreamer = None  # type: ignore

try:
    from signals.loaders.wfdb_loader import load_mitbih_record
except ImportError:  # pragma: no cover
    load_mitbih_record = None  # type: ignore

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[SignalSource] %(asctime)s %(levelname)s: %(message)s"))
    logger.addHandler(handler)


class BaseSignalSource(ABC):
    """Abstract source for ECG and related biomedical signal streams."""

    def __init__(self, name: str, fs: float, buffer_seconds: int = 15, simulate_if_missing: bool = True) -> None:
        self.name = name
        self.fs = float(fs)
        self.buffer_seconds = buffer_seconds
        self.simulate_if_missing = simulate_if_missing
        self.connected = False

    @abstractmethod
    def connect(self, force_port: Optional[str] = None) -> bool:
        raise NotImplementedError

    @abstractmethod
    def disconnect(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def start(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def stop(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_buffer(self) -> Tuple[np.ndarray, np.ndarray]:
        raise NotImplementedError

    def get_filtered_buffer(self, lowcut: float = 0.5, highcut: float = 40.0) -> Tuple[np.ndarray, np.ndarray]:
        t, signal = self.get_buffer()
        if len(signal) < 5:
            return t, signal
        nyq = 0.5 * self.fs
        b, a = butter(2, [lowcut / nyq, highcut / nyq], btype='band')
        try:
            return t, filtfilt(b, a, signal)
        except Exception as exc:
            logger.warning(f"Signal filtering failed: {exc}")
            return t, signal

    def get_latest_window(self, duration: float = 2.0) -> Tuple[np.ndarray, np.ndarray]:
        t, signal = self.get_buffer()
        if len(t) == 0:
            return t, signal
        cutoff = t[-1] - duration
        idx = int(np.searchsorted(t, cutoff, side='left')) if len(t) else 0
        return t[idx:], signal[idx:]

    def get_health_summary(self) -> Dict[str, float]:
        t, signal = self.get_buffer()
        length = len(signal)
        quality = {'source': self.name, 'signal_length': length, 'buffer_seconds': length / float(self.fs) if self.fs else 0.0}
        if length >= self.fs:
            quality['mean'] = float(np.nanmean(signal))
            quality['std'] = float(np.nanstd(signal))
        return quality


class SyntheticECGSource(BaseSignalSource):
    def __init__(self, fs: float = 250, duration: float = 30.0, hr: float = 72.0) -> None:
        super().__init__(name='Synthetic ECG', fs=fs, buffer_seconds=int(duration), simulate_if_missing=True)
        self.duration = float(duration)
        self.hr = float(hr)
        self.signal = self._generate_signal()
        self.time = np.arange(len(self.signal), dtype=float) / self.fs
        self.connected = True

    def connect(self, force_port: Optional[str] = None) -> bool:
        self.connected = True
        return True

    def disconnect(self) -> None:
        self.connected = False

    def start(self) -> bool:
        return True

    def stop(self) -> None:
        pass

    def get_buffer(self) -> Tuple[np.ndarray, np.ndarray]:
        return self.time, self.signal

    def _generate_signal(self) -> np.ndarray:
        n_samples = int(self.fs * self.duration)
        t = np.arange(n_samples, dtype=float) / self.fs
        hr_rad = 2 * np.pi * (self.hr / 60.0) * t
        p_wave = 0.15 * np.exp(-((t % 1.0) - 0.1) ** 2 / 0.008)
        qrs_complex = 1.0 * np.exp(-((t % 1.0) - 0.25) ** 2 / 0.005) * np.sin(6 * np.pi * (t % 1.0))
        t_wave = 0.3 * np.exp(-((t % 1.0) - 0.4) ** 2 / 0.02)
        baseline = 0.05 * np.sin(2 * np.pi * 0.1 * t)
        noise = 0.02 * np.random.normal(0, 1, n_samples)
        return p_wave + qrs_complex + t_wave + baseline + noise


class PhysioNetECGSource(BaseSignalSource):
    def __init__(self, record_id: str = '100', lead: int = 0) -> None:
        super().__init__(name=f'MIT-BIH {record_id}', fs=250.0, buffer_seconds=60, simulate_if_missing=False)
        self.record_id = record_id
        self.lead = lead
        self.signal: np.ndarray = np.array([], dtype=float)
        self.time: np.ndarray = np.array([], dtype=float)
        self.metadata: Dict[str, any] = {}

    def connect(self, force_port: Optional[str] = None) -> bool:
        if load_mitbih_record is None:
            raise ImportError('wfdb no está instalado. Instala pip install wfdb para PhysioNet support.')
        signal, fs, metadata = load_mitbih_record(self.record_id, lead=self.lead)
        self.signal = np.asarray(signal, dtype=float)
        self.fs = float(fs)
        self.time = np.arange(len(self.signal), dtype=float) / self.fs
        self.metadata = metadata
        self.connected = True
        return True

    def disconnect(self) -> None:
        self.connected = False

    def start(self) -> bool:
        return True

    def stop(self) -> None:
        pass

    def get_buffer(self) -> Tuple[np.ndarray, np.ndarray]:
        return self.time, self.signal

    def get_health_summary(self) -> Dict[str, float]:
        health = super().get_health_summary()
        health['record_id'] = self.record_id
        health['source'] = 'PhysioNet MIT-BIH'
        health['sig_name'] = self.metadata.get('sig_name', 'ECG')
        return health


class ESP32SignalSource(BaseSignalSource):
    def __init__(
        self,
        port: Optional[str] = None,
        baud: int = 115200,
        timeout: float = 0.75,
        fs: int = 250,
        buffer_seconds: int = 15,
        simulate_if_missing: bool = True,
    ) -> None:
        super().__init__(name='ESP32 Signal', fs=fs, buffer_seconds=buffer_seconds, simulate_if_missing=simulate_if_missing)
        if ESP32ECGStreamer is None:
            raise ImportError('hardware.esp32_stream no está disponible. Instala pyserial o revisa hardware/esp32_stream.py')
        self.streamer = ESP32ECGStreamer(
            port=port,
            baud=baud,
            timeout=timeout,
            fs=fs,
            buffer_seconds=buffer_seconds,
            simulate_if_missing=simulate_if_missing,
        )

    def connect(self, force_port: Optional[str] = None) -> bool:
        self.connected = self.streamer.connect(force_port=force_port)
        return self.connected

    def disconnect(self) -> None:
        self.streamer.disconnect()
        self.connected = False

    def start(self) -> bool:
        return self.streamer.start()

    def stop(self) -> None:
        self.streamer.stop()

    def get_buffer(self) -> Tuple[np.ndarray, np.ndarray]:
        return self.streamer.get_buffer()

    def get_ppg_buffer(self) -> Tuple[np.ndarray, np.ndarray]:
        return self.streamer.get_ppg_buffer()

    def get_spo2_buffer(self) -> Tuple[np.ndarray, np.ndarray]:
        return self.streamer.get_spo2_buffer()

    def get_multi_channel_buffer(self) -> Dict[str, np.ndarray]:
        buffers = self.streamer.get_multi_channel_buffer()
        return buffers

    def is_connected(self) -> bool:
        return self.streamer.is_connected()

    def is_hardware_present(self) -> bool:
        """True SOLO si hay una conexión serial real y activa.

        Tanda 4, Pieza 2 (2026-07-04): a diferencia de `is_connected()` (que
        el propio `ESP32ECGStreamer.is_connected()` define como
        `self.connected and (self.serial_conn is not None or
        self.simulate_if_missing)` — es decir, sigue siendo True incluso en
        modo simulado sin hardware), esto comprueba directamente
        `serial_conn is not None`: la única señal honesta de que hay un
        dispositivo físico respondiendo. Úsalo para decidir
        `Provenance.SENSOR_REAL` vs `Provenance.SIMULACION` — nunca
        `is_connected()`/`.connected` para esa decisión."""
        return self.streamer.serial_conn is not None

    def get_health_summary(self) -> Dict[str, float]:
        summary = self.streamer.get_health_summary()
        summary['source'] = 'ESP32 Hardware'
        return summary

    def get_status(self) -> str:
        return self.streamer.get_status()


__all__ = [
    'BaseSignalSource',
    'SyntheticECGSource',
    'PhysioNetECGSource',
    'ESP32SignalSource',
]
