"""
Tabla de referencia de presión arterial por escenario clínico.

Datos transcritos por el usuario desde fuentes clínicas citadas (2026-07-18)
-- Claude Code NO inventó ni ajustó ningún número; ver CHANGELOG.md para la
tabla de fuentes completa. PA ESTÁTICA: una fotografía del cuadro clínico
característico, no una trayectoria dinámica -- no varía por horizonte
temporal ni responde al motor de acoplamiento todavía (`domain/physiology/
coupling/`, que hoy solo lee `PhysiologicalDescriptor` dentro de
`DomainState`, no este tipo -- ver nota en `clinical_reference.py`).

Deliberadamente sin entrada para "fatigue" ni "copd": el usuario no dio
fuente para esos dos escenarios. La ausencia de clave (no una lista vacía)
es la señal honesta de "sin dato" -- `BLOOD_PRESSURE_REFERENCES.get(scenario)`
devuelve `None`, nunca un valor inventado.

Cuando un rango fue dado en vez de un punto único (p.ej. "130-150/85-95"),
se usó el punto medio del rango como `value` -- el rango completo queda
documentado en `phase_note`/la cita, porque `ClinicalReferenceValue.value`
es un único float, no un intervalo.
"""

from __future__ import annotations

from typing import Dict, List

from .clinical_reference import ClinicalReferenceValue, estimate_map

__all__ = ["BLOOD_PRESSURE_REFERENCES"]

_ACC_AHA_2017 = "ACC/AHA 2017 (2017 ACC/AHA Hypertension Guideline)"
_GUYTON = "Guyton & Hall, Tratado de Fisiología Médica"
_SEPSIS_3 = "Sepsis-3 (Singer et al. 2016, criterios de shock séptico: PAS<90 mmHg, PAM<65 mmHg)"
_HARRISON_AASM = "Harrison's Principles of Internal Medicine / AASM (picos hipertensivos post-arousal en AOS)"
_BRADLEY = "Bradley's Neurology in Clinical Practice (fase ictal de crisis convulsiva generalizada)"
_WEST_ACLS = "West's Respiratory Physiology / ACLS (respuesta compensatoria a hipoxemia)"
_AHA_ACC_HRS = "AHA/ACC/HRS (guía de manejo de arritmias, criterios de inestabilidad hemodinámica)"


def _bp_pair(
    scenario: str,
    systolic: float,
    diastolic: float,
    citation: str,
    phase_note: str,
) -> List[ClinicalReferenceValue]:
    """Sistólica + diastólica + PAM derivada con estimate_map() -- las tres
    ligadas a la misma cita y nota de fase."""
    return [
        ClinicalReferenceValue(
            scenario=scenario, domain="cardiovascular", descriptor="systolic_bp",
            value=systolic, unit="mmHg", citation=citation, phase_note=phase_note,
        ),
        ClinicalReferenceValue(
            scenario=scenario, domain="cardiovascular", descriptor="diastolic_bp",
            value=diastolic, unit="mmHg", citation=citation, phase_note=phase_note,
        ),
        ClinicalReferenceValue(
            scenario=scenario, domain="cardiovascular", descriptor="map",
            value=round(estimate_map(systolic, diastolic), 2), unit="mmHg",
            citation=f"{citation} (PAM derivada: PAM≈diastólica+⅓(sistólica−diastólica))",
            phase_note=phase_note,
        ),
    ]


