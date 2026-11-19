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


# ── ECG Monitoreo con la FC del paciente activo (integración, 2026-11-17) ───────────────────────────────────────────
ECG_SOURCE_KEY = "ecg_monitor_source"
ECG_PATIENT_SOURCE = "Paciente activo (simulación a su FC)"


def _ecg_hr_lines(at):
    """Las FC que muestra el Monitoreo: `**Frecuencia cardíaca** — N lpm` (`render_metric_explained`)."""
    return [m.value for m in at.markdown if m.value.startswith("**Frecuencia cardíaca** — ")]


def _ecg_hr_metric(at):
    lines = _ecg_hr_lines(at)
    assert len(lines) == 1, lines
    return float(lines[0].split("— ", 1)[1].split()[0].replace(",", "."))


def test_ecg_abre_en_el_paciente_activo_con_la_misma_fc_del_banner():
    patient_id = _patient_with({"ecg": {"heart_rate": 100.0}, "respiratory": {"respiratory_rate": 24.0, "spo2": 93.0}})
    at = _open("ecg", **{PATIENT_KEY: patient_id})
    assert at.session_state[ECG_SOURCE_KEY] == ECG_PATIENT_SOURCE
    assert "FC <b>100</b>" in _banner_texts(at)[0]
    assert abs(_ecg_hr_metric(at) - 100.0) < 1.0, "el trazo debe latir a la FC del UPS, no a la de la demo (72)"
    assert any("NEWS2 (RCP 2017): Pulso 1 punto" in c.value for c in at.caption), "la FC lleva sus puntos NEWS2"
    assert any("**Fuente:** simulación a la FC del paciente activo (UPS)" in m.value for m in at.markdown), \
        "el trazo debe declararse simulación"


def test_ecg_del_mismo_paciente_es_siempre_el_mismo_trazo():
    patient_id = _patient_with({"ecg": {"heart_rate": 88.0}})
    first = _ecg_hr_metric(_open("ecg", **{PATIENT_KEY: patient_id}))
    second = _ecg_hr_metric(_open("ecg", **{PATIENT_KEY: patient_id}))
    assert first == second and abs(first - 88.0) < 1.0


def test_ecg_sin_paciente_abre_en_la_demo_como_siempre():
    at = _open("ecg")
    assert at.session_state[ECG_SOURCE_KEY] == "Demo (sintético)"


def test_ecg_paciente_sin_fc_en_el_ups_dice_sin_dato_y_no_cae_en_la_demo():
    patient_id = _patient_with({"respiratory": {"respiratory_rate": 18.0, "spo2": 97.0}})
    at = _open("ecg", **{PATIENT_KEY: patient_id})
    at.radio(key=ECG_SOURCE_KEY).set_value(ECG_PATIENT_SOURCE).run()   # por clave: el menú tiene otros radios
    assert at.exception == []
    text = " ".join(m.value for m in at.markdown)
    assert "Sin dato" in text and "FC" in text
    assert _ecg_hr_lines(at) == [], "no debe dibujar una FC inventada"


def test_ecg_con_arritmia_aplicada_dice_ritmo_no_modelado():
    patient_id = _patient_with({"ecg": {"heart_rate": 130.0}})
    at = _open("ecg", **{PATIENT_KEY: patient_id, INPUT_SOURCE_KEY: "arritmia Fibrilación auricular (semilla 0)"})
    at.radio(key=ECG_SOURCE_KEY).set_value(ECG_PATIENT_SOURCE).run()   # por clave: el menú tiene otros radios
    assert at.exception == []
    assert "ritmo no modelado" in " ".join(m.value for m in at.markdown)
    assert _ecg_hr_lines(at) == []


def test_ecg_con_fc_fuera_del_rango_validado_dice_sin_dato():
    patient_id = _patient_with({"ecg": {"heart_rate": 230.0}})
    at = _open("ecg", **{PATIENT_KEY: patient_id})
    at.radio(key=ECG_SOURCE_KEY).set_value(ECG_PATIENT_SOURCE).run()   # por clave: el menú tiene otros radios
    assert at.exception == []
    assert "rango en que el generador está validado" in " ".join(m.value for m in at.markdown)


def test_ecg_del_paciente_no_se_guarda_de_vuelta_al_gemelo():
    patient_id = _patient_with({"ecg": {"heart_rate": 100.0}})
    at = _open("ecg", **{PATIENT_KEY: patient_id})
    assert not any("Guardar" in b.label and "gemelo" in b.label.lower() for b in at.button), \
        "esa señal nace del UPS: guardarla sería escribir el mismo valor otra vez"


