"""Puente de inferencia: ventanas → modelo (en otro hilo) → resultados.

`InferenceBridge` corre el análisis en un hilo propio, así que un modelo lento
nunca frena la lectura del puerto. Guarda solo la ventana más reciente: si el
modelo tarda más que el salto entre ventanas, la vieja se descarta (y se
cuenta en `dropped`), porque en tiempo real importa lo que está pasando ahora.

Un *analizador* es cualquier función que recibe un `ECGWindow` y devuelve un
dict con alguna de estas claves:

    prediction  lo que diga tu modelo (clase, probabilidades, dict...)
    bpm         frecuencia cardiaca, o None si no se pudo medir
    waves       ondas P-QRS-T (índices y amplitudes)
    notes       lista de textos (p. ej. por qué no hay BPM)
    labels      de dónde salió cada campo: {'bpm': 'TKEO (ECG Lab)', ...}

Listos para usar:

- `ModelAnalyzer`: envuelve tu clase, p. ej. `MiClaseML().procesar_ventana(datos_ecg)`.
- `BiocoreAnalyzer`: usa el motor de BIOCORE (BPM con el detector TKEO del
  ECG Lab, Q-R-S con su delineador validado `delineate_qrs`, P y T con una
  heurística propia, patrón opcional con `classify_ecg_signal`). Etiqueta cada
  cosa con lo que es: el patrón sale de reglas, no de un modelo de ML.
- `CompositeAnalyzer`: junta varios (p. ej. BPM de BIOCORE + predicción de tu modelo).
"""

from __future__ import annotations

import queue
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

from .preprocessing import WindowQuality


@dataclass
class ECGWindow:
    """Una ventana lista para analizar."""

    index: int                         # número de ventana desde que se conectó
    fs: float
    start_seq: int                     # índice de la primera muestra (reloj de la placa)
    ecg_mv: np.ndarray                 # señal limpia (filtrada), mV aproximados en el electrodo
    raw: np.ndarray                    # cuentas crudas del ADC
    flags: np.ndarray                  # banderas por muestra (ver preprocessing.FLAG_*)
    quality: WindowQuality
    model_input: Optional[np.ndarray]  # (1, N) float32 entre 0 y 1; None si la ventana no sirve
    provenance: str                    # 'SENSOR_REAL' o 'SIMULACION'
    source: str                        # p. ej. 'COM3 · Silicon Labs CP210x · fw 1.0'
    t_end: float                       # time.time() al cerrar la ventana
    connection: int = 0                # número de conexión (para ignorar resultados de una ya cerrada)

    @property
    def valid(self) -> bool:
        return self.quality.ok and self.model_input is not None

    @property
    def duration_s(self) -> float:
        return self.ecg_mv.size / self.fs


@dataclass
class WindowResult:
    """Lo que recibe la interfaz por cada ventana (válida o descartada)."""

    window: ECGWindow
    prediction: Any = None
    bpm: Optional[float] = None
    waves: Optional[Dict[str, Any]] = None
    notes: List[str] = field(default_factory=list)
    labels: Dict[str, str] = field(default_factory=dict)
    latency_ms: Optional[float] = None
    error: Optional[str] = None

    @property
    def valid(self) -> bool:
        return self.window.valid and self.error is None

    @property
    def clean_signal(self) -> np.ndarray:
        return self.window.ecg_mv

    @property
    def reasons(self) -> List[str]:
        """Por qué no hay resultado (vacío si todo salió bien)."""
        out = list(self.window.quality.reasons)
        if self.error:
            out.append(self.error)
        return out


Analyzer = Callable[[ECGWindow], Mapping]

_PREDICTION_KEYS = ('prediccion', 'predicción', 'prediction', 'clase', 'label', 'diagnostico')
_WAVE_KEYS = ('ondas', 'waves', 'pqrst')


