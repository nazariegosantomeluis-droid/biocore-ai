"""Cierre de la fase 0, PARTE C (2026-11-13, Art. I): índices globales, riesgo global y eventos (decisiones 1–5 de Luis).

1. Retirados: estado fisiológico global, coherencia, resiliencia, Cerebro↔Corazón y Cerebro↔Músculos.
2. Riesgo global: NEWS2 PARCIAL (puntos por parámetro disponible + lo que falta para el total); nunca un total.
3. Corazón↔Pulmones: razón FC:FR descriptiva; la referencia ≈4:1 solo porque Scholkmann & Wolf 2019 se leyó completo.
4. Línea de tiempo: FC y puntos NEWS2 del pulso.
5. Evento de FC del UPS = banda de 3 puntos NEWS2 (≤40 o ≥131), renombrado; el evento por hrv < 20 se retiró.
"""

import re
from pathlib import Path

import pytest

from app.engines.digital_twin_organism import NO_DATA, DigitalTwinOrganism
from app.engines.prediction_engine import PredictionEngine
from clinical.calculators import NEWS2_PARAMETERS_NOT_MODELED, PRQ_REFERENCE, news2_partial, pulse_respiration_quotient
from domain.physiology.state import EventSeverity, EventType, Provenance, from_digital_twin_organism
from src.signals.ecg.arrhythmia_types import EVENT_DEPENDS_ON_HR, get_type


def _fed(sensors):
    organism = DigitalTwinOrganism()
    organism.update_from_sensors(sensors)
    return organism


# ------------------------------------------------------------------------------------- 1 y 2: NEWS2 parcial, sin total
def test_news2_partial_lists_what_is_missing_and_has_no_total():
    partial = news2_partial(pulse=72, respiratory_rate=16, spo2=98)
    assert partial.components == {"Pulso": 0, "Frecuencia respiratoria": 0, "SpO₂ (escala 1)": 0}
    assert partial.missing == NEWS2_PARAMETERS_NOT_MODELED
    assert set(NEWS2_PARAMETERS_NOT_MODELED) == {"presión arterial sistólica", "temperatura", "nivel de consciencia (ACVPU)",
                                                  "oxígeno suplementario (aire u O₂)"}
    assert not any(name in dir(partial) for name in ("total", "score", "risk", "category"))
    only_rr = news2_partial(respiratory_rate=26.4)
    assert only_rr.components == {"Frecuencia respiratoria": 3} and only_rr.missing[:2] == ("pulso", "SpO₂")
    assert not news2_partial().available and news2_partial().missing[:3] == ("pulso", "frecuencia respiratoria", "SpO₂")


def test_the_organism_and_the_engine_never_expose_a_global_number():
    organism = _fed({"ecg": {"heart_rate": 72, "hrv": 50}, "respiratory": {"respiratory_rate": 16, "spo2": 98},
                     "eeg": {"stress_level": 35}, "emg": {"fatigue_index": 20}})
    g = organism.global_state
    assert set(g) == {"news2_partial", "hr_rr_ratio", "anomalies", "recommendations", "alerts"}
    sensor_data = {"ecg": organism.current_signals("heart"), "respiratory": organism.current_signals("lungs"),
                   "eeg": organism.current_signals("brain"), "emg": organism.current_signals("muscles")}
    assessment = PredictionEngine().assess_global_risk(organism, sensor_data, "t")
    for gone in ("global_risk_score", "risk_level", "monitoring_frequency", "critical_systems", "immediate_actions"):
        assert not hasattr(assessment, gone), gone
    assert assessment.news2_partial.components == {"Pulso": 0, "Frecuencia respiratoria": 0, "SpO₂ (escala 1)": 0}
    assert "sin total" in assessment.reason and "presión arterial sistólica" in assessment.reason
    text = organism.explain_state() + organism.generate_clinical_summary() + organism.to_json()
    for gone in ("Coherencia", "Resiliencia", "Estado Fisiológico Global", "Nivel de Riesgo", "neurocardiac", "neuromuscular_coupling"):
        assert gone not in text, gone
    assert "nunca: NEWS2 parcial" in organism.to_json()


# ------------------------------------------------------------------------------------------- 3: razón FC:FR descriptiva
def test_heart_lung_coupling_is_the_hr_rr_ratio_with_real_inputs_only():
    organism = _fed({"ecg": {"heart_rate": 64.0}, "respiratory": {"respiratory_rate": 16.0}})
    assert organism.global_state["hr_rr_ratio"] == pytest.approx(4.0)
    assert _fed({"ecg": {"heart_rate": 64.0}}).global_state["hr_rr_ratio"] is None             # sin FR actual
    assert _fed({"respiratory": {"respiratory_rate": 16.0}}).global_state["hr_rr_ratio"] is None   # sin FC actual
    assert pulse_respiration_quotient(72, 0) is None and pulse_respiration_quotient(float("nan"), 16) is None
    organism.update_from_sensors({"respiratory": {"respiratory_rate": 16.0}})                   # la FC pasa a vieja
    assert organism.global_state["hr_rr_ratio"] is None
    # la fuente de la referencia se verificó con texto completo; el texto citado es el del artículo
    assert "Scholkmann" in PRQ_REFERENCE and "10.3389/fphys.2019.00371" in PRQ_REFERENCE
    source = Path("clinical/calculators.py").read_text(encoding="utf-8")
    assert "distribution peaks at 3 and 4, corresponding to 3:1 and 4:1" in source


