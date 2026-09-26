"""
Bug 2 del ECG (2026-09-26, ver CHANGELOG.md) -- consolidación del detector
de HR de `render_ecg_monitor_page()` sobre `ECGAnalyzer.detect_r_peaks_tkeo()`
(TKEO), retirando `estimate_ecg_heart_rate()` (naive, sin distancia mínima
entre picos, contaba el par R+T del mismo latido como dos latidos
separados, saturaba en 220bpm). El diagnóstico de re-verificación (Bugs 1+3
del generador, ya cerrados en Fase 5B) confirmó por ejecución que Bug 2
persistía incluso contra un generador ya corregido, y que afectaba TODAS
las fuentes de la página -- no solo la demo, también MIT-BIH/PTB-XL/CSV/
hardware (señal REAL).

Banco de regresión: el mismo barrido `DynamicECGGenerator(hr conocido)` que
ya validó el generador en Fase 5B sirve, sin modificar, para anclar que el
detector consolidado sigue recuperando el HR real -- si alguien reintroduce
un detector sin distancia mínima, este test lo atrapa.
"""

import numpy as np
import pytest
from streamlit.testing.v1 import AppTest

from src.signals.ecg.dynamic_ecg_generator import DynamicECGGenerator
from clinical.ecg_analyzer import ECGAnalyzer
from app.main import _measure_ecg_heart_rate_tkeo


# --- Parte C: el banco de regresión, formalizado -----------------------

@pytest.mark.parametrize("true_hr", [40, 60, 100, 120, 150, 180, 200])
def test_consolidated_detector_recovers_known_hr_within_half_bpm(true_hr):
    """El mismo barrido que el diagnóstico corrió en vivo (0.00-0.12bpm de
    error medido) -- margen holgado a <0.5bpm para no acoplar el test a la
    cuarta cifra decimal, solo a que el detector siga siendo el correcto."""
    gen = DynamicECGGenerator(fs=250.0)
    signal = gen.generate(duration=20, hr=true_hr)
    measured = _measure_ecg_heart_rate_tkeo(signal, 250.0, ECGAnalyzer)
    assert measured is not None
    assert abs(measured - true_hr) < 0.5, f"hr={true_hr}: medido {measured}, error > 0.5bpm"


def test_naive_detector_saturation_no_longer_reachable():
    """El caso concreto que el diagnóstico midió como roto (hr real=100 ->
    201bpm con el naive, por contar R+T como dos latidos) -- confirmado
    que el detector consolidado NO reproduce ese error."""
    gen = DynamicECGGenerator(fs=250.0)
    signal = gen.generate(duration=20, hr=100)
    measured = _measure_ecg_heart_rate_tkeo(signal, 250.0, ECGAnalyzer)
    assert measured is not None
    assert 95 < measured < 105, f"esperado ~100bpm, medido {measured} -- ¿volvió el doble conteo R+T?"


def test_measurement_declines_honestly_without_ecg_analyzer():
    """Sin ECGAnalyzer disponible, `None` -- nunca un 0.0 ni un 220 de
    relleno."""
    gen = DynamicECGGenerator(fs=250.0)
    signal = gen.generate(duration=20, hr=80)
    assert _measure_ecg_heart_rate_tkeo(signal, 250.0, None) is None


def test_measurement_declines_honestly_on_unmeasurable_signal():
    """Señal sin picos R reconocibles (ruido plano) -- `None`, no un
    número inventado."""
    flat = np.zeros(250 * 20)
    assert _measure_ecg_heart_rate_tkeo(flat, 250.0, ECGAnalyzer) is None


# --- Parte A: el naive retirado, cero llamadores vivos -------------------

def test_naive_detector_removed_from_app_utils_and_supermodules():
    import app.utils as app_utils
    import app.supermodules as supermodules

    assert not hasattr(app_utils, "estimate_ecg_heart_rate")
    assert not hasattr(supermodules, "estimate_ecg_heart_rate")
    assert "estimate_ecg_heart_rate" not in supermodules.__all__


def test_naive_detector_has_zero_live_callers_in_source():
    """Grep de todos los llamadores vivos, como se hizo antes de retirar
    los gemelos muertos del EEG -- confirma que ninguna línea de código
    invoca la función. Las menciones que sobreviven son prosa explicativa
    (comentarios y docstrings) citando el nombre entre backticks -- se
    excluyen con el mismo patrón anti-falso-positivo ya usado en tandas
    anteriores (una mención documental no es una llamada)."""
    import re

    live_files = [
        "app/main.py",
        "app/utils.py",
        "app/supermodules/__init__.py",
    ]
    call_pattern = re.compile(r"(?<!`)\bestimate_ecg_heart_rate\s*\(")
    for path in live_files:
        src = open(path, encoding="utf-8").read()
        for line in src.splitlines():
            if line.strip().startswith("#"):
                continue
            assert not call_pattern.search(line), (
                f"{path} todavía LLAMA a estimate_ecg_heart_rate(): {line!r}"
            )


