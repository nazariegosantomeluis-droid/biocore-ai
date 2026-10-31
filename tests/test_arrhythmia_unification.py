"""
Unificación 1 (2026-10-31): "arritmia" genérico-aleatorio reemplazado por tipos específicos, desde una sola
fuente (`src/signals/ecg/arrhythmia_types.py`), con variabilidad DECLARADA. Cubre: la fuente única, la ausencia
de azar oculto (instancia = tipo + semilla, dentro del rango declarado), la no-divergencia entre los lugares que
simulan un tipo (simulador, organismo, ECG-12, entrenador), los eventos del UPS, el flutter que antes fallaba y
que la UI declare el rango.
"""

from pathlib import Path

import numpy as np
import pytest
from streamlit.testing.v1 import AppTest

from app.engines.digital_twin_organism import DigitalTwinOrganism
from app.engines.simulation_engine import ARRHYTHMIA_SCENARIO_TYPE, SimulationEngine, SimulationScenario
from clinical.ecg_analyzer import ECGAnalyzer
from domain.physiology.state import EventType, Provenance, from_digital_twin_organism
from src.signal_generator import ECGGenerator
from src.signals.ecg.advanced_patterns import AdvancedEcgPatterns
from src.signals.ecg.arrhythmia_types import (
    ARRHYTHMIA_TYPES,
    EVENT_ALWAYS,
    EVENT_DEPENDS_ON_HR,
    EVENT_NEVER,
    declare_instance,
    get_type,
    instance_hr,
)

_SEEDS = range(30)
_SCENARIO_OF = {key: scenario for scenario, key in ARRHYTHMIA_SCENARIO_TYPE.items()}


def _timeline_hr(type_key, seed):
    return [t.hr for t in SimulationEngine(seed=seed).simulate_scenario(_SCENARIO_OF[type_key])]


def _measured_hr(signal, fs):
    peaks = ECGAnalyzer(fs=fs).detect_r_peaks_tkeo(np.asarray(signal)) / fs
    return 60.0 / float(np.mean(np.diff(peaks)))


# --- Una sola fuente ----------------------------------------------------------------

def test_the_generic_arrhythmia_is_gone_and_the_types_are_the_single_source():
    assert not hasattr(SimulationScenario, "ARRHYTHMIA")
    assert set(ARRHYTHMIA_SCENARIO_TYPE.values()) == set(ARRHYTHMIA_TYPES)
    assert set(ARRHYTHMIA_TYPES) == {"afib", "aflutter", "svt", "sbrady"}
    for t in ARRHYTHMIA_TYPES.values():
        assert 0 < t.hr_min_bpm <= t.hr_max_bpm


def test_the_old_arrhythmia_preset_is_retired_not_silently_ignored():
    with pytest.raises(ValueError, match="apply_arrhythmia"):
        DigitalTwinOrganism().create_patient_scenario("arrhythmia")


def test_no_parallel_arrhythmia_tables_are_left():
    """Las FC propias que estas fuentes tenían (FA a 110/112 fijo, 120 con recorte 80-180, flutter 150 fijo,
    preset 95) ya no existen: salen del tipo canónico."""
    page = Path("app/supermodules/ecg_12/page_content.py").read_text(encoding="utf-8")
    assert "ventricular_rate=110" not in page and "ventricular_rate=150" not in page
    trainer = Path("src/signal_generator.py").read_text(encoding="utf-8")
    assert "avg_hr: float = 120" not in trainer and "np.clip(hr, 80, 180)" not in trainer
    from domain.physiology.scenarios import SCENARIOS
    assert "fibrilacion_estres" not in SCENARIOS and "taquicardia_estres" in SCENARIOS


# --- Variabilidad declarada: ni azar oculto ni valores fuera del rango ---------------

