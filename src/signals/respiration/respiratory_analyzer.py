"""
Respiratory Signal Analyzer - fase 3 del arco respiratorio (2026-11-07, Art. I)

Reescritura del detector contra los golden tests. Cumple los criterios firmados por Luis:

- D1 FR: 60 / media de los intervalos entre inspiraciones (en segundos); >= 3 respiraciones o "no
  disponible" (None, nunca 0). Antes de aplicar las bandas NEWS2 se redondea al entero con .5 hacia arriba
  (`round_half_up`, explícito; NO `round()` de Python). La banda NEWS2 la calcula la UI con
  `clinical.calculators._news2_rr` (no se copia la tabla aquí). Variabilidad = desviación estándar muestral
  de los intervalos (s), descriptiva. Duración del ciclo = media de los intervalos.
- D2 Apnea (Berry 2012, AASM): caída >= 90 % de la excursión pico respecto a la línea basal previa durante
  >= 10 s. Basal según Berry/Chicago: media de las respiraciones estables de los 120 s previos, o media de las
  3 mayores si el patrón es inestable; en registros cortos, la respiración disponible antes del evento,
  DECLARADA en cada evento. Central/obstructiva: "esfuerzo ausente = caída >= 90 % del esfuerzo respecto a
  su basal" (Criterio BIOCORE, nunca un umbral absoluto). Mixta: PENDING_VALIDATION (definición del manual
  AASM sin verificar): se calcula y se marca pendiente.
- D3 Hipopnea: no se detecta ni se muestra.
- D4 Conteo de apneas, tiempo total de apnea y tasa equivalente por hora de REGISTRO (extrapolada, sin valor
  diagnóstico). Sin categoría de severidad y sin la sigla del índice por hora de sueño.
- D5 Se informa la duración del ciclo; no se mide I:E.
- E11 Un evento ya en curso al inicio del registro (sin basal previa) es "no evaluable" y no cuenta; uno que
  llega al final cuenta solo si tiene >= 10 s dentro del registro y se marca "recortado".

Suprimidos (siguen sin calcularse hasta que Luis firme sus criterios): clasificador de patrón, notas
clínicas, ODI y severidad. Quedan como None.

Todo umbral técnico que NO está en los criterios firmados es HEURISTIC y está declarado en `HEURISTICS`
con su calibración. Ninguna compuerta de amplitud es absoluta: la señal de flujo tiene la escala del
generador (pico = volumen_corriente x FR), así que todo umbral es relativo a la amplitud de la propia señal o
al ruido que se estima de ella.
"""

import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from scipy.signal import find_peaks
from scipy.ndimage import uniform_filter1d, maximum_filter1d

# --- Criterios firmados (no se reinterpretan) ---------------------------------------------------------------
APNEA_DROP_FRACTION = 0.90          # Berry 2012: caída >= 90 % de la excursión pico
APNEA_MIN_DURATION_S = 10.0         # Berry 2012: >= 10 s
BASELINE_WINDOW_S = 120.0           # Berry 2012 / consenso de Chicago: 2 min previos
MIN_BREATHS_FOR_RATE = 3            # D1
STABLE_BREATHS_TO_AVERAGE = 3       # Berry: media de las 3 mayores si el patrón es inestable