# --- Parte B: las fuentes de ECG Monitor, demo Y reales, sobre TKEO -----

def test_ecg_monitor_demo_source_shows_measured_hr_not_saturated():
    def _script():
        import app.main as m
        m.render_ecg_monitor_page()

    at = AppTest.from_function(_script)
    at.run(timeout=30)
    assert at.exception == []
    slider = next(s for s in at.sidebar.slider if s.label == "Demo HR (bpm)")
    slider.set_value(130)
    at.run(timeout=30)
    assert at.exception == []
    metrics_text = " ".join(md.value for md in at.main.markdown)
    assert "**Heart Rate**" in metrics_text
    assert "220" not in metrics_text, "el 220 fijo no debe reaparecer"


def test_ecg_monitor_real_source_mitbih_shows_correct_hr_not_220():
    """La parte que más importa de esta tanda: una fuente de señal REAL
    (simulada aquí vía inyección de la misma caché de sesión que usa el
    código de producción tras una descarga real de MIT-BIH -- sin red,
    mismo camino de código exacto que un registro real recorrería) debe
    mostrar el HR correcto, no el 220 de relleno del detector roto."""
    gen = DynamicECGGenerator(fs=250.0)
    known_hr = 115.0
    real_like_signal = gen.generate(duration=20, hr=known_hr)

    def _script():
        import app.main as m
        m.render_ecg_monitor_page()

    at = AppTest.from_function(_script)
    at.run(timeout=30)
    at.session_state["_ecg_monitor_mitbih_cache"] = (
        real_like_signal, 250.0, {"source": "MIT-BIH 100 (PhysioNet)"},
    )
    radio = next(r for r in at.sidebar.radio if r.label == "ECG Source")
    radio.set_value("Base de datos MIT-BIH")
    at.run(timeout=30)
    assert at.exception == []

    metrics_text = " ".join(md.value for md in at.main.markdown)
    assert "**Heart Rate**" in metrics_text
    assert "220" not in metrics_text, "el detector roto ya no debe medir señal real tampoco"
    assert f"{known_hr:.0f}" in metrics_text, "el HR mostrado debe ser el real medido, no un valor inventado"


def test_ecg_monitor_real_source_declines_honestly_when_unmeasurable():
    """Una fuente real sin señal analizable (aquí, ruido plano bajo el
    mismo camino de MIT-BIH) declara 'No disponible', nunca un número de
    relleno -- degradación honesta, el paliativo que la tanda prohibió."""
    flat_signal = np.zeros(250 * 20)

    def _script():
        import app.main as m
        m.render_ecg_monitor_page()

    at = AppTest.from_function(_script)
    at.run(timeout=30)
    at.session_state["_ecg_monitor_mitbih_cache"] = (
        flat_signal, 250.0, {"source": "MIT-BIH 999 (PhysioNet)"},
    )
    radio = next(r for r in at.sidebar.radio if r.label == "ECG Source")
    radio.set_value("Base de datos MIT-BIH")
    at.run(timeout=30)
    assert at.exception == []

    metrics_text = " ".join(md.value for md in at.main.markdown)
    assert "No disponible" in metrics_text
    assert "220" not in metrics_text


def test_ecg_monitor_ptbxl_source_also_consolidated_on_tkeo():
    """PTB-XL pasa por el mismo camino que MIT-BIH (misma rama `else`
    retirada) -- confirmado con su propia caché de sesión."""
    gen = DynamicECGGenerator(fs=500.0)
    known_hr = 88.0
    real_like_signal = gen.generate(duration=20, hr=known_hr)

    def _script():
        import app.main as m
        m.render_ecg_monitor_page()

    at = AppTest.from_function(_script)
    at.run(timeout=30)
    at.session_state["_ecg_monitor_ptbxl_cache"] = (
        real_like_signal, 500.0, {"source": "PTB-XL 00001 (NORM, PhysioNet)"},
    )
    radio = next(r for r in at.sidebar.radio if r.label == "ECG Source")
    radio.set_value("Base de datos PTB-XL")
    at.run(timeout=30)
    assert at.exception == []

    metrics_text = " ".join(md.value for md in at.main.markdown)
    assert "**Heart Rate**" in metrics_text
    assert "220" not in metrics_text
    assert f"{known_hr:.0f}" in metrics_text


# --- El BBB, confirmado ajeno a esta consolidación ------------------------

def test_bbb_detector_does_not_reference_the_hr_detectors_touched_here():
    """El BBB (`clinical/bbb_detector.py`) nunca dependió de
    `estimate_ecg_heart_rate` ni de `_measure_ecg_heart_rate_tkeo` -- lee
    morfología real vía `QrsDelineation`, no un HR de resumen. Confirma que
    esta consolidación no rozó su ruta."""
    src = open("clinical/bbb_detector.py", encoding="utf-8").read()
    assert "estimate_ecg_heart_rate" not in src
    assert "_measure_ecg_heart_rate_tkeo" not in src
    assert "DynamicECGGenerator" not in src
