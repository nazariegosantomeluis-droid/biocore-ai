"""
Consolidación Visual, Tanda Final (2026-09-22) -- transcripción de las 9
firmas de jerarquía de validación del experto (Luis) en los
`render_module_header()` de cada lab. Cierra el hallazgo central del
Mapa 5 (diagnóstico de rediseño): hoy todo módulo se veía igual de
autorizado, sin importar su madurez de validación real.

Vocabulario formal transcrito (reemplaza "validado"/"heuristico" de
Tanda 1): `validation="VALIDATED"` (estrato clínico, 3 labs) /
`validation="HEURISTIC"` (estrato de ingeniería, 3 labs) /
`validation=None` explícito, con comentario que registra por qué (estrato
neutro/estructural, 2 labs). Verificado POR EJECUCIÓN, la barandilla de
siempre -- no es transcripción de texto, es transcripción CON los 9
render pasando.
"""

import glob
import os
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from app.utils.design_system import PALETTE

# --- Las 9 firmas verbatim, como constante de test para no duplicar a mano
# en cada aserción -- fuente única DENTRO del test también.

VALIDATED_SIGNATURES = {
    "ECG Lab": (
        "Detección QRS validada en 6 rondas contra MIT-BIH Arrhythmia Database "
        "(Sensibilidad >99%). Filtros estándar AHA."
    ),
    "Respiratory Lab": (
        "Cálculo de AHI y estratificación de severidad conformes a los manuales de puntuación de la "
        "American Academy of Sleep Medicine (AASM)."
    ),
    "HRV Analysis": (
        "Métricas de dominio temporal (SDNN, RMSSD) calculadas bajo los estándares de la Task Force "
        "de la European Society of Cardiology (ESC/NASPE)."
    ),
}

HEURISTIC_SIGNATURES = {
    "Multisensor Fusion Lab": (
        "Health Score propietario de BIOCORE. Índice agregado de peso paramétrico no validado "
        "poblacionalmente."
    ),
    "Biomarkers Lab": (
        "Índices compuestos (Estrés, Carga Cognitiva) derivados analíticamente de literatura base sin "
        "calibración de dispositivo médico."
    ),
    "EMG Muscle Lab": (
        "Activación RMS fisiológica; el índice de fatiga muscular (fatigue_index) opera bajo umbrales "
        "sintéticos fijos."
    ),
}


def _marker_div(at):
    return [md.value for md in at.main.markdown if "border-left:3px solid" in md.value]


# --- Los 3 VALIDATED (estrato clínico) --------------------------------------

def test_ecg_lab_shows_validated_signature_verbatim_not_truncated():
    def _script():
        import app.main as m
        m.render_ecg_lab_page()

    at = AppTest.from_function(_script)
    at.run(timeout=30)
    assert at.exception == []
    markers = _marker_div(at)
    assert len(markers) == 1
    assert PALETTE.STABLE in markers[0]
    assert "✓" in markers[0]
    assert VALIDATED_SIGNATURES["ECG Lab"] in markers[0], "la firma debe aparecer COMPLETA, nunca truncada"


def test_respiratory_lab_shows_validated_signature_verbatim_not_truncated():
    def _script():
        import app.supermodules.respiratory_lab.pages as m
        m.run()

    at = AppTest.from_function(_script)
    at.run(timeout=30)
    assert at.exception == []
    markers = _marker_div(at)
    assert len(markers) == 1
    assert PALETTE.STABLE in markers[0]
    assert "✓" in markers[0]
    assert VALIDATED_SIGNATURES["Respiratory Lab"] in markers[0]


def test_hrv_lab_shows_validated_signature_verbatim_not_truncated():
    def _script():
        import app.main as m
        m.render_hrv_page()

    at = AppTest.from_function(_script)
    at.run(timeout=30)
    assert at.exception == []
    markers = _marker_div(at)
    assert len(markers) == 1
    assert PALETTE.STABLE in markers[0]
    assert "✓" in markers[0]
    assert VALIDATED_SIGNATURES["HRV Analysis"] in markers[0]


# --- Los 3 HEURISTIC (estrato de ingeniería) --------------------------------

