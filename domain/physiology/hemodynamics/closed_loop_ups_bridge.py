"""
Conexión al UPS — los 3 escenarios validados, en coexistencia (2026-08-01).

El paso final de "La película": el motor hemodinámico de lazo cerrado
(`closed_loop.py`) escribe por PRIMERA VEZ al UPS real. Todo lo anterior
(Módulos 1-3, eslabón 1, Módulo 4B-i/ii, Rondas 1-2 de validación
cuantitativa, estabilidad numérica) vivió aislado -- comparado contra el
UPS, nunca conectado a él. Máxima cautela: este puente es deliberadamente
más estrecho que el motor que envuelve.

*** PASO 1 -- RESTRICCIÓN ESTRUCTURAL, NO UN IF EVITABLE ***
`HEMODYNAMIC_MODEL_ENABLED_SCENARIOS` es la única fuente de verdad de qué
escenarios pueden recibir PA calculada. `compute_and_attach_closed_loop_pressure()`
la consulta en su primera línea y **lanza** `HemodynamicModelNotEnabledError`
(no retorna `None` silenciosamente, no omite en silencio) para cualquier
escenario fuera de la lista -- imposible de sortear sin editar este
archivo a propósito. No hay una segunda ruta de código que llame a
`run_closed_loop()` y persista sin pasar por este guard.

Los otros 9 escenarios (`SimulationScenario`, 12 en total) NO reciben PA
calculada todavía, cada uno con su razón propia (ver "Reconocimiento",
2026-08-01, y "Estabilidad del lazo a HR alto", misma fecha):

- `exercise`: BLOQUEADO por un bug ajeno al lazo -- `_simulate_exercise()`
  (`app/engines/simulation_engine.py`) no acota `recovery_progress` a
  [0,1]; en el horizonte de 7 días produce heart_rate=-14580 bpm. El lazo
  cerrado rechaza correctamente ese valor (`ValueError`), pero no hay HR
  válido que darle todavía.
- `stress`, `anxiety`: la `ClinicalReferenceValue` de ambos es un PICO
  AGUDO transitorio de descarga simpática (207.5 mmHg, "no representa un
  valor sostenido") -- el lazo cerrado, por diseño, solo modela equilibrio
  ESTACIONARIO. No hay forma honesta de comparar un punto fijo contra un
  transitorio que el motor no representa.
- `apnea`, `seizure`: mismatch de FASE -- el heart_rate del último
  snapshot (horizonte 7 días) refleja un estado recuperado/basal, no la
  fase aguda (arousal post-apnea / ictal) que describe la referencia
  citada de cada uno.
- `arrhythmia`: falta un driver de efectividad de bombeo reducida (pérdida
  de contribución auricular, latido irregular) -- el barórreflejo
  normaliza la PA en vez de reproducir la descompensación hipotensiva real
  (PAM referencia 70 mmHg; el lazo da ~93).
- `hypoxia`: falta un driver quimiorreceptor de presión (reseteo por
  hipoxia, análogo al que hipertensión ya tiene para el barostato) -- el
  lazo normaliza en vez de mostrar la hipertensión reactiva compensatoria
  de la referencia (PAM 106.67 mmHg).
- `fatigue`, `copd`: sin `ClinicalReferenceValue` con cita (el usuario
  nunca dio fuente) -- nada contra qué validar un punto fijo, y ninguno
  de los dos fue objeto de validación experta explícita del punto fijo en
  sí (a diferencia de sano/hipertensión/sepsis).

*** PASO 2 -- CONFIANZA: VALIDADO, PERO SIGUE SIENDO UN CÁLCULO DE MODELO ***
`HEMODYNAMIC_MODEL_VALIDATED_CONFIDENCE=0.75` -- ver criterio completo
junto a la constante. Solo aplica a los 3 escenarios habilitados; un
escenario futuro conectado sin la misma validación debe usar una
confianza menor (banda 0.30-0.80 de `MODELO_HEMODINAMICO`, ver
`domain/physiology/state/schema.py`).

*** PASO 3 -- COEXISTENCIA ***
`compute_and_attach_closed_loop_pressure()` usa `append_descriptors()`
(mismo mecanismo que el puente original del Módulo 1,
`ups_bridge.py::compute_and_attach_calculated_pressure`) -- adjunta al
snapshot YA EXISTENTE, nunca crea uno nuevo, nunca borra ni sobrescribe
la `ClinicalReferenceValue` que `run_rich_scenario()` ya adjuntó al mismo
snapshot. Ambas conviven, cada una con su procedencia (`MODELO_HEMODINAMICO`
vs. la ausencia de banda de confianza numérica de `REFERENCIA_CLINICA`).

Nombres de descriptor reutilizados de `ups_bridge.py`
(`systolic_bp_modelo`/`diastolic_bp_modelo`/`map_modelo`) -- mismo
significado (PA calculada por un modelo hemodinámico), ahora vía el lazo
cerrado validado en vez del R-RCR estático del Módulo 1. Sin colisión de
rutas: el puente original nunca se invoca desde la app viva (confirmado
por grep antes de esta tanda), así que solo una ruta escribe estos
nombres en el UPS real."""

from __future__ import annotations

from typing import FrozenSet, Optional

from sqlalchemy.orm import Session

from .closed_loop import ClosedLoopResult, run_closed_loop
from ..state.repository import append_descriptors
from ..state.schema import PhysiologicalDescriptor, Provenance

