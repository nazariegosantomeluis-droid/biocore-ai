"""
Fase 1.2 — Definiciones de escenarios clínicos.

Cada escenario es una lista de waypoints: (progreso 0.0-1.0, señales de
entrada a `DigitalTwinOrganism.update_from_sensors`). Entre waypoints se
interpola linealmente — trayectoria determinista, no valores aleatorios.
El organismo sigue calculando sus propias métricas derivadas
(health_score, risk_score, detail.*) con la lógica ya existente en
`_update_heart`/`_update_lungs`; este módulo solo decide qué señales de
entrada recibe en cada paso, sin duplicar ningún umbral clínico.

Alcance de este slice (Fase 1.2, registro en CHANGELOG.md): 2 escenarios cardiovascular/
respiratorio, no una biblioteca completa — evitar sobre-ingeniería.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

Waypoint = Tuple[float, Dict[str, Dict[str, float]]]

SCENARIOS: Dict[str, List[Waypoint]] = {
    # Unificación 1: antes "fibrilacion_estres". Solo trazaba una FC 75->145 con HRV cayendo, sin nada de
    # fibrilación auricular (irregularidad, rango propio): una taquicardia de estrés con nombre de
    # diagnóstico. Ningún menú la usa (solo tests); la fibrilación auricular vive en
    # `src/signals/ecg/arrhythmia_types.py`.
    "taquicardia_estres": [
        (0.0, {"ecg": {"heart_rate": 75, "hrv": 55, "complexity": 60}, "eeg": {"stress_level": 25}}),
        (0.3, {"ecg": {"heart_rate": 95, "hrv": 35, "complexity": 45}, "eeg": {"stress_level": 45}}),
        (0.6, {"ecg": {"heart_rate": 120, "hrv": 20, "complexity": 25}, "eeg": {"stress_level": 65}}),
        (1.0, {"ecg": {"heart_rate": 145, "hrv": 10, "complexity": 12}, "eeg": {"stress_level": 80}}),
    ],
    "hipoxia_progresiva": [
        (0.0, {"respiratory": {"respiratory_rate": 15, "spo2": 97, "ahi": 0}}),
        (0.3, {"respiratory": {"respiratory_rate": 19, "spo2": 93, "ahi": 2}}),
        (0.6, {"respiratory": {"respiratory_rate": 24, "spo2": 88, "ahi": 6}}),
        (1.0, {"respiratory": {"respiratory_rate": 30, "spo2": 82, "ahi": 12}}),
    ],
    # Unificación 2: "sepsis_temprana" (FC 78->125, SpO2 97->88) se retiró -- la sepsis tiene UNA trayectoria
    # canónica, en `src/clinical/sepsis_trajectory.py`. Solo la usaban tests.
}


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def interpolate(waypoints: List[Waypoint], progress: float) -> Dict[str, Dict[str, float]]:
    """Señales de entrada en un punto `progress` (0-1) de la trayectoria,
    interpolando linealmente entre los dos waypoints que lo rodean."""
    progress = max(0.0, min(1.0, progress))

    lower, upper = waypoints[0], waypoints[-1]
    for i in range(len(waypoints) - 1):
        p0, _ = waypoints[i]
        p1, _ = waypoints[i + 1]
        if p0 <= progress <= p1:
            lower, upper = waypoints[i], waypoints[i + 1]
            break

    p0, data0 = lower
    p1, data1 = upper
    span = p1 - p0
    local_t = 0.0 if span <= 0 else (progress - p0) / span

    result: Dict[str, Dict[str, float]] = {}
    for category in set(data0) | set(data1):
        d0 = data0.get(category, {})
        d1 = data1.get(category, {})
        merged: Dict[str, float] = {}
        for key in set(d0) | set(d1):
            v0, v1 = d0.get(key), d1.get(key)
            if v0 is None:
                merged[key] = v1
            elif v1 is None:
                merged[key] = v0
            else:
                merged[key] = _lerp(v0, v1, local_t)
        result[category] = merged
    return result
