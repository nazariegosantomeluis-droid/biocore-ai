"""
Fase 1.3 — Contexto estructurado para el narrador clínico.

Esto es lo que separa al narrador de un chatbot: antes de llamar al modelo,
se arma un contexto de datos (no prosa) leído directamente del UPS —
descriptores actuales con procedencia/confianza, eventos activos, y una
comparación temporal explícita (antes/ahora) para cada descriptor, usando
la consulta temporal que ya existe (`get_value_history`). El modelo
interpreta estos datos; no los inventa.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from domain.physiology.state import get_events, get_latest_state, get_value_history


@dataclass(frozen=True)
class DescriptorContext:
    """Un descriptor con su valor actual, procedencia/confianza, y la
    comparación temporal antes/ahora dentro de la ventana observada."""

    domain: str
    name: str
    value: float
    unit: str
    provenance: str
    confidence: float
    now_timestamp: str
    before_value: Optional[float]
    before_timestamp: Optional[str]
    window_snapshot_count: int

    def to_payload(self) -> dict:
        return {
            "domain": self.domain,
            "descriptor": self.name,
            "value": self.value,
            "unit": self.unit,
            "provenance": self.provenance,
            "confidence": self.confidence,
            "now_timestamp": self.now_timestamp,
            "before_value": self.before_value,
            "before_timestamp": self.before_timestamp,
            "window_snapshot_count": self.window_snapshot_count,
        }


@dataclass(frozen=True)
class EventContext:
    """Un evento persistido, citable por su `event_type` exacto."""

    event_type: str
    domain: str
    severity: str
    description: str
    provenance: str
    confidence: float
    timestamp: str
    related_descriptor: Optional[str]

    def to_payload(self) -> dict:
        return {
            "event_type": self.event_type,
            "domain": self.domain,
            "severity": self.severity,
            "description": self.description,
            "provenance": self.provenance,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
            "related_descriptor": self.related_descriptor,
        }


@dataclass(frozen=True)
class NarrativeContext:
    """Contexto completo que se envía al modelo como datos estructurados —
    la única fuente de hechos permitida para la narración."""

    patient_id: str
    generated_at: str
    descriptors: List[DescriptorContext] = field(default_factory=list)
    events: List[EventContext] = field(default_factory=list)

    def to_payload(self) -> dict:
        return {
            "patient_id": self.patient_id,
            "generated_at": self.generated_at,
            "descriptors": [d.to_payload() for d in self.descriptors],
            "events": [e.to_payload() for e in self.events],
        }


def build_context(
    session: Session,
    patient_id: str,
    window_snapshots: int = 10,
    max_events: int = 10,
) -> NarrativeContext:
    """Construye el contexto estructurado del narrador a partir del UPS.

    Para cada descriptor del snapshot más reciente, consulta su trayectoria
    (`get_value_history`) y toma el primer y el último punto dentro de los
    últimos `window_snapshots` puntos como comparación antes/ahora — la
    prueba de fundamentación temporal que exige la Fase 1.3. Si solo hay un
    punto en la ventana, `before_value` queda en None (no se inventa un
    "antes" que no existe).
    """

    latest = get_latest_state(session, patient_id)
    if latest is None:
        raise ValueError(f"No hay estado UPS para el paciente {patient_id!r} — nada que narrar todavía.")

    now_ts = latest.timestamp.isoformat()

    descriptors: List[DescriptorContext] = []
    for domain_state in latest.all_domains().values():
        for descriptor in domain_state.descriptors.values():
            history = get_value_history(session, patient_id, domain_state.domain, descriptor.name)
            window = history[-window_snapshots:]

            before_value: Optional[float] = None
            before_timestamp: Optional[str] = None
            if len(window) >= 2:
                before_ts, before_val = window[0]
                before_value = before_val
                before_timestamp = before_ts.isoformat()

            descriptors.append(
                DescriptorContext(
                    domain=domain_state.domain,
                    name=descriptor.name,
                    value=descriptor.value,
                    unit=descriptor.unit,
                    provenance=descriptor.provenance.value,
                    confidence=descriptor.confidence,
                    now_timestamp=now_ts,
                    before_value=before_value,
                    before_timestamp=before_timestamp,
                    window_snapshot_count=len(window),
                )
            )

    events = get_events(session, patient_id)[-max_events:]
    event_contexts = [
        EventContext(
            event_type=e.event_type.value,
            domain=e.domain,
            severity=e.severity.value,
            description=e.description,
            provenance=e.provenance.value,
            confidence=e.confidence,
            timestamp=e.timestamp.isoformat(),
            related_descriptor=e.related_descriptor,
        )
        for e in events
    ]

    return NarrativeContext(
        patient_id=patient_id,
        generated_at=datetime.now(timezone.utc).isoformat(),
        descriptors=descriptors,
        events=event_contexts,
    )
