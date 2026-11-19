"""T4 de la ruta integrada (segunda parte, 2026-11-18): las unidades Respiración, Cerebro y Músculo.

Cada una monta su laboratorio convertido en instrumento (`app/instruments/respiracion.py`, `eeg.py`, `emg.py`) sobre
el paciente de la unidad, con su banco firmado y un cierre que dice lo que el sistema hace con el otro (o por qué no lo
calcula). Un recorrido por unidad, estación por estación, contra la base de pruebas.
"""

import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

MAIN = str(Path("app/main.py").resolve())
PATIENT_KEY = "twin_shell_ups_patient_id"
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿⭐⚠⛔⏱]")


def _texts(at, area=None):
    a = area or at.main
    parts = [m.value for m in a.markdown] + [c.value for c in a.caption] + [i.value for i in a.info]
    parts += [w.value for w in a.warning] + [s.value for s in a.success] + [e.value for e in a.error]
    return " ".join(parts)


def _open():
    at = AppTest.from_file(MAIN, default_timeout=300)
    at.session_state["biocore_start_page"] = "ruta"
    at.run()
    assert at.exception == [], at.exception
    return at


def _start(unit, scenario="healthy"):
    at = _open()
    at.radio(key="ruta_unit").set_value(unit).run()
    at.radio(key=f"ruta_{unit}_scenario").set_value(scenario).run()
    at.button(key=f"ruta_{unit}_start").click().run()
    assert at.exception == [], at.exception
    return at


def _go(at, unit, station):
    from app.supermodules.ruta import units

    index = [s.key for s in units.UNIT_BY_KEY[unit].stations].index(station)
    if at.session_state["ruta_progress"][unit]["station"] != index:
        at.button(key=f"ruta_node_{index}").click().run()
    assert at.exception == [], at.exception
    return at


def _composed(at):
    from app.utils.patient_session import get_shared_ups_engine
    from domain.physiology.state import get_composed_patient, make_session_factory

    with make_session_factory(get_shared_ups_engine())() as session:
        return get_composed_patient(session, at.session_state[PATIENT_KEY])


def _button(at, key):
    found = [b for b in at.button if b.key == key]
    return found[0] if found else None


# ── las cinco unidades ─────────────────────────────────────────────────────────────────────────────────────────────
def test_el_selector_tiene_las_cinco_unidades_en_el_orden_del_diseno():
    at = _open()
    assert at.radio(key="ruta_unit").options == ["Unidad Corazón", "Unidad Respiración", "Unidad Cerebro",
                                                 "Unidad Músculo", "Unidad Integración"]
    assert "(pendiente): falta" not in _texts(at)


def test_los_prefijos_de_las_unidades_no_se_pisan():
    """«Empezar de nuevo» borra las claves que empiezan con el prefijo de la unidad: un prefijo que fuera el comienzo
    de otro borraría el estado de la otra unidad (detalle diferido de la T4)."""
    from app.supermodules.ruta import cerebro, corazon, integracion, musculo, respiracion

    prefixes = [m.PREFIX for m in (corazon, respiracion, cerebro, musculo, integracion)]
    for a in prefixes:
        for b in prefixes:
            assert a == b or not b.startswith(a), (a, b)


@pytest.mark.parametrize("unit,scenario", [("respiracion", "hypoxia"), ("cerebro", "healthy"), ("musculo", "fatigue")])
def test_cada_estacion_se_dibuja_sin_emoji_ni_ingles(unit, scenario):
    from app.supermodules.ruta import units

    at = _start(unit, scenario)
    for station in units.UNIT_BY_KEY[unit].stations:
        _go(at, unit, station.key)
        text = _texts(at)
        assert not EMOJI.search(text), (station.key, EMOJI.findall(text))
        assert "bpm" not in text and "Unified Physiological State" not in text and " lab " not in text, station.key
        assert "No se pudo" not in text, station.key
    assert not at.sidebar.slider and not at.sidebar.number_input        # los controles van en la estación


