"""
Calibración fisiológica del módulo R-RCR — Paso 2, conexión al UPS.

Separado deliberadamente de `r_rcr.py`: los parámetros de `r_rcr.py`
(`RRCRParameters()`, por defecto) son los del caso de prueba OFICIAL de
svZeroDSolver, verificados matemáticamente contra una corrida real del
solver de referencia (ver `tests/test_hemodynamics_r_rcr.py`) — pero no
representan ninguna escala fisiológica real (con el flujo de ese caso de
prueba, Q≈5; con un flujo fisiológico real, Q≈80-90 mL/s, esos mismos
parámetros producirían presiones sin sentido, no mmHg).

Este módulo define un SEGUNDO conjunto de parámetros, calibrado a órdenes
de magnitud fisiológicos reales (mmHg, mL, s), para que la presión
calculada sea comparable con datos clínicos en mmHg
(`ClinicalReferenceValue` / `blood_pressure_references.py`).

*** ESTE SEGUNDO CONJUNTO NO ESTÁ VALIDADO FISIOLÓGICAMENTE EN CONTEXTO —
PENDIENTE DE CONFIRMACIÓN POR EL VALIDADOR EXPERTO ***
Mismo criterio que ya declara `r_rcr.py`: "cambiar los parámetros para
explorar otro régimen fisiológico es decisión del validador, no de este
código" — aquí es Claude Code quien PROPONE la calibración inicial,
explícitamente marcada como propuesta a confirmar, no como hecho
verificado (la verificación matemática de `r_rcr.py` NO cubre este
conjunto de parámetros, solo el conjunto original del caso de prueba).

Fuente de orden de magnitud — Guyton & Hall, Tratado de Fisiología Médica:
- Resistencia periférica total (RPT) normal ≈ 1 PRU (unidad de resistencia
  periférica = 1 mmHg·s/mL) en el adulto en reposo.
- Compliancia arterial sistémica total: orden de magnitud típico citado en
  fisiología cardiovascular, ~1-2 mL/mmHg.
- Volumen sistólico normal de reposo ≈ 70 mL.

Ninguno de estos tres es una cita verbatim con número de página (a
diferencia de `blood_pressure_references.py`, que sí lo es) — son órdenes
de magnitud de fisiología general. La división específica entre
resistencia proximal (Rp) y distal (Rd) es además una CONVENCIÓN de
modelado de Windkessel de 3 elementos (impedancia característica proximal
≈5-10% de la resistencia total — ver literatura de modelos Windkessel,
p.ej. Westerhof et al.), no una cifra de Guyton.

Volumen sistólico de referencia (SV_ref = 70 mL): deliberadamente
INDEPENDIENTE de `CardiacDetail.stroke_volume` del organismo
(`app/engines/digital_twin_organism.py`) — ese campo es un default
estático que `_update_heart()` nunca actualiza (confirmado leyendo el
código antes de esta tanda); usarlo habría heredado un valor fingido como
si fuera derivado del organismo. SV_ref coincide numéricamente con ese
default por ser el mismo valor de libro de texto, no porque se haya leído
de ahí.

--- Paso 1, recalibración (2026-07-20) ---
El validador señaló que sano/hipertensión quedaban ~15-20 mmHg bajos con
la primera calibración (Rd=0.90, Rp=0.10, C=2.0). Se recalibró la base
estática (Rd, Rp, C) para que el caso ancla "sano" (72 bpm, SV_ref 70 mL,
CO_medio=84 mL/s) produzca ~120/80 mmHg. Dos cantidades, dos criterios
distintos:

1. **PAM** — en régimen periódico convergido, la media de dP_c/dt es 0,
   así que PAM = RPT_total·CO_medio + Pd EXACTAMENTE (no depende de C ni
   de la forma del pulso — ver `r_rcr.py`). Se despejó RPT_total para
   PAM_objetivo = 93.33 mmHg (`estimate_map(120, 80)`, misma fórmula ya
   citada en `blood_pressure_references.py`):
   RPT_total = (93.33−2)/84 ≈ 1.0873 mmHg·s/mL — se mantuvo la división
   90/10 Rd/Rp (convención Windkessel ya documentada, sin cambios).
2. **Presión de pulso** (sistólica−diastólica) — SÍ depende de C. Se buscó
   por bisección numérica el C que produce ~40 mmHg de presión de pulso
   (valor normal de libro de texto para 120/80) con la RPT ya fijada en
   el paso anterior: C≈0.807 mL/mmHg (antes: 2.0 mL/mmHg — una revisión
   sustancial, documentada aquí sin disimulo).

Resultado verificado numéricamente: sistólica/diastólica/PAM calculadas
= 113.3/73.3/93.3 mmHg. La PAM y la presión de pulso quedan exactas (93.33
y 40.0, las dos cantidades con criterio citable/derivable); sistólica y
diastólica individuales no caen en 120/80 exactos porque la curva real
(integrada, no aproximada) no es perfectamente simétrica alrededor de la
media -- la regla PAM≈diastólica+⅓(sistólica−diastólica) es una
aproximación, no una identidad. Sigue siendo "~120/80" en el sentido que
pidió el validador. **Esto NO baja la bandera de sano/hipertensión** --
la calibración en sí sigue pendiente de que el validador la revise en
contexto (Paso final de esta tanda).
"""

