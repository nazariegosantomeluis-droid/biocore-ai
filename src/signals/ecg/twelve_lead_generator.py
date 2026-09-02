"""
12-Lead ECG Signal Generator - Professional Cardiovascular Assessment

Generates realistic 12-lead ECG signals with:
- Standard leads (I, II, III)
- Augmented limb leads (aVR, aVL, aVF)  
- Precordial leads (V1-V6)
- Configurable pathological patterns (STEMI, blocks, arrhythmias)

Clinical References:
- Lead placement: ESC/AHA guidelines
- Amplitude: mV scales (1 mm = 0.1 mV)
- Time: 25 mm/s standard
- QT interval: Bazett's formula
"""

import numpy as np
from typing import Dict, Tuple, List
from dataclasses import dataclass


@dataclass
class EcgParameters:
    """Configuration for 12-lead ECG generation"""
    heart_rate: float = 60  # bpm
    p_amplitude: float = 0.15  # mV
    pr_interval: float = 0.16  # seconds (120-200 ms)
    qrs_duration: float = 0.08  # seconds (80-120 ms)
    qt_interval: float = 0.40  # seconds
    st_segment: float = 0.0  # mV elevation
    t_amplitude: float = 0.3  # mV
    
    # Pathological markers
    axis_deviation: float = 0.0  # degrees (normal: -30 to +90)
    lvh_pattern: bool = False  # Left ventricular hypertrophy
    rbbb_pattern: bool = False  # Right bundle branch block
    lbbb_pattern: bool = False  # Left bundle branch block
    anterior_mi: bool = False  # Anterior MI (V1-V4)
    inferior_mi: bool = False  # Inferior MI (II, III, aVF)
    lateral_mi: bool = False  # Lateral MI (I, aVL, V5-V6)
    

