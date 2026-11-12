"""Frente cardiovascular, tanda C0 (2026-11-12, Art. I): contrato de escritura de derivados en la frontera del UPS.

REGLA: un valor derivado se escribe al UPS solo si TODAS las entradas de su fórmula llegaron en ese snapshot; una constante
que nadie calcula (`cardiac_output`), el eco de un default (`rhythm_stability`), un duplicado de la SpO2 con otro nombre
(`tissue_oxygenation`) y la potencia alfa fabricada desde el slider de estrés de Twin OS no se escriben nunca.
El punto único de verdad es `domain/physiology/state/derived_contract.py`, consultado solo por el builder. Todo contra
bases TEMPORALES.
"""

import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from app.engines.digital_twin_organism import DigitalTwinOrganism
from domain.physiology.state import (
    Provenance,
    create_patient,
    from_digital_twin_organism,
    get_latest_state,
    init_db,
    make_engine,
    make_session_factory,
)
from domain.physiology.state.derived_contract import (
    DERIVED_CONTRACT,
    accepted_band_powers,
    contract_rows,
    derived_is_writable,
)

MAIN = str(Path("app/main.py").resolve())
NEVER_WRITTEN = {"cardiac_output", "rhythm_stability", "tissue_oxygenation", "perfusion_index"}


@pytest.fixture
def ups(tmp_path):
    engine = make_engine(tmp_path / "c0.db")
    init_db(engine)
    sf = make_session_factory(engine)
    with sf() as s:
        pid = create_patient(s, display_name="contrato C0")
    return sf, pid


def _fields(state):
    return {dom: set(ds.descriptors) for dom, ds in state.all_domains().items() if ds.descriptors}


def _state_from(sensors, confidence=None):
    organism = DigitalTwinOrganism()
    organism.update_from_sensors(sensors)
    return from_digital_twin_organism(organism, "p", provenance=Provenance.SIMULACION, confidence=confidence)


def _press(ups, hub, page, key, before=None):
    sf, pid = ups
    at = AppTest.from_file(MAIN, default_timeout=240)
    at.session_state["biocore_ai_entry_done"] = True
    at.session_state["selected_hub"] = hub
    at.session_state["selected_page"] = page
    at.session_state["twin_shell_ups_session_factory"] = sf
    at.session_state["twin_shell_ups_patient_id"] = pid
    at.run()
    if before is not None:
        before(at)
    buttons = [b for b in at.button if b.key == key]
    assert buttons, f"no hay botón {key} en {page}"
    buttons[0].click().run()
    assert at.exception == [], at.exception
    with sf() as s:
        state = get_latest_state(s, pid)
    assert state is not None, f"{page}: no persistió ningún snapshot"
    return at, state


# ------------------------------------------------------------------------------------------------ la tabla del contrato
def test_the_contract_table_declares_what_is_never_written_and_cites_the_organism_formula():
    never = {(d, f) for d, fields in DERIVED_CONTRACT.items() for f, r in fields.items() if r.never_reason}
    assert never == {
        ("cardiovascular", "cardiac_output"), ("cardiovascular", "rhythm_stability"), ("respiratory", "tissue_oxygenation"),
    }
    for domain, field, needs, why in contract_rows():
        assert "digital_twin_organism.py:" in why, (domain, field)          # archivo:línea de la fórmula real
        assert needs, (domain, field)
    assert derived_is_writable("cardiovascular", "health_score", {"heart_rate", "hrv", "complexity"})
    assert not derived_is_writable("cardiovascular", "health_score", {"heart_rate", "hrv"})
    assert not derived_is_writable("cardiovascular", "cardiac_output", {"heart_rate", "hrv", "complexity", "cardiac_output"})
    assert derived_is_writable("neurological", "attention", {"attention"})                      # alternativa 1
    assert derived_is_writable("neurological", "attention", {"relaxation_level", "alpha_power"})  # alternativa 2
    assert not derived_is_writable("neurological", "attention", {"relaxation_level"})
    with pytest.raises(KeyError):                                   # un derivado sin contrato no se escribe
        derived_is_writable("cardiovascular", "inventado", {"heart_rate"})


