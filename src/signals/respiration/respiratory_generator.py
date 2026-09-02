"""
Respiratory Signal Generator - Clinical Respiration Monitoring

Generates realistic respiratory signals including:
- Normal breathing
- Tachypnea / Bradypnea
- Apnea (central, obstructive)
- Cheyne-Stokes respiration
- Ataxic respiration
- SpO2 integration (oxygen desaturation)

Clinical References:
- Normal respiratory rate: 12-20 breaths/minute
- Airflow: measured in L/min (typically 0.3-3.0 L/min)
- SpO2 normal: >95%
- ApneaDefinition: >10 seconds without airflow
"""

import numpy as np
from typing import Dict, Tuple, Optional
from dataclasses import dataclass


@dataclass
class RespiratoryPattern:
    """Configuration for respiratory signal generation"""
    respiratory_rate: float = 15  # breaths/minute
    tidal_volume: float = 0.5  # liters
    inspiration_time: float = 1.0  # seconds
    expiration_time: float = 1.5  # seconds
    
    # Pathological patterns
    pattern_type: str = "normal"  # "normal", "tachypnea", "bradypnea", "apnea_central", "apnea_obstructive", "cheyne_stokes", "ataxic"
    apnea_duration: float = 15.0  # seconds (for apnea patterns)
    cheyne_stokes_cycle: float = 60.0  # seconds (for Cheyne-Stokes)
    
    # SpO2 related
    baseline_spo2: float = 98  # %
    desaturation_level: float = 85  # % (minimum during apnea)
    recovery_time: float = 20.0  # seconds (time to recover from desaturation)


