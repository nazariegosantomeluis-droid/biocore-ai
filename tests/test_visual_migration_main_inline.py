"""
Consolidación Visual, Tanda 3 (2026-09-21) -- migra los 6 labs que viven
INLINE en `app/main.py` (EMG, HRV, ECG Monitor, Multisensor, Patient
Pipeline, Biomarkers) al sistema de diseño ya construido por las Tandas
1/2 (`app/utils/design_system.py`, `app/reporting.py`). Verificado POR
EJECUCIÓN vía `AppTest`, mismo criterio que las tandas anteriores.

Alcance real de esta tanda (ver el reporte de la tarea para el detalle
completo):
  - Biomarkers Lab: los 3 estilos ad hoc de "no disponible" (PLV,
    Learning Readiness Index, Autonomic Stability) unificados en
    `render_metric_card()`, motivo textual preservado verbatim. Leyenda
    de 4 badges reconstruida con `BADGES.label()` en vez de texto propio.
  - EMG Muscle Lab: "Median Frequency" (antes `st.write()` desnudo) ahora
    `render_metric_card(provenance=BADGES.HEURISTIC)`.
  - Multisensor Fusion Lab: Health Score/Heart Rate/SpO2 en Vista Clínica
    y Simulación migrados a `render_metric_card(provenance=BADGES.
    HEURISTIC)` -- mismo badge que ya usa el export de este módulo desde
    la Tanda 2.
  - ECG Monitor, HRV Analysis, Patient Pipeline: revisados, sin cambios
    (ver el reporte para el razonamiento de cada "no migrar" -- ninguno
    tenía un badge/cita ya establecido en este archivo para el valor en
    cuestión, y forzar uno sería fabricar una afirmación de honestidad,
    justo lo que Art. I prohíbe).

NOTA DE MÉTODO (igual que Tandas 1/2): `AppTest.from_function()` reejecuta
`_script()` como script AISLADO -- ningún closure ni import del scope que
lo define sobrevive. Cada `_script()` importa lo que necesita por su
cuenta.
"""

import glob
import os

import pytest
from streamlit.testing.v1 import AppTest

from app.utils.design_system import BADGES, PALETTE


def _click_view(at, view_label):
    radio = next(r for r in at.main.radio if r.label == "Capa de Exploración Cognitiva")
    radio.set_value(view_label)
    at.run(timeout=30)
    return at


# --- Render sin excepción, los 6 labs -------------------------------------

def test_biomarkers_lab_renders_without_exception():
    def _script():
        import app.main as m
        m.render_biomarkers_page()

    at = AppTest.from_function(_script)
    at.run(timeout=30)
    assert at.exception == [], f"excepción en el render: {at.exception}"


def test_emg_lab_renders_without_exception_in_investigacion_view():
    def _script():
        import app.main as m
        m.render_emg_page()

    at = AppTest.from_function(_script)
    at.run(timeout=30)
    assert at.exception == []
    _click_view(at, "Investigación")
    assert at.exception == [], f"excepción en Vista Investigación: {at.exception}"


def test_ecg_monitor_renders_without_exception():
    def _script():
        import app.main as m
        m.render_ecg_monitor_page()

    at = AppTest.from_function(_script)
    at.run(timeout=30)
    assert at.exception == [], f"excepción en el render: {at.exception}"


def test_multisensor_renders_without_exception_clinica_and_simulacion():
    def _script():
        import app.main as m
        m.render_multisensor_page()

    at = AppTest.from_function(_script)
    at.run(timeout=30)
    assert at.exception == [], f"excepción en Vista Clínica: {at.exception}"
    _click_view(at, "Simulación")
    assert at.exception == [], f"excepción en Vista Simulación: {at.exception}"


def test_hrv_lab_renders_without_exception():
    def _script():
        import app.main as m
        m.render_hrv_page()

    at = AppTest.from_function(_script)
    at.run(timeout=30)
    assert at.exception == [], f"excepción en el render: {at.exception}"


