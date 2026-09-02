"""
Impresión clínica humana — juicio sobre un snapshot real del UPS.

Deliberadamente en su propio archivo, separado de `schema.py`
(`PhysiologicalDescriptor`/`PhysiologicalEvent`) y de
`clinical_impression_repository.py` (separado de `repository.py`): una
impresión clínica es un tipo de dato distinto de una medición, y esa
distinción vive también en la organización de archivos, no solo en el
nombre de la clase.

Nunca lleva `Provenance` ni `confidence`. Esos dos campos están calibrados
en `schema.py` (`CONFIDENCE_REFERENCE`) para expresar cuánta confianza
merece una OBSERVACIÓN NUMÉRICA (sensor real, simulación, valor derivado)
— `default_confidence()` hace un lookup directo en ese diccionario sin
fallback, así que cualquier procedencia nueva que se le añadiera
necesitaría una banda de confianza numérica para no romper esa función.
Ponerle una banda a un juicio humano fingiría una precisión medida que no
existe; no dársela dejaría una mina (`KeyError`) para el primer llamador
que la use. Por eso `ClinicalImpression` no toca ese enum en absoluto — es
un tipo aparte, sin ningún campo de certeza numérica. La incertidumbre, si
existe, se expresa en prosa dentro de `notes`, como en una nota clínica
real.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

__all__ = ["ImpressionCategory", "ClinicalImpression"]


class ImpressionCategory(str, Enum):
    """Hacia dónde apunta la atención clínica — un juicio humano, nunca un
    umbral calculado (eso es `EventSeverity`, deliberadamente distinta,
    ver `schema.py`). Ligada a los dos dominios que el UPS modela hoy
    (cardiovascular/respiratorio); ampliar esta lista a otros sistemas es
    una decisión de esquema, no un string suelto en un caller."""

    ESTABLE = "estable"
    PREOCUPACION_CARDIOVASCULAR = "preocupacion_cardiovascular"
    PREOCUPACION_RESPIRATORIA = "preocupacion_respiratoria"
    PREOCUPACION_COMBINADA = "preocupacion_combinada"
    REQUIERE_SEGUIMIENTO = "requiere_seguimiento"
    CRITICO = "critico"


@dataclass(frozen=True)
class ClinicalImpression:
    """Juicio clínico humano sobre un snapshot real del UPS — nunca una
    medición ni un cálculo.

    `snapshot_id` es obligatorio y estructural: una impresión no puede
    existir sin un snapshot real al que ligarse (validado aquí, y reforzado
    por una foreign key NOT NULL a nivel de base de datos en
    `ClinicalImpressionRecord`, ver `models.py`)."""

    snapshot_id: str
    category: ImpressionCategory
    author: str  # genérico por ahora — // TODO: integración real de usuarios pendiente
    emitted_at: datetime
    notes: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.snapshot_id:
            raise ValueError(
                "ClinicalImpression.snapshot_id es obligatorio — no puede existir sin un snapshot real del UPS"
            )
        if not self.author:
            raise ValueError("ClinicalImpression.author es obligatorio")
