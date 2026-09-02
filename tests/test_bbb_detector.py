"""Verificación del detector morfológico de Bloqueo de Rama -- Detector BBB,
Fase 3 (`clinical/bbb_detector.py`).

Dos niveles, deliberadamente separados:
1. Las reglas de clasificación puras (`_check_rbbb_v1/_v6`,
   `_check_lbbb_v1/_v6`) contra objetos `QrsDelineation` construidos a mano
   -- rápido, preciso, sin depender de que una señal sintética produzca
   exactamente la morfología deseada tras pasar por el delineador real.
2. Un puñado de pruebas de extremo a extremo (señal -> `detect_bundle_
   branch_block`) para los casos donde una señal sintética simple SÍ
   reproduce el patrón de forma confiable (QRS angosto, sin latido válido,
   LBBB de un solo lóbulo).

La "prueba de fuego" pedida para la Fase 3 -- la matriz de confusión contra
los 50 casos reales de PTB-XL, extremo a extremo (señal real -> detector
completo, incluida la localización de latido) -- vive aparte en
`tests/test_bbb_detector_validation.py`. Ese es el test que de verdad
certifica el pipeline completo contra datos reales; este archivo cubre la
lógica en aislamiento y unos pocos casos sintéticos simples, más rápidos y
deterministas para CI."""

from __future__ import annotations

import numpy as np

from clinical.bbb_detector import (
    INDETERMINATE_LABEL,
    QRS_MAX_HALF_AMPLITUDE_WIDTH_MS,
    _check_lbbb_v1,
    _check_lbbb_v6,
    _check_rbbb_qr_v1,
    _check_rbbb_v1,
    _check_rbbb_v6,
    _half_amplitude_width_ms,
    _looks_like_qrs,
    _select_reference_beat,
    detect_bundle_branch_block,
)
from clinical.qrs_delineation import QrsDelineation

FS = 500.0


def _peak(ptype, idx, amplitude):
    return {"type": ptype, "idx": idx, "amplitude": amplitude}


def _delineation(peaks, onset=0, offset=100, duration_ms=150.0):
    return QrsDelineation(onset_idx=onset, offset_idx=offset, qrs_duration_ms=duration_ms, peaks=peaks)


# --- Reglas puras: RBBB --------------------------------------------------

def test_rbbb_v1_confirmed_when_terminal_second_positive_dominates():
    d = _delineation([_peak("R", 10, 0.25), _peak("S", 20, -0.35), _peak("R_prime", 40, 0.60)])
    ok, reason = _check_rbbb_v1(d)
    assert ok, reason


def test_rbbb_v1_rejected_when_only_one_positive_deflection():
    """RSR' en V1 exige una SEGUNDA deflexión positiva -- una R simple, sin
    R', no cumple."""
    d = _delineation([_peak("R", 10, 0.70)])
    ok, reason = _check_rbbb_v1(d)
    assert not ok, reason


def test_rbbb_v1_rejected_when_second_positive_is_not_dominant():
    d = _delineation([_peak("R", 10, 0.60), _peak("S", 20, -0.30), _peak("R_prime", 40, 0.15)])
    ok, reason = _check_rbbb_v1(d)
    assert not ok, reason


def test_rbbb_v1_rejected_when_terminal_deflection_is_negative_not_the_second_positive():
    """La segunda deflexión positiva existe pero NO es la terminal (algo
    negativo la sigue) -- no cumple "terminal"."""
    d = _delineation([_peak("R", 10, 0.30), _peak("R_prime", 25, 0.50), _peak("S", 40, -0.20)])
    ok, reason = _check_rbbb_v1(d)
    assert not ok, reason


def test_rbbb_v6_confirmed_with_wide_deep_terminal_s():
    signal = np.zeros(200)
    signal[10:30] = np.linspace(1.0, -0.3, 20)  # R descendiendo hacia S
    signal[30:55] = -0.3  # S sostenida ~50ms (a fs=500 -> 50 muestras=100ms, de sobra >=40ms)
    d = _delineation([_peak("R", 10, 1.0), _peak("S", 30, -0.3)], onset=0, offset=60)
    ok, reason = _check_rbbb_v6(signal, d, FS)
    assert ok, reason


