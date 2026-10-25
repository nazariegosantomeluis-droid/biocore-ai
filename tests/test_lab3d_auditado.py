"""
Laboratorio 3D traído del aporte externo AUDITADO (2026-10-22): solo las
piezas aprobadas, cada una con su rótulo de honestidad, y nada de lo
rechazado. La validación del pulmón contra TotalSegmentator vive en
`tests/test_reconstruction3d_validation.py`.

Adaptados de los tests del aporte externo: atribución de mallas, Kors frente
a Frank, lector CSV, esfera, ida y vuelta STL/OBJ/PLY, NIfTI, DICOM.
"""

from __future__ import annotations

import inspect
import io
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]


# --- Mallas de referencia (estáticas) ----------------------------------------

def test_body_meshes_come_from_the_real_ct_with_attribution():
    from visualization.anatomy3d import load_body

    body = load_body()
    assert body.source["license"] == "CC BY 4.0" and "10.5281/zenodo.10047292" in body.source["doi"]
    for key in ("heart", "lung_left", "lung_right", "brain", "liver", "spinal_cord", "trachea"):
        mesh = body[key]
        assert mesh.faces.max() < mesh.vertices.shape[0] and mesh.vertices.dtype == np.float32
    assert 350 < body["heart"].volume_ml < 1100
    assert 1000 < body["brain"].volume_ml < 1800


def test_reference_viewer_is_static_tissue_colored_and_organ_systems_only():
    from visualization import anatomy3d as A3

    assert "part_colors" not in inspect.signature(A3.body_figure).parameters, "sin coloreado por estado"
    assert not hasattr(A3, "TWIN_ORGAN_PARTS")
    fig = A3.body_figure(systems=("circulatory", "respiratory", "skeleton", "muscular", "skin"))
    body = A3.load_body()
    drawn = {t.name for t in fig.data}
    shown_systems = {m.system for m in body.meshes.values() if m.label in drawn}
    assert shown_systems == {"circulatory", "respiratory"}, "esqueleto, músculos y piel quedan fuera"
    for trace in fig.data:
        key = next(m.key for m in body.meshes.values() if m.label == trace.name)
        assert trace.color == A3.TISSUE_COLOR[key]
    assert "no reactiva" in A3.REFERENCE_ANATOMY_NOTE and "s1397" in A3.REFERENCE_ANATOMY_NOTE


def test_reference_head_shows_standard_1020_positions_without_any_eeg_map():
    """Sin valores, la cabeza de referencia sigue sin mapa. (El spline existe desde
    la Tanda 2D, con su propio test en tests/test_tanda2d_eeg_map_cohort.py.)"""
    from visualization import anatomy3d as A3

    fig = A3.head_figure()
    electrodes = next(t for t in fig.data if t.name == "Electrodos 10-20")
    assert len(electrodes.x) >= 19
    assert not any(getattr(t, "intensity", None) is not None for t in fig.data)


# --- VCG (Kors frente a Frank, verificado en 1 paciente) ----------------------

def test_kors_vcg_matches_the_real_frank_leads_of_the_same_patient():
    from src.signals.ecg.vcg import KORS_MATRIX, ptb_reference

    assert KORS_MATRIX.shape == (3, 8)
    ref = ptb_reference()
    cx, cy, cz = ref["corr"]
    assert (round(cx, 3), round(cy, 3), round(cz, 3)) == (0.982, 0.951, 0.728)
    real, kors = ref["real"].measures, ref["kors"].measures
    assert abs(real.qrs_duration_ms - kors.qrs_duration_ms) < 15
    assert abs(real.qrs_t_angle_deg - kors.qrs_t_angle_deg) < 20


