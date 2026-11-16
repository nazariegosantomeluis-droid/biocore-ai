"""Análisis de la onda de pulso (PPG) con dos luces, roja e infrarroja (2026-11-16).

La PPG detecta cambios del volumen de sangre en el lecho microvascular (Allen 2007). Con cada latido entra más
sangre al dedo, que absorbe más luz, así que lo que llega al sensor BAJA: `pulse_wave()` invierte la señal para
dibujar el pulso hacia arriba, como un monitor.

- `pulse_wave()`: pasa-banda de 0.5 a 8 Hz, Butterworth de segundo orden y de fase cero, el de Elgendi et al. 2013.
- `systolic_peaks()`: el método de dos promedios móviles de Elgendi et al. 2013, con sus parámetros (W1 = 111 ms,
  W2 = 667 ms, β = 0.02). Lo validaron en 40 registros de 20 s en reposo (5071 latidos). Se le agrega un periodo
  refractario de 0.3 s que no está en el artículo: si dos picos quedan más cerca, se queda el más alto.
- `analyze_ppg()`: la frecuencia de pulso (con la mediana de los intervalos), el índice de perfusión (cociente
  entre la parte pulsátil y la no pulsátil del infrarrojo, en %; definición de Beurton et al. 2019) y el cociente
  R = (AC/DC del rojo) / (AC/DC del infrarrojo).

La SpO₂ NO se calcula. Un oxímetro convierte R en SpO₂ con una curva calibrada contra mediciones directas de la
saturación arterial (Jubran 2015), y un MAX30102 suelto no la tiene: cualquier fórmula sería un número sin
calibrar.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
from scipy.signal import butter, filtfilt

BAND_HZ = (0.5, 8.0)              # Elgendi et al. 2013
PEAK_WINDOW_S = 0.111             # W1, Elgendi et al. 2013
BEAT_WINDOW_S = 0.667             # W2, Elgendi et al. 2013
BETA = 0.02                       # Elgendi et al. 2013
REFRACTORY_S = 0.3                # agregado (no está en el artículo): 200 latidos por minuto como máximo
INTERVAL_RANGE_S = (0.3, 2.0)     # intervalos plausibles: de 200 a 30 latidos por minuto
MIN_INTERVALS = 3                 # menos intervalos que estos: no se informa la frecuencia
IRREGULAR_DEVIATION = 0.25        # un intervalo «fuera» se aleja más de 25 % de la mediana (heurística)
# HEURISTIC (2026-11-16, Art. I): piso de amplitud de la onda filtrada, en cuentas del ADC. Por debajo no hay un pulso
# que el sensor resuelva y no se buscan latidos. Sin él, una señal pegada al tope del ADC (constante) dejaba ~1e-9
# cuentas de ruido numérico del filtro y el detector las contaba como latidos (42 lpm «irregular»). Calibración
# medida: sin pulso, ≤ 2.5e-9 cuentas con la señal constante y hasta 2.4 con ruido de cuantización (σ = 0.5 cuentas,
# 50 semillas); el pulso más chico probado (índice de perfusión 0.02 % sobre 50 000 cuentas, el umbral de «sin dedo»)
# deja 11.9. Límite conocido: ruido de 1 cuenta o más puede pasar el piso. Pendiente de calibrar con el sensor real.
MIN_PULSE_AMPLITUDE_COUNTS = 5.0


def bandpass(x: np.ndarray, fs: float, band=BAND_HZ) -> np.ndarray:
    """Butterworth de segundo orden, ida y vuelta (sin desfase), con 1 s de relleno contra los bordes."""
    x = np.asarray(x, dtype=float)
    nyquist = fs / 2.0
    high = min(band[1], 0.9 * nyquist)
    b, a = butter(2, [band[0] / nyquist, high / nyquist], btype='band')
    return filtfilt(b, a, x, padlen=min(x.size - 1, int(round(fs))))


def pulse_wave(counts: np.ndarray, fs: float) -> np.ndarray:
    """La luz recibida, filtrada e invertida: cada latido queda como un pico hacia arriba."""
    return -bandpass(counts, fs)


def _moving_average(x: np.ndarray, width: int) -> np.ndarray:
    width = max(1, int(width))
    return np.convolve(x, np.ones(width) / width, mode='same')      # centrado, como en el artículo


def systolic_peaks(wave: np.ndarray, fs: float) -> np.ndarray:
    """Índices de los picos sistólicos de una onda de pulso ya filtrada (picos hacia arriba)."""
    wave = np.asarray(wave, dtype=float)
    w1 = int(round(PEAK_WINDOW_S * fs))
    if wave.size < 3 * w1:
        return np.array([], dtype=int)
    squared = np.clip(wave, 0.0, None) ** 2              # recorta lo negativo y eleva al cuadrado
    ma_peak = _moving_average(squared, w1)
    ma_beat = _moving_average(squared, int(round(BEAT_WINDOW_S * fs)))
    blocks = ma_peak > ma_beat + BETA * np.mean(squared)   # THR1
    edges = np.diff(blocks.astype(int))
    starts = list(np.where(edges == 1)[0] + 1)
    ends = list(np.where(edges == -1)[0] + 1)
    if blocks[0]:
        starts.insert(0, 0)
    if blocks[-1]:
        ends.append(blocks.size)
    peaks: list = []
    refractory = REFRACTORY_S * fs
    for start, end in zip(starts, ends):
        if end - start < w1:                              # THR2 = W1: un bloque más angosto es ruido
            continue
        peak = start + int(np.argmax(wave[start:end]))
        if peaks and peak - peaks[-1] < refractory:
            if wave[peak] > wave[peaks[-1]]:
                peaks[-1] = peak
            continue
        peaks.append(peak)
    return np.array(peaks, dtype=int)


def plausible_intervals(peaks: np.ndarray, fs: float) -> np.ndarray:
    intervals = np.diff(np.asarray(peaks)) / fs
    return intervals[(intervals >= INTERVAL_RANGE_S[0]) & (intervals <= INTERVAL_RANGE_S[1])]


@dataclass(frozen=True)
class PpgAnalysis:
    fs: float
    wave: np.ndarray                          # onda de pulso del infrarrojo (filtrada e invertida)
    peaks: np.ndarray                         # índices de los picos sistólicos en `wave`
    intervals_s: np.ndarray                   # intervalos plausibles entre picos
    pulse_rate_bpm: Optional[float]           # 60 / mediana de los intervalos
    irregular_fraction: Optional[float]       # fracción de intervalos a más de 25 % de la mediana
    dc_red: float
    dc_ir: float
    perfusion_index_pct: Optional[float]      # AC/DC del infrarrojo × 100
    ratio_r: Optional[float]                  # (AC/DC rojo) / (AC/DC infrarrojo), mediana latido a latido


def analyze_ppg(red: np.ndarray, ir: np.ndarray, fs: float) -> PpgAnalysis:
    """`red` e `ir` en cuentas del sensor (luz recibida), con la misma frecuencia de muestreo."""
    red = np.asarray(red, dtype=float)
    ir = np.asarray(ir, dtype=float)
    wave_ir, wave_red = pulse_wave(ir, fs), pulse_wave(red, fs)
    if wave_ir.size == 0 or np.ptp(wave_ir) < MIN_PULSE_AMPLITUDE_COUNTS:
        peaks = np.array([], dtype=int)                  # sin amplitud que el sensor resuelva: no hay latidos
    else:
        peaks = systolic_peaks(wave_ir, fs)
    all_intervals = np.diff(peaks) / fs
    ok = (all_intervals >= INTERVAL_RANGE_S[0]) & (all_intervals <= INTERVAL_RANGE_S[1])
    intervals = all_intervals[ok]
    dc_red, dc_ir = float(np.median(red)), float(np.median(ir))
    if intervals.size < MIN_INTERVALS:
        return PpgAnalysis(fs, wave_ir, peaks, intervals, None, None, dc_red, dc_ir, None, None)
    median = float(np.median(intervals))
    irregular = float(np.mean(np.abs(intervals - median) > IRREGULAR_DEVIATION * median))
    # Amplitud pulsátil latido a latido, entre dos picos seguidos, en las dos luces con los mismos límites.
    beats = [(peaks[k], peaks[k + 1]) for k in np.where(ok)[0]]
    ac_ir = np.array([np.ptp(wave_ir[a:b + 1]) for a, b in beats])
    ac_red = np.array([np.ptp(wave_red[a:b + 1]) for a, b in beats])
    pi = ratio = None
    if dc_ir > 0:
        pi = float(100.0 * np.median(ac_ir) / dc_ir)
        if dc_red > 0 and np.all(ac_ir > 0):
            ratio = float(np.median((ac_red / dc_red) / (ac_ir / dc_ir)))
    return PpgAnalysis(fs, wave_ir, peaks, intervals, 60.0 / median, irregular, dc_red, dc_ir, pi, ratio)
