"""Clinical ECG 12-lead helpers: plotting and lead derivation helpers.

This module exposes `plot_ecg_12_leads` which accepts a mapping of lead names
(`'I','II','III','aVR','aVL','aVF','V1'..'V6'`) to numpy arrays and plots a
standard clinical 12-lead layout (3 rows x 4 columns of sequential leads plus
a full-length rhythm strip) on real ECG-paper style grid (0.04s/0.1mV minor
boxes, 0.2s/0.5mV major boxes — matches 25 mm/s, 10 mm/mV paper), using
Plotly when available and falling back to Matplotlib.

It also provides `derive_12_leads_from_3` for educational demonstration of
how limb leads relate (I, II, III, aVR, aVL, aVF) from three electrodes.
"""
from __future__ import annotations
from typing import Dict, Tuple, Optional
import numpy as np

# Standard clinical print layout: each column shows a different consecutive
# time window (a real 12-lead ECG machine only has 3-4 simultaneous
# channels, so the remaining leads are captured sequentially).
_LAYOUT_COLUMNS = [
    ['I', 'II', 'III'],
    ['aVR', 'aVL', 'aVF'],
    ['V1', 'V2', 'V3'],
    ['V4', 'V5', 'V6'],
]
_RHYTHM_LEAD = 'II'

_MAJOR_GRID_COLOR = '#e6767a'
_MINOR_GRID_COLOR = '#f7d4d6'
_PAPER_BG = '#fffafa'
_TRACE_COLOR = '#111111'


def derive_12_leads_from_3(lead_I: np.ndarray, lead_II: np.ndarray) -> Dict[str, np.ndarray]:
    """Derive limb leads III and augmented leads from I and II.

    Assumes leads are aligned and same sampling rate. Returns dict with keys
    'I','II','III','aVR','aVL','aVF'.
    """
    if lead_I.shape != lead_II.shape:
        raise ValueError('lead_I and lead_II must have same shape')
    lead_III = lead_II - lead_I
    aVR = -(lead_I + lead_II) / 2.0
    aVL = lead_I - lead_II / 2.0
    aVF = lead_II - lead_I / 2.0
    return {'I': lead_I, 'II': lead_II, 'III': lead_III, 'aVR': aVR, 'aVL': aVL, 'aVF': aVF}


def plot_ecg_12_leads(signals: Dict[str, np.ndarray], fs: int = 250, title: Optional[str] = 'ECG 12 leads') -> object:
    """Plot a standard clinical 12-lead ECG (3x4 sequential layout + rhythm strip).

    If Plotly is available, returns a plotly Figure; otherwise draws with
    Matplotlib and returns the Figure object.
    """
    try:
        return _plot_plotly(signals, fs, title)
    except Exception:
        return _plot_matplotlib(signals, fs, title)


def _plot_plotly(signals: Dict[str, np.ndarray], fs: int, title: Optional[str]):
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    n = len(next(iter(signals.values())))
    t = np.arange(n) / float(fs)
    total_duration = n / float(fs)
    seg_len = total_duration / 4.0

    subplot_titles = []
    for row in range(3):
        for col in range(4):
            subplot_titles.append(_LAYOUT_COLUMNS[col][row])
    subplot_titles.append(f'{_RHYTHM_LEAD} (tira de ritmo)')

    fig = make_subplots(
        rows=4, cols=4,
        specs=[
            [{}, {}, {}, {}],
            [{}, {}, {}, {}],
            [{}, {}, {}, {}],
            [{'colspan': 4}, None, None, None],
        ],
        row_heights=[0.22, 0.22, 0.22, 0.34],
        subplot_titles=subplot_titles,
        vertical_spacing=0.05,
        horizontal_spacing=0.03,
    )

    for col in range(4):
        window_start = col * seg_len
        window_end = window_start + seg_len
        mask = (t >= window_start) & (t < window_end)
        t_win = t[mask] - window_start
        for row in range(3):
            lead = _LAYOUT_COLUMNS[col][row]
            y = signals.get(lead, np.zeros(n))[mask]
            fig.add_trace(
                go.Scatter(x=t_win, y=y, mode='lines', name=lead,
                           line=dict(color=_TRACE_COLOR, width=1.3), showlegend=False),
                row=row + 1, col=col + 1,
            )
            _apply_ecg_grid(fig, row + 1, col + 1)

    # Full-length rhythm strip with a calibration pulse (0.2s/1mV) before t=0.
    rhythm = signals.get(_RHYTHM_LEAD, np.zeros(n))
    cal_x = [-0.28, -0.28, -0.08, -0.08, 0.0]
    cal_y = [0.0, 1.0, 1.0, 0.0, 0.0]
    fig.add_trace(
        go.Scatter(x=cal_x, y=cal_y, mode='lines', name='Calibración (1mV)',
                   line=dict(color=_TRACE_COLOR, width=1.3), showlegend=False),
        row=4, col=1,
    )
    fig.add_trace(
        go.Scatter(x=t, y=rhythm, mode='lines', name=_RHYTHM_LEAD,
                   line=dict(color=_TRACE_COLOR, width=1.3), showlegend=False),
        row=4, col=1,
    )
    _apply_ecg_grid(fig, 4, 1, x_range=[-0.4, total_duration])

    fig.update_layout(
        title=f'{title}<br><sub>25 mm/s · 10 mm/mV — cada columna es un tramo consecutivo del trazado real</sub>',
        height=780,
        plot_bgcolor=_PAPER_BG,
        paper_bgcolor='#1a1a1a',
        font=dict(color='#e5e5e5', size=10),
        margin=dict(t=90, b=40, l=40, r=20),
    )
    fig.update_annotations(font=dict(color='#e5e5e5', size=11))
    return fig


