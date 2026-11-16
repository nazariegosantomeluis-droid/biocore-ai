"""ECG sintético de 12 derivaciones con verdad conocida (2026-11-14, Art. I).

Lo usa la pestaña 12 Derivaciones del ECG Lab. Reemplaza ahí a `TwelveLeadEcgGenerator`
(su QRS ocupaba el 20 % del ciclo, la P se encimaba con el QRS, los bloqueos solo
escalaban amplitudes y aVL/aVF no seguían a Goldberger) y a los «12 canales» que eran
una sola derivación escalada (FA, flutter, WPW y QT largo). `TwelveLeadEcgGenerator`
sigue alimentando al gemelo (`domain/physiology/ml/ecg_signal_source.py`): cambiar eso
toca `domain/` y queda para Luis (CHANGELOG).

Cómo se construye un latido (tiempos relativos al inicio del QRS):

- P de −PR a −PR + duración de P; QRS de 0 a QRS; la T termina en el QT, con
  QT = QTc·√RR (Bazett, la fórmula que usa el analizador) y QTc de 415 ms
  (520 ms en el QT largo). El fin de la T es el de la tangente en su pendiente de
  bajada, como se mide (Postema & Wilde 2014).
- Plano frontal: cada componente (P, q, R, s, R′, onda delta, ST, T) es un vector
  (amplitud, ángulo; 0° = I, +90° = aVF). I y II son sus proyecciones; III, aVR,
  aVL y aVF salen de I y II por Einthoven y Goldberger, así que se cumplen exactas
  también con el ruido.
- Precordiales: una amplitud por derivación y componente (progresión de la R de V1
  a V6).

Las amplitudes son ilustrativas: no salen de una fuente. Los tiempos y los rasgos
que evalúa el analizador (`twelve_lead_measure`) se construyen con valores que
cumplen, o no, los criterios citados ahí: QRS ≥ 120 ms con rsR′ en V1 y S ancha en I
y V6; R ancha con muesca y sin q en I, aVL, V5 y V6; ST en el punto J por encima de
los umbrales de la ESC 2023; PR < 120 ms con onda delta; voltaje de Sokolow-Lyon;
QTc. `TwelveLeadTruth` devuelve esa verdad aparte, calculada del modelo sin ruido,
para que las pruebas comparen lo que mide el analizador; el analizador nunca la lee.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional, Tuple

import numpy as np
from scipy.signal import sawtooth

from src.signals.ecg.twelve_lead_analyzer import qrs_axis_from_net

SCENARIOS: Tuple[str, ...] = (
    "normal", "tachycardia", "bradycardia", "anterior_stemi", "inferior_stemi", "lateral_stemi",
    "rbbb", "lbbb", "lvh", "af", "flutter", "wpw", "long_qt",
)
LIMB_LEADS: Tuple[str, ...] = ("I", "II", "III", "aVR", "aVL", "aVF")
PRECORDIAL_LEADS: Tuple[str, ...] = ("V1", "V2", "V3", "V4", "V5", "V6")
LEADS: Tuple[str, ...] = LIMB_LEADS + PRECORDIAL_LEADS

QTC_NORMAL_MS = 415.0              # QTc normal (Rautaharju 2009: prolongado ≥ 450/460, corto ≤ 390)
QTC_LONG_QT_MS = 520.0
DEFAULT_ST_ELEVATION_MV = 0.3      # magnitud de referencia del infarto; el control de la página la escala
DEFAULT_QRS_MS = 90.0
DEFAULT_PR_MS = 160.0
FLUTTER_ATRIAL_RATE_BPM = 300.0    # flutter típico (Page 2015: ciclo de 200 ms)
_TANGENT_FRACTION = 0.5 + 1.0 / np.pi   # fin de T por tangente en una bajada de medio coseno (ver _t_wave)


@dataclass(frozen=True)
class _Wave:
    """Una componente del latido: tiempo (ms desde el inicio del QRS), vector frontal y precordiales."""

    start_ms: float
    dur_ms: float
    frontal_mv: float
    frontal_deg: float
    precordial_mv: Tuple[float, float, float, float, float, float]
    shape: str = "hann"            # "hann" | "rise" (sube rápido: onda delta)


@dataclass(frozen=True)
class _BeatPlan:
    pr_ms: Optional[float]          # None: sin onda P (FA, flutter)
    p_dur_ms: float
    qrs_ms: float
    qt_ms: float
    waves: Tuple[_Wave, ...]        # P y QRS
    t_frontal: Tuple[float, float]  # (mV, grados)
    t_precordial: Tuple[float, ...]
    st_frontal: Tuple[float, float] = (0.0, 0.0)
    st_precordial: Tuple[float, ...] = (0.0,) * 6


@dataclass(frozen=True)
class TwelveLeadTruth:
    """Lo que el generador construyó (sin ruido). Solo para pruebas y para la vista «qué se generó»."""

    scenario: str
    fs: float
    heart_rate_bpm: float
    qrs_onsets_s: Tuple[float, ...]
    rhythm: str                                 # "sinusal" | "fa" | "flutter"
    pr_ms: Optional[float]
    qrs_ms: float
    qt_ms: float
    qtc_bazett_ms: float
    axis_deg: float
    st_j_mv: Mapping[str, float]
    bundle_branch_block: Optional[str]          # "derecha" | "izquierda"
    preexcitation: bool
    sokolow_lyon_mv: float                      # S de V1 + R mayor de V5/V6
    ravl_mv: float
    atrial_rate_bpm: Optional[float] = None
    notes: Tuple[str, ...] = field(default_factory=tuple)


def _hann(t: np.ndarray, start: float, dur: float) -> np.ndarray:
    x = (t - start) / dur
    out = 0.5 * (1.0 - np.cos(2.0 * np.pi * x))
    return np.where((x >= 0.0) & (x <= 1.0), out, 0.0)


def _rise(t: np.ndarray, start: float, dur: float) -> np.ndarray:
    """Onda delta: rampa lineal durante el 35 % de `dur` y bajada en medio coseno.

    La rampa no se aplana antes de que empiece la R (que se encima a partir del 30 %): una meseta ahí
    partía el QRS en dos y el inicio de la delta quedaba fuera."""
    x = (t - start) / dur
    up = np.clip(x / 0.35, 0.0, 1.0)
    down = 0.5 * (1.0 + np.cos(np.pi * np.clip((x - 0.35) / 0.65, 0.0, 1.0)))
    out = np.where(x < 0.35, up, down)
    return np.where((x >= 0.0) & (x <= 1.0), out, 0.0)


def _t_timing(qt_ms: float, qrs_ms: float) -> Tuple[float, float, float]:
    """(inicio, pico, duración de la bajada) de la T, en ms desde el inicio del QRS.

    En una bajada de medio coseno de duración F, la tangente en la pendiente máxima corta la línea de
    base a (1/2 + 1/π)·F del pico: se coloca la T para que ese corte caiga justo en el QT."""
    t_dur = 0.42 * qt_ms
    t_on = qt_ms - (0.6 + 0.4 * _TANGENT_FRACTION) * t_dur
    if t_on < qrs_ms + 20.0:                                  # FC muy alta: se acorta la T, el ST queda ≥ 20 ms
        t_on = qrs_ms + 20.0
        t_dur = (qt_ms - t_on) / (0.6 + 0.4 * _TANGENT_FRACTION)
    return t_on, t_on + 0.6 * t_dur, 0.4 * t_dur


def _t_wave(t: np.ndarray, qt_ms: float, qrs_ms: float) -> np.ndarray:
    """Onda T asimétrica: sube en medio coseno y baja en otro más corto."""
    t_on, peak, fall = _t_timing(qt_ms, qrs_ms)
    rise = 0.5 * (1.0 - np.cos(np.pi * np.clip((t - t_on) / (peak - t_on), 0.0, 1.0)))
    down = 0.5 * (1.0 + np.cos(np.pi * np.clip((t - peak) / fall, 0.0, 1.0)))
    shape = np.where(t < peak, rise, down)
    return np.where((t >= t_on) & (t <= peak + fall), shape, 0.0)


def _st_shape(t: np.ndarray, qrs_ms: float, qt_ms: float) -> np.ndarray:
    """Desnivel del ST: sube en el último 30 % del QRS (vale 1 en el punto J), se mantiene hasta el pico de
    la T y vuelve a 0 en el fin de la T (QT)."""
    ramp0 = 0.7 * qrs_ms
    _, peak, _ = _t_timing(qt_ms, qrs_ms)
    rise = 0.5 * (1.0 - np.cos(np.pi * np.clip((t - ramp0) / (qrs_ms - ramp0), 0.0, 1.0)))
    fall = 0.5 * (1.0 + np.cos(np.pi * np.clip((t - peak) / max(qt_ms - peak, 1.0), 0.0, 1.0)))
    return np.where(t < ramp0, 0.0, np.where(t < peak, rise, fall))


def _project(frontal_mv: float, frontal_deg: float) -> Tuple[float, float]:
    """Proyección de un vector frontal sobre I (0°) y II (+60°)."""
    th = np.radians(frontal_deg)
    return frontal_mv * np.cos(th), frontal_mv * np.cos(th - np.radians(60.0))


def _qtc_to_qt(qtc_ms: float, rr_s: float) -> float:
    return qtc_ms * np.sqrt(rr_s)


def _plan(scenario: str, rr_s: float, qrs_ms: float, pr_ms: float, p_amp: float, st_mv: float,
          qtc_ms: Optional[float] = None) -> _BeatPlan:
    """Componentes del latido de cada escenario. Amplitudes ilustrativas; tiempos según el escenario."""
    qtc = qtc_ms if qtc_ms is not None else (QTC_LONG_QT_MS if scenario == "long_qt" else QTC_NORMAL_MS)
    p_scale = p_amp / 0.15
    p_precordial = tuple(p_scale * v for v in (0.06, 0.08, 0.08, 0.08, 0.08, 0.08))

    if scenario == "rbbb":
        q = 140.0
        waves = (
            _Wave(0.0, 0.2 * q, 0.15, 210.0, (0.25, 0.3, 0.15, -0.05, -0.1, -0.12)),
            _Wave(0.12 * q, 0.38 * q, 1.4, 60.0, (-0.6, -0.9, 0.6, 1.2, 1.3, 1.0)),
            _Wave(0.45 * q, 0.55 * q, 0.35, 200.0, (0.8, 0.6, 0.2, -0.3, -0.45, -0.5)),
        )
        t_front, t_prec = (0.3, 45.0), (-0.25, -0.15, 0.2, 0.3, 0.3, 0.25)
        st_front, st_prec = (0.0, 0.0), (0.0,) * 6
        pr = pr_ms
    elif scenario == "lbbb":
        q = 150.0
        waves = (
            _Wave(0.0, 0.3 * q, 0.45, 0.0, (0.1, 0.1, 0.1, 0.2, 0.35, 0.4)),
            _Wave(0.25 * q, 0.5 * q, 1.1, -10.0, (-1.4, -1.8, -1.0, 0.5, 1.1, 1.0)),
            _Wave(0.5 * q, 0.5 * q, 0.95, -30.0, (-1.1, -1.4, -0.6, 0.4, 0.95, 0.9)),
        )
        # ST y T opuestos al QRS (cambios secundarios del bloqueo)
        t_front, t_prec = (0.4, 170.0), (0.4, 0.5, 0.3, -0.1, -0.3, -0.35)
        st_front, st_prec = (0.1, 170.0), (0.15, 0.2, 0.1, 0.0, -0.08, -0.1)
        pr = pr_ms
    elif scenario == "wpw":
        q = 130.0
        waves = (
            _Wave(0.0, 0.75 * q, 0.4, 60.0, (0.15, 0.2, 0.3, 0.35, 0.35, 0.3), shape="rise"),
            _Wave(0.24 * q, 0.42 * q, 1.2, 60.0, (0.3, 0.6, 0.9, 1.3, 1.3, 1.0)),
            _Wave(0.65 * q, 0.35 * q, 0.3, 240.0, (-0.4, -0.5, -0.5, -0.4, -0.2, -0.1)),
        )
        t_front, t_prec = (0.25, 45.0), (0.05, 0.15, 0.25, 0.25, 0.2, 0.2)
        st_front, st_prec = (0.0, 0.0), (0.0,) * 6
        pr = 100.0
    else:
        q = qrs_ms
        main_amp, main_deg = 1.3, 60.0
        main_prec = (-1.0, -1.3, 0.7, 1.3, 1.4, 1.1)
        septal_prec = (0.3, 0.4, 0.2, -0.05, -0.1, -0.12)
        term_prec = (-0.1, -0.15, -0.8, -0.45, -0.2, -0.1)
        t_front, t_prec = (0.35, 45.0), (0.05, 0.25, 0.35, 0.35, 0.3, 0.25)
        st_front, st_prec = (0.0, 0.0), (0.0,) * 6
        if scenario == "lvh":
            q = max(qrs_ms, 100.0)
            main_amp, main_deg = 1.9, 10.0
            main_prec = (-1.8, -2.2, 0.4, 1.9, 2.6, 2.2)
            septal_prec = (0.3, 0.4, 0.2, -0.05, -0.12, -0.15)
            term_prec = (-0.1, -0.2, -0.9, -0.4, -0.15, -0.1)
            # «sobrecarga»: depresión del ST asociada a la hipertrofia y T opuesta en las derivaciones de R alta
            t_front, t_prec = (0.3, 190.0), (0.2, 0.35, 0.3, 0.05, -0.25, -0.25)
            st_front, st_prec = (0.12, 190.0), (0.05, 0.05, 0.0, -0.05, -0.12, -0.12)
        factor = st_mv / DEFAULT_ST_ELEVATION_MV
        if scenario == "anterior_stemi":
            st_front = (0.08 * factor, -90.0)
            st_prec = tuple(factor * v for v in (0.2, 0.35, 0.35, 0.25, 0.05, 0.0))
        elif scenario == "inferior_stemi":
            st_front = (0.3 * factor, 105.0)
        elif scenario == "lateral_stemi":
            st_front = (0.25 * factor, -20.0)
            st_prec = tuple(factor * v for v in (0.0, 0.0, 0.0, 0.05, 0.2, 0.2))
        waves = (
            _Wave(0.0, 0.3 * q, 0.15, 210.0, septal_prec),
            _Wave(0.18 * q, 0.5 * q, main_amp, main_deg, main_prec),
            _Wave(0.6 * q, 0.4 * q, 0.3, 240.0, term_prec),
        )
        pr = pr_ms

    rhythm_has_p = scenario not in ("af", "flutter")
    p_dur = min(100.0, pr - 40.0) if scenario != "wpw" else 80.0
    if rhythm_has_p:
        waves = (_Wave(-pr, p_dur, p_amp, 60.0, p_precordial),) + waves
    return _BeatPlan(
        pr_ms=pr if rhythm_has_p else None, p_dur_ms=p_dur, qrs_ms=q, qt_ms=_qtc_to_qt(qtc, rr_s),
        waves=waves, t_frontal=t_front, t_precordial=t_prec, st_frontal=st_front, st_precordial=st_prec,
    )


def _beat_leads(plan: _BeatPlan, t_ms: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Un latido: (I, II, precordiales (6, n)) sobre `t_ms` (relativo al inicio del QRS), sin ruido."""
    lead_i = np.zeros_like(t_ms)
    lead_ii = np.zeros_like(t_ms)
    prec = np.zeros((6, t_ms.size))
    for w in plan.waves:
        shape = (_rise if w.shape == "rise" else _hann)(t_ms, w.start_ms, w.dur_ms)
        a_i, a_ii = _project(w.frontal_mv, w.frontal_deg)
        lead_i += a_i * shape
        lead_ii += a_ii * shape
        prec += np.outer(w.precordial_mv, shape)
    t_shape = _t_wave(t_ms, plan.qt_ms, plan.qrs_ms)
    a_i, a_ii = _project(*plan.t_frontal)
    lead_i += a_i * t_shape
    lead_ii += a_ii * t_shape
    prec += np.outer(plan.t_precordial, t_shape)
    st = _st_shape(t_ms, plan.qrs_ms, plan.qt_ms)
    a_i, a_ii = _project(*plan.st_frontal)
    lead_i += a_i * st
    lead_ii += a_ii * st
    prec += np.outer(plan.st_precordial, st)
    return lead_i, lead_ii, prec