# ── Respiratorio y HRV empiezan en el paciente activo (integración, 2026-11-17) ─────────────────────────────────────
RESP_RR = "Frecuencia Respiratoria (resp/min)"
RESP_SPO2 = "SpO2 Basal (%)"


def _sidebar_number(at, label):
    return next(n for n in at.sidebar.number_input if n.label == label).value


def _sidebar_slider(at, label):
    return next(s for s in at.sidebar.slider if s.label == label).value


def _sidebar_captions(at):
    return " ".join(c.value for c in at.sidebar.caption)


def test_respiratorio_empieza_en_la_fr_y_spo2_del_paciente():
    patient_id = _patient_with({"ecg": {"heart_rate": 100.0}, "respiratory": {"respiratory_rate": 24.0, "spo2": 93.0}})
    at = _open("respiratorio", **{PATIENT_KEY: patient_id})
    assert _sidebar_number(at, RESP_RR) == 24 and _sidebar_number(at, RESP_SPO2) == 93
    notes = _sidebar_captions(at)
    assert f"`{patient_id[:SHORT_ID_LEN]}`" in notes and "ya es tu simulación" in notes


def test_respiratorio_sin_paciente_se_ve_como_siempre():
    at = _open("respiratorio")
    assert _sidebar_number(at, RESP_RR) == 15 and _sidebar_number(at, RESP_SPO2) == 98
    assert "paciente activo" not in _sidebar_captions(at)


def test_respiratorio_spo2_fuera_del_rango_del_control_no_se_recorta():
    # T4.1 (2026-11-18): el control baja hasta 70 % (los escenarios de hipoxia, apnea y EPOC ya caben); 65 % sigue fuera.
    patient_id = _patient_with({"respiratory": {"respiratory_rate": 22.0, "spo2": 65.0}})
    at = _open("respiratorio", **{PATIENT_KEY: patient_id})
    assert _sidebar_number(at, RESP_SPO2) == 98, "65 % no cabe en 70–100: no se recorta a 70 (sería otro paciente)"
    assert "fuera del rango de este control" in _sidebar_captions(at)
    assert _sidebar_number(at, RESP_RR) == 22


def test_respiratorio_empieza_en_una_spo2_de_hipoxia_con_el_piso_debajo():
    patient_id = _patient_with({"respiratory": {"respiratory_rate": 28.0, "spo2": 80.0}})
    at = _open("respiratorio", **{PATIENT_KEY: patient_id})
    assert _sidebar_number(at, RESP_SPO2) == 80 and _sidebar_number(at, "SpO2 Mínimo (%)") == 75
    assert not at.error, [e.value for e in at.error]          # el piso por debajo de la basal: parámetros posibles


def test_hrv_empieza_en_la_fc_y_fr_del_paciente_y_no_usa_su_hrv():
    patient_id = _patient_with({"ecg": {"heart_rate": 100.0, "hrv": 20.0},
                                "respiratory": {"respiratory_rate": 24.0, "spo2": 93.0}})
    at = _open("hrv", **{PATIENT_KEY: patient_id})
    assert _sidebar_slider(at, "FC base (lpm)") == 100
    assert _sidebar_slider(at, "Frecuencia respiratoria (rpm)") == 24
    assert _sidebar_slider(at, "Amplitud RSA (lpm)") == 5, "la amplitud no se ajusta al hrv del UPS"
    assert "sin decir qué índice es" in _sidebar_captions(at)


def test_hrv_sin_dato_de_fr_lo_dice():
    patient_id = _patient_with({"ecg": {"heart_rate": 88.0}})
    at = _open("hrv", **{PATIENT_KEY: patient_id})
    assert _sidebar_slider(at, "FC base (lpm)") == 88
    assert _sidebar_slider(at, "Frecuencia respiratoria (rpm)") == 15
    assert "no tiene FR en el UPS" in _sidebar_captions(at)


# ── T0 · paciente compuesto (2026-11-18): guardar en un laboratorio ya no borra los signos del paciente ──

def _append_eeg(patient_id: str) -> None:
    """Un guardado del EEG Lab sobre el mismo paciente: su snapshot solo trae el dominio neurológico."""
    from domain.physiology.state import Provenance, from_digital_twin_organism, save_state
    organism = DigitalTwinOrganism()
    organism.update_from_sensors({"eeg": {"delta_power": 1.0, "theta_power": 1.0, "alpha_power": 2.0,
                                          "beta_power": 4.0, "gamma_power": 0.5}})
    with _session_factory()() as session:
        save_state(session, from_digital_twin_organism(organism, patient_id, provenance=Provenance.SIMULACION,
                                                       source_detail="eeg_neuro_lab"))


