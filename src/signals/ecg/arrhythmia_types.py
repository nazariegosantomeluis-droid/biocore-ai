"""
Tipos de arritmia -- FUENTE ÚNICA (Unificación 1, 2026-10-31).

Reemplaza a "arritmia" genérico, que no es un diagnóstico sino una categoría
que promediaba fisiologías distintas, y a las cinco tablas paralelas que lo
simulaban con números propios (el preset "Arritmia" FC 95/HRV 15; el
`SimulationEngine` con FC ~ N(110, 30) sin semilla; ECG-12 con FA a 112 fijo;
el entrenador con FA a ~128; `fibrilacion_estres` 75->145). Este módulo es puro
(sin imports del proyecto) para que lo consuman todos sin ciclos:
`SimulationEngine`, `DigitalTwinOrganism`, ECG-12 y el entrenador ECG.
Cada consumidor puede dibujar su propia señal; la FC sale de aquí.

Variabilidad DECLARADA (opción B): cada tipo declara su rango de FC y si es
regular o irregular. Una "instancia" es el par (tipo, semilla): la FC es una
función determinista de la semilla dentro del rango declarado, y la UI muestra
rango, semilla y valor. Un tipo regular mantiene una sola FC durante todo el
episodio; uno irregular la cambia entre horizontes, siempre dentro del rango.
Ningún clic produce un paciente distinto sin que la semilla y el rango estén a
la vista.

ESTADO DE VALIDACIÓN: los rangos son los de la tabla propuesta por el experto
(Luis), PENDING_VALIDATION: ninguno tiene firma ni cita todavía. Los tipos
propuestos esperan su firma; quitar uno es borrar su entrada de `ARRHYTHMIA_TYPES`.

Extrasístoles (EV/EA) NO están: sus signos vitales son normales (la FC media no
cambia) y el UPS no tiene descriptor de ritmo, así que un escenario de signos
vitales no tendría nada que distinguirlo de "sano". Necesitan una forma de onda
con salvas prematuras, no una FC; se añaden con su propio generador si se firma.

LÍMITE DEL UPS (declarado): el UPS no modela ritmo, solo FC. El único evento que dispara
depende de la FC: `pulse_news2_3_points`, la banda de 3 puntos NEWS2 del pulso (≤ 40 o
≥ 131 lpm, `clinical.calculators.news2_pulse_score`; fase 0, 2026-11-13), así que
`ups_hr_event` describe cuándo ese evento acompaña al tipo, no un evento propio del tipo.
Los códigos `ARR_*_ON` propuestos requieren un descriptor de ritmo en el esquema del UPS
(decisión pendiente) y NO existen todavía. Huecos declarados: la bradicardia sinusal (40-59
lpm) solo dispara en 40 lpm (≤ 40 son 3 puntos; 41-59 no), y la taquicardia sinusal
(100-140) solo en 131-140 (su FC nominal, 120, no dispara). Un test verifica cada
`ups_hr_event` contra el builder real.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

import numpy as np

VALIDATION_STATUS = "PENDING_VALIDATION"

# `ups_hr_event`: cuándo el evento por FC del UPS acompaña a este tipo, dado su rango.
EVENT_ALWAYS = "siempre"
EVENT_DEPENDS_ON_HR = "segun_fc"
EVENT_NEVER = "nunca"


@dataclass(frozen=True)
class ArrhythmiaType:
    key: str
    label: str
    hr_min_bpm: float
    hr_max_bpm: float
    irregular: bool  # False: una sola FC por episodio; True: varía entre horizontes dentro del rango
    morphology: str
    ups_hr_event: str
    reversal: str  # tratamiento / reversión que la plataforma puede simular

    @property
    def nominal_hr_bpm(self) -> float:
        """FC de un trazado estático (un solo registro): el punto medio del rango declarado."""
        return (self.hr_min_bpm + self.hr_max_bpm) / 2.0

    @property
    def regularity_label(self) -> str:
        return "irregularmente irregular" if self.irregular else "regular"


ARRHYTHMIA_TYPES: Dict[str, ArrhythmiaType] = {
    t.key: t for t in (
        ArrhythmiaType(
            "afib", "Fibrilación auricular", 100.0, 160.0, True,
            "sin onda P, línea de base temblorosa, RR irregularmente irregular",
            EVENT_DEPENDS_ON_HR, "control de frecuencia / cardioversión",
        ),
        ArrhythmiaType(
            "aflutter", "Flutter auricular (conducción 2:1)", 150.0, 150.0, False,
            "ondas F en sierra (~300/min), conducción 2:1; otros bloqueos (3:1, 4:1) no modelados",
            EVENT_ALWAYS, "adenosina (revela las ondas F) / cardioversión",
        ),
        ArrhythmiaType(
            "svt", "Taquicardia supraventricular", 150.0, 220.0, False,
            "inicio y fin súbitos, QRS estrecho",
            EVENT_ALWAYS, "maniobras vagales / adenosina",
        ),
        ArrhythmiaType(
            "sbrady", "Bradicardia sinusal", 40.0, 59.0, False,
            "onda P antes de cada QRS, ritmo regular",
            EVENT_DEPENDS_ON_HR, "atropina / marcapasos",  # solo 40 lpm cae en la banda de 3 puntos (≤ 40)
        ),
    )
}

# Unificación 3 (2026-11-05): ritmos sinusales con FC canónica que NO son escenarios del simulador. ECG-12
# dibujaba "Taquicardia sinusal" con el slider de FC (75 por defecto): la etiqueta no producía la fisiología
# que nombra. Va aparte de ARRHYTHMIA_TYPES a propósito: el simulador (`ARRHYTHMIA_SCENARIO_TYPE`) y el juego
# diagnóstico de la Academia (grupos clínicos y distractores) enumeran ese dict, y añadir ahí un tipo exige
# decidir grupos clínicos y distractores del juego -- decisión de otro lab, no de esta unificación. Mismo
# dataclass, misma `instance_hr`/`declare_instance`/`get_type`. Rango propuesto por el experto (Luis),
# PENDING_VALIDATION como los demás. Definición clínica: FC sinusal en reposo > 100 lpm.
SINUS_RHYTHM_TYPES: Dict[str, ArrhythmiaType] = {
    t.key: t for t in (
        ArrhythmiaType(
            "stachy", "Taquicardia sinusal", 100.0, 140.0, False,
            "onda P antes de cada QRS, ritmo regular, QRS estrecho",
            EVENT_DEPENDS_ON_HR, "tratar la causa (fiebre, dolor, hipovolemia, ansiedad)",
        ),
    )
}

# Ritmo sinusal normal (no es una arritmia): FC de reposo del adulto, mismos cortes que usan
# `clinical/calculators.py` y el analizador de ECG-12 (60-100 lpm).
SINUS_NORMAL_RANGE_BPM: Tuple[float, float] = (60.0, 100.0)

_ALL_TYPES: Dict[str, ArrhythmiaType] = {**ARRHYTHMIA_TYPES, **SINUS_RHYTHM_TYPES}


def get_type(key: str) -> ArrhythmiaType:
    try:
        return _ALL_TYPES[key]
    except KeyError:
        raise ValueError(f"Tipo de ritmo desconocido: {key!r}. Disponibles: {sorted(_ALL_TYPES)}") from None


def instance_hr(key: str, seed: int = 0, slot: int = 0) -> float:
    """FC (lpm) de la instancia (tipo, semilla) en el instante `slot` (el horizonte, en minutos).
    Función pura: mismos argumentos, mismo valor. Un tipo regular ignora `slot`."""
    t = get_type(key)
    if t.hr_min_bpm == t.hr_max_bpm:
        return t.hr_min_bpm
    entropy = [int(seed), int(slot)] if t.irregular else [int(seed)]
    return float(np.random.default_rng(entropy).uniform(t.hr_min_bpm, t.hr_max_bpm))


def declare_instance(key: str, seed: int, slots: Tuple[int, ...]) -> str:
    """Texto que la UI muestra: rango declarado, regularidad, semilla y la FC de esta instancia."""
    t = get_type(key)
    rango = f"{t.hr_min_bpm:.0f}" if t.hr_min_bpm == t.hr_max_bpm else f"{t.hr_min_bpm:.0f}-{t.hr_max_bpm:.0f}"
    valores = sorted({round(instance_hr(key, seed, s)) for s in slots}) if t.irregular else [round(instance_hr(key, seed))]
    cierre = (
        "Otra semilla da otra instancia dentro del mismo rango."
        if t.hr_min_bpm != t.hr_max_bpm else "El tipo declara un valor único: no varía con la semilla."
    )
    return (
        f"Rango declarado de {t.label}: FC {rango} lpm, {t.regularity_label}. "
        f"Esta instancia (semilla {seed}): {', '.join(str(v) for v in valores)} lpm. {cierre} [{VALIDATION_STATUS}]"
    )
