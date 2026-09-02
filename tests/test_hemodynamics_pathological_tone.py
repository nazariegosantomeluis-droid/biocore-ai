"""
"La película" — Módulo 3 (2026-07-23): tono vascular alterable por
patología.

Cubre: dos mecanismos citados y distintos (reseteo del barostato en
hipertensión vs. vasoplejía/fallo del efector en sepsis), magnitudes
marcadas pendientes, salvaguarda anti-circularidad reforzada (los
parámetros del override NO se derivan de la referencia clínica del
escenario; `target_map` no varía por escenario salvo en hipertensión, y
ahí varía por el mecanismo citado, no por conveniencia), pass-through
exacto para escenarios sin mecanismo definido, y verificación en contexto
contra `ClinicalReferenceValue` como control de calidad independiente.
"""

import pytest

from app.engines.simulation_engine import SimulationScenario
from domain.physiology.hemodynamics.baroreflex import (
    BAROREFLEX_GAIN_K,
    BAROREFLEX_MAX_RD,
    BAROREFLEX_MIN_RD,
    BAROREFLEX_TARGET_MAP_MMHG,
    run_baroreflex,
)
from domain.physiology.hemodynamics.pathological_tone import (
    HYPERTENSION_RESET_CITATION,
    HYPERTENSION_RESET_TARGET_MAP_MMHG,
    PATHOLOGICAL_TONE_OVERRIDES,
    PATHOLOGICAL_TONE_PENDING_VALIDATION,
    SEPSIS_GAIN_K,
    SEPSIS_MAX_RD_MMHG_S_ML,
    SEPSIS_VASOPLEGIA_CITATION,
    run_pathological_baroreflex,
)
from domain.physiology.hemodynamics.pathological_tone_comparison import run_scenario_pathological_tone_comparison
from domain.physiology.state.clinical_reference import estimate_map


# --- Mecanismos citados vs. magnitudes pendientes ------------------------------


def test_hypertension_citation_is_non_empty_and_cites_guyton():
    assert "Guyton" in HYPERTENSION_RESET_CITATION
    assert len(HYPERTENSION_RESET_CITATION) > 20


def test_sepsis_citation_is_non_empty_and_cites_marino():
    assert "Marino" in SEPSIS_VASOPLEGIA_CITATION
    assert len(SEPSIS_VASOPLEGIA_CITATION) > 20


def test_the_two_mechanisms_are_genuinely_different_citations():
    """Hipertensión (reseteo del punto de ajuste) y sepsis (fallo del
    efector) son mecanismos DISTINTOS -- no la misma cita reutilizada."""
    assert HYPERTENSION_RESET_CITATION != SEPSIS_VASOPLEGIA_CITATION


def test_pathological_tone_parameters_fully_validated_as_of_round_2():
    """Los tres parámetros de este módulo (target_map hipertensión,
    max_rd/k sepsis) quedaron confirmados por el validador experto en
    Ronda 2 (2026-07-31) -- la bandera bajó a False."""
    assert PATHOLOGICAL_TONE_PENDING_VALIDATION is False


# --- Salvaguarda anti-circularidad reforzada -----------------------------------


def test_hypertension_reset_target_map_is_not_derived_from_clinical_reference():
    """El nuevo punto de ajuste (102.67 mmHg, +10% redondo sobre el ancla
    fija) NO es la PAM de referencia clínica de hipertensión (96.67 mmHg,
    ACC/AHA 2017) -- si coincidieran, sería la señal de que se ajustó el
    número para que "diera bien", justo lo prohibido."""
    hypertension_reference_map = estimate_map(130.0, 80.0)  # 96.67 -- ver blood_pressure_references.py
    assert HYPERTENSION_RESET_TARGET_MAP_MMHG != pytest.approx(hypertension_reference_map, abs=0.5)
    # Criterio explícito y verificable: +10% redondo sobre el ancla fija del Módulo 2.
    assert HYPERTENSION_RESET_TARGET_MAP_MMHG == pytest.approx(BAROREFLEX_TARGET_MAP_MMHG * 1.10)


def test_sepsis_max_rd_and_gain_are_not_derived_from_clinical_reference():
    """Los parámetros de vasoplejía (max_rd=0.5x, k=0.3x) son múltiplos
    redondos del Módulo 2 -- no fueron elegidos resolviendo la ecuación
    para que la PAM final diera 65 mmHg (la referencia de shock séptico)."""
    assert SEPSIS_MAX_RD_MMHG_S_ML == pytest.approx(BAROREFLEX_MAX_RD * 0.5)
    assert SEPSIS_GAIN_K == pytest.approx(BAROREFLEX_GAIN_K * 0.3)
    # Verificación directa de no-circularidad: correr sepsis con estos parámetros
    # NO converge a la referencia de shock (65 mmHg) -- ver test de abajo.


