"""Catálogo de sensores para la placa ESP32 de BIOCORE (2026-11-14).

Cada sensor dice qué anuncia la placa en su `BIO:HELLO` (`key` = la clave `sensor`), cómo se conecta, cómo se
convierten sus números a unidades físicas y qué se puede concluir con él. El firmware de cada uno está en
`firmware/` (MicroPython; se guarda en la placa como `main.py`).

EMG (MyoWare 2.0, salida RAW): datos de la guía de SparkFun y de la guía avanzada del fabricante
(`MYOWARE_GUIDE`, `MYOWARE_ADVANCED`); colocación de electrodos, también de Mesin et al. 2009.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, Optional, Tuple

import numpy as np

from clinical.emg_references import MESIN_2009

from .protocol import Hello

MYOWARE_GUIDE = ('SparkFun, «Getting Started with the MyoWare 2.0 Muscle Sensor Ecosystem» (learn.sparkfun.com), '
                 'leída el 2026-11-14')
MYOWARE_ADVANCED = ('Advancer Technologies, «How MyoWare works», guía avanzada del MyoWare 2.0 (2022), leída el '
                    '2026-11-14')

ESP32_ADC_NOTE = ('El ADC del ESP32 no está calibrado aquí: los números son aproximados, y peores cerca de 0 V y de '
                  '3.3 V.')


def counts_to_volts(counts: np.ndarray, hello: Hello) -> np.ndarray:
    bits = int(hello.number('bits') or 12)
    vref = float(hello.number('vref') or 3.3)
    return np.asarray(counts, dtype=float) / ((1 << bits) - 1) * vref


def emg_to_mv(values: np.ndarray, hello: Hello) -> np.ndarray:
    """Cuentas del ADC → mV en la piel, aproximados: la salida RAW del MyoWare está centrada en +Vs/2 y tiene una
    ganancia fija de 200 (guía avanzada). Se supone que el MyoWare va a 3.3 V, igual que la referencia del ADC."""
    vref = float(hello.number('vref') or 3.3)
    gain = float(hello.number('gain') or 200.0)
    return (counts_to_volts(values, hello) - vref / 2.0) / gain * 1000.0


@dataclass(frozen=True)
class BioSensor:
    key: str                                  # la clave `sensor` del HELLO
    name: str
    channels: Tuple[str, ...]
    default_fs: float
    unit_label: str
    firmware_file: str
    convert: Callable[[np.ndarray, Hello], np.ndarray]
    connection: str
    material: Tuple[str, ...] = ()
    wiring: Tuple[Tuple[str, str, str], ...] = ()          # (pin del sensor, pin de la ESP32, para qué)
    placement: Tuple[str, ...] = ()
    firmware_steps: Tuple[str, ...] = ()
    app_steps: Tuple[str, ...] = ()
    safety: Tuple[str, ...] = ()
    limits: Tuple[str, ...] = ()
    sources: Tuple[str, ...] = ()
    extra: Dict[str, str] = field(default_factory=dict)

    @property
    def firmware_path(self):
        from pathlib import Path
        return Path(__file__).resolve().parent / 'firmware' / self.firmware_file


EMG = BioSensor(
    key='emg', name='EMG de superficie: MyoWare 2.0 (salida RAW) + ESP32', channels=('EMG',), default_fs=1000.0,
    unit_label='mV en la piel (aprox.)', firmware_file='emg_myoware.py', convert=emg_to_mv,
    connection='Placa ESP32 por USB, con el firmware de BIOCORE; la computadora la encuentra sola.',
    material=(
        'Una ESP32 DevKit V1 con MicroPython instalado.',
        'Un MyoWare 2.0 Muscle Sensor y tres electrodos de broche (dos van en el sensor y uno es la referencia).',
        'Un cable soldado al pad RAW del MyoWare: RAW está en un pad de la tarjeta, no en un broche.',
        'Un cable USB que transmita datos y la computadora con BIOCORE y Thonny, funcionando con batería.',
    ),
    wiring=(
        ('+', '3V3', 'Alimentación a 3.3 V: la salida RAW queda dentro del rango del ADC, centrada en 1.65 V.'),
        ('−', 'GND', 'Tierra común.'),
        ('RAW', 'GPIO34', 'El EMG amplificado 200 veces, sin rectificar (entrada analógica).'),
        ('ENV', 'Sin conectar', 'La envolvente: el analizador de BIOCORE necesita la señal cruda (RAW).'),
    ),
    placement=(
        'Los dos electrodos del sensor (MID y END) van sobre el vientre del músculo, entre la zona de inervación y '
        'la unión con el tendón, en una línea paralela a las fibras.',
        'La referencia (REF) va en otra parte del cuerpo, por ejemplo la parte ósea del codo, con buen contacto.',
        'Evita poner los electrodos sobre la zona de inervación: ahí la amplitud cae bruscamente y la frecuencia '
        'del EMG cambia mucho con la posición.',
    ),
    firmware_steps=(
        'Descarga el firmware con el botón de abajo (en el repo está en `hardware/biosensors/firmware/emg_myoware.py`).',
        'Conecta la ESP32 por USB, abre el archivo en Thonny y guárdalo **en la placa** con el nombre `main.py`.',
        '**Cierra Thonny.** Mientras está abierto ocupa el puerto y detiene el programa de la placa.',
        'Presiona el botón EN de la ESP32. Desde ese momento la placa se presenta sola cada 2 s.',
    ),
    app_steps=(
        'En el EMG Muscle Lab, en la barra lateral, elige el origen **«Sensor en vivo (ESP32 + MyoWare)»** y la placa '
        '**«Placa real (ESP32 por USB)»**.',
        'Pulsa **«▶ Buscar la placa»**: la app revisa los puertos USB sola. Cuando diga «Transmitiendo» verás la '
        'insignia 🟢 PROCEDENCIA: SENSOR_REAL.',
        'Contrae y relaja el músculo. La página no se redibuja sola: pulsa **«🔄 Leer los últimos segundos»** para '
        'analizar lo más reciente (los segundos del control «Duración»).',
        'Para usar Thonny otra vez, pulsa **«⏹ Soltar el puerto»**.',
    ),
    safety=(
        '**Con una persona conectada a los electrodos, la computadora va con batería.** Desconecta el cargador de la '
        'pared antes de pegar los electrodos y no lo conectes hasta despegarlos.',
        'Es material educativo, no un dispositivo médico: no sirve para diagnosticar ni para descartar nada.',
        'Piel limpia y seca, y electrodos que peguen bien; quien se mide, sentado y sin moverse más que el músculo.',
    ),
    limits=(
        '**Una sola derivación de superficie.** La amplitud cambia con la piel, la grasa y la colocación: no compares '
        'microvoltios entre personas ni entre sesiones.',
        '**Banda del sensor de 20.8 a 498.4 Hz, con filtros de primer orden** (guía avanzada): a 1000 Hz algo de lo '
        'que pasa de 500 Hz se dobla hacia abajo. Si bajas el muestreo, la frecuencia mediana pierde sentido.',
        '**Los mV son aproximados**: suponen la ganancia de 200 y un MyoWare a 3.3 V, y el ADC del ESP32 no está '
        'calibrado.',
        '**«Activación muscular» del laboratorio no es el porcentaje de la contracción máxima (%MVC)**: es el '
        'cociente entre el promedio y el pico del EMG rectificado. Para saber cuánto contraes, mira el RMS en mV.',
    ),
    sources=(MYOWARE_GUIDE, MYOWARE_ADVANCED, MESIN_2009),
)

SENSORS: Tuple[BioSensor, ...] = (EMG,)
_BY_KEY = {s.key: s for s in SENSORS}


def get_sensor(key: str) -> BioSensor:
    return _BY_KEY[key]


def find_sensor(key: str) -> Optional[BioSensor]:
    return _BY_KEY.get((key or '').strip().lower())
