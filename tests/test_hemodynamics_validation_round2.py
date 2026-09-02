"""
"La película" — Validación cuantitativa, Ronda 2, "cosecha final" (2026-07-31).

Cubre el dictamen del validador experto sobre los ~13 parámetros que
quedaban pendientes tras Ronda 1, y la baja de banderas resultante:

- Registro de cada dictamen con su NATURALEZA correcta: cita directa
  (Pd, target_map, EDV_FLOOR_ML, HYPERTENSION_RESET_TARGET_MAP_MMHG,
  SEPSIS_MAX_RD/SEPSIS_GAIN_K, Rp/Rd) vs. forma validada
  (FRANK_STARLING_STEEPNESS_ML, DIASTASIS_TRANSITION_BUDGET_ML,
  RVR_REFERENCE_MMHG_S_ML) vs. umbral heurístico aceptado, explícitamente
  NO una cita (VENOUS_CAPACITANCE_SEPSIS_MULTIPLIER) -- no inflar un
  umbral a cita fue una regla explícita de esta ronda.
- Cinco banderas bajan enteras: BAROREFLEX_PARAMETERS_PENDING_VALIDATION,
  PATHOLOGICAL_TONE_PENDING_VALIDATION, FRANK_STARLING_PARAMETERS_PENDING_VALIDATION,
  DIASTASIS_CEILING_PENDING_VALIDATION, VENOUS_RETURN_PARAMETERS_PENDING_VALIDATION.
- Una bandera queda arriba, reducida a un solo parámetro:
  PHYSIOLOGICAL_PARAMETERS_PENDING_VALIDATION (solo por C=0.807,
  pendiente estructural).
- Los guards "no cambiar sin revisión" que vivían en cada función
  (`run_baroreflex`, `run_pathological_baroreflex`,
  `stroke_volume_frank_starling`, `apply_diastasis_ceiling`,
  `compute_dynamic_stroke_volume_with_diastasis_ceiling`, `run_closed_loop`)
  se retiraron conscientemente -- se verifica que las funciones siguen
  operando con normalidad, sin regresión en los resultados.

Nota de rendimiento: varios tests de este archivo corren el lazo cerrado
completo (`run_closed_loop`) -- caro. Se reutilizan fixtures de módulo
donde es posible.
"""

import pytest

from domain.physiology.hemodynamics.baroreflex import (
    BAROREFLEX_GAIN_K,
    BAROREFLEX_MAX_RD,
    BAROREFLEX_MIN_RD,
    BAROREFLEX_PARAMETERS_PENDING_VALIDATION,
    BAROREFLEX_TARGET_MAP_MMHG,
    run_baroreflex,
)
from domain.physiology.hemodynamics.closed_loop import (
    P_SF_HEALTHY_MMHG,
    RVR_REFERENCE_MMHG_S_ML,
    VENOUS_CAPACITANCE_SEPSIS_MULTIPLIER,
    VENOUS_RETURN_PARAMETERS_PENDING_VALIDATION,
    run_closed_loop,
)
from domain.physiology.hemodynamics.diastasis_ceiling import (
    DIASTASIS_CEILING_PENDING_VALIDATION,
    DIASTASIS_TRANSITION_BUDGET_ML,
    EDV_ANATOMICAL_CEILING_ML,
    apply_diastasis_ceiling,
    compute_dynamic_stroke_volume_with_diastasis_ceiling,
)
from domain.physiology.hemodynamics.frank_starling import (
    EDV_FLOOR_ML,
    EDV_HEALTHY_ML,
    FRANK_STARLING_PARAMETERS_PENDING_VALIDATION,
    FRANK_STARLING_STEEPNESS_ML,
    STROKE_VOLUME_REFERENCE_ML,
    VENOUS_RETURN_PLACEHOLDER_PENDING_MODULE_4B,
    stroke_volume_frank_starling,
)
from domain.physiology.hemodynamics.pathological_tone import (
    HYPERTENSION_RESET_TARGET_MAP_MMHG,
    PATHOLOGICAL_TONE_PENDING_VALIDATION,
    SEPSIS_GAIN_K,
    SEPSIS_MAX_RD_MMHG_S_ML,
    run_pathological_baroreflex,
)
from domain.physiology.hemodynamics.physiological_flow import (
    PHYSIOLOGICAL_PARAMETERS_PENDING_VALIDATION,
    PHYSIOLOGICAL_RRCR_PARAMETERS,
)


def _source(module) -> str:
    return open(module.__file__, encoding="utf-8").read()


# --- Cinco banderas bajan enteras ------------------------------------------------


