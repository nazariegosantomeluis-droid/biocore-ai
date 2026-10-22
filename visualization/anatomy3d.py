"""Anatomía 3D de referencia (traída del aporte externo auditado, 2026-10-22).

Mallas reales y con licencia, para UBICAR Y ENSEÑAR -- no un gemelo:

- `body_figure()`: órganos de una tomografía real de cuerpo completo
  (TotalSegmentator, sujeto s1397, CC BY 4.0).
- `head_figure()`: cuero cabelludo fsaverage, cerebro MNI ICBM 152 y las
  posiciones estándar del sistema 10-20.
- `mesh_figure()`: cualquier malla (la que el usuario reconstruye o abre).

ESTÁTICA POR DISEÑO (`REFERENCE_ANATOMY_NOTE`): las mallas son las de una
persona y una plantilla, y no cambian con el estado del paciente ni del
gemelo. En la versión original el cuerpo se coloreaba con el puntaje
heurístico del organismo de la sesión y su documentación decía "estado del
UPS", lo que era falso; ese coloreado no se trajo. Conectarlo al UPS es una
tanda aparte.

Coordenadas: RAS+ en mm (x hacia la derecha del paciente, y hacia anterior,
z hacia arriba). Sin Streamlit aquí; las páginas llaman a estas funciones.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, Mapping, Optional, Tuple

import numpy as np

ASSET_DIR = Path(__file__).resolve().parents[1] / "data" / "anatomy3d"
BODY_FILE = "body_ts_s1397.npz"
HEAD_FILE = "head_mni152.npz"

REFERENCE_ANATOMY_NOTE = (
    "Anatomía de referencia de un sujeto (s1397), no reactiva — ilustrativa, no un gemelo que reacciona al estado."
)

INK = "#e0e7ff"
INK_2 = "#b6c2e2"


class AnatomyUnavailableError(RuntimeError):
    """Falta el archivo de mallas en `data/anatomy3d/`."""


@dataclass(frozen=True)
class Mesh:
    key: str
    label: str
    system: str
    vertices: np.ndarray       # (n, 3) float32, mm
    faces: np.ndarray          # (m, 3) uint16/uint32
    volume_ml: Optional[float] = None

    @property
    def n_faces(self) -> int:
        return int(self.faces.shape[0])


@dataclass(frozen=True)
class Anatomy:
    kind: str
    meta: dict
    meshes: Mapping[str, Mesh]
    electrode_names: Tuple[str, ...] = ()
    electrode_xyz: Optional[np.ndarray] = None

    def __getitem__(self, key: str) -> Mesh:
        return self.meshes[key]

    @property
    def source(self) -> dict:
        return self.meta.get("source", {})


def _read(path: Path) -> Anatomy:
    if not path.exists():
        raise AnatomyUnavailableError(
            f"No se encontró {path.name} en data/anatomy3d/. Se genera con tools/build_anatomy3d.py."
        )
    with np.load(path, allow_pickle=False) as z:
        meta = json.loads(bytes(z["meta"]).decode("utf-8"))
        scale = float(meta["vertex_scale_mm"])
        meshes: Dict[str, Mesh] = {}
        for part in meta["parts"]:
            key = part["key"]
            meshes[key] = Mesh(key=key, label=part["label"], system=part["system"],
                               vertices=z[f"{key}__v"].astype(np.float32) * scale, faces=z[f"{key}__f"],
                               volume_ml=part.get("volume_ml"))
        names: Tuple[str, ...] = tuple(meta.get("electrodes", ()))
        xyz = z["electrodes__xyz"].astype(np.float32) if "electrodes__xyz" in z.files else None
    if xyz is not None:
        xyz = xyz - np.asarray(meta["origin_mm"], dtype=np.float32)
    return Anatomy(kind=meta["kind"], meta=meta, meshes=meshes, electrode_names=names, electrode_xyz=xyz)


@lru_cache(maxsize=1)
def load_body() -> Anatomy:
    """Cuerpo de la TC real (se lee una vez por proceso)."""
    return _read(ASSET_DIR / BODY_FILE)


@lru_cache(maxsize=1)
def load_head() -> Anatomy:
    """Cabeza fsaverage + cerebro MNI152 + electrodos 10-20 (se lee una vez por proceso)."""
    return _read(ASSET_DIR / HEAD_FILE)


def assets_available() -> bool:
    return (ASSET_DIR / BODY_FILE).exists() and (ASSET_DIR / HEAD_FILE).exists()


# ─────────────────────────────────────────────────────────────────────────
# Sistemas y colores de tejido
# ─────────────────────────────────────────────────────────────────────────

# Solo los sistemas de órganos. Esqueleto, músculos y piel quedan fuera del
# visor (auditoría 2026-10-22: no se ocupan). Las mallas siguen en el archivo
# de datos tal como se publicaron.
SYSTEM_LABELS: Dict[str, str] = {
    "circulatory": "Corazón y vasos",
    "respiratory": "Pulmones y tráquea",
    "nervous": "Encéfalo y médula",
    "abdominal": "Abdomen y pelvis",
}
DEFAULT_SYSTEMS: Tuple[str, ...] = ("circulatory", "respiratory", "nervous")

# Colores de tejido (anatomía, no estados clínicos).
TISSUE_COLOR: Dict[str, str] = {
    "heart": "#c0394c", "arteries": "#d9475a", "veins": "#5872c9", "pulmonary_veins": "#e06478",
    "lung_right": "#eeb0ab", "lung_left": "#eeb0ab", "trachea": "#ecd2c0",
    "brain": "#ecc0b4", "spinal_cord": "#f1d78b",
    "liver": "#9a3b31", "gallbladder": "#7f9e4a", "stomach": "#dba796", "esophagus": "#d38e80",
    "duodenum": "#e0ae99", "small_bowel": "#e3b19c", "colon": "#cf9c84", "pancreas": "#e6c086",
    "spleen": "#93405a", "kidneys": "#a54a3c", "adrenals": "#ddb05f", "bladder": "#e2c497",
    "prostate": "#c27e6c", "thyroid": "#bd5649",
}

LIGHTING = dict(ambient=0.42, diffuse=0.78, specular=0.32, roughness=0.42, fresnel=0.22)
LIGHT_POSITION = dict(x=-1200, y=2600, z=2200)

CAMERAS: Dict[str, dict] = {
    "front": dict(eye=dict(x=0.0, y=1.85, z=0.12), up=dict(x=0, y=0, z=1)),
    "back": dict(eye=dict(x=0.0, y=-1.85, z=0.12), up=dict(x=0, y=0, z=1)),
    "left": dict(eye=dict(x=-1.85, y=0.0, z=0.12), up=dict(x=0, y=0, z=1)),
    "right": dict(eye=dict(x=1.85, y=0.0, z=0.12), up=dict(x=0, y=0, z=1)),
    "oblique": dict(eye=dict(x=-1.2, y=1.45, z=0.35), up=dict(x=0, y=0, z=1)),
}
CAMERA_LABELS: Dict[str, str] = {"front": "Frente", "oblique": "Oblicua", "left": "Izquierda",
                                 "right": "Derecha", "back": "Detrás"}


def _scene_layout(camera, height: int, *, aspect: str = "data", uirevision: str = "anatomy3d") -> dict:
    axis = dict(visible=False, showbackground=False, showgrid=False, zeroline=False, showspikes=False, title="")
    return dict(
        height=height,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        uirevision=uirevision,
        scene=dict(xaxis=axis, yaxis=axis, zaxis=axis, aspectmode=aspect,
                   camera=dict(camera if isinstance(camera, dict) else CAMERAS.get(camera, CAMERAS["front"]),
                               projection=dict(type="perspective")),
                   dragmode="orbit", bgcolor="rgba(0,0,0,0)"),
        hoverlabel=dict(bgcolor="#111d36", bordercolor="#5d6b92", font=dict(color=INK, size=13)),
    )


def _mesh_trace(mesh: Mesh, *, color: str, opacity: float = 1.0, hover: Optional[str] = None):
    import plotly.graph_objects as go

    v, f = mesh.vertices, mesh.faces
    return go.Mesh3d(
        x=v[:, 0], y=v[:, 1], z=v[:, 2], i=f[:, 0], j=f[:, 1], k=f[:, 2],
        name=mesh.label, color=color, opacity=opacity, flatshading=False,
        lighting=LIGHTING, lightposition=LIGHT_POSITION, showscale=False,
        hovertemplate=hover if hover is not None else f"<b>{mesh.label}</b><extra></extra>",
    )


def part_hover(mesh: Mesh) -> str:
    vol = f"<br>Volumen en esta TC: {mesh.volume_ml:,.0f} mL".replace(",", " ") if mesh.volume_ml else ""
    return f"<b>{mesh.label}</b>{vol}<br>Anatomía de referencia (sujeto s1397)<extra></extra>"


def body_figure(*, systems: Iterable[str] = DEFAULT_SYSTEMS, camera: str = "front", height: int = 640):
    """Órganos de la TC real, siempre con su color de tejido: no reflejan
    ningún estado (ver `REFERENCE_ANATOMY_NOTE`)."""
    import plotly.graph_objects as go

    anat = load_body()
    systems = set(systems) & set(SYSTEM_LABELS)
    fig = go.Figure()
    for mesh in anat.meshes.values():
        if mesh.system in systems:
            fig.add_trace(_mesh_trace(mesh, color=TISSUE_COLOR.get(mesh.key, "#c8cfdc"), hover=part_hover(mesh)))
    fig.update_layout(**_scene_layout(camera, height, uirevision="body3d"))
    return fig


def mesh_figure(vertices: np.ndarray, faces: np.ndarray, *, color: str = "#e9dec7", label: str = "Modelo",
                camera: str = "front", height: int = 560, opacity: float = 1.0):
    """Figura de una malla arbitraria (vértices en mm)."""
    import plotly.graph_objects as go

    v = np.asarray(vertices, dtype=np.float32)
    v = v - (v.min(axis=0) + v.max(axis=0)) / 2.0
    mesh = Mesh(key="user", label=label, system="user", vertices=v, faces=np.asarray(faces))
    fig = go.Figure(_mesh_trace(mesh, color=color, opacity=opacity))
    fig.update_layout(**_scene_layout(camera, height, uirevision="mesh3d:" + label))
    return fig


# ─────────────────────────────────────────────────────────────────────────
# Cabeza de referencia: posiciones estándar 10-20 (sin mapa de valores)
# ─────────────────────────────────────────────────────────────────────────

HEAD_CENTER = np.array([0.0, -18.0, 12.0], dtype=np.float64)  # centro de la bóveda (MNI, mm)
SCALP_COLOR = "#b3bfd2"


def head_figure(*, show_brain: bool = True, show_labels: bool = True, camera: str = "oblique", height: int = 560):
    """Cuero cabelludo fsaverage, cerebro MNI152 y las posiciones estándar de
    los electrodos 10-20 (MNE). Referencia estática: no dibuja ningún EEG."""
    import plotly.graph_objects as go

    head = load_head()
    scalp = head["scalp_lo"] if "scalp_lo" in head.meshes else head["scalp"]
    fig = go.Figure()
    if show_brain:
        brain = head["brain"]
        fig.add_trace(_mesh_trace(brain, color=TISSUE_COLOR["brain"], hover=f"<b>{brain.label}</b><extra></extra>"))
    fig.add_trace(_mesh_trace(scalp, color=SCALP_COLOR, opacity=0.28 if show_brain else 1.0,
                              hover="<b>Cabeza (plantilla)</b><extra></extra>"))
    names = list(head.electrode_names)
    xyz = np.asarray(head.electrode_xyz, dtype=np.float64)
    out = (xyz - HEAD_CENTER) / np.linalg.norm(xyz - HEAD_CENTER, axis=1, keepdims=True)
    mk, lab = xyz + out * 3.0, xyz + out * 11.0
    fig.add_trace(go.Scatter3d(x=mk[:, 0], y=mk[:, 1], z=mk[:, 2], mode="markers", name="Electrodos 10-20",
                               marker=dict(size=4, color="#f1f5f9", line=dict(color="#0b1426", width=1)),
                               hovertemplate=[f"<b>{n}</b><extra></extra>" for n in names]))
    if show_labels:
        fig.add_trace(go.Scatter3d(x=lab[:, 0], y=lab[:, 1], z=lab[:, 2], mode="text", text=names,
                                   textfont=dict(color=INK_2, size=12), hoverinfo="skip", name="Nombres"))
    fig.update_layout(**_scene_layout(camera, height, uirevision="head3d"))
    return fig
