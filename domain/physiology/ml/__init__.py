"""
Tanda 4 (2026-07-04) — Puentes entre el UPS y modelos de ML reales que
antes vivían huérfanos (alcanzables solo con datos de paciente hardcodeados
en app/pages_legacy/4_👥_Patients.py, ya archivado).

Mismo espíritu que `domain/physiology/narrator/`: leen el UPS (nunca lo
reescriben), nunca inventan un valor que el UPS no tenga.
"""

from .ecg_classification import EcgClassificationResult, classify_ecg_signal
from .ecg_signal_source import SyntheticEcgResult, build_synthetic_ecg_from_ups
from .risk_context import RiskFeatures, build_risk_features

__all__ = [
    "RiskFeatures",
    "build_risk_features",
    "SyntheticEcgResult",
    "build_synthetic_ecg_from_ups",
    "EcgClassificationResult",
    "classify_ecg_signal",
]
