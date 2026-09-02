import os
import datetime
from typing import Dict, Any, List, Optional, Tuple

_MATPLOTLIB_AVAILABLE: Optional[bool] = None
_plt = None
_MATPLOTLIB_IMPORT_ERROR = None


def _ensure_matplotlib():
    global _MATPLOTLIB_AVAILABLE, _plt, _MATPLOTLIB_IMPORT_ERROR
    if _MATPLOTLIB_AVAILABLE is not None:
        return
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        _plt = plt
        _MATPLOTLIB_AVAILABLE = True
    except Exception as e:
        _MATPLOTLIB_AVAILABLE = False
        _MATPLOTLIB_IMPORT_ERROR = e
        _plt = None
        print(f"⚠️ Matplotlib no disponible: {e}")


def _ensure_reports_dir(path: str = "reports") -> str:
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)
    return path


def _create_logo(path: str) -> None:
    _ensure_matplotlib()
    if not _MATPLOTLIB_AVAILABLE or _plt is None:
        return
    try:
        fig, ax = _plt.subplots(figsize=(2, 0.7), dpi=150)
        ax.set_facecolor('#0f172a')
        ax.text(0.5, 0.45, 'BSP', color='#ffffff', fontsize=28, fontweight='bold', ha='center', va='center')
        ax.text(0.5, 0.12, 'Biomedical Signal Platform', color='#9fb8ff', fontsize=8, ha='center')
        ax.set_axis_off()
        fig.savefig(path, bbox_inches='tight', pad_inches=0.1)
        _plt.close(fig)
    except Exception:
        pass


def _save_signal_plot(path: str, time, signal, title: str = '') -> None:
    _ensure_matplotlib()
    if not _MATPLOTLIB_AVAILABLE or _plt is None:
        return
    try:
        fig, ax = _plt.subplots(figsize=(8, 2.0), dpi=150)
        ax.plot(time, signal, color='#1f77b4', linewidth=0.8)
        ax.set_title(title)
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Amplitude')
        ax.grid(alpha=0.25)
        fig.tight_layout()
        fig.savefig(path)
        _plt.close(fig)
    except Exception:
        pass


def _save_bar_plot(path: str, labels: List[str], values: List[float], title: str = '') -> None:
    _ensure_matplotlib()
    if not _MATPLOTLIB_AVAILABLE or _plt is None:
        return
    try:
        fig, ax = _plt.subplots(figsize=(6, 3), dpi=150)
        ax.bar(labels, values, color='#44d7b6')
        ax.set_title(title)
        ax.grid(axis='y', alpha=0.2)
        fig.tight_layout()
        fig.savefig(path)
        _plt.close(fig)
    except Exception:
        pass


def _save_plotly_fig(path: str, fig) -> bool:
    """Try to save a Plotly figure to PNG using kaleido (preferred)."""
    try:
        import plotly.io as pio
        # use kaleido if available
        img_bytes = pio.to_image(fig, format='png')
        with open(path, 'wb') as fh:
            fh.write(img_bytes)
        return True
    except Exception:
        try:
            # fallback: write html snapshot
            p_html = path + '.html'
            fig.write_html(p_html)
            return False
        except Exception:
            return False



