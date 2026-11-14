"""Pestaña «EEG en vivo (tutorial)» del EEG Neuro Lab (2026-11-14).

Enseña a usar la fuente «Hardware EEG en vivo» de la pestaña Clínica: qué equipos sirven, dónde va cada
electrodo, cómo se conecta cada uno, qué significa cada estado y cada aviso de calidad, y qué se puede concluir.
Cierra con una práctica con el simulador, que pasa por el mismo servicio, el mismo filtro de red y el mismo
analizador que un equipo real.

Por qué existe (regla 9): sin estas instrucciones la fuente en vivo no se puede usar en clase, y la práctica
enseña a reconocer la reactividad del ritmo alfa y los artefactos con el mismo código que procesa la señal real.
Todo lo de la práctica se rotula SIMULACIÓN y cada afirmación clínica lleva su fuente (Art. I).
"""

from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd
import streamlit as st

from app.supermodules.eeg_neuro_lab import live_service
from app.supermodules.eeg_neuro_lab.live_source import (MAINS_OPTIONS, SOURCE_LABEL, STATE_ICONS, TUTORIAL_TAB,
                                                        render_simulator_controls)
from app.utils.design_system import PALETTE, render_section_header
from clinical.eeg_references import KANE_2017, SEECK_2017, TATUM_2011
from hardware.eeg_live import DEVICES, assess_channels, prepare
from hardware.eeg_live.montage import POSITIONS, TEN_TWENTY
from hardware.eeg_live.quality import ISSUE_TEXT, QualityHeuristics

try:
    from src.signals.eeg import EegAnalyzer
except ImportError:                       # el resto del tutorial no depende del analizador
    EegAnalyzer = None

INTRO = (
    'Con un equipo de EEG puedes ver tu propio EEG en la pestaña Clínica y analizarlo con lo mismo que la señal '
    'sintética: potencia por banda, cocientes y exponente aperiódico. Sirven OpenBCI (Cyton, Cyton + Daisy y '
    'Ganglion), Muse 2 y Muse S, el Unicorn de g.tec y cualquier programa que publique el EEG por LSL. Sigue los '
    'pasos en orden; al final puedes practicar todo el flujo con un simulador, sin equipo.'
)

ORIGIN_TABLE = [
    ('Potencia por banda y banda dominante', 'EegAnalyzer: filtro de 0.5 a 40 Hz y Welch en ventanas de 1 s',
     'Cálculo estándar; con equipos reales no se ha validado en BIOCORE'),
    ('Ventanas descartadas', 'Rechazo por gradiente de EegAnalyzer (más de 5500 µV/s)',
     'Umbral de ingeniería calibrado con la señal del generador; sin probar con hardware real'),
    ('DAR, TBR, BAR y χ', 'Los mismos cálculos de la pestaña Clínica', 'Cada tarjeta dice su fuente'),
    ('Avisos de calidad por canal', 'Umbrales de ingeniería (`QualityHeuristics`)', 'Heurísticos, sin criterio '
                                                                                    'clínico citado'),
    ('Microvoltios', 'BrainFlow devuelve µV en los canales de EEG siempre que puede; un flujo LSL, lo que declare',
     'Del fabricante o del programa que publica; BIOCORE no calibra'),
]

SAFETY = [
    'Es para aprender: no sirve para diagnosticar ni para descartar nada, por ejemplo una epilepsia.',
    'Usa la batería del equipo. Para la Cyton, OpenBCI recomienda usar siempre el portapilas que vino con el kit.',
    'Si un canal se ve muy distinto a los demás, revisa ese electrodo antes de interpretar nada (sección 6).',
]

APP_STEPS = [
    f'En la pestaña **Clínica**, en la barra lateral, elige el origen de datos **«{SOURCE_LABEL}»**.',
    'Elige tu dispositivo y llena lo que pida (el puerto del dongle, por ejemplo). Pulsa **«▶ Conectar»**.',
    'Arriba de la página aparece «Señal en vivo», que se actualiza sola cada segundo. Revisa que todos los canales '
    'se vean parecidos antes de analizar.',
    'El análisis usa los últimos segundos del control «Duración» (desde 4 s). Para traer la señal más reciente '
    'pulsa **«🔄 Leer los últimos segundos»**.',
    'Para soltar el equipo (y usarlo con otro programa) pulsa **«⏹ Desconectar»**.',
]

