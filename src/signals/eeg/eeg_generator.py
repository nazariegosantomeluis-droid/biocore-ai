"""
EEG Signal Generator - Simulated brainwave activity for Neuro Lab

Generates multi-channel EEG with clinical patterns:
- Alpha (8-12 Hz)
- Beta (13-30 Hz)
- Theta (4-7 Hz)
- Delta (0.5-3 Hz)
- Sleep spindles
- Seizure-like spikes
- Blink/artifact noise
- Motor imagery (Mu ERD -- Tanda 1, 2026-09-26): evento motor con
  profundidad/timing conocidos por construcción, ground truth para
  `erd_detector.py`. Ver docstring de `_motor_imagery_erd()`.
"""

import numpy as np
from dataclasses import dataclass
from typing import Dict, NamedTuple, Optional, Tuple, List


# Ventanas de medición del ERD derivadas del evento (ver
# `MotorImageryEvent.measurement_windows()`): baseline de hasta 4s (mínimo
# 1s), que deja al menos 0.5s de señal antes de empezar; ventana de evento de
# 2s (acotada a la meseta) que arranca al terminar la transición.
_ERD_BASELINE_MAX_S = 4.0
_ERD_BASELINE_MIN_S = 1.0
_ERD_BASELINE_LEAD_IN_S = 0.5
_ERD_EVENT_WINDOW_S = 2.0


class MeasurementWindows(NamedTuple):
    """Parámetros de ventana en la forma que `erd_detector.detect_mu_erd()`
    recibe -- el detector sigue genérico y no conoce `MotorImageryEvent`."""

    baseline_duration_s: float
    event_offset_s: float
    event_duration_s: float


@dataclass(frozen=True)
class MotorImageryEvent:
    """Evento motor del patrón `motor_imagery` -- dueño único de su
    temporización: el generador la usa para construir la envolvente, el
    panel del EEG Lab para acotar el slider y para decirle al detector
    dónde medir. Defaults: evento en t=10s, transición 1s, meseta 3s,
    recuperación 3s -> termina en 17s, cabe en `duration=20.0`."""

    t_event: float = 10.0
    depth_pct: float = 60.0
    transition_s: float = 1.0
    plateau_s: float = 3.0
    recovery_s: float = 3.0

    def __post_init__(self):
        if self.t_event < 0.0:
            raise ValueError(f"t_event debe ser >= 0, recibido {self.t_event}")
        if not 0.0 <= self.depth_pct < 100.0:
            raise ValueError(f"depth_pct debe estar en [0, 100), recibido {self.depth_pct}")
        for name in ("transition_s", "plateau_s", "recovery_s"):
            value = getattr(self, name)
            if value <= 0.0:
                raise ValueError(f"{name} debe ser > 0, recibido {value}")

    @property
    def total_span_s(self) -> float:
        """Transición + meseta + recuperación: cuánto dura el evento desde `t_event`."""
        return self.transition_s + self.plateau_s + self.recovery_s

    def measurement_windows(self) -> MeasurementWindows:
        """Baseline inmediatamente antes de `t_event`; ventana de evento que
        salta la transición (mide la meseta ya asentada, no la pendiente) y
        cabe dentro de la meseta."""
        return MeasurementWindows(
            baseline_duration_s=min(_ERD_BASELINE_MAX_S, max(_ERD_BASELINE_MIN_S, self.t_event - _ERD_BASELINE_LEAD_IN_S)),
            event_offset_s=self.transition_s,
            event_duration_s=min(_ERD_EVENT_WINDOW_S, self.plateau_s),
        )


@dataclass
class EegPattern:
    pattern_type: str = "alpha"
    duration: float = 20.0
    fs: float = 256.0
    amplitude: float = 40.0
    noise_level: float = 0.25
    seizure_frequency: float = 6.0
    blink_rate: float = 0.5
    channels: int = 4
    # Solo lo lee el patrón `motor_imagery`; `None` -> `MotorImageryEvent()` por defecto.
    motor_event: Optional[MotorImageryEvent] = None


