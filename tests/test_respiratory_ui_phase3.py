"""Arco respiratorio, fase 3 / parte C (2026-11-07, Art. I): la UI muestra SOLO lo que tiene golden test.

Visible: FR (con su banda NEWS2), duración del ciclo, variabilidad, apneas (conteo, tiempo, tabla con tipo y
bordes declarados), tasa equivalente por hora de REGISTRO (extrapolada) y la SpO2 del modelo BIOCORE con su
procedencia. Oculto: hipopneas, I:E, patrón, notas clínicas, ODI, mixta sin marca de pendiente, categoría de
severidad, «Guardar al gemelo» e insignia de validado. La sigla del índice por hora de sueño está prohibida en el lab.
Todo corre contra una base temporal.
"""

import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from app.supermodules.respiratory_lab import views

LAB = Path("app/supermodules/respiratory_lab")
CALC_PAGE = "🧮 Calculadoras Clínicas"
PROVENANCE = "Simulación — modelo BIOCORE: Tc valor BIOCORE; r y recuperación, Howarth 2026"


@pytest.fixture
def temp_ups(tmp_path):
    from domain.physiology.state import create_patient, init_db, make_engine, make_session_factory

    engine = make_engine(Path(str(tmp_path / "resp_ui3.db")))
    init_db(engine)
    sf = make_session_factory(engine)
    with sf() as s:
        pid = create_patient(s, display_name="Paciente UI fase 3 (test)")
    return sf, pid


def _app(sf, pid, pattern=None):
    def _script():
        import app.supermodules.respiratory_lab.pages as m
        m.run()

    at = AppTest.from_function(_script, default_timeout=90)
    at.session_state["twin_shell_ups_session_factory"] = sf
    at.session_state["twin_shell_ups_patient_id"] = pid
    at.run()
    if pattern is not None:
        at.sidebar.selectbox[0].select(pattern).run()
    return at


def _text(at):
    parts = []
    for tree in (at, at.sidebar):
        for coll in (tree.markdown, tree.caption, tree.info, tree.warning, tree.success, tree.error, tree.header, tree.subheader):
            parts.extend(str(e.value) for e in coll)
    parts.extend(b.label for b in at.button)
    parts.extend(t.label for t in at.tabs)
    parts.extend(n.label for n in at.sidebar.number_input)
    return "\n".join(parts)


def _cards(at):
    """{etiqueta: [valores]} de las tarjetas de métrica (markdown con <strong>etiqueta</strong>: valor)."""
    out = {}
    for m in at.markdown:
        g = re.search(r"<strong>(.*?)</strong>(?::\s*(.*?))?(?:</div>|$)", m.value, re.S)
        if g:
            out.setdefault(g.group(1), []).append(re.sub(r"<[^>]+>", " ", g.group(2) or "").strip())
    return out


# ------------------------------------------------------------------------------------- lo validado se ve
@pytest.mark.parametrize("pattern", ["Normal (Quiet Breathing)", "Apnea Central", "Apnea Obstructiva", "Cheyne-Stokes", "Respiración Atáxica"])
def test_validated_values_are_shown_without_any_not_reliable_mark(temp_ups, pattern):
    sf, pid = temp_ups
    at = _app(sf, pid, pattern)
    assert at.exception == []
    text = _text(at)
    assert "no fiable" not in text and "(no usar)" not in text and "artefacto del generador" not in text
    cards = _cards(at)
    for label in ("Frecuencia Respiratoria", "Banda NEWS2 de la FR", "Duración del ciclo", "Apneas (≥ 10 s)", "SpO2 Mínimo",
                  "SpO2 Basal", "Tiempo total de apnea",
                  "Tasa equivalente por hora de registro (extrapolada, sin valor diagnóstico)"):
        assert label in cards, label
    assert any("resp/min" in v for v in cards["Frecuencia Respiratoria"])
    assert any("NEWS2" in v for v in cards["Banda NEWS2 de la FR"])


def test_the_rate_and_its_news2_band_are_two_cards_each_with_its_own_badge_and_source(temp_ups):
    sf, pid = temp_ups
    at = _app(sf, pid)
    fr = " ".join(m.value for m in at.markdown if "<strong>Frecuencia Respiratoria</strong>" in m.value)
    band = " ".join(m.value for m in at.markdown if "<strong>Banda NEWS2 de la FR</strong>" in m.value)
    assert "15.0 resp/min" in fr and "🟣" in fr and "60 / media de los intervalos" in fr and "🟢" not in fr
    assert "dentro de 12–20 (NEWS2)" in band and "🟢" in band and "Royal College of Physicians" in band


