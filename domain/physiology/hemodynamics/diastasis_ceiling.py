"""
Módulo 4B-i — Techo diastólico (diástasis), 2026-07-27.

Corrige un artefacto identificado por el validador experto: el
`VENOUS_RETURN_PLACEHOLDER` del eslabón 1 (`frank_starling.py`,
`estimate_edv_venous_return_placeholder_pending_module_4b`) asume que más
tiempo de llenado diastólico = más EDV, SIN límite -- a 40 bpm eso infla
el EDV a 216 mL, un valor anatómicamente irreal. En la realidad, el
pericardio y la rigidez miocárdica ponen un techo físico al llenado: fase
de **diástasis**, donde el llenado ventricular se detiene (o casi) aunque
sobre tiempo de diástole.

Es lo primero del Módulo 4B porque corrige ese artefacto visible y deja
el EDV anatómicamente sensato ANTES de reemplazar el retorno venoso
simplificado (Módulo 4B-ii, todavía no hecho). Este submódulo NO
reemplaza `estimate_edv_venous_return_placeholder_pending_module_4b()` --
sigue siendo el mismo andamiaje temporal, con su misma bandera
(`VENOUS_RETURN_PLACEHOLDER_PENDING_MODULE_4B`, sin tocar, importada
sin modificar de `frank_starling.py`). Este módulo le añade un TECHO
encima, como una corrección adicional y separada.

*** DOS COSAS DISTINTAS, MARCADAS POR SEPARADO (mismo criterio que
Módulos 2, 3 y el eslabón 1) ***

1. **El MECANISMO tiene fuente**: Guyton & Hall, Tratado de Fisiología
   Médica -- curva de distensibilidad (compliancia) ventricular y fase de
   diástasis del llenado: tras el llenado rápido inicial, la curva de
   presión-volumen del ventrículo se vuelve empinada (el ventrículo se
   vuelve mucho menos distensible cerca de su límite anatómico), y el
   llenado se aplana en una meseta -- el corazón no sigue llenándose
   linealmente solo porque haya más tiempo disponible. Esto es
   exactamente lo que `apply_diastasis_ceiling()` implementa: una curva
   saturante que aplana el EDV crudo del placeholder hacia un techo, en
   vez de dejarlo crecer sin límite.

2. **El NÚMERO del techo (EDV anatómico máximo) NO tiene esa fuente** --
   Guyton describe la existencia de la meseta, no da una cifra exacta de
   "techo anatómico" lista para esta ecuación. Entra marcado
   `DIASTASIS_CEILING_PENDING_VALIDATION=True`, con criterio explícito
   (ver `EDV_ANATOMICAL_CEILING_ML` abajo) -- consistente con que "la
   literatura suele citar ~120-150 mL como EDV normal, con límites de
   distensibilidad por encima" (contexto del validador, no una cita
   verbatim con página).

*** SALVAGUARDA ANTI-CIRCULARIDAD ***
`EDV_ANATOMICAL_CEILING_ML` y `DIASTASIS_TRANSITION_BUDGET_ML` se fijan
sin mirar ninguna `ClinicalReferenceValue` de presión arterial -- son
límites anatómicos en mL, de una escala y naturaleza completamente
distinta a las cifras de PA en mmHg. No se ajustan para que ninguna PA
salga bien; ver criterio de cada uno documentado junto a su constante.

*** QUÉ CAMBIA Y QUÉ NO CAMBIA ***
- `frank_starling.py` **no se toca**: `estimate_edv_venous_return_placeholder_pending_module_4b()`,
  `compute_dynamic_stroke_volume()` y `stroke_volume_table()` siguen
  existiendo exactamente igual, sin el techo -- este módulo los envuelve
  con una función NUEVA y separada, no los reemplaza in situ (mismo
  patrón que Módulo 3 con `run_pathological_baroreflex()` alrededor de
  `run_baroreflex()`, sin tocar `baroreflex.py`).
- El ancla de reposo YA VALIDADA (72 bpm -> EDV=120 mL -> SV=70 mL) queda
  INTACTA: a 72 bpm, el EDV crudo del placeholder ya es exactamente 120
  mL (el propio ancla), por debajo del punto donde el techo empieza a
  actuar -- el techo es la identidad para cualquier EDV crudo <=
  `EDV_HEALTHY_ML` (ver `apply_diastasis_ceiling`). Verificado con test
  dedicado.
- El lazo con el R-RCR sigue SIN cerrarse (`physiological_flow.py` sin
  tocar) -- ese cierre, y el reemplazo real del retorno venoso, quedan
  para el Módulo 4B-ii.
"""

