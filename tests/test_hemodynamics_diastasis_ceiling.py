"""
"La película" — Módulo 4B-i (2026-07-27): techo diastólico (diástasis)
sobre el placeholder de retorno venoso del eslabón 1.

Cubre: mecanismo de diástasis citado vs. techo anatómico marcado
pendiente, salvaguarda anti-circularidad (el techo no se deriva de
ninguna PA de referencia), identidad del techo por debajo del ancla
(el ancla de reposo 72bpm->120mL->70mL NO se rompe), corrección del
artefacto de bradicardia (40bpm ya no se dispara a 216 mL), monotonía y
saturación del techo sin excederlo, y que `frank_starling.py` no fue
modificado (sus funciones originales, sin techo, siguen intactas y
disponibles).
"""

import pytest

from domain.physiology.hemodynamics.diastasis_ceiling import (
    DIASTASIS_CEILING_PENDING_VALIDATION,
    DIASTASIS_MECHANISM_CITATION,
    DIASTASIS_TRANSITION_BUDGET_ML,
    EDV_ANATOMICAL_CEILING_ML,
    apply_diastasis_ceiling,
    compute_dynamic_stroke_volume_with_diastasis_ceiling,
    estimate_edv_with_diastasis_ceiling,
    stroke_volume_table_with_diastasis_ceiling,
)
from domain.physiology.hemodynamics.frank_starling import (
    EDV_FLOOR_ML,
    EDV_HEALTHY_ML,
    HEART_RATE_ANCHOR_BPM,
    STROKE_VOLUME_REFERENCE_ML,
    VENOUS_RETURN_PLACEHOLDER_PENDING_MODULE_4B,
    compute_dynamic_stroke_volume,
    estimate_edv_venous_return_placeholder_pending_module_4b,
)


# --- Mecanismo citado vs. techo marcado pendiente -------------------------------


def test_mechanism_citation_is_non_empty_and_cites_guyton():
    assert "Guyton" in DIASTASIS_MECHANISM_CITATION
    assert len(DIASTASIS_MECHANISM_CITATION) > 20


def test_diastasis_ceiling_fully_validated_as_of_round_2():
    """Los dos parámetros de este módulo (EDV_ANATOMICAL_CEILING_ML --
    Ronda 1; DIASTASIS_TRANSITION_BUDGET_ML -- Ronda 2, 2026-07-31)
    quedaron confirmados -- la bandera bajó a False, y el guard que antes
    vivía en `apply_diastasis_ceiling()` se retiró conscientemente: la
    función sigue operando con normalidad."""
    assert DIASTASIS_CEILING_PENDING_VALIDATION is False
    assert apply_diastasis_ceiling(200.0) > 0.0


def test_venous_return_placeholder_flag_still_true_not_replaced():
    """Este submódulo NO reemplaza el placeholder de retorno venoso --
    su bandera sigue en pendiente (bandera de andamiaje, retirada del
    flujo de validación activo en Ronda 1, pero técnicamente sin tocar)."""
    assert VENOUS_RETURN_PLACEHOLDER_PENDING_MODULE_4B is True


# --- Salvaguarda anti-circularidad ----------------------------------------------


def test_ceiling_is_a_round_multiple_of_the_already_used_anchor():
    """Criterio explícito y verificable: techo = 1.5x EDV_HEALTHY_ML, no
    una cifra derivada de ninguna PA de referencia."""
    assert EDV_ANATOMICAL_CEILING_ML == pytest.approx(EDV_HEALTHY_ML * 1.5)
    assert DIASTASIS_TRANSITION_BUDGET_ML == pytest.approx(EDV_ANATOMICAL_CEILING_ML - EDV_HEALTHY_ML)


def test_ceiling_constants_do_not_coincide_with_any_blood_pressure_reference_value():
    bp_reference_values_mmhg = {65.0, 85.0, 93.3, 96.7, 130.0, 55.0, 80.0}
    for value in (EDV_ANATOMICAL_CEILING_ML, DIASTASIS_TRANSITION_BUDGET_ML):
        assert round(value, 1) not in bp_reference_values_mmhg


# --- Identidad por debajo del ancla -- el ancla de reposo no se rompe ----------


def test_ceiling_is_identity_at_and_below_the_healthy_anchor():
    assert apply_diastasis_ceiling(EDV_HEALTHY_ML) == pytest.approx(EDV_HEALTHY_ML)
    assert apply_diastasis_ceiling(100.0) == pytest.approx(100.0)
    assert apply_diastasis_ceiling(0.0) == pytest.approx(0.0)


def test_resting_anchor_survives_diastasis_ceiling_unchanged():
    """72 bpm -> EDV=120 mL -> SV=70 mL, ya validado en el eslabón 1, debe
    quedar EXACTAMENTE igual al pasar por el techo de diástasis (el techo
    es identidad ahí, porque el placeholder crudo ya da 120 exacto)."""
    result = compute_dynamic_stroke_volume_with_diastasis_ceiling(HEART_RATE_ANCHOR_BPM)
    assert result.raw_edv_ml == pytest.approx(EDV_HEALTHY_ML)
    assert result.corrected_edv_ml == pytest.approx(EDV_HEALTHY_ML)
    assert result.stroke_volume_ml == pytest.approx(STROKE_VOLUME_REFERENCE_ML, abs=0.01)
    assert result.diastasis_ceiling_active is False

    # Coincide exactamente con el resultado sin techo del eslabón 1 -- no se rompió nada.
    baseline = compute_dynamic_stroke_volume(HEART_RATE_ANCHOR_BPM)
    assert result.corrected_edv_ml == pytest.approx(baseline.edv_ml)
    assert result.stroke_volume_ml == pytest.approx(baseline.stroke_volume_ml)


