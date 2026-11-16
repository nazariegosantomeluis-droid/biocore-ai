"""Firmware de temperatura de BIOCORE · ESP32 + DS18B20 · MicroPython 1.20 o más nuevo.

Qué hace
  - Lee un DS18B20 (bus 1-Wire) una vez por segundo, a 12 bits: pasos de 0.0625 °C y hasta 750 ms por conversión,
    según su hoja de datos. Manda cada lectura en grados Celsius:
        BIO:D,<seq>,<temperatura>
    seq = número de la lectura; si una se salta (el ciclo se atrasó más de un segundo), seq salta lo mismo.
  - Se presenta con BIO:HELLO al arrancar, cada 2 s y cuando la computadora manda BIO?.
  - Si no encuentra la sonda o una lectura falla, lo dice con BIO:E (la app lo muestra) y la vuelve a buscar.

Conexión (ESP32 DevKit V1 y un DS18B20 en sonda; los colores son los más comunes, revisa los de tu sonda)
    VDD (rojo)      → 3V3
    GND (negro)     → GND
    DQ  (amarillo)  → GPIO4, con una resistencia de 4.7 kΩ entre DQ y 3V3 (sin ella no hay comunicación)

Cargar: en Thonny, guarda este archivo en la placa como main.py, cierra Thonny y presiona EN. Thonny detiene el
programa al conectarse: con Thonny abierto, la computadora verá '>>>' en vez de tramas BIO.

Esto es material educativo, no un termómetro clínico: no sirve para decir si alguien tiene fiebre.
"""

import sys
import time

try:
    import select
except ImportError:  # algunos puertos viejos de MicroPython
    import uselect as select

import ds18x20
import onewire
from machine import Pin

try:
    ticks_ms, ticks_diff, sleep_ms = time.ticks_ms, time.ticks_diff, time.sleep_ms
except AttributeError:  # CPython: permite probar este mismo archivo en la computadora
    ticks_ms = lambda: int(time.monotonic() * 1000)
    ticks_diff = lambda a, b: a - b
    sleep_ms = lambda ms: time.sleep(ms / 1000)

FW = '1.0'
FS = 1                    # una lectura por segundo; la computadora lo lee del HELLO
PERIODO_MS = 1000
CONVERSION_MS = 750       # lo más que tarda una conversión a 12 bits (hoja de datos)
PIN_DATOS = 4
HELLO_CADA_MS = 2000
REINTENTO_MS = 2000

DETENER = False           # las pruebas lo ponen en True para salir del ciclo
ENTRADA = SALIDA = None   # en la computadora, las pruebas conectan aquí una terminal simulada


def _hello(tarde, perdidas):
    return ('BIO:HELLO,sensor=temp,fw=%s,fs=%d,ch=TEMP,unit=C,res=12,blk=1,sim=0,tarde=%d,perdidas=%d'
            % (FW, FS, tarde, perdidas))


def ejecutar(ciclos=None):
    sensor = ds18x20.DS18X20(onewire.OneWire(Pin(PIN_DATOS)))
    salida = SALIDA or sys.stdout
    entrada = ENTRADA or sys.stdin
    try:
        poll = select.poll()
        poll.register(entrada, select.POLLIN)
    except Exception:
        poll = None                                            # sin entrada: el HELLO periódico basta

    def escribir(texto):
        salida.write(texto + '\n')

    sondas = []
    seq = tarde = perdidas = 0
    convirtiendo = False
    pedido = ''
    t_intento = ticks_ms() - REINTENTO_MS
    t_siguiente = t_conversion = ticks_ms()
    escribir(_hello(0, 0))
    t_hello = ticks_ms()
    n = 0
    while not DETENER and (ciclos is None or n < ciclos):
        n += 1
        # 1) ¿La computadora pidió el handshake (BIO?)?
        if poll is not None:
            for _ in range(64):
                if not poll.poll(0):
                    break
                c = entrada.read(1)
                if not c:
                    break
                if c == '\n':
                    if 'BIO?' in pedido:
                        t_hello = ticks_ms() - HELLO_CADA_MS
                    pedido = ''
                elif len(pedido) < 32:
                    pedido += c
        # 2) Handshake periódico.
        ahora = ticks_ms()
        if ticks_diff(ahora, t_hello) >= HELLO_CADA_MS:
            escribir(_hello(tarde, perdidas))
            t_hello = ahora
        # 3) Sin sonda: buscarla cada 2 s y decir por qué no está.
        if not sondas:
            if ticks_diff(ahora, t_intento) >= REINTENTO_MS:
                t_intento = ahora
                try:
                    sondas = sensor.scan()
                except Exception:
                    sondas = []
                if sondas:
                    convirtiendo = False
                    t_siguiente = ahora
                else:
                    escribir('BIO:E,No se encontró ningún DS18B20 en GPIO4: revisa el cable de datos y la resistencia '
                             'de 4.7 kΩ entre DQ y 3V3.')
            sleep_ms(10)
            continue
        # 4) Una conversión por segundo; si el ciclo se atrasó más de un periodo, se salta y seq lo delata.
        if not convirtiendo and ticks_diff(ahora, t_siguiente) >= 0:
            atraso = ticks_diff(ahora, t_siguiente)
            if atraso >= PERIODO_MS:
                saltadas = atraso // PERIODO_MS
                seq += saltadas
                perdidas += saltadas
                t_siguiente += saltadas * PERIODO_MS
            elif atraso > PERIODO_MS // 10:
                tarde += 1
            try:
                sensor.convert_temp()
            except Exception as exc:
                escribir('BIO:E,No se pudo iniciar la lectura del DS18B20 (%s): revisa el cable de datos.' % exc)
                sondas = []
                continue
            convirtiendo = True
            t_conversion = ahora
            t_siguiente += PERIODO_MS
        elif convirtiendo and ticks_diff(ahora, t_conversion) >= CONVERSION_MS:
            convirtiendo = False
            try:
                grados = sensor.read_temp(sondas[0])
            except Exception as exc:
                escribir('BIO:E,No se pudo leer el DS18B20 (%s): revisa el cable de datos.' % exc)
                sondas = []
                continue
            escribir('BIO:D,%d,%.4f' % (seq, grados))
            seq += 1
        sleep_ms(10)


if __name__ == '__main__':
    ejecutar()
