"""
HRV no lineal (2026-10-31): SampEn, DFA alfa1 y Poincare (SD1/SD2) validados contra señales de propiedades
conocidas, degradación honesta, alfa2 declarado fuera, contraste serie real vs. ruido en el HRV Lab. Las
tolerancias salen de las mediciones del docstring de `hrv_nonlinear.py` (ruido blanco da alfa1 0.58, no 0.50).
"""

import re
from pathlib import Path

import numpy as np
import pytest
from streamlit.testing.v1 import AppTest

from clinical.ecg_analyzer import ECGAnalyzer
from src.signals.ecg import hrv_nonlinear as hn
from src.signals.ecg.hrv_nonlinear import (
    ALPHA2_NOTE, MIN_BEATS_NONLINEAR, MIN_BEATS_POINCARE, analyze_hrv_nonlinear, dfa_alpha1, poincare,
    sample_entropy, structure_note,
)
from src.signals.ecg.rsa import RsaParams, generate_rsa_signals


def _noise(n, beta, seed):
    """Ruido 1/f^beta de varianza unidad (síntesis espectral): beta=0 blanco (alfa teórico 0.5), 1 -> 1.0,
    2 (browniano) -> 1.5."""
    rng = np.random.default_rng(seed)
    f = np.fft.rfftfreq(n)
    f[0] = f[1]
    spec = (rng.normal(size=f.size) + 1j * rng.normal(size=f.size)) * f ** (-beta / 2)
    spec[0] = 0
    x = np.fft.irfft(spec, n)
    return x / x.std()


def _rr(x, mean=833.0, sd=40.0):
    return mean + sd * x


def _mean_over_seeds(fn, n, beta, seeds=range(20)):
    return float(np.mean([fn(_rr(_noise(n, beta, s))).value for s in seeds]))


# --- Ground truth: SampEn ------------------------------------------------------

def test_sampen_of_white_noise_matches_the_analytic_value():
    """Gaussiano iid, m=2, r=0.2·SD: A/B = P(|x-y|<=r) = erf(0.1) -> SampEn = 2.185."""
    from math import erf, log
    expected = -log(erf(0.1))
    assert _mean_over_seeds(sample_entropy, 400, 0) == pytest.approx(expected, abs=0.1)


def test_sampen_matches_a_naive_reference_implementation():
    x = _rr(_noise(220, 1, 3))
    m, r, n = 2, 0.2 * x.std(), x.size
    b = a = 0
    for i in range(n - m):
        for j in range(i + 1, n - m):
            if max(abs(x[i + k] - x[j + k]) for k in range(m)) <= r:
                b += 1
                if abs(x[i + m] - x[j + m]) <= r:
                    a += 1
    assert sample_entropy(x).value == pytest.approx(np.log(b / a), abs=1e-12)


def test_sampen_orders_regular_below_correlated_below_white():
    sinus = _rr(np.sin(2 * np.pi * np.arange(300) / 5.0))
    values = [sample_entropy(sinus).value, _mean_over_seeds(sample_entropy, 300, 1), _mean_over_seeds(sample_entropy, 300, 0)]
    assert values[0] < 0.2 < values[1] < values[2]


# --- Ground truth: DFA alfa1 ---------------------------------------------------

@pytest.mark.parametrize("beta, expected, tol", [(0, 0.58, 0.07), (1, 1.0, 0.08), (2, 1.5, 0.15)])
def test_dfa_alpha1_recovers_the_known_exponent(beta, expected, tol):
    """beta=0 -> 0.58 = 0.5 teórico más el sesgo medido de las escalas 4-16 (ver docstring del módulo)."""
    assert _mean_over_seeds(dfa_alpha1, 300, beta) == pytest.approx(expected, abs=tol)


def test_dfa_alpha1_separates_white_from_one_over_f_by_about_half():
    gap = _mean_over_seeds(dfa_alpha1, 300, 1) - _mean_over_seeds(dfa_alpha1, 300, 0)
    assert 0.3 < gap < 0.55


