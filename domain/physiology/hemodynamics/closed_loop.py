"""
Módulo 4B-ii — Retorno venoso real + CIERRE DEL LAZO, 2026-07-27. El
clímax de esta serie: reemplaza el `VENOUS_RETURN_PLACEHOLDER` (Módulo 4,
eslabón 1) por retorno venoso real dependiente de capacitancia venosa y
presión media de llenado sistémico (P_sf), y cierra la cadena completa
hasta la presión arterial:

    retorno venoso -> EDV (con techo diastólico, Módulo 4B-i) ->
    SV (Frank-Starling, eslabón 1) -> flujo -> R-RCR -> presión ->
    barórreflejo (Módulo 2/3) -> resistencia -> (de vuelta al retorno)

Esto introduce retroalimentación REAL (no una cadena unidireccional como
hasta ahora): la resistencia que el barórreflejo ajusta en un tick
influye el retorno venoso del SIGUIENTE tick, con riesgo genuino de
oscilación/no-convergencia. El "tick virtual" stateless (todo el estado
vive en variables locales de la llamada, nada en el módulo ni en sesión)
debe manejarlo -- ver `run_closed_loop()`.

*** REUTILIZACIÓN, NO DUPLICACIÓN ***
Este módulo NO reimplementa ninguna física ya construida y probada:
- `run_pathological_baroreflex()` (Módulo 3, sin tocar) se llama con
  `max_ticks=1` para ejecutar EXACTAMENTE un paso del controlador
  proporcional del barórreflejo (una evaluación R-RCR + un ajuste de Rd +
  una evaluación de cierre con el Rd ajustado -- ver `run_baroreflex()`,
  Módulo 2, sin tocar) -- reutiliza el mecanismo citado y las magnitudes
  ya declaradas pendientes de Rd/k/target_map/max_rd, incluidos los
  overrides patológicos de hipertensión/sepsis del Módulo 3.
- `apply_diastasis_ceiling()` (Módulo 4B-i, sin tocar) y
  `stroke_volume_frank_starling()` (eslabón 1, sin tocar) se llaman tal
  cual.
- `physiological_pulsatile_flow()` y `PHYSIOLOGICAL_RRCR_PARAMETERS`
  (Módulo 1, sin tocar) siguen siendo la base del flujo/Rp/C/Pd.

*** DOS COSAS DISTINTAS, MARCADAS POR SEPARADO (mismo criterio que toda
la serie) ***

1. **El MECANISMO tiene fuente**: Guyton & Hall, Cap. 20 (el gasto
   cardíaco está gobernado principalmente por el retorno venoso, no al
   revés -- VR=(P_sf-P_ra)/RVR, la presión de llenado sistémica media
   frente a la resistencia que se opone al retorno) y Cap. 24 (shock
   distributivo: la capacitancia venosa aumentada dilata el reservorio
   venoso, colapsando P_sf y, con ella, el retorno venoso).

2. **Los NÚMEROS (P_sf basal, cuánto sube la capacitancia venosa en
   sepsis, la resistencia al retorno venoso) NO tienen esa fuente** --
   entran marcados `VENOUS_RETURN_PARAMETERS_PENDING_VALIDATION=True`,
   con criterio explícito documentado junto a cada constante.

*** SALVAGUARDA ANTI-CIRCULARIDAD MÁXIMA (este es el momento de mayor
riesgo de toda la serie -- más parámetros nuevos que en cualquier tanda
anterior) ***
`P_SF_HEALTHY_MMHG` (Ronda 1: VALIDADO con cita directa de Guyton, 7.0
mmHg) y `VENOUS_CAPACITANCE_SEPSIS_MULTIPLIER` (todavía criterio redondo,
sin confirmar) se fijan SIN mirar ninguna `ClinicalReferenceValue` de PA
-- son mmHg y multiplicadores adimensionales de una naturaleza
completamente distinta a la PA resultante. `RVR_REFERENCE_MMHG_S_ML` es
la ÚNICA constante resuelta algebraicamente, y se resuelve contra el
ancla YA CITADA de EDV/SV (72 bpm -> 120 mL -> 70 mL, Módulo 4B-i/eslabón
1) -- exactamente el mismo criterio "resuelto para el ancla" que
`Rd`/`Rp`/`C` (Módulo 1), `target_map` (Módulo 2) y
`FRANK_STARLING_STEEPNESS_ML` (eslabón 1). NINGUNA constante de esta
tanda se resuelve, ajusta ni retoca contra 85/55 (sepsis) ni 130/80
(hipertensión) -- la PA de estos escenarios con el lazo cerrado se
calcula DESPUÉS de fijar todo lo anterior, y se reporta tal cual sale,
sea cual sea la dirección, sin retocar ningún parámetro para que "cierre
mejor". Test dedicado lo verifica. La corrección de P_sf en Ronda 1 (de
10.0 a 7.0 mmHg) es la excepción que confirma la regla: se hizo porque
10.0 era un ERROR fisiológico (ver `P_SF_HEALTHY_MMHG`), no porque se
acercara o alejara de ninguna PA de referencia -- de hecho se verificó
DESPUÉS que la sepsis siguiera colapsando por el mismo mecanismo, no que
la corrección "mejorara" el resultado.

*** ACOPLAMIENTO resistencia -> retorno: decisión de modelado ORIGINALMENTE
sin cita propia, VALIDADA OFICIALMENTE en Ronda 2 (2026-07-31) -- Y CÓMO SE
ELIGIÓ EL SIGNO (documentado con total transparencia, porque aquí era donde
más fácil hubiera sido introducir circularidad sin darse cuenta) ***
Guyton describe cualitativamente que la activación simpática co-activa
tono arteriolar (sube Rd) Y tono venoso (venoconstricción, que AYUDA al
retorno venoso -- reduce el volumen "no estresado" de las venas,
empujando sangre hacia el centro) -- pero no da una ecuación que ligue el
`Rd` de este proyecto con una `RVR` (resistencia al retorno venoso)
numérica. Se probaron las DOS direcciones posibles antes de fijar esta,
con dos criterios INDEPENDIENTES de cualquier PA de referencia:

1. `RVR_actual = RVR_referencia · (Rd_actual/Rd_base)` (RVR SUBE con Rd):
   produjo un colapso de retroalimentación POSITIVA -- no solo en sepsis,
   sino también en HIPERTENSIÓN (que no debería entrar en shock): más Rd
   -> más RVR -> menos retorno -> menos SV -> menos presión -> el
   barórreflejo sube Rd aún más -> ciclo vicioso hasta el techo de Rd,
   sin importar el escenario. Un modelo que colapsa TODOS los escenarios
   por igual, incluidos los que no deberían chocar, es un artefacto de
   inestabilidad numérica/estructural, no un hallazgo fisiológico
   específico de una enfermedad -- se descartó por esta razón estructural,
   NO porque "no diera 85/55".
2. `RVR_actual = RVR_referencia · (Rd_base/Rd_actual)` (RVR BAJA con Rd,
   la elegida): consistente con la DIRECCIÓN cualitativa citada
   (venoconstricción simpática ayuda al retorno) y, verificado
   computacionalmente, produce un equilibrio ESTABLE para sano e
   hipertensión (sin chocar límites, sin colapsar) y deja que sepsis
   colapse por SU PROPIO mecanismo ya fijado en el Módulo 3 (vasoplejía:
   `max_rd`/`k` reducidos) -- un comportamiento específico de escenario,
   no un artefacto universal.

La elección final se basó en (a) la dirección cualitativa citada y (b)
estabilidad estructural básica (un modelo no puede colapsar cualquier
escenario por igual y seguir siendo útil) -- NUNCA en si la PA de sepsis
se acercaba a 85/55 o la de hipertensión a 130/80. La magnitud del
acoplamiento (el cociente Rd_actual/Rd_base) es la MISMA en ambas
direcciones probadas -- lo único que cambió fue el signo, decidido antes
de mirar qué tan cerca quedaba cualquier PA de referencia.

*** Ronda 2 (2026-07-31): esta decisión pasó de "sin cita propia" a
VALIDADA OFICIALMENTE ***. El validador experto confirmó con cita
concreta: los receptores alfa-1 adrenérgicos median tanto la
constricción arteriolar (Rd) como la venoconstricción -- el mismo
receptor, el mismo tono simpático, dos efectores. Eso confirma la
DIRECCIÓN elegida (opción 2 arriba); la MAGNITUD (sin exponente
adicional, cociente lineal) sigue respaldada por la misma estabilidad
estructural ya verificada, no por una segunda cita. Ver
`_resistance_to_venous_return_mmhg_s_ml` para la anotación formal junto
al código.

*** SEPSIS: LA CONEXIÓN ESTRUCTURAL CON EL MÓDULO 3 ***
`_p_sf_effective_mmhg()` no compara el string `"sepsis"` a mano -- lee
`PATHOLOGICAL_TONE_OVERRIDES` (Módulo 3, sin tocar) y activa la caída de
P_sf para CUALQUIER escenario cuyo override ya module `max_rd` (hoy, solo
sepsis) -- "conecta ese efecto que ya existía en el módulo 3" de forma
estructural, no como un caso especial hardcodeado aparte.
"""

