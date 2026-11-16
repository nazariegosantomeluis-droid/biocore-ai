"""Módulo `onewire` simulado (solo pruebas)."""


class OneWireError(Exception):
    pass


class OneWire:
    def __init__(self, pin):
        self.pin = pin
