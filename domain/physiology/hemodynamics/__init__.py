"""
"La película" — modelo hemodinámico dinámico, Fase 0 / vertical slice
(2026-07-19), conectado al UPS en Paso 2 (mismo día).

Primer módulo: R→RCR (resistencia de Poiseuille en serie con un Windkessel
de 3 elementos), el caso de prueba más elemental del propio proyecto
svZeroDSolver que produce presión dinámica real -- presión = f(resistencia,
compliancia, flujo). Ver `r_rcr.py` para la verificación matemática contra
la referencia oficial (parámetros del caso de prueba, sin escala
fisiológica real), y `THIRD_PARTY_NOTICES.md` para la atribución de
licencia.

Paso 2 (conexión al UPS) añade dos piezas nuevas, deliberadamente
separadas del `r_rcr.py` ya validado:
- `physiological_flow.py` -- segundo set de parámetros R/Rp/Rd/C en
  unidades fisiológicas reales (mmHg/mL/s), PENDIENTE DE VALIDACIÓN
  EXPERTA, y el flujo de entrada derivado de `heart_rate` real del UPS +
  una constante de volumen sistólico citada (no del organismo, que la
  tiene fingida).
- `ups_bridge.py` -- calcula la PA y la persiste en el UPS con
  `Provenance.MODELO_HEMODINAMICO`, coexistiendo con la PA de referencia
  clínica (`ClinicalReferenceValue`) sin sobrescribirla.
- `context_comparison.py` -- Paso 3: corre un escenario y muestra ambas
  PA (calculada vs. referencia) lado a lado para verificación en contexto.

Módulo 2 (2026-07-20), resistencia vascular dinámica -- barórreflejo:
- `physiological_flow.py` -- Paso 1 de esta tanda recalibró la R base
  (y C) del módulo 1 (ver docstring "Paso 1, recalibración"), ancla
  "sano" ahora en 113.3/73.3/93.3 mmHg (antes: 97.9/74.3/86.1).
- `baroreflex.py` -- `run_baroreflex()`: controlador proporcional que
  modula Rd (mecanismo del barórreflejo CITADO, Guyton Cap. 18; ganancia
  k/límites/target_map son estimaciones del validador,
  PENDING_QUANTITATIVE_VALIDATION). Un solo `target_map` fijo para todos
  los escenarios (salvaguarda anti-circularidad explícita). Bucle de
  convergencia "tick virtual" -- vive en variables locales de cada
  llamada, sin estado compartido entre peticiones.
- `baroreflex_comparison.py` -- Paso 4: compara, para un escenario, PA de
  resistencia fija (módulo 1) vs. dinámica (módulo 2) vs. referencia
  clínica. No persiste nada nuevo en el UPS -- deliberadamente aislado,
  "validado en contexto antes de conectar a más escenarios".

Módulo 3 (2026-07-23), tono vascular alterable por patología:
- `pathological_tone.py` -- `run_pathological_baroreflex(scenario, hr)`:
  dos mecanismos DISTINTOS y citados por separado. Hipertensión → reseteo
  del barostato (Guyton Cap. 18): solo `target_map` sube, el efector
  queda intacto. Sepsis → vasoplejía/fallo del efector (Marino, The ICU
  Book): `target_map` NO cambia (el cuerpo sigue queriendo normalizar
  93.33 mmHg), lo que cae es `max_rd` (techo de vasoconstricción, 0.5x) y
  la ganancia efectiva `k` (0.3x). Magnitudes marcadas
  `PATHOLOGICAL_TONE_PENDING_VALIDATION`, elegidas con criterio
  INDEPENDIENTE de la referencia clínica de cada escenario (salvaguarda
  anti-circularidad reforzada, ver docstring del módulo). Escenarios sin
  mecanismo definido son pass-through exacto a `run_baroreflex()`.
- `pathological_tone_comparison.py` -- compara, para un escenario, la PA
  del Módulo 2 (sin patología) vs. Módulo 3 (con patología) vs.
  referencia clínica, como control de calidad independiente. No persiste
  nada nuevo en el UPS -- mismo aislamiento que `baroreflex_comparison.py`.

Módulo 4, eslabón 1 (2026-07-24), volumen sistólico dinámico vía
Frank-Starling:
- `frank_starling.py` -- `stroke_volume_frank_starling(edv_ml)`: SV=f(EDV)
  como curva saturante (mecanismo citado, Guyton Cap. 9/20/24; techo/piso/
  constante de forma marcados `FRANK_STARLING_PARAMETERS_PENDING_VALIDATION`,
  resueltos contra el ancla ya citada SV_ref=70mL/EDV_healthy=120mL, nunca
  contra una PA de referencia). El retorno venoso que alimenta el EDV es
  un ANDAMIAJE TEMPORAL declarado sin ambigüedad
  (`estimate_edv_venous_return_placeholder_pending_module_4b`,
  `VENOUS_RETURN_PLACEHOLDER_PENDING_MODULE_4B=True`) -- reemplazado
  cuando el Módulo 4B modele retorno venoso real (capacitancia venosa,
  P_sf). Repara la deuda del SV fijo (existe una función real, probada);
  NO conecta este SV dinámico al R-RCR todavía (`physiological_flow.py`
  sin tocar) -- lazo completo diferido a un eslabón posterior, tal como
  fue instruido.

Módulo 4B-i (2026-07-27), techo diastólico (diástasis):
- `diastasis_ceiling.py` -- corrige el artefacto del placeholder de
  retorno venoso (EDV se disparaba a 216 mL a 40 bpm, sin límite).
  `apply_diastasis_ceiling()` aplana el EDV crudo hacia un techo
  anatómico (mecanismo citado -- Guyton, curva de distensibilidad
  ventricular/fase de diástasis; `EDV_ANATOMICAL_CEILING_ML=180`
  marcado `DIASTASIS_CEILING_PENDING_VALIDATION`, criterio 1.5x el
  ancla). Identidad para EDV crudo <= `EDV_HEALTHY_ML` -- el ancla de
  reposo (72bpm->120mL->70mL) queda intacta. NO modifica
  `frank_starling.py` (envuelve, no reemplaza -- mismo patrón que
  `pathological_tone.py` alrededor de `baroreflex.py`); NO reemplaza el
  placeholder de retorno venoso todavía (eso es Módulo 4B-ii); NO cierra
  el lazo con el R-RCR.

Módulo 4B-ii (2026-07-30), retorno venoso real + CIERRE DEL LAZO -- el
clímax de esta serie:
- `closed_loop.py` -- reemplaza el placeholder de retorno venoso por uno
  real (P_sf/RVR, mecanismo citado -- Guyton Cap. 20/24) y cierra la
  cadena completa: retorno venoso -> EDV (techo de diástasis, Módulo
  4B-i) -> SV (Frank-Starling, eslabón 1) -> flujo -> R-RCR -> presión ->
  barórreflejo (Módulo 2/3) -> resistencia -> de vuelta al retorno.
  `run_closed_loop(scenario, heart_rate_bpm)` -- tick virtual stateless,
  reutiliza `run_pathological_baroreflex(..., max_ticks=1)` para un paso
  del controlador por tick combinado, sin reimplementar física. Parámetros
  nuevos (`P_SF_HEALTHY_MMHG`, `VENOUS_CAPACITANCE_SEPSIS_MULTIPLIER`,
  `RVR_REFERENCE_MMHG_S_ML`) marcados
  `VENOUS_RETURN_PARAMETERS_PENDING_VALIDATION`, fijados independientes
  de cualquier PA de referencia (salvaguarda anti-circularidad máxima,
  ver docstring del módulo, incluida la elección documentada del signo
  del acoplamiento resistencia->retorno). Conexión ESTRUCTURAL (no
  hardcodeada) con la vasoplejía de sepsis del Módulo 3. Instrumentación
  completa: `ClosedLoopResult.ticks` expone la traza tick-a-tick de cada
  variable intermedia.
- `closed_loop_comparison.py` -- verificación en contexto: PA del lazo
  cerrado vs. `ClinicalReferenceValue`, mismo aislamiento que
  `baroreflex_comparison.py`/`pathological_tone_comparison.py` (no
  persiste nada nuevo en el UPS).
- Hallazgo central: con los mismos parámetros fijados a ciegas, sepsis
  colapsa hacia el shock (PAM final muy por debajo de 65 mmHg) mientras
  hipertensión encuentra un equilibrio elevado estable, sin chocar
  límites -- ver CHANGELOG.md para el detalle completo, incluida la
  dirección de acoplamiento descartada por producir un colapso universal
  no específico de escenario.

Conexión al UPS (2026-08-01) -- el paso final, primera escritura real del
motor al UPS:
- `closed_loop_ups_bridge.py` -- `compute_and_attach_closed_loop_pressure(session,
  snapshot_id, scenario, heart_rate_bpm)`: PA calculada por `run_closed_loop`
  (sin modificar), persistida con `Provenance.MODELO_HEMODINAMICO`, en
  coexistencia con `ClinicalReferenceValue` (ninguna sobrescribe a la
  otra). Restricción ESTRUCTURAL a `HEMODYNAMIC_MODEL_ENABLED_SCENARIOS`
  ({healthy, hypertension, sepsis} -- los únicos 3 con validación experta
  completa) -- lanza `HemodynamicModelNotEnabledError` para cualquier otro
  escenario, sin ruta alterna que lo evite. Confianza
  `HEMODYNAMIC_MODEL_VALIDATED_CONFIDENCE=0.75` (banda de
  `MODELO_HEMODINAMICO` ensanchada a 0.30-0.80 en `domain/physiology/state/schema.py`
  para darle espacio a este régimen validado sin inventar una segunda
  procedencia -- el puente original del Módulo 1, `ups_bridge.py`,
  preserva su 0.425 histórico sin cambios). Narrador (`narrator/prompt.py`)
  actualizado para declarar `modelo_hemodinamico` honestamente como cálculo
  de modelo, no medición. Modelo de riesgo (`ml/risk_context.py`) sigue
  usando la referencia clínica, no la PA calculada -- decisión explícita,
  documentada en su propio módulo.

Sigue sin tocar `domain/physiology/coupling/` -- no lee estos descriptores
todavía.
"""

