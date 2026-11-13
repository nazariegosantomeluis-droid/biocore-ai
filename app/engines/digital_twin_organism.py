"""
BIOCORE AI — Digital Twin Organism

El corazón inteligente de la plataforma.
Representación viva y computacional del cuerpo humano.
Centro absoluto que integra todas las señales biomédicas.

Frente cardiovascular, Fase 1 (2026-11-12, Art. I): el organismo NO calcula con valores por defecto. Cada métrica se
calcula solo si llegaron sus entradas; si no, es `None` («sin dato») y así se muestra. Decisiones firmadas por Luis:
(1) se retiran `health_score` cardiaco y `myocardial_stress`; (2) se descartan `complexity` y `rhythm_stability`;
(3) `cardiac_output` no lo calcula el organismo («no modelado»); (4) el riesgo cardiaco son los puntos NEWS2 del pulso
(`clinical.calculators.news2_pulse_score`), sin umbrales caseros; (5) dato faltante = «sin dato», nunca «BAJO», 0 ni 50;
(7) `CardiacDetail` se eliminó entero: ninguno de sus 10 campos lo calculaba nadie.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
import json
import math
import numpy as np
from datetime import datetime, timedelta

from clinical.calculators import news2_pulse_score

NO_DATA = "sin dato"            # texto único para «el dato falta» (tarjetas, resumen, exportes)
NO_DATA_COLOR = "#64748b"       # gris: el MISMO que usa el Cuerpo Digital (ups_body_visual.NEUTRAL_COLOR)
NOT_MODELED = "no modelado"     # lo que el organismo no calcula (nadie lo calcula): se declara, no se rellena


def _is_num(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


class OrganHealthStatus(Enum):
    """Estados de salud de órganos"""
    CRITICAL = "critical"
    ALERT = "alert"
    NORMAL = "normal"
    OPTIMAL = "optimal"


@dataclass
class OrganMetrics:
    """Métricas de un órgano/sistema. Todo arranca en `None` = «sin dato» (antes 50/50/0, que eran números inventados)."""
    health_score: Optional[float] = None  # 0-100
    activity_level: Optional[float] = None  # 0-100
    risk_score: Optional[float] = None  # 0-100 (heurístico; el corazón NO lo usa: ver risk_points)
    risk_points: Optional[int] = None  # puntos NEWS2 del pulso (0-3), solo corazón: clinical.calculators.news2_pulse_score
    trend: Optional[str] = None  # rising, stable, falling -- nunca se asigna en ningún sitio: «no modelado»
    affected_by: List[str] = field(default_factory=list)  # Otros órganos que lo afectan
    affects: List[str] = field(default_factory=list)  # Órganos que afecta
    predictions: Dict[str, float] = field(default_factory=dict)
    signals: Dict[str, float] = field(default_factory=dict)
    # Cuándo llegaron `signals`. `signals_seq` = número de la llamada a `update_from_sensors()` que las trajo
    # (0 = nunca llegó nada); `signals_at` = su hora. Una entrada solo cuenta como actual si llegó en la actualización
    # ACTUAL (`signals_seq == organismo._update_seq`); una anterior solo puede usarse como ARRASTRE_TEMPORAL dentro de
    # la compuerta temporal del compositor, y pasada esa compuerta no existe.
    signals_seq: int = 0
    signals_at: Optional[datetime] = None


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
    """Estado de respuesta al estrés (transversal, no un órgano anatómico). `None` = sin dato / no modelado."""
    cortisol_level: Optional[float] = None  # μg/dL -- nunca se calcula: no modelado
    acute_stress: Optional[float] = None  # 0-100
    chronic_stress: Optional[float] = None  # 0-100
    inflammatory_markers: Optional[float] = None  # 0-100 -- nunca se calcula: no modelado


@dataclass
class RecoveryState:
    """Capacidad de recuperación (transversal). `None` = sin dato / no modelado."""
    recovery_capacity: Optional[float] = None  # 0-100
    circadian_alignment: Optional[float] = None  # 0-100 -- nunca se calcula: no modelado


@dataclass
class PerformanceState:
    """Capacidad de desempeño físico/cognitivo (transversal, derivado). `None` = sin dato / no modelado."""
    physical_capacity: Optional[float] = None  # 0-100
    cognitive_capacity: Optional[float] = None  # 0-100
    focus_level: Optional[float] = None  # 0-100
    peak_performance_window: Optional[str] = None  # nunca se calcula: no modelado


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
    detail: Optional[Any] = None  # NeurologicalDetail / etc. (el corazón no tiene: CardiacDetail se eliminó)

    @property
    def status(self) -> Optional[OrganHealthStatus]:
        """Estado actual según `health_score`; `None` si no hay (órgano sin alimentar o sin índice: «sin dato»)."""
        score = self.metrics.health_score
        if score is None:
            return None
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
        """Color: gris si no hay dato (mismo gris que el Cuerpo Digital); el corazón se colorea por sus puntos NEWS2."""
        if self.organ_id == "heart":
            points = self.metrics.risk_points
            if points is None:
                return NO_DATA_COLOR
            return {0: "#39ffbe", 1: "#ffd700", 2: "#ffd700", 3: "#ff3333"}[points]
        status = self.status
        if status is None:
            return NO_DATA_COLOR
        status_colors = {
            OrganHealthStatus.CRITICAL: "#ff3333",
            OrganHealthStatus.ALERT: "#ffd700",
            OrganHealthStatus.NORMAL: "#39ffbe",
            OrganHealthStatus.OPTIMAL: "#00ff00",
        }
        return status_colors.get(status, NO_DATA_COLOR)


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
        self._update_seq: int = 0  # número de la última llamada a update_from_sensors() (ver OrganMetrics.signals_seq)
        self.derived_signals: Dict[str, Dict[str, float]] = {}  # hrv_modulation, recovery_need: derivados, NO entradas
        self.input_provenance: Optional[str] = None  # de dónde vienen las entradas (p. ej. «simulación: sliders de Twin OS»)

        # Cross-cutting physiological states (not tied to a single anatomical organ).
        # Ported from the legacy DigitalTwinMultisystem during engine consolidation.
        self.stress = StressState()
        self.recovery = RecoveryState()
        self.performance = PerformanceState()
        self.interactions: List[PhysiologicalInteraction] = self._initialize_interactions()
        self._compute_global_state()  # todo en «sin dato» desde el nacimiento (antes global_state = {} y la UI inventaba 50/BAJO)
    
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
                detail=None,  # CardiacDetail se eliminó (Fase 1, decisión 7): ninguno de sus campos lo calculaba nadie
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
        self._update_seq += 1

        # Actualizar Corazón desde ECG
        if 'ecg' in sensor_data:
            self._update_heart(sensor_data['ecg'])
            self._stamp_inputs("heart")
        
        # Actualizar Cerebro desde EEG
        if 'eeg' in sensor_data:
            self._update_brain(sensor_data['eeg'])
            self._stamp_inputs("brain")
        
        # Actualizar Pulmones desde Respiración + SpO2
        if 'respiratory' in sensor_data:
            self._update_lungs(sensor_data['respiratory'])
            self._stamp_inputs("lungs")
        
        # Actualizar Músculos desde EMG
        if 'emg' in sensor_data:
            self._update_muscles(sensor_data['emg'])
            self._stamp_inputs("muscles")
        
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
    
    def _stamp_inputs(self, organ_id: str) -> None:
        """Marca las señales del órgano como llegadas en la actualización ACTUAL."""
        metrics = self.organs[organ_id].metrics
        metrics.signals_seq = self._update_seq
        metrics.signals_at = datetime.now()

    def inputs_are_current(self, organ_id: str) -> bool:
        """True si las señales del órgano llegaron en la última actualización (no son de una anterior)."""
        metrics = self.organs[organ_id].metrics
        return bool(metrics.signals) and metrics.signals_seq == self._update_seq

    def _update_heart(self, ecg_data: Dict[str, float]) -> None:
        """Actualiza el corazón desde el ECG: SIN defaults (Fase 1, 2026-11-12). `signals` es EXACTAMENTE lo que llegó.
        La única métrica cardiaca son los puntos NEWS2 del pulso (decisión 4), con una sola entrada, `heart_rate`; si no
        llegó, es `None` («sin dato»). Se retiraron `health_score`, `myocardial_stress`, `rhythm_stability`/`complexity`
        (decisiones 1-2), la «actividad» (= FC/100, sin fuente) y los umbrales caseros 40/120 y `hrv < 20` (decisión 4)."""
        heart = self.organs["heart"]
        heart.metrics.signals = dict(ecg_data)

        hr = ecg_data.get("heart_rate")
        heart.metrics.health_score = None
        heart.metrics.activity_level = None
        heart.metrics.risk_score = None
        heart.metrics.risk_points = news2_pulse_score(float(hr)) if _is_num(hr) else None

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
    
    def current_signals(self, organ_id: str) -> Dict[str, float]:
        """Señales del órgano SOLO si llegaron en la actualización actual; si no, `{}` (una entrada vieja no cuenta)."""
        return self.organs[organ_id].metrics.signals if self.inputs_are_current(organ_id) else {}

    def _propagate_physiological_effects(self) -> None:
        """Propaga efectos causales entre órganos, SOLO con entradas actuales y sin defaults. Lo derivado vive en
        `self.derived_signals` (campo propio), ya NO dentro de `signals`: no son entradas. Se retiró `rr_modulation`
        (dependía del riesgo cardiaco casero, retirado en la decisión 4)."""
        self.derived_signals = {}
        brain = self.organs["brain"]
        lungs_signals = self.current_signals("lungs")
        muscle_signals = self.current_signals("muscles")

        # Brain stress → Heart: modulación de HRV (solo si el cerebro tiene un índice calculado con entradas actuales)
        if self.inputs_are_current("brain") and brain.metrics.health_score is not None:
            self.derived_signals.setdefault("heart", {})["hrv_modulation"] = -(100 - brain.metrics.health_score) * 0.3

        # Low SpO2 → Brain: afecta cognición (solo con una SpO2 que LLEGÓ)
        spo2 = lungs_signals.get("spo2")
        if _is_num(spo2) and spo2 < 90 and brain.metrics.health_score is not None:
            brain.metrics.health_score *= 0.8

        # Muscle fatigue → Autonomic: requiere recuperación (solo con una fatiga que LLEGÓ)
        fatigue = muscle_signals.get("fatigue_index")
        if _is_num(fatigue):
            self.derived_signals.setdefault("autonomic", {})["recovery_need"] = fatigue * 0.6

    def _update_autonomic_state(self) -> None:
        """Estado autonómico: depende de la HRV (corazón) y del estrés (cerebro), ambas ACTUALES. Sin ellas, «sin dato»
        (antes `hrv = 50` y `brain.health = 50` por defecto fabricaban un balance autonómico)."""
        autonomic = self.organs["autonomic"]
        hrv = self.current_signals("heart").get("hrv")
        brain_health = self.organs["brain"].metrics.health_score if self.inputs_are_current("brain") else None

        if not _is_num(hrv) or brain_health is None:
            autonomic.metrics.health_score = None
            autonomic.metrics.signals = {}
            return

        brain_stress = 100 - brain_health
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
        """Estados transversales (estrés, recuperación, desempeño): cada uno se calcula solo si llegaron sus entradas
        en la actualización actual; si no, `None` (antes arrancaban en 20/35/75/80/70... sin que nadie los calculara).
        Cortisol, marcadores inflamatorios, alineación circadiana y ventana de desempeño NO se calculan nunca."""
        brain = self.organs["brain"]
        muscles = self.organs["muscles"]
        brain_signals = self.current_signals("brain")
        muscle_signals = self.current_signals("muscles")

        stress_level = brain_signals.get("stress_level")
        if not _is_num(stress_level) and self.inputs_are_current("brain") and brain.metrics.health_score is not None:
            stress_level = 100.0 - brain.metrics.health_score
        if _is_num(stress_level):
            self.stress.acute_stress = min(100.0, max(0.0, stress_level))
            previous = self.stress.chronic_stress
            self.stress.chronic_stress = min(100.0, max(0.0, (
                self.stress.acute_stress if previous is None else previous * 0.9 + self.stress.acute_stress * 0.1
            )))
        else:
            self.stress.acute_stress = None

        fatigue_index = muscle_signals.get("fatigue_index")
        self.recovery.recovery_capacity = (
            min(100.0, max(0.0, 100.0 - fatigue_index)) if _is_num(fatigue_index) else None
        )

        self.performance.physical_capacity = (
            min(100.0, max(0.0, 100.0 - muscles.metrics.risk_score))
            if self.inputs_are_current("muscles") and muscles.metrics.risk_score is not None else None
        )
        self.performance.cognitive_capacity = brain.metrics.health_score if self.inputs_are_current("brain") else None
        self.performance.focus_level = (
            min(100.0, max(0.0, 100.0 - self.stress.acute_stress)) if self.stress.acute_stress is not None else None
        )

    def _compute_global_state(self) -> None:
        """Estado fisiológico global. Fase 1 (Art. I): un índice global solo tiene número si TODOS los órganos de los que
        depende tienen su valor; si alguno falta o fue retirado (el `health_score` cardiaco, decisión 1), el índice es
        `None` («sin dato»). Prohibido promediar órganos sin alimentar. El destino de cada índice (retirarlo o darle
        fuente) lo decide Luis: aquí solo se vuelven honestos."""
        scores = [organ.metrics.health_score for organ in self.organs.values()]
        risks = [organ.metrics.risk_score for organ in self.organs.values()]
        complete_scores = all(s is not None for s in scores)
        complete_risks = all(r is not None for r in risks)

        self.global_state = {
            "global_health_score": float(np.mean(scores)) if complete_scores else None,
            "global_risk_score": float(np.max(risks)) if complete_risks else None,
            "system_coherence": self._compute_system_coherence(),
            "resilience_index": self._compute_resilience(),
            "cognitive_state": self.organs["brain"].metrics.health_score,
            "cardiac_state": None,  # el health_score cardiaco se retiró (decisión 1)
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
    def _compute_risk_level(global_risk_score: Optional[float]) -> str:
        """Nivel de riesgo global; sin puntaje -> «sin dato» (nunca «BAJO» por falta de datos). Único consumidor de
        `global_state["risk_level"]`: `twin_shell/pages.py::render_ambient_header()`, que solo lo muestra."""
        if global_risk_score is None:
            return NO_DATA
        if global_risk_score >= 70:
            return "CRÍTICO"
        elif global_risk_score >= 40:
            return "ALTO"
        elif global_risk_score >= 20:
            return "MODERADO"
        return "BAJO"

    def _detect_anomalies(self) -> Tuple[List[str], List[str], List[str]]:
        """Anomalías, recomendaciones y alertas desde lo que SÍ hay. Cada regla exige su entrada (sin `get(..., 0)`).
        Las frases se enrutan a un órgano por subcadena (`ORGAN_KEYWORDS` en twin_shell/pages.py). Fase 1: la alerta
        cardiaca ya no sale de un `health_score` (retirado) sino de la banda de 3 puntos NEWS2 del pulso."""
        anomalies: List[str] = []
        recommendations: List[str] = []
        alerts: List[str] = []

        heart = self.organs["heart"].metrics
        brain = self.organs["brain"].metrics
        lungs = self.organs["lungs"].metrics
        muscles = self.organs["muscles"].metrics

        if heart.risk_points == 3 and self.inputs_are_current("heart"):
            anomalies.append("Pulso en la banda de 3 puntos NEWS2 (corazón)")
            alerts.append("⚠️ Pulso en la banda de 3 puntos NEWS2 (≤ 40 o ≥ 131 lpm) — corazón")

        brain_stress = self.current_signals("brain").get("stress_level")
        if _is_num(brain_stress) and brain_stress > 75:
            anomalies.append("Estado de estrés elevado detectado")
            recommendations.append("Considera técnicas de relajación")
            alerts.append("⚠️ Niveles de estrés elevados")

        if brain.health_score is not None and brain.health_score < 30:
            anomalies.append("Somnolencia severa o deterioro cognitivo detectado")
            recommendations.append("Toma un descanso o duerme")
            alerts.append("⚠️ Alerta baja - riesgo de fatiga")

        if lungs.health_score is not None and lungs.health_score < 40:
            anomalies.append("Anomalía respiratoria detectada")
            alerts.append("⚠️ SpO₂ bajo o respiración irregular")

        if muscles.health_score is not None and muscles.health_score < 40:
            anomalies.append("Fatiga muscular severa detectada")
            recommendations.append("Se necesita descanso y recuperación")

        neurocardiac = self.global_state.get("neurocardiac_coupling")
        if neurocardiac is not None and neurocardiac < 0.3:
            anomalies.append("Desacoplamiento neurocardíaco detectado")
            alerts.append("⚠️ Coordinación cerebro-corazón afectada")

        cardiorespiratory = self.global_state.get("cardiorespiratory_coupling")
        if cardiorespiratory is not None and cardiorespiratory < 0.3:
            anomalies.append("Desincronización cardiorrespiratoria")
            alerts.append("⚠️ Sincronización corazón-aliento perdida")

        return anomalies, recommendations, alerts

    def _compute_couplings(self) -> Dict[str, Optional[float]]:
        """Acoplamientos inter-sistémicos (neurocardiaco, cardiorespiratorio, neuromuscular). Fase 1: la compuerta exige
        entradas REALES de AMBOS órganos en la actualización actual; sin ellas el acoplamiento es `None` («sin dato»).
        Se eliminaron la base 0.5 y los defaults (`hr 70`, `rr 16`, `hrv 50`, `alpha 50`, `fatigue 50`); la compuerta
        ya no es «hay algo en signals» (que `hrv_modulation` volvía siempre verdadera)."""
        heart_signals = self.current_signals("heart")
        brain_signals = self.current_signals("brain")
        lungs_signals = self.current_signals("lungs")
        muscles_signals = self.current_signals("muscles")

        couplings: Dict[str, Optional[float]] = {
            "neurocardiac_coupling": None,
            "cardiorespiratory_coupling": None,
            "neuromuscular_coupling": None,
        }

        alpha, hrv = brain_signals.get("alpha_power"), heart_signals.get("hrv")
        if _is_num(alpha) and _is_num(hrv):
            expected_hrv_from_relaxation = 50 + (alpha / 100) * 50
            coupling = 1.0 - abs(hrv - expected_hrv_from_relaxation) / 100
            couplings["neurocardiac_coupling"] = max(0.0, min(1.0, coupling))

        hr, rr = heart_signals.get("heart_rate"), lungs_signals.get("respiratory_rate")
        if _is_num(hr) and _is_num(rr):
            optimal_ratio = 4.0
            actual_ratio = hr / (rr + 1e-6)
            coupling = 1.0 - abs(actual_ratio - optimal_ratio) / optimal_ratio
            couplings["cardiorespiratory_coupling"] = max(0.0, min(1.0, coupling))

        cognitive_state = self.organs["brain"].metrics.health_score if self.inputs_are_current("brain") else None
        emg_fatigue = muscles_signals.get("fatigue_index")
        if cognitive_state is not None and _is_num(emg_fatigue):
            expected_fatigue = cognitive_state * 0.7
            coupling = 1.0 - abs(emg_fatigue - expected_fatigue) / 100
            couplings["neuromuscular_coupling"] = max(0.0, min(1.0, coupling))

        return couplings

    def _compute_system_coherence(self) -> Optional[float]:
        """Coherencia = 100 - desviación estándar de los `health_score` de TODOS los órganos; sin el de alguno, `None`."""
        scores = [organ.metrics.health_score for organ in self.organs.values()]
        if any(s is None for s in scores):
            return None
        return float(max(0, 100 - np.std(scores)))

    def _compute_resilience(self) -> Optional[float]:
        """Resiliencia = 0.4·salud global + 0.3·(100 − riesgo global) + 0.3·HRV; si falta alguno de los tres, `None`."""
        global_health = self.global_state.get("global_health_score")
        global_risk = self.global_state.get("global_risk_score")
        hrv = self.current_signals("heart").get("hrv")
        if global_health is None or global_risk is None or not _is_num(hrv):
            return None
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
                    "risk_points": organ.metrics.risk_points,
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
        """Explicación en lenguaje natural del estado actual; lo que falta dice «sin dato» (nunca 0 ni «BAJO»)."""
        g = self.global_state

        def fmt(value: Optional[float], suffix: str) -> str:
            return NO_DATA if value is None else f"{value:.0f}{suffix}"

        return (
            f"Estado Fisiológico Global: {fmt(g.get('global_health_score'), '/100')}\n"
            f"Nivel de Riesgo: {g.get('risk_level', NO_DATA)}\n"
            f"Coherencia Sistémica: {fmt(g.get('system_coherence'), '%')}\n"
            f"Resiliencia: {fmt(g.get('resilience_index'), '/100')}"
        )

    def _refresh_heart_points(self) -> None:
        hr = self.organs["heart"].metrics.signals.get("heart_rate")
        self.organs["heart"].metrics.risk_points = news2_pulse_score(float(hr)) if _is_num(hr) else None

    def simulate_intervention(self, intervention: str, intensity: float = 0.5) -> Dict[str, float]:
        """
        Simula una intervención médica sobre el organismo (no toca el estado real del
        paciente — solo esta instancia simulada). Fase 1 (Art. I): cada efecto se aplica solo si existe el valor
        sobre el que actúa (sin `get(..., 70/98/16/20)`); lo que no existe no se inventa para poder modificarlo.

        Args:
            intervention: "oxygen", "sedation", "exercise" o "rest".
            intensity: 0-1.
        """
        heart, lungs, brain, muscles = (
            self.organs["heart"], self.organs["lungs"], self.organs["brain"], self.organs["muscles"]
        )
        changes: Dict[str, float] = {}
        hr = heart.metrics.signals.get("heart_rate")
        spo2 = lungs.metrics.signals.get("spo2")
        rr = lungs.metrics.signals.get("respiratory_rate")
        fatigue = muscles.metrics.signals.get("fatigue_index")

        if intervention == "oxygen":
            if _is_num(spo2):
                if lungs.detail is not None:
                    lungs.detail.tissue_oxygenation = min(100.0, lungs.detail.tissue_oxygenation + intensity * 15)
                new_spo2 = min(100.0, spo2 + intensity * 8)
                lungs.metrics.signals["spo2"] = new_spo2
                changes['spo2'] = new_spo2
            if brain.detail is not None and brain.metrics.health_score is not None:
                brain.detail.cognitive_fatigue = max(0.0, brain.detail.cognitive_fatigue - intensity * 10)

        elif intervention == "sedation":
            if self.stress.acute_stress is not None:
                new_stress = max(0.0, self.stress.acute_stress - intensity * 40)
                self.stress.acute_stress = new_stress
                changes['stress'] = new_stress
            autonomic = self.organs["autonomic"]
            if autonomic.detail is not None and autonomic.metrics.health_score is not None:
                autonomic.detail.sympathetic_activity = max(0.0, autonomic.detail.sympathetic_activity - intensity * 30)
            if _is_num(hr):
                heart.metrics.signals["heart_rate"] = max(50.0, hr - intensity * 20)

        elif intervention == "exercise":
            if _is_num(hr):
                new_hr = min(180.0, hr + intensity * 40)
                heart.metrics.signals["heart_rate"] = new_hr
                changes['heart_rate'] = new_hr
            if _is_num(fatigue):
                muscles.metrics.signals["fatigue_index"] = min(100.0, fatigue + intensity * 30)
            if _is_num(rr):
                lungs.metrics.signals["respiratory_rate"] = rr + intensity * 8

        elif intervention == "rest":
            if self.recovery.recovery_capacity is not None:
                new_recovery = min(100.0, self.recovery.recovery_capacity + intensity * 20)
                self.recovery.recovery_capacity = new_recovery
                changes['recovery'] = new_recovery
            if self.stress.acute_stress is not None:
                self.stress.acute_stress = max(0.0, self.stress.acute_stress - intensity * 30)
            if _is_num(fatigue):
                muscles.metrics.signals["fatigue_index"] = max(0.0, fatigue - intensity * 15)

        self._refresh_heart_points()
        self._propagate_physiological_effects()
        self._compute_global_state()
        return changes

    def generate_clinical_summary(self) -> str:
        """Resumen clínico legible del organismo. Lo que falta dice «sin dato» (antes `0.0 bpm`, `5.0 L/min`, `85 %`);
        lo que nadie calcula dice «no modelado»; cada número lleva su procedencia entre corchetes."""
        heart, brain, lungs, muscles, autonomic = (
            self.organs["heart"], self.organs["brain"], self.organs["lungs"],
            self.organs["muscles"], self.organs["autonomic"],
        )

        def num(value: Any, unit: str = "", tag: str = "", digits: int = 1) -> str:
            if not _is_num(value):
                return NO_DATA
            return f"{value:.{digits}f}{unit}" + (f"  [{tag}]" if tag else "")

        fed = lambda organ: organ.metrics.health_score is not None   # detalle solo si el órgano tiene un índice calculado
        nd, rd, md, ad = brain.detail, lungs.detail, muscles.detail, autonomic.detail
        entrada = "entrada"
        heur = "heurístico BIOCORE"
        hr_signal = heart.metrics.signals.get("heart_rate")
        points = heart.metrics.risk_points
        stress = self.stress.acute_stress if self.stress.acute_stress is not None else None

        return f"""
