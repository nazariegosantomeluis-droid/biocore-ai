"""
EEG Analyzer - Frequency band analysis and clinical pattern classification.
"""

import numpy as np
from dataclasses import dataclass
from typing import Any, Dict, Tuple
from scipy.signal import welch


def _trapz(y: np.ndarray, x: np.ndarray) -> float:
    y = np.asarray(y, dtype=float)
    x = np.asarray(x, dtype=float)
    if y.size < 2 or x.size < 2:
        return 0.0
    return float(np.sum((x[1:] - x[:-1]) * 0.5 * (y[1:] + y[:-1])))


@dataclass
class EegAnalysis:
    dominant_band: str
    band_power: Dict[str, float]
    classification: str
    summary: str
    findings: Dict[str, Any]


class EegAnalyzer:
    """Analyze EEG for band power, dominant rhythm, and clinical interpretation."""

    def __init__(self, fs: float = 256.0):
        self.fs = fs

    def analyze(self, signal: np.ndarray) -> EegAnalysis:
        if signal.ndim != 1:
            signal = signal.flatten()

        nperseg = min(512, signal.shape[0])
        freqs, psd = welch(signal, fs=self.fs, nperseg=nperseg)
        band_power = {
            'delta': self._band_power(freqs, psd, 0.5, 3.5),
            'theta': self._band_power(freqs, psd, 4.0, 7.5),
            'alpha': self._band_power(freqs, psd, 8.0, 12.0),
            'beta': self._band_power(freqs, psd, 13.0, 30.0),
            'gamma': self._band_power(freqs, psd, 30.0, 45.0),
        }
        dominant_band = max(band_power, key=band_power.get)
        classification = self._classify_pattern(dominant_band, band_power)
        clinical_note = self._interpretation_text(dominant_band)
        summary = self._build_summary(dominant_band, band_power, classification, clinical_note)
        findings = self._build_findings(dominant_band, classification, clinical_note, band_power)

        return EegAnalysis(
            dominant_band=dominant_band,
            band_power=band_power,
            classification=classification,
            summary=summary,
            findings=findings
        )

    def _band_power(self, freqs: np.ndarray, psd: np.ndarray, low: float, high: float) -> float:
        mask = (freqs >= low) & (freqs <= high)
        return float(_trapz(psd[mask], freqs[mask])) if np.any(mask) else 0.0

    def _classify_pattern(self, dominant_band: str, band_power: Dict[str, float]) -> str:
        if dominant_band == 'alpha':
            return 'Despierto relajado'
        if dominant_band == 'beta':
            return 'Alerta / Enfocado'
        if dominant_band == 'theta':
            return 'Sueño ligero / Somnolencia'
        if dominant_band == 'delta':
            return 'Sueño profundo / Ritmo lento'
        if dominant_band == 'gamma':
            return 'Actividad cortical alta / Activación cognitiva'
        return 'Patrón no determinado'

    def _interpretation_text(self, dominant_band: str) -> str:
        mapping = {
            'alpha': 'Puede corresponder a relajación con ojos cerrados o estado de dominancia de la corteza occipital.',
            'beta': 'Sugiere atención, estrés mental o estado de alerta aumentada.',
            'theta': 'Suele aparecer en somnolencia, sueño ligero y estados de transición.',
            'delta': 'Indica actividad de sueño profundo o un ritmo cortical muy lento.',
            'gamma': 'Asociado con procesamiento cognitivo y actividad cortical sincronizada de alta frecuencia.',
        }
        return mapping.get(dominant_band, 'Patrón EEG no específico.')

    def _build_findings(
        self,
        dominant_band: str,
        classification: str,
        clinical_note: str,
        band_power: Dict[str, float]
    ) -> Dict[str, Any]:
        findings = {
            'Dominant Band': dominant_band.upper(),
            'Classification': classification,
            'Clinical Note': clinical_note,
            'Delta Power': f"{band_power['delta']:.3f}",
            'Theta Power': f"{band_power['theta']:.3f}",
            'Alpha Power': f"{band_power['alpha']:.3f}",
            'Beta Power': f"{band_power['beta']:.3f}",
            'Gamma Power': f"{band_power['gamma']:.3f}",
        }
        if dominant_band == 'delta':
            findings['Alert'] = 'Verificar estado de sueño profundo y descartar encefalopatía de onda lenta si procede.'
        elif dominant_band == 'theta':
            findings['Alert'] = 'Monitorizar somnolencia y potenciales patrones de transición de sueño.'
        elif dominant_band == 'beta':
            findings['Alert'] = 'Consultar estrés mental o estado de activación cortical elevada.'
        return findings

    def _build_summary(
        self,
        dominant_band: str,
        band_power: Dict[str, float],
        classification: str,
        clinical_note: str
    ) -> str:
        return (
            f"Dominante: {dominant_band.upper()} | Clasificación: {classification}. "
            f"Interpretación: {clinical_note} "
            f"Power: Δ={band_power['delta']:.2f}, θ={band_power['theta']:.2f}, "
            f"α={band_power['alpha']:.2f}, β={band_power['beta']:.2f}, γ={band_power['gamma']:.2f}."
        )
