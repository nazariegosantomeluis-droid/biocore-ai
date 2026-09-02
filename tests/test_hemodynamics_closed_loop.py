"""
"La película" — Módulo 4B-ii (2026-07-30): retorno venoso real + cierre
del lazo completo.

Cubre: mecanismo citado (Guyton) vs. parámetros nuevos marcados
pendientes, salvaguarda anti-circularidad MÁXIMA (ningún parámetro nuevo
se deriva de ninguna PA de referencia, verificado explícitamente), el
ancla de reposo reproducida exactamente con el lazo cerrado (tick único),
la conexión estructural (no hardcodeada) entre la vasoplejía de sepsis
(Módulo 3) y la caída de P_sf, instrumentación de la traza tick-a-tick,
detección de oscilación, no-convergencia honesta, aislamiento total
(sin UPS/sesión), y el hallazgo central: sepsis colapsa hacia el shock,
hipertensión no, con los mismos parámetros fijados a ciegas.

Nota de rendimiento: cada llamada a `run_closed_loop()` con un escenario
que se aleja del ancla puede tardar decenas de segundos (encadena
múltiples simulaciones R-RCR reales por tick). Los tres escenarios
"titulares" (sano/hipertensión/sepsis) se computan UNA sola vez cada uno
vía fixtures de módulo, reutilizados por todos los tests que los
necesitan -- no se repite el cómputo por test.
"""

import pytest

from domain.physiology.hemodynamics.closed_loop import (
    CLOSED_LOOP_CONVERGENCE_TOL,
    CLOSED_LOOP_MAX_TICKS,
    P_SF_HEALTHY_MMHG,
    RD_BASE_MMHG_S_ML,
    RVR_REFERENCE_MMHG_S_ML,
    VENOUS_CAPACITANCE_SEPSIS_MULTIPLIER,
    VENOUS_RETURN_MECHANISM_CITATION,
    VENOUS_RETURN_PARAMETERS_PENDING_VALIDATION,
    ClosedLoopTick,
    _detect_oscillation,
    _p_sf_effective_mmhg,
    _resistance_to_venous_return_mmhg_s_ml,
    _solve_rvr_reference_mmhg_s_ml,
    run_closed_loop,
)
from domain.physiology.hemodynamics.frank_starling import EDV_HEALTHY_ML, HEART_RATE_ANCHOR_BPM, STROKE_VOLUME_REFERENCE_ML
from domain.physiology.hemodynamics.pathological_tone import PATHOLOGICAL_TONE_OVERRIDES


# --- Fixtures: computar cada escenario titular una sola vez ---------------------


@pytest.fixture(scope="module")
def healthy_result():
    return run_closed_loop("healthy", HEART_RATE_ANCHOR_BPM)


@pytest.fixture(scope="module")
def hypertension_result():
    return run_closed_loop("hypertension", 85.0)


@pytest.fixture(scope="module")
def sepsis_result():
    return run_closed_loop("sepsis", 150.0)


# --- Mecanismo citado vs. parámetros pendientes ---------------------------------


def test_mechanism_citation_is_non_empty_and_cites_guyton():
    assert "Guyton" in VENOUS_RETURN_MECHANISM_CITATION
    assert len(VENOUS_RETURN_MECHANISM_CITATION) > 20


def test_venous_return_parameters_fully_validated_as_of_round_2():
    """Los tres parámetros de este módulo (P_SF_HEALTHY_MMHG -- Ronda 1;
    RVR_REFERENCE_MMHG_S_ML con forma validada y
    VENOUS_CAPACITANCE_SEPSIS_MULTIPLIER como umbral heurístico aceptado
    -- Ronda 2, 2026-07-31), más el acoplamiento Rd->RVR (validado
    formalmente en Ronda 2), quedaron confirmados -- la bandera bajó a
    False, y los guards que antes vivían en `run_closed_loop()` se
    retiraron conscientemente: el lazo sigue operando con normalidad."""
    assert VENOUS_RETURN_PARAMETERS_PENDING_VALIDATION is False
    result = run_closed_loop("healthy", 72.0)
    assert result.converged is True


# --- Salvaguarda anti-circularidad MÁXIMA ---------------------------------------


def test_new_parameters_are_round_or_solved_from_the_cited_anchor_never_from_bp():
    """P_SF_HEALTHY_MMHG y VENOUS_CAPACITANCE_SEPSIS_MULTIPLIER son
    cifras redondas fijadas por criterio explícito. RVR_REFERENCE_MMHG_S_ML
    es la única resuelta algebraicamente, y se resuelve contra el ancla ya
    citada (72 bpm -> 120 mL), reproducible independientemente."""
    assert P_SF_HEALTHY_MMHG == pytest.approx(7.0)  # Ronda 1: corregido de 10.0 (error) a 7.0 (cita Guyton)
    assert VENOUS_CAPACITANCE_SEPSIS_MULTIPLIER == pytest.approx(2.0)

    period_s_anchor = 60.0 / HEART_RATE_ANCHOR_BPM
    venous_return_needed = EDV_HEALTHY_ML / period_s_anchor
    expected_rvr = (P_SF_HEALTHY_MMHG - 2.0) / venous_return_needed  # Pd=2.0, Módulo 1, sin cambios
    assert RVR_REFERENCE_MMHG_S_ML == pytest.approx(expected_rvr)
    assert RVR_REFERENCE_MMHG_S_ML == pytest.approx(_solve_rvr_reference_mmhg_s_ml())


