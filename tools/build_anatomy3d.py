"""Construye las mallas 3D reales que usa la app (2026-10-21).

No se ejecuta en la app: genera, una sola vez, los archivos compactos de
`data/anatomy3d/` a partir de datos abiertos y reales:

1. Cuerpo: una tomografía real de cuerpo completo del TotalSegmentator
   dataset v2 (sujeto s1397, CC BY 4.0) con sus 117 segmentaciones
   anatómicas (Wasserthal et al., Radiology: AI 2023).
2. Cabeza: la superficie del cuero cabelludo de fsaverage (FreeSurfer) que
   distribuye MNE-Python, con las posiciones 10-20 estándar de MNE
   calculadas sobre esa misma cabeza.
3. Cerebro: la plantilla MNI ICBM 152 2009a (Fonov et al. 2009/2011), la
   que trae `nilearn` en su paquete (sustancia gris + blanca).

Uso (las rutas se pasan como argumentos; nada se descarga aquí):

    python tools/build_anatomy3d.py body --ts-dir RUTA/s1397 --out data/anatomy3d/body_ts_s1397.npz
    python tools/build_anatomy3d.py landmarks --ts-dir RUTA/s1397 --npz data/anatomy3d/body_ts_s1397.npz
    python tools/build_anatomy3d.py head --mni-dir RUTA/mni --montage RUTA/fsaverage_1020.tsv \
        --head-fif RUTA/fsaverage-head.fif --out data/anatomy3d/head_mni152.npz

Necesita (solo para construir, no para usar la app): nibabel, scikit-image,
scipy, fast-simplification y, para la cabeza, mne.

Formato de salida (npz sin pickle): por cada estructura `k`, `k__v` (int16,
vértices en mm relativos a `origin`, escala `VERTEX_SCALE_MM`) y `k__f`
(uint16, triángulos); más `meta` (JSON) con etiquetas, sistema y volumen
medido sobre la segmentación.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

VERTEX_SCALE_MM = 0.05  # 1 unidad int16 = 0.05 mm  (rango ±1638 mm)


# ─────────────────────────────────────────────────────────────────────────
# Malla a partir de una máscara
# ─────────────────────────────────────────────────────────────────────────

def _largest_components(mask: np.ndarray, keep: int) -> np.ndarray:
    from scipy import ndimage as ndi

    labels, n = ndi.label(mask)
    if n <= keep:
        return mask
    sizes = ndi.sum(mask, labels, index=np.arange(1, n + 1))
    order = np.argsort(sizes)[::-1][:keep] + 1
    return np.isin(labels, order)


def surface_from_mask(
    mask: np.ndarray,
    affine: np.ndarray,
    *,
    sigma: float,
    target_faces: int,
    keep_components: Optional[int] = None,
    min_component_voxels: int = 0,
) -> Tuple[np.ndarray, np.ndarray]:
    """Superficie (vértices en mm del mundo, triángulos) de una máscara 3D.

    La máscara se suaviza con un filtro gaussiano antes de marching cubes
    (sin escalones de vóxel, sin encoger estructuras finas con sigma < 1) y
    se simplifica con decimación cuádrica hasta `target_faces` triángulos.
    """
    from scipy import ndimage as ndi
    from skimage import measure
    import fast_simplification

    if not mask.any():
        raise ValueError("máscara vacía")
    if keep_components:
        mask = _largest_components(mask, keep_components)
    if min_component_voxels:
        labels, n = ndi.label(mask)
        if n > 1:
            sizes = ndi.sum(mask, labels, index=np.arange(1, n + 1))
            mask = np.isin(labels, np.nonzero(sizes >= min_component_voxels)[0] + 1)

    # Recorte a la caja que contiene la máscara (+ margen): mucho más rápido.
    idx = np.argwhere(mask)
    lo = np.maximum(idx.min(axis=0) - 4, 0)
    hi = np.minimum(idx.max(axis=0) + 5, mask.shape)
    sub = mask[lo[0]:hi[0], lo[1]:hi[1], lo[2]:hi[2]]
    # Relleno de ceros: cierra la superficie donde la estructura toca el
    # borde del campo de la TC (queda una "tapa" plana, como el corte real).
    sub = np.pad(sub, 2)
    field = sub.astype(np.float32)
    if sigma > 0:
        field = ndi.gaussian_filter(field, sigma)
    verts, faces, _normals, _values = measure.marching_cubes(field, level=0.5, allow_degenerate=False)
    verts = verts - 2 + lo  # deshace relleno y recorte -> índices de vóxel
    world = verts @ affine[:3, :3].T + affine[:3, 3]
    if np.linalg.det(affine[:3, :3]) < 0:
        faces = faces[:, ::-1]
    world = world.astype(np.float32)
    faces = faces.astype(np.int32)
    if target_faces and faces.shape[0] > target_faces:
        reduction = 1.0 - target_faces / faces.shape[0]
        world, faces = fast_simplification.simplify(world, faces, target_reduction=reduction)
    world, faces = _drop_unused_vertices(np.asarray(world, np.float32), np.asarray(faces, np.int64))
    # Normales hacia fuera (volumen con signo positivo): necesario para el
    # sombreado de "vidrio" de la piel y para luces consistentes.
    if signed_volume(world, faces) < 0:
        faces = faces[:, ::-1]
    return world, faces


def signed_volume(verts: np.ndarray, faces: np.ndarray) -> float:
    v0, v1, v2 = (verts[faces[:, i]].astype(np.float64) for i in range(3))
    return float(np.einsum("ij,ij->i", v0, np.cross(v1, v2)).sum() / 6.0)


def _drop_unused_vertices(verts: np.ndarray, faces: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    used = np.unique(faces)
    remap = -np.ones(verts.shape[0], dtype=np.int64)
    remap[used] = np.arange(used.size)
    return verts[used], remap[faces]


def taubin_smooth(verts: np.ndarray, faces: np.ndarray, iterations: int = 6,
                  lam: float = 0.5, mu: float = -0.53) -> np.ndarray:
    """Suavizado de Taubin (no encoge la malla, a diferencia de Laplace)."""
    from scipy import sparse

    n = verts.shape[0]
    e = np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]])
    e = np.concatenate([e, e[:, ::-1]])
    adj = sparse.coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(n, n)).tocsr()
    adj.data[:] = 1.0
    deg = np.asarray(adj.sum(axis=1)).ravel()
    deg[deg == 0] = 1.0
    v = verts.astype(np.float64)
    for _ in range(iterations):
        for factor in (lam, mu):
            avg = adj @ v / deg[:, None]
            v = v + factor * (avg - v)
    return v.astype(np.float32)


def loop_subdivide(verts: np.ndarray, faces: np.ndarray, iterations: int = 1) -> Tuple[np.ndarray, np.ndarray]:
    """Subdivisión de Loop (1987): cada triángulo -> 4, con los pesos de
    Loop/Warren; suaviza una malla gruesa sin cambiar su forma."""
    v = np.asarray(verts, dtype=np.float64)
    f = np.asarray(faces, dtype=np.int64)
    for _ in range(iterations):
        n = v.shape[0]
        edges = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
        key = np.sort(edges, axis=1)
        uniq, inv = np.unique(key, axis=0, return_inverse=True)
        inv = inv.ravel()
        m = f.shape[0]
        # vértice opuesto a cada arista en cada cara
        opp = np.concatenate([f[:, 2], f[:, 0], f[:, 1]])
        e_pts = np.zeros((uniq.shape[0], 3))
        cnt = np.bincount(inv, minlength=uniq.shape[0])
        np.add.at(e_pts, inv, v[opp] * (1.0 / 8.0))
        interior = cnt == 2
        e_pts[interior] += (v[uniq[interior, 0]] + v[uniq[interior, 1]]) * (3.0 / 8.0)
        e_pts[~interior] = (v[uniq[~interior, 0]] + v[uniq[~interior, 1]]) / 2.0
        # vértices originales: v' = (1 - k·β) v + β Σ vecinos
        nb_sum = np.zeros((n, 3))
        deg = np.zeros(n)
        np.add.at(nb_sum, uniq[:, 0], v[uniq[:, 1]])
        np.add.at(nb_sum, uniq[:, 1], v[uniq[:, 0]])
        np.add.at(deg, uniq[:, 0], 1)
        np.add.at(deg, uniq[:, 1], 1)
        k = np.maximum(deg, 1)
        beta = np.where(k == 3, 3.0 / 16.0, 3.0 / (8.0 * k))
        v_new = (1 - k * beta)[:, None] * v + beta[:, None] * nb_sum
        e_idx = n + inv.reshape(3, m).T  # (m, 3): aristas 01, 12, 20
        a, b, c = f[:, 0], f[:, 1], f[:, 2]
        ab, bc, ca = e_idx[:, 0], e_idx[:, 1], e_idx[:, 2]
        f = np.concatenate([
            np.stack([a, ab, ca], 1), np.stack([b, bc, ab], 1),
            np.stack([c, ca, bc], 1), np.stack([ab, bc, ca], 1)])
        v = np.concatenate([v_new, e_pts])
    return v.astype(np.float32), f


def quantize(verts: np.ndarray, origin: np.ndarray) -> np.ndarray:
    q = np.round((verts - origin) / VERTEX_SCALE_MM)
    if np.abs(q).max() >= 32767:
        raise ValueError("vértices fuera del rango int16; revisa `origin`")
    return q.astype(np.int16)


# ─────────────────────────────────────────────────────────────────────────
# Cuerpo: TotalSegmentator s1397
# ─────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Part:
    key: str
    label: str           # nombre en español para la interfaz
    system: str          # agrupa capas en la interfaz
    sources: Tuple[str, ...]
    faces: int
    sigma: float = 0.8
    keep: Optional[int] = None   # n.º de componentes conexas a conservar
    min_voxels: int = 30
    # Estructuras vecinas que se restan (dilatadas 1 vóxel): deja una
    # separación mínima donde dos superficies coincidirían (p. ej., la vena
    # cava al entrar en el corazón), que si no se verían "pelear" al renderizar.
    avoid: Tuple[str, ...] = ()
    # (estructura, vóxeles): conserva solo lo que está a esa distancia de la
    # estructura (p. ej., las raíces de los grandes vasos junto al corazón).
    within: Optional[Tuple[Tuple[str, ...], int]] = None


def _r(side: str, *names: str) -> Tuple[str, ...]:
    return tuple(f"{n}_{side}" for n in names)


VERTEBRAE = tuple(f"vertebrae_{v}" for v in (
    [f"C{i}" for i in range(1, 8)] + [f"T{i}" for i in range(1, 13)] + [f"L{i}" for i in range(1, 6)]
))
RIBS = tuple(f"rib_{s}_{i}" for s in ("left", "right") for i in range(1, 13))

BODY_PARTS: Tuple[Part, ...] = (
    # Esqueleto
    Part("skull", "Cráneo", "skeleton", ("skull",), 8000, sigma=0.7),
    Part("spine", "Columna vertebral (C1–L5)", "skeleton", VERTEBRAE, 11000, sigma=0.7),
    Part("ribs", "Costillas", "skeleton", RIBS, 10000, sigma=0.6),
    Part("sternum", "Esternón", "skeleton", ("sternum",), 1500, sigma=0.7, keep=1),
    Part("costal_cartilages", "Cartílagos costales", "skeleton", ("costal_cartilages",), 3500, sigma=0.7),
    Part("shoulder_girdle", "Clavículas y escápulas", "skeleton",
         ("clavicula_left", "clavicula_right", "scapula_left", "scapula_right"), 5000, sigma=0.7),
    Part("humeri", "Húmeros", "skeleton", ("humerus_left", "humerus_right"), 2600, sigma=0.7, keep=2),
    Part("pelvis", "Pelvis y sacro", "skeleton", ("hip_left", "hip_right", "sacrum", "vertebrae_S1"), 8000, sigma=0.7),
    Part("femurs", "Fémures (parte proximal)", "skeleton", ("femur_left", "femur_right"), 2600, sigma=0.7, keep=2),
    # Corazón y vasos
    Part("heart", "Corazón", "circulatory", ("heart", "atrial_appendage_left"), 7000, sigma=1.0, keep=1),
    Part("arteries", "Aorta y arterias principales", "circulatory",
         ("aorta", "brachiocephalic_trunk", "common_carotid_artery_left", "common_carotid_artery_right",
          "subclavian_artery_left", "subclavian_artery_right", "iliac_artery_left", "iliac_artery_right"),
         5000, sigma=0.8, avoid=("heart", "atrial_appendage_left")),
    Part("veins", "Venas cavas y venas principales", "circulatory",
         ("superior_vena_cava", "inferior_vena_cava", "brachiocephalic_vein_left", "brachiocephalic_vein_right",
          "iliac_vena_left", "iliac_vena_right", "portal_vein_and_splenic_vein"), 4000, sigma=0.8,
         avoid=("heart", "atrial_appendage_left", "liver")),
    Part("pulmonary_veins", "Venas pulmonares", "circulatory", ("pulmonary_vein",), 1500, sigma=0.8,
         avoid=("heart", "atrial_appendage_left")),
    # Raíces de los grandes vasos (hasta 2.5 cm del corazón): para la vista
    # del corazón aislado, con los vasos cortados de forma natural.
    Part("artery_roots", "Raíz de la aorta y arterias", "heart_detail",
         ("aorta", "brachiocephalic_trunk"), 1600, sigma=0.8, keep=1,
         avoid=("heart", "atrial_appendage_left"), within=(("heart", "atrial_appendage_left"), 17)),
    Part("vein_roots", "Desembocadura de las venas cavas y pulmonares", "heart_detail",
         ("superior_vena_cava", "inferior_vena_cava", "pulmonary_vein"), 1400, sigma=0.8,
         avoid=("heart", "atrial_appendage_left"), within=(("heart", "atrial_appendage_left"), 17)),
    # Respiratorio
    Part("lung_right", "Pulmón derecho (3 lóbulos)", "respiratory",
         ("lung_upper_lobe_right", "lung_middle_lobe_right", "lung_lower_lobe_right"), 7000, sigma=1.0, keep=1),
    Part("lung_left", "Pulmón izquierdo (2 lóbulos)", "respiratory",
         ("lung_upper_lobe_left", "lung_lower_lobe_left"), 6500, sigma=1.0, keep=1),
    Part("trachea", "Tráquea", "respiratory", ("trachea",), 1200, sigma=0.8, keep=1),
    # Nervioso
    Part("brain", "Encéfalo", "nervous", ("brain",), 7000, sigma=1.0, keep=1),
    Part("spinal_cord", "Médula espinal", "nervous", ("spinal_cord",), 2000, sigma=0.8, keep=1),
    # Músculos
    Part("back_muscles", "Músculos erectores de la columna", "muscular",
         ("autochthon_left", "autochthon_right"), 5000, sigma=1.0, keep=2),
    Part("iliopsoas", "Iliopsoas", "muscular", ("iliopsoas_left", "iliopsoas_right"), 3000, sigma=1.0, keep=2),
    Part("gluteals", "Glúteos (mayor, medio, menor)", "muscular",
         _r("left", "gluteus_maximus", "gluteus_medius", "gluteus_minimus")
         + _r("right", "gluteus_maximus", "gluteus_medius", "gluteus_minimus"), 6000, sigma=1.0),
    # Abdomen y pelvis
    Part("liver", "Hígado", "abdominal", ("liver",), 4000, sigma=1.0, keep=1),
    Part("gallbladder", "Vesícula biliar", "abdominal", ("gallbladder",), 700, sigma=1.0, keep=1),
    Part("stomach", "Estómago", "abdominal", ("stomach",), 2600, sigma=1.0, keep=1),
    Part("esophagus", "Esófago", "abdominal", ("esophagus",), 1000, sigma=0.8, keep=1),
    Part("duodenum", "Duodeno", "abdominal", ("duodenum",), 1000, sigma=0.9),
    Part("small_bowel", "Intestino delgado", "abdominal", ("small_bowel",), 4000, sigma=1.0),
    Part("colon", "Colon", "abdominal", ("colon",), 4000, sigma=1.0),
    Part("pancreas", "Páncreas", "abdominal", ("pancreas",), 1000, sigma=0.9, keep=1),
    Part("spleen", "Bazo", "abdominal", ("spleen",), 1300, sigma=1.0, keep=1),
    Part("kidneys", "Riñones", "abdominal", ("kidney_left", "kidney_right"), 2400, sigma=1.0, keep=2),
    Part("adrenals", "Glándulas suprarrenales", "abdominal", ("adrenal_gland_left", "adrenal_gland_right"), 400,
         sigma=0.7),
    Part("bladder", "Vejiga", "abdominal", ("urinary_bladder",), 1300, sigma=1.0, keep=1),
    Part("prostate", "Próstata", "abdominal", ("prostate",), 500, sigma=0.9, keep=1),
    Part("thyroid", "Tiroides", "abdominal", ("thyroid_gland",), 700, sigma=0.8),
)

SKIN_FACES = 18000


def _load_mask(seg_dir: str, names: Iterable[str], shape) -> Tuple[np.ndarray, List[str]]:
    import nibabel as nib

    mask = np.zeros(shape, dtype=bool)
    used = []
    for name in names:
        path = os.path.join(seg_dir, f"{name}.nii.gz")
        if not os.path.exists(path):
            print(f"  (falta {name})", file=sys.stderr)
            continue
        a = np.asanyarray(nib.load(path).dataobj) > 0
        if a.any():
            mask |= a
            used.append(name)
    return mask, used


def _skin_mask(ct: np.ndarray) -> np.ndarray:
    """Cuerpo completo (sin camilla) a partir de la TC: HU > -350, apertura
    morfológica para separar la camilla, componente mayor y relleno de
    huecos (pulmones y vía aérea) corte a corte."""
    from scipy import ndimage as ndi

    body = ct > -350
    body = ndi.binary_opening(body, structure=ndi.generate_binary_structure(3, 1), iterations=2)
    body = _largest_components(body, 1)
    for z in range(body.shape[2]):
        body[:, :, z] = ndi.binary_fill_holes(body[:, :, z])
    return body


def build_body(ts_dir: str, out: str) -> None:
    import nibabel as nib

    t0 = time.time()
    ct_img = nib.load(os.path.join(ts_dir, "ct.nii.gz"))
    affine = ct_img.affine
    shape = ct_img.shape
    voxel_ml = float(abs(np.linalg.det(affine[:3, :3]))) / 1000.0
    seg_dir = os.path.join(ts_dir, "segmentations")

    arrays: Dict[str, np.ndarray] = {}
    parts_meta = []
    all_verts = []
    meshes = {}
    for part in BODY_PARTS:
        mask, used = _load_mask(seg_dir, part.sources, shape)
        if not used:
            print(f"- {part.key}: sin datos, se omite")
            continue
        volume_ml = float(mask.sum()) * voxel_ml
        if part.avoid:
            from scipy import ndimage as ndi

            other, _ = _load_mask(seg_dir, part.avoid, shape)
            mask &= ~ndi.binary_dilation(other, iterations=1)
        if part.within:
            from scipy import ndimage as ndi

            ref, _ = _load_mask(seg_dir, part.within[0], shape)
            dist = ndi.distance_transform_edt(~ref)
            mask &= dist <= part.within[1]
        verts, faces = surface_from_mask(mask, affine, sigma=part.sigma, target_faces=part.faces,
                                         keep_components=part.keep, min_component_voxels=part.min_voxels)
        verts = taubin_smooth(verts, faces, iterations=4)
        meshes[part.key] = (verts, faces)
        all_verts.append(verts)
        parts_meta.append({
            "key": part.key, "label": part.label, "system": part.system,
            "sources": used, "volume_ml": round(volume_ml, 1),
            "faces": int(faces.shape[0]), "vertices": int(verts.shape[0]),
        })
        print(f"- {part.key:18s} {faces.shape[0]:6d} triángulos  {volume_ml:8.1f} mL  ({time.time() - t0:.0f} s)")

    # Piel: TC a 3 mm (la superficie externa no necesita más detalle).
    ct = np.asanyarray(ct_img.dataobj).astype(np.int16)
    ct3 = ct[::2, ::2, ::2]
    aff3 = affine.copy()
    aff3[:3, :3] = affine[:3, :3] * 2
    skin = _skin_mask(ct3)
    skin_volume_l = float(skin.sum()) * voxel_ml * 8 / 1000.0
    verts, faces = surface_from_mask(skin, aff3, sigma=1.0, target_faces=SKIN_FACES, keep_components=1)
    verts = taubin_smooth(verts, faces, iterations=6)
    meshes["skin"] = (verts, faces)
    all_verts.append(verts)
    parts_meta.append({
        "key": "skin", "label": "Piel (superficie corporal)", "system": "skin",
        "sources": ["ct.nii.gz (HU > -350)"], "volume_ml": round(skin_volume_l * 1000.0, 1),
        "faces": int(faces.shape[0]), "vertices": int(verts.shape[0]),
    })
    print(f"- skin               {faces.shape[0]:6d} triángulos")

    stacked = np.concatenate(all_verts)
    origin = np.round((stacked.min(axis=0) + stacked.max(axis=0)) / 2.0, 1).astype(np.float32)
    for key, (verts, faces) in meshes.items():
        if verts.shape[0] >= 65535:
            raise ValueError(f"{key}: demasiados vértices para uint16")
        arrays[f"{key}__v"] = quantize(verts, origin)
        arrays[f"{key}__f"] = faces.astype(np.uint16)

    meta = {
        "kind": "body",
        "title": "Tomografía real de cuerpo completo (TotalSegmentator, sujeto s1397)",
        "subject": "s1397",
        "coordinates": "RAS+ en mm (x: izquierda→derecha del paciente, y: posterior→anterior, z: inferior→superior), relativos a origin",
        "origin_mm": origin.tolist(),
        "vertex_scale_mm": VERTEX_SCALE_MM,
        "voxel_mm": [float(z) for z in ct_img.header.get_zooms()[:3]],
        "ct_shape": [int(s) for s in shape],
        "parts": parts_meta,
        "source": {
            "dataset": "Dataset with segmentations of 117 important anatomical structures in 1228 CT images (v2.0.1)",
            "author": "Jakob Wasserthal (University Hospital Basel)",
            "doi": "10.5281/zenodo.10047292",
            "paper": "Wasserthal J, et al. TotalSegmentator: Robust Segmentation of 104 Anatomic Structures in CT "
                     "Images. Radiology: Artificial Intelligence 2023;5(5):e230024. doi:10.1148/ryai.230024",
            "license": "CC BY 4.0",
            "changes": "Superficies obtenidas con marching cubes sobre las máscaras suavizadas, decimadas y "
                       "suavizadas (Taubin); piel a 3 mm sin camilla. Volúmenes medidos sobre las máscaras.",
        },
        "built": time.strftime("%Y-%m-%d"),
    }
    arrays["meta"] = np.frombuffer(json.dumps(meta, ensure_ascii=False).encode("utf-8"), dtype=np.uint8)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    np.savez_compressed(out, **arrays)
    add_landmarks(ts_dir, out)
    print(f"→ {out}  {os.path.getsize(out) / 1e6:.2f} MB  ({time.time() - t0:.0f} s)")


# ─────────────────────────────────────────────────────────────────────────
# Derivaciones precordiales V1-V6 sobre esta TC
# ─────────────────────────────────────────────────────────────────────────

PRECORDIAL_RULES = {
    "V1": "4.º espacio intercostal, borde esternal derecho",
    "V2": "4.º espacio intercostal, borde esternal izquierdo",
    "V3": "a medio camino entre V2 y V4",
    "V4": "5.º espacio intercostal, línea medioclavicular izquierda",
    "V5": "línea axilar anterior izquierda, a la altura de V4",
    "V6": "línea axilar media izquierda, a la altura de V4",
}


def _bands(column: np.ndarray, min_gap: int = 1) -> List[Tuple[int, int]]:
    """Tramos consecutivos (inicio, fin) donde `column` es verdadero,
    ordenados de arriba (k alto) hacia abajo."""
    out, start = [], None
    for k, v in enumerate(column):
        if v and start is None:
            start = k
        if not v and start is not None:
            out.append((start, k - 1))
            start = None
    if start is not None:
        out.append((start, len(column) - 1))
    merged: List[Tuple[int, int]] = []
    for a, b in out:
        if merged and a - merged[-1][1] - 1 < min_gap:
            merged[-1] = (merged[-1][0], b)
        else:
            merged.append((a, b))
    return merged[::-1]


def precordial_landmarks(ts_dir: str) -> Dict[str, Tuple[np.ndarray, np.ndarray]]:
    """V1-V6 (mm RAS sobre la piel, normal hacia fuera) con las reglas
    estándar de colocación, medidas sobre ESTA tomografía:

    - Espacios intercostales: en la cara anterior de la caja torácica se
      cuentan, de arriba abajo, los cartílagos costales que llegan al borde
      del esternón (1.º, 2.º, ...); el 4.º espacio queda entre el cartílago
      4 y el 5. En la línea medioclavicular (punto medio de la clavícula
      izquierda) las costillas 1-3 son hueso y los cartílagos 4, 5, 6...
      siguen debajo; el 5.º espacio queda entre el 5 y el 6.
    - Cada punto se lleva hacia delante hasta la piel (HU > -350).
    - V5/V6: en el corte axial de V4, líneas axilar anterior (normal de la
      piel a 45° entre anterior e izquierda) y media (punto más lateral).

    Son posiciones aproximadas (la colocación real se palpa)."""
    import nibabel as nib
    from scipy import ndimage as ndi

    seg = os.path.join(ts_dir, "segmentations")
    ct_img = nib.load(os.path.join(ts_dir, "ct.nii.gz"))
    aff = ct_img.affine
    if nib.aff2axcodes(aff) != ("R", "A", "S"):
        raise ValueError("se esperaba una TC en orientación RAS")
    shape = ct_img.shape

    def mask(name):
        return np.asanyarray(nib.load(os.path.join(seg, f"{name}.nii.gz")).dataobj) > 0

    sternum = mask("sternum")
    cart = mask("costal_cartilages")
    ribs = np.zeros(shape, dtype=np.int16)
    for i in range(1, 13):
        ribs[mask(f"rib_left_{i}")] = i
    body = np.asanyarray(ct_img.dataobj) > -350
    body = ndi.binary_opening(body, iterations=1)

    def world(i, j, k):
        return np.array([i, j, k], dtype=float) @ aff[:3, :3].T + aff[:3, 3]

    # Cara anterior de la caja: para cada (i, k), la estructura más anterior.
    labels = np.zeros(shape, dtype=np.int16)
    labels[ribs > 0] = ribs[ribs > 0]
    labels[cart] = 50
    labels[sternum] = 60
    has = labels > 0
    jmax = np.where(has, np.arange(shape[1])[None, :, None], -1).max(axis=1)
    front = np.take_along_axis(labels, np.clip(jmax, 0, None)[:, None, :], axis=1)[:, 0, :]
    front[jmax < 0] = 0

    st = np.argwhere(sternum)

    def sternal_border(k: int, side: str) -> int:
        sl = st[st[:, 2] == k]
        return int(sl[:, 0].min()) if side == "left" else int(sl[:, 0].max())

    def parasternal_ics(side: str, after_band: int) -> Tuple[float, int]:
        """k del espacio intercostal entre el cartílago `after_band` y el
        siguiente, siguiendo el borde del esternón corte a corte: en una
        franja de 15 mm por fuera del borde se cuentan los vóxeles de
        cartílago; cada cartílago es un tramo con cuenta > 6 y los espacios
        son los valles entre tramos. Devuelve (k, columna del borde)."""
        ks = np.unique(st[:, 2])
        counts, cols = [], {}
        for k in ks:
            border = sternal_border(int(k), side)
            cols[int(k)] = border
            xs = slice(max(border - 10, 0), border) if side == "left" else slice(border + 1, border + 11)
            counts.append(int(cart[xs, :, k].sum()))
        profile = np.zeros(int(ks.max()) + 1, dtype=bool)
        profile[ks] = np.asarray(counts) > 6
        bands = _bands(profile, min_gap=1)
        if len(bands) < after_band + 1:
            raise ValueError(f"borde esternal {side}: solo {len(bands)} cartílagos")
        upper, lower = bands[after_band - 1], bands[after_band]
        k = (upper[0] + lower[1]) / 2.0
        return k, cols[int(round(k))] if int(round(k)) in cols else cols[min(cols, key=lambda c: abs(c - k))]

    k_v2, i_left = parasternal_ics("left", 4)
    k_v1, i_right = parasternal_ics("right", 4)

    # Línea medioclavicular izquierda: punto medio de la clavícula en x.
    clav = np.argwhere(mask("clavicula_left"))
    medial = clav[clav[:, 0] >= np.percentile(clav[:, 0], 99)][:, 0].mean()
    lateral = clav[clav[:, 0] <= np.percentile(clav[:, 0], 1)][:, 0].mean()
    i_mcl = int(round((medial + lateral) / 2.0))
    col = front[i_mcl]
    # Bajo la clavícula, en la LMC: costillas óseas 1-3 y luego cartílagos 4, 5, 6.
    bands = _bands(col == 50, min_gap=2)
    rib3 = np.nonzero(col == 3)[0]
    if rib3.size == 0:
        raise ValueError("no se encontró la 3.ª costilla en la línea medioclavicular")
    below = [b for b in bands if b[1] < rib3.min()]
    if len(below) < 3:
        raise ValueError("faltan cartílagos bajo la 3.ª costilla en la línea medioclavicular")
    c5, c6 = below[1], below[2]          # below[0] = 4.º cartílago
    k_v4 = (c5[0] + c6[1]) / 2.0
    print(f"  4.º EIC: k={k_v1:.1f} (der.), k={k_v2:.1f} (izq.); LMC i={i_mcl}; 5.º EIC en LMC k={k_v4:.1f}; "
          f"cartílagos bajo la 3.ª costilla en LMC: {below[:4]}")

    def to_skin(i: float, k: float, j_start: Optional[int] = None) -> Tuple[np.ndarray, np.ndarray]:
        ii, kk = int(round(i)), int(round(k))
        # En el espacio intercostal no hay hueso ni cartílago en (i, k): se
        # parte de la cara anterior de los cartílagos vecinos (±12 mm).
        j = int(jmax[ii, max(kk - 8, 0):kk + 9].max()) if j_start is None else j_start
        if j < 0:
            raise ValueError(f"sin pared torácica cerca de i={ii}, k={kk}")
        while j < shape[1] - 1 and body[ii, j + 1, kk]:
            j += 1
        return world(ii, j + 0.5, kk), np.array([0.0, 1.0, 0.0])

    out: Dict[str, Tuple[np.ndarray, np.ndarray]] = {}
    out["V1"] = to_skin(i_right + 3, k_v1)
    out["V2"] = to_skin(i_left - 3, k_v2)
    out["V4"] = to_skin(i_mcl, k_v4)
    mid = (out["V2"][0] + out["V4"][0]) / 2.0
    ijk_mid = np.linalg.solve(aff[:3, :3], mid - aff[:3, 3])
    out["V3"] = to_skin(ijk_mid[0], ijk_mid[2])

    # Contorno del corte axial de V4 (lado izquierdo = i menor que la línea media).
    kk = int(round(k_v4))
    sl = ndi.binary_fill_holes(body[:, :, kk])
    sl = _largest_components(sl, 1)
    edge = sl & ~ndi.binary_erosion(sl)
    pts = np.argwhere(edge)
    i_center = st[:, 0].mean()
    left = pts[pts[:, 0] < i_center]
    # normal hacia fuera aproximada: gradiente de la distancia al interior
    dist = ndi.distance_transform_edt(sl)
    gi, gj = np.gradient(ndi.gaussian_filter(dist, 2.0))
    normals = -np.stack([gi[left[:, 0], left[:, 1]], gj[left[:, 0], left[:, 1]]], axis=1)
    normals /= np.linalg.norm(normals, axis=1, keepdims=True) + 1e-9
    ang = np.degrees(np.arctan2(normals[:, 1], -normals[:, 0]))  # 0° = izquierda pura, 90° = anterior pura
    j_v4 = np.linalg.solve(aff[:3, :3], out["V4"][0] - aff[:3, 3])[1]
    lat = left[(np.abs(ang) < 12) & (left[:, 1] < j_v4)]
    if lat.size == 0:
        raise ValueError("no se encontró la línea axilar media")
    v6 = lat[np.argmin(lat[:, 0])]
    aal = left[(np.abs(ang - 45) < 8) & (left[:, 1] > v6[1]) & (left[:, 1] < j_v4)]
    if aal.size == 0:
        raise ValueError("no se encontró la línea axilar anterior")
    v5 = aal[np.argmin(aal[:, 0])]

    def flat_normal(deg: float) -> np.ndarray:
        r = np.radians(deg)
        n_vox = np.array([-np.cos(r), np.sin(r), 0.0])  # i (der.), j (ant.)
        n = aff[:3, :3] @ n_vox
        return n / np.linalg.norm(n)

    out["V5"] = (world(v5[0] - 0.5, v5[1], kk), flat_normal(45.0))
    out["V6"] = (world(v6[0] - 0.5, v6[1], kk), flat_normal(0.0))
    return {name: out[name] for name in ("V1", "V2", "V3", "V4", "V5", "V6")}


def add_landmarks(ts_dir: str, npz_path: str) -> None:
    """Agrega V1-V6 al archivo del cuerpo (sin reconstruir las mallas)."""
    lm = precordial_landmarks(ts_dir)
    with np.load(npz_path, allow_pickle=False) as z:
        arrays = {k: z[k] for k in z.files}
    meta = json.loads(bytes(arrays["meta"]).decode("utf-8"))
    origin = np.asarray(meta["origin_mm"], dtype=np.float32)
    names = list(lm)
    arrays["landmarks__xyz"] = np.stack([lm[n][0] - origin for n in names]).astype(np.float32)
    arrays["landmarks__normal"] = np.stack([lm[n][1] for n in names]).astype(np.float32)
    meta["landmarks"] = [{"name": n, "rule": PRECORDIAL_RULES[n]} for n in names]
    # Centro de cada vértebra (mm relativos a origin): niveles para rotular la
    # columna y la médula (p. ej., la salida simpática T1-L2).
    import nibabel as nib

    seg = os.path.join(ts_dir, "segmentations")
    aff = nib.load(os.path.join(ts_dir, "ct.nii.gz")).affine
    levels = {}
    for name in VERTEBRAE + ("vertebrae_S1",):
        path = os.path.join(seg, f"{name}.nii.gz")
        if os.path.exists(path):
            ijk = np.argwhere(np.asanyarray(nib.load(path).dataobj) > 0)
            if ijk.size:
                c = ijk.mean(axis=0) @ aff[:3, :3].T + aff[:3, 3] - origin
                levels[name.replace("vertebrae_", "")] = [round(float(x), 1) for x in c]
    meta["vertebrae"] = levels
    meta["landmarks_note"] = ("Posiciones aproximadas de V1-V6 calculadas sobre esta TC con las reglas "
                              "estándar (cartílagos costales contados en el borde esternal y en la línea "
                              "medioclavicular). La colocación real se hace por palpación.")
    arrays["meta"] = np.frombuffer(json.dumps(meta, ensure_ascii=False).encode("utf-8"), dtype=np.uint8)
    np.savez_compressed(npz_path, **arrays)
    for n in names:
        p = lm[n][0]
        print(f"- {n}: ({p[0]:7.1f}, {p[1]:7.1f}, {p[2]:7.1f}) mm  ({PRECORDIAL_RULES[n]})")


# ─────────────────────────────────────────────────────────────────────────
# Cabeza y cerebro: MNI ICBM 152 2009a + 10-20
# ─────────────────────────────────────────────────────────────────────────

FIDUCIALS = {"NAS", "LPA", "RPA"}


def _read_montage(path: str) -> Tuple[List[str], np.ndarray]:
    names, pos = [], []
    with open(path, encoding="utf-8") as fh:
        header = fh.readline().strip().split("\t")
        if header[:4] != ["label", "x", "y", "z"]:
            raise ValueError(f"cabecera inesperada en {path}: {header}")
        for line in fh:
            parts = line.strip().split("\t")
            if len(parts) < 4:
                continue
            names.append(parts[0])
            pos.append([float(v) for v in parts[1:4]])
    return names, np.asarray(pos, dtype=np.float64)


def _project_to_surface(points: np.ndarray, verts: np.ndarray, center: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Proyecta cada punto sobre la superficie a lo largo del rayo desde
    `center`: el vértice de la malla con menor ángulo respecto al rayo
    (entre los más externos). Devuelve (posiciones, distancia original)."""
    dirs_v = verts - center
    r_v = np.linalg.norm(dirs_v, axis=1)
    unit_v = dirs_v / r_v[:, None]
    out, dist = [], []
    for p in points:
        d = p - center
        u = d / np.linalg.norm(d)
        cos = unit_v @ u
        cand = np.nonzero(cos > np.cos(np.radians(2.5)))[0]
        if cand.size == 0:
            cand = np.argsort(cos)[-20:]
        best = cand[np.argmax(r_v[cand])]
        out.append(verts[best])
        dist.append(float(np.linalg.norm(verts[best] - p)))
    return np.asarray(out, dtype=np.float32), np.asarray(dist)


