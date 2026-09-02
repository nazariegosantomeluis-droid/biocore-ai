"""
"La película" — Validación cuantitativa, Ronda 1 (2026-07-30/31).

Cubre las tres operaciones del dictamen del validador experto:

- Operación A: corrección de `P_SF_HEALTHY_MMHG` (10.0 -> 7.0 mmHg, cita
  directa de Guyton) y re-despeje de `RVR_REFERENCE_MMHG_S_ML` -- el ancla
  de reposo (72 bpm -> 120 mL -> 70 mL -> PAM 93.33) sobrevive intacta
  (verificado también en `test_hemodynamics_closed_loop.py`); sano/
  hipertensión quedan algebraicamente INDEPENDIENTES de P_sf (el término
  `P_sf-Pd` se cancela cuando `P_sf_effective == P_SF_HEALTHY_MMHG`); sepsis
  sí cambia, porque su P_sf efectiva es una FRACCIÓN de `P_SF_HEALTHY_MMHG`
  (el multiplicador de capacitancia no cancela).
- Operación B: cinco parámetros (`BAROREFLEX_MIN_RD`, `BAROREFLEX_MAX_RD`,
  `EDV_HEALTHY_ML`, `SV_MAX_ML`, `EDV_ANATOMICAL_CEILING_ML`) quedaron
  validados con cita de Guyton -- pero NINGUNA de las tres banderas que
  los cubren baja entera, porque cada una tiene al menos un parámetro
  hermano sin confirmar. Verificado explícitamente aquí.
- Operación C: `VENOUS_RETURN_PLACEHOLDER_PENDING_MODULE_4B` queda
  retirada del flujo de validación activo (superseded por el retorno
  venoso real de `closed_loop.py`), sin borrar código ni marcarlo
  silenciosamente como productivo.

No repite las pruebas de mecanismo/anti-circularidad ya cubiertas en los
archivos de cada módulo -- solo las de ESTA ronda de dictamen.
"""

import pytest

from domain.physiology.hemodynamics.baroreflex import (
    BAROREFLEX_GAIN_K,
    BAROREFLEX_MAX_RD,
    BAROREFLEX_MIN_RD,
    BAROREFLEX_TARGET_MAP_MMHG,
)
from domain.physiology.hemodynamics.closed_loop import (
    P_SF_HEALTHY_MMHG,
    RVR_REFERENCE_MMHG_S_ML,
    _p_sf_effective_mmhg,
    _solve_rvr_reference_mmhg_s_ml,
    _venous_return_step,
    run_closed_loop,
)
from domain.physiology.hemodynamics.diastasis_ceiling import (
    DIASTASIS_TRANSITION_BUDGET_ML,
    EDV_ANATOMICAL_CEILING_ML,
)
from domain.physiology.hemodynamics.frank_starling import (
    EDV_FLOOR_ML,
    EDV_HEALTHY_ML,
    FRANK_STARLING_STEEPNESS_ML,
    HEART_RATE_ANCHOR_BPM,
    STROKE_VOLUME_REFERENCE_ML,
    SV_MAX_ML,
    VENOUS_RETURN_PLACEHOLDER_PENDING_MODULE_4B,
    compute_dynamic_stroke_volume,
    estimate_edv_venous_return_placeholder_pending_module_4b,
)
from domain.physiology.hemodynamics.physiological_flow import PHYSIOLOGICAL_RRCR_PARAMETERS


# --- Operación A: P_sf corregida, ancla intacta, sepsis por mecanismo ----------


def test_p_sf_healthy_corrected_to_guyton_cited_value():
    assert P_SF_HEALTHY_MMHG == pytest.approx(7.0)


def test_p_sf_gradient_over_pd_stays_positive_no_conflict():
    """La corrección no rompió el gradiente de retorno -- Pd=2.0 (Módulo
    1, sin cambios) sigue siendo menor que P_sf=7.0."""
    pd_reference = PHYSIOLOGICAL_RRCR_PARAMETERS.pd
    assert P_SF_HEALTHY_MMHG > pd_reference


def test_rvr_reference_re_derived_automatically_from_corrected_p_sf():
    recomputed = _solve_rvr_reference_mmhg_s_ml()
    assert RVR_REFERENCE_MMHG_S_ML == pytest.approx(recomputed)
    assert RVR_REFERENCE_MMHG_S_ML == pytest.approx(0.034722, abs=1e-5)  # antes: ≈0.055556


