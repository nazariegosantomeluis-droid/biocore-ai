"""Cierre del pulido profesional (2026-11-16): coherencia con la teoría firmada (`docs/contenido/teoria_citada.md`).

1. [AR2025]: autores según PubMed (Porter R, Graham DD; PMID 29262235), en la Bibliografía y en el documento firmado.
2. Ninguna página muestra «[Sin fuente]» (el recorrido de TODAS las páginas y fuentes está en test_fase1_t2_pulido.py);
   el material retirado sigue en el código, sin montar, con la fuente que le haría falta.
3. 12 Derivaciones: la introducción y la tabla de la derecha son los temas 4 y 5 firmados; ninguna derivación suelta
   rotulada por pared.
4. Casos clínicos del Monitoreo a ≥ 500 muestras/s [K2007], con el mismo contenido clínico.
"""

import ast
import re
from pathlib import Path

import numpy as np
import pytest
from streamlit.testing.v1 import AppTest

MAIN = str(Path("app/main.py").resolve())
SIGNED_DOC = Path("docs/contenido/teoria_citada.md")


def _open(url):
    at = AppTest.from_file(MAIN, default_timeout=240)
    at.session_state["biocore_start_page"] = url
    at.run()
    assert at.exception == [], (url, at.exception)
    return at


def _all_text(at):
    from test_fase1_t2_pulido import visible_texts

    return " ".join(visible_texts(at))


# ── 1 ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_ar2025_authors_follow_pubmed_in_the_bibliography_and_the_signed_document():
    from app.supermodules.bibliography import SIGNED

    ref = next(r for r in SIGNED if r.key == "AR2025")
    assert ref.text.startswith("Porter R, Graham DD. Abnormal Respirations.") and "PMID 29262235" in ref.text
    assert "NBK470309" in ref.text and "Whited" not in ref.text
    line = next(l for l in SIGNED_DOC.read_text(encoding="utf-8").splitlines() if "**[AR2025]**" in l)
    assert "Porter R, Graham DD" in line and "PMID 29262235" in line
    assert "Autores corregidos según PubMed el 16 de noviembre de 2026" in line
    assert line.index("Porter R") < line.index("Whited")                     # «Whited» solo en la nota de corrección


# ── 2 ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("url", ["ecg", "biomarcadores"])
def test_no_page_shows_sin_fuente_where_it_used_to(url):
    text = _all_text(_open(url))
    assert "[Sin fuente]" not in text and "Fantasmas" not in text
    for retired in ("Anatomía interactiva", "Línea de tiempo fisiológica", "Qué cambiaría si",
                    "Fisiología dinámica", "Nodo SA", "PR (ms)", "QT (ms)"):
        assert retired not in text, retired


def test_retired_material_is_kept_unmounted_with_the_source_it_would_need():
    src = Path(MAIN).read_text(encoding="utf-8")
    tree = ast.parse(src)
    defs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    for name, needs in (("_ecg_monitor_unsourced_material", ("Guyton and Hall", "Surawicz 2009")),
                        ("_biomarkers_ghost_history", ("presión arterial", "PPG-PTT"))):
        assert name in defs, name
        doc = ast.get_docstring(defs[name])
        assert "Fuente que haría falta" in doc and all(n in doc for n in needs), name
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "id", None) == name]
        assert calls == [], f"{name} no debe montarse"
    # ninguna llamada viva a la etiqueta «[Sin fuente]» fuera de las dos funciones sin montar
    live = src
    for name in ("_ecg_monitor_unsourced_material", "_biomarkers_ghost_history"):
        node = defs[name]
        lines = src.splitlines()
        live = live.replace("\n".join(lines[node.lineno - 1:node.end_lineno]), "")
    live_code = "\n".join(l for l in live.splitlines() if not l.lstrip().startswith("#"))
    assert "BADGES.tag(BADGES.GHOST)" not in live_code and "[Sin fuente]" not in live_code


# ── 3 ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
WALL_LABEL = re.compile(r"cara (anterior|inferior|lateral|posterior)|\((Anterior|Inferior|Lateral)\)|"
                        r"Territorios Vasculares", re.IGNORECASE)


def test_twelve_lead_intro_and_table_are_the_signed_topics_4_and_5():
    from app.supermodules.learn_theory import ISCHEMIA_WARNING, SIGNED_ISCHEMIA, SIGNED_TWELVE_LEADS

    at = _open("ecg")
    markdown = [m.value for m in at.markdown]
    intro = markdown.index("##### 🎓 ¿Qué es un ECG de 12 derivaciones?")
    assert markdown[intro + 1] == SIGNED_TWELVE_LEADS.idea and markdown[intro + 2] == SIGNED_ISCHEMIA.idea
    assert f"#### {SIGNED_ISCHEMIA.title}" in markdown and ISCHEMIA_WARNING in markdown
    text = " ".join(markdown) + " " + " ".join(c.value for c in at.caption)
    assert not WALL_LABEL.search(text), WALL_LABEL.search(text)
    doc = SIGNED_DOC.read_text(encoding="utf-8")
    assert SIGNED_TWELVE_LEADS.idea.replace('\\"', '"') in doc and SIGNED_ISCHEMIA.idea in doc


# ── 4 ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_clinical_cases_are_sampled_at_500_hz_with_the_same_clinical_content(monkeypatch):
    import src.clinical.case_database as cdb

    db = cdb.build_complete_case_database()
    assert cdb.CASE_FS >= 500 and db.count_cases() == 61
    for case in db.cases.values():
        assert case.fs >= 500, case.case_id
        assert len(case.ecg_signal) == int(case.fs * case.duration_sec), case.case_id

    monkeypatch.setattr(cdb, "CASE_FS", 250)
    old = cdb.build_complete_case_database()
    assert sorted(db.cases) == sorted(old.cases)
    for cid, case in db.cases.items():
        before = old.cases[cid]
        assert before.fs == 250 and case.duration_sec == before.duration_sec
        assert case.primary_diagnosis == before.primary_diagnosis and case.difficulty == before.difficulty
        assert case.lead_type == before.lead_type and set(vars(case)) == set(vars(before))


def test_a_500_hz_sinus_case_still_measures_its_declared_rate():
    import src.clinical.case_database as cdb
    from clinical.ecg_analyzer import ECGAnalyzer

    np.random.seed(0)
    case = cdb.generate_nsr_case("p", 50, "M")
    assert case.fs == 500
    peaks = ECGAnalyzer(fs=case.fs).detect_r_peaks_tkeo(case.ecg_signal)
    rr = np.diff(np.asarray(peaks)) / case.fs
    assert 60.0 / np.median(rr) == pytest.approx(75, abs=1.5)                # el generador pide 75 lpm
