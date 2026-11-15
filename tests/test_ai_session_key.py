"""Clave de IA por sesión (2026-10-25; en Ajustes desde la tanda 1 de la fase 1, 2026-11-15): verificación y aislamiento.

La garantía que importa: la clave pegada vive solo en el `session_state` de esa
sesión y llega al narrador como cliente propio; nunca toca `os.environ` (que es
del proceso entero y la compartiría con otras pestañas/usuarios). Desde la tanda 1
la clave NO es la primera pantalla: la plataforma abre en Inicio y la clave vive en Ajustes.
"""
import os

import pytest

import app.utils.ai_session as S


@pytest.fixture(autouse=True)
def _no_env_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


def _app():
    from app.main import main
    main()


def _run(page=None, **state):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_app, default_timeout=180)
    if page:
        at.session_state["biocore_start_page"] = page
    for k, v in state.items():
        at.session_state[k] = v
    at.run()
    assert not at.exception, at.exception
    return at


def _sidebar_text(at):
    return " ".join(c.value for c in at.sidebar.caption)


def _save(at):
    return next(b for b in at.button if b.label == "Guardar mi clave")


def test_the_platform_opens_on_home_not_on_a_key_panel():
    at = _run()
    assert not at.text_input, "la clave de IA ya no es la primera pantalla"
    assert "IA apagada" in _sidebar_text(at)
    assert any(e.proto.page == "ajustes" for e in at.sidebar.get("page_link"))      # la clave vive en Ajustes


def test_settings_shows_the_key_field_and_says_ai_is_off():
    at = _run("ajustes")
    assert at.text_input(key=S._INPUT).value == ""
    assert any("IA apagada" in i.value for i in at.info)


def test_valid_key_stays_in_this_session_only(monkeypatch):
    checked = []
    monkeypatch.setattr(S, "validate_api_key", lambda k: checked.append(k))  # None = válida
    at = _run("ajustes")
    at.text_input(key=S._INPUT).input("  sk-ant-de-prueba-123  ")
    _save(at).click().run()
    assert not at.exception, at.exception
    assert checked == ["sk-ant-de-prueba-123"]
    assert at.session_state[S.SESSION_KEY] == "sk-ant-de-prueba-123"
    assert at.session_state[S._INPUT] == "", "la clave no se queda en el campo"
    assert "ANTHROPIC_API_KEY" not in os.environ, "nunca al entorno del proceso"
    assert "IA activa con tu clave" in _sidebar_text(at)
    other = _run("ajustes")  # otra sesión (otra pestaña): no ve la clave
    assert S.SESSION_KEY not in other.session_state and "IA apagada" in _sidebar_text(other)


def test_invalid_key_is_rejected_with_the_reason(monkeypatch):
    monkeypatch.setattr(S, "validate_api_key", lambda k: "Anthropic rechazó la clave: no es válida.")
    at = _run("ajustes")
    at.text_input(key=S._INPUT).input("sk-ant-mala")
    _save(at).click().run()
    assert any("rechazó la clave" in e.value for e in at.error)
    assert S.SESSION_KEY not in at.session_state
    assert at.session_state[S._INPUT] == ""


def test_forget_key_turns_ai_off(monkeypatch):
    at = _run("ajustes", **{S.SESSION_KEY: "sk-ant-x"})
    assert "IA activa con tu clave" in _sidebar_text(at)
    next(b for b in at.button if b.label == "Olvidar mi clave").click().run()
    assert S.SESSION_KEY not in at.session_state and "IA apagada" in _sidebar_text(at)


def test_server_env_key_turns_ai_on_without_any_panel(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-del-servidor")
    at = _run()
    assert "clave del entorno del servidor" in _sidebar_text(at) and not at.text_input


def test_narrator_receives_a_client_built_with_the_session_key(monkeypatch):
    import domain.physiology.narrator as N

    seen = {}

    def fake_stream(context, client=None, **_):
        seen["client"] = client
        yield "ok"

    monkeypatch.setattr(N, "stream_findings_narration", fake_stream)

    def _script():
        from app.main import render_findings_narrator
        render_findings_narrator("Lab de prueba", [("FC", "72 lpm", "normal")])

    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_script, default_timeout=120)
    at.session_state[S.SESSION_KEY] = "sk-ant-de-sesion"
    at.run()
    next(b for b in at.button if "Explicar" in b.label).click().run()
    assert not at.exception, at.exception
    assert seen["client"].api_key == "sk-ant-de-sesion"
    assert "ANTHROPIC_API_KEY" not in os.environ


def test_every_ai_call_in_the_ui_passes_the_session_client():
    """Ninguna llamada de la interfaz al narrador puede olvidar `client=`: sin él
    usaría solo la clave del entorno e ignoraría la pegada."""
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    calls = []
    for path in (root / "app").rglob("*.py"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if re.search(r"stream_(narration|findings_narration|causal_narration)\(", line) and "def " not in line:
                calls.append((path.name, line.strip()))
    assert len(calls) >= 6
    assert all("client=ai_client()" in line for _, line in calls), calls
