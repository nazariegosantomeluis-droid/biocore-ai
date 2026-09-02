"""
Módulo 4, eslabón 1 — Volumen sistólico dinámico vía Frank-Starling,
2026-07-24.

Confirmado por el validador experto: el eslabón perdido de esta serie es
el SV dinámico, y el mecanismo que lo hace dinámico es la ley de
Frank-Starling. Se entra por la pieza MÍNIMA -- SV como función del
llenado (EDV) -- con el retorno venoso todavía simplificado y DECLARADO
como andamiaje temporal, para validar este eslabón aislado antes de
cerrar el lazo completo (retorno venoso real con capacitancia venosa/P_sf
viene en el Módulo 4B).

*** DOS COSAS DISTINTAS, MARCADAS POR SEPARADO (mismo criterio que
Módulos 2 y 3) ***

1. **El MECANISMO tiene fuente**: Guyton & Hall, Tratado de Fisiología
   Médica, Cap. 9 (El corazón como bomba) y Cap. 20/24 (Regulación de la
   función cardíaca / gasto cardíaco y retorno venoso) -- ley de
   Frank-Starling: dentro de límites fisiológicos, el corazón bombea toda
   la sangre que recibe sin permitir una acumulación excesiva en las
   venas; el volumen sistólico aumenta con el grado de llenado/
   estiramiento diastólico (EDV, precarga) hasta un techo fisiológico.
   Esta cadena -- SV crece con EDV, con un techo, no linealmente hasta el
   infinito -- es exactamente lo que `stroke_volume_frank_starling()`
   implementa como curva saturante (`SV = SV_MAX*(1-exp(-(EDV-piso)/k))`).

2. **Los NÚMEROS de la curva (techo, piso, constante de forma/
   "elastancia") NO tienen esa fuente -- Guyton no da una ecuación exacta
   SV=f(EDV) ni sus constantes**. Entran marcados
   `FRANK_STARLING_PARAMETERS_PENDING_VALIDATION=True`, con el criterio
   explícito de cada uno documentado abajo -- mismo patrón que
   `k`/`min_rd`/`max_rd`/`target_map` del Módulo 2 y
   `HYPERTENSION_RESET_TARGET_MAP_MMHG`/`SEPSIS_MAX_RD_MMHG_S_ML`/
   `SEPSIS_GAIN_K` del Módulo 3.

*** SALVAGUARDA ANTI-CIRCULARIDAD (reforzada -- más parámetros, más
vigilancia) ***
Ninguna constante de esta curva se fija mirando una `ClinicalReferenceValue`
de presión arterial. El único ancla usada es la ya CITADA
`STROKE_VOLUME_REFERENCE_ML=70 mL` (Guyton, volumen sistólico normal de
reposo -- `physiological_flow.py`, sin cambios) junto al mismo heart_rate
ancla "sano" (72 bpm) ya usado en Módulos 1/2 -- mismo criterio "resuelto
para el ancla" que ya usan `Rd`/`Rp`/`C` (Módulo 1) y `target_map`
(Módulo 2), NO una cifra de PA. La PAM/PA resultante de sepsis
(Módulo 2/3) NO se toca ni se recalcula aquí -- este eslabón está
deliberadamente aislado, no cierra el lazo con el R-RCR todavía.

*** PASO 2 -- RETORNO VENOSO: ANDAMIAJE TEMPORAL, DECLARADO ***
El retorno venoso real (capacitancia venosa, presión de llenado sistémica
media P_sf -- Guyton Cap. 24) es un eslabón POSTERIOR (Módulo 4B). Aquí,
`estimate_edv_venous_return_placeholder_pending_module_4b()` es una
relación PROVISIONAL (EDV inversamente proporcional al heart_rate,
aproximando que el tiempo de llenado diastólico se acorta con la
taquicardia) -- nombre y bandera (`VENOUS_RETURN_PLACEHOLDER_PENDING_MODULE_4B`)
deliberadamente inequívocos para que sea IMPOSIBLE confundir este número
con retorno venoso fisiológico real. Esto es explícito para no repetir el
error histórico de `stroke_volume` fijo en `CardiacDetail`
(`app/engines/digital_twin_organism.py`) -- una simplificación que se
disfrazó de dato real. Aquí la simplificación se declara temporal en el
propio nombre de la función y de la bandera, no solo en un comentario.

*** QUÉ REPARA Y QUÉ NO REPARA ESTA TANDA ***
Repara la deuda de que el SV usado en el R-RCR (`STROKE_VOLUME_REFERENCE_ML`,
`physiological_flow.py`) era una CONSTANTE fija sin importar el escenario:
ahora existe una función real, probada y citada, `SV = f(EDV)`. Lo que
NO hace esta tanda (deliberado, instrucción explícita): conectar esta
función al flujo de entrada del R-RCR en reemplazo de
`STROKE_VOLUME_REFERENCE_ML` -- `physiological_flow.py` queda SIN TOCAR.
Cerrar ese lazo es el siguiente eslabón, una vez que el retorno venoso
real (no el andamiaje de este módulo) esté disponible.
"""