STATES = [
    ('🟡 Conectando', 'Abre la sesión con el equipo y espera las primeras muestras.'),
    ('🟢 Transmitiendo', 'Llegan muestras. Solo en este estado hay análisis y procedencia.'),
    ('🟠 Sin datos', 'Pasaron 3 s sin muestras: equipo apagado, lejos o sin batería.'),
    ('🔴 Sin conexión', 'No se pudo abrir, o pasaron 10 s sin muestras y se cerró la sesión. Dice el motivo y '
                       'reintenta solo cada 5 s.'),
    ('⚪ Detenido', 'Pulsaste «Desconectar». El equipo queda libre para otro programa.'),
]

PROVENANCE_ROWS = [
    ('🟢 SENSOR_REAL', 'Un equipo real (OpenBCI, Muse, Unicorn) mandando datos ahora mismo', 'SENSOR_REAL'),
    ('🟡 SIMULACIÓN', 'El simulador de práctica o el tablero sintético de BrainFlow', 'Simulación'),
    ('🟠 No verificable', 'Un flujo LSL: puede venir de un equipo o de un programa que inventa datos',
     'Simulación, con el nombre del flujo'),
]


def quality_rows():
    h = QualityHeuristics()
    return [
        ('Señal plana', f'Menos de {h.flat_rms_uv} µV de RMS entre 0.5 y 40 Hz', ISSUE_TEXT['plano']),
        ('Mucho más amplio que los demás', f'Más de {h.outlier_ratio:g} veces la mediana de los otros canales',
         ISSUE_TEXT['distinto']),
        ('Mucho ruido de la red', f'Más de {h.mains_rms_uv:g} µV de RMS alrededor de 50 o 60 Hz, antes del filtro',
         ISSUE_TEXT['red']),
    ]


def limits():
    return [
        '**Pocos electrodos, en lugares fijos.** La Muse tiene cuatro (TP9, AF7, AF8 y TP10), ninguno occipital, y el '
        'ritmo alfa tiene su máximo sobre las regiones occipitales (glosario IFCN): ahí se verá más débil que en un '
        'gorro con O1 y O2.',
        '**No es un EEG clínico.** No sirve para diagnosticar ni para descartar una epilepsia ni otra enfermedad.',
        '**Cada canal se mide contra una referencia**, «cualquier electrodo contra el que se miden las variaciones de '
        'potencial de otro» (glosario IFCN). Los valores cambian con la referencia y la colocación de cada equipo; no '
        'compares números entre equipos distintos.',
        '**La banda con más potencia no es un estado.** En EEG real la potencia cae con la frecuencia, así que delta '
        'puede dominar aunque estés despierto. Por eso, con señal en vivo, la pestaña Clínica no traduce la banda '
        'dominante a «sueño» o «alerta».',
        '**El rechazo de artefactos se calibró con la señal del generador**, no con hardware real; un parpadeo o un '
        'movimiento real puede pasar sin descartarse.',
        '**Por Bluetooth se pueden perder muestras.** Si llegan menos de las que deberían, la barra lateral avisa; el '
        'análisis trata la señal como continua.',
    ]


def _table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    lines = ['| ' + ' | '.join(headers) + ' |', '|' + '---|' * len(headers)]
    lines += ['| ' + ' | '.join(row) + ' |' for row in rows]
    return '\n'.join(lines)


def _bullets(items: Sequence[str]) -> str:
    return '\n'.join(f'- {item}' for item in items)


def _numbered(items: Sequence[str]) -> str:
    return '\n'.join(f'{i}. {item}' for i, item in enumerate(items, 1))


