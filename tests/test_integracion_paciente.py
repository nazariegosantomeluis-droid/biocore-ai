"""I2 + I3 (integración 2026-11-17): un mismo paciente entre laboratorios.

- El banner del paciente activo aparece en TODAS las páginas de Explorar, con el mismo id, y dice «sin dato» o «sin
  paciente activo» en vez de rellenar.
- Mirar una página no crea al paciente (salvo el gemelo, que siempre lo tiene).
- «Abrir en…» desde el gemelo: Calculadoras llega con FC, FR y SpO₂ del paciente y sus puntos NEWS2 coinciden con los
  del gemelo (golden test con sepsis).
Todo corre con la base de pruebas redirigida (`tests/conftest.py`); la de desarrollo no se toca.
"""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from app.engines.digital_twin_organism import DigitalTwinOrganism
from app.utils.patient_banner import (
    CALC_LOAD_PATIENT_KEY, INPUT_SOURCE_KEY, NO_PATIENT_TEXT, SHORT_ID_LEN, read_active_vitals,
)
from app.utils.physiological_state import persist_current_state
from domain.physiology.state import (
    create_patient, get_latest_state, init_db, make_engine, make_session_factory,
)
from src.clinical import sepsis_trajectory

MAIN = str(Path("app/main.py").resolve())
PATIENT_KEY = "twin_shell_ups_patient_id"
EXPLORAR = ("gemelo", "ecg", "multisensor", "respiratorio", "eeg", "emg", "hrv", "biomarcadores", "calculadoras",
            "pacientes", "modelo-3d")


@pytest.fixture(autouse=True)
def _no_env_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


def _session_factory():
    engine = make_engine()          # lee `DEFAULT_DB_PATH`, redirigido por conftest: la misma base que usa la app
    init_db(engine)
    return make_session_factory(engine)


def _patient_with(signals: dict) -> str:
    """Un paciente en el UPS con un snapshot persistido (simulación) de las señales dadas."""
    organism = DigitalTwinOrganism()
    organism.update_from_sensors(signals)
    with _session_factory()() as session:
        patient_id = create_patient(session, display_name="Paciente de prueba (integración)")
        persist_current_state(session, organism, patient_id, source_detail="twin_visual:prueba_integracion")
    return patient_id


def _open(url, **state):
    at = AppTest.from_file(MAIN, default_timeout=240)
    at.session_state["biocore_start_page"] = url
    for key, value in state.items():
        at.session_state[key] = value
    at.run()
    assert at.exception == [], (url, at.exception)
    return at


def _banner_texts(at):
    return [m.value for m in at.markdown if "Paciente activo" in m.value or NO_PATIENT_TEXT in m.value]


def _metric(at, label):
    """`data-value` de la tarjeta de métrica con esa etiqueta (la tarjeta lo lleva para las pruebas)."""
    for m in at.markdown:
        if f'data-label="{label}"' in m.value:
            value = m.value.split('data-value="', 1)[1].split('"', 1)[0]
            return value or None
    raise AssertionError(f"no hay tarjeta «{label}»")


def test_banner_en_todas_las_paginas_de_explorar_con_el_mismo_paciente():
    patient_id = _patient_with({"ecg": {"heart_rate": 88.0}, "respiratory": {"respiratory_rate": 18.0, "spo2": 97.0}})
    short = patient_id[:SHORT_ID_LEN]
    for url in EXPLORAR:
        at = _open(url, **{PATIENT_KEY: patient_id})
        banners = _banner_texts(at)
        assert len(banners) == 1, (url, banners)
        assert f"<code>{short}</code>" in banners[0], (url, banners[0])
        assert "FC <b>88</b> lpm" in banners[0] and "FR <b>18</b>" in banners[0] and "SpO₂ <b>97</b>" in banners[0], url
        assert "bpm" not in banners[0], f"{url}: ningún inglés visible"
        assert "[Simulación]" in banners[0], url
        assert at.session_state[PATIENT_KEY] == patient_id, f"{url} cambió de paciente"


def test_banner_dice_sin_dato_de_lo_que_el_ups_no_tiene():
    patient_id = _patient_with({"ecg": {"heart_rate": 72.0}})          # solo FC: ni FR ni SpO₂
    banner = _banner_texts(_open("hrv", **{PATIENT_KEY: patient_id}))[0]
    assert "FC <b>72</b>" in banner
    assert "FR: ○ Sin dato" in banner and "SpO₂: ○ Sin dato" in banner
    assert "<b>0</b>" not in banner, "nunca un valor por defecto"


