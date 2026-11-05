"""
Motor de acoplamiento fisiológico (Paso 1b, 2026-07-15).

Dado un `UnifiedPhysiologicalState` y un conjunto de `CouplingRule`,
`evaluate()` calcula qué reglas HABILITADAS se disparan y qué efectos
PROPONDRÍAN -- nunca los aplica al estado; aplicar es trabajo de
`coupling/bridge.py::apply_couplings()`.

Corrección 2026-11-05 (Tanda 1 de contención, Art. I): la versión original de
este docstring decía que el motor estaba "dormido", que ningún módulo importaba
este paquete y que el catálogo estaba vacío. Ya no es cierto: `catalog.py`
trae UNA regla activa (`AROUSAL_TAQUICARDIA_BAR`, VALIDADO_POR_FUENTE) y el
paquete tiene dos llamadores vivos de `apply_couplings()`:
`state/composer.py::compose_neuro_cardiac_snapshot()` (botón "Componer y
evaluar" de Digital Twin OS, donde la regla sí dispara) y el botón "Guardar
estado al gemelo" del EEG Lab (no-op honesto: ese snapshot no trae FC base).
Con un estado sin el descriptor de la condición o sin reglas habilitadas,
`evaluate()` devuelve una lista vacía: no falla ni inventa.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from domain.physiology.state.schema import UnifiedPhysiologicalState

from .rules import CouplingRule

__all__ = ["ProposedCoupling", "evaluate"]


@dataclass(frozen=True)
class ProposedCoupling:
    """Un acoplamiento propuesto -- nunca aplicado por este módulo. Trae
    consigo lo necesario para que quien decida aplicarlo (una fase futura)
    pueda anclar su explicación: la regla que disparó y el valor real
    observado que cruzó el umbral."""

    rule: CouplingRule
    observed_value: float

    @property
    def effect(self):
        return self.rule.effect

    @property
    def source(self) -> str:
        return self.rule.source


def evaluate(state: UnifiedPhysiologicalState, rules: Iterable[CouplingRule]) -> List[ProposedCoupling]:
    """Evalúa qué reglas se disparan contra `state`. Nunca modifica `state`.

    Reglas con `enabled=False` (el valor por defecto de toda `CouplingRule`)
    se ignoran por completo -- ni siquiera se evalúa su condición, para que
    quede clarísimo que una regla apagada no tiene ningún efecto, ni
    parcial ni de prueba. Si el descriptor de la condición no existe en el
    estado (p.ej. un organismo recién creado que nunca recibió esa señal),
    la regla simplemente no se dispara -- no se inventa un valor."""
    proposals: List[ProposedCoupling] = []
    for rule in rules:
        if not rule.enabled:
            continue

        domain_state = state.all_domains().get(rule.condition.domain)
        if domain_state is None:
            continue

        descriptor = domain_state.get(rule.condition.descriptor)
        if descriptor is None:
            continue

        if rule.condition.is_triggered_by(descriptor.value):
            proposals.append(ProposedCoupling(rule=rule, observed_value=descriptor.value))

    return proposals