from __future__ import annotations

import dataclasses
from typing import List, Tuple

from .diastasis_ceiling import apply_diastasis_ceiling
from .frank_starling import (
    EDV_FLOOR_ML,
    EDV_HEALTHY_ML,
    HEART_RATE_ANCHOR_BPM,
    STROKE_VOLUME_REFERENCE_ML,
    stroke_volume_frank_starling,
)
from .pathological_tone import PATHOLOGICAL_TONE_OVERRIDES, run_pathological_baroreflex
from .physiological_flow import PHYSIOLOGICAL_RRCR_PARAMETERS

__all__ = [
    "VENOUS_RETURN_MECHANISM_CITATION",
    "VENOUS_RETURN_PARAMETERS_PENDING_VALIDATION",
    "P_SF_HEALTHY_MMHG",
    "VENOUS_CAPACITANCE_SEPSIS_MULTIPLIER",
    "RD_BASE_MMHG_S_ML",
    "RVR_REFERENCE_MMHG_S_ML",
    "CLOSED_LOOP_MAX_TICKS",
    "CLOSED_LOOP_CONVERGENCE_TOL",
    "CLOSED_LOOP_RELAXATION_FACTOR",
    "ClosedLoopTick",
    "ClosedLoopResult",
    "run_closed_loop",
]

