"""Pestaña «Placa en vivo (tutorial)» del ECG Lab.

Enseña a usar la fuente «Hardware ESP32 en vivo» del Monitoreo: material,
seguridad, conexiones, firmware, electrodos, qué significa cada estado, qué
hacer si algo falla y qué se puede concluir con esa señal. Cierra con una
práctica con la placa simulada que recorre la misma tubería que la real
(búfer, filtro, revisión de calidad, análisis), para ensayar el flujo sin
hardware, incluidos el electrodo suelto y el cable desconectado.

Por qué existe (regla 9): sin estas instrucciones la fuente de hardware no se
puede usar en clase, y la práctica enseña calidad de señal con el mismo código
que procesa la placa real. Todo lo de la práctica se etiqueta SIMULACIÓN, y
cada número dice de dónde sale y qué tan validado está (Art. I).
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Sequence

import numpy as np
import pandas as pd
import streamlit as st
from streamlit.errors import StreamlitAPIException

import hardware.ecg_plugplay as ecg_plugplay
from app.supermodules.ecg_live import service as live_service
from app.supermodules.ecg_live.monitor_source import TUTORIAL_TAB
from app.utils.design_system import PALETTE, render_section_header
from hardware.ecg_plugplay.config import AD8232_GAIN_SOURCE
from hardware.ecg_plugplay.preprocessing import FILTER_LIMITS_SOURCE

FIRMWARE_PATH = Path(ecg_plugplay.__file__).resolve().parent / 'firmware' / 'main.py'
SPARKFUN_GUIDE = ('SparkFun, «AD8232 Heart Rate Monitor Hookup Guide»: '
                  'https://learn.sparkfun.com/tutorials/ad8232-heart-rate-monitor-hookup-guide')

INTRO = (
    'Con una ESP32 y una tarjeta AD8232 puedes ver en el Monitoreo un ECG de una derivación en vivo, '
    'el tuyo o el de un compañero. La app encuentra la placa sola, filtra la señal, descarta los tramos '
    'que no sirven y dice por qué. Sigue los pasos en orden; al final puedes practicar todo el flujo '
    'con una placa simulada, sin hardware.'
)

ORIGIN_TABLE = [
    ('Frecuencia cardiaca', 'Detector TKEO de BIOCORE, el mismo del resto del ECG Lab',
     'Validado contra registros MIT-BIH; con la señal de esta placa no se ha validado'),
    ('Ondas Q, R y S (práctica)', 'Delineador de QRS de BIOCORE (`delineate_qrs`, Sub-Fase 2.5)',
     'Especificación validada; su uso en vivo está en revisión clínica'),
    ('Ondas P y T (práctica)', 'Heurística del módulo de la placa', 'No validada'),
    ('Ventanas descartadas', 'Umbrales de calidad (`QualityHeuristics`)', 'Heurísticos, sin criterio clínico citado'),
    ('Amplitud en mV', 'Cuentas del ADC con una ganancia supuesta de 1100', 'Aproximada, sin calibrar'),
]

MATERIAL = [
    'Una ESP32 DevKit V1 con MicroPython instalado.',
    'Una tarjeta AD8232 con su cable de tres electrodos, y electrodos desechables nuevos.',
    'Un cable USB que transmita datos (algunos solo cargan).',
    'La computadora con BIOCORE y con Thonny, funcionando con batería.',
]

SAFETY = [
    '**Con una persona conectada a los electrodos, la computadora va con batería.** Desconecta el cargador '
    'de la pared antes de pegar los electrodos y no lo conectes hasta despegarlos.',
    'Es material educativo, no un dispositivo médico: no sirve para diagnosticar ni para descartar nada. La '
    'guía de la tarjeta lo dice así: «This device is not intended to diagnose or treat any conditions».',
    'Usa electrodos nuevos en cada medición, como recomienda la misma guía.',
]

WIRING = [
    ('3.3V', '3V3', 'Alimentación. A 3.3 V, nunca a 5 V.'),
    ('GND', 'GND', 'Tierra común.'),
    ('OUTPUT', 'GPIO34', 'La señal de ECG (entrada analógica).'),
    ('LO+', 'GPIO35', 'Avisa si se despega un electrodo.'),
    ('LO−', 'GPIO32', 'Avisa si se despega un electrodo.'),
    ('SDN', 'Sin conectar', 'En bajo apaga el chip.'),
]

FIRMWARE_STEPS = [
    'Descarga el firmware con el botón de abajo (en el repo está en `hardware/ecg_plugplay/firmware/main.py`).',
    'Conecta la ESP32 por USB, abre el archivo en Thonny y guárdalo **en la placa** con el nombre `main.py`.',
    '**Cierra Thonny.** Mientras está abierto ocupa el puerto y detiene el programa de la placa.',
    'Presiona el botón EN de la ESP32. Desde ese momento la placa se presenta sola cada 2 s.',
]

ELECTRODES = [
    ('RA', 'Antebrazo derecho, o pecho cerca del brazo derecho', 'Negro'),
    ('LA', 'Antebrazo izquierdo, o pecho cerca del brazo izquierdo', 'Azul'),
    ('RL', 'Pierna derecha, o arriba de la parte baja derecha del abdomen', 'Rojo'),
]

ELECTRODE_TIPS = [
    'Mientras más cerca del corazón estén los electrodos, mejor la señal, y RA y LA cada uno de su lado.',
    'Piel limpia y seca. Quien se mide, sentado o acostado, quieto, con los brazos relajados y sin hablar.',
    'Lejos del cargador y de otros aparatos conectados a la pared.',
]

APP_STEPS = [
    'En la pestaña **Monitoreo**, en la barra lateral, elige la fuente **«Hardware ESP32 en vivo»**.',
    'La app busca la placa sola en los puertos USB. No tienes que elegir el puerto.',
    'Cuando diga «Conectado» espera 4 s de señal limpia. Verás la insignia 🟢 PROCEDENCIA: SENSOR_REAL.',
    'La página no se redibuja sola: pulsa **«🔄 Leer los últimos segundos»** para traer la señal más reciente '
    '(hasta 10 s).',
    'Para usar Thonny otra vez, pulsa **«⏹ Soltar el puerto»**; para volver, **«▶ Buscar la placa»**.',
]

STATES = [
    ('🟡 Buscando', 'Revisa los puertos USB cada segundo. Conecta la placa.'),
    ('🟡 Verificando', 'Encontró un puerto y espera el saludo `ECG:HELLO` de la placa.'),
    ('🟢 Conectado', 'Llegan datos. Con 4 s de señal limpia, el Monitoreo la analiza.'),
    ('🔴 Desconectado', 'Se jaló el cable o pasaron 2 s sin datos. Cerró el puerto y vuelve a buscar sola.'),
    ('⚪ Detenido', 'Pulsaste «Soltar el puerto». Thonny ya puede usarlo.'),
]

DISCARD_REASONS = [
    ('Electrodo suelto', 'El AD8232 marcó que se despegó un electrodo.'),
    ('Faltan muestras', 'Se perdieron más de 2 muestras seguidas en la transmisión; no se inventan.'),
    ('El ADC saturó', 'La señal tocó el límite del ADC: movimiento o un electrodo flojo.'),
    ('El filtro se está estabilizando', 'Es el primer medio segundo después de una interrupción.'),
    ('Señal plana', 'Menos de 0.05 mV de pico a pico; suele ser un electrodo sin contacto.'),
]

TROUBLESHOOTING = [
    ('«COM3 está ocupado por otro programa…»', 'Cierra Thonny, el monitor serie de Arduino o cualquier terminal. '
                                               'La app reintenta sola cada 5 s.'),
    ('«…hay MicroPython esperando órdenes (>>>)…»', 'El firmware no está corriendo: guarda `main.py` en la placa, '
                                                    'cierra Thonny y presiona EN.'),
    ('«…el programa de la placa falló al arrancar (Traceback)»', 'Abre la placa en Thonny para leer el error.'),
    ('«…no respondió como placa de ECG…»', 'Es otra placa u otro firmware. Vuelve al paso 4.'),
    ('«…no responde: casi siempre es un puerto Bluetooth…»', 'La app se lo salta sola; no hay que hacer nada.'),
    ('Nunca aparece ningún puerto', 'El cable USB solo carga, o falta el controlador del chip USB de la placa '
                                    '(CP210x o CH340).'),
    ('«Sin señal limpia: electrodo suelto…»', 'Revisa que los tres electrodos estén bien pegados.'),
]


def _limits() -> List[str]:
    return [
        '**Una sola derivación.** Sirve para ritmo y frecuencia cardiaca. No sirve para el eje ni para '
        'compararla con un ECG de 12 derivaciones.',
        '**Filtro de monitoreo, de 0.5 a 40 Hz.** Un corte bajo de 0.5 Hz deforma el nivel del segmento ST, y '
        'para diagnóstico se pide un corte alto de al menos 150 Hz (Kligfield et al., *Circulation* 2007). No '
        'evalúes elevación ni depresión del ST con esta señal.',
        '**Amplitud aproximada.** Los mV suponen una ganancia de 1100, la de la configuración de monitor '
        'cardiaco de la hoja de datos del AD8232; tu tarjeta puede tener otra, y nadie la calibró.',
        '**El detector TKEO se validó con MIT-BIH, no con esta placa.** Si la frecuencia no te cuadra con el '
        'pulso que tomas a mano, cree al pulso.',
    ]


def _table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    lines = ['| ' + ' | '.join(headers) + ' |', '|' + '---|' * len(headers)]
    lines += ['| ' + ' | '.join(row) + ' |' for row in rows]
    return '\n'.join(lines)


def _bullets(items: Sequence[str]) -> str:
    return '\n'.join(f'- {item}' for item in items)


def _numbered(items: Sequence[str]) -> str:
    return '\n'.join(f'{i}. {item}' for i, item in enumerate(items, 1))


def wiring_svg() -> str:
    """Diagrama de conexiones en SVG, en una sola línea (con sangría, Streamlit lo mostraría como código)."""
    pins = [('3.3V', '3V3', '#ff4d4d'), ('GND', 'GND', '#94a3b8'), ('OUTPUT', 'GPIO34', '#39d98a'),
            ('LO+', 'GPIO35', '#ffc542'), ('LO−', 'GPIO32', '#fb923c')]
    parts = [
        '<svg viewBox="0 0 560 250" width="100%" style="max-width:560px" xmlns="http://www.w3.org/2000/svg" '
        'font-family="sans-serif" font-size="13" role="img" aria-label="Conexiones del AD8232 a la ESP32">',
        '<rect x="10" y="10" width="150" height="230" rx="10" fill="#7f1d1d" stroke="#e0e7ff"/>',
        f'<text x="85" y="34" text-anchor="middle" fill="{PALETTE.TEXT}" font-weight="bold">AD8232</text>',
        '<rect x="400" y="10" width="150" height="230" rx="10" fill="#1e293b" stroke="#e0e7ff"/>',
        f'<text x="475" y="34" text-anchor="middle" fill="{PALETTE.TEXT}" font-weight="bold">ESP32 DevKit V1</text>',
    ]
    for i, (izquierda, derecha, color) in enumerate(pins):
        y = 70 + 36 * i
        parts += [
            f'<line x1="160" y1="{y}" x2="400" y2="{y}" stroke="{color}" stroke-width="3"/>',
            f'<circle cx="160" cy="{y}" r="5" fill="{color}"/><circle cx="400" cy="{y}" r="5" fill="{color}"/>',
            f'<text x="148" y="{y + 4}" text-anchor="end" fill="{PALETTE.TEXT}">{izquierda}</text>',
            f'<text x="412" y="{y + 4}" fill="{PALETTE.TEXT}">{derecha}</text>',
        ]
    parts.append('</svg>')
    return ''.join(parts)


# ---------------------------------------------------------------- práctica
_ICONS = {'conectado': '🟢', 'buscando': '🟡', 'verificando': '🟡', 'desconectado': '🔴', 'detenido': '⚪'}
_WAVE_COLORS = {'P': '#8ecae6', 'Q': '#ffc542', 'R': '#ff4d4d', 'S': '#fb923c', 'T': '#39d98a'}

PRACTICE_INTRO = (
    'La placa simulada pasa por el mismo código que la real: búfer, filtro, revisión de calidad y análisis. '
    'Todo lo que ves aquí es **SIMULACIÓN**: la frecuencia la eliges tú con el control.'
)

PRACTICE_OBSERVE = [
    '**Despega un electrodo**: la ventana se descarta con su motivo y no hay frecuencia. Al volver a pegarlo, '
    'el primer medio segundo también se descarta («el filtro se está estabilizando»).',
    '**Desconecta el cable**: el estado pasa a «Desconectado» al instante, el búfer se vacía y la app vuelve '
    'a buscar. Al reconectarlo, se conecta sola.',
    '**Cambia la frecuencia**: el detector la sigue en las ventanas siguientes. Cada ventana dura 4 s y sale '
    'una nueva cada 2 s.',
]


def window_figure(result):
    """La última ventana válida con las ondas P, Q, R, S y T que se detectaron."""
    import plotly.graph_objects as go

    window = result.window
    t = np.arange(window.ecg_mv.size) / window.fs
    fig = go.Figure(go.Scatter(x=t, y=window.ecg_mv, mode='lines', name='ECG', line=dict(width=1.5)))
    for kind, color in _WAVE_COLORS.items():
        points = [beat[kind] for beat in (result.waves or {}).values() if kind in beat]
        if points:
            fig.add_trace(go.Scatter(
                x=[p['index'] / window.fs for p in points], y=[p['amplitude'] for p in points],
                mode='markers+text', text=[kind] * len(points), textposition='top center', name=kind,
                marker=dict(size=8, color=color),
            ))
    fig.update_layout(template='plotly_dark', height=300, showlegend=False, margin=dict(l=40, r=10, t=30, b=40),
                      title='Última ventana válida (4 s)', xaxis_title='s', yaxis_title='mV aprox.')
    return fig


def _refresh_now() -> None:
    """Vuelve a dibujar el panel en seguida, para que el botón muestre ya la acción contraria.

    Solo el panel si el clic llegó en una recarga del fragmento; la página entera si
    llegó en una recarga completa (ahí Streamlit no acepta scope='fragment') o si esta
    versión de Streamlit no tiene fragmentos. `st.rerun()` sale con una excepción de
    control (BaseException), así que `except Exception` no la atrapa.
    """
    try:
        st.rerun(scope='fragment')
    except (TypeError, StreamlitAPIException):
        st.rerun()


def _practice_body(servicio, placa) -> None:
    s = servicio.snapshot()
    st.markdown(f"{_ICONS.get(s['state'], '⚪')} **{s['state'].capitalize()}** — {s['message']}")
    st.caption('🟡 PROCEDENCIA: SIMULACIÓN — placa simulada; no es un sensor.')

    c1, c2, c3 = st.columns(3)
    hr = c1.slider('Frecuencia de la placa simulada (lpm)', 40, 180, 72, key='ecglab_tutorial_hr')
    if abs(placa.hr_bpm - hr) >= 1:
        placa.set_hr(hr)
    if placa.leadoff:
        if c2.button('🩹 Volver a pegar el electrodo', key='ecglab_tutorial_lo_off'):
            placa.set_leadoff(0)
            _refresh_now()
    elif c2.button('✋ Despegar un electrodo', key='ecglab_tutorial_lo_on'):
        placa.set_leadoff(1)
        _refresh_now()
    if placa.plugged:
        if c3.button('🔌 Desconectar el cable', key='ecglab_tutorial_unplug'):
            placa.unplug()
            _refresh_now()
    elif c3.button('🔌 Reconectar el cable', key='ecglab_tutorial_plug'):
        placa.plug()
        _refresh_now()

    mv, t = s['signal_mv'], s['signal_t']
    if mv.size:
        st.line_chart(pd.DataFrame({'ECG (mV aprox.)': mv}, index=np.round(t, 3)), height=220)
    r = s['last_result']
    filled, total = s['buffer_fill']
    if r is None:
        if s['state'] == 'conectado':
            st.progress(min(1.0, filled / total), text=f'Juntando la primera ventana: {filled} de {total} muestras.')
        return
    if not r.valid:
        st.warning('Ventana descartada: ' + '; '.join(r.reasons))
        return
    m1, m2, m3 = st.columns(3)
    m1.metric('Frecuencia que elegiste', f'{placa.hr_bpm:.0f} lpm')
    m2.metric('Frecuencia medida (TKEO)', f'{r.bpm:.0f} lpm' if r.bpm is not None else 'No disponible')
    counters = s['counters']
    m3.metric('Ventanas válidas / descartadas', f"{counters['validas']} / {counters['descartadas']}")
    st.plotly_chart(window_figure(r))
    origen = r.labels.get('waves', 'sin ondas detectadas')
    st.caption(f'Ondas: {origen}. Una onda que no se detectó no se dibuja.')
    for note in r.notes:
        st.caption(note)


_fragment = getattr(st, 'fragment', None)                       # Streamlit 1.37 o más nuevo
_practice_panel = _fragment(run_every=1.0)(_practice_body) if _fragment is not None else _practice_body


def _render_practice() -> None:
    practice = live_service.get_practice()
    servicio, placa = practice.service, practice.device
    st.markdown(PRACTICE_INTRO)
    if not servicio.is_running:
        if st.button('▶ Empezar práctica', key='ecglab_tutorial_start'):
            placa.plug()
            placa.set_leadoff(0)
            servicio.start()
            st.rerun()
        return
    if st.button('⏹ Terminar práctica', key='ecglab_tutorial_stop'):
        servicio.stop()
        st.rerun()
    _practice_panel(servicio, placa)
    if _fragment is None:
        st.button('🔄 Actualizar', key='ecglab_tutorial_refresh')
    st.markdown('**Qué observar**\n\n' + _bullets(PRACTICE_OBSERVE))


# ---------------------------------------------------------------- pestaña
def render_live_tutorial() -> None:
    render_section_header(TUTORIAL_TAB)
    st.markdown(INTRO)
    st.markdown('**De dónde sale cada número**\n\n' + _table(('Qué ves', 'De dónde sale', 'Qué tan validado'),
                                                              ORIGIN_TABLE))

    with st.expander('1. Qué necesitas', expanded=True):
        st.markdown(_bullets(MATERIAL))
        st.caption('Si tu ESP32 no tiene MicroPython, instálalo desde Thonny, en la configuración del intérprete, '
                   'o con las instrucciones de micropython.org.')

    with st.expander('2. Seguridad (léelo antes de pegar los electrodos)', expanded=True):
        st.warning(SAFETY[0])
        st.markdown(_bullets(SAFETY[1:]))
        st.caption(f'Fuente: {SPARKFUN_GUIDE}')

    with st.expander('3. Conecta el AD8232 a la ESP32'):
        st.markdown(wiring_svg(), unsafe_allow_html=True)
        st.markdown(_table(('AD8232', 'ESP32', 'Para qué'), WIRING))
        st.caption('LO+ y LO− se ponen en alto cuando se despega un electrodo (hoja de datos del AD8232, Rev. D).')

    with st.expander('4. Carga el firmware en la ESP32'):
        st.markdown(_numbered(FIRMWARE_STEPS))
        if FIRMWARE_PATH.exists():
            st.download_button('⬇ Descargar el firmware (main.py)', data=FIRMWARE_PATH.read_bytes(),
                               file_name='main.py', mime='text/x-python', key='ecglab_tutorial_firmware')
        else:
            st.error(f'No se encontró el firmware en {FIRMWARE_PATH}.')

    with st.expander('5. Coloca los electrodos'):
        st.markdown(_table(('Electrodo', 'Dónde', 'Color en el cable de SparkFun'), ELECTRODES))
        st.markdown(_bullets(ELECTRODE_TIPS))
        st.caption('Otros cables usan otros colores: guíate por las letras RA, LA y RL. Posiciones, colores y la '
                   f'regla de «cerca del corazón»: {SPARKFUN_GUIDE}')

    with st.expander('6. Conéctala en la app'):
        st.markdown(_numbered(APP_STEPS))
        st.markdown('**Qué significa cada estado**\n\n' + _table(('Estado', 'Qué pasa'), STATES))
        st.markdown('**Por qué se descarta una ventana** (la barra lateral dice el motivo)\n\n'
                    + _table(('Motivo', 'Qué significa'), DISCARD_REASONS))

    with st.expander('7. Si algo falla'):
        st.markdown(_table(('Lo que dice la app', 'Qué hacer'), TROUBLESHOOTING))

    with st.expander('8. Qué puedes y qué no puedes concluir'):
        st.markdown(_bullets(_limits()))
        st.caption(f'Fuentes: {FILTER_LIMITS_SOURCE} · {AD8232_GAIN_SOURCE}')

    render_section_header('9. Practica sin placa (SIMULACIÓN)')
    _render_practice()
