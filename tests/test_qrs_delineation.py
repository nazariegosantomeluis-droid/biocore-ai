"""Verificación objetiva del delineador de QRS aislado (Detector BBB,
Sub-Fase 2.5) -- `clinical/qrs_delineation.py`.

Estos tests son de MEDICIÓN, no clínicos: el delineador o mide bien los
bordes del QRS contra baseline conocido, o no. No evalúan si algo "es"
LBBB/RBBB (eso es la Fase 3, todavía no autorizada).

Cada test contrasta explícitamente contra `ECGAnalyzer.segment_qrs_complex()`
(el método viejo, argmin en ventana fija) para demostrar el defecto medido
en la auditoría de Sub-Fase 2 -- no se asume el defecto, se reproduce.
"""

import numpy as np
import pytest
from scipy.signal import find_peaks

from clinical.ecg_analyzer import ECGAnalyzer
from clinical.qrs_delineation import delineate_qrs


def _gaussian(t: np.ndarray, center: float, sigma: float, amp: float) -> np.ndarray:
    return amp * np.exp(-((t - center) ** 2) / (2 * sigma ** 2))


def _hann_bump(fs: float, total_s: float, r_time_s: float, half_width_ms: float, amplitude: float = 1.0,
               noise_std: float = 0.005, seed: int = 42):
    """QRS sintético simple: un único lóbulo positivo, EXACTAMENTE cero en
    los bordes de [r_time - half_width, r_time + half_width] (ventana de
    Hann) y ruido pequeño (muy por debajo del umbral isoeléctrico) fuera de
    ella -- ground truth de ancho total = 2*half_width_ms sin ambigüedad."""
    n = int(total_s * fs)
    signal = np.zeros(n)
    r_idx = int(r_time_s * fs)
    half_w = int(half_width_ms / 1000.0 * fs)
    idx = np.arange(r_idx - half_w, r_idx + half_w)
    idx = idx[(idx >= 0) & (idx < n)]
    local_t = (idx - r_idx) / half_w
    signal[idx] = amplitude * (0.5 * (1 + np.cos(np.pi * local_t)))
    rng = np.random.default_rng(seed)
    return signal + rng.normal(0, noise_std, n), r_idx


def _triphasic_qs_deeper_s(fs: float, total_s: float, r_time_s: float, noise_std: float = 0.004, seed: int = 7):
    """QRS trifásico Q-R-S continuo (sin dip artificial entre lóbulos), con
    S más profunda que Q -- para demostrar que `argmin` (método viejo)
    confunde Q con S cuando S es la deflexión más negativa de toda la
    ventana."""
    n = int(total_s * fs)
    t = np.arange(n) / fs
    signal = np.zeros(n)
    signal += _gaussian(t, r_time_s - 0.025, 0.010, -0.30)  # Q, amplitud -0.30
    signal += _gaussian(t, r_time_s, 0.022, 1.0)  # R
    signal += _gaussian(t, r_time_s + 0.028, 0.016, -0.40)  # S, amplitud -0.40 (más profunda que Q)
    rng = np.random.default_rng(seed)
    return signal + rng.normal(0, noise_std, n), int(r_time_s * fs)


def _rsr_prime(fs: float, total_s: float, r_time_s: float, noise_std: float = 0.004, seed: int = 11):
    """QRS con patrón RSR' -- R, dip S, segunda deflexión positiva R' --
    tres deflexiones claramente separadas (>=45ms entre centros) para que
    cada una sea un extremo local genuino."""
    n = int(total_s * fs)
    t = np.arange(n) / fs
    signal = np.zeros(n)
    signal += _gaussian(t, r_time_s, 0.012, 0.8)  # R
    signal += _gaussian(t, r_time_s + 0.045, 0.012, -0.35)  # S
    signal += _gaussian(t, r_time_s + 0.090, 0.012, 0.55)  # R'
    rng = np.random.default_rng(seed)
    return signal + rng.normal(0, noise_std, n), int(r_time_s * fs)


def _wide_multicomponent_qrs(fs: float, total_s: float, r_time_s: float, noise_std: float = 0.004, seed: int = 3):
    """QRS ancho (~150-170ms), con Q, R, S y una R' pequeña -- morfología
    tipo bloqueo de rama SIN etiquetarla LBBB/RBBB (eso es Fase 3)."""
    n = int(total_s * fs)
    t = np.arange(n) / fs
    signal = np.zeros(n)
    signal += _gaussian(t, r_time_s - 0.02, 0.014, -0.15)
    signal += _gaussian(t, r_time_s, 0.028, 1.0)
    signal += _gaussian(t, r_time_s + 0.05, 0.018, -0.30)
    signal += _gaussian(t, r_time_s + 0.075, 0.014, 0.25)
    rng = np.random.default_rng(seed)
    return signal + rng.normal(0, noise_std, n), int(r_time_s * fs)


