"""
BIOCORE AI — Prediction Engine

Evaluación por sistema de lo que se puede decir CON FUENTE a partir de las señales actuales del organismo.

Frente cardiovascular, Fase 1 (2026-11-12, Art. I): el motor NO evalúa con valores por defecto; un sistema sin ninguna
entrada es «sin dato», nunca «BAJO / monitoreo rutinario». Decisión 4: el riesgo cardiovascular son los puntos NEWS2 del
pulso (`clinical.calculators.news2_pulse_score`); se purgaron los umbrales caseros 40/140, 50/120, HRV 10/25 y
complexity < 30.

Cierre de la fase 0 (2026-11-13, Art. I; decisiones 1, 2 y 6 de Luis): se retiraron TODOS los umbrales propios no
cardiacos (SpO₂ 90/95, FR 8/35 y 12/25, AHI 15/30, estrés 60/80, cognición 20/40, relajación 20, fatiga 60/80,
eficiencia 30/50, activación 90, HRV 15/30) y las escalas 0-100 que los sumaban. Lo que queda tiene fuente:
- cardiovascular = puntos NEWS2 del pulso; respiratorio = puntos NEWS2 de la FR y de la SpO₂ (escala 1);
- neurológico, muscular y autonómico: la plataforma no tiene un criterio con fuente que los puntúe -> «sin criterio con
  fuente», se declara y no se evalúa (aunque haya entradas);
- el riesgo global ya no es un número: es el NEWS2 PARCIAL (componentes disponibles + lo que falta para el total, nunca
  un total). La extrapolación del riesgo global 0-100 a 2 horas se enterró con él.
"""

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from clinical.calculators import (
    NEWS2_CITATION,
    News2Partial,
    news2_partial,
    news2_pulse_score,
    news2_respiratory_rate_score,
    news2_spo2_scale1_score,
)

NO_DATA = "sin dato"
NO_SOURCED_CRITERION = "sin criterio con fuente"


