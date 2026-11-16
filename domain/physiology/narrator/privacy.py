"""
Qué datos puede recibir cada proveedor de IA del narrador (2026-11-16).

Los términos adicionales de la API de Gemini (versión del 18 de diciembre de 2025) dicen, para los servicios sin
pago, que Google usa lo que se manda y las respuestas para mejorar sus productos, que personas pueden leerlo y
anotarlo, y que no se mande información sensible, confidencial o personal. Por eso un proveedor sin pago
(`allows_personal_data = False`, hoy el nivel gratuito de Gemini) solo recibe datos que BIOCORE sabe que no son de
una persona:

- `SIMULADO`: lo genera la app (escenarios, casos sintéticos, señales demo, placas simuladas).
- `BASE_PUBLICA`: registros publicados y anonimizados (MIT-BIH, PTB-XL).

Lo demás se bloquea antes de llamar al proveedor, con el motivo (`ProviderNotAllowedError`):

- `PERSONA`: un sensor en vivo (SENSOR_REAL), una entrada manual de paciente o un juicio clínico con nombre.
- `DESCONOCIDO`: lo que no se sabe de dónde viene (un CSV cargado, una serie RR escrita a mano, un flujo LSL que
  BIOCORE no puede verificar, o una ruta nueva que todavía no está en `classify_source`). Cuenta como de una persona.

Con Anthropic (clave de pago de la persona) nada cambia: su cliente no declara `allows_personal_data = False`.
"""

from __future__ import annotations

from enum import Enum
from typing import Iterable, Optional

from .errors import ProviderNotAllowedError

__all__ = [
    "DataOrigin",
    "SHAREABLE_ORIGINS",
    "ProviderNotAllowedError",
    "classify_source",
    "worst_origin",
    "check_provider_allows",
]

GEMINI_TERMS = (
    "Términos adicionales de la API de Gemini (versión del 18 de diciembre de 2025), servicios sin pago: Google usa "
    "lo que se manda para mejorar sus productos, personas pueden leerlo, y piden no mandar información sensible, "
    "confidencial o personal."
)


class DataOrigin(str, Enum):
    SIMULADO = "simulado"
    BASE_PUBLICA = "base_publica"
    PERSONA = "persona"
    DESCONOCIDO = "desconocido"


SHAREABLE_ORIGINS = frozenset({DataOrigin.SIMULADO, DataOrigin.BASE_PUBLICA})
_RANK = {DataOrigin.SIMULADO: 0, DataOrigin.BASE_PUBLICA: 1, DataOrigin.DESCONOCIDO: 2, DataOrigin.PERSONA: 3}
ORIGIN_TEXT = {
    DataOrigin.SIMULADO: "datos simulados por BIOCORE",
    DataOrigin.BASE_PUBLICA: "registros de una base pública anonimizada",
    DataOrigin.PERSONA: "datos de una persona (un sensor en vivo, una entrada manual de paciente o un juicio clínico "
                        "con nombre)",
    DataOrigin.DESCONOCIDO: "datos de origen desconocido (por ejemplo, un archivo cargado o una serie escrita a mano)",
}

# Marcas en `source_detail` (en minúsculas). Se revisan en este orden: primero lo que es de una persona, luego lo que
# no se puede saber, luego las bases públicas y al final lo simulado. Sin ninguna marca: DESCONOCIDO.
_PERSON_MARKS = ("sensor_real", "patient_pipeline")
_UNKNOWN_MARKS = ("csv", "manual rr", "no verificable", "error de carga")
_PUBLIC_MARKS = ("mit-bih", "ptb-xl")
_SIMULATED_MARKS = (
    "simulaci",                          # «SIMULACIÓN» de las placas simuladas, «Simulación: acoplamiento…» del HRV
    "sintético", "sintetico",            # EEG sintético, ECG sintético del Twin OS
    "escenario",                         # motor de escenarios y escenarios ricos
    "scenario_simulator",                # el simulador de escenarios del Twin OS
    "comparacion_en_contexto",
    "twin_visual", "twin_shell_clinical_case_mode",
    "narrador:snapshot", "razonamiento_causal:snapshot",
    "estado_actual_en_memoria",
    "academia_synthetic_case",
    "respiratory_lab:",                  # el generador respiratorio (el laboratorio no carga señales de afuera)
    "caso clínico", "caso clinico",      # los 61 casos clínicos sintéticos del ECG Lab
    "origen=demo", "ecg_lab:demo",
)


def classify_source(provenance: Optional[str], source_detail: Optional[str]) -> DataOrigin:
    """Origen de UN valor del UPS, por su procedencia y su `source_detail`."""
    if (provenance or "").lower() == "sensor_real":
        return DataOrigin.PERSONA
    detail = (source_detail or "").lower()
    if any(mark in detail for mark in _PERSON_MARKS):
        return DataOrigin.PERSONA
    if any(mark in detail for mark in _UNKNOWN_MARKS):
        return DataOrigin.DESCONOCIDO
    if any(mark in detail for mark in _PUBLIC_MARKS):
        return DataOrigin.BASE_PUBLICA
    if any(mark in detail for mark in _SIMULATED_MARKS):
        return DataOrigin.SIMULADO
    return DataOrigin.DESCONOCIDO


def worst_origin(origins: Iterable[DataOrigin]) -> DataOrigin:
    """El origen más restrictivo de un conjunto (un contexto vacío no tiene datos de nadie: SIMULADO)."""
    return max(origins, key=_RANK.__getitem__, default=DataOrigin.SIMULADO)


def check_provider_allows(client, origin: DataOrigin) -> None:
    """Lanza `ProviderNotAllowedError` si `client` no puede recibir datos de este origen."""
    if getattr(client, "allows_personal_data", True) or origin in SHAREABLE_ORIGINS:
        return
    name = getattr(client, "provider_name", "este proveedor")
    raise ProviderNotAllowedError(
        f"Con {name} solo se explican datos simulados o de bases públicas, y aquí hay {ORIGIN_TEXT[origin]}. "
        "Sus términos piden no mandarle información personal o sensible. Cambia a una fuente simulada, o entra con "
        "una clave de Anthropic (en «Ajustes», menú lateral)."
    )
