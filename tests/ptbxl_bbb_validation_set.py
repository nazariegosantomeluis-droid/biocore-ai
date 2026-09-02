"""Set de validación BBB para el Detector de Bloqueo de Rama, Fase 3 (NO
autorizada todavía) -- ground truth de registros PTB-XL reales, CONFIRMADOS
(`scp_codes` con confianza EXACTA 100.0) como CRBBB (RBBB completo) o CLBBB
(LBBB completo).

Instrumento de validación, deliberadamente NO parte de la UI viva --
separado de `app/main.py::_ecg_get_ptbxl_records()` (el catálogo del ECG
Lab, pensado para navegación variada: 2 normales + 1 hallazgo de cada
tipo) y de `app/supermodules/ecg_monitor/pages.py::get_ptbxl_records()`
(mismo catálogo, en el supermódulo huérfano). Los tres comparten el acceso
al CSV (`clinical.ptbxl_metadata`) pero cada uno arma su propia selección
de registros para su propio propósito -- no se mezclan en un mismo módulo.

Solo bloqueos COMPLETOS (CRBBB/CLBBB) en esta tanda -- IRBBB/ILBBB
(incompletos) quedan fuera, como categoría aparte a considerar en una
tanda posterior: la Fase 3 empieza por los casos confirmados y completos,
no los ambiguos.

Este set es el ground truth contra el que la Fase 3 medirá el detector
morfológico (todavía no construido) -- no se construye ningún detector
aquí, solo los casos de validación con su etiqueta y ruta de carga."""

from __future__ import annotations

import ast
import dataclasses
from typing import List, Literal

from clinical.ptbxl_metadata import load_ptbxl_database

BbbLabel = Literal["RBBB", "LBBB"]

_SCP_CODE_BY_LABEL = {"RBBB": "CRBBB", "LBBB": "CLBBB"}
"""CRBBB/CLBBB = bloqueo de rama COMPLETO (derecho/izquierdo) en la
nomenclatura SCP-ECG de PTB-XL. IRBBB/ILBBB (incompletos) quedan fuera de
este set a propósito -- ver docstring del módulo."""


@dataclasses.dataclass(frozen=True)
class BbbValidationCase:
    """Un caso de ground truth: registro real de PTB-XL, confirmado."""

    ecg_id: int
    label: BbbLabel
    scp_code: str
    confidence: float
    filename: str  # filename_hr real -- listo para clinical.ptbxl_metadata.resolve_ptbxl_wfdb_args()


def build_bbb_validation_set(per_class_limit: int = 25) -> List[BbbValidationCase]:
    """Filtra `ptbxl_database.csv` por `scp_codes` con CRBBB/CLBBB en
    confianza EXACTA 100.0 -- solo confirmados, nunca dudosos (un valor
    menor a 100.0 significa que el diagnóstico no quedó completamente
    asentado en la revisión original de PTB-XL; se excluye sin excepción).

    Devuelve hasta `per_class_limit` casos de cada clase, tomados en el
    orden en que aparecen en el CSV (no aleatorizado ni curado a mano) --
    hay 541 CRBBB y 536 CLBBB confirmados en el dataset completo (conteo
    verificado en el diagnóstico previo a esta tanda), de sobra para un
    set balanceado sin necesidad de usarlos todos.

    Puede lanzar `PtbxlUnavailableError` (de `clinical.ptbxl_metadata`) si
    no hay CSV cacheado ni red -- no se captura aquí, el llamador decide
    (los tests de este set se saltan con motivo explícito si esto ocurre)."""
    df = load_ptbxl_database()

    cases: List[BbbValidationCase] = []
    for label, scp_code in _SCP_CODE_BY_LABEL.items():
        count_this_label = 0
        for _, row in df.iterrows():
            if count_this_label >= per_class_limit:
                break
            try:
                codes = ast.literal_eval(row["scp_codes"])
            except (ValueError, SyntaxError):
                continue
            confidence = codes.get(scp_code)
            if confidence != 100.0:
                continue
            cases.append(
                BbbValidationCase(
                    ecg_id=int(row["ecg_id"]),
                    label=label,  # type: ignore[arg-type]
                    scp_code=scp_code,
                    confidence=float(confidence),
                    filename=row["filename_hr"],
                )
            )
            count_this_label += 1

    return cases
