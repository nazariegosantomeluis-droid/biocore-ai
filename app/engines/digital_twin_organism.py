"""
BIOCORE AI — Digital Twin Organism

El corazón inteligente de la plataforma.
Representación viva y computacional del cuerpo humano.
Centro absoluto que integra todas las señales biomédicas.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
import json
import numpy as np
from datetime import datetime, timedelta


class OrganHealthStatus(Enum):
    """Estados de salud de órganos"""
    CRITICAL = "critical"
    ALERT = "alert"
    NORMAL = "normal"
    OPTIMAL = "optimal"


@dataclass
class OrganMetrics:
    """Métricas de un órgano/sistema"""
    health_score: float = 50.0  # 0-100
    activity_level: float = 50.0  # 0-100
    risk_score: float = 0.0  # 0-100
    trend: str = "stable"  # rising, stable, falling
    affected_by: List[str] = field(default_factory=list)  # Otros órganos que lo afectan
    affects: List[str] = field(default_factory=list)  # Órganos que afecta
    predictions: Dict[str, float] = field(default_factory=dict)
    signals: Dict[str, float] = field(default_factory=dict)


@dataclass
class CardiacDetail:
    """Detalle cardíaco de alta fidelidad (electrofisiología, hemodinámica)."""
    cardiac_output: float = 5.0  # L/min
    stroke_volume: float = 70.0  # ml
    qrs_duration: float = 0.08  # seg
    pr_interval: float = 0.16  # seg
    qt_interval: float = 0.40  # seg
    rhythm_stability: float = 85.0  # 0-100
    myocardial_stress: float = 30.0  # 0-100
    ventricular_ejection_fraction: float = 60.0  # %
    sa_node_rate: float = 60.0  # bpm
    av_conduction_delay: float = 0.12  # seg


@dataclass
class NeurologicalDetail:
    """Detalle neurológico: actividad cortical regional y estado cognitivo."""
    mental_workload: float = 40.0  # 0-100
    cognitive_fatigue: float = 20.0  # 0-100
    attention: float = 70.0  # 0-100
    stress_perception: float = 30.0  # 0-100
    sleepiness: float = 10.0  # 0-100
    frontal_activity: float = 55.0  # 0-100
    temporal_activity: float = 45.0  # 0-100
    parietal_activity: float = 50.0  # 0-100
    occipital_activity: float = 40.0  # 0-100
    motor_cortex_activation: float = 35.0  # 0-100
    sensory_integration: float = 60.0  # 0-100


@dataclass
class RespiratoryDetail:
    """Detalle respiratorio, incluyendo oxigenación (SpO2/perfusión)."""
    tidal_volume: float = 500.0  # ml
    minute_ventilation: float = 8.0  # L/min
    breathing_pattern: str = "normal"  # normal, shallow, deep, irregular
    apnea_risk: float = 5.0  # 0-100
    hypoxia_risk: float = 10.0  # 0-100
    perfusion_index: float = 85.0  # 0-100
    tissue_oxygenation: float = 80.0  # 0-100
    arterial_oxygen: float = 95.0  # mmHg


@dataclass
class MusculoskeletalDetail:
    """Detalle musculoesquelético: reclutamiento, simetría, eficiencia."""
    recruitment_pattern: float = 50.0  # 0-100
    motor_symmetry: float = 90.0  # 0-100
    neuromuscular_efficiency: float = 80.0  # 0-100
    movement_smoothness: float = 85.0  # 0-100
    power_output: float = 100.0  # % del máximo


@dataclass
class AutonomicDetail:
    """Detalle autonómico: balance simpático/parasimpático y variabilidad."""
    sympathetic_activity: float = 40.0  # 0-100
    parasympathetic_activity: float = 60.0  # 0-100
    autonomic_flexibility: float = 75.0  # 0-100
    lf_hf_ratio: float = 1.5  # Low Freq / High Freq


@dataclass
class StressState:
    """Estado de respuesta al estrés (transversal, no un órgano anatómico)."""
    cortisol_level: float = 10.0  # μg/dL
    acute_stress: float = 20.0  # 0-100
    chronic_stress: float = 35.0  # 0-100
    inflammatory_markers: float = 40.0  # 0-100


@dataclass
class RecoveryState:
    """Capacidad de recuperación (transversal)."""
    recovery_capacity: float = 75.0  # 0-100
    metabolic_recovery: float = 70.0  # 0-100
    circadian_alignment: float = 80.0  # 0-100


@dataclass
class SleepState:
    """Estado del sueño (transversal)."""
    sleep_stage: str = "awake"  # awake, N1, N2, N3, REM
    sleep_quality: float = 65.0  # 0-100
    sleep_efficiency: float = 85.0  # 0-100


@dataclass
class PerformanceState:
    """Capacidad de desempeño físico/cognitivo (transversal, derivado)."""
    physical_capacity: float = 80.0  # 0-100
    cognitive_capacity: float = 75.0  # 0-100
    focus_level: float = 70.0  # 0-100
    peak_performance_window: str = "optimal"  # suboptimal, optimal, overreached


@dataclass
class PhysiologicalInteraction:
    """Describe cómo un órgano/estado afecta a otro (para fines descriptivos/UI)."""
    source: str
    target: str
    interaction_type: str  # "increases", "decreases", "synchronizes"
    strength: float = 0.5  # 0-1
    description: str = ""


@dataclass
class OrganSystem:
    """Sistema fisiológico completo (Cerebro, Corazón, etc.)"""
    name: str
    organ_id: str  # brain, heart, lungs, muscles, autonomic
    metrics: OrganMetrics = field(default_factory=OrganMetrics)
    education: Dict[str, str] = field(default_factory=dict)  # Contenido educativo
    pathologies: List[str] = field(default_factory=list)  # Patologías conocidas
    detail: Optional[Any] = None  # CardiacDetail / NeurologicalDetail / etc. — high-fidelity parameters

    @property
    def status(self) -> OrganHealthStatus:
        """Determina estado actual"""
        score = self.metrics.health_score
        if score >= 80:
            return OrganHealthStatus.OPTIMAL
        elif score >= 60:
            return OrganHealthStatus.NORMAL
        elif score >= 40:
            return OrganHealthStatus.ALERT
        else:
            return OrganHealthStatus.CRITICAL
    
    @property
    def icon(self) -> str:
        """Icono representativo"""
        icons = {
            "brain": "🧠",
            "heart": "❤️",
            "lungs": "💨",
            "muscles": "💪",
            "autonomic": "⚡",
            "cardiovascular": "🫀",
            "respiratory": "🫁",
        }
        return icons.get(self.organ_id, "●")
    
    @property
    def color(self) -> str:
        """Color basado en estado"""
        status_colors = {
            OrganHealthStatus.CRITICAL: "#ff3333",
            OrganHealthStatus.ALERT: "#ffd700",
            OrganHealthStatus.NORMAL: "#39ffbe",
            OrganHealthStatus.OPTIMAL: "#00ff00",
        }
        return status_colors.get(self.status, "#808080")


class DigitalTwinOrganism:
    """
    Representación viva y computacional del cuerpo humano.
    Centro absoluto de BIOCORE AI.
    """
    
    def __init__(self):
        self.timestamp = datetime.now()
        self.organs: Dict[str, OrganSystem] = self._initialize_organs()
        self.connections: List[Tuple[str, str, str]] = self._initialize_connections()  # (from, to, type)
        self.global_state: Dict[str, float] = {}
        self.history: List[Dict] = []
        self.max_history = 500
        self.current_scenario: Optional[str] = None
        self.simulation_mode: bool = False
        self.timeline_events: List[Dict] = []

        # Cross-cutting physiological states (not tied to a single anatomical organ).
        # Ported from the legacy DigitalTwinMultisystem during engine consolidation.
        self.stress = StressState()
        self.recovery = RecoveryState()
        self.sleep = SleepState()
        self.performance = PerformanceState()
        self.interactions: List[PhysiologicalInteraction] = self._initialize_interactions()
    
    def _initialize_organs(self) -> Dict[str, OrganSystem]:
        """Inicializa los sistemas de órganos principales"""
        organs = {
            "brain": OrganSystem(
                # Fase 1 (idioma, 2026-08-30): `name` es solo texto de
                # display (se muestra tal cual en las tarjetas de órgano de
                # Twin OS) -- NO es una clave de lookup, esa es `organ_id`
                # ("brain", en minúsculas, sin tocar). Confirmado por grep
                # antes de traducir.
                name="Cerebro",
                organ_id="brain",
                education={
                    "es": "Control central del cuerpo. Procesa sensaciones, genera emociones, toma decisiones.",
                    "pathophysiology": "La disfunción cerebral afecta cognitivamente, emocionalmente y en control autonómico.",
                },
                pathologies=["Epilepsia", "Parkinson", "Alzheimer", "ACV", "Ansiedad", "Depresión"],
                detail=NeurologicalDetail(),
            ),
            "heart": OrganSystem(
                name="Corazón",
                organ_id="heart",
                education={
                    "es": "Bomba fisiológica. Mantiene perfusión sistémica y homeostasis.",
                    "pathophysiology": "Disfunción cardíaca reduce oxigenación y causa deterioro multisistémico.",
                },
                pathologies=["Infarto", "Arritmia", "Insuficiencia", "Hipertensión"],
                detail=CardiacDetail(),
            ),
            "lungs": OrganSystem(
                name="Pulmones",
                organ_id="lungs",
                education={
                    "es": "Intercambio gaseoso. Vital para oxigenación y equilibrio ácido-base.",
                    "pathophysiology": "Hipoxia causa disfunción cerebral, cardiaca y muscular secuenciales.",
                },
                pathologies=["EPOC", "Apnea", "Neumonía", "Asma", "Embolia"],
                detail=RespiratoryDetail(),
            ),
            "muscles": OrganSystem(
                name="Músculos",
                organ_id="muscles",
                education={
                    "es": "Sistema motriz. Genera movimiento, genera calor, protege.",
                    "pathophysiology": "Fatiga muscular refleja estrés sistémico y falta de recuperación.",
                },
                pathologies=["Miopatía", "Distrofia", "Fatiga crónica"],
                detail=MusculoskeletalDetail(),
            ),
            "autonomic": OrganSystem(
                name="Sistema Nervioso Autónomo",
                organ_id="autonomic",
                education={
                    "es": "Control automático. Simpático (fight) vs Parasimpático (rest).",
                    "pathophysiology": "Desequilibrio autonómico causa disregulación de HR, respiración y digestion.",
                },
                pathologies=["Disautonomía", "POTS", "Síncope", "Disfunción erectil"],
                detail=AutonomicDetail(),
            ),
        }
        return organs

    def _initialize_interactions(self) -> List[PhysiologicalInteraction]:
        """Red descriptiva de interacciones fisiológicas (para exploración/UI educativa)."""
        return [
            PhysiologicalInteraction("brain", "heart", "increases", 0.7, "Estrés mental aumenta frecuencia cardíaca"),
            PhysiologicalInteraction("heart", "lungs", "synchronizes", 0.6, "Ritmo cardíaco sincronizado con respiración"),
            PhysiologicalInteraction("lungs", "brain", "increases", 0.7, "Hipoxia reduce atención y cognición"),
            PhysiologicalInteraction("brain", "autonomic", "increases", 0.8, "Estrés cortical aumenta actividad simpática"),
            PhysiologicalInteraction("muscles", "autonomic", "decreases", 0.7, "Actividad muscular reduce capacidad de recuperación"),
            PhysiologicalInteraction("autonomic", "sleep", "synchronizes", 0.6, "Balance parasimpático facilita el sueño"),
            PhysiologicalInteraction("recovery", "performance", "increases", 0.8, "Recuperación mejora el desempeño"),
        ]
    
    def _initialize_connections(self) -> List[Tuple[str, str, str]]:
        """Inicializa conexiones causales entre órganos"""
        connections = [
            # Brain → Heart
            ("brain", "heart", "neurocardiac"),  # EEG stress → HRV ↓ → HR ↑
            # Heart → Lungs
            ("heart", "lungs", "cardiopulmonary"),  # Cardiac output → RR adjustment
            # Lungs → Brain
            ("lungs", "brain", "oxygenation"),  # SpO2 → Cognitive state
            # Brain → Autonomic
            ("brain", "autonomic", "stress_response"),  # Cortical stress → Sympathetic activation
            # Autonomic → Heart
            ("autonomic", "heart", "autonomic_control"),  # SNS/PSNS → HR/HRV
            # Autonomic → Lungs
            ("autonomic", "lungs", "autonomic_breathing"),  # SNS → RR ↑
            # Muscles → Autonomic
            ("muscles", "autonomic", "fatigue_signal"),  # EMG fatigue → Recovery need
            # Heart → Muscles
            ("heart", "muscles", "perfusion"),  # Cardiac output → Muscle perfusion
            # Lungs → Muscles
            ("lungs", "muscles", "oxygenation"),  # SpO2 → Muscle oxygen delivery
        ]
        return connections
    
    def update_from_sensors(self, sensor_data: Dict[str, Dict[str, float]]) -> None:
        """
        Actualiza el gemelo desde datos de sensores
        
        sensor_data: {
            'ecg': {'heart_rate': 72, 'hrv': 45, ...},
            'eeg': {'alpha_power': 50, 'stress_level': 35, ...},
            'respiratory': {'respiratory_rate': 16, 'spo2': 98, ...},
            'emg': {'fatigue_index': 20, 'activation': 45, ...},
            'temperature': {'mean_temp': 37.0, ...},
        }
        """
        # Actualizar Corazón desde ECG
        if 'ecg' in sensor_data:
            self._update_heart(sensor_data['ecg'])
        
        # Actualizar Cerebro desde EEG
        if 'eeg' in sensor_data:
            self._update_brain(sensor_data['eeg'])
        
        # Actualizar Pulmones desde Respiración + SpO2
        if 'respiratory' in sensor_data:
            self._update_lungs(sensor_data['respiratory'])
        
        # Actualizar Músculos desde EMG
        if 'emg' in sensor_data:
            self._update_muscles(sensor_data['emg'])
        
        # Propagar efectos entre órganos (causalidad)
        self._propagate_physiological_effects()

        # Actualizar estado autonómico
        self._update_autonomic_state()

        # Actualizar estados transversales (estrés, recuperación, desempeño)
        self._update_cross_cutting_states()

        # Calcular estado global
        self._compute_global_state()
        
        # Agregar a historia
        self._add_to_history()

        # Deuda de producción (2026-08-11, Capa A): datetime.now() en esta máquina
        # midió tan solo 2 valores distintos en 20.000 llamadas consecutivas -- un
        # escenario de 6 horizontes (run_rich_scenario, cada uno llama a este
        # método una vez, en ráfaga) podía producir dos timestamps IDÉNTICOS.
        # get_snapshot_id_at() (domain/physiology/state/clinical_impression_repository.py)
        # resuelve snapshots por (patient_id, timestamp) exacto -- una colisión ahí
        # dejaba la resolución no determinista, adjuntando la PA calculada al
        # snapshot equivocado (~1-2% de los casos, medido). Forzar timestamps
        # estrictamente crecientes dentro de la vida de este organismo elimina la
        # colisión en el origen -- ver CHANGELOG.md. (Capa B, en
        # get_snapshot_id_at(), es la defensa complementaria ante cualquier otra
        # fuente de colisión no prevista aquí -- ninguna de las dos sustituye a la
        # otra.)
        now = datetime.now()
        self.timestamp = now if now > self.timestamp else self.timestamp + timedelta(microseconds=1)
    
    def _update_heart(self, ecg_data: Dict[str, float]) -> None:
        """Actualiza estado cardíaco desde ECG"""
        heart = self.organs["heart"]
        
        hr = ecg_data.get("heart_rate", 70)
        hrv = ecg_data.get("hrv", 50)
        complexity = ecg_data.get("complexity", 50)
        
        # Health score: HR normal (60-100), HRV alto (>30)
        hr_penalty = abs(hr - 70) / 70 * 0.3
        hrv_bonus = min(100, (hrv / 100) * 100) * 0.5
        complexity_bonus = complexity * 0.2
        
        heart.metrics.health_score = min(100.0, max(0.0, 100 - hr_penalty * 100 + hrv_bonus + complexity_bonus))
        heart.metrics.activity_level = min(100, (hr / 100) * 100)
        heart.metrics.signals = ecg_data.copy()

        # Risk assessment
        if hr > 120 or hr < 40:
            heart.metrics.risk_score = 75.0
        elif hrv < 20:
            heart.metrics.risk_score = 50.0
        else:
            heart.metrics.risk_score = 0.0

        if heart.detail is not None:
            heart.detail.myocardial_stress = min(100.0, max(0.0, 100.0 - heart.metrics.health_score))
            heart.detail.rhythm_stability = min(100.0, max(0.0, complexity))
    
    def _update_brain(self, eeg_data: Dict[str, float]) -> None:
        """Actualiza estado cerebral desde EEG"""
        brain = self.organs["brain"]
        
        alpha = eeg_data.get("alpha_power", 50)
        beta = eeg_data.get("beta_power", 30)
        stress_level = eeg_data.get("stress_level", 35)
        relaxation = eeg_data.get("relaxation_level", 65)
        
        # Health score: Alta relajación, bajo estrés
        brain.metrics.health_score = max(0, relaxation - stress_level * 0.5)
        brain.metrics.activity_level = min(100, beta / 50 * 100)
        brain.metrics.signals = eeg_data.copy()
        
        # Risk assessment
        if stress_level > 75:
            brain.metrics.risk_score = 60.0
        elif stress_level > 50:
            brain.metrics.risk_score = 30.0
        else:
            brain.metrics.risk_score = 0.0

        if brain.detail is not None:
            brain.detail.mental_workload = min(100.0, beta)
            brain.detail.cognitive_fatigue = min(100.0, max(0.0, 100.0 - brain.metrics.health_score))
            brain.detail.attention = min(100.0, max(0.0, eeg_data.get("attention", relaxation + alpha * 0.2)))
            brain.detail.stress_perception = min(100.0, max(0.0, stress_level))
            brain.detail.sleepiness = min(100.0, max(0.0, 100.0 - brain.detail.attention))
    
    def _update_lungs(self, resp_data: Dict[str, float]) -> None:
        """Actualiza estado respiratorio"""
        lungs = self.organs["lungs"]
        
        rr = resp_data.get("respiratory_rate", 16)
        spo2 = resp_data.get("spo2", 98)
        ahi = resp_data.get("ahi", 0)
        
        # Health score: RR normal (12-20), SpO2 alto (>95%)
        rr_penalty = abs(rr - 16) / 16 * 0.3
        spo2_score = min(100, (spo2 / 100) * 100)
        ahi_penalty = min(100, ahi / 30 * 100) * 0.4
        
        lungs.metrics.health_score = max(0, (spo2_score * 0.5 + (100 - rr_penalty * 100) * 0.3 - ahi_penalty))
        lungs.metrics.activity_level = min(100, (rr / 40) * 100)
        lungs.metrics.signals = resp_data.copy()
        
        # Risk assessment
        if spo2 < 90 or ahi > 20:
            lungs.metrics.risk_score = 80.0
        elif spo2 < 95 or ahi > 5:
            lungs.metrics.risk_score = 40.0
        else:
            lungs.metrics.risk_score = 0.0

        if lungs.detail is not None:
            lungs.detail.apnea_risk = min(100.0, (ahi / 30.0) * 100.0)
            lungs.detail.hypoxia_risk = min(100.0, max(0.0, (95.0 - spo2) / 95.0 * 100.0))
            lungs.detail.perfusion_index = spo2_score
            lungs.detail.tissue_oxygenation = spo2_score
    
    def _update_muscles(self, emg_data: Dict[str, float]) -> None:
        """Actualiza estado muscular"""
        muscles = self.organs["muscles"]
        
        fatigue = emg_data.get("fatigue_index", 20)
        activation = emg_data.get("activation", 45)
        efficiency = emg_data.get("efficiency", 70)
        
        # Health score: Baja fatiga, eficiencia alta
        muscles.metrics.health_score = max(0, efficiency - fatigue * 0.5)
        muscles.metrics.activity_level = activation
        muscles.metrics.signals = emg_data.copy()
        
        # Risk assessment
        if fatigue > 80:
            muscles.metrics.risk_score = 70.0
        elif fatigue > 50:
            muscles.metrics.risk_score = 40.0
        else:
            muscles.metrics.risk_score = 0.0

        if muscles.detail is not None:
            muscles.detail.neuromuscular_efficiency = min(100.0, max(0.0, efficiency))
            muscles.detail.movement_smoothness = min(100.0, max(0.0, 100.0 - fatigue))
    
    def _propagate_physiological_effects(self) -> None:
        """Propaga efectos causales entre órganos"""
        # Brain stress → Heart: reduce HRV
        brain_stress = 100 - self.organs["brain"].metrics.health_score
        self.organs["heart"].metrics.signals["hrv_modulation"] = -brain_stress * 0.3
        
        # Heart dysfunction → Lungs: aumenta RR
        heart_risk = self.organs["heart"].metrics.risk_score
        self.organs["lungs"].metrics.signals["rr_modulation"] = heart_risk * 0.2
        
        # Low SpO2 → Brain: afecta cognición
        spo2 = self.organs["lungs"].metrics.signals.get("spo2", 98)
        if spo2 < 90:
            self.organs["brain"].metrics.health_score *= 0.8
        
        # Muscle fatigue → Autonomic: requiere recuperación
        muscle_fatigue = self.organs["muscles"].metrics.signals.get("fatigue_index", 0)
        self.organs["autonomic"].metrics.signals["recovery_need"] = muscle_fatigue * 0.6
    
    def _update_autonomic_state(self) -> None:
        """Actualiza estado autonómico basado en otros sistemas"""
        autonomic = self.organs["autonomic"]
        
        # Autonomic balance from HRV and stress
        hrv = self.organs["heart"].metrics.signals.get("hrv", 50)
        brain_stress = 100 - self.organs["brain"].metrics.health_score
        
        # HRV alto + bajo stress = parasimpático (bueno)
        # HRV bajo + alto stress = simpático dominante (malo)
        parasympathetic_tone = (hrv / 100) * (1 - brain_stress / 100)
        
        autonomic.metrics.health_score = max(0, parasympathetic_tone * 100)
        autonomic.metrics.signals = {
            "hrv": hrv,
            "stress_cortisol": brain_stress,
            "parasympathetic_tone": parasympathetic_tone,
        }

        if autonomic.detail is not None:
            autonomic.detail.sympathetic_activity = min(100.0, max(0.0, brain_stress))
            autonomic.detail.parasympathetic_activity = min(100.0, max(0.0, parasympathetic_tone * 100))

    def _update_cross_cutting_states(self) -> None:
        """
        Deriva estados transversales (estrés, recuperación, desempeño) del resto del
        organismo. Ported from the legacy DigitalTwinMultisystem during consolidation.
        """
        brain = self.organs["brain"]
        muscles = self.organs["muscles"]
        autonomic = self.organs["autonomic"]

        stress_level = brain.metrics.signals.get("stress_level", 100.0 - brain.metrics.health_score)
        self.stress.acute_stress = min(100.0, max(0.0, stress_level))
        self.stress.chronic_stress = min(100.0, max(0.0, self.stress.chronic_stress * 0.9 + self.stress.acute_stress * 0.1))

        fatigue_index = muscles.metrics.signals.get("fatigue_index", 20.0)
        self.recovery.recovery_capacity = min(100.0, max(0.0, 100.0 - fatigue_index))
        self.recovery.metabolic_recovery = autonomic.metrics.health_score

        self.performance.physical_capacity = min(100.0, max(0.0, 100.0 - muscles.metrics.risk_score))
        self.performance.cognitive_capacity = brain.metrics.health_score
        self.performance.focus_level = min(100.0, max(0.0, 100.0 - self.stress.acute_stress))

    def _compute_global_state(self) -> None:
        """Calcula el estado fisiológico global"""
        scores = [organ.metrics.health_score for organ in self.organs.values()]
        risks = [organ.metrics.risk_score for organ in self.organs.values()]

        self.global_state = {
            "global_health_score": float(np.mean(scores)),
            "global_risk_score": float(np.max(risks)),
            "system_coherence": self._compute_system_coherence(),
            "resilience_index": self._compute_resilience(),
            "cognitive_state": self.organs["brain"].metrics.health_score,
            "cardiac_state": self.organs["heart"].metrics.health_score,
            "respiratory_state": self.organs["lungs"].metrics.health_score,
            "muscular_state": self.organs["muscles"].metrics.health_score,
            "autonomic_balance": self.organs["autonomic"].metrics.health_score,
        }
        self.global_state.update(self._compute_couplings())
        self.global_state["risk_level"] = self._compute_risk_level(self.global_state["global_risk_score"])
        anomalies, recommendations, alerts = self._detect_anomalies()
        self.global_state["anomalies"] = anomalies
        self.global_state["recommendations"] = recommendations
        self.global_state["alerts"] = alerts

    @staticmethod
    def _compute_risk_level(global_risk_score: float) -> str:
        # Fase 1 (idioma, 2026-08-30): CRÍTICO/ALTO/MODERADO/BAJO -- antes
        # Critical/High/Medium/Low. Corrección sobre el diagnóstico original:
        # este método (el que alimenta `global_state["risk_level"]`, leído
        # en `render_ambient_header()`, "Riesgo: {risk}") SÍ estaba en
        # inglés -- el diagnóstico lo había confundido con el bloque de
        # texto de exportación más abajo en este archivo (Nivel de Riesgo:
        # ...), que ya era español pero es un método distinto y no
        # alimenta este campo. Único consumidor de `global_state["risk_level"]`
        # en todo el repo: `twin_shell/pages.py::render_ambient_header()` --
        # sin ninguna comparación lógica contra este valor (confirmado por
        # grep), solo se muestra. Ver CHANGELOG.md.
        if global_risk_score >= 70:
            return "CRÍTICO"
        elif global_risk_score >= 40:
            return "ALTO"
        elif global_risk_score >= 20:
            return "MODERADO"
        return "BAJO"

    def _detect_anomalies(self) -> Tuple[List[str], List[str], List[str]]:
        """
        Detecta anomalías y genera recomendaciones/alertas a partir del estado de cada órgano.
        Ported from the legacy PhysiologicalFusionEngine during engine consolidation.
        """
        anomalies: List[str] = []
        recommendations: List[str] = []
        alerts: List[str] = []

        heart = self.organs["heart"].metrics
        brain = self.organs["brain"].metrics
        lungs = self.organs["lungs"].metrics
        muscles = self.organs["muscles"].metrics

        # Fase 1 (idioma, 2026-08-30): traducidas a español -- eran texto
        # generado mostrado directamente al usuario (st.warning/st.error en
        # twin_shell/pages.py), no claves. ÚNICO cuidado real: estas frases
        # se enrutan a un órgano por coincidencia de subcadena
        # (`ORGAN_KEYWORDS` en twin_shell/pages.py, sobre palabras
        # compuestas como "cardiorespiratory"/"neurocardiac") -- cada
        # traducción se verificó para que produzca EXACTAMENTE el mismo
        # conjunto de órganos que la original en inglés (ver CHANGELOG.md
        # para la tabla de verificación). "corazón-aliento" en vez de
        # "corazón-respiración" es deliberado: preserva que este alert NO
        # se enrute a Pulmones, igual que el original ("breath", no
        # "breathing", no calzaba con el keyword de pulmones).
        if heart.health_score < 40:
            anomalies.append("Estrés cardiovascular detectado")
            alerts.append("⚠️ Anomalía en el ritmo o la frecuencia del corazón")

        if brain.signals.get("stress_level", 0) > 75:
            anomalies.append("Estado de estrés elevado detectado")
            recommendations.append("Considera técnicas de relajación")
            alerts.append("⚠️ Niveles de estrés elevados")

        if brain.health_score < 30:
            anomalies.append("Somnolencia severa o deterioro cognitivo detectado")
            recommendations.append("Toma un descanso o duerme")
            alerts.append("⚠️ Alerta baja - riesgo de fatiga")

        if lungs.health_score < 40:
            anomalies.append("Anomalía respiratoria detectada")
            alerts.append("⚠️ SpO₂ bajo o respiración irregular")

        if muscles.health_score < 40:
            anomalies.append("Fatiga muscular severa detectada")
            recommendations.append("Se necesita descanso y recuperación")

        if self.global_state.get("neurocardiac_coupling", 1.0) < 0.3:
            anomalies.append("Desacoplamiento neurocardíaco detectado")
            alerts.append("⚠️ Coordinación cerebro-corazón afectada")

        if self.global_state.get("cardiorespiratory_coupling", 1.0) < 0.3:
            anomalies.append("Desincronización cardiorrespiratoria")
            alerts.append("⚠️ Sincronización corazón-aliento perdida")

        return anomalies, recommendations, alerts

    def _compute_couplings(self) -> Dict[str, float]:
        """
        Acoplamientos inter-sistémicos (neurocardiaco, cardiorespiratorio, neuromuscular).
        Ported from the legacy PhysiologicalFusionEngine (app/engines/physiological_fusion.py)
        during engine consolidation — same formulas, adapted to organ-signal dicts.
        """
        heart_signals = self.organs["heart"].metrics.signals
        brain_signals = self.organs["brain"].metrics.signals
        lungs_signals = self.organs["lungs"].metrics.signals
        muscles_signals = self.organs["muscles"].metrics.signals

        couplings = {
            "neurocardiac_coupling": 0.5,
            "cardiorespiratory_coupling": 0.5,
            "neuromuscular_coupling": 0.5,
        }

        if brain_signals and heart_signals:
            alpha = brain_signals.get("alpha_power", 50)
            hrv = heart_signals.get("hrv", 50)
            expected_hrv_from_relaxation = 50 + (alpha / 100) * 50
            coupling = 1.0 - abs(hrv - expected_hrv_from_relaxation) / 100
            couplings["neurocardiac_coupling"] = max(0.0, min(1.0, coupling))

        if heart_signals and lungs_signals:
            hr = heart_signals.get("heart_rate", 70)
            rr = lungs_signals.get("respiratory_rate", 16)
            optimal_ratio = 4.0
            actual_ratio = hr / (rr + 1e-6)
            coupling = 1.0 - abs(actual_ratio - optimal_ratio) / optimal_ratio
            couplings["cardiorespiratory_coupling"] = max(0.0, min(1.0, coupling))

        if brain_signals and muscles_signals:
            cognitive_state = self.organs["brain"].metrics.health_score
            emg_fatigue = muscles_signals.get("fatigue_index", 50)
            expected_fatigue = cognitive_state * 0.7
            coupling = 1.0 - abs(emg_fatigue - expected_fatigue) / 100
            couplings["neuromuscular_coupling"] = max(0.0, min(1.0, coupling))

        return couplings
    
    def _compute_system_coherence(self) -> float:
        """Mide cuán bien trabajanintegrados los sistemas"""
        # Si todos los órganos tienen health scores similares, hay coherencia
        scores = [organ.metrics.health_score for organ in self.organs.values()]
        std = np.std(scores)
        # Coherencia es inversa a la varianza
        coherence = max(0, 100 - std)
        return float(coherence)
    
    def _compute_resilience(self) -> float:
        """Mide capacidad de recuperación del organismo"""
        # Resilience = capacidad de mantener homeostasis bajo estrés
        global_health = self.global_state.get("global_health_score", 50)
        global_risk = self.global_state.get("global_risk_score", 0)
        hrv = self.organs["heart"].metrics.signals.get("hrv", 50)
        
        # Buena salud + bajo riesgo + alto HRV = alta resiliencia
        resilience = (global_health * 0.4 + (100 - global_risk) * 0.3 + (hrv / 100) * 100 * 0.3)
        return float(np.clip(resilience, 0, 100))
    
    def _add_to_history(self) -> None:
        """Agrega estado actual a historia"""
        snapshot = {
            "timestamp": self.timestamp.isoformat(),
            "global_state": self.global_state.copy(),
            "organs": {
                organ_id: {
                    "health": organ.metrics.health_score,
                    "risk": organ.metrics.risk_score,
                    "activity": organ.metrics.activity_level,
                }
                for organ_id, organ in self.organs.items()
            }
        }
        self.history.append(snapshot)
        if len(self.history) > self.max_history:
            self.history.pop(0)
    
    def get_organ(self, organ_id: str) -> Optional[OrganSystem]:
        """Obtiene un órgano específico"""
        return self.organs.get(organ_id)
    
    def get_all_organs(self) -> List[OrganSystem]:
        """Obtiene todos los órganos"""
        return list(self.organs.values())
    
    def get_connection_path(self, from_organ: str, to_organ: str) -> Optional[List[str]]:
        """Busca ruta causal entre dos órganos"""
        # BFS para encontrar ruta
        from collections import deque
        
        graph = {}
        for src, dst, _ in self.connections:
            if src not in graph:
                graph[src] = []
            graph[src].append(dst)
        
        queue = deque([(from_organ, [from_organ])])
        visited = {from_organ}
        
        while queue:
            current, path = queue.popleft()
            if current == to_organ:
                return path
            
            for neighbor in graph.get(current, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))
        
        return None
    
    def explain_state(self) -> str:
        """Explicación en lenguaje natural del estado actual"""
        global_health = self.global_state.get("global_health_score", 0)
        global_risk = self.global_state.get("global_risk_score", 0)
        
        if global_risk > 70:
            risk_level = "CRÍTICO"
        elif global_risk > 40:
            risk_level = "ALTO"
        elif global_risk > 20:
            risk_level = "MODERADO"
        else:
            risk_level = "BAJO"
        
        return (
            f"Estado Fisiológico Global: {global_health:.0f}/100\n"
            f"Nivel de Riesgo: {risk_level}\n"
            f"Coherencia Sistémica: {self.global_state.get('system_coherence', 0):.0f}%\n"
            f"Resiliencia: {self.global_state.get('resilience_index', 0):.0f}/100"
        )

    def simulate_intervention(self, intervention: str, intensity: float = 0.5) -> Dict[str, float]:
        """
        Simula una intervención médica sobre el organismo (no toca el estado real del
        paciente — solo esta instancia simulada). Ported from DigitalTwinMultisystem.

        Args:
            intervention: "oxygen", "sedation", "exercise" o "rest".
            intensity: 0-1.
        """
        heart, lungs, brain, muscles = (
            self.organs["heart"], self.organs["lungs"], self.organs["brain"], self.organs["muscles"]
        )
        changes: Dict[str, float] = {}

        if intervention == "oxygen":
            if lungs.detail is not None:
                lungs.detail.tissue_oxygenation = min(100.0, lungs.detail.tissue_oxygenation + intensity * 15)
            new_spo2 = min(100.0, lungs.metrics.signals.get("spo2", 98.0) + intensity * 8)
            lungs.metrics.signals["spo2"] = new_spo2
            if brain.detail is not None:
                brain.detail.cognitive_fatigue = max(0.0, brain.detail.cognitive_fatigue - intensity * 10)
            changes['spo2'] = new_spo2

        elif intervention == "sedation":
            new_stress = max(0.0, self.stress.acute_stress - intensity * 40)
            self.stress.acute_stress = new_stress
            if self.organs["autonomic"].detail is not None:
                self.organs["autonomic"].detail.sympathetic_activity = max(
                    0.0, self.organs["autonomic"].detail.sympathetic_activity - intensity * 30
                )
            heart.metrics.signals["heart_rate"] = max(50.0, heart.metrics.signals.get("heart_rate", 70.0) - intensity * 20)
            changes['stress'] = new_stress

        elif intervention == "exercise":
            new_hr = min(180.0, heart.metrics.signals.get("heart_rate", 70.0) + intensity * 40)
            heart.metrics.signals["heart_rate"] = new_hr
            muscles.metrics.signals["fatigue_index"] = min(
                100.0, muscles.metrics.signals.get("fatigue_index", 20.0) + intensity * 30
            )
            lungs.metrics.signals["respiratory_rate"] = lungs.metrics.signals.get("respiratory_rate", 16.0) + intensity * 8
            changes['heart_rate'] = new_hr

        elif intervention == "rest":
            new_recovery = min(100.0, self.recovery.recovery_capacity + intensity * 20)
            self.recovery.recovery_capacity = new_recovery
            self.stress.acute_stress = max(0.0, self.stress.acute_stress - intensity * 30)
            muscles.metrics.signals["fatigue_index"] = max(
                0.0, muscles.metrics.signals.get("fatigue_index", 20.0) - intensity * 15
            )
            changes['recovery'] = new_recovery

        self._propagate_physiological_effects()
        self._compute_global_state()
        return changes

    def predict_physiological_events(self, horizon_minutes: int = 60) -> Dict[str, Dict[str, Any]]:
        """Predicciones fisiológicas simples con horizonte.

        Sin `confidence` por predicción (retirado 2026-08-14, Art. I --
        confianza simulada, mismo gemelo que `PredictionEngine.assess_*_risk`
        y el clasificador ECG): eran constantes fijas (0.75/0.70/0.65/
        0.80/0.85) que no reaccionaban a ningún dato. Confirmado por grep
        antes de retirarlas: este método no tiene ningún llamador vivo --
        solo aparece en `_archive/` -- así que además de fachada, estaba
        muerto; no hay ningún consumidor que se rompa."""
        muscles = self.organs["muscles"]
        fatigue_index = muscles.metrics.signals.get("fatigue_index", 20.0)
        fatigue_progression = fatigue_index + (horizon_minutes / 60.0 * 5.0)

        recovery_trajectory = self.recovery.recovery_capacity - (horizon_minutes / 120.0 * 2.0)

        stress_trend = (
            self.stress.acute_stress if self.stress.acute_stress > 50
            else max(0.0, self.stress.acute_stress - 5.0)
        )

        heart = self.organs["heart"]
        lungs = self.organs["lungs"]
        hr = heart.metrics.signals.get("heart_rate", 70.0)
        spo2 = lungs.metrics.signals.get("spo2", 98.0)
        cardiovascular_risk = "HIGH" if (hr > 120 or spo2 < 90) else "LOW"

        return {
            'fatigue': {'predicted': min(100.0, fatigue_progression)},
            'recovery': {'predicted': max(0.0, recovery_trajectory)},
            'stress': {'predicted': stress_trend},
            'cardiovascular_instability': {'risk': cardiovascular_risk},
        }

    def generate_clinical_summary(self) -> str:
        """Genera un resumen clínico legible del estado completo del organismo."""
        heart, brain, lungs, muscles, autonomic = (
            self.organs["heart"], self.organs["brain"], self.organs["lungs"],
            self.organs["muscles"], self.organs["autonomic"],
        )
        cd, nd, rd, md, ad = heart.detail, brain.detail, lungs.detail, muscles.detail, autonomic.detail

        return f"""
