"""
UTILIDADES DE DATOS PARA INTERFAZ STREAMLIT
============================================
Genera datos realistas de pacientes y signals para demostración.
Esta es la capa de DATOS que alimenta TODA la visualización.

USO:
    from app.utils.data_generator import generate_ecg_signal, generate_sample_patient
    
    # Generar señal ECG de ejemplo
    signal = generate_ecg_signal(duration=10, sampling_rate=500)
    
    # Generar paciente completo
    patient = generate_sample_patient("Cardiology")
"""

import numpy as np
from datetime import datetime, timedelta
import json


class DataGenerator:
    """
    Generador de datos realistas para pruebas.
    IMPORTANTE: Solo para demostración. En producción usar datos reales.
    """
    
    @staticmethod
    def generate_ecg_signal(duration=10, sampling_rate=500, condition="normal"):
        """
        Genera una señal ECG sintética realista.
        
        PARÁMETROS:
        -----------
        duration : int
            Duración en segundos (default: 10)
        sampling_rate : int
            Frecuencia de muestreo Hz (default: 500)
        condition : str
            Tipo de ECG: "normal", "afib", "bradycardia", "tachycardia"
        
        RETORNO:
        --------
        dict : {
            'signal': array NumPy con valores ECG,
            'time': array con timestamps,
            'sampling_rate': tasa de muestreo,
            'condition': condición simulada
        }
        
        EJEMPLO:
        --------
        >>> ecg = DataGenerator.generate_ecg_signal(duration=10)
        >>> signal_values = ecg['signal']
        >>> time_axis = ecg['time']
        """
        
        t = np.linspace(0, duration, int(duration * sampling_rate))
        
        # Frecuencia cardíaca base (bpm)
        if condition == "normal":
            hr = 70  # Normal
        elif condition == "bradycardia":
            hr = 45  # Lento
        elif condition == "tachycardia":
            hr = 120  # Rápido
        elif condition == "afib":
            hr = 80  # Irregular
        else:
            hr = 70
        
        # Frecuencia en Hz
        freq = hr / 60
        
        # ECG básico con componente P-QRS-T
        # P: Onda P (auricular)
        p_wave = 0.5 * np.sin(2 * np.pi * (t % (1/freq)) * 5)
        
        # QRS: Complejo QRS (ventricular) - componente más fuerte
        qrs_wave = 2 * np.sin(2 * np.pi * (t % (1/freq)) * 15) * np.exp(-((t % (1/freq) - 0.4/(1/freq))**2) / 0.01)
        
        # T: Onda T (recuperación ventricular)
        t_wave = 0.8 * np.sin(2 * np.pi * (t % (1/freq)) * 3) * np.exp(-((t % (1/freq) - 0.6/(1/freq))**2) / 0.02)
        
        # Línea base
        baseline = np.sin(2 * np.pi * 0.5 * t) * 0.1
        
        # Ruido realista
        noise = np.random.normal(0, 0.05, len(t))
        
        # Combinar componentes
        if condition == "afib":
            # Agregar variabilidad irregular
            irregular = np.random.normal(0, 0.2, len(t))
            signal = p_wave + qrs_wave + t_wave + baseline + noise + irregular
        else:
            signal = p_wave + qrs_wave + t_wave + baseline + noise
        
        return {
            'signal': signal,
            'time': t,
            'sampling_rate': sampling_rate,
            'condition': condition
        }
    
    @staticmethod
    def generate_eeg_signal(duration=30, sampling_rate=256, sleep_stage="awake"):
        """
        Genera una señal EEG sintética por banda de frecuencia.
        
        PARÁMETROS:
        -----------
        duration : int
            Duración en segundos (default: 30)
        sampling_rate : int
            Frecuencia de muestreo Hz (default: 256)
        sleep_stage : str
            Estadio: "awake", "n1", "n2", "n3", "rem"
        
        RETORNO:
        --------
        dict : {
            'signal': array NumPy con valores EEG,
            'time': array con timestamps,
            'bands': dict con potencia por banda (Delta, Theta, Alpha, Beta, Gamma),
            'sleep_stage': estadio de sueño
        }
        
        BANDAS EEG (Hz):
        ----------------
        Delta:  0.5-4 Hz   (sueño profundo)
        Theta:  4-8 Hz     (somnolencia)
        Alpha:  8-12 Hz    (relajación)
        Beta:   12-30 Hz   (alerta)
        Gamma:  30-100 Hz  (cognición)
        
        EJEMPLO:
        --------
        >>> eeg = DataGenerator.generate_eeg_signal(duration=30, sleep_stage="n2")
        >>> print(eeg['bands'])
        """
        
        t = np.linspace(0, duration, int(duration * sampling_rate))
        signal = np.zeros_like(t)
        bands = {}
        
        # Generar componentes por banda según estadio
        
        if sleep_stage == "awake":
            # Despierto: Beta (12-30 Hz) dominante
            beta = 2 * np.sin(2 * np.pi * 15 * t)
            gamma = 0.5 * np.sin(2 * np.pi * 40 * t)
            signal = beta + gamma
            bands = {'Delta': 5, 'Theta': 8, 'Alpha': 12, 'Beta': 40, 'Gamma': 15}
            
        elif sleep_stage == "n1":
            # N1: Theta (4-8 Hz) aumentado
            theta = 3 * np.sin(2 * np.pi * 6 * t)
            alpha = 1 * np.sin(2 * np.pi * 10 * t)
            signal = theta + alpha
            bands = {'Delta': 10, 'Theta': 35, 'Alpha': 15, 'Beta': 25, 'Gamma': 8}
            
        elif sleep_stage == "n2":
            # N2: Theta + sleep spindles (12-14 Hz)
            theta = 4 * np.sin(2 * np.pi * 6 * t)
            spindles = 2 * np.sin(2 * np.pi * 13 * t) * np.exp(-((t % 2)**2) / 0.5)
            signal = theta + spindles
            bands = {'Delta': 15, 'Theta': 45, 'Alpha': 12, 'Beta': 20, 'Gamma': 5}
            
        elif sleep_stage == "n3":
            # N3 (Deep sleep): Delta (0.5-4 Hz) dominante (>20%)
            delta = 5 * np.sin(2 * np.pi * 2 * t)
            theta = 2 * np.sin(2 * np.pi * 6 * t)
            signal = delta + theta
            bands = {'Delta': 50, 'Theta': 25, 'Alpha': 8, 'Beta': 10, 'Gamma': 2}
            
        elif sleep_stage == "rem":
            # REM: Beta/Gamma aumentado, más similar a despierto pero con ondas mixtas
            beta = 2 * np.sin(2 * np.pi * 20 * t)
            theta = 2 * np.sin(2 * np.pi * 7 * t)
            signal = beta + theta
            bands = {'Delta': 8, 'Theta': 30, 'Alpha': 15, 'Beta': 35, 'Gamma': 20}
        
        # Agregar ruido realista
        noise = np.random.normal(0, 0.3, len(t))
        signal = signal + noise
        
        return {
            'signal': signal,
            'time': t,
            'sampling_rate': sampling_rate,
            'sleep_stage': sleep_stage,
            'bands': bands
        }
    
    @staticmethod
    def generate_emg_signal(duration=10, sampling_rate=2000, muscle_state="rest"):
        """
        Genera una señal EMG sintética (electromiografía).
        
        PARÁMETROS:
        -----------
        duration : int
            Duración en segundos
        sampling_rate : int
            Frecuencia de muestreo (2000 Hz típico para EMG)
        muscle_state : str
            Estado del músculo: "rest", "low", "medium", "high", "fatigue"
        
        RETORNO:
        --------
        dict : {
            'signal': array NumPy (raw EMG),
            'envelope': array con envolvente,
            'time': array con timestamps,
            'activation_level': nivel de activación (0-100%),
            'fatigue_level': nivel de fatiga (0-100%),
            'median_frequency': Median Frequency en Hz
        }
        
        ACTIVACIÓN MUSCULAR:
        --------------------
        Rest:    0-10% amplitud
        Low:     10-30% amplitud
        Medium:  30-60% amplitud
        High:    60-90% amplitud
        
        FATIGA: Disminución de Median Frequency durante el tiempo
        
        EJEMPLO:
        --------
        >>> emg = DataGenerator.generate_emg_signal(duration=10, muscle_state="high")
        >>> print(f"Activación: {emg['activation_level']}%")
        """
        
        t = np.linspace(0, duration, int(duration * sampling_rate))
        
        # Amplitud base según estado
        if muscle_state == "rest":
            amplitude = 0.05
            activation = 5
        elif muscle_state == "low":
            amplitude = 0.2
            activation = 20
        elif muscle_state == "medium":
            amplitude = 0.4
            activation = 50
        elif muscle_state == "high":
            amplitude = 0.7
            activation = 80
        elif muscle_state == "fatigue":
            amplitude = 0.3
            activation = 40
        else:
            amplitude = 0.1
            activation = 15
        
        # EMG es ruido de banda ancha (100-500 Hz típicamente)
        # Simular con múltiples componentes sinusoidales
        emg = np.zeros_like(t)
        
        # Componentes de frecuencia múltiples
        for freq in [150, 250, 350, 450]:
            emg += amplitude * 0.3 * np.sin(2 * np.pi * freq * t)
        
        # Agregar ruido gaussiano (principal componente EMG)
        emg += np.random.normal(0, amplitude * 0.7, len(t))
        
        # Modular amplitud en el tiempo para simular contracción
        if muscle_state != "rest":
            # Envolvente de contracción suave
            envelope_mod = 0.3 + 0.7 * (0.5 + 0.5 * np.sin(2 * np.pi * 2 * t))
            emg = emg * envelope_mod
        
        # Calcular envolvente (rectificación + filtro)
        emg_rect = np.abs(emg)
        
        # Filtro movil simple para envolvente
        window_size = int(sampling_rate * 0.02)  # ventana 20ms
        envelope = np.convolve(emg_rect, np.ones(window_size)/window_size, mode='same')
        
        # Median Frequency (disminuye con fatiga)
        if muscle_state == "fatigue":
            # Simular fatiga: disminuye MF gradualmente
            mf_base = 200
            mf_final = 120
            mf = mf_base + (mf_final - mf_base) * (t / duration)
        else:
            mf = 250
        
        return {
            'signal': emg,
            'envelope': envelope,
            'time': t,
            'sampling_rate': sampling_rate,
            'activation_level': activation,
            'fatigue_level': 80 if muscle_state == "fatigue" else 20,
            'median_frequency': float(mf),
            'muscle_state': muscle_state
        }
    
    @staticmethod
    def generate_sample_patient(specialty="Cardiology", condition="normal"):
        """
        Genera un paciente de ejemplo completo con datos realistas.
        
        PARÁMETROS:
        -----------
        specialty : str
            "Cardiology", "Neurology", o "Musculoskeletal"
        condition : str
            Condición médica del paciente
        
        RETORNO:
        --------
        dict : Información completa del paciente
        
        EJEMPLO:
        --------
        >>> patient = DataGenerator.generate_sample_patient("Cardiology", "afib")
        >>> print(patient['name'])
        >>> print(patient['measurements'])
        """
        
        # Datos demográficos
        first_names = ["Juan", "María", "Carlos", "Ana", "Luis", "Rosa"]
        last_names = ["García", "López", "Martínez", "Rodríguez", "Pérez", "Sánchez"]
        
        patient = {
            'id': f"PAC-{np.random.randint(10000, 99999)}",
            'name': f"{np.random.choice(first_names)} {np.random.choice(last_names)}",
            'age': np.random.randint(25, 85),
            'gender': np.random.choice(['M', 'F']),
            'specialty': specialty,
            'condition': condition,
            'registration_date': (datetime.now() - timedelta(days=np.random.randint(1, 365))).strftime("%Y-%m-%d"),
            'medical_history': {
                'hypertension': np.random.choice([True, False], p=[0.4, 0.6]),
                'diabetes': np.random.choice([True, False], p=[0.3, 0.7]),
                'prior_events': np.random.randint(0, 3),
            }
        }
        
        # Mediciones según especialidad
        if specialty == "Cardiology":
            patient['latest_measurement'] = {
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'ecg': DataGenerator.generate_ecg_signal(condition=condition),
                'heart_rate': np.random.randint(60, 120),
                'systolic_bp': np.random.randint(110, 160),
                'diastolic_bp': np.random.randint(70, 100),
                'oxygen_saturation': np.random.uniform(95, 100),
            }
        
        elif specialty == "Neurology":
            patient['latest_measurement'] = {
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'eeg': DataGenerator.generate_eeg_signal(sleep_stage="awake"),
                'sleep_quality': np.random.randint(40, 100),
                'headaches': np.random.choice(['None', 'Mild', 'Moderate', 'Severe']),
            }
        
        elif specialty == "Musculoskeletal":
            patient['latest_measurement'] = {
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'emg_left': DataGenerator.generate_emg_signal(muscle_state=condition),
                'emg_right': DataGenerator.generate_emg_signal(muscle_state=condition),
                'rom_left': np.random.randint(80, 120),  # Range of Motion
                'rom_right': np.random.randint(80, 120),
                'strength_left': np.random.randint(60, 100),
                'strength_right': np.random.randint(60, 100),
            }
        elif specialty == "Respiratory":
            respiratory = DataGenerator.generate_respiratory_signal(pattern="normal")
            patient['latest_measurement'] = {
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'respiratory': respiratory,
                'respiratory_rate': respiratory['respiratory_rate'],
                'tidal_volume': respiratory['tidal_volume'],
                'oxygen_saturation': respiratory['oxygen_saturation'],
                'ventilation_quality': respiratory['ventilation_quality'],
            }
        elif specialty == "Metabolism":
            metabolic = DataGenerator.generate_metabolic_profile(condition=condition)
            patient['latest_measurement'] = {
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'metabolic_profile': metabolic,
                'blood_glucose': metabolic['blood_glucose'],
                'hba1c': metabolic['hba1c'],
                'insulin_sensitivity': metabolic['insulin_sensitivity'],
                'energy_expenditure': metabolic['energy_expenditure'],
            }
        
        return patient
    
    @staticmethod
    def generate_respiratory_signal(duration=60, sampling_rate=25, pattern="normal"):
        """
        Genera una señal respiratoria sintética con métricas clínicas.
        """
        t = np.linspace(0, duration, int(duration * sampling_rate))
        base_rate = 16
        if pattern == "normal":
            respiratory_rate = 16
            tidal_volume = 500
            ventilation_quality = 92
            oxygen_saturation = 98
        elif pattern == "tachypnea":
            respiratory_rate = 24
            tidal_volume = 420
            ventilation_quality = 80
            oxygen_saturation = 94
        elif pattern == "bradypnea":
            respiratory_rate = 8
            tidal_volume = 600
            ventilation_quality = 78
            oxygen_saturation = 96
        elif pattern == "obstructed":
            respiratory_rate = 18
            tidal_volume = 450
            ventilation_quality = 68
            oxygen_saturation = 90
        else:
            respiratory_rate = 16
            tidal_volume = 500
            ventilation_quality = 90
            oxygen_saturation = 97

        freq = respiratory_rate / 60.0
        waveform = 0.5 * np.sin(2 * np.pi * freq * t) + 0.1 * np.random.normal(0, 0.05, len(t))
        signal = waveform + 0.1 * np.sin(2 * np.pi * 0.2 * t)

        return {
            'signal': signal,
            'time': t,
            'sampling_rate': sampling_rate,
            'respiratory_rate': respiratory_rate,
            'tidal_volume': tidal_volume,
            'oxygen_saturation': oxygen_saturation,
            'ventilation_quality': ventilation_quality,
            'pattern': pattern
        }

    @staticmethod
    def generate_metabolic_profile(condition="normal"):
        """
        Genera un perfil metabólico sintético y clínico.
        """
        if condition == "normal":
            blood_glucose = np.random.uniform(80, 100)
            hba1c = np.random.uniform(4.8, 5.6)
            insulin_sensitivity = np.random.uniform(70, 90)
            energy_expenditure = np.random.uniform(1800, 2200)
            lactate = np.random.uniform(0.8, 1.2)
        elif condition == "prediabetes":
            blood_glucose = np.random.uniform(100, 125)
            hba1c = np.random.uniform(5.7, 6.4)
            insulin_sensitivity = np.random.uniform(50, 70)
            energy_expenditure = np.random.uniform(1700, 2100)
            lactate = np.random.uniform(1.1, 1.8)
        elif condition == "diabetes":
            blood_glucose = np.random.uniform(126, 180)
            hba1c = np.random.uniform(6.5, 8.0)
            insulin_sensitivity = np.random.uniform(30, 55)
            energy_expenditure = np.random.uniform(1600, 2000)
            lactate = np.random.uniform(1.5, 2.5)
        else:
            blood_glucose = np.random.uniform(85, 105)
            hba1c = np.random.uniform(5.0, 5.8)
            insulin_sensitivity = np.random.uniform(60, 85)
            energy_expenditure = np.random.uniform(1750, 2150)
            lactate = np.random.uniform(1.0, 1.4)

        return {
            'blood_glucose': float(blood_glucose),
            'hba1c': float(hba1c),
            'insulin_sensitivity': float(insulin_sensitivity),
            'energy_expenditure': float(energy_expenditure),
            'lactate': float(lactate),
            'condition': condition
        }

    @staticmethod
    def generate_measurement_history(patient, days=30):
        """
        Genera historial de mediciones para visualizar tendencias.
        """
        history = []
        specialty = patient['specialty']
        
        for day in range(days):
            date = datetime.now() - timedelta(days=days-day)
            
            if specialty == "Cardiology":
                measurement = {
                    'date': date.strftime("%Y-%m-%d"),
                    'timestamp': date.strftime("%Y-%m-%d %H:%M:%S"),
                    'heart_rate': np.random.randint(60, 100) + day * np.random.uniform(-2, 2),
                    'systolic_bp': np.random.randint(110, 140) + day * np.random.uniform(-1, 1),
                    'diastolic_bp': np.random.randint(70, 90) + day * np.random.uniform(-1, 1),
                }
            elif specialty == "Neurology":
                measurement = {
                    'date': date.strftime("%Y-%m-%d"),
                    'timestamp': date.strftime("%Y-%m-%d %H:%M:%S"),
                    'sleep_quality': int(50 + 30 * np.sin(day * np.pi / 7) + np.random.randint(-10, 10)),
                    'delta_power': 30 + day * 0.1 + np.random.uniform(-5, 5),
                    'theta_power': 25 + np.random.uniform(-5, 5),
                }
            elif specialty == "Musculoskeletal":
                measurement = {
                    'date': date.strftime("%Y-%m-%d"),
                    'timestamp': date.strftime("%Y-%m-%d %H:%M:%S"),
                    'strength_level': 70 + day * 0.5 + np.random.uniform(-5, 5),
                    'median_frequency': 250 - day * 0.5 + np.random.uniform(-10, 10),
                    'fatigue_level': 30 + day * np.random.uniform(-5, 5),
                }
            elif specialty == "Respiratory":
                measurement = {
                    'date': date.strftime("%Y-%m-%d"),
                    'timestamp': date.strftime("%Y-%m-%d %H:%M:%S"),
                    'respiratory_rate': 14 + np.random.uniform(-2, 2),
                    'tidal_volume': 500 + np.random.uniform(-50, 50),
                    'oxygen_saturation': 96 + np.random.uniform(-2, 2),
                    'ventilation_quality': 85 + np.random.uniform(-5, 5),
                }
            elif specialty == "Metabolism":
                measurement = {
                    'date': date.strftime("%Y-%m-%d"),
                    'timestamp': date.strftime("%Y-%m-%d %H:%M:%S"),
                    'blood_glucose': 90 + np.random.uniform(-10, 20),
                    'hba1c': 5.2 + np.random.uniform(-0.3, 0.8),
                    'insulin_sensitivity': 75 + np.random.uniform(-15, 15),
                    'energy_expenditure': 1900 + np.random.uniform(-200, 200),
                }
            
            history.append(measurement)
        
        return history