def test_mean_vector_azimuth_is_not_shown_because_it_fails_on_the_reference():
    """Auditoría: el acimut del vector QRS medio difiere ~74° del real en el
    caso de referencia. No se muestra como número y las flechas se rotulan."""
    from src.signals.ecg.vcg import ptb_reference
    from visualization.vcg3d import MEAN_VECTOR_NOTE, measures_table, vcg_figure

    ref = ptb_reference()
    real, kors = ref["real"].measures, ref["kors"].measures
    gap = abs((real.qrs_azimuth_deg - kors.qrs_azimuth_deg + 180) % 360 - 180)
    assert gap > 60, "si esto deja de fallar, se puede reconsiderar mostrarlo"
    table = measures_table(kors)
    assert not any("acimut" in v or "Vector QRS medio" in k for k, v in table.items())
    assert "74°" in MEAN_VECTOR_NOTE
    names = [t.name for t in vcg_figure(ref["kors"].beat, kors).data if t.name and "Vector medio" in t.name]
    assert names and all("no fiable" in n for n in names)


def test_vcg_csv_reader_derives_fs_from_a_time_column():
    import pandas as pd

    from src.signals.ecg.vcg import read_leads_csv, vcg_from_12_leads
    from src.signals.reference_recordings import ptb_s0010

    d = ptb_s0010()
    n = int(d["fs"] * 10)
    cols = {"tiempo_ms": np.arange(n) / d["fs"] * 1000.0}
    for lead in ("i", "ii", "v1", "v2", "v3", "v4", "v5", "v6"):
        cols[lead] = d["leads"][lead.upper()][:n]
    leads, fs, note = read_leads_csv(pd.DataFrame(cols).to_csv(index=False).encode())
    assert fs == pytest.approx(500.0, rel=1e-3) and "tiempo_ms" in note
    res = vcg_from_12_leads(leads, fs)
    assert res.n_beats >= 8 and 60 < res.heart_rate_bpm < 110


def test_reference_recordings_ship_only_audited_files():
    """PTB (Pieza 1) y CAP n16 (Tanda 2D, con el rótulo corregido). El resto de
    los registros del aporte no entró."""
    from src.signals import reference_recordings as R

    assert "ODC-By" in R.source_line("ptb_s0010") and "ODC-By" in R.source_line("cap_n16")
    assert sorted(p.name for p in (ROOT / "data" / "reference_signals").glob("*.npz")) == [
        "cap_n16.npz", "ptb_s0010.npz"]


# --- Motor TC/RM -> malla ------------------------------------------------------

def _sphere_mask(r=15, n=20):
    z, y, x = np.mgrid[-n:n + 1, -n:n + 1, -n:n + 1]
    return (x ** 2 + y ** 2 + z ** 2) <= r ** 2


def test_mesh_from_mask_measures_volume_and_exports_roundtrip():
    from src.imaging import volume3d as V

    aff = np.diag([1.5, 1.5, 1.5, 1.0])
    m = V.mesh_from_mask(_sphere_mask(), aff, target_faces=5000)
    expected = 4 / 3 * np.pi * (15 * 1.5) ** 3 / 1000
    assert m.volume_ml == pytest.approx(expected, rel=0.03)
    for name, writer in (("a.stl", V.to_stl), ("a.obj", V.to_obj), ("a.ply", V.to_ply)):
        v, f = V.read_mesh(name, writer(m.vertices, m.faces))
        assert f.shape == m.faces.shape
        assert V.mesh_stats(v, f)["volume_ml"] == pytest.approx(expected, rel=0.03), name
    with pytest.raises(V.VolumeError):
        V.mesh_from_mask(np.zeros((5, 5, 5), bool), aff)


def test_nifti_and_label_maps_are_read_in_ras():
    import nibabel as nib

    from src.imaging import volume3d as V

    lab = np.zeros((20, 20, 20), np.int16)
    lab[2:8, 2:8, 2:8] = 1
    lab[10:18, 10:18, 10:18] = 2
    vol = V.load_any([("seg.nii", nib.Nifti1Image(lab, np.diag([2.0, 2.0, 2.0, 1.0])).to_bytes())])
    assert vol.is_labels and V.label_values(vol) == [1, 2] and vol.spacing == (2.0, 2.0, 2.0)