def _derive(lead_i: np.ndarray, lead_ii: np.ndarray, prec: np.ndarray) -> Dict[str, np.ndarray]:
    """Las 12 derivaciones desde I, II y las precordiales (Einthoven y Goldberger)."""
    leads = {
        "I": lead_i, "II": lead_ii, "III": lead_ii - lead_i,
        "aVR": -(lead_i + lead_ii) / 2.0, "aVL": lead_i - lead_ii / 2.0, "aVF": lead_ii - lead_i / 2.0,
    }
    leads.update({name: prec[k] for k, name in enumerate(PRECORDIAL_LEADS)})
    return leads


def _rr_series(scenario: str, heart_rate: float, duration_s: float, rng: np.random.Generator) -> np.ndarray:
    mean_rr = 60.0 / heart_rate
    n = int(np.ceil(duration_s / mean_rr)) + 3
    if scenario == "af":
        rr = np.clip(mean_rr * (1.0 + 0.2 * rng.standard_normal(n)), 0.65 * mean_rr, 1.5 * mean_rr)
        inside = max(2, int(duration_s / mean_rr))
        return rr * (mean_rr / float(np.mean(rr[:inside])))     # la FC media del registro es la pedida
    return np.full(n, mean_rr)


def generate_twelve_lead(
    scenario: str = "normal",
    heart_rate: float = 75.0,
    duration_s: float = 10.0,
    fs: float = 500.0,
    *,
    qrs_ms: float = DEFAULT_QRS_MS,
    pr_ms: float = DEFAULT_PR_MS,
    p_amplitude_mv: float = 0.15,
    st_elevation_mv: float = DEFAULT_ST_ELEVATION_MV,
    noise_mv: float = 0.01,
    baseline_wander_mv: float = 0.0,
    qtc_ms: Optional[float] = None,
    seed: int = 0,
) -> Tuple[Dict[str, np.ndarray], TwelveLeadTruth]:
    """12 derivaciones (mV) + 'time' (s), y la verdad de lo construido.

    `qrs_ms` aplica a los escenarios de QRS estrecho (los bloqueos de rama y el WPW fijan el suyo);
    `st_elevation_mv` escala el desnivel del ST de los infartos (0.3 mV = referencia)."""
    if scenario not in SCENARIOS:
        raise ValueError(f"escenario desconocido: {scenario}")
    if heart_rate <= 0:
        raise ValueError("la frecuencia cardiaca debe ser > 0")
    rng = np.random.default_rng(seed)
    n = int(round(duration_s * fs))
    t = np.arange(n) / fs
    rr = _rr_series(scenario, heart_rate, duration_s, rng)
    median_rr = float(np.median(rr))
    plan = _plan(scenario, median_rr, qrs_ms, pr_ms, p_amplitude_mv, st_elevation_mv, qtc_ms)

    lead_i = np.zeros(n)
    lead_ii = np.zeros(n)
    prec = np.zeros((6, n))
    first = (plan.pr_ms or 0.0) / 1000.0 + 0.25
    onsets: List[float] = []
    if scenario == "flutter":
        atrial_period = 60.0 / FLUTTER_ATRIAL_RATE_BPM
        rr = np.full_like(rr, 2.0 * atrial_period)          # conducción 2:1
        median_rr = float(rr[0])
        plan = _plan(scenario, median_rr, qrs_ms, pr_ms, p_amplitude_mv, st_elevation_mv, qtc_ms)
    onset = first
    k = 0
    while onset < duration_s + 0.2 and k < rr.size:
        beat_plan = plan if scenario != "af" else _plan(scenario, float(rr[k]), qrs_ms, pr_ms, p_amplitude_mv,
                                                        st_elevation_mv, qtc_ms)
        lo = max(0, int((onset - 0.4) * fs))
        hi = min(n, int((onset + 0.9) * fs))
        if hi > lo:
            t_ms = (t[lo:hi] - onset) * 1000.0
            b_i, b_ii, b_prec = _beat_leads(beat_plan, t_ms)
            lead_i[lo:hi] += b_i
            lead_ii[lo:hi] += b_ii
            prec[:, lo:hi] += b_prec
        if onset < duration_s:
            onsets.append(onset)
        onset += float(rr[k])
        k += 1

    atrial_rate = None
    if scenario == "af":                                     # ondas f: irregulares, sin P
        f_wave = np.zeros(n)
        for freq in (5.6, 6.7, 7.9):
            phase = np.cumsum(rng.normal(0.0, 0.08, n))
            f_wave += np.sin(2 * np.pi * freq * t + rng.uniform(0, 2 * np.pi) + phase) / 3.0
        a_i, a_ii = _project(0.05, 60.0)
        lead_i += a_i * f_wave
        lead_ii += a_ii * f_wave
        prec += np.outer((0.08, 0.05, 0.03, 0.03, 0.03, 0.03), f_wave)
    elif scenario == "flutter":                              # ondas F en sierra a 300/min, negativas en II, III y aVF
        atrial_rate = FLUTTER_ATRIAL_RATE_BPM
        f_wave = sawtooth(2 * np.pi * (FLUTTER_ATRIAL_RATE_BPM / 60.0) * (t - first + 0.03), width=0.8)
        a_i, a_ii = _project(0.2, -90.0)
        lead_i += a_i * f_wave
        lead_ii += a_ii * f_wave
        prec += np.outer((0.1, 0.06, 0.02, 0.02, 0.02, 0.02), f_wave)

    if baseline_wander_mv > 0:
        wander = baseline_wander_mv * np.sin(2 * np.pi * 0.25 * t + rng.uniform(0, 2 * np.pi))
        lead_i += wander
        lead_ii += 0.8 * wander
        prec += np.outer(np.linspace(0.6, 1.0, 6), wander)
    if noise_mv > 0:
        lead_i = lead_i + rng.normal(0.0, noise_mv, n)
        lead_ii = lead_ii + rng.normal(0.0, noise_mv, n)
        prec = prec + rng.normal(0.0, noise_mv, prec.shape)

    leads = _derive(lead_i, lead_ii, prec)
    leads["time"] = t
    truth = _truth(scenario, plan, fs, median_rr, onsets, atrial_rate)
    return leads, truth


