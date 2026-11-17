"""Tutorial genérico de un sensor de la placa ESP32 de BIOCORE (2026-11-14).

Lo arma con el catálogo (`hardware/biosensors/sensors.py`): material, seguridad, conexiones con su diagrama,
firmware para descargar, colocación, pasos en la app, estados, qué hacer si algo falla, límites y la práctica que
le pase cada laboratorio. Mismo orden que el tutorial de la placa de ECG (`app/supermodules/ecg_live/tutorial.py`).
"""

from __future__ import annotations

from typing import Callable, Sequence

import streamlit as st

from app.utils.design_system import PALETTE, render_section_header
from app.utils.legal import SAFETY_BY_KIND, render_safety_precautions
from hardware.biosensors import BioSensor

STATES = [
    ('🟡 Conectando', 'Revisa los puertos USB, manda «BIO?» y espera el saludo `BIO:HELLO` de la placa.'),
    ('🟢 Transmitiendo', 'Llegan muestras. Solo en este estado hay análisis y procedencia.'),
    ('🟠 Sin datos', 'Pasaron 3 s sin muestras.'),
    ('🔴 Sin conexión', 'No encontró la placa, se desconectó el cable o pasaron 10 s sin muestras. Dice el motivo y '
                       'reintenta solo cada 5 s.'),
    ('⚪ Detenido', 'Pulsaste «Soltar el puerto»: Thonny ya puede usarlo.'),
]

TROUBLESHOOTING = [
    ('«No hay ninguna placa conectada por USB…»', 'El cable USB solo carga, o falta el controlador del chip USB de la '
                                                  'placa (CP210x o CH340).'),
    ('«…está ocupado por otro programa…»', 'Cierra Thonny, el monitor serie de Arduino o cualquier terminal. La app '
                                           'reintenta sola.'),
    ('«…hay MicroPython esperando órdenes («>>>»)…»', 'El firmware no está corriendo: guarda el archivo como '
                                                      '`main.py` en la placa, cierra Thonny y presiona EN.'),
    ('«…se detuvo con un error…»', 'Abre la placa en Thonny para leer el error.'),
    ('«…es la placa de ECG de BIOCORE…»', 'Esa placa tiene el firmware del ECG: úsala en el Laboratorio de ECG, o cárgale el '
                                          'firmware de este sensor.'),
    ('«…es una placa de …, no de …»', 'Tiene el firmware de otro sensor: cárgale el de este.'),
    ('«…no respondió como una placa de … de BIOCORE…»', 'Es otra placa u otro programa: vuelve a cargar el firmware.'),
    ('«Se han perdido … muestras…»', 'La placa no alcanzó a mandar todo, o el cable falla. Cierra otros programas '
                                     'pesados y prueba otro cable o puerto.'),
]


def _table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    lines = ['| ' + ' | '.join(headers) + ' |', '|' + '---|' * len(headers)]
    lines += ['| ' + ' | '.join(row) + ' |' for row in rows]
    return '\n'.join(lines)


def _bullets(items: Sequence[str]) -> str:
    return '\n'.join(f'- {item}' for item in items)


def _numbered(items: Sequence[str]) -> str:
    return '\n'.join(f'{i}. {item}' for i, item in enumerate(items, 1))