def _raised_cosine(frac: np.ndarray) -> np.ndarray:
    """Rampa suave 0 -> 1 para `frac` en [0, 1] (sin escalón abrupto)."""
    return (1.0 - np.cos(np.pi * frac)) / 2.0


class EegSignalGenerator:
    """Generate simulated EEG activity for educational neuro lab."""

    def __init__(self, sampling_rate: float = 256.0):
        self.fs = sampling_rate
        self.dt = 1.0 / sampling_rate

    def generate_eeg(self, params: EegPattern) -> Tuple[Dict[str, np.ndarray], np.ndarray]:
        n_samples = int(params.duration * self.fs)
        time = np.arange(n_samples) * self.dt
        leads = ['Fp1', 'Fp2', 'C3', 'C4'][: params.channels]
        eeg = {lead: self._generate_channel(time, params, i) for i, lead in enumerate(leads)}
        eeg['time'] = time
        return eeg, time

    def _generate_channel(self, time: np.ndarray, params: EegPattern, channel_index: int) -> np.ndarray:
        base = np.zeros_like(time)
        if params.pattern_type == 'alpha':
            base = self._band_signal(time, 10.0, params.amplitude * 0.8)
        elif params.pattern_type == 'beta':
            base = self._band_signal(time, 20.0, params.amplitude * 0.6)
        elif params.pattern_type == 'theta':
            base = self._band_signal(time, 5.5, params.amplitude * 1.0)
        elif params.pattern_type == 'delta':
            base = self._band_signal(time, 1.5, params.amplitude * 1.2)
        elif params.pattern_type == 'sleep_spindle':
            base = self._band_signal(time, 10.5, params.amplitude * 0.7)
            base += self._spindle_bursts(time)
        elif params.pattern_type == 'seizure':
            base = self._band_signal(time, 6.0, params.amplitude * 1.0)
            base += self._seizure_spikes(time, params.seizure_frequency)
        elif params.pattern_type == 'artifact':
            base = self._band_signal(time, 10.0, params.amplitude * 0.5)
            base += self._blink_artifacts(time, params.blink_rate)
        elif params.pattern_type == 'motor_imagery':
            base = self._motor_imagery_erd(time, params.amplitude, params.motor_event or MotorImageryEvent())
        else:
            base = self._band_signal(time, 10.0, params.amplitude * 0.8)

        noise = np.random.normal(0, params.amplitude * params.noise_level, len(time))
        return base + noise

    def _band_signal(self, time: np.ndarray, center_hz: float, amplitude: float) -> np.ndarray:
        phase = 2 * np.pi * center_hz * time
        return amplitude * np.sin(phase) * np.exp(-time / (len(time) * self.dt * 2))

    def _motor_imagery_erd(self, time: np.ndarray, amplitude: float, event: MotorImageryEvent) -> np.ndarray:
        """Mu ERD Tanda 1 (2026-09-26) -- ritmo mu (10Hz, centro de la banda
        8-13Hz) con una envolvente de AMPLITUD conocida por construcción:
        reposo (potencia mu normal) -> transición suave (coseno alzado, sin
        escalón abrupto) a una caída de `depth_pct`% de POTENCIA
        (definición Pfurtscheller de ERD%) en `t_event` -> meseta de
        `plateau_s` sostenida en el nivel reducido ->
        recuperación suave a la potencia basal.

        Deliberadamente NO usa `_band_signal()` (que aplica a los otros 7
        patrones): ese decaimiento exponencial de fondo, aplicado a TODA la
        señal, contaminaría el ground truth -- la única modulación de
        amplitud aquí debe ser la envolvente ERD exacta, para que
        `depth_pct` sea lo que `erd_detector.detect_mu_erd()` mide
        de vuelta, no una aproximación con una fuente de sesgo extra sin
        modelar.

        Potencia (vía Hilbert) escala con amplitud^2 -- el factor de
        amplitud durante la meseta es `sqrt(1 - profundidad/100)`, para que
        la caída de POTENCIA resultante sea exactamente `profundidad_pct`
        sobre una envolvente lenta (el criterio de banda angosta que Hilbert
        necesita para una envolvente instantánea precisa -- transición/
        recuperación de 1-3s son ordenes de magnitud más lentas que el
        ciclo de 100ms del ritmo mu de 10Hz).

        NOTA DE HONESTIDAD (Art. IV): señal SINTÉTICA con evento motor
        PRESCRITO matemáticamente -- nunca un registro de imaginación motora
        real. Ground truth de banco de pruebas, mismo criterio que
        `generate_blink_artifact()`/`spectral_model.generate_colored_noise()`
        -- el detector se valida midiendo si RECUPERA `depth_pct`,
        no si "se ve razonable"."""
        event_amplitude_factor = float(np.sqrt(1.0 - event.depth_pct / 100.0))
        drop = 1.0 - event_amplitude_factor

        t_transition_end = event.t_event + event.transition_s
        t_plateau_end = t_transition_end + event.plateau_s
        t_recovery_end = t_plateau_end + event.recovery_s

        envelope = np.ones_like(time)

        in_transition = (time >= event.t_event) & (time < t_transition_end)
        envelope[in_transition] = 1.0 - drop * _raised_cosine((time[in_transition] - event.t_event) / event.transition_s)

        in_plateau = (time >= t_transition_end) & (time < t_plateau_end)
        envelope[in_plateau] = event_amplitude_factor

        in_recovery = (time >= t_plateau_end) & (time < t_recovery_end)
        envelope[in_recovery] = event_amplitude_factor + drop * _raised_cosine((time[in_recovery] - t_plateau_end) / event.recovery_s)
        # time >= t_recovery_end ya vale 1.0 por el np.ones_like inicial.

        mu_carrier = amplitude * 0.8 * np.sin(2 * np.pi * 10.0 * time)
        return mu_carrier * envelope

    def _seizure_spikes(self, time: np.ndarray, frequency: float) -> np.ndarray:
        spikes = np.zeros_like(time)
        period = int(self.fs / frequency)
        for idx in range(0, len(time), max(1, period)):
            width = int(self.fs * 0.02)
            end = min(idx + width, len(time))
            spikes[idx:end] += np.linspace(0, 70.0, end - idx)
        return spikes

    def _spindle_bursts(self, time: np.ndarray) -> np.ndarray:
        bursts = np.zeros_like(time)
        for start in range(0, len(time), int(self.fs * 3.0)):
            end = min(start + int(self.fs * 0.5), len(time))
            bursts[start:end] += 30.0 * np.sin(2 * np.pi * 12.0 * time[start:end])
        return bursts

    def generate_blink_artifact(self, duration: float, rate: float = 0.5) -> np.ndarray:
        """Arco 2A (2026-09-11) -- wrapper PÚBLICO de `_blink_artifacts()`,
        para que el banco de pruebas del rechazo de artefactos pueda
        inyectar el parpadeo MODELADO (pulso Hann ~50ms, ~80µV, repetido
        cada `1/rate` segundos) sin depender de un método privado de esta
        clase. No cambia la fórmula ni la usa `_generate_channel()` en su
        lugar -- solo expone la misma señal que ya vive detrás del patrón
        "Artifact (parpadeo)" del selector del EEG Lab."""
        n_samples = int(duration * self.fs)
        time = np.arange(n_samples) * self.dt
        return self._blink_artifacts(time, rate)

    def _blink_artifacts(self, time: np.ndarray, rate: float) -> np.ndarray:
        artifacts = np.zeros_like(time)
        interval = int(self.fs / max(rate, 0.1))
        for start in range(0, len(time), interval):
            width = int(self.fs * 0.05)
            end = min(start + width, len(time))
            artifacts[start:end] += np.hanning(end - start) * 80.0
        return artifacts
