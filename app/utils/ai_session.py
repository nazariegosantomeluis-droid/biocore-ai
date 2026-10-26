"""Clave de IA por sesión de navegador (2026-10-25).

La persona puede pegar su API key de Anthropic en un panel de entrada y usarla
solo durante esa sesión. Reglas:

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
ENTRY_DONE = "biocore_ai_entry_done"
_INPUT = "biocore_ai_key_input"
_ERROR = "biocore_ai_key_error"

AI_KEY_HINT = "Pega tu clave con «🔑 Poner mi clave» en la barra lateral, o define `ANTHROPIC_API_KEY`."


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

def _enter_with_key() -> None:
    key = (st.session_state.get(_INPUT) or "").strip()
    st.session_state[_INPUT] = ""  # la clave no se queda en el widget
    if not key:
        st.session_state[_ERROR] = "Pega tu clave en el campo antes de entrar."
        return
    problem = validate_api_key(key)
    if problem:
        st.session_state[_ERROR] = problem
        return
    st.session_state[SESSION_KEY] = key
    st.session_state[ENTRY_DONE] = True
    st.session_state.pop(_ERROR, None)


def _enter_without_ai() -> None:
    st.session_state[ENTRY_DONE] = True
    st.session_state[_INPUT] = ""
    st.session_state.pop(_ERROR, None)


def _forget_key() -> None:
    st.session_state.pop(SESSION_KEY, None)


def _reopen_entry() -> None:
    st.session_state[ENTRY_DONE] = False


def render_entry_gate() -> bool:
    """Panel previo a la plataforma. Devuelve `True` si ya se puede entrar.
    Si el servidor ya tiene `ANTHROPIC_API_KEY`, no se muestra."""
    if st.session_state.get(ENTRY_DONE) or (env_key_configured() and ENTRY_DONE not in st.session_state):
        return True
    st.markdown("## 🔑 BIOCORE AI — clave de IA (opcional)")
    st.markdown(
        "Las explicaciones con IA (narrador clínico, pestañas «IA» de los laboratorios, feedback de la "
        "Academia) llaman a la API de Anthropic con **tu** clave. Sin clave, toda la plataforma funciona "
        "igual y esos paneles dicen que la IA está apagada."
    )
    st.text_input("Pega tu API key de Anthropic", type="password", key=_INPUT, placeholder="sk-ant-...")
    c1, c2 = st.columns(2)
    c1.button("Entrar con mi clave", type="primary", on_click=_enter_with_key, width="stretch")
    c2.button("Entrar sin IA", on_click=_enter_without_ai, width="stretch")
    if st.session_state.get(_ERROR):
        st.error(st.session_state[_ERROR])
    st.caption(
        "Tu clave se verifica con Anthropic y se guarda solo en la memoria de esta sesión del navegador: no "
        "se escribe en disco ni va al repositorio, y se pierde al cerrar o recargar la pestaña. Pégala solo "
        "en una instancia de BIOCORE en la que confíes (la tuya, o una servida por HTTPS)."
    )
    return False


def render_sidebar_status() -> None:
    if session_api_key():
        st.sidebar.caption("🔑 IA activa con tu clave (solo en esta sesión)")
        st.sidebar.button("Olvidar mi clave", key="biocore_ai_forget", on_click=_forget_key)
    elif env_key_configured():
        st.sidebar.caption("🔑 IA activa (clave del entorno del servidor)")
    else:
        st.sidebar.caption("🔑 IA apagada")
        st.sidebar.button("Poner mi clave", key="biocore_ai_reopen", on_click=_reopen_entry)
