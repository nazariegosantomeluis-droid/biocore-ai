"""Cierre de la fase 0, PARTE B (2026-11-13, Art. I): órganos no cardiacos sin defaults, con la misma lógica que el corazón.

Decisión 6 de Luis: respiratorio sin `ahi = 0` y con puntos NEWS2 de FR y SpO₂ (escala 1) en vez de `hypoxia_risk`/
`risk_score` (escala 2 «no modelada»); cerebro, músculos y autonómico sin `health_score`/`risk_score` ni umbrales
HRV < 15/30; campos fantasma de los detalles eliminados. Golden tests: solo respiratorio, sliders, fronteras de SpO₂.
"""

import json
import re

import pytest

from app.engines import digital_twin_organism as dto
from app.engines.digital_twin_organism import NO_DATA, NOT_MODELED, DigitalTwinOrganism
from clinical.calculators import news2_score, news2_spo2_scale1_score
from domain.physiology.state import Provenance, from_digital_twin_organism
from domain.physiology.state.derived_contract import DERIVED_CONTRACT, derived_is_writable

SLIDERS = {"ecg": {"heart_rate": 72, "hrv": 50}, "eeg": {"stress_level": 35},
           "respiratory": {"respiratory_rate": 16, "spo2": 98}, "emg": {"fatigue_index": 20}}


def _fed(sensors):
    organism = DigitalTwinOrganism()
    organism.update_from_sensors(sensors)
    return organism


# ------------------------------------------------------------------------------ SpO₂ escala 1: la tabla del repo
@pytest.mark.parametrize("spo2, points", [
    (85, 3), (91, 3), (91.4, 3), (91.5, 2), (92, 2), (93, 2), (93.4, 2), (93.5, 1), (94, 1), (95, 1), (95.4, 1),
    (95.5, 0), (96, 0), (100, 0),
])
def test_news2_spo2_scale1_bands_match_the_repo_table_with_half_up_rounding(spo2, points):
    # tabla del repo (RCP 2017, contrastada con PMC8244393; tests/test_respiratory_phase42.py): ≤91 → 3; 92–93 → 2;
    # 94–95 → 1; ≥96 → 0
    assert news2_spo2_scale1_score(spo2) == points


def test_news2_spo2_scale1_is_the_single_copy_of_the_table_and_rejects_non_finite():
    for spo2, points in ((91, 3), (92, 2), (94, 1), (96, 0)):
        result = news2_score(respiratory_rate=16, spo2=spo2, on_oxygen=False, systolic_bp=120, pulse=72, alert=True,
                             temperature_c=37.0)
        assert result.components["SpO₂ (escala 1)"] == points
    for bad in (float("nan"), float("inf"), None):
        with pytest.raises(ValueError):
            news2_spo2_scale1_score(bad)


# ---------------------------------------------------------------------------------- solo respiratorio (FR y SpO₂ reales)
def test_respiratory_only_gives_the_two_news2_points_and_nothing_computed_with_ahi():
    organism = _fed({"respiratory": {"respiratory_rate": 14.0, "spo2": 97.0}})
    lungs = organism.organs["lungs"].metrics
    assert (lungs.rr_points, lungs.spo2_points) == (0, 0)
    assert lungs.health_score is None                                         # exige AHI real: no se calcula con ahi = 0
    assert lungs.signals == {"respiratory_rate": 14.0, "spo2": 97.0}        # exactamente lo que llegó
    state = from_digital_twin_organism(organism, "p", provenance=Provenance.SIMULACION)
    assert set(state.respiratory.descriptors) == {
        "respiratory_rate", "spo2", "news2_respiratory_rate_points", "news2_spo2_scale1_points",
    }
    for name in ("risk_score", "hypoxia_risk", "apnea_risk", "health_score", "tissue_oxygenation"):
        assert name not in state.respiratory.descriptors
    points = state.respiratory.get("news2_spo2_scale1_points")
    assert points.provenance == Provenance.DERIVADO and "escala 2 no se modela" in points.source_detail
    assert state.cardiovascular.descriptors == {} and state.neurological.descriptors == {}
    assert not hasattr(dto, "RespiratoryDetail") and not hasattr(dto, "NeurologicalDetail")
    assert not hasattr(dto, "MusculoskeletalDetail") and not hasattr(dto, "AutonomicDetail")
    assert organism.generate_clinical_summary().count(NOT_MODELED) >= 2    # gasto cardiaco y SpO₂ escala 2


def test_the_lung_health_index_needs_rr_spo2_and_ahi_all_real():
    with_ahi = _fed({"respiratory": {"respiratory_rate": 16.0, "spo2": 98.0, "ahi": 2.0}})
    assert with_ahi.organs["lungs"].metrics.health_score is not None
    state = from_digital_twin_organism(with_ahi, "p", provenance=Provenance.SIMULACION)
    assert "health_score" in state.respiratory.descriptors and "apnea_risk" not in state.respiratory.descriptors
    assert derived_is_writable("respiratory", "health_score", {"respiratory_rate", "spo2", "ahi"})
    assert not derived_is_writable("respiratory", "health_score", {"respiratory_rate", "spo2"})


