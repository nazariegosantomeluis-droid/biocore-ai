"""Contención antes de la prueba con estudiantes (2026-11-16, Art. I).

- PARTE A.1: el Clasificador de ECG del gemelo se oculta (decía «QRS=0 ms, PR=0 ms, QTc=0 ms — dentro de rango» y un
  «QT largo» falso a 150 lpm); queda una línea honesta. Golden a 40, 75, 150 y 180 lpm.
- PARTE A.2: sin indicaciones de tratamiento ni «riesgo de mortalidad» sin cita: los casos clínicos del Monitoreo del
  ECG y el riesgo cardiovascular del gemelo. La guardia recorre además TODAS las páginas (`test_fase1_t2_pulido.py`).
- PARTE A.3: un CSV del Monitoreo del ECG no escribe al gemelo, con el mismo criterio y mensaje que el EMG.
- PARTE B: el «Caso ciego» de la Academia se corrige sin clave de IA.
- PARTE C: el pulso por luz saturado da «sin pulso», nunca una frecuencia; piso de amplitud HEURISTIC.
"""

import io

import numpy as np
import pytest
from streamlit.testing.v1 import AppTest
from streamlit.testing.v1.errors import AppTestError

from test_fase1_t2_pulido import visible_texts
from test_integracion_contencion import TREATMENT

NO_AI_VARS = ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY")


@pytest.fixture
def ups(tmp_path):
    from domain.physiology.state import create_patient, init_db, make_engine, make_session_factory

    engine = make_engine(tmp_path / "contencion.db")
    init_db(engine)
    sf = make_session_factory(engine)
    with sf() as s:
        pid = create_patient(s, display_name="contencion")
    return sf, pid


def _twin(sf, pid):
    def _script():
        import app.supermodules.twin_shell.pages as m
        m.run()

    at = AppTest.from_function(_script, default_timeout=240)
    at.session_state["twin_shell_ups_session_factory"] = sf
    at.session_state["twin_shell_ups_patient_id"] = pid
    at.run()
    assert at.exception == [], at.exception
    return at


# ------------------------------------------------------------------------------------- A.1 clasificador del gemelo
@pytest.mark.parametrize("hr", [40, 75, 150, 180])
def test_the_twin_shows_no_automatic_ecg_reading_at_any_heart_rate(ups, hr):
    from app.supermodules.twin_shell.pages import ECG_CLASSIFIER_IN_REVIEW

    at = _twin(*ups)
    at.slider(key="twin_shell_hr").set_value(hr).run()
    assert at.exception == [], at.exception
    text = " ".join(visible_texts(at))
    for facade in ("QRS=0", "PR=0", "QTc=0", "QT largo", "Clasificador de ECG", "dentro de rango"):
        assert facade not in text, (hr, facade)
    assert ECG_CLASSIFIER_IN_REVIEW in text
    assert "lectura automática del ECG del gemelo está en revisión" in ECG_CLASSIFIER_IN_REVIEW


def test_the_classifier_still_declines_skewness_and_kurtosis_with_identical_rr():
    """La garantía que antes se probaba a través del panel (tanda 2): con RR idénticos no hay número poco fiable."""
    from domain.physiology.ml import classify_ecg_signal
    from src.signals.ecg.dynamic_ecg_generator import DynamicECGGenerator

    result = classify_ecg_signal(DynamicECGGenerator(fs=250.0).generate(duration=20, hr=150), 250.0)
    assert {"Asimetría de RR", "Curtosis de RR"} <= set(result.unavailable_features)


