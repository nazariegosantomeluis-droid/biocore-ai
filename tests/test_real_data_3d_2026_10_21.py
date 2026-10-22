"""Tanda 2026-10-21: datos reales en lugar de dibujos, modelos 3D, "Crea tu
modelo 3D", IA local gratis y aprendizaje automático.

Qué se protege:
- Las mallas 3D salen de datos reales y abiertos (TC del TotalSegmentator,
  plantillas MNI/fsaverage) y traen su atribución; las medidas que muestra
  la app (volúmenes, V1-V6, electrodos) son coherentes con la anatomía.
- Los registros de PhysioNet se cargan, tienen licencia ODC-By y las
  mediciones sobre ellos (latido mediano, RR, bandas EEG, VCG) son estables.
- El VCG reconstruido con Kors se parece al VCG de Frank real del mismo
  paciente (validación con datos reales, no un supuesto).
- La reconstrucción de volúmenes (TC/RM -> malla), la exportación STL/OBJ/PLY
  y la lectura de DICOM funcionan con datos de prueba.
- El mapa de pacientes con aprendizaje automático evalúa FUERA de la muestra.
- El narrador funciona con una IA local gratuita (Ollama u OpenAI-compatible)
  sin clave, y falla de forma explícita si no hay motor (sin texto fingido).
- Integración: las páginas nuevas y las vistas 3D cargan sin excepciones.
"""
from __future__ import annotations

import io
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]


# ─── Anatomía 3D real ─────────────────────────────────────────────────────

def test_body_meshes_come_from_the_real_ct_with_attribution():
    from visualization.anatomy3d import load_body

    body = load_body()
    src = body.source
    assert src["license"] == "CC BY 4.0" and "10.5281/zenodo.10047292" in src["doi"]
    for key in ("heart", "lung_left", "lung_right", "brain", "spine", "ribs", "skin", "liver", "spinal_cord"):
        assert key in body.meshes, key
        mesh = body[key]
        assert mesh.faces.max() < mesh.vertices.shape[0]
        assert mesh.vertices.dtype == np.float32
    # Volúmenes medidos sobre las máscaras: rangos anatómicos plausibles.
    assert 350 < body["heart"].volume_ml < 1100
    assert 900 < body["liver"].volume_ml < 2600
    assert 1000 < body["brain"].volume_ml < 1800
    assert sum(m.n_faces for m in body.meshes.values()) < 220_000, "liviano para el navegador"


def test_precordial_landmarks_follow_the_placement_rules():
    from visualization.anatomy3d import load_body

    p = load_body().landmarks
    assert list(p) == ["V1", "V2", "V3", "V4", "V5", "V6"]
    x = {k: float(v[0]) for k, v in p.items()}
    z = {k: float(v[2]) for k, v in p.items()}
    # RAS: x > 0 = derecha del paciente.
    assert x["V1"] > 0 > x["V2"], "V1 a la derecha del esternón y V2 a la izquierda"
    assert x["V2"] > x["V3"] > x["V4"] > x["V5"] > x["V6"], "de medial a lateral izquierdo"
    assert abs(z["V1"] - z["V2"]) < 15, "ambos en el 4.º espacio intercostal"
    assert z["V4"] < z["V2"] - 15, "V4 (5.º espacio) más abajo"
    assert z["V4"] == pytest.approx(z["V5"]) == pytest.approx(z["V6"]), "V5 y V6 a la altura de V4"


def test_head_has_the_21_electrodes_on_the_scalp():
    from visualization.anatomy3d import electrode_point, load_head

    head = load_head()
    assert len(head.electrode_names) == 21 and {"Fp1", "Cz", "O2", "T7"} <= set(head.electrode_names)
    assert "scalp_lo" in head.meshes and head["scalp_lo"].n_faces < head["scalp"].n_faces
    assert "FreeSurfer" in head.source["head"] and "Collins" in head.source["notice"]
    name, pos = electrode_point("P4-O2")
    assert name == "P4-O2"
    assert electrode_point("t3")[0] == "T7", "nomenclatura antigua T3 -> T7"
    assert electrode_point("canal_raro") is None
    assert (ROOT / "data" / "anatomy3d" / "LICENSE-FreeSurfer.txt").is_file()


