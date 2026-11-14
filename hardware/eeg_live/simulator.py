"""EEG simulado para practicar sin hardware (2026-11-14). Siempre SIMULACIÓN, nunca un sensor.

Qué imita y de dónde sale cada rasgo:

- Ritmo alfa de 10 Hz, máximo en O1 y O2, menor en P7 y P8, poco en C3 y C4 y casi nada en Fp1 y Fp2. Con los
  ojos cerrados llega a 40 µV de pico; con los ojos abiertos baja a la cuarta parte, con una transición de
  medio segundo. El glosario de la IFCN lo define así: 8–13 Hz, en vigilia, sobre las regiones posteriores con
  máximo occipital, mejor con los ojos cerrados, bloqueado o atenuado por la atención (sobre todo visual) y casi
  siempre por debajo de 50 µV en el adulto (Kane et al. 2017). Los pesos por electrodo, la cuarta parte y el
  medio segundo son elecciones del simulador: el glosario no da cifras.
- Parpadeo: el mismo pulso que usa el generador del laboratorio (Hann de unos 50 ms y 80 µV,
  `EegSignalGenerator._blink_artifacts`), completo en Fp1 y Fp2, los electrodos más cercanos a los ojos, y a la
  décima parte en C3 y C4. Es el modelo del laboratorio, no un parpadeo registrado. El artefacto ocular nace del
  potencial corneorretiniano: la córnea es positiva respecto a la retina (Tatum et al. 2011).
- Electrodo flojo: un solo canal con mucho ruido de la red eléctrica y una deriva lenta y amplia. La actividad
  confinada a un solo canal es artefacto hasta demostrar lo contrario (Tatum et al. 2011).
- Fondo: ruido con más potencia en las frecuencias bajas (autorregresivo de orden 1) más un poco de ruido
  blanco y de red en todos los canales.
- Cable desconectado: deja de mandar muestras, como un equipo real apagado.
"""

from __future__ import annotations

import threading
import time
from typing import Callable, List, Optional, Tuple

import numpy as np
from scipy.signal import lfilter

CHANNELS: Tuple[str, ...] = ('Fp1', 'Fp2', 'C3', 'C4', 'P7', 'P8', 'O1', 'O2')
ALPHA_WEIGHTS = np.array([0.1, 0.1, 0.3, 0.3, 0.6, 0.6, 1.0, 1.0])
BLINK_WEIGHTS = np.array([1.0, 1.0, 0.1, 0.1, 0.0, 0.0, 0.0, 0.0])

ALPHA_HZ = 10.0
ALPHA_PEAK_UV = 40.0           # ojos cerrados, en O1 y O2
EYES_OPEN_FACTOR = 0.25
ALPHA_TAU_S = 0.5
BLINK_PEAK_UV = 80.0           # el pulso de `EegSignalGenerator._blink_artifacts`
BLINK_S = 0.05
BACKGROUND_RMS_UV = 6.0
BACKGROUND_AR = 0.95
WHITE_RMS_UV = 1.0
MAINS_UV = 1.0
LOOSE_MAINS_UV = 150.0
LOOSE_DRIFT_RMS_UV = 80.0
LOOSE_DRIFT_TAU_S = 0.3
MAX_READ_S = 2.0               # una lectura atrasada no entrega más de esto (no se inventa un hueco largo)


