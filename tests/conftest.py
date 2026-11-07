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