# ── Unidad Respiración ─────────────────────────────────────────────────────────────────────────────────────────────
def test_respiracion_mide_empieza_en_la_fr_del_paciente_y_guarda_como_simulacion():
    at = _go(_start("respiracion"), "respiracion", "mide")
    composed = _composed(at)
    rr = round(composed.state.respiratory.get("respiratory_rate").value)
    assert at.number_input(key="ruta_respiracion_mide__resp_rr").value == rr
    _button(at, "ruta_respiracion_mide__respiratory_lab_save_to_ups").click().run()
    assert at.exception == [], at.exception
    saved = _composed(at).state.respiratory.get("respiratory_rate")
    assert saved.provenance.name == "SIMULACION" and saved.source_detail.startswith("respiratory_lab:")
    assert "Guardaste FR" in _texts(at) and "Guardaste FC" not in _texts(at)   # la franja dice lo que se guardó


def test_respiracion_cierre_muestra_los_puntos_news2_del_paciente():
    at = _go(_start("respiracion", "hypoxia"), "respiracion", "cierre")
    text = _texts(at)
    spo2 = round(_composed(at).state.respiratory.get("spo2").value)
    assert f"SpO₂ {spo2} %" in text and "NEWS2 (RCP 2017)" in text and "nunca un total" in text
    assert [p for p in at.main.get("page_link") if p.proto.page.endswith("detective")] or "Detective" in text


def test_respiracion_practica_registra_news2():
    at = _go(_start("respiracion"), "respiracion", "practica")
    radio = at.radio(key="ruta_respiracion_news2_q_0_choice")
    radio.set_value(radio.options[0]).run()
    at.button(key="ruta_respiracion_news2_q_0_check").click().run()
    assert at.session_state["session_learning_log"][-1]["concept"] == "news2"
    assert len(at.session_state["ruta_progress"]["respiracion"]["answers"]) == 1


# ── Unidad Cerebro ─────────────────────────────────────────────────────────────────────────────────────────────────
def _save_eeg(at, pattern="Vigilia con arousal (alfa y beta)"):     # T6.1: BAR dentro del rango y del techo
    _go(at, "cerebro", "mide")
    at.selectbox(key="ruta_cerebro_mide__eeg_pattern").set_value(pattern).run()
    _button(at, "ruta_cerebro_mide__eeg_lab_save_to_ups").click().run()
    assert at.exception == [], at.exception
    return at


def test_cerebro_mide_guarda_el_eeg_en_el_paciente_de_la_unidad():
    at = _save_eeg(_start("cerebro"))
    bar = _composed(at).state.neurological.get("bar")
    assert bar is not None
    assert "valores de cerebro" in _texts(at)                            # la franja: no dice «Guardaste FC»
    assert "Hardware EEG en vivo" not in " ".join(at.radio(key="ruta_cerebro_mide__eeg_source").options)


def test_cerebro_cierre_muestra_la_regla_bar_con_su_fuente_y_su_confianza():
    """La composición en sí: `test_cerebro_compone_con_la_fc_medida_en_la_estacion` (con una FC medida en la unidad;
    la del escenario es una proyección y no se compone)."""
    at = _go(_save_eeg(_start("cerebro")), "cerebro", "cierre")
    text = _texts(at)
    assert "AROUSAL_TAQUICARDIA_BAR" in text and "Guyton" in text and "0.70" in text and "validada por su fuente" in text


def test_cerebro_cierre_sin_eeg_no_compone():
    """T6: sin botón «Componer»; sin EEG, la estación dice qué falta y no acopla nada."""
    at = _go(_start("cerebro"), "cerebro", "cierre")
    assert "BAR de tu paciente" in _texts(at) and "todavía no hay una medición guardada" in _texts(at)
    assert _composed(at).state.cardiovascular.get("heart_rate_acoplado") is None


def test_cerebro_cierre_en_estres_no_evalua_la_regla():
    at = _go(_save_eeg(_start("cerebro", "stress")), "cerebro", "cierre")
    assert "no se evalúa en el escenario Estrés" in _texts(at)
    assert _button(at, "ruta_cerebro_compose") is None


# ── Unidad Músculo ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_musculo_mide_guarda_la_activacion_como_simulacion():
    at = _go(_start("musculo", "fatigue"), "musculo", "mide")
    assert at.radio(key="ruta_musculo_mide__emg_source").options == ["Demo", "CSV"]   # sin sensor en vivo
    _button(at, "ruta_musculo_mide__emg_lab_save_to_ups").click().run()
    assert at.exception == [], at.exception
    activation = _composed(at).state.muscular.get("activation")
    assert activation is not None and activation.provenance.name == "SIMULACION"
    assert "valores de músculo" in _texts(at)


