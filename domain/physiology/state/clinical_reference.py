"""
Valor de referencia clínica — "típico de este cuadro según literatura
citable", nunca medido, simulado ni derivado.

Deliberadamente en su propio archivo y con su propio tipo, separado de
`schema.py` (`PhysiologicalDescriptor`/`PhysiologicalEvent`) — mismo
criterio que `ClinicalImpression` (`clinical_impression.py`): un dato de
esta naturaleza no debe convivir con los datos medidos/simulados/derivados,
y no debe llevar ningún campo de certeza numérica (`confidence: float`),
que es estructuralmente obligatorio en `PhysiologicalDescriptor` y está
calibrado para observaciones numéricas de sensor/simulación — no para un
rango de guía de un libro de texto. Ver `Provenance.REFERENCIA_CLINICA`
(`schema.py`) para la etiqueta de clasificación asociada, deliberadamente
sin banda en `CONFIDENCE_REFERENCE`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

__all__ = ["ClinicalReferenceValue", "estimate_map"]


@dataclass(frozen=True)
class ClinicalReferenceValue:
    """Un valor de referencia clínica ligado a un escenario/cuadro clínico.

    `citation` es obligatoria y estructural — sin cita, no se construye
    (mismo patrón que `CouplingRule.source`/`ClinicalImpression.author`).
    `phase_note` es obligatorio en la práctica para cuadros que evolucionan
    en fases (validado por convención de datos en
    `blood_pressure_references.py`, no forzado aquí a nivel de tipo, porque
    no todo valor de referencia describe necesariamente un cuadro bifásico)."""

    scenario: str  # SimulationScenario.value, p.ej. "sepsis" -- string plano, sin import duro del motor
    domain: str
    descriptor: str
    value: float
    unit: str
    citation: str
    phase_note: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.citation or not self.citation.strip():
            raise ValueError(
                "ClinicalReferenceValue.citation es obligatoria -- un valor de referencia clínica "
                "no puede construirse sin una fuente citable"
            )
        if not self.scenario or not self.scenario.strip():
            raise ValueError("ClinicalReferenceValue.scenario es obligatorio")
        if not self.descriptor or not self.descriptor.strip():
            raise ValueError("ClinicalReferenceValue.descriptor es obligatorio")


def estimate_map(systolic: float, diastolic: float) -> float:
    """PAM ≈ diastólica + ⅓(sistólica − diastólica) -- fórmula estándar de
    presión arterial media, citada explícitamente en cada valor derivado con
    ella (ver `blood_pressure_references.py`). Pura aritmética -- no decide
    ninguna fisiología, solo evita errores de cálculo manual al transcribir."""
    return diastolic + (systolic - diastolic) / 3.0
