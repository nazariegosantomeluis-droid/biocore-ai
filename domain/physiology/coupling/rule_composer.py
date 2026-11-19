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

Revisión final de la T6: las dos entradas del snapshot nuevo son COPIAS marcadas («… del snapshot <id> … para la
regla <R>», `state.repository.COPY_FOR_RULE_MARK`): el paciente compuesto las salta y lee los originales (con sus puntos
NEWS2 y sus eventos), y el compositor nunca vuelve a componer una copia. Se pasan a `apply_couplings` todas las reglas
firmadas no bloqueadas, para que la política de no combinar (dos reglas sobre la misma FC: no se escribe nada) se
aplique también aquí.

El compositor neurocardiaco de siempre (`state.composer.compose_neuro_cardiac_snapshot`, que usa el gemelo) no cambia.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from ..state.composed import DERIVED_INPUTS, horizon_of
from ..state.repository import (
    COPY_FOR_RULE_MARK,
    get_composer_copies,
    get_latest_measured_value,
    get_state_by_snapshot_id,
    save_state,
)
from ..state.schema import DomainState, PhysiologicalDescriptor, Provenance, UnifiedPhysiologicalState
from .bridge import COUPLING_DISABLED_SCENARIOS, AppliedCoupling, apply_couplings
from .catalog import VALIDATED_RULES
from .rules import WAKE_EEG_BANDS, CouplingRule, wake_eeg_reason

__all__ = ["MeasuredValue", "RuleEvaluation", "latest_measured", "rule_input_check", "evaluate_rule_for_patient"]

_DOMAINS = ("cardiovascular", "respiratory", "neurological", "muscular")
_SNAPSHOT_ID_RE = re.compile(r"del snapshot ([0-9A-Za-z-]+)")
_DETAIL_MAX = 255                                      # largo de `ups_values.source_detail`


@dataclass(frozen=True)
class MeasuredValue:
    snapshot_id: str
    timestamp: datetime
    descriptor: PhysiologicalDescriptor


@dataclass(frozen=True)
class RuleEvaluation:
    """`available=False` con `reason`: no se evaluó ni se escribió nada. `already_evaluated`: ese guardado ya tenía el
    valor acoplado de ESTA regla (no se acopla dos veces). `coupled`: el acoplamiento escrito en esta llamada, o
    `None`. `combined_with`: otras reglas firmadas que también cambian la misma señal en ese guardado; sin una
    política firmada para combinarlas, no se escribió ninguna."""

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
    combined_with: Tuple[str, ...] = ()
    above_limit: bool = False               # T6.1: la condición pasa el techo de la regla; no se aplica


def latest_measured(session: Session, patient_id: str, domain: str, name: str) -> Optional[MeasuredValue]:
    """El último valor de `(domain, name)` que es una medición: ni la copia de una composición ni un arrastre. Puede
    ser la proyección de un escenario: quien lo use lo decide con `horizon_of(descriptor.source_detail)`."""
    found = get_latest_measured_value(session, patient_id, domain, name)
    return None if found is None else MeasuredValue(*found)


def _already_composed(session: Session, patient_id: str, rule: CouplingRule, cond: MeasuredValue,
                      base: MeasuredValue) -> bool:
    """¿Ya hay una composición de ESTA regla (nombre completo) con estas dos mediciones? Sus copias nombran los dos
    snapshots de origen. Así no se acopla dos veces lo mismo (aunque la regla no se haya cumplido)."""
    named = {}
    for snapshot_id, detail in get_composer_copies(session, patient_id, rule.rule_id):
        named.setdefault(snapshot_id, set()).update(_SNAPSHOT_ID_RE.findall(detail))
    return any({cond.snapshot_id, base.snapshot_id} <= ids for ids in named.values())


def _blocked_reason(rule: CouplingRule, scenario: Optional[str]) -> Optional[str]:
    if scenario is None:
        return None
    if scenario in COUPLING_DISABLED_SCENARIOS:
        return (f"bloqueada en el escenario {scenario!r}: ya modela la descarga simpática (lista global de "
                "escenarios bloqueados)")
    if scenario in rule.blocked_scenarios:
        return f"bloqueada en el escenario {scenario!r}: el escenario ya modela este efecto (bloqueo de la regla)"
    return None


def _missing_derived_reason(session: Session, patient_id: str, value: MeasuredValue) -> Optional[str]:
    """Una condición derivada (el BAR sale de las bandas del EEG): si el guardado más reciente con sus entradas no la
    trae (p. ej. alfa ≈ 0), no se usa la de un guardado anterior."""
    domain = next(d for d in _DOMAINS if (d, value.descriptor.name) in DERIVED_INPUTS)
    for in_domain, in_name in DERIVED_INPUTS[(domain, value.descriptor.name)]:
        newest = latest_measured(session, patient_id, in_domain, in_name)
        if newest is not None and newest.snapshot_id != value.snapshot_id and newest.timestamp > value.timestamp:
            return (f"el guardado más reciente con las entradas de {value.descriptor.name} no lo trae (no se pudo "
                    f"calcular): no se usa el {value.descriptor.name} de un guardado anterior")
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
    if any((d, rule.condition.descriptor) in DERIVED_INPUTS for d in _DOMAINS):
        missing = _missing_derived_reason(session, patient_id, cond)
        if missing:
            return cond, base, missing
    if rule.requires_wake_eeg:
        source = get_state_by_snapshot_id(session, cond.snapshot_id)       # el EEG de origen (nunca una copia)
        bands = {n: (None if source.neurological.get(n) is None else source.neurological.get(n).value)
                 for n in WAKE_EEG_BANDS}
        not_wake = wake_eeg_reason(bands)
        if not_wake:
            return cond, base, not_wake
    for value in (cond, base):
        horizon = horizon_of(value.descriptor.source_detail)
        if horizon is not None:
            return cond, base, (f"el valor de {value.descriptor.name} es la proyección de un escenario (horizonte "
                                f"{horizon}), no una medición de un momento")
    gap = abs((cond.timestamp - base.timestamp).total_seconds())
    if gap > rule.window_s:
        older, newer = (cond, base) if cond.timestamp < base.timestamp else (base, cond)
        return cond, base, (f"la medición de {older.descriptor.name} se guardó {gap:.0f} s antes que la de "
                            f"{newer.descriptor.name}: la ventana de la regla es de {rule.window_s:.0f} s")
    return cond, base, None