from .baroreflex import (
    BAROREFLEX_CONVERGENCE_TOL,
    BAROREFLEX_GAIN_K,
    BAROREFLEX_MAX_RD,
    BAROREFLEX_MAX_TICKS,
    BAROREFLEX_MECHANISM_CITATION,
    BAROREFLEX_MIN_RD,
    BAROREFLEX_PARAMETERS_PENDING_VALIDATION,
    BAROREFLEX_TARGET_MAP_MMHG,
    BaroreflexResult,
    BaroreflexTick,
    run_baroreflex,
)
from .baroreflex_comparison import BaroreflexComparison, run_scenario_baroreflex_comparison
from .context_comparison import PressureComparison, run_scenario_pressure_comparison
from .physiological_flow import (
    PHYSIOLOGICAL_PARAMETERS_CITATION,
    PHYSIOLOGICAL_PARAMETERS_PENDING_VALIDATION,
    PHYSIOLOGICAL_RRCR_PARAMETERS,
    STROKE_VOLUME_CITATION,
    STROKE_VOLUME_REFERENCE_ML,
    physiological_pulsatile_flow,
)
from .r_rcr import (
    OFFICIAL_PULSATILE_T0_CHECKPOINT,
    OFFICIAL_STEADY_CHECKPOINT,
    RRCRParameters,
    RRCRResult,
    pulsatile_flow_reference,
    simulate_r_rcr,
    steady_flow_reference,
)
from .pathological_tone import (
    HYPERTENSION_RESET_CITATION,
    HYPERTENSION_RESET_TARGET_MAP_MMHG,
    PATHOLOGICAL_TONE_OVERRIDES,
    PATHOLOGICAL_TONE_PENDING_VALIDATION,
    SEPSIS_GAIN_K,
    SEPSIS_MAX_RD_MMHG_S_ML,
    SEPSIS_VASOPLEGIA_CITATION,
    PathologicalToneOverride,
    run_pathological_baroreflex,
)
from .pathological_tone_comparison import PathologicalToneComparison, run_scenario_pathological_tone_comparison
from .frank_starling import (
    EDV_FLOOR_ML,
    EDV_HEALTHY_ML,
    FRANK_STARLING_MECHANISM_CITATION,
    FRANK_STARLING_PARAMETERS_PENDING_VALIDATION,
    FRANK_STARLING_STEEPNESS_ML,
    HEART_RATE_ANCHOR_BPM,
    SV_MAX_ML,
    VALIDATOR_SEPSIS_SV_ESTIMATE_RANGE_ML,
    VENOUS_RETURN_PLACEHOLDER_PENDING_MODULE_4B,
    FrankStarlingResult,
    compute_dynamic_stroke_volume,
    estimate_edv_venous_return_placeholder_pending_module_4b,
    stroke_volume_frank_starling,
    stroke_volume_table,
)
from .diastasis_ceiling import (
    DIASTASIS_CEILING_PENDING_VALIDATION,
    DIASTASIS_MECHANISM_CITATION,
    DIASTASIS_TRANSITION_BUDGET_ML,
    EDV_ANATOMICAL_CEILING_ML,
    DiastasisCorrectedResult,
    apply_diastasis_ceiling,
    compute_dynamic_stroke_volume_with_diastasis_ceiling,
    estimate_edv_with_diastasis_ceiling,
    stroke_volume_table_with_diastasis_ceiling,
)
from .closed_loop import (
    CLOSED_LOOP_CONVERGENCE_TOL,
    CLOSED_LOOP_MAX_TICKS,
    CLOSED_LOOP_RELAXATION_FACTOR,
    P_SF_HEALTHY_MMHG,
    RD_BASE_MMHG_S_ML,
    RVR_REFERENCE_MMHG_S_ML,
    VENOUS_CAPACITANCE_SEPSIS_MULTIPLIER,
    VENOUS_RETURN_MECHANISM_CITATION,
    VENOUS_RETURN_PARAMETERS_PENDING_VALIDATION,
    ClosedLoopResult,
    ClosedLoopTick,
    run_closed_loop,
)
from .closed_loop_comparison import ClosedLoopComparison, run_scenario_closed_loop_comparison
from .closed_loop_ups_bridge import (
    HEMODYNAMIC_MODEL_ENABLED_SCENARIOS,
    HEMODYNAMIC_MODEL_VALIDATED_CONFIDENCE,
    HemodynamicModelNotEnabledError,
    compute_and_attach_closed_loop_pressure,
)
from .ups_bridge import compute_and_attach_calculated_pressure, compute_calculated_pressure