BLOOD_PRESSURE_REFERENCES: Dict[str, List[ClinicalReferenceValue]] = {
    "healthy": _bp_pair(
        "healthy", 120.0, 80.0, _ACC_AHA_2017,
        "Valor normal de referencia -- no representa una fase particular.",
    ),
    "hypertension": _bp_pair(
        "hypertension", 130.0, 80.0, _ACC_AHA_2017,
        "Umbral diagnóstico de Hipertensión Estadio 1 (≥130/80) -- no representa una "
        "crisis hipertensiva ni hipertensión severa/descontrolada.",
    ),
    "sepsis": [
        ClinicalReferenceValue(
            scenario="sepsis", domain="cardiovascular", descriptor="systolic_bp",
            value=85.0, unit="mmHg", citation=_SEPSIS_3,
            phase_note=(
                "Fase de shock séptico / hipotensión refractaria (PAS<90 mmHg) -- no "
                "representa sepsis temprana compensada, donde la PA puede ser normal."
            ),
        ),
        ClinicalReferenceValue(
            scenario="sepsis", domain="cardiovascular", descriptor="diastolic_bp",
            value=55.0, unit="mmHg",
            citation=(
                f"{_SEPSIS_3} -- diastólica NO viene directamente de Sepsis-3 (que da PAS y PAM, "
                "no PAD); se calculó resolviendo la fórmula de PAM citada (PAM≈DBP+⅓(SBP−DBP)) "
                "para que sea consistente con la sistólica (85) y la PAM (65) dadas por la fuente. "
                "Verificar si se prefiere otro criterio."
            ),
            phase_note="Fase de shock séptico / hipotensión refractaria -- ver nota de la sistólica.",
        ),
        ClinicalReferenceValue(
            scenario="sepsis", domain="cardiovascular", descriptor="map",
            value=65.0, unit="mmHg", citation=_SEPSIS_3,
            phase_note=(
                "Fase de shock séptico / hipotensión refractaria (PAM<65 mmHg, criterio Sepsis-3 "
                "directo -- no derivada de sistólica/diastólica, es el criterio primario de la fuente)."
            ),
        ),
    ],
    "apnea": _bp_pair(
        "apnea", 200.0, 100.0, _HARRISON_AASM,
        "Representa el pico de la fase de arousal/despertar post-apnea, no la fase "
        "apneica de hipoxemia (SpO2 baja) del mismo ciclo -- son fases distintas del "
        "mismo escenario.",
    ),
    "seizure": _bp_pair(
        "seizure", 180.0, 100.0, _BRADLEY,
        "Representa específicamente la fase ictal (crisis activa, >180/100) -- no la fase "
        "post-ictal, que cursa con normalización/hipotensión relativa, no cubierta por este dato.",
    ),
    "hypoxia": _bp_pair(
        "hypoxia", 140.0, 90.0, _WEST_ACLS,
        "Representa la fase compensatoria temprana (taquicardia e hipertensión reactivas, "
        "rango citado 130-150/85-95, valor de punto medio) -- no la hipoxia tardía/descompensada, "
        "donde la PA típicamente cae.",
    ),
    "arrhythmia": _bp_pair(
        "arrhythmia", 90.0, 60.0, _AHA_ACC_HRS,
        "Representa la fase de descompensación hemodinámica de la arritmia (<90/60) -- muchas "
        "arritmias cursan con PA normal/compensada; este valor es específico del cuadro "
        "descompensado, no de la arritmia en general.",
    ),
    # Estrés y Ansiedad comparten la misma cifra transcrita ("aumenta EN 75-100 mmHg
    # sobre el basal", confirmado por el usuario -- no "hasta un valor de 75-100").
    # Sin diastólica ni PAM: la fuente solo especificó el incremento sistólico.
    "stress": [
        ClinicalReferenceValue(
            scenario="stress", domain="cardiovascular", descriptor="systolic_bp",
            value=207.5, unit="mmHg", citation=f"{_GUYTON} (descarga simpática aguda)",
            phase_note=(
                "Pico agudo de descarga simpática (basal 120 + incremento de 75-100 mmHg citado, "
                "punto medio 207.5) -- representa el momento álgido de la respuesta, no un valor "
                "sostenido durante todo el cuadro. Diastólica y PAM sin dato: la fuente transcrita "
                "solo especificó el incremento sistólico."
            ),
        ),
    ],
    "anxiety": [
        ClinicalReferenceValue(
            scenario="anxiety", domain="cardiovascular", descriptor="systolic_bp",
            value=207.5, unit="mmHg", citation=f"{_GUYTON} (descarga simpática aguda)",
            phase_note=(
                "Mismo valor y fuente que 'stress' -- el usuario dio una única cifra para "
                "Estrés/Ansiedad combinados. Pico agudo de descarga simpática (basal 120 + "
                "incremento de 75-100 mmHg citado, punto medio 207.5). Diastólica y PAM sin dato."
            ),
        ),
    ],
    "exercise": [
        ClinicalReferenceValue(
            scenario="exercise", domain="cardiovascular", descriptor="systolic_bp",
            value=162.0, unit="mmHg", citation=f"{_GUYTON} (respuesta presora al ejercicio dinámico)",
            phase_note=(
                "Rango citado +30-40% sobre basal (120 → 156-168), valor de punto medio 162. "
                "Diastólica y PAM sin dato: la fuente transcrita no especificó comportamiento "
                "diastólico durante el ejercicio -- no se inventó."
            ),
        ),
    ],
    # "fatigue" y "copd": sin entrada -- el usuario no dio fuente. Ausencia
    # deliberada, no una lista vacía por omisión.
}
