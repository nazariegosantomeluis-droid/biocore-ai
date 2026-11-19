"""El paciente compuesto (T0 de la ruta integrada, 2026-11-18): un solo paciente para todas las pantallas.

Por qué existe -- medido el 2026-11-17: tras guardar en el gemelo (FC 100, FR 24, SpO₂ 92) y luego en el EEG Lab,
`get_latest_state()` devolvía FC/FR/SpO₂ en `None`. Esa función devuelve el último snapshot y nada más, y cada
laboratorio escribe solo lo que mide (los gates anti-órgano-fantasma del builder), así que cada guardado "borraba" a
los demás de todo lo que lee el estado actual: el banner, el Inicio, Calculadoras.

Qué hace `get_composed_patient()` -- SOLO LEE, nunca escribe un snapshot:
- El último valor de cada `(dominio, descriptor)`, en orden de `rowid` (orden real de inserción; el reloj de Windows
  no es monótono, ver `get_latest_state`).
- Un valor del snapshot más reciente conserva su procedencia. Uno de un snapshot anterior se entrega como
  `ARRASTRE_TEMPORAL`, con la confianza de origen tal cual y su origen declarado (snapshot, hora, procedencia
  original, edad) en `source_detail` y en `ComposedPatient.origins`.
- Ventana de sesión (decisión 1 firmada por Luis el 2026-11-17): para mostrar, un valor del paciente activo sigue
  vigente toda la sesión, siempre con su edad visible; por eso `max_age_s=None` es lo que usan las pantallas. La
  ventana fisiológica, estricta, es solo de los acoplamientos y vive en el compositor (`composer.py`), que sí escribe.
- Un derivado (`DERIVED_INPUTS`) viaja solo con sus entradas: se entrega si cada entrada se entrega y viene del MISMO
  snapshot que él. Nada se recalcula aquí; la regla C0 sigue viviendo solo en `derived_contract.py`.
- Eventos: solo los del snapshot más reciente (un evento es un momento, no un estado).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func, literal_column, select, text
from sqlalchemy.orm import Session

from .models import EventRecord, SnapshotRecord, ValueRecord
from .repository import _event_from_record, _to_aware_utc, is_composer_copy, not_composer_copy_clause
from .schema import DomainState, PhysiologicalDescriptor, Provenance, UnifiedPhysiologicalState

__all__ = ["CarryOrigin", "ComposedPatient", "DERIVED_INPUTS", "derived_inputs_of", "get_composed_patient", "horizon_of"]

_CV, _RESP, _NEURO = "cardiovascular", "respiratory", "neurological"

# (dominio, derivado) -> sus entradas (dominio, descriptor). Nombres y dominios tal como los escriben `builder.py`
# (puntos NEWS2), `hemodynamics/closed_loop_ups_bridge.py` (PA del modelo, cardiovascular) y `coupling/bridge.py` (FC
# acoplada, dominio del efecto de la regla: cardiovascular). Calificadas por dominio desde la T1.1: un nombre repetido
# en otro dominio no puede decidir por el de este.
DERIVED_INPUTS: Dict[Tuple[str, str], Tuple[Tuple[str, str], ...]] = {
    (_CV, "news2_pulse_points"): ((_CV, "heart_rate"),),
    (_RESP, "news2_respiratory_rate_points"): ((_RESP, "respiratory_rate"),),
    (_RESP, "news2_spo2_scale1_points"): ((_RESP, "spo2"),),
    (_CV, "systolic_bp_modelo"): ((_CV, "heart_rate"),),
    (_CV, "diastolic_bp_modelo"): ((_CV, "heart_rate"),),
    (_CV, "map_modelo"): ((_CV, "heart_rate"),),
    (_CV, "heart_rate_acoplado"): ((_NEURO, "bar"), (_CV, "heart_rate")),
    # Razones del EEG: `builder.py` las calcula de las bandas del MISMO snapshot (y las omite si alfa ~0 o falta una
    # banda). Revisión final de la T0: sin esto, un EEG nuevo sin razón mostraba la razón vieja junto a bandas nuevas.
    (_NEURO, "bar"): ((_NEURO, "beta_power"), (_NEURO, "alpha_power")),
    (_NEURO, "dar"): ((_NEURO, "delta_power"), (_NEURO, "alpha_power")),
    (_NEURO, "tbr"): ((_NEURO, "theta_power"), (_NEURO, "beta_power")),
}

# T6 (2026-11-18): con dos reglas firmadas, la FC acoplada no siempre sale del BAR. Sus entradas son las de SU regla,
# que el valor declara en su `source_detail` («acoplamiento:<regla> | …», `coupling/bridge.py`). La entrada fija de
# arriba queda solo para quien no tiene el valor a mano (`physiological_state`), y es la de la regla BAR.
_COUPLED_RULE_RE = re.compile(r"acoplamiento:([A-Za-z0-9_]+)")


def _coupling_rule_inputs(source_detail: Optional[str]) -> Optional[Tuple[Tuple[str, str], ...]]:
    """Las entradas de la regla firmada que escribió un valor acoplado, o `None` si el valor no nombra una regla del
    catálogo (`VALIDATED_RULES`): entonces no se sabe de qué salió."""
    from ..coupling.catalog import VALIDATED_RULES        # import diferido: coupling importa state

    match = _COUPLED_RULE_RE.search(source_detail or "")
    rule = next((r for r in VALIDATED_RULES if match and r.rule_id == match.group(1)), None)
    if rule is None:
        return None
    return ((rule.condition.domain, rule.condition.descriptor), (rule.effect.domain, rule.effect.descriptor))


def derived_inputs_of(domain: str, name: str,
                      source_detail: Optional[str] = None) -> Optional[Tuple[Tuple[str, str], ...]]:
    """Las entradas de un derivado: las de su regla si es un valor acoplado que la nombra, si no las de
    `DERIVED_INPUTS`. `None`: no es un derivado conocido."""
    if name.endswith("_acoplado"):
        inputs = _coupling_rule_inputs(source_detail)
        if inputs is not None:
            return inputs
    return DERIVED_INPUTS.get((domain, name))

# Un paso de una trayectoria de escenario (`rich_engine.run_rich_scenario`) marca su `source_detail` con
# `escenario_rico:<escenario>:modo:<modo>:horizonte:<tiempo>`. Sus pasos se guardan con segundos de diferencia, así que
# la edad en tiempo real no dice nada: lo que importa es el horizonte simulado (T1.1, revisión de la T0).
_HORIZON = re.compile(r":horizonte:([^:;\s]+)")


def horizon_of(source_detail: Optional[str]) -> Optional[str]:
    """El horizonte simulado de un valor de trayectoria, o `None` si no viene de una."""
    match = _HORIZON.search(source_detail or "")
    return match.group(1) if match else None

_DOMAINS = ("cardiovascular", "respiratory", "neurological", "muscular")


@dataclass(frozen=True)
class CarryOrigin:
    """De dónde viene un valor arrastrado: su snapshot, su hora, su procedencia original y su edad (>= 0) respecto al
    snapshot más reciente del paciente. `horizon`: el horizonte simulado si el valor sale de una trayectoria de
    escenario (entonces la edad en tiempo real no es lo que se muestra)."""

    snapshot_id: str
    timestamp: datetime
    provenance: Provenance
    age_s: float
    horizon: Optional[str] = None
    source_detail: Optional[str] = None     # el detalle ORIGINAL del valor (el del arrastre lleva además su prefijo)


@dataclass(frozen=True)
class ComposedPatient:
    """`state`: el tipo de siempre, con `timestamp` del snapshot más reciente. `origins`: SOLO los arrastrados."""

    state: UnifiedPhysiologicalState
    origins: Dict[Tuple[str, str], CarryOrigin]
    latest_snapshot_id: str


def _latest_values(session: Session, patient_id: str, max_rowid: int) -> list:
    """La última fila de cada `(dominio, descriptor)` del paciente, sin pasar del snapshot con `rowid` = `max_rowid`.
    Una consulta con ventana (T1.1): ya no se carga toda la historia del paciente en cada lectura. Dentro de un
    snapshot gana la última fila insertada (`append_descriptors` puede repetir un nombre), como en
    `get_latest_state`. Orden de salida: el mismo de antes (snapshot más nuevo primero)."""
    ranked = (
        select(
            ValueRecord.id.label("vid"),
            func.row_number().over(
                partition_by=(ValueRecord.domain, ValueRecord.descriptor),
                order_by=(text("ups_snapshots.rowid DESC"), text("ups_values.rowid DESC")),
            ).label("rn"),
        )
        .join(SnapshotRecord, ValueRecord.snapshot_id == SnapshotRecord.id)
        .where(SnapshotRecord.patient_id == patient_id)
        .where(text("ups_snapshots.rowid <= :max_rowid").bindparams(max_rowid=max_rowid))
        .where(not_composer_copy_clause())             # revisión final de la T6: una copia no es un valor nuevo
        .subquery()
    )
    return session.execute(
        select(ValueRecord, SnapshotRecord)
        .join(SnapshotRecord, ValueRecord.snapshot_id == SnapshotRecord.id)
        .join(ranked, ranked.c.vid == ValueRecord.id)
        .where(ranked.c.rn == 1)
        .order_by(text("ups_snapshots.rowid DESC"), text("ups_values.rowid DESC"))
    ).all()


def _latest_real_snapshot(session: Session, patient_id: str, max_rowid: int):
    """`(SnapshotRecord, rowid)` del último snapshot del paciente sin copias de un compositor, o `None`."""
    copies = select(ValueRecord.snapshot_id).where(~not_composer_copy_clause())
    return session.execute(
        select(SnapshotRecord, literal_column("ups_snapshots.rowid"))
        .where(SnapshotRecord.patient_id == patient_id)
        .where(text("ups_snapshots.rowid <= :max_rowid").bindparams(max_rowid=max_rowid))
        .where(SnapshotRecord.id.not_in(copies))
        .order_by(text("ups_snapshots.rowid DESC"))
        .limit(1)
    ).first()


def _rowid_after(session: Session, snapshot_id: str, rowid: int) -> bool:
    """¿El snapshot se escribió después del snapshot `rowid`? (un compositor, tras el último momento real)."""
    found = session.execute(
        select(literal_column("ups_snapshots.rowid")).select_from(SnapshotRecord).where(SnapshotRecord.id == snapshot_id)
    ).scalar_one_or_none()
    return found is not None and found > rowid


_COPY_SOURCE_RE = re.compile(r"del snapshot ([0-9A-Za-z-]+)")


def _copy_sources(session: Session, snapshot_id: str) -> Dict[Tuple[str, str], str]:
    """En un snapshot de un compositor: `(dominio, descriptor)` de cada copia → el snapshot de la medición original."""
    out = {}
    for domain, name, detail in session.execute(
        select(ValueRecord.domain, ValueRecord.descriptor, ValueRecord.source_detail)
        .where(ValueRecord.snapshot_id == snapshot_id)
    ).all():
        match = _COPY_SOURCE_RE.search(detail or "") if is_composer_copy(detail) else None
        if match:
            out[(domain, name)] = match.group(1)
    return out


def get_composed_patient(
    session: Session, patient_id: str, *, max_age_s: Optional[float] = None
) -> Optional[ComposedPatient]:
    """El paciente compuesto, o `None` si no tiene snapshots. Con `max_age_s`, un arrastre más viejo no se entrega."""
    # Primero el último snapshot y su rowid; los valores se leen con ese rowid como corte (T1.1): una escritura que
    # llegue entre las dos lecturas no vuelve arrastre todo.
    head = session.execute(
        select(SnapshotRecord, literal_column("ups_snapshots.rowid"))
        .where(SnapshotRecord.patient_id == patient_id)
        .order_by(text("ups_snapshots.rowid DESC"))
        .limit(1)
    ).first()
    if head is None:
        return None
    _head, latest_rowid = head
    # Revisión final de la T6: un snapshot de un compositor (copias + el valor acoplado) no es un momento nuevo del
    # paciente. Los eventos y las edades salen del último snapshot SIN copias; lo que un compositor escribió después
    # (el valor acoplado) cuenta como actual. Sin esto, la composición escondía los puntos NEWS2 y el aviso de SpO₂.
    real = _latest_real_snapshot(session, patient_id, latest_rowid)
    latest, real_rowid = real if real is not None else head
    latest_ts = _to_aware_utc(latest.timestamp)

    delivered: Dict[Tuple[str, str], Tuple[PhysiologicalDescriptor, str]] = {}
    origins: Dict[Tuple[str, str], CarryOrigin] = {}
    raw_detail: Dict[Tuple[str, str], Optional[str]] = {}
    for value, snapshot in _latest_values(session, patient_id, latest_rowid):
        key = (value.domain, value.descriptor)
        raw_detail[key] = value.source_detail
        descriptor = PhysiologicalDescriptor(
            name=value.descriptor,
            value=value.value,
            unit=value.unit or "",
            provenance=Provenance(value.provenance),
            confidence=value.confidence,
            source_detail=value.source_detail,
        )
        if snapshot.id != latest.id and not _rowid_after(session, snapshot.id, real_rowid):
            ts = _to_aware_utc(snapshot.timestamp)
            age_s = abs((latest_ts - ts).total_seconds())
            if max_age_s is not None and age_s > max_age_s:
                continue
            detail = (f"arrastrado del snapshot {snapshot.id} del {ts.isoformat()} "
                      f"(edad {age_s:.0f}s; origen: {descriptor.provenance.value})")
            if descriptor.source_detail:
                detail = f"{detail}; {descriptor.source_detail}"
            origins[key] = CarryOrigin(snapshot.id, ts, descriptor.provenance, age_s,
                                       horizon_of(descriptor.source_detail), descriptor.source_detail)
            descriptor = replace(descriptor, provenance=Provenance.ARRASTRE_TEMPORAL, source_detail=detail)
        delivered[key] = (descriptor, snapshot.id)

    # Se comprueba contra lo leído ANTES de quitar nada (T6): el resultado no depende del orden de las filas. Un
    # derivado viaja si sus entradas son las últimas y vienen de su mismo snapshot, aunque una de ellas no se muestre
    # (el BAR copiado de una composición viaja sin sus bandas; la FC acoplada que salió de él, sí).
    read = dict(delivered)
    for key in list(delivered):
        if key[1].endswith("_acoplado") and _coupling_rule_inputs(raw_detail.get(key)) is None:
            drop = True                                            # no nombra una regla del catálogo
        else:
            inputs = derived_inputs_of(key[0], key[1], raw_detail.get(key))
            own_sid = delivered[key][1]
            # En un snapshot de un compositor, la entrada es la copia de una medición: vale su original.
            sources = _copy_sources(session, own_sid) if key[1].endswith("_acoplado") else {}
            drop = bool(inputs) and any(inp not in read or read[inp][1] != sources.get(inp, own_sid)
                                        for inp in inputs)
        if drop:
            del delivered[key]
            origins.pop(key, None)

    by_domain: Dict[str, Dict[str, PhysiologicalDescriptor]] = {d: {} for d in _DOMAINS}
    for (domain, name), (descriptor, _sid) in delivered.items():
        by_domain.setdefault(domain, {})[name] = descriptor

    events: List = [
        _event_from_record(rec)
        for rec in session.execute(select(EventRecord).where(EventRecord.snapshot_id == latest.id)).scalars()
    ]
    state = UnifiedPhysiologicalState(
        patient_id=patient_id,
        timestamp=latest_ts,
        **{d: DomainState(domain=d, descriptors=by_domain[d]) for d in _DOMAINS},
        events=events,
    )
    return ComposedPatient(state=state, origins=origins, latest_snapshot_id=latest.id)
