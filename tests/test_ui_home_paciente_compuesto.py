"""T0 · El Inicio lee al paciente compuesto (2026-11-18).

Antes, el Inicio leía el último snapshot: tras guardar un EEG, la tarjeta del corazón decía que el UPS no tenía valores.
Y un valor arrastrado se sellaba «Medido · arrastre temporal» aunque su origen fuera una simulación: con el paciente
compuesto eso habría puesto «Medido» en cada FC simulada. Ahora el sello es el de la procedencia de ORIGEN, con su edad.
"""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from app.engines.digital_twin_organism import DigitalTwinOrganism
from app.supermodules import ui_catalog as C
from app.utils import i18n
from domain.physiology.state import (
    Provenance, create_patient, from_digital_twin_organism, init_db, make_engine, make_session_factory, save_state,
)

MAIN = str(Path("app/main.py").resolve())
PATIENT_KEY = "twin_shell_ups_patient_id"
MEDIDO = "biocore-sello-medido-monitor.svg"
SIMULADO = "biocore-sello-simulado-monitor.svg"
EEG = {"eeg": {"delta_power": 1.0, "theta_power": 1.0, "alpha_power": 2.0, "beta_power": 4.0, "gamma_power": 0.5}}
TWIN = {"ecg": {"heart_rate": 100.0}, "respiratory": {"respiratory_rate": 24.0, "spo2": 92.0}}


@pytest.fixture(autouse=True)
def _no_env_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


def _factory():
    engine = make_engine()          # la base redirigida por conftest
    init_db(engine)
    return make_session_factory(engine)


def _patient(*saves) -> str:
    with _factory()() as session:
        patient_id = create_patient(session, display_name="Inicio compuesto (prueba)")
    for signals in saves:
        organism = DigitalTwinOrganism()
        organism.update_from_sensors(signals)
        with _factory()() as session:
            save_state(session, from_digital_twin_organism(organism, patient_id, provenance=Provenance.SIMULACION,
                                                           source_detail="prueba_inicio"))
    return patient_id


def _home(patient_id: str, lang: str | None = None) -> str:
    at = AppTest.from_file(MAIN, default_timeout=240)
    at.session_state["biocore_start_page"] = "inicio"
    at.session_state[PATIENT_KEY] = patient_id
    at.session_state[C.SELECTED_ORGAN_KEY] = "corazon"
    if lang is not None:
        at.session_state[i18n.LANG_KEY] = lang
    at.run()
    assert at.exception == [], at.exception
    return " ".join(m.value for m in at.main.markdown)


def test_inicio_no_sella_medido_un_simulado_arrastrado():
    text = _home(_patient(TWIN, EEG))
    assert "Frecuencia cardiaca" in text
    assert SIMULADO in text and "hace" in text
    assert MEDIDO not in text, "una FC simulada arrastrada no es «Medido»"


def test_inicio_solo_eeg_sin_valores_del_corazon():
    text = _home(_patient(EEG))
    assert "El UPS del paciente activo no tiene valores de este sistema." in text


def test_inicio_en_ingles_traduce_la_edad_del_arrastre():
    text = _home(_patient(TWIN, EEG), "en")
    assert "ago" in text and "hace" not in text


def test_barra_fija_un_sello_por_signo_con_procedencias_mezcladas():
    """Revisión final de la T0: FR y SpO₂ simuladas y luego una FC de sensor real. La barra fija ponía UN sello (el
    de la primera con valor, «Medido») junto a los tres: la FR simulada quedaba bajo «Medido»."""
    from datetime import datetime, timezone
    from domain.physiology.state import DomainState, PhysiologicalDescriptor, UnifiedPhysiologicalState

    patient_id = _patient({"respiratory": {"respiratory_rate": 24.0, "spo2": 92.0}})
    hr = PhysiologicalDescriptor("heart_rate", 72.0, "bpm", Provenance.SENSOR_REAL, 0.85, "placa en vivo (prueba)")
    with _factory()() as session:
        save_state(session, UnifiedPhysiologicalState(
            patient_id=patient_id, timestamp=datetime.now(timezone.utc),
            cardiovascular=DomainState("cardiovascular", {"heart_rate": hr}),
            respiratory=DomainState("respiratory", {}), events=[]))
    at = AppTest.from_file(MAIN, default_timeout=240)
    at.session_state["biocore_start_page"] = "inicio"
    at.session_state[PATIENT_KEY] = patient_id
    at.run()
    assert at.exception == []
    sticky = next(m.value for m in at.main.markdown if m.value.startswith("<div class='bc-mini'>"))
    assert sticky.count("biocore-sello-") == 3, "un sello por signo"
    assert MEDIDO in sticky and SIMULADO in sticky
