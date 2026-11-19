"""Instrumentos de EEG (T4 de la ruta integrada, 2026-11-18).

El código se movió tal cual desde `app/supermodules/eeg_neuro_lab/page_content.py`: ningún cálculo, texto clínico,
cita ni compuerta cambió. La página de siempre es ahora la composición de estos instrumentos con `PAGE` (mismos
controles sin clave en el menú lateral); una estación de la ruta los monta con `station_context(prefijo)`.

- `fuente`: patrón, canales, origen de los datos y la señal. En una estación solo se ofrece la señal sintética: ni el
  EEG en vivo (como la placa ECG: pide consentimiento y un equipo), ni un CSV (no se sabe de quién viene), ni los dos
  patrones con evento inyectado (imaginación motora y tarea de engagement), cuyos controles viven en el menú lateral.
- `senales`: el trazo y la potencia de banda por canal.
- `metricas`: banda dominante, clasificación (solo con la señal sintética) y DAR, TBR y BAR con su cita.
- `guardar`: el único camino de escritura al UPS de este laboratorio (botón explícito)."""

from __future__ import annotations

import io
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple

import numpy as np
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from app.instruments.base import InstrumentContext, InstrumentResult
from app.utils.design_system import BADGES, GRAMMAR_NEUTRAL_STATE, PALETTE, render_error_state, render_metric_card, resolve_metric_card
from src.signals.eeg.eeg_analyzer import FINDING_LABELS_ES, band_label_es

try:
    from src.signals.eeg import (
        EegSignalGenerator, EegPattern, EegAnalyzer,
        classify_dar, classify_tbr, DAR_CITATION, TBR_CITATION, BAR_CITATION,
    )
    from app.supermodules.eeg_neuro_lab import engagement_panel, mu_erd_panel
    Eeg_import_error = None
except ImportError as e:
    mu_erd_panel = None
    engagement_panel = None
    EegSignalGenerator = None
    EegPattern = None
    EegAnalyzer = None
    classify_dar = None
    classify_tbr = None
    DAR_CITATION = None
    TBR_CITATION = None
    BAR_CITATION = None
    Eeg_import_error = e

# Arco 2C (2026-09-14): motor de parametrización espectral (χ aperiódico). Import guardado: si `fooof` no resolviera,
# el resto del EEG (potencia de banda, BAR/DAR/TBR, guardado al gemelo) sigue funcionando sin χ.
try:
    from src.signals.eeg.spectral_model import CHI_CITATION, classify_chi, fit_aperiodic_component
    SpectralModel_import_error = None
except ImportError as e:
    fit_aperiodic_component = None
    classify_chi = None
    CHI_CITATION = None
    SpectralModel_import_error = e

from app.supermodules.eeg_neuro_lab import live_source as eeg_live_source

try:
    from app.reporting import export_lab_report
    import app.reporting as reporting
except Exception:
    export_lab_report = None
    reporting = None

SYNTHETIC_SOURCE = "Generar EEG sintético"
CSV_SOURCE = "Cargar EEG desde CSV"
# T6.1 (2026-11-19): vigilia con arousal simulada (alfa reducido + beta), la que da un BAR dentro del rango de la
# fuente de la regla BAR; «Beta (activo)» es una sola banda y su BAR (≈ 100) pasa el techo de la regla.
AROUSAL_PATTERN = "Vigilia con arousal (alfa y beta)"

BASE_PATTERNS = [
    "Alfa (relajado)",
    AROUSAL_PATTERN,
    "Beta (activo)",
    "Theta (sueño ligero)",
    "Delta (sueño profundo)",
    "Huso de sueño",
    "Crisis (espigas)",
    "Artefacto (parpadeo)",
]
PATTERN_MAP = {
    "Alfa (relajado)": "alpha",
    AROUSAL_PATTERN: "awake_arousal",
    "Beta (activo)": "beta",
    "Theta (sueño ligero)": "theta",
    "Delta (sueño profundo)": "delta",
    "Huso de sueño": "sleep_spindle",
    "Crisis (espigas)": "seizure",
    "Artefacto (parpadeo)": "artifact",
}
if mu_erd_panel is not None:
    PATTERN_MAP[mu_erd_panel.MOTOR_IMAGERY_LABEL] = "motor_imagery"
    PATTERN_MAP[engagement_panel.ENGAGEMENT_TASK_LABEL] = "engagement_task"


