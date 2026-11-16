"""Fase 1 de la propuesta, tanda 2, PARTE A (2026-11-15): pulido del sistema de diseño y de la suite.

- Ningún «bpm» ni término en inglés de una lista llega al estudiante: se recorren las 21 páginas del menú (y las vistas
  de cada laboratorio) con AppTest y se lee TODO el texto visible (markdown, avisos, controles, pestañas, tablas y los
  textos de las gráficas Plotly). Las citas bibliográficas (en su idioma original) no contienen esos términos.
- PRIMARY nunca es color de TEXTO sobre el panel (4.44:1).
- Asimetría y curtosis con RR casi idénticos: «sin dato», no un número que SciPy declara poco fiable.
- fpdf sin avisos de obsolescencia (ln= y la sustitución de Arial).
"""

import json
import re
import warnings
from pathlib import Path

import numpy as np
import pytest
from streamlit.testing.v1 import AppTest

from app.utils.design_system import PALETTE, contrast_ratio

MAIN = str(Path("app/main.py").resolve())
VIEW_RADIO = "Capa de Exploración Cognitiva"

# «bpm» y términos en inglés que se encontraron en pantalla antes de esta tanda (barrido del 2026-11-15).
FORBIDDEN = re.compile(
    r"\bbpm\b|\bBPM\b|\bLab\b|\bSource\b|\bPower\b|Heart Rate|\bSinus\b|\bRhythm\b|Bundle Branch|Live Hardware|"
    r"\bSpindle\b|\bSeizure\b|\bArtifact\b|Clinical Note|\bDiscovery\b|\bPipeline\b|\bResilience\b|\binputs?\b|"
    r"\bEducational\b|\bwaves?\b|\bAnalysis\b|No acute findings|Routine monitoring|Motor Imagery|API key|"
    r"\bRun\b|\bRaw\b|\bVoltage\b|\bSignal\b|Clinical Findings|\bGenerated\b"
)


def _strip(html):
    return " ".join(re.sub(r"<[^>]+>", " ", str(html)).split())


def _plotly_texts(spec):
    fig = json.loads(spec)
    layout, out = fig.get("layout", {}), []

    def title(obj):
        t = obj.get("title") if isinstance(obj, dict) else None
        return t.get("text") if isinstance(t, dict) else (t if isinstance(t, str) else None)

    for key, value in layout.items():
        if isinstance(value, dict) and (key == "legend" or key.startswith(("xaxis", "yaxis", "scene"))):
            out.append(title(value))
    out.append(title(layout))
    out.extend(a.get("text") for a in layout.get("annotations", []) or [])
    out.extend(tr.get("name") for tr in fig.get("data", []) or [])
    return [_strip(t) for t in out if t]


def visible_texts(at):
    """Todo el texto que ve el estudiante en el estado actual de la app."""
    out = []
    for kind in ("markdown", "caption", "title", "header", "subheader", "info", "warning", "error", "success", "code"):
        out.extend(_strip(e.value) for e in getattr(at, kind))
    out.extend(f"{e.label} {e.value}" for e in at.metric)
    for kind in ("button", "radio", "selectbox", "multiselect", "slider", "select_slider", "number_input",
                 "text_input", "text_area", "checkbox", "toggle"):
        for e in getattr(at, kind, []):
            out.append(getattr(e, "label", "") or "")
            out.append(getattr(e, "help", "") or "")
            # AppTest ya entrega las opciones como las ve el estudiante (con su format_func aplicado)
            out.extend(str(o) for o in getattr(e, "options", []) or [])
    out.extend(str(e.value) for e in at.json)                        # p. ej. la tabla de potencias del EEG
    out.extend(e.label for e in at.tabs)
    out.extend(e.label for e in at.expander)
    out.extend(t for e in at.get("plotly_chart") for t in _plotly_texts(e.proto.spec))
    for e in at.dataframe:
        df = e.value
        out.extend(str(c) for c in df.columns)
        for col in df.columns:
            if df[col].dtype == object:
                out.extend(str(x) for x in df[col].head(60))
    return [t for t in out if t]


def _page_urls():
    import app.main as m

    return [url for _, url, *_ in m._page_specs()]


@pytest.mark.parametrize("url", _page_urls())
def test_no_bpm_and_no_listed_english_term_reaches_the_student(url):
    at = AppTest.from_file(MAIN, default_timeout=240)
    at.session_state["biocore_start_page"] = url
    at.run()
    assert at.exception == [], at.exception
    texts = visible_texts(at)
    radios = [r for r in at.main.radio if r.label == VIEW_RADIO]
    if radios:                                                  # cada vista del laboratorio
        for view in list(radios[0].options)[1:]:
            next(r for r in at.main.radio if r.label == VIEW_RADIO).set_value(view).run()
            assert at.exception == [], (view, at.exception)
            texts.extend(visible_texts(at))
    offenders = sorted({(m.group(0), t[:120]) for t in texts for m in [FORBIDDEN.search(t)] if m})
    assert offenders == [], offenders


