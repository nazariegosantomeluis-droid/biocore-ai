"""
Módulo 3 — Tono vascular alterable por patología, 2026-07-23.

Confirmado por el validador experto: dos mecanismos DISTINTOS por los que
un cuadro patológico altera el barórreflejo del Módulo 2
(`baroreflex.py`, sin tocar) -- no un solo "ajuste" genérico.

*** DOS MECANISMOS, CADA UNO CON SU PROPIA FUENTE Y SU PROPIO EFECTO ***

1. **Hipertensión → reseteo del barostato** (falla en el PUNTO DE AJUSTE,
   no en el efector): los barorreceptores arteriales se readaptan a un
   nivel de presión sostenido en 1-2 días y pierden la capacidad de
   normalizarlo -- Guyton & Hall, Tratado de Fisiología Médica, Cap. 18
   ("Regulación nerviosa de la circulación... reflejos barorreceptores").
   El barórreflejo sigue funcionando (el efector, Rd, sigue respondiendo
   con ganancia normal) -- lo que cambia es QUÉ PAM defiende:
   `target_map` sube. `max_rd`/`min_rd`/`k` quedan intactos (mismo
   `BaroreflexResult` estructural que el Módulo 2, solo con otro objetivo).

2. **Sepsis → vasoplejía** (falla en el EFECTOR, no en el punto de
   ajuste): shock distributivo con refractariedad de la musculatura lisa
   vascular a las catecolaminas endógenas -- Marino, The ICU Book. El
   `target_map` NO cambia (el cuerpo SIGUE queriendo normalizar 93.33
   mmHg -- el reflejo ordena vasoconstricción con la ganancia y el
   objetivo de siempre); lo que falla es la CAPACIDAD del vaso de
   responder a esa orden: el techo de resistencia alcanzable (`max_rd`)
   cae, y la ganancia efectiva (`k`) cae, porque la orden simpática llega
   pero el efector no la ejecuta con la fuerza normal. `min_rd` (techo de
   vasodilatación) queda intacto -- vasoplejía es incapacidad de
   CONSTREÑIR, no una tendencia activa a dilatar más allá de lo normal.

*** SALVAGUARDA ANTI-CIRCULARIDAD (reforzada, ver tests) ***
`HYPERTENSION_RESET_TARGET_MAP_MMHG` y `SEPSIS_MAX_RD_MMHG_S_ML_PER_ML` /
`SEPSIS_GAIN_K` se fijan cada uno con un CRITERIO INDEPENDIENTE de las
cifras de referencia clínica del escenario (`blood_pressure_references.py`
-- 96.67 mmHg para hipertensión, 65 mmHg para sepsis). Documentado abajo,
junto a cada constante, el criterio con el que se eligió -- ninguno es "el
número que hace que el resultado dé la referencia". Después de fijarlos,
`pathological_tone_comparison.py` compara el resultado con la referencia
como control de calidad INDEPENDIENTE, y reporta la divergencia tal cual
sale, sin retocar los parámetros para cerrarla. Mismo criterio ya usado en
`baroreflex.py` para `target_map` fijo entre escenarios -- aquí se permite
que varíe, pero solo por el mecanismo citado (reseteo), nunca por
conveniencia numérica.

Mantiene el test de `baroreflex.py` intacto (`target_map` fijo salvo
override explícito) y añade uno nuevo: `target_map` NO varía por
escenario salvo en hipertensión, donde varía por el mecanismo de reseteo
citado -- no por acercarse a ninguna referencia.

*** LO QUE NO CAMBIA ***
`run_baroreflex()` (Módulo 2) sigue siendo la única implementación del
controlador -- este módulo no reimplementa el bucle de convergencia,
solo decide QUÉ parámetros pasarle por escenario. `physiological_flow.py`
(Rp/C/Pd base) tampoco se toca. Ningún dominio nuevo se añade al UPS
(nada de esto se persiste todavía -- ver `pathological_tone_comparison.py`
para el mismo aislamiento que `baroreflex_comparison.py` ya declaró).
"""

from __future__ import annotations

import dataclasses
from typing import Dict, Optional

from .baroreflex import (
    BAROREFLEX_GAIN_K,
    BAROREFLEX_MAX_RD,
    BAROREFLEX_MIN_RD,
    BAROREFLEX_TARGET_MAP_MMHG,
    BaroreflexResult,
    run_baroreflex,
)

