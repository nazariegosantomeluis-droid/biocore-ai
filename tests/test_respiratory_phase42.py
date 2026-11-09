"""Arco respiratorio, tanda 4.2 (higiene final de citas, 2026-11-09, Art. I).

Regla firmada: lo que no tiene fuente, fuera. Cada cifra del lab se contrasta SOLO con las fuentes verificadas con texto
completo (Berry 2012, Epstein 2009, NEWS2 vía PMC8244393): si la sostienen se queda ajustada a su texto y con cita; si no,
se retira o se reescribe. Aquí no se toca ninguna señal. Todo contra una base temporal.
"""

import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from clinical.calculators import _news2_spo2_scale1, news2_respiratory_rate_score
from src.signals.respiration import RespiratoryAnalyzer, RespiratoryPattern, RespiratorySignalGenerator

LAB = Path("app/supermodules/respiratory_lab")
FS = 100

# Cifras y afirmaciones retiradas: ninguna de las tres fuentes las sostiene (o la contradice: prevalencia 10-30 %).
RETIRED = (
    "10-30", "10–30", "80% casos", "80 % de los casos", "3-4x", "3–4x", "Gold Standard", "400-600", "0.4-0.6 L",
    ">20 resp/min", "<12 resp/min", "IMC >30", "SpO2 Normal", ">95%", "Sudoración", "Muerte Súbita", "bradicardia vagal",
    "Bradicardia vagal", "fiebre, ansiedad", "depresión SNC", "Depresión SNC", "Estrés, fiebre", "Rango normal",
    "Regular, rítmico", "ahora la OBESIDAD", "↑ Simpático", "Parkinson-",
)


@pytest.fixture
def temp_ups(tmp_path):
    from domain.physiology.state import create_patient, init_db, make_engine, make_session_factory

    engine = make_engine(Path(str(tmp_path / "resp_42.db")))
    init_db(engine)
    sf = make_session_factory(engine)
    with sf() as s:
        pid = create_patient(s, display_name="Paciente 4.2 (test)")
    return sf, pid


def _app(sf, pid):
    def _script():
        import app.supermodules.respiratory_lab.pages as m
        m.run()

    at = AppTest.from_function(_script, default_timeout=90)
    at.session_state["twin_shell_ups_session_factory"] = sf
    at.session_state["twin_shell_ups_patient_id"] = pid
    at.run()
    return at


def _text(at):
    parts = []
    for tree in (at, at.sidebar):
        for coll in (tree.markdown, tree.caption, tree.info, tree.warning, tree.success, tree.error, tree.header, tree.subheader):
            parts.extend(str(e.value) for e in coll)
        parts.extend(str(n.help) for n in tree.number_input)
    return " ".join(" ".join(parts).split())


def _all_ui_text(sf, pid):
    """Texto de la página con cada tema educativo de la barra lateral y cada pregunta del cuestionario abiertos."""
    at = _app(sf, pid)
    out = [_text(at)]
    for topic in at.sidebar.radio(key="edu_sidebar").options:
        at.sidebar.radio(key="edu_sidebar").set_value(topic).run()
        out.append(_text(at))
    quiz = next(r for r in at.radio if r.label.startswith("Seleccionar Tipo de Pregunta"))
    for option in quiz.options:
        next(r for r in at.radio if r.label.startswith("Seleccionar Tipo de Pregunta")).set_value(option).run()
        out.append(_text(at))
    return " ".join(out)


# ------------------------------------------------------------------------------ lo retirado ya no está
def test_the_unsourced_figures_are_gone_from_every_screen_and_the_source(temp_ups):
    sf, pid = temp_ups
    text = _all_ui_text(sf, pid)
    for gone in RETIRED:
        assert gone not in text, gone
    for path in LAB.glob("*.py"):
        src = path.read_text(encoding="utf-8")
        for gone in ("10-30% adultos", "No diagnosticada:** 80", "↑ CV 3-4x", "**Gold Standard:**", "Volumen Corriente:** 400-600",
                     "Taquipnea:** >20", "Bradipnea:** <12", "Obesidad (IMC >30)"):
            assert gone not in src, (path.name, gone)


def test_tachypnea_and_bradypnea_are_no_longer_diagnostic_labels_with_numbers(temp_ups):
    sf, pid = temp_ups
    text = _all_ui_text(sf, pid)
    assert "fuera de 12–20 (NEWS2)" in text
    assert not re.search(r"(Taquipnea|Bradipnea)[^<>]{0,12}[<>]\s?\d", text)


# ------------------------------------------------------------------------------ lo que se queda dice lo que dice la fuente
def test_news2_points_written_in_the_lab_are_exactly_the_calculator_tables(temp_ups):
    """La tabla que el lab escribe (FR y SpO2 escala 1) se contrasta con las funciones que ya implementan NEWS2."""
    for rr, pts in ((6, 3), (8, 3), (9, 1), (11, 1), (12, 0), (20, 0), (21, 2), (24, 2), (25, 3), (40, 3)):
        assert news2_respiratory_rate_score(rr) == pts
    for spo2, pts in ((100, 0), (96, 0), (95, 1), (94, 1), (93, 2), (92, 2), (91, 3), (85, 3)):
        assert _news2_spo2_scale1(spo2) == pts
    sf, pid = temp_ups
    text = _text(_app(sf, pid))
    assert "**12–20 resp/min: 0**" in text and "9–11: 1" in text and "21–24: 2" in text and "≤ 8: 3" in text and "≥ 25: 3" in text
    assert "**≥ 96 %: 0**" in text and "94–95: 1" in text and "92–93: 2" in text and "≤ 91: 3" in text
    assert "Royal College of Physicians" in text and "12–20 resp/min puntúa 0 en NEWS2" in text


