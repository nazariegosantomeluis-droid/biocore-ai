"""
Motor de acoplamiento fisiológico entre sistemas del UPS (2026-07-15;
Sub-fase A 2026-09-06: infraestructura honesta e inerte).

Nace dormido y SIGUE dormido: sin reglas reales cargadas (ver `rules.py`,
que no precarga ninguna; una regla nace `enabled=False`), no propaga nada.
Las reglas se transcriben desde libros de fisiología citados -- no las
genera este código; la primera, validada con el experto, es la Sub-fase B.

`evaluate()` (`engine.py`) solo PROPONE acoplamientos; nunca modifica un
`UnifiedPhysiologicalState`. `apply_couplings()` (`bridge.py`, Sub-fase A)
sí puede persistir un valor acoplado -- pero SIEMPRE como un descriptor
NUEVO con sufijo `_acoplado` y `Provenance.DERIVADO_ACOPLAMIENTO`,
adjuntado a un snapshot ya existente vía `append_descriptors()`, sin tocar
el organismo, `builder.py`, `run_rich_scenario()` ni el descriptor medido.
Con el catálogo real (vacío) es inerte por construcción.
"""

from .bridge import (
    COUPLING_CONFIDENCE_TRANSCRITO,
    COUPLING_CONFIDENCE_VALIDADO,
    COUPLING_DISABLED_SCENARIOS,
    AppliedCoupling,
    CouplingScenarioBlockedError,
    apply_couplings,
    confidence_for_validation_status,
)
from .engine import ProposedCoupling, evaluate
from .rules import (
    COUPLABLE_DESCRIPTORS,
    ComparisonOperator,
    CouplingCondition,
    CouplingEffect,
    CouplingRule,
    EffectDirection,
    ValidationStatus,
)

__all__ = [
    "ProposedCoupling",
    "evaluate",
    "COUPLABLE_DESCRIPTORS",
    "ComparisonOperator",
    "CouplingCondition",
    "CouplingEffect",
    "CouplingRule",
    "EffectDirection",
    "ValidationStatus",
    "apply_couplings",
    "AppliedCoupling",
    "COUPLING_DISABLED_SCENARIOS",
    "COUPLING_CONFIDENCE_TRANSCRITO",
    "COUPLING_CONFIDENCE_VALIDADO",
    "CouplingScenarioBlockedError",
    "confidence_for_validation_status",
]
