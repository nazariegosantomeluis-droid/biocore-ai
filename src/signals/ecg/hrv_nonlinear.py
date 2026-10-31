"""
HRV no lineal -- SampEn, DFA alfa1 y Poincare (SD1/SD2), 2026-10-31.
Cardiovascular profundo, sub-arco HRV no lineal.

Módulo NUEVO: reemplaza a `src/advanced_hrv.py`, que sigue huérfano y NO se
reusa (su "DFA" devolvía 1.0 de relleno cuando no podía ajustar y su ApEn era
O(N²) y sesgado). Aquí cada métrica o devuelve un número calculado o declina
con motivo (`available=False`); nunca hay un valor de relleno.

Por qué recién ahora: sobre el ruido blanco del viejo "Demo (ECG-derived)" estas
métricas no enseñan nada (DFA alfa≈0.5, SampEn máxima). Los RR de la RSA
(`rsa.py`) tienen estructura, y ahí la complejidad se puede contrastar.

Mínimos de latidos MEDIDOS (2026-10-31, 100-300 series por celda), no tomados
de la literatura sin comprobar:
- SampEn (m=2, r=0.2·SD) sobre ruido blanco gaussiano converge a su valor
  analítico -ln(erf(0.1)) = 2.185; la desviación entre series baja de 0.42 con
  100 latidos a 0.21 con 150-200 y 0.08 con 400, y con 36-60 latidos hasta el
  39 % de las series no tiene coincidencias (SampEn indefinida).
- DFA alfa1 (escalas 4-16): desviación 0.09 con 100 latidos, 0.06 con 200. El
  contraste ruido blanco / 1/f es de ~0.43 en alfa1.
- SD1: error relativo de ~10 % con 50-60 latidos y ~4 % con 400.

Sesgo conocido y medido de DFA alfa1: el ruido blanco da 0.58, no 0.50, con
cualquier N (el ajuste lineal por caja en escalas tan cortas sesga el
exponente; con escalas 16-64 el mismo ruido da 0.46). Por eso el ground truth
se compara con esa referencia, y alfa1 sirve para CONTRASTAR series, no para
leer un valor absoluto.

DFA alfa2 (escalas 16-64) NO se calcula: necesita >1000 latidos y la demo de
30-300 s tiene 36-360. Calcularlo sobre datos insuficientes sería deshonesto.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

SAMPEN_CITATION: str = (
    "Richman JS, Moorman JR (2000). Physiological time-series analysis using approximate entropy and "
    "sample entropy. Am J Physiol Heart Circ Physiol 278(6):H2039-H2049"
)
DFA_CITATION: str = (
    "Peng CK, Havlin S, Stanley HE, Goldberger AL (1995). Quantification of scaling exponents and "
    "crossover phenomena in nonstationary heartbeat time series. Chaos 5(1):82-87"
)
POINCARE_CITATION: str = (
    "Brennan M, Palaniswami M, Kamen P (2001). Do existing measures of Poincare plot geometry reflect "
    "nonlinear features of heart rate variability? IEEE Trans Biomed Eng 48(11):1342-1347"
)

ALPHA2_NOTE: str = "alfa2 (escalas 16-64) requiere >1000 latidos, no disponible en esta duración"

NONLINEAR_SCOPE_NOTE: str = (
    "demostración de métricas de complejidad sobre una serie RR. Las interpretaciones clínicas de la complejidad "
    "autonómica (p. ej. alfa1 reducida) están en la literatura, pero BIOCORE no las firma todavía "
    "(PENDING_VALIDATION): no es un índice de riesgo."
)

MIN_BEATS_NONLINEAR: int = 200
MIN_BEATS_POINCARE: int = 50
# Un muestreo de 250 Hz cuantiza el RR en 4 ms; con SD por debajo de eso, r = 0.2·SD es menor que un
# escalón y SampEn/DFA medirían la cuantización del detector, no la serie.
MIN_RR_SD_MS: float = 4.0

DFA_ALPHA1_SCALES = (4, 16)
SAMPEN_M: int = 2
SAMPEN_R_FRACTION: float = 0.2

# Umbrales de `structure_note`, de las mismas mediciones (200-400 latidos): ruido blanco da alfa1 0.58±0.06
# y SampEn 2.2±0.2; el 1/f da alfa1 1.0; una sinusoide da SampEn 0-0.09.
_NOISE_ALPHA1_MAX: float = 0.70
_NOISE_SAMPEN_MIN: float = 1.9
_PERIODIC_SAMPEN_MAX: float = 0.5


@dataclass(frozen=True)
class MetricResult:
    """Espejo de `RSAResult`: `available=False` -> `value` es `None` y `reason` explica por qué."""

    available: bool
    value: Optional[float] = None
    n_beats: int = 0
    reason: Optional[str] = None


@dataclass(frozen=True)
class PoincareResult:
    available: bool
    sd1_ms: Optional[float] = None
    sd2_ms: Optional[float] = None
    ratio: Optional[float] = None  # SD1/SD2
    n_beats: int = 0
    reason: Optional[str] = None


@dataclass(frozen=True)
class HrvNonlinearResult:
    sampen: MetricResult
    alpha1: MetricResult
    poincare: PoincareResult
    structure_note: Optional[str]
    alpha2_note: str = ALPHA2_NOTE
    scope_note: str = NONLINEAR_SCOPE_NOTE


def _invalid_reason(rr_ms: np.ndarray, minimum: int) -> Optional[str]:
    """Motivo común de declinación, o `None` si la serie sirve."""
    if rr_ms.size < minimum:
        return f"se requieren ≥{minimum} latidos; hay {rr_ms.size}"
    if not np.all(np.isfinite(rr_ms)) or np.any(rr_ms <= 0):
        return "la serie RR contiene valores no válidos (no finitos o ≤ 0)"
    return None


def _flat_reason(rr_ms: np.ndarray) -> Optional[str]:
    sd = float(np.std(rr_ms))
    if sd < MIN_RR_SD_MS:
        return (
            f"SD de los RR {sd:.1f} ms por debajo de {MIN_RR_SD_MS:.0f} ms (un escalón del detector a 250 Hz) -- "
            "la métrica mediría la cuantización, no la serie"
        )
    return None


def sample_entropy(rr_ms, m: int = SAMPEN_M, r_fraction: float = SAMPEN_R_FRACTION) -> MetricResult:
    """SampEn(m, r=r_fraction·SD) de Richman y Moorman: -ln(A/B), con B los pares de plantillas de longitud m
    que coinciden (distancia de Chebyshev <= r) y A los que siguen coincidiendo a longitud m+1. A diferencia de
    ApEn no cuenta la coincidencia de cada plantilla consigo misma. Ambas longitudes usan las mismas N-m
    plantillas. Declina si faltan latidos, la serie es inválida o plana, o no hay coincidencias (A=0 o B=0:
    SampEn indefinida)."""
    x = np.asarray(rr_ms, dtype=float).ravel()
    reason = _invalid_reason(x, MIN_BEATS_NONLINEAR) or _flat_reason(x)
    if reason:
        return MetricResult(False, n_beats=x.size, reason=reason)

    r = r_fraction * float(np.std(x))
    n_templates = x.size - m
    windows = np.lib.stride_tricks.sliding_window_view(x, m)[:n_templates]
    b = a = 0
    # O(N²) por diseño, memoria O(N): una fila de distancias por plantilla.
    for i in range(n_templates - 1):
        match = np.max(np.abs(windows[i + 1:] - windows[i]), axis=1) <= r
        b += int(match.sum())
        a += int((match & (np.abs(x[i + 1 + m:n_templates + m] - x[i + m]) <= r)).sum())
    if a == 0 or b == 0:
        return MetricResult(
            False, n_beats=x.size,
            reason=f"sin coincidencias de plantillas (A={a}, B={b}) -- SampEn indefinida con esta serie",
        )
    return MetricResult(True, value=float(np.log(b / a)), n_beats=x.size)


def dfa_alpha1(rr_ms) -> MetricResult:
    """Exponente de escala alfa1 de DFA (Peng 1995) en cajas de 4 a 16 latidos: perfil integrado de la serie sin
    media, cajas sin solape, ajuste lineal por caja, F(n) = raíz del error cuadrático medio, alfa1 = pendiente de
    log F contra log n. Los latidos sobrantes al final de cada escala se descartan. Ver el sesgo medido en el
    docstring del módulo."""
    x = np.asarray(rr_ms, dtype=float).ravel()
    reason = _invalid_reason(x, MIN_BEATS_NONLINEAR) or _flat_reason(x)
    if reason:
        return MetricResult(False, n_beats=x.size, reason=reason)

    profile = np.cumsum(x - x.mean())
    scales = np.arange(DFA_ALPHA1_SCALES[0], DFA_ALPHA1_SCALES[1] + 1)
    fluctuation = []
    for n in scales:
        boxes = profile[: (profile.size // n) * n].reshape(-1, n)
        t = np.arange(n)
        design = np.column_stack([t, np.ones(n)])
        coef, *_ = np.linalg.lstsq(design, boxes.T, rcond=None)
        fluctuation.append(np.sqrt(np.mean((boxes.T - design @ coef) ** 2)))
    alpha = float(np.polyfit(np.log(scales), np.log(fluctuation), 1)[0])
    return MetricResult(True, value=alpha, n_beats=x.size)


def poincare(rr_ms) -> PoincareResult:
    """SD1/SD2 de la nube (RR_n, RR_n+1) (Brennan 2001): desviación a lo ancho de la diagonal (corto plazo, SD1)
    y a lo largo de ella (largo plazo, SD2). Relaciones conocidas que usan los tests: SD1 = RMSSD/√2 y
    SD2² = 2·SDNN² - SD1² (exactas salvo la media de las diferencias, ~0)."""
    x = np.asarray(rr_ms, dtype=float).ravel()
    reason = _invalid_reason(x, MIN_BEATS_POINCARE)
    if reason:
        return PoincareResult(False, n_beats=x.size, reason=reason)
    sd1 = float(np.std((x[:-1] - x[1:]) / np.sqrt(2.0), ddof=1))
    sd2 = float(np.std((x[:-1] + x[1:]) / np.sqrt(2.0), ddof=1))
    return PoincareResult(True, sd1_ms=sd1, sd2_ms=sd2, ratio=sd1 / sd2 if sd2 > 0 else None, n_beats=x.size)


def structure_note(sampen: MetricResult, alpha1: MetricResult) -> Optional[str]:
    """Rótulo sobre la estructura de la serie, solo cuando AMBAS métricas están disponibles; si no, `None`.
    Dice qué se parece la serie (ruido blanco / oscilación casi periódica); no la interpreta clínicamente."""
    if not (sampen.available and alpha1.available):
        return None
    if alpha1.value < _NOISE_ALPHA1_MAX and sampen.value > _NOISE_SAMPEN_MIN:
        return "sin estructura autonómica — señal de ruido (alfa1 y SampEn compatibles con ruido blanco)"
    if sampen.value < _PERIODIC_SAMPEN_MAX:
        return (
            "oscilación casi periódica (SampEn ≈ 0): más regular que cualquier corazón real -- esperable en una "
            "RSA sinusoidal sintética"
        )
    return None


def analyze_hrv_nonlinear(rr_ms) -> HrvNonlinearResult:
    sampen = sample_entropy(rr_ms)
    alpha1 = dfa_alpha1(rr_ms)
    return HrvNonlinearResult(
        sampen=sampen, alpha1=alpha1, poincare=poincare(rr_ms), structure_note=structure_note(sampen, alpha1)
    )
