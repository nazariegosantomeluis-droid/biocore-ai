"""Regresión: export_lab_report() debe copiar a out_dir las imágenes que referencia.

Antes `copyfile` no estaba importado; el NameError lo tragaba un `except` y el
HTML exportado apuntaba a imágenes inexistentes (fallo silencioso).
"""
import os

from app.reporting import export_lab_report


def test_external_images_are_copied_next_to_report(tmp_path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    img = src_dir / "senal.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    out_dir = tmp_path / "out"

    result = export_lab_report("Lab de prueba", {"fs": 250}, out_dir=str(out_dir),
                               image_paths=[("Señal", str(img))])

    assert os.path.exists(result)
    assert (out_dir / "senal.png").read_bytes() == img.read_bytes()


def test_image_already_inside_out_dir_does_not_crash(tmp_path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    img = out_dir / "ya_aqui.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    export_lab_report("Lab", {"fs": 250}, out_dir=str(out_dir), image_paths=[("x", str(img))])
    assert img.exists()


def test_pdf_is_generated_when_fpdf_available(tmp_path):
    """Antes el pie pedía DejaVu cursiva sin registrarla y `multi_cell` dejaba el
    cursor a la derecha: el PDF fallaba SIEMPRE y el `except` lo ocultaba."""
    import pytest
    pytest.importorskip("fpdf")
    result = export_lab_report(
        "Lab PDF", {"fs": 250, "HR": 72}, notes="nota con acentos: ñ, á — ✓",
        findings={"ritmo": "sinusal", "eje": "normal"}, out_dir=str(tmp_path),
    )
    assert result.endswith(".pdf")
    assert (tmp_path / os.path.basename(result)).read_bytes()[:4] == b"%PDF"
