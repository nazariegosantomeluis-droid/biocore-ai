"""Catálogo de sensores para la placa ESP32 de BIOCORE (2026-11-14).

Cada sensor dice qué anuncia la placa en su `BIO:HELLO` (`key` = la clave `sensor`), cómo se conecta, cómo se
convierten sus números a unidades físicas y qué se puede concluir con él. El firmware de cada uno está en
`firmware/` (MicroPython; se guarda en la placa como `main.py`).

EMG (MyoWare 2.0, salida RAW): datos de la guía de SparkFun y de la guía avanzada del fabricante
(`MYOWARE_GUIDE`, `MYOWARE_ADVANCED`); colocación de electrodos, también de Mesin et al. 2009.
Pulso por luz (MAX30102) y temperatura (DS18B20), 2026-11-16: registros, rangos y tiempos de sus hojas de datos;
lo que se puede concluir, de las referencias de `clinical/ppg_references.py` y `clinical/temperature_references.py`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, Optional, Tuple

import numpy as np

from clinical.emg_references import MESIN_2009
from clinical.ppg_references import ALLEN_2007, BEURTON_2019, ELGENDI_2013, JUBRAN_2015
from clinical.temperature_references import TAYLOR_2014

from .protocol import Hello

MYOWARE_GUIDE = ('SparkFun, «Getting Started with the MyoWare 2.0 Muscle Sensor Ecosystem» (learn.sparkfun.com), '
                 'leída el 2026-11-14')
MYOWARE_ADVANCED = ('Advancer Technologies, «How MyoWare works», guía avanzada del MyoWare 2.0 (2022), leída el '
                    '2026-11-14')

MAX30102_DATASHEET = ('Maxim Integrated (hoy Analog Devices), «MAX30102: High-Sensitivity Pulse Oximeter and '
                      'Heart-Rate Sensor for Wearable Health», hoja de datos, leída el 2026-11-15')
DS18B20_DATASHEET = ('Maxim Integrated, «DS18B20 Programmable Resolution 1-Wire Digital Thermometer», hoja de datos, '
                     'leída el 2026-11-16')

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


def ppg_counts(values: np.ndarray, hello: Hello) -> np.ndarray:
    """Cuentas del ADC del MAX30102 (luz recibida, 18 bits). Se dejan así: la frecuencia de pulso, el índice de
    perfusión y R son cocientes y no necesitan unidades físicas."""
    return np.asarray(values, dtype=float)


def temp_celsius(values: np.ndarray, hello: Hello) -> np.ndarray:
    """El firmware ya manda grados Celsius (`unit=C`), con la resolución de 12 bits del DS18B20 (0.0625 °C)."""
    return np.asarray(values, dtype=float)


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
    troubleshooting: Tuple[Tuple[str, str], ...] = ()      # (lo que dice la app, qué hacer), propios del sensor
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

PPG = BioSensor(
    key='ppg', name='Pulso por luz (PPG): MAX30102 + ESP32', channels=('ROJO', 'IR'), default_fs=100.0,
    unit_label='cuentas del ADC del MAX30102 (luz recibida, 18 bits)', firmware_file='ppg_max30102.py',
    convert=ppg_counts,
    connection='Placa ESP32 por USB, con el firmware de BIOCORE; la computadora la encuentra sola.',
    material=(
        'Una ESP32 DevKit V1 con MicroPython instalado.',
        'Un módulo MAX30102 (la tarjetita con el sensor que se vende para Arduino) y cuatro cables.',
        'Un cable USB que transmita datos y la computadora con BIOCORE y Thonny.',
    ),
    wiring=(
        ('VIN', '3V3', 'Alimentación del módulo.'),
        ('GND', 'GND', 'Tierra común.'),
        ('SDA', 'GPIO21', 'Datos del bus I2C (el sensor responde en la dirección 0x57).'),
        ('SCL', 'GPIO22', 'Reloj del bus I2C.'),
        ('INT', 'Sin conectar', 'El firmware le pregunta al sensor cada 10 ms; no usa la interrupción.'),
    ),
    placement=(
        'Apoya la yema del índice sobre el sensor, tapando las dos luces, **sin apretar**: la presión aplasta el pulso.',
        'Mano quieta y apoyada en la mesa, más o menos a la altura del corazón.',
        'Tapa el sensor de la luz ambiente, por ejemplo con tu otra mano encima, sin apretar.',
        'Con los dedos fríos el pulso suele verse más pequeño: caliéntalos antes.',
    ),
    firmware_steps=(
        'Descarga el firmware con el botón de abajo (en el repo está en `hardware/biosensors/firmware/ppg_max30102.py`).',
        'Conecta la ESP32 por USB, abre el archivo en Thonny y guárdalo **en la placa** con el nombre `main.py`.',
        '**Cierra Thonny.** Mientras está abierto ocupa el puerto y detiene el programa de la placa.',
        'Presiona el botón EN de la ESP32. Desde ese momento la placa se presenta sola cada 2 s. Si no encuentra el '
        'sensor, lo dice (la app lo muestra como «La placa dice: …»).',
    ),
    app_steps=(
        'En el Multisensor Fusion Lab, elige la vista **«Sensores en vivo»** y el sensor **«Pulso por luz '
        '(MAX30102)»**; en la barra lateral, la placa **«Placa real (ESP32 por USB)»**.',
        'Pulsa **«▶ Buscar la placa»**: la app revisa los puertos USB sola. Cuando diga «Transmitiendo» verás la '
        'insignia 🟢 PROCEDENCIA: SENSOR_REAL.',
        'Pon el dedo y quédate quieto unos segundos. La página no se redibuja sola: pulsa **«🔄 Leer los últimos '
        'segundos»** para analizar lo más reciente.',
        'Para usar Thonny otra vez, pulsa **«⏹ Soltar el puerto»**.',
    ),
    safety=(
        '**Es material educativo, no un dispositivo médico: no mide la saturación de oxígeno y no sirve para vigilar '
        'a nadie ni para diagnosticar.**',
        'Si tienes un oxímetro de verdad, úsalo para comparar la frecuencia de pulso, no para «calibrar» este sensor.',
    ),
    limits=(
        '**No mide la SpO₂.** Un oxímetro convierte R en saturación con una curva calibrada contra mediciones directas '
        'de la saturación arterial (Jubran 2015). Este sensor no tiene esa curva: la app muestra R y dice «no '
        'disponible» en la SpO₂.',
        '**Es la frecuencia de pulso, no la del corazón.** Casi siempre coinciden, pero un latido que no alcanza a '
        'bombear sangre suficiente no aparece en el pulso. Para el ritmo, usa el ECG.',
        '**El movimiento se parece al pulso.** Si los intervalos entre pulsos varían mucho, la app lo avisa: casi '
        'siempre es movimiento, pero también puede ser un ritmo irregular, y el PPG no distingue entre los dos.',
        '**El índice de perfusión cambia con el sitio, la presión del dedo, la temperatura y el sensor:** compáralo '
        'solo contigo, en la misma sesión.',
    ),
    sources=(MAX30102_DATASHEET, ALLEN_2007, ELGENDI_2013, BEURTON_2019, JUBRAN_2015),
    troubleshooting=(
        ('«La placa dice: No se encontró el MAX30102…»', 'Revisa VIN, GND, SDA (GPIO21) y SCL (GPIO22). La placa lo '
                                                        'vuelve a buscar cada 2 s.'),
        ('«…hay otro sensor (PART_ID …), no un MAX30102»', 'Es otro chip en la misma dirección, por ejemplo un '
                                                           'MAX30100: este firmware solo sirve para el MAX30102.'),
        ('«No hay un dedo sobre el sensor…» con el dedo puesto', 'Tapa las dos luces con la yema. El umbral (50 000 '
                                                                 'cuentas de infrarrojo) es una heurística: '
                                                                 '`PpgQualityHeuristics`.'),
        ('«La luz satura el sensor…»', 'Tapa la luz ambiente; si sigue, baja `LED` en el firmware (cada paso es de '
                                       '0.2 mA).'),
    ),
)

TEMP = BioSensor(
    key='temp', name='Temperatura de la piel: DS18B20 + ESP32', channels=('TEMP',), default_fs=1.0,
    unit_label='°C (±0.5 °C según la hoja de datos)', firmware_file='temp_ds18b20.py', convert=temp_celsius,
    connection='Placa ESP32 por USB, con el firmware de BIOCORE; la computadora la encuentra sola.',
    material=(
        'Una ESP32 DevKit V1 con MicroPython instalado.',
        'Un DS18B20 en sonda sumergible (un tubo de acero con tres cables) y una resistencia de 4.7 kΩ.',
        'Un cable USB que transmita datos y la computadora con BIOCORE y Thonny.',
    ),
    wiring=(
        ('VDD (rojo)', '3V3', 'Alimentación (de 3.0 a 5.5 V, según la hoja de datos). Los colores son los más comunes: '
                              'revisa los de tu sonda.'),
        ('GND (negro)', 'GND', 'Tierra común.'),
        ('DQ (amarillo)', 'GPIO4', 'Datos (bus 1-Wire), con la resistencia de 4.7 kΩ entre DQ y 3V3: sin ella no '
                                   'hay comunicación.'),
    ),
    placement=(
        'En la axila: la punta de la sonda en el hueco, con el brazo pegado al cuerpo y sin ropa de por medio.',
        'La sonda tarda minutos en igualarse con la piel: no leas hasta que la curva se aplane. La app dice «estable» '
        'cuando cambia menos de 0.1 °C en un minuto.',
        'Quieto, lejos de corrientes de aire, del sol y de cualquier fuente de calor.',
    ),
    firmware_steps=(
        'Descarga el firmware con el botón de abajo (en el repo está en `hardware/biosensors/firmware/temp_ds18b20.py`).',
        'Conecta la ESP32 por USB, abre el archivo en Thonny y guárdalo **en la placa** con el nombre `main.py`.',
        '**Cierra Thonny.** Mientras está abierto ocupa el puerto y detiene el programa de la placa.',
        'Presiona el botón EN de la ESP32. La placa se presenta sola cada 2 s y manda una lectura por segundo. Si no '
        'encuentra la sonda, lo dice (la app lo muestra como «La placa dice: …»).',
    ),
    app_steps=(
        'En el Multisensor Fusion Lab, elige la vista **«Sensores en vivo»** y el sensor **«Temperatura (DS18B20)»**; '
        'en la barra lateral, la placa **«Placa real (ESP32 por USB)»**.',
        'Pulsa **«▶ Buscar la placa»**. Cuando diga «Transmitiendo» verás la insignia 🟢 PROCEDENCIA: SENSOR_REAL.',
        'Coloca la sonda y espera. Pulsa **«🔄 Leer los últimos segundos»** de vez en cuando para ver la curva.',
        'Para usar Thonny otra vez, pulsa **«⏹ Soltar el puerto»**.',
    ),
    safety=(
        '**Es material educativo, no un termómetro clínico: no sirve para decir si alguien tiene fiebre.**',
        'Limpia la sonda antes y después de usarla, y úsala solo sobre la piel: nunca en la boca ni en otra cavidad.',
    ),
    limits=(
        '**Mide la temperatura de la sonda**, que con buen contacto se acerca a la de la piel. La temperatura de la '
        'piel resulta del metabolismo local, de la conducción del tejido y del flujo de sangre (Taylor 2014): cambia '
        'con el ambiente y no es la temperatura central.',
        '**No existe una medición de la temperatura central que sea estándar de oro** (Taylor 2014), y la axila es '
        'piel, no un sitio central.',
        '**±0.5 °C entre −10 y +85 °C** (hoja de datos), sin calibrar contra un termómetro clínico. Que muestre '
        'centésimas no la hace más exacta: su resolución es de 0.0625 °C.',
    ),
    sources=(DS18B20_DATASHEET, TAYLOR_2014),
    troubleshooting=(
        ('«La placa dice: No se encontró ningún DS18B20…»', 'Revisa el cable de datos (DQ a GPIO4) y la resistencia de '
                                                           '4.7 kΩ entre DQ y 3V3: sin ella el bus no funciona.'),
        ('«85 °C exactos es el valor de encendido…»', 'La lectura no terminó: revisa la alimentación y la '
                                                      'resistencia.'),
        ('La temperatura no deja de subir', 'Es normal los primeros minutos: la sonda se está igualando con la piel. '
                                            'Espera a que la app diga «estable».'),
    ),
)

SENSORS: Tuple[BioSensor, ...] = (EMG, PPG, TEMP)
_BY_KEY = {s.key: s for s in SENSORS}


def get_sensor(key: str) -> BioSensor:
    return _BY_KEY[key]


def find_sensor(key: str) -> Optional[BioSensor]:
    return _BY_KEY.get((key or '').strip().lower())
