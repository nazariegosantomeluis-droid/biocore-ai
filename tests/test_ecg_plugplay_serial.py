"""Pruebas por un puerto serial de verdad (pseudo-terminal), solo en Linux y Mac.

Aquí el servicio usa pyserial igual que con la placa real; el otro extremo
del puerto es el simulador o el propio firmware de MicroPython corriendo en la
computadora con `machine` simulado.
"""

import importlib.util
import os
import sys
import threading
import time
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip('serial')
pty = pytest.importorskip('pty')
if sys.platform.startswith('win'):
    pytest.skip('los pseudo-terminales no existen en Windows', allow_module_level=True)

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from hardware.ecg_plugplay import (AcquisitionConfig, ConnectionState, ECGAcquisitionService, PortError, PortInfo,
                                   SimulatedECGDevice)
from hardware.ecg_plugplay.simulator import PtyECGDevice, beats_to_mv, mv_to_counts
from hardware.ecg_plugplay.transport import SerialTransport

CP2102 = dict(vid=0x10C4, pid=0xEA60)


class Registro:
    def __init__(self):
        self.estados, self.resultados, self.avisos = [], [], []
        self.lock = threading.RLock()

    def estado(self, e):
        with self.lock:
            self.estados.append(e)

    def resultado(self, r):
        with self.lock:
            self.resultados.append(r)

    def aviso(self, a):
        with self.lock:
            self.avisos.append(a)

    def esperar(self, condicion, timeout):
        fin = time.monotonic() + timeout
        while time.monotonic() < fin:
            with self.lock:
                if condicion(self):
                    return True
            time.sleep(0.02)
        return False


def _servicio(puertos, config=None, fabrica=None, analizador=None):
    reg = Registro()
    svc = ECGAcquisitionService(config or AcquisitionConfig(), analizador or (lambda w: {'prediction': 'ok'}),
                                on_state=reg.estado, on_result=reg.resultado, on_warning=reg.aviso,
                                list_ports_fn=puertos, transport_factory=fabrica)
    return svc, reg


def test_puerto_real_conecta_y_detecta_el_cable_fuera():
    dispositivo = PtyECGDevice(SimulatedECGDevice(speed=4.0))
    conectado = {'si': True}
    puertos = lambda: [PortInfo(dispositivo.path, 'CP2102 simulado', **CP2102)] if conectado['si'] else []
    svc, reg = _servicio(puertos)
    with svc:
        assert svc.wait_for(ConnectionState.CONNECTED, 6.0)
        assert reg.esperar(lambda r: sum(x.valid for x in r.resultados) >= 2, 8.0)
        t0 = time.time()
        conectado['si'] = False
        dispositivo.close()                                  # «se jala el cable»
        assert reg.esperar(lambda r: any(e.state == ConnectionState.SEARCHING and e.time > t0
                                         for e in r.estados), 4.0)
    caida = next(e for e in reg.estados if e.state == ConnectionState.DISCONNECTED)
    assert caida.time - t0 < 2.5 and 'Puerto cerrado' in caida.message
    # Llegó por un puerto serial de verdad, pero la placa se declaró simulador (sim=1 en el HELLO):
    # nunca se presenta como sensor real.
    assert all(x.window.provenance == 'SIMULACION' for x in reg.resultados)
    conexion = next(e for e in reg.estados if e.state == ConnectionState.CONNECTED)
    assert 'SIMULACIÓN, no es un sensor' in conexion.message


def test_nunca_abre_un_puerto_bluetooth():
    dispositivo = PtyECGDevice(SimulatedECGDevice(speed=4.0))
    abiertos = []
    config = AcquisitionConfig()

    def fabrica(puerto):
        abiertos.append(puerto.device)
        return SerialTransport(puerto, config)

    puertos = lambda: [PortInfo('/dev/rfcomm0', 'Bluetooth SPP', hwid='BTHENUM\\{1101}'),
                       PortInfo(dispositivo.path, 'CP2102 simulado', **CP2102)]
    svc, reg = _servicio(puertos, config, fabrica)
    try:
        with svc:
            assert svc.wait_for(ConnectionState.CONNECTED, 6.0)
    finally:
        dispositivo.close()
    assert abiertos == [dispositivo.path]


def test_puerto_ocupado_avisa_una_vez_y_reintenta_solo():
    dispositivo = PtyECGDevice(SimulatedECGDevice(speed=4.0))
    config = AcquisitionConfig(busy_retry_s=0.3)
    intentos = {'n': 0}

    def fabrica(puerto):
        intentos['n'] += 1
        if intentos['n'] <= 3:                       # Thonny lo tiene abierto las primeras veces
            raise PortError('ocupado', puerto.device, f'{puerto.device} está ocupado por otro programa (Thonny).')
        return SerialTransport(puerto, config)

    puertos = lambda: [PortInfo(dispositivo.path, 'CP2102 simulado', **CP2102)]
    svc, reg = _servicio(puertos, config, fabrica)
    try:
        with svc:
            assert svc.wait_for(ConnectionState.CONNECTED, 6.0)
    finally:
        dispositivo.close()
    assert sum('ocupado' in a for a in reg.avisos) == 1 and intentos['n'] == 4