def test_rbbb_v6_rejected_when_s_too_shallow():
    signal = np.zeros(200)
    signal[10:20] = np.linspace(1.0, -0.05, 10)
    signal[20:30] = -0.05
    d = _delineation([_peak("R", 10, 1.0), _peak("S", 20, -0.05)], onset=0, offset=35)
    ok, reason = _check_rbbb_v6(signal, d, FS)
    assert not ok, reason


def test_rbbb_v6_rejected_when_no_negative_deflection_after_r():
    d = _delineation([_peak("R", 10, 1.0)])
    ok, reason = _check_rbbb_v6(np.zeros(200), d, FS)
    assert not ok, reason


def test_rbbb_v6_accepts_a_custom_stricter_amplitude_threshold():
    """El criterio qR (Fase 4) reutiliza `_check_rbbb_v6` con un umbral de
    amplitud más estricto (-0.15mV en vez de -0.1mV) -- confirma que el
    parámetro realmente cambia el resultado, no solo se acepta y se
    ignora."""
    signal = np.zeros(200)
    signal[10:30] = np.linspace(1.0, -0.12, 20)
    signal[30:55] = -0.12
    d = _delineation([_peak("R", 10, 1.0), _peak("S", 30, -0.12)], onset=0, offset=60)
    ok_default, _ = _check_rbbb_v6(signal, d, FS)
    ok_strict, reason_strict = _check_rbbb_v6(signal, d, FS, max_amplitude_mv=-0.15)
    assert ok_default, "con el umbral clásico (-0.1mV) debería pasar"
    assert not ok_strict, reason_strict


# --- Reglas puras: RBBB, morfología qR atípica (Fase 4, 2026-08-12) -------
# Firma: validador clínico, Detector BBB, Fase 4 -- fuente citada: Chou's
# Electrocardiography in Clinical Practice / Marriott's Practical
# Electrocardiography. El patrón qR en V1 (sin el notch RSR' clásico) es
# una segunda morfología válida de RBBB, con su propia salvaguarda V6 (más
# estricta, ver arriba) -- ver `clinical/bbb_detector.py` y CHANGELOG.md.

def test_qr_v1_confirmed_for_q_then_single_prominent_r_no_trailing_s():
    d = _delineation([_peak("Q", 10, -0.30), _peak("R", 25, 0.80)])
    ok, reason = _check_rbbb_qr_v1(d)
    assert ok, reason


def test_qr_v1_rejected_when_r_alone_without_a_preceding_q():
    """Hallazgo real de la Fase 4 (`ecg_id=826`/`1066`): una R única, sin
    ninguna deflexión negativa antes, es "R sola" -- no es qR, no se
    relaja el criterio para incluirla."""
    d = _delineation([_peak("R", 10, 0.90)])
    ok, reason = _check_rbbb_qr_v1(d)
    assert not ok, reason


def test_qr_v1_rejected_when_r_amplitude_too_small():
    d = _delineation([_peak("Q", 10, -0.30), _peak("R", 25, 0.30)])  # R < 0.5mV
    ok, reason = _check_rbbb_qr_v1(d)
    assert not ok, reason


def test_qr_v1_rejected_when_initial_q_too_shallow():
    d = _delineation([_peak("Q", 10, -0.05), _peak("R", 25, 0.80)])  # q > -0.1mV
    ok, reason = _check_rbbb_qr_v1(d)
    assert not ok, reason


def test_qr_v1_rejected_when_s_follows_the_r():
    """"Sin S posterior" es obligatorio -- una S tras la R es RS/qRS, no
    qR puro."""
    d = _delineation([_peak("Q", 10, -0.30), _peak("R", 25, 0.80), _peak("S", 40, -0.20)])
    ok, reason = _check_rbbb_qr_v1(d)
    assert not ok, reason


