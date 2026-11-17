"""Aislamiento de la suite: ningun test escribe en la base de desarrollo.

Diagnostico (Tanda 1.5, 2026-11-05): `tests/test_ai_session_key.py` arranca
`app/main.py` completo por AppTest sin inyectar un factory propio. La app llama a
`get_shared_ups_engine()` -> `make_engine()` sin ruta, que lee el global
`domain.physiology.state.db.DEFAULT_DB_PATH` en el momento de la llamada, y
`get_active_patient_id()` crea ahi un "Paciente Demo (Twin Shell)". Cada corrida de
la suite dejaba 4 pacientes huerfanos en `data/biocore_ups.db` (la base real).

Se redirige ese mismo global (el mecanismo que el codigo ya usa) a un archivo
temporal durante toda la sesion de pruebas. La ruta por defecto de la app no cambia.
"""

import pytest


@pytest.fixture(autouse=True, scope="session")
def _ups_db_aislada(tmp_path_factory):
    import domain.physiology.state.db as db

    original = db.DEFAULT_DB_PATH
    db.DEFAULT_DB_PATH = tmp_path_factory.mktemp("ups_suite") / "biocore_ups_suite.db"
    try:
        yield db.DEFAULT_DB_PATH
    finally:
        db.DEFAULT_DB_PATH = original


@pytest.fixture(autouse=True, scope="session")
def _learning_db_aislada(tmp_path_factory):
    """Lo mismo para la base local de la mejora continua de los cuestionarios (2026-11-16): las pruebas que responden
    un cuestionario no escriben en `data/local/biocore_learning.db`."""
    import educational.learning_analytics as la

    original = la.DEFAULT_DB_PATH
    la.DEFAULT_DB_PATH = tmp_path_factory.mktemp("learning_suite") / "biocore_learning_suite.db"
    try:
        yield la.DEFAULT_DB_PATH
    finally:
        la.DEFAULT_DB_PATH = original


@pytest.fixture(autouse=True, scope="session")
def _knowledge_db_aislada(tmp_path_factory):
    """Lo mismo para la base de conocimiento de la IA (2026-11-17): las pruebas no reconstruyen
    `data/local/conocimiento.db`."""
    import educational.knowledge_base as kb

    original = kb.DEFAULT_DB_PATH
    kb.DEFAULT_DB_PATH = tmp_path_factory.mktemp("knowledge_suite") / "conocimiento_suite.db"
    try:
        yield kb.DEFAULT_DB_PATH
    finally:
        kb.DEFAULT_DB_PATH = original


@pytest.fixture(autouse=True)
def _aviso_de_entrada_aceptado(request, monkeypatch):
    """Aviso clínico y educativo de entrada (2026-11-17, `app/utils/legal.py`): las pruebas que abren páginas con AppTest
    prueban la PÁGINA, no el aviso; se apaga aquí y las pruebas del aviso lo encienden (`tests/test_legal.py`, marca
    `aviso_de_entrada`). AppTest corre en este proceso, así que el cambio llega a la app; monkeypatch lo restaura."""
    if request.node.get_closest_marker("aviso_de_entrada"):
        return
    import app.utils.legal as legal

    monkeypatch.setattr(legal, "GATE_ENABLED", False)


def pytest_configure(config):
    config.addinivalue_line("markers", "aviso_de_entrada: la prueba ve el aviso clínico de entrada (no se apaga)")
