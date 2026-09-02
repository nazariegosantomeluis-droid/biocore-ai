"""
Módulo 2 — Paso 4: verificación en contexto del barórreflejo.

Deliberadamente NO persiste nada nuevo en el UPS -- "aislado, validado en
contexto antes de conectar a más escenarios" (instrucción explícita del
usuario para esta tanda). `run_rich_scenario()` sigue escribiendo sus
descriptores de siempre (heart_rate, hrv, ...) y su `ClinicalReferenceValue`
de siempre; este módulo solo LEE ese resultado y calcula (en memoria, sin
escribir) tanto la PA de resistencia fija (módulo 1,
`compute_calculated_pressure`) como la PA de resistencia dinámica
(módulo 2, `run_baroreflex`), para comparar ambas contra la misma
referencia clínica.

Ejecutar directamente:
    python -m domain.physiology.hemodynamics.baroreflex_comparison sepsis
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

from .baroreflex import BAROREFLEX_PARAMETERS_PENDING_VALIDATION, BaroreflexResult, run_baroreflex
from .ups_bridge import compute_calculated_pressure

__all__ = ["BaroreflexComparison", "run_scenario_baroreflex_comparison"]


@dataclass(frozen=True)
class BaroreflexComparison:
    scenario: str
    heart_rate_bpm: float
    static_r: dict  # módulo 1 -- resistencia FIJA, sin barórreflejo
    dynamic: BaroreflexResult  # módulo 2 -- resistencia dinámica, barórreflejo
    reference: List[ClinicalReferenceValue]
    pending_validation: bool

    def as_table_rows(self) -> List[tuple]:
        ref_by_descriptor = {r.descriptor: r for r in self.reference}
        rows = []
        for descriptor, static_key, dynamic_attr in (
            ("systolic_bp", "systolic_bp", "final_systolic_bp"),
            ("diastolic_bp", "diastolic_bp", "final_diastolic_bp"),
            ("map", "map", "final_map"),
        ):
            ref = ref_by_descriptor.get(descriptor)
            rows.append(
                (
                    descriptor,
                    round(self.static_r[static_key], 1),
                    round(getattr(self.dynamic, dynamic_attr), 1),
                    ref.value if ref else None,
                    ref.citation if ref else "sin referencia para este escenario",
                )
            )
        return rows


def run_scenario_baroreflex_comparison(
    scenario: SimulationScenario, db_path: Optional[Path] = None
) -> BaroreflexComparison:
    """Corre UN escenario (`run_rich_scenario`, modo basal, sin cambios) y
    calcula -- en memoria, sin persistir nada del barórreflejo -- la PA de
    resistencia fija y la de resistencia dinámica, para el mismo
    `heart_rate` final, comparadas contra la misma `ClinicalReferenceValue`."""
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

    static_r = compute_calculated_pressure(heart_rate_bpm)
    dynamic = run_baroreflex(heart_rate_bpm)

    return BaroreflexComparison(
        scenario=scenario.value,
        heart_rate_bpm=heart_rate_bpm,
        static_r=static_r,
        dynamic=dynamic,
        reference=reference,
        pending_validation=BAROREFLEX_PARAMETERS_PENDING_VALIDATION,
    )


def _print_comparison(comparison: BaroreflexComparison) -> None:
    print(f"\nEscenario: {comparison.scenario}  (heart_rate final: {comparison.heart_rate_bpm:.0f} bpm)")
    if comparison.pending_validation:
        print("*** Parámetros del barórreflejo (k, min_r, max_r, target_map) PENDIENTES DE VALIDACIÓN CUANTITATIVA (ver baroreflex.py) ***")
    print(
        f"Barórreflejo: converged={comparison.dynamic.converged}  ticks={len(comparison.dynamic.ticks)}  "
        f"Rd final={comparison.dynamic.final_rd:.3f} mmHg*s/mL  "
        f"clamped_min={comparison.dynamic.clamped_at_min}  clamped_max={comparison.dynamic.clamped_at_max}"
    )
    print(f"{'descriptor':<14}{'R fija (mmHg)':<16}{'R dinámica (mmHg)':<20}{'referencia (mmHg)':<20}cita de la referencia")
    for descriptor, static_val, dynamic_val, ref, citation in comparison.as_table_rows():
        ref_str = f"{ref:.1f}" if ref is not None else "—"
        print(f"{descriptor:<14}{static_val:<16}{dynamic_val:<20}{ref_str:<20}{citation}")
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
        result = run_scenario_baroreflex_comparison(scenario_enum, db_path=Path(tmp) / "baroreflex_comparison.db")
        _print_comparison(result)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
