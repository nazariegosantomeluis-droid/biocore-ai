"""Placa de sensores simulada: habla el protocolo BIO igual que el firmware (2026-11-14). Siempre `sim=1`.

Sirve para la práctica de los tutoriales y para las pruebas: entra por el mismo camino que una placa real (lista de
puertos → handshake → bloques con lo que manda el sensor), así que se prueba toda la tubería, no un atajo. La placa
pone la plomería (puerto, handshake, tiempo, saltos) y un modelo por sensor pone la señal y los controles
(`board.model`). Todas las cifras de los modelos son elecciones del simulador, no registros.

- EMG (`EmgModel`): en reposo, ruido de 10 µV RMS en la piel; al contraer, ruido filtrado de 30 a 200 Hz con un RMS
  de 0.5 mV a fuerza completa, con una rampa de 0.1 s. Se convierte a cuentas como la salida RAW del MyoWare 2.0 a
  3.3 V (ganancia 200, centrada en 1.65 V, ADC de 12 bits). Un electrodo despegado mete zumbido de red de 3 mV y una
  deriva lenta.
- Pulso por luz (`PpgModel`, 2026-11-16): luz recibida por el MAX30102 en cuentas de 18 bits, roja e infrarroja.
  Con el dedo, 95 000 y 120 000 cuentas de fondo; en cada latido baja la luz (entra más sangre) con una forma de dos
  ondas, un índice de perfusión de 2 % en el infrarrojo y R = 0.55. La respiración (15 por minuto) mueve la línea de
  base y el ritmo un poco. Sin dedo solo queda la luz ambiente; con movimiento, cambios lentos de hasta 4 % de la luz.
- Temperatura (`TempModel`, 2026-11-16): la sonda se acerca a 35.6 °C en la axila y a 24 °C en el aire con una
  constante de tiempo de 30 s, en pasos de 0.0625 °C como el DS18B20 a 12 bits.
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Dict, List, Optional

import numpy as np
from scipy.signal import butter, lfilter

from hardware.ecg_plugplay.ports import PortError, PortInfo
from hardware.ecg_plugplay.transport import Transport, TransportClosed

from .protocol import QUERY, data_line, hello_line
from .sensors import get_sensor

HELLO_EVERY_S = 2.0
MAX_CATCH_UP_S = 2.0          # si nadie lee por más de esto, la placa salta hacia adelante (y `seq` lo delata)

# EMG
BITS, VREF = 12, 3.3
EMG_GAIN = 200.0
EMG_REST_UV = 10.0
EMG_FULL_RMS_MV = 0.5
EMG_BAND_HZ = (30.0, 200.0)
EMG_RAMP_S = 0.1
EMG_OFF_MAINS_MV = 3.0
EMG_OFF_DRIFT_MV = 2.0

# Pulso por luz (MAX30102)
PPG_BITS = 18
PPG_FULL_SCALE = (1 << PPG_BITS) - 1
PPG_DC_FINGER = (95_000.0, 120_000.0)      # (rojo, infrarrojo)
PPG_DC_AIR = (2_000.0, 2_500.0)
PPG_PI_IR = 0.02                           # AC/DC del infrarrojo
PPG_RATIO_R = 0.55                         # (AC/DC rojo) / (AC/DC infrarrojo)
PPG_RESP_HZ = 0.25
PPG_RESP_DEPTH = 0.004                     # la respiración mueve la línea de base 0.4 % del fondo
PPG_RSA = 0.04                             # y el ritmo ±4 %
PPG_NOISE = 15.0                           # cuentas
PPG_MOTION = 0.04                          # cambios lentos de la luz por movimiento, hasta 4 % del fondo
PPG_MOTION_BAND_HZ = (0.3, 3.0)
PPG_RATES = (65.0, 110.0)                  # latidos por minuto que ofrece la práctica

# Temperatura (DS18B20)
TEMP_SKIN_C = 35.6
TEMP_AIR_C = 24.0
TEMP_TAU_S = 30.0
TEMP_NOISE_C = 0.02
TEMP_STEP_C = 0.0625                       # resolución a 12 bits (hoja de datos)


class EmgModel:
    """MyoWare 2.0 (salida RAW). Controles: fuerza (0 a 1) y electrodo despegado."""

    block = 20

    def __init__(self, fs: float, rng: np.random.Generator, mains_hz: float, lock: threading.Lock) -> None:
        self.fs, self._rng, self.mains_hz, self._lock = fs, rng, mains_hz, lock
        self.level = 0.0
        self.electrode_off = False
        self._level_now = 0.0
        nyq = fs / 2.0
        self._b, self._a = butter(2, [EMG_BAND_HZ[0] / nyq, EMG_BAND_HZ[1] / nyq], btype='band')
        impulse = np.zeros(int(fs * 4))
        impulse[0] = 1.0
        self._band_gain = float(np.sqrt(np.sum(lfilter(self._b, self._a, impulse) ** 2)))
        self._zi = np.zeros(max(len(self._a), len(self._b)) - 1)
        self._drift = 0.0

    def set_level(self, level: float) -> None:
        with self._lock:
            self.level = float(np.clip(level, 0.0, 1.0))

    def set_electrode_off(self, off: bool) -> None:
        with self._lock:
            self.electrode_off = bool(off)

    def hello_params(self) -> Dict[str, object]:
        return dict(unit='adc', bits=BITS, vref=VREF, gain=f'{EMG_GAIN:g}')

    def generate(self, start: int, n: int) -> np.ndarray:
        rng = self._rng
        t = (start + np.arange(n)) / self.fs
        k = np.arange(1, n + 1)
        alpha = 1.0 - np.exp(-1.0 / (EMG_RAMP_S * self.fs))
        level = self.level + (self._level_now - self.level) * (1.0 - alpha) ** k
        self._level_now = float(level[-1])
        band, self._zi = lfilter(self._b, self._a, rng.normal(0.0, 1.0, n), zi=self._zi)
        mv = (EMG_REST_UV / 1000.0) * rng.normal(0.0, 1.0, n) + EMG_FULL_RMS_MV * level * band / self._band_gain
        if self.electrode_off:
            drift = self._drift + np.cumsum(rng.normal(0.0, EMG_OFF_DRIFT_MV * 0.02, n))
            drift = np.clip(drift, -EMG_OFF_DRIFT_MV, EMG_OFF_DRIFT_MV)
            mv = mv + EMG_OFF_MAINS_MV * np.sin(2 * np.pi * self.mains_hz * t) + drift
            self._drift = float(drift[-1])
        volts = mv / 1000.0 * EMG_GAIN + VREF / 2.0
        counts = np.clip(np.round(volts / VREF * ((1 << BITS) - 1)), 0, (1 << BITS) - 1)
        return counts.astype(int).reshape(n, 1)


def _pulse_shape(phase: np.ndarray) -> np.ndarray:
    """Una onda sistólica y una diastólica más chica, periódica en la fase (0 a 1). Elección del simulador."""
    out = np.zeros_like(phase, dtype=float)
    for shift in (-1.0, 0.0, 1.0):
        p = phase + shift
        out += np.exp(-0.5 * ((p - 0.22) / 0.07) ** 2) + 0.45 * np.exp(-0.5 * ((p - 0.50) / 0.11) ** 2)
    return out


_GRID = _pulse_shape(np.linspace(0.0, 1.0, 1000, endpoint=False))
_SHAPE_MIN, _SHAPE_PTP = float(_GRID.min()), float(np.ptp(_GRID))


class PpgModel:
    """MAX30102 (rojo e infrarrojo). Controles: frecuencia del pulso, dedo puesto y movimiento."""

    block = 10

    def __init__(self, fs: float, rng: np.random.Generator, mains_hz: float, lock: threading.Lock) -> None:
        self.fs, self._rng, self._lock = fs, rng, lock
        self.rate_bpm = PPG_RATES[0]
        self.finger = True
        self.motion = False
        self._phase = 0.0
        nyq = fs / 2.0
        self._b, self._a = butter(2, [PPG_MOTION_BAND_HZ[0] / nyq, PPG_MOTION_BAND_HZ[1] / nyq], btype='band')
        impulse = np.zeros(int(fs * 20))
        impulse[0] = 1.0
        self._motion_gain = float(np.sqrt(np.sum(lfilter(self._b, self._a, impulse) ** 2)))
        self._zi = np.zeros(max(len(self._a), len(self._b)) - 1)

    def set_rate(self, bpm: float) -> None:
        with self._lock:
            self.rate_bpm = float(bpm)

    def set_finger(self, on: bool) -> None:
        with self._lock:
            self.finger = bool(on)

    def set_motion(self, on: bool) -> None:
        with self._lock:
            self.motion = bool(on)

    def hello_params(self) -> Dict[str, object]:
        return dict(unit='cuentas', bits=PPG_BITS, led_ma='7.2')

    def generate(self, start: int, n: int) -> np.ndarray:
        rng = self._rng
        t = (start + np.arange(n)) / self.fs
        resp = np.sin(2 * np.pi * PPG_RESP_HZ * t)
        freq = self.rate_bpm / 60.0 * (1.0 + PPG_RSA * resp)
        phase = self._phase + np.cumsum(freq) / self.fs
        self._phase = float(phase[-1] % 1.0)
        pulse = (_pulse_shape(phase % 1.0) - _SHAPE_MIN) / _SHAPE_PTP          # de 0 a 1 en cada latido
        motion, self._zi = lfilter(self._b, self._a, rng.normal(0.0, 1.0, n), zi=self._zi)
        motion = motion / self._motion_gain * (PPG_MOTION / 2.0) if self.motion else np.zeros(n)
        out = np.empty((n, 2))
        for i, ratio in enumerate((PPG_PI_IR * PPG_RATIO_R, PPG_PI_IR)):
            if self.finger:
                light = PPG_DC_FINGER[i] * (1.0 - ratio * pulse - PPG_RESP_DEPTH * resp + motion)
            else:
                light = PPG_DC_AIR[i] * (1.0 + motion)
            out[:, i] = light + rng.normal(0.0, PPG_NOISE, n)
        return np.clip(np.round(out), 0, PPG_FULL_SCALE).astype(int)


class TempModel:
    """DS18B20 en sonda. Control: en la axila o en el aire."""

    block = 1

    def __init__(self, fs: float, rng: np.random.Generator, mains_hz: float, lock: threading.Lock) -> None:
        self.fs, self._rng, self._lock = fs, rng, lock
        self.on_skin = False
        self._temp = TEMP_AIR_C

    def set_on_skin(self, on: bool) -> None:
        with self._lock:
            self.on_skin = bool(on)

    def hello_params(self) -> Dict[str, object]:
        return dict(unit='C', res=12)

    def generate(self, start: int, n: int) -> np.ndarray:
        target = TEMP_SKIN_C if self.on_skin else TEMP_AIR_C
        step = 1.0 - np.exp(-1.0 / (self.fs * TEMP_TAU_S))
        out = np.empty((n, 1))
        for i in range(n):
            self._temp += (target - self._temp) * step
            out[i, 0] = np.round((self._temp + self._rng.normal(0.0, TEMP_NOISE_C)) / TEMP_STEP_C) * TEMP_STEP_C
        return out


_MODELS = {'emg': EmgModel, 'ppg': PpgModel, 'temp': TempModel}


class SimulatedBioBoard:
    """Placa ESP32 simulada con un sensor del catálogo. Controles: plug/unplug aquí; la señal, en `model`."""

    def __init__(self, sensor_key: str = 'emg', fs: Optional[float] = None, block: Optional[int] = None,
                 seed: int = 7, mains_hz: float = 60.0, clock: Callable[[], float] = time.monotonic) -> None:
        self.sensor = get_sensor(sensor_key)
        self.fs = float(fs or self.sensor.default_fs)
        self._clock = clock
        self._rng = np.random.default_rng(seed)
        self._lock = threading.Lock()
        self.model = _MODELS[self.sensor.key](self.fs, self._rng, mains_hz, self._lock)
        self.block = int(block or self.model.block)
        self.port = PortInfo(f'SIMULADOR-{self.sensor.key.upper()}', f'Placa {self.sensor.key.upper()} simulada')
        self.plugged = True
        self._t0: Optional[float] = None
        self._produced = 0
        self._last_hello = -1e9
        self._hello_pending = True
        self._skipped = 0

    # ------------------------------------------------------------ cable
    def plug(self) -> None:
        with self._lock:
            self.plugged = True

    def unplug(self) -> None:
        with self._lock:
            self.plugged = False

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
            if due > MAX_CATCH_UP_S * self.fs and due > self.block:   # nadie leyó: se saltan muestras
                skip = due - int(self.block)
                self._produced += skip
                self._skipped += skip
                due -= skip
            while due >= self.block:
                samples = self.model.generate(self._produced, self.block)
                out.append(data_line(self._produced, samples.tolist()))
                self._produced += self.block
                due -= self.block
            return out

    def _hello(self) -> str:
        return hello_line(sensor=self.sensor.key, fw='sim-1.0', fs=f'{self.fs:g}', ch=';'.join(self.sensor.channels),
                          **self.model.hello_params(), blk=self.block, sim=1, tarde=0, perdidas=self._skipped)


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