class ModelAnalyzer:
    """Adapta tu modelo al puente.

    model.method(entrada) se llama con la ventana normalizada (forma (1, N),
    float32, 0 a 1) o, con use='ecg_mv', con la señal filtrada en mV.
    Si tu función devuelve un dict con 'prediccion', 'bpm' u 'ondas', cada
    valor va a su campo; cualquier otra cosa se toma como la predicción.
    """

    def __init__(self, model: Any, method: str = 'procesar_ventana', label: Optional[str] = None,
                 use: str = 'model_input') -> None:
        if use not in ('model_input', 'ecg_mv'):
            raise ValueError("use debe ser 'model_input' o 'ecg_mv'.")
        self.fn = getattr(model, method) if method else model
        self.use = use
        if label:
            self.label = label
        elif method:
            self.label = f'{type(model).__name__}.{method}'
        else:
            self.label = getattr(model, '__name__', 'modelo')

    def __call__(self, window: ECGWindow) -> Dict[str, Any]:
        data = window.model_input if self.use == 'model_input' else window.ecg_mv
        out = self.fn(data)
        result: Dict[str, Any] = {'labels': {'prediction': self.label}}
        if isinstance(out, Mapping):
            pred_key = next((k for k in _PREDICTION_KEYS if k in out), None)
            result['prediction'] = out[pred_key] if pred_key else dict(out)
            if 'bpm' in out:
                result['bpm'] = out['bpm']
                result['labels']['bpm'] = self.label
            wave_key = next((k for k in _WAVE_KEYS if k in out), None)
            if wave_key:
                result['waves'] = out[wave_key]
                result['labels']['waves'] = self.label
        else:
            result['prediction'] = out
        return result