from __future__ import annotations

import dataclasses
import math
from typing import List, Tuple

from .frank_starling import (
    EDV_FLOOR_ML,
    EDV_HEALTHY_ML,
    HEART_RATE_ANCHOR_BPM,
    STROKE_VOLUME_REFERENCE_ML,
    VENOUS_RETURN_PLACEHOLDER_PENDING_MODULE_4B,
    estimate_edv_venous_return_placeholder_pending_module_4b,
    stroke_volume_frank_starling,
)

__all__ = [
    "DIASTASIS_MECHANISM_CITATION",
    "DIASTASIS_CEILING_PENDING_VALIDATION",
    "EDV_ANATOMICAL_CEILING_ML",
    "DIASTASIS_TRANSITION_BUDGET_ML",
    "DiastasisCorrectedResult",
    "apply_diastasis_ceiling",
    "estimate_edv_with_diastasis_ceiling",
    "compute_dynamic_stroke_volume_with_diastasis_ceiling",
    "stroke_volume_table_with_diastasis_ceiling",
]

# --- Mecanismo: fuente citada ---------------------------------------------------
DIASTASIS_MECHANISM_CITATION = (
    "Guyton & Hall, Tratado de Fisiología Médica -- curva de distensibilidad "
    "(compliancia) ventricular y fase de diástasis del llenado diastólico: tras el "
    "llenado rápido inicial, la curva presión-volumen del ventrículo se empina "
    "(el ventrículo se vuelve mucho menos distensible cerca de su límite anatómico, "
    "por rigidez miocárdica y restricción pericárdica) y el llenado se aplana en una "
    "meseta -- más tiempo de diástole ya no se traduce en más EDV proporcional. Cita "
    "la EXISTENCIA de ese techo/meseta, no una cifra numérica exacta de EDV máximo."
)

# --- Magnitud: dictaminada por el validador experto ---------------------------
# Ronda 1 (2026-07-30/31): EDV_ANATOMICAL_CEILING_ML VALIDADO con cita de
# Guyton. Ronda 2 (2026-07-31): DIASTASIS_TRANSITION_BUDGET_ML con FORMA
# VALIDADA -- los DOS parámetros de esta bandera están confirmados, así que
# la bandera BAJA a False. Guards "no cambiar sin revisión" retirados de
# `apply_diastasis_ceiling()` y `compute_dynamic_stroke_volume_with_diastasis_ceiling()`
# -- ver CHANGELOG.md, entrada "Validación cuantitativa — Ronda 2".
DIASTASIS_CEILING_PENDING_VALIDATION = False

EDV_ANATOMICAL_CEILING_ML: float = EDV_HEALTHY_ML * 1.5  # = 180.0
"""Techo anatómico de EDV (distensión máxima antes de que la diástasis lo
detenga). CRITERIO original: múltiplo redondo (1.5x) del ancla ya usada
`EDV_HEALTHY_ML=120` (Módulo 4, eslabón 1) -- consistente con que la
literatura general cita EDV normal ~120-150 mL con límites de
distensibilidad por encima (contexto del validador, no cifra de página).
Mismo estilo de múltiplos redondos ya usado en toda la serie (SV_MAX=2.0x,
sepsis max_rd=0.5x/k=0.3x, hipertensión target_map=+10%). Independiente
de cualquier PA de referencia -- es un límite en mL, no en mmHg.

*** VALIDADO -- confirmado por el validador experto 2026-07-30 (Ronda 1,
Operación B) ***: Guyton & Hall, Tratado de Fisiología Médica -- la curva
de distensibilidad (compliancia) ventricular se vuelve casi vertical en
el rango 150-170 mL, respetando la restricción del pericardio. 180 mL,
por encima de ese rango, es consistente como techo asintótico (la curva
saturante de este módulo no "toca" 180 exactamente, se acerca a él)."""

