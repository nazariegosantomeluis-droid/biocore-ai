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

Arco Respiratory, fase 2a (2026-11-07, Art. I): el generador es el GROUND TRUTH contra el que se
validará el detector. Por eso:
- `generate_respiration()` devuelve la clave `'ground_truth'` con lo que el generador REALMENTE
  produjo (FR efectiva por patrón, lista de eventos con inicio/duración/tipo, periodo de
  modulación de Cheyne-Stokes), no con lo que se pidió.
- El ruido sale de un generador local (`np.random.default_rng(seed)`), no del estado global de numpy:
  la misma semilla produce la misma señal bit a bit.
- `apnea_duration`, `apnea_onset`, `apnea_period` y `expiration_time` tienen efecto real. Con los
  valores por defecto el comportamiento es el histórico (apneas de 20 s a los 40 s de cada minuto;
  la espiración ocupa el resto del ciclo).
- Los parámetros imposibles (inspiración >= ciclo, inspiración + espiración > ciclo, un evento que no
  cabe en su periodo) lanzan `ValueError`; antes producían en silencio una señal sin espiración.
- `recovery_time` y el modelo de SpO2 NO cambian aquí: la SpO2 (derivada de |flujo|) es un artefacto
  conocido y se rehace en la fase 2b. `recovery_time` sigue sin efecto y lo declara (warning +
  `ground_truth['spo2']`).
