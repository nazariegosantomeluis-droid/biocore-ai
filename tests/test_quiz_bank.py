"""Cuestionarios con respuesta correcta, fuente y calificación honesta (2026-11-14, Art. I).

- Cada banco de `educational/quiz_bank.py` tiene una sola respuesta correcta, escrita primero
  (un índice mal puesto no pasa desapercibido), con explicación y fuente.
- Las opciones se barajan siempre igual y el lugar de la correcta se reparte dentro del banco.
- Ninguna radio empieza con una opción elegida: sin contestar no hay acierto ni mensaje.
- Los errores clínicos corregidos no vuelven (pericarditis al revés, 12 derivaciones «sintéticas»
  desde una sola, SNR sin unidades, «pseudo-infarto», QT de hombres < 440 ms...).
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from educational.learning_engine import LearningEngine, generate_quiz
from educational.quiz_bank import (ACADEMIA_QUESTIONS, ECG12_QUESTIONS, EEG_QUESTIONS, QuizQuestion,
                                   balance_positions, numeric_choices, stable_shuffle)

ROOT = Path(__file__).resolve().parents[1]
BANKS = {"academia": ACADEMIA_QUESTIONS, "ecg12": ECG12_QUESTIONS, "eeg": EEG_QUESTIONS}


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return " ".join("".join(c for c in text if not unicodedata.combining(c)).split())


# --- estructura de cada banco ------------------------------------------------------------------------

@pytest.mark.parametrize("name", BANKS)
def test_each_question_has_one_correct_answer_written_first_with_explanation_and_source(name):
    for i, q in enumerate(BANKS[name]):
        where = f"{name}[{i}]: {q.prompt[:60]}"
        assert len(q.choices) >= 3, where
        assert len({_norm(c) for c in q.choices}) == len(q.choices), where        # sin opciones repetidas
        assert q.answer == 0, where                                               # la correcta va primero
        assert q.explanation.strip() and q.source.strip(), where
        assert not any(c.lstrip().startswith("✓") for c in q.choices), where
        assert _norm(q.correct_choice) not in _norm(q.prompt), where             # el enunciado no la regala


@pytest.mark.parametrize("name", BANKS)
def test_the_correct_answer_is_not_given_away_by_being_the_longest(name):
    bank = BANKS[name]
    longest = sum(1 for q in bank if len(q.correct_choice) > max(len(c) for c in q.choices[1:]))
    assert longest <= 0.4 * len(bank), (name, longest)


@pytest.mark.parametrize("name", BANKS)
def test_display_order_is_stable_and_the_correct_place_is_balanced(name):
    bank = BANKS[name]
    places = Counter()
    for q in bank:
        shown = q.display_choices()
        assert shown == q.display_choices()                                       # igual en cada recarga
        assert sorted(shown) == sorted(q.choices)
        places[shown.index(q.correct_choice)] += 1
    n_choices = {len(q.choices) for q in bank}
    assert n_choices == {4}
    assert max(places[p] for p in range(4)) - min(places[p] for p in range(4)) <= 1, places


def test_is_correct_needs_an_answer():
    q = ECG12_QUESTIONS[0]
    assert not q.is_correct(None)
    assert q.is_correct(q.correct_choice)
    assert not any(q.is_correct(c) for c in q.choices[1:])


def test_balance_positions_and_stable_shuffle_are_deterministic():
    make = lambda: [QuizQuestion(f"p{i}", ["a", "b", "c"], 0) for i in range(9)]  # noqa: E731
    first, second = balance_positions(make(), "x"), balance_positions(make(), "x")
    assert [q.display_position for q in first] == [q.display_position for q in second]
    assert Counter(q.display_position for q in first) == {0: 3, 1: 3, 2: 3}
    assert stable_shuffle(range(10), "s") == stable_shuffle(range(10), "s")


def test_numeric_choices_vary_the_place_of_the_correct_value():
    places = set()
    for correct in range(1, 40):
        options = numeric_choices(correct, 4, f"fr:{correct}", minimum=1)
        assert len(options) == 4 and options == sorted(set(options)) and correct in options
        assert min(options) >= 1 and all(b - a == 4 for a, b in zip(options, options[1:]))
        places.add(options.index(correct))
    assert places == {0, 1, 2, 3}                                                 # antes: siempre la segunda
    assert numeric_choices(0, 1, "apneas:0", minimum=0) == [0, 1, 2, 3]


# --- los errores clínicos corregidos no vuelven ------------------------------------------------------

def _find(bank, words):
    return next(q for q in bank if all(w in _norm(q.prompt) for w in words))


def test_pericarditis_is_diffuse_st_elevation_with_pr_depression_not_the_reverse():
    q = _find(ECG12_QUESTIONS, ["pericarditis"])
    assert _norm(q.correct_choice) == _norm("Elevación del ST difusa con descenso del PR")
    assert "ESC Guidelines for the management of myocarditis and pericarditis" in q.source


def test_one_lead_does_not_synthesize_twelve_and_does_not_assess_st_or_axis():
    q = _find(ECG12_QUESTIONS, ["sola derivacion"])
    assert _norm(q.correct_choice) == _norm("El ritmo y la FC; no el ST ni el eje")
    assert any("sintetizadas" in c for c in q.choices[1:])                       # la idea vieja quedó como distractor
    assert "Kligfield" in q.source


def test_unsourced_or_wrong_items_are_gone():
    text = " ".join(_norm(" ".join([q.prompt, *q.choices, q.explanation])) for q in ECG12_QUESTIONS + ACADEMIA_QUESTIONS)
    for gone in ("snr", "pseudo-infar", "derivadas sinteticas", "predominant", "deep s in", "large r in",
                 "delta wave", "derivada es util", "iec anterior"):
        assert gone not in text, gone
    for abbreviation in ("RCA", "LAD", "LCx", "RAD", "QB"):
        assert not any(abbreviation in q.choices for q in ECG12_QUESTIONS), abbreviation


def test_qtc_thresholds_match_rautaharju_2009():
    q = _find(ECG12_QUESTIONS, ["qtc", "hombre"])
    assert q.correct_choice == "450 ms o más" and "460 ms" in q.explanation and "390 ms" in q.explanation
    page = (ROOT / "app/supermodules/ecg_12/page_content.py").read_text(encoding="utf-8")
    assert "- QT: <440 ms" not in page and "QTc prolongado: ≥ 450 ms (♂), ≥ 460 ms (♀)" in page
    assert "- QRS: 60-120 ms" not in page


def test_the_eeg_seizure_question_no_longer_answers_itself():
    q = _find(EEG_QUESTIONS, ["crisis electrografica"])
    assert not any("Seizure" in c for c in q.choices)
    assert "2.5 Hz" in q.correct_choice and "Hirsch" in q.source


def test_sinus_bradycardia_question_teaches_the_2018_cut_off():
    q = ACADEMIA_QUESTIONS[0]
    assert q.correct_choice == "Frecuencia sinusal < 50 lpm" and "Kusumoto" in q.source


# --- motor de Academia -------------------------------------------------------------------------------

def test_submit_quiz_averages_every_quiz_including_a_zero():
    questions = generate_quiz(level="basic", lesson="ECG Básico")
    right = {i: q.answer for i, q in questions.items()}
    wrong = {i: q.answer + 1 for i, q in questions.items()}
    engine = LearningEngine(student_id="ana")
    assert engine.submit_quiz("ECG Básico", questions, wrong) == 0.0
    assert engine.submit_quiz("ECG Básico", questions, right) == 100.0
    assert engine.score == 50.0                                                   # antes: el 0 % se perdía (100)
    engine.submit_quiz("ECG Básico", questions, wrong)
    assert engine.score == pytest.approx(100.0 / 3)


def test_generate_quiz_keeps_lessons_and_levels():
    assert len(generate_quiz(level="advanced")) == len(ACADEMIA_QUESTIONS) == 16
    for lesson in ("ECG Básico", "ECG 12-derivaciones", "Arritmias", "Otras señales"):
        assert generate_quiz(level="advanced", lesson=lesson)
        assert all(q.category == lesson for q in generate_quiz(level="advanced", lesson=lesson).values())


# --- las pantallas: nada elegido de inicio, fuente al responder ---------------------------------------

def test_academia_quiz_starts_unanswered_and_shows_the_source(monkeypatch, tmp_path):
    import app.supermodules.academia.pages as pages
    import educational.rural_mode as R

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(R, "DEFAULT_PROGRESS_DIR", tmp_path / "progress")
    monkeypatch.setattr(pages, "stream_findings_narration", lambda *a, **k: (_ for _ in ()).throw(AssertionError()))

    def _script():
        from app.supermodules.academia.pages import run
        run()

    at = AppTest.from_function(_script, default_timeout=120).run()
    at.button(key="academia_start_quiz").click().run()
    q = at.session_state["academia_quiz"]["questions"][0]
    radio = at.radio(key="academia_quiz_choice_0")
    assert radio.value is None and sorted(radio.options) == sorted(q.choices)
    at.button(key="academia_quiz_submit_0").click().run()
    assert any("Elige una opción" in w.value for w in at.warning)
    assert not at.session_state["academia_quiz"]["answered_current"]
    at.radio(key="academia_quiz_choice_0").set_value(q.correct_choice).run()
    at.button(key="academia_quiz_submit_0").click().run()
    assert any(f"Correcto — {q.correct_choice}" in s.value for s in at.success)
    assert any(c.value == f"Fuente: {q.source}" for c in at.caption)
    assert not at.exception


def test_ecg12_quiz_starts_unanswered_grades_and_cites():
    def _script():
        from app.supermodules.ecg_12.pages import render_views
        render_views()

    at = AppTest.from_function(_script, default_timeout=120).run()
    assert not at.exception, at.exception
    q = ECG12_QUESTIONS[0]
    radio = at.radio(key="ecglab_12_quiz_1")
    assert radio.value is None and radio.options == q.display_choices()
    at.button(key="ecglab_12_quiz_verify").click().run()
    assert any("Elige una respuesta" in w.value for w in at.warning) and not at.success
    at.radio(key="ecglab_12_quiz_1").set_value(q.choices[1]).run()
    at.button(key="ecglab_12_quiz_verify").click().run()
    assert any(f"la respuesta es **{q.correct_choice}**" in e.value for e in at.error)
    assert any(c.value == f"Fuente: {q.source}" for c in at.caption)
    at.radio(key="ecglab_12_quiz_1").set_value(q.correct_choice).run()
    at.button(key="ecglab_12_quiz_verify").click().run()
    assert any("Correcto." in s.value and q.explanation in s.value for s in at.success)   # Streamlit separa el emoji
    text = " ".join(m.value for m in at.markdown)
    assert "Wagner" not in text                                                   # la fuente va en el caption
    assert any("Wagner GS" in c.value for c in at.caption) and any("Rautaharju PM" in c.value for c in at.caption)


@pytest.fixture
def temp_ups(tmp_path):
    from domain.physiology.state import create_patient, init_db, make_engine, make_session_factory

    engine = make_engine(Path(str(tmp_path / "quiz_bank.db")))
    init_db(engine)
    sf = make_session_factory(engine)
    with sf() as s:
        pid = create_patient(s, display_name="Cuestionarios (test)")
    return sf, pid


def test_eeg_quiz_unanswered_scores_zero_and_all_correct_scores_five(temp_ups):
    sf, pid = temp_ups

    def _script():
        import app.supermodules.eeg_neuro_lab.pages as m
        m.run()

    at = AppTest.from_function(_script, default_timeout=120)
    at.session_state["twin_shell_ups_session_factory"] = sf
    at.session_state["twin_shell_ups_patient_id"] = pid
    at.run()
    assert not at.exception, at.exception
    assert all(at.radio(key=f"eeg_quiz_{i}").value is None for i in range(1, 6))
    at.button(key="submit_eeg_quiz").click().run()
    assert any("Has respondido 0 de 5" in s.value for s in at.success)                # antes: la 3.ª sumaba sola
    assert any("5 pregunta(s) sin responder" in w.value for w in at.warning)
    for i, q in enumerate(EEG_QUESTIONS, start=1):
        at.radio(key=f"eeg_quiz_{i}").set_value(q.correct_choice).run()
    at.button(key="submit_eeg_quiz").click().run()
    assert any("Has respondido 5 de 5" in s.value for s in at.success)
    assert sum(1 for c in at.caption if c.value.startswith("Fuente: Kane N")) >= 4
    assert "procesamiento cognitivo integrado" not in " ".join(m.value for m in at.markdown)
