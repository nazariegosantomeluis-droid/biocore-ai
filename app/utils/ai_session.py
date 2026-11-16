"""Clave de IA por sesión de navegador (2026-10-25; desde la tanda 1 de la fase 1, 2026-11-15, en la página
Ajustes y no como primera pantalla).

La persona puede pegar su API key de Anthropic en Ajustes y usarla solo durante esa sesión. Reglas:

- La clave vive SOLO en `st.session_state` (memoria de esa sesión en el
  servidor): nunca se escribe en disco ni en `os.environ`. `os.environ` es del
  proceso entero, así que poner ahí la clave de una persona la compartiría con
  todas las demás pestañas y usuarios.
- Cada llamada de IA recibe un cliente creado con la clave de SU sesión
  (`ai_client()`); sin clave de sesión se usa la del entorno del servidor
  (`ANTHROPIC_API_KEY`, como siempre) o el narrador declara que está apagado.
- La clave se verifica contra Anthropic antes de aceptarla, para que un pegado
  fallido se note en el momento y no después, dentro de un panel.
"""

from __future__ import annotations

from typing import Optional

import streamlit as st

from domain.physiology.narrator import DEFAULT_MODEL
from domain.physiology.narrator import is_configured as env_key_configured

SESSION_KEY = "biocore_anthropic_api_key"
_INPUT = "biocore_ai_key_input"
_ERROR = "biocore_ai_key_error"
_SAVED = "biocore_ai_key_saved"

AI_KEY_HINT = "Pon tu clave en «Ajustes» (menú lateral), o define `ANTHROPIC_API_KEY`."


def session_api_key() -> Optional[str]:
    return st.session_state.get(SESSION_KEY) or None


def ai_configured() -> bool:
    """Hay IA en esta sesión: clave pegada aquí o clave del entorno del servidor."""
    return bool(session_api_key()) or env_key_configured()


def ai_client():
    """Cliente con la clave de ESTA sesión, o `None` para que el narrador use la
    del entorno (su comportamiento de siempre)."""
    key = session_api_key()
    if not key:
        return None
    import anthropic

    return anthropic.Anthropic(api_key=key)


def validate_api_key(key: str) -> Optional[str]:
    """`None` si la clave sirve para el modelo del narrador; si no, el motivo."""
    import anthropic

    try:
        with anthropic.Anthropic(api_key=key, max_retries=0, timeout=15.0) as client:
            client.models.retrieve(DEFAULT_MODEL)
    except anthropic.AuthenticationError:
        return "Anthropic rechazó la clave: no es válida o fue revocada. Revisa que la copiaste completa."
    except anthropic.PermissionDeniedError:
        return "La clave es válida, pero no tiene permiso para usar el modelo del narrador."
    except anthropic.NotFoundError:
        return f"La clave es válida, pero el modelo {DEFAULT_MODEL} no está disponible para ella."
    except anthropic.APIConnectionError:
        return "No se pudo conectar con Anthropic para verificar la clave. Revisa tu conexión a internet."
    except anthropic.APIStatusError as exc:
        return f"Anthropic respondió con un error ({exc.status_code}) al verificar la clave. Intenta de nuevo."
    return None


# --- Callbacks: corren antes del rerun, cuando sí se puede vaciar el campo ---

def _save_key() -> None:
    key = (st.session_state.get(_INPUT) or "").strip()
    st.session_state[_INPUT] = ""  # la clave no se queda en el widget
    st.session_state.pop(_SAVED, None)
    if not key:
        st.session_state[_ERROR] = "Pega tu clave en el campo antes de guardarla."
        return
    problem = validate_api_key(key)
    if problem:
        st.session_state[_ERROR] = problem
        return
    st.session_state[SESSION_KEY] = key
    st.session_state[_SAVED] = True
    st.session_state.pop(_ERROR, None)


def _forget_key() -> None:
    st.session_state.pop(SESSION_KEY, None)
    st.session_state.pop(_SAVED, None)


def render_settings_link() -> None:
    """Enlace a Ajustes justo donde una función necesita la IA y no hay clave (decisión 2)."""
    from app.utils import navigation as nav

    nav.link("ajustes", "Ir a Ajustes para poner tu clave", icon="⚙️")


def render_settings_page() -> None:
    """Ajustes: la clave de IA (opcional). Antes era un panel previo que tapaba la plataforma (primera pantalla)."""
    from app.utils.design_system import render_module_header

    render_module_header("Ajustes", icon="⚙️")
    st.markdown("### Clave de IA (opcional)")
    st.markdown(
        "Las explicaciones con IA (narrador clínico, pestañas «IA» de los laboratorios, feedback de la "
        "Academia) llaman a la API de Anthropic con **tu** clave. Sin clave, toda la plataforma funciona "
        "igual y esos paneles dicen que la IA está apagada."
    )
    if session_api_key():
        st.success("IA activa con tu clave (solo en esta sesión).")
        st.button("Olvidar mi clave", key="biocore_ai_forget", on_click=_forget_key)
    elif env_key_configured():
        st.info("IA activa con la clave del entorno del servidor (`ANTHROPIC_API_KEY`).")
    else:
        st.info("IA apagada: no hay clave en esta sesión ni en el servidor.")
    st.text_input("Pega tu clave de API de Anthropic", type="password", key=_INPUT, placeholder="sk-ant-...")
    st.button("Guardar mi clave", key="biocore_ai_save", on_click=_save_key, type="primary")
    if st.session_state.get(_ERROR):
        st.error(st.session_state[_ERROR])
    st.caption(
        "Tu clave se verifica con Anthropic y se guarda solo en la memoria de esta sesión del navegador: no "
        "se escribe en disco ni va al repositorio, y se pierde al cerrar o recargar la pestaña. Pégala solo "
        "en una instancia de BIOCORE en la que confíes (la tuya, o una servida por HTTPS)."
    )


def render_sidebar_status() -> None:
    with st.sidebar:
        if session_api_key():
            st.caption("🔑 IA activa con tu clave (solo en esta sesión)")
        elif env_key_configured():
            st.caption("🔑 IA activa (clave del entorno del servidor)")
        else:
            st.caption("🔑 IA apagada")
            render_settings_link()