def device_rows():
    rows = []
    for d in DEVICES:
        channels = f'{len(d.channels)}' if d.channels else 'los del flujo'
        fs = f'{d.fs:g} Hz' if d.fs else 'la del flujo'
        rows.append((d.name, channels, fs, d.connection, d.platforms or 'Cualquiera con BIOCORE'))
    return rows


def montage_svg(channels: Sequence[str], label: str) -> str:
    """Cabeza vista desde arriba, nariz arriba. En una sola línea: con sangría, Streamlit lo mostraría como código."""
    cx, cy, radius = 180, 185, 140
    marked = [c for c in channels if c in POSITIONS]
    parts = [
        f'<svg viewBox="0 0 360 370" width="100%" style="max-width:380px" xmlns="http://www.w3.org/2000/svg" '
        f'font-family="sans-serif" role="img" aria-label="Electrodos de {label} en el sistema 10-20">',
        f'<polygon points="{cx - 14},{cy - radius + 3} {cx},{cy - radius - 20} {cx + 14},{cy - radius + 3}" '
        f'fill="none" stroke="{PALETTE.TEXT}" stroke-width="2"/>',
        f'<ellipse cx="{cx - radius - 7}" cy="{cy}" rx="8" ry="24" fill="none" stroke="{PALETTE.TEXT}" stroke-width="2"/>',
        f'<ellipse cx="{cx + radius + 7}" cy="{cy}" rx="8" ry="24" fill="none" stroke="{PALETTE.TEXT}" stroke-width="2"/>',
        f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="none" stroke="{PALETTE.TEXT}" stroke-width="2"/>',
        f'<text x="20" y="360" fill="{PALETTE.TEXT}" font-size="11">izquierda</text>',
        f'<text x="340" y="360" fill="{PALETTE.TEXT}" font-size="11" text-anchor="end">derecha</text>',
    ]
    for name in list(dict.fromkeys(list(TEN_TWENTY) + marked)):
        x, y = POSITIONS[name]
        px, py = cx + x * radius, cy - y * radius
        if name in marked:
            parts.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="13" fill="{PALETTE.STABLE}"/>'
                         f'<text x="{px:.1f}" y="{py + 3.5:.1f}" text-anchor="middle" font-size="10" font-weight="bold" '
                         f'fill="{PALETTE.BACKGROUND}">{name}</text>')
        else:
            parts.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="11" fill="none" stroke="{PALETTE.NEUTRAL}"/>'
                         f'<text x="{px:.1f}" y="{py + 3:.1f}" text-anchor="middle" font-size="8.5" '
                         f'fill="{PALETTE.NEUTRAL}">{name}</text>')
    parts.append('</svg>')
    return ''.join(parts)


# ---------------------------------------------------------------- práctica
PRACTICE_WINDOW_S = 4.0
PRACTICE_SHOWN = ('Fp1', 'Fp2', 'O1', 'O2')
PRACTICE_INTRO = (
    'El simulador pasa por el mismo servicio, el mismo filtro de red y el mismo analizador que un equipo real. Todo '
    'lo que ves aquí es **SIMULACIÓN**. Es el mismo simulador que la fuente «Simulador de práctica de BIOCORE» de la '
    'pestaña Clínica: lo que hagas aquí se ve allá.'
)
PRACTICE_OBSERVE = [
    '**Cierra los ojos.** En unos segundos la potencia alfa sube mucho en O1 y O2 y poco adelante; al abrirlos, '
    'baja. Así define el glosario IFCN el ritmo alfa: posterior, con máximo occipital, mejor con los ojos cerrados y '
    'atenuado por la atención visual.',
    '**Parpadea.** El pulso aparece en Fp1 y Fp2, los electrodos más cercanos a los ojos, y casi nada atrás: el ojo '
    'es un dipolo (la córnea es positiva respecto a la retina). Mira «ventanas limpias»: el rechazo por gradiente se '
    'calibró con este mismo pulso del generador y no siempre lo atrapa.',
    '**Afloja un electrodo.** Ese canal se llena de ruido de red y de deriva, y la tabla lo marca. Lo que aparece en '
    'un solo canal es artefacto hasta demostrar lo contrario.',
    '**Desconecta el cable.** En segundo y medio el estado pasa a «sin datos»; a los 4 s se cierra la sesión y se '
    'reintenta sola. Al reconectarlo vuelve a transmitir, con el búfer vacío.',
]
PRACTICE_SIM_NOTE = (
    'Qué imita el simulador: alfa de 10 Hz con máximo en O1 y O2, de 40 µV de pico con los ojos cerrados y a la '
    'cuarta parte con los ojos abiertos (los pesos y la cuarta parte son elecciones del simulador); el parpadeo es '
    'el pulso del generador del laboratorio (unos 50 ms y 80 µV), no un parpadeo registrado.'
)


