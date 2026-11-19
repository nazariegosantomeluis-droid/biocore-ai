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

Ancla neuro: `bar` (Ratio Beta/Alfa), firmado por el experto en la
Sub-fase B (2026-09-06). Reemplaza a `beta_power` (provisional en la
Sub-fase A). Es un cociente adimensional de dos band power con cita en
literatura -- señal primaria derivada honesta, no un índice inventado por
BIOCORE. Ver el comentario junto a `COUPLABLE_DESCRIPTORS`. La primera
regla real (`AROUSAL_TAQUICARDIA_BAR`, `VALIDADO_POR_FUENTE`, `enabled`)
vive en `catalog.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, FrozenSet, Optional, Tuple

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


# Descriptores acoplables por dominio -- ver docstring del módulo para por
# qué los índices derivados de BIOCORE quedan fuera.
#
# Ancla neuro = `bar` (Ratio Beta/Alfa), FIRMADO POR EL EXPERTO (Sub-fase
# B, 2026-09-06). Reemplaza a `beta_power` (provisional en Sub-fase A), que
# el experto rechazó: la potencia beta ABSOLUTA varía por anatomía (cráneo,
# distancia fuente-sensor, ganancia) y es indefendible entre sujetos. El
# BAR = P_beta/P_alpha del mismo electrodo cancela esas variables (divide
# dos bandas de la misma medición) y es un biomarcador de arousal CITADO
# (Schutter 2006 / Handbook of Psychophysiology cap.10), no una invención
# de esta app -- por eso SÍ es ancla legítima donde `beta_power` crudo era
# pobre y `stress_perception` (índice derivado) está prohibido. `bar` se
# persiste (`builder._neurological_state`) con la procedencia de las band
# power de origen: es un cociente de dos señales primarias, no un índice
# calculado por el organismo. `beta_power` YA NO es acoplable (nada más lo
# usaba); sigue persistiéndose como band power, solo que no como ancla.
COUPLABLE_DESCRIPTORS: Dict[str, FrozenSet[str]] = {
    "cardiovascular": frozenset({"heart_rate", "hrv"}),
    "respiratory": frozenset({"respiratory_rate", "spo2"}),
    "neurological": frozenset({"bar"}),
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
    # T6.1 (2026-11-19, decisión de Luis): techo explícito. Por encima, la regla no se aplica (fuera del rango que
    # describen sus fuentes). `upper_limit_basis` dice de dónde sale y de qué naturaleza es (obligatorio con techo).
    upper_limit: Optional[float] = None
    upper_limit_basis: Optional[str] = None
    upper_limit_nature: Optional[str] = None      # rótulo corto para la pantalla («Criterio BIOCORE, heurística»)

    def __post_init__(self) -> None:
        _validate_domain_and_descriptor(self.domain, self.descriptor)
        if self.upper_limit is not None and not (self.upper_limit_basis and self.upper_limit_nature):
            raise ValueError("Un techo necesita su fundamento (upper_limit_basis) y su naturaleza (upper_limit_nature).")

    def above_limit(self, value: float) -> bool:
        """¿El valor pasa el techo de la regla?"""
        return self.upper_limit is not None and value > self.upper_limit

    def is_triggered_by(self, value: float) -> bool:
        if self.above_limit(value):
            return False
        return self._meets_threshold(value)

    def _meets_threshold(self, value: float) -> bool:
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
    # Escenarios donde ESTA regla no se evalúa porque el escenario ya modela su efecto (doble contabilidad), además de
    # la lista global `COUPLING_DISABLED_SCENARIOS` (bridge.py). Ficha 1 de `docs/contenido/fichas_acoplamientos.md`,
    # firmada el 2026-11-18: la hipoxia no se acopla en hypoxia/apnea/copd/sepsis, pero la regla BAR sí puede.
    blocked_scenarios: Tuple[str, ...] = ()
    # Ventana fisiológica de la regla (decisión 1 firmada, 2026-11-17: «la fisiológica conserva los 120 s de la FC;
    # cada regla nueva trae la suya en su ficha»): la condición y la señal que modula deben venir de momentos separados
    # como mucho por esta ventana. `None`: la regla no se compone (T6, 2026-11-18).
    window_s: Optional[float] = None
    # T6.1 (revisión final): la condición solo tiene sentido con un EEG de vigilia (`wake_eeg_reason`). La regla BAR:
    # en el sueño el alfa casi desaparece y el BAR sale alto sin que haya arousal.
    requires_wake_eeg: bool = False

    def __post_init__(self) -> None:
        if not self.rule_id or not self.rule_id.strip():
            raise ValueError("CouplingRule.rule_id es obligatorio")
        if not self.source or not self.source.strip():
            raise ValueError(
                "CouplingRule.source es obligatorio -- una regla de acoplamiento no puede "
                "construirse sin una fuente citable (libro, capítulo/página)"
            )


# ── EEG de vigilia (T6.1, revisión final, 2026-11-19) ──────────────────────────────────────────────────────────────
WAKE_EEG_BANDS = ("delta_power", "theta_power", "alpha_power", "beta_power")
WAKE_EEG_BASIS = (
    "Criterio BIOCORE firmado por Luis (2026-11-19), con el glosario IFCN (Kane 2017): el alfa es el ritmo de vigilia y el delta domina "
    "el sueño profundo. Si la mayor de las potencias delta o theta supera a la mayor de alfa o beta, el EEG no es de "
    "vigilia y el BAR no mide arousal."
)


def wake_eeg_reason(bands) -> Optional[str]:
    """`None` si el EEG es de vigilia según `WAKE_EEG_BASIS`; si no, o si faltan bandas para saberlo, el motivo."""
    if any(bands.get(name) is None for name in WAKE_EEG_BANDS):
        return "el EEG guardado no trae las cuatro bandas (delta, theta, alfa y beta) para saber si es de vigilia"
    slow = max(float(bands["delta_power"]), float(bands["theta_power"]))
    fast = max(float(bands["alpha_power"]), float(bands["beta_power"]))
    if slow > fast:
        return ("el EEG de tu paciente no es de vigilia: la potencia delta o theta supera a la alfa y a la beta "
                "(Criterio BIOCORE con el glosario IFCN, Kane 2017); en el sueño el BAR no mide arousal")
    return None
