"""
Motor de acoplamiento fisiológico entre sistemas del UPS
(2026-07-15 nace dormido; Sub-fase A 2026-09-06 infraestructura honesta;
Sub-fase B 2026-09-06 primera regla validada, activa).

`catalog.py::VALIDATED_RULES` es el único catálogo activo -- hoy UNA regla,
`AROUSAL_TAQUICARDIA_BAR` (arousal cortical BAR>1.8 -> ↑FC +15 bpm),
transcrita LITERALMENTE de la firma del experto (Guyton 14a ed. cap.61 +
Schutter 2006), `VALIDADO_POR_FUENTE`, `enabled=True`. Las reglas no las
genera este código; añadir una exige la firma completa documentada en
`catalog.py`.

`evaluate()` (`engine.py`) solo PROPONE; nunca modifica un
`UnifiedPhysiologicalState`. `apply_couplings()` (`bridge.py`) persiste el
valor acoplado -- SIEMPRE como un descriptor NUEVO con sufijo `_acoplado` y
`Provenance.DERIVADO_ACOPLAMIENTO`, adjunto a un snapshot ya existente vía
`append_descriptors()`, sin tocar el organismo, `builder.py`,
`run_rich_scenario()` ni el descriptor medido. Cableado al flujo vivo en
el botón "Guardar estado al gemelo" de EEG Lab (`scenario=None`);
`COUPLING_DISABLED_SCENARIOS` bloquea `stress`/`anxiety`/`seizure`.
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
from .catalog import AROUSAL_TAQUICARDIA_BAR, VALIDATED_RULES
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
    "VALIDATED_RULES",
    "AROUSAL_TAQUICARDIA_BAR",
]
