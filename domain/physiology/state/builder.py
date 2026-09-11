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
Welch + estado derivado).

Acoplamientos Sub-fase B (2026-09-06): + `bar` (Ratio Beta/Alfa) -- un
cociente adimensional de dos band power, biomarcador CITADO (Schutter
2006), no una invención de esta app. Persiste con la procedencia de las
band power de origen (ver comentario en `_neurological_state`). Es el
ancla firmada por el experto para la regla de acoplamiento arousal->↑FC."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from src.signals.eeg.eeg_analyzer import (
    BAR_CITATION,
    DAR_CITATION,
    TBR_CITATION,
    beta_alpha_ratio,
    delta_alpha_ratio,
    theta_beta_ratio,
)

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

    # BAR (Ratio Beta/Alfa) -- Acoplamientos Sub-fase B (2026-09-06). El
    # experto rechazó `beta_power` crudo como ancla de acoplamiento (potencia
    # absoluta indefendible entre sujetos) a favor del BAR = P_beta/P_alpha,
    # que cancela las variables anatómicas y es un biomarcador CITADO (ver
    # `BAR_CITATION`), no una invención de esta app. Es un cociente
    # adimensional de DOS señales primarias del mismo dominio -> lleva la
    # MISMA procedencia que las band power de origen (no `DERIVADO`: no lo
    # calcula el organismo con pesos propios, es una identidad aritmética
    # sobre dos mediciones/simulaciones). Sin ritmo alfa medible
    # (`alpha_power` ~0) el cociente es indefinido -> no se persiste (mismo
    # criterio que el gate: solo se escribe lo que realmente hay).
    if "alpha_power" in signals and "beta_power" in signals:
        bar_value = beta_alpha_ratio(float(signals["beta_power"]), float(signals["alpha_power"]))
        if bar_value is not None:
            descriptors["bar"] = PhysiologicalDescriptor(
                "bar", bar_value, "ratio (adimensional)", provenance, confidence,
                f"{source_detail + ' | ' if source_detail else ''}beta_alpha_ratio | {BAR_CITATION}",
            )

    # DAR (Ratio Delta/Alfa) -- Neuro Tanda 1 (2026-09-10). MISMO patrón que
    # el BAR arriba: cociente adimensional de dos band power del MISMO
    # dominio -> lleva la MISMA procedencia que las band power de origen
    # (no `DERIVADO` -- es una identidad aritmética, no un cálculo del
    # organismo). Gate INDIVIDUAL, no el gate del dominio: solo si AMBAS
    # bandas (`delta_power`/`alpha_power`) están presentes Y el cociente no
    # es indefinido (alpha_power ~0) -- un escritor que envíe delta+beta
    # pero no alpha puede tener `tbr` sin `dar`, exactamente como puede
    # tener band power sin `bar`.
    #
    # Neuro Tanda 2 (2026-09-10): firma del experto aplicada --
    # `DAR_CITATION` (`eeg_analyzer.py`) pasó de `PENDING_VALIDATION` a
    # `VALIDADO_POR_FUENTE` (Claassen et al. 2004), mismo estado que el BAR.
    # El umbral clínico (🟢/🟡/🔴, `DAR_THRESHOLDS`/`classify_dar()`) está
    # definido sobre el motor de banda Welch ACTUAL -- un cambio de motor de
    # señal (FOOOF/CWT) reabriría esta validación, no la hereda; ver
    # CHANGELOG.md.
    if "delta_power" in signals and "alpha_power" in signals:
        dar_value = delta_alpha_ratio(float(signals["delta_power"]), float(signals["alpha_power"]))
        if dar_value is not None:
            descriptors["dar"] = PhysiologicalDescriptor(
                "dar", dar_value, "ratio (adimensional)", provenance, confidence,
                f"{source_detail + ' | ' if source_detail else ''}delta_alpha_ratio | {DAR_CITATION}",
            )

    # TBR (Ratio Theta/Beta) -- mismo patrón, gate individual propio
    # (`theta_power`/`beta_power`). Neuro Tanda 2: firma del experto
    # aplicada -- `TBR_CITATION` pasó de Monastra 2001/PENDING_VALIDATION a
    # Boksem et al. 2005 (VALIDADO_POR_FUENTE) -- la cita correcta para
    # fatiga cognitiva en adultos, no el discriminante de TDAH pediátrico de
    # la Tanda 1 (ver `eeg_analyzer.py` para la nota completa). Mismo umbral
    # sobre el motor Welch actual, misma barandilla de re-validación futura.
    if "theta_power" in signals and "beta_power" in signals:
        tbr_value = theta_beta_ratio(float(signals["theta_power"]), float(signals["beta_power"]))
        if tbr_value is not None:
            descriptors["tbr"] = PhysiologicalDescriptor(
                "tbr", tbr_value, "ratio (adimensional)", provenance, confidence,
                f"{source_detail + ' | ' if source_detail else ''}theta_beta_ratio | {TBR_CITATION}",
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


def _muscular_state(
    organism: "DigitalTwinOrganism", provenance: Provenance, confidence: float, source_detail: Optional[str]
) -> DomainState:
    """Capa 5A, dominio muscular Tanda 2 (2026-09-10): cuarto dominio,
    patrón COPIADO LITERAL de `_neurological_state()` de arriba, incluido
    el gate anti-órgano-fantasma.

    Señales primarias: `activation` (mean|x|/max|x| sobre sEMG filtrada, la
    computa `EmgAnalyzer`, `src/signals/emg/emg_analyzer.py`) y
    `median_frequency` (MDF del PSD de Welch, marcador de fatiga estándar).
    Ambas son cantidades reales de la señal, no invenciones de la app."""
    muscles = organism.organs["muscles"]
    signals = muscles.metrics.signals
    detail = muscles.detail

    descriptors = {}

    # Músculo fantasma (mismo criterio que cerebro/corazón/pulmón fantasma):
    # `MusculoskeletalDetail()` nace poblado con defaults de aspecto
    # plausible (`_initialize_organs()` -- recruitment_pattern=50.0,
    # motor_symmetry=90.0, neuromuscular_efficiency=80.0,
    # movement_smoothness=85.0, power_output=100.0) y
    # `muscles.metrics.health_score`/`risk_score` arrancan en 50.0/0.0,
    # todo ANTES de que `_update_muscles()` corra ni una vez. El gate se
    # basa en `activation` -- la señal primaria que `_update_muscles()`
    # realmente consume (junto a `efficiency`/`fatigue_index`), y la única
    # de las tres que se deriva de una señal sEMG real (las otras dos hoy
    # vienen del slider "Fatiga muscular" de Twin OS). Sin `activation`, el
    # dominio muscular se escribe vacío -- nunca un músculo sano por
    # defecto indistinguible de uno medido.
    has_real_muscular_input = "activation" in signals

    if "activation" in signals:
        descriptors["activation"] = PhysiologicalDescriptor(
            "activation", float(signals["activation"]), "%", provenance, confidence, source_detail
        )
    if "median_frequency" in signals:
        descriptors["median_frequency"] = PhysiologicalDescriptor(
            "median_frequency", float(signals["median_frequency"]), "Hz", provenance, confidence, source_detail
        )

    # `fatigue_index` DIFERIDO -- NO se persiste en esta tanda. La fórmula
    # (`fatigue_index_from_mdf`, corrimiento de la MDF vs. un basal de 120
    # Hz) es real y responde sobre sEMG real (fresca ~101 Hz -> fatigada
    # ~60 Hz), PERO el generador demo (`generate_demo_emg_signal`, ruido
    # blanco = espectro plano -> MDF ~fs/4) lo clava en 0.00 en los 3
    # patrones. Persistirlo desde el demo sería una constante disfrazada de
    # medición -- el mismo patrón fantasma que ya se evita con los campos
    # de detail nunca asignados (abajo). Se persistirá cuando la escritura
    # venga de CSV/hardware, o cuando el generador se recalibre con
    # propósito declarado. Esto es ausencia DELIBERADA, no olvido -- ver el
    # diagnóstico del dominio muscular y la Tanda 1 (lado señal).

    if has_real_muscular_input:
        descriptors["health_score"] = PhysiologicalDescriptor(
            "health_score", float(muscles.metrics.health_score), "0-100", Provenance.DERIVADO, confidence, source_detail
        )
        descriptors["risk_score"] = PhysiologicalDescriptor(
            "risk_score", float(muscles.metrics.risk_score), "0-100", Provenance.DERIVADO, confidence, source_detail
        )
        if detail is not None:
            # NOTA: `recruitment_pattern`/`motor_symmetry`/`power_output`
            # (MusculoskeletalDetail) NUNCA se asignan en `_update_muscles()`
            # -- confirmado por lectura completa del método -- se quedan
            # para siempre en su default de dataclass (50.0/90.0/100.0).
            # Escribirlos al UPS sería persistir una constante disfrazada de
            # medición -- el análogo EXACTO de `frontal_activity`/
            # `temporal_activity` que `_neurological_state()` excluye por lo
            # mismo. Se omiten a propósito; solo los 2 campos que sí computa
            # cada vez.
            descriptors["neuromuscular_efficiency"] = PhysiologicalDescriptor(
                "neuromuscular_efficiency", float(detail.neuromuscular_efficiency), "0-100",
                Provenance.DERIVADO, confidence, source_detail
            )
            descriptors["movement_smoothness"] = PhysiologicalDescriptor(
                "movement_smoothness", float(detail.movement_smoothness), "0-100",
                Provenance.DERIVADO, confidence, source_detail
            )

    return DomainState(domain="muscular", descriptors=descriptors)


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
    muscle_signals = organism.organs["muscles"].metrics.signals

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

    # Capa 5A, dominio muscular Tanda 2 (2026-09-10): único evento muscular,
    # mismo umbral que YA usa `_update_muscles()` para su tier más alto de
    # `risk_score` (`fatigue > 80` -> 70) -- no se inventa un criterio
    # clínico nuevo. `fatigue_index` NO se persiste como descriptor todavía
    # (diferido -- generador demo roto, ver `_muscular_state()`), pero el
    # evento lee la señal cruda del organismo directamente, exactamente
    # como el evento de EEG lee `stress_level` sin persistirlo. Sobre el
    # generador demo (`fatigue_index` clavado en 0) este evento nunca
    # dispara -- disparará cuando la escritura venga de sEMG real fatigada.
    fatigue_index = muscle_signals.get("fatigue_index")
    if fatigue_index is not None and fatigue_index > 80:
        events.append(
            PhysiologicalEvent(
                event_type=EventType.SEVERE_MUSCLE_FATIGUE_EMG,
                domain="muscular",
                severity=EventSeverity.WARNING,
                description=f"Fatiga muscular severa según EMG: índice {fatigue_index:.0f}/100",
                provenance=provenance,
                confidence=confidence,
                timestamp=timestamp,
                related_descriptor="movement_smoothness",
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
    neurológico + muscular, desde la Capa 5A).

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
    muscular = _muscular_state(organism, provenance, confidence, source_detail)
    events = _detect_events(organism, provenance, confidence, timestamp)

    return UnifiedPhysiologicalState(
        patient_id=patient_id,
        timestamp=timestamp,
        cardiovascular=cardiovascular,
        respiratory=respiratory,
        neurological=neurological,
        muscular=muscular,
        events=events,
    )
