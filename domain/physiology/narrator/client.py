"""
Fase 1.3 — Cliente del narrador clínico: llamada real (streaming) a la API
de Anthropic. Sin esto, no hay narrador — no existe un modo "simulado" de
respaldo que devuelva texto preescrito.

API key: solo desde la variable de entorno `ANTHROPIC_API_KEY`, nunca
hardcodeada ni pasada desde la UI. Si no está configurada, se falla de
forma explícita en vez de fabricar una narración.

2026-11-16: `client` también puede ser un `GeminiClient` (`gemini.py`, nivel
gratuito de Google) con la misma interfaz. Sin `model`, se usa el del cliente
(`default_model`) o `DEFAULT_MODEL`; y antes de llamar se revisa que el
proveedor pueda recibir esos datos (`privacy.check_provider_allows`).
"""

from __future__ import annotations

import os
from typing import Iterator, Optional

import anthropic

from .context import NarrativeContext
from .errors import NarratorNotConfiguredError
from .privacy import check_provider_allows
from .prompt import DepthLevel, build_request

DEFAULT_MODEL = "claude-opus-5-5"


def is_configured() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def resolve_model(client, model: Optional[str]) -> str:
    """El modelo pedido, o el del cliente (Gemini elige el suyo al validar la clave), o el de Anthropic."""
    return model or getattr(client, "default_model", None) or DEFAULT_MODEL


def stream_narration(
    context: NarrativeContext,
    depth: DepthLevel,
    model: Optional[str] = None,
    max_tokens: int = 4096,
    client: Optional["anthropic.Anthropic"] = None,
) -> Iterator[str]:
    """Llama a la API de Anthropic con streaming y devuelve un generador de
    fragmentos de texto — pensado para pasar directo a `st.write_stream()`.

    `context` debe venir de `domain.physiology.narrator.context.build_context`
    (datos leídos del UPS), nunca de texto compuesto a mano.

    `max_tokens=4096` (2026-08-14, antes 1024): las explicaciones del
    narrador se cortaban a media frase -- causa confirmada por el usuario,
    max_tokens insuficiente. Una explicación clínica completa (mecanismo
    fisiológico + significado clínico + comparación antes/ahora) son
    fácilmente 600-1200 palabras, ~1500-2500 tokens -- 4096 deja margen real
    sobre ese techo, no un ajuste al límite (duplicar a 2048 habría quedado
    justo en el borde superior de esa estimación, sin margen)."""

    if client is None:
        if not is_configured():
            raise NarratorNotConfiguredError(
                "ANTHROPIC_API_KEY no está configurada. El narrador requiere una llamada real "
                "a la API de Anthropic — no hay una narración de respaldo simulada."
            )
        client = anthropic.Anthropic()
    check_provider_allows(client, context.origin)

    system_prompt, messages = build_request(context, depth)

    with client.messages.stream(
        model=resolve_model(client, model),
        max_tokens=max_tokens,
        system=system_prompt,
        messages=messages,
    ) as stream:
        yield from stream.text_stream
