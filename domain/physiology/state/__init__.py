"""
Unified Physiological State (UPS) — fuente única de verdad del organismo.

Fase 1.1 (ver PLAN.md): esquema tipado + persistencia SQLAlchemy/SQLite,
con procedencia y confianza por valor, trayectoria temporal, y eventos
como entidad de primera clase. Alcance de este slice: dominios
cardiovascular y respiratorio únicamente.
"""

from .builder import from_digital_twin_organism
from .blood_pressure_references import BLOOD_PRESSURE_REFERENCES
from .clinical_impression import ClinicalImpression, ImpressionCategory
from .clinical_impression_repository import (
    create_clinical_impression,
    get_clinical_impressions_for_patient,
    get_clinical_impressions_for_snapshot,
    get_latest_snapshot_id,
    get_snapshot_id_at,
)
from .clinical_reference import ClinicalReferenceValue, estimate_map
from .clinical_reference_repository import (
    create_clinical_reference,
    get_clinical_references_for_patient,
    get_clinical_references_for_snapshot,
)
from .composer import ComposeResult, compose_neuro_cardiac_snapshot
from .db import init_db, make_engine, make_session_factory
from .repository import (
    create_patient,
    get_events,
    get_latest_snapshot_id_with_descriptor,
    get_latest_state,
    get_patient,
    get_state_by_snapshot_id,
    get_value_history,
    rename_patient,
    save_state,
)
from .schema import (
    CONFIDENCE_REFERENCE,
    ConfidenceBand,
    DomainState,
    EventSeverity,
    EventType,
    PhysiologicalDescriptor,
    PhysiologicalEvent,
    Provenance,
    UnifiedPhysiologicalState,
    default_confidence,
)

__all__ = [
    "from_digital_twin_organism",
    "init_db",
    "make_engine",
    "make_session_factory",
    "create_patient",
    "get_events",
    "get_latest_snapshot_id_with_descriptor",
    "get_latest_state",
    "get_patient",
    "get_state_by_snapshot_id",
    "get_value_history",
    "rename_patient",
    "save_state",
    # Compositor multi-dominio (Tanda 1 de (b), 2026-09-08) -- aditivo.
    "ComposeResult",
    "compose_neuro_cardiac_snapshot",
    "CONFIDENCE_REFERENCE",
    "ConfidenceBand",
    "DomainState",
    "EventSeverity",
    "EventType",
    "PhysiologicalDescriptor",
    "PhysiologicalEvent",
    "Provenance",
    "UnifiedPhysiologicalState",
    "default_confidence",
    # Fusión de persistencia, Paso 2 (2026-07-15) -- aditivo.
    "ClinicalImpression",
    "ImpressionCategory",
    "create_clinical_impression",
    "get_clinical_impressions_for_patient",
    "get_clinical_impressions_for_snapshot",
    "get_latest_snapshot_id",
    "get_snapshot_id_at",
    # Presión arterial, Paso 1+2 (2026-07-18) -- aditivo.
    "BLOOD_PRESSURE_REFERENCES",
    "ClinicalReferenceValue",
    "estimate_map",
    "create_clinical_reference",
    "get_clinical_references_for_patient",
    "get_clinical_references_for_snapshot",
]
