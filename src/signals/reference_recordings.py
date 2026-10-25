"""Registros reales de referencia (PhysioNet) que trae la app.

Traído del aporte externo auditado (2026-10-22), recortado a lo que usa algo
aprobado: el registro PTB s0010_re, ground truth del vectocardiograma (12
derivaciones + Frank grabadas a la vez). Verificado en la auditoría: los
canales son idénticos al original de PhysioNet (r = 1.0000). Desde la Tanda 2D
(2026-10-24), también CAP n16, el EEG real del mapa sobre la cabeza.

Siempre se muestran con su fuente (`source_line()`): es un registro real de
otra persona, no datos del usuario ni del gemelo.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict

import numpy as np

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "reference_signals"


class ReferenceUnavailableError(RuntimeError):
    """Falta el archivo del registro en data/reference_signals/."""


@dataclass(frozen=True)
class Recording:
    key: str
    meta: dict
    arrays: Dict[str, np.ndarray]

    @property
    def title(self) -> str:
        return self.meta["title"]

    @property
    def citation(self) -> str:
        return self.meta["citation"]

    @property
    def license(self) -> str:
        return self.meta["license"]


def _step(meta: dict, name: str) -> float:
    step = meta["step"]
    return float(step[name]) if isinstance(step, dict) else float(step)


@lru_cache(maxsize=None)
def load(key: str) -> Recording:
    path = DATA_DIR / f"{key}.npz"
    if not path.exists():
        raise ReferenceUnavailableError(f"No se encontró {path.name} (tools/build_reference_signals.py)")
    with np.load(path, allow_pickle=False) as z:
        meta = json.loads(bytes(z["meta"]).decode("utf-8"))
        arrays = {}
        for name in z.files:
            if name == "meta":
                continue
            a = z[name]
            if a.dtype == np.int16:
                arrays[name] = a.astype(np.float64) * _step(meta, name if isinstance(meta["step"], dict) else "")
            else:
                arrays[name] = a
    return Recording(key=key, meta=meta, arrays=arrays)


def source_line(key: str) -> str:
    """'Registro real: <título> (licencia ODC-By 1.0)'."""
    rec = load(key)
    return f"Registro real: {rec.title} (licencia {rec.license})"


def ptb_s0010() -> dict:
    """12 derivaciones + Frank (vx, vy, vz) en mV, 500 Hz, 20 s."""
    rec = load("ptb_s0010")
    sig = rec.arrays["signals"]
    return {"fs": float(rec.meta["fs"]), "leads": {n: sig[:, i] for i, n in enumerate(rec.meta["leads"])}}


def cap_n16() -> dict:
    """EEG bipolar (µV, 100 Hz, 30 s) del CAP n16. El tramo se eligió por su
    alfa en P4-O2, no por el hipnograma: ver `meta["detail"]` y
    `meta["hypnogram_check"]`, que la interfaz muestra tal cual."""
    rec = load("cap_n16")
    sig = rec.arrays["signals"]
    return {"fs": float(rec.meta["fs"]), "leads": {n: sig[:, i] for i, n in enumerate(rec.meta["leads"])},
            "segment_s": tuple(rec.meta["segment_s"]), "detail": rec.meta["detail"],
            "hypnogram_check": rec.meta.get("hypnogram_check")}
