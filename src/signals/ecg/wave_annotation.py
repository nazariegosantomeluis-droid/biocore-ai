"""
Wave Annotation and Timing for 12-Lead ECG

Automatically detects and annotates:
- P wave: Onset, peak, offset
- QRS complex: Q onset, R peak, S offset
- T wave: Onset, peak, offset
- Intervals: PR, QRS, QT, ST

Clinical references:
- Normal PR: 120-200 ms
- Normal QRS: 60-120 ms  
- Normal QT: <440 ms (males), <460 ms (females)
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class WaveAnnotation:
    """Single wave annotation"""
    wave_type: str  # 'P', 'Q', 'R', 'S', 'T'
    lead: str
    onset_idx: int
    peak_idx: int
    offset_idx: int
    amplitude: float  # mV
    duration_ms: float
    

@dataclass
class ComplexAnnotation:
    """Full PQRST complex annotation for a single beat"""
    beat_num: int
    lead: str
    p_wave: Optional[WaveAnnotation]
    qrs_complex: Optional[Dict[str, WaveAnnotation]]  # Q, R, S
    t_wave: Optional[WaveAnnotation]
    pr_interval_ms: float
    qrs_duration_ms: float
    qt_interval_ms: float
    st_segment_level: float


class WaveAnnotator:
    """Automatic wave annotation for ECG signals"""
    
    def __init__(self, sampling_rate: float = 250):
        """
        Initialize annotator
        
        Args:
            sampling_rate: Samples per second
        """
        self.sampling_rate = sampling_rate
        self.sample_interval = 1.0 / sampling_rate
        
    def annotate_lead(self, signal: np.ndarray, lead_name: str) -> List[ComplexAnnotation]:
        """
        Annotate all PQRST complexes in a signal
        
        Args:
            signal: ECG signal array
            lead_name: Lead identifier (e.g., 'II')
            
        Returns:
            List of annotated complexes
        """
        # Detect QRS complexes first (anchor point)
        qrs_positions = self._detect_qrs(signal)
        
        if len(qrs_positions) == 0:
            return []
        
        annotations = []
        
        for beat_num, qrs_peak_idx in enumerate(qrs_positions):
            # Define windows around QRS
            p_window_start = max(0, qrs_peak_idx - int(0.3 * self.sampling_rate))  # 300 ms before
            p_window_end = qrs_peak_idx
            
            qrs_window_start = max(0, qrs_peak_idx - int(0.1 * self.sampling_rate))  # 100 ms before peak
            qrs_window_end = min(len(signal), qrs_peak_idx + int(0.1 * self.sampling_rate))  # 100 ms after
            
            t_window_start = qrs_peak_idx
            t_window_end = min(len(signal), qrs_peak_idx + int(0.4 * self.sampling_rate))  # 400 ms after
            
            # Extract waves
            p_wave = self._extract_p_wave(signal, p_window_start, p_window_end, lead_name)
            qrs_complex = self._extract_qrs_complex(signal, qrs_window_start, qrs_window_end)
            t_wave = self._extract_t_wave(signal, t_window_start, t_window_end, lead_name)
            
            # Calculate intervals
            pr_interval = self._calculate_pr_interval(p_wave, qrs_complex)
            qrs_duration = self._calculate_qrs_duration(qrs_complex)
            qt_interval = self._calculate_qt_interval(qrs_complex, t_wave)
            st_segment = self._calculate_st_segment(signal, qrs_peak_idx, t_window_start)
            
            annotation = ComplexAnnotation(
                beat_num=beat_num,
                lead=lead_name,
                p_wave=p_wave,
                qrs_complex=qrs_complex,
                t_wave=t_wave,
                pr_interval_ms=pr_interval,
                qrs_duration_ms=qrs_duration,
                qt_interval_ms=qt_interval,
                st_segment_level=st_segment
            )
            
            annotations.append(annotation)
        
        return annotations
    
    def _detect_qrs(self, signal: np.ndarray) -> List[int]:
        """Detect QRS peak positions"""
        from scipy.signal import find_peaks
        
        # Simple peak detection - R wave is strongest positive deflection
        # Use adaptive threshold
        baseline = np.median(signal)
        threshold = baseline + 0.5 * np.std(signal)
        
        peaks, _ = find_peaks(
            signal, 
            height=threshold,
            distance=int(0.3 * self.sampling_rate)  # Min 300 ms between beats
        )
        
        return peaks.tolist()
    
    def _extract_p_wave(
        self, 
        signal: np.ndarray, 
        start_idx: int, 
        end_idx: int,
        lead_name: str
    ) -> Optional[WaveAnnotation]:
        """Extract P wave annotation"""
        
        if start_idx >= end_idx:
            return None
        
        p_region = signal[start_idx:end_idx]
        
        if len(p_region) < 10:
            return None
        
        # Find P wave peak (should be positive in most leads)
        # Exception: aVR shows negative P
        if lead_name == 'aVR':
            peak_local_idx = np.argmin(p_region)
        else:
            peak_local_idx = np.argmax(p_region)
        
        peak_idx = start_idx + peak_local_idx
        amplitude = signal[peak_idx]
        
        # Find onset and offset (where crosses baseline)
        baseline = np.mean(signal[max(0, start_idx-50):start_idx])
        
        # Onset: first point where signal exceeds baseline
        onset_region = p_region[:peak_local_idx]
        if len(onset_region) > 0:
            if lead_name == 'aVR':
                onset_local_idx = np.where(onset_region < baseline - 0.02)[0]
            else:
                onset_local_idx = np.where(onset_region > baseline + 0.02)[0]
            
            onset_idx = start_idx + (onset_local_idx[0] if len(onset_local_idx) > 0 else 0)
        else:
            onset_idx = start_idx
        
        # Offset: last point where signal exceeds baseline after peak
        offset_region = p_region[peak_local_idx:]
        if len(offset_region) > 0:
            if lead_name == 'aVR':
                offset_local_idx = np.where(offset_region < baseline - 0.02)[0]
            else:
                offset_local_idx = np.where(offset_region > baseline + 0.02)[0]
            
            if len(offset_local_idx) > 0:
                offset_idx = start_idx + peak_local_idx + offset_local_idx[-1]
            else:
                offset_idx = peak_idx + int(0.1 * self.sampling_rate)
        else:
            offset_idx = peak_idx + int(0.05 * self.sampling_rate)
        
        duration_ms = (offset_idx - onset_idx) / self.sampling_rate * 1000
        
        return WaveAnnotation(
            wave_type='P',
            lead=lead_name,
            onset_idx=onset_idx,
            peak_idx=peak_idx,
            offset_idx=offset_idx,
            amplitude=amplitude,
            duration_ms=duration_ms
        )
    
    def _extract_qrs_complex(
        self,
        signal: np.ndarray,
        start_idx: int,
        end_idx: int
    ) -> Dict[str, WaveAnnotation]:
        """Extract Q, R, S wave annotations"""
        
        qrs_dict = {}
        
        if start_idx >= end_idx:
            return qrs_dict
        
        qrs_region = signal[start_idx:end_idx]
        
        # Find R peak (maximum)
        r_local_idx = np.argmax(qrs_region)
        r_idx = start_idx + r_local_idx
        r_amplitude = signal[r_idx]
        
        # Q wave (negative deflection before R)
        if r_local_idx > 0:
            q_region = qrs_region[:r_local_idx]
            q_local_idx = np.argmin(q_region)
            q_idx = start_idx + q_local_idx
            q_amplitude = signal[q_idx]
            
            # Q wave should be noticeable (> 0.1 mV)
            if q_amplitude < -0.05:
                qrs_dict['Q'] = WaveAnnotation(
                    wave_type='Q',
                    lead='',
                    onset_idx=q_idx - int(0.01 * self.sampling_rate),
                    peak_idx=q_idx,
                    offset_idx=q_idx,
                    amplitude=q_amplitude,
                    duration_ms=0
                )
        
        # R wave
        qrs_dict['R'] = WaveAnnotation(
            wave_type='R',
            lead='',
            onset_idx=start_idx,
            peak_idx=r_idx,
            offset_idx=r_idx,
            amplitude=r_amplitude,
            duration_ms=0
        )
        
        # S wave (negative deflection after R)
        if r_local_idx < len(qrs_region) - 1:
            s_region = qrs_region[r_local_idx:]
            s_local_idx = np.argmin(s_region)
            s_idx = start_idx + r_local_idx + s_local_idx
            s_amplitude = signal[s_idx]
            
            if s_amplitude < -0.05:
                qrs_dict['S'] = WaveAnnotation(
                    wave_type='S',
                    lead='',
                    onset_idx=s_idx,
                    peak_idx=s_idx,
                    offset_idx=s_idx + int(0.01 * self.sampling_rate),
                    amplitude=s_amplitude,
                    duration_ms=0
                )
        
        return qrs_dict
    
    def _extract_t_wave(
        self,
        signal: np.ndarray,
        start_idx: int,
        end_idx: int,
        lead_name: str
    ) -> Optional[WaveAnnotation]:
        """Extract T wave annotation"""
        
        if start_idx >= end_idx:
            return None
        
        t_region = signal[start_idx:end_idx]
        
        if len(t_region) < 10:
            return None
        
        # T wave typically positive (except aVR, V1)
        if lead_name in ['aVR', 'V1']:
            peak_local_idx = np.argmin(t_region)
        else:
            peak_local_idx = np.argmax(t_region)
        
        peak_idx = start_idx + peak_local_idx
        amplitude = signal[peak_idx]
        
        # Onset/offset detection
        baseline = np.mean(signal[max(0, end_idx-50):end_idx])
        
        onset_region = t_region[:peak_local_idx]
        if len(onset_region) > 0:
            if lead_name in ['aVR', 'V1']:
                onset_local_idx = np.where(onset_region < baseline - 0.02)[0]
            else:
                onset_local_idx = np.where(onset_region > baseline + 0.02)[0]
            
            onset_idx = start_idx + (onset_local_idx[0] if len(onset_local_idx) > 0 else 0)
        else:
            onset_idx = start_idx
        
        offset_region = t_region[peak_local_idx:]
        if len(offset_region) > 0:
            if lead_name in ['aVR', 'V1']:
                offset_local_idx = np.where(offset_region < baseline - 0.02)[0]
            else:
                offset_local_idx = np.where(offset_region > baseline + 0.02)[0]
            
            offset_idx = start_idx + peak_local_idx + (offset_local_idx[-1] if len(offset_local_idx) > 0 else len(offset_region))
        else:
            offset_idx = end_idx
        
        duration_ms = (offset_idx - onset_idx) / self.sampling_rate * 1000
        
        return WaveAnnotation(
            wave_type='T',
            lead=lead_name,
            onset_idx=onset_idx,
            peak_idx=peak_idx,
            offset_idx=offset_idx,
            amplitude=amplitude,
            duration_ms=duration_ms
        )
    
    def _calculate_pr_interval(
        self,
        p_wave: Optional[WaveAnnotation],
        qrs_complex: Dict[str, WaveAnnotation]
    ) -> float:
        """Calculate PR interval in milliseconds"""
        
        if p_wave is None or 'R' not in qrs_complex:
            return 0
        
        r_wave = qrs_complex['R']
        duration = (r_wave.peak_idx - p_wave.onset_idx) / self.sampling_rate * 1000
        
        return duration
    
    def _calculate_qrs_duration(self, qrs_complex: Dict[str, WaveAnnotation]) -> float:
        """Calculate QRS duration in milliseconds"""
        
        if not qrs_complex or 'R' not in qrs_complex:
            return 0
        
        q_start = qrs_complex.get('Q', qrs_complex['R']).onset_idx
        s_end = qrs_complex.get('S', qrs_complex['R']).offset_idx
        
        duration = (s_end - q_start) / self.sampling_rate * 1000
        
        return duration
    
    def _calculate_qt_interval(
        self,
        qrs_complex: Dict[str, WaveAnnotation],
        t_wave: Optional[WaveAnnotation]
    ) -> float:
        """Calculate QT interval in milliseconds"""
        
        if not qrs_complex or 'Q' not in qrs_complex or t_wave is None:
            return 0
        
        q_start = qrs_complex['Q'].onset_idx
        t_end = t_wave.offset_idx
        
        duration = (t_end - q_start) / self.sampling_rate * 1000
        
        return duration
    
    def _calculate_st_segment(
        self,
        signal: np.ndarray,
        qrs_peak_idx: int,
        t_onset_idx: int
    ) -> float:
        """Calculate ST segment level (elevation/depression)"""
        
        # ST point is typically 80 ms after QRS peak
        st_point_idx = int(qrs_peak_idx + 0.08 * self.sampling_rate)
        
        if st_point_idx >= len(signal):
            return 0
        
        # Measure baseline (80 ms before QRS)
        baseline_start = max(0, qrs_peak_idx - int(0.08 * self.sampling_rate))
        baseline_end = qrs_peak_idx
        baseline = np.mean(signal[baseline_start:baseline_end])
        
        # ST level relative to baseline
        st_level = signal[st_point_idx] - baseline
        
        return st_level


def create_wave_annotation_summary(annotation: ComplexAnnotation) -> str:
    """Create readable summary of wave annotations"""
    summary = f"""