def load_eeg_csv(uploaded_file):
    raw = uploaded_file.getvalue().decode('utf-8', errors='replace')
    text = io.StringIO(raw)
    try:
        data = np.genfromtxt(text, delimiter=',', names=True, dtype=float, invalid_raise=False)
    except ValueError:
        text.seek(0)
        data = np.genfromtxt(text, delimiter=',', dtype=float)

    result = {}
    time = None
    if data is None or (hasattr(data, 'size') and data.size == 0):
        return result, np.array([])

    if hasattr(data, 'dtype') and data.dtype.names is not None:
        names = list(data.dtype.names)
        time_keys = [name for name in names if name.lower() in ('time', 't', 'timestamp', 'ts')]
        if time_keys:
            time = np.asarray(data[time_keys[0]], dtype=float)
        else:
            first_name = names[0]
            time = np.arange(len(data[first_name]), dtype=float)
        for name in names:
            if name.lower() in ('time', 't', 'timestamp', 'ts'):
                continue
            result[name] = np.asarray(data[name], dtype=float)
    elif isinstance(data, np.ndarray):
        if data.ndim == 1:
            time = np.arange(data.shape[0], dtype=float)
            result['EEG1'] = data
        else:
            time = np.arange(data.shape[0], dtype=float)
            for idx in range(min(data.shape[1], 8)):
                result[f'EEG{idx + 1}'] = np.asarray(data[:, idx], dtype=float)

    if time is None and result:
        time = np.arange(len(next(iter(result.values()))), dtype=float)

    result['time'] = time
    return result, time


@dataclass
class EegSeries:
    eeg_data: Any
    time: Any
    fs: float
    data_source: str
    signal_source: str
    channels: int
    live: Any = None
    hardware_source: bool = False
    interpretation_applies: bool = True
    motor_event: Any = None
    engagement_event: Any = None
    cards: List[Tuple[str, Any]] = field(default_factory=list)


