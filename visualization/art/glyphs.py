"""Íconos de trazo dibujados para BIOCORE AI (2026-10-19).

Reemplazan a los emoji en los títulos de módulo y en las tarjetas de órgano
de Digital Twin OS (UI UX Pro Max: "no emoji como íconos": cada sistema
operativo dibuja el emoji distinto, no se puede colorear por estado y los
lectores de pantalla leen su nombre en inglés).

- `module_glyph_svg(kind)`: 24×24, trazo `currentColor` de 1.75 px.
- `organ_glyph_svg(organ_id, color)`: 48×48, trazo + relleno tenue del
  color que se le pase (el color de estado lo decide quien llama).

Los dibujos son originales (no copiados de una librería de íconos).
"""

from __future__ import annotations

from typing import Dict

from visualization.art.svg import esc

# ─── Íconos de módulo (viewBox 0 0 24 24) ────────────────────────────────

MODULE_GLYPHS: Dict[str, str] = {
    # Cuerpo con un trazo de pulso en el pecho: el gemelo "vivo".
    "twin": (
        '<circle cx="12" cy="6" r="3"/>'
        '<path d="M5 21v-2.6a7 7 0 0 1 14 0V21"/>'
        '<path d="M7.6 16.6h2l1-2.1 1.5 4.2 1.2-3.1.8 1h2.3"/>'
    ),
    # Libro abierto con un latido en la página derecha.
    "academia": (
        '<path d="M3 6.4c2.6-1 5.6-1 9 .7 3.4-1.7 6.4-1.7 9-.7v12c-2.6-1-5.6-1-9 .7-3.4-1.7-6.4-1.7-9-.7z"/>'
        '<path d="M12 7.1v12"/>'
        '<path d="M14.2 12.6h1.2l.8-1.7 1.1 3.3.8-1.6h1.3"/>'
    ),
    # Corazón con la tira de ECG que lo cruza.
    "ecg": (
        '<path d="M12 20.3C6.3 16.6 3.2 13.4 3.2 9.8 3.2 7.2 5.2 5.2 7.7 5.2c1.8 0 3.3 1 4.3 2.4 1-1.4 2.5-2.4 4.3-2.4 2.5 0 4.5 2 4.5 4.6 0 3.6-3.1 6.8-8.8 10.5z"/>'
        '<path d="M1.8 12.4h5.4l1.3-2.3 1.9 5.1 1.9-7.4 1.5 4.6h8.4"/>'
    ),
    # Tres carriles: pulso, ECG y respiración (fusión de sensores).
    "multisensor": (
        '<path d="M3 6.5c1.6 0 2-2.2 3.6-2.2s2 2.2 3.6 2.2 2-2.2 3.6-2.2 2 2.2 3.6 2.2 1.6-1 2.6-1.6"/>'
        '<path d="M3 12h4.3l1.3-2.6 1.8 5.4 1.6-4 1 1.2H21"/>'
        '<path d="M3 18.5c2.4 0 3-2 6-2s3.6 2 6 2 3.4-1.4 6-1.6"/>'
    ),
    # Pulmones con tráquea y bronquios principales.
    "respiratory": (
        '<path d="M12 3v7.5"/><path d="M12 10.5 9.6 12.6M12 10.5l2.4 2.1"/>'
        '<path d="M9.3 7.4C6 7.6 3.6 11.2 3.6 15.6c0 2.9 1.4 4.9 3.9 4.9 1.9 0 2.6-1.4 2.6-3.4v-7.6"/>'
        '<path d="M14.7 7.4c3.3.2 5.7 3.8 5.7 8.2 0 2.9-1.4 4.9-3.9 4.9-1.9 0-2.6-1.4-2.6-3.4v-7.6"/>'
    ),
    # Cabeza vista desde arriba con electrodos (el mapa 10-20 en miniatura).
    "eeg": (
        '<circle cx="12" cy="13" r="8.2"/>'
        '<path d="M10.2 4.9 12 2.7l1.8 2.2"/>'
        '<path d="M3.8 11.2c-1.3.3-1.3 3.3 0 3.6M20.2 11.2c1.3.3 1.3 3.3 0 3.6"/>'
        '<circle cx="9.6" cy="8.6" r="1.1" fill="currentColor"/><circle cx="14.4" cy="8.6" r="1.1" fill="currentColor"/>'
        '<circle cx="7.9" cy="13" r="1.1" fill="currentColor"/><circle cx="12" cy="13" r="1.1" fill="currentColor"/>'
        '<circle cx="16.1" cy="13" r="1.1" fill="currentColor"/><circle cx="12" cy="17.4" r="1.1" fill="currentColor"/>'
    ),
    # Brazo flexionado (bíceps) con una ráfaga de EMG encima.
    "emg": (
        '<path d="M2.6 20.4h12.6c2.9 0 4.8-2.1 4.8-4.9V8.4c.7-.8.8-2.4 0-3.2-.9-.8-2.6-.7-3.4.2-.5.6-.4 1.6-.2 2.4v5'
        'c-1.2-2-3-3-5-3-2.2 0-4 1.1-5.2 2.8-1.2.8-2.4 1.3-3.6 1.6"/>'
        '<path d="M14.6 16.6c-1.3.8-2.7 1.2-4.1 1.2"/>'
        '<path d="M2.6 6.4h1.6l.8-2 1 4 .9-3 .7 1h1.6"/>'
    ),
    # Tacograma: cada punto es un intervalo RR.
    "hrv": (
        '<path d="M3 20.5h18"/>'
        '<path d="M4 14.5 7.4 10.6l3.4 3.2 3.4-5.4 3.4 3.6L21 8.4"/>'
        '<circle cx="4" cy="14.5" r="1.2"/><circle cx="7.4" cy="10.6" r="1.2"/><circle cx="10.8" cy="13.8" r="1.2"/>'
        '<circle cx="14.2" cy="8.4" r="1.2"/><circle cx="17.6" cy="12" r="1.2"/><circle cx="21" cy="8.4" r="1.2"/>'
    ),
    # Gota con pulso: biomarcadores derivados de señales.
    "biomarkers": (
        '<path d="M12 3.4S5.6 10.3 5.6 14.4a6.4 6.4 0 0 0 12.8 0C18.4 10.3 12 3.4 12 3.4z"/>'
        '<path d="M8.2 15h1.7l.9-2 1.3 3.8 1-1.8h2.7"/>'
    ),
    # Compás de ECG (calibrador) midiendo sobre una línea base.
    "calculators": (
        '<circle cx="12" cy="4.2" r="1.6"/>'
        '<path d="M11.2 5.6 6.6 19.6M12.8 5.6l4.6 14"/>'
        '<path d="M8.4 13.4c2.3 1 4.9 1 7.2 0"/>'
        '<path d="M3 21.2h18"/>'
    ),
    # Línea de tiempo de estados del paciente (snapshots del UPS).
    "pipeline": (
        '<circle cx="5" cy="13" r="2.2"/><circle cx="12" cy="13" r="2.2"/><circle cx="19" cy="13" r="2.2"/>'
        '<path d="M7.2 13h2.6M14.2 13h2.6"/>'
        '<path d="M5 9.2V6.4M12 9.2V4.6M19 9.2V7.6"/>'
    ),
}

