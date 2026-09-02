"""
Learning Hub — Conexión de la PA calculada del motor hemodinámico al modo
caso clínico de Academia (2026-08-06).

Cubre la lógica exacta que vive en
`app/supermodules/academia/pages.py::render_synthetic_case_section()` (el
manejador de "🆕 Nuevo caso sintético"), replicada aquí sin Streamlit:
para los 3 escenarios de `HEMODYNAMIC_MODEL_ENABLED_SCENARIOS` (healthy,
hypertension, sepsis), el caso generado por `case_bank.generate_case()`
recibe la PA calculada del lazo cerrado, adjuntada al snapshot EXACTO del
horizonte elegido (no necesariamente el último) -- para los otros 9,
el caso queda exactamente igual que antes de esta tanda.

2026-08-06 (réplica a Twin OS): `_attach_calculated_pa_to_case()` y
`_build_pa_findings()` ya NO se replican a mano en este archivo -- se
importan directo de `app.supermodules.twin_shell.pages`, donde se
extrajeron para que Academia y Twin OS (`tests/test_twin_shell_case_hemodynamics.py`)
compartan exactamente la misma función, no una copia que pueda divergir."""

import pytest

from app.engines.simulation_engine import SimulationScenario
from app.supermodules.twin_shell.pages import (
    _attach_calculated_pa_to_case,
    _build_pa_findings,
)
from domain.physiology.hemodynamics import (
    HEMODYNAMIC_MODEL_ENABLED_SCENARIOS,
    HEMODYNAMIC_MODEL_VALIDATED_CONFIDENCE,
    compute_and_attach_closed_loop_pressure,
)
from domain.physiology.scenarios.case_bank import generate_case
from domain.physiology.state import (
    Provenance,
    get_snapshot_id_at,
    get_state_by_snapshot_id,
    init_db,
    make_engine,
    make_session_factory,
)


def _session_factory(path):
    engine = make_engine(path)
    init_db(engine)
    return make_session_factory(engine)


def _generate_case_with_calculated_pa(session, scenario, rng):
    """Réplica exacta de la lógica del manejador "Nuevo caso sintético" en
    `academia/pages.py` -- llama a la MISMA función compartida que usa el
    código real, no una copia."""
    case = generate_case(session, scenario=scenario, rng=rng)
    case_state, case_references = _attach_calculated_pa_to_case(
        session, case.patient_id, case.scenario.value, case.state, source_detail="test:academia_synthetic_case",
    )
    return case, case_state, case_references


@pytest.mark.parametrize(
    "scenario",
    [SimulationScenario.HEALTHY, SimulationScenario.HYPERTENSION, SimulationScenario.SEPSIS],
)
def test_enabled_scenarios_receive_calculated_pa_labeled_with_provenance(tmp_path, scenario):
    SessionLocal = _session_factory(tmp_path / f"academia_case_{scenario.value}.db")

    with SessionLocal() as session:
        case, case_state, _ = _generate_case_with_calculated_pa(session, scenario, rng=__import__("random").Random(0))

        for name in ("systolic_bp_modelo", "diastolic_bp_modelo", "map_modelo"):
            descriptor = case_state.cardiovascular.get(name)
            assert descriptor is not None, name
            assert descriptor.provenance == Provenance.MODELO_HEMODINAMICO
            assert descriptor.confidence == pytest.approx(HEMODYNAMIC_MODEL_VALIDATED_CONFIDENCE)


def test_sepsis_case_calculated_pa_is_collapsed_consistent_with_shock(tmp_path):
    """No repite la validación fisiológica ya hecha en 'La película' -- solo
    confirma que el valor que llega a la UI de Academia sigue siendo el
    mismo tipo de colapso (PAM muy por debajo de lo normal), no un número
    desconectado del motor."""
    SessionLocal = _session_factory(tmp_path / "academia_case_sepsis_shock.db")

    with SessionLocal() as session:
        case, case_state, _ = _generate_case_with_calculated_pa(
            session, SimulationScenario.SEPSIS, rng=__import__("random").Random(2)
        )
        map_modelo = case_state.cardiovascular.get("map_modelo")
        assert map_modelo.value < 65.0  # muy por debajo de una PAM sana (~93)