def _apply_ecg_grid(fig, row: int, col: int, x_range=None) -> None:
    axis_kwargs = dict(
        showgrid=True, gridcolor=_MAJOR_GRID_COLOR, gridwidth=1, dtick=0.2,
        minor=dict(showgrid=True, gridcolor=_MINOR_GRID_COLOR, gridwidth=0.5, dtick=0.04),
        zeroline=False, showticklabels=(row == 4), color='#666666',
    )
    y_axis_kwargs = dict(
        showgrid=True, gridcolor=_MAJOR_GRID_COLOR, gridwidth=1, dtick=0.5,
        minor=dict(showgrid=True, gridcolor=_MINOR_GRID_COLOR, gridwidth=0.5, dtick=0.1),
        zeroline=False, showticklabels=False,
    )
    if x_range is not None:
        axis_kwargs['range'] = x_range
    fig.update_xaxes(row=row, col=col, **axis_kwargs)
    fig.update_yaxes(row=row, col=col, **y_axis_kwargs)


def _plot_matplotlib(signals: Dict[str, np.ndarray], fs: int, title: Optional[str]):
    import matplotlib.pyplot as plt
    from matplotlib.gridspec import GridSpec
    from matplotlib.ticker import MultipleLocator

    n = len(next(iter(signals.values())))
    t = np.arange(n) / float(fs)
    total_duration = n / float(fs)
    seg_len = total_duration / 4.0

    fig = plt.figure(figsize=(14, 10), facecolor='#1a1a1a')
    gs = GridSpec(4, 4, figure=fig, height_ratios=[1, 1, 1, 1.4], hspace=0.5, wspace=0.15)

    def _style_axis(ax):
        ax.set_facecolor(_PAPER_BG)
        ax.xaxis.set_major_locator(MultipleLocator(0.2))
        ax.xaxis.set_minor_locator(MultipleLocator(0.04))
        ax.yaxis.set_major_locator(MultipleLocator(0.5))
        ax.yaxis.set_minor_locator(MultipleLocator(0.1))
        ax.grid(which='major', color=_MAJOR_GRID_COLOR, linewidth=0.8)
        ax.grid(which='minor', color=_MINOR_GRID_COLOR, linewidth=0.4)
        ax.set_yticklabels([])

    for col in range(4):
        window_start = col * seg_len
        window_end = window_start + seg_len
        mask = (t >= window_start) & (t < window_end)
        t_win = t[mask] - window_start
        for row in range(3):
            lead = _LAYOUT_COLUMNS[col][row]
            y = signals.get(lead, np.zeros(n))[mask]
            ax = fig.add_subplot(gs[row, col])
            _style_axis(ax)
            ax.plot(t_win, y, color=_TRACE_COLOR, linewidth=0.9)
            ax.set_title(lead, color='#e5e5e5', fontsize=9, loc='left')
            if row < 2:
                ax.set_xticklabels([])

    ax_rhythm = fig.add_subplot(gs[3, :])
    _style_axis(ax_rhythm)
    rhythm = signals.get(_RHYTHM_LEAD, np.zeros(n))
    cal_x = [-0.28, -0.28, -0.08, -0.08, 0.0]
    cal_y = [0.0, 1.0, 1.0, 0.0, 0.0]
    ax_rhythm.plot(cal_x, cal_y, color=_TRACE_COLOR, linewidth=0.9)
    ax_rhythm.plot(t, rhythm, color=_TRACE_COLOR, linewidth=0.9)
    ax_rhythm.set_xlim(-0.4, total_duration)
    ax_rhythm.set_title(f'{_RHYTHM_LEAD} (tira de ritmo)', color='#e5e5e5', fontsize=9, loc='left')
    ax_rhythm.set_xlabel('Tiempo (s)', color='#e5e5e5')

    fig.suptitle(f'{title}\n25 mm/s · 10 mm/mV', color='#e5e5e5')
    return fig
