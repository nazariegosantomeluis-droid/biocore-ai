"""
Catálogo de reglas de acoplamiento fisiológico VALIDADAS.

Cada regla se transcribe LITERALMENTE de la firma de un experto -- no la
genera este código, no se ajusta "a ojo". `VALIDATED_RULES` es la única
fuente de verdad de qué acoplamientos están activos en el flujo vivo
(`apply_couplings()`, `bridge.py`).

Disciplina (lección del detector de HR): UNA regla validada a fondo vale
más que varias a medias. Las direcciones espejo (relajación -> ↓FC) y
otros acoplamientos son reglas futuras, cada una con SU propia firma --
no se añaden aquí "por simetría".

--------------------------------------------------------------------------
Regla 1 -- AROUSAL_TAQUICARDIA_BAR  (Acoplamientos Sub-fase B, 2026-09-06)
--------------------------------------------------------------------------
FIRMA DEL EXPERTO:
  - Dirección: arousal cortical -> ↑ frecuencia cardíaca. Retirada vagal +
    activación simpática vía centros bulbares cardiovasculares.
    Fuente: Guyton & Hall, Tratado de Fisiología Médica, 14a ed., cap. 61
    (Sistema Nervioso Autónomo y la respuesta de estrés).
  - Ancla: BAR (Ratio Beta/Alfa) > 1.8. Basal 0.8-1.2; arousal (Stroop,
    Trier Social Stress Test) > 1.8. Fuente: Schutter DJLG 2006 /
    Handbook of Psychophysiology, 3a ed., cap. 10.
  - Magnitud: +15.0 bpm. Acotado por el experto a arousal cognitivo PURO,
    rango +10 a +25 bpm en las pruebas citadas; +15.0 es el punto medio
    conservador (no el techo).
  - Escenarios: NO aplicar sobre `stress` / `anxiety` / `seizure` -- su CV
    ya modela la descarga simpática (doble contabilidad). Ya bloqueados
    estructuralmente por `COUPLING_DISABLED_SCENARIOS` (`bridge.py`).
  - `validation_status = VALIDADO_POR_FUENTE` -> el puente le asigna
    confianza 0.70 (extremo alto de la banda de `DERIVADO_ACOPLAMIENTO`,
    todavía por debajo de `SIMULACION` -- sigue siendo un cálculo, no una
    medición).
"""

from __future__ import annotations

from typing import Tuple

from .rules import (
    ComparisonOperator,
    CouplingCondition,
    CouplingEffect,
    CouplingRule,
    EffectDirection,
    ValidationStatus,
)

__all__ = ["AROUSAL_TAQUICARDIA_BAR", "HIPOXIA_TAQUICARDIA", "VALIDATED_RULES"]


AROUSAL_TAQUICARDIA_BAR = CouplingRule(
    rule_id="AROUSAL_TAQUICARDIA_BAR",
    condition=CouplingCondition(
        domain="neurological",
        descriptor="bar",
        operator=ComparisonOperator.GREATER_THAN,
        threshold=1.8,
        unit="ratio (adimensional)",
    ),
    effect=CouplingEffect(
        domain="cardiovascular",
        descriptor="heart_rate",
        direction=EffectDirection.AUMENTA,
        magnitude_hint="+10 a +25 bpm (arousal cognitivo puro, Stroop / Trier Social Stress Test)",
        magnitude_delta=15.0,
    ),
    source=(
        "Guyton & Hall, Tratado de Fisiologia Medica, 14a ed., cap. 61 (SNA y respuesta de estres) | "
        "Schutter DJLG 2006 / Handbook of Psychophysiology 3a ed., cap. 10 (Beta/Alpha Ratio como "
        "biomarcador de arousal; basal 0.8-1.2, arousal >1.8)"
    ),
    validation_status=ValidationStatus.VALIDADO_POR_FUENTE,
    enabled=True,
    notes=(
        "Arousal cortical (BAR>1.8) -> retirada vagal + activacion simpatica -> ↑FC. Acotado por "
        "el experto a arousal cognitivo PURO (+10-25 bpm; +15.0 punto medio conservador). NO "
        "aplicar sobre escenarios que ya modelan la descarga simpatica (COUPLING_DISABLED_SCENARIOS). "
        "La direccion espejo (relajacion -> ↓FC) es una regla futura con su propia firma."
    ),
)


