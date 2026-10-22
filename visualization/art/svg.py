"""Utilidades SVG compartidas por las ilustraciones (2026-10-19).

Todo devuelve `str`. Las salidas son deterministas (mismos parámetros ->
mismo SVG, byte a byte): Streamlit no vuelve a montar un elemento cuyo
contenido no cambió entre reruns, y las pruebas pueden comparar salidas.

Nota para quien edite: el SVG se inserta con `st.markdown(...,
unsafe_allow_html=True)`. Por eso nada aquí emite líneas en blanco ni
sangría (Markdown las convertiría en párrafos o bloques de código) ni los
caracteres que el Markdown de Streamlit interpreta dentro de texto
(signo de pesos para LaTeX, tildes dobles, `:nombre:`).
"""

from __future__ import annotations

import hashlib
from html import escape
from typing import Iterable, Optional, Sequence, Tuple

import numpy as np

from visualization.art import tokens as T


def esc(text: object) -> str:
    """Escapa texto para usarlo dentro de SVG/HTML."""
    return escape(str(text), quote=True)


def uid(prefix: str, *parts: object) -> str:
    """Id determinista y corto (para <title>, <pattern>, <clipPath>)."""
    digest = hashlib.sha1("|".join(map(str, parts)).encode("utf-8")).hexdigest()[:8]
    return f"bc-{prefix}-{digest}"


def fmt(value: float) -> str:
    """Número compacto para coordenadas (1 decimal, sin ceros sobrantes)."""
    out = f"{value:.1f}"
    if out.endswith(".0"):
        out = out[:-2]
    return "0" if out == "-0" else out


def simplify(xs: np.ndarray, ys: np.ndarray, tol: float) -> tuple:
    """Ramer-Douglas-Peucker: quita los puntos que se desvían menos de `tol`
    unidades del segmento que los rodea. Con `tol` por debajo de un píxel
    el trazo se ve idéntico y el SVG pesa varias veces menos (las curvas
    suaves y los tramos planos, como una apnea, se quedan en pocos puntos)."""
    n = xs.size
    if n < 3 or tol <= 0:
        return xs, ys
    keep = np.zeros(n, dtype=bool)
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    while stack:
        a, b = stack.pop()
        if b - a < 2:
            continue
        dx, dy = xs[b] - xs[a], ys[b] - ys[a]
        seg = np.hypot(dx, dy) or 1e-12
        idx = np.arange(a + 1, b)
        dist = np.abs(dy * (xs[idx] - xs[a]) - dx * (ys[idx] - ys[a])) / seg
        k = int(np.argmax(dist))
        if dist[k] > tol:
            m = a + 1 + k
            keep[m] = True
            stack.append((a, m))
            stack.append((m, b))
    return xs[keep], ys[keep]


def path_from_xy(xs: Sequence[float], ys: Sequence[float], tol: float = 0.3) -> str:
    """`d` de un <path> que une los puntos (x, y) en orden (simplificado con
    `simplify(tol)`; `tol=0` conserva todos los puntos)."""
    xs = np.asarray(xs, dtype=float)
    ys = np.asarray(ys, dtype=float)
    if xs.size == 0:
        return ""
    xs, ys = simplify(xs, ys, tol)
    parts = [f"M{fmt(xs[0])} {fmt(ys[0])}"]
    parts.extend(f"L{fmt(x)} {fmt(y)}" for x, y in zip(xs[1:], ys[1:]))
    return "".join(parts)


def map_signal(
    t: np.ndarray,
    v: np.ndarray,
    *,
    x0: float,
    width: float,
    y_mid: float,
    px_per_unit: float,
    t_start: Optional[float] = None,
    t_end: Optional[float] = None,
) -> tuple:
    """Proyecta una señal (t, v) a coordenadas SVG (y crece hacia abajo)."""
    t = np.asarray(t, dtype=float)
    v = np.asarray(v, dtype=float)
    t_start = float(t[0]) if t_start is None else t_start
    t_end = float(t[-1]) if t_end is None else t_end
    span = max(t_end - t_start, 1e-9)
    xs = x0 + (t - t_start) / span * width
    ys = y_mid - v * px_per_unit
    return xs, ys


def trace(d: str, *, color: str = T.TRACE, width: float = 2.0, opacity: float = 1.0,
          extra: str = "") -> str:
    op = "" if opacity >= 1 else f' stroke-opacity="{opacity:g}"'
    return (
        f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width:g}"{op} '
        f'stroke-linecap="round" stroke-linejoin="round"{(" " + extra) if extra else ""}/>'
    )


