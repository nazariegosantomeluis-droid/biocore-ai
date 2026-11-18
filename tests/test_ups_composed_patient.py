"""T0 · El paciente compuesto (2026-11-18): todas las pantallas leen un solo paciente.

Medido el 2026-11-17: tras guardar en el gemelo (FC 100, FR 24, SpO₂ 92) y luego en el EEG Lab, `get_latest_state()`
devolvía FC/FR/SpO₂ en `None` -- el último snapshot gana y cada laboratorio "borraba" a los demás. Estas pruebas fijan
la regla de `get_composed_patient()`: el último valor de cada descriptor; uno de un snapshot anterior viaja como
`ARRASTRE_TEMPORAL` con su origen y su edad; un derivado viaja solo con sus entradas; leer no escribe.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.engines.digital_twin_organism import DigitalTwinOrganism
from domain.physiology.state import (
    DomainState,
    EventType,
    PhysiologicalDescriptor,
    Provenance,
    UnifiedPhysiologicalState,
    create_patient,
    from_digital_twin_organism,
    get_composed_patient,
    init_db,
    make_engine,
    make_session_factory,
    save_state,
)
from domain.physiology.state.models import SnapshotRecord, ValueRecord

EEG_BANDS = {"delta_power": 1.0, "theta_power": 1.0, "alpha_power": 2.0, "beta_power": 4.0, "gamma_power": 0.5}


@pytest.fixture
def factory(tmp_path):
    engine = make_engine(tmp_path / "ups.db")
    init_db(engine)
    return make_session_factory(engine)


@pytest.fixture
def pid(factory):
    with factory() as s:
        patient_id = create_patient(s, display_name="Paciente compuesto (prueba)")
        s.commit()
    return patient_id


def _d(name, value, unit="", prov=Provenance.SIMULACION, conf=0.6, detail=None):
    return PhysiologicalDescriptor(name, float(value), unit, prov, conf, detail)


def _save(factory, pid, cv=(), resp=(), neuro=(), ts=None):
    state = UnifiedPhysiologicalState(
        patient_id=pid,
        timestamp=ts or datetime.now(timezone.utc),
        cardiovascular=DomainState("cardiovascular", {d.name: d for d in cv}),
        respiratory=DomainState("respiratory", {d.name: d for d in resp}),
        neurological=DomainState("neurological", {d.name: d for d in neuro}),
        events=[],
    )
    with factory() as s:
        return save_state(s, state)


def _save_organism(factory, pid, signals, detail):
    organism = DigitalTwinOrganism()
    organism.update_from_sensors(signals)
    with factory() as s:
        return save_state(s, from_digital_twin_organism(organism, pid, provenance=Provenance.SIMULACION,
                                                        source_detail=detail))


def _twin(factory, pid, hr=100):
    return _save_organism(factory, pid, {"ecg": {"heart_rate": hr},
                                         "respiratory": {"respiratory_rate": 24, "spo2": 92}}, "gemelo")


def _eeg(factory, pid):
    return _save_organism(factory, pid, {"eeg": dict(EEG_BANDS)}, "eeg_neuro_lab")


def _composed(factory, pid, **kw):
    with factory() as s:
        return get_composed_patient(s, pid, **kw)


def test_sin_snapshots_devuelve_none(factory, pid):
    assert _composed(factory, pid) is None


def test_gemelo_luego_eeg_conserva_signos_como_arrastre(factory, pid):
    _twin(factory, pid)
    _eeg(factory, pid)
    composed = _composed(factory, pid)
    hr = composed.state.cardiovascular.get("heart_rate")
    assert hr is not None and hr.value == 100.0
    assert hr.provenance is Provenance.ARRASTRE_TEMPORAL
    assert composed.origins[("cardiovascular", "heart_rate")].provenance is Provenance.SIMULACION
    assert composed.state.respiratory.get("respiratory_rate").value == 24.0
    assert composed.state.respiratory.get("spo2").value == 92.0
    assert ("neurological", "bar") not in composed.origins
    assert composed.state.neurological.get("bar").provenance is Provenance.SIMULACION


def test_arrastre_hereda_confianza_y_declara_origen(factory, pid):
    first = _save(factory, pid, cv=[_d("heart_rate", 88, "bpm", Provenance.SENSOR_REAL, 0.85, "ecg_lead_II")])
    _eeg(factory, pid)
    hr = _composed(factory, pid).state.cardiovascular.get("heart_rate")
    assert hr.confidence == 0.85
    assert first in hr.source_detail and "sensor_real" in hr.source_detail and "ecg_lead_II" in hr.source_detail


def test_la_lectura_no_escribe(factory, pid):
    _twin(factory, pid)
    _eeg(factory, pid)
    with factory() as s:
        before = (s.query(SnapshotRecord).count(), s.query(ValueRecord).count())
    _composed(factory, pid)
    _composed(factory, pid)
    with factory() as s:
        assert (s.query(SnapshotRecord).count(), s.query(ValueRecord).count()) == before


def test_valor_mas_nuevo_gana(factory, pid):
    _save(factory, pid, cv=[_d("heart_rate", 100, "bpm")])
    _save(factory, pid, cv=[_d("heart_rate", 80, "bpm")])
    composed = _composed(factory, pid)
    hr = composed.state.cardiovascular.get("heart_rate")
    assert hr.value == 80.0 and hr.provenance is Provenance.SIMULACION
    assert ("cardiovascular", "heart_rate") not in composed.origins


def test_solo_eeg_signos_sin_dato(factory, pid):
    _eeg(factory, pid)
    state = _composed(factory, pid).state
    assert state.cardiovascular.get("heart_rate") is None
    assert state.respiratory.get("spo2") is None


def test_derivado_viaja_con_su_entrada(factory, pid):
    twin_id = _twin(factory, pid)
    with factory() as s:
        from domain.physiology.state import get_state_by_snapshot_id
        assert get_state_by_snapshot_id(s, twin_id).cardiovascular.get("news2_pulse_points") is not None  # precondición
    _eeg(factory, pid)
    composed = _composed(factory, pid)
    assert composed.state.cardiovascular.get("news2_pulse_points") is not None
    assert (composed.origins[("cardiovascular", "news2_pulse_points")].snapshot_id
            == composed.origins[("cardiovascular", "heart_rate")].snapshot_id == twin_id)


def test_derivado_se_omite_si_su_entrada_es_mas_nueva(factory, pid):
    _twin(factory, pid)
    _save(factory, pid, cv=[_d("heart_rate", 135, "bpm", Provenance.SENSOR_REAL, 0.85)])
    composed = _composed(factory, pid)
    hr = composed.state.cardiovascular.get("heart_rate")
    assert hr.value == 135.0 and hr.provenance is Provenance.SENSOR_REAL
    assert composed.state.cardiovascular.get("news2_pulse_points") is None


def test_acoplado_viejo_se_omite_con_fc_nueva(factory, pid):
    _save(factory, pid, cv=[_d("heart_rate", 90, "bpm"),
                            _d("heart_rate_acoplado", 105, "bpm", Provenance.DERIVADO_ACOPLAMIENTO, 0.7)],
          neuro=[_d("alpha_power", 2.0), _d("beta_power", 4.0), _d("bar", 2.0)])
    _save(factory, pid, cv=[_d("heart_rate", 70, "bpm")])
    composed = _composed(factory, pid)
    assert composed.state.neurological.get("bar") is not None      # el bar sigue: viaja con sus bandas
    assert composed.state.cardiovascular.get("heart_rate_acoplado") is None


def test_mismo_lab_sin_descriptor_arrastra_el_viejo(factory, pid):
    _save(factory, pid, neuro=[_d("alpha_power", 2.0), _d("chi_aperiodic", 1.4)])
    _save(factory, pid, neuro=[_d("alpha_power", 3.0)])
    composed = _composed(factory, pid)
    chi = composed.state.neurological.get("chi_aperiodic")
    assert chi is not None and chi.provenance is Provenance.ARRASTRE_TEMPORAL
    assert ("neurological", "chi_aperiodic") in composed.origins
    alpha = composed.state.neurological.get("alpha_power")
    assert alpha.value == 3.0 and ("neurological", "alpha_power") not in composed.origins


def test_timestamps_invertidos(factory, pid):
    t0 = datetime.now(timezone.utc)
    _save(factory, pid, cv=[_d("heart_rate", 100, "bpm")], ts=t0)
    _save(factory, pid, neuro=[_d("alpha_power", 1.5)], ts=t0 - timedelta(microseconds=1))
    composed = _composed(factory, pid)
    assert composed.state.neurological.get("alpha_power").provenance is Provenance.SIMULACION  # el último por rowid
    assert all(o.age_s >= 0 for o in composed.origins.values())


def test_max_age_corta(factory, pid):
    t0 = datetime.now(timezone.utc)
    _save(factory, pid, cv=[_d("heart_rate", 100, "bpm")], ts=t0 - timedelta(minutes=10))
    _save(factory, pid, neuro=[_d("bar", 1.5)], ts=t0)
    assert _composed(factory, pid, max_age_s=60).state.cardiovascular.get("heart_rate") is None
    composed = _composed(factory, pid, max_age_s=None)
    assert composed.state.cardiovascular.get("heart_rate").value == 100.0
    assert composed.origins[("cardiovascular", "heart_rate")].age_s == pytest.approx(600, abs=1)


def test_eventos_solo_del_ultimo(factory, pid):
    twin_id = _twin(factory, pid, hr=30)
    with factory() as s:
        from domain.physiology.state import get_state_by_snapshot_id
        events = get_state_by_snapshot_id(s, twin_id).events
        assert any(e.event_type is EventType.PULSE_NEWS2_3_POINTS for e in events)  # precondición
    _eeg(factory, pid)
    assert _composed(factory, pid).state.events == []


# ── Revisión final de la T0 (2026-11-18) ──

def test_razones_eeg_viajan_con_sus_bandas(factory, pid):
    """BAR, DAR y TBR salen de las bandas del MISMO snapshot (`builder.py`). Un EEG nuevo con bandas nuevas pero sin
    razón (alfa ~0, banda faltante) no puede mostrar la razón vieja junto a las bandas nuevas."""
    _save(factory, pid, neuro=[_d("delta_power", 1.0), _d("theta_power", 1.0), _d("alpha_power", 2.0),
                               _d("beta_power", 4.0), _d("bar", 2.0), _d("dar", 0.5), _d("tbr", 0.25)])
    _save(factory, pid, neuro=[_d("delta_power", 1.0), _d("theta_power", 1.0), _d("alpha_power", 3.0),
                               _d("beta_power", 4.0)])
    neuro = _composed(factory, pid).state.neurological
    assert neuro.get("alpha_power").value == 3.0
    assert neuro.get("bar") is None and neuro.get("dar") is None and neuro.get("tbr") is None


def test_duplicado_en_un_snapshot_coincide_con_get_latest_state(factory, pid):
    """`append_descriptors` puede agregar una segunda fila con el mismo nombre al mismo snapshot: el paciente
    compuesto elige la misma que `get_latest_state` (la última insertada)."""
    from domain.physiology.state import get_latest_state
    from domain.physiology.state.repository import append_descriptors
    sid = _save(factory, pid, cv=[_d("heart_rate", 90, "bpm")])
    with factory() as s:
        append_descriptors(s, sid, "cardiovascular", [_d("heart_rate", 95, "bpm")])
        s.commit()
        expected = get_latest_state(s, pid).cardiovascular.get("heart_rate").value
    assert expected == 95.0
    assert _composed(factory, pid).state.cardiovascular.get("heart_rate").value == expected