# ------------------------------------------------------------------------------------------------ 4: línea de tiempo
def test_the_history_keeps_heart_rate_and_pulse_points_not_retired_indices():
    organism = DigitalTwinOrganism()
    organism.update_from_sensors({"ecg": {"heart_rate": 72.0}})
    organism.update_from_sensors({"ecg": {"heart_rate": 140.0}})
    organism.update_from_sensors({"respiratory": {"respiratory_rate": 16.0}})                  # sin FC actual
    assert [(h["heart_rate"], h["news2_pulse_points"]) for h in organism.history] == [(72.0, 0), (140.0, 3), (None, None)]
    assert all(set(h) == {"timestamp", "heart_rate", "news2_pulse_points"} for h in organism.history)


# ------------------------------------------------------------------------------------ 5: eventos de FC en las fronteras
def _hr_events(hr):
    state = from_digital_twin_organism(_fed({"ecg": {"heart_rate": float(hr), "hrv": 10.0}}), "p", provenance=Provenance.SIMULACION)
    return [e for e in state.events if e.domain == "cardiovascular"]


@pytest.mark.parametrize("hr, fires", [(39, True), (40, True), (40.4, True), (40.5, False), (41, False), (130, False),
                                       (130.4, False), (130.5, True), (131, True), (185, True)])
def test_the_hr_event_is_the_news2_3_point_band_at_the_boundaries(hr, fires):
    events = _hr_events(hr)
    assert bool(events) is fires, (hr, events)
    if fires:
        (event,) = events
        assert event.event_type == EventType.PULSE_NEWS2_3_POINTS and event.severity == EventSeverity.WARNING
        assert "3 puntos NEWS2" in event.description and event.related_descriptor == "news2_pulse_points"


def test_the_hrv_event_and_the_old_hr_event_are_never_emitted_anymore():
    for hr, hrv in ((72.0, 5.0), (125.0, 10.0), (36.0, 50.0)):
        state = from_digital_twin_organism(_fed({"ecg": {"heart_rate": hr, "hrv": hrv}}), "p", provenance=Provenance.SIMULACION)
        types = {e.event_type.value for e in state.events}
        assert "low_hrv_autonomic_stress" not in types and "arrhythmia_risk_hr_extreme" not in types
    builder = Path("domain/physiology/state/builder.py").read_text(encoding="utf-8")
    code = re.sub(r'"""[\s\S]*?"""', "", builder)
    for gone in ("LOW_HRV_AUTONOMIC_STRESS", "ARRHYTHMIA_RISK_HR_EXTREME", "hr > 120", "hr < 40", "hr > 150", "hrv < 20"):
        assert gone not in code, gone
    assert EventType.PULSE_NEWS2_3_POINTS.value == "pulse_news2_3_points"                # dice lo que mide, no «arrhythmia_risk»


def test_arrhythmia_declarations_follow_the_new_rule():
    """Bradicardia sinusal 40-59: solo 40 lpm cae en la banda de 3 puntos -> depende de la FC (antes «nunca»)."""
    assert get_type("sbrady").ups_hr_event == EVENT_DEPENDS_ON_HR
    assert _hr_events(get_type("sbrady").hr_min_bpm) and not _hr_events(get_type("sbrady").hr_max_bpm)
    assert not _hr_events(get_type("stachy").nominal_hr_bpm) and _hr_events(get_type("stachy").hr_max_bpm)


def test_the_digital_body_paints_the_heart_by_the_news2_event():
    from app.supermodules.twin_shell import ups_body_visual as U

    assert U.EVENT_VISUAL_MAP[EventType.PULSE_NEWS2_3_POINTS][0] == "heart"
    warning = from_digital_twin_organism(_fed({"ecg": {"heart_rate": 140.0}}), "p", provenance=Provenance.SIMULACION)
    calm = from_digital_twin_organism(_fed({"ecg": {"heart_rate": 125.0, "hrv": 8.0}}), "p", provenance=Provenance.SIMULACION)
    assert U.organ_visual_state(warning)["heart"].color == U.SEVERITY_COLOR[EventSeverity.WARNING]
    assert U.organ_visual_state(calm)["heart"].color == U.STABLE_COLOR                      # 125 lpm / HRV 8: sin evento
    assert 'descriptors.get("mental_workload")' not in Path(U.__file__).read_text(encoding="utf-8")   # el cerebro ya no lo usa
