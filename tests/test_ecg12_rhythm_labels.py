"""
Unificación 3 (2026-11-05): la etiqueta de ECG-12 produce la fisiología que nombra. Antes "Taquicardia sinusal"
dibujaba el slider de FC (75 por defecto: la etiqueta no hacía nada), "Normal" aceptaba cualquier FC del slider, y
WPW / QT largo mostraban en la métrica el slider aunque el trazado salía a otra FC (74.9 y 60.0). La FC sale de
la fuente única de tipos de ritmo (`src/signals/ecg/arrhythmia_types.py`) y la métrica es la FC realmente generada.
La FC se mide sobre el trazado (picos R), no se lee del parámetro que se le dio al generador.
"""

from pathlib import Path

import numpy as np
import pytest
from streamlit.testing.v1 import AppTest

from clinical.ecg_analyzer import ECGAnalyzer
from src.signals.ecg.arrhythmia_types import SINUS_NORMAL_RANGE_BPM, get_type
from src.signals.ecg.twelve_lead_generator import generate_12lead_example


def _measured_hr(signal, fs=500):
    peaks = ECGAnalyzer(fs=fs).detect_r_peaks_tkeo(np.asarray(signal)) / fs
    return 60.0 / float(np.mean(np.diff(peaks)))


def _generate(label_part, slider=None):
    def _script():
        import app.supermodules.ecg_12.pages as m
        m.run()

    at = AppTest.from_function(_script)
    at.run(timeout=90)
    box = next(b for b in at.selectbox if "Escenario" in b.label)
    box.set_value(next(o for o in box.options if label_part in o))
    if slider is not None:
        next(s for s in at.slider if "Frecuencia" in s.label).set_value(slider)
    next(b for b in at.button if "Generar ECG" in b.label).click()
    at.run(timeout=90)
    assert at.exception == [], (label_part, slider, at.exception)
    return at, _measured_hr(at.session_state["ecg_data"]["II"])


# --- La fuente: taquicardia sinusal es un tipo canónico, como la bradicardia ------------------------------

def test_sinus_tachycardia_is_a_canonical_type_next_to_sinus_bradycardia():
    t = get_type("stachy")
    assert (t.hr_min_bpm, t.hr_max_bpm, t.irregular) == (100.0, 140.0, False)
    assert t.nominal_hr_bpm == 120.0
    assert SINUS_NORMAL_RANGE_BPM == (60.0, 100.0)
    # los rangos de bradicardia, normal y taquicardia sinusales no se solapan (solo se tocan en sus cortes clínicos)
    assert get_type("sbrady").hr_max_bpm < SINUS_NORMAL_RANGE_BPM[0] <= SINUS_NORMAL_RANGE_BPM[1] <= t.hr_min_bpm


# --- El test que importa: la etiqueta produce la FC que dice, aunque el slider diga otra cosa -------------

@pytest.mark.parametrize("slider", [30, 75, 200])
def test_tachycardia_label_gives_over_100_in_trace_and_metric_whatever_the_slider_says(slider):
    at, measured = _generate("Taquicardia sinusal", slider)
    assert at.session_state["condition"] == "tachycardia"
    assert at.session_state["heart_rate"] == get_type("stachy").nominal_hr_bpm > 100
    assert measured > 100, f"slider {slider}: el trazado de 'Taquicardia' salió a {measured:.1f} lpm"


@pytest.mark.parametrize("slider", [30, 75, 200])
def test_bradycardia_label_gives_under_60_in_trace_and_metric_whatever_the_slider_says(slider):
    at, measured = _generate("Bradicardia", slider)
    assert at.session_state["heart_rate"] == get_type("sbrady").nominal_hr_bpm < 60
    assert measured < 60, f"slider {slider}: {measured:.1f} lpm"