def _num(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


@dataclass
class RiskAssessment:
    """Evaluación de un sistema. `news2_points` = componentes NEWS2 que SÍ se pudieron puntuar (vacío si el sistema no
    tiene criterio con fuente o no llegó su entrada); `risk_level` es el texto que se muestra."""
    system_name: str
    risk_level: str  # «NEWS2 pulso: N punto(s)», «sin dato» o «sin criterio con fuente»
    recommendation: str
    news2_points: Dict[str, int] = field(default_factory=dict)
    key_factors: List[Tuple[str, float]] = field(default_factory=list)

    @property
    def has_data(self) -> bool:
        return bool(self.news2_points)


@dataclass
class GlobalRiskAssessment:
    """Riesgo global del organismo = NEWS2 PARCIAL (decisión 2). Sin total, sin categoría, sin frecuencia de
    monitoreo: un NEWS2 parcial no es un NEWS2. `reason` dice qué falta."""
    timestamp: str
    news2_partial: News2Partial
    system_risks: Dict[str, RiskAssessment]
    reason: str


def _no_data(system_name: str, missing: str) -> RiskAssessment:
    return RiskAssessment(
        system_name=system_name, risk_level=NO_DATA,
        recommendation=f"{NO_DATA}: no llegó ninguna entrada ({missing}); el sistema no se evalúa.",
    )


def _no_criterion(system_name: str, measured: str) -> RiskAssessment:
    return RiskAssessment(
        system_name=system_name, risk_level=NO_SOURCED_CRITERION,
        recommendation=(
            f"{NO_SOURCED_CRITERION}: la plataforma no tiene una escala publicada que puntúe este sistema; lo medido "
            f"({measured}) se muestra como lo que es, sin nivel de riesgo (los umbrales propios se retiraron, fase 0)."
        ),
    )


class PredictionEngine:
    """Evaluación por sistema con fuente; nada de umbrales propios."""

    def __init__(self):
        self.risk_history: List[GlobalRiskAssessment] = []

    def assess_cardiovascular_risk(self, ecg_data: Dict[str, float]) -> RiskAssessment:
        """Riesgo cardiovascular = puntos NEWS2 del pulso (decisión 4; RCP 2017, `news2_pulse_score`). Su única entrada es
        `heart_rate`; sin ella, «sin dato». No es un diagnóstico ni indica una conducta por sí solo."""
        hr = ecg_data.get("heart_rate")
        if not _num(hr):
            return _no_data("Cardiovascular", "heart_rate")
        points = news2_pulse_score(float(hr))
        return RiskAssessment(
            system_name="Cardiovascular",
            risk_level=f"NEWS2 pulso: {points} punto(s)",
            recommendation="Componente de pulso del puntaje NEWS2 (0-3 puntos); un solo componente, sin conducta asociada.",
            news2_points={"Pulso": points},
            key_factors=[("Pulso (NEWS2, RCP 2017)", float(points))],
        )

    def assess_respiratory_risk(self, resp_data: Dict[str, float]) -> RiskAssessment:
        """Riesgo respiratorio = puntos NEWS2 de la FR y de la SpO₂ (escala 1), cada uno con su única entrada (decisión
        6). El AHI no tiene componente NEWS2: no se puntúa. La escala 2 de SpO₂ no se modela."""
        rr, spo2 = resp_data.get("respiratory_rate"), resp_data.get("spo2")
        points: Dict[str, int] = {}
        if _num(rr):
            points["Frecuencia respiratoria"] = news2_respiratory_rate_score(math.floor(float(rr) + 0.5))
        if _num(spo2):
            points["SpO₂ (escala 1)"] = news2_spo2_scale1_score(float(spo2))
        if not points:
            return _no_data("Respiratory", "respiratory_rate, spo2")
        label = " · ".join(f"NEWS2 {name}: {p} punto(s)" for name, p in points.items())
        return RiskAssessment(
            system_name="Respiratory",
            risk_level=label,
            recommendation="Componentes de FR y SpO₂ (escala 1) del puntaje NEWS2; sin conducta asociada. Escala 2: no modelada.",
            news2_points=points,
            key_factors=[(f"{name} (NEWS2, RCP 2017)", float(p)) for name, p in points.items()],
        )

    def assess_neurological_risk(self, eeg_data: Dict[str, float]) -> RiskAssessment:
        """Sin criterio con fuente: los umbrales de estrés/cognición/relajación se retiraron (decisión 6)."""
        measured = ", ".join(k for k, v in eeg_data.items() if _num(v))
        return _no_criterion("Neurological", measured) if measured else _no_data("Neurological", "eeg")

    def assess_muscular_risk(self, emg_data: Dict[str, float]) -> RiskAssessment:
        """Sin criterio con fuente: los umbrales de fatiga/eficiencia/activación se retiraron (decisión 6)."""
        measured = ", ".join(k for k, v in emg_data.items() if _num(v))
        return _no_criterion("Muscular", measured) if measured else _no_data("Muscular", "emg")

    def assess_autonomic_risk(self, organism) -> RiskAssessment:
        """Sin criterio con fuente: los umbrales HRV < 15/30 se retiraron (decisión 6). La HRV se muestra como HRV."""
        hrv = organism.current_signals("heart").get("hrv")
        return _no_criterion("Autonomic", "hrv") if _num(hrv) else _no_data("Autonomic", "hrv")

    def assess_global_risk(
        self,
        organism,
        sensor_data: Dict[str, Dict[str, float]],
        timestamp: str,
    ) -> GlobalRiskAssessment:
        """Riesgo global = NEWS2 PARCIAL (decisión 2): puntos por parámetro disponible (pulso, FR, SpO₂) y la lista de
        lo que falta para el total. Nunca un total, nunca un promedio, nunca «BAJO»."""
        system_risks = {}
        if "ecg" in sensor_data:
            system_risks["cardiovascular"] = self.assess_cardiovascular_risk(sensor_data["ecg"])
        if "respiratory" in sensor_data:
            system_risks["respiratory"] = self.assess_respiratory_risk(sensor_data["respiratory"])
        if "eeg" in sensor_data:
            system_risks["neurological"] = self.assess_neurological_risk(sensor_data["eeg"])
        if "emg" in sensor_data:
            system_risks["muscular"] = self.assess_muscular_risk(sensor_data["emg"])
        system_risks["autonomic"] = self.assess_autonomic_risk(organism)

        ecg, resp = sensor_data.get("ecg", {}), sensor_data.get("respiratory", {})
        partial = news2_partial(
            pulse=float(ecg["heart_rate"]) if _num(ecg.get("heart_rate")) else None,
            respiratory_rate=float(resp["respiratory_rate"]) if _num(resp.get("respiratory_rate")) else None,
            spo2=float(resp["spo2"]) if _num(resp.get("spo2")) else None,
        )
        reason = (
            f"NEWS2 parcial, sin total: faltan {', '.join(partial.missing)} ({NEWS2_CITATION})"
            if partial.available else f"{NO_DATA}: sin pulso, FR ni SpO₂ actuales; faltan además {', '.join(partial.missing[-4:])}"
        )
        assessment = GlobalRiskAssessment(
            timestamp=timestamp, news2_partial=partial, system_risks=system_risks, reason=reason,
        )
        self.risk_history.append(assessment)
        if len(self.risk_history) > 500:
            self.risk_history.pop(0)
        return assessment
