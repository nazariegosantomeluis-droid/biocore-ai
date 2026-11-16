"""Mejora continua de los cuestionarios con ML local (2026-11-16): registro, análisis de ítems, Elo y su interfaz.

Verificación por ejecución con verdad conocida: estudiantes simulados con el modelo de Rasch (habilidad y
dificultad conocidas) responden un banco donde una pregunta tiene la clave mal puesta. El análisis debe señalar esa
pregunta y no las buenas, y el Elo debe recuperar el orden de las dificultades y de las habilidades.
"""

from __future__ import annotations

import math
import random

import numpy as np
import pytest
from scipy.stats import spearmanr

from educational import learning_analytics as LA
from educational.quiz_bank import ACADEMIA_QUESTIONS, ECG12_QUESTIONS, EEG_QUESTIONS, QuizQuestion

BANK = "prueba"
TRUE_D = np.linspace(-1.5, 1.5, 12)
MISKEYED = 7


def bank_questions():
    return [QuizQuestion(f"Pregunta {i}", ["A", "B", "C", "D"], 0, category="Tema 1" if i < 6 else "Tema 2")
            for i in range(12)]


@pytest.fixture
def simulated(tmp_path):
    """60 estudiantes, 2 intentos cada uno, 12 preguntas; en la pregunta 7 «aciertan» los que saben menos."""
    rng = random.Random(3)
    db = tmp_path / "learning.db"
    questions = bank_questions()
    thetas = {f"e{k}": rng.gauss(0, 1) for k in range(60)}
    for learner, theta in thetas.items():
        for _ in range(2):
            attempt = LA.new_attempt()
            for i, question in enumerate(questions):
                p = 1 / (1 + math.exp(-(theta - TRUE_D[i])))
                right = rng.random() < (1 - p if i == MISKEYED else p)
                wrong = ["B"] if i == MISKEYED else ["B", "C", "D"]
                LA.record_answer(BANK, question, "A" if right else rng.choice(wrong), attempt, learner, path=db)
    return db, questions, thetas


def test_answers_and_reports_are_stored_locally_and_graded_by_the_bank(tmp_path):
    db = tmp_path / "learning.db"
    question = ACADEMIA_QUESTIONS[0]
    wrong = question.choices[1]
    LA.record_answer("academia", question, wrong, "intento-1", "ana", path=db)
    LA.record_answer("academia", question, question.correct_choice, "intento-2", "ana", path=db)
    answers = LA.load_answers(db)
    assert [a.correct for a in answers] == [0, 1]                       # lo decide `is_correct`, no quien llama
    qid = LA.question_id("academia", question.prompt)
    assert answers[0].question_id == qid == LA.question_id("academia", question.prompt)
    assert LA.load_questions(db)[qid]["correct_choice"] == question.correct_choice
    LA.record_report("academia", question, "  La fuente no dice eso.  ", "ana", path=db)
    assert LA.load_reports(db) == {qid: ["La fuente no dice eso."]}
    with pytest.raises(ValueError):
        LA.record_report("academia", question, "   ", "ana", path=db)
    assert LA.question_id("academia", question.prompt + " (editada)") != qid      # otro enunciado, otra pregunta


def test_item_analysis_flags_the_miskeyed_question_and_not_the_good_ones(simulated):
    db, questions, _ = simulated
    stats = LA.item_statistics(LA.load_answers(db), {}, {LA.question_id(BANK, q.prompt): "A" for q in questions})
    by_index = [stats[LA.question_id(BANK, q.prompt)] for q in questions]
    assert by_index[MISKEYED].discrimination < 0 and by_index[MISKEYED].discrimination_ci[1] < 0
    assert "clave" in by_index[MISKEYED].flags and by_index[MISKEYED].needs_review
    for i, item in enumerate(by_index):
        assert item.responses == 120 and item.pairs == 120
        if i != MISKEYED:
            assert item.discrimination > 0 and not {"clave", "distractor"} & set(item.flags), i
    assert "facil" not in by_index[-1].flags and "dificil" in by_index[-1].flags        # d = +1.5: 21 % de aciertos


