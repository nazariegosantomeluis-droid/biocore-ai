"""
Learning Hub — Réplica al modo caso clínico de Twin OS de la conexión de PA
calculada que ya existía en Academia (2026-08-06).

Cubre la lógica exacta que vive en
`app/supermodules/twin_shell/pages.py::render_clinical_case_mode()` (el
manejador de "🆕 Nuevo caso clínico"), replicada aquí sin Streamlit -- usando
las MISMAS funciones compartidas (`_attach_calculated_pa_to_case`,
`_build_pa_findings`, `_DIVERGENCE_THRESHOLD_MEANING_BY_SCENARIO`) que
`tests/test_academia_case_hemodynamics.py` ya prueba para Academia. No se
duplica el código de producción -- se importa igual que
`app/supermodules/academia/pages.py` lo hace en vivo.

Diferencia real frente a Academia, verificada aquí: Twin OS no elige un
horizonte al azar -- `render_clinical_case_mode()` siempre agota los 6
horizontes de `run_rich_scenario()` y usa el ÚLTIMO (`step.state` en la
última iteración), nunca uno intermedio. Por construcción, el snapshot que
se muestra SIEMPRE coincide con el más reciente del paciente -- a diferencia
de Academia (`case_bank.generate_case()`, que elige cualquiera de los 6),
aquí no hay manera de que ese bug ocurra. `_attach_calculated_pa_to_case()`
resuelve igual por timestamp exacto en ambos modos (no asume cuál
comportamiento tiene el llamador), y por eso la referencia clínica coexiste
SIEMPRE que el escenario tiene una (nunca depende de una semilla al azar,
a diferencia de Academia)."""

import pytest

from app.engines.digital_twin_organism import DigitalTwinOrganism
from app.engines.simulation_engine import SimulationScenario
from app.supermodules.twin_shell.pages import (
    _DIVERGENCE_THRESHOLD_MEANING_BY_SCENARIO,
    _attach_calculated_pa_to_case,
    _build_pa_findings,
)
from domain.physiology.hemodynamics import HEMODYNAMIC_MODEL_ENABLED_SCENARIOS, HEMODYNAMIC_MODEL_VALIDATED_CONFIDENCE
from domain.physiology.scenarios.rich_engine import run_rich_scenario
from domain.physiology.state import (
    Provenance,
    create_patient,
    get_latest_snapshot_id,
    init_db,
    make_engine,
    make_session_factory,
)


def _session_factory(path):
    engine = make_engine(path)
    init_db(engine)
    return make_session_factory(engine)


def _generate_twin_shell_case(session, scenario):
    """Réplica exacta del manejador "Nuevo caso clínico" de
    `render_clinical_case_mode()`: agota los 6 horizontes y usa el último."""
    patient_id = create_patient(session, display_name="Caso clínico interactivo (test)")
    organism = DigitalTwinOrganism()
    last_step = None
    for step in run_rich_scenario(session, patient_id, scenario, organism, start_from_current_state=False):
        last_step = step

    case_state, case_references = _attach_calculated_pa_to_case(
        session, patient_id, scenario.value, last_step.state, source_detail="test:twin_shell_clinical_case_mode",
    )
    return patient_id, case_state, case_references


@pytest.mark.parametrize(
    "scenario",
    [SimulationScenario.HEALTHY, SimulationScenario.HYPERTENSION, SimulationScenario.SEPSIS],
)
def test_enabled_scenarios_receive_calculated_pa_in_twin_shell_mode(tmp_path, scenario):
    SessionLocal = _session_factory(tmp_path / f"twin_shell_case_{scenario.value}.db")

    with SessionLocal() as session:
        _, case_state, _ = _generate_twin_shell_case(session, scenario)

        for name in ("systolic_bp_modelo", "diastolic_bp_modelo", "map_modelo"):
            descriptor = case_state.cardiovascular.get(name)
            assert descriptor is not None, name
            assert descriptor.provenance == Provenance.MODELO_HEMODINAMICO
            assert descriptor.confidence == pytest.approx(HEMODYNAMIC_MODEL_VALIDATED_CONFIDENCE)