def test_spo2_cards_carry_the_simulation_provenance(temp_ups):
    sf, pid = temp_ups
    at = _app(sf, pid, "Apnea Central")
    cards = " ".join(m.value for m in at.markdown if "SpO2" in m.value)
    assert PROVENANCE in cards
    assert any(PROVENANCE in i.value for i in at.info)
    specs = [m for m in at.sidebar.caption if PROVENANCE in m.value]
    assert specs, "el sidebar declara la procedencia de la SpO2"


def test_central_apnea_is_listed_with_type_declared_borders_and_baseline(temp_ups):
    sf, pid = temp_ups
    at = _app(sf, pid, "Apnea Central")
    rows = at.dataframe[0].value.to_dict("records")
    assert [round(r["Inicio (s)"]) for r in rows] == [40, 100] and all(r["Tipo (Criterio BIOCORE)"] == "🟣 central" for r in rows)
    assert rows[0]["Borde"] == "completo" and "recortado" in rows[1]["Borde"]       # el 2.º llega al final del registro
    assert "respiraciones previas" in rows[0]["Línea basal"] and "registro corto" in rows[0]["Línea basal"]
    obstructive = _app(sf, pid, "Apnea Obstructiva").dataframe[0].value.to_dict("records")
    assert all(r["Tipo (Criterio BIOCORE)"] == "🟣 obstructiva" for r in obstructive)


def test_cheyne_stokes_warns_that_a_short_record_is_not_evaluable(temp_ups):
    sf, pid = temp_ups
    at = _app(sf, pid, "Cheyne-Stokes")
    assert any("no es evaluable como respiración de Cheyne-Stokes" in w.value and "2 horas" in w.value for w in at.warning)
    assert not any("Cheyne-Stokes" in w.value for w in _app(sf, pid).warning)


def test_a_normal_record_says_no_apneas_without_ruling_them_out_elsewhere(temp_ups):
    sf, pid = temp_ups
    text = _text(_app(sf, pid))
    assert "No se detectaron apneas de ≥ 10 s en este registro (no descarta apneas en otros registros)" in text


# ----------------------------------------------------------------------------------------- lo oculto sigue oculto
@pytest.mark.parametrize("pattern", ["Normal (Quiet Breathing)", "Apnea Central", "Taquipnea (Breathing Fast)"])
def test_hidden_values_stay_hidden(temp_ups, pattern):
    sf, pid = temp_ups
    at = _app(sf, pid, pattern)
    text = _text(at).replace(views.EDUCATION_CITATION, "")        # el título inglés de la guía citada no es texto antiguo
    cards = _cards(at)
    for hidden in ("Ratio I:E Promedio", "Patrón respiratorio", "Severidad", "Clasificación", "Índice", "ODI", "Hipopnea"):
        assert not any(hidden in label for label in cards), hidden
    for forbidden in ("Tachypnea", "Bradypnea", "Periodic breathing", "sleep apnea", "No apneas detected", "AOS leve",
                      "Respiratory rate within normal range", "cardiology referral", "CPAP therapy consideration", "1:2 a 1:3", "Ratio I:E Normal",
                      "Índice de desaturación"):
        assert forbidden not in text, forbidden
    assert "Sigue fuera" in text and "hipopneas" in text and "relación I:E" in text


def test_the_acronym_of_the_per_sleep_hour_index_is_banned_in_the_lab(temp_ups):
    sf, pid = temp_ups
    for pattern in (None, "Apnea Central", "Cheyne-Stokes"):
        assert "AHI" not in _text(_app(sf, pid, pattern))
    for path in list(LAB.glob("*.py")) + list(Path("src/signals/respiration").glob("*.py")):
        assert "AHI" not in path.read_text(encoding="utf-8"), path


