"""Firmware EMG de BIOCORE · ESP32 + MyoWare 2.0 (salida RAW) · MicroPython 1.20 o más nuevo.

Qué hace
  - Muestrea la salida RAW del MyoWare a 1000 Hz con un Timer (ADC de 12 bits: 0 a 4095). RAW es el EMG
    amplificado 200 veces, sin rectificar y centrado en la mitad de la alimentación; el sensor lo filtra de
    20.8 a 498.4 Hz (guía avanzada del MyoWare 2.0). Por eso hacen falta unas 1000 muestras por segundo.
  - Manda bloques de 20 muestras por el mismo USB que usa Thonny, a 115200 baudios:
        BIO:D,<seq>,<v1>,...,<v20>
    seq = índice de la primera muestra (la computadora detecta así las perdidas).
  - Se presenta con BIO:HELLO al arrancar, cada 2 s y cuando la computadora manda BIO?. Así la computadora la
    reconoce sola, sin elegir el puerto a mano. `tarde` cuenta las muestras que el Timer tomó con retraso y
    `perdidas` las que se saltaron porque el ciclo principal se atrasó.

Conexión (ESP32 DevKit V1 y MyoWare 2.0)
    MyoWare +    → 3V3      (a 3.3 V la salida queda dentro del rango del ADC)
    MyoWare −    → GND
    MyoWare RAW  → GPIO34   (ADC1: sigue funcionando aunque se active el Wi-Fi). RAW es un pad de la tarjeta:
                             hay que soldarle un cable.
    MyoWare ENV  sin conectar (es la envolvente; el analizador de BIOCORE necesita la señal cruda)
    Electrodos: MID y END sobre el vientre del músculo, en línea con las fibras; REF en una zona ósea (el codo).

Cargar: en Thonny, guarda este archivo en la placa como main.py, cierra Thonny y presiona EN. Thonny detiene el
programa al conectarse: con Thonny abierto, la computadora verá '>>>' en vez de tramas BIO.

Seguridad: con una persona conectada a los electrodos, la computadora va con batería (sin el cargador conectado a
la pared). Esto es material educativo, no un dispositivo médico.
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
FS = 1000                 # Hz; la computadora lo lee del HELLO
PERIODO_MS = 1            # 1000 / FS
BLOQUE = 20               # muestras por línea (50 líneas por segundo, ~40 % de 115200 baudios)
ANILLO = 1024             # potencia de 2: ~1 s de colchón si el ciclo principal se atrasa
PIN_EMG = 34
GANANCIA = 200            # la de la salida RAW del MyoWare 2.0, fija (guía avanzada). Con ella la computadora
                          # estima los mV en la piel.
HELLO_CADA_MS = 2000
TIMER_ID = 0

DETENER = False           # las pruebas lo ponen en True para salir del ciclo
ENTRADA = SALIDA = None   # en la computadora, las pruebas conectan aquí una terminal simulada

_valores = array('H', [0] * ANILLO)
_escritas = 0
_tarde = 0
_ultimo_us = 0
_adc = None


def _muestrear(_t):
    """Corre 1000 veces por segundo (Timer). Sin crear objetos nuevos."""
    global _escritas, _tarde, _ultimo_us
    ahora = ticks_us()
    if _ultimo_us and ticks_diff(ahora, _ultimo_us) > 1500:    # llegó 1.5 periodos tarde
        _tarde += 1
    _ultimo_us = ahora
    _valores[_escritas & (ANILLO - 1)] = _adc.read_u16() >> 4  # 0 a 4095
    _escritas += 1


def _hello(perdidas):
    return ('BIO:HELLO,sensor=emg,fw=%s,fs=%d,ch=EMG,unit=adc,bits=12,vref=3.3,gain=%d,blk=%d,sim=0,'
            'tarde=%d,perdidas=%d' % (FW, FS, GANANCIA, BLOQUE, _tarde, perdidas))


def ejecutar(ciclos=None):
    global _adc, _escritas, _tarde, _ultimo_us
    _adc = ADC(Pin(PIN_EMG))
    _adc.atten(ADC.ATTN_11DB)                                  # rango completo de 0 a ~3.3 V
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
            # 2) Handshake periódico (así se reconoce aunque la computadora llegue tarde).
            if ticks_diff(ticks_ms(), t_hello) >= HELLO_CADA_MS:
                escribir(_hello(perdidas))
                t_hello = ticks_ms()
            # 3) Bloques listos. Si el ciclo se atrasó más que el anillo, se salta hacia adelante y el salto en seq
            #    le avisa a la computadora.
            disponibles = _escritas - leidas
            if disponibles > ANILLO - BLOQUE:
                saltar = disponibles - BLOQUE
                perdidas += saltar
                leidas += saltar
            while _escritas - leidas >= BLOQUE:
                partes = []
                for k in range(BLOQUE):
                    partes.append(str(_valores[(leidas + k) & (ANILLO - 1)]))
                escribir('BIO:D,%d,%s' % (leidas, ','.join(partes)))
                leidas += BLOQUE
            sleep_ms(2)
    finally:
        timer.deinit()


if __name__ == '__main__':
    ejecutar()
