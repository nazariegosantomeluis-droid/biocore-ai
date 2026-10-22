"""Paneles 3D reutilizables (2026-10-21): vectocardiograma y mapa EEG en la cabeza.

Los usan "Crea tu modelo 3D" y, dentro de su módulo, ECG Lab (12
derivaciones) y EEG Neuro Lab. Todo el cálculo vive en `src/` y las figuras
en `visualization/`; aquí solo está la interfaz.
"""

from __future__ import annotations

from typing import Dict, Mapping

import numpy as np
import streamlit as st

PLOTLY_CONFIG = {"displaylogo": False, "scrollZoom": True}


def plotly_3d(fig, key: str) -> None:
    st.plotly_chart(fig, width="stretch", key=key, config=PLOTLY_CONFIG)


# ─────────────────────────────────────────────────────────────────────────
# Vectocardiograma
# ─────────────────────────────────────────────────────────────────────────

VCG_SOURCES = ("ptb", "clinical", "upload")
VCG_SOURCE_LABELS = {
    "ptb": "Paciente real (PTB)",
    "clinical": "ECG de la Vista Clínica",
    "upload": "Subir mi ECG (CSV)",
}


def _vcg_metrics(result) -> None:
    from visualization.vcg3d import measures_table

    m = result.measures
    cols = st.columns(4)
    cols[0].metric("Latidos promediados", f"{result.n_beats}", help="Latido mediano: mediana muestra a muestra.")
    cols[1].metric("Frecuencia", f"{result.heart_rate_bpm:.0f} lpm")
    cols[2].metric("Duración del QRS", f"{m.qrs_duration_ms:.0f} ms",
                   help="Desde que el vector empieza a moverse rápido hasta que se detiene (velocidad espacial).")
    cols[3].metric("Ángulo QRS-T espacial", f"{m.qrs_t_angle_deg:.0f}°",
                   help="Ángulo entre los vectores medios de despolarización (QRS) y repolarización (T). "
                        "Ángulos amplios se asocian a mayor riesgo cardiovascular (Oehler et al., 2014).")
    with st.expander("Todas las mediciones del asa"):
        st.table({k: [v] for k, v in measures_table(m).items()})


