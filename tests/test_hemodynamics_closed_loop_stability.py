"""
"La película" — Estabilidad del lazo a HR alto: sub-relajación (2026-08-01).

Contexto: el "Reconocimiento" de los 9 escenarios no validados reveló que
el lazo cerrado entraba en un ciclo límite de periodo 2 para HR por
encima de ~95-98 bpm (escenario "healthy"). Diagnóstico confirmado
(análisis de ganancia local dM/dRd, con y sin el acoplamiento SV-Rd):
`BAROREFLEX_GAIN_K` (Módulo 2) queda EXONERADO -- el barórreflejo
aislado (SV fija) no oscila en ningún HR probado, hasta 220. La causa es
el acoplamiento Rd->retorno venoso->SV (`_resistance_to_venous_return_mmhg_s_ml`
× `stroke_volume_frank_starling`) duplicando la ganancia efectiva del
lazo, amplificación que crece con HR porque el EDV de equilibrio es menor
(curva de Frank-Starling más empinada).

Solución: sub-relajación del paso combinado (`CLOSED_LOOP_RELAXATION_FACTOR`)
-- una constante NUMÉRICA de convergencia, no fisiológica, sin bandera
`PENDING_VALIDATION`. Matemáticamente no puede mover el punto fijo (la
ecuación de equilibrio no depende de ella) -- solo cambia la trayectoria.

Este archivo cubre: la naturaleza no-fisiológica de la constante, que los
tres puntos fijos ya validados (sano/hipertensión/sepsis) dan EXACTAMENTE
el mismo equilibrio que antes de la sub-relajación (sin oscilar), que el
rango completo de HR (72-220) converge ahora, y la instrumentación
candidato-vs-amortiguado (`rd_candidate` vs `rd_after`).
"""

import pytest

from domain.physiology.hemodynamics.baroreflex import BAROREFLEX_GAIN_K
from domain.physiology.hemodynamics.closed_loop import (
    CLOSED_LOOP_RELAXATION_FACTOR,
    run_closed_loop,
)
from domain.physiology.hemodynamics.pathological_tone import SEPSIS_MAX_RD_MMHG_S_ML


# --- La constante es numérica, no fisiológica ------------------------------------


def test_relaxation_factor_is_a_fraction_strictly_between_zero_and_one():
    assert 0.0 < CLOSED_LOOP_RELAXATION_FACTOR < 1.0


def test_relaxation_factor_documented_as_non_physiological_numerical_control():
    import domain.physiology.hemodynamics.closed_loop as cl_module

    source = open(cl_module.__file__, encoding="utf-8").read()
    assert "CONTROL NUMÉRICO DE CONVERGENCIA" in source
    assert "NO ES UN PARÁMETRO FISIOLÓGICO" in source


def test_relaxation_factor_has_no_pending_validation_flag():
    """A diferencia de todos los parámetros fisiológicos de la serie, esta
    constante no tiene (ni necesita) una bandera PENDING_VALIDATION propia
    -- mismo tratamiento que CLOSED_LOOP_MAX_TICKS/CLOSED_LOOP_CONVERGENCE_TOL."""
    import domain.physiology.hemodynamics.closed_loop as cl_module

    assert not hasattr(cl_module, "CLOSED_LOOP_RELAXATION_FACTOR_PENDING_VALIDATION")


def test_baroreflex_gain_k_untouched_by_the_stability_fix():
    """Exoneración confirmada: la solución vive enteramente en
    closed_loop.py -- BAROREFLEX_GAIN_K (Módulo 2) sigue en su valor
    validado, sin tocar."""
    assert BAROREFLEX_GAIN_K == pytest.approx(1.0)


# --- Los tres puntos fijos validados: MISMO equilibrio, ya sin oscilar ---------


