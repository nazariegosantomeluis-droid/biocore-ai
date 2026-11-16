"""Fase 1 de la propuesta, tanda 2, PARTE C (2026-11-15): primera vista de las pantallas más usadas.

Sin cambiar qué se calcula, solo el orden y lo que se ve al abrir. Los paneles «visibles al abrir» se cuentan en el
árbol de AppTest con el mismo criterio del diagnóstico (métricas, tarjetas, gráficas, tablas, avisos y expanders),
sin entrar en expanders cerrados ni en pestañas que no son la activa.
"""

import inspect
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

MAIN = str(Path("app/main.py").resolve())
_PANEL_TYPES = {"metric", "plotly_chart", "arrow_data_frame", "dataframe", "json", "code", "table", "image",
                "info", "warning", "error", "success", "pyplot", "deck_gl_json_chart", "vega_lite_chart",
                "arrow_vega_lite_chart"}


def _open(url):
    at = AppTest.from_file(MAIN, default_timeout=240)
    at.session_state["biocore_start_page"] = url
    at.run()
    assert at.exception == [], at.exception
    return at


def _children(node):
    kids = getattr(node, "children", None)
    return list(kids.values()) if isinstance(kids, dict) else []


def visible_panels(node):
    """Paneles a la vista al abrir: no entra en expanders cerrados ni en pestañas no activas."""
    count = 0
    for child in _children(node):
        kind = getattr(child, "type", "")
        if kind == "expander":
            count += 1
            if child.proto.expanded:
                count += visible_panels(child)
        elif kind == "tab_container":
            tabs = _children(child)
            count += visible_panels(tabs[0]) if tabs else 0
        elif kind == "markdown":
            count += 1 if "border" in str(child.value) and "<div" in str(child.value) else 0
        elif kind in _PANEL_TYPES:
            count += 1
        else:
            count += visible_panels(child)
    return count


@pytest.mark.parametrize("url", ["hrv", "eeg", "biomarcadores"])
def test_at_most_five_panels_are_visible_when_the_page_opens(url):
    at = _open(url)
    assert visible_panels(at.main) <= 5, url


def test_the_ecg_trace_comes_before_the_heart_rate_and_the_save_panel():
    import app.main as m

    src = inspect.getsource(m.render_ecg_monitor_page)
    clinical = src[src.index("if view == 'Clínica':"):src.index("elif view == 'Educativa':")]
    assert clinical.index("st.plotly_chart") < clinical.index("render_metric_explained('Frecuencia cardíaca'")
    assert clinical.index("st.plotly_chart") < clinical.index("_render_ecg_save_to_twin(")
    assert 'render_section_header("Monitoreo")' not in src                         # ya lo dice la pestaña


def test_the_respiratory_status_notice_is_one_line_with_the_detail_on_demand():
    from app.supermodules.respiratory_lab.pages import RESPIRATORY_STATUS_NOTICE, RESPIRATORY_STATUS_SUMMARY

    at = _open("respiratorio")
    summary = next(e for e in at.main.expander if e.label == RESPIRATORY_STATUS_SUMMARY)
    assert not summary.proto.expanded and "\n" not in RESPIRATORY_STATUS_SUMMARY
    assert any(i.value == RESPIRATORY_STATUS_NOTICE for i in summary.info)            # el detalle, intacto


def test_the_twin_opens_on_the_case_and_the_digital_body_with_the_rest_folded():
    at = _open("gemelo")
    labels = [e.label for e in at.main.expander]
    case = next(e for e in at.main.expander if e.label.startswith("🎓 Caso clínico interactivo"))
    assert case.proto.expanded
    for folded in ("🎛️ Ajustar señales fisiológicas (simulación)", "🔁 Barorreflejo: el lazo cerrado por dentro",
                   "🔗 Evaluar acoplamiento neuro-cardíaco (BAR → FC)"):
        e = next(x for x in at.main.expander if x.label == folded)
        assert not e.proto.expanded, folded
    texts = [m.value for m in at.main.markdown]
    body = next(i for i, t in enumerate(texts) if "Cuerpo Digital — tu estado actual" in t)
    grid = next(i for i, t in enumerate(texts) if "Toca un órgano para explorar" in t)
    assert body < grid and "🎓 Caso clínico interactivo (diagnóstico ciego) — v1" in labels