def test_body_figure_colors_and_focus():
    from visualization.anatomy3d import TWIN_ORGAN_PARTS, body_figure

    fig = body_figure(part_colors={"heart": "#ff4d4d"}, highlight=TWIN_ORGAN_PARTS["heart"])
    by_name = {t.name: t for t in fig.data}
    assert by_name["Corazón"].color == "#ff4d4d" and by_name["Corazón"].opacity == 1.0
    assert by_name["Encéfalo"].opacity < 0.5, "lo que no está enfocado se atenúa"
    assert len(fig.to_json()) < 3_500_000


def test_spherical_spline_reproduces_the_measured_values():
    from visualization.anatomy3d import electrode_positions, spherical_spline

    pos = electrode_positions(["Fp1", "Fp2", "C3", "C4", "O1", "O2", "Cz"])
    names = list(pos)
    src = np.stack([pos[n] for n in names])
    vals = np.arange(len(names), dtype=float)
    est = spherical_spline(src, vals, src, smoothing=1e-9)
    assert np.allclose(est, vals, atol=1e-3)
    flat = spherical_spline(src, np.full(len(names), 7.0), src * 1.01)
    assert np.allclose(flat, 7.0, atol=1e-6), "un campo constante sigue constante"


def test_head_map_greys_out_regions_without_electrodes():
    from visualization.anatomy3d import head_figure

    fig = head_figure(values={"Fp1": 1, "Fp2": 2, "C3": 3, "C4": 4}, value_label="alfa")
    assert fig.layout.meta["mapped"] and fig.layout.meta["points"] == 4
    scalp = fig.data[0]
    assert float(np.min(scalp.intensity)) == 0.0, "zonas lejos de todo electrodo quedan en gris"
    few = head_figure(values={"Fp1": 1, "Cz": 2})
    assert not few.layout.meta["mapped"], "con menos de 4 puntos no se interpola"


# ─── Renders y láminas con datos reales ──────────────────────────────────

def test_render_manifest_images_exist_with_alt_text_and_anchors():
    from visualization.art import renders as R

    man = R.manifest()
    assert {"organ_heart", "organ_lungs", "organ_brain", "organ_muscles", "organ_autonomic", "atlas_body",
            "atlas_precordial", "atlas_1020_top", "atlas_1020_left", "atlas_heart"} <= set(man)
    from PIL import Image

    for name, e in man.items():
        path = R.STATIC_DIR / e["file"]
        assert path.is_file() and path.suffix == ".webp"
        with Image.open(path) as im:
            assert im.size == (e["width"], e["height"])
        assert len(e["alt"]) > 20 and e["source"]
    assert set(R.anchors("atlas_precordial")) == {"V1", "V2", "V3", "V4", "V5", "V6"}
    assert {"SA", "AV", "His", "Apex"} <= set(R.anchors("atlas_heart"))


def test_render_figure_overlay_is_accessible_and_markdown_safe():
    from visualization.art import renders as R

    html = R.figure_html("atlas_precordial", '<circle cx="1" cy="1" r="1"/>', label="Prueba de capa")
    assert 'alt=""' in html, "con capa SVG la imagen es decorativa; la capa lleva el título"
    assert 'role="img"' in html and "Prueba de capa" in html
    assert "\n\n" not in html and "$" not in html


# ─── Registros reales de PhysioNet ───────────────────────────────────────

def test_reference_recordings_load_with_license():
    from src.signals import reference_recordings as RR

    assert RR.available()
    for key in RR.KEYS:
        rec = RR.load(key)
        assert rec.license == "ODC-By 1.0" and rec.citation
    d = RR.mitdb_100()
    assert d["fs"] == 360.0 and d["mlii"].size == 360 * 300
    assert d["symbols"].count("N") > 2000
    assert 600 < float(np.mean(RR.normal_rr_ms(400))) < 1000
    eeg = RR.cap_n16()
    assert eeg["fs"] == 100.0 and "P4-O2" in eeg["leads"]
    ptb = RR.ptb_s0010()
    assert {"I", "II", "V1", "V6", "VX", "VY", "VZ"} <= set(ptb["leads"])