def test_five_flags_fully_cleared_in_round_2():
    assert BAROREFLEX_PARAMETERS_PENDING_VALIDATION is False
    assert PATHOLOGICAL_TONE_PENDING_VALIDATION is False
    assert FRANK_STARLING_PARAMETERS_PENDING_VALIDATION is False
    assert DIASTASIS_CEILING_PENDING_VALIDATION is False
    assert VENOUS_RETURN_PARAMETERS_PENDING_VALIDATION is False


def test_physiological_parameters_flag_stays_up_reduced_to_only_c():
    """La única bandera que NO baja entera -- reducida a un solo
    parámetro (la compliancia C), no a los cinco que cubría antes."""
    assert PHYSIOLOGICAL_PARAMETERS_PENDING_VALIDATION is True

    import domain.physiology.hemodynamics.physiological_flow as pf_module

    source = _source(pf_module)
    assert "solo por C" in source or "único que falta" in source


def test_orphaned_placeholder_flag_untouched_by_round_2():
    """VENOUS_RETURN_PLACEHOLDER_PENDING_MODULE_4B (retirada del flujo
    activo en Ronda 1) no fue tocada en Ronda 2 -- sigue en True, sin
    relación con las cinco banderas que sí bajaron."""
    assert VENOUS_RETURN_PLACEHOLDER_PENDING_MODULE_4B is True


# --- Naturaleza correcta de cada dictamen: cita directa --------------------------


def test_pd_validated_as_direct_citation_with_emergent_5mmhg_gradient_note():
    import domain.physiology.hemodynamics.physiological_flow as pf_module

    source = _source(pf_module)
    assert "VALIDADO" in source
    assert "5.0 mmHg" in source or "5 mmHg" in source
    assert PHYSIOLOGICAL_RRCR_PARAMETERS.pd == pytest.approx(2.0)
    assert P_SF_HEALTHY_MMHG - PHYSIOLOGICAL_RRCR_PARAMETERS.pd == pytest.approx(5.0)


def test_rp_rd_validated_total_citable_split_form_validated():
    import domain.physiology.hemodynamics.physiological_flow as pf_module

    source = _source(pf_module)
    assert "VALIDADO" in source
    assert "Westerhof" in source
    rpt_total = PHYSIOLOGICAL_RRCR_PARAMETERS.rp + PHYSIOLOGICAL_RRCR_PARAMETERS.rd
    assert rpt_total == pytest.approx(1.0873, abs=1e-3)  # ~1 PRU, Guyton


def test_baroreflex_target_map_validated_as_derivation_of_already_cited_bp():
    import domain.physiology.hemodynamics.baroreflex as baroreflex_module

    source = _source(baroreflex_module)
    assert "VALIDADO" in source
    assert "ACC/AHA" in source
    assert BAROREFLEX_TARGET_MAP_MMHG == pytest.approx(93.33333, abs=1e-4)


def test_baroreflex_gain_k_validated_as_sensible_control_gain():
    import domain.physiology.hemodynamics.baroreflex as baroreflex_module

    source = _source(baroreflex_module)
    assert "VALIDADO" in source
    assert BAROREFLEX_GAIN_K == pytest.approx(1.0)


def test_edv_floor_validated_below_normal_esv_range():
    import domain.physiology.hemodynamics.frank_starling as fs_module

    source = _source(fs_module)
    assert "VALIDADO" in source
    assert EDV_FLOOR_ML == pytest.approx(20.0)
    assert EDV_FLOOR_ML < 40.0  # por debajo del rango normal de VTS (~40-50 mL)


def test_hypertension_reset_target_map_validated_as_sustained_stage1():
    import domain.physiology.hemodynamics.pathological_tone as pt_module

    source = _source(pt_module)
    assert "VALIDADO" in source
    assert HYPERTENSION_RESET_TARGET_MAP_MMHG == pytest.approx(102.66667, abs=1e-4)


def test_sepsis_max_rd_and_gain_k_validated_together_as_refractory_shock_degree():
    import domain.physiology.hemodynamics.pathological_tone as pt_module

    source = _source(pt_module)
    assert "VALIDADO" in source
    assert "30-50%" in source
    assert SEPSIS_MAX_RD_MMHG_S_ML == pytest.approx(BAROREFLEX_MAX_RD * 0.5)
    assert SEPSIS_GAIN_K == pytest.approx(BAROREFLEX_GAIN_K * 0.3)


# --- Naturaleza correcta de cada dictamen: forma validada (NO cita de magnitud) --


def test_frank_starling_steepness_form_validated_not_a_magnitude_citation():
    import domain.physiology.hemodynamics.frank_starling as fs_module

    source = _source(fs_module)
    assert "FORMA VALIDADA" in source
    assert "actina-miosina" in source or "sarcómero" in source
    assert FRANK_STARLING_STEEPNESS_ML == pytest.approx(144.26950, abs=1e-3)


