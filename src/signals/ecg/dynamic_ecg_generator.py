"""
DynamicECGGenerator — modelo de McSharry et al. 2003 (IEEE Transactions on
Biomedical Engineering, "A dynamical model for generating synthetic
electrocardiogram signals"), estándar de oro para ECG sintético paramétrico.

Fase 5B (2026-08-30) — reemplaza a `generate_demo_ecg_signal()`
(`app/utils.py`), que tenía 3 bugs confirmados por ejecución:
  1. Ignoraba el `hr` pedido -- el QRS usaba un ciclo fijo `t % 1` (siempre
     ~60 bpm en la forma de onda, sin importar el parámetro).
  2. El detector simple que lo consumía (`estimate_ecg_heart_rate`,
     `app/utils.py`) saturaba en 220 bpm (`np.clip(..., 0, 220)`).
  3. Al no variar el período con el HR, la morfología QRS no toleraba un
     ciclo cardíaco distinto del que tenía cableado.

Modelo (fórmulas EXACTAS del validador clínico -- cableadas tal cual, no
aproximadas):

  Velocidad angular dinámica:  ω(t) = 2π·HR(t)/60
  Fase integrada:              θ(t) = (∫₀ᵗ ω(τ)dτ) mod 2π
    -- discretizada como suma acumulada: θ[n] = (Σ_{k<=n} ω[k]·dt) mod 2π.
    La fase avanza continuamente y se reinicia cada latido (0 → 2π).
  Suma de 5 ondas gaussianas:  z(θ) = Σᵢ aᵢ·exp(−Δθᵢ²/(2bᵢ²)), i ∈ {P,Q,R,S,T}
    -- Δθᵢ es la distancia angular MÍNIMA (con signo) entre θ y θᵢ, envuelta
    a (−π, π] -- necesario porque θᵢ de P/Q es negativo mientras θ se
    representa en [0, 2π): sin envolver, la gaussiana de P nunca vería las
    muestras que le corresponden al final de cada ciclo.

Matriz de parámetros (derivación II / MLII, base 60 bpm) -- EXACTA, ver
tabla del validador:

    Onda | aᵢ (mV) | bᵢ (rad) | θᵢ (rad, base 60bpm)
    P    |  0.15   |   0.25   | −π/3   (≈ −1.047)
    Q    | −0.20   |   0.10   | −π/12  (≈ −0.261)
    R    |  1.50   |   0.10   |  0.0   (fiducial)
    S    | −0.40   |   0.10   | +π/12  (≈ +0.261)
    T    |  0.40   |   0.40   |  π/2   (≈ 1.571, base a 60bpm -- dinámico
         |         |          |  por HR vía Bazett, ver abajo)

Restitución QT de Bazett (θ_T dinámico, NO estático): la posición angular
de la T se desplaza con el HR para que la sístole no se comprima
linealmente y la T no colisione con el QRS a HR alto:

    θ_T(HR) = θ_R + (π/2)·√(HR/60) = (π/2)·√(HR/60)   (con θ_R = 0)

A 60 bpm → θ_T = π/2 (coincide con la base de la tabla). A 150 bpm →
θ_T ≈ 2.48 rad (verificado por el validador: mantiene ~2.222 rad de
distancia de la S, en +0.261 -- sin colisión).

Frecuencia de muestreo: el generador viejo (`generate_demo_ecg_signal`,
`app/utils.py`) corre a `fs=250` por defecto -- MISMA fs que usó el
validador clínico para su batería (el error <0.1 bpm reportado es
"truncamiento sub-muestra a 250 Hz"). Sin discrepancia entre el fs de
producción y el fs de validación -- confirmado por grep antes de escribir
esta clase, no asumido.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Union

import numpy as np

ArrayOrScalar = Union[float, np.ndarray]

# Matriz de parámetros del validador -- EXACTA, no aproximada.
_WAVE_NAMES = ("P", "Q", "R", "S", "T")
_A_MV = {"P": 0.15, "Q": -0.20, "R": 1.50, "S": -0.40, "T": 0.40}
_B_RAD = {"P": 0.25, "Q": 0.10, "R": 0.10, "S": 0.10, "T": 0.40}
# θ_P/Q/R/S son fijos; θ_T es dinámico (ver _theta_t_bazett) -- no vive aquí.
_THETA_RAD = {"P": -np.pi / 3, "Q": -np.pi / 12, "R": 0.0, "S": np.pi / 12}


@dataclass(frozen=True)
class DynamicEcgResult:
    """Salida de `DynamicECGGenerator.generate()`."""
    signal: np.ndarray
    fs: float
    hr: np.ndarray  # HR instantánea usada por muestra (bpm) -- útil para validación


def _wrap_to_pi(delta: np.ndarray) -> np.ndarray:
    """Envuelve una diferencia angular a (−π, π] -- distancia mínima con
    signo sobre el círculo. Necesario porque θ se representa en [0, 2π)
    mientras θ_P/θ_Q son negativos por convención de la tabla del
    validador."""
    return (delta + np.pi) % (2 * np.pi) - np.pi


class DynamicECGGenerator:
    """Generador dinámico de ECG (McSharry et al. 2003) -- oscilador de
    fase angular + suma de 5 gaussianas + restitución QT de Bazett.
    Vectorizado en NumPy; ver docstring de módulo para las fórmulas
    exactas."""

    def __init__(self, fs: float = 250.0):
        self.fs = float(fs)

    def generate(
        self,
        duration: float,
        hr: ArrayOrScalar,
        noise_std: float = 0.0,
        baseline_wander_mv: float = 0.0,
        baseline_wander_hz: float = 0.1,
        seed: "int | None" = None,
    ) -> np.ndarray:
        """Genera `duration` segundos de ECG sintético a `self.fs`.

        `hr` puede ser un escalar (HR constante, el caso de uso del modo
        demo) o un array de longitud `int(fs*duration)` (HR variable en el
        tiempo -- el modelo lo soporta porque ω(t)/θ_T(t) son funciones de
        HR(t), no de una constante).

        `noise_std`/`baseline_wander_mv` son puramente cosméticos (realismo
        visual) -- CERO por defecto, para que el modelo validado (P-Q-R-S-T
        + Bazett) sea exactamente el que se mide, sin nada añadido que el
        validador no especificó. Los llamadores que quieran textura visual
        los pasan explícitos."""
        n_samples = int(round(self.fs * duration))
        dt = 1.0 / self.fs

        hr_arr = np.full(n_samples, float(hr), dtype=float) if np.isscalar(hr) else np.asarray(hr, dtype=float)
        if hr_arr.shape[0] != n_samples:
            raise ValueError(f"hr array length {hr_arr.shape[0]} != n_samples {n_samples}")

        omega = 2.0 * np.pi * hr_arr / 60.0  # ω(t) = 2π·HR(t)/60
        theta_raw = np.cumsum(omega * dt)  # ∫ω dt discretizada (suma acumulada)
        theta = theta_raw % (2.0 * np.pi)  # fase envuelta [0, 2π), reinicia cada latido

        theta_t_dynamic = self._theta_t_bazett(hr_arr)  # Bazett: θ_T(HR), NO constante

        z = np.zeros(n_samples, dtype=float)
        for wave in _WAVE_NAMES:
            a = _A_MV[wave]
            b = _B_RAD[wave]
            theta_i = theta_t_dynamic if wave == "T" else np.full(n_samples, _THETA_RAD[wave])
            delta = _wrap_to_pi(theta - theta_i)
            z += a * np.exp(-(delta ** 2) / (2.0 * b ** 2))

        if baseline_wander_mv:
            t = np.arange(n_samples) * dt
            z = z + baseline_wander_mv * np.sin(2.0 * np.pi * baseline_wander_hz * t)

        if noise_std:
            rng = np.random.default_rng(seed)
            z = z + rng.normal(0.0, noise_std, n_samples)

        return z

    @staticmethod
    def _theta_t_bazett(hr: np.ndarray) -> np.ndarray:
        """Restitución QT de Bazett: θ_T(HR) = θ_R + (π/2)·√(HR/60), con
        θ_R = 0 (fiducial) -- así θ_T(HR) = (π/2)·√(HR/60). A 60bpm da π/2
        (coincide con la base de la tabla); a HR alto, θ_T avanza MENOS que
        linealmente (raíz cuadrada), evitando que la T colisione con el
        QRS del latido siguiente."""
        return (np.pi / 2.0) * np.sqrt(np.clip(hr, 1e-6, None) / 60.0)
