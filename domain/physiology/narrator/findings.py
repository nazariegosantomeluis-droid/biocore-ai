"""
Narrador de hallazgos puntuales — complemento del narrador UPS (`context.py` /
`prompt.py` / `client.py`) para laboratorios que calculan métricas reales sobre
una señal cargada en el momento (EMG, HRV, Multisensor, ECG Monitor) pero que
no persisten en el Unified Physiological State — el UPS hoy solo modela los
dominios cardiovascular y respiratorio (ver `domain/physiology/state/schema.py`),
así que estos laboratorios no tienen dónde guardar un snapshot que anclar.

Misma disciplina de anclaje y la misma llamada real (streaming, Anthropic,
`ANTHROPIC_API_KEY` obligatoria, sin narración simulada de respaldo) que el
narrador UPS — la única diferencia es el contexto: aquí es una lista plana de
métricas ya calculadas por el laboratorio (nunca texto compuesto a mano, nunca
inventadas), en vez de descriptores/eventos leídos de una base de datos con
comparación temporal.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Iterator, List, Optional

import anthropic

from .client import DEFAULT_MODEL, NarratorNotConfiguredError, is_configured

__all__ = [
    "Finding",
    "FindingsContext",
    "stream_findings_narration",
]


@dataclass(frozen=True)
class Finding:
    """Una métrica ya calculada por el laboratorio, con su valor real."""

    name: str
    value: str
    meaning: str = ""

    def to_payload(self) -> dict:
        return {"metric": self.name, "value": self.value, "meaning": self.meaning}


@dataclass(frozen=True)
class FindingsContext:
    """Contexto completo que se envía al modelo — la única fuente de hechos
    permitida para esta narración."""

    lab_name: str
    findings: List[Finding] = field(default_factory=list)

    def to_payload(self) -> dict:
        return {
            "lab": self.lab_name,
            "findings": [f.to_payload() for f in self.findings],
        }


_SYSTEM_PROMPT = """Eres el narrador clínico de BIOCORE AI para laboratorios educativos de señales \
biomédicas. Interpretas métricas ya calculadas sobre una señal (real o sintética, ya etiquetada como \
tal en la interfaz que te contiene); no eres un chatbot de propósito general y no respondes desde \
conocimiento médico genérico sin anclarlo a los datos que se te entregan.

Tu única fuente de hechos es el contexto estructurado (JSON) que recibes en el mensaje del usuario: \
una lista de métricas ya computadas para este laboratorio, con su nombre exacto y valor. No hay otra \
fuente de datos, y no hay comparación temporal disponible (a diferencia del narrador del Unified \
Physiological State) — limítate al estado actual.

Reglas estrictas, no negociables:
1. Cada afirmación clínica debe citar el nombre exacto de una métrica del contexto (p.ej. \
`median_frequency_hz`, `sdnn_ms`). Si no puedes anclar una afirmación a una métrica dada, omítela — \
no la inventes.
2. Nunca inventes un valor o unidad que no esté en el contexto.
3. Sé breve (3-5 frases): qué muestra cada métrica relevante, qué significa fisiológicamente, y qué \
vigilarías a continuación. No agregues disclaimers genéricos de "esto no es un diagnóstico médico" — \
el contexto educativo/simulado ya está declarado en la UI que te contiene."""


def build_findings_messages(context: FindingsContext) -> List[dict]:
    payload = json.dumps(context.to_payload(), ensure_ascii=False, indent=2)
    content = (
        f"Métricas calculadas en el laboratorio '{context.lab_name}' (única fuente de hechos "
        f"permitida):\n\n"
        f"```json\n{payload}\n```\n\n"
        "Explica qué significan estos hallazgos, siguiendo las reglas del system prompt."
    )
    return [{"role": "user", "content": content}]


def stream_findings_narration(
    context: FindingsContext,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 4096,
    client: Optional["anthropic.Anthropic"] = None,
) -> Iterator[str]:
    """Llama a la API de Anthropic con streaming — pensado para pasar directo
    a `st.write_stream()`, igual que `client.stream_narration`.

    `max_tokens=4096` (2026-08-14, antes 1024) -- mismo arreglo y misma
    justificación que `client.stream_narration`, ver su docstring."""

    if client is None:
        if not is_configured():
            raise NarratorNotConfiguredError(
                "ANTHROPIC_API_KEY no está configurada. Este narrador requiere una llamada real a "
                "la API de Anthropic — no hay una narración de respaldo simulada."
            )
        client = anthropic.Anthropic()

    with client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        system=_SYSTEM_PROMPT,
        messages=build_findings_messages(context),
    ) as stream:
        yield from stream.text_stream