def test_multisensor_shows_heuristic_signature_verbatim_not_truncated():
    def _script():
        import app.main as m
        m.render_multisensor_page()

    at = AppTest.from_function(_script)
    at.run(timeout=30)
    assert at.exception == []
    markers = _marker_div(at)
    assert len(markers) == 1
    assert PALETTE.NEUTRAL in markers[0]
    assert "◇" in markers[0]
    assert VALIDATED_SIGNATURES.get("Multisensor Fusion Lab") is None  # sanity: no está en el set VALIDATED
    assert HEURISTIC_SIGNATURES["Multisensor Fusion Lab"] in markers[0]


def test_biomarkers_shows_heuristic_signature_verbatim_not_truncated():
    def _script():
        import app.main as m
        m.render_biomarkers_page()

    at = AppTest.from_function(_script)
    at.run(timeout=30)
    assert at.exception == []
    markers = _marker_div(at)
    assert len(markers) == 1
    assert PALETTE.NEUTRAL in markers[0]
    assert "◇" in markers[0]
    assert HEURISTIC_SIGNATURES["Biomarkers Lab"] in markers[0]


def test_emg_lab_shows_heuristic_signature_verbatim_not_truncated():
    def _script():
        import app.main as m
        m.render_emg_page()

    at = AppTest.from_function(_script)
    at.run(timeout=30)
    assert at.exception == []
    markers = _marker_div(at)
    assert len(markers) == 1
    assert PALETTE.NEUTRAL in markers[0]
    assert "◇" in markers[0]
    assert HEURISTIC_SIGNATURES["EMG Muscle Lab"] in markers[0]


# --- Los 2 None deliberados (estrato neutro/estructural) --------------------

@pytest.fixture
def eeg_ups(tmp_path):
    from domain.physiology.state import create_patient, init_db, make_engine, make_session_factory

    engine = make_engine(Path(str(tmp_path / "eeg_tanda_final_test.db")))
    init_db(engine)
    sf = make_session_factory(engine)
    with sf() as s:
        pid = create_patient(s, display_name="Paciente Tanda Final EEG (test)")
    return sf, pid


def test_eeg_neuro_lab_stays_deliberately_mute(eeg_ups):
    """`validation=None` EXPLÍCITO -- confirmado por lectura del código
    (el kwarg está presente, no solo ausente) Y por ejecución (ningún
    marcador renderiza)."""
    src = Path("app/supermodules/eeg_neuro_lab/pages.py").read_text(encoding="utf-8")
    assert "validation=None," in src
    assert "contenedor MIXTO" in src or "contenedor mixto" in src.lower() or "mixto" in src.lower(), (
        "debe haber un comentario que registre POR QUÉ es mudo, no solo el kwarg"
    )

    sf, pid = eeg_ups

    def _script():
        import app.supermodules.eeg_neuro_lab.pages as m
        m.run()

    at = AppTest.from_function(_script)
    at.session_state["twin_shell_ups_session_factory"] = sf
    at.session_state["twin_shell_ups_patient_id"] = pid
    at.run(timeout=30)
    assert at.exception == []
    assert _marker_div(at) == []


def test_patient_pipeline_stays_deliberately_mute(tmp_path):
    from domain.physiology.state import create_patient, init_db, make_engine, make_session_factory

    src = Path("app/main.py").read_text(encoding="utf-8")
    assert "validation=None" in src
    assert "ETL" in src, "debe haber un comentario que registre POR QUÉ es mudo (ETL, no inferencia clínica)"

    engine = make_engine(tmp_path / "patient_pipeline_tanda_final.db")
    init_db(engine)
    sf = make_session_factory(engine)
    with sf() as s:
        pid = create_patient(s, display_name="Paciente Tanda Final Pipeline (test)")

    def _script():
        import app.main as m
        m.render_patient_pipeline_page()

    at = AppTest.from_function(_script)
    at.session_state["twin_shell_ups_session_factory"] = sf
    at.session_state["twin_shell_ups_patient_id"] = pid
    at.run(timeout=30)
    assert at.exception == []
    assert _marker_div(at) == []


# --- La jerarquía es LEGIBLE A LA VISTA, no solo un dato --------------------

