"""
Motor de acoplamiento fisiológico entre sistemas del UPS (2026-07-15).

Nace dormido: sin reglas reales cargadas (ver `rules.py`), no propaga
nada. Las reglas se transcriben desde libros de fisiología citados (fuente
obligatoria, validada estructuralmente) -- no las genera este código.
Aditivo -- no toca `domain/physiology/state/*`, `narrator/*`, ni el flujo
vivo del UPS. `evaluate()` (`engine.py`) solo PROPONE acoplamientos; nunca
modifica un `UnifiedPhysiologicalState`. Conectar el motor al flujo vivo es
una fase futura, posterior a esta.
"""

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
]
