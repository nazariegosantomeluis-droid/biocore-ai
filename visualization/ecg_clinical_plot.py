"""High-level plotting utilities to create clinical-style ECG visualizations.

Functions produce:
 - ecg_clinical.png
 - ecg_annotated.png
 - ecg_zoomed_beat.png
 - ecg_medical_report.png

APIs are conservative and accept optional `rpeaks` to avoid changing existing pipeline behavior.
"""
from __future__ import annotations

import os
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import find_peaks, savgol_filter

from .medical_grid import draw_ecg_grid
from .ecg_annotations import detect_waves, compute_measurements, simple_pattern_detection, plot_wave_markers
from .educational_panel import build_educational_text, draw_panel


def _ensure_outdir(outdir: str):
    os.makedirs(outdir, exist_ok=True)


def _ensure_rpeaks(sig: np.ndarray, fs: float, rpeaks: np.ndarray | None):
    if rpeaks is not None:
        return np.asarray(rpeaks, dtype=int)
    # very simple R-peak detection fallback: find peaks on absolute signal
    distance = int(0.3 * fs)
    height = np.mean(sig) + 0.5 * np.std(sig)
    peaks, _ = find_peaks(sig, distance=distance, height=height)
    if len(peaks) == 0:
        # try looser threshold
        peaks, _ = find_peaks(sig, distance=distance)
    return peaks


def _smooth_signal(sig: np.ndarray, fs: float) -> np.ndarray:
    """Return a smooth version of the ECG for display without altering detection."""
    if len(sig) < 25:
        return sig
    window = int(min(len(sig) - (1 - len(sig) % 2), max(5, round(0.08 * fs))))
    if window % 2 == 0:
        window += 1
    window = min(window, len(sig) - 1)
    try:
        return savgol_filter(sig, window_length=window, polyorder=3)
    except Exception:
        return sig


def _set_ecg_style(ax, *, dark: bool = False):
    if dark:
        ax.set_facecolor("#081b27")
        ax.tick_params(axis="x", colors="#d8f3ff", labelsize=10)
        ax.tick_params(axis="y", colors="#d8f3ff", labelsize=10)
        for spine in ax.spines.values():
            spine.set_color("#3a6a8f")
            spine.set_linewidth(0.8)
    else:
        ax.set_facecolor("#fff9f2")
        ax.tick_params(axis="x", colors="#333333", labelsize=10)
        ax.tick_params(axis="y", colors="#333333", labelsize=10)
        for spine in ax.spines.values():
            spine.set_color("#8c8c8c")
            spine.set_linewidth(0.8)
    ax.grid(False)