def wiring_svg(sensor: BioSensor, sensor_label: str) -> str:
    """Diagrama de conexiones, en una sola línea (con sangría, Streamlit lo mostraría como código)."""
    colors = PALETTE.DIAGRAM_SERIES
    rows = [(s, e) for s, e, _ in sensor.wiring if not e.lower().startswith('sin conectar')]
    height = 70 + 36 * len(rows)
    parts = [
        f'<svg viewBox="0 0 560 {height}" width="100%" style="max-width:560px" xmlns="http://www.w3.org/2000/svg" '
        f'font-family="sans-serif" font-size="13" role="img" aria-label="Conexiones de {sensor_label} a la ESP32">',
        f'<rect x="10" y="10" width="150" height="{height - 20}" rx="10" fill="{PALETTE.SENSOR_BOARD}" stroke="{PALETTE.TEXT}"/>',
        f'<text x="85" y="34" text-anchor="middle" fill="{PALETTE.TEXT}" font-weight="bold">{sensor_label}</text>',
        f'<rect x="400" y="10" width="150" height="{height - 20}" rx="10" fill="{PALETTE.SECONDARY_BACKGROUND}" stroke="{PALETTE.TEXT}"/>',
        f'<text x="475" y="34" text-anchor="middle" fill="{PALETTE.TEXT}" font-weight="bold">ESP32 DevKit V1</text>',
    ]
    for i, (left, right) in enumerate(rows):
        y, color = 62 + 36 * i, colors[i % len(colors)]
        parts += [
            f'<line x1="160" y1="{y}" x2="400" y2="{y}" stroke="{color}" stroke-width="3"/>',
            f'<circle cx="160" cy="{y}" r="5" fill="{color}"/><circle cx="400" cy="{y}" r="5" fill="{color}"/>',
            f'<text x="148" y="{y + 4}" text-anchor="end" fill="{PALETTE.TEXT}">{left}</text>',
            f'<text x="412" y="{y + 4}" fill="{PALETTE.TEXT}">{right}</text>',
        ]
    parts.append('</svg>')
    return ''.join(parts)


def render_sensor_tutorial(sensor: BioSensor, title: str, prefix: str, intro: str, origin_table: Sequence,
                           sensor_label: str, practice: Callable[[], None]) -> None:
    render_section_header(title)
    st.markdown(intro)
    st.markdown('**De dónde sale cada número**\n\n' + _table(('Qué ves', 'De dónde sale', 'Qué tan validado'),
                                                              origin_table))

    with st.expander('1. Qué necesitas', expanded=True):
        st.markdown(_bullets(sensor.material))
        st.caption('Si tu ESP32 no tiene MicroPython, instálalo desde Thonny, en la configuración del intérprete, o con '
                   'las instrucciones de micropython.org.')

    with st.expander('2. Seguridad (léelo antes de conectar a nadie)', expanded=True):
        if sensor.safety:
            st.warning(sensor.safety[0])
            st.markdown(_bullets(sensor.safety[1:]))
        if sensor.key in SAFETY_BY_KIND:     # 2026-11-17: precauciones del manual de usuario (`app/utils/legal.py`)
            render_safety_precautions(sensor.key)

    with st.expander(f'3. Conecta {sensor_label} a la ESP32'):
        st.markdown(wiring_svg(sensor, sensor_label), unsafe_allow_html=True)
        st.markdown(_table((sensor_label, 'ESP32', 'Para qué'), sensor.wiring))

    with st.expander('4. Carga el firmware en la ESP32'):
        st.markdown(_numbered(sensor.firmware_steps))
        path = sensor.firmware_path
        if path.exists():
            st.download_button(f'⬇ Descargar el firmware ({path.name}, guárdalo como main.py)',
                               data=path.read_bytes(), file_name='main.py', mime='text/x-python',
                               key=f'{prefix}_firmware')
        else:
            st.error(f'No se encontró el firmware en {path}.')

    with st.expander('5. Coloca el sensor'):
        st.markdown(_bullets(sensor.placement))

    with st.expander('6. Conéctala en la app'):
        st.markdown(_numbered(sensor.app_steps))
        st.markdown('**Qué significa cada estado**\n\n' + _table(('Estado', 'Qué pasa'), STATES))

    with st.expander('7. Si algo falla'):
        st.markdown(_table(('Lo que dice la app', 'Qué hacer'), list(TROUBLESHOOTING) + list(sensor.troubleshooting)))

    with st.expander('8. Qué puedes y qué no puedes concluir'):
        st.markdown(_bullets(sensor.limits))
        st.caption('Fuentes: ' + ' · '.join(sensor.sources))

    render_section_header('9. Practica sin placa (SIMULACIÓN)')
    practice()
