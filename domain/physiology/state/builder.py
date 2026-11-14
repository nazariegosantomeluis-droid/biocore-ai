"""
Unified Physiological State — builder desde `DigitalTwinOrganism`.

`app/engines/digital_twin_organism.py` no se modifica: este módulo solo lo
lee y traduce su estado (heart/lungs/brain) al esquema tipado del UPS. Los
valores medidos/simulados (heart_rate, hrv, spo2, respiratory_rate,
band power EEG) llevan la procedencia que indique el llamador; los
valores que el organismo ya calcula a partir de esos (puntos NEWS2, índice de
salud pulmonar) siempre se marcan `Provenance.DERIVADO`,
sin importar la procedencia de origen — es una cantidad distinta,
calculada, no observada. C0 (2026-11-12, Art. I): un derivado solo se
escribe si TODAS sus entradas llegaron (contrato en `derived_contract.py`, único punto de verdad; ver `_add_derived()`).

El evento de FC es la banda de 3 puntos NEWS2 del pulso (fase 0, decisión 5); los
demás eventos conservan los umbrales que ya vivían en el organismo.

Capa 5A, Sub-fase 1 (2026-08-30): tercer dominio, neurológico
(`_neurological_state()`) -- mismo patrón y misma disciplina de gate
anti-órgano-fantasma que cardiovascular/respiratorio. Escribe lo que
`EegAnalyzer` (`src/signals/eeg/eeg_analyzer.py`) ya calcula (band power
Welch); desde la fase 0 (2026-11-13) sin derivados del organismo.

Acoplamientos Sub-fase B (2026-09-06): + `bar` (Ratio Beta/Alfa) -- un
cociente adimensional de dos band power, biomarcador CITADO (Schutter
2006), no una invención de esta app. Persiste con la procedencia de las
band power de origen (ver comentario en `_neurological_state`). Es el
ancla firmada por el experto para la regla de acoplamiento arousal->↑FC."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Mapping, Optional, Tuple

from clinical.calculators import NEWS2_CITATION, news2_pulse_score, news2_spo2_scale1_score

from src.signals.eeg.eeg_analyzer import (
    BAR_CITATION,
    DAR_CITATION,
    TBR_CITATION,
    beta_alpha_ratio,
    delta_alpha_ratio,
    theta_beta_ratio,
)
from src.signals.eeg.spectral_model import CHI_APERIODIC_CITATION, CHI_CITATION

from .composer import DEFAULT_MAX_HR_CARRY_AGE_S
from .derived_contract import SPECTRAL_BANDS, accepted_band_powers, derived_confidence, derived_is_writable
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


def _usable_inputs(
    organism: "DigitalTwinOrganism", organ_id: str, provenance: Provenance, source_detail: Optional[str]
) -> Tuple[dict, Provenance, Optional[str], bool]:
    """Qué entradas del órgano puede usar el UPS y con qué procedencia (Fase 1, 2026-11-12, Art. I).

    - ACTUAL: llegaron en la última actualización del organismo -> procedencia del llamador; los derivados se permiten.
    - ARRASTRADA: llegaron en una actualización anterior pero dentro de la compuerta temporal del compositor
      (`DEFAULT_MAX_HR_CARRY_AGE_S`, la MISMA constante) -> solo valores medidos, con `ARRASTRE_TEMPORAL` y su edad
      declarada; NUNCA derivados.
    - VENCIDA o inexistente: la entrada no existe (dominio vacío).
    Devuelve (señales usables, procedencia, source_detail, ¿se permiten derivados?)."""
    metrics = organism.organs[organ_id].metrics
    if not metrics.signals or metrics.signals_seq == 0:
        return {}, provenance, source_detail, False
    if organism.inputs_are_current(organ_id):
        return metrics.signals, provenance, source_detail, True
    age_s = (organism.timestamp - metrics.signals_at).total_seconds() if metrics.signals_at else float("inf")
    if age_s > DEFAULT_MAX_HR_CARRY_AGE_S:
        return {}, provenance, source_detail, False
    detail = f"{source_detail + ' | ' if source_detail else ''}arrastrada de una actualización anterior (edad {age_s:.0f} s)"
    return metrics.signals, Provenance.ARRASTRE_TEMPORAL, detail, False


def _current_signals(organism: "DigitalTwinOrganism", organ_id: str) -> dict:
    """Señales del órgano SOLO si llegaron en la actualización actual (los eventos no se derivan de entradas viejas)."""
    return organism.organs[organ_id].metrics.signals if organism.inputs_are_current(organ_id) else {}


def _add_derived(descriptors, domain, signals, candidates, confidence, source_detail, input_confidence=None) -> None:
    """ÚNICO camino por el que un valor derivado del organismo entra al UPS: lo filtra el contrato
    (`derived_contract.derived_is_writable`) según las entradas que REALMENTE llegaron en `signals`, y su confianza
    es la MENOR de las de sus entradas (`derived_confidence`, decisión 6). Un candidato puede traer su propio detalle."""
    for candidate in candidates:
        name, value, unit = candidate[:3]
        if derived_is_writable(domain, name, signals):
            descriptors[name] = PhysiologicalDescriptor(
                name, float(value), unit, Provenance.DERIVADO,
                derived_confidence(domain, name, signals, input_confidence, confidence),
                candidate[3] if len(candidate) > 3 else source_detail,
            )


def _cardiovascular_state(
    organism: "DigitalTwinOrganism", provenance: Provenance, confidence: float, source_detail: Optional[str],
    input_confidence: Optional[Mapping[str, float]] = None,
) -> DomainState:
    """Cardiovascular. Fase 1 (2026-11-12, decisiones firmadas): solo se escribe lo medido (`heart_rate`, `hrv`) y UN
    derivado, los puntos NEWS2 del pulso (`news2_pulse_points`, única entrada `heart_rate`, con su cita). Sin
    `health_score`, `myocardial_stress`, `rhythm_stability` ni `cardiac_output` (ver `derived_contract.py`). El corazón
    fantasma (2026-08-22) sigue vetado: sin `heart_rate` no hay derivado."""
    signals, provenance, source_detail, derived_ok = _usable_inputs(organism, "heart", provenance, source_detail)
    ic = input_confidence or {}

    descriptors = {}
    if "heart_rate" in signals:
        descriptors["heart_rate"] = PhysiologicalDescriptor(
            "heart_rate", float(signals["heart_rate"]), "bpm", provenance, ic.get("heart_rate", confidence), source_detail
        )
    if "hrv" in signals:
        descriptors["hrv"] = PhysiologicalDescriptor(
            "hrv", float(signals["hrv"]), "ms", provenance, ic.get("hrv", confidence), source_detail
        )

    if derived_ok and "heart_rate" in signals:
        points = news2_pulse_score(float(signals["heart_rate"]))
        _add_derived(
            descriptors, "cardiovascular", signals,
            [("news2_pulse_points", points, "puntos NEWS2 (0-3)",
              f"{source_detail + ' | ' if source_detail else ''}news2_pulse_score | {NEWS2_CITATION}")],
            confidence, source_detail, input_confidence,
        )

    return DomainState(domain="cardiovascular", descriptors=descriptors)


def _respiratory_state(
    organism: "DigitalTwinOrganism", provenance: Provenance, confidence: float, source_detail: Optional[str],
    input_confidence: Optional[Mapping[str, float]] = None,
) -> DomainState:
    lungs = organism.organs["lungs"]
    signals, provenance, source_detail, derived_ok = _usable_inputs(organism, "lungs", provenance, source_detail)
    ic = input_confidence or {}

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
            "respiratory_rate", float(signals["respiratory_rate"]), "resp/min", provenance, ic.get("respiratory_rate", confidence), source_detail
        )
    if "spo2" in signals:
        descriptors["spo2"] = PhysiologicalDescriptor(
            "spo2", float(signals["spo2"]), "%", provenance, ic.get("spo2", confidence), source_detail
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
            "ahi", float(signals["ahi"]), "eventos/h", provenance, ic.get("ahi", confidence), source_detail
        )

    # Contrato de derivados (C0 + fase 0, decisión 6): ver `derived_contract.py`. Puntos NEWS2 de la FR y de la SpO₂
    # (escala 1), cada uno con su única entrada y su cita. `health_score` (pesos 0.5/0.3/0.4 sin cita, tanda 0.1),
    # `risk_score`, `hypoxia_risk`, `apnea_risk` y `tissue_oxygenation` NUNCA (retirados).
    if has_real_respiratory_input and derived_ok:
        cite = f"{source_detail + ' | ' if source_detail else ''}"
        candidates = []
        if lungs.metrics.rr_points is not None:
            candidates.append(("news2_respiratory_rate_points", lungs.metrics.rr_points, "puntos NEWS2 (0-3)",
                               f"{cite}news2_respiratory_rate_score | {NEWS2_CITATION}"))
        if lungs.metrics.spo2_points is not None:
            candidates.append(("news2_spo2_scale1_points", lungs.metrics.spo2_points, "puntos NEWS2 (0-3)",
                               f"{cite}news2_spo2_scale1_score (escala 1; la escala 2 no se modela) | {NEWS2_CITATION}"))
        candidates = [c for c in candidates if c[1] is not None]
        _add_derived(descriptors, "respiratory", signals, candidates, confidence, source_detail, input_confidence)

    return DomainState(domain="respiratory", descriptors=descriptors)


def _neurological_state(
    organism: "DigitalTwinOrganism", provenance: Provenance, confidence: float, source_detail: Optional[str],
    input_confidence: Optional[Mapping[str, float]] = None,
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
    signals, provenance, source_detail, derived_ok = _usable_inputs(organism, "brain", provenance, source_detail)
    ic = input_confidence or {}

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
    # Contrato (C0, 2026-11-12): una potencia de banda se acepta como medición solo si llegó con >= 2 bandas (un
    # espectro, no una banda aislada). Twin OS envía SOLA `alpha_power = 70 - 0.5*estrés` (slider): fabricada, no se
    # escribe -- y, al no quedar banda aceptada, el gate deja el dominio vacío. Ver `derived_contract.py`.
    bands = accepted_band_powers(signals)
    has_real_neuro_input = "alpha_power" in bands or "beta_power" in bands

    for band in SPECTRAL_BANDS:
        if band in bands:
            descriptors[band] = PhysiologicalDescriptor(
                band, float(bands[band]), "power (u.a.)", provenance, ic.get(band, confidence), source_detail
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
    if "alpha_power" in bands and "beta_power" in bands:
        bar_value = beta_alpha_ratio(float(bands["beta_power"]), float(bands["alpha_power"]))
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
    if "delta_power" in bands and "alpha_power" in bands:
        dar_value = delta_alpha_ratio(float(bands["delta_power"]), float(bands["alpha_power"]))
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
    if "theta_power" in bands and "beta_power" in bands:
        tbr_value = theta_beta_ratio(float(bands["theta_power"]), float(bands["beta_power"]))
        if tbr_value is not None:
            descriptors["tbr"] = PhysiologicalDescriptor(
                "tbr", tbr_value, "ratio (adimensional)", provenance, confidence,
                f"{source_detail + ' | ' if source_detail else ''}theta_beta_ratio | {TBR_CITATION}",
            )

    # χ (exponente aperiódico 1/f) -- Arco 2C (2026-09-14), elevado desde el
    # banco de pruebas aislado de Arco 2B (`src/signals/eeg/
    # spectral_model.py`). MISMO patrón de gate individual que
    # bar/dar/tbr arriba -- independiente, no toca ninguno de esos
    # bloques: solo se persiste si el escritor incluyó la clave, y el
    # escritor (el botón del EEG Lab) solo la incluye cuando
    # `AperiodicComponent.available=True` -- el gate de evidencia/calidad
    # (`MIN_CHI_CLEAN_WINDOWS` + R², ambos en `spectral_model.py`) ya corrió
    # ANTES de que la clave llegara a `signals`. Es una IDENTIDAD (el
    # exponente que devolvió el ajuste), no un cálculo del organismo --
    # misma procedencia que las band power de origen, no `DERIVADO`.
    #
    # Arco 2D (2026-09-18): firma del experto aplicada -- `PENDING_VALIDATION`
    # retirado, mismo cierre que vivieron DAR/TBR en Neuro Tanda 2 (ver
    # `eeg_analyzer.py`). `source_detail` ahora lleva DOS citas, cada una de
    # su propio eje: `CHI_APERIODIC_CITATION` (Donoghue et al. 2020, respalda
    # el ALGORITMO de ajuste FOOOF) y `CHI_CITATION` (Gao et al. 2017,
    # respalda la INTERPRETACIÓN clínica del número ya ajustado, con la
    # cláusula de alcance LFP->EEG de superficie incluida en su propio
    # texto -- ver `spectral_model.py`). El umbral clínico (🔴/🔵/💤,
    # `CHI_THRESHOLDS`/`classify_chi()`, `spectral_model.py`) ya existe --
    # a diferencia de `classify_dar()`/`classify_tbr()`, que viven en
    # `eeg_analyzer.py`, `classify_chi()` vive junto a `fit_aperiodic_
    # component()` en `spectral_model.py`, donde chi se calcula.
    if "chi_aperiodic" in signals:
        descriptors["chi_aperiodic"] = PhysiologicalDescriptor(
            "chi_aperiodic", float(signals["chi_aperiodic"]), "exponente (adimensional)",
            provenance, confidence,
            f"{source_detail + ' | ' if source_detail else ''}"
            f"VALIDADO_POR_FUENTE | {CHI_APERIODIC_CITATION} | {CHI_CITATION}",
        )

    # Fase 0 (decisión 6, Parte E): el dominio neurológico no escribe NINGÚN derivado del organismo. `health_score`/
    # `risk_score` (sin cita), `mental_workload` (= min(100, beta_power)), `stress_perception` (= stress_level),
    # `cognitive_fatigue`, `attention`, `sleepiness` y los campos nunca asignados (`frontal_activity`...) están en
    # NUNCA en `derived_contract.py`. Lo medido (potencias, BAR/DAR/TBR, χ) ya se escribió arriba como lo que es.

    return DomainState(domain="neurological", descriptors=descriptors)


def _muscular_state(
    organism: "DigitalTwinOrganism", provenance: Provenance, confidence: float, source_detail: Optional[str],
    input_confidence: Optional[Mapping[str, float]] = None,
) -> DomainState:
    """Capa 5A, dominio muscular Tanda 2 (2026-09-10): cuarto dominio,
    patrón COPIADO LITERAL de `_neurological_state()` de arriba, incluido
    el gate anti-órgano-fantasma.

    Señales primarias: `activation` (mean|x|/max|x| sobre sEMG filtrada, la
    computa `EmgAnalyzer`, `src/signals/emg/emg_analyzer.py`) y
    `median_frequency` (MDF del PSD de Welch, marcador de fatiga estándar).
    Ambas son cantidades reales de la señal, no invenciones de la app."""
    muscles = organism.organs["muscles"]
    signals, provenance, source_detail, derived_ok = _usable_inputs(organism, "muscles", provenance, source_detail)
    ic = input_confidence or {}

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
            "activation", float(signals["activation"]), "%", provenance, ic.get("activation", confidence), source_detail
        )
    if "median_frequency" in signals:
        descriptors["median_frequency"] = PhysiologicalDescriptor(
            "median_frequency", float(signals["median_frequency"]), "Hz", provenance, ic.get("median_frequency", confidence), source_detail
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

    # Fase 0 (decisión 6, Parte E): el dominio muscular no escribe NINGÚN derivado del organismo (`health_score`/
    # `risk_score` sin cita, `neuromuscular_efficiency` = `efficiency`, `movement_smoothness` = 100 − fatiga, y los
    # tres campos nunca asignados): todos en NUNCA en `derived_contract.py`.

    return DomainState(domain="muscular", descriptors=descriptors)


def _detect_events(
    organism: "DigitalTwinOrganism", provenance: Provenance, confidence: float, timestamp: datetime
) -> List[PhysiologicalEvent]:
    """Eventos desde las entradas ACTUALES (nunca de una entrada vieja).

    Fase 0 (2026-11-13, decisión 5 de Luis): el evento de FC es la banda de 3 puntos NEWS2 del pulso (≤ 40 o ≥ 131 lpm,
    `news2_pulse_score`, RCP 2017), nombrado por lo que mide (`PULSE_NEWS2_3_POINTS`); se retiraron el evento por
    umbrales propios (40/120, crítico 35/150) y el de `hrv < 20`. Severidad única (WARNING): NEWS2 no gradúa un pulso
    aislado como crítico; eso lo hace el total, que el gemelo no tiene. Tanda 0.1: el evento de SpO₂ es la banda de 3
    puntos NEWS2 escala 1 (≤ 91 %) y el de estrés > 75 se retiró; el de fatiga > 80 conserva su umbral (sin firma)."""

    events: List[PhysiologicalEvent] = []
    heart_signals = _current_signals(organism, "heart")
    lungs_signals = _current_signals(organism, "lungs")
    brain_signals = _current_signals(organism, "brain")
    muscle_signals = _current_signals(organism, "muscles")

    hr = heart_signals.get("heart_rate")
    if hr is not None and news2_pulse_score(float(hr)) == 3:
        events.append(
            PhysiologicalEvent(
                event_type=EventType.PULSE_NEWS2_3_POINTS,
                domain="cardiovascular",
                severity=EventSeverity.WARNING,
                description=f"Pulso en la banda de 3 puntos NEWS2 (≤ 40 o ≥ 131 lpm): {hr:.0f} lpm",
                provenance=provenance,
                confidence=confidence,
                timestamp=timestamp,
                related_descriptor="news2_pulse_points",
            )
        )

    # Tanda 0.1 (decisión 1): banda de 3 puntos NEWS2 escala 1 (≤ 91 %), misma tabla que el organismo; se retiraron
    # los umbrales 90/95 (sin cita) y el evento de estrés > 75 (sin fuente).
    spo2 = lungs_signals.get("spo2")
    if spo2 is not None and news2_spo2_scale1_score(float(spo2)) == 3:
        events.append(
            PhysiologicalEvent(
                event_type=EventType.SPO2_NEWS2_3_POINTS,
                domain="respiratory",
                severity=EventSeverity.WARNING,
                description=f"SpO₂ en la banda de 3 puntos NEWS2, escala 1 (≤ 91 %): {spo2:.0f} %",
                provenance=provenance,
                confidence=confidence,
                timestamp=timestamp,
                related_descriptor="news2_spo2_scale1_points",
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
                related_descriptor=None,  # `movement_smoothness` se retiró (fase 0); `fatigue_index` no se persiste
            )
        )

    return events


def from_digital_twin_organism(
    organism: "DigitalTwinOrganism",
    patient_id: str,
    provenance: Provenance = Provenance.SIMULACION,
    confidence: Optional[float] = None,
    source_detail: Optional[str] = None,
    input_confidence: Optional[Mapping[str, float]] = None,
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

    Fase 1 (2026-11-12): `input_confidence` = confianza propia de cada entrada (por nombre: `{"heart_rate": 0.84}`); una
    entrada sin ella hereda `confidence`. Un derivado hereda la MENOR confianza de sus entradas (propagación
    conservadora, decisión 6). Las entradas que no llegaron en la actualización actual del organismo solo entran como
    `ARRASTRE_TEMPORAL` dentro de la compuerta del compositor, y pasada esa compuerta no existen.
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

    cardiovascular = _cardiovascular_state(organism, provenance, confidence, source_detail, input_confidence)
    respiratory = _respiratory_state(organism, provenance, confidence, source_detail, input_confidence)
    neurological = _neurological_state(organism, provenance, confidence, source_detail, input_confidence)
    muscular = _muscular_state(organism, provenance, confidence, source_detail, input_confidence)
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
