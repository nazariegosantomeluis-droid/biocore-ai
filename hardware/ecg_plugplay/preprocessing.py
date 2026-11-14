"""Preprocesamiento al vuelo: muestras crudas del ADC → señal limpia en mV.

Tres piezas:

1. `SamplePipeline.push()` recibe cada bloque de muestras y:
   - detecta muestras perdidas por el índice `seq`: huecos de 1 o 2 muestras
     se interpolan (y se marcan); huecos mayores se rellenan con NaN, que
     invalidan la ventana: no se inventa señal que no llegó;
   - marca saturación del ADC (muestras pegadas a 0 o al máximo) y electrodo
     suelto (bandera LO del AD8232);
   - convierte cuentas a mV aproximados en el electrodo (ADC sin calibrar y
     ganancia nominal de la placa: sirve para morfología y ritmo, no como
     medición de amplitud exacta);
   - filtra en línea (filtro causal): pasa-banda 0.5–40 Hz y notch de 60 Hz,
     con el estado del filtro guardado entre llamadas para que no haya saltos
     entre bloques. Tras una
     interrupción (electrodo suelto, hueco, saturación larga) el filtro se
     reinicia y las primeras muestras se marcan «estabilizando».
2. `assess_window()` decide si una ventana sirve y, si no, dice por qué.
3. `normalize_for_model()` deja la ventana como la espera el modelo:
   arreglo float32 de forma (1, 1000) entre 0 y 1.

Nota: 0.5–40 Hz es banda de monitoreo, no diagnóstica (`FILTER_LIMITS_SOURCE`):
un corte bajo de 0.5 Hz deforma el nivel del segmento ST y el diagnóstico pide
al menos 150 Hz arriba. Esta señal no sirve para enseñar elevación o depresión
del ST ni para medir amplitudes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy.signal import butter, iirnotch, sosfilt, sosfilt_zi, tf2sos

from .config import AcquisitionConfig, QualityHeuristics

FILTER_LIMITS_SOURCE = (
    'Kligfield P, Gettes LS, Bailey JJ, et al. Recommendations for the Standardization and '
    'Interpretation of the Electrocardiogram: Part I. Circulation. 2007;115:1306-1324. '
    'doi:10.1161/CIRCULATIONAHA.106.180200 («a 0.5-Hz low-frequency cutoff introduces considerable '
    'distortion into the ECG, particularly with respect to the level of the ST segment»; corte alto '
    'de al menos 150 Hz en adultos).'
)

FLAG_LEADOFF = 1 << 0
FLAG_SATURATED = 1 << 1
FLAG_MISSING = 1 << 2
FLAG_INTERPOLATED = 1 << 3
FLAG_SETTLING = 1 << 4


class StreamingFilter:
    """Pasa-banda Butterworth + notch opcional, aplicado por trozos (causal)."""

    def __init__(self, fs: float, band: Tuple[float, float], order: int = 2,
                 notch_hz: Optional[float] = 60.0, notch_q: float = 30.0) -> None:
        sections = [butter(order, band, btype='bandpass', fs=fs, output='sos')]
        if notch_hz:
            b, a = iirnotch(notch_hz, notch_q, fs=fs)
            sections.append(tf2sos(b, a))
        self.sos = np.vstack(sections)
        self._zi_unit = sosfilt_zi(self.sos)
        self._zi: Optional[np.ndarray] = None

    def reset(self) -> None:
        self._zi = None

    def process(self, x: np.ndarray) -> np.ndarray:
        x = np.asarray(x, dtype=float)
        if x.size == 0:
            return x
        if self._zi is None:
            # Arranca como si la señal llevara un rato en x[0]: sin escalón inicial.
            self._zi = self._zi_unit * x[0]
        y, self._zi = sosfilt(self.sos, x, zi=self._zi)
        return y


@dataclass
class AdcParams:
    bits: int = 12
    vref: float = 3.3
    gain: float = 1100.0

    @property
    def full_scale(self) -> int:
        return (1 << int(self.bits)) - 1

    def to_mv(self, counts: np.ndarray) -> np.ndarray:
        volts = np.asarray(counts, dtype=float) / self.full_scale * self.vref
        return (volts - self.vref / 2.0) / self.gain * 1000.0


class SamplePipeline:
    """Convierte bloques crudos en muestras listas para el buffer de ventanas."""

    def __init__(self, fs: float, adc: AdcParams, heuristics: QualityHeuristics,
                 filt: Optional[StreamingFilter], max_fill: int) -> None:
        self.fs = float(fs)
        self.adc = adc
        self.h = heuristics
        self.filt = filt
        self.max_fill = int(max_fill)
        self.settle_n = int(round(heuristics.settle_s * fs))
        self.sat_reset_n = max(1, int(round(heuristics.saturation_reset_s * fs)))
        self.stats: Dict[str, int] = {}
        self.reset()

    def reset(self) -> None:
        self.next_seq: Optional[int] = None
        self.last_raw: Optional[float] = None
        self._need_reset = True
        self._first_reset = True
        self._settle_left = 0
        self._sat_run = 0
        if self.filt is not None:
            self.filt.reset()
        self.stats = {'recibidas': 0, 'perdidas': 0, 'interpoladas': 0, 'reinicios_placa': 0}

    def push(self, values: Sequence[float], seq: Optional[int] = None, leadoff: int = 0) -> Dict[str, np.ndarray]:
        vals = np.asarray(values, dtype=float)
        n = vals.size
        if seq is None:
            seq = self.next_seq if self.next_seq is not None else 0
        fill_raw = np.empty(0)
        fill_flags = np.empty(0, dtype=np.uint8)
        fill_seq = np.empty(0, dtype=np.int64)
        if self.next_seq is not None:
            gap = seq - self.next_seq
            if gap < 0:
                # El índice retrocedió: la placa se reinició. Se empieza de nuevo sin rellenar.
                self.stats['reinicios_placa'] += 1
                self._need_reset = True
            elif 0 < gap <= self.h.max_interp_gap and self.last_raw is not None and n:
                fill_raw = np.linspace(self.last_raw, vals[0], gap + 2)[1:-1]
                fill_flags = np.full(gap, FLAG_INTERPOLATED, dtype=np.uint8)
                fill_seq = np.arange(seq - gap, seq, dtype=np.int64)
                self.stats['interpoladas'] += gap
            elif gap > self.h.max_interp_gap:
                k = min(gap, self.max_fill)
                fill_raw = np.full(k, np.nan)
                fill_flags = np.full(k, FLAG_MISSING, dtype=np.uint8)
                fill_seq = np.arange(seq - k, seq, dtype=np.int64)
                self.stats['perdidas'] += gap
                self._need_reset = True

        raw = np.concatenate([fill_raw, vals])
        flags = np.concatenate([fill_flags, np.zeros(n, dtype=np.uint8)])
        seqs = np.concatenate([fill_seq, np.arange(seq, seq + n, dtype=np.int64)])
        new = slice(raw.size - n, raw.size)
        if leadoff:
            flags[new] |= FLAG_LEADOFF
        margin = self.h.saturation_margin_counts
        saturated = (vals <= margin) | (vals >= self.adc.full_scale - margin)
        flags[new] |= np.where(saturated, FLAG_SATURATED, 0).astype(np.uint8)

        mv_in = self.adc.to_mv(raw)
        filterable = ((flags & (FLAG_LEADOFF | FLAG_MISSING)) == 0) & np.isfinite(mv_in)
        reset_before = np.zeros(raw.size, dtype=bool)
        for i in range(raw.size):
            if not filterable[i]:
                self._need_reset = True
                self._sat_run = 0
                continue
            if flags[i] & FLAG_SATURATED:
                self._sat_run += 1
            else:
                if self._sat_run >= self.sat_reset_n:
                    self._need_reset = True
                self._sat_run = 0
            if self._need_reset:
                reset_before[i] = True
                self._need_reset = False
                # Al arrancar el filtro empieza sin escalón; tras una interrupción, se espera.
                self._settle_left = 0 if self._first_reset else self.settle_n
                self._first_reset = False
            if self._settle_left > 0:
                flags[i] |= FLAG_SETTLING
                self._settle_left -= 1

        mv = np.full(raw.size, np.nan)
        i = 0
        while i < raw.size:
            if not filterable[i]:
                i += 1
                continue
            j = i + 1
            while j < raw.size and filterable[j] and not reset_before[j]:
                j += 1
            if self.filt is None:
                mv[i:j] = mv_in[i:j]
            else:
                if reset_before[i]:
                    self.filt.reset()
                mv[i:j] = self.filt.process(mv_in[i:j])
            i = j

        self.stats['recibidas'] += n
        self.next_seq = seq + n
        if n:
            self.last_raw = float(vals[-1])
        return {'seq': seqs, 'raw': raw, 'mv': mv, 'flags': flags}


@dataclass
class WindowQuality:
    """Resultado de revisar una ventana. `reasons` vacío = ventana válida."""

    samples: int
    missing: int = 0
    interpolated: int = 0
    leadoff: int = 0
    saturated: int = 0
    settling: int = 0
    peak_to_peak_mv: Optional[float] = None
    reasons: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.reasons


def _pct(k: int, n: int) -> str:
    return f'{100.0 * k / max(n, 1):.0f} %'


def assess_window(mv: np.ndarray, flags: np.ndarray, h: QualityHeuristics) -> WindowQuality:
    n = int(mv.size)
    q = WindowQuality(
        samples=n,
        missing=int(np.count_nonzero(flags & FLAG_MISSING)),
        interpolated=int(np.count_nonzero(flags & FLAG_INTERPOLATED)),
        leadoff=int(np.count_nonzero(flags & FLAG_LEADOFF)),
        saturated=int(np.count_nonzero(flags & FLAG_SATURATED)),
        settling=int(np.count_nonzero(flags & FLAG_SETTLING)),
    )
    finite = np.isfinite(mv)
    if finite.any():
        q.peak_to_peak_mv = float(np.nanmax(mv) - np.nanmin(mv))
    if q.leadoff > h.max_leadoff_fraction * n:
        q.reasons.append(f'electrodo suelto en {_pct(q.leadoff, n)} de la ventana (señal LO del AD8232): '
                         'revisa que los tres electrodos estén bien pegados')
    if q.missing:
        q.reasons.append(f'faltan {q.missing} muestras ({_pct(q.missing, n)}) por pérdida de datos en la transmisión')
    if q.saturated > h.max_saturated_fraction * n:
        q.reasons.append(f'el ADC saturó en {_pct(q.saturated, n)} de la ventana (la señal tocó sus límites): '
                         'revisa el contacto de los electrodos y evita moverte')
    if q.settling:
        q.reasons.append('el filtro se está estabilizando después de una interrupción')
    if not q.reasons:
        if not finite.all():
            q.reasons.append('la ventana tiene valores no numéricos')
        elif q.peak_to_peak_mv is not None and q.peak_to_peak_mv < h.min_peak_to_peak_mv:
            q.reasons.append(f'señal plana: {q.peak_to_peak_mv:.3f} mV de pico a pico tras filtrar '
                             f'(mínimo {h.min_peak_to_peak_mv} mV); ¿están colocados los electrodos?')
    return q


def normalize_for_model(mv: np.ndarray, config: AcquisitionConfig) -> np.ndarray:
    """Escala la ventana a [0, 1] y le da la forma y el tipo que espera el modelo."""
    x = np.asarray(mv, dtype=float)
    if config.normalization == 'robust':
        lo, hi = np.percentile(x, [1.0, 99.0])
        x = np.clip(x, lo, hi)
    else:
        lo, hi = float(np.min(x)), float(np.max(x))
    if not np.isfinite([lo, hi]).all() or hi - lo <= 1e-12:
        raise ValueError('no se puede normalizar una ventana constante o con valores no numéricos')
    return ((x - lo) / (hi - lo)).astype(np.float32).reshape(config.model_input_shape)