def plot_ecg_clinical(sig: np.ndarray, fs: float, rpeaks: np.ndarray | None = None,
                      outdir: str = "figures", prefix: str = "ecg"):
    """Create clinical ECG images and save them to `outdir`.

    `sig` must be in mV. `fs` is sampling frequency in Hz.
    """
    _ensure_outdir(outdir)
    rpeaks = _ensure_rpeaks(sig, fs, rpeaks)
    beats = detect_waves(sig, fs, rpeaks)
    measurements = compute_measurements(beats, fs)
    patterns = simple_pattern_detection(measurements, beats, fs)

    t = np.arange(len(sig)) / fs
    duration = t[-1] if len(t) else 0.0

    # determine y-limits (mV) with small margin
    vmin = np.min(sig) - 0.5
    vmax = np.max(sig) + 0.5
    sig_vis = _smooth_signal(sig, fs)

    # 1) Clinical baseline plot with grid (zoomed to 8 seconds for better visibility)
    clinical_duration = min(8.0, duration)  # Show max 8 seconds
    fig, ax = plt.subplots(figsize=(14, 5))
    _set_ecg_style(ax, dark=True)
    draw_ecg_grid(ax, clinical_duration, vmin, vmax, fs, background_color="#0a2438", minor_color="#1a4d6d", major_color="#2a7aad")
    ax.plot(t[:int(clinical_duration * fs)], sig_vis[:int(clinical_duration * fs)], color="#00ff7f", linewidth=2.2, zorder=3)
    ax.set_xlabel("Time (s)", color="#d8f3ff", fontsize=11)
    ax.set_ylabel("Voltage (mV)", color="#d8f3ff", fontsize=11)
    ax.set_title("ECG — Clinical Monitor Display", fontsize=18, weight="semibold", color="#c2f0ff")
    ax.text(0.02 * clinical_duration, vmax - 0.08 * (vmax - vmin), "25 mm/s | 10 mm/mV", color="#a8dfff", fontsize=10, 
            bbox=dict(boxstyle="round,pad=0.4", facecolor="#0a1820", alpha=0.8, edgecolor="#1a4d6d"))
    ax.set_yticks([])
    ax.set_xticks(np.arange(0, clinical_duration + 0.5, 1.0))
    ax.set_xlim(0, clinical_duration)
    plt.tight_layout()
    clinical_path = os.path.join(outdir, f"{prefix}_clinical.png")
    fig.savefig(clinical_path, dpi=200, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)

    # 2) Annotated plot (zoomed to 8 seconds)
    annotated_duration = min(8.0, duration)
    fig, ax = plt.subplots(figsize=(14, 5))
    _set_ecg_style(ax, dark=True)
    draw_ecg_grid(ax, annotated_duration, vmin, vmax, fs, background_color="#0a2438", minor_color="#1a4d6d", major_color="#2a7aad")
    ax.plot(t[:int(annotated_duration * fs)], sig_vis[:int(annotated_duration * fs)], color="#00ff7f", linewidth=2.4, zorder=3)
    # Filter beats to show only those in the zoomed window
    visible_beats = [b for b in beats if b.get("R", 0) < int(annotated_duration * fs)]
    plot_wave_markers(ax, visible_beats, fs, sig, n_beats=6, annotate=False)
    hr = measurements.get("HR")
    info = [f"HR: {hr:.1f} bpm" if hr else "HR: N/A",
            f"PR: {measurements.get('PR_mean')*1000:.0f} ms" if measurements.get("PR_mean") else "PR: N/A",
            f"QRS: {measurements.get('QRS_mean')*1000:.0f} ms" if measurements.get("QRS_mean") else "QRS: N/A",
            f"QTc: {measurements.get('QTc'):.0f} ms" if measurements.get("QTc") else "QTc: N/A",
            "", "MARKERS:",
            "● P=Atrial  ■ Q=Q-wave  ★ R=R-peak",
            "◆ S=S-wave  ▲ T=T-wave"]
    ax.text(0.02 * annotated_duration, vmax - 0.10 * (vmax - vmin), "\n".join(info), ha="left", va="top",
            bbox=dict(facecolor="#0a1820", boxstyle="round,pad=0.5", edgecolor="#2a7aad", linewidth=1.5), 
            fontsize=9, color="#e7f8ff", family="monospace")
    ax.set_yticks([])
    ax.set_xticks(np.arange(0, annotated_duration + 0.5, 1.0))
    ax.set_xlim(0, annotated_duration)
    ax.set_xlabel("Time (s)", color="#d8f3ff", fontsize=11)
    ax.set_title("ECG — Annotated Clinical Strip", fontsize=18, weight="semibold", color="#c2f0ff")
    plt.tight_layout()
    annotated_path = os.path.join(outdir, f"{prefix}_annotated.png")
    fig.savefig(annotated_path, dpi=200, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)

    # 3) Zoomed beat (first well-formed beat)
    zoom_path = None
    start = 0
    end = min(len(sig), int(0.6 * fs))
    small_beats = []
    if len(rpeaks) > 0:
        idx = int(len(rpeaks) // 2)
        r = rpeaks[idx]
        win = int(0.6 * fs)
        start = max(0, r - win)
        end = min(len(sig), r + win)
        fig, ax = plt.subplots(figsize=(8, 4))
        _set_ecg_style(ax, dark=True)
        draw_ecg_grid(ax, (end - start) / fs, np.min(sig[start:end]) - 0.3, np.max(sig[start:end]) + 0.3, fs,
                      background_color="#0a2438", minor_color="#1a4d6d", major_color="#2a7aad")
        ax.plot(t[start:end] - t[start], _smooth_signal(sig[start:end], fs), color="#00ff7f", linewidth=2.0)
        # annotate this single beat
        small_beats = [b for b in beats if start <= b["R"] <= end]
        plot_wave_markers(ax, small_beats, fs, sig[start:end], n_beats=4, sample_offset=start, annotate=False)
        ax.set_title("Zoomed Beat", fontsize=12, weight="semibold")
        plt.tight_layout()
        zoom_path = os.path.join(outdir, f"{prefix}_zoomed_beat.png")
        fig.savefig(zoom_path, dpi=200)
        plt.close(fig)

    # 4) Medical report image: combine annotated ECG + educational panel
    report_duration = min(8.0, duration)
    fig = plt.figure(figsize=(15, 10))
    gs = fig.add_gridspec(3, 2, width_ratios=(3, 1), height_ratios=(2, 1, 1.2), hspace=0.35, wspace=0.30)
    ax_main = fig.add_subplot(gs[0:2, 0])
    ax_summary = fig.add_subplot(gs[0, 1])
    ax_zoom = fig.add_subplot(gs[1, 1])
    ax_educ = fig.add_subplot(gs[2, :])

    _set_ecg_style(ax_main, dark=True)
    draw_ecg_grid(ax_main, report_duration, vmin, vmax, fs, background_color="#0a2438", minor_color="#1a4d6d", major_color="#2a7aad")
    ax_main.plot(t[:int(report_duration * fs)], sig_vis[:int(report_duration * fs)], color="#00ff7f", linewidth=2.0)
    visible_beats_report = [b for b in beats if b.get("R", 0) < int(report_duration * fs)]
    plot_wave_markers(ax_main, visible_beats_report, fs, sig, n_beats=6, annotate=False)
    ax_main.set_yticks([])
    ax_main.set_xticks(np.arange(0, report_duration + 0.5, 1.0))
    ax_main.set_xlim(0, report_duration)
    ax_main.set_xlabel("Time (s)", color="#d8f3ff", fontsize=10)
    ax_main.set_title("ECG Clinical Overview", fontsize=16, weight="bold", color="#c2f0ff")

    ax_summary.axis("off")
    ax_summary.set_facecolor("#0a2438")
    summary_text = ["CLINICAL SUMMARY", ""] + info
    if patterns:
        summary_text.extend(["", "PATTERNS:"])
        for p in patterns:
            summary_text.append(f" • {p['label']}")
    summary_text = "\n".join(summary_text)
    ax_summary.text(0, 1, summary_text, va="top", ha="left", fontsize=9, color="#d8f3ff",
                    family="monospace", linespacing=1.5, bbox=dict(facecolor="#051621", edgecolor="#2a7aad", boxstyle="round,pad=0.6", linewidth=1))

    _set_ecg_style(ax_zoom, dark=True)
    draw_ecg_grid(ax_zoom, (end - start) / fs, np.min(sig[start:end]) - 0.3, np.max(sig[start:end]) + 0.3, fs,
                  background_color="#0a2438", minor_color="#1a4d6d", major_color="#2a7aad")
    ax_zoom.plot(t[start:end] - t[start], _smooth_signal(sig[start:end], fs), color="#00ff7f", linewidth=2.2)
    plot_wave_markers(ax_zoom, small_beats, fs, sig[start:end], n_beats=4, sample_offset=start, annotate=False)
    ax_zoom.set_yticks([])
    ax_zoom.set_xticks(np.arange(0, (end - start) / fs + 0.2, 0.2))
    ax_zoom.set_xlabel("Time (s)", color="#d8f3ff", fontsize=9)
    ax_zoom.set_title("Beat Detail", fontsize=12, weight="semibold", color="#c2f0ff")

    ax_educ.axis("off")
    ax_educ.set_facecolor("#0a2438")
    ed_text = build_educational_text(measurements, patterns)
    draw_panel(ax_educ, ed_text, dark=True)
    ax_educ.set_title("Educational Guidance", fontsize=12, weight="semibold", pad=10, color="#c2f0ff")

    fig.suptitle("ECG Medical Report", fontsize=20, weight="bold", color="#00ff7f")
    fig.patch.set_facecolor("#081b27")
    fig.subplots_adjust(top=0.92, left=0.05, right=0.98, hspace=0.35, wspace=0.28)
    report_path = os.path.join(outdir, f"{prefix}_medical_report.png")
    fig.savefig(report_path, dpi=200, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)

    return {
        "clinical": clinical_path,
        "annotated": annotated_path,
        "zoomed": zoom_path if len(rpeaks) > 0 else None,
        "report": report_path,
        "measurements": measurements,
        "patterns": patterns,
    }


if __name__ == "__main__":
    print("This module provides plotting utilities. Import and call `plot_ecg_clinical`.")
