"""Simple ECG wave detection and annotation helpers.

These use heuristics based on R-peak locations to find Q, S, P and T waves.
Designed to be conservative and educational rather than diagnostic.
"""
from __future__ import annotations

import numpy as np
from typing import List, Dict, Any, Optional
from matplotlib.lines import Line2D


def detect_waves(sig: np.ndarray, fs: float, rpeaks: np.ndarray) -> List[Dict[str, Any]]:
    """Return detected wave indices and times for each beat.

    Expects `sig` in mV and `rpeaks` as sample indices.
    """
    beats = []
    N = len(sig)
    for r in rpeaks:
        beat = {"R": int(r)}
        # Q: local minimum within 40 ms before R
        q_start = max(0, int(r - 0.04 * fs))
        q_end = int(r)
        if q_end - q_start > 2:
            q_rel = np.argmin(sig[q_start:q_end])
            beat["Q"] = int(q_start + q_rel)
        else:
            beat["Q"] = None

        # S: local minimum within 60 ms after R
        s_start = int(r)
        s_end = min(N, int(r + 0.06 * fs))
        if s_end - s_start > 2:
            s_rel = np.argmin(sig[s_start:s_end])
            beat["S"] = int(s_start + s_rel)
        else:
            beat["S"] = None

        # P: search 120-200 ms before Q (if Q exists)
        p_idx = None
        if beat.get("Q"):
            p_search_end = max(0, beat["Q"] - int(0.02 * fs))
            p_search_start = max(0, beat["Q"] - int(0.20 * fs))
            if p_search_end - p_search_start > 2:
                p_rel = np.argmax(sig[p_search_start:p_search_end])
                p_idx = int(p_search_start + p_rel)
        beat["P"] = p_idx

        # T: search 80-400 ms after S
        t_idx = None
        if beat.get("S"):
            t_search_start = beat["S"] + int(0.08 * fs)
            t_search_end = min(N, beat["S"] + int(0.40 * fs))
            if t_search_end - t_search_start > 2:
                t_rel = np.argmax(sig[t_search_start:t_search_end])
                t_idx = int(t_search_start + t_rel)
        beat["T"] = t_idx

        beats.append(beat)
    return beats


def compute_measurements(beats: List[Dict[str, Any]], fs: float) -> Dict[str, Any]:
    """Compute HR and intervals from detected beats list.

    Returns a dict with HR, PR, QRS, QT, RR stats.
    """
    r_times = np.array([b["R"] for b in beats]) / fs
    rr = np.diff(r_times)
    hr = 60.0 / np.mean(rr) if len(rr) > 0 else float("nan")

    pr_list = []
    qrs_list = []
    qt_list = []
    for b in beats:
        P = b.get("P")
        Q = b.get("Q")
        S = b.get("S")
        T = b.get("T")
        if P and Q:
            pr_list.append((b["R"] - P) / fs)
        if Q and S:
            qrs_list.append((S - Q) / fs)
        if Q and T:
            qt_list.append((T - Q) / fs)

    measurements = {
        "HR": float(hr),
        "RR_mean": float(np.mean(rr)) if len(rr) > 0 else None,
        "RR_std": float(np.std(rr)) if len(rr) > 0 else None,
        "PR_mean": float(np.mean(pr_list)) if pr_list else None,
        "QRS_mean": float(np.mean(qrs_list)) if qrs_list else None,
        "QT_mean": float(np.mean(qt_list)) if qt_list else None,
    }
    # Simple QTc (Bazett)
    if measurements.get("QT_mean") and measurements.get("RR_mean"):
        qt = measurements["QT_mean"]
        rrm = measurements["RR_mean"]
        measurements["QTc"] = qt / (rrm ** 0.5)
    else:
        measurements["QTc"] = None

    return measurements


