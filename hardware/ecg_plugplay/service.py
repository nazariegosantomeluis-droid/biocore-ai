"""Servicio Plug & Play de adquisición de ECG.

Un hilo de adquisición hace todo el ciclo, sin bloquear la interfaz:

    BUSCANDO ──(puerto USB nuevo)──> VERIFICANDO ──(ECG:HELLO o tramas ECG:)──> CONECTADO
        ^                                │ no es una placa de ECG: se anota el motivo
        │                                v y se reintenta más tarde
        └── DESCONECTADO <──(cable fuera, o 2 s sin datos)── CONECTADO

1. Búsqueda (hardware listener): cada segundo revisa los puertos. Solo sondea
   puertos USB (no Bluetooth), primero los chips conocidos por VID/PID.
2. Verificación (handshake): abre el puerto sin reiniciar la placa, manda
   'ECG?' y espera 'ECG:HELLO' o tramas 'ECG:D'. Si no llegan, dice por qué
   (p. ej. MicroPython esperando en '>>>') y no lo vuelve a abrir en un rato.
3. Adquisición: limpia cada bloque (preprocessing.SamplePipeline), lo acumula
   en el buffer circular y, cada `hop` muestras, arma una ventana de
   `window_size`, la revisa y la manda al puente de inferencia (otro hilo).
4. Desconexión (hot-unplug): si el puerto falla o pasan `data_timeout_s` sin
   tramas válidas, cierra el puerto, limpia buffers y resultados, avisa y
   vuelve a buscar.

La interfaz se entera por dos vías (usa la que le acomode a tu framework):

- Callbacks: on_state(StatusEvent) y on_signal(SignalChunk) llegan desde el
  hilo de adquisición; on_result(WindowResult) desde el hilo de inferencia;
  on_warning(str) desde cualquiera. No toques widgets dentro de un callback:
  en Qt emite una señal, en FastAPI mete el dato en una cola.
- snapshot(): copia del estado completo, segura entre hilos. Es lo que usa
  Streamlit, que vuelve a dibujar la página cada medio segundo.
"""

from __future__ import annotations

import atexit
import threading
import time
from collections import Counter, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple

import numpy as np

from .config import AcquisitionConfig
from .inference import Analyzer, ECGWindow, InferenceBridge, WindowResult
from .ports import PortError, PortInfo, candidate_ports, system_ports
from .preprocessing import (FLAG_INTERPOLATED, FLAG_LEADOFF, FLAG_MISSING, FLAG_SATURATED, AdcParams,
                            SamplePipeline, StreamingFilter, assess_window, normalize_for_model)
from .protocol import QUERY, DataBlock, DeviceMessage, Hello, LegacySample, LineReader, Other, parse_line
from .ring_buffer import SlidingWindowBuffer
from .transport import SerialTransport, Transport, TransportClosed


class ConnectionState(str, Enum):
    STOPPED = 'detenido'
    SEARCHING = 'buscando'
    PROBING = 'verificando'
    CONNECTED = 'conectado'
    DISCONNECTED = 'desconectado'


@dataclass(frozen=True)
class StatusEvent:
    """Cambio de estado de la conexión, con un mensaje listo para mostrar."""

    state: ConnectionState
    message: str
    port: Optional[str] = None
    provenance: Optional[str] = None
    device: Dict[str, str] = field(default_factory=dict)
    time: float = field(default_factory=time.time)


@dataclass(frozen=True)
class SignalChunk:
    """Muestras recién limpiadas, para graficar en vivo."""

    seq: np.ndarray
    mv: np.ndarray
    flags: np.ndarray
    fs: float
    provenance: str


@dataclass
class _Identity:
    kind: str                 # 'handshake', 'sin_handshake' o 'legado'
    hello: Optional[Hello]
    note: str = ''


