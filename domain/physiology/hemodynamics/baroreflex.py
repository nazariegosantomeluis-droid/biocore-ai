"""
Módulo 2 — Resistencia vascular dinámica (barórreflejo), 2026-07-20.

Confirmado por el validador experto: el módulo 2 es un controlador
proporcional que modela el barórreflejo arterial — el mecanismo de
retroalimentación negativa por el cual el cuerpo ajusta el tono vascular
(y la frecuencia cardíaca, no modelada aquí) para defender la presión
arterial media (PAM) frente a perturbaciones.

*** DOS COSAS DISTINTAS, MARCADAS POR SEPARADO ***

1. **El MECANISMO tiene fuente y es fisiología establecida**: barorreceptores
   en el seno carotídeo y el cayado aórtico detectan el estiramiento de la
   pared arterial (proxy de presión); su señal aferente llega al núcleo del
   tracto solitario; una PAM por debajo del punto de ajuste reduce la
   descarga barorreceptora, lo que aumenta el tono simpático y reduce el
   parasimpático → vasoconstricción arteriolar (↑resistencia periférica) y
   taquicardia; una PAM por encima del punto de ajuste hace lo inverso
   (vasodilatación, bradicardia relativa). Esta cadena de retroalimentación
   negativa es exactamente lo que `BaroreflexController` implementa como
   controlador proporcional sobre la resistencia distal (Rd) -- ver
   Guyton & Hall, Tratado de Fisiología Médica, Cap. 18 ("Regulación
   nerviosa de la circulación... reflejos barorreceptores"), misma fuente
   ya usada en `blood_pressure_references.py` (`_GUYTON`) para otros
   escenarios de esta serie.

2. **Los NÚMEROS (k, min_r, max_r, target_map) NO tienen esa fuente --
   son estimaciones del validador experto, marcadas explícitamente
   PENDING_QUANTITATIVE_VALIDATION**, igual que R/Rp/Rd/C del módulo 1
   (`physiological_flow.py`). Guyton describe el mecanismo cualitativamente
   (dirección del efecto), no da una ganancia proporcional k lista para
   usar en esta ecuación concreta -- inventar un número y llamarlo "de
   Guyton" sería exactamente el error que este proyecto prohíbe (Art. I).

*** SALVAGUARDA ANTI-CIRCULARIDAD (deliberada, ver tests) ***
`BAROREFLEX_TARGET_MAP_MMHG` es UN SOLO valor fijo -- la PAM ancla del
módulo 1 calibrado en el caso "sano" (93.33 mmHg) -- usado para TODOS los
escenarios, nunca uno distinto por escenario. El barórreflejo defiende
siempre el mismo punto de ajuste homeostático; lo que cambia entre
escenarios es únicamente `heart_rate` (la entrada dinámica real del UPS,
igual que en el módulo 1) y, por lo tanto, el caudal medio que el
controlador debe compensar. Si `target_map` variara por escenario para
acercarse a cada `ClinicalReferenceValue`, el modelo estaría afinado para
reproducir la respuesta correcta en vez de producirla por mecanismo --
precisamente lo que el validador prohibió. La `ClinicalReferenceValue` de
cada escenario es el control de calidad independiente de esta corrida, NO
un objetivo de ajuste de `k`/`min_r`/`max_r`/`target_map`.

*** QUÉ RESISTENCIA MODULA ***
Solo `Rd` (resistencia distal/arteriolar) — Rp (impedancia característica
proximal/aórtica), C y Pd quedan en su valor calibrado del módulo 1, sin
tocar. El tono arteriolar mediado por barórreflejo es fisiológicamente el
efector de resistencia periférica; la impedancia característica aórtica
depende más de la geometría/rigidez del vaso que de la inervación
simpática beat-to-beat -- decisión de modelado explícita, no una cita.
"""

from __future__ import annotations

import dataclasses
from typing import Tuple

import numpy as np

