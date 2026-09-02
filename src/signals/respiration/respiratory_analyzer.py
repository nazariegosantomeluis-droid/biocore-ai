"""
Respiratory Signal Analyzer - Clinical Interpretation

Analyzes respiratory signals for:
- Respiratory rate (RR) and variability
- Apnea detection and duration
- Pattern classification (normal, irregular, periodic)
- SpO2 statistics (nadir, AUC, time below threshold)
- Sleep apnea severity index
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from scipy.signal import find_peaks, butter, filtfilt


@dataclass
class BreathDetection:
    """Single breath detection result"""
    breath_num: int
    inspiration_start_idx: int
    inspiration_end_idx: int
    expiration_end_idx: int
    peak_amplitude: float  # mV or cm of movement
    duration_seconds: float
    inspiration_time: float
    expiration_time: float
    i_e_ratio: float  # Inspiration:Expiration ratio


@dataclass
class RespiratoryAnalysis:
    """Complete respiratory analysis"""
    respiratory_rate: float  # breaths/minute
    rr_variability: float  # Standard deviation
    breaths: List[BreathDetection]
    
    # Apnea analysis
    apnea_detected: bool
    apnea_type: str  # "central", "obstructive", "none"
    apnea_events: List[Dict]  # List of apnea events with duration and SpO2 drop
    apnea_hypopnea_index: float  # AHI (events per hour)
    
    # Pattern classification
    breathing_pattern: str  # "normal", "irregular", "periodic", "ataxic"
    
    # SpO2 analysis
    baseline_spo2: float
    minimum_spo2: float
    spo2_nadir_time: float  # Time of lowest SpO2
    time_below_90: float  # Seconds below 90%
    time_below_85: float  # Seconds below 85%
    oxygen_desaturation_index: float  # ODI (dips >3% per hour)
    
    # Clinical interpretation
    severity: str  # "normal", "mild", "moderate", "severe"
    clinical_notes: List[str]


class RespiratoryAnalyzer:
    """Professional respiratory signal analyzer"""
    
    def __init__(self, sampling_rate: float = 100):
        """
        Initialize analyzer
        
        Args:
            sampling_rate: Samples per second
        """
        self.sampling_rate = sampling_rate
        self.sample_interval = 1.0 / sampling_rate
    
    def analyze_respiration(
        self,
        airflow: np.ndarray,
        time: np.ndarray,
        spo2: np.ndarray,
        respiratory_effort: Optional[np.ndarray] = None
    ) -> RespiratoryAnalysis:
        """
        Perform complete respiratory analysis
        
        Args:
            airflow: Airflow signal (L/min)
            time: Time array (seconds)
            spo2: SpO2 signal (%)
            respiratory_effort: Optional chest/abdominal movement for apnea classification
            
        Returns:
            RespiratoryAnalysis with all findings
        """
        # Preprocess signal
        airflow_filtered = self._preprocess_airflow(airflow)
        
        # Detect individual breaths
        breaths = self._detect_breaths(airflow_filtered, time)
        
        # Calculate respiratory rate and variability
        rr, rr_variability = self._calculate_respiratory_rate(breaths)
        
        # Detect apneas
        apnea_detected, apnea_type, apnea_events, ahi = self._detect_apneas(
            airflow_filtered, 
            time, 
            breaths,
            respiratory_effort
        )
        
        # Classify breathing pattern
        pattern = self._classify_breathing_pattern(breaths, time)
        
        # Analyze SpO2
        baseline, minimum, nadir_time, t_below_90, t_below_85, odi = self._analyze_spo2(
            spo2, 
            time
        )
        
        # Determine severity
        severity = self._assess_severity(ahi, odi, minimum, pattern)
        
        # Generate clinical notes
        clinical_notes = self._generate_clinical_notes(
            rr, 
            pattern, 
            apnea_detected,
            apnea_type,
            minimum,
            ahi
        )
        
        return RespiratoryAnalysis(
            respiratory_rate=rr,
            rr_variability=rr_variability,
            breaths=breaths,
            apnea_detected=apnea_detected,
            apnea_type=apnea_type,
            apnea_events=apnea_events,
            apnea_hypopnea_index=ahi,
            breathing_pattern=pattern,
            baseline_spo2=baseline,
            minimum_spo2=minimum,
            spo2_nadir_time=nadir_time,
            time_below_90=t_below_90,
            time_below_85=t_below_85,
            oxygen_desaturation_index=odi,
            severity=severity,
            clinical_notes=clinical_notes
        )
    
    def _preprocess_airflow(self, airflow: np.ndarray) -> np.ndarray:
        """Preprocess airflow signal (filter and normalize)"""
        
        # High-pass filter to remove DC offset and slow drift
        b, a = butter(2, 0.1, 'highpass', fs=self.sampling_rate)
        airflow_filt = filtfilt(b, a, airflow)
        
        # Normalize
        max_amp = np.max(np.abs(airflow_filt))
        if max_amp > 0:
            airflow_norm = airflow_filt / max_amp
        else:
            airflow_norm = airflow_filt
        
        return airflow_norm
    
    def _detect_breaths(
        self,
        airflow: np.ndarray,
        time: np.ndarray
    ) -> List[BreathDetection]:
        """Detect individual breaths from airflow signal"""
        
        breaths = []
        
        # Find inspiration peaks (positive)
        inspiration_peaks, _ = find_peaks(
            airflow,
            distance=int(self.sampling_rate * 1.5)  # Min 1.5s between peaks
        )
        
        # Find expiration valleys (negative)
        expiration_peaks, _ = find_peaks(
            -airflow,
            distance=int(self.sampling_rate * 1.5)
        )
        
        # Pair inspirations and expirations
        for i, insp_idx in enumerate(inspiration_peaks[:-1]):
            # Find next expiration after this inspiration
            exp_indices = expiration_peaks[expiration_peaks > insp_idx]
            
            if len(exp_indices) > 0:
                exp_idx = exp_indices[0]
                
                # Find next inspiration or end of breath cycle
                next_insp = inspiration_peaks[i + 1] if i + 1 < len(inspiration_peaks) else len(airflow)
                
                # Calculate metrics
                insp_duration = (exp_idx - insp_idx) / self.sampling_rate
                exp_duration = (next_insp - exp_idx) / self.sampling_rate
                total_duration = (next_insp - insp_idx) / self.sampling_rate
                
                ie_ratio = insp_duration / exp_duration if exp_duration > 0 else 0
                peak_amplitude = airflow[insp_idx]
                
                breath = BreathDetection(
                    breath_num=i,
                    inspiration_start_idx=insp_idx,
                    inspiration_end_idx=exp_idx,
                    expiration_end_idx=next_insp,
                    peak_amplitude=peak_amplitude,
                    duration_seconds=total_duration,
                    inspiration_time=insp_duration,
                    expiration_time=exp_duration,
                    i_e_ratio=ie_ratio
                )
                
                breaths.append(breath)
        
        return breaths
    
    def _calculate_respiratory_rate(
        self,
        breaths: List[BreathDetection]
    ) -> Tuple[float, float]:
        """Calculate respiratory rate and variability"""
        
        if len(breaths) < 2:
            return 0, 0
        
        # Calculate RR intervals (time between breaths)
        rr_intervals = [
            breaths[i + 1].breath_num - breaths[i].breath_num
            for i in range(len(breaths) - 1)
        ]
        
        # Convert to breaths per minute
        mean_interval = np.mean(rr_intervals)
        rr = 60.0 / mean_interval if mean_interval > 0 else 0
        
        # Variability (coefficient of variation)
        rr_std = np.std(rr_intervals)
        
        return rr, rr_std
    
    def _detect_apneas(
        self,
        airflow: np.ndarray,
        time: np.ndarray,
        breaths: List[BreathDetection],
        respiratory_effort: Optional[np.ndarray] = None
    ) -> Tuple[bool, str, List[Dict], float]:
        """
        Detect apneas and classify type
        
        Central apnea: No airflow + No respiratory effort
        Obstructive apnea: No airflow but WITH respiratory effort
        """
        
        apnea_events = []
        apnea_threshold = 10.0  # 10 seconds
        
        # Define apnea windows (periods without meaningful airflow)
        apnea_mask = np.abs(airflow) < 0.1  # Low airflow threshold
        
        # Find continuous segments of apnea
        apnea_transitions = np.diff(apnea_mask.astype(int))
        apnea_starts = np.where(apnea_transitions == 1)[0]
        apnea_ends = np.where(apnea_transitions == -1)[0]
        
        # Match starts and ends
        for start, end in zip(apnea_starts, apnea_ends):
            duration = (end - start) / self.sampling_rate
            
            if duration >= (apnea_threshold / 10):  # Minimum apnea detection
                # Classify as central or obstructive
                if respiratory_effort is not None:
                    # Check if there's respiratory effort during apnea
                    effort_during_apnea = respiratory_effort[start:end]
                    mean_effort = np.mean(np.abs(effort_during_apnea))
                    
                    if mean_effort > 0.3:  # Significant effort
                        apnea_type = "obstructive"
                    else:
                        apnea_type = "central"
                else:
                    apnea_type = "unknown"
                
                apnea_event = {
                    'start_time': time[start],
                    'end_time': time[end],
                    'duration': duration,
                    'type': apnea_type
                }
                
                apnea_events.append(apnea_event)
        
        # Calculate Apnea-Hypopnea Index (AHI)
        total_time_hours = time[-1] / 3600.0
        ahi = len(apnea_events) / total_time_hours if total_time_hours > 0 else 0
        
        apnea_detected = len(apnea_events) > 0
        
        # Determine predominant apnea type
        if apnea_detected:
            types = [e['type'] for e in apnea_events]
            predominant_type = max(set(types), key=types.count) if types else "unknown"
        else:
            predominant_type = "none"
        
        return apnea_detected, predominant_type, apnea_events, ahi
    
    def _classify_breathing_pattern(
        self,
        breaths: List[BreathDetection],
        time: np.ndarray
    ) -> str:
        """Classify breathing pattern"""
        
        if len(breaths) < 3:
            return "insufficient_data"
        
        # Calculate cycle regularity (coefficient of variation of cycle times)
        cycle_times = [b.duration_seconds for b in breaths]
        cv = np.std(cycle_times) / np.mean(cycle_times) if np.mean(cycle_times) > 0 else 0
        
        # Calculate I:E ratio regularity
        ie_ratios = [b.i_e_ratio for b in breaths]
        ie_cv = np.std(ie_ratios) / np.mean(ie_ratios) if np.mean(ie_ratios) > 0 else 0
        
        if cv < 0.15 and ie_cv < 0.20:
            return "regular"
        elif cv > 0.50 and ie_cv > 0.40:
            return "irregular"
        elif time[-1] > 60 and cv < 0.40:
            # Periodic if longer record and moderate variability
            return "periodic"
        else:
            return "normal"
    
    def _analyze_spo2(
        self,
        spo2: np.ndarray,
        time: np.ndarray
    ) -> Tuple[float, float, float, float, float, float]:
        """Analyze SpO2 statistics"""
        
        baseline = np.percentile(spo2, 90)  # 90th percentile as baseline
        minimum = np.min(spo2)
        nadir_idx = np.argmin(spo2)
        nadir_time = time[nadir_idx]
        
        # Time below thresholds
        t_below_90 = np.sum(spo2 < 90) / self.sampling_rate
        t_below_85 = np.sum(spo2 < 85) / self.sampling_rate
        
        # Oxygen Desaturation Index (ODI): dips >3%
        # Simplified: count drops >3% from baseline
        baseline_for_odi = np.percentile(spo2, 95)
        dips = baseline_for_odi - spo2
        significant_dips = np.sum(dips > 3)
        
        total_time_hours = time[-1] / 3600.0
        odi = significant_dips / total_time_hours if total_time_hours > 0 else 0
        
        return baseline, minimum, nadir_time, t_below_90, t_below_85, odi
    
    def _assess_severity(
        self,
        ahi: float,
        odi: float,
        spo2_min: float,
        pattern: str
    ) -> str:
        """Assess overall sleep apnea severity"""
        
        # AASM Sleep Apnea Severity Classification
        if ahi < 5:
            return "normal"
        elif ahi < 15:
            if spo2_min < 85:
                return "moderate"
            else:
                return "mild"
        elif ahi < 30:
            return "moderate"
        else:
            return "severe"
    
    def _generate_clinical_notes(
        self,
        rr: float,
        pattern: str,
        apnea_detected: bool,
        apnea_type: str,
        spo2_min: float,
        ahi: float
    ) -> List[str]:
        """Generate clinical interpretation notes"""
        
        notes = []
        
        # Respiratory rate assessment
        if 12 <= rr <= 20:
            notes.append("✅ Respiratory rate within normal range")
        elif rr > 20:
            notes.append(f"⚠️ Tachypnea detected (RR {rr:.0f}/min)")
        elif rr < 12:
            notes.append(f"⚠️ Bradypnea detected (RR {rr:.0f}/min)")
        
        # Pattern assessment
        if pattern == "regular":
            notes.append("✅ Regular, orderly breathing pattern")
        elif pattern == "irregular":
            notes.append("⚠️ Irregular breathing pattern - may indicate sleep instability")
        elif pattern == "periodic":
            notes.append("⚠️ Periodic breathing detected - characteristic of sleep apnea")
        
        # Apnea assessment
        if apnea_detected:
            notes.append(f"🔴 {apnea_type.upper()} apnea detected (AHI {ahi:.1f} events/hour)")
            if ahi > 30:
                notes.append("🔴 SEVERE sleep apnea - cardiology referral recommended")
            elif ahi > 15:
                notes.append("⚠️ Moderate sleep apnea - CPAP therapy consideration")
        else:
            notes.append("✅ No apneas detected")
        
        # SpO2 assessment
        if spo2_min >= 95:
            notes.append("✅ SpO2 maintained >95% - adequate oxygenation")
        elif spo2_min >= 90:
            notes.append(f"⚠️ SpO2 drops to {spo2_min:.0f}% - mild hypoxemia during events")
        elif spo2_min >= 85:
            notes.append(f"🔴 SpO2 drops to {spo2_min:.0f}% - significant hypoxemia")
        else:
            notes.append(f"🔴 CRITICAL: SpO2 drops to {spo2_min:.0f}% - severe hypoxemia")
        
        return notes


def create_respiratory_summary(analysis: RespiratoryAnalysis) -> str:
    """Create readable clinical summary"""
    
    summary = f"""
