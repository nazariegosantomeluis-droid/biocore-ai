"""Las unidades de la Ruta, en el orden del diseño firmado (T4, 2026-11-18): Corazón, Respiración, Cerebro, Músculo e
Integración.

Una estación sin contenido firmado no se dibuja: queda en la lista de pendientes de su unidad (`Unit.pending`), con lo
que le falta (diseño, «Una estación sin contenido firmado no existe»). Una unidad entera sin sus instrumentos tampoco:
iría en `PENDING_UNITS`, que hoy está vacía.
"""

from app.supermodules.ruta import cerebro, corazon, integracion, musculo, respiracion

UNITS = (corazon.UNIT, respiracion.UNIT, cerebro.UNIT, musculo.UNIT, integracion.UNIT)
UNIT_BY_KEY = {u.key: u for u in UNITS}

# (título, lo que le falta) de una unidad que todavía no se puede recorrer.
PENDING_UNITS: tuple = ()
