"""
Fusión de persistencia, Paso 2 — `ClinicalImpression`.

Cubre: ligadura estructural obligatoria a un snapshot real, ausencia
absoluta de provenance/confidence, ida y vuelta por la base de datos, y que
las tablas existentes del UPS (ups_values/ups_events) siguen intactas y
funcionando sin cambios.
"""

import dataclasses

import pytest
import sqlalchemy.exc

from app.engines.digital_twin_organism import DigitalTwinOrganism
from domain.physiology.state import (
    ClinicalImpression,
    ImpressionCategory,
    Provenance,
    create_clinical_impression,
    create_patient,
    from_digital_twin_organism,
    get_clinical_impressions_for_patient,
    get_clinical_impressions_for_snapshot,
    get_events,
    get_latest_snapshot_id,
    get_latest_state,
    init_db,
    make_engine,
    make_session_factory,
    save_state,
)


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "clinical_impression_test.db"


def _session_factory(path):
    engine = make_engine(path)
    init_db(engine)
    return make_session_factory(engine)


def _save_demo_state(session, patient_id, scenario="healthy"):
    organism = DigitalTwinOrganism()
    organism.create_patient_scenario(scenario)
    state = from_digital_twin_organism(organism, patient_id, Provenance.SIMULACION, 0.9)
    snapshot_id = save_state(session, state)
    return snapshot_id, state


def test_clinical_impression_has_no_provenance_or_confidence_field():
    """Comprobación estructural: el tipo no tiene ningún campo de certeza
    numérica -- ni 'provenance' ni 'confidence' existen en absoluto."""
    field_names = {f.name for f in dataclasses.fields(ClinicalImpression)}
    assert "provenance" not in field_names
    assert "confidence" not in field_names
    assert field_names == {"snapshot_id", "category", "author", "emitted_at", "notes"}


def test_snapshot_id_and_author_are_required(db_path):
    from datetime import datetime, timezone

    with pytest.raises(ValueError, match="snapshot_id"):
        ClinicalImpression(
            snapshot_id="",
            category=ImpressionCategory.ESTABLE,
            author="clinico_demo",
            emitted_at=datetime.now(timezone.utc),
        )

    with pytest.raises(ValueError, match="author"):
        ClinicalImpression(
            snapshot_id="algun-snapshot-real",
            category=ImpressionCategory.ESTABLE,
            author="",
            emitted_at=datetime.now(timezone.utc),
        )


def test_create_and_retrieve_impression_round_trip(db_path):
    SessionLocal = _session_factory(db_path)

    with SessionLocal() as session:
        patient_id = create_patient(session, display_name="Paciente Impresion")
        snapshot_id, _ = _save_demo_state(session, patient_id)

        impression_id = create_clinical_impression(
            session,
            snapshot_id=snapshot_id,
            patient_id=patient_id,
            category=ImpressionCategory.PREOCUPACION_CARDIOVASCULAR,
            author="clinico_demo",
            notes="Ritmo irregular al auscultar; correlacionar con HRV.",
        )
        assert impression_id

    # "Otra sesión" -- sin memoria compartida, igual que test_ups_state.py.
    SessionLocal2 = _session_factory(db_path)
    with SessionLocal2() as session:
        by_snapshot = get_clinical_impressions_for_snapshot(session, snapshot_id)
        by_patient = get_clinical_impressions_for_patient(session, patient_id)

    assert len(by_snapshot) == 1
    imp = by_snapshot[0]
    assert imp.snapshot_id == snapshot_id
    assert imp.category == ImpressionCategory.PREOCUPACION_CARDIOVASCULAR
    assert imp.author == "clinico_demo"
    assert imp.notes == "Ritmo irregular al auscultar; correlacionar con HRV."

    assert len(by_patient) == 1
    assert by_patient[0].snapshot_id == snapshot_id


def test_impression_without_notes_is_allowed(db_path):
    SessionLocal = _session_factory(db_path)
    with SessionLocal() as session:
        patient_id = create_patient(session, display_name="Paciente Sin Notas")
        snapshot_id, _ = _save_demo_state(session, patient_id)

        create_clinical_impression(
            session,
            snapshot_id=snapshot_id,
            patient_id=patient_id,
            category=ImpressionCategory.ESTABLE,
            author="clinico_demo",
        )

        impressions = get_clinical_impressions_for_snapshot(session, snapshot_id)

    assert len(impressions) == 1
    assert impressions[0].notes is None


def test_impression_requires_a_real_existing_snapshot(db_path):
    """La foreign key NOT NULL a ups_snapshots.id se hace cumplir a nivel de
    base de datos -- un snapshot_id inventado debe fallar, no persistirse
    silenciosamente."""
    SessionLocal = _session_factory(db_path)
    with SessionLocal() as session:
        patient_id = create_patient(session, display_name="Paciente Huerfano")
        with pytest.raises(sqlalchemy.exc.IntegrityError):
            create_clinical_impression(
                session,
                snapshot_id="snapshot-que-no-existe",
                patient_id=patient_id,
                category=ImpressionCategory.ESTABLE,
                author="clinico_demo",
            )


def test_multiple_impressions_on_same_snapshot_preserve_order(db_path):
    SessionLocal = _session_factory(db_path)
    with SessionLocal() as session:
        patient_id = create_patient(session, display_name="Paciente Multi")
        snapshot_id, _ = _save_demo_state(session, patient_id)

        create_clinical_impression(
            session, snapshot_id=snapshot_id, patient_id=patient_id,
            category=ImpressionCategory.ESTABLE, author="clinico_a", notes="Primera revisión.",
        )
        create_clinical_impression(
            session, snapshot_id=snapshot_id, patient_id=patient_id,
            category=ImpressionCategory.REQUIERE_SEGUIMIENTO, author="clinico_b", notes="Segunda opinión.",
        )

        impressions = get_clinical_impressions_for_snapshot(session, snapshot_id)

    assert len(impressions) == 2
    assert [i.author for i in impressions] == ["clinico_a", "clinico_b"]


def test_get_latest_snapshot_id_matches_get_latest_state(db_path):
    SessionLocal = _session_factory(db_path)
    with SessionLocal() as session:
        patient_id = create_patient(session, display_name="Paciente Snapshot Id")
        first_snapshot_id, _ = _save_demo_state(session, patient_id, scenario="healthy")
        second_snapshot_id, _ = _save_demo_state(session, patient_id, scenario="exercise")

        latest_id = get_latest_snapshot_id(session, patient_id)

    assert latest_id == second_snapshot_id
    assert latest_id != first_snapshot_id


def test_existing_ups_tables_unaffected_by_clinical_impressions(db_path):
    """Regresión: ups_values/ups_events y UnifiedPhysiologicalState siguen
    funcionando exactamente igual, sin ningún campo de ClinicalImpression
    embebido -- opción (ii) del diseño aprobado."""
    SessionLocal = _session_factory(db_path)
    with SessionLocal() as session:
        patient_id = create_patient(session, display_name="Paciente Regresion")
        snapshot_id, state = _save_demo_state(session, patient_id, scenario="arrhythmia")

        create_clinical_impression(
            session, snapshot_id=snapshot_id, patient_id=patient_id,
            category=ImpressionCategory.CRITICO, author="clinico_demo", notes="Revisar de inmediato.",
        )

    with SessionLocal() as session:
        recovered = get_latest_state(session, patient_id)
        events = get_events(session, patient_id)

    assert recovered is not None
    assert not hasattr(recovered, "clinical_impressions")
    assert recovered.cardiovascular.get("heart_rate") is not None
    assert isinstance(events, list)
