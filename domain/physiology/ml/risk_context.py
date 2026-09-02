"""
Tanda 4, Pieza 1 (2026-07-04) — Puente entre el UPS y el scoring de riesgo
real (`src.ai.patient_analytics.PatientRiskPredictor`).

Mismo patrón que `domain/physiology/narrator/context.py::build_context()`:
lee el UPS (descriptores del snapshot más reciente + historial real +
eventos), arma un vector de features de solo lectura. No modifica ningún
archivo de `domain/physiology/state/` ni `narrator/`.

`RiskFeatures` refleja honestamente qué existe en el UPS y qué no. Presión
arterial, Paso 1+2 (2026-07-18): `systolic_bp`/`diastolic_bp` ahora se leen,
cuando existen, de `ClinicalReferenceValue` (`clinical_reference.py`) — un
valor de referencia clínica citado, transcrito de literatura clínica para
el cuadro del escenario, NUNCA medido ni simulado dinámicamente. Siguen en
`None` para pacientes/escenarios sin esa referencia (p.ej. fatiga, EPOC —
sin fuente transcrita todavía) o sin ningún escenario corrido. `age` sigue
en `None` siempre: el UPS no modela demografía en absoluto, sin cambios."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from sqlalchemy.orm import Session

from domain.physiology.state import (
    EventType,
    get_clinical_references_for_snapshot,
    get_latest_snapshot_id,
    get_latest_state,
    get_value_history,
)

MAX_TREND_POINTS = 7

# --- Decisión explícita (Conexión al UPS de los 3 escenarios validados,
# 2026-08-01): con la PA calculada por el lazo cerrado (`systolic_bp_modelo`/
# `diastolic_bp_modelo`, Provenance.MODELO_HEMODINAMICO) ahora persistida en el
# UPS para healthy/hypertension/sepsis, hay DOS fuentes posibles de PA para este
# vector de riesgo. Se decidió deliberadamente NO cambiar nada abajo -- este
# módulo sigue leyendo systolic_bp/diastolic_bp EXCLUSIVAMENTE de
# `ClinicalReferenceValue` (la referencia citada de literatura clínica), no de
# los descriptores `_modelo`. Razón: la referencia es un valor citado y estable
# por escenario; la PA calculada es un valor didáctico/comparativo -- útil para
# que el estudiante compare "lo que predice el modelo" contra "lo que dice la
# literatura", pero el score de riesgo mismo debe apoyarse en la fuente más
# citable, no en el cálculo más nuevo. Si algún día se prefiere que el riesgo
# use la PA calculada (p.ej. porque cubra más escenarios que la referencia),
# ese es un cambio deliberado aparte, no una consecuencia automática de
# conectar el modelo al UPS.

__all__ = ["RiskFeatures", "build_risk_features"]


@dataclass(frozen=True)
class RiskFeatures:
    """Vector de features real, listo para `PatientRiskPredictor.calculate_risk_score()`.

    `heart_rate`/`hrv_sdnn` son `None` si el UPS todavía no tiene ese
    descriptor para el paciente (organismo recién creado, sin señales).
    `systolic_bp`/`diastolic_bp` son `None` si el escenario que generó el
    snapshot más reciente no tiene una referencia de PA transcrita (ver
    `blood_pressure_references.py`) — nunca un valor típico inventado.
    `age` sigue sin modelarse en el UPS."""

    heart_rate: Optional[float]
    hrv_sdnn: Optional[float]  # el UPS solo modela un "hrv" genérico en ms — se usa como proxy de SDNN
    ecg_pattern: str  # derivado de eventos reales del UPS (nunca fabricado): 'arrhythmia' o 'normal'
    trend_data: List[float] = field(default_factory=list)  # historial real de heart_rate

    # El UPS (Fase 1.1) no modela demografía en absoluto -- age se deja
    # explícito en `None` para que quede claro que fue considerado y
    # descartado por falta de una fuente real, no omitido por descuido.
    age: Optional[int] = None
    systolic_bp: Optional[float] = None
    diastolic_bp: Optional[float] = None


def build_risk_features(session: Session, patient_id: str) -> Optional[RiskFeatures]:
    """Construye el vector de features desde el snapshot más reciente del UPS.

    Devuelve `None` si el paciente no tiene ningún snapshot todavía — no hay
    nada real que puntuar (igual que `build_context()` del narrador, que
    también falla explícito en ese caso en vez de fabricar un contexto)."""
    state = get_latest_state(session, patient_id)
    if state is None:
        return None

    cardio = state.all_domains()["cardiovascular"]
    hr_desc = cardio.get("heart_rate")
    hrv_desc = cardio.get("hrv")

    ecg_pattern = "normal"
    for event in state.events:
        if event.domain == "cardiovascular" and event.event_type == EventType.ARRHYTHMIA_RISK_HR_EXTREME:
            ecg_pattern = "arrhythmia"
            break

    history = get_value_history(session, patient_id, "cardiovascular", "heart_rate")
    trend_data = [value for _, value in history[-MAX_TREND_POINTS:]]

    systolic_bp: Optional[float] = None
    diastolic_bp: Optional[float] = None
    latest_snapshot_id = get_latest_snapshot_id(session, patient_id)
    if latest_snapshot_id is not None:
        for reference in get_clinical_references_for_snapshot(session, latest_snapshot_id):
            if reference.descriptor == "systolic_bp":
                systolic_bp = reference.value
            elif reference.descriptor == "diastolic_bp":
                diastolic_bp = reference.value

    return RiskFeatures(
        heart_rate=hr_desc.value if hr_desc is not None else None,
        hrv_sdnn=hrv_desc.value if hrv_desc is not None else None,
        ecg_pattern=ecg_pattern,
        trend_data=trend_data,
        systolic_bp=systolic_bp,
        diastolic_bp=diastolic_bp,
    )