def test_every_derived_descriptor_the_builder_can_emit_is_in_the_contract_and_never_a_never_field():
    full = {
        "ecg": {"heart_rate": 72, "hrv": 40, "complexity": 60},
        "respiratory": {"respiratory_rate": 16, "spo2": 97, "ahi": 2},
        "eeg": {"delta_power": 1, "theta_power": 2, "alpha_power": 10, "beta_power": 5, "gamma_power": 1,
                "stress_level": 30, "relaxation_level": 60},
        "emg": {"activation": 30, "efficiency": 80, "fatigue_index": 10},
    }
    state = _state_from(full)
    seen = 0
    for domain, ds in state.all_domains().items():
        for name, d in ds.descriptors.items():
            if d.provenance == Provenance.DERIVADO:
                seen += 1
                assert name in DERIVED_CONTRACT[domain], (domain, name)
                assert not DERIVED_CONTRACT[domain][name].never_reason, (domain, name)
    assert seen >= 15                                               # con todas las entradas, los derivados SÍ se escriben
    assert not (NEVER_WRITTEN & {n for ds in state.all_domains().values() for n in ds.descriptors})


def test_presence_is_decided_by_what_arrived_not_by_the_resulting_value():
    # 70/50/50 enviados de verdad (una medición puede valer 70): el derivado SÍ se escribe...
    sent = _state_from({"ecg": {"heart_rate": 70, "hrv": 50, "complexity": 50}})
    assert {"health_score", "risk_score", "myocardial_stress"} <= set(sent.cardiovascular.descriptors)
    # ...y con los MISMOS valores pero sin enviarlos (defaults del organismo) no.
    defaulted = _state_from({"ecg": {"heart_rate": 70}})
    assert set(defaulted.cardiovascular.descriptors) == {"heart_rate"}
    assert defaulted.cardiovascular.get("heart_rate").value == pytest.approx(70.0)


def test_an_organism_fed_only_with_heart_rate_writes_only_heart_rate():
    state = _state_from({"ecg": {"heart_rate": 72.0}})
    assert _fields(state) == {"cardiovascular": {"heart_rate"}}


def test_an_isolated_band_power_is_not_a_spectrum_and_a_real_spectrum_is_accepted():
    assert accepted_band_powers({"alpha_power": 52.5}) == {}
    assert set(accepted_band_powers({"alpha_power": 10.0, "beta_power": 4.0})) == {"alpha_power", "beta_power"}
    # el payload de los sliders de Twin OS: estrés + alpha fabricada sola -> el dominio neuro queda vacío
    twin_os = _state_from({"eeg": {"stress_level": 35, "alpha_power": max(0, 70 - 35 * 0.5)}})
    assert twin_os.neurological.descriptors == {}


# ------------------------------------------------------------------------------------------- ruta -> campos (exactos)
def test_route_hrv_lab_writes_heart_rate_hrv_and_risk_score_but_no_health_score_nor_rhythm_stability(ups):
    _, state = _press(ups, "Clinical Hub", "📈 HRV Analysis", "hrv_lab_save_to_ups")
    assert _fields(state) == {"cardiovascular": {"heart_rate", "hrv", "risk_score"}}
    assert state.cardiovascular.get("risk_score").provenance == Provenance.DERIVADO


def test_route_patient_pipeline_without_ahi_has_no_apnea_risk_and_no_cardiac_derivatives(ups):
    _, state = _press(ups, "Clinical Hub", "👥 Patient Pipeline", "patient_pipeline_save_state")
    # `hypoxia_risk` sale de la SpO2 sola (digital_twin_organism.py:450): su única entrada SÍ llegó -> se escribe.
    assert _fields(state) == {
        "cardiovascular": {"heart_rate"},
        "respiratory": {"respiratory_rate", "spo2", "hypoxia_risk"},
    }
    resp = state.respiratory.descriptors
    assert "apnea_risk" not in resp and "health_score" not in resp and "risk_score" not in resp


