"""Registro de evidencia: de dónde sale cada valor que muestran el banner del paciente activo, Calculadoras y las
tarjetas del gemelo (pasaporte de evidencia, 2026-11-17).

Art. I: este archivo NO redacta nada. Cada texto es una cita literal y contigua del código o de docs/, con su
ubicación (`archivo:línea`), copiada tal cual la encontró la extracción de solo lectura. Si un apartado no está escrito
en el repositorio, queda en `None` y el pasaporte dice «no documentado»; nunca se rellena.
`tests/test_pasaporte_evidencia.py` comprueba que cada cita aparezca en el archivo que dice su ubicación.

Campos: `<superficie>.<id>`. En Calculadoras, `<id>` es el `report_id` de `_card()` (`calculators/pages.py`), así
que el pasaporte se coloca con una sola línea dentro de `_card()`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

SURFACES = ("banner", "calculadoras", "gemelo")


@dataclass(frozen=True)
class Cita:
    """Texto literal del repositorio y dónde está."""

    texto: str
    ubicacion: str          # "archivo:línea"

    @property
    def archivo(self) -> str:
        return self.ubicacion.rsplit(":", 1)[0]


@dataclass(frozen=True)
class Fuente:
    """Cómo se liga el valor con la Bibliografía. `clave`: una clave firmada (`bibliography.SIGNED_KEYS`).
    `constante`: «módulo.CONSTANTE» con la cita que `bibliography.repo_references()` ya lista. `cita`: el texto literal
    que liga ESTE valor con esa fuente."""

    clave: Optional[str] = None
    constante: Optional[str] = None
    cita: Optional[Cita] = None


@dataclass(frozen=True)
class Evidencia:
    campo: str
    superficie: str
    etiqueta: str                       # rótulo con el que la UI muestra el valor
    mostrado_en: str                    # archivo:línea donde la UI lo dibuja
    produce: Optional[str]              # módulo.función que calcula o entrega el valor
    origen: Optional[str]               # archivo:línea de esa función o fórmula
    procedencia: Optional[str]          # nombre del enum Provenance, "variable" (la del UPS en ejecución) o None
    procedencia_cita: Optional[Cita] = None
    regla: Optional[Cita] = None
    supuestos: Optional[Cita] = None
    no_modelado: Optional[Cita] = None
    fuente: Optional[Fuente] = None


ENTRIES: Tuple[Evidencia, ...] = ()

REGISTRY: Dict[str, Evidencia] = {e.campo: e for e in ENTRIES}


def get_evidence(campo: str) -> Optional[Evidencia]:
    return REGISTRY.get(campo)


def fields(superficie: Optional[str] = None) -> Tuple[str, ...]:
    return tuple(c for c, e in REGISTRY.items() if superficie is None or e.superficie == superficie)