@pytest.mark.parametrize("type_key", sorted(ARRHYTHMIA_TYPES))
def test_every_instance_stays_inside_the_declared_range(type_key):
    t = get_type(type_key)
    for seed in _SEEDS:
        for hr in _timeline_hr(type_key, seed):
            assert t.hr_min_bpm <= hr <= t.hr_max_bpm, (type_key, seed, hr)


@pytest.mark.parametrize("type_key", sorted(ARRHYTHMIA_TYPES))
def test_same_type_and_seed_give_the_same_patient_regardless_of_global_random_state(type_key):
    """El `np.random` silencioso de antes daba 163 lpm o 81 lpm con el mismo clic. Ahora la instancia es función
    pura de (tipo, semilla): el estado global de numpy no la afecta."""
    np.random.seed(1)
    first = _timeline_hr(type_key, 7)
    np.random.seed(2)
    second = _timeline_hr(type_key, 7)
    assert first == second


def test_regular_types_hold_one_rate_and_the_irregular_one_varies_within_its_range():
    for key in ("aflutter", "svt", "sbrady"):
        assert len(set(_timeline_hr(key, 3))) == 1, f"{key} es regular: una sola FC por episodio"
    assert len(set(_timeline_hr("afib", 3))) > 1, "la FA es irregularmente irregular: varía entre horizontes"


def test_other_seeds_give_other_instances_inside_the_same_range_except_for_a_single_value_type():
    for key in ("afib", "svt", "sbrady"):
        assert len({round(_timeline_hr(key, seed)[0]) for seed in _SEEDS}) > 5, key
    assert get_type("aflutter").hr_min_bpm == get_type("aflutter").hr_max_bpm == 150.0
    assert {instance_hr("aflutter", seed) for seed in _SEEDS} == {150.0}


def test_the_declaration_shows_range_seed_and_value_and_is_only_for_arrhythmias():
    text = declare_instance("afib", 5, (0, 5, 30, 120, 1440, 10080))
    assert "100-160" in text and "irregularmente irregular" in text and "semilla 5" in text
    assert "PENDING_VALIDATION" in text
    assert "no varía con la semilla" in declare_instance("aflutter", 5, (0,))
    engine = SimulationEngine(seed=5)
    assert engine.instance_declaration(SimulationScenario.ARRHYTHMIA_AFIB) == text
    assert engine.instance_declaration(SimulationScenario.SEPSIS) is None


# --- No-divergencia: el mismo tipo da la misma fisiología en todos los lugares -----------

@pytest.mark.parametrize("type_key", sorted(ARRHYTHMIA_TYPES))
def test_the_quick_apply_and_the_simulator_start_from_the_same_instance(type_key):
    for seed in (0, 4, 11):
        organism = DigitalTwinOrganism()
        organism.apply_arrhythmia(type_key, seed)
        applied = organism.organs["heart"].metrics.signals["heart_rate"]
        assert applied == pytest.approx(_timeline_hr(type_key, seed)[0])
        assert applied == pytest.approx(instance_hr(type_key, seed))


def test_apply_arrhythmia_touches_only_the_heart_rate():
    organism = DigitalTwinOrganism()
    organism.create_patient_scenario("sepsis")
    heart, lungs = organism.organs["heart"].metrics.signals, organism.organs["lungs"].metrics.signals
    before = dict(heart), dict(lungs)
    organism.apply_arrhythmia("svt", 2)
    heart, lungs = organism.organs["heart"].metrics.signals, organism.organs["lungs"].metrics.signals
    # Entradas medidas intactas (HRV, FR, SpO2); lo derivado (p. ej. rr_modulation) lo recalcula el organismo.
    assert heart["hrv"] == before[0]["hrv"]
    assert lungs["respiratory_rate"] == before[1]["respiratory_rate"] and lungs["spo2"] == before[1]["spo2"]
    assert heart["heart_rate"] == pytest.approx(instance_hr("svt", 2))


