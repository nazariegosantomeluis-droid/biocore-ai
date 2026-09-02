"""
"La película" — Módulo 4, eslabón 1 (2026-07-24): volumen sistólico
dinámico vía Frank-Starling, retorno venoso simplificado (andamiaje
temporal, Paso 2).

Cubre: mecanismo citado (Guyton) vs. constantes de la curva marcadas
pendientes, salvaguarda anti-circularidad (constantes resueltas contra el
ancla ya citada SV_ref/EDV_healthy, nunca contra una PA de referencia),
el andamiaje de retorno venoso declarado e inequívoco (imposible de
confundir con fisiología final), monotonía y techo de la curva, el efecto
verificable (SV cae a HR alta, sube a HR baja), y aislamiento total
(función pura, sin UPS, sin sesión de base de datos).
"""

import pytest

from domain.physiology.hemodynamics.frank_starling import (
    EDV_FLOOR_ML,
    EDV_HEALTHY_ML,
    FRANK_STARLING_MECHANISM_CITATION,
    FRANK_STARLING_PARAMETERS_PENDING_VALIDATION,
    FRANK_STARLING_STEEPNESS_ML,
    HEART_RATE_ANCHOR_BPM,
    SV_MAX_ML,
    VALIDATOR_SEPSIS_SV_ESTIMATE_RANGE_ML,
    VENOUS_RETURN_PLACEHOLDER_PENDING_MODULE_4B,
    compute_dynamic_stroke_volume,
    estimate_edv_venous_return_placeholder_pending_module_4b,
    stroke_volume_frank_starling,
    stroke_volume_table,
)
from domain.physiology.hemodynamics.physiological_flow import STROKE_VOLUME_REFERENCE_ML


# --- Mecanismo citado vs. constantes pendientes --------------------------------


def test_mechanism_citation_is_non_empty_and_cites_guyton():
    assert "Guyton" in FRANK_STARLING_MECHANISM_CITATION
    assert len(FRANK_STARLING_MECHANISM_CITATION) > 20


def test_frank_starling_parameters_fully_validated_as_of_round_2():
    """Los cuatro parámetros de este módulo (EDV_HEALTHY_ML/SV_MAX_ML --
    Ronda 1; EDV_FLOOR_ML/FRANK_STARLING_STEEPNESS_ML -- Ronda 2,
    2026-07-31) quedaron confirmados -- la bandera bajó a False, y el
    guard que antes vivía en `stroke_volume_frank_starling()` (bloqueaba
    un flip a False sin revisión) se retiró conscientemente: la función
    sigue operando con normalidad."""
    assert FRANK_STARLING_PARAMETERS_PENDING_VALIDATION is False
    assert stroke_volume_frank_starling(EDV_HEALTHY_ML) == pytest.approx(STROKE_VOLUME_REFERENCE_ML, abs=0.01)


def test_sv_max_is_a_round_multiple_of_the_already_cited_sv_reference():
    """Criterio explícito y verificable: SV_MAX = 2.0x SV_ref (ya citado),
    no una cifra derivada de ninguna PA de referencia."""
    assert SV_MAX_ML == pytest.approx(STROKE_VOLUME_REFERENCE_ML * 2.0)


# --- Salvaguarda anti-circularidad ----------------------------------------------


def test_steepness_constant_is_solved_from_the_cited_anchor_not_from_any_bp_reference():
    """FRANK_STARLING_STEEPNESS_ML se resuelve algebraicamente para que la
    curva pase EXACTO por (EDV_HEALTHY_ML, SV_REFERENCE_ML) -- el mismo
    ancla ya citado en physiological_flow.py, no una cifra de PA."""
    reproduced = stroke_volume_frank_starling(EDV_HEALTHY_ML)
    assert reproduced == pytest.approx(STROKE_VOLUME_REFERENCE_ML, abs=0.01)
    # El valor numérico resuelto -- documentado, no mágico.
    assert FRANK_STARLING_STEEPNESS_ML == pytest.approx(144.27, abs=0.05)


def test_curve_constants_do_not_coincide_with_any_blood_pressure_reference_value():
    """Sanity check de no-circularidad: ninguna constante de la curva
    (EDV_HEALTHY_ML, EDV_FLOOR_ML, SV_MAX_ML) es una cifra de PA
    (mmHg) -- son volúmenes (mL), de una escala y unidad completamente
    distinta a 65/85/93.3/96.7/130 mmHg de las referencias clínicas."""
    bp_reference_values_mmhg = {65.0, 85.0, 93.3, 96.7, 130.0, 55.0, 80.0}
    for value in (EDV_HEALTHY_ML, EDV_FLOOR_ML, SV_MAX_ML, FRANK_STARLING_STEEPNESS_ML):
        assert round(value, 1) not in bp_reference_values_mmhg


