"""
Learning Hub — Trabajo 2, Fase 1 (2026-08-06): restricción estructural de
horizontes evaluables en `case_bank.generate_case()`.

Cubre que la matriz medida en la Fase 0 (ver CHANGELOG.md) se traduce
correctamente en `EVALUABLE_HORIZONS_BY_SCENARIO` y que `generate_case()`
NUNCA elige un horizonte fuera de esa lista para el escenario dado -- ni
por casualidad de semilla, verificado con muchas repeticiones, no una sola
corrida.
"""

import random

import pytest

from app.engines.simulation_engine import SimulationScenario
from domain.physiology.hemodynamics import HEMODYNAMIC_MODEL_ENABLED_SCENARIOS
from domain.physiology.scenarios.case_bank import (
    EVALUABLE_HORIZONS_BY_SCENARIO,
    generate_case,
)
from domain.physiology.state import init_db, make_engine, make_session_factory

_ALL_HORIZONS = {"now", "5min", "30min", "2h", "24h", "7d"}
_N_TRIALS = 40  # suficiente para que un horizonte prohibido, si se colara, aparezca


def _session_factory(path):
    engine = make_engine(path)
    init_db(engine)
    return make_session_factory(engine)


def test_evaluable_horizons_map_matches_the_measured_matrix():
    """Los 5 escenarios con restricción documentada, exactamente como midió
    la Fase 0 -- ni más ni menos horizontes que los medidos evaluables."""
    assert dict(EVALUABLE_HORIZONS_BY_SCENARIO) == {
        "seizure": frozenset({"now"}),
        "exercise": frozenset({"now", "5min", "30min"}),
        "stress": frozenset({"30min", "2h", "24h", "7d"}),
        "anxiety": frozenset({"5min", "30min"}),
        "hypoxia": frozenset({"30min", "2h", "24h", "7d"}),
    }


@pytest.mark.parametrize(
    "scenario_value,allowed",
    [
        ("seizure", {"now"}),
        ("exercise", {"now", "5min", "30min"}),
        ("stress", {"30min", "2h", "24h", "7d"}),
        ("anxiety", {"5min", "30min"}),
        ("hypoxia", {"30min", "2h", "24h", "7d"}),
    ],
)
def test_generate_case_never_chooses_a_forbidden_horizon(tmp_path, scenario_value, allowed):
    scenario = SimulationScenario(scenario_value)
    SessionLocal = _session_factory(tmp_path / f"case_bank_horizon_{scenario_value}.db")

    seen = set()
    with SessionLocal() as session:
        for i in range(_N_TRIALS):
            case = generate_case(session, scenario=scenario, rng=random.Random(2000 + i))
            horizon = case.parametros["horizonte_elegido"]
            assert horizon in allowed, (
                f"{scenario_value}: horizonte {horizon!r} elegido pero no está en {sorted(allowed)}"
            )
            seen.add(horizon)

    forbidden = _ALL_HORIZONS - allowed
    assert not (seen & forbidden), f"{scenario_value}: se coló un horizonte prohibido: {seen & forbidden}"


def test_seizure_always_uses_now_never_anything_else(tmp_path):
    """Caso extremo explícito: convulsión tiene un solo horizonte evaluable
    -- confirma que SIEMPRE es ese, en 40 corridas, no "casi siempre"."""
    SessionLocal = _session_factory(tmp_path / "case_bank_seizure_always_now.db")
    with SessionLocal() as session:
        horizons = {
            generate_case(session, scenario=SimulationScenario.SEIZURE, rng=random.Random(3000 + i)).parametros[
                "horizonte_elegido"
            ]
            for i in range(_N_TRIALS)
        }
    assert horizons == {"now"}


@pytest.mark.parametrize(
    "scenario_value",
    ["healthy", "arrhythmia", "sepsis", "hypertension", "fatigue", "apnea", "copd"],
)
def test_unrestricted_scenarios_are_not_limited_to_a_subset(tmp_path, scenario_value):
    """Los 7 escenarios que la Fase 0 midió limpios en los 6 horizontes no
    deben tener ninguna entrada en el mapa de restricción -- confirma que
    `generate_case()` sigue pudiendo elegir cualquiera de los 6 para ellos
    (no una prueba de que salgan los 6 en 40 tiros -- con 6 horizontes
    equiprobables eso es posible que falte alguno por azar -- sino de que
    el mapa no los restringe estructuralmente)."""
    assert scenario_value not in EVALUABLE_HORIZONS_BY_SCENARIO


def test_the_three_hemodynamic_enabled_scenarios_are_all_unrestricted():
    """Paso 3 del Trabajo 2: sano/hipertensión/sepsis (los únicos 3 con PA
    calculada del motor hemodinámico) no deben tener ninguna restricción de
    horizonte -- si algún día alguien restringe uno de estos tres por error,
    este test lo detecta antes de que afecte la conexión de PA calculada."""
    assert HEMODYNAMIC_MODEL_ENABLED_SCENARIOS == frozenset({"healthy", "hypertension", "sepsis"})
    for scenario_value in HEMODYNAMIC_MODEL_ENABLED_SCENARIOS:
        assert scenario_value not in EVALUABLE_HORIZONS_BY_SCENARIO


def test_every_scenario_has_at_least_one_evaluable_horizon():
    """Ningún escenario de los 12 puede quedar sin ningún horizonte
    evaluable -- generate_case() lanzaría ValueError en ese caso (defensivo,
    no debería ocurrir), pero el mapa mismo no debe permitirlo."""
    from app.engines.simulation_engine import SimulationScenario as AllScenarios

    for scenario in AllScenarios:
        allowed = EVALUABLE_HORIZONS_BY_SCENARIO.get(scenario.value, _ALL_HORIZONS)
        assert len(allowed) >= 1, scenario.value
