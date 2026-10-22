"""Crea tu modelo 3D (2026-10-21).

La persona sube SUS datos y obtiene un modelo 3D:
- tomografía o resonancia (NIfTI o DICOM, también mapas de segmentación)
  -> superficie 3D descargable (STL/OBJ/PLY);
- un modelo 3D que ya tenga (STL/OBJ/PLY) -> visor con medidas;
- ECG de 12 derivaciones -> vectocardiograma 3D;
- EEG -> mapa de potencia por banda sobre una cabeza 3D;
- una tabla de pacientes -> mapa 3D con aprendizaje automático (PCA,
  K-means, Isolation Forest, bosque aleatorio con validación cruzada) y,
  si trae signos vitales, el paciente sobre el cuerpo 3D (NEWS2).

Cada pestaña trae un ejemplo real para probar sin datos propios. Todo se
procesa en la computadora de la persona; no se usa ninguna IA externa.
"""

from __future__ import annotations

import hashlib
import io
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
import streamlit as st

from app.supermodules.model3d.panels import plotly_3d, render_reference_eeg_map, render_head_map, \
    relative_band_power, render_vcg_panel
from app.utils.design_system import PALETTE, render_error_state, render_module_header, render_section_header

ROOT = Path(__file__).resolve().parents[3]
SAMPLE_CT = ROOT / "data" / "samples" / "tc_torax_s1397_2mm.nii.gz"
SAMPLE_CT_SOURCE = ("TotalSegmentator dataset v2, sujeto s1397 (Wasserthal et al., Radiology: AI 2023; CC BY 4.0): "
                    "tórax recortado y remuestreado a 2 mm.")

TABS = [
    ":material/view_in_ar: Tu tomografía o resonancia",
    ":material/deployed_code: Ver un modelo 3D",
    ":material/ecg_heart: ECG en 3D",
    ":material/neurology: EEG en 3D",
    ":material/scatter_plot: Tu base de pacientes",
]
QUALITY = {"rapida": ("Rápida", 60_000, 9_000_000), "detallada": ("Detallada", 220_000, 24_000_000)}
LABEL_COLORS = ("#e9dec7", "#c0394c", "#eeb0ab", "#5872c9", "#f1d78b", "#b4493f", "#9a3b31", "#7f9e4a",
                "#e6c086", "#93405a", "#a54a3c", "#ddb05f")


def _digest(raw: bytes) -> str:
    return hashlib.sha1(raw).hexdigest()[:16]


# ─────────────────────────────────────────────────────────────────────────
# 1. Tomografía o resonancia -> 3D
# ─────────────────────────────────────────────────────────────────────────