def test_a_distractor_the_upper_group_prefers_asks_to_check_the_key(tmp_path):
    db = tmp_path / "learning.db"
    target = QuizQuestion("¿Cuál?", ["A", "B", "C", "D"], 0)
    anchors = [QuizQuestion(f"¿Ancla {i}?", ["A", "B"], 0) for i in range(3)]
    for k in range(40):
        attempt, strong = LA.new_attempt(), k < 20
        for anchor in anchors:
            LA.record_answer(BANK, anchor, "A" if strong else "B", attempt, f"e{k}", path=db)
        LA.record_answer(BANK, target, "B" if strong else ("A" if k % 2 else "C"), attempt, f"e{k}", path=db)
    qid = LA.question_id(BANK, target.prompt)
    item = LA.item_statistics(LA.load_answers(db), {}, {qid: "A"})[qid]
    assert {"distractor", "clave"} <= set(item.flags) and item.choice_counts["B"] == 20


def test_flags_need_evidence_not_just_a_low_sample_value():
    """Regresión del criterio: con 120 respuestas, una pregunta buena llegó a 0.16 por azar y se marcaba. Ahora el
    intervalo de 95 % tiene que quedar entero por debajo del corte."""
    low, high = LA.fisher_interval(0.16, 120)
    assert low < 0.16 < high and high > LA.LOW_DISCRIMINATION                 # no se marca
    assert LA.fisher_interval(-0.40, 120)[1] < 0                              # la clave mal puesta, sí
    assert LA.fisher_interval(0.5, 3) == (-1.0, 1.0)


def test_item_analysis_waits_for_enough_data_and_counts_the_first_response(tmp_path):
    db = tmp_path / "learning.db"
    question = QuizQuestion("¿Una?", ["A", "B"], 0)
    LA.record_answer(BANK, question, "B", "intento", "ana", path=db)
    LA.record_answer(BANK, question, "A", "intento", "ana", path=db)            # volver a verificar no cuenta
    item = LA.item_statistics(LA.load_answers(db))[LA.question_id(BANK, question.prompt)]
    assert item.responses == 1 and item.difficulty is None and item.flags == ()
    assert LA.fit_elo(LA.load_answers(db)).difficulty_counts[LA.question_id(BANK, question.prompt)] == 1
    other = QuizQuestion("¿Otra?", ["A", "B"], 0)
    LA.record_report(BANK, other, "La clave está mal.", "ana", path=db)
    reported = LA.item_statistics(LA.load_answers(db), LA.load_reports(db))[LA.question_id(BANK, other.prompt)]
    assert reported.flags == ("reportada",) and reported.needs_review and reported.responses == 0


def test_elo_update_is_the_one_in_pelanek_2016():
    state = LA.EloState()
    state.update("ana", "Tema", "q1", correct=1)                    # P = 0.5 y K = a = 1
    assert state.skills[("ana", "Tema")] == pytest.approx(0.5) and state.difficulties["q1"] == pytest.approx(-0.5)
    expected = LA.logistic(0.5 - (-0.5))
    state.update("ana", "Tema", "q1", correct=0)                    # K = 1 / (1 + 0.05)
    assert state.skills[("ana", "Tema")] == pytest.approx(0.5 - expected / 1.05)
    assert (LA.ELO_A, LA.ELO_B) == (1.0, 0.05) and "10.1016/j.compedu.2016.03.017" in LA.PELANEK_2016


def test_elo_recovers_the_order_of_difficulties_and_skills(simulated):
    db, questions, thetas = simulated
    state = LA.fit_elo(LA.load_answers(db))
    good = [i for i in range(12) if i != MISKEYED]
    estimated = [state.difficulties[LA.question_id(BANK, questions[i].prompt)] for i in good]
    assert spearmanr(estimated, [TRUE_D[i] for i in good]).correlation > 0.9
    skill = [np.mean([state.skills[(who, t)] for t in ("Tema 1", "Tema 2")]) for who in thetas]
    assert spearmanr(skill, list(thetas.values())).correlation > 0.75
    weakest, strongest = min(thetas, key=thetas.get), max(thetas, key=thetas.get)
    assert LA.learner_summary(state, weakest)[0][1] < LA.learner_summary(state, strongest)[0][1]


def test_suggestions_aim_at_three_out_of_four(simulated):
    db, questions, thetas = simulated
    state = LA.fit_elo(LA.load_answers(db))
    learner = min(thetas, key=thetas.get)
    chosen = LA.suggest_questions(state, learner, questions, BANK, n=3)
    gap = lambda q: abs(state.predict(learner, q.category, LA.question_id(BANK, q.prompt)) - LA.TARGET_SUCCESS)
    assert len(chosen) == 3 and max(map(gap, chosen)) <= min(gap(q) for q in questions if q not in chosen)


