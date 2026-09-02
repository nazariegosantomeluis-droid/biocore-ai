"""
Puente Paso 2 — conecta el módulo R-RCR (`r_rcr.py` + calibración
fisiológica de `physiological_flow.py`) al UPS vivo.

Lee `heart_rate` real de un snapshot ya persistido del UPS, calcula
presión con el segundo set de parámetros fisiológicos (PENDIENTE DE
VALIDACIÓN EXPERTA — ver `physiological_flow.py`), y persiste el
resultado como `PhysiologicalDescriptor` con
`Provenance.MODELO_HEMODINAMICO`, adjuntado al MISMO snapshot vía
`append_descriptors()` — coexiste con los descriptores medidos/simulados
y con cualquier `ClinicalReferenceValue` ya adjunta
(`blood_pressure_references.py`), sin sobrescribir ninguno.

Nombres de descriptor con sufijo `_modelo` (`systolic_bp_modelo`, ...) —
deliberadamente distintos de `"systolic_bp"`/`"diastolic_bp"`/`"map"`
(usados por `ClinicalReferenceValue`, y reservados para un futuro
descriptor medido/derivado real) para que nunca colisionen como clave de
diccionario al leer un snapshot (`repository.py::_domain_state_from_values`
indexa `PhysiologicalDescriptor` por nombre dentro de cada dominio).

No toca `run_rich_scenario()`, `builder.py` ni ningún flujo existente —
se invoca aparte, explícitamente, sobre un snapshot ya persistido.
"""

from __future__ import annotations

from typing import Dict, Optional

import numpy as np
from sqlalchemy.orm import Session

from .physiological_flow import (
    PHYSIOLOGICAL_PARAMETERS_CITATION,
    PHYSIOLOGICAL_PARAMETERS_PENDING_VALIDATION,
    PHYSIOLOGICAL_RRCR_PARAMETERS,
    STROKE_VOLUME_CITATION,
    physiological_pulsatile_flow,
)
from .r_rcr import simulate_r_rcr
from ..state.repository import append_descriptors
from ..state.schema import PhysiologicalDescriptor, Provenance

__all__ = ["compute_calculated_pressure", "compute_and_attach_calculated_pressure"]

_N_CYCLES = 10
_N_POINTS_PER_CYCLE = 201


def compute_calculated_pressure(
    heart_rate_bpm: float, n_cycles: int = _N_CYCLES, n_points_per_cycle: int = _N_POINTS_PER_CYCLE
) -> Dict[str, float]:
    """Corre el R-RCR con la calibración fisiológica (Paso 1 aprobado) para
    un `heart_rate_bpm` dado y devuelve sistólica/diastólica/PAM del
    último ciclo (régimen periódico convergido, no el transitorio).

    Sistólica = máximo de la presión de entrada en el último ciclo;
    diastólica = mínimo; PAM = media temporal REAL del ciclo (integral
    trapezoidal de la curva calculada, no la fórmula de aproximación
    diastólica+⅓(sistólica−diastólica) que usa `estimate_map()` para datos
    de guía clínica sin curva -- aquí sí tenemos la curva completa, así
    que la media real es más rigurosa que la aproximación)."""
    flow_fn, period_s = physiological_pulsatile_flow(heart_rate_bpm)
    result = simulate_r_rcr(
        flow_fn,
        PHYSIOLOGICAL_RRCR_PARAMETERS,
        period_s=period_s,
        n_cycles=n_cycles,
        n_points_per_cycle=n_points_per_cycle,
    )

    p_last = result.pressure_inlet[-n_points_per_cycle:]
    t_last = result.time[-n_points_per_cycle:]

    systolic = float(np.max(p_last))
    diastolic = float(np.min(p_last))
    map_value = float(np.trapezoid(p_last, t_last) / (t_last[-1] - t_last[0]))

    return {
        "systolic_bp": systolic,
        "diastolic_bp": diastolic,
        "map": map_value,
        "period_s": period_s,
        "heart_rate_bpm": heart_rate_bpm,
    }


def compute_and_attach_calculated_pressure(
    session: Session,
    snapshot_id: str,
    heart_rate_bpm: float,
    source_detail: Optional[str] = None,
) -> Dict[str, float]:
    """Calcula la presión (ver `compute_calculated_pressure`) y la persiste
    como tres `PhysiologicalDescriptor` (`systolic_bp_modelo`,
    `diastolic_bp_modelo`, `map_modelo`) con
    `Provenance.MODELO_HEMODINAMICO`, adjuntos al `snapshot_id` dado.

    No crea un snapshot nuevo -- `snapshot_id` debe ser el de un
    `SnapshotRecord` ya persistido (p.ej. el último de una corrida de
    `run_rich_scenario()` / `get_latest_snapshot_id()`)."""
    assert PHYSIOLOGICAL_PARAMETERS_PENDING_VALIDATION, (
        "Los parámetros fisiológicos R/Rp/Rd/C siguen pendientes de confirmación experta -- "
        "ver physiological_flow.py. Este assert es una salvaguarda deliberada: si algún día se "
        "confirman y esta constante pasa a False, hay que revisar conscientemente si el "
        "comportamiento de este puente sigue siendo el correcto, no solo borrar el assert."
    )

    pressures = compute_calculated_pressure(heart_rate_bpm)
    # Confianza FIJA explícita (2026-08-01), NO default_confidence(): la banda de
    # MODELO_HEMODINAMICO se ensanchó (0.30-0.80) para darle espacio a
    # closed_loop_ups_bridge.py (3 escenarios validados, confianza ~0.75) sin
    # inventar una segunda procedencia -- pero ESTE puente (Módulo 1, R-RCR
    # estático, sin barórreflejo/retorno venoso/validación experta) no cambió en
    # nada su propio estado de validación. Se fija 0.425 -- el mismo punto medio
    # que `default_confidence()` ya devolvía bajo la banda ORIGINAL (0.30-0.55) --
    # para preservar el comportamiento histórico exacto de este puente, en vez de
    # heredar silenciosamente el nuevo punto medio (0.55) de la banda ensanchada,
    # que implicaría una confianza que este puente en particular no se ganó.
    confidence = 0.425

    citation_detail = (
        f"{source_detail + ' | ' if source_detail else ''}"
        f"modulo:r_rcr_fisiologico | SV_ref: {STROKE_VOLUME_CITATION} | "
        f"Parametros R/Rp/Rd/C: {PHYSIOLOGICAL_PARAMETERS_CITATION}"
    )

    descriptors = [
        PhysiologicalDescriptor(
            "systolic_bp_modelo", pressures["systolic_bp"], "mmHg",
            Provenance.MODELO_HEMODINAMICO, confidence, citation_detail,
        ),
        PhysiologicalDescriptor(
            "diastolic_bp_modelo", pressures["diastolic_bp"], "mmHg",
            Provenance.MODELO_HEMODINAMICO, confidence, citation_detail,
        ),
        PhysiologicalDescriptor(
            "map_modelo", pressures["map"], "mmHg",
            Provenance.MODELO_HEMODINAMICO, confidence, citation_detail,
        ),
    ]
    append_descriptors(session, snapshot_id=snapshot_id, domain="cardiovascular", descriptors=descriptors)

    return pressures
