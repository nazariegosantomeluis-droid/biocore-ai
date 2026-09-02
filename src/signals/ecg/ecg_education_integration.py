"""
ECG System Integration with Existing Educational Platform

Bridges the new 12-lead ECG system with:
- Existing ECGTutor system
- Educational module structure
- Quiz generation
- Student tracking
- Clinical case management
"""

import sys
from typing import Dict, List, Optional

# Import new components
from src.signals.ecg.integrated_ecg_system import (
    EcgStudyGenerator,
    ComprehensiveEcgStudy,
    EcgTutorIntegration,
    TEACHING_CASES
)

# Import existing components (these should be in educational/ecg_tutor.py)
try:
    from educational.ecg_tutor import ECGTutor, ECGTutorCase
    HAS_ECG_TUTOR = True
except ImportError:
    HAS_ECG_TUTOR = False
    print("⚠️ Warning: ECGTutor not found. Creating adapter.")


class UnifiedEcgEducationSystem:
    """
    Unified system combining:
    - 12-lead ECG generation and analysis
    - Wave annotation
    - Advanced patterns
    - Educational content
    - Student progress tracking
    """
    
    def __init__(self):
        """Initialize unified system"""
        self.study_generator = EcgStudyGenerator(sampling_rate=250)
        self.cases = {}
        self.student_progress = {}
        self._initialize_default_cases()
    
    def _initialize_default_cases(self):
        """Load predefined teaching cases"""
        for case_id, case_data in TEACHING_CASES.items():
            self.cases[case_id] = case_data
    
    def generate_case(self, case_id: str) -> ComprehensiveEcgStudy:
        """Generate a teaching case"""
        case_data = self.cases.get(case_id)
        
        if not case_data:
            # Create a basic normal case as fallback
            return self.study_generator.create_basic_study()
        
        # Create study from case data
        study = self.study_generator.create_clinical_case_study(
            patient_age=case_data.get('patient', {}).get('age', 45),
            chief_complaint=case_data.get('complaint', ''),
            history=case_data.get('history', ''),
            ecg_findings=case_data.get('ecg_diagnosis', 'normal'),
            diagnosis=case_data.get('ecg_diagnosis', 'normal')
        )
        
        return study
    
    def get_quiz_for_case(self, study: ComprehensiveEcgStudy) -> Dict:
        """Get quiz for a case"""
        quiz = self.study_generator.get_educational_quiz(study)
        return quiz
    
    def track_student_progress(
        self, 
        student_id: str, 
        case_id: str, 
        quiz_answers: List[int],
        correct_answers: List[int]
    ) -> Dict:
        """Track student performance"""
        
        if student_id not in self.student_progress:
            self.student_progress[student_id] = {
                'completed_cases': [],
                'quiz_scores': [],
                'total_attempts': 0,
                'average_score': 0
            }
        
        # Calculate score
        correct = sum(1 for a, c in zip(quiz_answers, correct_answers) if a == c)
        total = len(correct_answers)
        score = (correct / total * 100) if total > 0 else 0
        
        # Update progress
        progress = self.student_progress[student_id]
        progress['completed_cases'].append(case_id)
        progress['quiz_scores'].append(score)
        progress['total_attempts'] += 1
        progress['average_score'] = sum(progress['quiz_scores']) / len(progress['quiz_scores'])
        
        return {
            'case_id': case_id,
            'score': score,
            'correct': correct,
            'total': total,
            'student_average': progress['average_score']
        }
    
    def get_student_progress(self, student_id: str) -> Dict:
        """Get student's learning progress"""
        return self.student_progress.get(student_id, {
            'completed_cases': [],
            'quiz_scores': [],
            'total_attempts': 0,
            'average_score': 0
        })
    
    def get_recommended_case(self, student_id: str) -> str:
        """Recommend next case based on progress"""
        progress = self.get_student_progress(student_id)
        completed = set(progress['completed_cases'])
        available = set(self.cases.keys())
        
        # Get cases not yet completed
        remaining = available - completed
        
        if not remaining:
            return None  # All cases completed
        
        # Sort remaining by difficulty (basic, intermediate, advanced)
        difficulty_order = {'basic': 0, 'intermediate': 1, 'advanced': 2}
        
        sorted_remaining = sorted(
            remaining,
            key=lambda x: difficulty_order.get(
                self.cases.get(x, {}).get('complexity', 'basic'), 
                0
            )
        )
        
        return sorted_remaining[0] if sorted_remaining else None
    
    def generate_student_report(self, student_id: str) -> Dict:
        """Generate comprehensive student report"""
        progress = self.get_student_progress(student_id)
        
        report = {
            'student_id': student_id,
            'total_cases_completed': len(progress['completed_cases']),
            'average_quiz_score': f"{progress['average_score']:.1f}%",
            'total_attempts': progress['total_attempts'],
            'completed_cases': progress['completed_cases'],
            'quiz_scores': [f"{s:.1f}%" for s in progress['quiz_scores']],
            'recommendation': self._get_learning_recommendation(progress)
        }
        
        return report
    
    def _get_learning_recommendation(self, progress: Dict) -> str:
        """Generate learning recommendations"""
        avg_score = progress['average_score']
        
        if avg_score >= 85:
            return "🌟 Excelente! Listo para casos más avanzados"
        elif avg_score >= 70:
            return "✅ Buen progreso! Continúa practicando"
        elif avg_score >= 55:
            return "🟡 En progreso. Revisa los conceptos principales"
        else:
            return "📚 Recomendado: Revisar material educativo básico"