def test_route_twin_os_checkpoint_writes_no_fabricated_alpha_and_no_neurological_domain(ups):
    _, state = _press(ups, "Digital Twin OS", "🧬 Digital Twin OS", "twin_shell_body_sync")
    assert _fields(state) == {
        "cardiovascular": {"heart_rate", "hrv", "risk_score"},
        "respiratory": {"respiratory_rate", "spo2", "hypoxia_risk"},
    }
    assert state.neurological.descriptors == {} and state.muscular.descriptors == {}


def test_route_eeg_lab_writes_the_real_spectrum_and_only_derivatives_whose_inputs_arrived(ups):
    _, state = _press(ups, "Clinical Hub", "🧠 EEG Neuro Lab", "eeg_lab_save_to_ups")
    neuro = set(state.neurological.descriptors)
    assert neuro - {"chi_aperiodic"} == {
        "delta_power", "theta_power", "alpha_power", "beta_power", "gamma_power", "bar", "dar", "tbr", "mental_workload",
    }
    assert set(_fields(state)) == {"neurological"}


def test_route_emg_lab_writes_activation_and_median_frequency_only(ups):
    _, state = _press(ups, "Clinical Hub", "🦾 EMG Muscle Lab", "emg_lab_save_to_ups")
    assert _fields(state) == {"muscular": {"activation", "median_frequency"}}


def test_route_respiratory_lab_is_unchanged_two_fields_with_their_provenance(ups):
    _, state = _press(ups, "Clinical Hub", "💨 Respiratory Lab", "respiratory_lab_save_to_ups")
    assert _fields(state) == {"respiratory": {"respiratory_rate", "spo2"}}
    for d in state.respiratory.descriptors.values():
        assert d.provenance == Provenance.SIMULACION and d.source_detail.startswith("respiratory_lab:")


def test_route_ecg_lab_writes_only_heart_rate_with_the_confidence_the_detector_computed(ups):
    def choose_sinus_case(at):
        [r for r in at.sidebar.radio if r.label == "ECG Source"][0].set_value("Caso clínico (61 disponibles)").run()
        [x for x in at.sidebar.selectbox if x.label == "Diagnóstico primario"][0].set_value("I°AV").run()

    at, state = _press(ups, "Clinical Hub", "🫀 ECG Lab", "ecg_lab_save_to_ups", before=choose_sinus_case)
    assert _fields(state) == {"cardiovascular": {"heart_rate"}}
    hr = state.cardiovascular.get("heart_rate")
    shown = re.search(r"confianza=([0-9.]+)", " ".join(s.value for s in at.success))
    assert shown, [s.value for s in at.success]
    assert hr.confidence == pytest.approx(float(shown.group(1)), abs=0.006)     # la calculada (p. ej. 0.84)...
    assert hr.confidence != pytest.approx(0.75)                                  # ...no el punto medio fijo de la banda


def test_all_routes_together_never_write_the_never_fields(ups):
    seen = set()
    for hub, page, key in (
        ("Clinical Hub", "📈 HRV Analysis", "hrv_lab_save_to_ups"),
        ("Clinical Hub", "👥 Patient Pipeline", "patient_pipeline_save_state"),
        ("Digital Twin OS", "🧬 Digital Twin OS", "twin_shell_body_sync"),
        ("Clinical Hub", "🧠 EEG Neuro Lab", "eeg_lab_save_to_ups"),
        ("Clinical Hub", "🦾 EMG Muscle Lab", "emg_lab_save_to_ups"),
    ):
        _, state = _press(ups, hub, page, key)
        seen |= {n for ds in state.all_domains().values() for n in ds.descriptors}
    assert not (seen & NEVER_WRITTEN)