from __future__ import annotations

from typing import Callable, Tuple

import numpy as np

from ..state.clinical_reference import estimate_map
from .r_rcr import RRCRParameters

__all__ = [
    "STROKE_VOLUME_REFERENCE_ML",
    "STROKE_VOLUME_CITATION",
    "PHYSIOLOGICAL_RRCR_PARAMETERS",
    "PHYSIOLOGICAL_PARAMETERS_CITATION",
    "PHYSIOLOGICAL_PARAMETERS_PENDING_VALIDATION",
    "physiological_pulsatile_flow",
]

STROKE_VOLUME_REFERENCE_ML: float = 70.0
STROKE_VOLUME_CITATION = (
    "Guyton & Hall, Tratado de Fisiología Médica -- volumen sistólico normal de reposo "
    "(~70 mL). Constante citada, NO leída de CardiacDetail.stroke_volume (ese campo del "
    "organismo es un default estático nunca actualizado por la simulación)."
)

# Caso ancla de calibración (Paso 1, 2026-07-20): "sano" en reposo.
_CALIBRATION_HEART_RATE_BPM = 72.0
_CALIBRATION_CO_MEAN_ML_S = (_CALIBRATION_HEART_RATE_BPM / 60.0) * STROKE_VOLUME_REFERENCE_ML  # 84.0 mL/s
_CALIBRATION_PD_MMHG = 2.0
_CALIBRATION_MAP_TARGET_MMHG = estimate_map(120.0, 80.0)  # ≈93.33 mmHg
_CALIBRATION_TPR_TOTAL_MMHG_S_ML = (
    _CALIBRATION_MAP_TARGET_MMHG - _CALIBRATION_PD_MMHG
) / _CALIBRATION_CO_MEAN_ML_S  # ≈1.0873 mmHg*s/mL -- RPT_total = (PAM_objetivo - Pd) / CO_medio

# Ronda 2 de validación cuantitativa (2026-07-31): Rp, Rd y Pd quedaron VALIDADOS -- ver el
# comentario junto a cada uno abajo. `c=0.8073` sigue siendo la ÚNICA razón por la que
# PHYSIOLOGICAL_PARAMETERS_PENDING_VALIDATION (más abajo) sigue en True.
PHYSIOLOGICAL_RRCR_PARAMETERS = RRCRParameters(
    # mmHg*s/mL -- plegada en Rp (no hay resistor de Poiseuille discreto en esta escala fisiológica).
    # PENDIENTE, mantenido honesto (Ronda 2, 2026-07-31): simplificación aceptada, no revisada como cifra
    # propia porque no representa una magnitud libre -- es un grado de libertad fijado en 0 por diseño.
    r_poiseuille=0.0,
    # mmHg*s/mL -- ~10% de la RPT_total.
    # *** VALIDADO -- confirmado por el validador experto 2026-07-31 (Ronda 2) ***: la MAGNITUD TOTAL
    # (RPT_total≈1.0873 mmHg·s/mL, Rp+Rd) coincide con Guyton (RPT normal ≈1 PRU). La DIVISIÓN 90/10
    # entre Rp y Rd es FORMA VALIDADA (no una cita de magnitud propia): convención de modelado Windkessel
    # de 3 elementos (impedancia característica proximal ≈5-10% de la resistencia total -- Westerhof et al.).
    rp=_CALIBRATION_TPR_TOTAL_MMHG_S_ML * 0.10,  # ≈0.1087
    # mL/mmHg -- calibrado por bisección para presión de pulso ~40 mmHg (antes: 2.0). PENDIENTE ESTRUCTURAL,
    # CONFIRMADO por el validador experto 2026-07-30/31 (Ronda 1 de validación cuantitativa, "casos que no se
    # tocan"): compensa la simplificación de physiological_pulsatile_flow() (sinusoide reescalada, no una
    # curva de eyección ventricular real) -- no cambiar hasta modelar esa curva de eyección pulsátil real
    # (candidato a módulo futuro). No es "todavía no revisado"; es "revisado y confirmado como no validable
    # con el modelo de flujo actual" -- ver CHANGELOG.md, entrada "Validación cuantitativa — Ronda 1".
    c=0.8073,
    # mmHg*s/mL -- resto de la RPT_total (90%). *** VALIDADO -- confirmado por el validador experto
    # 2026-07-31 (Ronda 2) ***: mismo dictamen que Rp arriba (total ≈1 PRU citado, división 90/10 forma
    # validada por convención Windkessel, Westerhof et al.).
    rd=_CALIBRATION_TPR_TOTAL_MMHG_S_ML * 0.90,  # ≈0.9786
    # mmHg -- presión venosa central de referencia.
    # *** VALIDADO -- confirmado por el validador experto 2026-07-31 (Ronda 2) ***: 2.0 mmHg es un
    # estándar de reposo razonable en modelos de lazo cerrado. Hallazgo emergente notable, registrado
    # especialmente: el gradiente de retorno venoso P_sf−Pd (con P_SF_HEALTHY_MMHG=7.0 ya corregido y
    # validado en Ronda 1, closed_loop.py) da 7.0−2.0=5.0 mmHg -- ese gradiente de 5 mmHg coincide con
    # el orden de magnitud que Guyton & Hall (Cap. 20) describe para el gradiente de presión que impulsa
    # el retorno venoso. No se ajustó Pd para producir este resultado -- se calculó primero (Ronda 1) y
    # se confirmó después (Ronda 2) que coincide.
    pd=_CALIBRATION_PD_MMHG,
)