from ..state.clinical_reference import estimate_map
from .physiological_flow import PHYSIOLOGICAL_RRCR_PARAMETERS, STROKE_VOLUME_REFERENCE_ML, physiological_pulsatile_flow
from .r_rcr import RRCRParameters, simulate_r_rcr

__all__ = [
    "BAROREFLEX_GAIN_K",
    "BAROREFLEX_MIN_RD",
    "BAROREFLEX_MAX_RD",
    "BAROREFLEX_TARGET_MAP_MMHG",
    "BAROREFLEX_MAX_TICKS",
    "BAROREFLEX_CONVERGENCE_TOL",
    "BAROREFLEX_MECHANISM_CITATION",
    "BAROREFLEX_PARAMETERS_PENDING_VALIDATION",
    "BaroreflexTick",
    "BaroreflexResult",
    "run_baroreflex",
]

# --- Mecanismo: fuente citada -------------------------------------------------
BAROREFLEX_MECHANISM_CITATION = (
    "Guyton & Hall, Tratado de Fisiología Médica, Cap. 18 -- reflejos barorreceptores: "
    "PAM por debajo del punto de ajuste -> vasoconstricción arteriolar (sube resistencia "
    "periférica); PAM por encima -> vasodilatación (baja resistencia periférica). Mecanismo "
    "de retroalimentación negativa, no una cita para los valores numéricos de abajo."
)

# --- Magnitudes: dictaminadas por el validador experto -----------------------
# Ronda 1 (2026-07-30/31): BAROREFLEX_MIN_RD y BAROREFLEX_MAX_RD VALIDADOS con
# cita de Guyton. Ronda 2 (2026-07-31): BAROREFLEX_GAIN_K y BAROREFLEX_TARGET_MAP_MMHG
# también VALIDADOS -- los CUATRO parámetros de esta bandera están confirmados, así
# que la bandera BAJA a False (ver CHANGELOG.md, entrada "Validación cuantitativa —
# Ronda 2"). El guard `if not BAROREFLEX_PARAMETERS_PENDING_VALIDATION: raise
# AssertionError(...)` que vivía en `run_baroreflex()` existía para bloquear un flip
# SIN revisión -- esa revisión ya ocurrió (documentada abajo, junto a cada constante,
# y en CHANGELOG.md), así que el guard se retiró (ya no tiene nada que impedir).
BAROREFLEX_PARAMETERS_PENDING_VALIDATION = False

BAROREFLEX_GAIN_K: float = 1.0
"""Ganancia proporcional del controlador (adimensional). Estimación del
validador -- un valor "de ganancia unitaria" deliberadamente redondo, no
ajustado para reproducir ninguna PA de referencia. Nota de estabilidad
(control, no fisiología): con la RPT base calibrada en el módulo 1, la
iteración de punto fijo de este controlador converge geométricamente para
k por debajo de ~2 (más allá, oscila/diverge) -- k=1.0 deja margen amplio.

*** VALIDADO -- confirmado por el validador experto 2026-07-31 (Ronda 2) ***:
ganancia de control sensata que evita oscilación (ver nota de estabilidad
arriba, ya verificada computacionalmente en toda la serie -- ningún
escenario típico osciló con k=1.0)."""

BAROREFLEX_MIN_RD: float = PHYSIOLOGICAL_RRCR_PARAMETERS.rd * 0.3
"""Vasodilatación máxima -- el cuerpo no dilata infinitamente. Múltiplo
redondo (0.3x) de la Rd base calibrada.

*** VALIDADO -- confirmado por el validador experto 2026-07-30 (Ronda 1,
Operación B) ***: Guyton & Hall, Tratado de Fisiología Médica, Cap. 18 --
la inhibición simpática máxima (retirada completa del tono vasoconstrictor
basal) reduce la resistencia periférica a aproximadamente ⅓ del valor
basal -- 0.3x coincide con esa cifra citada, no es solo un múltiplo
redondo sin respaldo."""