def test_dicom_series_is_stacked_in_order():
    from pydicom.dataset import FileDataset, FileMetaDataset
    from pydicom.uid import ExplicitVRLittleEndian, generate_uid

    from src.imaging import volume3d as V

    files, series = [], generate_uid()
    for k in [3, 0, 4, 1, 2]:  # desordenados a propósito
        meta = FileMetaDataset()
        meta.TransferSyntaxUID = ExplicitVRLittleEndian
        meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
        meta.MediaStorageSOPInstanceUID = generate_uid()
        ds = FileDataset(None, {}, file_meta=meta, preamble=b"\0" * 128)
        ds.Modality, ds.SeriesInstanceUID = "CT", series
        ds.Rows = ds.Columns = 8
        ds.BitsAllocated, ds.BitsStored, ds.HighBit, ds.PixelRepresentation = 16, 16, 15, 1
        ds.SamplesPerPixel, ds.PhotometricInterpretation = 1, "MONOCHROME2"
        ds.PixelSpacing = [0.7, 0.7]
        ds.ImageOrientationPatient = [1, 0, 0, 0, 1, 0]
        ds.ImagePositionPatient = [0, 0, 2.5 * k]
        ds.RescaleSlope, ds.RescaleIntercept = 1, -1024
        ds.PixelData = (np.full((8, 8), 1024 + 100 * k, np.int16)).tobytes()
        buf = io.BytesIO()
        ds.save_as(buf, enforce_file_format=True)
        files.append((f"c{k}.dcm", buf.getvalue()))
    vol = V.load_any(files)
    assert vol.shape == (8, 8, 5) and vol.modality == "CT"
    assert [float(vol.data[0, 0, k]) for k in range(5)] == [0.0, 100.0, 200.0, 300.0, 400.0]
    assert vol.spacing == pytest.approx((0.7, 0.7, 2.5))


def test_simplification_never_opens_a_closed_mesh():
    """Medido en la auditoría: a 60 000 triángulos (calidad "Rápida") la
    simplificación abría el pulmón (1 arista, orientación mezclada). Ahora
    reintenta con menos reducción hasta que cierra, y lo dice."""
    from src.imaging import volume3d as V

    vol = V.load_nifti_bytes((ROOT / "data" / "samples" / "tc_torax_s1397_2mm.nii.gz").read_bytes())
    m = V.mesh_from_mask(V.preset_mask(vol, "lungs"), vol.affine, target_faces=60_000)
    q = V.mesh_quality(m.faces)
    assert q.watertight and q.winding_consistent
    assert any("se abría la malla" in n for n in m.notes)


def test_only_the_validated_lung_preset_is_offered():
    from src.imaging import volume3d as V

    assert list(V.CT_PRESETS) == ["lungs"]
    assert "1 sujeto" in V.LUNG_VALIDATION_NOTE and "TotalSegmentator" in V.LUNG_VALIDATION_NOTE
    with pytest.raises(KeyError):
        V.preset_mask(None, "bone")


# --- La página, con sus rótulos ------------------------------------------------

def _run_page():
    from streamlit.testing.v1 import AppTest

    def _script():
        from app.supermodules.model3d.pages import run
        run()

    at = AppTest.from_function(_script, default_timeout=300)
    at.run()
    assert not at.exception, at.exception
    return at


def _text(at) -> str:
    parts = [m.value for m in at.markdown] + [c.value for c in at.caption] + [i.value for i in at.info]
    return " ".join(parts)


