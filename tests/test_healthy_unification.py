"""
Unificación 4 (2026-11-05): "sano" (`SimulationEngine._simulate_healthy`) con variabilidad DECLARADA, función pura
de la semilla, en vez de 7 `np.random.normal` sin semilla (el mismo "sano" daba un paciente distinto en cada
clic, con fatiga de -9.8 e índice cognitivo de 102.6 como valores posibles). Fuente única de "sano":
`src/clinical/healthy_baseline.py`; el banco de casos y las constantes basales del motor derivan de ella.
"""

import inspect
from pathlib import Path

import numpy as np
import pytest

from app.engines.simulation_engine import SimulationEngine, SimulationScenario
from src.clinical import healthy_baseline as hb
from src.signals.ecg.arrhythmia_types import SINUS_NORMAL_RANGE_BPM

_FIELDS = tuple(hb.HEALTHY_VARIABLES)
_SEEDS = range(40)


def _healthy(seed):
    return SimulationEngine(seed=seed).simulate_scenario(SimulationScenario.HEALTHY)


def _vitals(timestep):
    return {k: getattr(timestep, k) for k in _FIELDS}


# --- El test que importa: reproducible -----------------------------------------------------------

@pytest.mark.parametrize("seed", [0, 1, 7, 12345])
def test_same_seed_is_the_same_patient_in_every_click_and_every_horizon(seed):
    first, second = _healthy(seed), _healthy(seed)
    assert [_vitals(t) for t in first] == [_vitals(t) for t in second]
    assert len({tuple(_vitals(t).values()) for t in first}) == 1, "una persona sana: la misma en los 6 horizontes"


def test_the_global_numpy_state_does_not_change_the_healthy_patient():
    """El patrón de arritmia: `np.random.seed` ya no mueve el resultado (antes sí: 7 gaussianas globales)."""
    np.random.seed(1)
    first = [_vitals(t) for t in _healthy(5)]
    np.random.seed(2)
    assert [_vitals(t) for t in _healthy(5)] == first


def test_different_seeds_are_different_people_all_inside_the_declared_ranges():
    people = [_vitals(_healthy(seed)[0]) for seed in _SEEDS]
    for name, (nominal, lo, hi) in hb.HEALTHY_VARIABLES.items():
        values = [p[name] for p in people]
        assert all(lo <= v <= hi for v in values), (name, min(values), max(values))
        assert len({round(v, 3) for v in values}) > 20, f"{name}: otra semilla debe dar otra persona"


def test_seed_zero_is_the_reference_person_with_the_nominal_values():
    """La semilla por defecto del motor es 0: el 'sano' que nadie configuró es el de referencia, estable."""
    assert _vitals(_healthy(0)[0]) == {k: v[0] for k, v in hb.HEALTHY_VARIABLES.items()}
    assert SimulationEngine().simulate_scenario(SimulationScenario.HEALTHY)[0].hr == 72.0


def test_healthy_never_produces_physically_impossible_values():
    """Antes: fatiga -9.8 y cognición 102.6 con el gaussiano sin acotar."""
    for seed in _SEEDS:
        for t in _healthy(seed):
            assert 0 <= t.fatigue_index <= 100 and 0 <= t.cognitive_state <= 100 and 0 <= t.stress_level <= 100
            assert t.spo2 <= 100


# --- Sin np.random oculto ----------------------------------------------------------------------------

def test_no_unseeded_random_is_left_in_the_healthy_path():
    source = inspect.getsource(SimulationEngine._simulate_healthy)
    assert "np.random" not in source and "random" not in source
    assert "np.random" not in Path("app/engines/simulation_engine.py").read_text(encoding="utf-8")
    assert "np.random.normal" not in Path("src/clinical/healthy_baseline.py").read_text(encoding="utf-8")


def test_seizure_after_the_ictal_phase_returns_to_the_same_declared_healthy_person():
    """`_simulate_seizure` devuelve 'sano' a partir de los 5 min: antes heredaba su temblor (sd ~2.8 lpm)."""
    def post(seed):
        return [t.hr for t in SimulationEngine(seed=seed).simulate_scenario(SimulationScenario.SEIZURE)[1:]]

    assert post(3) == post(3) == [hb.instance(3)["hr"]] * 5
    assert post(3) != post(4)


# --- Declarado ---------------------------------------------------------------------------------------------

def test_the_declaration_shows_the_ranges_the_seed_and_this_instance():
    text = SimulationEngine(seed=9).instance_declaration(SimulationScenario.HEALTHY)
    assert "FC 60-85" in text and "semilla 9" in text and "PENDING_VALIDATION" in text
    assert f"FC {hb.instance(9)['hr']:.1f}" in text.split("Esta instancia")[1]
    assert "referencia" in SimulationEngine(seed=0).instance_declaration(SimulationScenario.HEALTHY)
    assert SimulationEngine().instance_declaration(SimulationScenario.SEPSIS) is None


