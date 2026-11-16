"""
Tanda 4, Pieza 2 (2026-07-04) — Clasificación clínica + explicabilidad real
sobre una señal de ECG cruda ya obtenida (sintética del UPS, modo A, o de
hardware real, modo B) — este módulo nunca genera ni inventa la señal, solo
la analiza. Cero `np.random`, cero resultado hardcodeado: cada valor sale
de `clinical.ecg_analyzer.ECGAnalyzer` (detección de picos R real) y
`src.feature_extraction`/`src.interpretability` (HRV real + explicación por contribución de pesos fijos)
sobre esa misma señal.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

from clinical.ecg_analyzer import ECGAnalyzer
from src.feature_extraction import UNRELIABLE_MOMENT_REASON, compute_psd, extract_features
from clinical.ecg_analyzer import pattern_label_es
from src.interpretability import generate_shap_lime_report

# compute_psd exige >=4 intervalos RR (>=5 picos R) — por debajo de eso no
# se calcula explicabilidad, se informa honestamente en vez de forzarlo.
MIN_RR_INTERVALS_FOR_EXPLAINABILITY = 4

__all__ = ["EcgClassificationResult", "classify_ecg_signal"]


@dataclass(frozen=True)
class EcgClassificationResult:
    """`confidence` se retiró (2026-08-06) -- era una constante literal por
    rama de regla en `ECGAnalyzer.detect_clinical_pattern()`
    (0.95/0.92/.../0.60), sin ningún cálculo detrás, mostrada como si fuera
    una probabilidad. `reasoning` ya cita el criterio medido exacto (valor +
    umbral) que disparó el patrón -- eso es lo honesto, no un porcentaje
    inventado. Ver CHANGELOG.md."""

    pattern: str
    reasoning: List[str]
    features: Dict[str, float]
    r_peak_count: int
    shap_lime: Optional[Dict[str, Any]]
    explainability_note: Optional[str]
    # Tanda 2 de la fase 1: métricas HRV que no se pudieron calcular de forma fiable -> {etiqueta: motivo}
    unavailable_features: Dict[str, str] = field(default_factory=dict)


def classify_ecg_signal(signal: np.ndarray, fs: float) -> EcgClassificationResult:
    """Clasifica `signal` (real, ya sea sintética-del-UPS o de hardware) con
    el analizador real y, si hay suficientes latidos, calcula
    explicación por contribución de pesos fijos (heurística; no es SHAP ni LIME)
    sobre las mismas métricas HRV extraídas de esa señal — nunca sobre texto canned."""
    analyzer = ECGAnalyzer(fs=fs)
    result = analyzer.detect_clinical_pattern(signal)
    r_peaks = analyzer.detect_r_peaks(signal)
    rr_intervals = np.diff(r_peaks) / fs if len(r_peaks) > 1 else np.array([])

    shap_lime = None
    note = None
    unavailable = {}
    if len(rr_intervals) >= MIN_RR_INTERVALS_FOR_EXPLAINABILITY:
        try:
            frequencies, power_spectrum = compute_psd(rr_intervals)
            hrv_features = extract_features(rr_intervals, power_spectrum, frequencies)
            shap_lime = generate_shap_lime_report(hrv_features, pattern_label_es(result["pattern"]))
            unavailable = {label: UNRELIABLE_MOMENT_REASON for key, label in (("Skewness", "Asimetría de RR"),
                                                                             ("Kurtosis", "Curtosis de RR"))
                           if np.isnan(hrv_features.get(key, 0.0))}
        except Exception as exc:  # cálculo real que puede fallar con datos límite — no fabricar respaldo
            note = f"No se pudo calcular la explicación por contribución: {exc}"
    else:
        note = (
            f"Se detectaron {len(r_peaks)} picos R ({len(rr_intervals)} intervalos RR) — se "
            f"necesitan al menos {MIN_RR_INTERVALS_FOR_EXPLAINABILITY + 1} picos para calcular "
            f"la explicación por contribución."
        )

    return EcgClassificationResult(
        pattern=result["pattern"],
        reasoning=result["reasoning"],
        features=result["features"],
        r_peak_count=len(r_peaks),
        shap_lime=shap_lime,
        explainability_note=note,
        unavailable_features=unavailable,
    )
