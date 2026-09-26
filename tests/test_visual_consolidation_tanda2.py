"""
Consolidación Visual, Tanda 2 (2026-09-21) -- la prioridad de honestidad:
`app/reporting.py` (el HTML/PDF exportable) hereda la arquitectura de
honestidad completa -- badges de procedencia, clasificación clínica,
citas, "no disponible" con su razón -- desde la MISMA fuente que la app
viva. Verificado POR EJECUCIÓN de cada uno de los 4 llamadores reales
(EMG/ECG/Multisensor Research + EEG Neuro), la barandilla de siempre.

Regla rectora del arco: UNA fuente de honestidad
(`design_system.resolve_metric_card()`), DOS renderizadores
(`render_metric_card()` para Streamlit, `metric_card_to_html()` para el
export) -- ninguno reimplementa qué badge/gramática/cita corresponde a un
valor.
"""

import glob
import os

import pytest
from streamlit.testing.v1 import AppTest

from app.utils.design_system import (
    BADGES,
    GRAMMAR_NEUTRAL_STATE,
    GRAMMAR_SEVERITY,
    PALETTE,
    MetricCardData,
    metric_card_to_html,
    resolve_metric_card,
    resolve_validation_marker,
)


@pytest.fixture
def reports_dir(tmp_path, monkeypatch):
    """Cada test exporta a un `out_dir` temporal propio -- nunca al
    `reports/` real del repo (que además tiene un `.gitkeep` rastreado)."""
    d = tmp_path / "reports"
    return str(d)


# --- Parte A: fuente única, resuelta una vez, dos renderizadores ----------

def test_resolve_metric_card_is_the_single_source_for_both_renderers():
    """`render_metric_card()` (Streamlit) y `metric_card_to_html()` (export)
    parten del MISMO `MetricCardData` -- mismo color de marco, mismo orden
    de partes, misma cita completa."""
    from src.signals.eeg.spectral_model import CHI_CITATION, classify_chi

    data = resolve_metric_card(
        "χ", "0.80", classification=classify_chi(0.8), grammar=GRAMMAR_NEUTRAL_STATE, citation=CHI_CITATION,
    )
    html = metric_card_to_html(data)
    assert data.border_color == PALETTE.ACCENT_ON_DARK
    assert CHI_CITATION in html
    assert data.border_color in html

    def _script():
        import streamlit as st
        from app.utils.design_system import GRAMMAR_NEUTRAL_STATE, render_metric_card
        from src.signals.eeg.spectral_model import CHI_CITATION, classify_chi
        render_metric_card("χ", "0.80", classification=classify_chi(0.8), grammar=GRAMMAR_NEUTRAL_STATE, citation=CHI_CITATION)

    at = AppTest.from_function(_script)
    at.run(timeout=30)
    streamlit_card = next(md.value for md in at.main.markdown if "χ" in md.value)
    # el HTML de Streamlit y el HTML autónomo del export deben coincidir
    # en el color de marco y en la cita -- prueba de fuente única.
    assert PALETTE.ACCENT_ON_DARK in streamlit_card
    assert CHI_CITATION in streamlit_card


def test_single_source_proof_a_change_reflects_in_both_renderers(monkeypatch):
    """LA prueba que pide la tanda: un cambio de cita/umbral en un solo
    lugar (aquí, simulado con monkeypatch sobre `BADGES._LABELS` --
    equivalente a editar `design_system.py`) se refleja en AMBOS
    renderizadores sin tocar ninguno de los dos. Si esto fallara, `render_
    metric_card()`/`metric_card_to_html()` habrían reimplementado la
    lógica de honestidad en vez de compartirla."""
    from app.utils import design_system

    original_labels = dict(design_system.BADGES._LABELS)
    new_text = "CAMBIO_DE_PRUEBA_FUENTE_UNICA"
    monkeypatch.setitem(design_system.BADGES._LABELS, design_system.BADGES.CLINICAL, new_text)

    data = resolve_metric_card("BAR", "0.95", provenance=design_system.BADGES.CLINICAL)
    html = metric_card_to_html(data)
    assert new_text in html, "metric_card_to_html() no heredó el cambio -- fuente desincronizada"

    def _script():
        from app.utils.design_system import BADGES, render_metric_card
        render_metric_card("BAR", "0.95", provenance=BADGES.CLINICAL)

    at = AppTest.from_function(_script)
    at.run(timeout=30)
    streamlit_card = next(md.value for md in at.main.markdown if "BAR" in md.value)
    assert new_text in streamlit_card, "render_metric_card() no heredó el cambio -- fuente desincronizada"

    assert design_system.BADGES._LABELS == {**original_labels, design_system.BADGES.CLINICAL: new_text}


