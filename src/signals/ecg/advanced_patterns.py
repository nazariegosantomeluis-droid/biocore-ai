"""
Advanced ECG Patterns for Clinical Education

Additional pathological patterns:
- Atrial Fibrillation (AF)
- Atrial Flutter
- Premature Ventricular Contractions (PVC)
- Premature Atrial Contractions (PAC)
- Wolff-Parkinson-White (WPW)
- Long QT Syndrome
- Short QT Syndrome
"""

import numpy as np
from typing import Dict, Tuple


class AdvancedEcgPatterns:
    """Generator for advanced ECG pathological patterns"""
    
    @staticmethod
    def generate_atrial_fibrillation(
        duration: float = 10.0,
        sampling_rate: float = 250,
        ventricular_rate: float = 110,
        fibrillation_amplitude: float = 0.15
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Generate Atrial Fibrillation pattern
        
        Characteristics:
        - Absent P waves
        - Irregularly irregular ventricular rate
        - Fibrillation waves (f waves) in baseline
        - Variable AV conduction
        
        Args:
            duration: Recording length in seconds
            sampling_rate: Samples per second
            ventricular_rate: Average ventricular rate (100-160 typical)
            fibrillation_amplitude: Baseline oscillation amplitude (0.1-0.3 mV)
            
        Returns:
            (signal, time) tuple
        """
        n_samples = int(duration * sampling_rate)
        time = np.arange(n_samples) / sampling_rate
        signal = np.zeros(n_samples)
        
        # Add fibrillation waves (300-600 bpm atrial rate)
        af_freq = np.random.uniform(300/60, 600/60)  # Hz
        signal += fibrillation_amplitude * np.sin(2 * np.pi * af_freq * time)
        signal += fibrillation_amplitude * 0.3 * np.cos(2 * np.pi * af_freq * 1.5 * time)
        
        # Generate irregular QRS complexes
        # Use variable RR intervals (irregular)
        beat_positions = []
        current_time = 0
        mean_rr = 60.0 / ventricular_rate
        
        while current_time < duration:
            # Random variation ±20% of mean RR
            rr_interval = mean_rr * np.random.uniform(0.8, 1.2)
            current_time += rr_interval
            beat_positions.append(int(current_time * sampling_rate))
        
        # Add QRS complexes at irregular intervals
        for beat_pos in beat_positions:
            if beat_pos < n_samples:
                # Generate irregular QRS complex
                qrs_width = int(0.12 * sampling_rate)  # 120 ms (wide in AF)
                
                if beat_pos + qrs_width < n_samples:
                    qrs = np.sin(np.linspace(0, 2*np.pi, qrs_width))
                    qrs[0:qrs_width//3] *= 0.3  # Q wave
                    qrs[qrs_width//3:2*qrs_width//3] *= 1.5  # R wave
                    qrs[2*qrs_width//3:] *= 0.4  # S wave
                    
                    signal[beat_pos:beat_pos + qrs_width] += qrs * 0.8
        
        # Add noise
        signal += np.random.normal(0, 0.02, n_samples)
        
        return signal, time
    
    @staticmethod
    def generate_atrial_flutter(
        duration: float = 10.0,
        sampling_rate: float = 250,
        flutter_rate: float = 300,
        atrioventricular_ratio: int = 2,
        ventricular_rate: float = 150
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Generate Atrial Flutter pattern
        
        Characteristics:
        - Regular "sawtooth" flutter waves
        - Regular ventricular rate (2:1, 3:1, etc. conduction)
        - Fixed AV conduction ratio
        
        Args:
            duration: Recording length
            sampling_rate: Samples per second
            flutter_rate: Atrial flutter rate (typically 250-350 bpm)
            atrioventricular_ratio: 2:1 or 3:1 conduction (default 2:1)
            ventricular_rate: Resulting ventricular rate
            
        Returns:
            (signal, time) tuple
        """
        n_samples = int(duration * sampling_rate)
        time = np.arange(n_samples) / sampling_rate
        signal = np.zeros(n_samples)
        
        # Flutter waves at regular rate (sawtooth pattern)
        flutter_freq = flutter_rate / 60  # Convert to Hz
        flutter_signal = np.sawtooth(2 * np.pi * flutter_freq * time)
        signal += 0.3 * flutter_signal
        
        # Generate regular QRS complexes
        mean_rr = 60.0 / ventricular_rate
        beat_positions = np.arange(0, duration, mean_rr)
        
        for beat_time in beat_positions:
            beat_pos = int(beat_time * sampling_rate)
            
            if beat_pos < n_samples:
                qrs_width = int(0.08 * sampling_rate)  # Narrow QRS in flutter
                
                if beat_pos + qrs_width < n_samples:
                    qrs = np.sin(np.linspace(0, 2*np.pi, qrs_width))
                    qrs[0:qrs_width//3] *= 0.2
                    qrs[qrs_width//3:2*qrs_width//3] *= 1.2
                    qrs[2*qrs_width//3:] *= 0.3
                    
                    signal[beat_pos:beat_pos + qrs_width] += qrs
        
        signal += np.random.normal(0, 0.015, n_samples)
        
        return signal, time
    
    @staticmethod
    def generate_pvc_pattern(
        base_signal: np.ndarray,
        sampling_rate: float = 250,
        pvc_positions: list = None,
        pvc_morphology: str = 'rbbb'
    ) -> np.ndarray:
        """
        Insert Premature Ventricular Contractions into existing signal
        
        Args:
            base_signal: Normal ECG signal
            sampling_rate: Samples per second
            pvc_positions: List of time positions (seconds) for PVCs
            pvc_morphology: 'rbbb' or 'lbbb' pattern
            
        Returns:
            Modified signal with PVCs
        """
        signal = base_signal.copy()
        
        if pvc_positions is None:
            pvc_positions = []
        
        for pvc_time in pvc_positions:
            pvc_idx = int(pvc_time * sampling_rate)
            
            # Generate PVC QRS
            qrs_width = int(0.16 * sampling_rate)  # 160 ms (wide)
            
            if pvc_idx + qrs_width < len(signal):
                if pvc_morphology == 'rbbb':
                    # RBBB morphology: rSR' in V1
                    qrs = np.array([0.5, -0.8, 0.6] + [-0.1] * (qrs_width - 3))
                else:
                    # LBBB morphology: broad R in V6
                    qrs = np.array([0.2, -0.3, 1.2] + [-0.2] * (qrs_width - 3))
                
                # Normalize length
                if len(qrs) < qrs_width:
                    qrs = np.concatenate([qrs, np.zeros(qrs_width - len(qrs))])
                else:
                    qrs = qrs[:qrs_width]
                
                signal[pvc_idx:pvc_idx + qrs_width] = qrs * 0.7
                
                # Add compensatory pause
                pause_duration = int(0.1 * sampling_rate)
                if pvc_idx + qrs_width + pause_duration < len(signal):
                    signal[pvc_idx + qrs_width:pvc_idx + qrs_width + pause_duration] *= 0
        
        return signal
    
    @staticmethod
    def generate_pac_pattern(
        base_signal: np.ndarray,
        sampling_rate: float = 250,
        pac_positions: list = None,
        pr_shortening: float = 0.02
    ) -> np.ndarray:
        """
        Insert Premature Atrial Contractions into existing signal
        
        Args:
            base_signal: Normal ECG signal
            sampling_rate: Samples per second
            pac_positions: List of time positions for PACs
            pr_shortening: Shortened PR interval (seconds)
            
        Returns:
            Modified signal with PACs
        """
        signal = base_signal.copy()
        
        if pac_positions is None:
            pac_positions = []
        
        for pac_time in pac_positions:
            pac_idx = int(pac_time * sampling_rate)
            
            # Early P wave (often buried in T wave or shortened PR)
            p_wave_start = max(0, pac_idx - int(0.1 * sampling_rate))
            p_wave_end = pac_idx + int(0.02 * sampling_rate)
            
            # Abnormal P wave (may be inverted or biphasic)
            p_duration = p_wave_end - p_wave_start
            p_wave = -0.2 * np.sin(np.linspace(0, np.pi, p_duration))  # Inverted
            
            signal[p_wave_start:p_wave_end] = p_wave
        
        return signal
    
    @staticmethod
    def generate_wpw_pattern(
        duration: float = 10.0,
        sampling_rate: float = 250,
        heart_rate: float = 75,
        delta_wave_amplitude: float = 0.15
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Generate Wolff-Parkinson-White (WPW) pattern
        
        Characteristics:
        - Shortened PR interval (<120 ms)
        - Delta wave (slow initial QRS component)
        - Prolonged QRS duration
        - Secondary ST changes
        
        Args:
            duration: Recording length
            sampling_rate: Samples per second
            heart_rate: HR in bpm
            delta_wave_amplitude: Slurred initial QRS (0.1-0.3 mV)
            
        Returns:
            (signal, time) tuple
        """
        n_samples = int(duration * sampling_rate)
        time = np.arange(n_samples) / sampling_rate
        signal = np.zeros(n_samples)
        
        # Generate beats with WPW characteristics
        mean_rr = 60.0 / heart_rate
        beat_positions = np.arange(0, duration, mean_rr)
        
        for beat_idx, beat_time in enumerate(beat_positions):
            beat_pos = int(beat_time * sampling_rate)
            
            # Shortened PR interval (80-120 ms)
            pr_interval = np.random.uniform(0.08, 0.12)
            p_wave_end = beat_pos + int(pr_interval * sampling_rate)
            
            if p_wave_end > beat_pos:
                # P wave
                p_duration = int(0.08 * sampling_rate)
                if p_wave_end + p_duration < n_samples:
                    p_wave = 0.15 * np.sin(np.linspace(0, np.pi, p_duration))
                    signal[p_wave_end:p_wave_end + p_duration] += p_wave
            
            # QRS with delta wave (slow slurred initial component)
            qrs_start = p_wave_end
            qrs_width = int(0.12 * sampling_rate)  # 120 ms (prolonged)
            
            if qrs_start + qrs_width < n_samples:
                # Delta wave (0-40 ms): slurred
                delta_width = int(0.04 * sampling_rate)
                delta = delta_wave_amplitude * np.linspace(0, 1, delta_width)
                
                # Main QRS (40+ ms)
                main_qrs_width = qrs_width - delta_width
                main_qrs = np.sin(np.linspace(0, 2*np.pi, main_qrs_width))
                main_qrs[0:main_qrs_width//3] *= 0.3
                main_qrs[main_qrs_width//3:2*main_qrs_width//3] *= 1.5
                main_qrs[2*main_qrs_width//3:] *= 0.4
                
                qrs = np.concatenate([delta, main_qrs])
                signal[qrs_start:qrs_start + qrs_width] += qrs
                
                # Secondary ST depression
                st_start = qrs_start + qrs_width
                st_duration = int(0.1 * sampling_rate)
                if st_start + st_duration < n_samples:
                    signal[st_start:st_start + st_duration] -= 0.15
        
        signal += np.random.normal(0, 0.015, n_samples)
        
        return signal, time
    
    @staticmethod
    def generate_long_qt_pattern(
        duration: float = 10.0,
        sampling_rate: float = 250,
        heart_rate: float = 60,
        qt_prolongation: float = 0.5
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Generate Long QT Syndrome pattern
        
        Characteristics:
        - Markedly prolonged QT interval (>500 ms)
        - Prominent/notched T wave
        - U waves
        - Risk of torsades de pointes
        
        Args:
            duration: Recording length
            sampling_rate: Samples per second
            heart_rate: HR in bpm
            qt_prolongation: Factor of prolongation (1.5-2.0)
            
        Returns:
            (signal, time) tuple
        """
        n_samples = int(duration * sampling_rate)
        time = np.arange(n_samples) / sampling_rate
        signal = np.zeros(n_samples)
        
        mean_rr = 60.0 / heart_rate
        beat_positions = np.arange(0, duration, mean_rr)
        
        for beat_time in beat_positions:
            beat_pos = int(beat_time * sampling_rate)
            
            # P wave
            p_duration = int(0.08 * sampling_rate)
            if beat_pos + p_duration < n_samples:
                p_wave = 0.15 * np.sin(np.linspace(0, np.pi, p_duration))
                signal[beat_pos:beat_pos + p_duration] += p_wave
            
            # PR interval (normal)
            pr_interval = 0.16
            qrs_start = beat_pos + int(pr_interval * sampling_rate)
            
            # Normal QRS
            qrs_width = int(0.08 * sampling_rate)
            if qrs_start + qrs_width < n_samples:
                qrs = np.sin(np.linspace(0, 2*np.pi, qrs_width))
                qrs[0:qrs_width//3] *= 0.2
                qrs[qrs_width//3:2*qrs_width//3] *= 1.5
                qrs[2*qrs_width//3:] *= 0.3
                signal[qrs_start:qrs_start + qrs_width] += qrs
            
            # Prolonged ST segment
            st_start = qrs_start + qrs_width
            
            # Prolonged QT: extend T wave
            t_duration = int(0.2 * qt_prolongation * sampling_rate)
            
            if st_start + t_duration < n_samples:
                # Prominent T wave with notch
                t_wave = 0.4 * np.sin(np.linspace(0, np.pi, t_duration))
                
                # Add notch in T wave (characteristic of Long QT)
                notch_pos = int(t_duration * 0.4)
                t_wave[notch_pos:notch_pos + int(0.02*sampling_rate)] -= 0.1
                
                signal[st_start:st_start + t_duration] += t_wave
                
                # U wave
                u_start = st_start + t_duration
                u_duration = int(0.08 * sampling_rate)
                if u_start + u_duration < n_samples:
                    u_wave = 0.15 * np.sin(np.linspace(0, np.pi, u_duration))
                    signal[u_start:u_start + u_duration] += u_wave
        
        signal += np.random.normal(0, 0.015, n_samples)
        
        return signal, time
    
    @staticmethod
    def generate_short_qt_pattern(
        duration: float = 10.0,
        sampling_rate: float = 250,
        heart_rate: float = 70
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Generate Short QT Syndrome pattern
        
        Characteristics:
        - Shortened QT interval (<300 ms)
        - Early T wave offset
        - High takeoff of ST segment
        - Risk of sudden cardiac death
        """
        n_samples = int(duration * sampling_rate)
        time = np.arange(n_samples) / sampling_rate
        signal = np.zeros(n_samples)
        
        mean_rr = 60.0 / heart_rate
        beat_positions = np.arange(0, duration, mean_rr)
        
        for beat_time in beat_positions:
            beat_pos = int(beat_time * sampling_rate)
            
            # Normal P wave
            p_duration = int(0.08 * sampling_rate)
            if beat_pos + p_duration < n_samples:
                p_wave = 0.12 * np.sin(np.linspace(0, np.pi, p_duration))
                signal[beat_pos:beat_pos + p_duration] += p_wave
            
            # Normal QRS
            pr_interval = 0.14
            qrs_start = beat_pos + int(pr_interval * sampling_rate)
            qrs_width = int(0.08 * sampling_rate)
            
            if qrs_start + qrs_width < n_samples:
                qrs = np.sin(np.linspace(0, 2*np.pi, qrs_width))
                qrs[qrs_width//3:2*qrs_width//3] *= 1.5
                signal[qrs_start:qrs_start + qrs_width] += qrs
            
            # Shortened T wave (early termination)
            t_start = qrs_start + qrs_width
            t_duration = int(0.08 * sampling_rate)  # Very short
            
            if t_start + t_duration < n_samples:
                t_wave = 0.5 * np.sin(np.linspace(0, np.pi, t_duration))
                signal[t_start:t_start + t_duration] += t_wave
        
        signal += np.random.normal(0, 0.015, n_samples)
        
        return signal, time


def demo_advanced_patterns():
    """Demonstrate all advanced patterns"""
    import matplotlib.pyplot as plt
    
    duration = 5
    
    # AF
    af_signal, af_time = AdvancedEcgPatterns.generate_atrial_fibrillation(duration=duration)
    
    # Flutter
    flutter_signal, flutter_time = AdvancedEcgPatterns.generate_atrial_flutter(duration=duration)
    
    # WPW
    wpw_signal, wpw_time = AdvancedEcgPatterns.generate_wpw_pattern(duration=duration)
    
    # Long QT
    long_qt_signal, long_qt_time = AdvancedEcgPatterns.generate_long_qt_pattern(duration=duration)
    
    print("✅ Advanced ECG patterns generated successfully")
    print(f"  - Atrial Fibrillation: {len(af_signal)} samples")
    print(f"  - Atrial Flutter: {len(flutter_signal)} samples")
    print(f"  - WPW Pattern: {len(wpw_signal)} samples")
    print(f"  - Long QT: {len(long_qt_signal)} samples")


if __name__ == "__main__":
    demo_advanced_patterns()
