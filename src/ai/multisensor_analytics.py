"""
Multisensor ML Analysis - Real-time physiological correlation and predictive health scores
"""

import numpy as np
from typing import Dict, List, Tuple, Any
import warnings
warnings.filterwarnings('ignore')


class MultisensorAnalyzer:
    """Advanced multisensor analysis with real-time correlation and health profiling."""
    
    def __init__(self):
        self.baseline_profiles = {
            'healthy': {
                'hr_range': (60, 100),
                'spo2_min': 95,
                'rr_range': (12, 20),
                'temp_range': (36.5, 37.5),
                'bp_systolic': (100, 140),
                'bp_diastolic': (60, 90),
            }
        }
    
    def calculate_comprehensive_health_index(self,
                                            heart_rate: float,
                                            spo2: float,
                                            respiration_rate: float,
                                            temperature: float,
                                            systolic_bp: float,
                                            diastolic_bp: float) -> Dict[str, Any]:
        """
        Calculate a comprehensive health index combining multiple vital signs.
        
        Returns:
            Dict with health score (0-1), interpretation, and contributing factors
        """
        scores = {}
        
        # HR contribution (normalized)
        if 60 <= heart_rate <= 100:
            hr_score = 1.0
        elif 50 <= heart_rate < 60 or 100 < heart_rate <= 120:
            hr_score = 0.7
        else:
            hr_score = 0.3
        scores['heart_rate'] = hr_score
        
        # SpO2 contribution
        if spo2 >= 95:
            spo2_score = 1.0
        elif spo2 >= 90:
            spo2_score = 0.7
        elif spo2 >= 85:
            spo2_score = 0.4
        else:
            spo2_score = 0.1
        scores['spo2'] = spo2_score
        
        # Respiration rate contribution
        if 12 <= respiration_rate <= 20:
            rr_score = 1.0
        elif 10 <= respiration_rate < 12 or 20 < respiration_rate <= 25:
            rr_score = 0.7
        else:
            rr_score = 0.3
        scores['respiration'] = rr_score
        
        # Temperature contribution
        if 36.5 <= temperature <= 37.5:
            temp_score = 1.0
        elif 36.0 <= temperature < 36.5 or 37.5 < temperature <= 38.0:
            temp_score = 0.7
        else:
            temp_score = 0.3
        scores['temperature'] = temp_score
        
        # Blood pressure contribution
        if 100 <= systolic_bp <= 140 and 60 <= diastolic_bp <= 90:
            bp_score = 1.0
        elif 90 <= systolic_bp < 100 or 140 < systolic_bp <= 160:
            bp_score = 0.7
        else:
            bp_score = 0.3
        scores['blood_pressure'] = bp_score
        
        # Weighted average
        weights = {
            'heart_rate': 0.25,
            'spo2': 0.30,
            'respiration': 0.20,
            'temperature': 0.15,
            'blood_pressure': 0.10,
        }
        
        health_index = sum(scores[k] * weights[k] for k in scores)
        
        # Interpretation
        if health_index >= 0.85:
            interpretation = "✅ Excelente - Todos los signos normales"
            color = "#22c55e"
        elif health_index >= 0.70:
            interpretation = "🟡 Bueno - Ligeras variaciones observadas"
            color = "#84cc16"
        elif health_index >= 0.50:
            interpretation = "⚠️ Moderado - Requiere monitorización"
            color = "#f97316"
        else:
            interpretation = "🔴 Crítico - Buscar atención médica"
            color = "#ef4444"
        
        return {
            'health_index': round(health_index, 3),
            'interpretation': interpretation,
            'color': color,
            'component_scores': scores,
            'critical_flags': self._identify_critical_flags(scores, (heart_rate, spo2, respiration_rate, temperature, systolic_bp, diastolic_bp))
        }
    
    def _identify_critical_flags(self, scores: Dict, vitals: Tuple) -> List[str]:
        """Identify critical warning signs."""
        flags = []
        hr, spo2, rr, temp, sys_bp, dia_bp = vitals
        
        if spo2 < 90:
            flags.append("🚨 SpO2 crítico - Hipoxemia grave")
        elif spo2 < 93:
            flags.append("⚠️ SpO2 bajo - Posible hipoxemia")
        
        if hr > 120 or hr < 40:
            flags.append("⚠️ HR extrema - Bradicardia o taquicardia severa")
        
        if rr > 30 or rr < 8:
            flags.append("⚠️ RR anormal - Posible distress respiratorio")
        
        if temperature > 38.5 or temperature < 35.5:
            flags.append("⚠️ Temperatura extrema - Fiebre o hipotermia")
        
        if sys_bp > 180 or sys_bp < 80:
            flags.append("⚠️ Presión arterial crítica")
        
        return flags[:3]  # Top 3 flags
    
    def detect_cardiorespiratory_correlation(self,
                                            heart_rate_trend: np.ndarray,
                                            respiration_trend: np.ndarray) -> Dict[str, Any]:
        """
        Detect correlation between heart rate and respiration patterns.
        Respiratory sinus arrhythmia is normal (HR increases with inspiration).
        """
        if len(heart_rate_trend) < 5 or len(respiration_trend) < 5:
            return {
                'correlation_detected': False,
                'correlation_strength': 0.0,
                'pattern': 'insufficient_data'
            }
        
        # Normalize signals
        hr_norm = (heart_rate_trend - np.mean(heart_rate_trend)) / (np.std(heart_rate_trend) + 1e-6)
        rr_norm = (respiration_trend - np.mean(respiration_trend)) / (np.std(respiration_trend) + 1e-6)
        
        # Truncate to same length
        min_len = min(len(hr_norm), len(rr_norm))
        hr_norm = hr_norm[:min_len]
        rr_norm = rr_norm[:min_len]
        
        # Calculate correlation
        correlation = np.corrcoef(hr_norm, rr_norm)[0, 1]
        
        # Interpret
        if correlation > 0.6:
            pattern = 'strong_positive_correlation'
            interpretation = "Correlación fuerte HR-RR (normal)"
        elif correlation > 0.3:
            pattern = 'moderate_correlation'
            interpretation = "Correlación moderada detectada"
        else:
            pattern = 'weak_correlation'
            interpretation = "Baja correlación o independencia"
        
        return {
            'correlation_detected': correlation > 0.3,
            'correlation_strength': round(correlation, 3),
            'pattern': pattern,
            'interpretation': interpretation,
            'clinical_significance': 'Patrón fisiológico normal' if correlation > 0.3 else 'Podría indicar disritmia'
        }
    
    def predict_hypoxemia_risk(self,
                              spo2: float,
                              respiration_rate: float,
                              heart_rate: float,
                              recent_spo2_trend: List[float] = None) -> Dict[str, Any]:
        """
        Predict risk of hypoxemia development based on current vitals and trends.
        """
        risk_factors = []
        risk_score = 0.0
        
        # SpO2 level
        if spo2 < 90:
            risk_factors.append("SpO2 < 90%")
            risk_score += 0.4
        elif spo2 < 94:
            risk_factors.append("SpO2 94-95%")
            risk_score += 0.2
        
        # Respiration abnormality
        if respiration_rate > 25:
            risk_factors.append("Taquipnea (RR > 25)")
            risk_score += 0.25
        elif respiration_rate < 10:
            risk_factors.append("Bradipnea (RR < 10)")
            risk_score += 0.3
        
        # HR compensation
        if heart_rate > 110:
            risk_factors.append("Taquicardia compensatoria")
            risk_score += 0.15
        
        # SpO2 trending downward
        if recent_spo2_trend and len(recent_spo2_trend) >= 3:
            trend_slope = recent_spo2_trend[-1] - recent_spo2_trend[-3]
            if trend_slope < -2:
                risk_factors.append("SpO2 disminuyendo")
                risk_score += 0.2
        
        risk_score = min(risk_score, 1.0)
        
        if risk_score >= 0.7:
            risk_level = "🔴 ALTO"
            recommendation = "Evaluar causa inmediatamente, considerar O2 suplementario"
        elif risk_score >= 0.4:
            risk_level = "🟠 MODERADO"
            recommendation = "Monitorizar estrechamente, estar preparado para intervención"
        else:
            risk_level = "🟢 BAJO"
            recommendation = "Monitorización de rutina"
        
        return {
            'risk_score': round(risk_score, 3),
            'risk_level': risk_level,
            'risk_factors': risk_factors,
            'recommendation': recommendation
        }
    
    def generate_multisensor_report(self,
                                   vitals_dict: Dict[str, float],
                                   trends_dict: Dict[str, List[float]] = None) -> str:
        """Generate comprehensive multisensor clinical report."""
        report = """
╔════════════════════════════════════════════════════════════╗
║         REPORTE MULTISENSORIAL INTEGRADO                  ║
╚════════════════════════════════════════════════════════════╝

SIGNOS VITALES ACTUALES:
"""
        for param, value in vitals_dict.items():
            report += f"  • {param}: {value}\n"
        
        # Health index
        health = self.calculate_comprehensive_health_index(**vitals_dict)
        report += f"\nÍNDICE DE SALUD INTEGRAL: {health['health_index']}\n"
        report += f"  {health['interpretation']}\n"
        
        if health['critical_flags']:
            report += "\n⚠️ BANDERAS CRÍTICAS:\n"
            for flag in health['critical_flags']:
                report += f"  {flag}\n"
        
        return report


# Testing
if __name__ == '__main__':
    analyzer = MultisensorAnalyzer()
    
    # Test comprehensive health
    health = analyzer.calculate_comprehensive_health_index(
        heart_rate=72,
        spo2=97,
        respiration_rate=16,
        temperature=37.1,
        systolic_bp=120,
        diastolic_bp=75
    )
    print("Health Index:", health)
    
    # Test correlation
    hr_trend = np.array([70, 72, 75, 73, 71, 72])
    rr_trend = np.array([14, 14, 16, 15, 14, 14])
    corr = analyzer.detect_cardiorespiratory_correlation(hr_trend, rr_trend)
    print("\nCorrelation:", corr)