def test_dfa_alpha1_ignores_level_and_scale_of_the_series():
    x = _noise(250, 1, 7)
    assert dfa_alpha1(_rr(x, 600, 20)).value == pytest.approx(dfa_alpha1(_rr(x, 1100, 90)).value, abs=1e-9)


# --- Ground truth: Poincare ----------------------------------------------------

def test_poincare_sd1_is_rmssd_over_sqrt2_and_sd2_follows_sdnn():
    for beta, seed in [(0, 1), (1, 2), (2, 3)]:
        rr = _rr(_noise(300, beta, seed))
        p = poincare(rr)
        rmssd = np.sqrt(np.mean(np.diff(rr) ** 2))
        sdnn = np.std(rr, ddof=1)
        assert p.sd1_ms == pytest.approx(rmssd / np.sqrt(2), rel=0.01)
        assert p.sd2_ms ** 2 == pytest.approx(2 * sdnn ** 2 - p.sd1_ms ** 2, rel=0.02)
        assert p.ratio == pytest.approx(p.sd1_ms / p.sd2_ms)


def test_poincare_white_noise_has_circular_cloud_and_correlated_noise_is_elongated():
    assert poincare(_rr(_noise(400, 0, 1))).ratio == pytest.approx(1.0, abs=0.15)
    assert poincare(_rr(_noise(400, 2, 1))).ratio < 0.3


# --- Degradación honesta -------------------------------------------------------

@pytest.mark.parametrize("fn", [sample_entropy, dfa_alpha1])
def test_nonlinear_metrics_decline_below_the_measured_minimum(fn):
    short = fn(_rr(_noise(MIN_BEATS_NONLINEAR - 1, 0, 1)))
    assert not short.available and short.value is None
    assert f"se requieren ≥{MIN_BEATS_NONLINEAR} latidos; hay {MIN_BEATS_NONLINEAR - 1}" in short.reason
    assert fn(_rr(_noise(MIN_BEATS_NONLINEAR, 0, 1))).available


def test_poincare_declines_below_its_own_smaller_minimum():
    short = poincare(_rr(_noise(MIN_BEATS_POINCARE - 1, 0, 1)))
    assert not short.available and short.sd1_ms is None and "≥50 latidos" in short.reason
    assert poincare(_rr(_noise(MIN_BEATS_POINCARE, 0, 1))).available
    assert MIN_BEATS_POINCARE < MIN_BEATS_NONLINEAR


def test_invalid_or_flat_series_decline_instead_of_returning_a_number():
    bad = _rr(_noise(250, 0, 1))
    bad[10] = np.nan
    neg = _rr(_noise(250, 0, 1))
    neg[5] = -1.0
    for series in (bad, neg):
        for fn in (sample_entropy, dfa_alpha1, poincare):
            r = fn(series)
            assert not r.available and "no válidos" in r.reason
    flat = np.full(250, 833.0) + np.random.default_rng(0).choice([-2.0, 2.0], 250)
    for fn in (sample_entropy, dfa_alpha1):
        r = fn(flat)
        assert not r.available and "cuantización" in r.reason


def test_sampen_declines_when_there_are_no_template_matches(monkeypatch):
    """Con >=200 latidos r = 0.2·SD siempre da vecinos, así que la guarda se prueba bajando el mínimo."""
    monkeypatch.setattr(hn, "MIN_BEATS_NONLINEAR", 5)
    r = sample_entropy([800.0, 1500.0, 100.0, 2000.0, 300.0, 1700.0, 50.0])
    assert not r.available and "sin coincidencias" in r.reason


def test_alpha2_is_declared_out_and_never_computed():
    result = analyze_hrv_nonlinear(_rr(_noise(300, 1, 1)))
    assert result.alpha2_note == ALPHA2_NOTE and ">1000 latidos" in ALPHA2_NOTE
    assert not [name for name in dir(hn) if "alpha2" in name.lower() and callable(getattr(hn, name))]
    assert not hasattr(result, "alpha2")


# --- Contraste serie con estructura vs. ruido ----------------------------------

def _rsa_rr(params, duration_s=240.0):
    signals = generate_rsa_signals(params, duration_s, fs=250.0)
    return np.diff(ECGAnalyzer(fs=250.0).detect_r_peaks_tkeo(signals.ecg) / 250.0) * 1000.0


