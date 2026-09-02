"""EEG-Neuro-Lab — integra la página EEG original en la pestaña Clínica
y añade las demás vistas requeridas.
"""

import os
import runpy
import streamlit as st

from app.utils.design_system import render_module_header, render_section_header, render_error_state, render_empty_state

# Reubicado (Tanda de eliminación de pages_legacy, Movimiento 1, 2026-07-13):
# antes apuntaba a app/pages_legacy/8_🧠_EEG-Neuro-Lab.py — mismo contenido,
# copiado tal cual a page_content.py junto a este archivo, sin cambiar una línea.
MODULE_EMOJI = os.path.join(os.path.dirname(__file__), 'page_content.py')

def render_views():
    # Consolidación, Tanda 1 (2026-07-13): la pestaña "IA" se eliminó — era una
    # sola línea estática ("Modelos para detección de crisis y herramientas
    # explicables") sin ningún cálculo detrás (Art. I). La Vista Clínica real
    # (tabs[0]) no se tocó.
    # Capa 2, Fase 2.2, Ejecución 2 (2026-08-21): "Educativa"/"Investigación"/
    # "Simulación"/"Gemelo Digital" retiradas -- eran header+write sin
    # contenido (fachada de estructura, R1/R3); llenarlas habría requerido
    # fabricar análisis de bandas/conectividad/simuladores que no existen hoy
    # en el repo. Candidatas a contenido futuro, ver CHANGELOG.md.
    # Fase 2.3 Tanda 3 (2026-08-29): título de módulo con el sistema
    # compartido -- este módulo no tenía ninguno propio.
    render_module_header("EEG Neuro Lab", icon="🧠")
    tabs = st.tabs(["Clínica"])

    with tabs[0]:
        render_section_header("Vista Clínica")
        if os.path.exists(MODULE_EMOJI):
            try:
                runpy.run_path(MODULE_EMOJI, run_name='__main__')
            except Exception as e:
                render_error_state("No se pudo renderizar la Vista Clínica de EEG Neuro Lab.", exception=e)
        else:
            render_empty_state("EEG Neuro Lab no encontrado", action="verifica la instalación del módulo")


def main():
    render_views()


def run():
    """Wrapper entrypoint compatible with importing as `run` from supermodules.

    NOTA (2026-07-03): antes había también un `try: main() except ...` a nivel
    de módulo, que se ejecutaba una vez al importar y otra vez aquí — doble
    renderizado la primera vez que se importaba el módulo en un proceso. Se
    eliminó; `run()` es ahora el único punto de entrada, igual que en
    twin_shell/academia."""
    try:
        main()
    except Exception as e:
        render_error_state("No se pudo cargar EEG Neuro Lab.", exception=e)
