"""Placa de sensores ESP32 de BIOCORE (2026-11-14): firmware, protocolo, conexión, simulador y calidad.

- `protocol`: tramas de texto `BIO:HELLO` / `BIO:D` / `BIO:E` (mismo esquema que la placa de ECG).
- `sensors`: el catálogo (EMG con MyoWare 2.0, pulso por luz con MAX30102 y temperatura con DS18B20): conexiones,
  conversión a unidades físicas y límites.
- `serial_backend`: busca la placa por USB, verifica el handshake y lee; entra al servicio del EEG en vivo
  (`hardware/eeg_live/service.py`), con sus estados y su regla de procedencia.
- `simulator`: la placa simulada de la práctica, con un modelo por sensor (siempre `sim=1`, SIMULACIÓN).
- `quality`: avisos de calidad de cada sensor (heurísticas de ingeniería).
- `firmware/`: los programas de MicroPython que se guardan en la placa como `main.py`.
"""

from .protocol import DataBlock, DeviceMessage, Hello, Other, data_line, hello_line, parse_line
from .sensors import EMG, PPG, SENSORS, TEMP, BioSensor, find_sensor, get_sensor
from .serial_backend import SerialBioBackend
from .simulator import SimulatedBioBoard

__all__ = ['BioSensor', 'DataBlock', 'DeviceMessage', 'EMG', 'Hello', 'Other', 'PPG', 'SENSORS', 'SerialBioBackend',
           'SimulatedBioBoard', 'TEMP', 'data_line', 'find_sensor', 'get_sensor', 'hello_line', 'parse_line']