def test_patient_pipeline_renders_without_exception(tmp_path):
    from domain.physiology.state import create_patient, init_db, make_engine, make_session_factory

    engine = make_engine(tmp_path / "test_patient_pipeline.db")
    init_db(engine)
    sf = make_session_factory(engine)
    with sf() as s:
        pid = create_patient(s, display_name="Test Patient (Tanda 3)")

    def _script():
        import app.main as m
        m.render_patient_pipeline_page()

    at = AppTest.from_function(_script)
    at.session_state["twin_shell_ups_session_factory"] = sf
    at.session_state["twin_shell_ups_patient_id"] = pid
    at.run(timeout=30)
    assert at.exception == [], f"excepción en el render: {at.exception}"


# --- Rule 2 (histórico, Tanda 3): validation=None en los 4 labs migrados,
# SUPERSEDIDO por la Consolidación Visual Tanda Final (2026-09-22) --------
#
# Tanda 3 dejó los 4 labs de este archivo (EMG/HRV/Patient Pipeline/
# Biomarkers) sin `validation=` a propósito: asignar un nivel es una
# afirmación clínica que solo el experto humano autoriza. La Tanda Final
# transcribió la firma del experto: EMG/Biomarkers -> HEURISTIC, HRV ->
# VALIDATED, Patient Pipeline -> `None` EXPLÍCITO (infraestructura ETL, el
# concepto de validación no aplica). Este test ahora confirma la firma
# vigente en vez de "ningún marcador" -- la ausencia de marcador en
# Patient Pipeline sigue siendo una aserción real, ya no por default sino
# porque el experto firmó que debía quedar mudo.

def test_emg_hrv_biomarkers_show_their_signed_validation_marker():
    def _script_emg():
        import app.main as m
        m.render_emg_page()

    def _script_hrv():
        import app.main as m
        m.render_hrv_page()

    def _script_biomarkers():
        import app.main as m
        m.render_biomarkers_page()

    from app.utils.design_system import PALETTE

    for script, expected_color, fragment in (
        (_script_emg, PALETTE.NEUTRAL, "Activación RMS fisiológica"),
        (_script_hrv, PALETTE.STABLE, "Task Force"),
        (_script_biomarkers, PALETTE.NEUTRAL, "Índices compuestos"),
    ):
        at = AppTest.from_function(script)
        at.run(timeout=30)
        assert at.exception == []
        markers = [md.value for md in at.main.markdown if "border-left:3px solid" in md.value]
        assert len(markers) == 1, f"se esperaba exactamente un marcador de confianza: {markers}"
        assert fragment in markers[0], f"texto de la firma no encontrado en el marcador: {markers[0]}"
        assert expected_color in markers[0]


def test_patient_pipeline_header_has_no_validation_marker_deliberately(tmp_path):
    """Patient Pipeline es el único de los 4 que sigue mudo -- firmado
    EXPLÍCITAMENTE como `validation=None` (infraestructura ETL, no
    inferencia clínica), no un olvido."""
    from domain.physiology.state import create_patient, init_db, make_engine, make_session_factory

    engine = make_engine(tmp_path / "test_patient_pipeline_validation.db")
    init_db(engine)
    sf = make_session_factory(engine)
    with sf() as s:
        pid = create_patient(s, display_name="Test Patient (Tanda Final)")

    def _script():
        import app.main as m
        m.render_patient_pipeline_page()

    at = AppTest.from_function(_script)
    at.session_state["twin_shell_ups_session_factory"] = sf
    at.session_state["twin_shell_ups_patient_id"] = pid
    at.run(timeout=30)
    assert at.exception == []
    validation_markers = [md.value for md in at.main.markdown if "border-left:3px solid" in md.value]
    assert validation_markers == [], f"Patient Pipeline debe seguir mudo: {validation_markers}"


# --- Rule 5: las dos asignaciones existentes, byte a byte -----------------