def test_new_parameters_do_not_coincide_with_any_blood_pressure_reference_value():
    bp_reference_values_mmhg = {65.0, 85.0, 93.3, 96.7, 130.0, 55.0, 80.0, 120.0}
    for value in (P_SF_HEALTHY_MMHG, VENOUS_CAPACITANCE_SEPSIS_MULTIPLIER, RVR_REFERENCE_MMHG_S_ML):
        assert round(value, 1) not in bp_reference_values_mmhg


def test_sepsis_p_sf_is_exactly_healthy_p_sf_divided_by_the_round_multiplier():
    """P_sf de sepsis = P_SF_HEALTHY_MMHG / VENOUS_CAPACITANCE_SEPSIS_MULTIPLIER
    -- fórmula directa, no un número aparte elegido para que la PA
    resultante se acerque a 65 mmHg."""
    assert _p_sf_effective_mmhg("sepsis") == pytest.approx(P_SF_HEALTHY_MMHG / VENOUS_CAPACITANCE_SEPSIS_MULTIPLIER)
    assert _p_sf_effective_mmhg("sepsis") == pytest.approx(3.5)  # Ronda 1: 7.0/2.0 (antes 10.0/2.0=5.0)


def test_p_sf_effective_is_unaffected_for_scenarios_without_arterial_vasoplegia():
    for scenario in ("healthy", "hypertension", "arrhythmia", "exercise"):
        assert _p_sf_effective_mmhg(scenario) == pytest.approx(P_SF_HEALTHY_MMHG)


def test_venous_capacitance_connection_is_structural_not_a_hardcoded_string_check():
    """Verifica que la conexión con el Módulo 3 lee
    PATHOLOGICAL_TONE_OVERRIDES (estructural) -- confirmado indirectamente:
    hoy sepsis es el ÚNICO escenario con `max_rd` en el override, y es el
    ÚNICO cuya P_sf efectiva difiere de la basal."""
    scenarios_with_arterial_vasoplegia = {
        scenario for scenario, override in PATHOLOGICAL_TONE_OVERRIDES.items() if override.max_rd is not None
    }
    assert scenarios_with_arterial_vasoplegia == {"sepsis"}
    for scenario in scenarios_with_arterial_vasoplegia:
        assert _p_sf_effective_mmhg(scenario) < P_SF_HEALTHY_MMHG


def test_rd_to_rvr_coupling_direction_is_inverse_venoconstriction_helps_return():
    """La dirección elegida (documentada en closed_loop.py tras probar
    ambas y descartar la que colapsaba TODOS los escenarios): más Rd ->
    menos RVR -> más facilidad de retorno."""
    rvr_at_base = _resistance_to_venous_return_mmhg_s_ml(RD_BASE_MMHG_S_ML)
    rvr_at_higher_rd = _resistance_to_venous_return_mmhg_s_ml(RD_BASE_MMHG_S_ML * 1.5)
    rvr_at_lower_rd = _resistance_to_venous_return_mmhg_s_ml(RD_BASE_MMHG_S_ML * 0.5)
    assert rvr_at_base == pytest.approx(RVR_REFERENCE_MMHG_S_ML)
    assert rvr_at_higher_rd < rvr_at_base < rvr_at_lower_rd


# --- Ancla de reposo reproducida exactamente con el lazo cerrado ---------------


def test_resting_anchor_converges_in_a_single_tick_and_reproduces_prior_modules(healthy_result):
    """72 bpm con el lazo COMPLETO cerrado debe reproducir exactamente el
    ancla ya validada en módulos anteriores (120 mL EDV, 70 mL SV, PAM
    93.33) -- el sistema ya está en su punto fijo desde el primer tick,
    porque así se calibró RVR_REFERENCE_MMHG_S_ML."""
    assert healthy_result.converged is True
    assert len(healthy_result.ticks) == 1
    assert healthy_result.final_edv_ml == pytest.approx(EDV_HEALTHY_ML, abs=0.5)
    assert healthy_result.final_stroke_volume_ml == pytest.approx(STROKE_VOLUME_REFERENCE_ML, abs=0.5)
    assert healthy_result.final_map == pytest.approx(93.33, abs=0.5)
    assert healthy_result.clamped_at_min_rd is False
    assert healthy_result.clamped_at_max_rd is False
    assert healthy_result.clamped_at_edv_floor is False


# --- Instrumentación: traza tick a tick -----------------------------------------


