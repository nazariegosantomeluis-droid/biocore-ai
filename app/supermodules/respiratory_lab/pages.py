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

from app.utils.design_system import render_module_header, render_section_header, render_error_state

# Reubicado (Tanda de eliminación de pages_legacy, Movimiento 1, 2026-07-13):
# antes apuntaba a app/pages_legacy/7_💨_Respiratory-Lab.py — mismo contenido,
# copiado tal cual a page_content.py junto a este archivo, sin cambiar una línea.
MODULE_EMOJI = os.path.join(os.path.dirname(__file__), 'page_content.py')

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
    render_module_header("Respiratory Lab", icon="💨")
    tabs = st.tabs(["Clínica", "Investigación", "Simulación"])

    with tabs[0]:
        render_section_header("Vista Clínica")
        if os.path.exists(MODULE_EMOJI):
            try:
                runpy.run_path(MODULE_EMOJI, run_name='__main__')
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
    """Detalle del AHI y eventos de apnea -- reutiliza el análisis YA calculado
    por RespiratoryAnalyzer en la Vista Clínica (page_content.py), leído vía
    st.session_state. No vuelve a calcular nada: el bloque `with tabs[0]:` de
    arriba ya corrió y pobló `_respiratory_lab_analysis` antes de llegar aquí,
    en el mismo rerun de Streamlit (2026-08-21, Capa 2 Fase 2.2, Ejecución 2)."""
    st.header("Vista Investigación — Índice AHI y eventos de apnea")

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

    col1, col2, col3 = st.columns(3)
    col1.metric("Índice AHI", f"{analysis.apnea_hypopnea_index:.1f}", help="Eventos de apnea/hipopnea por hora")
    col2.metric("Severidad", analysis.severity.title())
    col3.metric("Eventos de apnea detectados", len(analysis.apnea_events))

    if analysis.apnea_detected and analysis.apnea_events:
        import pandas as pd
        events_df = pd.DataFrame([
            {
                "Evento": i,
                "Inicio (s)": f"{event['start_time']:.1f}",
                "Fin (s)": f"{event['end_time']:.1f}",
                "Duración (s)": f"{event['duration']:.1f}",
                "Tipo": event['type'].capitalize(),
            }
            for i, event in enumerate(analysis.apnea_events, 1)
        ])
        st.dataframe(events_df, use_container_width=True, hide_index=True)
        st.download_button(
            "⬇️ Exportar eventos de apnea (CSV)",
            events_df.to_csv(index=False).encode('utf-8'),
            file_name="respiratory_apnea_events.csv",
            mime="text/csv",
        )
    else:
        st.success("✅ No se detectaron eventos de apnea en el patrón/parámetros actuales de la Vista Clínica.")

    st.divider()
    _render_save_to_twin(analysis, bridge['pattern_display'])


def _render_save_to_twin(analysis, pattern_display: str) -> None:
    """Piloto de integración estrecha (2026-08-24, Capa 2 Fase 2.4): primer
    lab que escribe al UPS real, con botón explícito -- mismo patrón que
    Patient Pipeline (`app/main.py::render_patient_pipeline_page()`), nunca
    automático (evita inundar la trayectoria con un snapshot por cada
    interacción de widget).

    Paciente destino: Fase 3 (paciente único de sesión, 2026-08-30) formalizó
    lo que este piloto ya hacía por convención -- `get_active_patient_id()`/
    `get_active_session_factory()` (`app/utils/patient_session.py`) son
    ahora el único punto de verdad, reemplazando la lectura directa de
    `twin_shell_ups_session_factory`/`twin_shell_ups_patient_id` que este
    archivo tenía inline (1 de los 4 sitios que copiaban ese bootstrap).
    Mismo paciente de siempre -- Twin OS/ECG Lab/HRV/Patient Pipeline lo
    comparten todos a través de la misma función.

    Qué escribe -- solo lo real con destino Y efecto (cruce del recon de
    2.4.0): `respiratory_rate`, `spo2` (mapeado desde `analysis.baseline_spo2`,
    no `minimum_spo2` -- representa el nivel de reposo/estable del patrón
    actual, coherente con cómo Patient Pipeline/Twin OS tratan `spo2` como
    un valor de estado, no un nadir puntual durante un evento) y `ahi`.
    `rr_variability`/`apnea_type`/`breathing_pattern`/etc. NO se escriben --
    no tienen destino en el schema (`PhysiologicalDescriptor.value` es
    float, y esos campos son categóricos o sin slot) -- no se fuerzan.

    Procedencia: `Provenance.SIMULACION` (señal generada por
    `RespiratorySignalGenerator`, nunca un sensor real) con `source_detail`
    describiendo el origen exacto -- mismo criterio que Patient Pipeline
    etiqueta su entrada manual como `"patient_pipeline:entrada_manual"`.

    La raíz cardiovascular (Fase 2.4, gate ya cerrado en el builder) hace su
    trabajo aquí sola: como `update_from_sensors()` solo recibe `"respiratory"`,
    el dominio cardiovascular del estado resultante queda vacío -- no hay
    corazón fantasma que evitar a mano."""
    st.markdown("#### 🔗 Guardar estado al gemelo")
    st.caption(
        "Escribe `respiratory_rate`/`spo2`/`ahi` reales (del análisis de arriba) al Unified "
        "Physiological State, bajo el mismo paciente que renderiza Digital Twin OS -- sus "
        "pulmones reaccionarán a estos valores la próxima vez que abras esa página o pulses "
        "\"Sincronizar\" ahí. Procedencia: simulación (señal generada, no un sensor real)."
    )
    if st.button("💾 Guardar estado al gemelo", key="respiratory_lab_save_to_ups"):
        from domain.physiology.state import Provenance, from_digital_twin_organism, save_state
        from app.engines.digital_twin_organism import DigitalTwinOrganism
        from app.utils.patient_session import get_active_patient_id, get_active_session_factory

        session_factory = get_active_session_factory()
        patient_id = get_active_patient_id()

        organism = DigitalTwinOrganism()
        organism.update_from_sensors({
            "respiratory": {
                "respiratory_rate": float(analysis.respiratory_rate),
                "spo2": float(analysis.baseline_spo2),
                "ahi": float(analysis.apnea_hypopnea_index),
            }
        })
        state = from_digital_twin_organism(
            organism, patient_id, provenance=Provenance.SIMULACION,
            source_detail=f"respiratory_lab:investigacion:patron={pattern_display}",
        )
        with session_factory() as session:
            snapshot_id = save_state(session, state)

        st.success(f"Estado guardado al gemelo -- snapshot: {snapshot_id}")
        st.caption(
            f"cardiovascular: {len(state.cardiovascular.descriptors)} descriptores "
            f"(vacío esperado -- este lab no envía dato cardíaco) · "
            f"respiratory: {len(state.respiratory.descriptors)} descriptores"
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
    st.header("Vista Simulación — Generador respiratorio paramétrico")
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

    col_ptp, col_cycles = st.columns(2)
    chest_ptp = float(np.max(chest) - np.min(chest))
    col_ptp.metric("Amplitud torácica (pico-a-pico)", f"{chest_ptp:.2f}")
    col_cycles.metric("Ciclos respiratorios en 30s", f"{(30 * sim_rr / 60):.0f}")

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
