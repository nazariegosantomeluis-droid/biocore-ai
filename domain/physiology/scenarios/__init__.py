"""
Fase 1.2 — Simulador de escenarios clínicos que alimenta el UPS.

Ver `engine.py` para el generador de trayectorias y `definitions.py` para
los escenarios disponibles (todos etiquetados como simulación).
"""

from .definitions import SCENARIOS
from .engine import ScenarioStep, available_scenarios, run_scenario

__all__ = [
    "SCENARIOS",
    "ScenarioStep",
    "available_scenarios",
    "run_scenario",
]
