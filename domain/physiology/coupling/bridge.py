"""
Puente de aplicación de acoplamientos al UPS -- Sub-fase A (2026-09-06).

Réplica del patrón de `domain/physiology/hemodynamics/ups_bridge.py`: una
función explícita y aparte (`apply_couplings`) que lee un snapshot YA
PERSISTIDO, evalúa el catálogo de reglas de acoplamiento contra él, y
adjunta el resultado como `PhysiologicalDescriptor` nuevos vía
`append_descriptors()` -- COEXISTIENDO con los descriptores medidos, nunca
sobrescribiéndolos.

*** HONESTIDAD ***
- Un valor acoplado (FC que subió porque el estrés neurológico la empuja)
  NO es medido: lo produce una regla. Se persiste con
  `Provenance.DERIVADO_ACOPLAMIENTO` (ver `schema.py`), confianza EXPLÍCITA
  según el `validation_status` de la regla, y `source_detail` que declara
  la regla, la cita, el valor neuro observado que disparó, y el valor base
  medido.
- El nombre lleva sufijo `_acoplado` (`heart_rate` -> `heart_rate_acoplado`)
  -- deliberadamente distinto del medido, para que
  `repository._domain_state_from_values()` (que indexa por nombre) NO
  sobrescriba el medido al leer el snapshot. Ambos conviven como filas
  `ValueRecord` distintas. Mismo criterio que `systolic_bp_modelo`.
- NO muta el organismo. NO toca `builder.py`, `run_rich_scenario()` ni
  ningún flujo vivo. Se invoca aparte, explícitamente.

*** INERTE EN SUB-FASE A ***
No existe NINGUNA regla real (`rules.py` no precarga ninguna; una regla
nace `enabled=False`). Con el catálogo real -- vacío -- `evaluate()`
devuelve `[]` y `apply_couplings()` no escribe nada: el puente nace
honestamente inerte, igual que el motor. La Sub-fase B añade la primera
regla, validada con el experto, con su `magnitude_delta`.

*** POLÍTICA DE COMBINACIÓN MULTI-REGLA (pendiente de definición formal) ***
Si dos reglas habilitadas apuntaran al MISMO descriptor efecto (p.ej. dos
reglas distintas que ambas suben `heart_rate`), hoy `apply_couplings()`
adjuntaría dos filas `heart_rate_acoplado` y, al leer, ganaría la última
(dict indexado por nombre en `_domain_state_from_values`). Eso NO es una
política decidida -- es el comportamiento por defecto. Con <=1 regla
habilitada (el caso de la Sub-fase B) la cuestión no se plantea. Si la
Sub-fase B (o posterior) habilita >1 regla sobre el mismo efecto, debe
elegir y documentar aquí una política explícita (sumar los deltas / tomar
el de mayor magnitud / precedencia por `validation_status`) ANTES de
habilitarlas -- ver `_combine_proposals_for_same_effect()`, el gancho
reservado.

*** LISTA DE ESCENARIOS ***
`COUPLING_DISABLED_SCENARIOS` -- escritores/escenarios donde el
acoplamiento NO debe aplicarse porque su CV YA incluye el efecto
autonómico (doble contabilidad). Ver la constante. El acoplamiento SÍ
aplica, por doctrina, a escritores neuro-sin-CV-correlacionada (EEG Lab
"guardar al gemelo", un escritor solo-EEG) -- ésos pasan `scenario=None`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet, Iterable, List, Optional

from sqlalchemy.orm import Session

from ..state.repository import append_descriptors, get_state_by_snapshot_id
from ..state.schema import PhysiologicalDescriptor, Provenance
from .engine import ProposedCoupling, evaluate
from .rules import CouplingRule, EffectDirection, ValidationStatus

__all__ = [
    "COUPLING_DISABLED_SCENARIOS",
    "COUPLING_CONFIDENCE_TRANSCRITO",
    "COUPLING_CONFIDENCE_VALIDADO",
    "CouplingScenarioBlockedError",
    "AppliedCoupling",
    "confidence_for_validation_status",
    "apply_couplings",
]


# --- Lista de escenarios (doctrina del diagnóstico, 2026-09-06) ----------------

COUPLING_DISABLED_SCENARIOS: FrozenSet[str] = frozenset({"stress", "anxiety", "seizure"})
"""Escenarios (`SimulationScenario`, `app/engines/simulation_engine.py`)
cuyo CV el autor YA co-authoreó con la descarga simpática -- aplicar una
regla neuro->↑FC encima contaría el mismo efecto dos veces:

