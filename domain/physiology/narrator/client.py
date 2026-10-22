"""
Fase 1.3 — Cliente del narrador clínico: llamada real (streaming) a un
modelo de lenguaje. Sin esto, no hay narrador — no existe un modo
"simulado" de respaldo que devuelva texto preescrito.

2026-10-21: el motor ya no tiene que ser Anthropic. `providers.py` elige
entre una IA local gratuita (Ollama u otro servidor compatible con OpenAI,
sin clave) y Claude (con `ANTHROPIC_API_KEY`, que sigue saliendo solo del
entorno, nunca de la UI). Si no hay ningún motor, se falla de forma
explícita en vez de fabricar una narración.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Iterator, Optional

if TYPE_CHECKING:  # pragma: no cover
    import anthropic

from .context import NarrativeContext
from .prompt import DepthLevel, build_request

# Activo según la tabla oficial de deprecaciones (retiro "no antes de"
# 2027-05-28). `BIOCORE_CLAUDE_MODEL` permite actualizarlo sin tocar código
# cuando se anuncie su retiro (se lee al importar; app/main.py carga `.env`
# antes de importar el narrador).
DEFAULT_MODEL = os.environ.get("BIOCORE_CLAUDE_MODEL", "").strip() or "claude-opus-4-8"


class NarratorNotConfiguredError(RuntimeError):
    """No hay ningún motor de IA disponible (ni local ni Anthropic)."""


def is_configured() -> bool:
    """Hay un motor de IA listo (local gratuito o Anthropic)."""
    from . import providers

    return providers.resolve().ready


def stream_narration(
    context: NarrativeContext,
    depth: DepthLevel,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 4096,
    client: Optional["anthropic.Anthropic"] = None,
) -> Iterator[str]:
    """Genera la narración con streaming (motor activo de `providers`, o el
    `client` de Anthropic que se pase, p. ej. en pruebas) y devuelve un
    generador de fragmentos de texto — pensado para `st.write_stream()`.

    `context` debe venir de `domain.physiology.narrator.context.build_context`
    (datos leídos del UPS), nunca de texto compuesto a mano.

    `max_tokens=4096` (2026-08-14, antes 1024): las explicaciones del
    narrador se cortaban a media frase -- causa confirmada por el usuario,
    max_tokens insuficiente. Una explicación clínica completa (mecanismo
    fisiológico + significado clínico + comparación antes/ahora) son
    fácilmente 600-1200 palabras, ~1500-2500 tokens -- 4096 deja margen real
    sobre ese techo, no un ajuste al límite (duplicar a 2048 habría quedado
    justo en el borde superior de esa estimación, sin margen)."""

    system_prompt, messages = build_request(context, depth)
    if client is None:
        from . import providers

        yield from providers.stream_chat(system_prompt, messages, max_tokens=max_tokens, anthropic_model=model)
        return

    with client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=messages,
    ) as stream:
        yield from stream.text_stream
