import os
import datetime
from typing import Dict, Any, List, Optional, Tuple

# Consolidación Visual Tanda 2 (2026-09-21): `app/reporting.py` es la
# superficie de mayor riesgo que encontró el diagnóstico de Tanda 1 -- el
# HTML/PDF exportado viaja FUERA de la app, sin contexto, en manos de un
# decano/médico/investigador que podría archivarlo o reenviarlo. Un export
# ciego (número sin procedencia) se lee como medición autorizada -- Art. I
# lo prohíbe tanto adentro de Streamlit como afuera. `MetricCardData`/
# `metric_card_to_html()`/`resolve_validation_marker()` son la MISMA
# fuente de honestidad que ya usa la app viva (`render_metric_card()`,
# Tanda 1) -- este módulo NO reimplementa qué badge/gramática/cita
# corresponde a cada valor, solo consume lo que `design_system.py` ya
# resolvió. Si mañana cambia un umbral o una cita, cambia en un solo
# lugar y ambos renderizadores (Streamlit vivo, HTML exportado) lo heredan.
from app.utils.design_system import MetricCardData, PALETTE, metric_card_to_html, resolve_validation_marker

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
        ax.set_facecolor(PALETTE.BACKGROUND)
        ax.text(0.5, 0.45, 'BSP', color=PALETTE.TEXT, fontsize=28, fontweight='bold', ha='center', va='center')
        ax.text(0.5, 0.12, 'Biomedical Signal Platform', color=PALETTE.ACCENT_ON_DARK, fontsize=8, ha='center')
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
        ax.plot(time, signal, color=PALETTE.PRIMARY, linewidth=0.8)
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
        ax.bar(labels, values, color=PALETTE.STABLE)
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
    honesty_cards: Optional[List[MetricCardData]] = None,
    validation: Optional[str] = None,
    validation_detail: Optional[str] = None,
) -> str:
    """Export a styled HTML report and an enriched PDF (if fpdf available).

    Parameters:
    - lab_name: title
    - metrics: key->value metrics (técnicos, sin honestidad de procedencia
      -- p.ej. `fs`, `length`, nombres de canal. NO uses este dict para
      valores clínicos que necesiten badge/cita; para esos, `honesty_cards`)
    - notes: additional text
    - findings: optional clinical findings or classification summary
      (texto plano preformateado -- se conserva por compatibilidad, pero
      NO lleva cita; para eso, igual, `honesty_cards`)
    - out_dir: folder to write
    - image_paths: optional list of (caption, path-to-png)
    - honesty_cards (Consolidación Visual Tanda 2, 2026-09-21): lista de
      `MetricCardData` -- CADA valor clínicamente relevante (DAR/TBR/χ/BAR
      y cualquier otro que un llamador construya vía `resolve_metric_
      card()`) con su badge de procedencia y/o clasificación clínica, su
      cita completa, y -- si el dato no está disponible -- el motivo
      textual exacto. Misma fuente que `render_metric_card()` usa dentro
      de la app (`design_system.py::resolve_metric_card()`); este módulo
      solo la formatea distinto (HTML autónomo en vez de `st.markdown`).
      Renderizada en su propia sección "Honestidad de procedencia", en
      HTML y en texto plano en el PDF -- nunca omitida, nunca rellenada
      con un número si el dato no está.
    - validation/validation_detail: jerarquía de confianza del módulo
      (Consolidación Visual Tanda 1, "validado"/"heuristico") -- mismo
      criterio que `render_module_header(validation=...)`, vía `resolve_
      validation_marker()` (fuente única). Un informe de un módulo
      heurístico no debe leerse con la misma autoridad que uno validado,
      tampoco fuera de la app.

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
        logo_html = (
            f'<div class="logo" style="display:inline-block;padding:12px 18px;'
            f'background:{PALETTE.SECONDARY_BACKGROUND};border-radius:12px;'
            f'color:{PALETTE.TEXT};font-weight:700;font-size:1rem;">BIOCORE AI</div>'
        )

    # Consolidación Visual Tanda 2 (2026-09-21): paleta migrada de 6 hex
    # propios (#071226/#cfe9ff/#99c7ff/#eaf6ff/#dfefff/#bcdff8, sin
    # relación con `PALETTE`) a los mismos tokens que ya usa la app viva
    # (`.streamlit/config.toml` + `design_system.PALETTE`) -- pantalla
    # primero, mismo tema oscuro que la app, sin variante de impresión
    # declarada (este export no se optimiza para papel hoy; si hiciera
    # falta un derivado de mayor contraste para impresión, se declara
    # explícitamente cuando se construya, no se deja como paleta huérfana
    # mientras tanto). `.honesty`/`.biocore-metric` (ver `metric_card_to_
    # html()`, `design_system.py`) son las tarjetas de honestidad --
    # mismo criterio visual que `render_metric_card()` en Streamlit.
    css = (
        f"body{{font-family:Inter, Arial, Helvetica, sans-serif; background:{PALETTE.BACKGROUND}; color:{PALETTE.TEXT}; margin:0;}}"
        f" .container{{max-width:980px;margin:18px auto;background:{PALETTE.SECONDARY_BACKGROUND};padding:22px;border-radius:14px;border:1px solid rgba(255,255,255,0.03);}}"
        " .header{display:flex;align-items:center;gap:12px;margin-bottom:14px;}"
        " .logo{height:60px;border-radius:8px;box-shadow:0 8px 20px rgba(0,0,0,0.45);}"
        f" .title{{font-size:1.6rem;color:{PALETTE.ACCENT_ON_DARK};margin:0;}}"
        f" .sub{{color:{PALETTE.TEXT};opacity:0.75;margin:0;font-size:0.9rem;}}"
        " .metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;margin:14px 0;}"
        f" .metric{{background:rgba(255,255,255,0.03);padding:10px;border-radius:8px;border:1px solid rgba(255,255,255,0.04);color:{PALETTE.TEXT};}}"
        " .fig{margin:10px 0;} img{max-width:100%;border-radius:8px;}"
        " .honesty{margin-top:14px;}"
        f" .findings{{background:{PALETTE.SECONDARY_BACKGROUND};padding:10px;border-radius:8px;margin-top:10px;color:{PALETTE.TEXT};}}"
        f" pre{{background:rgba(0,0,0,0.25);padding:12px;border-radius:8px;color:{PALETTE.TEXT};white-space:pre-wrap;}}"
    )

    # Consolidación Visual Tanda 2: jerarquía de confianza heredada en el
    # export -- mismo `resolve_validation_marker()` que usa `render_module_
    # header()` dentro de la app (Tanda 1, fuente única). Si `validation`
    # no es un nivel reconocido (o no se pasó), no se agrega nada --
    # mismo criterio permisivo de "no forzar" que la app viva.
    validation_html = ''
    marker = resolve_validation_marker(validation, validation_detail)
    if marker is not None:
        v_color, v_symbol, v_text = marker
        validation_html = (
            f'<div class="validation" style="border-left:3px solid {v_color}; padding:4px 10px; '
            f'margin-top:6px; color:{PALETTE.TEXT}; opacity:0.92; font-size:0.9rem;">'
            f'{v_symbol}&nbsp;&nbsp;{v_text}</div>'
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
        f'<div><h1 class="title">{lab_name}</h1><div class="sub">Generated: {timestamp}</div>{validation_html}</div>',
        '</div>',
        '<hr style="border:none;border-top:1px solid rgba(255,255,255,0.03);margin:12px 0;">',
        '<div class="metrics">',
    ]

    # Add metric cards (técnicos, sin honestidad de procedencia -- ver
    # `honesty_cards` más abajo para lo que sí lleva badge/cita)
    for k, v in metrics.items():
        html_lines.append(f'<div class="metric"><strong>{k}</strong><div style="font-size:1.1rem;margin-top:6px;color:{PALETTE.TEXT};">{v}</div></div>')

    html_lines += ['</div>']

    # Consolidación Visual Tanda 2: la sección que cierra la vulnerabilidad
    # de export ciego -- cada `MetricCardData` se formatea con
    # `metric_card_to_html()` (`design_system.py`), la MISMA resolución de
    # honestidad que `render_metric_card()` usa en la app viva. Nunca
    # omitida por falta de dato: un valor `unavailable` se exporta con su
    # `reason` textual completo (ver `metric_card_to_html`), nunca se cae
    # en silencio de la sección.
    if honesty_cards:
        html_lines.append('<div class="honesty"><h3>Honestidad de procedencia</h3>')
        for card in honesty_cards:
            html_lines.append(metric_card_to_html(card))
        html_lines.append('</div>')

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
    html_lines.append(f'<div style="font-size:0.9rem;color:{PALETTE.TEXT};opacity:0.75;">Recommended installs: <code>pip install plotly kaleido fpdf</code></div>')
    html_lines += ['</div>', '</body>', '</html>']

    # Write files and copy images (ensure images are in same dir)
    # NOTA (2026-09-21, hallazgo incidental de Consolidación Visual Tanda 2
    # -- bloqueaba la verificación por ejecución de esta misma tanda, no
    # relacionado con la honestidad): `logo_path` ya vive DENTRO de
    # `out_dir` (`_create_logo(logo_path)` arriba lo construye así) --
    # copiarlo "a `out_dir`" era copiarlo sobre sí mismo, y `shutil.
    # copyfile` lanza `SameFileError` en cuanto `_create_logo()` produce
    # un logo real (requiere matplotlib, disponible en este entorno) --
    # cualquier export con logo real crasheaba sin capturar la excepción
    # en ningún llamador. El logo no necesita copiarse -- ya está donde
    # tiene que estar.
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
        if marker is not None:
            _, v_symbol, v_text = marker
            pdf.multi_cell(0, 6, f"{v_symbol} {v_text}")
        pdf.ln(4)

        pdf.set_font(base_font, 'B', 11)
        pdf.cell(0, 6, 'Metrics', ln=1)
        pdf.ln(2)
        pdf.set_font(base_font, size=10)
        for k, v in metrics.items():
            pdf.multi_cell(0, 6, f"{k}: {v}")

        # Consolidación Visual Tanda 2: misma sección de honestidad que el
        # HTML (`honesty_cards`), en texto plano -- el PDF no pierde la
        # procedencia/cita/razón solo porque FPDF no tiene el HTML de
        # `metric_card_to_html()` disponible.
        if honesty_cards:
            pdf.ln(4)
            pdf.set_font(base_font, 'B', 11)
            pdf.cell(0, 6, 'Honestidad de procedencia', ln=1)
            pdf.ln(2)
            pdf.set_font(base_font, size=10)
            for card in honesty_cards:
                if not card.available:
                    pdf.multi_cell(0, 6, f"{card.label}: no disponible — {card.reason}")
                else:
                    detail = " — ".join(card.detail_parts)
                    line = f"{card.label}: {card.value}" + (f" — {detail}" if detail else "")
                    pdf.multi_cell(0, 6, line)

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