def test_sin_paciente_el_banner_lo_dice_y_no_lo_crea():
    for url in ("ecg", "calculadoras", "multisensor"):
        at = _open(url)
        banners = _banner_texts(at)
        assert len(banners) == 1 and NO_PATIENT_TEXT in banners[0], (url, banners)
        assert PATIENT_KEY not in at.session_state, f"{url} creó un paciente solo por mostrarse"


def test_el_gemelo_siempre_muestra_su_paciente():
    at = _open("gemelo")
    banner = _banner_texts(at)[0]
    assert NO_PATIENT_TEXT not in banner
    assert f"<code>{at.session_state[PATIENT_KEY][:SHORT_ID_LEN]}</code>" in banner


def test_la_clave_de_la_fuente_activa_es_la_del_gemelo():
    from app.supermodules.twin_shell import pages
    assert INPUT_SOURCE_KEY == pages.INPUT_SOURCE_KEY


def test_el_banner_declara_la_fuente_activa_de_un_escenario():
    patient_id = _patient_with({"ecg": {"heart_rate": 80.0}})
    banner = _banner_texts(_open("ecg", **{PATIENT_KEY: patient_id, INPUT_SOURCE_KEY: "sepsis, horizonte now"}))[0]
    assert "Fuente activa: sepsis, horizonte now" in banner


@pytest.mark.parametrize("horizon", list(sepsis_trajectory.HORIZON_PHASES))
def test_golden_sepsis_los_puntos_de_calculadoras_coinciden_con_el_gemelo(horizon):
    at = _open("gemelo")
    at.selectbox(key="twin_shell_sepsis_horizon").set_value(horizon).run()
    next(b for b in at.button if b.key == "twin_shell_sepsis_apply").click().run()
    assert at.exception == []
    twin_points = at.session_state["twin_shell_organism"].global_state["news2_partial"].components
    assert set(twin_points) == {"Pulso", "Frecuencia respiratoria", "SpO₂ (escala 1)"}, twin_points
    patient_id = at.session_state[PATIENT_KEY]

    next(b for b in at.button if b.key == "twin_shell_open_in_calculators").click().run()
    assert at.exception == [], at.exception
    assert at.session_state[PATIENT_KEY] == patient_id, "Calculadoras cambió de paciente"
    assert CALC_LOAD_PATIENT_KEY not in at.session_state, "Calculadoras debe consumir la bandera al abrir"

    # los puntos de pulso (y los otros dos) de Calculadoras = los del gemelo
    for label, component in (("Pulso NEWS2", "Pulso"), ("Frecuencia respiratoria NEWS2", "Frecuencia respiratoria"),
                             ("SpO₂ (escala 1) NEWS2", "SpO₂ (escala 1)")):
        value = _metric(at, label)
        assert value is not None and value.split()[0] == str(twin_points[component]), (horizon, label, value, twin_points)

    # los campos llegan cargados con FC/FR/SpO₂ del paciente
    vitals = at.session_state["twin_shell_organism"].organs
    assert at.number_input(key="calc_news_pulse").value == round(vitals["heart"].metrics.signals["heart_rate"])
    assert at.number_input(key="calc_news_rr").value == round(vitals["lungs"].metrics.signals["respiratory_rate"])
    assert at.number_input(key="calc_news_spo2").value == round(vitals["lungs"].metrics.signals["spo2"])

    # «Abrir en…» guardó el momento en el UPS, declarando el escenario que lo originó
    with _session_factory()() as session:
        state = get_latest_state(session, patient_id)
    detail = state.cardiovascular.get("heart_rate").source_detail
    assert detail.startswith("twin_visual:abrir_en_calculadoras") and "sepsis" in detail, detail

    # y el banner de Calculadoras muestra al mismo paciente
    assert f"<code>{patient_id[:SHORT_ID_LEN]}</code>" in _banner_texts(at)[0]


@pytest.mark.parametrize("button,url", [("twin_shell_open_in_ecg", "ecg"), ("twin_shell_open_in_hrv", "hrv")])
def test_ver_ecg_y_ver_hrv_llevan_al_mismo_paciente(button, url):
    at = _open("gemelo")
    patient_id = at.session_state[PATIENT_KEY]
    next(b for b in at.button if b.key == button).click().run()
    assert at.exception == [], at.exception
    assert at.session_state[PATIENT_KEY] == patient_id
    banner = _banner_texts(at)[0]
    assert f"<code>{patient_id[:SHORT_ID_LEN]}</code>" in banner and "FC <b>72</b>" in banner, banner