# Funciones de conveniencia de alto nivel
def generate_ecg_signal(duration=10, sampling_rate=500, condition="normal"):
    """Genera ECG. Wrapper simple."""
    return DataGenerator.generate_ecg_signal(duration, sampling_rate, condition)

def generate_eeg_signal(duration=30, sampling_rate=256, sleep_stage="awake"):
    """Genera EEG. Wrapper simple."""
    return DataGenerator.generate_eeg_signal(duration, sampling_rate, sleep_stage)

def generate_emg_signal(duration=10, sampling_rate=2000, muscle_state="rest"):
    """Genera EMG. Wrapper simple."""
    return DataGenerator.generate_emg_signal(duration, sampling_rate, muscle_state)

def generate_respiratory_signal(duration=60, sampling_rate=25, pattern="normal"):
    """Genera señal respiratoria. Wrapper simple."""
    return DataGenerator.generate_respiratory_signal(duration, sampling_rate, pattern)

def generate_metabolic_profile(condition="normal"):
    """Genera perfil metabólico. Wrapper simple."""
    return DataGenerator.generate_metabolic_profile(condition)

def generate_sample_patient(specialty="Cardiology", condition="normal"):
    """Genera paciente. Wrapper simple."""
    return DataGenerator.generate_sample_patient(specialty, condition)

def generate_measurement_history(patient, days=30):
    """Genera historial. Wrapper simple."""
    return DataGenerator.generate_measurement_history(patient, days)
