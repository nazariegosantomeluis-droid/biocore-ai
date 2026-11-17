"""Pulido profesional (2026-11-16): ECG con estándar clínico, ancho, vistas unificadas y teoría citada.

PARTE A — papel ECG: escala de la cuadrícula (px/mm iguales en los dos ejes a 25 mm/s y 10 mm/mV [MCM]), pulso de
calibración de 1 mV al inicio de cada tira, demo a ≥ 500 muestras/s y orden del formato 3×4 con tira de ritmo de 10 s
[K2007]; el filtro de 0.5–40 Hz se rotula «de monitoreo» y la firma ya no dice «Filtros estándar AHA» ni «>99 %».
PARTE B — ancho máximo y medida de párrafo con el selector por clave de contenedor.
PARTE C — sin «Capa de Exploración Cognitiva»; prueba de alcanzabilidad: cada función de las vistas antiguas sigue en
la página.
PARTE D — «¿Qué significa…?» solo con capas firmadas; Bibliografía con todas las claves.
"""

from pathlib import Path

import numpy as np
import pytest
from streamlit.testing.v1 import AppTest

from app.utils import ecg_paper as P

MAIN = str(Path("app/main.py").resolve())


def _open(url, **state):
    at = AppTest.from_file(MAIN, default_timeout=240)
    at.session_state["biocore_start_page"] = url
    for k, v in state.items():
        at.session_state[k] = v
    at.run()
    assert at.exception == [], (url, at.exception)
    return at


def _figures(at):
    import json

    return [json.loads(e.proto.spec) for e in at.get("plotly_chart")]


def _paper(at):
    """Las figuras de papel ECG: las que llevan el pulso de calibración."""
    return [f for f in _figures(at) if any(t.get("name") == "Calibración 1 mV" for t in f["data"])]


# ── PARTE A ────────────────────────────────────────────────────────────────────────────────────────────────────────

def _px_per_mm(layout):
    """Plotly: con `scaleanchor`, una unidad de y ocupa `scaleratio` veces los píxeles de una unidad de x."""
    x_px_per_unit = 1.0                                   # cualquier ancho: la proporción no depende de él
    y_px_per_unit = layout["yaxis"]["scaleratio"] * x_px_per_unit
    return x_px_per_unit / P.MM_PER_S, y_px_per_unit / P.MM_PER_MV


def test_grid_scale_is_the_same_in_both_axes_at_25_mm_s_and_10_mm_mv():
    for fig in (P.strip_figure(np.zeros(5000), 500, filter_label=P.NO_FILTER_LABEL).to_plotly_json(),
                P.twelve_lead_figure({}, 500, filter_label=P.NO_FILTER_LABEL).to_plotly_json()):
        lay = fig["layout"]
        assert lay["yaxis"]["scaleanchor"] == "x"
        # la proporción se logra achicando el área, nunca estirando el rango (con "range" el papel crecía al redibujar)
        assert lay["xaxis"]["constrain"] == lay["yaxis"]["constrain"] == "domain"
        px_x, px_y = _px_per_mm(lay)
        assert px_x == pytest.approx(px_y)                                   # 0.04 s ocupa lo mismo que 0.1 mV
        assert lay["xaxis"]["dtick"] == pytest.approx(0.2) and lay["xaxis"]["minor"]["dtick"] == pytest.approx(0.04)
        assert lay["yaxis"]["dtick"] == pytest.approx(0.5) and lay["yaxis"]["minor"]["dtick"] == pytest.approx(0.1)
        assert "25 mm/s · 10 mm/mV" in lay["title"]["text"]


def _calibrations(fig):
    return [t for t in fig["data"] if t.get("name") == "Calibración 1 mV"]


def test_every_strip_starts_with_a_1_mv_calibration_pulse_5_mm_wide():
    strip = P.strip_figure(np.zeros(5000), 500, filter_label=P.NO_FILTER_LABEL).to_plotly_json()
    twelve = P.twelve_lead_figure({}, 500, filter_label=P.NO_FILTER_LABEL).to_plotly_json()
    for fig, rows in ((strip, 1), (twelve, 4)):
        cals = _calibrations(fig)
        assert len(cals) == rows
        for c in cals:
            assert max(c["y"]) - min(c["y"]) == pytest.approx(1.0)          # 1 mV = 10 mm
            top = [x for x, y in zip(c["x"], c["y"]) if y == max(c["y"])]
            assert max(top) - min(top) == pytest.approx(0.2)                 # 5 mm de ancho
            assert max(c["x"]) <= 0.0                                         # antes del trazo