def test_page_has_only_the_approved_tabs_and_declares_mixed_validation():
    at = _run_page()
    # EEG en 3D y Tu base de pacientes: aprobadas en la Tanda 2D (2026-10-24).
    assert [t.label for t in at.tabs] == [
        ":material/view_in_ar: Tu tomografía o resonancia", ":material/deployed_code: Ver un modelo 3D",
        ":material/ecg_heart: ECG en 3D", ":material/neurology: EEG en 3D",
        ":material/scatter_plot: Tu base de pacientes", ":material/accessibility_new: Anatomía de referencia"]
    text = _text(at)
    assert "Módulo mixto" in text and "no sirve para diagnosticar ni planear tratamientos" in text


def test_vcg_tab_says_verified_in_one_patient_not_validated():
    at = _run_page()
    info = " ".join(i.value for i in at.info)
    assert "Verificado en 1 paciente real (PTB s0010, derivaciones de Frank simultáneas)" in info
    assert "validado" not in info.lower()
    text = _text(at)
    assert "X 0.98, Y 0.95, Z 0.73" in text and "la Z es la más difícil" in text
    assert "dirección absoluta de los vectores medios no es fiable" in text
    assert "acimut" not in " ".join(str(t.value) for t in at.table)


def test_reference_anatomy_tab_declares_it_is_not_reactive():
    from visualization.anatomy3d import REFERENCE_ANATOMY_NOTE

    at = _run_page()
    assert REFERENCE_ANATOMY_NOTE in " ".join(i.value for i in at.info)


def test_sample_ct_builds_the_lung_mesh_with_a_real_closure_check_and_three_downloads():
    at = _run_page()
    next(b for b in at.button if b.key == "m3d_sample").click().run()
    next(b for b in at.button if b.key == "m3d_build").click().run()
    assert not at.exception, at.exception
    assert len(at.get("download_button")) == 3
    text = _text(at)
    assert "Malla cerrada ✓" in text and "verificado contra TotalSegmentator en 1 sujeto" in text
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Tipo detectado"] == "Tomografía" and "mL" in metrics["Volumen de la selección"]


def test_lab3d_is_in_the_navigation():
    import app.main as m

    assert m.HUBS["Laboratorio 3D"] == ["🧊 Crea tu modelo 3D"]


# --- Lo rechazado NO entró ------------------------------------------------------

def test_rejected_pieces_are_absent():
    # Código fuente, no carpetas: una caché `__pycache__` huérfana no es código traído.
    # Las calculadoras salieron de esta lista en la Tanda 2C (2026-10-24): entraron
    # auditadas, sin arte. Que no traigan `visualization.art` lo comprueba
    # tests/test_clinical_calculators.py. `src/ml` y `visualization/cohort3d.py`
    # salieron en la Tanda 2D: entraron con la guardia anti-fuga por ID y sin el
    # cuerpo NEWS2 (tests/test_tanda2d_eeg_map_cohort.py).
    for path in ("visualization/art", "app/static/anatomy"):
        assert not [f for f in (ROOT / path).rglob("*") if f.is_file() and f.suffix != ".pyc"], path
    twin = (ROOT / "app/supermodules/twin_shell/pages.py").read_text(encoding="utf-8")
    # El 3D heurístico del aporte (`render_body_3d`) no entra; el cuerpo 3D del gemelo
    # vive en `ups_body_3d.py` y colorea con `organ_visual_state()` (Pieza 2).
    assert "render_body_3d" not in twin and "anatomy3d" not in twin, "el 3D heurístico del aporte no entra"
    for doc in ("CHANGELOG.md", "CLAUDE.md"):
        text = (ROOT / doc).read_text(encoding="utf-8")
        assert "coloreados por su estado del UPS" not in text
        assert "Colores de estado** en el cuerpo 3D solo desde el UPS" not in text
    for path in ("src/imaging/volume3d.py", "app/supermodules/model3d/pages.py", "visualization/anatomy3d.py",
                 "app/supermodules/model3d/panels.py", "visualization/vcg3d.py", "src/signals/ecg/vcg.py"):
        src = (ROOT / path).read_text(encoding="utf-8")
        assert "visualization.art" not in src and "part_colors" not in src, path
