"""Ondas fisiológicas sintéticas DETERMINISTAS para ilustrar (2026-10-19).

No son señales de paciente ni sustituyen a los generadores de los
laboratorios (`src/signals/`): son modelos pequeños y legibles para dibujar
esquemas. Toda aleatoriedad usa `np.random.default_rng(seed)` local -- nunca
el estado global de NumPy -- para que la misma llamada dibuje siempre lo
mismo.

ECG: suma de gaussianas por onda (la idea de ECGSYN, McSharry et al. 2003,
IEEE Trans Biomed Eng 50:289-294, simplificada a tiempo en vez de fase).
Los parámetros de `NORMAL_BEAT` se eligieron para que los intervalos que
resultan caigan dentro de los rangos de referencia del adulto que ya usa la
app (`app/supermodules/ecg_12/page_content.py`): PR 120-200 ms, QRS < 120
ms, QTc < 450 ms. `beat_intervals()` los MIDE sobre el propio modelo; las
láminas rotulan esos valores medidos, no números escritos a mano.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Sequence, Tuple

import numpy as np

# Una onda dura ±K_SIGMA desviaciones alrededor de su centro (99 % del área).
K_SIGMA = 2.5


@dataclass(frozen=True)
class Wave:
    name: str
    amp_mv: float
    center_s: float  # relativo al pico R
    sigma_s: float

    @property
    def onset(self) -> float:
        return self.center_s - K_SIGMA * self.sigma_s

    @property
    def offset(self) -> float:
        return self.center_s + K_SIGMA * self.sigma_s


NORMAL_BEAT: Tuple[Wave, ...] = (
    Wave("P", 0.15, -0.170, 0.022),
    Wave("Q", -0.12, -0.028, 0.008),
    Wave("R", 1.20, 0.000, 0.010),
    Wave("S", -0.25, 0.025, 0.009),
    Wave("T", 0.30, 0.250, 0.042),
)


def wave_map(waves: Sequence[Wave] = NORMAL_BEAT) -> Dict[str, Wave]:
    return {w.name: w for w in waves}


def beat(t_rel: np.ndarray, waves: Sequence[Wave] = NORMAL_BEAT) -> np.ndarray:
    """Un latido (mV) en función del tiempo relativo al pico R (s)."""
    t_rel = np.asarray(t_rel, dtype=float)
    out = np.zeros_like(t_rel)
    for w in waves:
        out += w.amp_mv * np.exp(-0.5 * ((t_rel - w.center_s) / w.sigma_s) ** 2)
    return out


def ecg(t: np.ndarray, r_times: Iterable[float], waves: Sequence[Wave] = NORMAL_BEAT) -> np.ndarray:
    """Tira de ECG: un latido `beat()` centrado en cada tiempo de R."""
    t = np.asarray(t, dtype=float)
    out = np.zeros_like(t)
    for r in r_times:
        near = (t > r - 0.6) & (t < r + 0.7)
        out[near] += beat(t[near] - r, waves)
    return out


def regular_r_times(duration_s: float, hr_bpm: float, first_s: float = 0.35) -> np.ndarray:
    rr = 60.0 / hr_bpm
    return np.arange(first_s, duration_s + rr, rr)


def beat_intervals(waves: Sequence[Wave] = NORMAL_BEAT) -> Dict[str, float]:
    """Intervalos del latido modelo, en segundos, medidos sobre las ondas.

    PR = inicio de P -> inicio de QRS; QRS = inicio de Q -> fin de S;
    QT = inicio de QRS -> fin de T; ST = fin de S (punto J) -> inicio de T.
    """
    m = wave_map(waves)
    qrs_on = m["Q"].onset if "Q" in m else m["R"].onset
    qrs_off = m["S"].offset if "S" in m else m["R"].offset
    return {
        "P": m["P"].offset - m["P"].onset,
        "PR": qrs_on - m["P"].onset,
        "QRS": qrs_off - qrs_on,
        "ST": m["T"].onset - qrs_off,
        "QT": m["T"].offset - qrs_on,
        "p_on": m["P"].onset,
        "p_off": m["P"].offset,
        "qrs_on": qrs_on,
        "qrs_off": qrs_off,
        "t_on": m["T"].onset,
        "t_off": m["T"].offset,
    }


def breathing(t: np.ndarray, rate_rpm: float = 15.0, insp_fraction: float = 0.4) -> np.ndarray:
    """Excursión torácica 0..1: inspiración más rápida que la espiración."""
    t = np.asarray(t, dtype=float)
    period = 60.0 / rate_rpm
    p = np.mod(t / period, 1.0)
    rise = 0.5 * (1 - np.cos(np.pi * p / insp_fraction))
    fall = 0.5 * (1 + np.cos(np.pi * (p - insp_fraction) / (1 - insp_fraction)))
    return np.where(p < insp_fraction, rise, fall)


def eeg_band(t: np.ndarray, freq_hz: float, amp: float = 1.0, seed: int = 0) -> np.ndarray:
    """Ritmo de una banda: senoide con fase y modulación lenta deterministas."""
    rng = np.random.default_rng(seed)
    t = np.asarray(t, dtype=float)
    phase = rng.uniform(0, 2 * np.pi)
    wobble = 1.0 + 0.22 * np.sin(2 * np.pi * 0.45 * t + rng.uniform(0, 2 * np.pi))
    jitter = 0.06 * np.sin(2 * np.pi * freq_hz * 0.13 * t + phase)
    return amp * wobble * np.sin(2 * np.pi * freq_hz * t + phase + jitter)


def eeg_alpha(t: np.ndarray, seed: int = 3) -> np.ndarray:
    """EEG con alfa dominante (ojos cerrados): ~10 Hz que crece y decrece."""
    t = np.asarray(t, dtype=float)
    rng = np.random.default_rng(seed)
    envelope = 0.65 + 0.35 * np.sin(2 * np.pi * 0.32 * t) ** 2
    alpha = envelope * np.sin(2 * np.pi * 10.0 * t + 0.4 * np.sin(2 * np.pi * 0.7 * t))
    beta = 0.18 * np.sin(2 * np.pi * 21.0 * t + 1.1)
    theta = 0.22 * np.sin(2 * np.pi * 5.5 * t + 0.3)
    noise = 0.08 * rng.standard_normal(t.size)
    return alpha + beta + theta + noise


def emg_bursts(t: np.ndarray, burst_times: Sequence[float], width_s: float = 0.55,
               seed: int = 11) -> np.ndarray:
    """EMG de superficie: patrón de interferencia modulado por contracciones."""
    t = np.asarray(t, dtype=float)
    rng = np.random.default_rng(seed)
    envelope = 0.06 + sum(np.exp(-0.5 * ((t - c) / (width_s / 2.355)) ** 2) for c in burst_times)
    return envelope * rng.standard_normal(t.size)


def ppg(t: np.ndarray, r_times: Iterable[float]) -> np.ndarray:
    """Onda de pulso (fotopletismografía): pico sistólico + onda dicrótica."""
    t = np.asarray(t, dtype=float)
    out = np.zeros_like(t)
    for r in r_times:
        rel = t - r
        near = (rel > -0.1) & (rel < 1.2)
        x = rel[near]
        out[near] += 1.0 * np.exp(-0.5 * ((x - 0.30) / 0.075) ** 2)
        out[near] += 0.38 * np.exp(-0.5 * ((x - 0.58) / 0.095) ** 2)
    return out


def rr_series(n: int, mean_ms: float = 860.0, rsa_ms: float = 38.0, lf_ms: float = 14.0,
              seed: int = 5) -> np.ndarray:
    """Serie RR con arritmia sinusal respiratoria (≈ 1 ciclo cada 4.5 latidos)."""
    rng = np.random.default_rng(seed)
    k = np.arange(n)
    return (mean_ms + rsa_ms * np.sin(2 * np.pi * k / 4.5)
            + lf_ms * np.sin(2 * np.pi * k / 13.0 + 0.6)
            + 6.0 * rng.standard_normal(n))