# ------------------------------------------------------------------------------------ escenarios, casos y simulador
def test_sepsis_simulator_does_not_write_cardiac_output_nor_a_derived_value_with_default_inputs(ups):
    from app.engines.simulation_engine import SimulationEngine, SimulationScenario
    from domain.physiology.scenarios.rich_engine import run_rich_scenario

    sf, pid = ups
    engine_co = [s.cardiac_output for s in SimulationEngine(seed=0).simulate_scenario(SimulationScenario.SEPSIS)]
    assert min(engine_co) < 5.0                                      # el motor SÍ baja el gasto (4.0 -> 2.0)
    with sf() as session:
        steps = list(run_rich_scenario(session, pid, SimulationScenario.SEPSIS, DigitalTwinOrganism(), False, seed=0))
    assert len(steps) == 6
    for step in steps:
        cardio = step.state.cardiovascular.descriptors
        assert set(cardio) == {"heart_rate", "hrv", "risk_score"}
        assert "cardiac_output" not in cardio and "rhythm_stability" not in cardio
        # ahi SÍ llega en el simulador rico -> los derivados respiratorios con ahi real se conservan
        assert {"respiratory_rate", "spo2", "ahi", "health_score", "risk_score", "hypoxia_risk", "apnea_risk"} == set(
            step.state.respiratory.descriptors
        )
        assert step.state.neurological.descriptors == {}


def test_clinical_case_bank_writes_no_default_derived_values(ups):
    import random

    from domain.physiology.scenarios.case_bank import generate_case

    sf, _ = ups
    with sf() as session:
        case = generate_case(session, rng=random.Random(7))
        state = get_latest_state(session, case.patient_id)
    assert not (NEVER_WRITTEN & {n for ds in state.all_domains().values() for n in ds.descriptors})
    assert set(state.cardiovascular.descriptors) <= {"heart_rate", "hrv", "risk_score"}


def test_legacy_scenario_with_real_complexity_still_writes_its_cardiac_derivatives(ups):
    from domain.physiology.scenarios import run_scenario

    sf, pid = ups
    with sf() as session:
        steps = list(run_scenario(session, pid, "taquicardia_estres", steps=3, organism=DigitalTwinOrganism()))
    cardio = set(steps[0].state.cardiovascular.descriptors)
    assert {"heart_rate", "hrv", "health_score", "risk_score", "myocardial_stress"} == cardio   # `complexity` SÍ llegó
    assert "rhythm_stability" not in cardio and "cardiac_output" not in cardio                   # nunca


# ----------------------------------------------------------------------------------------------------------- narrador
def test_narrator_context_has_no_cardiac_output_nor_rhythm_stability_in_sepsis_and_for_an_ecg_only_patient(ups):
    from app.engines.simulation_engine import SimulationScenario
    from domain.physiology.narrator.context import build_context
    from domain.physiology.scenarios.rich_engine import run_rich_scenario
    from domain.physiology.state import save_state

    sf, pid = ups
    with sf() as session:
        for _ in run_rich_scenario(session, pid, SimulationScenario.SEPSIS, DigitalTwinOrganism(), False, seed=0):
            pass
        sepsis_ctx = build_context(session, pid)
        ecg_pid = create_patient(session, display_name="solo ECG")
        organism = DigitalTwinOrganism()
        organism.update_from_sensors({"ecg": {"heart_rate": 72.0}})
        save_state(session, from_digital_twin_organism(organism, ecg_pid, provenance=Provenance.SIMULACION))
        organism.update_from_sensors({"ecg": {"heart_rate": 74.0}})
        save_state(session, from_digital_twin_organism(organism, ecg_pid, provenance=Provenance.SIMULACION))
        ecg_ctx = build_context(session, ecg_pid)
    sepsis_names = {d.name for d in sepsis_ctx.descriptors}
    assert "heart_rate" in sepsis_names and not (NEVER_WRITTEN & sepsis_names)
    sepsis_cardio = {d.name for d in sepsis_ctx.descriptors if d.domain == "cardiovascular"}
    assert sepsis_cardio == {"heart_rate", "hrv", "risk_score"}     # sin `complexity` -> sin health_score cardíaco
    ecg_names = {d.name for d in ecg_ctx.descriptors}
    assert ecg_names == {"heart_rate"}                              # solo ECG: el contexto contiene solo la FC


