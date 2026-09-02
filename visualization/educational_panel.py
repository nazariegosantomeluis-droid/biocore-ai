"""Functions to render an educational panel describing ECG findings."""
from __future__ import annotations

from typing import List, Dict


def build_educational_text(measurements: Dict[str, float], patterns: List[Dict[str, str]]) -> str:
    """Return a multi-line educational explanation string."""
    lines = ["EDUCATIONAL SUMMARY", ""]

    lines.append("Clinical Measurements:")
    hr = measurements.get("HR")
    if hr is not None:
        lines.append(f" • Heart rate: {hr:.1f} bpm")
    pr = measurements.get("PR_mean")
    if pr is not None:
        lines.append(f" • PR interval: {pr*1000:.0f} ms")
    qrs = measurements.get("QRS_mean")
    if qrs is not None:
        lines.append(f" • QRS duration: {qrs*1000:.0f} ms")
    qt = measurements.get("QT_mean")
    if qt is not None:
        lines.append(f" • QT interval: {qt*1000:.0f} ms (QTc {measurements.get('QTc'):.0f} ms)")

    lines.append("")
    lines.append("Detected Patterns:")
    if patterns:
        for p in patterns:
            lines.append(f" • {p['label']}: {p['explanation']}")
    else:
        lines.append(" • No major patterns detected by heuristics.")

    lines.append("")
    lines.append("Key Teaching Points:")
    lines.append(" • P wave: look for upright, consistent morphology.")
    lines.append(" • Wide QRS (>120 ms) suggests ventricular conduction delay.")
    lines.append(" • ST elevation in contiguous leads suggests injury.")
    lines.append(" • Irregular RR intervals with absent Ps suggest atrial fibrillation.")

    return "\n".join(lines)


def draw_panel(ax, text: str, *, dark: bool = False):
    if dark:
        ax.set_facecolor("#101922")
        ax.axis("off")
        ax.text(0, 1, text, va="top", ha="left", fontsize=10, family="sans-serif",
                color="#e6f7ff", linespacing=1.4)
    else:
        ax.set_facecolor("#f8f4ed")
        ax.axis("off")
        ax.text(0, 1, text, va="top", ha="left", fontsize=10, family="sans-serif",
                color="#222222", linespacing=1.4)
