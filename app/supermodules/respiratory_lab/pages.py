"""Respiratory-Lab — integra la página respiratoria existente en la vista Clínica
y añade las demás vistas del Biomedical Cognitive Exploration Lab.
"""

import os
import runpy
import numpy as np
import streamlit as st

try:
    import plotly.graph_objects as PLOTLY_GO
    PLOTLY_OK = True
except ImportError:
    PLOTLY_GO, PLOTLY_OK = None, False

from app.utils.design_system import BADGES, render_module_header, render_section_header, render_error_state, render_metric_card
from app.supermodules.respiratory_lab import views

# Reubicado (Tanda de eliminación de pages_legacy, Movimiento 1, 2026-07-13):
# antes apuntaba a app/pages_legacy/7_💨_Respiratory-Lab.py — mismo contenido,
# copiado tal cual a page_content.py junto a este archivo, sin cambiar una línea.
MODULE_EMOJI = os.path.join(os.path.dirname(__file__), 'page_content.py')

# Tanda 1 de contención (2026-11-05, Art. I): la insignia de validación de este
# módulo (firma AASM de la Tanda Final) se RETIRÓ. El inventario del 2026-11-05
# midió que `RespiratoryAnalyzer` devolvía FR = 60.0 constante y 0 apneas con
# cualquier señal (incluidos los patrones de apnea), así que la firma ya no
# describía lo que el módulo calculaba. En la fase 3 (2026-11-07) el detector se
# reparó contra golden tests, pero la insignia NO se reactiva.
class VistaClinicaOmitida(Exception):
    """La vista clínica no se dibuja (parámetros imposibles). Se captura aquí para que las demás pestañas se
    sigan dibujando, en vez del `st.stop()` que dejaba toda la página a medias."""


RESPIRATORY_STATUS_NOTICE = (
    "**Arco respiratorio, fase 3 (2026-11-07).** Se muestran solo los valores con golden test: frecuencia respiratoria "
    "(60 / media de los intervalos entre inspiraciones; banda NEWS2), duración del ciclo y su variabilidad, apneas "
    "(≥ 10 s con caída ≥ 90 %, Berry 2012; tipo por esfuerzo = Criterio BIOCORE), la tasa equivalente por hora de "
    "**registro** (extrapolada, sin valor diagnóstico) y la SpO₂ del modelo BIOCORE (simulación). **Siguen ocultos:** "
    "hipopneas, relación I:E, patrón respiratorio, notas clínicas, ODI y la categoría de severidad (que vive en "
    "Calculadoras Clínicas). Este laboratorio **no escribe al gemelo** y **no lleva insignia de validado**. La señal es "
    "simulada (se declara así); los resultados no son una medición de un paciente."
)


def render_views():
    # Consolidación, Tanda 1 (2026-07-13): la pestaña "IA" se eliminó — era una
    # sola línea estática ("Modelos de detección de apnea y explicabilidad")
    # sin ningún cálculo detrás (Art. I). La Vista Clínica real (tabs[0]) no
    # se tocó.
    # Capa 2, Fase 2.2, Ejecución 2 (2026-08-21): "Educativa" y "Gemelo
    # Digital" retiradas -- eran header+write sin contenido (fachada de
    # estructura, R1/R3); "Educativa" era candidata a contenido futuro (ver
    # CHANGELOG.md), "Gemelo Digital" no lo es -- es destino de integración de
    # la Fase 2.4, no una pestaña a construir aquí. "Investigación" y
    # "Simulación" se llenaron con contenido real (ver funciones abajo).
    # Fase 2.3 Tanda 3 (2026-08-29): título de módulo con el sistema
    # compartido -- este módulo no tenía ninguno propio (el card decorativo
    # de page_content.py, dentro de la pestaña Clínica, no cuenta como
    # título de módulo consistente con el resto de la app).
    # `validation=None` EXPLÍCITO -- no un olvido: la insignia de validado NO se reactiva en la fase 3
    # (decisión del arco: llegará, si llega, tras la validación experta); ver `RESPIRATORY_STATUS_NOTICE`.
    render_module_header("Respiratory Lab", icon="💨", validation=None)
    st.info(RESPIRATORY_STATUS_NOTICE, icon="🫁")
    tabs = st.tabs(["Clínica", "Investigación", "Simulación"])

    with tabs[0]:
        render_section_header("Vista Clínica")
        if os.path.exists(MODULE_EMOJI):
            try:
                runpy.run_path(MODULE_EMOJI, run_name='__main__')
            except VistaClinicaOmitida:
                pass  # el error ya está junto al control afectado; las otras pestañas se siguen dibujando
            except Exception as e:
                render_error_state(
                    "No se pudo renderizar la Vista Clínica de Respiratory Lab.",
                    exception=e,
                )
        else:
            st.info("Respiratory Lab no encontrado. Implementación de plantilla.")

    with tabs[1]:
        _render_investigacion_tab()

    with tabs[2]:
        _render_simulacion_tab()


