"""Mediciones y criterios del ECG de 12 derivaciones (2026-11-14, Art. I).

Reemplaza la interpretación de `TwelveLeadEcgAnalyzer` en la pestaña 12 Derivaciones. Aquella
no medía la duración del QRS (decidía «bloqueo de rama» por la amplitud de la R en I o por
cuántas muestras de V1 tenían pendiente), medía el «ST» donde la señal tenía menos amplitud
y el eje con la media de todo el registro, P y T incluidas.

Aquí hay dos capas, y la página las muestra separadas:

1. **Medir** (🟣 método BIOCORE, probado contra la verdad del generador en
   `tests/test_twelve_lead_measure.py`): latidos con el detector TKEO de la app; latido mediano
   de cada derivación; inicio y fin del QRS globales por la velocidad espacial (suma de
   |pendiente| de todas las derivaciones) contra un umbral relativo a su máximo; fin de la T por
   la tangente sobre la magnitud espacial (`TANGENT_CITATION`); onda P en la ventana previa al
   QRS; ST en el punto J contra la línea de base del segmento PR.
2. **Comparar con criterios publicados** (🟢, cada uno con su fuente): bloqueos de rama y
   preexcitación (Surawicz 2009), IAMCEST (ESC 2023, con las derivaciones contiguas de la
   tercera definición universal), HVI (Sokolow-Lyon), QTc (Rautaharju 2009, Drew 2010), PR y
   bradicardia (Kusumoto 2018), taquicardia y P sinusal (Page 2015), FA (ESC 2024), eje
   (Chou's) y onda T (Rautaharju 2009).

Lo que no se puede evaluar se dice, con el motivo: sin I y aVF no hay eje; sin V1/V2 e I/V6 no
hay morfología de bloqueo; con bloqueo de rama los umbrales del ST no aplican (ESC 2023). Es
una lectura automática educativa, no un diagnóstico.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
from scipy.signal import butter, filtfilt, find_peaks

from clinical.calculators import BAZETT_CITATION, QRS_AXIS_CITATION, QTC_500_CITATION
from clinical.ecg_references import (
    BYRNE_2023, KUSUMOTO_2018, PAGE_2015, RAUTAHARJU_2009, SOKOLOW_LYON_1949, SURAWICZ_2009, THYGESEN_2012,
    VAN_GELDER_2024, WAGNER_2009,
)
from src.signals.ecg.twelve_lead_analyzer import QrsAxis, qrs_axis_from_net
from src.signals.ecg.vcg import TANGENT_CITATION

LEADS: Tuple[str, ...] = ("I", "II", "III", "aVR", "aVL", "aVF", "V1", "V2", "V3", "V4", "V5", "V6")

# --- Método BIOCORE de medición (umbrales técnicos; los prueba tests/test_twelve_lead_measure.py) -------
QRS_ONSET_FRACTION = 0.025    # el QRS empieza donde la velocidad espacial cruza el 2.5 % de su máximo...
QRS_OFFSET_FRACTION = 0.04     # ...y termina donde baja del 4 %
QRS_ONSET_QUIET_MS = 6.0       # abajo del umbral al menos 6 ms antes del inicio
QRS_OFFSET_QUIET_MS = 12.0     # y 12 ms después del fin
ISOELECTRIC_MV = 0.03          # segmento isoeléctrico: ≥ 30 ms seguidos con |II| < 0.03 mV antes del QRS
ISOELECTRIC_MS = 30.0
DERIVATIVE_SMOOTH_MS = 8.0     # media móvil antes de derivar (baja el ruido de la pendiente)
P_MIN_MV = 0.04                # una P menor no se distingue del ruido del latido mediano
P_ONSET_FRACTION = 0.05        # inicio de P: donde baja al 5 % de su pico
P_CONSISTENT_FRACTION = 0.8    # P «constante»: en ≥ 80 % de los latidos, mismo signo y ≥ 50 % de la altura mediana
RR_REGULAR_CV = 0.08           # RR con coeficiente de variación < 8 %: regular (heurística)
Q_WAVE_MIN_MV = 0.05           # una deflexión inicial negativa ≥ 0.05 mV cuenta como onda q
LOBE_MIN_MV = 0.02             # amplitud mínima para contar un lóbulo positivo o negativo del QRS
BROAD_R_FRACTION = 0.6         # «R ancha»: la parte positiva ocupa ≥ 60 % del QRS
DELTA_SLOW_MS = 30.0           # «onda delta»: ≥ 30 ms desde el inicio del QRS hasta la subida rápida
MORPH_SMOOTH_MS = 8.0          # media móvil antes de leer morfología, amplitudes y el ST (el ruido partía los lóbulos)
METHOD_NOTE = (
    "Medición automática de BIOCORE sobre el latido mediano (umbrales técnicos propios, probados contra la "
    "verdad del generador sintético); puede diferir de la medición experta."
)

# --- Umbrales de los criterios citados -----------------------------------------------------------------
POPULATIONS: Dict[str, str] = {
    "mujer": "mujer", "hombre_40_o_mas": "hombre de 40 años o más", "hombre_menor_40": "hombre menor de 40 años",
}
ST_V2V3_MV = {"mujer": 0.15, "hombre_40_o_mas": 0.20, "hombre_menor_40": 0.25}   # ESC 2023, 3.2.1
ST_OTHER_MV = 0.10
CONTIGUOUS_GROUPS: Dict[str, Tuple[Tuple[str, str], ...]] = {     # Thygesen 2012
    "anterior": (("V1", "V2"), ("V2", "V3"), ("V3", "V4"), ("V4", "V5"), ("V5", "V6")),
    "inferior": (("II", "III"), ("II", "aVF"), ("III", "aVF")),
    "lateral": (("I", "aVL"),),
}
GROUP_TEXT = {
    "anterior": "V1–V6 (cara anterior; la parte VI la atribuye a la descendente anterior)",
    "inferior": "II, III y aVF (cara inferior; coronaria derecha o circunfleja, según la parte VI)",
    "lateral": "I y aVL (lateral/apical)",
}
QTC_PROLONGED_MS = {"mujer": 460.0, "hombre_40_o_mas": 450.0, "hombre_menor_40": 450.0}   # Rautaharju 2009
QTC_SHORT_MS = 390.0
QTC_HIGH_RISK_MS = 500.0                                                                  # Drew 2010


@dataclass(frozen=True)
class Criterion:
    key: str
    title: str
    met: Optional[bool]       # None: no evaluable (o depende del sexo y la edad); `detail` dice por qué
    detail: str
    source: str

    def __post_init__(self):
        if self.met is not None:                       # un bool de NumPy no es `True` para `is True`
            object.__setattr__(self, "met", bool(self.met))


@dataclass(frozen=True)
class TwelveLeadReport:
    leads: Tuple[str, ...]
    fs: float
    n_beats: int
    heart_rate_bpm: Optional[float]
    rr_cv: Optional[float]
    regular: Optional[bool]
    p_wave: str                 # "sinusal" | "no sinusal" | "ausente" | "no evaluable"
    pr_ms: Optional[float]
    qrs_ms: Optional[float]
    qt_ms: Optional[float]
    qtc_ms: Optional[float]
    axis: Optional[QrsAxis]
    st_j_mv: Mapping[str, float]
    criteria: Tuple[Criterion, ...]
    unavailable: Tuple[str, ...] = field(default_factory=tuple)
    population: Optional[str] = None

    def criterion(self, key: str) -> Optional[Criterion]:
        return next((c for c in self.criteria if c.key == key), None)

    def met(self) -> List[Criterion]:
        return [c for c in self.criteria if c.met is True]


@dataclass(frozen=True)
class _Beat:
    t_ms: np.ndarray
    leads: Dict[str, np.ndarray]     # latido mediano, línea de base del segmento PR restada
    rr_s: float
    n: int
    stacks: Dict[str, np.ndarray]    # cada latido (filas), con la misma línea de base restada


# --- utilidades ----------------------------------------------------------------------------------------

def qrs_axis_from_leads(lead_i_qrs: np.ndarray, avf_qrs: np.ndarray) -> QrsAxis:
    """Eje del QRS por el área neta de I y aVF dentro del QRS (la fórmula vive en `qrs_axis_from_net`)."""
    return qrs_axis_from_net(float(np.mean(lead_i_qrs)), float(np.mean(avf_qrs)))


def _fs_from(leads: Mapping[str, np.ndarray], default: float) -> float:
    t = leads.get("time")
    if t is not None and len(t) > 2:
        dt = float(np.median(np.diff(np.asarray(t, dtype=float))))
        if dt > 0:
            return 1.0 / dt
    return float(default)


def _smooth(x: np.ndarray, fs: float, ms: float) -> np.ndarray:
    k = max(1, int(round(ms / 1000.0 * fs)))
    return np.convolve(x, np.ones(k) / k, mode="same")


def _detection_lead(leads: Mapping[str, np.ndarray], fs: float) -> str:
    """La derivación con más energía en la banda del QRS (5–15 Hz)."""
    b, a = butter(3, [5.0 / (fs / 2), 15.0 / (fs / 2)], btype="band")
    best, best_amp = None, -1.0
    for name in LEADS:
        if name in leads:
            x = np.asarray(leads[name], dtype=float)
            if x.size < 3 * fs:
                continue
            amp = float(np.percentile(np.abs(filtfilt(b, a, x)), 99))
            if amp > best_amp:
                best, best_amp = name, amp
    return best


def _align(leads: Mapping[str, np.ndarray], peaks: np.ndarray, fs: float) -> np.ndarray:
    """Punto de alineación de cada latido: la máxima velocidad espacial cerca del pico detectado.

    El pico del detector puede caer en la R o en la S según el latido (en las pruebas saltaba 25 ms);
    alinear así el latido mediano no lo emborrona. Después, un ajuste fino por correlación con la mediana."""
    vel = sum(np.abs(np.gradient(_smooth(np.asarray(sig, dtype=float), fs, DERIVATIVE_SMOOTH_MS)))
              for sig in leads.values())
    w = int(0.08 * fs)
    n = vel.size
    fid = np.array([p - w + int(np.argmax(vel[p - w:p + w + 1])) for p in peaks if p - w >= 0 and p + w < n])
    if fid.size < 3:
        return fid
    lo, hi = int(0.1 * fs), int(0.15 * fs)
    ok = fid[(fid - lo - 8 >= 0) & (fid + hi + 8 < n)]
    stack = np.stack([np.concatenate([np.asarray(sig, dtype=float)[f - lo:f + hi] for sig in leads.values()]) for f in ok])
    template = np.median(stack, axis=0)
    refined = []
    for f in ok:
        best, best_lag = -np.inf, 0
        for lag in range(-8, 9):
            seg = np.concatenate([np.asarray(sig, dtype=float)[f + lag - lo:f + lag + hi] for sig in leads.values()])
            score = float(np.dot(seg - seg.mean(), template - template.mean()))
            if score > best:
                best, best_lag = score, lag
        refined.append(f + best_lag)
    return np.array(refined)


def _median_beat(leads: Mapping[str, np.ndarray], peaks: np.ndarray, fs: float) -> Tuple[np.ndarray, Dict, float, int]:
    rr_s = float(np.median(np.diff(peaks))) / fs
    pre_ms = min(0.45 * rr_s * 1000.0, 350.0)
    post_ms = min(0.75 * rr_s * 1000.0, 650.0)
    pre, post = int(pre_ms / 1000 * fs), int(post_ms / 1000 * fs)
    n_total = len(next(iter(leads.values())))
    ok = [p for p in peaks if p - pre >= 0 and p + post <= n_total]
    t_ms = np.arange(-pre, post) / fs * 1000.0
    stacks = {name: np.stack([np.asarray(sig, dtype=float)[p - pre:p + post] for p in ok]) for name, sig in leads.items()}
    return t_ms, stacks, rr_s, len(ok)


def _qrs_bounds(t_ms: np.ndarray, med: Mapping[str, np.ndarray], fs: float) -> Tuple[int, int, np.ndarray]:
    """Inicio y fin del QRS globales por la velocidad espacial del latido mediano."""
    vel = sum(np.abs(np.gradient(_smooth(sig, fs, DERIVATIVE_SMOOTH_MS))) * fs for sig in med.values())
    win = np.where((t_ms > -100) & (t_ms < 120))[0]
    i_max = int(win[np.argmax(vel[win])])
    base = float(np.percentile(vel, 20))
    thr_on = base + QRS_ONSET_FRACTION * (float(vel[i_max]) - base)
    thr_off = base + QRS_OFFSET_FRACTION * (float(vel[i_max]) - base)
    n_on = max(1, int(QRS_ONSET_QUIET_MS / 1000 * fs))
    n_off = max(1, int(QRS_OFFSET_QUIET_MS / 1000 * fs))
    i = i_max
    while i - n_on >= 0 and not np.all(vel[i - n_on + 1:i + 1] < thr_on):
        i -= 1
    onset = i + 1
    j = i_max
    while j + n_off <= len(vel) and not np.all(vel[j:j + n_off] < thr_off):
        j += 1
    offset = j - 1
    return onset, offset, vel


def _build_beat(leads: Mapping[str, np.ndarray], peaks: np.ndarray, fs: float) -> Tuple[_Beat, int, int, np.ndarray]:
    t_ms, stacks, rr_s, n = _median_beat(leads, peaks, fs)
    raw = {name: np.median(st, axis=0) for name, st in stacks.items()}
    onset, _, _ = _qrs_bounds(t_ms, raw, fs)
    # Línea de base de cada latido: el segmento PR (de −30 a −10 ms del inicio del QRS); se resta antes de la mediana.
    b0 = max(0, onset - int(30 / 1000 * fs))
    b1 = max(b0 + 1, onset - int(10 / 1000 * fs))
    corrected_stacks = {name: st - st[:, b0:b1].mean(axis=1, keepdims=True) for name, st in stacks.items()}
    corrected = {name: np.median(st, axis=0) for name, st in corrected_stacks.items()}
    onset, offset, vel = _qrs_bounds(t_ms, corrected, fs)
    return _Beat(t_ms=t_ms, leads=corrected, rr_s=rr_s, n=n, stacks=corrected_stacks), onset, offset, vel


def _lobes(x: np.ndarray, fs: float) -> Tuple[float, float, float, float]:
    """(duración positiva del lóbulo de la R, duración del último lóbulo negativo, máx +, máx −) en ms y mV."""
    pos = x > LOBE_MIN_MV
    neg = x < -LOBE_MIN_MV
    r_idx = int(np.argmax(x))
    r_dur = 0.0
    if pos[r_idx]:
        a = r_idx
        while a > 0 and pos[a - 1]:
            a -= 1
        b = r_idx
        while b < x.size - 1 and pos[b + 1]:
            b += 1
        r_dur = (b - a + 1) / fs * 1000.0
    s_dur = 0.0
    idx = np.where(neg)[0]
    if idx.size and idx[-1] > r_idx:
        b = idx[-1]
        a = b
        while a > 0 and neg[a - 1]:
            a -= 1
        if a > r_idx:
            s_dur = (b - a + 1) / fs * 1000.0
    return r_dur, s_dur, float(x.max()), float(x.min())


def _has_rsr_prime(x: np.ndarray, fs: float) -> bool:
    """r (o R) seguida de s (o S) y luego R′ (rsr′, rsR′ o rSR′)."""
    dist = max(1, int(0.015 * fs))
    pos, _ = find_peaks(x, distance=dist, prominence=0.05)
    neg, _ = find_peaks(-x, distance=dist, prominence=0.05)
    pos = [p for p in pos if x[p] > LOBE_MIN_MV]
    neg = [q for q in neg if x[q] < -LOBE_MIN_MV]
    for p1 in pos:
        for q in neg:
            if q > p1 and any(p2 > q and x[p2] >= 0.1 for p2 in pos):
                return True
    return False


def _population_verdict(results: Dict[str, bool]) -> Optional[bool]:
    vals = set(results.values())
    return vals.pop() if len(vals) == 1 else None


def _fmt_pop(results: Dict[str, bool]) -> str:
    yes = [POPULATIONS[k] for k, v in results.items() if v]
    no = [POPULATIONS[k] for k, v in results.items() if not v]
    parts = []
    if yes:
        parts.append("cumple para " + ", ".join(yes))
    if no:
        parts.append("no cumple para " + ", ".join(no))
    return "; ".join(parts)


# --- análisis ------------------------------------------------------------------------------------------

def analyze_twelve_lead(leads: Mapping[str, np.ndarray], fs: Optional[float] = None,
                        population: Optional[str] = None) -> TwelveLeadReport:
    """Mide sobre el latido mediano y compara con los criterios citados.

    `population` ("mujer", "hombre_40_o_mas", "hombre_menor_40") elige los umbrales que dependen del
    sexo y la edad (ST en V2–V3, QTc). Sin ella, el criterio dice para quién se cumple."""
    if population is not None and population not in POPULATIONS:
        raise ValueError(f"población desconocida: {population}")
    fs = _fs_from(leads, 500.0) if fs is None else float(fs)
    present = {name: np.asarray(leads[name], dtype=float) for name in LEADS if name in leads and leads[name] is not None}
    names = tuple(present)
    derived: List[str] = []
    if "I" in present and "II" in present:                     # Einthoven y Goldberger: exactas en un ECG estándar
        i_, ii_ = present["I"], present["II"]
        for name, sig in (("III", ii_ - i_), ("aVR", -(i_ + ii_) / 2.0), ("aVL", i_ - ii_ / 2.0), ("aVF", ii_ - i_ / 2.0)):
            if name not in present:
                present[name] = sig
                derived.append(name)
        present = {name: present[name] for name in LEADS if name in present}
    pops = [population] if population else list(POPULATIONS)

    def _empty(reason: str) -> TwelveLeadReport:
        return TwelveLeadReport(leads=names, fs=fs, n_beats=0, heart_rate_bpm=None, rr_cv=None, regular=None,
                                p_wave="no evaluable", pr_ms=None, qrs_ms=None, qt_ms=None, qtc_ms=None, axis=None,
                                st_j_mv={}, criteria=(), unavailable=(reason,), population=population)

    if not present:
        return _empty("No hay derivaciones con nombre estándar (I, II, III, aVR, aVL, aVF, V1–V6).")
    det = _detection_lead(present, fs)
    if det is None:
        return _empty("El registro dura menos de 3 s: no alcanza para medir latidos.")
    from src.signals.ecg.vcg import detect_beats   # detector TKEO de la app

    peaks = detect_beats(present[det], fs)
    if peaks.size < 3:
        return _empty(f"Menos de 3 latidos detectados en {det}: no hay latido mediano.")
    rr = np.diff(peaks) / fs
    hr = 60.0 / float(np.mean(rr))
    rr_cv = float(np.std(rr) / np.mean(rr))
    regular = rr_cv < RR_REGULAR_CV

    beat, on, off, vel = _build_beat(present, _align(present, peaks, fs), fs)
    if beat.n < 2:
        return _empty("Ningún latido completo dentro del registro.")
    t, med = beat.t_ms, beat.leads
    dt_ms = 1000.0 / fs
    qrs_ms = (off - on) * dt_ms
    unavailable: List[str] = []
    if derived:
        unavailable.append("Derivadas de I y II (Einthoven y Goldberger), no venían en el registro: " + ", ".join(derived) + ".")
    criteria: List[Criterion] = []

    # --- QT y QTc -------------------------------------------------------------------------------------
    mag = np.sqrt(sum(sig ** 2 for sig in med.values()))
    m0 = float(np.median(mag[max(0, on - int(30 / dt_ms)):max(1, on - int(10 / dt_ms))]))
    t_search = np.arange(min(off + int(40 / dt_ms), mag.size - 2), mag.size - 1)
    qt_ms = qtc_ms = None
    if t_search.size > 5:
        t_peak = int(t_search[np.argmax(mag[t_search])])
        after = np.arange(t_peak, mag.size - 1)
        if after.size > 3 and mag[t_peak] >= max(3.0 * m0, 0.05):     # hay una T que se distingue del ruido
            slope = np.gradient(mag, dt_ms)[after]
            k = int(after[int(np.argmin(slope))])
            s = float(np.gradient(mag, dt_ms)[k])
            if s < -1e-4:
                t_end = float(t[k] + (m0 - mag[k]) / s)
                candidate = t_end - float(t[on])
                if qrs_ms + 40.0 <= candidate <= 0.9 * beat.rr_s * 1000.0 and t_end <= float(t[-1]):
                    qt_ms = candidate
                    qtc_ms = float(qt_ms / np.sqrt(beat.rr_s))
    if qt_ms is None:
        unavailable.append("QT: no se encontró el final de la T dentro del latido.")

    # --- onda P y PR ------------------------------------------------------------------------------------
    w0 = max(0, on - int(min(0.4 * beat.rr_s * 1000.0, 350.0) / dt_ms))
    if qt_ms is not None:                                    # la ventana de la P empieza después de la T previa
        prev_t_end = on + int((qt_ms - beat.rr_s * 1000.0 + 10.0) / dt_ms)
        w0 = max(w0, prev_t_end)
    w1 = on - int(10 / dt_ms)
    p_lead = "II" if "II" in med else None
    p_wave, pr_ms = "no evaluable", None
    if p_lead is None:
        unavailable.append("Onda P y PR: falta la derivación II.")
    elif w1 - w0 < int(40 / dt_ms):
        w0 = max(0, w1 - int(40 / dt_ms))
        unavailable.append("Onda P y PR: entre la T previa y el QRS quedan menos de 40 ms para buscarla.")
    else:
        seg = med[p_lead][w0:w1]
        k = int(np.argmax(np.abs(seg)))
        peak = float(seg[k])
        idx = w0 + k
        hw = max(1, int(0.01 * fs))
        per_beat = beat.stacks[p_lead][:, max(0, idx - hw):idx + hw + 1].mean(axis=1)
        consistent = float(np.mean((np.sign(per_beat) == np.sign(peak)) & (np.abs(per_beat) >= 0.5 * abs(peak))))
        if abs(peak) < P_MIN_MV or consistent < P_CONSISTENT_FRACTION:
            p_wave = "ausente"
        else:
            def _up(ld):
                s = med[ld][w0:w1]
                return float(s.max()) >= P_MIN_MV / 2 and float(s.max()) > abs(float(s.min()))
            if all(ld in med for ld in ("I", "II", "aVF")):
                p_wave = "sinusal" if all(_up(ld) for ld in ("I", "II", "aVF")) else "no sinusal"
            else:
                p_wave = "presente"
            if p_wave in ("sinusal", "presente"):
                # hacia atrás desde el pico de la P hasta el 5 % de su altura o hasta un valle (la cola de la T previa)
                x = _smooth(med[p_lead], fs, 16.0)
                i = w0 + k
                while i > w0 and x[i] > P_ONSET_FRACTION * peak and not (x[i - 1] > x[i] and x[i] < 0.3 * peak):
                    i -= 1
                pr_ms = (on - i) * dt_ms

    ref_lead = "II" if "II" in med else det
    near_zero = np.abs(med[ref_lead][w0:w1]) < ISOELECTRIC_MV
    longest, run = 0, 0
    for flag in near_zero:
        run = run + 1 if flag else 0
        longest = max(longest, run)
    isoelectric = longest * dt_ms >= ISOELECTRIC_MS
    if not isoelectric:
        unavailable.append(
            f"Sin segmento isoeléctrico antes del QRS en {ref_lead} (≥ {ISOELECTRIC_MS:.0f} ms con |señal| < "
            f"{ISOELECTRIC_MV} mV): el ST y el eje no tienen línea de base de referencia (pasa, por ejemplo, con ondas F)."
        )

    # --- eje ---------------------------------------------------------------------------------------------
    axis = None
    lead_i = med.get("I")
    avf = med.get("aVF")
    if avf is None and lead_i is not None and "II" in med:
        avf = med["II"] - lead_i / 2.0                          # Goldberger
    if lead_i is not None and avf is not None and isoelectric:
        axis = qrs_axis_from_leads(lead_i[on:off + 1], avf[on:off + 1])
    elif lead_i is None or avf is None:
        unavailable.append("Eje: faltan I y aVF (o I y II).")

    # --- ST en el punto J ---------------------------------------------------------------------------------
    smooth = {name: _smooth(sig, fs, MORPH_SMOOTH_MS) for name, sig in med.items()}
    j_win = max(1, int(MORPH_SMOOTH_MS / dt_ms))                # ST en J: media de J a J + 8 ms (sin la S)
    st_j = {name: float(np.mean(sig[off:off + j_win])) for name, sig in med.items()}

    # --- ritmo --------------------------------------------------------------------------------------------
    criteria.append(Criterion(
        "sinus", "Ritmo sinusal: P positiva en I, II y aVF antes de cada QRS",
        None if p_wave in ("no evaluable", "presente") else p_wave == "sinusal",
        {"sinusal": "P positiva en I, II y aVF en el latido mediano.",
         "presente": "Hay una P constante en II, pero faltan I o aVF para ver su polaridad.",
         "no sinusal": "Hay actividad auricular antes del QRS, pero no es positiva en I, II y aVF.",
         "ausente": "No hay una onda P constante antes del QRS (misma forma en ≥ 80 % de los latidos).",
         "no evaluable": "Falta alguna de I, II o aVF."}[p_wave],
        PAGE_2015 + " (sección 3: la P sinusal es positiva en I, II y aVF)",
    ))
    if p_wave == "sinusal":
        criteria.append(Criterion("sinus_tachycardia", "Taquicardia sinusal (> 100 lpm)", hr > 100,
                                  f"FC {hr:.0f} lpm.", PAGE_2015 + " (tabla 3)"))
        brady_detail = f"FC {hr:.0f} lpm."
        if 50 <= hr < 60:
            brady_detail += " Está por debajo de 60, el corte de la convención docente, pero no de 50."
        criteria.append(Criterion("sinus_bradycardia", "Bradicardia sinusal (< 50 lpm)", hr < 50, brady_detail,
                                  KUSUMOTO_2018 + " (tabla 3)"))
    af_met = (not regular) and p_wave == "ausente"
    criteria.append(Criterion(
        "af", "Compatible con fibrilación auricular: sin P discernibles y RR sin patrón", af_met,
        f"RR {'irregulares' if not regular else 'regulares'} (coeficiente de variación {rr_cv * 100:.0f} %; "
        f"irregular si ≥ {RR_REGULAR_CV * 100:.0f} %, heurística BIOCORE); onda P: {p_wave}.",
        VAN_GELDER_2024 + " (sección 3.1)",
    ))
    if regular and p_wave in ("no sinusal", "ausente"):
        criteria.append(Criterion(
            "rhythm_unidentified", "Ritmo regular sin P sinusal", None,
            "El analizador no identifica este ritmo (puede ser flutter, taquicardia auricular, de la unión u otro): "
            "mira la actividad auricular en II, III, aVF y V1. El flutter típico da ondas F negativas «en sierra» "
            "en II, III y aVF.", PAGE_2015 + " (tabla 3: flutter típico)",
        ))

    # --- PR -----------------------------------------------------------------------------------------------
    if pr_ms is not None:
        criteria.append(Criterion("av_block_1", "Bloqueo AV de primer grado (PR > 200 ms)", pr_ms > 200,
                                  f"PR {pr_ms:.0f} ms.", KUSUMOTO_2018 + " (tabla 3)"))

    # --- morfología del QRS: bloqueos de rama ----------------------------------------------------------------
    qrs = {name: sig[on:off + 1] for name, sig in smooth.items()}
    v12 = [ld for ld in ("V1", "V2") if ld in qrs]
    i_v6 = [ld for ld in ("I", "V6") if ld in qrs]
    rbbb_morph = lbbb_morph = None
    if v12 and len(i_v6) == 2:
        rsr = [ld for ld in v12 if _has_rsr_prime(qrs[ld], fs)]
        wide_s = {}
        for ld in i_v6:
            r_dur, s_dur, _, _ = _lobes(qrs[ld], fs)
            wide_s[ld] = s_dur > 40.0 or (s_dur > r_dur and s_dur > 0)
        rbbb_morph = bool(rsr) and all(wide_s.values())
        rbbb_detail = (f"rsR′ en V1–V2: {', '.join(rsr) if rsr else 'no'}; S ancha (> 40 ms o más larga que la R): "
                       + ", ".join(f"en {k} {'sí' if v else 'no'}" for k, v in wide_s.items()) + ".")
    else:
        rbbb_detail = "Faltan V1/V2, I o V6."
        unavailable.append("Morfología de bloqueo de rama derecha: " + rbbb_detail)
    left = [ld for ld in ("I", "aVL", "V5", "V6") if ld in qrs]
    if len(left) >= 3 and all(ld in qrs for ld in ("I", "V5", "V6")):
        broad = [ld for ld in left if _lobes(qrs[ld], fs)[0] >= BROAD_R_FRACTION * qrs_ms and qrs[ld].max() > -qrs[ld].min()]
        n_init = max(1, int(30 / dt_ms))
        with_q = [ld for ld in ("I", "V5", "V6") if float(qrs[ld][:n_init].min()) <= -Q_WAVE_MIN_MV
                  and int(np.argmin(qrs[ld][:n_init])) < int(np.argmax(qrs[ld]))]
        rpt = {ld: int(np.argmax(qrs[ld])) * dt_ms for ld in ("V5", "V6")}
        lbbb_morph = len(broad) >= 3 and not with_q and max(rpt.values()) > 60.0
        lbbb_detail = (f"R ancha (≥ {BROAD_R_FRACTION * 100:.0f} % del QRS) en: {', '.join(broad) or 'ninguna'} "
                       f"(se buscan I, aVL, V5 y V6); onda q en I, V5 o V6: {', '.join(with_q) or 'no'}; tiempo al pico "
                       f"de R en V5/V6: {rpt['V5']:.0f}/{rpt['V6']:.0f} ms (debe ser > 60).")
    else:
        lbbb_detail = "Faltan I, V5 o V6."
        unavailable.append("Morfología de bloqueo de rama izquierda: " + lbbb_detail)

    # --- preexcitación --------------------------------------------------------------------------------------
    v_max = float(vel[on:off + 1].max())
    above = np.where(vel[on:off + 1] >= 0.5 * v_max)[0]
    slow_ms = float(above[0]) * dt_ms if above.size else 0.0
    delta = slow_ms >= DELTA_SLOW_MS
    pre = None if pr_ms is None else (pr_ms < 120 and delta and qrs_ms > 120)
    criteria.append(Criterion(
        "preexcitation", "Preexcitación ventricular (PR < 120 ms, onda delta, QRS > 120 ms)", pre,
        (f"PR {pr_ms:.0f} ms; " if pr_ms is not None else "PR no medible; ")
        + f"inicio lento del QRS de {slow_ms:.0f} ms (onda delta si ≥ {DELTA_SLOW_MS:.0f} ms, criterio BIOCORE); "
          f"QRS {qrs_ms:.0f} ms.", SURAWICZ_2009,
    ))
    rbbb = None if rbbb_morph is None else (qrs_ms >= 120 and rbbb_morph)
    lbbb = None if lbbb_morph is None else (qrs_ms >= 120 and lbbb_morph and not rbbb_morph)
    if pre:
        rbbb = lbbb = None
        note = (" Con preexcitación el QRS ancho tiene otra causa: el analizador no evalúa un bloqueo de rama encima "
                "(Surawicz 2009 los describe como trastornos distintos).")
        rbbb_detail += note
        lbbb_detail += note
    criteria.append(Criterion("rbbb", "Bloqueo de rama derecha completo", rbbb,
                              f"QRS {qrs_ms:.0f} ms (≥ 120). {rbbb_detail}", SURAWICZ_2009))
    criteria.append(Criterion("lbbb", "Bloqueo de rama izquierda completo", lbbb,
                              f"QRS {qrs_ms:.0f} ms (≥ 120). {lbbb_detail}", SURAWICZ_2009))
    if rbbb_morph and 110 <= qrs_ms < 120:
        criteria.append(Criterion("rbbb_incomplete", "Bloqueo de rama derecha incompleto", True,
                                  f"QRS {qrs_ms:.0f} ms (110–120) con morfología de bloqueo derecho.", SURAWICZ_2009))

    if qrs_ms > 110 and not rbbb and not lbbb and not pre and not (rbbb_morph and qrs_ms >= 110):
        criteria.append(Criterion("ivcd", "Trastorno inespecífico de la conducción intraventricular (QRS > 110 ms)",
                                  True, f"QRS {qrs_ms:.0f} ms sin morfología de bloqueo de rama ni preexcitación.",
                                  SURAWICZ_2009))

    # --- HVI (Sokolow-Lyon) ----------------------------------------------------------------------------------
    lvh = None
    if all(ld in qrs for ld in ("V1", "V5", "V6")) or "aVL" in qrs:
        sv1 = float(-qrs["V1"].min()) if "V1" in qrs else None
        rv56 = max(float(qrs[ld].max()) for ld in ("V5", "V6") if ld in qrs) if ("V5" in qrs or "V6" in qrs) else None
        ravl = float(qrs["aVL"].max()) if "aVL" in qrs else None
        sl = sv1 + rv56 if sv1 is not None and rv56 is not None else None
        lvh = (sl is not None and sl >= 3.5) or (ravl is not None and ravl >= 1.1)
        criteria.append(Criterion(
            "lvh", "Voltaje de hipertrofia ventricular izquierda (Sokolow-Lyon)", lvh,
            (f"S en V1 + R en V5/V6 = {sl:.2f} mV (≥ 3.5); " if sl is not None else "")
            + (f"R en aVL = {ravl:.2f} mV (≥ 1.1)." if ravl is not None else ""), SOKOLOW_LYON_1949,
        ))
    else:
        unavailable.append("Voltaje de HVI: faltan V1, V5/V6 y aVL.")

    # --- IAMCEST (ST en el punto J, derivaciones contiguas) -------------------------------------------------
    if not isoelectric:
        criteria.append(Criterion(
            "stemi", "Elevación del ST en el punto J en ≥ 2 derivaciones contiguas", None,
            "Sin segmento isoeléctrico antes del QRS no hay contra qué medir el ST.", BYRNE_2023 + " (sección 3.2.1)",
        ))
    elif rbbb or lbbb:
        criteria.append(Criterion(
            "stemi", "Elevación del ST en el punto J en ≥ 2 derivaciones contiguas", None,
            "Con bloqueo de rama (o marcapasos) la ESC 2023 dice que no se puede evaluar con precisión; ante "
            "sospecha clínica alta de isquemia en curso se maneja como un IAMCEST.", BYRNE_2023 + " (sección 3.2.1)",
        ))
    elif lvh:
        criteria.append(Criterion(
            "stemi", "Elevación del ST en el punto J en ≥ 2 derivaciones contiguas", None,
            "La ESC 2023 da el umbral de ≥ 1 mm en ausencia de HVI o de bloqueo de rama izquierda; con voltaje de "
            "HVI no se aplica aquí.", BYRNE_2023 + " (sección 3.2.1)",
        ))
    elif not any(a in st_j and b in st_j for pairs in CONTIGUOUS_GROUPS.values() for a, b in pairs):
        criteria.append(Criterion(
            "stemi", "Elevación del ST en el punto J en ≥ 2 derivaciones contiguas", None,
            "Faltan derivaciones contiguas (V1–V6 vecinas, dos de II, III y aVF, o I y aVL).", THYGESEN_2012,
        ))
    else:
        def _threshold(lead: str, pop: str) -> float:
            return ST_V2V3_MV[pop] if lead in ("V2", "V3") else ST_OTHER_MV

        by_pop: Dict[str, bool] = {}
        groups_by_pop: Dict[str, List[str]] = {}
        for pop in pops:
            hit = [g for g, pairs in CONTIGUOUS_GROUPS.items()
                   if any(a in st_j and b in st_j and st_j[a] >= _threshold(a, pop) and st_j[b] >= _threshold(b, pop)
                          for a, b in pairs)]
            by_pop[pop] = bool(hit)
            groups_by_pop[pop] = hit
        verdict = _population_verdict(by_pop)
        elevated = ", ".join(f"{ld} {st_j[ld] * 10:+.1f} mm" for ld in LEADS if ld in st_j and st_j[ld] >= 0.1)
        groups = sorted({g for gs in groups_by_pop.values() for g in gs})
        detail = (f"ST en el punto J ≥ 1 mm en: {elevated or 'ninguna derivación'}. Umbral: ≥ 1 mm, salvo V2–V3 "
                  f"(≥ 1.5 mm en mujeres, ≥ 2 mm en hombres de 40 años o más, ≥ 2.5 mm en hombres menores de 40).")
        if groups:
            detail += " Grupo contiguo: " + "; ".join(GROUP_TEXT[g] for g in groups) + "."
        if len(pops) > 1 and verdict is None:
            detail += " " + _fmt_pop(by_pop).capitalize() + "."
        criteria.append(Criterion(
            "stemi", "Elevación del ST en el punto J en ≥ 2 derivaciones contiguas", verdict, detail,
            f"{BYRNE_2023} (sección 3.2.1); {THYGESEN_2012}; {WAGNER_2009}",
        ))

    # --- QTc ---------------------------------------------------------------------------------------------------
    if qtc_ms is not None:
        if qrs_ms >= 120:
            criteria.append(Criterion(
                "qtc", "QTc prolongado", None,
                f"QRS {qrs_ms:.0f} ms: el QT se prolonga en los trastornos de la conducción ventricular y necesita un "
                "ajuste por la duración del QRS, que este analizador no hace.", RAUTAHARJU_2009,
            ))
        else:
            res = {pop: qtc_ms >= QTC_PROLONGED_MS[pop] for pop in pops}
            verdict = _population_verdict(res)
            detail = (f"QT {qt_ms:.0f} ms, RR {beat.rr_s * 1000:.0f} ms, QTc (Bazett) {qtc_ms:.0f} ms. Prolongado: "
                      f"≥ 450 ms en hombres, ≥ 460 ms en mujeres. La fórmula de Bazett puede dar prolongaciones "
                      f"falsas.")
            if len(pops) > 1 and verdict is None:
                detail += " " + _fmt_pop(res).capitalize() + "."
            criteria.append(Criterion("qtc", "QTc prolongado", verdict, detail,
                                      f"{RAUTAHARJU_2009}; {BAZETT_CITATION}; {TANGENT_CITATION}"))
            criteria.append(Criterion("qtc_500", "QTc de 500 ms o más (riesgo de torsade de pointes)",
                                      qtc_ms >= QTC_HIGH_RISK_MS, f"QTc {qtc_ms:.0f} ms.", QTC_500_CITATION))
            criteria.append(Criterion("qt_short", "QT corto (QTc ≤ 390 ms)", qtc_ms <= QTC_SHORT_MS,
                                      f"QTc {qtc_ms:.0f} ms.", RAUTAHARJU_2009))

    # --- eje ------------------------------------------------------------------------------------------------------
    if axis is not None:
        names_es = {"Normal": "normal (−30° a +90°)", "LAD": "desviado a la izquierda (−30° a −90°)",
                    "RAD": "desviado a la derecha (+90° a +180°)", "Extreme": "extremo (−90° a ±180°)"}
        criteria.append(Criterion("axis_deviation", "Eje del QRS fuera de lo normal", axis.category != "Normal",
                                  f"Eje {axis.axis_degrees:.0f}°: {names_es.get(axis.category, axis.category)}.",
                                  QRS_AXIS_CITATION))

    # --- onda T ---------------------------------------------------------------------------------------------------
    t_leads = [ld for ld in ("I", "II", "V3", "V4", "V5", "V6") if ld in med]
    if qt_ms is not None and t_leads and not isoelectric:
        criteria.append(Criterion("t_wave", "Onda T positiva en I, II y V3–V6 (adulto de 20 años o más)", None,
                                  "Sin segmento isoeléctrico antes del QRS no hay contra qué leer la polaridad de la T.",
                                  RAUTAHARJU_2009))
    elif qt_ms is not None and t_leads:
        t_lo = min(off + int(40 / dt_ms), mag.size - 1)
        t_hi = min(on + int((qt_ms) / dt_ms), mag.size)
        negative = []
        for ld in t_leads:
            seg = med[ld][t_lo:t_hi]
            if seg.size and float(seg.min()) < -abs(float(seg.max())):
                negative.append(ld)
        detail = ("T positiva en " + ", ".join(t_leads) + "." if not negative
                  else "T negativa en " + ", ".join(negative) + ".")
        if negative and (rbbb or lbbb or lvh):
            detail += (" Con bloqueo de rama el ST y la T suelen ir opuestos al QRS (Surawicz 2009), y la HVI se "
                       "asocia a depresión del ST (Rautaharju 2009).")
        criteria.append(Criterion("t_wave", "Onda T positiva en I, II y V3–V6 (adulto de 20 años o más)",
                                  not negative, detail, RAUTAHARJU_2009))

    return TwelveLeadReport(
        leads=names, fs=fs, n_beats=beat.n, heart_rate_bpm=hr, rr_cv=rr_cv, regular=regular, p_wave=p_wave,
        pr_ms=pr_ms, qrs_ms=qrs_ms, qt_ms=qt_ms, qtc_ms=qtc_ms, axis=axis, st_j_mv=st_j, criteria=tuple(criteria),
        unavailable=tuple(unavailable), population=population,
    )


def missing_leads(leads: Sequence[str]) -> List[str]:
    return [ld for ld in LEADS if ld not in leads]
