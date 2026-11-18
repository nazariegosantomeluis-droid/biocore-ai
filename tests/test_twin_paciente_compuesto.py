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


# ── T1.1 (2026-11-18): sliders desde el paciente; lo que no se movió sigue siendo del paciente ──

def _save_hr(patient_id: str, hr: float, prov=Provenance.SENSOR_REAL) -> None:
    with _shared_factory()() as session:
        save_state(session, UnifiedPhysiologicalState(
            patient_id=patient_id, timestamp=datetime.now(timezone.utc),
            cardiovascular=DomainState("cardiovascular", {
                "heart_rate": PhysiologicalDescriptor("heart_rate", float(hr), "bpm", prov, 0.85, "placa (prueba)")}),
            respiratory=DomainState("respiratory", {}), events=[]))


def _twin_app(patient_id: str) -> AppTest:
    at = AppTest.from_file(MAIN, default_timeout=240)
    at.session_state["biocore_start_page"] = "gemelo"
    at.session_state[PATIENT_KEY] = patient_id
    at.run()
    assert at.exception == [], at.exception
    return at


def _md(at: AppTest) -> str:
    return " ".join(m.value for m in at.main.markdown)


def test_slider_arranca_en_la_fc_del_paciente():
    patient_id = _patient_with({"ecg": {"heart_rate": 88.0}})
    at = _twin_app(patient_id)
    assert at.slider(key="twin_shell_hr").value == 88
    assert any("empieza en la FC del paciente activo" in c.value for c in at.main.caption)


def test_slider_sigue_al_paciente_mientras_no_se_mueve():
    patient_id = _patient_with({"ecg": {"heart_rate": 88.0}})
    at = _twin_app(patient_id)
    _save_hr(patient_id, 95)                     # el laboratorio de ECG guarda una FC medida
    at.run()
    assert at.slider(key="twin_shell_hr").value == 95
    text = _md(at)
    assert "FC: 95 lpm" in text and "Procedencia: Sensor real" in text, "lo no movido viene del paciente"


def test_slider_movido_gana():
    patient_id = _patient_with({"ecg": {"heart_rate": 88.0}})
    at = _twin_app(patient_id)
    at.slider(key="twin_shell_hr").set_value(120).run()
    _save_hr(patient_id, 95)
    at.run()
    assert at.slider(key="twin_shell_hr").value == 120
    text = _md(at)
    assert "FC: 120 lpm" in text
    heart = text.split("🫀 Corazón", 1)[1].split("</div></div>", 1)[0]
    assert "Procedencia: Simulación" in heart and "hace" not in heart


def test_escenario_activo_no_difiere():
    patient_id = _patient_with({"ecg": {"heart_rate": 88.0}})
    at = AppTest.from_file(MAIN, default_timeout=240)
    at.session_state["biocore_start_page"] = "gemelo"
    at.session_state[PATIENT_KEY] = patient_id
    at.session_state["twin_shell_input_source"] = "escenario de prueba"
    at.run()
    assert at.exception == []
    assert at.session_state["twin_shell_deferred_inputs"] == frozenset()


def test_pulmones_dicen_que_procedencia_es_de_cual(pid):
    from app.supermodules.twin_shell.ups_body_visual import _render_lungs_card
    state = _state(pid, resp=[_d("respiratory_rate", 18, "breaths/min"),
                              _d("spo2", 94, "%", prov=Provenance.SENSOR_REAL)])
    html = _render_lungs_card(state, origins={})
    assert "Procedencia: FR: Simulación; SpO₂: Sensor real" in html


def test_cerebro_sin_bandas_sin_linea_de_procedencia(pid):
    from app.supermodules.twin_shell.ups_body_visual import _render_brain_card
    html = _render_brain_card(_state(pid, neuro=[_d("chi_aperiodic", 1.4)]), origins={})
    assert "banda dominante" in html and "biocore-organ-source" not in html


def test_pie_dice_gris_sin_dato():
    text = " ".join(c.value for c in _twin_app(_patient_with(EEG)).main.caption)
    assert "una tarjeta sin dato se pinta en gris" in text


# ── Revisión final de la T1.1 ──

def test_dominio_diferido_entero_no_duplica_alertas(factory, pid):
    organism = DigitalTwinOrganism()
    organism.update_from_sensors({"respiratory": {"respiratory_rate": 18.0, "spo2": 90.0}})
    _save(factory, from_digital_twin_organism(organism, pid, provenance=Provenance.SIMULACION, source_detail="lab"))
    from app.utils.physiological_state import get_current_physiological_state
    current = get_current_physiological_state(organism, pid)
    state, _ = overlay_current_on_composed(current, _composed(factory, pid),
                                           frozenset({("respiratory", "respiratory_rate"), ("respiratory", "spo2")}))
    assert [e.event_type for e in state.events].count(EventType.SPO2_NEWS2_3_POINTS) == 1


def test_valor_del_paciente_fuera_de_rango_no_lo_tapa_el_slider():
    patient_id = _patient_with()
    with _shared_factory()() as session:
        save_state(session, UnifiedPhysiologicalState(
            patient_id=patient_id, timestamp=datetime.now(timezone.utc),
            cardiovascular=DomainState("cardiovascular", {}),
            respiratory=DomainState("respiratory", {"spo2": PhysiologicalDescriptor(
                "spo2", 69.0, "%", Provenance.SENSOR_REAL, 0.85, "oxímetro (prueba)")}), events=[]))
    at = _twin_app(patient_id)
    assert at.slider(key="twin_shell_spo2").value == 98          # el control no llega a 69
    text = _md(at)
    assert "SpO₂: 69%" in text and "SpO₂: Sensor real" in text
