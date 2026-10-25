"""Tanda 2B (2026-10-24): el reporte genera un PDF de verdad, con fpdf2.

Antes, en main, `export_lab_report()` nunca producía PDF: con PyFPDF 1.7.2
moría en `Undefined font: dejavu B` (y tras ese, la cursiva del pie nunca
registrada). El `except` general lo tragaba y devolvía el HTML. Además
`copyfile` no estaba importado: las figuras no se copiaban junto al reporte.

Aquí se prueba el arreglo y que el cambio PyFPDF -> fpdf2 no rompió a ningún
otro consumidor del módulo `fpdf` en main.
"""
import os
import runpy
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_fpdf_module_is_fpdf2_not_pyfpdf():
    import fpdf

    major = int(fpdf.__version__.split(".")[0])
    assert major >= 2, f"`fpdf` resuelve a PyFPDF {fpdf.__version__}, no a fpdf2"
    from fpdf import XPos  # noqa: F401  (solo existe en fpdf2)


def test_requirements_declare_fpdf2_not_pyfpdf():
    for name in ("requirements.txt", "requirements_extra.txt"):
        pkgs = [ln.split("#")[0].strip() for ln in (ROOT / name).read_text(encoding="utf-8").splitlines()]
        assert any(p.startswith("fpdf2") for p in pkgs), name
        assert not any(p == "fpdf" or p.startswith(("fpdf=", "fpdf>", "fpdf<", "PyFPDF")) for p in pkgs), name


def _real_png(path):
    from app.reporting import _save_signal_plot

    _save_signal_plot(str(path), [0, 1, 2, 3], [0, 1, 0, -1], "Señal")
    assert path.read_bytes()[:4] == b"\x89PNG"


def test_pdf_is_real_and_embeds_the_figure_even_after_its_tmpdir_is_gone(tmp_path):
    """El flujo de EEG Neuro Lab: la figura vive en un tmpdir que se borra
    justo después de exportar. Debe quedar copiada y dentro del PDF."""
    from app.reporting import export_lab_report

    src = tmp_path / "tmp_figuras"
    src.mkdir()
    _real_png(src / "psd.png")
    out = tmp_path / "out"

    result = export_lab_report("EEG Neuro Lab", {"fs": 250}, out_dir=str(out),
                               image_paths=[("PSD", str(src / "psd.png"))])
    shutil.rmtree(src)

    assert result.endswith(".pdf"), f"cayó al HTML de respaldo: {result}"
    data = Path(result).read_bytes()
    assert data[:4] == b"%PDF"
    assert b"/Subtype /Image" in data, "el PDF no lleva la figura"
    assert (out / "psd.png").read_bytes()[:4] == b"\x89PNG"
    assert list(out.glob("*.html")), "el HTML se sigue escribiendo junto al PDF"


def test_pdf_carries_the_same_honesty_as_the_screen(tmp_path, monkeypatch):
    """Jerarquía de validación, badge de procedencia, clasificación, cita,
    motivo de "no disponible" y aviso educativo llegan al PDF. Se espía el
    texto que se escribe (el PDF guarda glifos, no texto legible)."""
    import fpdf

    from app.reporting import EDUCATIONAL_NOTICE, export_lab_report
    from app.utils.design_system import BADGES, GRAMMAR_NEUTRAL_STATE, resolve_metric_card
    from src.signals.eeg.eeg_analyzer import BAR_CITATION
    from src.signals.eeg.spectral_model import CHI_CITATION, classify_chi

    written = []
    for name in ("cell", "multi_cell"):
        original = getattr(fpdf.FPDF, name)

        def spy(self, *args, _original=original, **kwargs):
            text = kwargs.get("text", kwargs.get("txt", args[2] if len(args) > 2 else ""))
            written.append(str(text))
            return _original(self, *args, **kwargs)

        monkeypatch.setattr(fpdf.FPDF, name, spy)

    cards = [
        resolve_metric_card("χ", "0.80", classification=classify_chi(0.8),
                            grammar=GRAMMAR_NEUTRAL_STATE, citation=CHI_CITATION),
        resolve_metric_card("BAR", "2.30", provenance=BADGES.CLINICAL,
                            grammar=GRAMMAR_NEUTRAL_STATE, citation=BAR_CITATION),
        resolve_metric_card("PLV", None, unavailable_reason="faltan 4.2 s de registro"),
    ]
    detail = "Combinador heurístico -- no validado"
    result = export_lab_report("EEG Neuro Lab", {"fs": 250}, out_dir=str(tmp_path),
                               honesty_cards=cards, validation="HEURISTIC", validation_detail=detail)

    assert result.endswith(".pdf"), f"cayó al HTML de respaldo: {result}"
    text = "\n".join(written)
    assert detail in text
    assert EDUCATIONAL_NOTICE in text
    assert "Honestidad de procedencia" in text
    assert "χ: 0.80" in text and "excitación cortical" in text and CHI_CITATION in text
    assert BADGES.label(BADGES.CLINICAL) in text and BAR_CITATION in text
    assert "PLV: no disponible — faltan 4.2 s de registro" in text


def test_html_declares_educational_notice_and_recommends_fpdf2(tmp_path):
    from app.reporting import EDUCATIONAL_NOTICE, export_lab_report

    export_lab_report("Lab", {"fs": 250}, out_dir=str(tmp_path))
    html = next(tmp_path.glob("*.html")).read_text(encoding="utf-8")
    assert EDUCATIONAL_NOTICE in html
    assert "pip install plotly kaleido fpdf2" in html


def test_rural_pdf_report_survives_the_swap(tmp_path):
    from src.rural_health.offline_support import generate_pdf_report

    path = generate_pdf_report({"name": "Paciente simulado", "age": 40},
                               "Resumen con acentos: ñ, á.", path=str(tmp_path / "r" / "rural.pdf"))
    assert Path(path).read_bytes()[:4] == b"%PDF"


@pytest.mark.parametrize("script", [
    "docs/validation/ecg_hr_detector_bank/build_decision_sheet.py",
    "docs/validation/ecg_hr_detector_bank/round2/build_decision_sheet2.py",
    "docs/validation/ecg_hr_detector_bank/round3/build_decision_sheet3.py",
])
def test_docs_decision_sheets_still_regenerate_with_fpdf2(script, tmp_path):
    """Los PDF versionados de esas hojas los hizo PyFPDF 1.7.2. Se corre una
    copia en tmp_path (escriben junto a sí mismas: no se pisan los del repo)."""
    copy = tmp_path / Path(script).name
    shutil.copy(ROOT / script, copy)
    runpy.run_path(str(copy), run_name="__main__")
    pdfs = [p for p in os.listdir(tmp_path) if p.endswith(".pdf")]
    assert len(pdfs) == 1 and (tmp_path / pdfs[0]).read_bytes()[:4] == b"%PDF"