def test_resting_anchor_unaffected_by_p_sf_correction():
    """Verificación crítica del validador: el ancla de reposo sobrevive
    intacta tras la corrección."""
    result = run_closed_loop("healthy", HEART_RATE_ANCHOR_BPM)
    assert result.converged is True
    assert len(result.ticks) == 1
    assert result.final_edv_ml == pytest.approx(EDV_HEALTHY_ML, abs=0.5)
    assert result.final_stroke_volume_ml == pytest.approx(STROKE_VOLUME_REFERENCE_ML, abs=0.5)
    assert result.final_map == pytest.approx(93.33, abs=0.5)


def test_venous_return_algebraically_independent_of_p_sf_when_no_vasoplegia():
    """Propiedad estructural (no una coincidencia): cuando P_sf_effective
    == P_SF_HEALTHY_MMHG (sano/hipertensión, sin vasoplejía), el término
    (P_sf-Pd) se CANCELA entre `_p_sf_effective_mmhg` y
    `RVR_REFERENCE_MMHG_S_ML` -- el retorno venoso queda determinado
    únicamente por Rd_actual/Rd_base, no por P_sf. Por eso hipertensión no
    cambió tras la corrección de Ronda 1."""
    rd_base = PHYSIOLOGICAL_RRCR_PARAMETERS.rd
    for rd_test in (rd_base, rd_base * 1.3, rd_base * 0.7):
        _, _, venous_return_ml_s, _ = _venous_return_step(85.0, rd_test, "hypertension")
        expected = (EDV_HEALTHY_ML / (60.0 / HEART_RATE_ANCHOR_BPM)) * (rd_test / rd_base)
        assert venous_return_ml_s == pytest.approx(expected, rel=1e-6)


def test_sepsis_p_sf_effective_recomputed_after_correction():
    assert _p_sf_effective_mmhg("sepsis") == pytest.approx(3.5)  # 7.0/2.0, antes 10.0/2.0=5.0


def test_sepsis_collapses_more_severely_after_correction_explained_by_gradient_ratio():
    """El colapso de sepsis se hizo MÁS severo tras corregir P_sf (no
    menos) -- explicado algebraicamente, no un efecto misterioso: la
    vasoplejía opera como una FRACCIÓN de P_SF_HEALTHY_MMHG
    (capacitancia x2 -> P_sf a la mitad), y el gradiente base (P_sf-Pd)
    que sostenía esa fracción se achicó (de 8.0 a 5.0 mmHg) al corregir
    P_sf -- la misma fracción de un gradiente más chico deja MENOS
    retorno venoso absoluto, no más. El mecanismo (vasoplejía -> cae
    P_sf -> cae retorno) es el mismo; lo que cambió es la magnitud base
    sobre la que ese mecanismo opera, precisamente porque esa magnitud
    base estaba mal (Operación A)."""
    old_ratio = (5.0 - 2.0) / (10.0 - 2.0)
    new_ratio = (_p_sf_effective_mmhg("sepsis") - 2.0) / (P_SF_HEALTHY_MMHG - 2.0)
    assert new_ratio < old_ratio

    result = run_closed_loop("sepsis", 150.0)
    assert result.converged is True
    assert result.clamped_at_max_rd is True  # el barórreflejo sigue saturado intentando compensar
    assert result.final_map < 47.5  # más severo que el hallazgo previo (P_sf=10, error)
    assert result.final_map < 65.0  # sigue por debajo del umbral de shock de Sepsis-3


def test_sepsis_trace_shows_collapse_originates_in_venous_return_not_baroreflex_gain():
    """Traza tick-a-tick: el colapso se ve EN el retorno venoso (P_sf
    efectiva baja, EDV crudo bajo) desde el primer tick -- no es un
    artefacto tardío del barórreflejo."""
    result = run_closed_loop("sepsis", 150.0)
    first_tick = result.ticks[0]
    assert first_tick.p_sf_effective_mmhg == pytest.approx(3.5)
    assert first_tick.raw_edv_ml < EDV_HEALTHY_ML  # muy por debajo del ancla desde el tick 0
    assert first_tick.stroke_volume_ml < STROKE_VOLUME_REFERENCE_ML


# --- Operación B: parámetros validados, banderas que NO bajan enteras ---------


