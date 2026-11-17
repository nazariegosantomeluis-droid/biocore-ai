"""Rediseño Duolingo + Apple (2026-11-17): Inicio como tablero, «Temas» como ficha de producto y «Comparar pacientes».

- El catálogo solo enlaza contenido que existe: temas firmados, preguntas con fuente, páginas del menú, conceptos de la
  sesión.
- El comparativo arma sus filas del UPS con la procedencia de cada valor y dice «Sin dato» donde falta.
- El quiz del tema registra en la sesión con la confianza declarada o sin ella (nunca un valor por defecto).
- Una calculadora vacía no calcula.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from streamlit.testing.v1 import AppTest

from app.supermodules import ui_catalog as C
from app.supermodules import ui_compare as CMP
from app.utils.session_learning import CONCEPTS
from domain.physiology.state.schema import Provenance

MAIN = str(Path("app/main.py").resolve())


def test_catalog_points_only_to_existing_content():
    import app.main as m

    urls = {u for _, u, *_ in m._page_specs()}
    for topic in C.TOPICS:
        assert topic.concept is None or topic.concept in CONCEPTS, topic.key
        assert topic.organ in C.ORGAN_BY_KEY and (topic.lab is None or topic.lab in urls)
        assert topic.theory.idea, topic.key
        for q in C.quiz_questions(topic):
            assert q.source, (topic.key, q.prompt)
    for organ, nodes in C.PATHS.items():
        assert organ in C.ORGAN_BY_KEY
        for _label, kind, target in nodes:
            assert (target in C.TOPIC_BY_KEY) if kind == "tema" else (target in urls), target


@dataclass
class _D:
    value: float
    unit: str
    provenance: Provenance
    source_detail: str = ""


@dataclass
class _Domain:
    descriptors: dict = field(default_factory=dict)


class _State:
    def __init__(self, **cv):
        self._d = {"cardiovascular": _Domain(cv), "respiratory": _Domain(), "neurological": _Domain(),
                   "muscular": _Domain()}

    def all_domains(self):
        return self._d


def test_compare_rows_show_each_value_with_its_provenance_and_no_data_where_missing():
    a = _State(heart_rate=_D(72, "bpm", Provenance.SIMULACION))
    b = _State(heart_rate=_D(118, "bpm", Provenance.SENSOR_REAL), hr_rr_ratio=_D(4.1, "", Provenance.DERIVADO))
    rows = CMP.compare_rows([a, b, None])
    assert rows == [
        ("Cardiovascular", "Frecuencia cardiaca", ["72.0 lpm · Simulación", "118.0 lpm · Sensor real", "Sin dato"]),
        ("Cardiovascular", "Razón FC:FR", ["Sin dato", "4.1  · Derivado", "Sin dato"]),
    ]
    assert CMP.compare_rows([None, None, None]) == []


def test_default_columns_compare_the_active_patient_in_time():
    options = [("s3", "p1", "c"), ("s2", "p2", "b"), ("s1", "p1", "a")]
    assert CMP.default_columns(options, "p1") == ["s3", "s1", CMP.NONE_OPTION]
    assert CMP.default_columns(options, None) == ["s3", "s2", CMP.NONE_OPTION]
    assert CMP.default_columns([], None) == [CMP.NONE_OPTION] * 3


def _open(url: str, **state) -> AppTest:
    at = AppTest.from_file(MAIN, default_timeout=240)
    at.session_state["biocore_start_page"] = url
    for k, v in state.items():
        at.session_state[k] = v
    at.run()
    assert at.exception == [], (url, at.exception)
    return at


def test_home_is_the_dashboard_with_monitoring_organs_and_three_doors():
    at = _open("inicio")
    text = " ".join(m.value for m in at.main.markdown)
    assert "Monitoreo del paciente activo" in text and "Equivócate aquí." in text
    assert all(f"### {door}" in text for door in ("Aprender", "Practicar", "Clinical Hub"))
    assert at.main.get("button_group"), "el selector de órganos (st.pills)"


def test_topic_quiz_logs_to_the_session_without_inventing_confidence():
    q = C.quiz_questions(C.TOPIC_BY_KEY["fc"])[0]
    at = _open("temas", **{C.SELECTED_TOPIC_KEY: "fc", "bc_slide_fc": "Quiz final"})
    at.radio(key="bc_q_fc_0_choice").set_value(q.correct_choice)
    at.run()
    at.button(key="bc_q_fc_0_check").click()
    at.run()
    assert at.exception == []
    log = at.session_state["session_learning_log"]
    assert len(log) == 1 and log[0]["concept"] == "frecuencia_cardiaca" and log[0]["correct"] is True
    assert log[0]["confidence"] is None and log[0]["source"] == "quiz"
    assert any(m.value.startswith("**Correcto.**") for m in at.main.markdown)


def test_an_empty_calculator_calculates_nothing():
    at = _open("temas", **{C.SELECTED_TOPIC_KEY: "fc"})
    cards = [m.value for m in at.main.markdown if 'data-label="Frecuencia cardiaca"' in m.value]
    assert cards == []
    at.number_input(key="bc_calc_rr").set_value(800.0)
    at.run()
    assert any('data-value="75 lpm"' in m.value for m in at.main.markdown)


def test_compare_page_renders():
    _open("comparar")