╔════════════════════════════════════════════════════════════════════════════╗
║                    RESUMEN CLÍNICO DEL GEMELO DIGITAL                      ║
║                          {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}                              ║
╚════════════════════════════════════════════════════════════════════════════╝

🫀 SISTEMA CARDIOVASCULAR:
   • Frecuencia Cardíaca: {heart.metrics.signals.get('heart_rate', 0):.1f} bpm
   • Variabilidad (HRV): {heart.metrics.signals.get('hrv', 0):.1f} ms
   • Estabilidad de Ritmo: {cd.rhythm_stability if cd else 0:.1f}%
   • Estrés Miocárdico: {cd.myocardial_stress if cd else 0:.1f}%
   • Gasto Cardíaco: {cd.cardiac_output if cd else 0:.1f} L/min

🧠 SISTEMA NEUROLÓGICO:
   • Salud General: {brain.metrics.health_score:.1f}%
   • Carga Cognitiva: {nd.mental_workload if nd else 0:.1f}%
   • Fatiga Cognitiva: {nd.cognitive_fatigue if nd else 0:.1f}%

💨 SISTEMA RESPIRATORIO / OXIGENACIÓN:
   • Frecuencia Respiratoria: {lungs.metrics.signals.get('respiratory_rate', 0):.1f} resp/min
   • SpO₂: {lungs.metrics.signals.get('spo2', 0):.1f}%
   • Riesgo de Apnea: {rd.apnea_risk if rd else 0:.1f}%
   • Riesgo de Hipoxia: {rd.hypoxia_risk if rd else 0:.1f}%

