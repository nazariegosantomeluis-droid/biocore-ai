"""Delineador de QRS aislado -- Detector BBB, Sub-Fase 2.5.

Onset/offset del complejo QRS por cruce de umbral contra un baseline
isoeléctrico local, en vez de `argmin` en una ventana fija (el método de
`ECGAnalyzer.segment_qrs_complex()`, auditado en la Sub-Fase 2: amputa QRS
patológicamente anchos porque su ventana total, 120 ms, es igual al propio
umbral clínico que la dispara, y no puede reportar "no hay Q" porque
`argmin` siempre devuelve un índice, exista o no una onda real).

Extiende a QRS el mismo patrón de cruce-de-baseline que
`src/signals/ecg/wave_annotation.py` ya usa correctamente para P y T
(`_extract_p_wave`/`_extract_t_wave`, umbral contra baseline local) --
nunca antes aplicado al complejo QRS en ningún archivo del repo (ese mismo
archivo delinea Q/R/S con `argmin` + un padding arbitrario de ±10 ms y
`duration_ms=0` hardcodeado, el mismo defecto que este módulo corrige).

PROCEDENCIA DE LA ESPECIFICACIÓN NUMÉRICA: reglas firmadas por el
validador clínico (Detector BBB, Sub-Fase 2.5, aprobación 2026-08-09),
implementadas verbatim con una única excepción documentada explícitamente
en `_isoelectric_baseline()`: la redacción "umbral = ~0.05 mV o 2×std del
segmento isoeléctrico" no especifica cuál de las dos prevalece cuando
difieren -- se interpretó como `max(0.05, 2*std)` (el más estricto de los
dos, para no colapsar el umbral en señales muy limpias ni quedarse corto
en señales ruidosas). Si el validador quiso otra cosa, es un cambio de una
línea (`ISOELECTRIC_THRESHOLD_FLOOR_MV`/`ISOELECTRIC_THRESHOLD_STD_MULTIPLIER`
más abajo). El resto de las reglas (ventana ±120ms, segmento de baseline
R-120ms a R-80ms, sostenimiento de 10ms en el offset, distancia intra-QRS
de 20ms y prominencia 0.1mV en la búsqueda fina) no tuvo ambigüedad y se
implementó tal cual.

AISLADO del pipeline vivo -- verificado por grep (ver CHANGELOG.md): este
módulo no se importa desde `clinical/ecg_analyzer.py` ni desde ningún
call site de `detect_clinical_pattern()`. Coexiste con
`segment_qrs_complex()` sin reemplazarlo. La integración es Fase 3,
todavía no autorizada.
"""

from __future__ import annotations

import dataclasses
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy.signal import find_peaks

# --- Constantes de la especificación validada ---------------------------------

QRS_WINDOW_HALF_MS: float = 120.0
"""Ventana dinámica ±120 ms (240 ms total) centrada en el pico R -- nunca
amputa un QRS patológico de 160 ms (la ventana total de
`segment_qrs_complex()` es de solo 120 ms, igual al umbral clínico que la
dispara)."""

BASELINE_SEGMENT_START_MS: float = 120.0
BASELINE_SEGMENT_END_MS: float = 80.0
"""Segmento pre-QRS para el baseline isoeléctrico: R-120ms a R-80ms."""

ISOELECTRIC_THRESHOLD_FLOOR_MV: float = 0.05
ISOELECTRIC_THRESHOLD_STD_MULTIPLIER: float = 2.0
"""Umbral isoeléctrico = max(0.05 mV, 2*std(segmento isoeléctrico)) -- ver
nota de procedencia en el docstring del módulo sobre esta interpretación."""

OFFSET_SUSTAIN_MS: float = 10.0
"""El offset exige que la señal permanezca dentro de la franja isoeléctrica
al menos 10 ms seguidos -- evita terminar el QRS en un cruce por cero
transitorio entre deflexiones (p.ej. entre S y una R' tardía)."""

