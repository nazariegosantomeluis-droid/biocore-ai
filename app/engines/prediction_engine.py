"""
BIOCORE AI — Prediction Engine

Motor predictivo fisiológico.
Estima riesgos multisistémicos:
- Riesgo cardiovascular
- Riesgo respiratorio
- Riesgo neurológico
- Riesgo muscular
- Riesgo autonómico
- Riesgo global

Frente cardiovascular, Fase 1 (2026-11-12, Art. I): el motor NO evalúa con valores por defecto. Cada factor se evalúa solo
si su entrada LLEGÓ; un sistema sin ninguna entrada es «sin dato», nunca «BAJO / monitoreo rutinario». Decisión 4 firmada
por Luis: el riesgo cardiovascular son los puntos NEWS2 del pulso (`clinical.calculators.news2_pulse_score`); se purgaron
los umbrales caseros 40/140, 50/120, HRV 10/25 y complexity < 30 (y la `complexity` misma: decisión 2).
"""

import math
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
import numpy as np

from clinical.calculators import news2_pulse_score

NO_DATA = "sin dato"


def _num(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


@dataclass
class RiskAssessment:
    """Evaluación de riesgo para un sistema.

    Sin campo `confidence` (retirado 2026-08-14, Art. I -- confianza simulada). Fase 1 (2026-11-12): `risk_score` es
    `None` cuando el sistema no tiene datos («sin dato», `risk_level == "sin dato"`); el sistema cardiovascular no usa la
    escala 0-100 sino los puntos NEWS2 del pulso (`news2_points`, 0-3), con `risk_score = None`."""
    system_name: str
    risk_score: Optional[float]  # 0-100; None = sin dato (o cardiovascular: ver news2_points)
    risk_level: str  # BAJO, MODERADO, ALTO, CRÍTICO, o «sin dato» / «NEWS2 pulso: N punto(s)» (cardiovascular)
    key_factors: List[Tuple[str, float]]  # [(factor, weight), ...]
    recommendation: str
    estimated_time_to_critical: Optional[int] = None  # minutos
    news2_points: Optional[int] = None  # solo cardiovascular: puntos NEWS2 del pulso

    @property
    def has_data(self) -> bool:
        return self.risk_score is not None or self.news2_points is not None


@dataclass
class GlobalRiskAssessment:
    """Evaluación de riesgo global del organismo. `global_risk_score` es `None` si falta un sistema del que depende o si
    alguno no está en la escala 0-100 (`reason` lo dice); nunca se promedian sistemas sin datos."""
    timestamp: str
    global_risk_score: Optional[float]  # 0-100, o None = sin dato
    risk_level: str  # BAJO, MODERADO, ALTO, CRÍTICO, o «sin dato»
    system_risks: Dict[str, RiskAssessment]
    critical_systems: List[str]
    immediate_actions: List[str]
    monitoring_frequency: str  # hourly, every_4h, daily, weekly, o «sin dato»
    reason: str = ""


def _no_data(system_name: str, missing: str) -> RiskAssessment:
    return RiskAssessment(
        system_name=system_name, risk_score=None, risk_level=NO_DATA, key_factors=[],
        recommendation=f"{NO_DATA}: no llegó ninguna entrada ({missing}); el sistema no se evalúa.",
    )


class PredictionEngine:
    """Motor de predicción de riesgos fisiológicos"""

    # Umbrales críticos de los sistemas NO cardiovasculares (el cardiovascular usa NEWS2 de pulso, sin umbrales propios).
    CRITICAL_THRESHOLDS = {
        "respiratory": {
            "spo2_low": 90,
            "respiratory_rate_high": 35,
            "respiratory_rate_low": 8,
            "ahi_high": 30,
        },
        "neurological": {
            "stress_level_high": 85,
            "cognitive_state_low": 20,
            "eeg_abnormality": 80,
        },
        "muscular": {
            "fatigue_index_high": 90,
            "activation_critical": 95,
        },
        "autonomic": {
            "hrv_low": 15,
            "parasympathetic_low": 10,
        },
    }

    def __init__(self):
        self.risk_history: List[GlobalRiskAssessment] = []
        self.prediction_models: Dict = {}

    def assess_cardiovascular_risk(self, ecg_data: Dict[str, float]) -> RiskAssessment:
        """Riesgo cardiovascular = puntos NEWS2 del pulso (decisión 4; RCP 2017, `news2_pulse_score`). Su única entrada es
        `heart_rate`; sin ella, «sin dato». No es un diagnóstico ni indica una conducta por sí solo."""
        hr = ecg_data.get("heart_rate")
        if not _num(hr):
            return _no_data("Cardiovascular", "heart_rate")
        points = news2_pulse_score(float(hr))
        return RiskAssessment(
            system_name="Cardiovascular",
            risk_score=None,
            risk_level=f"NEWS2 pulso: {points} punto(s)",
            key_factors=[("Pulso (NEWS2, RCP 2017)", float(points))],
            recommendation="Componente de pulso del puntaje NEWS2 (0-3 puntos); un solo componente, sin conducta asociada.",
            news2_points=points,
        )

    def assess_respiratory_risk(self, resp_data: Dict[str, float]) -> RiskAssessment:
        """Evalúa riesgo respiratorio; cada factor exige su entrada (spo2, respiratory_rate, ahi)."""
        spo2, rr, ahi = resp_data.get("spo2"), resp_data.get("respiratory_rate"), resp_data.get("ahi")
        if not any(_num(v) for v in (spo2, rr, ahi)):
            return _no_data("Respiratory", "spo2, respiratory_rate, ahi")

        risk_score = 0.0
        factors = []

        # Factor 1: SpO2 bajo
        if _num(spo2):
            if spo2 < 90:
                risk_score += 50
                factors.append(("Hipoxemia severa", 50))
            elif spo2 < 95:
                risk_score += 30
                factors.append(("Hipoxemia moderada", 30))

        # Factor 2: RR extrema
        if _num(rr):
            if rr < 8 or rr > 35:
                risk_score += 35
                factors.append(("Frecuencia respiratoria extrema", 35))
            elif rr < 12 or rr > 25:
                risk_score += 15
                factors.append(("Frecuencia respiratoria anormal", 15))

        # Factor 3: AHI alto (apnea)
        if _num(ahi):
            if ahi > 30:
                risk_score += 30
                factors.append(("Apnea severa", 30))
            elif ahi > 15:
                risk_score += 20
                factors.append(("Apnea moderada", 20))

        # Nivel de riesgo
        if risk_score >= 70:
            risk_level = "CRÍTICO"
            time_to_critical = 15
        elif risk_score >= 50:
            risk_level = "ALTO"
            time_to_critical = 60
        elif risk_score >= 30:
            risk_level = "MODERADO"
            time_to_critical = None
        else:
            risk_level = "BAJO"
            time_to_critical = None

        # Recomendación
        if risk_score >= 70:
            recommendation = "⚠️ CRÍTICO: Suplemento de oxígeno, asegurar vía aérea, considerar ventilación"
        elif risk_score >= 50:
            recommendation = "⚠️ ALTO: Oxígeno, gasometría, evaluación neumológica urgente"
        elif risk_score >= 30:
            recommendation = "⚠️ MODERADO: Oxígeno si es necesario, test de sleep apnea si es indicado"
        else:
            recommendation = "✓ BAJO: sin factores de riesgo en las entradas disponibles"

        return RiskAssessment(
            system_name="Respiratory",
            risk_score=min(100, risk_score),
            risk_level=risk_level,
            key_factors=factors,
            recommendation=recommendation,
            estimated_time_to_critical=time_to_critical,
        )

    def assess_neurological_risk(self, eeg_data: Dict[str, float]) -> RiskAssessment:
        """Evalúa riesgo neurológico; cada factor exige su entrada (stress_level, cognitive_state, relaxation_level)."""
        stress_level = eeg_data.get("stress_level")
        cognitive_state = eeg_data.get("cognitive_state")
        relaxation = eeg_data.get("relaxation_level")
        if not any(_num(v) for v in (stress_level, cognitive_state, relaxation)):
            return _no_data("Neurological", "stress_level, cognitive_state, relaxation_level")

        risk_score = 0.0
        factors = []

        # Factor 1: Estrés muy alto
        if _num(stress_level):
            if stress_level > 80:
                risk_score += 35
                factors.append(("Estrés severo", 35))
            elif stress_level > 60:
                risk_score += 20
                factors.append(("Estrés moderado-alto", 20))

        # Factor 2: Cognición deteriorada
        if _num(cognitive_state):
            if cognitive_state < 20:
                risk_score += 40
                factors.append(("Alteración cognitiva severa", 40))
            elif cognitive_state < 40:
                risk_score += 25
                factors.append(("Alteración cognitiva moderada", 25))

        # Factor 3: Falta de relajación
        if _num(relaxation) and relaxation < 20:
            risk_score += 20
            factors.append(("Incapacidad para relajarse", 20))

        # Nivel de riesgo
        if risk_score >= 70:
            risk_level = "CRÍTICO"
        elif risk_score >= 50:
            risk_level = "ALTO"
        elif risk_score >= 30:
            risk_level = "MODERADO"
        else:
            risk_level = "BAJO"

        # Recomendación
        if risk_score >= 70:
            recommendation = "⚠️ CRÍTICO: Evaluación psiquiátrica/neurológica urgente, medicación si es indicada"
        elif risk_score >= 50:
            recommendation = "⚠️ ALTO: Apoyo psicológico, técnicas de relajación, evaluación especializada"
        elif risk_score >= 30:
            recommendation = "⚠️ MODERADO: Manejo del estrés, mindfulness, seguimiento psicológico"
        else:
            recommendation = "✓ BAJO: sin factores de riesgo en las entradas disponibles"

        return RiskAssessment(
            system_name="Neurological",
            risk_score=min(100, risk_score),
            risk_level=risk_level,
            key_factors=factors,
            recommendation=recommendation,
        )

    def assess_muscular_risk(self, emg_data: Dict[str, float]) -> RiskAssessment:
        """Evalúa riesgo muscular; cada factor exige su entrada (fatigue_index, efficiency, activation)."""
        fatigue = emg_data.get("fatigue_index")
        activation = emg_data.get("activation")
        efficiency = emg_data.get("efficiency")
        if not any(_num(v) for v in (fatigue, activation, efficiency)):
            return _no_data("Muscular", "fatigue_index, efficiency, activation")

        risk_score = 0.0
        factors = []

        # Factor 1: Fatiga severa
        if _num(fatigue):
            if fatigue > 80:
                risk_score += 40
                factors.append(("Fatiga severa", 40))
            elif fatigue > 60:
                risk_score += 20
                factors.append(("Fatiga moderada", 20))

        # Factor 2: Baja eficiencia
        if _num(efficiency):
            if efficiency < 30:
                risk_score += 35
                factors.append(("Eficiencia muscular muy baja", 35))
            elif efficiency < 50:
                risk_score += 20
                factors.append(("Eficiencia muscular baja", 20))

        # Factor 3: Sobrecarga
        if _num(activation) and activation > 90:
            risk_score += 25
            factors.append(("Sobrecarga muscular", 25))

        # Nivel de riesgo
        if risk_score >= 70:
            risk_level = "ALTO"
        elif risk_score >= 40:
            risk_level = "MODERADO"
        else:
            risk_level = "BAJO"

        # Recomendación
        if risk_score >= 70:
            recommendation = "⚠️ ALTO: Reposo obligatorio, fisioterapia, valorar sobreentrenamiento"
        elif risk_score >= 40:
            recommendation = "⚠️ MODERADO: Reducir actividad, estiramientos, monitoreo"
        else:
            recommendation = "✓ BAJO: sin factores de riesgo en las entradas disponibles"

        return RiskAssessment(
            system_name="Muscular",
            risk_score=min(100, risk_score),
            risk_level=risk_level,
            key_factors=factors,
            recommendation=recommendation,
        )

    def assess_autonomic_risk(self, organism) -> RiskAssessment:
        """Evalúa riesgo autonómico: exige la HRV (corazón) y/o el índice del cerebro, ambos ACTUALES. Sin ninguno,
        «sin dato» (antes `hrv = 50` y `brain.health = 50` por defecto daban «Balance autonómico adecuado»)."""
        hrv = organism.current_signals("heart").get("hrv")
        brain_health = (
            organism.organs["brain"].metrics.health_score if organism.inputs_are_current("brain") else None
        )
        if not _num(hrv) and brain_health is None:
            return _no_data("Autonomic", "hrv, índice cerebral")

        risk_score = 0.0
        factors = []

        # Factor 1: HRV baja (parasimpático bajo)
        if _num(hrv):
            if hrv < 15:
                risk_score += 40
                factors.append(("Variabilidad cardíaca muy baja", 40))
            elif hrv < 30:
                risk_score += 25
                factors.append(("Variabilidad cardíaca baja", 25))

        # Factor 2: Estrés crónico
        if brain_health is not None:
            stress = 100 - brain_health
            if stress > 70:
                risk_score += 35
                factors.append(("Estrés simpático dominante", 35))
            elif stress > 50:
                risk_score += 20
                factors.append(("Estrés moderado", 20))

        # Nivel de riesgo
        if risk_score >= 60:
            risk_level = "ALTO"
        elif risk_score >= 35:
            risk_level = "MODERADO"
        else:
            risk_level = "BAJO"

        # Recomendación
        if risk_score >= 60:
            recommendation = "⚠️ ALTO: Activación parasimpática (respiración, meditación), medicación si indicada"
        elif risk_score >= 35:
            recommendation = "⚠️ MODERADO: Técnicas de relajación, yoga, terapia del estrés"
        else:
            recommendation = "✓ BAJO: sin factores de riesgo en las entradas disponibles"

        return RiskAssessment(
            system_name="Autonomic",
            risk_score=min(100, risk_score),
            risk_level=risk_level,
            key_factors=factors,
            recommendation=recommendation,
        )

    def assess_global_risk(
        self,
        organism,
        sensor_data: Dict[str, Dict[str, float]],
        timestamp: str,
    ) -> GlobalRiskAssessment:
        """Evalúa el riesgo global del organismo. El número global solo existe si los 5 sistemas tienen riesgo en la
        escala 0-100; si falta alguno, o el cardiovascular está en puntos NEWS2 (otra escala), es «sin dato» y `reason`
        dice por qué. Prohibido promediar sistemas sin datos o de escalas distintas."""

        # Evaluar cada sistema
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

        expected = {"cardiovascular", "respiratory", "neurological", "muscular", "autonomic"}
        missing = sorted(expected - set(system_risks))
        no_data = sorted(n for n, r in system_risks.items() if not r.has_data)
        other_scale = sorted(n for n, r in system_risks.items() if r.has_data and r.risk_score is None)
        if missing or no_data or other_scale:
            global_risk_score = None
            parts = []
            if missing or no_data:
                parts.append("sin dato en: " + ", ".join(missing + no_data))
            if other_scale:
                parts.append("escala distinta (puntos NEWS2, no 0-100) en: " + ", ".join(other_scale))
            reason = "; ".join(parts)
        else:
            global_risk_score = float(np.mean([r.risk_score for r in system_risks.values()]))
            reason = ""

        critical_systems = [
            name for name, risk in system_risks.items()
            if risk.risk_level in ["CRÍTICO", "ALTO"]
        ]

        if global_risk_score is None:
            risk_level, monitoring_frequency = NO_DATA, NO_DATA
        elif global_risk_score >= 70:
            risk_level, monitoring_frequency = "CRÍTICO", "every_15min"
        elif global_risk_score >= 50:
            risk_level, monitoring_frequency = "ALTO", "hourly"
        elif global_risk_score >= 30:
            risk_level, monitoring_frequency = "MODERADO", "every_4h"
        else:
            risk_level, monitoring_frequency = "BAJO", "daily"

        # Acciones inmediatas
        immediate_actions = []
        for system_name, risk in system_risks.items():
            if risk.risk_level == "CRÍTICO":
                immediate_actions.append(f"[CRÍTICO] {system_name}: {risk.recommendation}")
            elif risk.risk_level == "ALTO":
                immediate_actions.append(f"[ALTO] {system_name}: {risk.recommendation}")

        assessment = GlobalRiskAssessment(
            timestamp=timestamp,
            global_risk_score=None if global_risk_score is None else float(np.clip(global_risk_score, 0, 100)),
            risk_level=risk_level,
            system_risks=system_risks,
            critical_systems=critical_systems,
            immediate_actions=immediate_actions,
            monitoring_frequency=monitoring_frequency,
            reason=reason,
        )

        # Agregar a historia
        self.risk_history.append(assessment)
        if len(self.risk_history) > 500:
            self.risk_history.pop(0)

        return assessment

    def predict_decompensation_risk(self, organism) -> Optional[float]:
        """Predice probabilidad de descompensación en próximas 2 horas (0-100%); `None` sin dos riesgos globales reales."""
        scored = [a.global_risk_score for a in self.risk_history if a.global_risk_score is not None]
        if len(scored) < 2:
            return None
        recent_risk, previous_risk = scored[-1], scored[-2]
        risk_trend = recent_risk - previous_risk  # Positivo = empeorando

        # Extrapolación simple
        decompensation_probability = recent_risk + (risk_trend * 2)
        return float(np.clip(decompensation_probability, 0, 100))
