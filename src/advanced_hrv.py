"""
Análisis Avanzado de Variabilidad de Frecuencia Cardíaca (HRV)

Proporciona métricas clínicas avanzadas para evaluación
del sistema nervioso autónomo y estado de salud cardiovascular.
"""

from typing import Dict, Tuple
import numpy as np
from scipy.integrate import trapezoid
from scipy.signal import welch


class AnalisisHRVAvanzado:
    """
    Análisis clínico avanzado de HRV.
    
    Cubre:
    - Dominio temporal
    - Dominio de frecuencia
    - Medidas no-lineales
    """

    @staticmethod
    def metricas_temporales(intervalos_rr: np.ndarray) -> Dict[str, float]:
        """
        Calcula métricas de HRV en dominio temporal.
        
        Parámetros
        ----------
        intervalos_rr : ndarray
            Intervalos RR en segundos
            
        Retorna
        -------
        dict
            Métricas temporales clínicas
        """
        if len(intervalos_rr) < 10:
            return {}

        rr_ms = intervalos_rr * 1000  # Convertir a ms

        return {
            'SDNN': np.std(rr_ms),  # Desviación estándar de todos los NN
            'SDANN': np.std([np.mean(rr_ms[i:i+300]) for i in range(0, len(rr_ms)-300, 300)]),  # SDNN de promedios de 5min
            'RMSSD': np.sqrt(np.mean(np.diff(rr_ms) ** 2)),  # Raíz cuadrada del promedio de diferencias al cuadrado
            'pNN50': 100 * np.sum(np.abs(np.diff(rr_ms)) > 50) / len(rr_ms),  # Porcentaje de diferencias > 50ms
            'pNN20': 100 * np.sum(np.abs(np.diff(rr_ms)) > 20) / len(rr_ms),  # Porcentaje de diferencias > 20ms
            'HR_max': 60000 / np.min(rr_ms),
            'HR_min': 60000 / np.max(rr_ms),
            'HR_media': np.mean(60000 / rr_ms),
            'TINN': np.ptp(rr_ms),  # Rango
        }

    @staticmethod
    def metricas_frecuencia(intervalos_rr: np.ndarray, fs: float = 4.0) -> Dict[str, float]:
        """
        Calcula métricas en dominio de frecuencia (PSD).
        
        Parámetros
        ----------
        intervalos_rr : ndarray
            Intervalos RR
        fs : float
            Frecuencia de muestreo
            
        Retorna
        -------
        dict
            Potencia en bandas de frecuencia
        """
        from scipy import signal

        # Interpolar a fs constante
        t_original = np.cumsum(intervalos_rr)
        t_interpolado = np.arange(0, t_original[-1], 1/fs)
        rr_interpolado = np.interp(t_interpolado, t_original, intervalos_rr)

        # PSD usando Welch
        freqs, pxx = signal.welch(rr_interpolado, fs=fs, nperseg=256)

        # Bandas de frecuencia
        vlf = (0.0033, 0.04)  # Muy baja frecuencia
        lf = (0.04, 0.15)     # Baja frecuencia
        hf = (0.15, 0.4)      # Alta frecuencia

        vlf_pow = trapezoid(pxx[(freqs >= vlf[0]) & (freqs < vlf[1])], freqs[(freqs >= vlf[0]) & (freqs < vlf[1])])
        lf_pow = trapezoid(pxx[(freqs >= lf[0]) & (freqs < lf[1])], freqs[(freqs >= lf[0]) & (freqs < lf[1])])
        hf_pow = trapezoid(pxx[(freqs >= hf[0]) & (freqs < hf[1])], freqs[(freqs >= hf[0]) & (freqs < hf[1])])

        return {
            'VLF_potencia': vlf_pow,
            'LF_potencia': lf_pow,
            'HF_potencia': hf_pow,
            'LF_norm': 100 * lf_pow / (lf_pow + hf_pow),
            'HF_norm': 100 * hf_pow / (lf_pow + hf_pow),
            'LF_HF': lf_pow / hf_pow if hf_pow > 0 else 0,
            'potencia_total': vlf_pow + lf_pow + hf_pow
        }

    @staticmethod
    def indice_entropia_aproximada(intervalos_rr: np.ndarray, m: int = 2, r: float = 0.2) -> float:
        """
        Calcula la entropía aproximada (ApEn).
        
        Mide la previsibilidad/regularidad de la serie RR.
        Valores altos = menos predecible = más salud
        """
        rr = intervalos_rr / np.std(intervalos_rr)
        N = len(rr)

        def maxdist(x_i, x_j):
            return max(abs(ua - va) for ua, va in zip(x_i, x_j))

        def phi(m):
            patterns = np.array([[rr[j] for j in range(i, i + m)] for i in range(N - m + 1)])
            C = [len(np.where(np.array([maxdist(patterns[i], patterns[j]) <= r for j in range(len(patterns))]))[0]) / (N - m + 1.0) for i in range(len(patterns))]
            return (N - m + 1.0) ** (-1) * np.sum(np.log(C))

        return abs(phi(m) - phi(m + 1))

    @staticmethod
    def analisis_poincare(intervalos_rr: np.ndarray) -> Dict[str, float]:
        """
        Análisis de Poincaré (gráfico de dispersión RR).
        
        Características geométricas que reflejan autonomía nerviosa.
        """
        rr1 = intervalos_rr[:-1]
        rr2 = intervalos_rr[1:]

        # Ejes de la elipse de Poincaré
        sd1 = np.std(rr2 - rr1) / np.sqrt(2)
        sd2 = np.std(rr1 + rr2) / np.sqrt(2)

        return {
            'SD1': sd1,  # Eje corto (refleja HF - parasimpático)
            'SD2': sd2,  # Eje largo (refleja actividad total)
            'SD1_SD2_ratio': sd1 / sd2,
            'elipse_area': np.pi * sd1 * sd2
        }

    @staticmethod
    def dimensionalidad_fractal(intervalos_rr: np.ndarray) -> float:
        """
        Análisis de escalas múltiples (DFA).
        
        Caracteriza la complejidad auto-similar de la serie RR.
        """
        # Integración
        y = np.cumsum(intervalos_rr - np.mean(intervalos_rr))

        # Ventanas de análisis
        scales = np.logspace(0, 2.3, 20, dtype=int)
        fluctuations = []

        for scale in scales:
            fluctuation = []
            for i in range(0, len(y), scale):
                segment = y[i:i+scale]
                if len(segment) >= 4:
                    coeffs = np.polyfit(range(len(segment)), segment, 2)
                    fit = np.polyval(coeffs, range(len(segment)))
                    fluctuation.append(np.sqrt(np.mean((segment - fit) ** 2)))
            if fluctuation:
                fluctuations.append(np.mean(fluctuation))

        # Pendiente en escala log-log
        if len(fluctuations) > 2:
            alpha = np.polyfit(np.log(scales[:len(fluctuations)]), np.log(fluctuations), 1)[0]
            return alpha
        return 1.0


