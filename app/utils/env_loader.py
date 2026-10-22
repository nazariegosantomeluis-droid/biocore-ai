"""Carga mínima de `.env` (sin dependencias nuevas).

`.env.example` y SETUP.md indican copiar el archivo a `.env`, pero hasta ahora
nada lo leía: la clave solo funcionaba si se exportaba a mano en la terminal,
y el narrador mostraba "no configurada" aunque `.env` existiera.

Reglas deliberadas:
- Una variable que ya existe en el entorno GANA sobre `.env` (nunca se pisa).
- Se ignora el valor de ejemplo `sk-your-key-here`, para que una copia sin
  editar de `.env.example` no se presente como una clave real (Art. I: declarar,
  no fingir) -- el narrador sigue mostrando "no configurada".
- Si el archivo no existe o no se puede leer, no pasa nada.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict

_PLACEHOLDER_VALUES = {"sk-your-key-here", ""}


def parse_dotenv(text: str) -> Dict[str, str]:
    """Parsea líneas `CLAVE=valor` (admite `export`, comillas y comentarios #)."""
    values: Dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        if key:
            values[key] = value
    return values


def load_dotenv_file(path: Path) -> Dict[str, str]:
    """Aplica `path` a `os.environ` sin sobrescribir. Devuelve lo que se cargó."""
    try:
        text = Path(path).read_text(encoding="utf-8-sig")
    except OSError:
        return {}
    loaded: Dict[str, str] = {}
    for key, value in parse_dotenv(text).items():
        if value in _PLACEHOLDER_VALUES or key in os.environ:
            continue
        os.environ[key] = value
        loaded[key] = value
    return loaded
