"""
Unified Physiological State — builder desde `DigitalTwinOrganism`.

`app/engines/digital_twin_organism.py` no se modifica: este módulo solo lo
lee y traduce su estado (heart/lungs/brain) al esquema tipado del UPS. Los
valores medidos/simulados (heart_rate, hrv, spo2, respiratory_rate,
band power EEG) llevan la procedencia que indique el llamador; los
valores que el organismo ya calcula a partir de esos (health_score,
riesgos, rhythm_stability, ...) siempre se marcan `Provenance.DERIVADO`,
sin importar la procedencia de origen — es una cantidad distinta,
calculada, no observada.

Los eventos usan los mismos umbrales que ya vive en
`DigitalTwinOrganism._update_heart` / `_update_lungs` / `_update_brain`,
para no introducir un segundo criterio clínico paralelo.

Capa 5A, Sub-fase 1 (2026-08-30): tercer dominio, neurológico
(`_neurological_state()`) -- mismo patrón y misma disciplina de gate
anti-órgano-fantasma que cardiovascular/respiratorio. Escribe lo que
`EegAnalyzer` (`src/signals/eeg/eeg_analyzer.py`) ya calcula (band power
Welch + estado derivado) -- no construye biomarcadores nuevos."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from .schema import (
    DomainState,
    EventSeverity,
    EventType,
    PhysiologicalDescriptor,
    PhysiologicalEvent,
    Provenance,
    UnifiedPhysiologicalState,
    default_confidence,
)

if TYPE_CHECKING:
    from app.engines.digital_twin_organism import DigitalTwinOrganism


def _cardiovascular_state(
    organism: "DigitalTwinOrganism", provenance: Provenance, confidence: float, source_detail: Optional[str]
) -> DomainState:
    heart = organism.organs["heart"]
    signals = heart.metrics.signals
    detail = heart.detail

    descriptors = {}

    # Corazón fantasma (2026-08-22, Capa 2 Fase 2.4, Art. I): `heart.detail`
    # nace poblado con defaults de aspecto plausible (CardiacDetail(),
    # digital_twin_organism.py `_initialize_organs()` -- cardiac_output=5.0,
    # rhythm_stability=85.0, myocardial_stress=30.0) ANTES de que
    # `_update_heart()` corra ni una vez, y `heart.metrics.health_score`/
    # `risk_score` arrancan en 50.0/0.0 por el mismo motivo (OrganMetrics,
    # misma clase). Antes, health_score/risk_score/detail.* se escribían
    # aquí SIN el gate que sí protegía a heart_rate/hrv -- cualquier llamador
    # que pasara `update_from_sensors({"respiratory": {...}})` sin `"ecg"`
    # (el caso de Respiratory Lab, Fase 2.4; ya reproducible hoy vía Twin OS:
    # botón "🔴 EPOC" -- create_patient_scenario("copd"), que solo toca
    # lungs -- seguido de cualquiera de los 3 botones "snapshot bajo
    # demanda") persistía un corazón sano, completo, Provenance.DERIVADO,
    # indistinguible de uno medido. Gate simétrico al de heart_rate/hrv: sin
    # dato cardíaco real de entrada, el dominio cardiovascular se escribe
    # vacío -- "sin datos", nunca "corazón sano por defecto". Diagnóstico de
    # consumidores (Paso 1) confirmó que ninguno asume presencia incondicional
    # de estos 5 descriptores -- ver CHANGELOG.md.
    has_real_cardiac_input = "heart_rate" in signals

    if "heart_rate" in signals:
        descriptors["heart_rate"] = PhysiologicalDescriptor(
            "heart_rate", float(signals["heart_rate"]), "bpm", provenance, confidence, source_detail
        )
    if "hrv" in signals:
        descriptors["hrv"] = PhysiologicalDescriptor(
            "hrv", float(signals["hrv"]), "ms", provenance, confidence, source_detail
        )

    if has_real_cardiac_input:
        descriptors["health_score"] = PhysiologicalDescriptor(
            "health_score", float(heart.metrics.health_score), "0-100", Provenance.DERIVADO, confidence, source_detail
        )
        descriptors["risk_score"] = PhysiologicalDescriptor(
            "risk_score", float(heart.metrics.risk_score), "0-100", Provenance.DERIVADO, confidence, source_detail
        )
        if detail is not None:
            descriptors["rhythm_stability"] = PhysiologicalDescriptor(
                "rhythm_stability", float(detail.rhythm_stability), "0-100", Provenance.DERIVADO, confidence, source_detail
            )
            descriptors["myocardial_stress"] = PhysiologicalDescriptor(
                "myocardial_stress", float(detail.myocardial_stress), "0-100", Provenance.DERIVADO, confidence, source_detail
            )
            descriptors["cardiac_output"] = PhysiologicalDescriptor(
                "cardiac_output", float(detail.cardiac_output), "L/min", Provenance.DERIVADO, confidence, source_detail
            )

    return DomainState(domain="cardiovascular", descriptors=descriptors)


def _respiratory_state(
    organism: "DigitalTwinOrganism", provenance: Provenance, confidence: float, source_detail: Optional[str]
) -> DomainState:
    lungs = organism.organs["lungs"]
    signals = lungs.metrics.signals
    detail = lungs.detail

    descriptors = {}

    # Pulmón fantasma (2026-08-22, Capa 2 Fase 2.4, Art. I): gate simétrico al
    # de _cardiovascular_state() -- `lungs.detail` nace poblado con defaults
    # de aspecto plausible (RespiratoryDetail(), digital_twin_organism.py
    # `_initialize_organs()` -- hypoxia_risk=10.0, apnea_risk=5.0,
    # tissue_oxygenation=80.0) y `lungs.metrics.health_score`/`risk_score`
    # arrancan en 50.0/0.0, todo antes de que `_update_lungs()` corra ni una
    # vez. Sin este gate, un escritor cardio-únicamente (HRV, ECG -- las
    # próximas dos integraciones estrechas) persistiría unos pulmones sanos,
    # completos, Provenance.DERIVADO, indistinguibles de una medición real.
    # Mismo criterio que protege heart_rate/hrv en el dominio cardiovascular.
    has_real_respiratory_input = "respiratory_rate" in signals

    if "respiratory_rate" in signals:
        descriptors["respiratory_rate"] = PhysiologicalDescriptor(
            "respiratory_rate", float(signals["respiratory_rate"]), "resp/min", provenance, confidence, source_detail
        )
    if "spo2" in signals:
        descriptors["spo2"] = PhysiologicalDescriptor(
            "spo2", float(signals["spo2"]), "%", provenance, confidence, source_detail
        )
    # Fase 2 (2026-08-12), fisiología real de apnea/EPOC: `ahi` ya llegaba a
    # `lungs.metrics.signals` (copiado íntegro por `_update_lungs()`, ver
    # `digital_twin_organism.py`) pero se perdía aquí -- nunca se convertía
    # en PhysiologicalDescriptor, así que el UPS (y por lo tanto el
    # Narrador Clínico, que solo lee del UPS vía `build_context()`) no
    # podía citarlo. `build_context()` es genérico (itera TODOS los
    # descriptores de cada dominio, sin lista fija) -- exponerlo aquí basta
    # para que el narrador lo use, sin tocar `narrator/context.py` ni
    # `prompt.py`. Aditivo para los 12 escenarios (todos pasan `ahi` en su
    # `SimulationTimestep`, la mayoría con valores bajos/0 -- ninguno
    # perdía nada antes, solo apnea necesitaba que esto existiera).
    if "ahi" in signals:
        descriptors["ahi"] = PhysiologicalDescriptor(
            "ahi", float(signals["ahi"]), "eventos/h", provenance, confidence, source_detail
        )

    if has_real_respiratory_input:
        descriptors["health_score"] = PhysiologicalDescriptor(
            "health_score", float(lungs.metrics.health_score), "0-100", Provenance.DERIVADO, confidence, source_detail
        )
        descriptors["risk_score"] = PhysiologicalDescriptor(
            "risk_score", float(lungs.metrics.risk_score), "0-100", Provenance.DERIVADO, confidence, source_detail
        )
        if detail is not None:
            descriptors["hypoxia_risk"] = PhysiologicalDescriptor(
                "hypoxia_risk", float(detail.hypoxia_risk), "0-100", Provenance.DERIVADO, confidence, source_detail
            )
            descriptors["apnea_risk"] = PhysiologicalDescriptor(
                "apnea_risk", float(detail.apnea_risk), "0-100", Provenance.DERIVADO, confidence, source_detail
            )
            descriptors["tissue_oxygenation"] = PhysiologicalDescriptor(
                "tissue_oxygenation", float(detail.tissue_oxygenation), "0-100", Provenance.DERIVADO, confidence, source_detail
            )

    return DomainState(domain="respiratory", descriptors=descriptors)


def _neurological_state(
    organism: "DigitalTwinOrganism", provenance: Provenance, confidence: float, source_detail: Optional[str]
) -> DomainState:
    """Capa 5A, Sub-fase 1 (2026-08-30): tercer dominio, mismo patrón que
    `_cardiovascular_state()`/`_respiratory_state()` de arriba, incluido el
    gate anti-órgano-fantasma.

    Band power: los 5 valores que `EegAnalyzer.analyze()`
    (`src/signals/eeg/eeg_analyzer.py`) ya calcula vía PSD de Welch --
    fronteras de banda estándar de texto (delta/theta/alpha/beta/gamma),
    citables como DEFINICIÓN, no como referencia clínica de rango sano (no
    existe una en este slice, igual que corazón/pulmón no citan sus PESOS
    de fórmula, solo su punto de referencia)."""
    brain = organism.organs["brain"]
    signals = brain.metrics.signals
    detail = brain.detail

    descriptors = {}

    # Cerebro fantasma (Capa 5A, mismo criterio que corazón/pulmón fantasma
    # de la Fase 2.4): `brain.detail` nace poblado con defaults de aspecto
    # plausible (NeurologicalDetail(), `_initialize_organs()` --
    # mental_workload=40.0, attention=70.0, etc.) y `brain.metrics.
    # health_score`/`risk_score` arrancan en 50.0/0.0, todo ANTES de que
    # `_update_brain()` corra ni una vez. El gate se basa en `alpha_power`/
    # `beta_power` -- las dos señales que `_update_brain()` realmente
    # consume para health_score/activity_level/risk_score/detail (mismo
    # nivel de rigor que el gate cardiovascular, que tampoco exige que
    # CADA sub-entrada de la fórmula -- ahí hrv/complexity -- sea real,
    # solo la señal primaria del órgano). Sin ninguna de las dos, el
    # dominio neurológico se escribe vacío -- nunca un cerebro sano por
    # defecto indistinguible de uno medido.
    has_real_neuro_input = "alpha_power" in signals or "beta_power" in signals

    for band in ("delta_power", "theta_power", "alpha_power", "beta_power", "gamma_power"):
        if band in signals:
            descriptors[band] = PhysiologicalDescriptor(
                band, float(signals[band]), "power (u.a.)", provenance, confidence, source_detail
            )

    if has_real_neuro_input:
        descriptors["health_score"] = PhysiologicalDescriptor(
            "health_score", float(brain.metrics.health_score), "0-100", Provenance.DERIVADO, confidence, source_detail
        )
        descriptors["risk_score"] = PhysiologicalDescriptor(
            "risk_score", float(brain.metrics.risk_score), "0-100", Provenance.DERIVADO, confidence, source_detail
        )
        if detail is not None:
            # NOTA: `frontal_activity`/`temporal_activity` (NeurologicalDetail)
            # NUNCA se asignan en `_update_brain()` -- confirmado por lectura
            # completa del método -- se quedan para siempre en su default de
            # dataclass (55.0/45.0). Escribirlos al UPS sería persistir una
            # constante disfrazada de medición -- el mismo patrón de "campo
            # fantasma" que ya se evitó con `trend`/`status` en Fase 1/2. Se
            # omiten a propósito; solo los 5 campos que sí computa cada vez.
            descriptors["mental_workload"] = PhysiologicalDescriptor(
                "mental_workload", float(detail.mental_workload), "0-100", Provenance.DERIVADO, confidence, source_detail
            )
            descriptors["cognitive_fatigue"] = PhysiologicalDescriptor(
                "cognitive_fatigue", float(detail.cognitive_fatigue), "0-100", Provenance.DERIVADO, confidence, source_detail
            )
            descriptors["attention"] = PhysiologicalDescriptor(
                "attention", float(detail.attention), "0-100", Provenance.DERIVADO, confidence, source_detail
            )
            descriptors["stress_perception"] = PhysiologicalDescriptor(
                "stress_perception", float(detail.stress_perception), "0-100", Provenance.DERIVADO, confidence, source_detail
            )
            descriptors["sleepiness"] = PhysiologicalDescriptor(
                "sleepiness", float(detail.sleepiness), "0-100", Provenance.DERIVADO, confidence, source_detail
            )

    return DomainState(domain="neurological", descriptors=descriptors)


def _detect_events(
    organism: "DigitalTwinOrganism", provenance: Provenance, confidence: float, timestamp: datetime
) -> List[PhysiologicalEvent]:
    """Umbrales idénticos a los ya usados en
    DigitalTwinOrganism._update_heart / _update_lungs — el evento es una
    lectura distinta del mismo criterio clínico, no uno nuevo."""

    events: List[PhysiologicalEvent] = []
    heart_signals = organism.organs["heart"].metrics.signals
    lungs_signals = organism.organs["lungs"].metrics.signals
    brain_signals = organism.organs["brain"].metrics.signals

    hr = heart_signals.get("heart_rate")
    hrv = heart_signals.get("hrv")
    if hr is not None and (hr > 120 or hr < 40):
        severity = EventSeverity.CRITICAL if (hr > 150 or hr < 35) else EventSeverity.WARNING
        events.append(
            PhysiologicalEvent(
                event_type=EventType.ARRHYTHMIA_RISK_HR_EXTREME,
                domain="cardiovascular",
                severity=severity,
                description=f"Frecuencia cardíaca fuera de rango seguro: {hr:.0f} bpm",
                provenance=provenance,
                confidence=confidence,
                timestamp=timestamp,
                related_descriptor="heart_rate",
            )
        )
    elif hrv is not None and hrv < 20:
        events.append(
            PhysiologicalEvent(
                event_type=EventType.LOW_HRV_AUTONOMIC_STRESS,
                domain="cardiovascular",
                severity=EventSeverity.WARNING,
                description=f"HRV bajo, posible estrés autonómico: {hrv:.0f} ms",
                provenance=provenance,
                confidence=confidence,
                timestamp=timestamp,
                related_descriptor="hrv",
            )
        )

    spo2 = lungs_signals.get("spo2")
    if spo2 is not None and spo2 < 90:
        events.append(
            PhysiologicalEvent(
                event_type=EventType.HYPOXIA_SPO2_CRITICAL,
                domain="respiratory",
                severity=EventSeverity.CRITICAL,
                description=f"SpO2 crítico: {spo2:.0f}%",
                provenance=provenance,
                confidence=confidence,
                timestamp=timestamp,
                related_descriptor="spo2",
            )
        )
    elif spo2 is not None and spo2 < 95:
        events.append(
            PhysiologicalEvent(
                event_type=EventType.HYPOXIA_SPO2_LOW,
                domain="respiratory",
                severity=EventSeverity.WARNING,
                description=f"SpO2 bajo lo esperado: {spo2:.0f}%",
                provenance=provenance,
                confidence=confidence,
                timestamp=timestamp,
                related_descriptor="spo2",
            )
        )

    # Capa 5A, Sub-fase 1 (2026-08-30): único evento neuro, mismo umbral
    # que YA usa `_update_brain()` para su propio `risk_score` (el tier más
    # alto que ese método define, `stress_level > 75`) -- no se inventa un
    # umbral clínico nuevo. `stress_level` no se persiste como descriptor
    # crudo (solo band power + los 5 campos derivados) -- el evento lee la
    # señal cruda del organismo directamente, igual que arriba HR/HRV/SpO2
    # se leen de `*_signals`, no de descriptores ya construidos.
    stress_level = brain_signals.get("stress_level")
    if stress_level is not None and stress_level > 75:
        events.append(
            PhysiologicalEvent(
                event_type=EventType.HIGH_STRESS_EEG,
                domain="neurological",
                severity=EventSeverity.WARNING,
                description=f"Estrés elevado según EEG: nivel {stress_level:.0f}/100",
                provenance=provenance,
                confidence=confidence,
                timestamp=timestamp,
                related_descriptor="stress_perception",
            )
        )

    return events


def from_digital_twin_organism(
    organism: "DigitalTwinOrganism",
    patient_id: str,
    provenance: Provenance = Provenance.SIMULACION,
    confidence: Optional[float] = None,
    source_detail: Optional[str] = None,
) -> UnifiedPhysiologicalState:
    """Construye un `UnifiedPhysiologicalState` a partir del estado actual
    de un `DigitalTwinOrganism` (cardiovascular + respiratorio +
    neurológico, desde la Capa 5A).

    `provenance`/`confidence` describen los valores medidos/simulados
    (heart_rate, hrv, spo2, respiratory_rate). Los valores que el organismo
    ya deriva (health_score, riesgos, etc.) se marcan siempre como
    `Provenance.DERIVADO`. Si no se pasa `confidence`, se toma el punto
    medio de la banda de referencia de `provenance` (`CONFIDENCE_REFERENCE`)
    en lugar de un número arbitrario.
    """
    if confidence is None:
        confidence = default_confidence(provenance)

    # organism.timestamp viene de datetime.now() (naive, hora local). astimezone()
    # sin argumentos en un datetime naive lo interpreta como hora local del sistema
    # y permite convertirlo correctamente a UTC — replace(tzinfo=utc) sería incorrecto
    # (relabelearía la hora local como si ya fuera UTC).
    timestamp = organism.timestamp
    if timestamp.tzinfo is None:
        timestamp = timestamp.astimezone()
    timestamp = timestamp.astimezone(timezone.utc)

    cardiovascular = _cardiovascular_state(organism, provenance, confidence, source_detail)
    respiratory = _respiratory_state(organism, provenance, confidence, source_detail)
    neurological = _neurological_state(organism, provenance, confidence, source_detail)
    events = _detect_events(organism, provenance, confidence, timestamp)

    return UnifiedPhysiologicalState(
        patient_id=patient_id,
        timestamp=timestamp,
        cardiovascular=cardiovascular,
        respiratory=respiratory,
        neurological=neurological,
        events=events,
    )
