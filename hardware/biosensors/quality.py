"""Revisión de calidad de los sensores en vivo de la placa ESP32 (heurísticas de ingeniería, sin criterio clínico
citado). Los umbrales viven en un `...Heuristics` por sensor, para ajustarlos con hardware real.

EMG: tres avisos para la salida RAW del MyoWare 2.0 leída con el ADC de la ESP32, ya convertida a mV en la piel:

- «saturada»: más del 1 % de las muestras pegadas al límite del ADC (±8.25 mV en la piel con el MyoWare a 3.3 V y
  ganancia 200: 1.65 V / 200). Un electrodo flojo o un movimiento brusco llevan la salida al tope.
- «plana»: RMS menor a 2 µV entre 20 y 450 Hz: el sensor sin alimentación o un cable suelto.
- «red»: más de 0.05 mV RMS de zumbido de la red antes del filtro notch, medido como una línea en 50 o 60 Hz que
  sobresale del espectro a su alrededor (`mains_line_rms`): un electrodo con mal contacto o la computadora conectada
  a la pared. Medir solo la banda de 58 a 62 Hz confundía una contracción fuerte con zumbido, porque el EMG también
  tiene potencia ahí.

`prepare()` quita la media y el zumbido de la red (el mismo notch que el EEG en vivo); el pasa-banda de 20 a 450 Hz
lo pone `EmgAnalyzer`.

Pulso por luz (MAX30102, 2026-11-16), sobre el análisis de `src/signals/ppg/analysis.py`: «sin dedo» (poca luz
infrarroja de fondo), «saturada» (el fondo toca el tope del ADC), «sin pulso» (menos de 3 intervalos plausibles) e
«irregular» (más de 20 % de los intervalos a más de 25 % de la mediana; medido con las grabaciones de ejemplo de
HeartPy: 0 % en la limpia, 22 % y 33 % en las dos con movimiento).

Temperatura (DS18B20, 2026-11-16): «arranque» si llega el valor de encendido del sensor (85 °C exactos, hoja de
datos), y `temp_trend()` para decir cuándo la sonda ya se estabilizó.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Optional, Tuple

import numpy as np
from scipy.signal import butter, filtfilt

from hardware.eeg_live.quality import mains_line_rms, remove_mains

if TYPE_CHECKING:                                   # solo para las anotaciones: la calidad no corre el análisis
    from src.signals.ppg.analysis import PpgAnalysis

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


# ---------------------------------------------------------------- pulso por luz (MAX30102)
PPG_FULL_SCALE = (1 << 18) - 1
PPG_ISSUE_TEXT = {
    'sin dedo': 'No hay un dedo sobre el sensor, o no tapa las dos luces: apoya la yema sin apretar.',
    'saturada': 'La luz satura el sensor: tapa la luz ambiente o baja la corriente de los LED en el firmware.',
    'sin pulso': 'No se encuentra una onda de pulso: quédate quieto y no aprietes el sensor (la presión aplasta el '
                 'pulso).',
    'irregular': 'Los intervalos entre pulsos varían mucho: casi siempre es movimiento, pero también puede ser un ritmo '
                 'irregular, y el PPG no distingue entre los dos. Mientras dure, la frecuencia, el índice de perfusión '
                 'y R no son confiables. Para el ritmo, usa el ECG.',
}


@dataclass(frozen=True)
class PpgQualityHeuristics:
    finger_dc_counts: float = 50_000.0   # menos luz infrarroja de fondo que esto: no hay dedo
    rail_fraction: float = 0.98          # fondo a más de 98 % del rango del ADC: saturado
    irregular_fraction: float = 0.2      # más de 20 % de los intervalos lejos de la mediana


def ppg_quality(analysis: 'PpgAnalysis', heuristics: PpgQualityHeuristics = PpgQualityHeuristics()
                ) -> Tuple[str, ...]:
    if analysis.dc_ir < heuristics.finger_dc_counts:
        return ('sin dedo',)                        # sin dedo, lo demás no significa nada
    issues: List[str] = []
    if max(analysis.dc_red, analysis.dc_ir) >= heuristics.rail_fraction * PPG_FULL_SCALE:
        issues.append('saturada')
    if analysis.pulse_rate_bpm is None:
        issues.append('sin pulso')
    elif analysis.irregular_fraction is not None and analysis.irregular_fraction > heuristics.irregular_fraction:
        issues.append('irregular')
    return tuple(issues)


# ---------------------------------------------------------------- temperatura (DS18B20)
TEMP_POWER_ON_C = 85.0                   # valor del registro al encender (hoja de datos)
TEMP_ISSUE_TEXT = {
    'arranque': '85 °C exactos es el valor de encendido del DS18B20 (hoja de datos): esa lectura no terminó. Revisa '
                'la alimentación (3V3) y la resistencia de 4.7 kΩ.',
}
STABLE_WINDOW_S = 60.0
STABLE_SLOPE_C_PER_MIN = 0.1             # «estable»: cambia menos de 0.1 °C por minuto (heurística)


def temp_quality(x_c: np.ndarray) -> Tuple[str, ...]:
    return ('arranque',) if np.any(np.asarray(x_c, dtype=float) == TEMP_POWER_ON_C) else ()


def valid_temperatures(x_c: np.ndarray) -> np.ndarray:
    """Sin las lecturas de encendido (85 °C exactos), que no son temperaturas medidas."""
    x = np.asarray(x_c, dtype=float)
    return x[x != TEMP_POWER_ON_C]


def temp_trend(x_c: np.ndarray, fs: float, window_s: float = STABLE_WINDOW_S) -> Optional[float]:
    """Pendiente en °C por minuto de los últimos `window_s` segundos (recta por mínimos cuadrados), o None si todavía
    no hay tantos segundos de señal."""
    x = valid_temperatures(x_c)
    n = int(round(window_s * fs))
    if n < 3 or x.size < n:
        return None
    t = np.arange(n) / fs
    return float(np.polyfit(t, x[-n:], 1)[0] * 60.0)


def is_stable(trend_c_per_min: Optional[float]) -> bool:
    return trend_c_per_min is not None and abs(trend_c_per_min) < STABLE_SLOPE_C_PER_MIN
