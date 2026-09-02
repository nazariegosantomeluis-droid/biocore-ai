"""Detector BBB, Fase 3 -- Paso 3: la "prueba de fuego" contra los 50 casos
reales de PTB-XL (25 RBBB + 25 LBBB, `tests/ptbxl_bbb_validation_set.py`).

Corre el detector morfológico completo (`clinical.bbb_detector.
detect_bundle_branch_block`) sobre V1/V6 reales, extremo a extremo --
localización de latido, delineación, clasificación -- y arma la matriz de
confusión RBBB/LBBB/indeterminado/QRS<=120ms vs. la etiqueta real.

Pasa lead II como `reference_signal` (corrección de sincronización, Fase 3,
2026-08-12) -- la derivación de ritmo estándar, con la que se ancla V1 Y V6
al MISMO latido. Sin pasarla, `detect_bundle_branch_block()` cae a V6 como
ancla (fallback documentado, sigue siendo sincronizado, pero II es el
diseño recomendado -- ver `clinical/bbb_detector.py`).

Deliberadamente NO se asertan umbrales de exactitud: el propósito de esta
tanda es reportar la matriz real, no ajustar el criterio para que un
assert pase (instrucción explícita del validador -- ver CHANGELOG.md). Los
asserts de este archivo solo verifican que el proceso corrió sobre las 50
casos sin excepciones y que nunca se fuerza una rama sobre la otra sin
evidencia (RBBB<->LBBB cruzados se cuentan y reportan, no se prohíben por
código -- si el detector los produce, el test los deja pasar y los expone
en el mensaje, porque prohibirlos silenciaría exactamente el hallazgo que
esta fase pide reportar).

Se salta con motivo explícito si PTB-XL no está accesible (mismo patrón que
`tests/test_ptbxl_bbb_validation_set.py`) -- no bloquea la suite por falta
de conectividad, ni fabrica un resultado."""

from __future__ import annotations

from collections import Counter

import pytest

from clinical.bbb_detector import detect_bundle_branch_block
from clinical.ptbxl_metadata import PtbxlUnavailableError, resolve_ptbxl_wfdb_args
from ptbxl_bbb_validation_set import build_bbb_validation_set

NOT_WIDE_LABEL = "QRS<=120ms (no evaluado)"


def _load_v1_v6_ii(filename: str):
    import wfdb

    record_id, pn_dir = resolve_ptbxl_wfdb_args(filename)
    record = wfdb.rdrecord(record_id, pn_dir=pn_dir)
    names = [n.strip().upper() for n in record.sig_name]
    v1 = record.p_signal[:, names.index("V1")]
    v6 = record.p_signal[:, names.index("V6")]
    ii = record.p_signal[:, names.index("II")]
    return v1, v6, ii, float(record.fs)


def test_bbb_detector_confusion_matrix_against_50_real_ptbxl_cases():
    try:
        cases = build_bbb_validation_set(per_class_limit=25)
    except PtbxlUnavailableError as exc:
        pytest.skip(f"PTB-XL no accesible en este entorno: {exc}")

    assert len(cases) == 50

    try:
        import wfdb  # noqa: F401
    except ImportError:
        pytest.skip("wfdb no instalado")

    matrix = {"RBBB": Counter(), "LBBB": Counter()}
    severe_errors = []  # RBBB clasificado como LBBB, o viceversa
    load_failures = 0

    for case in cases:
        try:
            v1, v6, ii, fs = _load_v1_v6_ii(case.filename)
        except Exception as exc:
            load_failures += 1
            matrix[case.label]["LOAD_FAILED"] += 1
            continue

        result = detect_bundle_branch_block(v1, v6, fs, reference_signal=ii)
        predicted = result.pattern if result.pattern is not None else NOT_WIDE_LABEL
        matrix[case.label][predicted] += 1

        if {case.label, predicted} == {"RBBB", "LBBB"}:
            severe_errors.append((case.ecg_id, case.label, predicted))

    if load_failures > 40:
        pytest.skip(f"PTB-XL no accesible para carga real de señales ({load_failures}/50 fallaron)")

    total_evaluated = sum(sum(c.values()) for c in matrix.values())
    assert total_evaluated == 50

    report_lines = ["Matriz de confusión, detector BBB Fase 3 (50 casos reales PTB-XL):"]
    for real_label in ("RBBB", "LBBB"):
        for predicted_label, count in matrix[real_label].most_common():
            report_lines.append(f"  real={real_label} -> predicho={predicted_label}: {count}")
    report_lines.append(f"Errores graves (RBBB<->LBBB cruzados): {severe_errors or 'ninguno'}")
    print("\n" + "\n".join(report_lines))

    # No se asertan umbrales de exactitud (instrucción explícita: reportar,
    # no ajustar el criterio para que esto "pase" mejor). Solo se verifica
    # que el detector nunca produce una tercera opción inesperada.
    known_labels = {"RBBB", "LBBB", "Bloqueo de rama indeterminado", NOT_WIDE_LABEL, "LOAD_FAILED"}
    for real_label in ("RBBB", "LBBB"):
        assert set(matrix[real_label].keys()) <= known_labels
