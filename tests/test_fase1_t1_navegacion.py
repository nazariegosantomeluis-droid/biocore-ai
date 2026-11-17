"""Fase 1 de la propuesta, tanda 1, PARTE C (2026-11-15): navegación por intención.

- El menú son Inicio, Aprender, Practicar, Explorar y Ajustes; ni «Mi progreso» ni «Docente» (decisión 1).
- Inicio: tres puertas con una línea cada una; la clave de IA ya no es la primera pantalla (decisión 2).
- Ninguna página se pierde: las 12 entradas del menú anterior siguen alcanzables y renderizan.
"""

import ast
import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

MAIN = str(Path("app/main.py").resolve())
SRC = Path("app/main.py").read_text(encoding="utf-8")
LEGACY = ast.literal_eval(re.search(r"^LEGACY_ENTRIES = (\{.*?^\})", SRC, re.S | re.M).group(1))


@pytest.fixture(autouse=True)
def _no_env_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


def _specs():
    import app.main as m

    return m._page_specs()


def _open(url=None, **state):
    at = AppTest.from_file(MAIN, default_timeout=240)
    if url:
        at.session_state["biocore_start_page"] = url
    for k, v in state.items():
        at.session_state[k] = v
    at.run()
    assert at.exception == [], (url, at.exception)
    return at


def _links(block):
    return [(e.proto.page, e.proto.label) for e in block.get("page_link")]


def test_the_menu_is_the_five_intentions_and_nothing_without_identity():
    sections = [s for s, *_ in _specs()]
    assert list(dict.fromkeys(sections)) == ["", "Aprender", "Practicar", "Explorar", "Ajustes"]
    titles = " ".join(t for _, _, t, _, _ in _specs())
    assert "progreso" not in titles.lower() and "docente" not in titles.lower()
    urls = [u for _, u, *_ in _specs()]
    assert len(urls) == len(set(urls))
    assert 'st.navigation(menu, position="sidebar", expanded=True)' in SRC and 'showSidebarNavigation = true' in Path(".streamlit/config.toml").read_text(encoding="utf-8")


def test_each_section_holds_what_the_signed_decision_lists():
    by_section = {}
    for section, url, *_ in _specs():
        by_section.setdefault(section, []).append(url)
    # Pulido profesional (2026-11-16): Bibliografía, pedida en la tanda (todas las referencias, con enlaces).
    assert by_section["Aprender"] == ["teoria", "referencias", "ecg-3d", "bibliografia"]
    assert by_section["Practicar"] == ["quiz", "caso-ciego", "desafio-ecg", "cuestionarios", "casos-simulador", "detective"]
    assert by_section["Explorar"] == ["gemelo", "ecg", "multisensor", "respiratorio", "eeg", "emg", "hrv",
                                      "biomarcadores", "calculadoras", "pacientes", "modelo-3d"]
    assert by_section["Ajustes"] == ["ajustes"] and by_section[""] == ["inicio"]


def test_the_twelve_old_entries_all_map_to_existing_pages():
    assert len(LEGACY) == 12
    urls = {u for _, u, *_ in _specs()}
    for entry, targets in LEGACY.items():
        assert targets and set(targets) <= urls, entry


@pytest.mark.parametrize("url", sorted({u for t in LEGACY.values() for u in t}))
def test_every_old_entry_is_reachable_and_renders(url):
    at = _open(url)
    title = next(t for _, u, t, _, _ in _specs() if u == url)
    assert len(at.main.markdown) + len(at.main.get("tabs")) > 0, title


@pytest.mark.parametrize("url", ["inicio", "referencias", "ecg-3d", "desafio-ecg", "cuestionarios", "casos-simulador", "ajustes"])
def test_the_new_pages_render(url):
    _open(url)


def test_home_has_three_doors_with_one_line_each_and_no_key_gate():
    at = _open()
    links = _links(at.main)
    doors = [(p, l) for p, l in links if p in ("teoria", "cuestionarios", "gemelo")]
    assert [p for p, _ in doors] == ["teoria", "cuestionarios", "gemelo"]
    text = " ".join(m.value for m in at.main.markdown)
    for word in ("Aprender", "Practicar", "Explorar"):
        assert f"### " in text and word in text
    assert not at.text_input, "la clave de IA ya no es la primera pantalla"
    assert ("ajustes", "Ajustes: clave de IA") in links


def test_a_feature_that_needs_ai_says_so_right_there_with_a_link_to_settings():
    at = _open("hrv")
    assert any(p == "ajustes" for p, _ in _links(at.main)), "el aviso de IA debe enlazar a Ajustes ahí mismo"
    assert any("Ajustes" in w.value for w in at.main.warning)


def test_respiratory_links_to_the_calculator_page_through_the_menu():
    at = _open("respiratorio")
    assert ("calculadoras", "Abrir la calculadora de severidad (Calculadoras clínicas → Escalas)") in _links(at.main)


def test_a_lab_run_outside_the_menu_says_where_the_page_is_instead_of_failing():
    def _script():
        from app.utils import navigation as nav
        nav.link("calculadoras", "Calculadora")

    at = AppTest.from_function(_script)
    at.run()
    assert at.exception == [] and "en el menú lateral" in at.caption[0].value


def test_streamlit_minimum_is_the_installed_one_and_playwright_logs_are_ignored():
    import streamlit

    assert "streamlit>=1.66.1" in Path("requirements.txt").read_text(encoding="utf-8")
    assert tuple(int(x) for x in streamlit.__version__.split(".")[:2]) >= (1, 66)
    assert ".playwright-mcp/" in Path(".gitignore").read_text(encoding="utf-8")