BAROREFLEX_MAX_RD: float = PHYSIOLOGICAL_RRCR_PARAMETERS.rd * 3.0
"""Vasoconstricción máxima -- el cuerpo no contrae infinitamente. Múltiplo
redondo (3.0x) de la Rd base calibrada.

*** VALIDADO -- confirmado por el validador experto 2026-07-30 (Ronda 1,
Operación B) ***: Guyton & Hall, Tratado de Fisiología Médica, Cap. 18 --
la estimulación simpática máxima puede elevar la resistencia periférica
total 3-4x el valor basal -- 3.0x cae dentro de ese rango citado, no es
solo un múltiplo redondo sin respaldo."""

BAROREFLEX_TARGET_MAP_MMHG: float = estimate_map(120.0, 80.0)
"""PAM objetivo homeostática -- FIJA para todos los escenarios (ver nota
anti-circularidad en el docstring del módulo). Coincide con el ancla de
calibración del módulo 1 (93.33 mmHg) -- no es casualidad: es el mismo
punto de ajuste "sano" que ese módulo ya usó, reutilizado aquí como el
punto que el barórreflejo intenta defender.

*** VALIDADO -- confirmado por el validador experto 2026-07-31 (Ronda 2) ***:
es la traducción directa de 120/80 mmHg (ACC/AHA 2017, ya citado en
`blood_pressure_references.py`) a PAM vía `estimate_map()` -- no una
estimación aparte, sino una consecuencia aritmética de dos cifras ya
validadas."""

BAROREFLEX_MAX_TICKS: int = 40
BAROREFLEX_CONVERGENCE_TOL: float = 1e-4  # tolerancia relativa en Rd entre ticks consecutivos

_N_CYCLES = 12
_N_POINTS_PER_CYCLE = 101


@dataclasses.dataclass(frozen=True)
class BaroreflexTick:
    """Un paso del bucle de convergencia -- puramente informativo (para
    Paso 4, inspección), no se persiste en el UPS."""

    tick: int
    rd: float
    systolic_bp: float
    diastolic_bp: float
    map: float


@dataclasses.dataclass(frozen=True)
class BaroreflexResult:
    converged: bool
    ticks: Tuple[BaroreflexTick, ...]
    heart_rate_bpm: float
    target_map: float
    final_rd: float
    final_systolic_bp: float
    final_diastolic_bp: float
    final_map: float
    clamped_at_min: bool
    clamped_at_max: bool


def _evaluate(flow_fn, period_s: float, params: RRCRParameters) -> Tuple[float, float, float]:
    result = simulate_r_rcr(flow_fn, params, period_s=period_s, n_cycles=_N_CYCLES, n_points_per_cycle=_N_POINTS_PER_CYCLE)
    p_last = result.pressure_inlet[-_N_POINTS_PER_CYCLE:]
    t_last = result.time[-_N_POINTS_PER_CYCLE:]
    systolic = float(np.max(p_last))
    diastolic = float(np.min(p_last))
    map_value = float(np.trapezoid(p_last, t_last) / (t_last[-1] - t_last[0]))
    return systolic, diastolic, map_value