# --- Mecanismo: fuente citada ---------------------------------------------------
VENOUS_RETURN_MECHANISM_CITATION = (
    "Guyton & Hall, Tratado de Fisiología Médica, Cap. 20 (Gasto cardíaco, retorno venoso "
    "y su regulación) -- el gasto cardíaco está gobernado principalmente por el retorno "
    "venoso: VR=(P_sf-P_ra)/RVR, la presión de llenado sistémica media (P_sf) frente a la "
    "resistencia que se opone al retorno (RVR). Cap. 24 (Shock circulatorio -- shock "
    "distributivo/séptico): la capacitancia venosa aumentada dilata el reservorio venoso, "
    "colapsando P_sf y, con ella, el retorno venoso -- mecanismo del shock distributivo, "
    "no una cifra numérica de cuánto cae P_sf ni de la capacitancia venosa."
)

# --- Magnitudes: dictaminadas por el validador experto -----------------------
# Ronda 1 (2026-07-30/31): P_SF_HEALTHY_MMHG VALIDADO con cita de Guyton.
# Ronda 2 (2026-07-31): RVR_REFERENCE_MMHG_S_ML con FORMA VALIDADA (única
# solución de Ohm dado el gradiente ya validado), VENOUS_CAPACITANCE_SEPSIS_MULTIPLIER
# registrado como UMBRAL HEURÍSTICO ACEPTADO (el validador aclaró explícitamente
# que no hay cita universal para esto -- es una convención de simulación
# razonable, NO una cita directa; se registra con esa naturaleza honesta), y
# el acoplamiento Rd->RVR (`_resistance_to_venous_return_mmhg_s_ml`) VALIDADO
# formalmente (receptores alfa-1 median constricción arteriolar Y venosa;
# validado por estabilidad + parsimonia). Los TRES parámetros de esta bandera
# más la decisión de acoplamiento están confirmados -- la bandera BAJA a
# False. Guards "no cambiar sin revisión" retirados de `run_closed_loop()` --
# ver CHANGELOG.md, entrada "Validación cuantitativa — Ronda 2".
VENOUS_RETURN_PARAMETERS_PENDING_VALIDATION = False

P_SF_HEALTHY_MMHG: float = 7.0
"""Presión de llenado sistémica media basal.

*** VALIDADO -- confirmado por el validador experto 2026-07-30 (Ronda 1,
Operación A) ***: Guyton & Hall, Tratado de Fisiología Médica -- presión
media de llenado sistémica normal en el adulto normovolémico ≈7.0 mmHg
(rango 6-8 mmHg). Cita directa, con número -- no una estimación redonda.

CORRECCIÓN, no ajuste fino: el valor original de esta serie (10.0 mmHg,
Módulo 4B-ii, 2026-07-30 tanda anterior) era un ERROR fisiológico real,
no una estimación pendiente de refinar -- 10.0 mmHg implica un paciente
"sano" hipervolémico, incompatible con el ancla de reposo que el resto
del modelo asume. Corregido a 7.0 mmHg, dentro del gradiente positivo
sobre `Pd=2.0 mmHg` (Módulo 1, sin cambios) -- 7.0 > 2.0, sin conflicto
algebraico. `RVR_REFERENCE_MMHG_S_ML` (abajo) se re-despejó contra este
valor corregido para seguir reproduciendo EXACTO el mismo ancla de
siempre (72 bpm -> 120 mL EDV -> 70 mL SV -> PAM 93.33) -- la corrección
de P_sf no requirió tocar el ancla ni ningún otro módulo."""