def test_calculadoras_sin_paciente_dice_sin_paciente_y_no_inventa_puntos():
    at = _open("calculadoras")
    assert all(m.value.count('data-label="Pulso NEWS2"') == 0 for m in at.markdown)
    assert any("Sin paciente activo" in c.value for c in at.caption)


def test_calculadoras_sin_dato_de_fr_y_spo2():
    patient_id = _patient_with({"ecg": {"heart_rate": 120.0}})
    at = _open("calculadoras", **{PATIENT_KEY: patient_id})
    assert _metric(at, "Pulso NEWS2").startswith("2 ")                     # 111-130 → 2 puntos
    assert _metric(at, "Frecuencia respiratoria NEWS2") is None
    assert _metric(at, "SpO₂ (escala 1) NEWS2") is None
    vitals = None
    with _session_factory()() as session:
        vitals = get_latest_state(session, patient_id)
    assert vitals.respiratory.get("respiratory_rate") is None


def test_read_active_vitals_sin_paciente(monkeypatch):
    import streamlit as st
    monkeypatch.setattr(st, "session_state", {})
    vitals = read_active_vitals()
    assert vitals.patient_id is None and vitals.short_id is None
    assert vitals.values == {"hr": None, "rr": None, "spo2": None}


# ── Un solo criterio visible: toda FC/FR/SpO₂ con sus puntos NEWS2 (misma tabla que el gemelo) ──

def test_news2_reading_note_usa_la_tabla_del_gemelo():
    from clinical.calculators import news2_partial, news2_reading_note
    assert news2_reading_note(pulse=95) == "NEWS2 (RCP 2017): Pulso 1 punto"            # 91-110 → 1
    assert news2_reading_note(pulse=111) == "NEWS2 (RCP 2017): Pulso 2 puntos"          # 111-130 → 2
    assert news2_reading_note(pulse=131) == "NEWS2 (RCP 2017): Pulso 3 puntos"          # ≥ 131 → 3
    assert news2_reading_note(pulse=75) == "NEWS2 (RCP 2017): Pulso 0 puntos"
    assert news2_reading_note(pulse=95, respiratory_rate=22, spo2=94) == (
        "NEWS2 (RCP 2017): Pulso 1 punto · Frecuencia respiratoria 2 puntos · SpO₂ (escala 1) 1 punto")
    assert news2_reading_note() is None and news2_reading_note(pulse=float("nan")) is None
    for hr in range(30, 200):                       # nunca difiere del NEWS2 parcial que usa el gemelo
        points = news2_partial(pulse=float(hr)).components["Pulso"]
        assert f"Pulso {points} punto" in news2_reading_note(pulse=float(hr))


def test_el_banner_muestra_los_puntos_news2_de_cada_valor():
    patient_id = _patient_with({"ecg": {"heart_rate": 95.0}, "respiratory": {"respiratory_rate": 22.0, "spo2": 94.0}})
    banner = _banner_texts(_open("emg", **{PATIENT_KEY: patient_id}))[0]
    assert "FC <b>95</b> lpm" in banner and "NEWS2 1 punto" in banner
    assert "NEWS2 2 puntos" in banner                       # FR 22
    assert banner.count("NEWS2") == 3, banner               # pulso, FR y SpO₂ (94 → 1 punto)


def test_sin_dato_no_lleva_puntos_news2():
    patient_id = _patient_with({"ecg": {"heart_rate": 95.0}})
    banner = _banner_texts(_open("emg", **{PATIENT_KEY: patient_id}))[0]
    assert banner.count("NEWS2") == 1, banner               # solo el pulso; FR y SpO₂ dicen «Sin dato»


@pytest.mark.parametrize("url", ["calculadoras", "ecg", "multisensor"])
def test_las_pantallas_que_muestran_una_lectura_traen_sus_puntos_news2(url):
    at = _open(url)
    notes = [c.value for c in at.caption if c.value.startswith("NEWS2 (RCP 2017): ")]
    assert notes, f"{url}: la lectura no trae sus puntos NEWS2"
    assert all("Pulso" in n for n in notes)
