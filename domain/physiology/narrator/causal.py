"""
Narrador causal — complemento del narrador UPS (`context.py`/`prompt.py`/
`client.py`) para responder una pregunta distinta: no "¿qué muestra el estado
ahora?" sino "¿por qué llegó a este estado?".

Reutiliza `build_context()` sin cambiarlo — la comparación antes→ahora de
cada descriptor y el orden temporal de los eventos ya son, por construcción,
la evidencia causal (qué cambió, y cuándo). No se duplica esa lectura del
UPS; solo se envuelve con el órgano objetivo y un pequeño set de pistas
fisiológicas de referencia.

Sobre `CAUSAL_RULES`: originalmente vivía en `app/engines/causality_engine.py`
(`CausalityEngine`, retirado el 2026-08-19 -- Art. I, confidence hardcodeado
sin cálculo, huérfano desde el 2026-07-13 cuando este narrador lo reemplazó
en la UI). `_CAUSAL_HINTS` abajo es un espejo manual de esas 2 reglas, no un
import -- sigue vigente sin cambios pese al retiro del archivo original. De
las 8 reglas originales, solo 2 conectaban exclusivamente dominios que el UPS modela hoy
(cardiovascular/respiratorio) — las otras 6 involucran `brain`/`muscles`/
`autonomic`, que el UPS no modela todavía. Pasarle esas 6 al modelo como
"pista" lo invitaría a razonar sobre datos inexistentes — el mismo tipo de
especulación sin ancla que el Art. I prohíbe. Por eso solo se conservan las 2
UPS-fundamentables aquí, explícitamente etiquetadas como marco interpretativo
opcional, nunca como una afirmación por sí solas.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Iterator, List, Optional

import anthropic

from .client import DEFAULT_MODEL, NarratorNotConfiguredError, is_configured
from .context import NarrativeContext, build_context

__all__ = [
    "CausalHint",
    "CausalContext",
    "build_causal_context",
    "stream_causal_narration",
]


@dataclass(frozen=True)
class CausalHint:
    """Una relación fisiológica de referencia — marco interpretativo, nunca un
    hecho medido. Solo se incluyen las que conectan descriptores que el UPS
    realmente modela (cardiovascular/respiratorio).

    Terminología alineada (Tanda 2, 2026-08-14) con el mismo vocabulario de
    procedencia que `app/supermodules/twin_shell/pages.py`
    (`PROVENANCE_HEURISTIC_LABEL`): `confidence` aquí NO es una medición del
    paciente ni una cita clínica formal, es -- igual que las heurísticas del
    Digital Twin -- un índice interno de BIOCORE sin validación clínica
    externa, expuesto al modelo como `reference_confidence` (nunca a la UI
    como una métrica cruda) para que razone con ese contexto explícito, no
    para que el usuario lo lea como un dato citado."""

    cause_descriptor: str
    effect_descriptor: str
    direction: str  # "positive" | "negative"
    confidence: float
    note: str

    def to_payload(self) -> dict:
        return {
            "cause_descriptor": self.cause_descriptor,
            "effect_descriptor": self.effect_descriptor,
            "direction": self.direction,
            "reference_confidence": self.confidence,
            "note": self.note,
        }


# Espejo, no import, de las 2 entradas de CausalityEngine.CAUSAL_RULES cuyo
# cause/effect son ambos dominios UPS-modelados (ver docstring del módulo).
_CAUSAL_HINTS: List[CausalHint] = [
    CausalHint(
        cause_descriptor="spo2",
        effect_descriptor="heart_rate",
        direction="negative",
        confidence=0.88,
        note="SpO2 bajo puede forzar taquicardia compensatoria (mayor demanda de oxígeno).",
    ),
    CausalHint(
        cause_descriptor="respiratory_rate",
        effect_descriptor="spo2",
        direction="positive",
        confidence=0.85,
        note="Frecuencia respiratoria adecuada tiende a sostener la saturación de oxígeno.",
    ),
]

_ORGAN_TO_DOMAIN = {"heart": "cardiovascular", "lungs": "respiratory"}


@dataclass(frozen=True)
class CausalContext:
    """Contexto completo para la pregunta causal — el mismo `NarrativeContext`
    del narrador UPS (descriptores con antes→ahora, eventos con timestamp),
    más el órgano objetivo y las pistas fisiológicas de referencia."""

    narrative: NarrativeContext
    target_organ: str
    hints: List[CausalHint] = field(default_factory=lambda: list(_CAUSAL_HINTS))

    def to_payload(self) -> dict:
        return {
            "target_organ": self.target_organ,
            "target_domain": _ORGAN_TO_DOMAIN.get(self.target_organ, self.target_organ),
            **self.narrative.to_payload(),
            "reference_physiological_hints": [h.to_payload() for h in self.hints],
        }


def build_causal_context(session, patient_id: str, target_organ: str) -> CausalContext:
    """`target_organ` es el id del organismo (`heart`/`lungs`) — se traduce a
    su dominio del UPS solo para el payload; la llamada a `build_context()` no
    cambia en absoluto."""
    narrative = build_context(session, patient_id)
    return CausalContext(narrative=narrative, target_organ=target_organ)


_SYSTEM_PROMPT = """Eres el narrador causal de BIOCORE AI. No describes qué muestra el estado \
fisiológico actual — explicas POR QUÉ el órgano objetivo llegó a ese estado. Interpretas datos \
reales del Unified Physiological State (UPS); no eres un chatbot de propósito general y no \
razonas desde conocimiento médico genérico sin anclarlo a los datos que se te entregan.