# ------------------------------------------------------------------------------------ A.2 tratamientos sin cita
def test_the_twin_risk_panel_gives_no_recommendation_even_at_high_risk(ups):
    """Historial persistido con taquicardia en aumento (riesgo alto): antes salía «Considere consulta cardiólogo
    urgente», «Frecuencia cardíaca elevada - evaluar causa»..."""
    from app.engines.digital_twin_organism import DigitalTwinOrganism
    from domain.physiology.state import Provenance, from_digital_twin_organism, save_state

    sf, pid = ups
    for hr in (110.0, 130.0, 150.0, 170.0):
        organism = DigitalTwinOrganism()
        organism.update_from_sensors({"ecg": {"heart_rate": hr}})
        with sf() as s:
            save_state(s, from_digital_twin_organism(organism, pid, provenance=Provenance.SIMULACION,
                                                     source_detail="prueba de contención"))
    at = _twin(sf, pid)
    texts = visible_texts(at)
    assert any("RIESGO CARDIOVASCULAR" in t for t in texts), [t for t in texts if "snapshot" in t]
    hits = sorted({m.group(0) for t in texts for m in TREATMENT.finditer(t)})
    assert hits == [], hits


def test_the_risk_predictor_returns_no_recommendations():
    from src.ai.patient_analytics import PatientRiskPredictor

    result = PatientRiskPredictor().calculate_risk_score(heart_rate=170.0, systolic_bp=180.0, diastolic_bp=110.0,
                                                         ecg_pattern="stemi", hrv_sdnn=10.0,
                                                         trend_data=[80, 100, 120, 140])
    assert result["total_risk"] >= 0.5 and "recommendations" not in result
    assert "recommendations" not in PatientRiskPredictor().calculate_risk_score()


def _ecg_monitor(sf=None, pid=None, csv_bytes=b""):
    def _script(csv_bytes):
        import io

        import streamlit as st

        import app.main as m

        class Upload(io.BytesIO):
            name = "registro.csv"

        original = st.sidebar.file_uploader
        st.sidebar.file_uploader = lambda *a, **k: Upload(csv_bytes)      # un archivo cargado (AppTest no sube)
        try:
            m.render_ecg_monitor_page()
        finally:
            st.sidebar.file_uploader = original

    at = AppTest.from_function(_script, args=(csv_bytes,), default_timeout=240)
    if sf is not None:
        at.session_state["twin_shell_ups_session_factory"] = sf
        at.session_state["twin_shell_ups_patient_id"] = pid
    at.run()
    assert at.exception == [], at.exception
    return at


def test_no_ecg_clinical_case_shows_an_action_or_a_mortality_risk():
    """Un caso por diagnóstico: ni «Acción clínica recomendada» (betabloqueadores, ACLS, PCI, marcapasos, DAI, sin
    cita y en inglés) ni «Riesgo de mortalidad estimado» (cifra sin fuente)."""
    at = _ecg_monitor()
    next(r for r in at.sidebar.radio if r.label == "Origen del ECG").set_value("Caso clínico (61 disponibles)").run()
    diagnoses = list(next(s for s in at.sidebar.selectbox if s.label == "Diagnóstico primario").options)
    assert len(diagnoses) >= 5
    for diagnosis in diagnoses:
        next(s for s in at.sidebar.selectbox if s.label == "Diagnóstico primario").set_value(diagnosis).run()
        assert at.exception == [], (diagnosis, at.exception)
        texts = visible_texts(at)
        assert any("Detalle del caso" in t for t in texts), diagnosis
        hits = sorted({m.group(0) for t in texts for m in TREATMENT.finditer(t)})
        assert hits == [], (diagnosis, hits)
        assert not any("mortalidad" in t.lower() for t in texts), diagnosis


def test_the_case_database_keeps_no_action_or_mortality_field():
    from src.clinical.case_database import ClinicalCase

    fields = set(ClinicalCase.__dataclass_fields__)
    assert "clinical_action" not in fields and "mortality_risk" not in fields


