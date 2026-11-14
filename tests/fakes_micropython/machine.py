"""Módulo `machine` simulado para correr el firmware en la computadora (solo pruebas)."""

import threading
import time


class Pin:
    IN, OUT = 0, 1
    valores = {}                      # número de pin → lo que lee value()

    def __init__(self, n, mode=None, pull=None):
        self.n = n

    def value(self, v=None):
        if v is None:
            return Pin.valores.get(self.n, 0)
        Pin.valores[self.n] = v


class ADC:
    ATTN_11DB = 3
    fuente = None                     # función sin argumentos que devuelve cuentas de 12 bits

    def __init__(self, pin):
        self.pin = pin

    def atten(self, a):
        pass

    def read_u16(self):
        v = ADC.fuente() if ADC.fuente else 2048
        return (int(v) & 0xFFF) << 4


class Timer:
    PERIODIC = 1

    def __init__(self, timer_id):
        self._stop = threading.Event()
        self._thread = None

    def init(self, period, mode, callback):
        def correr():
            siguiente = time.monotonic()
            while not self._stop.is_set():
                siguiente += period / 1000.0
                callback(self)
                espera = siguiente - time.monotonic()
                if espera > 0:
                    time.sleep(espera)

        self._thread = threading.Thread(target=correr, daemon=True)
        self._thread.start()

    def deinit(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(1.0)
