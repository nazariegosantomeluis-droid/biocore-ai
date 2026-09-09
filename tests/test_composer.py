"""
Compositor multi-dominio del paciente único -- Tanda 1 de (b), 2026-09-08.

Prueba que `compose_neuro_cardiac_snapshot()` compone BAR real + FC real de
forma HONESTA (procedencia por descriptor, arrastre declarado, gate
temporal espejo del PLV) ANTES de que dispare ningún acoplamiento. Cero
`apply_couplings`, cero UI.
"""

from datetime import datetime, timedelta, timezone

import pytest

from domain.physiology.state import (
    ComposeResult,
    DomainState,
    PhysiologicalDescriptor,
    Provenance,
    UnifiedPhysiologicalState,
    compose_neuro_cardiac_snapshot,
    create_patient,
    get_latest_snapshot_id,
    get_latest_snapshot_id_with_descriptor,
    get_state_by_snapshot_id,
    init_db,
    make_engine,
    make_session_factory,
    save_state,
)


@pytest.fixture
def session_factory(tmp_path):
    engine = make_engine(tmp_path / "composer_test.db")
    init_db(engine)
    return make_session_factory(engine)


def _state(pid, ts, *, cardio=None, neuro=None):
    return UnifiedPhysiologicalState(
        patient_id=pid,
        timestamp=ts,
        cardiovascular=DomainState(domain="cardiovascular", descriptors=cardio or {}),
        respiratory=DomainState(domain="respiratory", descriptors={}),
        neurological=DomainState(domain="neurological", descriptors=neuro or {}),
        events=[],
    )


def _hr_desc(value=72.0, prov=Provenance.SIMULACION, conf=0.75):
    return PhysiologicalDescriptor("heart_rate", value, "bpm", prov, conf, "ecg_lab:SENSOR_REAL")


def _bar_desc(value=2.4, conf=0.75):
    return PhysiologicalDescriptor(
        "bar", value, "ratio (adimensional)", Provenance.SIMULACION, conf,
        "beta_alpha_ratio | Schutter DJLG 2006",
    )


def _save_ecg(session, pid, ts, hr=None):
    return save_state(session, _state(pid, ts, cardio={"heart_rate": hr or _hr_desc()}))


def _save_eeg_bar(session, pid, ts, bar=None):
    return save_state(session, _state(pid, ts, neuro={"bar": bar or _bar_desc()}))


# --- Parte A: la consulta de lectura por dominio ---------------------------

def test_get_latest_snapshot_id_with_descriptor_ignores_snapshots_without_it(session_factory):
    with session_factory() as s:
        pid = create_patient(s, display_name="query-target")
        now = datetime.now(timezone.utc)

        first_bar = _save_eeg_bar(s, pid, now - timedelta(seconds=30))
        # dos snapshots MÁS RECIENTES que NO tienen `bar` (uno neuro sin bar, uno cardio)
        save_state(s, _state(pid, now - timedelta(seconds=20), neuro={
            "beta_power": PhysiologicalDescriptor("beta_power", 30.0, "power (u.a.)", Provenance.SIMULACION, 0.75, "x"),
        }))
        _save_ecg(s, pid, now)
        second_bar = _save_eeg_bar(s, pid, now + timedelta(seconds=10))

        got = get_latest_snapshot_id_with_descriptor(s, pid, "neurological", "bar")
        assert got == second_bar          # el ÚLTIMO con `bar`, no el último snapshot
        assert got != first_bar

        # y si nadie tiene el descriptor -> None
        assert get_latest_snapshot_id_with_descriptor(s, pid, "respiratory", "spo2") is None


# --- Parte D: el camino feliz --------------------------------------------