from __future__ import annotations

import dataclasses
import math
from typing import List, Optional, Tuple

from .physiological_flow import STROKE_VOLUME_CITATION, STROKE_VOLUME_REFERENCE_ML

__all__ = [
    "FRANK_STARLING_MECHANISM_CITATION",
    "FRANK_STARLING_PARAMETERS_PENDING_VALIDATION",
    "EDV_HEALTHY_ML",
    "EDV_FLOOR_ML",
    "SV_MAX_ML",
    "FRANK_STARLING_STEEPNESS_ML",
    "HEART_RATE_ANCHOR_BPM",
    "VENOUS_RETURN_PLACEHOLDER_PENDING_MODULE_4B",
    "VALIDATOR_SEPSIS_SV_ESTIMATE_RANGE_ML",
    "FrankStarlingResult",
    "stroke_volume_frank_starling",
    "estimate_edv_venous_return_placeholder_pending_module_4b",
    "compute_dynamic_stroke_volume",
    "stroke_volume_table",
]

# --- Mecanismo: fuente citada --------------------------------------------------
FRANK_STARLING_MECHANISM_CITATION = (
    "Guyton & Hall, Tratado de Fisiología Médica, Cap. 9 (El corazón como bomba) y "
    "Cap. 20/24 (Regulación de la función cardíaca y el gasto cardíaco; retorno venoso) -- "
    "ley de Frank-Starling: dentro de límites fisiológicos, el corazón bombea toda la "
    "sangre que le llega sin permitir una acumulación excesiva en las venas; el volumen "
    "sistólico aumenta con el grado de llenado diastólico (precarga/EDV) hasta un techo "
    "fisiológico. Cita la DIRECCIÓN del efecto y la existencia de un techo -- Guyton no da "
    "una ecuación exacta SV=f(EDV) ni sus constantes numéricas."
)

# --- Magnitudes: dictaminadas por el validador experto -----------------------
# Ronda 1 (2026-07-30/31): EDV_HEALTHY_ML y SV_MAX_ML VALIDADOS con cita de
# Guyton. Ronda 2 (2026-07-31): EDV_FLOOR_ML VALIDADO con cita, y
# FRANK_STARLING_STEEPNESS_ML con FORMA VALIDADA -- los CUATRO parámetros de
# esta bandera están confirmados, así que la bandera BAJA a False. Guard "no
# cambiar sin revisión" retirado de `stroke_volume_frank_starling()` -- ver
# CHANGELOG.md, entrada "Validación cuantitativa — Ronda 2".
FRANK_STARLING_PARAMETERS_PENDING_VALIDATION = False

HEART_RATE_ANCHOR_BPM: float = 72.0
"""Mismo heart_rate ancla 'sano' ya usado en Módulos 1/2 (`physiological_flow.py`,
`_CALIBRATION_HEART_RATE_BPM`) -- reutilizado aquí por consistencia, no
recalculado ni redefinido."""

