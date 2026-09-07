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

__all__ = ["AROUSAL_TAQUICARDIA_BAR", "VALIDATED_RULES"]


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


VALIDATED_RULES: Tuple[CouplingRule, ...] = (AROUSAL_TAQUICARDIA_BAR,)
"""Único catálogo activo. `apply_couplings()` lo consume en el flujo vivo.
Añadir una regla aquí exige la firma completa del experto documentada
arriba -- no es un ajuste incidental."""
