"""
"La película", vertical slice — módulo hemodinámico R-RCR.

Dos niveles de verificación matemática, ambos contra datos REALES de
svZeroDSolver (Stanford/SimVascular, BSD-3-Clause), nunca inventados:

1. Los checkpoints analíticos publicados textualmente en los casos de
   prueba oficiales `steadyFlow_R_RCR.json`/`pulsatileFlow_R_RCR.json`
   (mismos valores que `tests/test_integration.py::test_steady_flow_r_rcr`/
   `test_pulsatile_flow_r_rcr` del paquete oficial).
2. Una muestra de 11 puntos del último ciclo (régimen periódico) extraída
   de una corrida GENUINA del solver oficial (`svzerodsolver`, la
   implementación Python del mismo proyecto) durante esta tanda —
   ver CHANGELOG.md para cómo se obtuvo. No es un valor inventado ni
   recalculado por este mismo módulo (eso sería una verificación circular).
"""

import numpy as np
import pytest

from domain.physiology.hemodynamics import (
    OFFICIAL_PULSATILE_T0_CHECKPOINT,
    OFFICIAL_STEADY_CHECKPOINT,
    RRCRParameters,
    pulsatile_flow_reference,
    simulate_r_rcr,
    steady_flow_reference,
)

# Muestra de 11 puntos del último ciclo (t en [0,1], régimen periódico),
# extraída el 2026-07-19 de una corrida real de `svzerodsolver`
# (SimVascular/svZeroDSolver-Archived) sobre pulsatileFlow_R_RCR.json.
# Formato: (t, flow, pressure_inlet, pressure_outlet).
REAL_SOLVER_LAST_CYCLE_SAMPLE = [
    (0.0000, 2.199999, 3493.642848, 3273.642935),
    (0.1000, 3.669522, 6378.668827, 6011.716591),
    (0.2000, 4.577738, 8591.943090, 8134.169290),
    (0.3000, 4.577739, 9288.070094, 8830.296240),
    (0.4000, 3.669524, 8201.152983, 7834.200606),
    (0.5000, 2.200001, 5746.357152, 5526.357065),
    (0.6000, 0.730478, 2861.331173, 2788.283409),
    (0.7000, -0.177738, 648.056910, 665.830710),
    (0.8000, -0.177739, -48.070094, -30.296240),
    (0.9000, 0.730476, 1038.847017, 965.799394),
    (1.0000, 2.199999, 3493.642848, 3273.642935),
]


def test_default_parameters_match_official_test_case():
    """Los parámetros por defecto no son inventados -- son los del caso
    oficial steadyFlow_R_RCR.json/pulsatileFlow_R_RCR.json."""
    p = RRCRParameters()
    assert p.r_poiseuille == 100.0
    assert p.rp == 1000.0
    assert p.c == 0.0001
    assert p.rd == 1000.0
    assert p.pd == 0.0


def test_steady_flow_reproduces_official_analytical_checkpoint():
    result = simulate_r_rcr(steady_flow_reference(5.0), n_cycles=1, n_points_per_cycle=3)
    assert result.flow[0] == pytest.approx(OFFICIAL_STEADY_CHECKPOINT["flow"])
    assert result.pressure_inlet[0] == pytest.approx(OFFICIAL_STEADY_CHECKPOINT["pressure_inlet"], abs=1e-6)
    assert result.pressure_outlet[0] == pytest.approx(OFFICIAL_STEADY_CHECKPOINT["pressure_outlet"], abs=1e-6)


def test_steady_flow_stays_constant_at_steady_state():
    """A flujo constante, la presión no debe variar en el tiempo -- el
    capacitor ya está en su condición de carga estacionaria desde t=0."""
    result = simulate_r_rcr(steady_flow_reference(5.0), n_cycles=3, n_points_per_cycle=50)
    assert np.allclose(result.pressure_inlet, result.pressure_inlet[0], atol=1e-6)
    assert np.allclose(result.pressure_outlet, result.pressure_outlet[0], atol=1e-6)


