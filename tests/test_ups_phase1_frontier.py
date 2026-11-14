"""Frente cardiovascular, Fase 1, PARTE A (2026-11-12, Art. I): frontera del UPS.

Decisiones firmadas por Luis que se prueban aquí:
- 3: `cardiac_output` solo desde el motor hemodinámico base (hoy no lo calcula: no se escribe);
- 4: el riesgo cardiaco son los puntos NEWS2 del pulso (única entrada: `heart_rate`);
- 6: un derivado hereda la MENOR confianza de sus entradas;
- «entradas viejas»: una entrada cuenta solo si llegó en la actualización ACTUAL; una anterior solo puede usarse como
  ARRASTRE_TEMPORAL dentro de la MISMA compuerta temporal del compositor; pasada la compuerta, no existe.
Todo contra bases/organismos temporales.
"""

import ast
from datetime import timedelta
from pathlib import Path

import pytest

from app.engines.digital_twin_organism import DigitalTwinOrganism
from clinical.calculators import news2_pulse_score, news2_score
from domain.physiology.state import Provenance, from_digital_twin_organism
from domain.physiology.state import builder as ups_builder
from domain.physiology.state import composer
from domain.physiology.state.derived_contract import DERIVED_CONTRACT, derived_confidence


def _state(organism, **kw):
    return from_digital_twin_organism(organism, "p", provenance=Provenance.SIMULACION, **kw)


# ------------------------------------------------------------------------------------------- NEWS2 del pulso
@pytest.mark.parametrize("hr, points", [
    (40, 3), (40.4, 3), (40.5, 1), (41, 1), (50, 1), (50.4, 1), (50.5, 0), (51, 0), (90, 0), (90.4, 0), (90.5, 1),
    (91, 1), (110, 1), (110.4, 1), (110.5, 2), (111, 2), (130, 2), (130.4, 2), (130.5, 3), (131, 3), (20, 3), (200, 3),
])
def test_news2_pulse_bands_and_half_up_rounding(hr, points):
    # tabla verificada (RCP 2017, PMC8244393): ≤40 → 3; 41–50 → 1; 51–90 → 0; 91–110 → 1; 111–130 → 2; ≥131 → 3
    assert news2_pulse_score(hr) == points


def test_news2_pulse_is_the_single_copy_of_the_table_and_rejects_non_finite():
    assert [news2_score(respiratory_rate=16, spo2=98, on_oxygen=False, systolic_bp=120, pulse=hr, alert=True,
                        temperature_c=37.0).components["Pulso"] for hr in (40, 41, 91, 111, 131)] == [3, 1, 1, 2, 3]
    for bad in (float("nan"), float("inf"), None):
        with pytest.raises(ValueError):
            news2_pulse_score(bad)


# ------------------------------------------------------------------------------------------ confianza (decisión 6)
def test_a_derived_value_inherits_the_lowest_confidence_of_its_inputs():
    organism = DigitalTwinOrganism()
    organism.update_from_sensors({
        "ecg": {"heart_rate": 72.0},
        "respiratory": {"respiratory_rate": 16.0, "spo2": 97.0, "ahi": 3.0},
    })
    state = _state(organism, confidence=0.75,
                   input_confidence={"heart_rate": 0.9, "respiratory_rate": 0.8, "spo2": 0.7, "ahi": 0.55})
    resp = state.respiratory.descriptors
    assert resp["respiratory_rate"].confidence == pytest.approx(0.8)               # las medidas conservan la suya
    assert resp["health_score"].confidence == pytest.approx(0.55)                  # min(rr 0.8, spo2 0.7, ahi 0.55)
    assert resp["news2_respiratory_rate_points"].confidence == pytest.approx(0.8)   # solo rr (fase 0: sustituye a risk_score)
    assert resp["news2_spo2_scale1_points"].confidence == pytest.approx(0.7)        # solo spo2 (fase 0: sustituye a hypoxia_risk)
    assert state.cardiovascular.get("news2_pulse_points").confidence == pytest.approx(0.9)   # su única entrada
    assert all(d.confidence != pytest.approx(0.75) for d in resp.values())          # ninguno es la constante del escritor


def test_an_input_without_its_own_confidence_inherits_the_writers():
    assert derived_confidence("respiratory", "health_score", {"respiratory_rate", "spo2", "ahi"},
                              {"spo2": 0.6}, 0.8) == pytest.approx(0.6)
    assert derived_confidence("respiratory", "health_score", {"respiratory_rate", "spo2", "ahi"}, None, 0.8) == pytest.approx(0.8)
    # un derivado de una sola entrada hereda exactamente la de esa entrada
    assert derived_confidence("respiratory", "news2_spo2_scale1_points", {"spo2", "respiratory_rate"},
                              {"spo2": 0.4, "respiratory_rate": 0.9}, 0.7) == pytest.approx(0.4)
    with pytest.raises(ValueError):
        derived_confidence("respiratory", "health_score", {"spo2"}, None, 0.8)       # no escribible: no hay confianza


