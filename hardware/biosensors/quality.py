"""Revisión de calidad del EMG en vivo (heurísticas de ingeniería, sin criterio clínico citado).

Tres avisos para la salida RAW del MyoWare 2.0 leída con el ADC de la ESP32, ya convertida a mV en la piel:

- «saturada»: más del 1 % de las muestras pegadas al límite del ADC (±8.25 mV en la piel con el MyoWare a 3.3 V y
  ganancia 200: 1.65 V / 200). Un electrodo flojo o un movimiento brusco llevan la salida al tope.
- «plana»: RMS menor a 2 µV entre 20 y 450 Hz: el sensor sin alimentación o un cable suelto.
- «red»: más de 0.05 mV RMS de zumbido de la red antes del filtro notch, medido como una línea en 50 o 60 Hz que
  sobresale del espectro a su alrededor (`mains_line_rms`): un electrodo con mal contacto o la computadora conectada
  a la pared. Medir solo la banda de 58 a 62 Hz confundía una contracción fuerte con zumbido, porque el EMG también
  tiene potencia ahí.

`prepare()` quita la media y el zumbido de la red (el mismo notch que el EEG en vivo); el pasa-banda de 20 a 450 Hz
lo pone `EmgAnalyzer`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
from scipy.signal import butter, filtfilt

from hardware.eeg_live.quality import mains_line_rms, remove_mains

EMG_RAIL_MV = 3.3 / 2.0 / 200.0 * 1000.0       # 8.25 mV: la mitad del rango del ADC entre la ganancia del MyoWare
ISSUE_TEXT = {
    'saturada': 'La señal toca el límite del ADC: revisa que los tres electrodos estén bien pegados y quédate quieto.',
    'plana': 'Señal plana: revisa la alimentación del MyoWare (3V3 y GND) y el cable de RAW.',
    'red': 'Mucho zumbido de la red eléctrica: revisa el contacto de los electrodos (sobre todo la referencia) y que '
           'la computadora esté con batería.',
}


@dataclass(frozen=True)
class EmgQualityHeuristics:
    rail_fraction: float = 0.01
    rail_margin: float = 0.98            # «pegada al límite» = |x| ≥ 98 % de EMG_RAIL_MV
    flat_rms_mv: float = 0.002
    mains_rms_mv: float = 0.05           # zumbido de la red (`mains_line_rms`), antes del notch


def _band_rms(x: np.ndarray, fs: float, low: float, high: float) -> Optional[float]:
    nyq = fs / 2.0
    high = min(high, 0.99 * nyq)
    if not 0 < low < high or x.size <= 15:
        return None
    b, a = butter(2, [low / nyq, high / nyq], btype='band')
    return float(np.sqrt(np.mean(filtfilt(b, a, x) ** 2)))


def prepare(x_mv: np.ndarray, fs: float, mains_hz: Optional[float]) -> np.ndarray:
    x = np.asarray(x_mv, dtype=float)
    if x.size < 2:
        return x.copy()
    return remove_mains(x - np.mean(x), fs, mains_hz)


def emg_quality(x_mv: np.ndarray, fs: float, mains_hz: Optional[float],
                heuristics: EmgQualityHeuristics = EmgQualityHeuristics()) -> Tuple[str, ...]:
    x = np.asarray(x_mv, dtype=float)
    issues: List[str] = []
    if x.size == 0:
        return ()
    if np.mean(np.abs(x) >= heuristics.rail_margin * EMG_RAIL_MV) > heuristics.rail_fraction:
        issues.append('saturada')
    rms = _band_rms(x - np.mean(x), fs, 20.0, 450.0)
    if rms is not None and rms < heuristics.flat_rms_mv:
        issues.append('plana')
    if mains_hz:
        mains = mains_line_rms(x, fs, mains_hz)
        if mains is not None and mains > heuristics.mains_rms_mv:
            issues.append('red')
    return tuple(issues)


def rms_mv(x_mv: np.ndarray, fs: float) -> Optional[float]:
    """RMS entre 20 y 450 Hz (la misma banda que `EmgAnalyzer`), en mV."""
    x = np.asarray(x_mv, dtype=float)
    return _band_rms(x - np.mean(x), fs, 20.0, 450.0) if x.size else None
