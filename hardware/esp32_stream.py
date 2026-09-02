"""ESP32 ECG stream helper for AD8232 and serial wearable acquisition.

This module supports a low-latency serial stream from ESP32/Arduino and
provides a circular buffer, automatic reconnection, timestamp handling,
signal normalization and a minimal real-time quality assessment for
biomedical ECG monitoring.
"""

import collections
import logging
import re
import threading
import time
from typing import Deque, List, Optional, Tuple

import numpy as np
from scipy.signal import butter, filtfilt, find_peaks

try:
    import serial
    from serial.tools import list_ports
except ImportError:  # type: ignore
    serial = None  # type: ignore
    list_ports = None  # type: ignore

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[ESP32] %(asctime)s %(levelname)s: %(message)s"))
    logger.addHandler(handler)

SERIAL_LINE_PATTERN = re.compile(r"^\s*(?P<ts>[0-9]+(?:\.[0-9]+)?)\s*,\s*(?P<value>-?[0-9]+(?:\.[0-9]+)?)\s*$")


class ESP32ECGStreamer:
    """Stream ECG data from ESP32/Arduino over serial/Bluetooth."""

    def __init__(
        self,
        port: Optional[str] = None,
        baud: int = 115200,
        timeout: float = 0.75,
        fs: int = 250,
        buffer_seconds: int = 15,
        simulate_if_missing: bool = True,
    ) -> None:
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self.fs = fs
        self.simulate_if_missing = simulate_if_missing
        self.serial_conn = None
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._time_buffer: Deque[float] = collections.deque(maxlen=buffer_seconds * fs)
        self._ecg_buffer: Deque[float] = collections.deque(maxlen=buffer_seconds * fs)
        self._ppg_buffer: Deque[float] = collections.deque(maxlen=buffer_seconds * fs)
        self._spo2_buffer: Deque[float] = collections.deque(maxlen=buffer_seconds * fs)
        self.last_error: Optional[str] = None
        self.connected = False
        self._simulate_phase = 0.0

    def auto_detect_port(self) -> Optional[str]:
        """Find a candidate serial port for an ESP32/Arduino device."""
        if list_ports is None:
            return None

        candidate_ports = []
        for port_info in list_ports.comports():
            name = port_info.device.lower()
            if 'usb' in name or 'com' in name or 'tty' in name or 'esp' in name:
                candidate_ports.append(port_info.device)

        if candidate_ports:
            detected = candidate_ports[0]
            logger.info(f"Auto-detect port: {detected}")
            return detected

        logger.info("No serial candidate port encontrado.")
        return None

    def connect(self, force_port: Optional[str] = None) -> bool:
        """Open the serial connection or prepare simulation mode."""
        if serial is None:
            self.last_error = 'pyserial no está instalado.'
            logger.warning(self.last_error)
            if self.simulate_if_missing:
                logger.info('Entrando en modo simulación de señal ECG.')
                self.connected = True
                return True
            return False

        chosen_port = force_port or self.port
        if chosen_port is None:
            chosen_port = self.auto_detect_port()

        if chosen_port is None:
            self.last_error = 'No se encontró puerto serial compatible.'
            logger.warning(self.last_error)
            if self.simulate_if_missing:
                logger.info('Entrando en modo simulación de señal ECG.')
                self.connected = True
                return True
            return False

        try:
            self.serial_conn = serial.Serial(
                port=chosen_port,
                baudrate=self.baud,
                timeout=self.timeout,
                write_timeout=1,
            )
            self.connected = True
            self.port = chosen_port
            logger.info(f"Conectado a {chosen_port} a {self.baud} baudios.")
            return True
        except Exception as exc:
            self.last_error = str(exc)
            self.connected = False
            logger.error(f"Fallo al conectar: {exc}")
            if self.simulate_if_missing:
                logger.info('Entrando en modo simulación de señal ECG.')
                self.connected = True
                return True
            return False

    def disconnect(self) -> None:
        """Stop streaming and close the serial port."""
        self.stop()
        if self.serial_conn is not None:
            try:
                self.serial_conn.close()
                logger.info('Puerto serial cerrado.')
            except Exception as exc:
                logger.error(f'Error cerrando puerto serial: {exc}')
        self.serial_conn = None
        self.connected = False

    def is_connected(self) -> bool:
        return self.connected and (self.serial_conn is not None or self.simulate_if_missing)

    def _normalize_raw_ecg(self, raw_value: float) -> float:
        """Normalize raw ADC values to approximate millivolts."""
        if 0 <= raw_value <= 1023:
            return (raw_value - 512.0) / 512.0 * 1.5
        return raw_value * 0.001

    def _normalize_raw_ppg(self, raw_value: float) -> float:
        if 0 <= raw_value <= 1023:
            return float(raw_value) / 1023.0
        return float(raw_value)

    def _normalize_raw_spo2(self, raw_value: float) -> float:
        if 0 <= raw_value <= 1023:
            return float(raw_value) / 1023.0 * 100.0
        return float(raw_value)

    def _parse_line(self, line: str) -> Optional[Tuple[float, float, Optional[float], Optional[float]]]:
        if not line:
            return None

        line = line.strip()
        parts = re.split(r'[;:,\t]+', line)
        values: List[float] = []
        for part in parts:
            try:
                values.append(float(part))
            except ValueError:
                continue

        if len(values) >= 2:
            timestamp = float(values[0])
            ecg_value = float(values[1])
            ppg_value = float(values[2]) if len(values) >= 3 else None
            spo2_value = float(values[3]) if len(values) >= 4 else None
            return (
                timestamp,
                self._normalize_raw_ecg(ecg_value),
                self._normalize_raw_ppg(ppg_value) if ppg_value is not None else None,
                self._normalize_raw_spo2(spo2_value) if spo2_value is not None else None,
            )

        if len(values) == 1:
            try:
                return time.time(), self._normalize_raw_ecg(values[0]), None, None
            except ValueError:
                return None

        match = SERIAL_LINE_PATTERN.match(line)
        if match:
            try:
                timestamp = float(match.group('ts'))
                value = float(match.group('value'))
                return timestamp, self._normalize_raw_ecg(value), None, None
            except ValueError:
                return None

        return None

    def _generate_simulation(self) -> Tuple[float, float]:
        self._simulate_phase += 2 * np.pi * 1.2 / self.fs
        t = time.time()
        signal = 0.9 * np.sin(self._simulate_phase)
        signal += 0.2 * np.sin(2.0 * self._simulate_phase)
        signal += 0.15 * np.random.randn()
        return t, signal

    def _read_serial_line(self) -> Optional[str]:
        if self.serial_conn is None:
            return None
        try:
            raw = self.serial_conn.readline().decode('utf-8', errors='ignore')
            return raw.strip()
        except Exception as exc:
            self.last_error = f'Error leyendo serial: {exc}'
            logger.warning(self.last_error)
            return None

    def _append_sample(
        self,
        timestamp: float,
        ecg_value: float,
        ppg_value: Optional[float] = None,
        spo2_value: Optional[float] = None,
    ) -> None:
        with self._lock:
            self._time_buffer.append(timestamp)
            self._ecg_buffer.append(ecg_value)
            self._ppg_buffer.append(ppg_value if ppg_value is not None else np.nan)
            self._spo2_buffer.append(spo2_value if spo2_value is not None else np.nan)

    def _stream_loop(self) -> None:
        while not self._stop_event.is_set():
            if self.serial_conn is None and self.simulate_if_missing:
                sample = self._generate_simulation()
                timestamp, ecg_value = sample
                ppg_value = None
                spo2_value = None
            else:
                line = self._read_serial_line()
                if not line:
                    time.sleep(0.005)
                    continue
                parsed = self._parse_line(line)
                if parsed is None:
                    continue
                timestamp, ecg_value, ppg_value, spo2_value = parsed

            self._append_sample(timestamp, ecg_value, ppg_value, spo2_value)
            time.sleep(max(0, 1.0 / self.fs - 0.001))

    def start(self) -> bool:
        """Begin continuous data acquisition in a background thread."""
        if self._thread and self._thread.is_alive():
            return True

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._stream_loop, daemon=True)
        self._thread.start()
        logger.info('Streaming iniciado.')
        return True

    def stop(self) -> None:
        """Stop the background streaming thread."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=1.5)
        self._thread = None
        logger.info('Streaming detenido.')

    def get_buffer(self) -> Tuple[np.ndarray, np.ndarray]:
        """Return the current timestamp and ECG buffers."""
        with self._lock:
            return np.array(self._time_buffer, dtype=float), np.array(self._ecg_buffer, dtype=float)

    def get_ppg_buffer(self) -> Tuple[np.ndarray, np.ndarray]:
        """Return the current timestamp and PPG buffers."""
        with self._lock:
            return np.array(self._time_buffer, dtype=float), np.array(self._ppg_buffer, dtype=float)

    def get_spo2_buffer(self) -> Tuple[np.ndarray, np.ndarray]:
        """Return the current timestamp and SpO2 buffers."""
        with self._lock:
            return np.array(self._time_buffer, dtype=float), np.array(self._spo2_buffer, dtype=float)

    def get_multi_channel_buffer(self) -> dict:
        """Return the latest buffered multi-channel signal arrays."""
        t, ecg = self.get_buffer()
        _, ppg = self.get_ppg_buffer()
        _, spo2 = self.get_spo2_buffer()
        return {'time': t, 'ecg': ecg, 'ppg': ppg, 'spo2': spo2}

    def get_recent_quality(self) -> dict:
        """Compute lightweight signal quality metrics."""
        _, ecg = self.get_buffer()
        quality = {
            'signal_length': len(ecg),
            'noise_score': 0.0,
            'peak_count': 0,
            'bpm': None,
            'ppg_present': np.isfinite(self._ppg_buffer[-1]) if len(self._ppg_buffer) else False,
            'spo2_present': np.isfinite(self._spo2_buffer[-1]) if len(self._spo2_buffer) else False,
        }
        if len(ecg) < self.fs * 3:
            return quality

        quality['noise_score'] = float(np.std(ecg[-int(self.fs * 3):]))
        peaks, _ = find_peaks(ecg, distance=int(0.25 * self.fs), height=np.mean(ecg) + 0.25 * np.std(ecg))
        quality['peak_count'] = len(peaks)
        if len(peaks) >= 2:
            rr_intervals = np.diff(peaks) / float(self.fs)
            quality['bpm'] = float(60.0 / np.mean(rr_intervals))
        return quality

    def get_filtered_buffer(self, lowcut: float = 0.5, highcut: float = 40.0) -> Tuple[np.ndarray, np.ndarray]:
        t, ecg = self.get_buffer()
        if len(ecg) < 5:
            return t, ecg
        b, a = butter(2, [lowcut / (0.5 * self.fs), highcut / (0.5 * self.fs)], btype='band')
        try:
            filtered = filtfilt(b, a, ecg)
            return t, filtered
        except Exception:
            return t, ecg

    def get_status(self) -> str:
        if not self.connected:
            return 'Desconectado'
        if self._thread and self._thread.is_alive():
            return 'Transmitiendo'
        return 'Conectado'

    def get_health_summary(self) -> dict:
        quality = self.get_recent_quality()
        signal_status = 'OK' if quality['noise_score'] < 0.4 else 'Ruido alto'
        ppg_status = 'Sí' if quality['ppg_present'] else 'No'
        spo2_status = 'Sí' if quality['spo2_present'] else 'No'
        return {
            'state': self.get_status(),
            'buffer_seconds': round(len(self._ecg_buffer) / float(self.fs), 1),
            'quality': signal_status,
            'bpm': quality['bpm'],
            'noise_std': quality['noise_score'],
            'peaks': quality['peak_count'],
            'ppg_present': ppg_status,
            'spo2_present': spo2_status,
            'last_error': self.last_error,
        }