def fuente(ctx: InstrumentContext) -> Optional[EegSeries]:
    """La señal del análisis (sintética, CSV o, en la página, en vivo), o `None` si el motor no cargó."""
    if Eeg_import_error is not None or EegSignalGenerator is None:
        render_error_state("El módulo de generación/análisis de EEG no se ha podido cargar.", exception=Eeg_import_error)
        return None
    panel = ctx.panel
    k = ctx.auto_key
    panel.markdown("### Parámetros de generación")
    patterns = list(BASE_PATTERNS)
    # Revisión final de la T4: en una estación solo la señal sintética. Un CSV se guardaba al paciente como simulación
    # sin saber de quién viene (el ECG y el EMG ya lo bloquean con `CSV_SAVE_BLOCKER`); la página lo sigue ofreciendo.
    sources = [SYNTHETIC_SOURCE]
    if not ctx.in_station:
        patterns += [mu_erd_panel.MOTOR_IMAGERY_LABEL, engagement_panel.ENGAGEMENT_TASK_LABEL]
        sources += [CSV_SOURCE, eeg_live_source.SOURCE_LABEL]
    pattern = panel.selectbox("Patrón EEG", patterns, key=k("eeg_pattern"))
    channels = panel.selectbox("Número de canales", [2, 3, 4], index=2, key=k("eeg_channels"))

    signal_source = panel.radio("Origen de datos", sources, key=k("eeg_source"))
    hardware_source = signal_source == eeg_live_source.SOURCE_LABEL
    # Con EEG real (CSV o en vivo) la banda dominante no se traduce a un estado (`live_source.REAL_EEG_NOTE`).
    interpretation_applies = signal_source == SYNTHETIC_SOURCE

    duration = panel.slider("Duración (segundos)", min_value=10, max_value=120, value=30, step=10, key=k("eeg_duration"))
    fs = panel.selectbox("Frecuencia de muestreo (Hz)", [128, 256, 512], index=1, key=k("eeg_fs"))
    noise = panel.slider("Nivel de ruido de fondo", min_value=0.0, max_value=0.5, value=0.18, step=0.02,
                         key=k("eeg_noise"))

    # Los paneles de ERD y Engagement comparan el detector contra el evento que inyecta el generador; con señal en
    # vivo no hay evento inyectado, así que no se ofrecen (2026-11-14). En una estación sus patrones no se ofrecen.
    motor_event = None if (hardware_source or ctx.in_station) else mu_erd_panel.render_mu_erd_sidebar(pattern, duration)
    engagement_event = (None if (hardware_source or ctx.in_station)
                        else engagement_panel.render_engagement_sidebar(pattern, duration))

    uploaded_file = None
    live = None
    if signal_source == CSV_SOURCE:
        uploaded_file = panel.file_uploader(
            "Sube un archivo CSV de EEG",
            type=['csv'],
            help="Las columnas pueden incluir datos de EEG y una columna de tiempo opcional.",
            key=k("eeg_csv"),
        )
        if uploaded_file is not None:
            panel.success("Archivo EEG cargado correctamente.")
        else:
            panel.info("Cargue un CSV para visualizar datos reales de EEG.")
    elif hardware_source:
        live = eeg_live_source.render_live_source(duration)    # None sin señal en vivo: no hay respaldo sintético

    panel.markdown("---")
    panel.markdown("### Configuración Avanzada")

    if signal_source == SYNTHETIC_SOURCE:
        panel.markdown("### Síntesis EEG")
        panel.write("Se generará una señal EEG de laboratorio con el patrón seleccionado.")
    elif hardware_source:
        panel.markdown("### EEG en vivo")
        panel.write("El análisis usa los últimos segundos del equipo conectado (control «Duración»). Sin señal en vivo no se analiza nada.")
    else:
        panel.markdown("### EEG desde CSV")
        panel.write("El análisis usará los datos cargados desde el archivo CSV.")

    synthetic_params = EegPattern(
        pattern_type=PATTERN_MAP[pattern],
        duration=duration,
        fs=fs,
        amplitude=40.0,
        noise_level=noise,
        channels=channels,
        motor_event=motor_event,
        engagement_event=engagement_event,
    )

    data_source = "Sintético"
    if signal_source == CSV_SOURCE and uploaded_file is not None:
        eeg_data, time = load_eeg_csv(uploaded_file)
        data_source = "CSV cargado"
        if len(time) > 1:
            fs = float(round(1.0 / np.median(np.diff(time)), 2))
        if not eeg_data or 'time' not in eeg_data:
            eeg_data = {}
            time = np.array([])
            data_source = "Error de carga CSV"
    elif hardware_source:
        data_source, eeg_data, time = "Hardware en vivo: sin señal", {}, np.array([])
        if live is not None:
            eeg_data, time, fs, data_source = live.eeg, live.time, live.fs, live.label
    else:
        eeg_data, time = EegSignalGenerator(sampling_rate=fs).generate_eeg(synthetic_params)

    return EegSeries(eeg_data, time, fs, data_source, signal_source, channels, live, hardware_source,
                     interpretation_applies, motor_event, engagement_event)


