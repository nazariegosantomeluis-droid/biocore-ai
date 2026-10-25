"""Arranque de BIOCORE AI — lo usan RUN_BIOCORE.bat y run_local.ps1.

Uso:  python run_biocore.py [opciones de streamlit, p. ej. --server.port 8501]
(equivale a `streamlit run app/main.py ...`, que sigue funcionando igual).

Por qué existe (2026-10-19): Streamlit sirve la app con Uvicorn (ya en 1.58, la
versión instalada al auditar) sobre el event loop por defecto de Windows
(ProactorEventLoop). Si un cliente aborta una conexión mientras se acepta
(WinError 64, "El nombre de red especificado ya no está disponible" — basta un
navegador que cancela una pre-conexión), asyncio CIERRA el socket de escucha
(`proactor_events._start_serving`, verificado en CPython 3.13): el proceso
sigue vivo pero http://localhost:8501 deja de responder para siempre. Con el
event loop de selectores ese error solo afecta a esa conexión. Es el mismo
remedio que aplica Uvicorn en Windows cuando usa subprocesos.

Rótulo honesto (Tanda 2B, 2026-10-24) — es una MITIGACIÓN, no un arreglo:
- Solo actúa si se arranca con este lanzador (RUN_BIOCORE.bat, run_local.ps1 o
  `python run_biocore.py`). Con `streamlit run app/main.py` directo NO se
  aplica y el comportamiento de CPython sigue ahí.
- Tiene fecha de caducidad: `asyncio.set_event_loop_policy` y
  `WindowsSelectorEventLoopPolicy` están deprecadas desde Python 3.14 y se
  retiran en 3.16. En 3.14/3.15 funciona (con el aviso silenciado abajo); en
  3.16 la política ya no existe, la mitigación deja de aplicarse y se avisa
  por consola. Revisar entonces (p. ej. una `loop_factory` si Streamlit la
  expone).
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
        print("Aviso: este Python ya no tiene WindowsSelectorEventLoopPolicy; la mitigacion "
              "del cierre de socket no se aplica (ver run_biocore.py).", file=sys.stderr)
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
