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
"""

from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import numpy as np


@dataclass
class RiskAssessment:
    """Evaluación de riesgo para un sistema.

    Sin campo `confidence` (retirado 2026-08-14, Art. I -- confianza
    simulada): las 5 llamadas de `assess_*_risk()` devolvían un float fijo
    por sistema (0.85/0.90/0.80/0.75/0.82) que nunca variaba con la señal
    real -- ni un cálculo estadístico ni una métrica del modelo, solo una
    constante con apariencia de medición. Confirmado por grep antes de
    retirarlo: ningún consumidor (`app/supermodules/twin_shell/pages.py::
    render_risk_assessment`, único call site vivo) lo leía -- ni la UI, ni
    ningún cálculo interno de este mismo módulo (`assess_global_risk` agrega
    por `risk_score`, nunca por `confidence`). Mismo patrón ya retirado del
    clasificador ECG. `risk_score`/`risk_level`/`recommendation` (los
    umbrales reales) no cambian -- ver CHANGELOG.md."""
    system_name: str
    risk_score: float  # 0-100
    risk_level: str  # BAJO, MODERADO, ALTO, CRÍTICO
    key_factors: List[Tuple[str, float]]  # [(factor, weight), ...]
    recommendation: str
    estimated_time_to_critical: Optional[int] = None  # minutos


@dataclass
class GlobalRiskAssessment:
    """Evaluación de riesgo global del organismo"""
    timestamp: str
    global_risk_score: float  # 0-100
    risk_level: str  # BAJO, MODERADO, ALTO, CRÍTICO
    system_risks: Dict[str, RiskAssessment]
    critical_systems: List[str]
    immediate_actions: List[str]
    monitoring_frequency: str  # hourly, every_4h, daily, weekly


class PredictionEngine:
    """Motor de predicción de riesgos fisiológicos"""
    
    # Umbrales críticos para cada sistema
    CRITICAL_THRESHOLDS = {
        "cardiovascular": {
            "heart_rate_low": 40,
            "heart_rate_high": 140,
            "hrv_low": 10,
            "cardiac_output_low": 2.5,
        },
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
        """Evalúa riesgo cardiovascular desde ECG"""
        hr = ecg_data.get("heart_rate", 70)
        hrv = ecg_data.get("hrv", 50)
        complexity = ecg_data.get("complexity", 50)
        
        risk_score = 0.0
        factors = []
        
        # Factor 1: HR extremo
        if hr < 40 or hr > 140:
            risk_score += 40
            factors.append(("Frecuencia cardíaca extrema", 40))
        elif hr < 50 or hr > 120:
            risk_score += 20
            factors.append(("Frecuencia cardíaca anormal", 20))
        
        # Factor 2: HRV bajo
        if hrv < 10:
            risk_score += 35
            factors.append(("HRV muy baja (riesgo de arritmia)", 35))
        elif hrv < 25:
            risk_score += 20
            factors.append(("HRV baja", 20))
        
        # Factor 3: Complejidad cardíaca
        if complexity < 30:
            risk_score += 25
            factors.append(("Complejidad cardíaca disminuida", 25))
        
        # Determinar nivel de riesgo
        if risk_score >= 70:
            risk_level = "CRÍTICO"
            time_to_critical = 30
        elif risk_score >= 50:
            risk_level = "ALTO"
            time_to_critical = 120
        elif risk_score >= 30:
            risk_level = "MODERADO"
            time_to_critical = None
        else:
            risk_level = "BAJO"
            time_to_critical = None
        
        # Recomendación
        if risk_score >= 70:
            recommendation = "⚠️ CRÍTICO: Activar ECG 12-derivaciones, troponinas, considerar unidad de cuidados intensivos"
        elif risk_score >= 50:
            recommendation = "⚠️ ALTO: Monitoreo continuo, EKG seriados, valoración cardiológica urgente"
        elif risk_score >= 30:
            recommendation = "⚠️ MODERADO: Monitoreo frecuente, EKG, evaluación clínica"
        else:
            recommendation = "✓ BAJO: Monitoreo rutinario, educación en factores de riesgo"
        
        return RiskAssessment(
            system_name="Cardiovascular",
            risk_score=min(100, risk_score),
            risk_level=risk_level,
            key_factors=factors,
            recommendation=recommendation,
            estimated_time_to_critical=time_to_critical,
        )
    
    def assess_respiratory_risk(self, resp_data: Dict[str, float]) -> RiskAssessment:
        """Evalúa riesgo respiratorio"""
        spo2 = resp_data.get("spo2", 98)
        rr = resp_data.get("respiratory_rate", 16)
        ahi = resp_data.get("ahi", 0)
        
        risk_score = 0.0
        factors = []
        
        # Factor 1: SpO2 bajo
        if spo2 < 90:
            risk_score += 50
            factors.append(("Hipoxemia severa", 50))
        elif spo2 < 95:
            risk_score += 30
            factors.append(("Hipoxemia moderada", 30))
        
        # Factor 2: RR extrema
        if rr < 8 or rr > 35:
            risk_score += 35
            factors.append(("Frecuencia respiratoria extrema", 35))
        elif rr < 12 or rr > 25:
            risk_score += 15
            factors.append(("Frecuencia respiratoria anormal", 15))
        
        # Factor 3: AHI alto (apnea)
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
            recommendation = "✓ BAJO: Monitoreo rutinario de SpO2"
        
        return RiskAssessment(
            system_name="Respiratory",
            risk_score=min(100, risk_score),
            risk_level=risk_level,
            key_factors=factors,
            recommendation=recommendation,
            estimated_time_to_critical=time_to_critical,
        )
    
    def assess_neurological_risk(self, eeg_data: Dict[str, float]) -> RiskAssessment:
        """Evalúa riesgo neurológico"""
        stress_level = eeg_data.get("stress_level", 35)
        cognitive_state = eeg_data.get("cognitive_state", 75)
        relaxation = eeg_data.get("relaxation_level", 65)
        
        risk_score = 0.0
        factors = []
        
        # Factor 1: Estrés muy alto
        if stress_level > 80:
            risk_score += 35
            factors.append(("Estrés severo", 35))
        elif stress_level > 60:
            risk_score += 20
            factors.append(("Estrés moderado-alto", 20))
        
        # Factor 2: Cognición deteriorada
        if cognitive_state < 20:
            risk_score += 40
            factors.append(("Alteración cognitiva severa", 40))
        elif cognitive_state < 40:
            risk_score += 25
            factors.append(("Alteración cognitiva moderada", 25))
        
        # Factor 3: Falta de relajación
        if relaxation < 20:
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
            recommendation = "✓ BAJO: Mantener técnicas de relajación"
        
        return RiskAssessment(
            system_name="Neurological",
            risk_score=min(100, risk_score),
            risk_level=risk_level,
            key_factors=factors,
            recommendation=recommendation,
        )
    
    def assess_muscular_risk(self, emg_data: Dict[str, float]) -> RiskAssessment:
        """Evalúa riesgo muscular"""
        fatigue = emg_data.get("fatigue_index", 20)
        activation = emg_data.get("activation", 45)
        efficiency = emg_data.get("efficiency", 70)
        
        risk_score = 0.0
        factors = []
        
        # Factor 1: Fatiga severa
        if fatigue > 80:
            risk_score += 40
            factors.append(("Fatiga severa", 40))
        elif fatigue > 60:
            risk_score += 20
            factors.append(("Fatiga moderada", 20))
        
        # Factor 2: Baja eficiencia
        if efficiency < 30:
            risk_score += 35
            factors.append(("Eficiencia muscular muy baja", 35))
        elif efficiency < 50:
            risk_score += 20
            factors.append(("Eficiencia muscular baja", 20))
        
        # Factor 3: Sobrecarga
        if activation > 90:
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
            recommendation = "✓ BAJO: Actividad normal con descanso adecuado"
        
        return RiskAssessment(
            system_name="Muscular",
            risk_score=min(100, risk_score),
            risk_level=risk_level,
            key_factors=factors,
            recommendation=recommendation,
        )
    
    def assess_autonomic_risk(self, organism) -> RiskAssessment:
        """Evalúa riesgo autonómico"""
        heart = organism.get_organ("heart")
        brain = organism.get_organ("brain")
        
        hrv = heart.metrics.signals.get("hrv", 50)
        stress = 100 - brain.metrics.health_score
        
        risk_score = 0.0
        factors = []
        
        # Factor 1: HRV baja (parasimpático bajo)
        if hrv < 15:
            risk_score += 40
            factors.append(("Variabilidad cardíaca muy baja", 40))
        elif hrv < 30:
            risk_score += 25
            factors.append(("Variabilidad cardíaca baja", 25))
        
        # Factor 2: Estrés crónico
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
            recommendation = "✓ BAJO: Balance autonómico adecuado"
        
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
        """Evalúa riesgo global del organismo"""
        
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
        
        # Calcular riesgo global
        risk_scores = [r.risk_score for r in system_risks.values()]
        global_risk_score = np.mean(risk_scores) if risk_scores else 50.0
        
        # Identificar sistemas críticos
        # Fase 1 (idioma, 2026-08-30): risk_level ahora es CRÍTICO/ALTO/
        # MODERADO/BAJO (antes Critical/High/Medium/Low) -- unificado con el
        # vocabulario que `DigitalTwinOrganism._compute_risk_level()` ya usa,
        # para que la misma página de Twin OS no muestre dos idiomas de
        # riesgo distintos. Esta comparación se actualizó en el mismo cambio
        # -- ver CHANGELOG.md.
        critical_systems = [
            name for name, risk in system_risks.items()
            if risk.risk_level in ["CRÍTICO", "ALTO"]
        ]

        # Determinar nivel de riesgo global
        if global_risk_score >= 70:
            risk_level = "CRÍTICO"
            monitoring_frequency = "every_15min"
        elif global_risk_score >= 50:
            risk_level = "ALTO"
            monitoring_frequency = "hourly"
        elif global_risk_score >= 30:
            risk_level = "MODERADO"
            monitoring_frequency = "every_4h"
        else:
            risk_level = "BAJO"
            monitoring_frequency = "daily"

        # Acciones inmediatas
        immediate_actions = []
        for system_name, risk in system_risks.items():
            if risk.risk_level == "CRÍTICO":
                immediate_actions.append(f"[CRÍTICO] {system_name}: {risk.recommendation}")
            elif risk.risk_level == "ALTO":
                immediate_actions.append(f"[ALTO] {system_name}: {risk.recommendation}")
        
        assessment = GlobalRiskAssessment(
            timestamp=timestamp,
            global_risk_score=float(np.clip(global_risk_score, 0, 100)),
            risk_level=risk_level,
            system_risks=system_risks,
            critical_systems=critical_systems,
            immediate_actions=immediate_actions,
            monitoring_frequency=monitoring_frequency,
        )
        
        # Agregar a historia
        self.risk_history.append(assessment)
        if len(self.risk_history) > 500:
            self.risk_history.pop(0)
        
        return assessment
    
    def predict_decompensation_risk(self, organism) -> float:
        """Predice probabilidad de descompensación en próximas 2 horas (0-100%)"""
        # Basado en tendencias de riesgo
        if len(self.risk_history) < 2:
            return 0.0
        
        recent_risk = self.risk_history[-1].global_risk_score
        previous_risk = self.risk_history[-2].global_risk_score
        risk_trend = recent_risk - previous_risk  # Positivo = empeorando
        
        # Extrapolación simple
        decompensation_probability = recent_risk + (risk_trend * 2)
        return float(np.clip(decompensation_probability, 0, 100))
