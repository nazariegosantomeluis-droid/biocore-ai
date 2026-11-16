"""Conexión con una placa de sensores ESP32 por USB: busca el puerto, verifica el `BIO:HELLO` y lee bloques.

Cumple el contrato de `hardware/eeg_live/backends.py` (open / read / close), así que la placa entra al mismo
servicio que el EEG en vivo: estados, búfer, procedencia y reconexión automática.

- `open()` revisa los puertos USB (primero los chips conocidos; se salta los Bluetooth), manda 'BIO?' y espera el
  handshake del sensor que se pidió. Si en un puerto hay otra cosa, dice qué: la placa de ECG, otra placa de
  sensores, MicroPython esperando órdenes (Thonny abierto) o un programa que se detuvo con un error.
- `read()` arma líneas, cuenta las muestras que se perdieron en el cable (saltos en `seq`) y convierte a unidades
  físicas con la función del sensor (`sensors.py`).
- La procedencia es SENSOR_REAL salvo que el HELLO diga `sim=1` (el simulador de práctica).

Puertos y errores: los mismos ayudantes que la placa de ECG (`hardware/ecg_plugplay/ports.py`, `transport.py`).
"""

from __future__ import annotations

import time
from collections import deque
from typing import Callable, Deque, Dict, List, Optional, Tuple

import numpy as np

from hardware.ecg_plugplay.config import AcquisitionConfig
from hardware.ecg_plugplay.ports import PortError, PortInfo, candidate_ports, system_ports
from hardware.ecg_plugplay.transport import SerialTransport, Transport, TransportClosed
from hardware.eeg_live.backends import Backend, BackendError, StreamDescription
from hardware.eeg_live.devices import SENSOR_REAL, SIMULACION

from .protocol import QUERY, DataBlock, DeviceMessage, Hello, LineReader, Other, parse_line
from .sensors import BioSensor, find_sensor

PROBE_TIMEOUT_S = 2.5
READ_TIMEOUT_S = 0.01


def usb_ports() -> List[PortInfo]:
    """Puertos USB a revisar, primero los chips conocidos (CP210x, CH340, FTDI…)."""
    try:
        return candidate_ports(system_ports(), AcquisitionConfig())
    except ImportError as exc:
        raise BackendError(f'pyserial no está instalado ({exc}). Instálalo con «pip install pyserial».') from exc


def open_serial_transport(port: PortInfo) -> Transport:
    return SerialTransport(port, AcquisitionConfig())       # 115200 baudios, sin reiniciar la placa


def explain_probe(port: str, seen: set, sensor: BioSensor, timeout_s: float) -> str:
    """Por qué un puerto no resultó ser la placa del sensor pedido."""
    if 'ecg' in seen:
        return f'{port} es la placa de ECG de BIOCORE: úsala en el ECG Lab.'
    if 'repl' in seen or 'banner' in seen:
        return (f'En {port} hay MicroPython esperando órdenes («>>>»): el firmware no está corriendo. Guarda el '
                'archivo como main.py en la placa, cierra Thonny y presiona EN.')
    if 'traceback' in seen:
        return f'El programa de la placa en {port} se detuvo con un error: ábrela en Thonny para leerlo.'
    return f'{port} no respondió como una placa de {sensor.key.upper()} de BIOCORE en {timeout_s:.1f} s.'


