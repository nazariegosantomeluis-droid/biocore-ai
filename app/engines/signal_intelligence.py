"""
BIOCORE AI — SIGNAL INTELLIGENCE LAYER

Motores especializados de procesamiento de señales biomédicas.

- ECG Engine
- EEG Engine
- EMG Engine  
- Respiratory Engine
- PPG/SpO2 Engine
"""

from typing import Dict, Tuple, List, Any
from dataclasses import dataclass
import numpy as np
from enum import Enum


class CardiacRhythm(Enum):
    """Ritmos cardíacos detectables"""
    NORMAL_SINUS = "normal_sinus"
    SINUS_TACHYCARDIA = "sinus_tachycardia"
    SINUS_BRADYCARDIA = "sinus_bradycardia"
    ATRIAL_FIBRILLATION = "atrial_fibrillation"
    VENTRICULAR_TACHYCARDIA = "ventricular_tachycardia"
    PREMATURE_VENTRICULAR_BEAT = "premature_ventricular_beat"
    BLOCK = "block"
    UNKNOWN = "unknown"


@dataclass
class ECGAnalysis:
    """Análisis completo de ECG"""
    heart_rate: float
    hrv: float
    rhythm: CardiacRhythm
    st_segment: str
    t_wave: str
    qrs_duration: float
    pr_interval: float
    qt_interval: float
    risk_score: float
    interpretation: str


class ECGEngine:
    """Motor de análisis de ECG"""
    
    def __init__(self):
        self.sampling_rate = 250.0
        self.qrs_threshold = 0.5
        
    def detect_r_peaks(self, ecg_signal: np.ndarray) -> np.ndarray:
        """Detecta picos R en el ECG"""
        # Filtrado simple
        filtered = self._filter_signal(ecg_signal)
        
        # Detección de picos
        peaks = []
        for i in range(1, len(filtered) - 1):
            if filtered[i] > self.qrs_threshold and filtered[i] > filtered[i-1] and filtered[i] > filtered[i+1]:
                peaks.append(i)
        
        return np.array(peaks)
    
    def _filter_signal(self, signal: np.ndarray) -> np.ndarray:
        """Filtro simple de media móvil"""
        window = 5
        filtered = np.convolve(signal, np.ones(window)/window, mode='same')
        return np.abs(filtered)
    
    def calculate_heart_rate(self, r_peaks: np.ndarray) -> float:
        """Calcula FC desde picos R"""
        if len(r_peaks) < 2:
            return 0.0
        
        rr_intervals = np.diff(r_peaks) / self.sampling_rate
        heart_rate = 60.0 / np.mean(rr_intervals)
        return heart_rate
    
    def calculate_hrv(self, r_peaks: np.ndarray) -> float:
        """Calcula HRV (desviación estándar de intervalos RR)"""
        if len(r_peaks) < 2:
            return 0.0
        
        rr_intervals = np.diff(r_peaks) / self.sampling_rate * 1000  # en ms
        hrv = np.std(rr_intervals)
        return hrv
    
    def detect_arrhythmia(self, r_peaks: np.ndarray) -> CardiacRhythm:
        """Detecta tipo de arritmia"""
        if len(r_peaks) < 2:
            return CardiacRhythm.UNKNOWN
        
        hr = self.calculate_heart_rate(r_peaks)
        
        # Lógica simple de clasificación
        if hr > 100:
            return CardiacRhythm.SINUS_TACHYCARDIA
        elif hr < 60:
            return CardiacRhythm.SINUS_BRADYCARDIA
        else:
            # Análisis de regularidad
            rr_intervals = np.diff(r_peaks)
            regularity = np.std(rr_intervals) / np.mean(rr_intervals)
            
            if regularity > 0.3:
                return CardiacRhythm.ATRIAL_FIBRILLATION
            else:
                return CardiacRhythm.NORMAL_SINUS
    
    def analyze(self, ecg_signal: np.ndarray) -> ECGAnalysis:
        """Análisis completo de ECG"""
        r_peaks = self.detect_r_peaks(ecg_signal)
        hr = self.calculate_heart_rate(r_peaks)
        hrv = self.calculate_hrv(r_peaks)
        rhythm = self.detect_arrhythmia(r_peaks)
        
        # Estimaciones simples
        qrs_duration = 0.08
        pr_interval = 0.16
        qt_interval = 0.40
        
        # Risk score
        risk = 0.0
        if rhythm != CardiacRhythm.NORMAL_SINUS:
            risk += 0.3
        if hr > 120 or hr < 50:
            risk += 0.2
        if hrv < 20:
            risk += 0.15
        
        interpretation = self._interpret_ecg(rhythm, hr, hrv)
        
        return ECGAnalysis(
            heart_rate=hr,
            hrv=hrv,
            rhythm=rhythm,
            st_segment="normal",
            t_wave="normal",
            qrs_duration=qrs_duration,
            pr_interval=pr_interval,
            qt_interval=qt_interval,
            risk_score=min(1.0, risk),
            interpretation=interpretation
        )
    
    def _interpret_ecg(self, rhythm: CardiacRhythm, hr: float, hrv: float) -> str:
        """Genera interpretación clínica"""
        if rhythm == CardiacRhythm.NORMAL_SINUS:
            return f"Ritmo sinusal normal. FC={hr:.0f} bpm, HRV={hrv:.1f} ms"
        elif rhythm == CardiacRhythm.SINUS_TACHYCARDIA:
            return f"Taquicardia sinusal. FC={hr:.0f} bpm"
        elif rhythm == CardiacRhythm.SINUS_BRADYCARDIA:
            return f"Bradicardia sinusal. FC={hr:.0f} bpm"
        elif rhythm == CardiacRhythm.ATRIAL_FIBRILLATION:
            return f"Fibrilación auricular. FC promedio={hr:.0f} bpm"
        else:
            return f"Ritmo irregular detectado. FC={hr:.0f} bpm"


