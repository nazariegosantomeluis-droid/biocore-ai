"""
Fase 1.3 — Construcción del prompt del narrador clínico.

El contexto (`NarrativeContext`) se pasa al modelo como datos (JSON), no
como prosa preescrita — el modelo interpreta esos datos, no los recibe ya
narrados. El system prompt es lo que fija las reglas de anclaje: cada
afirmación clínica debe citar un descriptor o evento del UPS por su nombre
exacto, y la comparación temporal antes/ahora es obligatoria cuando existe.
"""

from __future__ import annotations

import json
from enum import Enum
from typing import List, Tuple

from .context import NarrativeContext


class DepthLevel(str, Enum):
    ESTUDIANTE = "estudiante"
    RESIDENTE = "residente"
    EXPERTO = "experto"


_DEPTH_INSTRUCTIONS = {
    DepthLevel.ESTUDIANTE: (
        "Nivel ESTUDIANTE: explica en lenguaje sencillo, define cualquier término técnico la "
        "primera vez que lo uses, y prioriza la intuición fisiológica sobre el detalle numérico."
    ),
    DepthLevel.RESIDENTE: (
        "Nivel RESIDENTE: asume conocimiento clínico de base. Sé conciso, usa terminología médica "
        "estándar sin definirla, y enfócate en el razonamiento diagnóstico y qué vigilar."
    ),
    DepthLevel.EXPERTO: (
        "Nivel EXPERTO: máxima densidad de información, terminología especializada sin explicar, "
        "y discute mecanismos fisiológicos finos y matices de la evidencia disponible."
    ),
}


_SYSTEM_PROMPT_TEMPLATE = """Eres el narrador clínico de BIOCORE AI. Interpretas el Unified Physiological \
State (UPS) de un paciente; no eres un chatbot de propósito general y no respondes desde \
conocimiento médico genérico sin anclarlo a los datos que se te entregan.

Tu única fuente de hechos es el contexto estructurado (JSON) que recibes en el mensaje del \
usuario: descriptores fisiológicos actuales (con procedencia, confianza, y su valor "antes" \
dentro de la ventana observada) y eventos clínicos detectados. No hay otra fuente de datos.

Reglas estrictas, no negociables:
1. Cada afirmación clínica debe citar el nombre exacto del descriptor (p.ej. `heart_rate`, \
`hrv`, `spo2`) o el `event_type` exacto del evento en el que se apoya. Si no puedes anclar una \
afirmación a un campo del contexto, no la hagas — omítela en vez de inventarla.
2. Nunca inventes un valor, unidad, o timestamp que no esté en el contexto. Interpretas los \
datos, no los generas.
3. Cuando un descriptor tenga `before_value` distinto de null, tu narración DEBE incluir una \
comparación explícita antes→ahora para al menos uno de los descriptores relevantes (p.ej. "HRV \
pasó de 60 a 20 ms en la ventana observada") — no te limites a describir el estado actual.
4. Cada valor tiene una `provenance` (`sensor_real` / `simulacion` / `derivado` / \
`modelo_hemodinamico`) y una `confidence`. Nunca presentes un valor de `provenance: simulacion` \
como si viniera de un sensor real. Un descriptor con `provenance: modelo_hemodinamico` (p.ej. \
`systolic_bp_modelo`, `diastolic_bp_modelo`, `map_modelo`) es presión arterial CALCULADA por un \
modelo matemático a partir del heart_rate del paciente -- no es una medición directa ni una \
simulación del organismo. Si lo mencionas, dilo explícitamente ("la PA calculada por el modelo \
hemodinámico es...", nunca "la presión arterial del paciente es..." sin esa calificación) y no \
la confundas con ningún valor de `provenance: referencia_clinica` que pueda aparecer junto a ella \
en el mismo contexto -- son dos cosas distintas (una calculada por el modelo, la otra citada de \
literatura clínica para el cuadro), nunca la misma medición. Menciona la procedencia o confianza \
cuando sean relevantes para calibrar cuánto peso dar a tu interpretación.
5. No existe un diccionario de etiquetas legibles en la aplicación para los nombres de \
descriptor: cuando cites uno por su nombre técnico, acompáñalo tú mismo de su nombre clínico \
legible en español la primera vez que lo mencionas (p.ej. "`heart_rate` (frecuencia cardíaca)") \
— esa traducción es parte de tu trabajo, no una plantilla fija de la aplicación.
6. {depth_instruction}

Estructura tu respuesta en este orden: observación (qué cambió y desde cuándo) → mecanismo \
fisiológico (por qué ocurre) → significado clínico → qué vigilar a continuación. No agregues \
disclaimers genéricos de "esto no es un diagnóstico médico" en cada respuesta — el contexto \
educativo/simulado ya está declarado en la UI que te contiene."""


def build_system_prompt(depth: DepthLevel) -> str:
    return _SYSTEM_PROMPT_TEMPLATE.format(depth_instruction=_DEPTH_INSTRUCTIONS[depth])


def build_messages(context: NarrativeContext) -> List[dict]:
    """El contexto va como JSON en el mensaje del usuario — son datos que el
    modelo interpreta, no una pregunta en lenguaje natural preescrita."""

    payload = json.dumps(context.to_payload(), ensure_ascii=False, indent=2)
    content = (
        "Contexto estructurado del UPS (única fuente de hechos permitida):\n\n"
        f"```json\n{payload}\n```\n\n"
        "Narra qué está pasando con este paciente ahora mismo, siguiendo las reglas del "
        "system prompt."
    )
    return [{"role": "user", "content": content}]


def build_request(context: NarrativeContext, depth: DepthLevel) -> Tuple[str, List[dict]]:
    return build_system_prompt(depth), build_messages(context)
