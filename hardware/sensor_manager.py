"""Sensor manager for low-cost biomedical hardware integration."""

import logging
from typing import List, Optional

try:
    from serial.tools import list_ports
except ImportError:
    list_ports = None  # type: ignore

logger = logging.getLogger(__name__)


class SensorManager:
    """Manage serial and Bluetooth sensor devices for ESP32/Arduino."""

    def __init__(self):
        self.available_ports: List[str] = []
        self.refresh_ports()

    def refresh_ports(self) -> List[str]:
        if list_ports is None:
            logger.warning('pyserial no está disponible, no se pueden listar puertos.')
            self.available_ports = []
            return self.available_ports

        self.available_ports = [port.device for port in list_ports.comports()]
        return self.available_ports

    def choose_port(self, preferred: Optional[str] = None) -> Optional[str]:
        if preferred and preferred in self.available_ports:
            return preferred
        if self.available_ports:
            return self.available_ports[0]
        return None

    def describe_ports(self) -> str:
        if not self.available_ports:
            return 'No se detectaron puertos seriales.'
        return '\n'.join(self.available_ports)