@pytest.mark.parametrize("spo2, points, color", [(97, 0, "#39ffbe"), (94, 1, "#ffd700"), (92, 2, "#ffd700"), (85, 3, "#ff3333")])
def test_the_lungs_are_colored_by_their_news2_points(spo2, points, color):
    organism = _fed({"respiratory": {"respiratory_rate": 16.0, "spo2": float(spo2)}})
    assert organism.organs["lungs"].metrics.spo2_points == points and organism.organs["lungs"].color == color


# ------------------------------------------------------------------------------- sliders: nada «Alerta» ni «Crítico»
def test_with_sliders_brain_and_autonomic_no_longer_come_out_alert_or_critical_from_defaults():
    organism = _fed(SLIDERS)
    for organ_id in ("brain", "muscles", "autonomic"):
        organ = organism.organs[organ_id]
        assert organ.metrics.health_score is None and organ.status is None, organ_id   # sin índice: ni «Alerta» ni «Crítico»
        assert organ.color == dto.HAS_DATA_COLOR                                       # hay entrada, sin criterio
    assert organism.organs["brain"].metrics.signals == {"stress_level": 35}
    assert organism.organs["muscles"].metrics.signals == {"fatigue_index": 20}
    assert organism.organs["autonomic"].metrics.signals == {"hrv": 50}                 # la HRV como HRV
    assert organism.organs["lungs"].metrics.health_score is None                      # sin AHI
    assert not any("Alerta" in a or "Crítico" in a for a in organism.global_state["alerts"])
    exported = json.loads(organism.to_json())
    dumped = json.dumps(exported)
    for gone in ("health_score\": 5", "risk_score", "activity_level", "relaxation", "efficiency", "detail",
                 "mental_workload", "stress_perception", "neuromuscular_efficiency", "recovery", "performance"):
        assert gone not in dumped, gone


def test_no_default_inputs_remain_in_the_organism_source():
    source = open(dto.__file__, encoding="utf-8").read()
    code = re.sub(r'"""[\s\S]*?"""', "", "\n".join(l for l in source.splitlines() if not l.lstrip().startswith("#")))
    for pattern in (r"""\.get\(\s*["'][a-z_]+["']\s*,\s*\d""", r"relaxation", r"efficiency", r"hrv\s*<\s*\d",
                    r"spo2\s*<\s*9", r"stress_level\s*>\s*50", r"fatigue\s*>\s*\d", r"ahi\s*>\s*\d", r"\bdetail\b"):
        assert not re.search(pattern, code), pattern


# --------------------------------------------------------------------------------------- contrato: lo retirado es NUNCA
def test_the_contract_declares_every_retired_non_cardiac_derivative_as_never():
    never = {f for domain in ("neurological", "muscular") for f, r in DERIVED_CONTRACT[domain].items() if r.never_reason}
    assert never == {"health_score", "risk_score", "mental_workload", "cognitive_fatigue", "attention", "stress_perception",
                     "sleepiness", "neuromuscular_efficiency", "movement_smoothness"}
    assert all(r.never_reason for r in DERIVED_CONTRACT["neurological"].values())
    assert all(r.never_reason for r in DERIVED_CONTRACT["muscular"].values())
    resp = DERIVED_CONTRACT["respiratory"]
    assert {f for f, r in resp.items() if r.never_reason} == {"risk_score", "hypoxia_risk", "apnea_risk", "tissue_oxygenation"}
    assert derived_is_writable("respiratory", "news2_spo2_scale1_points", {"spo2"})
    assert derived_is_writable("respiratory", "news2_respiratory_rate_points", {"respiratory_rate"})
    assert not derived_is_writable("respiratory", "news2_spo2_scale1_points", {"respiratory_rate"})


def test_eeg_and_emg_lab_payloads_write_only_what_they_measure():
    eeg = _fed({"eeg": {"delta_power": 1, "theta_power": 2, "alpha_power": 10, "beta_power": 5, "gamma_power": 1}})
    neuro = from_digital_twin_organism(eeg, "p", provenance=Provenance.SIMULACION).neurological.descriptors
    assert set(neuro) == {"delta_power", "theta_power", "alpha_power", "beta_power", "gamma_power", "bar", "dar", "tbr"}
    emg = _fed({"emg": {"activation": 30.0, "median_frequency": 110.0, "efficiency": 72.0, "fatigue_index": 15.0}})
    musc = from_digital_twin_organism(emg, "p", provenance=Provenance.SIMULACION).muscular.descriptors
    assert set(musc) == {"activation", "median_frequency"}                        # ni con efficiency/fatigue reales hay derivado


def test_an_unfed_organism_is_no_data_everywhere():
    organism = DigitalTwinOrganism()
    assert all(o.color == dto.NO_DATA_COLOR and o.metrics.signals == {} for o in organism.organs.values())
    assert organism.explain_state().count(NO_DATA) == 2                           # NEWS2 parcial y razón FC:FR
    assert not organism.global_state["news2_partial"].available
    summary = organism.generate_clinical_summary()
    assert not re.search(r"\d", summary.split("Procedencia")[1].replace("NEWS2", "").replace("escala 1", "").replace("escala 2", "").replace("0.5/0.3/0.4", "").split("📊")[0].replace("de 3", ""))