def test_prevalence_is_aligned_with_epstein_and_the_education_texts_say_what_the_guidelines_say(temp_ups):
    sf, pid = temp_ups
    at = _app(sf, pid)
    at.sidebar.radio(key="edu_sidebar").set_value("Apnea del Sueño").run()
    text = _text(at)
    assert "Prevalencia:** al menos 2–4 % de la población adulta" in text and "Epstein 2009" in text
    for symptom in ("Apneas presenciadas", "Ronquido", "Ahogo o asfixia nocturnos", "Somnolencia excesiva"):
        assert symptom in text
    assert "polisomnografía en laboratorio y monitores portátiles" in text and "Gold Standard" not in text
    at.sidebar.radio(key="edu_sidebar").set_value("Patrones Clínicos").run()
    text = _text(at)
    assert "≥ 3 apneas/hipopneas centrales consecutivas con ciclo ≥ 40 s" in text and "insuficiencia cardíaca congestiva no reconocida" in text
    full = _all_ui_text(sf, pid)
    assert "Caída ≥ 90 %" in full.capitalize() or "caída ≥ 90 % de la excursión del flujo respecto a la línea basal previa durante ≥ 10 s" in full


# ------------------------------------------------------------------------------ cuestionario reescrito a la fuente
def _quiz(at, option):
    next(r for r in at.radio if r.label.startswith("Seleccionar Tipo de Pregunta")).set_value(option).run()


def test_the_risk_factor_quiz_asks_what_the_epstein_table_says(temp_ups):
    sf, pid = temp_ups
    at = _app(sf, pid)
    _quiz(at, "Factores de Riesgo")
    assert any("Epstein 2009" in i.value and "ALTO RIESGO" in i.value for i in at.info)
    answers = [r for r in at.radio if r.label == "Tu respuesta:"][0]
    right = next(o for o in answers.options if o.startswith("✓"))
    answers.set_value(right).run()
    ok = " ".join(s.value for s in at.success)
    for item in ("obesidad (IMC > 35)", "fibrilación auricular", "hipertensión refractaria", "diabetes tipo 2", "disritmias nocturnas"):
        assert item in ok, item
    [r for r in at.radio if r.label == "Tu respuesta:"][0].set_value("Una persona sana que viaja como pasajera").run()
    assert any("no figura en la lista de alto riesgo" in e.value for e in at.error)
    assert "MODIFICABLE" not in _text(at) and "más efectivo en la mayoría" not in _text(at)


def test_the_cardiovascular_quiz_no_longer_asserts_bradycardia_or_st_changes(temp_ups):
    sf, pid = temp_ups
    at = _app(sf, pid)
    quiz = next(r for r in at.radio if r.label.startswith("Seleccionar Tipo de Pregunta"))
    assert "Correlación cardiovascular (guía AASM)" in quiz.options and "Correlación ECG-Respiratoria" not in quiz.options
    _quiz(at, "Correlación cardiovascular (guía AASM)")
    answers = [r for r in at.radio if r.label == "Tu respuesta:"][0]
    right = next(o for o in answers.options if o.startswith("✓"))
    assert "Fibrilación auricular y disritmias nocturnas" in right
    answers.set_value(right).run()
    ok = " ".join(s.value for s in at.success)
    assert "lista de alto riesgo de la guía" in ok and "Berry 2012" in ok and "sin insuficiencia cardíaca declarada" in ok
    text = _text(at)
    for gone in ("Bradicardia, potencial aumento", "cambios ST", "hipoxia crónica causa bradicardia"):
        assert gone not in text, gone


# ------------------------------------------------------------------------------ las dos marcas ya no comparten nombre
def test_the_two_marks_have_different_names_and_meanings():
    gen = RespiratorySignalGenerator(FS).generate_respiration(
        duration=300, seed=22, params=RespiratoryPattern(respiratory_rate=8, pattern_type="ataxic", irregularity=0.40))
    truth = gen["ground_truth"]["events"]
    assert truth and all("near_threshold" in e and "borderline" not in e and "gradual_edge" not in e for e in truth)
    a = RespiratoryAnalyzer(FS).analyze_respiration(gen["airflow"], gen["time"], gen["spo2"], gen["chest_wall"])
    assert a.apnea_events and all("gradual_edge" in e and "borderline" not in e and "near_threshold" not in e for e in a.apnea_events)
    for path in list(LAB.glob("*.py")) + list(Path("src/signals/respiration").glob("*.py")):
        assert "borderline" not in path.read_text(encoding="utf-8").lower(), path.name


def test_the_u_help_says_what_it_means_and_why_it_can_be_large():
    def _script():
        from app.supermodules.respiratory_lab import views as _v
        from src.signals.respiration import RespiratoryAnalyzer as _A, RespiratoryPattern as _P, RespiratorySignalGenerator as _G

        d = _G(100).generate_respiration(
            duration=360, seed=0, params=_P(respiratory_rate=8, pattern_type="cheyne_stokes", cheyne_stokes_cycle=90.0))
        _v.render_events_table(_A(100).analyze_respiration(d["airflow"], d["time"], d["spo2"], d["chest_wall"]))

    at = AppTest.from_function(_script, default_timeout=60).run()
    caps = " ".join(c.value for c in at.caption)
    assert "≈ X s, borde gradual ± U s" in caps
    for piece in ("cuánto cambia la duración del evento", "un 2 %", "p95 medido", "Puede ser grande en un borde gradual",
                  "cruza el 10 % de la basal muy despacio", "No es un número preciso"):
        assert piece in caps, piece
