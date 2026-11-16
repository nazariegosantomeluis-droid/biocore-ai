"""
Fase 1.3 — Narrador clínico en tiempo real (IA real, Anthropic).

Refunde `app/ai_copilot.py` (JARVIS, muerto/sin uso) y `app/biomedical_tutor.py`
(diccionario de keywords) en un único punto de IA real: este narrador lee el
Unified Physiological State (`domain/physiology/state/`) y genera su
explicación fundamentada en esos datos, vía streaming de la API de
Anthropic o, desde el 2026-11-16, del nivel gratuito de Gemini (`gemini.py`),
que solo recibe datos simulados o de bases públicas (`privacy.py`). No es un
chatbot de propósito general (Art. I de la Constitución) — no tiene system
prompt genérico ni memoria de conversación libre; cada llamada se reconstruye
desde el UPS actual.
"""

from .causal import CausalContext, CausalHint, build_causal_context, stream_causal_narration
from .client import DEFAULT_MODEL, NarratorNotConfiguredError, is_configured, resolve_model, stream_narration
from .context import DescriptorContext, EventContext, NarrativeContext, build_context
from .errors import ProviderNotAllowedError
from .findings import Finding, FindingsContext, stream_findings_narration
from .gemini import DEFAULT_GEMINI_MODEL, GeminiClient, GeminiError
from .privacy import DataOrigin, check_provider_allows, classify_source
from .prompt import DepthLevel, build_messages, build_request, build_system_prompt

__all__ = [
    "DEFAULT_MODEL",
    "NarratorNotConfiguredError",
    "ProviderNotAllowedError",
    "is_configured",
    "resolve_model",
    "stream_narration",
    "DEFAULT_GEMINI_MODEL",
    "GeminiClient",
    "GeminiError",
    "DataOrigin",
    "check_provider_allows",
    "classify_source",
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
