"""WFDB (PhysioNet) record loader for MIT-BIH and other databases."""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple, Any

import numpy as np


def load_wfdb_record(
    record_path: str,
    lead: int = 0,
    duration: Optional[float] = None
) -> Tuple[np.ndarray, float, Dict[str, Any]]:
    """
    Carga registros WFDB desde PhysioNet (MIT-BIH, etc).
    """
    try:
        import wfdb
    except ImportError:
        raise ImportError(
            "wfdb no está instalado. Instala con: pip install wfdb"
        )

    record_name = record_path
    pn_dir = None
    normalized_path = record_path.replace('\\', '/').strip()
    if '/' in normalized_path:
        parts = normalized_path.split('/')
        if len(parts) == 2:
            pn_dir, record_name = parts
        elif len(parts) > 2:
            pn_dir = parts[-2]
            record_name = parts[-1]

    if pn_dir and pn_dir.lower() == 'mitdb':
        pn_dir = 'mitdb'

    try:
        if os.path.exists(record_path) or os.path.exists(f"{record_path}.hea"):
            record = wfdb.rdrecord(record_path)
        elif pn_dir:
            record = wfdb.rdrecord(record_name, pn_dir=pn_dir)
        else:
            record = wfdb.rdrecord(record_name, pn_dir='mitdb')
    except Exception as exc:
        error_message = str(exc)
        if '404' in error_message or 'Not Found' in error_message:
            raise RuntimeError(
                f"MIT-BIH record '{record_path}' no encontrado en PhysioNet. "
                "Asegúrate de tener acceso a internet o utiliza un registro de demo."
            )
        raise RuntimeError(f"No se pudo cargar el registro WFDB '{record_path}': {exc}")

    signal = record.p_signal[:, lead]
    fs = record.fs

    if duration is not None:
        max_samples = int(duration * fs)
        signal = signal[:max_samples]

    metadata = {
        'record_name': record.record_name,
        'fs': fs,
        'n_sig': record.n_sig,
        'sig_name': record.sig_name[lead] if lead < len(record.sig_name) else f'Lead_{lead}',
        'channels': record.sig_name,
        'comments': record.comments if hasattr(record, 'comments') else []
    }

    if hasattr(record, 'ann_samp') and hasattr(record, 'symbol'):
        metadata['annotations'] = {
            'samples': record.ann_samp.tolist() if hasattr(record.ann_samp, 'tolist') else record.ann_samp,
            'symbols': record.symbol if isinstance(record.symbol, list) else list(record.symbol)
        }

    return signal, fs, metadata


def get_mitbih_records() -> List[str]:
    """
    Retorna lista de registros disponibles en MIT-BIH Database.
    
    Returns
    -------
    list
        IDs de registros (ej: ['100', '101', ...])
    """
    return [
        '100', '101', '102', '103', '104', '105', '106', '107', '108', '109',
        '111', '112', '113', '114', '115', '116', '117', '118', '119',
        '121', '122', '123', '124',
        '200', '201', '202', '203', '205', '207', '208', '209', '210',
        '212', '213', '214', '215', '217', '219',
        '220', '221', '222', '223', '228',
    ]


def load_mitbih_record(
    record_id: str,
    lead: int = 0
) -> Tuple[np.ndarray, float, Dict[str, Any]]:
    """
    Cargador conveniente para MIT-BIH Database.
    """
    return load_wfdb_record(record_id, lead=lead)


def download_mitbih_record(record_id: str, output_dir: str = 'datasets/mitbih') -> str:
    """
    Descarga un registro de MIT-BIH Database.
    
    Requiere internet la primera vez.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        import wfdb
        wfdb.dl_database('mitdb', dl_dir=output_dir)
        return f"{output_dir}/mitdb/{record_id}"
    except Exception as e:
        raise RuntimeError(f"No se pudo descargar MIT-BIH: {e}")
