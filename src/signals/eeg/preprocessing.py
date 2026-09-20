"""Basic EEG preprocessing for simple clinical-simulated education."""

from typing import Dict, Tuple

import numpy as np
from scipy.signal import butter, filtfilt

# Arco 2C (2026-09-14): nombrados explícitamente -- antes vivían solo como
# defaults posicionales de `preprocess_eeg()`. `spectral_model.py` los
# necesita para calcular la respuesta en magnitud EXACTA de este mismo
# filtro (ver `correct_bandpass_attenuation()` allá) y corregir el sesgo que
# introduce sobre el exponente aperiódico chi -- un consumidor externo que
# solo tuviera acceso a los defaults de la firma de la función no podría
# importarlos sin invocar la función; como constantes, sí. Ningún cambio de
# comportamiento: mismos valores (0.5, 40.0, orden 2) que ya regían.
DEFAULT_LOWCUT_HZ: float = 0.5
DEFAULT_HIGHCUT_HZ: float = 40.0
FILTER_ORDER: int = 2


def preprocess_eeg(
    signal: np.ndarray, fs: float, lowcut: float = DEFAULT_LOWCUT_HZ, highcut: float = DEFAULT_HIGHCUT_HZ
) -> Tuple[np.ndarray, Dict[str, float]]:
    if signal.ndim != 1:
        signal = signal.flatten()

    nyquist = 0.5 * fs
    low = lowcut / nyquist
    high = highcut / nyquist
    b, a = butter(FILTER_ORDER, [low, high], btype='band')
    filtered = filtfilt(b, a, signal)

    metrics = {
        'fs': fs,
        'signal_std': float(np.std(filtered)),
        'duration_sec': len(filtered) / fs,
    }
    return filtered, metrics
