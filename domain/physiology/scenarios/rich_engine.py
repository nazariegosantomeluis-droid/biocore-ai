"""
Tanda 3 (2026-07-03) — Puente entre el motor rico de 12 escenarios
(`app.engines.simulation_engine.SimulationEngine`) y el pipeline del UPS
que ya usan los 3 escenarios de la Fase 1.2 (`engine.py` / `definitions.py`
— sin tocar, siguen existiendo y probados por `tests/test_scenario_simulator.py`).

No reescribe el núcleo verificado: reutiliza exactamente las mismas
funciones ya probadas — `organism.update_from_sensors()`,
`from_digital_twin_organism()`, `save_state()`, `create_patient()` — para
persistir cada paso. Lo único nuevo es de dónde vienen los valores de
entrada (`SimulationEngine` en vez de interpolación de waypoints) y el
mapeo de sus 6 horizontes temporales al mismo shape de estado que el
organismo ya entiende.

`SimulationEngine.simulate_scenario()` reutiliza `self.timeline` /
`self.current_scenario` internamente entre llamadas al mismo objeto — se
instancia un `SimulationEngine()` nuevo en cada corrida para no arrastrar
estado residual entre escenarios (cautela señalada por la auditoría).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterator, List, Optional

from sqlalchemy.orm import Session

from app.engines.simulation_engine import SimulationEngine, SimulationScenario
from app.utils.physiological_state import persist_current_state
from domain.physiology.state import (
    BLOOD_PRESSURE_REFERENCES,
    create_clinical_reference,
    create_patient,
)

from .engine import ScenarioStep

if TYPE_CHECKING:
    from app.engines.digital_twin_organism import DigitalTwinOrganism

__all__ = [
    "available_rich_scenarios",
    "run_rich_scenario",
    "create_ephemeral_basal_patient",
    "create_ephemeral_case_patient",
]


def available_rich_scenarios() -> List[SimulationScenario]:
    """Los 12 escenarios reales del SimulationEngine, en el orden del enum."""
    return list(SimulationScenario)


def _current_state_as_initial_state(organism: "DigitalTwinOrganism") -> dict:
    """Construye el `initial_state` del SimulationEngine a partir de las
    señales reales del organismo actual. Si una señal no existe todavía
    (organismo recién creado, nunca recibió `update_from_sensors`), se omite
    — nunca se inventa un valor; el motor cae a su propio basal solo para
    esa señal puntual (`SimulationEngine.BASELINE_PARAMETERS`)."""
    heart_signals = organism.organs["heart"].metrics.signals
    lungs_signals = organism.organs["lungs"].metrics.signals
    brain_signals = organism.organs["brain"].metrics.signals

    initial_state: dict = {}
    if "heart_rate" in heart_signals:
        initial_state["hr"] = heart_signals["heart_rate"]
    if "hrv" in heart_signals:
        initial_state["hrv"] = heart_signals["hrv"]
    if "respiratory_rate" in lungs_signals:
        initial_state["respiratory_rate"] = lungs_signals["respiratory_rate"]
    if "spo2" in lungs_signals:
        initial_state["spo2"] = lungs_signals["spo2"]
    if "stress_level" in brain_signals:
        initial_state["stress_level"] = brain_signals["stress_level"]
    return initial_state


def run_rich_scenario(
    session: Session,
    patient_id: str,
    scenario: SimulationScenario,
    organism: "DigitalTwinOrganism",
    start_from_current_state: bool,
) -> Iterator[ScenarioStep]:
    """Evoluciona `organism` a través de uno de los 12 escenarios reales del
    SimulationEngine y persiste cada uno de sus 6 horizontes temporales
    (now/5min/30min/2h/24h/7d) en el UPS — mismo `ScenarioStep`,
    `from_digital_twin_organism()` y `save_state()` que usan los 3
    escenarios de la Fase 1.2; solo cambia de dónde vienen los valores.

    `start_from_current_state=True` ("estado actual"): el escenario arranca
    de las señales reales del organismo — continuidad realista, el
    narrador podrá comparar antes→ahora con historial genuino.

    `start_from_current_state=False` ("basal"): arranca de los parámetros
    basales del propio SimulationEngine. El llamador debe usar un
    `patient_id` efímero nuevo (`create_ephemeral_basal_patient`) para este
    modo — este módulo no decide el patient_id, solo la trayectoria.

    Presión arterial, Paso 1+2 (2026-07-18): si `scenario` tiene entrada en
    `BLOOD_PRESSURE_REFERENCES`, los valores de referencia (sistólica/
    diastólica/PAM, con su cita) se adjuntan al ÚLTIMO snapshot de esta
    corrida — no a los 6, porque es una fotografía del cuadro, no una
    trayectoria dinámica. Escenarios sin fuente transcrita (fatiga, EPOC)
    no reciben nada, honestamente."""
    engine = SimulationEngine()  # instancia nueva: cero estado residual entre corridas
    initial_state = _current_state_as_initial_state(organism) if start_from_current_state else None
    timeline = engine.simulate_scenario(scenario, initial_state=initial_state)

    total_steps = len(timeline)
    mode_label = "estado_actual" if start_from_current_state else "basal"
    last_snapshot_id: Optional[str] = None

    for i, step in enumerate(timeline):
        sensor_data = {
            "ecg": {"heart_rate": step.hr, "hrv": step.hrv},
            "respiratory": {"respiratory_rate": step.respiratory_rate, "spo2": step.spo2, "ahi": step.ahi},
        }
        organism.update_from_sensors(sensor_data)

        # Fase 5.3 (2026-08-30): helper compartido con los otros 3
        # escritores del UPS (Guardar este momento/Narrador/Razonamiento
        # causal, `twin_shell/pages.py`) -- mismo `from_digital_twin_
        # organism() + save_state()`, mismo `Provenance.SIMULACION` por
        # defecto, solo cambia `source_detail`.
        state, last_snapshot_id = persist_current_state(
            session,
            organism,
            patient_id,
            source_detail=f"escenario_rico:{scenario.value}:modo:{mode_label}:horizonte:{step.time_point}",
        )

        progress = i / (total_steps - 1) if total_steps > 1 else 1.0
        yield ScenarioStep(index=i, total_steps=total_steps, progress=progress, state=state)

    references = BLOOD_PRESSURE_REFERENCES.get(scenario.value)
    if references and last_snapshot_id is not None:
        for reference in references:
            create_clinical_reference(session, snapshot_id=last_snapshot_id, patient_id=patient_id, reference=reference)


def create_ephemeral_basal_patient(session: Session, scenario: SimulationScenario) -> str:
    """Crea un paciente nuevo y desechable para una corrida en modo 'basal'.

    Garantiza que `get_value_history`/`get_latest_state` no encuentren
    ningún snapshot previo no relacionado (de otro escenario, de otro modo,
    o del paciente continuo) — así el narrador no compara un caso
    didáctico contra un 'antes' ajeno. Antes de que este mismo escenario
    persista su segundo paso, `before_value` es `None` por construcción
    (no hay historial previo para este `patient_id`, no porque se haya
    ocultado nada)."""
    return create_patient(session, display_name=f"Caso didáctico — {scenario.value} (basal)")


def create_ephemeral_case_patient(session: Session, label: str) -> str:
    """Fase 3 (paciente único de sesión, 2026-08-30) — mismo principio que
    `create_ephemeral_basal_patient()` de arriba, generalizado: un paciente
    nuevo y desechable para un ejercicio de diagnóstico ciego, que NUNCA
    debe mezclarse con el paciente único continuo de la sesión
    (`get_active_patient_id()`, `app/utils/patient_session.py`) -- si se
    mezclara, el estudiante vería la trayectoria real de otra parte de su
    propia sesión colándose en un caso que se supone aislado.

    Antes de esta tanda, dos módulos creaban este mismo tipo de paciente
    cada uno con su `create_patient()` inline, sin ningún nombre que
    declarara la intención: `case_bank.py::generate_case()` (el quiz de
    Academia) y `twin_shell/pages.py::render_clinical_case_mode()` (el
    "Modo caso clínico interactivo" de Twin OS) -- confirmado por grep que
    eran, byte a byte, el mismo patrón (crear paciente -> correr
    escenario -> diagnóstico ciego) repetido dos veces. `label` es el
    `display_name` -- cada llamador conserva su propio texto."""
    return create_patient(session, display_name=label)