def test_the_sweep_would_catch_what_it_was_written_for():
    for sample in ("FC=72 bpm", "Normal Sinus Rhythm", "ECG Source", "🫀 ECG Lab", "Live Hardware", "Power: Δ=1"):
        assert FORBIDDEN.search(sample), sample
    for spanish in ("Ritmo sinusal, FC 78 lpm (normal)", "Laboratorio de ECG", "Potencia: Δ=1", "NEWS2"):
        assert not FORBIDDEN.search(spanish), spanish


# ------------------------------------------------------------------------------------------------- PRIMARY como texto
def test_primary_is_never_a_text_color_on_the_panel():
    assert contrast_ratio(PALETTE.PRIMARY, PALETTE.SECONDARY_BACKGROUND) < 4.5          # la razón: 4.44:1
    text_use = re.compile(r"(?<![-\w])color\s*:\s*\{PALETTE\.PRIMARY\}|font(?:_color)?\s*=\s*(?:dict\()?\s*(?:color\s*=\s*)?PALETTE\.PRIMARY")
    for path in Path("app").rglob("*.py"):
        code = "\n".join(l for l in path.read_text(encoding="utf-8").splitlines() if not l.lstrip().startswith("#"))
        assert not text_use.search(code), path
    import tomllib

    theme = tomllib.loads(Path(".streamlit/config.toml").read_text(encoding="utf-8"))["theme"]
    assert theme["linkColor"].lower() != PALETTE.PRIMARY                               # los enlaces son texto


# ------------------------------------------------------------------------------------------- asimetría y curtosis
def test_skewness_and_kurtosis_are_nan_when_scipy_declares_them_unreliable():
    from src.feature_extraction import compute_psd, extract_features

    rr = np.full(20, 0.8333333)
    freqs, power = compute_psd(rr)
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)                # ya no se deja escapar el aviso de SciPy
        features = extract_features(rr, power, freqs)
    assert np.isnan(features["Skewness"]) and np.isnan(features["Kurtosis"])
    rr2 = 0.8 + 0.05 * np.random.default_rng(1).standard_normal(30)
    freqs, power = compute_psd(rr2)
    varied = extract_features(rr2, power, freqs)
    assert np.isfinite(varied["Skewness"]) and np.isfinite(varied["Kurtosis"])     # con variabilidad sí se calculan


def test_the_twin_ecg_classifier_shows_no_data_for_them_instead_of_a_number(tmp_path):
    """Con la sepsis aplicada el ECG sintético tiene FC fija sin variabilidad (RR casi idénticos): el panel del
    clasificador dice «sin dato» para asimetría y curtosis en vez de un número que SciPy declara poco fiable."""
    from domain.physiology.state import create_patient, init_db, make_engine, make_session_factory

    engine = make_engine(tmp_path / "t2_twin.db")
    init_db(engine)
    sf = make_session_factory(engine)
    with sf() as s:
        pid = create_patient(s, display_name="t2")

    def _script():
        import app.supermodules.twin_shell.pages as m
        m.run()

    at = AppTest.from_function(_script, default_timeout=180)
    at.session_state["twin_shell_ups_session_factory"] = sf
    at.session_state["twin_shell_ups_patient_id"] = pid
    at.run()
    at.selectbox(key="twin_shell_sepsis_horizon").set_value("24h")
    at.button(key="twin_shell_sepsis_apply").click().run()
    assert at.exception == []
    text = " ".join(_strip(m.value) for m in at.markdown)
    assert "Sin dato: falta Asimetría de RR" in text and "Sin dato: falta Curtosis de RR" in text
    assert "casi idénticos" in text


# ------------------------------------------------------------------------------------------------------------ fpdf
def test_pdf_exports_emit_no_fpdf_deprecation(tmp_path):
    from app.reporting import export_lab_report
    from src.rural_health.offline_support import generate_pdf_report

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = export_lab_report("Laboratorio de EEG", {"fs": 250}, notes="nota", findings={"a": "b"},
                                   out_dir=str(tmp_path))
        generate_pdf_report({"name": "Ana", "age": "30"}, "resumen", path=str(tmp_path / "rural" / "r.pdf"))
    assert result.endswith(".pdf")
    fpdf_warnings = [str(w.message) for w in caught if "fpdf" in (w.filename or "") or "ln" in str(w.message)
                     or "font" in str(w.message).lower()]
    assert not [m for m in fpdf_warnings if 'parameter "ln"' in m or "Substituting font" in m], fpdf_warnings
