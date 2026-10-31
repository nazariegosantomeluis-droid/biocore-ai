"""
Unificación 2 (2026-10-31): sepsis desde UNA trayectoria canónica (`src/clinical/sepsis_trajectory.py`). Cubre la
no-divergencia entre los lugares que simulan sepsis (simulador, punto aplicado al organismo, estado persistido en
el UPS), la cadena FC -> motor hemodinámico -> PA de punta a punta, la fase que viaja con la PA calculada y que el
motor hemodinámico (la física) no se tocó.

Hallazgo que estos tests dejan fijado (medido, no supuesto): con CUALQUIER FC canónica de sepsis el motor da una
PAM por debajo de 65 (47 con la FC temprana, 24 con la de shock); la referencia citada (Sepsis-3: 85/55, PAM 65)
es el umbral de shock, no la sepsis temprana. Por eso la PA calculada solo representa a las fases de shock y la
UI y el narrador lo declaran.
"""

import subprocess
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from app.engines.digital_twin_organism import DigitalTwinOrganism
from app.engines.simulation_engine import SimulationEngine, SimulationScenario
from app.supermodules.twin_shell.baroreflex_panel import _FIXED_POINT_HR_BPM
from app.supermodules.twin_shell.pages import _attach_calculated_pa_to_case, _build_pa_findings
from domain.physiology.hemodynamics import run_closed_loop
from domain.physiology.scenarios import SCENARIOS
from domain.physiology.scenarios.rich_engine import create_ephemeral_basal_patient, run_rich_scenario
from domain.physiology.state import (
    BLOOD_PRESSURE_REFERENCES,
    init_db,
    make_engine,
    make_session_factory,
)
from src.clinical import sepsis_trajectory as sepsis

_HORIZONS = list(sepsis.HORIZON_PHASES)
_VITALS = ("hr", "hrv", "respiratory_rate", "spo2", "stress_level")
_SHOCK_THRESHOLD_MAP = BLOOD_PRESSURE_REFERENCES["sepsis"][2].value  # PAM 65, Sepsis-3


def _session_factory(tmp_path):
    engine = make_engine(Path(str(tmp_path / "sepsis.db")))
    init_db(engine)
    return make_session_factory(engine)


# --- Una sola fuente ------------------------------------------------------------------

def test_the_engine_timeline_is_exactly_the_canonical_trajectory():
    timeline = SimulationEngine().simulate_scenario(SimulationScenario.SEPSIS)
    assert [t.time_point for t in timeline] == _HORIZONS
    for step in timeline:
        canonical = sepsis.horizon_vitals(step.time_point)
        for name in _VITALS:
            assert getattr(step, name) == pytest.approx(canonical[name]), (step.time_point, name)


def test_the_trajectory_is_deterministic_and_has_no_hidden_variability():
    first = [(t.hr, t.spo2) for t in SimulationEngine(seed=0).simulate_scenario(SimulationScenario.SEPSIS)]
    again = [(t.hr, t.spo2) for t in SimulationEngine(seed=99).simulate_scenario(SimulationScenario.SEPSIS)]
    assert first == again, "la trayectoria es única: la semilla no la cambia"
    assert "sin variabilidad entre instancias" in sepsis.declare_trajectory()


def test_the_trajectory_evolves_from_early_sepsis_to_shock_with_the_cited_start():
    start, end = sepsis.horizon_vitals("now"), sepsis.horizon_vitals("7d")
    assert start["hr"] > 90 and start["respiratory_rate"] >= 22, "el inicio cumple SIRS (FC > 90) y qSOFA (FR >= 22)"
    assert end["hr"] > start["hr"] and end["respiratory_rate"] > start["respiratory_rate"]
    assert end["spo2"] < start["spo2"] and end["hrv"] < start["hrv"]
    assert [sepsis.phase_of(h) for h in _HORIZONS] == ["temprana"] * 3 + ["progresion"] + ["shock"] * 2
    assert "PENDING_VALIDATION" in sepsis.declare_trajectory()


