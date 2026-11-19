"""Compositor por regla (T6 de la ruta integrada, 2026-11-18).

Diseño firmado: «Generalizar el compositor a pares de descriptores definidos por las reglas firmadas, en vez de solo
bar + heart_rate, cuando exista la segunda regla». Hay dos (`AROUSAL_TAQUICARDIA_BAR` y `HIPOXIA_TAQUICARDIA`).

`evaluate_rule_for_patient(session, patient_id, rule, scenario=...)` junta la condición de la regla (`bar`, `spo2`) y
la señal que modula (`heart_rate`) del paciente y evalúa SOLO esa regla:

1. **Escenario bloqueado** (lista global `COUPLING_DISABLED_SCENARIOS` o `rule.blocked_scenarios`): no se evalúa ni se
   escribe nada; el motivo lo dice. El llamador pasa el escenario del paciente (los pacientes de la Ruta salen de un
   escenario y son el paciente activo; con `scenario=None` los bloqueos por regla no se aplicarían).
2. **Solo mediciones:** la última condición y la última señal que no sean una copia de una composición anterior (un
   snapshot con un `ARRASTRE_TEMPORAL` persistido lo escribió un compositor) ni la proyección de un escenario (un valor
   con horizonte: un horizonte no es un momento). Lección de la revisión de la T4: sin este filtro, una FC vieja
   «rejuvenecía» al componer sus propias copias.
3. **Ventana de la regla** (`rule.window_s`, firmada por regla): la condición y la señal separadas como mucho por esa
   ventana; si no, el motivo dice cuál es más vieja.
4. **Mismo guardado:** si la condición y la señal están en el mismo snapshot (el gemelo, un escenario sin horizonte),
   se evalúa ese snapshot, sin escribir otro. Si ya tiene el valor acoplado de esa señal, no se vuelve a acoplar.
5. **Guardados distintos:** se escribe un snapshot nuevo con las dos: la más reciente tal cual (como el `bar` del
   compositor de siempre) y la más vieja como `ARRASTRE_TEMPORAL`, con su snapshot de origen y su edad.

El compositor neurocardiaco de siempre (`state.composer.compose_neuro_cardiac_snapshot`, que usa el gemelo) no cambia.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from ..state.composed import horizon_of
from ..state.repository import get_snapshot_ids_with_descriptor, get_state_by_snapshot_id, save_state
from ..state.schema import DomainState, PhysiologicalDescriptor, Provenance, UnifiedPhysiologicalState
from .bridge import COUPLING_DISABLED_SCENARIOS, AppliedCoupling, apply_couplings
from .rules import CouplingRule

__all__ = ["MeasuredValue", "RuleEvaluation", "latest_measured", "rule_input_check", "evaluate_rule_for_patient"]

_DOMAINS = ("cardiovascular", "respiratory", "neurological", "muscular")


@dataclass(frozen=True)
class MeasuredValue:
    snapshot_id: str
    timestamp: datetime
    descriptor: PhysiologicalDescriptor


@dataclass(frozen=True)
class RuleEvaluation:
    """`available=False` con `reason`: no se evaluó ni se escribió nada. `already_evaluated`: ese guardado ya tenía el
    valor acoplado (no se acopla dos veces). `coupled`: el acoplamiento escrito en esta llamada, o `None`."""

    rule_id: str
    available: bool
    reason: Optional[str] = None
    snapshot_id: Optional[str] = None
    wrote_snapshot: bool = False
    already_evaluated: bool = False
    gap_s: Optional[float] = None
    condition: Optional[MeasuredValue] = None
    base: Optional[MeasuredValue] = None
    coupled: Optional[AppliedCoupling] = field(default=None)


def _is_composed(state: UnifiedPhysiologicalState) -> bool:
    """Un snapshot con un arrastre persistido lo escribió un compositor: sus valores son copias, no mediciones."""
    return any(d.provenance == Provenance.ARRASTRE_TEMPORAL
               for dom in _DOMAINS for d in getattr(state, dom).descriptors.values())


def latest_measured(session: Session, patient_id: str, domain: str, name: str) -> Optional[MeasuredValue]:
    """El último valor de `(domain, name)` que no es una copia de una composición. Puede ser la proyección de un
    escenario: quien lo use lo decide con `horizon_of(descriptor.source_detail)`."""
    for snapshot_id in get_snapshot_ids_with_descriptor(session, patient_id, domain, name):
        state = get_state_by_snapshot_id(session, snapshot_id)
        if state is None or _is_composed(state):
            continue
        descriptor = getattr(state, domain).get(name)
        if descriptor is not None:
            return MeasuredValue(snapshot_id, state.timestamp, descriptor)
    return None


def _already_composed(session: Session, patient_id: str, rule: CouplingRule, cond: MeasuredValue,
                      base: MeasuredValue) -> bool:
    """¿Ya hay una composición de ESTA regla con estas dos mediciones? (su arrastre nombra la regla y los dos
    snapshots de origen). Así no se acopla dos veces lo mismo."""
    # Toda composición de la regla lleva su condición (aunque la regla no se haya cumplido y no haya valor acoplado).
    for snapshot_id in get_snapshot_ids_with_descriptor(session, patient_id, rule.condition.domain,
                                                        rule.condition.descriptor):
        state = get_state_by_snapshot_id(session, snapshot_id)
        if state is None:
            continue
        for dom in _DOMAINS:
            for d in getattr(state, dom).descriptors.values():
                detail = d.source_detail or ""
                if (d.provenance == Provenance.ARRASTRE_TEMPORAL and f"regla {rule.rule_id}" in detail
                        and cond.snapshot_id in detail and base.snapshot_id in detail):
                    return True
    return False


def _blocked_reason(rule: CouplingRule, scenario: Optional[str]) -> Optional[str]:
    if scenario is None:
        return None
    if scenario in COUPLING_DISABLED_SCENARIOS:
        return (f"bloqueada en el escenario {scenario!r}: ya modela la descarga simpática (lista global de "
                "escenarios bloqueados)")
    if scenario in rule.blocked_scenarios:
        return f"bloqueada en el escenario {scenario!r}: el escenario ya modela este efecto (bloqueo de la regla)"
    return None


def rule_input_check(session: Session, patient_id: str, rule: CouplingRule, scenario: Optional[str] = None):
    """`(condición, base, motivo)` sin escribir nada. `motivo` es `None` si la regla se puede evaluar ahora."""
    blocked = _blocked_reason(rule, scenario)
    cond = latest_measured(session, patient_id, rule.condition.domain, rule.condition.descriptor)
    base = latest_measured(session, patient_id, rule.effect.domain, rule.effect.descriptor)
    if blocked:
        return cond, base, blocked
    if rule.window_s is None:
        return cond, base, "la regla no declara su ventana fisiológica"
    if cond is None:
        return cond, base, f"falta una medición de {rule.condition.descriptor} del paciente"
    if base is None:
        return cond, base, f"falta una medición de {rule.effect.descriptor} del paciente"
    for value in (cond, base):
        horizon = horizon_of(value.descriptor.source_detail)
        if horizon is not None:
            return cond, base, (f"el valor de {value.descriptor.name} es la proyección de un escenario (horizonte "
                                f"{horizon}), no una medición de un momento")
    gap = abs((cond.timestamp - base.timestamp).total_seconds())
    if gap > rule.window_s:
        older, newer = (cond, base) if cond.timestamp < base.timestamp else (base, cond)
        return cond, base, (f"la medición de {older.descriptor.name} se guardó {gap:.0f} s antes que la de "
                            f"{newer.descriptor.name}: "
                            f"la ventana de la regla es de {rule.window_s:.0f} s")
    return cond, base, None


def evaluate_rule_for_patient(session: Session, patient_id: str, rule: CouplingRule, *,
                              scenario: Optional[str] = None) -> RuleEvaluation:
    cond, base, reason = rule_input_check(session, patient_id, rule, scenario)
    if reason is not None:
        return RuleEvaluation(rule.rule_id, False, reason=reason, condition=cond, base=base)
    gap = abs((cond.timestamp - base.timestamp).total_seconds())
    coupled_name = f"{rule.effect.descriptor}_acoplado"

    if cond.snapshot_id == base.snapshot_id:
        target = cond.snapshot_id
        state = get_state_by_snapshot_id(session, target)
        if getattr(state, rule.effect.domain).get(coupled_name) is not None:
            return RuleEvaluation(rule.rule_id, True, snapshot_id=target, already_evaluated=True, gap_s=gap,
                                  condition=cond, base=base)
        wrote = False
    elif _already_composed(session, patient_id, rule, cond, base):
        return RuleEvaluation(rule.rule_id, True, already_evaluated=True, gap_s=gap, condition=cond, base=base)
    else:
        newer, older = (cond, base) if cond.timestamp >= base.timestamp else (base, cond)
        carried = PhysiologicalDescriptor(
            name=older.descriptor.name,
            value=older.descriptor.value,
            unit=older.descriptor.unit,
            provenance=Provenance.ARRASTRE_TEMPORAL,
            confidence=older.descriptor.confidence,           # se hereda tal cual
            source_detail=(f"{older.descriptor.name} arrastrado del snapshot {older.snapshot_id} del "
                           f"{older.timestamp.isoformat()} (edad {gap:.0f}s) para la regla {rule.rule_id}, junto al "
                           f"{newer.descriptor.name} del snapshot {newer.snapshot_id}"),
        )
        values = {dom: {} for dom in _DOMAINS}
        values[rule.condition.domain if newer is cond else rule.effect.domain][newer.descriptor.name] = newer.descriptor
        values[rule.effect.domain if newer is cond else rule.condition.domain][older.descriptor.name] = carried
        composed = UnifiedPhysiologicalState(
            patient_id=patient_id,
            timestamp=datetime.now(timezone.utc),
            events=[],
            **{dom: DomainState(domain=dom, descriptors=values[dom]) for dom in _DOMAINS},
        )
        target = save_state(session, composed)
        wrote = True

    applied = apply_couplings(session, target, [rule], scenario=scenario)
    return RuleEvaluation(rule.rule_id, True, snapshot_id=target, wrote_snapshot=wrote, gap_s=gap, condition=cond,
                          base=base, coupled=applied[0] if applied else None)
