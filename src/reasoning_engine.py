"""
Biomedical Reasoning Engine (BRE)

Motor de razonamiento clínico que transforma métricas fisiológicas en
razonamiento clínico explicable, diagnósticos diferenciales educativos
y recomendaciones personalizadas.

Arquitectura:
- ReasoningPattern: Abstracción para patrones fisiológicos
- PhysiologicalPatternDetector: Detector de patrones
- ClinicalHypothesisGenerator: Generador de hipótesis clínicas
- DifferentialDiagnosisGenerator: Generador de diagnósticos diferenciales
- RiskEstimator: Estimador de riesgo fisiológico
- EducationalRecommendationGenerator: Generador de recomendaciones
- BiomedicalReasoningEngine: Orquestador principal

Principios SOLID:
- S: Cada clase tiene responsabilidad única
- O: Abierto a extensión, cerrado a modificación
- L: Sustitución de Liskov respetada
- I: Interfaces segregadas
- D: Inversión de dependencias mediante abstracciones
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
import json


class RiskLevel(Enum):
    """Niveles de riesgo fisiológico."""
    BAJO = "bajo"
    MODERADO = "moderado"
    ALTO = "alto"
    CRÍTICO = "crítico"


class AutonomicState(Enum):
    """Estados del sistema nervioso autónomo."""
    SIMPÁTICO = "simpático"
    PARASIMPÁTICO = "parasimpático"
    EQUILIBRIO = "equilibrio"
    DISFUNCIÓN = "disfunción"


@dataclass
class HRVMetrics:
    """Contenedor para métricas HRV."""
    bpm: float
    sdnn: float
    rmssd: float
    pnn50: float
    lf: float
    hf: float
    lf_hf: float
    entropy: float
    ai_score: Optional[float] = None
    timestamp: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario."""
        return asdict(self)

    def validate(self) -> Tuple[bool, str]:
        """Valida las métricas."""
        if self.bpm <= 0 or self.bpm > 300:
            return False, "BPM fuera de rango (0-300)"
        if self.sdnn < 0 or self.sdnn > 1.0:
            return False, "SDNN fuera de rango (0-1)"
        if self.rmssd < 0 or self.rmssd > 1.0:
            return False, "RMSSD fuera de rango (0-1)"
        if self.pnn50 < 0 or self.pnn50 > 100:
            return False, "pNN50 fuera de rango (0-100)"
        if self.lf < 0:
            return False, "LF no puede ser negativo"
        if self.hf < 0:
            return False, "HF no puede ser negativo"
        if self.lf_hf < 0:
            return False, "LF/HF no puede ser negativo"
        if self.entropy < 0 or self.entropy > 10:
            return False, "Entropía fuera de rango (0-10)"
        if self.ai_score is not None and (self.ai_score < 0 or self.ai_score > 1):
            return False, "AI Score debe estar entre 0 y 1"
        return True, "Válido"


@dataclass
class PhysiologicalFinding:
    """Hallazgo fisiológico detectable."""
    name: str
    description: str
    confidence: float  # 0-1
    implications: List[str] = field(default_factory=list)
    clinical_relevance: str = ""


@dataclass
class ClinicalHypothesis:
    """Hipótesis clínica generada."""
    hypothesis: str
    probability: float  # 0-1
    supporting_metrics: List[str] = field(default_factory=list)
    contraindications: List[str] = field(default_factory=list)
    next_steps: List[str] = field(default_factory=list)
    educational_note: str = ""


@dataclass
class DifferentialDiagnosis:
    """Diagnóstico diferencial educativo."""
    condition: str
    probability: float  # 0-1
    cardinal_features: List[str] = field(default_factory=list)
    supporting_findings: List[str] = field(default_factory=list)
    distinguishing_features: List[str] = field(default_factory=list)
    investigation_recommendations: List[str] = field(default_factory=list)


@dataclass
class EducationalRecommendation:
    """Recomendación educativa personalizada."""
    category: str  # "lifestyle", "monitoring", "investigation", "clinical_follow_up"
    recommendation: str
    rationale: str
    urgency: str  # "routine", "soon", "urgent"
    evidence_level: str  # "A", "B", "C"