def build_head(mni_dir: str, montage: str, head_fif: str, out: str) -> None:
    import nibabel as nib

    t0 = time.time()
    gm_img = nib.load(os.path.join(mni_dir, "mni_icbm152_gm_tal_nlin_sym_09a_converted.nii.gz"))
    wm_img = nib.load(os.path.join(mni_dir, "mni_icbm152_wm_tal_nlin_sym_09a_converted.nii.gz"))
    affine = gm_img.affine
    gm = np.asanyarray(gm_img.dataobj).astype(np.float32) / 255.0
    wm = np.asanyarray(wm_img.dataobj).astype(np.float32) / 255.0

    # Cabeza: la superficie del cuero cabelludo de fsaverage que trae
    # MNE-Python (fsaverage-head.fif, FreeSurfer). La plantilla MNI152 de
    # nilearn viene sin cráneo ni cuero cabelludo, así que no sirve para
    # esto; fsaverage es además la cabeza sobre la que MNE calculó las
    # posiciones 10-20 que se usan abajo.
    import mne

    surf = mne.read_bem_surfaces(head_fif, verbose=False)[0]
    scalp_v = surf["rr"].astype(np.float32) * 1000.0
    scalp_f = surf["tris"].astype(np.int64)
    # Dos niveles: ×1 (16 mil triángulos) para la figura interactiva y ×2
    # (65 mil) para los renders estáticos.
    lo_v, lo_f = loop_subdivide(scalp_v, scalp_f, iterations=1)
    if signed_volume(lo_v, lo_f) < 0:
        lo_f = lo_f[:, ::-1]
    scalp_v, scalp_f = loop_subdivide(scalp_v, scalp_f, iterations=2)
    if signed_volume(scalp_v, scalp_f) < 0:
        scalp_f = scalp_f[:, ::-1]
    print(f"- scalp  {scalp_f.shape[0]} triángulos (fsaverage, subdivisión de Loop x2) ({time.time() - t0:.0f} s)")

    # Cerebro: probabilidad de sustancia gris + blanca > 0.5.
    brain = (gm + wm) > 0.5
    brain = _largest_components(brain, 1)
    brain_ml = float(brain.sum()) * float(abs(np.linalg.det(affine[:3, :3]))) / 1000.0
    brain_v, brain_f = surface_from_mask(brain, affine, sigma=0.6, target_faces=36000, keep_components=1)
    brain_v = taubin_smooth(brain_v, brain_f, iterations=3)
    print(f"- brain  {brain_f.shape[0]} triángulos, {brain_ml:.0f} mL ({time.time() - t0:.0f} s)")

    names, pos_m = _read_montage(montage)
    keep = [i for i, n in enumerate(names) if n not in FIDUCIALS]
    names = [names[i] for i in keep]
    pos_mm = pos_m[keep] * 1000.0
    # Centro de proyección: punto medio entre preauriculares, elevado (centro de la bóveda).
    center = np.array([0.0, -18.0, 12.0])
    elec, dist = _project_to_surface(pos_mm, scalp_v, center)
    print("- electrodos 10-20: desplazamiento a la superficie "
          f"mediana {np.median(dist):.1f} mm, máximo {dist.max():.1f} mm")

    origin = np.zeros(3, dtype=np.float32)  # MNI ya está centrado (comisura anterior = 0)
    arrays = {
        "scalp__v": quantize(scalp_v, origin), "scalp__f": scalp_f.astype(np.uint16),
        "scalp_lo__v": quantize(lo_v, origin), "scalp_lo__f": lo_f.astype(np.uint16),
        "brain__v": quantize(brain_v, origin), "brain__f": brain_f.astype(np.uint16),
        "electrodes__xyz": np.round(elec, 2).astype(np.float32),
    }
    meta = {
        "kind": "head",
        "title": "Cabeza (fsaverage) y cerebro (MNI ICBM 152 2009a) con el sistema 10-20",
        "coordinates": "MNI/fsaverage (RAS+, mm); ambas plantillas comparten el espacio MNI con diferencias de pocos mm",
        "origin_mm": origin.tolist(),
        "vertex_scale_mm": VERTEX_SCALE_MM,
        "electrodes": names,
        "projection_offset_mm": {"median": round(float(np.median(dist)), 1), "max": round(float(dist.max()), 1)},
        "parts": [
            {"key": "scalp", "label": "Cabeza (fsaverage)", "system": "skin",
             "faces": int(scalp_f.shape[0]), "vertices": int(scalp_v.shape[0])},
            {"key": "scalp_lo", "label": "Cabeza (fsaverage, resolución interactiva)", "system": "skin_lo",
             "faces": int(lo_f.shape[0]), "vertices": int(lo_v.shape[0])},
            {"key": "brain", "label": "Cerebro (sustancia gris + blanca)", "system": "nervous",
             "faces": int(brain_f.shape[0]), "vertices": int(brain_v.shape[0]), "volume_ml": round(brain_ml, 1)},
        ],
        "source": {
            "head": "Superficie del cuero cabelludo de fsaverage (FreeSurfer; Fischl et al., NeuroImage 1999;9:195-207), "
                    "tal como la distribuye MNE-Python (mne/data/fsaverage/fsaverage-head.fif). Modificada: "
                    "subdividida (Loop x2). Licencia: FreeSurfer Software License Agreement (ver "
                    "data/anatomy3d/LICENSE-FreeSurfer.txt).",
            "template": "Cerebro: MNI ICBM 152 non-linear symmetric 2009a (versión incluida en nilearn)",
            "notice": "Copyright (C) 1993-2009 Louis Collins, McConnell Brain Imaging Centre, Montreal "
                      "Neurological Institute, McGill University. Permission to use, copy, modify, and "
                      "distribute this software and its documentation for any purpose and without fee is "
                      "hereby granted, provided that the above copyright notice appear in all copies. The "
                      "authors and McGill University make no representations about the suitability of this "
                      "software for any purpose. It is provided \"as is\" without express or implied warranty.",
            "papers": [
                "Fonov VS, Evans AC, McKinstry RC, Almli CR, Collins DL. Unbiased nonlinear average "
                "age-appropriate brain templates from birth to adulthood. NeuroImage 2009;47(S1):S102.",
                "Fonov VS, Evans AC, Botteron K, et al. Unbiased average age-appropriate atlases for "
                "pediatric studies. NeuroImage 2011;54(1):313-327.",
            ],
            "electrodes": "Posiciones 10-20 estándar de MNE-Python (fsaverage_1020.tsv, BSD-3-Clause), "
                          "calculadas por MNE sobre esta misma cabeza fsaverage; se proyectan radialmente "
                          "sobre la superficie subdividida.",
        },
        "built": time.strftime("%Y-%m-%d"),
    }
    arrays["meta"] = np.frombuffer(json.dumps(meta, ensure_ascii=False).encode("utf-8"), dtype=np.uint8)
    np.savez_compressed(out, **arrays)
    print(f"→ {out}  {os.path.getsize(out) / 1e6:.2f} MB  ({time.time() - t0:.0f} s)")


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("body")
    b.add_argument("--ts-dir", required=True)
    b.add_argument("--out", required=True)
    lm = sub.add_parser("landmarks", help="agrega V1-V6 a un archivo de cuerpo ya construido")
    lm.add_argument("--ts-dir", required=True)
    lm.add_argument("--npz", required=True)
    h = sub.add_parser("head")
    h.add_argument("--mni-dir", required=True)
    h.add_argument("--montage", required=True)
    h.add_argument("--head-fif", required=True, help="mne/data/fsaverage/fsaverage-head.fif")
    h.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    if args.cmd == "body":
        build_body(args.ts_dir, args.out)
    elif args.cmd == "landmarks":
        add_landmarks(args.ts_dir, args.npz)
    else:
        build_head(args.mni_dir, args.montage, args.head_fif, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
