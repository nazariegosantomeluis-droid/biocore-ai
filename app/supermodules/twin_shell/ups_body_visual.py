"""
Fase 1.4 — Digital Twin visual sincronizado con el UPS (cierre de Fase 1).

Un cuerpo SVG (2D, sin Three.js/WebGL) donde el corazón, los pulmones y el
cerebro — los tres dominios que el UPS modela
(`domain/physiology/state/schema.py`: cardiovascular, respiratorio,
neurológico) — cambian de color y animación según el
`UnifiedPhysiologicalState` actual.

Capa 5A, Sub-fase 2 (2026-08-31, presentacional): el cerebro
(`_render_brain_card()`) se suma como tercer órgano. Reacciona al dominio
neurológico que la Sub-fase 1 añadió al UPS, con la MISMA mecánica que
corazón/pulmones — mismo `state`, misma paleta (`SEVERITY_COLOR`/
`NEUTRAL_COLOR`/`STABLE_COLOR`), mismo trato del dominio vacío (gris "sin
dato", nunca un color que finja una medición). Cero lógica de datos nueva:
el band power/estado ya persiste y ya es honesto, esto sólo lo hace visible
en la representación principal.

Regla de diseño (decidida, no negociable): el resaltado lo decide un
`UnifiedPhysiologicalState` estructurado — severidad de eventos por dominio
(`EventSeverity`) y descriptores (`heart_rate`, `respiratory_rate`, `spo2`,
band power EEG / `mental_workload`) — nunca el texto del narrador
(`narrator/`). Este módulo y el narrador son dos lectores independientes de
la misma verdad fisiológica; ninguno lee al otro. `render_ups_body()`
recibe siempre un `UnifiedPhysiologicalState` ya construido, nunca el
organismo crudo ni una cadena de texto generada por IA.

Fase 5.1 (2026-08-30): ese `UnifiedPhysiologicalState` puede venir de dos
caminos, ambos igualmente honestos — el último snapshot PERSISTIDO
(`get_latest_state`, para el modo caso clínico de Academia/Twin OS y cada
paso de un escenario, donde "lo que se guardó" es exactamente lo que debe
mostrarse) o el estado ACTUAL en memoria sin persistir (`get_current_
physiological_state`, para el Cuerpo Digital sincronizado de Twin OS, que
ahora refleja el organismo al instante en vez de esperar a que algo lo
guarde). Ver `app/utils/physiological_state.py` para el porqué.

Si un dominio no tiene un descriptor clave (`heart_rate`/`respiratory_rate`,
o el dominio neurológico completamente vacío por el gate anti-órgano-fantasma
de la Sub-fase 1) todavía, el órgano se muestra en gris neutro — no se
inventa una animación a partir de un valor que no existe (mismo principio
que `before_value=None` en el narrador).
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import streamlit as st

from domain.physiology.state import (
    EventSeverity,
    EventType,
    PhysiologicalEvent,
    UnifiedPhysiologicalState,
)

# Sub-fase 1 (2026-08-30) escribió estos 5 band power al dominio neurológico
# — mismos nombres que `builder._neurological_state()`. El cerebro elige su
# banda dominante entre las que estén presentes, igual que EegAnalyzer.
_BRAIN_BAND_DESCRIPTORS = ("delta_power", "theta_power", "alpha_power", "beta_power", "gamma_power")

# Único lugar donde severidad -> color se decide, reutilizado por ambos órganos.
NEUTRAL_COLOR = "#64748b"   # gris — el dominio no tiene datos todavía (persistidos o actuales)
STABLE_COLOR = "#39d98a"    # verde — datos presentes, sin evento activo en este dominio
SEVERITY_COLOR: Dict[EventSeverity, str] = {
    EventSeverity.INFO: "#39d98a",
    EventSeverity.WARNING: "#ffc542",
    EventSeverity.CRITICAL: "#ff4d4d",
}
_SEVERITY_RANK = {EventSeverity.INFO: 0, EventSeverity.WARNING: 1, EventSeverity.CRITICAL: 2}

# EventType -> (órgano que lo señala, etiqueta corta). Explícito y cerrado,
# igual que el propio EventType — si se añade un EventType nuevo en una fase
# futura, este mapeo debe actualizarse a propósito, no inferirse del dominio.
EVENT_VISUAL_MAP: Dict[EventType, Tuple[str, str]] = {
    EventType.ARRHYTHMIA_RISK_HR_EXTREME: ("heart", "⚡ Arritmia — FC fuera de rango"),
    EventType.LOW_HRV_AUTONOMIC_STRESS: ("heart", "😰 Estrés autonómico (HRV bajo)"),
    EventType.HYPOXIA_SPO2_LOW: ("lungs", "🫁 SpO₂ bajo lo esperado"),
    EventType.HYPOXIA_SPO2_CRITICAL: ("lungs", "🚨 Hipoxia crítica"),
    # Capa 5A, Sub-fase 2: el único EventType neuro (añadido en la Sub-fase 1)
    # señala al cerebro, igual que los 4 de arriba señalan a su órgano.
    EventType.HIGH_STRESS_EEG: ("brain", "🧠 Estrés elevado (EEG)"),
}

_STYLE = """
<style>
@keyframes biocore-heartbeat {
  0%   { transform: scale(1); }
  20%  { transform: scale(1.16); }
  35%  { transform: scale(0.96); }
  50%  { transform: scale(1.10); }
  70%  { transform: scale(1); }
  100% { transform: scale(1); }
}
@keyframes biocore-breathe {
  0%, 100% { transform: scale(1); }
  50%      { transform: scale(1.09); }
}
@keyframes biocore-brainwave {
  0%, 100% { transform: scale(1); opacity: 0.90; }
  50%      { transform: scale(1.045); opacity: 1; }
}
@keyframes biocore-alert-halo {
  0%, 100% { opacity: 0.20; }
  50%      { opacity: 0.85; }
}
.biocore-organ-card {
  text-align: center; padding: 14px 8px; border-radius: 16px;
  background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.10);
}
.biocore-organ-title { font-weight: 700; font-size: 15px; margin-top: 6px; color: #e5e5e5; }
.biocore-organ-metric { font-size: 13px; color: #9fb4c9; margin-top: 2px; }
.biocore-organ-alert {
  margin-top: 6px; font-size: 12px; font-weight: 600; color: #ffb4b4;
  background: rgba(255,77,77,0.12); border-radius: 8px; padding: 3px 8px; display: inline-block;
}
</style>
"""

_HEART_PATH = (
    "M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 "
    "4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 "
    "11.54L12 21.35z"
)

# Silueta de cerebro (contorno mdi-brain, sólo el trazo exterior — mismo
# criterio que `_HEART_PATH`: una figura llena reconocible, sin detalle
# interno). viewBox 0 0 24 24, igual que el corazón.
_BRAIN_PATH = (
    "M12,3C10.73,3 9.6,3.8 9.18,5H9C7.9,5 7,5.9 7,7C7,7.11 7,7.23 7.03,7.34C5.87,7.68 "
    "5,8.74 5,10C5,10.86 5.42,11.65 6.06,12.14C6,12.42 6,12.71 6,13C6,14.66 7.34,16 9,16C9,17.66 "
    "10.34,19 12,19C13.66,19 15,17.66 15,16C16.66,16 18,14.66 18,13C18,12.71 18,12.42 17.94,12.14C18.58,11.65 "
    "19,10.86 19,10C19,8.74 18.13,7.68 16.97,7.34C17,7.23 17,7.11 17,7C17,5.9 16.1,5 15,5H14.82C14.4,3.8 13.27,3 12,3Z"
)


def _severity_for_domain(state: Optional[UnifiedPhysiologicalState], domain: str) -> Optional[EventSeverity]:
    if state is None:
        return None
    domain_events = [e for e in state.events if e.domain == domain]
    if not domain_events:
        return None
    return max((e.severity for e in domain_events), key=lambda s: _SEVERITY_RANK[s])


def _domain_events(state: Optional[UnifiedPhysiologicalState], domain: str) -> List[PhysiologicalEvent]:
    if state is None:
        return []
    return [e for e in state.events if e.domain == domain]


def _event_labels_for_organ(events: List[PhysiologicalEvent], organ_id: str) -> List[str]:
    labels = []
    for e in events:
        organ, label = EVENT_VISUAL_MAP.get(e.event_type, (None, e.event_type.value))
        if organ == organ_id:
            labels.append(label)
    return labels


def _render_heart_card(state: Optional[UnifiedPhysiologicalState]) -> str:
    hr = state.all_domains()["cardiovascular"].get("heart_rate") if state else None
    severity = _severity_for_domain(state, "cardiovascular")
    events = _domain_events(state, "cardiovascular")

    if hr is None:
        color = NEUTRAL_COLOR
        animation_css = ""
        # Fase 5.1: sin "en el UPS" -- `state` puede venir de get_latest_state()
        # (persistido) o get_current_physiological_state() (actual, sin
        # persistir); "sin dato" es honesto para ambos, igual que ya hacían
        # rr_label/spo2_label en _render_lungs_card() más abajo.
        metric_label = "FC: sin dato"
    else:
        color = STABLE_COLOR if severity is None else SEVERITY_COLOR[severity]
        # Un ciclo cardíaco por latido — taquicardia se ve/pulsa más rápido que bradicardia,
        # la animación transmite el dato en vez de ser decorativa.
        beat_duration = max(0.35, min(2.2, 60.0 / max(hr.value, 1.0)))
        animation_css = f"animation: biocore-heartbeat {beat_duration:.2f}s ease-in-out infinite; transform-origin: center;"
        metric_label = f"FC: {hr.value:.0f} bpm"

    halo = ""
    if severity in (EventSeverity.WARNING, EventSeverity.CRITICAL):
        halo_speed = 0.55 if severity == EventSeverity.CRITICAL else 1.3
        halo = (
            f'<circle cx="12" cy="11" r="11.5" fill="none" stroke="{color}" stroke-width="1.2" '
            f'style="animation: biocore-alert-halo {halo_speed}s ease-in-out infinite;"/>'
        )

    alerts_html = "".join(
        f'<div class="biocore-organ-alert">{lbl}</div>' for lbl in _event_labels_for_organ(events, "heart")
    )

    # Bug 1 (2026-07-13): con indentación de 4+ espacios al inicio de cada línea,
    # Markdown (CommonMark) interpreta el bloque como un "indented code block" —
    # texto preformateado literal — ANTES de que unsafe_allow_html=True tenga
    # oportunidad de dejar pasar el HTML. El bloque debe quedar sin sangría
    # (flush-left) para que se renderice como HTML/SVG real, no como texto.
    return (
        '<div class="biocore-organ-card">'
        f'<svg viewBox="0 0 24 24" width="110" height="110" style="overflow: visible;">'
        f'{halo}'
        f'<path d="{_HEART_PATH}" fill="{color}" style="{animation_css}"/>'
        '</svg>'
        '<div class="biocore-organ-title">🫀 Corazón</div>'
        f'<div class="biocore-organ-metric">{metric_label}</div>'
        f'{alerts_html}'
        '</div>'
    )


def _render_lungs_card(state: Optional[UnifiedPhysiologicalState]) -> str:
    rr = state.all_domains()["respiratory"].get("respiratory_rate") if state else None
    spo2 = state.all_domains()["respiratory"].get("spo2") if state else None
    severity = _severity_for_domain(state, "respiratory")
    events = _domain_events(state, "respiratory")

    if rr is None and spo2 is None:
        color = NEUTRAL_COLOR
        animation_css = ""
    else:
        color = STABLE_COLOR if severity is None else SEVERITY_COLOR[severity]
        if rr is not None:
            # Un ciclo respiratorio (inhalar/exhalar) por respiración.
            breath_duration = max(0.8, min(4.0, 60.0 / max(rr.value, 1.0)))
            animation_css = f"animation: biocore-breathe {breath_duration:.2f}s ease-in-out infinite; transform-origin: center;"
        else:
            animation_css = ""

    rr_label = f"{rr.value:.0f} resp/min" if rr is not None else "sin dato"
    spo2_label = f"{spo2.value:.0f}%" if spo2 is not None else "sin dato"

    halo = ""
    if severity in (EventSeverity.WARNING, EventSeverity.CRITICAL):
        halo_speed = 0.55 if severity == EventSeverity.CRITICAL else 1.3
        halo = (
            f'<ellipse cx="100" cy="115" rx="78" ry="75" fill="none" stroke="{color}" stroke-width="4" '
            f'style="animation: biocore-alert-halo {halo_speed}s ease-in-out infinite;"/>'
        )

    alerts_html = "".join(
        f'<div class="biocore-organ-alert">{lbl}</div>' for lbl in _event_labels_for_organ(events, "lungs")
    )

    # Bug 1 (2026-07-13): mismo motivo que en _render_heart_card — sin sangría,
    # para que no se interprete como bloque de código de Markdown.
    return (
        '<div class="biocore-organ-card">'
        '<svg viewBox="0 0 200 220" width="110" height="121" style="overflow: visible;">'
        f'{halo}'
        f'<g style="{animation_css}">'
        f'<rect x="94" y="10" width="12" height="45" rx="5" fill="{color}" opacity="0.85"/>'
        f'<path d="M100,52 L60,78" stroke="{color}" stroke-width="8" fill="none" stroke-linecap="round"/>'
        f'<path d="M100,52 L140,78" stroke="{color}" stroke-width="8" fill="none" stroke-linecap="round"/>'
        f'<path d="M100,70 C68,70 34,92 28,138 C23,178 52,200 84,188 C97,183 100,162 100,140 Z" fill="{color}"/>'
        f'<path d="M100,70 C132,70 166,92 172,138 C177,178 148,200 116,188 C103,183 100,162 100,140 Z" fill="{color}"/>'
        '</g>'
        '</svg>'
        '<div class="biocore-organ-title">🫁 Pulmones</div>'
        f'<div class="biocore-organ-metric">RR: {rr_label} · SpO₂: {spo2_label}</div>'
        f'{alerts_html}'
        '</div>'
    )


def _render_brain_card(state: Optional[UnifiedPhysiologicalState]) -> str:
    """Capa 5A, Sub-fase 2 (presentacional): tercer órgano, mismo patrón
    EXACTO que `_render_heart_card()`/`_render_lungs_card()`.

    - Lee del MISMO `state` que corazón/pulmones (`all_domains()
      ["neurological"]`) — coherencia con Fase 5.1: un único punto de
      verdad, sin desincronización posible por añadir un órgano.
    - Color: `NEUTRAL_COLOR` si el dominio neuro está vacío (gate
      anti-órgano-fantasma de la Sub-fase 1 activo — escritor no-neuro);
      `STABLE_COLOR` si hay datos y ningún evento neuro; `SEVERITY_COLOR`
      del evento (`HIGH_STRESS_EEG` → WARNING) si lo hay. Idéntico a los
      otros dos.
    - Animación: pulso sutil (`biocore-brainwave`) cuya velocidad sube con
      `mental_workload` — el dato modula la animación, no la decora
      (mismo criterio que FC → velocidad de latido). Sin `mental_workload`
      (band power presente pero sin campos DERIVADOS), cerebro estático.
    - Métrica legible: banda dominante entre las presentes + carga mental,
      con la honestidad de Fase 5.1 (es el estado ACTUAL, no un snapshot
      que finge permanencia)."""
    neuro = state.all_domains()["neurological"] if state else None
    descriptors = dict(neuro.descriptors) if neuro is not None else {}
    severity = _severity_for_domain(state, "neurological")
    events = _domain_events(state, "neurological")

    if not descriptors:
        # Gate visual: el dominio neuro vacío (escritor no-neuro) se dibuja
        # "sin dato" en gris — nunca un color que implique una medición.
        # Espejo exacto del `hr is None` del corazón.
        color = NEUTRAL_COLOR
        animation_css = ""
        metric_label = "Estado: sin dato neurológico"
    else:
        color = STABLE_COLOR if severity is None else SEVERITY_COLOR[severity]

        workload = descriptors.get("mental_workload")
        if workload is not None:
            # workload 0 → 3.0s (pulso lento), workload 100 → ~0.9s (rápido).
            wave_duration = max(0.9, min(3.0, 3.0 - (workload.value / 100.0) * 2.1))
            animation_css = (
                f"animation: biocore-brainwave {wave_duration:.2f}s ease-in-out infinite; "
                "transform-origin: center;"
            )
        else:
            animation_css = ""

        present_bands = [(b, descriptors[b].value) for b in _BRAIN_BAND_DESCRIPTORS if b in descriptors]
        if present_bands:
            dominant = max(present_bands, key=lambda kv: kv[1])[0].replace("_power", "")
            band_label = f"Banda dom.: {dominant.upper()}"
        else:
            band_label = "Banda dom.: sin dato"
        metric_label = (
            f"{band_label} · Carga mental: {workload.value:.0f}"
            if workload is not None
            else band_label
        )

    halo = ""
    if severity in (EventSeverity.WARNING, EventSeverity.CRITICAL):
        halo_speed = 0.55 if severity == EventSeverity.CRITICAL else 1.3
        halo = (
            f'<circle cx="12" cy="11" r="11.5" fill="none" stroke="{color}" stroke-width="1.2" '
            f'style="animation: biocore-alert-halo {halo_speed}s ease-in-out infinite;"/>'
        )

    alerts_html = "".join(
        f'<div class="biocore-organ-alert">{lbl}</div>' for lbl in _event_labels_for_organ(events, "brain")
    )

    # Bug 1 (2026-07-13): sin sangría, igual que corazón/pulmones — si no,
    # Markdown lo trata como bloque de código literal antes de que
    # unsafe_allow_html deje pasar el SVG.
    return (
        '<div class="biocore-organ-card">'
        '<svg viewBox="0 0 24 24" width="110" height="110" style="overflow: visible;">'
        f'{halo}'
        f'<path d="{_BRAIN_PATH}" fill="{color}" style="{animation_css}"/>'
        '</svg>'
        '<div class="biocore-organ-title">🧠 Cerebro</div>'
        f'<div class="biocore-organ-metric">{metric_label}</div>'
        f'{alerts_html}'
        '</div>'
    )


def render_ups_body(state: Optional[UnifiedPhysiologicalState]) -> None:
    """Fase 1.4: corazón y pulmones coloreados/animados desde un
    `UnifiedPhysiologicalState` real — nunca de texto del narrador.
    Capa 5A, Sub-fase 2 (2026-08-31): + el cerebro, tercer órgano, misma
    mecánica y mismo `state`.

    Fase 5.1 (2026-08-30): `state` viene de `get_latest_state()` (el último
    snapshot PERSISTIDO — modo caso clínico de Academia/Twin OS, cada paso
    de un escenario) o de `get_current_physiological_state()` (el estado
    ACTUAL en memoria, sin persistir — el Cuerpo Digital sincronizado de
    Twin OS, desde esta tanda). Ambos caminos son igualmente honestos: la
    diferencia es "actual vs. último guardado", no "real vs. inventado" —
    quien llama a esta función decide cuál mostrar y es responsable de que
    el copy alrededor lo diga (ver `render_synced_digital_twin_body()`).
    Si `state` es `None` (paciente sin ningún snapshot persistido
    todavía — solo posible con `get_latest_state()`, `get_current_
    physiological_state()` nunca devuelve `None`), los tres órganos se
    muestran en gris neutro."""
    st.markdown(_STYLE, unsafe_allow_html=True)
    if state is None:
        st.caption("Sin snapshot del UPS todavía para este paciente — cuerpo en estado neutro.")

    # Cerebro arriba (anatómicamente natural), centrado sobre corazón/pulmones.
    # El layout de dos órganos no se rompe: la fila de corazón/pulmones sigue
    # siendo `st.columns(2)` idéntica, sólo se le antepone la fila del cerebro.
    _, brain_col, _ = st.columns([1, 2, 1])
    with brain_col:
        st.markdown(_render_brain_card(state), unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(_render_heart_card(state), unsafe_allow_html=True)
    with col2:
        st.markdown(_render_lungs_card(state), unsafe_allow_html=True)
