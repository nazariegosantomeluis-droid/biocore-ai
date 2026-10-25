"""run_biocore.py y lanzadores de Windows (2026-10-19).

Regresión real, vista en una PC con Windows: el abridor del navegador
consultaba el puerto con `-TimeoutSec 1`; una consulta abortada a medio
aceptar (WinError 64) hacía que el ProactorEventLoop de asyncio CERRARA el
socket de escucha de Uvicorn y http://localhost:8501 dejaba de responder.
"""
import asyncio
import os
import sys
from pathlib import Path

import pytest

import run_biocore

ROOT = Path(__file__).resolve().parents[1]


def test_selector_event_loop_policy_is_installed_on_windows(monkeypatch):
    installed = []

    class FakeSelectorPolicy:
        pass

    monkeypatch.setattr(run_biocore.sys, "platform", "win32")
    monkeypatch.setattr(asyncio, "WindowsSelectorEventLoopPolicy", FakeSelectorPolicy, raising=False)
    monkeypatch.setattr(asyncio, "set_event_loop_policy", installed.append)
    assert run_biocore.use_selector_event_loop_on_windows() is True
    assert len(installed) == 1 and isinstance(installed[0], FakeSelectorPolicy)


def test_event_loop_policy_untouched_outside_windows(monkeypatch):
    installed = []
    monkeypatch.setattr(run_biocore.sys, "platform", "linux")
    monkeypatch.setattr(asyncio, "set_event_loop_policy", installed.append)
    assert run_biocore.use_selector_event_loop_on_windows() is False
    assert installed == []


def test_main_runs_streamlit_on_app_main_with_extra_args(monkeypatch):
    import streamlit.web.cli as stcli

    captured = {}

    def fake_main():
        captured["argv"] = list(sys.argv)
        return 0

    monkeypatch.setattr(stcli, "main", fake_main)
    monkeypatch.setattr(sys, "argv", ["run_biocore.py"])
    assert run_biocore.main(["--server.port", "8501"]) == 0
    argv = captured["argv"]
    assert argv[:2] == ["streamlit", "run"]
    assert argv[2].endswith(os.path.join("app", "main.py")) and Path(argv[2]).is_file()
    assert argv[3:] == ["--server.port", "8501"]


def test_windows_launchers_use_run_biocore_and_never_abort_health_checks():
    for name in ("RUN_BIOCORE.bat", "run_local.ps1"):
        text = (ROOT / name).read_text(encoding="utf-8-sig")
        assert "run_biocore.py" in text, name
        assert "-TimeoutSec 1 " not in text, name          # el detonante del WinError 64
        assert "-TimeoutSec 60" in text, name
        assert (ROOT / name).read_bytes().count(b"\r\n") > 5, f"{name} debe tener fin de línea CRLF"


# Tanda 2B: el aporte fijaba headless en .streamlit/config.toml, junto con su
# rediseño visual (no traído). En main lo pasan los lanzadores, para no
# cambiar `streamlit run` directo.
def test_launchers_run_headless_because_they_open_the_browser_themselves():
    for name in ("RUN_BIOCORE.bat", "run_local.ps1"):
        text = (ROOT / name).read_text(encoding="utf-8-sig")
        assert "run_biocore.py --server.port 8501 --server.headless true" in text, name


@pytest.mark.skipif(sys.platform != "win32", reason="la mitigación solo existe en Windows")
def test_real_policy_gives_streamlit_a_selector_loop_on_windows():
    """Sin fakes: tras la mitigación, `asyncio.run` (lo que usa el bootstrap
    de Streamlit) corre sobre un SelectorEventLoop, no sobre el Proactor."""
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        previous = asyncio.get_event_loop_policy()
    try:
        assert run_biocore.use_selector_event_loop_on_windows() is True

        async def loop_type():
            return type(asyncio.get_running_loop())

        assert issubclass(asyncio.run(loop_type()), asyncio.SelectorEventLoop)
    finally:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            asyncio.set_event_loop_policy(previous)


def test_run_biocore_declares_it_is_a_mitigation_with_expiry_date():
    doc = run_biocore.__doc__
    assert "MITIGACIÓN" in doc and "streamlit run app/main.py` directo NO se" in doc
    assert "deprecadas desde Python 3.14" in doc and "3.16" in doc