def senales(ctx: InstrumentContext, s: EegSeries) -> List[Tuple[str, Any]]:
    """El trazo y la potencia de banda por canal; devuelve `(canal, resultado)` de cada canal analizado."""
    analyzer = EegAnalyzer(fs=s.fs)
    analysis_cards = []    # sin canales (fuente en vivo sin señal, CSV vacío) la columna de métricas no tiene qué leer
    eeg_data, time, fs = s.eeg_data, s.time, s.fs
    st.markdown(f"## {ctx.deco('📈')}Señales EEG")
    st.markdown(f"**Fuente de datos:** {s.data_source}  ")
    if s.data_source == "CSV cargado":
        st.markdown(f"**Frecuencia de muestreo estimada:** {fs:.2f} Hz")
    elif s.live is not None:
        st.markdown(f"**Muestreo del equipo:** {fs:g} Hz · últimos {len(time) / fs:.0f} s recibidos")

    lead_names = [key for key in eeg_data.keys() if key != 'time']
    display_leads = lead_names[:s.channels] if s.signal_source == CSV_SOURCE else lead_names
    display_rows = max(len(display_leads), 1)

    if len(display_leads) == 0:
        st.warning("No hay datos EEG válidos." + ("" if s.hardware_source else " Cargue un archivo CSV o genere una señal sintética."))
    else:
        fig = make_subplots(rows=display_rows, cols=1, shared_xaxes=True, vertical_spacing=0.06)
        for idx, lead in enumerate(display_leads, start=1):
            fig.add_trace(
                go.Scatter(x=time, y=eeg_data[lead], name=lead, line=dict(width=1.5)),
                row=idx, col=1
            )
            fig.update_yaxes(title_text=lead, row=idx, col=1)
            fig.update_yaxes(showgrid=True, gridcolor=PALETTE.GRID, gridwidth=1, row=idx, col=1)
        fig.update_xaxes(title_text='Tiempo (s)', row=display_rows, col=1)
        fig.update_xaxes(showgrid=True, gridcolor=PALETTE.GRID, gridwidth=1, row=display_rows, col=1)
        fig.update_layout(height=250 * display_rows, template='plotly_dark', paper_bgcolor=PALETTE.BACKGROUND, plot_bgcolor=PALETTE.BACKGROUND, font=dict(color=PALETTE.TEXT))
        st.plotly_chart(fig, use_container_width=True, key=ctx.auto_key("eeg_chart"))

        # Tanda 2 de la fase 1: el detalle por canal, a demanda (el cálculo no cambia).
        with st.expander(f"{ctx.deco('🧠')}Análisis de potencia de banda por canal", expanded=False):
            st.markdown(f"## {ctx.deco('🧠')}Análisis de Potencia de Banda")
            analysis_cards = []
            for lead in display_leads:
                result = analyzer.analyze(eeg_data[lead])
                analysis_cards.append((lead, result))
                st.markdown(f"### Canal {lead}")
                # Arco 2A: `result.available=False` (degradación tipo-PLV) deja `summary=None`/`band_power={}` --
                # mostrar el motivo en vez de `.write(None)` o un KeyError sobre un dict vacío.
                if not result.available:
                    st.caption(f"{ctx.deco('⚠️')}{result.reason}")
                    continue
                st.write(eeg_live_source.channel_summary(result, s.interpretation_applies))
                band_table = {
                    'Delta': f"{result.band_power['delta']:.2f}",
                    'Theta': f"{result.band_power['theta']:.2f}",
                    'Alfa': f"{result.band_power['alpha']:.2f}",
                    'Beta': f"{result.band_power['beta']:.2f}",
                    'Gamma': f"{result.band_power['gamma']:.2f}",
                }
                st.write(band_table)

        if s.motor_event is not None:
            mu_erd_panel.render_mu_erd_panel(eeg_data[display_leads[0]], display_leads[0], fs, time, s.motor_event)
        if s.engagement_event is not None:
            engagement_panel.render_engagement_panel(eeg_data[display_leads[0]], display_leads[0], fs, s.engagement_event)
    s.cards = analysis_cards
    return analysis_cards


def _cls(ctx: InstrumentContext, classification):
    """En una estación (sin emoji), la clasificación lleva la palabra «Clasificación:» en lugar de su emoji de color;
    el nivel y la etiqueta (y el color del borde) no cambian. En la página, tal cual."""
    if classification is None or not ctx.in_station:
        return classification
    level, label, _badge = classification
    return (level, label, "Clasificación:")