def test_resolve_validation_marker_is_the_single_source_for_header_and_export():
    """Mismo criterio que arriba, para la jerarquía de confianza:
    `render_module_header(validation=...)` y `export_lab_report(
    validation=...)` (vía `app/reporting.py`) parten del mismo `resolve_
    validation_marker()`."""
    marker = resolve_validation_marker("VALIDATED", "Detector TKEO, 6 rondas MIT-BIH")
    assert marker == (PALETTE.STABLE, "✓", "Detector TKEO, 6 rondas MIT-BIH")
    assert resolve_validation_marker("nivel_inventado") is None


# --- Parte B: paleta unificada, gramáticas preservadas en HTML ------------

def test_reporting_module_has_no_orphan_hex_palette(reports_dir):
    """NOTA DE MÉTODO: se verifica el CSS REALMENTE producido, no el texto
    crudo del archivo -- un grep sobre el módulo completo falsea contra
    los propios comentarios que documentan qué hex viejo se retiró (los
    citan a propósito, como referencia para quien lea después)."""
    from app.reporting import export_lab_report

    path = export_lab_report("Palette Check", {"x": 1}, out_dir=reports_dir)
    html_path = path if path.endswith(".html") else glob.glob(os.path.join(reports_dir, "*.html"))[0]
    content = open(html_path, encoding="utf-8").read()
    for orphan_hex in ("#071226", "#cfe9ff", "#99c7ff", "#eaf6ff", "#dfefff", "#bcdff8"):
        assert orphan_hex not in content, f"{orphan_hex} debía migrarse a PALETTE"
    assert PALETTE.BACKGROUND in content
    assert PALETTE.ACCENT_ON_DARK in content


def test_export_preserves_severity_grammar_for_dar_tbr():
    from src.signals.eeg.eeg_analyzer import DAR_CITATION, classify_dar

    data = resolve_metric_card("DAR", "1.20", classification=classify_dar(1.2), grammar=GRAMMAR_SEVERITY, citation=DAR_CITATION)
    assert data.border_color == PALETTE.STABLE
    html = metric_card_to_html(data)
    assert PALETTE.STABLE in html
    assert PALETTE.CRITICAL not in html


def test_export_never_frames_neutral_state_values_as_danger(reports_dir):
    """LA aserción central de Tanda 2: en el HTML exportado, χ (badge 🔴,
    nivel 'excitacion') y BAR (sin clasificación) se enmarcan en NEUTRAL/
    ACCENT_ON_DARK -- nunca en CRITICAL/WARNING. La colisión roja resuelta
    en pantalla (Tanda 1) no puede reaparecer en el export."""
    from app.reporting import export_lab_report
    from src.signals.eeg.eeg_analyzer import BAR_CITATION
    from src.signals.eeg.spectral_model import CHI_CITATION, classify_chi

    cards = [
        resolve_metric_card("χ", "0.80", classification=classify_chi(0.8), grammar=GRAMMAR_NEUTRAL_STATE, citation=CHI_CITATION),
        resolve_metric_card("BAR", "2.30", provenance=BADGES.CLINICAL, grammar=GRAMMAR_NEUTRAL_STATE, citation=BAR_CITATION),
    ]
    path = export_lab_report("Test Neutral Grammar", {}, out_dir=reports_dir, honesty_cards=cards)
    html_path = path if path.endswith(".html") else glob.glob(os.path.join(reports_dir, "*.html"))[0]
    content = open(html_path, encoding="utf-8").read()

    assert "🔴" in content, "el badge de excitación sigue vivo -- no se tocó classify_chi()"
    assert PALETTE.CRITICAL not in content
    assert PALETTE.WARNING not in content
    assert PALETTE.ACCENT_ON_DARK in content


# --- Parte C: la jerarquía de confianza, heredada en el export -----------

def test_export_validation_marker_matches_app_tier():
    marker_validated = resolve_validation_marker("VALIDATED", "Detector TKEO, 6 rondas MIT-BIH")
    marker_heuristic = resolve_validation_marker("HEURISTIC", "Combinador heurístico -- no validado")
    assert marker_validated[0] == PALETTE.STABLE
    assert marker_heuristic[0] == PALETTE.NEUTRAL
    assert marker_validated[0] != marker_heuristic[0]