def test_musculo_cierre_no_calcula_la_respuesta_de_la_fc_sin_firma():
    at = _go(_start("musculo", "fatigue"), "musculo", "cierre")
    text = _texts(at)
    assert "Respuesta de la FC a la contracción" in text and "está firmada" in text
    assert "todavía no guardaste el EMG" in text
    assert "Pendiente: La respuesta de la FC a la contracción" in text   # en el riel


def test_musculo_practica_registra_emg():
    at = _go(_start("musculo"), "musculo", "practica")
    radio = at.radio(key="ruta_musculo_emg_q_0_choice")
    radio.set_value(radio.options[0]).run()
    at.button(key="ruta_musculo_emg_q_0_check").click().run()
    assert at.session_state["session_learning_log"][-1]["concept"] == "emg"


# ── Revisión final de la T4 (segunda parte) ───────────────────────────────────────────────────────────────────────
def _cierre_cerebro_con_fc_medida():
    at = _go(_save_eeg(_start("cerebro")), "cerebro", "cierre")
    _button(at, "ruta_cerebro_fc__hrv_lab_save_to_ups").click().run()
    assert at.exception == [], at.exception
    return at


def test_cerebro_no_compone_la_fc_proyectada_del_escenario():
    """La FC del escenario es la proyección del simulador (horizonte 7 días), no una medición de este momento."""
    at = _go(_save_eeg(_start("cerebro")), "cerebro", "cierre")
    assert "proyección de un escenario" in _texts(at)
    assert _composed(at).state.cardiovascular.get("heart_rate_acoplado") is None


def test_cerebro_compone_con_la_fc_medida_en_la_estacion():
    """T6: medir la FC basta (la regla se evalúa sola al guardar; ya no hay botón «Componer»)."""
    at = _cierre_cerebro_con_fc_medida()
    assert _button(at, "ruta_cerebro_compose") is None
    coupled = _composed(at).state.cardiovascular.get("heart_rate_acoplado")
    assert coupled is not None and coupled.provenance.name == "DERIVADO_ACOPLAMIENTO"   # «Beta (activo)»: BAR > 1.8
    assert "se aplicó" in _texts(at)


def test_cerebro_no_vuelve_a_componer_las_copias():
    """T6: con una FC nueva, la regla junta el BAR MEDIDO (el del EEG, simulación), nunca la copia de la evaluación
    anterior (que sería un arrastre); el dominio lo prueba en `test_t6_compositor_reglas.py`."""
    at = _cierre_cerebro_con_fc_medida()
    _button(at, "ruta_cerebro_fc__hrv_lab_save_to_ups").click().run()
    assert at.exception == [], at.exception
    result = at.session_state["ruta_cerebro_coupling_result"]
    assert result["condition"].startswith("BAR") and "Simulación" in result["condition"]
    assert "Arrastre" not in result["condition"]


def test_cerebro_estado_con_palabras_y_sin_csv():
    at = _cierre_cerebro_con_fc_medida()
    text = _texts(at)
    assert "simulacion" not in text and "validado_por_fuente" not in text and "arrastre_temporal" not in text
    at2 = _go(_start("cerebro"), "cerebro", "mide")
    assert at2.radio(key="ruta_cerebro_mide__eeg_source").options == ["Generar EEG sintético"]


@pytest.mark.parametrize("unit,signal", [("cerebro", "EEG"), ("musculo", "EMG")])
def test_la_estacion_0_dice_que_el_escenario_no_genera_la_senal(unit, signal):
    at = _open()
    at.radio(key="ruta_unit").set_value(unit).run()
    assert f"no genera {signal}" in _texts(at)


def test_respiracion_epoc_no_puntua_la_spo2_con_la_escala_1():
    at = _go(_start("respiracion", "copd"), "respiracion", "cierre")
    text = _texts(at)
    assert "escala 2" in text and "SpO₂ (escala 1)" not in text


def test_respiracion_el_enlace_a_la_calculadora_no_lleva_emoji_en_la_estacion():
    at = _go(_start("respiracion"), "respiracion", "mide")
    links = [p for p in at.main.get("page_link") if "calculadora" in p.proto.label]
    assert links and all(not p.proto.icon for p in links)