def test_twelve_lead_layout_is_the_traditional_3x4_with_a_10_s_rhythm_strip():
    fs = 500
    t = np.arange(int(10 * fs)) / fs
    leads = {name: np.sin(2 * np.pi * t) for column in P.TWELVE_LEAD_COLUMNS for name in column}
    figure = P.twelve_lead_figure(leads, fs, filter_label=P.NO_FILTER_LABEL)
    fig = figure.to_plotly_json()
    labels = {a["text"].replace("<b>", "").replace("</b>", ""): (a["x"], a["y"]) for a in fig["layout"]["annotations"]}
    assert [c for c in P.TWELVE_LEAD_COLUMNS] == [("I", "II", "III"), ("aVR", "aVL", "aVF"), ("V1", "V2", "V3"),
                                                   ("V4", "V5", "V6")]
    for c, column in enumerate(P.TWELVE_LEAD_COLUMNS):
        xs = {round(labels[name][0], 3) for name in column}
        assert len(xs) == 1                                                   # una columna, un tramo de tiempo
        ys = [labels[name][1] for name in column]
        assert ys == sorted(ys, reverse=True)                                 # de arriba abajo
        if c:
            assert labels[column[0]][0] > labels[P.TWELVE_LEAD_COLUMNS[c - 1][0]][0]
    rhythm = np.asarray(next(tr for tr in figure.data if tr.name == "II ritmo").x)
    assert rhythm[-1] - rhythm[0] == pytest.approx(10.0, abs=0.01)
    assert any("tira de ritmo, 10 s" in k for k in labels)


def test_the_monitor_demo_is_sampled_at_500_hz_and_drawn_on_paper():
    from app.main import ECG_DEMO_FS

    assert ECG_DEMO_FS >= 500
    at = _open("ecg")
    papers = _paper(at)
    assert papers, "el Monitoreo no dibuja el papel ECG"
    assert "500 muestras/s" in papers[0]["layout"]["title"]["text"]
    assert any("**Muestreo:** 500 Hz" in m.value for m in at.markdown)


def test_the_ecg_banner_no_longer_claims_aha_filters_or_99_percent_and_links_its_report():
    from app.main import _ECG_VALIDATION_DETAIL

    assert "AHA" not in _ECG_VALIDATION_DETAIL and "99" not in _ECG_VALIDATION_DETAIL
    assert "monitoreo" in _ECG_VALIDATION_DETAIL and "[K2007]" in _ECG_VALIDATION_DETAIL
    assert "docs/validation/ecg_hr_detector_bank/" in _ECG_VALIDATION_DETAIL
    assert Path("docs/validation/ecg_hr_detector_bank/round6_robustez/cohort_results.json").exists()


def test_the_cohort_report_does_not_support_99_percent_sensitivity():
    """Por qué se retiró la cifra: lo que mide el informe del repositorio."""
    import json

    rows = json.loads(Path("docs/validation/ecg_hr_detector_bank/round6_robustez/cohort_results.json")
                      .read_text(encoding="utf-8"))["rows"]
    pooled = sum(r["n_beats_gt"] * r["sens_tkeo"] for r in rows) / sum(r["n_beats_gt"] for r in rows)
    assert len(rows) == 25 and pooled < 0.99


def test_the_twelve_lead_page_labels_its_monitoring_filter_and_its_synthetic_origin():
    at = _open("ecg")
    titles = [f["layout"]["title"]["text"] for f in _paper(at)]
    assert any("filtro de monitoreo 0.5–40 Hz, no diagnóstico [K2007]" in t for t in titles)
    assert any("500 muestras/s" in t for t in titles)
    text = " ".join(c.value for c in at.caption)
    assert "Trazado sintético generado por BIOCORE" in text
    assert not any("Aplicar filtro banda" in c.label for c in at.checkbox)