class ECGAcquisitionService:
    """Detecta la placa, adquiere, limpia y entrega ventanas al analizador."""

    def __init__(
        self,
        config: Optional[AcquisitionConfig] = None,
        analyzer: Optional[Analyzer] = None,
        *,
        on_state: Optional[Callable[[StatusEvent], None]] = None,
        on_signal: Optional[Callable[[SignalChunk], None]] = None,
        on_result: Optional[Callable[[WindowResult], None]] = None,
        on_warning: Optional[Callable[[str], None]] = None,
        simulator: Any = None,
        list_ports_fn: Optional[Callable[[], List[PortInfo]]] = None,
        transport_factory: Optional[Callable[[PortInfo], Transport]] = None,
    ) -> None:
        self.config = config or AcquisitionConfig()
        self.config.check()
        self.analyzer = analyzer
        self.on_state, self.on_signal, self.on_result, self.on_warning = on_state, on_signal, on_result, on_warning
        self._simulator = simulator
        self._list_ports = list_ports_fn or system_ports
        self._transport_factory = transport_factory or self._default_transport

        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._bridge = InferenceBridge(analyzer, self._handle_result)
        self._atexit = False

        self._state = ConnectionState.STOPPED
        self._message = 'Detenido.'
        self._port: Optional[str] = None
        self._provenance: Optional[str] = None
        self._device: Dict[str, str] = {}
        self._events: Deque[StatusEvent] = deque(maxlen=50)
        self._warnings: Deque[str] = deque(maxlen=10)
        self._warned: Dict[Tuple[str, str], str] = {}
        self._retry_after: Dict[str, float] = {}
        self._fails: Counter = Counter()
        self._connection = 0
        self._window_index = 0
        self._last_result: Optional[WindowResult] = None
        self._counters = {'ventanas': 0, 'validas': 0, 'descartadas': 0, 'conexiones': 0}
        self._stats: Dict[str, int] = {}
        self._buffer_fill = 0
        self._last_data_time: Optional[float] = None
        cap = max(1, int(round(self.config.display_seconds * self.config.fs)))
        self._disp_mv = np.full(cap, np.nan)
        self._disp_flags = np.zeros(cap, dtype=np.uint8)
        self._disp_total = 0

    # ================================================================ ciclo de vida
    def start(self) -> 'ECGAcquisitionService':
        """Arranca la búsqueda en segundo plano. Se puede llamar varias veces."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return self
            # Cada arranque empieza de cero: los contadores y los avisos de la sesión anterior
            # (p. ej. «COM3 está ocupado») ya no describen lo que pasa ahora.
            self._counters = {key: 0 for key in self._counters}
            self._stats = {}
            self._warnings.clear()
            self._warned.clear()
            self._retry_after.clear()
            self._fails.clear()
            self._bridge.dropped = 0
            self._stop.clear()
            self._bridge.start()
            self._thread = threading.Thread(target=self._run, name='ecg-adquisicion', daemon=True)
            self._thread.start()
            if not self._atexit:
                atexit.register(self.stop)   # al cerrar el programa, el puerto se suelta
                self._atexit = True
        return self

    def stop(self, timeout: float = 3.0) -> None:
        """Detiene todo y cierra el puerto."""
        self._stop.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout)
        self._thread = None
        self._bridge.stop()
        self._set_state(ConnectionState.STOPPED, 'Detenido.')

    def __enter__(self) -> 'ECGAcquisitionService':
        return self.start()

    def __exit__(self, *exc: Any) -> None:
        self.stop()

    @property
    def state(self) -> ConnectionState:
        return self._state

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def wait_for(self, state: ConnectionState, timeout: float) -> bool:
        """Espera (bloqueando) a que el servicio llegue a `state`. Útil en scripts y pruebas."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._state == state:
                return True
            time.sleep(0.02)
        return self._state == state

    # ================================================================ lectura para la UI
    def snapshot(self) -> Dict[str, Any]:
        """Copia del estado actual (segura entre hilos)."""
        with self._lock:
            cap = self._disp_mv.size
            n = min(self._disp_total, cap)
            idx = np.arange(self._disp_total - n, self._disp_total) % cap
            fs = self.config.fs
            age = None if self._last_data_time is None else time.time() - self._last_data_time
            return {
                'state': self._state.value,
                'message': self._message,
                'port': self._port,
                'provenance': self._provenance,
                'device': dict(self._device),
                'fs': fs,
                'signal_mv': self._disp_mv[idx].copy(),
                'signal_flags': self._disp_flags[idx].copy(),
                'signal_t': (np.arange(n) - (n - 1)) / fs,
                'buffer_fill': (self._buffer_fill, self.config.window_size),
                'last_result': self._last_result,
                'counters': dict(self._counters, descartadas_por_lentitud=self._bridge.dropped),
                'stats': dict(self._stats),
                'last_data_age_s': age,
                'warnings': list(self._warnings),
                'events': list(self._events)[-10:],
            }

    # ================================================================ hilo principal
    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self._set_state(ConnectionState.SEARCHING, 'Buscando un dispositivo de ECG… conecta la placa por USB.')
                found = self._find_device()
                if found is None:
                    self._stop.wait(self.config.scan_interval_s)
                    continue
                transport, ident, port = found
                reason = 'Servicio detenido.'
                try:
                    reason = self._acquire(transport, ident)
                finally:
                    self._teardown(transport, port, reason)
            except Exception as exc:   # nunca morir en silencio: avisar y volver a buscar
                self._warn(f'Error inesperado en la adquisición ({type(exc).__name__}: {exc}); se reinicia la búsqueda.')
                self._stop.wait(1.0)

    def _default_transport(self, port: PortInfo) -> Transport:
        if self._simulator is not None:
            from .simulator import SimulatedTransport

            return SimulatedTransport(self._simulator)
        return SerialTransport(port, self.config)

    # ---------------------------------------------------------------- búsqueda
    def _candidates(self) -> List[PortInfo]:
        if self._simulator is not None:
            from .simulator import SIM_PORT

            return [SIM_PORT] if self._simulator.plugged else []
        try:
            ports = self._list_ports()
        except Exception as exc:
            self._warn_once('sistema', 'listar', f'No se pudieron listar los puertos: {exc}')
            return []
        present = {p.device for p in ports}
        for device in list(self._retry_after):
            if device not in present and device != self.config.port:
                # Se desconectó: al volver a aparecer se prueba de inmediato.
                self._retry_after.pop(device, None)
                self._fails.pop(device, None)
                for key in [k for k in self._warned if k[0] == device]:
                    self._warned.pop(key, None)
        return candidate_ports(ports, self.config)

    def _find_device(self) -> Optional[Tuple[Transport, _Identity, PortInfo]]:
        cfg = self.config
        for port in self._candidates():
            if self._stop.is_set():
                return None
            if self._retry_after.get(port.device, 0.0) > time.monotonic():
                continue
            self._set_state(ConnectionState.PROBING, f'Verificando {port.device} · {port.label}…', port=port.device)
            try:
                transport = self._transport_factory(port)
            except PortError as err:
                wait = {'ocupado': cfg.busy_retry_s, 'no_existe': cfg.scan_interval_s}.get(err.kind, cfg.not_ecg_retry_s)
                self._retry_after[port.device] = time.monotonic() + wait
                self._warn_once(port.device, err.kind, err.message)
                continue
            ident, diagnosis = self._probe(transport)
            if ident is not None:
                self._fails.pop(port.device, None)
                for key in [k for k in self._warned if k[0] == port.device]:
                    self._warned.pop(key, None)
                return transport, ident, port
            try:
                transport.close()
            except Exception:
                pass
            self._fails[port.device] += 1
            backoff = min(6, 2 ** (self._fails[port.device] - 1))   # 10, 20, 40, 60 s...
            self._retry_after[port.device] = time.monotonic() + cfg.not_ecg_retry_s * backoff
            self._warn_once(port.device, 'no_ecg', diagnosis)
        return None

    def _probe(self, transport: Transport) -> Tuple[Optional[_Identity], str]:
        """Pregunta 'ECG?' y escucha: ¿es una placa de ECG?"""
        cfg = self.config
        reader = LineReader()
        deadline = time.monotonic() + cfg.probe_timeout_s
        next_query = 0.0
        seen: Counter = Counter()
        data_frames = legacy = 0
        woke = extended = False
        while time.monotonic() < deadline and not self._stop.is_set():
            try:
                if time.monotonic() >= next_query:
                    transport.write(QUERY)
                    next_query = time.monotonic() + 1.0
                data = transport.read(0.1)
            except TransportClosed as exc:
                return None, f'{transport.name} se cerró mientras se verificaba ({exc}).'
            for line in reader.feed(data):
                frame = parse_line(line, cfg.accept_legacy)
                if isinstance(frame, Hello):
                    return _Identity('handshake', frame), ''
                if isinstance(frame, DataBlock):
                    data_frames += 1
                    if data_frames >= 3:
                        return _Identity('sin_handshake', None, 'sin ECG:HELLO, se usa la configuración'), ''
                elif isinstance(frame, LegacySample):
                    legacy += 1
                    if legacy >= 25:
                        return _Identity('legado', None, 'formato legado ts,valor'), ''
                elif isinstance(frame, Other):
                    seen[frame.kind] += 1
                    if frame.kind in ('arranque', 'banner') and not extended:
                        deadline += 3.0          # la placa está arrancando: se le da tiempo
                        extended = True
                    if frame.kind == 'repl' and cfg.wake_micropython and not woke:
                        try:
                            transport.write(b'\r\x04')   # Ctrl-D: reinicio suave, MicroPython corre main.py
                        except TransportClosed:
                            pass
                        woke = True
                        deadline = time.monotonic() + 4.0
        name = transport.name
        if seen['traceback']:
            return None, (f'{name}: el programa de la placa falló al arrancar (Traceback). '
                          'Ábrela en Thonny para ver el error.')
        if seen['repl']:
            return None, (f'{name}: hay MicroPython esperando órdenes (>>>), pero el firmware de ECG no está '
                          'corriendo. Cierra Thonny y presiona EN, o guarda main.py en la placa.')
        if seen['numerica']:
            return None, (f'{name} manda números sin el prefijo ECG: (¿formato viejo ts,valor?). Actívalo con '
                          'accept_legacy=True si no hay otra placa conectada.')
        return None, (f'{name} no respondió como placa de ECG en {cfg.probe_timeout_s:g} s '
                      '(¿es otra placa o el firmware no manda tramas ECG:?).')

    # ---------------------------------------------------------------- adquisición
    def _acquire(self, transport: Transport, ident: _Identity) -> str:
        cfg = self.config
        hello = ident.hello
        fs_device = (hello.fs if hello and hello.fs else cfg.fs)
        adc = AdcParams(
            bits=(hello.bits if hello and hello.bits else cfg.adc_bits),
            vref=(hello.vref if hello and hello.vref else cfg.adc_vref),
            gain=(hello.gain if hello and hello.gain else cfg.gain),
        )
        prefiltered = bool(hello and hello.prefiltered)
        filt = None if prefiltered else StreamingFilter(cfg.fs, cfg.bandpass_hz, cfg.bandpass_order,
                                                        cfg.notch_hz, cfg.notch_q)
        pipeline = SamplePipeline(cfg.fs, adc, cfg.heuristics, filt, max_fill=cfg.window_size)
        buffer = SlidingWindowBuffer(cfg.window_size, cfg.hop,
                                     {'seq': np.int64, 'raw': np.float64, 'mv': np.float64, 'flags': np.uint8})
        reader = LineReader()
        fs_problem = None
        if abs(fs_device - cfg.fs) > 1e-6:
            fs_problem = (f'la placa muestrea a {fs_device:g} Hz y el modelo espera {cfg.fs:g} Hz; '
                          'ajusta FS en el firmware o fs en la configuración')
        source = f'{transport.name} · {transport.label}' + (f' · fw {hello.firmware}' if hello else '')
        # Procedencia: un puerto USB que respondió es SENSOR_REAL, salvo que la propia placa se declare
        # simulador (sim=1 en el HELLO, como el simulador por pty). El firmware real nunca lo manda.
        provenance = 'SIMULACION' if (hello and hello.params.get('sim') == '1') else transport.provenance

        with self._lock:
            self._connection += 1
            self._window_index = 0
            self._port = transport.name
            self._provenance = provenance
            self._device = dict(hello.params) if hello else {}
            self._last_result = None
            self._buffer_fill = 0
            self._stats = {}
            self._clear_display()
            self._counters['conexiones'] += 1
            connection = self._connection

        message = f'Conectado: {transport.name} · {transport.label}'
        if hello:
            message += f' · firmware {hello.firmware}'
        message += f' · {fs_device:g} Hz'
        if ident.note:
            message += f' · {ident.note}'
        if provenance == 'SIMULACION':
            message += ' · SIMULACIÓN, no es un sensor'
        self._set_state(ConnectionState.CONNECTED, message, port=transport.name)
        if fs_problem:
            self._warn(f'{transport.name}: {fs_problem}. Las ventanas se descartan hasta que coincidan.')
        if prefiltered:
            self._warn(f'{transport.name}: la placa ya filtra la señal (filt=1); aquí no se vuelve a filtrar.')

        legacy = cfg.accept_legacy or ident.kind == 'legado'
        last_data = time.monotonic()
        while not self._stop.is_set():
            try:
                data = transport.read(0.05)
            except TransportClosed as exc:
                return f'Se desconectó el dispositivo ({exc}).'
            now = time.monotonic()
            for line in reader.feed(data):
                frame = parse_line(line, legacy)
                if isinstance(frame, DataBlock):
                    arrays = pipeline.push(frame.values, frame.seq, frame.leadoff)
                elif isinstance(frame, LegacySample):
                    arrays = pipeline.push((frame.value,), None, 0)
                elif isinstance(frame, DeviceMessage):
                    self._warn(f'{transport.name} dice: {frame.text}')
                    continue
                elif isinstance(frame, Other) and frame.kind == 'traceback':
                    self._warn_once(transport.name, 'traceback',
                                    f'{transport.name}: el programa de la placa falló (Traceback).')
                    continue
                else:
                    continue
                last_data = now
                self._on_samples(arrays, buffer, pipeline, provenance, source, fs_problem, connection)
            if now - last_data > cfg.data_timeout_s:
                return f'No llegan datos de {transport.name} desde hace {now - last_data:.1f} s.'
        return 'Servicio detenido.'

    def _on_samples(self, arrays: Dict[str, np.ndarray], buffer: SlidingWindowBuffer, pipeline: SamplePipeline,
                    provenance: str, source: str, fs_problem: Optional[str], connection: int) -> None:
        windows = buffer.extend(seq=arrays['seq'], raw=arrays['raw'], mv=arrays['mv'], flags=arrays['flags'])
        with self._lock:
            self._append_display(arrays['mv'], arrays['flags'])
            self._last_data_time = time.time()
            self._stats = dict(pipeline.stats)
            self._buffer_fill = buffer.filled
        if self.on_signal is not None:
            try:
                self.on_signal(SignalChunk(arrays['seq'], arrays['mv'], arrays['flags'], self.config.fs,
                                           provenance))
            except Exception:
                pass
        for w in windows:
            self._emit_window(w, provenance, source, fs_problem, connection)

    def _emit_window(self, w: Dict[str, np.ndarray], provenance: str, source: str,
                     fs_problem: Optional[str], connection: int) -> None:
        cfg = self.config
        quality = assess_window(w['mv'], w['flags'], cfg.heuristics)
        if fs_problem:
            quality.reasons.insert(0, fs_problem)
        model_input = None
        if quality.ok:
            try:
                model_input = normalize_for_model(w['mv'], cfg)
            except ValueError as exc:
                quality.reasons.append(str(exc))
        window = ECGWindow(
            index=self._window_index, fs=cfg.fs, start_seq=int(w['seq'][0]), ecg_mv=w['mv'], raw=w['raw'],
            flags=w['flags'], quality=quality, model_input=model_input, provenance=provenance,
            source=source, t_end=time.time(), connection=connection,
        )
        self._window_index += 1
        with self._lock:
            self._counters['ventanas'] += 1
            self._counters['validas' if window.valid else 'descartadas'] += 1
        self._bridge.submit(window)

    def _handle_result(self, result: WindowResult) -> None:
        """Llega desde el hilo de inferencia."""
        with self._lock:
            if result.window.connection != self._connection or self._state != ConnectionState.CONNECTED:
                return   # resultado de una conexión que ya se cerró: no se muestra
            self._last_result = result
        if self.on_result is not None:
            try:
                self.on_result(result)
            except Exception:
                pass

    def _teardown(self, transport: Transport, port: PortInfo, reason: str) -> None:
        try:
            transport.close()
        except Exception:
            pass
        self._bridge.clear()
        with self._lock:
            self._connection += 1          # los resultados que aún vengan en camino se ignoran
            self._last_result = None
            self._buffer_fill = 0
            self._provenance = None
            self._device = {}
            self._clear_display()
        if self._stop.is_set():
            self._set_state(ConnectionState.DISCONNECTED, f'{reason} Puerto cerrado.', port=port.device)
            return
        self._retry_after[port.device] = time.monotonic() + min(1.0, self.config.scan_interval_s)
        self._set_state(ConnectionState.DISCONNECTED, f'{reason} Puerto cerrado; se vuelve a buscar.', port=port.device)

    # ================================================================ utilidades
    def _set_state(self, state: ConnectionState, message: str, port: Optional[str] = None) -> None:
        with self._lock:
            if state == self._state and message == self._message:
                return
            self._state = state
            self._message = message
            if port is not None:
                self._port = port
            event = StatusEvent(state, message, port or self._port, self._provenance, dict(self._device))
            self._events.append(event)
        if self.on_state is not None:
            try:
                self.on_state(event)
            except Exception:
                pass

    def _warn(self, message: str) -> None:
        with self._lock:
            self._warnings.append(message)
        if self.on_warning is not None:
            try:
                self.on_warning(message)
            except Exception:
                pass

    def _warn_once(self, key: str, kind: str, message: str) -> None:
        """Avisa una vez por puerto y motivo (hasta que el puerto desaparezca o conecte)."""
        if self._warned.get((key, kind)) == message:
            return
        self._warned[(key, kind)] = message
        self._warn(message)

    def _append_display(self, mv: np.ndarray, flags: np.ndarray) -> None:
        cap = self._disp_mv.size
        n = mv.size
        if n >= cap:
            mv, flags = mv[-cap:], flags[-cap:]
            self._disp_total += n - cap
            n = cap
        start = self._disp_total % cap
        first = min(n, cap - start)
        self._disp_mv[start:start + first] = mv[:first]
        self._disp_flags[start:start + first] = flags[:first]
        if first < n:
            self._disp_mv[:n - first] = mv[first:]
            self._disp_flags[:n - first] = flags[first:]
        self._disp_total += n

    def _clear_display(self) -> None:
        self._disp_mv.fill(np.nan)
        self._disp_flags.fill(0)
        self._disp_total = 0


