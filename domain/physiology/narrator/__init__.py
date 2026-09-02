"""
Fase 1.3 — Narrador clínico en tiempo real (IA real, Anthropic).

Refunde `app/ai_copilot.py` (JARVIS, muerto/sin uso) y `app/biomedical_tutor.py`
(diccionario de keywords) en un único punto de IA real: este narrador lee el
Unified Physiological State (`domain/physiology/state/`) y genera su
explicación fundamentada en esos datos, vía streaming de la API de
Anthropic. No es un chatbot de propósito general (Art. I de la
Constitución) — no tiene system prompt genérico ni memoria de conversación
libre; cada llamada se reconstruye desde el UPS actual.
"""

from .causal import CausalContext, CausalHint, build_causal_context, stream_causal_narration
from .client import DEFAULT_MODEL, NarratorNotConfiguredError, is_configured, stream_narration
from .context import DescriptorContext, EventContext, NarrativeContext, build_context
from .findings import Finding, FindingsContext, stream_findings_narration
from .prompt import DepthLevel, build_messages, build_request, build_system_prompt

__all__ = [
    "DEFAULT_MODEL",
    "NarratorNotConfiguredError",
    "is_configured",
    "stream_narration",
    "DescriptorContext",
    "EventContext",
    "NarrativeContext",
    "build_context",
    "Finding",
    "FindingsContext",
    "stream_findings_narration",
    "DepthLevel",
    "build_messages",
    "build_request",
    "build_system_prompt",
    "CausalContext",
    "CausalHint",
    "build_causal_context",
    "stream_causal_narration",
]
