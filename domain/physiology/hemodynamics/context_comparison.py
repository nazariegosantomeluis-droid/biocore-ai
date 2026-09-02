"""
Paso 3 — verificación en contexto: PA calculada (modelo R-RCR fisiológico)
junto a la PA de referencia clínica (`ClinicalReferenceValue`), para el
mismo escenario y el mismo snapshot, de forma comparable.

Esto NO es una validación automática — es la forma de INSPECCIONAR el
resultado para que el usuario y su validador experto juzguen si tiene
sentido fisiológico. Una gran divergencia es una señal de alarma a
investigar, no un test que pasa o falla por sí solo (a diferencia de
`tests/test_hemodynamics_r_rcr.py`, que sí verifica matemáticamente contra
el solver de referencia).

Ejecutar directamente para inspeccionar un escenario:
    python -m domain.physiology.hemodynamics.context_comparison healthy
    python -m domain.physiology.hemodynamics.context_comparison hypertension
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from app.engines.digital_twin_organism import DigitalTwinOrganism
from app.engines.simulation_engine import SimulationScenario
from domain.physiology.scenarios.rich_engine import create_ephemeral_basal_patient, run_rich_scenario
from domain.physiology.state import (
    ClinicalReferenceValue,
    get_clinical_references_for_patient,
    get_latest_snapshot_id,
    get_latest_state,
    init_db,
    make_engine,
    make_session_factory,
)

from .physiological_flow import PHYSIOLOGICAL_PARAMETERS_PENDING_VALIDATION
from .ups_bridge import compute_and_attach_calculated_pressure

__all__ = ["PressureComparison", "run_scenario_pressure_comparison"]


@dataclass(frozen=True)
class PressureComparison:
    scenario: str
    heart_rate_bpm: float
    calculated: dict  # systolic_bp/diastolic_bp/map, del modelo hemodinámico
    reference: List[ClinicalReferenceValue]  # de blood_pressure_references.py, puede ser []
    pending_validation: bool  # PHYSIOLOGICAL_PARAMETERS_PENDING_VALIDATION -- siempre True hoy

    def as_table_rows(self) -> List[tuple]:
        ref_by_descriptor = {r.descriptor: r for r in self.reference}
        rows = []
        for descriptor, calc_key in (
            ("systolic_bp", "systolic_bp"),
            ("diastolic_bp", "diastolic_bp"),
            ("map", "map"),
        ):
            ref = ref_by_descriptor.get(descriptor)
            rows.append(
                (
                    descriptor,
                    round(self.calculated[calc_key], 1),
                    ref.value if ref else None,
                    ref.citation if ref else "sin referencia para este escenario",
                )
            )
        return rows


def run_scenario_pressure_comparison(scenario: SimulationScenario, db_path: Optional[Path] = None) -> PressureComparison:
    """Corre UN escenario completo (`run_rich_scenario`, modo basal), adjunta
    la PA calculada por el modelo hemodinámico al snapshot final, y la
    empareja con la PA de referencia clínica del mismo escenario (si
    existe -- no todos los escenarios tienen fuente, ver
    `blood_pressure_references.py`)."""
    engine = make_engine(db_path)
    init_db(engine)
    SessionLocal = make_session_factory(engine)

    with SessionLocal() as session:
        organism = DigitalTwinOrganism()
        patient_id = create_ephemeral_basal_patient(session, scenario)
        list(run_rich_scenario(session, patient_id, scenario, organism, start_from_current_state=False))

        state = get_latest_state(session, patient_id)
        heart_rate_descriptor = state.cardiovascular.get("heart_rate")
        if heart_rate_descriptor is None:
            raise ValueError(f"El escenario {scenario.value} no dejó heart_rate en su snapshot final")
        heart_rate_bpm = heart_rate_descriptor.value

        snapshot_id = get_latest_snapshot_id(session, patient_id)
        calculated = compute_and_attach_calculated_pressure(
            session,
            snapshot_id=snapshot_id,
            heart_rate_bpm=heart_rate_bpm,
            source_detail=f"comparacion_en_contexto:{scenario.value}",
        )

        reference = get_clinical_references_for_patient(session, patient_id)
        reference = [r for r in reference if r.scenario == scenario.value]

    return PressureComparison(
        scenario=scenario.value,
        heart_rate_bpm=heart_rate_bpm,
        calculated=calculated,
        reference=reference,
        pending_validation=PHYSIOLOGICAL_PARAMETERS_PENDING_VALIDATION,
    )


def _print_comparison(comparison: PressureComparison) -> None:
    print(f"\nEscenario: {comparison.scenario}  (heart_rate final: {comparison.heart_rate_bpm:.0f} bpm)")
    if comparison.pending_validation:
        print("*** Parámetros R/Rp/Rd/C fisiológicos PENDIENTES DE VALIDACIÓN EXPERTA (ver physiological_flow.py) ***")
    print(f"{'descriptor':<14}{'calculada (mmHg)':<20}{'referencia (mmHg)':<20}cita de la referencia")
    for descriptor, calc, ref, citation in comparison.as_table_rows():
        ref_str = f"{ref:.1f}" if ref is not None else "—"
        print(f"{descriptor:<14}{calc:<20}{ref_str:<20}{citation}")
    print()


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # consola de Windows por defecto no es utf-8 (cp1252)

    scenario_arg = sys.argv[1] if len(sys.argv) > 1 else "healthy"
    try:
        scenario_enum = SimulationScenario(scenario_arg)
    except ValueError:
        valid = ", ".join(s.value for s in SimulationScenario)
        raise SystemExit(f"Escenario desconocido: {scenario_arg!r}. Válidos: {valid}")

    tmp = tempfile.mkdtemp()
    try:
        result = run_scenario_pressure_comparison(scenario_enum, db_path=Path(tmp) / "context_comparison.db")
        _print_comparison(result)
    finally:
        # SQLite en Windows puede dejar el archivo .db-wal bloqueado un instante
        # tras cerrar la sesión -- best-effort, no crítico (directorio temporal).
        shutil.rmtree(tmp, ignore_errors=True)
