"""Simulador de la placa de ECG: habla el mismo protocolo que el firmware.

Sirve para probar el módulo y para demos sin hardware. Todo lo que produce
lleva la procedencia 'SIMULACION' (Art. I de BIOCORE: lo sintético se
etiqueta siempre como simulación, nunca como sensor real).

La morfología es una suma de gaussianas (P, Q, R, S, T) por latido, con algo
de variabilidad RR, ruido, zumbido de 60 Hz y deriva de línea base. Es una
aproximación propia para pruebas: no es un modelo fisiológico validado.

Tres formas de usarlo:

    # 1) Dentro del servicio (cualquier sistema operativo):
    svc = ECGAcquisitionService(config, analizador, simulator=SimulatedECGDevice())

    # 2) Como puerto serial falso en Linux o Mac (para probar pyserial de verdad):
    python -m hardware.ecg_plugplay.simulator --pty
    # imprime algo como /dev/pts/5; úsalo con AcquisitionConfig(port='/dev/pts/5')

    # 3) Controles para pruebas: unplug(), plug(), set_leadoff(1), set_frozen(True)
"""

from __future__ import annotations

import argparse
import os
import threading
import time
from collections import deque
from typing import Deque, List, Optional

import numpy as np

from .ports import PortError, PortInfo
from .transport import Transport, TransportClosed

SIM_DEVICE = 'SIMULADOR'
SIM_PORT = PortInfo(SIM_DEVICE, 'Simulador de ECG')

# (amplitud en mV, centro en s respecto a la R, ancho en s)
_WAVES = (
    (0.15, -0.200, 0.025),    # P
    (-0.12, -0.035, 0.010),   # Q
    (1.10, 0.000, 0.011),     # R
    (-0.25, 0.035, 0.012),    # S
    (0.30, 0.280, 0.050),     # T
)


def beats_to_mv(t: np.ndarray, beats: np.ndarray) -> np.ndarray:
    """Suma de gaussianas de los latidos `beats` (tiempos de la R) en los tiempos `t`."""
    y = np.zeros_like(t, dtype=float)
    for b in beats:
        for amp, center, width in _WAVES:
            y += amp * np.exp(-0.5 * ((t - b - center) / width) ** 2)
    return y


def mv_to_counts(mv: np.ndarray, bits: int = 12, vref: float = 3.3, gain: float = 1100.0) -> np.ndarray:
    full = (1 << bits) - 1
    volts = np.asarray(mv, dtype=float) / 1000.0 * gain + vref / 2.0
    return np.clip(np.round(volts / vref * full), 0, full).astype(int)


class SimulatedECGDevice:
    """Placa de ECG simulada (thread-safe)."""

    def __init__(self, fs: float = 250.0, hr_bpm: float = 72.0, block: int = 10, speed: float = 1.0,
                 bits: int = 12, vref: float = 3.3, gain: float = 1100.0, noise_mv: float = 0.02,
                 mains_mv: float = 0.03, wander_mv: float = 0.10, hrv: float = 0.03, seed: int = 7,
                 firmware: str = 'sim-1.0', send_hello: bool = True) -> None:
        self.fs = float(fs)
        self.hr_bpm = float(hr_bpm)
        self.block = int(block)
        self.speed = float(speed)
        self.bits, self.vref, self.gain = int(bits), float(vref), float(gain)
        self.noise_mv, self.mains_mv, self.wander_mv, self.hrv = noise_mv, mains_mv, wander_mv, hrv
        self.seed = seed
        self.firmware = firmware
        self.send_hello = send_hello
        self.plugged = True
        self.frozen = False
        self.leadoff = 0
        self._lock = threading.RLock()
        self._reset_stream()

    # ------------------------------------------------------------ controles
    def unplug(self) -> None:
        with self._lock:
            self.plugged = False

    def plug(self) -> None:
        """Vuelve a conectar: como encender la placa de nuevo (seq empieza en 0)."""
        with self._lock:
            self.plugged = True
            self._reset_stream()

    def set_leadoff(self, value: int) -> None:
        with self._lock:
            self.leadoff = int(value)

    def set_frozen(self, value: bool) -> None:
        """Congela la placa: el cable sigue conectado pero no llegan datos."""
        with self._lock:
            if self.frozen and not value and self._t0 is not None:
                # Al descongelar no manda de golpe lo que "no midió".
                self._t0 = time.monotonic() - self._seq / (self.fs * self.speed)
            self.frozen = bool(value)

    def set_hr(self, bpm: float) -> None:
        with self._lock:
            self.hr_bpm = float(bpm)

    # ------------------------------------------------------------ protocolo
    def hello_line(self) -> str:
        return (f'ECG:HELLO,fw={self.firmware},fs={self.fs:g},bits={self.bits},vref={self.vref:g},'
                f'gain={self.gain:g},blk={self.block},sim=1')

    def handle_input(self, data: bytes) -> None:
        with self._lock:
            if b'ECG?' in data and self.send_hello and not self.frozen:
                self._pending.append(self.hello_line())

    def lines_due(self, now: Optional[float] = None) -> List[str]:
        """Líneas que la placa ya habría mandado a la hora `now` (time.monotonic())."""
        now = time.monotonic() if now is None else now
        with self._lock:
            if not self.plugged:
                return []
            if self._t0 is None:
                self._t0 = now
                if self.send_hello:
                    self._pending.append(self.hello_line())
            out = list(self._pending)
            self._pending.clear()
            if self.frozen:
                return out
            due = int((now - self._t0) * self.fs * self.speed)
            while self._seq + self.block <= due:
                t_dev = self._seq / self.fs
                if self.send_hello and t_dev - self._last_hello >= 2.0:
                    out.append(self.hello_line())
                    self._last_hello = t_dev
                out.append(self._data_line())
            return out

    # ------------------------------------------------------------ interno
    def _reset_stream(self) -> None:
        self._t0: Optional[float] = None
        self._seq = 0
        self._beats: Deque[float] = deque()
        self._next_beat = 0.35
        self._last_hello = 0.0
        self._pending: Deque[str] = deque()
        self._rng = np.random.default_rng(self.seed)

    def _ecg_mv(self, t: np.ndarray) -> np.ndarray:
        while self._next_beat < t[-1] + 0.8:
            self._beats.append(self._next_beat)
            rr = 60.0 / self.hr_bpm * (1.0 + self.hrv * self._rng.standard_normal())
            self._next_beat += float(np.clip(rr, 0.25, 2.5))
        while self._beats and self._beats[0] < t[0] - 0.8:
            self._beats.popleft()
        y = beats_to_mv(t, np.fromiter(self._beats, dtype=float))
        y += self.noise_mv * self._rng.standard_normal(t.size)
        y += self.mains_mv * np.sin(2 * np.pi * 60.0 * t)
        y += self.wander_mv * np.sin(2 * np.pi * 0.25 * t)
        return y

    def _data_line(self) -> str:
        t = (self._seq + np.arange(self.block)) / self.fs
        counts = mv_to_counts(self._ecg_mv(t), self.bits, self.vref, self.gain)
        lo = self.leadoff
        if lo:
            counts[:] = (1 << self.bits) - 1      # como el AD8232: la salida se va al riel
        line = f'ECG:D,{self._seq},{lo},' + ','.join(str(int(c)) for c in counts)
        self._seq += self.block
        return line


