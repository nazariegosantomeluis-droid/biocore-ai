"""Instrumentos de variabilidad cardiaca (T2, 2026-11-18).

El código se movió tal cual desde `render_hrv_page()` y `_render_hrv_save_to_twin()` de `app/main.py`: ningún
cálculo, texto, cita ni compuerta cambió. La página de siempre (`render_hrv_page`) es ahora la composición de estos
instrumentos con `PAGE`; una estación de la ruta los monta con `station_context(prefijo)`.

- `rr_source`: la serie RR (simulación con RSA o serie manual). Sus controles van en `ctx.panel`.
- `tiempo`: SDNN, RMSSD y pNN50 con su «¿Qué significa…?» firmado (B2, [SG2017]).
- `frecuencia`: espectro y potencias LF/HF, con la razón LF/HF rotulada «interpretación discutida» [B2013].
- `rsa`, `no_lineal`: los paneles de siempre.
- `guardar`: el único camino de escritura al UPS de este laboratorio (botón explícito, procedencia simulación)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import numpy as np
import streamlit as st

from app.instruments.base import InstrumentContext, InstrumentResult
from app.instruments.common import render_metric_explained
from app.supermodules import hrv_nonlinear_panel, rsa_panel, safe_import_ecg_modules, safe_import_plotly
from app.utils.design_system import render_error_state
from app.utils.patient_banner import patient_start_value
from app.utils.patient_session import get_active_patient_id, get_active_session_factory
from src.signals.ecg.rsa import HF_BAND_HZ, LF_BAND_HZ, RsaParams, band_power, detect_rsa, rr_spectrum

PLOTLY_GO, _, PLOTLY_OK = safe_import_plotly()

MANUAL_SOURCE = 'Serie RR manual'


@dataclass
class RRSeries:
    rr_ms: np.ndarray
    source: str
    rsa_signals: Any = None
    rsa_params: Optional[RsaParams] = None
    r_peak_times_s: Optional[np.ndarray] = None


def rr_source(ctx: InstrumentContext) -> Optional[RRSeries]:
    """La serie RR del análisis, o `None` (con el motivo en pantalla) si no hay una que analizar."""
    panel = ctx.panel
    # Sub-arco RSA (2026-10-19): la fuente demo era "Demo (ECG-derived)" y no
    # derivaba de ningún ECG (`mean_rr + N(0, 3%)`, ruido blanco). Ahora los RR
    # salen de verdad de un ECG sintético con RSA, por el detector TKEO.
    source = panel.radio('Origen de la HRV', [rsa_panel.RSA_SOURCE_LABEL, MANUAL_SOURCE], index=0,
                         key=ctx.auto_key('hrv_source'))
    rr_ms = None
    rsa_signals, rsa_params, r_peak_times_s = None, None, None
    if source == MANUAL_SOURCE:
        txt = st.text_area('Pega RR intervals en ms separados por comas', '800,820,790,810,805',
                           key=ctx.auto_key('hrv_manual_rr'))
        try:
            rr_ms = np.array([float(x.strip()) for x in txt.split(',') if x.strip()])
        except Exception:
            rr_ms = None
    else:
        ECGAnalyzer, _, _, _, _ = safe_import_ecg_modules()
        if ECGAnalyzer is None:
            render_error_state('Motor ECGAnalyzer (detector TKEO) no disponible en este entorno -- sin RR que derivar.')
            return None
        # Integración (2026-11-17): FC base y FR EMPIEZAN en las del paciente activo del UPS (si caben en el control).
        # La amplitud RSA no: el `hrv` del UPS no dice qué índice es, y ajustar la serie para «dar» ese número sería
        # inventar la relación entre ambos.
        hr_start, hr_note = patient_start_value('hr', 40, 140, 72, 'FC base')
        rr_start, rr_note = patient_start_value('rr', 6, 30, 15, 'Frecuencia respiratoria')
        rsa_params = RsaParams(
            hr_base_bpm=float(panel.slider('FC base (lpm)', 40, 140, int(hr_start), key=ctx.auto_key('hrv_hr_base'))),
            rsa_amplitude_bpm=float(panel.slider('Amplitud RSA (lpm)', 0, 15, 5,
                help='Cuánto sube la FC en inspiración y baja en espiración respecto de la FC base.',
                key=ctx.auto_key('hrv_amplitude'))),
            respiratory_rate_rpm=float(panel.slider('Frecuencia respiratoria (rpm)', 6, 30, int(rr_start),
                help='La banda HF (0.15–0.40 Hz) está influida por la respiración entre 9 y 24 respiraciones '
                     'por minuto [SG2017]; fuera de ese rango la RSA no se lee como HF.',
                key=ctx.auto_key('hrv_resp_rate'))),
        )
        for note in (hr_note, rr_note):
            if note:
                panel.caption(note)
        if hr_note or rr_note:
            panel.caption('La amplitud RSA no sale del paciente: el UPS guarda «hrv» sin decir qué índice es.')
        # 240 s (~290 latidos a 72 lpm): SampEn y DFA α1 necesitan ≥200 latidos; con 120 s
        # (~144) la fuente por defecto declinaría ambas.
        n = panel.slider('Duración (seg)', 30, 300, 240, key=ctx.auto_key('hrv_duration'))
        rsa_signals, r_peak_times_s = rsa_panel.simulate_rsa_rr(rsa_params, float(n), ECGAnalyzer)
        rr_ms = np.diff(r_peak_times_s) * 1000.0
        st.caption(
            f"Fuente: simulación -- {len(r_peak_times_s)} picos R detectados por TKEO sobre un ECG sintético "
            "(McSharry 2003) cuya FC modula la respiración. No es un registro de un paciente."
        )

    if rr_ms is None or len(rr_ms) < 5:
        render_error_state('RR series insuficiente -- provee más latidos o usa la fuente de simulación.')
        return None
    return RRSeries(rr_ms=rr_ms, source=source, rsa_signals=rsa_signals, rsa_params=rsa_params,
                    r_peak_times_s=r_peak_times_s)


def tiempo(ctx: InstrumentContext, series: RRSeries) -> InstrumentResult:
    """Dominio temporal. `values`: sdnn, rmssd, pnn50 y mean_nn (ms, ms, %, ms)."""
    rr_ms = series.rr_ms
    diffs = np.diff(rr_ms)
    sdnn = float(np.std(rr_ms, ddof=1))
    rmssd = float(np.sqrt(np.mean(diffs**2))) if len(diffs) > 0 else 0.0
    pnn50 = float(np.sum(np.abs(diffs) > 50) / max(1, len(diffs)) * 100)
    mean_nn = float(np.mean(rr_ms))

    # Pulido profesional (2026-11-16, Art. I): las capas de «¿Qué significa…?» de SDNN/RMSSD/pNN50 no tenían fuente
    # («Indicador general de variabilidad autonómica», «Bajos valores asociados a mayor riesgo cardiovascular»...) y
    # no hay tema firmado de HRV: se retiran. Queda la definición de cada cálculo (método, no una afirmación clínica).
    # Teoría citada 2 (2026-11-17): «¿Qué significa…?» con la línea firmada de B2 de cada valor ([SG2017]).
    from app.supermodules.learn_theory import SIGNED_HRV_PNN50, SIGNED_HRV_RMSSD, SIGNED_HRV_SDNN

    render_metric_explained('SDNN', f'{sdnn:.1f}', unit='ms', topic=SIGNED_HRV_SDNN)
    render_metric_explained('RMSSD', f'{rmssd:.1f}', unit='ms', topic=SIGNED_HRV_RMSSD)
    render_metric_explained('pNN50', f'{pnn50:.1f}', unit='%', topic=SIGNED_HRV_PNN50)
    st.caption('Cómo se calcula: SDNN = desviación estándar de los intervalos NN; RMSSD = raíz cuadrática media de las '
               'diferencias sucesivas entre intervalos NN; pNN50 = porcentaje de diferencias sucesivas mayores de 50 ms.')
    return InstrumentResult(values={"sdnn": sdnn, "rmssd": rmssd, "pnn50": pnn50, "mean_nn": mean_nn})


def frecuencia(ctx: InstrumentContext, series: RRSeries) -> InstrumentResult:
    """Espectro de la serie RR. `values`: lf y hf cuando el espectro se pudo calcular; vacío si no."""
    from app.supermodules.learn_theory import LF_HF_DISCUSSED, LF_HF_LABEL

    rr_ms = series.rr_ms
    try:
        # Sub-arco RSA: el cálculo en línea se movió a `rr_spectrum()` (compartido con
        # la RSA). Antes usaba `np.trapz`, que numpy 2.x ya no tiene -- el espectro
        # fallaba siempre y el `except` culpaba a scipy.
        f, pxx = rr_spectrum(rr_ms)
        lf_power = band_power(f, pxx, LF_BAND_HZ)
        hf_power = band_power(f, pxx, HF_BAND_HZ)
        lf_hf = lf_power / hf_power if hf_power > 0 else None
        st.markdown('### Vista Investigación — Espectro HRV')
        if PLOTLY_OK:
            fig = PLOTLY_GO.Figure()
            fig.add_trace(PLOTLY_GO.Scatter(x=f, y=pxx, mode='lines', name='PSD'))
            fig.update_layout(template='plotly_dark', height=320, xaxis_title='Hz', yaxis_title='Potencia')
            st.plotly_chart(fig, use_container_width=True, key=ctx.auto_key('hrv_spectrum'))
        else:
            st.line_chart(pxx)
        # Teoría citada 2, B3 (decisión de Luis): la razón va rotulada «interpretación discutida» con [B2013].
        lf_hf_txt = f'{lf_hf:.2f}' if lf_hf is not None else 'no disponible (potencia HF nula)'
        st.write(f'LF: {lf_power:.3f} — HF: {hf_power:.3f} — {LF_HF_LABEL} [B2013]: {lf_hf_txt}')
        st.caption(LF_HF_DISCUSSED)
    except ValueError as exc:
        st.info(f'No se pudo calcular el espectro HRV con esta serie RR: {exc}')
        return InstrumentResult()
    return InstrumentResult(values={"lf": float(lf_power), "hf": float(hf_power)})


def rsa(ctx: InstrumentContext, series: RRSeries) -> InstrumentResult:
    """RSA. Con la fuente manual no hay respiración simultánea: el panel declina con motivo."""
    r_peak_times_s = series.r_peak_times_s
    if r_peak_times_s is None:
        r_peak_times_s = np.concatenate([[0.0], np.cumsum(series.rr_ms) / 1000.0])
    rsa_signals = series.rsa_signals
    rsa_panel.render_rsa_panel(
        detect_rsa(r_peak_times_s, rsa_signals.respiration if rsa_signals is not None else None, rsa_panel.ECG_FS_HZ),
        rsa_signals, series.rsa_params, key=ctx.auto_key('hrv_rsa_chart'),
    )
    return InstrumentResult()


def no_lineal(ctx: InstrumentContext, series: RRSeries) -> InstrumentResult:
    hrv_nonlinear_panel.render_nonlinear_panel(series.rr_ms, key=ctx.auto_key('hrv_poincare'))
    return InstrumentResult()


def guardar(ctx: InstrumentContext, series: RRSeries, sdnn: float, mean_nn: float) -> InstrumentResult:
    """Segundo lab de la integración estrecha (2026-08-24, Capa 2 Fase 2.4) --
    mismo molde que tuvo `respiratory_lab/pages.py::_render_save_to_twin()`
    (desactivada el 2026-11-05: FR/AHI no fiables), aplicado al lado cardio-únicamente. Botón explícito, nunca
    automático. Fase 3 (2026-08-30): el bootstrap manual ya no existe --
    llama a `get_active_patient_id()`/`get_active_session_factory()`
    (`app/utils/patient_session.py`), el punto único de verdad que
    reemplazó la convención de copiar `twin_shell_ups_session_factory`/
    `twin_shell_ups_patient_id` en cada lab (decisión de alcance del piloto
    de Respiratory, ahora formalizada).

    Qué escribe -- solo lo real con destino confirmado (Paso 1 del recon
    cardiovascular): `hrv` mapeado desde `sdnn`, no RMSSD -- convención YA
    documentada en el repo (`domain/physiology/ml/risk_context.py`:
    "el UPS solo modela un 'hrv' genérico en ms -- se usa como proxy de
    SDNN"), no una decisión nueva. `heart_rate` mapeado desde `60000/mean_nn`
    -- derivado de la MISMA serie RR real, no fabricado. `rmssd`/`pnn50`/
    LF/HF no tienen slot en el schema -- no se escriben, no se fuerzan.

    Procedencia: `Provenance.SIMULACION` siempre -- ambas fuentes de este lab
    (RR manual pegado por el usuario, o RR demo generado con jitter) son
    entrada de demo/manual, nunca un sensor real verificado en el momento.
    `source_detail` incluye qué fuente (`source`) se usó.

    La raíz respiratoria (gate simétrico ya cerrado en el builder) hace su
    trabajo aquí sola: como `update_from_sensors()` solo recibe `"ecg"`, el
    dominio respiratorio del estado resultante queda vacío -- no hay pulmón
    fantasma que evitar a mano, espejo exacto de cómo Respiratory dejó
    cardiovascular vacío en su propio piloto.

    T2 (2026-11-18): antes `_render_hrv_save_to_twin()` de `app/main.py`. Con `PAGE`, la clave del botón es la de
    siempre (`hrv_lab_save_to_ups`). `saved_snapshot_id` dice qué snapshot se escribió en este rerun (o `None`)."""
    source = series.source
    st.markdown("#### 🔗 Guardar estado al gemelo")
    st.caption(
        "Escribe `heart_rate`/`hrv` reales (calculados de la serie RR de arriba -- `hrv` mapeado "
        "desde SDNN) al Unified Physiological State, bajo el mismo paciente que renderiza Digital "
        "Twin OS -- su corazón reaccionará a estos valores la próxima vez que abras esa página o "
        "pulses \"Sincronizar\" ahí. Procedencia: simulación (serie RR de demo/manual, no un sensor real)."
    )
    if not st.button("💾 Guardar estado al gemelo", key=ctx.k("hrv_lab_save_to_ups")):
        return InstrumentResult()
    from domain.physiology.state import Provenance, from_digital_twin_organism, save_state
    from app.engines.digital_twin_organism import DigitalTwinOrganism

    # Fase 3 (paciente único de sesión, 2026-08-30): ver el mismo
    # comentario en render_ecg_monitor_page() más arriba -- este era el
    # 2° de los 4 sitios que copiaban el bootstrap inline.
    session_factory = get_active_session_factory()
    patient_id = get_active_patient_id()

    heart_rate_bpm = 60000.0 / mean_nn
    organism = DigitalTwinOrganism()
    organism.update_from_sensors({
        "ecg": {
            "heart_rate": float(heart_rate_bpm),
            "hrv": float(sdnn),
        }
    })
    state = from_digital_twin_organism(
        organism, patient_id, provenance=Provenance.SIMULACION,
        source_detail=f"hrv_lab:sdnn_desde_serie_rr:fuente={source}",
    )
    with session_factory() as session:
        snapshot_id = save_state(session, state)

    st.success(f"Estado guardado al gemelo -- snapshot: {snapshot_id}")
    st.caption(
        f"cardiovascular: {len(state.cardiovascular.descriptors)} descriptores · "
        f"respiratory: {len(state.respiratory.descriptors)} descriptores "
        f"(vacío esperado -- este lab no envía dato respiratorio)"
    )
    return InstrumentResult(saved_snapshot_id=snapshot_id)
