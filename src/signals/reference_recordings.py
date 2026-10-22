"""Registros reales de referencia (PhysioNet) que trae la app (2026-10-21).

Tramos cortos de bases de datos abiertas (todas con licencia Open Data
Commons Attribution 1.0) que `tools/build_reference_signals.py` guarda en
`data/reference_signals/`. Se usan donde antes había trazos dibujados: las
tiras de los encabezados, el latido mediano del Atlas, el tacograma y las
bandas del EEG, y el vectocardiograma del PTB.

Siempre se muestran con su fuente (`source_line()`): son registros reales
de otras personas, no datos del usuario ni del gemelo.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, Tuple

import numpy as np

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "reference_signals"
KEYS: Tuple[str, ...] = ("mitdb_100", "ptb_s0010", "cap_n16", "challenge2015_a103l", "mimic_037")


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


def available() -> bool:
    return all((DATA_DIR / f"{k}.npz").exists() for k in KEYS)


def source_line(key: str) -> str:
    """'Registro real: <título> (licencia ODC-By 1.0)'."""
    rec = load(key)
    return f"Registro real: {rec.title} (licencia {rec.license})"


# ─────────────────────────────────────────────────────────────────────────
# Accesos cómodos
# ─────────────────────────────────────────────────────────────────────────

def mitdb_100() -> dict:
    """ECG MLII (mV, 360 Hz, 5 min) + latidos anotados (muestras y símbolos)."""
    rec = load("mitdb_100")
    return {
        "fs": float(rec.meta["fs"]),
        "mlii": rec.arrays["mlii"],
        "beats": rec.arrays["beat_sample"].astype(int),
        "symbols": bytes(rec.arrays["beat_symbol"]).decode("ascii"),
    }


def normal_rr_ms(max_beats: int = 400, start_s: float = 0.0) -> np.ndarray:
    """Intervalos RR (ms) entre latidos normales consecutivos (N-N) del
    registro 100, según las anotaciones de los cardiólogos."""
    d = mitdb_100()
    b, s, fs = d["beats"], d["symbols"], d["fs"]
    keep = b >= start_s * fs
    b, s = b[keep], "".join(c for c, k in zip(s, keep) if k)
    rr = []
    for i in range(1, len(b)):
        if s[i] == "N" and s[i - 1] == "N":
            rr.append((b[i] - b[i - 1]) / fs * 1000.0)
        if len(rr) >= max_beats:
            break
    return np.asarray(rr, dtype=float)


def ptb_s0010() -> dict:
    """12 derivaciones + Frank (vx, vy, vz) en mV, 500 Hz, 20 s."""
    rec = load("ptb_s0010")
    sig = rec.arrays["signals"]
    return {"fs": float(rec.meta["fs"]), "leads": {n: sig[:, i] for i, n in enumerate(rec.meta["leads"])}}


def cap_n16() -> dict:
    """EEG bipolar (µV, 100 Hz, 30 s de vigilia con alfa)."""
    rec = load("cap_n16")
    sig = rec.arrays["signals"]
    return {"fs": float(rec.meta["fs"]), "leads": {n: sig[:, i] for i, n in enumerate(rec.meta["leads"])},
            "segment_s": tuple(rec.meta["segment_s"])}


def ppg_a103l() -> dict:
    """PPG del oxímetro (u.n.) y ECG II (mV) a 250 Hz, 30 s."""
    rec = load("challenge2015_a103l")
    return {"fs": float(rec.meta["fs"]), "pleth": rec.arrays["pleth"], "ii": rec.arrays["ii"]}


def mimic_037() -> dict:
    """Monitor de UCI: ECG MCL1 (500 Hz), ABP (mmHg, 125 Hz), RESP (125 Hz), 120 s."""
    rec = load("mimic_037")
    fs = rec.meta["fs"]
    return {"fs": {k: float(v) for k, v in fs.items()}, "mcl1": rec.arrays["mcl1"],
            "abp": rec.arrays["abp"], "resp": rec.arrays["resp"]}