def simple_pattern_detection(measurements: Dict[str, Any], beats: List[Dict[str, Any]], fs: float) -> List[Dict[str, str]]:
    """Return simple detected patterns with explanations.

    Heuristics only; educational use.
    """
    patterns = []
    hr = measurements.get("HR")
    if hr:
        if hr < 60:
            patterns.append({"label": "Bradycardia", "explanation": "Heart rate < 60 bpm. Check clinical context."})
        elif hr > 100:
            patterns.append({"label": "Tachycardia", "explanation": "Heart rate > 100 bpm. Consider sinus tachy or other causes."})

    # RR irregularity -> suspect AF
    rr_std = measurements.get("RR_std")
    rr_mean = measurements.get("RR_mean")
    if rr_std and rr_mean and rr_std > 0.1 * rr_mean:
        # check absence of Ps heuristic: many missing P detections
        p_count = sum(1 for b in beats if b.get("P"))
        if p_count < 0.6 * max(1, len(beats)):
            patterns.append({"label": "Atrial fibrillation suspected", "explanation": "Irregular RR intervals and few visible P waves."})

    # PVC heuristic: premature beat with short preceding RR and wide QRS
    if len(beats) >= 3:
        r_inds = np.array([b["R"] for b in beats])
        rr = np.diff(r_inds)
        avg_rr = np.mean(rr)
        for i in range(1, len(rr)):
            if rr[i] < 0.8 * avg_rr:
                # check QRS duration for that beat
                b = beats[i + 1] if i + 1 < len(beats) else beats[i]
                if b.get("Q") and b.get("S") and ((b["S"] - b["Q"]) / fs) > 0.12:
                    patterns.append({"label": "PVC", "explanation": "Premature beat with wide QRS — possible PVC."})
                    break

    return patterns


def plot_wave_markers(ax, beats: List[Dict[str, Any]], fs: float, sig: np.ndarray,
                      n_beats: int = 4, sample_offset: int = 0, annotate: bool = False):
    """Place wave markers on an ECG plot.

    If annotate=True, add wave labels with intelligent offset positioning to avoid overlap.
    Otherwise, use markers with a compact legend (no text labels).
    """
    colors = {"P": "#1f77b4", "Q": "#444444", "R": "#d62728", "S": "#ff7f0e", "T": "#9467bd"}
    markers = {"P": "o", "Q": "s", "R": "*", "S": "D", "T": "^"}
    desc = {"P": "P wave",
            "Q": "Q wave",
            "R": "R peak",
            "S": "S wave",
            "T": "T wave"}

    legend_handles = []
    added = set()
    placed_labels = []  # Track placed labels to avoid overlap

    for i, b in enumerate(beats[:n_beats]):
        for key in ("P", "Q", "R", "S", "T"):
            idx = b.get(key)
            if idx is None:
                continue
            local_idx = int(idx - sample_offset)
            if local_idx < 0 or local_idx >= len(sig):
                continue
            t = local_idx / fs
            y = sig[local_idx]
            ax.scatter(t, y, marker=markers[key], s=80, edgecolors="#ffffff", linewidths=1.2,
                       facecolor=colors[key], zorder=5)

            if annotate and i == 0:
                # Smart offset to avoid overlap with previously placed labels
                offset_y = 0.14
                for px, py, pl in placed_labels:
                    if abs(px - t) < 0.3:  # If labels are close horizontally
                        offset_y = max(offset_y, py + 0.12)  # Stack vertically instead
                
                ax.annotate(key,
                            xy=(t, y), xytext=(t + 0.05, y + offset_y),
                            textcoords="data",
                            arrowprops=dict(arrowstyle="->", color=colors[key], linewidth=0.8, lw=1),
                            color=colors[key], fontsize=9, weight="bold",
                            bbox=dict(boxstyle="round,pad=0.3", fc="#ffffffdd", ec=colors[key], lw=0.6))
                
                placed_labels.append((t, offset_y, key))

            if key not in added:
                legend_handles.append(Line2D([0], [0], marker=markers[key], color="w",
                                             markerfacecolor=colors[key], markeredgecolor="#444444",
                                             markersize=8, linestyle="None", label=desc[key]))
                added.add(key)

    if not annotate and legend_handles:
        ax.legend(handles=legend_handles, loc="upper right", frameon=True,
                  fontsize=8, facecolor="#f7f5f0", edgecolor="#777777", framealpha=0.95)


def annotate_ax(ax, beats: List[Dict[str, Any]], fs: float, sig: np.ndarray,
                n_beats: int = 6, sample_offset: int = 0):
    """Annotate the axes with a limited set of markers and labels."""
    plot_wave_markers(ax, beats, fs, sig, n_beats=n_beats, sample_offset=sample_offset, annotate=True)
