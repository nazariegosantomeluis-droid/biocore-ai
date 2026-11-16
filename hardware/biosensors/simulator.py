"""Placa de sensores simulada: habla el protocolo BIO igual que el firmware (2026-11-14). Siempre `sim=1`.

Sirve para la práctica del tutorial y para las pruebas: entra por el mismo camino que una placa real (lista de
puertos → handshake → bloques de cuentas del ADC), así que se prueba toda la tubería, no un atajo.

EMG (modelo del simulador, no un EMG registrado): en reposo, ruido de 10 µV RMS en la piel; al contraer, ruido
filtrado de 30 a 200 Hz con un RMS de 0.5 mV a fuerza completa, con una rampa de 0.1 s al subir o bajar la fuerza.
La placa lo convierte a cuentas como lo haría la salida RAW del MyoWare 2.0 a 3.3 V: ganancia 200, centrada en
1.65 V, ADC de 12 bits. Un electrodo despegado mete zumbido de red de 3 mV y una deriva lenta, y la salida puede
tocar los límites del ADC. Las cifras son elecciones del simulador.
"""

from __future__ import annotations

import threading
import time
from typing import Callable, List, Optional

import numpy as np
from scipy.signal import butter, lfilter

from hardware.ecg_plugplay.ports import PortError, PortInfo
from hardware.ecg_plugplay.transport import Transport, TransportClosed

from .protocol import QUERY, data_line, hello_line
from .sensors import get_sensor

BITS, VREF = 12, 3.3
EMG_GAIN = 200.0
EMG_REST_UV = 10.0
EMG_FULL_RMS_MV = 0.5
EMG_BAND_HZ = (30.0, 200.0)
EMG_RAMP_S = 0.1
EMG_OFF_MAINS_MV = 3.0
EMG_OFF_DRIFT_MV = 2.0
HELLO_EVERY_S = 2.0
MAX_CATCH_UP_S = 2.0          # si nadie lee por más de esto, la placa salta hacia adelante (y `seq` lo delata)