╔════════════════════════════════════════════╗
║      BEAT #{annotation.beat_num} - {annotation.lead}         ║
╚════════════════════════════════════════════╝

P WAVE:
  {f"  Onset: {annotation.p_wave.onset_idx} | Peak: {annotation.p_wave.peak_idx} | Offset: {annotation.p_wave.offset_idx}" if annotation.p_wave else "  Not detected"}
  {f"  Amplitude: {annotation.p_wave.amplitude:+.2f} mV | Duration: {annotation.p_wave.duration_ms:.0f} ms" if annotation.p_wave else ""}

PR INTERVAL: {annotation.pr_interval_ms:.0f} ms {'✅' if 120 <= annotation.pr_interval_ms <= 200 else '⚠️'}

QRS COMPLEX:
  Q: {f"{annotation.qrs_complex['Q'].amplitude:+.2f} mV" if 'Q' in annotation.qrs_complex else "Not prominent"}
  R: {f"{annotation.qrs_complex['R'].amplitude:+.2f} mV" if 'R' in annotation.qrs_complex else "N/A"}
  S: {f"{annotation.qrs_complex['S'].amplitude:+.2f} mV" if 'S' in annotation.qrs_complex else "Not prominent"}

QRS DURATION: {annotation.qrs_duration_ms:.0f} ms {'✅' if 60 <= annotation.qrs_duration_ms <= 120 else '⚠️'}

