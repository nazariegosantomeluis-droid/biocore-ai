"""T1 · El gemelo lee al paciente compuesto (2026-11-18).

Antes, el cuerpo del gemelo se dibujaba solo con el organismo en memoria (sliders o escenario): lo que guardaban los
laboratorios -- bandas del EEG, activación del EMG, valores de sensor real -- nunca llegaba al gemelo. Regla firmada
(decisión del diseño): lo que el estudiante mueve ahora gana; lo que no movió viene del paciente, cada valor con su
procedencia. El músculo, que no tenía tarjeta, ahora la tiene.
"""

from datetime import datetime, timezone
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from app.engines.digital_twin_organism import DigitalTwinOrganism
from app.utils.physiological_state import overlay_current_on_composed
from domain.physiology.state import (
    DomainState, EventSeverity, EventType, PhysiologicalDescriptor, PhysiologicalEvent, Provenance,
    UnifiedPhysiologicalState, create_patient, from_digital_twin_organism, get_composed_patient, init_db, make_engine,
    make_session_factory, save_state,
)

MAIN = str(Path("app/main.py").resolve())
PATIENT_KEY = "twin_shell_ups_patient_id"
EEG = {"eeg": {"delta_power": 1.0, "theta_power": 1.0, "alpha_power": 2.0, "beta_power": 4.0, "gamma_power": 0.5}}
EMG = {"emg": {"activation": 42.0, "median_frequency": 85.0}}


def _d(name, value, unit="", prov=Provenance.SIMULACION):
    return PhysiologicalDescriptor(name, float(value), unit, prov, 0.6, None)


def _state(pid, cv=(), resp=(), neuro=(), events=()):
    return UnifiedPhysiologicalState(
        patient_id=pid, timestamp=datetime.now(timezone.utc),
        cardiovascular=DomainState("cardiovascular", {d.name: d for d in cv}),
        respiratory=DomainState("respiratory", {d.name: d for d in resp}),
        neurological=DomainState("neurological", {d.name: d for d in neuro}),
        events=list(events),
    )


@pytest.fixture
def factory(tmp_path):
    engine = make_engine(tmp_path / "ups.db")
    init_db(engine)
    return make_session_factory(engine)


@pytest.fixture
def pid(factory):
    with factory() as s:
        return create_patient(s, display_name="Gemelo compuesto (prueba)")


def _composed(factory, pid):
    with factory() as s:
        return get_composed_patient(s, pid)


def _save(factory, state):
    with factory() as s:
        save_state(s, state)


# ── Task 1: la superposición ──

def test_sin_paciente_devuelve_el_estado_actual(pid):
    current = _state(pid, cv=[_d("heart_rate", 72, "bpm")])
    state, origins = overlay_current_on_composed(current, None)
    assert state is current and origins == {}


def test_lo_actual_gana_y_lo_demas_viene_del_paciente(factory, pid):
    _save(factory, _state(pid, cv=[_d("heart_rate", 100, "bpm")],
                          neuro=[_d("alpha_power", 2.0), _d("beta_power", 4.0)]))
    _save(factory, _state(pid, resp=[_d("spo2", 95, "%")]))     # vuelve arrastre lo anterior
    current = _state(pid, cv=[_d("heart_rate", 72, "bpm")], neuro=[_d("stress_level", 35)])
    state, origins = overlay_current_on_composed(current, _composed(factory, pid))
    assert state.cardiovascular.get("heart_rate").value == 72.0
    assert ("cardiovascular", "heart_rate") not in origins
    assert state.neurological.get("alpha_power").value == 2.0
    assert origins[("neurological", "alpha_power")].provenance is Provenance.SIMULACION
    assert state.neurological.get("stress_level").value == 35.0
    assert state.respiratory.get("spo2").value == 95.0


def test_derivado_viejo_se_quita_si_el_slider_trae_su_entrada(factory, pid):
    _save(factory, _state(pid, cv=[_d("heart_rate", 100, "bpm"), _d("news2_pulse_points", 1)]))
    current = _state(pid, cv=[_d("heart_rate", 140, "bpm")])
    state, _ = overlay_current_on_composed(current, _composed(factory, pid))
    assert state.cardiovascular.get("news2_pulse_points") is None


def test_evento_viejo_no_pinta_un_dominio_que_se_movio(factory, pid):
    organism = DigitalTwinOrganism()
    organism.update_from_sensors({"ecg": {"heart_rate": 30}})
    _save(factory, from_digital_twin_organism(organism, pid, provenance=Provenance.SIMULACION, source_detail="prueba"))
    composed = _composed(factory, pid)
    assert any(e.domain == "cardiovascular" for e in composed.state.events)          # precondición
    state, _ = overlay_current_on_composed(_state(pid, cv=[_d("heart_rate", 72, "bpm")]), composed)
    assert not [e for e in state.events if e.domain == "cardiovascular"]