def test_ecg12_uses_the_canonical_rate_for_each_rhythm_type():
    """AF, flutter y bradicardia: la FC del trazado es la del tipo (antes 112 fijo, 150 fijo y el slider a 75
    con etiqueta de bradicardia) y la métrica de la página muestra la FC realmente generada."""
    expected = {"Fibrilación": ("afib", "af"), "Flutter": ("aflutter", "flutter"), "Bradicardia": ("sbrady", "bradycardia")}

    def _script():
        import app.supermodules.ecg_12.pages as m
        m.run()

    for label_part, (type_key, condition) in expected.items():
        at = AppTest.from_function(_script)
        at.run(timeout=60)
        box = next(b for b in at.selectbox if "Escenario" in b.label)
        box.set_value(next(o for o in box.options if label_part in o))
        next(b for b in at.button if "Generar ECG" in b.label).click()
        at.run(timeout=60)
        assert at.exception == [], (label_part, at.exception)
        t = get_type(type_key)
        assert at.session_state["condition"] == condition
        assert at.session_state["heart_rate"] == pytest.approx(t.nominal_hr_bpm)
        assert t.hr_min_bpm - 2 <= _measured_hr(at.session_state["ecg_data"]["II"], 500) <= t.hr_max_bpm + 2
        assert any("rango declarado" in c.value for c in at.caption), "la página declara el rango del tipo"


def test_trainer_atrial_fibrillation_and_bradycardia_follow_the_canonical_types():
    afib, sbrady = get_type("afib"), get_type("sbrady")
    _, af_signal = ECGGenerator.get_case("fibrilacion_auricular", 20, 250)
    assert afib.hr_min_bpm - 5 <= _measured_hr(af_signal, 250) <= afib.hr_max_bpm + 5
    _, brady_signal = ECGGenerator.get_case("bradicardia", 20, 250)
    assert _measured_hr(brady_signal, 250) == pytest.approx(sbrady.nominal_hr_bpm, abs=3)
    a, b = ECGGenerator.generate_afib(10, 250)[1], ECGGenerator.generate_afib(10, 250)[1]
    assert np.array_equal(a, b), "misma semilla (por defecto), mismo trazado"
    assert not np.array_equal(a, ECGGenerator.generate_afib(10, 250, seed=1)[1])


# --- Eventos del UPS coherentes con cada tipo ---------------------------------------------

def _hr_event(hr):
    organism = DigitalTwinOrganism()
    organism.update_from_sensors({"ecg": {"heart_rate": hr}})
    state = from_digital_twin_organism(organism, "p", Provenance.SIMULACION)
    return [e for e in state.events if e.event_type == EventType.ARRHYTHMIA_RISK_HR_EXTREME]


@pytest.mark.parametrize("type_key", sorted(ARRHYTHMIA_TYPES))
def test_declared_ups_event_matches_what_the_ups_actually_emits(type_key):
    """`ups_hr_event` se verifica contra el builder real, no se confía en la declaración."""
    t = get_type(type_key)
    rates = [t.hr_min_bpm, t.hr_max_bpm] + [instance_hr(type_key, s, m) for s in _SEEDS for m in (0, 30)]
    fired = {bool(_hr_event(hr)) for hr in rates}
    expected = {EVENT_ALWAYS: {True}, EVENT_NEVER: {False}, EVENT_DEPENDS_ON_HR: {True, False}}[t.ups_hr_event]
    assert fired == expected, (type_key, t.ups_hr_event, fired)


def test_fast_rhythms_raise_the_rate_event_and_the_ups_gap_for_bradycardia_is_explicit():
    assert all(_hr_event(hr) for hr in (130.0, 150.0, 185.0))
    assert _hr_event(130.0)[0].severity.value == "warning" and _hr_event(185.0)[0].severity.value == "critical"
    assert not _hr_event(get_type("sbrady").hr_max_bpm) and not _hr_event(get_type("sbrady").hr_min_bpm)
    assert _hr_event(35.0), "el UPS solo marca bradicardia por debajo de 40 lpm: el rango 40-59 no dispara evento"
    assert get_type("sbrady").ups_hr_event == EVENT_NEVER