def render_vcg_panel(key: str = "vcg", *, default_source: str = "ptb", allow_clinical: bool = True) -> None:
    """Selector de fuente + VCG 3D + mediciones."""
    from src.signals.ecg import vcg as V
    from visualization.vcg3d import vcg_figure

    options = [s for s in VCG_SOURCES if allow_clinical or s != "clinical"]
    source = st.segmented_control("Fuente del ECG", options, format_func=VCG_SOURCE_LABELS.get,
                                  default=default_source, key=f"{key}_source") or default_source
    result, compare, compare_label = None, None, ""
    if source == "ptb":
        try:
            ref = V.ptb_reference()
        except Exception as exc:  # noqa: BLE001
            st.error(f"No se pudo leer el registro de referencia: {exc}")
            return
        show_real = st.toggle("Comparar con el VCG de Frank real", value=True, key=f"{key}_compare",
                              help="La paciente tiene además las derivaciones ortogonales de Frank registradas "
                                   "a la vez: sirven para comprobar la reconstrucción.")
        result = ref["kors"]
        if show_real:
            compare, compare_label = ref["real"].beat, "Frank real (registrado)"
        r = ref["corr"]
        st.caption(
            "Paciente real del PTB Diagnostic ECG Database (mujer de 81 años con infarto agudo inferolateral). "
            f"El VCG se reconstruye de sus 12 derivaciones con la matriz de Kors; comparado con su VCG de Frank "
            f"registrado, la correlación es X {r[0]:.2f}, Y {r[1]:.2f}, Z {r[2]:.2f} (la Z es la más difícil de "
            "reconstruir, como en la literatura)."
        )
    elif source == "clinical":
        data = st.session_state.get("ecg_data")
        if not data:
            st.info("Genera o carga un ECG en la pestaña «Clínica» de 12 Derivaciones y vuelve aquí.")
            return
        leads = {k: np.asarray(v, float) for k, v in data.items() if k != "time"}
        t = np.asarray(data.get("time", []), float)
        fs = float(1.0 / np.median(np.diff(t))) if t.size > 2 else 500.0
        origin = st.session_state.get("signal_source", "Vista Clínica")
        st.caption(f"ECG de la Vista Clínica ({origin}); si es simulado, el VCG también lo es.")
        try:
            result = V.vcg_from_12_leads(leads, fs, source=str(origin))
        except Exception as exc:  # noqa: BLE001
            st.warning(f"No se pudo calcular el VCG de ese ECG: {exc}")
            return
    else:
        up = st.file_uploader("CSV con las derivaciones I, II y V1-V6 (encabezados; columna de tiempo opcional)",
                              type=["csv", "txt"], key=f"{key}_csv")
        fs_default = st.number_input("Frecuencia de muestreo si no hay columna de tiempo (Hz)", 50, 10000, 500,
                                     key=f"{key}_fs")
        if up is None:
            st.caption("Formato: una columna por derivación (I, II, III, aVR, aVL, aVF, V1…V6; mayúsculas o "
                       "minúsculas). Se usan I, II y V1-V6 (matriz de Kors).")
            return
        try:
            leads, fs, note = V.read_leads_csv(up.getvalue(), default_fs=float(fs_default))
            st.caption(note.capitalize() + ".")
            if all(k in leads for k in ("VX", "VY", "VZ")):
                result = V.vcg_from_xyz(np.stack([leads["VX"], leads["VY"], leads["VZ"]], axis=1), fs,
                                        r_signal=leads.get("II"), source="Frank (archivo)")
            else:
                result = V.vcg_from_12_leads(leads, fs, source=up.name)
        except V.LeadsMissingError as exc:
            st.error(str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            st.error(f"No se pudo leer el ECG: {exc}")
            return
    _vcg_metrics(result)
    plotly_3d(vcg_figure(result.beat, result.measures, compare=compare, compare_label=compare_label),
              key=f"{key}_fig")
    st.caption(
        "Cada asa es la trayectoria de la punta del vector cardiaco durante el latido mediano: P (verde), "
        "QRS (azul) y T (naranja); las flechas son sus vectores medios y las sombras, sus proyecciones en "
        "los planos frontal, horizontal y sagital. Gira con el ratón o el dedo. Medición automática "
        "educativa; no es un diagnóstico."
    )


# ─────────────────────────────────────────────────────────────────────────
# EEG: mapa sobre la cabeza
# ─────────────────────────────────────────────────────────────────────────

BAND_LABELS = {"delta": "Delta", "theta": "Theta", "alpha": "Alfa", "beta": "Beta", "gamma": "Gamma"}


def relative_band_power(signals: Mapping[str, np.ndarray], fs: float) -> Dict[str, Dict[str, float]]:
    """{canal: {banda: % de la potencia}} con el `EegAnalyzer` del laboratorio."""
    from src.signals.eeg.eeg_analyzer import EegAnalyzer

    out = {}
    an = EegAnalyzer(fs=fs)
    for name, x in signals.items():
        res = an.analyze(np.asarray(x, float))
        if not res.available:
            continue
        tot = sum(res.band_power.values()) or 1.0
        out[name] = {b: 100.0 * p / tot for b, p in res.band_power.items()}
    return out


def render_head_map(rel: Mapping[str, Mapping[str, float]], key: str, *, default_band: str = "alpha",
                    note: str = "") -> None:
    from visualization import anatomy3d as A3

    band = st.segmented_control("Banda", list(BAND_LABELS), format_func=BAND_LABELS.get, default=default_band,
                                key=f"{key}_band") or default_band
    values = {ch: v[band] for ch, v in rel.items() if band in v}
    show_brain = st.toggle("Ver el cerebro por dentro", value=False, key=f"{key}_brain")
    fig = A3.head_figure(values=values, value_label=f"{BAND_LABELS[band]} (% de la potencia)",
                         value_format=".0f", show_brain=show_brain, camera="auto", height=560)
    meta = fig.layout.meta or {}
    plotly_3d(fig, key=f"{key}_fig")
    known = int(meta.get("points", 0))
    if known == 0:
        st.info("Ningún canal tiene nombre del sistema 10-20 (p. ej., Fp1, C3, O2 o derivaciones como P4-O2): "
                "no se pueden ubicar en la cabeza.")
    elif not meta.get("mapped"):
        st.caption(f"{known} canales ubicados: con menos de {A3.MAP_MIN_POINTS} no se interpola un mapa; se "
                   "muestran los valores medidos en cada punto.")
    else:
        st.caption(
            f"Mapa interpolado con splines esféricos (Perrin et al., 1989) a partir de {known} puntos medidos; "
            f"donde no hay ningún electrodo a menos de {A3.MAP_REACH_MM:.0f} mm queda en gris: ahí no hay datos. "
            + note
        )


def render_eeg_lab_head_map(analysis_cards, data_source: str, key: str = "eeg_lab_head3d") -> None:
    """Sección del EEG Neuro Lab: la potencia de cada canal ya analizado
    (`[(canal, resultado del EegAnalyzer)]`) sobre una cabeza 3D (10-20)."""
    from app.utils.design_system import render_error_state

    st.markdown("## 🧠 Mapa 3D sobre la cabeza")
    try:
        rel = {}
        for lead, res in analysis_cards:
            if res.available:
                tot = sum(res.band_power.values()) or 1.0
                rel[lead] = {b: 100.0 * p / tot for b, p in res.band_power.items()}
        if not rel:
            st.info("No hay canales con señal limpia suficiente para el mapa.")
            return
        render_head_map(rel, key, note=f"Señal: {data_source}; si es simulada, el mapa también lo es.")
        with st.expander("Comparar con un EEG real (persona sana, relajada)"):
            render_reference_eeg_map(f"{key}_ref")
    except Exception as exc:  # noqa: BLE001
        render_error_state("No se pudo dibujar el mapa 3D.", exception=exc)


def render_reference_eeg_map(key: str = "eeg3d_ref") -> None:
    """EEG real de referencia (CAP Sleep n16): 5 derivaciones bipolares del
    hemisferio derecho."""
    from src.signals.reference_recordings import cap_n16

    d = cap_n16()
    rel = relative_band_power(d["leads"], d["fs"])
    render_head_map(rel, key, note="Derivaciones bipolares: cada punto es el centro entre sus dos electrodos.")
    st.caption("Registro real: CAP Sleep Database, n16 (persona sana despierta y relajada; 30 s). Solo tiene "
               "canales del lado derecho, por eso el izquierdo queda en gris.")