def test_sepsis_sv_estimate_range_is_informational_not_a_formal_reference():
    """VALIDATOR_SEPSIS_SV_ESTIMATE_RANGE_ML es contexto cualitativo, no
    una ClinicalReferenceValue -- verificamos que sigue siendo un simple
    tuple informativo, no un tipo con obligación de cita estructural."""
    assert isinstance(VALIDATOR_SEPSIS_SV_ESTIMATE_RANGE_ML, tuple)
    assert VALIDATOR_SEPSIS_SV_ESTIMATE_RANGE_ML == (30.0, 40.0)


# --- Paso 2: retorno venoso -- andamiaje temporal, declarado e inequívoco -----


def test_venous_return_placeholder_flag_exists_and_is_true():
    assert VENOUS_RETURN_PLACEHOLDER_PENDING_MODULE_4B is True


def test_venous_return_placeholder_function_name_is_unambiguous():
    """El nombre de la función en sí mismo declara que es un placeholder
    pendiente del Módulo 4B -- no un comentario que se pueda perder."""
    assert "placeholder" in estimate_edv_venous_return_placeholder_pending_module_4b.__name__
    assert "pending_module_4b" in estimate_edv_venous_return_placeholder_pending_module_4b.__name__


def test_venous_return_placeholder_docstring_declares_it_is_not_final_physiology():
    doc = estimate_edv_venous_return_placeholder_pending_module_4b.__doc__ or ""
    assert "ANDAMIAJE TEMPORAL" in doc
    assert "NO es fisiología final" in doc


def test_venous_return_placeholder_reproduces_the_anchor_exactly_at_anchor_heart_rate():
    edv = estimate_edv_venous_return_placeholder_pending_module_4b(HEART_RATE_ANCHOR_BPM)
    assert edv == pytest.approx(EDV_HEALTHY_ML)


def test_venous_return_placeholder_decreases_with_heart_rate_above_anchor():
    edv_72 = estimate_edv_venous_return_placeholder_pending_module_4b(72.0)
    edv_85 = estimate_edv_venous_return_placeholder_pending_module_4b(85.0)
    edv_150 = estimate_edv_venous_return_placeholder_pending_module_4b(150.0)
    edv_220 = estimate_edv_venous_return_placeholder_pending_module_4b(220.0)
    assert edv_72 > edv_85 > edv_150 > edv_220


def test_venous_return_placeholder_increases_with_bradycardia_below_anchor():
    """Más tiempo de llenado diastólico a HR baja -> más EDV (por encima
    del ancla) -- dirección esperada del mecanismo de llenado, aunque la
    magnitud exacta sea andamiaje."""
    edv_40 = estimate_edv_venous_return_placeholder_pending_module_4b(40.0)
    assert edv_40 > EDV_HEALTHY_ML


def test_venous_return_placeholder_floors_at_extreme_tachycardia():
    for extreme_hr in (500.0, 1000.0, 10000.0):
        edv = estimate_edv_venous_return_placeholder_pending_module_4b(extreme_hr)
        assert edv == pytest.approx(EDV_FLOOR_ML)


def test_venous_return_placeholder_rejects_non_positive_heart_rate():
    with pytest.raises(ValueError):
        estimate_edv_venous_return_placeholder_pending_module_4b(0.0)
    with pytest.raises(ValueError):
        estimate_edv_venous_return_placeholder_pending_module_4b(-10.0)


# --- Paso 1: forma de la curva (monotonía, techo, piso) ------------------------


def test_curve_is_zero_at_and_below_floor():
    assert stroke_volume_frank_starling(EDV_FLOOR_ML) == 0.0
    assert stroke_volume_frank_starling(EDV_FLOOR_ML - 5.0) == 0.0
    assert stroke_volume_frank_starling(0.0) == 0.0


def test_curve_is_monotonically_increasing_above_floor():
    edv_samples = [21.0, 40.0, 70.0, 100.0, 120.0, 160.0, 250.0, 500.0]
    sv_samples = [stroke_volume_frank_starling(edv) for edv in edv_samples]
    assert sv_samples == sorted(sv_samples)
    assert len(set(sv_samples)) == len(sv_samples)  # estrictamente creciente, sin empates


def test_curve_saturates_toward_ceiling_without_exceeding_it():
    # (EDV-piso)/k ~ 10 -- exp(-10)~4.5e-5, todavía distinguible de 1.0 en
    # punto flotante. Un EDV mucho mayor haría que 1-exp(-x) redondee a
    # exactamente 1.0 (la resta se pierde frente al épsilon de float64),
    # dando SV == SV_MAX_ML por precisión numérica, no por el modelo.
    sv_near_ceiling = stroke_volume_frank_starling(1500.0)
    assert sv_near_ceiling < SV_MAX_ML
    assert sv_near_ceiling == pytest.approx(SV_MAX_ML, rel=1e-3)
    for edv in (50.0, 120.0, 300.0, 1500.0):
        assert stroke_volume_frank_starling(edv) < SV_MAX_ML


