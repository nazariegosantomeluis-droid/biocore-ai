"""T4 de la ruta integrada (2026-11-18): varias unidades en la Ruta y la Unidad Integración (el sistema autónomo).

Integración une corazón, respiración y cerebro con la variabilidad cardiaca (decisión 6 firmada), los bancos HRV H1–H8 y
Hemodinámica G1–G10 y, al cierre, la PA del lazo cerrado del escenario del paciente («en revisión clínica» en sepsis,
declinada fuera de la fase modelada), como ya la muestra el Detective. Todo contra la base de pruebas.
"""

import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

MAIN = str(Path("app/main.py").resolve())
PATIENT_KEY = "twin_shell_ups_patient_id"
STATIONS = ("paciente", "concepto", "mide", "practica_hrv", "practica_hemo", "cierre")


def _texts(at, area=None):
    a = area or at
    parts = [m.value for m in a.markdown] + [c.value for c in a.caption] + [i.value for i in a.info]
    parts += [w.value for w in a.warning] + [s.value for s in a.success]
    return " ".join(parts)


def _open(**state):
    at = AppTest.from_file(MAIN, default_timeout=300)
    at.session_state["biocore_start_page"] = "ruta"
    for key, value in state.items():
        at.session_state[key] = value
    at.run()
    assert at.exception == [], at.exception
    return at


def _unit(at, key):
    at.radio(key="ruta_unit").set_value(key).run()
    assert at.exception == [], at.exception
    return at


def _start(scenario="healthy", unit="integracion"):
    at = _unit(_open(), unit)
    at.radio(key=f"ruta_{unit}_scenario").set_value(scenario).run()
    at.button(key=f"ruta_{unit}_start").click().run()
    assert at.exception == [], at.exception
    return at


def _go(at, station, unit="integracion"):
    index = STATIONS.index(station)
    if at.session_state["ruta_progress"][unit]["station"] != index:
        at.button(key=f"ruta_node_{index}").click().run()
    assert at.exception == [], at.exception
    return at


def _hr(at):
    from app.utils.patient_session import get_shared_ups_engine
    from domain.physiology.state import get_composed_patient, make_session_factory

    with make_session_factory(get_shared_ups_engine())() as session:
        return get_composed_patient(session, at.session_state[PATIENT_KEY]).state.cardiovascular.get("heart_rate")


# ── Task 2: varias unidades y lo compartido ────────────────────────────────────────────────────────────────────────
def _bank_script():
    from app.supermodules.ruta import common
    from educational.quiz_bank import HRV_QUESTIONS

    common.render_bank_practice(HRV_QUESTIONS[:2], "hrv", key_prefix="prueba_", unit_key="integracion")


def test_banco_registra_una_vez_con_su_concepto():
    from educational.quiz_bank import CONCEPT_BY_PROMPT, HRV_QUESTIONS

    at = AppTest.from_function(_bank_script, default_timeout=60).run()
    radio = at.radio(key="prueba_q_0_choice")
    radio.set_value(radio.options[0]).run()
    at.select_slider(key="prueba_q_0_conf").set_value(80).run()
    at.button(key="prueba_q_0_check").click().run()
    at.run()
    log = at.session_state["session_learning_log"]
    assert len(log) == 1 and log[0]["concept"] == CONCEPT_BY_PROMPT[HRV_QUESTIONS[0].prompt] == "hrv"
    assert log[0]["confidence"] == 80
    answers = at.session_state["ruta_progress"]["integracion"]["answers"]      # cuenta como de la unidad
    assert [{k: a[k] for k in ("item_id", "concept", "correct", "confidence")} for a in answers] == \
        [{k: r[k] for k in ("item_id", "concept", "correct", "confidence")} for r in log]


def test_unidades_pendientes_dicen_que_les_falta():
    at = _open()
    assert at.radio(key="ruta_unit").options == ["Unidad Corazón", "Unidad Integración"]
    text = _texts(at)
    for unit in ("Respiración", "Cerebro", "Músculo"):
        assert f"Unidad {unit} (pendiente)" in text


# ── Task 3: Unidad Integración ─────────────────────────────────────────────────────────────────────────────────────
def test_mide_arranca_en_la_fc_del_paciente():
    at = _go(_start("hypertension"), "mide")
    hr = round(_hr(at).value)
    sliders = {s.key: s.value for s in at.main.slider}
    assert sliders["ruta_integracion_mide__hrv_hr_base"] == hr
    assert not at.sidebar.slider                                            # los controles de la fuente van en la estación
    assert [r.key for r in at.sidebar.radio] == ["biocore_lang"]            # el menú lateral solo tiene el idioma
    assert "Hardware" not in _texts(at)


