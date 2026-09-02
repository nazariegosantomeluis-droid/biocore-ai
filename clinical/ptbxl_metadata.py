"""Acceso compartido a la metadata de PTB-XL (`ptbxl_database.csv`).

Usado por DOS entregables separados que comparten el CSV pero no la
selección de registros:
- El loader vivo del ECG Monitor (`app/main.py::_ecg_get_ptbxl_records()`,
  UI) -- navegación de unos pocos registros variados. (Nota 2026-08-20: vivía
  aquí documentado como `app/supermodules/ecg_monitor/pages.py`, pero ese
  supermódulo se enterró por código muerto -- el loader real siempre fue la
  copia de `app/main.py`, ver CHANGELOG.md.)
- El set de validación BBB de la Fase 3 (`tests/ptbxl_bbb_validation_set.py`,
  instrumento de test, NO UI) -- ground truth confirmado para validar el
  detector morfológico (no autorizado todavía).

Corrige el defecto confirmado por diagnóstico (2026-08-09): antes de esto,
`load_ptbxl_record()` NUNCA cargó un registro real de PTB-XL -- usaba
`pn_dir='ptbxl'` (slug sin guion, inexistente en PhysioNet) y una lista de
5 IDs inventados (`'10038'`, `'11106'`, ...) que no existen en el dataset
(el formato real es `00001_lr`/`00001_hr`, con la ruta completa dada por
`filename_lr`/`filename_hr` en el CSV). Cualquier resultado que ese código
mostró alguna vez como "PTB-XL cargado" fue en realidad el fallback
silencioso a `generate_demo_ecg_signal()` -- una fachada (Art. I de la
Constitución: nunca presentar una simulación como si fuera el dato real
que el usuario pidió). Ver CHANGELOG.md.

Este módulo es deliberadamente headless (sin `import streamlit`) para que
el set de validación de la Fase 3 pueda importarlo sin arrastrar una
dependencia de UI.
"""

from __future__ import annotations

import os
import posixpath
import urllib.request
from typing import Tuple

import pandas as pd

PTBXL_VERSION = "1.0.3"
PTBXL_CSV_URL = f"https://physionet.org/files/ptb-xl/{PTBXL_VERSION}/ptbxl_database.csv"
PTBXL_CSV_LOCAL_PATH = os.path.join("data", "ptbxl_database.csv")


class PtbxlUnavailableError(RuntimeError):
    """PTB-XL requiere conexión a PhysioNet y no se pudo contactar.

    NUNCA se debe capturar esto para caer a una señal sintética disfrazada
    de PTB-XL (Art. I de la Constitución) -- el llamador debe mostrar este
    mensaje tal cual, no ocultarlo detrás de un demo."""


def ensure_ptbxl_database_csv(local_path: str = PTBXL_CSV_LOCAL_PATH) -> str:
    """Descarga `ptbxl_database.csv` UNA sola vez (6.6MB de metadata, NO
    las señales -- eso son ~3GB aparte, nunca descargados aquí) y lo
    cachea en `local_path`. Si ya existe, lo reutiliza sin volver a tocar
    la red."""
    if os.path.exists(local_path):
        return local_path

    parent = os.path.dirname(local_path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    try:
        with urllib.request.urlopen(PTBXL_CSV_URL, timeout=30) as resp:
            data = resp.read()
    except Exception as exc:
        raise PtbxlUnavailableError(
            "PTB-XL requiere conexión a PhysioNet -- no se pudo descargar "
            f"ptbxl_database.csv ({type(exc).__name__}: {exc})."
        ) from exc

    with open(local_path, "wb") as f:
        f.write(data)
    return local_path


def load_ptbxl_database(local_path: str = PTBXL_CSV_LOCAL_PATH) -> pd.DataFrame:
    """Lee el CSV cacheado, descargándolo primero si hace falta (ver
    `ensure_ptbxl_database_csv`)."""
    path = ensure_ptbxl_database_csv(local_path)
    return pd.read_csv(path)


def resolve_ptbxl_wfdb_args(filename: str) -> Tuple[str, str]:
    """`filename` es el valor de `filename_lr`/`filename_hr` del CSV
    (p.ej. `'records500/00000/00172_hr'`). Devuelve `(record_id, pn_dir)`
    en el patrón verificado empíricamente (Sub-Fase 2.5 y diagnóstico
    posterior): la carpeta completa (versión + records{100,500} + carpeta
    bucket) va en `pn_dir`; `wfdb.rdrecord()` NO resuelve subcarpetas
    dentro de `record_id` -- solo el nombre de archivo final va ahí."""
    directory, basename = posixpath.split(filename)
    pn_dir = f"ptb-xl/{PTBXL_VERSION}/{directory}"
    return basename, pn_dir
