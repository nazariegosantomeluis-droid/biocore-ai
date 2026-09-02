"""
Visualization Module for ECG and HRV Analysis

Professional clinical ECG and HRV plotting utilities.
This module is designed for research-quality, medical-style
visualization and educational ECG interpretation.
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass

try:
    import matplotlib as mpl
    mpl.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.gridspec import GridSpec
    from matplotlib.patches import Rectangle
    from matplotlib.ticker import MultipleLocator, FuncFormatter
    _MATPLOTLIB_AVAILABLE = True
    _MATPLOTLIB_IMPORT_ERROR = None
except Exception as e:
    mpl = None
    plt = None
    GridSpec = None
    Rectangle = None
    MultipleLocator = None
    FuncFormatter = None
    _MATPLOTLIB_AVAILABLE = False
    _MATPLOTLIB_IMPORT_ERROR = e


# ----------------------------------------------------------------------------
# Global style configuration for clinical ECG visualization
# ----------------------------------------------------------------------------
if _MATPLOTLIB_AVAILABLE:
    mpl.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['DejaVu Sans', 'Arial', 'Liberation Sans'],
    'font.size': 11,
    'axes.titlesize': 16,
    'axes.labelsize': 12,
    'axes.linewidth': 1.0,
    'lines.linewidth': 1.8,
    'lines.antialiased': True,
    'figure.dpi': 200,
    'savefig.dpi': 300,
    'legend.frameon': False,
    'legend.fontsize': 11,
    'xtick.direction': 'out',
    'ytick.direction': 'out',
    'xtick.color': '#333333',
    'ytick.color': '#333333',
})


@dataclass(frozen=True)
class _ECGStyle:
    paper_background: str = '#fff6f0'
    small_grid_color: str = '#f9d5d3'
    large_grid_color: str = '#e07a5f'
    signal_color: str = '#111111'
    peak_marker: str = '#d62828'
    axis_color: str = '#333333'
    annotation_color: str = '#1f3b73'
    secondary_color: str = '#2a6f97'
    neutral_color: str = '#444444'
    hz_band_alpha: float = 0.18
    grid_small_linewidth: float = 0.45
    grid_large_linewidth: float = 0.95


STYLE = _ECGStyle()


def _smooth_signal(signal: np.ndarray, window: int = 11) -> np.ndarray:
    """Apply a light smoothing filter to preserve ECG morphology."""
    if window < 3 or window % 2 == 0:
        window = 11
    kernel = np.ones(window, dtype=float) / window
    return np.convolve(signal, kernel, mode='same')


def _format_seconds(x, pos):
    return f'{x:.1f}'


def _configure_ecg_axes(ax, duration: float, amplitude_range: tuple[float, float], fs: float) -> None:
    """Apply medical ECG grid and axis styling."""
    ax.set_facecolor(STYLE.paper_background)
    ax.set_xlim(0, duration)
    ax.set_ylim(amplitude_range)

    # ECG paper style: 1 mm = 0.04 s horizontally at 25 mm/s
    ax.set_xticks(np.arange(0, duration + 0.001, 0.04), minor=True)
    ax.set_xticks(np.arange(0, duration + 0.001, 0.20), minor=False)
    ax.set_yticks(np.arange(amplitude_range[0], amplitude_range[1] + 0.001, 0.1), minor=True)
    ax.set_yticks(np.arange(amplitude_range[0], amplitude_range[1] + 0.001, 0.5), minor=False)

    ax.grid(which='minor', color=STYLE.small_grid_color, linewidth=STYLE.grid_small_linewidth)
    ax.grid(which='major', color=STYLE.large_grid_color, linewidth=STYLE.grid_large_linewidth)

    ax.set_axisbelow(True)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color(STYLE.axis_color)
    ax.spines['bottom'].set_color(STYLE.axis_color)

    ax.xaxis.set_major_formatter(FuncFormatter(_format_seconds))
    ax.tick_params(which='major', length=6, color=STYLE.axis_color)
    ax.tick_params(which='minor', length=3, color=STYLE.axis_color)


def _annotate_ecg_components(
    ax,
    time: np.ndarray,
    signal: np.ndarray,
    peaks: np.ndarray | None,
    fs: float,
    teaching_mode: bool = False,
    show_annotations: bool = True
) -> None:
    """Annotate P, QRS, T regions and RR interval markers."""
    if peaks is None or len(peaks) == 0 or not show_annotations:
        return

    peak_idx = peaks[0]
    if peak_idx <= 0 or peak_idx >= len(signal) - 1:
        return

    r_time = time[peak_idx]
    q_start = max(0.0, r_time - 0.12)
    t_end = min(time[-1], r_time + 0.36)
    baseline = np.median(signal)
    annotation_y = np.max(signal) * 0.65

    ax.annotate(
        'QRS',
        xy=(r_time, signal[peak_idx]),
        xytext=(r_time + 0.4, annotation_y),
        color=STYLE.annotation_color,
        arrowprops=dict(arrowstyle='-|>', color=STYLE.annotation_color, lw=1.2),
        fontsize=11,
        weight='semibold'
    )
    ax.annotate(
        'P',
        xy=(q_start, baseline),
        xytext=(q_start - 0.25, annotation_y - 0.2),
        color=STYLE.annotation_color,
        arrowprops=dict(arrowstyle='->', color=STYLE.annotation_color, lw=1.0),
        fontsize=10
    )
    ax.annotate(
        'T',
        xy=(t_end, baseline),
        xytext=(t_end + 0.05, annotation_y - 0.20),
        color=STYLE.annotation_color,
        arrowprops=dict(arrowstyle='->', color=STYLE.annotation_color, lw=1.0),
        fontsize=10
    )

    if teaching_mode:
        annotation_box = (
            'Modo educativo:\n'
            'P = despolarización auricular\n'
            'QRS = despolarización ventricular\n'
            'T = repolarización ventricular'
        )
        ax.text(
            0.02,
            0.95,
            annotation_box,
            transform=ax.transAxes,
            fontsize=10,
            color=STYLE.neutral_color,
            bbox=dict(facecolor='white', alpha=0.8, edgecolor='none')
        )


def _add_zoom_panel(fig, time, signal, fs, duration: float = 5.0) -> None:
    """Add a zoomed-in ECG segment to the figure."""
    zoom_duration = min(duration, time[-1])
    end_sample = int(zoom_duration * fs)
    zoom_time = time[:end_sample]
    zoom_signal = signal[:end_sample]

    inset = fig.add_axes([0.60, 0.58, 0.35, 0.30], facecolor=STYLE.paper_background)
    _configure_ecg_axes(inset, zoom_duration, (zoom_signal.min() - 0.5, zoom_signal.max() + 0.5), fs)
    inset.plot(zoom_time, zoom_signal, color=STYLE.signal_color, linewidth=1.8)
    inset.set_title('Zoom 5 s', fontsize=12, fontweight='bold')
    inset.set_xlabel('Tiempo (s)', fontsize=10)
    inset.set_ylabel('mV', fontsize=10)
    inset.tick_params(labelsize=8)


def _build_signal_range(signal: np.ndarray) -> tuple[float, float]:
    """Compute a symmetric amplitude range for ECG display."""
    peak = max(abs(signal.min()), abs(signal.max()))
    padding = max(0.5, peak * 0.20)
    return (-peak - padding, peak + padding)


def plot_ecg_signal(
    signal: np.ndarray,
    fs: float,
    peaks: np.ndarray | None = None,
    filtered_signal: np.ndarray | None = None,
    figsize: tuple[float, float] = (16, 9),
    zoom_seconds: float = 5.0,
    teaching_mode: bool = False,
    show_annotations: bool = True,
    max_display_seconds: float = 10.0
):
    """
    Generate a professional clinical ECG visualization.

    Parameters
    ----------
    signal : ndarray
        Señal ECG original.
    fs : float
        Frecuencia de muestreo en Hz.
    peaks : ndarray, optional
        Índices de picos R detectados.
    filtered_signal : ndarray, optional
        Señal filtrada para comparación.
    figsize : tuple, optional
        Tamaño de la figura.
    zoom_seconds : float, optional
        Duración de la vista ampliada.
    teaching_mode : bool, optional
        Activar anotaciones educativas.
    show_annotations : bool, optional
        Mostrar etiquetas de P/QRS/T.
    max_display_seconds : float, optional
        Mostrar solo los primeros segundos si la señal es larga.

    Returns
    -------
    fig : matplotlib.figure.Figure
        Figura de ECG.
    """
    time = np.arange(len(signal)) / fs
    display_duration = min(max_display_seconds, time[-1])
    display_samples = int(display_duration * fs)

    ecg_signal = filtered_signal[:display_samples] if filtered_signal is not None else signal[:display_samples]
    reference_signal = signal[:display_samples]
    display_time = time[:display_samples]

    fig = plt.figure(figsize=figsize)
    main_ax = fig.add_subplot(1, 1, 1)
    _configure_ecg_axes(main_ax, display_duration, _build_signal_range(ecg_signal), fs)

    if filtered_signal is not None:
        main_ax.plot(
            display_time,
            reference_signal,
            color='#888888',
            linewidth=1.0,
            alpha=0.5,
            label='ECG crudo'
        )

    main_ax.plot(
        display_time,
        ecg_signal,
        color=STYLE.signal_color,
        linewidth=2.2,
        solid_capstyle='round',
        label='Señal ECG'
    )

    if peaks is not None and len(peaks) > 0:
        peak_mask = peaks < display_samples
        if peak_mask.any():
            visible_peaks = peaks[peak_mask]
            main_ax.plot(
                visible_peaks / fs,
                ecg_signal[visible_peaks],
                marker='o',
                markersize=7,
                markeredgewidth=1.3,
                markeredgecolor='white',
                markerfacecolor=STYLE.peak_marker,
                linestyle='None',
                label='Picos R'
            )

    main_ax.set_title(
        'Visualización Clínica ECG | 25 mm/s · 10 mm/mV',
        fontsize=18,
        fontweight='bold',
        color=STYLE.neutral_color,
        pad=16
    )
    main_ax.set_xlabel('Tiempo (s)', fontsize=13)
    main_ax.set_ylabel('Amplitud (mV)', fontsize=13)
    main_ax.text(
        0.02,
        0.02,
        'Monitoreo ECG simulada | Modo educativo' if teaching_mode else 'Monitoreo ECG clínico',
        transform=main_ax.transAxes,
        fontsize=10,
        color=STYLE.neutral_color,
        bbox=dict(facecolor='white', alpha=0.7, edgecolor='none')
    )

    _annotate_ecg_components(
        main_ax,
        display_time,
        ecg_signal,
        peaks[peaks < display_samples] if peaks is not None else None,
        fs,
        teaching_mode=teaching_mode,
        show_annotations=show_annotations
    )

    if display_duration >= zoom_seconds:
        _add_zoom_panel(fig, display_time, ecg_signal, fs, duration=zoom_seconds)

    main_ax.legend(loc='upper right', fontsize=11)
    fig.tight_layout(pad=1.2)
    return fig


def plot_rr_intervals(rr_intervals: np.ndarray, figsize: tuple[float, float] = (14, 8)):
    """
    Plot RR interval series and histogram with clinical style.
    """
    fig = plt.figure(figsize=figsize)
    gs = GridSpec(2, 1, height_ratios=[2, 1], figure=fig, hspace=0.28)

    ax_series = fig.add_subplot(gs[0, 0])
    ax_hist = fig.add_subplot(gs[1, 0])

    mean_rr = np.mean(rr_intervals)
    std_rr = np.std(rr_intervals)

    ax_series.plot(
        np.arange(1, len(rr_intervals) + 1),
        rr_intervals,
        color=STYLE.signal_color,
        linewidth=2.2,
        marker='o',
        markersize=6,
        markerfacecolor=STYLE.secondary_color,
        markeredgecolor='white',
        markeredgewidth=0.9
    )
    ax_series.axhline(mean_rr, color='#d62828', linestyle='--', linewidth=1.8, label=f'RR medio = {mean_rr:.3f} s')
    ax_series.fill_between(
        np.arange(1, len(rr_intervals) + 1),
        rr_intervals,
        mean_rr,
        where=rr_intervals >= mean_rr,
        facecolor=STYLE.secondary_color,
        alpha=0.12
    )

    ax_series.set_title('Variabilidad de Intervalos RR', fontsize=16, fontweight='bold')
    ax_series.set_xlabel('Número de latido', fontsize=12)
    ax_series.set_ylabel('RR (s)', fontsize=12)
    ax_series.grid(True, linestyle='--', color='#bbbbbb', alpha=0.4)
    ax_series.legend(loc='upper right')

    ax_hist.hist(
        rr_intervals,
        bins=18,
        color=STYLE.secondary_color,
        edgecolor=STYLE.axis_color,
        alpha=0.85
    )
    ax_hist.axvline(mean_rr, color='#d62828', linestyle='--', linewidth=1.6, label='RR medio')
    ax_hist.set_title('Distribución de Intervalos RR', fontsize=14, fontweight='bold')
    ax_hist.set_xlabel('RR (s)', fontsize=12)
    ax_hist.set_ylabel('Frecuencia', fontsize=12)
    ax_hist.grid(True, linestyle='--', color='#bbbbbb', alpha=0.35)
    ax_hist.legend(loc='upper right')

    fig.suptitle('Análisis Clínico de Intervalos RR', fontsize=18, fontweight='bold', y=0.98)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    return fig


def _smooth_power_spectrum(power_spectrum: np.ndarray, window: int = 11) -> np.ndarray:
    """Smooth PSD curve for publication-quality appearance."""
    if window < 3:
        window = 11
    kernel = np.ones(window, dtype=float) / window
    return np.convolve(power_spectrum, kernel, mode='same')


def plot_psd(frequencies: np.ndarray, power_spectrum: np.ndarray, figsize: tuple[float, float] = (12, 7)):
    """
    Plot power spectral density (HRV) with LF/HF shading.
    """
    smoothed = _smooth_power_spectrum(power_spectrum, window=9)
    fig, ax = plt.subplots(figsize=figsize)

    ax.semilogy(
        frequencies,
        smoothed,
        color=STYLE.signal_color,
        linewidth=2.4,
        solid_capstyle='round'
    )
    ax.fill_between(frequencies, smoothed, color='#222222', alpha=0.08)

    lf_band = (frequencies >= 0.04) & (frequencies < 0.15)
    hf_band = (frequencies >= 0.15) & (frequencies < 0.4)

    ax.fill_between(
        frequencies[lf_band],
        smoothed[lf_band],
        color='#e07a5f',
        alpha=STYLE.hz_band_alpha,
        label='LF (0.04-0.15 Hz)'
    )
    ax.fill_between(
        frequencies[hf_band],
        smoothed[hf_band],
        color='#2a6f97',
        alpha=STYLE.hz_band_alpha,
        label='HF (0.15-0.4 Hz)'
    )

    ax.set_xlim(0, 0.5)
    ax.set_ylim(bottom=max(smoothed[smoothed > 0].min() * 0.7, 1e-8))
    ax.set_xlabel('Frecuencia (Hz)', fontsize=13)
    ax.set_ylabel('Potencia (ms²/Hz)', fontsize=13)
    ax.set_title('Densidad Espectral de Potencia HRV', fontsize=18, fontweight='bold')
    ax.grid(True, which='major', linestyle='--', color='#999999', alpha=0.35)
    ax.grid(True, which='minor', linestyle=':', color='#cccccc', alpha=0.25)
    ax.legend(loc='upper right', framealpha=0.9)
    ax.tick_params(axis='x', which='minor', bottom=True)

    ax.text(
        0.02,
        0.92,
        'Este gráfico es útil para evaluación del balance autónomo y la variabilidad cardíaca.',
        transform=ax.transAxes,
        fontsize=10,
        color=STYLE.neutral_color,
        bbox=dict(facecolor='white', alpha=0.8, edgecolor='none')
    )

    fig.tight_layout(pad=1.05)
    return fig


def plot_feature_comparison(features_dict_list, labels, figsize=(14, 8)):
    """
    Compare HRV features across multiple recordings with scientific styling.
    """
    feature_names = ['BPM', 'SDNN', 'RMSSD', 'LF_HF', 'Skewness', 'Kurtosis']
    fig = plt.figure(figsize=figsize)
    gs = GridSpec(3, 2, figure=fig)

    for idx, feature in enumerate(feature_names):
        ax = fig.add_subplot(gs[idx // 2, idx % 2])
        values = [features[feature] for features in features_dict_list]

        bars = ax.bar(
            labels,
            values,
            color=[STYLE.secondary_color if v >= np.median(values) else STYLE.signal_color for v in values],
            alpha=0.85,
            edgecolor='black'
        )
        ax.set_title(f'Comparación {feature}', fontsize=13, fontweight='bold')
        ax.set_ylabel(feature, fontsize=11)
        ax.grid(True, axis='y', linestyle='--', alpha=0.25)

        if len(labels) > 2:
            ax.set_xticklabels(labels, rotation=35, ha='right')

        for bar in bars:
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.01 * max(values),
                f'{bar.get_height():.2f}',
                ha='center',
                va='bottom',
                fontsize=9
            )

    fig.suptitle('Comparación de Características HRV', fontsize=18, fontweight='bold')
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    return fig


def show_plots():
    """Display all plots."""
    # plt.show()  # Disabled: figures are saved, not displayed
