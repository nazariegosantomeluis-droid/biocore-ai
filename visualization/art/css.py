"""CSS de las ilustraciones y del encabezado de módulo (2026-10-19).

Una sola fuente: `inject_global_theme()` (app/utils/design_system.py) lo
inyecta en la app y `tests/` / el atlas de vista previa lo reutilizan.
Prefijo `bc-` en todas las clases (y ninguno de los nombres retirados en la
Consolidación Visual Tanda 1: no hay `.biocore-card`, `.biocore-panel`,
`.status-pill` ni `.pulse-dot`).
"""

from visualization.art import tokens as T

ART_CSS = f"""
.bc-head{{margin:0 0 4px 0}}
.bc-crumb{{font-size:.875rem;line-height:1.4;color:{T.INK_3};margin:0 0 6px 0}}
.bc-crumb span{{padding:0 .4em;color:{T.LINE}}}
.bc-title-row{{display:flex;align-items:center;gap:14px}}
.bc-glyph{{flex:0 0 48px;width:48px;height:48px;display:grid;place-items:center;border-radius:12px;
  color:{T.TRACE};background:rgba(34,211,238,.10);box-shadow:inset 0 0 0 1px rgba(34,211,238,.22)}}
div.bc-head h1{{margin:0;padding:0;font-family:{T.FONT_HEAD};font-weight:700;font-size:2.25rem;
  line-height:1.15;letter-spacing:-.01em;color:#f1f5ff}}
.bc-sub{{margin:8px 0 0 0;max-width:72ch;color:{T.INK_2};font-size:1rem;line-height:1.55}}
.bc-strip{{margin:14px 0 12px 0;height:64px;border-radius:10px;overflow:hidden;
  border:1px solid rgba(34,211,238,.16);background:{T.STRIP_BG}}}
.bc-strip svg{{display:block;width:100%;height:100%}}
.bc-draw{{stroke-dasharray:1;stroke-dashoffset:1;animation:bc-draw 1.8s cubic-bezier(.22,.7,.2,1) .1s forwards}}
@keyframes bc-draw{{to{{stroke-dashoffset:0}}}}

.bc-plate{{margin:6px 0 18px 0;padding:14px 16px 12px 16px;border-radius:14px;background:{T.PANEL};
  border:1px solid rgba(148,163,209,.18)}}
.bc-plate-top{{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:10px}}
.bc-plate-topic{{font-size:.8125rem;color:{T.INK_3}}}
.bc-plate-art svg{{display:block;width:100%;height:auto;max-height:560px}}
.bc-render{{position:relative;width:100%;max-width:720px;margin:0 auto;border-radius:12px;overflow:hidden;
  background:radial-gradient(ellipse at 50% 42%,#16244a 0%,{T.BACKGROUND} 72%)}}
.bc-render-img{{display:block;width:100%;height:100%;object-fit:contain}}
.bc-render svg.bc-render-layer,.bc-plate-art .bc-render svg.bc-render-layer{{position:absolute;inset:0;width:100%;
  height:100%;max-height:none;pointer-events:none}}
.bc-render-tall{{max-width:460px}}
.bc-render-pair{{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:10px}}
.bc-organ-img{{display:block;width:104px;height:104px;object-fit:contain;margin:0 auto 2px auto}}
.bc-glyph img.bc-organ-icon{{width:44px;height:44px;object-fit:contain}}
.bc-plate figcaption{{margin-top:12px;color:{T.INK_2};font-size:.9375rem;line-height:1.55}}
.bc-plate figcaption p{{margin:.35em 0}}
.bc-plate figcaption ul,.bc-plate figcaption ol{{margin:.3em 0 .4em 1.2em;padding:0}}
.bc-plate figcaption li{{margin:.15em 0}}
.bc-plate figcaption strong{{color:{T.INK}}}
.bc-plate-title{{display:block;font-family:{T.FONT_HEAD};font-size:1.125rem;font-weight:700;margin-bottom:2px}}
.bc-steps li.bc-on{{color:{T.INK}}}
.bc-steps li.bc-on::marker{{color:{T.TRACE};font-weight:700}}
.bc-src{{margin-top:8px;font-size:.8125rem;color:{T.INK_3}}}
.bc-src summary{{cursor:pointer;min-height:32px;display:inline-flex;align-items:center;color:{T.INK_2}}}
.bc-src ul{{margin:.2em 0 0 1.1em}}
.bc-chip{{display:inline-block;font-size:.75rem;line-height:1.5;padding:1px 9px;border-radius:999px;
  color:#a5f3fc;border:1px solid rgba(34,211,238,.38);background:rgba(34,211,238,.06)}}

.bc-legend{{display:flex;flex-wrap:wrap;gap:6px 18px;margin:0 0 10px 0;font-size:.875rem;color:{T.INK_2}}}
.bc-legend i{{display:inline-block;width:16px;height:3px;border-radius:2px;margin-right:6px;vertical-align:middle}}
.bc-tiles{{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:12px}}
.bc-tile{{padding:10px;border-radius:12px;background:{T.BACKGROUND};border:1px solid rgba(148,163,209,.16)}}
.bc-tile.bc-on{{border-color:{T.TRACE};box-shadow:inset 0 0 0 1px {T.TRACE}}}
.bc-tile-head{{display:flex;align-items:center;justify-content:space-between;gap:6px;margin-bottom:6px;
  color:{T.INK};font-size:.9375rem}}
.bc-tile svg{{display:block;width:100%;height:auto}}
.bc-tile p{{margin:6px 0 0 0;font-size:.8125rem;line-height:1.45;color:{T.INK_2}}}

.bc-organ{{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;
  height:150px;box-sizing:border-box;padding:12px 8px;border-radius:18px;text-align:center;
  background:rgba(255,255,255,.03)}}
.bc-organ-name{{font-weight:600;font-size:.8125rem;line-height:1.2;margin-top:2px;color:{T.INK}}}
.bc-organ-note{{font-size:.6875rem;color:{T.INK_3}}}

.bc-brand{{display:flex;align-items:center;gap:12px;margin:2px 0 6px 0}}
.bc-brand-name{{font-family:{T.FONT_HEAD};font-weight:700;font-size:1.25rem;letter-spacing:.01em;color:#f1f5ff}}
.bc-brand-tag{{font-size:.8125rem;color:{T.INK_3};line-height:1.3}}
.bc-status{{display:grid;gap:8px;font-size:.8125rem;line-height:1.35;color:{T.INK_2}}}
.bc-status-row{{display:flex;gap:9px;align-items:flex-start}}
.bc-status-row b{{display:block;color:{T.INK};font-weight:600}}
.bc-dot{{flex:0 0 10px;width:10px;height:10px;margin-top:3px;border-radius:50%}}
.bc-meter{{margin:4px 0 14px 0}}
.bc-meter svg{{display:block;width:100%;max-width:680px;height:auto}}

@media (prefers-reduced-motion: reduce){{
  .bc-draw{{animation:none;stroke-dasharray:none;stroke-dashoffset:0}}
}}
@media (max-width: 640px){{
  div.bc-head h1{{font-size:1.75rem}}
  .bc-glyph{{flex-basis:40px;width:40px;height:40px}}
  .bc-strip{{height:52px}}
  .bc-plate{{padding:12px}}
}}
"""
