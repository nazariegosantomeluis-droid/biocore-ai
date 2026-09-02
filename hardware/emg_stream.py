"""Generic EMG streamer: serial/acquisition + simulation fallback.

Provides a simple background streamer compatible with the ESP32 streamer
pattern used elsewhere in the project. Streams timestamped samples and
offers lightweight quality metrics and bandpass-filtered output.
"""

import collections
import logging
import threading
import time
from typing import Deque, List, Optional, Tuple

import numpy as np
from scipy.signal import butter, filtfilt

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
    handler.setFormatter(logging.Formatter("[EMG] %(asctime)s %(levelname)s: %(message)s"))
    logger.addHandler(handler)


class EMGStreamer:
    def __init__(
        self,
        port: Optional[str] = None,
        baud: int = 115200,
        timeout: float = 0.5,
        fs: int = 1000,
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
        self._emg_buffer: Deque[float] = collections.deque(maxlen=buffer_seconds * fs)
        self.last_error: Optional[str] = None
        self.connected = False
        self._simulate_phase = 0.0

    def auto_detect_port(self) -> Optional[str]:
        if list_ports is None:
            return None
        candidates = []
        for p in list_ports.comports():
            name = p.device.lower()
            if 'usb' in name or 'com' in name or 'tty' in name or 'esp' in name:
                candidates.append(p.device)
        return candidates[0] if candidates else None

    def connect(self, force_port: Optional[str] = None) -> bool:
        if serial is None:
            self.last_error = 'pyserial no está instalado.'
            logger.warning(self.last_error)
            if self.simulate_if_missing:
                logger.info('Modo simulación EMG activado (pyserial ausente).')
                self.connected = True
                return True
            return False

        chosen = force_port or self.port or self.auto_detect_port()
        if chosen is None:
            self.last_error = 'No se encontró puerto serial.'
            logger.warning(self.last_error)
            if self.simulate_if_missing:
                self.connected = True
                return True
            return False

        try:
            self.serial_conn = serial.Serial(port=chosen, baudrate=self.baud, timeout=self.timeout)
            self.connected = True
            self.port = chosen
            logger.info(f'Conectado a {chosen} ({self.baud} baudios)')
            return True
        except Exception as exc:
            self.last_error = str(exc)
            logger.error(f'Fallo al conectar: {exc}')
            if self.simulate_if_missing:
                logger.info('Modo simulación EMG activado por fallo conexión.')
                self.connected = True
                return True
            return False

    def disconnect(self) -> None:
        self.stop()
        if self.serial_conn is not None:
            try:
                self.serial_conn.close()
            except Exception:
                pass
        self.serial_conn = None
        self.connected = False

    def _generate_simulation(self) -> Tuple[float, float]:
        # EMG-like bursty noise
        t = time.time()
        self._simulate_phase += 2 * np.pi * 50.0 / float(self.fs)
        burst = 0.6 * (0.5 + 0.5 * np.sign(np.sin(self._simulate_phase * 0.2)))
        noise = np.random.randn() * 0.35
        value = burst * (0.8 * np.random.randn() + 0.2 * np.sin(2 * np.pi * 150.0 * (self._simulate_phase / (2 * np.pi)))) + noise
        return t, float(value)

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

    def _parse_line(self, line: str) -> Optional[Tuple[float, float]]:
        if not line:
            return None
        parts = [p for p in line.replace(';', ',').split(',') if p.strip()]
        if len(parts) >= 2:
            try:
                ts = float(parts[0])
                val = float(parts[1])
                return ts, float(val)
            except Exception:
                pass
        # fallback: try to extract numeric from line
        import re
        vals = re.findall(r'-?\d+\.?\d*', line)
        if vals:
            try:
                return time.time(), float(vals[-1])
            except Exception:
                return None
        return None

    def _append_sample(self, timestamp: float, value: float) -> None:
        with self._lock:
            self._time_buffer.append(timestamp)
            self._emg_buffer.append(value)

    def _stream_loop(self) -> None:
        while not self._stop_event.is_set():
            if self.serial_conn is None and self.simulate_if_missing:
                sample = self._generate_simulation()
            else:
                line = self._read_serial_line()
                if not line:
                    time.sleep(0.001)
                    continue
                parsed = self._parse_line(line)
                if parsed is None:
                    continue
                sample = parsed

            self._append_sample(*sample)
            time.sleep(max(0, 1.0 / float(self.fs) - 0.0005))

    def start(self) -> bool:
        if self._thread and self._thread.is_alive():
            return True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._stream_loop, daemon=True)
        self._thread.start()
        logger.info('EMG streaming iniciado.')
        return True

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=1.5)
        self._thread = None
        logger.info('EMG streaming detenido.')

    def get_buffer(self) -> Tuple[np.ndarray, np.ndarray]:
        with self._lock:
            return np.array(self._time_buffer, dtype=float), np.array(self._emg_buffer, dtype=float)

    def get_filtered_buffer(self, lowcut: float = 20.0, highcut: float = 450.0) -> Tuple[np.ndarray, np.ndarray]:
        t, emg = self.get_buffer()
        if len(emg) < 5:
            return t, emg
        b, a = butter(3, [lowcut / (0.5 * self.fs), highcut / (0.5 * self.fs)], btype='band')
        try:
            filtered = filtfilt(b, a, emg)
            return t, filtered
        except Exception:
            return t, emg

    def is_connected(self) -> bool:
        return self.connected and (self.serial_conn is not None or self.simulate_if_missing)

    def auto_list_ports(self) -> List[str]:
        if list_ports is None:
            return []
        return [p.device for p in list_ports.comports()]

    def get_status(self) -> str:
        if not self.connected:
            return 'Desconectado'
        if self._thread and self._thread.is_alive():
            return 'Transmitiendo'
        return 'Conectado'
