"""Blood pressure academy: classes and helpers to represent BP states."""
from __future__ import annotations
from typing import Tuple, Dict


def classify_bp(systolic: float, diastolic: float) -> str:
    """Return an educational BP category following common clinical thresholds."""
    if systolic < 90 or diastolic < 60:
        return 'Hipotensión'
    if systolic < 120 and diastolic < 80:
        return 'Normal'
    if systolic < 130 and diastolic < 80:
        return 'Elevada'
    if systolic < 140 or diastolic < 90:
        return 'Hipertensión etapa 1'
    if systolic >= 140 or diastolic >= 90:
        return 'Hipertensión etapa 2'
    return 'Desconocido'


def mean_arterial_pressure(systolic: float, diastolic: float) -> float:
    return float(diastolic + (systolic - diastolic) / 3.0)
