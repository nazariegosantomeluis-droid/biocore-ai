"""Vectocardiograma (VCG) 3D a partir del ECG (2026-10-21).

El VCG representa la actividad eléctrica del corazón como un vector que
gira en el espacio durante el latido: la punta dibuja un "asa" para la onda
P, otra (la mayor) para el QRS y otra para la T.

- Con las derivaciones ortogonales de Frank (X, Y, Z) el asa se dibuja tal
  cual (p. ej., el registro real del PTB que trae la app).
- Con un ECG estándar de 12 derivaciones, X/Y/Z se reconstruyen con la
  matriz de regresión de Kors (Kors et al., 1990), la más usada y validada.

Convención de Frank (la de la matriz de Kors): X positivo hacia la
izquierda del paciente, Y positivo hacia los pies (inferior) y Z positivo
hacia la espalda (posterior). `to_anatomical()` lo convierte a RAS para
dibujarlo orientado como el cuerpo.

Todo aquí es cálculo puro (NumPy/SciPy); nada de Streamlit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Dict, Mapping, Optional, Sequence, Tuple

import numpy as np

KORS_CITATION = (
    "Kors JA, van Herpen G, Sittig AC, van Bemmel JH. Reconstruction of the Frank vectorcardiogram from "
    "standard electrocardiographic leads: diagnostic comparison of different methods. "
    "Eur Heart J. 1990;11(12):1083-1092."
)
QRST_ANGLE_CITATION = (
    "Oehler A, Feldman T, Henrikson CA, Tereshchenko LG. QRS-T angle: a review. "
    "Ann Noninvasive Electrocardiol. 2014;19(6):534-542."
)
TANGENT_CITATION = (
    "Postema PG, Wilde AAM. The measurement of the QT interval. Curr Cardiol Rev. 2014;10(3):287-294 "
    "(método de la tangente)."
)

KORS_LEADS: Tuple[str, ...] = ("I", "II", "V1", "V2", "V3", "V4", "V5", "V6")
# Filas X, Y, Z; columnas I, II, V1-V6 (Kors et al. 1990, matriz de regresión).
KORS_MATRIX = np.array([
    [0.38, -0.07, -0.13, 0.05, -0.01, 0.14, 0.06, 0.54],
    [-0.07, 0.93, 0.06, -0.02, -0.05, 0.06, -0.17, 0.13],
    [0.11, -0.23, -0.43, -0.06, -0.14, -0.20, -0.11, 0.31],
])


class LeadsMissingError(ValueError):
    """Faltan derivaciones para reconstruir el VCG."""


def normalize_lead_name(name: str) -> str:
    """'ii' -> 'II', 'v1' -> 'V1', 'aVR' -> 'AVR', 'MLII' -> 'II'."""
    s = str(name).strip().upper().replace(" ", "").replace("LEAD", "")
    if s in ("MLII", "ML2"):
        return "II"
    if s.startswith("D") and s[1:] in ("I", "II", "III"):  # DI, DII, DIII (nomenclatura latina)
        s = s[1:]
    return s


def kors_xyz(leads: Mapping[str, np.ndarray]) -> np.ndarray:
    """X, Y, Z (mV) por la matriz de Kors. `leads` acepta nombres en
    cualquier capitalización ("i", "II", "v1"...). Devuelve (n, 3)."""
    norm = {normalize_lead_name(k): np.asarray(v, dtype=float) for k, v in leads.items()}
    missing = [ld for ld in KORS_LEADS if ld not in norm]
    if missing:
        raise LeadsMissingError("Faltan derivaciones para el VCG: " + ", ".join(missing))
    stack = np.stack([norm[ld] for ld in KORS_LEADS])  # (8, n)
    return (KORS_MATRIX @ stack).T


def to_anatomical(xyz: np.ndarray) -> np.ndarray:
    """Frank (X izq., Y inf., Z post.) -> RAS (x der., y ant., z sup.)."""
    xyz = np.asarray(xyz, dtype=float)
    return np.stack([-xyz[:, 0], -xyz[:, 2], -xyz[:, 1]], axis=1)


# ─────────────────────────────────────────────────────────────────────────
# Latido mediano y asas
# ─────────────────────────────────────────────────────────────────────────

def detect_beats(signal: np.ndarray, fs: float) -> np.ndarray:
    """Picos R con el detector TKEO validado de la app (`ECGAnalyzer`)."""
    from clinical.ecg_analyzer import ECGAnalyzer

    peaks = ECGAnalyzer(fs=fs).detect_r_peaks_tkeo(np.asarray(signal, dtype=float))
    return np.asarray(peaks, dtype=int)


def _highpass(x: np.ndarray, fs: float, fc: float = 0.5) -> np.ndarray:
    from scipy.signal import butter, filtfilt

    b, a = butter(2, fc / (fs / 2), btype="high")
    return filtfilt(b, a, x, axis=0)


@dataclass(frozen=True)
class MedianBeat:
    t_ms: np.ndarray            # tiempo relativo al pico R (ms)
    xyz: np.ndarray             # (m, 3) mV, convención de Frank
    n_beats: int
    fs: float
    rr_ms: float


def median_beat(xyz: np.ndarray, r_peaks: Sequence[int], fs: float, *, pre_ms: float = 250.0,
                post_ms: Optional[float] = None) -> MedianBeat:
    """Latido mediano (mediana muestra a muestra de los latidos alineados en
    R): reduce ruido sin promediar arritmias raras. `post_ms` por defecto es
    0.7×RR mediano (alcanza a cubrir la onda T)."""
    xyz = np.asarray(xyz, dtype=float)
    r = np.asarray(r_peaks, dtype=int)
    if r.size < 2:
        raise ValueError("Se necesitan al menos 2 latidos para el latido mediano")
    rr = float(np.median(np.diff(r))) / fs * 1000.0
    if post_ms is None:
        post_ms = min(0.7 * rr, 650.0)
    pre, post = int(pre_ms / 1000 * fs), int(post_ms / 1000 * fs)
    beats = [xyz[p - pre:p + post] for p in r if p - pre >= 0 and p + post <= xyz.shape[0]]
    if not beats:
        raise ValueError("Ningún latido completo dentro del registro")
    stack = np.stack(beats)
    med = np.median(stack, axis=0)
    t = (np.arange(-pre, post) / fs) * 1000.0
    return MedianBeat(t_ms=t, xyz=med, n_beats=len(beats), fs=fs, rr_ms=rr)


@dataclass(frozen=True)
class LoopMeasures:
    qrs_on_ms: float
    qrs_off_ms: float
    t_off_ms: float
    qrs_duration_ms: float
    qrs_peak_mv: float
    qrs_peak_vector: Tuple[float, float, float]
    t_peak_mv: float
    t_peak_vector: Tuple[float, float, float]
    qrs_t_angle_deg: float      # entre los vectores medios de QRS y T
    qrs_mean_vector: Tuple[float, float, float]
    t_mean_vector: Tuple[float, float, float]
    qrs_azimuth_deg: float
    qrs_elevation_deg: float
    notes: Tuple[str, ...] = field(default_factory=tuple)


def _angle_deg(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return float("nan")
    return float(np.degrees(np.arccos(np.clip(a @ b / (na * nb), -1.0, 1.0))))


def loop_measures(beat: MedianBeat) -> LoopMeasures:
    """Mide sobre el latido mediano: límites del QRS por la velocidad
    espacial (umbral relativo a su máximo), fin de T por la tangente sobre
    la magnitud espacial, vectores pico y medios, y ángulo QRS-T espacial
    entre los vectores medios de QRS y T.

    Medición automática educativa: puede diferir de la medición experta."""
    t, xyz = beat.t_ms, beat.xyz
    dt = (t[1] - t[0])
    # Línea de base: mediana del tramo PR (−250..−120 ms ≈ antes del QRS).
    base_mask = (t > -150) & (t < -90)
    base = np.median(xyz[base_mask], axis=0) if base_mask.any() else xyz[0]
    x = xyz - base
    mag = np.linalg.norm(x, axis=1)
    vel = np.linalg.norm(np.gradient(x, dt, axis=0), axis=1)
    r_idx = int(np.argmin(np.abs(t)))
    win = (t > -120) & (t < 160)
    vmax = float(vel[win].max())
    thr = 0.12 * vmax
    i = r_idx
    while i > 0 and t[i] > -120 and not (vel[i] < thr and vel[i - 1] < thr):
        i -= 1
    qrs_on = i
    j = r_idx
    while j < len(t) - 2 and t[j] < 160 and not (vel[j] < thr and vel[j + 1] < thr):
        j += 1
    qrs_off = j
    # Asa T: vector de mayor magnitud después del QRS (+60 ms).
    t_mask = np.arange(len(t)) > qrs_off + int(60 / dt)
    t_idx = int(np.argmax(np.where(t_mask, mag, -np.inf)))
    # Fin de T: tangente en la pendiente descendente más pronunciada de la magnitud.
    after = np.arange(t_idx, len(t) - 1)
    if after.size > 3:
        slope = np.gradient(mag, dt)[after]
        k = after[int(np.argmin(slope))]
        s = float(np.gradient(mag, dt)[k])
        t_end = float(t[k] - mag[k] / s) if s < 0 else float(t[-1])
        t_end = min(max(t_end, float(t[t_idx])), float(t[-1]))
    else:
        t_end = float(t[-1])
    q_seg = x[qrs_on:qrs_off + 1]
    q_peak = q_seg[int(np.argmax(np.linalg.norm(q_seg, axis=1)))]
    t_peak = x[t_idx]
    # Vectores medios (integral del asa / duración): más estables que los
    # vectores pico cuando el asa tiene dos lóbulos de tamaño parecido.
    q_mean = q_seg.mean(axis=0)
    t_seg = x[(t > t[qrs_off]) & (t <= t_end)]
    t_mean = t_seg.mean(axis=0) if t_seg.size else t_peak
    # Ángulo QRS-T espacial (entre vectores medios).
    angle = _angle_deg(q_mean, t_mean)
    # Acimut (plano horizontal X-Z) y elevación (hacia Y) del vector QRS medio.
    az = float(np.degrees(np.arctan2(q_mean[2], q_mean[0])))
    el = float(np.degrees(np.arctan2(q_mean[1], np.hypot(q_mean[0], q_mean[2]))))
    return LoopMeasures(
        qrs_on_ms=float(t[qrs_on]), qrs_off_ms=float(t[qrs_off]), t_off_ms=t_end,
        qrs_duration_ms=float(t[qrs_off] - t[qrs_on]),
        qrs_peak_mv=float(np.linalg.norm(q_peak)), qrs_peak_vector=tuple(float(v) for v in q_peak),
        t_peak_mv=float(np.linalg.norm(t_peak)), t_peak_vector=tuple(float(v) for v in t_peak),
        qrs_t_angle_deg=angle, qrs_mean_vector=tuple(float(v) for v in q_mean),
        t_mean_vector=tuple(float(v) for v in t_mean), qrs_azimuth_deg=az, qrs_elevation_deg=el,
    )


def segment_masks(beat: MedianBeat, m: LoopMeasures) -> Dict[str, np.ndarray]:
    """Máscaras booleanas de las asas P, QRS y T sobre el latido mediano."""
    t = beat.t_ms
    return {
        "P": (t >= m.qrs_on_ms - 200) & (t < m.qrs_on_ms - 10),
        "QRS": (t >= m.qrs_on_ms) & (t <= m.qrs_off_ms),
        "T": (t > m.qrs_off_ms) & (t <= m.t_off_ms),
    }


def correlation_by_axis(a: np.ndarray, b: np.ndarray) -> Tuple[float, float, float]:
    """Correlación de Pearson por eje entre dos señales XYZ (n, 3)."""
    out = []
    for k in range(3):
        x, y = a[:, k] - a[:, k].mean(), b[:, k] - b[:, k].mean()
        den = float(np.sqrt((x * x).sum() * (y * y).sum()))
        out.append(float((x * y).sum() / den) if den > 0 else float("nan"))
    return tuple(out)


# ─────────────────────────────────────────────────────────────────────────
# Flujo completo: de derivaciones a VCG medido
# ─────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class VcgResult:
    beat: MedianBeat
    measures: LoopMeasures
    n_beats: int
    heart_rate_bpm: float
    source: str


def vcg_from_xyz(xyz: np.ndarray, fs: float, *, r_signal: Optional[np.ndarray] = None,
                 source: str = "") -> VcgResult:
    """Latido mediano + mediciones a partir de X/Y/Z (mV, Frank)."""
    xyz = _highpass(np.asarray(xyz, dtype=float), fs)
    ref = np.linalg.norm(xyz, axis=1) if r_signal is None else _highpass(np.asarray(r_signal, float), fs)
    r = detect_beats(ref, fs)
    if r.size < 3:
        raise ValueError("Se detectaron menos de 3 latidos: el registro es muy corto o muy ruidoso")
    beat = median_beat(xyz, r, fs)
    return VcgResult(beat=beat, measures=loop_measures(beat), n_beats=beat.n_beats,
                     heart_rate_bpm=60000.0 / beat.rr_ms, source=source)


def vcg_from_12_leads(leads: Mapping[str, np.ndarray], fs: float, *, source: str = "") -> VcgResult:
    """VCG reconstruido (Kors) de un ECG de 12 derivaciones."""
    norm = {normalize_lead_name(k): np.asarray(v, float) for k, v in leads.items()}
    xyz = kors_xyz(norm)
    return vcg_from_xyz(xyz, fs, r_signal=norm.get("II"), source=source)


_TIME_NAMES = {"time", "tiempo", "timestamp"}
_MS_UNITS = {"ms", "msec", "msecs", "milisegundos", "milliseconds"}
_S_UNITS = {"s", "sec", "secs", "seg", "second", "seconds", "segundo", "segundos"}


def _time_column(columns: Sequence[str]) -> Tuple[Optional[str], Optional[str]]:
    """(columna de tiempo, unidad "ms"/"s"/None) según el encabezado:
    «time», «Tiempo (ms)», «tiempo_ms», «t», «Time [s]», «ms»..."""
    import re

    for c in columns:
        tokens = [tok for tok in re.split(r"[^a-z]+", str(c).lower()) if tok]
        if not tokens:
            continue
        if _TIME_NAMES & set(tokens) or set(tokens) <= _TIME_NAMES | _MS_UNITS | _S_UNITS | {"t"}:
            unit = "ms" if _MS_UNITS & set(tokens) else "s" if _S_UNITS & set(tokens) else None
            return str(c), unit
    return None, None


def read_leads_csv(raw: bytes, default_fs: float = 500.0) -> Tuple[Dict[str, np.ndarray], float, str]:
    """Lee un CSV de derivaciones con encabezado (I, II, V1... en cualquier
    capitalización; columna opcional de tiempo en s o ms). Devuelve
    (derivaciones, fs, nota sobre cómo se obtuvo fs)."""
    import io

    import pandas as pd

    df = pd.read_csv(io.BytesIO(raw), sep=None, engine="python")
    df.columns = [str(c).strip() for c in df.columns]
    time_col, unit = _time_column(df.columns)
    fs, note = float(default_fs), f"frecuencia de muestreo supuesta: {default_fs:g} Hz (no hay columna de tiempo)"
    if time_col is not None:
        t = pd.to_numeric(df[time_col], errors="coerce").to_numpy(dtype=float)
        dt = float(np.nanmedian(np.diff(t)))
        if dt > 0:
            # Sin unidad en el nombre: un ECG nunca se muestrea a menos de 2 Hz,
            # así que un paso >= 0.5 solo puede estar en milisegundos.
            is_ms = unit == "ms" or (unit is None and dt >= 0.5)
            fs = 1000.0 / dt if is_ms else 1.0 / dt
            note = f"frecuencia de muestreo calculada de la columna «{time_col}»: {fs:.0f} Hz"
    leads = {}
    for c in df.columns:
        if c == time_col:
            continue
        name = normalize_lead_name(c)
        if name in KORS_LEADS or name in ("III", "AVR", "AVL", "AVF", "VX", "VY", "VZ", "X", "Y", "Z"):
            leads[name] = pd.to_numeric(df[c], errors="coerce").interpolate(limit_direction="both").to_numpy(float)
    return leads, fs, note


@lru_cache(maxsize=1)
def ptb_reference() -> dict:
    """VCG real (Frank) de la paciente del PTB + el reconstruido por Kors de
    sus 12 derivaciones, y la correlación por eje entre ambos (validación)."""
    from src.signals.reference_recordings import ptb_s0010

    d = ptb_s0010()
    fs, L = d["fs"], d["leads"]
    frank = np.stack([L["VX"], L["VY"], L["VZ"]], axis=1)
    kors = kors_xyz(L)
    real = vcg_from_xyz(frank, fs, r_signal=L["II"], source="Frank (real)")
    recon = vcg_from_xyz(kors, fs, r_signal=L["II"], source="Kors (reconstruido)")
    corr = correlation_by_axis(_highpass(frank, fs), _highpass(kors, fs))
    return {"real": real, "kors": recon, "corr": corr, "fs": fs}
