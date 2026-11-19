"""Instrumentos de EMG (T4 de la ruta integrada, 2026-11-18).

El código se movió tal cual desde `render_emg_page()`, `_render_emg_lab()` y `_render_emg_save_to_twin()` de
`app/main.py`: ningún cálculo, texto, cita ni compuerta cambió. La página de siempre es la composición de estos
instrumentos con `PAGE` (mismos controles sin clave en el menú lateral); una estación de la ruta los monta con
`station_context(prefijo)`.

- `fuente`: origen (demo, CSV o, solo en la página, el sensor en vivo), patrón, fs y duración.
- `trazo`: el trazo, la «activación muscular» (promedio/pico, no %MVC) y el RMS con su tema firmado (A5).
- `guardar`: el único camino de escritura al UPS de este laboratorio (botón explícito; un CSV no se escribe)."""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Any, Callable, Optional

import numpy as np
import streamlit as st

from app.instruments.base import InstrumentContext, InstrumentResult
from app.instruments.common import CSV_SAVE_BLOCKER
from app.utils.design_system import BADGES, render_error_state, render_metric_card

DEMO_SOURCE = 'Demo'
CSV_SOURCE = 'CSV'


def generate_demo_emg_signal(fs: float, duration: float, pattern: str) -> np.ndarray:
    n = int(fs * duration)
    t = np.arange(n) / fs
    if pattern == "Isométrica":
        env = 0.6 + 0.2 * np.sin(2*np.pi*0.5*t)
    elif pattern == "Rápida":
        env = 0.4 + 0.5*np.exp(-((t-duration/2)**2)/0.25)
    else:
        env = 0.6 + 0.3*(1-t/max(duration, 1))
    return env * np.random.normal(0, 1, n) + 0.05*np.sin(100*np.pi*t)


@dataclass
class EmgSignal:
    signal: Optional[np.ndarray]
    time_arr: np.ndarray
    fs: float
    source: str
    live: Any = None


def fuente(ctx: InstrumentContext, demo: Callable = generate_demo_emg_signal) -> EmgSignal:
    """La señal EMG. `demo` es el generador de la señal demo (la página pasa el suyo, que las pruebas sustituyen por
    una señal fija)."""
    from app.supermodules.biosensors import emg as emg_live

    panel = ctx.panel
    k = ctx.auto_key
    sources = [DEMO_SOURCE, CSV_SOURCE] + ([] if ctx.in_station else [emg_live.SOURCE_LABEL])
    source = panel.radio('Origen EMG', sources, key=k('emg_source'))
    pattern = panel.selectbox('Patrón', ['Isométrica','Rápida','Fatiga'], key=k('emg_pattern'))
    fs = panel.selectbox('fs (Hz)', [500,1000,2000], index=1, key=k('emg_fs'))
    duration = panel.slider('Duración (s)', 5, 60, 15, key=k('emg_duration'))

    signal = None
    time_arr = np.array([])
    live = None
    if source == CSV_SOURCE:
        f = st.file_uploader('CSV EMG', type=['csv'], key=k('emg_csv'))
        if f:
            try:
                data = np.genfromtxt(io.StringIO(f.read().decode()), delimiter=',')
                signal = data if data.ndim == 1 else data[:, 0]
                time_arr = np.arange(len(signal)) / fs
            except Exception as e:
                render_error_state(
                    "No se pudo leer el archivo CSV de EMG -- verifica el formato.",
                    exception=e,
                )
    elif source == emg_live.SOURCE_LABEL:
        # Sin placa transmitiendo no hay señal: no se usa la demo de respaldo (2026-11-14, Art. I).
        live = emg_live.render_emg_source(duration)
        if live is not None:
            signal, fs = live.signal, live.fs
            time_arr = np.arange(len(signal)) / fs
    else:
        signal = demo(fs, duration, pattern)
        time_arr = np.arange(len(signal)) / fs
    return EmgSignal(signal, time_arr, fs, source, live)


