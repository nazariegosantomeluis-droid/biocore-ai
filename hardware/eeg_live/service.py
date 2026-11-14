"""Servicio de EEG en vivo: un hilo abre la fuente, lee, guarda los últimos segundos y dice en qué estado está.

    CONECTANDO ──(llegan muestras)──> TRANSMITIENDO ──(3 s sin muestras)──> SIN DATOS
        ^  │ no se pudo abrir: SIN CONEXIÓN, con el motivo        │ vuelven las muestras: TRANSMITIENDO
        │  v                                                      v 10 s sin muestras: se cierra la sesión
        └── reintento cada 5 s <─────────────────────────────── SIN CONEXIÓN

La procedencia que entrega `snapshot()` es la del dispositivo (SENSOR_REAL, SIMULACION o NO_VERIFICABLE) solo
mientras el estado es TRANSMITIENDO; en cualquier otro estado es None, y el búfer de una sesión anterior no se
presenta como señal en vivo (la página no analiza sin TRANSMITIENDO). Cada sesión nueva empieza con el búfer
vacío: no se mezclan muestras de dos conexiones.

La interfaz lee con `snapshot()`, que es una copia segura entre hilos (Streamlit vuelve a dibujar la página
desde otro hilo).
"""

from __future__ import annotations

import atexit
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Deque, Dict, Optional, Tuple

import numpy as np

from .backends import Backend, BackendError, StreamDescription
from .devices import EegDevice


class LiveState(str, Enum):
    STOPPED = 'detenido'
    CONNECTING = 'conectando'
    STREAMING = 'transmitiendo'
    NO_DATA = 'sin datos'
    FAILED = 'sin conexión'


@dataclass
class LiveConfig:
    buffer_seconds: float = 120.0      # lo más que analiza la página (el control «Duración» llega a 120 s)
    poll_s: float = 0.05
    data_timeout_s: float = 3.0        # sin muestras por más de esto: SIN DATOS
    reconnect_after_s: float = 10.0    # sin muestras por más de esto: se cierra la sesión y se reintenta
    retry_s: float = 5.0               # espera entre intentos de conexión
    rate_window_s: float = 5.0         # ventana para estimar la frecuencia con que llegan las muestras


@dataclass(frozen=True)
class StatusEvent:
    state: LiveState
    message: str
    time: float = field(default_factory=time.time)


class _Ring:
    """Últimas `capacity` muestras de cada canal, en un arreglo fijo."""

    def __init__(self, n_channels: int, capacity: int) -> None:
        self.data = np.zeros((n_channels, max(1, capacity)))
        self.total = 0

    @property
    def capacity(self) -> int:
        return self.data.shape[1]

    def extend(self, chunk: np.ndarray) -> None:
        n = chunk.shape[1]
        if n >= self.capacity:            # solo cabe lo último, cada muestra en su lugar circular
            idx = np.arange(self.total + n - self.capacity, self.total + n) % self.capacity
            self.data[:, idx] = chunk[:, -self.capacity:]
            self.total += n
            return
        start = self.total % self.capacity
        first = min(n, self.capacity - start)
        self.data[:, start:start + first] = chunk[:, :first]
        if first < n:
            self.data[:, :n - first] = chunk[:, first:]
        self.total += n

    def last(self, n: int) -> np.ndarray:
        n = max(0, min(n, self.total, self.capacity))
        idx = np.arange(self.total - n, self.total) % self.capacity
        return self.data[:, idx].copy()