VENOUS_CAPACITANCE_SEPSIS_MULTIPLIER: float = 2.0
"""Cuánto se asume que sube la capacitancia venosa en vasoplejía séptica.
CRITERIO: múltiplo redondo (2.0x) -- mismo estilo de múltiplos redondos
ya usado en toda la serie (SV_MAX=2.0x eslabón 1, techo EDV=1.5x Módulo
4B-i, max_rd/k sepsis=0.5x/0.3x Módulo 3). Representa una capacitancia
venosa aproximadamente duplicada, consistente con la DIRECCIÓN del
mecanismo citado (Guyton Cap. 24), no una magnitud de página. Con P_sf
inversamente proporcional a la capacitancia (a volumen sanguíneo
efectivo constante -- no modelado por separado en esta tanda), esto
implica P_sf_sepsis = P_SF_HEALTHY_MMHG / 2.0 = 3.5 mmHg (Ronda 1:
recalculado tras la corrección de P_SF_HEALTHY_MMHG a 7.0 -- antes 5.0
mmHg con el valor erróneo de 10.0).

*** REGISTRADO -- validador experto 2026-07-31 (Ronda 2), naturaleza
honesta: UMBRAL HEURÍSTICO ACEPTADO, NO CITA DIRECTA ***. El validador
aclaró explícitamente que no existe una cifra universal citable en
Guyton (ni en otra fuente estándar) para "cuánto sube la capacitancia
venosa en sepsis" -- a diferencia de MIN_RD/MAX_RD (que sí tenían
fracciones citadas con página), este 2.0x es una convención de
simulación razonable, aceptada como tal por el validador, no verificada
contra una magnitud publicada. Se registra con esta distinción
deliberada -- inflar esto a "cita" sería exactamente el riesgo de
circularidad que la clasificación por categorías de Ronda 2
(preparación) buscaba evitar."""

RD_BASE_MMHG_S_ML: float = PHYSIOLOGICAL_RRCR_PARAMETERS.rd
"""Rd calibrado del Módulo 1 (sin cambios) -- referencia para el
acoplamiento resistencia->RVR de abajo, y punto de partida (tick 0) del
lazo cerrado."""


def _solve_rvr_reference_mmhg_s_ml(
    p_sf_healthy_mmhg: float = P_SF_HEALTHY_MMHG,
    pd_reference_mmhg: float = PHYSIOLOGICAL_RRCR_PARAMETERS.pd,
    edv_healthy_ml: float = EDV_HEALTHY_ML,
    heart_rate_anchor_bpm: float = HEART_RATE_ANCHOR_BPM,
) -> float:
    """Resuelve algebraicamente la ÚNICA constante de esta tanda que no es
    un múltiplo redondo directo: la resistencia al retorno venoso de
    referencia, para que el retorno venoso reproduzca EXACTO el ancla ya
    citada (72 bpm -> EDV=120 mL) cuando Rd_actual=Rd_base (tick 0, antes
    de que el barórreflejo mueva nada). Mismo criterio "resuelto para el
    ancla" que RPT_total/C (Módulo 1), target_map (Módulo 2) y
    FRANK_STARLING_STEEPNESS_ML (eslabón 1) -- NUNCA una cifra de PA de
    referencia clínica."""
    period_s_anchor = 60.0 / heart_rate_anchor_bpm
    venous_return_needed_ml_s = edv_healthy_ml / period_s_anchor
    return (p_sf_healthy_mmhg - pd_reference_mmhg) / venous_return_needed_ml_s


RVR_REFERENCE_MMHG_S_ML: float = _solve_rvr_reference_mmhg_s_ml()
"""Resistencia al retorno venoso de referencia (Rd=Rd_base) -- ver
`_solve_rvr_reference_mmhg_s_ml`. Valor numérico ≈0.03472 mmHg·s/mL
(Ronda 1: re-despejado tras la corrección de P_SF_HEALTHY_MMHG a 7.0 --
antes ≈0.0556 mmHg·s/mL con el P_sf erróneo de 10.0; el ancla de reposo
que esta constante reproduce -- 72 bpm -> 120 mL -> 70 mL -- no cambió,
solo el valor de la constante que la sostiene).

*** FORMA VALIDADA -- confirmado por el validador experto 2026-07-31
(Ronda 2) ***: no es una cita de magnitud independiente -- es la ÚNICA
solución posible de la ley de Ohm (R=V/I, aquí RVR=(P_sf-Pd)/retorno)
dado un gradiente de presión YA VALIDADO (P_sf=7.0 mmHg y Pd=2.0 mmHg,
Ronda 1 y Ronda 2 respectivamente) y un flujo objetivo YA CITADO (el
ancla EDV=120mL/72bpm). Con esos tres ya confirmados, RVR no tiene grado
de libertad propio que "coincidir o no" con literatura -- se deriva."""


