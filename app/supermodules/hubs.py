"""Los destinos del menú (T5 de la ruta integrada, 2026-11-18; diseño firmado, «Navegación nueva (T5)»).

El menú baja a cinco destinos: Hoy, Ruta, Paciente, Biblioteca y Ajustes. Las páginas de antes no desaparecen: siguen
abriendo en su dirección (`url_path`), fuera del menú, y su destino las enlaza aquí, agrupadas por lo que hace el
estudiante con ellas. Cada descripción solo dice qué hace la página; ninguna hace una afirmación clínica.

- `render_patient_hub`: el paciente activo, el gemelo, medir con cualquier instrumento, su historia y comparar,
  conectar un equipo real y el taller 3D.
- `render_library_hub`: toda la teoría firmada y sus fuentes.
- `render_practice_library`: la práctica libre de la Ruta.
- `render_settings_links`: los textos legales, debajo de Ajustes.
- `render_continue_card`: «Continúa en: …» del Hoy, leído del avance de la Ruta en esta sesión.
"""

from __future__ import annotations

from typing import Sequence, Tuple

import streamlit as st

# (url_path, descripción). La descripción dice qué se hace en la página; el título es el de la página.
Card = Tuple[str, str]

PATIENT_GROUPS: Sequence[Tuple[str, Sequence[Card]]] = (
    ("El gemelo", (
        ("gemelo", "El cuerpo completo de tu paciente: cada órgano con sus valores y su procedencia."),
    )),
    ("Medir con un instrumento", (
        ("ecg", "Trazo en papel ECG, frecuencia cardiaca y las 12 derivaciones."),
        ("respiratorio", "Patrones respiratorios, apneas y la SpO₂ del modelo."),
        ("eeg", "Bandas del EEG y sus cocientes, con su cita."),
        ("emg", "Señal muscular de superficie: activación y RMS."),
        ("hrv", "Variabilidad cardiaca: dominio temporal, espectro y RSA."),
        ("multisensor", "El pulso por luz y la temperatura en vivo, con sus tutoriales."),
        ("calculadoras", "Calculadoras clínicas con su fuente, con los signos de tu paciente."),
    )),
    ("Historia y comparación", (
        ("pacientes", "Los pacientes guardados y sus estados en el tiempo."),
        ("comparar", "Hasta tres estados guardados lado a lado, cada valor con su procedencia."),
    )),
    ("Conectar un equipo real", (
        ("ecg", "Pestaña «Placa en vivo (tutorial)»: la placa ECG con ESP32."),
        ("eeg", "Pestaña «EEG en vivo (tutorial)»: OpenBCI, Muse, Unicorn o LSL."),
        ("emg", "Vista «Sensor en vivo (tutorial)»: MyoWare con ESP32."),
        ("multisensor", "Vista «Sensores en vivo»: pulso por luz y temperatura."),
    )),
    ("Modelos en 3D", (
        ("modelo-3d", "Crea un modelo 3D a partir de imágenes de TC o RM."),
    )),
)

LIBRARY_GROUPS: Sequence[Tuple[str, Sequence[Card]]] = (
    ("Teoría firmada", (
        ("temas", "Cada tema en fichas: explicación, teoría, hallazgos y un quiz."),
        ("teoria", "Teoría en capas del ECG, la frecuencia cardiaca y NEWS2."),
        ("referencias", "La teoría de Respiración, EEG, EMG y variabilidad cardiaca."),
        ("ecg-3d", "El vectocardiograma: el ECG como un vector en el espacio."),
    )),
    ("Fuentes y preguntas", (
        ("bibliografia", "Todas las referencias, con su clave y su enlace."),
        ("pregunta", "Pregunta y la IA responde solo con la base de conocimiento firmada, citando cada afirmación."),
    )),
)

PRACTICE_GROUPS: Sequence[Tuple[str, Sequence[Card]]] = (
    ("Preguntas", (
        ("quiz", "Preguntas con fuente de todos los bancos, con práctica adaptativa."),
        ("cuestionarios", "Los cuestionarios de Respiración y EEG."),
        ("desafio-ecg", "Lee un ECG de 12 derivaciones."),
    )),
    ("Casos", (
        ("caso-guiado", "Un caso de ECG paso a paso: hipótesis, pruebas y límites."),
        ("caso-ciego", "Un caso sin diagnóstico a la vista, corregido con la evidencia."),
        ("casos-simulador", "Un escenario del simulador para interpretar, corregido con su evidencia."),
        ("detective", "Pide pistas y propone un diagnóstico."),
        ("what-if", "Predice qué pasa con la presión al cambiar la frecuencia cardiaca."),
    )),
    ("Tu sesión", (
        ("mi-sesion", "Aciertos por concepto y qué tan calibrada está tu confianza en esta sesión."),
    )),
)