def run_baroreflex(
    heart_rate_bpm: float,
    base_params: RRCRParameters = PHYSIOLOGICAL_RRCR_PARAMETERS,
    k: float = BAROREFLEX_GAIN_K,
    min_rd: float = BAROREFLEX_MIN_RD,
    max_rd: float = BAROREFLEX_MAX_RD,
    target_map: float = BAROREFLEX_TARGET_MAP_MMHG,
    sv_ref_ml: float = STROKE_VOLUME_REFERENCE_ML,
    max_ticks: int = BAROREFLEX_MAX_TICKS,
    tol: float = BAROREFLEX_CONVERGENCE_TOL,
) -> BaroreflexResult:
    """Bucle de convergencia del barórreflejo -- "tick virtual" que vive
    ENTERAMENTE en variables locales de esta llamada (`rd`, `ticks`, ...).
    No hay estado de módulo ni de sesión que sobreviva entre llamadas: dos
    invocaciones concurrentes de `run_baroreflex()` no comparten nada --
    el motor sigue siendo stateless entre peticiones, mismo criterio que
    ya vale para `compute_calculated_pressure()` del módulo 1.

    En cada tick: simula el R-RCR con la Rd actual, mide PAM resultante,
    calcula el error frente a `target_map`, y aplica el controlador
    proporcional (R_nueva = R_base·(1 + k·ΔPAM/PAM_objetivo), con
    ΔPAM = PAM_objetivo − PAM_actual — signo elegido para que sea
    retroalimentación NEGATIVA: PAM por debajo del objetivo → ΔPAM>0 →
    Rd sube (vasoconstricción); PAM por encima → ΔPAM<0 → Rd baja
    (vasodilatación), tal como describe el mecanismo citado). El
    resultado se recorta a [min_rd, max_rd] en cada tick.

    Converge cuando el cambio relativo de Rd entre ticks es menor que
    `tol`. Si no converge en `max_ticks` -- se reporta `converged=False`
    con el último estado alcanzado, NO se lanza una excepción ni se oculta:
    la no-convergencia (con Rd persistentemente en un límite y PAM lejos
    del objetivo) es en sí un hallazgo fisiológico válido -- un cuadro
    donde el mecanismo no logra compensar (shock descompensado), no un
    error de este código."""
    # Guard de "no cambiar a False sin revisión" retirado -- Ronda 2 de validación
    # cuantitativa (2026-07-31): BAROREFLEX_PARAMETERS_PENDING_VALIDATION pasó a False
    # tras confirmación explícita del validador (k, target_map, min_rd, max_rd, los
    # cuatro validados -- ver sus docstrings arriba y CHANGELOG.md).

    flow_fn, period_s = physiological_pulsatile_flow(heart_rate_bpm, sv_ref_ml)

    rd = base_params.rd
    ticks: list[BaroreflexTick] = []
    converged = False

    for i in range(max_ticks):
        params = dataclasses.replace(base_params, rd=rd)
        systolic, diastolic, current_map = _evaluate(flow_fn, period_s, params)
        ticks.append(BaroreflexTick(tick=i, rd=rd, systolic_bp=systolic, diastolic_bp=diastolic, map=current_map))

        delta_map = target_map - current_map
        rd_next = rd * (1.0 + k * delta_map / target_map)
        rd_next = min(max(rd_next, min_rd), max_rd)

        if abs(rd_next - rd) <= tol * max(rd, 1e-9):
            rd = rd_next
            converged = True
            break
        rd = rd_next
    else:
        # max_ticks agotado sin converger -- una corrida más con el último Rd para reportar el estado final real
        pass

    # Corrida final con el Rd asentado (converja o no) -- el último tick de la lista
    # puede corresponder a un Rd anterior al último ajuste; esta corrida cierra con el
    # Rd efectivamente vigente.
    params_final = dataclasses.replace(base_params, rd=rd)
    systolic, diastolic, current_map = _evaluate(flow_fn, period_s, params_final)
    ticks.append(BaroreflexTick(tick=len(ticks), rd=rd, systolic_bp=systolic, diastolic_bp=diastolic, map=current_map))

    last = ticks[-1]
    return BaroreflexResult(
        converged=converged,
        ticks=tuple(ticks),
        heart_rate_bpm=heart_rate_bpm,
        target_map=target_map,
        final_rd=last.rd,
        final_systolic_bp=last.systolic_bp,
        final_diastolic_bp=last.diastolic_bp,
        final_map=last.map,
        clamped_at_min=last.rd <= min_rd * (1.0 + 1e-9),
        clamped_at_max=last.rd >= max_rd * (1.0 - 1e-9),
    )
