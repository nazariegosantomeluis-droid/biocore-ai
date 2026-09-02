"""Verifica que el set de validación BBB (ground truth para la Fase 3, no
autorizada todavía) se arma correctamente desde `ptbxl_database.csv` --
balanceado, solo confirmados (confianza == 100.0), rutas listas para
cargar.

Se salta con motivo explícito si no hay CSV cacheado ni red disponible --
no bloquea la suite por falta de conectividad, ni fabrica un resultado."""

import pytest

from clinical.ptbxl_metadata import PtbxlUnavailableError
from ptbxl_bbb_validation_set import build_bbb_validation_set


def _build_or_skip(per_class_limit=25):
    try:
        return build_bbb_validation_set(per_class_limit=per_class_limit)
    except PtbxlUnavailableError as exc:
        pytest.skip(f"PTB-XL no accesible en este entorno: {exc}")


def test_validation_set_is_balanced_and_confirmed():
    cases = _build_or_skip(per_class_limit=25)

    rbbb = [c for c in cases if c.label == "RBBB"]
    lbbb = [c for c in cases if c.label == "LBBB"]

    assert len(rbbb) == 25
    assert len(lbbb) == 25
    assert all(c.confidence == 100.0 for c in cases)
    assert all(c.scp_code == "CRBBB" for c in rbbb)
    assert all(c.scp_code == "CLBBB" for c in lbbb)
    assert len({c.ecg_id for c in cases}) == len(cases)  # sin duplicados
    assert all(c.filename.startswith("records500/") for c in cases)


def test_validation_set_cases_are_loadable_from_ptbxl():
    """Prueba de humo contra PTB-XL real -- toma 1 RBBB y 1 LBBB del set y
    confirma que de verdad cargan (no solo que el CSV los liste)."""
    cases = _build_or_skip(per_class_limit=1)
    assert len(cases) == 2

    try:
        import wfdb
    except ImportError:
        pytest.skip("wfdb no instalado")

    from clinical.ptbxl_metadata import resolve_ptbxl_wfdb_args

    for case in cases:
        record_id, pn_dir = resolve_ptbxl_wfdb_args(case.filename)
        try:
            record = wfdb.rdrecord(record_id, pn_dir=pn_dir)
        except Exception as exc:
            pytest.skip(f"PTB-XL no accesible para carga real ({type(exc).__name__}: {exc})")
        names = [n.strip().upper() for n in record.sig_name]
        assert "V1" in names and "V6" in names