# --- 1. QRS de ancho conocido -- estrecho no se toca, ancho NO se amputa -----

def test_narrow_qrs_measured_close_to_true_width():
    fs = 500.0
    signal, r_idx = _hann_bump(fs, 2.0, 1.0, half_width_ms=45.0)  # ancho total real = 90ms
    result = delineate_qrs(signal, r_idx, fs)
    assert 60.0 <= result.qrs_duration_ms <= 100.0


def test_wide_qrs_not_amputated_by_fixed_120ms_window():
    """El fallo medido del método viejo: `segment_qrs_complex()` usa una
    ventana total de 120ms (igual al umbral clínico que la dispara) -- un
    QRS real de 150ms no puede medir más que eso ahí. El delineador nuevo
    usa ±120ms POR LADO (240ms total) y debe medir por encima de 120ms."""
    fs = 500.0
    signal, r_idx = _hann_bump(fs, 2.0, 1.0, half_width_ms=75.0)  # ancho total real = 150ms
    result = delineate_qrs(signal, r_idx, fs)
    assert result.qrs_duration_ms > 120.0, (
        f"qrs_duration_ms={result.qrs_duration_ms} no debería quedar acotado por "
        "el techo de 120ms del método viejo -- el delineador nuevo se amputó igual."
    )
    assert 122.0 <= result.qrs_duration_ms <= 170.0


def test_wide_multicomponent_qrs_vs_old_method_collapse():
    """Reproduce el defecto del método viejo con un QRS ancho realista
    (Q-R-S-R'): `segment_qrs_complex()` puede colapsar q_idx==s_idx (ambos
    caen en el mismo mínimo global de la ventana) -- una duración medida
    absurda. El delineador nuevo debe producir una duración fisiológicamente
    plausible y mayor que la del método viejo."""
    fs = 500.0
    signal, r_idx = _wide_multicomponent_qrs(fs, 2.0, 1.0)

    result = delineate_qrs(signal, r_idx, fs)

    analyzer = ECGAnalyzer(fs=fs)
    q_old, s_old = analyzer.segment_qrs_complex(signal, r_idx)
    old_duration_ms = (s_old - q_old) / fs * 1000.0

    assert 130.0 <= result.qrs_duration_ms <= 200.0
    assert result.qrs_duration_ms > old_duration_ms, (
        f"El delineador nuevo ({result.qrs_duration_ms}ms) debería medir más que "
        f"el método viejo ({old_duration_ms}ms) en un QRS ancho -- si no, no se "
        "corrigió la amputación."
    )


# --- 2. Onset/offset por baseline, no por argmin ------------------------------

def test_onset_offset_by_baseline_not_by_deepest_point():
    """El delineador nuevo debe ubicar onset/offset en los CRUCES de
    baseline (antes del trough de Q, después del trough de S) -- no en el
    punto más negativo de la ventana. El método viejo, en cambio, con S más
    profunda que Q, colapsa q_idx==s_idx en el trough de S (el mínimo
    GLOBAL de toda la ventana) -- ni siquiera distingue Q de S."""
    fs = 500.0
    signal, r_idx = _triphasic_qs_deeper_s(fs, 2.0, 1.0)

    result = delineate_qrs(signal, r_idx, fs)

    q_trough_true = r_idx - int(0.025 * fs)
    s_trough_true = r_idx + int(0.028 * fs)

    assert result.onset_idx <= q_trough_true, (
        "El onset debería caer en o antes del trough de Q (cruce de baseline), "
        "no después de él."
    )
    assert result.offset_idx >= s_trough_true, (
        "El offset debería caer en o después del trough de S (cruce de baseline), "
        "no antes de él."
    )

    analyzer = ECGAnalyzer(fs=fs)
    q_old, s_old = analyzer.segment_qrs_complex(signal, r_idx)
    assert q_old == s_old, (
        "Este es precisamente el defecto que motiva el delineador nuevo: "
        "argmin() sobre toda la ventana debería colapsar q_idx y s_idx en el "
        "mismo punto (el trough de S, más profundo que el de Q) -- si esto "
        "cambia, la señal sintética ya no reproduce el defecto documentado."
    )


