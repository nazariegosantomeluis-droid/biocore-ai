"""Banco de NEWS2, FIRMADO por Luis el 2026-11-17 (N1–N9; D-N7: sí).

- Cada cita «t1:N — «…»» de la hoja existe literal en su línea de `teoria_citada.md`.
- El código dice lo mismo que la hoja: pregunta, opciones, respuesta correcta y explicación; cada explicación sale de
  su línea firmada (sin la clave final, en minúsculas).
- Los puntos de pulso de N4 y N5 coinciden con `clinical.calculators.news2_pulse_score`.
- La lección «NEWS2» del Quiz de la Academia registra cada respuesta en la sesión con el concepto `news2` y en la
  mejora continua con su banco.
"""
import re
from pathlib import Path

import pytest

from clinical.calculators import news2_pulse_score
from educational.quiz_bank import CONCEPT_BY_PROMPT, NEWS2_QUESTIONS

ROOT = Path(__file__).resolve().parents[1]
DOC = (ROOT / "docs/contenido/banco_preguntas_news2.md").read_text(encoding="utf-8")
T1 = (ROOT / "docs/contenido/teoria_citada.md").read_text(encoding="utf-8").splitlines()
LINE_OF = {"N1": 91, "N2": 94, "N3": 94, "N4": 35, "N5": 35, "N6": 96, "N7": 99, "N8": 100, "N9": 101}


def _sheet():
    """{ID: (pregunta, [opciones], correcta)} leído de la hoja firmada."""
    out = {}
    for block in re.split(r"(?m)^\*\*(?=N\d · )", DOC)[1:]:
        qid = block.split(" ", 1)[0]
        lines = block.splitlines()
        prompt = lines[1].strip()
        options = [re.sub(r"^- (✅ )?", "", l).strip() for l in lines if l.startswith("- ")]
        correct = next(re.sub(r"^- ✅ ", "", l).strip() for l in lines if l.startswith("- ✅"))
        out[qid] = (prompt, options[:4], correct)
    return out


def test_la_hoja_esta_firmada_con_sus_ids():
    assert "**Estado:** FIRMADO 2026-11-17 por Luis Nazariego Santome" in DOC
    assert "> Firmo todo. — Luis Nazariego Santome, 17/11/2026" in DOC
    assert "☐" not in DOC and DOC.count("☑ firmado (17-11-2026)") >= 9


def test_cada_cita_es_literal_en_su_linea_firmada():
    quotes = re.findall(r"\*Línea firmada:\* t1:(\d+) — «(.*)»$", DOC, flags=re.M)
    assert len(quotes) >= 7
    for n, text in quotes:
        assert T1[int(n) - 1] == text, n


def test_el_codigo_dice_lo_mismo_que_la_hoja_firmada():
    sheet = _sheet()
    assert len(sheet) == len(NEWS2_QUESTIONS) == 9
    by_prompt = {q.prompt: q for q in NEWS2_QUESTIONS}
    for qid, (prompt, options, correct) in sheet.items():
        q = by_prompt[prompt]
        assert sorted(q.choices) == sorted(options), qid
        assert q.choices[q.answer] == correct, qid
        assert CONCEPT_BY_PROMPT[prompt] == "news2", qid


@pytest.mark.parametrize("qid", sorted(LINE_OF))
def test_cada_explicacion_sale_de_su_linea_firmada(qid):
    prompt = _sheet()[qid][0]
    q = next(x for x in NEWS2_QUESTIONS if x.prompt == prompt)
    core = q.explanation.replace(" [RCP2017]", "").rstrip(".").lower()
    assert core in T1[LINE_OF[qid] - 1].lower(), qid
    assert q.source.startswith("[RCP2017]")


def test_los_puntos_de_pulso_coinciden_con_el_codigo():
    assert news2_pulse_score(120) == 2 and "2 puntos (tramo de 111 a 130 lpm)" in DOC
    assert news2_pulse_score(45) == 1 and "1 punto (tramo de 41 a 50 lpm)" in DOC


def test_la_leccion_registra_en_la_sesion_y_en_la_mejora_continua(monkeypatch):
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest
    import educational.learning_analytics as LA

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    before = len(LA.load_answers(bank="news2"))
    at = AppTest.from_file(str(ROOT / "app/main.py"), default_timeout=180)
    at.session_state["biocore_start_page"] = "quiz"
    at.run()
    at.selectbox(key="academia_lesson").set_value("NEWS2")
    at.radio(key="academia_level").set_value("advanced")
    at.button(key="academia_start_quiz").click().run()
    questions = at.session_state["academia_quiz"]["questions"]
    assert len(questions) == 9
    for i in range(len(questions)):
        q = questions[i]
        at.radio(key=f"academia_quiz_choice_{i}").set_value(q.correct_choice if i % 2 == 0 else q.choices[1])
        at.radio(key=f"academia_quiz_confidence_{i}").set_value(75).run()
        at.button(key=f"academia_quiz_submit_{i}").click().run()
        assert at.exception == [], at.exception
        at.button(key=f"academia_quiz_next_{i}").click().run()
    log = at.session_state["session_learning_log"]
    assert len(log) == 9 and {e["concept"] for e in log} == {"news2"} and {e["source"] for e in log} == {"quiz"}
    assert [e["correct"] for e in log] == [i % 2 == 0 for i in range(9)]
    assert len(LA.load_answers(bank="news2")) - before == 9


def test_en_el_codigo_estan_exactamente_los_ids_firmados():
    src = (ROOT / "educational/quiz_bank.py").read_text(encoding="utf-8")
    ids = re.findall(r"QuizQuestion\(\s*#\s*(N\d+) ·", src)
    assert ids == [f"N{i}" for i in range(1, 10)]
