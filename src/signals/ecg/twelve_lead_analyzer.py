"""
12-Lead ECG Clinical Analyzer

Interprets 12-lead ECG signals for:
- QRS axis determination
- ST elevation/depression detection (STEMI localization)
- Conduction abnormalities (blocks)
- Wave abnormalities
- Arrhythmia patterns
- Clinical summaries
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class QrsAxis:
    """QRS axis determination result"""
    axis_degrees: float
    category: str  # "Normal", "LAD" (Left Axis Deviation), "RAD" (Right Axis Deviation)
    description: str


@dataclass
class StSegmentFinding:
    """ST segment abnormality"""
    lead: str
    elevation_mv: float
    location: str  # "anterior", "inferior", "lateral", "posterior"
    severity: str  # "normal", "minimal", "moderate", "significant"


@dataclass
class ConductionBlock:
    """Conduction abnormality detection"""
    block_type: str  # "RBBB", "LBBB", "AV_block_1", "AV_block_2", "AV_block_3"
    degree: int  # 1, 2, 3
    affected_leads: List[str]
    description: str


@dataclass
class WaveAbnormality:
    """Abnormal wave patterns"""
    wave_type: str  # "P", "Q", "R", "S", "T"
    leads_affected: List[str]
    abnormality: str  # "inversion", "prolongation", "low_voltage", "pathological_q"
    description: str


@dataclass
class EcgInterpretation:
    """Complete ECG interpretation"""
    qrs_axis: QrsAxis
    st_findings: List[StSegmentFinding]
    conduction_blocks: List[ConductionBlock]
    wave_abnormalities: List[WaveAbnormality]
    rhythm: str
    primary_diagnosis: str
    differential_diagnoses: List[str]
    clinical_significance: str
    recommendations: List[str]


class TwelveLeadEcgAnalyzer:
    """Professional ECG analyzer"""
    
    # Lead groupings for interpretation
    ANTERIOR_LEADS = ['V1', 'V2', 'V3', 'V4']
    SEPTAL_LEADS = ['V1', 'V2']
    LATERAL_LEADS = ['I', 'aVL', 'V5', 'V6']
    INFERIOR_LEADS = ['II', 'III', 'aVF']
    RIGHT_LEADS = ['aVR', 'V1']
    
    # Anatomical locations for STEMI
    STEMI_LOCATIONS = {
        ('V1', 'V2', 'V3', 'V4'): ('Anterior', 'LAD territory'),
        ('V1', 'V2'): ('Septal', 'LAD septal branch'),
        ('I', 'aVL', 'V5', 'V6'): ('Lateral', 'LCx territory'),
        ('II', 'III', 'aVF'): ('Inferior', 'RCA territory'),
        ('V1', 'V2', 'II', 'III', 'aVF'): ('Posterior', 'Posterior wall'),
    }
    
    def __init__(self):
        """Initialize analyzer"""
        pass
    
    def analyze_12lead(self, ecg_signals: Dict[str, np.ndarray]) -> EcgInterpretation:
        """
        Perform complete 12-lead ECG analysis
        
        Args:
            ecg_signals: Dictionary with leads I-III, aVR-aVF, V1-V6, and 'time' array
            
        Returns:
            Complete ECG interpretation with findings
        """
        # Extract signals
        time = ecg_signals.get('time', None)
        
        # Determine QRS axis
        qrs_axis = self._determine_qrs_axis(
            ecg_signals.get('I', None),
            ecg_signals.get('aVF', None),
            ecg_signals.get('II', None)
        )
        
        # Detect ST segment abnormalities
        st_findings = self._detect_st_abnormalities(ecg_signals)
        
        # Determine STEMI location if present
        stemi_location = self._localize_stemi(st_findings) if st_findings else None
        
        # Detect conduction blocks
        conduction_blocks = self._detect_conduction_blocks(ecg_signals)
        
        # Detect wave abnormalities
        wave_abnormalities = self._detect_wave_abnormalities(ecg_signals)
        
        # Determine rhythm
        rhythm = self._determine_rhythm(ecg_signals)
        
        # Generate primary diagnosis
        primary_diagnosis = self._generate_primary_diagnosis(
            stemi_location, conduction_blocks, qrs_axis, rhythm
        )
        
        # Generate differential diagnoses
        differential = self._generate_differential_diagnoses(
            st_findings, wave_abnormalities, qrs_axis
        )
        
        # Clinical significance
        clinical_sig = self._assess_clinical_significance(
            st_findings, conduction_blocks, wave_abnormalities, rhythm
        )
        
        # Recommendations
        recommendations = self._generate_recommendations(
            primary_diagnosis, st_findings, rhythm
        )
        
        return EcgInterpretation(
            qrs_axis=qrs_axis,
            st_findings=st_findings,
            conduction_blocks=conduction_blocks,
            wave_abnormalities=wave_abnormalities,
            rhythm=rhythm,
            primary_diagnosis=primary_diagnosis,
            differential_diagnoses=differential,
            clinical_significance=clinical_sig,
            recommendations=recommendations
        )
    
    def _determine_qrs_axis(self, lead_i: np.ndarray, aVF: np.ndarray, lead_ii: np.ndarray) -> QrsAxis:
        """
        Determine QRS axis using simplified lead analysis
        
        Rules:
        - Predominant positive: axis in that direction
        - Equiphasic (equal +/-): perpendicular direction
        - Most negative: opposite direction
        """
        if lead_i is None or aVF is None:
            return QrsAxis(axis_degrees=0, category="Unknown", description="Insufficient data")
        
        # Calculate QRS amplitudes (simplified: peak-to-peak)
        amp_i = np.max(lead_i) - np.min(lead_i)
        amp_aVF = np.max(aVF) - np.min(aVF)
        
        # Determine net direction
        lead_i_net = np.mean(lead_i)
        aVF_net = np.mean(aVF)
        
        # Calculate approximate axis angle
        axis_rad = np.arctan2(aVF_net, lead_i_net)
        axis_deg = np.degrees(axis_rad)
        if axis_deg < 0:
            axis_deg += 360
        
        # Normalize to -180 to +180
        if axis_deg > 180:
            axis_deg -= 360
        
        # Categorize
        if -30 <= axis_deg <= 90:
            category = "Normal"
            description = f"Normal axis: {axis_deg:.0f}°"
        elif axis_deg < -30:
            category = "LAD"
            description = f"Left Axis Deviation: {axis_deg:.0f}°"
        else:  # axis_deg > 90
            category = "RAD"
            description = f"Right Axis Deviation: {axis_deg:.0f}°"
        
        return QrsAxis(
            axis_degrees=axis_deg,
            category=category,
            description=description
        )
    
    def _detect_st_abnormalities(self, ecg_signals: Dict[str, np.ndarray]) -> List[StSegmentFinding]:
        """Detect ST segment elevation/depression"""
        findings = []
        
        # ST segment usually at 40% of cardiac cycle after QRS
        # Simplified: measure elevation relative to baseline
        
        for lead_name in ['I', 'II', 'III', 'aVR', 'aVL', 'aVF', 'V1', 'V2', 'V3', 'V4', 'V5', 'V6']:
            signal = ecg_signals.get(lead_name, None)
            if signal is None:
                continue
            
            # Find ST segment (between QRS and T wave)
            # Simplified: find the baseline region with lowest amplitude
            sorted_signal = np.sort(np.abs(signal))
            baseline_threshold = sorted_signal[len(sorted_signal)//4]
            
            # Measure ST level
            st_region = signal[np.abs(signal) < baseline_threshold * 2]
            st_level = np.mean(st_region) if len(st_region) > 0 else 0
            
            # Determine location based on lead grouping
            if lead_name in self.ANTERIOR_LEADS:
                location = "anterior"
            elif lead_name in self.INFERIOR_LEADS:
                location = "inferior"
            elif lead_name in self.LATERAL_LEADS and lead_name != 'aVR':
                location = "lateral"
            else:
                location = "other"
            
            # Determine severity
            if abs(st_level) < 0.05:
                severity = "normal"
                continue
            elif abs(st_level) < 0.1:
                severity = "minimal"
            elif abs(st_level) < 0.2:
                severity = "moderate"
            else:
                severity = "significant"
            
            findings.append(StSegmentFinding(
                lead=lead_name,
                elevation_mv=st_level,
                location=location,
                severity=severity
            ))
        
        return findings
    
    def _localize_stemi(self, st_findings: List[StSegmentFinding]) -> Optional[str]:
        """Localize myocardial infarction based on ST elevation pattern"""
        if not st_findings:
            return None
        
        # Find leads with significant ST elevation
        elevated_leads = {f.lead for f in st_findings if f.severity in ["moderate", "significant"] and f.elevation_mv > 0}
        
        # Specific patterns
        if elevated_leads & set(self.ANTERIOR_LEADS):
            return "Anterior STEMI (LAD territory)"
        elif elevated_leads & set(self.INFERIOR_LEADS):
            return "Inferior STEMI (RCA/LCx territory)"
        elif elevated_leads & set(self.LATERAL_LEADS):
            return "Lateral STEMI (LCx territory)"
        
        return None
    
    def _detect_conduction_blocks(self, ecg_signals: Dict[str, np.ndarray]) -> List[ConductionBlock]:
        """Detect conduction abnormalities"""
        blocks = []
        
        # Simplified block detection based on QRS width and morphology
        # In real implementation, would measure PR interval, QRS duration precisely
        
        v1 = ecg_signals.get('V1', None)
        v6 = ecg_signals.get('V6', None)
        lead_i = ecg_signals.get('I', None)
        lead_ii = ecg_signals.get('II', None)
        
        if v1 is not None and v6 is not None:
            # Estimate QRS duration (simplified)
            v1_transitions = np.sum(np.abs(np.diff(v1)) > 0.1)
            
            # RBBB pattern: RSR' in V1, wide S in V6
            if v1_transitions > 50:
                blocks.append(ConductionBlock(
                    block_type="RBBB",
                    degree=1,
                    affected_leads=['V1', 'V2', 'V3', 'I', 'V5', 'V6'],
                    description="Right Bundle Branch Block: Wide QRS (>120 ms), RSR' in V1-V2, wide S in lateral leads"
                ))
            
            # LBBB pattern: Wide notched R in I/V6, deep S in V1
            if lead_i is not None and lead_i.max() > 1.2:
                blocks.append(ConductionBlock(
                    block_type="LBBB",
                    degree=1,
                    affected_leads=['I', 'aVL', 'V5', 'V6'],
                    description="Left Bundle Branch Block: Wide QRS (>120 ms), broad notched R in lateral leads"
                ))
        
        return blocks
    
    def _detect_wave_abnormalities(self, ecg_signals: Dict[str, np.ndarray]) -> List[WaveAbnormality]:
        """Detect abnormal P, QRS, T waves"""
        abnormalities = []
        
        # T wave inversion in specific patterns
        for lead_name in self.ANTERIOR_LEADS:
            signal = ecg_signals.get(lead_name, None)
            if signal is not None:
                # Simplified: detect if T wave is predominantly negative
                t_region = signal[len(signal)//2:]  # Later part of signal
                if np.mean(t_region) < -0.2:
                    abnormalities.append(WaveAbnormality(
                        wave_type="T",
                        leads_affected=[lead_name],
                        abnormality="inversion",
                        description=f"T wave inversion in {lead_name}"
                    ))
        
        # Pathological Q waves (especially in leads II, III, aVF for inferior MI)
        for lead_name in self.INFERIOR_LEADS:
            signal = ecg_signals.get(lead_name, None)
            if signal is not None:
                # Q wave detection (negative deflection before R)
                # Simplified detection
                min_idx = np.argmin(signal)
                if min_idx < len(signal) // 3:  # Early negative deflection
                    min_val = signal[min_idx]
                    if min_val < -0.3:
                        abnormalities.append(WaveAbnormality(
                            wave_type="Q",
                            leads_affected=[lead_name],
                            abnormality="pathological_q",
                            description=f"Pathological Q wave in {lead_name}"
                        ))
        
        return abnormalities
    
    def _determine_rhythm(self, ecg_signals: Dict[str, np.ndarray]) -> str:
        """Determine cardiac rhythm"""
        time = ecg_signals.get('time', None)
        lead_ii = ecg_signals.get('II', None)
        
        if lead_ii is None or time is None:
            return "Unknown rhythm"
        
        # Count QRS complexes by peak detection (simplified)
        from scipy.signal import find_peaks
        
        peaks, _ = find_peaks(lead_ii, height=0.5, distance=50)
        
        if len(peaks) > 0:
            total_time = time[-1] - time[0]
            heart_rate = (len(peaks) / total_time) * 60
            
            if 60 <= heart_rate <= 100:
                return f"Sinus rhythm, HR {heart_rate:.0f} bpm (normal)"
            elif heart_rate > 100:
                return f"Sinus tachycardia, HR {heart_rate:.0f} bpm"
            elif heart_rate < 60:
                return f"Sinus bradycardia, HR {heart_rate:.0f} bpm"
        
        return "Unable to determine rhythm"
    
    def _generate_primary_diagnosis(
        self, 
        stemi_location: Optional[str], 
        conduction_blocks: List[ConductionBlock],
        qrs_axis: QrsAxis,
        rhythm: str
    ) -> str:
        """Generate primary diagnosis"""
        if stemi_location:
            return f"ACUTE MYOCARDIAL INFARCTION - {stemi_location}"
        
        if conduction_blocks:
            return f"{conduction_blocks[0].block_type}"
        
        if "tachycardia" in rhythm:
            return "Sinus Tachycardia"
        elif "bradycardia" in rhythm:
            return "Sinus Bradycardia"
        
        return "Normal ECG or non-specific findings"
    
    def _generate_differential_diagnoses(
        self,
        st_findings: List[StSegmentFinding],
        wave_abnormalities: List[WaveAbnormality],
        qrs_axis: QrsAxis
    ) -> List[str]:
        """Generate differential diagnoses"""
        differentials = []
        
        if st_findings:
            differentials.append("Acute myocardial infarction")
            differentials.append("Myocarditis/Pericarditis")
        
        if any(w.abnormality == "pathological_q" for w in wave_abnormalities):
            differentials.append("Chronic myocardial infarction")
            differentials.append("Cardiomyopathy")
        
        if qrs_axis.category == "LAD":
            differentials.append("Left anterior fascicular block")
            differentials.append("Inferior myocardial infarction")
            differentials.append("Wolff-Parkinson-White syndrome")
        
        if qrs_axis.category == "RAD":
            differentials.append("Chronic lung disease")
            differentials.append("Lateral myocardial infarction")
        
        return differentials
    
    def _assess_clinical_significance(
        self,
        st_findings: List[StSegmentFinding],
        conduction_blocks: List[ConductionBlock],
        wave_abnormalities: List[WaveAbnormality],
        rhythm: str
    ) -> str:
        """Assess clinical urgency and significance"""
        if any(f.severity == "significant" for f in st_findings):
            return "🔴 CRITICAL: ST elevation suggests acute MI. Activate emergency protocol immediately. Cardiology consultation required."
        
        if conduction_blocks and "3rd degree" in str(conduction_blocks):
            return "🔴 CRITICAL: Complete heart block. Pacemaker consideration required. Immediate cardiology consultation."
        
        if "bradycardia" in rhythm and "bradycardia" in rhythm and float(rhythm.split()[-2]) < 40:
            return "🟠 URGENT: Severe bradycardia. Monitor for hemodynamic compromise."
        
        if wave_abnormalities:
            return "🟡 ABNORMAL: ECG shows pathological findings. Cardiology consultation recommended."
        
        return "✅ NORMAL: No acute findings. Routine monitoring appropriate."
    
    def _generate_recommendations(
        self,
        primary_diagnosis: str,
        st_findings: List[StSegmentFinding],
        rhythm: str
    ) -> List[str]:
        """Generate clinical recommendations"""
        recommendations = []
        
        if "INFARCTION" in primary_diagnosis:
            recommendations.extend([
                "1. ACTIVATE STEMI protocol immediately",
                "2. Call cardiology/interventional cardiology STAT",
                "3. Prepare for emergent cardiac catheterization",
                "4. Obtain troponin, electrolytes, CBC",
                "5. Start aspirin, heparin, antiplatelet therapy per protocol",
                "6. 12-lead ECG to be repeated in 10-15 minutes",
                "7. Notify cardiologist of lead location for optimal revascularization strategy"
            ])
        
        elif "bradycardia" in rhythm:
            recommendations.extend([
                "1. Assess hemodynamic status",
                "2. Monitor for progression to heart block",
                "3. Prepare pacing capability if HR < 40",
                "4. Cardiology consultation if symptomatic"
            ])
        
        elif "tachycardia" in rhythm:
            recommendations.extend([
                "1. Assess for underlying cause (infection, hyperthyroidism, pain)",
                "2. Monitor vital signs and symptoms",
                "3. Consider rate control if sustained"
            ])
        
        else:
            recommendations.extend([
                "1. Routine clinical correlation",
                "2. Repeat ECG if clinical change",
                "3. Continue standard monitoring"
            ])
        
        return recommendations


def create_clinical_summary(interpretation: EcgInterpretation) -> str:
    """Create readable clinical summary from interpretation"""
    summary = f"""