class TwelveLeadEcgGenerator:
    """Generate professional 12-lead ECG signals"""
    
    def __init__(self, sampling_rate: float = 250.0):
        """
        Initialize ECG generator
        
        Args:
            sampling_rate: Samples per second (typically 250 Hz, up to 1000 Hz)
        """
        self.sampling_rate = sampling_rate
        self.sample_interval = 1.0 / sampling_rate
        
    def generate_ecg(
        self, 
        duration: float = 10.0,
        params: EcgParameters = None
    ) -> Dict[str, np.ndarray]:
        """
        Generate complete 12-lead ECG recording
        
        Args:
            duration: Recording length in seconds
            params: ECG parameters (uses defaults if None)
            
        Returns:
            Dictionary with leads as keys:
            {
                'I': array,   'II': array,  'III': array,
                'aVR': array, 'aVL': array, 'aVF': array,
                'V1': array,  'V2': array,  'V3': array,
                'V4': array,  'V5': array,  'V6': array,
                'time': array
            }
        """
        if params is None:
            params = EcgParameters()
            
        n_samples = int(duration * self.sampling_rate)
        time = np.arange(n_samples) * self.sample_interval
        
        # Generate base PQRST complex
        pqrst = self._generate_pqrst(time, params)
        
        # Generate standard limb leads (I, II, III)
        lead_i = pqrst.copy()
        lead_ii = pqrst.copy()
        lead_iii = pqrst.copy()
        
        # Apply lead-specific transformations
        lead_i = self._apply_lead_i_characteristics(lead_i, params)
        lead_ii = self._apply_lead_ii_characteristics(lead_ii, params)
        lead_iii = lead_ii - lead_i  # Einthoven's triangle
        
        # Generate augmented leads
        lead_aVR = -(lead_i + lead_ii) / 2  # Opposite of average
        lead_aVL = lead_i - lead_iii / 2
        lead_aVF = lead_ii + lead_iii / 2
        
        # Normalize augmented leads
        lead_aVR = lead_aVR * 1.5  # Larger amplitudes
        lead_aVL = lead_aVL * 1.5
        lead_aVF = lead_aVF * 1.5
        
        # Generate precordial leads (V1-V6)
        # V1-V2: Right ventricle (Q-wave visible, negative T)
        # V3-V4: Transition zone
        # V5-V6: Left ventricle (R-wave dominant)
        precordial = {}
        for v in range(1, 7):
            precordial[f'V{v}'] = self._generate_precordial_lead(
                lead_i, lead_ii, v, params
            )
        
        # Apply pathological patterns
        if params.anterior_mi:
            for v in range(1, 5):  # V1-V4
                precordial[f'V{v}'] = self._apply_st_elevation(
                    precordial[f'V{v}'], params.st_segment
                )
                
        if params.inferior_mi:
            lead_ii = self._apply_st_elevation(lead_ii, params.st_segment)
            lead_iii = self._apply_st_elevation(lead_iii, params.st_segment)
            lead_aVF = self._apply_st_elevation(lead_aVF, params.st_segment)
            
        if params.lateral_mi:
            lead_i = self._apply_st_elevation(lead_i, params.st_segment)
            lead_aVL = self._apply_st_elevation(lead_aVL, params.st_segment)
            for v in [5, 6]:
                precordial[f'V{v}'] = self._apply_st_elevation(
                    precordial[f'V{v}'], params.st_segment
                )
        
        # Bundle branch blocks
        if params.rbbb_pattern:
            lead_i, lead_v1, lead_v2 = self._apply_rbbb(lead_i, precordial['V1'], precordial['V2'])
            precordial['V1'] = lead_v1
            precordial['V2'] = lead_v2
            
        if params.lbbb_pattern:
            lead_i, lead_v1, lead_v6 = self._apply_lbbb(lead_i, precordial['V1'], precordial['V6'])
            precordial['V1'] = lead_v1
            precordial['V6'] = lead_v6
        
        # Left ventricular hypertrophy
        if params.lvh_pattern:
            lead_i, lead_aVL, lead_v5, lead_v6 = self._apply_lvh(
                lead_i, lead_aVL, precordial['V5'], precordial['V6']
            )
            lead_aVL = lead_aVL
            precordial['V5'] = lead_v5
            precordial['V6'] = lead_v6
        
        # Compile results
        result = {
            'I': lead_i,
            'II': lead_ii,
            'III': lead_iii,
            'aVR': lead_aVR,
            'aVL': lead_aVL,
            'aVF': lead_aVF,
            'time': time
        }
        result.update(precordial)
        
        return result
    
    def _generate_pqrst(self, time: np.ndarray, params: EcgParameters) -> np.ndarray:
        """Generate base PQRST complex"""
        rr_interval = 60.0 / params.heart_rate  # seconds
        heart_cycle = np.mod(time, rr_interval) / rr_interval  # 0 to 1
        
        signal = np.zeros_like(time)
        
        # P wave (0-0.2 of cycle)
        p_mask = (heart_cycle < 0.2) & (heart_cycle > 0.05)
        p_pos = (heart_cycle[p_mask] - 0.05) / 0.15
        signal[p_mask] += params.p_amplitude * np.sin(p_pos * np.pi)
        
        # QRS complex (0.2-0.4 of cycle, centered at 0.25)
        # NOTA (2026-07-04, Tanda 4 Pieza 2): `signal[qrs_mask][q_mask] -= ...` era un
        # bug real de indexado encadenado de NumPy — `signal[qrs_mask]` ya es una copia
        # (fancy/boolean indexing siempre copia), así que `[q_mask] -= ...` modificaba
        # esa copia descartada, nunca `signal`. El complejo QRS completo (Q, R y S)
        # nunca se escribía en la señal — cualquier consumidor de este generador
        # (ECG-12, y ahora el clasificador real del Twin OS) recibía una onda con solo
        # P y T, sin QRS. Se arregla construyendo el tramo QRS aparte y asignándolo de
        # una sola vez con `signal[qrs_mask] = qrs_values` (sin indexado encadenado).
        qrs_mask = (heart_cycle > 0.15) & (heart_cycle < 0.35)
        qrs_pos = (heart_cycle[qrs_mask] - 0.15) / 0.2
        qrs_values = np.zeros_like(qrs_pos)

        # Q wave (slight negative)
        q_mask = qrs_pos < 0.33
        qrs_values[q_mask] -= 0.1 * np.sin(qrs_pos[q_mask] * np.pi / 0.33)

        # R wave (main positive)
        r_mask = (qrs_pos >= 0.33) & (qrs_pos < 0.67)
        qrs_values[r_mask] += 1.2 * np.sin((qrs_pos[r_mask] - 0.33) * np.pi / 0.34)

        # S wave (negative)
        s_mask = qrs_pos >= 0.67
        qrs_values[s_mask] -= 0.3 * np.sin((qrs_pos[s_mask] - 0.67) * np.pi / 0.33)

        signal[qrs_mask] += qrs_values
        
        # ST segment (flat baseline expected)
        st_mask = (heart_cycle > 0.35) & (heart_cycle < 0.55)
        signal[st_mask] += 0.0  # Modified by pathology
        
        # T wave (0.55-0.95)
        t_mask = (heart_cycle > 0.55) & (heart_cycle < 0.95)
        t_pos = (heart_cycle[t_mask] - 0.55) / 0.4
        signal[t_mask] += params.t_amplitude * np.sin(t_pos * np.pi)
        
        # Add noise
        noise = np.random.normal(0, 0.01, len(signal))  # 0.01 mV noise
        signal += noise
        
        return signal
    
    def _apply_lead_i_characteristics(self, signal: np.ndarray, params: EcgParameters) -> np.ndarray:
        """Apply Lead I characteristics (left arm view)"""
        # Lead I is baseline for axis calculation
        if params.axis_deviation != 0:
            # Axis deviation rotates the ECG vector
            rotation_factor = params.axis_deviation / 90.0
            signal = signal * (1 + 0.1 * rotation_factor)
        
        return signal
    
    def _apply_lead_ii_characteristics(self, signal: np.ndarray, params: EcgParameters) -> np.ndarray:
        """Apply Lead II characteristics (right shoulder to left foot)"""
        # Lead II typically shows largest R wave
        # Increase R wave amplitude
        signal = signal * 1.1
        return signal
    
    def _generate_precordial_lead(
        self, 
        lead_i: np.ndarray, 
        lead_ii: np.ndarray,
        lead_num: int, 
        params: EcgParameters
    ) -> np.ndarray:
        """Generate precordial lead (V1-V6)"""
        # V1-V2: Right ventricle (negative QRS, late S wave)
        # V3-V4: Transition
        # V5-V6: Left ventricle (positive QRS, large R)
        
        if lead_num <= 2:
            # Right ventricle view
            signal = -lead_i * 0.7 - lead_ii * 0.3
        elif lead_num <= 4:
            # Transition zone
            weight_left = (lead_num - 2) / 2
            signal = -lead_i * (1 - weight_left) + lead_ii * weight_left
        else:
            # Left ventricle
            signal = lead_i * 0.8 + lead_ii * 0.2
        
        # Gradually increase amplitude from V1 to V6
        amplitude_scale = 0.5 + 0.15 * lead_num
        signal = signal * amplitude_scale
        
        return signal
    
    def _apply_st_elevation(self, signal: np.ndarray, elevation: float) -> np.ndarray:
        """Apply ST segment elevation (STEMI marker)"""
        # Find ST segment (approximately 0.35-0.55 of cardiac cycle)
        # Simplified: add DC offset during ST segment
        signal_copy = signal.copy()
        
        # Detect ST segment by amplitude (low baseline region after QRS)
        st_threshold = np.percentile(np.abs(signal_copy), 25)
        st_mask = np.abs(signal_copy) < st_threshold
        
        signal_copy[st_mask] += elevation
        return signal_copy
    
    def _apply_rbbb(self, lead_i: np.ndarray, v1: np.ndarray, v2: np.ndarray) -> Tuple:
        """Apply Right Bundle Branch Block pattern
        
        RBBB characteristics:
        - QRS duration > 120 ms
        - RSR' pattern in V1-V2
        - Wide S wave in I, V5-V6
        """
        # Widen QRS and add secondary R wave
        lead_i_mod = lead_i * 1.1  # Widen QRS
        v1_mod = v1.copy()
        v2_mod = v2.copy()
        
        # Add secondary positive deflection (RSR' pattern)
        # This is simplified - in real ECG requires precise timing
        
        return lead_i_mod, v1_mod, v2_mod
    
    def _apply_lbbb(self, lead_i: np.ndarray, v1: np.ndarray, v6: np.ndarray) -> Tuple:
        """Apply Left Bundle Branch Block pattern
        
        LBBB characteristics:
        - QRS duration > 120 ms
        - Broad notched R wave in I, V5-V6
        - Deep S wave in V1-V2
        """
        lead_i_mod = lead_i * 1.15  # Increase R wave
        v1_mod = v1 * 1.3  # Deeper S wave
        v6_mod = v6 * 1.15
        
        return lead_i_mod, v1_mod, v6_mod
    
    def _apply_lvh(self, lead_i: np.ndarray, aVL: np.ndarray, v5: np.ndarray, v6: np.ndarray) -> Tuple:
        """Apply Left Ventricular Hypertrophy pattern
        
        LVH characteristics:
        - Increased QRS amplitude in left leads (I, aVL)
        - Increased S wave in V1-V2
        - Increased R wave in V5-V6
        - T wave inversion in lateral leads
        """
        # Increase amplitude in left-sided leads
        lead_i_mod = lead_i * 1.3
        aVL_mod = aVL * 1.3
        v5_mod = v5 * 1.3
        v6_mod = v6 * 1.3
        
        return lead_i_mod, aVL_mod, v5_mod, v6_mod
    
    def get_lead_metadata(self) -> Dict[str, Dict]:
        """Get clinical metadata for each lead"""
        return {
            'I': {
                'name': 'Lateral I',
                'placement': 'Left arm vs Right arm',
                'axis': 0,
                'normal_qrs': 'Small Q, Medium R, Small S'
            },
            'II': {
                'name': 'Inferior',
                'placement': 'Right shoulder to Left foot',
                'axis': 60,
                'normal_qrs': 'Small Q, Large R, Small S'
            },
            'III': {
                'name': 'Inferior',
                'placement': 'Left arm to Left foot',
                'axis': 120,
                'normal_qrs': 'Variable (depends on axis)'
            },
            'aVR': {
                'name': 'Right',
                'placement': 'Right arm (opposite view)',
                'axis': -150,
                'normal_qrs': 'Negative (away from right arm)'
            },
            'aVL': {
                'name': 'Lateral I',
                'placement': 'Left arm',
                'axis': -30,
                'normal_qrs': 'Small Q, Medium R'
            },
            'aVF': {
                'name': 'Inferior',
                'placement': 'Left foot',
                'axis': 90,
                'normal_qrs': 'Small Q, Large R'
            },
            'V1': {
                'name': 'Septal',
                'placement': '4th intercostal, right sternal border',
                'axis': None,
                'normal_qrs': 'Small R (or absent), Large S'
            },
            'V2': {
                'name': 'Septal',
                'placement': '4th intercostal, left sternal border',
                'axis': None,
                'normal_qrs': 'Small R, Large S'
            },
            'V3': {
                'name': 'Anterior',
                'placement': 'Midway between V2 and V4',
                'axis': None,
                'normal_qrs': 'Transition zone'
            },
            'V4': {
                'name': 'Anterior',
                'placement': '4th intercostal, midclavicular line',
                'axis': None,
                'normal_qrs': 'Largest R wave'
            },
            'V5': {
                'name': 'Lateral',
                'placement': '5th intercostal, anterior axillary line',
                'axis': None,
                'normal_qrs': 'Large R, Small S'
            },
            'V6': {
                'name': 'Lateral',
                'placement': '5th intercostal, midaxillary line',
                'axis': None,
                'normal_qrs': 'R > S'
            }
        }