def test_qr_v1_rejected_when_a_second_positive_deflection_present():
    """Dos positivas es candidato a R'/RSR' (morfología clásica), no qR."""
    d = _delineation([_peak("Q", 10, -0.30), _peak("R", 25, 0.80), _peak("R_prime", 40, 0.60)])
    ok, reason = _check_rbbb_qr_v1(d)
    assert not ok, reason


def test_end_to_end_qr_morphology_confirms_rbbb_with_v6_safeguard():
    """qR en V1 + S ancha/profunda en V6 (cumpliendo el umbral más estricto
    del qR, -0.15mV) -> RBBB, por la morfología B."""
    signal_v6 = np.zeros(200)
    signal_v6[10:30] = np.linspace(1.0, -0.30, 20)
    signal_v6[30:60] = -0.30  # S sostenida >=40ms, amplitud <=-0.15mV
    d_v1 = _delineation([_peak("Q", 10, -0.30), _peak("R", 25, 0.80)])
    d_v6 = _delineation([_peak("R", 10, 1.0), _peak("S", 30, -0.30)], onset=0, offset=65)

    qr_v1_ok, _ = _check_rbbb_qr_v1(d_v1)
    qr_v6_ok, _ = _check_rbbb_v6(signal_v6, d_v6, FS, max_amplitude_mv=-0.15, min_duration_ms=40.0)
    assert qr_v1_ok and qr_v6_ok, "ambas mitades del criterio qR deberían cumplirse en este caso"


def test_qr_v1_alone_without_v6_safeguard_is_not_enough():
    """La salvaguarda V6 es AND obligatorio -- qR en V1 sin S ancha/profunda
    en V6 NUNCA basta por sí solo (regresión directa de la regla "nunca se
    relaja la salvaguarda")."""
    d_v1 = _delineation([_peak("Q", 10, -0.30), _peak("R", 25, 0.80)])
    d_v6_no_s = _delineation([_peak("R", 10, 1.0)])  # sin S en absoluto
    qr_v1_ok, _ = _check_rbbb_qr_v1(d_v1)
    qr_v6_ok, reason = _check_rbbb_v6(np.zeros(200), d_v6_no_s, FS, max_amplitude_mv=-0.15)
    assert qr_v1_ok
    assert not qr_v6_ok, reason


# --- Reglas puras: LBBB ---------------------------------------------------

def test_lbbb_v1_confirmed_for_clean_qs():
    d = _delineation([_peak("Q", 10, -1.2)])
    ok, reason = _check_lbbb_v1(d)
    assert ok, reason


def test_lbbb_v1_rejected_when_second_positive_deflection_present():
    d = _delineation([_peak("R", 10, 0.2), _peak("S", 20, -0.3), _peak("R_prime", 40, 0.5)])
    ok, reason = _check_lbbb_v1(d)
    assert not ok, reason


def test_lbbb_v1_rejected_when_dominant_is_positive():
    d = _delineation([_peak("R", 10, 0.8), _peak("S", 20, -0.2)])
    ok, reason = _check_lbbb_v1(d)
    assert not ok, reason


def test_lbbb_v6_confirmed_for_wide_r_without_septal_q():
    d = _delineation([_peak("R", 10, 1.5)])
    ok, reason = _check_lbbb_v6(d)
    assert ok, reason


def test_lbbb_v6_rejected_when_septal_q_present():
    d = _delineation([_peak("Q", 5, -0.20), _peak("R", 15, 1.5)])
    ok, reason = _check_lbbb_v6(d)
    assert not ok, reason


def test_lbbb_v6_rejected_when_dominant_is_negative():
    d = _delineation([_peak("Q", 10, -1.0)])
    ok, reason = _check_lbbb_v6(d)
    assert not ok, reason


# --- Selección del latido de referencia compartido (sincronización V1/V6) --
# Corrección de plomería, Fase 3 (2026-08-12): antes, V1 y V6 elegían su
# latido de referencia CADA UNA por su cuenta -- confirmado contra los 50
# casos reales que podían terminar describiendo complejos separados hasta
# 5368ms, invalidando la premisa del criterio ("R' en V1 Y S ancha en V6
# del MISMO complejo"). Ver `clinical/bbb_detector.py::_select_reference_
# beat()` y CHANGELOG.md.