def _p_sf_effective_mmhg(scenario: str) -> float:
    """Conexión ESTRUCTURAL con el Módulo 3 (no un `if scenario=="sepsis"`
    hardcodeado): cualquier escenario cuyo override ya reduzca `max_rd`
    (hoy, solo sepsis -- ver `pathological_tone.py`) también dilata las
    venas -- mismo mecanismo de vasoplejía, dos efectores distintos
    (arteriolar, Módulo 3; venoso, este módulo)."""
    override = PATHOLOGICAL_TONE_OVERRIDES.get(scenario)
    if override is not None and override.max_rd is not None:
        return P_SF_HEALTHY_MMHG / VENOUS_CAPACITANCE_SEPSIS_MULTIPLIER
    return P_SF_HEALTHY_MMHG


def _resistance_to_venous_return_mmhg_s_ml(rd_current_mmhg_s_ml: float) -> float:
    """RVR escala INVERSAMENTE con la Rd actual del barórreflejo -- más
    tono simpático (Rd sube) facilita el retorno venoso (RVR baja), no lo
    opone. Elegida originalmente por dirección fisiológica citada +
    estabilidad estructural verificada (ver docstring del módulo, sección
    de acoplamiento resistencia->retorno, para el razonamiento completo y
    la alternativa descartada), NUNCA por acercarse a una PA de referencia.

    *** VALIDADO OFICIALMENTE -- confirmado por el validador experto
    2026-07-31 (Ronda 2) ***: los receptores alfa-1 adrenérgicos median
    tanto la constricción arteriolar (Rd, ya modelada) como la
    venoconstricción (efecto sobre RVR/capacitancia venosa) -- el mismo
    tono simpático que sube Rd fisiológicamente también facilita el
    retorno venoso por el mismo receptor. Dirección confirmada por esta
    cita, magnitud (el cociente Rd_base/Rd_actual, sin exponente
    adicional) confirmada por estabilidad estructural y parsimonia (la
    alternativa con signo opuesto colapsaba todos los escenarios por
    igual, un artefacto -- ver docstring del módulo)."""
    return RVR_REFERENCE_MMHG_S_ML * (RD_BASE_MMHG_S_ML / rd_current_mmhg_s_ml)


def _venous_return_step(
    heart_rate_bpm: float,
    rd_current_mmhg_s_ml: float,
    scenario: str,
) -> Tuple[float, float, float, float]:
    """Un paso de Paso 1 (retorno venoso real): devuelve
    `(p_sf_effective_mmhg, rvr_mmhg_s_ml, venous_return_ml_s, raw_edv_ml)`."""
    p_sf_effective_mmhg = _p_sf_effective_mmhg(scenario)
    rvr_mmhg_s_ml = _resistance_to_venous_return_mmhg_s_ml(rd_current_mmhg_s_ml)
    pd_reference_mmhg = PHYSIOLOGICAL_RRCR_PARAMETERS.pd

    venous_return_ml_s = (p_sf_effective_mmhg - pd_reference_mmhg) / rvr_mmhg_s_ml
    period_s = 60.0 / heart_rate_bpm
    raw_edv_ml = venous_return_ml_s * period_s

    return p_sf_effective_mmhg, rvr_mmhg_s_ml, venous_return_ml_s, raw_edv_ml


# --- Paso 2: cierre del lazo, tick virtual stateless ----------------------------

CLOSED_LOOP_MAX_TICKS: int = 40
"""Control numérico del bucle combinado -- mismo orden que
BAROREFLEX_MAX_TICKS (Módulo 2). NO es una magnitud fisiológica, no se
marca pendiente."""

CLOSED_LOOP_CONVERGENCE_TOL: float = 1e-4
"""Tolerancia relativa en Rd entre ticks COMBINADOS consecutivos -- mismo
valor y criterio que BAROREFLEX_CONVERGENCE_TOL (Módulo 2). Control
numérico, no magnitud fisiológica."""