__all__ = [
    "HYPERTENSION_RESET_CITATION",
    "HYPERTENSION_RESET_TARGET_MAP_MMHG",
    "SEPSIS_VASOPLEGIA_CITATION",
    "SEPSIS_MAX_RD_MMHG_S_ML",
    "SEPSIS_GAIN_K",
    "PATHOLOGICAL_TONE_PENDING_VALIDATION",
    "PathologicalToneOverride",
    "PATHOLOGICAL_TONE_OVERRIDES",
    "run_pathological_baroreflex",
]

# --- Mecanismos: fuente citada (cualitativa, dirección del efecto) -----------

HYPERTENSION_RESET_CITATION = (
    "Guyton & Hall, Tratado de Fisiología Médica, Cap. 18 -- reflejos barorreceptores: "
    "los barorreceptores se readaptan ('resetean') a un nivel de presión sostenido en "
    "1-2 días y pierden la capacidad de normalizarlo. Cita el MECANISMO (el barostato "
    "puede resetearse hacia arriba en hipertensión crónica) y su ESCALA TEMPORAL "
    "(1-2 días), no una magnitud numérica del nuevo punto de ajuste -- ese número no "
    "está en esta fuente."
)

SEPSIS_VASOPLEGIA_CITATION = (
    "Marino, The ICU Book -- shock distributivo / vasoplejía séptica: refractariedad de "
    "la musculatura lisa vascular a las catecolaminas endógenas (y exógenas). Cita el "
    "MECANISMO (el efector no responde a la orden simpática con la fuerza normal, aunque "
    "el reflejo sigue intentando vasoconstreñir hacia el mismo objetivo homeostático), "
    "no una magnitud numérica de cuánto cae la resistencia alcanzable -- ese número no "
    "está en esta fuente."
)

# --- Magnitudes: dictaminadas por el validador experto -----------------------
# Ronda 2 de validación cuantitativa (2026-07-31): los TRES parámetros de esta
# bandera (target_map de hipertensión, max_rd/k de sepsis) quedaron VALIDADOS
# (ver docstrings abajo) -- la bandera BAJA a False. Guard "no cambiar sin
# revisión" retirado de `run_pathological_baroreflex()` -- ver CHANGELOG.md,
# entrada "Validación cuantitativa — Ronda 2".
PATHOLOGICAL_TONE_PENDING_VALIDATION = False

HYPERTENSION_RESET_TARGET_MAP_MMHG: float = BAROREFLEX_TARGET_MAP_MMHG * 1.10
"""Nuevo punto de ajuste homeostático en hipertensión crónica -- CRITERIO:
+10% redondo sobre el ancla fija 'sana' (93.33 mmHg) del Módulo 2, mismo
estilo de estimación "redonda, no ajustada" ya usado en ese módulo
(k=1.0, min_rd/max_rd=0.3x/3.0x). Elegido ANTES de mirar la referencia
clínica de este escenario (96.67 mmHg, ACC/AHA 2017) y sin usarla en el
cálculo -- 102.67 mmHg no es 96.67 mmHg, es una coincidencia de orden de
magnitud, no un ajuste. La comparación contra 96.67 se hace después, como
control de calidad independiente (`pathological_tone_comparison.py`),
nunca al revés.

*** VALIDADO -- confirmado por el validador experto 2026-07-31 (Ronda 2) ***:
+10% es consistente con hipertensión Estadio 1 sostenida (reseteo moderado
del barostato, no una crisis hipertensiva severa)."""

SEPSIS_MAX_RD_MMHG_S_ML: float = BAROREFLEX_MAX_RD * 0.5
"""Techo de resistencia alcanzable durante vasoplejía séptica -- CRITERIO:
mitad redonda (0.5x) del techo normal del Módulo 2 (`BAROREFLEX_MAX_RD`,
ya 3.0x la Rd base). Representa refractariedad PARCIAL (el vaso todavía
puede constreñir algo por encima del basal, no vasoplejía total/parálisis
completa, que sería 1.0x = sin capacidad de subir Rd en absoluto) --
"mitad de la capacidad normal" es una estimación redonda y deliberadamente
NO ajustada para producir ninguna PA de referencia. `min_rd` (techo de
vasodilatación, `BAROREFLEX_MIN_RD`) NO se toca: la vasoplejía es
incapacidad de constreñir, no una tendencia activa a dilatar más allá de
lo normal -- no hay mecanismo citado para eso.

*** VALIDADO -- confirmado por el validador experto 2026-07-31 (Ronda 2) ***:
0.5x cae en el rango de refractariedad 30-50% del máximo descrito para
shock refractario -- junto con SEPSIS_GAIN_K (abajo), ambos consistentes
como magnitud de refractariedad parcial, no total."""

