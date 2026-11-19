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


def test_respiracion_mide_con_spo2_fuera_del_control_no_ofrece_guardar():
    at = _go(_start("respiracion", "hypoxia"), "respiracion", "mide")
    assert "fuera del rango de la simulación" in _texts(at)
    assert _button(at, "ruta_respiracion_mide__respiratory_lab_save_to_ups") is None


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
def _save_eeg(at, pattern="Beta (activo)"):
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
    at = _go(_start("cerebro"), "cerebro", "cierre")
    assert "todavía no guardaste su EEG" in _texts(at)
    assert at.button(key="ruta_cerebro_compose").disabled


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
    assert "Respuesta de la FC a la contracción" in text and "espera su firma" in text
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
    assert "proyección del escenario" in _texts(at)
    assert at.button(key="ruta_cerebro_compose").disabled


def test_cerebro_compone_con_la_fc_medida_en_la_estacion():
    at = _cierre_cerebro_con_fc_medida()
    assert not at.button(key="ruta_cerebro_compose").disabled
    at.button(key="ruta_cerebro_compose").click().run()
    assert at.exception == [], at.exception
    coupled = _composed(at).state.cardiovascular.get("heart_rate_acoplado")
    assert coupled is not None and coupled.provenance.name == "DERIVADO_ACOPLAMIENTO"   # «Beta (activo)»: BAR > 1.8
    assert "se aplicó" in _texts(at)


def test_cerebro_no_vuelve_a_componer_las_copias():
    at = _cierre_cerebro_con_fc_medida()
    at.button(key="ruta_cerebro_compose").click().run()
    assert at.button(key="ruta_cerebro_compose").disabled and "ya compusiste" in _texts(at)
    _button(at, "ruta_cerebro_fc__hrv_lab_save_to_ups").click().run()     # una FC nueva no basta: el BAR es la copia
    assert at.button(key="ruta_cerebro_compose").disabled and "guarda el EEG de nuevo" in _texts(at)
    assert "se aplicó" not in _texts(at)                                  # el resultado viejo no queda bajo datos nuevos


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