class ECGStreamlitIntegration:
    """Integration utilities for Streamlit pages"""
    
    @staticmethod
    def display_comprehensive_study(study: ComprehensiveEcgStudy):
        """Display comprehensive study in Streamlit"""
        import streamlit as st
        
        # Display clinical context if available
        if study.clinical_case:
            st.markdown("### 👤 Contexto Clínico")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.write(f"**Edad:** {study.clinical_case['patient_age']}")
            with col2:
                st.write(f"**Queja Principal:** {study.clinical_case['chief_complaint']}")
            with col3:
                st.write(f"**Complejidad:** {study.complexity}")
        
        # Display ECG interpretation
        st.markdown("### 📋 Interpretación ECG")
        
        interpretation = study.interpretation
        col1, col2 = st.columns(2)
        
        with col1:
            st.write(f"**Diagnóstico:** {interpretation.primary_diagnosis}")
            st.write(f"**Ritmo:** {interpretation.rhythm}")
            st.write(f"**Eje:** {interpretation.qrs_axis.description}")
        
        with col2:
            if interpretation.st_findings:
                st.write(f"**Hallazgos ST:** {len(interpretation.st_findings)} detectadas")
            if interpretation.conduction_blocks:
                st.write(f"**Bloqueos:** {interpretation.conduction_blocks[0].block_type}")
        
        # Display wave annotations for Lead II
        if study.wave_annotations:
            st.markdown("### 📊 Anotación de Ondas (Derivación II)")
            for annotation in study.wave_annotations[:2]:  # Show first 2 beats
                with st.expander(f"Beat #{annotation.beat_num}"):
                    st.write(f"PR Interval: {annotation.pr_interval_ms:.0f} ms")
                    st.write(f"QRS Duration: {annotation.qrs_duration_ms:.0f} ms")
                    st.write(f"QT Interval: {annotation.qt_interval_ms:.0f} ms")
                    st.write(f"ST Segment: {annotation.st_segment_level:+.2f} mV")
        
        # Clinical recommendations
        st.markdown("### ⚠️ Recomendaciones Clínicas")
        for rec in interpretation.recommendations[:3]:
            st.write(f"  • {rec}")
    
    @staticmethod
    def display_quiz(quiz: Dict):
        """Display interactive quiz in Streamlit"""
        import streamlit as st
        
        st.markdown(f"### 🎓 Quiz - Complejidad: {quiz['complexity'].upper()}")
        st.write(f"Total de preguntas: {quiz['total_questions']}")
        
        quiz_answers = []
        
        for i, question in enumerate(quiz['questions'], 1):
            st.write(f"**Pregunta {i}:** {question['question']}")
            answer = st.radio(
                f"Respuesta {i}",
                question['options'],
                key=f"quiz_q{i}"
            )
            # Store index of selected answer
            quiz_answers.append(question['options'].index(answer))
        
        if st.button("📤 Enviar respuestas", key="submit_quiz"):
            # Calculate score
            correct = sum(1 for ans, correct_idx in zip(quiz_answers, 
                         [q['correct'] for q in quiz['questions']]) 
                         if ans == correct_idx)
            total = len(quiz['questions'])
            score = (correct / total * 100) if total > 0 else 0
            
            st.success(f"📊 Puntuación: {score:.0f}% ({correct}/{total} correctas)")
            
            # Show explanations
            st.markdown("### 📝 Explicaciones")
            for i, (question, answer_idx) in enumerate(zip(quiz['questions'], quiz_answers), 1):
                is_correct = answer_idx == question['correct']
                status = "✅" if is_correct else "❌"
                st.write(f"{status} Pregunta {i}: {question['explanation']}")


# Example usage
def demo_unified_system():
    """Demonstrate the unified system"""
    print("╔════════════════════════════════════════════════════════════╗")
    print("║   UNIFIED ECG EDUCATION SYSTEM DEMONSTRATION               ║")
    print("╚════════════════════════════════════════════════════════════╝\n")
    
    # Initialize system
    system = UnifiedEcgEducationSystem()
    print("✅ System initialized")
    print(f"   - {len(system.cases)} predefined teaching cases\n")
    
    # Generate a case
    case_id = 'case_001'
    study = system.generate_case(case_id)
    print(f"📚 Generated case: {system.cases[case_id]['title']}")
    print(f"   - Patient age: {study.clinical_case['patient_age']}")
    print(f"   - Diagnosis: {study.clinical_case['expected_diagnosis']}\n")
    
    # Get quiz
    quiz = system.get_quiz_for_case(study)
    print(f"🎓 Generated quiz: {quiz['total_questions']} questions\n")
    
    # Simulate student progress
    print("👤 Simulating student progress...")
    student_id = "STUDENT_001"
    
    # First attempt
    quiz_answers = [0, 0, 1]  # Mix of correct and incorrect
    correct_answers = [0, 0, 0]
    result = system.track_student_progress(student_id, case_id, quiz_answers, correct_answers)
    print(f"   - Case 1: {result['score']:.0f}% ({result['correct']}/{result['total']})\n")
    
    # Generate report
    report = system.generate_student_report(student_id)
    print(f"📊 Student Report for {student_id}:")
    print(f"   - Total cases: {report['total_cases_completed']}")
    print(f"   - Average score: {report['average_quiz_score']}")
    print(f"   - Recommendation: {report['recommendation']}")
    
    print("\n✅ Unified system demonstration completed!")


if __name__ == "__main__":
    demo_unified_system()