class BiocoreAnalyzer:
    """Motor de BIOCORE sobre la ventana limpia (necesita el repo de BIOCORE en el path).

    - BPM: picos R de `ECGAnalyzer.detect_r_peaks_tkeo` (el detector validado del
      ECG Lab) y la misma fórmula que `_measure_ecg_heart_rate_tkeo` (60·fs / RR
      medio). Con menos de 2 picos R no hay BPM y se dice por qué.
    - Q, R, S e inicio y fin del QRS: `clinical.qrs_delineation.delineate_qrs`
      (especificación validada en la Sub-Fase 2.5 del detector BBB) sobre cada
      pico TKEO. Si no hay onda Q o S que cumpla esa especificación, no se inventa.
      No se usa `segment_qrs_complex`: toma la Q como el mínimo de toda la ventana
      y casi siempre la pone encima de la S (QRS de 0 ms).
    - P y T: heurística de este módulo, no validada: la mayor desviación respecto
      a la línea isoeléctrica (R-120 a R-80 ms, como delineate_qrs) en ventanas
      fisiológicas antes y después del QRS. Si no supera el ruido, esa onda queda
      sin detectar. Los latidos cortados por el borde de la ventana no se delinean.
    - Patrón (solo con pattern=True): reglas de `classify_ecg_signal`, que no son
      un modelo de ML. Solo se entrega si su detector de picos encuentra los mismos
      latidos que el TKEO (±50 ms) y si sus propias mediciones de intervalos son
      fisiológicas; si no, queda «no disponible» con el motivo. Hoy casi nunca
      pasan (ver NOTAS_PARA_LUIS.md).

    Cada parte va por separado: si una falla en una ventana, las demás se entregan.
    """

    WAVES_LABEL = ('Q, R y S: delineate_qrs de BIOCORE (Sub-Fase 2.5) sobre los picos TKEO; '
                   'P y T: heurística de este módulo (no validada)')

    def __init__(self, fs: float, pattern: bool = False, waves: bool = True) -> None:
        from clinical.ecg_analyzer import ECGAnalyzer  # imports tardíos: solo dentro de BIOCORE

        self._analyzer_cls = ECGAnalyzer
        self._delineate = None
        if waves:
            from clinical.qrs_delineation import delineate_qrs

            self._delineate = delineate_qrs
        self._classify = None
        if pattern:
            from domain.physiology.ml.ecg_classification import classify_ecg_signal

            self._classify = classify_ecg_signal
        self.fs = float(fs)

    def __call__(self, window: ECGWindow) -> Dict[str, Any]:
        signal = np.asarray(window.ecg_mv, dtype=float)
        analyzer = self._analyzer_cls(fs=self.fs)
        out: Dict[str, Any] = {'notes': [], 'labels': {}}
        peaks = np.asarray(analyzer.detect_r_peaks_tkeo(signal), dtype=int)
        if len(peaks) >= 2:
            out['bpm'] = float(60.0 * self.fs / np.mean(np.diff(peaks)))
            out['labels']['bpm'] = 'Detector TKEO de BIOCORE (ECG Lab)'
        else:
            out['bpm'] = None
            out['notes'].append(f'BPM no disponible: el detector TKEO encontró {len(peaks)} pico(s) R en '
                                f'{window.duration_s:.0f} s y se necesitan al menos 2.')
        if self._delineate is not None:
            try:
                out['waves'] = self._waves(signal, peaks) or None
                out['labels']['waves'] = self.WAVES_LABEL
                if out['waves'] is None:
                    out['notes'].append('Ondas no disponibles: no hay ningún latido completo dentro de la ventana.')
            except Exception as exc:
                out['waves'] = None
                out['notes'].append(f'Ondas no disponibles: el delineador falló en esta ventana '
                                    f'({type(exc).__name__}: {exc}).')
        if self._classify is not None:
            prediction, note = self._pattern(analyzer, signal, peaks)
            out['prediction'] = prediction
            if note:
                out['notes'].append(note)
            else:
                out['labels']['prediction'] = 'Reglas de ECGAnalyzer (no es un modelo de ML)'
        return out

    # ---------------------------------------------------------------- ondas
    def _ms(self, milliseconds: float) -> int:
        return int(round(milliseconds * self.fs / 1000.0))

    def _waves(self, signal: np.ndarray, peaks: np.ndarray) -> Dict[str, Any]:
        n, ms = signal.size, self._ms
        beats: Dict[str, Any] = {}
        for i, r_tkeo in enumerate(int(p) for p in peaks):
            if r_tkeo - ms(150) < 0 or r_tkeo + ms(150) >= n:
                continue                                        # latido cortado por el borde
            d = self._delineate(signal, r_tkeo, self.fs)
            found = {p['type']: int(p['idx']) for p in sorted(d.peaks, key=lambda p: -abs(p['idx'] - r_tkeo))}
            r = found.get('R', r_tkeo)
            if abs(r - r_tkeo) > ms(40):
                r = r_tkeo
            points = {'R': r}
            for kind, side in (('Q', -1), ('S', 1)):            # el sub-pico de ese lado más cercano a R
                near = [int(p['idx']) for p in d.peaks if p['type'] == kind and (p['idx'] - r) * side > 0]
                if near:
                    points[kind] = min(near, key=lambda idx: abs(idx - r))
            iso = signal[r - ms(120):r - ms(80)]
            baseline, noise = float(np.mean(iso)), float(np.std(iso))
            prev_r = int(peaks[i - 1]) if i > 0 else None
            next_r = int(peaks[i + 1]) if i + 1 < len(peaks) else None
            # P: antes del QRS, sin meterse en la segunda mitad del latido anterior.
            p_from = r - ms(300) if prev_r is None else max(r - ms(300), (prev_r + r) // 2)
            p_to = int(d.onset_idx) - ms(10)
            if p_from >= 0 and p_to - p_from >= ms(40):
                k = p_from + int(np.argmax(signal[p_from:p_to] - baseline))
                if signal[k] - baseline >= max(0.03, 2.0 * noise):
                    points['P'] = k
            # T: después del ST y antes de que se acerque el siguiente latido.
            t_from = int(d.offset_idx) + ms(60)
            t_to = r + ms(450) if next_r is None else min(r + ms(450), next_r - ms(200))
            if t_to < n and t_to - t_from >= ms(100):
                k = t_from + int(np.argmax(np.abs(signal[t_from:t_to] - baseline)))
                if abs(signal[k] - baseline) >= max(0.05, 2.0 * noise):
                    points['T'] = k
            beat: Dict[str, Any] = {kind: {'index': idx, 'amplitude': float(signal[idx])}
                                    for kind, idx in sorted(points.items(), key=lambda kv: kv[1])}
            beat['QRS'] = {'onset': int(d.onset_idx), 'offset': int(d.offset_idx),
                           'duration_ms': float(d.qrs_duration_ms)}
            beats[f'beat_{i}'] = beat
        return beats

    # ---------------------------------------------------------------- patrón
    def _pattern(self, analyzer: Any, signal: np.ndarray, peaks: np.ndarray) -> Tuple[Any, str]:
        own = np.asarray(analyzer.detect_r_peaks(signal), dtype=int)
        tol = self._ms(50)
        if len(own) != len(peaks) or (len(own) > 0 and not bool(np.all(np.abs(own - peaks) <= tol))):
            return None, (f'Patrón no disponible: las reglas de BIOCORE usan otro detector de picos, que encontró '
                          f'{len(own)} latido(s) donde el TKEO encontró {len(peaks)}; con esa diferencia el patrón '
                          'no es confiable en esta ventana.')
        try:
            iv = analyzer.measure_intervals(signal)
            qrs, pr, qt = (float(iv.get(k, 0.0)) for k in ('QRS_duration_ms', 'PR_interval_ms', 'QT_interval_ms'))
            if not (40 <= qrs <= 200 and 80 <= pr <= 300 and 200 <= qt <= 600):
                return None, (f'Patrón no disponible: las reglas midieron QRS={qrs:.0f} ms, PR={pr:.0f} ms y '
                              f'QT={qt:.0f} ms en esta ventana; no son valores fisiológicos (falló su medición de '
                              'intervalos), así que el patrón no se puede afirmar.')
            r = self._classify(signal, self.fs)
        except Exception as exc:
            return None, (f'Patrón no disponible: las reglas de BIOCORE fallaron en esta ventana '
                          f'({type(exc).__name__}: {exc}).')
        return {'patron': r.pattern, 'razonamiento': list(r.reasoning)}, ''


class CompositeAnalyzer:
    """Corre varios analizadores en orden; los campos de los últimos mandan."""

    def __init__(self, analyzers: Sequence[Analyzer]) -> None:
        self.analyzers = list(analyzers)

    def __call__(self, window: ECGWindow) -> Dict[str, Any]:
        merged: Dict[str, Any] = {'notes': [], 'labels': {}}
        for analyzer in self.analyzers:
            part = dict(analyzer(window) or {})
            merged['notes'].extend(part.pop('notes', []) or [])
            merged['labels'].update(part.pop('labels', {}) or {})
            for key, value in part.items():
                if value is not None or key not in merged:
                    merged[key] = value
        return merged


class InferenceBridge:
    """Hilo de inferencia con «solo la ventana más nueva»."""

    def __init__(self, analyzer: Optional[Analyzer], on_result: Callable[[WindowResult], None]) -> None:
        self.analyzer = analyzer
        self.on_result = on_result
        self.dropped = 0
        self.processed = 0
        self._slot: 'queue.Queue[ECGWindow]' = queue.Queue(maxsize=1)
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name='ecg-inferencia', daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout)
        self._thread = None

    def submit(self, window: ECGWindow) -> None:
        """No bloquea: si hay una ventana esperando, la reemplaza."""
        while True:
            try:
                self._slot.put_nowait(window)
                return
            except queue.Full:
                try:
                    self._slot.get_nowait()
                    self.dropped += 1
                except queue.Empty:
                    pass

    def clear(self) -> None:
        try:
            while True:
                self._slot.get_nowait()
        except queue.Empty:
            pass

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                window = self._slot.get(timeout=0.2)
            except queue.Empty:
                continue
            result = self.analyze(window)
            self.processed += 1
            try:
                self.on_result(result)
            except Exception:
                pass  # un error en la interfaz no debe tumbar el hilo

    def analyze(self, window: ECGWindow) -> WindowResult:
        result = WindowResult(window=window)
        if not window.valid or self.analyzer is None:
            if self.analyzer is None and window.valid:
                result.notes.append('No hay analizador configurado: solo se entrega la señal limpia.')
            return result
        t0 = time.perf_counter()
        try:
            out = dict(self.analyzer(window) or {})
        except Exception as exc:
            result.error = f'El análisis falló: {type(exc).__name__}: {exc}'
            result.latency_ms = (time.perf_counter() - t0) * 1000.0
            return result
        result.latency_ms = (time.perf_counter() - t0) * 1000.0
        result.prediction = _first(out, ('prediction',) + _PREDICTION_KEYS)
        bpm = out.get('bpm')
        try:
            result.bpm = float(bpm) if bpm is not None and np.isfinite(float(bpm)) else None
        except (TypeError, ValueError):
            result.notes.append(f'BPM descartado: el analizador devolvió {bpm!r}, que no es un número.')
        result.waves = _first(out, _WAVE_KEYS)
        result.notes.extend(_first(out, ('notes', 'notas')) or [])
        result.labels.update(_first(out, ('labels', 'etiquetas')) or {})
        return result


def _first(data: Mapping, keys: Sequence[str]) -> Any:
    """Primer valor presente entre varias claves (acepta nombres en español o inglés)."""
    for key in keys:
        if key in data:
            return data[key]
    return None