def test_banner_conserva_signos_tras_guardar_eeg():
    patient_id = _patient_with({"ecg": {"heart_rate": 100.0}, "respiratory": {"respiratory_rate": 24.0, "spo2": 92.0}})
    _append_eeg(patient_id)
    banner = _banner_texts(_open("calculadoras", **{PATIENT_KEY: patient_id}))[0]
    assert "FC <b>100</b>" in banner and "FR <b>24</b>" in banner and "SpO₂ <b>92</b>" in banner, banner
    assert "Simulación · hace" in banner, "un valor arrastrado dice su procedencia de origen y su edad"
    assert "Sin dato" not in banner


def test_read_active_vitals_origen():
    patient_id = _patient_with({"ecg": {"heart_rate": 100.0}, "respiratory": {"respiratory_rate": 24.0, "spo2": 92.0}})
    _append_eeg(patient_id)

    def script():
        import streamlit as st
        from app.utils.patient_banner import read_active_vitals
        vitals = read_active_vitals()
        st.session_state["out"] = (vitals.values["hr"].value, vitals.origins["hr"].provenance.value)

    at = AppTest.from_function(script)
    at.session_state[PATIENT_KEY] = patient_id
    at.run()
    assert at.exception == []
    assert at.session_state["out"] == (100.0, "simulacion")


def test_age_text():
    from app.utils.patient_banner import age_text
    assert age_text(5) == "hace 5 s"
    assert age_text(125) == "hace 2 min"
    assert age_text(7300) == "hace 2 h"


def test_pasaporte_y_pie_del_banner_con_arrastre():
    """Revisión final de la T0: el pasaporte de un valor arrastrado lleva la procedencia de ORIGEN (simulado, no
    «estimado») y dice que es un arrastre; el pie del banner ya no dice «Último estado guardado»."""
    from app.utils.patient_banner import passport_args
    patient_id = _patient_with({"ecg": {"heart_rate": 100.0}, "respiratory": {"respiratory_rate": 24.0, "spo2": 92.0}})
    _append_eeg(patient_id)

    def script():
        import streamlit as st
        from app.utils.patient_banner import passport_args, read_active_vitals
        st.session_state["out"] = passport_args(read_active_vitals(), "hr")

    at = AppTest.from_function(script)
    at.session_state[PATIENT_KEY] = patient_id
    at.run()
    valor, procedencia = at.session_state["out"]
    assert procedencia.value == "simulacion"
    assert valor.startswith("100 lpm") and "arrastre" in valor and "hace" in valor

    at = _open("calculadoras", **{PATIENT_KEY: patient_id})
    captions = " ".join(c.value for c in at.main.caption)
    assert "Último estado guardado" not in captions
    assert "Últimos valores guardados en el UPS de esta sesión" in captions


# ── T1.1 (2026-11-18): horizonte de trayectoria y edad en los paneles que mezclan momentos ──

def _patient_then_eeg() -> str:
    patient_id = _patient_with({"ecg": {"heart_rate": 100.0}, "respiratory": {"respiratory_rate": 24.0, "spo2": 92.0}})
    _append_eeg(patient_id)
    return patient_id


def test_procedencia_de_una_trayectoria_dice_su_horizonte():
    from datetime import datetime, timezone
    from app.utils.patient_banner import vital_provenance_text
    from domain.physiology.state import CarryOrigin, PhysiologicalDescriptor, Provenance
    d = PhysiologicalDescriptor("heart_rate", 100.0, "bpm", Provenance.ARRASTRE_TEMPORAL, 0.6, None)
    origin = CarryOrigin("s1", datetime.now(timezone.utc), Provenance.SIMULACION, 2.0, "6h")
    assert vital_provenance_text(d, origin) == "Simulación · horizonte 6h"


def test_title_del_banner_usa_la_misma_edad_que_la_etiqueta():
    banner = _banner_texts(_open("calculadoras", **{PATIENT_KEY: _patient_then_eeg()}))[0]
    assert "(edad " not in banner, "el title= ya no trae la edad respecto al último snapshot"
    assert "title='Valor de un guardado anterior (Simulación · hace" in banner


def test_news2_de_calculadoras_dice_procedencia_y_edad():
    at = _open("calculadoras", **{PATIENT_KEY: _patient_then_eeg()})
    captions = " ".join(c.value for c in at.main.caption)
    assert "FC 100 lpm · Simulación · hace" in captions
    assert "SpO₂ 92 % · Simulación · hace" in captions