# ================================================================ interfaz (AppTest)
def _academia(monkeypatch):
    from streamlit.testing.v1 import AppTest

    import app.supermodules.academia.pages as pages

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(pages, "stream_findings_narration", lambda *a, **k: pytest.fail("sin clave no se narra"))

    def _script():
        from app.supermodules.academia.pages import run
        run()

    at = AppTest.from_function(_script, default_timeout=120)
    at.run()
    assert not at.exception, at.exception
    return at


def test_academia_logs_answers_reports_and_offers_adaptive_practice(monkeypatch, tmp_path):
    monkeypatch.setattr(LA, "DEFAULT_DB_PATH", tmp_path / "learning.db")
    at = _academia(monkeypatch)
    at.text_input(key="academia_student_id").input("ana").run()
    at.button(key="academia_start_quiz").click().run()
    q = at.session_state["academia_quiz"]["questions"][0]
    at.radio(key="academia_quiz_choice_0").set_value(q.choices[1]).run()
    at.button(key="academia_quiz_submit_0").click().run()
    assert not at.exception, at.exception
    answers = LA.load_answers()
    assert [(a.learner, a.bank, a.chosen, a.correct) for a in answers] == [("ana", "academia", q.choices[1], 0)]
    at.text_area(key="academia_report_0_text").input("La explicación no coincide con la fuente.").run()
    at.button(key="academia_report_0_send").click().run()
    assert any("cola de revisión" in s.value for s in at.success)
    assert list(LA.load_reports().values()) == [["La explicación no coincide con la fuente."]]

    at.button(key="academia_adaptive_quiz").click().run()
    quiz = at.session_state["academia_quiz"]
    assert quiz["lesson_id"] == "Práctica adaptativa" and len(quiz["questions"]) == 5
    assert all(question in ACADEMIA_QUESTIONS for question in quiz["questions"].values())
    page = " ".join(e.label for e in at.expander)
    assert "Revisión del banco de preguntas" in page and "Tu dominio estimado por tema — ana" in page


def test_review_table_lists_flagged_questions_first(monkeypatch, simulated):
    db, questions, _ = simulated
    monkeypatch.setattr(LA, "DEFAULT_DB_PATH", db)
    from app.supermodules.academia.improvement import review_table

    table = review_table()
    assert len(table) == 12 and table.loc[0, "Revisar"] == "⚠️"
    assert table.loc[0, "Pregunta"] == f"Pregunta {MISKEYED}" and "Revisar la clave" in table.loc[0, "Avisos"]
    assert table.loc[0, "Discriminación (IC 95 %)"].startswith("-0.") and " a " in table.loc[0, "Discriminación (IC 95 %)"]


def test_twelve_lead_and_eeg_quizzes_log_each_answer_once(monkeypatch, tmp_path):
    from streamlit.testing.v1 import AppTest

    monkeypatch.setattr(LA, "DEFAULT_DB_PATH", tmp_path / "learning.db")

    def _ecg12():
        import runpy
        runpy.run_path("app/supermodules/ecg_12/page_content.py", run_name="__main__")

    at = AppTest.from_function(_ecg12, default_timeout=180)
    at.run()
    question = ECG12_QUESTIONS[0]
    at.radio(key="ecglab_12_quiz_1").set_value(question.correct_choice).run()
    at.button(key="ecglab_12_quiz_verify").click().run()
    at.button(key="ecglab_12_quiz_verify").click().run()                 # volver a verificar no la repite
    assert not at.exception, at.exception
    assert [(a.bank, a.correct) for a in LA.load_answers()] == [("ecg12", 1)]

    def _eeg():
        import runpy
        runpy.run_path("app/supermodules/eeg_neuro_lab/page_content.py", run_name="__main__")

    at = AppTest.from_function(_eeg, default_timeout=180)
    at.run()
    at.radio(key="eeg_quiz_1").set_value(EEG_QUESTIONS[0].correct_choice).run()
    at.button(key="submit_eeg_quiz").click().run()
    at.button(key="submit_eeg_quiz").click().run()                       # mismas respuestas: no se repite
    assert not at.exception, at.exception
    eeg = [a for a in LA.load_answers() if a.bank == "eeg"]
    assert [(a.chosen, a.correct) for a in eeg] == [(EEG_QUESTIONS[0].correct_choice, 1)]