class SerialBioBackend(Backend):
    """Una placa ESP32 de BIOCORE con el sensor `sensor`, por USB (o por el simulador, con los mismos pasos)."""

    def __init__(self, sensor: BioSensor, list_ports: Optional[Callable[[], List[PortInfo]]] = None,
                 open_transport: Optional[Callable[[PortInfo], Transport]] = None,
                 probe_timeout_s: float = PROBE_TIMEOUT_S, clock: Callable[[], float] = time.monotonic) -> None:
        self.sensor = sensor
        self._list_ports = list_ports or usb_ports
        self._open_transport = open_transport or open_serial_transport
        self.probe_timeout_s = probe_timeout_s
        self._clock = clock
        self._transport: Optional[Transport] = None
        self._reader = LineReader()
        self._hello: Optional[Hello] = None
        self._next_seq: Optional[int] = None
        self._port = ''
        self.lost_in_transit = 0
        self.messages: Deque[str] = deque(maxlen=5)

    # ------------------------------------------------------------ apertura
    def open(self) -> StreamDescription:
        ports = self._list_ports()
        if not ports:
            raise BackendError('No hay ninguna placa conectada por USB. Conecta la ESP32 con un cable que transmita '
                               'datos (algunos solo cargan).')
        reasons: List[str] = []
        for port in ports:
            try:
                transport = self._open_transport(port)
            except PortError as exc:
                reasons.append(exc.message)
                continue
            except Exception as exc:
                reasons.append(f'No se pudo abrir {port.device}: {exc}')
                continue
            hello, why = self._probe(transport, port.device)
            if hello is None:
                try:
                    transport.close()
                except Exception:
                    pass
                reasons.append(why)
                continue
            return self._accept(transport, port.device, hello)
        raise BackendError(' '.join(reasons))

    def _probe(self, transport: Transport, device: str) -> Tuple[Optional[Hello], str]:
        reader = LineReader()
        seen: set = set()
        deadline = self._clock() + self.probe_timeout_s
        last_query = -1e9
        try:
            while self._clock() < deadline:
                if self._clock() - last_query >= 1.0:
                    transport.write(QUERY)
                    last_query = self._clock()
                for line in reader.feed(transport.read(0.05)):
                    frame = parse_line(line)
                    if isinstance(frame, Hello):
                        if frame.sensor == self.sensor.key:
                            self._reader = reader            # conserva lo que ya llegó después del HELLO
                            return frame, ''
                        other = find_sensor(frame.sensor)
                        nombre = other.name if other else f'«{frame.sensor or "?"}»'
                        return None, f'{device} es una placa de {nombre}, no de {self.sensor.key.upper()}.'
                    if isinstance(frame, Other):
                        seen.add(frame.kind)
        except TransportClosed as exc:
            return None, f'{device} se desconectó mientras se verificaba ({exc}).'
        return None, explain_probe(device, seen, self.sensor, self.probe_timeout_s)

    def _accept(self, transport: Transport, device: str, hello: Hello) -> StreamDescription:
        fs = hello.fs
        if not fs or fs <= 0:
            transport.close()
            raise BackendError(f'La placa en {device} no dice su frecuencia de muestreo (fs) en el HELLO.')
        channels = hello.channels or self.sensor.channels
        if len(channels) != len(self.sensor.channels):
            transport.close()
            raise BackendError(f'La placa en {device} manda {len(channels)} canales y el sensor '
                               f'{self.sensor.key.upper()} usa {len(self.sensor.channels)}.')
        self._transport, self._hello, self._port = transport, hello, device
        self._next_seq = None
        provenance = SIMULACION if hello.simulated else SENSOR_REAL
        unit_note = f'{self.sensor.unit_label}, convertidos de «{hello.unit or "?"}» con los datos del HELLO.'
        detail = f'placa {self.sensor.key.upper()} en {device} (firmware {hello.firmware})'
        return StreamDescription(tuple(self.sensor.channels), float(fs), detail, unit_note, provenance)

    # ------------------------------------------------------------ lectura
    def read(self) -> np.ndarray:
        if self._transport is None or self._hello is None:
            raise BackendError('La placa no está abierta.')
        try:
            data = self._transport.read(READ_TIMEOUT_S)
        except TransportClosed as exc:
            raise BackendError(str(exc)) from exc
        width = len(self.sensor.channels)
        samples: List[Tuple[float, ...]] = []
        for line in self._reader.feed(data):
            frame = parse_line(line)
            if isinstance(frame, DataBlock):
                if len(frame.samples[0]) != width:
                    continue
                if frame.seq is not None:
                    if self._next_seq is not None and frame.seq > self._next_seq:
                        self.lost_in_transit += frame.seq - self._next_seq
                    self._next_seq = frame.seq + len(frame.samples)
                samples.extend(frame.samples)
            elif isinstance(frame, Hello):
                if frame.sensor != self.sensor.key:
                    raise BackendError(f'La placa en {self._port} ahora dice ser de «{frame.sensor}».')
                if frame.fs and self._hello.fs and frame.fs != self._hello.fs:
                    raise BackendError(f'La placa cambió de frecuencia de muestreo ({self._hello.fs:g} → '
                                       f'{frame.fs:g} Hz); se vuelve a abrir.')
                self._hello = frame
            elif isinstance(frame, DeviceMessage):
                self.messages.append(frame.text)
        if not samples:
            return np.zeros((width, 0))
        return self.sensor.convert(np.asarray(samples, dtype=float).T, self._hello)

    def close(self) -> None:
        transport, self._transport = self._transport, None
        if transport is not None:
            try:
                transport.close()
            except Exception:
                pass

    def status(self) -> Dict[str, object]:
        """Contadores para la interfaz: lo que dice la placa de sí misma y lo que se perdió en el cable."""
        hello = self._hello
        return {
            'firmware': hello.firmware if hello else None,
            'tarde_en_la_placa': int(hello.number('tarde') or 0) if hello else 0,
            'perdidas_en_la_placa': int(hello.number('perdidas') or 0) if hello else 0,
            'perdidas_en_el_cable': self.lost_in_transit,
            'avisos': list(self.messages),
        }