def test_ecg_lab_and_multisensor_validation_assignments_signed_by_expert():
    """NOTA (Consolidación Visual Tanda Final, 2026-09-22): este test
    verificaba que Tanda 3 no tocara las dos asignaciones de Tanda 1 --
    la Tanda Final SÍ las toca, a propósito, para transcribir el texto
    VERBATIM de la firma del experto (reemplaza el texto provisional).
    Se actualiza para confirmar la firma vigente, no la de Tanda 1."""
    import pathlib
    src = pathlib.Path("app/main.py").read_text(encoding="utf-8")
    assert "Detección QRS validada en 6 rondas contra MIT-BIH Arrhythmia Database" in src
    assert "Health Score propietario de BIOCORE. Índice agregado de peso paramétrico no validado" in src
    assert 'validation="VALIDATED",' in src
    assert 'validation_detail=_ECG_VALIDATION_DETAIL,' in src
    assert 'validation="HEURISTIC",' in src
    assert 'validation_detail=_MULTISENSOR_VALIDATION_DETAIL,' in src
    # las claves de tier viejas (minúscula) no deben sobrevivir en ningún
    # `validation=` real del archivo
    assert 'validation="validado"' not in src
    assert 'validation="heuristico"' not in src


def test_ecg_lab_still_shows_validated_marker_and_multisensor_heuristic_marker():
    def _script_ecg():
        import app.main as m
        m.render_ecg_lab_page()

    def _script_multi():
        import app.main as m
        m.render_multisensor_page()

    at_ecg = AppTest.from_function(_script_ecg)
    at_ecg.run(timeout=30)
    assert at_ecg.exception == []
    ecg_marker = next(md.value for md in at_ecg.main.markdown if "MIT-BIH" in md.value)
    assert PALETTE.STABLE in ecg_marker and "✓" in ecg_marker

    at_multi = AppTest.from_function(_script_multi)
    at_multi.run(timeout=30)
    assert at_multi.exception == []
    multi_marker = next(md.value for md in at_multi.main.markdown if "Health Score propietario" in md.value)
    assert PALETTE.NEUTRAL in multi_marker and "◇" in multi_marker


# --- Biomarkers: los 3 "no disponible" reales de este panel ---------------
#
# La Vista de Biomarkers Lab llama a `engine.get_full_biomarker_suite(datos_
# sensores)` SIN señal cruda EEG/RR (`eeg_frontal_signal`/`rr_intervals_s`
# no se pasan desde este panel -- confirmado leyendo `render_biomarkers_
# page()`/`BiocoreEngine.get_full_biomarker_suite()`), así que el PLV
# SIEMPRE sale `available=False` aquí, y Learning Readiness (que depende
# del PLV) en cascada también. Autonomic Stability es incondicional. Los 3
# motivos son deterministas y verificables sin forzar disponibilidad.

_UNAVAILABLE_CASES = [
    (
        "NeuroCardiac PLV",
        "🟣 Métrica deshabilitada: el PLV requiere ≥180s de señal ECG+EEG simultánea. Muestra actual: 0s.",
    ),
    (
        "Learning Readiness Index",
        "🔵 Métrica deshabilitada: depende del PLV neurocardíaco (arriba), que no está disponible.",
    ),
    (
        "Autonomic Stability",
        "🔴 No disponible — sin fuente de señal real. Requiere presión arterial y PPG-PTT que hoy no "
        "existen en el pipeline (ver 🔴 Fantasmas abajo).",
    ),
]


@pytest.mark.parametrize("label, exact_reason", _UNAVAILABLE_CASES)
def test_biomarkers_unavailable_cards_preserve_exact_reason_verbatim(label, exact_reason):
    def _script():
        import app.main as m
        m.render_biomarkers_page()

    at = AppTest.from_function(_script)
    at.run(timeout=30)
    assert at.exception == []
    card = next(md.value for md in at.main.markdown if label in md.value)
    assert exact_reason in card, f"motivo original no preservado verbatim para {label}"
    assert "no disponible" in card
    # forma unificada: las 3 pasan ahora por render_metric_card (marco
    # NEUTRAL, mismo patrón que cualquier otro "no disponible" del repo)
    assert PALETTE.NEUTRAL in card


