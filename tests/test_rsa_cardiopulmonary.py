"""
Cardiovascular profundo, sub-arco RSA (2026-10-19): acoplamiento
cardiopulmonar. Generador respiración -> FC -> ECG, picos R por el TKEO
consolidado, detector de RSA sobre los RR reales. Ground truth por
construcción; degradación honesta; el HRV Lab deja de etiquetar ruido blanco
como "ECG-derived".
"""

import re
import subprocess
from pathlib import Path

import numpy as np
import pytest
from streamlit.testing.v1 import AppTest

from clinical.ecg_analyzer import ECGAnalyzer
from src.signals.ecg.rsa import (
    HF_BAND_HZ,
    MIN_RSA_DURATION_S,
    RSA_SCOPE_NOTE,
    RsaParams,
    band_power,
    detect_rsa,
    generate_rsa_signals,
    rr_spectrum,
)

_FS = 250.0


def _chain(params: RsaParams, duration_s: float = 120.0):
    signals = generate_rsa_signals(params, duration_s, fs=_FS)
    peaks_s = ECGAnalyzer(fs=_FS).detect_r_peaks_tkeo(signals.ecg) / _FS
    return signals, peaks_s, detect_rsa(peaks_s, signals.respiration, _FS)


def _beat_sampled_amplitude(params: RsaParams, peaks_s: np.ndarray) -> float:
    """Ground truth de lo que una serie RR PUEDE contener: la FC promediada en
    cada latido de una modulación sinusoidal A vale A·sinc(f_resp·RR medio)."""
    return params.rsa_amplitude_bpm * float(np.sinc(params.respiratory_freq_hz * np.mean(np.diff(peaks_s))))


# --- Recuperación de la RSA conocida -----------------------------------------

@pytest.mark.parametrize("hr, amplitude, rpm", [
    (60, 5, 12), (72, 3, 15), (72, 5, 15), (72, 10, 18), (85, 8, 10), (100, 5, 20), (100, 10, 24),
])
def test_recovers_injected_rsa(hr, amplitude, rpm):
    """Calibrado sobre 136 combinaciones (FC 50-130, A 3-10 lpm, 9-24 rpm,
    >=3.5 latidos por respiración): error de amplitud <=4.2% frente a
    A·sinc, |fase| <=4.3°, frecuencia respiratoria exacta. Tolerancias ~2x."""
    params = RsaParams(hr, amplitude, rpm)
    _, peaks_s, result = _chain(params)
    assert result.available, result.reason
    expected = _beat_sampled_amplitude(params, peaks_s)
    assert abs(result.rsa_amplitude_bpm / expected - 1) < 0.08, (result.rsa_amplitude_bpm, expected)
    assert abs(result.respiratory_freq_hz - params.respiratory_freq_hz) < 0.01
    assert abs(result.phase_deg) < 10.0, "la FC sube en inspiración: en fase con el volumen pulmonar"


def test_amplitude_scales_with_the_injected_rsa_not_a_constant():
    low = _chain(RsaParams(72, 3, 15))[2].rsa_amplitude_bpm
    high = _chain(RsaParams(72, 9, 15))[2].rsa_amplitude_bpm
    assert 2.7 < high / low < 3.3


def test_hf_power_matches_the_rr_oscillation():
    """La potencia HF de la serie RR es la de su oscilación: A_RR²/2, con
    A_RR ≈ 60000·A/FC² (ms) para una RSA pequeña."""
    params = RsaParams(72, 5, 15)
    _, peaks_s, result = _chain(params)
    a_rr_ms = 60000.0 * _beat_sampled_amplitude(params, peaks_s) / 72.0 ** 2
    assert abs(result.hf_power_ms2 / (a_rr_ms ** 2 / 2) - 1) < 0.15


# --- Los RR tienen estructura, no son ruido ----------------------------------

def test_rr_series_has_power_concentrated_at_the_respiratory_frequency():
    _, peaks_s, result = _chain(RsaParams(72, 5, 15))
    assert result.hf_peak_fraction > 0.95

    # El antiguo "Demo (ECG-derived)": mean_rr + N(0, 3%) -- espectro plano.
    rng = np.random.default_rng(0)
    white = 833.0 + rng.normal(0, 25.0, len(peaks_s) - 1)
    f, p = rr_spectrum(white)
    white_fraction = band_power(f, p, (0.21, 0.29)) / band_power(f, p, (0.04, 2.0))
    assert white_fraction < 0.2, white_fraction


def test_without_rsa_the_ecg_is_a_metronome():
    _, peaks_s, result = _chain(RsaParams(72, 0, 15))
    assert np.ptp(np.diff(peaks_s)) <= 2.0 / _FS + 1e-9, "sin RSA, RR constante salvo cuantización"
    assert result.rsa_amplitude_bpm < 0.2


# --- Degradación honesta -----------------------------------------------------

def test_declines_without_respiration():
    _, peaks_s, _ = _chain(RsaParams())
    for resp in (None, np.zeros(1000), np.array([1.0])):
        r = detect_rsa(peaks_s, resp, _FS)
        assert not r.available and r.rsa_amplitude_bpm is None
        assert "sin señal respiratoria" in r.reason