# ── T4.1 (2026-11-18): rango de la SpO₂, confirmación del guardado, BAR fuera del rango de la fuente, fichas ────────
def test_respiracion_mide_empieza_en_la_spo2_de_la_hipoxia_y_la_guarda():
    at = _go(_start("respiracion", "hypoxia"), "respiracion", "mide")
    spo2 = round(_composed(at).state.respiratory.get("spo2").value)
    assert at.number_input(key="ruta_respiracion_mide__resp_spo2_basal").value == spo2
    assert "fuera del rango de la simulación" not in _texts(at)
    _button(at, "ruta_respiracion_mide__respiratory_lab_save_to_ups").click().run()
    assert at.exception == [], at.exception
    assert round(_composed(at).state.respiratory.get("spo2").value) == spo2


def test_respiracion_mide_con_fr_de_apnea_no_ofrece_guardar():
    at = _go(_start("respiracion", "apnea"), "respiracion", "mide")
    assert "fuera del rango de la simulación" in _texts(at)
    assert _button(at, "ruta_respiracion_mide__respiratory_lab_save_to_ups") is None


def test_el_guardado_se_confirma_en_la_estacion():
    at = _go(_start("respiracion"), "respiracion", "mide")
    _button(at, "ruta_respiracion_mide__respiratory_lab_save_to_ups").click().run()
    assert any("Guardado en tu paciente" in s.value and "FR" in s.value for s in at.main.success)


def test_cerebro_dice_el_rango_de_la_fuente_y_que_el_aumento_no_crece_con_el_bar():
    at = _cierre_cerebro_con_fc_medida()
    text = _texts(at)
    assert "basal 0.8–1.2" in text and "no crece con el BAR" in text


def test_musculo_dice_que_su_regla_esta_firmada_y_espera_la_calibracion():
    at = _go(_start("musculo"), "musculo", "cierre")
    text = _texts(at)
    assert "firmada" in text and "calibración" in text and "espera su firma" not in text


def test_respiracion_cierre_muestra_la_regla_de_hipoxia_firmada_y_por_que_no_se_evalua():
    """T6: la regla ya se evalúa en la ruta (`test_t6_acoplamientos_ruta.py`); con la FC del escenario, dice por qué
    no (es una proyección)."""
    at = _go(_start("respiracion"), "respiracion", "cierre")
    text = _texts(at)
    assert "HIPOXIA_TAQUICARDIA" in text and "Halliwill" in text and "se evalúa sola" in text
    assert "falta su compositor" not in text           # falso: el escenario ya guarda la SpO₂ y la FC juntas
    at2 = _go(_start("respiracion", "hypoxia"), "respiracion", "cierre")
    assert "no se evalúa en el escenario Hipoxia" in _texts(at2)


def test_respiracion_mide_con_spo2_por_debajo_de_70_no_ofrece_guardar():
    """Revisión de la T5: ninguna prueba de estación cubría una SpO₂ por debajo del nuevo control (70–100 %)."""
    from app.engines.digital_twin_organism import DigitalTwinOrganism
    from app.utils.patient_session import get_shared_ups_engine
    from domain.physiology.state import Provenance, from_digital_twin_organism, make_session_factory, save_state

    at = _start("respiracion")
    o = DigitalTwinOrganism()
    o.update_from_sensors({"respiratory": {"respiratory_rate": 22.0, "spo2": 65.0}})
    with make_session_factory(get_shared_ups_engine())() as session:
        save_state(session, from_digital_twin_organism(o, at.session_state[PATIENT_KEY], Provenance.SIMULACION, 0.8))
    at = _go(at, "respiracion", "mide")
    assert "fuera del rango de la simulación" in _texts(at)
    assert _button(at, "ruta_respiracion_mide__respiratory_lab_save_to_ups") is None


def test_respiracion_avisa_que_las_tasas_de_desaturacion_no_se_midieron_desde_una_basal_baja():
    at = _go(_start("respiracion", "hypoxia"), "respiracion", "mide")
    assert "no se midieron desde una basal" in _texts(at)
    at2 = _go(_start("respiracion"), "respiracion", "mide")
    assert "no se midieron desde una basal" not in _texts(at2)
