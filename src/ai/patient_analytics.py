"""
ML-based Patient Analytics - Real AI Risk Scoring and Anomaly Detection
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta


class PatientRiskPredictor:
    """ML-based cardiovascular risk prediction using vital signs and historical data."""
    
    def __init__(self):
        self.risk_weights = {
            'age': 0.15,
            'heart_rate': 0.20,
            'blood_pressure': 0.25,
            'ecg_pattern': 0.20,
            'hrv': 0.10,
            'trend': 0.10
        }
    
    def calculate_risk_score(self,
                            age: Optional[int] = None,
                            heart_rate: Optional[float] = None,
                            systolic_bp: Optional[float] = None,
                            diastolic_bp: Optional[float] = None,
                            ecg_pattern: str = 'normal',
                            hrv_sdnn: Optional[float] = None,
                            trend_data: List[float] = None) -> Dict[str, Any]:
        """
        Calculate comprehensive cardiovascular risk score using multiple factors.

        Tanda 4 (2026-07-04): todos los factores salvo `ecg_pattern` son ahora
        opcionales. Cuando una fuente real no está disponible (p.ej. el UPS no
        modela presión arterial ni demografía — solo cardiovascular y
        respiratorio), el factor correspondiente se OMITE del score en vez de
        rellenarse con un valor típico inventado — "simulación ≠ dato falso"
        aplica también a "dato ausente ≠ dato inventado". El peso total se
        renormaliza sobre los factores realmente disponibles, para que
        `total_risk` siga siendo comparable en escala 0-1 sin importar cuántos
        factores falten.

        Args:
            age: Patient age in years (None si no hay una fuente real)
            heart_rate: Current heart rate in bpm (None si no hay una fuente real)
            systolic_bp: Systolic blood pressure in mmHg (None si no hay una fuente real)
            diastolic_bp: Diastolic blood pressure in mmHg (None si no hay una fuente real)
            ecg_pattern: ECG classification (siempre 'normal' u otro patrón real, nunca None)
            hrv_sdnn: Heart rate variability (SDNN in ms, None si no hay una fuente real)
            trend_data: Historical heart rate trend (last 7 measurements)

        Returns:
            Dict con el score, factores realmente usados, y factores omitidos
            por falta de dato real (`factors_used` / `factors_omitted`).
        """
        scores = {}
        omitted = []

        # Age risk (0-1 scale)
        if age is not None:
            scores['age'] = min((age - 18) / 82, 1.0) if age >= 18 else 0.0
        else:
            omitted.append('age')

        # Heart rate risk
        if heart_rate is not None:
            if 60 <= heart_rate <= 100:
                hr_score = 0.0
            elif 50 <= heart_rate < 60 or 100 < heart_rate <= 120:
                hr_score = 0.3
            elif 40 <= heart_rate < 50 or 120 < heart_rate <= 150:
                hr_score = 0.6
            else:
                hr_score = 1.0
            scores['heart_rate'] = hr_score
        else:
            omitted.append('heart_rate')

        # Blood pressure risk (using Framingham model-like scoring) — requiere ambos valores
        if systolic_bp is not None and diastolic_bp is not None:
            scores['blood_pressure'] = self._calculate_bp_risk(systolic_bp, diastolic_bp)
        else:
            omitted.append('blood_pressure')

        # ECG pattern risk — siempre presente (default 'normal' es un patrón real, no un placeholder)
        ecg_risk_map = {
            'normal': 0.0,
            'arrhythmia': 0.4,
            'ischemia': 0.6,
            'stemi': 1.0,
            'af': 0.5,
            'unknown': 0.3,
        }
        scores['ecg_pattern'] = ecg_risk_map.get(ecg_pattern.lower(), 0.3)

        # HRV risk (lower HRV = higher risk)
        if hrv_sdnn is not None:
            if hrv_sdnn >= 50:
                hrv_score = 0.0
            elif 30 <= hrv_sdnn < 50:
                hrv_score = 0.3
            elif 20 <= hrv_sdnn < 30:
                hrv_score = 0.6
            else:
                hrv_score = 1.0
            scores['hrv'] = hrv_score
        else:
            omitted.append('hrv')

        # Trend analysis risk
        if trend_data:
            scores['trend'] = self._calculate_trend_risk(trend_data)
        else:
            omitted.append('trend')

        # Weighted total risk, renormalizado sobre los pesos realmente usados
        used_weight_sum = sum(self.risk_weights[key] for key in scores)
        if used_weight_sum <= 0:
            return {
                'total_risk': None,
                'risk_level': "⚪ Datos insuficientes",
                'color': "#94a3b8",
                'contributing_factors': {},
                'factors_used': [],
                'factors_omitted': omitted,
                'recommendations': ["No hay suficientes datos reales para calcular un score de riesgo."],
            }
        total_risk = sum(scores[key] * self.risk_weights[key] for key in scores) / used_weight_sum

        # Classify risk level
        if total_risk < 0.2:
            risk_level = "🟢 Bajo riesgo"
            color = "#22c55e"
        elif total_risk < 0.5:
            risk_level = "🟡 Riesgo moderado"
            color = "#eab308"
        elif total_risk < 0.8:
            risk_level = "🟠 Riesgo elevado"
            color = "#f97316"
        else:
            risk_level = "🔴 Riesgo muy alto"
            color = "#ef4444"

        return {
            'total_risk': round(total_risk, 3),
            'risk_level': risk_level,
            'color': color,
            'contributing_factors': scores,
            'factors_used': list(scores.keys()),
            'factors_omitted': omitted,
            'recommendations': self._get_recommendations(total_risk, scores)
        }
    
    def _calculate_bp_risk(self, systolic: float, diastolic: float) -> float:
        """Calculate blood pressure risk using stages."""
        if systolic < 120 and diastolic < 80:
            return 0.0
        elif systolic < 130 and diastolic < 80:
            return 0.2
        elif systolic < 140 or diastolic < 90:
            return 0.4
        elif systolic < 160 or diastolic < 100:
            return 0.7
        else:
            return 1.0
    
    def _calculate_trend_risk(self, trend_data: List[float]) -> float:
        """Calculate risk from heart rate trend (positive trend = increasing HR)."""
        if len(trend_data) < 2:
            return 0.0
        
        trend = np.polyfit(np.arange(len(trend_data)), trend_data, 1)[0]
        
        if trend < -2:  # HR decreasing significantly
            return 0.3
        elif -2 <= trend <= 2:  # HR stable
            return 0.0
        elif 2 < trend < 5:  # HR increasing moderately
            return 0.3
        else:  # HR increasing significantly
            return 0.6
    
    def _get_recommendations(self, risk_score: float, factors: Dict) -> List[str]:
        """Generate personalized recommendations based on risk profile.

        Tanda 4: `factors` ahora puede no traer todas las claves (factores
        omitidos por falta de dato real) — se usa `.get(key, 0.0)` en vez de
        indexado directo para no fallar cuando faltan."""
        recommendations = []

        if risk_score >= 0.5:
            recommendations.append("⚠️ Considere consulta cardiólogo urgente")

        if factors.get('blood_pressure', 0.0) > 0.5:
            recommendations.append("📋 Monitorizar presión arterial diariamente")

        if factors.get('heart_rate', 0.0) > 0.5:
            recommendations.append("💓 Frecuencia cardíaca elevada - evaluar causa")

        if factors.get('hrv', 0.0) > 0.5:
            recommendations.append("😰 HRV baja - posible estrés o fatiga")

        if factors.get('trend', 0.0) > 0.3:
            recommendations.append("📈 Tendencia adversa detectada en últimas mediciones")
        
        if risk_score < 0.3:
            recommendations.append("✅ Continuar seguimiento de rutina")
        
        return recommendations[:3]  # Top 3 recommendations


class AnomalyDetector:
    """Real-time anomaly detection in vital signs using statistical methods."""
    
    def __init__(self, window_size: int = 20):
        self.window_size = window_size
        self.baseline_stats = {}
    
    def detect_anomalies(self, 
                        signal: np.ndarray,
                        parameter_name: str = 'vitals',
                        threshold_std: float = 2.5) -> Dict[str, Any]:
        """
        Detect anomalies using Z-score method.
        
        Args:
            signal: Time series of measurements
            parameter_name: Name of the parameter being analyzed
            threshold_std: Number of standard deviations for anomaly threshold
        
        Returns:
            Dict with anomaly detection results
        """
        if len(signal) < 3:
            return {
                'anomalies_detected': False,
                'anomaly_indices': [],
                'anomaly_values': [],
                'severity': 'unknown'
            }
        
        # Calculate statistics
        mean = np.mean(signal)
        std = np.std(signal)
        
        if std < 1e-6:  # Flat signal
            return {
                'anomalies_detected': True,
                'anomaly_indices': list(range(len(signal))),
                'anomaly_values': list(signal),
                'severity': 'critical',
                'message': 'Señal plana - posible fallo de sensor'
            }
        
        # Calculate z-scores
        z_scores = np.abs((signal - mean) / std)
        
        # Identify anomalies
        anomaly_indices = np.where(z_scores > threshold_std)[0]
        
        if len(anomaly_indices) == 0:
            return {
                'anomalies_detected': False,
                'anomaly_indices': [],
                'anomaly_values': [],
                'severity': 'normal'
            }
        
        # Calculate severity
        max_z = np.max(z_scores)
        if max_z > 4:
            severity = 'critical'
        elif max_z > 3:
            severity = 'high'
        else:
            severity = 'moderate'
        
        return {
            'anomalies_detected': True,
            'anomaly_indices': anomaly_indices.tolist(),
            'anomaly_values': signal[anomaly_indices].tolist(),
            'severity': severity,
            'max_deviation_std': round(max_z, 2),
            'percentage_anomalous': round(100 * len(anomaly_indices) / len(signal), 1)
        }
    
    def detect_pattern_change(self,
                             historical_signal: np.ndarray,
                             recent_signal: np.ndarray,
                             sensitivity: float = 0.7) -> Dict[str, Any]:
        """
        Detect changes in signal patterns using correlation.
        
        Args:
            historical_signal: Baseline pattern
            recent_signal: Current pattern
            sensitivity: Detection sensitivity (0-1)
        
        Returns:
            Pattern change detection results
        """
        if len(historical_signal) < 2 or len(recent_signal) < 2:
            return {
                'pattern_changed': False,
                'correlation': 1.0,
                'change_magnitude': 0.0
            }
        
        # Normalize signals
        hist_norm = (historical_signal - np.mean(historical_signal)) / (np.std(historical_signal) + 1e-6)
        recent_norm = (recent_signal - np.mean(recent_signal)) / (np.std(recent_signal) + 1e-6)
        
        # Truncate to same length
        min_len = min(len(hist_norm), len(recent_norm))
        hist_norm = hist_norm[:min_len]
        recent_norm = recent_norm[:min_len]
        
        # Calculate correlation
        correlation = np.corrcoef(hist_norm, recent_norm)[0, 1]
        
        # Determine if pattern changed
        threshold = 0.5 + 0.5 * (1 - sensitivity)
        pattern_changed = correlation < threshold
        
        return {
            'pattern_changed': pattern_changed,
            'correlation': round(correlation, 3),
            'change_magnitude': round(1 - correlation, 3),
            'severity': 'high' if pattern_changed and correlation < 0.3 else 'moderate' if pattern_changed else 'normal'
        }


class AdaptiveQuizEngine:
    """ML-based adaptive quiz generation based on student performance."""
    
    def __init__(self):
        self.difficulty_levels = ['beginner', 'intermediate', 'advanced', 'expert']
        self.question_bank = {}
    
    def assess_student_level(self, 
                            correct_answers: int,
                            total_questions: int,
                            response_times: List[float] = None) -> Dict[str, Any]:
        """
        Adaptively assess student competency level.
        
        Args:
            correct_answers: Number of correct responses
            total_questions: Total number of questions attempted
            response_times: Time taken for each question (in seconds)
        
        Returns:
            Student assessment and recommended difficulty level
        """
        if total_questions == 0:
            accuracy = 0.0
        else:
            accuracy = correct_answers / total_questions
        
        # Calculate average response time confidence
        avg_response_time = np.mean(response_times) if response_times else 30.0
        time_confidence = min(1.0, 20.0 / avg_response_time) if avg_response_time > 0 else 0.5
        
        # Combined competency score
        competency_score = 0.7 * accuracy + 0.3 * time_confidence
        
        # Determine difficulty level
        if competency_score >= 0.85:
            level = 'expert'
            level_idx = 3
        elif competency_score >= 0.70:
            level = 'advanced'
            level_idx = 2
        elif competency_score >= 0.50:
            level = 'intermediate'
            level_idx = 1
        else:
            level = 'beginner'
            level_idx = 0
        
        return {
            'competency_score': round(competency_score, 3),
            'recommended_level': level,
            'accuracy': round(accuracy, 3),
            'time_efficiency': round(time_confidence, 3),
            'next_difficulty_adjustment': 'increase' if competency_score >= 0.8 else 'maintain' if competency_score >= 0.6 else 'decrease'
        }
    
    def generate_adaptive_question(self, 
                                  topic: str,
                                  difficulty: str,
                                  student_weak_areas: List[str] = None) -> Dict[str, Any]:
        """
        Generate adaptive quiz question based on student profile.
        
        Args:
            topic: Topic area (e.g., 'ECG', 'Arrhythmia', 'HRV')
            difficulty: Difficulty level
            student_weak_areas: Areas where student struggled
        
        Returns:
            Adaptive quiz question
        """
        # Prioritize weak areas
        focus_area = student_weak_areas[0] if student_weak_areas else topic
        
        # Question generation (simplified)
        difficulty_map = {
            'beginner': 'Básica - Definición/Reconocimiento',
            'intermediate': 'Intermedia - Análisis/Aplicación',
            'advanced': 'Avanzada - Síntesis/Evaluación',
            'expert': 'Experto - Análisis crítico/Investigación'
        }
        
        return {
            'topic': focus_area,
            'difficulty': difficulty_map[difficulty],
            'adaptive_hint': '🎯 Pregunta adaptada a tu nivel',
            'is_weak_area_focus': student_weak_areas is not None
        }


# Example usage and testing
if __name__ == '__main__':
    # Test Risk Predictor
    predictor = PatientRiskPredictor()
    risk = predictor.calculate_risk_score(
        age=65,
        heart_rate=92,
        systolic_bp=145,
        diastolic_bp=90,
        ecg_pattern='arrhythmia',
        hrv_sdnn=35,
        trend_data=[80, 82, 85, 88, 90]
    )
    print("Risk Score:", risk)
    
    # Test Anomaly Detector
    detector = AnomalyDetector()
    signal = np.array([70, 72, 71, 120, 75, 73, 74, 150, 72, 71])  # Contains anomalies
    anomalies = detector.detect_anomalies(signal, parameter_name='heart_rate')
    print("\nAnomalies:", anomalies)
    
    # Test Adaptive Quiz
    quiz = AdaptiveQuizEngine()
    assessment = quiz.assess_student_level(
        correct_answers=18,
        total_questions=20,
        response_times=[5.2, 6.1, 4.8] * 6 + [5.0, 5.1]
    )
    print("\nStudent Assessment:", assessment)