SUBPEAK_MIN_DISTANCE_MS: float = 20.0
SUBPEAK_MIN_PROMINENCE_MV: float = 0.1
"""Búsqueda fina de sub-picos dentro de [onset, offset]: SIN el filtro de
300 ms entre latidos que usa `ECGAnalyzer.detect_r_peaks()` -- distancia
mínima intra-QRS de solo 20 ms, para poder capturar la R' del patrón RSR'
(que `find_peaks(distance=300ms)` no puede ver por diseño, ver auditoría
de Sub-Fase 2)."""


@dataclasses.dataclass(frozen=True)
class QrsDelineation:
    """Resultado del delineador para un único complejo QRS."""

    onset_idx: int
    offset_idx: int
    qrs_duration_ms: float
    peaks: List[Dict]  # cada uno: {"type": "Q"|"R"|"R_prime"|"S", "idx": int, "amplitude": float}


def _isoelectric_baseline(signal: np.ndarray, r_idx: int, fs: float) -> Tuple[float, float]:
    """Baseline (media) y umbral de ruido del segmento pre-QRS R-120ms a R-80ms."""
    start = max(0, r_idx - int(BASELINE_SEGMENT_START_MS / 1000.0 * fs))
    end = max(start + 1, r_idx - int(BASELINE_SEGMENT_END_MS / 1000.0 * fs))
    segment = signal[start:end]
    if segment.size == 0:
        # Sin margen suficiente antes de R (latido pegado al borde de la señal)
        # -- baseline degenerado (0.0, piso del umbral) en vez de fallar; el
        # llamador puede detectarlo si onset_idx == window_start.
        return 0.0, ISOELECTRIC_THRESHOLD_FLOOR_MV
    baseline = float(np.mean(segment))
    noise_std = float(np.std(segment))
    threshold = max(ISOELECTRIC_THRESHOLD_FLOOR_MV, ISOELECTRIC_THRESHOLD_STD_MULTIPLIER * noise_std)
    return baseline, threshold


def _find_onset(signal: np.ndarray, r_idx: int, window_start: int, baseline: float, threshold: float) -> int:
    """Escanea hacia atrás desde R hasta |señal-baseline| <= umbral."""
    for i in range(r_idx, window_start - 1, -1):
        if abs(signal[i] - baseline) <= threshold:
            return i
    return window_start


def _find_offset(
    signal: np.ndarray,
    window_end: int,
    baseline: float,
    threshold: float,
    fs: float,
    search_from_idx: int,
) -> int:
    """Escanea hacia adelante desde `search_from_idx` (R, o R' si hay una
    R' más tardía) hasta que la señal regrese y permanezca >=10ms dentro de
    la franja isoeléctrica."""
    hold_samples = max(1, int(OFFSET_SUSTAIN_MS / 1000.0 * fs))
    last_start = window_end - hold_samples + 1
    for i in range(search_from_idx, last_start):
        segment = signal[i : i + hold_samples]
        if np.all(np.abs(segment - baseline) <= threshold):
            return i
    return window_end


def _find_late_r_prime_idx(signal: np.ndarray, r_idx: int, window_end: int, fs: float) -> Optional[int]:
    """Pre-escaneo liviano: ¿hay una segunda deflexión positiva prominente
    después de R, dentro de la ventana? Si la hay, el offset debe buscarse
    desde ahí, no desde R -- si no, el offset podría cerrarse sobre el
    cruce por baseline ENTRE S y R', cortando la R' fuera del complejo."""
    if window_end <= r_idx:
        return None
    segment = signal[r_idx : window_end + 1]
    distance = max(1, int(SUBPEAK_MIN_DISTANCE_MS / 1000.0 * fs))
    pos_local, _ = find_peaks(segment, distance=distance, prominence=SUBPEAK_MIN_PROMINENCE_MV)
    candidates = [r_idx + int(i) for i in pos_local if i > 0]
    return max(candidates) if candidates else None


