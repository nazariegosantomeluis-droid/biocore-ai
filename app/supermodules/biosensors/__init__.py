"""Placa de sensores ESP32 de BIOCORE dentro de la app (2026-11-14).

- `live_service.py`: el servicio de la placa real de cada sensor (uno por proceso) y el de su práctica con la placa
  simulada.
- `source.py`: la fuente «sensor en vivo» genérica de la barra lateral (estados, procedencia, avisos).
- `tutorial.py`: el tutorial genérico de un sensor (material, conexiones, firmware, colocación, estados, límites y
  práctica), armado con el catálogo de `hardware/biosensors/sensors.py`.
- `emg.py`: lo propio del EMG Muscle Lab (controles de la placa simulada, RMS, práctica).
"""
