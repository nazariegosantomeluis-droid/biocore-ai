"""
Fase 5.1 (punto único de verdad del estado fisiológico, 2026-08-30) —
análogo literal de `get_active_patient_id()` (Fase 3, `patient_session.py`
en este mismo directorio): una función, los lectores convergen.

El diagnóstico de la Fase 5, Paso 0 encontró que 3 paneles de Twin OS
(Cuerpo Digital SVG, Riesgo ML, clasificador ECG) leían `get_latest_state()`
— el ÚLTIMO SNAPSHOT PERSISTIDO — mientras las tarjetas de órgano y el
resto del panel leían `organism` directo (memoria). Como los sliders
(`render_sensor_controls()`, `twin_shell/pages.py`) mutan el organismo sin
persistir nunca por sí mismos, los dos grupos de lectores divergían
visiblemente: mover un slider actualizaba las tarjetas al instante pero
dejaba el SVG/ML/ECG mostrando el estado de hace varios clics.

`get_current_physiological_state()` es la MISMA conversión que ya usan los
4 escritores del UPS (`from_digital_twin_organism()`, reutilizada tal
cual) — solo que sin llamar `save_state()`. Devuelve la MISMA forma que
`get_latest_state()` (`UnifiedPhysiologicalState`), con la MISMA
disciplina de procedencia (`Provenance`/`confidence` reales, derivados del
organismo — nunca inventados). La diferencia entre leer aquí y leer
`get_latest_state()` es "estado actual vs. último guardado", NO "honesto
vs. atajo" — ambos caminos son igualmente honestos, solo miran a un
momento distinto.

Esta función NO decide cuándo persistir. Los 4 escritores (Guardar este
momento -- ex "Sincronizar", Simulador de escenarios, Narrador,
Razonamiento causal) siguen escribiendo al UPS exactamente igual que antes
de la Fase 5.1 — la trayectoria histórica no cambia.

Fase 5.3 (2026-08-30): `persist_current_state()` es la prima de escritura
de `get_current_physiological_state()` -- uno persiste lo que el otro
devuelve sin persistir. Encapsula el patrón `from_digital_twin_organism()`
+ `save_state()` que los 4 escritores repetían a mano, idéntico en los 4
salvo el `source_detail` (confirmado por grep antes de extraerlo: los 4
usan `provenance=Provenance.SIMULACION`, ninguno pasa `confidence`
explícito) -- refactor de "extraer método", cero cambio de comportamiento.
Ver CHANGELOG.md, Fase 5.3.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Tuple

from sqlalchemy.orm import Session

from domain.physiology.state import (
    Provenance,
    UnifiedPhysiologicalState,
    from_digital_twin_organism,
    save_state,
)

from .patient_session import get_active_patient_id

if TYPE_CHECKING:
    from app.engines.digital_twin_organism import DigitalTwinOrganism


def get_current_physiological_state(
    organism: "DigitalTwinOrganism", patient_id: Optional[str] = None
) -> UnifiedPhysiologicalState:
    """El estado fisiológico ACTUAL del organismo en memoria — construido
    con `from_digital_twin_organism()`, sin persistir. Mismo `patient_id`
    que `get_active_patient_id()` si no se pasa uno explícito; se acepta un
    `patient_id` explícito para los pocos llamadores que ya operan sobre un
    paciente distinto al activo (p.ej. el modo "Basal" del simulador de
    escenarios, que sustituye temporalmente al paciente activo — ver
    `set_active_patient_id()` — pero ahí siempre se lee tras haber
    sustituido, así que `get_active_patient_id()` ya basta incluso en ese
    caso; el parámetro queda disponible por si algún llamador futuro
    necesita leer explícitamente el estado de un paciente que no es el
    activo)."""
    if patient_id is None:
        patient_id = get_active_patient_id()
    return from_digital_twin_organism(
        organism,
        patient_id,
        provenance=Provenance.SIMULACION,
        source_detail="estado_actual_en_memoria:sin_persistir",
    )


def persist_current_state(
    session: Session,
    organism: "DigitalTwinOrganism",
    patient_id: str,
    source_detail: str,
    provenance: Provenance = Provenance.SIMULACION,
) -> Tuple[UnifiedPhysiologicalState, str]:
    """Fase 5.3: helper compartido de escritura al UPS -- reemplaza el
    patrón `from_digital_twin_organism(...) + save_state(...)` que los 4
    escritores del UPS (Guardar este momento, Simulador de escenarios,
    Narrador, Razonamiento causal) construían cada uno a mano. Mismo
    resultado exacto: persiste un snapshot nuevo (la trayectoria SIEMPRE
    crece, nunca sobrescribe -- ver `save_state()`,
    `domain/physiology/state/repository.py`) y devuelve `(state,
    snapshot_id)`.

    `patient_id` se recibe explícito (no se asume `get_active_patient_id()`
    dentro del helper) porque el Simulador de escenarios en modo "Basal"
    persiste bajo un paciente efímero temporal, no necesariamente el activo
    -- este helper no decide identidad, solo persiste sobre la que el
    llamador ya resolvió (mismo principio que `get_current_physiological_
    state()` arriba, que sí ofrece un default porque casi todos sus
    llamadores SÍ quieren el paciente activo)."""
    state = from_digital_twin_organism(organism, patient_id, provenance=provenance, source_detail=source_detail)
    snapshot_id = save_state(session, state)
    return state, snapshot_id