def test_pulsatile_flow_reproduces_official_analytical_checkpoint_at_t0():
    result = simulate_r_rcr(pulsatile_flow_reference, n_cycles=10, n_points_per_cycle=201)
    assert result.flow[0] == pytest.approx(OFFICIAL_PULSATILE_T0_CHECKPOINT["flow"], abs=1e-9)
    assert result.pressure_inlet[0] == pytest.approx(OFFICIAL_PULSATILE_T0_CHECKPOINT["pressure_inlet"], abs=1e-6)
    assert result.pressure_outlet[0] == pytest.approx(OFFICIAL_PULSATILE_T0_CHECKPOINT["pressure_outlet"], abs=1e-6)


def test_pulsatile_flow_converged_cycle_matches_real_official_solver_output():
    """Verificación más fuerte: no solo el checkpoint t=0, sino la forma
    completa de la curva dinámica convergida, contra una corrida GENUINA
    del solver oficial (no una referencia recalculada por este módulo)."""
    result = simulate_r_rcr(pulsatile_flow_reference, n_cycles=10, n_points_per_cycle=201)

    last_cycle_time = result.time[-201:] - result.time[-201]
    last_cycle_p_in = result.pressure_inlet[-201:]
    last_cycle_p_out = result.pressure_outlet[-201:]
    last_cycle_q = result.flow[-201:]

    for t_ref, q_ref, p_in_ref, p_out_ref in REAL_SOLVER_LAST_CYCLE_SAMPLE:
        idx = int(round(t_ref * 200))
        assert last_cycle_q[idx] == pytest.approx(q_ref, abs=1e-3)
        # Tolerancia de 0.5: diferencia de esquema numerico (Radau adaptativo
        # aqui vs. generalized-alpha de paso fijo en el solver oficial), no
        # una discrepancia de modelo -- ver docstring de r_rcr.py.
        assert last_cycle_p_in[idx] == pytest.approx(p_in_ref, abs=0.5)
        assert last_cycle_p_out[idx] == pytest.approx(p_out_ref, abs=0.5)
    # Confirma que efectivamente estamos comparando en los mismos instantes.
    assert last_cycle_time[0] == pytest.approx(0.0, abs=1e-9)
    assert last_cycle_time[-1] == pytest.approx(1.0, abs=1e-9)


def test_higher_resistance_raises_pressure_for_same_flow():
    """Sanity check estructural (no fisiológico): a mayor resistencia, mayor
    presión para el mismo flujo -- P = P_c + R*Q es monótona creciente en R."""
    low_r = simulate_r_rcr(steady_flow_reference(5.0), RRCRParameters(r_poiseuille=50.0), n_cycles=1, n_points_per_cycle=3)
    high_r = simulate_r_rcr(steady_flow_reference(5.0), RRCRParameters(r_poiseuille=200.0), n_cycles=1, n_points_per_cycle=3)
    assert high_r.pressure_inlet[0] > low_r.pressure_inlet[0]


def test_higher_compliance_slows_the_transient_not_the_steady_value():
    """La compliancia no cambia el valor final en estado estacionario (mismo
    P_c0 por construccion), pero sí cuánto tarda en amortiguarse una
    perturbacion -- verificado aquí sobre un escalon de flujo, no sobre el
    caso periodico de referencia."""
    params_low_c = RRCRParameters(c=0.0001)
    params_high_c = RRCRParameters(c=0.01)

    def step_flow(t):
        return 5.0 if t < 0.5 else 8.0

    low_c_result = simulate_r_rcr(step_flow, params_low_c, n_cycles=1, n_points_per_cycle=201)
    high_c_result = simulate_r_rcr(step_flow, params_high_c, n_cycles=1, n_points_per_cycle=201)

    # Justo después del escalón (t=0.5), la compliancia alta debe haber
    # cambiado menos (más lenta) que la compliancia baja.
    idx_just_after = 101  # t ~ 0.505
    low_c_change = abs(low_c_result.pressure_inlet[idx_just_after] - low_c_result.pressure_inlet[100])
    high_c_change = abs(high_c_result.pressure_inlet[idx_just_after] - high_c_result.pressure_inlet[100])
    assert high_c_change < low_c_change


def test_result_arrays_have_consistent_shapes():
    result = simulate_r_rcr(pulsatile_flow_reference, n_cycles=2, n_points_per_cycle=51)
    n = len(result.time)
    assert len(result.flow) == n
    assert len(result.pressure_inlet) == n
    assert len(result.pressure_outlet) == n
    assert len(result.pressure_capacitor) == n