def test_biomarkers_badge_legend_uses_badges_label_not_bespoke_text():
    """La leyenda de 4 badges (antes texto propio de este módulo) ahora
    compone con `BADGES.label()` -- fuente única en design_system.py.
    NOTA: esto SÍ cambia el texto mostrado (de la redacción propia de
    Biomarkers a la redacción canónica de BADGES._LABELS) -- a diferencia
    de los 3 "no disponible" de arriba, que se preservan verbatim. Ver el
    reporte de la tarea para la justificación de esta distinción."""
    def _script():
        import app.main as m
        m.render_biomarkers_page()

    at = AppTest.from_function(_script)
    at.run(timeout=30)
    assert at.exception == []
    caption = next(c.value for c in at.main.caption if "pasa el mouse sobre cada métrica" in c.value)
    assert BADGES.label(BADGES.CLINICAL) in caption
    assert BADGES.label(BADGES.HEURISTIC) in caption
    assert BADGES.label(BADGES.METHOD) in caption
    assert BADGES.label(BADGES.GHOST) in caption


# --- EMG: Median Frequency migrado, badge HEURISTIC ------------------------

def test_emg_median_frequency_card_shows_heuristic_badge():
    def _script():
        import app.main as m
        m.render_emg_page()

    at = AppTest.from_function(_script)
    at.run(timeout=30)
    _click_view(at, "Investigación")
    assert at.exception == []
    card = next(md.value for md in at.main.markdown if "Median Frequency" in md.value)
    assert BADGES.label(BADGES.HEURISTIC) in card
    assert "Hz" in card


def test_emg_median_frequency_card_matches_exported_value_same_execution(tmp_path, monkeypatch):
    """Prueba de 'cero cambio de valor calculado': dentro de UNA sola
    ejecución de script (la que corre al pulsar 'Exportar'), la tarjeta
    en pantalla (mi código nuevo) y el `honesty_cards` que ya exportaba la
    Tanda 2 (código sin tocar) leen la MISMA variable `median_freq` --
    si coinciden, la migración solo cambió CÓMO se muestra, nunca qué se
    calculó."""
    import app.reporting as reporting_mod
    original = reporting_mod.export_lab_report

    def _patched(*args, **kwargs):
        kwargs.setdefault("out_dir", str(tmp_path))
        return original(*args, **kwargs)

    monkeypatch.setattr("app.main.export_lab_report", _patched)

    def _script():
        import app.main as m
        m.render_emg_page()

    at = AppTest.from_function(_script)
    at.run(timeout=30)
    _click_view(at, "Investigación")
    btn = next(b for b in at.main.button if b.label == "Exportar EMG para investigación")
    btn.click()
    at.run(timeout=30)
    assert at.exception == [], f"excepción al exportar: {at.exception}"

    card = next(md.value for md in at.main.markdown if "Median Frequency" in md.value)
    import re
    m_card = re.search(r"Median Frequency</strong>:\s*([\d.]+)\s*Hz", card)
    assert m_card, f"no se pudo extraer el valor de la tarjeta: {card}"
    card_value = m_card.group(1)

    htmls = glob.glob(os.path.join(str(tmp_path), "*EMG_Research*.html"))
    assert htmls, "no se generó el HTML de EMG Research"
    content = open(htmls[0], encoding="utf-8").read()
    m_export = re.search(r"Median Frequency</strong>:\s*([\d.]+)\s*Hz", content)
    assert m_export, "no se pudo extraer el valor del export"
    export_value = m_export.group(1)

    assert card_value == export_value, (
        f"la tarjeta en pantalla ({card_value} Hz) y el export ({export_value} Hz) deben coincidir -- "
        "misma variable median_freq, misma ejecución de script"
    )


# --- Multisensor: Health Score / Heart Rate / SpO2, badge HEURISTIC -------