def _practice_body(service, sim) -> None:
    snap = service.snapshot(seconds=PRACTICE_WINDOW_S)
    st.markdown(f"{STATE_ICONS.get(snap['state'], '⚪')} **{snap['state'].capitalize()}** — {snap['message']}")
    st.caption('🟡 PROCEDENCIA: SIMULACIÓN — simulador de práctica; no es un sensor.')
    render_simulator_controls(sim, st, 'eeglab_tut_sim', fragment=True)
    data, fs, channels = snap['data'], snap['fs'], list(snap['channels'])
    if snap['state'] != 'transmitiendo' or not fs or data.shape[-1] < int(2 * fs):
        return
    mains = MAINS_OPTIONS['60 Hz (México)']
    clean = prepare(data, fs, mains)
    t = np.round((np.arange(clean.shape[1]) - clean.shape[1] + 1) / fs, 3)
    st.line_chart(pd.DataFrame({c: clean[channels.index(c)] for c in PRACTICE_SHOWN}, index=t), height=240)
    st.caption(f'Últimos {PRACTICE_WINDOW_S:.0f} s de Fp1, Fp2, O1 y O2 (µV, sin tendencia y sin red).')
    quality = assess_channels(data, clean, fs, channels, mains)
    rows = []
    analyzer = EegAnalyzer(fs=fs) if EegAnalyzer is not None else None
    for i, name in enumerate(channels):
        row = {'Canal': name, 'Calidad': '✓' if quality[name].ok else '⚠ ' + ', '.join(quality[name].issues)}
        if analyzer is not None:
            r = analyzer.analyze(clean[i])
            row['Banda dominante'] = r.dominant_band if r.available else 'no disponible'
            row['Potencia alfa (µV²)'] = round(r.band_power['alpha'], 1) if r.available else None
            row['Ventanas limpias'] = f'{r.clean_window_count} de {int(PRACTICE_WINDOW_S)}'
        rows.append(row)
    st.dataframe(pd.DataFrame(rows), hide_index=True)
    st.caption('Banda dominante y potencia alfa: EegAnalyzer sobre los últimos 4 s de cada canal. «Calidad»: los '
               'avisos de la sección 6.')


_fragment = getattr(st, 'fragment', None)                      # Streamlit 1.37 o más nuevo
_practice_panel = _fragment(run_every=1.0)(_practice_body) if _fragment is not None else _practice_body


def _render_practice() -> None:
    practice = live_service.get_practice()
    service, sim = practice.service, practice.device
    st.markdown(PRACTICE_INTRO)
    if not service.is_running:
        if st.button('▶ Empezar práctica', key='eeglab_tut_start'):
            sim.plug()
            service.start()
            st.rerun()
        st.caption(PRACTICE_SIM_NOTE)
        return
    if st.button('⏹ Terminar práctica', key='eeglab_tut_stop'):
        service.stop()
        st.rerun()
    _practice_panel(service, sim)
    if _fragment is None:
        st.button('🔄 Actualizar', key='eeglab_tut_refresh')
    st.markdown('**Qué observar**\n\n' + _bullets(PRACTICE_OBSERVE))
    st.caption(PRACTICE_SIM_NOTE + f' Fuentes: {KANE_2017} · {TATUM_2011}')


