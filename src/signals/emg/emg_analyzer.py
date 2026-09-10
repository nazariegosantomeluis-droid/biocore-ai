"""
EMG Analyzer - activación muscular y marcadores espectrales de fatiga.

Misma forma que `src/signals/eeg/eeg_analyzer.py` (EegAnalyzer/EegAnalysis):
`analyze(signal) -> EmgAnalysis`, valores con unidad honesta.

TODO el cálculo corre sobre la señal FILTRADA (`preprocess_emg`, butter
20-450 Hz + rectificado interno). La frecuencia mediana (MDF) sobre señal
CRUDA estaría sesgada hacia abajo por artefacto de movimiento (baja
frecuencia) y hacia arriba por ruido de alta frecuencia; la activación,
por el DC. Filtrar primero no es una preferencia -- es lo que hace que la
MDF sea el marcador de fatiga que la literatura describe.

Las fórmulas NO cambiaron respecto de las 3 funciones sueltas que vivían
en `app/main.py` (Capa 5A dominio muscular, Tanda 1 -- lado señal,
2026-09-09): median_frequency (searchsorted sobre la CDF del PSD de Welch),
fatigue_index (mapa lineal de la MDF vs. un basal de 120 Hz), activación
(mean|x| / max|x|). Solo se consolidaron y se les garantizó la entrada
filtrada.

DEUDA CONOCIDA, DIFERIDA: `fatigue_index` sigue clavado en ~0 sobre el
generador demo (`generate_demo_emg_signal`, ruido blanco -> espectro plano
-> MDF ~fs/4, muy por encima del basal). Es un bug del GENERADOR, no de la
fórmula (sobre sEMG real band-limited la MDF cae ~101 Hz -> ~60 Hz con la
fatiga y el índice responde). No se persiste al UPS hasta recalibrar el
generador o restringir la escritura a CSV/hardware -- ver el diagnóstico
del dominio muscular.
"""

import numpy as np
from dataclasses import dataclass
from typing import Any, Dict
from scipy.signal import welch

from .preprocessing import preprocess_emg

# fatigue_index = (MDF_BASELINE_HZ - MDF) / MDF_SPAN_HZ * 100, acotado 0-100.
# Mapa lineal desde una MDF de referencia "sin fatiga": a medida que la
# fatiga desplaza la MDF hacia abajo, el índice sube; 60 Hz de caída = 100.
# Constantes heredadas TAL CUAL de `compute_emg_fatigue_index()` -- NO se
# recalibran aquí (necesitarían firma de experto, como el basal del BAR).
MDF_BASELINE_HZ: float = 120.0
MDF_SPAN_HZ: float = 60.0

_WELCH_NPERSEG_CAP: int = 1024
_ACTIVATION_EPS: float = 1e-9


def median_frequency(signal: np.ndarray, fs: float) -> float:
    """MDF: la frecuencia que parte la potencia total del espectro (Welch
    PSD) en dos mitades iguales. Marcador estándar de fatiga muscular -- se
    desplaza hacia abajo cuando baja la velocidad de conducción de la fibra.
    Devuelve 0.0 si el espectro no tiene potencia."""
    freqs, psd = welch(signal, fs=fs, nperseg=min(_WELCH_NPERSEG_CAP, len(signal)))
    if psd.size == 0:
        return 0.0
    cdf = np.cumsum(psd)
    if cdf[-1] <= 0:
        return 0.0
    median_idx = np.searchsorted(cdf, cdf[-1] / 2.0)
    return float(freqs[min(median_idx, len(freqs) - 1)])


def fatigue_index_from_mdf(mdf_hz: float) -> float:
    """Índice 0-100 desde el corrimiento de la MDF respecto de
    `MDF_BASELINE_HZ`. Fórmula heredada sin cambios."""
    fatigue = (MDF_BASELINE_HZ - mdf_hz) / MDF_SPAN_HZ * 100.0
    return float(np.clip(fatigue, 0.0, 100.0))


@dataclass
class EmgAnalysis:
    activation_pct: float          # % -- mean|x| / max|x| sobre señal FILTRADA
    median_frequency_hz: float     # Hz -- MDF del espectro de potencia (Welch)
    fatigue_index: float           # 0-100 -- corrimiento de la MDF vs. baseline
    findings: Dict[str, Any]


class EmgAnalyzer:
    """Analiza EMG de superficie: activación + marcadores de fatiga.
    Mismo contrato que `EegAnalyzer`: `EmgAnalyzer(fs).analyze(signal)`."""

    def __init__(self, fs: float = 1000.0):
        self.fs = fs

    def analyze(self, signal: np.ndarray) -> EmgAnalysis:
        if signal.ndim != 1:
            signal = signal.flatten()

        filtered, _ = preprocess_emg(signal, self.fs)
        rect = np.abs(filtered)
        activation = float(
            np.clip(np.mean(rect) / (np.max(rect) + _ACTIVATION_EPS) * 100.0, 0.0, 100.0)
        )
        mdf = median_frequency(filtered, self.fs)
        fatigue = fatigue_index_from_mdf(mdf)

        findings = {
            "Activación muscular": f"{activation:.1f} %",
            "Frecuencia mediana (MDF)": f"{mdf:.1f} Hz",
            "Índice de fatiga": f"{fatigue:.0f} / 100",
        }
        return EmgAnalysis(
            activation_pct=activation,
            median_frequency_hz=mdf,
            fatigue_index=fatigue,
            findings=findings,
        )
