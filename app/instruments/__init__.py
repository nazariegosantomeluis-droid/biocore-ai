"""Instrumentos (T2, 2026-11-18): las piezas de los laboratorios que una estación de la ruta puede montar.

Cada instrumento recibe un `InstrumentContext` (`base.py`): con `PAGE` se dibuja como en la página de siempre; con
`station_context(prefijo)` se dibuja dentro de una estación, con sus claves propias y sin tocar el menú lateral.
Este paquete nunca importa `app.main` (la página importa a los instrumentos, no al revés)."""