def _impulse_train(fs, total_s, beat_times, amp=1.0, sigma=0.01, seed=0):
    n = int(total_s * fs)
    t = np.arange(n) / fs
    signal = np.zeros(n)
    for bt in beat_times:
        signal += amp * np.exp(-((t - bt) ** 2) / (2 * sigma ** 2))
    rng = np.random.default_rng(seed)
    return signal + rng.normal(0, 0.002, n)


def test_select_reference_beat_excludes_first_and_last():
    fs = 500.0
    beat_times = [0.3, 1.1, 1.9, 2.7, 3.5, 4.3]
    signal = _impulse_train(fs, 5.0, beat_times)
    idx = _select_reference_beat(signal, fs)
    chosen_time = round(idx / fs, 2)
    assert chosen_time not in (beat_times[0], beat_times[-1])


def test_select_reference_beat_prefers_the_middle_of_the_recording():
    fs = 500.0
    beat_times = [0.3, 1.1, 1.9, 2.7, 3.5, 4.3]
    signal = _impulse_train(fs, 5.0, beat_times)
    idx = _select_reference_beat(signal, fs)
    chosen_time = round(idx / fs, 2)
    # entre los interiores (1.1/1.9/2.7/3.5), los mas cercanos al centro
    # temporal del registro (2.5s) son 1.9 y 2.7
    assert chosen_time in (1.9, 2.7)


def test_select_reference_beat_avoids_ectopic_short_coupled_beat():
    """Un latido con RR muy corto respecto a sus vecinos (acoplamiento
    corto tipo extrasístole) nunca se elige como referencia -- ver
    `REFERENCE_BEAT_RR_TOLERANCE`. Varios de los 50 casos reales de
    validación tienen PVCs documentadas en su reporte original de PTB-XL."""
    fs = 500.0
    beat_times = [0.3, 1.1, 1.9, 2.4, 3.2, 4.0, 4.8]  # 1.9->2.4 = 0.5s, la mitad del RR normal (0.8s)
    signal = _impulse_train(fs, 5.3, beat_times)
    idx = _select_reference_beat(signal, fs)
    chosen_time = round(idx / fs, 2)
    assert chosen_time != 2.4


def test_select_reference_beat_returns_none_without_peaks():
    """Señal perfectamente plana (sin ruido): `find_peaks` no encuentra
    ningún máximo local estricto -- caso degenerado, no una señal ruidosa
    real (el ruido casi siempre produce ALGÚN pico por encima del umbral
    permisivo de `_detect_reference_peaks`, ver
    `test_end_to_end_no_valid_beat_returns_none_pattern`, que cubre ese
    caso a través de la puerta de ancho de QRS en vez de aquí)."""
    flat = np.zeros(int(2.0 * FS))
    assert _select_reference_beat(flat, FS) is None


# --- Distinguir QRS de onda T (`_looks_like_qrs`) ---------------------------
# Corrección posterior a la sincronización, misma fecha (2026-08-12): la
# regularidad de RR NO distingue QRS de onda T -- una T ocurre una vez por
# latido, igual que el QRS, así que pasa el filtro de `REFERENCE_BEAT_RR_
# TOLERANCE` igual de bien. Confirmado contra datos reales: los anclajes
# automáticos que antes caían en onda T en `ecg_id=1123`/`1232` (hallados en
# la investigación de solo lectura previa a esta tanda) medían 88-112ms de
# ancho a media amplitud, frente a 16-62ms de picos de QRS conocidos -- ver
# CHANGELOG.md para la calibración completa contra los 50 casos reales.

def _gaussian_bump(t, center, sigma, amp):
    return amp * np.exp(-((t - center) ** 2) / (2 * sigma ** 2))


def test_looks_like_qrs_true_for_narrow_peak():
    fs = 500.0
    t = np.arange(int(1.0 * fs)) / fs
    signal = _gaussian_bump(t, 0.5, 0.010, 1.0)  # FWHM ~24ms -- típico de un QRS
    assert _looks_like_qrs(signal, int(0.5 * fs), fs) is True


