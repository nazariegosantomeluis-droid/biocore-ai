"""
Compositor multi-dominio del paciente único (Tanda 1 de (b), 2026-09-08).

El acoplamiento neuro->CV (`coupling/`) necesita, para disparar, un
snapshot donde el `bar` (Ratio Beta/Alfa, entra solo por EEG Lab) y el
`heart_rate` medido (entra por ECG/HRV/Twin OS) COEXISTAN. El diagnóstico
confirmó que ningún flujo vivo produce eso: cada lab persiste un snapshot
mono-fuente.

`compose_neuro_cardiac_snapshot()` compone uno: toma el ÚLTIMO `bar` real
persistido del paciente y el ÚLTIMO `heart_rate` real persistido, y los
escribe juntos en un snapshot nuevo -- con procedencia HONESTA por
descriptor:

- `bar`: copia LITERAL del descriptor de origen. Su procedencia queda
  intacta (la del band power de EEG Lab). Es "el estado neuro actual del
  paciente" -- no hay uno más reciente.
- `heart_rate`: copia del valor real, pero con `Provenance.ARRASTRE_TEMPORAL`
  (hold de orden cero -- ver `schema.py`) y un `source_detail` que DECLARA
  el snapshot de origen, su timestamp y la edad del arrastre en segundos.

Barandilla dura (Art. I): si falta el `bar` real, o falta el `heart_rate`
real, o el `heart_rate` es más viejo que `max_hr_carry_age_s` respecto al
`bar`, el compositor NO compone un snapshot a medias -- devuelve
`ComposeResult(available=False, reason=...)`. Nunca finge un acoplamiento.
Mismo patrón de degradación que `PLVResult` (`biomarkers.py`): "no
disponible con motivo", jamás un número inventado.

NO pasa por `from_digital_twin_organism()` -- esa función aplica UNA sola
procedencia/source_detail a todos los descriptores, lo que aplanaría la
distinción bar-real / FC-arrastrada. El compositor arma los `DomainState`
directamente.

Tanda 2 (2026-09-08): tras el `save_state()` del camino feliz, el
compositor llama `apply_couplings(session, composed_id, VALIDATED_RULES,
scenario=None)` -- "componer" es atómicamente "componer + acoplar", ningún
llamador puede olvidar el segundo paso. `scenario=None` SIEMPRE: los
`SimulationScenario` (incluidos los bloqueados) corren solo sobre
pacientes efímeros, nunca sobre el paciente continuo; `COUPLING_DISABLED_
SCENARIOS` queda intacto como barandilla estructural para un hipotético
compositor de pacientes-de-escenario futuro. Si la regla dispara
(`bar > 1.8`), `heart_rate_acoplado` se adjunta al MISMO snapshot; si no,
el snapshot combinado queda con `bar` + `heart_rate` coexistiendo pero sin
fila acoplada -- el compositor no fuerza un acoplamiento donde el arousal
no lo justifica. `ComposeResult.coupled` expone qué disparó (vacío si
nada).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from .repository import (
    get_latest_snapshot_id_with_descriptor,
    get_state_by_snapshot_id,
    save_state,
)
from .schema import (
    DomainState,
    PhysiologicalDescriptor,
    Provenance,
    UnifiedPhysiologicalState,
)

__all__ = ["ComposeResult", "compose_neuro_cardiac_snapshot", "DEFAULT_MAX_HR_CARRY_AGE_S"]

# Ventana de antigüedad admisible del `heart_rate` arrastrado respecto al
# `bar`. ~120s: rango de la respuesta autonómica AGUDA que el acoplamiento
# modela (arousal -> taquicardia en segundos-minutos). Un HR de hace 20 min
# con un BAR de ahora no es acoplamiento, es correlación espuria entre
# momentos distintos. Es config del compositor, no una constante clínica
# firmada -- el experto la ajusta en una tanda futura junto con la posible
# degradación de confianza por edad.
DEFAULT_MAX_HR_CARRY_AGE_S: float = 120.0


@dataclass(frozen=True)
class ComposeResult:
    """Resultado de una composición -- mismo patrón que `PLVResult`:
    `available` distingue "compuso" de "no disponible (con motivo)", nunca
    se cae a un snapshot a medias.

    `coupled`: los acoplamientos que dispararon sobre el snapshot compuesto
    (`AppliedCoupling` de `coupling/bridge.py`) -- tupla vacía si `bar`
    coexiste con `heart_rate` pero la regla no disparó (arousal insuficiente),
    o si `available=False`."""

    available: bool
    snapshot_id: Optional[str] = None
    reason: Optional[str] = None
    hr_age_s: Optional[float] = None
    coupled: Tuple = field(default_factory=tuple)


def compose_neuro_cardiac_snapshot(
    session: Session,
    patient_id: str,
    *,
    max_hr_carry_age_s: float = DEFAULT_MAX_HR_CARRY_AGE_S,
) -> ComposeResult:
    """Compone el último `bar` real + el último `heart_rate` real del
    paciente en un snapshot nuevo, con procedencia honesta por descriptor.

    Devuelve `ComposeResult(available=False, reason=...)` -- sin persistir
    nada -- si falta cualquiera de los dos, o si el `heart_rate` excede la
    ventana de arrastre respecto al `bar`."""
    snap_bar_id = get_latest_snapshot_id_with_descriptor(
        session, patient_id, "neurological", "bar"
    )
    if snap_bar_id is None:
        return ComposeResult(available=False, reason="sin BAR persistido")

    snap_hr_id = get_latest_snapshot_id_with_descriptor(
        session, patient_id, "cardiovascular", "heart_rate"
    )
    if snap_hr_id is None:
        return ComposeResult(available=False, reason="sin FC medida persistida")

    bar_state = get_state_by_snapshot_id(session, snap_bar_id)
    hr_state = get_state_by_snapshot_id(session, snap_hr_id)
    # Defensivo: los ids vienen de una consulta que EXIGE el descriptor, así
    # que esto no debería pasar salvo borrado concurrente entre consultas.
    if bar_state is None or hr_state is None:
        return ComposeResult(available=False, reason="snapshot de origen desapareció entre consultas")

    bar_desc = bar_state.neurological.get("bar")
    hr_desc = hr_state.cardiovascular.get("heart_rate")
    if bar_desc is None or hr_desc is None:
        return ComposeResult(available=False, reason="descriptor de origen ausente en su snapshot")

    # |Δ| -- NO se exige hr_ts < bar_ts estricto: el datetime.now() no
    # monótono en Windows invierte pares por microsegundos (ver
    # get_latest_state), y aquí importa la magnitud del hueco, no su signo.
    hr_age_s = abs((bar_state.timestamp - hr_state.timestamp).total_seconds())
    if hr_age_s > max_hr_carry_age_s:
        return ComposeResult(
            available=False,
            reason=(
                f"FC arrastrada demasiado vieja: {hr_age_s:.0f}s > {max_hr_carry_age_s:.0f}s "
                "-- arousal y FC de momentos distintos, no acoplamiento"
            ),
            hr_age_s=hr_age_s,
        )

    carried_hr = PhysiologicalDescriptor(
        name="heart_rate",
        value=hr_desc.value,
        unit=hr_desc.unit,
        provenance=Provenance.ARRASTRE_TEMPORAL,
        confidence=hr_desc.confidence,  # se hereda TAL CUAL de origen
        source_detail=(
            f"FC arrastrada del snapshot {snap_hr_id} del "
            f"{hr_state.timestamp.isoformat()} (edad {hr_age_s:.0f}s)"
        ),
    )

    composed = UnifiedPhysiologicalState(
        patient_id=patient_id,
        timestamp=datetime.now(timezone.utc),
        cardiovascular=DomainState(domain="cardiovascular", descriptors={"heart_rate": carried_hr}),
        respiratory=DomainState(domain="respiratory", descriptors={}),
        neurological=DomainState(domain="neurological", descriptors={"bar": bar_desc}),
        events=[],
    )

    composed_id = save_state(session, composed)

    # "Componer" es atómicamente "componer + acoplar" -- import perezoso
    # para que la capa `state/` no dependa de `coupling/` en tiempo de
    # import (coupling ya depende de state; la llamada es one-way en
    # runtime). scenario=None es estructural aquí -- ver docstring del módulo.
    from domain.physiology.coupling import VALIDATED_RULES, apply_couplings

    applied = apply_couplings(session, composed_id, VALIDATED_RULES, scenario=None)
    return ComposeResult(
        available=True, snapshot_id=composed_id, hr_age_s=hr_age_s, coupled=tuple(applied)
    )
