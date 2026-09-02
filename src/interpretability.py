"""
Interpretability Module for Explainable Cardiac AI

Translates machine learning predictions and extracted features
into clinically meaningful physiological interpretations.

This module enables medical students and clinicians to understand
not just WHAT the system predicts, but WHY it makes that prediction.

Clinical Reference Ranges
==========================
Derived from ESC/NASPE standards and clinical cardiology guidelines.
"""

import numpy as np


def interpret_features(features):
    """
    Generate physiological interpretations of HRV features.
    
    Analyzes each HRV metric and provides clinical context
    for abnormal findings.
    
    Parameters
    ----------
    features : dict
        Extracted HRV features with keys:
        'BPM', 'SDNN', 'RMSSD', 'LF_HF', 'Skewness', 'Kurtosis'
        
    Returns
    -------
    interpretations : list
        List of clinical interpretation strings
        
    Clinical Reasoning
    ==================
    1. BPM (Heart Rate):
       - Normal: 60-100 bpm at rest
       - > 100: Tachycardia (increased sympathetic activity)
       - < 60: Bradycardia (increased parasympathetic activity)
       
    2. SDNN (Overall HRV):
       - Reflects total autonomic nervous system activity
       - Low SDNN: Reduced overall variability, autonomic dysfunction
       - Associated with mortality risk post-MI
       
    3. RMSSD (Parasympathetic Activity):
       - Measures beat-to-beat variability
       - Low RMSSD: Reduced vagal tone, parasympathetic withdrawal
       - Indicates autonomic imbalance
       
    4. LF/HF Ratio (Sympathetic/Parasympathetic Balance):
       - LF: Sympathetic + parasympathetic
       - HF: Pure parasympathetic (vagal) activity
       - High ratio: Sympathetic dominance (stress, arrhythmia risk)
       
    5. Skewness & Kurtosis:
       - Measures distribution irregularity
       - Abnormal values suggest rhythm disturbances
    """
    
    interpretations = []
    
    # ============================================
    # HEART RATE ANALYSIS
    # ============================================
    
    bpm = features['BPM']
    
    if bpm > 100:
        interpretations.append(
            f"⚠️  TACHYCARDIA (HR {bpm:.0f} bpm): "
            f"Elevated resting heart rate indicates increased sympathetic activity. "
            f"Common in: anxiety, fever, arrhythmias, thyroid disorders, cardiac stress."
        )
    elif bpm < 60:
        interpretations.append(
            f"⚠️  BRADYCARDIA (HR {bpm:.0f} bpm): "
            f"Low resting heart rate may indicate increased parasympathetic tone. "
            f"Can be normal in athletes; abnormal in patients with conduction disease."
        )
    else:
        interpretations.append(
            f"✓ NORMAL HEART RATE ({bpm:.0f} bpm): "
            f"Resting heart rate is within normal sinus range (60-100 bpm)."
        )
    
    # ============================================
    # HRV AMPLITUDE (SDNN)
    # ============================================
    
    sdnn = features['SDNN']
    
    if sdnn < 0.05:
        interpretations.append(
            f"🔴 CRITICALLY LOW HRV (SDNN {sdnn:.4f}s): "
            f"Severely reduced heart rate variability indicates profound autonomic dysfunction. "
            f"Strong prognostic marker for sudden cardiac death risk. "
            f"Urgent evaluation recommended."
        )
    elif sdnn < 0.10:
        interpretations.append(
            f"🟠 LOW HRV (SDNN {sdnn:.4f}s): "
            f"Reduced overall heart rate variability may indicate: "
            f"autonomic neuropathy, post-MI remodeling, heart failure, or systemic stress. "
            f"Associated with increased cardiovascular risk."
        )
    else:
        interpretations.append(
            f"🟢 ADEQUATE HRV (SDNN {sdnn:.4f}s): "
            f"Good overall heart rate variability suggests healthy autonomic function."
        )
    
    # ============================================
    # PARASYMPATHETIC ACTIVITY (RMSSD)
    # ============================================
    
    rmssd = features['RMSSD']
    
    if rmssd < 0.03:
        interpretations.append(
            f"🔴 PARASYMPATHETIC WITHDRAWAL (RMSSD {rmssd:.4f}s): "
            f"Severely reduced parasympathetic (vagal) tone. "
            f"Indicates vagal denervation or autonomic neuropathy. "
            f"Loss of protective vagal brake on heart rate."
        )
    elif rmssd < 0.05:
        interpretations.append(
            f"🟠 REDUCED VAGAL TONE (RMSSD {rmssd:.4f}s): "
            f"Decreased parasympathetic activity indicates: "
            f"reduced cardioprotection, autonomic imbalance, or impending arrhythmia risk. "
            f"Important risk marker in cardiac patients."
        )
    else:
        interpretations.append(
            f"🟢 GOOD PARASYMPATHETIC TONE (RMSSD {rmssd:.4f}s): "
            f"Healthy vagal activity provides cardioprotection and beat-to-beat variability."
        )
    
    # ============================================
    # AUTONOMIC BALANCE (LF/HF RATIO)
    # ============================================
    
    lf_hf = features['LF_HF']
    
    if np.isnan(lf_hf):
        interpretations.append(
            "⚠️  INSUFFICIENT DATA: Cannot compute LF/HF ratio (inadequate frequency domain data)"
        )
    elif lf_hf > 3.0:
        interpretations.append(
            f"🔴 SYMPATHETIC DOMINANCE (LF/HF {lf_hf:.2f}): "
            f"Strongly elevated sympathetic-to-parasympathetic ratio indicates: "
            f"heightened 'fight-or-flight' response, mental/physical stress, or arrhythmia vulnerability. "
            f"Associated with reduced parasympathetic brake and increased sudden death risk."
        )
    elif lf_hf > 2.0:
        interpretations.append(
            f"🟠 ELEVATED SYMPATHETIC ACTIVITY (LF/HF {lf_hf:.2f}): "
            f"Moderately increased sympathetic dominance suggests: "
            f"stress, anxiety, inadequate recovery, or early autonomic dysfunction. "
            f"Monitor for progression to arrhythmia."
        )
    elif lf_hf < 1.0:
        interpretations.append(
            f"🟢 PARASYMPATHETIC DOMINANCE (LF/HF {lf_hf:.2f}): "
            f"Elevated parasympathetic tone (rest-and-digest state). "
            f"Indicates good vagal control and relaxation. Healthy pattern."
        )
    else:
        interpretations.append(
            f"🟢 BALANCED AUTONOMIC TONE (LF/HF {lf_hf:.2f}): "
            f"Well-balanced sympathetic-parasympathetic activity indicates normal autonomic function."
        )
    
    # ============================================
    # DISTRIBUTION REGULARITY (Skewness & Kurtosis)
    # ============================================
    
    skewness = features['Skewness']
    kurtosis = features['Kurtosis']
    
    if abs(skewness) > 1.0 or abs(kurtosis) > 2.0:
        interpretations.append(
            f"⚠️  IRREGULAR RR DISTRIBUTION (Skewness {skewness:.2f}, Kurtosis {kurtosis:.2f}): "
            f"Abnormal distribution shape indicates: ectopic beats, arrhythmias, or irregular rhythm patterns. "
            f"May suggest underlying conduction or rhythm disturbances."
        )
    
    return interpretations


