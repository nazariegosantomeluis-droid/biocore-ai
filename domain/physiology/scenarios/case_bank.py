"""
Banco de casos clínicos sintéticos — capa "casos" del módulo de aprendizaje.

Genera variaciones honestas de los 12 escenarios reales del
`SimulationEngine` reutilizando `run_rich_scenario` (`rich_engine.py`) sin
tocar el motor. Ningún patrón nuevo: la lista de patrones posibles es
exactamente `available_rich_scenarios()` (los 12 miembros de
`SimulationScenario`) — generar un caso de una patología que el simulador
no modela violaría el Art. I de la Constitución (fisiología fingida).

Tres ejes de variación, todos reales (nada inventado numéricamente):
1. Estado inicial: jitter dentro de rango fisiológico normal de reposo
   (`_BASELINE_JITTER`) antes de correr el escenario — dos pacientes sanos
   no comparten la misma FC de reposo. El escenario luego evoluciona ese
   punto de partida con su propia lógica real (`SimulationEngine`), sin
   alterarla.
2. Punto de la evolución: se elige al azar uno de los horizontes reales que
   el propio motor calcula (now/5min/30min/2h/24h/7d) como snapshot del
   caso -- SOLO entre los que la matriz de evaluabilidad (Trabajo 2, Fase 0,
   2026-08-06) midió característicos para ese escenario específico, nunca
   fijo al último. Ver `EVALUABLE_HORIZONS_BY_SCENARIO`: algunos escenarios
   (convulsión, ejercicio, estrés, ansiedad, hipoxia) revierten a un estado
   indistinguible de sano más allá de cierto horizonte; esos horizontes
   quedan excluidos de la generación por construcción, no por filtro
   evitable. (Ejercicio: hasta el Bloque 4, 2026-08-10, revertía a valores
   físicamente imposibles en vez de a un estado indistinguible -- ver
   `EVALUABLE_HORIZONS_BY_SCENARIO["exercise"]` para el detalle; la
   restricción de horizontes no cambió, cambió la razón.)
3. Ruido: el que `SimulationEngine` ya aplica sin semilla en cada corrida
   (gaussiano, no controlado por este módulo) — gratis, ya presente.

No hay una perilla de "severidad": `SimulationEngine.SCENARIO_PARAMETERS`
no la expone como parámetro (solo trae etiquetas descriptivas internas de
cada `_simulate_*`, no configurables desde fuera). Simular severidad de
verdad requeriría extender `app/engines/simulation_engine.py` — fuera de
alcance de este banco, que solo reutiliza el motor tal cual existe hoy.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Optional

from sqlalchemy.orm import Session

from app.engines.digital_twin_organism import DigitalTwinOrganism
from app.engines.simulation_engine import SimulationScenario
from domain.physiology.state import (
    PhysiologicalEvent,
    Provenance,
    UnifiedPhysiologicalState,
    get_events,
)

from .rich_engine import available_rich_scenarios, create_ephemeral_case_patient, run_rich_scenario

__all__ = ["ClinicalCase", "EVALUABLE_HORIZONS_BY_SCENARIO", "generate_case"]

_HORIZON_LABELS = ["now", "5min", "30min", "2h", "24h", "7d"]
_ALL_HORIZONS: FrozenSet[str] = frozenset(_HORIZON_LABELS)

# Trabajo 2, Fase 1 (2026-08-06) -- restricción ESTRUCTURAL de qué horizontes
# puede mostrar un caso generado, por escenario. Basada en la matriz medida
# (Fase 0, misma fecha, ver CHANGELOG.md): para cada uno de los 12
# escenarios, se corrió `SimulationEngine().simulate_scenario()` real y se
# comparó cada uno de los 6 horizontes contra la banda de ruido real de
# "sano" en ese mismo horizonte. Un horizonte "colapsado" (indistinguible de
# sano, o con valores físicamente imposibles) generaría un caso sin
# respuesta discernible -- el estudiante adivinaría, no diagnosticaría.
#
# Los escenarios que NO aparecen aquí explícitamente (sano, arritmia,
# sepsis, hipertensión, fatiga, apnea, EPOC) fueron medidos EVALUABLES en
# los 6 horizontes -- caen al default `_ALL_HORIZONS` vía `.get()` más abajo,
# sin restricción.
#
# Apnea y EPOC (Fase 2, 2026-08-12 -- fisiología real, ver CHANGELOG.md):
# hasta entonces mostraban una fase parcial fija (nunca arousal en apnea,
# fórmula con `%1` sobre enteros, matemáticamente inalcanzable; nunca
# exacerbación en EPOC, ningún horizonte muestreado caía en la ventana de
# 4h) -- pero YA eran evaluables igual (se distinguían de sano con margen
# claro, aunque mostraran una fase incompleta). Con el arreglo, ambos
# escenarios producen ahora un estado ÚNICO, determinista y sostenido en
# los 6 horizontes -- apnea como foto del evento apneico crítico (SpO2 82,
# HR 55, AHI 45) y EPOC como exacerbación sostenida (SpO2 85, HR 95, RR 28,
# sin el ciclo de 4h) -- medido de nuevo tras el arreglo: ambos siguen
# claramente fuera de la banda de sano en los 6 horizontes (ningún cambio
# de restricción necesario, la evaluabilidad no empeoró ni mejoró de forma
# que exija ajustar esta entrada).
EVALUABLE_HORIZONS_BY_SCENARIO: Dict[str, FrozenSet[str]] = {
    # `_simulate_seizure` solo ejecuta la fase ictal si minutes<5 -- de los 6
    # horizontes muestreados, únicamente "now" (minutes=0) califica. Medido:
    # "5min" ya devuelve _simulate_healthy() completo (HR=72.9, SpO2=97.8,
    # riesgo=5.0 -- indistinguible de sano). Los 5 restantes son el mismo caso.
    "seizure": frozenset({"now"}),
    # Bloque 4 (2026-08-10): `recovery_progress = (minutes-30)/60` se acotó a
    # [0,1] en `_simulate_exercise()` -- antes, sin acotar, "2h" daba HR=28
    # (undershoot sin sentido), "24h" HR=-1908, "7d" HR=-14580 (valores
    # físicamente imposibles). Esa era la razón original de esta entrada.
    # Con el arreglo, medido de nuevo: "2h"/"24h"/"7d" dan HR=72.0, RR=16.0,
    # fatiga=10.0, HRV=50.0 -- exactamente el centro de la banda de sano
    # (`_simulate_healthy`: HR=72±3, RR=16±1, fatiga=10±5). La restricción de
    # horizontes NO cambió (sigue siendo solo now/5min/30min), pero la razón
    # sí: ahora es la misma categoría que convulsión/estrés/ansiedad/hipoxia
    # -- "recuperado, indistinguible de sano" -- no "valores rotos". "now"
    # (HR=120) y "5min" (HR=126.7) y "30min" (HR=160, pico del esfuerzo) no
    # se tocaron por este arreglo: esa fase no usa `recovery_progress`, vive
    # en la rama `if minutes<=30` por separado.
    "exercise": frozenset({"now", "5min", "30min"}),
    # Medido: "now" (HR=75, estrés=30) y "5min" (HR=76.2, estrés=32.1) caen
    # dentro o al borde de la banda de ruido de sano en esos mismos
    # horizontes -- el estrés recién empieza a subir. Desde "30min"
    # (HR=82.5, estrés=42.5) es limpio, y se sostiene característico
    # (meseta) hasta "7d".
    "stress": frozenset({"30min", "2h", "24h", "7d"}),
    # Medido: el pico agudo real está en "30min" (HR=140, SpO2=93,
    # inequívoco); "5min" (HR=90, estrés=56.7) también se midió característico
    # en la Fase 0, se incluye. "now" (HR=80, estrés=50) es dudoso -- el
    # episodio recién empieza. Desde "2h" en adelante, la fórmula NO revierte
    # a sano sino a un tercer estado propio (HR=80, estrés=50 fijo, salud_
    # global=70) que no es sano NI ansiedad aguda -- tratado como no
    # evaluable para generación, tal como pidió el validador.
    "anxiety": frozenset({"5min", "30min"}),
    # Medido: "now" (SpO2=98.0) y "5min" (SpO2=97.2) -- el marcador que
    # define el escenario (SpO2) todavía no bajó de forma clara. Desde
    # "30min" (SpO2=93.5) es inequívoco, y se sostiene severo (SpO2=80)
    # desde "2h" hasta "7d".
    "hypoxia": frozenset({"30min", "2h", "24h", "7d"}),
}

# Rango de variación honesta del estado inicial — fisiológicamente normal de
# reposo, nunca patológico por sí mismo (la patología la aporta el
# escenario, no el punto de partida). Equivalente a la variabilidad
# interpersonal real entre pacientes sanos en reposo.
_BASELINE_JITTER = {
    "hr": (60.0, 85.0),
    "hrv": (35.0, 65.0),
    "respiratory_rate": (12.0, 18.0),
    "spo2": (96.0, 99.0),
    "stress_level": (10.0, 35.0),
}


@dataclass(frozen=True)
class ClinicalCase:
    """Un caso clínico sintético: una trayectoria real del SimulationEngine,
    congelada en un horizonte temporal real, con su fuente declarada.

    `origen`/`provenance` son campos estructurales obligatorios — un caso
    sin fuente declarada no es válido (ver `__post_init__`), igual que la
    procedencia en el UPS."""

    case_id: str
    patient_id: str
    scenario: SimulationScenario  # verdad de referencia — por código, nunca por el modelo
    state: UnifiedPhysiologicalState
    events: List[PhysiologicalEvent]
    origen: str
    parametros: Dict[str, object]
    provenance: Provenance

    def __post_init__(self) -> None:
        if self.origen != "simulador_biocore":
            raise ValueError(
                "ClinicalCase.origen debe ser 'simulador_biocore' — fuente estructural obligatoria"
            )
        if self.provenance != Provenance.SIMULACION:
            raise ValueError("ClinicalCase.provenance debe ser Provenance.SIMULACION")


def generate_case(
    session: Session,
    scenario: Optional[SimulationScenario] = None,
    rng: Optional[random.Random] = None,
) -> ClinicalCase:
    """Genera un caso clínico sintético a partir de uno de los 12 escenarios
    reales del `SimulationEngine`, reutilizando `run_rich_scenario` sin
    modificarlo.

    `scenario=None` elige uno al azar entre los 12 reales (nunca un patrón
    inventado — ver `available_rich_scenarios()`)."""
    rng = rng or random.Random()
    scenario = scenario or rng.choice(available_rich_scenarios())

    organism = DigitalTwinOrganism()
    seed_hr = rng.uniform(*_BASELINE_JITTER["hr"])
    seed_hrv = rng.uniform(*_BASELINE_JITTER["hrv"])
    seed_rr = rng.uniform(*_BASELINE_JITTER["respiratory_rate"])
    seed_spo2 = rng.uniform(*_BASELINE_JITTER["spo2"])
    seed_stress = rng.uniform(*_BASELINE_JITTER["stress_level"])
    organism.update_from_sensors(
        {
            "ecg": {"heart_rate": seed_hr, "hrv": seed_hrv},
            "respiratory": {"respiratory_rate": seed_rr, "spo2": seed_spo2},
            "eeg": {"stress_level": seed_stress},
        }
    )  # punto de partida real, dentro de rango fisiológico normal

    # Fase 3 (paciente único de sesión, 2026-08-30): paciente efímero
    # deliberado, nunca el paciente único continuo de la sesión (ver
    # `create_ephemeral_case_patient()`, `rich_engine.py`) -- un quiz no
    # debe mezclarse con la trayectoria real del usuario.
    patient_id = create_ephemeral_case_patient(session, f"Caso sintético — {scenario.value}")

    steps = list(
        run_rich_scenario(session, patient_id, scenario, organism, start_from_current_state=True)
    )

    # Trabajo 2, Fase 1 (2026-08-06): restricción ESTRUCTURAL -- solo se
    # elige entre los horizontes de ESTE escenario que la matriz midió
    # evaluables (ver EVALUABLE_HORIZONS_BY_SCENARIO arriba). No es un
    # filtro que se pueda saltar: `chosen_step` solo puede salir de
    # `evaluable_steps`, nunca de `steps` sin filtrar.
    evaluable_horizons = EVALUABLE_HORIZONS_BY_SCENARIO.get(scenario.value, _ALL_HORIZONS)
    evaluable_steps = [
        step for step in steps
        if step.index < len(_HORIZON_LABELS) and _HORIZON_LABELS[step.index] in evaluable_horizons
    ]
    if not evaluable_steps:
        raise ValueError(
            f"Ningún horizonte evaluable para el escenario {scenario.value!r} -- revisar "
            "EVALUABLE_HORIZONS_BY_SCENARIO, cada escenario debe tener al menos uno."
        )
    chosen_step = rng.choice(evaluable_steps)  # punto de la evolución: solo entre los horizontes evaluables

    events = get_events(session, patient_id, end=chosen_step.state.timestamp)

    horizon_label = (
        _HORIZON_LABELS[chosen_step.index]
        if chosen_step.index < len(_HORIZON_LABELS)
        else str(chosen_step.index)
    )
    parametros = {
        "escenario": scenario.value,
        "horizonte_elegido": horizon_label,
        "fc_base_semilla": round(seed_hr, 1),
        "hrv_base_semilla": round(seed_hrv, 1),
        "respiratory_rate_base_semilla": round(seed_rr, 1),
        "spo2_base_semilla": round(seed_spo2, 1),
        "stress_level_base_semilla": round(seed_stress, 1),
    }

    return ClinicalCase(
        case_id=f"{patient_id}:{chosen_step.state.timestamp.isoformat()}",
        patient_id=patient_id,
        scenario=scenario,
        state=chosen_step.state,
        events=events,
        origen="simulador_biocore",
        parametros=parametros,
        provenance=Provenance.SIMULACION,
    )