╔════════════════════════════════════════════════════════════════════════════╗
║                    RESUMEN CLÍNICO DEL GEMELO DIGITAL                      ║
║                          {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}                              ║
╚════════════════════════════════════════════════════════════════════════════╝
Procedencia de las entradas: {self.input_provenance or 'sin declarar'}

🫀 SISTEMA CARDIOVASCULAR:
   • Frecuencia Cardíaca: {num(hr_signal, ' bpm', entrada)}
   • Variabilidad (HRV): {num(heart.metrics.signals.get('hrv'), ' ms', entrada)}
   • Puntos NEWS2 del pulso: {NO_DATA if points is None else f'{points} de 3  [NEWS2, RCP 2017]'}
   • Gasto Cardíaco: {NOT_MODELED}

🧠 SISTEMA NEUROLÓGICO:
   • Salud General: {num(brain.metrics.health_score, '%', heur)}
   • Carga Cognitiva: {num(nd.mental_workload if fed(brain) else None, '%', heur)}
   • Fatiga Cognitiva: {num(nd.cognitive_fatigue if fed(brain) else None, '%', heur)}

💨 SISTEMA RESPIRATORIO / OXIGENACIÓN:
   • Frecuencia Respiratoria: {num(lungs.metrics.signals.get('respiratory_rate'), ' resp/min', entrada)}
   • SpO₂: {num(lungs.metrics.signals.get('spo2'), '%', entrada)}
   • Riesgo de Apnea: {num(rd.apnea_risk if fed(lungs) else None, '%', heur)}
   • Riesgo de Hipoxia: {num(rd.hypoxia_risk if fed(lungs) else None, '%', heur)}