EDV_HEALTHY_ML: float = 120.0
"""Volumen telediastólico ancla 'sano'. Junto con `HEART_RATE_ANCHOR_BPM`,
define el ancla (72 bpm, 120 mL) sobre la que se resuelve
`FRANK_STARLING_STEEPNESS_ML` para que la curva pase EXACTAMENTE por
(`EDV_HEALTHY_ML`, `STROKE_VOLUME_REFERENCE_ML`) -- no una cifra de PA de
referencia.

*** VALIDADO -- confirmado por el validador experto 2026-07-30 (Ronda 1,
Operación B) ***: Guyton & Hall, Tratado de Fisiología Médica -- EDV
normal de reposo en el rango 110-130 mL. 120 mL cae dentro de ese rango
citado."""

EDV_FLOOR_ML: float = 20.0
"""Piso de EDV por debajo del cual el modelo asume SV=0 (colapso -- el
ventrículo no eyecta con un llenado casi nulo). CRITERIO: redondo,
deliberadamente muy por debajo de cualquier volumen ventricular
fisiológico típico (incluida la referencia de ESV normal, ~40-50 mL) --
conservador, no ajustado a ningún resultado de PA.

*** VALIDADO -- confirmado por el validador experto 2026-07-31 (Ronda 2) ***:
protege contra el colapso quedando por debajo del volumen telesistólico
(VTS) normal (~40-50 mL) -- un EDV en ese rango o menor ya sería
incompatible con eyección, así que 20 mL es un piso conservador y
sensato."""

SV_MAX_ML: float = STROKE_VOLUME_REFERENCE_ML * 2.0  # = 140.0
"""Techo de SV alcanzable por precarga (reserva de Frank-Starling).
CRITERIO original: múltiplo redondo (2.0x) del SV de reposo YA CITADO
(`STROKE_VOLUME_REFERENCE_ML`) -- mismo estilo de múltiplos redondos ya
usado en Módulo 2 (`min_rd`/`max_rd`=0.3x/3.0x) y Módulo 3
(`SEPSIS_MAX_RD_MMHG_S_ML`=0.5x, `SEPSIS_GAIN_K`=0.3x). Representa una
reserva finita, no infinita -- ninguna relación con PA de referencia.

*** VALIDADO -- confirmado por el validador experto 2026-07-30 (Ronda 1,
Operación B) ***: 140 mL es sensato como techo combinando el vaciado
sistólico normal más la reserva por contractilidad aumentada (reserva
inotrópica) -- consistente con la reserva cardíaca descrita en Guyton &
Hall (el corazón puede varias veces su gasto de reposo mediante
precarga+contractilidad combinadas)."""


def _solve_frank_starling_steepness_ml(
    edv_healthy_ml: float = EDV_HEALTHY_ML,
    edv_floor_ml: float = EDV_FLOOR_ML,
    sv_reference_ml: float = STROKE_VOLUME_REFERENCE_ML,
    sv_max_ml: float = SV_MAX_ML,
) -> float:
    """Resuelve algebraicamente la constante de forma `k` de la curva
    saturante `SV = SV_MAX*(1-exp(-(EDV-piso)/k))` para que pase EXACTO
    por el ancla (`edv_healthy_ml`, `sv_reference_ml`) -- mismo criterio
    "resuelto para el ancla" que `RPT_total` (PAM, Módulo 1) y `C`
    (presión de pulso, Módulo 1): despejar UNA constante para reproducir
    UN punto ya citado, nunca una cifra de PA de referencia clínica."""
    remaining_fraction = 1.0 - (sv_reference_ml / sv_max_ml)
    if not (0.0 < remaining_fraction < 1.0):
        raise ValueError(
            f"sv_reference_ml ({sv_reference_ml}) debe ser menor que sv_max_ml ({sv_max_ml}) "
            "para que la curva saturante tenga solución -- revisar SV_MAX_ML."
        )
    return -(edv_healthy_ml - edv_floor_ml) / math.log(remaining_fraction)