"""

import warnings

import numpy as np
from typing import Dict, Tuple, Optional
from dataclasses import dataclass

# Valor por defecto de `recovery_time`; cualquier otro valor se declara como "sin efecto" (fase 2b).
RECOVERY_TIME_DEFAULT = 20.0

KNOWN_PATTERNS = (
    "normal", "tachypnea", "bradypnea", "apnea_central", "apnea_obstructive", "cheyne_stokes", "ataxic",
)


@dataclass
class RespiratoryPattern:
    """Configuration for respiratory signal generation"""
    respiratory_rate: float = 15  # breaths/minute
    tidal_volume: float = 0.5  # liters
    inspiration_time: float = 1.0  # seconds
    # seconds. None (por defecto) = la espiración ocupa el resto del ciclo (comportamiento histórico).
    # Un valor explícito acota el flujo espiratorio a esa duración y deja una pausa telespiratoria
    # (flujo cero) hasta el final del ciclo; inspiración + espiración no pueden superar el ciclo.
    expiration_time: Optional[float] = None

    # Pathological patterns
    pattern_type: str = "normal"  # "normal", "tachypnea", "bradypnea", "apnea_central", "apnea_obstructive", "cheyne_stokes", "ataxic"
    apnea_duration: float = 20.0  # seconds (for apnea patterns); antes 15.0 pero no se usaba: el evento real duraba 20 s
    cheyne_stokes_cycle: float = 60.0  # seconds (for Cheyne-Stokes)

    # SpO2 related
    baseline_spo2: float = 98  # %
    desaturation_level: float = 85  # % (minimum during apnea)
    recovery_time: float = RECOVERY_TIME_DEFAULT  # seconds; SIN EFECTO hasta la fase 2b (modelo de SpO2)

    # Calendario de eventos de apnea: un evento empieza `apnea_onset` s dentro de cada periodo de
    # `apnea_period` s y dura `apnea_duration` s (por defecto 40 s / 60 s / 20 s, como siempre).
    apnea_onset: float = 40.0
    apnea_period: float = 60.0


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

    # ------------------------------------------------------------------
    # Parametros efectivos, validacion y ground truth
    # ------------------------------------------------------------------
    @staticmethod
    def effective_params(params: RespiratoryPattern) -> RespiratoryPattern:
        """Parámetros con los que el generador respira de verdad. Taquipnea = FR x1.5 (tope 40) y
        bradipnea = FR x0.5 (piso 6), con volumen y tiempos escalados; el resto de patrones usa los
        parámetros tal cual. Única fuente de este escalado: lo usan la generación y el ground truth."""
        if params.pattern_type == "tachypnea":
            return RespiratoryPattern(
                respiratory_rate=min(params.respiratory_rate * 1.5, 40),  # Up to 40/min
                tidal_volume=params.tidal_volume * 0.6,  # Shallower
                inspiration_time=params.inspiration_time * 0.5,  # Faster
                expiration_time=None if params.expiration_time is None else params.expiration_time * 0.5,
            )
        if params.pattern_type == "bradypnea":
            return RespiratoryPattern(
                respiratory_rate=max(params.respiratory_rate * 0.5, 6),  # Down to 6/min
                tidal_volume=params.tidal_volume * 1.5,  # Deeper
                inspiration_time=params.inspiration_time * 1.5,  # Slower
                expiration_time=None if params.expiration_time is None else params.expiration_time * 1.5,
            )
        return params

    @staticmethod
    def _validate(params: RespiratoryPattern, eff: RespiratoryPattern, duration: float) -> None:
        """Rechaza combinaciones imposibles con un mensaje explícito (nunca una señal sin espiración)."""
        if not duration > 0:
            raise ValueError(f"duration debe ser > 0 s (recibido {duration}).")
        if not eff.respiratory_rate > 0:
            raise ValueError(f"respiratory_rate debe ser > 0 (recibido {eff.respiratory_rate}).")
        if params.pattern_type != "ataxic":
            cycle = 60.0 / eff.respiratory_rate
            ctx = (f"patrón '{params.pattern_type}', FR efectiva {eff.respiratory_rate:g}/min "
                   f"(ciclo {cycle:.2f} s), inspiración efectiva {eff.inspiration_time:g} s")
            if not eff.inspiration_time > 0:
                raise ValueError(f"inspiration_time debe ser > 0 ({ctx}).")
            if eff.inspiration_time >= cycle:
                raise ValueError(
                    f"Parámetros imposibles: la inspiración ({eff.inspiration_time:g} s) no cabe en el ciclo "
                    f"({cycle:.2f} s) y no quedaría espiración ({ctx}). Baja el tiempo de inspiración o la FR."
                )
            if eff.expiration_time is not None:
                if not eff.expiration_time > 0:
                    raise ValueError(f"expiration_time debe ser > 0 o None ({ctx}).")
                if eff.inspiration_time + eff.expiration_time > cycle + 1e-9:
                    raise ValueError(
                        f"Parámetros imposibles: inspiración ({eff.inspiration_time:g} s) + espiración "
                        f"({eff.expiration_time:g} s) superan el ciclo ({cycle:.2f} s) ({ctx})."
                    )
        if params.pattern_type in ("apnea_central", "apnea_obstructive"):
            if not (params.apnea_duration > 0 and params.apnea_period > 0 and params.apnea_onset >= 0):
                raise ValueError("apnea_duration y apnea_period deben ser > 0 y apnea_onset >= 0.")
            if params.apnea_onset + params.apnea_duration > params.apnea_period + 1e-9:
                raise ValueError(
                    f"El evento de {params.apnea_duration:g} s que empieza en {params.apnea_onset:g} s no cabe en "
                    f"el periodo de {params.apnea_period:g} s: baja apnea_duration/apnea_onset o sube apnea_period."
                )

    def _ground_truth(self, params: RespiratoryPattern, eff: RespiratoryPattern, duration: float,
                      seed: Optional[int]) -> Dict:
        """Lo que la señal contiene REALMENTE, calculado de los mismos parámetros que la generan."""
        pattern = params.pattern_type if params.pattern_type in KNOWN_PATTERNS else "normal"
        events = []
        if pattern in ("apnea_central", "apnea_obstructive"):
            kind = "central" if pattern == "apnea_central" else "obstructive"
            k = 0
            while True:
                start = k * params.apnea_period + params.apnea_onset
                if start >= duration:
                    break
                end = min(start + params.apnea_duration, duration)
                events.append({
                    "start_s": float(start),
                    "duration_s": float(end - start),
                    "type": kind,
                    "truncated": bool(end < start + params.apnea_duration),
                })
                k += 1
        return {
            "pattern": pattern,
            "requested_pattern": params.pattern_type,
            "requested_respiratory_rate": float(params.respiratory_rate),
            "effective_respiratory_rate": float(eff.respiratory_rate),
            # La atáxica es una portadora regular a esa FR con amplitud aleatoria: su frecuencia no es irregular.
            "rate_is_regular": True,
            "events": events,
            "modulation_period_s": float(params.cheyne_stokes_cycle) if pattern == "cheyne_stokes" else None,
            "duration_s": float(duration),
            "sampling_rate_hz": float(self.sampling_rate),
            "seed": seed,
            # La SpO2 NO es ground truth: se deriva de |flujo| (artefacto conocido, se rehace en la fase 2b).
            "spo2": {
                "is_ground_truth": False,
                "model": "legacy_airflow_derived",
                "recovery_time_applied": False,
            },
        }

    def _event_window(self, phase: np.ndarray, params: RespiratoryPattern) -> np.ndarray:
        """Máscara de las muestras dentro de un evento de apnea. Con los valores por defecto la
        aritmética es la histórica (fase >= 40/60 y fase < 60/60 = 1.0, siempre verdadera)."""
        onset_phase = params.apnea_onset / params.apnea_period
        end_phase = (params.apnea_onset + params.apnea_duration) / params.apnea_period
        return (phase >= onset_phase) & (phase < end_phase)

    @staticmethod
    def _expiration_fraction(params: RespiratoryPattern, cycle_duration: float) -> Optional[float]:
        return None if params.expiration_time is None else params.expiration_time / cycle_duration

    def generate_respiration(
        self,
        duration: float = 60.0,
        params: RespiratoryPattern = None,
        seed: Optional[int] = None,
    ) -> Dict[str, np.ndarray]:
        """
        Generate complete respiratory waveform

        Args:
            duration: Recording length in seconds
            params: Respiratory parameters
            seed: semilla del ruido (misma semilla -> misma señal bit a bit). None = no reproducible.

        Returns:
            Dictionary with signals:
            {
                'airflow': array,  # L/min
                'chest_wall': array,  # Strain gauge (dimensionless)
                'abdomen': array,  # Abdominal movement
                'spo2': array,  # Oxygen saturation (%)
                'time': array,
                'ground_truth': dict  # FR efectiva, eventos (inicio, duración, tipo), patrón
            }
        """
        if params is None:
            params = RespiratoryPattern()

        eff = self.effective_params(params)
        self._validate(params, eff, duration)
        if params.recovery_time != RECOVERY_TIME_DEFAULT:
            warnings.warn(
                "recovery_time no tiene efecto todavía: la cinética de recuperación de la SpO2 se implementa "
                "en la fase 2b del arco respiratorio.", UserWarning, stacklevel=2,
            )

        rng = np.random.default_rng(seed)
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
            airflow, chest, abdomen = self._generate_ataxic_respiration(time, params, rng)
        else:
            airflow, chest, abdomen = self._generate_normal_respiration(time, params)

        # Generate SpO2 based on airflow
        spo2 = self._generate_spo2(airflow, time, params, rng)

        # Add noise to signals
        airflow += rng.normal(0, 0.02, n_samples)
        chest += rng.normal(0, 0.01, n_samples)
        abdomen += rng.normal(0, 0.01, n_samples)

        result = {
            'airflow': airflow,  # Primary respiratory signal
            'chest_wall': chest,  # Thoracic movement
            'abdomen': abdomen,  # Abdominal movement
            'spo2': spo2,  # Pulse oximetry
            'time': time,
            'ground_truth': self._ground_truth(params, eff, duration, seed),
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
        exp_fraction = self._expiration_fraction(params, cycle_duration)

        # Generate sinusoidal airflow (positive during inspiration, negative during expiration)
        inspiration_mask = phase < inspiration_fraction
        expiration_mask = ~inspiration_mask
        if exp_fraction is not None:  # espiración acotada: el resto del ciclo es pausa telespiratoria (flujo 0)
            expiration_mask = expiration_mask & (phase < inspiration_fraction + exp_fraction)

        # Inspiration: gradual increase then decrease
        inspiration_phase = phase[inspiration_mask] / inspiration_fraction
        airflow[inspiration_mask] = (
            params.tidal_volume *
            np.sin(inspiration_phase * np.pi) *
            (60.0 / cycle_duration)  # Convert to breaths/min scale
        )

        # Expiration: slower, longer phase
        exp_span = (1.0 - inspiration_fraction) if exp_fraction is None else exp_fraction
        expiration_phase = (phase[expiration_mask] - inspiration_fraction) / exp_span
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
        return self._generate_normal_respiration(time, self.effective_params(params))

    def _generate_bradypnea(
        self,
        time: np.ndarray,
        params: RespiratoryPattern
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Generate bradypnea (slow, deep breathing)"""
        return self._generate_normal_respiration(time, self.effective_params(params))

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
        apnea_cycle = params.apnea_period  # 60 s por defecto

        cycles = time / cycle_duration
        apnea_events = time / apnea_cycle
        phase_in_apnea_cycle = np.mod(apnea_events, 1.0)

        # Create breathing pattern
        base_phase = np.mod(cycles, 1.0)
        inspiration_fraction = params.inspiration_time / cycle_duration
        exp_fraction = self._expiration_fraction(params, cycle_duration)

        # Identify apnea windows (por defecto, los últimos 20 s de cada ciclo de 60 s)
        in_apnea = self._event_window(phase_in_apnea_cycle, params)

        # Generate breathing outside apnea
        breathing_mask = ~in_apnea
        inspiration_mask = (base_phase < inspiration_fraction) & breathing_mask
        expiration_mask = (base_phase >= inspiration_fraction) & breathing_mask
        if exp_fraction is not None:
            expiration_mask = expiration_mask & (base_phase < inspiration_fraction + exp_fraction)

        inspiration_phase = base_phase[inspiration_mask] / inspiration_fraction
        airflow[inspiration_mask] = (
            params.tidal_volume *
            np.sin(inspiration_phase * np.pi) *
            (60.0 / cycle_duration)
        )

        exp_span = (1.0 - inspiration_fraction) if exp_fraction is None else exp_fraction
        expiration_phase = (base_phase[expiration_mask] - inspiration_fraction) / exp_span
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
        apnea_cycle = params.apnea_period  # 60 s por defecto

        cycles = time / cycle_duration
        apnea_events = time / apnea_cycle
        phase_in_apnea_cycle = np.mod(apnea_events, 1.0)

        base_phase = np.mod(cycles, 1.0)
        inspiration_fraction = params.inspiration_time / cycle_duration
        exp_fraction = self._expiration_fraction(params, cycle_duration)

        # Identify obstruction windows
        in_obstruction = self._event_window(phase_in_apnea_cycle, params)

        # Generate airflow (normal breathing outside obstruction)
        breathing_mask = ~in_obstruction
        inspiration_mask = (base_phase < inspiration_fraction) & breathing_mask
        expiration_mask = (base_phase >= inspiration_fraction) & breathing_mask
        if exp_fraction is not None:
            expiration_mask = expiration_mask & (base_phase < inspiration_fraction + exp_fraction)

        inspiration_phase = base_phase[inspiration_mask] / inspiration_fraction
        airflow[inspiration_mask] = (
            params.tidal_volume *
            np.sin(inspiration_phase * np.pi) *
            (60.0 / cycle_duration)
        )

        exp_span = (1.0 - inspiration_fraction) if exp_fraction is None else exp_fraction
        expiration_phase = (base_phase[expiration_mask] - inspiration_fraction) / exp_span
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
        exp_fraction = self._expiration_fraction(params, cycle_duration)

        # Generate modulated breathing
        inspiration_mask = breathing_phase < inspiration_fraction
        expiration_mask = ~inspiration_mask
        if exp_fraction is not None:
            expiration_mask = expiration_mask & (breathing_phase < inspiration_fraction + exp_fraction)

        inspiration_phase = breathing_phase[inspiration_mask] / inspiration_fraction
        airflow[inspiration_mask] = (
            amplitude_mod[inspiration_mask] *
            params.tidal_volume *
            np.sin(inspiration_phase * np.pi) *
            (60.0 / cycle_duration)
        )

        exp_span = (1.0 - inspiration_fraction) if exp_fraction is None else exp_fraction
        expiration_phase = (breathing_phase[expiration_mask] - inspiration_fraction) / exp_span
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
        params: RespiratoryPattern,
        rng: np.random.Generator,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Generate Ataxic respiration (Biot breathing)
        - Completely irregular breathing pattern
        - Variable depth and frequency
        - Associated with brainstem injury

        NOTA (2026-11-07, sin cambiar la semántica): hoy solo varía la AMPLITUD. La portadora es una
        sinusoide a la FR pedida (pico espectral exacto en esa FR con cualquier semilla), así que la
        frecuencia NO es irregular. Propuesta para hacerla fiel: ver el informe de la fase 2a.
        """
        airflow = rng.normal(0, params.tidal_volume * 0.3, len(time))

        # Add some structure to avoid complete noise
        cycle_duration = 60.0 / params.respiratory_rate
        breathing_cycles = time / cycle_duration
        base_pattern = np.sin(2 * np.pi * breathing_cycles)

        # Random modulation
        random_mod = np.cumsum(rng.normal(0, 0.1, len(time)))
        random_mod = np.exp(-np.abs(random_mod) / 10)  # Decay fluctuations

        airflow = (base_pattern * random_mod +
                   rng.normal(0, 0.1, len(time))) * params.tidal_volume

        chest = airflow * 0.8
        abdomen = airflow * 1.1

        return airflow, chest, abdomen

    def _generate_spo2(
        self,
        airflow: np.ndarray,
        time: np.ndarray,
        params: RespiratoryPattern,
        rng: np.random.Generator,
    ) -> np.ndarray:
        """
        Generate SpO2 (oxygen saturation) based on respiratory signal

        Low/absent airflow → hypoxemia → SpO2 drop

        ARTEFACTO CONOCIDO (inventario 2026-11-05; se rehace en la fase 2b): la desaturación sale de
        |flujo| normalizado, así que cae en cada cruce por cero del flujo incluso con respiración
        normal. La fórmula NO se tocó en la fase 2a; solo el ruido usa ahora el generador local.
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
        spo2 += rng.normal(0, 0.5, len(spo2))
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