def test_sepsis_target_map_stays_fixed_body_still_wants_to_normalize():
    """A diferencia de hipertensión, sepsis NO reajusta target_map -- el
    mecanismo es fallo del efector, no del punto de ajuste; el cuerpo
    sigue queriendo normalizar 93.33 mmHg."""
    result = run_pathological_baroreflex("sepsis", 150.0)
    assert result.target_map == pytest.approx(BAROREFLEX_TARGET_MAP_MMHG)


def test_hypertension_target_map_is_reset_by_cited_mechanism_not_convenience():
    """Único escenario donde target_map varía -- y varía exactamente al
    valor documentado con criterio explícito, no a un valor "que ajuste"."""
    result = run_pathological_baroreflex("hypertension", 85.0)
    assert result.target_map == pytest.approx(HYPERTENSION_RESET_TARGET_MAP_MMHG)
    assert result.target_map != pytest.approx(BAROREFLEX_TARGET_MAP_MMHG)


def test_target_map_does_not_vary_by_scenario_except_hypertension():
    """Salvaguarda reforzada del Módulo 2: recorre TODOS los escenarios --
    target_map debe quedar en el ancla fija (93.33) para todos salvo
    'hypertension', donde debe ser el valor reseteado citado."""
    for scenario in SimulationScenario:
        result = run_pathological_baroreflex(scenario.value, 90.0)
        if scenario.value == "hypertension":
            assert result.target_map == pytest.approx(HYPERTENSION_RESET_TARGET_MAP_MMHG)
        else:
            assert result.target_map == pytest.approx(BAROREFLEX_TARGET_MAP_MMHG), (
                f"target_map cambió sin mecanismo citado para el escenario {scenario.value!r}"
            )


def test_sepsis_dynamic_still_does_not_match_clinical_reference_by_construction():
    """Hallazgo esperado, NO oculto: incluso con vasoplejía modelada
    (max_rd/k reducidos), la PAM de sepsis en este modelo (HR=150) sigue
    convergiendo cerca de 93.3 mmHg, no de la referencia de shock (65
    mmHg). Causa mecanicista documentada en pathological_tone_comparison.py
    y CHANGELOG.md: a HR=150 el barórreflejo necesita VASODILATAR (bajar
    Rd) para defender target_map, no vasoconstreñir -- por lo que el techo
    de vasoconstricción reducido (max_rd) no es la restricción activa. Si
    este test empezara a fallar porque alguien ajustó max_rd/k/target_map
    para acercarse a 65, eso sería la circularidad prohibida."""
    result = run_pathological_baroreflex("sepsis", 150.0)
    assert result.converged is True
    assert result.final_map == pytest.approx(BAROREFLEX_TARGET_MAP_MMHG, abs=1.0)
    assert result.final_map > 80.0  # lejos de la referencia de shock (PAM<65)
    assert result.clamped_at_max is False  # confirma que max_rd reducido no es la restricción activa aquí


# --- Estructura del override ----------------------------------------------------


def test_overrides_only_defined_for_hypertension_and_sepsis():
    assert set(PATHOLOGICAL_TONE_OVERRIDES.keys()) == {"hypertension", "sepsis"}


def test_hypertension_override_only_touches_target_map():
    override = PATHOLOGICAL_TONE_OVERRIDES["hypertension"]
    assert override.target_map_mmhg is not None
    assert override.max_rd is None
    assert override.k is None


def test_sepsis_override_only_touches_max_rd_and_gain_not_target_map():
    override = PATHOLOGICAL_TONE_OVERRIDES["sepsis"]
    assert override.target_map_mmhg is None
    assert override.max_rd is not None
    assert override.k is not None


def test_sepsis_min_rd_untouched_vasoplegia_is_not_excess_dilation():
    """Vasoplejía es incapacidad de constreñir, no una tendencia a dilatar
    más -- min_rd (techo de vasodilatación) no tiene mecanismo citado para
    cambiar, así que el override no lo toca: reproduce exactamente
    run_baroreflex() con max_rd/k sobrescritos y min_rd por defecto."""
    heart_rate = 150.0
    pathological = run_pathological_baroreflex("sepsis", heart_rate)
    manual = run_baroreflex(heart_rate, max_rd=SEPSIS_MAX_RD_MMHG_S_ML, k=SEPSIS_GAIN_K)
    assert pathological.final_rd == pytest.approx(manual.final_rd, rel=1e-9)
    assert manual.final_rd >= BAROREFLEX_MIN_RD  # min_rd por defecto, no tocado por el override