def test_reference_eeg_is_alpha_dominant_posteriorly():
    from visualization.art.plates_real import reference_eeg_bands

    ref = reference_eeg_bands()
    assert ref["dominant"] == "alpha" and ref["relative"]["alpha"] > 40


# ─── Vectocardiograma ────────────────────────────────────────────────────

def test_kors_vcg_matches_the_real_frank_leads_of_the_same_patient():
    from src.signals.ecg.vcg import KORS_MATRIX, ptb_reference

    assert KORS_MATRIX.shape == (3, 8)
    ref = ptb_reference()
    cx, cy, cz = ref["corr"]
    assert cx > 0.9 and cy > 0.9 and cz > 0.6
    real, kors = ref["real"].measures, ref["kors"].measures
    assert abs(real.qrs_duration_ms - kors.qrs_duration_ms) < 15
    assert abs(real.qrs_t_angle_deg - kors.qrs_t_angle_deg) < 20
    assert 70 < real.qrs_duration_ms < 130


def test_vcg_csv_reader_derives_fs_from_a_time_column():
    from src.signals.ecg.vcg import read_leads_csv, vcg_from_12_leads
    from src.signals.reference_recordings import ptb_s0010

    d = ptb_s0010()
    n = int(d["fs"] * 10)
    cols = {"tiempo_ms": np.arange(n) / d["fs"] * 1000.0}
    for lead in ("i", "ii", "v1", "v2", "v3", "v4", "v5", "v6"):
        cols[lead] = d["leads"][lead.upper()][:n]
    import pandas as pd

    raw = pd.DataFrame(cols).to_csv(index=False).encode()
    leads, fs, note = read_leads_csv(raw)
    assert fs == pytest.approx(500.0, rel=1e-3) and "tiempo_ms" in note
    res = vcg_from_12_leads(leads, fs)
    assert res.n_beats >= 8 and 60 < res.heart_rate_bpm < 110


# ─── Volúmenes -> mallas ─────────────────────────────────────────────────

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
    bio = io.BytesIO()
    img = nib.Nifti1Image(lab, np.diag([2.0, 2.0, 2.0, 1.0]))
    bio.write(img.to_bytes())
    vol = V.load_any([("seg.nii", bio.getvalue())])
    assert vol.is_labels and V.label_values(vol) == [1, 2] and vol.spacing == (2.0, 2.0, 2.0)


def test_dicom_series_is_stacked_in_order():
    pytest.importorskip("pydicom")
    from pydicom.dataset import FileDataset, FileMetaDataset
    from pydicom.uid import ExplicitVRLittleEndian, generate_uid

    from src.imaging import volume3d as V

    files = []
    series = generate_uid()
    order = [3, 0, 4, 1, 2]           # desordenados a propósito
    for k in order:
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


def test_sample_ct_presets_give_anatomical_volumes():
    from src.imaging import volume3d as V

    vol = V.load_nifti_bytes((ROOT / "data" / "samples" / "tc_torax_s1397_2mm.nii.gz").read_bytes())
    assert vol.modality == "CT"
    lungs = V.mesh_from_mask(V.preset_mask(vol, "lungs"), vol.affine, target_faces=20000)
    assert 3500 < lungs.volume_ml < 7000
    bone = V.mesh_from_mask(V.preset_mask(vol, "bone"), vol.affine, target_faces=20000)
    assert 500 < bone.volume_ml < 2500


# ─── Aprendizaje automático ──────────────────────────────────────────────

def test_cohort_map_on_a_real_dataset_is_evaluated_out_of_sample():
    from src.ml.cohort_map import build_cohort_map, example_wdbc

    df, target = example_wdbc()
    cm = build_cohort_map(df, target=target, id_col="paciente")
    assert cm.coords.shape == (569, 3) and 2 <= cm.k <= 6
    assert 0.5 < cm.explained.sum() <= 1.0
    mr = cm.model
    assert mr.n_splits == 5 and mr.auc > 0.95
    assert mr.accuracy > mr.baseline_accuracy + 0.2, "mejor que adivinar la clase más común"
    assert len(mr.importances) > 0