🦾 SISTEMA MUSCULOESQUELÉTICO:
   • Índice de Fatiga: {muscles.metrics.signals.get('fatigue_index', 0):.1f}%
   • Eficiencia Neuromuscular: {md.neuromuscular_efficiency if md else 0:.1f}%

🔄 SISTEMA AUTONÓMICO:
   • Actividad Simpática: {ad.sympathetic_activity if ad else 0:.1f}%
   • Actividad Parasimpática: {ad.parasympathetic_activity if ad else 0:.1f}%

⚡ RECUPERACIÓN Y RENDIMIENTO:
   • Capacidad de Recuperación: {self.recovery.recovery_capacity:.1f}%
   • Estrés Agudo: {self.stress.acute_stress:.1f}%
   • Desempeño Físico: {self.performance.physical_capacity:.1f}%
   • Desempeño Cognitivo: {self.performance.cognitive_capacity:.1f}%

════════════════════════════════════════════════════════════════════════════════
"""

    def to_json(self) -> str:
        """Convierte el estado completo (órganos + estados transversales) a JSON."""
        state = {
            'timestamp': self.timestamp.isoformat(),
            'global_state': self.global_state,
            'organs': {
                organ_id: {
                    'health_score': organ.metrics.health_score,
                    'risk_score': organ.metrics.risk_score,
                    'signals': organ.metrics.signals,
                    'detail': organ.detail.__dict__ if organ.detail is not None else None,
                }
                for organ_id, organ in self.organs.items()
            },
            'stress': self.stress.__dict__,
            'recovery': self.recovery.__dict__,
            'sleep': self.sleep.__dict__,
            'performance': self.performance.__dict__,
        }
        return json.dumps(state, indent=2, default=str)

    def create_patient_scenario(self, scenario: str) -> None:
        """
        Aplica un preset de paciente (healthy, hypertension, copd, arrhythmia, sepsis)
        directamente a las señales/detalles de los órganos correspondientes.
        """
        scenarios: Dict[str, Dict[str, Dict[str, float]]] = {
            'healthy': {
                'ecg': {'heart_rate': 72, 'hrv': 60}, 'respiratory': {'respiratory_rate': 16, 'spo2': 98},
                'eeg': {'stress_level': 20}, 'emg': {'fatigue_index': 10, 'efficiency': 90},
            },
            'hypertension': {
                'ecg': {'heart_rate': 85, 'hrv': 40}, 'eeg': {'stress_level': 55},
            },
            'copd': {
                'respiratory': {'respiratory_rate': 22, 'spo2': 88, 'ahi': 3},
            },
            'arrhythmia': {
                'ecg': {'heart_rate': 95, 'hrv': 15},
            },
            'sepsis': {
                'ecg': {'heart_rate': 110, 'hrv': 20}, 'respiratory': {'respiratory_rate': 28, 'spo2': 92},
                'eeg': {'stress_level': 85},
            },
        }

        config = scenarios.get(scenario)
        if config is None:
            return
        self.current_scenario = scenario
        self.update_from_sensors(config)