╔════════════════════════════════════════════════════════╗
║         RESPIRATORY ANALYSIS CLINICAL SUMMARY          ║
╚════════════════════════════════════════════════════════╝

RESPIRATORY MECHANICS:
  Respiratory Rate: {analysis.respiratory_rate:.1f} breaths/min (variability: {analysis.rr_variability:.2f})
  Breathing Pattern: {analysis.breathing_pattern.upper()}
  Total Breaths Detected: {len(analysis.breaths)}

APNEA ANALYSIS:
  Apneas Detected: {"YES" if analysis.apnea_detected else "NO"}
  Type: {analysis.apnea_type.upper()}
  Events: {len(analysis.apnea_events)}
  AHI (Apnea-Hypopnea Index): {analysis.apnea_hypopnea_index:.1f} events/hour

OXYGENATION:
  Baseline SpO2: {analysis.baseline_spo2:.1f}%
  Minimum SpO2: {analysis.minimum_spo2:.1f}%
  Time <90%: {analysis.time_below_90:.1f} seconds
  Time <85%: {analysis.time_below_85:.1f} seconds
  ODI (Desaturation Index): {analysis.oxygen_desaturation_index:.1f} events/hour

SEVERITY: {analysis.severity.upper()}

CLINICAL NOTES:
{"".join([f"  • {note}" for note in analysis.clinical_notes])}

════════════════════════════════════════════════════════

    ⚠️ Correlation with patient symptoms essential ⚠️
    Consider: clinical presentation, daytime sleepiness,
              BMI, age, comorbidities, medication effects
════════════════════════════════════════════════════════
"""
    return summary


if __name__ == "__main__":
    from respiratory_generator import RespiratorySignalGenerator, RespiratoryPattern
    
    print("Testing respiratory analyzer...")
    
    # Generate test signal
    generator = RespiratorySignalGenerator(sampling_rate=100)
    params = RespiratoryPattern(
        respiratory_rate=15,
        pattern_type="apnea_obstructive"
    )
    respiration = generator.generate_respiration(duration=120, params=params)
    
    # Analyze
    analyzer = RespiratoryAnalyzer(sampling_rate=100)
    analysis = analyzer.analyze_respiration(
        airflow=respiration['airflow'],
        time=respiration['time'],
        spo2=respiration['spo2'],
        respiratory_effort=respiration['chest_wall']
    )
    
    # Display results
    summary = create_respiratory_summary(analysis)
    print(summary)
