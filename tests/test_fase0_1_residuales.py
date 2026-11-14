"""Fase 0, tanda 0.1 (2026-11-13, Art. I): residuales.

1. Evento de SpO₂ del UPS = banda de 3 puntos NEWS2 escala 1 (≤ 91 %); sin umbral 95; sin evento de estrés > 75.
2. Índice de salud pulmonar (pesos 0.5/0.3/0.4 sin cita): fuera del organismo, del contrato y de la UI.
3. Filas históricas de tipos retirados purgadas (con respaldo); los tipos fuera de `EventType`.
4. Estados transversales retirados (aceptado).
Declaración de la sepsis: sección «qué calcula el modelo y qué está prescrito», capacitancia rotulada, gasto en revisión.
"""

import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from app.engines import digital_twin_organism as dto
from app.engines.digital_twin_organism import NOT_MODELED, DigitalTwinOrganism
from domain.physiology.state import EventSeverity, EventType, Provenance, from_digital_twin_organism
from domain.physiology.state.derived_contract import DERIVED_CONTRACT


def _state(sensors):
    organism = DigitalTwinOrganism()
    organism.update_from_sensors(sensors)
    return organism, from_digital_twin_organism(organism, "p", provenance=Provenance.SIMULACION)


# ------------------------------------------------------------------------------------- 1: eventos de SpO₂ y estrés
@pytest.mark.parametrize("spo2, fires", [(85, True), (91, True), (91.4, True), (91.5, False), (92, False), (94, False), (98, False)])
def test_the_spo2_event_is_the_news2_3_point_band_at_the_91_92_boundary(spo2, fires):
    _, state = _state({"respiratory": {"respiratory_rate": 16.0, "spo2": float(spo2)}})
    events = [e for e in state.events if e.domain == "respiratory"]
    assert bool(events) is fires, (spo2, events)
    if fires:
        (event,) = events
        assert event.event_type == EventType.SPO2_NEWS2_3_POINTS and event.severity == EventSeverity.WARNING
        assert "3 puntos NEWS2" in event.description and event.related_descriptor == "news2_spo2_scale1_points"


def test_no_stress_event_and_no_stress_alert_at_all():
    organism, state = _state({"eeg": {"stress_level": 95.0, "alpha_power": 5.0, "beta_power": 20.0}})
    assert [e for e in state.events if e.domain == "neurological"] == []
    assert organism.global_state["alerts"] == [] and organism.global_state["recommendations"] == []
    assert not any("estrés" in a.lower() for a in organism.global_state["anomalies"])


def test_the_retired_event_types_are_gone_from_the_catalog_and_the_builder():
    names = {e.name for e in EventType}
    assert names == {"PULSE_NEWS2_3_POINTS", "SPO2_NEWS2_3_POINTS", "HYPOXIA_SPO2_LOW", "SEVERE_MUSCLE_FATIGUE_EMG"}
    builder = re.sub(r'"""[\s\S]*?"""', "", Path("domain/physiology/state/builder.py").read_text(encoding="utf-8"))
    code = "\n".join(l for l in builder.splitlines() if not l.lstrip().startswith("#"))
    for gone in ("HYPOXIA_SPO2_LOW", "HYPOXIA_SPO2_CRITICAL", "HIGH_STRESS_EEG", "spo2 < 90", "spo2 < 95", "stress_level > 75"):
        assert gone not in code, gone


# ------------------------------------------------------------------------------------------ 2: índice pulmonar
def test_no_lung_health_index_in_the_organism_the_ups_or_the_ui():
    organism, state = _state({"respiratory": {"respiratory_rate": 16.0, "spo2": 98.0, "ahi": 2.0}})
    assert not hasattr(organism.organs["lungs"].metrics, "health_score") and not hasattr(dto, "OrganHealthStatus")
    assert "health_score" not in state.respiratory.descriptors
    assert DERIVED_CONTRACT["respiratory"]["health_score"].never_reason
    assert "0.5/0.3/0.4" not in organism.generate_clinical_summary() and "health_score" not in organism.to_json()
    pages = Path("app/supermodules/twin_shell/pages.py").read_text(encoding="utf-8")
    assert "health_score" not in pages and "_LUNG_HEALTH_HELP" not in pages
    organism_src = re.sub(r'"""[\s\S]*?"""', "", Path(dto.__file__).read_text(encoding="utf-8"))
    assert not re.search(r"^\s*[^#\n]*health_score", organism_src, re.M)


