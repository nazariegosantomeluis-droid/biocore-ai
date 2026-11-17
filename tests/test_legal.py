"""Textos legales en la app (2026-11-17, `app/utils/legal.py`; originales y ajustes en docs/legal/textos_legales.md).

Art. I: cada texto de la app está literal en el documento; ningún dato faltante se inventa (se ve «[pendiente: …]»);
el aviso clínico de entrada bloquea la página hasta marcar la casilla y vuelve a pedirse al entrar a un caso clínico.
"""
import re
import warnings
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import app.utils.legal as legal

DOC = Path(legal.LEGAL_DOC).read_text(encoding="utf-8")
MAIN = str(Path("app/main.py").resolve())


def _app_texts():
    texts = [legal.FOOTER_NOTICE, legal.IN_REVIEW_NOTICE, legal.PRIVACY_PREAMBLE, legal.CLICKWRAP_TEXT,
             legal.CLICKWRAP_CHECKBOX, legal.CLICKWRAP_BUTTON, legal.CLICKWRAP_HINT, legal.SAFETY_TITLE]
    texts += [body for _, _, body in legal.TERMS + legal.PRIVACY] + list(legal.SAFETY.values())
    return texts


def test_cada_texto_de_la_app_esta_literal_en_el_documento():
    for text in _app_texts():
        assert text in DOC, text[:80]
    for _id, heading, _ in legal.TERMS + legal.PRIVACY:
        assert f"**{_id} · {heading}**" in DOC, _id


def test_los_originales_quedan_en_el_documento_tal_como_se_entregaron():
    for fragment in ("métricas (incluyendo estimaciones de oxigenación)", "simulaciones matemáticas validadas",
                     "Permitir la evaluación académica en la \"Capa Docente\"",
                     "infraestructura de servidores cifrados de BIOCORE AI", "Consumo máximo: [X] mA",
                     "BIOCORE AI – KIT DE LABORATORIO DIGITAL DE FISIOLOGÍA"):
        assert fragment in DOC, fragment


def test_lo_que_no_es_cierto_hoy_no_llega_a_la_app():
    """Las frases que describían funciones que no existen no se muestran (sí siguen en el documento como original)."""
    shown = " ".join(legal.fill(t) for t in _app_texts())
    for false_today in ("simulaciones matemáticas validadas", "servidores cifrados", "estimaciones de oxigenación",
                        "matrícula y rol (estudiante/docente)", "Permitir la evaluación académica"):
        assert false_today not in shown, false_today


def test_ningun_dato_faltante_se_inventa():
    for text in _app_texts():
        filled = legal.fill(text)
        assert "{" not in filled and "}" not in filled, filled[:80]
        assert "[Nombre de tu" not in filled and "[X]" not in filled
    for key in legal.missing_data():
        assert legal.pending_marker(key) in legal.fill("{" + key + "}")
    assert set(legal.DATA_LABELS) == set(legal.LEGAL_DATA)
    if legal.missing_data():          # no rompe la suite: avisa en el resumen mientras falten datos
        warnings.warn(f"Textos legales con datos pendientes: {', '.join(legal.missing_data())} "
                      f"(llénalos en LEGAL_DATA, app/utils/legal.py)", UserWarning)


def test_un_dato_dado_reemplaza_su_marcador(monkeypatch):
    monkeypatch.setitem(legal.LEGAL_DATA, "correo_privacidad", "privacidad@ejemplo.mx")
    text = dict((i, b) for i, _, b in legal.PRIVACY)["AP4"]
    assert "privacidad@ejemplo.mx" in legal.fill(text) and "[pendiente" not in legal.fill(text)


def test_las_precauciones_del_manual_van_en_cada_tutorial_de_hardware():
    calls = {
        "app/supermodules/ecg_live/tutorial.py": "render_safety_precautions('ecg')",
        "app/supermodules/eeg_neuro_lab/live_tutorial.py": "render_safety_precautions('eeg')",
        "app/supermodules/biosensors/tutorial.py": "render_safety_precautions(sensor.key)",
    }
    for path, call in calls.items():
        assert call in Path(path).read_text(encoding="utf-8"), path
    from hardware.biosensors.sensors import SENSORS
    assert {s.key for s in SENSORS} <= set(legal.SAFETY_BY_KIND)
    assert set(k for keys in legal.SAFETY_BY_KIND.values() for k in keys) == set(legal.SAFETY)