FRANK_STARLING_STEEPNESS_ML: float = _solve_frank_starling_steepness_ml()
"""Constante de forma de la curva -- vagamente análoga a una
"elastancia"/compliancia de la relación SV-EDV, pero NO es una cita de
ningún valor de elastancia ventricular de Guyton; es la solución
algebraica de la ecuación del ancla (ver `_solve_frank_starling_steepness_ml`).
Valor numérico ≈144.27 mL.

*** FORMA VALIDADA -- confirmado por el validador experto 2026-07-31
(Ronda 2) ***: no es una cita de magnitud (no hay cifra de Guyton para
este número) -- lo que se validó es que la FORMA exponencial-saturante en
sí es fisiológicamente correcta para representar el mecanismo de
Frank-Starling a nivel de sarcómero (el traslape actina-miosina satura de
forma similarmente asintótica al alargarse el sarcómero, no linealmente
hasta el infinito). El número (≈144.27) queda determinado por esa forma
más el ancla ya citada -- no es, en sí, una cifra independiente que
pudiera "coincidir o no" con literatura."""

VALIDATOR_SEPSIS_SV_ESTIMATE_RANGE_ML: Tuple[float, float] = (30.0, 40.0)
"""Estimación CUALITATIVA del validador experto para SV en sepsis
(HR=150, llenado reducido) -- contexto informativo para el Paso 3, NO una
`ClinicalReferenceValue` formal ni un objetivo de ajuste de
`EDV_HEALTHY_ML`/`EDV_FLOOR_ML`/`SV_MAX_ML`/`FRANK_STARLING_STEEPNESS_ML`
(todos fijados ANTES de calcular este resultado, ver docstring del
módulo). Se compara después, como control de calidad -- si el resultado
calculado hubiera caído fuera de este rango, se habría reportado tal
cual, sin retocar las constantes."""


@dataclasses.dataclass(frozen=True)
class FrankStarlingResult:
    heart_rate_bpm: float
    edv_ml: float
    stroke_volume_ml: float
    edv_from_placeholder: bool
    clamped_at_edv_floor: bool


def stroke_volume_frank_starling(
    edv_ml: float,
    sv_max_ml: float = SV_MAX_ML,
    edv_floor_ml: float = EDV_FLOOR_ML,
    k_ml: float = FRANK_STARLING_STEEPNESS_ML,
) -> float:
    """SV = f(EDV) -- Paso 1, el mecanismo de Frank-Starling. Curva
    saturante: crece monotónicamente con EDV desde 0 (en `edv_floor_ml`)
    hacia el techo `sv_max_ml` sin alcanzarlo nunca -- "el corazón bombea
    más al recibir más, hasta un límite fisiológico" (mecanismo citado,
    ver `FRANK_STARLING_MECHANISM_CITATION`). La FORMA exponencial
    saturante es una decisión de modelado explícita (no una cita de
    Guyton) para representar ese techo -- mismo criterio que la división
    Rp/Rd del Windkessel en `physiological_flow.py` ("convención de
    modelado, no cifra de Guyton").

    Función pura, sin estado -- ningún valor de módulo se muta aquí."""
    # Guard de "no cambiar a False sin revisión" retirado -- Ronda 2 de validación
    # cuantitativa (2026-07-31): FRANK_STARLING_PARAMETERS_PENDING_VALIDATION pasó a
    # False tras confirmación explícita del validador (EDV_HEALTHY_ML, SV_MAX_ML,
    # EDV_FLOOR_ML, FRANK_STARLING_STEEPNESS_ML -- ver docstrings arriba y CHANGELOG.md).
    if edv_ml <= edv_floor_ml:
        return 0.0
    return sv_max_ml * (1.0 - math.exp(-(edv_ml - edv_floor_ml) / k_ml))


# --- Paso 2: retorno venoso simplificado -- ANDAMIAJE TEMPORAL, declarado ------
#
# *** RETIRADA DEL FLUJO DE VALIDACIÓN ACTIVO -- Ronda 1 (2026-07-30/31),
# Operación C ***: el validador experto confirmó que esta bandera y el
# mecanismo que cubre quedaron SUPERSEDED por el retorno venoso real del
# Módulo 4B-ii (`closed_loop.py`, `_venous_return_step`/`_p_sf_effective_mmhg`/
# `_resistance_to_venous_return_mmhg_s_ml`) -- el lazo cerrado NO llama a
# `estimate_edv_venous_return_placeholder_pending_module_4b()` en ningún punto
# (verificado: `closed_loop.py` no la importa). No se retira de este archivo ni
# se cambia a `False` (seguiría siendo una simplificación no-fisiológica si
# alguien la llamara) -- en su lugar, esta función y las que dependen de ella
# (`compute_dynamic_stroke_volume`, `stroke_volume_table`) quedan marcadas
# explícitamente como DEMO STANDALONE NO PRODUCTIVA del eslabón 1 aislado
# (siguen usándose en sus propios tests y en su propio `__main__`), no como
# parte pendiente de validación cuantitativa del modelo activo. Ya no aparece
# en el inventario de parámetros pendientes -- no representa una magnitud
# numérica con un valor que un validador pueda "confirmar" (es la elección de
# una forma funcional -- proporcionalidad inversa a HR -- ya reemplazada).