Tu única fuente de hechos es el contexto estructurado (JSON) que recibes en el mensaje del \
usuario: descriptores fisiológicos con su comparación antes→ahora, eventos clínicos con su \
timestamp exacto, y un pequeño set de "reference_physiological_hints" — relaciones fisiológicas \
de referencia, NO hechos medidos, solo marco interpretativo opcional.

Reglas estrictas, no negociables:
1. Tu tarea es razonar el ORIGEN del estado de `target_organ`, no describirlo. Estructura tu \
respuesta como una cadena causal: qué cambió primero, qué vino después, y cómo eso explica el \
estado actual del órgano objetivo.
2. Ancla cada paso causal a un descriptor (con su comparación antes→ahora) o a un evento (con su \
timestamp) del contexto — citando su nombre exacto. Si no puedes anclar un paso, omítelo.
3. Usa el ORDEN TEMPORAL de los eventos como evidencia: un evento con timestamp anterior es un \
candidato a causa de un evento posterior en otro dominio — pero solo lo son si los datos reales \
lo sustentan, nunca por suposición.
4. Puedes usar las `reference_physiological_hints` como marco interpretativo — pero solo cuando \
los descriptores/eventos reales las respalden. Nunca afirmes una relación causal apoyándote solo \
en una pista, sin datos reales que la sustenten.
5. Si no hay suficiente trayectoria para inferir una causa (los descriptores no tienen un "antes", \
o no hay eventos con orden temporal claro), dilo honestamente: "No hay suficiente historial para \
determinar una causa" — no inventes un origen que no está en los datos. Mismo principio que un \
`before_value` ausente: no se rellena, se declara ausente.
6. Nunca presentes un valor de `provenance: simulacion` como si viniera de un sensor real.

Sé conciso (4-6 frases): la cadena causal, su fundamento en los datos, y qué vigilarías para \
confirmarla."""


def _build_causal_messages(context: CausalContext) -> List[dict]:
    payload = json.dumps(context.to_payload(), ensure_ascii=False, indent=2)
    content = (
        f"Contexto estructurado del UPS para razonar la causa del estado de "
        f"'{context.target_organ}' (única fuente de hechos permitida):\n\n"
        f"```json\n{payload}\n```\n\n"
        "Explica por qué este órgano llegó a su estado actual, siguiendo las reglas del "
        "system prompt."
    )
    return [{"role": "user", "content": content}]


def stream_causal_narration(
    context: CausalContext,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 4096,
    client: Optional["anthropic.Anthropic"] = None,
) -> Iterator[str]:
    """Llama a la API de Anthropic con streaming — mismo patrón que
    `client.stream_narration`/`findings.stream_findings_narration`.

    `max_tokens=4096` (2026-08-14, antes 1024) -- mismo arreglo y misma
    justificación que `client.stream_narration`, ver su docstring."""

    if client is None:
        if not is_configured():
            raise NarratorNotConfiguredError(
                "ANTHROPIC_API_KEY no está configurada. El narrador causal requiere una llamada "
                "real a la API de Anthropic — no hay una narración de respaldo simulada."
            )
        client = anthropic.Anthropic()

    with client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        system=_SYSTEM_PROMPT,
        messages=_build_causal_messages(context),
    ) as stream:
        yield from stream.text_stream
