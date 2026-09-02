"""
Bloque 4 — Congelamiento a 7d (2026-08-12): etiqueta honesta de la meseta en
la línea de tiempo del simulador de escenarios de Twin OS
(`app/supermodules/twin_shell/pages.py::render_ups_scenario_simulator`).

Cubre `_tail_is_plateaued()`, la función pura que decide si se muestra el
aviso "esta trayectoria se aplanó" -- genérica (no una lista de escenarios
hardcodeada): dispara solo cuando la cola de la serie está fija Y la serie
se movió en algún punto anterior, para distinguir un aplanado real
(stress/hypoxia/sepsis, que arrancan de un valor y luego saturan) de una
foto constante por diseño (apnea/EPOC/hipertensión, los 6 horizontes iguales
desde `now` -- no es el mismo problema, ver CHANGELOG.md).

No cambia ningún valor del simulador -- solo prueba la detección y su
conexión con la salida real de `SimulationEngine`.
"""

import pytest

from app.engines.simulation_engine import SimulationEngine, SimulationScenario
from app.supermodules.twin_shell.pages import _tail_is_plateaued


def test_flat_tail_after_real_movement_is_a_plateau():
    assert _tail_is_plateaued([75.0, 76.25, 82.5, 105.0, 105.0, 105.0]) is True


def test_constant_series_from_the_start_is_not_a_plateau():
    """Apnea/EPOC/hipertensión: los 6 horizontes son el mismo valor desde
    `now` -- constante por diseño, no un aplanado (CHANGELOG.md 2026-08-12)."""
    assert _tail_is_plateaued([55.0, 55.0, 55.0, 55.0, 55.0, 55.0]) is False


def test_series_still_moving_at_the_tail_is_not_a_plateau():
    assert _tail_is_plateaued([100.0, 105.0, 110.0, 116.7, 130.0, 150.0]) is False


def test_short_series_below_tail_len_is_not_a_plateau():
    assert _tail_is_plateaued([72.0]) is False


def test_none_values_in_the_tail_are_not_a_plateau():
    assert _tail_is_plateaued([75.0, 80.0, 90.0, 105.0, None, 105.0]) is False


@pytest.mark.parametrize("scenario", [SimulationScenario.STRESS, SimulationScenario.HYPOXIA])
def test_stress_and_hypoxia_hr_plateau_from_2h_in_the_real_engine(scenario):
    """Confirmado por ejecución (no asumido): `min(1.0, minutes/120)` capa en
    2h -- 2h/24h/7d dan el mismo HR, calculado a partir de un `now` distinto."""
    timeline = SimulationEngine().simulate_scenario(scenario)
    hr_values = [step.hr for step in timeline]
    assert _tail_is_plateaued(hr_values) is True
    assert hr_values[3] == hr_values[4] == hr_values[5]  # 2h == 24h == 7d
    assert hr_values[0] != hr_values[-1]  # now sí es distinto -- hubo movimiento real


def test_sepsis_hr_plateaus_only_at_24h_7d_not_at_2h():
    """`min(1.0, minutes/360)` capa a las 6h -- de los horizontes muestreados,
    2h (120min) aún no llegó al techo; 24h y 7d sí, y coinciden entre sí."""
    timeline = SimulationEngine().simulate_scenario(SimulationScenario.SEPSIS)
    hr_values = [step.hr for step in timeline]
    assert hr_values[4] == hr_values[5]  # 24h == 7d
    assert hr_values[3] != hr_values[4]  # 2h todavía progresando
    assert _tail_is_plateaued(hr_values) is True


def test_apnea_and_copd_are_constant_not_flagged_as_a_plateau():
    """Ambos son una foto determinista sostenida en los 6 horizontes desde
    `now` -- ver CHANGELOG.md 2026-08-12, "constantes por diseño, no el
    mismo problema"."""
    for scenario in (SimulationScenario.APNEA, SimulationScenario.COPD):
        timeline = SimulationEngine().simulate_scenario(scenario)
        hr_values = [step.hr for step in timeline]
        spo2_values = [step.spo2 for step in timeline]
        assert _tail_is_plateaued(hr_values) is False
        assert _tail_is_plateaued(spo2_values) is False