DEFAULT_FEATURE_BASELINES = {
    'BPM': 72.0,
    'SDNN': 0.10,
    'RMSSD': 0.05,
    'LF_HF': 1.50,
    'Skewness': 0.0,
    'Kurtosis': 3.0,
}

FEATURE_RISK_DIRECTION = {
    'BPM': 1,
    'SDNN': -1,
    'RMSSD': -1,
    'LF_HF': 1,
    'Skewness': 1,
    'Kurtosis': 1,
}

FEATURE_LABELS = {
    'BPM': 'Frecuencia cardiaca',
    'SDNN': 'Variabilidad total (SDNN)',
    'RMSSD': 'Variabilidad parasimpática (RMSSD)',
    'LF_HF': 'Balance simpático/parasimpático (LF/HF)',
    'Skewness': 'Asimetría de RR',
    'Kurtosis': 'Curtosis de RR',
}

FEATURE_EXPLANATIONS = {
    'BPM': 'La frecuencia cardiaca alta suele incrementar el riesgo por mayor estrés autonómico.',
    'SDNN': 'SDNN bajo indica pérdida de variabilidad global del ritmo cardiaco.',
    'RMSSD': 'RMSSD bajo refleja menor actividad parasimpática y peor recuperación vagal.',
    'LF_HF': 'Relación LF/HF elevada sugiere dominancia simpática y mayor estrés fisiológico.',
    'Skewness': 'Skewness alto indica irregularidad en los intervalos RR, compatible con latidos anormales.',
    'Kurtosis': 'Kurtosis elevada sugiere distribución de intervalos RR con picos extremos, típico de arritmias.',
}