def test_multisensor_clinica_cards_show_heuristic_badge_never_alarm_colors():
    def _script():
        import app.main as m
        m.render_multisensor_page()

    at = AppTest.from_function(_script)
    at.run(timeout=30)
    assert at.exception == []
    for label in ("Health Score", "Heart Rate", "SpO2"):
        # "Health Score" también aparece en el `render_metric_explained()`
        # educativo que se conserva arriba (mismo label, div distinto) --
        # se filtra específicamente por la tarjeta de render_metric_card
        # (identificable por su borde), no por cualquier markdown que
        # mencione el label.
        card = next(
            md.value for md in at.main.markdown
            if label in md.value and "border-left:4px solid" in md.value
        )
        assert BADGES.label(BADGES.HEURISTIC) in card, f"{label}: falta el badge heurístico"
        # Multisensor es heurístico, no una alarma -- el marco de estas
        # tarjetas (sin `classification=`) debe ser NEUTRAL, nunca CRITICAL/WARNING.
        assert PALETTE.CRITICAL not in card
        assert PALETTE.WARNING not in card


def test_multisensor_simulacion_cards_show_heuristic_badge():
    def _script():
        import app.main as m
        m.render_multisensor_page()

    at = AppTest.from_function(_script)
    at.run(timeout=30)
    _click_view(at, "Simulación")
    assert at.exception == []
    labels = ("Heart Rate (detectado del ECG)", "SpO2 (recalculado)", "Health Score (recalculado)")
    for label in labels:
        card = next(md.value for md in at.main.markdown if label in md.value)
        assert BADGES.label(BADGES.HEURISTIC) in card, f"{label}: falta el badge heurístico"


# --- Confirmaciones de las 3 reglas duras ----------------------------------

def test_design_system_module_untouched_by_this_tanda():
    """Regla 1: `design_system.py` es de solo lectura para esta tanda --
    confirma que las funciones que esta tanda CONSUME siguen con la firma
    documentada en el hand-off (no una prueba exhaustiva del archivo, solo
    que las firmas que uso existen tal cual)."""
    import inspect

    from app.utils.design_system import render_metric_card, resolve_metric_card

    sig = inspect.signature(render_metric_card)
    for p in ("label", "value", "provenance", "classification", "grammar", "citation", "unavailable_reason"):
        assert p in sig.parameters
    assert inspect.signature(resolve_metric_card).parameters.keys() == sig.parameters.keys()


def test_no_hex_color_literals_introduced_in_the_six_functions():
    """Regla de limpieza (no dura, pero verificada): ningún hex color
    nuevo dentro de las 6 funciones migradas -- grep de código, no de
    comentarios (el único hex que aparece en el archivo hoy es una
    referencia histórica dentro de un comentario de Fase 2.3 Tanda 1)."""
    import pathlib
    import re

    src = pathlib.Path("app/main.py").read_text(encoding="utf-8")
    lines = src.splitlines()
    func_starts = {
        name: i for i, line in enumerate(lines)
        for name in (
            "def render_biomarkers_page(", "def render_emg_page(", "def render_ecg_monitor_page(",
            "def render_multisensor_page(", "def render_hrv_page(", "def render_patient_pipeline_page(",
        )
        if line.startswith(name)
    }
    assert len(func_starts) == 6, f"no se encontraron las 6 funciones: {func_starts}"
    hex_pattern = re.compile(r"#[0-9a-fA-F]{6}")
    for name, start in func_starts.items():
        # corta en el siguiente "def " de nivel 0 o fin de archivo
        end = len(lines)
        for j in range(start + 1, len(lines)):
            if lines[j].startswith("def "):
                end = j
                break
        for j in range(start, end):
            stripped = lines[j].strip()
            if stripped.startswith("#"):
                continue
            assert not hex_pattern.search(lines[j]), f"hex color en código vivo, {name}, línea {j+1}: {lines[j]}"


def test_reporting_and_supermodules_not_imported_for_editing_only_running():
    """No es una prueba de comportamiento -- documenta la regla dura 'no
    toco reporting.py ni app/supermodules/*' dejando registrado que este
    archivo de tests no importa nada de ahí salvo lo que la Tanda 2 ya
    exponía (`export_lab_report`, sin tocar su código)."""
    import app.reporting as reporting_mod
    assert hasattr(reporting_mod, "export_lab_report")
