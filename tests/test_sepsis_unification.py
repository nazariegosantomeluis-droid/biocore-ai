"""
Unificación 2 (2026-10-31): sepsis desde UNA trayectoria canónica (`src/clinical/sepsis_trajectory.py`). Cubre la
no-divergencia entre los lugares que simulan sepsis (simulador, punto aplicado al organismo, estado persistido en
el UPS), la cadena FC -> motor hemodinámico -> PA de punta a punta, la fase que viaja con la PA calculada y que el
motor hemodinámico (la física) no se tocó.

Hallazgo que estos tests dejan fijado (medido, no supuesto): con CUALQUIER FC canónica de sepsis el motor da una
PAM por debajo de 65 (47 con la FC temprana, 24 con la de shock); la referencia citada (Sepsis-3: 85/55, PAM 65)
es el umbral de shock, no la sepsis temprana. Por eso la PA calculada solo representa a las fases de shock, y
REGLA FIRMADA POR EL EXPERTO (2026-11-02): fuera de shock la PA se DECLINA con motivo (no se calcula ni se
muestra) en lugar de acompañar un número de shock con una nota que lo desmienta.
"""

import re
import subprocess
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from app.engines.digital_twin_organism import DigitalTwinOrganism
from app.engines.simulation_engine import SimulationEngine, SimulationScenario
from app.supermodules.twin_shell.baroreflex_panel import _FIXED_POINT_HR_BPM
from app.supermodules.twin_shell.pages import _attach_calculated_pa_to_case, _build_pa_findings
from domain.physiology.hemodynamics import HEMODYNAMIC_MODEL_VALIDATED_CONFIDENCE, run_closed_loop
from domain.physiology.scenarios import SCENARIOS
from domain.physiology.scenarios.rich_engine import create_ephemeral_basal_patient, run_rich_scenario
from domain.physiology.state import (
    BLOOD_PRESSURE_REFERENCES,
    Provenance,
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


# --- La cadena FC -> motor -> PA, de punta a punta, bajo la REGLA FIRMADA --------------------------
# Decisión clínica del experto (Luis, 2026-11-02), no una regresión: el motor hemodinámico solo modela el shock
# establecido, así que la PA se DECLINA (con motivo) en temprana y progresión y se muestra solo en shock. Antes
# estos tests fijaban la PA en los 6 horizontes con una nota que la desmentía en los tempranos. Las aserciones de
# la fase de shock (PAM ~24, meseta 24h = 7d, referencia en 7d, tres Findings) NO cambiaron.

_EARLY = [h for h in _HORIZONS if sepsis.phase_of(h) != "shock"]    # now, 5min, 30min, 2h
_SHOCK = [h for h in _HORIZONS if sepsis.phase_of(h) == "shock"]    # 24h, 7d
_PA_NAMES = ("systolic_bp_modelo", "diastolic_bp_modelo", "map_modelo")


def _chain(tmp_path):
    """Por cada horizonte: el estado y las referencias que salen de las mismas funciones que usan Academia y el
    modo caso de Twin OS."""
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


def test_the_ups_always_gets_the_canonical_rate_but_the_pa_only_in_shock(tmp_path):
    rows = _chain(tmp_path)
    for horizon, (state, _) in rows.items():
        assert state.cardiovascular.get("heart_rate").value == pytest.approx(sepsis.horizon_vitals(horizon)["hr"]), horizon
        for name in _PA_NAMES:
            present = state.cardiovascular.get(name) is not None
            assert present == (horizon in _SHOCK), (horizon, name, "PA solo en shock, declinada en el resto")


def test_in_shock_the_engine_receives_the_canonical_rate_and_the_pa_keeps_its_validated_values(tmp_path):
    rows = _chain(tmp_path)
    maps = {}
    for horizon in _SHOCK:
        state, _ = rows[horizon]
        hr = state.cardiovascular.get("heart_rate").value
        calculated = state.cardiovascular.get("map_modelo")
        assert calculated.value == pytest.approx(run_closed_loop("sepsis", hr).final_map), (
            "la PA del UPS es la del motor con ESA FC, sin otra FC de por medio"
        )
        assert calculated.provenance == Provenance.MODELO_HEMODINAMICO
        assert calculated.confidence == pytest.approx(HEMODYNAMIC_MODEL_VALIDATED_CONFIDENCE)
        assert calculated.value < _SHOCK_THRESHOLD_MAP, "en shock el cálculo cae por debajo del umbral Sepsis-3"
        maps[horizon] = calculated.value
    assert maps["24h"] == pytest.approx(maps["7d"]), "meseta: 24h y 7d son el mismo punto de la trayectoria"
    assert maps["24h"] == pytest.approx(24.2, abs=0.5)


def test_no_shock_pa_number_appears_before_shock_and_the_engine_limit_that_motivates_it_is_pinned(tmp_path):
    """En temprana/progresión el UPS no guarda ninguna PA calculada. El MOTIVO de la declinación se fija contra el
    motor, que no se tocó: con la FC canónica temprana daría PAM 47 (shock), no la PA de una sepsis temprana. Si
    algún día se recalibra el motor o se firma un modelo de sepsis temprana, la regla se revisa, no este test."""
    rows = _chain(tmp_path)
    for horizon in _EARLY:
        state, refs = rows[horizon]
        assert all(state.cardiovascular.get(name) is None for name in _PA_NAMES), horizon
        assert refs == [], horizon
    assert run_closed_loop("sepsis", sepsis.horizon_vitals("now")["hr"]).final_map == pytest.approx(47.1, abs=1.0)


def test_the_declination_reuses_the_apnea_pattern_and_never_calls_the_engine(tmp_path, monkeypatch):
    """Mismo patrón que apnea: `_attach_calculated_pa_to_case` devuelve el estado intacto y `[]` sin calcular
    nada. Un espía en el motor lo comprueba: no se invoca en las fases tempranas y sí en shock."""
    from app.supermodules.twin_shell import pages

    calls = []
    real = pages.compute_and_attach_closed_loop_pressure
    monkeypatch.setattr(pages, "compute_and_attach_closed_loop_pressure", lambda *a, **k: calls.append(k) or real(*a, **k))
    SessionLocal = _session_factory(tmp_path)
    with SessionLocal() as session:
        patient_id = create_ephemeral_basal_patient(session, SimulationScenario.SEPSIS)
        steps = list(run_rich_scenario(
            session, patient_id, SimulationScenario.SEPSIS, DigitalTwinOrganism(), start_from_current_state=False
        ))
        for horizon, step in zip(_HORIZONS, steps):
            returned_state, refs = _attach_calculated_pa_to_case(session, patient_id, "sepsis", step.state, f"test:{horizon}")
            if horizon in _EARLY:
                assert returned_state is step.state and refs == [], horizon
                assert not calls, f"el motor no debe correr en {horizon}"
    assert len(calls) == len(_SHOCK), "el motor corrió una vez por horizonte de shock y ninguna en los demás"


def test_a_sepsis_state_without_an_identifiable_phase_is_declined_not_assumed_shock(tmp_path):
    """Sin `:horizonte:` en la FC no se puede afirmar que el motor aplique: se declina (falla cerrado)."""
    from domain.physiology.state import create_patient, from_digital_twin_organism, save_state

    SessionLocal = _session_factory(tmp_path)
    with SessionLocal() as session:
        patient_id = create_patient(session, display_name="Sepsis sin horizonte")
        organism = DigitalTwinOrganism()
        organism.apply_sepsis("24h")
        state = from_digital_twin_organism(organism, patient_id)  # sin source_detail de escenario rico: sin horizonte
        save_state(session, state)
        out_state, refs = _attach_calculated_pa_to_case(session, patient_id, "sepsis", state, "test:sin_horizonte")
    assert out_state.cardiovascular.get("map_modelo") is None and refs == []
    finding = _build_pa_findings(out_state, refs, "sepsis")[0]
    assert finding.value == "PA no disponible - fase de la sepsis no identificada (límite del modelo)"


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


def test_the_narrator_gets_the_declination_instead_of_a_number_before_shock(tmp_path):
    rows = _chain(tmp_path)
    expected = {
        "now": "PA no disponible en fase temprana (límite del modelo)",
        "5min": "PA no disponible en fase temprana (límite del modelo)",
        "30min": "PA no disponible en fase temprana (límite del modelo)",
        "2h": "PA no disponible en fase de progresión (límite del modelo)",
    }
    for horizon in _EARLY:
        findings = _build_pa_findings(rows[horizon][0], rows[horizon][1], "sepsis")
        assert [f.name for f in findings] == ["PA del modelo hemodinámico (declinada)"], horizon
        finding = findings[0]
        assert finding.value == expected[horizon]
        assert not re.search(r"\d+\s*/\s*\d+|PAM\s*\d|mmHg", finding.value), "ningún número de PA en la declinación"
        assert "dinámica de shock establecido (vasoplejía completa)" in finding.meaning
        assert "modelo que la plataforma no tiene aún" in finding.meaning
        assert "NO inventes" in finding.meaning


def test_in_shock_the_narrator_gets_the_calculated_pa_with_its_phase_and_no_declination(tmp_path):
    rows = _chain(tmp_path)
    for horizon in _SHOCK:
        findings = _build_pa_findings(rows[horizon][0], rows[horizon][1], "sepsis")
        meaning = findings[0].meaning
        assert "mmHg (PAM" in findings[0].value and "no disponible" not in findings[0].value
        assert "fase de shock séptico" in meaning
        assert "NO calculó" not in meaning
    assert sepsis.horizon_from_source_detail("escenario_rico:sepsis:modo:basal:horizonte:2h") == "2h"
    assert sepsis.horizon_from_source_detail("emg_muscle_lab:origen=x") is None


def test_no_text_pairs_a_pa_number_with_a_note_that_disowns_it():
    """La nota contradictoria ("esta PA NO representa a este paciente") se retiró del código y de la UI: ya no hay
    PA en las fases tempranas que anotar."""
    for path in ("src/clinical/sepsis_trajectory.py", "app/supermodules/twin_shell/pages.py",
                 "app/engines/digital_twin_organism.py", "app/supermodules/academia/pages.py"):
        source = Path(path).read_text(encoding="utf-8")
        assert "NO representa a este paciente" not in source, path
        assert "es lo que el modelo daría si ya estuviera en shock" not in source, path
    for horizon in _HORIZONS:
        note = sepsis.pa_phase_note(sepsis.phase_of(horizon))
        assert "NO representa" not in note
        if horizon in _EARLY:
            assert "PA no disponible" in note and not re.search(r"\d+/\d+|PAM \d", note)


def test_applying_an_early_point_declares_the_pa_declination():
    declaration = DigitalTwinOrganism().apply_sepsis("now")
    assert "fase temprana" in declaration and "PA no disponible en fase temprana (límite del modelo)" in declaration
    assert "shock séptico" in DigitalTwinOrganism().apply_sepsis("24h")


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
    assert "solo modela la fase de **shock**" in text and "se declina (no se muestra)" in text
    assert "NO representa" not in text
