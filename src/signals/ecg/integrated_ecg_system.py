"""
12-Lead ECG Integration with Educational System

Bridges:
- 12-Lead generator and analyzer
- Wave annotation
- Advanced patterns
- ECGTutor system
- Clinical interpretation

Creates unified interface for education and clinical practice
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

# Import existing components
from src.signals.ecg.twelve_lead_generator import (
    TwelveLeadEcgGenerator,
    EcgParameters,
    generate_12lead_example
)
from src.signals.ecg.twelve_lead_analyzer import (
    TwelveLeadEcgAnalyzer,
    EcgInterpretation
)
from src.signals.ecg.wave_annotation import (
    WaveAnnotator,
    ComplexAnnotation
)
from src.signals.ecg.advanced_patterns import AdvancedEcgPatterns


@dataclass
class ComprehensiveEcgStudy:
    """Complete ECG study with all analysis components"""
    
    # Raw data
    signals: Dict[str, np.ndarray]  # 12-lead signals
    time: np.ndarray
    sampling_rate: float
    
    # Clinical interpretation
    interpretation: EcgInterpretation
    
    # Wave annotations (for lead II)
    wave_annotations: List[ComplexAnnotation]
    
    # Metadata
    study_type: str  # "normal", "stemi", "arrhythmia", etc.
    complexity: str  # "basic", "intermediate", "advanced"
    clinical_case: Optional[Dict] = None
    

class EcgStudyGenerator:
    """Generate comprehensive ECG studies for education and training"""
    
    def __init__(self, sampling_rate: float = 250):
        """Initialize study generator"""
        self.sampling_rate = sampling_rate
        self.generator = TwelveLeadEcgGenerator(sampling_rate=sampling_rate)
        self.analyzer = TwelveLeadEcgAnalyzer()
        self.annotator = WaveAnnotator(sampling_rate=sampling_rate)
    
    def create_basic_study(
        self,
        case_type: str = "normal",
        heart_rate: float = 75,
        clinical_case: Optional[Dict] = None
    ) -> ComprehensiveEcgStudy:
        """
        Create basic ECG study (for learning)
        
        Args:
            case_type: "normal", "tachycardia", "bradycardia", etc.
            heart_rate: HR in bpm
            clinical_case: Optional clinical context
            
        Returns:
            ComprehensiveEcgStudy object
        """
        # Generate 12-lead ECG
        ecg_signals = generate_12lead_example(
            heart_rate=heart_rate,
            condition=case_type
        )
        
        # Analyze
        interpretation = self.analyzer.analyze_12lead(ecg_signals)
        
        # Annotate waves (lead II)
        wave_annotations = self.annotator.annotate_lead(ecg_signals['II'], 'II')
        
        return ComprehensiveEcgStudy(
            signals=ecg_signals,
            time=ecg_signals['time'],
            sampling_rate=self.sampling_rate,
            interpretation=interpretation,
            wave_annotations=wave_annotations,
            study_type=case_type,
            complexity="basic",
            clinical_case=clinical_case
        )
    
    def create_intermediate_study(
        self,
        case_type: str = "anterior_stemi"
    ) -> ComprehensiveEcgStudy:
        """Create intermediate ECG study"""
        ecg_signals = generate_12lead_example(
            heart_rate=88,
            condition=case_type
        )
        
        interpretation = self.analyzer.analyze_12lead(ecg_signals)
        wave_annotations = self.annotator.annotate_lead(ecg_signals['II'], 'II')
        
        return ComprehensiveEcgStudy(
            signals=ecg_signals,
            time=ecg_signals['time'],
            sampling_rate=self.sampling_rate,
            interpretation=interpretation,
            wave_annotations=wave_annotations,
            study_type=case_type,
            complexity="intermediate"
        )
    
    def create_advanced_arrhythmia_study(
        self,
        arrhythmia_type: str = "atrial_fibrillation"
    ) -> ComprehensiveEcgStudy:
        """
        Create advanced ECG study with arrhythmias
        
        Args:
            arrhythmia_type: "atrial_fibrillation", "flutter", "wpw", "long_qt", etc.
            
        Returns:
            ComprehensiveEcgStudy
        """
        # Generate arrhythmia signal
        if arrhythmia_type == "atrial_fibrillation":
            signal, time = AdvancedEcgPatterns.generate_atrial_fibrillation(
                duration=10.0,
                sampling_rate=self.sampling_rate,
                ventricular_rate=115
            )
        elif arrhythmia_type == "flutter":
            signal, time = AdvancedEcgPatterns.generate_atrial_flutter(
                duration=10.0,
                sampling_rate=self.sampling_rate,
                flutter_rate=300,
                ventricular_rate=150
            )
        elif arrhythmia_type == "wpw":
            signal, time = AdvancedEcgPatterns.generate_wpw_pattern(
                duration=10.0,
                sampling_rate=self.sampling_rate
            )
        elif arrhythmia_type == "long_qt":
            signal, time = AdvancedEcgPatterns.generate_long_qt_pattern(
                duration=10.0,
                sampling_rate=self.sampling_rate,
                qt_prolongation=1.7
            )
        else:
            signal, time = AdvancedEcgPatterns.generate_short_qt_pattern(
                duration=10.0,
                sampling_rate=self.sampling_rate
            )
        
        # Create 12-lead representation (simplified for arrhythmias)
        ecg_signals = {
            'I': signal * 0.8,
            'II': signal,
            'III': signal * 0.9,
            'aVR': -signal,
            'aVL': signal * 0.7,
            'aVF': signal * 0.85,
            'V1': signal * 0.6,
            'V2': signal * 0.65,
            'V3': signal * 0.7,
            'V4': signal * 0.75,
            'V5': signal * 0.8,
            'V6': signal * 0.85,
            'time': time
        }
        
        interpretation = self.analyzer.analyze_12lead(ecg_signals)
        wave_annotations = self.annotator.annotate_lead(signal, 'II')
        
        return ComprehensiveEcgStudy(
            signals=ecg_signals,
            time=time,
            sampling_rate=self.sampling_rate,
            interpretation=interpretation,
            wave_annotations=wave_annotations,
            study_type=arrhythmia_type,
            complexity="advanced"
        )
    
    def create_clinical_case_study(
        self,
        patient_age: int,
        chief_complaint: str,
        history: str,
        ecg_findings: str,
        diagnosis: str
    ) -> ComprehensiveEcgStudy:
        """
        Create detailed clinical case study for teaching
        
        Args:
            patient_age: Age in years
            chief_complaint: Chief complaint (e.g., "chest pain")
            history: Medical history
            ecg_findings: ECG pattern to generate
            diagnosis: Expected diagnosis
            
        Returns:
            ComprehensiveEcgStudy with clinical context
        """
        # Map diagnosis to ECG pattern
        case_type_map = {
            "STEMI anterior": "anterior_stemi",
            "STEMI inferior": "inferior_stemi",
            "AF con RVR": "atrial_fibrillation",
            "Flutter auricular": "flutter",
            "WPW": "wpw",
            "Long QT": "long_qt",
        }
        
        case_type = case_type_map.get(diagnosis, "normal")
        
        if case_type in ["atrial_fibrillation", "flutter", "wpw", "long_qt"]:
            study = self.create_advanced_arrhythmia_study(arrhythmia_type=case_type)
        elif case_type in ["anterior_stemi", "inferior_stemi"]:
            study = self.create_intermediate_study(case_type=case_type)
        else:
            study = self.create_basic_study(case_type=case_type)
        
        # Add clinical context
        study.clinical_case = {
            "patient_age": patient_age,
            "chief_complaint": chief_complaint,
            "history": history,
            "expected_diagnosis": diagnosis
        }
        
        return study
    
    def get_educational_quiz(self, study: ComprehensiveEcgStudy) -> Dict:
        """
        Generate educational quiz from ECG study
        
        Returns:
            Quiz with question, options, answer, explanation
        """
        interpretation = study.interpretation
        
        # Generate quiz based on complexity
        if study.complexity == "basic":
            return self._generate_basic_quiz(interpretation)
        elif study.complexity == "intermediate":
            return self._generate_intermediate_quiz(interpretation)
        else:
            return self._generate_advanced_quiz(interpretation)
    
    def _generate_basic_quiz(self, interpretation: EcgInterpretation) -> Dict:
        """Generate basic-level quiz"""
        questions = [
            {
                "question": f"¿Cuál es el ritmo cardíaco observado?",
                "options": [
                    interpretation.rhythm,
                    "Fibrilación auricular",
                    "Flutter auricular",
                    "Taquicardia paroxística"
                ],
                "correct": 0,
                "explanation": f"El ritmo es {interpretation.rhythm}. Esta es una hallazgo fundamental del ECG."
            },
            {
                "question": f"¿Cuál es el diagnóstico principal?",
                "options": [
                    interpretation.primary_diagnosis,
                    interpretation.differential_diagnoses[0] if interpretation.differential_diagnoses else "ECG normal",
                    "Miocarditis aguda",
                    "Perimocarditis"
                ],
                "correct": 0,
                "explanation": f"Diagnóstico: {interpretation.primary_diagnosis}. {interpretation.clinical_significance}"
            }
        ]
        
        return {
            "complexity": "basic",
            "total_questions": len(questions),
            "questions": questions
        }
    
    def _generate_intermediate_quiz(self, interpretation: EcgInterpretation) -> Dict:
        """Generate intermediate-level quiz"""
        questions = [
            {
                "question": "¿Cuál es el eje QRS?",
                "options": [
                    interpretation.qrs_axis.category,
                    "Desviación izquierda severa",
                    "Desviación derecha severa",
                    "Eje indeterminado"
                ],
                "correct": 0,
                "explanation": f"Eje QRS: {interpretation.qrs_axis.description}"
            },
            {
                "question": "¿Cuáles son los hallazgos ST?",
                "options": [
                    f"{len(interpretation.st_findings)} elevaciones detectadas" if interpretation.st_findings else "Sin elevaciones ST",
                    "Depresión ST generalizada",
                    "ST indiferente",
                    "ST no evaluable"
                ],
                "correct": 0,
                "explanation": f"ST findings: {[f'{f.lead}: {f.elevation_mv:+.2f} mV' for f in interpretation.st_findings]}"
            }
        ]
        
        if interpretation.conduction_blocks:
            questions.append({
                "question": "¿Qué bloqueo de conducción está presente?",
                "options": [
                    interpretation.conduction_blocks[0].block_type,
                    "Bloqueo AV 2° grado",
                    "Bloqueo AV 3° grado",
                    "Sin bloqueo"
                ],
                "correct": 0,
                "explanation": f"Bloqueo: {interpretation.conduction_blocks[0].description}"
            })
        
        return {
            "complexity": "intermediate",
            "total_questions": len(questions),
            "questions": questions
        }
    
    def _generate_advanced_quiz(self, interpretation: EcgInterpretation) -> Dict:
        """Generate advanced-level quiz"""
        questions = [
            {
                "question": "¿Cuál es el territorio anatómico afectado?",
                "options": self.interpretation.differential_diagnoses[:4] if len(interpretation.differential_diagnoses) >= 4 else interpretation.differential_diagnoses + ["Normal"],
                "correct": 0,
                "explanation": f"Territorio: {interpretation.primary_diagnosis}"
            },
            {
                "question": "¿Cuál sería el siguiente paso clínico?",
                "options": interpretation.recommendations[:4] if len(interpretation.recommendations) >= 4 else interpretation.recommendations,
                "correct": 0,
                "explanation": "Las recomendaciones dependen de la urgencia y hallazgos clínicos."
            }
        ]
        
        return {
            "complexity": "advanced",
            "total_questions": len(questions),
            "questions": questions
        }


class EcgTutorIntegration:
    """Integration bridge with existing ECGTutor system"""
    
    @staticmethod
    def convert_to_ecg_tutor_case(study: ComprehensiveEcgStudy) -> Dict:
        """
        Convert ComprehensiveEcgStudy to ECGTutor format
        
        Returns:
            Dictionary compatible with existing ECGTutor system
        """
        return {
            'case_type': study.study_type,
            'titulo': study.interpretation.primary_diagnosis,
            'descripcion': study.interpretation.clinical_significance,
            'dificultad': study.complexity,
            'signals': study.signals,
            'time': study.time,
            'interpretation': study.interpretation,
            'annotations': study.wave_annotations,
            'clinical_context': study.clinical_case
        }
    
    @staticmethod
    def create_educational_module(study: ComprehensiveEcgStudy) -> Dict:
        """Create complete educational module from study"""
        return {
            'case': EcgTutorIntegration.convert_to_ecg_tutor_case(study),
            'learning_objectives': [
                f"Identificar {study.interpretation.primary_diagnosis}",
                f"Reconocer hallazgos de {study.study_type}",
                f"Aplicar criterios diagnósticos"
            ],
            'key_findings': [
                f"Ritmo: {study.interpretation.rhythm}",
                f"Eje: {study.interpretation.qrs_axis.category}",
                f"Diagnóstico: {study.interpretation.primary_diagnosis}"
            ]
        }


# Predefined clinical cases for teaching
TEACHING_CASES = {
    "case_001": {
        "title": "Dolor torácico agudo - Varón 45 años",
        "patient": {"age": 45, "sex": "M", "risk_factors": ["Hipertensión", "Tabaquismo"]},
        "complaint": "Dolor torácico anterior de 2 horas",
        "history": "Migraña hace 1 mes",
        "ecg_diagnosis": "STEMI anterior",
        "complexity": "intermediate"
    },
    "case_002": {
        "title": "Palpitaciones - Mujer 62 años",
        "patient": {"age": 62, "sex": "F", "risk_factors": ["Edad"]},
        "complaint": "Palpitaciones irregulares",
        "history": "Hipertensión controlada",
        "ecg_diagnosis": "AF con RVR",
        "complexity": "advanced"
    },
    "case_003": {
        "title": "Mareo - Varón 28 años",
        "patient": {"age": 28, "sex": "M", "risk_factors": ["Ninguno"]},
        "complaint": "Mareo con síncope presincope",
        "history": "Antecedentes familiares de muerte súbita",
        "ecg_diagnosis": "Long QT",
        "complexity": "advanced"
    }
}


def demo_comprehensive_study():
    """Demonstrate comprehensive ECG study generation"""
    
    print("╔════════════════════════════════════════════════════════════╗")
    print("║  12-LEAD ECG COMPREHENSIVE STUDY GENERATION & INTEGRATION ║")
    print("╚════════════════════════════════════════════════════════════╝\n")
    
    # Create generator
    generator = EcgStudyGenerator(sampling_rate=250)
    
    # Basic study
    print("📚 BASIC STUDY: Normal Sinus Rhythm")
    basic_study = generator.create_basic_study(case_type="normal", heart_rate=75)
    print(f"  ✅ Generated: {len(basic_study.signals)} leads, {len(basic_study.time)} samples")
    print(f"  📊 Diagnosis: {basic_study.interpretation.primary_diagnosis}")
    print(f"  🎓 Complexity: {basic_study.complexity}\n")
    
    # Intermediate study
    print("📚 INTERMEDIATE STUDY: Anterior STEMI")
    intermediate_study = generator.create_intermediate_study(case_type="anterior_stemi")
    print(f"  ✅ Generated: {len(intermediate_study.signals)} leads")
    print(f"  🚨 Diagnosis: {intermediate_study.interpretation.primary_diagnosis}")
    print(f"  ⚕️ Urgency: {intermediate_study.interpretation.clinical_significance[:30]}...\n")
    
    # Advanced arrhythmia study
    print("📚 ADVANCED STUDY: Atrial Fibrillation")
    advanced_study = generator.create_advanced_arrhythmia_study(arrhythmia_type="atrial_fibrillation")
    print(f"  ✅ Generated: Arrhythmia pattern")
    print(f"  💓 Diagnosis: {advanced_study.interpretation.primary_diagnosis}")
    print(f"  🎓 Complexity: {advanced_study.complexity}\n")
    
    # Clinical case
    print("📚 CLINICAL CASE: Teaching Module")
    clinical_study = generator.create_clinical_case_study(
        patient_age=45,
        chief_complaint="Dolor torácico agudo",
        history="Hipertensión, tabaquismo",
        ecg_findings="STEMI anterior",
        diagnosis="STEMI anterior"
    )
    print(f"  👤 Patient: {clinical_study.clinical_case['patient_age']} años")
    print(f"  🩺 Chief complaint: {clinical_study.clinical_case['chief_complaint']}")
    print(f"  📋 Diagnosis: {clinical_study.clinical_case['expected_diagnosis']}\n")
    
    # Educational quiz
    print("📝 EDUCATIONAL QUIZ")
    quiz = generator.get_educational_quiz(intermediate_study)
    print(f"  📊 Complexity: {quiz['complexity']}")
    print(f"  ❓ Total questions: {quiz['total_questions']}")
    for i, q in enumerate(quiz['questions'], 1):
        print(f"    {i}. {q['question'][:50]}...\n")
    
    print("✅ Comprehensive ECG study generation completed successfully!")


if __name__ == "__main__":
    demo_comprehensive_study()
