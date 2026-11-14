"""Eje eléctrico del QRS (fuente única de la fórmula).

2026-11-14 (Art. I): aquí vivía también `TwelveLeadEcgAnalyzer`, la «interpretación automática» de la
pestaña 12 Derivaciones. No medía la duración del QRS (daba bloqueo de rama izquierda si la R de I pasaba
de 1.2 mV y derecha si más de 50 muestras de V1 cambiaban más de 0.1), medía el «ST» donde la señal tenía
menos amplitud, buscaba la «Q patológica» en el primer tercio del registro y calculaba el eje con la media
de todo el registro. La reemplazó `src/signals/ecg/twelve_lead_measure.py` (mide sobre el latido mediano y
compara con criterios citados) y se retiró; ver CHANGELOG.md. Queda la fórmula del eje, que también usa la
calculadora (`clinical/calculators.py`).
"""

from dataclasses import dataclass

import numpy as np


@dataclass
class QrsAxis:
    """QRS axis determination result"""
    axis_degrees: float
    category: str  # "Normal", "LAD", "RAD", "Extreme" (-90 a ±180, eje indeterminado), "Unknown"
    description: str


def qrs_axis_from_net(lead_i_net: float, avf_net: float) -> QrsAxis:
    """
    Eje eléctrico medio en el plano frontal, desde la amplitud/área NETA de I y aVF.

    Fuente única (Tanda 2C, 2026-10-24): la usan `_determine_qrs_axis` (ECG-12)
    y la calculadora de eje (`clinical/calculators.py`). No dupliques la fórmula.

    Corregido 2026-10-22: antes `atan2(aVF, I)`, ahora `atan2(2·aVF, √3·I)`.
    Con un vector cardíaco de módulo E y ángulo θ (0° = I, +90° = aVF),
    Einthoven da I = E·cos θ, II = E·cos(θ − 60°), III = E·cos(θ − 120°),
    y Goldberger aVF = (II + III)/2 = (√3/2)·E·sen θ. I y aVF son
    perpendiculares pero NO tienen la misma escala: aVF mide √3/2 de lo
    que mediría una derivación como I a 90°. Por eso tan θ = 2·aVF/(√3·I).
    La fórmula vieja comprimía el ángulo hacia 0°/±180°: un eje real entre
    −30° y −33.7° (desviación izquierda) salía "normal".

    Zonas: normal −30° a +90°; desviación izquierda −30° a −90°; derecha
    +90° a +180°; −90° a ±180°, desviación extrema (eje indeterminado).
    """
    axis_deg = float(np.degrees(np.arctan2(2.0 * avf_net, np.sqrt(3.0) * lead_i_net)))  # [-180, 180]

    if -30 <= axis_deg <= 90:
        category = "Normal"
        description = f"Normal axis: {axis_deg:.0f}°"
    elif -90 <= axis_deg < -30:
        category = "LAD"
        description = f"Left Axis Deviation: {axis_deg:.0f}°"
    elif axis_deg > 90:
        category = "RAD"
        description = f"Right Axis Deviation: {axis_deg:.0f}°"
    else:  # -180 a -90: antes salía "LAD", pero no es desviación izquierda
        category = "Extreme"
        description = f"Extreme axis deviation (indeterminate axis): {axis_deg:.0f}°"

    return QrsAxis(axis_degrees=axis_deg, category=category, description=description)
