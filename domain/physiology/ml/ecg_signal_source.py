"""
Tanda 4, Pieza 2 (2026-07-04) — Modo (A): forma de onda ECG sintética
generada desde el estado REAL y actual del UPS, para alimentar al
clasificador real (`clinical/ecg_analyzer.py`). Siempre
`Provenance.SIMULACION` — nunca se presenta como sensor real.

Usa `TwelveLeadEcgGenerator` (src/signals/ecg/twelve_lead_generator.py),
NO `generate_demo_ecg_signal` (app/utils.py): confirmado leyendo su código
que esta última calcula `hr_rad` a partir de `heart_rate` pero nunca lo usa
para espaciar P/QRS/T (usa `t % 1` fijo, siempre ~60 bpm sin importar el
parámetro) — habría hecho falsa la premisa de "la onda refleja el
heart_rate real". `TwelveLeadEcgGenerator` sí ata `rr_interval = 60.0 /
params.heart_rate` al espaciado real de los latidos.

La onda solo refleja lo que el UPS realmente detecta hoy: la frecuencia
cardíaca real. No se fabrican patrones (STEMI, bloqueos, fibrilación...)
que el UPS no ha detectado — el único evento cardiovascular que el UPS
dispara por ritmo/frecuencia es `ARRHYTHMIA_RISK_HR_EXTREME`, y ese ya
queda reflejado con solo pasar el `heart_rate` real (una FC de 155 bpm ya
genera un trazado taquicárdico vía el espaciado RR correcto, sin necesitar
un flag de "patrón de arritmia" aparte que fabricaría una morfología que el
UPS no detectó).

Fase 5.1 (2026-08-30): `build_synthetic_ecg_from_ups()` recibe el
`UnifiedPhysiologicalState` ya construido, en vez de leerlo ella misma del
UPS -- puede venir del último snapshot persistido o del estado actual en
memoria sin persistir (`get_current_physiological_state()`); a esta
función no le importa cuál, solo necesita un `heart_rate` real."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from domain.physiology.state import EventType, UnifiedPhysiologicalState
from src.signals.ecg.twelve_lead_generator import EcgParameters, TwelveLeadEcgGenerator

__all__ = ["SyntheticEcgResult", "build_synthetic_ecg_from_ups"]


@dataclass(frozen=True)
class SyntheticEcgResult:
    signal: np.ndarray
    fs: float
    heart_rate: float
    arrhythmia_event_active: bool
    source_detail: str


def build_synthetic_ecg_from_ups(
    state: Optional[UnifiedPhysiologicalState],
    fs: float = 250.0,
    duration: float = 10.0,
) -> Optional[SyntheticEcgResult]:
    """`None` si `state` es `None` o todavía no tiene un descriptor
    `heart_rate` — no se fabrica una FC por defecto (nada de "72 bpm"
    inventado cuando no hay dato real).

    Fase 5.1 (2026-08-30): antes recibía `(session, patient_id)` y leía
    `get_latest_state()` internamente — acoplado a que el estado viniera
    siempre del UPS persistido. Esta función nunca necesitó más que un
    `UnifiedPhysiologicalState` ya construido; ahora lo recibe directo, así
    que el único llamador vivo (`render_ecg_classifier_panel()`,
    `twin_shell/pages.py`) puede pasarle el estado ACTUAL en memoria
    (`get_current_physiological_state()`) sin que esta función tenga que
    saber de dónde vino. Misma lógica, mismo resultado para el mismo
    `state` -- solo se movió quién hace la consulta a la base de datos."""
    if state is None:
        return None

    hr_desc = state.all_domains()["cardiovascular"].get("heart_rate")
    if hr_desc is None:
        return None

    arrhythmia_active = any(
        e.domain == "cardiovascular" and e.event_type == EventType.ARRHYTHMIA_RISK_HR_EXTREME
        for e in state.events
    )

    generator = TwelveLeadEcgGenerator(sampling_rate=fs)
    # t_amplitude=0.1 (en vez del 0.3 por defecto del generador): con el 0.3 por
    # defecto, la onda T queda lo bastante alta como para que
    # ECGAnalyzer.detect_r_peaks() (umbral fijo mean + 0.3*std) la detecte como un
    # segundo "pico R" por latido, duplicando la FC detectada. 0.1 mV sigue siendo
    # una amplitud de onda T fisiológicamente normal — no es un valor inventado,
    # es un ajuste real de un parámetro real para que estos dos componentes reales
    # (generador + analizador, nunca antes probados juntos) sean compatibles.
    # Verificado en el rango 40-180 bpm: FC detectada = FC real en todos los casos.
    params = EcgParameters(heart_rate=hr_desc.value, t_amplitude=0.1)
    leads = generator.generate_ecg(duration=duration, params=params)

    return SyntheticEcgResult(
        signal=leads["II"],
        fs=fs,
        heart_rate=hr_desc.value,
        arrhythmia_event_active=arrhythmia_active,
        source_detail=f"twin_os:ecg_sintetico:hr_real={hr_desc.value:.0f}bpm",
    )
