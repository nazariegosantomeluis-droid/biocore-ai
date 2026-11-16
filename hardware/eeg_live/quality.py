"""Preparación de la señal en vivo y revisión de calidad por canal.

`prepare()` quita la tendencia lineal y, si se pide, el ruido de la red con un filtro notch. El resto (pasa-banda
de 0.5 a 40 Hz y rechazo de ventanas con artefactos) lo hace `EegAnalyzer`; aplicarlo aquí también lo haría dos
veces y sesgaría el exponente aperiódico, que corrige exactamente un paso de ese filtro (`spectral_model.py`).

`assess_channels()` marca tres problemas con umbrales de ingeniería (`QualityHeuristics`), no con un criterio
clínico citado: canal plano, canal mucho más amplio que los demás y mucho ruido de red. Lo que se le dice a la
persona sobre los dos últimos sale de Tatum et al. 2011 (`clinical.eeg_references.TATUM_2011`).

`mains_line_rms()` mide el zumbido de la red como una línea del espectro; también lo usa el EMG en vivo
(`hardware/biosensors/quality.py`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
from scipy.signal import butter, detrend, filtfilt, iirnotch, welch

NOTCH_Q = 30.0
QUALITY_BAND_HZ = (0.5, 40.0)        # la misma banda que analiza `EegAnalyzer`
MAINS_HALF_WIDTH_HZ = 2.0            # la línea de la red, con la fuga de la ventana, cabe en ±2 Hz
MAINS_FLANK_HZ = (4.0, 10.0)         # el piso del espectro se estima entre 4 y 10 Hz a cada lado de la línea
MAINS_MIN_RATIO = 4.0                # la banda de la línea debe valer al menos 4 veces el piso para contar
MAINS_MIN_SECONDS = 2.0              # con segmentos de 1 s, al menos 3 segmentos de Welch

ISSUE_TEXT = {
    'plano': 'Señal plana: el electrodo no hace contacto o el canal está apagado.',
    'distinto': ('Mucho más amplio que los demás canales. Lo que aparece en un solo canal es artefacto hasta '
                 'demostrar lo contrario: revisa ese electrodo y vuelve a fijarlo.'),
    'red': ('Mucho ruido de la red eléctrica: aleja cables y cargadores. Un electrodo con mal contacto lo '
            'empeora.'),
}


@dataclass(frozen=True)
class QualityHeuristics:
    """Umbrales de ingeniería (sin cita clínica), en un solo lugar para ajustarlos con hardware real."""

    flat_rms_uv: float = 0.5           # por debajo, en 0.5-40 Hz: canal plano
    outlier_ratio: float = 4.0         # más de 4 veces la mediana de los demás canales
    min_channels_for_outlier: int = 3
    mains_rms_uv: float = 10.0         # ruido de red, antes del notch


@dataclass(frozen=True)
class ChannelQuality:
    channel: str
    rms_uv: float                      # RMS en 0.5-40 Hz, después del notch
    mains_rms_uv: Optional[float]      # RMS del zumbido de la red (`mains_line_rms`), antes del notch
    issues: Tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.issues

    @property
    def messages(self) -> List[str]:
        return [ISSUE_TEXT[i] for i in self.issues]


def _bandpass(x: np.ndarray, fs: float, low: float, high: float) -> Optional[np.ndarray]:
    nyquist = fs / 2.0
    if not 0 < low < high < nyquist:
        return None
    b, a = butter(2, [low / nyquist, high / nyquist], btype='band')
    if x.shape[-1] <= 3 * max(len(a), len(b)):
        return None
    return filtfilt(b, a, x, axis=-1)


def remove_mains(x: np.ndarray, fs: float, mains_hz: Optional[float]) -> np.ndarray:
    """Filtro notch en `mains_hz` (ida y vuelta, sin desfase). Sin efecto si no se pide o no cabe en fs/2.

    El notch con Q = 30 responde despacio (décimas de segundo): con el relleno corto que pone `filtfilt` por defecto
    (9 muestras), un zumbido fuerte deja una oscilación falsa en los bordes de la ventana. Con 1 s de relleno
    desaparece (medido: con 3 mV de red, el borde pasa de 1.37 mV de oscilación a lo mismo que el centro).
    """
    if not mains_hz or mains_hz >= fs / 2.0 or x.shape[-1] <= 9:
        return x
    b, a = iirnotch(mains_hz, NOTCH_Q, fs)
    return filtfilt(b, a, x, axis=-1, padlen=min(x.shape[-1] - 1, int(round(fs))))


def mains_line_rms(x: np.ndarray, fs: float, mains_hz: Optional[float]
                   ) -> Union[None, float, np.ndarray]:
    """RMS del zumbido de la red en `x` (en su misma unidad; un valor por canal), o None si no se puede medir.

    El zumbido es una línea: casi toda su potencia cae a ±2 Hz de `mains_hz`. El EMG, y el artefacto muscular en el
    EEG, son de banda ancha y también ponen potencia ahí: medir solo la banda los confunde con la red (medido: una
    contracción simulada de 0.4 mV de RMS dejaba unos 0.05 mV entre 58 y 62 Hz, justo el umbral del EMG). Por eso
    se resta el piso del espectro a los lados (mediana entre 4 y 10 Hz de distancia), y solo cuenta si la banda de
    la línea vale al menos `MAINS_MIN_RATIO` veces ese piso; si no, es 0. Welch con segmentos de 1 s (1 Hz de
    resolución); hacen falta `MAINS_MIN_SECONDS` de señal.
    """
    x = np.asarray(x, dtype=float)
    nyquist = fs / 2.0
    if not mains_hz or mains_hz + MAINS_HALF_WIDTH_HZ >= nyquist or x.shape[-1] < MAINS_MIN_SECONDS * fs:
        return None
    f, p = welch(x, fs=fs, window='hann', nperseg=int(round(fs)), detrend='linear', axis=-1)
    distance = np.abs(f - mains_hz)
    line = distance <= MAINS_HALF_WIDTH_HZ
    flank = (distance >= MAINS_FLANK_HZ[0]) & (distance <= MAINS_FLANK_HZ[1]) & (f < 0.95 * nyquist)
    if np.count_nonzero(flank) < 3:
        return None
    df = f[1] - f[0]
    band = np.sum(p[..., line], axis=-1) * df
    floor = np.median(p[..., flank], axis=-1) * np.count_nonzero(line) * df
    excess = np.sqrt(np.clip(band - floor, 0.0, None))
    out = np.where(band >= MAINS_MIN_RATIO * floor, excess, 0.0)
    return float(out) if out.ndim == 0 else out


def prepare(raw: np.ndarray, fs: float, mains_hz: Optional[float]) -> np.ndarray:
    """Sin tendencia lineal y sin red. Forma (canales, muestras), en µV."""
    raw = np.asarray(raw, dtype=float)
    if raw.shape[-1] < 2:
        return raw.copy()
    return remove_mains(detrend(raw, axis=-1, type='linear'), fs, mains_hz)


def assess_channels(raw: np.ndarray, prepared: np.ndarray, fs: float, channels: Sequence[str],
                    mains_hz: Optional[float], heuristics: QualityHeuristics = QualityHeuristics()
                    ) -> Dict[str, ChannelQuality]:
    """Calidad de cada canal en el tramo recibido."""
    band = _bandpass(np.asarray(prepared, dtype=float), fs, *QUALITY_BAND_HZ)
    rms = (np.sqrt(np.mean(band ** 2, axis=-1)) if band is not None
           else np.std(np.asarray(prepared, dtype=float), axis=-1))
    mains = mains_line_rms(np.atleast_2d(np.asarray(raw, dtype=float)), fs, mains_hz)
    out: Dict[str, ChannelQuality] = {}
    for i, name in enumerate(channels):
        issues = []
        if rms[i] < heuristics.flat_rms_uv:
            issues.append('plano')
        others = np.delete(rms, i)
        if (len(channels) >= heuristics.min_channels_for_outlier and others.size
                and rms[i] > heuristics.outlier_ratio * max(float(np.median(others)), heuristics.flat_rms_uv)):
            issues.append('distinto')
        mains_i = None if mains is None else float(mains[i])
        if mains_i is not None and mains_i > heuristics.mains_rms_uv:
            issues.append('red')
        out[name] = ChannelQuality(name, float(rms[i]), mains_i, tuple(issues))
    return out
