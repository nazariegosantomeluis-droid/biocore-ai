"""
Acoplamiento cardiopulmonar -- arritmia sinusal respiratoria (RSA),
2026-10-19. Cardiovascular profundo, sub-arco RSA.

La cadena se construye DENTRO de un solo generador: la fase respiratoria
modula la FC instantánea -> `DynamicECGGenerator.generate(hr=array)`
(McSharry 2003, que admite HR(t)) -> el llamador detecta los picos R con el
TKEO -> RR con estructura respiratoria real -> `detect_rsa()`. NO se cruzan
el Respiratory Lab y el ECG Lab a través del UPS: ese cruce es el bloqueo
multidominio todavía abierto (el mismo del neuro->CV y del PLV), y fingirlo
sería deshonesto.

Este módulo es puro (numpy/scipy): no importa `clinical/` ni el UPS. El
detector recibe los instantes de los picos R (de quien los haya detectado) y
la señal respiratoria.

Modelo del generador: volumen pulmonar normalizado V(t) = -cos(φ), con
φ = 2π·f_resp·t (la inspiración es el tramo en que V sube); FC(t) =
FC_base - A·cos(φ), en fase con el volumen: la FC sube durante la
inspiración y baja durante la espiración (freno vagal que se retira y se
reaplica). A es la amplitud de la RSA en lpm (la mitad del pico a pico).
Ground truth por construcción: A, f_resp y fase 0° entre FC y volumen.

NOTA DE HONESTIDAD (Art. IV): señal SINTÉTICA con RSA prescrita
matemáticamente -- sinusoidal, sin la asimetría inspiración/espiración ni el
retardo del reflejo real, sin variabilidad no respiratoria (ondas de Mayer,
LF). Es un demostrador del fenómeno, no un modelo de un paciente.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np
from scipy.interpolate import CubicSpline
from scipy.signal import csd, welch

RSA_CITATION: str = (
    "Task Force of the ESC and NASPE (1996). Heart rate variability: standards of measurement, "
    "physiological interpretation and clinical use. Circulation 93(5):1043-1065 -- la potencia HF "
    "(0.15-0.40 Hz) refleja la modulación vagal respiratoria (RSA)"
)

RSA_SCOPE_NOTE: str = (
    "demostración del fenómeno sobre ECG sintético: la respiración modula la FC dentro de un mismo "
    "generador; no se combinan registros de laboratorios distintos ni es un índice de tono vagal de un "
    "paciente."
)

# Bandas y remuestreo del HRV Lab (Task Force 1996) -- una sola definición,
# la usan `rr_spectrum()` aquí y `render_hrv_page()`.
LF_BAND_HZ: Tuple[float, float] = (0.04, 0.15)
HF_BAND_HZ: Tuple[float, float] = (0.15, 0.40)
RR_INTERP_FS_HZ: float = 4.0
_RR_WELCH_NPERSEG: int = 256

# Task Force 1996: la ventana debe durar al menos 10 veces el periodo del
# límite inferior de la banda -- 10/0.15 Hz ≈ 67 s para HF.
MIN_RSA_DURATION_S: float = 10.0 / HF_BAND_HZ[0]

# Latidos por ciclo respiratorio mínimos: la serie RR muestrea la respiración
# a la frecuencia cardíaca (Nyquist = FC/2). Medido (2026-10-19, 60 combinaciones
# FC x amplitud x rpm): por debajo de 3 latidos por respiración la amplitud
# recuperada cae -20 a -37% (p.ej. 50 lpm a 20 rpm); en 3-3.5 el sesgo es <=10%.
MIN_BEATS_PER_BREATH: float = 3.0

# Semiancho de la integración alrededor de f_resp para la amplitud: cubre el
# lóbulo principal de la ventana de Hann (±2 bins de 1/64 s a 4 Hz).
_PEAK_HALF_WIDTH_HZ: float = 0.04


@dataclass(frozen=True)
class RsaParams:
    """Parámetros del generador -- el ground truth del detector."""

    hr_base_bpm: float = 72.0
    rsa_amplitude_bpm: float = 5.0
    respiratory_rate_rpm: float = 15.0

    def __post_init__(self):
        if not 30.0 <= self.hr_base_bpm <= 200.0:
            raise ValueError(f"hr_base_bpm debe estar en [30, 200], recibido {self.hr_base_bpm}")
        if not 0.0 <= self.rsa_amplitude_bpm < self.hr_base_bpm - 20.0:
            raise ValueError(
                f"rsa_amplitude_bpm debe estar en [0, hr_base_bpm-20), recibido {self.rsa_amplitude_bpm}"
            )
        if self.respiratory_rate_rpm <= 0.0:
            raise ValueError(f"respiratory_rate_rpm debe ser > 0, recibido {self.respiratory_rate_rpm}")

    @property
    def respiratory_freq_hz(self) -> float:
        return self.respiratory_rate_rpm / 60.0


@dataclass(frozen=True)
class RsaSignals:
    time: np.ndarray
    respiration: np.ndarray  # volumen pulmonar normalizado, -1..1
    heart_rate_bpm: np.ndarray  # FC instantánea prescrita, muestra a muestra
    ecg: np.ndarray


def generate_rsa_signals(params: RsaParams, duration_s: float, fs: float = 250.0) -> RsaSignals:
    """Respiración y FC con RSA muestra a muestra, y el ECG que esa FC
    produce. El ECG es `DynamicECGGenerator` sin ruido añadido."""
    from .dynamic_ecg_generator import DynamicECGGenerator

    n = int(round(duration_s * fs))
    time = np.arange(n) / fs
    phase = 2.0 * np.pi * params.respiratory_freq_hz * time
    respiration = -np.cos(phase)
    heart_rate = params.hr_base_bpm + params.rsa_amplitude_bpm * respiration
    ecg = DynamicECGGenerator(fs=fs).generate(duration=duration_s, hr=heart_rate)
    return RsaSignals(time=time, respiration=respiration, heart_rate_bpm=heart_rate, ecg=ecg)


def rr_spectrum(rr_ms: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """PSD (ms²/Hz) de una serie RR: tiempos por suma acumulada, spline
    cúbico a `RR_INTERP_FS_HZ`, Welch sobre la serie sin media. Reemplaza el
    cálculo en línea del HRV Lab, que interpolaba linealmente: la
    interpolación lineal atenúa la banda HF como sinc²(f/f_latido) -- medido
    aquí, ~14% a 15 rpm y 72 lpm --; el spline cúbico es el remuestreo
    habitual en HRV y no tiene esa pérdida apreciable."""
    rr_ms = np.asarray(rr_ms, dtype=float)
    t = np.cumsum(rr_ms) / 1000.0
    t = t - t[0]
    ti = np.arange(0.0, t[-1], 1.0 / RR_INTERP_FS_HZ)
    rr_interp = CubicSpline(t, rr_ms)(ti)
    return welch(rr_interp - np.mean(rr_interp), fs=RR_INTERP_FS_HZ, nperseg=min(_RR_WELCH_NPERSEG, len(rr_interp)))


def band_power(freqs: np.ndarray, psd: np.ndarray, band: Tuple[float, float]) -> float:
    mask = (freqs >= band[0]) & (freqs <= band[1])
    return float(np.trapezoid(psd[mask], freqs[mask])) if np.any(mask) else 0.0


@dataclass(frozen=True)
class RSAResult:
    """Espejo de `ErdResult`/`EngagementResult`. `available=False` -> las
    magnitudes son `None` (o parciales) y `reason` explica por qué.
    `beat_times_s`/`beat_hr_bpm` (la FC latido a latido medida) viajan para
    dibujar solo cuando hay latidos suficientes para calcularlos."""

    available: bool
    rsa_amplitude_bpm: Optional[float] = None
    hf_power_ms2: Optional[float] = None
    hf_peak_fraction: Optional[float] = None
    respiratory_freq_hz: Optional[float] = None
    phase_deg: Optional[float] = None
    n_beats: int = 0
    duration_s: float = 0.0
    beat_times_s: Optional[np.ndarray] = None
    beat_hr_bpm: Optional[np.ndarray] = None
    reason: Optional[str] = None
    scope_note: str = RSA_SCOPE_NOTE


def detect_rsa(
    r_peak_times_s: np.ndarray, respiration: Optional[np.ndarray], resp_fs: float
) -> RSAResult:
    """RSA medida sobre los RR reales:

    - frecuencia respiratoria: pico del espectro de la respiración; debe
      caer en la banda HF (fuera de ella la RSA migra a LF y la lectura
      HF deja de ser la de la Task Force -> declina);
    - `hf_power_ms2`: potencia RR en 0.15-0.40 Hz (Task Force);
    - `rsa_amplitude_bpm`: amplitud de la oscilación de la FC instantánea
      (60/RR) en f_resp: A = sqrt(2·∫PSD) alrededor del pico;
    - `hf_peak_fraction`: fracción de la varianza RR (>= 0.04 Hz) que cae
      en f_resp ± 0.04 Hz -- cuánto de la variabilidad es respiratoria;
    - `phase_deg`: fase de la FC respecto de la respiración en f_resp
      (densidad espectral cruzada); 0° = en fase con el volumen.

    Declina con motivo: menos de 3 latidos, menos de `MIN_RSA_DURATION_S`
    de latidos, sin señal respiratoria (ausente o plana), frecuencia
    respiratoria fuera de la banda HF, menos de `MIN_BEATS_PER_BREATH`
    latidos por respiración.

    Límite conocido: la amplitud medida es la de la FC promediada latido a
    latido (lo único que contiene una serie RR) -- para una modulación
    sinusoidal continua de amplitud A vale A·sinc(f_resp·RR medio), ~7%
    menos a 15 rpm y 72 lpm. No se corrige con ese modelo: en un registro
    real la modulación no es una sinusoide conocida. Con picos R a 250 Hz
    (4 ms), una RSA muy pequeña a FC alta queda cerca de la cuantización."""
    peaks = np.asarray(r_peak_times_s, dtype=float).ravel()
    n_beats = int(peaks.size)
    duration_s = float(peaks[-1] - peaks[0]) if n_beats >= 2 else 0.0

    def declined(reason: str, **partial) -> RSAResult:
        return RSAResult(available=False, n_beats=n_beats, duration_s=duration_s, reason=reason, **partial)

    if respiration is None or np.asarray(respiration).size < 2 or float(np.std(respiration)) < 1e-9:
        return declined("sin señal respiratoria simultánea -- la RSA se define respecto de la respiración")
    if n_beats < 3:
        return declined(f"{n_beats} latidos detectados -- se necesitan al menos 3 para una serie RR")

    rr_s = np.diff(peaks)
    # Cada RR es la FC media de SU intervalo: se fecha en el punto medio. Fecharlo
    # al final del intervalo (la convención de `np.cumsum`) retrasa la serie RR/2 --
    # medido: -37° de fase espuria a 15 rpm y 72 lpm.
    beat_times = (peaks[:-1] + peaks[1:]) / 2.0
    beat_hr = 60.0 / rr_s
    if duration_s < MIN_RSA_DURATION_S:
        return declined(
            f"{duration_s:.0f}s de latidos -- la banda HF necesita al menos {MIN_RSA_DURATION_S:.0f}s "
            "(10 periodos de 0.15 Hz, Task Force 1996)",
            beat_times_s=beat_times, beat_hr_bpm=beat_hr,
        )

    respiration = np.asarray(respiration, dtype=float)
    f_resp_axis, p_resp = welch(respiration - np.mean(respiration), fs=resp_fs, nperseg=respiration.size)
    resp_freq = float(f_resp_axis[np.argmax(p_resp)])
    if not HF_BAND_HZ[0] <= resp_freq <= HF_BAND_HZ[1]:
        return declined(
            f"frecuencia respiratoria {resp_freq * 60:.1f} rpm fuera de la banda HF "
            f"({HF_BAND_HZ[0] * 60:.0f}-{HF_BAND_HZ[1] * 60:.0f} rpm) -- la RSA cae fuera de la banda que la "
            "Task Force asocia a la modulación respiratoria",
            respiratory_freq_hz=resp_freq, beat_times_s=beat_times, beat_hr_bpm=beat_hr,
        )

    beats_per_breath = float(np.mean(beat_hr)) / 60.0 / resp_freq
    if beats_per_breath < MIN_BEATS_PER_BREATH:
        return declined(
            f"{beats_per_breath:.1f} latidos por ciclo respiratorio -- con menos de {MIN_BEATS_PER_BREATH:.0f} la "
            "serie RR submuestrea la respiración (Nyquist = FC/2) y la amplitud de la RSA no se recupera",
            respiratory_freq_hz=resp_freq, beat_times_s=beat_times, beat_hr_bpm=beat_hr,
        )

    f_rr, p_rr = rr_spectrum(rr_s * 1000.0)
    hf_power = band_power(f_rr, p_rr, HF_BAND_HZ)
    peak_band = (resp_freq - _PEAK_HALF_WIDTH_HZ, resp_freq + _PEAK_HALF_WIDTH_HZ)
    total = band_power(f_rr, p_rr, (LF_BAND_HZ[0], RR_INTERP_FS_HZ / 2.0))
    peak_fraction = band_power(f_rr, p_rr, peak_band) / total if total > 0 else 0.0

    # FC instantánea y respiración en la misma rejilla de 4 Hz.
    grid = np.arange(beat_times[0], beat_times[-1], 1.0 / RR_INTERP_FS_HZ)
    hr_grid = CubicSpline(beat_times, beat_hr)(grid)
    resp_grid = np.interp(grid, np.arange(respiration.size) / resp_fs, respiration)
    nperseg = min(_RR_WELCH_NPERSEG, grid.size)
    f_hr, p_hr = welch(hr_grid - np.mean(hr_grid), fs=RR_INTERP_FS_HZ, nperseg=nperseg)
    amplitude = float(np.sqrt(2.0 * band_power(f_hr, p_hr, peak_band)))

    # csd(x, y) da conj(X)·Y: con x=respiración, y=FC, el ángulo es fase(FC) - fase(respiración).
    f_x, p_x = csd(resp_grid - np.mean(resp_grid), hr_grid - np.mean(hr_grid), fs=RR_INTERP_FS_HZ, nperseg=nperseg)
    phase = float(np.degrees(np.angle(p_x[np.argmin(np.abs(f_x - resp_freq))])))

    return RSAResult(
        available=True, rsa_amplitude_bpm=amplitude, hf_power_ms2=hf_power, hf_peak_fraction=peak_fraction,
        respiratory_freq_hz=resp_freq, phase_deg=phase, n_beats=n_beats, duration_s=duration_s,
        beat_times_s=beat_times, beat_hr_bpm=beat_hr,
    )
