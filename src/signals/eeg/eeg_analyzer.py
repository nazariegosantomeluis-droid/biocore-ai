"""
EEG Analyzer - Frequency band analysis and clinical pattern classification.
"""

import numpy as np
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple
from scipy.signal import welch

# Ratio Beta/Alfa (BAR) -- biomarcador de arousal cortical citado, NO una
# invención de esta app: BAR = P_beta / P_alpha del MISMO electrodo, así que
# el cociente cancela las variables anatómicas (grosor de cráneo, distancia
# fuente-sensor, ganancia) que hacen indefendible la potencia beta ABSOLUTA
# entre sujetos. Rangos de referencia: basal 0.8-1.2; arousal (Stroop /
# Trier Social Stress Test) BAR > 1.8. Fuente: Schutter DJLG 2006 /
# Handbook of Psychophysiology, 3a ed., cap. 10.
BAR_BASELINE_RANGE: Tuple[float, float] = (0.8, 1.2)
BAR_AROUSAL_THRESHOLD: float = 1.8
BAR_CITATION: str = "Schutter DJLG 2006 / Handbook of Psychophysiology 3a ed. cap.10 (Beta/Alpha Ratio, arousal cortical)"

# alpha_power por debajo de esto se trata como "sin ritmo alfa medible" -->
# el cociente es indefinido, NO infinito. Un ratio indefinido se declara
# indefinido (None), nunca se fuerza a un número.
_BAR_ALPHA_FLOOR: float = 1e-9

# DAR (Ratio Delta/Alfa) -- Neuro DAR+TBR (2026-09-10). Cociente de dos
# band power del mismo electrodo, mismo criterio que el BAR (cancela
# variables anatómicas). Citado en monitorización EEG continua de UCI
# neurocrítica: la razón INVERSA alfa/delta que cae sostenidamente (>50%,
# >=2h) predice isquemia cerebral diferida tras hemorragia subaracnoidea de
# mal grado -- DAR es su inverso, sube cuando delta domina sobre alfa
# (enlentecimiento cortical). Fuente: Claassen J et al. 2004, Clin
# Neurophysiol 115(12):2699-2710.
#
# PENDING_VALIDATION: `DAR_ELEVATED_REFERENCE` es el valor transcrito de
# ESE contexto clínico específico (HSA en UCI, cambio relativo sostenido en
# el tiempo) -- NO confirmado por el experto como umbral aplicable a la
# población general de BIOCORE ni a una lectura puntual. El ratio en sí
# (band power reales / band power reales) se persiste sin reservas; lo que
# espera firma es la interpretación clínica de "sufrimiento cortical" sobre
# ese número. No degradar a validado sin confirmación explícita.
DAR_ELEVATED_REFERENCE: float = 1.0
DAR_CITATION: str = (
    "Claassen J et al. 2004, Clin Neurophysiol 115(12):2699-2710 (razón alfa/delta inversa, "
    "isquemia cerebral diferida post-HSA) -- PENDING_VALIDATION"
)
DAR_THRESHOLD_PENDING_VALIDATION: bool = True
_DAR_ALPHA_FLOOR: float = 1e-9

# TBR (Ratio Theta/Beta) -- mismo cociente adimensional, banda frontal.
# Citado originalmente como discriminante de TDAH (cutoff que luego adoptó
# el sistema "NEBA" con autorización FDA). Fuente: Monastra VJ, Lubar JF,
# Linden M. 2001, Neuropsychology 15(1):136-144.
#
# PENDING_VALIDATION: el meta-análisis posterior de Arns M, Conners CK,
# Kraemer HC. 2013, J Atten Disord 17(5):374-383 ("A decade of EEG
# Theta/Beta Ratio Research in ADHD") encontró que el tamaño de efecto del
# TBR elevado se redujo con los años y cuestionó la generalización de ese
# punto de corte -- la propia literatura está en disputa, razón de más para
# no hardcodear `TBR_ELEVATED_REFERENCE` como umbral validado sin que el
# experto confirme su aplicabilidad aquí.
TBR_ELEVATED_REFERENCE: float = 3.0
TBR_CITATION: str = (
    "Monastra VJ, Lubar JF, Linden M. 2001, Neuropsychology 15(1):136-144; cuestionado por "
    "Arns M, Conners CK, Kraemer HC. 2013, J Atten Disord 17(5):374-383 (meta-análisis) -- "
    "PENDING_VALIDATION"
)
TBR_THRESHOLD_PENDING_VALIDATION: bool = True
_TBR_BETA_FLOOR: float = 1e-9


