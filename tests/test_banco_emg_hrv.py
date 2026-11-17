"""Bancos de EMG (E1–E10) y HRV (H1–H8), firmados por Luis el 2026-11-17 (bloque de firma del 17-11-2026), y la privacidad de
«Pregunta a BIOCORE».

- Cada pregunta en código coincide letra por letra con la hoja de firma v2 (E1, firmada «tal cual», con su versión v2 del
  banco), y con el documento firmado `docs/contenido/banco_preguntas_emg_hrv.md`.
- Cada explicación es una subcadena de su línea t2:N de `teoria_citada_2.md` (E1 conserva la explicación v2 firmada tal
  cual; H4 se corta antes de la segunda mención de «la razón LF/HF»).
- Ningún ID fuera de E1–E10/H1–H8 está en código; los dos bancos van dentro de `balance_positions`; la correcta es la
  más larga en como máximo el 40 % de cada banco.
- Las 18 se registran en la sesión con `emg`/`hrv` (y en la mejora continua con su banco).
- «Pregunta a BIOCORE» no guarda la pregunta ni la respuesta en ninguna base, y el aviso P2 está a la vista.
"""
import ast
import re
from pathlib import Path

import pytest

from educational import quiz_bank as QB

ROOT = Path(__file__).resolve().parents[1]
HOJA = (ROOT / "docs/contenido/hoja_firma_banco_emg_hrv_v2.md").read_text(encoding="utf-8").replace("\r", "")
BANCO = (ROOT / "docs/contenido/banco_preguntas_emg_hrv.md").read_text(encoding="utf-8").replace("\r", "")
T2 = (ROOT / "docs/contenido/teoria_citada_2.md").read_text(encoding="utf-8").replace("\r", "").split("\n")
SIGNED_IDS = [f"E{i}" for i in range(1, 11)] + [f"H{i}" for i in range(1, 9)]
BANK = {f"E{i}": q for i, q in enumerate(QB.EMG_QUESTIONS, start=1)} | {f"H{i}": q for i, q in
                                                                        enumerate(QB.HRV_QUESTIONS, start=1)}


def _hoja(qid):
    body = re.search(rf"^### {qid} — .+?\n(.*?)(?=^### |^---|\Z)", HOJA, re.M | re.S).group(1)
    expl = re.search(r"^- \*\*Explicación\*\* \(literal de ([^)]+)\): (.+)$", body, re.M)
    src = re.search(r"^- \*\*Fuente:\*\* (.+?) · \*\*Concepto:\*\* `(\w+)`", body, re.M)
    return {"prompt": re.search(r"^- \*\*Enunciado:\*\* (.+)$", body, re.M).group(1),
            "choices": re.findall(r"^  1\. (?:✅ )?(.+)$", body, re.M), "explanation": expl.group(2),
            "lines": [int(n) for n in re.findall(r"t2:(\d+)", expl.group(1))],
            "keys": re.findall(r"\[([A-Z]+\d{4})\]", src.group(1)), "concept": src.group(2)}


def _banco(qid):
    """La pregunta tal como quedó en el documento firmado del banco."""
    m = re.search(rf"^\*\*{qid} · [^\n]+\n(.+?)\n((?:- .+\n){{4}})\n\*Explicación:\* (.+?) \*Fuente:\* ((?:\[[A-Z]+\d{{4}}\])+)"
                  rf" · \*Línea firmada:\* ([^\n]+)\n\n\*\*Firma de Luis:\*\* ☑ firmo", BANCO, re.M)
    assert m, qid
    return {"prompt": m.group(1), "choices": [re.sub(r"^- (?:✅ )?", "", l) for l in m.group(2).strip().split("\n")],
            "explanation": m.group(3), "keys": re.findall(r"\[([A-Z]+\d{4})\]", m.group(4)),
            "lines": [int(n) for n in re.findall(r"t2:(\d+)", m.group(5))]}


def _limpia(linea):
    """Las reglas de la hoja: sin «Idea./Mecanismo./Detalle.», sin `**`, sin viñeta ni clave; tabla «A: B.»."""
    m = re.match(r"^\|\s*(.+?)\s*\|\s*(.+?)\s*\|$", linea)
    s = f"{m.group(1)}: {m.group(2)}." if m else linea
    s = re.sub(r"^\s*-\s+", "", s).replace("**", "")
    s = re.sub(r"^(Idea|Mecanismo|Detalle)\.\s*", "", s)
    return re.sub(r"\s*(\[[A-Z]+\d{4}\])+", "", s)


