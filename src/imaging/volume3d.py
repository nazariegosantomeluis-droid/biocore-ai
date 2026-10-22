"""De un estudio de imagen (TC/RM) a un modelo 3D (2026-10-21).

Para "Crea tu modelo 3D": la persona sube su propio estudio --
- NIfTI (.nii / .nii.gz), incluidos mapas de etiquetas de segmentación
  (p. ej., la salida de TotalSegmentator), o
- DICOM (varios .dcm o un .zip con la serie) --
y aquí se reconstruye la superficie con marching cubes (Lorensen & Cline,
1987), se suaviza y se simplifica para verla en el navegador y descargarla
como STL/OBJ/PLY (impresión 3D, Blender, 3D Slicer...).

Todo se procesa en la computadora de la persona: nada sale del equipo.
"""

from __future__ import annotations

import gzip
import io
import zipfile
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

MARCHING_CUBES_CITATION = (
    "Lorensen WE, Cline HE. Marching cubes: a high resolution 3D surface construction algorithm. "
    "SIGGRAPH Comput Graph. 1987;21(4):163-169."
)
MAX_VOXELS = 14_000_000      # por encima se reduce la resolución (memoria y tiempo)
MAX_UPLOAD_MB = 400


class VolumeError(ValueError):
    """El archivo no se pudo leer como volumen 3D."""


@dataclass
class Volume:
    data: np.ndarray                 # (i, j, k) float32
    affine: np.ndarray               # vóxel -> mm RAS
    modality: str                    # "CT", "MR", "labels" u "other"
    source: str                      # nombre del archivo o de la serie
    notes: List[str] = field(default_factory=list)

    @property
    def spacing(self) -> Tuple[float, float, float]:
        return tuple(float(np.linalg.norm(self.affine[:3, i])) for i in range(3))

    @property
    def shape(self) -> Tuple[int, int, int]:
        return tuple(int(s) for s in self.data.shape[:3])

    @property
    def is_labels(self) -> bool:
        return self.modality == "labels"


# ─────────────────────────────────────────────────────────────────────────
# Lectura
# ─────────────────────────────────────────────────────────────────────────