def test_happy_path_composes_bar_and_carried_hr_with_honest_provenance(session_factory):
    with session_factory() as s:
        pid = create_patient(s, display_name="happy")
        now = datetime.now(timezone.utc)
        hr_snap = _save_ecg(s, pid, now - timedelta(seconds=45), hr=_hr_desc(value=78.0, conf=0.82))
        _save_eeg_bar(s, pid, now, bar=_bar_desc(value=2.7))

        result = compose_neuro_cardiac_snapshot(s, pid)

        assert isinstance(result, ComposeResult)
        assert result.available is True
        assert result.snapshot_id is not None
        assert result.hr_age_s == pytest.approx(45.0, abs=1.0)

        composed = get_state_by_snapshot_id(s, result.snapshot_id)
        # bar: copia LITERAL, procedencia de origen intacta
        bar = composed.neurological.get("bar")
        assert bar.value == pytest.approx(2.7)
        assert bar.provenance == Provenance.SIMULACION
        assert bar.unit == "ratio (adimensional)"
        # heart_rate: valor real, pero ARRASTRE_TEMPORAL + declaración
        hr = composed.cardiovascular.get("heart_rate")
        assert hr.value == pytest.approx(78.0)          # valor real sin tocar
        assert hr.confidence == pytest.approx(0.82)     # confidence heredada TAL CUAL
        assert hr.provenance == Provenance.ARRASTRE_TEMPORAL
        assert hr_snap in hr.source_detail              # id del snapshot de origen
        assert "edad 45s" in hr.source_detail
        assert "FC arrastrada" in hr.source_detail
        # respiratorio vacío -- el compositor no inventa lo que no tiene
        assert composed.respiratory.descriptors == {}


def test_carry_within_window_declares_age_correctly(session_factory):
    with session_factory() as s:
        pid = create_patient(s, display_name="within-window")
        now = datetime.now(timezone.utc)
        _save_ecg(s, pid, now - timedelta(seconds=60))
        _save_eeg_bar(s, pid, now)

        result = compose_neuro_cardiac_snapshot(s, pid, max_hr_carry_age_s=120.0)

        assert result.available is True
        assert result.hr_age_s == pytest.approx(60.0, abs=1.0)
        hr = get_state_by_snapshot_id(s, result.snapshot_id).cardiovascular.get("heart_rate")
        assert "edad 60s" in hr.source_detail


# --- Parte D: las tres barandillas de "no disponible" -------------------

def test_hr_too_old_degrades_to_unavailable_and_persists_nothing(session_factory):
    with session_factory() as s:
        pid = create_patient(s, display_name="too-old")
        now = datetime.now(timezone.utc)
        _save_ecg(s, pid, now - timedelta(seconds=300))     # 5 min viejo
        _save_eeg_bar(s, pid, now)
        snap_before = get_latest_snapshot_id(s, pid)

        result = compose_neuro_cardiac_snapshot(s, pid, max_hr_carry_age_s=120.0)

        assert result.available is False
        assert result.snapshot_id is None
        assert "demasiado vieja" in result.reason
        assert "300s > 120s" in result.reason
        assert result.hr_age_s == pytest.approx(300.0, abs=1.0)
        # NADA se persistió -- el último snapshot sigue siendo el de antes
        assert get_latest_snapshot_id(s, pid) == snap_before


def test_no_bar_persisted_is_unavailable(session_factory):
    with session_factory() as s:
        pid = create_patient(s, display_name="no-bar")
        _save_ecg(s, pid, datetime.now(timezone.utc))       # solo ECG guardado
        snap_before = get_latest_snapshot_id(s, pid)

        result = compose_neuro_cardiac_snapshot(s, pid)

        assert result.available is False
        assert result.reason == "sin BAR persistido"
        assert result.snapshot_id is None
        assert get_latest_snapshot_id(s, pid) == snap_before


def test_no_measured_hr_is_unavailable(session_factory):
    with session_factory() as s:
        pid = create_patient(s, display_name="no-hr")
        _save_eeg_bar(s, pid, datetime.now(timezone.utc))   # solo EEG/bar guardado
        snap_before = get_latest_snapshot_id(s, pid)

        result = compose_neuro_cardiac_snapshot(s, pid)

        assert result.available is False
        assert result.reason == "sin FC medida persistida"
        assert result.snapshot_id is None
        assert get_latest_snapshot_id(s, pid) == snap_before