def test_validated_and_heuristic_labs_are_visually_distinct():
    """La prueba que pide la tanda: un lab VALIDATED (ECG) y uno HEURISTIC
    (Multisensor) deben verse con autoridad visualmente distinta --
    colores de marco y símbolos distintos, no solo un campo de datos
    diferente en algún lado."""
    def _script_ecg():
        import app.main as m
        m.render_ecg_lab_page()

    def _script_multi():
        import app.main as m
        m.render_multisensor_page()

    at_ecg = AppTest.from_function(_script_ecg)
    at_ecg.run(timeout=30)
    at_multi = AppTest.from_function(_script_multi)
    at_multi.run(timeout=30)

    ecg_marker = _marker_div(at_ecg)[0]
    multi_marker = _marker_div(at_multi)[0]

    assert PALETTE.STABLE in ecg_marker and PALETTE.STABLE not in multi_marker
    assert PALETTE.NEUTRAL in multi_marker and PALETTE.NEUTRAL not in ecg_marker
    assert "✓" in ecg_marker and "✓" not in multi_marker
    assert "◇" in multi_marker and "◇" not in ecg_marker


# --- La honestidad viaja al export (reporting.py, Tanda 2) ------------------

@pytest.fixture
def reports_dir(tmp_path):
    return str(tmp_path / "reports")


def test_ecg_export_shows_validated_mark_multisensor_export_shows_heuristic(reports_dir, monkeypatch):
    """Un informe exportado de ECG se ve validado; uno de Multisensor se
    ve heurístico -- la jerarquía no puede vivir solo en pantalla. Ambos
    exports reales, via los botones reales, con `out_dir` apuntado a un
    directorio temporal (nunca al `reports/` real del repo)."""
    import app.reporting as reporting_mod

    original = reporting_mod.export_lab_report

    def _patched(*args, **kwargs):
        kwargs.setdefault("out_dir", reports_dir)
        return original(*args, **kwargs)

    monkeypatch.setattr("app.main.export_lab_report", _patched)

    # ECG Segment
    def _script_ecg():
        import app.main as m
        m.render_ecg_monitor_page()

    at_ecg = AppTest.from_function(_script_ecg)
    at_ecg.run(timeout=30)
    radio = next(r for r in at_ecg.main.radio if r.label == "Capa de Exploración Cognitiva")
    radio.set_value("Investigación")
    at_ecg.run(timeout=30)
    btn = next(b for b in at_ecg.main.button if "Exportar segmento" in b.label)
    btn.click()
    at_ecg.run(timeout=30)
    assert at_ecg.exception == []

    ecg_htmls = glob.glob(os.path.join(reports_dir, "*ECG_Segment*.html"))
    assert ecg_htmls, "no se generó el HTML de ECG Segment"
    ecg_content = open(ecg_htmls[0], encoding="utf-8").read()
    assert 'class="validation"' in ecg_content
    assert PALETTE.STABLE in ecg_content
    assert VALIDATED_SIGNATURES["ECG Lab"] in ecg_content, "firma verbatim, no truncada, en el export"

    # Multisensor Research
    def _script_multi():
        import app.main as m
        m.render_multisensor_page()

    at_multi = AppTest.from_function(_script_multi)
    at_multi.run(timeout=30)
    radio2 = next(r for r in at_multi.main.radio if r.label == "Capa de Exploración Cognitiva")
    radio2.set_value("Investigación")
    at_multi.run(timeout=30)
    btn2 = next(b for b in at_multi.main.button if "Exportar multisensor" in b.label)
    btn2.click()
    at_multi.run(timeout=30)
    assert at_multi.exception == []

    multi_htmls = glob.glob(os.path.join(reports_dir, "*Multisensor_Research*.html"))
    assert multi_htmls, "no se generó el HTML de Multisensor Research"
    multi_content = open(multi_htmls[0], encoding="utf-8").read()
    assert 'class="validation"' in multi_content
    assert PALETTE.NEUTRAL in multi_content
    assert HEURISTIC_SIGNATURES["Multisensor Fusion Lab"] in multi_content

    # las dos marcas de export (el div class="validation", no la página
    # entera -- el color NEUTRAL también aparece en badges HEURISTIC de
    # métricas individuales, legítimamente, así que comparar la página
    # completa daría un falso positivo) son visualmente distintas entre sí
    ecg_validation_div = ecg_content.split('class="validation"')[1][:400]
    multi_validation_div = multi_content.split('class="validation"')[1][:400]
    assert PALETTE.STABLE in ecg_validation_div
    assert PALETTE.NEUTRAL not in ecg_validation_div
    assert PALETTE.NEUTRAL in multi_validation_div
    assert PALETTE.STABLE not in multi_validation_div