CLOSED_LOOP_RELAXATION_FACTOR: float = 0.5
"""*** CONTROL NUMÉRICO DE CONVERGENCIA -- NO ES UN PARÁMETRO FISIOLÓGICO,
NO REQUIERE VALIDACIÓN FISIOLÓGICA, SIN BANDERA PENDING_VALIDATION ***
(mismo tratamiento que `CLOSED_LOOP_MAX_TICKS`/`CLOSED_LOOP_CONVERGENCE_TOL`).

Sub-relajación (under-relaxation) del paso combinado: en vez de aceptar
completo el candidato de Rd que propone un tick del barórreflejo
(`run_pathological_baroreflex(..., max_ticks=1)`), el lazo se mueve solo
una FRACCIÓN `α` de la distancia hacia ese candidato --
`rd_siguiente = rd_actual + α·(rd_candidato − rd_actual)` -- ver
`run_closed_loop()`.

DIAGNÓSTICO que motivó esto (2026-08-01, "Reconocimiento" + análisis de
estabilidad): a HR alto (umbral empírico entre 95 y 98 bpm en el
escenario "healthy"), el lazo combinado entraba en un ciclo límite de
periodo 2 -- confirmado que la causa es el acoplamiento Rd->retorno
venoso->SV (`_resistance_to_venous_return_mmhg_s_ml`,
`stroke_volume_frank_starling`) DUPLICANDO la ganancia efectiva del lazo
respecto al Módulo 2 aislado (medido: dM/dRd con SV acoplada ≈2x la
dM/dRd con SV fija, en todo el rango de HR probado) -- y esa ganancia ya
duplicada cruza el umbral de estabilidad (|1-ganancia|>1) al subir el HR,
porque a HR alto el EDV de equilibrio es menor (menos tiempo de llenado),
lo que opera la curva de Frank-Starling en su tramo más empinado
(mayor dSV/dEDV local), amplificando aún más ese acoplamiento.
`BAROREFLEX_GAIN_K=1.0` (Módulo 2) quedó EXONERADO explícitamente: el
Módulo 2 aislado (SV fija) no osciló en ningún HR probado, hasta 220.

CRITERIO de α=0.5, no ajustado a ningún resultado de PA: la sub-relajación
es matemáticamente equivalente a multiplicar la ganancia efectiva por α
(`nuevo_factor = 1 - α·ganancia_original`) -- probado que NO mueve el
punto fijo (Rd_actual=Rd_candidato en el equilibrio, con o sin α, la
ecuación de equilibrio no depende de α). Se eligió α=0.5 por margen
amplio: incluso en el peor caso medido (HR=200, ganancia≈2.12), α=0.5 deja
el nuevo factor de amplificación en ≈-0.06 (muy por debajo de 1) -- a HR
más realistas el margen es todavía mayor. Efecto colateral verificado
(no buscado, pero honesto reportarlo): también acelera la convergencia en
casos que ya convergían sin oscilar (menos ticks, no solo más estables)."""

_OSCILLATION_LOOKBACK_TICKS: int = 6
_OSCILLATION_MIN_SIGN_CHANGES: int = 3


@dataclasses.dataclass(frozen=True)
class ClosedLoopTick:
    """Un tick COMBINADO -- Paso 3, instrumentación: expone cada variable
    intermedia de la cadena completa, no solo el resultado final."""

    tick: int
    rd_before: float
    p_sf_effective_mmhg: float
    rvr_mmhg_s_ml: float
    venous_return_ml_s: float
    raw_edv_ml: float
    corrected_edv_ml: float
    diastasis_ceiling_active: bool
    stroke_volume_ml: float
    rd_candidate: float  # candidato CRUDO del barórreflejo, ANTES de la sub-relajación (transparencia/auditoría)
    rd_after: float  # Rd realmente usado en el siguiente tick, DESPUÉS de la sub-relajación (CLOSED_LOOP_RELAXATION_FACTOR)
    systolic_bp: float
    diastolic_bp: float
    map: float
    clamped_at_min_rd: bool
    clamped_at_max_rd: bool


@dataclasses.dataclass(frozen=True)
class ClosedLoopResult:
    scenario: str
    heart_rate_bpm: float
    converged: bool
    oscillated: bool
    ticks: Tuple[ClosedLoopTick, ...]
    final_rd: float
    final_edv_ml: float
    final_stroke_volume_ml: float
    final_systolic_bp: float
    final_diastolic_bp: float
    final_map: float
    clamped_at_min_rd: bool
    clamped_at_max_rd: bool
    clamped_at_edv_floor: bool


def _detect_oscillation(
    ticks: List[ClosedLoopTick],
    lookback: int = _OSCILLATION_LOOKBACK_TICKS,
    min_sign_changes: int = _OSCILLATION_MIN_SIGN_CHANGES,
) -> bool:
    """Heurística simple (NO un análisis espectral riguroso, documentado
    como tal): mira los últimos `lookback` deltas de `rd_after` entre
    ticks combinados consecutivos -- si el signo alterna al menos
    `min_sign_changes` veces, se reporta oscilación, distinguiéndolo de
    una deriva monótona sin converger (p.ej. colapso progresivo hacia un
    límite, un hallazgo distinto)."""
    if len(ticks) < lookback + 1:
        return False
    recent = ticks[-(lookback + 1):]
    deltas = [recent[i + 1].rd_after - recent[i].rd_after for i in range(len(recent) - 1)]
    sign_changes = sum(1 for i in range(len(deltas) - 1) if deltas[i] * deltas[i + 1] < 0)
    return sign_changes >= min_sign_changes


