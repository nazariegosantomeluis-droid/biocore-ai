"""
"La película" — Módulo 2 (2026-07-20): resistencia vascular dinámica
(barórreflejo, controlador proporcional).

Cubre: mecanismo citado vs. magnitudes marcadas pendientes, salvaguarda
anti-circularidad (un solo target_map fijo para todos los escenarios,
nunca ajustado por escenario), signo de la retroalimentación negativa,
convergencia/clamping/no-convergencia honesta del bucle, aislamiento
stateless, y que Rp/C/Pd del módulo 1 quedan intactos (solo Rd se mueve).
"""

import dataclasses

import numpy as np
import pytest

from app.engines.simulation_engine import SimulationScenario
from domain.physiology.hemodynamics.baroreflex import (
    BAROREFLEX_MAX_RD,
    BAROREFLEX_MECHANISM_CITATION,
    BAROREFLEX_MIN_RD,
    BAROREFLEX_PARAMETERS_PENDING_VALIDATION,
    BAROREFLEX_TARGET_MAP_MMHG,
    run_baroreflex,
)
from domain.physiology.hemodynamics.baroreflex_comparison import run_scenario_baroreflex_comparison
from domain.physiology.hemodynamics.physiological_flow import PHYSIOLOGICAL_RRCR_PARAMETERS, physiological_pulsatile_flow
from domain.physiology.hemodynamics.r_rcr import RRCRParameters, simulate_r_rcr
from domain.physiology.hemodynamics.ups_bridge import compute_calculated_pressure
from domain.physiology.state.clinical_reference import estimate_map


# --- Mecanismo citado vs. magnitudes pendientes -------------------------------


def test_mechanism_citation_is_non_empty_and_cites_guyton():
    assert "Guyton" in BAROREFLEX_MECHANISM_CITATION
    assert len(BAROREFLEX_MECHANISM_CITATION) > 20


def test_baroreflex_parameters_fully_validated_as_of_round_2():
    """Los cuatro parámetros de este módulo (min_rd/max_rd -- Ronda 1;
    k/target_map -- Ronda 2, 2026-07-31) quedaron confirmados por el
    validador experto -- la bandera bajó a False. Ver
    tests/test_hemodynamics_validation_round2.py para el detalle de cada
    dictamen."""
    assert BAROREFLEX_PARAMETERS_PENDING_VALIDATION is False


def test_min_max_rd_are_symmetric_multiples_of_calibrated_base_rd():
    base_rd = PHYSIOLOGICAL_RRCR_PARAMETERS.rd
    assert BAROREFLEX_MIN_RD == pytest.approx(base_rd * 0.3)
    assert BAROREFLEX_MAX_RD == pytest.approx(base_rd * 3.0)


# --- Salvaguarda anti-circularidad --------------------------------------------


def test_target_map_is_a_single_fixed_value_not_scenario_specific():
    """El target_map por defecto de run_baroreflex() es SIEMPRE el mismo
    (el ancla 'sano' del módulo 1, 93.33 mmHg) sin importar el
    heart_rate/escenario que se le pase -- si variara por escenario para
    acercarse a la referencia clínica de cada uno, el modelo estaría
    afinado para reproducir la respuesta, no produciéndola por mecanismo."""
    assert BAROREFLEX_TARGET_MAP_MMHG == pytest.approx(estimate_map(120.0, 80.0))

    result_healthy = run_baroreflex(72.0)
    result_sepsis = run_baroreflex(150.0)
    assert result_healthy.target_map == result_sepsis.target_map == BAROREFLEX_TARGET_MAP_MMHG


def test_sepsis_dynamic_map_does_not_match_clinical_reference_by_construction():
    """Hallazgo esperado y documentado, NO oculto: con un único target_map
    fijo y heart_rate como única entrada dinámica, el barórreflejo
    normaliza la PAM de sepsis (~93 mmHg) en vez de reproducir la
    hipotensión de la referencia clínica (65 mmHg) -- no hay ningún driver
    de vasoplejía séptica en este modelo. Si este test empieza a fallar
    porque alguien "ajustó" target_map/k/límites para acercarse a 65, eso
    sería exactamente la circularidad prohibida por el validador."""
    result = run_baroreflex(150.0)
    assert result.converged is True
    assert result.final_map == pytest.approx(BAROREFLEX_TARGET_MAP_MMHG, abs=0.5)
    assert result.final_map > 80.0  # lejos de la referencia de shock (PAM<65)


# --- Signo de la retroalimentación negativa -----------------------------------


def test_high_flow_scenario_triggers_vasodilation_not_vasoconstriction():
    """hypertension (HR=85) produce, con Rd fija, una PAM por ENCIMA del
    objetivo (más flujo -> más presión) -- el barórreflejo debe reducir Rd
    (vasodilatar) para compensar, no subirla."""
    base_rd = PHYSIOLOGICAL_RRCR_PARAMETERS.rd
    result = run_baroreflex(85.0)
    assert result.final_rd < base_rd


def test_low_flow_scenario_triggers_vasoconstriction_not_vasodilation():
    """Bradicardia marcada (HR=40) produce, con Rd fija, una PAM por
    DEBAJO del objetivo -- el barórreflejo debe subir Rd (vasoconstricción)."""
    base_rd = PHYSIOLOGICAL_RRCR_PARAMETERS.rd
    result = run_baroreflex(40.0)
    assert result.final_rd > base_rd


# --- Convergencia, clamping, no-convergencia honesta --------------------------


def test_typical_scenarios_converge_within_reasonable_ticks():
    for hr in (72.0, 85.0, 150.0):
        result = run_baroreflex(hr)
        assert result.converged is True
        assert len(result.ticks) < 20