# --------------------------------------------------------------------------------------- A.3 CSV del ECG al gemelo
def test_a_loaded_ecg_csv_is_analyzed_but_never_written_to_the_twin(ups):
    """Golden con un archivo de verdad (un CSV con 20 s de ECG): hay trazo y FC, pero «Guardar al gemelo» está
    desactivado con «archivo sin procedencia verificable» y el UPS queda vacío. Antes la página lo rotulaba «demo» y
    decía que la FC la había elegido el estudiante en un slider."""
    from app.main import CSV_SAVE_BLOCKER
    from domain.physiology.state import get_latest_state
    from src.signals.ecg.dynamic_ecg_generator import DynamicECGGenerator

    sf, pid = ups
    signal = DynamicECGGenerator(fs=250.0).generate(duration=20, hr=75)
    csv_bytes = ("ecg\n" + "\n".join(f"{v:.6f}" for v in signal)).encode()
    at = _ecg_monitor(sf, pid, csv_bytes)
    next(r for r in at.sidebar.radio if r.label == "Origen del ECG").set_value("CSV local").run()
    assert at.exception == [], at.exception
    texts = " ".join(visible_texts(at))
    assert "**Frecuencia cardíaca**" in " ".join(m.value for m in at.main.markdown)       # sí se analizó
    assert "Fuente:** demo" not in " ".join(m.value for m in at.main.markdown)
    assert "slider" not in texts
    assert "archivo sin procedencia verificable" in CSV_SAVE_BLOCKER
    assert any(CSV_SAVE_BLOCKER in w.value for w in at.warning)
    button = next(b for b in at.button if b.key == "ecg_lab_save_to_ups")
    assert button.disabled
    with pytest.raises(AppTestError, match="disabled"):
        button.click().run()
    with sf() as s:
        assert get_latest_state(s, pid) is None


# ------------------------------------------------------------------------------------ B. Caso ciego sin clave
@pytest.fixture
def blind_case_without_ai(ups, monkeypatch):
    import app.supermodules.academia.pages as academia

    for var in NO_AI_VARS:
        monkeypatch.delenv(var, raising=False)

    def _no_ai(*a, **k):
        raise AssertionError("la corrección no debe llamar a ningún modelo de lenguaje")

    monkeypatch.setattr(academia, "stream_findings_narration", _no_ai)
    sf, _ = ups

    def _script():
        from app.supermodules.academia.pages import render_synthetic_case_section
        render_synthetic_case_section()

    at = AppTest.from_function(_script, default_timeout=240)
    at.session_state["academia_case_session_factory"] = sf
    at.run()
    assert at.exception == [], at.exception
    assert not any(w.value.startswith("La IA está apagada") for w in at.warning)    # ya no bloquea el caso
    next(b for b in at.button if b.key == "academia_case_new").click().run()
    assert at.exception == [], at.exception
    return at


def _answer_blind(at, pick):
    from app.supermodules.twin_shell.pages import RICH_SCENARIO_LABELS

    hidden = at.session_state["academia_case_hidden_scenario"]
    options = at.session_state["academia_case_options"]
    choice = hidden if pick == "correct" else next(o for o in options if o != hidden)
    next(r for r in at.radio if r.label == "¿Cuál es tu diagnóstico?").set_value(RICH_SCENARIO_LABELS[choice]).run()
    next(b for b in at.button if b.key.startswith("academia_case_confirm_")).click().run()
    assert at.exception == [], at.exception
    return hidden, choice, RICH_SCENARIO_LABELS


def test_the_blind_case_is_corrected_without_an_ai_key_when_right(blind_case_without_ai):
    from clinical.calculators import NEWS2_CITATION

    at = blind_case_without_ai
    hidden, _, labels = _answer_blind(at, "correct")
    assert [s.value for s in at.success] == [f"¡Correcto! El caso era: {labels[hidden]}"]
    text = " ".join(m.value for m in at.markdown)
    assert "Qué mostró el caso, con su criterio citado:" in text
    assert any(NEWS2_CITATION in c.value for c in at.caption)
    assert "Narración con IA (opcional; no es la corrección):" in text
    assert not any(b.key.startswith("academia_case_narrate_") for b in at.button)     # sin clave, ni el botón
    assert at.error == []