def test_declines_with_too_few_beats_or_too_short():
    signals, peaks_s, _ = _chain(RsaParams(), duration_s=40.0)
    r = detect_rsa(peaks_s, signals.respiration, _FS)
    assert not r.available and f"{MIN_RSA_DURATION_S:.0f}s" in r.reason
    r = detect_rsa(peaks_s[:2], signals.respiration, _FS)
    assert not r.available and "2 latidos" in r.reason


def test_declines_when_breathing_is_outside_the_hf_band():
    r = _chain(RsaParams(72, 5, 6))[2]
    assert not r.available and "fuera de la banda HF" in r.reason
    assert r.respiratory_freq_hz < HF_BAND_HZ[0]


def test_declines_with_too_few_beats_per_breath():
    """50 lpm a 20 rpm = 2.5 latidos por respiración: medido, la amplitud
    caería ~-20 a -37% -- declina en vez de reportarla."""
    r = _chain(RsaParams(50, 5, 20))[2]
    assert not r.available and "latidos por ciclo respiratorio" in r.reason


def test_params_reject_invalid_values():
    for bad in (dict(hr_base_bpm=20), dict(rsa_amplitude_bpm=-1), dict(hr_base_bpm=40, rsa_amplitude_bpm=25),
                dict(respiratory_rate_rpm=0)):
        with pytest.raises(ValueError):
            RsaParams(**bad)


# --- HRV Lab: la fuente dice la verdad, el panel se ve ------------------------

def _run_hrv(source=None):
    def _script():
        import app.main as m
        m.render_hrv_page()

    at = AppTest.from_function(_script)
    at.run(timeout=60)
    if source is not None:
        at.sidebar.radio[0].set_value(source)
        at.run(timeout=60)
    return at


def test_hrv_lab_source_no_longer_claims_ecg_derived_over_white_noise():
    src = Path("app/main.py").read_text(encoding="utf-8")
    assert "'Demo (ECG-derived)'" not in src, "la etiqueta ya no se usa como opción de la fuente"
    assert "np.random.normal(0, mean_rr * 0.03" not in src
    at = _run_hrv()
    assert at.exception == [], at.exception
    options = at.sidebar.radio[0].options
    assert any("ECG con RSA" in o and "TKEO" in o for o in options)
    assert "picos R detectados por TKEO" in " ".join(c.value for c in at.caption)


def test_hrv_lab_shows_rsa_panel_with_curve_and_measured_amplitude():
    at = _run_hrv()
    md = " ".join(m.value for m in at.markdown)
    assert "Acoplamiento cardiopulmonar (RSA)" in md
    amp = re.search(r"Amplitud de la RSA</strong>: (\d+\.\d+) lpm", md)
    assert amp and 4.0 < float(amp.group(1)) < 5.5, "default: 5 lpm inyectados a 72 lpm y 15 rpm"
    assert RSA_SCOPE_NOTE in " ".join(w.value for w in at.warning)
    specs = [c.proto.spec for c in at.get("plotly_chart")]
    assert any("FC latido a latido" in s for s in specs), "curva de FC sobre el volumen pulmonar"


def test_hrv_lab_rsa_amplitude_follows_the_slider():
    at = _run_hrv()
    next(s for s in at.sidebar.slider if s.label == "Amplitud RSA (lpm)").set_value(12)
    at.run(timeout=60)
    md = " ".join(m.value for m in at.markdown)
    assert float(re.search(r"Amplitud de la RSA</strong>: (\d+\.\d+) lpm", md).group(1)) > 10.0


def test_hrv_lab_manual_rr_declines_rsa_without_respiration():
    at = _run_hrv("Manual RR series")
    assert at.exception == []
    assert "RSA no disponible: sin señal respiratoria" in " ".join(i.value for i in at.info)
    assert not any("FC latido a latido" in c.proto.spec for c in at.get("plotly_chart"))


def test_hrv_lab_spectrum_is_computed_again():
    """Antes `np.trapz` (ausente en numpy 2.x) hacía fallar siempre el
    espectro y el mensaje culpaba a scipy."""
    at = _run_hrv()
    assert "No se pudo calcular" not in " ".join(i.value for i in at.info)
    assert re.search(r"LF: \d+\.\d+ — HF: \d+\.\d+", " ".join(m.value for m in at.markdown))


# --- No cruza labs por el UPS; motor intacto ----------------------------------

def test_rsa_never_reads_other_labs_through_the_ups():
    for path in ("src/signals/ecg/rsa.py", "app/supermodules/rsa_panel.py"):
        src = Path(path).read_text(encoding="utf-8")
        code = "\n".join(line for line in src.splitlines() if not line.lstrip().startswith("#"))
        imports = "\n".join(line for line in code.splitlines() if line.lstrip().startswith(("import", "from")))
        for forbidden in ("domain.physiology", "respiratory_lab", "get_latest_state", "session_factory"):
            assert forbidden not in imports, f"{path} importa {forbidden}"


def test_hemodynamic_engine_untouched():
    try:
        out = subprocess.run(
            ["git", "diff", "--stat", "HEAD", "--", "domain/physiology/hemodynamics/"],
            capture_output=True, text=True, check=True,
        ).stdout
    except (FileNotFoundError, subprocess.CalledProcessError):
        pytest.skip("git no disponible")
    assert out.strip() == ""