def test_emg_export_now_carries_its_signed_heuristic_mark(reports_dir, monkeypatch):
    """EMG Research (Tanda 2) no llevaba `validation=` porque EMG no tenía
    nivel asignado todavía -- ahora sí (HEURISTIC, firmado), y el export
    lo hereda igual que ya hacían ECG/Multisensor."""
    import app.reporting as reporting_mod

    original = reporting_mod.export_lab_report

    def _patched(*args, **kwargs):
        kwargs.setdefault("out_dir", reports_dir)
        return original(*args, **kwargs)

    monkeypatch.setattr("app.main.export_lab_report", _patched)

    def _script():
        import app.main as m
        m.render_emg_page()

    at = AppTest.from_function(_script)
    at.run(timeout=30)
    radio = next(r for r in at.main.radio if r.label == "Capa de Exploración Cognitiva")
    radio.set_value("Investigación")
    at.run(timeout=30)
    btn = next(b for b in at.main.button if b.label == "Exportar EMG para investigación")
    btn.click()
    at.run(timeout=30)
    assert at.exception == []

    htmls = glob.glob(os.path.join(reports_dir, "*EMG_Research*.html"))
    assert htmls, "no se generó el HTML de EMG Research"
    content = open(htmls[0], encoding="utf-8").read()
    assert 'class="validation"' in content
    assert PALETTE.NEUTRAL in content
    assert HEURISTIC_SIGNATURES["EMG Muscle Lab"] in content


def test_eeg_export_still_carries_no_validation_mark(reports_dir, monkeypatch, eeg_ups):
    """EEG Neuro Lab sigue mudo también en el export -- consistente con
    el estar mudo en pantalla (contenedor mixto)."""
    import app.reporting as reporting_mod

    original = reporting_mod.export_lab_report

    def _patched(*args, **kwargs):
        kwargs.setdefault("out_dir", reports_dir)
        return original(*args, **kwargs)

    monkeypatch.setattr(reporting_mod, "export_lab_report", _patched)

    sf, pid = eeg_ups

    def _script():
        import app.supermodules.eeg_neuro_lab.pages as m
        m.run()

    at = AppTest.from_function(_script)
    at.session_state["twin_shell_ups_session_factory"] = sf
    at.session_state["twin_shell_ups_patient_id"] = pid
    at.run(timeout=30)
    dur_slider = next(s for s in at.sidebar.slider if s.label == "Duración (segundos)")
    dur_slider.set_value(90)
    at.run(timeout=30)
    btn = next(b for b in at.main.button if b.label == "Exportar informe EEG")
    btn.click()
    at.run(timeout=30)
    assert at.exception == []

    htmls = glob.glob(os.path.join(reports_dir, "*EEG_Neuro_Lab*.html"))
    assert htmls, "no se generó el HTML de EEG Neuro Lab"
    content = open(htmls[0], encoding="utf-8").read()
    assert 'class="validation"' not in content


# --- Los ~9 labs renderizan sin excepción, con o sin marca ------------------

def test_all_signed_labs_render_without_exception(eeg_ups):
    sf, pid = eeg_ups

    def _script_ecg():
        import app.main as m
        m.render_ecg_lab_page()

    def _script_respiratory():
        import app.supermodules.respiratory_lab.pages as m
        m.run()

    def _script_hrv():
        import app.main as m
        m.render_hrv_page()

    def _script_multi():
        import app.main as m
        m.render_multisensor_page()

    def _script_biomarkers():
        import app.main as m
        m.render_biomarkers_page()

    def _script_emg():
        import app.main as m
        m.render_emg_page()

    for script in (_script_ecg, _script_respiratory, _script_hrv, _script_multi, _script_biomarkers, _script_emg):
        at = AppTest.from_function(script)
        at.run(timeout=30)
        assert at.exception == [], f"{script.__name__}: excepción en el render: {at.exception}"

    def _script_eeg():
        import app.supermodules.eeg_neuro_lab.pages as m
        m.run()

    at_eeg = AppTest.from_function(_script_eeg)
    at_eeg.session_state["twin_shell_ups_session_factory"] = sf
    at_eeg.session_state["twin_shell_ups_patient_id"] = pid
    at_eeg.run(timeout=30)
    assert at_eeg.exception == []

    def _script_pipeline():
        import app.main as m
        m.render_patient_pipeline_page()

    at_pipeline = AppTest.from_function(_script_pipeline)
    at_pipeline.session_state["twin_shell_ups_session_factory"] = sf
    at_pipeline.session_state["twin_shell_ups_patient_id"] = pid
    at_pipeline.run(timeout=30)
    assert at_pipeline.exception == []
