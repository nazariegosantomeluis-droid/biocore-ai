"""Interfaz en español e inglés (2026-11-18).

- Español por defecto; sin traducción se muestra el texto original, nunca uno inventado.
- Cada página y sección del menú, y cada texto que traduce el Inicio, tiene su traducción.
- El Inicio en inglés traduce su interfaz; el contenido firmado sigue en español y lo dice.
- En inglés, una página sin traducir lo avisa arriba; las legales dicen que aplica el texto firmado en español.
- El aviso de entrada en inglés es una traducción de cortesía y conserva el texto firmado en español.
"""

from __future__ import annotations

import re
from pathlib import Path

from streamlit.testing.v1 import AppTest

from app.utils import i18n, legal

MAIN = str(Path("app/main.py").resolve())
SAME_IN_BOTH = {"SpO₂", "HRV", "NEWS2", "ECG", "EEG", "EMG"}          # siglas que no cambian


def test_spanish_is_the_default_and_untranslated_text_falls_back_to_spanish():
    assert i18n.get_lang() == "es"                 # fuera de una sesión
    assert i18n.t("Ruta") == "Ruta" and i18n.t("") == ""


def test_every_menu_page_and_section_has_an_english_title():
    import app.main as m

    for section, url, title, *_ in m._page_specs():
        assert title in i18n.EN or title in SAME_IN_BOTH, (url, title)
        assert not section or section in i18n.EN, section
    assert all(value.strip() for value in i18n.EN.values())


def test_every_text_the_home_translates_has_a_translation():
    from app.supermodules import ui_catalog as C
    from app.supermodules import ui_home as H
    from app.utils.patient_banner import UNIT_ES, VITALS

    src = Path("app/supermodules/ui_home.py").read_text(encoding="utf-8")
    texts = {m.group(2) for m in re.finditer(r"""\bt\((["'])(.+?)\1\)""", src)}
    texts |= {H.LEMA, H.DESCRIPTOR, H.TIRA_LABEL, *H.DESCRIPTOR_ES.values(), *UNIT_ES.values()}
    texts |= {word for _kind, word in (*H.PROVENANCE_SEAL.values(), H.NO_DATA_SEAL)}
    texts |= {o.label for o in C.ORGANS} | {label for nodes in C.PATHS.values() for label, _, _ in nodes}
    texts |= {label for _key, label, *_ in VITALS}
    # T5: la tarjeta «Continúa en» del Hoy (`hubs.continue_target`) traduce su marco y el tipo de estación.
    from app.supermodules.ruta.model import KIND_LABELS
    texts |= {"Ruta", "Continúa en", "Empezar la Ruta", "estación", *KIND_LABELS.values()}
    missing = sorted(x for x in texts - SAME_IN_BOTH if x not in i18n.EN)
    assert missing == [], missing


def _open(url: str, lang: str | None = None) -> AppTest:
    at = AppTest.from_file(MAIN, default_timeout=240)
    at.session_state["biocore_start_page"] = url
    if lang is not None:
        at.session_state[i18n.LANG_KEY] = lang
    at.run()
    assert at.exception == [], (url, at.exception)
    return at


def _markdown(at) -> str:
    return " ".join(m.value for m in at.main.markdown)


def test_home_in_english_translates_the_interface_and_flags_signed_content():
    at = _open("inicio", "en")
    text = _markdown(at)
    assert "Active patient monitoring" in text and "Get it wrong here." in text
    assert all(f"### {door}" in text for door in ("Library", "Path", "Patient"))       # 2026-11-19: los destinos
    assert "Monitoreo del paciente activo" not in text and "### Aprender" not in text
    assert i18n.SIGNED_CONTENT_NOTE in " ".join(c.value for c in at.main.caption)
    assert not at.main.info                              # el Inicio está traducido: sin aviso de página en español


def test_spanish_stays_the_default_and_the_selector_switches_to_english():
    at = _open("inicio")
    assert "Monitoreo del paciente activo" in _markdown(at)
    radio = next(r for r in at.sidebar.radio if r.label == i18n.SELECTOR_LABEL)
    assert radio.value == "es" and list(radio.options) == ["Español", "English"]
    radio.set_value("en").run()
    assert at.exception == []
    assert "Active patient monitoring" in _markdown(at)


def test_untranslated_and_legal_pages_say_so_in_english():
    assert any(i18n.UNTRANSLATED_NOTICE in e.value for e in _open("bibliografia", "en").main.info)
    assert any(i18n.LEGAL_NOTICE in e.value for e in _open("terminos", "en").main.info)
    assert not _open("bibliografia").main.info or all(i18n.UNTRANSLATED_NOTICE not in e.value
                                                      for e in _open("bibliografia").main.info)


def _clickwrap_script():
    import streamlit as st

    from app.utils import i18n, legal

    st.session_state[i18n.LANG_KEY] = "en"
    legal.render_clickwrap("inicio")


def test_the_entry_notice_in_english_keeps_the_signed_spanish_text():
    at = AppTest.from_function(_clickwrap_script, default_timeout=30)
    at.run()
    assert not at.exception
    text = " ".join(m.value for m in at.markdown)
    assert i18n.CLICKWRAP_TEXT_EN in text and legal.CLICKWRAP_TEXT in text
    assert any(i18n.COURTESY_NOTE in c.value for c in at.caption)
    assert at.checkbox[0].label == i18n.EN[legal.CLICKWRAP_CHECKBOX]
    assert at.button[0].label == i18n.EN[legal.CLICKWRAP_BUTTON]
