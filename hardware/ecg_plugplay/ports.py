"""Puertos seriales: cuáles vale la pena sondear y cómo abrirlos sin sorpresas.

Lecciones de las pruebas con la ESP32:

- En Windows, emparejar un aparato Bluetooth (como el casco Unicorn) crea
  puertos COM que no son la placa; abrirlos tarda y falla con «semaphore
  timeout». Aquí nunca se sondean.
- «Access is denied» en Windows significa que otro programa tiene el puerto
  (casi siempre Thonny o el monitor serie de Arduino).
- Abrir el puerto con DTR y RTS en alto reinicia la ESP32 en muchas placas;
  se abre con los dos en bajo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence

from .config import KNOWN_USB_IDS, AcquisitionConfig


@dataclass(frozen=True)
class PortInfo:
    """Un puerto serial tal como lo reporta el sistema operativo."""

    device: str
    description: str = ''
    vid: Optional[int] = None
    pid: Optional[int] = None
    hwid: str = ''
    manufacturer: str = ''
    serial_number: str = ''

    @property
    def is_bluetooth(self) -> bool:
        text = f'{self.description} {self.hwid} {self.manufacturer} {self.device}'.lower()
        return 'bluetooth' in text or 'bthenum' in text or 'rfcomm' in self.device.lower()

    @property
    def known_chip(self) -> Optional[str]:
        if self.vid is None:
            return None
        for vid, pid, name in KNOWN_USB_IDS:
            if vid == self.vid and (pid is None or pid == self.pid):
                return name
        return None

    @property
    def label(self) -> str:
        return self.known_chip or self.description or self.device


def system_ports() -> List[PortInfo]:
    """Puertos que ve el sistema operativo (necesita pyserial)."""
    from serial.tools import list_ports

    return [
        PortInfo(
            device=p.device,
            description=p.description or '',
            vid=p.vid,
            pid=p.pid,
            hwid=p.hwid or '',
            manufacturer=p.manufacturer or '',
            serial_number=p.serial_number or '',
        )
        for p in list_ports.comports()
    ]


def candidate_ports(ports: Sequence[PortInfo], config: AcquisitionConfig) -> List[PortInfo]:
    """Puertos a sondear, en orden: primero los chips conocidos.

    Se descartan los Bluetooth y los que no son USB (COM1, /dev/ttyS0...).
    Si la configuración fija un puerto, solo se usa ese.
    """
    if config.port:
        fixed = [p for p in ports if p.device == config.port]
        return fixed or [PortInfo(config.port, 'puerto fijado en la configuración')]
    usb = [p for p in ports if not p.is_bluetooth and p.vid is not None]
    return sorted(usb, key=lambda p: (p.known_chip is None, p.device))


class PortError(Exception):
    """No se pudo abrir un puerto. `kind` dice por qué y `message` qué hacer."""

    def __init__(self, kind: str, device: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind          # 'ocupado', 'permiso', 'no_responde', 'no_existe' u 'otro'
        self.device = device
        self.message = message


def explain_serial_error(exc: BaseException, device: str) -> PortError:
    """Traduce los errores típicos de pyserial a un motivo y una acción."""
    t = str(exc).lower()
    if 'access is denied' in t or 'acceso denegado' in t or 'busy' in t:
        return PortError('ocupado', device,
                         f'{device} está ocupado por otro programa. Cierra Thonny, el monitor serie de Arduino '
                         'o cualquier terminal que lo use; se reintentará solo.')
    if 'permission denied' in t:
        return PortError('permiso', device,
                         f'Sin permiso para abrir {device}. En Linux agrega tu usuario al grupo dialout '
                         '(sudo usermod -a -G dialout $USER) y vuelve a iniciar sesión.')
    if 'semaphore' in t or 'semáforo' in t or ', 121)' in t:
        return PortError('no_responde', device,
                         f'{device} no responde: casi siempre es un puerto Bluetooth, no la placa.')
    if 'filenotfound' in t or 'cannot find' in t or 'no such file' in t or 'no se puede encontrar' in t:
        return PortError('no_existe', device, f'{device} ya no existe (se desconectó o cambió de número).')
    return PortError('otro', device, f'No se pudo abrir {device}: {exc}')


def open_serial(port: PortInfo, config: AcquisitionConfig):
    """Abre el puerto sin reiniciar la placa. Lanza PortError si no se puede."""
    import serial

    ser = serial.Serial()
    ser.port = port.device
    ser.baudrate = config.baudrate
    ser.timeout = 0.05
    ser.write_timeout = 0.5
    ser.dtr = config.assert_dtr
    ser.rts = False
    try:
        ser.open()
    except (serial.SerialException, OSError, ValueError) as exc:
        raise explain_serial_error(exc, port.device) from exc
    try:
        ser.reset_input_buffer()
    except Exception:
        pass
    return ser
