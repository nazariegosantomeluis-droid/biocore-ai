"""Protocolo de texto entre una placa de sensores ESP32 y la computadora (2026-11-14).

Es el mismo esquema que el de la placa de ECG (`hardware/ecg_plugplay/protocol.py`), con el prefijo 'BIO:' y la
clave `sensor` para que una sola tubería sirva para varios sensores. Una línea por trama, terminada en '\\n', a
115200 baudios:

    BIO:HELLO,sensor=emg,fw=1.0,fs=1000,ch=EMG,unit=adc,bits=12,vref=3.3,gain=200,blk=20,sim=0
        Handshake. La placa lo manda al arrancar, cada 2 s y cuando recibe 'BIO?'. `sensor` dice qué trae
        (emg, ppg, temp); `ch` los canales separados por ';'; `unit` en qué vienen los números (adc = cuentas
        del ADC; C = grados Celsius; cuentas = lo que entrega el sensor); `sim=1` = es un simulador.
        Las claves que no se conocen se ignoran.
    BIO:D,<seq>,<m1>,<m2>,...
        Bloque de muestras. seq = índice de la primera (sirve para contar las perdidas). Cada muestra es un número
        o, si hay varios canales, los valores de cada canal separados por ';' (p. ej. 51234;60321).
    BIO:E,<texto>
        Aviso de la placa (se muestra tal cual).

De la computadora a la placa solo va 'BIO?\\n' (pide el handshake).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Optional, Sequence, Tuple, Union

from hardware.ecg_plugplay.protocol import LineReader   # se reexporta: arma líneas completas desde bytes

__all__ = ['PREFIX', 'QUERY', 'Hello', 'DataBlock', 'DeviceMessage', 'Other', 'Frame', 'LineReader', 'parse_line',
           'hello_line', 'data_line']

PREFIX = 'BIO:'
QUERY = b'BIO?\n'

_NUMBER = re.compile(r'^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$')
_BOOT_PREFIXES = ('rst:', 'ets ', 'configsip', 'clk_drv', 'mode:', 'load:', 'entry ', 'ho ', 'boot:')


@dataclass(frozen=True)
class Hello:
    params: Dict[str, str] = field(default_factory=dict)

    def number(self, key: str) -> Optional[float]:
        value = self.params.get(key)
        if value is None or not _NUMBER.match(value.strip()):
            return None
        return float(value)

    @property
    def sensor(self) -> str:
        return self.params.get('sensor', '').strip().lower()

    @property
    def fs(self) -> Optional[float]:
        return self.number('fs')

    @property
    def channels(self) -> Tuple[str, ...]:
        raw = self.params.get('ch', '')
        return tuple(c.strip() for c in raw.split(';') if c.strip())

    @property
    def unit(self) -> str:
        return self.params.get('unit', '').strip()

    @property
    def firmware(self) -> str:
        return self.params.get('fw', '?')

    @property
    def simulated(self) -> bool:
        return self.params.get('sim', '0').strip().lower() in ('1', 'si', 'sí', 'true')


@dataclass(frozen=True)
class DataBlock:
    seq: Optional[int]
    samples: Tuple[Tuple[float, ...], ...]       # una tupla por muestra, un valor por canal


@dataclass(frozen=True)
class DeviceMessage:
    text: str


@dataclass(frozen=True)
class Other:
    """Lo que no es una trama BIO. kind: 'vacia', 'ecg' (es la placa de ECG), 'repl' (MicroPython esperando),
    'traceback', 'banner', 'arranque', 'corrupta' o 'desconocida'."""

    kind: str
    text: str = ''


Frame = Union[Hello, DataBlock, DeviceMessage, Other]


def _num(text: str) -> float:
    text = text.strip()
    if not _NUMBER.match(text):
        raise ValueError(text)
    return float(text)


def parse_line(line: str) -> Frame:
    """Convierte una línea en una trama. Nunca lanza excepciones."""
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
                samples = tuple(tuple(_num(v) for v in p.split(';')) for p in parts[2:])
            except (IndexError, ValueError):
                return Other('corrupta', s)
            widths = {len(m) for m in samples}
            if not samples or len(widths) != 1 or (seq is not None and seq < 0):
                return Other('corrupta', s)
            return DataBlock(seq, samples)
        if body.startswith('E,'):
            return DeviceMessage(body[2:].strip())
        return Other('corrupta', s)
    if s.startswith('ECG:'):
        return Other('ecg', s)
    if s.startswith('>>>') or s.startswith('raw REPL'):
        return Other('repl', s)
    if s.startswith('Traceback') or s.startswith('File "') or 'Error:' in s:
        return Other('traceback', s)
    if s.startswith('MicroPython'):
        return Other('banner', s)
    if s.startswith(_BOOT_PREFIXES):
        return Other('arranque', s)
    return Other('desconocida', s)


def hello_line(**params) -> str:
    return 'BIO:HELLO,' + ','.join(f'{k}={v}' for k, v in params.items())


def data_line(seq: int, samples: Sequence[Sequence[float]]) -> str:
    def fmt(v: float) -> str:
        return str(int(v)) if float(v).is_integer() else f'{v:.4f}'
    return f'BIO:D,{seq},' + ','.join(';'.join(fmt(v) for v in m) for m in samples)
