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

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .models import EventRecord, SnapshotRecord, ValueRecord
from .repository import _event_from_record, _to_aware_utc
from .schema import DomainState, PhysiologicalDescriptor, Provenance, UnifiedPhysiologicalState

__all__ = ["CarryOrigin", "ComposedPatient", "DERIVED_INPUTS", "get_composed_patient"]

# Derivado -> descriptores de entrada (en cualquier dominio). Nombres tal como los escriben `builder.py`
# (puntos NEWS2), `hemodynamics/closed_loop_ups_bridge.py` (PA del modelo) y `coupling/bridge.py` (FC acoplada).
DERIVED_INPUTS: Dict[str, Tuple[str, ...]] = {
    "news2_pulse_points": ("heart_rate",),
    "news2_respiratory_rate_points": ("respiratory_rate",),
    "news2_spo2_scale1_points": ("spo2",),
    "systolic_bp_modelo": ("heart_rate",),
    "diastolic_bp_modelo": ("heart_rate",),
    "map_modelo": ("heart_rate",),
    "heart_rate_acoplado": ("bar", "heart_rate"),
    # Razones del EEG: `builder.py` las calcula de las bandas del MISMO snapshot (y las omite si alfa ~0 o falta una
    # banda). Revisión final de la T0: sin esto, un EEG nuevo sin razón mostraba la razón vieja junto a bandas nuevas.
    "bar": ("beta_power", "alpha_power"),
    "dar": ("delta_power", "alpha_power"),
    "tbr": ("theta_power", "beta_power"),
}

_DOMAINS = ("cardiovascular", "respiratory", "neurological", "muscular")


@dataclass(frozen=True)
class CarryOrigin:
    """De dónde viene un valor arrastrado: su snapshot, su hora, su procedencia original y su edad (>= 0) respecto al
    snapshot más reciente del paciente."""

    snapshot_id: str
    timestamp: datetime
    provenance: Provenance
    age_s: float


@dataclass(frozen=True)
class ComposedPatient:
    """`state`: el tipo de siempre, con `timestamp` del snapshot más reciente. `origins`: SOLO los arrastrados."""

    state: UnifiedPhysiologicalState
    origins: Dict[Tuple[str, str], CarryOrigin]
    latest_snapshot_id: str


def get_composed_patient(
    session: Session, patient_id: str, *, max_age_s: Optional[float] = None
) -> Optional[ComposedPatient]:
    """El paciente compuesto, o `None` si no tiene snapshots. Con `max_age_s`, un arrastre más viejo no se entrega."""
    rows = session.execute(
        select(ValueRecord, SnapshotRecord)
        .join(SnapshotRecord, ValueRecord.snapshot_id == SnapshotRecord.id)
        .where(SnapshotRecord.patient_id == patient_id)
        # Segunda llave: dentro de un snapshot, la última fila insertada gana (`append_descriptors` puede repetir un
        # nombre), igual que en `get_latest_state`.
        .order_by(text("ups_snapshots.rowid DESC"), text("ups_values.rowid DESC"))
    ).all()
    latest = session.execute(
        select(SnapshotRecord)
        .where(SnapshotRecord.patient_id == patient_id)
        .order_by(text("rowid DESC"))
        .limit(1)
    ).scalar_one_or_none()
    if latest is None:
        return None
    latest_ts = _to_aware_utc(latest.timestamp)

    # (dominio, descriptor) -> (valor, snapshot): el primero en orden de rowid descendente gana.
    first: Dict[Tuple[str, str], Tuple[ValueRecord, SnapshotRecord]] = {}
    for value, snapshot in rows:
        first.setdefault((value.domain, value.descriptor), (value, snapshot))

    delivered: Dict[Tuple[str, str], Tuple[PhysiologicalDescriptor, str]] = {}
    origins: Dict[Tuple[str, str], CarryOrigin] = {}
    for key, (value, snapshot) in first.items():
        descriptor = PhysiologicalDescriptor(
            name=value.descriptor,
            value=value.value,
            unit=value.unit or "",
            provenance=Provenance(value.provenance),
            confidence=value.confidence,
            source_detail=value.source_detail,
        )
        if snapshot.id != latest.id:
            ts = _to_aware_utc(snapshot.timestamp)
            age_s = abs((latest_ts - ts).total_seconds())
            if max_age_s is not None and age_s > max_age_s:
                continue
            detail = (f"arrastrado del snapshot {snapshot.id} del {ts.isoformat()} "
                      f"(edad {age_s:.0f}s; origen: {descriptor.provenance.value})")
            if descriptor.source_detail:
                detail = f"{detail}; {descriptor.source_detail}"
            origins[key] = CarryOrigin(snapshot.id, ts, descriptor.provenance, age_s)
            descriptor = replace(descriptor, provenance=Provenance.ARRASTRE_TEMPORAL, source_detail=detail)
        delivered[key] = (descriptor, snapshot.id)

    snapshot_of_name = {name: sid for (_dom, name), (_d, sid) in delivered.items()}
    for key in [k for k in delivered if k[1] in DERIVED_INPUTS]:
        own_sid = delivered[key][1]
        if any(snapshot_of_name.get(inp) != own_sid for inp in DERIVED_INPUTS[key[1]]):
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