VENOUS_RETURN_PLACEHOLDER_PENDING_MODULE_4B: bool = True
"""Bandera de andamiaje (no de magnitud numérica) -- sigue en `True` porque
la función de abajo, cuando se llama, SIGUE sin modelar retorno venoso real
(capacitancia venosa, P_sf -- Guyton Cap. 24); eso no cambió. Lo que sí
cambió en Ronda 1 (Operación C): esta bandera ya NO representa un ítem
activo del flujo de validación cuantitativa -- el mecanismo real que la
reemplaza ya existe y está en uso (`closed_loop.py`, Módulo 4B-ii). Ver la
nota de "RETIRADA DEL FLUJO DE VALIDACIÓN ACTIVO" arriba."""


def estimate_edv_venous_return_placeholder_pending_module_4b(
    heart_rate_bpm: float,
    edv_healthy_ml: float = EDV_HEALTHY_ML,
    edv_floor_ml: float = EDV_FLOOR_ML,
    heart_rate_anchor_bpm: float = HEART_RATE_ANCHOR_BPM,
) -> float:
    """*** DEMO STANDALONE NO PRODUCTIVA (Ronda 1, Operación C,
    2026-07-30/31) -- el lazo cerrado (`closed_loop.py`, Módulo 4B-ii) NO
    llama a esta función; usa retorno venoso real (`_venous_return_step`).
    Esta función se conserva únicamente para la demostración aislada del
    eslabón 1 por sí solo (`compute_dynamic_stroke_volume`/
    `stroke_volume_table`/`__main__` de este archivo, y sus propios tests) --
    no representa el comportamiento del sistema conectado. ***

    ANDAMIAJE TEMPORAL -- NO es fisiología final (ver
    `VENOUS_RETURN_PLACEHOLDER_PENDING_MODULE_4B`). Aproxima el llenado
    diastólico (EDV) como inversamente proporcional al heart_rate
    respecto al ancla 'sano' (72 bpm -> 120 mL): a mayor frecuencia, menos
    tiempo de llenado diastólico por latido, menos EDV -- dirección
    cualitativamente correcta (Guyton: la diástole se acorta
    desproporcionadamente más que la sístole al subir la frecuencia), pero
    la proporcionalidad INVERSA exacta es una simplificación de esta
    tanda, NO una cita ni un cálculo de tiempo de llenado real (eso
    requiere capacitancia venosa/P_sf -- ya modelado en `closed_loop.py`
    para el lazo cerrado real). Recortada en `edv_floor_ml` para evitar
    valores negativos/sin sentido en taquicardia extrema.

    Si `heart_rate_bpm <= 0`, lanza `ValueError` (mismo criterio que
    `physiological_pulsatile_flow`)."""
    if heart_rate_bpm <= 0:
        raise ValueError(f"heart_rate_bpm debe ser positivo: {heart_rate_bpm}")
    edv_ml = edv_healthy_ml * (heart_rate_anchor_bpm / heart_rate_bpm)
    return max(edv_ml, edv_floor_ml)


# --- Paso 3: efecto verificable -------------------------------------------------