def test_there_is_no_global_validation_badge_and_the_notice_says_what_is_validated_and_what_stays_out(temp_ups):
    """Fase 4: sustituye al aviso «En corrección». Sin insignia GLOBAL (la mixta sigue pendiente); la confianza va por valor."""
    sf, pid = temp_ups
    at = _app(sf, pid)
    assert [md for md in at.main.markdown if "border-left:3px" in md.value] == []     # sin marcador de validación del módulo
    notice = " ".join(i.value for i in at.info)
    assert "Validado por fuente" in notice and "banda NEWS2" in notice and "Berry 2012" in notice
    assert "Pendiente de validación" in notice and "apnea mixta" in notice
    assert "Sigue fuera" in notice and "hipopneas" in notice and "relación I:E" in notice and "ODI" in notice
    assert "En corrección" not in _text(at) and "no lleva insignia de validado" not in notice
    assert "American Academy of Sleep Medicine" not in _text(at)


def test_pressing_every_button_but_the_explicit_save_writes_nothing_to_the_ups(temp_ups):
    from sqlalchemy import text as sql

    sf, pid = temp_ups
    for i in range(len(_app(sf, pid).button)):
        fresh = _app(sf, pid)
        if "Guardar FR y SpO₂ basal" in fresh.button[i].label:
            continue
        fresh.button[i].click().run()
        assert fresh.exception == []
    with sf() as s:
        assert s.execute(sql("select count(*) from ups_snapshots")).scalar_one() == 0


# ------------------------------------------------------------------------------------ calculadora y enlace
def test_the_lab_links_to_the_severity_calculator(temp_ups):
    sf, pid = temp_ups
    at = _app(sf, pid)
    link = next(b for b in at.button if "calculadora de severidad" in b.label)
    link.click().run()
    assert at.session_state["selected_hub"] == "Clinical Hub" and at.session_state["selected_page"] == CALC_PAGE
    from importlib import import_module

    assert CALC_PAGE in import_module("app.main").HUBS["Clinical Hub"]


def test_the_lab_never_shows_a_severity_category_for_a_minutes_long_record(temp_ups):
    sf, pid = temp_ups
    text = _text(_app(sf, pid, "Apnea Central"))
    assert "apnea del sueño leve" not in text and "apnea del sueño moderada" not in text and "apnea del sueño severa" not in text
    assert "por hora de sueño" in text and "no la muestra porque su registro dura minutos" in text


def test_the_calculator_page_shows_the_severity_with_epstein_citation():
    def _page():
        import app.supermodules.calculators.pages as m
        m.run()

    at = AppTest.from_function(_page, default_timeout=60).run()
    assert not at.exception, at.exception
    for events, hours, word in ((3, 1.0, "sin apnea"), (10, 1.0, "leve"), (30, 1.0, "moderada"), (31, 1.0, "severa")):
        n = next(x for x in at.number_input if x.key == "calc_osa_events")
        h = next(x for x in at.number_input if x.key == "calc_osa_hours")
        n.set_value(events)
        h.set_value(hours)
        at.run()
        text = " ".join(m.value for m in at.markdown)
        assert word in text, (events, hours)
    assert "Epstein" in text and "J Clin Sleep Med 2009;5(3):263" in text


# ------------------------------------------------------------------------------------------------ cuestionario
def test_the_quiz_reactivates_only_questions_answered_by_validated_values(temp_ups):
    sf, pid = temp_ups
    at = _app(sf, pid)
    quiz = next(r for r in at.radio if r.label.startswith("Seleccionar Tipo de Pregunta"))
    assert {"Frecuencia de esta señal", "Contar las apneas de esta señal"} <= set(quiz.options)
    assert "Identificar Patrón" not in quiz.options and "AHI y Severidad" not in quiz.options
    quiz.set_value("Frecuencia de esta señal").run()
    answer = next(r for r in at.radio if r.key == "resp_quiz_fr")
    assert "15" in [str(o) for o in answer.options]
    answer.set_value(15).run()
    assert any("Correcto" in s.value and "NEWS2" in s.value for s in at.success)
    next(r for r in at.radio if r.key == "resp_quiz_fr").set_value(19).run()
    assert any("FR = 60" in e.value for e in at.error)


def test_the_apnea_counting_question_takes_its_answer_from_the_detector(temp_ups):
    sf, pid = temp_ups
    at = _app(sf, pid, "Apnea Central")
    next(r for r in at.radio if r.label.startswith("Seleccionar Tipo de Pregunta")).set_value("Contar las apneas de esta señal").run()
    answer = next(r for r in at.radio if r.key == "resp_quiz_apneas")
    answer.set_value(2).run()
    assert any("Correcto" in s.value and "2 apnea" in s.value for s in at.success)
    next(r for r in at.radio if r.key == "resp_quiz_apneas").set_value(3).run()
    assert any("solo cuentan los de ≥ 10 s" in e.value for e in at.error)