DIASTASIS_TRANSITION_BUDGET_ML: float = EDV_ANATOMICAL_CEILING_ML - EDV_HEALTHY_ML  # = 60.0
"""Constante de forma de la curva de saturación del techo -- CRITERIO:
deliberadamente IGUAL al presupuesto de distensión restante
(techo - ancla), para no introducir una constante libre adicional sin
justificar (economía de parámetros -- "más parámetros = más vigilancia").
Con esta elección, la curva alcanza ~63% del presupuesto restante cuando
el exceso crudo iguala al propio presupuesto, y se acerca asintóticamente
al techo sin necesitar una segunda cifra estimada aparte del techo mismo.

*** FORMA VALIDADA -- confirmado por el validador experto 2026-07-31
(Ronda 2) ***: no es una cita de magnitud -- lo que se validó es que la
transición hacia el techo es ASINTÓTICA (se acerca sin alcanzarlo
abruptamente), consistente con la fisiología de la diástasis (el llenado
se frena progresivamente, no se detiene en seco). El valor numérico
(60.0 mL) queda determinado por esa forma más el techo ya validado, no
es una cifra independiente a contrastar con literatura."""


@dataclasses.dataclass(frozen=True)
class DiastasisCorrectedResult:
    heart_rate_bpm: float
    raw_edv_ml: float  # EDV crudo del placeholder (Módulo 4, eslabón 1) -- el artefacto sin corregir
    corrected_edv_ml: float  # con el techo de diástasis aplicado
    diastasis_ceiling_active: bool  # True si el techo tuvo efecto (raw_edv > EDV_HEALTHY_ML)
    stroke_volume_ml: float
    clamped_at_edv_floor: bool  # mismo piso de taquicardia extrema del eslabón 1, sin cambios


def apply_diastasis_ceiling(
    raw_edv_ml: float,
    edv_healthy_ml: float = EDV_HEALTHY_ML,
    transition_budget_ml: float = DIASTASIS_TRANSITION_BUDGET_ML,
) -> float:
    """Curva saturante que aplana el EDV crudo del placeholder hacia el
    techo anatómico -- Paso único de este submódulo (mecanismo de
    diástasis, ver docstring del módulo).

    IDENTIDAD para `raw_edv_ml <= edv_healthy_ml`: el techo de
    distensibilidad no actúa por debajo (o en) el volumen de reposo ya
    citado -- ahí no hay sobre-llenado que aplanar. Esto es lo que
    mantiene intacto el ancla de reposo (72 bpm -> 120 mL -> 70 mL): a esa
    frecuencia el placeholder YA da exactamente 120 mL, sin exceso.

    Para `raw_edv_ml > edv_healthy_ml`, satura exponencialmente hacia
    `edv_healthy_ml + transition_budget_ml` (= `EDV_ANATOMICAL_CEILING_ML`
    por construcción) sin excederlo nunca -- mismo estilo de curva
    saturante que `stroke_volume_frank_starling()` (Paso 1 del eslabón 1),
    reutilizado aquí para el mismo tipo de fenómeno fisiológico (una
    meseta), no copiado por casualidad."""
    # Guard de "no cambiar a False sin revisión" retirado -- Ronda 2 de validación
    # cuantitativa (2026-07-31): DIASTASIS_CEILING_PENDING_VALIDATION pasó a False
    # tras confirmación explícita del validador -- ver docstrings arriba y CHANGELOG.md.
    if raw_edv_ml <= edv_healthy_ml:
        return raw_edv_ml
    excess_ml = raw_edv_ml - edv_healthy_ml
    return edv_healthy_ml + transition_budget_ml * (1.0 - math.exp(-excess_ml / transition_budget_ml))


def estimate_edv_with_diastasis_ceiling(
    heart_rate_bpm: float,
    heart_rate_anchor_bpm: float = HEART_RATE_ANCHOR_BPM,
) -> Tuple[float, float]:
    """Compone Paso 2 del eslabón 1 (placeholder crudo, SIN modificar,
    importado tal cual de `frank_starling.py`) con el techo de diástasis
    de este submódulo. Devuelve `(raw_edv_ml, corrected_edv_ml)` -- ambos,
    para que el llamador pueda ver el artefacto original junto a la
    corrección (ver `_print_comparison_table`)."""
    raw_edv_ml = estimate_edv_venous_return_placeholder_pending_module_4b(
        heart_rate_bpm, heart_rate_anchor_bpm=heart_rate_anchor_bpm
    )
    corrected_edv_ml = apply_diastasis_ceiling(raw_edv_ml)
    return raw_edv_ml, corrected_edv_ml


