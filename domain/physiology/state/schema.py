"""
Unified Physiological State — esquema tipado (contrato de datos).

Este módulo define la forma del UPS en memoria, independiente de cómo se
persiste (ver `models.py`/`repository.py`). Toda pieza de información
fisiológica pasa por `PhysiologicalDescriptor`, que obliga a declarar de
dónde viene el dato y con qué certeza se conoce — la regla "simulación no es
dato falso" se cumple a nivel de dato, no de rótulo en la UI.

Alcance (Fase 1.1: cardiovascular + respiratorio; Capa 5A: + neurológico
2026-08-30, + muscular 2026-09-10). El resto de los sistemas descritos en
documentation/Nivel 01/104_UNIFIED_PHYSIOLOGICAL_STATE.md se añadirá en
fases posteriores siguiendo el mismo contrato.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, NamedTuple, Optional


class Provenance(str, Enum):
    """Origen de un valor fisiológico. Nunca inferible después del hecho —
    debe declararse en el momento en que el valor entra al UPS.

    `REFERENCIA_CLINICA` (2026-07-18) es una etiqueta de clasificación —
    "valor típico de este cuadro según literatura clínica citable, ni
    medido ni simulado ni derivado". Deliberadamente NO tiene entrada en
    `CONFIDENCE_REFERENCE` (ver abajo) y no se usa con `PhysiologicalDescriptor`
    (que exige `confidence: float` obligatorio) — un rango de guía de un
    libro de texto no es una medición con incertidumbre de sensor, y
    ponerle un número de esa banda fingiría una precisión que no tiene.
    Los valores de esta procedencia usan su propio tipo,
    `ClinicalReferenceValue` (`clinical_reference.py`), con `citation`
    obligatoria en su lugar — mismo criterio que `ClinicalImpression`.

    `MODELO_HEMODINAMICO` (2026-07-19; banda ensanchada 2026-08-01 tras
    validación cuantitativa) — un valor calculado por un modelo matemático
    validado estructuralmente (`domain/physiology/hemodynamics/`, módulo
    R-RCR verificado contra svZeroDSolver), pero alimentado con al menos
    una entrada que no es una medición/simulación directa del organismo
    (constante de volumen sistólico citada de literatura, parámetros de
    resistencia/compliancia estimados — ver `hemodynamics/physiological_flow.py`).
    A diferencia de `DERIVADO` (cálculo interno ya confiable sobre datos ya
    confiables), esta cantidad hace una afirmación fisiológica nueva (una
    presión arterial) a partir de parámetros que, según el caso, están
    pendientes de confirmación experta o ya la tienen.

    Esta procedencia cubre DOS regímenes distintos bajo la misma etiqueta,
    y la banda (0.30-0.80, ver `CONFIDENCE_REFERENCE`) es deliberadamente
    ancha para darles espacio a ambos SIN inventar una segunda procedencia:
    (a) cálculos NO validados en contexto (extremo bajo de la banda,
    ~0.30-0.55 -- el techo original, sin cambios, para cualquier conexión
    futura a un escenario que no haya pasado por validación experta), y
    (b) cálculos SÍ validados (Rondas 1-2 de validación cuantitativa +
    verificación de estabilidad numérica, 2026-07-31/08-01, para los 3
    escenarios en `hemodynamics/closed_loop_ups_bridge.py` --
    `HEMODYNAMIC_MODEL_ENABLED_SCENARIOS`), que pueden usar confianza más
    alta (~0.70-0.80) reflejando "validado contra literatura, pero sigue
    siendo un cálculo de modelo, no una medición" -- por eso el techo
    (0.80) queda deliberadamente por debajo del techo de `SIMULACION`
    (0.90): ni el escenario más validado de este modelo compite con un
    dato leído/derivado directamente del organismo. `default_confidence()`
    (el punto medio automático de la banda) YA NO es apropiado para esta
    procedencia -- cada llamador debe pasar una confianza EXPLÍCITA que
    refleje si su caso concreto está validado o no (ver
    `closed_loop_ups_bridge.py` y el `ups_bridge.py` original, que
    preserva su 0.425 histórico explícitamente en vez de heredar el nuevo
    punto medio de la banda ensanchada).

    `DERIVADO_ACOPLAMIENTO` (2026-09-06; Acoplamientos, Sub-fase A) -- un
    valor calculado por una REGLA DE ACOPLAMIENTO fisiológico
    (`domain/physiology/coupling/`): cuando el estado de un sistema modula
    una señal primaria de otro (p.ej. activación neurológica -> ↑FC), el
    valor modulado NO es medido ni simulado -- lo produce la regla, a
    partir del valor base real y de un descriptor real del sistema origen.
    Mismo criterio que `MODELO_HEMODINAMICO` (y NO `DERIVADO` a secas): es
    una afirmación fisiológica NUEVA (una FC acoplada) pendiente o dotada
    de validación experta, no un cálculo interno ya confiable sobre datos
    ya confiables. Banda 0.30-0.80 con la misma forma de dos regímenes:
    extremo bajo para reglas `TRANSCRITO_SIN_VALIDAR`, extremo alto para
    `VALIDADO_POR_FUENTE` -- y el techo (0.80) deliberadamente por debajo
    del de `SIMULACION` (0.90): ni la regla mejor validada compite con un
    dato leído/simulado directo del organismo. Sin punto medio automático
    razonable -- `apply_couplings()` (`coupling/bridge.py`) pasa la
    confianza EXPLÍCITA según el `validation_status` de cada regla. El
    descriptor acoplado se persiste SIEMPRE bajo un nombre distinto del
    medido (sufijo `_acoplado`, p.ej. `heart_rate_acoplado`) para que
    coexista con el medido sin sobrescribirlo -- mismo patrón que
    `systolic_bp_modelo` en `hemodynamics/ups_bridge.py`.

    `ARRASTRE_TEMPORAL` (2026-09-08; compositor multi-dominio, Tanda 1 de
    (b)) -- un valor REAL medido/simulado en un snapshot T-1, AFIRMADO en
    un snapshot compuesto T porque se asume que la última lectura sigue
    vigente dentro de una ventana temporal acotada. Es un "hold de orden
    cero" (zero-order hold): la señal no se re-mide ni se interpola, se
    mantiene constante entre muestras. NO es `SENSOR_REAL`: ningún sensor
    midió en el timestamp del snapshot compuesto -- la lectura es de otro
    instante. NO es `DERIVADO`: no se calculó a partir de otras entradas,
    se ARRASTRÓ una medición sin transformarla. El único uso hoy:
    `compose_neuro_cardiac_snapshot()` (`composer.py`) trae el último
    `heart_rate` real y lo pone junto a un `bar` de ahora, para que el
    acoplamiento neuro->CV tenga una FC base sobre la cual disparar. La
    `confidence` se arrastra TAL CUAL del descriptor de origen (sin banda
    propia en `CONFIDENCE_REFERENCE`, igual que `REFERENCIA_CLINICA`); la
    degradación de confianza en función de la edad del arrastre queda como
    refinación futura, firmada por experto. El `source_detail` declara
    SIEMPRE el snapshot de origen, su timestamp y la edad del arrastre en
    segundos -- sin esa declaración el valor no se persiste. La ventana de
    antigüedad admisible la impone el compositor
    (`max_hr_carry_age_s`), no esta procedencia: fuera de ventana el
    compositor devuelve "no disponible", nunca un arrastre marcado."""

    SENSOR_REAL = "sensor_real"
    SIMULACION = "simulacion"
    DERIVADO = "derivado"
    REFERENCIA_CLINICA = "referencia_clinica"
    MODELO_HEMODINAMICO = "modelo_hemodinamico"
    DERIVADO_ACOPLAMIENTO = "derivado_acoplamiento"
    ARRASTRE_TEMPORAL = "arrastre_temporal"


class ConfidenceBand(NamedTuple):
    low: float
    high: float
    description: str


# Semántica central de `confidence` por procedencia. No cambia el tipo (sigue
# float 0.0-1.0): fija qué rango es razonable para cada origen, para que una
# confianza de 0.8 en un valor DERIVADO signifique lo mismo que una de 0.8 en
# uno SENSOR_REAL cuando se comparan entre sí (p.ej. en el narrador de 1.3).
# Todo llamador que asigne `confidence` debe partir de esta tabla, no de un
# número arbitrario.
CONFIDENCE_REFERENCE: Dict["Provenance", ConfidenceBand] = {
    Provenance.SENSOR_REAL: ConfidenceBand(
        0.85, 1.0, "Medido por un sensor real; el margen solo cubre ruido/calibración del dispositivo."
    ),
    Provenance.SIMULACION: ConfidenceBand(
        0.60, 0.90, "Generado por un escenario educativo, nunca una medición real; techo por debajo de sensor_real."
    ),
    Provenance.DERIVADO: ConfidenceBand(
        0.50, 0.95, "Calculado a partir de otros valores; su confianza depende de la de sus entradas."
    ),
    Provenance.MODELO_HEMODINAMICO: ConfidenceBand(
        0.30, 0.80,
        "Calculado por un modelo matemático validado estructuralmente, con al menos un "
        "parámetro de entrada no derivado directamente del organismo. Banda ancha porque cubre "
        "dos regímenes bajo la misma etiqueta: extremo bajo (~0.30-0.55) para cálculos SIN "
        "validación experta en contexto todavía; extremo alto (~0.70-0.80) para los que SÍ la "
        "tienen (Rondas 1-2 de validación cuantitativa + estabilidad numérica confirmada) -- "
        "techo (0.80) siempre por debajo de SIMULACION (0.90), ni el caso más validado de este "
        "modelo compite con un dato leído/derivado directamente del organismo. Sin punto medio "
        "automático razonable dado el ancho del rango -- cada llamador pasa confianza explícita.",
    ),
    Provenance.DERIVADO_ACOPLAMIENTO: ConfidenceBand(
        0.30, 0.80,
        "Calculado por una regla de acoplamiento fisiológico (coupling/): una señal primaria de "
        "un sistema modulada por el estado de otro. Afirmación fisiológica nueva (no un cálculo "
        "interno ya confiable), pendiente o dotada de validación experta. Banda ancha, dos "
        "regímenes: extremo bajo (~0.30-0.45) para reglas TRANSCRITO_SIN_VALIDAR; extremo alto "
        "(~0.65-0.75) para VALIDADO_POR_FUENTE. Techo (0.80) siempre por debajo de SIMULACION "
        "(0.90). Sin punto medio automático -- apply_couplings() pasa la confianza explícita "
        "según el validation_status de cada regla (misma disciplina que MODELO_HEMODINAMICO).",
    ),
    # Provenance.REFERENCIA_CLINICA deliberadamente NO tiene banda aquí. No es
    # un descuido: esta procedencia nunca se usa con PhysiologicalDescriptor/
    # default_confidence() -- vive en su propio tipo (ClinicalReferenceValue,
    # clinical_reference.py), sin ningún campo de confianza numérica. Si algún
    # día alguien llama default_confidence(Provenance.REFERENCIA_CLINICA), el
    # KeyError resultante es la señal correcta de que se está usando el tipo
    # equivocado para un valor de referencia clínica, no un bug que arreglar
    # agregando una banda inventada.
    #
    # Provenance.ARRASTRE_TEMPORAL tampoco tiene banda, por otra razón: la
    # confianza de un valor arrastrado ES la del descriptor de origen, tal
    # cual -- el compositor la copia, no la inventa ni la promedia. Un
    # default_confidence(Provenance.ARRASTRE_TEMPORAL) -> KeyError también
    # es la señal correcta (nadie debería pedir una confianza "por defecto"
    # para un arrastre; se hereda). La degradación por edad, si se decide,
    # será una fórmula explícita en el compositor, no una banda aquí.
}


def default_confidence(provenance: "Provenance") -> float:
    """Confianza por defecto para una procedencia dada — el punto medio de su
    banda de referencia en `CONFIDENCE_REFERENCE`. Los llamadores pueden
    pasar un valor explícito distinto (p.ej. un sensor con ruido conocido),
    pero deben mantenerse dentro de la banda para que las confianzas sigan
    siendo comparables entre procedencias."""
    band = CONFIDENCE_REFERENCE[provenance]
    return round((band.low + band.high) / 2, 2)


class EventSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class EventType(str, Enum):
    """Catálogo cerrado de eventos que el UPS puede emitir en este slice
    (cardiovascular + respiratorio + neurológico + muscular, desde Capa
    5A). Los consumidores de fases posteriores (1.3 narrador, 1.4 conexión
    visual) deben referenciar estos miembros, no strings sueltos — añadir
    un evento nuevo significa añadir un miembro aquí, no inventar un string
    en el llamador."""

    ARRHYTHMIA_RISK_HR_EXTREME = "arrhythmia_risk_hr_extreme"
    LOW_HRV_AUTONOMIC_STRESS = "low_hrv_autonomic_stress"
    HYPOXIA_SPO2_CRITICAL = "hypoxia_spo2_critical"
    HYPOXIA_SPO2_LOW = "hypoxia_spo2_low"
    # Capa 5A, Sub-fase 1 (2026-08-30): único evento neuro -- mismo umbral
    # que YA usa `DigitalTwinOrganism._update_brain()` para su propio
    # `risk_score` (`stress_level > 75`, el tier más alto que ese método
    # define) -- no se inventa un umbral clínico nuevo, se reutiliza el que
    # ya vive en el motor, mismo criterio que los 4 eventos de arriba.
    HIGH_STRESS_EEG = "high_stress_eeg"
    # Capa 5A, dominio muscular Tanda 2 (2026-09-10): único evento muscular
    # -- mismo criterio que HIGH_STRESS_EEG: reutiliza el umbral que YA usa
    # `_update_muscles()` para su tier más alto de `risk_score`
    # (`fatigue_index > 80`). El `fatigue_index` NO se persiste como
    # descriptor todavía (diferido -- generador demo roto, ver
    # `_muscular_state()`), pero el evento sí puede leer la señal cruda del
    # organismo, exactamente como el evento de EEG lee `stress_level` sin
    # persistirlo.
    SEVERE_MUSCLE_FATIGUE_EMG = "severe_muscle_fatigue_emg"


@dataclass(frozen=True)
class PhysiologicalDescriptor:
    """Un valor fisiológico individual con procedencia y confianza."""

    name: str  # p.ej. "heart_rate", "hrv", "spo2", "respiratory_rate"
    value: float
    unit: str
    provenance: Provenance
    confidence: float  # 0.0-1.0
    source_detail: Optional[str] = None  # p.ej. "escenario:sepsis", "ecg_lead_II"

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence fuera de rango [0,1]: {self.confidence}")


@dataclass(frozen=True)
class DomainState:
    """Estado de un dominio fisiológico (cardiovascular, respiratorio, ...)
    en un instante dado: un conjunto de descriptores nombrados."""

    domain: str
    descriptors: Dict[str, PhysiologicalDescriptor] = field(default_factory=dict)

    def get(self, name: str) -> Optional[PhysiologicalDescriptor]:
        return self.descriptors.get(name)


@dataclass(frozen=True)
class PhysiologicalEvent:
    """Evento discreto de primera clase (no derivado de mirar números después).

    Se detecta y materializa en el momento en que el UPS se construye a
    partir de una fuente (sensor, simulación), no se re-deriva más tarde
    inspeccionando la serie de valores.
    """

    event_type: EventType
    domain: str
    severity: EventSeverity
    description: str
    provenance: Provenance
    confidence: float
    timestamp: datetime
    related_descriptor: Optional[str] = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence fuera de rango [0,1]: {self.confidence}")


@dataclass(frozen=True)
class UnifiedPhysiologicalState:
    """Un snapshot del organismo en un instante — la unidad que se persiste
    y que compone la trayectoria temporal del paciente.

    Capa 5A, Sub-fase 1 (2026-08-30): `neurological` es el tercer dominio,
    campo NOMBRADO como los otros dos (el diagnóstico de alcance confirmó
    que este schema es explícito por dominio, no una colección genérica).
    Lleva `default_factory` a un `DomainState` vacío -- no `required` --
    para que los sitios que ya construyen `UnifiedPhysiologicalState(...)`
    sin saber de neuro sigan funcionando idénticos, con un dominio neuro
    vacío por default en vez de romper. Mismo principio que el gate
    anti-órgano-fantasma del builder: "sin dato real, vacío" -- aquí
    aplicado a nivel de constructor, no solo de builder.

    Capa 5A, dominio muscular Tanda 2 (2026-09-10): `muscular` es el cuarto
    dominio, EXACTAMENTE igual que `neurological` -- campo nombrado con
    `default_factory` a un `DomainState` vacío. Verificado: los 11 sitios
    que construyen `UnifiedPhysiologicalState(...)` (builder, composer,
    repository ×2, 7 tests) pasan todo por keyword y no fijan `muscular` --
    reciben el dominio muscular vacío por default, sin editarse."""

    patient_id: str
    timestamp: datetime
    cardiovascular: DomainState
    respiratory: DomainState
    neurological: DomainState = field(default_factory=lambda: DomainState(domain="neurological"))
    muscular: DomainState = field(default_factory=lambda: DomainState(domain="muscular"))
    events: List[PhysiologicalEvent] = field(default_factory=list)

    def all_domains(self) -> Dict[str, DomainState]:
        return {
            "cardiovascular": self.cardiovascular,
            "respiratory": self.respiratory,
            "neurological": self.neurological,
            "muscular": self.muscular,
        }