def _truth(scenario: str, plan: _BeatPlan, fs: float, median_rr: float, onsets: List[float],
           atrial_rate: Optional[float]) -> TwelveLeadTruth:
    """Verdad del modelo sin ruido: un latido aislado (sin ondas auriculares de FA o flutter)."""
    t_ms = np.arange(-400.0, 900.0, 1000.0 / fs)
    b_i, b_ii, b_prec = _beat_leads(plan, t_ms)
    beat = _derive(b_i, b_ii, b_prec)
    qrs = (t_ms >= 0.0) & (t_ms <= plan.qrs_ms)
    j_idx = int(np.argmin(np.abs(t_ms - plan.qrs_ms)))
    axis = qrs_axis_from_net(float(np.mean(beat["I"][qrs])), float(np.mean(beat["aVF"][qrs])))
    st_j = {lead: round(float(beat[lead][j_idx]), 4) for lead in LEADS}
    sv1 = float(-np.min(beat["V1"][qrs]))
    rv56 = float(max(np.max(beat["V5"][qrs]), np.max(beat["V6"][qrs])))
    bbb = {"rbbb": "derecha", "lbbb": "izquierda"}.get(scenario)
    rhythm = {"af": "fa", "flutter": "flutter"}.get(scenario, "sinusal")
    return TwelveLeadTruth(
        scenario=scenario, fs=fs, heart_rate_bpm=60.0 / median_rr if scenario != "af" else
        60.0 * (len(onsets) - 1) / (onsets[-1] - onsets[0]),
        qrs_onsets_s=tuple(onsets), rhythm=rhythm, pr_ms=plan.pr_ms, qrs_ms=plan.qrs_ms, qt_ms=plan.qt_ms,
        qtc_bazett_ms=plan.qt_ms / np.sqrt(median_rr), axis_deg=axis.axis_degrees, st_j_mv=st_j,
        bundle_branch_block=bbb, preexcitation=scenario == "wpw", sokolow_lyon_mv=sv1 + rv56,
        ravl_mv=float(np.max(beat["aVL"][qrs])), atrial_rate_bpm=atrial_rate,
    )