SETTINGS_LINKS: Sequence[Card] = (
    ("terminos", "Términos y condiciones de uso."),
    ("privacidad", "Qué se guarda y dónde."),
)


def _card(url: str, description: str) -> None:
    from app.utils import navigation as nav
    from app.utils.design_system import ICONS_URL, NAV_ICONS

    page = nav.page(url)
    title = page.title if page is not None else url
    with st.container(border=True):
        icon = NAV_ICONS.get(url)
        if icon:
            st.markdown(f"<img class='bc-hub-icon' src='{ICONS_URL}/{icon}' alt=''>", unsafe_allow_html=True)
        nav.link(url, title)
        st.caption(description)


def render_groups(groups: Sequence[Tuple[str, Sequence[Card]]], key: str) -> None:
    for heading, cards in groups:
        st.markdown(f"#### {heading}")
        cols = st.columns(3)
        for i, (url, description) in enumerate(cards):
            with cols[i % 3]:
                _card(url, description)


def render_patient_hub() -> None:
    from app.utils.patient_banner import render_active_patient_banner

    st.markdown("<span class='bc-eyebrow'>Paciente</span><div class='bc-hero'>Tu paciente</div>",
                unsafe_allow_html=True)
    render_active_patient_banner()
    st.caption("Todo lo de aquí es del mismo paciente. Los instrumentos que tienen «Guardar al gemelo» escriben en él lo "
               "que mides cuando lo guardas, con su procedencia, y lo ven el gemelo y la Ruta; los demás solo leen.")
    render_groups(PATIENT_GROUPS, "paciente")


def render_library_hub() -> None:
    st.markdown("<span class='bc-eyebrow'>Biblioteca</span><div class='bc-hero'>Teoría y fuentes</div>",
                unsafe_allow_html=True)
    st.caption("Teoría con su fuente: los temas firmados y el texto citado de los laboratorios, enlazados a la "
               "Bibliografía.")
    render_groups(LIBRARY_GROUPS, "biblioteca")


def render_practice_library() -> None:
    st.caption("Practica por tu cuenta, fuera de las unidades.")
    render_groups(PRACTICE_GROUPS, "practica")


def render_settings_links() -> None:
    st.markdown("### Textos legales")
    render_groups((("", SETTINGS_LINKS),), "ajustes")


def continue_target() -> Tuple[str, str]:
    """(etiqueta, clave de la unidad) del «Continúa en» del Hoy: la unidad abierta por última vez en la Ruta y su
    estación, o la primera unidad si todavía no se abrió ninguna. Solo lee `st.session_state` (se pierde al cerrar)."""
    from app.supermodules.ruta import units
    from app.supermodules.ruta.model import KIND_LABELS, PROGRESS_KEY
    from app.supermodules.ruta.page import OPEN_UNIT_KEY
    from app.utils.i18n import t

    progress = st.session_state.get(PROGRESS_KEY) or {}
    unit_key = st.session_state.get(OPEN_UNIT_KEY)
    if unit_key not in progress:
        return f"{t('Empezar la Ruta')}: {units.UNITS[0].title}", units.UNITS[0].key
    unit = units.UNIT_BY_KEY[unit_key]
    index = progress[unit_key].get("station", 0)
    station = unit.stations[index]
    # Los nombres de la unidad y de la estación son contenido de la Ruta (en español); el marco se traduce.
    return (f"{t('Continúa en')}: {unit.title} · {t('estación')} {index} ({t(KIND_LABELS[station.kind])}: "
            f"{station.title})", unit_key)


def _open_unit(unit_key: str) -> None:
    from app.supermodules.ruta.page import OPEN_UNIT_KEY

    st.session_state[OPEN_UNIT_KEY] = unit_key
    st.session_state["ruta_open_mode"] = "unidades"
    st.session_state.pop("ruta_unit", None)
    st.session_state.pop("ruta_mode", None)


def render_continue_card() -> None:
    """Revisión final de la T5: un botón (no un enlace) que abre la Ruta en la unidad y el modo de la tarjeta."""
    from app.utils import navigation as nav
    from app.utils.i18n import t

    label, unit_key = continue_target()
    with st.container(border=True, key="bc_continue_card"):
        st.markdown(f"<span class='bc-eyebrow'>{t('Ruta')}</span>", unsafe_allow_html=True)
        if st.button(label, key="bc_continue", on_click=_open_unit, args=(unit_key,)):
            target = nav.page("ruta")
            if target is not None:
                st.switch_page(target)