- `stress`, `anxiety`: descarga simpática psicológica aguda; el heart_rate
  del escenario ya sube CON el stress_level en cada waypoint (ver
  `scenarios/definitions.py::fibrilacion_estres`: stress 25->80 junto a FC
  75->145). El módulo hemodinámico ya los excluye por la misma razón
  (`closed_loop_ups_bridge.py`: "PICO AGUDO transitorio de descarga
  simpática").
- `seizure`: surge autonómico ictal -- mismo caso.

NO es una lista blanca: por doctrina el acoplamiento aplica a cualquier
escritor que aporte neuro SIN CV ya correlacionada (EEG Lab, escritor
solo-EEG, que pasan `scenario=None`). Esta lista es la excepción
estructural. Vacía de efecto en la Sub-fase A (no hay reglas); la Sub-fase
B la consulta al conectar la primera regla a un flujo con escenarios.
Cambiarla es una decisión deliberada, no un ajuste incidental."""


# --- Confianza según validation_status (sin punto medio automático) ------------

COUPLING_CONFIDENCE_TRANSCRITO: float = 0.35
"""Regla `TRANSCRITO_SIN_VALIDAR`: extremo bajo de la banda de
`DERIVADO_ACOPLAMIENTO` (0.30-0.80). Transcrita de un libro pero sin
revisión experta del efecto/umbral/magnitud en contexto -- por debajo del
0.425 del puente R-RCR estático (`ups_bridge.py`), que al menos está
validado estructuralmente contra svZeroDSolver; una regla de acoplamiento
sin firmar no tiene ni eso."""

COUPLING_CONFIDENCE_VALIDADO: float = 0.70
"""Regla `VALIDADO_POR_FUENTE`: extremo alto de la banda. Un hair por
debajo del 0.75 del lazo hemodinámico validado (`closed_loop_ups_bridge.py`)
-- una regla de acoplamiento confirma una DIRECCIÓN fisiológica citable,
no un modelo numérico validado cuantitativamente. Techo por debajo de
SIMULACION (0.90): ni la regla mejor validada compite con un dato
leído/simulado directo del organismo."""


def confidence_for_validation_status(status: ValidationStatus) -> float:
    """Confianza EXPLÍCITA para un descriptor acoplado, según el
    `validation_status` de la regla que lo produjo. Nunca
    `default_confidence()` -- la banda de `DERIVADO_ACOPLAMIENTO` es ancha
    a propósito y su punto medio no significa nada."""
    if status == ValidationStatus.VALIDADO_POR_FUENTE:
        return COUPLING_CONFIDENCE_VALIDADO
    if status == ValidationStatus.TRANSCRITO_SIN_VALIDAR:
        return COUPLING_CONFIDENCE_TRANSCRITO
    raise AssertionError(f"ValidationStatus no manejado: {status}")  # exhaustivo por diseño


class CouplingScenarioBlockedError(ValueError):
    """Se lanza -- nunca se absorbe en silencio -- cuando se pide aplicar
    acoplamientos a un escenario de `COUPLING_DISABLED_SCENARIOS`. Mismo
    patrón estructural que `HemodynamicModelNotEnabledError`: la exclusión
    no se puede sortear sin editar la lista a propósito."""


@dataclass(frozen=True)
class AppliedCoupling:
    """Registro de un acoplamiento efectivamente persistido -- lo que
    `apply_couplings()` devuelve por cada fila `_acoplado` escrita."""

    rule_id: str
    effect_domain: str
    coupled_descriptor: str          # p.ej. "heart_rate_acoplado"
    base_descriptor: str             # p.ej. "heart_rate"
    base_value: float
    coupled_value: float
    observed_value: float            # el valor neuro que cruzó el umbral
    provenance: Provenance
    confidence: float


def _combine_proposals_for_same_effect(proposals: List[ProposedCoupling]) -> List[ProposedCoupling]:
    """Gancho reservado para la política de combinación multi-regla (ver
    docstring del módulo). Sub-fase A: identidad -- con <=1 regla habilitada
    no hay nada que combinar. NO inventar una política sin >1 regla que la
    ejercite."""
    return proposals


def _coupled_descriptor_from_proposal(
    proposal: ProposedCoupling, base: PhysiologicalDescriptor
) -> Optional[PhysiologicalDescriptor]:
    """Traduce una propuesta + el descriptor base medido en el
    `PhysiologicalDescriptor` acoplado a persistir. Devuelve `None` si la
    regla no trae `magnitude_delta` -- sin un número citado no se puede
    escribir un valor acoplado honesto (eso lo aporta la regla validada de
    la Sub-fase B)."""
    effect = proposal.effect
    if effect.magnitude_delta is None:
        return None

    coupled_value = base.value + effect.magnitude_delta
    # Redundante con el check de CouplingEffect.__post_init__, pero explícito
    # aquí porque es el punto donde el número entra al UPS.
    if effect.direction == EffectDirection.AUMENTA and coupled_value <= base.value:
        raise ValueError("regla AUMENTA pero el valor acoplado no supera al base")
    if effect.direction == EffectDirection.DISMINUYE and coupled_value >= base.value:
        raise ValueError("regla DISMINUYE pero el valor acoplado no baja del base")

    rule = proposal.rule
    source_detail = (
        f"acoplamiento:{rule.rule_id} | {rule.source} | "
        f"disparo: {rule.condition.descriptor}={proposal.observed_value:g} | "
        f"{effect.descriptor} base={base.value:g}"
    )
    return PhysiologicalDescriptor(
        name=f"{effect.descriptor}_acoplado",
        value=coupled_value,
        unit=base.unit,
        provenance=Provenance.DERIVADO_ACOPLAMIENTO,
        confidence=confidence_for_validation_status(rule.validation_status),
        source_detail=source_detail,
    )


def apply_couplings(
    session: Session,
    snapshot_id: str,
    rules: Iterable[CouplingRule],
    *,
    scenario: Optional[str] = None,
) -> List[AppliedCoupling]:
    """Evalúa `rules` contra el snapshot `snapshot_id` YA PERSISTIDO y
    adjunta un descriptor `{descriptor}_acoplado` por cada acoplamiento que
    dispare y traiga `magnitude_delta`. Nunca crea un snapshot nuevo, nunca
    muta el organismo, nunca sobrescribe un descriptor medido.

    `scenario` -- el escenario del escritor, o `None` si no es un escenario
    (EEG Lab, escritor solo-EEG). Si está en `COUPLING_DISABLED_SCENARIOS`
    se lanza `CouplingScenarioBlockedError` de inmediato, antes de evaluar
    nada.

    Sub-fase A: con el catálogo real (vacío) devuelve `[]` y no escribe
    nada -- inerte por construcción."""
    if scenario is not None and scenario in COUPLING_DISABLED_SCENARIOS:
        raise CouplingScenarioBlockedError(
            f"El escenario {scenario!r} está en COUPLING_DISABLED_SCENARIOS "
            f"({sorted(COUPLING_DISABLED_SCENARIOS)}) -- su CV ya incluye el efecto "
            "autonómico; aplicar acoplamiento neuro->CV encima sería doble contabilidad. "
            "No se evaluó ni se persistió nada."
        )

    state = get_state_by_snapshot_id(session, snapshot_id)
    if state is None:
        raise ValueError(f"snapshot {snapshot_id!r} no existe -- nada que acoplar")

    proposals = _combine_proposals_for_same_effect(evaluate(state, rules))

    applied: List[AppliedCoupling] = []
    for proposal in proposals:
        effect_domain_state = state.all_domains().get(proposal.effect.domain)
        base = effect_domain_state.get(proposal.effect.descriptor) if effect_domain_state else None
        if base is None:
            # No se puede modular una señal que este snapshot nunca midió.
            continue

        coupled = _coupled_descriptor_from_proposal(proposal, base)
        if coupled is None:
            # Regla sin magnitud numérica citada -- Sub-fase B / experto.
            continue

        append_descriptors(
            session, snapshot_id=snapshot_id, domain=proposal.effect.domain, descriptors=[coupled]
        )
        applied.append(
            AppliedCoupling(
                rule_id=proposal.rule.rule_id,
                effect_domain=proposal.effect.domain,
                coupled_descriptor=coupled.name,
                base_descriptor=proposal.effect.descriptor,
                base_value=base.value,
                coupled_value=coupled.value,
                observed_value=proposal.observed_value,
                provenance=coupled.provenance,
                confidence=coupled.confidence,
            )
        )

    return applied
