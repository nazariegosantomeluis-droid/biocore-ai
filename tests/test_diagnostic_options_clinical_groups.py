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


S = SimulationScenario
_TACHY = {S.ARRHYTHMIA_AFIB, S.ARRHYTHMIA_AFLUTTER, S.ARRHYTHMIA_SVT}
_ARRHYTHMIAS = _TACHY | {S.ARRHYTHMIA_SBRADY}


def test_clinical_groups_cover_all_scenarios():
    covered = set()
    for group in CLINICAL_GROUPS.values():
        covered |= group
    assert covered == set(SimulationScenario)


def test_tachyarrhythmias_inherit_both_group_a_and_group_c_and_bradycardia_only_c():
    """Unificación 1: el "arrhythmia" genérico (A y C, decisión explícita del validador) se retiró; los tres
    tipos taquiarrítmicos heredan esa doble pertenencia y la bradicardia sinusal solo entra en C. Pendiente de
    firma del validador."""
    for scenario in _TACHY:
        assert scenario in CLINICAL_GROUPS["A_activacion_simpatica_aguda"]
        assert scenario in CLINICAL_GROUPS["C_hipotension_bajo_gasto_shock"]
    assert S.ARRHYTHMIA_SBRADY in CLINICAL_GROUPS["C_hipotension_bajo_gasto_shock"]
    assert S.ARRHYTHMIA_SBRADY not in CLINICAL_GROUPS["A_activacion_simpatica_aguda"]
    for scenario in SimulationScenario:
        if scenario in _TACHY:
            continue
        count = sum(1 for group in CLINICAL_GROUPS.values() if scenario in group)
        assert count == 1, f"{scenario.value} está en {count} grupos, se esperaba exactamente 1"


@pytest.mark.parametrize(
    "scenario,expected_neighbors",
    [
        (S.SEPSIS, _ARRHYTHMIAS),
        (S.ANXIETY, {S.STRESS, S.EXERCISE, S.SEIZURE} | _TACHY),
        (S.HEALTHY, {S.FATIGUE, S.HYPERTENSION}),
        (S.HYPOXIA, {S.APNEA, S.COPD}),
        (S.ARRHYTHMIA_AFIB, {S.STRESS, S.ANXIETY, S.EXERCISE, S.SEIZURE, S.SEPSIS, S.ARRHYTHMIA_AFLUTTER, S.ARRHYTHMIA_SVT, S.ARRHYTHMIA_SBRADY}),
        (S.ARRHYTHMIA_SBRADY, {S.SEPSIS} | _TACHY),
    ],
)
def test_clinical_neighbors_match_the_grouping(scenario, expected_neighbors):
    assert _clinical_neighbors(scenario) == frozenset(expected_neighbors)
    assert scenario not in _clinical_neighbors(scenario)  # nunca vecino de sí mismo


def test_sepsis_distractors_are_always_arrhythmia_types():
    """Grupo C = sepsis + los 4 tipos de arritmia: los 3 distractores de sepsis salen siempre de ahí."""
    for i in range(_N_TRIALS):
        random.seed(4000 + i)
        options = _diagnostic_options(SimulationScenario.SEPSIS)
        assert {o for o in options if o != SimulationScenario.SEPSIS} <= _ARRHYTHMIAS


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
    distractores lejanos -- verificado para todos los escenarios, no solo los
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
