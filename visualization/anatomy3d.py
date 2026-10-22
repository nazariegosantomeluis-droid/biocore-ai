"""Anatomía 3D real (2026-10-21).

Carga las mallas que construye `tools/build_anatomy3d.py` -- datos reales,
no dibujos -- y arma figuras Plotly interactivas para la app:

- `body_figure()`: cuerpo reconstruido de una tomografía real de cuerpo
  completo (TotalSegmentator, sujeto s1397, CC BY 4.0): esqueleto, corazón y
  vasos, pulmones, encéfalo y médula, músculos, órganos abdominales y piel.
  Los órganos del gemelo digital pueden colorearse por su estado.
- `head_figure()`: cabeza y cerebro de la plantilla MNI ICBM 152 con el
  sistema 10-20; si recibe valores por electrodo, los interpola sobre el
  cuero cabelludo con splines esféricos (Perrin et al. 1989), como un mapa
  topográfico de EEG.
- `mesh_figure()`: cualquier malla (p. ej., la que el usuario reconstruye
  de su propia TC/RM en "Crea tu modelo 3D").

Coordenadas: RAS+ en mm (x hacia la derecha del paciente, y hacia anterior,
z hacia arriba). Sin Streamlit aquí; las páginas llaman a estas funciones.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, Mapping, Optional, Sequence, Tuple

import numpy as np

ASSET_DIR = Path(__file__).resolve().parents[1] / "data" / "anatomy3d"
BODY_FILE = "body_ts_s1397.npz"
HEAD_FILE = "head_mni152.npz"

PANEL_BG = "#0f172a"   # = PALETTE.BACKGROUND
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

    @property
    def center(self) -> np.ndarray:
        return self.vertices.mean(axis=0)


@dataclass(frozen=True)
class Anatomy:
    kind: str
    meta: dict
    meshes: Mapping[str, Mesh]
    electrode_names: Tuple[str, ...] = ()
    electrode_xyz: Optional[np.ndarray] = None
    # V1-V6 calculadas sobre la TC (mm relativos al origen) y su normal.
    landmarks: Mapping[str, np.ndarray] = None  # type: ignore[assignment]
    landmark_normals: Mapping[str, np.ndarray] = None  # type: ignore[assignment]

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
            v = z[f"{key}__v"].astype(np.float32) * scale
            f = z[f"{key}__f"]
            meshes[key] = Mesh(key=key, label=part["label"], system=part["system"], vertices=v, faces=f,
                               volume_ml=part.get("volume_ml"))
        names: Tuple[str, ...] = tuple(meta.get("electrodes", ()))
        xyz = z["electrodes__xyz"].astype(np.float32) if "electrodes__xyz" in z.files else None
        lm_names = [lm["name"] for lm in meta.get("landmarks", [])]
        landmarks, normals = {}, {}
        if lm_names and "landmarks__xyz" in z.files:
            landmarks = dict(zip(lm_names, z["landmarks__xyz"].astype(np.float32)))
            normals = dict(zip(lm_names, z["landmarks__normal"].astype(np.float32)))
    if xyz is not None:
        xyz = xyz - np.asarray(meta["origin_mm"], dtype=np.float32)
    return Anatomy(kind=meta["kind"], meta=meta, meshes=meshes, electrode_names=names, electrode_xyz=xyz,
                   landmarks=landmarks, landmark_normals=normals)


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


def body_counts() -> Tuple[int, int]:
    """(superficies, segmentaciones de la TC que las forman), leídos del archivo.
    La piel no es una segmentación (sale del umbral de la TC) y no se cuenta."""
    body = load_body()
    sources = {s for p in body.meta.get("parts", []) for s in p.get("sources", []) if ".nii" not in s}
    return len(body.meshes), len(sources)


# ─────────────────────────────────────────────────────────────────────────
# Capas, colores de tejido y órganos del gemelo
# ─────────────────────────────────────────────────────────────────────────

SYSTEM_LABELS: Dict[str, str] = {
    "skeleton": "Esqueleto",
    "circulatory": "Corazón y vasos",
    "respiratory": "Pulmones y tráquea",
    "nervous": "Encéfalo y médula",
    "muscular": "Músculos",
    "abdominal": "Abdomen y pelvis",
    "skin": "Piel",
}
DEFAULT_SYSTEMS: Tuple[str, ...] = ("skeleton", "circulatory", "respiratory", "nervous", "muscular", "skin")

# Colores de tejido (anatomía, no estados clínicos: el verde/ámbar/rojo de
# PALETTE.STABLE/WARNING/CRITICAL queda reservado para el estado del gemelo).
TISSUE_COLOR: Dict[str, str] = {
    "skull": "#e9dec7", "spine": "#e9dec7", "ribs": "#e9dec7", "sternum": "#e9dec7",
    "costal_cartilages": "#b8d2dc", "shoulder_girdle": "#e9dec7", "humeri": "#e9dec7",
    "pelvis": "#e9dec7", "femurs": "#e9dec7",
    "heart": "#c0394c", "arteries": "#d9475a", "veins": "#5872c9", "pulmonary_veins": "#e06478",
    "lung_right": "#eeb0ab", "lung_left": "#eeb0ab", "trachea": "#ecd2c0",
    "brain": "#ecc0b4", "spinal_cord": "#f1d78b",
    "back_muscles": "#b4493f", "iliopsoas": "#b4493f", "gluteals": "#b4493f",
    "liver": "#9a3b31", "gallbladder": "#7f9e4a", "stomach": "#dba796", "esophagus": "#d38e80",
    "duodenum": "#e0ae99", "small_bowel": "#e3b19c", "colon": "#cf9c84", "pancreas": "#e6c086",
    "spleen": "#93405a", "kidneys": "#a54a3c", "adrenals": "#ddb05f", "bladder": "#e2c497",
    "prostate": "#c27e6c", "thyroid": "#bd5649",
    "skin": "#a9bad6",
}

# Órgano del gemelo -> partes de la malla que lo representan.
TWIN_ORGAN_PARTS: Dict[str, Tuple[str, ...]] = {
    "heart": ("heart", "arteries", "veins", "pulmonary_veins"),
    "lungs": ("lung_right", "lung_left", "trachea"),
    "brain": ("brain",),
    "muscles": ("back_muscles", "iliopsoas", "gluteals"),
    # El sistema autónomo no se ve en una TC: se resalta la médula espinal,
    # de donde sale la vía simpática (T1-L2).
    "autonomic": ("spinal_cord",),
}

LIGHTING = dict(ambient=0.42, diffuse=0.78, specular=0.32, roughness=0.42, fresnel=0.22)
LIGHT_POSITION = dict(x=-1200, y=2600, z=2200)

CAMERAS: Dict[str, dict] = {
    "front": dict(eye=dict(x=0.0, y=1.85, z=0.12), up=dict(x=0, y=0, z=1)),
    "back": dict(eye=dict(x=0.0, y=-1.85, z=0.12), up=dict(x=0, y=0, z=1)),
    "left": dict(eye=dict(x=-1.85, y=0.0, z=0.12), up=dict(x=0, y=0, z=1)),
    "right": dict(eye=dict(x=1.85, y=0.0, z=0.12), up=dict(x=0, y=0, z=1)),
    "oblique": dict(eye=dict(x=-1.2, y=1.45, z=0.35), up=dict(x=0, y=0, z=1)),
    "top": dict(eye=dict(x=0.0, y=0.05, z=1.9), up=dict(x=0, y=1, z=0)),
}
# Cortas a propósito: caben las cuatro en un control segmentado a 390 px.
CAMERA_LABELS: Dict[str, str] = {
    "front": "Frente", "oblique": "Oblicua", "left": "Izquierda",
    "right": "Derecha", "back": "Detrás", "top": "Arriba",
}


def _blend(hex_color: str, toward: str, amount: float) -> str:
    a = np.array([int(hex_color[i:i + 2], 16) for i in (1, 3, 5)], dtype=float)
    b = np.array([int(toward[i:i + 2], 16) for i in (1, 3, 5)], dtype=float)
    c = np.clip(np.round(a + (b - a) * amount), 0, 255).astype(int)
    return "#" + "".join(f"{x:02x}" for x in c)


def _scene_layout(camera, height: int, *, aspect: str = "data", uirevision: str = "anatomy3d") -> dict:
    axis = dict(visible=False, showbackground=False, showgrid=False, zeroline=False,
                showspikes=False, title="")
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
                intensity: Optional[np.ndarray] = None, colorscale=None, cmin=None, cmax=None,
                colorbar: Optional[dict] = None, name: Optional[str] = None):
    import plotly.graph_objects as go

    v, f = mesh.vertices, mesh.faces
    kwargs = dict(
        x=v[:, 0], y=v[:, 1], z=v[:, 2],
        i=f[:, 0], j=f[:, 1], k=f[:, 2],
        name=name or mesh.label,
        opacity=opacity,
        flatshading=False,
        lighting=LIGHTING,
        lightposition=LIGHT_POSITION,
        hovertemplate=hover if hover is not None else f"<b>{mesh.label}</b><extra></extra>",
        showscale=False,
    )
    if intensity is not None:
        kwargs.update(intensity=intensity, colorscale=colorscale, cmin=cmin, cmax=cmax,
                      showscale=colorbar is not None, intensitymode="vertex")
        if colorbar is not None:
            kwargs["colorbar"] = colorbar
    else:
        kwargs["color"] = color
    return go.Mesh3d(**kwargs)


def part_hover(mesh: Mesh, extra: str = "") -> str:
    vol = f"<br>Volumen en esta TC: {mesh.volume_ml:,.0f} mL".replace(",", " ") if mesh.volume_ml else ""
    return f"<b>{mesh.label}</b>{vol}{extra}<extra></extra>"


def body_figure(
    *,
    systems: Iterable[str] = DEFAULT_SYSTEMS,
    highlight: Sequence[str] = (),
    part_colors: Optional[Mapping[str, str]] = None,
    part_notes: Optional[Mapping[str, str]] = None,
    dim_others: bool = True,
    camera: str = "front",
    height: int = 640,
    skin_opacity: float = 0.12,
):
    """Cuerpo 3D de la TC real.

    `highlight`: claves de partes a resaltar (las demás se atenúan si
    `dim_others`). `part_colors`: color por parte (p. ej., el estado del
    órgano del gemelo); por defecto, color de tejido. `part_notes`: texto
    extra para el hover de cada parte (p. ej., "Estado: estable").
    """
    import plotly.graph_objects as go

    anat = load_body()
    systems = set(systems)
    highlight = tuple(highlight)
    part_colors = dict(part_colors or {})
    part_notes = dict(part_notes or {})
    fig = go.Figure()
    for mesh in anat.meshes.values():
        if mesh.system not in systems and mesh.key not in highlight:
            continue
        color = part_colors.get(mesh.key, TISSUE_COLOR.get(mesh.key, "#c8cfdc"))
        if mesh.system == "skin":
            opacity = skin_opacity
        elif highlight and dim_others and mesh.key not in highlight:
            color = _blend(color, "#8090b0", 0.55)
            opacity = 0.16
        else:
            opacity = 1.0
        note = part_notes.get(mesh.key, "")
        fig.add_trace(_mesh_trace(mesh, color=color, opacity=opacity,
                                  hover=part_hover(mesh, f"<br>{note}" if note else "")))
    fig.update_layout(**_scene_layout(camera, height, uirevision="body3d"))
    return fig


def organ_figure(parts: Sequence[str], *, context: Sequence[str] = (), camera: str = "oblique",
                 height: int = 460, colors: Optional[Mapping[str, str]] = None):
    """Primer plano de unas partes (p. ej., el corazón y sus vasos), con
    otras partes como contexto atenuado."""
    import plotly.graph_objects as go

    anat = load_body()
    colors = dict(colors or {})
    fig = go.Figure()
    for key in context:
        if key in anat.meshes:
            m = anat[key]
            fig.add_trace(_mesh_trace(m, color=_blend(TISSUE_COLOR.get(key, "#c8cfdc"), "#8090b0", 0.5),
                                      opacity=0.22, hover=part_hover(m)))
    for key in parts:
        if key in anat.meshes:
            m = anat[key]
            fig.add_trace(_mesh_trace(m, color=colors.get(key, TISSUE_COLOR.get(key, "#c8cfdc")),
                                      hover=part_hover(m)))
    fig.update_layout(**_scene_layout(camera, height, uirevision="organ3d:" + ",".join(parts)))
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
# Cabeza: 10-20 y mapa topográfico (splines esféricos)
# ─────────────────────────────────────────────────────────────────────────

HEAD_CENTER = np.array([0.0, -18.0, 12.0], dtype=np.float64)  # centro de la bóveda (MNI, mm)

# Rampa secuencial de un solo tono (azul), de oscuro (poco) a claro (mucho):
# en fondo oscuro el valor bajo se funde con la superficie.
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
    """Interpolación por splines esféricos (Perrin et al., 1989), la usada
    para mapas topográficos de EEG: proyecta electrodos y puntos destino a
    la esfera unitaria y resuelve el sistema [G 1; 1ᵀ 0][c; c0] = [v; 0]."""
    def unit(p):
        d = np.asarray(p, dtype=float) - center
        return d / np.linalg.norm(d, axis=1, keepdims=True)

    s, d = unit(src_xyz), unit(dst_xyz)
    values = np.asarray(values, dtype=float)
    n = s.shape[0]
    g = _legendre_g(s @ s.T, m, n_terms) + smoothing * np.eye(n)
    a = np.zeros((n + 1, n + 1))
    a[:n, :n] = g
    a[:n, n] = 1.0
    a[n, :n] = 1.0
    coef = np.linalg.solve(a, np.concatenate([values, [0.0]]))
    return _legendre_g(d @ s.T, m, n_terms) @ coef[:n] + coef[n]


def electrode_positions(names: Optional[Iterable[str]] = None) -> Dict[str, np.ndarray]:
    """Posición (mm, MNI) de cada electrodo 10-20 sobre el cuero cabelludo."""
    head = load_head()
    out = {n: head.electrode_xyz[i] for i, n in enumerate(head.electrode_names)}
    if names is None:
        return out
    wanted = {canonical_electrode(n) for n in names}
    return {n: p for n, p in out.items() if n in wanted}


_ALIASES = {"T3": "T7", "T4": "T8", "T5": "P7", "T6": "P8"}


def canonical_electrode(name: str) -> str:
    """'fp1' -> 'Fp1', 'T3' -> 'T7' (nomenclatura 10-20 revisada, ACNS 2006)."""
    raw = str(name).strip().replace(" ", "")
    raw = raw.split("-")[0]  # "Fp1-Ref" o "P4-O2" -> primer electrodo
    raw = raw.upper()
    raw = _ALIASES.get(raw, raw)
    fixes = {"FP1": "Fp1", "FP2": "Fp2", "FPZ": "Fpz", "FZ": "Fz", "CZ": "Cz", "PZ": "Pz", "OZ": "Oz"}
    return fixes.get(raw, raw[:1] + raw[1:].lower() if raw[:1].isalpha() else raw)


MAP_MIN_POINTS = 4
MAP_REACH_MM = 45.0     # más lejos de cualquier electrodo, el mapa no se colorea (gris)
SCALP_NEUTRAL = "#b3bfd2"


def electrode_point(name: str) -> Optional[Tuple[str, np.ndarray]]:
    """(rótulo, posición en mm) de un electrodo ("C3") o de una derivación
    bipolar ("P4-O2": punto medio de ambos, llevado al cuero cabelludo)."""
    head = load_head()
    pos = {n: head.electrode_xyz[i] for i, n in enumerate(head.electrode_names)}
    raw = str(name).strip().replace(" ", "")
    parts = [p for p in raw.replace("–", "-").split("-") if p]
    if len(parts) == 2:
        a, b = canonical_electrode(parts[0]), canonical_electrode(parts[1])
        if a in pos and b in pos:
            mid = (pos[a] + pos[b]) / 2.0
            d = mid - HEAD_CENTER
            r = np.mean([np.linalg.norm(pos[a] - HEAD_CENTER), np.linalg.norm(pos[b] - HEAD_CENTER)])
            return f"{a}-{b}", (HEAD_CENTER + d / np.linalg.norm(d) * r).astype(np.float32)
    c = canonical_electrode(parts[0] if parts else raw)
    if c in pos:
        return c, pos[c]
    return None


def head_figure(
    *,
    values: Optional[Mapping[str, float]] = None,
    value_label: str = "Valor",
    value_format: str = ".2f",
    highlight: Iterable[str] = (),
    show_brain: bool = False,
    show_labels: bool = True,
    camera: str = "oblique",
    height: int = 560,
):
    """Cabeza 3D con los electrodos 10-20.

    `camera="auto"` mira hacia donde están los electrodos con datos: de lado
    si todos quedan en un hemisferio (p. ej., un montaje bipolar derecho),
    oblicua si cubren los dos.

    Con `values` ({electrodo o derivación bipolar: valor}) y al menos
    `MAP_MIN_POINTS` puntos, colorea el cuero cabelludo con la
    interpolación por splines esféricos (mapa topográfico). Donde no hay
    ningún electrodo a menos de `MAP_REACH_MM` el mapa queda en gris: ahí
    no hay datos, solo extrapolación.
    """
    import plotly.graph_objects as go

    head = load_head()
    scalp = head["scalp_lo"] if "scalp_lo" in head.meshes else head["scalp"]
    fig = go.Figure()
    if show_brain:
        brain = head["brain"]
        fig.add_trace(_mesh_trace(brain, color=TISSUE_COLOR["brain"], hover=part_hover(brain)))
    pos = {n: head.electrode_xyz[i] for i, n in enumerate(head.electrode_names)}
    points: Dict[str, Tuple[np.ndarray, float]] = {}
    for name, v in (values or {}).items():
        if v is None or not np.isfinite(v):
            continue
        hit = electrode_point(name)
        if hit is not None:
            points[hit[0]] = (hit[1], float(v))
    mapped = len(points) >= MAP_MIN_POINTS
    if mapped:
        labels = list(points)
        src = np.stack([points[n][0] for n in labels])
        vals = np.array([points[n][1] for n in labels])
        lo, hi = float(vals.min()), float(vals.max())
        span = (hi - lo) or 1.0
        inten = np.clip(spherical_spline(src, vals, scalp.vertices), lo, hi)
        # Cobertura: distancia de cada vértice al electrodo más cercano.
        dist = np.min(np.linalg.norm(scalp.vertices[:, None, :] - src[None, :, :], axis=2), axis=1)
        level = np.where(dist <= MAP_REACH_MM, 0.1 + 0.9 * (inten - lo) / span, 0.0)
        scale = [[0.0, SCALP_NEUTRAL], [0.08, SCALP_NEUTRAL]] + [[0.1 + 0.9 * s, c] for s, c in SEQUENTIAL_BLUE]
        trace = _mesh_trace(scalp, color=SCALP_NEUTRAL, opacity=0.55 if show_brain else 1.0, intensity=level,
                            colorscale=scale, cmin=0.0, cmax=1.0, colorbar=None,
                            hover="<b>Cabeza</b><extra></extra>", name="Mapa sobre el cuero cabelludo")
        fig.add_trace(trace)
        # Barra de color con los valores reales (traza auxiliar invisible).
        fig.add_trace(go.Scatter3d(
            x=[float(src[0, 0])], y=[float(src[0, 1])], z=[float(src[0, 2])], mode="markers", hoverinfo="skip",
            showlegend=False, marker=dict(size=0.1, opacity=0, color=[lo], cmin=lo, cmax=hi,
                                          colorscale=SEQUENTIAL_BLUE, showscale=True,
                                          colorbar=dict(title=dict(text=value_label, side="right",
                                                                   font=dict(color=INK_2, size=12)),
                                                        tickfont=dict(color=INK_2, size=11), thickness=12,
                                                        len=0.6, outlinewidth=0, x=1.0))))
    else:
        fig.add_trace(_mesh_trace(scalp, color=SCALP_NEUTRAL, opacity=0.28 if show_brain else 1.0,
                                  hover="<b>Cabeza</b><extra></extra>"))
    hot = {canonical_electrode(h) for h in highlight}
    names = list(pos)
    xyz = np.stack([pos[n] for n in names])
    out = xyz - HEAD_CENTER
    out = out / np.linalg.norm(out, axis=1, keepdims=True)
    mk = xyz + out * 3.0
    lab = xyz + out * 11.0
    fig.add_trace(go.Scatter3d(
        x=mk[:, 0], y=mk[:, 1], z=mk[:, 2], mode="markers",
        marker=dict(size=[6 if n in hot else 4 for n in names],
                    color=["#22d3ee" if n in hot else "#f1f5f9" for n in names],
                    line=dict(color="#0b1426", width=1)),
        hovertemplate=[f"<b>{n}</b><extra></extra>" for n in names], name="Electrodos 10-20"))
    if show_labels:
        fig.add_trace(go.Scatter3d(
            x=lab[:, 0], y=lab[:, 1], z=lab[:, 2], mode="text", text=names,
            textfont=dict(color=[INK if n in hot else INK_2 for n in names], size=12,
                          family="Figtree, Noto Sans, sans-serif"),
            hoverinfo="skip", name="Nombres"))
    if points:
        labels = list(points)
        p = np.stack([points[n][0] for n in labels])
        d = p - HEAD_CENTER
        p = p + d / np.linalg.norm(d, axis=1, keepdims=True) * 5.0
        vals = [points[n][1] for n in labels]
        fig.add_trace(go.Scatter3d(
            x=p[:, 0], y=p[:, 1], z=p[:, 2], mode="markers",
            marker=dict(size=9, color=vals, colorscale=SEQUENTIAL_BLUE, cmin=min(vals), cmax=max(vals),
                        line=dict(color="#e0e7ff", width=2)),
            text=labels, customdata=vals, name="Medido",
            hovertemplate=f"<b>%{{text}}</b><br>{value_label}: %{{customdata:{value_format}}}<extra></extra>"))
    if camera == "auto":
        camera = "oblique"
        if points:
            cx = float(np.mean([pt[0][0] for pt in points.values()]) - HEAD_CENTER[0])
            if abs(cx) > 15.0:
                camera = "right" if cx > 0 else "left"
    layout = _scene_layout(camera, height, uirevision=f"head3d-{camera}")
    fig.update_layout(**layout)
    fig.layout.meta = {"mapped": mapped, "points": len(points)}
    return fig
