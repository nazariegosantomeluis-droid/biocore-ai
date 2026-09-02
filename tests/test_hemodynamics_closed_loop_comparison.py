"""
"La película" — Módulo 4B-ii, verificación en contexto (2026-07-30).

Cubre: la PA final de sano/hipertensión/sepsis con el lazo COMPLETO
cerrado, comparada contra `ClinicalReferenceValue`, end-to-end (con
`run_rich_scenario` real); no-persistencia de nada nuevo en el UPS.

Nota de rendimiento: cada test de este archivo corre un escenario
completo (`run_rich_scenario`) + el lazo cerrado -- caro. Solo 3
escenarios titulares, un test end-to-end cada uno más un test de
aislamiento del UPS.
"""

import pytest

from app.engines.simulation_engine import SimulationScenario
from domain.physiology.hemodynamics.closed_loop_comparison import run_scenario_closed_loop_comparison


def test_healthy_closed_loop_comparison_end_to_end(tmp_path):
    comparison = run_scenario_closed_loop_comparison(SimulationScenario.HEALTHY, db_path=tmp_path / "closed_loop_healthy.db")

    assert comparison.scenario == "healthy"
    assert comparison.pending_validation is False  # VENOUS_RETURN_PARAMETERS_PENDING_VALIDATION, validado Ronda 2
    assert comparison.closed_loop.converged is True
    assert len(comparison.reference) == 3

    rows = comparison.as_table_rows()
    assert len(rows) == 3
    for _descriptor, closed_val, ref_val, _citation in rows:
        assert closed_val is not None
        assert ref_val is not None

    # PAM debe quedar muy cerca de la referencia -- el ancla de calibración.
    map_row = next(r for r in rows if r[0] == "map")
    assert map_row[1] == pytest.approx(map_row[2], abs=1.0)


def test_hypertension_closed_loop_comparison_end_to_end(tmp_path):
    comparison = run_scenario_closed_loop_comparison(
        SimulationScenario.HYPERTENSION, db_path=tmp_path / "closed_loop_hypertension.db"
    )

    assert comparison.scenario == "hypertension"
    assert comparison.closed_loop.converged is True
    assert comparison.closed_loop.clamped_at_max_rd is False  # encuentra equilibrio, no choca límites
    assert len(comparison.reference) == 3

    rows = comparison.as_table_rows()
    map_row = next(r for r in rows if r[0] == "map")
    # PAM elevada respecto al sano (93.3), consistente con la dirección de la referencia (96.7).
    assert map_row[1] > 93.3


def test_sepsis_closed_loop_comparison_end_to_end_collapses_toward_shock(tmp_path):
    """El hallazgo central de esta tanda, verificado end-to-end: con el
    lazo cerrado, la PAM de sepsis cae por DEBAJO del ancla sana (93.3) --
    y por debajo del umbral clínico de shock (65 mmHg) -- de forma
    orgánica (parámetros fijados antes de mirar este resultado), no
    porque se haya retocado nada para que coincida con la referencia."""
    comparison = run_scenario_closed_loop_comparison(SimulationScenario.SEPSIS, db_path=tmp_path / "closed_loop_sepsis.db")

    assert comparison.scenario == "sepsis"
    assert comparison.closed_loop.converged is True
    assert comparison.closed_loop.clamped_at_max_rd is True  # el barórreflejo choca su techo intentando compensar
    assert len(comparison.reference) == 3

    rows = comparison.as_table_rows()
    map_row = next(r for r in rows if r[0] == "map")
    assert map_row[1] < 65.0  # por debajo del umbral de shock de la propia referencia (Sepsis-3)
    assert map_row[1] < 93.3  # por debajo del ancla sana -- colapso real, no un artefacto


def test_closed_loop_comparison_does_not_write_new_ups_descriptors(tmp_path):
    """Aislado -- mismo criterio que baroreflex_comparison.py y
    pathological_tone_comparison.py: correr la comparación del lazo
    cerrado no debe dejar descriptores nuevos en el UPS."""
    from domain.physiology.state import get_latest_state, init_db, make_engine, make_session_factory

    db_path = tmp_path / "closed_loop_isolation.db"
    run_scenario_closed_loop_comparison(SimulationScenario.HEALTHY, db_path=db_path)

    engine = make_engine(db_path)
    init_db(engine)
    SessionLocal = make_session_factory(engine)
    with SessionLocal() as session:
        from sqlalchemy import select

        from domain.physiology.state.models import ValueRecord

        descriptor_names = set(session.execute(select(ValueRecord.descriptor)).scalars().all())

    assert "systolic_bp_modelo" not in descriptor_names
    assert "diastolic_bp_modelo" not in descriptor_names
    assert "map_modelo" not in descriptor_names