# ── la firma ───────────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_bank_document_is_signed_with_luis_block_and_the_explicit_ids():
    assert "**Estado:** FIRMADO 2026-11-17" in BANCO
    assert "> «Firmo, el 17 de noviembre de 2026, Luis Nazariego Santome:\n> (1) E1–E10 y H1–H8" in BANCO
    assert "> No firmo hoy: las [N] del apéndice, H10–H12, C1.2 ni los casos C1–C6.»" in BANCO
    assert "Firmo todo" not in BANCO
    assert ("**Lo que abarca la firma (IDs firmados):** " + ", ".join(SIGNED_IDS) + ".") in BANCO
    assert BANCO.count("**Firma de Luis:** ☑ firmo") == 18
    for part in ("# Parte 3.", "# Apéndice.", "# Decisiones para Luis"):
        after = BANCO[BANCO.index(part):]
        assert after.split("\n", 3)[2].startswith("> **Después de hoy.**"), part


# ── letra por letra ────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("qid", SIGNED_IDS)
def test_each_question_matches_the_signed_sheet_letter_by_letter(qid):
    q, doc = BANK[qid], _banco(qid)
    assert (q.prompt, q.choices, q.answer) == (doc["prompt"], doc["choices"], 0)
    if qid == "E1":                                   # «Se integra tal como está en la v2 (enunciado, opciones y explicación)»
        assert "### E1 — FIRMAR TAL CUAL" in HOJA and "Se integra tal como está en la v2" in HOJA
        assert q.explanation == doc["explanation"] == "el electrodo capta la suma de los potenciales de las unidades motoras que tiene debajo."
        return
    hoja = _hoja(qid)
    assert (q.prompt, q.choices) == (hoja["prompt"], hoja["choices"])
    assert doc["explanation"] == hoja["explanation"] and doc["lines"] == hoja["lines"] and doc["keys"] == hoja["keys"]
    if qid == "H4":                                   # cortada antes de la segunda «la razón LF/HF»
        cut = hoja["explanation"][:hoja["explanation"].index("la razón LF/HF", 5)]
        assert cut.startswith(q.explanation) and "la razón LF/HF" not in q.explanation[5:]
        assert cut[len(q.explanation):].strip() in ("; por eso", "por eso")
    else:
        assert q.explanation == hoja["explanation"]
    for key in hoja["keys"]:
        assert f"[{key}] " in q.source
    assert QB.CONCEPT_BY_PROMPT[q.prompt] == hoja["concept"]


@pytest.mark.parametrize("qid", SIGNED_IDS)
def test_each_explanation_is_a_substring_of_its_signed_t2_lines(qid):
    q = BANK[qid]
    if qid == "E1":
        # Excepción explícita, no una omisión: E1 se firmó «tal cual» en la hoja v2, cuya explicación resume t2:13 en
        # vez de copiarla. Se exige que sea EXACTAMENTE la de la hoja. Allí va entre comillas dentro de una frase; la
        # app la muestra como oración, con su punto final.
        signed = re.search(r"^### E1 — FIRMAR TAL CUAL\n.*?la explicación de la v2 \(«([^»]+)»\)", HOJA, re.M | re.S)
        assert signed, "la hoja v2 debe traer la explicación firmada de E1 entre «»"
        assert q.explanation == signed.group(1) + ".", (q.explanation, signed.group(1))
        return
    lines = _hoja(qid)["lines"]
    joined = " ".join(_limpia(T2[n - 1]) for n in lines)
    assert q.explanation in joined, (qid, lines)


def test_no_id_outside_the_signed_list_is_in_code():
    src = (ROOT / "educational/quiz_bank.py").read_text(encoding="utf-8")
    ids = re.findall(r"QuizQuestion\(\s*#\s*([A-Z]+\d+(?:\.\d+)?) ·", src)
    assert ids == SIGNED_IDS
    unsigned = re.findall(r"^\*\*(C\d\.\d)\*\* (?:\*\([^)]*\)\* )?(.+)$", BANCO, re.M)
    prompts = {q.prompt for q in QB.EMG_QUESTIONS + QB.HRV_QUESTIONS}
    assert unsigned and not any(p in prompts for _, p in unsigned)        # los casos (después de hoy) no están
    for appendix_id in ("E11", "E12", "H9", "H10", "H11", "H12"):
        assert f"# {appendix_id} ·" not in src


def test_both_banks_are_inside_balance_positions():
    tree = ast.parse((ROOT / "educational/quiz_bank.py").read_text(encoding="utf-8"))
    calls = {n.target.id: n.value for n in tree.body if isinstance(n, ast.AnnAssign)}
    for name in ("ACADEMIA_QUESTIONS", "ECG12_QUESTIONS", "EEG_QUESTIONS", "EMG_QUESTIONS", "HRV_QUESTIONS"):
        assert isinstance(calls[name], ast.Call) and calls[name].func.id == "balance_positions", name