# ------------------------------------------------------------------------------------------ 3: base de desarrollo
def test_the_dev_database_has_no_rows_of_retired_event_types_and_a_backup_exists():
    import sqlite3

    db = Path("data/biocore_ups.db")
    if not db.exists():
        pytest.skip("sin base de desarrollo en este entorno")
    c = sqlite3.connect(db)
    types = {t for (t,) in c.execute("select distinct event_type from ups_events")}
    c.close()
    assert not ({"arrhythmia_risk_hr_extreme", "low_hrv_autonomic_stress"} & types)
    assert all(EventType(t) for t in types)                                   # todo lo que queda se puede leer
    assert Path("data/biocore_ups.backup-20261113-fase0.1.db").exists()


# ------------------------------------------------------------------------------- 4: estados transversales (aceptado)
def test_cross_cutting_states_stay_retired():
    for gone in ("StressState", "RecoveryState", "PerformanceState"):
        assert not hasattr(dto, gone)
    organism = DigitalTwinOrganism()
    assert not any(hasattr(organism, a) for a in ("stress", "recovery", "performance"))


# ------------------------------------------------------------------------------------ declaración de la sepsis
def test_cardiac_output_is_in_clinical_review_only_in_sepsis_and_never_written():
    organism = DigitalTwinOrganism()
    organism.update_from_sensors({"ecg": {"heart_rate": 72.0}})
    assert organism.cardiac_output_label() == NOT_MODELED
    organism.apply_sepsis("24h")
    assert organism.cardiac_output_label() == dto.CARDIAC_OUTPUT_IN_REVIEW == "calculado por el motor — en revisión clínica"
    summary = organism.generate_clinical_summary()
    assert dto.CARDIAC_OUTPUT_IN_REVIEW in summary and "L/min" not in summary
    state = from_digital_twin_organism(organism, "p", provenance=Provenance.SIMULACION)
    assert "cardiac_output" not in state.cardiovascular.descriptors
    assert DERIVED_CONTRACT["cardiovascular"]["cardiac_output"].never_reason


def test_the_sepsis_scenario_screen_declares_what_is_computed_and_what_is_prescribed(tmp_path):
    from domain.physiology.state import create_patient, init_db, make_engine, make_session_factory

    engine = make_engine(tmp_path / "sepsis_decl.db")
    init_db(engine)
    sf = make_session_factory(engine)
    with sf() as s:
        pid = create_patient(s, display_name="sepsis decl")

    def _script():
        import app.supermodules.twin_shell.pages as m
        m.run()

    at = AppTest.from_function(_script, default_timeout=180)
    at.session_state["twin_shell_ups_session_factory"] = sf
    at.session_state["twin_shell_ups_patient_id"] = pid
    at.run()
    assert at.exception == []
    from app.engines.simulation_engine import SimulationScenario

    at.selectbox(key="twin_shell_rich_scenario_select").set_value(SimulationScenario.SEPSIS).run()
    assert at.exception == []
    text = " ".join(" ".join(str(e.value).split()) for e in list(at.markdown) + list(at.info))
    assert "Qué calcula el modelo y qué está prescrito" in text
    assert "Prescrito" in text and "frecuencia cardíaca" in text and "vasoplejía" in text
    assert "Calculado por el motor" in text and "retorno venoso" in text and "volumen sistólico" in text and "presión arterial" in text
    assert "capacitancia venosa 2× — Criterio BIOCORE, sin cita (en revisión clínica)" in text
    assert "gasto cardíaco" in text and "en revisión clínica, sin cifra" in text
    assert "85/55" in text and "PAM 65" in text and "Sepsis‑3" in text
    assert not re.search(r"\d+[.,]\d+\s*L/min", text)                           # el gasto nunca aparece como número
    # el panel del corazón, con la sepsis aplicada, tampoco muestra cifra de gasto
    at.selectbox(key="twin_shell_sepsis_horizon").set_value("24h").run()
    at.button(key="twin_shell_sepsis_apply").click().run()
    assert at.exception == []
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Gasto cardíaco"] == dto.CARDIAC_OUTPUT_IN_REVIEW
