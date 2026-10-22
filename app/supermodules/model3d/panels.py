"""Panel 3D del vectocardiograma (traído del aporte externo auditado, 2026-10-22).

Todo el cálculo vive en `src/signals/ecg/vcg.py` y la figura en
`visualization/vcg3d.py`; aquí solo está la interfaz. Rótulos de la
auditoría: "verificado en 1 paciente" (no "validado") y el acimut del vector
QRS medio retirado (difería 74° del real en el caso de referencia).
"""

from __future__ import annotations

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