def test_patient_tables_can_come_from_excel():
    from app.supermodules.model3d.pages import _read_table
    from src.ml.cohort_map import build_cohort_map, example_wdbc

    df, target = example_wdbc()
    buf = io.BytesIO()
    df.head(150).to_excel(buf, index=False)
    back = _read_table(buf.getvalue(), "pacientes.xlsx")
    assert list(back.columns) == list(df.columns) and len(back) == 150
    cm = build_cohort_map(back, target=target, id_col="paciente")
    assert cm.coords.shape == (150, 3) and cm.model.auc > 0.9
    csv = df.head(20).to_csv(index=False, sep=";").encode()
    assert len(_read_table(csv, "pacientes.csv")) == 20, "CSV con ; también"


def test_vital_columns_and_news2_scores():
    from src.ml.cohort_map import CohortError, build_cohort_map, news2_parameter_scores, vital_columns

    cols = vital_columns(["FC", "FR", "SpO2 (%)", "PAS", "Temp", "otra"])
    assert cols == {"pulse": "FC", "respiratory_rate": "FR", "spo2": "SpO2 (%)", "systolic_bp": "PAS",
                    "temperature_c": "Temp"}
    s = news2_parameter_scores({"FC": 130, "FR": 28, "SpO2 (%)": 89, "PAS": 85, "Temp": 39.4}, cols)
    assert s == {"pulse": 2, "respiratory_rate": 3, "spo2": 3, "systolic_bp": 3, "temperature_c": 2}
    assert news2_parameter_scores({"FC": 800}, {"pulse": "FC"})["pulse"] is None, "no plausible -> sin dato"
    import pandas as pd

    with pytest.raises(CohortError):
        build_cohort_map(pd.DataFrame({"a": [1, 2]}))


# ─── IA local gratis ─────────────────────────────────────────────────────