def export_lab_report(
    lab_name: str,
    metrics: Dict[str, Any],
    notes: str = "",
    findings: Optional[Dict[str, Any]] = None,
    out_dir: str = "reports",
    image_paths: Optional[List[Tuple[str, str]]] = None,
) -> str:
    """Export a styled HTML report and an enriched PDF (if fpdf available).

    Parameters:
    - lab_name: title
    - metrics: key->value metrics
    - notes: additional text
    - findings: optional clinical findings or classification summary
    - out_dir: folder to write
    - image_paths: optional list of (caption, path-to-png)

    Returns path to the generated PDF if created, otherwise HTML path.
    """
    out_dir = _ensure_reports_dir(out_dir)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = lab_name.replace(' ', '_')
    html_path = os.path.join(out_dir, f"report_{safe_name}_{timestamp}.html")
    logo_path = os.path.join(out_dir, f"logo_{safe_name}.png")
    if not os.path.exists(logo_path):
        _create_logo(logo_path)

    logo_html = ''
    if os.path.exists(logo_path):
        logo_html = f'<img class="logo" src="{os.path.basename(logo_path)}" alt="logo">'
    else:
        logo_html = '<div class="logo" style="display:inline-block;padding:12px 18px;background:#152339;border-radius:12px;color:#d1e8ff;font-weight:700;font-size:1rem;">BIOCORE AI</div>'

    # Build a richer HTML report with responsive cards and embedded images
    css = (
        "body{font-family:Inter, Arial, Helvetica, sans-serif; background:#071226; color:#e6eef8; margin:0;}"
        " .container{max-width:980px;margin:18px auto;background:linear-gradient(180deg,#061026, #071428);padding:22px;border-radius:14px;border:1px solid rgba(255,255,255,0.03);}"
        " .header{display:flex;align-items:center;gap:12px;margin-bottom:14px;}"
        " .logo{height:60px;border-radius:8px;box-shadow:0 8px 20px rgba(0,0,0,0.45);}"
        " .title{font-size:1.6rem;color:#cfe9ff;margin:0;}"
        " .sub{color:#99c7ff;margin:0;font-size:0.9rem;}"
        " .metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;margin:14px 0;}"
        " .metric{background:rgba(255,255,255,0.03);padding:10px;border-radius:8px;border:1px solid rgba(255,255,255,0.04);}"
        " .fig{margin:10px 0;} img{max-width:100%;border-radius:8px;}"
        " .findings{background:rgba(10,20,36,0.6);padding:10px;border-radius:8px;margin-top:10px;}"
        " pre{background:rgba(2,8,18,0.6);padding:12px;border-radius:8px;color:#dfefff;white-space:pre-wrap;}"
    )

    html_lines = [
        '<!doctype html>',
        '<html lang="es">',
        '<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
        f'<title>{lab_name} — Report</title>',
        f'<style>{css}</style>',
        '</head>',
        '<body>',
        '<div class="container">',
        '<div class="header">',
        f'{logo_html}',
        f'<div><h1 class="title">{lab_name}</h1><div class="sub">Generated: {timestamp}</div></div>',
        '</div>',
        '<hr style="border:none;border-top:1px solid rgba(255,255,255,0.03);margin:12px 0;">',
        '<div class="metrics">',
    ]

    # Add metric cards
    for k, v in metrics.items():
        html_lines.append(f'<div class="metric"><strong>{k}</strong><div style="font-size:1.1rem;margin-top:6px;color:#eaf6ff;">{v}</div></div>')

    html_lines += ['</div>']

    if findings:
        html_lines.append('<div class="findings"><h3>Clinical Findings</h3>')
        for k, v in findings.items():
            html_lines.append(f'<div><strong>{k}:</strong> {v}</div>')
        html_lines.append('</div>')

    if image_paths:
        html_lines.append('<div class="fig"><h3>Figures</h3>')
        for caption, p in image_paths:
            html_lines.append(f'<div style="margin-bottom:12px;"><strong>{caption}</strong><br><img src="{os.path.basename(p)}" alt="{caption}"></div>')
        html_lines.append('</div>')

    html_lines += [f'<h3>Notes</h3><pre>{notes}</pre>', '<hr style="border:none;border-top:1px solid rgba(255,255,255,0.03);margin:12px 0;">']
    html_lines.append('<div style="font-size:0.9rem;color:#bcdff8;">Recommended installs: <code>pip install plotly kaleido fpdf</code></div>')
    html_lines += ['</div>', '</body>', '</html>']

    # Write files and copy images (ensure images are in same dir)
    # Copy logo and image files to out_dir if not already
    from shutil import copyfile
    if os.path.exists(logo_path):
        copyfile(logo_path, os.path.join(out_dir, os.path.basename(logo_path)))

    if image_paths:
        for _, p in image_paths:
            try:
                copyfile(p, os.path.join(out_dir, os.path.basename(p)))
            except Exception:
                pass

    with open(html_path, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(html_lines))

    # Try to build a PDF with FPDF including images; if not available, return HTML and leave assets in out_dir
    pdf_path = None
    try:
        from fpdf import FPDF

        # Try to embed a TTF font (DejaVu Sans) if available to support Unicode
        try:
            import matplotlib.font_manager as fm
            font_path = fm.findfont('DejaVu Sans')
        except Exception:
            font_path = None

        class PDF(FPDF):
            def header(self_inner):
                logo_file = os.path.join(out_dir, os.path.basename(logo_path))
                if os.path.exists(logo_file):
                    try:
                        self_inner.image(logo_file, x=10, y=8, w=36)
                    except Exception:
                        pass
                self_inner.set_font('DejaVu' if font_path else 'Arial', 'B', 14)
                self_inner.cell(0, 10, f"{lab_name}", ln=1, align='R')

            def footer(self_inner):
                self_inner.set_y(-15)
                self_inner.set_font('DejaVu' if font_path else 'Arial', 'I', 8)
                self_inner.cell(0, 6, f"Generated: {timestamp}", align='L')
                self_inner.cell(0, 6, f"Page {self_inner.page_no()}", align='R')

        pdf_path = os.path.join(out_dir, f"report_{safe_name}_{timestamp}.pdf")
        pdf = PDF('P', 'mm', 'A4')
        pdf.set_auto_page_break(auto=True, margin=15)

        base_font = 'DejaVu' if font_path and os.path.exists(font_path) else 'Arial'
        if font_path and os.path.exists(font_path):
            try:
                pdf.add_font('DejaVu', '', font_path, uni=True)
                pdf.add_font('DejaVu', 'B', font_path, uni=True)
                base_font = 'DejaVu'
            except Exception:
                base_font = 'Arial'

        pdf.add_page()
        pdf.set_font(base_font, 'B', 12)
        pdf.cell(0, 8, f"{lab_name} — Report", ln=1)
        pdf.set_font(base_font, size=9)
        pdf.cell(0, 6, f"Generated: {timestamp}", ln=1)
        pdf.ln(4)

        pdf.set_font(base_font, 'B', 11)
        pdf.cell(0, 6, 'Metrics', ln=1)
        pdf.ln(2)
        pdf.set_font(base_font, size=10)
        for k, v in metrics.items():
            pdf.multi_cell(0, 6, f"{k}: {v}")

        if findings:
            pdf.add_page()
            pdf.set_font(base_font, 'B', 12)
            pdf.cell(0, 6, 'Clinical Findings', ln=1)
            pdf.ln(4)
            pdf.set_font(base_font, size=10)
            for k, v in findings.items():
                pdf.multi_cell(0, 6, f"{k}: {v}")
            pdf.ln(4)

        if image_paths:
            for caption, p in image_paths:
                img_path = os.path.join(out_dir, os.path.basename(p))
                if os.path.exists(img_path):
                    pdf.add_page()
                    pdf.set_font(base_font, 'B', 11)
                    pdf.multi_cell(0, 6, caption)
                    page_w = pdf.w - 2 * pdf.l_margin
                    try:
                        pdf.image(img_path, w=page_w)
                    except Exception:
                        pass

        if notes:
            pdf.add_page()
            pdf.set_font(base_font, 'B', 12)
            pdf.cell(0, 6, 'Notes', ln=1)
            pdf.ln(2)
            pdf.set_font(base_font, size=10)
            pdf.multi_cell(0, 6, notes)

        pdf.output(pdf_path)
    except Exception:
        pdf_path = None

    return pdf_path if pdf_path else html_path
