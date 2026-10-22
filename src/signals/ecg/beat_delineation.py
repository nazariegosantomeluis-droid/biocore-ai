"""Latido mediano y delineación P-QRS-T de una derivación (2026-10-21).

Para mostrar un latido REAL con sus intervalos medidos (Atlas visual, tira
de Academia y de Calculadoras), en vez de un latido dibujado:

1. `median_beat()`: mediana muestra a muestra de los latidos alineados en R
   (anotados o detectados). Quita ruido sin promediar latidos raros.
2. `delineate()`: sobre ese latido,
   - QRS: criterio de pendiente: el complejo empieza y termina donde
     |dV/dt| cae por debajo del 6 % de su máximo y se mantiene así al
     menos 8 ms (el delineador de `clinical/qrs_delineation.py` sigue
     aislado del flujo vivo -- Fase 3 sin autorizar -- y no se usa aquí);
   - P: pico = mayor desviación respecto a la línea de base antes del QRS;
     inicio/fin donde la desviación cae por debajo del 20 % del pico;
   - fin de T: método de la tangente (la tangente en la pendiente más
     pronunciada de la rama descendente de T corta la línea de base),
     el estándar para medir QT (Postema & Wilde, 2014).

Las pendientes se miden sobre el latido suavizado (Savitzky-Golay: ~8 ms
para el QRS, 20 ms para P y 40 ms para T). Sin eso, en una T baja la
"pendiente más pronunciada" la decidía el escalón de cuantización del
registro (0.005 mV en la MIT-BIH) y no la onda: el fin de T salía hasta
50 ms antes.

Medición automática educativa: puede diferir unos milisegundos de la
medición manual de un cardiólogo.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Sequence

import numpy as np

TANGENT_CITATION = (
    "Postema PG, Wilde AAM. The measurement of the QT interval. Curr Cardiol Rev. 2014;10(3):287-294."
)


@dataclass(frozen=True)
class Beat:
    t_ms: np.ndarray       # tiempo relativo a R (ms)
    v: np.ndarray          # mV
    fs: float
    n_beats: int
    rr_ms: float           # RR mediano de los latidos usados


@dataclass(frozen=True)
class Delineation:
    p_on: float
    p_peak: float
    p_off: float
    qrs_on: float
    r: float
    qrs_off: float
    t_on: float
    t_peak: float
    t_off: float
    baseline_mv: float
    p_amp_mv: float
    r_amp_mv: float
    t_amp_mv: float

    @property
    def pr_ms(self) -> float:
        return self.qrs_on - self.p_on

    @property
    def qrs_ms(self) -> float:
        return self.qrs_off - self.qrs_on

    @property
    def qt_ms(self) -> float:
        return self.t_off - self.qrs_on

    def qtc_bazett_ms(self, rr_ms: float) -> float:
        return self.qt_ms / np.sqrt(rr_ms / 1000.0)


def median_beat(signal: np.ndarray, r_samples: Sequence[int], fs: float, *, pre_ms: float = 320.0,
                post_ms: float = 520.0, max_beats: int = 300) -> Beat:
    """Latido mediano alrededor de las R dadas (se descartan los latidos
    que no caben completos en la señal)."""
    x = np.asarray(signal, dtype=float)
    r = np.asarray(r_samples, dtype=int)
    pre, post = int(round(pre_ms / 1000 * fs)), int(round(post_ms / 1000 * fs))
    r = r[(r - pre >= 0) & (r + post < x.size)][:max_beats]
    if r.size < 3:
        raise ValueError("se necesitan al menos 3 latidos completos")
    stack = np.stack([x[p - pre:p + post] for p in r])
    med = np.median(stack, axis=0)
    t = (np.arange(-pre, post) / fs) * 1000.0
    rr = float(np.median(np.diff(r))) / fs * 1000.0
    return Beat(t_ms=t, v=med, fs=fs, n_beats=int(r.size), rr_ms=rr)


def _smooth(v: np.ndarray, fs: float, window_ms: float, order: int = 3) -> np.ndarray:
    """Savitzky-Golay de ~`window_ms`: conserva la forma y la posición de los
    picos, y quita el ruido que hace inútil una derivada muestra a muestra."""
    from scipy.signal import savgol_filter

    v = np.asarray(v, dtype=float)
    n = int(round(window_ms / 1000.0 * fs)) | 1
    if n <= order + 1 or n >= v.size:
        return v
    return savgol_filter(v, n, order)


def _baseline(beat: Beat, qrs_on_ms: float) -> float:
    """Línea de base: mediana del segmento PR (de -60 a -15 ms antes del QRS)."""
    m = (beat.t_ms > qrs_on_ms - 60) & (beat.t_ms < qrs_on_ms - 15)
    return float(np.median(beat.v[m])) if m.any() else float(np.median(beat.v))


def _qrs_bounds(t: np.ndarray, v: np.ndarray, r_idx: int, *, frac: float = 0.06,
                sustain_ms: float = 8.0) -> tuple:
    """Inicio/fin del QRS por la pendiente (ver docstring del módulo)."""
    dt = float(t[1] - t[0])
    d = np.abs(np.gradient(v, t))
    win = np.nonzero(np.abs(t - t[r_idx]) <= 60)[0]
    thr = frac * float(d[win].max())
    need = max(1, int(round(sustain_ms / dt)))
    i = r_idx
    while i - need >= 0 and t[i] > t[r_idx] - 120:
        if np.all(d[i - need:i] < thr):
            break
        i -= 1
    j = r_idx
    while j + need < t.size and t[j] < t[r_idx] + 160:
        if np.all(d[j:j + need] < thr):
            break
        j += 1
    return i, j


def delineate(beat: Beat) -> Delineation:
    t, raw = beat.t_ms, beat.v
    v = _smooth(raw, beat.fs, 8.0, order=2)
    # Pico R real: la mayor desviación absoluta en ±40 ms de la marca.
    win = np.nonzero(np.abs(t) <= 40)[0]
    r_idx = int(win[np.argmax(np.abs(v[win] - np.median(v)))])
    on_idx, off_idx = _qrs_bounds(t, v, r_idx)
    qrs_on, qrs_off = float(t[on_idx]), float(t[off_idx])
    base = _baseline(beat, qrs_on)
    dev = v - base

    # Onda P: mayor desviación en [QRS-260, QRS-40] ms.
    dev_p = _smooth(raw, beat.fs, 20.0) - base
    pm = np.nonzero((t >= qrs_on - 260) & (t <= qrs_on - 40))[0]
    p_idx = int(pm[np.argmax(np.abs(dev_p[pm]))])
    p_amp = float(dev_p[p_idx])
    thr = 0.2 * abs(p_amp)
    i = p_idx
    while i > pm[0] and abs(dev_p[i]) > thr:
        i -= 1
    j = p_idx
    while j < pm[-1] and abs(dev_p[j]) > thr:
        j += 1
    p_on, p_off = float(t[i]), float(t[j])

    # Onda T: la mayor desviación entre QRS+80 ms y el final de la ventana,
    # medida desde el nivel del segmento ST (si el ST está desnivelado, una
    # T baja quedaría casi igual de lejos de la línea de base que el propio
    # ST y la elección dependería del ruido).
    dev_t = _smooth(raw, beat.fs, 40.0) - base
    grad_t = np.gradient(dev_t, t)
    st = (t >= qrs_off + 40) & (t <= qrs_off + 100)
    st_level = float(np.median(dev_t[st])) if st.any() else 0.0
    tm = np.nonzero((t >= qrs_off + 80) & (t <= min(t[-1] - 10, qrs_on + 0.62 * beat.rr_ms)))[0]
    t_idx = int(tm[np.argmax(np.abs(dev_t[tm] - st_level))])
    t_amp = float(dev_t[t_idx])
    sign = 1.0 if dev_t[t_idx] > st_level else -1.0
    after = np.arange(t_idx, np.nonzero(t <= t[-1] - 10)[0][-1] + 1)
    k = int(after[int(np.argmin(grad_t[after] * sign))])   # rama descendente: pendiente más pronunciada
    s = float(grad_t[k])
    t_off = float(t[k] - dev_t[k] / s) if s * sign < 0 else float(t[after[-1]])
    t_off = float(np.clip(t_off, t[t_idx], t[-1]))
    # Inicio de T: hacia atrás desde el pico, donde la desviación cae por
    # debajo del 20 % de la amplitud de T (sin cruzar el fin del QRS).
    i = t_idx
    while i > 0 and t[i - 1] > qrs_off + 20 and abs(dev_t[i]) > 0.2 * abs(t_amp):
        i -= 1
    t_on = float(t[i])
    return Delineation(
        p_on=p_on, p_peak=float(t[p_idx]), p_off=p_off, qrs_on=qrs_on, r=float(t[r_idx]), qrs_off=qrs_off,
        t_on=t_on, t_peak=float(t[t_idx]), t_off=t_off, baseline_mv=base, p_amp_mv=p_amp,
        r_amp_mv=float(dev[r_idx]), t_amp_mv=t_amp,
    )


@lru_cache(maxsize=1)
def reference_beat(max_beats: int = 300) -> tuple:
    """(Beat, Delineation) del registro real MIT-BIH 100 (MLII, latidos N)."""
    from src.signals.reference_recordings import mitdb_100

    d = mitdb_100()
    normal = np.array([b for b, s in zip(d["beats"], d["symbols"]) if s == "N"])
    normal = normal[normal < d["mlii"].size]
    beat = median_beat(d["mlii"], normal, d["fs"], max_beats=max_beats)
    return beat, delineate(beat)