ST SEGMENT: {annotation.st_segment_level:+.2f} mV {'✅' if abs(annotation.st_segment_level) < 0.1 else '⚠️'}

T WAVE:
  {f"  Onset: {annotation.t_wave.onset_idx} | Peak: {annotation.t_wave.peak_idx} | Offset: {annotation.t_wave.offset_idx}" if annotation.t_wave else "  Not detected"}
  {f"  Amplitude: {annotation.t_wave.amplitude:+.2f} mV | Duration: {annotation.t_wave.duration_ms:.0f} ms" if annotation.t_wave else ""}

QT INTERVAL: {annotation.qt_interval_ms:.0f} ms {'✅' if annotation.qt_interval_ms < 440 else '⚠️'}

════════════════════════════════════════════
"""
    return summary


if __name__ == "__main__":
    # Test annotation
    from twelve_lead_generator import generate_12lead_example
    
    print("Testing wave annotation...")
    
    ecg = generate_12lead_example(heart_rate=75, condition='normal')
    annotator = WaveAnnotator(sampling_rate=500)
    
    # Annotate lead II
    annotations = annotator.annotate_lead(ecg['II'], 'II')
    
    if annotations:
        for ann in annotations[:2]:  # Show first 2 beats
            print(create_wave_annotation_summary(ann))
