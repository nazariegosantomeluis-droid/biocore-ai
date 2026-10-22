"""Medidores con DATOS (2026-10-19): a diferencia de las láminas, aquí el
dibujo representa un resultado calculado por la app.

`news2_meter_svg()`: la escala NEWS2 (0-20) con sus tres bandas de respuesta
del Royal College of Physicians y una marca en el puntaje calculado por
`clinical.calculators.news2_score()`. Aquí los colores de ESTADO sí son los
correctos (significan riesgo), y nunca van solos: cada banda lleva su
nombre y su rango escritos (skill de dataviz: estado = color + etiqueta).
La escala es lineal (cada punto ocupa lo mismo), por eso la banda "medio"
es angosta y su rótulo va en una segunda fila, unido con una línea.
"""

from __future__ import annotations

from visualization.art import tokens as T
from visualization.art.svg import fmt, join, svg_root, text

NEWS2_MAX = 20
NEWS2_BANDS = (
    # (desde, hasta, etiqueta, color de estado, fila del rótulo)
    (0, 4, "Bajo 0–4", T.STATUS_RESERVED[0], 0),
    (5, 6, "Medio 5–6", T.STATUS_RESERVED[1], 1),
    (7, NEWS2_MAX, "Alto ≥ 7", T.STATUS_RESERVED[2], 0),
)


def news2_meter_svg(total: int, *, any_single_3: bool = False) -> str:
    W, H = 640.0, 142.0
    x0, x1, y, h = 20.0, W - 20.0, 46.0, 16.0
    unit = (x1 - x0) / (NEWS2_MAX + 1)          # cada punto ocupa una celda
    total = max(0, min(int(total), NEWS2_MAX))
    body = []
    for lo, hi, label, color, row in NEWS2_BANDS:
        bx = x0 + lo * unit
        bw = (hi - lo + 1) * unit - 2           # 2 px de separación entre bandas
        active = lo <= total <= hi
        body.append(
            f'<rect x="{fmt(bx)}" y="{fmt(y)}" width="{fmt(bw)}" height="{fmt(h)}" rx="4" fill="{color}" '
            f'fill-opacity="{0.9 if active else 0.28}"/>'
        )
        cx = bx + bw / 2
        ly = y + h + 24 + row * 26
        if row:
            body.append(f'<path d="M{fmt(cx)} {fmt(y + h + 4)}V{fmt(ly - 15)}" stroke="{T.INK_3}" stroke-width="1.2"/>')
        body.append(text(cx, ly, label, size=15, fill=T.INK if active else T.INK_2, anchor="middle",
                         weight=700 if active else 500))
    mx = x0 + (total + 0.5) * unit
    body.append(
        f'<path d="M{fmt(mx - 8)} {fmt(y - 22)}H{fmt(mx + 8)}L{fmt(mx)} {fmt(y - 9)}Z" fill="{T.INK}"/>'
    )
    anchor = "start" if total <= 1 else ("end" if total >= NEWS2_MAX - 1 else "middle")
    body.append(text(mx if anchor == "middle" else (mx - 8 if anchor == "start" else mx + 8), y - 28,
                     f"{total} puntos", size=15, fill=T.INK, anchor=anchor, weight=700))
    if any_single_3:
        body.append(text(x0, H - 6, "Un parámetro en 3: respuesta urgente aunque el total sea bajo.",
                         size=14, fill=T.INK_2))
    return svg_root(
        W, H, join(body),
        label=f"Medidor NEWS2: {total} puntos sobre 20",
        desc="Bandas del Royal College of Physicians: bajo 0 a 4, medio 5 a 6, alto 7 o más.",
    )
