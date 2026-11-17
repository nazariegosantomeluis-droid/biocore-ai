"""Residuos del PR #8 (2026-11-17, Art. I): «Validado por fuente» solo con una fuente de la Bibliografía.

Lee los textos de ayuda de Biomarcadores y la firma del laboratorio de HRV; la última prueba recorre con AppTest
el texto visible del laboratorio de HRV (las dos fuentes) y los motivos con que la RSA declina.
"""

import re
from pathlib import Path

import numpy as np
from streamlit.testing.v1 import AppTest

from app.main import _BIOMARKER_HELP, _HRV_VALIDATION_DETAIL
from app.supermodules.bibliography import OEHLER_2014, SIGNED_KEYS
from app.utils.design_system import BADGES
from src.signals.ecg.rsa import RSA_CITATION, detect_rsa
from test_fase1_t2_pulido import MAIN, visible_texts

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


def test_no_help_says_unverified_citation():
    """Una cita que no se pudo verificar no se muestra «a medias»: o entra a la Bibliografía con su clave, o se quita."""
    offenders = [name for name, text in _BIOMARKER_HELP.items() if "cita sin verificar" in text]
    offenders += [str(p) for p in Path("app").rglob("*.py") if "cita sin verificar" in p.read_text(encoding="utf-8")]
    assert offenders == [], f"«cita sin verificar» sigue en: {offenders}"


def test_no_visible_text_of_the_hrv_lab_attributes_anything_to_the_task_force():
    """A [TF1996] no se le atribuye ninguna afirmación: solo vive en la Bibliografía, con su nota."""
    at = AppTest.from_file(MAIN, default_timeout=240)
    at.session_state["biocore_start_page"] = "hrv"
    at.run()
    assert at.exception == [], at.exception
    texts = visible_texts(at)
    def source():
        return next(r for r in at.sidebar.radio if r.label == "Origen de la HRV")

    for option in list(source().options):
        source().set_value(option).run()
        assert at.exception == [], (option, at.exception)
        texts.extend(visible_texts(at))
    # Los motivos con que la RSA declina (también se muestran): registro corto y respiración fuera de la banda HF.
    peaks = np.arange(0.0, 30.0, 0.8)
    t = np.arange(0.0, 30.0, 0.04)
    texts.append(detect_rsa(peaks, np.sin(2 * np.pi * 0.25 * t), 25.0).reason or "")
    peaks = np.arange(0.0, 120.0, 0.8)
    t = np.arange(0.0, 120.0, 0.04)
    texts.append(detect_rsa(peaks, np.sin(2 * np.pi * 0.08 * t), 25.0).reason or "")
    texts.append(RSA_CITATION)
    offenders = [x for x in texts if "Task Force" in x or "TF1996" in x]
    assert offenders == [], f"texto visible del laboratorio de HRV atribuido a la Task Force: {offenders}"
    assert "Criterio BIOCORE (HEURISTIC)" in texts[-3] and "[SG2017]" in texts[-2] and "[SG2017]" in RSA_CITATION
