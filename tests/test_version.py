"""Qué versión corre y si el proceso quedó con código viejo (2026-11-17, `app/utils/version.py`).

El 2026-11-17 Streamlit Cloud dio un ImportError: recargó `app/utils/patient_banner.py` pero no `clinical/`, que se quedó
con la versión con que arrancó el proceso. La app ahora dice qué versión corre y avisa cuando el proceso quedó atrás."""
import subprocess
from pathlib import Path

from streamlit.testing.v1 import AppTest

import app.utils.version as v

SHA_A, SHA_B = "a" * 40, "b" * 40


def _git(tmp_path, head, loose=None, packed=None):
    git = tmp_path / ".git"
    (git / "refs" / "heads").mkdir(parents=True)
    (git / "HEAD").write_text(head + "\n", encoding="utf-8")
    if loose:
        (git / "refs" / "heads" / "main").write_text(loose + "\n", encoding="utf-8")
    if packed:
        (git / "packed-refs").write_text(f"# pack-refs with: peeled\n{packed} refs/heads/main\n", encoding="utf-8")
    return tmp_path


def test_lee_el_commit_de_la_rama_suelta_empaquetada_o_separada(tmp_path):
    assert v.current_commit(_git(tmp_path / "a", "ref: refs/heads/main", loose=SHA_A)) == SHA_A
    assert v.current_commit(_git(tmp_path / "b", "ref: refs/heads/main", packed=SHA_B)) == SHA_B
    assert v.current_commit(_git(tmp_path / "c", SHA_A)) == SHA_A
    assert v.current_commit(tmp_path / "sin_git") is None
    assert v.short(None) == "no disponible" and v.short(SHA_A) == "aaaaaaa"


def test_en_este_repositorio_coincide_con_git():
    head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=v.ROOT).stdout.strip()
    assert v.current_commit() == head


def _script():
    from app.utils import version as ver
    ver.render_stale_warning()
    import streamlit as st
    st.caption(ver.version_text())


def test_sin_cambios_no_avisa_y_con_codigo_nuevo_pide_reiniciar(monkeypatch):
    from datetime import datetime, timezone

    # El arranque del proceso vive en `st.cache_resource` (todo el proceso de pytest): aquí se fija para la prueba.
    monkeypatch.setattr(v, "started", lambda: (SHA_A, datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)))
    monkeypatch.setattr(v, "current_commit", lambda root=v.ROOT: SHA_A)
    at = AppTest.from_function(_script, default_timeout=30)
    at.run()
    assert not at.warning and "`aaaaaaa`" in at.caption[0].value
    monkeypatch.setattr(v, "current_commit", lambda root=v.ROOT: SHA_B)      # main avanzó; el proceso sigue igual
    at.run()
    assert at.warning and "`bbbbbbb`" in at.warning[0].value and "`aaaaaaa`" in at.warning[0].value
    assert "Reboot app" in at.warning[0].value


def test_ajustes_muestra_la_version():
    at = AppTest.from_file(str(Path("app/main.py").resolve()), default_timeout=240)
    at.session_state["biocore_start_page"] = "ajustes"
    at.run()
    assert at.exception == []
    assert any(c.value.startswith("Versión del código:") for c in at.caption)
