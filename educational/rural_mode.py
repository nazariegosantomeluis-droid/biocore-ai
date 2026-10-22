"""Modo Rural: persistencia local (offline) del progreso de Academia.

`educational/learning_engine.py` importa este módulo desde la Fusión
Education+Academia (2026-07-13), pero el archivo no existía en el repo: el
`ImportError` hacía que `app/supermodules/academia/pages.py` declarara
`LESSONS_AVAILABLE = False` y el Learning Hub mostraba solo "El módulo de
lecciones no está disponible" -- quiz y casos clínicos inaccesibles.

Contrato que ya esperaba `LearningEngine` (no se inventa API nueva):
- `save_progress(student_id, progress)`  -- guarda el dict de progreso.
- `load_progress(student_id) -> dict | None` -- lo devuelve, o `None` si no hay.

Almacenamiento: un JSON por estudiante en `data/local/progress/` (ya
git-ignorado por `data/local/*`). Sin red, sin base de datos: es justo lo que
promete el checkbox "Modo Rural (offline, guardar progreso localmente)".
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULT_PROGRESS_DIR = Path(__file__).resolve().parents[1] / "data" / "local" / "progress"

_SAFE_ID = re.compile(r"[^A-Za-z0-9_.-]+")


def _progress_path(student_id: str, base_dir: Optional[Path] = None) -> Path:
    """Ruta del JSON del estudiante. El id se sanea para que no pueda escapar
    del directorio (`../`, separadores, etc.)."""
    safe = _SAFE_ID.sub("_", str(student_id).strip())[:80].strip("._") or "estudiante"
    return Path(base_dir or DEFAULT_PROGRESS_DIR) / f"{safe}.json"


def save_progress(student_id: str, progress: Dict[str, Any], base_dir: Optional[Path] = None) -> Path:
    """Escribe el progreso de forma atómica (archivo temporal + rename), para
    que un cierre a mitad de escritura no deje un JSON corrupto."""
    path = _progress_path(student_id, base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"student_id": str(student_id), "progress": progress}
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    return path


def load_progress(student_id: str, base_dir: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Progreso guardado del estudiante, o `None` si no existe o está ilegible."""
    path = _progress_path(student_id, base_dir)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    progress = payload.get("progress") if isinstance(payload, dict) else None
    return progress if isinstance(progress, dict) else None