def test_looks_like_qrs_false_for_wide_rounded_peak():
    fs = 500.0
    t = np.arange(int(1.0 * fs)) / fs
    signal = _gaussian_bump(t, 0.5, 0.070, 1.0)  # FWHM ~165ms -- típico de una onda T
    assert _looks_like_qrs(signal, int(0.5 * fs), fs) is False


def test_half_amplitude_width_matches_known_gaussian_scale():
    """Sanity check de la métrica en sí: un gaussiano de sigma conocido
    tiene un ancho a media altura (FWHM) teórico de 2.355*sigma."""
    fs = 500.0
    sigma = 0.020
    t = np.arange(int(1.0 * fs)) / fs
    signal = _gaussian_bump(t, 0.5, sigma, 1.0)
    measured = _half_amplitude_width_ms(signal, int(0.5 * fs), fs)
    expected = 2.355 * sigma * 1000.0
    assert abs(measured - expected) < 8.0  # tolerancia por muestreo discreto (2ms/muestra)


def test_select_reference_beat_prefers_qrs_over_periodic_t_wave():
    """El caso central de esta corrección: una onda T PERIÓDICA (misma
    cadencia que el QRS, 320ms después de cada latido -- más allá de los
    300ms mínimos que exige `_detect_reference_peaks` entre picos, para que
    ambas se detecten como picos separados). El filtro de regularidad de RR
    por sí solo no distinguiría cuál es cuál; el filtro de anchura sí."""
    fs = 500.0
    total_s = 6.0
    beat_times = [0.3, 1.1, 1.9, 2.7, 3.5, 4.3, 5.1]
    t = np.arange(int(total_s * fs)) / fs
    signal = np.zeros_like(t)
    for bt in beat_times:
        signal = signal + _gaussian_bump(t, bt, 0.010, 1.0)          # QRS: angosto
        signal = signal + _gaussian_bump(t, bt + 0.32, 0.070, 0.35)  # T: ancha, periódica
    rng = np.random.default_rng(7)
    signal = signal + rng.normal(0, 0.002, len(signal))

    idx = _select_reference_beat(signal, fs)
    chosen_time = idx / fs
    nearest_beat = min(beat_times, key=lambda bt: abs(bt - chosen_time))
    assert abs(chosen_time - nearest_beat) < 0.05, (
        f"ancla en t={chosen_time:.2f}s -- no cae cerca de un QRS ({nearest_beat}s), "
        "parece haber elegido la onda T"
    )


def test_detect_bundle_branch_block_delineates_v1_and_v6_on_the_same_beat():
    """Regresión directa del bug de sincronización: espía las llamadas a
    `delineate_qrs()` y confirma que V1 y V6 se delinean con el MISMO
    `r_idx` -- no dos latidos elegidos independientemente."""
    from unittest.mock import patch

    import clinical.bbb_detector as bbb_detector_module

    total_s, period = 3.0, 0.8
    v1 = _repeat_beat(FS, total_s, period, [(0.0, 0.040, -1.2)])
    v6 = _repeat_beat(FS, total_s, period, [(0.0, 0.040, 1.5)])

    calls = []
    original = bbb_detector_module.delineate_qrs

    def spy(signal, r_idx, fs):
        calls.append(r_idx)
        return original(signal, r_idx, fs)

    with patch.object(bbb_detector_module, "delineate_qrs", side_effect=spy):
        detect_bundle_branch_block(v1, v6, FS)

    assert len(calls) == 2
    assert calls[0] == calls[1], f"V1 y V6 se delinearon en latidos distintos: {calls}"