# ------------------------------------------------------------------------------- entradas viejas (compuerta temporal)
def _heart_then_respiratory(hr=72.0):
    organism = DigitalTwinOrganism()
    organism.update_from_sensors({"ecg": {"heart_rate": hr, "hrv": 40.0}})
    organism.update_from_sensors({"respiratory": {"respiratory_rate": 16.0, "spo2": 97.0}})
    return organism


def test_the_gate_is_the_compositors_constant_not_a_new_one():
    assert ups_builder.DEFAULT_MAX_HR_CARRY_AGE_S is composer.DEFAULT_MAX_HR_CARRY_AGE_S
    assert composer.DEFAULT_MAX_HR_CARRY_AGE_S == 120.0


def test_an_input_from_a_previous_update_is_only_carried_never_current_never_derived():
    organism = _heart_then_respiratory()
    assert organism.inputs_are_current("lungs") and not organism.inputs_are_current("heart")
    state = _state(organism)
    cardio = state.cardiovascular.descriptors
    assert set(cardio) == {"heart_rate", "hrv"}                                     # sin news2_pulse_points
    assert all(d.provenance == Provenance.ARRASTRE_TEMPORAL for d in cardio.values())
    assert "arrastrada de una actualización anterior" in cardio["heart_rate"].source_detail
    # lo que SÍ llegó en la actualización actual conserva su procedencia y sus derivados
    assert state.respiratory.get("spo2").provenance == Provenance.SIMULACION
    assert "news2_spo2_scale1_points" in state.respiratory.descriptors


def test_an_old_input_beyond_the_gate_does_not_exist():
    organism = _heart_then_respiratory(hr=150.0)
    heart = organism.organs["heart"].metrics
    heart.signals_at -= timedelta(seconds=119)                                       # dentro de la compuerta: arrastre
    inside = _state(organism)
    assert set(inside.cardiovascular.descriptors) == {"heart_rate", "hrv"}
    heart.signals_at -= timedelta(seconds=2)                                         # 121 s > 120 s: no existe
    outside = _state(organism)
    assert outside.cardiovascular.descriptors == {}
    # y tampoco genera eventos: una FC de 150 lpm vencida no es un hallazgo de hoy
    assert not [e for e in outside.events if e.domain == "cardiovascular"]
    assert [e for e in inside.events if e.domain == "cardiovascular"] == []          # arrastrada: tampoco evento


def test_current_inputs_still_produce_events_and_everything_is_current_after_a_single_update():
    organism = DigitalTwinOrganism()
    organism.update_from_sensors({"ecg": {"heart_rate": 150.0}, "respiratory": {"respiratory_rate": 16.0, "spo2": 88.0}})
    state = _state(organism)
    assert state.cardiovascular.get("heart_rate").provenance == Provenance.SIMULACION
    assert {e.domain for e in state.events} == {"cardiovascular", "respiratory"}


# ------------------------------------------------------------------- cardiac_output (decisión 3), con evidencia
def test_cardiac_output_is_only_from_the_hemodynamic_engine_and_that_engine_does_not_compute_it():
    rule = DERIVED_CONTRACT["cardiovascular"]["cardiac_output"]
    assert rule.inputs == () and rule.only_from.startswith("motor hemodinámico base")
    organism = DigitalTwinOrganism()
    organism.update_from_sensors({"ecg": {"heart_rate": 72.0, "hrv": 40.0}})
    assert "cardiac_output" not in _state(organism).cardiovascular.descriptors
    # El motor de escenarios NO es el motor hemodinámico: no importa nada de `domain.physiology.hemodynamics`
    # (sus `cardiac_output` son literales por escenario), así que su gasto es «no modelado» para el UPS.
    tree = ast.parse(Path("app/engines/simulation_engine.py").read_text(encoding="utf-8"))
    imported = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)] + [
        a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names
    ]
    assert not [m for m in imported if "hemodynamics" in m or "svzero" in m.lower()], imported
    # y el motor RCR base recibe el flujo como ENTRADA (nada llamado cardiac_output sale de él)
    for name in ("r_rcr.py", "ups_bridge.py", "closed_loop_ups_bridge.py"):
        assert "cardiac_output" not in (Path("domain/physiology/hemodynamics") / name).read_text(encoding="utf-8")