def test_the_apnea_counting_answer_is_the_detector_count_which_matches_the_synchronized_annotation(temp_ups):
    """Fase 4, decisión 1: la respuesta sale de `analysis.apnea_count` (el detector) y coincide con el ground truth
    sincronizado del generador, también con la atáxica al valor por defecto (0.20 → ninguna apnea emergente)."""
    sf, pid = temp_ups
    at = _app(sf, pid, "Respiración Atáxica")
    next(r for r in at.radio if r.label.startswith("Seleccionar Tipo de Pregunta")).set_value("Contar las apneas de esta señal").run()
    truth = [e for e in at.session_state["_respiratory_lab_analysis"]["analysis"].apnea_events]
    assert truth == []                                                             # sin apneas emergentes a 0.20
    next(r for r in at.radio if r.key == "resp_quiz_apneas").set_value(0).run()
    assert any("Correcto" in s.value and "0 apnea" in s.value for s in at.success)


# ------------------------------------------------------------------------- parámetros imposibles sin st.stop()
def test_impossible_parameters_show_the_error_at_the_control_and_keep_the_other_tabs(temp_ups):
    sf, pid = temp_ups
    at = _app(sf, pid)
    next(n for n in at.sidebar.number_input if n.label == "Frecuencia Respiratoria (resp/min)").set_value(40)
    next(n for n in at.sidebar.number_input if n.label == "Tiempo Inspiración (s)").set_value(3.0)
    at.run()
    assert at.exception == []
    # el error está en la barra lateral, junto al control de inspiración/espiración
    assert any("Parámetros imposibles" in e.value and "no cabe en el ciclo" in e.value for e in at.sidebar.error)
    # y las demás pestañas se siguen dibujando (antes, st.stop() las dejaba sin dibujar)
    text = _text(at)
    assert "Vista Simulación" in text and len(at.get("plotly_chart")) >= 1
    assert any("Aún no hay un análisis disponible" in i.value for i in at.info)         # Investigación sin análisis, con aviso
    # y corregir el valor restablece la vista clínica
    next(n for n in at.sidebar.number_input if n.label == "Tiempo Inspiración (s)").set_value(1.0)
    at.run()
    assert not at.sidebar.error and "Frecuencia Respiratoria" in _cards(at)


@pytest.mark.parametrize("label,value,control_hint", [
    ("SpO2 Mínimo (%)", 95, "piso de SpO2"),      # piso (95) por debajo de la basal (98): válido
    ("Retardo circulatorio Tc (s) — Valor BIOCORE", 30.0, "Tc"),
])
def test_valid_extreme_spo2_controls_keep_working(temp_ups, label, value, control_hint):
    sf, pid = temp_ups
    at = _app(sf, pid, "Apnea Central")
    next(n for n in at.sidebar.number_input if n.label == label).set_value(value).run()
    assert at.exception == [] and not at.sidebar.error, control_hint


def test_a_floor_above_the_baseline_is_reported_at_the_spo2_controls(temp_ups):
    sf, pid = temp_ups
    at = _app(sf, pid, "Apnea Central")
    next(n for n in at.sidebar.number_input if n.label == "SpO2 Basal (%)").set_value(90).run()
    next(n for n in at.sidebar.number_input if n.label == "SpO2 Mínimo (%)").set_value(95).run()
    assert any("piso de SpO2" in e.value for e in at.sidebar.error)
    assert "Vista Simulación" in _text(at)


def test_the_tc_control_is_labeled_as_a_biocore_value_and_moves_the_response(temp_ups):
    sf, pid = temp_ups
    at = _app(sf, pid, "Apnea Central")
    tc = next(n for n in at.sidebar.number_input if n.label == "Retardo circulatorio Tc (s) — Valor BIOCORE")
    assert tc.value == 15.0 and (tc.min, tc.max) == (5.0, 30.0)
    base = at.get("plotly_chart")[1]
    tc.set_value(5.0).run()
    assert at.get("plotly_chart")[1].proto.spec != base.proto.spec