def run_closed_loop(
    scenario: str,
    heart_rate_bpm: float,
    max_ticks: int = CLOSED_LOOP_MAX_TICKS,
    tol: float = CLOSED_LOOP_CONVERGENCE_TOL,
    relaxation_factor: float = CLOSED_LOOP_RELAXATION_FACTOR,
) -> ClosedLoopResult:
    """El lazo cerrado completo -- "tick virtual" stateless: TODO el
    estado (`rd_current`, `ticks`) vive en variables locales de esta
    llamada, igual que `run_baroreflex()` (Módulo 2) y
    `run_pathological_baroreflex()` (Módulo 3) -- dos invocaciones
    concurrentes no comparten nada.

    Cada tick COMBINADO recorre la cadena completa una vez: retorno
    venoso (con el Rd del tick anterior) -> EDV con techo de diástasis ->
    SV vía Frank-Starling -> UN paso del controlador proporcional del
    barórreflejo (`run_pathological_baroreflex(..., max_ticks=1)`, que ya
    incluye los overrides patológicos del escenario) -> ese candidato de
    Rd se SUB-RELAJA (`CLOSED_LOOP_RELAXATION_FACTOR`, ver su docstring
    para el diagnóstico completo) antes de aceptarse -- el Rd realmente
    usado en el siguiente tick es una fracción `α` del camino hacia el
    candidato, no el candidato completo. La presión (S/D/PAM) de este
    tick se reevalúa en el Rd YA sub-relajado (una evaluación R-RCR extra,
    `max_ticks=0` -- una sola pasada, sin ajuste), para que lo reportado
    corresponda exactamente al Rd que de verdad se lleva al tick
    siguiente, no al candidato descartado.

    Converge cuando el cambio relativo de Rd (ya sub-relajado) entre ticks
    COMBINADOS es menor que `tol`. Si no converge en `max_ticks`, se
    reporta `converged=False` con el último estado alcanzado -- no se
    lanza excepción ni se oculta: es un hallazgo fisiológico válido (shock
    descompensado / el mecanismo no logra estabilizarse), no un error de
    este código. `oscillated` distingue ese caso de una deriva monótona
    sin converger (ver `_detect_oscillation`) -- con la sub-relajación
    activa, un `oscillated=True` genuino (no solo lento) es en sí mismo un
    hallazgo, no algo esperado en el rango de HR ya verificado."""
    # Guards de "no cambiar a False sin revisión" retirados -- Ronda 2 de validación
    # cuantitativa (2026-07-31): VENOUS_RETURN_PARAMETERS_PENDING_VALIDATION (este
    # módulo) y sus dos dependencias (FRANK_STARLING_PARAMETERS_PENDING_VALIDATION,
    # DIASTASIS_CEILING_PENDING_VALIDATION) pasaron todas a False tras confirmación
    # explícita del validador -- ver docstrings de cada constante y CHANGELOG.md.

    rd_current = RD_BASE_MMHG_S_ML
    ticks: List[ClosedLoopTick] = []
    converged = False

    for i in range(max_ticks):
        p_sf_effective_mmhg, rvr_mmhg_s_ml, venous_return_ml_s, raw_edv_ml = _venous_return_step(
            heart_rate_bpm, rd_current, scenario
        )
        corrected_edv_ml = apply_diastasis_ceiling(raw_edv_ml)
        stroke_volume_ml = stroke_volume_frank_starling(corrected_edv_ml)

        base_params_this_tick = dataclasses.replace(PHYSIOLOGICAL_RRCR_PARAMETERS, rd=rd_current)
        one_tick_result = run_pathological_baroreflex(
            scenario,
            heart_rate_bpm,
            base_params=base_params_this_tick,
            sv_ref_ml=stroke_volume_ml,
            max_ticks=1,
        )
        rd_candidate = one_tick_result.final_rd

        # Sub-relajación (CLOSED_LOOP_RELAXATION_FACTOR, control numérico -- ver su
        # docstring): el paso combinado se mueve solo una fracción hacia el candidato
        # crudo del barórreflejo, no el paso completo. Matemáticamente equivalente a
        # reducir la ganancia efectiva del lazo -- NO cambia dónde converge (la
        # ecuación de equilibrio no depende de esta constante), solo cómo llega ahí.
        rd_damped = rd_current + relaxation_factor * (rd_candidate - rd_current)

        # Reevaluación de presión EN el Rd ya sub-relajado (una pasada, max_ticks=0,
        # sin ajuste adicional) -- lo reportado en este tick debe corresponder al Rd
        # que realmente se lleva al tick siguiente, no al candidato descartado.
        damped_evaluation = run_pathological_baroreflex(
            scenario,
            heart_rate_bpm,
            base_params=dataclasses.replace(PHYSIOLOGICAL_RRCR_PARAMETERS, rd=rd_damped),
            sv_ref_ml=stroke_volume_ml,
            max_ticks=0,
        )

        tick_record = ClosedLoopTick(
            tick=i,
            rd_before=rd_current,
            p_sf_effective_mmhg=p_sf_effective_mmhg,
            rvr_mmhg_s_ml=rvr_mmhg_s_ml,
            venous_return_ml_s=venous_return_ml_s,
            raw_edv_ml=raw_edv_ml,
            corrected_edv_ml=corrected_edv_ml,
            diastasis_ceiling_active=raw_edv_ml > EDV_HEALTHY_ML * (1.0 + 1e-9),
            stroke_volume_ml=stroke_volume_ml,
            rd_candidate=rd_candidate,
            rd_after=rd_damped,
            systolic_bp=damped_evaluation.final_systolic_bp,
            diastolic_bp=damped_evaluation.final_diastolic_bp,
            map=damped_evaluation.final_map,
            # Clamping se lee del CANDIDATO crudo (one_tick_result), no del Rd ya
            # amortiguado: refleja si el controlador proporcional está COMANDANDO
            # saturación (querer ir más allá del límite), que es la señal fisiológica
            # relevante ("el reflejo está saturado"). El Rd amortiguado se acerca al
            # límite de forma asintótica y en general NUNCA lo toca exactamente dentro
            # de la ventana de convergencia -- comparar el clamp contra el valor ya
            # amortiguado subestimaría la saturación (verificado con sepsis: el
            # candidato queda clavado en max_rd desde el tick 2, pero el Rd amortiguado
            # solo se acerca a ~99.994% de max_rd al converger).
            clamped_at_min_rd=one_tick_result.clamped_at_min,
            clamped_at_max_rd=one_tick_result.clamped_at_max,
        )
        ticks.append(tick_record)

        if abs(rd_damped - rd_current) <= tol * max(rd_current, 1e-9):
            rd_current = rd_damped
            converged = True
            break
        rd_current = rd_damped

    last = ticks[-1]
    oscillated = (not converged) and _detect_oscillation(ticks)

    return ClosedLoopResult(
        scenario=scenario,
        heart_rate_bpm=heart_rate_bpm,
        converged=converged,
        oscillated=oscillated,
        ticks=tuple(ticks),
        final_rd=last.rd_after,
        final_edv_ml=last.corrected_edv_ml,
        final_stroke_volume_ml=last.stroke_volume_ml,
        final_systolic_bp=last.systolic_bp,
        final_diastolic_bp=last.diastolic_bp,
        final_map=last.map,
        clamped_at_min_rd=last.clamped_at_min_rd,
        clamped_at_max_rd=last.clamped_at_max_rd,
        clamped_at_edv_floor=last.corrected_edv_ml <= EDV_FLOOR_ML * (1.0 + 1e-9),
    )