def generar_reporte_hrv_completo(intervalos_rr: np.ndarray, fs: float = 4.0) -> str:
    """Genera reporte completo de análisis HRV avanzado."""
    analizador = AnalisisHRVAvanzado()

    metricas_temp = analizador.metricas_temporales(intervalos_rr)
    metricas_freq = analizador.metricas_frecuencia(intervalos_rr, fs)
    entropia = analizador.indice_entropia_aproximada(intervalos_rr)
    poincare = analizador.analisis_poincare(intervalos_rr)
    dfa = analizador.dimensionalidad_fractal(intervalos_rr)

    reporte = f"""
╔═════════════════════════════════════════════════════════════════╗
║     REPORTE CLÍNICO AVANZADO DE VARIABILIDAD CARDÍACA (HRV)    ║
╚═════════════════════════════════════════════════════════════════╝

1️⃣  MÉTRICAS TEMPORALES (Dominio del Tiempo)
─────────────────────────────────────────────────────────────────

SDNN (ms): {metricas_temp.get('SDNN', 0):.2f}
   → Variabilidad general de la frecuencia cardíaca
   → Valor normal: > 50 ms (buena salud autonómica)
   → Bajo SDNN: indica estrés o disfunción

SDANN (ms): {metricas_temp.get('SDANN', 0):.2f}
   → Variabilidad a largo plazo

RMSSD (ms): {metricas_temp.get('RMSSD', 0):.2f}
   → Variabilidad latido a latido (tono parasimpático)
   → Valor normal: > 25 ms
   → Refleja actividad del nervio vago

pNN50 (%): {metricas_temp.get('pNN50', 0):.2f}
   → Porcentaje de cambios > 50ms entre latidos
   → Indica actividad parasimpática

HR Media (bpm): {metricas_temp.get('HR_media', 0):.1f}
   → Frecuencia cardíaca promedio
HR Máxima (bpm): {metricas_temp.get('HR_max', 0):.1f}
HR Mínima (bpm): {metricas_temp.get('HR_min', 0):.1f}

───────────────────────────────────────────────────────────────────

2️⃣  MÉTRICAS DE FRECUENCIA (Dominio Espectral)
─────────────────────────────────────────────────────────────────

Potencia Total (ms²): {metricas_freq.get('potencia_total', 0):.2f}
   → Energía total en toda la serie RR

VLF Potencia (ms²): {metricas_freq.get('VLF_potencia', 0):.2f}
   → Banda 0.0033-0.04 Hz
   → Refleja regulación hormonal y vasomotora

LF Potencia (ms²): {metricas_freq.get('LF_potencia', 0):.2f}
   → Banda 0.04-0.15 Hz
   → Refleja actividad simpática + parasimpática
   → LF normalizado: {metricas_freq.get('LF_norm', 0):.1f}%

HF Potencia (ms²): {metricas_freq.get('HF_potencia', 0):.2f}
   → Banda 0.15-0.4 Hz
   → Refleja actividad parasimpática (vago)
   → HF normalizado: {metricas_freq.get('HF_norm', 0):.1f}%

LF/HF Ratio: {metricas_freq.get('LF_HF', 0):.2f}
   → Balance simpático-parasimpático
   → Ratio > 3: dominancia simpática (estrés)
   → Ratio < 1: dominancia parasimpática (descanso)
   → Ratio 1-2: balance óptimo

───────────────────────────────────────────────────────────────────

3️⃣  MEDIDAS NO-LINEALES (Complejidad Cardiovascular)
─────────────────────────────────────────────────────────────────

Entropía Aproximada: {entropia:.4f}
   → Mide complejidad y previsibilidad
   → Valor alto: patrón más complejo/menos predecible (más salud)
   → Valor bajo: patrón regular/predecible (puede indicar estrés)

Análisis de Poincaré:
   SD1 (ms): {poincare.get('SD1', 0):.3f}
      → Variabilidad a corto plazo (HF parasimpática)
   SD2 (ms): {poincare.get('SD2', 0):.3f}
      → Variabilidad a largo plazo
   SD1/SD2: {poincare.get('SD1_SD2_ratio', 0):.3f}
      → Ratio de variabilidades
   Área Elipse (ms²): {poincare.get('elipse_area', 0):.2f}
      → Indica variabilidad general

Exponente de Escalas Múltiples (DFA Alpha): {dfa:.2f}
   → Mide auto-similaridad fractal
   → Valor ~1.0: sistema en balance (saludable)
   → Valor < 0.5: exceso de regulación
   → Valor > 1.5: pérdida de regulación

───────────────────────────────────────────────────────────────────

📊 INTERPRETACIÓN CLÍNICA

Estado Autonómico:
{f"✓ Balance favorable (balance simpático-parasimpático)" if metricas_freq.get('LF_HF', 0) < 2.5 else "⚠️ Tendencia a dominancia simpática (estrés relativo)"}

Regulación Cardiovascular:
{f"✓ Buena capacidad adaptativa" if entropia > 1.0 else "⚠️ Capacidad adaptativa reducida"}

Pronóstico:
{f"✓ Patrones favorables" if metricas_temp.get('RMSSD', 0) > 30 else "⚠️ Requiere evaluación"}

───────────────────────────────────────────────────────────────────

⚠️ NOTA: Este análisis es educativo. Para evaluación clínica
completa, consultar profesional de cardiología.

═════════════════════════════════════════════════════════════════
"""
    return reporte
