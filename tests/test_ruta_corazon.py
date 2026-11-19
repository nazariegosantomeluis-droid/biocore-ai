"""T3 de la ruta integrada (2026-11-18): la Unidad Corazón en la página Ruta.

Prueba que la cierra (diseño firmado): recorrido AppTest estación por estación. El paciente de la estación 0 es el que
late en el ECG, el que carga la calculadora y el del cierre; con una fuente que sí guarda, su valor reemplaza al
anterior en las estaciones siguientes. Todo contra la base de pruebas (`tests/conftest.py`).
"""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from app.utils.session_learning import get_session_log  # noqa: F401  (documenta de dónde sale el registro)

MAIN = str(Path("app/main.py").resolve())
PATIENT_KEY = "twin_shell_ups_patient_id"
STATIONS = ("paciente", "concepto", "observa", "mide", "practica", "altera", "concepto_12", "cierre")


def _open(**state):
    at = AppTest.from_file(MAIN, default_timeout=300)
    at.session_state["biocore_start_page"] = "ruta"
    for key, value in state.items():
        at.session_state[key] = value
    at.run()
    assert at.exception == [], at.exception
    return at


def _texts(at):
    parts = [m.value for m in at.markdown] + [c.value for c in at.caption] + [i.value for i in at.info]
    parts += [w.value for w in at.warning] + [s.value for s in at.success]
    return " ".join(parts)


def _start(scenario="hypertension"):
    at = _open()
    at.radio(key="ruta_corazon_scenario").set_value(scenario).run()
    at.button(key="ruta_corazon_start").click().run()
    assert at.exception == [], at.exception
    return at


def _go(at, station):
    index = STATIONS.index(station)
    if at.session_state["ruta_progress"]["corazon"]["station"] == index:     # ya está ahí (su nodo está deshabilitado)
        return at
    at.button(key=f"ruta_node_{index}").click().run()
    assert at.exception == [], at.exception
    return at


def _unit_hr(at):
    from app.utils.patient_session import get_shared_ups_engine
    from domain.physiology.state import get_composed_patient, make_session_factory

    with make_session_factory(get_shared_ups_engine())() as session:
        composed = get_composed_patient(session, at.session_state[PATIENT_KEY])
    return composed.state.cardiovascular.get("heart_rate")


# ── menú ───────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_ruta_esta_en_el_menu_con_su_icono():
    from app.main import _page_specs
    from app.utils import design_system as DS

    specs = {url: (section, title) for section, url, title, *_ in _page_specs()}
    assert specs["ruta"] == ("", "Ruta")
    assert (Path(DS.ICONS_URL.replace("app/static", "app/static")) / DS.NAV_ICONS["ruta"]).exists()


# ── estación 0 ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_estacion_0_crea_el_paciente_de_la_unidad():
    at = _start("hypertension")
    pid = at.session_state[PATIENT_KEY]
    assert at.session_state["ruta_progress"]["corazon"]["patient_id"] == pid
    hr = _unit_hr(at)
    assert hr is not None and hr.provenance.name == "SIMULACION"
    assert hr.source_detail.startswith("escenario_rico:hypertension:")
    text = _texts(at)
    assert "Unidad Corazón · Hipertensión" in text and "horizonte" in text


def test_riel_y_siguiente():
    at = _start("healthy")
    assert at.button(key="ruta_node_0").disabled                     # la estación actual
    at.button(key="ruta_next").click().run()
    assert at.session_state["ruta_progress"]["corazon"]["station"] == 1
    text = _texts(at)
    assert "se pierde al cerrar" in text and "dominada" not in text.replace("no como dominada", "")
    assert "Tu paciente ahora: FC" in text                           # el hilo describe al paciente