def compute_dynamic_stroke_volume(
    heart_rate_bpm: float,
    edv_ml: Optional[float] = None,
) -> FrankStarlingResult:
    """Une Paso 1 (mecanismo) y Paso 2 (andamiaje) en un solo resultado.

    Si `edv_ml` se pasa explícito, se usa tal cual (para cuando el Módulo
    4B tenga un EDV real que no venga del placeholder) -- `edv_from_placeholder`
    queda en `False`. Si no, se deriva del andamiaje temporal del Paso 2 --
    `edv_from_placeholder=True`, señal explícita en el propio resultado de
    que ese EDV es provisional.

    Nota Ronda 1 (Operación C, 2026-07-30/31): en su modo POR DEFECTO
    (`edv_ml=None`) esta función es la DEMO STANDALONE no productiva del
    eslabón 1 aislado (ver nota en
    `estimate_edv_venous_return_placeholder_pending_module_4b`) -- el lazo
    cerrado real no la usa así. Llamada con `edv_ml` explícito, en cambio,
    es solo un envoltorio delgado sobre `stroke_volume_frank_starling()`
    (Paso 1, sin cambios, sí vigente) -- ese uso no es "demo", es el
    mecanismo real con un EDV que viene de otro lado."""
    edv_from_placeholder = edv_ml is None
    if edv_ml is None:
        edv_ml = estimate_edv_venous_return_placeholder_pending_module_4b(heart_rate_bpm)

    stroke_volume_ml = stroke_volume_frank_starling(edv_ml)

    return FrankStarlingResult(
        heart_rate_bpm=heart_rate_bpm,
        edv_ml=edv_ml,
        stroke_volume_ml=stroke_volume_ml,
        edv_from_placeholder=edv_from_placeholder,
        clamped_at_edv_floor=edv_ml <= EDV_FLOOR_ML * (1.0 + 1e-9),
    )


def stroke_volume_table(
    heart_rates_bpm: Tuple[float, ...] = (40.0, 72.0, 85.0, 150.0, 220.0),
) -> List[FrankStarlingResult]:
    """Tabla SV vs. (llenado, frecuencia) para un conjunto representativo
    de heart_rates -- mismos anclas que los tests del Módulo 2
    (bradicardia marcada, sano, hipertensión, sepsis, taquicardia
    extrema). Todo vía el andamiaje temporal del Paso 2 -- ver
    `_print_table` para la verificación en contexto contra la estimación
    cualitativa del validador (`VALIDATOR_SEPSIS_SV_ESTIMATE_RANGE_ML`).

    DEMO STANDALONE no productiva (Ronda 1, Operación C) -- ver nota en
    `estimate_edv_venous_return_placeholder_pending_module_4b`."""
    return [compute_dynamic_stroke_volume(hr) for hr in heart_rates_bpm]


def _print_table() -> None:
    print("\nMódulo 4, eslabón 1 -- SV dinámico vía Frank-Starling (retorno venoso: ANDAMIAJE TEMPORAL, Paso 2)")
    print("*** Parámetros de la curva PENDIENTES DE VALIDACIÓN CUANTITATIVA (ver frank_starling.py) ***")
    print(f"Ancla citada: EDV={EDV_HEALTHY_ML:.1f} mL @ HR={HEART_RATE_ANCHOR_BPM:.0f} bpm -> SV={STROKE_VOLUME_REFERENCE_ML:.1f} mL ({STROKE_VOLUME_CITATION.split(' --')[0]})")
    print(f"{'HR (bpm)':<12}{'EDV (mL, placeholder 4B)':<28}{'SV (mL, Frank-Starling)':<26}clamped_at_edv_floor")
    for result in stroke_volume_table():
        print(f"{result.heart_rate_bpm:<12.0f}{result.edv_ml:<28.1f}{result.stroke_volume_ml:<26.1f}{result.clamped_at_edv_floor}")

    sepsis_result = compute_dynamic_stroke_volume(150.0)
    low, high = VALIDATOR_SEPSIS_SV_ESTIMATE_RANGE_ML
    within_range = low <= sepsis_result.stroke_volume_ml <= high
    print(
        f"\nSepsis (HR=150): SV calculado={sepsis_result.stroke_volume_ml:.1f} mL -- "
        f"estimación cualitativa del validador: {low:.0f}-{high:.0f} mL "
        f"({'dentro del rango' if within_range else 'FUERA del rango'}, reportado tal cual, sin retocar constantes)"
    )
    print()


if __name__ == "__main__":
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    _print_table()
