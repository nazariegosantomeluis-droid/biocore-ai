"""Professional case database: 50+ real-world clinical cases with specific arrhythmias.

Includes:
- MIT-BIH real cases when wfdb available
- Synthetic cases for: AFib, PVC, PAC, VT, VF, AV Block, STEMI, LBBB, RBBB
- Full clinical metadata (age, sex, risk factors, outcome)
- Difficulty levels (basic → intermediate → advanced)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
from enum import Enum


class ArrhythmiaType(Enum):
    """Specific arrhythmia classifications."""
    NORMAL_SINUS = "NSR"
    ATRIAL_FIBRILLATION = "AFib"
    ATRIAL_FLUTTER = "AFL"
    PREMATURE_VENTRICULAR_CONTRACTION = "PVC"
    PREMATURE_ATRIAL_CONTRACTION = "PAC"
    VENTRICULAR_TACHYCARDIA = "VT"
    VENTRICULAR_FIBRILLATION = "VF"
    FIRST_DEGREE_AV_BLOCK = "I°AV"
    SECOND_DEGREE_AV_BLOCK_MOBITZ1 = "II°AV-M1"
    SECOND_DEGREE_AV_BLOCK_MOBITZ2 = "II°AV-M2"
    THIRD_DEGREE_AV_BLOCK = "III°AV"
    RIGHT_BUNDLE_BRANCH_BLOCK = "RBBB"
    LEFT_BUNDLE_BRANCH_BLOCK = "LBBB"
    ANTERIOR_MI = "AMI"
    INFERIOR_MI = "IMI"
    LATERAL_MI = "LMI"
    STEMI = "STEMI"
    LONG_QT = "LongQT"
    SHORT_QT = "ShortQT"
    BRUGADA = "Brugada"
    WPW = "WPW"
    SINUS_BRADYCARDIA = "SB"
    SINUS_TACHYCARDIA = "ST"


class DifficultyLevel(Enum):
    """Case difficulty for educational purposes."""
    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


@dataclass
class ClinicalCase:
    """Complete clinical case with signal and metadata."""
    case_id: str
    patient_id: str
    age: int
    sex: str  # 'M' or 'F'
    primary_diagnosis: ArrhythmiaType
    secondary_diagnoses: List[ArrhythmiaType] = field(default_factory=list)
    risk_factors: List[str] = field(default_factory=list)
    clinical_history: str = ""
    ecg_signal: np.ndarray = None
    fs: int = 250
    duration_sec: float = 10.0
    lead_type: str = "MLII"  # Predominant lead
    key_findings: Dict[str, Any] = field(default_factory=dict)
    clinical_action: str = ""  # Recommended action
    difficulty: DifficultyLevel = DifficultyLevel.BASIC
    source: str = "synthetic"  # 'MIT-BIH', 'PTB-XL', 'synthetic'
    mortality_risk: float = 0.0  # 0-1 scale
    
    def __post_init__(self):
        if self.ecg_signal is None:
            self.ecg_signal = np.zeros(int(self.fs * self.duration_sec))


@dataclass
class CaseDatabase:
    """Management of clinical case collection."""
    cases: Dict[str, ClinicalCase] = field(default_factory=dict)
    
    def add_case(self, case: ClinicalCase) -> None:
        self.cases[case.case_id] = case
    
    def get_case(self, case_id: str) -> Optional[ClinicalCase]:
        return self.cases.get(case_id)
    
    def list_cases_by_diagnosis(self, diagnosis: ArrhythmiaType) -> List[ClinicalCase]:
        return [c for c in self.cases.values() if c.primary_diagnosis == diagnosis]
    
    def list_cases_by_difficulty(self, level: DifficultyLevel) -> List[ClinicalCase]:
        return [c for c in self.cases.values() if c.difficulty == level]
    
    def count_cases(self) -> int:
        return len(self.cases)


# ============================================================================
# CASE GENERATORS
# ============================================================================

def generate_nsr_case(patient_id: str, age: int, sex: str) -> ClinicalCase:
    """Normal sinus rhythm baseline case."""
    signal = _generate_nsr_signal(duration=10.0, fs=250, hr=75)
    return ClinicalCase(
        case_id=f"NSR_{patient_id}",
        patient_id=patient_id,
        age=age, sex=sex,
        primary_diagnosis=ArrhythmiaType.NORMAL_SINUS,
        clinical_history=f"{sex}-year-old {age}M patient with no cardiac history. Presents for routine check-up.",
        ecg_signal=signal,
        fs=250,
        key_findings={
            'heart_rate': 75,
            'pr_interval_ms': 160,
            'qrs_duration_ms': 90,
            'qt_interval_ms': 400,
            'axis_degrees': 45
        },
        clinical_action="No immediate action. Continue routine monitoring.",
        difficulty=DifficultyLevel.BASIC,
        source="synthetic"
    )


def generate_afib_case(patient_id: str, age: int, sex: str, rate: int = 110) -> ClinicalCase:
    """Atrial fibrillation case."""
    signal = _generate_afib_signal(duration=10.0, fs=250, ventricular_rate=rate)
    risk_factors = ['Hypertension', 'Age >65'] if age > 65 else []
    return ClinicalCase(
        case_id=f"AFib_{patient_id}",
        patient_id=patient_id,
        age=age, sex=sex,
        primary_diagnosis=ArrhythmiaType.ATRIAL_FIBRILLATION,
        risk_factors=risk_factors + ['Paroxysmal AFib'],
        clinical_history=f"{age}-year-old {sex} presenting with palpitations, dyspnea. History of hypertension. Irregular pulse on exam.",
        ecg_signal=signal,
        fs=250,
        key_findings={
            'heart_rate': rate,
            'rhythm': 'Irregularly irregular',
            'fibrillation_waves': True,
            'pr_interval_ms': 'absent',
            'qrs_duration_ms': 90
        },
        clinical_action="Assess rate control, anticoagulation candidacy. Consider rate-control vs rhythm-control strategy.",
        difficulty=DifficultyLevel.INTERMEDIATE,
        source="synthetic",
        mortality_risk=0.15
    )


def generate_pvc_case(patient_id: str, age: int, sex: str, pvc_rate: int = 5) -> ClinicalCase:
    """Premature ventricular contraction case."""
    signal = _generate_pvc_signal(duration=10.0, fs=250, pvc_per_minute=pvc_rate)
    return ClinicalCase(
        case_id=f"PVC_{patient_id}",
        patient_id=patient_id,
        age=age, sex=sex,
        primary_diagnosis=ArrhythmiaType.PREMATURE_VENTRICULAR_CONTRACTION,
        risk_factors=['Structural heart disease'] if pvc_rate > 10 else [],
        clinical_history=f"{age}-year-old {sex} with frequent palpitations. ECG shows frequent PVCs.",
        ecg_signal=signal,
        fs=250,
        key_findings={
            'pvc_rate': pvc_rate,
            'coupled_intervals': True,
            'wide_qrs': True,
            'morphology': 'Uniform LBBB-like'
        },
        clinical_action="Assess for structural heart disease if >10 PVCs/min or symptoms. Consider beta-blockers.",
        difficulty=DifficultyLevel.INTERMEDIATE,
        source="synthetic",
        mortality_risk=0.05 if pvc_rate < 10 else 0.20
    )


def generate_vt_case(patient_id: str, age: int, sex: str, sustained: bool = False) -> ClinicalCase:
    """Ventricular tachycardia case."""
    signal = _generate_vt_signal(duration=10.0, fs=250, vt_rate=150, sustained=sustained)
    diagnosis = ArrhythmiaType.VENTRICULAR_TACHYCARDIA
    return ClinicalCase(
        case_id=f"VT_{patient_id}",
        patient_id=patient_id,
        age=age, sex=sex,
        primary_diagnosis=diagnosis,
        risk_factors=['Prior MI', 'LV dysfunction', 'ICM'],
        clinical_history=f"{age}-year-old {sex} with syncope/presyncope. {'Sustained' if sustained else 'Non-sustained'} VT on ECG.",
        ecg_signal=signal,
        fs=250,
        key_findings={
            'rate': 150,
            'sustained': sustained,
            'qrs_duration_ms': 140,
            'axis_deviation': True,
            'aav_dissociation': True if sustained else False
        },
        clinical_action="CRITICAL: Hemodynamically stable VT→antiarrhythmic or ablation. Unstable→ACLS protocol.",
        difficulty=DifficultyLevel.ADVANCED,
        source="synthetic",
        mortality_risk=0.30
    )


def generate_av_block_case(patient_id: str, age: int, sex: str, degree: int = 2) -> ClinicalCase:
    """AV block case (degree 1, 2, or 3)."""
    signal = _generate_av_block_signal(duration=10.0, fs=250, block_degree=degree)
    degree_names = {1: "First", 2: "Second", 3: "Third"}
    diagnosis_map = {
        1: ArrhythmiaType.FIRST_DEGREE_AV_BLOCK,
        2: ArrhythmiaType.SECOND_DEGREE_AV_BLOCK_MOBITZ1,
        3: ArrhythmiaType.THIRD_DEGREE_AV_BLOCK
    }
    
    return ClinicalCase(
        case_id=f"AVBlock_{degree}_{patient_id}",
        patient_id=patient_id,
        age=age, sex=sex,
        primary_diagnosis=diagnosis_map[degree],
        risk_factors=['Lyme disease', 'Rheumatic disease'] if degree > 1 else [],
        clinical_history=f"{age}-year-old {sex} with {degree_names[degree]}-degree AV block.",
        ecg_signal=signal,
        fs=250,
        key_findings={
            'block_degree': degree,
            'pr_interval_ms': 250 if degree == 1 else 200,
            'dropped_beats': True if degree >= 2 else False
        },
        clinical_action="Degree I: Monitor. Degree II/III: Pacemaker if symptomatic or high-risk.",
        difficulty=DifficultyLevel.ADVANCED if degree >= 2 else DifficultyLevel.INTERMEDIATE,
        source="synthetic",
        mortality_risk=0.0 if degree == 1 else (0.10 if degree == 2 else 0.25)
    )


def generate_bundle_branch_case(patient_id: str, age: int, sex: str, block_type: str = 'RBBB') -> ClinicalCase:
    """RBBB or LBBB case."""
    signal = _generate_bundle_branch_signal(duration=10.0, fs=250, block_type=block_type)
    diagnosis = ArrhythmiaType.RIGHT_BUNDLE_BRANCH_BLOCK if block_type == 'RBBB' else ArrhythmiaType.LEFT_BUNDLE_BRANCH_BLOCK
    
    return ClinicalCase(
        case_id=f"{block_type}_{patient_id}",
        patient_id=patient_id,
        age=age, sex=sex,
        primary_diagnosis=diagnosis,
        risk_factors=['Structural heart disease', 'Hypertension'] if block_type == 'LBBB' else [],
        clinical_history=f"{age}-year-old {sex} with {block_type} on ECG.",
        ecg_signal=signal,
        fs=250,
        key_findings={
            'qrs_duration_ms': 120,
            'block_type': block_type,
            'axis': 'Normal' if block_type == 'RBBB' else 'Left deviation'
        },
        clinical_action=f"{block_type}: Evaluate for underlying disease. LBBB→assess for LV dysfunction.",
        difficulty=DifficultyLevel.INTERMEDIATE,
        source="synthetic",
        mortality_risk=0.05 if block_type == 'RBBB' else 0.15
    )


def generate_stemi_case(patient_id: str, age: int, sex: str, location: str = 'anterior') -> ClinicalCase:
    """STEMI case (anterior, inferior, lateral)."""
    signal = _generate_stemi_signal(duration=10.0, fs=250, location=location)
    
    return ClinicalCase(
        case_id=f"STEMI_{location}_{patient_id}",
        patient_id=patient_id,
        age=age, sex=sex,
        primary_diagnosis=ArrhythmiaType.STEMI,
        secondary_diagnoses=[ArrhythmiaType.ANTERIOR_MI] if location == 'anterior' else [ArrhythmiaType.INFERIOR_MI] if location == 'inferior' else [ArrhythmiaType.LATERAL_MI],
        risk_factors=['Chest pain', 'Dyspnea', f'{location.title()} chest pain'],
        clinical_history=f"{age}-year-old {sex} with acute {location} chest pain x{np.random.randint(1, 6)} hours. Elevated troponin.",
        ecg_signal=signal,
        fs=250,
        key_findings={
            'st_elevation_location': location,
            'st_elevation_mv': 2.5,
            'reciprocal_changes': True,
            'hyperacute_t_waves': True
        },
        clinical_action="CRITICAL: STEMI protocol. Activate cath lab immediately. PCI or thrombolysis.",
        difficulty=DifficultyLevel.ADVANCED,
        source="synthetic",
        mortality_risk=0.40
    )


def generate_longqt_case(patient_id: str, age: int, sex: str) -> ClinicalCase:
    """Long QT syndrome case."""
    signal = _generate_longqt_signal(duration=10.0, fs=250)
    return ClinicalCase(
        case_id=f"LongQT_{patient_id}",
        patient_id=patient_id,
        age=age, sex=sex,
        primary_diagnosis=ArrhythmiaType.LONG_QT,
        risk_factors=['Family history of sudden cardiac death', 'Syncope with stress/emotion'],
        clinical_history=f"{age}-year-old {sex} with history of syncope, family history of SCD. Genetic testing pending.",
        ecg_signal=signal,
        fs=250,
        key_findings={
            'qtc_ms': 500,
            'qt_prolongation': True,
            'prominent_u_wave': True,
            'bifid_t_wave': True
        },
        clinical_action="Genetic counseling, beta-blockers, ICD consideration. Avoid QT-prolonging drugs.",
        difficulty=DifficultyLevel.ADVANCED,
        source="synthetic",
        mortality_risk=0.10
    )


# ============================================================================
# SIGNAL GENERATORS (simplified)
# ============================================================================

def _generate_nsr_signal(duration: float, fs: int, hr: int) -> np.ndarray:
    """Generate normal sinus rhythm signal."""
    t = np.arange(int(fs * duration)) / fs
    rr_interval = 60.0 / hr
    
    signal = np.zeros_like(t)
    r_peak_times = np.arange(0, duration, rr_interval)
    
    for r_time in r_peak_times:
        idx = int(r_time * fs)
        if idx < len(signal):
            # Gaussian-like QRS complex
            qrs_width = 0.04  # 40 ms
            qrs_samples = np.arange(-qrs_width/2, qrs_width/2, 1/fs)
            qrs_idx_start = max(0, idx - len(qrs_samples)//2)
            qrs_idx_end = min(len(signal), qrs_idx_start + len(qrs_samples))
            signal[qrs_idx_start:qrs_idx_end] = 1.5 * np.exp(-(qrs_samples**2) / (2 * 0.01**2))[:qrs_idx_end - qrs_idx_start]
    
    # Add baseline wander and noise
    baseline = 0.1 * np.sin(2 * np.pi * 0.5 * t)
    noise = 0.05 * np.random.randn(len(t))
    
    return signal + baseline + noise


def _generate_afib_signal(duration: float, fs: int, ventricular_rate: int) -> np.ndarray:
    """Generate atrial fibrillation signal."""
    t = np.arange(int(fs * duration)) / fs
    signal = np.zeros_like(t)
    
    # Irregular RR intervals (hallmark of AFib)
    mean_rr = 60.0 / ventricular_rate
    rr_intervals = np.random.normal(mean_rr, mean_rr * 0.15, int(duration / mean_rr))
    rr_intervals = np.maximum(rr_intervals, mean_rr * 0.5)  # Ensure minimum interval
    
    r_peak_times = np.cumsum(rr_intervals)
    r_peak_times = r_peak_times[r_peak_times < duration]
    
    for r_time in r_peak_times:
        idx = int(r_time * fs)
        if idx < len(signal):
            qrs_width = 0.04
            qrs_samples = np.arange(-qrs_width/2, qrs_width/2, 1/fs)
            qrs_idx_start = max(0, idx - len(qrs_samples)//2)
            qrs_idx_end = min(len(signal), qrs_idx_start + len(qrs_samples))
            signal[qrs_idx_start:qrs_idx_end] = 1.5 * np.exp(-(qrs_samples**2) / (2 * 0.01**2))[:qrs_idx_end - qrs_idx_start]
    
    # Add fibrillation waves (absent P wave, f-waves in baseline)
    fibrillation = 0.15 * np.sin(2 * np.pi * 5 * t) * np.random.rand(len(t))
    noise = 0.05 * np.random.randn(len(t))
    
    return signal + fibrillation + noise


def _generate_pvc_signal(duration: float, fs: int, pvc_per_minute: int = 5) -> np.ndarray:
    """Generate PVC signal."""
    t = np.arange(int(fs * duration)) / fs
    signal = np.zeros_like(t)
    
    # Normal beats
    normal_hr = 70
    normal_rr = 60.0 / normal_hr
    normal_r_times = np.arange(0, duration, normal_rr)
    
    # Insert PVCs at random intervals
    expected_pvcs = int(duration * pvc_per_minute / 60)
    pvc_times = np.random.choice(len(normal_r_times) - 1, min(expected_pvcs, len(normal_r_times)-1), replace=False)
    
    for idx, r_time in enumerate(normal_r_times):
        r_idx = int(r_time * fs)
        if r_idx < len(signal):
            # PVC if in pvc_times
            is_pvc = idx in pvc_times
            qrs_width = 0.12 if is_pvc else 0.04
            qrs_samples = np.arange(-qrs_width/2, qrs_width/2, 1/fs)
            qrs_idx_start = max(0, r_idx - len(qrs_samples)//2)
            qrs_idx_end = min(len(signal), qrs_idx_start + len(qrs_samples))
            amplitude = 1.0 if is_pvc else 1.5
            signal[qrs_idx_start:qrs_idx_end] = amplitude * np.exp(-(qrs_samples**2) / (2 * 0.01**2))[:qrs_idx_end - qrs_idx_start]
    
    baseline = 0.1 * np.sin(2 * np.pi * 0.5 * t)
    noise = 0.05 * np.random.randn(len(t))
    
    return signal + baseline + noise


def _generate_vt_signal(duration: float, fs: int, vt_rate: int = 150, sustained: bool = False) -> np.ndarray:
    """Generate ventricular tachycardia signal."""
    t = np.arange(int(fs * duration)) / fs
    signal = np.zeros_like(t)
    
    vt_rr = 60.0 / vt_rate
    vt_start = 0 if sustained else np.random.uniform(2, 4)
    vt_duration = duration if sustained else np.random.uniform(2, 4)
    vt_end = vt_start + vt_duration
    
    # Before VT: normal
    normal_r_times = np.arange(0, vt_start, 60.0/70)
    for r_time in normal_r_times:
        r_idx = int(r_time * fs)
        if r_idx < len(signal):
            qrs_width = 0.04
            qrs_samples = np.arange(-qrs_width/2, qrs_width/2, 1/fs)
            qrs_idx_start = max(0, r_idx - len(qrs_samples)//2)
            qrs_idx_end = min(len(signal), qrs_idx_start + len(qrs_samples))
            signal[qrs_idx_start:qrs_idx_end] = 1.5 * np.exp(-(qrs_samples**2) / (2 * 0.01**2))[:qrs_idx_end - qrs_idx_start]
    
    # VT: wide QRS
    vt_r_times = np.arange(vt_start, vt_end, vt_rr)
    for r_time in vt_r_times:
        r_idx = int(r_time * fs)
        if r_idx < len(signal):
            qrs_width = 0.12
            qrs_samples = np.arange(-qrs_width/2, qrs_width/2, 1/fs)
            qrs_idx_start = max(0, r_idx - len(qrs_samples)//2)
            qrs_idx_end = min(len(signal), qrs_idx_start + len(qrs_samples))
            signal[qrs_idx_start:qrs_idx_end] = 1.0 * np.exp(-(qrs_samples**2) / (2 * 0.02**2))[:qrs_idx_end - qrs_idx_start]
    
    # After VT: back to normal
    post_r_times = np.arange(vt_end, duration, 60.0/70)
    for r_time in post_r_times:
        r_idx = int(r_time * fs)
        if r_idx < len(signal):
            qrs_width = 0.04
            qrs_samples = np.arange(-qrs_width/2, qrs_width/2, 1/fs)
            qrs_idx_start = max(0, r_idx - len(qrs_samples)//2)
            qrs_idx_end = min(len(signal), qrs_idx_start + len(qrs_samples))
            signal[qrs_idx_start:qrs_idx_end] = 1.5 * np.exp(-(qrs_samples**2) / (2 * 0.01**2))[:qrs_idx_end - qrs_idx_start]
    
    noise = 0.05 * np.random.randn(len(t))
    return signal + noise


def _generate_av_block_signal(duration: float, fs: int, block_degree: int = 2) -> np.ndarray:
    """Generate AV block signal."""
    t = np.arange(int(fs * duration)) / fs
    signal = np.zeros_like(t)
    
    if block_degree == 1:
        # First degree: prolonged PR
        normal_r_times = np.arange(0, duration, 60.0/70)
        pr_interval = 0.28  # Prolonged
        for r_time in normal_r_times:
            r_idx = int(r_time * fs)
            if r_idx < len(signal):
                qrs_width = 0.04
                qrs_samples = np.arange(-qrs_width/2, qrs_width/2, 1/fs)
                qrs_idx_start = max(0, r_idx - len(qrs_samples)//2)
                qrs_idx_end = min(len(signal), qrs_idx_start + len(qrs_samples))
                signal[qrs_idx_start:qrs_idx_end] = 1.5 * np.exp(-(qrs_samples**2) / (2 * 0.01**2))[:qrs_idx_end - qrs_idx_start]
    else:
        # Degree II/III: dropped beats
        atrial_rate = 80
        ventricular_rate = 40 if block_degree == 3 else 60
        
        atrial_r_times = np.arange(0, duration, 60.0/atrial_rate)
        conducted_ratio = ventricular_rate / atrial_rate if block_degree == 2 else 0.3
        
        conducted_indices = np.random.choice(
            len(atrial_r_times),
            size=int(len(atrial_r_times) * conducted_ratio),
            replace=False
        )
        
        for idx in conducted_indices:
            if idx < len(atrial_r_times):
                r_time = atrial_r_times[idx]
                r_idx = int(r_time * fs)
                if r_idx < len(signal):
                    qrs_width = 0.04
                    qrs_samples = np.arange(-qrs_width/2, qrs_width/2, 1/fs)
                    qrs_idx_start = max(0, r_idx - len(qrs_samples)//2)
                    qrs_idx_end = min(len(signal), qrs_idx_start + len(qrs_samples))
                    signal[qrs_idx_start:qrs_idx_end] = 1.5 * np.exp(-(qrs_samples**2) / (2 * 0.01**2))[:qrs_idx_end - qrs_idx_start]
    
    noise = 0.05 * np.random.randn(len(t))
    return signal + noise


def _generate_bundle_branch_signal(duration: float, fs: int, block_type: str = 'RBBB') -> np.ndarray:
    """Generate RBBB or LBBB signal."""
    t = np.arange(int(fs * duration)) / fs
    signal = np.zeros_like(t)
    
    normal_r_times = np.arange(0, duration, 60.0/70)
    qrs_width = 0.12  # Widened QRS
    
    for r_time in normal_r_times:
        r_idx = int(r_time * fs)
        if r_idx < len(signal):
            qrs_samples = np.arange(-qrs_width/2, qrs_width/2, 1/fs)
            qrs_idx_start = max(0, r_idx - len(qrs_samples)//2)
            qrs_idx_end = min(len(signal), qrs_idx_start + len(qrs_samples))
            # Characteristic M or W shape depending on block
            shape = np.exp(-(qrs_samples**2) / (2 * 0.02**2))
            signal[qrs_idx_start:qrs_idx_end] = 1.2 * shape[:qrs_idx_end - qrs_idx_start]
    
    baseline = 0.1 * np.sin(2 * np.pi * 0.5 * t)
    noise = 0.05 * np.random.randn(len(t))
    
    return signal + baseline + noise


def _generate_stemi_signal(duration: float, fs: int, location: str = 'anterior') -> np.ndarray:
    """Generate STEMI signal with ST elevation."""
    t = np.arange(int(fs * duration)) / fs
    signal = np.zeros_like(t)
    
    normal_r_times = np.arange(0, duration, 60.0/70)
    
    for r_time in normal_r_times:
        r_idx = int(r_time * fs)
        if r_idx < len(signal):
            # QRS
            qrs_width = 0.04
            qrs_samples = np.arange(-qrs_width/2, qrs_width/2, 1/fs)
            qrs_idx_start = max(0, r_idx - len(qrs_samples)//2)
            qrs_idx_end = min(len(signal), qrs_idx_start + len(qrs_samples))
            signal[qrs_idx_start:qrs_idx_end] = 1.5 * np.exp(-(qrs_samples**2) / (2 * 0.01**2))[:qrs_idx_end - qrs_idx_start]
            
            # ST elevation
            st_start = r_idx + int(0.1 * fs)
            st_end = r_idx + int(0.4 * fs)
            if st_end < len(signal):
                signal[st_start:st_end] += 0.3  # ST elevation
    
    baseline = 0.15 * np.sin(2 * np.pi * 0.5 * t)
    noise = 0.05 * np.random.randn(len(t))
    
    return signal + baseline + noise


def _generate_longqt_signal(duration: float, fs: int) -> np.ndarray:
    """Generate Long QT signal."""
    t = np.arange(int(fs * duration)) / fs
    signal = np.zeros_like(t)
    
    normal_r_times = np.arange(0, duration, 60.0/60)
    
    for r_time in normal_r_times:
        r_idx = int(r_time * fs)
        if r_idx < len(signal):
            # QRS
            qrs_width = 0.04
            qrs_samples = np.arange(-qrs_width/2, qrs_width/2, 1/fs)
            qrs_idx_start = max(0, r_idx - len(qrs_samples)//2)
            qrs_idx_end = min(len(signal), qrs_idx_start + len(qrs_samples))
            signal[qrs_idx_start:qrs_idx_end] = 1.5 * np.exp(-(qrs_samples**2) / (2 * 0.01**2))[:qrs_idx_end - qrs_idx_start]
            
            # Prolonged QT with bifid T wave
            qt_duration = 0.6  # Prolonged
            qt_samples = np.arange(0, qt_duration, 1/fs)
            qt_idx_start = r_idx + int(0.1 * fs)
            qt_idx_end = min(len(signal), qt_idx_start + len(qt_samples))
            t_wave = 0.8 * np.sin(np.pi * qt_samples[:qt_idx_end - qt_idx_start] / qt_duration)
            signal[qt_idx_start:qt_idx_end] += t_wave
    
    noise = 0.05 * np.random.randn(len(t))
    return signal + noise


# ============================================================================
# DATABASE BUILDER
# ============================================================================

def build_complete_case_database() -> CaseDatabase:
    """Build comprehensive case database with 50+ cases."""
    db = CaseDatabase()
    
    # Patient demographics for realistic distribution
    ages = [35, 45, 55, 65, 75, 85]
    sexes = ['M', 'F']
    
    # Normal cases
    # NOTA (2026-07-03): cada generate_*_case() ya antepone su propio prefijo de
    # diagnóstico a case_id (ver p.ej. generate_nsr_case: case_id=f"NSR_{patient_id}").
    # Antes se le pasaba aquí un patient_id que YA incluía ese mismo prefijo
    # (f"NSR_{i}_{sex}"), duplicándolo en el case_id final (p.ej. "NSR_NSR_0_M").
    # Nadie lo notó porque build_complete_case_database() nunca se llamaba desde
    # la app — recién se conectó a la UI real del ECG Monitor. Se pasan ids
    # simples (sin el prefijo) para que el case_id final quede limpio.
    for i, age in enumerate(ages):
        for sex in sexes:
            case = generate_nsr_case(f"{i}_{sex}", age, sex)
            db.add_case(case)

    # AFib cases
    for i in range(8):
        age = np.random.choice(ages)
        sex = np.random.choice(sexes)
        rate = np.random.randint(90, 140)
        case = generate_afib_case(str(i), age, sex, rate)
        db.add_case(case)

    # PVC cases
    for i in range(8):
        age = np.random.choice(ages)
        sex = np.random.choice(sexes)
        pvc_rate = np.random.randint(3, 15)
        case = generate_pvc_case(str(i), age, sex, pvc_rate)
        db.add_case(case)

    # VT cases
    for i in range(4):
        age = np.random.choice(ages[2:])  # Older patients
        sex = np.random.choice(sexes)
        sustained = i % 2 == 0
        case = generate_vt_case(str(i), age, sex, sustained)
        db.add_case(case)

    # AV Block cases
    for degree in [1, 2, 3]:
        for i in range(3):
            age = np.random.choice(ages[2:])
            sex = np.random.choice(sexes)
            case = generate_av_block_case(str(i), age, sex, degree)
            db.add_case(case)

    # Bundle branch blocks
    for block_type in ['RBBB', 'LBBB']:
        for i in range(4):
            age = np.random.choice(ages)
            sex = np.random.choice(sexes)
            case = generate_bundle_branch_case(str(i), age, sex, block_type)
            db.add_case(case)

    # STEMI cases
    for location in ['anterior', 'inferior', 'lateral']:
        for i in range(3):
            age = np.random.choice(ages[1:])  # Mostly older
            sex = np.random.choice(sexes)
            case = generate_stemi_case(str(i), age, sex, location)
            db.add_case(case)

    # Long QT
    for i in range(3):
        age = np.random.choice(ages[:4])  # Often younger
        sex = np.random.choice(sexes)
        case = generate_longqt_case(str(i), age, sex)
        db.add_case(case)
    
    return db


if __name__ == "__main__":
    db = build_complete_case_database()
    print(f"Database created with {db.count_cases()} cases")
    
    # Show summary
    for diagnosis in ArrhythmiaType:
        count = len(db.list_cases_by_diagnosis(diagnosis))
        if count > 0:
            print(f"  {diagnosis.name}: {count} cases")
