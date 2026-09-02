"""ECG-12 Derivaciones — integra la página 12-leads existente en la pestaña Clínica
y añade vistas para educación, investigación, IA, simulación y gemelo.
"""

import os
import runpy
import streamlit as st

from app.utils.design_system import render_section_header, render_error_state, render_empty_state

# Reubicado (Tanda de eliminación de pages_legacy, Movimiento 1, 2026-07-13):
# antes apuntaba a app/pages_legacy/6_📋_ECG-12-Derivaciones.py — mismo contenido,
# copiado tal cual a page_content.py junto a este archivo, sin cambiar una línea.
MODULE_EMOJI = os.path.join(os.path.dirname(__file__), 'page_content.py')

def render_views():
    # Fase 2.3 Tanda 3 (2026-08-29): ECG-12 se alcanza como pestaña dentro
    # del hub "ECG Lab" (render_ecg_lab_page(), que ya muestra
    # render_module_header("ECG Lab")) -- sus "Vista X" son encabezados de
    # SECCIÓN, no un segundo título de módulo duplicado (mismo criterio que
    # la pestaña "Monitoreo").
    # Consolidación, Tanda 1 (2026-07-13): la pestaña "IA" se eliminó — era una
    # sola línea estática ("Modelos de clasificación de 12 derivaciones y
    # explicaciones") sin ningún cálculo detrás (Art. I). La Vista Clínica real
    # (tabs[0]) no se tocó.
    # Capa 2, Fase 2.2, Ejecución 2 (2026-08-21): "Investigación"/"Simulación"/
    # "Gemelo Digital" retiradas -- eran header+write sin contenido (fachada de
    # estructura, R1/R3). "Educativa" se llenó con un puntero honesto a la
    # tabla real de 12 derivaciones (Academia Clinica), no una lección
    # fabricada. Ver CHANGELOG.md.
    tabs = st.tabs(["Clínica", "Educativa"])

    with tabs[0]:
        render_section_header("Vista Clínica — ECG 12 Derivaciones")
        if os.path.exists(MODULE_EMOJI):
            try:
                runpy.run_path(MODULE_EMOJI, run_name='__main__')
            except Exception as e:
                render_error_state("No se pudo renderizar la Vista Clínica de ECG-12.", exception=e)
        else:
            render_empty_state(
                "ECG-12 no encontrado", action="se requiere la implementación original para contenido clínico completo"
            )

    with tabs[1]:
        render_section_header("Vista Educativa")
        st.info(
            "🩺 **Derivaciones ECG** — la tabla real de las 12 derivaciones (localización, "
            "territorio, cara afectada) está disponible en **Learning Hub → 🏫 Academia Clinica → "
            "Lecciones y Casos → 📖 Teoría**."
        )


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
        render_error_state("No se pudo cargar ECG-12.", exception=e)
