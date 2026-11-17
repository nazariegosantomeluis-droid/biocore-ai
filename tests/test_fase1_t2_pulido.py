"""Fase 1 de la propuesta, tanda 2, PARTE A (2026-11-15): pulido del sistema de diseño y de la suite.

- Ningún «bpm» ni término en inglés de una lista llega al estudiante: se recorren las 21 páginas del menú (y las vistas
  de cada laboratorio) con AppTest y se lee TODO el texto visible (markdown, avisos, controles, pestañas, tablas y los
  textos de las gráficas Plotly). Los títulos de obras citadas y los nombres propios en su idioma original se exceptúan
  uno por uno, por su texto exacto (`CITED_TITLES_AND_PROPER_NAMES`).
- Contención (2026-11-16): el mismo recorrido busca indicaciones de tratamiento sin cita (`TREATMENT` de
  `test_integracion_contencion.py`) en TODAS las páginas y fuentes, no solo en 12 Derivaciones.
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
from test_integracion_contencion import TREATMENT

MAIN = str(Path("app/main.py").resolve())
VIEW_RADIO = "Capa de Exploración Cognitiva"

# «bpm» y términos en inglés que se encontraron en pantalla antes de esta tanda (barrido del 2026-11-15).
FORBIDDEN = re.compile(
    r"\bbpm\b|\bBPM\b|\bLab\b|\bSource\b|\bPower\b|Heart Rate|\bSinus\b|\bRhythm\b|Bundle Branch|Live Hardware|"
    r"\bSpindle\b|\bSeizure\b|\bArtifact\b|Clinical Note|\bDiscovery\b|\bPipeline\b|\bResilience\b|\binputs?\b|"
    r"\bEducational\b|\bwaves?\b|\bAnalysis\b|No acute findings|Routine monitoring|Motor Imagery|API key|"
    r"\bRun\b|\bRaw\b|\bVoltage\b|\bSignal\b|Clinical Findings|\bGenerated\b"
)


# Integración con main (2026-11-16): títulos de obras citadas y nombres propios en su idioma original. Se quitan por su
# texto EXACTO antes de buscar; cualquier otra aparición del término sigue fallando.
CITED_TITLES_AND_PROPER_NAMES = (
    "AD8232 Heart Rate Monitor Hookup Guide",                     # guía de SparkFun (tutorial de la placa ECG)
    "the ST segment, T and U waves, and the QT interval",          # Rautaharju 2009, Circulation
    "Heart Rhythm 20",                                             # revista (Page 2015)
    "Artifact and recording concepts in EEG",                     # Tatum 2011, J Clin Neurophysiol
    "Lab Streaming Layer",                                        # nombre propio del protocolo LSL
    "*Heart Rhythm*",                                             # revista de [K2007] en la Bibliografía (pulido)
)

# Pulido profesional (2026-11-16): frases del documento FIRMADO (`docs/contenido/teoria_citada.md`) que el patrón amplio
# de tratamientos atrapa sin ser una indicación de tratamiento. Se quitan por su texto EXACTO y una prueba exige que
# sigan estando, tal cual, en el documento firmado; cualquier otra aparición sigue fallando.
SIGNED_NON_TREATMENT = (
    "la recomendación es una frecuencia de corte superior de al menos 150 Hz",   # tema 1 [K2007]: filtro del equipo
)


def _without_citations(text):
    for name in CITED_TITLES_AND_PROPER_NAMES + SIGNED_NON_TREATMENT:
        text = text.replace(name, "")
    return text


def test_every_signed_exemption_is_literally_in_the_signed_document():
    doc = Path("docs/contenido/teoria_citada.md").read_text(encoding="utf-8")
    for phrase in SIGNED_NON_TREATMENT:
        assert phrase in doc and TREATMENT.search(phrase), phrase       # firmada, y de verdad la atrapaba el patrón


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
    # Pulido profesional (2026-11-16): ya no hay selector de vistas (`VIEW_RADIO`); las secciones de cada laboratorio
    # están en la misma página (plegadas: AppTest lee su contenido igual) y las pestañas se dibujan todas.
    assert not [r for r in at.main.radio if r.label == VIEW_RADIO], url
    # Integración con main: cada sensor × cada modo de «Sensores en vivo» (pulso por luz y temperatura; medir y
    # tutorial), ahora una pestaña de Multisensor.
    if any(r.label == "Sensor" for r in at.main.radio):
        sensors = list(next(r for r in at.main.radio if r.label == "Sensor").options)
        modes = list(next(r for r in at.main.radio if r.label == "Qué quieres hacer").options)
        for sensor in sensors:
            for mode in modes:
                next(r for r in at.main.radio if r.label == "Sensor").set_value(sensor).run()
                next(r for r in at.main.radio if r.label == "Qué quieres hacer").set_value(mode).run()
                assert at.exception == [], (sensor, mode, at.exception)
                texts.extend(visible_texts(at))
    texts = [_without_citations(t) for t in texts]
    offenders = sorted({(m.group(0), t[:120]) for t in texts for m in [FORBIDDEN.search(t)] if m})
    assert offenders == [], offenders
    treatments = sorted({(m.group(0), t[:120]) for t in texts for m in [TREATMENT.search(t)] if m})
    assert treatments == [], treatments
    # Cierre del pulido (2026-11-16): el material rotulado «[Sin fuente]» ya no se monta en ninguna página.
    assert not [t[:120] for t in texts if "[Sin fuente]" in t], url


# Integración con main: las fuentes de cada laboratorio que no son la de inicio (sin red ni puerto: MIT-BIH/PTB-XL
# piden red; «Hardware ESP32 en vivo» del ECG busca puertos en segundo plano y lo cubre `test_ecg_live_app.py`).
SOURCES = [
    ("ecg", "Origen del ECG", "CSV local"),
    ("ecg", "Origen del ECG", "Caso clínico (61 disponibles)"),
    ("eeg", "Origen de datos", "Cargar EEG desde CSV"),
    ("eeg", "Origen de datos", "Hardware EEG en vivo"),
    ("emg", "Origen EMG", "CSV"),
    ("emg", "Origen EMG", "Sensor en vivo (ESP32 + MyoWare)"),
    ("hrv", "Origen de la HRV", "Serie RR manual"),
]


@pytest.mark.parametrize("url,label,option", SOURCES)
def test_no_bpm_and_no_listed_english_term_in_the_other_sources(url, label, option):
    at = AppTest.from_file(MAIN, default_timeout=240)
    at.session_state["biocore_start_page"] = url
    at.run()
    next(r for r in at.sidebar.radio if r.label == label).set_value(option).run()
    assert at.exception == [], at.exception
    texts = [_without_citations(t) for t in visible_texts(at) + [_strip(e.value) for kind in
             ("markdown", "caption", "info", "warning", "error", "success") for e in getattr(at.sidebar, kind)]]
    offenders = sorted({(m.group(0), t[:120]) for t in texts for m in [FORBIDDEN.search(t)] if m})
    assert offenders == [], offenders
    treatments = sorted({(m.group(0), t[:120]) for t in texts for m in [TREATMENT.search(t)] if m})
    assert treatments == [], treatments
    assert not [t[:120] for t in texts if "[Sin fuente]" in t], (url, option)      # cierre del pulido


def test_the_citation_exemption_removes_only_the_exact_title():
    assert FORBIDDEN.search(_without_citations("Monitor de Heart Rate"))
    assert not FORBIDDEN.search(_without_citations("SparkFun, «AD8232 Heart Rate Monitor Hookup Guide»"))


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
    """Con la sepsis aplicada el ECG sintético tiene FC fija sin variabilidad (RR casi idénticos): el gemelo no
    muestra un número de asimetría ni de curtosis que SciPy declara poco fiable (desde la contención del 2026-11-16,
    ningún número del clasificador: el panel está en revisión)."""
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
    # Contención (2026-11-16): el panel del clasificador se ocultó (leía QRS/PR/QTc = 0 ms «dentro de rango»); con
    # él se fue todo número suyo. La garantía de «sin dato» con RR idénticos sigue probada sobre el clasificador
    # (`test_contencion_prueba.py::test_the_classifier_still_declines_skewness_and_kurtosis_with_identical_rr`).
    from app.supermodules.twin_shell.pages import ECG_CLASSIFIER_IN_REVIEW

    text = " ".join(_strip(t) for t in visible_texts(at))
    assert "Asimetría de RR" not in text and "Curtosis de RR" not in text
    assert ECG_CLASSIFIER_IN_REVIEW in text


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
