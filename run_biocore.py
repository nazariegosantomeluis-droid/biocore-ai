"""Arranque de BIOCORE AI — lo usan RUN_BIOCORE.bat y run_local.ps1.

Uso:  python run_biocore.py [opciones de streamlit, p. ej. --server.port 8501]
(equivale a `streamlit run app/main.py ...`, que sigue funcionando igual).

Por qué existe (2026-10-19): Streamlit >= 1.66 sirve la app con Uvicorn sobre
el event loop por defecto de Windows (ProactorEventLoop). Si un cliente aborta
una conexión mientras se acepta (WinError 64, "El nombre de red especificado ya
no está disponible" — basta un navegador que cancela una pre-conexión), asyncio
CIERRA el socket de escucha (`proactor_events._start_serving`): el proceso
sigue vivo pero http://localhost:8501 deja de responder para siempre. Con el
event loop de selectores ese error solo afecta a esa conexión. Es el mismo
remedio que aplica Uvicorn en Windows cuando usa subprocesos.
"""
from __future__ import annotations

import asyncio
import sys
import warnings
from pathlib import Path
from typing import List, Optional

APP = Path(__file__).resolve().parent / "app" / "main.py"


def use_selector_event_loop_on_windows() -> bool:
    """Instala `WindowsSelectorEventLoopPolicy` en Windows. Devuelve si lo hizo."""
    if sys.platform != "win32":
        return False
    policy_cls = getattr(asyncio, "WindowsSelectorEventLoopPolicy", None)
    if policy_cls is None:  # Python sin políticas de event loop (>= 3.16)
        return False
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)  # políticas deprecadas en 3.14
        asyncio.set_event_loop_policy(policy_cls())
    return True


def main(argv: Optional[List[str]] = None) -> int:
    use_selector_event_loop_on_windows()
    from streamlit.web import cli as stcli

    extra = list(sys.argv[1:] if argv is None else argv)
    sys.argv = ["streamlit", "run", str(APP), *extra]
    return stcli.main()


if __name__ == "__main__":
    sys.exit(main())
