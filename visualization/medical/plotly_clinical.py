"""Professional medical ECG visualization with Plotly."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple, Any

import numpy as np


def create_clinical_ecg_figure(
    signal: np.ndarray,
    fs: float,
    r_peaks: Optional[np.ndarray] = None,
    time_window: Tuple[float, float] = (0.0, 10.0),
    show_grid: bool = True,
    show_annotations: bool = True,
    title: str = "ECG — Clinical Monitor"
) -> Dict[str, Any]:
    """
    Create Plotly figure for clinical ECG display.
    
    Parameters
    ----------
    signal : ndarray
        ECG signal in mV
    fs : float
        Sampling frequency in Hz
    r_peaks : ndarray, optional
        Indices of R peaks
    time_window : tuple
        (start_time, end_time) in seconds
    show_grid : bool
        Show ECG grid
    show_annotations : bool
        Show P/QRS/T annotations
    title : str
        Figure title
        
    Returns
    -------
    dict
        Plotly figure specification
    """
    try:
        import plotly.graph_objects as go
    except ImportError:
        raise ImportError("Instala plotly: pip install plotly")
    
    time = np.arange(len(signal)) / fs
    start_idx = int(time_window[0] * fs)
    end_idx = int(min(time_window[1], time[-1]) * fs)
    
    signal_window = signal[start_idx:end_idx]
    time_window_data = time[start_idx:end_idx]
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=time_window_data,
        y=signal_window,
        mode='lines',
        line=dict(color='#00ff96', width=2.5),
        name='ECG Signal'
    ))
    
    if r_peaks is not None:
        visible_peaks = r_peaks[(r_peaks >= start_idx) & (r_peaks < end_idx)]
        if len(visible_peaks) > 0:
            fig.add_trace(go.Scatter(
                x=time[visible_peaks],
                y=signal[visible_peaks],
                mode='markers',
                marker=dict(color='#ff6b6b', size=8, symbol='x'),
                name='R Peaks'
            ))
    
    if show_grid:
        shapes = []
        
        x0 = time_window[0]
        while x0 <= time_window[1]:
            major = abs((x0 - time_window[0]) / 0.2 - round((x0 - time_window[0]) / 0.2)) < 1e-6
            shapes.append({
                'type': 'line',
                'x0': x0,
                'x1': x0,
                'y0': signal_window.min() - 0.5,
                'y1': signal_window.max() + 0.5,
                'line': {
                    'color': '#ff4040' if major else '#ffccd2',
                    'width': 1.5 if major else 0.8,
                }
            })
            x0 += 0.04
        
        y0 = int((signal_window.min() - 0.5) * 10) / 10
        while y0 <= signal_window.max() + 0.5:
            major = abs(y0 - round(y0, 1)) < 0.05
            shapes.append({
                'type': 'line',
                'x0': time_window[0],
                'x1': time_window[1],
                'y0': y0,
                'y1': y0,
                'line': {
                    'color': '#ff4040' if major else '#ffccd2',
                    'width': 1.5 if major else 0.8,
                }
            })
            y0 += 0.1
        
        fig.update_layout(shapes=shapes)
    
    fig.update_layout(
        title=title,
        xaxis_title='Time (s)',
        yaxis_title='mV',
        hovermode='x unified',
        paper_bgcolor='#081c2c',
        plot_bgcolor='#081c2c',
        font=dict(color='#ffffff', family='Arial'),
        height=500,
        margin=dict(l=50, r=50, t=50, b=50)
    )
    
    fig.update_xaxes(
        showgrid=False,
        zeroline=False,
        range=[time_window[0], time_window[1]]
    )
    
    fig.update_yaxes(
        showgrid=False,
        zeroline=False
    )
    
    return fig


def create_multisensor_dashboard(
    channels: Dict[str, np.ndarray],
    fs: float,
    time_window: Tuple[float, float] = (0.0, 10.0)
) -> Dict[str, Any]:
    """
    Create multisensorial dashboard with multiple signal displays.
    
    Parameters
    ----------
    channels : dict
        Dictionary of {name: signal_array}
    fs : float
        Sampling frequency
    time_window : tuple
        Time range to display
        
    Returns
    -------
    dict
        Plotly subplot figure
    """
    try:
        import plotly.subplots as sp
        import plotly.graph_objects as go
    except ImportError:
        raise ImportError("Instala plotly: pip install plotly")
    
    n_channels = len(channels)
    
    fig = sp.make_subplots(
        rows=n_channels,
        cols=1,
        subplot_titles=list(channels.keys()),
        specs=[[{"secondary_y": False}] for _ in range(n_channels)]
    )
    
    time = np.arange(len(next(iter(channels.values())))) / fs
    start_idx = int(time_window[0] * fs)
    end_idx = int(min(time_window[1], time[-1]) * fs)
    
    colors = ['#00ff96', '#ffa15a', '#ff6b6b', '#636efa', '#ab63fa', '#ffa15a']
    
    for idx, (name, signal) in enumerate(channels.items(), 1):
        signal_window = signal[start_idx:end_idx]
        time_window_data = time[start_idx:end_idx]
        
        fig.add_trace(
            go.Scatter(
                x=time_window_data,
                y=signal_window,
                mode='lines',
                line=dict(color=colors[(idx - 1) % len(colors)], width=2),
                name=name
            ),
            row=idx,
            col=1
        )
        
        fig.update_yaxes(title_text=name, row=idx, col=1)
    
    fig.update_xaxes(title_text='Time (s)', row=n_channels, col=1)
    
    fig.update_layout(
        title='Multisensorial Biomedical Dashboard',
        height=200 * n_channels,
        paper_bgcolor='#081c2c',
        plot_bgcolor='#081c2c',
        font=dict(color='#ffffff'),
        hovermode='x unified'
    )
    
    return fig


def create_hrv_plot(
    rr_intervals: np.ndarray,
    frequencies: Optional[np.ndarray] = None,
    power: Optional[np.ndarray] = None
) -> Dict[str, Any]:
    """Create HRV analysis figure with time and frequency domain."""
    try:
        import plotly.subplots as sp
        import plotly.graph_objects as go
    except ImportError:
        raise ImportError("Instala plotly: pip install plotly")
    
    fig = sp.make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("RR Intervals", "Power Spectral Density")
    )
    
    time = np.cumsum(rr_intervals)
    
    fig.add_trace(
        go.Scatter(
            x=time,
            y=rr_intervals,
            mode='lines+markers',
            line=dict(color='#00ff96', width=2),
            marker=dict(size=4),
            name='RR Intervals'
        ),
        row=1,
        col=1
    )
    
    if frequencies is not None and power is not None:
        fig.add_trace(
            go.Scatter(
                x=frequencies,
                y=power,
                mode='lines',
                fill='tozeroy',
                line=dict(color='#ffa15a', width=2),
                name='Power'
            ),
            row=1,
            col=2
        )
    
    fig.update_xaxes(title_text='Time (s)', row=1, col=1)
    fig.update_yaxes(title_text='RR Interval (s)', row=1, col=1)
    fig.update_xaxes(title_text='Frequency (Hz)', row=1, col=2)
    fig.update_yaxes(title_text='Power (ms²/Hz)', row=1, col=2)
    
    fig.update_layout(
        title='Heart Rate Variability Analysis',
        height=400,
        paper_bgcolor='#081c2c',
        plot_bgcolor='#081c2c',
        font=dict(color='#ffffff'),
        hovermode='x unified'
    )
    
    return fig