def test_news2_de_temas_dice_procedencia_y_edad():
    from app.supermodules import ui_catalog as C
    at = AppTest.from_file(MAIN, default_timeout=240)
    at.session_state["biocore_start_page"] = "temas"
    at.session_state[PATIENT_KEY] = _patient_then_eeg()
    at.session_state[C.SELECTED_TOPIC_KEY] = "news2"
    at.session_state["bc_slide_news2"] = "Hallazgos"        # la lista NEWS2 del paciente vive en esa diapositiva
    at.run()
    assert at.exception == []
    text = " ".join(m.value for m in at.main.markdown)
    assert "Pulso: 1 punto (FC 100 lpm · Simulación · hace" in text, text[-600:]


def test_ecg_paciente_activo_dice_la_procedencia_de_su_fc():
    at = _open("ecg", **{PATIENT_KEY: _patient_then_eeg()})     # con FC del paciente, la fuente por defecto es él
    captions = " ".join(c.value for c in at.main.caption)
    assert "FC 100 lpm del paciente activo · Simulación · hace" in captions


# ── Revisión final de la T1.1 ──

def test_title_de_un_arrastre_trae_el_detalle_original_completo():
    from app.utils.patient_banner import display_detail, vital_provenance_text
    from domain.physiology.state import (
        DomainState, PhysiologicalDescriptor, Provenance, UnifiedPhysiologicalState, save_state,
    )
    from datetime import datetime, timezone
    patient_id = _patient_with({"respiratory": {"respiratory_rate": 18.0}})
    hr = PhysiologicalDescriptor("heart_rate", 88.0, "bpm", Provenance.SENSOR_REAL, 0.85, "ecg_lab:monitor")
    with _session_factory()() as session:
        save_state(session, UnifiedPhysiologicalState(
            patient_id=patient_id, timestamp=datetime.now(timezone.utc),
            cardiovascular=DomainState("cardiovascular", {"heart_rate": hr}),
            respiratory=DomainState("respiratory", {}), events=[]))
    _append_eeg(patient_id)

    def script():
        import streamlit as st
        from app.utils.patient_banner import display_detail, read_active_vitals, vital_provenance_text
        v = read_active_vitals()
        st.session_state["out"] = (display_detail(v.values["hr"], v.origins["hr"]),
                                   vital_provenance_text(v.values["hr"], v.origins["hr"]))

    at = AppTest.from_function(script)
    at.session_state[PATIENT_KEY] = patient_id
    at.run()
    title, label = at.session_state["out"]
    assert title == f"Valor de un guardado anterior ({label}); ecg_lab:monitor"


def test_horizonte_now_se_dice_en_espanol():
    from datetime import datetime, timezone
    from app.utils.patient_banner import vital_provenance_text
    from domain.physiology.state import CarryOrigin, PhysiologicalDescriptor, Provenance
    d = PhysiologicalDescriptor("heart_rate", 100.0, "bpm", Provenance.ARRASTRE_TEMPORAL, 0.6, None)
    origin = CarryOrigin("s1", datetime.now(timezone.utc), Provenance.SIMULACION, 2.0, "now")
    assert vital_provenance_text(d, origin) == "Simulación · horizonte ahora"


def test_registro_del_banner_apunta_a_la_linea_que_dibuja_el_valor():
    from app.utils.evidence_registry import ENTRIES
    for entry in [e for e in ENTRIES if e.superficie == "banner"]:
        path, line = entry.mostrado_en.rsplit(":", 1)
        assert "_value_html(" in Path(path).read_text(encoding="utf-8").splitlines()[int(line) - 1], entry.campo


def test_valor_del_ultimo_paso_de_una_trayectoria_dice_su_horizonte():
    """T3 (detalle de la T1.1): un valor del último guardado (sin origen de arrastre) que salió de una trayectoria de
    escenario se rotula con su horizonte, como sus valores arrastrados."""
    from app.utils.patient_banner import vital_provenance_text
    from domain.physiology.state import PhysiologicalDescriptor, Provenance

    d = PhysiologicalDescriptor(name="heart_rate", value=88.0, unit="bpm", provenance=Provenance.SIMULACION,
                                confidence=0.6, source_detail="escenario_rico:hypertension:modo:basal:horizonte:7d")
    assert vital_provenance_text(d) == "Simulación · horizonte 7 días"         # revisión final de la T6: en palabras
    plain = PhysiologicalDescriptor(name="heart_rate", value=88.0, unit="bpm", provenance=Provenance.SIMULACION,
                                    confidence=0.6, source_detail="twin_visual:x")
    assert vital_provenance_text(plain) == "Simulación"
