"""Pulido estético y optimización (2026-11-18).

- El botón principal deshabilitado se lee (antes su texto quedaba oscuro sobre fondo oscuro).
- El menú lateral va sobre PANEL, y su texto tiene el contraste medido en `CONTRAST_PAIRS`.
- La barra superior no muestra «Deploy» ni las opciones de desarrollo.
- La animación de entrada del contenido es solo de opacidad: un transform rompería la barra fija del Inicio.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from app.utils import design_system as DS


def _theme_css(monkeypatch) -> str:
    captured = []
    monkeypatch.setattr(DS.st, "markdown", lambda body, **_kw: captured.append(body))
    DS.inject_global_theme()
    return "".join(captured)


def test_disabled_primary_button_text_is_readable(monkeypatch):
    css = _theme_css(monkeypatch)
    assert f'[data-testid="stBaseButton-primary"]:disabled * {{\n                color: {DS.PALETTE.NEUTRAL} !important; }}' in css
    assert ("NEUTRAL", "BACKGROUND", 4.5) in DS.CONTRAST_PAIRS


def test_sidebar_on_panel_with_measured_text(monkeypatch):
    css = _theme_css(monkeypatch)
    assert f'[data-testid="stSidebar"] {{ background: {DS.PALETTE.PANEL};' in css
    for pair in (("TEXT", "PANEL", 4.5), ("NEUTRAL", "PANEL", 4.5), ("TINTA_2", "PANEL", 4.5)):
        assert pair in DS.CONTRAST_PAIRS


def test_toolbar_is_minimal():
    config = tomllib.loads(Path(".streamlit/config.toml").read_text(encoding="utf-8"))
    assert config["client"]["toolbarMode"] == "minimal"


def test_content_fade_does_not_use_transform(monkeypatch):
    css = _theme_css(monkeypatch)
    fade = re.search(r"@keyframes bc-fade \{(.*?)\}\s*\}", css, re.S)
    assert fade and "transform" not in fade.group(1)