# --- Paso 3: instrumentación -- traza tick a tick --------------------------------


def _print_trace(result: ClosedLoopResult) -> None:
    print(
        f"\n=== Lazo cerrado -- escenario={result.scenario!r}  HR={result.heart_rate_bpm:.0f} bpm ==="
    )
    print(
        f"converged={result.converged}  oscillated={result.oscillated}  "
        f"ticks={len(result.ticks)}  clamped_min_rd={result.clamped_at_min_rd}  "
        f"clamped_max_rd={result.clamped_at_max_rd}  clamped_edv_floor={result.clamped_at_edv_floor}"
    )
    header = (
        f"{'tick':<5}{'Rd antes':<10}{'P_sf ef.':<10}{'RVR':<10}{'retorno mL/s':<14}"
        f"{'EDV crudo':<11}{'EDV corr.':<11}{'SV':<8}{'Rd candidato':<14}{'Rd después':<12}{'PAM':<8}"
    )
    print(header)
    for t in result.ticks:
        print(
            f"{t.tick:<5}{t.rd_before:<10.4f}{t.p_sf_effective_mmhg:<10.2f}{t.rvr_mmhg_s_ml:<10.4f}"
            f"{t.venous_return_ml_s:<14.2f}{t.raw_edv_ml:<11.1f}{t.corrected_edv_ml:<11.1f}"
            f"{t.stroke_volume_ml:<8.1f}{t.rd_candidate:<14.4f}{t.rd_after:<12.4f}{t.map:<8.2f}"
        )
    print(
        f"Final: SV={result.final_stroke_volume_ml:.1f} mL  EDV={result.final_edv_ml:.1f} mL  "
        f"PA={result.final_systolic_bp:.1f}/{result.final_diastolic_bp:.1f}  PAM={result.final_map:.1f} mmHg"
    )


if __name__ == "__main__":
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    for scenario_value, heart_rate in (("healthy", 72.0), ("hypertension", 85.0), ("sepsis", 150.0)):
        _print_trace(run_closed_loop(scenario_value, heart_rate))