@pytest.mark.parametrize(
    "scenario",
    [s for s in SimulationScenario if s.value not in HEMODYNAMIC_MODEL_ENABLED_SCENARIOS],
)
def test_the_nine_non_enabled_scenarios_get_no_calculated_pa_in_twin_shell_mode(tmp_path, scenario):
    SessionLocal = _session_factory(tmp_path / f"twin_shell_case_{scenario.value}.db")

    with SessionLocal() as session:
        _, case_state, case_references = _generate_twin_shell_case(session, scenario)

        assert case_state.cardiovascular.get("map_modelo") is None
        assert case_state.cardiovascular.get("systolic_bp_modelo") is None
        assert case_state.cardiovascular.get("diastolic_bp_modelo") is None
        assert case_state.cardiovascular.get("heart_rate") is not None  # el caso sigue intacto
        pa_findings = _build_pa_findings(case_state, case_references, scenario.value)
        assert pa_findings == []


def test_twin_shell_case_always_uses_the_last_horizon_so_coexistence_is_never_random(tmp_path):
    """A diferencia de Academia, el modo caso de Twin OS SIEMPRE muestra el
    último horizonte -- por lo tanto, para un escenario con
    ClinicalReferenceValue, la coexistencia con la PA calculada NO depende
    de una semilla al azar, ocurre siempre. Confirma también que el
    snapshot usado es el mismo que `get_latest_snapshot_id()` -- sin el
    riesgo de horizonte-no-último que sí existe en Academia."""
    SessionLocal = _session_factory(tmp_path / "twin_shell_case_always_last.db")

    with SessionLocal() as session:
        patient_id, case_state, case_references = _generate_twin_shell_case(session, SimulationScenario.SEPSIS)

        assert len(case_references) == 3  # systolic_bp, diastolic_bp, map -- siempre, no a veces
        assert {r.descriptor for r in case_references} == {"systolic_bp", "diastolic_bp", "map"}
        assert case_state.cardiovascular.get("map_modelo") is not None

        # El snapshot que recibió la PA calculada es el mismo que "el más
        # reciente del paciente" -- por construcción, no por casualidad.
        latest_id = get_latest_snapshot_id(session, patient_id)
        from domain.physiology.state import get_state_by_snapshot_id

        latest_state = get_state_by_snapshot_id(session, latest_id)
        assert latest_state.cardiovascular.get("map_modelo") is not None


def test_divergence_citation_is_correct_per_scenario_in_twin_shell_mode_too(tmp_path):
    """Misma verificación que en Academia (mismo bug, misma corrección,
    misma función compartida) -- confirma que la corrección de la cita
    fija en Sepsis-3 también cubre el modo caso de Twin OS, no solo
    Academia, porque ambos llaman al mismo `_build_pa_findings()`."""
    SessionLocal = _session_factory(tmp_path / "twin_shell_case_divergence_citation.db")

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
    assert set(expectations) == HEMODYNAMIC_MODEL_ENABLED_SCENARIOS

    with SessionLocal() as session:
        for scenario_value, expectation in expectations.items():
            scenario = SimulationScenario(scenario_value)
            _, case_state, case_references = _generate_twin_shell_case(session, scenario)
            assert case_references  # siempre coexiste en este modo (ver test de arriba)

            pa_findings = _build_pa_findings(case_state, case_references, scenario_value)
            divergence = next(f for f in pa_findings if f.name == "Nota sobre la posible divergencia entre las dos PA")
            ref_map = next(r for r in case_references if r.descriptor == "map")

            assert ref_map.citation in divergence.meaning
            for phrase in expectation["must_contain"]:
                assert phrase in divergence.meaning, f"{scenario_value}: falta {phrase!r}"
            for phrase in expectation["must_not_contain"]:
                assert phrase not in divergence.meaning, f"{scenario_value}: no debería contener {phrase!r}"


def test_twin_shell_and_academia_share_the_exact_same_functions_not_copies():
    """Prueba de diseño, no de comportamiento: confirma que Academia importa
    estos símbolos DIRECTAMENTE de twin_shell.pages (mismo objeto en
    memoria) -- si algún día alguien "desconecta" el import y pega una
    copia local en academia/pages.py, este test lo detecta."""
    import app.supermodules.academia.pages as academia_pages
    import app.supermodules.twin_shell.pages as twin_shell_pages

    assert academia_pages._attach_calculated_pa_to_case is twin_shell_pages._attach_calculated_pa_to_case
    assert academia_pages._build_pa_findings is twin_shell_pages._build_pa_findings
