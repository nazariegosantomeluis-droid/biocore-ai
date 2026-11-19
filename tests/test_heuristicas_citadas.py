"""Tanda de heurísticas (2026-11-19): nada visible se rotula «Heurística» ni «demo».

Pedido de Luis (2026-11-19): «todo lo que aparezca como heurístico se arregle por algo que está citado, busca las citas
de fuentes confiables por favor, pero ya no quiero que las cosas heurísticas inunden la plataforma, termina con todas de
una vez por todas». Decisiones del mismo día:
- Biomarcadores sale del menú;
- Fusión de sensores pierde los canales demo;
- el índice de riesgo del gemelo se retira;
- un umbral sin fuente pierde su juicio y queda la medida.

Inventario y plan: `docs/evolution/00_BASELINE_AUDIT.md` §4.

El recorrido es el de `test_fase1_t2_pulido.py`: las 34 páginas, cada sensor × modo de «Sensores en vivo» y las fuentes
alternas de los laboratorios. «Criterio BIOCORE» solo puede aparecer en los criterios que Luis firmó, uno por uno
(`SIGNED_CRITERIA`).
"""

import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from tests.test_fase1_t2_pulido import MAIN, SOURCES, _page_urls, _strip, visible_texts

HEURISTIC = re.compile(r"heur[ií]stic|\bdemo\b|demostraci[oó]n|PENDING_VALIDATION", re.IGNORECASE)
METHOD = re.compile(r"criterio biocore|valor biocore", re.IGNORECASE)
# Un «Criterio BIOCORE» solo se ve si el MISMO texto dice que Luis lo firmó (el techo y la vigilia de la regla BAR,
# «Si, confirmo ambos», 2026-11-19), o si es la capacitancia venosa 2× de la sepsis, que no está firmada y por eso se
# declara «en revisión clínica» junto a la cifra (pendiente de la firma de Luis; ver la auditoría).
SIGNED_CRITERIA = ("firmado por Luis", "confirmado por Luis", "capacitancia venosa 2×")


# Textos FIRMADOS por Luis que nombran la palabra: cambiarlos pide su firma (se le informó el 2026-11-19). Cada uno se
# exceptúa por su fragmento exacto, y una prueba comprueba que el fragmento siga en su documento firmado.
SIGNED_TEXTS = {
    # Tema A7 firmado (teoría citada 2): «Detalle» del índice de fatiga.
    "(En BIOCORE, el índice de fatiga está \"no disponible\" con la señal demo, porque su espectro es plano: el criterio "
    "sigue siendo válido con una señal real.)": "docs/contenido/teoria_citada_2.md",
    # Términos y condiciones (ajustes del Art. I firmados el 2026-11-17): las categorías de procedencia.
    "con su criterio rotulado (con fuente, criterio propio de BIOCORE o heurística)": "docs/legal/textos_legales.md",
}


def _without_signed(text):
    for fragment in SIGNED_TEXTS:
        text = text.replace(fragment, "")
    return text


def _sweep(at):
    texts = visible_texts(at) + [_strip(e.value) for kind in ("markdown", "caption", "info", "warning")
                                 for e in getattr(at.sidebar, kind)]
    if any(r.label == "Sensor" for r in at.main.radio):
        for sensor in list(next(r for r in at.main.radio if r.label == "Sensor").options):
            for mode in list(next(r for r in at.main.radio if r.label == "Qué quieres hacer").options):
                next(r for r in at.main.radio if r.label == "Sensor").set_value(sensor).run()
                next(r for r in at.main.radio if r.label == "Qué quieres hacer").set_value(mode).run()
                texts += visible_texts(at)
    return texts


def _offenders(texts):
    out = set()
    for t in map(_without_signed, texts):
        if HEURISTIC.search(t):
            out.add(("heurística/demo", t.strip()[:160]))
        if METHOD.search(t) and not any(s in t for s in SIGNED_CRITERIA):
            out.add(("criterio sin firma", t.strip()[:160]))
    return sorted(out)


@pytest.mark.parametrize("url", _page_urls())
def test_ninguna_pagina_rotula_heuristica(url):
    at = AppTest.from_file(MAIN, default_timeout=240)
    at.session_state["biocore_start_page"] = url
    at.run()
    assert at.exception == [], at.exception
    assert _offenders(_sweep(at)) == []


@pytest.mark.parametrize("url,label,option", SOURCES)
def test_ninguna_fuente_rotula_heuristica(url, label, option):
    at = AppTest.from_file(MAIN, default_timeout=240)
    at.session_state["biocore_start_page"] = url
    at.run()
    next(r for r in at.sidebar.radio if r.label == label).set_value(option).run()
    assert at.exception == [], at.exception
    assert _offenders(_sweep(at)) == []


def test_el_guardia_atrapa_lo_que_vigila():
    assert _offenders(["FC : 75 — Heurística (de ingeniería, no de estudio de cohorte)"])
    assert _offenders(["Canales demo"])
    assert _offenders(["RMS — Criterio BIOCORE (metodología propia)"])
    assert not _offenders(["el techo de 3.0: Criterio BIOCORE firmado por Luis"])
    assert _offenders(["onda delta si ≥ 30 ms, criterio BIOCORE"]) and _offenders(["Tc valor BIOCORE"])
    assert _offenders(["el techo de 3.0, Criterio BIOCORE"])              # «techo» solo ya no basta
    assert _offenders(["Índice de riesgo heurístico (pesos fijos)"]) and _offenders(["(PENDING_VALIDATION)"])


def test_each_signed_exception_is_still_in_its_signed_document():
    for fragment, doc in SIGNED_TEXTS.items():
        assert " ".join(fragment.split()) in " ".join(Path(doc).read_text(encoding="utf-8").split()), doc


# ── Retiradas que decidió Luis ─────────────────────────────────────────────────────────────────────────────────────
def _open(url):
    at = AppTest.from_file(MAIN, default_timeout=240)
    at.session_state["biocore_start_page"] = url
    at.run()
    assert at.exception == [], at.exception
    return at


def test_biomarcadores_esta_retirado_y_dice_por_que():
    at = _open("biomarcadores")
    text = " ".join(visible_texts(at))
    assert "Retirado el 2026-11-19" in text and "sin fuente" in text
    assert "alimentar el motor de biomarcadores" not in text                # el contenido ya no se monta
    hub = _open("paciente")
    assert "biomarcadores" not in {e.proto.page for e in hub.main.get("page_link")}


def test_el_contenido_de_biomarcadores_queda_sin_montar():
    import ast
    from pathlib import Path

    tree = ast.parse(Path(MAIN).read_text(encoding="utf-8"))
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "id", None) ==
             "render_biomarkers_page"]
    assert calls == []                                                       # nadie lo llama: solo las pruebas


def test_fusion_de_sensores_queda_con_los_sensores_en_vivo():
    at = _open("multisensor")
    text = " ".join(visible_texts(at))
    assert "Canales demo" not in text and "Frecuencia cardíaca (detectada del ECG" not in text
    assert any(r.label == "Sensor" for r in at.main.radio)                  # el pulso por luz y la temperatura
    from app.supermodules import hubs

    caption = dict(c for _h, cards in hubs.PATIENT_GROUPS for c in cards)["multisensor"]
    assert "demostración" not in caption and "en vivo" in caption