def _slice_previews(vol, mask: Optional[np.ndarray]) -> List[Tuple[str, np.ndarray]]:
    """Cortes centrales (axial, coronal, sagital) en RGB, con la selección en cian."""
    d = vol.data
    if vol.modality == "CT":
        lo, hi = -1000.0, 1000.0
    else:
        finite = d[np.isfinite(d)]
        lo, hi = (float(np.percentile(finite, 1)), float(np.percentile(finite, 99))) if finite.size else (0.0, 1.0)
    out = []
    i, j, k = (s // 2 for s in d.shape)
    for title, sl, ms in (("Axial", d[:, :, k], None if mask is None else mask[:, :, k]),
                          ("Coronal", d[:, j, :], None if mask is None else mask[:, j, :]),
                          ("Sagital", d[i, :, :], None if mask is None else mask[i, :, :])):
        g = np.clip((np.nan_to_num(sl) - lo) / ((hi - lo) or 1.0), 0, 1).T[::-1]
        rgb = np.stack([g, g, g], axis=-1)
        if ms is not None:
            m = ms.T[::-1]
            rgb[m] = rgb[m] * 0.45 + np.array([0.13, 0.83, 0.93]) * 0.55
        out.append((title, (rgb * 255).astype(np.uint8)))
    return out


def _load_volume_from_inputs() -> Optional[object]:
    from src.imaging import volume3d as V

    c1, c2 = st.columns([3, 2])
    with c1:
        files = st.file_uploader(
            "NIfTI (.nii, .nii.gz) o serie DICOM (varios archivos o un .zip)", accept_multiple_files=True,
            key="m3d_files", help="Se procesa en tu computadora; nada se envía a internet.")
    with c2:
        st.caption("¿Sin un estudio a mano?")
        if st.button("Usar el ejemplo: TC real de tórax", key="m3d_sample", width="stretch"):
            st.session_state["m3d_use_sample"] = True
    if files:
        st.session_state["m3d_use_sample"] = False
        payload = [(f.name, f.getvalue()) for f in files]
        digest = _digest(b"".join(r for _, r in payload))
        if st.session_state.get("m3d_volume_digest") != digest:
            with st.spinner("Leyendo el estudio…"):
                try:
                    st.session_state["m3d_volume"] = V.load_any(payload)
                    st.session_state["m3d_volume_digest"] = digest
                    st.session_state.pop("m3d_mesh", None)
                except V.VolumeError as exc:
                    st.error(f"No se pudo leer: {exc}")
                    return None
                except Exception as exc:  # noqa: BLE001
                    render_error_state("No se pudo leer el estudio.", exception=exc)
                    return None
    elif st.session_state.get("m3d_use_sample"):
        if st.session_state.get("m3d_volume_digest") != "sample":
            st.session_state["m3d_volume"] = V.load_nifti_bytes(SAMPLE_CT.read_bytes(), SAMPLE_CT.name)
            st.session_state["m3d_volume"].notes.append("Ejemplo: " + SAMPLE_CT_SOURCE)
            st.session_state["m3d_volume_digest"] = "sample"
            st.session_state.pop("m3d_mesh", None)
    return st.session_state.get("m3d_volume")


def render_imaging_tab() -> None:
    from src.imaging import volume3d as V
    from visualization.anatomy3d import mesh_figure

    st.markdown("Sube una tomografía (TC) o resonancia (RM) y obtén su modelo 3D para girarlo, medirlo, "
                "imprimirlo o abrirlo en 3D Slicer o Blender.")
    vol = _load_volume_from_inputs()
    if vol is None:
        return
    sx, sy, sz = vol.spacing
    kind, kind_help = {"CT": ("Tomografía", "TC en unidades Hounsfield."),
                       "labels": ("Segmentación", "Mapa de etiquetas: cada número es una estructura."),
                       "MR": ("Resonancia", "Intensidades de RM (sin unidades absolutas)."),
                       "other": ("Otro volumen", "Intensidades sin unidades conocidas.")}[vol.modality]

    def _mm(v: float) -> str:
        return f"{v:.2f}".rstrip("0").rstrip(".")

    voxel = _mm(sx) if max(vol.spacing) - min(vol.spacing) < 1e-3 else "×".join(_mm(s) for s in vol.spacing)
    cols = st.columns(4)
    cols[0].metric("Tipo detectado", kind, help=kind_help)
    cols[1].metric("Vóxeles", "×".join(str(s) for s in vol.shape))
    cols[2].metric("Vóxel (mm)", voxel, help=f"{sx:.3f} × {sy:.3f} × {sz:.3f} mm")
    origin = "Ejemplo" if st.session_state.get("m3d_volume_digest") == "sample" else vol.source
    cols[3].metric("Origen", origin if len(origin) <= 14 else origin[:12] + "…", help=vol.source)
    for n in vol.notes:
        st.caption(n)

    selection: Optional[tuple] = None
    color = "#e9dec7"
    keep: Optional[int] = None
    if vol.is_labels:
        values = V.label_values(vol)
        counts = {v: int((vol.data == v).sum()) for v in values[:64]}
        labels_sel = st.multiselect(
            "Etiquetas a reconstruir", values, default=values[: min(6, len(values))],
            format_func=lambda v: f"Etiqueta {v} ({counts.get(v, 0):,} vóxeles)".replace(",", " "),
            key="m3d_labels")
        selection = ("labels", tuple(labels_sel)) if labels_sel else None
    elif vol.modality == "CT":
        choices = list(V.CT_PRESETS) + ["manual"]
        preset = st.radio("Qué reconstruir", choices, horizontal=True, key="m3d_preset",
                          format_func=lambda p: V.CT_PRESETS[p]["label"] if p in V.CT_PRESETS else "Umbral manual")
        if preset == "manual":
            lo, hi = st.slider("Rango (HU)", -1024, 3000, (200, 3000), step=10, key="m3d_hu")
            selection = ("range", float(lo), float(hi))
        else:
            selection = ("preset", preset)
            color = V.CT_PRESETS[preset]["color"]
            keep = 1 if preset == "skin" else None
    else:
        finite = vol.data[np.isfinite(vol.data)]
        auto = V.otsu_threshold(vol.data)
        lo_v, hi_v = float(np.percentile(finite, 0.5)), float(np.percentile(finite, 99.9))
        thr = st.slider("Umbral de intensidad (por defecto: Otsu)", lo_v, hi_v, float(np.clip(auto, lo_v, hi_v)),
                        key="m3d_thr")
        selection = ("range", float(thr), None)
        color = "#c3cddd"
    c1, c2 = st.columns([2, 3])
    with c1:
        quality = st.segmented_control("Calidad", list(QUALITY), format_func=lambda q: QUALITY[q][0],
                                       default="rapida", key="m3d_quality") or "rapida"
    with c2:
        largest = st.toggle("Solo la pieza más grande", value=bool(keep), key="m3d_largest",
                            help="Quita islas sueltas (ruido, la camilla del tomógrafo...).")
    _, target_faces, max_vox = QUALITY[quality]

    with st.expander("Ver los cortes centrales (la selección en cian)", expanded=False):
        preview = None
        if selection is not None:
            try:
                preview = _selection_mask(vol, selection)
            except Exception:  # noqa: BLE001
                preview = None
        cols = st.columns(3)
        for col, (title, img) in zip(cols, _slice_previews(vol, preview)):
            col.image(img, caption=title, width="stretch")

    if st.button("Reconstruir en 3D", type="primary", key="m3d_build", icon=":material/view_in_ar:"):
        if selection is None:
            st.warning("Elige qué reconstruir.")
            return
        with st.spinner("Reconstruyendo la superficie (marching cubes)…"):
            try:
                small, _step = V.downsample_for_mesh(vol, max_voxels=max_vox)
                meshes = []
                if selection[0] == "labels":
                    per = max(8000, target_faces // max(len(selection[1]), 1))
                    for n, lab in enumerate(selection[1]):
                        m = V.mesh_from_mask(small.data == lab, small.affine, target_faces=per,
                                             keep_components=1 if largest else None)
                        meshes.append((f"Etiqueta {lab}", LABEL_COLORS[n % len(LABEL_COLORS)], m))
                else:
                    m = V.mesh_from_mask(_selection_mask(small, selection), small.affine,
                                         target_faces=target_faces, keep_components=1 if largest else None)
                    meshes.append(("Modelo", color, m))
                st.session_state["m3d_mesh"] = {"meshes": meshes, "notes": small.notes[len(vol.notes):]}
            except V.VolumeError as exc:
                st.error(str(exc))
                return
            except MemoryError:
                st.error("No alcanzó la memoria: elige la calidad «Rápida».")
                return
    built = st.session_state.get("m3d_mesh")
    if not built:
        return
    meshes = built["meshes"]
    import plotly.graph_objects as go

    if len(meshes) == 1:
        name, col, m = meshes[0]
        fig = mesh_figure(m.vertices, m.faces, color=col, label=name, camera="front", height=620)
    else:
        allv = np.concatenate([m.vertices for _, _, m in meshes])
        center = (allv.min(axis=0) + allv.max(axis=0)) / 2.0
        fig = go.Figure()
        for name, col, m in meshes:
            v = m.vertices - center
            fig.add_trace(go.Mesh3d(x=v[:, 0], y=v[:, 1], z=v[:, 2], i=m.faces[:, 0], j=m.faces[:, 1],
                                    k=m.faces[:, 2], color=col, name=name, flatshading=False,
                                    lighting=dict(ambient=0.42, diffuse=0.78, specular=0.32, roughness=0.42,
                                                  fresnel=0.22),
                                    hovertemplate=f"<b>{name}</b><br>{m.volume_ml:,.0f} mL<extra></extra>"
                                    .replace(",", " ")))
        from visualization.anatomy3d import _scene_layout
        fig.update_layout(**_scene_layout("front", 620, uirevision="m3d_labels"))
    plotly_3d(fig, key="m3d_fig")
    total_faces = sum(m.n_faces for _, _, m in meshes)
    vol_ml = sum(m.volume_ml for _, _, m in meshes)
    allv = np.concatenate([m.vertices for _, _, m in meshes])
    size = allv.max(axis=0) - allv.min(axis=0)
    cols = st.columns(3)
    cols[0].metric("Triángulos", f"{total_faces:,}".replace(",", " "))
    cols[1].metric("Volumen de la selección", f"{vol_ml:,.0f} mL".replace(",", " "),
                   help="Vóxeles seleccionados × volumen del vóxel (antes de suavizar la superficie).")
    cols[2].metric("Tamaño", f"{size[0] / 10:.1f} × {size[1] / 10:.1f} × {size[2] / 10:.1f} cm")
    for n in built["notes"] + [x for _, _, m in meshes for x in m.notes][:2]:
        st.caption(n)
    verts = np.concatenate([m.vertices for _, _, m in meshes])
    offs = np.cumsum([0] + [m.vertices.shape[0] for _, _, m in meshes[:-1]])
    faces = np.concatenate([m.faces + o for (_, _, m), o in zip(meshes, offs)])
    st.caption(_quality_caption(V.mesh_quality(faces)))
    d1, d2, d3 = st.columns(3)
    d1.download_button("Descargar STL", V.to_stl(verts, faces), "modelo_biocore.stl", "model/stl",
                       key="m3d_dl_stl", icon=":material/download:", width="stretch")
    d2.download_button("Descargar OBJ", V.to_obj(verts, faces), "modelo_biocore.obj", "model/obj",
                       key="m3d_dl_obj", icon=":material/download:", width="stretch")
    d3.download_button("Descargar PLY", V.to_ply(verts, faces), "modelo_biocore.ply", "application/octet-stream",
                       key="m3d_dl_ply", icon=":material/download:", width="stretch")
    st.caption("Coordenadas en milímetros (RAS: x hacia la derecha del paciente, y hacia delante, z hacia arriba). "
               "Superficie por marching cubes (Lorensen y Cline, 1987). Es un modelo educativo: no sirve para "
               "planear tratamientos.")


def _quality_caption(q) -> str:
    """Calidad topológica de la malla (`V.mesh_quality`), en una línea."""
    if q.watertight:
        head = "Malla cerrada ✓ (sin huecos: el volumen está definido y se puede imprimir en 3D)"
    else:
        head = f"Malla abierta ✗ ({q.open_edges} aristas sin cerrar: el volumen encerrado no es fiable)"
    winding = "orientación de las caras consistente" if q.winding_consistent else "caras con orientación mezclada"
    return f"{head} · {winding} · {q.bodies} pieza{'s' if q.bodies != 1 else ''}."


def _selection_mask(vol, selection: tuple) -> np.ndarray:
    """Máscara de la selección sobre `vol` (el original o el reducido)."""
    from src.imaging import volume3d as V

    kind = selection[0]
    if kind == "preset":
        return V.preset_mask(vol, selection[1])
    if kind == "range":
        return V.threshold_mask(vol, selection[1], selection[2])
    if kind == "labels":
        return np.isin(vol.data, list(selection[1]))
    raise ValueError(kind)


# ─────────────────────────────────────────────────────────────────────────
# 2. Visor de modelos
# ─────────────────────────────────────────────────────────────────────────

def render_mesh_viewer_tab() -> None:
    from src.imaging import volume3d as V
    from visualization.anatomy3d import mesh_figure

    st.markdown("Abre un modelo 3D (STL, OBJ o PLY): uno exportado de 3D Slicer, de una impresora 3D o el "
                "que descargaste en la primera pestaña.")
    up = st.file_uploader("Modelo 3D", type=["stl", "obj", "ply"], key="m3d_mesh_file")
    if up is None:
        return
    try:
        v, f = V.read_mesh(up.name, up.getvalue())
    except Exception as exc:  # noqa: BLE001
        st.error(f"No se pudo leer el modelo: {exc}")
        return
    if f.shape[0] == 0:
        st.error("El archivo no tiene triángulos.")
        return
    stats = V.mesh_stats(v, f)
    quality = V.mesh_quality(f)
    shown_f = f
    if f.shape[0] > 300_000:
        try:
            import fast_simplification

            v2, shown_f = fast_simplification.simplify(v.astype(np.float32), f.astype(np.int32),
                                                       target_reduction=1 - 300_000 / f.shape[0])
            v = np.asarray(v2)
            st.caption("Para verlo fluido se simplificó a 300 000 triángulos (las medidas son del original).")
        except ImportError:
            pass
    cols = st.columns(4)
    cols[0].metric("Triángulos", f"{int(stats['triangles']):,}".replace(",", " "))
    cols[1].metric("Área", f"{stats['area_cm2']:,.1f} cm²".replace(",", " "))
    cols[2].metric("Volumen encerrado",
                   f"{stats['volume_ml']:,.1f} mL".replace(",", " ") if quality.watertight else "no fiable",
                   help="Solo está definido si la malla es cerrada (sin huecos); ver la línea de calidad abajo.")
    cols[3].metric("Tamaño", f"{stats['size_x_mm']:.0f}×{stats['size_y_mm']:.0f}×{stats['size_z_mm']:.0f}",
                   help="En las unidades del archivo (normalmente mm).")
    st.caption(_quality_caption(quality))
    plotly_3d(mesh_figure(v, shown_f, color="#c3cddd", label=up.name, height=620), key="m3d_mesh_fig")


# ─────────────────────────────────────────────────────────────────────────
# 4. EEG
# ─────────────────────────────────────────────────────────────────────────

def render_eeg_tab() -> None:
    st.markdown("La potencia de cada banda del EEG, medida canal por canal con el mismo analizador de EEG "
                "Neuro Lab, dibujada sobre una cabeza 3D con el sistema 10-20.")
    source = st.segmented_control("Fuente del EEG", ["ref", "upload"],
                                  format_func={"ref": "EEG real de ejemplo", "upload": "Subir mi EEG (CSV)"}.get,
                                  default="ref", key="m3d_eeg_source") or "ref"
    if source == "ref":
        render_reference_eeg_map("m3d_eeg_ref")
        return
    up = st.file_uploader("CSV: una columna por canal con nombre 10-20 (Fp1, C3, O2… o bipolares P4-O2)",
                          type=["csv", "txt"], key="m3d_eeg_csv")
    fs = st.number_input("Frecuencia de muestreo (Hz)", 50, 5000, 256, key="m3d_eeg_fs")
    if up is None:
        return
    import pandas as pd

    try:
        df = pd.read_csv(io.BytesIO(up.getvalue()), sep=None, engine="python")
    except Exception as exc:  # noqa: BLE001
        st.error(f"No se pudo leer el CSV: {exc}")
        return
    sig = {}
    for c in df.columns:
        if str(c).strip().lower() in ("time", "t", "tiempo"):
            continue
        s = pd.to_numeric(df[c], errors="coerce")
        if s.notna().mean() > 0.9:
            sig[str(c).strip()] = s.interpolate(limit_direction="both").to_numpy(float)
    if not sig:
        st.error("No se encontraron columnas numéricas.")
        return
    with st.spinner("Calculando la potencia por banda…"):
        rel = relative_band_power(sig, float(fs))
    if not rel:
        st.warning("Ningún canal tuvo señal limpia suficiente para el análisis (mínimo unos segundos).")
        return
    render_head_map(rel, "m3d_eeg_up")


# ─────────────────────────────────────────────────────────────────────────
# 5. Base de pacientes -> aprendizaje automático
# ─────────────────────────────────────────────────────────────────────────

def _read_table(raw: bytes, name: str, nrows: Optional[int] = None):
    """CSV/TXT (separador detectado solo) o Excel .xlsx (la primera hoja)."""
    import pandas as pd

    if str(name).lower().endswith((".xlsx", ".xlsm")):
        return pd.read_excel(io.BytesIO(raw), nrows=nrows)
    return pd.read_csv(io.BytesIO(raw), sep=None, engine="python", nrows=nrows)


@st.cache_data(show_spinner=False, max_entries=8)
def _cohort(raw: bytes, name: str, target: Optional[str], id_col: Optional[str]):
    from src.ml.cohort_map import build_cohort_map

    df = _read_table(raw, name)
    return df, build_cohort_map(df, target=target, id_col=id_col)


def _example_csv() -> bytes:
    from src.ml.cohort_map import example_wdbc

    df, _ = example_wdbc()
    return df.to_csv(index=False).encode("utf-8")


def render_cohort_tab() -> None:
    from src.ml.cohort_map import (KMEANS_CITATION, PCA_CITATION, RF_CITATION, WDBC_CITATION, CohortError,
                                   news2_parameter_scores, top_loadings, vital_columns)
    from visualization.cohort3d import cohort_figure, importance_figure

    st.markdown("Sube tu tabla de pacientes (una fila por paciente, una columna por variable) y el aprendizaje "
                "automático la convierte en un mapa 3D: pacientes parecidos quedan cerca. Sin IA externa ni "
                "claves: todo corre en tu computadora con scikit-learn.")
    c1, c2 = st.columns([3, 2])
    with c1:
        up = st.file_uploader("Tabla CSV o Excel (.xlsx)", type=["csv", "txt", "xlsx"], key="m3d_cohort_csv",
                              help="Excel: se lee la primera hoja, con los nombres de columna en la primera fila.")
    with c2:
        st.caption("¿Sin datos a mano?")
        if st.button("Usar un ejemplo real: 569 pacientes (WDBC)", key="m3d_cohort_example", width="stretch"):
            st.session_state["m3d_cohort_raw"] = _example_csv()
            st.session_state["m3d_cohort_name"] = "ejemplo"
    if up is not None:
        st.session_state["m3d_cohort_raw"] = up.getvalue()
        st.session_state["m3d_cohort_name"] = up.name
    raw = st.session_state.get("m3d_cohort_raw")
    if not raw:
        st.caption("Ejemplo: Wisconsin Diagnostic Breast Cancer, base clínica real con 30 medidas de núcleos "
                   "celulares y el diagnóstico confirmado de cada paciente.")
        return
    name = st.session_state.get("m3d_cohort_name", "")
    is_example = name == "ejemplo"
    try:
        head = _read_table(raw, name, nrows=200)
    except ImportError:
        st.error("Para leer Excel falta el paquete openpyxl (pip install openpyxl). También puedes guardar la "
                 "hoja como CSV.")
        return
    except Exception as exc:  # noqa: BLE001
        st.error(f"No se pudo leer la tabla: {exc}")
        return
    cols = list(head.columns)
    c1, c2 = st.columns(2)
    id_default = cols.index("paciente") + 1 if "paciente" in cols else 0
    id_col = c1.selectbox("Columna que identifica al paciente (opcional)", ["(ninguna)"] + cols,
                          index=id_default, key="m3d_cohort_id")
    tgt_default = cols.index("diagnóstico") + 1 if "diagnóstico" in cols else 0
    target = c2.selectbox("Columna objetivo para entrenar un modelo (opcional)", ["(ninguna)"] + cols,
                          index=tgt_default, key="m3d_cohort_target",
                          help="Una categoría por paciente (diagnóstico, desenlace...). Se evalúa con validación "
                               "cruzada: los números son FUERA de la muestra de entrenamiento.")
    id_col = None if id_col == "(ninguna)" else id_col
    target = None if target == "(ninguna)" else target
    with st.spinner("Entrenando (PCA, K-means, Isolation Forest y bosque aleatorio)…"):
        try:
            df, cm = _cohort(raw, name, target, id_col)
        except CohortError as exc:
            st.error(str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            render_error_state("No se pudo analizar la tabla.", exception=exc)
            return
    color_opts = ["cluster", "outlier"] + (["target"] if target else [])
    color_by = st.segmented_control(
        "Colorear por", color_opts, default="target" if target else "cluster", key="m3d_cohort_color",
        format_func={"cluster": "Grupos (K-means)", "outlier": "Atípicos", "target": f"«{target}»"}.get)
    pick = st.selectbox("Paciente a resaltar", ["(ninguno)"] + cm.row_ids, key="m3d_cohort_pick")
    hl = None if pick == "(ninguno)" else cm.row_ids.index(pick)
    fig = cohort_figure(cm, color_by=color_by or "cluster", labels=df[target].tolist() if target else None,
                        highlight=hl, height=600)
    plotly_3d(fig, key="m3d_cohort_fig")
    m = st.columns(4)
    m[0].metric("Pacientes", f"{len(cm.row_ids)}")
    m[1].metric("Variables usadas", f"{len(cm.features)}")
    m[2].metric("Varianza en los 3 ejes", f"{cm.explained.sum():.0%}")
    m[3].metric("Grupos", f"{cm.k}", help=f"El k con mejor silueta ({cm.silhouette:.2f})." if cm.silhouette
                else None)
    with st.expander("Qué significa cada eje", expanded=False):
        for ax in range(3):
            if cm.explained[ax] <= 0:
                continue
            parts = ", ".join(f"{n} ({'+' if w > 0 else '−'})" for n, w in top_loadings(cm, ax))
            st.markdown(f"**CP{ax + 1}** ({cm.explained[ax]:.0%} de la varianza): sobre todo {parts}.")
        st.caption(PCA_CITATION)
    if cm.model is not None:
        mr = cm.model
        st.markdown(f"#### Modelo para predecir «{mr.target}»")
        k = st.columns(3)
        k[0].metric("Exactitud (validación cruzada)", f"{mr.accuracy:.1%}",
                    help=f"{mr.n_splits} pliegues estratificados. Si siempre dijera la clase más común: "
                         f"{mr.baseline_accuracy:.1%}.")
        k[1].metric("Exactitud balanceada", f"{mr.balanced_accuracy:.1%}")
        k[2].metric("AUC", f"{mr.auc:.3f}" if mr.auc is not None else "—")
        if mr.importances:
            plotly_3d(importance_figure(mr.importances, height=60 + 26 * len(mr.importances)),
                      key="m3d_cohort_importance")
        st.caption("Importancia por permutación en los datos de prueba de cada pliegue: cuánto AUC pierde el "
                   "modelo si se baraja esa variable. Cuando varias variables dicen lo mismo (están "
                   "correlacionadas), la importancia se reparte entre ellas y cada una parece pequeña. "
                   f"{RF_CITATION} Es un análisis exploratorio, no un diagnóstico ni un modelo validado para "
                   "uso clínico.")
    if int(cm.outlier.sum()):
        with st.expander(f"Pacientes atípicos para revisar ({int(cm.outlier.sum())})"):
            st.write(", ".join(cm.row_ids[i] for i in np.nonzero(cm.outlier)[0][:200]))
            st.caption("Isolation Forest: pueden ser errores de captura o casos realmente raros.")
    with st.expander("Perfil de cada grupo (valores z: 0 = promedio de la tabla)"):
        st.dataframe(cm.cluster_profiles.round(2).T, width="stretch")
        st.caption(KMEANS_CITATION)
    for n in cm.notes[:6]:
        st.caption(n)
    if is_example:
        st.caption("Ejemplo real: " + WDBC_CITATION)

    st.markdown("#### El paciente sobre el cuerpo 3D")
    vit = vital_columns(df.columns)
    if not vit:
        st.caption("Si tu tabla trae signos vitales (columnas como FC, FR, SpO2, PAS, Temp), aquí puedes ver a "
                   "cada paciente sobre el cuerpo 3D, coloreado con la puntuación NEWS2 de cada parámetro.")
        return
    who = st.selectbox("Paciente", cm.row_ids, index=hl or 0, key="m3d_cohort_body")
    row = df.iloc[cm.row_ids.index(who)].to_dict()
    scores = news2_parameter_scores(row, vit)
    _render_patient_body(scores, row, vit)


def _news2_color(score: Optional[int]) -> Optional[str]:
    if score is None:
        return None
    return PALETTE.STABLE if score == 0 else (PALETTE.WARNING if score < 3 else PALETTE.CRITICAL)


def _render_patient_body(scores, row, vit) -> None:
    from clinical.calculators import NEWS2_CITATION
    from visualization import anatomy3d as A3

    names = {"pulse": "Pulso", "respiratory_rate": "Frecuencia respiratoria", "spo2": "SpO₂",
             "systolic_bp": "Presión sistólica", "temperature_c": "Temperatura"}
    organ_scores = {
        "heart": [scores.get("pulse"), scores.get("systolic_bp")],
        "lungs": [scores.get("respiratory_rate"), scores.get("spo2")],
    }
    part_colors, notes = {}, {}
    for organ, vals in organ_scores.items():
        vals = [v for v in vals if v is not None]
        if not vals:
            continue
        color = _news2_color(max(vals))
        for p in A3.TWIN_ORGAN_PARTS[organ]:
            part_colors[p] = color
            notes[p] = f"NEWS2 del parámetro: {max(vals)} puntos"
    fig = A3.body_figure(systems=("skeleton", "circulatory", "respiratory", "skin"), part_colors=part_colors,
                         part_notes=notes, highlight=tuple(part_colors), camera="front", height=560)
    c1, c2 = st.columns([3, 2])
    with c1:
        plotly_3d(fig, key="m3d_patient_body")
    with c2:
        rows = []
        for p, label in names.items():
            col = vit.get(p)
            val = row.get(col) if col else None
            sc = scores.get(p)
            rows.append({"Parámetro": label, "Valor": "—" if val is None else str(val),
                         "NEWS2": "sin dato" if sc is None else f"{sc}"})
        st.table(rows)
        st.caption("Corazón: el peor de pulso y presión sistólica; pulmones: el peor de frecuencia respiratoria "
                   "y SpO₂. Verde 0 puntos, ámbar 1-2, rojo 3. " + NEWS2_CITATION)


# ─────────────────────────────────────────────────────────────────────────

def main() -> None:
    render_module_header(
        "Crea tu modelo 3D", icon="🧊",
        subtitle="Tus datos en 3D: tomografías, modelos, ECG, EEG y tablas de pacientes. Todo se procesa en "
                 "tu computadora.",
    )
    tabs = st.tabs(TABS)
    with tabs[0]:
        render_section_header("De tu estudio de imagen a un modelo 3D")
        render_imaging_tab()
    with tabs[1]:
        render_section_header("Visor de modelos 3D")
        render_mesh_viewer_tab()
    with tabs[2]:
        render_section_header("Vectocardiograma 3D")
        render_vcg_panel("m3d_vcg", allow_clinical=False)
    with tabs[3]:
        render_section_header("Mapa del EEG sobre la cabeza")
        render_eeg_tab()
    with tabs[4]:
        render_section_header("Tu base de pacientes en 3D")
        render_cohort_tab()


def run() -> None:
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        render_error_state("No se pudo cargar Crea tu modelo 3D.", exception=exc)