def test_detect_bundle_branch_block_uses_explicit_reference_signal_when_given():
    """Con `reference_signal` (p.ej. lead II), el ancla se deriva de ESA
    señal, no de V6 -- confirma que el parámetro realmente se usa, no solo
    se acepta y se ignora."""
    from unittest.mock import patch

    import clinical.bbb_detector as bbb_detector_module

    total_s, period = 3.0, 0.8
    v1 = _repeat_beat(FS, total_s, period, [(0.0, 0.040, -1.2)])
    v6 = _repeat_beat(FS, total_s, period, [(0.0, 0.040, 1.5)])
    # lead II sintética con latidos en instantes DISTINTOS a V1/V6 (fase
    # desplazada), para que el ancla resultante sea verificablemente la de
    # esta señal y no la de v6.
    reference = _repeat_beat(FS, total_s, 0.7, [(0.0, 0.030, 1.0)])

    calls = []
    original = bbb_detector_module._select_reference_beat

    def spy(signal, fs):
        idx = original(signal, fs)
        calls.append((signal is reference, idx))
        return idx

    with patch.object(bbb_detector_module, "_select_reference_beat", side_effect=spy):
        detect_bundle_branch_block(v1, v6, FS, reference_signal=reference)

    assert len(calls) == 1
    assert calls[0][0] is True, "no se usó `reference_signal` para elegir el ancla"


# --- Extremo a extremo: casos donde una señal sintética simple basta ------

def _gaussian(t, center, sigma, amp):
    return amp * np.exp(-((t - center) ** 2) / (2 * sigma ** 2))


def _repeat_beat(fs, total_s, period_s, components):
    n = int(total_s * fs)
    t = np.arange(n) / fs
    signal = np.zeros(n)
    beat_time = 0.3
    while beat_time < total_s - 0.3:
        for offset_s, sigma, amp in components:
            signal += _gaussian(t, beat_time + offset_s, sigma, amp)
        beat_time += period_s
    rng = np.random.default_rng(0)
    return signal + rng.normal(0, 0.003, n)


def test_end_to_end_lbbb_pattern_confirmed():
    """QS único y profundo en V1 (sin componente previo que contamine el
    baseline pre-QRS) + R ancha en V6 -- el caso de un solo lóbulo, donde el
    latido de referencia SÍ coincide con el inicio real del complejo."""
    total_s, period = 3.0, 0.8
    v1 = _repeat_beat(FS, total_s, period, [(0.0, 0.040, -1.2)])
    v6 = _repeat_beat(FS, total_s, period, [(0.0, 0.040, 1.5)])
    result = detect_bundle_branch_block(v1, v6, FS)
    assert result.pattern == "LBBB", result.reasoning
    assert result.qrs_duration_ms > 120.0


def test_end_to_end_narrow_qrs_returns_none_pattern_not_false_normal():
    """QRS que no supera el umbral -> `pattern=None` (ver docstring de
    `BbbMorphologyResult`: nunca "no BBB" definitivo, honesto sobre el
    límite de lo que este detector midió)."""
    total_s, period = 3.0, 0.8
    v1 = _repeat_beat(FS, total_s, period, [(0.0, 0.010, 0.5)])
    v6 = _repeat_beat(FS, total_s, period, [(0.0, 0.010, 1.0)])
    result = detect_bundle_branch_block(v1, v6, FS)
    assert result.pattern is None
    assert result.qrs_duration_ms <= 120.0


def test_end_to_end_no_valid_beat_returns_none_pattern():
    flat = np.zeros(int(2.0 * FS)) + np.random.default_rng(1).normal(0, 0.001, int(2.0 * FS))
    result = detect_bundle_branch_block(flat, flat, FS)
    assert result.pattern is None


def test_conflicting_hard_criteria_never_forces_a_branch():
    """Red de seguridad: si (hipotéticamente) ambas ramas cumplieran sus
    criterios duros a la vez, el resultado es indeterminado, nunca una
    rama forzada -- se ejercita llamando directamente las reglas, no vía
    señal (el conflicto no ocurre en la práctica, ver docstring del
    módulo)."""
    v1_peaks = [_peak("Q", 10, -1.2)]  # cumple LBBB_V1
    v1 = _delineation(v1_peaks)
    ok_lbbb_v1, _ = _check_lbbb_v1(v1)
    assert ok_lbbb_v1