@dataclass
class EEGAnalysis:
    """Análisis de EEG"""
    attention: float  # 0-100%
    mental_workload: float
    cognitive_fatigue: float
    relaxation_level: float
    stress_level: float
    sleepiness: float
    dominant_frequency: float
    brain_state: str
    interpretation: str


class EEGEngine:
    """Motor de análisis de EEG"""
    
    def __init__(self):
        self.sampling_rate = 250.0
        self.freq_bands = {
            'delta': (0.5, 4),
            'theta': (4, 8),
            'alpha': (8, 12),
            'beta': (12, 30),
            'gamma': (30, 50),
        }
    
    def compute_band_power(self, signal: np.ndarray) -> Dict[str, float]:
        """Calcula potencia en cada banda de frecuencia"""
        # FFT simple
        fft = np.abs(np.fft.fft(signal))
        freqs = np.fft.fftfreq(len(signal), 1/self.sampling_rate)
        
        power = {}
        for band, (low, high) in self.freq_bands.items():
            mask = (freqs >= low) & (freqs <= high)
            power[band] = np.sum(fft[mask]) / len(signal)
        
        return power
    
    def detect_cognitive_state(self, band_power: Dict[str, float]) -> str:
        """Detecta estado cognitivo desde bandas"""
        alpha = band_power.get('alpha', 0)
        beta = band_power.get('beta', 0)
        theta = band_power.get('theta', 0)
        
        if alpha > beta:
            return "relaxed"
        elif beta > alpha and alpha > theta:
            return "focused"
        elif theta > alpha:
            return "drowsy"
        else:
            return "unknown"
    
    def analyze(self, eeg_signal: np.ndarray) -> EEGAnalysis:
        """Análisis completo de EEG"""
        band_power = self.compute_band_power(eeg_signal)
        state = self.detect_cognitive_state(band_power)
        
        # Cálculos de métricas
        alpha = band_power['alpha']
        beta = band_power['beta']
        theta = band_power['theta']
        
        attention = min(100, (beta / (beta + alpha) * 100)) if (beta + alpha) > 0 else 50
        relaxation = min(100, (alpha / (alpha + beta + theta) * 100)) if (alpha + beta + theta) > 0 else 50
        sleepiness = min(100, (theta / (theta + alpha) * 100)) if (theta + alpha) > 0 else 20
        
        return EEGAnalysis(
            attention=attention,
            mental_workload=100 - relaxation,
            cognitive_fatigue=sleepiness * 0.5,
            relaxation_level=relaxation,
            stress_level=100 - relaxation,
            sleepiness=sleepiness,
            dominant_frequency=8.0,  # Simplificado
            brain_state=state,
            interpretation=f"Estado: {state}. Atención: {attention:.0f}%, Relajación: {relaxation:.0f}%"
        )