@pytest.mark.parametrize("slider", [30, 75, 200])
def test_normal_label_stays_inside_the_normal_sinus_range_whatever_the_slider_says(slider):
    at, measured = _generate("Normal -", slider)
    lo, hi = SINUS_NORMAL_RANGE_BPM
    assert lo <= at.session_state["heart_rate"] <= hi
    assert lo - 2 <= measured <= hi + 2, f"slider {slider}: 'Normal' salió a {measured:.1f} lpm"
    if slider == 75:
        assert at.session_state["heart_rate"] == 75, "dentro del rango normal el slider sigue mandando"
    else:
        assert any("limit" in c.value.lower() for c in at.caption), "si se recorta el slider, la página lo dice"


def test_the_three_labels_no_longer_collapse_to_the_same_rate():
    rates = {p: _generate(p, 75)[1] for p in ("Taquicardia sinusal", "Normal -", "Bradicardia")}
    assert rates["Taquicardia sinusal"] > 100 > rates["Normal -"] > 60 > rates["Bradicardia"], rates


def test_the_hr_slider_is_disabled_when_the_label_fixes_the_rate():
    at, _ = _generate("Taquicardia sinusal")
    assert next(s for s in at.slider if "Frecuencia" in s.label).disabled
    at, _ = _generate("STEMI Anterior")
    assert not next(s for s in at.slider if "Frecuencia" in s.label).disabled


# --- Métrica = FC generada, en TODAS las condiciones (WPW y QT largo mostraban el slider y trazaban otra) --

@pytest.mark.parametrize("label_part", [
    "Normal -", "Taquicardia sinusal", "Bradicardia", "STEMI Anterior", "derecha (RBBB)", "izquierda (LBBB)",
    "(LVH)", "Fibrilación", "Flutter", "WPW", "QT largo",
])
def test_the_metric_is_the_rate_the_trace_really_has(label_part):
    at, measured = _generate(label_part, 110)
    assert at.session_state["heart_rate"] == pytest.approx(measured, abs=4), (label_part, measured)


# --- Un solo número por concepto: nadie más escribe su propia FC de taqui/bradicardia sinusal en ECG-12 -----

def test_the_twelve_lead_example_helper_uses_the_canonical_rates():
    assert _measured_hr(generate_12lead_example(condition="tachycardia")["II"], fs=250) == pytest.approx(120.0, abs=3)
    assert _measured_hr(generate_12lead_example(condition="bradycardia")["II"], fs=250) == pytest.approx(49.5, abs=3)


def test_no_own_tachy_brady_literals_left_in_the_ecg12_package():
    gen = Path("src/signals/ecg/twelve_lead_generator.py").read_text(encoding="utf-8")
    page = Path("app/supermodules/ecg_12/page_content.py").read_text(encoding="utf-8")
    assert "heart_rate = 110" not in gen and "heart_rate = 45" not in gen
    assert "get_type" in gen and "stachy" in page


# --- UPS: la taquicardia sinusal respeta los umbrales, sin hueco nuevo ni disparo falso -------------------

def test_ups_rate_event_follows_the_declared_thresholds_for_sinus_tachycardia():
    from app.engines.digital_twin_organism import DigitalTwinOrganism
    from domain.physiology.state import EventType, Provenance, from_digital_twin_organism

    def fires(hr):
        organism = DigitalTwinOrganism()
        organism.update_from_sensors({"ecg": {"heart_rate": hr}})
        state = from_digital_twin_organism(organism, "p", Provenance.SIMULACION)
        return any(e.event_type == EventType.PULSE_NEWS2_3_POINTS for e in state.events)

    t = get_type("stachy")
    assert not fires(t.hr_min_bpm) and not fires(t.nominal_hr_bpm) and not fires(130.0), "100-130 lpm: el UPS marca solo >= 131 (3 puntos NEWS2)"
    assert fires(t.hr_max_bpm) and fires(131.0)
    assert t.ups_hr_event == "segun_fc"
    assert not fires(get_type("sbrady").hr_max_bpm), "hueco declarado: bradicardia 41-59 sin evento (solo <= 40 son 3 puntos)"