def compute_dynamic_stroke_volume_with_diastasis_ceiling(heart_rate_bpm: float) -> DiastasisCorrectedResult:
    """Mismo rol que `compute_dynamic_stroke_volume()` del eslabón 1, pero
    con el EDV pasado por el techo de diástasis antes de entrar a la
    curva de Frank-Starling (`stroke_volume_frank_starling`, sin tocar,
    Paso 1 del eslabón 1 -- el mecanismo de Frank-Starling no cambia, solo
    cambia el EDV que se le pasa)."""
    # Guard de "no cambiar a False sin revisión" retirado -- Ronda 2 de validación
    # cuantitativa (2026-07-31): FRANK_STARLING_PARAMETERS_PENDING_VALIDATION (su
    # dependencia) pasó a False tras confirmación explícita del validador -- ver
    # frank_starling.py y CHANGELOG.md.
    raw_edv_ml, corrected_edv_ml = estimate_edv_with_diastasis_ceiling(heart_rate_bpm)
    stroke_volume_ml = stroke_volume_frank_starling(corrected_edv_ml)

    return DiastasisCorrectedResult(
        heart_rate_bpm=heart_rate_bpm,
        raw_edv_ml=raw_edv_ml,
        corrected_edv_ml=corrected_edv_ml,
        diastasis_ceiling_active=raw_edv_ml > EDV_HEALTHY_ML * (1.0 + 1e-9),
        stroke_volume_ml=stroke_volume_ml,
        clamped_at_edv_floor=corrected_edv_ml <= EDV_FLOOR_ML * (1.0 + 1e-9),
    )


def stroke_volume_table_with_diastasis_ceiling(
    heart_rates_bpm: Tuple[float, ...] = (40.0, 72.0, 85.0, 150.0, 220.0),
) -> List[DiastasisCorrectedResult]:
    """Misma tabla de heart_rates de referencia que
    `stroke_volume_table()` (eslabón 1) -- para comparación directa,
    fila a fila, entre el EDV crudo (artefacto) y el corregido."""
    return [compute_dynamic_stroke_volume_with_diastasis_ceiling(hr) for hr in heart_rates_bpm]


def _print_comparison_table() -> None:
    print("\nMódulo 4B-i -- techo diastólico (diástasis) sobre el placeholder de retorno venoso")
    print("*** Techo anatómico PENDIENTE DE VALIDACIÓN CUANTITATIVA (ver diastasis_ceiling.py) ***")
    print(f"Ancla de reposo (sin romper): {HEART_RATE_ANCHOR_BPM:.0f} bpm -> EDV={EDV_HEALTHY_ML:.1f} mL -> SV={STROKE_VOLUME_REFERENCE_ML:.1f} mL")
    print(f"Techo anatómico: EDV_ANATOMICAL_CEILING_ML={EDV_ANATOMICAL_CEILING_ML:.1f} mL")
    print(f"{'HR (bpm)':<12}{'EDV crudo (artefacto)':<24}{'EDV corregido (techo)':<24}{'SV (mL)':<12}{'techo activo'}")
    for result in stroke_volume_table_with_diastasis_ceiling():
        print(
            f"{result.heart_rate_bpm:<12.0f}{result.raw_edv_ml:<24.1f}{result.corrected_edv_ml:<24.1f}"
            f"{result.stroke_volume_ml:<12.1f}{result.diastasis_ceiling_active}"
        )

    anchor = compute_dynamic_stroke_volume_with_diastasis_ceiling(HEART_RATE_ANCHOR_BPM)
    anchor_intact = (
        abs(anchor.corrected_edv_ml - EDV_HEALTHY_ML) < 0.01
        and abs(anchor.stroke_volume_ml - STROKE_VOLUME_REFERENCE_ML) < 0.01
    )
    print(f"\nAncla de reposo intacta: {anchor_intact} (EDV={anchor.corrected_edv_ml:.2f} mL, SV={anchor.stroke_volume_ml:.2f} mL)")
    print()


if __name__ == "__main__":
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    _print_comparison_table()
