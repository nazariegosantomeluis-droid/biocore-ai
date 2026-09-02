"""
BIOCORE AI — HRV (HEART RATE VARIABILITY) ENGINE

Motor especializado de análisis de Variabilidad de Frecuencia Cardíaca (HRV).

Implementa análisis temporal, frecuencial y no-lineal de HRV para:
- Evaluar función autonómica
- Detección de estrés y recuperación
- Predicción de riesgos cardiovasculares
- Análisis de respuesta fisiológica

Referencia: JACC Clinical Electrophysiology, ESC Heart Failure Guidelines
"""

from dataclasses import dataclass
from typing import Dict, Tuple, List, Optional
from enum import Enum
import numpy as np
from scipy import signal


class AutonomicState(Enum):
    """Estados autonómicos detectables"""
    SYMPATHETIC_DOMINANT = "sympathetic_dominant"  # Estrés, alerta
    PARASYMPATHETIC_DOMINANT = "parasympathetic_dominant"  # Relajación, recuperación
    BALANCED = "balanced"  # Estado óptimo
    DYSREGULATED = "dysregulated"  # Disfunción autonómica
    UNKNOWN = "unknown"


@dataclass
class HRVMetrics:
    """Métricas completas de HRV"""
    # TEMPORAL (Time Domain)
    mean_rr: float  # Promedio de intervalos RR (ms)
    sdnn: float  # Desviación estándar de RR (ms) - medida general de variabilidad
    sdann: float  # SD de promedios de RR en segmentos de 5 min
    rmssd: float  # Raíz cuadrada del promedio de diferencias cuadradas RR (ms)
    pnn50: float  # Porcentaje de intervalos RR que difieren >50 ms del anterior
    pnn20: float  # Porcentaje de intervalos RR que difieren >20 ms
    
    # FRECUENCIAL (Frequency Domain)
    vlf: float  # Very Low Frequency (0.0033-0.04 Hz) - actividad vagal muy baja
    lf: float  # Low Frequency (0.04-0.15 Hz) - simpático/parasimpático
    hf: float  # High Frequency (0.15-0.40 Hz) - actividad vagal
    lfhf_ratio: float  # LF/HF - balance simpático/parasimpático
    total_power: float
    
    # NO-LINEAL (Nonlinear Domain)
    dfa_alpha1: float  # Detrended Fluctuation Analysis - corto plazo
    dfa_alpha2: float  # DFA - largo plazo
    sample_entropy: float  # Complejidad de la serie RR
    poincare_sd1: float  # Variabilidad instantánea (relacionada a RMSSD)
    poincare_sd2: float  # Variabilidad de largo plazo (relacionada a SDNN)
    poincare_ratio: float  # SD1/SD2 ratio
    
    # INTEGRADOS
    stress_index: float  # 0-100, mayor = más estrés
    recovery_index: float  # 0-100, mayor = mejor recuperación
    autonomic_balance: float  # -1 a 1, donde >0 es parasimpático
    health_score: float  # 0-100, índice de salud cardiovascular
    
    # ESTADO Y RIESGO
    autonomic_state: AutonomicState
    risk_score: float  # 0-100, riesgo cardiovascular