def test_rsa_series_is_quasi_periodic_and_its_shuffle_is_noise():
    """El generador RSA es una sinusoide: SampEn ≈ 0 y alfa1 baja (NO el 1.0 de un corazón real, que el
    generador no reproduce). Barajarla conserva los valores y destruye el orden: queda ruido."""
    rr = _rsa_rr(RsaParams(72, 5, 15))
    shuffled = np.random.default_rng(0).permutation(rr)
    real, noise = analyze_hrv_nonlinear(rr), analyze_hrv_nonlinear(shuffled)
    assert real.sampen.value < 0.2 and noise.sampen.value > 1.9
    assert real.alpha1.value < 0.4 and 0.45 < noise.alpha1.value < 0.7
    assert "casi periódica" in real.structure_note
    assert "ruido" in noise.structure_note
    # mismos valores -> Poincare idéntico en dispersión total, distinto en la forma
    assert real.poincare.ratio < noise.poincare.ratio


def test_noise_label_fires_on_white_noise_and_never_on_one_over_f():
    seeds = range(30)
    white = [structure_note(sample_entropy(_rr(_noise(300, 0, s))), dfa_alpha1(_rr(_noise(300, 0, s)))) for s in seeds]
    pink = [structure_note(sample_entropy(_rr(_noise(300, 1, s))), dfa_alpha1(_rr(_noise(300, 1, s)))) for s in seeds]
    assert sum(n is not None and "ruido" in n for n in white) >= 0.85 * len(white)
    assert not any(n is not None and "ruido" in n for n in pink)


def test_no_label_when_a_metric_is_unavailable():
    assert analyze_hrv_nonlinear(_rr(_noise(100, 0, 1))).structure_note is None


# --- El viejo advanced_hrv no se reusa ------------------------------------------

def test_new_module_has_no_filler_values_and_does_not_reuse_advanced_hrv():
    for path in ("src/signals/ecg/hrv_nonlinear.py", "app/supermodules/hrv_nonlinear_panel.py"):
        src = Path(path).read_text(encoding="utf-8")
        code = "\n".join(line for line in src.splitlines() if not line.lstrip().startswith("#"))
        assert "return 1.0" not in code and "advanced_hrv" not in code.replace("`src/advanced_hrv.py`", "")


# --- HRV Lab ------------------------------------------------------------------

def _run_hrv(source=None, duration=None):
    def _script():
        import app.main as m
        m.render_hrv_page()

    at = AppTest.from_function(_script)
    at.run(timeout=90)
    if source is not None:
        at.sidebar.radio[0].set_value(source)
        at.run(timeout=90)
    if duration is not None:
        next(s for s in at.sidebar.slider if s.label == "Duración (seg)").set_value(duration)
        at.run(timeout=90)
    return at


def test_hrv_lab_shows_the_three_metrics_and_the_real_vs_noise_contrast():
    at = _run_hrv()
    assert at.exception == [], at.exception
    md = " ".join(m.value for m in at.markdown)
    assert "HRV no lineal" in md
    for label in ("SampEn", "DFA α1", "SD1", "SD2"):
        assert re.search(rf"<strong>{label}[^<]*</strong>: ", md), label
    assert "casi periódica" in md and "sin estructura autonómica" in md
    assert "alfa2" in md and ">1000 latidos" in md
    assert "PENDING_VALIDATION" in " ".join(i.value for i in at.info)
    assert any("Poincar" in c.proto.spec for c in at.get("plotly_chart"))


def test_hrv_lab_declines_visibly_when_the_recording_is_too_short():
    at = _run_hrv(duration=60)
    assert at.exception == []
    md = " ".join(m.value for m in at.markdown)
    assert re.search(r"se requieren ≥200 latidos; hay \d+", md)
    assert not re.search(r"<strong>SampEn[^<]*</strong>: \d", md)


def test_hrv_lab_manual_series_declines_with_reason():
    at = _run_hrv("Manual RR series")
    assert at.exception == []
    assert "se requieren ≥50 latidos; hay 5" in " ".join(m.value for m in at.markdown)
