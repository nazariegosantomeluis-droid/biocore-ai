"""
Engagement Index (2026-10-18) -- β/(α+θ), Pope, Bogart & Bartolome 1995,
RELATIVO al baseline de reposo del propio sujeto. Firma del experto (Luis):
índice de estado operativo (no patología), gramática neutra, reportado como
% de cambio respecto al reposo -- el uso original del sistema biocibernético
de Pope, porque el valor absoluto varía entre sujetos y no admite un corte
universal. Por eso, a diferencia de DAR/TBR/BAR (un valor absoluto del
espectro de toda la señal), tiene capa de baseline, como el Mu ERD.

Hermano de `erd_detector.py`: genérico 1-D (`signal` + `fs`), el instante de
la tarea es CONOCIDO (`t_task`, nunca descubierto), mismas ventanas
baseline -> tramo. Una sola cadena espectral (gráfico temporal,
2026-10-18): `EegAnalyzer.windowed_band_power()` filtra la señal completa
UNA vez y da el band power de cada ventana de 1s con el rechazo de
artefactos de Arco 2A -- los MISMOS bordes de banda y la misma barandilla de
motor Welch que BAR/DAR/TBR. De ahí sale la curva β/(α+θ) por ventana
(`engagement_curve`), y el baseline y la tarea son la MEDIA DE ESA CURVA
sobre las ventanas limpias contenidas en cada tramo -- el estimador de Pope
(índice por ventana + promedio móvil). La curva, la línea de baseline del
gráfico y el % no pueden desviarse entre sí: son el mismo cálculo. Cada
tramo exige `MIN_CLEAN_EEG_DURATION_S` de ventanas limpias; nunca se mezcla
reposo con tarea.

AISLADO DEL UPS (decisión declarada): el engagement relativo es una
propiedad de una SESIÓN (reposo vs. tarea), no un valor puntual de estado
que un snapshot del organismo pueda llevar -- vive como el ERD, en el EEG
Neuro Lab, sin importarse desde `builder.py`/`schema.py`/`repository.py` ni
reexportarse desde `src/signals/eeg/__init__.py`.

NOTA DE HONESTIDAD (Art. I): `detect_engagement()` declara `available=False`
con motivo ante señal demasiado corta, ventanas fuera de la señal, ventana
sin señal limpia suficiente, α+θ ≈ 0 (cociente indefinido) o engagement de
baseline ≈ 0 (cambio relativo indefinido) -- nunca un engagement de relleno.
Validado contra el patrón `engagement_task` de `eeg_generator.py` (cambio
SINTÉTICO, conocido por construcción); su comportamiento sobre captura EEG
real de un operador es trabajo futuro.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np

from .eeg_analyzer import MIN_CLEAN_EEG_DURATION_S, EegAnalyzer
from .preprocessing import MIN_FILTERABLE_SAMPLES

# Cita firmada por el experto. Autores, año y título transcritos verbatim de
# la firma; la revista se corrigió al verificarla en PubMed (PMID 7647180,
# doi:10.1016/0301-0511(95)05116-3): el artículo es de Biological Psychology,
# no de IEEE Trans. Systems, Man, and Cybernetics -- mismo criterio que la
# corrección de cita del TBR (qué fuente respalda qué afirmación).
ENGAGEMENT_CITATION: str = (
    "Pope, A. T., Bogart, E. H., & Bartolome, D. S. (1995). Biocybernetic system evaluates indices "
    "of operator engagement in automated task. Biological Psychology, 40(1-2), 187-195 -- "
    "relativo al baseline de reposo del propio sujeto"
)

# Cláusula de alcance -- viaja con cada resultado, disponible o no (patrón
# `MU_ERD_SCOPE_NOTE`).
ENGAGEMENT_SCOPE_NOTE: str = (
    "índice de engagement relativo al reposo del propio sujeto (Pope 1995); el valor absoluto "
    "varía entre sujetos, se interpreta como cambio dentro de la sesión."
)

# Piso RELATIVO, no absoluto como `_BAR_ALPHA_FLOOR` (1e-9 µV²): medido al
# construir este detector, la fuga espectral del Welch deja "≈ 0" muy por
# encima de un piso absoluto -- β pura dio α+θ ≈ 3e-6·β (engagement ≈ 370000)
# y un reposo de solo alfa dio β/(α+θ) ≈ 3e-9 (cambio relativo ≈ 1e10 %).
# Un cociente adimensional pide un piso adimensional: una banda con menos de
# una milésima de la potencia de la otra se trata como "sin ritmo medible".
# Default de ingeniería, no umbral clínico citado.
_ENGAGEMENT_RELATIVE_FLOOR: float = 1e-3


def engagement_index(beta_power: float, alpha_power: float, theta_power: float) -> Optional[float]:
    """Engagement absoluto de UNA ventana: P_β / (P_α + P_θ). `None` si
    alguna potencia falta/no es finita o si α+θ ≈ 0 (menos de
    `_ENGAGEMENT_RELATIVE_FLOOR` de β+α+θ) -- indefinido, nunca infinito.
    Su valor crudo no se interpreta solo (varía entre sujetos): ver
    `detect_engagement()`."""
    if beta_power is None or alpha_power is None or theta_power is None:
        return None
    if not all(np.isfinite(p) for p in (beta_power, alpha_power, theta_power)):
        return None
    denominator = float(alpha_power) + float(theta_power)
    if denominator <= _ENGAGEMENT_RELATIVE_FLOOR * (denominator + float(beta_power)):
        return None
    return float(beta_power) / denominator


def classify_engagement_change(change_pct: Optional[float]) -> Tuple[str, str, str]:
    """Dirección firmada, `(nivel, etiqueta, badge)` para `render_metric_card`
    bajo `GRAMMAR_NEUTRAL_STATE` (marco accent, nunca semáforo). Solo el
    signo: la firma define dirección, no zonas -- no se inventa una banda
    muerta ni un umbral de "cambio significativo" que Pope no estableció."""
    if change_pct is None:
        return ("no_disponible", "no disponible", "")
    if change_pct > 0:
        return ("aumento", "mayor enganche atencional / concentración activa", "↑")
    if change_pct < 0:
        return ("descenso", "desatención / somnolencia", "↓")
    return ("sin_cambio", "sin cambio respecto al baseline", "→")


@dataclass(frozen=True)
class EngagementResult:
    """Salida de `detect_engagement()` -- espejo de `ErdResult`.
    `available=False` -> `engagement_relative_pct` es `None`, los valores
    absolutos son `None` o parciales (lo que se alcanzó a medir antes de
    declinar) y `reason` explica por qué. Las ventanas son las absolutas
    `[inicio, fin)` en segundos que el detector usó -- quien dibuje la
    medición dibuja ESTAS, no las recalcula.

    `engagement_curve`/`curve_time`: β/(α+θ) de cada ventana de 1s y su
    centro en segundos; `NaN` en las ventanas rechazadas como artefacto o
    con α+θ ≈ 0 (un hueco honesto, no un valor interpolado). `None` siempre
    que el resultado declina -- nunca una curva de ceros ni de relleno."""

    available: bool
    baseline_window: Tuple[float, float]
    task_window: Tuple[float, float]
    engagement_relative_pct: Optional[float] = None
    baseline_value: Optional[float] = None
    task_value: Optional[float] = None
    reason: Optional[str] = None
    engagement_curve: Optional[np.ndarray] = None
    curve_time: Optional[np.ndarray] = None
    scope_note: str = ENGAGEMENT_SCOPE_NOTE


def _engagement_series(signal: np.ndarray, fs: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    """La única cadena espectral del detector: `(curva, tiempo, limpia,
    duración_de_ventana_s)`, una entrada por ventana de
    `EegAnalyzer.windowed_band_power()`."""
    per_window, window_s = EegAnalyzer(fs=fs).windowed_band_power(signal)
    clean = np.array([bp is not None for bp in per_window], dtype=bool)
    values = [engagement_index(bp["beta"], bp["alpha"], bp["theta"]) if bp is not None else None for bp in per_window]
    curve = np.array([np.nan if v is None else v for v in values], dtype=float)
    curve_time = (np.arange(len(per_window)) + 0.5) * window_s
    return curve, curve_time, clean, window_s


def _segment_mean(
    curve: np.ndarray, curve_time: np.ndarray, clean: np.ndarray, window_s: float,
    window: Tuple[float, float], label: str,
) -> Tuple[Optional[float], Optional[str]]:
    """Media de la curva sobre las ventanas limpias contenidas por completo
    en `window` -- `(valor, None)` o `(None, motivo)`."""
    eps = 1e-9
    inside = (curve_time - window_s / 2 >= window[0] - eps) & (curve_time + window_s / 2 <= window[1] + eps)
    clean_s = float(np.count_nonzero(inside & clean)) * window_s
    if clean_s < MIN_CLEAN_EEG_DURATION_S:
        return None, (
            f"{label}: {clean_s:.1f}s limpios de {window[1] - window[0]:.1f}s pedidos tras rechazo de artefactos "
            f"(mínimo {MIN_CLEAN_EEG_DURATION_S:.0f}s) -- no se calcula engagement sobre el fragmento"
        )
    defined = curve[inside & clean & np.isfinite(curve)]
    if defined.size * window_s < MIN_CLEAN_EEG_DURATION_S:
        return None, f"{label}: potencia α+θ indistinguible de cero -- engagement β/(α+θ) indefinido"
    return float(np.mean(defined)), None


def detect_engagement(
    signal: np.ndarray,
    fs: float,
    t_task: float,
    baseline_duration_s: float = 10.0,
    task_offset_s: float = 1.0,
    task_duration_s: float = 12.0,
) -> EngagementResult:
    """Engagement relativo = (E_tarea - E_baseline) / E_baseline · 100, con
    E = β/(α+θ) de cada ventana. Baseline = `[t_task - baseline_duration_s,
    t_task)`; tarea = `[t_task + task_offset_s, ... + task_duration_s)` --
    el offset salta la transición para medir la meseta asentada."""
    signal = np.asarray(signal, dtype=float).flatten()
    total_duration_s = len(signal) / fs
    baseline_window = (t_task - baseline_duration_s, t_task)
    task_window = (t_task + task_offset_s, t_task + task_offset_s + task_duration_s)

    def declined(reason: str, baseline_value: Optional[float] = None) -> EngagementResult:
        return EngagementResult(
            available=False, baseline_window=baseline_window, task_window=task_window,
            baseline_value=baseline_value, reason=reason,
        )

    if len(signal) < MIN_FILTERABLE_SAMPLES:
        return declined(
            f"señal de {len(signal)} muestras -- se necesitan al menos {MIN_FILTERABLE_SAMPLES} para "
            "filtrar; no hay engagement que calcular"
        )
    if baseline_window[0] < 0.0:
        return declined(
            f"la ventana de baseline pedida [{baseline_window[0]:.2f}s, {baseline_window[1]:.2f}s) empieza "
            "antes del inicio de la señal -- se necesita más reposo antes de la tarea"
        )
    if task_window[1] > total_duration_s:
        return declined(
            f"la ventana de tarea pedida [{task_window[0]:.2f}s, {task_window[1]:.2f}s) excede la duración "
            f"de la señal ({total_duration_s:.2f}s)"
        )

    curve, curve_time, clean, window_s = _engagement_series(signal, fs)

    baseline_value, reason = _segment_mean(curve, curve_time, clean, window_s, baseline_window, "baseline")
    if reason is not None:
        return declined(reason)
    if baseline_value < _ENGAGEMENT_RELATIVE_FLOOR:
        return declined(
            "engagement de baseline indistinguible de cero (sin potencia beta en reposo) -- el cambio "
            "relativo es indefinido sobre un denominador nulo",
            baseline_value=baseline_value,
        )

    task_value, reason = _segment_mean(curve, curve_time, clean, window_s, task_window, "tramo de tarea")
    if reason is not None:
        return declined(reason, baseline_value=baseline_value)

    return EngagementResult(
        available=True, baseline_window=baseline_window, task_window=task_window,
        engagement_relative_pct=(task_value - baseline_value) / baseline_value * 100.0,
        baseline_value=baseline_value, task_value=task_value,
        engagement_curve=curve, curve_time=curve_time,
    )
