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

Cierre de la fase 0 (2026-11-13, Art. I), con la misma lógica en los demás órganos (decisiones firmadas por Luis):
- Pulmones: sin defaults (`ahi = 0` fuera). `hypoxia_risk` y el riesgo respiratorio se sustituyen por los puntos NEWS2
  de SpO₂ (escala 1, `news2_spo2_scale1_score`) y de FR (`news2_respiratory_rate_score`); la escala 2 es «no modelada».
  El índice de salud pulmonar (pesos propios, sin cita) solo se calcula si llegaron FR, SpO₂ y AHI, los tres.
- Cerebro, músculos y autonómico: se retiran sus `health_score`/`risk_score` (sin cita) y los umbrales autonómicos
  caseros (HRV < 15/30). Lo que sí se mide se muestra como lo que es (la HRV como HRV, el estrés como la entrada que es).
- Campos fantasma de los detalles (`NeurologicalDetail`, `RespiratoryDetail`, `MusculoskeletalDetail`,
  `AutonomicDetail`) y los estados transversales (estrés/recuperación/desempeño, copias con otro nombre de las
  entradas o dependientes de índices retirados): limpieza total, como `CardiacDetail`.
- Índices globales: se RETIRAN el estado fisiológico global, la coherencia sistémica, la resiliencia y los
  acoplamientos Cerebro↔Corazón y Cerebro↔Músculos (decisión 1). El riesgo global se retira como número: en su lugar
  un NEWS2 PARCIAL (puntos por parámetro disponible y lista explícita de lo que falta para el total; nunca un total,
  decisión 2). Corazón↔Pulmones es la razón FC:FR como número descriptivo (decisión 3, cita en `clinical/calculators`).
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
import json
import math
from datetime import datetime, timedelta

from clinical.calculators import (
    NEWS2_PARAMETERS_NOT_MODELED,
    PRQ_REST_REFERENCE_TEXT,
    News2Partial,
    news2_partial,
    news2_pulse_score,
    news2_respiratory_rate_score,
    news2_spo2_scale1_score,
    pulse_respiration_quotient,
)

NO_DATA = "sin dato"            # texto único para «el dato falta» (tarjetas, resumen, exportes)
NO_DATA_COLOR = "#64748b"       # gris: el MISMO que usa el Cuerpo Digital (ups_body_visual.NEUTRAL_COLOR)
HAS_DATA_COLOR = "#39d98a"      # verde del Cuerpo Digital (ups_body_visual.STABLE_COLOR): hay entrada, sin criterio que la puntúe
NOT_MODELED = "no modelado"     # lo que el organismo no calcula (nadie lo calcula): se declara, no se rellena

# Puntos NEWS2 (0-3) -> color de órgano. Un solo mapa para pulso, FR y SpO₂.
NEWS2_POINTS_COLOR = {0: "#39ffbe", 1: "#ffd700", 2: "#ffd700", 3: "#ff3333"}