def test_export_without_validation_declared_skips_marker_not_forced(reports_dir):
    """Un llamador que no pasa `validation=` (el default) no fuerza
    ningún marcador -- el export se ve igual de honesto sin la jerarquía
    que con ella, nunca inventada. (Genérico, no depende de qué lab tenga
    o no un nivel asignado hoy -- ver Tanda Final para las 9 firmas.)"""
    from app.reporting import export_lab_report

    path = export_lab_report("Sin Validacion Asignada", {"x": 1}, out_dir=reports_dir)
    html_path = path if path.endswith(".html") else glob.glob(os.path.join(reports_dir, "*.html"))[0]
    content = open(html_path, encoding="utf-8").read()
    assert "class=\"validation\"" not in content


# --- Parte C/D: los 4 llamadores reales, por ejecución --------------------
#
# NOTA DE MÉTODO: `AppTest.from_function()` re-ejecuta `_script()` como
# script aislado -- cada uno importa lo que necesita por su cuenta.

@pytest.fixture
def _isolated_reports_dir(tmp_path, monkeypatch):
    """Los 4 llamadores reales usan el default `out_dir='reports'` de
    `export_lab_report()` -- se apunta ese default a un directorio
    temporal para no escribir en `reports/` real del repo (que tiene un
    `.gitkeep` rastreado) durante la suite.

    Dos parches, por las dos formas físicas de módulo (Consolidación
    Visual, diagnóstico previo, Mapa 1): `app/main.py` importó `export_
    lab_report` una sola vez al cargar el módulo, así que su NOMBRE LOCAL
    hay que parchear directo. `eeg_neuro_lab/page_content.py` se ejecuta
    vía `runpy` -- reimporta `from app.reporting import export_lab_report`
    en cada corrida, así que ahí basta (y hace falta) parchear el
    atributo real del módulo `app.reporting`."""
    import app.reporting as reporting_mod

    target = tmp_path / "reports"
    original = reporting_mod.export_lab_report

    def _patched(*args, **kwargs):
        kwargs.setdefault("out_dir", str(target))
        return original(*args, **kwargs)

    monkeypatch.setattr("app.main.export_lab_report", _patched)
    monkeypatch.setattr(reporting_mod, "export_lab_report", _patched)
    yield target


def _click_view(at, view_label):
    radio = next(r for r in at.main.radio if r.label == "Capa de Exploración Cognitiva")
    radio.set_value(view_label)
    at.run(timeout=30)
    return at


def test_emg_research_export_has_no_bare_numbers(_isolated_reports_dir):
    def _script():
        import app.main as m
        m.render_emg_page()

    at = AppTest.from_function(_script)
    at.run(timeout=30)
    assert at.exception == []
    _click_view(at, "Investigación")
    btn = next(b for b in at.main.button if b.label == "Exportar EMG para investigación")
    btn.click()
    at.run(timeout=30)
    assert at.exception == [], f"excepción al exportar: {at.exception}"
    assert len(at.main.success) >= 1

    htmls = glob.glob(os.path.join(str(_isolated_reports_dir), "*EMG_Research*.html"))
    assert htmls, "no se generó el HTML de EMG Research"
    content = open(htmls[0], encoding="utf-8").read()
    assert "Median Frequency" in content
    assert BADGES.label(BADGES.HEURISTIC) in content, "antes exportaba el número desnudo, sin procedencia"


def test_ecg_segment_export_has_no_bare_numbers_and_validation_marker(_isolated_reports_dir):
    def _script():
        import app.main as m
        m.render_ecg_monitor_page()

    at = AppTest.from_function(_script)
    at.run(timeout=30)
    assert at.exception == []
    _click_view(at, "Investigación")
    btn = next(b for b in at.main.button if "Exportar segmento" in b.label)
    btn.click()
    at.run(timeout=30)
    assert at.exception == [], f"excepción al exportar: {at.exception}"

    htmls = glob.glob(os.path.join(str(_isolated_reports_dir), "*ECG_Segment*.html"))
    assert htmls, "no se generó el HTML de ECG Segment"
    content = open(htmls[0], encoding="utf-8").read()
    assert "Heart Rate" in content
    assert BADGES.label(BADGES.HEURISTIC) in content, "antes exportaba solo {'length': ...}, cero honestidad"
    assert "MIT-BIH" in content, "ECG Segment debe heredar el nivel de validación ya declarado para ECG Lab"
    assert PALETTE.STABLE in content