def compute_feature_importance(features, baseline=None):
    if baseline is None:
        baseline = DEFAULT_FEATURE_BASELINES

    contributions = {}
    for key, value in features.items():
        if key not in baseline or value is None:
            continue
        try:
            value_float = float(value)
        except Exception:
            continue
        base = float(baseline.get(key, 1.0))
        if np.isnan(value_float):
            continue
        diff = value_float - base
        weight = abs(diff) / max(abs(base), 0.01)
        contributions[key] = {
            'feature': key,
            'label': FEATURE_LABELS.get(key, key),
            'value': value_float,
            'baseline': base,
            'delta': diff,
            'weight': float(weight),
            'percent': 0.0,
            'direction': 'higher' if diff * FEATURE_RISK_DIRECTION.get(key, 1) > 0 else 'lower',
            'human': FEATURE_EXPLANATIONS.get(key, ''),
        }

    total_weight = sum(item['weight'] for item in contributions.values())
    if total_weight <= 0:
        total_weight = 1.0

    for item in contributions.values():
        item['percent'] = float(item['weight'] / total_weight * 100.0)

    ordered = sorted(contributions.values(), key=lambda x: x['percent'], reverse=True)
    return ordered


def shap_like_explanation(features, prediction):
    """`probability` se retiró del parámetro (2026-08-06) -- el único
    llamador real (`classify_ecg_signal`) lo alimentaba con un `confidence`
    que era una constante literal por rama de regla en
    `ECGAnalyzer.detect_clinical_pattern()`, no una probabilidad calculada;
    mostrarlo aquí como "X% de confianza" era el mismo dato falso filtrado
    por una segunda vía. Ver CHANGELOG.md."""
    importance = compute_feature_importance(features)
    if not importance:
        return []

    narrative = []
    narrative.append(
        'La clasificación de riesgo fue impulsada principalmente por:'
    )
    for item in importance[:4]:
        change = 'alto' if item['direction'] == 'higher' else 'bajo'
        narrative.append(
            f"- {item['label']} {change} ({item['percent']:.0f}%) — {item['human']}"
        )
    narrative.append(
        f"El modelo combina estos factores para explicar el resultado: {prediction}."
    )
    return narrative


def lime_like_explanation(features, prediction):
    importance = compute_feature_importance(features)
    if not importance:
        return []

    narrative = []
    narrative.append(
        'Explicación estilo LIME (vecindario local) para principiantes:'
    )
    for item in importance[:4]:
        narrative.append(
            f"- Si {item['label']} cambia un poco, el resultado se mueve {'hacia mayor riesgo' if item['direction'] == 'higher' else 'hacia menor riesgo'} "
            f"(contribución estimada {item['percent']:.0f}%)."
        )
    narrative.append(
        'Estas son las características que más cambian la predicción cuando se alteran ligeramente en el entorno local del ECG analizado.'
    )
    return narrative


def feature_importance_summary(features, prediction, probability):
    importance = compute_feature_importance(features)
    if not importance:
        return []

    summary = []
    summary.append(f"Predicción: {prediction} ({probability:.0%} de confianza)")
    summary.append('Características más importantes:')
    for item in importance[:4]:
        summary.append(
            f"{item['label']} = {item['value']:.2f} ({item['percent']:.0f}%)"
        )
    return summary


def generate_shap_lime_report(features, prediction):
    return {
        'shap': shap_like_explanation(features, prediction),
        'lime': lime_like_explanation(features, prediction),
        'importance': compute_feature_importance(features),
    }


