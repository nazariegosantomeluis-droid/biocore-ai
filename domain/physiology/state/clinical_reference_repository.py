"""
Persistencia de `ClinicalReferenceValue` -- deliberadamente separado de
`repository.py` (datos medidos/derivados) y de `clinical_impression_repository.py`
(juicio humano): un valor de referencia clínica es un tercer tipo de dato,
distinto de ambos.
"""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from .clinical_reference import ClinicalReferenceValue
from .models import ClinicalReferenceRecord

__all__ = [
    "create_clinical_reference",
    "get_clinical_references_for_snapshot",
    "get_clinical_references_for_patient",
]


def _from_record(rec: ClinicalReferenceRecord) -> ClinicalReferenceValue:
    return ClinicalReferenceValue(
        scenario=rec.scenario,
        domain=rec.domain,
        descriptor=rec.descriptor,
        value=rec.value,
        unit=rec.unit or "",
        citation=rec.citation,
        phase_note=rec.phase_note,
    )


def create_clinical_reference(
    session: Session,
    snapshot_id: str,
    patient_id: str,
    reference: ClinicalReferenceValue,
) -> str:
    """Persiste un `ClinicalReferenceValue` ya construido (y por lo tanto ya
    validado -- `citation` obligatoria) ligado a un snapshot real del UPS."""
    record = ClinicalReferenceRecord(
        snapshot_id=snapshot_id,
        patient_id=patient_id,
        scenario=reference.scenario,
        domain=reference.domain,
        descriptor=reference.descriptor,
        value=reference.value,
        unit=reference.unit,
        citation=reference.citation,
        phase_note=reference.phase_note,
    )
    session.add(record)
    session.commit()
    return record.id


def get_clinical_references_for_snapshot(session: Session, snapshot_id: str) -> List[ClinicalReferenceValue]:
    stmt = (
        select(ClinicalReferenceRecord)
        .where(ClinicalReferenceRecord.snapshot_id == snapshot_id)
        .order_by(ClinicalReferenceRecord.descriptor.asc())
    )
    records = session.execute(stmt).scalars().all()
    return [_from_record(r) for r in records]


def get_clinical_references_for_patient(
    session: Session, patient_id: str, limit: int = 50
) -> List[ClinicalReferenceValue]:
    stmt = (
        select(ClinicalReferenceRecord)
        .where(ClinicalReferenceRecord.patient_id == patient_id)
        .order_by(ClinicalReferenceRecord.created_at.desc())
        .limit(limit)
    )
    records = session.execute(stmt).scalars().all()
    return [_from_record(r) for r in records]
