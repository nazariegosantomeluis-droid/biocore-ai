"""
Módulo 3 — Paso 2: verificación en contexto del tono vascular patológico.

Mismo criterio de aislamiento que `baroreflex_comparison.py` (Módulo 2,
Paso 4): deliberadamente NO persiste nada nuevo en el UPS. `run_rich_scenario()`
sigue escribiendo sus descriptores de siempre; este módulo solo LEE ese
resultado y calcula -- en memoria, sin escribir -- tanto la PA de
barórreflejo SIN mecanismo patológico (Módulo 2 puro, `run_baroreflex`)
como la PA CON el mecanismo patológico de este escenario (Módulo 3,
`run_pathological_baroreflex`), para comparar ambas contra la misma
`ClinicalReferenceValue` -- control de calidad independiente, no un
objetivo de ajuste (ver salvaguarda anti-circularidad en
`pathological_tone.py`).

Ejecutar directamente:
    python -m domain.physiology.hemodynamics.pathological_tone_comparison sepsis
    python -m domain.physiology.hemodynamics.pathological_tone_comparison hypertension
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

from .baroreflex import BaroreflexResult, run_baroreflex
from .pathological_tone import PATHOLOGICAL_TONE_OVERRIDES, PATHOLOGICAL_TONE_PENDING_VALIDATION, run_pathological_baroreflex

__all__ = ["PathologicalToneComparison", "run_scenario_pathological_tone_comparison"]


@dataclass(frozen=True)
class PathologicalToneComparison:
    scenario: str
    heart_rate_bpm: float
    baseline_dynamic: BaroreflexResult  # Módulo 2 puro -- sin mecanismo patológico
    pathological_dynamic: BaroreflexResult  # Módulo 3 -- con el mecanismo del escenario (si existe)
    has_pathological_override: bool
    reference: List[ClinicalReferenceValue]
    pending_validation: bool

    def as_table_rows(self) -> List[tuple]:
        ref_by_descriptor = {r.descriptor: r for r in self.reference}
        rows = []
        for descriptor, dynamic_attr in (
            ("systolic_bp", "final_systolic_bp"),
            ("diastolic_bp", "final_diastolic_bp"),
            ("map", "final_map"),
        ):
            ref = ref_by_descriptor.get(descriptor)
            rows.append(
                (
                    descriptor,
                    round(getattr(self.baseline_dynamic, dynamic_attr), 1),
                    round(getattr(self.pathological_dynamic, dynamic_attr), 1),
                    ref.value if ref else None,
                    ref.citation if ref else "sin referencia para este escenario",
                )
            )
        return rows


def run_scenario_pathological_tone_comparison(
    scenario: SimulationScenario, db_path: Optional[Path] = None
) -> PathologicalToneComparison:
    """Corre UN escenario (`run_rich_scenario`, modo basal, sin cambios) y
    calcula -- en memoria, sin persistir nada del Módulo 3 -- la PA de
    barórreflejo sin y con el mecanismo patológico del escenario, para el
    mismo `heart_rate` final, comparadas contra la misma
    `ClinicalReferenceValue`."""
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

    baseline_dynamic = run_baroreflex(heart_rate_bpm)
    pathological_dynamic = run_pathological_baroreflex(scenario.value, heart_rate_bpm)

    return PathologicalToneComparison(
        scenario=scenario.value,
        heart_rate_bpm=heart_rate_bpm,
        baseline_dynamic=baseline_dynamic,
        pathological_dynamic=pathological_dynamic,
        has_pathological_override=scenario.value in PATHOLOGICAL_TONE_OVERRIDES,
        reference=reference,
        pending_validation=PATHOLOGICAL_TONE_PENDING_VALIDATION,
    )


def _print_comparison(comparison: PathologicalToneComparison) -> None:
    print(f"\nEscenario: {comparison.scenario}  (heart_rate final: {comparison.heart_rate_bpm:.0f} bpm)")
    if comparison.pending_validation:
        print("*** Parámetros del tono vascular patológico PENDIENTES DE VALIDACIÓN CUANTITATIVA (ver pathological_tone.py) ***")
    if not comparison.has_pathological_override:
        print(f"(sin mecanismo patológico definido para '{comparison.scenario}' -- pathological_dynamic == baseline_dynamic, pass-through)")
    print(
        f"Módulo 2 (sin patología): target_map={comparison.baseline_dynamic.target_map:.2f}  "
        f"Rd final={comparison.baseline_dynamic.final_rd:.3f}  converged={comparison.baseline_dynamic.converged}"
    )
    print(
        f"Módulo 3 (con patología): target_map={comparison.pathological_dynamic.target_map:.2f}  "
        f"Rd final={comparison.pathological_dynamic.final_rd:.3f}  converged={comparison.pathological_dynamic.converged}  "
        f"clamped_max={comparison.pathological_dynamic.clamped_at_max}"
    )
    print(f"{'descriptor':<14}{'Módulo 2 (mmHg)':<18}{'Módulo 3 (mmHg)':<18}{'referencia (mmHg)':<20}cita de la referencia")
    for descriptor, baseline_val, pathological_val, ref, citation in comparison.as_table_rows():
        ref_str = f"{ref:.1f}" if ref is not None else "—"
        print(f"{descriptor:<14}{baseline_val:<18}{pathological_val:<18}{ref_str:<20}{citation}")
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
        result = run_scenario_pathological_tone_comparison(scenario_enum, db_path=Path(tmp) / "pathological_tone_comparison.db")
        _print_comparison(result)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