@pytest.mark.parametrize(
    "scenario",
    [s for s in SimulationScenario if s.value not in HEMODYNAMIC_MODEL_ENABLED_SCENARIOS],
)
def test_the_nine_non_enabled_scenarios_get_no_calculated_pa_and_no_exception(tmp_path, scenario):
    """Restricción estructural verificada desde el punto de entrada real de
    Academia -- los 9 escenarios sin validación experta completa no
    reciben PA calculada, y el caso no se rompe (HemodynamicModelNotEnabledError
    nunca escapa al llamador)."""
    SessionLocal = _session_factory(tmp_path / f"academia_case_{scenario.value}.db")

    with SessionLocal() as session:
        case, case_state, _ = _generate_case_with_calculated_pa(session, scenario, rng=__import__("random").Random(0))

        assert case_state.cardiovascular.get("map_modelo") is None
        assert case_state.cardiovascular.get("systolic_bp_modelo") is None
        assert case_state.cardiovascular.get("diastolic_bp_modelo") is None
        # El caso sigue teniendo sus datos normales -- nada se rompió camino abajo.
        assert case_state.cardiovascular.get("heart_rate") is not None


def test_coexistence_calculated_pa_and_clinical_reference_survive_together(tmp_path):
    """Cuando el horizonte elegido por generate_case() resulta ser el
    último de la corrida (el único que puede llevar ClinicalReferenceValue,
    ver docstring de run_rich_scenario), ambas fuentes de PA conviven en el
    mismo snapshot -- ninguna sobrescribe a la otra."""
    SessionLocal = _session_factory(tmp_path / "academia_case_coexistence.db")

    with SessionLocal() as session:
        # Semilla que, verificado manualmente, elige el último horizonte (7d)
        # para sepsis -- el único que lleva ClinicalReferenceValue.
        found_coexistence = False
        for seed in range(20):
            case, case_state, references = _generate_case_with_calculated_pa(
                session, SimulationScenario.SEPSIS, rng=__import__("random").Random(seed)
            )
            if references:
                found_coexistence = True
                assert case_state.cardiovascular.get("map_modelo") is not None
                assert len(references) == 3  # systolic_bp, diastolic_bp, map
                assert {r.descriptor for r in references} == {"systolic_bp", "diastolic_bp", "map"}
                break

        assert found_coexistence, "ninguna de las 20 semillas probadas cayó en el último horizonte -- revisar el test"


def test_snapshot_id_used_is_the_exact_horizon_not_the_latest(tmp_path):
    """El corazón de por qué hizo falta get_snapshot_id_at(): confirma que
    la PA calculada se adjunta al snapshot del horizonte que generate_case()
    eligió, no al último de la corrida (que run_rich_scenario ya persistió
    completa antes de que case_bank elija cuál mostrar)."""
    from domain.physiology.state import get_latest_snapshot_id

    SessionLocal = _session_factory(tmp_path / "academia_case_exact_horizon.db")

    with SessionLocal() as session:
        # Busca una semilla cuyo horizonte elegido NO sea el último.
        for seed in range(20):
            case = generate_case(session, scenario=SimulationScenario.SEPSIS, rng=__import__("random").Random(seed))
            snapshot_id = get_snapshot_id_at(session, case.patient_id, case.state.timestamp)
            latest_id = get_latest_snapshot_id(session, case.patient_id)
            if snapshot_id != latest_id:
                # Este es el caso interesante: adjuntar al snapshot resuelto por
                # timestamp, y confirmar que el snapshot "más reciente" (que
                # habría sido el bug de usar get_latest_snapshot_id) NO lo tiene.
                hr = case.state.cardiovascular.get("heart_rate").value
                compute_and_attach_closed_loop_pressure(
                    session, snapshot_id=snapshot_id, scenario="sepsis", heart_rate_bpm=hr,
                    source_detail="test:exact_horizon",
                )
                correct_state = get_state_by_snapshot_id(session, snapshot_id)
                latest_state = get_state_by_snapshot_id(session, latest_id)
                assert correct_state.cardiovascular.get("map_modelo") is not None
                assert latest_state.cardiovascular.get("map_modelo") is None
                return

        pytest.fail("ninguna de las 20 semillas probadas eligió un horizonte no-último -- revisar el test")


