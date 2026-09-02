"""
Fase 1.2 — Simulador de escenarios clínicos que alimenta el UPS.

Hace evolucionar un `DigitalTwinOrganism` a lo largo de un escenario
definido en `definitions.py`, reutilizando la lógica fisiológica ya
existente en `update_from_sensors` (ningún umbral clínico se duplica
aquí — ver `domain/physiology/state/builder.py` para el mismo principio
aplicado a la detección de eventos). Cada paso se traduce a un
`UnifiedPhysiologicalState` y se persiste de inmediato, siempre con
`Provenance.SIMULACION` — nunca se presenta como dato de sensor real.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, List, Optional, TYPE_CHECKING

from sqlalchemy.orm import Session

from domain.physiology.state import (
    Provenance,
    UnifiedPhysiologicalState,
    from_digital_twin_organism,
    save_state,
)

from .definitions import SCENARIOS, interpolate

if TYPE_CHECKING:
    from app.engines.digital_twin_organism import DigitalTwinOrganism


@dataclass(frozen=True)
class ScenarioStep:
    index: int
    total_steps: int
    progress: float
    state: UnifiedPhysiologicalState


def available_scenarios() -> List[str]:
    return sorted(SCENARIOS.keys())


def run_scenario(
    session: Session,
    patient_id: str,
    scenario_name: str,
    steps: int = 10,
    organism: Optional["DigitalTwinOrganism"] = None,
) -> Iterator[ScenarioStep]:
    """Hace evolucionar `organism` a través de `scenario_name` en `steps`
    pasos deterministas (interpolación de waypoints clínicos, no valores
    aleatorios), persistiendo un snapshot del UPS por paso.

    Generador: produce un `ScenarioStep` ya persistido por cada paso, para
    que un llamador (UI o prueba) pueda observar la evolución sin esperar
    a que termine el escenario completo.
    """
    if scenario_name not in SCENARIOS:
        raise ValueError(f"Escenario desconocido: {scenario_name!r}. Disponibles: {available_scenarios()}")
    if steps < 2:
        raise ValueError("Un escenario necesita al menos 2 pasos para tener trayectoria.")

    if organism is None:
        from app.engines.digital_twin_organism import DigitalTwinOrganism
        organism = DigitalTwinOrganism()

    waypoints = SCENARIOS[scenario_name]

    for i in range(steps):
        progress = i / (steps - 1)
        sensor_data = interpolate(waypoints, progress)
        organism.update_from_sensors(sensor_data)

        state = from_digital_twin_organism(
            organism,
            patient_id=patient_id,
            provenance=Provenance.SIMULACION,
            source_detail=f"escenario:{scenario_name}:paso:{i + 1}/{steps}",
        )
        save_state(session, state)

        yield ScenarioStep(index=i, total_steps=steps, progress=progress, state=state)
