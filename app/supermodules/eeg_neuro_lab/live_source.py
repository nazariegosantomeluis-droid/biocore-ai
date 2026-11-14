"""La fuente «Hardware EEG en vivo» de la pestaña Clínica del EEG Neuro Lab (2026-11-14).

Reemplaza a la rama que usaba `ESP32SignalSource` (ver CHANGELOG, 2026-11-14). Esa rama tomaba una sola señal
de la placa y la copiaba a cuatro canales rotulados Fp1, Fp2, C3 y C4 (la misma señal desplazada, con ruido
encima), y sin hardware caía en silencio a la señal sintética (la casilla «Simular si no hay hardware
conectado» venía marcada) con la etiqueta «Hardware en vivo (simulado)»: canales inventados y una fuente que
decía ser hardware (Art. I).

Aquí cada dispositivo dice lo que es, la procedencia es SENSOR_REAL solo mientras un equipo real manda datos, y
sin señal en vivo no hay análisis: la página dice por qué. Practicar sin hardware es una elección explícita
(«Simulador de práctica» o «Tablero sintético de BrainFlow»), siempre rotulada SIMULACIÓN.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import streamlit as st
from streamlit.errors import StreamlitAPIException

from app.supermodules.eeg_neuro_lab import live_service
from domain.physiology.state import Provenance
from hardware.eeg_live import (DEVICES, NO_VERIFICABLE, SENSOR_REAL, SIMULACION, BackendError, ChannelQuality,
                               EegDevice, LslStreamChoice, assess_channels, backend_unavailable_reason,
                               discover_lsl_streams, prepare)
from hardware.eeg_live.devices import PARAM_LABELS

SOURCE_LABEL = "Hardware EEG en vivo"
TUTORIAL_TAB = "EEG en vivo (tutorial)"
MIN_SECONDS = 4.0
MONITOR_SECONDS = 5.0
LOSS_WARNING_FRACTION = 0.9
MAINS_OPTIONS = {"60 Hz (México)": 60.0, "50 Hz (Europa)": 50.0, "Sin filtro": None}
MANUAL_PORT = "Escribir el puerto…"
FTDI_VID = 0x0403

STATE_ICONS = {"transmitiendo": "🟢", "conectando": "🟡", "sin datos": "🟠", "sin conexión": "🔴", "detenido": "⚪"}
PROVENANCE_LABEL = {SENSOR_REAL: "SENSOR_REAL", SIMULACION: "SIMULACIÓN", NO_VERIFICABLE: "origen no verificable"}
PROVENANCE_TEXT = {
    SENSOR_REAL: "🟢 PROCEDENCIA: SENSOR_REAL — {detail}, mandando datos ahora mismo.",
    SIMULACION: "🟡 PROCEDENCIA: SIMULACIÓN — {detail}; no es un sensor.",
    NO_VERIFICABLE: ("🟠 PROCEDENCIA: NO VERIFICABLE — {detail}. BIOCORE no puede comprobar si detrás hay un "
                     "equipo o un programa que genera datos; al gemelo se guarda como simulación."),
}
REAL_EEG_NOTE = (
    "no se traduce a un estado con EEG real: la potencia del EEG cae con la frecuencia (componente aperiódico, "
    "tipo 1/f; Donoghue et al. 2020, Nature Neuroscience 23:1655-1665), así que la banda con más potencia "
    "absoluta puede ser delta aunque la persona esté despierta. La traducción banda → estado solo vale para los "
    "patrones que construye el generador"
)
HIDDEN_FOR_REAL_EEG = ("Classification", "Clinical Note", "Alert")


@dataclass
class LiveData:
    """Lo que la página analiza: los canales elegidos, ya sin tendencia y sin red, y de dónde salen."""

    eeg: Dict[str, np.ndarray]
    time: np.ndarray
    fs: float
    label: str
    provenance: str
    detail: str
    quality: Dict[str, ChannelQuality]


# ---------------------------------------------------------------- helpers para la página
def twin_provenance(live: Optional[LiveData]) -> Tuple[Provenance, str]:
    """Procedencia con la que se guarda al gemelo y la frase que lo explica."""
    if live is None:
        return Provenance.SIMULACION, "Procedencia: simulación (señal generada o archivo cargado, no un sensor en vivo)."
    if live.provenance == SENSOR_REAL:
        return Provenance.SENSOR_REAL, f"Procedencia: SENSOR_REAL ({live.detail}, mandando datos en este momento)."
    if live.provenance == NO_VERIFICABLE:
        return Provenance.SIMULACION, (f"Procedencia: se guarda como simulación porque BIOCORE no puede verificar "
                                       f"el origen del {live.detail}.")
    return Provenance.SIMULACION, f"Procedencia: simulación ({live.detail})."


def save_blocker(live: Optional[LiveData], channel: str) -> Optional[str]:
    """Motivo para no guardar al gemelo un canal en vivo con problemas de calidad (None si se puede)."""
    if live is None or channel not in live.quality or live.quality[channel].ok:
        return None
    return f"El canal {channel} tiene problemas de calidad: " + " ".join(live.quality[channel].messages)


def channel_summary(result, interpretation_applies: bool) -> str:
    """Resumen de un canal. Con EEG real, solo lo medido: sin «Clasificación» ni «Interpretación»."""
    if interpretation_applies:
        return result.summary
    bp = result.band_power
    return (f"Banda con más potencia: {result.dominant_band.upper()} (no se traduce a un estado con EEG real). "
            f"Potencia: Δ={bp['delta']:.2f}, θ={bp['theta']:.2f}, α={bp['alpha']:.2f}, β={bp['beta']:.2f}, "
            f"γ={bp['gamma']:.2f}.")


def visible_findings(findings: Dict[str, str], interpretation_applies: bool) -> Dict[str, str]:
    """Con EEG real se ocultan las frases que traducen la banda dominante a un estado (ver `REAL_EEG_NOTE`)."""
    if interpretation_applies:
        return dict(findings)
    return {k: v for k, v in findings.items() if k not in HIDDEN_FOR_REAL_EEG}


# ---------------------------------------------------------------- controles del simulador
def _rerun(fragment: bool) -> None:
    """Vuelve a dibujar en seguida para que el botón muestre la acción contraria (ver ecg_live/tutorial.py)."""
    if fragment:
        try:
            st.rerun(scope="fragment")
            return
        except (TypeError, StreamlitAPIException):
            pass
    st.rerun()


def render_simulator_controls(sim, container, prefix: str, fragment: bool = False) -> None:
    """Botones del simulador. Son botones y no casillas: así nunca muestran un estado viejo cuando el mismo
    simulador se movió desde la otra pestaña."""
    estado = "cerrados" if sim.eyes_closed else "abiertos"
    flojo = sim.loose or "ninguno"
    cable = "conectado" if sim.plugged else "desconectado"
    container.caption(f"Simulador: ojos {estado} · electrodo flojo: {flojo} · cable {cable}.")
    if sim.eyes_closed:
        if container.button("👀 Abrir los ojos", key=f"{prefix}_open"):
            sim.set_eyes_closed(False)
            _rerun(fragment)
    elif container.button("😌 Cerrar los ojos", key=f"{prefix}_close"):
        sim.set_eyes_closed(True)
        _rerun(fragment)
    if container.button("😉 Parpadear", key=f"{prefix}_blink"):
        sim.blink()
    if sim.loose:
        if container.button(f"🩹 Volver a fijar {sim.loose}", key=f"{prefix}_fix"):
            sim.set_loose(None)
            _rerun(fragment)
    else:
        canal = container.selectbox("Electrodo para aflojar", list(sim.channels), index=len(sim.channels) - 2,
                                    key=f"{prefix}_which")
        if container.button("✋ Aflojar ese electrodo", key=f"{prefix}_loosen"):
            sim.set_loose(canal)
            _rerun(fragment)
    if sim.plugged:
        if container.button("🔌 Desconectar el cable", key=f"{prefix}_unplug"):
            sim.unplug()
            _rerun(fragment)
    elif container.button("🔌 Reconectar el cable", key=f"{prefix}_plug"):
        sim.plug()
        _rerun(fragment)


# ---------------------------------------------------------------- barra lateral
def _serial_ports() -> List:
    try:
        from hardware.ecg_plugplay.ports import system_ports
        return [p for p in system_ports() if not p.is_bluetooth]
    except Exception:
        return []


def _port_label(port) -> str:
    hint = " · chip FTDI, como el dongle de OpenBCI" if port.vid == FTDI_VID else ""
    return f"{port.device} · {port.description or port.label}{hint}"


def _params_inputs(device: EegDevice, sb) -> Dict[str, str]:
    params: Dict[str, str] = {}
    if "serial_port" in device.required:
        ports = _serial_ports()
        labels = {p.device: _port_label(p) for p in ports}
        choice = sb.selectbox("Puerto del dongle", list(labels) + [MANUAL_PORT],
                              format_func=lambda d: labels.get(d, d), key="eeglab_live_port")
        if choice == MANUAL_PORT:
            choice = sb.text_input("Puerto (COM3, /dev/ttyUSB0, /dev/cu.usbserial-…)", key="eeglab_live_port_manual")
        params["serial_port"] = (choice or "").strip()
    if device.optional:
        with sb.expander("Opcional: si hay varios equipos cerca"):
            for name in device.optional:
                value = st.text_input(PARAM_LABELS[name].capitalize(), key=f"eeglab_live_{device.key}_{name}")
                if value.strip():
                    params[name] = value.strip()
    return params


def _lsl_picker(sb) -> Optional[LslStreamChoice]:
    if sb.button("🔎 Buscar flujos LSL", key="eeglab_live_lsl_search"):
        try:
            st.session_state["eeglab_live_lsl_found"] = discover_lsl_streams(1.5)
        except BackendError as exc:
            sb.error(str(exc))
    found: List[LslStreamChoice] = st.session_state.get("eeglab_live_lsl_found", [])
    if not found:
        sb.info("Pulsa «Buscar flujos LSL» con el programa que publica el EEG ya transmitiendo.")
        return None
    labels = [c.label for c in found]
    pick = sb.selectbox("Flujo LSL", labels, key="eeglab_live_lsl_pick")
    return found[labels.index(pick)]


def _monitor_body(service, channels: Tuple[str, ...], mains_hz: Optional[float]) -> None:
    snap = service.snapshot(seconds=MONITOR_SECONDS)
    st.markdown(f"{STATE_ICONS.get(snap['state'], '⚪')} **{snap['state'].capitalize()}** — {snap['message']}")
    data, fs = snap["data"], snap["fs"]
    if snap["state"] != "transmitiendo" or not fs or data.shape[-1] < 16:
        return
    names = list(snap["channels"])
    shown = [c for c in channels if c in names] or names[:4]
    clean = prepare(data, fs, mains_hz)
    frame = pd.DataFrame({c: clean[names.index(c)] for c in shown},
                         index=np.round((np.arange(clean.shape[1]) - clean.shape[1] + 1) / fs, 3))
    st.line_chart(frame, height=220)
    st.caption(f"Últimos {MONITOR_SECONDS:.0f} s, sin tendencia y sin red (µV). Se actualiza solo cada segundo; el "
               "análisis de abajo usa lo que había al pulsar «Leer los últimos segundos».")


_fragment = getattr(st, "fragment", None)
_monitor = _fragment(run_every=1.0)(_monitor_body) if _fragment is not None else _monitor_body


def render_live_source(duration_s: float) -> Optional[LiveData]:
    """Dibuja los controles en la barra lateral y el monitor en vivo arriba de la página.

    Devuelve los últimos `duration_s` segundos (o los que haya, desde `MIN_SECONDS`) de los canales elegidos, o
    None si no hay señal en vivo; con None la página dice por qué y no analiza nada.
    """
    sb = st.sidebar
    sb.markdown(f"### {SOURCE_LABEL}")
    names = [d.name for d in DEVICES]
    device = DEVICES[names.index(sb.selectbox("Dispositivo EEG", names, key="eeglab_live_device"))]
    sb.caption(device.connection + f" ¿Primera vez? Abre la pestaña «{TUTORIAL_TAB}».")
    reason = backend_unavailable_reason(device.backend)
    if reason:
        sb.error(reason)
        st.info(f"{device.name} no se puede usar en esta computadora: {reason}")
        return None

    manager = live_service.get_manager()
    other = manager.service if (manager.service is not None and manager.service.is_running
                                and manager.service.device.key != device.key) else None
    if device.key == "practica":
        practice = live_service.get_practice()
        service = practice.service
        render_simulator_controls(practice.device, sb, "eeglab_live_sim")
        connect, disconnect = practice.service.start, practice.service.stop
        if other is not None:
            sb.warning(f"{other.device.name} sigue conectado. Para soltarlo, elígelo y pulsa «⏹ Desconectar».")
    else:
        params = _params_inputs(device, sb)
        lsl_choice = _lsl_picker(sb) if device.backend == "lsl" else None
        service = manager.service if (manager.service and manager.service.device.key == device.key) else None

        def connect():
            if device.backend == "lsl" and lsl_choice is None:
                return
            manager.connect(device, params, lsl_choice)

        disconnect = manager.disconnect
        if other is not None:
            sb.warning(f"Está conectado {other.device.name}. «▶ Conectar» lo cierra y abre {device.name}.")
    mains_hz = MAINS_OPTIONS[sb.radio("Filtro de la red eléctrica", list(MAINS_OPTIONS), key="eeglab_live_mains",
                                      help="Quita el zumbido de los aparatos y contactos cercanos (filtro notch).")]

    running = service is not None and service.is_running
    if running:
        if sb.button("⏹ Desconectar", key="eeglab_live_stop"):
            disconnect()
            st.rerun()
    elif sb.button("▶ Conectar", key="eeglab_live_start"):
        connect()
        st.rerun()
    sb.button("🔄 Leer los últimos segundos", key="eeglab_live_refresh")

    if service is None or not (running or service.state.value != "detenido"):
        st.info("Fuente en vivo: elige el dispositivo y pulsa «▶ Conectar» en la barra lateral. Sin conexión no hay "
                "señal que analizar (no se usa una señal de respaldo).")
        return None
    snap = service.snapshot(seconds=duration_s)
    selected = _channel_choice(sb, snap, device)
    st.markdown("#### Señal en vivo")
    _monitor(service, tuple(selected), mains_hz)
    if snap["state"] != "transmitiendo":
        if snap["warnings"]:
            sb.warning("Último aviso: " + snap["warnings"][-1])
        st.info(f"Sin señal en vivo ({snap['state']}): {snap['message']} No se analiza nada mientras tanto.")
        return None
    if snap["seconds_available"] < MIN_SECONDS:
        st.info(f"Juntando señal: {snap['seconds_available']:.0f} de {MIN_SECONDS:.0f} s. Pulsa «Leer los últimos "
                "segundos» en un momento.")
        return None
    if not selected:
        sb.info("Elige al menos un canal.")
        return None
    return _live_data(snap, selected, mains_hz, sb)


def _channel_choice(sb, snap, device: EegDevice) -> List[str]:
    channels = list(snap["channels"])
    if not channels:
        return []
    default = [c for c in device.default_channels if c in channels] or channels[:4]
    return sb.multiselect("Canales a analizar", channels, default=default,
                          key=f"eeglab_live_channels_{snap['key']}")


def _live_data(snap, selected: List[str], mains_hz: Optional[float], sb) -> LiveData:
    raw, fs, channels = snap["data"], float(snap["fs"]), list(snap["channels"])
    prepared = prepare(raw, fs, mains_hz)
    quality = assess_channels(raw, prepared, fs, channels, mains_hz)
    eff = snap["effective_fs"]
    if eff is not None and eff < LOSS_WARNING_FRACTION * fs:
        sb.warning(f"Llegan {eff:.0f} muestras por segundo de {fs:.0f}: se están perdiendo muestras (Bluetooth débil o "
                   "computadora ocupada). El análisis trata la señal como continua.")
    provenance = snap["provenance"]
    message = PROVENANCE_TEXT[provenance].format(detail=snap["detail"])
    (sb.success if provenance == SENSOR_REAL else sb.warning)(message)
    sb.caption("Unidades: " + snap["unit_note"])
    for name in selected:
        if not quality[name].ok:
            sb.warning(f"{name}: " + " ".join(quality[name].messages))
    time = np.arange(raw.shape[1]) / fs
    eeg = {name: prepared[channels.index(name)] for name in selected}
    eeg["time"] = time
    label = f"{snap['detail']} ({PROVENANCE_LABEL[provenance]})"
    return LiveData(eeg, time, fs, label, provenance, snap["detail"], quality)