class SimulatedEegDevice:
    """Ocho canales de EEG simulado que la práctica controla: ojos, parpadeo, electrodo flojo y cable."""

    channels: Tuple[str, ...] = CHANNELS

    def __init__(self, fs: float = 250.0, mains_hz: Optional[float] = 60.0, seed: int = 7,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.fs = float(fs)
        self.mains_hz = mains_hz if mains_hz and mains_hz < self.fs / 2 else None
        self._clock = clock
        self._rng = np.random.default_rng(seed)
        self._lock = threading.Lock()
        self.plugged = True
        self.eyes_closed = False
        self.loose: Optional[str] = None
        self._n = 0
        self._carry = 0.0
        self._last: Optional[float] = None
        self._alpha_level = EYES_OPEN_FACTOR
        self._phase = self._rng.uniform(0.0, 0.3, len(CHANNELS))
        self._bg_zi = np.zeros((len(CHANNELS), 1))
        drift_a = float(np.exp(-1.0 / (LOOSE_DRIFT_TAU_S * self.fs)))
        self._drift_a = drift_a
        self._drift_zi = np.zeros(1)
        self._blinks: List[int] = []

    # ------------------------------------------------------------ controles
    def plug(self) -> None:
        with self._lock:
            self.plugged = True

    def unplug(self) -> None:
        with self._lock:
            self.plugged = False

    def set_eyes_closed(self, closed: bool) -> None:
        with self._lock:
            self.eyes_closed = bool(closed)

    def set_loose(self, channel: Optional[str]) -> None:
        if channel is not None and channel not in CHANNELS:
            raise ValueError(f'{channel} no es un canal del simulador.')
        with self._lock:
            self.loose = channel

    def blink(self) -> None:
        with self._lock:
            self._blinks.append(self._n)

    # ------------------------------------------------------------ lectura
    def start_session(self) -> None:
        with self._lock:
            self._last = self._clock()
            self._carry = 0.0

    def read(self) -> np.ndarray:
        """Las muestras que «llegaron» desde la última lectura, según el reloj; nada si el cable está fuera."""
        with self._lock:
            now = self._clock()
            if not self.plugged or self._last is None:
                self._last = now
                return np.zeros((len(CHANNELS), 0))
            want = (now - self._last) * self.fs + self._carry
            n = int(want)
            self._carry = want - n
            self._last = now
            return self._generate(min(n, int(MAX_READ_S * self.fs)))

    def generate(self, n: int) -> np.ndarray:
        """`n` muestras seguidas, sin reloj (para pruebas y para llenar un registro de una vez)."""
        with self._lock:
            return self._generate(int(n))

    def _generate(self, n: int) -> np.ndarray:
        n_ch = len(CHANNELS)
        if n <= 0:
            return np.zeros((n_ch, 0))
        fs = self.fs
        t = (self._n + np.arange(n)) / fs
        rng = self._rng

        # Todas las muestras aleatorias en orden de muestra (fondo, blanco y deriva de cada instante): así la señal
        # es la misma se lea en trozos de cualquier tamaño, y la deriva no cambia la secuencia al aflojar un electrodo.
        noise = rng.normal(0.0, 1.0, (n, 2 * n_ch + 1))
        innovation = noise[:, :n_ch].T * (BACKGROUND_RMS_UV * np.sqrt(1 - BACKGROUND_AR ** 2))
        background, self._bg_zi = lfilter([1.0], [1.0, -BACKGROUND_AR], innovation, axis=1, zi=self._bg_zi)
        x = background + WHITE_RMS_UV * noise[:, n_ch:2 * n_ch].T

        target = 1.0 if self.eyes_closed else EYES_OPEN_FACTOR
        level = target + (self._alpha_level - target) * np.exp(-np.arange(1, n + 1) / (ALPHA_TAU_S * fs))
        self._alpha_level = float(level[-1])
        x += ALPHA_PEAK_UV * ALPHA_WEIGHTS[:, None] * level[None, :] * np.sin(
            2 * np.pi * ALPHA_HZ * t[None, :] + self._phase[:, None])

        mains = np.sin(2 * np.pi * self.mains_hz * t) if self.mains_hz else np.zeros(n)
        x += MAINS_UV * mains[None, :]

        width = int(fs * BLINK_S)             # igual que `_blink_artifacts`: np.hanning(int(fs * 0.05)) * 80
        pulse = np.hanning(width) * BLINK_PEAK_UV
        for start in self._blinks:
            lo, hi = max(start, self._n), min(start + width, self._n + n)
            if lo < hi:
                x[:, lo - self._n:hi - self._n] += BLINK_WEIGHTS[:, None] * pulse[None, lo - start:hi - start]
        self._blinks = [s for s in self._blinks if s + width > self._n + n]

        if self.loose is not None:
            i = CHANNELS.index(self.loose)
            step = LOOSE_DRIFT_RMS_UV * np.sqrt(1 - self._drift_a ** 2)
            drift, self._drift_zi = lfilter([step], [1.0, -self._drift_a], noise[:, -1], zi=self._drift_zi)
            x[i] += LOOSE_MAINS_UV * mains + drift

        self._n += n
        return x
