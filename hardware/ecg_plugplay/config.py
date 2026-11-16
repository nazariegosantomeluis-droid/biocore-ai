"""Configuración del módulo Plug & Play de ECG.

Dos grupos de parámetros:

- `AcquisitionConfig`: lo que define la adquisición (frecuencia, ventana,
  solape, puerto serial, filtros) y el formato que espera el modelo.
- `QualityHeuristics`: umbrales de ingeniería para descartar ventanas.
  Son heurísticos (no salen de un criterio clínico citado) y por eso viven
  juntos y con nombre propio, como los `HEURISTICS` del Respiratory Lab.

Los valores de la electrónica (bits del ADC, referencia, ganancia) son los
de una ESP32 con un AD8232; si el firmware manda su `ECG:HELLO`, los valores
del dispositivo reemplazan a estos. La ganancia de 1100 es un SUPUESTO: es
la de la configuración «monitor cardiaco» de la hoja de datos (`AD8232_GAIN_SOURCE`);
la de cada tarjeta depende de sus resistencias, así que los mV que salen de
aquí son aproximados, sin calibrar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple

AD8232_GAIN_SOURCE = (
    'Analog Devices, AD8232 Data Sheet, Rev. D (3/2020, D10866-3/20(D)): configuración de monitor '
    'cardiaco (Figura 66), etapa de op amp con ganancia 11 para una ganancia total del sistema de 1100, '
    'pasa-altas de dos polos a 0.5 Hz y pasa-bajas de dos polos a 40 Hz.'
)

# Chips USB-serial de las placas ESP32/Arduino más comunes: (VID, PID, nombre).
# PID None = cualquier producto de ese fabricante. Sirven para decidir qué
# puertos vale la pena sondear; la identificación final es el handshake.
KNOWN_USB_IDS: Tuple[Tuple[int, Optional[int], str], ...] = (
    (0x10C4, 0xEA60, 'Silicon Labs CP210x'),
    (0x1A86, 0x7523, 'WCH CH340'),
    (0x1A86, 0x55D4, 'WCH CH9102'),
    (0x1A86, None, 'WCH CH34x/CH910x'),
    (0x303A, None, 'Espressif USB nativo'),
    (0x0403, None, 'FTDI'),
    (0x2341, None, 'Arduino'),
)


@dataclass
class QualityHeuristics:
    """Umbrales para aceptar o descartar una ventana (heurísticos)."""

    # Fracción máxima de muestras en los límites del ADC antes de descartar.
    max_saturated_fraction: float = 0.01
    # Fracción máxima de muestras con electrodo suelto (LO+/LO− del AD8232).
    max_leadoff_fraction: float = 0.0
    # Pico a pico mínimo de la señal filtrada; por debajo es una línea plana.
    min_peak_to_peak_mv: float = 0.05
    # Tras una interrupción el filtro se reinicia; estas muestras no cuentan.
    settle_s: float = 0.5
    # Cuentas desde 0 o desde el máximo que se consideran saturación.
    saturation_margin_counts: int = 8
    # Una racha de saturación más larga que esto reinicia el filtro al acabar.
    saturation_reset_s: float = 0.1
    # Huecos de hasta este número de muestras se interpolan (y se cuentan).
    max_interp_gap: int = 2


@dataclass
class AcquisitionConfig:
    """Parámetros de adquisición, ventana y conexión."""

    # --- Muestreo y ventana que espera el modelo
    fs: float = 250.0
    window_size: int = 1000                  # 4 s a 250 Hz
    overlap: float = 0.5                     # 50 %: una ventana nueva cada 2 s
    model_input_shape: Tuple[int, ...] = (1, 1000)
    normalization: str = 'minmax'            # 'minmax' (0 a 1) o 'robust' (percentiles 1 y 99)

    # --- Puerto serial
    baudrate: int = 115200
    port: Optional[str] = None               # fija un puerto (p. ej. 'COM3') y se salta el escaneo
    scan_interval_s: float = 1.0             # cada cuánto se vuelven a revisar los puertos
    probe_timeout_s: float = 2.5             # cuánto se espera el handshake al sondear un puerto
    data_timeout_s: float = 2.0              # sin tramas válidas por más de esto = desconexión
    busy_retry_s: float = 5.0                # espera antes de reintentar un puerto ocupado
    not_ecg_retry_s: float = 10.0            # espera antes de re-sondear un puerto que no es de ECG
    accept_legacy: bool = False              # acepta el formato viejo 'ts,valor' (sin handshake)
    wake_micropython: bool = False           # si ve '>>>', manda Ctrl-D para arrancar main.py
    assert_dtr: bool = False                 # True solo para placas con USB nativo que lo necesiten

    # --- Electrónica por defecto (el ECG:HELLO del firmware la reemplaza)
    adc_bits: int = 12
    adc_vref: float = 3.3
    gain: float = 1100.0                     # supuesto: ver AD8232_GAIN_SOURCE (sin calibrar)

    # --- Filtro en línea (se aplica a la señal cruda del ADC)
    bandpass_hz: Tuple[float, float] = (0.5, 40.0)
    bandpass_order: int = 2
    notch_hz: Optional[float] = 60.0         # red eléctrica en México; 50 en Europa; None lo apaga
    notch_q: float = 30.0

    # --- Interfaz
    display_seconds: float = 10.0            # cuánta señal guarda snapshot() para graficar

    heuristics: QualityHeuristics = field(default_factory=QualityHeuristics)

    @property
    def hop(self) -> int:
        """Muestras entre el inicio de una ventana y el de la siguiente."""
        return max(1, int(round(self.window_size * (1.0 - self.overlap))))

    def check(self) -> None:
        """Lanza ValueError con un mensaje claro si algo no cuadra."""
        nyquist = self.fs / 2.0
        if self.window_size <= 0:
            raise ValueError('window_size debe ser mayor que 0.')
        if not 0.0 <= self.overlap < 1.0:
            raise ValueError('overlap va de 0 (sin solape) a menos de 1.')
        n = 1
        for d in self.model_input_shape:
            n *= int(d)
        if n != self.window_size:
            raise ValueError(f'model_input_shape {self.model_input_shape} no tiene {self.window_size} elementos.')
        low, high = self.bandpass_hz
        if not 0.0 < low < high < nyquist:
            raise ValueError(f'El pasa-banda {self.bandpass_hz} Hz debe quedar entre 0 y {nyquist:g} Hz.')
        if self.notch_hz is not None and not 0.0 < self.notch_hz < nyquist:
            raise ValueError(f'El notch de {self.notch_hz} Hz debe quedar por debajo de {nyquist:g} Hz.')
        if self.normalization not in ('minmax', 'robust'):
            raise ValueError("normalization debe ser 'minmax' o 'robust'.")
        if self.data_timeout_s <= 0 or self.probe_timeout_s <= 0:
            raise ValueError('Los tiempos de espera deben ser positivos.')