@pytest.mark.parametrize("horizon", _HORIZONS)
def test_the_applied_point_and_the_simulator_start_from_the_same_values(horizon):
    organism = DigitalTwinOrganism()
    organism.apply_sepsis(horizon)
    heart, lungs, brain = (organism.organs[o].metrics.signals for o in ("heart", "lungs", "brain"))
    canonical = sepsis.horizon_vitals(horizon)
    assert heart["heart_rate"] == pytest.approx(canonical["hr"]) and heart["hrv"] == pytest.approx(canonical["hrv"])
    assert lungs["respiratory_rate"] == pytest.approx(canonical["respiratory_rate"])
    assert lungs["spo2"] == pytest.approx(canonical["spo2"])
    assert brain["stress_level"] == pytest.approx(canonical["stress_level"])


def test_the_old_sepsis_tables_are_retired_not_silently_ignored():
    with pytest.raises(ValueError, match="apply_sepsis"):
        DigitalTwinOrganism().create_patient_scenario("sepsis")
    assert "sepsis_temprana" not in SCENARIOS and not any("sepsis" in name for name in SCENARIOS)
    organism_source = Path("app/engines/digital_twin_organism.py").read_text(encoding="utf-8")
    assert "'respiratory_rate': 28, 'spo2': 92" not in organism_source


def test_the_baroreflex_panel_starts_from_the_canonical_shock_rate():
    assert _FIXED_POINT_HR_BPM["sepsis"] == sepsis.horizon_vitals("24h")["hr"] == 150.0


# --- La cadena FC -> motor -> PA, de punta a punta ---------------------------------------------

def _chain(tmp_path):
    """Por cada horizonte: la FC que llega al UPS, la que recibe el motor y la PAM que vuelve, con las mismas
    funciones que usan Academia y el modo caso de Twin OS."""
    SessionLocal = _session_factory(tmp_path)
    rows = {}
    with SessionLocal() as session:
        patient_id = create_ephemeral_basal_patient(session, SimulationScenario.SEPSIS)
        steps = list(run_rich_scenario(
            session, patient_id, SimulationScenario.SEPSIS, DigitalTwinOrganism(), start_from_current_state=False
        ))
        for horizon, step in zip(_HORIZONS, steps):
            state, references = _attach_calculated_pa_to_case(session, patient_id, "sepsis", step.state, f"test:{horizon}")
            rows[horizon] = (state, references)
    return rows


def test_the_engine_receives_the_canonical_rate_at_every_horizon_and_the_map_follows_the_trajectory(tmp_path):
    rows = _chain(tmp_path)
    maps = {}
    for horizon, (state, _) in rows.items():
        hr = state.cardiovascular.get("heart_rate").value
        assert hr == pytest.approx(sepsis.horizon_vitals(horizon)["hr"]), "el UPS guarda la FC canónica"
        calculated = state.cardiovascular.get("map_modelo").value
        assert calculated == pytest.approx(run_closed_loop("sepsis", hr).final_map), (
            "la PA del UPS es la del motor con ESA FC, sin otra FC de por medio"
        )
        maps[horizon] = calculated
    assert maps["now"] > maps["2h"] > maps["24h"], "la PA cae a lo largo de la trayectoria"
    assert maps["24h"] == pytest.approx(maps["7d"]), "meseta: 24h y 7d son el mismo punto de la trayectoria"
    assert maps["24h"] == pytest.approx(24.2, abs=0.5)


def test_reference_and_engine_tell_the_same_story_the_engine_below_the_shock_threshold(tmp_path):
    """La referencia (Sepsis-3) es el umbral de shock; el motor, el shock establecido: por debajo del umbral en
    todas las fases y más abajo cuanto más avanzada. NO se afirma que el motor dé PAM 65 con la FC temprana: no
    lo da (47) porque no modela sepsis temprana. Si algún día se recalibra, este test hay que actualizarlo."""
    rows = _chain(tmp_path)
    for horizon, (state, _) in rows.items():
        assert state.cardiovascular.get("map_modelo").value < _SHOCK_THRESHOLD_MAP, horizon
    early = rows["now"][0].cardiovascular.get("map_modelo").value
    assert early == pytest.approx(47.1, abs=1.0) and early < _SHOCK_THRESHOLD_MAP - 10


def test_the_reference_only_coexists_at_the_last_horizon_and_the_divergence_is_declared(tmp_path):
    rows = _chain(tmp_path)
    assert all(not refs for h, (_, refs) in rows.items() if h != "7d")
    state, refs = rows["7d"]
    assert {r.descriptor for r in refs} == {"systolic_bp", "diastolic_bp", "map"}
    names = [f.name for f in _build_pa_findings(state, refs, "sepsis")]
    assert names == [
        "PA calculada por el modelo hemodinámico",
        "PA de referencia clínica (guía citada)",
        "Nota sobre la posible divergencia entre las dos PA",
    ]