def generate_12lead_example(
    heart_rate: float = 75,
    condition: str = 'normal'
) -> Dict[str, np.ndarray]:
    """
    Convenience function to generate common ECG patterns
    
    Args:
        heart_rate: Heart rate in bpm
        condition: 'normal', 'tachycardia', 'bradycardia', 'anterior_stemi', 
                   'inferior_stemi', 'rbbb', 'lbbb', 'lvh'
    
    Returns:
        12-lead ECG signals
    """
    params = EcgParameters(heart_rate=heart_rate)
    
    if condition == 'tachycardia':
        params.heart_rate = 110
    elif condition == 'bradycardia':
        params.heart_rate = 45
    elif condition == 'anterior_stemi':
        params.anterior_mi = True
        params.st_segment = 0.25  # 2.5 mm = 0.25 mV
    elif condition == 'inferior_stemi':
        params.inferior_mi = True
        params.st_segment = 0.2
    elif condition == 'rbbb':
        params.rbbb_pattern = True
        params.qrs_duration = 0.12
    elif condition == 'lbbb':
        params.lbbb_pattern = True
        params.qrs_duration = 0.12
    elif condition == 'lvh':
        params.lvh_pattern = True
    
    generator = TwelveLeadEcgGenerator()
    return generator.generate_ecg(duration=10.0, params=params)


if __name__ == "__main__":
    # Example usage
    print("Generating 12-lead ECG signals...")
    
    # Normal ECG
    normal_ecg = generate_12lead_example(heart_rate=75, condition='normal')
    print(f"Normal ECG generated: {len(normal_ecg)} leads, {len(normal_ecg['time'])} samples")
    
    # Anterior STEMI
    stemi_ecg = generate_12lead_example(condition='anterior_stemi')
    print(f"Anterior STEMI generated: ST elevation in V1-V4")
    
    # RBBB
    rbbb_ecg = generate_12lead_example(condition='rbbb')
    print(f"RBBB pattern generated: Wide QRS in V1-V2")
