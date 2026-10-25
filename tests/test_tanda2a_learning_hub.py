"""
Tanda 2A del aporte auditado (2026-10-22): el Learning Hub revive.

- rural_mode reintroducido (lo borró f2d88e4 sin ver que learning_engine lo
  importa) -> el Learning Hub vuelve a renderizar lecciones y quiz.
- El quiz califica sin clave de IA; solo el feedback narrado la requiere.
- `.env` se carga (sin pisar el entorno, sin aceptar el placeholder).
- Un solo engine de BD por proceso, no un pool por sesión de navegador.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


# --- Parte A: rural_mode ------------------------------------------------------

def test_learning_engine_imports_rural_mode_again():
    from app.supermodules.academia import pages
    from educational import learning_engine, rural_mode

    assert learning_engine.rural_mode is rural_mode
    assert pages.LESSONS_AVAILABLE


def test_rural_mode_docstring_tells_the_true_history():
    from educational import rural_mode

    doc = rural_mode.__doc__
    assert "f2d88e4" in doc and "2026-09-05" in doc
    assert "no existía" not in doc


def test_progress_roundtrip_is_atomic(tmp_path):
    from educational import rural_mode as R

    progress = {"ECG Básico": {"completed": True, "score": 80.0}}
    path = R.save_progress("ana", progress, base_dir=tmp_path)
    assert path.parent == tmp_path
    assert R.load_progress("ana", base_dir=tmp_path) == progress
    assert R.load_progress("nadie", base_dir=tmp_path) is None
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize("evil", ["../../fuera", "..\\..\\fuera", "/etc/passwd", "C:\\Windows\\x", "..", ""])
def test_student_id_cannot_escape_the_progress_dir(tmp_path, evil):
    from educational import rural_mode as R

    base = tmp_path / "progress"
    path = R.save_progress(evil, {"x": 1}, base_dir=base)
    assert path.resolve().parent == base.resolve()


def test_corrupt_progress_reads_as_none(tmp_path):
    from educational import rural_mode as R

    R._progress_path("ana", tmp_path).write_text("{no es json", encoding="utf-8")
    assert R.load_progress("ana", base_dir=tmp_path) is None


# --- Parte B: Learning Hub y quiz sin clave ----------------------------------

def _academia(monkeypatch, tmp_path):
    from streamlit.testing.v1 import AppTest

    import app.supermodules.academia.pages as pages
    import educational.rural_mode as R

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(R, "DEFAULT_PROGRESS_DIR", tmp_path / "progress")

    def _never_called(*_a, **_k):
        raise AssertionError("sin clave no se debe llamar al narrador")

    monkeypatch.setattr(pages, "stream_findings_narration", _never_called)

    def _script():
        from app.supermodules.academia.pages import run
        run()

    at = AppTest.from_function(_script, default_timeout=120)
    at.run()
    assert not at.exception, at.exception
    return at


def test_learning_hub_renders_lessons_instead_of_the_import_error(monkeypatch, tmp_path):
    at = _academia(monkeypatch, tmp_path)
    assert "no está disponible" not in " ".join(w.value for w in at.warning)
    at.checkbox(key="academia_rural_mode")
    at.button(key="academia_start_quiz")


def test_quiz_grades_a_wrong_answer_without_api_key(monkeypatch, tmp_path):
    at = _academia(monkeypatch, tmp_path)
    at.button(key="academia_start_quiz").click().run()
    q = at.session_state["academia_quiz"]["questions"][0]
    assert "Sin clave de IA" in " ".join(m.value for m in at.markdown)

    wrong = next(c for i, c in enumerate(q.choices) if i != q.answer)
    at.radio(key="academia_quiz_choice_0").set_value(wrong).run()
    at.button(key="academia_quiz_submit_0").click().run()
    assert not at.exception, at.exception

    errors = " ".join(e.value for e in at.error)
    assert f"la respuesta correcta es **{q.choices[q.answer]}**" in errors
    state = at.session_state["academia_quiz"]
    assert state["answered_current"] and state["responses"][0] == q.choices.index(wrong)
    assert state["feedback"] is None and state["feedback_error"] is None
    assert "solo el feedback narrado queda apagado" in " ".join(m.value for m in at.markdown)


def test_full_quiz_without_key_scores_100_and_saves_progress(monkeypatch, tmp_path):
    at = _academia(monkeypatch, tmp_path)
    at.checkbox(key="academia_rural_mode").check().run()
    at.button(key="academia_start_quiz").click().run()
    quiz = at.session_state["academia_quiz"]
    lesson, n = quiz["lesson_id"], len(quiz["questions"])
    assert n > 0

    for i in range(n):
        q = at.session_state["academia_quiz"]["questions"][i]
        at.radio(key=f"academia_quiz_choice_{i}").set_value(q.choices[q.answer]).run()
        at.button(key=f"academia_quiz_submit_{i}").click().run()
        assert any(f"Correcto — {q.choices[q.answer]}" in s.value for s in at.success), i
        at.button(key=f"academia_quiz_next_{i}").click().run()
        assert not at.exception, at.exception

    assert any("Puntuación: 100.0%" in s.value for s in at.success)
    saved = json.loads(next((tmp_path / "progress").glob("*.json")).read_text(encoding="utf-8"))
    assert saved["progress"][lesson] == {"completed": True, "score": 100.0}


def test_off_notice_promises_only_what_main_has():
    from app.utils.design_system import AI_FEEDBACK_OFF_MESSAGE

    assert "la calificación funciona igual" in AI_FEEDBACK_OFF_MESSAGE
    assert "ANTHROPIC_API_KEY" in AI_FEEDBACK_OFF_MESSAGE
    assert "ollama" not in AI_FEEDBACK_OFF_MESSAGE.lower()  # main no tiene IA local


# --- Parte C: .env ------------------------------------------------------------

def test_dotenv_key_reaches_the_narrator_but_the_placeholder_does_not(tmp_path, monkeypatch):
    from app.utils.env_loader import load_dotenv_file
    from domain.physiology.narrator import is_configured

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    env = tmp_path / ".env"
    env.write_text("ANTHROPIC_API_KEY=sk-your-key-here\n", encoding="utf-8")
    load_dotenv_file(env)
    assert not is_configured()

    env.write_text("ANTHROPIC_API_KEY=sk-ant-de-prueba\n", encoding="utf-8")
    load_dotenv_file(env)
    assert is_configured()


def test_main_loads_dotenv_before_the_app_imports():
    src = (ROOT / "app/main.py").read_text(encoding="utf-8")
    assert 'load_dotenv_file(Path(ROOT_DIR) / ".env")' in src
    assert src.index("load_dotenv_file(Path") < src.index("from app.supermodules import")


# --- Parte D: un engine por proceso -------------------------------------------

def test_browser_sessions_share_one_engine_but_not_the_orm_factory(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest

    import app.utils.patient_session as PS
    from domain.physiology.state import make_engine

    created = []

    def _make_engine():
        created.append(make_engine(tmp_path / "compartido.db"))
        return created[-1]

    def _script():
        import streamlit as st

        from app.utils.patient_session import get_active_session_factory

        sf = get_active_session_factory()
        st.session_state["engine_id"] = id(sf.kw["bind"])
        st.session_state["factory_id"] = id(sf)

    monkeypatch.setattr(PS, "make_engine", _make_engine)
    PS.get_shared_ups_engine.clear()
    sessions = []
    try:
        for _ in range(3):
            at = AppTest.from_function(_script, default_timeout=60)
            at.run()
            assert not at.exception, at.exception
            sessions.append(at)
        assert len(created) == 1
        assert len({at.session_state["engine_id"] for at in sessions}) == 1
        assert len({at.session_state["factory_id"] for at in sessions}) == 3
    finally:
        PS.get_shared_ups_engine.clear()
        for engine in created:
            engine.dispose()


def test_shared_engine_is_safe_across_threads(tmp_path):
    from sqlalchemy import text

    from domain.physiology.state import make_engine

    engine = make_engine(tmp_path / "hilos.db")
    assert type(engine.pool).__name__ == "QueuePool"
    assert engine.dialect.create_connect_args(engine.url)[1]["check_same_thread"] is False

    errors = []

    def _query():
        try:
            with engine.connect() as conn:
                assert conn.execute(text("select 1")).scalar() == 1
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=_query) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    engine.dispose()
    assert not errors, errors


def test_academia_case_uses_the_shared_engine():
    src = (ROOT / "app/supermodules/academia/pages.py").read_text(encoding="utf-8")
    assert "make_engine(" not in src
    assert "make_session_factory(get_shared_ups_engine())" in src
