"""EDF (European Data Format) file loader for biomedical signals."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple, Any

import numpy as np


def load_edf_file(
    file_path: str,
    channel: int = 0,
    duration: Optional[float] = None
) -> Tuple[np.ndarray, float, Dict[str, Any]]:
    """
    Carga archivos EDF (European Data Format).
    
    Formato estándar para datos clínicos:
    - ECG
    - EEG
    - EMG
    - Respiración
    - etc.
    
    Parameters
    ----------
    file_path : str
        Ruta al archivo .edf
    channel : int
        Índice del canal a cargar
    duration : float, optional
        Duración máxima en segundos
        
    Returns
    -------
    signal : ndarray
        Datos del canal
    fs : float
        Frecuencia de muestreo
    metadata : dict
        Información del archivo
    """
    try:
        import mne
    except ImportError:
        try:
            import pyedflib
            return _load_edf_pyedflib(file_path, channel, duration)
        except ImportError:
            raise ImportError(
                "Se requiere: pip install mne o pip install pyedflib"
            )
    
    raw = mne.io.read_raw_edf(file_path, preload=True, verbose=False)
    
    channels = raw.ch_names
    fs = int(raw.info['sfreq'])
    
    signal = raw.get_data(picks=channel)[0] if hasattr(raw.get_data(picks=channel), '__len__') else raw.get_data(picks=channel)
    
    if duration is not None:
        max_samples = int(duration * fs)
        signal = signal[:max_samples]
    
    metadata = {
        'channels': channels,
        'fs': fs,
        'n_channels': len(channels),
        'selected_channel': channels[channel] if channel < len(channels) else f'CH{channel}',
        'duration': len(signal) / fs
    }
    
    return signal, float(fs), metadata


def _load_edf_pyedflib(
    file_path: str,
    channel: int = 0,
    duration: Optional[float] = None
) -> Tuple[np.ndarray, float, Dict[str, Any]]:
    """Loader alternativo usando pyedflib."""
    import pyedflib
    
    with pyedflib.EdfReader(file_path) as f:
        n_channels = f.signals_in_file
        fs = f.getSampleFrequency(channel)
        
        if duration is not None:
            n_samples = int(duration * fs)
            signal = f.readSignal(channel, 0, n_samples)
        else:
            signal = f.readSignal(channel)
        
        signal = np.array(signal, dtype=np.float32)
        
        channels = [f.getSignalLabel(i) for i in range(n_channels)]
        
        metadata = {
            'channels': channels,
            'fs': fs,
            'n_channels': n_channels,
            'selected_channel': channels[channel] if channel < len(channels) else f'CH{channel}',
            'duration': len(signal) / fs,
            'starttime': f.getStartdatetime()
        }
    
    return signal, float(fs), metadata