def test_evento_del_paciente_se_conserva_en_dominio_no_movido(factory, pid):
    event = PhysiologicalEvent(event_type=EventType.SPO2_NEWS2_3_POINTS, domain="respiratory",
                               severity=EventSeverity.WARNING, description="SpO₂ ≤ 91 % (prueba)",
                               provenance=Provenance.SIMULACION, confidence=0.6, timestamp=datetime.now(timezone.utc))
    _save(factory, _state(pid, resp=[_d("spo2", 88, "%")], events=[event]))
    state, _ = overlay_current_on_composed(_state(pid, cv=[_d("heart_rate", 72, "bpm")]), _composed(factory, pid))
    assert [e.event_type for e in state.events] == [EventType.SPO2_NEWS2_3_POINTS]


# ── Task 2: el cuerpo del gemelo dibuja al paciente ──

def _shared_factory():
    engine = make_engine()          # la base redirigida por conftest: la misma que usa la app
    init_db(engine)
    return make_session_factory(engine)


def _patient_with(*saves) -> str:
    with _shared_factory()() as session:
        patient_id = create_patient(session, display_name="Gemelo (prueba de cuerpo)")
    for signals in saves:
        organism = DigitalTwinOrganism()
        organism.update_from_sensors(signals)
        with _shared_factory()() as session:
            save_state(session, from_digital_twin_organism(organism, patient_id, provenance=Provenance.SIMULACION,
                                                           source_detail="laboratorio (prueba)"))
    return patient_id


def _twin_text(patient_id: str) -> str:
    at = AppTest.from_file(MAIN, default_timeout=240)
    at.session_state["biocore_start_page"] = "gemelo"
    at.session_state[PATIENT_KEY] = patient_id
    at.run()
    assert at.exception == [], at.exception
    return " ".join(m.value for m in at.main.markdown)


def test_gemelo_muestra_el_eeg_guardado():
    text = _twin_text(_patient_with(EEG))
    assert "Banda dom.: BETA" in text
    # Revisión final de la T1: lo guardado por un laboratorio dice su edad; lo que mueves ahora, no.
    assert "Procedencia: Simulación · hace" in text


def test_gemelo_muestra_el_emg_guardado():
    text = _twin_text(_patient_with(EMG))
    assert "Activación EMG: 42 %" in text and "no % de contracción máxima" in text
    assert "Frecuencia mediana: 85 Hz" in text


def test_musculo_sin_emg_dice_sin_dato():
    text = _twin_text(_patient_with(EEG))
    card = text.split('biocore-organ-title">💪 Músculo</div>', 1)
    assert len(card) == 2, "la tarjeta muscular existe"
    assert "Sin dato" in card[1].split("</div></div>", 1)[0] or "sin dato" in card[1].split("</div></div>", 1)[0].lower()
    assert "Activación EMG" not in text


def test_modo_caso_sin_linea_de_procedencia():
    def script():
        from datetime import datetime, timezone
        from app.supermodules.twin_shell.ups_body_visual import render_ups_body
        from domain.physiology.state import DomainState, PhysiologicalDescriptor, Provenance, UnifiedPhysiologicalState
        hr = PhysiologicalDescriptor("heart_rate", 80.0, "bpm", Provenance.SIMULACION, 0.6, None)
        render_ups_body(UnifiedPhysiologicalState(
            patient_id="caso", timestamp=datetime.now(timezone.utc),
            cardiovascular=DomainState("cardiovascular", {"heart_rate": hr}),
            respiratory=DomainState("respiratory", {}), events=[]))

    at = AppTest.from_function(script)
    at.run()
    assert at.exception == []
    text = " ".join(m.value for m in at.markdown)
    assert "FC: 80 lpm" in text and "biocore-organ-source" not in text.replace(".biocore-organ-source", "")



# ── Revisión final de la T1 ──

def test_todo_valor_del_paciente_lleva_origen(factory, pid):
    """Un valor del ÚLTIMO snapshot del paciente no es arrastre, pero tampoco es «ahora»: también lleva su origen,
    para que el cuerpo no lo confunda con lo que el slider mueve en este momento."""
    sid = None
    with factory() as s:
        sid = save_state(s, _state(pid, neuro=[_d("alpha_power", 2.0), _d("beta_power", 4.0)]))
    state, origins = overlay_current_on_composed(_state(pid, cv=[_d("heart_rate", 72, "bpm")]),
                                                 _composed(factory, pid))
    assert origins[("neurological", "alpha_power")].snapshot_id == sid
    assert ("cardiovascular", "heart_rate") not in origins


def test_insignias_del_eeg_dicen_su_procedencia():
    at = AppTest.from_file(MAIN, default_timeout=240)
    at.session_state["biocore_start_page"] = "gemelo"
    at.session_state[PATIENT_KEY] = _patient_with(EEG)
    at.run()
    assert at.exception == []
    badges = [c.value for c in at.main.caption if "DAR =" in c.value or "TBR =" in c.value]
    assert badges, "precondición: el EEG guardado trae DAR/TBR"
    assert all("Procedencia: Simulación · hace" in b for b in badges), badges