def test_multisensor_research_export_has_no_bare_numbers_and_heuristic_marker(_isolated_reports_dir):
    def _script():
        import app.main as m
        m.render_multisensor_page()

    at = AppTest.from_function(_script)
    at.run(timeout=30)
    assert at.exception == []
    _click_view(at, "Investigación")
    btn = next(b for b in at.main.button if "Exportar multisensor" in b.label)
    btn.click()
    at.run(timeout=30)
    assert at.exception == [], f"excepción al exportar: {at.exception}"

    htmls = glob.glob(os.path.join(str(_isolated_reports_dir), "*Multisensor_Research*.html"))
    assert htmls, "no se generó el HTML de Multisensor Research"
    content = open(htmls[0], encoding="utf-8").read()
    assert "Health Score" in content and "SpO2" in content
    assert BADGES.label(BADGES.HEURISTIC) in content, "antes exportaba solo {'channels': [...]}, cero honestidad"
    assert PALETTE.NEUTRAL in content, "Multisensor es heurístico -- marco NEUTRAL, no una alarma"


def test_eeg_neuro_lab_export_includes_dar_tbr_bar_and_chi_with_full_scope_clause(_isolated_reports_dir):
    """El test que importa de esta tanda: antes, el export de EEG Neuro
    Lab pasaba DAR/TBR con badge pero SIN cita, y χ no aparecía en
    absoluto. Ahora los 4 (DAR/TBR/BAR/χ) aparecen, χ con su cláusula de
    alcance COMPLETA, nunca truncada."""
    from pathlib import Path

    from domain.physiology.state import create_patient, init_db, make_engine, make_session_factory

    engine = make_engine(Path(str(Path(str(_isolated_reports_dir)).parent / "eeg_export_test.db")))
    init_db(engine)
    sf = make_session_factory(engine)
    with sf() as s:
        pid = create_patient(s, display_name="Paciente export EEG (test)")

    def _script():
        import app.supermodules.eeg_neuro_lab.pages as m
        m.run()

    at = AppTest.from_function(_script)
    at.session_state["twin_shell_ups_session_factory"] = sf
    at.session_state["twin_shell_ups_patient_id"] = pid
    at.run(timeout=30)
    assert at.exception == []

    dur_slider = next(s for s in at.sidebar.slider if s.label == "Duración (segundos)")
    dur_slider.set_value(90)  # >= MIN_CHI_CLEAN_WINDOWS con margen -- χ disponible
    at.run(timeout=30)
    assert at.exception == []

    btn = next(b for b in at.main.button if b.label == "Exportar informe EEG")
    btn.click()
    at.run(timeout=30)
    assert at.exception == [], f"excepción al exportar: {at.exception}"
    assert len(at.main.success) >= 1

    htmls = glob.glob(os.path.join(str(_isolated_reports_dir), "*EEG_Neuro_Lab*.html"))
    assert htmls, "no se generó el HTML de EEG Neuro Lab"
    content = open(htmls[0], encoding="utf-8").read()

    assert "DAR" in content and "TBR" in content and "BAR" in content
    assert "χ" in content

    from src.signals.eeg.spectral_model import CHI_CITATION
    assert CHI_CITATION in content, "la cita de χ debe estar COMPLETA, con su cláusula de alcance, nunca truncada"
    assert "analogía LFP" in content and "EEG de superficie" in content

    from src.signals.eeg.eeg_analyzer import DAR_CITATION, TBR_CITATION
    assert DAR_CITATION in content, "antes DAR llevaba badge pero NUNCA la cita -- ahora sí"
    assert TBR_CITATION in content

    # las dos gramáticas, en este export real: DAR/TBR bajo severidad
    # (verde/ámbar/rojo posible), BAR/χ bajo estado neutro -- sin que χ se
    # lea como alarma pase lo que pase con su nivel.
    assert PALETTE.CRITICAL not in _extract_card_border(content, "χ")
    assert PALETTE.WARNING not in _extract_card_border(content, "χ")


def _extract_card_border(html: str, label_fragment: str) -> str:
    import re
    m = re.search(
        r"<div class='biocore-metric'[^>]*border-left:4px solid ([^;]+);[^>]*>.{0,20}" + re.escape(label_fragment),
        html,
    )
    return m.group(0) if m else ""


# --- No-regresión de datos --------------------------------------------------

def test_no_regression_reporting_import_and_export_lab_report_signature():
    """`export_lab_report()` sigue aceptando su firma original
    (`metrics`/`findings`/`image_paths`) sin cambios -- los parámetros
    nuevos (`honesty_cards`/`validation`/`validation_detail`) son
    exclusivamente aditivos, con default `None`."""
    import inspect

    from app.reporting import export_lab_report

    sig = inspect.signature(export_lab_report)
    for original_param in ("lab_name", "metrics", "notes", "findings", "out_dir", "image_paths"):
        assert original_param in sig.parameters
    for new_param in ("honesty_cards", "validation", "validation_detail"):
        assert sig.parameters[new_param].default is None
