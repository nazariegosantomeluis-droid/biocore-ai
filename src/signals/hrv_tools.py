"""Herramientas puras de HRV para la app (2026-10-19): lectura de series RR
desde archivo y geometría del gráfico de Poincaré.

Sin Streamlit, sin estado -- lo consume `app/main.py::render_hrv_page()` y
se prueba aparte (`tests/test_hrv_tools.py`).

- `parse_rr_file()`: acepta los formatos de exportación habituales (un RR por
  línea, CSV con encabezado y varias columnas, separadores `,` `;` tab o
  espacio, decimales con coma europea). Detecta si los valores vienen en
  segundos y los pasa a ms. DECLARA lo que hizo (líneas ignoradas, unidad
  detectada, valores fuera de rango) en vez de filtrar en silencio.
- `poincare_sd1_sd2()`: SD1/SD2 según Brennan et al. 2001
  (`POINCARE_CITATION`): SD1² = ½·Var(ΔRR), SD2² = 2·SDNN² − ½·Var(ΔRR).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Union

import numpy as np

POINCARE_CITATION = (
    "Brennan M, Palaniswami M, Kamen P. Do existing measures of Poincaré plot geometry reflect "
    "nonlinear features of heart rate variability? IEEE Trans Biomed Eng 2001;48(11):1342–1347"
)

# Rango fisiológico plausible de un intervalo RR (≈ 30–200 lpm). Fuera de él
# suele ser artefacto o latido ectópico mal detectado -- se REPORTA, y solo
# se excluye si quien llama lo pide explícitamente.
RR_PLAUSIBLE_MS: Tuple[float, float] = (300.0, 2000.0)

_NUMBER = re.compile(r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?")


@dataclass
class RRParseResult:
    rr_ms: np.ndarray
    unit_detected: str                 # "ms" o "s" (convertido a ms)
    lines_skipped: int                 # líneas sin ningún número (encabezados, vacías)
    column_used: Optional[int]         # None = un valor por línea; k = k-ésima columna (desde 1)
    out_of_range_idx: List[int] = field(default_factory=list)

    @property
    def n_out_of_range(self) -> int:
        return len(self.out_of_range_idx)


def _numbers_in_line(line: str) -> List[float]:
    # Coma decimal europea: "0,812;0,795" o "812,5 ; 799,1". Solo si la línea
    # usa ';' o tabulador como separador (si no, la coma ES el separador).
    if ("," in line) and (";" in line or "\t" in line):
        line = line.replace(",", ".")
    return [float(tok) for tok in _NUMBER.findall(line)]


def parse_rr_file(content: Union[str, bytes], *, exclude_out_of_range: bool = False) -> RRParseResult:
    """Serie RR (en ms) a partir del texto de un archivo .csv/.txt."""
    if isinstance(content, bytes):
        content = content.decode("utf-8-sig", errors="replace")

    rows: List[List[float]] = []
    skipped = 0
    for raw in content.splitlines():
        nums = _numbers_in_line(raw.strip())
        if nums:
            rows.append(nums)
        else:
            skipped += 1

    if not rows:
        return RRParseResult(np.array([], dtype=float), "ms", skipped, None)

    single_value_lines = sum(1 for r in rows if len(r) == 1)
    column_used: Optional[int]
    if len(rows) == 1 or single_value_lines >= len(rows) / 2:
        # Una sola línea con toda la serie ("800, 820, 790"), o un RR por
        # línea (si alguna trae varios, se aplanan en orden).
        values = [v for r in rows for v in r]
        column_used = None
    else:
        # CSV de varias columnas (índice/tiempo + RR): la última columna es la
        # convención de los exportadores más comunes (Polar, Kubios, Elite HRV).
        width = max(len(r) for r in rows)
        values = [r[-1] for r in rows if len(r) >= 2]
        column_used = width

    rr = np.asarray(values, dtype=float)
    rr = rr[np.isfinite(rr)]
    unit = "ms"
    if rr.size and float(np.median(rr)) < 10.0:
        rr = rr * 1000.0  # venía en segundos
        unit = "s"

    lo, hi = RR_PLAUSIBLE_MS
    bad = [int(i) for i in np.flatnonzero((rr < lo) | (rr > hi))]
    if exclude_out_of_range and bad:
        rr = np.delete(rr, bad)
    return RRParseResult(rr, unit, skipped, column_used, bad)


def poincare_sd1_sd2(rr_ms: np.ndarray) -> Optional[Tuple[float, float]]:
    """(SD1, SD2) en ms, o `None` con menos de 3 intervalos."""
    x = np.asarray(rr_ms, dtype=float)
    if x.size < 3:
        return None
    diffs = np.diff(x)
    sd1 = float(np.sqrt(np.var(diffs, ddof=1) / 2.0))
    sdnn = float(np.std(x, ddof=1))
    sd2_sq = 2.0 * sdnn ** 2 - sd1 ** 2
    sd2 = float(np.sqrt(sd2_sq)) if sd2_sq > 0 else 0.0
    return sd1, sd2