# Ronda 2 de validación cuantitativa (2026-07-31): Rp, Rd y Pd quedaron VALIDADOS (ver comentarios
# arriba, junto a cada uno). Esta bandera NO baja -- `c=0.8073` (compliancia) sigue pendiente
# ESTRUCTURAL (Ronda 1: no validable hasta modelar la curva de eyección ventricular pulsátil real).
# De los cinco parámetros que esta bandera cubría, C es ahora el ÚNICO que falta -- ver CHANGELOG.md,
# entrada "Validación cuantitativa — Ronda 2" para el estado completo del motor.
PHYSIOLOGICAL_PARAMETERS_PENDING_VALIDATION = True  # no cambiar a False sin confirmación explícita del validador experto -- hoy, solo por C

PHYSIOLOGICAL_PARAMETERS_CITATION = (
    "Guyton & Hall -- PAM = RPT_total*CO_medio + Pd (relación exacta del Windkessel en régimen "
    "periódico, no una estimación) resuelta para RPT_total con PAM_objetivo=93.33 mmHg "
    "(estimate_map(120,80), caso ancla 'sano'). División Rp/Rd (convención Windkessel) y C "
    "(calibrado por bisección para presión de pulso ~40 mmHg) siguen siendo una PROPUESTA de "
    "Claude Code, NO una cita verbatim -- PENDIENTE DE CONFIRMACIÓN por el validador experto "
    "antes de considerarse fisiológicamente válida (ver PHYSIOLOGICAL_PARAMETERS_PENDING_VALIDATION)."
)


def physiological_pulsatile_flow(
    heart_rate_bpm: float, sv_ref_ml: float = STROKE_VOLUME_REFERENCE_ML
) -> Tuple[Callable[[float], float], float]:
    """Flujo pulsátil Q(t) escalado a la cadencia real (heart_rate del UPS,
    dinámico) y a la amplitud de SV_ref (constante citada, fija) --
    preserva exactamente la FORMA validada matemáticamente en r_rcr.py
    (`pulsatile_flow_reference`: media 2.2, amplitud 2.5, razón
    amplitud/media ≈1.136 -- el caso oficial pulsatileFlow_R_RCR.json),
    solo reescala tiempo (periodo) y magnitud (caudal medio).

    Devuelve (flow_fn, period_s). `flow_fn` está definido sobre
    [0, period_s), listo para pasar a
    `simulate_r_rcr(flow_fn, ..., period_s=period_s)`."""
    if heart_rate_bpm <= 0:
        raise ValueError(f"heart_rate_bpm debe ser positivo: {heart_rate_bpm}")

    period_s = 60.0 / heart_rate_bpm
    co_mean_ml_s = (heart_rate_bpm / 60.0) * sv_ref_ml  # mL/s

    def flow_fn(t: float) -> float:
        return (co_mean_ml_s / 2.2) * (2.5 * np.sin(2 * np.pi * t / period_s) + 2.2)

    return flow_fn, period_s