def text(x: float, y: float, content: object, *, size: float = 13, fill: str = T.INK_2,
         anchor: str = "start", weight: int = 400, family: str = T.FONT_BODY,
         extra: str = "", halo: Optional[str] = None) -> str:
    """<text>. `halo` = color de fondo: dibuja un contorno de ese color
    detrás de las letras para que se lean encima de líneas o rellenos."""
    halo_attr = (
        f' paint-order="stroke" stroke="{halo}" stroke-width="5" stroke-linejoin="round"' if halo else ""
    )
    return (
        f'<text x="{fmt(x)}" y="{fmt(y)}" font-size="{size:g}" fill="{fill}" '
        f'text-anchor="{anchor}" font-weight="{weight}" font-family="{family}"{halo_attr}'
        f'{(" " + extra) if extra else ""}>{esc(content)}</text>'
    )


def smooth_path(points: Sequence[Tuple[float, float]], closed: bool = True) -> str:
    """Curva suave que pasa por los puntos (Catmull-Rom convertida a Bézier
    cúbica). Permite dibujar contornos anatómicos razonando con puntos."""
    pts = np.asarray(points, dtype=float)
    n = len(pts)
    if n < 2:
        return ""
    d = [f"M{fmt(pts[0][0])} {fmt(pts[0][1])}"]
    last = n if closed else n - 1
    for i in range(last):
        p0 = pts[(i - 1) % n] if (closed or i > 0) else pts[0]
        p1 = pts[i]
        p2 = pts[(i + 1) % n]
        p3 = pts[(i + 2) % n] if (closed or i + 2 < n) else pts[-1]
        c1 = p1 + (p2 - p0) / 6.0
        c2 = p2 - (p3 - p1) / 6.0
        d.append(f"C{fmt(c1[0])} {fmt(c1[1])} {fmt(c2[0])} {fmt(c2[1])} {fmt(p2[0])} {fmt(p2[1])}")
    if closed:
        d.append("Z")
    return "".join(d)


def mm_grid(x: float, y: float, w: float, h: float, mm_px: float, *, key: str,
            minor_opacity: float = T.GRID_MINOR_OPACITY,
            major_opacity: float = T.GRID_MAJOR_OPACITY) -> str:
    """Retícula de papel de ECG: cuadro pequeño = 1 mm, grande = 5 mm.

    `<pattern>` en vez de cientos de líneas: el SVG sigue pesando poco.
    `key` debe distinguir retículas de tamaño distinto en la misma página.
    """
    pid = uid("grid", key, mm_px)
    big = 5 * mm_px
    minor = "".join(
        f'<path d="M{fmt(i * mm_px)} 0V{fmt(big)}M0 {fmt(i * mm_px)}H{fmt(big)}" '
        f'stroke="{T.GRID}" stroke-opacity="{minor_opacity:g}" stroke-width="1"/>'
        for i in range(1, 5)
    )
    major = (
        f'<path d="M0 0H{fmt(big)}M0 0V{fmt(big)}" stroke="{T.GRID}" '
        f'stroke-opacity="{major_opacity:g}" stroke-width="1.2"/>'
    )
    return (
        f'<defs><pattern id="{pid}" width="{fmt(big)}" height="{fmt(big)}" '
        f'patternUnits="userSpaceOnUse" x="{fmt(x)}" y="{fmt(y)}">{minor}{major}</pattern></defs>'
        f'<rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{fmt(h)}" fill="url(#{pid})"/>'
    )


def svg_root(width: float, height: float, body: str, *, label: str, desc: str = "",
             cls: str = "", preserve: str = "xMidYMid meet", style: str = "") -> str:
    """Raíz SVG accesible: role="img" + <title> + <desc> enlazados por id."""
    tid = uid("t", label, width, height, len(body))
    did = tid.replace("-t-", "-d-")
    labelled = f'{tid} {did}' if desc else tid
    desc_el = f'<desc id="{did}">{esc(desc)}</desc>' if desc else ""
    cls_attr = f' class="{cls}"' if cls else ""
    style_attr = f' style="{style}"' if style else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {fmt(width)} {fmt(height)}" '
        f'role="img" aria-labelledby="{labelled}" preserveAspectRatio="{preserve}"{cls_attr}{style_attr}>'
        f'<title id="{tid}">{esc(label)}</title>{desc_el}{body}</svg>'
    )


def join(parts: Iterable[str]) -> str:
    return "".join(p for p in parts if p)
