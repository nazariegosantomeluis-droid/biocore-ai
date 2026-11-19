"""Navegación (T5 de la ruta integrada, 2026-11-18): cinco destinos en el menú (Hoy, Ruta, Paciente, Biblioteca y
Ajustes) con `st.navigation`; las demás páginas siguen registradas, fuera del menú. `app/main.py` declara las páginas
(`_page_specs()`) y las registra aquí en cada ejecución; cualquier módulo enlaza a otra página por su `url_path` con
`link()`, sin conocer el menú.

«Mi progreso» y «Docente» NO existen todavía (decisión 1): no hay identidad ni persistencia que los respalde.
"""

from __future__ import annotations

from typing import Optional

import streamlit as st

_REGISTRY = "_biocore_nav_pages"     # {url_path: StreamlitPage} de ESTA sesión (lo escribe app/main.py)
START_PAGE = "biocore_start_page"    # url_path de la página inicial (pruebas AppTest; sin él, Inicio)

# Dónde vive cada página en el menú, para el texto de respaldo cuando no hay menú (un laboratorio corrido solo).
SECTION_OF: dict = {}


def register(pages: dict, sections: dict) -> None:
    st.session_state[_REGISTRY] = pages
    SECTION_OF.update(sections)


def page(url_path: str):
    return (st.session_state.get(_REGISTRY) or {}).get(url_path)


def link(url_path: str, label: str, icon: Optional[str] = None) -> None:
    """Enlace a otra página del menú. Si la página no está registrada (el laboratorio corre fuera de la app, p. ej.
    en una prueba), dice dónde encontrarla en vez de fallar."""
    target = page(url_path)
    if target is None:
        where = SECTION_OF.get(url_path)
        st.caption(f"{label}: en el menú lateral" + (f", destino «{where}»." if where else "."))
        return
    st.page_link(target, label=label, icon=icon)
