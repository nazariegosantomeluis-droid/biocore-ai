"""Arco respiratorio, tanda 4.3 (cierre total del texto clínico, 2026-11-11, Art. I).

Regla firmada: lo que no tiene fuente, fuera. Esta prueba RECORRE todo el texto visible del lab (los 7 patrones, los 4 temas
de la barra lateral, los 5 cuestionarios con cada opción y su explicación, ayudas de los controles) y exige que ningún
elemento con vocabulario clínico quede sin fuente ni etiqueta: cada uno debe llevar una cita (Berry 2012, Epstein 2009,
NEWS2/RCP 2017) o una etiqueta (Criterio BIOCORE, HEURISTIC, descripción de la simulación). Todo contra una base temporal.
"""

import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

LAB = Path("app/supermodules/respiratory_lab")

# Vocabulario clínico: cualquier elemento visible que lo use debe llevar fuente o etiqueta.
CLINICAL_TERMS = (
    "insuficiencia", "hipertensión", "diabetes", "acv", "accidente cerebrovascular", "infarto", "fibrilación", "disritmia",
    "arritmia", "parkinson", "niñ", "pediátric", "obesidad", "obeso", "sexo", "bradicardia", "taquicardia", "saludable",
    "tratamiento", "cpap", "prevalencia", "pronóstico", "diagnóstic", "cirugía", "enfermedad", "lesión", "fiebre",
    "ansiedad", "fármaco", "cor pulmonale", "polisomnograf", "hipoxemia", "hipercapnia", "apnea obstructiva del sueño",
    "ronquido", "somnolencia",
)
SOURCE_OR_LABEL = (
    "berry", "epstein", "news2", "rcp", "aasm", "criterio biocore", "biocore", "heurístic", "heuristic", "simulación",
    "simulada", "simulado", "simulados", "fuente:",
)


@pytest.fixture(scope="module")
def lab_texts(tmp_path_factory):
    """{texto: contexto} de TODO lo que el lab muestra, recorriendo patrones, temas, cuestionarios y sus opciones."""
    from domain.physiology.state import create_patient, init_db, make_engine, make_session_factory

    engine = make_engine(tmp_path_factory.mktemp("resp43") / "audit.db")
    init_db(engine)
    sf = make_session_factory(engine)
    with sf() as s:
        pid = create_patient(s, display_name="auditoría 4.3")

    def _script():
        import app.supermodules.respiratory_lab.pages as m
        m.run()

    seen = {}

    def collect(at, ctx):
        for tree in (at, at.sidebar):
            for name in ("markdown", "caption", "info", "warning", "success", "error", "header", "subheader"):
                for e in getattr(tree, name):
                    v = " ".join(re.sub(r"<[^>]+>", " ", str(e.value)).split())
                    if v:
                        seen.setdefault(v, ctx)
            for n in tree.number_input:
                for v in (n.label, str(n.help or "")):
                    v = " ".join(v.split())
                    if v:
                        seen.setdefault(v, ctx + "/control")
            for b in tree.button:
                seen.setdefault(" ".join(b.label.split()), ctx + "/botón")

    at = AppTest.from_function(_script, default_timeout=120)
    at.session_state["twin_shell_ups_session_factory"] = sf
    at.session_state["twin_shell_ups_patient_id"] = pid
    at.run()
    for pattern in list(at.sidebar.selectbox[0].options):
        at.sidebar.selectbox[0].select(pattern).run()
        collect(at, pattern)
        topics = at.sidebar.radio(key="edu_sidebar").options
        for topic in topics:
            at.sidebar.radio(key="edu_sidebar").set_value(topic).run()
            collect(at, f"{pattern}/{topic}")
        at.sidebar.radio(key="edu_sidebar").set_value(topics[0]).run()
        quiz_options = next(r for r in at.radio if r.label.startswith("Seleccionar Tipo de Pregunta")).options
        for opt in quiz_options:
            next(r for r in at.radio if r.label.startswith("Seleccionar Tipo de Pregunta")).set_value(opt).run()
            collect(at, f"{pattern}/quiz:{opt}")
            answers = [r for r in at.radio if r.key not in ("edu_sidebar",) and not r.label.startswith("Seleccionar")]
            if not answers:
                continue
            for o in list(answers[0].options):
                [r for r in at.radio if r.key not in ("edu_sidebar",) and not r.label.startswith("Seleccionar")][0].set_value(o).run()
                collect(at, f"{pattern}/quiz:{opt}/{o}")
        next(r for r in at.radio if r.label.startswith("Seleccionar Tipo de Pregunta")).set_value(quiz_options[0]).run()
    assert at.exception == []
    return seen