__all__ = [
    "HEMODYNAMIC_MODEL_ENABLED_SCENARIOS",
    "HEMODYNAMIC_MODEL_VALIDATED_CONFIDENCE",
    "HemodynamicModelNotEnabledError",
    "compute_and_attach_closed_loop_pressure",
]

# --- Paso 1: restricción estructural a los 3 escenarios validados --------------

HEMODYNAMIC_MODEL_ENABLED_SCENARIOS: FrozenSet[str] = frozenset({"healthy", "hypertension", "sepsis"})
"""Única fuente de verdad de qué escenarios reciben PA calculada. Ver el
docstring del módulo para la razón específica de cada uno de los otros 9
escenarios excluidos. Cambiar esta lista es una decisión deliberada, no
un ajuste incidental -- añadir un escenario aquí sin haberlo pasado antes
por su propia validación experta (como sano/hipertensión/sepsis) sería
exactamente el error que esta restricción existe para prevenir."""


class HemodynamicModelNotEnabledError(ValueError):
    """Se lanza -- nunca se absorbe en silencio -- cuando se pide PA
    calculada para un escenario fuera de `HEMODYNAMIC_MODEL_ENABLED_SCENARIOS`.
    No hay una ruta alterna que la evite: es la ÚNICA función de este
    paquete que persiste PA del lazo cerrado al UPS, y esta es su primera
    comprobación."""


# --- Paso 2: confianza -- validado, pero sigue siendo un cálculo de modelo -----

HEMODYNAMIC_MODEL_VALIDATED_CONFIDENCE: float = 0.75
"""CRITERIO: punto medio redondo del rango 0.70-0.80 (validación
experta + verificación de estabilidad numérica completas para estos 3
escenarios específicos). Por ENCIMA del techo original de
`MODELO_HEMODINAMICO` no validado (0.55) -- ya no es "un cálculo con
parámetros pendientes sin revisar en contexto". Por DEBAJO del piso de
`SENSOR_REAL` (0.85) -- sigue sin ser una medición. Se posiciona dentro
del rango de `SIMULACION` (0.60-0.90) sin alcanzar su techo (0.90):
epistemológicamente comparable a una lectura simulada del organismo, pero
nunca más confiable que una -- es un cálculo derivado de heart_rate (real,
vía `run_rich_scenario`) a través de un modelo con al menos un parámetro
todavía no citable (la compliancia `C=0.807`, pendiente ESTRUCTURAL, y el
umbral heurístico `VENOUS_CAPACITANCE_SEPSIS_MULTIPLIER`, aceptado pero no
citado -- ver Ronda 2 de validación cuantitativa). Esa deuda pendiente
específica es exactamente lo que impide llegar a 0.80+ o cruzar hacia la
banda de SENSOR_REAL."""


def compute_and_attach_closed_loop_pressure(
    session: Session,
    snapshot_id: str,
    scenario: str,
    heart_rate_bpm: float,
    source_detail: Optional[str] = None,
) -> ClosedLoopResult:
    """Corre el lazo cerrado (`run_closed_loop`, sin modificar) y persiste
    S/D/PAM como tres `PhysiologicalDescriptor` con
    `Provenance.MODELO_HEMODINAMICO`, adjuntos al `snapshot_id` YA
    EXISTENTE -- coexiste con la `ClinicalReferenceValue` del mismo
    snapshot (si la hay), sin sobrescribir nada.

    Lanza `HemodynamicModelNotEnabledError` -- de inmediato, antes de
    calcular nada -- si `scenario` no está en
    `HEMODYNAMIC_MODEL_ENABLED_SCENARIOS`. Esta es la restricción
    estructural del Paso 1: no hay forma de persistir PA calculada para un
    escenario no habilitado a través de esta función."""
    if scenario not in HEMODYNAMIC_MODEL_ENABLED_SCENARIOS:
        raise HemodynamicModelNotEnabledError(
            f"El escenario {scenario!r} no está en HEMODYNAMIC_MODEL_ENABLED_SCENARIOS "
            f"({sorted(HEMODYNAMIC_MODEL_ENABLED_SCENARIOS)}) -- ver docstring del módulo para "
            "la razón específica por la que este escenario todavía no está conectado al UPS. "
            "No se calculó ni se persistió nada."
        )

    result = run_closed_loop(scenario, heart_rate_bpm)

    citation_detail = (
        f"{source_detail + ' | ' if source_detail else ''}"
        f"modulo:lazo_cerrado_validado | escenario:{scenario} | "
        f"convergió={result.converged} en {len(result.ticks)} ticks | "
        "confianza=0.75 (validado Rondas 1-2 + estabilidad numérica, no una medición)"
    )

    descriptors = [
        PhysiologicalDescriptor(
            "systolic_bp_modelo", result.final_systolic_bp, "mmHg",
            Provenance.MODELO_HEMODINAMICO, HEMODYNAMIC_MODEL_VALIDATED_CONFIDENCE, citation_detail,
        ),
        PhysiologicalDescriptor(
            "diastolic_bp_modelo", result.final_diastolic_bp, "mmHg",
            Provenance.MODELO_HEMODINAMICO, HEMODYNAMIC_MODEL_VALIDATED_CONFIDENCE, citation_detail,
        ),
        PhysiologicalDescriptor(
            "map_modelo", result.final_map, "mmHg",
            Provenance.MODELO_HEMODINAMICO, HEMODYNAMIC_MODEL_VALIDATED_CONFIDENCE, citation_detail,
        ),
    ]
    append_descriptors(session, snapshot_id=snapshot_id, domain="cardiovascular", descriptors=descriptors)

    return result
