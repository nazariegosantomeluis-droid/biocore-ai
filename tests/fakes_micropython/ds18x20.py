"""Módulo `ds18x20` simulado (solo pruebas): una o varias sondas DS18B20 en el bus 1-Wire."""


class DS18X20:
    sondas = []          # ROM de cada sonda presente
    fuente = None        # función sin argumentos que devuelve la temperatura en °C
    falla = None         # excepción que lanza read_temp (cable suelto, error de CRC)

    def __init__(self, bus):
        self.bus = bus
        self._convertida = False

    def scan(self):
        return list(DS18X20.sondas)

    def convert_temp(self):
        self._convertida = True

    def read_temp(self, rom):
        if DS18X20.falla is not None:
            raise DS18X20.falla
        if not self._convertida:
            return 85.0                              # valor de encendido del registro (hoja de datos)
        valor = DS18X20.fuente() if DS18X20.fuente else 25.0
        return round(valor * 16) / 16                # 12 bits: pasos de 0.0625 °C
