"""
Signal Generator for ECG Educational Cases

Generates synthetic ECG waveforms for various arrhythmias and clinical conditions.
"""

import numpy as np

from src.signals.ecg.arrhythmia_types import get_type

class ECGGenerator:
    @staticmethod
    def generate_base_ecg(duration: float, fs: float, hr: float, noise: float = 0.05):
        t = np.linspace(0, duration, int(duration * fs))
        signal = np.zeros_like(t)
        
        period = 60.0 / hr
        n_beats = int(duration / period)
        
        for i in range(n_beats):
            center = (i + 0.5) * period
            # P wave
            signal += 0.15 * np.exp(-((t - (center - 0.15))**2) / (2 * 0.02**2))
            # QRS
            signal += 1.2 * np.exp(-((t - center)**2) / (2 * 0.01**2))
            # T wave
            signal += 0.3 * np.exp(-((t - (center + 0.25))**2) / (2 * 0.04**2))
            
        signal += noise * np.random.randn(len(t))
        return t, signal

    @staticmethod
    def generate_afib(duration: float, fs: float, avg_hr: float = None, seed: int = 0):
        # Unificación 1: la FC media y su recorte salen del tipo canónico (fuente única); antes eran
        # un 120 y un recorte 80-180 propios de este generador. Misma semilla, mismo trazado.
        afib = get_type('afib')
        avg_hr = afib.nominal_hr_bpm if avg_hr is None else avg_hr
        rng = np.random.default_rng(seed)
        t = np.linspace(0, duration, int(duration * fs))
        signal = np.zeros_like(t)
        
        current_t = 0.2
        while current_t < duration - 0.5:
            hr = avg_hr + rng.normal(0, 25)
            hr = np.clip(hr, afib.hr_min_bpm, afib.hr_max_bpm)
            period = 60.0 / hr
            
            signal += 1.1 * np.exp(-((t - current_t)**2) / (2 * 0.01**2))
            signal += 0.25 * np.exp(-((t - (current_t + 0.2))**2) / (2 * 0.04**2))
            current_t += period
            
        signal += 0.08 * np.sin(2 * np.pi * rng.uniform(10, 20) * t)
        signal += 0.05 * rng.standard_normal(len(t))
        return t, signal

    @staticmethod
    def generate_vt(duration: float, fs: float, hr: float = 160):
        t = np.linspace(0, duration, int(duration * fs))
        signal = np.zeros_like(t)
        period = 60.0 / hr
        
        for i in range(int(duration / period)):
            center = (i + 0.2) * period
            signal += 1.5 * np.exp(-((t - center)**2) / (2 * 0.04**2))
            signal -= 0.5 * np.exp(-((t - (center + 0.15))**2) / (2 * 0.06**2))
            
        signal += 0.05 * np.random.randn(len(t))
        return t, signal

    @staticmethod
    def generate_stemi(duration: float, fs: float, hr: float = 85, st_elevation: float = 0.4):
        t, signal = ECGGenerator.generate_base_ecg(duration, fs, hr)
        
        period = 60.0 / hr
        for i in range(int(duration / period)):
            center = (i + 0.5) * period
            st_mask = (t > center + 0.02) & (t < center + 0.18)
            signal[st_mask] += st_elevation
            
        return t, signal

    @staticmethod
    def get_case(case_type: str, duration: float = 10, fs: float = 250):
        if case_type == 'ritmo_sinusal_normal':
            return ECGGenerator.generate_base_ecg(duration, fs, 75)
        elif case_type == 'taquicardia':
            return ECGGenerator.generate_base_ecg(duration, fs, 120)
        elif case_type == 'bradicardia':
            return ECGGenerator.generate_base_ecg(duration, fs, get_type('sbrady').nominal_hr_bpm)
        elif case_type == 'fibrilacion_auricular':
            return ECGGenerator.generate_afib(duration, fs)
        elif case_type == 'taquicardia_ventricular':
            return ECGGenerator.generate_vt(duration, fs)
        elif case_type == 'stemi':
            return ECGGenerator.generate_stemi(duration, fs)
        else:
            return ECGGenerator.generate_base_ecg(duration, fs, 70)

def get_all_case_types():
    return ['ritmo_sinusal_normal', 'taquicardia', 'bradicardia', 'fibrilacion_auricular', 'taquicardia_ventricular', 'stemi']