def metricas(ctx: InstrumentContext, s: EegSeries):
    """Banda dominante, clasificación y DAR/TBR/BAR con su cita (y, en la página, el informe exportable). Devuelve el
    resultado del primer canal, el que se guarda (o `None`)."""
    analysis_cards = s.cards
    st.markdown(f"## {ctx.deco('📊')}Métricas y Clasificación")
    overall = analysis_cards[0][1] if analysis_cards else None
    # Arco 2A (2026-09-11): degradación tipo-PLV -- `overall.available` puede ser `False` (rechazo de artefactos dejó
    # menos de `MIN_CLEAN_EEG_DURATION_S` de señal limpia). Entonces `dominant_band`/`classification` son `None`.
    if overall is not None and not overall.available:
        st.info(f"Canal {analysis_cards[0][0]}: {overall.reason}")
    elif overall is not None:
        # `dominant_band`/`classification`: cálculo real de `EegAnalyzer` sin cita clínica externa -- HEURISTIC.
        render_metric_card(
            "Banda dominante", band_label_es(overall.dominant_band),
            provenance=BADGES.HEURISTIC,
        )
        if s.interpretation_applies:
            render_metric_card("Clasificación", overall.classification, provenance=BADGES.HEURISTIC)
        else:
            render_metric_card("Clasificación", None, unavailable_reason=eeg_live_source.REAL_EEG_NOTE)
        shown_findings = eeg_live_source.visible_findings(overall.findings, s.interpretation_applies)
        with st.expander("Interpretación y hallazgos: DAR, TBR, BAR y potencias", expanded=False):
            st.markdown("### Interpretación Clínica")
            st.write(
                "Este laboratorio simula ondas EEG típicas y las clasifica en patrones de alerta, relajación y sueño."
                if s.interpretation_applies else
                "Con EEG real se muestran las mediciones (potencias, cocientes con su fuente) sin traducirlas a un estado."
            )
            st.markdown("### Hallazgos clínicos EEG")
            # Consolidación Visual Tanda 3 (2026-09-21): DAR/TBR/BAR con `render_metric_card` (misma expresión que el
            # informe exportado, cero cambio de valor); las tres claves de ratio se excluyen del loop genérico.
            _ratio_keys = {'Delta/Alpha Ratio (DAR)', 'Theta/Beta Ratio (TBR)', 'Beta/Alpha Ratio (BAR)'}
            if classify_dar is not None:
                if overall.dar is not None:
                    render_metric_card(
                        'DAR (Delta/Alfa)', f'{overall.dar:.2f}',
                        classification=_cls(ctx, classify_dar(overall.dar)), citation=DAR_CITATION,
                    )
                else:
                    render_metric_card(
                        'DAR (Delta/Alfa)', None,
                        unavailable_reason='indefinido -- sin ritmo alfa medible (alpha_power ~0)',
                    )
            if classify_tbr is not None:
                if overall.tbr is not None:
                    render_metric_card(
                        'TBR (Theta/Beta)', f'{overall.tbr:.2f}',
                        classification=_cls(ctx, classify_tbr(overall.tbr)), citation=TBR_CITATION,
                    )
                else:
                    render_metric_card(
                        'TBR (Theta/Beta)', None,
                        unavailable_reason='indefinido -- sin ritmo beta medible (beta_power ~0)',
                    )
            # BAR: sin `classify_bar()` a propósito (Schutter 2006 no establece zonas clínicas de 3 niveles):
            # `GRAMMAR_NEUTRAL_STATE` sin `classification=`, el marco queda NEUTRAL.
            if overall.bar is not None:
                render_metric_card(
                    'BAR (Beta/Alfa)', f'{overall.bar:.2f}',
                    provenance=BADGES.CLINICAL, grammar=GRAMMAR_NEUTRAL_STATE, citation=BAR_CITATION,
                )
            else:
                render_metric_card(
                    'BAR (Beta/Alfa)', None,
                    unavailable_reason='indefinido -- sin ritmo alfa medible (alpha_power ~0)',
                )
            for key, value in shown_findings.items():
                if key in _ratio_keys:
                    continue
                shown = band_label_es(value) if key == "Dominant Band" else value
                st.write(f"**{FINDING_LABELS_ES.get(key, key)}:** {shown}")

        # El informe exportable escribe un archivo en la computadora: solo en la página del laboratorio.
        if not ctx.in_station and export_lab_report is not None and st.button("Exportar informe EEG"):
        # Se lee de `app.reporting` al exportar (como cuando la página se ejecutaba con runpy en cada pasada): así las
        # pruebas pueden redirigir el directorio del informe.
            _export_report(s, overall, shown_findings)
    return overall


