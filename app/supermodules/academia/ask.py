"""«Pregunta a BIOCORE»: el estudiante pregunta y la IA responde SOLO con la teoría firmada (2026-11-17, Art. I).

La lógica vive en `educational/citation_tutor.py`; aquí solo está la pantalla:
- Los fragmentos firmados que responden a la pregunta se muestran SIEMPRE, con o sin IA: sin clave, el estudiante
  igual lee la teoría con su fuente.
- Con IA, la explicación llega en streaming y después se revisan sus citas: una clave que el modelo no recibió, o una
  respuesta sin ninguna cita, se avisa en pantalla.
- Sin fragmentos firmados se dice «no disponible» y no se llama al modelo.

Privacidad (2026-11-17, decisión de Luis):
- P1. La pregunta y la respuesta NO se guardan en ninguna base ni registro: viven solo en la sesión del navegador
  (`st.session_state`) y no pasan por `app/utils/learning_log.py` ni por `educational/learning_analytics.py`. La base
  de conocimiento solo se LEE.
- P2. Sobre el campo, el aviso `PRIVACY_NOTICE`.
- P3. El nivel gratuito de Gemini nunca recibe la pregunta (`ProviderNotAllowedError`); sin IA se muestran solo los
  fragmentos firmados.
"""
from __future__ import annotations

import streamlit as st

from app.utils.ai_session import (
    AI_CALL_FAILED, AI_KEY_HINT, AI_OFF, ai_client, ai_configured, render_settings_link,
)
from app.utils.design_system import render_error_state
from educational import citation_tutor as tutor
from educational import knowledge_base as kb

QUESTION_KEY = "ask_biocore_question"
INTRO = ("Pregunta sobre la teoría de BIOCORE. La respuesta sale solo de los temas firmados, cada afirmación con su "
         "fuente; si la teoría firmada no lo cubre, BIOCORE te lo dice en lugar de inventarlo.")
FREE_TIER_NOTE = ("Con el nivel gratuito de Gemini, BIOCORE no envía preguntas escritas por personas: sus términos piden "
                  "no mandar información personal, y BIOCORE no puede revisar qué contiene tu pregunta. Usa una clave "
                  "de Anthropic en «Ajustes», o lee abajo los fragmentos firmados que responden a tu pregunta.")
PRIVACY_NOTICE = ("No escribas datos personales ni de pacientes: tu pregunta se envía al proveedor de IA configurado para "
                  "responderla.")
NO_AI_NOTE ="Sin IA en esta sesión: abajo tienes los fragmentos firmados que responden a tu pregunta."
SOURCES_TITLE = "Fragmentos firmados que usó la respuesta"
CAPA_LABEL = {"idea": "Idea", "mecanismo": "Mecanismo", "detalle": "Detalle", "sin_fuente": "Sin fuente verificada"}


def render_fragments(prep: tutor.Preparacion, expanded: bool) -> None:
    with st.expander(SOURCES_TITLE, expanded=expanded):
        for f in prep.fragmentos:
            tema = f"{f['tema_titulo']} ({f['subtema']})" if f["subtema"] else f["tema_titulo"]
            claves = " ".join(f"[{c}]" for c in f["claves"])
            st.markdown(f"**{tema}** · {CAPA_LABEL.get(f['capa'], f['capa'])} {claves}")
            st.markdown(f["texto"])
        if prep.referencias:
            st.markdown("**Referencias**")
            for clave, texto in prep.referencias.items():
                st.markdown(f"- **[{clave}]** {texto}")


def render_ask_biocore() -> None:
    from domain.physiology.narrator import GeminiError, NarratorNotConfiguredError, ProviderNotAllowedError

    st.caption(INTRO)
    st.warning(PRIVACY_NOTICE)                      # P2: visible sobre el campo, antes de escribir
    pregunta = st.text_area("Tu pregunta", key=QUESTION_KEY, placeholder="Por ejemplo: ¿por qué se filtra el EMG a 20 Hz?")
    if not st.button("Preguntar", key="ask_biocore_submit", disabled=not (pregunta or "").strip()):
        return

    prep = tutor.preparar(pregunta)
    if not prep.hay_respuesta:
        st.info(kb.NO_DISPONIBLE)
        return

    if not ai_configured():
        st.info(NO_AI_NOTE)
        st.caption(AI_OFF + " " + AI_KEY_HINT)
        render_settings_link()
        render_fragments(prep, expanded=True)
        return

    try:
        respuesta = st.write_stream(tutor.responder(prep, client=ai_client()))
    except ProviderNotAllowedError:
        st.warning(FREE_TIER_NOTE)
        render_settings_link()
        render_fragments(prep, expanded=True)
        return
    except NarratorNotConfiguredError as exc:
        render_error_state(str(exc))
        return
    except GeminiError as exc:
        render_error_state(str(exc), exception=exc)
        return
    except Exception as exc:  # llamada real a la API: puede fallar por red o cuota
        render_error_state(AI_CALL_FAILED, exception=exc)
        return

    for aviso in tutor.verificar_citas(respuesta if isinstance(respuesta, str) else "", prep).avisos:
        st.warning(aviso)
    render_fragments(prep, expanded=False)