SEPSIS_GAIN_K: float = BAROREFLEX_GAIN_K * 0.3
"""Ganancia proporcional efectiva durante vasoplejía séptica -- CRITERIO:
30% redondo de la ganancia normal del Módulo 2 (`BAROREFLEX_GAIN_K=1.0`).
Representa que la orden simpática SIGUE llegando (el reflejo no está
apagado, target_map no cambia) pero el efector la ejecuta con mucha menos
fuerza por unidad de error de PAM -- consistente con "refractariedad", no
con "ausencia total de respuesta" (que sería k=0). Estimación redonda,
elegida sin mirar la PA de referencia de sepsis (65 mmHg).

*** VALIDADO -- confirmado por el validador experto 2026-07-31 (Ronda 2) ***:
0.3x cae en el mismo rango de refractariedad 30-50% del máximo (shock
refractario) que `SEPSIS_MAX_RD_MMHG_S_ML` -- ambos validados juntos, como
un mismo grado de refractariedad expresado en dos efectores distintos
(techo alcanzable y velocidad de respuesta)."""


@dataclasses.dataclass(frozen=True)
class PathologicalToneOverride:
    """Qué parámetros de `run_baroreflex()` sobrescribe un escenario, y por
    qué. `None` en cualquier campo significa "este mecanismo NO toca ese
    parámetro" -- se usa el valor por defecto del Módulo 2, explícitamente,
    no un valor "olvidado"."""

    scenario: str
    mechanism_citation: str
    criterion: str
    target_map_mmhg: Optional[float] = None
    max_rd: Optional[float] = None
    k: Optional[float] = None


PATHOLOGICAL_TONE_OVERRIDES: Dict[str, PathologicalToneOverride] = {
    "hypertension": PathologicalToneOverride(
        scenario="hypertension",
        mechanism_citation=HYPERTENSION_RESET_CITATION,
        criterion=(
            "Reseteo del punto de ajuste (target_map = +10% redondo sobre el ancla fija), "
            "efector (max_rd/min_rd/k) intacto -- el barórreflejo sigue funcionando normal, "
            "solo defiende un objetivo más alto."
        ),
        target_map_mmhg=HYPERTENSION_RESET_TARGET_MAP_MMHG,
        max_rd=None,
        k=None,
    ),
    "sepsis": PathologicalToneOverride(
        scenario="sepsis",
        mechanism_citation=SEPSIS_VASOPLEGIA_CITATION,
        criterion=(
            "Fallo del efector (max_rd=0.5x techo normal, k=0.3x ganancia normal), punto de "
            "ajuste (target_map) intacto -- el cuerpo sigue queriendo normalizar 93.33 mmHg, "
            "simplemente no puede constreñir lo suficiente para lograrlo."
        ),
        target_map_mmhg=None,
        max_rd=SEPSIS_MAX_RD_MMHG_S_ML,
        k=SEPSIS_GAIN_K,
    ),
}


def run_pathological_baroreflex(scenario: str, heart_rate_bpm: float, **kwargs) -> BaroreflexResult:
    """Corre `run_baroreflex()` (Módulo 2, sin modificar) con los parámetros
    sobrescritos por el mecanismo patológico de `scenario`, si existe uno en
    `PATHOLOGICAL_TONE_OVERRIDES`. Escenarios sin entrada (incluido
    "healthy") son un PASS-THROUGH exacto a `run_baroreflex()` -- mismo
    comportamiento que el Módulo 2, ningún cambio implícito.

    `kwargs` explícitos del llamador tienen prioridad sobre el override del
    escenario (p.ej. para tests que quieran forzar un valor concreto)."""
    # Guards de "no cambiar a False sin revisión" retirados -- Ronda 2 de validación
    # cuantitativa (2026-07-31): tanto PATHOLOGICAL_TONE_PENDING_VALIDATION (este
    # módulo) como BAROREFLEX_PARAMETERS_PENDING_VALIDATION (su dependencia) pasaron
    # a False tras confirmación explícita del validador -- ver CHANGELOG.md.

    override = PATHOLOGICAL_TONE_OVERRIDES.get(scenario)
    if override is None:
        return run_baroreflex(heart_rate_bpm, **kwargs)

    call_kwargs = dict(kwargs)
    if override.target_map_mmhg is not None:
        call_kwargs.setdefault("target_map", override.target_map_mmhg)
    if override.max_rd is not None:
        call_kwargs.setdefault("max_rd", override.max_rd)
    if override.k is not None:
        call_kwargs.setdefault("k", override.k)

    return run_baroreflex(heart_rate_bpm, **call_kwargs)