def beta_alpha_ratio(beta_power: float, alpha_power: float) -> Optional[float]:
    """BAR = beta_power / alpha_power. Adimensional -- su valor NO depende
    de la escala absoluta de la señal (por eso el experto lo eligió sobre
    `beta_power` crudo). Devuelve `None` si `alpha_power` es ~0 (cociente
    indefinido) -- honestidad de borde: no se inventa un infinito ni un
    tope arbitrario. Fuente: ver `BAR_CITATION`."""
    if alpha_power is None or beta_power is None:
        return None
    if not np.isfinite(alpha_power) or not np.isfinite(beta_power):
        return None
    if abs(alpha_power) < _BAR_ALPHA_FLOOR:
        return None
    return float(beta_power) / float(alpha_power)


def delta_alpha_ratio(delta_power: float, alpha_power: float) -> Optional[float]:
    """DAR = delta_power / alpha_power. Mismo criterio de honestidad de
    borde que `beta_alpha_ratio`: `None` si `alpha_power` es ~0 (indefinido,
    NO un infinito ni un tope arbitrario). Fuente: ver `DAR_CITATION`. El
    umbral de interpretación clínica (`DAR_ELEVATED_REFERENCE`) está
    PENDING_VALIDATION -- esta función solo calcula el ratio, no lo
    clasifica."""
    if delta_power is None or alpha_power is None:
        return None
    if not np.isfinite(delta_power) or not np.isfinite(alpha_power):
        return None
    if abs(alpha_power) < _DAR_ALPHA_FLOOR:
        return None
    return float(delta_power) / float(alpha_power)


def theta_beta_ratio(theta_power: float, beta_power: float) -> Optional[float]:
    """TBR = theta_power / beta_power. Mismo criterio de honestidad de
    borde: `None` si `beta_power` es ~0 (indefinido). Fuente: ver
    `TBR_CITATION`. El umbral de interpretación clínica
    (`TBR_ELEVATED_REFERENCE`) está PENDING_VALIDATION -- esta función solo
    calcula el ratio, no lo clasifica."""
    if theta_power is None or beta_power is None:
        return None
    if not np.isfinite(theta_power) or not np.isfinite(beta_power):
        return None
    if abs(beta_power) < _TBR_BETA_FLOOR:
        return None
    return float(theta_power) / float(beta_power)


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
    # BAR (Ratio Beta/Alfa) -- biomarcador de arousal cortical (ver
    # `beta_alpha_ratio` y `BAR_CITATION`). `None` si no hay ritmo alfa
    # medible (alpha_power ~0) -- indefinido, no forzado a un número.
    bar: Optional[float] = None
    # DAR (Ratio Delta/Alfa) -- enlentecimiento cortical (ver
    # `delta_alpha_ratio` y `DAR_CITATION`). `None` si alpha_power ~0.
    # Umbral clínico PENDING_VALIDATION -- ver `DAR_ELEVATED_REFERENCE`.
    dar: Optional[float] = None
    # TBR (Ratio Theta/Beta) -- carga/fatiga atencional (ver
    # `theta_beta_ratio` y `TBR_CITATION`). `None` si beta_power ~0.
    # Umbral clínico PENDING_VALIDATION -- ver `TBR_ELEVATED_REFERENCE`.
    tbr: Optional[float] = None


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
        # DAR/TBR reusan los mismos band power ya calculados arriba para el
        # BAR -- no se recalcula el PSD, solo se toman otros dos cocientes
        # de los mismos 4 valores (delta/theta/alpha/beta).
        bar = beta_alpha_ratio(band_power['beta'], band_power['alpha'])
        dar = delta_alpha_ratio(band_power['delta'], band_power['alpha'])
        tbr = theta_beta_ratio(band_power['theta'], band_power['beta'])
        classification = self._classify_pattern(dominant_band, band_power)
        clinical_note = self._interpretation_text(dominant_band)
        summary = self._build_summary(dominant_band, band_power, classification, clinical_note)
        findings = self._build_findings(dominant_band, classification, clinical_note, band_power)
        findings['Beta/Alpha Ratio (BAR)'] = f"{bar:.2f}" if bar is not None else "indefinido (sin ritmo alfa)"
        findings['Delta/Alpha Ratio (DAR)'] = (
            f"{dar:.2f} (umbral clínico PENDING_VALIDATION)" if dar is not None else "indefinido (sin ritmo alfa)"
        )
        findings['Theta/Beta Ratio (TBR)'] = (
            f"{tbr:.2f} (umbral clínico PENDING_VALIDATION)" if tbr is not None else "indefinido (sin ritmo beta)"
        )

        return EegAnalysis(
            dominant_band=dominant_band,
            band_power=band_power,
            classification=classification,
            summary=summary,
            findings=findings,
            bar=bar,
            dar=dar,
            tbr=tbr,
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