def trazo(ctx: InstrumentContext, sig: EmgSignal):
    """El trazo y los valores clave. Devuelve el análisis del `EmgAnalyzer` (o `None` sin señal)."""
    from app.supermodules import safe_import_plotly
    from app.supermodules.biosensors import emg as emg_live
    from app.supermodules.learn_theory import SIGNED_EMG_A1, SIGNED_EMG_A5
    from app.utils.design_system import render_theory_topic
    from src.signals.emg import EmgAnalyzer

    PLOTLY_GO, _, _ = safe_import_plotly()
    signal, time_arr, fs, live = sig.signal, sig.time_arr, sig.fs, sig.live
    if signal is None:
        return None
    emg_analysis = EmgAnalyzer(fs).analyze(signal)

    st.plotly_chart(PLOTLY_GO.Figure(PLOTLY_GO.Scatter(x=time_arr, y=signal, name='EMG cruda')),
                    use_container_width=True, key=ctx.k('emg_lab_trace'))
    activation = emg_analysis.activation_pct
    # 2026-11-14 (Art. I): `activation_pct` es media/máximo del EMG rectificado: casi igual en reposo y en contracción.
    # Pulido profesional: es la definición del cálculo, con su etiqueta de método, y conserva sus advertencias.
    render_metric_card('Activación muscular', f'{activation:.1f} %', provenance=BADGES.METHOD)
    st.caption('Cociente entre el promedio y el pico del EMG rectificado y filtrado (20-450 Hz). Describe la forma de '
               'la señal: no es el porcentaje de la contracción máxima (%MVC). En reposo y en una contracción sostenida '
               'da valores parecidos: no lo uses para decir esfuerzo, fatiga ni riesgo.')
    # Teoría citada 2 (2026-11-17, Art. I): decía «Para saber cuánto contraes, mira el RMS: crece con la contracción»,
    # es decir, deducía la fuerza de la amplitud. Lo firmado (A1, A9) dice lo contrario:
    st.caption(SIGNED_EMG_A1.detail)
    rms_value = emg_live.rms_mv(emg_live.prepare(signal, fs, None), fs)
    render_metric_card(
        'RMS del EMG (20-450 Hz)',
        None if rms_value is None else (f'{rms_value:.3f} mV' if live is not None else f'{rms_value:.3f} (unidades de la señal)'),
        provenance=BADGES.METHOD,
        unavailable_reason=None if rms_value is not None else 'señal demasiado corta para filtrar',
    )
    if live is not None:
        st.caption('mV en la piel aproximados: ganancia 200 del MyoWare y ADC del ESP32 sin calibrar.')
    with st.expander('¿Qué significa RMS del EMG?', expanded=False):        # tema A5 firmado
        render_theory_topic(SIGNED_EMG_A5, inside_expander=True)
    return emg_analysis


