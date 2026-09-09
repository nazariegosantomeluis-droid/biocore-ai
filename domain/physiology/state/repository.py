"""
Unified Physiological State — repositorio de persistencia.

Traduce entre el esquema tipado en memoria (`schema.py`) y las tablas
SQLAlchemy (`models.py`). Ningún otro módulo debería construir
`ValueRecord`/`EventRecord` directamente — todo pasa por aquí.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .models import EventRecord, PatientRecord, SnapshotRecord, ValueRecord
from .schema import (
    DomainState,
    EventSeverity,
    EventType,
    PhysiologicalDescriptor,
    PhysiologicalEvent,
    Provenance,
    UnifiedPhysiologicalState,
)


def _to_naive_utc(ts: datetime) -> datetime:
    """SQLite no conserva tzinfo. Normalizamos a UTC naive al escribir."""
    if ts.tzinfo is not None:
        return ts.astimezone(timezone.utc).replace(tzinfo=None)
    return ts


def _to_aware_utc(ts: datetime) -> datetime:
    """Al leer, reatachamos tzinfo=UTC (lo que se guardó siempre fue UTC)."""
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts


def create_patient(session: Session, display_name: str, external_id: Optional[str] = None) -> str:
    """Crea un paciente y devuelve su id. No verifica duplicados de
    `external_id` — eso es una regla de negocio de una fase posterior."""
    record = PatientRecord(display_name=display_name, external_id=external_id)
    session.add(record)
    session.commit()
    return record.id


def get_patient(session: Session, patient_id: str) -> Optional[PatientRecord]:
    return session.get(PatientRecord, patient_id)


def rename_patient(session: Session, patient_id: str, display_name: str) -> None:
    """Fase 3 (paciente único de sesión, 2026-08-30): renombra el
    `display_name` de un paciente ya existente -- cosmético, nunca crea un
    paciente nuevo ni cambia su `id`. Reemplaza el vestigio de Patient
    Pipeline (`create_patient(display_name=etiqueta)` en cada cambio de
    input, que perdía continuidad silenciosamente creando un paciente
    distinto por cada etiqueta -- ver CHANGELOG.md). No-op silencioso si
    `patient_id` no existe (mismo criterio permisivo que `get_patient`)."""
    record = session.get(PatientRecord, patient_id)
    if record is not None:
        record.display_name = display_name
        session.commit()


def save_state(session: Session, state: UnifiedPhysiologicalState) -> str:
    """Persiste un snapshot completo del UPS: la trayectoria temporal crece
    con cada llamada — nunca se sobrescribe el snapshot anterior."""

    snapshot = SnapshotRecord(
        patient_id=state.patient_id,
        timestamp=_to_naive_utc(state.timestamp),
    )
    session.add(snapshot)
    session.flush()  # asigna snapshot.id sin cerrar la transacción

    for domain_state in state.all_domains().values():
        for descriptor in domain_state.descriptors.values():
            session.add(
                ValueRecord(
                    snapshot_id=snapshot.id,
                    domain=domain_state.domain,
                    descriptor=descriptor.name,
                    value=descriptor.value,
                    unit=descriptor.unit,
                    provenance=descriptor.provenance.value,
                    confidence=descriptor.confidence,
                    source_detail=descriptor.source_detail,
                )
            )

    for evt in state.events:
        session.add(
            EventRecord(
                patient_id=state.patient_id,
                snapshot_id=snapshot.id,
                domain=evt.domain,
                event_type=evt.event_type.value,
                severity=evt.severity.value,
                description=evt.description,
                provenance=evt.provenance.value,
                confidence=evt.confidence,
                related_descriptor=evt.related_descriptor,
                timestamp=_to_naive_utc(evt.timestamp),
            )
        )

    session.commit()
    return snapshot.id


def append_descriptors(
    session: Session, snapshot_id: str, domain: str, descriptors: List[PhysiologicalDescriptor]
) -> None:
    """Añade descriptores a un snapshot YA EXISTENTE, sin crear uno nuevo --
    para pipelines de cálculo posteriores (p.ej. el modelo hemodinámico,
    `domain/physiology/hemodynamics/ups_bridge.py`) que se adjuntan al
    mismo snapshot que ya tiene sus descriptores medidos/simulados, igual
    que `create_clinical_reference()` ya hace con su propia tabla. No
    sobrescribe nada: cada llamada agrega filas de `ValueRecord` nuevas
    bajo el mismo `snapshot_id` -- coexisten, ninguna reemplaza a otra."""
    for descriptor in descriptors:
        session.add(
            ValueRecord(
                snapshot_id=snapshot_id,
                domain=domain,
                descriptor=descriptor.name,
                value=descriptor.value,
                unit=descriptor.unit,
                provenance=descriptor.provenance.value,
                confidence=descriptor.confidence,
                source_detail=descriptor.source_detail,
            )
        )
    session.commit()


def _domain_state_from_values(domain: str, values: List[ValueRecord]) -> DomainState:
    descriptors = {
        v.descriptor: PhysiologicalDescriptor(
            name=v.descriptor,
            value=v.value,
            unit=v.unit or "",
            provenance=Provenance(v.provenance),
            confidence=v.confidence,
            source_detail=v.source_detail,
        )
        for v in values
        if v.domain == domain
    }
    return DomainState(domain=domain, descriptors=descriptors)


def _event_from_record(rec: EventRecord) -> PhysiologicalEvent:
    return PhysiologicalEvent(
        event_type=EventType(rec.event_type),
        domain=rec.domain,
        severity=EventSeverity(rec.severity),
        description=rec.description,
        provenance=Provenance(rec.provenance),
        confidence=rec.confidence,
        timestamp=_to_aware_utc(rec.timestamp),
        related_descriptor=rec.related_descriptor,
    )


def get_latest_state(session: Session, patient_id: str) -> Optional[UnifiedPhysiologicalState]:
    """Recupera el snapshot más reciente del paciente — funciona igual si la
    sesión/proceso que escribió el estado ya terminó (persistencia real, no
    session_state).

    Deuda de producción (2026-08-12): tercer gemelo del bug de colisión de
    timestamps, encontrado al barrer el repo tras cerrar el segundo en
    `get_latest_snapshot_id()` -- esta es la función MÁS usada de todo el
    UPS ("el estado actual del paciente").

    El orden se resuelve por `rowid` (orden real de inserción en SQLite),
    NO por `timestamp` -- ni siquiera con desempate. Medido: `datetime.now()`
    en Windows no es estrictamente monótono entre llamadas consecutivas de
    instancias distintas (`DigitalTwinOrganism()` nuevos en sucesión
    rápida pueden generar el segundo timestamp un microsegundo ANTES que
    el primero -- 27/500 casos medidos). Eso no es un empate desempatable:
    es un orden de timestamp ya equivocado antes de llegar a la consulta.
    `rowid` es ajeno al reloj del sistema y coincide con la recencia
    cronológica real porque `save_state()` siempre inserta hacia adelante
    (nunca retroactivo). Ver `get_latest_snapshot_id()` (mismo archivo
    hermano) y CHANGELOG.md para la reproducción completa."""

    stmt = (
        select(SnapshotRecord)
        .where(SnapshotRecord.patient_id == patient_id)
        .order_by(text("rowid DESC"))
        .limit(1)
    )
    snapshot = session.execute(stmt).scalar_one_or_none()
    if snapshot is None:
        return None

    values = list(snapshot.values)
    events = [_event_from_record(e) for e in snapshot.events]

    return UnifiedPhysiologicalState(
        patient_id=patient_id,
        timestamp=_to_aware_utc(snapshot.timestamp),
        cardiovascular=_domain_state_from_values("cardiovascular", values),
        respiratory=_domain_state_from_values("respiratory", values),
        neurological=_domain_state_from_values("neurological", values),
        events=events,
    )


def get_state_by_snapshot_id(session: Session, snapshot_id: str) -> Optional[UnifiedPhysiologicalState]:
    """Como `get_latest_state()`, pero para un snapshot ESPECÍFICO, no
    necesariamente el más reciente del paciente (2026-08-06). Necesario
    para releer un snapshot después de `append_descriptors()` (p.ej.
    `compute_and_attach_closed_loop_pressure()`) cuando ese snapshot no es
    el último persistido -- caso real de `case_bank.generate_case()`, que
    elige al azar cualquiera de los 6 horizontes como "el caso"."""
    snapshot = session.get(SnapshotRecord, snapshot_id)
    if snapshot is None:
        return None

    values = list(snapshot.values)
    events = [_event_from_record(e) for e in snapshot.events]

    return UnifiedPhysiologicalState(
        patient_id=snapshot.patient_id,
        timestamp=_to_aware_utc(snapshot.timestamp),
        cardiovascular=_domain_state_from_values("cardiovascular", values),
        respiratory=_domain_state_from_values("respiratory", values),
        neurological=_domain_state_from_values("neurological", values),
        events=events,
    )


def get_latest_snapshot_id_with_descriptor(
    session: Session, patient_id: str, domain: str, descriptor: str
) -> Optional[str]:
    """El id del ÚLTIMO snapshot del paciente que contiene `(domain,
    descriptor)` -- ignorando los snapshots que no lo tienen (2026-09-08,
    compositor multi-dominio Tanda 1 de (b)).

    Necesario porque el paciente único acumula snapshots mono-fuente: EEG
    Lab persiste `bar` sin `heart_rate`, ECG/HRV Lab persiste `heart_rate`
    sin `bar`. `get_latest_state()` devuelve el snapshot más reciente
    entero -- que suele tener solo uno de los dos. Esta consulta busca
    "el último que SÍ tiene X".

    Orden por `rowid DESC` (orden de inserción real en SQLite), NO por
    `timestamp` -- mismo criterio que `get_latest_state()` /
    `get_latest_snapshot_id()`, y a propósito distinto de
    `get_value_history()` (que ordena por timestamp y arrastra el bug de
    `datetime.now()` no-monótono en Windows). `save_state()` es la única
    vía de escritura y siempre inserta hacia adelante -- rowid y recencia
    cronológica coinciden por invariante de la app, no por el reloj."""
    stmt = (
        select(SnapshotRecord.id)
        .join(ValueRecord, ValueRecord.snapshot_id == SnapshotRecord.id)
        .where(
            SnapshotRecord.patient_id == patient_id,
            ValueRecord.domain == domain,
            ValueRecord.descriptor == descriptor,
        )
        .order_by(text("ups_snapshots.rowid DESC"))
        .limit(1)
    )
    return session.execute(stmt).scalar_one_or_none()


def get_value_history(
    session: Session,
    patient_id: str,
    domain: str,
    descriptor: str,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> List[Tuple[datetime, float]]:
    """Consulta cómo cambió un valor concreto (p.ej. HRV) en el tiempo.
    Devuelve pares (timestamp, value) ordenados cronológicamente."""

    stmt = (
        select(SnapshotRecord.timestamp, ValueRecord.value)
        .join(ValueRecord, ValueRecord.snapshot_id == SnapshotRecord.id)
        .where(
            SnapshotRecord.patient_id == patient_id,
            ValueRecord.domain == domain,
            ValueRecord.descriptor == descriptor,
        )
        .order_by(SnapshotRecord.timestamp.asc())
    )
    if start is not None:
        stmt = stmt.where(SnapshotRecord.timestamp >= _to_naive_utc(start))
    if end is not None:
        stmt = stmt.where(SnapshotRecord.timestamp <= _to_naive_utc(end))

    rows = session.execute(stmt).all()
    return [(_to_aware_utc(ts), value) for ts, value in rows]


def get_events(
    session: Session,
    patient_id: str,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> List[PhysiologicalEvent]:
    stmt = (
        select(EventRecord)
        .where(EventRecord.patient_id == patient_id)
        .order_by(EventRecord.timestamp.asc())
    )
    if start is not None:
        stmt = stmt.where(EventRecord.timestamp >= _to_naive_utc(start))
    if end is not None:
        stmt = stmt.where(EventRecord.timestamp <= _to_naive_utc(end))

    records = session.execute(stmt).scalars().all()
    return [_event_from_record(r) for r in records]
