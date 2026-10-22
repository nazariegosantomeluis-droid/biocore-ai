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


def test_streamlit_config_is_headless_and_local_only():
    config = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    assert "headless = true" in config
    assert 'address = "127.0.0.1"' in config
    assert "gatherUsageStats = false" in config