def guardar(ctx: InstrumentContext, sig: EmgSignal, emg_analysis) -> InstrumentResult:
    """Capa 5A dominio muscular, Tanda 3 (2026-09-10): botón explícito, opt-in. Lo que llega al músculo del UPS es la
    `activation` y la `median_frequency` MEDIDAS por `EmgAnalyzer` sobre la señal filtrada, no un slider. Qué NO se
    envía: `fatigue_index` (con la señal demo es una constante; `_muscular_state()` lo difiere). Fase 0 (2026-11-13): el
    organismo ya no deriva nada del músculo, así que al UPS llegan EXACTAMENTE las dos medidas.

    Procedencia (2026-11-14): `SENSOR_REAL` solo con la placa real transmitiendo y sin avisos de calidad; la demo y la
    placa simulada van como `SIMULACION`; un CSV cargado no se escribe (2026-11-16: archivo sin procedencia
    verificable, `CSV_SAVE_BLOCKER`).

    T4 (2026-11-18): antes `_render_emg_save_to_twin()` de `app/main.py`. Con `PAGE`, la clave del botón es la de
    siempre (`emg_lab_save_to_ups`). `saved_snapshot_id` dice qué snapshot se escribió en este rerun (o `None`)."""
    from app.utils.patient_session import get_active_patient_id, get_active_session_factory
    from domain.physiology.state import from_digital_twin_organism, save_state

    source, live = sig.source, sig.live
    st.markdown("---")
    st.markdown(f"#### {ctx.deco('🔗')}Guardar estado al gemelo")

    if emg_analysis is None:
        # Origen=CSV sin archivo: el botón no finge, declara que no hay señal analizable que persistir.
        if ctx.in_station:                 # la estación no ofrece la placa en vivo: no la menciona
            st.info("Sin señal EMG analizable (CSV sin archivo cargado). No hay nada que persistir al gemelo: carga "
                    "un CSV o cambia el Origen a Demo.")
        else:
            st.info(
                "Sin señal EMG analizable (CSV sin archivo cargado, o placa en vivo sin transmitir). No hay nada "
                "que persistir al gemelo -- carga un CSV, conecta la placa en vivo o cambia el Origen a Demo."
            )
        return InstrumentResult()

    if source == CSV_SOURCE:
        # Contención antes de la prueba con estudiantes (2026-11-16, Art. I): un CSV cargado se escribía al gemelo
        # como SIMULACION, pero no es una simulación: no se sabe de quién ni de qué equipo viene.
        st.button(f"{ctx.deco('💾')}Guardar estado al gemelo", key=ctx.k("emg_lab_save_to_ups"), disabled=True,
                  help=CSV_SAVE_BLOCKER)
        st.warning(f"{ctx.deco('⛔')}No se guarda al gemelo: {CSV_SAVE_BLOCKER}.")
        return InstrumentResult()

    from app.supermodules.biosensors import emg as emg_live

    twin_prov, twin_note = emg_live.twin_provenance(live)
    st.caption(
        f"Escribe la **«activación muscular»** ({emg_analysis.activation_pct:.1f}%: promedio/pico del EMG "
        f"rectificado, no %MVC) y la **frecuencia mediana** ({emg_analysis.median_frequency_hz:.1f} Hz) "
        "analizadas de esta señal al estado fisiológico unificado (UPS) del paciente activo: el gemelo digital las "
        "mostrará con su procedencia la próxima vez que lo abras. Vienen del analizador de EMG (señal filtrada "
        "20-450 Hz), no del control «Fatiga muscular» del gemelo. "
        f"El índice de fatiga no se escribe (heurístico, sin calibrar: diferido). {twin_note}"
    )
    blocker = emg_live.save_blocker(live)
    if blocker:
        st.warning(f"{ctx.deco('⛔')}No se guarda al gemelo: {blocker}")
        return InstrumentResult()
    if not st.button(f"{ctx.deco('💾')}Guardar estado al gemelo", key=ctx.k("emg_lab_save_to_ups")):
        return InstrumentResult()
    from app.engines.digital_twin_organism import DigitalTwinOrganism

    session_factory = get_active_session_factory()
    patient_id = get_active_patient_id()

    emg_organism = DigitalTwinOrganism()
    emg_organism.update_from_sensors({
        "emg": {
            "activation": float(emg_analysis.activation_pct),
            "median_frequency": float(emg_analysis.median_frequency_hz),
        }
    })
    state = from_digital_twin_organism(
        emg_organism, patient_id, provenance=twin_prov,
        source_detail=f"emg_muscle_lab:origen={live.label if live is not None else source}",
    )
    with session_factory() as session:
        snapshot_id = save_state(session, state)

    st.success(f"Estado guardado al gemelo -- snapshot: {snapshot_id}")
    muscular = state.muscular
    if muscular.descriptors:
        st.caption(
            f"muscular: {len(muscular.descriptors)} descriptores · "
            f"activation = {muscular.get('activation').value:.1f}% "
            f"({muscular.get('activation').provenance.value}) · "
            f"median_frequency = {muscular.get('median_frequency').value:.1f} Hz · "
            "sin derivados del organismo (fase 0: health_score, risk_score, neuromuscular_efficiency y "
            "movement_smoothness retirados) · sin fatigue_index (diferido) · sin campos fantasma"
        )
    else:
        st.caption("muscular: 0 descriptores (gate no cumplido -- inesperado con activation enviada)")
    st.caption(
        f"cardiovascular: {len(state.cardiovascular.descriptors)} · "
        f"respiratory: {len(state.respiratory.descriptors)} · "
        f"neurological: {len(state.neurological.descriptors)} "
        "(vacíos esperados -- este laboratorio solo envía EMG)"
    )
    return InstrumentResult(saved_snapshot_id=snapshot_id)