@dataclass
class ReasoningOutput:
    """Salida principal del motor de razonamiento."""
    findings: List[PhysiologicalFinding] = field(default_factory=list)
    hypotheses: List[ClinicalHypothesis] = field(default_factory=list)
    differential_diagnoses: List[DifferentialDiagnosis] = field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.BAJO
    autonomic_state: AutonomicState = AutonomicState.EQUILIBRIO
    risk_score: float = 0.0  # 0-100
    main_narrative: str = ""
    clinical_impression: str = ""
    recommendations: List[EducationalRecommendation] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario, preservando los enums."""
        result = {
            "findings": [
                {
                    "name": f.name,
                    "description": f.description,
                    "confidence": f.confidence,
                    "implications": f.implications,
                    "clinical_relevance": f.clinical_relevance,
                }
                for f in self.findings
            ],
            "hypotheses": [
                {
                    "hypothesis": h.hypothesis,
                    "probability": h.probability,
                    "supporting_metrics": h.supporting_metrics,
                    "contraindications": h.contraindications,
                    "next_steps": h.next_steps,
                    "educational_note": h.educational_note,
                }
                for h in self.hypotheses
            ],
            "differential_diagnoses": [
                {
                    "condition": d.condition,
                    "probability": d.probability,
                    "cardinal_features": d.cardinal_features,
                    "supporting_findings": d.supporting_findings,
                    "distinguishing_features": d.distinguishing_features,
                    "investigation_recommendations": d.investigation_recommendations,
                }
                for d in self.differential_diagnoses
            ],
            "risk_level": self.risk_level.value,
            "autonomic_state": self.autonomic_state.value,
            "risk_score": self.risk_score,
            "main_narrative": self.main_narrative,
            "clinical_impression": self.clinical_impression,
            "recommendations": [
                {
                    "category": r.category,
                    "recommendation": r.recommendation,
                    "rationale": r.rationale,
                    "urgency": r.urgency,
                    "evidence_level": r.evidence_level,
                }
                for r in self.recommendations
            ],
            "warnings": self.warnings,
        }
        return result

    def to_json(self) -> str:
        """Convierte a JSON."""
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


class ReasoningPattern(ABC):
    """Patrón abstracto de razonamiento fisiológico."""

    @abstractmethod
    def detect(self, metrics: HRVMetrics) -> Optional[PhysiologicalFinding]:
        """Detecta el patrón en las métricas."""
        pass


class PhysiologicalPatternDetector:
    """Detecta patrones fisiológicos en métricas HRV."""

    def __init__(self):
        """Inicializa el detector con patrones predefinidos."""
        self.patterns: List[ReasoningPattern] = [
            TachycardiaPattern(),
            BradycardiaPattern(),
            HighVariabilityPattern(),
            LowVariabilityPattern(),
            SympatheticDominancePattern(),
            ParasympatheticDominancePattern(),
            LowEntropyPattern(),
            HighEntropyPattern(),
        ]

    def detect_all(self, metrics: HRVMetrics) -> List[PhysiologicalFinding]:
        """Detecta todos los patrones aplicables."""
        findings = []
        for pattern in self.patterns:
            finding = pattern.detect(metrics)
            if finding:
                findings.append(finding)
        return findings


class TachycardiaPattern(ReasoningPattern):
    """Patrón de taquicardia."""

    def detect(self, metrics: HRVMetrics) -> Optional[PhysiologicalFinding]:
        """Detecta taquicardia."""
        if metrics.bpm > 100:
            severity = "leve" if metrics.bpm <= 110 else "moderada" if metrics.bpm <= 130 else "severa"
            return PhysiologicalFinding(
                name=f"Taquicardia {severity}",
                description=f"Frecuencia cardíaca elevada: {metrics.bpm:.0f} bpm",
                confidence=1.0 if metrics.bpm > 130 else 0.9,
                implications=[
                    "Activación simpática",
                    "Estrés metabólico",
                    "Posible descompensación autonómica",
                ],
                clinical_relevance="Requiere investigación de causa base (fiebre, ansiedad, insuficiencia cardíaca)",
            )
        return None


class BradycardiaPattern(ReasoningPattern):
    """Patrón de bradicardia."""

    def detect(self, metrics: HRVMetrics) -> Optional[PhysiologicalFinding]:
        """Detecta bradicardia."""
        if metrics.bpm < 60:
            severity = "leve" if metrics.bpm >= 50 else "moderada" if metrics.bpm >= 40 else "severa"
            return PhysiologicalFinding(
                name=f"Bradicardia {severity}",
                description=f"Frecuencia cardíaca baja: {metrics.bpm:.0f} bpm",
                confidence=1.0 if metrics.bpm < 40 else 0.9,
                implications=[
                    "Activación parasimpática pronunciada",
                    "Posible bloqueo AV o disfunción nodo SA",
                    "En atletas: adaptación esperada",
                ],
                clinical_relevance="En no-atletas requiere evaluación de arritmias",
            )
        return None


class HighVariabilityPattern(ReasoningPattern):
    """Patrón de variabilidad alta (buena)."""

    def detect(self, metrics: HRVMetrics) -> Optional[PhysiologicalFinding]:
        """Detecta alta variabilidad."""
        if metrics.sdnn > 0.15 and metrics.rmssd > 0.05:
            return PhysiologicalFinding(
                name="Variabilidad Cardíaca Alta",
                description="Excelente variabilidad en intervalos RR",
                confidence=0.95,
                implications=[
                    "Buena función autonómica",
                    "Excelente capacidad adaptativa",
                    "Baja susceptibilidad a arritmias",
                ],
                clinical_relevance="Indicador de buena salud cardiovascular y resilencia",
            )
        return None


class LowVariabilityPattern(ReasoningPattern):
    """Patrón de variabilidad baja (preocupante)."""

    def detect(self, metrics: HRVMetrics) -> Optional[PhysiologicalFinding]:
        """Detecta baja variabilidad."""
        if metrics.sdnn < 0.05 or metrics.rmssd < 0.015:
            severity = "moderada" if metrics.sdnn > 0.035 else "severa"
            return PhysiologicalFinding(
                name=f"Variabilidad Cardíaca Baja ({severity})",
                description=f"Ritmo cardíaco monótono: SDNN={metrics.sdnn:.4f}",
                confidence=0.9 if metrics.sdnn < 0.035 else 0.8,
                implications=[
                    "Disfunción autonómica",
                    "Estrés crónico o agudo",
                    "Riesgo cardiovascular aumentado",
                    "Posible fatiga o overtraining",
                ],
                clinical_relevance="Requiere investigación de causa: estrés, enfermedad, fatiga",
            )
        return None


class SympatheticDominancePattern(ReasoningPattern):
    """Patrón de dominancia simpática."""

    def detect(self, metrics: HRVMetrics) -> Optional[PhysiologicalFinding]:
        """Detecta dominancia simpática."""
        if metrics.lf_hf > 2.0 and metrics.lf > metrics.hf:
            return PhysiologicalFinding(
                name="Dominancia Simpática",
                description=f"Relación LF/HF elevada: {metrics.lf_hf:.2f}",
                confidence=0.9,
                implications=[
                    "Activación del sistema simpático",
                    "Estado de alerta aumentado",
                    "Posible estrés, ansiedad o combate",
                    "Respuesta cardiovascular hiperdinámica",
                ],
                clinical_relevance="Esperado en ejercicio o estrés agudo; crónico requiere investigación",
            )
        return None


class ParasympatheticDominancePattern(ReasoningPattern):
    """Patrón de dominancia parasimpática."""

    def detect(self, metrics: HRVMetrics) -> Optional[PhysiologicalFinding]:
        """Detecta dominancia parasimpática."""
        if metrics.lf_hf < 1.0 and metrics.hf > metrics.lf and metrics.rmssd > 0.04:
            return PhysiologicalFinding(
                name="Dominancia Parasimpática",
                description=f"Relación LF/HF baja: {metrics.lf_hf:.2f}",
                confidence=0.9,
                implications=[
                    "Activación del sistema parasimpático",
                    "Estado de calma y recuperación",
                    "Buena variabilidad parasimpática",
                    "Capacidad de relajación preservada",
                ],
                clinical_relevance="Indicador de buena recuperación y función vagal",
            )
        return None


class LowEntropyPattern(ReasoningPattern):
    """Patrón de entropía baja."""

    def detect(self, metrics: HRVMetrics) -> Optional[PhysiologicalFinding]:
        """Detecta entropía baja."""
        if metrics.entropy < 2.0:
            return PhysiologicalFinding(
                name="Baja Complejidad (Entropía Baja)",
                description=f"Patrón de ritmo predecible: Entropía={metrics.entropy:.2f}",
                confidence=0.85,
                implications=[
                    "Ritmo cardíaco muy regular",
                    "Posible pérdida de complejidad fisiológica",
                    "Sugiere estrés crónico o enfermedad",
                    "Adaptabilidad reducida",
                ],
                clinical_relevance="Patología frecuentemente asociada; investigar causa",
            )
        return None


class HighEntropyPattern(ReasoningPattern):
    """Patrón de entropía alta."""

    def detect(self, metrics: HRVMetrics) -> Optional[PhysiologicalFinding]:
        """Detecta entropía alta."""
        if metrics.entropy > 4.0:
            return PhysiologicalFinding(
                name="Alta Complejidad (Entropía Alta)",
                description=f"Patrón de ritmo complejo: Entropía={metrics.entropy:.2f}",
                confidence=0.85,
                implications=[
                    "Ritmo cardíaco altamente variable",
                    "Buena complejidad fisiológica",
                    "Adaptabilidad preservada",
                    "Sistema dinámico y responsive",
                ],
                clinical_relevance="Indicador de salud fisiológica y capacidad adaptativa",
            )
        return None


class ClinicalHypothesisGenerator:
    """Genera hipótesis clínicas basadas en patrones."""

    @staticmethod
    def generate_hypotheses(
        findings: List[PhysiologicalFinding],
        metrics: HRVMetrics,
    ) -> List[ClinicalHypothesis]:
        """Genera hipótesis clínicas."""
        hypotheses = []

        # Hipótesis de estrés agudo
        if any(f.name == "Taquicardia moderada" or f.name == "Taquicardia severa" for f in findings) and any(
            f.name == "Variabilidad Cardíaca Baja (moderada)" for f in findings
        ):
            hypotheses.append(
                ClinicalHypothesis(
                    hypothesis="Estrés agudo o respuesta de lucha/huida",
                    probability=0.85,
                    supporting_metrics=["Frecuencia cardíaca elevada", "Variabilidad baja", "LF/HF elevado"],
                    contraindications=["Fiebre confirmada", "Infección activa"],
                    next_steps=[
                        "Evaluar factores estresantes recientes",
                        "Monitoreo de vital signs",
                        "Técnicas de respiración/relajación",
                    ],
                    educational_note="La respuesta de estrés agudo es fisiológicamente normal pero requiere resolución",
                )
            )

        # Hipótesis de buena salud cardiovascular
        if any(f.name == "Variabilidad Cardíaca Alta" for f in findings) and any(
            f.name == "Dominancia Parasimpática" for f in findings
        ):
            hypotheses.append(
                ClinicalHypothesis(
                    hypothesis="Buena función cardiovascular y recuperación",
                    probability=0.9,
                    supporting_metrics=["Alta variabilidad", "Dominancia parasimpática", "Ritmo regular"],
                    contraindications=[],
                    next_steps=["Mantener estilo de vida actual", "Monitoreo periódico"],
                    educational_note="Indicadores de excelente salud autonómica",
                )
            )

        # Hipótesis de disfunción autonómica
        if any(f.name == "Variabilidad Cardíaca Baja (severa)" for f in findings) and metrics.bpm > 100:
            hypotheses.append(
                ClinicalHypothesis(
                    hypothesis="Posible disfunción autonómica o estrés crónico",
                    probability=0.75,
                    supporting_metrics=["Variabilidad muy baja", "Taquicardia", "Patrón anómalo LF/HF"],
                    contraindications=["Actividad física reciente"],
                    next_steps=[
                        "Evaluación clínica completa",
                        "Investigar estrés crónico",
                        "Test de esfuerzo si indicado",
                        "Considerar referencia cardiológica",
                    ],
                    educational_note="Requiere evaluación clínica especializada",
                )
            )

        # Hipótesis de recuperación post-esfuerzo
        if metrics.bpm < 70 and metrics.rmssd > 0.05:
            hypotheses.append(
                ClinicalHypothesis(
                    hypothesis="Estado de recuperación post-esfuerzo",
                    probability=0.8,
                    supporting_metrics=["Frecuencia cardíaca normal/baja", "Alta variabilidad parasimpática"],
                    contraindications=[],
                    next_steps=["Continuar descanso/recuperación", "Hidratación adecuada"],
                    educational_note="Patrón esperado después de actividad física",
                )
            )

        return hypotheses


class DifferentialDiagnosisGenerator:
    """Genera diagnósticos diferenciales educativos."""

    @staticmethod
    def generate_differential_diagnoses(
        findings: List[PhysiologicalFinding],
        metrics: HRVMetrics,
    ) -> List[DifferentialDiagnosis]:
        """Genera diagnósticos diferenciales."""
        diagnoses = []

        # Diferencial para taquicardia
        if metrics.bpm > 100:
            diagnoses.append(
                DifferentialDiagnosis(
                    condition="Estrés/Ansiedad",
                    probability=0.4,
                    cardinal_features=["Taquicardia", "Variabilidad baja", "Patrón LF/HF elevado"],
                    supporting_findings=["Síntomas emocionales", "Patrón rítmico"],
                    distinguishing_features=[
                        "Mejora con técnicas de relajación",
                        "Desaparece con tratamiento ansiolítico",
                    ],
                    investigation_recommendations=[
                        "Evaluación psicológica",
                        "Monitoreo de factores estresantes",
                    ],
                )
            )

            diagnoses.append(
                DifferentialDiagnosis(
                    condition="Infección/Fiebre",
                    probability=0.3,
                    cardinal_features=["Taquicardia", "Posible febrícula"],
                    supporting_findings=["Síntomas sistémicos", "Malestar general"],
                    distinguishing_features=["Presencia de fiebre", "Elevación de marcadores inflamatorios"],
                    investigation_recommendations=[
                        "Medición de temperatura",
                        "CBC, PCR, ferritina",
                        "Búsqueda de foco infeccioso",
                    ],
                )
            )

            diagnoses.append(
                DifferentialDiagnosis(
                    condition="Arritmia Supraventricular",
                    probability=0.15,
                    cardinal_features=["Taquicardia paroxística", "Patrón irregular"],
                    supporting_findings=["Palpitaciones", "Disnea asociada"],
                    distinguishing_features=["ECG mostrando ondas P aberrantes", "Conversiónbrusca"],
                    investigation_recommendations=[
                        "ECG de 12 derivaciones",
                        "Holter de 24h",
                        "Referencia a cardiología",
                    ],
                )
            )

        # Diferencial para variabilidad baja
        if metrics.sdnn < 0.05:
            diagnoses.append(
                DifferentialDiagnosis(
                    condition="Estrés Crónico",
                    probability=0.45,
                    cardinal_features=["Variabilidad muy baja", "SDNN < 0.05", "Entropía baja"],
                    supporting_findings=["Historia de estrés", "Síntomas de burnout"],
                    distinguishing_features=["Mejora con resolución de estresores"],
                    investigation_recommendations=[
                        "Evaluación de factores estresantes",
                        "Escalas de estrés (PSS, DASS)",
                        "Seguimiento con intervención",
                    ],
                )
            )

            diagnoses.append(
                DifferentialDiagnosis(
                    condition="Diabetes Mellitus",
                    probability=0.25,
                    cardinal_features=["Neuropatía autonómica", "Variabilidad baja"],
                    supporting_findings=["Glucemias elevadas", "Polineuropatía"],
                    distinguishing_features=["HbA1c elevada", "Glicemia en ayunas > 126"],
                    investigation_recommendations=[
                        "Glucosa en ayunas",
                        "HbA1c",
                        "Prueba de tolerancia oral a glucosa",
                        "Neuropatía assessment",
                    ],
                )
            )

            diagnoses.append(
                DifferentialDiagnosis(
                    condition="Enfermedad Cardiovascular",
                    probability=0.2,
                    cardinal_features=["Variabilidad muy baja", "Evidencia de isquemia"],
                    supporting_findings=["Factores de riesgo presentes", "Síntomas cardíacos"],
                    distinguishing_features=["Cambios isquémicos en ECG", "Troponinas elevadas"],
                    investigation_recommendations=[
                        "Troponina I/T",
                        "BNP/NT-proBNP",
                        "Ecocardiograma",
                        "Test de esfuerzo si estable",
                    ],
                )
            )

        return diagnoses


class RiskEstimator:
    """Estima el riesgo fisiológico global."""

    @staticmethod
    def estimate_risk(
        metrics: HRVMetrics,
        findings: List[PhysiologicalFinding],
        ai_score: Optional[float] = None,
    ) -> Tuple[RiskLevel, float]:
        """
        Estima riesgo global (0-100 escala).
        
        Retorna
        -------
        tuple
            (RiskLevel, risk_score: float)
        """
        risk_score = 0.0

        # Factor de frecuencia cardíaca
        if metrics.bpm > 130:
            risk_score += 25
        elif metrics.bpm > 110:
            risk_score += 20  # Aumentado de 15
        elif metrics.bpm < 40:
            risk_score += 20
        elif metrics.bpm < 50:
            risk_score += 10

        # Factor de variabilidad
        if metrics.sdnn < 0.05:
            risk_score += 25
        elif metrics.sdnn < 0.08:
            risk_score += 20  # Aumentado de 15

        # Factor de entropía
        if metrics.entropy < 1.5:
            risk_score += 15
        elif metrics.entropy < 2.0:
            risk_score += 10  # Aumentado de 8

        # Factor LF/HF (autonomic balance)
        if metrics.lf_hf > 3.5 and metrics.bpm > 100:
            risk_score += 20  # Aumentado de 15
        elif metrics.lf_hf > 2.5:
            risk_score += 12  # Aumentado de 8

        # Factor AI score si disponible
        if ai_score is not None:
            if ai_score > 0.7:  # Alta probabilidad de anomalía
                risk_score += 15
            elif ai_score > 0.5:
                risk_score += 10  # Aumentado de 8

        # Número de hallazgos adversos
        adverse_findings = sum(
            1 for f in findings if "Baja" in f.name or "severa" in f.name.lower()
        )
        risk_score += min(adverse_findings * 8, 20)  # Aumentado multiplicador y max

        # Normalizar a 0-100
        risk_score = min(risk_score, 100)

        # Determinar nivel de riesgo
        if risk_score >= 75:
            risk_level = RiskLevel.CRÍTICO
        elif risk_score >= 50:
            risk_level = RiskLevel.ALTO
        elif risk_score >= 25:
            risk_level = RiskLevel.MODERADO
        else:
            risk_level = RiskLevel.BAJO

        return risk_level, risk_score


class EducationalRecommendationGenerator:
    """Genera recomendaciones educativas personalizadas."""

    @staticmethod
    def generate_recommendations(
        metrics: HRVMetrics,
        findings: List[PhysiologicalFinding],
        risk_level: RiskLevel,
    ) -> List[EducationalRecommendation]:
        """Genera recomendaciones."""
        recommendations = []

        # Recomendaciones para estrés
        if any("Taquicardia" in f.name for f in findings) or metrics.lf_hf > 2.0:
            recommendations.append(
                EducationalRecommendation(
                    category="lifestyle",
                    recommendation="Practicar técnicas de respiración diafragmática (4-7-8 o coherencia cardíaca)",
                    rationale="La respiración lenta y profunda estimula el sistema parasimpático",
                    urgency="soon",
                    evidence_level="A",
                )
            )

            recommendations.append(
                EducationalRecommendation(
                    category="lifestyle",
                    recommendation="Realizar meditación o mindfulness 15-20 min diarios",
                    rationale="Reduce actividad simpática y mejora HRV",
                    urgency="soon",
                    evidence_level="A",
                )
            )

        # Recomendaciones para variabilidad baja
        if metrics.sdnn < 0.08:
            recommendations.append(
                EducationalRecommendation(
                    category="lifestyle",
                    recommendation="Incrementar actividad física moderada (150 min/semana)",
                    rationale="El ejercicio regular mejora la variabilidad cardíaca",
                    urgency="soon",
                    evidence_level="A",
                )
            )

            recommendations.append(
                EducationalRecommendation(
                    category="monitoring",
                    recommendation="Monitoreo de HRV semanal o diario",
                    rationale="Permite seguimiento de recuperación y tendencias",
                    urgency="routine",
                    evidence_level="B",
                )
            )

        # Recomendaciones para entropía baja
        if metrics.entropy < 2.0:
            recommendations.append(
                EducationalRecommendation(
                    category="lifestyle",
                    recommendation="Aumentar variedad en actividades y estímulos",
                    rationale="Promueve adaptabilidad y complejidad fisiológica",
                    urgency="soon",
                    evidence_level="B",
                )
            )

        # Recomendaciones para riesgo alto
        if risk_level in [RiskLevel.ALTO, RiskLevel.CRÍTICO]:
            recommendations.append(
                EducationalRecommendation(
                    category="clinical_follow_up",
                    recommendation="Evaluación cardiológica completa recomendada",
                    rationale="Descartar patología cardiovascular subyacente",
                    urgency="urgent",
                    evidence_level="A",
                )
            )

            recommendations.append(
                EducationalRecommendation(
                    category="investigation",
                    recommendation="Realizar ECG de 12 derivaciones y Holter si no disponible",
                    rationale="Evaluación estructurada de ritmo y conducción",
                    urgency="urgent",
                    evidence_level="A",
                )
            )

        # Recomendaciones generales
        recommendations.append(
            EducationalRecommendation(
                category="lifestyle",
                recommendation="Mantener sueño regular (7-9 horas) y consistente",
                rationale="El sueño restaura la función autonómica",
                urgency="routine",
                evidence_level="A",
            )
        )

        recommendations.append(
            EducationalRecommendation(
                category="lifestyle",
                recommendation="Limitar cafeína y alcohol",
                rationale="Ambos afectan negativamente la HRV",
                urgency="routine",
                evidence_level="B",
            )
        )

        return recommendations


class AutonomicStateClassifier:
    """Clasifica el estado del sistema nervioso autónomo."""

    @staticmethod
    def classify(metrics: HRVMetrics) -> AutonomicState:
        """Clasifica el estado autonómico."""
        # Criterios específicos de clasificación
        if metrics.sdnn < 0.05:
            return AutonomicState.DISFUNCIÓN

        # Dominancia simpática: LF/HF elevado Y frecuencia elevada Y baja variabilidad
        if metrics.lf_hf > 2.5 and metrics.bpm > 95 and metrics.rmssd < 0.04:
            return AutonomicState.SIMPÁTICO

        # Dominancia parasimpática: LF/HF muy bajo AND RMSSD elevado Y HF > LF
        if metrics.lf_hf < 0.7 and metrics.rmssd > 0.06 and metrics.hf > metrics.lf and metrics.bpm < 70:
            return AutonomicState.PARASIMPÁTICO

        # Equilibrio: valores moderados con balance
        return AutonomicState.EQUILIBRIO


class BiomedicalReasoningEngine:
    """
    Motor principal de razonamiento clínico.
    
    Orquesta detección de patrones, generación de hipótesis,
    diagnósticos diferenciales, estimación de riesgo y recomendaciones.
    """

    def __init__(self):
        """Inicializa el motor."""
        self.pattern_detector = PhysiologicalPatternDetector()
        self.hypothesis_generator = ClinicalHypothesisGenerator()
        self.diagnosis_generator = DifferentialDiagnosisGenerator()
        self.risk_estimator = RiskEstimator()
        self.recommendation_generator = EducationalRecommendationGenerator()
        self.autonomic_classifier = AutonomicStateClassifier()

    def reason(
        self,
        metrics: HRVMetrics,
    ) -> ReasoningOutput:
        """
        Ejecuta razonamiento completo sobre métricas HRV.
        
        Parámetros
        ----------
        metrics : HRVMetrics
            Métricas de HRV para analizar
            
        Retorna
        -------
        ReasoningOutput
            Razonamiento clínico completo
        """
        # Validar métricas
        is_valid, validation_msg = metrics.validate()
        if not is_valid:
            return ReasoningOutput(
                warnings=[f"Error de validación: {validation_msg}"],
                clinical_impression="No se puede procesar debido a métricas inválidas",
            )

        # Detectar patrones
        findings = self.pattern_detector.detect_all(metrics)

        # Generar hipótesis
        hypotheses = self.hypothesis_generator.generate_hypotheses(findings, metrics)

        # Generar diagnósticos diferenciales
        differential_diagnoses = self.diagnosis_generator.generate_differential_diagnoses(findings, metrics)

        # Estimar riesgo
        risk_level, risk_score = self.risk_estimator.estimate_risk(metrics, findings, metrics.ai_score)

        # Clasificar estado autonómico
        autonomic_state = self.autonomic_classifier.classify(metrics)

        # Generar recomendaciones
        recommendations = self.recommendation_generator.generate_recommendations(
            metrics, findings, risk_level
        )

        # Generar narrativa clínica
        main_narrative = self._generate_narrative(metrics, findings, hypotheses, risk_level)

        # Generar impresión clínica
        clinical_impression = self._generate_clinical_impression(hypotheses, risk_level, autonomic_state)

        # Generar advertencias
        warnings = self._generate_warnings(metrics, findings, risk_level)

        return ReasoningOutput(
            findings=findings,
            hypotheses=hypotheses,
            differential_diagnoses=differential_diagnoses,
            risk_level=risk_level,
            autonomic_state=autonomic_state,
            risk_score=risk_score,
            main_narrative=main_narrative,
            clinical_impression=clinical_impression,
            recommendations=recommendations,
            warnings=warnings,
        )

    def _generate_narrative(
        self,
        metrics: HRVMetrics,
        findings: List[PhysiologicalFinding],
        hypotheses: List[ClinicalHypothesis],
        risk_level: RiskLevel,
    ) -> str:
        """Genera narrativa clínica descriptiva."""
        lines = []

        lines.append(f"Análisis de {len(findings)} hallazgos fisiológicos detectados:")
        for finding in findings[:3]:  # Top 3 findings
            lines.append(f"  • {finding.name}: {finding.description}")

        if hypotheses:
            lines.append(f"\nHipótesis principal: {hypotheses[0].hypothesis}")
            lines.append(f"Probabilidad estimada: {hypotheses[0].probability * 100:.0f}%")

        lines.append(f"\nEvaluación de riesgo: {risk_level.value.upper()}")
        lines.append(f"Puntuación de riesgo: {risk_level} (0-100 escala)")

        return "\n".join(lines)

    def _generate_clinical_impression(
        self,
        hypotheses: List[ClinicalHypothesis],
        risk_level: RiskLevel,
        autonomic_state: AutonomicState,
    ) -> str:
        """Genera impresión clínica concisa."""
        if not hypotheses:
            return "No se pueden generar conclusiones clínicas con los datos actuales."

        primary_hypothesis = hypotheses[0]
        impression = f"Evaluación sugiere: {primary_hypothesis.hypothesis}. "
        impression += f"Estado autonómico: {autonomic_state.value}. "
        impression += f"Nivel de riesgo: {risk_level.value}. "

        if risk_level in [RiskLevel.ALTO, RiskLevel.CRÍTICO]:
            impression += "Requiere evaluación clínica especializada."

        return impression

    def _generate_warnings(
        self,
        metrics: HRVMetrics,
        findings: List[PhysiologicalFinding],
        risk_level: RiskLevel,
    ) -> List[str]:
        """Genera advertencias clínicas."""
        warnings = []

        if risk_level == RiskLevel.CRÍTICO:
            warnings.append("⚠️ RIESGO CRÍTICO DETECTADO: Requiere evaluación médica inmediata")
        elif risk_level == RiskLevel.ALTO:
            warnings.append("⚠️ Riesgo elevado: Seguimiento clínico recomendado")

        if metrics.bpm < 40:
            warnings.append("⚠️ Bradicardia severa: Consultar médico si síntomas presentes")
        elif metrics.bpm > 130:
            warnings.append("⚠️ Taquicardia pronunciada: Investigar causa subyacente")

        if metrics.bpm > 150:
            warnings.append("⚠️ Taquicardia severa: Requiere evaluación urgente")

        if metrics.sdnn < 0.03:
            warnings.append("⚠️ Variabilidad cardíaca extremadamente baja: Patrón anómalo")

        if any("Baja" in f.name and "severa" in f.name.lower() for f in findings):
            warnings.append("⚠️ Función autonómica deteriorada: Requiere investigación")

        if metrics.lf_hf > 5.0:
            warnings.append("⚠️ Desequilibrio autonómico extremo: Dominancia simpática severa")

        return warnings
