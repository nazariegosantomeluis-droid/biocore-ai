"""
Unified Physiological State — modelos SQLAlchemy.

Esquema inspirado en _archive/v2_backend_stack/db/models.py (Patient,
SignalReading, Prediction, AuditLog), adaptado a lo que necesita el UPS:
un paciente, una trayectoria de snapshots en el tiempo, valores con
procedencia/confianza dentro de cada snapshot, y eventos discretos como
entidad propia (no derivados de los valores).

// TODO: integración real pendiente — PatientRecord guarda el nombre en
texto plano. _archive/v2_backend_stack/db/models.py cifraba name/email
(LargeBinary). Cuando este módulo maneje pacientes reales (no solo
escenarios de simulación educativos), retomar ese cifrado.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, String
from sqlalchemy.orm import DeclarativeBase, relationship


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class PatientRecord(Base):
    __tablename__ = "ups_patients"

    id = Column(String(36), primary_key=True, default=_uuid)
    external_id = Column(String(255), unique=True, nullable=True, index=True)
    display_name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=_utcnow)


class SnapshotRecord(Base):
    __tablename__ = "ups_snapshots"

    id = Column(String(36), primary_key=True, default=_uuid)
    patient_id = Column(String(36), ForeignKey("ups_patients.id"), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=_utcnow)

    values = relationship("ValueRecord", back_populates="snapshot", cascade="all, delete-orphan")
    events = relationship("EventRecord", back_populates="snapshot", cascade="all, delete-orphan")
    # Fusión de persistencia, Paso 2 (2026-07-15): atributo ORM aditivo —
    # ups_snapshots no gana ninguna columna nueva, solo esta relación.
    clinical_impressions = relationship(
        "ClinicalImpressionRecord", back_populates="snapshot", cascade="all, delete-orphan"
    )
    # Presión arterial, Paso 1+2 (2026-07-18): otro atributo ORM aditivo --
    # ups_snapshots sigue sin ganar ninguna columna nueva.
    clinical_references = relationship(
        "ClinicalReferenceRecord", back_populates="snapshot", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_ups_snapshots_patient_timestamp", "patient_id", "timestamp"),
    )


class ValueRecord(Base):
    __tablename__ = "ups_values"

    id = Column(String(36), primary_key=True, default=_uuid)
    snapshot_id = Column(String(36), ForeignKey("ups_snapshots.id"), nullable=False, index=True)
    domain = Column(String(50), nullable=False)  # "cardiovascular" | "respiratory"
    descriptor = Column(String(100), nullable=False, index=True)  # p.ej. "heart_rate"
    value = Column(Float, nullable=False)
    unit = Column(String(20), nullable=True)
    provenance = Column(String(20), nullable=False)  # sensor_real | simulacion | derivado
    confidence = Column(Float, nullable=False)
    source_detail = Column(String(255), nullable=True)

    snapshot = relationship("SnapshotRecord", back_populates="values")

    __table_args__ = (
        Index("ix_ups_values_snapshot_descriptor", "snapshot_id", "descriptor"),
    )


class EventRecord(Base):
    __tablename__ = "ups_events"

    id = Column(String(36), primary_key=True, default=_uuid)
    patient_id = Column(String(36), ForeignKey("ups_patients.id"), nullable=False, index=True)
    snapshot_id = Column(String(36), ForeignKey("ups_snapshots.id"), nullable=True, index=True)
    domain = Column(String(50), nullable=False)
    event_type = Column(String(100), nullable=False, index=True)  # EventType.value — ver schema.py
    severity = Column(String(20), nullable=False)
    description = Column(String(500), nullable=False)
    provenance = Column(String(20), nullable=False)
    confidence = Column(Float, nullable=False)
    related_descriptor = Column(String(100), nullable=True)
    timestamp = Column(DateTime, nullable=False, index=True)

    snapshot = relationship("SnapshotRecord", back_populates="events")


class ClinicalImpressionRecord(Base):
    """Fusión de persistencia, Paso 2 (2026-07-15): tabla aditiva -- no toca
    ups_values/ups_events ni ninguna columna de ups_snapshots. Ver
    `clinical_impression.py` para por qué este tipo nunca lleva
    provenance/confidence: deliberadamente no reutiliza esos campos."""

    __tablename__ = "ups_clinical_impressions"

    id = Column(String(36), primary_key=True, default=_uuid)
    snapshot_id = Column(String(36), ForeignKey("ups_snapshots.id"), nullable=False, index=True)
    # patient_id redundante junto a snapshot_id -- mismo patrón que EventRecord,
    # para poder consultar por paciente sin hacer join.
    patient_id = Column(String(36), ForeignKey("ups_patients.id"), nullable=False, index=True)
    category = Column(String(50), nullable=False, index=True)
    notes = Column(String(2000), nullable=True)
    author = Column(String(255), nullable=False)
    emitted_at = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=_utcnow)

    snapshot = relationship("SnapshotRecord", back_populates="clinical_impressions")


class ClinicalReferenceRecord(Base):
    """Presión arterial, Paso 1+2 (2026-07-18): tabla aditiva -- no toca
    ups_values/ups_events/ups_clinical_impressions ni ninguna columna de
    ups_snapshots. Ver `clinical_reference.py` para por qué este tipo nunca
    lleva provenance/confidence de PhysiologicalDescriptor."""

    __tablename__ = "ups_clinical_references"

    id = Column(String(36), primary_key=True, default=_uuid)
    snapshot_id = Column(String(36), ForeignKey("ups_snapshots.id"), nullable=False, index=True)
    # patient_id redundante junto a snapshot_id -- mismo patrón que EventRecord
    # y ClinicalImpressionRecord, para consultar por paciente sin join.
    patient_id = Column(String(36), ForeignKey("ups_patients.id"), nullable=False, index=True)
    scenario = Column(String(50), nullable=False, index=True)
    domain = Column(String(50), nullable=False)
    descriptor = Column(String(100), nullable=False, index=True)
    value = Column(Float, nullable=False)
    unit = Column(String(20), nullable=True)
    citation = Column(String(500), nullable=False)
    phase_note = Column(String(1000), nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    snapshot = relationship("SnapshotRecord", back_populates="clinical_references")