# -------------------------------------------------------------------------------------- índice de riesgo heurístico
def test_risk_index_without_any_real_cardiovascular_factor_is_not_evaluable_not_low_risk(ups):
    from domain.physiology.ml import build_risk_features
    from domain.physiology.state import save_state
    from src.ai.patient_analytics import PatientRiskPredictor

    sf, pid = ups
    with sf() as session:
        organism = DigitalTwinOrganism()
        organism.update_from_sensors({"respiratory": {"respiratory_rate": 14, "spo2": 97}})
        save_state(session, from_digital_twin_organism(organism, pid, provenance=Provenance.SIMULACION))
        features = build_risk_features(session, pid)
    assert features.heart_rate is None and features.hrv_sdnn is None
    assert features.ecg_pattern is None and features.trend_data == []

    result = PatientRiskPredictor().calculate_risk_score(
        heart_rate=features.heart_rate, hrv_sdnn=features.hrv_sdnn, ecg_pattern=features.ecg_pattern,
        trend_data=features.trend_data,
    )
    assert result["total_risk"] is None and "No evaluable" in result["risk_level"]
    assert "ecg_pattern" not in result["factors_used"] and result["factors_used"] == []


def test_risk_index_trend_needs_two_real_points_and_ecg_pattern_only_if_one_was_recorded():
    predictor = PatientRiskPredictorFactory()
    one = predictor.calculate_risk_score(heart_rate=72, trend_data=[72.0])
    assert "trend" not in one["factors_used"] and "trend" in one["factors_omitted"]
    two = predictor.calculate_risk_score(heart_rate=72, trend_data=[72.0, 73.0])
    assert "trend" in two["factors_used"]
    assert "ecg_pattern" not in one["factors_used"]
    arr = predictor.calculate_risk_score(heart_rate=72, ecg_pattern="arrhythmia")
    assert "ecg_pattern" in arr["factors_used"]


def PatientRiskPredictorFactory():
    from src.ai.patient_analytics import PatientRiskPredictor

    return PatientRiskPredictor()


def test_twin_os_risk_panel_says_not_evaluable_for_a_respiratory_only_patient(ups):
    from domain.physiology.state import save_state

    sf, pid = ups
    organism = DigitalTwinOrganism()
    organism.update_from_sensors({"respiratory": {"respiratory_rate": 14, "spo2": 97}})
    with sf() as session:
        save_state(session, from_digital_twin_organism(organism, pid, provenance=Provenance.SIMULACION))

    def _script():
        import app.supermodules.twin_shell.pages as m
        m.run()

    at = AppTest.from_function(_script, default_timeout=180)
    at.session_state["twin_shell_ups_session_factory"] = sf
    at.session_state["twin_shell_ups_patient_id"] = pid
    at.run()
    assert at.exception == []
    warnings = " ".join(w.value for w in at.warning)
    text = " ".join(" ".join(m.value.split()) for m in at.markdown)
    assert "No evaluable" in warnings
    assert "RIESGO CARDIOVASCULAR" not in text                       # ni «0 %» ni «Bajo riesgo»
    assert "ecg_pattern" not in text


# -------------------------------------------------------------------------------------------------------------- grep
def test_no_code_path_creates_a_cardiac_output_descriptor():
    pattern = re.compile(r"""(PhysiologicalDescriptor\(\s*|descriptors\[\s*)["']cardiac_output["']""")
    offenders = []
    for root in ("app", "domain", "src", "clinical", "visualization"):
        for path in Path(root).rglob("*.py"):
            if pattern.search(path.read_text(encoding="utf-8")):
                offenders.append(str(path))
    assert offenders == []