@pytest.mark.parametrize("kind", sorted(legal.SAFETY_BY_KIND))
def test_las_precauciones_se_dibujan_tal_cual(kind):
    def _script():
        import streamlit as st
        from app.utils.legal import render_safety_precautions
        render_safety_precautions(st.session_state["kind"])

    at = AppTest.from_function(_script, default_timeout=30)
    at.session_state["kind"] = kind
    at.run()
    assert not at.exception
    text = " ".join(m.value for m in at.markdown)
    for key in legal.SAFETY_BY_KIND[kind]:
        assert legal.SAFETY[key] in text


def _open(start):
    at = AppTest.from_file(MAIN, default_timeout=240)
    at.session_state["biocore_start_page"] = start
    at.run()
    assert at.exception == [], at.exception
    return at


def _texts(at):
    return " ".join([m.value for m in at.markdown] + [c.value for c in at.caption])


@pytest.mark.aviso_de_entrada
def test_el_aviso_de_entrada_bloquea_la_pagina_hasta_marcar_la_casilla():
    assert legal.GATE_ENABLED
    at = _open("quiz")
    assert legal.CLICKWRAP_TEXT in _texts(at)
    assert "Quiz de la Academia" not in " ".join(m.value for m in at.markdown)     # la página no se dibuja
    enter = next(b for b in at.button if b.label == legal.CLICKWRAP_BUTTON)
    assert enter.disabled, "sin la casilla no se ingresa"
    at.checkbox[0].check().run()
    next(b for b in at.button if b.label == legal.CLICKWRAP_BUTTON).click().run()
    assert at.exception == []
    assert legal.CLICKWRAP_TEXT not in _texts(at)
    assert at.session_state[legal._SESSION_OK] is True


@pytest.mark.aviso_de_entrada
def test_cada_pagina_de_caso_clinico_vuelve_a_pedir_el_aviso():
    """La lógica, paso a paso: sesión nueva → aviso; aceptado → libre; caso → aviso; aceptado → libre dentro del caso;
    salir a otra página y volver al caso → aviso otra vez."""
    def _script():
        import streamlit as st
        from app.utils import legal as lg
        url = st.session_state["url"]
        st.session_state["pending"] = lg.clickwrap_pending(url)
        if st.session_state.get("accept") and st.session_state["pending"]:
            st.session_state[lg._SESSION_OK] = True
            if url in lg.CASE_PAGES:
                st.session_state[lg._CASE_OK] = url

    at = AppTest.from_function(_script, default_timeout=30)
    steps = [("quiz", False, True), ("quiz", True, True), ("quiz", False, False), ("detective", False, True),
             ("detective", True, True), ("detective", False, False), ("teoria", False, False),
             ("detective", False, True), ("caso-guiado", False, True)]
    for url, accept, expected in steps:
        at.session_state["url"], at.session_state["accept"] = url, accept
        at.run()
        assert at.session_state["pending"] is expected, (url, accept)


@pytest.mark.aviso_de_entrada
def test_un_caso_clinico_pide_el_aviso_aunque_la_sesion_ya_lo_acepto():
    at = _open("detective")
    at.checkbox[0].check().run()
    next(b for b in at.button if b.label == legal.CLICKWRAP_BUTTON).click().run()
    assert "Nuevo caso" in " ".join(b.label for b in at.button)                    # el Detective ya se ve
    assert set(legal.CASE_PAGES) == {"caso-ciego", "casos-simulador", "detective", "caso-guiado"}


@pytest.mark.parametrize("url,title,ids", [("terminos", legal.TERMS_TITLE, [i for i, *_ in legal.TERMS]),
                                           ("privacidad", legal.PRIVACY_TITLE, [i for i, *_ in legal.PRIVACY])])
def test_las_paginas_legales_muestran_los_textos_con_sus_marcadores(url, title, ids):
    at = _open(url)
    text = _texts(at)
    sections = dict((i, b) for i, _, b in legal.TERMS + legal.PRIVACY)
    for _id in ids:
        assert legal.fill(sections[_id]) in text, _id
    assert legal.IN_REVIEW_NOTICE in text
    if "entidad_legal" in legal.missing_data():
        assert legal.pending_marker("entidad_legal") in text          # nombrada en TC2/TC4 y en el preámbulo
    assert not re.search(r"\{[a-z_]+\}", text)


def test_el_pie_de_pagina_va_en_cada_pagina_y_enlaza_a_los_textos():
    at = _open("inicio")
    assert legal.FOOTER_NOTICE in _texts(at)
    links = {(link.proto.page, link.proto.label) for link in at.main.get("page_link")}
    assert {("terminos", "Términos y condiciones"), ("privacidad", "Aviso de privacidad")} <= links
