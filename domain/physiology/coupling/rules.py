"""
Formato de regla de acoplamiento fisiológico (Paso 1a, aprobado 2026-07-15).

Una `CouplingRule` describe un acoplamiento entre dos sistemas del UPS tal
como lo documenta un libro de fisiología citado -- nunca inventado por este
código. Diseñada para que un humano la transcriba directamente de un texto
(Guyton et al.), con la fuente como campo estructural obligatorio.

Alcance deliberadamente estricto -- igual criterio que
`domain/physiology/state/schema.py`: los tres dominios que el UPS modela
hoy (cardiovascular, respiratorio, neurológico -- este último desde Capa
5A Sub-fase 1) y, dentro de esos, solo las señales primarias
medidas/simuladas (`COUPLABLE_DESCRIPTORS`). Los índices que el propio
BIOCORE deriva (`health_score`, `risk_score`, `rhythm_stability`,
`myocardial_stress`, `cardiac_output`, `hypoxia_risk`, `apnea_risk`,
`tissue_oxygenation`, y en neuro `mental_workload`, `cognitive_fatigue`,
`attention`, `stress_perception`, `sleepiness` -- ver
`domain/physiology/state/builder.py`) quedan fuera a propósito: son
invenciones de esta app, no conceptos de un libro de fisiología, así que
una regla de acoplamiento citable no puede apuntar a ellos.

Ancla neuro (2026-09-06, Acoplamientos Sub-fase A): `beta_power` -- band
power vía PSD de Welch (`EegAnalyzer`, señal primaria, NO un índice
derivado por BIOCORE, así que la doctrina de arriba se mantiene intacta).
Es PROVISIONAL: la firma del experto (Sub-fase B) podría cambiarlo a un
ratio nombrado por la literatura (theta/beta, beta/alpha). Esta sub-fase
solo deja el dominio disponible para anclar -- NINGUNA regla real existe
todavía.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, FrozenSet, Optional

__all__ = [
    "ComparisonOperator",
    "EffectDirection",
    "ValidationStatus",
    "COUPLABLE_DESCRIPTORS",
    "CouplingCondition",
    "CouplingEffect",
    "CouplingRule",
]


class ComparisonOperator(str, Enum):
    """Sin '==' ni '!=' -- los umbrales fisiológicos son siempre sobre
    cruzar un límite, no igualar un valor exacto."""

    LESS_THAN = "<"
    LESS_THAN_OR_EQUAL = "<="
    GREATER_THAN = ">"
    GREATER_THAN_OR_EQUAL = ">="


class EffectDirection(str, Enum):
    AUMENTA = "aumenta"
    DISMINUYE = "disminuye"


class ValidationStatus(str, Enum):
    """Distingue 'transcrito de un libro' de 'revisado por un experto'.
    El motor (engine.py) no exige VALIDADO_POR_FUENTE para evaluar una
    regla -- solo exige `enabled=True` y `source` presente (estructural,
    ver `CouplingRule.__post_init__`). Este campo viaja como metadato de
    honestidad hacia quien consuma el resultado más adelante (p.ej. un
    narrador), no como una compuerta adicional del motor."""

    TRANSCRITO_SIN_VALIDAR = "transcrito_sin_validar"
    VALIDADO_POR_FUENTE = "validado_por_fuente"


# Señales primarias acoplables por dominio -- ver docstring del módulo para
# por qué los índices derivados de BIOCORE quedan fuera, y por qué el ancla
# neuro es `beta_power` (band power, señal primaria) y no `stress_perception`
# (índice derivado, sigue prohibido).
COUPLABLE_DESCRIPTORS: Dict[str, FrozenSet[str]] = {
    "cardiovascular": frozenset({"heart_rate", "hrv"}),
    "respiratory": frozenset({"respiratory_rate", "spo2"}),
    "neurological": frozenset({"beta_power"}),
}


def _validate_domain_and_descriptor(domain: str, descriptor: str) -> None:
    if domain not in COUPLABLE_DESCRIPTORS:
        raise ValueError(
            f"dominio {domain!r} no es uno de los dominios que el UPS modela "
            f"({', '.join(sorted(COUPLABLE_DESCRIPTORS))})"
        )
    if descriptor not in COUPLABLE_DESCRIPTORS[domain]:
        raise ValueError(
            f"descriptor {descriptor!r} no es una señal primaria acoplable en el dominio "
            f"{domain!r} ({', '.join(sorted(COUPLABLE_DESCRIPTORS[domain]))}) -- los índices "
            "derivados por BIOCORE (health_score, risk_score, etc.) no son fisiología citable"
        )


@dataclass(frozen=True)
class CouplingCondition:
    """'Qué cambio en qué sistema dispara la regla' -- p.ej. spo2 < 90%."""

    domain: str
    descriptor: str
    operator: ComparisonOperator
    threshold: float
    unit: str

    def __post_init__(self) -> None:
        _validate_domain_and_descriptor(self.domain, self.descriptor)

    def is_triggered_by(self, value: float) -> bool:
        if self.operator == ComparisonOperator.LESS_THAN:
            return value < self.threshold
        if self.operator == ComparisonOperator.LESS_THAN_OR_EQUAL:
            return value <= self.threshold
        if self.operator == ComparisonOperator.GREATER_THAN:
            return value > self.threshold
        if self.operator == ComparisonOperator.GREATER_THAN_OR_EQUAL:
            return value >= self.threshold
        raise AssertionError(f"ComparisonOperator no manejado: {self.operator}")  # exhaustivo por diseño


@dataclass(frozen=True)
class CouplingEffect:
    """'Qué le pasa al otro sistema' -- p.ej. heart_rate aumenta."""

    domain: str
    descriptor: str
    direction: EffectDirection
    magnitude_hint: Optional[str] = None  # texto de la fuente ("respuesta compensatoria...", un rango)
    # `magnitude_delta` (2026-09-06, Acoplamientos Sub-fase A): el cambio
    # numérico con signo que la fuente cita, CUANDO lo cita -- lo que
    # `apply_couplings()` necesita para escribir un valor acoplado honesto
    # (`base + delta`). `None` en TODA regla de esta sub-fase (no hay
    # ninguna): lo rellena la regla validada de la Sub-fase B con el número
    # que confirme el experto. Un modelo de magnitud más rico (p.ej.
    # proporcional al exceso sobre el umbral) es una decisión de la Sub-fase
    # B; este campo cubre el caso simple "delta fijo citado".
    magnitude_delta: Optional[float] = None

    def __post_init__(self) -> None:
        _validate_domain_and_descriptor(self.domain, self.descriptor)
        if self.magnitude_delta is not None:
            positivo = self.magnitude_delta > 0
            if self.direction == EffectDirection.AUMENTA and not positivo:
                raise ValueError(
                    f"magnitude_delta={self.magnitude_delta} contradice direction=AUMENTA "
                    "-- un efecto que 'aumenta' no puede tener un delta <= 0"
                )
            if self.direction == EffectDirection.DISMINUYE and positivo:
                raise ValueError(
                    f"magnitude_delta={self.magnitude_delta} contradice direction=DISMINUYE "
                    "-- un efecto que 'disminuye' no puede tener un delta > 0"
                )


@dataclass(frozen=True)
class CouplingRule:
    """Una regla de acoplamiento completa. `source` es obligatorio y
    estructural -- sin fuente, la regla no se construye (mismo patrón que
    `snapshot_id` en `ClinicalImpression`). `enabled=False` por defecto:
    encender una regla transcrita es un acto explícito, nunca el estado de
    fábrica."""

    rule_id: str
    condition: CouplingCondition
    effect: CouplingEffect
    source: str
    validation_status: ValidationStatus
    enabled: bool = False
    notes: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.rule_id or not self.rule_id.strip():
            raise ValueError("CouplingRule.rule_id es obligatorio")
        if not self.source or not self.source.strip():
            raise ValueError(
                "CouplingRule.source es obligatorio -- una regla de acoplamiento no puede "
                "construirse sin una fuente citable (libro, capítulo/página)"
            )
