"""Las unidades de la Ruta, en el orden del diseño firmado (T4, 2026-11-18).

Una unidad sin sus instrumentos o sin su contenido firmado no se dibuja: queda listada como pendiente, con lo que le
falta (diseño, «Una estación sin contenido firmado no existe»).
"""

from app.supermodules.ruta import corazon, integracion

UNITS = (corazon.UNIT, integracion.UNIT)
UNIT_BY_KEY = {u.key: u for u in UNITS}

# (título, lo que le falta), en el orden del diseño: Corazón, Respiración, Cerebro, Músculo, Integración.
PENDING_UNITS = (
    ("Unidad Respiración", "convertir el laboratorio de Respiración en instrumento (hoy dibuja sus controles en el "
                           "menú lateral); la explicación clínica por escenario del Detective sigue sin firma"),
    ("Unidad Cerebro", "convertir el EEG en instrumento; el cierre (arousal → taquicardia con la regla BAR firmada) "
                       "llama al compositor después de guardar el EEG"),
    ("Unidad Músculo", "convertir el EMG en instrumento; el cierre espera la firma de la ficha músculo → autonómico "
                       "(docs/contenido/fichas_acoplamientos.md)"),
)