def generate_clinical_report(
    features,
    prediction,
    probability,
    confidence,
    recording_duration=None,
    patient_info=None
):
    """
    Generate a comprehensive clinical interpretation report.
    
    Combines HRV analysis, prediction results, and physiological
    interpretation into a structured medical report format.
    
    Parameters
    ----------
    features : dict
        Extracted HRV features
    prediction : str
        Classification result from model
    probability : ndarray
        [P(normal), P(arrhythmia)]
    confidence : float
        Confidence of prediction (0-1)
    recording_duration : float, optional
        Duration of ECG recording in seconds
    patient_info : dict, optional
        Patient demographic information
        
    Returns
    -------
    report : str
        Formatted clinical report
    """
    
    interpretations = interpret_features(features)
    
    report = []
    report.append("\n" + "="*70)
    report.append("CARDIAC ARRHYTHMIA AI ANALYSIS REPORT")
    report.append("="*70)
    
    # Patient info
    if patient_info:
        report.append(f"\nPatient ID: {patient_info.get('id', 'N/A')}")
        report.append(f"Age: {patient_info.get('age', 'N/A')}")
        report.append(f"Sex: {patient_info.get('sex', 'N/A')}")
    
    if recording_duration:
        report.append(f"Recording Duration: {recording_duration:.1f} seconds")
    
    # ============================================
    # PREDICTION SECTION
    # ============================================
    
    report.append("\n" + "-"*70)
    report.append("CLASSIFICATION RESULT")
    report.append("-"*70)
    report.append(f"{prediction}")
    report.append(f"Confidence Level: {confidence:.1%}")
    report.append(f"Normal Rhythm Probability: {probability[0]:.1%}")
    report.append(f"Arrhythmia Probability: {probability[1]:.1%}")
    
    # ============================================
    # QUANTITATIVE FEATURES
    # ============================================
    
    report.append("\n" + "-"*70)
    report.append("QUANTITATIVE HRV FEATURES")
    report.append("-"*70)
    report.append(f"Heart Rate (BPM):           {features['BPM']:>10.1f}")
    report.append(f"SDNN (Overall HRV):         {features['SDNN']:>10.4f} s")
    report.append(f"RMSSD (Parasympathetic):    {features['RMSSD']:>10.4f} s")
    report.append(f"LF/HF Ratio (Aut. Balance): {features['LF_HF']:>10.2f}")
    report.append(f"Skewness (Distribution):    {features['Skewness']:>10.2f}")
    report.append(f"Kurtosis (Distribution):    {features['Kurtosis']:>10.2f}")
    
    # ============================================
    # CLINICAL INTERPRETATION
    # ============================================
    
    report.append("\n" + "-"*70)
    report.append("CLINICAL INTERPRETATION")
    report.append("-"*70)
    
    for interpretation in interpretations:
        report.append(f"\n{interpretation}")
    
    # ============================================
    # SUMMARY & RECOMMENDATIONS
    # ============================================
    
    report.append("\n" + "-"*70)
    report.append("SUMMARY & CLINICAL SIGNIFICANCE")
    report.append("-"*70)
    
    # Risk stratification
    if probability[1] > 0.7:
        report.append(
            "\n⚠️  HIGH ARRHYTHMIA RISK: Patient exhibits physiological markers "
            "suggestive of abnormal cardiac rhythm. Clinical correlation and further "
            "cardiac evaluation are strongly recommended."
        )
    elif probability[1] > 0.5:
        report.append(
            "\n⚠️  INTERMEDIATE RISK: Some markers suggest possible rhythm abnormality. "
            "Continued monitoring and clinical assessment recommended."
        )
    else:
        report.append(
            "\n✓ LOW RISK: Physiological parameters are consistent with normal sinus rhythm. "
            "No urgent indicators of arrhythmia detected."
        )
    
    report.append("\n" + "="*70)
    report.append("DISCLAIMER: This AI analysis is for educational and clinical support purposes.")
    report.append("Final diagnosis and clinical decisions must be made by qualified clinicians.")
    report.append("="*70 + "\n")
    
    return "\n".join(report)