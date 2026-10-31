"""
Trayectoria canónica de sepsis -- FUENTE ÚNICA (Unificación 2, 2026-10-31).

Reemplaza a las fuentes que simulaban "sepsis" con números propios: el preset
de Twin OS (FC 110, FR 28, SpO2 92), `scenarios/definitions.py::sepsis_temprana`
(FC 78->125, SpO2 97->88) y la fórmula en línea de `SimulationEngine`. Los tres
ponen a "sepsis" en puntos distintos de una misma evolución sin decirlo; aquí la
evolución es UNA y los demás lugares muestran puntos de ella. Módulo puro (sin
imports del proyecto), como `arrhythmia_types.py`.

La sepsis evoluciona: de temprana a progresión y a shock. Dos extremos con
interpolación lineal en el tiempo, saturada a los 360 min (`SHOCK_ONSET_MIN`):

    variable   inicio (0 min)   shock (>= 360 min)
    FC         100 lpm          150 lpm
    HRV         30               5
    FR          22 rpm           32 rpm
    SpO2        95 %             85 %
    estrés      70               100

CITAS: FC > 90 (criterio SIRS, Bone 1992) y FR >= 22 (qSOFA, Sepsis-3, Singer
2016) respaldan el inicio (FC 100 y FR 22 cumplen ambos criterios). Las
magnitudes del extremo de shock (FC 150, FR 32, SpO2 85, HRV 5) NO tienen cita:
PENDING_VALIDATION, como todo lo demás de la tabla hasta la firma del experto.
Los puntos medios son interpolación, no datos.

FASES por horizonte del `SimulationEngine` (etiquetas PENDING_VALIDATION):
temprana (now, 5min, 30min), progresión (2h) y shock (24h, 7d). La fase importa
para la presión: el motor hemodinámico modela la vasoplejía del shock séptico
establecido (techo de vasoconstricción 0.5x, ganancia 0.3x, retorno venoso
reducido) y NO tiene un mecanismo de sepsis temprana, donde la PA puede ser
normal. Medido (2026-10-31), el motor da PAM 61 con FC 60, 47 con FC 100, 36 con
FC 125 y 24 con FC 150: cae por debajo de 65 con cualquier FC porque la presión
la fija el mecanismo, no la FC. Por eso la PA calculada solo representa a las
fases de shock, y la referencia citada (Sepsis-3: 85/55, PAM 65) es el UMBRAL
del shock, no la sepsis temprana. Ver `pa_phase_note()`.

SIN VARIABILIDAD entre instancias: la trayectoria es única y determinista (no
usa semilla). Si se firma variabilidad, debe ser función pura de (semilla,
horizonte), como en `arrhythmia_types.py`, y declararse.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

VALIDATION_STATUS = "PENDING_VALIDATION"

SHOCK_ONSET_MIN: float = 360.0

# (valor al inicio, valor en shock)
_ENDPOINTS: Dict[str, Tuple[float, float]] = {
    "hr": (100.0, 150.0),
    "hrv": (30.0, 5.0),
    "respiratory_rate": (22.0, 32.0),
    "spo2": (95.0, 85.0),
    "stress_level": (70.0, 100.0),
}

CITATIONS: Dict[str, str] = {
    "hr": "inicio FC > 90: criterio SIRS (Bone 1992); FC 150 en shock sin cita",
    "respiratory_rate": "inicio FR >= 22: qSOFA, Sepsis-3 (Singer 2016); FR 32 en shock sin cita",
    "spo2": "sin cita",
    "hrv": "sin cita",
    "stress_level": "sin cita",
}

# Horizontes del SimulationEngine -> (minutos, fase).
HORIZON_PHASES: Dict[str, Tuple[int, str]] = {
    "now": (0, "temprana"),
    "5min": (5, "temprana"),
    "30min": (30, "temprana"),
    "2h": (120, "progresion"),
    "24h": (1440, "shock"),
    "7d": (10080, "shock"),
}

# Fases en las que el motor hemodinámico describe al paciente (ver docstring).
PA_MODEL_PHASES = frozenset({"shock"})


def progression(minutes: float) -> float:
    """0 en el inicio, 1 desde `SHOCK_ONSET_MIN` en adelante."""
    return max(0.0, min(1.0, minutes / SHOCK_ONSET_MIN))


def vitals(minutes: float) -> Dict[str, float]:
    """Signos de la trayectoria en `minutes`: `hr`, `hrv`, `respiratory_rate`, `spo2`, `stress_level`."""
    p = progression(minutes)
    return {name: start + p * (end - start) for name, (start, end) in _ENDPOINTS.items()}


def horizon_vitals(horizon: str) -> Dict[str, float]:
    return vitals(HORIZON_PHASES[horizon][0])


def phase_of(horizon: str) -> str:
    return HORIZON_PHASES[horizon][1]


def horizon_from_source_detail(source_detail: Optional[str]) -> Optional[str]:
    """Horizonte de un descriptor generado por `run_rich_scenario` (su `source_detail` termina en
    ``:horizonte:<etiqueta>``), o `None` si no es de un escenario rico."""
    if not source_detail or ":horizonte:" not in source_detail:
        return None
    label = source_detail.rsplit(":horizonte:", 1)[1]
    return label if label in HORIZON_PHASES else None


def pa_phase_note(phase: str) -> str:
    """Qué representa la PA calculada por el motor en esta fase (para la UI y el narrador)."""
    if phase in PA_MODEL_PHASES:
        return (
            "fase de shock séptico: el modelo hemodinámico (vasoplejía, retorno venoso reducido) describe a "
            "este paciente; la referencia citada (Sepsis-3, PAM 65) es el UMBRAL de shock y el cálculo cae por "
            "debajo de él."
        )
    return (
        f"fase {phase.replace('progresion', 'de progresión')} de la sepsis: el modelo hemodinámico solo modela la "
        "vasoplejía del shock establecido y no tiene un mecanismo de sepsis temprana, donde la PA real puede ser "
        "normal -- esta PA calculada NO representa a este paciente; es lo que el modelo daría si ya estuviera en shock."
    )


def declare_trajectory() -> str:
    """Texto (markdown) que la UI muestra: la trayectoria completa, sus fases y su estado de validación."""
    filas = ["| Horizonte | Fase | FC (lpm) | FR (rpm) | SpO₂ (%) |", "|---|---|---|---|---|"]
    for label, (minutes, phase) in HORIZON_PHASES.items():
        v = vitals(minutes)
        filas.append(
            f"| {label} | {phase} | {v['hr']:.0f} | {v['respiratory_rate']:.0f} | {v['spo2']:.0f} |"
        )
    return (
        "**Trayectoria canónica de sepsis** (una sola, sin variabilidad entre instancias; "
        f"[{VALIDATION_STATUS}]: FC > 90 y FR ≥ 22 al inicio tienen cita —SIRS, qSOFA—; las magnitudes de shock no).\n\n"
        + "\n".join(filas)
        + "\n\nPresión arterial: el modelo hemodinámico solo describe la fase de **shock**; en las fases "
        "temprana y de progresión su PA no representa al paciente (la PA real puede ser normal)."
    )