# --- 3. Captura de la R' del patrón RSR' --------------------------------------

def test_rsr_prime_two_positive_deflections_captured():
    """El delineador nuevo debe reportar DOS deflexiones positivas (R y
    R_prime) como entradas separadas de `peaks`. `find_peaks` con el filtro
    de 300ms entre latidos (el que usa `ECGAnalyzer.detect_r_peaks()`) NO
    puede verlas por separado -- se reproduce esa limitación explícitamente
    para contrastar."""
    fs = 500.0
    signal, r_idx = _rsr_prime(fs, 2.0, 1.0)

    result = delineate_qrs(signal, r_idx, fs)

    positive_types = [p["type"] for p in result.peaks if p["amplitude"] > 0]
    assert "R" in positive_types
    assert "R_prime" in positive_types, (
        f"La R' no fue capturada -- peaks encontrados: {result.peaks}"
    )
    r_prime_entries = [p for p in result.peaks if p["type"] == "R_prime"]
    assert len(r_prime_entries) == 1
    assert r_prime_entries[0]["idx"] > r_idx  # R' es posterior al pico R principal

    s_entries = [p for p in result.peaks if p["type"] == "S"]
    assert len(s_entries) == 1
    assert r_idx < s_entries[0]["idx"] < r_prime_entries[0]["idx"]  # orden R, S, R'

    # Contraste explícito con el filtro de 300ms del pipeline vivo -- reproduce
    # la limitación documentada en la auditoría de Sub-Fase 2, no se asume.
    whole_beat_peaks, _ = find_peaks(
        signal, distance=int(0.3 * fs), height=np.mean(signal) + 0.3 * np.std(signal)
    )
    peaks_within_this_beat = [p for p in whole_beat_peaks if abs(int(p) - r_idx) < int(0.15 * fs)]
    assert len(peaks_within_this_beat) == 1, (
        "find_peaks(distance=300ms) debería ver un único pico en este latido "
        "-- si ve dos, el filtro de distancia ya no reproduce la limitación "
        "documentada y esta prueba de contraste dejó de ser válida."
    )


# --- 4. Contra PTB-XL real (si hay red disponible) ----------------------------

def test_delineation_on_real_ptbxl_v1_v6():
    """Registro real de PTB-XL (no sintético). Verifica `sig_name` antes de
    indexar (nunca asume posición 6/11) -- mismo patrón de extracción
    verificado diseñado en la Fase 1. Si no hay red disponible, se salta
    con motivo explícito -- no se falla el suite completo por falta de
    conectividad, ni se fabrica un resultado."""
    try:
        import wfdb
    except ImportError:
        pytest.skip("wfdb no instalado")

    try:
        record = wfdb.rdrecord("00001_lr", pn_dir="ptb-xl/1.0.3/records100/00000")
    except Exception as exc:
        pytest.skip(f"PTB-XL no accesible en este entorno ({type(exc).__name__}: {exc}) -- "
                     "verificado por separado que la red SÍ está disponible en general; "
                     "esto no bloquea la sub-fase, ver CHANGELOG.md.")

    names = [n.strip().upper() for n in record.sig_name]
    assert "V1" in names and "V6" in names, f"Registro sin V1/V6: {names}"

    v1 = record.p_signal[:, names.index("V1")]
    v6 = record.p_signal[:, names.index("V6")]
    fs = float(record.fs)

    analyzer = ECGAnalyzer(fs=fs)
    for lead_name, lead_signal in [("V1", v1), ("V6", v6)]:
        r_peaks = analyzer.detect_r_peaks(lead_signal)
        if len(r_peaks) < 2:
            continue  # registro/derivación sin picos R claros a esta fs -- no es lo que se prueba aquí
        r_idx = int(r_peaks[1])  # segundo latido, evita bordes del registro
        result = delineate_qrs(lead_signal, r_idx, fs)

        assert result.onset_idx < r_idx < result.offset_idx, (
            f"[{lead_name}] onset/offset deberían encerrar al pico R: "
            f"onset={result.onset_idx} r={r_idx} offset={result.offset_idx}"
        )
        # Rango fisiológicamente plausible (generoso -- normal a muy patológico),
        # no una validación clínica -- eso es Fase 3.
        assert 20.0 <= result.qrs_duration_ms <= 300.0, (
            f"[{lead_name}] duración fuera de rango plausible: {result.qrs_duration_ms}ms"
        )
