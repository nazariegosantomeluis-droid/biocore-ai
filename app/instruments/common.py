"""Auxiliares que comparten los instrumentos y las páginas de los laboratorios (T2, 2026-11-18).

Se movieron tal cual desde `app/main.py`, que los sigue exponiendo con el mismo nombre."""

from typing import Any, List, Tuple

import streamlit as st

from app.instruments.base import PAGE, InstrumentContext
from app.utils.ai_session import AI_CALL_FAILED, AI_KEY_HINT, AI_OFF, ai_client, ai_configured, render_settings_link
from app.utils.design_system import render_error_state

# Un CSV cargado no escribe al gemelo (EMG y ECG, contención del 2026-11-16, Art. I). T2: vive aquí porque lo usan la
# página del EMG y el instrumento del trazo del ECG; `app.main` lo sigue exponiendo.
CSV_SAVE_BLOCKER = "archivo sin procedencia verificable (un CSV cargado no dice de quién ni de qué equipo viene)"


def render_metric_explained(title: str, value: Any, unit: str = '', topic=None) -> None:
    """El número y, a demanda, «¿Qué significa…?» con las capas de un tema FIRMADO y su fuente.

    Pulido profesional (2026-11-16, Art. I): la explicación ya no se escribe a mano en cada llamada. Antes cada llamador
    pasaba sus propias capas («¿Por qué importa?», «¿Qué la afecta?»...), sin fuente; en la frecuencia cardiaca eran
    genéricas. Ahora una capa solo existe si viene de un `TheoryTopic` de `learn_theory.py` (texto de
    `docs/contenido/teoria_citada.md`, firmado por Luis, con su clave de cita). Sin tema, no hay expander."""
    from app.utils.design_system import render_theory_topic

    try:
        display_value = f"{value} {unit}" if unit else f"{value}"
    except Exception:
        display_value = str(value)

    st.markdown(f"**{title}** — {display_value}")
    if topic is not None:
        with st.expander(f"¿Qué significa {title}?", expanded=False):
            render_theory_topic(topic, inside_expander=True)


def render_findings_narrator(lab_name: str, findings: List[Tuple[str, str, str]], origin=None,
                             ctx: InstrumentContext = PAGE) -> None:
    """Narrador clínico real (Anthropic o Gemini, streaming) para hallazgos calculados en
    laboratorios que no persisten en el UPS (EMG/HRV/Multisensor/ECG Monitor no
    tienen dominio en el Unified Physiological State — solo cardiovascular y
    respiratorio están modelados). Ver domain/physiology/narrator/findings.py.

    Mismo patrón que el narrador del Digital Twin OS (twin_shell/pages.py):
    llamada real a la API, sin narración simulada de respaldo, cada afirmación
    anclada a una métrica exacta del contexto — pero sin comparación temporal
    (estas señales ad-hoc no tienen historial persistido).

    `findings`: lista de tuplas (nombre_metrica, valor, significado). `origin`
    (2026-11-16): de dónde vienen los datos (`DataOrigin`); sin declarar es
    DESCONOCIDO, y el nivel gratuito de Gemini no lo recibe. `ctx` (T2): el contexto del instrumento; con `PAGE`,
    la clave del botón es la de siempre."""
    from domain.physiology.narrator import (
        DataOrigin,
        Finding,
        FindingsContext,
        GeminiError,
        NarratorNotConfiguredError,
        ProviderNotAllowedError,
        stream_findings_narration,
    )

    if not ai_configured():
        st.warning(
            AI_OFF + " Este narrador llama a un modelo de lenguaje real con streaming — no existe una "
            "narración simulada de respaldo. " + AI_KEY_HINT
        )
        render_settings_link()
        return

    st.caption("Interpreta las métricas ya calculadas arriba — no genera datos nuevos.")
    if st.button("🗣️ Explicar estos hallazgos", key=ctx.k(f"findings_narrator_{lab_name}")):
        context = FindingsContext(lab_name=lab_name, findings=[Finding(*f) for f in findings],
                                  origin=origin or DataOrigin.DESCONOCIDO)
        try:
            st.write_stream(stream_findings_narration(context, client=ai_client()))
        except ProviderNotAllowedError as exc:
            st.warning(str(exc))
        except NarratorNotConfiguredError as exc:
            render_error_state(str(exc))
        except GeminiError as exc:
            render_error_state(str(exc), exception=exc)
        except Exception as exc:  # llamada real a la API — puede fallar por red/cuota/etc.
            # Fase 2.3 Tanda 3 (2026-08-29): compartido por EMG/ECG Monitor/
            # Multisensor/HRV (pestaña "IA") -- una sola migración cubre los
            # 4. Antes exponía `{exc}` crudo (puede incluir detalle interno
            # de la respuesta HTTP de la API).
            render_error_state(AI_CALL_FAILED, exception=exc)