class SimulatedBioBoard:
    """Placa ESP32 simulada con un sensor del catálogo. Controles: plug/unplug, fuerza, electrodo."""

    def __init__(self, sensor_key: str = 'emg', fs: Optional[float] = None, block: int = 20, seed: int = 7,
                 mains_hz: float = 60.0, clock: Callable[[], float] = time.monotonic) -> None:
        self.sensor = get_sensor(sensor_key)
        self.fs = float(fs or self.sensor.default_fs)
        self.block = int(block)
        self.mains_hz = mains_hz
        self._clock = clock
        self._rng = np.random.default_rng(seed)
        self._lock = threading.Lock()
        self.port = PortInfo(f'SIMULADOR-{self.sensor.key.upper()}', f'Placa {self.sensor.key.upper()} simulada')
        self.plugged = True
        self.level = 0.0
        self.electrode_off = False
        self._level_now = 0.0
        self._t0: Optional[float] = None
        self._produced = 0
        self._last_hello = -1e9
        self._hello_pending = True
        self._skipped = 0
        nyq = self.fs / 2.0
        self._b, self._a = butter(2, [EMG_BAND_HZ[0] / nyq, EMG_BAND_HZ[1] / nyq], btype='band')
        impulse = np.zeros(int(self.fs * 4))
        impulse[0] = 1.0
        self._band_gain = float(np.sqrt(np.sum(lfilter(self._b, self._a, impulse) ** 2)))
        self._zi = np.zeros(max(len(self._a), len(self._b)) - 1)
        self._drift = 0.0

    # ------------------------------------------------------------ controles
    def plug(self) -> None:
        with self._lock:
            self.plugged = True

    def unplug(self) -> None:
        with self._lock:
            self.plugged = False

    def set_level(self, level: float) -> None:
        with self._lock:
            self.level = float(np.clip(level, 0.0, 1.0))

    def set_electrode_off(self, off: bool) -> None:
        with self._lock:
            self.electrode_off = bool(off)

    # ------------------------------------------------------------ lo que ve el backend
    def list_ports(self) -> List[PortInfo]:
        return [self.port] if self.plugged else []

    def open_transport(self, port: PortInfo) -> Transport:
        if not self.plugged:
            raise PortError('no_existe', port.device, f'{port.device} ya no existe (se desconectó).')
        return _SimTransport(self)

    def _start(self) -> None:
        with self._lock:
            self._t0 = self._clock()
            self._produced = 0
            self._hello_pending = True

    def handle_input(self, data: bytes) -> None:
        if QUERY.strip() in data:
            with self._lock:
                self._hello_pending = True

    def lines_due(self) -> List[str]:
        with self._lock:
            if not self.plugged:
                raise TransportClosed(f'{self.port.device} se desconectó')
            now = self._clock()
            out: List[str] = []
            if self._hello_pending or now - self._last_hello >= HELLO_EVERY_S:
                out.append(self._hello())
                self._last_hello, self._hello_pending = now, False
            due = int((now - self._t0) * self.fs) - self._produced
            if due > MAX_CATCH_UP_S * self.fs:            # nadie leyó: se saltan muestras, como el firmware
                skip = due - int(self.block)
                self._produced += skip
                self._skipped += skip
                due -= skip
            while due >= self.block:
                counts = self._emg_counts(self.block)
                out.append(data_line(self._produced, [[c] for c in counts]))
                self._produced += self.block
                due -= self.block
            return out

    def _hello(self) -> str:
        return hello_line(sensor=self.sensor.key, fw='sim-1.0', fs=f'{self.fs:g}', ch=';'.join(self.sensor.channels),
                          unit='adc', bits=BITS, vref=VREF, gain=f'{EMG_GAIN:g}', blk=self.block, sim=1,
                          tarde=0, perdidas=self._skipped)

    # ------------------------------------------------------------ señal
    def _emg_counts(self, n: int) -> np.ndarray:
        rng = self._rng
        t = (self._produced + np.arange(n)) / self.fs
        k = np.arange(1, n + 1)
        alpha = 1.0 - np.exp(-1.0 / (EMG_RAMP_S * self.fs))
        level = self.level + (self._level_now - self.level) * (1.0 - alpha) ** k
        self._level_now = float(level[-1])
        band, self._zi = lfilter(self._b, self._a, rng.normal(0.0, 1.0, n), zi=self._zi)
        mv = (EMG_REST_UV / 1000.0) * rng.normal(0.0, 1.0, n) + EMG_FULL_RMS_MV * level * band / self._band_gain
        if self.electrode_off:
            self._drift = self._drift + np.cumsum(rng.normal(0.0, EMG_OFF_DRIFT_MV * 0.02, n))
            self._drift = np.clip(self._drift, -EMG_OFF_DRIFT_MV, EMG_OFF_DRIFT_MV)
            mv = mv + EMG_OFF_MAINS_MV * np.sin(2 * np.pi * self.mains_hz * t) + self._drift
            self._drift = float(self._drift[-1])
        volts = mv / 1000.0 * EMG_GAIN + VREF / 2.0
        return np.clip(np.round(volts / VREF * ((1 << BITS) - 1)), 0, (1 << BITS) - 1).astype(int)


class _SimTransport(Transport):
    """El «puerto» de la placa simulada."""

    provenance = 'SIMULACION'

    def __init__(self, board: SimulatedBioBoard) -> None:
        self.board = board
        self.name = board.port.device
        self.label = board.port.label
        board._start()

    def read(self, timeout: float) -> bytes:
        lines = self.board.lines_due()
        if not lines:
            time.sleep(min(timeout, 0.01))
            return b''
        return ('\n'.join(lines) + '\n').encode()

    def write(self, data: bytes) -> None:
        if not self.board.plugged:
            raise TransportClosed(f'{self.name} se desconectó')
        self.board.handle_input(data)

    def close(self) -> None:
        pass