def _guess_modality(data: np.ndarray, hint: str = "") -> str:
    hint = hint.upper()
    if hint in ("CT", "MR"):
        return hint
    finite = data[np.isfinite(data)]
    if finite.size == 0:
        raise VolumeError("el volumen está vacío")
    is_int = np.allclose(finite[:: max(1, finite.size // 200000)], np.round(finite[:: max(1, finite.size // 200000)]))
    uniq = np.unique(finite[:: max(1, finite.size // 500000)])
    if is_int and uniq.size <= 256 and finite.min() >= 0 and finite.max() < 2000:
        return "labels"
    if finite.min() < -500 and finite.max() > 300:
        return "CT"
    return "other"


def load_nifti_bytes(raw: bytes, name: str = "volumen.nii") -> Volume:
    import nibabel as nib

    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    try:
        img = nib.Nifti1Image.from_bytes(raw)
    except Exception:
        try:
            img = nib.Nifti2Image.from_bytes(raw)
        except Exception as exc:  # noqa: BLE001
            raise VolumeError(f"no parece un NIfTI válido ({exc})") from exc
    img = nib.as_closest_canonical(img)   # ejes RAS
    data = np.asanyarray(img.dataobj)
    if data.ndim == 4:
        data = data[..., 0]
    if data.ndim != 3:
        raise VolumeError(f"se esperaba un volumen 3D y llegó uno de {data.ndim} dimensiones")
    data = np.asarray(data, dtype=np.float32)
    return Volume(data=data, affine=np.asarray(img.affine, float), modality=_guess_modality(data), source=name)


def load_dicom_files(files: Sequence[Tuple[str, bytes]]) -> Volume:
    """Serie DICOM (lista de (nombre, bytes)); acepta también un .zip."""
    import pydicom

    expanded: List[Tuple[str, bytes]] = []
    for name, raw in files:
        if name.lower().endswith(".zip") or raw[:4] == b"PK\x03\x04":
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                for info in zf.infolist():
                    if not info.is_dir() and info.file_size > 0:
                        expanded.append((info.filename, zf.read(info)))
        else:
            expanded.append((name, raw))
    slices = []
    for name, raw in expanded:
        try:
            ds = pydicom.dcmread(io.BytesIO(raw), force=True)
            if "PixelData" not in ds:
                continue
            slices.append(ds)
        except Exception:
            continue
    if len(slices) < 3:
        raise VolumeError("no se encontraron al menos 3 cortes DICOM con imagen")
    # Una sola serie: la más numerosa.
    by_series: Dict[str, list] = {}
    for ds in slices:
        by_series.setdefault(str(getattr(ds, "SeriesInstanceUID", "única")), []).append(ds)
    series = max(by_series.values(), key=len)
    notes = []
    if len(by_series) > 1:
        notes.append(f"había {len(by_series)} series; se usó la de {len(series)} cortes")
    ref = series[0]
    try:
        iop = np.array([float(v) for v in ref.ImageOrientationPatient])
    except Exception:
        iop = np.array([1, 0, 0, 0, 1, 0], float)
        notes.append("sin orientación en los DICOM: se asumió axial")
    row, col = iop[:3], iop[3:]
    normal = np.cross(row, col)

    def pos(ds):
        try:
            return np.array([float(v) for v in ds.ImagePositionPatient])
        except Exception:
            return np.array([0.0, 0.0, float(getattr(ds, "InstanceNumber", 0))])

    series.sort(key=lambda ds: float(pos(ds) @ normal))
    arrays = []
    for ds in series:
        a = ds.pixel_array.astype(np.float32)
        slope = float(getattr(ds, "RescaleSlope", 1) or 1)
        inter = float(getattr(ds, "RescaleIntercept", 0) or 0)
        arrays.append(a * slope + inter)
    shapes = {a.shape for a in arrays}
    if len(shapes) != 1:
        raise VolumeError("los cortes tienen tamaños distintos")
    vol = np.stack(arrays, axis=-1)          # (filas, columnas, cortes)
    vol = np.transpose(vol, (1, 0, 2))      # (columnas=i, filas=j, cortes=k)
    ps = [float(v) for v in getattr(ref, "PixelSpacing", [1.0, 1.0])]
    p0, p1 = pos(series[0]), pos(series[-1])
    dz = float(np.linalg.norm(p1 - p0)) / max(len(series) - 1, 1) or float(getattr(ref, "SliceThickness", 1.0) or 1.0)
    # Afín LPS (DICOM) -> RAS (NIfTI): se invierten x e y.
    lps = np.eye(4)
    lps[:3, 0] = row * ps[1]
    lps[:3, 1] = col * ps[0]
    lps[:3, 2] = normal * dz
    lps[:3, 3] = p0
    flip = np.diag([-1.0, -1.0, 1.0, 1.0])
    affine = flip @ lps
    modality = str(getattr(ref, "Modality", "")).upper()
    return Volume(data=vol, affine=affine, modality=_guess_modality(vol, modality),
                  source=f"serie DICOM de {len(series)} cortes", notes=notes)


def load_any(files: Sequence[Tuple[str, bytes]]) -> Volume:
    """Elige el lector por extensión/contenido."""
    if not files:
        raise VolumeError("no se recibió ningún archivo")
    total = sum(len(r) for _, r in files) / 1e6
    if total > MAX_UPLOAD_MB:
        raise VolumeError(f"{total:.0f} MB supera el máximo de {MAX_UPLOAD_MB} MB")
    if len(files) == 1:
        name, raw = files[0]
        low = name.lower()
        if low.endswith((".nii", ".nii.gz", ".gz")) or raw[344:348] in (b"n+1\x00", b"ni1\x00"):
            return load_nifti_bytes(raw, name)
    return load_dicom_files(files)


def downsample_for_mesh(vol: Volume, max_voxels: int = MAX_VOXELS) -> Tuple[Volume, int]:
    """Reduce la resolución por un factor entero si el volumen es enorme."""
    n = int(np.prod(vol.shape))
    step = 1
    while n / step ** 3 > max_voxels:
        step += 1
    if step == 1:
        return vol, 1
    data = vol.data[::step, ::step, ::step]
    aff = vol.affine.copy()
    aff[:3, :3] = aff[:3, :3] * step
    return Volume(data=data, affine=aff, modality=vol.modality, source=vol.source,
                  notes=vol.notes + [f"resolución reducida ×{step} para reconstruir rápido"]), step


# ─────────────────────────────────────────────────────────────────────────
# Segmentación simple por umbral y superficies
# ─────────────────────────────────────────────────────────────────────────

# Solo los presets con validación medida. Los de hueso, piel y tejido blando de
# la versión original se retiraron en la auditoría del 2026-10-22: hueso medido
# incompleto (sin cartílago costal, costillas finas con huecos a 2 mm), piel sin
# referencia independiente (la del TotalSegmentator sale del mismo umbral) y
# tejido blando sin medir. El umbral manual sigue disponible, rotulado sin validar.
CT_PRESETS: Dict[str, dict] = {
    "lungs": {"label": "Pulmones y vía aérea", "high": -400.0, "color": "#eeb0ab"},
}
LUNG_VALIDATION_NOTE = (
    "Preset de pulmón verificado contra TotalSegmentator en 1 sujeto (s1397): volumen −1.9 %, distancia media "
    "entre superficies 1.2-1.3 mm, malla cerrada. Un solo sujeto: no es una validación clínica."
)


def otsu_threshold(data: np.ndarray) -> float:
    from skimage.filters import threshold_otsu

    sample = data[np.isfinite(data)]
    sample = sample[:: max(1, sample.size // 2_000_000)]
    return float(threshold_otsu(sample))


def _largest(mask: np.ndarray, keep: int) -> np.ndarray:
    from scipy import ndimage as ndi

    labels, n = ndi.label(mask)
    if n <= keep:
        return mask
    sizes = ndi.sum(mask, labels, index=np.arange(1, n + 1))
    order = np.argsort(sizes)[::-1][:keep] + 1
    return np.isin(labels, order)


LUNG_SEGMENTATION_CITATION = (
    "Hu S, Hoffman EA, Reinhardt JM. Automatic lung segmentation for accurate quantitation of volumetric "
    "X-ray CT images. IEEE Trans Med Imaging. 2001;20(6):490-498."
)
# Bolsas de aire intracorporal que se conservan como pulmón/vía aérea: las de al
# menos esta fracción de la mayor. Heurística propia (2026-10-21), medida sobre la
# TC de ejemplo (s1397): el pulmón con la tráquea es una sola bolsa de 4.9 L y el
# gas digestivo, 0.24 y 0.08 L -- quedarse con "las 3 mayores" (o "las 2", como
# Medical3DReconstruction) metía el gas del estómago en "Pulmones". Si los dos
# pulmones salen separados, cada uno pesa ~30-70% del total y ambos pasan.
LUNG_MIN_FRACTION_OF_LARGEST = 0.2
LUNG_CLOSING_RADIUS_MM = 2.0


def _keep_relative(mask: np.ndarray, fraction: float) -> np.ndarray:
    from scipy import ndimage as ndi

    labels, n = ndi.label(mask)
    if n <= 1:
        return mask
    sizes = ndi.sum(mask, labels, index=np.arange(1, n + 1))
    return np.isin(labels, np.flatnonzero(sizes >= fraction * sizes.max()) + 1)


def _ball(radius: int) -> np.ndarray:
    g = np.arange(-radius, radius + 1)
    zz, yy, xx = np.meshgrid(g, g, g, indexing="ij")
    return zz ** 2 + yy ** 2 + xx ** 2 <= radius ** 2


def _clean_lungs(mask: np.ndarray, spacing: Tuple[float, float, float]) -> np.ndarray:
    """Postproceso pulmonar de Hu et al. 2001 (como en Medical3DReconstruction):
    descarta el gas fuera del pulmón, rellena huecos (vasos dentro del pulmón,
    que el umbral deja fuera) y cierra 2 mm el borde pleural. Validado contra la
    segmentación de TotalSegmentator del mismo sujeto (ver tests)."""
    from scipy import ndimage as ndi

    mask = ndi.binary_fill_holes(_keep_relative(mask, LUNG_MIN_FRACTION_OF_LARGEST))
    radius = max(1, int(round(LUNG_CLOSING_RADIUS_MM / min(spacing))))
    return ndi.binary_fill_holes(ndi.binary_closing(mask, structure=_ball(radius)))


def preset_mask(vol: Volume, preset: str) -> np.ndarray:
    from scipy import ndimage as ndi

    """Máscara del preset (hoy solo "lungs": aire dentro del cuerpo + postproceso
    de `_clean_lungs`)."""
    cfg = CT_PRESETS[preset]
    d = vol.data
    body = _largest(ndi.binary_opening(d > -350, iterations=1), 1)
    for k in range(body.shape[2]):
        body[:, :, k] = ndi.binary_fill_holes(body[:, :, k])
    body = ndi.binary_erosion(body, iterations=2)
    return _clean_lungs((d < cfg["high"]) & body, vol.spacing)


def threshold_mask(vol: Volume, low: Optional[float], high: Optional[float] = None) -> np.ndarray:
    mask = np.ones(vol.data.shape, bool)
    if low is not None:
        mask &= vol.data >= low
    if high is not None:
        mask &= vol.data < high
    return mask


def label_values(vol: Volume, max_labels: int = 256) -> List[int]:
    vals = np.unique(vol.data[vol.data > 0]).astype(int)
    return [int(v) for v in vals[:max_labels]]


@dataclass
class MeshResult:
    vertices: np.ndarray      # (n, 3) float32 mm RAS
    faces: np.ndarray         # (m, 3) int32
    voxels: int
    volume_ml: float
    notes: List[str] = field(default_factory=list)

    @property
    def n_faces(self) -> int:
        return int(self.faces.shape[0])


def taubin_smooth(verts: np.ndarray, faces: np.ndarray, iterations: int = 5,
                  lam: float = 0.5, mu: float = -0.53) -> np.ndarray:
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
        for f in (lam, mu):
            v = v + f * (adj @ v / deg[:, None] - v)
    return v.astype(np.float32)


def mesh_from_mask(mask: np.ndarray, affine: np.ndarray, *, target_faces: int = 120_000, sigma: float = 0.8,
                   keep_components: Optional[int] = None, smooth_iterations: int = 5) -> MeshResult:
    """Superficie de una máscara (marching cubes sobre la máscara suavizada,
    decimación cuádrica si `fast_simplification` está instalada y suavizado
    de Taubin). Vértices en mm RAS."""
    from scipy import ndimage as ndi
    from skimage import measure

    if not mask.any():
        raise VolumeError("la selección no contiene ningún vóxel: ajusta el umbral")
    notes = []
    if keep_components:
        mask = _largest(mask, keep_components)
    voxels = int(mask.sum())
    vox_ml = float(abs(np.linalg.det(affine[:3, :3]))) / 1000.0
    idx = np.argwhere(mask)
    lo = np.maximum(idx.min(axis=0) - 3, 0)
    hi = np.minimum(idx.max(axis=0) + 4, mask.shape)
    sub = np.pad(mask[lo[0]:hi[0], lo[1]:hi[1], lo[2]:hi[2]], 2).astype(np.float32)
    if sigma > 0:
        sub = ndi.gaussian_filter(sub, sigma)
    verts, faces, _n, _v = measure.marching_cubes(sub, level=0.5, allow_degenerate=False)
    verts = verts - 2 + lo
    world = (verts @ affine[:3, :3].T + affine[:3, 3]).astype(np.float32)
    faces = faces.astype(np.int64)
    if np.linalg.det(affine[:3, :3]) < 0:
        faces = faces[:, ::-1]
    if faces.shape[0] > target_faces:
        try:
            import fast_simplification

            # Simplificar nunca debe abrir una malla cerrada (auditoría 2026-10-22: el
            # pulmón de la TC de ejemplo se abría por debajo de ~80 000 triángulos). Si el
            # resultado sale abierto, se reintenta con el doble; si nunca cierra, se
            # deja la malla sin simplificar.
            closed = mesh_quality(faces).watertight
            target = target_faces
            while target < faces.shape[0]:
                sv, sf = fast_simplification.simplify(world, faces.astype(np.int32),
                                                      target_reduction=1 - target / faces.shape[0])
                if not closed or mesh_quality(sf).watertight:
                    note = f"simplificada a {sf.shape[0]:,} triángulos".replace(",", " ")
                    if target > target_faces:
                        note += f" (a {target_faces:,} se abría la malla)".replace(",", " ")
                    world, faces = sv, sf
                    notes.append(note)
                    break
                target *= 2
            else:
                notes.append("sin simplificar: simplificarla abría la malla")
        except ImportError:
            notes.append("sin fast-simplification: malla sin simplificar (puede ir lenta)")
    world = np.asarray(world, np.float32)
    faces = np.asarray(faces, np.int64)
    if smooth_iterations:
        world = taubin_smooth(world, faces, iterations=smooth_iterations)
    return MeshResult(vertices=world, faces=faces.astype(np.int32), voxels=voxels, volume_ml=voxels * vox_ml,
                      notes=notes)


# ─────────────────────────────────────────────────────────────────────────
# Exportación e importación de mallas
# ─────────────────────────────────────────────────────────────────────────

def to_stl(vertices: np.ndarray, faces: np.ndarray, name: str = "biocore") -> bytes:
    """STL binario (milímetros)."""
    v = np.asarray(vertices, np.float32)
    f = np.asarray(faces, np.int64)
    tri = v[f]
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    n = np.divide(n, ln, out=np.zeros_like(n), where=ln > 0)
    rec = np.zeros(f.shape[0], dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])
    rec["n"] = n
    rec["v"] = tri
    header = (f"BIOCORE AI STL {name}".encode("ascii", "replace") + b" " * 80)[:80]
    return header + np.uint32(f.shape[0]).tobytes() + rec.tobytes()


def to_obj(vertices: np.ndarray, faces: np.ndarray) -> bytes:
    lines = ["# BIOCORE AI - coordenadas en mm"]
    lines += [f"v {x:.3f} {y:.3f} {z:.3f}" for x, y, z in np.asarray(vertices, float)]
    lines += [f"f {a + 1} {b + 1} {c + 1}" for a, b, c in np.asarray(faces, int)]
    return ("\n".join(lines) + "\n").encode("ascii")


def to_ply(vertices: np.ndarray, faces: np.ndarray) -> bytes:
    v = np.asarray(vertices, "<f4")
    f = np.asarray(faces, "<i4")
    header = (f"ply\nformat binary_little_endian 1.0\ncomment BIOCORE AI (mm)\nelement vertex {v.shape[0]}\n"
              "property float x\nproperty float y\nproperty float z\n"
              f"element face {f.shape[0]}\nproperty list uchar int vertex_indices\nend_header\n").encode("ascii")
    rec = np.zeros(f.shape[0], dtype=[("n", "u1"), ("i", "<i4", 3)])
    rec["n"] = 3
    rec["i"] = f
    return header + v.tobytes() + rec.tobytes()


def read_mesh(name: str, raw: bytes) -> Tuple[np.ndarray, np.ndarray]:
    """Lee STL (binario o ASCII), OBJ o PLY (ASCII o binario little-endian)."""
    low = name.lower()
    if low.endswith(".stl"):
        if raw[:5].lower() == b"solid" and b"facet" in raw[:2000]:
            pts = [list(map(float, ln.split()[1:4])) for ln in raw.decode("ascii", "replace").splitlines()
                   if ln.strip().startswith("vertex")]
            v = np.asarray(pts, np.float32)
        else:
            n = int(np.frombuffer(raw[80:84], "<u4")[0])
            rec = np.frombuffer(raw[84:84 + n * 50], dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])
            v = rec["v"].reshape(-1, 3)
        f = np.arange(v.shape[0]).reshape(-1, 3)
        return _weld(v, f)
    if low.endswith(".obj"):
        vs, fs = [], []
        for ln in raw.decode("utf-8", "replace").splitlines():
            if ln.startswith("v "):
                vs.append([float(x) for x in ln.split()[1:4]])
            elif ln.startswith("f "):
                idx = [int(p.split("/")[0]) for p in ln.split()[1:]]
                idx = [i - 1 if i > 0 else len(vs) + i for i in idx]
                for k in range(1, len(idx) - 1):
                    fs.append([idx[0], idx[k], idx[k + 1]])
        return np.asarray(vs, np.float32), np.asarray(fs, np.int64)
    if low.endswith(".ply"):
        return _read_ply(raw)
    raise VolumeError("formato de malla no soportado (usa STL, OBJ o PLY)")


_PLY_TYPES = {"char": "i1", "int8": "i1", "uchar": "u1", "uint8": "u1", "short": "i2", "int16": "i2",
              "ushort": "u2", "uint16": "u2", "int": "i4", "int32": "i4", "uint": "u4", "uint32": "u4",
              "float": "f4", "float32": "f4", "double": "f8", "float64": "f8"}


def _read_ply(raw: bytes) -> Tuple[np.ndarray, np.ndarray]:
    """PLY ASCII o binario little-endian (vértices x/y/z de cualquier tipo
    numérico, caras como lista; los polígonos se triangulan en abanico)."""
    end = raw.find(b"end_header")
    if not raw.startswith(b"ply") or end < 0:
        raise VolumeError("PLY sin encabezado válido")
    header = raw[:end].decode("ascii", "replace").splitlines()
    body = raw[raw.find(b"\n", end) + 1:]
    fmt_line = next((h for h in header if h.startswith("format")), "format ascii 1.0")
    elements: List[dict] = []
    for h in header:
        parts = h.split()
        if parts[:1] == ["element"]:
            elements.append({"name": parts[1], "count": int(parts[2]), "props": []})
        elif parts[:1] == ["property"] and elements:
            elements[-1]["props"].append(parts[1:])
    vert = next((e for e in elements if e["name"] == "vertex"), None)
    face = next((e for e in elements if e["name"] == "face"), None)
    if vert is None or face is None:
        raise VolumeError("PLY sin vértices o sin caras")
    names = [p[-1] for p in vert["props"]]
    if "ascii" in fmt_line:
        rows = body.decode("ascii", "replace").split("\n")
        v = np.asarray([[float(x) for x in r.split()] for r in rows[:vert["count"]]], np.float64)
        v = v[:, [names.index(c) for c in ("x", "y", "z")]]
        faces = []
        for r in rows[vert["count"]:vert["count"] + face["count"]]:
            idx = [int(x) for x in r.split()]
            for k in range(1, idx[0] - 1):
                faces.append([idx[1], idx[1 + k], idx[2 + k]])
        return v.astype(np.float32), np.asarray(faces, np.int64)
    if "binary_little_endian" not in fmt_line:
        raise VolumeError("PLY binario big-endian no soportado")
    dtype = np.dtype([(p[-1], "<" + _PLY_TYPES[p[0]]) for p in vert["props"] if p[0] != "list"])
    varr = np.frombuffer(body[:vert["count"] * dtype.itemsize], dtype=dtype)
    v = np.stack([varr["x"], varr["y"], varr["z"]], axis=1).astype(np.float32)
    rest = body[vert["count"] * dtype.itemsize:]
    lst = next(p for p in face["props"] if p[0] == "list")
    ct, it = "<" + _PLY_TYPES[lst[1]], "<" + _PLY_TYPES[lst[2]]
    tri = np.dtype([("n", ct), ("i", it, 3)])
    if len(rest) >= face["count"] * tri.itemsize:
        arr = np.frombuffer(rest[:face["count"] * tri.itemsize], dtype=tri)
        if np.all(arr["n"] == 3):
            return v, arr["i"].astype(np.int64)
    faces, off = [], 0
    csz, isz = np.dtype(ct).itemsize, np.dtype(it).itemsize
    for _ in range(face["count"]):
        n = int(np.frombuffer(rest[off:off + csz], ct)[0])
        idx = np.frombuffer(rest[off + csz:off + csz + n * isz], it)
        off += csz + n * isz
        for k in range(1, n - 1):
            faces.append([idx[0], idx[k], idx[k + 1]])
    return v, np.asarray(faces, np.int64)


def _weld(v: np.ndarray, f: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Une vértices duplicados (STL guarda cada triángulo suelto)."""
    q = np.round(v / 1e-4).astype(np.int64)
    _, idx, inv = np.unique(q, axis=0, return_index=True, return_inverse=True)
    return v[idx], inv.reshape(-1)[f]


@dataclass(frozen=True)
class MeshQuality:
    """Calidad topológica de una malla (criterios de Medical3DReconstruction,
    `assess_mesh_quality`, aquí sin `trimesh`)."""

    watertight: bool          # cada arista la comparten exactamente 2 triángulos
    winding_consistent: bool  # ninguna arista se recorre dos veces en el mismo sentido
    bodies: int               # piezas conectadas
    open_edges: int           # aristas con 1 triángulo (borde) o con más de 2 (no-manifold)
    euler: int                # V - A + C (2 para una superficie cerrada sin agujeros)


def mesh_quality(faces: np.ndarray) -> MeshQuality:
    """Sin una malla cerrada, el "volumen encerrado" no está definido y una
    impresora 3D no sabe qué es dentro y qué es fuera."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components

    f = np.asarray(faces, np.int64)
    directed = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
    undirected, counts = np.unique(np.sort(directed, axis=1), axis=0, return_counts=True)
    open_edges = int((counts != 2).sum())
    _, directed_counts = np.unique(directed, axis=0, return_counts=True)
    used, local = np.unique(f, return_inverse=True)
    local = local.reshape(f.shape)
    e = np.concatenate([local[:, [0, 1]], local[:, [1, 2]]])
    graph = coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(len(used), len(used)))
    bodies = int(connected_components(graph, directed=False)[0]) if len(used) else 0
    return MeshQuality(
        watertight=open_edges == 0 and len(f) > 0,
        winding_consistent=bool(directed_counts.max() == 1) if len(f) else False,
        bodies=bodies, open_edges=open_edges,
        euler=int(len(used) - len(undirected) + len(f)),
    )


def mesh_stats(vertices: np.ndarray, faces: np.ndarray) -> Dict[str, float]:
    v = np.asarray(vertices, float)
    f = np.asarray(faces, int)
    tri = v[f]
    cross = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    area = float(np.linalg.norm(cross, axis=1).sum() / 2.0)
    vol = float(abs(np.einsum("ij,ij->i", tri[:, 0], np.cross(tri[:, 1], tri[:, 2])).sum()) / 6.0)
    size = v.max(axis=0) - v.min(axis=0)
    return {"triangles": float(f.shape[0]), "vertices": float(v.shape[0]), "area_cm2": area / 100.0,
            "volume_ml": vol / 1000.0, "size_x_mm": float(size[0]), "size_y_mm": float(size[1]),
            "size_z_mm": float(size[2])}
