"""Anatomía 3D de referencia (traída del aporte externo auditado, 2026-10-22).

Mallas reales y con licencia, para UBICAR Y ENSEÑAR -- no un gemelo:

- `body_figure()`: órganos de una tomografía real de cuerpo completo
  (TotalSegmentator, sujeto s1397, CC BY 4.0).
- `head_figure()`: cuero cabelludo fsaverage, cerebro MNI ICBM 152 y las
  posiciones estándar del sistema 10-20; si recibe valores por electrodo,
  un mapa topográfico por splines esféricos (Perrin 1989; Tanda 2D).
- `mesh_figure()`: cualquier malla (la que el usuario reconstruye o abre).

La GEOMETRÍA es siempre de referencia (una persona y una plantilla): no
cambia con el estado. En el Laboratorio 3D el cuerpo es estático
(`REFERENCE_ANATOMY_NOTE`). En el gemelo (Pieza 2, 2026-10-22), `body_figure`
puede recibir `organ_colors` para los TRES órganos que el UPS modela
(`UPS_ORGAN_PARTS`), y esos colores los decide `organ_visual_state()` -- la
misma función que usa el cuerpo SVG. La versión original coloreaba con el
puntaje heurístico del organismo de la sesión (y fabricaba "alerta" desde un
valor por defecto); ese coloreado no existe aquí.

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


def _mesh_trace(mesh: Mesh, *, color: str, opacity: float = 1.0, hover: Optional[str] = None,
                name: Optional[str] = None, intensity: Optional[np.ndarray] = None, colorscale=None):
    import plotly.graph_objects as go

    v, f = mesh.vertices, mesh.faces
    paint = dict(color=color) if intensity is None else dict(
        intensity=intensity, intensitymode="vertex", colorscale=colorscale, cmin=0.0, cmax=1.0)
    return go.Mesh3d(
        x=v[:, 0], y=v[:, 1], z=v[:, 2], i=f[:, 0], j=f[:, 1], k=f[:, 2],
        name=name or mesh.label, opacity=opacity, flatshading=False,
        lighting=LIGHTING, lightposition=LIGHT_POSITION, showscale=False,
        hovertemplate=hover if hover is not None else f"<b>{mesh.label}</b><extra></extra>",
        **paint,
    )


def part_hover(mesh: Mesh) -> str:
    vol = f"<br>Volumen en esta TC: {mesh.volume_ml:,.0f} mL".replace(",", " ") if mesh.volume_ml else ""
    return f"<b>{mesh.label}</b>{vol}<br>Anatomía de referencia (sujeto s1397)<extra></extra>"


# Órgano modelado por el UPS -> mallas que lo representan. Solo estos tres: los
# vasos (los eventos cardiovasculares son de ritmo/autonómicos, no vasculares),
# la médula (el UPS no tiene dominio autonómico) y el abdomen no tienen dominio.
UPS_ORGAN_PARTS: Dict[str, Tuple[str, ...]] = {
    "heart": ("heart",),
    "lungs": ("lung_left", "lung_right", "trachea"),
    "brain": ("brain",),
}
# Anatomía sin dominio, en modo "por estado": atenuada hacia gris azulado para que
# un tejido rojizo (arterias #d9475a) no se lea como el rojo crítico.
UNMODELED_BLEND = 0.6
UNMODELED_TOWARD = "#8090b0"
UNMODELED_OPACITY = 0.22


def _blend(hex_color: str, toward: str, amount: float) -> str:
    a = np.array([int(hex_color[i:i + 2], 16) for i in (1, 3, 5)], dtype=float)
    b = np.array([int(toward[i:i + 2], 16) for i in (1, 3, 5)], dtype=float)
    c = np.clip(np.round(a + (b - a) * amount), 0, 255).astype(int)
    return "#" + "".join(f"{x:02x}" for x in c)


def body_figure(*, systems: Iterable[str] = DEFAULT_SYSTEMS, camera: str = "front", height: int = 640,
                organ_colors: Optional[Mapping[str, str]] = None,
                organ_notes: Optional[Mapping[str, str]] = None):
    """Órganos de la TC real. Sin `organ_colors`: todo en color de tejido
    (referencia estática). Con `organ_colors` ({"heart"|"lungs"|"brain": color},
    calculados por `organ_visual_state()`): solo las mallas de
    `UPS_ORGAN_PARTS` toman ese color; el resto queda en tejido atenuado y
    nunca toma un color de estado."""
    import plotly.graph_objects as go

    anat = load_body()
    systems = set(systems) & set(SYSTEM_LABELS)
    part_organ = {part: organ for organ, parts in UPS_ORGAN_PARTS.items() for part in parts}
    by_state = organ_colors is not None
    fig = go.Figure()
    for mesh in anat.meshes.values():
        if mesh.system not in systems:
            continue
        tissue = TISSUE_COLOR.get(mesh.key, "#c8cfdc")
        organ = part_organ.get(mesh.key)
        if not by_state:
            fig.add_trace(_mesh_trace(mesh, color=tissue, hover=part_hover(mesh)))
        elif organ is not None and organ in organ_colors:
            note = (organ_notes or {}).get(organ, "")
            fig.add_trace(_mesh_trace(mesh, color=organ_colors[organ],
                                      hover=f"<b>{mesh.label}</b><br>{note}<extra></extra>"))
        else:
            fig.add_trace(_mesh_trace(mesh, color=_blend(tissue, UNMODELED_TOWARD, UNMODELED_BLEND),
                                      opacity=UNMODELED_OPACITY,
                                      hover=f"<b>{mesh.label}</b><br>Anatomía sin dominio en el UPS<extra></extra>"))
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
# Cabeza: posiciones 10-20 y, si recibe valores, mapa por splines esféricos
# ─────────────────────────────────────────────────────────────────────────

HEAD_CENTER = np.array([0.0, -18.0, 12.0], dtype=np.float64)  # centro de la bóveda (MNI, mm)
SCALP_COLOR = "#b3bfd2"

# Mapa topográfico (Tanda 2D, 2026-10-24, del aporte auditado).
MAP_MIN_POINTS = 4
MAP_REACH_MM = 45.0   # más lejos de cualquier electrodo el mapa queda gris: ahí no hay datos, solo extrapolación
# Rampa secuencial de un solo tono (azul): oscuro = poco, claro = mucho.
SEQUENTIAL_BLUE = [
    [0.0, "#104281"], [0.17, "#184f95"], [0.33, "#256abf"], [0.5, "#3987e5"],
    [0.67, "#6da7ec"], [0.83, "#9ec5f4"], [1.0, "#cde2fb"],
]


def _legendre_g(cos_angle: np.ndarray, m: int = 4, n_terms: int = 50) -> np.ndarray:
    from numpy.polynomial import legendre

    n = np.arange(1, n_terms + 1, dtype=float)
    coeffs = np.concatenate([[0.0], (2 * n + 1) / (n ** m * (n + 1) ** m)]) / (4 * np.pi)
    return legendre.legval(np.clip(cos_angle, -1.0, 1.0), coeffs)


def spherical_spline(src_xyz: np.ndarray, values: np.ndarray, dst_xyz: np.ndarray, *,
                     center: np.ndarray = HEAD_CENTER, m: int = 4, n_terms: int = 50,
                     smoothing: float = 1e-5) -> np.ndarray:
    """Splines esféricos (Perrin F, Pernier J, Bertrand O, Echallier JF.
    Electroencephalogr Clin Neurophysiol 1989;72:184-187), m = 4, 50 términos
    de Legendre, λ = 1e-5: proyecta electrodos y puntos destino a la esfera
    unitaria y resuelve [G + λI 1; 1ᵀ 0][c; c0] = [v; 0]."""
    def unit(p):
        d = np.asarray(p, dtype=float) - center
        return d / np.linalg.norm(d, axis=1, keepdims=True)

    s, d = unit(src_xyz), unit(dst_xyz)
    n = s.shape[0]
    a = np.zeros((n + 1, n + 1))
    a[:n, :n] = _legendre_g(s @ s.T, m, n_terms) + smoothing * np.eye(n)
    a[:n, n] = 1.0
    a[n, :n] = 1.0
    coef = np.linalg.solve(a, np.concatenate([np.asarray(values, dtype=float), [0.0]]))
    return _legendre_g(d @ s.T, m, n_terms) @ coef[:n] + coef[n]


_ALIASES = {"T3": "T7", "T4": "T8", "T5": "P7", "T6": "P8"}  # nomenclatura 10-20 revisada (ACNS 2006)
_CASE = {"FP1": "Fp1", "FP2": "Fp2", "FPZ": "Fpz", "FZ": "Fz", "CZ": "Cz", "PZ": "Pz", "OZ": "Oz"}


def canonical_electrode(name: str) -> str:
    """'fp1' -> 'Fp1', 'T3' -> 'T7'."""
    raw = str(name).strip().replace(" ", "").upper()
    raw = _ALIASES.get(raw, raw)
    return _CASE.get(raw, raw[:1] + raw[1:].lower() if raw[:1].isalpha() else raw)


def electrode_point(name: str) -> Optional[Tuple[str, np.ndarray]]:
    """(rótulo, posición en mm) de un electrodo ("C3") o de una derivación
    bipolar ("P4-O2": el punto medio de ambos, llevado al cuero cabelludo).
    Ubicar una bipolar en su punto medio es una convención de dibujo: la
    señal es la diferencia entre los dos electrodos, no un registro ahí.
    Si la referencia no está en el 10-20 del modelo ("C4-A1": oreja), se ubica
    en el electrodo activo y el rótulo la conserva (el aporte la llamaba "C4")."""
    head = load_head()
    pos = {n: np.asarray(head.electrode_xyz[i], dtype=np.float64) for i, n in enumerate(head.electrode_names)}
    parts = [p for p in str(name).strip().replace(" ", "").replace("–", "-").split("-") if p]
    if len(parts) == 2:
        a, b = canonical_electrode(parts[0]), canonical_electrode(parts[1])
        if a in pos and b in pos:
            mid = (pos[a] + pos[b]) / 2.0 - HEAD_CENTER
            r = (np.linalg.norm(pos[a] - HEAD_CENTER) + np.linalg.norm(pos[b] - HEAD_CENTER)) / 2.0
            return f"{a}-{b}", HEAD_CENTER + mid / np.linalg.norm(mid) * r
        if a in pos:
            return f"{a}-{b}", pos[a]
    c = canonical_electrode(parts[0]) if parts else ""
    return (c, pos[c]) if c in pos else None


def head_figure(*, values: Optional[Mapping[str, float]] = None, value_label: str = "Valor",
                value_format: str = ".2f", show_brain: bool = True, show_labels: bool = True,
                camera: str = "oblique", height: int = 560):
    """Cuero cabelludo fsaverage, cerebro MNI152 y las posiciones estándar de
    los electrodos 10-20 (MNE). Sin `values`: referencia estática, sin EEG.

    Con `values` ({electrodo o bipolar: valor}) y al menos `MAP_MIN_POINTS`
    puntos, colorea el cuero cabelludo con `spherical_spline`. Más allá de
    `MAP_REACH_MM` de todo electrodo queda gris. El spline puede pasarse del
    rango medido entre electrodos (sobreoscilación): se recorta al mínimo y
    máximo medidos y la fracción recortada de la zona coloreada va en
    `fig.layout.meta["clipped_fraction"]` para que la interfaz la declare.
    `camera="auto"`: de lado si todos los puntos caen en un hemisferio."""
    import plotly.graph_objects as go

    head = load_head()
    scalp = head["scalp_lo"] if "scalp_lo" in head.meshes else head["scalp"]
    fig = go.Figure()
    if show_brain:
        brain = head["brain"]
        fig.add_trace(_mesh_trace(brain, color=TISSUE_COLOR["brain"], hover=f"<b>{brain.label}</b><extra></extra>"))
    points: Dict[str, Tuple[np.ndarray, float]] = {}
    for name, v in (values or {}).items():
        hit = electrode_point(name) if v is not None and np.isfinite(v) else None
        if hit is not None:
            points[hit[0]] = (hit[1], float(v))
    mapped, clipped = len(points) >= MAP_MIN_POINTS, 0.0
    if mapped:
        src = np.stack([p for p, _ in points.values()])
        vals = np.array([v for _, v in points.values()])
        lo, hi = float(vals.min()), float(vals.max())
        raw = spherical_spline(src, vals, scalp.vertices)
        near = np.min(np.linalg.norm(scalp.vertices[:, None, :] - src[None, :, :], axis=2), axis=1) <= MAP_REACH_MM
        clipped = float(np.mean((raw[near] < lo) | (raw[near] > hi))) if near.any() else 0.0
        level = np.where(near, 0.1 + 0.9 * (np.clip(raw, lo, hi) - lo) / ((hi - lo) or 1.0), 0.0)
        scale = [[0.0, SCALP_COLOR], [0.08, SCALP_COLOR]] + [[0.1 + 0.9 * s, c] for s, c in SEQUENTIAL_BLUE]
        fig.add_trace(_mesh_trace(scalp, color=SCALP_COLOR, opacity=0.55 if show_brain else 1.0, intensity=level,
                                  colorscale=scale, name="Mapa sobre el cuero cabelludo",
                                  hover="<b>Cabeza (plantilla)</b><extra></extra>"))
        # Barra de color con los valores reales (traza auxiliar invisible).
        fig.add_trace(go.Scatter3d(
            x=[float(src[0, 0])], y=[float(src[0, 1])], z=[float(src[0, 2])], mode="markers", hoverinfo="skip",
            showlegend=False, name="Escala",
            marker=dict(size=0.1, opacity=0, color=[lo], cmin=lo, cmax=hi, colorscale=SEQUENTIAL_BLUE,
                        showscale=True, colorbar=dict(title=dict(text=value_label, side="right",
                                                                 font=dict(color=INK_2, size=12)),
                                                      tickfont=dict(color=INK_2, size=11), thickness=12,
                                                      len=0.6, outlinewidth=0, x=1.0))))
    else:
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
    if points:
        labels = list(points)
        p = np.stack([points[n][0] for n in labels])
        p = p + (p - HEAD_CENTER) / np.linalg.norm(p - HEAD_CENTER, axis=1, keepdims=True) * 5.0
        vals = [points[n][1] for n in labels]
        fig.add_trace(go.Scatter3d(
            x=p[:, 0], y=p[:, 1], z=p[:, 2], mode="markers", name="Medido", text=labels, customdata=vals,
            marker=dict(size=9, color=vals, colorscale=SEQUENTIAL_BLUE, cmin=min(vals), cmax=max(vals),
                        line=dict(color=INK, width=2)),
            hovertemplate=f"<b>%{{text}}</b><br>{value_label}: %{{customdata:{value_format}}}<extra></extra>"))
    if camera == "auto":
        cx = float(np.mean([pt[0][0] for pt in points.values()]) - HEAD_CENTER[0]) if points else 0.0
        camera = "oblique" if abs(cx) <= 15.0 else ("right" if cx > 0 else "left")
    fig.update_layout(**_scene_layout(camera, height, uirevision=f"head3d-{camera}"))
    fig.layout.meta = {"mapped": mapped, "points": len(points), "clipped_fraction": clipped}
    return fig
