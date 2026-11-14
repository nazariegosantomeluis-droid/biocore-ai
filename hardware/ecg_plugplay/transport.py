"""Transportes: de dónde salen los bytes.

`SerialTransport` lee la placa real por USB. El servicio solo conoce esta
interfaz (read / write / close), así que el simulador (`simulator.py`) entra
por el mismo camino y un transporte BLE se podría agregar sin tocar el resto.

`provenance` declara de dónde viene el dato, con los nombres del UPS de
BIOCORE: 'SENSOR_REAL' para hardware que respondió al handshake y
'SIMULACION' para el simulador.
"""

from __future__ import annotations

from .config import AcquisitionConfig
from .ports import PortInfo, open_serial


class TransportClosed(Exception):
    """El dispositivo dejó de estar disponible (cable fuera, puerto caído)."""


class Transport:
    """Interfaz mínima que usa el servicio."""

    name: str = ''
    label: str = ''
    provenance: str = 'SENSOR_REAL'

    def read(self, timeout: float) -> bytes:  # pragma: no cover - interfaz
        raise NotImplementedError

    def write(self, data: bytes) -> None:  # pragma: no cover - interfaz
        raise NotImplementedError

    def close(self) -> None:  # pragma: no cover - interfaz
        raise NotImplementedError


class SerialTransport(Transport):
    """Puerto serial real (pyserial)."""

    provenance = 'SENSOR_REAL'

    def __init__(self, port: PortInfo, config: AcquisitionConfig) -> None:
        self.port = port
        self.name = port.device
        self.label = port.label
        self._ser = open_serial(port, config)

    def read(self, timeout: float) -> bytes:
        ser = self._ser
        try:
            if ser.timeout != timeout:
                ser.timeout = timeout
            waiting = ser.in_waiting
            return ser.read(waiting if waiting > 0 else 1)
        except Exception as exc:  # pyserial lanza tipos distintos según el sistema al desconectar
            raise TransportClosed(f'{self.name} dejó de responder ({exc})') from exc

    def write(self, data: bytes) -> None:
        try:
            self._ser.write(data)
        except Exception as exc:
            raise TransportClosed(f'no se pudo escribir en {self.name} ({exc})') from exc

    def close(self) -> None:
        try:
            self._ser.close()
        except Exception:
            pass