def test_extreme_tachycardia_clamps_at_min_rd():
    """HR=220 exige una Rd por debajo del piso fisiológico -- el
    controlador debe recortar en min_rd, no salirse de rango."""
    result = run_baroreflex(220.0)
    assert result.clamped_at_min is True
    assert result.final_rd == pytest.approx(BAROREFLEX_MIN_RD, rel=1e-6)
    # Compensación parcial: no llega al objetivo, pero tampoco se dispara sin límite
    assert result.final_map > BAROREFLEX_TARGET_MAP_MMHG


def test_pathological_gain_fails_to_converge_honestly_not_silently():
    """Una ganancia muy alta hace oscilar la iteración de punto fijo --
    debe reportarse converged=False con el último estado alcanzado, no
    lanzar una excepción ni fingir convergencia."""
    result = run_baroreflex(150.0, k=10.0, max_ticks=15)
    assert result.converged is False
    assert len(result.ticks) == 16  # max_ticks intentos + 1 corrida de cierre


# --- Aislamiento stateless -----------------------------------------------------


def test_two_calls_do_not_share_state():
    """Dos llamadas consecutivas con entradas distintas no deben
    contaminarse -- todo el estado del bucle vive en variables locales de
    la llamada (ver docstring de run_baroreflex)."""
    result_a = run_baroreflex(72.0)
    result_b = run_baroreflex(150.0)
    result_a_again = run_baroreflex(72.0)

    assert result_a.final_rd == pytest.approx(result_a_again.final_rd, rel=1e-9)
    assert result_a.final_rd != result_b.final_rd
    assert result_a.heart_rate_bpm == 72.0  # no fue sobrescrito por la llamada intermedia


# --- Solo Rd se modula; Rp/C/Pd del módulo 1 quedan intactos -------------------


def test_only_rd_is_modulated_rp_c_pd_pass_through_unchanged():
    """Reconstruye manualmente la simulación con Rp/C/Pd del set base y
    la Rd final del barórreflejo -- debe reproducir exactamente el
    resultado de run_baroreflex(), confirmando que ningún otro parámetro
    fue tocado por el controlador."""
    heart_rate_bpm = 85.0
    result = run_baroreflex(heart_rate_bpm)

    flow_fn, period_s = physiological_pulsatile_flow(heart_rate_bpm)
    manual_params = dataclasses.replace(PHYSIOLOGICAL_RRCR_PARAMETERS, rd=result.final_rd)
    assert manual_params.rp == PHYSIOLOGICAL_RRCR_PARAMETERS.rp
    assert manual_params.c == PHYSIOLOGICAL_RRCR_PARAMETERS.c
    assert manual_params.pd == PHYSIOLOGICAL_RRCR_PARAMETERS.pd

    manual_result = simulate_r_rcr(flow_fn, manual_params, period_s=period_s, n_cycles=12, n_points_per_cycle=101)
    p_last = manual_result.pressure_inlet[-101:]
    t_last = manual_result.time[-101:]
    manual_map = float(np.trapezoid(p_last, t_last) / (t_last[-1] - t_last[0]))

    assert manual_map == pytest.approx(result.final_map, abs=0.1)


# --- Paso 4: comparación en contexto -------------------------------------------


def test_sepsis_baroreflex_comparison_end_to_end(tmp_path):
    comparison = run_scenario_baroreflex_comparison(SimulationScenario.SEPSIS, db_path=tmp_path / "baroreflex.db")

    assert comparison.scenario == "sepsis"
    assert comparison.pending_validation is False  # BAROREFLEX_PARAMETERS_PENDING_VALIDATION, validado Ronda 2
    assert comparison.dynamic.converged is True
    assert len(comparison.reference) == 3

    rows = comparison.as_table_rows()
    assert len(rows) == 3
    for descriptor, static_val, dynamic_val, ref_val, _citation in rows:
        assert static_val is not None
        assert dynamic_val is not None
        assert ref_val is not None

    # La resistencia dinámica reduce drásticamente el error frente a la
    # referencia en sistólica/diastólica respecto a la resistencia fija
    # (aunque no lo cierre del todo -- ver test de no-circularidad arriba).
    static_systolic = comparison.static_r["systolic_bp"]
    dynamic_systolic = comparison.dynamic.final_systolic_bp
    reference_systolic = next(r.value for r in comparison.reference if r.descriptor == "systolic_bp")
    assert abs(dynamic_systolic - reference_systolic) < abs(static_systolic - reference_systolic)


def test_baroreflex_comparison_handles_scenario_without_reference(tmp_path):
    comparison = run_scenario_baroreflex_comparison(SimulationScenario.FATIGUE, db_path=tmp_path / "baroreflex2.db")
    assert comparison.reference == []
    rows = comparison.as_table_rows()
    for _, static_val, dynamic_val, ref_val, citation in rows:
        assert static_val is not None
        assert dynamic_val is not None
        assert ref_val is None
        assert citation == "sin referencia para este escenario"


def test_baroreflex_comparison_does_not_write_new_ups_descriptors(tmp_path):
    """Aislado: correr la comparación no debe dejar descriptores nuevos de
    barórreflejo en el UPS -- solo lo que run_rich_scenario() ya escribe
    normalmente (heart_rate, hrv, etc. + la PA calculada del módulo 1 NO
    se adjunta aquí tampoco, porque este módulo no llama a
    compute_and_attach_calculated_pressure())."""
    from domain.physiology.state import get_latest_state, init_db, make_engine, make_session_factory

    db_path = tmp_path / "baroreflex_isolation.db"
    run_scenario_baroreflex_comparison(SimulationScenario.HEALTHY, db_path=db_path)

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