def _export_report(s: EegSeries, overall, shown_findings) -> None:
    fs = s.fs
    metrics = {
        'data_source': s.data_source,
        'fs': fs,
        'dominant_band': overall.dominant_band,
        'classification': overall.classification if s.interpretation_applies else 'no se interpreta (EEG real)',
    }
    for bname, val in overall.band_power.items():
        metrics[f'band_{bname}'] = float(val)
    notes = f"EEG Neuro Lab autogenerated report. {shown_findings.get('Clinical Note', '')}"
    findings = shown_findings

    # Consolidación Visual Tanda 2 (2026-09-21): cada valor del informe sale de la MISMA fuente que la app viva
    # (`resolve_metric_card()`); ninguno se fabrica: si un cociente es indefinido o χ degrada, va el motivo.
    honesty_cards = []
    if classify_dar is not None:
        if overall.dar is not None:
            honesty_cards.append(resolve_metric_card(
                'DAR (Delta/Alfa)', f'{overall.dar:.2f}',
                classification=classify_dar(overall.dar), citation=DAR_CITATION,
            ))
        else:
            honesty_cards.append(resolve_metric_card(
                'DAR (Delta/Alfa)', None,
                unavailable_reason='indefinido -- sin ritmo alfa medible (alpha_power ~0)',
            ))
    if classify_tbr is not None:
        if overall.tbr is not None:
            honesty_cards.append(resolve_metric_card(
                'TBR (Theta/Beta)', f'{overall.tbr:.2f}',
                classification=classify_tbr(overall.tbr), citation=TBR_CITATION,
            ))
        else:
            honesty_cards.append(resolve_metric_card(
                'TBR (Theta/Beta)', None,
                unavailable_reason='indefinido -- sin ritmo beta medible (beta_power ~0)',
            ))
    if overall.bar is not None:
        honesty_cards.append(resolve_metric_card(
            'BAR (Beta/Alfa)', f'{overall.bar:.2f}',
            provenance=BADGES.CLINICAL, grammar=GRAMMAR_NEUTRAL_STATE, citation=BAR_CITATION,
        ))
    else:
        honesty_cards.append(resolve_metric_card(
            'BAR (Beta/Alfa)', None,
            unavailable_reason='indefinido -- sin ritmo alfa medible (alpha_power ~0)',
        ))
    # χ: mismo motor y mismas entradas reales que el guardado al gemelo; sin `fooof`, χ no se agrega.
    if fit_aperiodic_component is not None and overall.psd_freqs is not None:
        chi_result = fit_aperiodic_component(
            overall.psd_freqs, overall.psd_power,
            clean_window_count=overall.clean_window_count, bandpass_fs=fs,
        )
        if chi_result.available:
            honesty_cards.append(resolve_metric_card(
                'χ (aperiódico)', f'{chi_result.exponent:.2f}',
                classification=classify_chi(chi_result.exponent), grammar=GRAMMAR_NEUTRAL_STATE,
                citation=CHI_CITATION,
            ))
        else:
            honesty_cards.append(resolve_metric_card('χ (aperiódico)', None, unavailable_reason=chi_result.reason))

    tmpdir = tempfile.mkdtemp(prefix='bsp_report_')
    try:
        bp_path = os.path.join(tmpdir, 'eeg_band_power.png')
        try:
            labels = list(overall.band_power.keys())
            values = [float(overall.band_power[k]) for k in labels]
            reporting._save_bar_plot(bp_path, labels, values, title='Potencia de banda EEG')
        except Exception:
            pass
        image_paths = []
        if os.path.exists(bp_path):
            image_paths.append(('Potencia de banda EEG', bp_path))
        # Sin `validation=`: firmado como mudo por el experto (contenedor mixto); los `honesty_cards` hacen el
        # trabajo fino también en el export.
        path = reporting.export_lab_report(
            'EEG Neuro Lab', metrics, notes=notes, findings=findings, image_paths=image_paths,
            honesty_cards=honesty_cards,
        )
    finally:
        try:
            shutil.rmtree(tmpdir)
        except Exception:
            pass
    st.success(f"Informe exportado: {path}")


