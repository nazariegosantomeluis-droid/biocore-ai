"""Ayudantes de las pruebas de la placa de sensores ESP32 (EMG, pulso por luz y temperatura).

- `FastClock` y `wait`: tiempo acelerado para la placa simulada y espera con límite.
- `ScriptTransport`: un puerto que entrega líneas escritas a mano.
- `firmware_running()`: corre un firmware de MicroPython en la computadora, con los módulos simulados de
  `tests/fakes_micropython`, y lo conecta a un pseudo-terminal que se lee con pyserial de verdad.
- `Max30102Double`: un MAX30102 a nivel de registros (los de su hoja de datos), para el bus I2C simulado: FIFO de 32
  lugares con sus punteros, contador de muestras perdidas, reinicio y modo SpO2 a la frecuencia configurada.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Optional, Tuple

from hardware.ecg_plugplay.transport import Transport, TransportClosed

RAIZ = Path(__file__).resolve().parents[1]
FAKES = str(RAIZ / 'tests' / 'fakes_micropython')
FAKE_MODULES = ('machine', 'micropython', 'onewire', 'ds18x20')


class FastClock:
    def __init__(self, speed: float = 10.0) -> None:
        self.speed, self.t0 = speed, time.monotonic()

    def __call__(self) -> float:
        return (time.monotonic() - self.t0) * self.speed


def wait(predicate, timeout=8.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return predicate()


class ScriptTransport(Transport):
    """Transporte de prueba: entrega las líneas que se le den, una por lectura, y registra lo que se le escribe."""

    def __init__(self, lines, closed_after=None):
        self.lines, self.written, self.reads, self.closed_after = list(lines), [], 0, closed_after
        self.name = 'COM9'

    def read(self, timeout):
        self.reads += 1
        if self.closed_after is not None and self.reads > self.closed_after:
            raise TransportClosed('COM9 se desconectó')
        if not self.lines:
            return b''
        return (self.lines.pop(0) + '\n').encode()

    def write(self, data):
        self.written.append(data)

    def close(self):
        pass


class Terminal:
    """El lado de la placa del pseudo-terminal: lo que el firmware usa como stdin y stdout."""

    def __init__(self, fd):
        self.fd = fd

    def fileno(self):
        return self.fd

    def read(self, n=1):
        try:
            return os.read(self.fd, n).decode('utf-8', 'replace')
        except OSError:
            return ''

    def write(self, texto):
        try:
            os.write(self.fd, texto.encode())
        except (BlockingIOError, OSError):
            pass


@contextmanager
def firmware_running(path: Path, prepare: Optional[Callable[[], None]] = None):
    """Corre `ejecutar()` del firmware en un hilo. `prepare()` se llama con los módulos simulados ya cargados (para
    poner la fuente del ADC, los dispositivos del bus I2C o las sondas 1-Wire). Entrega (módulo, puerto)."""
    import pty
    import tty

    sys.path.insert(0, FAKES)
    for name in FAKE_MODULES:
        sys.modules.pop(name, None)
    master = slave = None
    hilo = fw = None
    try:
        spec = importlib.util.spec_from_file_location(f'firmware_{path.stem}', path)
        fw = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fw)
        if prepare is not None:
            prepare()
        master, slave = pty.openpty()
        tty.setraw(slave)
        os.set_blocking(master, False)
        fw.ENTRADA = fw.SALIDA = Terminal(master)
        fw.DETENER = False
        hilo = threading.Thread(target=fw.ejecutar, daemon=True)
        hilo.start()
        yield fw, os.ttyname(slave)
    finally:
        if fw is not None:
            fw.DETENER = True
        if hilo is not None:
            hilo.join(2.0)
        for fd in (master, slave):
            if fd is not None:
                os.close(fd)
        while FAKES in sys.path:
            sys.path.remove(FAKES)
        for name in FAKE_MODULES:
            sys.modules.pop(name, None)


class Max30102Double:
    """MAX30102 a nivel de registros. `fuente(t)` da (rojo, infrarrojo) en cuentas de 18 bits en el segundo t."""

    RATES = {0: 50, 1: 100, 2: 200, 3: 400, 4: 800, 5: 1000, 6: 1600, 7: 3200}      # SPO2_CFG bits 4:2

    def __init__(self, fuente: Callable[[float], Tuple[int, int]], part_id: int = 0x15,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.fuente, self.part_id, self._clock = fuente, part_id, clock
        self._lock = threading.Lock()
        self.regs = {}
        self.fifo = []                 # lo que hay en la FIFO, de la más vieja a la más nueva
        self.wr = self.rd = self.ovf = 0
        self.produced = 0              # muestras generadas desde que se activó el modo SpO2
        self.thrown = 0                # muestras que se tiraron con la FIFO llena
        self.pause = 0.0               # las pruebas lo suben para simular un ciclo atrasado
        self._t0 = None

    def _reset(self):
        self.regs, self.fifo = {}, []
        self.wr = self.rd = self.ovf = 0
        self._t0 = None

    def _fs(self):
        return self.RATES[(self.regs.get(0x0A, 0) >> 2) & 0x7]

    def _advance(self):
        if self._t0 is None or self.regs.get(0x09, 0) & 0x7 != 0x3:
            return
        due = int((self._clock() - self._t0) * self._fs())
        while self.produced < due:
            t = self.produced / self._fs()
            self.produced += 1
            if len(self.fifo) == 32:
                if not self.regs.get(0x08, 0) & 0x10:            # sin FIFO circular: la nueva se pierde
                    self.ovf = min(self.ovf + 1, 0x1F)
                    self.thrown += 1
                    continue
                self.fifo.pop(0)                                  # circular: se pierde la más vieja
                self.rd = (self.rd + 1) & 0x1F
                self.ovf = min(self.ovf + 1, 0x1F)
                self.thrown += 1
            self.fifo.append(self.fuente(t))
            self.wr = (self.wr + 1) & 0x1F

    def leer(self, reg, n):
        if self.pause:
            time.sleep(self.pause)
            self.pause = 0.0
        with self._lock:
            self._advance()
            if reg == 0xFF:
                return bytes([self.part_id] * n)
            if reg == 0x04:
                return bytes([self.wr])
            if reg == 0x05:
                return bytes([self.ovf])
            if reg == 0x06:
                return bytes([self.rd])
            if reg == 0x07:
                out = bytearray()
                for _ in range(n // 6):
                    red, ir = self.fifo.pop(0) if self.fifo else (0, 0)
                    self.rd = (self.rd + 1) & 0x1F
                    self.ovf = 0                                  # se borra al sacar una muestra completa
                    for value in (red, ir):
                        out += bytes([(value >> 16) & 0x03, (value >> 8) & 0xFF, value & 0xFF])
                return bytes(out)
            return bytes([self.regs.get(reg, 0)] * n)

    def escribir(self, reg, datos):
        with self._lock:
            value = datos[0]
            if reg == 0x09 and value & 0x40:
                self._reset()                                     # el bit de reinicio se borra solo
                return
            if reg == 0x04:
                self.wr = value & 0x1F
            elif reg == 0x05:
                self.ovf = value & 0x1F
            elif reg == 0x06:
                self.rd = value & 0x1F
            else:
                self.regs[reg] = value
            if reg == 0x09 and value & 0x7 == 0x3:
                self._t0, self.produced, self.fifo = self._clock(), 0, []