class PlacaEnREPL:
    """ESP32 con MicroPython parado en '>>>'. Con Ctrl-D arranca el firmware de ECG."""

    def __init__(self):
        self.master, slave = pty.openpty()
        import tty
        tty.setraw(slave)
        os.set_blocking(self.master, False)
        self.path, self._slave = os.ttyname(slave), slave
        self.ecg = None
        self._stop = threading.Event()
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        import select
        ultimo = 0.0
        while not self._stop.is_set():
            listo, _, _ = select.select([self.master], [], [], 0.01)
            try:
                if listo:
                    datos = os.read(self.master, 256)
                    if b'\x04' in datos and self.ecg is None:
                        self.ecg = SimulatedECGDevice(speed=4.0)
                    elif self.ecg is not None:
                        self.ecg.handle_input(datos)
                if self.ecg is None and time.monotonic() - ultimo > 0.3:
                    os.write(self.master, b'>>> \r\n')
                    ultimo = time.monotonic()
                elif self.ecg is not None:
                    lineas = self.ecg.lines_due()
                    if lineas:
                        os.write(self.master, ('\n'.join(lineas) + '\n').encode())
            except (BlockingIOError, OSError):
                pass

    def close(self):
        self._stop.set()
        time.sleep(0.05)
        for fd in (self.master, self._slave):
            try:
                os.close(fd)
            except OSError:
                pass


def test_micropython_en_espera_se_explica_y_opcionalmente_se_despierta():
    placa = PlacaEnREPL()
    puertos = lambda: [PortInfo(placa.path, 'CP2102 simulado', **CP2102)]
    try:
        svc, reg = _servicio(puertos, AcquisitionConfig(probe_timeout_s=1.0))
        with svc:
            assert reg.esperar(lambda r: any('>>>' in a for a in r.avisos), 5.0)
        assert placa.ecg is None                     # por defecto no se toca la placa
        svc, reg = _servicio(puertos, AcquisitionConfig(probe_timeout_s=1.0, wake_micropython=True))
        with svc:
            assert svc.wait_for(ConnectionState.CONNECTED, 8.0)
    finally:
        placa.close()
    assert placa.ecg is not None


# ------------------------------------------------------------------ firmware de MicroPython
class Terminal:
    """Extremo de la placa en el pseudo-terminal: lo que el firmware ve como sys.stdin/sys.stdout."""

    def __init__(self, fd):
        self.fd = fd

    def fileno(self):
        return self.fd

    def read(self, n=1):
        try:
            return os.read(self.fd, n).decode('utf-8', 'replace')
        except OSError:
            return ''

    def write(self, texto):
        try:
            os.write(self.fd, texto.encode())
        except (BlockingIOError, OSError):
            pass                                     # sin lector, como un UART real


RUTA_FIRMWARE = RAIZ / 'hardware' / 'ecg_plugplay' / 'firmware' / 'main.py'
FALSOS = str(RAIZ / 'tests' / 'fakes_micropython')


def _cargar_firmware():
    """Carga el firmware con `machine` y `micropython` simulados; se deshace con _descargar_firmware()."""
    sys.path.insert(0, FALSOS)
    for nombre in ('machine', 'micropython'):
        sys.modules.pop(nombre, None)
    spec = importlib.util.spec_from_file_location('firmware_ecg_ad8232', RUTA_FIRMWARE)
    fw = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fw)
    import machine
    return fw, machine


def _descargar_firmware():
    while FALSOS in sys.path:
        sys.path.remove(FALSOS)
    for nombre in ('machine', 'micropython'):
        sys.modules.pop(nombre, None)


def test_firmware_de_la_esp32_de_punta_a_punta():
    fw, machine = _cargar_firmware()
    t0 = time.monotonic()
    rr = 60.0 / 72.0

    def adc():                                       # ECG sintético de 72 lpm en la entrada del ADC
        t = time.monotonic() - t0
        k = np.arange(int(t / rr) - 1, int(t / rr) + 2)
        return int(mv_to_counts(beats_to_mv(np.array([t]), 0.35 + k * rr))[0])

    machine.ADC.fuente = adc
    machine.Pin.valores = {35: 0, 32: 0}
    master, slave = pty.openpty()
    import tty
    tty.setraw(slave)
    os.set_blocking(master, False)
    fw.ENTRADA = fw.SALIDA = Terminal(master)
    fw.DETENER = False
    hilo = threading.Thread(target=fw.ejecutar, daemon=True)
    hilo.start()

    puertos = lambda: [PortInfo(os.ttyname(slave), 'CP2102 simulado', **CP2102)]
    svc, reg = _servicio(puertos)
    try:
        with svc:
            assert svc.wait_for(ConnectionState.CONNECTED, 6.0)
            assert reg.esperar(lambda r: any(x.valid for x in r.resultados), 9.0)
            dispositivo = svc.snapshot()['device']
            buena_procedencia = svc.snapshot()['provenance']
            machine.Pin.valores[35] = 1                      # se despega un electrodo (LO+)
            n = len(reg.resultados)
            assert reg.esperar(lambda r: any(not x.valid for x in r.resultados[n:]), 6.0)
    finally:
        fw.DETENER = True
        hilo.join(2.0)
        for fd in (master, slave):
            os.close(fd)
        _descargar_firmware()
    assert dispositivo['fw'] == '1.0' and dispositivo['fs'] == '250' and dispositivo['blk'] == '10'
    assert buena_procedencia == 'SENSOR_REAL'          # el firmware real no se declara simulador
    buena = next(x for x in reg.resultados if x.valid)
    assert buena.window.model_input.shape == (1, 1000) and buena.window.quality.missing == 0
    mala = next(x for x in reg.resultados[n:] if not x.valid)
    assert 'electrodo suelto' in mala.reasons[0]
