"""Real biomedical signal loader supporting EDF, WFDB and CSV formats."""

import os
import logging
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd

try:
    import wfdb
except ImportError:
    wfdb = None  # type: ignore

try:
    import pyedflib
except ImportError:
    pyedflib = None  # type: ignore

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = ['.edf', '.csv', '.hea', '.dat']


def _normalize_signal(signal: np.ndarray) -> np.ndarray:
    if signal.dtype.kind in 'iu':
        signal = signal.astype(float)
    if np.max(np.abs(signal)) > 10:
        signal = signal / np.max(np.abs(signal))
    return signal


def _apply_quality_checks(signal: np.ndarray) -> Dict[str, Any]:
    quality = {
        'duration_seconds': None,
        'signal_std': float(np.std(signal)),
        'peak_to_peak': float(np.ptp(signal)),
        'has_nans': bool(np.isnan(signal).any()),
    }
    if signal.size > 1:
        quality['duration_seconds'] = float(signal.size)
    return quality


def normalize_sampling_rate(signal: np.ndarray, original_fs: float, target_fs: float) -> Tuple[np.ndarray, float]:
    """Resample a biomedical signal to the target sampling frequency."""
    from scipy.signal import resample

    if original_fs == target_fs:
        return signal, target_fs

    n_samples = int(signal.shape[0] * target_fs / original_fs)
    resampled = resample(signal, n_samples)
    return resampled, target_fs


def load_edf(path: str, channel: Optional[str] = None) -> Tuple[np.ndarray, float, Dict[str, Any]]:
    if pyedflib is None:
        raise ImportError('pyedflib is required to read EDF files. Instala pyedflib.')

    with pyedflib.EdfReader(path) as reader:
        if channel is None:
            channel = reader.getLabel(0)
        signal = reader.readSignal(reader.getSignalLabels().index(channel))
        fs = reader.getSampleFrequency(reader.getSignalLabels().index(channel))

    signal = _normalize_signal(np.array(signal, dtype=float))
    metadata = {
        'channels': reader.getSignalLabels(),
        'signal_label': channel,
    }
    return signal, float(fs), metadata


def load_wfdb(record_path: str, channel: int = 0) -> Tuple[np.ndarray, float, Dict[str, Any]]:
    if wfdb is None:
        raise ImportError('wfdb is required to read WFDB files. Instala wfdb.')

    record = wfdb.rdrecord(record_path)
    signal = record.p_signal[:, channel]
    fs = record.fs
    metadata = {
        'record_name': record_path,
        'channels': record.sig_name,
    }
    signal = _normalize_signal(signal)
    return signal, float(fs), metadata


def load_csv(path: str, timestamp_column: Optional[str] = None, value_column: Optional[str] = None) -> Tuple[np.ndarray, float, Dict[str, Any]]:
    df = pd.read_csv(path)
    if value_column is None:
        value_column = df.columns[-1]
    values = df[value_column].to_numpy(dtype=float)
    if timestamp_column and timestamp_column in df.columns:
        timestamps = df[timestamp_column].to_numpy(dtype=float)
        if len(timestamps) > 1:
            fs = 1.0 / float(np.median(np.diff(timestamps)))
        else:
            fs = 250.0
    else:
        fs = 250.0

    signal = _normalize_signal(values)
    metadata = {
        'path': path,
        'value_column': value_column,
        'timestamp_column': timestamp_column,
    }
    return signal, float(fs), metadata


def validate_signal(signal: np.ndarray) -> Dict[str, Any]:
    """Validate basic properties of a biomedical signal array."""
    return {
        'shape': signal.shape,
        'dtype': str(signal.dtype),
        'is_finite': bool(np.isfinite(signal).all()),
        'has_nans': bool(np.isnan(signal).any()),
        'min': float(np.min(signal)) if signal.size else None,
        'max': float(np.max(signal)) if signal.size else None,
    }


def assess_signal_quality(signal: np.ndarray, fs: float) -> Dict[str, Any]:
    """Estimate signal quality using simple noise and flatline detection."""
    quality = _apply_quality_checks(signal)
    quality.update({
        'sampling_rate': fs,
        'snr_estimate': float(np.mean(signal) / (np.std(signal) + 1e-9)),
        'flatline_percent': float(np.mean(np.abs(np.diff(signal)) < 1e-4) * 100),
    })
    return quality


def load_biomedical_signal(path: str, **kwargs) -> Tuple[np.ndarray, float, Dict[str, Any]]:
    """Auto-detect and load a biomedical signal from a supported file."""
    extension = os.path.splitext(path)[1].lower()
    if extension == '.edf':
        return load_edf(path, **kwargs)
    if extension in ['.hea', '.dat']:
        return load_wfdb(path, **kwargs)
    if extension == '.csv':
        return load_csv(path, **kwargs)

    raise ValueError(f'Formato no soportado: {extension}')