class HRVEngine:
    """Motor de análisis avanzado de HRV"""
    
    def __init__(self, sampling_rate: float = 250.0):
        """Inicializa motor HRV"""
        self.sampling_rate = sampling_rate
        self.min_window = 60  # Mínimo 60 segundos de datos
        
    def detect_r_peaks_from_ecg(self, ecg_signal: np.ndarray) -> np.ndarray:
        """Detecta picos R en ECG para calcular intervalos RR"""
        # Filtro simple
        filtered = np.convolve(ecg_signal, np.ones(5)/5, mode='same')
        
        # Detección de picos
        threshold = np.mean(filtered) + 2 * np.std(filtered)
        peaks = []
        
        for i in range(1, len(filtered) - 1):
            if filtered[i] > threshold and filtered[i] > filtered[i-1] and filtered[i] > filtered[i+1]:
                peaks.append(i)
        
        return np.array(peaks)
    
    def calculate_rr_intervals(self, r_peaks: np.ndarray) -> np.ndarray:
        """Calcula intervalos RR en milisegundos"""
        if len(r_peaks) < 2:
            return np.array([])
        
        rr_intervals = np.diff(r_peaks) / (self.sampling_rate / 1000)
        return rr_intervals
    
    # =====================================================================
    # TEMPORAL DOMAIN METRICS
    # =====================================================================
    
    def compute_temporal_metrics(self, rr_intervals: np.ndarray) -> Dict[str, float]:
        """Calcula todas las métricas en dominio temporal"""
        if len(rr_intervals) < 10:
            return {}
        
        # Filtrar intervalos anómalos (artefactos)
        rr_intervals = self._filter_outliers(rr_intervals)
        
        if len(rr_intervals) < 10:
            return {}
        
        metrics = {
            'mean_rr': np.mean(rr_intervals),
            'sdnn': np.std(rr_intervals),  # Desviación estándar
            'sdann': self._calculate_sdann(rr_intervals),  # SD de medias en bloques
            'rmssd': np.sqrt(np.mean(np.diff(rr_intervals) ** 2)),  # RMS de diferencias
            'pnn50': self._calculate_pnnx(rr_intervals, 50),  # % intervalos que difieren >50ms
            'pnn20': self._calculate_pnnx(rr_intervals, 20),  # % intervalos que difieren >20ms
        }
        
        return metrics
    
    def _filter_outliers(self, rr_intervals: np.ndarray, deviation: float = 2.5) -> np.ndarray:
        """Elimina intervalos anómalos (artefactos)"""
        mean = np.mean(rr_intervals)
        std = np.std(rr_intervals)
        lower = mean - deviation * std
        upper = mean + deviation * std
        
        return rr_intervals[(rr_intervals > lower) & (rr_intervals < upper)]
    
    def _calculate_sdann(self, rr_intervals: np.ndarray, block_size: int = 300) -> float:
        """Calcula desviación estándar de medias en bloques de 5 minutos"""
        n_blocks = max(1, len(rr_intervals) // block_size)
        if n_blocks == 1:
            return 0.0
        
        block_means = []
        for i in range(n_blocks):
            start = i * block_size
            end = min(start + block_size, len(rr_intervals))
            block_mean = np.mean(rr_intervals[start:end])
            block_means.append(block_mean)
        
        return np.std(block_means)
    
    def _calculate_pnnx(self, rr_intervals: np.ndarray, threshold: float) -> float:
        """Calcula porcentaje de intervalos RR que difieren más que threshold del anterior"""
        if len(rr_intervals) < 2:
            return 0.0
        
        diffs = np.abs(np.diff(rr_intervals))
        count = np.sum(diffs > threshold)
        return (count / len(diffs)) * 100
    
    # =====================================================================
    # FREQUENCY DOMAIN METRICS (Welch's Method)
    # =====================================================================
    
    def compute_frequency_metrics(self, rr_intervals: np.ndarray) -> Dict[str, float]:
        """Calcula métricas en dominio frecuencial usando Welch PSD"""
        if len(rr_intervals) < 20:
            return {}
        
        # Interpolar para tener serie regular
        rr_regular = self._interpolate_rr(rr_intervals)
        
        if len(rr_regular) < 64:
            return {}
        
        # Welch Power Spectral Density
        freqs, psd = signal.welch(rr_regular, fs=4.0, nperseg=min(256, len(rr_regular)))
        
        # Definir bandas
        vlf_band = (freqs >= 0.0033) & (freqs < 0.04)
        lf_band = (freqs >= 0.04) & (freqs < 0.15)
        hf_band = (freqs >= 0.15) & (freqs <= 0.4)
        
        vlf = np.trapz(psd[vlf_band], freqs[vlf_band]) if np.any(vlf_band) else 0
        lf = np.trapz(psd[lf_band], freqs[lf_band]) if np.any(lf_band) else 0
        hf = np.trapz(psd[hf_band], freqs[hf_band]) if np.any(hf_band) else 0
        
        total_power = vlf + lf + hf
        
        lfhf_ratio = (lf / (hf + 1e-6)) if hf > 0 else 0
        
        metrics = {
            'vlf': vlf,
            'lf': lf,
            'hf': hf,
            'lfhf_ratio': lfhf_ratio,
            'total_power': total_power,
            'lf_norm': (lf / (total_power + 1e-6)) * 100,
            'hf_norm': (hf / (total_power + 1e-6)) * 100,
        }
        
        return metrics
    
    def _interpolate_rr(self, rr_intervals: np.ndarray) -> np.ndarray:
        """Interpola intervalos RR a frecuencia regular de 4 Hz"""
        # Crear timestamp de intervalos RR
        timestamps = np.cumsum(rr_intervals) / 1000  # Convertir a segundos
        
        # Nueva frecuencia de 4 Hz
        new_freq = 4.0
        new_times = np.arange(0, timestamps[-1], 1/new_freq)
        
        # Interpolación cúbica
        rr_regular = np.interp(new_times, timestamps, rr_intervals)
        
        return rr_regular
    
    # =====================================================================
    # NONLINEAR METRICS
    # =====================================================================
    
    def compute_nonlinear_metrics(self, rr_intervals: np.ndarray) -> Dict[str, float]:
        """Calcula métricas no-lineales"""
        if len(rr_intervals) < 20:
            return {}
        
        metrics = {
            'dfa_alpha1': self._calculate_dfa(rr_intervals, min_box=4, max_box=16),
            'dfa_alpha2': self._calculate_dfa(rr_intervals, min_box=16, max_box=min(64, len(rr_intervals)//4)),
            'sample_entropy': self._calculate_sample_entropy(rr_intervals, m=2, r=0.2),
        }
        
        # Poincaré plot
        poincare = self._calculate_poincare_plot(rr_intervals)
        metrics.update(poincare)
        
        return metrics
    
    def _calculate_dfa(self, signal_data: np.ndarray, min_box: int = 4, max_box: int = 64) -> float:
        """Detrended Fluctuation Analysis"""
        # Integrar la serie
        profile = np.cumsum(signal_data - np.mean(signal_data))
        
        # Calcular DFA
        box_sizes = np.logspace(np.log10(min_box), np.log10(max_box), 20, dtype=int)
        fluctuations = []
        
        for box_size in box_sizes:
            n_boxes = len(profile) // box_size
            
            fluctuation = 0
            for i in range(n_boxes):
                segment = profile[i*box_size:(i+1)*box_size]
                # Fit polinomio de grado 1
                coeffs = np.polyfit(np.arange(len(segment)), segment, 1)
                fit = np.polyval(coeffs, np.arange(len(segment)))
                fluctuation += np.mean((segment - fit) ** 2)
            
            fluctuation = np.sqrt(fluctuation / n_boxes)
            fluctuations.append(fluctuation)
        
        # Calcular pendiente en escala log-log
        log_boxes = np.log10(box_sizes)
        log_fluct = np.log10(fluctuations)
        
        alpha = np.polyfit(log_boxes, log_fluct, 1)[0]
        return alpha
    
    def _calculate_sample_entropy(self, rr_intervals: np.ndarray, m: int = 2, r: float = 0.2) -> float:
        """Sample Entropy (complejidad de la serie)"""
        N = len(rr_intervals)
        r_scaled = r * np.std(rr_intervals)
        
        # Contar patrones de longitud m
        count_m = 0
        count_m1 = 0
        
        for i in range(N - m):
            for j in range(i + 1, N - m):
                distance_m = np.max(np.abs(rr_intervals[i:i+m] - rr_intervals[j:j+m]))
                distance_m1 = np.max(np.abs(rr_intervals[i:i+m+1] - rr_intervals[j:j+m+1]))
                
                if distance_m <= r_scaled:
                    count_m += 1
                if distance_m1 <= r_scaled:
                    count_m1 += 1
        
        if count_m == 0:
            return 0.0
        
        sample_entropy = -np.log((count_m1 + 1e-6) / (count_m + 1e-6))
        return sample_entropy
    
    def _calculate_poincare_plot(self, rr_intervals: np.ndarray) -> Dict[str, float]:
        """Análisis de Poincaré plot"""
        if len(rr_intervals) < 2:
            return {}
        
        rr_n = rr_intervals[:-1]
        rr_n1 = rr_intervals[1:]
        
        # Calcular SD1 y SD2
        mean_rr = np.mean(rr_intervals)
        diff = rr_n1 - rr_n
        
        sd1 = np.sqrt(np.sum(diff ** 2) / (2 * len(diff)))
        sd2 = np.sqrt(2 * np.var(rr_intervals) - sd1 ** 2)
        
        sd1_sd2 = (sd1 / (sd2 + 1e-6)) if sd2 > 0 else 0
        
        return {
            'poincare_sd1': sd1,
            'poincare_sd2': sd2,
            'poincare_ratio': sd1_sd2,
        }
    
    # =====================================================================
    # INTEGRATED ANALYSIS
    # =====================================================================
    
    def compute_stress_index(self, freq_metrics: Dict, temporal_metrics: Dict) -> float:
        """Índice de estrés: alto LF/HF, bajo HF, alto SDNN"""
        stress = 0.0
        
        if 'lfhf_ratio' in freq_metrics:
            # LF/HF > 2 indica estrés
            lfhf_normalized = min(freq_metrics['lfhf_ratio'] / 4, 1.0)
            stress += lfhf_normalized * 40
        
        if 'hf' in freq_metrics and 'total_power' in freq_metrics:
            # HF bajo indica estrés
            if freq_metrics['total_power'] > 0:
                hf_norm = 1.0 - (freq_metrics['hf'] / (freq_metrics['total_power'] + 1e-6))
                stress += hf_norm * 30
        
        if 'rmssd' in temporal_metrics:
            # RMSSD bajo indica estrés
            rmssd_norm = max(0, 1.0 - (temporal_metrics['rmssd'] / 100))
            stress += rmssd_norm * 30
        
        return min(100, stress)
    
    def compute_recovery_index(self, freq_metrics: Dict, temporal_metrics: Dict) -> float:
        """Índice de recuperación: bajo LF/HF, alto HF, alto SDNN"""
        recovery = 0.0
        
        if 'lfhf_ratio' in freq_metrics:
            # LF/HF < 1 indica recuperación
            lfhf_normalized = max(0, 1.0 - freq_metrics['lfhf_ratio'])
            recovery += lfhf_normalized * 40
        
        if 'hf' in freq_metrics and 'total_power' in freq_metrics:
            # HF alto indica recuperación
            if freq_metrics['total_power'] > 0:
                hf_norm = freq_metrics['hf'] / (freq_metrics['total_power'] + 1e-6)
                recovery += hf_norm * 30
        
        if 'rmssd' in temporal_metrics:
            # RMSSD alto indica recuperación
            rmssd_norm = min(temporal_metrics['rmssd'] / 100, 1.0)
            recovery += rmssd_norm * 30
        
        return min(100, recovery)
    
    def determine_autonomic_state(self, freq_metrics: Dict) -> AutonomicState:
        """Determina estado autonómico basado en LF/HF"""
        if not freq_metrics or 'lfhf_ratio' not in freq_metrics:
            return AutonomicState.UNKNOWN
        
        lfhf = freq_metrics['lfhf_ratio']
        
        if lfhf > 3.0:
            return AutonomicState.SYMPATHETIC_DOMINANT
        elif lfhf < 0.5:
            return AutonomicState.PARASYMPATHETIC_DOMINANT
        elif 0.5 <= lfhf <= 3.0:
            return AutonomicState.BALANCED
        else:
            return AutonomicState.DYSREGULATED
    
    def compute_health_score(self, temporal_metrics: Dict, freq_metrics: Dict, 
                            nonlinear_metrics: Dict, stress: float) -> float:
        """Calcula puntuación general de salud HRV"""
        health = 100.0
        
        # Penalizar estrés alto
        health -= stress * 0.4
        
        # Penalizar SDNN bajo
        if 'sdnn' in temporal_metrics:
            sdnn_score = min(temporal_metrics['sdnn'] / 100, 1.0) * 20
            health += sdnn_score - 10  # Máx +10, mín -10
        
        # Penalizar HF bajo (parasimpático bajo)
        if 'hf_norm' in freq_metrics:
            hf_score = (freq_metrics['hf_norm'] / 100) * 20
            health += hf_score - 10
        
        # Penalizar Sample Entropy baja (menos complejidad)
        if 'sample_entropy' in nonlinear_metrics:
            se_score = min(nonlinear_metrics['sample_entropy'] / 3, 1.0) * 20
            health += se_score - 10
        
        return max(0, min(100, health))
    
    # =====================================================================
    # MAIN ANALYSIS METHOD
    # =====================================================================
    
    def analyze(self, rr_intervals: np.ndarray) -> HRVMetrics:
        """Análisis completo de HRV"""
        # Validar datos
        if len(rr_intervals) < 20:
            raise ValueError("Se requieren al menos 20 intervalos RR para análisis HRV")
        
        # Calcular métricas
        temporal = self.compute_temporal_metrics(rr_intervals)
        frequency = self.compute_frequency_metrics(rr_intervals)
        nonlinear = self.compute_nonlinear_metrics(rr_intervals)
        
        # Índices integrados
        stress = self.compute_stress_index(frequency, temporal)
        recovery = self.compute_recovery_index(frequency, temporal)
        autonomic_state = self.determine_autonomic_state(frequency)
        health = self.compute_health_score(temporal, frequency, nonlinear, stress)
        
        # Risk score (inverso del health score)
        risk = 100 - health
        
        # Autonomic balance (-1 a 1, donde >0 es parasimpático)
        if frequency and 'lfhf_ratio' in frequency:
            # Normalizar LF/HF a rango -1 a 1
            lfhf = frequency['lfhf_ratio']
            autonomic_balance = (1 - lfhf) / (1 + lfhf)
        else:
            autonomic_balance = 0.0
        
        return HRVMetrics(
            mean_rr=temporal.get('mean_rr', 0),
            sdnn=temporal.get('sdnn', 0),
            sdann=temporal.get('sdann', 0),
            rmssd=temporal.get('rmssd', 0),
            pnn50=temporal.get('pnn50', 0),
            pnn20=temporal.get('pnn20', 0),
            vlf=frequency.get('vlf', 0),
            lf=frequency.get('lf', 0),
            hf=frequency.get('hf', 0),
            lfhf_ratio=frequency.get('lfhf_ratio', 0),
            total_power=frequency.get('total_power', 0),
            dfa_alpha1=nonlinear.get('dfa_alpha1', 0),
            dfa_alpha2=nonlinear.get('dfa_alpha2', 0),
            sample_entropy=nonlinear.get('sample_entropy', 0),
            poincare_sd1=nonlinear.get('poincare_sd1', 0),
            poincare_sd2=nonlinear.get('poincare_sd2', 0),
            poincare_ratio=nonlinear.get('poincare_ratio', 0),
            stress_index=stress,
            recovery_index=recovery,
            autonomic_balance=autonomic_balance,
            health_score=health,
            autonomic_state=autonomic_state,
            risk_score=risk,
        )
    
    def interpret(self, metrics: HRVMetrics) -> str:
        """Interpretación clínica de HRV"""
        interpretation = f"HRV Analysis:\n"
        interpretation += f"Salud: {metrics.health_score:.0f}/100\n"
        
        if metrics.autonomic_state == AutonomicState.PARASYMPATHETIC_DOMINANT:
            interpretation += "✅ Estado parasimpático: recuperación, relajación\n"
        elif metrics.autonomic_state == AutonomicState.SYMPATHETIC_DOMINANT:
            interpretation += "⚠️ Estado simpático: estrés, alerta\n"
        elif metrics.autonomic_state == AutonomicState.BALANCED:
            interpretation += "✅ Balance autonómico normal\n"
        else:
            interpretation += "❓ Estado autonómico indeterminado\n"
        
        interpretation += f"Estrés: {metrics.stress_index:.0f}%, Recuperación: {metrics.recovery_index:.0f}%\n"
        interpretation += f"Riesgo Cardiovascular: {metrics.risk_score:.0f}%"
        
        return interpretation
