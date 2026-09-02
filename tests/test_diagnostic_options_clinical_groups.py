"""
Learning Hub — Trabajo 1 (2026-08-06): distractores curados por similitud
clínica en `_diagnostic_options()` (`app/supermodules/twin_shell/pages.py`,
compartida por Academia y Twin OS).

Cubre la agrupación clínica (`CLINICAL_GROUPS`, con la arritmia en dos
grupos -- decisión explícita del validador) y la garantía de que cada caso
tiene al menos un distractor clínicamente cercano, no puramente al azar.
"""

import random

import pytest

from app.engines.simulation_engine import SimulationScenario
from app.supermodules.twin_shell.pages import (
    CLINICAL_GROUPS,
    RICH_SCENARIO_LABELS,
    _clinical_neighbors,
    _diagnostic_options,
)

_N_TRIALS = 60


def test_clinical_groups_cover_all_twelve_scenarios():
    covered = set()
    for group in CLINICAL_GROUPS.values():
        covered |= group
    assert covered == set(SimulationScenario)


def test_arrhythmia_belongs_to_both_group_a_and_group_c():
    """Decisión explícita del validador -- no un accidente de partición."""
    assert SimulationScenario.ARRHYTHMIA in CLINICAL_GROUPS["A_activacion_simpatica_aguda"]
    assert SimulationScenario.ARRHYTHMIA in CLINICAL_GROUPS["C_hipotension_bajo_gasto_shock"]
    membership_count = sum(
        1 for group in CLINICAL_GROUPS.values() if SimulationScenario.ARRHYTHMIA in group
    )
    assert membership_count == 2  # ningún otro escenario debería estar en más de un grupo
    for scenario in SimulationScenario:
        if scenario is SimulationScenario.ARRHYTHMIA:
            continue
        count = sum(1 for group in CLINICAL_GROUPS.values() if scenario in group)
        assert count == 1, f"{scenario.value} está en {count} grupos, se esperaba exactamente 1"


@pytest.mark.parametrize(
    "scenario,expected_neighbors",
    [
        (SimulationScenario.SEPSIS, {SimulationScenario.ARRHYTHMIA}),
        (
            SimulationScenario.ANXIETY,
            {SimulationScenario.STRESS, SimulationScenario.EXERCISE, SimulationScenario.SEIZURE, SimulationScenario.ARRHYTHMIA},
        ),
        (SimulationScenario.HEALTHY, {SimulationScenario.FATIGUE, SimulationScenario.HYPERTENSION}),
        (SimulationScenario.HYPOXIA, {SimulationScenario.APNEA, SimulationScenario.COPD}),
        (
            SimulationScenario.ARRHYTHMIA,
            {
                SimulationScenario.STRESS, SimulationScenario.ANXIETY, SimulationScenario.EXERCISE,
                SimulationScenario.SEIZURE, SimulationScenario.SEPSIS,
            },
        ),
    ],
)
def test_clinical_neighbors_match_the_validated_grouping(scenario, expected_neighbors):
    assert _clinical_neighbors(scenario) == frozenset(expected_neighbors)
    assert scenario not in _clinical_neighbors(scenario)  # nunca vecino de sí mismo


def test_sepsis_always_includes_arrhythmia_the_only_close_distractor():
    """Grupo C solo tiene 2 miembros -- sepsis SIEMPRE debe traer arritmia,
    en cada tirada, no solo "a veces"."""
    for i in range(_N_TRIALS):
        random.seed(4000 + i)
        options = _diagnostic_options(SimulationScenario.SEPSIS)
        assert SimulationScenario.ARRHYTHMIA in options


def test_healthy_always_includes_both_fatigue_and_hypertension():
    """Grupo D minus sano tiene exactamente 2 miembros y se piden 3
    distractores -- ambos entran siempre, no una fracción del tiempo."""
    for i in range(_N_TRIALS):
        random.seed(4100 + i)
        options = _diagnostic_options(SimulationScenario.HEALTHY)
        assert SimulationScenario.FATIGUE in options
        assert SimulationScenario.HYPERTENSION in options


def test_anxiety_distractors_are_always_from_group_a_never_a_far_scenario():
    """Grupo A minus ansiedad tiene 4 miembros, se piden 3 distractores --
    con cupo de sobra, los 3 deben salir de ahí, cero lejanos."""
    group_a_neighbors = _clinical_neighbors(SimulationScenario.ANXIETY)
    for i in range(_N_TRIALS):
        random.seed(4200 + i)
        options = _diagnostic_options(SimulationScenario.ANXIETY)
        distractors = [o for o in options if o != SimulationScenario.ANXIETY]
        assert all(d in group_a_neighbors for d in distractors), distractors


@pytest.mark.parametrize("scenario", list(SimulationScenario))
def test_every_scenario_gets_at_least_one_close_distractor_across_many_trials(scenario):
    """La garantía central del Trabajo 1: ningún caso queda con puros
    distractores lejanos -- verificado para los 12 escenarios, no solo los
    de ejemplo, en muchas tiradas cada uno."""
    neighbors = _clinical_neighbors(scenario)
    assert neighbors, f"{scenario.value} no tiene ningún vecino clínico -- revisar CLINICAL_GROUPS"

    for i in range(_N_TRIALS):
        random.seed(4300 + i)
        options = _diagnostic_options(scenario)
        distractors = [o for o in options if o != scenario]
        assert any(d in neighbors for d in distractors), (
            f"{scenario.value}: ninguno de los distractores {distractors} es un vecino clínico"
        )


@pytest.mark.parametrize("scenario", list(SimulationScenario))
def test_options_are_well_formed(scenario):
    """Invariantes estructurales que no deben romperse por curar
    distractores: la opción correcta aparece exactamente una vez, sin
    duplicados, tamaño correcto."""
    for i in range(20):
        random.seed(4400 + i)
        options = _diagnostic_options(scenario, n_options=4)
        assert len(options) == 4
        assert len(set(options)) == 4  # sin duplicados
        assert options.count(scenario) == 1
        assert all(o in RICH_SCENARIO_LABELS for o in options)


def test_diagnostic_options_is_the_same_shared_function_used_by_both_case_modes():
    """`_diagnostic_options` (con la curación nueva) sigue siendo la MISMA
    función que Academia importa -- no una copia que pueda desincronizarse,
    igual que ya se probó para `_attach_calculated_pa_to_case`/
    `_build_pa_findings` en la tanda anterior."""
    import app.supermodules.academia.pages as academia_pages
    import app.supermodules.twin_shell.pages as twin_shell_pages

    assert academia_pages._diagnostic_options is twin_shell_pages._diagnostic_options