@dataclass
class EMGAnalysis:
    """Análisis de EMG"""
    rms_amplitude: float
    fatigue_index: float
    activation_level: float
    recruitment_pattern: str
    efficiency: float
    interpretation: str


class EMGEngine:
    """Motor de análisis de EMG"""
    
    def __init__(self):
        self.sampling_rate = 1000.0
    
    def calculate_rms(self, signal: np.ndarray) -> float:
        """Calcula RMS del signal (amplitud efectiva)"""
        return np.sqrt(np.mean(signal ** 2))
    
    def calculate_fatigue_index(self, signal: np.ndarray) -> float:
        """Calcula índice de fatiga"""
        # Dividir en ventanas
        window_size = int(self.sampling_rate / 10)  # 100ms
        if len(signal) < window_size * 2:
            return 0.0
        
        windows = [signal[i:i+window_size] for i in range(0, len(signal)-window_size, window_size)]
        if len(windows) < 2:
            return 0.0
        
        rms_values = [self.calculate_rms(w) for w in windows]
        
        # Fatiga: disminución de RMS con el tiempo (simplificado)
        fatigue = max(0, (rms_values[0] - rms_values[-1]) / rms_values[0]) * 100 if rms_values[0] > 0 else 0
        return min(100, fatigue)
    
    def analyze(self, emg_signal: np.ndarray) -> EMGAnalysis:
        """Análisis completo de EMG"""
        rms = self.calculate_rms(emg_signal)
        fatigue = self.calculate_fatigue_index(emg_signal)
        
        # Normalización simple (asumir máximo de 100 microvolts)
        activation = min(100, (rms / 100) * 100)
        
        return EMGAnalysis(
            rms_amplitude=rms,
            fatigue_index=fatigue,
            activation_level=activation,
            recruitment_pattern="normal" if activation < 50 else "high",
            efficiency=100 - fatigue,
            interpretation=f"Activación: {activation:.0f}%, Fatiga: {fatigue:.0f}%"
        )


@dataclass
class RespiratoryAnalysis:
    """Análisis de respiración"""
    respiratory_rate: float
    breathing_pattern: str
    ventilation_quality: float
    apnea_risk: float
    hypoxia_risk: float
    interpretation: str