# ---------------------------------------------------------------- pestaña
def render_live_tutorial() -> None:
    render_section_header(TUTORIAL_TAB)
    st.markdown(INTRO)
    st.markdown('**De dónde sale cada número**\n\n' + _table(('Qué ves', 'De dónde sale', 'Qué tan validado'),
                                                              ORIGIN_TABLE))

    with st.expander('1. Elige tu equipo', expanded=True):
        st.markdown(_table(('Equipo', 'Canales', 'Muestreo', 'Cómo se conecta', 'Dónde funciona'), device_rows()))
        st.caption('Canales y muestreo: descriptores de BrainFlow 5.24.0. Conexión y sistemas: documentación de '
                   'BrainFlow y de OpenBCI, leída el 2026-11-14.')

    with st.expander('2. Seguridad y alcance', expanded=True):
        st.markdown(_bullets(SAFETY))

    names = [d.name for d in DEVICES]
    device = DEVICES[names.index(st.selectbox('Tu equipo (para las secciones 3 y 4)', names, index=2,
                                              key='eeglab_tut_device'))]

    with st.expander('3. Dónde va cada electrodo'):
        if any(c in POSITIONS for c in device.channels):
            st.markdown(montage_svg(device.channels, device.name), unsafe_allow_html=True)
            st.caption(f'En verde, los canales de {device.name}: {", ".join(device.channels)} ({device.names_note}). En '
                       'gris, el resto del sistema 10-20.')
        else:
            st.info(f'{device.name}: {device.names_note}.')
            st.markdown(montage_svg((), 'el sistema 10-20'), unsafe_allow_html=True)
        st.markdown('El sistema 10-20 coloca los electrodos midiendo la cabeza desde cuatro puntos (nasion, inion y '
                    'los dos preauriculares) y tomando el 10 o el 20 % de esas medidas; el 10-10 agrega electrodos en '
                    'pasos del 10 %, como AF7, PO7 o TP9. Las letras F, T, P y O dicen el lóbulo de abajo (frontal, '
                    'temporal, parietal, occipital), C la región central y Fp los frontopolares. Los números impares '
                    'van a la izquierda, los pares a la derecha, y la «z» (de cero) marca la línea media.')
        st.caption(f'Esquema sobre una cabeza esférica ideal, no las coordenadas de una cabeza real. Fuentes: '
                   f'{KANE_2017} · {SEECK_2017}')

    with st.expander('4. Conecta tu equipo'):
        st.markdown(f'**{device.name}** — {device.connection}')
        if device.platforms:
            st.caption(f'Dónde funciona: {device.platforms}')
        st.markdown(_numbered(list(device.steps)))
        st.markdown('**En BIOCORE**\n\n' + _numbered(APP_STEPS))
        if device.source:
            st.caption(f'Fuente: {device.source}')

    with st.expander('5. Qué significa cada estado'):
        st.markdown(_table(('Estado', 'Qué pasa'), STATES))
        st.markdown('**Procedencia**\n\n' + _table(('Insignia', 'Cuándo', 'Cómo se guarda al gemelo'),
                                                   PROVENANCE_ROWS))

    with st.expander('6. Calidad de la señal'):
        st.markdown(_table(('Aviso', 'Cuándo aparece', 'Qué hacer'), quality_rows()))
        st.markdown('El **filtro de la red eléctrica** quita el zumbido de 60 Hz (México) o 50 Hz (Europa): la fuente '
                    'más común de ese ruido es la corriente alterna de los aparatos y contactos cercanos, y un '
                    'electrodo con mal contacto lo empeora.')
        st.caption(f'Umbrales: de ingeniería, sin cita clínica. Qué hacer: {TATUM_2011}')

    with st.expander('7. Qué puedes y qué no puedes concluir'):
        st.markdown(_bullets(limits()))
        st.caption(f'Fuentes: {KANE_2017} · Donoghue T et al. Parameterizing neural power spectra into periodic and '
                   'aperiodic components. Nature Neuroscience 2020;23:1655-1665')

    render_section_header('8. Practica sin equipo (SIMULACIÓN)')
    _render_practice()
