"""
Fase 3 (paciente único de sesión, 2026-08-30) — punto único de verdad para
"quién es el paciente activo de esta sesión de navegador".

Antes de esta tanda, 4 sitios distintos (`twin_shell/pages.py::init_session()`,
y los botones "Guardar estado al gemelo" de ECG Lab/HRV/Respiratory, en
`main.py`/`respiratory_lab/pages.py`) copiaban el mismo bloque de 8-9 líneas:
comprobar si `st.session_state["twin_shell_ups_patient_id"]` existe y, si
no, crearlo. Funcionaba porque los 4 copiaban el mismo nombre de clave -- una
convención frágil, no una autoridad real. Este módulo ES esa autoridad:
`get_active_patient_id()` reemplaza los 4 sitios, que ahora la llaman en vez
de decidir por su cuenta.

Mismo principio que la Fase 5 replicará para el estado persistido en
general: un punto único de verdad en vez de una clave copiada.

Deliberadamente NO exportado por `app/utils/__init__.py` -- se importa
explícito (`from app.utils.patient_session import ...`), mismo patrón que
`app/utils/design_system.py`.
"""

from __future__ import annotations

import streamlit as st

from domain.physiology.state import create_patient, init_db, make_engine, make_session_factory, rename_patient

# Mismos nombres de clave que ya usaba el bootstrap original -- no se
# renombran (evita romper cualquier lectura directa que sobreviva en algún
# rincón no migrado); lo que cambia es que a partir de ahora hay un único
# lugar que decide cuándo crearlas, no 4.
_SESSION_FACTORY_KEY = "twin_shell_ups_session_factory"
_PATIENT_ID_KEY = "twin_shell_ups_patient_id"
_DISPLAY_NAME_KEY = "twin_shell_ups_patient_display_name"

DEFAULT_PATIENT_DISPLAY_NAME = "Paciente Demo (Twin Shell)"


def get_active_session_factory():
    """Sessionmaker del UPS compartido por toda la sesión de navegador.
    Se crea una única vez (idempotente, igual que `get_active_patient_id()`
    de abajo) y la reutilizan tanto esta función como cualquier módulo que
    necesite abrir su propia sesión sobre el paciente activo."""
    if _SESSION_FACTORY_KEY not in st.session_state:
        engine = make_engine()
        init_db(engine)
        st.session_state[_SESSION_FACTORY_KEY] = make_session_factory(engine)
    return st.session_state[_SESSION_FACTORY_KEY]


def get_active_patient_id() -> str:
    """El `patient_id` del paciente único de esta sesión de navegador --
    ÚNICA fuente de verdad. Lo crea la primera vez que se llama, sin
    importar qué módulo llame primero (Twin OS, ECG Lab, HRV, Respiratory o
    Patient Pipeline) -- idempotente vía el guard de `session_state`, igual
    que el bootstrap original, pero centralizado en un solo sitio en vez de
    copiado en 4. Ningún módulo debe volver a comprobar/crear
    `twin_shell_ups_patient_id` por su cuenta; todos llaman aquí."""
    if _PATIENT_ID_KEY not in st.session_state:
        session_factory = get_active_session_factory()
        with session_factory() as session:
            st.session_state[_PATIENT_ID_KEY] = create_patient(
                session, display_name=st.session_state.get(_DISPLAY_NAME_KEY, DEFAULT_PATIENT_DISPLAY_NAME)
            )
    return st.session_state[_PATIENT_ID_KEY]


def set_active_patient_id(patient_id: str) -> None:
    """Sobrescribe el paciente activo de la sesión -- uso deliberado y
    excepcional, no para "cambiar de paciente" (esa capacidad queda fuera
    de alcance de la Fase 3, ver CHANGELOG.md). El único llamador legítimo
    hoy es el modo "Basal" del simulador de escenarios de Twin OS
    (`render_ups_scenario_simulator()`), que sustituye TEMPORALMENTE al
    paciente activo por uno efímero (`create_ephemeral_basal_patient()`) y
    guarda el `patient_id` continuo aparte (`twin_shell_ups_canonical_
    patient_id`) para poder restaurarlo con su propio botón "Volver al
    paciente continuo" -- ese mecanismo de ida y vuelta no se tocó, solo
    pasa a escribir a través de esta función en vez de a
    `st.session_state["twin_shell_ups_patient_id"]` directo."""
    st.session_state[_PATIENT_ID_KEY] = patient_id


def get_active_patient_display_name() -> str:
    """Nombre cosmético del paciente único de la sesión. Editable (ver
    `rename_active_patient()`) -- NUNCA es un mecanismo de cambio de
    paciente. Reemplaza al vestigio de Patient Pipeline: antes, escribir
    una etiqueta nueva creaba un paciente NUEVO (continuidad perdida en
    silencio); ahora solo renombra al mismo paciente único."""
    return st.session_state.get(_DISPLAY_NAME_KEY, DEFAULT_PATIENT_DISPLAY_NAME)


def rename_active_patient(display_name: str) -> None:
    """Renombra al paciente único activo -- cosmético: actualiza
    `PatientRecord.display_name` en el UPS (vía `rename_patient()`,
    `domain/physiology/state/repository.py`) y el nombre en caché de esta
    sesión. NO crea un paciente nuevo, NO cambia `patient_id`. Si el
    paciente activo todavía no existe (nadie llamó `get_active_patient_id()`
    todavía), solo cachea el nombre para cuando se cree."""
    st.session_state[_DISPLAY_NAME_KEY] = display_name
    if _PATIENT_ID_KEY in st.session_state:
        session_factory = get_active_session_factory()
        with session_factory() as session:
            rename_patient(session, st.session_state[_PATIENT_ID_KEY], display_name)
