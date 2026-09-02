"""Tools to draw an authentic ECG paper grid on a Matplotlib Axes.

Grid units follow clinical scales: 25 mm/s and 10 mm/mV.
All functions operate with time in seconds and voltage in mV.
"""
from __future__ import annotations

import numpy as np


def draw_ecg_grid(ax, duration_s, vmin, vmax, fs, *,
                  mm_per_s: float = 25.0,
                  mm_per_mV: float = 10.0,
                  minor_color: str = "#ffeaea",
                  major_color: str = "#ff9999",
                  background_color: str = "#fffaf6"):
    """Draw an ECG paper-like grid on `ax`.

    Parameters
    - ax: matplotlib Axes
    - duration_s: length of x-axis in seconds
    - vmin, vmax: y-axis limits in mV
    - fs: sampling frequency (unused for grid spacing, kept for API)
    - background_color: axis face color for the grid
    """
    # clinical scale: 25 mm per second -> 1 mm = 1/25 s
    minor_sec = 1.0 / mm_per_s
    major_sec = minor_sec * 5

    # amplitude: 10 mm per mV -> 1 mm = 1/10 mV
    minor_mV = 1.0 / mm_per_mV
    major_mV = minor_mV * 5

    xmin, xmax = 0.0, duration_s
    ymin, ymax = vmin, vmax

    # vertical (time) lines
    t_minor = np.arange(xmin, xmax + minor_sec, minor_sec)
    for t in t_minor:
        ax.axvline(t, color=minor_color, linewidth=0.5, zorder=0)
    t_major = np.arange(xmin, xmax + major_sec, major_sec)
    for t in t_major:
        ax.axvline(t, color=major_color, linewidth=1.0, zorder=0)

    # horizontal (voltage) lines
    y_minor = np.arange(ymin - minor_mV, ymax + minor_mV, minor_mV)
    for y in y_minor:
        ax.axhline(y, color=minor_color, linewidth=0.5, zorder=0)
    y_major = np.arange(ymin - major_mV, ymax + major_mV, major_mV)
    for y in y_major:
        ax.axhline(y, color=major_color, linewidth=1.0, zorder=0)

    # cosmetic: set limits and keep grid behind
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_facecolor(background_color)