__all__ = [
    "RRCRParameters",
    "RRCRResult",
    "simulate_r_rcr",
    "steady_flow_reference",
    "pulsatile_flow_reference",
    "OFFICIAL_STEADY_CHECKPOINT",
    "OFFICIAL_PULSATILE_T0_CHECKPOINT",
    "STROKE_VOLUME_REFERENCE_ML",
    "STROKE_VOLUME_CITATION",
    "PHYSIOLOGICAL_RRCR_PARAMETERS",
    "PHYSIOLOGICAL_PARAMETERS_CITATION",
    "PHYSIOLOGICAL_PARAMETERS_PENDING_VALIDATION",
    "physiological_pulsatile_flow",
    "compute_calculated_pressure",
    "compute_and_attach_calculated_pressure",
    "PressureComparison",
    "run_scenario_pressure_comparison",
    "BAROREFLEX_MECHANISM_CITATION",
    "BAROREFLEX_PARAMETERS_PENDING_VALIDATION",
    "BAROREFLEX_GAIN_K",
    "BAROREFLEX_MIN_RD",
    "BAROREFLEX_MAX_RD",
    "BAROREFLEX_TARGET_MAP_MMHG",
    "BAROREFLEX_MAX_TICKS",
    "BAROREFLEX_CONVERGENCE_TOL",
    "BaroreflexTick",
    "BaroreflexResult",
    "run_baroreflex",
    "BaroreflexComparison",
    "run_scenario_baroreflex_comparison",
    "HYPERTENSION_RESET_CITATION",
    "HYPERTENSION_RESET_TARGET_MAP_MMHG",
    "SEPSIS_VASOPLEGIA_CITATION",
    "SEPSIS_MAX_RD_MMHG_S_ML",
    "SEPSIS_GAIN_K",
    "PATHOLOGICAL_TONE_PENDING_VALIDATION",
    "PathologicalToneOverride",
    "PATHOLOGICAL_TONE_OVERRIDES",
    "run_pathological_baroreflex",
    "PathologicalToneComparison",
    "run_scenario_pathological_tone_comparison",
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
    "DIASTASIS_MECHANISM_CITATION",
    "DIASTASIS_CEILING_PENDING_VALIDATION",
    "EDV_ANATOMICAL_CEILING_ML",
    "DIASTASIS_TRANSITION_BUDGET_ML",
    "DiastasisCorrectedResult",
    "apply_diastasis_ceiling",
    "estimate_edv_with_diastasis_ceiling",
    "compute_dynamic_stroke_volume_with_diastasis_ceiling",
    "stroke_volume_table_with_diastasis_ceiling",
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
    "ClosedLoopComparison",
    "run_scenario_closed_loop_comparison",
    "HEMODYNAMIC_MODEL_ENABLED_SCENARIOS",
    "HEMODYNAMIC_MODEL_VALIDATED_CONFIDENCE",
    "HemodynamicModelNotEnabledError",
    "compute_and_attach_closed_loop_pressure",
]
