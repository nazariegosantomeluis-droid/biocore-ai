"""Firmware ECG Plug & Play · ESP32 + AD8232 · MicroPython 1.20 o más nuevo.

Qué hace
  - Muestrea la salida del AD8232 a 250 Hz con un Timer (ADC de 12 bits: 0 a 4095).
  - Lee LO+ y LO− (electrodo suelto). En el modo de detección en DC del AD8232,
    LOD+ está en alto cuando el electrodo de +IN está desconectado y LOD− cuando
    lo está el de −IN (hoja de datos del AD8232, Rev. D).
  - Manda bloques de 10 muestras por el mismo USB que usa Thonny, a 115200 baudios:
        ECG:D,<seq>,<lo>,<v1>,...,<v10>
    seq = índice de la primera muestra (la computadora detecta así las perdidas);
    lo = 1 (LO+), 2 (LO−), 3 (ambos), 0 (bien).
  - Se presenta con ECG:HELLO al arrancar, cada 2 s y cuando la computadora manda ECG?.
    Así la computadora la reconoce sola, sin elegir el puerto a mano.

Conexión (ESP32 DevKit V1 y placa AD8232 tipo SparkFun)
    AD8232 OUTPUT → GPIO34   (ADC1: sigue funcionando aunque se active el Wi-Fi)
    AD8232 LO+    → GPIO35
    AD8232 LO−    → GPIO32
    AD8232 3.3V   → 3V3      (no a 5V)
    AD8232 GND    → GND
    SDN           sin conectar
    Electrodos: RA brazo derecho, LA brazo izquierdo, RL pierna derecha (o abdomen).

Cargar: en Thonny, guarda este archivo en la placa como main.py, cierra Thonny y
presiona EN. Thonny detiene el programa al conectarse: con Thonny abierto, la
computadora verá '>>>' en vez de tramas ECG.

Seguridad: con una persona conectada a los electrodos, la computadora va con
batería (sin el cargador conectado a la pared). Esto es material educativo,
no un dispositivo médico.
"""

import sys
import time
from array import array

try:
    import select
except ImportError:  # algunos puertos viejos de MicroPython
    import uselect as select

from machine import ADC, Pin, Timer

try:
    import micropython

    micropython.alloc_emergency_exception_buf(100)
except Exception:
    pass

try:
    ticks_ms, ticks_us, ticks_diff, sleep_ms = time.ticks_ms, time.ticks_us, time.ticks_diff, time.sleep_ms
except AttributeError:  # CPython: permite probar este mismo archivo en la computadora
    ticks_ms = lambda: int(time.monotonic() * 1000)
    ticks_us = lambda: int(time.monotonic() * 1000000)
    ticks_diff = lambda a, b: a - b
    sleep_ms = lambda ms: time.sleep(ms / 1000)

FW = '1.0'
FS = 250                  # Hz; si lo cambias, cambia también fs en la computadora
PERIODO_MS = 4            # 1000 / FS
BLOQUE = 10               # muestras por línea (25 líneas por segundo)
ANILLO = 256              # potencia de 2: ~1 s de colchón si el ciclo principal se atrasa
PIN_ECG, PIN_LO_MAS, PIN_LO_MENOS = 34, 35, 32
GANANCIA = 1100           # supuesto: la de la config. «monitor cardiaco» del AD8232 (hoja de datos Rev. D,
                          # Fig. 66); tu tarjeta puede tener otra. La computadora la usa para estimar mV.
HELLO_CADA_MS = 2000
TIMER_ID = 0

DETENER = False           # las pruebas lo ponen en True para salir del ciclo
ENTRADA = SALIDA = None   # en la computadora, las pruebas conectan aquí una terminal simulada

_valores = array('H', [0] * ANILLO)
_lo = bytearray(ANILLO)
_escritas = 0
_tarde = 0
_ultimo_us = 0
_adc = _lo_mas = _lo_menos = None


def _muestrear(_t):
    """Corre 250 veces por segundo (Timer). Sin crear objetos nuevos."""
    global _escritas, _tarde, _ultimo_us
    ahora = ticks_us()
    if _ultimo_us and ticks_diff(ahora, _ultimo_us) > 6000:   # llegó 1.5 periodos tarde
        _tarde += 1
    _ultimo_us = ahora
    i = _escritas & (ANILLO - 1)
    _valores[i] = _adc.read_u16() >> 4                         # 0 a 4095
    _lo[i] = _lo_mas.value() | (_lo_menos.value() << 1)
    _escritas += 1


def _hello(perdidas):
    return ('ECG:HELLO,fw=%s,fs=%d,bits=12,vref=3.3,gain=%d,blk=%d,tarde=%d,perdidas=%d'
            % (FW, FS, GANANCIA, BLOQUE, _tarde, perdidas))


def ejecutar(ciclos=None):
    global _adc, _lo_mas, _lo_menos, _escritas, _tarde, _ultimo_us
    _adc = ADC(Pin(PIN_ECG))
    _adc.atten(ADC.ATTN_11DB)                                  # rango completo de 0 a ~3.3 V
    _lo_mas = Pin(PIN_LO_MAS, Pin.IN)
    _lo_menos = Pin(PIN_LO_MENOS, Pin.IN)
    _escritas = _tarde = _ultimo_us = 0

    salida = SALIDA or sys.stdout
    entrada = ENTRADA or sys.stdin
    try:
        poll = select.poll()
        poll.register(entrada, select.POLLIN)
    except Exception:
        poll = None                                            # sin entrada: el HELLO periódico basta

    def escribir(texto):
        salida.write(texto + '\n')

    leidas = 0
    perdidas = 0
    pedido = ''
    escribir(_hello(0))
    t_hello = ticks_ms()
    timer = Timer(TIMER_ID)
    timer.init(period=PERIODO_MS, mode=Timer.PERIODIC, callback=_muestrear)
    n = 0
    try:
        while not DETENER and (ciclos is None or n < ciclos):
            n += 1
            # 1) ¿La computadora pidió el handshake (ECG?)?
            if poll is not None:
                for _ in range(64):
                    if not poll.poll(0):
                        break
                    c = entrada.read(1)
                    if not c:
                        break
                    if c == '\n':
                        if 'ECG?' in pedido:
                            t_hello = ticks_ms() - HELLO_CADA_MS
                        pedido = ''
                    elif len(pedido) < 32:
                        pedido += c
            # 2) Handshake periódico (así se reconoce aunque la computadora llegue tarde).
            if ticks_diff(ticks_ms(), t_hello) >= HELLO_CADA_MS:
                escribir(_hello(perdidas))
                t_hello = ticks_ms()
            # 3) Bloques listos. Si el ciclo se atrasó más que el anillo, se salta
            #    hacia adelante y el salto en seq le avisa a la computadora.
            disponibles = _escritas - leidas
            if disponibles > ANILLO - BLOQUE:
                saltar = disponibles - BLOQUE
                perdidas += saltar
                leidas += saltar
            while _escritas - leidas >= BLOQUE:
                lo = 0
                partes = []
                for k in range(BLOQUE):
                    j = (leidas + k) & (ANILLO - 1)
                    partes.append(str(_valores[j]))
                    lo |= _lo[j]
                escribir('ECG:D,%d,%d,%s' % (leidas, lo, ','.join(partes)))
                leidas += BLOQUE
            sleep_ms(5)
    finally:
        timer.deinit()


if __name__ == '__main__':
    ejecutar()