def _rules_for(scenario: Optional[str]):
    """Las reglas firmadas que se evalúan juntas (para la política de no combinar), sin las bloqueadas."""
    return [r for r in VALIDATED_RULES if _blocked_reason(r, scenario) is None]


def _coupled_by(state: UnifiedPhysiologicalState, rule: CouplingRule) -> bool:
    d = getattr(state, rule.effect.domain).get(f"{rule.effect.descriptor}_acoplado")
    return d is not None and re.search(rf"acoplamiento:{re.escape(rule.rule_id)}(?![A-Za-z0-9_])",
                                       d.source_detail or "") is not None


def _competing(state: UnifiedPhysiologicalState, rule: CouplingRule, scenario: Optional[str]) -> Tuple[str, ...]:
    """Otras reglas firmadas que, en este guardado, también se cumplen y cambian la misma señal (si esta se cumple)."""
    own = getattr(state, rule.condition.domain).get(rule.condition.descriptor)
    if own is None or not rule.condition.is_triggered_by(own.value):
        return ()
    out = []
    for other in _rules_for(scenario):
        if other.rule_id == rule.rule_id or (other.effect.domain, other.effect.descriptor) != (
                rule.effect.domain, rule.effect.descriptor):
            continue
        c = getattr(state, other.condition.domain).get(other.condition.descriptor)
        if c is not None and other.condition.is_triggered_by(c.value):
            out.append(other.rule_id)
    return tuple(out)


def _copy(value: MeasuredValue, rule: CouplingRule, carried: bool, gap: float) -> PhysiologicalDescriptor:
    """La copia marcada de una medición para el snapshot de la regla: la más vieja como arrastre con su edad, la más
    reciente con su procedencia de siempre. El marcador va primero (el detalle se recorta a 255)."""
    d = value.descriptor
    if carried:
        detail = (f"{d.name} arrastrado del snapshot {value.snapshot_id} del {value.timestamp.isoformat()} "
                  f"(edad {gap:.0f}s) {COPY_FOR_RULE_MARK}{rule.rule_id}")
    else:
        detail = f"{d.name} copiado del snapshot {value.snapshot_id} {COPY_FOR_RULE_MARK}{rule.rule_id}"
    if d.source_detail:
        detail = f"{detail}; {d.source_detail}"
    return PhysiologicalDescriptor(name=d.name, value=d.value, unit=d.unit,
                                   provenance=Provenance.ARRASTRE_TEMPORAL if carried else d.provenance,
                                   confidence=d.confidence,          # se hereda tal cual
                                   source_detail=detail[:_DETAIL_MAX])


def evaluate_rule_for_patient(session: Session, patient_id: str, rule: CouplingRule, *,
                              scenario: Optional[str] = None) -> RuleEvaluation:
    cond, base, reason = rule_input_check(session, patient_id, rule, scenario)
    if reason is not None:
        return RuleEvaluation(rule.rule_id, False, reason=reason, condition=cond, base=base)
    gap = abs((cond.timestamp - base.timestamp).total_seconds())

    if cond.snapshot_id == base.snapshot_id:
        target = cond.snapshot_id
        if _coupled_by(get_state_by_snapshot_id(session, target), rule):
            return RuleEvaluation(rule.rule_id, True, snapshot_id=target, already_evaluated=True, gap_s=gap,
                                  condition=cond, base=base)
        wrote = False
    elif _already_composed(session, patient_id, rule, cond, base):
        return RuleEvaluation(rule.rule_id, True, already_evaluated=True, gap_s=gap, condition=cond, base=base)
    else:
        newer, older = (cond, base) if cond.timestamp >= base.timestamp else (base, cond)
        values = {dom: {} for dom in _DOMAINS}
        for value, carried in ((newer, False), (older, True)):
            domain = rule.condition.domain if value is cond else rule.effect.domain
            values[domain][value.descriptor.name] = _copy(value, rule, carried, gap)
        composed = UnifiedPhysiologicalState(
            patient_id=patient_id,
            timestamp=datetime.now(timezone.utc),
            events=[],
            **{dom: DomainState(domain=dom, descriptors=values[dom]) for dom in _DOMAINS},
        )
        target = save_state(session, composed)
        wrote = True

    applied = [a for a in apply_couplings(session, target, _rules_for(scenario), scenario=scenario)
               if a.rule_id == rule.rule_id]
    competing = _competing(get_state_by_snapshot_id(session, target), rule, scenario) if not applied else ()
    return RuleEvaluation(rule.rule_id, True, snapshot_id=target, wrote_snapshot=wrote, gap_s=gap, condition=cond,
                          base=base, coupled=applied[0] if applied else None, combined_with=competing,
                          above_limit=rule.condition.above_limit(cond.descriptor.value))