GLYPH_LABELS: Dict[str, str] = {
    "twin": "Gemelo digital",
    "academia": "Academia",
    "ecg": "Electrocardiograma",
    "multisensor": "Fusión de sensores",
    "respiratory": "Respiración",
    "eeg": "Electroencefalograma",
    "emg": "Electromiografía",
    "hrv": "Variabilidad de la frecuencia cardiaca",
    "biomarkers": "Biomarcadores",
    "calculators": "Calculadoras clínicas",
    "pipeline": "Registro de estados del paciente",
}


def module_glyph_svg(kind: str, size: int = 28, stroke: float = 1.75) -> str:
    """Ícono de módulo. Decorativo (`aria-hidden`): el título ya lo nombra."""
    body = MODULE_GLYPHS.get(kind)
    if body is None:
        return ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="{size}" height="{size}" '
        f'fill="none" stroke="currentColor" stroke-width="{stroke:g}" stroke-linecap="round" '
        f'stroke-linejoin="round" aria-hidden="true" focusable="false">{body}</svg>'
    )


# ─── Órganos (viewBox 0 0 48 48) ─────────────────────────────────────────

ORGAN_GLYPHS: Dict[str, str] = {
    # Corazón anatómico: ventrículos con el ápex a la izquierda del paciente,
    # cayado aórtico, vena cava superior y tronco pulmonar.
    "heart": (
        '<path class="fill" d="M19.6 15.2c-6.6.2-10.4 6.2-9.6 13 .8 7 6.6 12.8 14.6 14.6 2.2.5 4.2-.8 5.2-2.8 3.8-6.8 7.8-12.6 7.2-18.6-.5-4-3.9-6.5-7.9-6-3 .4-5 1-6.5 1-1.1-.2-1.9-1.3-3-1.2z"/>'
        '<path d="M23.4 16.4c-.6-6 2-9.6 6.4-9.6 4 0 6 3 6 6.4"/>'
        '<path d="M27 7.6V4.2M30 6.8V3.6M33 7.6V4.6"/>'
        '<path d="M19.4 15.6V7.4"/>'
        '<path d="M27.6 16.8c.6-3.4 2-5 4-5"/>'
        '<path d="M26.4 19.6c-2 7.4-1.6 14.4 2 21"/>'
    ),
    # Cerebro en vista lateral (frente a la izquierda): hemisferio con la
    # cisura lateral y el surco central, cerebelo y tronco encefálico.
    "brain": (
        '<path class="fill" d="M8.6 25.4C7.4 17.2 13.6 9.6 23 9.2c8.6-.4 15.6 4.6 16.4 12 .5 4.6-1.6 8-5 9.6'
        '-1.6.8-3.4 1-5.2.8-2.6-.2-4.6.8-6.8 1.4-3.4.9-7.4.4-10-1.6-2-1.5-3.4-3.4-3.8-6z"/>'
        '<path class="fill" d="M29.4 31.8c3.4-.4 6.6.8 7 3.4.4 2.8-2.4 4.6-5.6 4.4-2.6-.2-4.4-1.8-4.4-4"/>'
        '<path d="M26.4 32.6c.2 3.4 1 6.4 2.8 9.4"/>'
        '<path d="M12.2 25.6c3.4-2.4 8.6-2.6 12.4-.4 2.2 1.2 4.6 1.4 6.8.6"/>'
        '<path d="M25.4 9.6c-1.4 4.2-.6 8.6 2.6 12.2"/>'
        '<path d="M15.6 16.4c2.2-.6 4.2.4 5.2 2.2M31.4 14c2.4.4 4 2 4.4 4.4M16.4 31c1.6-1.4 3.8-1.6 5.6-.6"/>'
        '<path d="M30.6 34.4h4.6M30 36.8h4"/>'
    ),
    # Pulmones con árbol bronquial; muesca cardiaca en el pulmón izquierdo.
    "lungs": (
        '<path class="fill" d="M18.2 11.2C11 12.2 7 20.4 7 30c0 7 2.6 12 8 12 4 0 6-2.6 6-7V21.6z"/>'
        '<path class="fill" d="M29.8 11.2C37 12.2 41 20.4 41 30c0 7-2.6 12-8 12-2.4 0-3.8-1-4.6-2.6 2.6-1 3.4-3.6 2.4-6.2-.8-2.2-2.6-3-3.8-3.4V21.6z"/>'
        '<path d="M24 4.6v13.6M24 18.2l-5.4 4.6M24 18.2l5.4 4.6M18.6 22.8 15 27.4M18.6 22.8l.6 6.2M29.4 22.8l3.6 4.6M29.4 22.8l-.6 6.2"/>'
    ),
    # Brazo flexionado: el bíceps (con sus fascículos) es el músculo
    # esquelético más reconocible a este tamaño.
    "muscles": (
        '<path class="fill" d="M5 41h25.4c5.8 0 9.6-4.2 9.6-9.8V17c1.4-1.6 1.6-4.8 0-6.4-1.8-1.6-5.2-1.4-6.8.4'
        '-1 1.2-.8 3.2-.4 4.8v10c-2.4-4-6-6-10-6-4.4 0-8 2.2-10.4 5.6-2.4 1.6-4.8 2.6-7.4 3.2z"/>'
        '<path d="M29.2 33.4c-2.6 1.6-5.4 2.4-8.2 2.4"/>'
        '<path d="M11.4 28.4c3.4-2.2 7.6-2.8 11.6-1.6M10 32.6c4-1.4 8.4-1.4 12.4 0"/>'
    ),
    # Sistema nervioso autónomo: tronco encefálico y médula; a un lado la
    # cadena simpática de ganglios, al otro el vago (parasimpático)
    # ramificándose hacia las vísceras.
    "autonomic": (
        '<path class="fill" d="M16.4 10.6c0-4 3.4-6.6 7.6-6.6s7.6 2.6 7.6 6.6c0 3.2-2.4 5.4-5.4 5.8H21.8c-3-.4-5.4-2.6-5.4-5.8z"/>'
        '<path d="M24 16.4V44" stroke-width="3"/>'
        '<path d="M14.6 18.6v22"/>'
        '<circle class="fill" cx="14.6" cy="21.4" r="2.3"/><circle class="fill" cx="14.6" cy="28.4" r="2.3"/>'
        '<circle class="fill" cx="14.6" cy="35.4" r="2.3"/>'
        '<path d="M24 21.4h-7.1M24 28.4h-7.1M24 35.4h-7.1"/>'
        '<path d="M27.6 16c3.6 2.6 5 6.4 5.6 10.6.5 3.6 2.4 6.2 6 7.6M33.4 24.6c2.6.2 4.6-.8 6.2-2.8M35.6 31.6c-.4 2.6.4 5 2.6 7"/>'
    ),
}

ORGAN_LABELS: Dict[str, str] = {
    "heart": "Corazón",
    "brain": "Cerebro",
    "lungs": "Pulmones",
    "muscles": "Músculos",
    "autonomic": "Sistema nervioso autónomo",
}


def organ_glyph_svg(organ_id: str, color: str, size: int = 44, label: str = "") -> str:
    """Órgano dibujado con trazo `color` y relleno tenue del mismo color.

    Con `label` el SVG es una imagen con nombre (`role="img"`); sin él es
    decorativo (`aria-hidden`) porque la tarjeta ya escribe el nombre.
    """
    body = ORGAN_GLYPHS.get(organ_id)
    if body is None:
        return ""
    a11y = (
        f'role="img" aria-label="{esc(label)}"' if label else 'aria-hidden="true" focusable="false"'
    )
    # Relleno como atributo, NO como <style>: un <style> dentro de un SVG
    # en línea es CSS global del documento y pintaría todos los órganos de
    # la página con el color del último.
    body = body.replace('class="fill"', f'fill="{color}" fill-opacity="0.14"')
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="{size}" height="{size}" '
        f'fill="none" stroke="{color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" {a11y}>'
        f'{body}</svg>'
    )
