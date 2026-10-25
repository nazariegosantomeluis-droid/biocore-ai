"""Paneles 3D (traídos del aporte externo auditado): vectocardiograma (2026-10-22)
y mapa EEG sobre la cabeza (Tanda 2D, 2026-10-24).

Todo el cálculo vive en `src/` y las figuras en `visualization/`; aquí solo
está la interfaz. Rótulos de la auditoría: VCG "verificado en 1 paciente" (no
"validado"), acimut del vector QRS medio retirado (difería 74° del real); mapa
EEG con el tramo de referencia rotulado por cómo se eligió (por su alfa, no por
el hipnograma) y la sobreoscilación del spline declarada con su porcentaje.
"""

from __future__ import annotations

from typing import Dict, Mapping

import numpy as np
import streamlit as st

PLOTLY_CONFIG = {"displaylogo": False, "scrollZoom": True}

VCG_VERIFIED_LABEL = "Verificado en 1 paciente real (PTB s0010, derivaciones de Frank simultáneas)"

VCG_SOURCES = ("ptb", "upload")
VCG_SOURCE_LABELS = {"ptb": "Paciente real (PTB)", "upload": "Subir mi ECG (CSV)"}


def plotly_3d(fig, key: str) -> None:
    st.plotly_chart(fig, width="stretch", key=key, config=PLOTLY_CONFIG)


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


def render_vcg_panel(key: str = "vcg") -> None:
    """Selector de fuente + VCG 3D + mediciones."""
    from src.signals.ecg import vcg as V
    from visualization.vcg3d import MEAN_VECTOR_NOTE, vcg_figure

    st.info(f"**{VCG_VERIFIED_LABEL}.** La reconstrucción de Kors (Kors et al., 1990) se comparó con el VCG de "
            "Frank grabado a la vez en esa paciente; un solo caso no es una validación clínica.")
    source = st.segmented_control("Fuente del ECG", VCG_SOURCES, format_func=VCG_SOURCE_LABELS.get,
                                  default="ptb", key=f"{key}_source") or "ptb"
    compare, compare_label = None, ""
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
                st.caption("Este VCG es una reconstrucción de Kors: no hay un VCG de Frank de este archivo con el "
                           "cual compararlo.")
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
        "QRS (azul) y T (naranja); las sombras son sus proyecciones en los planos frontal, horizontal y "
        "sagital. Gira con el ratón o el dedo. Medición automática educativa; no es un diagnóstico."
    )
    st.caption(MEAN_VECTOR_NOTE)


# ─────────────────────────────────────────────────────────────────────────
# EEG: mapa sobre la cabeza (Tanda 2D, 2026-10-24)
# ─────────────────────────────────────────────────────────────────────────

BAND_LABELS = {"delta": "Delta", "theta": "Theta", "alpha": "Alfa", "beta": "Beta", "gamma": "Gamma"}
# El tramo de referencia se eligió por su alfa: abrirlo en alfa presentaría el
# criterio de selección como si fuera un hallazgo. Se abre en la primera banda.
REFERENCE_DEFAULT_BAND = "delta"
OVERSHOOT_EXTRAPOLATION_NOTE_FROM = 0.10


def relative_band_power(signals: Mapping[str, np.ndarray], fs: float) -> Dict[str, Dict[str, float]]:
    """{canal: {banda: % de la potencia}} con el `EegAnalyzer` del laboratorio."""
    from src.signals.eeg.eeg_analyzer import EegAnalyzer

    out = {}
    an = EegAnalyzer(fs=fs)
    for name, x in signals.items():
        res = an.analyze(np.asarray(x, float))
        if res.available:
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
        return
    if not meta.get("mapped"):
        st.caption(f"{known} canales ubicados: con menos de {A3.MAP_MIN_POINTS} no se interpola un mapa; se "
                   "muestran los valores medidos en cada punto.")
        return
    st.caption(f"Mapa interpolado con splines esféricos (Perrin et al., 1989; m = 4, 50 términos, λ = 1e-5) a "
               f"partir de {known} puntos medidos; donde no hay ningún electrodo a menos de "
               f"{A3.MAP_REACH_MM:.0f} mm queda en gris: ahí no hay datos. " + note)
    clipped = float(meta.get("clipped_fraction", 0.0))
    text = (f"Sobreoscilación: el spline se pasa del rango medido en el {clipped:.0%} de la zona coloreada; ahí "
            "el color se recorta al mínimo o al máximo medido.")
    if clipped >= OVERSHOOT_EXTRAPOLATION_NOTE_FROM:
        text += (" Con tan pocos puntos, buena parte del color es extrapolación: lee el mapa como la ubicación de "
                 "los valores medidos, no como una topografía.")
    st.caption(text)


def render_reference_eeg_map(key: str = "eeg3d_ref") -> None:
    """EEG real de referencia (CAP Sleep n16): 5 derivaciones del lado derecho,
    con el rótulo de cómo se eligió el tramo (meta del archivo, sin reescribir)."""
    from src.signals.reference_recordings import cap_n16, source_line

    d = cap_n16()
    a, b = d["segment_s"]
    st.caption(f"{source_line('cap_n16')} — 30 s ({a:.0f}–{b:.0f} s del registro).")
    st.info(f"**Cómo se eligió este tramo.** {d['detail']} Por eso que la alfa domine aquí es el criterio de "
            f"selección, no un hallazgo. {d['hypnogram_check'] or 'No se comprobó contra el hipnograma.'}")
    render_head_map(relative_band_power(d["leads"], d["fs"]), key, default_band=REFERENCE_DEFAULT_BAND,
                    note="Derivaciones bipolares: cada punto se dibuja en el centro entre sus dos electrodos "
                         "(convención de dibujo, no un registro ahí); C4-A1 va en C4 porque A1 (oreja) no está "
                         "en el modelo. Solo hay canales del lado derecho: el izquierdo queda en gris.")
