"""Contrato de los instrumentos (T2, 2026-11-18).

Un instrumento es una función `instrumento(ctx, ...)` que dibuja una pieza de un laboratorio. El contexto decide dos
cosas que antes estaban fijas en cada página:

- **Claves:** todo widget se nombra con `ctx.k("nombre")`. En la página de siempre (`PAGE`) la clave queda igual que
  antes (las pruebas y el estado de la sesión no cambian); en una estación lleva el prefijo de la estación, para que el
  mismo instrumento pueda montarse dos veces en una página sin chocar.
- **Controles de la fuente:** van en `ctx.panel`. En la página, el menú lateral (como siempre); en una estación, un
  contenedor dentro de la página: la ruta no usa el menú lateral para los controles de un paso."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import streamlit as st

MODE_FREE = "libre"          # la página de siempre (o «Paciente › Medir» en la ruta)
MODE_STATION = "estacion"    # dentro de una estación de la ruta


@dataclass(frozen=True)
class InstrumentContext:
    key_prefix: str = ""
    mode: str = MODE_FREE
    controls: Any = None     # None = el menú lateral

    def __post_init__(self):
        # Revisión de la T2: en una estación, `auto_key` sin prefijo dejaría widgets sin clave y dos montajes chocarían.
        if self.mode == MODE_STATION and not self.key_prefix:
            raise ValueError("un contexto de estación necesita prefijo (usa station_context)")

    def k(self, name: str) -> str:
        return f"{self.key_prefix}{name}"

    def auto_key(self, name: str) -> Optional[str]:
        """La clave de un widget que en su página de siempre NO tenía clave: en la página sigue sin ella (misma
        identidad de widget, mismo comportamiento: un control sin clave vuelve a su valor inicial cuando ese valor
        cambia, p. ej. la FC del paciente); en una estación lleva `k(name)` para no chocar con otro montaje."""
        return self.k(name) if self.key_prefix else None

    @property
    def panel(self):
        return self.controls if self.controls is not None else st.sidebar

    def deco(self, emoji: str) -> str:
        """El emoji decorativo de la página de siempre; en una estación de la ruta, nada (diseño firmado: sin emoji).
        El texto que sigue dice lo mismo con palabras."""
        return "" if self.in_station else f"{emoji} "

    @property
    def in_station(self) -> bool:
        return self.mode == MODE_STATION


PAGE = InstrumentContext()


def station_context(prefix: str) -> InstrumentContext:
    """El contexto de un instrumento dentro de una estación: claves `"<prefijo>__<nombre>"` y controles en un
    contenedor nuevo de la página, en el lugar donde se llama."""
    return InstrumentContext(key_prefix=f"{prefix}__", mode=MODE_STATION, controls=st.container())


@dataclass
class InstrumentResult:
    """Lo que un instrumento calculó, para que la estación (o la página) lo use sin volver a calcularlo."""
    values: Dict[str, float] = field(default_factory=dict)
    saved_snapshot_id: Optional[str] = None
