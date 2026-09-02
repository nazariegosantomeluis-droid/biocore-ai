"""
Persistencia de `ClinicalImpression` — deliberadamente separado de
`repository.py` (que traduce `PhysiologicalDescriptor`/`PhysiologicalEvent`
medidos/derivados). Una impresión clínica humana es un tipo de dato
distinto; mantener su repositorio en un archivo aparte evita que quien lea
`repository.py` vea código de juicios humanos mezclado con el de datos
medidos.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .clinical_impression import ClinicalImpression, ImpressionCategory
from .models import ClinicalImpressionRecord, SnapshotRecord

__all__ = [
    "create_clinical_impression",
    "get_clinical_impressions_for_snapshot",
    "get_clinical_impressions_for_patient",
    "get_latest_snapshot_id",
    "get_snapshot_id_at",
]


def _to_naive_utc(ts: datetime) -> datetime:
    """SQLite no conserva tzinfo. Normalizamos a UTC naive al escribir —
    mismo criterio que `repository.py`."""
    if ts.tzinfo is not None:
        return ts.astimezone(timezone.utc).replace(tzinfo=None)
    return ts


def _to_aware_utc(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts


def _from_record(rec: ClinicalImpressionRecord) -> ClinicalImpression:
    return ClinicalImpression(
        snapshot_id=rec.snapshot_id,
        category=ImpressionCategory(rec.category),
        author=rec.author,
        emitted_at=_to_aware_utc(rec.emitted_at),
        notes=rec.notes,
    )


def create_clinical_impression(
    session: Session,
    snapshot_id: str,
    patient_id: str,
    category: ImpressionCategory,
    author: str,
    notes: Optional[str] = None,
    emitted_at: Optional[datetime] = None,
) -> str:
    """Persiste una impresión clínica humana ligada a un snapshot real del
    UPS. `snapshot_id` debe corresponder a un `SnapshotRecord` ya
    persistido -- la foreign key NOT NULL lo exige a nivel de base de
    datos, además de la validación en `ClinicalImpression.__post_init__`."""
    impression = ClinicalImpression(
        snapshot_id=snapshot_id,
        category=category,
        author=author,
        emitted_at=emitted_at or datetime.now(timezone.utc),
        notes=notes,
    )  # valida snapshot_id/author antes de tocar la base de datos

    record = ClinicalImpressionRecord(
        snapshot_id=impression.snapshot_id,
        patient_id=patient_id,
        category=impression.category.value,
        notes=impression.notes,
        author=impression.author,
        emitted_at=_to_naive_utc(impression.emitted_at),
    )
    session.add(record)
    session.commit()
    return record.id


def get_clinical_impressions_for_snapshot(session: Session, snapshot_id: str) -> List[ClinicalImpression]:
    stmt = (
        select(ClinicalImpressionRecord)
        .where(ClinicalImpressionRecord.snapshot_id == snapshot_id)
        .order_by(ClinicalImpressionRecord.emitted_at.asc())
    )
    records = session.execute(stmt).scalars().all()
    return [_from_record(r) for r in records]


def get_clinical_impressions_for_patient(
    session: Session, patient_id: str, limit: int = 50
) -> List[ClinicalImpression]:
    stmt = (
        select(ClinicalImpressionRecord)
        .where(ClinicalImpressionRecord.patient_id == patient_id)
        .order_by(ClinicalImpressionRecord.emitted_at.desc())
        .limit(limit)
    )
    records = session.execute(stmt).scalars().all()
    return [_from_record(r) for r in records]


def get_latest_snapshot_id(session: Session, patient_id: str) -> Optional[str]:
    """Conveniencia para ligar una `ClinicalImpression` al snapshot más
    reciente de un paciente sin tocar `repository.py` -- mismo criterio de
    'más reciente' que `get_latest_state()` (timestamp descendente).
    `get_latest_state()` no expone el id del snapshot que arma (lo diluye
    en `UnifiedPhysiologicalState`, que deliberadamente no lo tiene), así
    que esta consulta va directo al modelo.

    Deuda de producción (2026-08-12): esta función quedó sin desempate
    cuando se arregló su gemela `get_snapshot_id_at()` (2026-08-11),
    marcada "fuera de alcance" -- se reprodujo el mismo bug por esta vía
    (`test_get_latest_snapshot_id_matches_get_latest_state` intermitente).

    Primer intento (Capa B, `ORDER BY timestamp DESC, rowid DESC`) NO fue
    suficiente -- verificado con el mismo test corrido 100 veces: seguía
    fallando 2/100. Diagnóstico: `_save_demo_state()` crea dos
    `DigitalTwinOrganism()` nuevos en sucesión rápida; la Capa A (timestamp
    monótono) protege dentro de la vida de UN organismo, no entre
    instancias distintas -- y `datetime.now()` en Windows NO es
    estrictamente monótono entre dos llamadas consecutivas de procesos/
    objetos distintos (medido directamente: 27/500 pares de timestamps
    generados en sucesión inmediata salieron con el segundo un microsegundo
    ANTES que el primero -- p.ej. `.380843` seguido de `.380842`). No es un
    empate que un desempate por `rowid` alcance a resolver -- son
    timestamps DISTINTOS pero en el orden equivocado, así que
    `ORDER BY timestamp DESC` los ordena mal de forma determinista, sin
    ninguna ambigüedad que un tie-break pueda corregir.

    Arreglo real: `rowid` (orden de inserción real en SQLite, ajeno al
    reloj del sistema) pasa a ser el ÚNICO criterio de orden -- no un
    desempate. Válido porque `save_state()` es la única vía de escritura y
    siempre inserta el estado recién calculado, nunca uno retroactivo fuera
    de orden -- orden de inserción y recencia cronológica coinciden por
    invariante de la aplicación, no por el reloj. Verificado: 0/100 fallos
    tras este cambio (antes: 2/100 con el intento de Capa B por sí solo).
    Ver CHANGELOG.md."""
    stmt = (
        select(SnapshotRecord.id)
        .where(SnapshotRecord.patient_id == patient_id)
        .order_by(text("rowid DESC"))
        .limit(1)
    )
    return session.execute(stmt).scalar_one_or_none()


def get_snapshot_id_at(session: Session, patient_id: str, timestamp: datetime) -> Optional[str]:
    """Conveniencia (2026-08-06): resuelve el id del snapshot de un
    (`patient_id`, `timestamp`) EXACTO -- no necesariamente el más
    reciente. Necesario para `case_bank.generate_case()`: elige al azar
    CUALQUIERA de los 6 horizontes reales de `run_rich_scenario()` como
    "el caso", no siempre el último, así que `get_latest_snapshot_id()` no
    sirve aquí (podría devolver un snapshot distinto al horizonte que el
    estudiante realmente ve). Mismo criterio de normalización de tzinfo
    que `save_state()` (`repository.py`) -- el timestamp debe coincidir
    exactamente con el que quedó persistido.

    Deuda de producción (2026-08-11, Capa B -- defensa complementaria a la
    Capa A en `DigitalTwinOrganism.update_from_sensors()`, que ya elimina
    la colisión en el origen): `timestamp` puede coincidir en más de una
    fila si dos snapshots del mismo paciente comparten el mismo instante
    (medido: ~1-2% de los casos, antes de la Capa A). Sin desempate, el
    `.limit(1)` era no determinista y podía devolver el snapshot
    equivocado (confirmado: el que NO tenía las referencias clínicas
    adjuntas). `ORDER BY rowid DESC` desempata por orden de inserción real
    en SQLite (verificado empíricamente, no asumido) -- el snapshot
    insertado más tarde es siempre el horizonte generado después, nunca al
    revés. `id` (UUID aleatorio) y `created_at` (también `datetime.now()`,
    mismo problema de resolución de reloj) NO sirven como desempate; el
    rowid implícito de SQLite sí, porque es estrictamente secuencial por
    inserción y no depende del reloj del sistema. Cuando no hay empate
    (el caso normal, >98% de las veces) esta cláusula no cambia el
    resultado -- solo un tie-break, no un reordenamiento de la consulta.
    Ver CHANGELOG.md."""
    stmt = (
        select(SnapshotRecord.id)
        .where(SnapshotRecord.patient_id == patient_id, SnapshotRecord.timestamp == _to_naive_utc(timestamp))
        .order_by(text("rowid DESC"))
        .limit(1)
    )
    return session.execute(stmt).scalar_one_or_none()
