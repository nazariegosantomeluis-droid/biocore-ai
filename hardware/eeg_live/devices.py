"""Catálogo de dispositivos EEG que abre el EEG Neuro Lab (2026-11-14).

Cada entrada dice cómo se conecta, qué datos pide, cómo se llaman sus canales y qué procedencia tiene lo
que entrega:

- `SENSOR_REAL`: BrainFlow abre la placa física. Solo se muestra así mientras están llegando muestras.
- `SIMULACION`: el tablero sintético de BrainFlow o el simulador de práctica de BIOCORE.
- `NO_VERIFICABLE`: un flujo LSL. BIOCORE no puede comprobar si detrás hay un equipo o un programa que
  genera datos; al gemelo se guarda como simulación, con el nombre del flujo en el detalle.

Pasos y requisitos de conexión: documentación de BrainFlow («Supported Boards») y de OpenBCI (guía de
inicio de la Cyton; LSL desde OpenBCI GUI), leídas el 2026-11-14 (`BRAINFLOW_DOCS`, `OPENBCI_CYTON_DOCS`,
`OPENBCI_LSL_DOCS`). Nombres de canal y frecuencias de muestreo: los descriptores de BrainFlow 5.24.0
(`BoardShim.get_board_descr`); `tests/test_eeg_live.py` comprueba que sigan coincidiendo con la versión
instalada.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional, Tuple

SENSOR_REAL = 'SENSOR_REAL'
SIMULACION = 'SIMULACION'
NO_VERIFICABLE = 'NO_VERIFICABLE'

BRAINFLOW_DOCS = ('BrainFlow, documentación «Supported Boards» y «Data Format Description» '
                  '(brainflow.readthedocs.io), leída el 2026-11-14')
OPENBCI_CYTON_DOCS = 'OpenBCI, «Cyton Getting Started Guide» (docs.openbci.com), leída el 2026-11-14'
OPENBCI_LSL_DOCS = 'OpenBCI, «Lab Streaming Layer (LSL)» (docs.openbci.com), leída el 2026-11-14'
DESCRIPTOR_NOTE = 'nombres y frecuencia de los descriptores de BrainFlow 5.24.0'

# Lo que pide cada campo de BrainFlowInputParams, dicho para la persona que lo llena.
PARAM_LABELS = {
    'serial_port': 'el puerto serial del dongle',
    'mac_address': 'la dirección MAC',
    'serial_number': 'el nombre o número de serie del equipo',
    'other_info': 'opciones extra de BrainFlow (other_info)',
}

_BLE_PLATFORMS = ('Bluetooth de la computadora: Windows 10 (10.0.19041 o más nuevo) o macOS 10.15 o más nuevo '
                  '(en macOS 12.0 a 12.2 la búsqueda falla: actualiza a 12.3 o más). En Linux probablemente haya '
                  'que compilar BrainFlow desde el código fuente.')
_SERIAL_PLATFORMS = 'Windows 8.1 o más nuevo, Linux y macOS.'


@dataclass(frozen=True)
class EegDevice:
    """Un dispositivo del catálogo."""

    key: str
    name: str
    backend: str                         # 'brainflow', 'lsl' o 'simulador'
    provenance: str                      # SENSOR_REAL, SIMULACION o NO_VERIFICABLE
    link: str                            # 'serial', 'ble', 'dongle', 'red' o 'ninguno'
    connection: str
    platforms: str = ''
    board: Optional[str] = None          # nombre en brainflow.board_shim.BoardIds
    channels: Tuple[str, ...] = ()
    fs: Optional[float] = None
    names_note: str = ''
    required: Tuple[str, ...] = ()
    optional: Tuple[str, ...] = ()
    steps: Tuple[str, ...] = ()
    source: str = ''
    default_channels: Tuple[str, ...] = ()   # los que la página propone analizar (si no, los primeros 4)

    @property
    def is_simulated(self) -> bool:
        return self.provenance == SIMULACION


CYTON_STEPS = (
    'Carga la batería LiPo hasta que el LED del cargador se ponga verde. OpenBCI recomienda usar siempre el '
    'portapilas que vino con el kit.',
    'Instala el driver FTDI VCP: el dongle USB de OpenBCI usa un chip FTDI.',
    'Conecta el dongle con su interruptor en **GPIO 6** (no en RESET): del lado más cercano a la computadora.',
    'Pon el interruptor de la Cyton en **PC** (no en OFF ni en BLE).',
    'En Windows, baja la latencia del driver FTDI con la guía «FTDI Driver Fix» de OpenBCI: con la de fábrica '
    'la señal llega entrecortada.',
    'En macOS elige el puerto `/dev/cu.…`, no `/dev/tty.…`. En Linux quizá necesites permiso para el puerto '
    'serial.',
    'Cierra OpenBCI GUI o cualquier programa que use el dongle: un puerto serial lo abre un solo programa a la vez.',
)

BLE_STEPS = (
    'Enciende el equipo y déjalo cerca de la computadora, con el Bluetooth de la computadora encendido.',
    'BrainFlow lo busca solo. Si hay varios iguales cerca, escribe su dirección MAC o su nombre en «Opcional».',
    'En macOS 12 o más nuevo quizá tengas que darle permiso de Bluetooth a la aplicación.',
    'Si otra app (la del teléfono, por ejemplo) está conectada al equipo, desconéctala antes.',
)

DEVICES: Tuple[EegDevice, ...] = (
    EegDevice(
        key='practica', name='Simulador de práctica de BIOCORE', backend='simulador', provenance=SIMULACION,
        link='ninguno', connection='Sin hardware. Lo controlas tú: ojos abiertos o cerrados, parpadeo, electrodo '
                                   'flojo y cable.',
        channels=('Fp1', 'Fp2', 'C3', 'C4', 'P7', 'P8', 'O1', 'O2'), fs=250.0,
        names_note='montaje del simulador (las posiciones por defecto de la Cyton en BrainFlow)',
        default_channels=('Fp1', 'Fp2', 'O1', 'O2'),
        steps=('Elige «Simulador de práctica de BIOCORE» y pulsa «Conectar».',
               'Los controles del simulador aparecen debajo, en la barra lateral, y en la práctica del tutorial.'),
    ),
    EegDevice(
        key='brainflow_sintetico', name='Tablero sintético de BrainFlow', backend='brainflow',
        provenance=SIMULACION, link='ninguno', board='SYNTHETIC_BOARD',
        connection='Sin hardware: BrainFlow genera la señal. Sirve para comprobar que BrainFlow quedó bien instalado.',
        platforms='Windows 8.1 o más nuevo, Linux y macOS.',
        channels=('Fz', 'C3', 'Cz', 'C4', 'Pz', 'PO7', 'Oz', 'PO8', 'F5', 'F7', 'F3', 'F1', 'F2', 'F4', 'F6', 'F8'),
        fs=250.0, names_note=DESCRIPTOR_NOTE,
        steps=('Elige «Tablero sintético de BrainFlow» y pulsa «Conectar».',
               'No es EEG: en BrainFlow 5.24.0 cada canal es un seno (el canal k, de 1 a 16, a 5·k Hz) más ruido. '
               'Fz (5 Hz) debe salir theta, C3 (10 Hz) alfa y Cz (15 Hz) beta.'),
        source=BRAINFLOW_DOCS,
    ),
    EegDevice(
        key='cyton', name='OpenBCI Cyton (8 canales)', backend='brainflow', provenance=SENSOR_REAL, link='serial',
        board='CYTON_BOARD', connection='Dongle USB de OpenBCI (puerto serial).', platforms=_SERIAL_PLATFORMS,
        channels=('Fp1', 'Fp2', 'C3', 'C4', 'P7', 'P8', 'O1', 'O2'), fs=250.0,
        names_note=DESCRIPTOR_NOTE + '; solo valen si pones los electrodos ahí',
        required=('serial_port',), steps=CYTON_STEPS, source=BRAINFLOW_DOCS + ' · ' + OPENBCI_CYTON_DOCS,
        default_channels=('Fp1', 'Fp2', 'O1', 'O2'),
    ),
    EegDevice(
        key='cyton_daisy', name='OpenBCI Cyton + Daisy (16 canales)', backend='brainflow', provenance=SENSOR_REAL,
        link='serial', board='CYTON_DAISY_BOARD', connection='Dongle USB de OpenBCI (puerto serial).',
        platforms=_SERIAL_PLATFORMS,
        channels=('Fp1', 'Fp2', 'C3', 'C4', 'P7', 'P8', 'O1', 'O2', 'F7', 'F8', 'F3', 'F4', 'T7', 'T8', 'P3', 'P4'),
        fs=125.0, names_note=DESCRIPTOR_NOTE + '; solo valen si pones los electrodos ahí',
        required=('serial_port',), steps=CYTON_STEPS + ('Con la Daisy, BrainFlow entrega 16 canales a 125 Hz.',),
        default_channels=('Fp1', 'Fp2', 'O1', 'O2'),
        source=BRAINFLOW_DOCS + ' · ' + OPENBCI_CYTON_DOCS,
    ),
    EegDevice(
        key='ganglion', name='OpenBCI Ganglion (4 canales)', backend='brainflow', provenance=SENSOR_REAL, link='ble',
        board='GANGLION_NATIVE_BOARD', connection='Bluetooth de la computadora (sin dongle).',
        platforms=_BLE_PLATFORMS, channels=('Canal 1', 'Canal 2', 'Canal 3', 'Canal 4'), fs=200.0,
        names_note='BrainFlow no les pone nombre: tú decides dónde va cada electrodo',
        optional=('mac_address', 'serial_number', 'other_info'),
        steps=BLE_STEPS + ('Desde BrainFlow 5.21 se usa por defecto el firmware 3. Para una Ganglion con firmware 2 '
                           'escribe `fw:2` en «opciones extra».',),
        source=BRAINFLOW_DOCS,
    ),
    EegDevice(
        key='muse_2', name='Muse 2', backend='brainflow', provenance=SENSOR_REAL, link='ble', board='MUSE_2_BOARD',
        connection='Bluetooth de la computadora (sin dongle).', platforms=_BLE_PLATFORMS,
        channels=('TP9', 'AF7', 'AF8', 'TP10'), fs=256.0,
        names_note=DESCRIPTOR_NOTE + '; la diadema los tiene en lugares fijos',
        optional=('mac_address', 'serial_number', 'other_info'),
        steps=BLE_STEPS + ('BrainFlow la inicia con el comando p21: 4 canales de EEG más el sensor de movimiento.',),
        source=BRAINFLOW_DOCS,
    ),
    EegDevice(
        key='muse_s', name='Muse S', backend='brainflow', provenance=SENSOR_REAL, link='ble', board='MUSE_S_BOARD',
        connection='Bluetooth de la computadora (sin dongle).', platforms=_BLE_PLATFORMS,
        channels=('TP9', 'AF7', 'AF8', 'TP10'), fs=256.0,
        names_note=DESCRIPTOR_NOTE + '; la diadema los tiene en lugares fijos',
        optional=('mac_address', 'serial_number', 'other_info'),
        steps=BLE_STEPS + ('BrainFlow la inicia con el comando p21: 4 canales de EEG más el sensor de movimiento.',),
        source=BRAINFLOW_DOCS,
    ),
    EegDevice(
        key='unicorn', name='g.tec Unicorn (8 canales)', backend='brainflow', provenance=SENSOR_REAL, link='dongle',
        board='UNICORN_BOARD', connection='El dongle Bluetooth que trae el Unicorn.',
        platforms='Windows y Ubuntu 18.04 (en otros Linux depende de la biblioteca de Unicorn).',
        channels=('Fz', 'C3', 'Cz', 'C4', 'Pz', 'PO7', 'Oz', 'PO8'), fs=250.0, names_note=DESCRIPTOR_NOTE,
        default_channels=('Fz', 'Cz', 'Pz', 'Oz'),
        optional=('serial_number',),
        steps=('Conecta el dongle que trae el Unicorn.',
               'Empareja el Unicorn con la computadora usando ese dongle, no el Bluetooth integrado.',
               'Si hay varios Unicorn cerca, escribe su número de serie en «Opcional».'),
        source=BRAINFLOW_DOCS,
    ),
    EegDevice(
        key='lsl', name='Flujo LSL (cualquier programa)', backend='lsl', provenance=NO_VERIFICABLE, link='red',
        connection='Lab Streaming Layer: un programa de tu computadora o de tu red publica el EEG.',
        names_note='los que declara el flujo; si no declara ninguno, Canal 1, Canal 2…',
        steps=('En el programa que lee tu equipo, activa la salida LSL. En OpenBCI GUI: widget Networking, '
               'protocolo LSL, «Start LSL Stream».',
               'En BIOCORE elige «Flujo LSL», pulsa «Buscar flujos LSL», elige el tuyo y pulsa «Conectar».',
               'Hace falta una frecuencia de muestreo fija: los flujos irregulares no sirven para el espectro.',
               'Si el flujo declara la unidad de cada canal (microvolts, millivolts o volts) se convierte a µV; si no '
               'la declara, se asumen µV y se avisa.'),
        source=OPENBCI_LSL_DOCS,
    ),
)

_BY_KEY = {d.key: d for d in DEVICES}


def get_device(key: str) -> EegDevice:
    return _BY_KEY[key]


@lru_cache(maxsize=None)
def backend_unavailable_reason(backend: str) -> Optional[str]:
    """None si la librería del backend se puede usar aquí; si no, el motivo y cómo arreglarlo."""
    if backend == 'brainflow':
        try:
            importlib.import_module('brainflow.board_shim')
        except Exception as exc:     # ImportError, u OSError si falta la biblioteca nativa
            return f'BrainFlow no está disponible ({type(exc).__name__}: {exc}). Instálalo con «pip install brainflow».'
        return None
    if backend == 'lsl':
        try:
            importlib.import_module('pylsl')
        except Exception as exc:     # RuntimeError si falta liblsl
            return (f'pylsl no está disponible ({type(exc).__name__}: {exc}). Instálalo con «pip install pylsl»; en '
                    'Linux también hace falta la biblioteca liblsl.')
        return None
    return None