@pytest.mark.parametrize("bank", [QB.EMG_QUESTIONS, QB.HRV_QUESTIONS], ids=["emg", "hrv"])
def test_the_correct_answer_is_the_longest_in_at_most_40_percent(bank):
    longest = sum(1 for q in bank if len(q.correct_choice) > max(len(c) for c in q.choices[1:]))
    assert longest <= 0.4 * len(bank), longest


def test_lf_hf_texts_follow_b3():
    """Decisión de Luis (B3): la razón LF/HF va rotulada «(interpretación discutida)» o es el texto firmado que explica
    por qué es discutida; nunca como balance, dominancia o proxy."""
    for q in QB.HRV_QUESTIONS:
        for text in [q.prompt, *q.choices, q.explanation]:
            if "LF/HF" in text:
                assert "(interpretación discutida)" in text or text.startswith("La razón LF/HF es discutida"), text
                assert not re.search(r"balance|dominancia|proxy", text, re.I), text


# ── registro en la sesión y en la mejora continua ──────────────────────────────────────────────────────────────────
def _academia_quiz(lesson):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(ROOT / "app/main.py"), default_timeout=180)
    at.session_state["biocore_start_page"] = "quiz"
    at.run()
    at.selectbox(key="academia_lesson").set_value(lesson)
    at.radio(key="academia_level").set_value("advanced")
    at.button(key="academia_start_quiz").click().run()
    questions = at.session_state["academia_quiz"]["questions"]
    for i in range(len(questions)):
        q = questions[i]
        at.radio(key=f"academia_quiz_choice_{i}").set_value(q.correct_choice if i % 2 == 0 else q.choices[1])
        at.radio(key=f"academia_quiz_confidence_{i}").set_value(75).run()
        at.button(key=f"academia_quiz_submit_{i}").click().run()
        assert at.exception == [], at.exception
        at.button(key=f"academia_quiz_next_{i}").click().run()
    return at, questions


@pytest.mark.parametrize("lesson, concept, bank, n", [("EMG", "emg", "emg", 10), ("HRV", "hrv", "hrv", 8)])
def test_the_18_questions_are_logged_in_the_session_with_their_concept(monkeypatch, lesson, concept, bank, n):
    pytest.importorskip("streamlit")
    import educational.learning_analytics as LA

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    before = len(LA.load_answers(bank=bank))
    at, questions = _academia_quiz(lesson)
    assert len(questions) == n
    log = at.session_state["session_learning_log"]
    assert len(log) == n and {e["concept"] for e in log} == {concept} and {e["source"] for e in log} == {"quiz"}
    assert [e["confidence"] for e in log] == [75] * n
    assert [e["correct"] for e in log] == [i % 2 == 0 for i in range(n)]
    assert len(LA.load_answers(bank=bank)) - before == n               # mejora continua, con su banco


# ── «Pregunta a BIOCORE»: nada se guarda; aviso P2 ─────────────────────────────────────────────────────────────────
def test_asking_biocore_stores_nothing_and_shows_the_privacy_notice(monkeypatch):
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    import domain.physiology.state.db as ups_db
    import educational.knowledge_base as kb
    import educational.learning_analytics as LA
    from app.supermodules.academia.ask import PRIVACY_NOTICE

    assert PRIVACY_NOTICE == ("No escribas datos personales ni de pacientes: tu pregunta se envía al proveedor de IA "
                              "configurado para responderla.")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    question = "¿Por qué se filtra el EMG a 20 Hz?"
    snapshot = lambda: (len(LA.load_answers()), len(LA.load_questions()), sum(map(len, LA.load_reports().values())))
    before = snapshot()

    at = AppTest.from_file(str(ROOT / "app/main.py"), default_timeout=120)
    at.session_state["biocore_start_page"] = "pregunta"
    at.run()
    assert PRIVACY_NOTICE in [w.value for w in at.warning]            # a la vista antes de escribir
    at.text_area(key="ask_biocore_question").input(question).run()
    at.button(key="ask_biocore_submit").click().run()
    assert at.exception == [] and "[DL2010]" in " ".join(m.value for m in at.main.markdown)

    assert snapshot() == before
    assert "session_learning_log" not in at.session_state
    for path in (LA.DEFAULT_DB_PATH, ups_db.DEFAULT_DB_PATH, kb.DEFAULT_DB_PATH):
        if Path(path).exists():
            assert question.encode("utf-8") not in Path(path).read_bytes(), path
    src = (ROOT / "app/supermodules/academia/ask.py").read_text(encoding="utf-8")
    code = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
    for persist in ("learning_log", "learning_analytics", "log_answer", "record_", "log_session_answer"):
        assert persist not in code.split('"""', 2)[-1], persist             # fuera del docstring
