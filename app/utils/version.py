"""Qué versión del código corre y si el proceso quedó con módulos viejos (2026-11-17).

Por qué: al actualizarse main, Streamlit Cloud recarga solo los módulos que cambiaron dentro de `app/`; lo de fuera
(`clinical/`, `src/`, `domain/`) se queda con la versión con la que arrancó el proceso. El 2026-11-17 eso dio un
`ImportError` (`patient_banner` nuevo pedía `news2_points_text`, que el `clinical.calculators` viejo no tenía).

- `current_commit()` lee `.git` directamente (HEAD, la rama y `packed-refs`); sin carpeta `.git`, «no disponible».
- `started_commit()` es el commit que había cuando arrancó ESTE proceso: se guarda con `st.cache_resource`, que vive
  lo que vive el proceso y no se borra cuando Streamlit recarga un módulo.
- Si los dos difieren, el proceso mezcla código viejo y nuevo: `render_stale_warning()` pide reiniciar la app.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]
REBOOT_HINT = "En Streamlit Cloud: «Manage app» (abajo a la derecha) → «Reboot app»; en una computadora, vuelve a abrirla."


def _read(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def current_commit(root: Path = ROOT) -> Optional[str]:
    """El commit al que apunta HEAD, o None si no hay `.git` legible."""
    git = root / ".git"
    head = _read(git / "HEAD")
    if not head:
        return None
    if not head.startswith("ref: "):
        return head or None                                 # HEAD separado: ya es el commit
    ref = head[5:].strip()
    loose = _read(git / ref)
    if loose:
        return loose
    for line in (_read(git / "packed-refs") or "").splitlines():
        if line.endswith(" " + ref) and not line.startswith(("#", "^")):
            return line.split(" ", 1)[0]
    return None


def short(commit: Optional[str]) -> str:
    return commit[:7] if commit else "no disponible"


def started() -> Tuple[Optional[str], datetime]:
    """(commit, hora) con que arrancó este proceso; la primera llamada lo fija."""
    import streamlit as st

    @st.cache_resource(show_spinner=False)
    def _process_start() -> Tuple[Optional[str], datetime]:
        return current_commit(), datetime.now(timezone.utc)

    return _process_start()


def process_is_stale() -> bool:
    start_commit, _ = started()
    now = current_commit()
    return bool(start_commit and now and start_commit != now)


def version_text() -> str:
    start_commit, at = started()
    return (f"Versión del código: `{short(current_commit())}` · este proceso arrancó con `{short(start_commit)}` el "
            f"{at:%Y-%m-%d %H:%M} UTC.")


def render_stale_warning() -> None:
    """Solo si el código cambió después de arrancar el proceso (si no, no dibuja nada)."""
    if not process_is_stale():
        return
    import streamlit as st

    start_commit, _ = started()
    st.warning(f"El código se actualizó a `{short(current_commit())}` después de que arrancó este proceso "
               f"(`{short(start_commit)}`): algunas partes pueden seguir con la versión anterior y fallar. "
               f"Reinicia la app. {REBOOT_HINT}")