🦾 SISTEMA MUSCULOESQUELÉTICO:
   • Índice de Fatiga: {num(muscles.metrics.signals.get('fatigue_index'), '%', entrada)}
   • Eficiencia Neuromuscular: {num(md.neuromuscular_efficiency if fed(muscles) else None, '%', heur)}

🔄 SISTEMA AUTONÓMICO:
   • Actividad Simpática: {num(ad.sympathetic_activity if fed(autonomic) else None, '%', heur)}
   • Actividad Parasimpática: {num(ad.parasympathetic_activity if fed(autonomic) else None, '%', heur)}

⚡ RECUPERACIÓN Y RENDIMIENTO:
   • Capacidad de Recuperación: {num(self.recovery.recovery_capacity, '%', heur)}
   • Estrés Agudo: {num(stress, '%', heur)}
   • Desempeño Físico: {num(self.performance.physical_capacity, '%', heur)}
   • Desempeño Cognitivo: {num(self.performance.cognitive_capacity, '%', heur)}

════════════════════════════════════════════════════════════════════════════════
"""

    def to_json(self) -> str:
        """Estado completo (órganos + estados transversales) a JSON. Lo que falta se exporta como «sin dato» y lo que
        nadie calcula como «no modelado» (antes salían los defaults: 5.0, 85.0, 50.0...)."""

        def clean(value: Any) -> Any:
            if value is None:
                return NO_DATA
            if isinstance(value, dict):
                return {k: clean(v) for k, v in value.items()}
            return value

        state = {
            'timestamp': self.timestamp.isoformat(),
            'input_provenance': self.input_provenance or "sin declarar",
            'global_state': clean(self.global_state),
            'organs': {
                organ_id: {
                    'health_score': organ.metrics.health_score,
                    'risk_score': organ.metrics.risk_score,
                    'risk_points_news2': organ.metrics.risk_points,
                    'signals': organ.metrics.signals,
                    'detail': (organ.detail.__dict__ if organ.metrics.health_score is not None else NO_DATA)
                    if organ.detail is not None else NOT_MODELED,
                }
                for organ_id, organ in self.organs.items()
            },
            'derived_signals': self.derived_signals,
            'stress': self.stress.__dict__,
            'recovery': self.recovery.__dict__,
            'performance': self.performance.__dict__,
        }
        state['organs'] = {k: clean(v) for k, v in state['organs'].items()}
        for key in ('stress', 'recovery', 'performance'):
            state[key] = clean(state[key])
        state['stress']['cortisol_level'] = state['stress']['inflammatory_markers'] = NOT_MODELED
        state['recovery']['circadian_alignment'] = state['performance']['peak_performance_window'] = NOT_MODELED
        return json.dumps(state, indent=2, default=str)

    def create_patient_scenario(self, scenario: str) -> None:
        """
        Aplica un preset de paciente (healthy, hypertension, copd)
        directamente a las señales/detalles de los órganos correspondientes.
        """
        from src.clinical.healthy_baseline import instance as _healthy_instance
        _H = _healthy_instance()  # semilla de referencia: valores nominales
        scenarios: Dict[str, Dict[str, Dict[str, float]]] = {
            # Unificación 4: los valores de "sano" son los nominales de la fuente única (antes HRV 60 aquí y 50 en el motor).
            'healthy': {
                'ecg': {'heart_rate': _H['hr'], 'hrv': _H['hrv']},
                'respiratory': {'respiratory_rate': _H['respiratory_rate'], 'spo2': _H['spo2']},
                'eeg': {'stress_level': _H['stress_level']}, 'emg': {'fatigue_index': _H['fatigue_index'], 'efficiency': 90},
            },
            'hypertension': {
                'ecg': {'heart_rate': 85, 'hrv': 40}, 'eeg': {'stress_level': 55},
            },
            'copd': {
                'respiratory': {'respiratory_rate': 22, 'spo2': 88, 'ahi': 3},
            },
        }

        if scenario == 'arrhythmia':
            raise ValueError(
                "El preset 'arrhythmia' se retiró (Unificación 1): 'arritmia' no es un diagnóstico. "
                "Usa apply_arrhythmia(tipo, semilla) con un tipo de arrhythmia_types.ARRHYTHMIA_TYPES."
            )
        if scenario == 'sepsis':
            raise ValueError(
                "El preset 'sepsis' (FC 110, FR 28, SpO2 92) se retiró (Unificación 2): era un punto "
                "arbitrario de una evolución. Usa apply_sepsis(horizonte) con un horizonte de la trayectoria "
                "canónica src/clinical/sepsis_trajectory.py."
            )
        config = scenarios.get(scenario)
        if config is None:
            return
        self.current_scenario = scenario
        self.update_from_sensors(config)

    def apply_arrhythmia(self, type_key: str, seed: int = 0) -> str:
        """Aplica un tipo de arritmia de la fuente única (`src/signals/ecg/arrhythmia_types.py`): solo la FC de la
        instancia (tipo, semilla) en el horizonte inicial. Devuelve el texto de variabilidad declarada (rango, semilla,
        FC) para que la UI lo muestre. Fase 1: la FC es la ÚNICA entrada de esta actualización; ya no se reenvían las
        señales vigentes (HRV...) como si fueran nuevas -- una entrada anterior no se vuelve actual por reenviarla."""
        from src.signals.ecg.arrhythmia_types import declare_instance, instance_hr

        self.current_scenario = f"arrhythmia_{type_key}"
        self.input_provenance = "simulación (instancia de la fuente única de arritmias)"
        self.update_from_sensors({'ecg': {'heart_rate': instance_hr(type_key, seed)}})
        return declare_instance(type_key, seed, (0,))

    def apply_sepsis(self, horizon: str = 'now') -> str:
        """Aplica un PUNTO de la trayectoria canónica de sepsis (`src/clinical/sepsis_trajectory.py`) --
        FC, HRV, FR, SpO2 y estrés de ese horizonte, el mismo valor que el `SimulationEngine` da en él.
        Devuelve la fase del punto y su declaración de PA para que la UI la muestre. Fase 1: solo se envía lo que el
        horizonte define; ya no se reenvían las demás señales vigentes como si fueran nuevas."""
        from src.clinical import sepsis_trajectory as sepsis

        v = sepsis.horizon_vitals(horizon)
        self.current_scenario = f"sepsis:{horizon}"
        self.input_provenance = "simulación (trayectoria canónica de sepsis)"
        self.update_from_sensors({
            'ecg': {'heart_rate': v['hr'], 'hrv': v['hrv']},
            'respiratory': {'respiratory_rate': v['respiratory_rate'], 'spo2': v['spo2']},
            'eeg': {'stress_level': v['stress_level']},
        })
        return f"Sepsis, horizonte {horizon} (fase {sepsis.phase_of(horizon)}): {sepsis.pa_phase_note(sepsis.phase_of(horizon))}"