class _Ollama(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path == "/api/tags":
            body = json.dumps({"models": [{"name": "qwen2.5:7b"}, {"name": "llama3.2:3b"}]}).encode()
            self.send_response(200)
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        assert req["stream"] is True and req["messages"][0]["role"] == "system"
        self.send_response(200)
        self.end_headers()
        for w in ("Texto ", "de ", req["model"]):
            self.wfile.write((json.dumps({"message": {"content": w}, "done": False}) + "\n").encode())
        self.wfile.write(b'{"done": true}\n')


class _OpenAI(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path == "/v1/models":
            body = json.dumps({"data": [{"id": "modelo-local"}]}).encode()
            self.send_response(200)
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"]))
        self.send_response(200)
        self.end_headers()
        for w in ("Hola ", "SSE"):
            self.wfile.write(f"data: {json.dumps({'choices': [{'delta': {'content': w}}]})}\n\n".encode())
        self.wfile.write(b"data: [DONE]\n\n")


@pytest.fixture
def local_server():
    servers = []

    def start(handler):
        srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        servers.append(srv)
        return f"http://127.0.0.1:{srv.server_address[1]}"

    yield start
    from domain.physiology.narrator import providers

    providers.configure()
    for s in servers:
        s.shutdown()


def _ctx():
    from domain.physiology.narrator import Finding, FindingsContext

    return FindingsContext(lab_name="HRV", findings=[Finding("sdnn_ms", "45", "variabilidad")])


def test_narrator_streams_from_a_free_local_ollama_without_api_key(local_server, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from domain.physiology.narrator import is_configured, providers, stream_findings_narration

    providers.configure(provider="auto", url=local_server(_Ollama))
    eng = providers.resolve()
    assert eng.ready and eng.provider == "local" and eng.model == "qwen2.5:7b" and eng.api == "ollama"
    assert is_configured()
    assert "".join(stream_findings_narration(_ctx())) == "Texto de qwen2.5:7b"
    providers.configure(provider="local", model="llama3.2:3b", url=providers.local_url())
    assert "".join(stream_findings_narration(_ctx())).endswith("llama3.2:3b")


def test_narrator_streams_from_an_openai_compatible_local_server(local_server, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from domain.physiology.narrator import providers, stream_findings_narration

    providers.configure(provider="local", url=local_server(_OpenAI))
    assert providers.resolve().api == "openai"
    assert "".join(stream_findings_narration(_ctx())) == "Hola SSE"


def test_without_any_engine_the_narrator_fails_explicitly(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from domain.physiology.narrator import NarratorNotConfiguredError, is_configured, providers, \
        stream_findings_narration

    providers.configure(provider="auto", url="http://127.0.0.1:9")
    try:
        assert not is_configured()
        with pytest.raises(NarratorNotConfiguredError, match="Ollama"):
            "".join(stream_findings_narration(_ctx()))
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        eng = providers.resolve()
        assert eng.ready and eng.provider == "anthropic"
    finally:
        providers.configure()


# ─── Integración (AppTest) ───────────────────────────────────────────────

def _run(fn_path: str, **state):
    from streamlit.testing.v1 import AppTest

    module, func = fn_path.rsplit(".", 1)

    def _script(module, func):
        import importlib
        getattr(importlib.import_module(module), func)()

    at = AppTest.from_function(_script, args=(module, func), default_timeout=300)
    for k, v in state.items():
        at.session_state[k] = v
    at.run()
    assert not at.exception, at.exception
    return at


def test_create_your_3d_model_page_builds_from_the_sample_ct_and_exports():
    at = _run("app.supermodules.model3d.pages.run")
    labels = [t.label for t in at.tabs]
    assert labels[:5] == [
        ":material/view_in_ar: Tu tomografía o resonancia", ":material/deployed_code: Ver un modelo 3D",
        ":material/ecg_heart: ECG en 3D", ":material/neurology: EEG en 3D",
        ":material/scatter_plot: Tu base de pacientes"]
    next(b for b in at.button if b.key == "m3d_sample").click().run()
    next(b for b in at.button if b.key == "m3d_build").click().run()
    assert not at.exception
    assert len(at.get("download_button")) == 3
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Tipo detectado"] == "Tomografía" and "mL" in metrics["Volumen de la selección"]


def test_create_your_3d_model_page_trains_on_the_example_cohort():
    at = _run("app.supermodules.model3d.pages.run")
    next(b for b in at.button if b.key == "m3d_cohort_example").click().run()
    assert not at.exception
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Pacientes"] == "569" and "AUC" in metrics


def test_ecg_lab_has_a_3d_vectorcardiogram_tab():
    at = _run("app.main.render_ecg_lab_page")
    assert "Vectocardiograma 3D" in [t.label for t in at.tabs]
    assert any(m.label == "Ángulo QRS-T espacial" for m in at.metric)


def test_new_3d_lab_is_in_the_navigation():
    import app.main as main

    assert main.HUBS["Laboratorio 3D"] == ["🧊 Crea tu modelo 3D"]
    assert main.HUB_ICONS["Laboratorio 3D"] == ":material/view_in_ar:"


def test_eeg_lab_shows_its_channels_on_a_3d_head(tmp_path):
    from domain.physiology.state import create_patient, init_db, make_engine, make_session_factory

    engine = make_engine(Path(str(tmp_path / "eeg3d.db")))
    init_db(engine)
    sf = make_session_factory(engine)
    with sf() as s:
        pid = create_patient(s, display_name="EEG 3D (test)")
    at = _run("app.supermodules.eeg_neuro_lab.pages.run", twin_shell_ups_session_factory=sf,
              twin_shell_ups_patient_id=pid)
    assert any("Mapa 3D sobre la cabeza" in m.value for m in at.markdown)
    specs = [str(c.proto) for c in at.get("plotly_chart")]
    assert any("de la potencia" in s for s in specs), "falta la cabeza con la potencia por canal"
    engine.dispose()


def test_academia_atlas_has_the_3d_explorer():
    at = _run("app.supermodules.academia.pages.render_atlas_tab")
    assert "Explorar en 3D: el cuerpo de la tomografía real" in [e.label for e in at.expander]
    assert len(at.get("plotly_chart")) == 1
    assert any(".webp" in m.value for m in at.markdown), "las láminas usan los renders reales"


def test_sidebar_offers_the_free_local_ai_engine(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(ROOT / "app" / "main.py"), default_timeout=180)
    at.run()
    assert not at.exception
    assert "Motor de IA" in [e.label for e in at.sidebar.expander]
    captions = " ".join(c.value for c in at.sidebar.caption)
    assert "Sin motor de IA" in captions and "ollama pull qwen2.5:7b" in captions