def _render_investigacion_tab():
    """Vista Investigación (fase 3): eventos de apnea con su tabla, tiempo total y la tasa equivalente por hora de
    REGISTRO (extrapolada, sin valor diagnóstico). Lee el análisis que ya calculó la Vista Clínica."""
    render_section_header("Apneas y tasa equivalente por hora de registro")

    bridge = st.session_state.get('_respiratory_lab_analysis')
    if bridge is None:
        st.info(
            "Aún no hay un análisis disponible -- abre primero la Vista Clínica "
            "en esta misma carga de página para generarlo."
        )
        return

    analysis = bridge['analysis']
    st.caption(
        f"Datos del análisis activo en Vista Clínica: patrón **{bridge['pattern_display']}**, "
        f"ventana de **{bridge['duration']}s**. Mismo cálculo, sin recalcular."
    )
    views.render_apnea_cards(analysis)
    views.render_events_table(analysis)
    views.render_calculator_link("resp_osa_link_research")

    st.divider()
    _render_save_to_twin_disabled()


def _render_save_to_twin_disabled() -> None:
    """Guardar al gemelo -- DESACTIVADO (Tanda 1 de contención, 2026-11-05).

    El botón escribía `respiratory_rate=analysis.respiratory_rate` (siempre 60.0)
    y el índice de apneas por hora (siempre 0.0) al UPS con procedencia
    `SIMULACION`: una constante disfrazada de medición, que el narrador, el
    clasificador de riesgo y el cuerpo visual leerían como dato del paciente
    (Art. I). Este laboratorio no escribe al UPS por ninguna ruta mientras el
    analizador no se repare; no hay botón ni código de escritura aquí."""
    st.markdown("#### 🔗 Guardar estado al gemelo")
    st.caption(
        "Desactivado: no se reactiva en esta fase. Volverá con su procedencia («Simulación — modelo BIOCORE») en la fase 4, "
        "solo para los campos validados."
    )