def test_diastasis_transition_budget_form_validated_not_a_magnitude_citation():
    import domain.physiology.hemodynamics.diastasis_ceiling as dc_module

    source = _source(dc_module)
    assert "FORMA VALIDADA" in source
    assert "asintótica" in source or "asintótico" in source
    assert DIASTASIS_TRANSITION_BUDGET_ML == pytest.approx(60.0)


def test_rvr_reference_form_validated_as_unique_ohms_law_solution():
    import domain.physiology.hemodynamics.closed_loop as cl_module

    source = _source(cl_module)
    assert "FORMA VALIDADA" in source
    assert "Ohm" in source
    assert RVR_REFERENCE_MMHG_S_ML == pytest.approx(0.034722, abs=1e-5)


# --- Naturaleza correcta: umbral heurístico aceptado, NO cita directa -----------


def test_venous_capacitance_multiplier_registered_as_heuristic_not_citation():
    """Regla explícita de esta ronda: no inflar un umbral a "cita". El
    validador aclaró que no hay cifra universal para esto -- debe quedar
    registrado como tal, no disfrazado de cita de Guyton."""
    import domain.physiology.hemodynamics.closed_loop as cl_module

    source = _source(cl_module)
    assert "UMBRAL HEURÍSTICO ACEPTADO" in source
    assert "NO CITA DIRECTA" in source or "NO ES CITA DIRECTA" in source or "no cita directa" in source.lower()
    assert VENOUS_CAPACITANCE_SEPSIS_MULTIPLIER == pytest.approx(2.0)


def test_rd_rvr_coupling_validated_officially_with_alpha1_citation():
    import domain.physiology.hemodynamics.closed_loop as cl_module

    source = _source(cl_module)
    assert "VALIDADO OFICIALMENTE" in source
    assert "alfa-1" in source or "alpha-1" in source.lower()


# --- Casos mantenidos pendientes, honestos ---------------------------------------


def test_compliance_c_remains_pending_structural_untouched_value():
    assert PHYSIOLOGICAL_RRCR_PARAMETERS.c == pytest.approx(0.8073)
    import domain.physiology.hemodynamics.physiological_flow as pf_module

    source = _source(pf_module)
    assert "PENDIENTE ESTRUCTURAL" in source


def test_r_poiseuille_remains_pending_accepted_simplification():
    assert PHYSIOLOGICAL_RRCR_PARAMETERS.r_poiseuille == pytest.approx(0.0)
    import domain.physiology.hemodynamics.physiological_flow as pf_module

    source = _source(pf_module)
    assert "simplificación aceptada" in source


# --- Guards retirados, funciones siguen operando sin regresión ------------------


def test_run_baroreflex_operates_normally_after_guard_removal():
    result = run_baroreflex(72.0)
    assert result.converged is True
    assert result.final_map == pytest.approx(93.33, abs=0.5)


def test_run_pathological_baroreflex_operates_normally_after_guard_removal():
    result = run_pathological_baroreflex("sepsis", 150.0)
    assert result.converged is True


def test_stroke_volume_frank_starling_operates_normally_after_guard_removal():
    assert stroke_volume_frank_starling(EDV_HEALTHY_ML) == pytest.approx(STROKE_VOLUME_REFERENCE_ML, abs=0.01)


def test_apply_diastasis_ceiling_operates_normally_after_guard_removal():
    assert apply_diastasis_ceiling(EDV_HEALTHY_ML) == pytest.approx(EDV_HEALTHY_ML)
    assert apply_diastasis_ceiling(300.0) < EDV_ANATOMICAL_CEILING_ML


def test_compute_dynamic_stroke_volume_with_diastasis_ceiling_operates_normally():
    result = compute_dynamic_stroke_volume_with_diastasis_ceiling(40.0)
    assert result.stroke_volume_ml == pytest.approx(89.77, abs=0.1)


def test_closed_loop_reproduces_anchor_exactly_no_regression():
    result = run_closed_loop("healthy", 72.0)
    assert result.converged is True
    assert len(result.ticks) == 1
    assert result.final_map == pytest.approx(93.33, abs=0.5)
    assert result.final_stroke_volume_ml == pytest.approx(70.0, abs=0.5)


def test_closed_loop_hypertension_matches_pre_round2_result_no_regression():
    """Hipertensión no depende de ningún parámetro dictaminado en Ronda 2
    -- debe dar exactamente lo mismo que tras la corrección de Ronda 1."""
    result = run_closed_loop("hypertension", 85.0)
    assert result.converged is True
    assert result.clamped_at_max_rd is False
    assert result.final_map == pytest.approx(102.67, abs=0.5)


def test_closed_loop_sepsis_still_collapses_toward_shock_no_regression():
    result = run_closed_loop("sepsis", 150.0)
    assert result.converged is True
    assert result.clamped_at_max_rd is True
    assert result.final_map < 65.0
    assert result.final_map < 93.33