def _find_subpeaks(signal: np.ndarray, onset_idx: int, offset_idx: int, fs: float) -> List[Dict]:
    """Sub-picos dentro de [onset, offset], SIN el filtro de 300ms --
    distancia intra-QRS >=20ms, prominencia >=0.1mV. Clasifica Q/R/R_prime/S
    por signo y posición relativa al pico R principal (el de mayor amplitud
    absoluta del complejo)."""
    if offset_idx <= onset_idx:
        return []

    segment = signal[onset_idx : offset_idx + 1]
    distance = max(1, int(SUBPEAK_MIN_DISTANCE_MS / 1000.0 * fs))

    pos_local, _ = find_peaks(segment, distance=distance, prominence=SUBPEAK_MIN_PROMINENCE_MV)
    neg_local, _ = find_peaks(-segment, distance=distance, prominence=SUBPEAK_MIN_PROMINENCE_MV)

    candidates: List[Tuple[int, float]] = [(onset_idx + int(i), float(segment[i])) for i in pos_local]
    candidates += [(onset_idx + int(i), float(segment[i])) for i in neg_local]

    if not candidates:
        # Ningún sub-pico con prominencia >=0.1mV -- se reporta al menos el
        # pico R principal (máximo bruto del segmento), sin inventar Q/S/R'
        # que no cumplen el umbral de prominencia de la especificación.
        r_local = int(np.argmax(segment))
        return [{"type": "R", "idx": onset_idx + r_local, "amplitude": float(segment[r_local])}]

    # El pico R principal es el candidato de mayor amplitud ABSOLUTA -- es el
    # evento dominante del complejo (convención clínica: R es la deflexión de
    # mayor magnitud del QRS).
    r_idx_final, r_amp = max(candidates, key=lambda c: abs(c[1]))

    peaks: List[Dict] = [{"type": "R", "idx": r_idx_final, "amplitude": r_amp}]
    for idx, amp in candidates:
        if idx == r_idx_final:
            continue
        if amp < 0 and idx < r_idx_final:
            ptype = "Q"
        elif amp < 0 and idx > r_idx_final:
            ptype = "S"
        elif amp > 0 and idx > r_idx_final:
            ptype = "R_prime"
        else:
            # Positivo y ANTES de R -- morfología atípica (notch temprano) no
            # contemplada explícitamente en la especificación validada. Se
            # etiqueta como R_prime (segunda deflexión positiva distinguible
            # de R) en vez de descartarla silenciosamente -- decisión a
            # revisar por el validador si aparece en datos reales.
            ptype = "R_prime"
        peaks.append({"type": ptype, "idx": idx, "amplitude": amp})

    peaks.sort(key=lambda p: p["idx"])
    return peaks


def delineate_qrs(signal: np.ndarray, r_peak_idx: int, fs: float) -> QrsDelineation:
    """Delinea un único complejo QRS alrededor de `r_peak_idx`, según la
    especificación numérica validada (ver docstring del módulo).

    AISLADO -- no se llama desde ningún punto del pipeline vivo todavía
    (Fase 3, no autorizada)."""
    half_window = int(QRS_WINDOW_HALF_MS / 1000.0 * fs)
    window_start = max(0, r_peak_idx - half_window)
    window_end = min(len(signal) - 1, r_peak_idx + half_window)

    baseline, threshold = _isoelectric_baseline(signal, r_peak_idx, fs)

    onset_idx = _find_onset(signal, r_peak_idx, window_start, baseline, threshold)

    # "Offset: escaneando hacia adelante desde R (o R')" -- si hay una R'
    # tardía dentro de la ventana, el offset se busca desde ahí, no desde R,
    # para no cerrar el complejo sobre el cruce por baseline entre S y R'.
    r_prime_idx = _find_late_r_prime_idx(signal, r_peak_idx, window_end, fs)
    offset_search_start = r_prime_idx if r_prime_idx is not None else r_peak_idx
    offset_search_start = max(offset_search_start, r_peak_idx)

    offset_idx = _find_offset(signal, window_end, baseline, threshold, fs, offset_search_start)

    peaks = _find_subpeaks(signal, onset_idx, offset_idx, fs)
    qrs_duration_ms = (offset_idx - onset_idx) / fs * 1000.0

    return QrsDelineation(
        onset_idx=onset_idx,
        offset_idx=offset_idx,
        qrs_duration_ms=qrs_duration_ms,
        peaks=peaks,
    )
