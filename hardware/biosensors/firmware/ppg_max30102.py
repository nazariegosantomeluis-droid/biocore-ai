"""Firmware de pulso por luz de BIOCORE · ESP32 + MAX30102 · MicroPython 1.20 o más nuevo.

Qué hace
  - Configura el MAX30102 en modo SpO2 (luz roja e infrarroja) con los registros de su hoja de datos: 100 muestras
    por segundo, pulso de 411 µs (18 bits), rango del ADC de 4096 nA y 7.2 mA en cada LED.
  - Cada 10 ms lee por I2C las muestras nuevas de la memoria FIFO del sensor (32 lugares) y manda bloques de 10:
        BIO:D,<seq>,<rojo>;<ir>,...
    Son cuentas del ADC: la luz que llega al sensor (baja en cada latido, porque entra más sangre al dedo).
    seq = índice de la primera muestra. Si la FIFO se llenó porque el ciclo se atrasó, el sensor cuenta las muestras
    que tiró y seq salta lo mismo: así la computadora sabe cuántas se perdieron.
  - Se presenta con BIO:HELLO al arrancar, cada 2 s y cuando la computadora manda BIO?.
  - Si no encuentra el sensor, lo dice con BIO:E (la app lo muestra) y lo vuelve a buscar cada 2 s.

Conexión (ESP32 DevKit V1 y un módulo MAX30102)
    VIN → 3V3
    GND → GND
    SDA → GPIO21
    SCL → GPIO22
    INT sin conectar (el firmware le pregunta al sensor cada 10 ms)
    El dedo: la yema sobre las dos luces, sin apretar, la mano quieta y tapada de la luz ambiente.

Cargar: en Thonny, guarda este archivo en la placa como main.py, cierra Thonny y presiona EN. Thonny detiene el
programa al conectarse: con Thonny abierto, la computadora verá '>>>' en vez de tramas BIO.

Esto es material educativo, no un dispositivo médico: no mide la saturación de oxígeno (para eso hace falta una
curva de calibración que este sensor no trae).
"""

import sys
import time

try:
    import select
except ImportError:  # algunos puertos viejos de MicroPython
    import uselect as select

from machine import Pin

try:
    from machine import SoftI2C as BusI2C
except ImportError:  # MicroPython viejo: I2C por software con el nombre de siempre
    from machine import I2C as BusI2C

try:
    ticks_ms, ticks_diff, sleep_ms = time.ticks_ms, time.ticks_diff, time.sleep_ms
except AttributeError:  # CPython: permite probar este mismo archivo en la computadora
    ticks_ms = lambda: int(time.monotonic() * 1000)
    ticks_diff = lambda a, b: a - b
    sleep_ms = lambda ms: time.sleep(ms / 1000)

FW = '1.0'
FS = 100                  # muestras por segundo (registro SPO2_CFG); la computadora lo lee del HELLO
BLOQUE = 10               # muestras por línea (10 líneas por segundo)
PIN_SDA, PIN_SCL = 21, 22
I2C_HZ = 400000
DIRECCION = 0x57
LED = 0x24                # 36 pasos de 0.2 mA = 7.2 mA en cada LED
HELLO_CADA_MS = 2000
REINTENTO_MS = 2000

# Registros (hoja de datos del MAX30102)
REG_FIFO_WR = 0x04        # puntero de escritura de la FIFO
REG_OVF = 0x05            # muestras perdidas con la FIFO llena (se borra al leer una muestra)
REG_FIFO_RD = 0x06        # puntero de lectura de la FIFO
REG_FIFO_DATOS = 0x07     # 6 bytes por muestra: rojo (3) e infrarrojo (3)
REG_FIFO_CFG = 0x08
REG_MODO = 0x09
REG_SPO2_CFG = 0x0A
REG_LED_ROJO = 0x0C
REG_LED_IR = 0x0D
REG_PART_ID = 0xFF
PART_ID = 0x15

FIFO_CFG = 0x1F           # sin promediar (bits 7:5 = 000), FIFO circular (bit 4 = 1), aviso de llena en 15
SPO2_CFG = 0x27           # rango 4096 nA (bits 6:5 = 01), 100 muestras/s (bits 4:2 = 001), 411 µs = 18 bits (1:0 = 11)
MODO_SPO2 = 0x03          # rojo e infrarrojo
MODO_REINICIO = 0x40      # bit 6: reinicia el sensor y se borra solo
MASCARA = 0x3FFFF         # 18 bits: el bit más alto de cada dato queda en el bit 17
FIFO_LUGARES = 32

DETENER = False           # las pruebas lo ponen en True para salir del ciclo
ENTRADA = SALIDA = None   # en la computadora, las pruebas conectan aquí una terminal simulada


class SensorAusente(Exception):
    pass


def _leer(i2c, reg, n=1):
    return i2c.readfrom_mem(DIRECCION, reg, n)