def _render_simulacion_tab():
    """Simulador paramétrico real: RR y volumen corriente (profundidad)
    regeneran la señal a través de RespiratorySignalGenerator/RespiratoryPattern
    -- el mismo motor que ya usa la Vista Clínica, patrón fijo en "normal".
    Barandilla anti-placebo (lección de Multisensor, 2026-08-20/21): verificado
    por ejecución que ambos sliders cambian el arreglo generado, no solo la
    etiqueta -- ver CHANGELOG.md para la prueba (amplitud torácica pico-a-pico
    escala con volumen corriente; el conteo de ciclos en la ventana escala con
    RR, tal como usa `cycle_duration = 60.0 / respiratory_rate` dentro del
    generador real)."""
    render_section_header("Vista Simulación — Generador respiratorio paramétrico")
    st.write(
        "Ajusta frecuencia respiratoria y volumen corriente (profundidad) y observa la señal "
        "real regenerada por `RespiratorySignalGenerator` (patrón normal) -- el mismo motor que "
        "usa la Vista Clínica, no una animación separada."
    )

    from src.signals.respiration import RespiratorySignalGenerator, RespiratoryPattern

    sim_rr = st.slider('Frecuencia respiratoria (resp/min)', 6, 40, 15, key='resp_sim_rr')
    sim_tv = st.slider('Volumen corriente / profundidad (L)', 0.1, 1.5, 0.5, step=0.1, key='resp_sim_tv')

    generator = RespiratorySignalGenerator(sampling_rate=100)
    params = RespiratoryPattern(respiratory_rate=sim_rr, tidal_volume=sim_tv, pattern_type='normal')
    sim_data = generator.generate_respiration(duration=30, params=params)
    chest = sim_data['chest_wall']
    airflow = sim_data['airflow']
    time_arr = sim_data['time']

    # Consolidación Visual Tanda 3 (2026-09-21): `col.metric` crudo ->
    # `render_metric_card`. `BADGES.HEURISTIC`: propiedades descriptivas
    # de una señal SIMULADA (generador paramétrico bajo control de
    # sliders) -- cálculo real, sin cita/umbral clínico detrás.
    col_ptp, col_cycles = st.columns(2)
    chest_ptp = float(np.max(chest) - np.min(chest))
    with col_ptp:
        render_metric_card(
            "Amplitud torácica (pico-a-pico)", f"{chest_ptp:.2f}",
            provenance=BADGES.HEURISTIC,
        )
    with col_cycles:
        render_metric_card(
            "Ciclos objetivo en 30 s (calculado de la FR elegida, no medido)", f"{(30 * sim_rr / 60):.0f}",
            provenance=BADGES.HEURISTIC,
        )

    if PLOTLY_OK:
        fig = PLOTLY_GO.Figure()
        fig.add_trace(PLOTLY_GO.Scatter(x=time_arr, y=airflow, name='Flujo de aire', line=dict(color='#8ecae6')))
        fig.add_trace(PLOTLY_GO.Scatter(x=time_arr, y=chest, name='Pared torácica', line=dict(color='#7c3aed')))
        fig.update_layout(template='plotly_dark', height=360, title='Señal respiratoria regenerada')
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.line_chart({'Flujo de aire': airflow, 'Pared torácica': chest})

    st.caption(
        "**Ambos sliders mueven la señal de verdad**: el volumen corriente escala la amplitud "
        "torácica de forma proporcional (verificado por ejecución: p.ej. 0.2L≈0.45 pico-a-pico, "
        "1.2L≈2.45 pico-a-pico); la frecuencia cambia `cycle_duration = 60/RR` dentro del generador, "
        "así que a mayor RR verás más ciclos comprimidos en la misma ventana de 30s."
    )


def main():
    render_views()


def run():
    """Wrapper entrypoint compatible with importing as `run` from supermodules.

    NOTA (2026-08-20, Capa 2 Fase 2.1, cierre): este archivo tenía también un
    `try: main() except ...` a nivel de módulo, que se ejecutaba una vez al
    importar y otra vez aquí -- doble renderizado en cada carga de página
    (mismo bug ya identificado y corregido en `ecg_12/pages.py` y
    `eeg_neuro_lab/pages.py` el 2026-07-03, nunca aplicado aquí). Quedó
    enmascarado hasta ahora por el `st.set_page_config()` duplicado de
    `page_content.py` (también retirado en esta tanda), que fallaba primero
    y ocultaba el síntoma real (IDs de widget duplicados, p.ej. el
    `st.sidebar.selectbox` del selector de patrón respiratorio). Se elimina
    el `try: main()` de módulo; `run()` es ahora el único punto de entrada,
    igual que en `ecg_12`/`eeg_neuro_lab`/`twin_shell`/`academia`. Ver
    CHANGELOG.md."""
    try:
        main()
    except Exception as e:
        render_error_state("No se pudo cargar Respiratory Lab.", exception=e)
