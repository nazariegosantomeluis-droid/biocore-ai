"""CSV and text file loaders for biomedical signals."""

from __future__ import annotations

from typing import Dict, Optional, Tuple, Any

import numpy as np


def load_csv_signal(
    file_path: str,
    signal_column: int | str = 0,
    fs: Optional[float] = None,
    time_column: Optional[int | str] = None,
    skip_rows: int = 0,
    delimiter: str = ','
) -> Tuple[np.ndarray, float, Dict[str, Any]]:
    """
    Cargador flexible para archivos CSV con biosignals.
    
    Soporta múltiples formatos:
    - CSV simple: [valor1, valor2, ...]
    - CSV con timestamp: [timestamp, valor]
    - CSV multicanal: [ECG, PPG, SpO2]
    
    Parameters
    ----------
    file_path : str
        Ruta al archivo CSV
    signal_column : int or str
        Columna de señal (índice o nombre)
    fs : float, optional
        Frecuencia de muestreo. Si no, se estima del tiempo
    time_column : int or str, optional
        Columna de tiempo para estimar fs
    skip_rows : int
        Filas a saltar (headers)
    delimiter : str
        Delimitador CSV
        
    Returns
    -------
    signal : ndarray
        Datos de biosignal
    fs : float
        Frecuencia de muestreo
    metadata : dict
        Información del archivo
    """
    data = np.genfromtxt(
        file_path,
        delimiter=delimiter,
        skip_header=skip_rows,
        dtype=float,
        filling_values=np.nan
    )
    
    if data.ndim == 1:
        signal = data
    else:
        if isinstance(signal_column, str):
            signal_column = 0
        signal = data[:, signal_column]
    
    if fs is None:
        if time_column is not None:
            if data.ndim > 1:
                time_col = data[:, time_column] if isinstance(time_column, int) else data[:, 0]
            else:
                time_col = data
            if len(time_col) > 1:
                fs = 1.0 / np.mean(np.diff(time_col))
            else:
                fs = 250.0
        else:
            fs = 250.0
    
    signal = signal[~np.isnan(signal)]
    
    metadata = {
        'file_path': file_path,
        'fs': fs,
        'signal_column': signal_column,
        'delimiter': delimiter,
        'source': 'CSV',
        'duration': len(signal) / fs
    }
    
    return signal, float(fs), metadata


def load_wearable_data(
    file_path: str,
    signal_type: str = 'heart_rate',
    **kwargs
) -> Tuple[np.ndarray, float, Dict[str, Any]]:
    """
    Cargador para datos de wearables (smartwatch, fitness tracker).
    
    Soporta:
    - Fitbit (JSON export)
    - Apple Watch (CSV export)
    - Garmin (CSV export)
    - Genérico JSON
    
    Parameters
    ----------
    file_path : str
        Ruta al archivo de wearable
    signal_type : str
        Tipo de señal: 'heart_rate', 'steps', 'sleep', etc.
        
    Returns
    -------
    signal : ndarray
        Serie temporal del wearable
    fs : float
        Frecuencia efectiva de muestreo
    metadata : dict
        Información del dispositivo
    """
    import json
    
    if file_path.endswith('.json'):
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        if signal_type in data:
            values = data[signal_type]
            if isinstance(values, dict):
                signal = np.array(list(values.values()), dtype=float)
                timestamps = np.array(list(values.keys()), dtype=float)
            else:
                signal = np.array(values, dtype=float)
                timestamps = np.arange(len(signal))
        else:
            signal = np.array(data.get('values', []), dtype=float)
            timestamps = np.arange(len(signal))
        
        fs = 1.0 / np.mean(np.diff(timestamps)) if len(timestamps) > 1 else 1.0 / 60.0
        
    elif file_path.endswith('.csv'):
        signal, fs, _ = load_csv_signal(file_path, **kwargs)
        timestamps = np.arange(len(signal)) / fs
    else:
        raise ValueError("Formato wearable no soportado. Usa JSON o CSV.")
    
    metadata = {
        'source': 'wearable',
        'signal_type': signal_type,
        'fs': fs,
        'duration': len(signal) / fs if fs > 0 else len(signal)
    }
    
    return signal, fs, metadata
