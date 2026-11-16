"""Dónde va cada electrodo: posiciones 10-20 y 10-10 sobre una cabeza esférica ideal (para el diagrama).

El sistema 10-20 coloca los electrodos midiendo la cabeza desde cuatro puntos externos (nasion, inion y los
dos preauriculares) y tomando el 10 o el 20 % de esas medidas; el 10-10 agrega electrodos a medio camino entre
los del 10-20, en pasos del 10 % (glosario IFCN, Kane et al. 2017). De nasion a inion: Fpz al 10 %, y Fz, Cz, Pz
y Oz cada 20 %, con Oz al 10 % del inion (Seeck et al. 2017). En una esfera eso da ángulos fijos:

- La línea media de nasion a inion es media vuelta (180°): cada 10 % son 18°. Fpz queda a 72° del vértice (Cz)
  hacia adelante, Fz a 36°, Cz en el vértice, Pz a 36° hacia atrás y Oz a 72°. Lo mismo de oreja a oreja: T7
  a 72°, C3 a 36°.
- El anillo a 72° del vértice (Fpz, Fp1, F7, T7, P7, O1, Oz…) se reparte cada 18° alrededor de la cabeza; el
  anillo inferior del 10-10 (a 90°: F9, T9, TP9, P9…) igual.
- Los electrodos de en medio (F3, F5, P3…) se ponen a partes iguales del arco que une el extremo lateral con
  la línea media (F7, F5, F3, F1, Fz), sobre la circunferencia que pasa por los tres puntos de esa fila.

Es un esquema para ubicar los electrodos, no las coordenadas de una cabeza real. La proyección al plano es
azimutal equidistante: la distancia al centro del dibujo es proporcional al ángulo desde el vértice, y el
borde del círculo queda a 90° (la altura de las orejas).
"""

from __future__ import annotations

from typing import Dict, Tuple

import numpy as np

# Anillo a 72° del vértice: ángulo alrededor de la cabeza, desde el frente, positivo hacia la izquierda.
_RING_72 = {'Fpz': 0, 'Fp1': 18, 'AF7': 36, 'F7': 54, 'FT7': 72, 'T7': 90, 'TP7': 108, 'P7': 126, 'PO7': 144,
            'O1': 162, 'Oz': 180, 'Fp2': -18, 'AF8': -36, 'F8': -54, 'FT8': -72, 'T8': -90, 'TP8': -108,
            'P8': -126, 'PO8': -144, 'O2': -162}
_RING_90 = {'F9': 54, 'FT9': 72, 'T9': 90, 'TP9': 108, 'P9': 126,
            'F10': -54, 'FT10': -72, 'T10': -90, 'TP10': -108, 'P10': -126}
# Línea media: ángulo desde el vértice (positivo hacia adelante).
_MIDLINE = {'AFz': 54, 'Fz': 36, 'FCz': 18, 'Cz': 0, 'CPz': -18, 'Pz': -36, 'POz': -54}
# Filas: (extremo izquierdo, electrodos intermedios de izquierda a centro, centro, espejo derecho).
_ROWS = (
    ('AF7', ('AF3',), 'AFz', ('AF4',), 'AF8'),
    ('F7', ('F5', 'F3', 'F1'), 'Fz', ('F2', 'F4', 'F6'), 'F8'),
    ('FT7', ('FC5', 'FC3', 'FC1'), 'FCz', ('FC2', 'FC4', 'FC6'), 'FT8'),
    ('T7', ('C5', 'C3', 'C1'), 'Cz', ('C2', 'C4', 'C6'), 'T8'),
    ('TP7', ('CP5', 'CP3', 'CP1'), 'CPz', ('CP2', 'CP4', 'CP6'), 'TP8'),
    ('P7', ('P5', 'P3', 'P1'), 'Pz', ('P2', 'P4', 'P6'), 'P8'),
    ('PO7', ('PO3',), 'POz', ('PO4',), 'PO8'),
)

TEN_TWENTY = ('Fp1', 'Fp2', 'F7', 'F3', 'Fz', 'F4', 'F8', 'T7', 'C3', 'Cz', 'C4', 'T8', 'P7', 'P3', 'Pz', 'P4',
              'P8', 'O1', 'O2')


def _sphere(theta_deg: float, around_deg: float) -> np.ndarray:
    """Punto de la esfera: `theta` desde el vértice y `around` desde el frente (positivo a la izquierda)."""
    th, al = np.radians(theta_deg), np.radians(around_deg)
    return np.array([-np.sin(th) * np.sin(al), np.sin(th) * np.cos(al), np.cos(th)])   # x derecha, y frente


def _arc_point(a: np.ndarray, m: np.ndarray, b: np.ndarray, fraction: float) -> np.ndarray:
    """El punto a `fraction` del arco a→m, sobre la circunferencia que pasa por a, m y b."""
    normal = np.cross(m - a, b - a)
    normal /= np.linalg.norm(normal)
    center = np.dot(a, normal) * normal
    u = a - center
    radius = np.linalg.norm(u)
    u /= radius
    v = np.cross(normal, u)
    angle_m = np.arctan2(np.dot(m - center, v), np.dot(m - center, u))
    if angle_m < 0:
        v, angle_m = -v, -angle_m
    p = center + radius * (np.cos(fraction * angle_m) * u + np.sin(fraction * angle_m) * v)
    return p / np.linalg.norm(p)


def _build() -> Dict[str, np.ndarray]:
    pts: Dict[str, np.ndarray] = {}
    for name, around in _RING_72.items():
        pts[name] = _sphere(72, around)
    for name, around in _RING_90.items():
        pts[name] = _sphere(90, around)
    for name, theta in _MIDLINE.items():
        pts[name] = _sphere(abs(theta), 0 if theta >= 0 else 180)
    for left, inner_left, mid, inner_right, right in _ROWS:
        a, m, b = pts[left], pts[mid], pts[right]
        steps = len(inner_left) + 1
        for k, name in enumerate(inner_left, start=1):
            pts[name] = _arc_point(a, m, b, k / steps)
        for k, name in enumerate(reversed(inner_right), start=1):
            pts[name] = _arc_point(b, m, a, k / steps)
    return pts


SPHERE: Dict[str, np.ndarray] = _build()


def _project(p: np.ndarray) -> Tuple[float, float]:
    horizontal = float(np.hypot(p[0], p[1]))
    if horizontal < 1e-12:
        return 0.0, 0.0
    r = float(np.arccos(np.clip(p[2], -1.0, 1.0))) / (np.pi / 2)
    return r * float(p[0]) / horizontal, r * float(p[1]) / horizontal


# (x, y) en el plano: x hacia la derecha de la persona, y hacia la nariz; el borde del círculo es radio 1.
POSITIONS: Dict[str, Tuple[float, float]] = {name: _project(p) for name, p in SPHERE.items()}


def has_position(name: str) -> bool:
    return name in POSITIONS
