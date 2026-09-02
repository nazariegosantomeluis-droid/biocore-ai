"""
BIOCORE AI — Simulation Engine

Motor de simulación fisiológica.
12 escenarios clínicos dinámicos.
Evolución temporal (Ahora → 5min → 30min → 2h → 24h → 7d)
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import numpy as np


class SimulationScenario(Enum):
    """12 escenarios clínicos"""
    HEALTHY = "healthy"  # Paciente sano
    EXERCISE = "exercise"  # Ejercicio
    STRESS = "stress"  # Estrés psicológico
    ANXIETY = "anxiety"  # Ansiedad
    ARRHYTHMIA = "arrhythmia"  # Arritmia cardíaca
    HYPOXIA = "hypoxia"  # Hipoxia (SpO2 bajo)
    APNEA = "apnea"  # Apnea del sueño
    FATIGUE = "fatigue"  # Fatiga crónica
    SEIZURE = "seizure"  # Epilepsia (convulsión)
    SEPSIS = "sepsis"  # Sepsis (infección sistémica)
    COPD = "copd"  # EPOC
    HYPERTENSION = "hypertension"  # Hipertensión


@dataclass
class SimulationTimestep:
    """Estado fisiológico en un timestep de simulación"""
    time_point: str  # "now", "5min", "30min", "2h", "24h", "7d"
    minutes_elapsed: int
    
    # Cardiovascular
    hr: float
    hrv: float
    cardiac_output: float
    
    # Neurological
    stress_level: float
    cognitive_state: float
    eeg_activity: float
    
    # Respiratory
    respiratory_rate: float
    spo2: float
    ahi: float  # Apnea-Hypopnea Index
    
    # Muscular
    fatigue_index: float
    muscle_activation: float
    
    # Autonomic
    sympathetic_tone: float
    parasympathetic_tone: float
    
    # Global
    global_health: float
    risk_level: float


class SimulationEngine:
    """Motor de simulación fisiológica multiescenario"""
    
    # Parámetros basales (sano)
    BASELINE_PARAMETERS = {
        "hr": 72,
        "hrv": 50,
        "respiratory_rate": 16,
        "spo2": 98,
        "stress_level": 20,
        "cognitive_state": 80,
        "fatigue_index": 10,
        "sympathetic_tone": 30,
    }
    
    # Definición de escenarios
    SCENARIO_PARAMETERS = {
        SimulationScenario.HEALTHY: {
            "hr_trend": "stable",
            "stress_trend": "low",
            "respiratory_trend": "stable",
            "fatigue_trend": "stable",
            "duration_minutes": 60,
        },
        SimulationScenario.EXERCISE: {
            "hr_trend": "high_increasing",
            "stress_trend": "moderate_increasing",
            "respiratory_trend": "high_increasing",
            "fatigue_trend": "moderate_increasing",
            "duration_minutes": 30,
            "recovery_minutes": 60,
        },
        SimulationScenario.STRESS: {
            "hr_trend": "moderate_increasing",
            "stress_trend": "high_sustained",
            "respiratory_trend": "shallow_fast",
            "fatigue_trend": "mild_increasing",
            "duration_minutes": 120,
        },
        SimulationScenario.ANXIETY: {
            "hr_trend": "tachycardia_irregular",
            "stress_trend": "very_high",
            "respiratory_trend": "hyperventilation",
            "fatigue_trend": "increasing",
            "duration_minutes": 90,
        },
        SimulationScenario.ARRHYTHMIA: {
            "hr_trend": "irregular_spikes",
            "hrv_trend": "very_low",
            "stress_trend": "high_acute",
            "respiratory_trend": "shallow",
            "fatigue_trend": "rapid",
            "duration_minutes": 60,
            "severity": "high",
        },
        SimulationScenario.HYPOXIA: {
            "spo2_trend": "decreasing",
            "hr_trend": "compensatory_tachycardia",
            "stress_trend": "increasing",
            "cognitive_trend": "decreasing",
            "duration_minutes": 120,
            "critical_threshold": 85,
        },
        SimulationScenario.APNEA: {
            "respiratory_trend": "periodic_cessation",
            "spo2_trend": "drops_periodic",
            "hr_trend": "irregular",
            "stress_trend": "high_periodic",
            "duration_minutes": 480,  # 8 hours (sleep)
        },
        SimulationScenario.FATIGUE: {
            "fatigue_trend": "persistent_high",
            "cognitive_trend": "declining",
            "stress_trend": "chronic_moderate",
            "hrv_trend": "decreasing",
            "duration_minutes": 1440,  # 24 hours
        },
        SimulationScenario.SEIZURE: {
            "cognitive_trend": "sudden_loss",
            "eeg_trend": "abnormal_spikes",
            "hr_trend": "tachycardia_severe",
            "respiratory_trend": "irregular",
            "muscular_trend": "convulsions",
            "duration_minutes": 5,
            "severity": "critical",
        },
        SimulationScenario.SEPSIS: {
            "hr_trend": "sustained_tachycardia",
            "respiratory_trend": "tachypnea",
            "spo2_trend": "declining",
            "cognitive_trend": "altered_declining",
            "stress_trend": "maximum_sustained",
            "duration_minutes": 360,
        },
        SimulationScenario.COPD: {
            "respiratory_trend": "limited_capacity",
            "spo2_trend": "low_baseline",
            "hr_trend": "elevated_baseline",
            "fatigue_trend": "high_baseline",
            "exacerbation_episodes": True,
            "duration_minutes": 1440,
        },
        SimulationScenario.HYPERTENSION: {
            "hr_trend": "elevated_sustained",
            "stress_trend": "chronic_moderate",
            "hrv_trend": "low_sustained",
            "cardiovascular_risk": "high",
            "duration_minutes": 1440,
        },
    }
    
    def __init__(self):
        self.current_scenario: Optional[SimulationScenario] = None
        self.timeline: List[SimulationTimestep] = []
        self.current_step: int = 0
    
    def simulate_scenario(
        self,
        scenario: SimulationScenario,
        initial_state: Optional[Dict] = None,
    ) -> List[SimulationTimestep]:
        """
        Simula un escenario clínico completo
        
        Args:
            scenario: Tipo de escenario
            initial_state: Estado fisiológico inicial (opcional)
        
        Returns:
            Timeline de estado fisiológico
        """
        self.current_scenario = scenario
        self.timeline = []
        
        # Combinar parámetros basales con iniciales
        state = self.BASELINE_PARAMETERS.copy()
        if initial_state:
            state.update(initial_state)
        
        # Puntos temporales a simular
        time_points = [
            ("now", 0),
            ("5min", 5),
            ("30min", 30),
            ("2h", 120),
            ("24h", 1440),
            ("7d", 10080),
        ]
        
        for time_label, minutes in time_points:
            timestep = self._compute_timestep(
                scenario,
                time_label,
                minutes,
                state,
            )
            self.timeline.append(timestep)
            state = self._update_state_from_timestep(state, timestep)
        
        return self.timeline
    
    def _compute_timestep(
        self,
        scenario: SimulationScenario,
        time_label: str,
        minutes_elapsed: int,
        base_state: Dict,
    ) -> SimulationTimestep:
        """Calcula parámetros fisiológicos para un timestep"""
        
        params = self.SCENARIO_PARAMETERS.get(scenario, {})
        
        # Aplicar modificaciones según escenario
        if scenario == SimulationScenario.HEALTHY:
            timestep = self._simulate_healthy(time_label, minutes_elapsed, base_state)
        
        elif scenario == SimulationScenario.EXERCISE:
            timestep = self._simulate_exercise(time_label, minutes_elapsed, base_state)
        
        elif scenario == SimulationScenario.STRESS:
            timestep = self._simulate_stress(time_label, minutes_elapsed, base_state)
        
        elif scenario == SimulationScenario.ANXIETY:
            timestep = self._simulate_anxiety(time_label, minutes_elapsed, base_state)
        
        elif scenario == SimulationScenario.ARRHYTHMIA:
            timestep = self._simulate_arrhythmia(time_label, minutes_elapsed, base_state)
        
        elif scenario == SimulationScenario.HYPOXIA:
            timestep = self._simulate_hypoxia(time_label, minutes_elapsed, base_state)
        
        elif scenario == SimulationScenario.APNEA:
            timestep = self._simulate_apnea(time_label, minutes_elapsed, base_state)
        
        elif scenario == SimulationScenario.FATIGUE:
            timestep = self._simulate_fatigue(time_label, minutes_elapsed, base_state)
        
        elif scenario == SimulationScenario.SEIZURE:
            timestep = self._simulate_seizure(time_label, minutes_elapsed, base_state)
        
        elif scenario == SimulationScenario.SEPSIS:
            timestep = self._simulate_sepsis(time_label, minutes_elapsed, base_state)
        
        elif scenario == SimulationScenario.COPD:
            timestep = self._simulate_copd(time_label, minutes_elapsed, base_state)
        
        elif scenario == SimulationScenario.HYPERTENSION:
            timestep = self._simulate_hypertension(time_label, minutes_elapsed, base_state)
        
        else:
            timestep = self._baseline_timestep(time_label, minutes_elapsed, base_state)
        
        return timestep
    
    # ============ SIMULADORES POR ESCENARIO ============
    
    def _simulate_healthy(self, time_label: str, minutes: int, state: Dict) -> SimulationTimestep:
        """Simulación: Paciente sano"""
        return SimulationTimestep(
            time_point=time_label,
            minutes_elapsed=minutes,
            hr=72 + np.random.normal(0, 3),
            hrv=50 + np.random.normal(0, 5),
            cardiac_output=5.0,
            stress_level=20 + np.random.normal(0, 5),
            cognitive_state=85 + np.random.normal(0, 5),
            eeg_activity=50,
            respiratory_rate=16 + np.random.normal(0, 1),
            spo2=98 + np.random.normal(0, 0.5),
            ahi=2,
            fatigue_index=10 + np.random.normal(0, 5),
            muscle_activation=40,
            sympathetic_tone=30,
            parasympathetic_tone=70,
            global_health=90,
            risk_level=5,
        )
    
    def _simulate_exercise(self, time_label: str, minutes: int, state: Dict) -> SimulationTimestep:
        """Simulación: Ejercicio"""
        # Fase activa (primeros 30 min) vs recuperación
        if minutes <= 30:
            hr = 120 + (minutes / 30) * 40  # Sube hasta 160
            rr = 25 + (minutes / 30) * 15  # Sube hasta 40
            fatigue = 20 + (minutes / 30) * 40  # Sube hasta 60
            hrv = 35  # Baja durante ejercicio
        else:
            # Bloque 4: acotado a [0,1] -- sin esto, recovery_progress crecía sin
            # límite pasados los ~90min de recuperación (a 24h daba 23.5, a 7d
            # 167.5), llevando hr muy por debajo de cero (-1908 a 24h, -14580 a
            # 7d). Lectura A (decidida): el ejercicio agudo se resuelve -- tras
            # la recuperación, HR vuelve a reposo (~72) y se queda ahí, no sigue
            # bajando. max(0.0, ...) es defensivo (minutes>30 en este branch
            # nunca da numerador negativo), no cambia nada hoy.
            recovery_progress = max(0.0, min(1.0, (minutes - 30) / 60))  # 0-1, saturado
            hr = 160 - (recovery_progress * 88)  # Vuelve a ~72 y se estabiliza ahí
            rr = 40 - (recovery_progress * 24)  # Vuelve a ~16
            fatigue = 60 - (recovery_progress * 50)  # Vuelve a ~10
            hrv = 35 + (recovery_progress * 15)  # Recupera
        
        return SimulationTimestep(
            time_point=time_label,
            minutes_elapsed=minutes,
            hr=hr,
            hrv=hrv,
            cardiac_output=6.5,
            stress_level=40 if minutes <= 30 else 25,
            cognitive_state=75,
            eeg_activity=70,
            respiratory_rate=rr,
            spo2=96,
            ahi=0,
            fatigue_index=fatigue,
            muscle_activation=90 if minutes <= 30 else 40,
            sympathetic_tone=70 if minutes <= 30 else 40,
            parasympathetic_tone=30 if minutes <= 30 else 60,
            global_health=75 if minutes <= 30 else 85,
            risk_level=15 if minutes <= 30 else 5,
        )
    
    def _simulate_stress(self, time_label: str, minutes: int, state: Dict) -> SimulationTimestep:
        """Simulación: Estrés psicológico"""
        stress_progression = min(1.0, minutes / 120)  # Max a 2h
        
        return SimulationTimestep(
            time_point=time_label,
            minutes_elapsed=minutes,
            hr=75 + stress_progression * 30,
            hrv=50 - stress_progression * 20,
            cardiac_output=5.2,
            stress_level=30 + stress_progression * 50,
            cognitive_state=80 - stress_progression * 15,
            eeg_activity=60 + stress_progression * 20,
            respiratory_rate=16 + stress_progression * 6,
            spo2=97 - stress_progression * 2,
            ahi=2,
            fatigue_index=15 + stress_progression * 30,
            muscle_activation=50 + stress_progression * 20,
            sympathetic_tone=40 + stress_progression * 40,
            parasympathetic_tone=60 - stress_progression * 40,
            global_health=80 - stress_progression * 25,
            risk_level=10 + stress_progression * 25,
        )
    
    def _simulate_anxiety(self, time_label: str, minutes: int, state: Dict) -> SimulationTimestep:
        """Simulación: Ansiedad aguda"""
        anxiety_peak = min(1.0, minutes / 30)  # Max a 30min
        recovery = max(0, 1 - (minutes - 30) / 60)  # Recovery después
        intensity = anxiety_peak if minutes <= 30 else anxiety_peak * recovery
        
        return SimulationTimestep(
            time_point=time_label,
            minutes_elapsed=minutes,
            hr=80 + intensity * 60,
            hrv=45 - intensity * 35,
            cardiac_output=5.3,
            stress_level=50 + intensity * 40,
            cognitive_state=75 - intensity * 20,
            eeg_activity=70,
            respiratory_rate=18 + intensity * 10,
            spo2=96 - intensity * 3,
            ahi=0,
            fatigue_index=20 + intensity * 30,
            muscle_activation=60 + intensity * 30,
            sympathetic_tone=60 + intensity * 30,
            parasympathetic_tone=40 - intensity * 30,
            global_health=70 - intensity * 30,
            risk_level=15 + intensity * 35,
        )
    
    def _simulate_arrhythmia(self, time_label: str, minutes: int, state: Dict) -> SimulationTimestep:
        """Simulación: Arritmia cardíaca"""
        return SimulationTimestep(
            time_point=time_label,
            minutes_elapsed=minutes,
            hr=110 + np.random.normal(0, 30),  # Muy variable
            hrv=15,  # Muy baja
            cardiac_output=3.8,
            stress_level=70,
            cognitive_state=65,
            eeg_activity=55,
            respiratory_rate=22,
            spo2=94,
            ahi=1,
            fatigue_index=50,
            muscle_activation=45,
            sympathetic_tone=75,
            parasympathetic_tone=25,
            global_health=40,
            risk_level=85,
        )
    
    def _simulate_hypoxia(self, time_label: str, minutes: int, state: Dict) -> SimulationTimestep:
        """Simulación: Hipoxia progresiva"""
        hypoxia_progression = min(1.0, minutes / 120)
        spo2 = 98 - hypoxia_progression * 18  # Baja hasta 80
        
        return SimulationTimestep(
            time_point=time_label,
            minutes_elapsed=minutes,
            hr=75 + hypoxia_progression * 35,
            hrv=50 - hypoxia_progression * 30,
            cardiac_output=4.5 - hypoxia_progression * 1.5,
            stress_level=30 + hypoxia_progression * 50,
            cognitive_state=80 - hypoxia_progression * 40,
            eeg_activity=50 - hypoxia_progression * 20,
            respiratory_rate=18 + hypoxia_progression * 10,
            spo2=spo2,
            ahi=0,
            fatigue_index=20 + hypoxia_progression * 50,
            muscle_activation=40 - hypoxia_progression * 20,
            sympathetic_tone=40 + hypoxia_progression * 35,
            parasympathetic_tone=60 - hypoxia_progression * 35,
            global_health=85 - hypoxia_progression * 55,
            risk_level=5 + hypoxia_progression * 80,
        )
    
    def _simulate_apnea(self, time_label: str, minutes: int, state: Dict) -> SimulationTimestep:
        """Simulación: Apnea Obstructiva del Sueño (AOS) -- Fase 2 (2026-08-12).

        Reemplaza `(minutes*2) % 1` -- con `minutes` entero (siempre lo es,
        los 6 horizontes son enteros) esa expresión da 0 SIEMPRE, un bug de
        fórmula, no un problema de muestreo (ver auditoría Bloque 4 y diseño
        Fase 1, CHANGELOG.md): el arousal era matemáticamente inalcanzable
        para cualquier entero, no solo para los 6 horizontes oficiales.

        Decisión del validador (Fase 1): el ciclo real apnea-arousal dura
        ~30-90s -- inalcanzable por escala frente a horizontes de minutos/
        horas/días. En vez de perseguir el ciclo, esto muestra una FOTO
        DETERMINISTA del evento apneico crítico (nadir del evento, SIEMPRE
        la misma fase -- no alterna por residuo de minutos) + AHI como
        ancla diagnóstica real: la apnea se diagnostica clínicamente por AHI
        (eventos/hora), no por una foto puntual de un evento. Ver
        `get_scenario_description()` para la aclaración de escala que se
        muestra al usuario (82% es el nadir de un evento, no el SpO2
        sostenido del paciente).

        Procedencia (Fase 2, 2026-08-12, validador): SpO2=82% y HR=55
        (nadir del evento apneico / bradicardia del evento) -- CITADOS.
        AHI=45 (AOS severa, criterio AASM AHI>=30) -- CITADO; fluye al UPS
        como descriptor real (`_respiratory_state()`, `builder.py`) para
        que el Narrador Clínico lo cite. El resto de los campos no fue
        parte de esta validación -- PENDING_VALIDATION, se conservan sin
        cambio del valor que ya tenía el código."""
        return SimulationTimestep(
            time_point=time_label,
            minutes_elapsed=minutes,
            hr=55,  # bradicardia del evento apneico -- CITADO, validador Fase 2 (2026-08-12)
            hrv=30,  # PENDING_VALIDATION
            cardiac_output=4.2,  # PENDING_VALIDATION
            stress_level=40,  # PENDING_VALIDATION
            cognitive_state=40,  # PENDING_VALIDATION
            eeg_activity=30,  # PENDING_VALIDATION
            respiratory_rate=0,  # apnea = ausencia de flujo respiratorio, por definición del evento
            spo2=82.0,  # nadir del evento apneico -- CITADO, validador Fase 2 (2026-08-12); NO es el SpO2 sostenido
            ahi=45,  # AOS severa (AASM: AHI>=30) -- CITADO, validador Fase 2 (2026-08-12); ancla diagnóstica real
            fatigue_index=85,  # PENDING_VALIDATION
            muscle_activation=20,  # PENDING_VALIDATION
            sympathetic_tone=50,  # PENDING_VALIDATION
            parasympathetic_tone=50,  # PENDING_VALIDATION
            global_health=30,  # PENDING_VALIDATION
            risk_level=70,  # PENDING_VALIDATION
        )
    
    def _simulate_fatigue(self, time_label: str, minutes: int, state: Dict) -> SimulationTimestep:
        """Simulación: Fatiga crónica"""
        progression = min(1.0, minutes / 1440)
        
        return SimulationTimestep(
            time_point=time_label,
            minutes_elapsed=minutes,
            hr=75,
            hrv=40 - progression * 15,
            cardiac_output=4.8,
            stress_level=35 + progression * 25,
            cognitive_state=70 - progression * 20,
            eeg_activity=40,
            respiratory_rate=16,
            spo2=97,
            ahi=2,
            fatigue_index=70 + progression * 20,
            muscle_activation=30 - progression * 15,
            sympathetic_tone=45,
            parasympathetic_tone=55,
            global_health=55 - progression * 20,
            risk_level=25 + progression * 15,
        )
    
    def _simulate_seizure(self, time_label: str, minutes: int, state: Dict) -> SimulationTimestep:
        """Simulación: Convulsión epiléptica"""
        if minutes < 5:
            return SimulationTimestep(
                time_point=time_label,
                minutes_elapsed=minutes,
                hr=150,
                hrv=5,
                cardiac_output=7.0,
                stress_level=99,
                cognitive_state=10,
                eeg_activity=90,
                respiratory_rate=40,
                spo2=85,
                ahi=0,
                fatigue_index=95,
                muscle_activation=99,
                sympathetic_tone=99,
                parasympathetic_tone=1,
                global_health=5,
                risk_level=99,
            )
        else:
            return self._simulate_healthy(time_label, minutes, state)
    
    def _simulate_sepsis(self, time_label: str, minutes: int, state: Dict) -> SimulationTimestep:
        """Simulación: Sepsis progresiva"""
        progression = min(1.0, minutes / 360)
        
        return SimulationTimestep(
            time_point=time_label,
            minutes_elapsed=minutes,
            hr=100 + progression * 50,
            hrv=30 - progression * 25,
            cardiac_output=4.0 - progression * 2.0,
            stress_level=70 + progression * 30,
            cognitive_state=75 - progression * 50,
            eeg_activity=45 - progression * 25,
            respiratory_rate=22 + progression * 10,
            spo2=95 - progression * 10,
            ahi=0,
            fatigue_index=80 + progression * 15,
            muscle_activation=30,
            sympathetic_tone=80,
            parasympathetic_tone=20,
            global_health=50 - progression * 50,
            risk_level=50 + progression * 45,
        )
    
    def _simulate_copd(self, time_label: str, minutes: int, state: Dict) -> SimulationTimestep:
        """Simulación: EPOC exacerbada -- Fase 2 (2026-08-12).

        Elimina `(minutes // 240) % 2` -- la fórmula sí alcanzaba la
        exacerbación matemáticamente, pero ningún horizonte muestreado la
        mostraba (24h/7d caen siempre en bloque par de la ventana de 240min,
        ver auditoría Bloque 4); y, aparte, el término de SpO2 sumaba 0 en
        AMBAS ramas -- un no-op que nunca reflejó la exacerbación, ni
        siquiera en los minutos que sí la alcanzaban. Dos defectos
        distintos, ambos corregidos aquí.

        Decisión del validador (Fase 1): una exacerbación real dura días,
        no se alterna con la fase estable cada 4h -- alternar por reloj
        interno no modela cuándo ocurre una exacerbación real (la
        desencadena una infección/contaminación, no un temporizador). Este
        escenario representa EPOC EXACERBADA de forma sostenida, siempre --
        ya no hay una fase "estable" que mostrar dentro de este escenario.

        Procedencia (Fase 2, 2026-08-12, validador): SpO2 basal de EPOC
        ESTABLE citada en 88-92% -- no se muestra en este escenario (que
        siempre representa el estado exacerbado); documentada aquí solo
        para trazar la cita completa. SpO2 EXACERBADA <88% -- CITADA; se usa
        85.0 (criterio: valor redondo dentro del rango citado, sin ajustar a
        ningún resultado). Taquicardia/taquipnea -- dirección CONFIRMADA por
        el validador, sin magnitud exacta dada -- HR=95/RR=28 heredados del
        valor que ya tenía el código como marcador (PENDING_VALIDATION,
        magnitud sin citar). CO2/hipercapnia -- omitido a propósito: el
        modelo no representa CO2 en ningún punto del esquema (confirmado por
        lectura completa de `SimulationTimestep`, Fase 1) -- no se finge."""
        return SimulationTimestep(
            time_point=time_label,
            minutes_elapsed=minutes,
            hr=95,  # taquicardia -- PENDING_VALIDATION (magnitud sin citar, dirección confirmada)
            hrv=40,  # PENDING_VALIDATION
            cardiac_output=4.5,  # PENDING_VALIDATION
            stress_level=60,  # PENDING_VALIDATION
            cognitive_state=75,  # PENDING_VALIDATION
            eeg_activity=50,  # PENDING_VALIDATION
            respiratory_rate=28,  # taquipnea -- PENDING_VALIDATION (magnitud sin citar, dirección confirmada)
            spo2=85.0,  # exacerbada, <88% -- CITADO, validador Fase 2 (2026-08-12); ver docstring para el basal (88-92%)
            ahi=0,
            fatigue_index=70,  # PENDING_VALIDATION
            muscle_activation=35,  # PENDING_VALIDATION
            sympathetic_tone=50,  # PENDING_VALIDATION
            parasympathetic_tone=50,  # PENDING_VALIDATION
            global_health=35,  # PENDING_VALIDATION
            risk_level=60,  # PENDING_VALIDATION
        )
    
    def _simulate_hypertension(self, time_label: str, minutes: int, state: Dict) -> SimulationTimestep:
        """Simulación: Hipertensión"""
        return SimulationTimestep(
            time_point=time_label,
            minutes_elapsed=minutes,
            hr=85,
            hrv=35,
            cardiac_output=5.2,
            stress_level=40,
            cognitive_state=75,
            eeg_activity=55,
            respiratory_rate=16,
            spo2=97,
            ahi=0,
            fatigue_index=25,
            muscle_activation=45,
            sympathetic_tone=60,
            parasympathetic_tone=40,
            global_health=65,
            risk_level=40,
        )
    
    def _baseline_timestep(self, time_label: str, minutes: int, state: Dict) -> SimulationTimestep:
        """Línea base (estado basal)"""
        return SimulationTimestep(
            time_point=time_label,
            minutes_elapsed=minutes,
            hr=state.get("hr", 72),
            hrv=state.get("hrv", 50),
            cardiac_output=5.0,
            stress_level=state.get("stress_level", 20),
            cognitive_state=80,
            eeg_activity=50,
            respiratory_rate=state.get("respiratory_rate", 16),
            spo2=state.get("spo2", 98),
            ahi=0,
            fatigue_index=state.get("fatigue_index", 10),
            muscle_activation=40,
            sympathetic_tone=state.get("sympathetic_tone", 30),
            parasympathetic_tone=70,
            global_health=85,
            risk_level=10,
        )
    
    def _update_state_from_timestep(self, state: Dict, timestep: SimulationTimestep) -> Dict:
        """Actualiza estado para siguiente timestep"""
        state.update({
            "hr": timestep.hr,
            "hrv": timestep.hrv,
            "respiratory_rate": timestep.respiratory_rate,
            "spo2": timestep.spo2,
            "stress_level": timestep.stress_level,
            "cognitive_state": timestep.cognitive_state,
            "fatigue_index": timestep.fatigue_index,
            "sympathetic_tone": timestep.sympathetic_tone,
        })
        return state
    
    def get_scenario_description(self, scenario: SimulationScenario) -> str:
        """Descripción del escenario para educación"""
        descriptions = {
            SimulationScenario.HEALTHY: "Individuo sano con parámetros fisiológicos normales.",
            SimulationScenario.EXERCISE: "Ejercicio intenso con recuperación. Ver aumento de FC, RR y fatiga durante actividad.",
            SimulationScenario.STRESS: "Estrés psicológico sostenido. Activación simpática, aumento de FC y estrés hormonal.",
            SimulationScenario.ANXIETY: "Ataque de pánico / ansiedad aguda. Taquicardia, hiperventilación, disminución cognitiva.",
            SimulationScenario.ARRHYTHMIA: "Arritmia cardíaca. FC muy irregular, HRV muy baja, riesgo cardiovascular alto.",
            SimulationScenario.HYPOXIA: "Hipoxia progresiva. SpO2 cae, aumento compensatorio de FC y RR, deterioro cognitivo.",
            SimulationScenario.APNEA: (
                "Apnea Obstructiva del Sueño severa. Muestra el NADIR de un evento apneico crítico "
                "(SpO2 82%, bradicardia) -- no el SpO2 sostenido del paciente. AHI=45 (eventos/hora) "
                "es la métrica diagnóstica real de severidad, no la foto puntual."
            ),
            SimulationScenario.FATIGUE: "Fatiga crónica. HRV baja, deterioro cognitivo progresivo, fatiga muscular persistente.",
            SimulationScenario.SEIZURE: "Convulsión epiléptica. Crisis de ~5 minutos con parámetros fisiológicos críticos.",
            SimulationScenario.SEPSIS: "Sepsis progresiva. Taquicardia, taquipnea, hipoxia, deterioro cognitivo, choque.",
            SimulationScenario.COPD: (
                "EPOC exacerbada, estado SOSTENIDO (no cíclico -- una exacerbación real dura días, "
                "no horas). SpO2 <88%, taquicardia, taquipnea."
            ),
            SimulationScenario.HYPERTENSION: "Hipertensión crónica. FC elevada sostenida, HRV baja, riesgo cardiovascular.",
        }
        return descriptions.get(scenario, "Escenario desconocido")