class RespiratorySignalGenerator:
    """Generate realistic respiratory signals"""
    
    def __init__(self, sampling_rate: float = 100):
        """
        Initialize respiratory generator
        
        Args:
            sampling_rate: Samples per second
        """
        self.sampling_rate = sampling_rate
        self.sample_interval = 1.0 / sampling_rate
    
    def generate_respiration(
        self,
        duration: float = 60.0,
        params: RespiratoryPattern = None
    ) -> Dict[str, np.ndarray]:
        """
        Generate complete respiratory waveform
        
        Args:
            duration: Recording length in seconds
            params: Respiratory parameters
            
        Returns:
            Dictionary with signals:
            {
                'airflow': array,  # L/min
                'chest_wall': array,  # Strain gauge (dimensionless)
                'abdomen': array,  # Abdominal movement
                'spo2': array,  # Oxygen saturation (%)
                'time': array
            }
        """
        if params is None:
            params = RespiratoryPattern()
        
        n_samples = int(duration * self.sampling_rate)
        time = np.arange(n_samples) * self.sample_interval
        
        # Generate base respiratory pattern
        if params.pattern_type == "normal":
            airflow, chest, abdomen = self._generate_normal_respiration(time, params)
        elif params.pattern_type == "tachypnea":
            airflow, chest, abdomen = self._generate_tachypnea(time, params)
        elif params.pattern_type == "bradypnea":
            airflow, chest, abdomen = self._generate_bradypnea(time, params)
        elif params.pattern_type == "apnea_central":
            airflow, chest, abdomen = self._generate_central_apnea(time, params)
        elif params.pattern_type == "apnea_obstructive":
            airflow, chest, abdomen = self._generate_obstructive_apnea(time, params)
        elif params.pattern_type == "cheyne_stokes":
            airflow, chest, abdomen = self._generate_cheyne_stokes(time, params)
        elif params.pattern_type == "ataxic":
            airflow, chest, abdomen = self._generate_ataxic_respiration(time, params)
        else:
            airflow, chest, abdomen = self._generate_normal_respiration(time, params)
        
        # Generate SpO2 based on airflow
        spo2 = self._generate_spo2(airflow, time, params)
        
        # Add noise to signals
        airflow += np.random.normal(0, 0.02, n_samples)
        chest += np.random.normal(0, 0.01, n_samples)
        abdomen += np.random.normal(0, 0.01, n_samples)
        
        result = {
            'airflow': airflow,  # Primary respiratory signal
            'chest_wall': chest,  # Thoracic movement
            'abdomen': abdomen,  # Abdominal movement
            'spo2': spo2,  # Pulse oximetry
            'time': time
        }
        
        return result
    
    def _generate_normal_respiration(
        self,
        time: np.ndarray,
        params: RespiratoryPattern
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Generate normal quiet breathing (tidal breathing)"""
        
        airflow = np.zeros_like(time)
        chest = np.zeros_like(time)
        abdomen = np.zeros_like(time)
        
        # Calculate breathing cycle duration
        cycle_duration = 60.0 / params.respiratory_rate
        
        # Generate cycles
        cycles = time / cycle_duration
        phase = np.mod(cycles, 1.0)
        
        # Inspiration phase (0 to inspiration_fraction)
        inspiration_fraction = params.inspiration_time / cycle_duration
        
        # Generate sinusoidal airflow (positive during inspiration, negative during expiration)
        inspiration_mask = phase < inspiration_fraction
        expiration_mask = ~inspiration_mask
        
        # Inspiration: gradual increase then decrease
        inspiration_phase = phase[inspiration_mask] / inspiration_fraction
        airflow[inspiration_mask] = (
            params.tidal_volume * 
            np.sin(inspiration_phase * np.pi) * 
            (60.0 / cycle_duration)  # Convert to breaths/min scale
        )
        
        # Expiration: slower, longer phase
        expiration_phase = (phase[expiration_mask] - inspiration_fraction) / (1.0 - inspiration_fraction)
        airflow[expiration_mask] = (
            -params.tidal_volume * 
            0.5 * 
            np.sin(expiration_phase * np.pi) * 
            (60.0 / cycle_duration)
        )
        
        # Chest wall movement (primarily ribcage)
        chest = np.sin(2 * np.pi * cycles) * params.tidal_volume
        
        # Abdominal movement (primarily diaphragm)
        abdomen = 1.2 * chest  # Slightly larger amplitude
        
        return airflow, chest, abdomen
    
    def _generate_tachypnea(
        self,
        time: np.ndarray,
        params: RespiratoryPattern
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Generate tachypnea (fast, shallow breathing)"""
        
        # Modify parameters for tachypnea
        params_tach = RespiratoryPattern(
            respiratory_rate=min(params.respiratory_rate * 1.5, 40),  # Up to 40/min
            tidal_volume=params.tidal_volume * 0.6,  # Shallower
            inspiration_time=params.inspiration_time * 0.5,  # Faster
            expiration_time=params.expiration_time * 0.5
        )
        
        return self._generate_normal_respiration(time, params_tach)
    
    def _generate_bradypnea(
        self,
        time: np.ndarray,
        params: RespiratoryPattern
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Generate bradypnea (slow, deep breathing)"""
        
        # Modify parameters for bradypnea
        params_brady = RespiratoryPattern(
            respiratory_rate=max(params.respiratory_rate * 0.5, 6),  # Down to 6/min
            tidal_volume=params.tidal_volume * 1.5,  # Deeper
            inspiration_time=params.inspiration_time * 1.5,  # Slower
            expiration_time=params.expiration_time * 1.5
        )
        
        return self._generate_normal_respiration(time, params_brady)
    
    def _generate_central_apnea(
        self,
        time: np.ndarray,
        params: RespiratoryPattern
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Generate Central Sleep Apnea
        - Complete cessation of airflow AND respiratory effort
        - No chest wall or abdominal movement during apnea
        """
        airflow = np.zeros_like(time)
        chest = np.zeros_like(time)
        abdomen = np.zeros_like(time)
        
        # Baseline breathing interrupted by apneas
        baseline_rr = params.respiratory_rate
        cycle_duration = 60.0 / baseline_rr
        apnea_cycle = 60.0  # Apnea every 60 seconds
        
        cycles = time / cycle_duration
        apnea_events = time / apnea_cycle
        phase_in_apnea_cycle = np.mod(apnea_events, 1.0)
        
        # Create breathing pattern
        base_phase = np.mod(cycles, 1.0)
        inspiration_fraction = params.inspiration_time / cycle_duration
        
        # Identify apnea windows (last 20 seconds of each 60-second cycle)
        apnea_start_phase = 40.0 / 60.0
        in_apnea = phase_in_apnea_cycle >= apnea_start_phase
        
        # Generate breathing outside apnea
        breathing_mask = ~in_apnea
        inspiration_mask = (base_phase < inspiration_fraction) & breathing_mask
        expiration_mask = (base_phase >= inspiration_fraction) & breathing_mask
        
        inspiration_phase = base_phase[inspiration_mask] / inspiration_fraction
        airflow[inspiration_mask] = (
            params.tidal_volume * 
            np.sin(inspiration_phase * np.pi) * 
            (60.0 / cycle_duration)
        )
        
        expiration_phase = (base_phase[expiration_mask] - inspiration_fraction) / (1.0 - inspiration_fraction)
        airflow[expiration_mask] = (
            -params.tidal_volume * 
            0.5 * 
            np.sin(expiration_phase * np.pi) * 
            (60.0 / cycle_duration)
        )
        
        # Chest and abdomen also stop during apnea (key feature of central apnea)
        chest = np.sin(2 * np.pi * cycles) * params.tidal_volume
        chest[in_apnea] = 0  # No movement during apnea
        
        abdomen = 1.2 * chest
        
        return airflow, chest, abdomen
    
    def _generate_obstructive_apnea(
        self,
        time: np.ndarray,
        params: RespiratoryPattern
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Generate Obstructive Sleep Apnea
        - NO airflow but PERSISTENT respiratory effort (chest/abdominal movement)
        - Key difference from central apnea
        """
        airflow = np.zeros_like(time)
        chest = np.zeros_like(time)
        abdomen = np.zeros_like(time)
        
        # Baseline breathing interrupted by obstructions
        cycle_duration = 60.0 / params.respiratory_rate
        apnea_cycle = 60.0  # Event every 60 seconds
        
        cycles = time / cycle_duration
        apnea_events = time / apnea_cycle
        phase_in_apnea_cycle = np.mod(apnea_events, 1.0)
        
        base_phase = np.mod(cycles, 1.0)
        inspiration_fraction = params.inspiration_time / cycle_duration
        
        # Identify obstruction windows
        obstruction_start_phase = 40.0 / 60.0
        in_obstruction = phase_in_apnea_cycle >= obstruction_start_phase
        
        # Generate airflow (normal breathing outside obstruction)
        breathing_mask = ~in_obstruction
        inspiration_mask = (base_phase < inspiration_fraction) & breathing_mask
        expiration_mask = (base_phase >= inspiration_fraction) & breathing_mask
        
        inspiration_phase = base_phase[inspiration_mask] / inspiration_fraction
        airflow[inspiration_mask] = (
            params.tidal_volume * 
            np.sin(inspiration_phase * np.pi) * 
            (60.0 / cycle_duration)
        )
        
        expiration_phase = (base_phase[expiration_mask] - inspiration_fraction) / (1.0 - inspiration_fraction)
        airflow[expiration_mask] = (
            -params.tidal_volume * 
            0.5 * 
            np.sin(expiration_phase * np.pi) * 
            (60.0 / cycle_duration)
        )
        
        # Airflow goes to zero during obstruction but effort continues!
        airflow[in_obstruction] = 0
        
        # Key feature: chest and abdomen continue to move (paradoxical movement)
        chest = np.sin(2 * np.pi * cycles) * params.tidal_volume
        abdomen = 1.2 * chest
        
        # During obstruction, movements may become paradoxical
        abdomen[in_obstruction] *= -0.5  # Inward during obstruction attempt
        
        return airflow, chest, abdomen
    
    def _generate_cheyne_stokes(
        self,
        time: np.ndarray,
        params: RespiratoryPattern
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Generate Cheyne-Stokes respiration
        - Periodic breathing: progressive increase then decrease in depth
        - Typically 40-60 second cycles
        - Common in heart failure, CNS disease
        """
        airflow = np.zeros_like(time)
        chest = np.zeros_like(time)
        abdomen = np.zeros_like(time)
        
        cycle_duration = 60.0 / params.respiratory_rate
        cheyne_stokes_period = params.cheyne_stokes_cycle
        
        # Position within Cheyne-Stokes cycle
        cs_cycles = time / cheyne_stokes_period
        cs_phase = np.mod(cs_cycles, 1.0)
        
        # Modulation: gradual increase then decrease in amplitude
        # First half: amplitude increases (crescendo)
        # Second half: amplitude decreases (decrescendo)
        amplitude_mod = np.where(
            cs_phase < 0.5,
            cs_phase * 2,  # 0 to 1
            2 - cs_phase * 2  # 1 to 0
        )
        
        # Regular breathing cycles but with varying amplitude
        breathing_cycles = time / cycle_duration
        breathing_phase = np.mod(breathing_cycles, 1.0)
        inspiration_fraction = params.inspiration_time / cycle_duration
        
        # Generate modulated breathing
        inspiration_mask = breathing_phase < inspiration_fraction
        expiration_mask = ~inspiration_mask
        
        inspiration_phase = breathing_phase[inspiration_mask] / inspiration_fraction
        airflow[inspiration_mask] = (
            amplitude_mod[inspiration_mask] *
            params.tidal_volume * 
            np.sin(inspiration_phase * np.pi) * 
            (60.0 / cycle_duration)
        )
        
        expiration_phase = (breathing_phase[expiration_mask] - inspiration_fraction) / (1.0 - inspiration_fraction)
        airflow[expiration_mask] = (
            -amplitude_mod[expiration_mask] *
            params.tidal_volume * 
            0.5 * 
            np.sin(expiration_phase * np.pi) * 
            (60.0 / cycle_duration)
        )
        
        chest = amplitude_mod * np.sin(2 * np.pi * breathing_cycles) * params.tidal_volume
        abdomen = amplitude_mod * 1.2 * chest
        
        return airflow, chest, abdomen
    
    def _generate_ataxic_respiration(
        self,
        time: np.ndarray,
        params: RespiratoryPattern
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Generate Ataxic respiration (Biot breathing)
        - Completely irregular breathing pattern
        - Variable depth and frequency
        - Associated with brainstem injury
        """
        airflow = np.random.normal(0, params.tidal_volume * 0.3, len(time))
        
        # Add some structure to avoid complete noise
        cycle_duration = 60.0 / params.respiratory_rate
        breathing_cycles = time / cycle_duration
        base_pattern = np.sin(2 * np.pi * breathing_cycles)
        
        # Random modulation
        random_mod = np.cumsum(np.random.normal(0, 0.1, len(time)))
        random_mod = np.exp(-np.abs(random_mod) / 10)  # Decay fluctuations
        
        airflow = (base_pattern * random_mod + 
                   np.random.normal(0, 0.1, len(time))) * params.tidal_volume
        
        chest = airflow * 0.8
        abdomen = airflow * 1.1
        
        return airflow, chest, abdomen
    
    def _generate_spo2(
        self,
        airflow: np.ndarray,
        time: np.ndarray,
        params: RespiratoryPattern
    ) -> np.ndarray:
        """
        Generate SpO2 (oxygen saturation) based on respiratory signal
        
        Low/absent airflow → hypoxemia → SpO2 drop
        """
        spo2 = np.full_like(airflow, params.baseline_spo2)
        
        # Calculate ventilation index (simple: absolute value of airflow)
        ventilation = np.abs(airflow)
        max_ventilation = np.max(ventilation)
        
        if max_ventilation > 0:
            ventilation_norm = ventilation / max_ventilation
        else:
            ventilation_norm = np.ones_like(ventilation)
        
        # SpO2 decreases with poor ventilation
        desaturation = (1 - ventilation_norm) * (params.baseline_spo2 - params.desaturation_level)
        
        # Smooth desaturation (lungs don't immediately desaturate)
        kernel_size = int(self.sampling_rate * 2)  # 2-second smoothing
        kernel_size = max(kernel_size, 3)
        sigma = kernel_size / 4.0
        kernel_x = np.arange(kernel_size) - (kernel_size - 1) / 2.0
        kernel = np.exp(-0.5 * (kernel_x / sigma) ** 2)
        kernel /= np.sum(kernel)
        
        if len(desaturation) > len(kernel):
            desaturation_smooth = np.convolve(desaturation, kernel, mode='same')
        else:
            desaturation_smooth = desaturation
        
        spo2 = params.baseline_spo2 - desaturation_smooth
        
        # Ensure SpO2 stays in reasonable range
        spo2 = np.clip(spo2, 50, 100)
        
        # Add realistic noise (pulse oximetry noise)
        spo2 += np.random.normal(0, 0.5, len(spo2))
        spo2 = np.clip(spo2, 50, 100)
        
        return spo2


def demo_respiratory_patterns():
    """Demonstrate all respiratory patterns"""
    
    print("╔════════════════════════════════════════════════════════════╗")
    print("║        RESPIRATORY SIGNAL GENERATOR - DEMONSTRATION        ║")
    print("╚════════════════════════════════════════════════════════════╝\n")
    
    generator = RespiratorySignalGenerator(sampling_rate=100)
    
    patterns = [
        ("Normal", "normal"),
        ("Tachypnea", "tachypnea"),
        ("Bradypnea", "bradypnea"),
        ("Central Apnea", "apnea_central"),
        ("Obstructive Apnea", "apnea_obstructive"),
        ("Cheyne-Stokes", "cheyne_stokes"),
        ("Ataxic", "ataxic"),
    ]
    
    for name, pattern_type in patterns:
        params = RespiratoryPattern(
            respiratory_rate=15,
            tidal_volume=0.5,
            pattern_type=pattern_type
        )
        
        respiration = generator.generate_respiration(duration=30, params=params)
        
        # Calculate metrics
        airflow = respiration['airflow']
        spo2 = respiration['spo2']
        
        print(f"✅ {name.upper()}")
        print(f"   - Airflow range: {np.min(airflow):.2f} to {np.max(airflow):.2f} L/min")
        print(f"   - SpO2 range: {np.min(spo2):.1f}% to {np.max(spo2):.1f}%")
        print(f"   - Samples: {len(airflow)}\n")
    
    print("✅ Respiratory pattern generation completed successfully!")


if __name__ == "__main__":
    demo_respiratory_patterns()