# --- Flutter: ya se genera -----------------------------------------------------------------------

def test_atrial_flutter_is_generated_with_its_sawtooth_at_300_per_minute():
    """Antes `np.sawtooth` (no existe en numpy) hacía fallar el flutter con AttributeError."""
    signal, time = AdvancedEcgPatterns.generate_atrial_flutter(
        duration=20.0, sampling_rate=500, flutter_rate=300, ventricular_rate=90
    )
    assert signal.shape == time.shape and np.all(np.isfinite(signal))
    spectrum = np.abs(np.fft.rfft(signal - signal.mean()))
    freqs = np.fft.rfftfreq(signal.size, 1 / 500)
    band = lambda lo, hi: spectrum[(freqs >= lo) & (freqs <= hi)].max()
    assert band(4.9, 5.1) > 10 * band(5.3, 5.5), "pico de las ondas F a 5 Hz (300/min)"
    again, _ = AdvancedEcgPatterns.generate_atrial_flutter(
        duration=20.0, sampling_rate=500, flutter_rate=300, ventricular_rate=90
    )
    assert np.array_equal(signal, again)


# --- La UI declara el rango ---------------------------------------------------------------------------

def test_quick_apply_panel_declares_range_and_seed():
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
    at.selectbox(key="twin_shell_arrhythmia_type").set_value("svt")
    at.number_input(key="twin_shell_arrhythmia_seed").set_value(3)
    at.button(key="twin_shell_arrhythmia_apply").click()
    at.run(timeout=60)
    text = " ".join(i.value for i in at.info)
    assert "Rango declarado de Taquicardia supraventricular" in text and "150-220" in text and "semilla 3" in text
    assert str(round(instance_hr("svt", 3))) in text
    assert not any("arrhythmia" in b.key for b in at.button if b.key and b.key.startswith("twin_shell_scenario_"))


def test_scenario_simulator_declares_the_variability_before_running(tmp_path):
    from app.utils import patient_session
    from domain.physiology.state import create_patient, init_db, make_engine, make_session_factory

    factory = make_session_factory(_init_engine(tmp_path, make_engine, init_db))
    with factory() as session:
        patient_id = create_patient(session, display_name="Paciente prueba arritmia")

    def _script():
        import streamlit as st
        from app.engines.digital_twin_organism import DigitalTwinOrganism
        from app.supermodules.twin_shell.pages import render_ups_scenario_simulator

        render_ups_scenario_simulator(DigitalTwinOrganism())

    at = AppTest.from_function(_script)
    at.session_state[patient_session._SESSION_FACTORY_KEY] = factory
    at.session_state[patient_session._PATIENT_ID_KEY] = patient_id
    at.run(timeout=60)
    assert at.exception == [], at.exception
    assert not any("Rango declarado" in i.value for i in at.info)

    box = at.selectbox(key="twin_shell_rich_scenario_select")
    box.set_value(SimulationScenario.ARRHYTHMIA_AFIB)
    at.run(timeout=60)
    assert any("Rango declarado de Fibrilación auricular" in i.value and "semilla 0" in i.value for i in at.info)

    at.number_input(key="twin_shell_rich_arrhythmia_seed").set_value(5)
    at.run(timeout=60)
    assert any("semilla 5" in i.value for i in at.info)

    box = at.selectbox(key="twin_shell_rich_scenario_select")
    box.set_value(SimulationScenario.SEPSIS)
    at.run(timeout=60)
    assert not any("Rango declarado" in i.value for i in at.info), "solo las arritmias declaran un rango"


def _init_engine(tmp_path, make_engine, init_db):
    engine = make_engine(Path(str(tmp_path / "arrhythmia_ui.db")))
    init_db(engine)
    return engine
