"""Protocolo de texto entre la placa de ECG y la computadora.

Una línea por trama, terminada en '\\n', a 115200 baudios. Todas empiezan con
'ECG:' para que la computadora reconozca la placa sin depender del puerto:

    ECG:HELLO,fw=1.0,fs=250,bits=12,vref=3.3,gain=1100,blk=10
        Handshake. La placa lo manda al arrancar, cada 2 s y cuando recibe 'ECG?'.
        Las claves que no se conocen se ignoran; las que faltan toman la configuración.
    ECG:D,<seq>,<lo>,<v1>,...,<vN>
        Bloque de muestras crudas del ADC. seq = índice de la primera muestra
        (sirve para detectar muestras perdidas); lo = electrodo suelto
        (1 = LO+, 2 = LO−, 3 = ambos, 0 = bien).
    ECG:<valor>   o   ECG:<valor>,<lo>
        Una sola muestra, para sketches mínimos (sin seq: la computadora las cuenta).
    ECG:E,<texto>
        Aviso de la placa (se muestra tal cual).

De la computadora a la placa solo va 'ECG?\\n' (pide el handshake).

Formato legado (opcional): las líneas 'ts,valor' que lee `hardware/esp32_stream.py`.
No tienen prefijo, así que no identifican al dispositivo; solo se aceptan si la
configuración lo pide (`accept_legacy=True`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Union

PREFIX = 'ECG:'
QUERY = b'ECG?\n'
MAX_LINE = 600

_NUMBER = re.compile(r'^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$')
_SPLIT_LEGACY = re.compile(r'[;,\t ]+')
_BOOT_PREFIXES = ('rst:', 'ets ', 'configsip', 'clk_drv', 'mode:', 'load:', 'entry ', 'ho ', 'boot:')


@dataclass(frozen=True)
class Hello:
    """Handshake de la placa: describe cómo muestrea."""

    params: Dict[str, str] = field(default_factory=dict)

    def number(self, key: str) -> Optional[float]:
        value = self.params.get(key)
        if value is None or not _NUMBER.match(value.strip()):
            return None
        return float(value)

    @property
    def fs(self) -> Optional[float]:
        return self.number('fs')

    @property
    def bits(self) -> Optional[int]:
        v = self.number('bits')
        return int(v) if v is not None else None

    @property
    def vref(self) -> Optional[float]:
        return self.number('vref')

    @property
    def gain(self) -> Optional[float]:
        return self.number('gain')

    @property
    def firmware(self) -> str:
        return self.params.get('fw', '?')

    @property
    def prefiltered(self) -> bool:
        """True si la placa ya manda la señal filtrada (clave filt=1)."""
        return self.params.get('filt', '0').strip() in ('1', 'si', 'sí', 'true')


@dataclass(frozen=True)
class DataBlock:
    """Muestras crudas del ADC. seq None = la placa no las numera."""

    seq: Optional[int]
    leadoff: int
    values: Tuple[float, ...]


@dataclass(frozen=True)
class LegacySample:
    """Muestra en el formato viejo 'ts,valor' (sin handshake)."""

    t: float
    value: float


@dataclass(frozen=True)
class DeviceMessage:
    """Aviso de texto de la placa (ECG:E,...)."""

    text: str


@dataclass(frozen=True)
class Other:
    """Todo lo que no es una trama de ECG.

    kind: 'vacia', 'repl' (MicroPython esperando, >>>), 'traceback' (el
    programa de la placa falló), 'banner', 'arranque', 'numerica' (números
    sin prefijo con el formato legado apagado), 'corrupta' o 'desconocida'.
    """

    kind: str
    text: str = ''


Frame = Union[Hello, DataBlock, LegacySample, DeviceMessage, Other]


def _num(text: str) -> float:
    text = text.strip()
    if not _NUMBER.match(text):
        raise ValueError(text)
    return float(text)


def parse_line(line: str, accept_legacy: bool = False) -> Frame:
    """Convierte una línea de texto en una trama. Nunca lanza excepciones."""
    s = line.strip()
    if not s:
        return Other('vacia')

    if s.startswith(PREFIX):
        body = s[len(PREFIX):].strip()
        if body.upper().startswith('HELLO'):
            params: Dict[str, str] = {}
            for part in body[5:].split(','):
                if '=' in part:
                    key, value = part.split('=', 1)
                    params[key.strip().lower()] = value.strip()
            return Hello(params)
        if body.startswith('D,'):
            parts = body.split(',')
            try:
                seq = None if parts[1].strip() in ('', '-') else int(parts[1])
                leadoff = int(parts[2])
                values = tuple(_num(p) for p in parts[3:])
            except (IndexError, ValueError):
                return Other('corrupta', s)
            if not values or (seq is not None and seq < 0):
                return Other('corrupta', s)
            return DataBlock(seq, leadoff, values)
        if body.startswith('E,'):
            return DeviceMessage(body[2:].strip())
        parts = body.split(',')
        try:
            value = _num(parts[0])
            leadoff = int(parts[1]) if len(parts) > 1 else 0
        except (ValueError, IndexError):
            return Other('corrupta', s)
        return DataBlock(None, leadoff, (value,))

    if s.startswith('>>>') or s.startswith('raw REPL'):
        return Other('repl', s)
    if s.startswith('Traceback') or s.startswith('File "') or 'Error:' in s:
        return Other('traceback', s)
    if s.startswith('MicroPython'):
        return Other('banner', s)
    if s.startswith(_BOOT_PREFIXES):
        return Other('arranque', s)

    parts = [p for p in _SPLIT_LEGACY.split(s) if p]
    if parts and all(_NUMBER.match(p) for p in parts) and len(parts) <= 4:
        if not accept_legacy:
            return Other('numerica', s)
        if len(parts) == 1:
            return LegacySample(float('nan'), float(parts[0]))
        return LegacySample(float(parts[0]), float(parts[1]))
    return Other('desconocida', s)


class LineReader:
    """Arma líneas completas a partir de bytes sueltos del puerto."""

    def __init__(self, max_line: int = MAX_LINE) -> None:
        self.max_line = max_line
        self.overflows = 0
        self._buf = bytearray()

    def feed(self, data: bytes) -> List[str]:
        if data:
            self._buf += data
        lines: List[str] = []
        while True:
            i = self._buf.find(b'\n')
            if i < 0:
                break
            raw = bytes(self._buf[:i])
            del self._buf[:i + 1]
            lines.append(raw.rstrip(b'\r').decode('utf-8', 'replace'))
        if len(self._buf) > self.max_line:
            # Basura sin salto de línea (p. ej. el arranque de la ESP32 a 74880 baudios).
            self._buf.clear()
            self.overflows += 1
        return lines

    def clear(self) -> None:
        self._buf.clear()
