"""Residuos del PR #8 (2026-11-17, Art. I): «Validado por fuente» solo con una fuente de la Bibliografía.

Sin hardware ni AppTest: lee los textos de ayuda de Biomarcadores y la firma del laboratorio de HRV.
"""

import re
from pathlib import Path

from app.main import _BIOMARKER_HELP, _HRV_VALIDATION_DETAIL
from app.supermodules.bibliography import OEHLER_2014, SIGNED_KEYS
from app.utils.design_system import BADGES

KEY = re.compile(r"\[([A-Za-z0-9]+)\]")
BIBLIOGRAPHY_KEYS = set(SIGNED_KEYS) | {OEHLER_2014.key}


def _validated_without_key(helps):
    validated = BADGES.tag(BADGES.CLINICAL)
    offenders = []
    for name, help_text in helps.items():
        for segment in help_text.split(" · "):
            if validated not in segment:
                continue
            keys = set(KEY.findall(segment)) & BIBLIOGRAPHY_KEYS
            if not keys - {"TF1996"}:
                offenders.append((name, segment[:120]))
    return offenders


def test_the_guard_rejects_what_it_should():
    tag = BADGES.tag(BADGES.CLINICAL)
    assert _validated_without_key({"x": f"{tag} SDNN 15-150 ms: dictamen interno"})
    assert _validated_without_key({"x": f"{tag} bandas [TF1996]"})
    assert _validated_without_key({"x": f"{tag} sin clave · [SG2017] en otro segmento"})
    assert not _validated_without_key({"x": f"{tag} bandas [SG2017]"})


def test_every_validated_segment_of_the_biomarker_help_cites_a_bibliography_key():
    offenders = _validated_without_key(_BIOMARKER_HELP)
    assert offenders == [], (
        "«Validado por fuente» sin una clave de la Bibliografía (que no sea [TF1996], a la que no se le atribuye "
        f"ninguna afirmación): {offenders}"
    )


def test_no_app_file_mentions_the_golden_markers_dictum():
    offenders = [str(p) for p in Path("app").rglob("*.py") if "marcadores dorados" in p.read_text(encoding="utf-8")]
    assert offenders == [], f"«marcadores dorados» (dictamen interno, sin fuente publicada) sigue en: {offenders}"


def test_hrv_signature_cites_sg2017_and_not_the_task_force():
    assert "[SG2017]" in _HRV_VALIDATION_DETAIL, "la firma del laboratorio de HRV debe citar [SG2017]"
    assert "Task Force" not in _HRV_VALIDATION_DETAIL, "la firma del laboratorio de HRV no debe atribuir nada a la Task Force"
