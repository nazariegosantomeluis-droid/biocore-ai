"""
Capa 5A dominio muscular, Tanda 1 (lado señal) -- el EmgAnalyzer consolidado.

Reemplaza a `test_emg_preprocessing.py`: cubre `preprocess_emg` (el real, no
el stub no-op que se mató en `app/main.py`) + el `EmgAnalyzer` extraído a
`src/signals/emg/`. Verifica que activación y MDF corren sobre señal
FILTRADA, que el corrimiento de MDF con la fatiga sigue funcionando tras la
consolidación, y que `fatigue_index` sigue clavado en ~0 sobre el generador
demo (deuda del generador, diferida).
"""

import numpy as np
import pytest

from src.signals.emg import (
    EmgAnalysis,
    EmgAnalyzer,
    fatigue_index_from_mdf,
    median_frequency,
    preprocess_emg,
)


# --- preprocess_emg (el real: butter 20-450 Hz) -------------------------------

def test_preprocess_emg_returns_filtered_and_metrics():
    fs = 1000.0
    t = np.arange(0, 1.0, 1.0 / fs)
    signal = 0.8 * np.random.randn(len(t)) * (0.5 + 0.5 * np.sin(2 * np.pi * 2 * t))
    filtered, metrics = preprocess_emg(signal, fs)
    assert isinstance(filtered, np.ndarray) and filtered.shape == signal.shape
    assert metrics["fs"] == fs
    assert "mean_rectified" in metrics and "signal_std" in metrics


def test_preprocess_emg_actually_filters_out_of_band_energy():
    """Un tono de 5 Hz (por debajo del corte de 20 Hz) debe quedar muy
    atenuado -- prueba de que el bandpass corre, no es un passthrough."""
    fs = 1000.0
    t = np.arange(0, 2.0, 1.0 / fs)
    low_tone = np.sin(2 * np.pi * 5.0 * t)          # 5 Hz, fuera de banda
    in_band = 0.2 * np.sin(2 * np.pi * 120.0 * t)   # 120 Hz, en banda
    raw = low_tone + in_band
    filtered, _ = preprocess_emg(raw, fs)
    assert np.std(filtered) < 0.5 * np.std(raw)     # el 5 Hz dominante se fue


# --- median_frequency / fatigue_index_from_mdf (fórmulas intactas) -----------

def test_fatigue_index_formula_unchanged():
    # (120 - mdf) / 60 * 100, clip 0-100
    assert fatigue_index_from_mdf(120.0) == pytest.approx(0.0)
    assert fatigue_index_from_mdf(90.0) == pytest.approx(50.0)
    assert fatigue_index_from_mdf(60.0) == pytest.approx(100.0)
    assert fatigue_index_from_mdf(20.0) == pytest.approx(100.0)   # clip
    assert fatigue_index_from_mdf(200.0) == pytest.approx(0.0)    # clip


def _bandnoise(lo, hi, fs, n, seed):
    from scipy.signal import butter, filtfilt
    rng = np.random.default_rng(seed)
    x = rng.standard_normal(n)
    b, a = butter(4, [lo / (fs / 2), hi / (fs / 2)], btype="band")
    return filtfilt(b, a, x)


def test_mdf_shift_with_fatigue_survives_consolidation():
    """Señal band-limited realista: 'fresca' con potencia en 60-150 Hz,
    'fatigada' desplazada a 30-90 Hz. La MDF debe caer y el índice subir --
    exactamente lo que midió el diagnóstico (~101 Hz -> ~60 Hz)."""
    fs = 1000.0
    n = int(fs * 10)
    fresh = _bandnoise(60, 150, fs, n, seed=1)
    fatigued = _bandnoise(30, 90, fs, n, seed=2)

    mdf_fresh = median_frequency(fresh, fs)
    mdf_fat = median_frequency(fatigued, fs)
    assert 80.0 < mdf_fresh < 125.0
    assert 45.0 < mdf_fat < 80.0
    assert mdf_fat < mdf_fresh - 20.0
    assert fatigue_index_from_mdf(mdf_fat) > fatigue_index_from_mdf(mdf_fresh) + 20.0


# --- EmgAnalyzer: contrato tipo EegAnalyzer ---------------------------------

def test_emg_analyzer_returns_analysis_with_units():
    fs = 1000.0
    sig = _bandnoise(60, 150, fs, int(fs * 8), seed=3)
    result = EmgAnalyzer(fs).analyze(sig)
    assert isinstance(result, EmgAnalysis)
    assert 0.0 <= result.activation_pct <= 100.0
    assert 0.0 <= result.median_frequency_hz <= fs / 2
    assert 0.0 <= result.fatigue_index <= 100.0
    assert set(result.findings) == {
        "Activación muscular", "Frecuencia mediana (MDF)", "Índice de fatiga"
    }


def test_emg_analyzer_computes_on_FILTERED_signal_not_raw():
    """La prueba central de la Tanda 1: la activación del analizador (sobre
    señal filtrada) DIFIERE de la activación sobre señal cruda. No importa el
    número exacto -- importa que el bandpass tiene efecto medible."""
    fs = 1000.0
    t = np.arange(0, 3.0, 1.0 / fs)
    rng = np.random.default_rng(4)
    # EMG-like en banda + fuerte deriva de baja frecuencia (artefacto de
    # movimiento) que el bandpass debe quitar.
    raw = 0.6 * rng.standard_normal(len(t)) + 1.5 * np.sin(2 * np.pi * 3.0 * t)

    raw_activation = float(np.clip(
        np.mean(np.abs(raw)) / (np.max(np.abs(raw)) + 1e-9) * 100.0, 0.0, 100.0
    ))
    filtered_activation = EmgAnalyzer(fs).analyze(raw).activation_pct

    assert abs(filtered_activation - raw_activation) > 1.0   # el filtro cambió el resultado

    # y la MDF cruda (sesgada por el artefacto de 3 Hz) es más baja que la filtrada
    from src.signals.emg import median_frequency as mdf
    assert mdf(raw, fs) < EmgAnalyzer(fs).analyze(raw).median_frequency_hz


def test_fatigue_index_still_pinned_at_zero_on_demo_generator():
    """El generador demo produce ruido blanco (espectro plano) -> MDF ~fs/4,
    muy por encima del basal de 120 Hz -> fatigue_index clavado en 0 en los
    3 patrones. Deuda del GENERADOR, no de la fórmula. NO se arregla aquí; se
    difiere (no se persistirá al UPS en la Tanda 2)."""
    from app.main import generate_demo_emg_signal
    fs = 1000.0
    for pattern in ("Isométrica", "Rápida", "Fatiga"):
        sig = generate_demo_emg_signal(fs, 15.0, pattern)
        result = EmgAnalyzer(fs).analyze(sig)
        assert result.fatigue_index == pytest.approx(0.0), pattern
        assert result.median_frequency_hz > 150.0, pattern   # muy por encima del basal