class RespiratoryEngine:
    """Motor de análisis respiratorio"""
    
    def __init__(self):
        self.sampling_rate = 100.0
    
    def detect_breath_peaks(self, respiratory_signal: np.ndarray) -> np.ndarray:
        """Detecta picos de inspiración"""
        filtered = np.convolve(respiratory_signal, np.ones(5)/5, mode='same')
        
        peaks = []
        for i in range(1, len(filtered) - 1):
            if filtered[i] > filtered[i-1] and filtered[i] > filtered[i+1]:
                peaks.append(i)
        
        return np.array(peaks)
    
    def calculate_respiratory_rate(self, peaks: np.ndarray, duration: float) -> float:
        """Calcula frecuencia respiratoria"""
        if len(peaks) < 2:
            return 0.0
        
        # Contar respiraciones en la duración
        breaths = len(peaks)
        rr = (breaths / duration) * 60
        return rr
    
    def analyze(self, respiratory_signal: np.ndarray, duration: float = 10.0) -> RespiratoryAnalysis:
        """Análisis completo de respiración"""
        peaks = self.detect_breath_peaks(respiratory_signal)
        rr = self.calculate_respiratory_rate(peaks, duration)
        
        # Análisis de regularidad
        if len(peaks) > 2:
            intervals = np.diff(peaks)
            regularity = np.std(intervals) / np.mean(intervals) if np.mean(intervals) > 0 else 1
            pattern = "irregular" if regularity > 0.3 else "regular"
        else:
            pattern = "unknown"
        
        # Calidad de ventilación
        ventilation = min(100, (rr / 20 * 100)) if rr > 0 else 0
        
        return RespiratoryAnalysis(
            respiratory_rate=rr,
            breathing_pattern=pattern,
            ventilation_quality=ventilation,
            apnea_risk=5.0 if pattern == "regular" else 25.0,
            hypoxia_risk=10.0,
            interpretation=f"FR: {rr:.0f} resp/min, Patrón: {pattern}, Ventilación: {ventilation:.0f}%"
        )


@dataclass
class PPGAnalysis:
    """Análisis de PPG/SpO2"""
    spo2: float
    pulse_rate: float
    perfusion_index: float
    vascular_tone: float
    blood_pressure_estimate: str
    interpretation: str


class PPGEngine:
    """Motor de análisis de PPG y SpO2"""
    
    def __init__(self):
        self.sampling_rate = 100.0
    
    def detect_pulse(self, ppg_signal: np.ndarray) -> np.ndarray:
        """Detecta pulsaciones en la señal PPG"""
        # Normalizar
        signal_norm = (ppg_signal - np.min(ppg_signal)) / (np.max(ppg_signal) - np.min(ppg_signal))
        
        # Filtrar
        filtered = np.convolve(signal_norm, np.ones(5)/5, mode='same')
        
        # Detectar picos
        threshold = np.mean(filtered) + 0.5 * np.std(filtered)
        peaks = []
        
        for i in range(1, len(filtered) - 1):
            if filtered[i] > threshold and filtered[i] > filtered[i-1] and filtered[i] > filtered[i+1]:
                peaks.append(i)
        
        return np.array(peaks)
    
    def estimate_spo2(self, ppg_signal: np.ndarray) -> float:
        """Estima SpO2 desde PPG (simplificado)"""
        # En realidad se necesitaría señal infrarroja y roja
        # Aquí hacemos una estimación simple
        signal_quality = 1 - (np.std(ppg_signal) / (np.max(ppg_signal) - np.min(ppg_signal)))
        spo2 = 95 + (signal_quality * 5)
        return min(100, max(85, spo2))
    
    def analyze(self, ppg_signal: np.ndarray) -> PPGAnalysis:
        """Análisis completo de PPG"""
        peaks = self.detect_pulse(ppg_signal)
        pulse_rate = (len(peaks) / len(ppg_signal)) * self.sampling_rate * 60 if len(ppg_signal) > 0 else 0
        spo2 = self.estimate_spo2(ppg_signal)
        
        # Estimaciones
        perfusion = min(100, (np.max(ppg_signal) - np.min(ppg_signal)) / np.max(ppg_signal) * 100) if np.max(ppg_signal) > 0 else 50
        
        return PPGAnalysis(
            spo2=spo2,
            pulse_rate=pulse_rate,
            perfusion_index=perfusion,
            vascular_tone="normal" if perfusion > 50 else "reduced",
            blood_pressure_estimate="normal",
            interpretation=f"SpO₂: {spo2:.1f}%, FC: {pulse_rate:.0f} bpm, Perfusión: {perfusion:.0f}%"
        )
