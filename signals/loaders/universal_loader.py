"""Universal biomedical signal loader with automatic format detection and validation."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import numpy as np


class BiomedicalSignalInfo:
    """Metadata container for loaded biomedical signals."""
    
    def __init__(
        self,
        signal: np.ndarray,
        fs: float,
        signal_type: str,
        source_file: str,
        duration: float,
        channels: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.signal = signal
        self.fs = fs
        self.signal_type = signal_type
        self.source_file = source_file
        self.duration = duration
        self.channels = channels or ['CH0']
        self.metadata = metadata or {}
        
    def __repr__(self) -> str:
        return (
            f"BiomedicalSignalInfo("
            f"type={self.signal_type}, "
            f"fs={self.fs}Hz, "
            f"duration={self.duration:.1f}s, "
            f"channels={len(self.channels)})"
        )


def detect_signal_type(file_path: str) -> str:
    """
    Detecta automáticamente el tipo de biosignal basado en extensión y contenido.
    
    Soporta:
    - MIT-BIH: .hea, .dat (WFDB)
    - EDF: .edf
    - CSV: .csv
    - Wearable: .txt, .json
    """
    path = Path(file_path)
    ext = path.suffix.lower()
    
    if ext in ['.hea', '.dat']:
        return 'wfdb'
    elif ext == '.edf':
        return 'edf'
    elif ext == '.csv':
        return 'csv'
    elif ext in ['.txt', '.json']:
        return 'wearable'
    else:
        raise ValueError(f"Formato de archivo no soportado: {ext}")


def validate_signal(signal: np.ndarray, fs: float) -> Dict[str, Any]:
    """
    Valida la integridad de la señal y sus parámetros.
    
    Returns
    -------
    dict
        Reporte de validación con warnings y errores
    """
    report = {
        'valid': True,
        'warnings': [],
        'errors': [],
        'metadata': {
            'length': len(signal),
            'duration': len(signal) / fs if fs > 0 else 0,
            'fs': fs,
            'min': float(np.min(signal)),
            'max': float(np.max(signal)),
            'mean': float(np.mean(signal)),
            'std': float(np.std(signal)),
        }
    }
    
    if fs <= 0:
        report['errors'].append('Frecuencia de muestreo inválida')
        report['valid'] = False
    
    if len(signal) == 0:
        report['errors'].append('Señal vacía')
        report['valid'] = False
    
    if np.isnan(signal).any():
        report['warnings'].append(f'Señal contiene {np.isnan(signal).sum()} valores NaN')
    
    if np.isinf(signal).any():
        report['warnings'].append('Señal contiene valores infinitos')
    
    if len(signal) < fs:
        report['warnings'].append(f'Señal muy corta: {len(signal)/fs:.2f}s')
    
    if report['metadata']['std'] == 0:
        report['warnings'].append('Señal sin varianza (constante)')
    
    return report


def load_biomedical_data(
    file_path: str,
    signal_type: Optional[str] = None,
    **kwargs
) -> BiomedicalSignalInfo:
    """
    Cargador universal para múltiples formatos de biosignales.
    
    Detecta automáticamente el tipo si no se especifica.
    Valida la señal y retorna información detallada.
    
    Parameters
    ----------
    file_path : str
        Ruta al archivo de biosignal
    signal_type : str, optional
        Tipo de archivo: 'wfdb', 'edf', 'csv', 'wearable'
        Si no se especifica, se detecta automáticamente
    **kwargs
        Argumentos adicionales para loaders específicos
        
    Returns
    -------
    BiomedicalSignalInfo
        Objeto con señal, metadatos y validación
        
    Raises
    ------
    FileNotFoundError
        Si el archivo no existe
    ValueError
        Si el formato no es soportado
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Archivo no encontrado: {file_path}")
    
    if signal_type is None:
        signal_type = detect_signal_type(file_path)
    
    if signal_type == 'wfdb':
        from .wfdb_loader import load_wfdb_record
        signal, fs, metadata = load_wfdb_record(file_path, **kwargs)
    elif signal_type == 'edf':
        from .edf_loader import load_edf_file
        signal, fs, metadata = load_edf_file(file_path, **kwargs)
    elif signal_type == 'csv':
        from .csv_loader import load_csv_signal
        signal, fs, metadata = load_csv_signal(file_path, **kwargs)
    elif signal_type == 'wearable':
        from .wearable_loader import load_wearable_data
        signal, fs, metadata = load_wearable_data(file_path, **kwargs)
    else:
        raise ValueError(f"Tipo de señal no soportado: {signal_type}")
    
    duration = len(signal) / fs if fs > 0 else 0
    channels = metadata.get('channels', ['ECG'])
    
    info = BiomedicalSignalInfo(
        signal=signal,
        fs=fs,
        signal_type=signal_type,
        source_file=file_path,
        duration=duration,
        channels=channels,
        metadata=metadata
    )
    
    validation = validate_signal(signal, fs)
    if validation['warnings']:
        info.metadata['validation_warnings'] = validation['warnings']
    if not validation['valid']:
        info.metadata['validation_errors'] = validation['errors']
    
    return info


def normalize_amplitude(signal: np.ndarray, target_unit: str = 'mV') -> np.ndarray:
    """
    Normaliza la amplitud de la señal a unidades estándar.
    
    Parameters
    ----------
    signal : ndarray
        Señal a normalizar
    target_unit : str
        Unidad objetivo: 'mV', 'uV', 'V'
        
    Returns
    -------
    ndarray
        Señal normalizada
    """
    if target_unit == 'mV':
        if np.max(np.abs(signal)) > 50:
            return signal / 1000
    return signal


def detect_sampling_rate(signal: np.ndarray, time_axis: Optional[np.ndarray] = None) -> float:
    """
    Estima la frecuencia de muestreo si no está disponible.
    
    Útil para archivos CSV sin metadata.
    """
    if time_axis is not None and len(time_axis) > 1:
        return 1.0 / np.mean(np.diff(time_axis))
    return 250.0