# --------------------------------------------------------------------------
# Regla 2 -- HIPOXIA_TAQUICARDIA  (ficha 1, firmada por Luis el 2026-11-18)
# --------------------------------------------------------------------------
# FIRMA DEL EXPERTO («firmo las dos fichas de acoplamiento»; se firmaron las
# propuestas de `docs/contenido/fichas_acoplamientos.md`, ficha 1):
#   - Dirección: SpO2 baja -> ↑ FC, por los quimiorreceptores periféricos y la
#     retirada vagal (Lucy 2000; Niewinski 2025; Halliwill 2003).
#   - Ancla: spo2 <= 91 %, el límite de la banda de 3 puntos NEWS2 de la SpO2
#     escala 1 (RCP 2017). La fuente no da un umbral (la respuesta es
#     continua): el umbral fijo es Criterio BIOCORE y así se declara.
#   - Magnitud: +13 lpm, la medida en sanos a SpO2 ~86 % (Halliwill 2003:
#     61.2 -> 74.7 lpm). En la franja 87-91 % sobreestima.
#   - Confianza: VALIDADO_POR_FUENTE -> 0.70.
#   - Escenarios bloqueados por regla: hypoxia, apnea, copd, sepsis (su
#     simulador ya modela la FC con la caída de SpO2); más la lista global.
#   - Ventana: la SpO2 y la FC de la misma ventana de 120 s (la del
#     compositor). Los escenarios y el gemelo guardan SpO2 y FC en un mismo
#     snapshot, pero esos guardados no llaman a `apply_couplings()`: hoy solo
#     lo hacen el compositor neurocardiaco (sin SpO2) y el guardado del EEG
#     (sin FC). La regla no dispara en el flujo vivo hasta la T6.
HIPOXIA_TAQUICARDIA = CouplingRule(
    rule_id="HIPOXIA_TAQUICARDIA",
    condition=CouplingCondition(
        domain="respiratory",
        descriptor="spo2",
        operator=ComparisonOperator.LESS_THAN_OR_EQUAL,
        threshold=91.0,
        unit="%",
    ),
    effect=CouplingEffect(
        domain="cardiovascular",
        descriptor="heart_rate",
        direction=EffectDirection.AUMENTA,
        magnitude_hint=("+13.5 lpm a SpO2 ~86 % en sanos, hipoxia isocapnica (Halliwill 2003); "
                        "pendiente 0.6-1.0 lpm por % de caida"),
        magnitude_delta=13.0,
    ),
    source=(
        "Halliwill JR, Morgan BJ, Charkoudian N. J Physiol 2003;552(Pt 1):295-302. "
        "doi:10.1113/jphysiol.2003.050708 | Niewinski P, Tubek S, Josiak K, Nowak K, Ponikowski P. "
        "Sci Rep 2025;15:6633. doi:10.1038/s41598-025-91214-6 | Lucy SD y cols. Exp Physiol "
        "2000;85(2):227-237. doi:10.1111/j.1469-445X.2000.01932.x | Umbral: banda de 3 puntos NEWS2 de la "
        "SpO2 escala 1 (RCP 2017)"
    ),
    validation_status=ValidationStatus.VALIDADO_POR_FUENTE,
    enabled=True,
    notes=(
        "Quimiorreflejo periferico -> retirada vagal -> ↑FC. Umbral 91 % = Criterio BIOCORE (la respuesta "
        "es continua). Ventana de 120 s entre la SpO2 y la FC. Firmada por Luis el 2026-11-18 (ficha 1)."
    ),
    blocked_scenarios=("hypoxia", "apnea", "copd", "sepsis"),
)


VALIDATED_RULES: Tuple[CouplingRule, ...] = (AROUSAL_TAQUICARDIA_BAR, HIPOXIA_TAQUICARDIA)
"""Único catálogo activo. `apply_couplings()` lo consume en el flujo vivo.
Añadir una regla aquí exige la firma completa del experto documentada
arriba -- no es un ajuste incidental."""
