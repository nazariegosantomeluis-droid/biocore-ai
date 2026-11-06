"""
Persona sana en reposo -- FUENTE ÚNICA de "sano" (Unificación 4, 2026-11-05).

Reemplaza a las definiciones paralelas de "sano" que no coincidían entre sí:
`SimulationEngine._simulate_healthy` (7 gaussianas del estado global de numpy, SIN semilla: FC 72 +- 3, HRV 50 +- 5, FR 16 +- 1...,
el mismo "sano" daba un paciente distinto en cada clic y en cada horizonte, con fatiga de -9.8 e índice cognitivo
de 102.6 entre sus valores posibles), `SimulationEngine.BASELINE_PARAMETERS`, el preset "healthy" del organismo
(HRV 60 donde el motor decía 50) y el jitter del banco de casos (`case_bank._BASELINE_JITTER`). Módulo puro (sin
imports del proyecto salvo la constante del ritmo sinusal), como `arrhythmia_types.py` y `sepsis_trajectory.py`.

VARIABILIDAD DECLARADA (opción B de la unificación 1): una instancia es la semilla, y cada valor es función pura
de ella dentro del rango declarado de su variable. Una persona sana en reposo es UNA persona: los valores no
cambian entre horizontes (antes saltaban de un horizonte a otro). La UI muestra rangos, semilla y valores.

SEMILLA 0 = PERSONA DE REFERENCIA: los valores nominales (FC 72, HRV 50, FR 16, SpO2 98...). Es la semilla por
defecto de `SimulationEngine`, así que el "sano" que nadie configuró es siempre el mismo y los puntos fijos de
validación de la plataforma (p. ej. el lazo hemodinámico a FC 72) siguen siendo su baseline. Otra semilla = otra
persona sana dentro de los mismos rangos.

RELACIÓN CON EL "NORMAL" DE ECG-12 (unificación 3): no son el mismo concepto. "Normal" es el corte clínico del
ritmo sinusal (60-100 lpm, `SINUS_NORMAL_RANGE_BPM`); "sano" es el subrango de una persona sana en reposo. Comparten
el límite: la FC de "sano" va CONTENIDA en el rango normal (un test lo verifica). El subrango es 60-85 y no 60-100
porque con 98-100 lpm "sano" se confundiría con estrés (82.5), hipertensión (85) y, en el lazo hemodinámico, el
límite de ciclo documentado para FC >= 98.

ESTADO DE VALIDACIÓN: PENDING_VALIDATION, ningún rango tiene cita. Origen de cada uno:
  - FC, HRV, FR, SpO2, estrés: los rangos que ya usaba el banco de casos ("fisiológicamente normal de reposo");
    los nominales, los de `BASELINE_PARAMETERS` y los medios del antiguo `_simulate_healthy`.
  - cognición y fatiga: nominal +- 5, el sigma del antiguo gaussiano, ahora ACOTADO (no hay valores imposibles).
Quitar o cambiar un rango es editar `HEALTHY_VARIABLES`: todos los consumidores derivan de aquí.
"""

from __future__ import annotations

from typing import Dict, Tuple

import numpy as np

from src.signals.ecg.arrhythmia_types import SINUS_NORMAL_RANGE_BPM

VALIDATION_STATUS = "PENDING_VALIDATION"
REFERENCE_SEED = 0

# nombre del campo de `SimulationTimestep` -> (nominal, mínimo, máximo)
HEALTHY_VARIABLES: Dict[str, Tuple[float, float, float]] = {
    "hr": (72.0, 60.0, 85.0),
    "hrv": (50.0, 35.0, 65.0),
    "respiratory_rate": (16.0, 12.0, 18.0),
    "spo2": (98.0, 96.0, 99.0),
    "stress_level": (20.0, 10.0, 35.0),
    "cognitive_state": (85.0, 80.0, 90.0),
    "fatigue_index": (10.0, 5.0, 15.0),
}

_LABELS = {
    "hr": ("FC", "lpm"), "hrv": ("HRV", ""), "respiratory_rate": ("FR", "rpm"), "spo2": ("SpO2", "%"),
    "stress_level": ("estrés", ""), "cognitive_state": ("cognición", ""), "fatigue_index": ("fatiga", ""),
}

assert SINUS_NORMAL_RANGE_BPM[0] <= HEALTHY_VARIABLES["hr"][1] and HEALTHY_VARIABLES["hr"][2] <= SINUS_NORMAL_RANGE_BPM[1]


def instance(seed: int = REFERENCE_SEED) -> Dict[str, float]:
    """La persona sana de esta semilla. Función pura: mismos argumentos, mismos valores; el estado global
    de numpy no la afecta. Semilla 0: valores nominales."""
    if seed == REFERENCE_SEED:
        return {name: nominal for name, (nominal, _, _) in HEALTHY_VARIABLES.items()}
    return {
        name: float(np.random.default_rng([int(seed), i]).uniform(lo, hi))
        for i, (name, (_, lo, hi)) in enumerate(HEALTHY_VARIABLES.items())
    }


def declare_instance(seed: int = REFERENCE_SEED) -> str:
    """Texto que la UI muestra: rangos declarados, semilla y los valores de esta instancia."""
    def fmt(v: float) -> str:
        return f"{v:.0f}" if float(v).is_integer() else f"{v:.1f}"

    rangos, valores = [], []
    for name, (_, lo, hi) in HEALTHY_VARIABLES.items():
        etiqueta, unidad = _LABELS[name]
        sufijo = f" {unidad}" if unidad else ""
        rangos.append(f"{etiqueta} {fmt(lo)}-{fmt(hi)}{sufijo}")
        valores.append(f"{etiqueta} {fmt(instance(seed)[name])}")
    quien = "persona de referencia (valores nominales)" if seed == REFERENCE_SEED else "otra persona sana"
    return (
        f"Rangos declarados de Sano (en reposo): {', '.join(rangos)}; la FC va contenida en el ritmo sinusal "
        f"normal ({SINUS_NORMAL_RANGE_BPM[0]:.0f}-{SINUS_NORMAL_RANGE_BPM[1]:.0f} lpm). Esta instancia "
        f"(semilla {seed}, {quien}): {', '.join(valores)}. Es una sola persona: no cambia entre horizontes. "
        f"Otra semilla da otra persona dentro de los mismos rangos. [{VALIDATION_STATUS}]"
    )
