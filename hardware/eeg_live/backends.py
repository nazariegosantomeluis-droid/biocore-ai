"""Cómo se abre cada fuente de EEG en vivo: BrainFlow, LSL o el simulador de práctica.

Las tres cumplen el mismo contrato, para que el servicio (`service.py`) no sepa con cuál habla:

- `open()` abre la sesión y devuelve un `StreamDescription` (canales, frecuencia, unidades, procedencia).
  Si no se puede, lanza `BackendError` con un mensaje que dice por qué y qué hacer.
- `read()` devuelve lo que llegó desde la última lectura, en µV, con forma (canales, muestras);
  (canales, 0) si no llegó nada. Nunca bloquea.
- `close()` suelta el dispositivo. No lanza.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from .devices import NO_VERIFICABLE, PARAM_LABELS, SIMULACION, EegDevice

BRAINFLOW_UNIT_NOTE = 'µV: BrainFlow devuelve µV en los canales de EEG siempre que puede (documentación de BrainFlow).'
LSL_OPEN_TIMEOUT_S = 3.0
LSL_MAX_BUFFER_S = 60


class BackendError(Exception):
    """No se pudo abrir o leer la fuente. El texto dice por qué y qué hacer."""


@dataclass(frozen=True)
class StreamDescription:
    channels: Tuple[str, ...]
    fs: float
    detail: str              # «OpenBCI Cyton en COM3», «LSL «X» desde host»…
    unit_note: str
    provenance: str


class Backend:
    def open(self) -> StreamDescription:          # pragma: no cover - contrato
        raise NotImplementedError

    def read(self) -> np.ndarray:                 # pragma: no cover - contrato
        raise NotImplementedError

    def close(self) -> None:                      # pragma: no cover - contrato
        pass


# ================================================================ BrainFlow
def explain_brainflow_error(exit_code: int, device: EegDevice, params: Mapping[str, str], raw: str = '') -> str:
    """Traduce el código de salida de BrainFlow a un motivo y una acción, según cómo se conecta el equipo."""
    port = params.get('serial_port', '')
    name = device.name
    if exit_code == 13:                       # INVALID_ARGUMENTS_ERROR
        faltan = ', '.join(PARAM_LABELS[p] for p in device.required) or 'algún parámetro'
        return f'Faltan datos para abrir {name}: {faltan}.'
    if exit_code in (1, 16):                  # PORT_ALREADY_OPEN_ERROR, ANOTHER_BOARD_IS_CREATED_ERROR
        return (f'{name} ya está abierto en otra sesión o por otro programa (OpenBCI GUI, por ejemplo). Ciérralo y '
                'vuelve a conectar.')
    if exit_code == 2:                        # UNABLE_TO_OPEN_PORT_ERROR
        if device.link == 'serial':
            return (f'No se pudo abrir el puerto {port or "(vacío)"}: revisa que sea el del dongle y que ningún otro '
                    'programa lo esté usando.')
        return (f'No se encontró {name}: revisa que esté encendido y cerca, y que el Bluetooth de la computadora esté '
                'activo.')
    if exit_code == 7:                        # BOARD_NOT_READY_ERROR
        if device.link == 'serial':
            return ('La placa no respondió: revisa que tenga batería, que su interruptor esté en PC y el del dongle en '
                    'GPIO 6.')
        return f'{name} no respondió: revisa que esté encendido y cargado.'
    if exit_code == 17 and device.key == 'unicorn':   # GENERAL_ERROR
        return ('No se pudo abrir el Unicorn: revisa que esté encendido y emparejado con el dongle que trae (no con el '
                'Bluetooth de la computadora). BrainFlow lo soporta en Windows y Ubuntu.')
    return f'BrainFlow no pudo abrir {name} (código {exit_code}{": " + raw if raw else ""}).'


class BrainFlowBackend(Backend):
    """Una sesión de BrainFlow con un tablero del catálogo."""

    def __init__(self, device: EegDevice, params: Optional[Mapping[str, str]] = None, shim: Any = None) -> None:
        if device.backend != 'brainflow' or not device.board:
            raise ValueError(f'{device.key} no es un tablero de BrainFlow.')
        self.device = device
        self.params: Dict[str, str] = {k: str(v).strip() for k, v in (params or {}).items() if str(v or '').strip()}
        self._shim = shim               # módulo falso en las pruebas
        self._board = None
        self._rows: List[int] = []

    def _modules(self):
        if self._shim is not None:
            return self._shim
        try:
            from brainflow import board_shim, exit_codes
        except Exception as exc:
            raise BackendError(f'BrainFlow no está disponible ({exc}). Instálalo con «pip install brainflow».') from exc
        return _BrainFlowModules(board_shim, exit_codes)

    def open(self) -> StreamDescription:
        missing = [p for p in self.device.required if not self.params.get(p)]
        if missing:
            raise BackendError(f'Falta {PARAM_LABELS[missing[0]]} para abrir {self.device.name}.')
        mods = self._modules()
        board_id = getattr(mods.BoardIds, self.device.board).value
        inputs = mods.BrainFlowInputParams()
        for key, value in self.params.items():
            setattr(inputs, key, value)
        try:
            mods.BoardShim.disable_board_logger()
        except Exception:
            pass
        board = mods.BoardShim(board_id, inputs)
        try:
            board.prepare_session()
            board.start_stream()
        except mods.BrainFlowError as exc:
            try:
                board.release_session()
            except Exception:
                pass
            raise BackendError(explain_brainflow_error(int(getattr(exc, 'exit_code', -1)), self.device, self.params,
                                                       str(exc))) from exc
        self._board = board
        self._rows = list(mods.BoardShim.get_eeg_channels(board_id))
        try:
            names = tuple(mods.BoardShim.get_eeg_names(board_id))
        except Exception:                 # la Ganglion no trae nombres
            names = ()
        if len(names) != len(self._rows):
            names = tuple(f'Canal {i}' for i in range(1, len(self._rows) + 1))
        fs = float(mods.BoardShim.get_sampling_rate(board_id))
        where = f' en {self.params["serial_port"]}' if self.params.get('serial_port') else ''
        return StreamDescription(names, fs, f'{self.device.name}{where}', BRAINFLOW_UNIT_NOTE, self.device.provenance)

    def read(self) -> np.ndarray:
        if self._board is None:
            raise BackendError('La sesión de BrainFlow no está abierta.')
        data = np.asarray(self._board.get_board_data(), dtype=float)
        if data.ndim != 2 or data.shape[1] == 0:
            return np.zeros((len(self._rows), 0))
        return data[self._rows]

    def close(self) -> None:
        board, self._board = self._board, None
        if board is None:
            return
        for step in ('stop_stream', 'release_session'):
            try:
                getattr(board, step)()
            except Exception:
                pass


@dataclass
class _BrainFlowModules:
    board_shim: Any
    exit_codes: Any

    @property
    def BoardShim(self):
        return self.board_shim.BoardShim

    @property
    def BoardIds(self):
        return self.board_shim.BoardIds

    @property
    def BrainFlowInputParams(self):
        return self.board_shim.BrainFlowInputParams

    @property
    def BrainFlowError(self):
        return self.exit_codes.BrainFlowError


# ================================================================ LSL
UNIT_SCALES = {
    'microvolts': 1.0, 'microvolt': 1.0, 'uv': 1.0, 'µv': 1.0, 'μv': 1.0,
    'millivolts': 1e3, 'millivolt': 1e3, 'mv': 1e3,
    'volts': 1e6, 'volt': 1e6, 'v': 1e6,
}


@dataclass(frozen=True)
class LslStreamChoice:
    """Un flujo LSL encontrado en la red, con lo necesario para volver a encontrarlo."""

    name: str
    type: str
    source_id: str
    hostname: str
    channel_count: int
    nominal_srate: float

    @property
    def label(self) -> str:
        rate = f'{self.nominal_srate:g} Hz' if self.nominal_srate > 0 else 'irregular'
        return f'{self.name} · tipo {self.type or "?"} · {self.channel_count} canales · {rate} · {self.hostname or "?"}'

    @property
    def key(self) -> str:
        return f'{self.name}|{self.source_id}|{self.hostname}'


def _pylsl(module: Any = None):
    if module is not None:
        return module
    try:
        import pylsl
    except Exception as exc:
        raise BackendError(f'pylsl no está disponible ({exc}). Instálalo con «pip install pylsl».') from exc
    return pylsl


def _choice_from_info(info: Any) -> LslStreamChoice:
    return LslStreamChoice(info.name(), info.type(), info.source_id(), info.hostname(), int(info.channel_count()),
                           float(info.nominal_srate()))


def discover_lsl_streams(timeout_s: float = 1.5, pylsl_module: Any = None) -> List[LslStreamChoice]:
    """Flujos LSL visibles ahora; primero los de tipo EEG."""
    pylsl = _pylsl(pylsl_module)
    found = [_choice_from_info(info) for info in pylsl.resolve_streams(timeout_s)]
    return sorted(found, key=lambda c: (c.type.upper() != 'EEG', c.name.lower()))


def channel_metadata(info: Any, count: int) -> Tuple[List[str], List[str], List[str]]:
    """Etiquetas, unidades y tipos que declara el flujo (cadenas vacías donde no declara nada)."""
    labels, units, types = [], [], []
    try:
        ch = info.desc().child('channels').child('channel')
        while not ch.empty() and len(labels) < count:
            labels.append(ch.child_value('label'))
            units.append(ch.child_value('unit'))
            types.append(ch.child_value('type'))
            ch = ch.next_sibling()
    except Exception:
        pass
    if len(labels) != count:
        return [''] * count, [''] * count, [''] * count
    return labels, units, types


def unit_scales(units: Sequence[str]) -> Tuple[np.ndarray, str]:
    """Factor de cada canal para llevarlo a µV, y una nota honesta de qué se supuso."""
    scales, unknown = [], set()
    for unit in units:
        factor = UNIT_SCALES.get((unit or '').strip().lower())
        if factor is None:
            unknown.add(unit.strip() or 'sin unidad')
            factor = 1.0
        scales.append(factor)
    if not unknown:
        return np.asarray(scales), 'µV (convertidos de la unidad que declara el flujo).'
    listed = ', '.join(sorted(unknown))
    return np.asarray(scales), (f'El flujo no declara una unidad conocida en algunos canales ({listed}); se asumen µV. '
                                'Si los valores te parecen enormes o diminutos, revisa la unidad en el programa que '
                                'publica el flujo.')


class LslBackend(Backend):
    """Un inlet de LSL sobre el flujo elegido; si el programa lo reinicia, se vuelve a encontrar por nombre e id."""

    def __init__(self, choice: LslStreamChoice, pylsl_module: Any = None) -> None:
        self.choice = choice
        self._module = pylsl_module
        self._inlet = None
        self._keep: List[int] = []
        self._scales = np.ones(0)

    def open(self) -> StreamDescription:
        pylsl = _pylsl(self._module)
        c = self.choice
        prop, value = ('source_id', c.source_id) if c.source_id else ('name', c.name)
        infos = [i for i in pylsl.resolve_byprop(prop, value, 1, LSL_OPEN_TIMEOUT_S)
                 if i.name() == c.name and (not c.hostname or i.hostname() == c.hostname)]
        if not infos:
            raise BackendError(f'No aparece el flujo LSL «{c.name}»: revisa que el programa lo siga publicando.')
        inlet = pylsl.StreamInlet(infos[0], max_buflen=LSL_MAX_BUFFER_S, recover=True)
        info = inlet.info(LSL_OPEN_TIMEOUT_S)
        fs = float(info.nominal_srate())
        count = int(info.channel_count())
        if fs <= 0:
            inlet.close_stream()
            raise BackendError(f'El flujo «{c.name}» es irregular (sin frecuencia de muestreo fija); el espectro '
                               'necesita una frecuencia fija.')
        if info.channel_format() == getattr(pylsl, 'cf_string', 3):
            inlet.close_stream()
            raise BackendError(f'El flujo «{c.name}» manda texto, no números.')
        labels, units, types = channel_metadata(info, count)
        keep = list(range(count))
        if any(t.strip().upper() == 'EEG' for t in types):
            keep = [i for i, t in enumerate(types) if t.strip().upper() == 'EEG']
        names = tuple(labels[i] or f'Canal {i + 1}' for i in keep)
        if len(set(names)) != len(names):
            names = tuple(f'{n} ({i + 1})' for n, i in zip(names, keep))
        scales, unit_note = unit_scales([units[i] for i in keep])
        inlet.open_stream(LSL_OPEN_TIMEOUT_S)
        self._inlet, self._keep, self._scales = inlet, keep, scales
        detail = f'flujo LSL «{c.name}» (tipo {c.type or "?"}) desde {c.hostname or "?"}'
        return StreamDescription(names, fs, detail, unit_note, NO_VERIFICABLE)

    def read(self) -> np.ndarray:
        if self._inlet is None:
            raise BackendError('El flujo LSL no está abierto.')
        samples, _stamps = self._inlet.pull_chunk(timeout=0.0, max_samples=int(LSL_MAX_BUFFER_S * 1000))
        if not samples:
            return np.zeros((len(self._keep), 0))
        data = np.asarray(samples, dtype=float).T
        return data[self._keep] * self._scales[:, None]

    def close(self) -> None:
        inlet, self._inlet = self._inlet, None
        if inlet is not None:
            try:
                inlet.close_stream()
            except Exception:
                pass


# ================================================================ simulador de práctica
class SimulatorBackend(Backend):
    """El simulador de práctica (`simulator.SimulatedEegDevice`). Nunca abre un puerto."""

    def __init__(self, device: Any) -> None:
        self.sim = device

    def open(self) -> StreamDescription:
        if not self.sim.plugged:
            raise BackendError('El cable del simulador está desconectado: pulsa «Reconectar el cable».')
        self.sim.start_session()
        return StreamDescription(tuple(self.sim.channels), float(self.sim.fs), 'Simulador de práctica de BIOCORE',
                                 'µV simulados.', SIMULACION)

    def read(self) -> np.ndarray:
        return self.sim.read()

    def close(self) -> None:
        pass