def _is_num(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


class OrganHealthStatus(Enum):
    """Estados de salud de órganos (hoy solo los pulmones tienen un índice que clasificar)."""
    CRITICAL = "critical"
    ALERT = "alert"
    NORMAL = "normal"
    OPTIMAL = "optimal"


@dataclass
class OrganMetrics:
    """Métricas de un órgano/sistema. Todo arranca en `None` = «sin dato» (antes 50/50/0, que eran números inventados).
    No hay `risk_score`, `activity_level`, `trend` ni `detail`: eran heurísticas sin cita, copias de una entrada o
    campos que nadie asignaba (retirados en la fase 0)."""
    health_score: Optional[float] = None  # 0-100; SOLO pulmones (FR + SpO₂ + AHI, los tres presentes)
    risk_points: Optional[int] = None  # puntos NEWS2 del pulso (0-3), solo corazón: clinical.calculators.news2_pulse_score
    rr_points: Optional[int] = None  # puntos NEWS2 de la FR (0-3), solo pulmones: news2_respiratory_rate_score
    spo2_points: Optional[int] = None  # puntos NEWS2 de la SpO₂ escala 1 (0-3), solo pulmones: news2_spo2_scale1_score
    affected_by: List[str] = field(default_factory=list)  # Otros órganos que lo afectan
    affects: List[str] = field(default_factory=list)  # Órganos que afecta
    signals: Dict[str, float] = field(default_factory=dict)
    # Cuándo llegaron `signals`. `signals_seq` = número de la llamada a `update_from_sensors()` que las trajo
    # (0 = nunca llegó nada); `signals_at` = su hora. Una entrada solo cuenta como actual si llegó en la actualización
    # ACTUAL (`signals_seq == organismo._update_seq`); una anterior solo puede usarse como ARRASTRE_TEMPORAL dentro de
    # la compuerta temporal del compositor, y pasada esa compuerta no existe.
    signals_seq: int = 0
    signals_at: Optional[datetime] = None


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

    @property
    def status(self) -> Optional[OrganHealthStatus]:
        """Estado según `health_score` (solo pulmones); `None` si no hay («sin dato»)."""
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
        """Color: gris si no hay dato (mismo gris que el Cuerpo Digital). Corazón y pulmones se colorean por sus puntos
        NEWS2 (el peor de FR/SpO₂ en los pulmones); los órganos sin criterio con fuente se pintan «con dato» (verde
        del Cuerpo Digital) cuando tienen una entrada y nunca se gradúan."""
        m = self.metrics
        if self.organ_id == "heart":
            return NO_DATA_COLOR if m.risk_points is None else NEWS2_POINTS_COLOR[m.risk_points]
        if self.organ_id == "lungs":
            points = [p for p in (m.rr_points, m.spo2_points) if p is not None]
            return NO_DATA_COLOR if not points else NEWS2_POINTS_COLOR[max(points)]
        return HAS_DATA_COLOR if m.signals else NO_DATA_COLOR


class DigitalTwinOrganism:
    """
    Representación viva y computacional del cuerpo humano.
    Centro absoluto de BIOCORE AI.
    """

    def __init__(self):
        self.timestamp = datetime.now()
        self.organs: Dict[str, OrganSystem] = self._initialize_organs()
        self.connections: List[Tuple[str, str, str]] = self._initialize_connections()  # (from, to, type)
        self.global_state: Dict[str, Any] = {}
        self.history: List[Dict] = []
        self.max_history = 500
        self.current_scenario: Optional[str] = None
        self.simulation_mode: bool = False
        self.timeline_events: List[Dict] = []
        self._update_seq: int = 0  # número de la última llamada a update_from_sensors() (ver OrganMetrics.signals_seq)
        self.input_provenance: Optional[str] = None  # de dónde vienen las entradas (p. ej. «simulación: sliders de Twin OS»)
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
            ),
            "heart": OrganSystem(
                name="Corazón",
                organ_id="heart",
                education={
                    "es": "Bomba fisiológica. Mantiene perfusión sistémica y homeostasis.",
                    "pathophysiology": "Disfunción cardíaca reduce oxigenación y causa deterioro multisistémico.",
                },
                pathologies=["Infarto", "Arritmia", "Insuficiencia", "Hipertensión"],
            ),
            "lungs": OrganSystem(
                name="Pulmones",
                organ_id="lungs",
                education={
                    "es": "Intercambio gaseoso. Vital para oxigenación y equilibrio ácido-base.",
                    "pathophysiology": "Hipoxia causa disfunción cerebral, cardiaca y muscular secuenciales.",
                },
                pathologies=["EPOC", "Apnea", "Neumonía", "Asma", "Embolia"],
            ),
            "muscles": OrganSystem(
                name="Músculos",
                organ_id="muscles",
                education={
                    "es": "Sistema motriz. Genera movimiento, genera calor, protege.",
                    "pathophysiology": "Fatiga muscular refleja estrés sistémico y falta de recuperación.",
                },
                pathologies=["Miopatía", "Distrofia", "Fatiga crónica"],
            ),
            "autonomic": OrganSystem(
                name="Sistema Nervioso Autónomo",
                organ_id="autonomic",
                education={
                    "es": "Control automático. Simpático (fight) vs Parasimpático (rest).",
                    "pathophysiology": "Desequilibrio autonómico causa disregulación de HR, respiración y digestion.",
                },
                pathologies=["Disautonomía", "POTS", "Síncope", "Disfunción erectil"],
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

        # Actualizar la vista autonómica (la HRV del corazón, como HRV)
        self._update_autonomic_state()

        # Calcular estado global (NEWS2 parcial, razón FC:FR, alertas)
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

    def current_signals(self, organ_id: str) -> Dict[str, float]:
        """Señales del órgano SOLO si llegaron en la actualización actual; si no, `{}` (una entrada vieja no cuenta)."""
        return self.organs[organ_id].metrics.signals if self.inputs_are_current(organ_id) else {}

    def _update_heart(self, ecg_data: Dict[str, float]) -> None:
        """Actualiza el corazón desde el ECG: SIN defaults (Fase 1, 2026-11-12). `signals` es EXACTAMENTE lo que llegó.
        La única métrica cardiaca son los puntos NEWS2 del pulso (decisión 4), con una sola entrada, `heart_rate`; si no
        llegó, es `None` («sin dato»). Se retiraron `health_score`, `myocardial_stress`, `rhythm_stability`/`complexity`
        (decisiones 1-2), la «actividad» (= FC/100, sin fuente) y los umbrales caseros 40/120 y `hrv < 20` (decisión 4)."""
        heart = self.organs["heart"]
        heart.metrics.signals = dict(ecg_data)
        hr = ecg_data.get("heart_rate")
        heart.metrics.risk_points = news2_pulse_score(float(hr)) if _is_num(hr) else None

    def _update_brain(self, eeg_data: Dict[str, float]) -> None:
        """Actualiza el cerebro desde el EEG: `signals` es EXACTAMENTE lo que llegó (potencias de banda medidas, o el
        `stress_level` de un slider declarado como simulación). Fase 0: sin `health_score`/`risk_score` (fórmulas con
        defaults 65/35 y umbrales 50/75 sin cita), sin «actividad» (= beta/50) y sin `NeurologicalDetail` (carga
        cognitiva = beta con otro nombre, atención/somnolencia/fatiga cognitiva inventadas, 6 campos nunca asignados)."""
        self.organs["brain"].metrics.signals = dict(eeg_data)

    def _update_lungs(self, resp_data: Dict[str, float]) -> None:
        """Actualiza los pulmones: SIN defaults (`ahi = 0`, `rr = 16`, `spo2 = 98` fuera). Puntos NEWS2 de la FR y de
        la SpO₂ (escala 1), cada uno con su única entrada; el índice de salud (pesos propios, sin cita) solo si llegaron
        FR, SpO₂ y AHI, los tres. Se retiraron `risk_score` (umbrales 90/95 y AHI 5/20 propios), `hypoxia_risk`
        (sustituido por los puntos de SpO₂) y `RespiratoryDetail` (`apnea_risk` = AHI × 3.33, `perfusion_index`/
        `tissue_oxygenation` = SpO₂ con otro nombre, y 4 campos nunca asignados)."""
        lungs = self.organs["lungs"]
        lungs.metrics.signals = dict(resp_data)
        rr, spo2, ahi = resp_data.get("respiratory_rate"), resp_data.get("spo2"), resp_data.get("ahi")

        lungs.metrics.rr_points = news2_respiratory_rate_score(math.floor(float(rr) + 0.5)) if _is_num(rr) else None
        lungs.metrics.spo2_points = news2_spo2_scale1_score(float(spo2)) if _is_num(spo2) else None

        if _is_num(rr) and _is_num(spo2) and _is_num(ahi):
            # Heurística BIOCORE (sin cita en los pesos): centros de referencia FR 16 y SpO₂ 100 %, AHI 30 = 100 %.
            rr_penalty = abs(rr - 16) / 16 * 0.3
            spo2_score = min(100, (spo2 / 100) * 100)
            ahi_penalty = min(100, ahi / 30 * 100) * 0.4
            lungs.metrics.health_score = max(0, (spo2_score * 0.5 + (100 - rr_penalty * 100) * 0.3 - ahi_penalty))
        else:
            lungs.metrics.health_score = None

    def _update_muscles(self, emg_data: Dict[str, float]) -> None:
        """Actualiza los músculos desde el EMG: `signals` es EXACTAMENTE lo que llegó (`activation` y
        `median_frequency` medidas por el EMG Lab, o el `fatigue_index` de un slider). Fase 0: sin `health_score`/
        `risk_score` (fórmula con defaults 70/20 y umbrales 50/80 sin cita) ni `MusculoskeletalDetail`
        (`neuromuscular_efficiency` = `efficiency` con otro nombre, `movement_smoothness` = 100 − fatiga, 3 campos
        nunca asignados)."""
        self.organs["muscles"].metrics.signals = dict(emg_data)

    def _update_autonomic_state(self) -> None:
        """El sistema autonómico no tiene entradas propias: muestra la HRV del corazón COMO HRV, con la misma marca de
        actualidad que el corazón. Fase 0: se retiraron el `health_score` autonómico (HRV × (1 − estrés) sin cita), los
        umbrales HRV < 15/30 y `AutonomicDetail` (LF/HF y flexibilidad nunca calculadas; simpático = estrés con otro
        nombre)."""
        autonomic = self.organs["autonomic"]
        heart = self.organs["heart"].metrics
        hrv = heart.signals.get("hrv")
        if _is_num(hrv):
            autonomic.metrics.signals = {"hrv": hrv}
            autonomic.metrics.signals_seq = heart.signals_seq
            autonomic.metrics.signals_at = heart.signals_at
        else:
            autonomic.metrics.signals = {}

    def _compute_global_state(self) -> None:
        """Estado global = lo que se puede decir con fuente a partir de lo que llegó en la actualización ACTUAL:
        - `news2_partial`: puntos NEWS2 por parámetro disponible (pulso, FR, SpO₂ escala 1) y lo que falta para el
          total (decisión 2; nunca un total);
        - `hr_rr_ratio`: razón FC:FR, número descriptivo (decisión 3; referencia en reposo con cita en calculators);
        - alertas/anomalías/recomendaciones.
        Retirados (decisión 1): estado fisiológico global, riesgo global como número, coherencia sistémica, resiliencia
        y los acoplamientos Cerebro↔Corazón y Cerebro↔Músculos."""
        heart = self.current_signals("heart")
        lungs = self.current_signals("lungs")
        hr, rr, spo2 = heart.get("heart_rate"), lungs.get("respiratory_rate"), lungs.get("spo2")
        partial = news2_partial(
            pulse=float(hr) if _is_num(hr) else None,
            respiratory_rate=float(rr) if _is_num(rr) else None,
            spo2=float(spo2) if _is_num(spo2) else None,
        )
        self.global_state = {
            "news2_partial": partial,
            "hr_rr_ratio": pulse_respiration_quotient(hr, rr) if _is_num(hr) and _is_num(rr) else None,
        }
        anomalies, recommendations, alerts = self._detect_anomalies()
        self.global_state["anomalies"] = anomalies
        self.global_state["recommendations"] = recommendations
        self.global_state["alerts"] = alerts

    def _detect_anomalies(self) -> Tuple[List[str], List[str], List[str]]:
        """Anomalías, recomendaciones y alertas desde lo que SÍ hay y tiene fuente: la banda de 3 puntos NEWS2 del pulso,
        de la FR y de la SpO₂ (escala 1), y el estrés > 75 (mismo umbral que el evento `HIGH_STRESS_EEG` del UPS).
        Las frases se enrutan a un órgano por subcadena (`ORGAN_KEYWORDS` en twin_shell/pages.py)."""
        anomalies: List[str] = []
        recommendations: List[str] = []
        alerts: List[str] = []

        heart = self.organs["heart"].metrics
        lungs = self.organs["lungs"].metrics

        if heart.risk_points == 3 and self.inputs_are_current("heart"):
            anomalies.append("Pulso en la banda de 3 puntos NEWS2 (corazón)")
            alerts.append("⚠️ Pulso en la banda de 3 puntos NEWS2 (≤ 40 o ≥ 131 lpm) — corazón")

        if self.inputs_are_current("lungs"):
            if lungs.rr_points == 3:
                anomalies.append("Frecuencia respiratoria en la banda de 3 puntos NEWS2 (respiratorio)")
                alerts.append("⚠️ Frecuencia respiratoria en la banda de 3 puntos NEWS2 (≤ 8 o ≥ 25 resp/min) — pulmones")
            if lungs.spo2_points == 3:
                anomalies.append("SpO₂ en la banda de 3 puntos NEWS2, escala 1 (respiratorio)")
                alerts.append("⚠️ SpO₂ ≤ 91 % (3 puntos NEWS2, escala 1) — pulmones")

        brain_stress = self.current_signals("brain").get("stress_level")
        if _is_num(brain_stress) and brain_stress > 75:
            anomalies.append("Estado de estrés elevado detectado")
            recommendations.append("Considera técnicas de relajación")
            alerts.append("⚠️ Niveles de estrés elevados")

        return anomalies, recommendations, alerts

    def _add_to_history(self) -> None:
        """Agrega el momento actual a la historia: la FC y sus puntos NEWS2 (decisión 4: la línea de tiempo es FC y
        puntos de pulso en el tiempo), `None` cuando no hay FC actual."""
        heart = self.organs["heart"].metrics
        hr = self.current_signals("heart").get("heart_rate")
        self.history.append({
            "timestamp": self.timestamp.isoformat(),
            "heart_rate": float(hr) if _is_num(hr) else None,
            "news2_pulse_points": heart.risk_points if _is_num(hr) else None,
        })
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

    def news2_partial_text(self) -> str:
        """Texto único del NEWS2 parcial (resumen, `explain_state`, exportes): componentes disponibles y lo que falta.
        Nunca un total."""
        partial: News2Partial = self.global_state["news2_partial"]
        if not partial.available:
            return f"NEWS2 parcial: {NO_DATA} (sin pulso, FR ni SpO₂ actuales)"
        parts = " · ".join(f"{name} {points}" for name, points in partial.components.items())
        return f"NEWS2 parcial (sin total): {parts} · faltan para el total: {', '.join(partial.missing)}"

    def explain_state(self) -> str:
        """Explicación en lenguaje natural del estado actual; lo que falta dice «sin dato» (nunca 0 ni «BAJO»)."""
        ratio = self.global_state.get("hr_rr_ratio")
        return (
            f"{self.news2_partial_text()}\n"
            f"Razón FC:FR: {NO_DATA if ratio is None else f'{ratio:.1f} : 1'}"
        )

    def _recompute_from_signals(self) -> None:
        """Vuelve a calcular puntos/índices a partir de las señales vigentes SIN declararlas nuevas (la marca de
        actualidad no cambia): lo usa `simulate_intervention`."""
        self._update_heart(self.organs["heart"].metrics.signals)
        self._update_lungs(self.organs["lungs"].metrics.signals)
        self._update_autonomic_state()
        self._compute_global_state()

    def simulate_intervention(self, intervention: str, intensity: float = 0.5) -> Dict[str, float]:
        """
        Simula una intervención médica sobre el organismo (no toca el estado real del
        paciente — solo esta instancia simulada). Fase 1 (Art. I): cada efecto se aplica solo si existe el valor
        sobre el que actúa (sin `get(..., 70/98/16/20)`); lo que no existe no se inventa para poder modificarlo. Fase 0:
        solo actúa sobre entradas (FC, SpO₂, FR, fatiga); los estados transversales que antes modificaba se retiraron.

        Args:
            intervention: "oxygen", "sedation", "exercise" o "rest".
            intensity: 0-1.
        """
        heart, lungs, muscles = self.organs["heart"], self.organs["lungs"], self.organs["muscles"]
        changes: Dict[str, float] = {}
        hr = heart.metrics.signals.get("heart_rate")
        spo2 = lungs.metrics.signals.get("spo2")
        rr = lungs.metrics.signals.get("respiratory_rate")
        fatigue = muscles.metrics.signals.get("fatigue_index")

        if intervention == "oxygen":
            if _is_num(spo2):
                new_spo2 = min(100.0, spo2 + intensity * 8)
                lungs.metrics.signals["spo2"] = new_spo2
                changes['spo2'] = new_spo2

        elif intervention == "sedation":
            if _is_num(hr):
                new_hr = max(50.0, hr - intensity * 20)
                heart.metrics.signals["heart_rate"] = new_hr
                changes['heart_rate'] = new_hr

        elif intervention == "exercise":
            if _is_num(hr):
                new_hr = min(180.0, hr + intensity * 40)
                heart.metrics.signals["heart_rate"] = new_hr
                changes['heart_rate'] = new_hr
            if _is_num(fatigue):
                muscles.metrics.signals["fatigue_index"] = min(100.0, fatigue + intensity * 30)
                changes['fatigue_index'] = muscles.metrics.signals["fatigue_index"]
            if _is_num(rr):
                lungs.metrics.signals["respiratory_rate"] = rr + intensity * 8
                changes['respiratory_rate'] = lungs.metrics.signals["respiratory_rate"]

        elif intervention == "rest":
            if _is_num(fatigue):
                muscles.metrics.signals["fatigue_index"] = max(0.0, fatigue - intensity * 15)
                changes['fatigue_index'] = muscles.metrics.signals["fatigue_index"]

        self._recompute_from_signals()
        return changes

    def generate_clinical_summary(self) -> str:
        """Resumen clínico legible del organismo. Lo que falta dice «sin dato» (antes `0.0 bpm`, `5.0 L/min`, `85 %`);
        lo que nadie calcula dice «no modelado»; cada número lleva su procedencia entre corchetes."""
        heart, brain, lungs, muscles = (
            self.organs["heart"], self.organs["brain"], self.organs["lungs"], self.organs["muscles"],
        )

        def num(value: Any, unit: str = "", tag: str = "", digits: int = 1) -> str:
            if not _is_num(value):
                return NO_DATA
            return f"{value:.{digits}f}{unit}" + (f"  [{tag}]" if tag else "")

        def points(value: Optional[int]) -> str:
            return NO_DATA if value is None else f"{value} de 3  [NEWS2, RCP 2017]"

        entrada = "entrada"
        heur = "heurístico BIOCORE"
        ratio = self.global_state.get("hr_rr_ratio")
        bands = {k: v for k, v in brain.metrics.signals.items() if k.endswith("_power")}
        bands_txt = ", ".join(f"{k.replace('_power', '')} {v:.2f}" for k, v in bands.items()) if bands else NO_DATA

        return f"""
╔════════════════════════════════════════════════════════════════════════════╗
║                    RESUMEN CLÍNICO DEL GEMELO DIGITAL                      ║
║                          {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}                              ║
╚════════════════════════════════════════════════════════════════════════════╝
Procedencia de las entradas: {self.input_provenance or 'sin declarar'}

🫀 SISTEMA CARDIOVASCULAR:
   • Frecuencia Cardíaca: {num(heart.metrics.signals.get('heart_rate'), ' bpm', entrada)}
   • Variabilidad (HRV): {num(heart.metrics.signals.get('hrv'), ' ms', entrada)}
   • Puntos NEWS2 del pulso: {points(heart.metrics.risk_points)}
   • Gasto Cardíaco: {NOT_MODELED}

🧠 SISTEMA NEUROLÓGICO:
   • Estrés (entrada): {num(brain.metrics.signals.get('stress_level'), '/100', entrada, 0)}
   • Potencias de banda EEG (entrada): {bands_txt}
   • Índice de salud / riesgo neurológico: retirados (sin cita)

💨 SISTEMA RESPIRATORIO / OXIGENACIÓN:
   • Frecuencia Respiratoria: {num(lungs.metrics.signals.get('respiratory_rate'), ' resp/min', entrada)}
   • SpO₂: {num(lungs.metrics.signals.get('spo2'), '%', entrada)}
   • AHI: {num(lungs.metrics.signals.get('ahi'), ' eventos/h', entrada)}
   • Puntos NEWS2 de la FR: {points(lungs.metrics.rr_points)}
   • Puntos NEWS2 de la SpO₂ (escala 1): {points(lungs.metrics.spo2_points)}
   • SpO₂ escala 2: {NOT_MODELED}
   • Índice de salud pulmonar: {num(lungs.metrics.health_score, '%', heur + ' (FR + SpO₂ + AHI)', 0)}

🦾 SISTEMA MUSCULOESQUELÉTICO:
   • Índice de Fatiga: {num(muscles.metrics.signals.get('fatigue_index'), '%', entrada)}
   • Activación: {num(muscles.metrics.signals.get('activation'), '%', entrada)}
   • Frecuencia mediana EMG: {num(muscles.metrics.signals.get('median_frequency'), ' Hz', entrada)}

🔄 SISTEMA AUTONÓMICO:
   • HRV: {num(self.organs['autonomic'].metrics.signals.get('hrv'), ' ms', entrada)}
   • Balance simpático/parasimpático: {NOT_MODELED}

📊 GLOBAL:
   • {self.news2_partial_text()}
   • Razón FC:FR: {NO_DATA if ratio is None else f'{ratio:.1f} : 1  [Scholkmann & Wolf 2019: {PRQ_REST_REFERENCE_TEXT}]'}

════════════════════════════════════════════════════════════════════════════════
"""

    def to_json(self) -> str:
        """Estado completo a JSON. Lo que falta se exporta como «sin dato» y lo que nadie calcula como «no modelado»
        (antes salían los defaults: 5.0, 85.0, 50.0...). Sin total NEWS2."""

        def clean(value: Any) -> Any:
            if value is None:
                return NO_DATA
            if isinstance(value, dict):
                return {k: clean(v) for k, v in value.items()}
            return value

        partial: News2Partial = self.global_state["news2_partial"]
        state = {
            'timestamp': self.timestamp.isoformat(),
            'input_provenance': self.input_provenance or "sin declarar",
            'global_state': {
                'news2_partial': {
                    'components': dict(partial.components) if partial.available else NO_DATA,
                    'missing_for_total': list(partial.missing),
                    'total': "nunca: NEWS2 parcial",
                },
                'hr_rr_ratio': clean(self.global_state.get("hr_rr_ratio")),
                'alerts': list(self.global_state.get("alerts", [])),
                'anomalies': list(self.global_state.get("anomalies", [])),
                'recommendations': list(self.global_state.get("recommendations", [])),
            },
            'organs': {
                organ_id: clean({
                    'signals': organ.metrics.signals,
                    **({'news2_pulse_points': organ.metrics.risk_points} if organ_id == "heart" else {}),
                    **({'news2_rr_points': organ.metrics.rr_points, 'news2_spo2_scale1_points': organ.metrics.spo2_points,
                        'spo2_scale2': NOT_MODELED, 'health_score': organ.metrics.health_score} if organ_id == "lungs" else {}),
                    **({'cardiac_output': NOT_MODELED} if organ_id == "heart" else {}),
                })
                for organ_id, organ in self.organs.items()
            },
        }
        return json.dumps(state, indent=2, default=str)

    def create_patient_scenario(self, scenario: str) -> None:
        """
        Aplica un preset de paciente (healthy, hypertension, copd)
        directamente a las señales de los órganos correspondientes.
        """
        from src.clinical.healthy_baseline import instance as _healthy_instance
        _H = _healthy_instance()  # semilla de referencia: valores nominales
        scenarios: Dict[str, Dict[str, Dict[str, float]]] = {
            # Unificación 4: los valores de "sano" son los nominales de la fuente única (antes HRV 60 aquí y 50 en el motor).
            # Fase 0: sin `efficiency: 90` (valor inventado que nadie medía).
            'healthy': {
                'ecg': {'heart_rate': _H['hr'], 'hrv': _H['hrv']},
                'respiratory': {'respiratory_rate': _H['respiratory_rate'], 'spo2': _H['spo2']},
                'eeg': {'stress_level': _H['stress_level']}, 'emg': {'fatigue_index': _H['fatigue_index']},
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
        self.input_provenance = f"simulación: preset «{scenario}»"
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