def test_trace_exposes_every_intermediate_variable_per_tick(hypertension_result):
    assert len(hypertension_result.ticks) > 1  # hipertensión SÍ necesita varios ticks para asentarse
    for tick in hypertension_result.ticks:
        assert isinstance(tick, ClosedLoopTick)
        assert tick.rd_before > 0
        assert tick.p_sf_effective_mmhg > 0
        assert tick.rvr_mmhg_s_ml > 0
        assert tick.venous_return_ml_s > 0
        assert tick.raw_edv_ml >= 0
        assert tick.corrected_edv_ml >= 0
        assert tick.stroke_volume_ml >= 0
        assert tick.rd_after > 0
        assert tick.map > 0


def test_trace_tick_indices_are_sequential_from_zero():
    result = run_closed_loop("healthy", 90.0)
    for expected_index, tick in enumerate(result.ticks):
        assert tick.tick == expected_index


# --- Reporte por escenario: ¿convergió? ¿en cuántos ticks? ¿osciló? ¿límites? --


def test_hypertension_converges_without_oscillating_or_hitting_limits(hypertension_result):
    assert hypertension_result.converged is True
    assert hypertension_result.oscillated is False
    assert hypertension_result.clamped_at_min_rd is False
    assert hypertension_result.clamped_at_max_rd is False
    assert hypertension_result.clamped_at_edv_floor is False
    assert len(hypertension_result.ticks) < CLOSED_LOOP_MAX_TICKS


def test_sepsis_converges_quickly_but_hits_the_arterial_resistance_ceiling(sepsis_result):
    """La vasoplejía de sepsis (Módulo 3) reduce max_rd -- el barórreflejo
    choca ese techo intentando compensar la PA colapsada; esto es
    fisiología esperada (reflejo saturado), no un error del bucle."""
    assert sepsis_result.converged is True
    assert sepsis_result.clamped_at_max_rd is True
    assert len(sepsis_result.ticks) < CLOSED_LOOP_MAX_TICKS


def test_oscillation_detector_flags_alternating_deltas():
    import dataclasses

    def fake_tick(i, rd_after):
        return ClosedLoopTick(
            tick=i, rd_before=1.0, p_sf_effective_mmhg=10.0, rvr_mmhg_s_ml=0.05,
            venous_return_ml_s=100.0, raw_edv_ml=100.0, corrected_edv_ml=100.0,
            diastasis_ceiling_active=False, stroke_volume_ml=60.0, rd_candidate=rd_after, rd_after=rd_after,
            systolic_bp=120.0, diastolic_bp=80.0, map=93.0, clamped_at_min_rd=False, clamped_at_max_rd=False,
        )

    alternating_rds = [1.0, 1.2, 0.9, 1.15, 0.92, 1.1, 0.95]
    oscillating_ticks = [fake_tick(i, rd) for i, rd in enumerate(alternating_rds)]
    assert _detect_oscillation(oscillating_ticks) is True

    monotonic_rds = [1.0, 1.05, 1.09, 1.12, 1.14, 1.15, 1.16]
    monotonic_ticks = [fake_tick(i, rd) for i, rd in enumerate(monotonic_rds)]
    assert _detect_oscillation(monotonic_ticks) is False


def test_non_convergence_is_reported_honestly_not_raised(monkeypatch):
    """Fuerza una tolerancia imposible de satisfacer (0.0 exacto) para
    verificar que agotar max_ticks se reporta como converged=False con el
    último estado, no una excepción -- mismo criterio que
    BAROREFLEX_CONVERGENCE_TOL en Módulo 2."""
    result = run_closed_loop("healthy", 90.0, max_ticks=3, tol=0.0)
    assert result.converged is False
    assert len(result.ticks) == 3


# --- El hallazgo central: sepsis colapsa, hipertensión no ----------------------


def test_sepsis_collapses_toward_shock_hypertension_does_not(hypertension_result, sepsis_result, healthy_result):
    """La pregunta central de esta tanda: con los mismos parámetros
    fijados a ciegas de la referencia clínica, ¿sepsis se desploma
    orgánicamente y hipertensión no? Verificado con los tres escenarios
    ya computados."""
    assert sepsis_result.final_map < healthy_result.final_map
    assert sepsis_result.final_map < hypertension_result.final_map
    assert sepsis_result.final_stroke_volume_ml < healthy_result.final_stroke_volume_ml
    assert hypertension_result.final_map > healthy_result.final_map  # dirección correcta, elevada
    assert hypertension_result.clamped_at_max_rd is False  # hipertensión encuentra equilibrio, no choca límites


# --- Aislamiento -----------------------------------------------------------------


def test_module_has_no_ups_or_session_dependency():
    import domain.physiology.hemodynamics.closed_loop as closed_loop_module

    assert not hasattr(closed_loop_module, "Session")
    names = [name for name in dir(closed_loop_module) if not name.startswith("_")]
    assert "get_latest_state" not in names
    assert "make_session_factory" not in names


def test_two_calls_do_not_share_state():
    result_a = run_closed_loop("healthy", 72.0)
    result_b = run_closed_loop("hypertension", 85.0)
    result_a_again = run_closed_loop("healthy", 72.0)

    assert result_a.final_rd == pytest.approx(result_a_again.final_rd, rel=1e-9)
    assert result_a.final_rd != pytest.approx(result_b.final_rd)