# ── el mismo paciente en cada estación ─────────────────────────────────────────────────────────────────────────────
def test_el_paciente_late_en_el_ecg_y_carga_la_calculadora():
    at = _go(_start("hypertension"), "mide")
    hr = _unit_hr(at).value
    text = _texts(at)
    assert f"Trazo simulado a la FC {hr:.0f} lpm del paciente activo" in text
    assert at.radio(key="ruta_corazon_mide__ecg_monitor_source").value == "Paciente activo (simulación a su FC)"
    assert f"FC del paciente: {hr:.0f} lpm" in text                    # la calculadora de QTc usa su FC
    at.number_input(key="ruta_corazon_qt").set_value(400.0).run()
    assert "QTc" in _texts(at) + " ".join(m.value for m in at.markdown)
    assert not at.sidebar.radio or "Origen del ECG" not in [r.label for r in at.sidebar.radio]


def test_fuente_que_guarda_reemplaza_el_valor_en_las_siguientes():
    from src.signals.ecg.rsa import RsaParams, generate_rsa_signals

    at = _go(_start("hypertension"), "mide")
    before = _unit_hr(at).value
    # Un registro con variabilidad (RSA): uno perfectamente regular lo declina la compuerta (SDNN < 3 ms).
    signal = generate_rsa_signals(RsaParams(hr_base_bpm=115.0, rsa_amplitude_bpm=5.0, respiratory_rate_rpm=15.0),
                                  30.0, fs=250.0).ecg
    at.session_state["ruta_corazon_mide___ecg_monitor_mitbih_cache"] = (signal, 250.0,
                                                                        {"source": "MIT-BIH 100 (PhysioNet)"})
    at.radio(key="ruta_corazon_mide__ecg_monitor_source").set_value("Base de datos MIT-BIH").run()
    at.button(key="ruta_corazon_mide__ecg_lab_save_to_ups").click().run()
    assert at.exception == [], at.exception
    saved = _unit_hr(at)
    hr = round(saved.value)
    assert abs(hr - 115) <= 3 and abs(round(before) - hr) > 3 and saved.source_detail.startswith("ecg_lab:")
    assert f"Guardaste FC {hr} lpm" in _texts(at)                      # la franja lo dice ahí mismo
    _go(at, "practica")
    assert f"Tu paciente ahora: FC {hr} lpm" in _texts(at)
    _go(at, "cierre")
    text = _texts(at)
    assert f"FC {hr} lpm" in text and f"FC {before:.0f} lpm" in text   # ahora y al empezar


def test_cierre_es_el_mismo_paciente():
    at = _start("healthy")
    pid = at.session_state[PATIENT_KEY]
    _go(at, "cierre")
    assert pid[:8] in _texts(at)
    assert at.session_state[PATIENT_KEY] == pid


def test_practica_registra_con_su_confianza():
    at = _go(_start("healthy"), "practica")
    radio = at.radio(key="ruta_corazon_fc_q_0_choice")
    radio.set_value(radio.options[0]).run()
    at.select_slider(key="ruta_corazon_fc_q_0_conf").set_value(70).run()
    at.button(key="ruta_corazon_fc_q_0_check").click().run()
    log = at.session_state["session_learning_log"]
    assert log and log[-1]["source"] == "quiz" and log[-1]["concept"] == "frecuencia_cardiaca"
    assert log[-1]["confidence"] == 70


def test_altera_usa_el_escenario_del_paciente():
    at = _go(_start("healthy"), "altera")
    from app.supermodules import what_if as W

    sano = [c.label for c in W.CASES if c.scenario == "healthy"]
    assert at.selectbox(key="ruta_corazon_altera__what_if_case").options == sano


def test_sepsis_altera_declina():
    at = _go(_start("sepsis"), "altera")
    assert not [s for s in at.selectbox if s.key == "ruta_corazon_altera__what_if_case"]
    assert "No se ofrecen:** la sepsis" in _texts(at)


# ── sin paciente o con otro paciente ───────────────────────────────────────────────────────────────────────────────
def test_sin_paciente_de_la_unidad_las_estaciones_lo_dicen():
    at = _open(ruta_progress={"corazon": {"station": 3, "visited": {0, 3}, "patient_id": None, "scenario": None,
                                          "start": {}, "trajectory": []}})
    assert "Sin dato: falta Paciente de la unidad" in _texts(at)
    assert PATIENT_KEY not in at.session_state                        # mirar la ruta no crea pacientes
    assert not [r for r in at.radio if r.key == "ruta_corazon_mide__ecg_monitor_source"]