class SimulatedTransport(Transport):
    """Transporte en memoria hacia un SimulatedECGDevice."""

    provenance = 'SIMULACION'

    def __init__(self, device: SimulatedECGDevice) -> None:
        if not device.plugged:
            raise PortError('no_existe', SIM_DEVICE, 'El simulador está desconectado.')
        self.device = device
        self.name = SIM_DEVICE
        self.label = 'Simulador de ECG'

    def read(self, timeout: float) -> bytes:
        deadline = time.monotonic() + timeout
        while True:
            if not self.device.plugged:
                raise TransportClosed('se desconectó el simulador')
            lines = self.device.lines_due()
            if lines:
                return ('\n'.join(lines) + '\n').encode()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return b''
            time.sleep(min(0.004, remaining))

    def write(self, data: bytes) -> None:
        if not self.device.plugged:
            raise TransportClosed('se desconectó el simulador')
        self.device.handle_input(data)

    def close(self) -> None:
        pass


class PtyECGDevice:
    """Expone un SimulatedECGDevice como puerto serial falso (solo Linux y Mac).

    `path` es el puerto que se abre con pyserial. `close()` simula desconectar el cable.
    """

    def __init__(self, device: SimulatedECGDevice) -> None:
        import pty
        import tty

        self.device = device
        self._master, slave = pty.openpty()
        tty.setraw(slave)
        os.set_blocking(self._master, False)   # sin lector, los datos se pierden como en un UART real
        self.path = os.ttyname(slave)
        self._slave = slave
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name='ecg-pty', daemon=True)
        self._thread.start()

    def _run(self) -> None:
        import select

        while not self._stop.is_set():
            try:
                ready, _, _ = select.select([self._master], [], [], 0.005)
                if ready:
                    self.device.handle_input(os.read(self._master, 256))
                lines = self.device.lines_due()
                if lines:
                    os.write(self._master, ('\n'.join(lines) + '\n').encode())
            except BlockingIOError:
                continue
            except OSError:
                break

    def close(self) -> None:
        self._stop.set()
        self._thread.join(1.0)
        for fd in (self._master, self._slave):
            try:
                os.close(fd)
            except OSError:
                pass


def main() -> None:
    ap = argparse.ArgumentParser(description='Placa de ECG simulada (SIMULACIÓN, no es un sensor).')
    ap.add_argument('--pty', action='store_true', help='crear un puerto serial falso (Linux o Mac)')
    ap.add_argument('--hr', type=float, default=72.0, help='frecuencia cardiaca simulada (lpm)')
    args = ap.parse_args()
    if not args.pty:
        ap.error('Por ahora el modo de línea de comandos solo crea un puerto falso: usa --pty.')
    pty_dev = PtyECGDevice(SimulatedECGDevice(hr_bpm=args.hr))
    print(f'Puerto simulado: {pty_dev.path}  (Ctrl+C para salir)')
    print(f"Úsalo con AcquisitionConfig(port='{pty_dev.path}')")
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        pty_dev.close()


if __name__ == '__main__':
    main()