def test_the_real_ptb_record_is_drawn_with_its_provenance():
    at = _open("ecg")
    radio = next(r for r in at.radio if r.label == "Origen de la señal:")
    radio.set_value("Registro real (PTB s0010_re, PhysioNet)").run()
    assert at.exception == []
    text = " ".join(c.value for c in at.caption)
    assert "Registro real: PTB Diagnostic ECG Database, registro s0010_re (licencia ODC-By 1.0)" in text
    assert "Bousseljot" in text and "Trazado sintético" not in text
    paper = [f for f in _paper(at) if len(_calibrations(f)) == 4]
    assert paper and len([t for t in paper[0]["data"] if t.get("name") not in ("Calibración 1 mV",)]) >= 13


# ── PARTE B ────────────────────────────────────────────────────────────────────────────────────────────────────────

def test_content_width_and_paragraph_measure_use_the_container_key_selector():
    import inspect

    import app.main as m
    from app.utils import design_system as ds

    css = inspect.getsource(ds.inject_global_theme)
    assert ".st-key-{CONTENT_KEY} {{ max-width: {CONTENT_MAX_PX}px; margin-left: auto; margin-right: auto; }}" in css
    assert ".st-key-{CONTENT_KEY} p, .st-key-{CONTENT_KEY} li {{ max-width: {MEASURE_CH}ch; }}" in css
    assert ds.CONTENT_MAX_PX == 1200 and ds.MEASURE_CH == 75
    assert "with st.container(key=CONTENT_KEY):" in inspect.getsource(m.main)


# ── PARTE C ────────────────────────────────────────────────────────────────────────────────────────────────────────

def test_no_page_or_code_keeps_the_view_selector():
    for path in Path("app").rglob("*.py"):
        code = "\n".join(l for l in path.read_text(encoding="utf-8").splitlines() if not l.lstrip().startswith("#"))
        assert "'Capa de Exploración Cognitiva'" not in code and "render_view_selector(" not in code, path


def _labels(at):
    out = set()
    for kind in ("button", "slider", "selectbox", "multiselect", "radio", "checkbox"):
        out.update(getattr(e, "label", "") for e in getattr(at, kind))
    out.update(e.label for e in at.expander)
    out.update(e.label for e in at.tabs)
    return out


# Lo que había en cada vista antigua y dónde quedó (la tabla vieja → nueva del CHANGELOG, comprobada).
REACHABLE = {
    "ecg": {
        "Clínica": ["¿Qué significa Frecuencia cardíaca?"],          # la demo no guarda al gemelo (lo dice)
        # Cierre del pulido: el material sin fuente de Educativa y «Simular» (controles que no movían nada) ya no se
        # montan; su código queda en `_ecg_monitor_unsourced_material()` (ver tests/test_cierre_pulido.py).
        "Educativa → Teoría": ["Teoría"],
        "Investigación → Cómo se calcula": ["Cómo se calcula", "Exportar segmento para investigación",
                                            "📓 Generar notebook reproducible desde esta señal"],
        "IA → Narración con IA (opcional)": ["Narración con IA (opcional)"],
    },
    "emg": {
        "Investigación → Cómo se calcula": ["Cómo se calcula", "Exportar EMG para investigación"],
        "Simulación → Simular": ["Simular"],
        "IA → Narración con IA (opcional)": ["Narración con IA (opcional)"],
        "Tutorial → pestaña": ["Laboratorio"],
    },
    "multisensor": {
        "Educativa → arriba": ["Canales"],
        "Investigación → Cómo se calcula": ["Cómo se calcula", "Exportar multisensor para investigación"],
        "Simulación → Simular": ["Simular", "FC (lpm)", "SpO₂ (%)", "FR (resp/min)"],
        "IA → Narración con IA (opcional)": ["Narración con IA (opcional)"],
        "Sensores en vivo → pestaña": ["Canales demo", "Sensor", "Qué quieres hacer"],
    },
    "respiratorio": {
        "Investigación → Cómo se calcula": ["Cómo se calcula"],
        "Simulación → Simular": ["Simular", "Frecuencia respiratoria (resp/min)", "Volumen corriente / profundidad (L)"],
        "Teoría": ["Teoría"],
    },
    "pacientes": {
        "Clínica": ["Guardar nuevo estado"],
        "IA → Narración con IA (opcional)": ["Narración con IA (opcional)"],
    },
}