def test_the_blind_case_is_corrected_without_an_ai_key_when_wrong(blind_case_without_ai):
    at = blind_case_without_ai
    hidden, choice, labels = _answer_blind(at, "wrong")
    assert [e.value for e in at.error] == [f"Elegiste {labels[choice]} — el caso real era {labels[hidden]}"]
    assert any(m.value.startswith("- ") for m in at.markdown)                          # la evidencia del caso


# ---------------------------------------------------------------------------------- C. pulso por luz saturado
def test_the_ppg_amplitude_floor_is_heuristic_and_sits_between_its_calibration_points():
    """Calibración (2026-11-16): sin pulso, el filtro deja ≤ 2.5e-9 cuentas con la señal pegada al tope y hasta 2.4
    cuentas con ruido de cuantización (σ = 0.5 cuentas, 50 semillas); el pulso más chico probado (índice de perfusión
    0.02 % sobre 50 000 cuentas, el umbral de «sin dedo») deja 11.9. El piso queda entre los dos."""
    from src.signals.ppg import analysis as ppg_analysis
    from src.signals.ppg import analyze_ppg

    import inspect

    floor = ppg_analysis.MIN_PULSE_AMPLITUDE_COUNTS
    source = inspect.getsource(ppg_analysis)
    assert "# HEURISTIC" in source.split("MIN_PULSE_AMPLITUDE_COUNTS =")[0].rsplit("\n\n", 1)[-1]   # rotulada
    noise = [np.ptp(ppg_analysis.pulse_wave(np.round(120000 + np.random.default_rng(k).normal(0, 0.5, 1000)), 100.0))
             for k in range(50)]
    assert max(noise) < floor
    for k in range(50):
        quantized = np.round(120000 + np.random.default_rng(k).normal(0, 0.5, 1000))
        assert analyze_ppg(quantized, quantized, 100.0).pulse_rate_bpm is None, k

    t = np.arange(2000) / 100.0
    pulse = sum(np.exp(-0.5 * ((t - b - 0.15) / 0.06) ** 2) + 0.45 * np.exp(-0.5 * ((t - b - 0.4) / 0.09) ** 2)
                for b in np.arange(0, 20, 60 / 72))
    pulse /= np.ptp(pulse[200:-200])
    smallest = np.round(50000.0 * (1 - 0.0002 * pulse))
    a = analyze_ppg(smallest, smallest, 100.0)
    assert np.ptp(a.wave) > floor and a.pulse_rate_bpm == pytest.approx(72.0, abs=1.0)


def test_a_saturated_ppg_never_shows_a_rate_or_a_rhythm():
    """Saturada con algo de pulso por debajo del tope: ni frecuencia, ni índice de perfusión, ni R, ni «irregular»."""
    from app.supermodules.biosensors.ppg import render_ppg_cards
    from hardware.biosensors.quality import PPG_FULL_SCALE, ppg_quality
    from src.signals.ppg import analyze_ppg

    t = np.arange(3000) / 100.0
    rng = np.random.default_rng(4)
    beats = np.cumsum(60 / 72 * (1 + 0.45 * rng.uniform(-1, 1, 60)))
    dips = sum(np.exp(-0.5 * ((t - b) / 0.06) ** 2) for b in beats)
    clipped = np.minimum(PPG_FULL_SCALE * 1.01 * (1 - 0.02 * dips), PPG_FULL_SCALE)
    analysis = analyze_ppg(clipped, clipped, 100.0)
    issues = ppg_quality(analysis)
    assert "saturada" in issues and "irregular" not in issues

    def _script(analysis, issues):
        from app.supermodules.biosensors.ppg import render_ppg_cards
        render_ppg_cards(analysis, issues)

    at = AppTest.from_function(_script, args=(analysis, issues)).run()
    assert at.exception == [], at.exception
    html = " ".join(m.value for m in at.markdown)
    for label in ("Frecuencia de pulso", "Índice de perfusión (IR)", "R (rojo / infrarrojo)"):
        assert f'data-label="{label}" data-value=""' in html, label
    assert "lpm" not in html
    assert render_ppg_cards                                                            # la vista real, importable