# --- HEURISTIC (fuera de los criterios firmados) -------------------------------------------------------------
HEURISTICS = {
    "breath_smoothing_s": (0.25, "media móvil para localizar los picos inspiratorios; calibrada con el prototipo de la fase 1 (error de FR <= 0.03/min)"),
    "apnea_smoothing_s": (0.10, "media móvil para medir los bordes de un evento; con 0.25 s el borde se corre hasta 0.6 s y 9.5 s de silencio llega a contarse"),
    "peak_prominence_noise_multiple": (8.0, "prominencia mínima de un pico = 8 x el ruido suavizado estimado; por debajo de eso un máximo local es ruido (flat/ruido blanco dan 0 respiraciones; SNR 2.5 detecta todas)"),
    "peak_prominence_floor_of_signal": (0.02, "piso relativo: 2 % de la amplitud p95 de la señal (evita prominencia 0 en señales sin ruido)"),
    "onset_fraction_of_crest": (0.10, "el inicio de la inspiración es el punto donde el flujo sube al 10 % de la cresta de ESA respiración (relativo a su profundidad); sirve para medir intervalos entre inspiraciones y no entre crestas (cresta a cresta atenúa la variabilidad: 3 s/5 s dan 3.5/4.5 s)"),
    "min_breath_separation_s": (1.0, "separación mínima entre inspiraciones (limita la FR medible a 60/min, por encima de todo lo que genera el lab)"),
    "baseline_stability_cv": (0.30, "CV máximo de las amplitudes para llamar 'estable' al patrón (Chicago distingue dos regímenes sin dar el corte)"),
    "effort_present_fraction": (0.90, "fracción del evento con esfuerzo presente para llamarlo obstructivo (Criterio BIOCORE)"),
    "effort_absent_fraction": (0.10, "fracción máxima con esfuerzo presente para llamarlo central (Criterio BIOCORE)"),
    "effort_window_cycles": (0.6, "ventana del esfuerzo = 0.6 ciclos (>= medio ciclo garantiza ver una cresta de |seno|)"),
    "effort_min_to_noise": (8.0, "el esfuerzo basal debe superar 8 x su ruido suavizado; si no, el tipo es 'sin esfuerzo medible'"),
    "spo2_stable_cluster_points": (3.0, "SpO2 basal = mediana de las muestras a <= 3 puntos del p95 (3 % = umbral de desaturación de Berry 2012)"),
}


def round_half_up(x: float) -> int:
    """Redondeo explícito al entero con .5 hacia arriba (NO `round()` de Python, que redondea .5 al par)."""
    return int(np.floor(float(x) + 0.5))


@dataclass
class BreathDetection:
    """Una inspiración detectada (cresta del flujo)."""
    breath_num: int
    peak_index: int
    peak_time_s: float
    peak_amplitude: float
    onset_time_s: float = 0.0   # inicio de la inspiración (interpolado): los intervalos de D1 se miden entre inicios


@dataclass
class RespiratoryAnalysis:
    """Resultado del análisis. Los campos suprimidos valen None hasta que Luis firme sus criterios."""
    # D1
    respiratory_rate: Optional[float]            # resp/min, None = no disponible
    respiratory_rate_rounded: Optional[int]      # entero (.5 hacia arriba) para las bandas NEWS2
    rr_variability: Optional[float]              # DE muestral de los intervalos entre inspiraciones (s)
    cycle_duration_s: Optional[float]            # media de los intervalos (s)
    breaths: List[BreathDetection]
    signal_status: str                           # 'ok' | 'sin_senal_respiratoria' | 'datos_insuficientes'
    signal_status_detail: str

    # D2 / D4
    apnea_events: List[Dict]                     # eventos evaluables (cuentan)
    non_evaluable_events: List[Dict]             # p. ej. ya en curso al inicio del registro (no cuentan)
    apnea_count: Optional[int]                   # None si la señal no permite evaluar apneas
    apnea_total_time_s: Optional[float]
    equivalent_rate_per_hour: Optional[float]    # extrapolada, por hora de REGISTRO, sin valor diagnóstico
    record_duration_s: float
    apnea_detected: bool
    apnea_type: str                              # tipo predominante o 'none'
    event_period_s: Optional[float]              # mediana de la separación entre inicios de eventos (>= 2 eventos)
    cheyne_stokes_evaluable: bool
    cheyne_stokes_note: str

    # SpO2 (la procedencia la declara la UI)
    baseline_spo2: float
    minimum_spo2: float
    spo2_nadir_time: float
    time_below_90: float
    time_below_85: float

    # Suprimidos
    breathing_pattern: Optional[str] = None
    severity: Optional[str] = None
    clinical_notes: List[str] = field(default_factory=list)
    oxygen_desaturation_index: Optional[float] = None


