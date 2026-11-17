"""Hemodinámica (2026-11-17): teoría firmada (`teoria_citada_3.md`) y banco G1–G10, FIRMADOS por Luis con la condición
«que salga de referencias verídicas».

- La teoría está firmada, cada afirmación lleva una clave y cada clave está en su bibliografía con su registro.
- Cada cita «t3:N — «…»» de la hoja del banco existe literal en su línea; cada explicación sale de su línea.
- El código dice lo mismo que la hoja; los dos cálculos (PAM 110/80 y gasto 70 × 70) son correctos.
- La lección «Hemodinámica» registra en la sesión con el concepto `hemodinamica` y en la mejora continua con su banco.
- En ninguna pregunta la correcta es la opción más larga.
"""
import re
from pathlib import Path

import pytest

from educational.quiz_bank import CONCEPT_BY_PROMPT, HEMO_QUESTIONS

ROOT = Path(__file__).resolve().parents[1]
THEORY = (ROOT / "docs/contenido/teoria_citada_3.md").read_text(encoding="utf-8")
T3 = THEORY.splitlines()
DOC = (ROOT / "docs/contenido/banco_preguntas_hemodinamica.md").read_text(encoding="utf-8")


def test_la_teoria_esta_firmada_y_cada_clave_tiene_su_referencia():
    assert T3[2].startswith("**Estado:** FIRMADO 2026-11-17 por Luis Nazariego Santome")
    body, biblio = THEORY.split("## Bibliografía", 1)
    keys = set(re.findall(r"\[([A-Z]{2}\d{4})\]", body))
    assert keys == {"DW2019", "ME2000", "JO2024", "MY2003", "SQ2015"}
    for k in keys:
        assert re.search(rf"\*\*\[{k}\]\*\* .+\[Registro\]\(https://consensus\.app/papers/details/", biblio), k
    clinical = body.split("## 4. Qué modela BIOCORE", 1)[0]   # el tema 4 describe el modelo, no es texto clínico
    for line in clinical.splitlines():                   # toda afirmación de los temas 1–3 lleva su clave
        if line.startswith(("**Idea.**", "- ")):
            assert re.search(r"\[[A-Z]{2}\d{4}\]", line), line


def _sheet():
    out = {}
    for block in re.split(r"(?m)^\*\*(?=G\d+ · )", DOC)[1:]:
        qid = block.split(" ", 1)[0]
        lines = block.splitlines()
        options = [re.sub(r"^- (✅ )?", "", l).strip() for l in lines if l.startswith("- ")]
        correct = next(re.sub(r"^- ✅ ", "", l).strip() for l in lines if l.startswith("- ✅"))
        line_no = int(re.search(r"\*Línea firmada:\* t3:(\d+)", block).group(1))
        out[qid] = (lines[1].strip(), options[:4], correct, line_no)
    return out


def test_la_hoja_esta_firmada_y_cada_cita_es_literal():
    assert "**Estado:** FIRMADO 2026-11-17 por Luis Nazariego Santome" in DOC and "☐" not in DOC
    quotes = re.findall(r"\*Línea firmada:\* t3:(\d+) — «(.*)»$", DOC, flags=re.M)
    assert len(quotes) == 10
    for n, text in quotes:
        assert T3[int(n) - 1] == text, n


def test_el_codigo_dice_lo_mismo_que_la_hoja_y_la_explicacion_sale_de_su_linea():
    sheet = _sheet()
    assert len(sheet) == len(HEMO_QUESTIONS) == 10
    by_prompt = {q.prompt: q for q in HEMO_QUESTIONS}
    for qid, (prompt, options, correct, n) in sheet.items():
        q = by_prompt[prompt]
        assert sorted(q.choices) == sorted(options) and q.choices[q.answer] == correct, qid
        assert CONCEPT_BY_PROMPT[prompt] == "hemodinamica", qid
        core = re.sub(r" \[[A-Z]{2}\d{4}\]\.$", "", q.explanation).lower()
        assert core in T3[n - 1].lower(), qid
        assert q.source.startswith("[") and q.source[1:7] in q.explanation


def test_los_calculos_son_correctos():
    sistolica, diastolica = 110, 80
    assert diastolica + (sistolica - diastolica) / 3 == 90
    assert 70 * 70 / 1000 == 4.9
    by_prompt = {q.prompt: q for q in HEMO_QUESTIONS}
    assert any(q.choices[q.answer] == "90 mmHg" for q in by_prompt.values())
    assert any(q.choices[q.answer] == "4.9 L/min" for q in by_prompt.values())


def test_la_correcta_no_es_la_opcion_mas_larga():
    for q in HEMO_QUESTIONS:
        assert max(q.choices, key=len) != q.choices[q.answer], q.prompt


def test_en_el_codigo_estan_exactamente_los_ids_firmados():
    src = (ROOT / "educational/quiz_bank.py").read_text(encoding="utf-8")
    assert re.findall(r"QuizQuestion\(\s*#\s*(G\d+) ·", src) == [f"G{i}" for i in range(1, 11)]


def test_la_leccion_registra_en_la_sesion_y_en_la_mejora_continua(monkeypatch):
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest
    import educational.learning_analytics as LA

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    before = len(LA.load_answers(bank="hemodinamica"))
    at = AppTest.from_file(str(ROOT / "app/main.py"), default_timeout=180)
    at.session_state["biocore_start_page"] = "quiz"
    at.run()
    at.selectbox(key="academia_lesson").set_value("Hemodinámica")
    at.radio(key="academia_level").set_value("advanced")
    at.button(key="academia_start_quiz").click().run()
    questions = at.session_state["academia_quiz"]["questions"]
    assert len(questions) == 10
    for i in range(len(questions)):
        q = questions[i]
        at.radio(key=f"academia_quiz_choice_{i}").set_value(q.correct_choice if i % 2 == 0 else q.choices[1])
        at.radio(key=f"academia_quiz_confidence_{i}").set_value(75).run()
        at.button(key=f"academia_quiz_submit_{i}").click().run()
        assert at.exception == [], at.exception
        at.button(key=f"academia_quiz_next_{i}").click().run()
    log = at.session_state["session_learning_log"]
    assert len(log) == 10 and {e["concept"] for e in log} == {"hemodinamica"}
    assert len(LA.load_answers(bank="hemodinamica")) - before == 10


def test_la_bibliografia_muestra_las_cinco_referencias_de_hemodinamica():
    from streamlit.testing.v1 import AppTest
    from app.supermodules.bibliography import HEMO_KEYS

    assert set(HEMO_KEYS) == {"DW2019", "ME2000", "JO2024", "MY2003", "SQ2015"}
    at = AppTest.from_file(str(ROOT / "app/main.py"), default_timeout=180)
    at.session_state["biocore_start_page"] = "bibliografia"
    at.run()
    assert at.exception == []
    text = " ".join(m.value for m in at.markdown)
    for key in HEMO_KEYS:
        assert f"**[{key}]**" in text, key
