"""
Módulo 4B-ii — verificación en contexto del lazo cerrado.

Mismo criterio de aislamiento que `baroreflex_comparison.py` (Módulo 2) y
`pathological_tone_comparison.py` (Módulo 3): deliberadamente NO persiste
nada nuevo en el UPS. `run_rich_scenario()` sigue escribiendo sus
descriptores de siempre; este módulo solo LEE ese resultado (el
`heart_rate` final) y calcula -- en memoria, sin escribir -- la PA con el
lazo COMPLETO cerrado (`run_closed_loop`, Módulo 4B-ii), comparada contra
la misma `ClinicalReferenceValue` de cada escenario -- control de calidad
independiente, no un objetivo de ajuste (ver salvaguarda anti-circularidad
máxima en `closed_loop.py`).

Ejecutar directamente:
    python -m domain.physiology.hemodynamics.closed_loop_comparison sepsis
    python -m domain.physiology.hemodynamics.closed_loop_comparison hypertension
    python -m domain.physiology.hemodynamics.closed_loop_comparison healthy
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
    get_latest_state,
    init_db,
    make_engine,
    make_session_factory,
)

from .closed_loop import VENOUS_RETURN_PARAMETERS_PENDING_VALIDATION, ClosedLoopResult, run_closed_loop

__all__ = ["ClosedLoopComparison", "run_scenario_closed_loop_comparison"]


@dataclass(frozen=True)
class ClosedLoopComparison:
    scenario: str
    heart_rate_bpm: float
    closed_loop: ClosedLoopResult
    reference: List[ClinicalReferenceValue]
    pending_validation: bool

    def as_table_rows(self) -> List[tuple]:
        ref_by_descriptor = {r.descriptor: r for r in self.reference}
        rows = []
        for descriptor, attr in (
            ("systolic_bp", "final_systolic_bp"),
            ("diastolic_bp", "final_diastolic_bp"),
            ("map", "final_map"),
        ):
            ref = ref_by_descriptor.get(descriptor)
            rows.append(
                (
                    descriptor,
                    round(getattr(self.closed_loop, attr), 1),
                    ref.value if ref else None,
                    ref.citation if ref else "sin referencia para este escenario",
                )
            )
        return rows


def run_scenario_closed_loop_comparison(
    scenario: SimulationScenario, db_path: Optional[Path] = None
) -> ClosedLoopComparison:
    """Corre UN escenario (`run_rich_scenario`, modo basal, sin cambios) y
    calcula -- en memoria, sin persistir nada del lazo cerrado -- la PA
    resultante de cerrar la cadena completa (Módulo 4B-ii) para el mismo
    `heart_rate` final, comparada contra la misma `ClinicalReferenceValue`."""
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

        reference = get_clinical_references_for_patient(session, patient_id)
        reference = [r for r in reference if r.scenario == scenario.value]

    closed_loop_result = run_closed_loop(scenario.value, heart_rate_bpm)

    return ClosedLoopComparison(
        scenario=scenario.value,
        heart_rate_bpm=heart_rate_bpm,
        closed_loop=closed_loop_result,
        reference=reference,
        pending_validation=VENOUS_RETURN_PARAMETERS_PENDING_VALIDATION,
    )


def _print_comparison(comparison: ClosedLoopComparison) -> None:
    print(f"\nEscenario: {comparison.scenario}  (heart_rate final: {comparison.heart_rate_bpm:.0f} bpm)")
    if comparison.pending_validation:
        print("*** Parámetros del retorno venoso real PENDIENTES DE VALIDACIÓN CUANTITATIVA (ver closed_loop.py) ***")
    print(
        f"Lazo cerrado: converged={comparison.closed_loop.converged}  oscillated={comparison.closed_loop.oscillated}  "
        f"ticks={len(comparison.closed_loop.ticks)}  SV final={comparison.closed_loop.final_stroke_volume_ml:.1f} mL  "
        f"EDV final={comparison.closed_loop.final_edv_ml:.1f} mL  "
        f"clamped_min_rd={comparison.closed_loop.clamped_at_min_rd}  clamped_max_rd={comparison.closed_loop.clamped_at_max_rd}  "
        f"clamped_edv_floor={comparison.closed_loop.clamped_at_edv_floor}"
    )
    print(f"{'descriptor':<14}{'lazo cerrado (mmHg)':<22}{'referencia (mmHg)':<20}cita de la referencia")
    for descriptor, closed_val, ref, citation in comparison.as_table_rows():
        ref_str = f"{ref:.1f}" if ref is not None else "—"
        print(f"{descriptor:<14}{closed_val:<22}{ref_str:<20}{citation}")
    print()


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    scenario_arg = sys.argv[1] if len(sys.argv) > 1 else "sepsis"
    try:
        scenario_enum = SimulationScenario(scenario_arg)
    except ValueError:
        valid = ", ".join(s.value for s in SimulationScenario)
        raise SystemExit(f"Escenario desconocido: {scenario_arg!r}. Válidos: {valid}")

    tmp = tempfile.mkdtemp()
    try:
        result = run_scenario_closed_loop_comparison(scenario_enum, db_path=Path(tmp) / "closed_loop_comparison.db")
        _print_comparison(result)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
