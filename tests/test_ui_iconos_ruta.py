"""Íconos del menú, flechas de la ruta y animaciones de scroll (2026-11-17).

- Cada página del menú tiene su ícono dibujado y el archivo existe: ningún enlace queda con un hueco en blanco (antes
  una regla genérica reservaba el espacio del ícono en todos los enlaces, también en los que no tenían ícono).
- Los íconos siguen las reglas del manual de marca v1.1 (24 × 24, línea de 1.75, puntas y uniones redondas, Trazo).
- La ruta del Inicio dibuja una flecha entre cada par de nodos, alternando la dirección del zigzag, y ninguna después
  del último; las flechas son decorativas (el lector de pantalla las omite).
- Toda animación se detiene con prefers-reduced-motion.
"""

from __future__ import annotations

import re
from pathlib import Path

from streamlit.testing.v1 import AppTest

from app.supermodules import ui_catalog as C
from app.utils import design_system as DS

STATIC = Path("app/static/marca")


def test_every_menu_page_has_an_existing_icon():
    import app.main as m

    urls = [u for _, u, *_ in m._page_specs()]
    assert len(urls) == 31 and set(DS.NAV_ICONS) == set(urls)
    for url, file in DS.NAV_ICONS.items():
        assert (STATIC / "iconos" / file).is_file(), (url, file)


def test_icons_follow_the_brand_rules():
    for file in sorted(set(DS.NAV_ICONS.values())):
        svg = (STATIC / "iconos" / file).read_text(encoding="utf-8")
        assert 'viewBox="0 0 24 24"' in svg and 'stroke-width="1.75"' in svg, file
        assert 'stroke-linecap="round"' in svg and 'stroke-linejoin="round"' in svg, file
        assert f'stroke="{DS.PALETTE.TRAZO}"' in svg and "<title>" in svg, file


def _theme_css(monkeypatch) -> str:
    captured = []
    monkeypatch.setattr(DS.st, "markdown", lambda body, **_kw: captured.append(body))
    DS.inject_global_theme()
    return "".join(captured)


def test_the_menu_reserves_icon_space_only_where_there_is_an_icon(monkeypatch):
    css = _theme_css(monkeypatch)
    assert not re.search(r'\[data-testid="stSidebarNav"\] a::before\s*\{', css)   # sin regla para todos los enlaces
    for url, file in DS.NAV_ICONS.items():
        assert f'a[href$="/{url}"]::before' in css and f"{DS.ICONS_URL}/{file}" in css, url
    assert 'a[href$="/"]::before' in css                     # Inicio, la página por defecto, enlaza a la raíz


def test_animations_stop_with_reduced_motion(monkeypatch):
    css = _theme_css(monkeypatch)
    assert "animation-timeline: view()" in css and "@supports (animation-timeline: view())" in css
    assert "@media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }" in css
    for direction in ("derecha", "izquierda"):
        svg = (STATIC / "ruta" / f"biocore-ruta-flecha-{direction}.svg").read_text(encoding="utf-8")
        assert "prefers-reduced-motion" in svg and f'stroke="{DS.PALETTE.TRAZO}"' in svg


def _path_script():
    from app.supermodules import ui_catalog as C
    from app.supermodules.ui_home import _render_path

    _render_path(C.ORGAN_BY_KEY["corazon"])


def test_the_route_draws_one_arrow_between_each_pair_of_nodes():
    at = AppTest.from_function(_path_script, default_timeout=30)
    at.run()
    assert not at.exception
    arrows = [m.value for m in at.markdown if "bc-arrow" in m.value]
    assert len(arrows) == len(C.PATHS["corazon"]) - 1
    for i, html in enumerate(arrows, start=1):
        direction = "derecha" if i % 2 == 1 else "izquierda"    # el nodo i va a la derecha cuando i es impar
        assert f"bc-arrow-{direction}" in html and 'aria-hidden="true"' in html and 'alt=""' in html
        assert (STATIC / "ruta" / f"biocore-ruta-flecha-{direction}.svg").is_file()