def test_the_phase_travels_with_the_calculated_pa_to_the_narrator(tmp_path):
    rows = _chain(tmp_path)
    for horizon in ("now", "30min", "2h"):
        meaning = _build_pa_findings(rows[horizon][0], rows[horizon][1], "sepsis")[0].meaning
        assert f"horizonte {horizon}" in meaning and "NO representa a este paciente" in meaning, horizon
    for horizon in ("24h", "7d"):
        meaning = _build_pa_findings(rows[horizon][0], rows[horizon][1], "sepsis")[0].meaning
        assert f"horizonte {horizon}" in meaning and "fase de shock séptico" in meaning, horizon
        assert "NO representa a este paciente" not in meaning
    assert sepsis.horizon_from_source_detail("escenario_rico:sepsis:modo:basal:horizonte:2h") == "2h"
    assert sepsis.horizon_from_source_detail("emg_muscle_lab:origen=x") is None


# --- La física no se tocó -----------------------------------------------------------------------

def test_the_hemodynamic_engine_is_untouched():
    try:
        out = subprocess.run(
            ["git", "diff", "--stat", "HEAD", "--", "domain/physiology/hemodynamics/"],
            capture_output=True, text=True, check=True,
        ).stdout
    except (FileNotFoundError, subprocess.CalledProcessError):
        pytest.skip("git no disponible")
    assert out.strip() == ""


def test_engine_values_that_the_validation_rounds_pinned_are_unchanged():
    """Los puntos fijos del lazo en sepsis que ya fijaron las rondas de validación."""
    assert run_closed_loop("sepsis", 150.0).final_map == pytest.approx(24.2, abs=0.2)
    assert run_closed_loop("healthy", 72.0).final_map == pytest.approx(93.3, abs=0.2)


# --- La UI declara la trayectoria ------------------------------------------------------------------

def test_quick_apply_panel_applies_a_point_and_declares_its_phase():
    def _script():
        import streamlit as st
        from app.engines.digital_twin_organism import DigitalTwinOrganism
        from app.supermodules.twin_shell.pages import render_scenario_and_interventions

        if "org" not in st.session_state:
            st.session_state.org = DigitalTwinOrganism()
        render_scenario_and_interventions(st.session_state.org)

    at = AppTest.from_function(_script)
    at.run(timeout=60)
    assert at.exception == []
    assert not any(b.key == "twin_shell_scenario_sepsis" for b in at.button), "el preset de sepsis ya no existe"
    at.selectbox(key="twin_shell_sepsis_horizon").set_value("24h")
    at.button(key="twin_shell_sepsis_apply").click()
    at.run(timeout=60)
    text = " ".join(i.value for i in at.info)
    assert "horizonte 24h" in text and "fase shock" in text
    assert at.session_state["org"].organs["heart"].metrics.signals["heart_rate"] == pytest.approx(150.0)


def test_scenario_simulator_declares_the_canonical_trajectory_only_for_sepsis(tmp_path):
    from app.utils import patient_session
    from domain.physiology.state import create_patient

    factory = _session_factory(tmp_path)
    with factory() as session:
        patient_id = create_patient(session, display_name="Paciente prueba sepsis")

    def _script():
        from app.engines.digital_twin_organism import DigitalTwinOrganism
        from app.supermodules.twin_shell.pages import render_ups_scenario_simulator

        render_ups_scenario_simulator(DigitalTwinOrganism())

    at = AppTest.from_function(_script)
    at.session_state[patient_session._SESSION_FACTORY_KEY] = factory
    at.session_state[patient_session._PATIENT_ID_KEY] = patient_id
    at.run(timeout=60)
    assert at.exception == [], at.exception
    assert not any("Trayectoria canónica de sepsis" in i.value for i in at.info)

    at.selectbox(key="twin_shell_rich_scenario_select").set_value(SimulationScenario.SEPSIS)
    at.run(timeout=60)
    text = " ".join(i.value for i in at.info)
    assert "Trayectoria canónica de sepsis" in text and "PENDING_VALIDATION" in text
    assert "| 24h | shock | 150 | 32 | 85 |" in text
    assert "solo describe la fase de **shock**" in text