def test_non_bradycardic_heart_rates_are_unaffected_by_the_ceiling():
    """A HR>=72 (donde el placeholder crudo ya es <=120), el techo no
    debe cambiar nada -- ni siquiera sepsis (150 bpm), ya validado
    independientemente en el eslabón 1."""
    for heart_rate in (72.0, 85.0, 150.0, 220.0):
        with_ceiling = compute_dynamic_stroke_volume_with_diastasis_ceiling(heart_rate)
        without_ceiling = compute_dynamic_stroke_volume(heart_rate)
        assert with_ceiling.corrected_edv_ml == pytest.approx(without_ceiling.edv_ml)
        assert with_ceiling.stroke_volume_ml == pytest.approx(without_ceiling.stroke_volume_ml)
        assert with_ceiling.diastasis_ceiling_active is False


# --- Corrección del artefacto de bradicardia ------------------------------------


def test_bradycardia_edv_no_longer_blows_up_to_the_old_artifact_value():
    """El hallazgo que motivó este submódulo: a 40 bpm el EDV crudo del
    placeholder (artefacto) es 216 mL -- corregido, debe quedar muy por
    debajo, y por debajo del techo anatómico."""
    result = compute_dynamic_stroke_volume_with_diastasis_ceiling(40.0)
    assert result.raw_edv_ml == pytest.approx(216.0, abs=0.5)  # el artefacto original, sin corregir, para contraste
    assert result.corrected_edv_ml < result.raw_edv_ml
    assert result.corrected_edv_ml < EDV_ANATOMICAL_CEILING_ML
    assert result.diastasis_ceiling_active is True
    assert result.corrected_edv_ml == pytest.approx(167.9, abs=0.1)
    assert result.stroke_volume_ml == pytest.approx(89.8, abs=0.1)


def test_extreme_bradycardia_saturates_toward_ceiling_without_exceeding_it():
    raw_edv, corrected_edv = estimate_edv_with_diastasis_ceiling(10.0)
    assert raw_edv > EDV_ANATOMICAL_CEILING_ML  # el crudo sigue disparado (artefacto sin corregir)
    assert corrected_edv < EDV_ANATOMICAL_CEILING_ML
    assert corrected_edv == pytest.approx(EDV_ANATOMICAL_CEILING_ML, rel=0.05)  # cerca del techo, sin tocarlo


def test_ceiling_curve_is_monotonically_increasing_and_never_exceeds_ceiling():
    raw_samples = [120.0, 140.0, 160.0, 200.0, 300.0, 1000.0]
    corrected_samples = [apply_diastasis_ceiling(raw) for raw in raw_samples]
    assert corrected_samples == sorted(corrected_samples)
    for corrected in corrected_samples:
        assert corrected <= EDV_ANATOMICAL_CEILING_ML


# --- Tabla completa, comparación cruda vs. corregida ----------------------------


def test_full_range_table_matches_raw_placeholder_for_non_bradycardic_rates():
    results = stroke_volume_table_with_diastasis_ceiling()
    heart_rates = [r.heart_rate_bpm for r in results]
    assert heart_rates == [40.0, 72.0, 85.0, 150.0, 220.0]

    for result in results:
        raw = estimate_edv_venous_return_placeholder_pending_module_4b(result.heart_rate_bpm)
        assert result.raw_edv_ml == pytest.approx(raw)
        if result.heart_rate_bpm >= HEART_RATE_ANCHOR_BPM:
            assert result.corrected_edv_ml == pytest.approx(raw)
        else:
            assert result.corrected_edv_ml <= raw


def test_stroke_volume_still_falls_monotonically_as_heart_rate_rises_after_correction():
    """El efecto del eslabón 1 (SV cae con HR alta) sigue intacto tras la
    corrección -- el techo solo actúa en el extremo bradicárdico."""
    results = stroke_volume_table_with_diastasis_ceiling()
    stroke_volumes = [r.stroke_volume_ml for r in results]
    assert stroke_volumes == sorted(stroke_volumes, reverse=True)


# --- frank_starling.py no fue modificado -----------------------------------------


def test_frank_starling_module_functions_remain_unmodified_and_unbounded():
    """Las funciones originales del eslabón 1 siguen dando el EDV crudo
    SIN techo -- confirma que este submódulo envuelve, no reemplaza."""
    raw = estimate_edv_venous_return_placeholder_pending_module_4b(40.0)
    assert raw == pytest.approx(216.0, abs=0.5)  # sigue "roto" ahí -- el techo vive solo en este submódulo

    baseline = compute_dynamic_stroke_volume(40.0)
    assert baseline.edv_ml == pytest.approx(216.0, abs=0.5)
    assert baseline.stroke_volume_ml == pytest.approx(104.0, abs=0.5)  # el artefacto del eslabón 1, sin corregir


def test_floor_clamping_from_link_1_still_reachable_through_the_ceiling_wrapper():
    """El piso de taquicardia extrema (EDV_FLOOR_ML, colapso de SV) sigue
    funcionando igual a través de este envoltorio -- el techo de
    diástasis no interfiere con el extremo taquicárdico."""
    result = compute_dynamic_stroke_volume_with_diastasis_ceiling(1000.0)
    assert result.clamped_at_edv_floor is True
    assert result.corrected_edv_ml == pytest.approx(EDV_FLOOR_ML)
    assert result.stroke_volume_ml == pytest.approx(0.0, abs=1e-6)