def test_baroreflex_min_max_rd_values_unchanged_by_the_ronda1_citation():
    """Ronda 1 (2026-07-30) validó MIN_RD/MAX_RD con cita -- registrar la
    cita no cambió los NÚMEROS (siguen siendo los mismos múltiplos de Rd
    base). NOTA: la bandera BAROREFLEX_PARAMETERS_PENDING_VALIDATION que
    esta prueba original verificaba como "sigue en True" pasó a False en
    Ronda 2 (2026-07-31, k/target_map también confirmados) -- ver
    tests/test_hemodynamics_validation_round2.py para ese estado."""
    for constant in (BAROREFLEX_MIN_RD, BAROREFLEX_MAX_RD):
        assert isinstance(constant, float)  # siguen siendo los mismos valores, solo con cita añadida
    assert BAROREFLEX_MIN_RD == pytest.approx(PHYSIOLOGICAL_RRCR_PARAMETERS.rd * 0.3)
    assert BAROREFLEX_MAX_RD == pytest.approx(PHYSIOLOGICAL_RRCR_PARAMETERS.rd * 3.0)
    assert BAROREFLEX_GAIN_K == pytest.approx(1.0)
    assert BAROREFLEX_TARGET_MAP_MMHG == pytest.approx(93.33333, abs=1e-4)


def test_frank_starling_edv_healthy_sv_max_values_unchanged_by_the_ronda1_citation():
    """Mismo criterio que el test anterior, para el eslabón 1. La bandera
    FRANK_STARLING_PARAMETERS_PENDING_VALIDATION pasó a False en Ronda 2
    -- ver tests/test_hemodynamics_validation_round2.py."""
    assert EDV_HEALTHY_ML == pytest.approx(120.0)
    assert SV_MAX_ML == pytest.approx(140.0)
    assert EDV_FLOOR_ML == pytest.approx(20.0)
    assert FRANK_STARLING_STEEPNESS_ML == pytest.approx(144.26950, abs=1e-3)


def test_diastasis_ceiling_values_unchanged_by_the_ronda1_citation():
    """Mismo criterio, para el Módulo 4B-i. La bandera
    DIASTASIS_CEILING_PENDING_VALIDATION pasó a False en Ronda 2 -- ver
    tests/test_hemodynamics_validation_round2.py."""
    assert EDV_ANATOMICAL_CEILING_ML == pytest.approx(180.0)
    assert DIASTASIS_TRANSITION_BUDGET_ML == pytest.approx(60.0)


def test_validated_constants_carry_a_citation_note_in_their_docstrings():
    """No solo el CHANGELOG -- la cita de validación queda registrada en
    el propio código, junto a cada constante confirmada."""
    import domain.physiology.hemodynamics.baroreflex as baroreflex_module
    import domain.physiology.hemodynamics.diastasis_ceiling as diastasis_module
    import domain.physiology.hemodynamics.frank_starling as frank_starling_module

    baroreflex_source = open(baroreflex_module.__file__, encoding="utf-8").read()
    frank_starling_source = open(frank_starling_module.__file__, encoding="utf-8").read()
    diastasis_source = open(diastasis_module.__file__, encoding="utf-8").read()

    assert "VALIDADO" in baroreflex_source and "Ronda 1" in baroreflex_source
    assert "VALIDADO" in frank_starling_source and "Ronda 1" in frank_starling_source
    assert "VALIDADO" in diastasis_source and "Ronda 1" in diastasis_source


# --- Operación C: bandera huérfana retirada, sin código muerto silencioso ------


def test_orphaned_placeholder_flag_still_true_but_documented_as_retired():
    """La bandera NO se apaga silenciosamente (seguiría siendo una
    simplificación no-fisiológica si algo la llamara) -- se documenta como
    retirada del flujo de validación activo."""
    assert VENOUS_RETURN_PLACEHOLDER_PENDING_MODULE_4B is True

    import domain.physiology.hemodynamics.frank_starling as frank_starling_module

    source = open(frank_starling_module.__file__, encoding="utf-8").read()
    assert "RETIRADA DEL FLUJO DE VALIDACIÓN ACTIVO" in source
    assert "DEMO STANDALONE NO PRODUCTIVA" in source


def test_closed_loop_does_not_use_the_orphaned_placeholder():
    """Confirma en código (no solo en prosa) que el lazo cerrado nunca
    llama al placeholder retirado."""
    import domain.physiology.hemodynamics.closed_loop as closed_loop_module

    source = open(closed_loop_module.__file__, encoding="utf-8").read()
    assert "estimate_edv_venous_return_placeholder_pending_module_4b" not in source


def test_standalone_demo_still_functions_for_its_own_isolated_purpose():
    """La demo no productiva sigue siendo código VÁLIDO para su propio
    propósito aislado (eslabón 1 solo, sin el lazo) -- no se rompió al
    documentarla como no productiva."""
    result = compute_dynamic_stroke_volume(150.0)
    assert result.edv_from_placeholder is True
    manual_edv = estimate_edv_venous_return_placeholder_pending_module_4b(150.0)
    assert result.edv_ml == pytest.approx(manual_edv)