def test_scenario_simulator_ui_declares_the_healthy_range_and_takes_a_seed(tmp_path):
    from streamlit.testing.v1 import AppTest

    from app.utils import patient_session
    from domain.physiology.state import create_patient, init_db, make_engine, make_session_factory

    engine = make_engine(Path(str(tmp_path / "healthy_ui.db")))
    init_db(engine)
    factory = make_session_factory(engine)
    with factory() as session:
        patient_id = create_patient(session, display_name="Paciente prueba sano")

    def _script():
        from app.engines.digital_twin_organism import DigitalTwinOrganism
        from app.supermodules.twin_shell.pages import render_ups_scenario_simulator

        render_ups_scenario_simulator(DigitalTwinOrganism())

    at = AppTest.from_function(_script)
    at.session_state[patient_session._SESSION_FACTORY_KEY] = factory
    at.session_state[patient_session._PATIENT_ID_KEY] = patient_id
    at.run(timeout=60)
    assert at.exception == [], at.exception
    at.selectbox(key="twin_shell_rich_scenario_select").set_value(SimulationScenario.HEALTHY)
    at.run(timeout=60)
    assert any("FC 60-85" in i.value and "semilla 0" in i.value for i in at.info)
    at.number_input(key="twin_shell_rich_arrhythmia_seed").set_value(5)
    at.run(timeout=60)
    assert any("semilla 5" in i.value for i in at.info)


# --- Una sola fuente de "sano" ---------------------------------------------------------------------------------

def test_healthy_heart_rate_lives_inside_the_canonical_normal_sinus_range():
    """'Sano' y el 'Normal' de ECG-12 (unificación 3) no son el mismo concepto -- 'Normal' es el corte clínico del
    ritmo (60-100), 'sano' es el subrango de una persona sana en reposo --, pero comparten el límite: 'sano' va
    contenido en 'Normal' y ambos salen del mismo `SINUS_NORMAL_RANGE_BPM`."""
    nominal, lo, hi = hb.HEALTHY_VARIABLES["hr"]
    assert SINUS_NORMAL_RANGE_BPM[0] <= lo <= nominal <= hi <= SINUS_NORMAL_RANGE_BPM[1]
    for name, (nom, low, high) in hb.HEALTHY_VARIABLES.items():
        assert low <= nom <= high, name


def test_the_engine_baseline_and_the_case_bank_derive_from_the_single_source():
    from domain.physiology.scenarios.case_bank import _BASELINE_JITTER

    for name in ("hr", "hrv", "respiratory_rate", "spo2", "stress_level", "fatigue_index"):
        nominal, lo, hi = hb.HEALTHY_VARIABLES[name]
        assert SimulationEngine.BASELINE_PARAMETERS[name] == nominal
        if name in _BASELINE_JITTER:
            assert _BASELINE_JITTER[name] == (lo, hi)
    source = Path("domain/physiology/scenarios/case_bank.py").read_text(encoding="utf-8")
    assert '"hr": (60.0, 85.0)' not in source, "el jitter del banco ya no es una tabla propia"


def test_the_organism_healthy_preset_uses_the_canonical_nominal_values():
    from app.engines.digital_twin_organism import DigitalTwinOrganism

    organism = DigitalTwinOrganism()
    organism.create_patient_scenario("healthy")
    heart = organism.organs["heart"].metrics.signals
    assert heart["heart_rate"] == hb.HEALTHY_VARIABLES["hr"][0]
    assert heart["hrv"] == hb.HEALTHY_VARIABLES["hrv"][0], "el preset decía HRV 60 y el motor 50"


def test_a_healthy_case_reports_the_base_values_it_really_has(tmp_path):
    """'sano' ignora el estado de partida (es la instancia de la semilla): el banco no puede declarar como
    'base' una FC distinta de la que el caso muestra."""
    import random

    from domain.physiology.scenarios.case_bank import generate_case
    from domain.physiology.state import init_db, make_engine, make_session_factory

    engine = make_engine(tmp_path / "healthy_case.db")
    init_db(engine)
    with make_session_factory(engine)() as session:
        for i in range(5):
            case = generate_case(session, scenario=SimulationScenario.HEALTHY, rng=random.Random(40 + i))
            p = case.parametros
            person = hb.instance(p["semilla_instancia"])
            assert p["fc_base_semilla"] == round(person["hr"], 1)
            assert p["spo2_base_semilla"] == round(person["spo2"], 1)
            assert "Sano" in p["variabilidad_declarada"]