def test_curve_reproduces_cited_anchor_exactly():
    assert stroke_volume_frank_starling(EDV_HEALTHY_ML) == pytest.approx(STROKE_VOLUME_REFERENCE_ML, abs=0.01)


def test_curve_is_pure_function_two_calls_do_not_interfere():
    a1 = stroke_volume_frank_starling(90.0)
    b = stroke_volume_frank_starling(200.0)
    a2 = stroke_volume_frank_starling(90.0)
    assert a1 == pytest.approx(a2, rel=1e-12)
    assert a1 != pytest.approx(b)


# --- Paso 3: efecto verificable (SV cae a HR alta, sube a HR baja) -------------


def test_stroke_volume_falls_at_high_heart_rate_with_reduced_filling():
    """El efecto que el validador predijo: a HR=150 (llenado reducido vía
    el andamiaje del Paso 2), SV cae respecto al reposo (HR=72)."""
    resting = compute_dynamic_stroke_volume(72.0)
    tachycardic = compute_dynamic_stroke_volume(150.0)
    assert tachycardic.stroke_volume_ml < resting.stroke_volume_ml
    assert resting.stroke_volume_ml == pytest.approx(STROKE_VOLUME_REFERENCE_ML, abs=0.01)


def test_stroke_volume_rises_at_low_heart_rate_with_increased_filling():
    resting = compute_dynamic_stroke_volume(72.0)
    bradycardic = compute_dynamic_stroke_volume(40.0)
    assert bradycardic.stroke_volume_ml > resting.stroke_volume_ml


def test_sepsis_heart_rate_stroke_volume_falls_within_validators_qualitative_estimate():
    """Observado DESPUÉS de fijar las constantes con criterio independiente
    -- no el objetivo de su ajuste (ver docstring de
    VALIDATOR_SEPSIS_SV_ESTIMATE_RANGE_ML). Si este test empezara a fallar
    porque alguien retocó EDV_HEALTHY_ML/EDV_FLOOR_ML/SV_MAX_ML para que
    "diera bien", eso sería la circularidad prohibida."""
    result = compute_dynamic_stroke_volume(150.0)
    low, high = VALIDATOR_SEPSIS_SV_ESTIMATE_RANGE_ML
    assert low <= result.stroke_volume_ml <= high
    assert result.stroke_volume_ml == pytest.approx(32.1, abs=0.1)


def test_extreme_tachycardia_clamps_at_edv_floor_stroke_volume_collapses():
    result = compute_dynamic_stroke_volume(1000.0)
    assert result.clamped_at_edv_floor is True
    assert result.stroke_volume_ml == pytest.approx(0.0, abs=1e-6)


def test_compute_dynamic_stroke_volume_flags_placeholder_origin_of_edv():
    from_placeholder = compute_dynamic_stroke_volume(150.0)
    assert from_placeholder.edv_from_placeholder is True

    explicit_edv = compute_dynamic_stroke_volume(150.0, edv_ml=90.0)
    assert explicit_edv.edv_from_placeholder is False
    assert explicit_edv.edv_ml == pytest.approx(90.0)
    assert explicit_edv.stroke_volume_ml == pytest.approx(stroke_volume_frank_starling(90.0))


def test_stroke_volume_table_covers_module_2_reference_heart_rates_ordered_by_falling_sv():
    results = stroke_volume_table()
    heart_rates = [r.heart_rate_bpm for r in results]
    assert heart_rates == [40.0, 72.0, 85.0, 150.0, 220.0]
    stroke_volumes = [r.stroke_volume_ml for r in results]
    assert stroke_volumes == sorted(stroke_volumes, reverse=True)  # SV cae monótonamente al subir HR en esta tabla


# --- Aislamiento -----------------------------------------------------------------


def test_module_has_no_ups_or_session_dependency():
    """Aislado por construcción -- no importa sqlalchemy.orm.Session ni
    nada de domain.physiology.state. Verificación directa del módulo,
    complementaria al grep de aislamiento reportado en CHANGELOG.md."""
    import domain.physiology.hemodynamics.frank_starling as fs_module

    assert not hasattr(fs_module, "Session")
    source_imports = [name for name in dir(fs_module) if name.startswith("_") is False]
    assert "get_latest_state" not in source_imports
    assert "make_session_factory" not in source_imports