def test_paciente_activo_cambiado_fuera_de_la_ruta():
    from app.utils.patient_session import get_shared_ups_engine
    from domain.physiology.state import create_patient, make_session_factory

    at = _start("healthy")
    unit_pid = at.session_state[PATIENT_KEY]
    with make_session_factory(get_shared_ups_engine())() as session:
        other = create_patient(session, display_name="otro paciente")
    at.session_state[PATIENT_KEY] = other
    _go(at, "mide")
    assert "El paciente activo ya no es el de esta unidad" in _texts(at)
    assert not [r for r in at.radio if r.key == "ruta_corazon_mide__ecg_monitor_source"]
    at.button(key="ruta_back_to_unit_patient").click().run()
    assert at.session_state[PATIENT_KEY] == unit_pid


@pytest.mark.parametrize("station", STATIONS)
def test_cada_estacion_dibuja_hasta_el_final_sin_ingles_ni_emoji(station):
    import re

    at = _go(_start("hypertension"), station)
    main = at.main
    text = " ".join([m.value for m in main.markdown] + [c.value for c in main.caption] + [i.value for i in main.info]
                    + [w.value for w in main.warning] + [b.label for b in main.button])
    assert "bpm" not in text and " Lab" not in text
    assert not re.search(r"[\U0001F300-\U0001FAFF\u26D4]", text)     # sin emoji en la ruta (el menú lateral es aparte)


# ── revisión final de la T3 ────────────────────────────────────────────────────────────────────────────────────────
def _franja(at):
    return next(m.value for m in at.markdown if m.value.startswith("<div class='bc-franja"))


def _other_patient_with_hr(hr):
    from app.engines.digital_twin_organism import DigitalTwinOrganism
    from app.utils.patient_session import get_shared_ups_engine
    from app.utils.physiological_state import persist_current_state
    from domain.physiology.state import create_patient, make_session_factory

    organism = DigitalTwinOrganism()
    organism.update_from_sensors({"ecg": {"heart_rate": hr}})
    with make_session_factory(get_shared_ups_engine())() as session:
        pid = create_patient(session, display_name="otro paciente")
        persist_current_state(session, organism, pid, source_detail="twin_visual:otro")
    return pid


def test_la_franja_no_muestra_a_otro_paciente_como_el_tuyo():
    at = _start("healthy")
    at.session_state[PATIENT_KEY] = _other_patient_with_hr(150.0)
    _go(at, "concepto")
    assert "<b>150</b>" not in _franja(at) and "no es el de esta unidad" in _franja(at)
    _go(at, "paciente")                                                # la estación 0 también lo dice
    assert any("ya no es el de esta unidad" in w.value for w in at.warning)


def test_antes_de_empezar_la_franja_no_toma_al_paciente_de_otra_pagina():
    at = _open(**{PATIENT_KEY: _other_patient_with_hr(150.0)})
    assert "<b>150</b>" not in _franja(at) and "sin paciente de la unidad" in _franja(at)


def test_las_estaciones_que_no_leen_al_paciente_no_se_bloquean():
    from app.supermodules import learn_theory as LT

    at = _start("healthy")
    at.session_state[PATIENT_KEY] = _other_patient_with_hr(150.0)
    _go(at, "concepto")
    assert LT.SIGNED_ECG_PAPER.title in _texts(at)
    assert "Tu paciente ahora" not in _texts(at)                     # el hilo solo describe al paciente de la unidad


def test_el_paciente_de_la_unidad_no_hereda_la_fuente_del_gemelo():
    """Una arritmia aplicada antes en el gemelo no puede dejar sin trazo a un paciente sano de la unidad."""
    at = _open(twin_shell_input_source="arritmia Fibrilación auricular (semilla 1)")
    at.radio(key="ruta_corazon_scenario").set_value("healthy").run()
    at.button(key="ruta_corazon_start").click().run()
    _go(at, "mide")
    assert "Trazo simulado a la FC" in _texts(at) and "ritmo no modelado" not in _texts(at)
    assert "twin_shell_organism" not in at.session_state