class EegLiveService:
    """Lee una fuente de EEG en segundo plano. `key` identifica el dispositivo y sus parámetros."""

    def __init__(self, device: EegDevice, backend_factory: Callable[[], Backend],
                 config: Optional[LiveConfig] = None, key: str = '') -> None:
        self.device = device
        self.key = key or device.key
        self.config = config or LiveConfig()
        self._factory = backend_factory
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._atexit = False
        self._state = LiveState.STOPPED
        self._message = 'Detenido.'
        self._desc: Optional[StreamDescription] = None
        self._ring: Optional[_Ring] = None
        self._arrivals: Deque[Tuple[float, int]] = deque()
        self._stream_started: Optional[float] = None
        self._last_data: Optional[float] = None
        self._events: Deque[StatusEvent] = deque(maxlen=30)
        self._warnings: Deque[str] = deque(maxlen=10)
        self._connections = 0

    # ------------------------------------------------------------ ciclo de vida
    def start(self) -> 'EegLiveService':
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                if not self._stop.is_set():
                    return self
                self._warn('Todavía se está cerrando la conexión anterior; vuelve a intentar en unos segundos.')
                return self
            self._warnings.clear()
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, name=f'eeg-{self.device.key}', daemon=True)
            self._thread.start()
            if not self._atexit:
                atexit.register(self.stop)      # al cerrar el programa se suelta el dispositivo
                self._atexit = True
        return self

    def stop(self, timeout: float = 3.0) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout)
        self._set_state(LiveState.STOPPED, 'Detenido.')

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive() and not self._stop.is_set()

    @property
    def state(self) -> LiveState:
        return self._state

    def wait_for(self, state: LiveState, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._state == state:
                return True
            time.sleep(0.02)
        return self._state == state

    # ------------------------------------------------------------ lectura para la interfaz
    def snapshot(self, seconds: Optional[float] = None) -> Dict[str, Any]:
        with self._lock:
            desc, ring = self._desc, self._ring
            fs = desc.fs if desc else None
            available = 0 if ring is None else min(ring.total, ring.capacity)
            n = available if (seconds is None or fs is None) else min(available, int(round(seconds * fs)))
            data = ring.last(n) if ring is not None else np.zeros((0, 0))
            streaming = self._state == LiveState.STREAMING
            age = None if self._last_data is None else time.monotonic() - self._last_data
            return {
                'state': self._state.value,
                'message': self._message,
                'device_key': self.device.key,
                'device_name': self.device.name,
                'key': self.key,
                'detail': desc.detail if desc else '',
                'provenance': desc.provenance if (desc and streaming) else None,
                'channels': desc.channels if desc else (),
                'fs': fs,
                'unit_note': desc.unit_note if desc else '',
                'data': data,
                'seconds_available': (available / fs) if fs else 0.0,
                'total_samples': 0 if ring is None else ring.total,
                'effective_fs': self._effective_fs(),
                'last_data_age_s': age,
                'connections': self._connections,
                'warnings': list(self._warnings),
                'events': list(self._events)[-10:],
            }

    def _effective_fs(self) -> Optional[float]:
        cfg = self.config
        if self._stream_started is None or not self._arrivals:
            return None
        now = time.monotonic()
        if now - self._stream_started < cfg.rate_window_s:
            return None
        recent = sum(n for t, n in self._arrivals if now - t <= cfg.rate_window_s)
        return recent / cfg.rate_window_s

    # ------------------------------------------------------------ hilo
    def _run(self) -> None:
        while not self._stop.is_set():
            self._set_state(LiveState.CONNECTING, f'Abriendo {self.device.name}…')
            try:
                backend = self._factory()
                desc = backend.open()
            except BackendError as exc:
                self._fail(str(exc))
                continue
            except Exception as exc:          # nunca morir en silencio
                self._fail(f'Error inesperado al abrir {self.device.name} ({type(exc).__name__}: {exc}).')
                continue
            if self._stop.is_set():
                self._close(backend)
                break
            self._begin(desc)
            reason = 'Detenido.'
            try:
                reason = self._stream(backend, desc)
            finally:
                self._close(backend)
            if not self._stop.is_set():
                self._fail(reason)
        self._stream_started = None

    def _close(self, backend: Backend) -> None:
        try:
            backend.close()
        except Exception:
            pass

    def _begin(self, desc: StreamDescription) -> None:
        with self._lock:
            self._desc = desc
            self._ring = _Ring(len(desc.channels), int(round(self.config.buffer_seconds * desc.fs)))
            self._arrivals.clear()
            self._stream_started = None
            self._last_data = None
            self._connections += 1
        self._set_state(LiveState.CONNECTING, f'Sesión abierta con {desc.detail}; esperando las primeras muestras…')

    def _stream(self, backend: Backend, desc: StreamDescription) -> str:
        cfg = self.config
        last = time.monotonic()
        while not self._stop.is_set():
            try:
                chunk = np.asarray(backend.read(), dtype=float)
            except Exception as exc:
                return f'Se perdió la conexión con {desc.detail} ({exc}).'
            now = time.monotonic()
            if chunk.ndim == 2 and chunk.shape[1] > 0:
                if chunk.shape[0] != len(desc.channels):
                    return (f'{desc.detail} mandó {chunk.shape[0]} canales y se esperaban {len(desc.channels)}; '
                            'se cierra la sesión.')
                with self._lock:
                    self._ring.extend(chunk)
                    self._arrivals.append((now, chunk.shape[1]))
                    while self._arrivals and now - self._arrivals[0][0] > cfg.rate_window_s:
                        self._arrivals.popleft()
                    if self._stream_started is None:
                        self._stream_started = now
                    self._last_data = now
                last = now
                if self._state != LiveState.STREAMING:
                    self._set_state(LiveState.STREAMING, f'{desc.detail}: llegan muestras.')
            else:
                idle = now - last
                if idle > cfg.reconnect_after_s:
                    return f'{desc.detail} no mandó datos en {idle:.0f} s; se cerró la sesión.'
                if idle > cfg.data_timeout_s and self._state in (LiveState.STREAMING, LiveState.NO_DATA):
                    self._set_state(LiveState.NO_DATA, f'{desc.detail} no manda datos desde hace {idle:.0f} s. '
                                                       'Revisa que esté encendido, cerca y conectado.')
            self._stop.wait(cfg.poll_s)
        return 'Detenido.'

    def _fail(self, reason: str) -> None:
        if self._stop.is_set():           # ya lo detuvieron: el estado se queda en DETENIDO
            return
        self._warn(reason)
        self._set_state(LiveState.FAILED, f'{reason} Se reintenta en {self.config.retry_s:.0f} s.')
        self._stop.wait(self.config.retry_s)

    # ------------------------------------------------------------ estado
    def _set_state(self, state: LiveState, message: str) -> None:
        with self._lock:
            if self._stop.is_set() and state != LiveState.STOPPED:
                return                    # el hilo terminando no pisa el DETENIDO de stop()
            changed = state != self._state
            self._state, self._message = state, message
            if changed:
                self._events.append(StatusEvent(state, message))

    def _warn(self, text: str) -> None:
        with self._lock:
            if not self._warnings or self._warnings[-1] != text:
                self._warnings.append(text)