def latest_clean_segment(snapshot: Dict[str, Any], min_seconds: float = 4.0) -> Tuple[Optional[np.ndarray], str]:
    """El tramo más reciente de la señal en vivo que sirve para analizar como señal continua.

    Para pantallas que no aceptan NaN ni huecos (el ECG Lab de BIOCORE rechaza la
    señal entera si trae un solo NaN). Se queda con las últimas muestras sin
    electrodo suelto, pérdidas, saturación ni filtro estabilizándose; las 1 o 2
    muestras interpoladas sí cuentan como buenas.

    Recibe un snapshot() para que la señal y su procedencia salgan del mismo
    instante. Devuelve (señal en mV, '') o (None, motivo en español).
    """
    if snapshot['state'] != ConnectionState.CONNECTED.value:
        return None, snapshot['message']
    mv, flags, fs = snapshot['signal_mv'], snapshot['signal_flags'], snapshot['fs']
    bad = np.flatnonzero((flags & np.uint8(0xFF & ~FLAG_INTERPOLATED)) != 0)
    tail = mv[bad[-1] + 1:] if bad.size else mv
    if tail.size >= int(round(min_seconds * fs)) and np.isfinite(tail).all():
        return tail.astype(float), ''
    if bad.size and bad[-1] == mv.size - 1:          # el problema sigue ahora mismo
        last = int(flags[-1])
        if last & FLAG_LEADOFF:
            why = 'electrodo suelto (señal LO del AD8232); revisa que los tres electrodos estén pegados'
        elif last & FLAG_SATURATED:
            why = 'el ADC está saturado; revisa los electrodos y que la persona no se mueva'
        elif last & FLAG_MISSING:
            why = 'se están perdiendo muestras en la transmisión'
        else:
            why = 'el filtro se está estabilizando'
        return None, f'Sin señal limpia: {why}.'
    return None, f'Juntando señal limpia: {tail.size / fs:.1f} de {min_seconds:g} s.'