def test_healthy_fixed_point_unchanged_converges_without_oscillation():
    r = run_closed_loop("healthy", 72.0)
    assert r.converged is True
    assert r.oscillated is False
    assert r.final_map == pytest.approx(93.333, abs=0.01)
    assert r.final_stroke_volume_ml == pytest.approx(70.0, abs=0.5)
    assert r.final_systolic_bp == pytest.approx(113.3, abs=0.5)
    assert r.final_diastolic_bp == pytest.approx(73.3, abs=0.5)


def test_hypertension_fixed_point_unchanged_converges_without_oscillation():
    r = run_closed_loop("hypertension", 85.0)
    assert r.converged is True
    assert r.oscillated is False
    assert r.final_map == pytest.approx(102.67, abs=0.1)
    assert r.clamped_at_max_rd is False
    assert r.clamped_at_min_rd is False


def test_sepsis_fixed_point_unchanged_still_saturates_ceiling_no_oscillation():
    r = run_closed_loop("sepsis", 150.0)
    assert r.converged is True
    assert r.oscillated is False
    assert r.final_map == pytest.approx(24.2, abs=0.5)
    assert r.final_map < 65.0  # sigue por debajo del umbral de shock de Sepsis-3
    assert r.clamped_at_max_rd is True  # el reflejo sigue saturando su techo -- mecanismo intacto


# --- Rango completo de HR: converge sin oscilar hasta 220 -----------------------


@pytest.mark.parametrize(
    "heart_rate_bpm",
    [88.0, 95.0, 98.0, 100.0, 105.0, 110.0, 115.0, 120.0, 123.3, 130.0, 150.0, 180.0, 200.0, 220.0],
)
def test_full_hr_range_converges_without_oscillation(heart_rate_bpm):
    """Antes de la sub-relajación, HR>=98 en el escenario 'healthy' entraba
    en un ciclo límite de periodo 2 y nunca convergía. Ahora debe converger
    en todo el rango probado, sin oscilar, con el mismo target_map fijo
    (93.33, healthy no tiene override de escenario)."""
    r = run_closed_loop("healthy", heart_rate_bpm)
    assert r.converged is True
    assert r.oscillated is False
    assert r.final_map == pytest.approx(93.33, abs=1.0)


# --- Instrumentación candidato vs. amortiguado -----------------------------------


def test_rd_candidate_differs_from_damped_rd_after_when_relaxation_is_active():
    r = run_closed_loop("hypertension", 85.0)
    assert any(abs(t.rd_candidate - t.rd_after) > 1e-6 for t in r.ticks)


def test_damping_moves_exactly_the_documented_fraction_toward_the_candidate():
    r = run_closed_loop("hypertension", 85.0)
    first_tick = r.ticks[0]
    expected_damped = first_tick.rd_before + CLOSED_LOOP_RELAXATION_FACTOR * (
        first_tick.rd_candidate - first_tick.rd_before
    )
    assert first_tick.rd_after == pytest.approx(expected_damped, rel=1e-9)


def test_sepsis_candidate_saturates_ceiling_exactly_while_damped_value_approaches_asymptotically():
    """La razón por la que clamped_at_max_rd se lee del candidato crudo, no
    del Rd amortiguado -- verificado directamente aquí."""
    r = run_closed_loop("sepsis", 150.0)
    last = r.ticks[-1]
    assert last.rd_candidate == pytest.approx(SEPSIS_MAX_RD_MMHG_S_ML, abs=1e-3)
    assert last.rd_after < SEPSIS_MAX_RD_MMHG_S_ML  # amortiguado: se acerca, no coincide exacto
    assert last.clamped_at_max_rd is True


def test_convergence_is_much_faster_with_damping_than_the_old_undamped_oscillating_case():
    """Efecto colateral honesto, no buscado pero verificado: la sub-relajación
    también acelera la convergencia en casos que antes eran lentos (cerca
    del viejo umbral de oscilación), no solo estabiliza los que oscilaban."""
    r = run_closed_loop("healthy", 95.0)  # antes: 38 ticks, al límite de converger
    assert len(r.ticks) < 20
