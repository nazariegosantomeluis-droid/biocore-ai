"""
Reconstrucción 3D (2026-10-21): lo que se trajo de Medical3DReconstruction
(repo propio, MIT) a "Crea tu modelo 3D", y su validación contra una
referencia real.

- Postproceso pulmonar de Hu, Hoffman & Reinhardt 2001 (relleno + cierre de
  2 mm), con selección de bolsas de aire por tamaño relativo (la de "las N
  mayores" metía el gas del estómago en "Pulmones").
- Calidad de malla (estanca, orientación, piezas) sin `trimesh`.

Referencia: las superficies de TotalSegmentator del MISMO sujeto (s1397) que
la TC de ejemplo, en `data/anatomy3d/body_ts_s1397.npz` (vértices relativos
a `meta["origin_mm"]`).
"""

from functools import lru_cache
from pathlib import Path

import numpy as np
import pytest
from scipy.spatial import cKDTree

from src.imaging import volume3d as V

_SAMPLE = Path("data/samples/tc_torax_s1397_2mm.nii.gz")


def _sample_surface(v, f, per_mm2=1.0, seed=0):
    rng = np.random.default_rng(seed)
    tri = np.asarray(v, float)[np.asarray(f)]
    area = np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1) / 2
    idx = np.repeat(np.arange(len(tri)), rng.poisson(area * per_mm2))
    r1, r2 = rng.random(len(idx)), rng.random(len(idx))
    s = np.sqrt(r1)
    t = tri[idx]
    return (1 - s)[:, None] * t[:, 0] + (s * (1 - r2))[:, None] * t[:, 1] + (s * r2)[:, None] * t[:, 2]


@lru_cache(maxsize=1)
def _lungs_vs_reference():
    from visualization.anatomy3d import load_body

    body = load_body()
    origin = np.asarray(body.meta["origin_mm"], float)
    parts = ("lung_left", "lung_right", "trachea")
    ref = np.vstack([_sample_surface(np.asarray(body.meshes[p].vertices, float) + origin, body.meshes[p].faces)
                     for p in parts])
    ref_ml = sum(p["volume_ml"] for p in body.meta["parts"] if p.get("key") in parts)
    vol = V.load_nifti_bytes(_SAMPLE.read_bytes(), _SAMPLE.name)
    mesh = V.mesh_from_mask(V.preset_mask(vol, "lungs"), vol.affine)
    ours = _sample_surface(mesh.vertices, mesh.faces)
    d_ours, _ = cKDTree(ref).query(ours)
    d_ref, _ = cKDTree(ours).query(ref)
    return mesh, ref_ml, d_ours, d_ref


# --- Validación contra TotalSegmentator (mismo sujeto) ---------------------

def test_lung_preset_volume_matches_the_reference_segmentation():
    """Medido: 4962 mL frente a 5056 mL (pulmones + tráquea), -1.9%. Antes
    de este cambio: 5228 mL (+3.4%), por el gas abdominal."""
    mesh, ref_ml, _, _ = _lungs_vs_reference()
    assert ref_ml == pytest.approx(5056.1, abs=1.0)
    assert abs(mesh.volume_ml / ref_ml - 1) < 0.05


def test_lung_preset_surface_matches_the_reference_in_both_directions():
    """Medido: distancia media 1.23 mm (BIOCORE -> ref) y 1.30 mm (ref ->
    BIOCORE), p95 3.9 / 3.6 mm, con vóxel de 2 mm. Antes: 7.8 mm y p95 60 mm
    en el sentido BIOCORE -> ref (gas del estómago e intestino)."""
    _, _, d_ours, d_ref = _lungs_vs_reference()
    assert d_ours.mean() < 2.0 and np.percentile(d_ours, 95) < 6.0
    assert d_ref.mean() < 2.0 and np.percentile(d_ref, 95) < 6.0


def test_lung_preset_mesh_is_watertight():
    mesh, _, _, _ = _lungs_vs_reference()
    q = V.mesh_quality(mesh.faces)
    assert q.watertight and q.winding_consistent and q.open_edges == 0


def test_abdominal_gas_is_discarded_but_two_separate_lungs_are_kept():
    """Una bolsa grande (pulmón), otra comparable (el otro pulmón) y una
    chica (gas digestivo): se quedan las dos primeras."""
    mask = np.zeros((60, 40, 40), bool)
    mask[5:25, 5:35, 5:35] = True    # 18 000 vóxeles
    mask[30:48, 5:35, 5:35] = True   # 16 200: el otro pulmón
    mask[52:56, 10:20, 10:20] = True  # 400: gas
    kept = V._keep_relative(mask, V.LUNG_MIN_FRACTION_OF_LARGEST)
    assert kept[10, 10, 10] and kept[40, 10, 10] and not kept[54, 15, 15]


# --- Calidad de malla, contra casos de verdad conocida ---------------------

_CUBE_V = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0], [0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1]], float)
_CUBE_F = np.array([[0, 2, 1], [0, 3, 2], [4, 5, 6], [4, 6, 7], [0, 1, 5], [0, 5, 4],
                    [1, 2, 6], [1, 6, 5], [2, 3, 7], [2, 7, 6], [3, 0, 4], [3, 4, 7]])


def test_closed_cube_is_watertight_consistent_one_body_euler_two():
    q = V.mesh_quality(_CUBE_F)
    assert (q.watertight, q.winding_consistent, q.bodies, q.open_edges, q.euler) == (True, True, 1, 0, 2)
    assert V.mesh_stats(_CUBE_V, _CUBE_F)["volume_ml"] == pytest.approx(1e-3)


def test_cube_with_a_missing_face_is_open():
    q = V.mesh_quality(_CUBE_F[1:])
    assert not q.watertight and q.open_edges == 3


def test_flipped_face_breaks_winding_but_not_closure():
    f = _CUBE_F.copy()
    f[0] = f[0][::-1]
    q = V.mesh_quality(f)
    assert q.watertight and not q.winding_consistent


def test_two_separate_cubes_are_two_bodies():
    assert V.mesh_quality(np.vstack([_CUBE_F, _CUBE_F + 8])).bodies == 2


# --- UI ---------------------------------------------------------------------

def test_viewer_marks_volume_unreliable_for_an_open_mesh():
    from streamlit.testing.v1 import AppTest

    def _script():
        import numpy as np
        import streamlit as st
        from app.supermodules.model3d import pages
        from src.imaging import volume3d as V

        f = np.array([[0, 2, 1], [0, 3, 2], [4, 5, 6], [4, 6, 7], [0, 1, 5], [0, 5, 4],
                      [1, 2, 6], [1, 6, 5], [2, 3, 7], [2, 7, 6], [3, 0, 4]])  # cubo sin una cara
        st.write(pages._quality_caption(V.mesh_quality(f)))

    at = AppTest.from_function(_script)
    at.run(timeout=60)
    assert at.exception == []
    assert "Malla abierta ✗ (3 aristas sin cerrar" in " ".join(m.value for m in at.markdown)