def test_divergence_note_present_only_when_both_pa_coexist(tmp_path):
    """Refuerzo del prompt (2026-08-06): cuando la PA calculada y la PA de
    referencia coexisten en un caso, se añade un tercer Finding que instruye
    al narrador a explicar la divergencia como lección (umbral de guía vs.
    estimación específica del paciente), nunca como contradicción. Cuando
    solo hay una de las dos PA, ese Finding NO debe aparecer -- verificado
    en ambos casos, no solo en el que coexiste."""
    SessionLocal = _session_factory(tmp_path / "academia_case_divergence.db")

    with SessionLocal() as session:
        found_coexistence = False
        found_calculated_only = False

        for seed in range(30):
            if found_coexistence and found_calculated_only:
                break
            case, case_state, references = _generate_case_with_calculated_pa(
                session, SimulationScenario.SEPSIS, rng=__import__("random").Random(seed)
            )
            pa_findings = _build_pa_findings(case_state, references, "sepsis")
            names = [f.name for f in pa_findings]

            if references and not found_coexistence:
                found_coexistence = True
                assert names == [
                    "PA calculada por el modelo hemodinámico",
                    "PA de referencia clínica (guía citada)",
                    "Nota sobre la posible divergencia entre las dos PA",
                ]
                divergence = pa_findings[2]
                # Las tres reglas explícitas que pidió el usuario, verificadas
                # literalmente presentes en la instrucción -- no solo "existe
                # un Finding", sino que dice lo que debe decir.
                assert "no como una contradicción" in divergence.meaning
                assert "NUNCA declares una 'correcta' y la otra 'incorrecta'" in divergence.meaning
                assert "NUNCA ajustes ninguna de las dos" in divergence.meaning
                assert "Sepsis-3" in divergence.meaning  # ejemplo concreto de umbral de guía
                assert "PARA ESTE paciente concreto" in divergence.meaning  # estimación específica

            elif not references and not found_calculated_only:
                found_calculated_only = True
                assert names == ["PA calculada por el modelo hemodinámico"]
                assert "Nota sobre la posible divergencia entre las dos PA" not in names

        assert found_coexistence, "ninguna semilla probada coexistió -- revisar el test"
        assert found_calculated_only, "ninguna semilla probada tuvo solo PA calculada -- revisar el test"


@pytest.mark.parametrize(
    "scenario",
    [s for s in SimulationScenario if s.value not in HEMODYNAMIC_MODEL_ENABLED_SCENARIOS],
)
def test_divergence_note_never_applies_to_the_nine_non_enabled_scenarios(tmp_path, scenario):
    """Los 9 escenarios sin PA calculada tampoco pueden recibir la nota de
    divergencia -- no hay nada que diverja si solo existe (a lo sumo) la
    referencia clínica."""
    SessionLocal = _session_factory(tmp_path / f"academia_case_divergence_{scenario.value}.db")

    with SessionLocal() as session:
        case, case_state, references = _generate_case_with_calculated_pa(session, scenario, rng=__import__("random").Random(0))
        pa_findings = _build_pa_findings(case_state, references, scenario.value)
        assert pa_findings == []  # sin map_modelo, _build_pa_findings no arma nada


def test_divergence_citation_is_correct_per_scenario_not_hardcoded_to_sepsis(tmp_path):
    """Corrección (2026-08-06): la cita de la nota de divergencia estaba fija
    en 'Sepsis-3' sin importar el escenario -- correcta para sepsis, un dato
    incorrecto en el contexto para hipertensión o sano. Verifica que ahora
    cada uno de los 3 escenarios validados, cuando coexisten ambas PA, cita
    su propia fuente real (tomada en vivo de `ref_map.citation`, ya
    transcrita en `blood_pressure_references.py` -- no reinventada aquí) con
    el framing correcto -- y que NUNCA aparece la cita de otro escenario."""
    SessionLocal = _session_factory(tmp_path / "academia_case_divergence_citation.db")

    expectations = {
        "sepsis": {"must_contain": ["Sepsis-3", "shock"], "must_not_contain": ["ACC/AHA"]},
        "hypertension": {
            "must_contain": ["ACC/AHA", "categoría diagnóstica de hipertensión"],
            "must_not_contain": ["Sepsis-3"],
        },
        "healthy": {
            "must_contain": ["ACC/AHA", "no un umbral de ninguna categoría patológica"],
            "must_not_contain": ["Sepsis-3"],
        },
    }
    assert set(expectations) == HEMODYNAMIC_MODEL_ENABLED_SCENARIOS  # cubre exactamente los 3 validados

    with SessionLocal() as session:
        for scenario_value, expectation in expectations.items():
            scenario = SimulationScenario(scenario_value)
            found = False
            for seed in range(40):
                case, case_state, references = _generate_case_with_calculated_pa(
                    session, scenario, rng=__import__("random").Random(seed)
                )
                if not references:
                    continue
                found = True
                pa_findings = _build_pa_findings(case_state, references, scenario_value)
                divergence = next(
                    f for f in pa_findings if f.name == "Nota sobre la posible divergencia entre las dos PA"
                )
                ref_map = next(r for r in references if r.descriptor == "map")
                # La cita real del escenario debe estar embebida literalmente --
                # prueba de que se lee en vivo de blood_pressure_references.py,
                # no de un string reescrito a mano en el prompt.
                assert ref_map.citation in divergence.meaning
                for phrase in expectation["must_contain"]:
                    assert phrase in divergence.meaning, f"{scenario_value}: falta {phrase!r}"
                for phrase in expectation["must_not_contain"]:
                    assert phrase not in divergence.meaning, f"{scenario_value}: no debería contener {phrase!r}"
                break
            assert found, f"ninguna semilla probada coexistió para {scenario_value} -- revisar el test"