def test_mide_guarda_y_la_franja_lo_dice():
    at = _go(_start("healthy"), "mide")
    at.session_state["ruta_integracion_mide__hrv_duration"] = 60
    at.run()
    at.button(key="ruta_integracion_mide__hrv_lab_save_to_ups").click().run()
    assert at.exception == [], at.exception
    hr = _hr(at)
    assert hr.source_detail.startswith("hrv_lab:")
    assert f"Guardaste FC {hr.value:.0f} lpm" in _texts(at)


def test_cierre_sepsis_pa_en_revision():
    at = _go(_start("sepsis"), "cierre")
    text = _texts(at)
    assert "en revisión clínica" in text and "mmHg" in text
    assert "no se guarda" in text


def test_cierre_sano_pa_calculada():
    at = _go(_start("healthy"), "cierre")
    text = _texts(at)
    assert "PA calculada" in text and "mmHg" in text and "en revisión clínica" not in text


def test_cierre_sepsis_fuera_de_la_fase_declina():
    """Si la FC del paciente ya no viene de la trayectoria (la guardó HRV), la fase no se identifica: la PA se declina."""
    at = _go(_start("sepsis"), "mide")
    # La FC de la sepsis (150) no cabe en la simulación con RSA: se guarda una serie pegada a mano.
    at.radio(key="ruta_integracion_mide__hrv_source").set_value("Serie RR manual").run()
    rr = ",".join(str(400 + (i % 5) * 4) for i in range(120))
    at.text_area(key="ruta_integracion_mide__hrv_manual_rr").set_value(rr).run()
    at.button(key="ruta_integracion_mide__hrv_lab_save_to_ups").click().run()
    _go(at, "cierre")
    assert "mmHg" not in " ".join(m.value for m in at.markdown if "PA calculada" in m.value)
    assert "Presión arterial" in _texts(at) or "declina" in _texts(at)


def test_practica_hemodinamica_registra_con_su_concepto():
    at = _go(_start("healthy"), "practica_hemo")
    radio = at.radio(key="ruta_integracion_hemo_q_0_choice")
    radio.set_value(radio.options[0]).run()
    at.button(key="ruta_integracion_hemo_q_0_check").click().run()
    assert at.session_state["session_learning_log"][-1]["concept"] == "hemodinamica"


def test_dos_unidades_no_mezclan_pacientes():
    at = _start("sepsis", unit="corazon")
    heart_pid = at.session_state[PATIENT_KEY]
    _unit(at, "integracion")
    assert "el paciente activo no es el de esta unidad" in _texts(at) or "sin paciente de la unidad" in _texts(at)
    at.radio(key="ruta_integracion_scenario").set_value("healthy").run()
    at.button(key="ruta_integracion_start").click().run()
    integ_pid = at.session_state[PATIENT_KEY]
    assert integ_pid != heart_pid
    _unit(at, "corazon")                                                    # vuelve a la estación 0 de Corazón
    assert "el paciente activo no es el de esta unidad" in _texts(at)        # la franja no muestra al otro
    assert any("ya no es el de esta unidad" in w.value for w in at.warning)
    at.button(key="ruta_back_to_unit_patient").click().run()
    assert at.session_state[PATIENT_KEY] == heart_pid


@pytest.mark.parametrize("station", STATIONS)
def test_cada_estacion_sin_ingles_ni_emoji(station):
    at = _go(_start("hypertension"), station)
    text = _texts(at, at.main) + " ".join(b.label for b in at.main.button)
    assert "bpm" not in text and " Lab" not in text
    assert not re.search(r"[\U0001F300-\U0001FAFF⛔]", text)


# ── Revisión final de la T4 ────────────────────────────────────────────────────────────────────────────────────────
def test_mide_en_sepsis_no_dice_que_empieza_en_el_paciente_ni_guarda_otra_fc():
    """La FC de la sepsis (150) no cabe en la simulación (40–140): la serie empieza en 72. La estación lo dice y no
    ofrece guardar, para no escribirle al paciente una FC que no es la suya."""
    at = _go(_start("sepsis"), "mide")
    text = _texts(at)
    assert "empieza en la FC y la FR de tu paciente" not in text
    assert "fuera del rango de la simulación" in text
    assert not [b for b in at.button if b.key == "ruta_integracion_mide__hrv_lab_save_to_ups"]


def test_las_respuestas_vuelven_a_contar_despues_de_empezar_de_nuevo():
    at = _go(_start("healthy"), "practica_hrv")
    for _ in range(2):
        radio = at.radio(key="ruta_integracion_hrv_q_0_choice")
        radio.set_value(radio.options[0]).run()
        at.button(key="ruta_integracion_hrv_q_0_check").click().run()
        _go(at, "cierre")
        assert "1 respuesta" in _texts(at)
        _go(at, "paciente")
        at.button(key="ruta_integracion_start").click().run()
        _go(at, "practica_hrv")