# --- Pass-through exacto para escenarios sin mecanismo --------------------------


def test_scenarios_without_override_are_exact_pass_through_to_run_baroreflex():
    for scenario_value in ("healthy", "exercise", "stress", "anxiety", "arrhythmia", "hypoxia", "apnea", "fatigue", "seizure", "copd"):
        heart_rate = 90.0
        pathological = run_pathological_baroreflex(scenario_value, heart_rate)
        baseline = run_baroreflex(heart_rate)
        assert pathological.final_rd == pytest.approx(baseline.final_rd, rel=1e-9)
        assert pathological.final_map == pytest.approx(baseline.final_map, rel=1e-9)
        assert pathological.target_map == baseline.target_map


def test_explicit_kwargs_take_priority_over_scenario_override():
    """Un llamador que pasa target_map explícito para hipertensión gana
    sobre el override del escenario -- mismo criterio que cualquier
    default de Python (setdefault, no overwrite)."""
    forced_target = 111.0
    result = run_pathological_baroreflex("hypertension", 85.0, target_map=forced_target)
    assert result.target_map == pytest.approx(forced_target)
    assert result.target_map != pytest.approx(HYPERTENSION_RESET_TARGET_MAP_MMHG)


# --- Verificación en contexto -- comparación contra ClinicalReferenceValue -----


def test_hypertension_pathological_comparison_end_to_end(tmp_path):
    comparison = run_scenario_pathological_tone_comparison(
        SimulationScenario.HYPERTENSION, db_path=tmp_path / "pathological_hypertension.db"
    )

    assert comparison.scenario == "hypertension"
    assert comparison.pending_validation is False  # PATHOLOGICAL_TONE_PENDING_VALIDATION, validado Ronda 2
    assert comparison.has_pathological_override is True
    assert comparison.pathological_dynamic.converged is True
    assert len(comparison.reference) == 3

    # target_map con patología > target_map sin patología (reseteo hacia arriba, no hacia abajo)
    assert comparison.pathological_dynamic.target_map > comparison.baseline_dynamic.target_map

    rows = comparison.as_table_rows()
    assert len(rows) == 3
    for _descriptor, baseline_val, pathological_val, ref_val, _citation in rows:
        assert baseline_val is not None
        assert pathological_val is not None
        assert ref_val is not None


def test_sepsis_pathological_comparison_end_to_end(tmp_path):
    comparison = run_scenario_pathological_tone_comparison(
        SimulationScenario.SEPSIS, db_path=tmp_path / "pathological_sepsis.db"
    )

    assert comparison.scenario == "sepsis"
    assert comparison.pending_validation is False  # PATHOLOGICAL_TONE_PENDING_VALIDATION, validado Ronda 2
    assert comparison.has_pathological_override is True
    assert comparison.pathological_dynamic.converged is True
    assert len(comparison.reference) == 3

    # target_map NO cambia en sepsis (mecanismo de efector, no de punto de ajuste)
    assert comparison.pathological_dynamic.target_map == pytest.approx(comparison.baseline_dynamic.target_map)


def test_pathological_comparison_handles_scenario_without_override(tmp_path):
    """'healthy' no tiene entrada en PATHOLOGICAL_TONE_OVERRIDES -- debe
    comportarse como pass-through exacto también en la comparación end-to-end."""
    comparison = run_scenario_pathological_tone_comparison(
        SimulationScenario.HEALTHY, db_path=tmp_path / "pathological_healthy.db"
    )
    assert comparison.has_pathological_override is False
    assert comparison.pathological_dynamic.final_rd == pytest.approx(comparison.baseline_dynamic.final_rd, rel=1e-9)


def test_pathological_comparison_does_not_write_new_ups_descriptors(tmp_path):
    """Aislado -- mismo criterio que baroreflex_comparison.py: correr la
    comparación del Módulo 3 no debe dejar descriptores nuevos en el UPS."""
    from domain.physiology.state import get_latest_state, init_db, make_engine, make_session_factory

    db_path = tmp_path / "pathological_isolation.db"
    run_scenario_pathological_tone_comparison(SimulationScenario.SEPSIS, db_path=db_path)

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
