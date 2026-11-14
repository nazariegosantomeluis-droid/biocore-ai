"""Preparación de la señal en vivo y revisión de calidad por canal.

`prepare()` quita la tendencia lineal y, si se pide, el ruido de la red con un filtro notch. El resto (pasa-banda
de 0.5 a 40 Hz y rechazo de ventanas con artefactos) lo hace `EegAnalyzer`; aplicarlo aquí también lo haría dos
veces y sesgaría el exponente aperiódico, que corrige exactamente un paso de ese filtro (`spectral_model.py`).

`assess_channels()` marca tres problemas con umbrales de ingeniería (`QualityHeuristics`), no con un criterio
clínico citado: canal plano, canal mucho más amplio que los demás y mucho ruido de red. Lo que se le dice a la
persona sobre los dos últimos sale de Tatum et al. 2011 (`clinical.eeg_references.TATUM_2011`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy.signal import butter, detrend, filtfilt, iirnotch

NOTCH_Q = 30.0
QUALITY_BAND_HZ = (0.5, 40.0)        # la misma banda que analiza `EegAnalyzer`
MAINS_HALF_WIDTH_HZ = 2.0

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
    mains_rms_uv: Optional[float]      # RMS alrededor de la frecuencia de red, antes del notch
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
    """Filtro notch en `mains_hz` (ida y vuelta, sin desfase). Sin efecto si no se pide o no cabe en fs/2."""
    if not mains_hz or mains_hz >= fs / 2.0 or x.shape[-1] <= 9:
        return x
    b, a = iirnotch(mains_hz, NOTCH_Q, fs)
    return filtfilt(b, a, x, axis=-1)


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
    mains = None
    if mains_hz:
        lo, hi = mains_hz - MAINS_HALF_WIDTH_HZ, mains_hz + MAINS_HALF_WIDTH_HZ
        centered = np.asarray(raw, dtype=float) - np.mean(raw, axis=-1, keepdims=True)
        mains_band = _bandpass(centered, fs, lo, hi)
        if mains_band is not None:
            mains = np.sqrt(np.mean(mains_band ** 2, axis=-1))
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
