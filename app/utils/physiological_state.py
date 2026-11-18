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

from typing import TYPE_CHECKING, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from domain.physiology.state import (
    horizon_of,
    DERIVED_INPUTS,
    CarryOrigin,
    ComposedPatient,
    DomainState,
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


def overlay_current_on_composed(
    current: UnifiedPhysiologicalState, composed: Optional[ComposedPatient],
    defer_to_patient: frozenset = frozenset(),
) -> Tuple[UnifiedPhysiologicalState, Dict[Tuple[str, str], CarryOrigin]]:
    """T1 de la ruta integrada (2026-11-18): el cuerpo del gemelo = el paciente compuesto con el estado en memoria
    encima. Regla firmada: lo que el estudiante mueve ahora (sliders o escenario) gana; lo que no movió viene del
    paciente, con su origen. Devuelve el estado y el origen de TODO valor que viene del paciente -- también los de su
    último snapshot, con edad 0 respecto a ese snapshot (revisión final de la T1): sin origen, un valor guardado por
    un laboratorio hace una hora se vería igual que el que el slider mueve ahora.

    - Sin paciente (`composed is None`): el estado en memoria tal cual.
    - Un derivado del paciente (`DERIVED_INPUTS`) se quita si el estado actual trae alguna de sus entradas: unos
      puntos NEWS2 viejos no se muestran junto a la FC nueva del slider.
    - Eventos: los del estado actual para los dominios que trae; los del paciente para los demás. Un evento de FC
      viejo no colorea el corazón si el estudiante ya movió la FC.
    - `defer_to_patient` (T1.1): entradas `(dominio, descriptor)` que el estado actual trae solo porque un slider se
      sembró con el valor del paciente y el estudiante no lo movió. Para ellas gana el valor del paciente, con su
      procedencia y su edad; un derivado actual cuyas entradas están todas diferidas cede también.
    """
    if composed is None:
        return current, {}
    patient_domains = composed.state.all_domains()
    deferred = {k for k in defer_to_patient if patient_domains[k[0]].get(k[1]) is not None}
    now_domains = current.all_domains()

    def _defers(domain: str, name: str) -> bool:
        if (domain, name) in deferred:
            return True
        inputs = DERIVED_INPUTS.get((domain, name))
        return bool(inputs) and all(inp in deferred for inp in inputs)

    now_keys = {(domain, name) for domain, dom in now_domains.items() for name in dom.descriptors
                if not _defers(domain, name)}
    origins: Dict[Tuple[str, str], CarryOrigin] = {}
    merged: Dict[str, DomainState] = {}
    latest_ts = composed.state.timestamp
    for domain, patient_dom in composed.state.all_domains().items():
        current_dom = now_domains.get(domain)
        current_descriptors = {name: d for name, d in (current_dom.descriptors if current_dom is not None else {}).items()
                               if (domain, name) in now_keys}
        descriptors = {}
        for name, descriptor in patient_dom.descriptors.items():
            if name in current_descriptors:
                continue
            if (domain, name) in DERIVED_INPUTS and any(inp in now_keys for inp in DERIVED_INPUTS[(domain, name)]):
                continue
            descriptors[name] = descriptor
            origins[(domain, name)] = composed.origins.get(
                (domain, name), CarryOrigin(composed.latest_snapshot_id, latest_ts, descriptor.provenance, 0.0,
                                            horizon_of(descriptor.source_detail), descriptor.source_detail))
        descriptors.update(current_descriptors)
        merged[domain] = DomainState(domain=domain, descriptors=descriptors)
    moved = {domain for domain, _name in now_keys}
    # Revisión final de la T1.1: un dominio cuyas entradas actuales están TODAS diferidas al paciente toma sus eventos
    # del paciente, no del estado actual (que solo los repetía, calculados del valor sembrado y redondeado).
    fully_deferred = {domain for domain, dom in now_domains.items()
                      if dom.descriptors and all(_defers(domain, name) for name in dom.descriptors)}
    events = ([e for e in current.events if e.domain not in fully_deferred]
              + [e for e in composed.state.events if e.domain not in moved])
    return UnifiedPhysiologicalState(patient_id=current.patient_id, timestamp=current.timestamp, **merged,
                                     events=events), origins