def test_every_visible_element_with_clinical_vocabulary_carries_a_source_or_a_label(lab_texts):
    assert len(lab_texts) > 120                                              # se recorrió todo, no una parte
    bad = []
    for text, ctx in lab_texts.items():
        # las negaciones («no es un diagnóstico», «sin valor diagnóstico») son avisos, no afirmaciones
        low = re.sub(r"no (es|son) un diagnóstico|sin valor diagnóstico|valor diagnóstico", "", text.lower())
        terms = [t for t in CLINICAL_TERMS if t in low]
        if terms and not any(m in low for m in SOURCE_OR_LABEL):
            bad.append((ctx, terms, text[:140]))
    assert not bad, bad


def test_the_children_claim_is_gone_everywhere(lab_texts):
    blob = " ".join(lab_texts).lower()
    for gone in ("más común en niños", "mas comun en niños", "niños", "pediátric"):
        assert gone not in blob, gone
    for path in LAB.glob("*.py"):
        assert "más común en niños" not in path.read_text(encoding="utf-8"), path


def test_the_other_unsourced_residuals_are_gone(lab_texts):
    blob = " ".join(lab_texts)
    for gone in ("Parkinson", "sexo masculino", "lesión tronco", "lesión de tronco", "Factor de riesgo: obesidad, edad",
                 "oxigenación saludable", "respiración estable", "intercambio gaseoso", "Entrada de O₂", "Salida de CO₂",
                 "Oclusión de vía aérea superior", "Asociada a: insuficiencia cardíaca"):
        assert gone not in blob, gone


# ----------------------------------------------------------------------------------------------- quiz reescrito
def _app(tmp_path):
    from domain.physiology.state import create_patient, init_db, make_engine, make_session_factory

    engine = make_engine(tmp_path / "quiz43.db")
    init_db(engine)
    sf = make_session_factory(engine)
    with sf() as s:
        pid = create_patient(s, display_name="quiz 4.3")

    def _script():
        import app.supermodules.respiratory_lab.pages as m
        m.run()

    at = AppTest.from_function(_script, default_timeout=90)
    at.session_state["twin_shell_ups_session_factory"] = sf
    at.session_state["twin_shell_ups_patient_id"] = pid
    at.run()
    return at


def test_the_differentiation_quiz_answer_comes_from_berry_and_the_wrong_options_are_refuted_by_berry(tmp_path):
    at = _app(tmp_path)
    next(r for r in at.radio if r.label.startswith("Seleccionar Tipo de Pregunta")).set_value("Diferenciación Apnea").run()
    q = " ".join(i.value for i in at.info)
    assert "Según Berry 2012 (AASM)" in q and "obstructiva, mixta o central" in q
    answers = [r for r in at.radio if r.label == "Tu respuesta:"][0]
    options = list(answers.options)
    # 2026-11-14: sin «✓» que delate la correcta, sin opción elegida de inicio
    right = "En el esfuerzo respiratorio"
    assert len(options) == 3 and right in options and not any(o.startswith("✓") for o in options)
    assert answers.value is None
    answers.set_value(right).run()
    ok = " ".join(s.value for s in at.success)
    assert "Berry 2012 (§4.1.1)" in ok and "esfuerzo respiratorio" in ok and "Criterio BIOCORE" in ok and "PENDING_VALIDATION" in ok
    for wrong in [o for o in options if o != right]:
        [r for r in at.radio if r.label == "Tu respuesta:"][0].set_value(wrong).run()
        err = " ".join(e.value for e in at.error)
        # la regla de apnea es la misma para todas (Berry 2012) y ≥ 30 % es el criterio de HIPOPNEA, no de apnea
        assert "caída ≥ 90 %" in err and "≥ 10 s" in err and "Berry 2012" in err and "hipopnea" in err
        assert "esfuerzo respiratorio" in err
    # las opciones incorrectas no inventan ninguna afirmación clínica: hablan de duración y de caída del flujo
    assert "niños" not in " ".join(options)


def test_references_classify_the_apnea_by_effort_with_labels_and_no_unsourced_associations(tmp_path):
    at = _app(tmp_path)
    text = " ".join(" ".join(m.value for m in at.markdown).split())
    assert "se basa en el esfuerzo respiratorio" in text and "§4.1.1" in text
    assert "Central (Criterio BIOCORE)" in text and "Obstructiva (Criterio BIOCORE)" in text
    assert "se observa a menudo durante una apnea u hipopnea obstructiva" in text            # Berry 2012 (RIP)
    assert "resultado directo del colapso repetitivo de la vía aérea superior" in text         # Epstein 2009
    assert "Atáxica (descripción de la simulación)" in text and "no hay afirmación clínica sobre su causa" in text
    assert "Normal (simulación)" in text and "Apnea (simulación)" in text and "Taquipnea / Bradipnea (simulación)" in text