def _escribir(i2c, reg, valor):
    i2c.writeto_mem(DIRECCION, reg, bytes([valor]))


def configurar(i2c):
    try:
        presentes = i2c.scan()
    except OSError:
        presentes = []
    if DIRECCION not in presentes:
        raise SensorAusente('No se encontró el MAX30102 en el bus I2C (SDA=GPIO21, SCL=GPIO22): revisa VIN, GND, SDA '
                            'y SCL.')
    parte = _leer(i2c, REG_PART_ID)[0]
    if parte != PART_ID:
        raise SensorAusente('En la dirección 0x57 hay otro sensor (PART_ID 0x%02x), no un MAX30102.' % parte)
    _escribir(i2c, REG_MODO, MODO_REINICIO)
    for _ in range(100):
        if not _leer(i2c, REG_MODO)[0] & MODO_REINICIO:
            break
        sleep_ms(1)
    _escribir(i2c, REG_FIFO_CFG, FIFO_CFG)
    _escribir(i2c, REG_SPO2_CFG, SPO2_CFG)
    _escribir(i2c, REG_LED_ROJO, LED)
    _escribir(i2c, REG_LED_IR, LED)
    for reg in (REG_FIFO_WR, REG_OVF, REG_FIFO_RD):
        _escribir(i2c, reg, 0)
    _escribir(i2c, REG_MODO, MODO_SPO2)


def _hello(perdidas):
    return ('BIO:HELLO,sensor=ppg,fw=%s,fs=%d,ch=ROJO;IR,unit=cuentas,bits=18,led_ma=%.1f,blk=%d,sim=0,perdidas=%d'
            % (FW, FS, LED * 0.2, BLOQUE, perdidas))


def ejecutar(ciclos=None):
    i2c = BusI2C(scl=Pin(PIN_SCL), sda=Pin(PIN_SDA), freq=I2C_HZ)
    salida = SALIDA or sys.stdout
    entrada = ENTRADA or sys.stdin
    try:
        poll = select.poll()
        poll.register(entrada, select.POLLIN)
    except Exception:
        poll = None                                            # sin entrada: el HELLO periódico basta

    def escribir(texto):
        salida.write(texto + '\n')

    seq = 0                   # índice de la primera muestra pendiente
    perdidas = 0
    pendientes = []
    pedido = ''
    listo = False
    t_intento = ticks_ms() - REINTENTO_MS
    escribir(_hello(0))
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
        if ticks_diff(ticks_ms(), t_hello) >= HELLO_CADA_MS:
            escribir(_hello(perdidas))
            t_hello = ticks_ms()
        # 3) Sin sensor: buscarlo cada 2 s y decir por qué no está.
        if not listo:
            if ticks_diff(ticks_ms(), t_intento) >= REINTENTO_MS:
                t_intento = ticks_ms()
                try:
                    configurar(i2c)
                    listo = True
                    pendientes = []
                except SensorAusente as exc:
                    escribir('BIO:E,' + str(exc))
                except OSError as exc:
                    escribir('BIO:E,Falla del bus I2C (%s): revisa SDA y SCL.' % exc)
            sleep_ms(10)
            continue
        # 4) Muestras nuevas en la FIFO.
        try:
            escritura = _leer(i2c, REG_FIFO_WR)[0] & 0x1F
            desbordes = _leer(i2c, REG_OVF)[0] & 0x1F
            lectura = _leer(i2c, REG_FIFO_RD)[0] & 0x1F
            nuevas = (escritura - lectura) & 0x1F
            if desbordes and nuevas == 0:
                nuevas = FIFO_LUGARES                          # llena: los dos punteros coinciden
            datos = _leer(i2c, REG_FIFO_DATOS, 6 * nuevas) if nuevas else b''
        except OSError as exc:
            escribir('BIO:E,Se perdió la comunicación con el MAX30102 (%s): revisa los cables.' % exc)
            listo = False
            continue
        if desbordes:
            # Las que el sensor tiró van antes de las que quedan en la FIFO: se manda lo pendiente y seq salta.
            if pendientes:
                escribir('BIO:D,%d,%s' % (seq, ','.join(pendientes)))
                seq += len(pendientes)
                pendientes = []
            seq += desbordes
            perdidas += desbordes
        for k in range(nuevas):
            b = datos[6 * k:6 * k + 6]
            rojo = ((b[0] << 16) | (b[1] << 8) | b[2]) & MASCARA
            ir = ((b[3] << 16) | (b[4] << 8) | b[5]) & MASCARA
            pendientes.append('%d;%d' % (rojo, ir))
        while len(pendientes) >= BLOQUE:
            escribir('BIO:D,%d,%s' % (seq, ','.join(pendientes[:BLOQUE])))
            seq += BLOQUE
            pendientes = pendientes[BLOQUE:]
        sleep_ms(10)


if __name__ == '__main__':
    ejecutar()