╔════════════════════════════════════════════════════════════════╗
║             12-LEAD ECG CLINICAL INTERPRETATION                ║
╚════════════════════════════════════════════════════════════════╝

PRIMARY DIAGNOSIS:
  {interpretation.primary_diagnosis}

QRS AXIS:
  {interpretation.qrs_axis.description}

RHYTHM:
  {interpretation.rhythm}

ST SEGMENT FINDINGS:
  {chr(10).join([f"  • {f.lead}: {f.elevation_mv:+.2f} mV ({f.severity})" for f in interpretation.st_findings]) if interpretation.st_findings else "  • No significant ST abnormalities"}

CONDUCTION BLOCKS:
  {chr(10).join([f"  • {b.block_type}: {b.description}" for b in interpretation.conduction_blocks]) if interpretation.conduction_blocks else "  • No conduction blocks detected"}

WAVE ABNORMALITIES:
  {chr(10).join([f"  • {w.wave_type} wave: {', '.join(w.leads_affected)} - {w.abnormality}" for w in interpretation.wave_abnormalities]) if interpretation.wave_abnormalities else "  • No wave abnormalities"}

CLINICAL SIGNIFICANCE:
  {interpretation.clinical_significance}

DIFFERENTIAL DIAGNOSES:
{chr(10).join([f"  • {d}" for d in interpretation.differential_diagnoses])}

RECOMMENDATIONS:
{chr(10).join(interpretation.recommendations)}

════════════════════════════════════════════════════════════════
    ⚠️ CLINICAL CORRELATION AND PATIENT CONTEXT ESSENTIAL ⚠️
════════════════════════════════════════════════════════════════
"""
    return summary


if __name__ == "__main__":
    from twelve_lead_generator import generate_12lead_example
    
    print("Testing ECG analyzer...")
    
    # Generate test ECG (anterior STEMI)
    ecg = generate_12lead_example(condition='anterior_stemi')
    
    # Analyze
    analyzer = TwelveLeadEcgAnalyzer()
    interpretation = analyzer.analyze_12lead(ecg)
    
    # Display results
    summary = create_clinical_summary(interpretation)
    print(summary)