def guardar(ctx: InstrumentContext, s: EegSeries, overall) -> InstrumentResult:
    """Capa 5A, Sub-fase 1 (2026-08-30): botón explícito, nunca automático. Escribe las 5 potencias de banda reales
    del primer canal (+ χ si pasa su gate) y, por el builder, los cocientes BAR/DAR/TBR con su cita. Procedencia
    `SENSOR_REAL` solo con un equipo real transmitiendo (`live_source.twin_provenance`); lo demás, `SIMULACION` con
    el origen en `source_detail`. Un canal en vivo con avisos de calidad no se guarda (`save_blocker`).

    Fase 0 (2026-11-13, Art. I): el organismo ya no deriva NADA del cerebro (health_score/risk_score con defaults,
    mental_workload = beta_power con otro nombre, stress_perception, attention...: todos retirados). Al UPS llegan
    exactamente las 5 potencias de banda, los cocientes BAR/DAR/TBR (identidades aritméticas con cita) y, si pasa su
    gate, chi.

    T4 (2026-11-18): antes vivía dentro de `page_content.py`. Con `PAGE`, la clave del botón es la de siempre
    (`eeg_lab_save_to_ups`). `saved_snapshot_id` dice qué snapshot se escribió en este rerun (o `None`)."""
    from domain.physiology.state import from_digital_twin_organism, save_state
    from domain.physiology.coupling import VALIDATED_RULES, CouplingScenarioBlockedError, apply_couplings
    from app.engines.digital_twin_organism import DigitalTwinOrganism
    from app.utils.patient_session import get_active_patient_id, get_active_session_factory

    if overall is None or not overall.available:     # como antes: sin análisis válido, la sección no se dibuja
        return InstrumentResult()
    live, fs, data_source = s.live, s.fs, s.data_source
    st.markdown("---")
    st.markdown(f"#### {ctx.deco('🔗')}Guardar estado al gemelo")
    eeg_lab_channel = s.cards[0][0]
    twin_prov, twin_note = eeg_live_source.twin_provenance(live)
    st.caption(
        f"Escribe la potencia de banda real (delta/theta/alpha/beta/gamma) del canal "
        f"**{eeg_lab_channel}** al estado fisiológico unificado (UPS) del paciente activo: el gemelo digital la "
        f"mostrará con su procedencia la próxima vez que lo abras. {twin_note}"
    )
    if not st.button(f"{ctx.deco('💾')}Guardar estado al gemelo", key=ctx.k("eeg_lab_save_to_ups")):
        return InstrumentResult()
    blocker = eeg_live_source.save_blocker(live, eeg_lab_channel)
    # Arco 2A (2026-09-11): `overall` puede llegar `available=False`: el botón no finge guardar y NO llama a
    # `update_from_sensors()` (el gate de `_neurological_state()` deja el dominio neuro vacío).
    if not overall.available:
        st.info(
            f"Sin señal EEG limpia suficiente para guardar al gemelo -- {overall.reason}. "
            "No hay banda de potencia real que persistir."
        )
        return InstrumentResult()
    if blocker:
        st.warning(f"{ctx.deco('⛔')}No se guarda al gemelo: {blocker}")
        return InstrumentResult()
    session_factory = get_active_session_factory()
    patient_id = get_active_patient_id()

    # Arco 2C (2026-09-14): χ aperiódico, aditivo, sobre el MISMO PSD de `overall`; si degrada, la clave
    # `chi_aperiodic` no se agrega y el resto del guardado sigue intacto. `bandpass_fs=fs`: corrige la distorsión del
    # bandpass de `preprocess_eeg()` (sin ella χ queda sesgado ~+0.46, ver `spectral_model.py`).
    chi_result = None
    if fit_aperiodic_component is not None and overall.psd_freqs is not None:
        chi_result = fit_aperiodic_component(
            overall.psd_freqs, overall.psd_power,
            clean_window_count=overall.clean_window_count,
            bandpass_fs=fs,
        )

    eeg_sensors = {
        "delta_power": float(overall.band_power["delta"]),
        "theta_power": float(overall.band_power["theta"]),
        "alpha_power": float(overall.band_power["alpha"]),
        "beta_power": float(overall.band_power["beta"]),
        "gamma_power": float(overall.band_power["gamma"]),
    }
    if chi_result is not None and chi_result.available:
        eeg_sensors["chi_aperiodic"] = float(chi_result.exponent)

    eeg_organism = DigitalTwinOrganism()
    eeg_organism.update_from_sensors({"eeg": eeg_sensors})
    eeg_ups_state = from_digital_twin_organism(
        eeg_organism, patient_id, provenance=twin_prov,
        source_detail=(f"eeg_neuro_lab:canal={eeg_lab_channel}:banda_dominante={overall.dominant_band}"
                       f":fuente={data_source}"),
    )
    with session_factory() as eeg_ups_session:
        eeg_snapshot_id = save_state(eeg_ups_session, eeg_ups_state)

        # Acoplamientos Sub-fase B (2026-09-06): tras persistir se evalúa el catálogo validado
        # (`AROUSAL_TAQUICARDIA_BAR`). `scenario=None`: el EEG es un escritor neuro sin FC correlacionada. Este
        # snapshot no trae FC: hoy es un no-op honesto aquí (la Unidad Cerebro llama al compositor en su cierre).
        try:
            coupled = apply_couplings(
                eeg_ups_session, eeg_snapshot_id, VALIDATED_RULES, scenario=None
            )
        except CouplingScenarioBlockedError:
            coupled = []  # inalcanzable con scenario=None; defensivo
        bar_desc = eeg_ups_state.neurological.get("bar")

    st.success(f"Estado guardado al gemelo -- snapshot: {eeg_snapshot_id}")
    st.caption(f"neurological: {len(eeg_ups_state.neurological.descriptors)} descriptores")
    if bar_desc is not None:
        render_metric_card(
            'BAR (Beta/Alfa)', f'{bar_desc.value:.2f}',
            provenance=BADGES.CLINICAL, grammar=GRAMMAR_NEUTRAL_STATE, citation=BAR_CITATION,
        )
    else:
        render_metric_card(
            'BAR (Beta/Alfa)', None,
            unavailable_reason='indefinido (sin ritmo alfa)',
        )
    if chi_result is not None and chi_result.available:
        render_metric_card(
            'χ (aperiódico)', f'{chi_result.exponent:.2f}',
            classification=_cls(ctx, classify_chi(chi_result.exponent)), grammar=GRAMMAR_NEUTRAL_STATE,
            citation=CHI_CITATION,
        )
    elif chi_result is not None:
        render_metric_card('χ (aperiódico)', None, unavailable_reason=chi_result.reason)
    if coupled:
        ac = coupled[0]
        st.caption(
            f"{ctx.deco('🔗')}Acoplamiento **{ac.rule_id}**: FC medida {ac.base_value:.0f} -> "
            f"FC acoplada **{ac.coupled_value:.0f} lpm** (DERIVADO_ACOPLAMIENTO, "
            f"confianza {ac.confidence:.2f}) -- BAR observado {ac.observed_value:.2f}"
        )
    else:
        st.caption(
            f"{ctx.deco('🔗')}Acoplamiento AROUSAL_TAQUICARDIA_BAR: sin FC medida en este snapshot, "
            "nada que modular (se aplicaría si el paciente tuviera FC medida y un BAR mayor que 1.8 y no mayor que su "
            "techo de 3.0, en un EEG de vigilia)."
        )
    st.caption(
        f"cardiovascular: {len(eeg_ups_state.cardiovascular.descriptors)} descriptores "
        "(vacío esperado -- este laboratorio no envía dato cardíaco) · "
        f"respiratory: {len(eeg_ups_state.respiratory.descriptors)} descriptores "
        "(vacío esperado -- este laboratorio no envía dato respiratorio)"
    )
    return InstrumentResult(saved_snapshot_id=eeg_snapshot_id)