class RespiratoryAnalyzer:
    """Analizador respiratorio (fase 3)."""

    def __init__(self, sampling_rate: float = 100):
        self.sampling_rate = sampling_rate
        self.sample_interval = 1.0 / sampling_rate

    # ------------------------------------------------------------------ utilidades
    def _smooth(self, x: np.ndarray, seconds: float) -> np.ndarray:
        return uniform_filter1d(x, max(1, int(round(seconds * self.sampling_rate))))

    def _noise_sd(self, x: np.ndarray) -> float:
        """Ruido blanco por muestra, robusto a la señal: MAD de la segunda diferencia (la respiración casi no tiene curvatura)."""
        if len(x) < 8:
            return 0.0
        d2 = np.diff(x, 2)
        return float(np.median(np.abs(d2 - np.median(d2))) / 0.6745 / np.sqrt(6.0))

    # ------------------------------------------------------------------ API
    def analyze_respiration(
        self,
        airflow: np.ndarray,
        time: np.ndarray,
        spo2: np.ndarray,
        respiratory_effort: Optional[np.ndarray] = None,
    ) -> RespiratoryAnalysis:
        airflow = np.asarray(airflow, dtype=float)
        n = len(airflow)
        fs = self.sampling_rate
        record_s = n / fs

        s_breath = self._smooth(airflow, HEURISTICS["breath_smoothing_s"][0])
        s_apnea = self._smooth(airflow, HEURISTICS["apnea_smoothing_s"][0])
        window = max(1, int(round(HEURISTICS["breath_smoothing_s"][0] * fs)))
        noise_s = self._noise_sd(airflow) / np.sqrt(window)
        a95 = float(np.percentile(np.abs(s_breath), 95)) if n else 0.0

        breaths = self._detect_breaths(s_breath, noise_s, a95)
        status, detail = self._signal_status(breaths, a95, noise_s)

        events, non_eval, evaluable = [], [], status != "sin_senal_respiratoria"
        if evaluable and len(breaths) >= 1:
            events, non_eval = self._detect_apneas(s_apnea, time, breaths, respiratory_effort)

        rr, rr_rounded, sd, cycle = self._respiratory_rate(breaths, events)
        if rr is None and status == "ok":
            status, detail = "datos_insuficientes", f"se detectaron {len(breaths)} respiraciones; D1 exige al menos {MIN_BREATHS_FOR_RATE}"

        count = len(events) if evaluable and len(breaths) >= 1 else None
        total = float(sum(e["duration"] for e in events)) if count is not None else None
        rate_h = (count * 3600.0 / record_s) if count is not None and record_s > 0 else None
        types = [e["type"] for e in events]
        starts = [e["start_time"] for e in events]
        baseline, minimum, nadir_time, t90, t85 = self._analyze_spo2(np.asarray(spo2, dtype=float), np.asarray(time, dtype=float))

        return RespiratoryAnalysis(
            respiratory_rate=rr, respiratory_rate_rounded=rr_rounded, rr_variability=sd, cycle_duration_s=cycle,
            breaths=breaths, signal_status=status, signal_status_detail=detail,
            apnea_events=events, non_evaluable_events=non_eval, apnea_count=count, apnea_total_time_s=total,
            equivalent_rate_per_hour=rate_h, record_duration_s=record_s, apnea_detected=bool(events),
            apnea_type=(max(set(types), key=types.count) if types else "none"),
            event_period_s=(float(np.median(np.diff(starts))) if len(starts) >= 2 else None),
            cheyne_stokes_evaluable=False,
            cheyne_stokes_note=(
                "Un registro de este tamaño no es evaluable como respiración de Cheyne-Stokes: Berry 2012 (AASM) "
                "exige >= 3 eventos centrales consecutivos con ciclo >= 40 s y >= 5 eventos por hora "
                "en un mínimo de 2 horas de monitoreo."),
            baseline_spo2=baseline, minimum_spo2=minimum, spo2_nadir_time=nadir_time,
            time_below_90=t90, time_below_85=t85,
        )

    # ------------------------------------------------------------------ respiraciones
    def _detect_breaths(self, s: np.ndarray, noise_s: float, a95: float) -> List[BreathDetection]:
        if len(s) < 3 or a95 <= 0:
            return []
        prom = max(HEURISTICS["peak_prominence_noise_multiple"][0] * noise_s,
                   HEURISTICS["peak_prominence_floor_of_signal"][0] * a95)
        distance = int(HEURISTICS["min_breath_separation_s"][0] * self.sampling_rate)
        pk, _ = find_peaks(s, prominence=prom, distance=max(1, distance))
        frac = HEURISTICS["onset_fraction_of_crest"][0]
        out = []
        for i, p in enumerate(pk):
            thr = frac * s[p]
            j = int(p)
            while j > 0 and s[j] > thr:
                j -= 1
            if j == 0 and s[0] > thr:
                onset = 0.0
            else:  # interpolación lineal entre j y j+1
                onset = (j + (thr - s[j]) / (s[j + 1] - s[j])) / self.sampling_rate if s[j + 1] != s[j] else j / self.sampling_rate
            out.append(BreathDetection(i, int(p), float(p / self.sampling_rate), float(s[p]), float(onset)))
        return out

    def _signal_status(self, breaths, a95: float, noise_s: float):
        if not breaths:
            return "sin_senal_respiratoria", "ninguna excursión supera el ruido de la propia señal"
        return "ok", ""

    def _respiratory_rate(self, breaths, events):
        if len(breaths) < MIN_BREATHS_FOR_RATE:
            return None, None, None, None
        t = np.array([b.onset_time_s for b in breaths])
        iv, lo, hi = np.diff(t), t[:-1], t[1:]
        keep = np.ones(len(iv), dtype=bool)
        for e in events:  # los intervalos que contienen una apnea no son respiraciones consecutivas
            keep &= ~((lo < e["end_time"]) & (hi > e["start_time"]))
        iv = iv[keep]
        if len(iv) < 2:
            return None, None, None, None
        mean = float(np.mean(iv))
        rr = 60.0 / mean
        return rr, round_half_up(rr), float(np.std(iv, ddof=1)), mean

    # ------------------------------------------------------------------ apneas
    def _runs(self, mask: np.ndarray):
        d = np.diff(np.concatenate([[0], mask.astype(np.int8), [0]]))
        return list(zip(np.where(d == 1)[0], np.where(d == -1)[0]))  # [a, b) semiabierto

    def _baseline(self, breaths, a_idx: int):
        """Línea basal previa al evento (Berry/Chicago). Devuelve (amplitud, n, ventana_s, regla) o None."""
        fs = self.sampling_rate
        t_a = a_idx / fs
        prev = [b for b in breaths if t_a - BASELINE_WINDOW_S <= b.peak_time_s < t_a]
        if not prev:
            return None
        amps = np.array([b.peak_amplitude for b in prev])
        cv = float(np.std(amps) / np.mean(amps)) if len(amps) > 1 and np.mean(amps) > 0 else 0.0
        if len(amps) > STABLE_BREATHS_TO_AVERAGE and cv > HEURISTICS["baseline_stability_cv"][0]:
            value, rule = float(np.mean(np.sort(amps)[-STABLE_BREATHS_TO_AVERAGE:])), "media de las 3 mayores (patrón inestable)"
        else:
            value, rule = float(np.mean(amps)), "media de las respiraciones previas (patrón estable)"
        return value, len(prev), float(t_a - prev[0].peak_time_s), rule

    def _detect_apneas(self, s, time, breaths, effort):
        fs = self.sampling_rate
        n = len(s)
        amps = np.array([b.peak_amplitude for b in breaths])
        b_max = float(np.max(amps))
        events, non_eval = [], []
        a_abs = np.abs(s)
        # candidatos generosos (umbral sobre la mayor cresta); se refinan con la basal previa de cada evento
        for a, b in self._runs(a_abs < (1.0 - APNEA_DROP_FRACTION) * b_max):
            if (b - a) / fs < APNEA_MIN_DURATION_S - 2.0:  # los bordes se afinan abajo; el piso evita revisar ruido
                continue
            if a == 0:
                non_eval.append({"start_time": float(time[0]), "end_time": float(time[0]) + (b - a) / fs,
                                 "duration": (b - a) / fs, "reason": "ya en curso al inicio del registro (sin basal previa)"})
                continue
            base = self._baseline(breaths, a)
            if base is None:
                non_eval.append({"start_time": float(time[a]), "end_time": float(time[0]) + b / fs, "duration": (b - a) / fs,
                                 "reason": "sin respiración previa que sirva de basal"})
                continue
            value, n_prev, win_s, rule = base
            thr = (1.0 - APNEA_DROP_FRACTION) * value
            # run real con la basal del evento, alrededor del candidato
            mid = (a + b) // 2
            if a_abs[mid] >= thr:
                continue
            lo = mid
            while lo > 0 and a_abs[lo - 1] < thr:
                lo -= 1
            hi = mid
            while hi < n - 1 and a_abs[hi + 1] < thr:
                hi += 1
            truncated = hi == n - 1
            dur = (hi + 1 - lo) / fs
            if lo == 0:
                non_eval.append({"start_time": float(time[0]), "end_time": float(time[0]) + dur, "duration": dur,
                                 "reason": "ya en curso al inicio del registro (sin basal previa)"})
                continue
            if dur < APNEA_MIN_DURATION_S:
                continue
            ev = {
                "start_time": float(time[lo]), "end_time": float(time[0]) + (hi + 1) / fs, "duration": dur,
                "truncated": bool(truncated),
                "baseline": {"amplitude": value, "n_breaths": n_prev, "window_s": win_s, "rule": rule,
                             "declared_short": bool(win_s < BASELINE_WINDOW_S - 1.0)},
            }
            ev.update(self._classify(ev, lo, hi, breaths, effort, s_effort_cache=None))
            events.append(ev)
        events.sort(key=lambda e: e["start_time"])
        return events, non_eval

    def _classify(self, ev, lo, hi, breaths, effort, s_effort_cache):
        """Tipo por esfuerzo (Criterio BIOCORE). Mixta: PENDING_VALIDATION."""
        if effort is None:
            return {"type": "unknown", "type_detail": "sin canal de esfuerzo", "type_label": "Criterio BIOCORE", "mixed_pending": False}
        fs = self.sampling_rate
        eff = np.abs(self._smooth(np.asarray(effort, dtype=float), HEURISTICS["breath_smoothing_s"][0]))  # suavizar CON signo y luego |.|: promediar |ruido| lo dejaría en 0.8 sd
        noise = self._noise_sd(np.asarray(effort, dtype=float)) / np.sqrt(max(1, int(round(HEURISTICS["breath_smoothing_s"][0] * fs))))
        pre_a = max(0, lo - int(BASELINE_WINDOW_S * fs))
        pre = eff[pre_a:lo]
        # la basal de esfuerzo se toma de las cimas previas (p95 del esfuerzo suavizado)
        e_base = float(np.percentile(pre, 95)) if len(pre) else 0.0
        if e_base < HEURISTICS["effort_min_to_noise"][0] * noise:
            return {"type": "unknown", "type_detail": "esfuerzo basal no medible", "type_label": "Criterio BIOCORE", "mixed_pending": False}
        cyc = ev_cycle = None
        t = np.array([b.peak_time_s for b in breaths if b.peak_time_s < lo / fs])
        cycle = float(np.median(np.diff(t))) if len(t) >= 3 else 4.0
        w = max(int(HEURISTICS["effort_window_cycles"][0] * cycle * fs), int(1.0 * fs))
        env = maximum_filter1d(eff, w)
        a_i, b_i = lo + w // 2, hi + 1 - w // 2
        seg = env[a_i:b_i] if b_i > a_i else env[lo:hi + 1]
        present = float(np.mean(seg >= (1.0 - APNEA_DROP_FRACTION) * e_base))
        if present >= HEURISTICS["effort_present_fraction"][0]:
            kind = "obstructive"
        elif present <= HEURISTICS["effort_absent_fraction"][0]:
            kind = "central"
        else:
            kind = "mixed"
        return {"type": kind, "type_detail": f"esfuerzo presente en {present:.0%} del evento", "type_label": "Criterio BIOCORE",
                "mixed_pending": kind == "mixed"}

    # ------------------------------------------------------------------ SpO2
    def _analyze_spo2(self, spo2: np.ndarray, time: np.ndarray):
        fs = self.sampling_rate
        p95 = np.percentile(spo2, 95)
        cluster = spo2[spo2 >= p95 - HEURISTICS["spo2_stable_cluster_points"][0]]
        baseline = float(np.median(cluster))
        minimum = float(np.min(spo2))
        nadir_time = float(time[int(np.argmin(spo2))])
        return baseline, minimum, nadir_time, float(np.sum(spo2 < 90) / fs), float(np.sum(spo2 < 85) / fs)
