"""Fase 1 de la propuesta, tanda 2, PARTE B (2026-11-15): teoría en capas en Aprender.

Regla firmada: ningún contenido médico nuevo. Cada capa de cada tema es texto que YA existía en el repositorio
(con su cita o etiqueta); aquí se comprueba, línea por línea, contra el archivo de origen. Capa sin contenido con
fuente: se omite (no hay relleno) y se lista como pendiente.
"""

import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from app.supermodules import learn_theory as LT
from app.utils.design_system import THEORY_NO_SOURCE, TheoryTopic

MAIN = str(Path("app/main.py").resolve())
ALL_TOPICS = [t for topics in LT.LEARN_TOPICS.values() for t in topics]


def _norm(text):
    return " ".join(re.findall(r"[\wáéíóúñü%≥≤₂]+", text.lower()))


@pytest.mark.parametrize("topic", ALL_TOPICS, ids=lambda t: t.title)
def test_every_layer_is_text_that_already_existed_in_its_origin_file(topic):
    # Pulido profesional: un tema puede salir de su archivo del repositorio y/o del documento firmado por Luis
    # (`docs/contenido/teoria_citada.md`); cada línea tiene que estar, literal, en alguno de ellos.
    origin = " || ".join(_norm(Path(f).read_text(encoding="utf-8")) for f in LT.ORIGINS[topic.title])
    for layer in (topic.idea, topic.mechanism, topic.detail if isinstance(topic.detail, str) else None):
        if not layer:
            continue
        for line in layer.split("\n"):
            if _norm(line):
                assert _norm(line) in origin, (topic.title, line)


def test_no_layer_is_filler_and_every_detail_names_its_source_or_says_it_has_none():
    for t in ALL_TOPICS:
        assert t.idea or t.mechanism or t.detail, t.title
        for layer in (t.idea, t.mechanism):
            assert layer is None or layer.strip(), t.title            # vacía = omitida, nunca una cadena de relleno
        if t.detail and t.source is None:
            assert (t.title, "fuente") in {(a, b) for a, b, _ in LT.PENDING_LAYERS}, t.title
    omitted = {(t.title, "mecanismo") for t in ALL_TOPICS if not t.mechanism}
    assert omitted <= {(a, b) for a, b, _ in LT.PENDING_LAYERS}             # cada omisión queda reportada


def test_the_three_learn_pages_use_the_single_component_and_open_layers_on_demand():
    # Teoría citada 2 (2026-11-17): Referencias suma los 9 temas de EMG y los 9 de HRV.
    for url, n_topics in (("teoria", 6), ("referencias", 26), ("ecg-3d", 1)):
        at = AppTest.from_file(MAIN, default_timeout=240)
        at.session_state["biocore_start_page"] = url
        at.run()
        assert at.exception == [], (url, at.exception)
        titles = [m.value for m in at.main.markdown if m.value.startswith("#### ")]
        assert [t[5:] for t in titles[:n_topics]] == [t.title for t in LT.LEARN_TOPICS[url]], url
        expanders = [e.label for e in at.main.expander]
        topics = LT.LEARN_TOPICS[url]
        assert expanders.count("Detalle y fuente") == sum(1 for t in topics if t.detail)
        assert expanders.count("¿Cómo funciona? — mecanismo") == sum(1 for t in topics if t.mechanism)
        captions = " ".join(c.value for c in at.main.caption)
        for t in topics:
            if t.detail:
                assert f"Fuente: {t.source or THEORY_NO_SOURCE}" in captions, t.title


def test_the_component_omits_missing_layers_instead_of_filling_them():
    def _script():
        from app.utils.design_system import TheoryTopic, render_theory_topic

        render_theory_topic(TheoryTopic(title="Solo idea", idea="Una frase."))

    at = AppTest.from_function(_script)
    at.run()
    assert not at.expander and [m.value for m in at.markdown] == ["#### Solo idea", "Una frase."]


def test_the_learn_pages_keep_every_citation_they_had():
    from clinical.calculators import NEWS2_CITATION
    from app.supermodules.respiratory_lab.views import EDUCATION_CITATION

    sources = " ".join(t.source or "" for t in ALL_TOPICS)
    assert NEWS2_CITATION in sources and EDUCATION_CITATION in sources and "Berry RB et al." in sources
    # Pulido profesional (2026-11-16): el VCG cita ahora [VZ2014] y [KORS1990] (firmados); Oehler 2014 se auditó y
    # quedó con su referencia completa en el panel del VCG y en la Bibliografía.
    assert "[KORS1990]" in sources and "[VZ2014]" in sources
    from app.supermodules.bibliography import OEHLER_2014
    from src.signals.ecg.vcg import QRST_ANGLE_CITATION

    assert "Oehler A, Feldman T" in QRST_ANGLE_CITATION and "doi:10.1111/anec.12206" in OEHLER_2014.links[0][0]


def test_signed_topics_cite_only_keys_that_the_bibliography_lists_and_nothing_unsigned_remains():
    """Pulido profesional: todo tema nuevo sale del documento firmado y cada clave que cita existe en la Bibliografía.
    La tabla de 12 derivaciones sin cita (lead_explanations) ya no se muestra en Aprender ni en la Academia."""
    import re as _re

    from app.supermodules.bibliography import SIGNED_KEYS

    signed_doc = Path(LT.SIGNED_DOC).read_text(encoding="utf-8")
    assert "☑ firmado" in signed_doc and "☐" not in signed_doc                 # la hoja de firma, entera
    for t in ALL_TOPICS:
        text = " ".join(x for x in (t.idea, t.mechanism, t.detail if isinstance(t.detail, str) else "", t.source) if x)
        for key in _re.findall(r"\[([A-Z][A-Z0-9]+)\]", text):
            assert key in SIGNED_KEYS, (t.title, key)
        assert ("[" in (t.source or "")) or LT.SIGNED_DOC not in LT.ORIGINS[t.title] or t.title in (
            LT.HOW_MEASURED.title, LT.EEG_BANDS.title), t.title
    assert not hasattr(LT, "TWELVE_LEADS")
    src = Path("app/supermodules/academia/pages.py").read_text(encoding="utf-8")
    assert "leads = lead_explanations()" not in src and "SIGNED_ISCHEMIA" in src