@pytest.mark.parametrize("url", sorted(REACHABLE))
def test_every_function_of_the_old_views_is_still_on_the_page(url):
    at = _open(url)
    labels = _labels(at)
    assert "Capa de Exploración Cognitiva" not in labels
    for where, needed in REACHABLE[url].items():
        for label in needed:
            assert any(label in lab for lab in labels), (url, where, label)


def test_the_narrators_are_reachable_and_still_honest_without_a_key():
    from app.utils.ai_session import AI_OFF

    for url in ("ecg", "emg", "multisensor", "pacientes"):
        at = _open(url)
        expander = next(e for e in at.expander if e.label == "Narración con IA (opcional)")
        assert not expander.proto.expanded
        if url != "pacientes":                                     # pacientes: sin estado guardado no hay qué narrar
            assert any(AI_OFF in w.value for w in at.warning), url


def test_the_old_differential_example_without_source_is_gone_and_unsourced_material_is_labeled():
    at = _open("ecg")
    text = " ".join(m.value for m in at.markdown) + " ".join(c.value for c in at.caption)
    assert "Diagnóstico diferencial (ejemplo)" not in text and "Infarto agudo de miocardio anterior (LAD)" not in text
    assert "[Sin fuente]" not in text                       # cierre del pulido: el material sin fuente no se monta


# ── PARTE D ────────────────────────────────────────────────────────────────────────────────────────────────────────

def test_heart_rate_explanation_is_the_signed_topic_2_and_nothing_generic():
    from app.supermodules.learn_theory import SIGNED_HEART_RATE

    at = _open("ecg")
    expander = next(e for e in at.expander if e.label == "¿Qué significa Frecuencia cardíaca?")
    inside = " ".join(m.value for m in expander.markdown) + " ".join(c.value for c in expander.caption)
    assert SIGNED_HEART_RATE.idea in inside and "Fuente: [MCM] · [RCP2017]" in inside
    for generic in ("Principal indicador de estado cardiovascular", "Ejercicio, arritmias, fármacos",
                    "Cambios bruscos pueden indicar arritmia", "¿Por qué importa?", "¿Qué la afecta?"):
        assert generic not in inside


def test_metric_explanations_only_accept_a_signed_topic():
    import inspect

    from app.main import render_metric_explained

    params = set(inspect.signature(render_metric_explained).parameters)
    assert params == {"title", "value", "unit", "topic"}           # ya no se puede pasar texto suelto sin fuente


def test_bibliography_lists_every_signed_key_and_the_repo_citations_with_links():
    from app.supermodules.bibliography import SIGNED, SIGNED_KEYS, repo_references

    assert set(SIGNED_KEYS) == {"K2007", "W2009", "RCP2017", "B2012", "E2009", "IFCN2017", "MCM", "CS2023",
                                "AR2025", "KORS1990", "VZ2014"}
    doc = Path("docs/contenido/teoria_citada.md").read_text(encoding="utf-8")
    for key in SIGNED_KEYS:
        assert f"**[{key}]**" in doc                                       # las mismas claves que el documento
    assert "Chapa-Rodriguez A" in next(r.text for r in SIGNED if r.key == "CS2023")    # metadatos completados
    at = _open("bibliografia")
    text = " ".join(m.value for m in at.markdown)
    for key in SIGNED_KEYS:
        assert f"**[{key}]**" in text, key
    assert "https://doi.org/10.1111/anec.12206" in text                    # Oehler 2014, auditado y completado
    for ref in repo_references():
        assert ref.text in text
        assert " (" not in ref.text.split(". ")[-1] or "publicada" in ref.text or "licencia" in ref.text


def test_theory_blocks_link_their_keys_to_the_bibliography():
    at = _open("teoria")
    links = [e.proto.page for e in at.main.get("page_link")]
    assert any("bibliografia" in p for p in links)
    titles = [m.value[5:] for m in at.main.markdown if m.value.startswith("#### ")]
    assert "Derivaciones e isquemia: qué sugiere cada grupo" in titles and "Las 12 derivaciones del ECG" not in titles
    warning = " ".join(m.value for m in at.main.markdown)
    assert "no rotular derivaciones individuales" in warning                  # la advertencia de la AHA [W2009]