def test_el_qtc_de_la_estacion_cita_su_formula():
    from clinical import calculators as calc

    at = _go(_start("healthy"), "mide")
    at.number_input(key="ruta_corazon_qt").set_value(400.0).run()
    page = " ".join(m.value for m in at.markdown)
    assert calc.BAZETT_CITATION in page and calc.HODGES_CITATION in page


def test_el_cierre_no_dice_que_solo_una_estacion_guarda():
    at = _go(_start("healthy"), "cierre")
    assert "es porque una estación guardó" not in _texts(at)


def test_la_estacion_actual_del_riel_se_ve_marcada_no_apagada():
    """Un botón deshabilitado de Streamlit se pinta gris y transparente: la estación actual parecía apagada. El CSS le
    da el texto y el fondo de «resalte», un par medido en CONTRAST_PAIRS."""
    import inspect

    from app.utils import design_system as DS

    src = inspect.getsource(DS.inject_global_theme)
    rule = next(line for line in src.splitlines() if 'st-key-bc_node"] button:disabled' in line)
    assert "PALETTE.TINTA_TITULO" in rule and "PALETTE.RESALTE" in rule
    assert ("TINTA_TITULO", "RESALTE", 4.5) in DS.CONTRAST_PAIRS


# ── T4: detalles menores de la T3 ──────────────────────────────────────────────────────────────────────────────────
def test_cierre_cuenta_solo_lo_practicado_en_la_unidad():
    at = _start("healthy")
    at.session_state["session_learning_log"] = [                     # respuestas de otras páginas
        {"item_id": "x", "source": "quiz", "concept": "frecuencia_cardiaca", "correct": True, "confidence": 50,
         "ts": "2026-11-18T00:00:00+00:00"}] * 3
    _go(at, "practica")
    radio = at.radio(key="ruta_corazon_fc_q_0_choice")
    radio.set_value(radio.options[0]).run()
    at.button(key="ruta_corazon_fc_q_0_check").click().run()
    _go(at, "cierre")
    assert "1 respuesta" in _texts(at) and "4 respuestas" not in _texts(at)


def test_empezar_de_nuevo_reinicia_la_unidad_y_recuerda_el_escenario():
    at = _go(_start("hypertension"), "mide")
    at.number_input(key="ruta_corazon_qt").set_value(400.0).run()
    _go(at, "paciente")
    assert at.radio(key="ruta_corazon_scenario").value == "hypertension"    # no vuelve a «Sano»
    at.radio(key="ruta_corazon_scenario").set_value("sepsis").run()
    at.button(key="ruta_corazon_start").click().run()
    progress = at.session_state["ruta_progress"]["corazon"]
    assert progress["visited"] == {0} and progress["scenario"] == "sepsis"
    assert "ruta_corazon_qt" not in at.session_state


def test_el_hilo_muestra_lo_que_mide_acaba_de_guardar():
    from src.signals.ecg.rsa import RsaParams, generate_rsa_signals

    at = _go(_start("hypertension"), "mide")
    signal = generate_rsa_signals(RsaParams(hr_base_bpm=115.0, rsa_amplitude_bpm=5.0, respiratory_rate_rpm=15.0),
                                  30.0, fs=250.0).ecg
    at.session_state["ruta_corazon_mide___ecg_monitor_mitbih_cache"] = (signal, 250.0,
                                                                        {"source": "MIT-BIH 100 (PhysioNet)"})
    at.radio(key="ruta_corazon_mide__ecg_monitor_source").set_value("Base de datos MIT-BIH").run()
    at.button(key="ruta_corazon_mide__ecg_lab_save_to_ups").click().run()
    hr = round(_unit_hr(at).value)
    assert f"Tu paciente ahora: FC {hr} lpm" in _texts(at) and f"Guardaste FC {hr} lpm" in _texts(at)
