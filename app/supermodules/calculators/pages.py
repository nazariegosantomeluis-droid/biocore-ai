"""🧮 Calculadoras Clínicas (2026-10-19) — Clinical Hub.

Fórmulas y escalas publicadas para practicar con números reales: QTc (4
correcciones), FC desde el papel del ECG, eje eléctrico, PAM/presión de
pulso/índice de choque, gasto e índice cardiaco, IMC/ASC, PAO₂ y gradiente
A–a con corrección por ALTITUD (Ciudad de México, Guadalajara, Toluca…),
PaO₂/FiO₂ (Berlín), NEWS2, qSOFA y Glasgow.

Separación de responsabilidades (mismo patrón que EEG con
`classify_dar()`/`render_metric_card()`): todo el cálculo, los umbrales y las
citas viven en `clinical/calculators.py` (funciones puras, probadas en
`tests/test_clinical_calculators.py`); esta página solo pide los datos y
dibuja el resultado con `render_metric_card()`.

Conexión con el gemelo digital: el botón "📥 Usar estos valores" copia la FC,
FR y SpO₂ que el gemelo de ESTA sesión tiene en ese momento -- etiquetadas
como simulación. El gemelo no modela presión arterial, temperatura ni
conciencia: esos campos siempre los captura el usuario (no se inventan).

Uso educativo: una clasificación es la lectura de un número contra el corte
que fija su referencia, nunca un diagnóstico.
"""
from __future__ import annotations

import datetime
import os
from typing import Dict, Optional, Tuple

import streamlit as st

from app.utils.design_system import (
    BADGES,
    MetricCardData,
    PALETTE,
    render_empty_state,
    render_error_state,
    render_metric_card,
    render_module_header,
    render_plate,
    resolve_metric_card,
)
from clinical import calculators as calc
from visualization.art.meters import news2_meter_svg

_REPORT_KEY = "calc_report_cards"

CALC_TABS = [
    ":material/ecg_heart: ECG",
    ":material/bloodtype: Hemodinamia",
    ":material/pulmonology: Oxigenación",
    ":material/monitor_weight: Antropometría",
    ":material/emergency: Escalas",
    ":material/description: Informe",
]

# Rango de cada campo numérico: (mínimo, máximo, paso, formato, valor inicial).
# Única fuente para el widget Y para recortar los valores que llegan del
# gemelo (un valor fuera de rango haría fallar el `number_input`).
_FIELDS: Dict[str, Tuple[float, float, float, str, float]] = {
    "calc_qtc_qt": (150.0, 700.0, 5.0, "%.0f", 400.0),
    "calc_qtc_hr": (20.0, 250.0, 1.0, "%.0f", 75.0),
    "calc_hrp_large": (0.5, 20.0, 0.5, "%.1f", 4.0),
    "calc_hrp_small": (2.0, 100.0, 1.0, "%.0f", 20.0),
    "calc_hrp_6s": (0.0, 40.0, 1.0, "%.0f", 8.0),
    "calc_hrp_rr": (200.0, 3000.0, 10.0, "%.0f", 800.0),
    "calc_axis_i": (-30.0, 30.0, 0.5, "%.1f", 6.0),
    "calc_axis_avf": (-30.0, 30.0, 0.5, "%.1f", 4.0),
    "calc_hemo_sbp": (40.0, 300.0, 1.0, "%.0f", 120.0),
    "calc_hemo_dbp": (20.0, 200.0, 1.0, "%.0f", 80.0),
    "calc_si_hr": (20.0, 250.0, 1.0, "%.0f", 75.0),
    "calc_co_hr": (20.0, 250.0, 1.0, "%.0f", 75.0),
    "calc_co_sv": (10.0, 200.0, 1.0, "%.0f", 70.0),
    "calc_co_weight": (2.0, 350.0, 0.5, "%.1f", 70.0),
    "calc_co_height": (40.0, 250.0, 1.0, "%.0f", 170.0),
    "calc_bmi_weight": (2.0, 350.0, 0.5, "%.1f", 70.0),
    "calc_bmi_height": (40.0, 250.0, 1.0, "%.0f", 170.0),
    "calc_oxy_altitude": (-400.0, 6000.0, 10.0, "%.0f", 2240.0),
    "calc_oxy_fio2": (0.21, 1.0, 0.01, "%.2f", 0.21),
    # Iniciales típicos de un adulto sano en la Ciudad de México (altitud por defecto).
    "calc_oxy_pao2": (20.0, 650.0, 1.0, "%.0f", 65.0),
    "calc_oxy_paco2": (10.0, 150.0, 1.0, "%.0f", 32.0),
    "calc_oxy_age": (0.0, 120.0, 1.0, "%.0f", 30.0),
    "calc_news_rr": (2.0, 70.0, 1.0, "%.0f", 16.0),
    "calc_news_spo2": (50.0, 100.0, 1.0, "%.0f", 98.0),
    "calc_news_sbp": (40.0, 300.0, 1.0, "%.0f", 120.0),
    "calc_news_pulse": (20.0, 250.0, 1.0, "%.0f", 75.0),
    "calc_news_temp": (30.0, 43.0, 0.1, "%.1f", 37.0),
    "calc_qsofa_rr": (2.0, 70.0, 1.0, "%.0f", 16.0),
    "calc_qsofa_sbp": (40.0, 300.0, 1.0, "%.0f", 120.0),
}

# Qué campos recibe cada signo vital del gemelo.
_TWIN_TARGETS = {
    "hr": ("calc_qtc_hr", "calc_si_hr", "calc_co_hr", "calc_news_pulse"),
    "rr": ("calc_news_rr", "calc_qsofa_rr"),
    "spo2": ("calc_news_spo2",),
}


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

def _num(label: str, key: str, help: Optional[str] = None) -> float:
    lo, hi, step, fmt, default = _FIELDS[key]
    if key not in st.session_state:
        st.session_state[key] = default
    return float(st.number_input(label, min_value=lo, max_value=hi, step=step, format=fmt, key=key, help=help))


def _card(report_id: str, label: str, value: Optional[str], *, classification=None, citation: Optional[str] = None,
          provenance: Optional[str] = BADGES.CLINICAL, unavailable_reason: Optional[str] = None) -> None:
    """Dibuja la tarjeta y guarda el mismo `MetricCardData` para el informe
    (una sola resolución de honestidad para la app y para el export)."""
    kwargs = dict(provenance=provenance, classification=classification, citation=citation,
                  unavailable_reason=unavailable_reason)
    render_metric_card(label, value, **kwargs)
    st.session_state.setdefault(_REPORT_KEY, {})[report_id] = resolve_metric_card(label, value, **kwargs)


def _forget(*report_ids: str) -> None:
    """Quita del informe resultados que dejaron de ser válidos con los datos actuales."""
    cards = st.session_state.get(_REPORT_KEY, {})
    for rid in report_ids:
        cards.pop(rid, None)


def _twin_vitals() -> Optional[Dict[str, float]]:
    """FC/FR/SpO₂ que el gemelo de ESTA sesión tiene ahora, o `None`."""
    organism = st.session_state.get("twin_shell_organism")
    if organism is None:
        return None
    organs = getattr(organism, "organs", {})
    heart, lungs = organs.get("heart"), organs.get("lungs")
    raw = {
        "hr": heart.metrics.signals.get("heart_rate") if heart else None,
        "rr": lungs.metrics.signals.get("respiratory_rate") if lungs else None,
        "spo2": lungs.metrics.signals.get("spo2") if lungs else None,
    }
    vitals = {k: float(v) for k, v in raw.items() if v is not None}
    return vitals or None


def _apply_twin_vitals() -> None:
    vitals = _twin_vitals() or {}
    for name, keys in _TWIN_TARGETS.items():
        if name not in vitals:
            continue
        for key in keys:
            lo, hi, _step, _fmt, _default = _FIELDS[key]
            st.session_state[key] = float(min(hi, max(lo, round(vitals[name]))))
    st.session_state["calc_twin_applied"] = dict(vitals)


def _render_twin_banner() -> None:
    vitals = _twin_vitals()
    with st.container(border=True):
        if not vitals:
            st.caption(
                "🧬 El gemelo digital todavía no tiene signos vitales en esta sesión — abre "
                "**Digital Twin OS** y vuelve aquí para poder importarlos."
            )
            return
        parts = []
        if "hr" in vitals:
            parts.append(f"FC {vitals['hr']:.0f} lpm")
        if "rr" in vitals:
            parts.append(f"FR {vitals['rr']:.0f} rpm")
        if "spo2" in vitals:
            parts.append(f"SpO₂ {vitals['spo2']:.0f} %")
        c1, c2 = st.columns([3, 2])
        with c1:
            st.markdown(f"🧬 **Gemelo digital (simulación):** {' · '.join(parts)}")
            st.caption(
                "Valores SIMULADOS por el gemelo, no mediciones de un paciente. El gemelo no modela "
                "presión arterial, temperatura ni nivel de conciencia: esos los capturas tú."
            )
        with c2:
            st.button("📥 Usar estos valores en las calculadoras", key="calc_use_twin",
                      on_click=_apply_twin_vitals, width="stretch")
        if st.session_state.get("calc_twin_applied"):
            st.caption("✅ Valores del gemelo copiados a FC (QTc, índice de choque, gasto cardiaco, NEWS2), "
                       "FR (NEWS2, qSOFA) y SpO₂ (NEWS2).")


# ═══════════════════════════════════════════════════════════════════════
# Pestañas
# ═══════════════════════════════════════════════════════════════════════

def _render_ecg_tab() -> None:
    st.markdown("#### QT corregido (QTc)")
    c1, c2, c3 = st.columns(3)
    with c1:
        qt = _num("QT medido (ms)", "calc_qtc_qt")
    with c2:
        hr = _num("Frecuencia cardiaca (lpm)", "calc_qtc_hr")
    with c3:
        sex = st.radio("Sexo", ["Hombre", "Mujer"], horizontal=True, key="calc_qtc_sex")
    st.latex(r"\text{Bazett}=\frac{QT}{\sqrt{RR}}\quad \text{Fridericia}=\frac{QT}{\sqrt[3]{RR}}\quad "
             r"\text{Framingham}=QT+154(1-RR)\quad \text{Hodges}=QT+1.75(FC-60)")
    results = calc.qtc_all(qt, hr)
    citations = {"Bazett": calc.BAZETT_CITATION, "Fridericia": calc.FRIDERICIA_CITATION,
                 "Framingham": calc.FRAMINGHAM_QTC_CITATION, "Hodges": calc.HODGES_CITATION}
    sex_code = "F" if sex == "Mujer" else "M"
    cols = st.columns(2)
    for i, (name, value) in enumerate(results.items()):
        with cols[i % 2]:
            _card(f"qtc_{name}", f"QTc {name}", f"{value:.0f} ms",
                  classification=calc.classify_qtc(value, sex_code), citation=citations[name])
    st.caption(f"RR = 60/FC = {60.0 / hr:.3f} s. Umbrales: {calc.QTC_THRESHOLDS_CITATION}; {calc.QTC_500_CITATION}. "
               "La misma guía recomienda corregir con funciones de regresión lineal (p. ej. Framingham, "
               "Hodges) en lugar de Bazett, que sobrecorrige a FC altas.")
    with st.expander("Lámina: dónde se mide el QT"):
        render_plate("ecg_complex", highlight="QT")

    st.markdown("---")
    st.markdown("#### Frecuencia cardiaca desde el trazo")
    method = st.radio("Método", ["Cuadros grandes (300/n)", "Cuadros pequeños (1500/n)",
                                 "Regla de los 6 segundos", "Intervalo RR (ms)"],
                      horizontal=True, key="calc_hrp_method")
    if method.startswith("Cuadros grandes"):
        rate = calc.hr_from_ecg_paper(large_squares=_num("Cuadros grandes entre dos R", "calc_hrp_large"))
    elif method.startswith("Cuadros pequeños"):
        rate = calc.hr_from_ecg_paper(small_squares=_num("Cuadros pequeños entre dos R", "calc_hrp_small"))
    elif method.startswith("Regla"):
        rate = calc.hr_six_second_method(_num("Complejos QRS en 6 segundos (30 cuadros grandes)", "calc_hrp_6s"))
    else:
        rate = calc.hr_from_rr_ms(_num("Intervalo RR (ms)", "calc_hrp_rr"))
    _card("hr_paper", "Frecuencia cardiaca", f"{rate:.0f} lpm",
          classification=calc.classify_heart_rate(rate), citation=calc.ECG_PAPER_CITATION)

    st.markdown("---")
    st.markdown("#### Eje eléctrico del QRS (DI y aVF)")
    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        net_i = _num("QRS neto en DI (mm, R − S)", "calc_axis_i")
    with c2:
        net_avf = _num("QRS neto en aVF (mm, R − S)", "calc_axis_avf")
    try:
        axis = calc.qrs_axis_degrees(net_i, net_avf)
    except ValueError as exc:
        _forget("qrs_axis")
        with c3:
            render_error_state(str(exc))
        return
    with c3:
        _card("qrs_axis", "Eje del QRS", f"{axis:+.0f}°", classification=calc.classify_qrs_axis(axis),
              citation=calc.QRS_AXIS_CITATION)
    # Rediseño visual (2026-10-19): el eje calculado se marca sobre la lámina
    # del sistema hexaxial (antes un dial polar de Plotly sin rótulos de
    # derivación legibles).
    render_plate("hexaxial", axis_deg=axis)


# `_render_axis_dial()` (dial polar de Plotly) se retiró el 2026-10-19: su
# único llamador ahora dibuja la lámina hexaxial con el eje marcado.


def _render_hemodynamics_tab() -> None:
    st.markdown("#### Presión arterial media, presión de pulso e índice de choque")
    c1, c2, c3 = st.columns(3)
    with c1:
        sbp = _num("Presión sistólica (mmHg)", "calc_hemo_sbp")
    with c2:
        dbp = _num("Presión diastólica (mmHg)", "calc_hemo_dbp")
    with c3:
        hr = _num("Frecuencia cardiaca (lpm)", "calc_si_hr")
    st.latex(r"PAM \approx PAD + \frac{PAS-PAD}{3}\qquad PP = PAS - PAD\qquad IC_{choque} = \frac{FC}{PAS}")
    if dbp >= sbp:
        _forget("map", "pulse_pressure", "shock_index")
        render_error_state("La presión diastólica debe ser menor que la sistólica.")
    else:
        mapv = calc.mean_arterial_pressure(sbp, dbp)
        si = calc.shock_index(hr, sbp)
        cols = st.columns(3)
        with cols[0]:
            _card("map", "PAM", f"{mapv:.0f} mmHg", classification=calc.classify_map(mapv),
                  citation=calc.MAP_TARGET_CITATION)
        with cols[1]:
            _card("pulse_pressure", "Presión de pulso", f"{calc.pulse_pressure(sbp, dbp):.0f} mmHg")
        with cols[2]:
            _card("shock_index", "Índice de choque", f"{si:.2f}", classification=calc.classify_shock_index(si),
                  citation=calc.SHOCK_INDEX_CITATION)

    st.markdown("---")
    st.markdown("#### Gasto cardiaco e índice cardiaco")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        hr_co = _num("FC (lpm)", "calc_co_hr")
    with c2:
        sv = _num("Volumen sistólico (ml)", "calc_co_sv",
                  help="El que tengas medido (ecocardiograma, termodilución) — la calculadora no lo estima.")
    with c3:
        weight = _num("Peso (kg)", "calc_co_weight")
    with c4:
        height = _num("Talla (cm)", "calc_co_height")
    co = calc.cardiac_output_l_min(hr_co, sv)
    bsa = calc.bsa_mosteller(height, weight)
    ci = calc.cardiac_index(co, bsa)
    st.latex(r"GC = FC \times VS \qquad IC = \frac{GC}{ASC}")
    cols = st.columns(2)
    with cols[0]:
        _card("cardiac_output", "Gasto cardiaco", f"{co:.2f} L/min")
    with cols[1]:
        _card("cardiac_index", "Índice cardiaco", f"{ci:.2f} L/min/m²",
              classification=calc.classify_cardiac_index(ci), citation=calc.FORRESTER_CITATION)
    st.caption(f"ASC usada: {bsa:.2f} m² (Mosteller).")


def _render_oxygenation_tab() -> None:
    st.markdown("#### PAO₂, gradiente alvéolo-arterial y PaO₂/FiO₂")
    places = list(calc.CITY_ALTITUDES_M) + ["Otra altitud"]
    c1, c2 = st.columns(2)
    with c1:
        place = st.selectbox("¿Dónde se tomó la gasometría?", places,
                             index=places.index("Ciudad de México"), key="calc_oxy_place")
    with c2:
        if place == "Otra altitud":
            altitude = _num("Altitud (m s. n. m.)", "calc_oxy_altitude")
        else:
            altitude = calc.CITY_ALTITUDES_M[place]
            st.metric("Altitud aproximada", f"{altitude:.0f} m")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        fio2 = _num("FiO₂ (fracción)", "calc_oxy_fio2", help="0.21 = aire ambiente. Escribe 0.40, no 40.")
    with c2:
        pao2 = _num("PaO₂ (mmHg)", "calc_oxy_pao2")
    with c3:
        paco2 = _num("PaCO₂ (mmHg)", "calc_oxy_paco2")
    with c4:
        age = _num("Edad (años)", "calc_oxy_age")

    patm = calc.barometric_pressure_mmhg(altitude)
    alveolar = calc.alveolar_po2(fio2, paco2, patm)
    gradient = alveolar - pao2
    pf = calc.pf_ratio(pao2, fio2)
    st.latex(r"P_AO_2 = FiO_2\,(P_{atm} - 47) - \frac{PaCO_2}{0.8}\qquad A\text{–}a = P_AO_2 - PaO_2")

    cols = st.columns(2)
    with cols[0]:
        _card("patm", "Presión barométrica estimada", f"{patm:.0f} mmHg", provenance=BADGES.HEURISTIC,
              citation=calc.ISA_CITATION)
        _card("pao2_alveolar", "PAO₂ (alveolar)", f"{alveolar:.0f} mmHg", citation=calc.ALVEOLAR_GAS_CITATION)
    with cols[1]:
        if abs(fio2 - 0.21) < 1e-9:
            expected = calc.expected_aa_gradient(age)
            classification = (
                ("leve", f"mayor que el esperado para la edad (≈{expected:.0f} mmHg)", "🟡")
                if gradient > expected else
                ("normal", f"dentro del esperado para la edad (≈{expected:.0f} mmHg)", "🟢")
            )
            _card("aa_gradient", "Gradiente A–a", f"{gradient:.0f} mmHg", classification=classification,
                  provenance=BADGES.HEURISTIC,
                  citation="valor esperado por la regla clínica habitual edad/4 + 4 (aire ambiente)")
        else:
            _card("aa_gradient", "Gradiente A–a", f"{gradient:.0f} mmHg",
                  citation="la regla del valor esperado (edad/4 + 4) solo aplica en aire ambiente")
        _card("pf_ratio", "PaO₂/FiO₂", f"{pf:.0f} mmHg", classification=calc.classify_pf_ratio(pf),
              citation=calc.BERLIN_CITATION)
    _render_altitude_chart(altitude, fio2, paco2, place)
    st.caption(
        "Por qué importa la altitud: en la Ciudad de México la presión barométrica es ~580 mmHg, así "
        "que la PAO₂ en aire ambiente ronda 60 mmHg en lugar de ~100 al nivel del mar — una PaO₂ que "
        "sería baja en la costa puede ser normal ahí. La P/F es solo el criterio de oxigenación de "
        "Berlín: el diagnóstico de SDRA exige además PEEP ≥5 cmH₂O, temporalidad, imagen y origen no "
        "cardiogénico."
    )


def _render_altitude_chart(altitude: float, fio2: float, paco2: float, place: str) -> None:
    """PAO₂ esperada vs. altitud con TUS FiO₂ y PaCO₂ (rediseño visual
    2026-10-19). Misma ecuación y presión estándar que las tarjetas de
    arriba (`calc.alveolar_po2`, `calc.barometric_pressure_mmhg`): la curva
    es esa fórmula evaluada de 0 a 3 200 m, con las ciudades marcadas."""
    try:
        import numpy as np
        import plotly.graph_objects as go
    except ImportError:
        return
    xs = np.linspace(0, 3200, 81)
    ys = [calc.alveolar_po2(fio2, paco2, calc.barometric_pressure_mmhg(h)) for h in xs]
    series = "#3987e5"  # slot 1 de chartCategoricalColors
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color=series, width=2), name="PAO₂",
                             hovertemplate="%{x:.0f} m: PAO₂ %{y:.0f} mmHg<extra></extra>"))
    cities = list(calc.CITY_ALTITUDES_M.items())
    cy = [calc.alveolar_po2(fio2, paco2, calc.barometric_pressure_mmhg(h)) for _, h in cities]
    # Rótulos directos: Puebla y Ciudad de México están a ~100 m de distancia,
    # así que se reparten arriba/abajo para no encimarse.
    positions = {"Nivel del mar": "bottom right", "Puebla": "top left", "Ciudad de México": "bottom right"}
    fig.add_trace(go.Scatter(
        x=[h for _, h in cities], y=cy, mode="markers+text", text=[n for n, _ in cities],
        textposition=[positions.get(n, "top right") for n, _ in cities],
        textfont=dict(color=PALETTE.TEXT, size=12),
        marker=dict(size=9, color=series, line=dict(width=2, color=PALETTE.BACKGROUND)),
        hovertemplate="%{text}: %{x:.0f} m, PAO₂ %{y:.0f} mmHg<extra></extra>", name="ciudades",
    ))
    here = calc.alveolar_po2(fio2, paco2, calc.barometric_pressure_mmhg(altitude))
    fig.add_trace(go.Scatter(x=[altitude], y=[here], mode="markers", name="tu gasometría",
                             marker=dict(size=16, color=PALETTE.TRACE, symbol="circle-open", line=dict(width=3)),
                             hovertemplate=f"{place}: PAO₂ %{{y:.0f}} mmHg<extra></extra>"))
    fig.update_layout(height=320, showlegend=False, margin=dict(l=50, r=20, t=40, b=45),
                      title=dict(text=f"PAO₂ esperada según la altitud (FiO₂ {fio2:.2f}, PaCO₂ {paco2:.0f} mmHg)",
                                 font=dict(size=14)),
                      xaxis_title="Altitud (m s. n. m.)", yaxis_title="PAO₂ (mmHg)")
    lo, hi = float(min(ys)), float(max(ys))
    fig.update_yaxes(range=[lo - 0.08 * (hi - lo) - 2, hi + 0.12 * (hi - lo) + 2])
    st.plotly_chart(fig, width="stretch", key="calc_altitude_chart")


def _render_anthropometry_tab() -> None:
    st.markdown("#### Índice de masa corporal y área de superficie corporal")
    c1, c2 = st.columns(2)
    with c1:
        weight = _num("Peso (kg)", "calc_bmi_weight")
    with c2:
        height = _num("Talla (cm)", "calc_bmi_height")
    bmi = calc.body_mass_index(weight, height)
    st.latex(r"IMC = \frac{peso}{talla^2}\quad ASC_{Mosteller}=\sqrt{\frac{talla\cdot peso}{3600}}\quad "
             r"ASC_{DuBois}=0.007184\,peso^{0.425}\,talla^{0.725}")
    cols = st.columns(3)
    with cols[0]:
        _card("bmi", "IMC", f"{bmi:.1f} kg/m²", classification=calc.classify_bmi(bmi), citation=calc.WHO_BMI_CITATION)
    with cols[1]:
        _card("bsa_mosteller", "ASC (Mosteller)", f"{calc.bsa_mosteller(height, weight):.2f} m²",
              citation=calc.MOSTELLER_CITATION)
    with cols[2]:
        _card("bsa_dubois", "ASC (Du Bois)", f"{calc.bsa_dubois(height, weight):.2f} m²",
              citation=calc.DUBOIS_CITATION)
    st.caption("Las categorías de IMC de la OMS son para adultos; en niños y adolescentes se usan percentiles por edad y sexo.")


def _render_scores_tab() -> None:
    st.markdown("#### NEWS2 — National Early Warning Score 2")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        rr = _num("Frecuencia respiratoria (rpm)", "calc_news_rr")
        spo2 = _num("SpO₂ (%)", "calc_news_spo2")
    with c2:
        scale = st.radio("Escala de SpO₂", [1, 2], horizontal=True, key="calc_news_scale",
                         help="Escala 2 solo para insuficiencia respiratoria hipercápnica con objetivo prescrito de 88–92 %.")
        on_o2 = st.checkbox("Recibe oxígeno suplementario", key="calc_news_o2")
    with c3:
        sbp = _num("Presión sistólica (mmHg)", "calc_news_sbp")
        pulse = _num("Pulso (lpm)", "calc_news_pulse")
    with c4:
        consciousness = st.radio("Conciencia (ACVPU)", ["Alerta", "C/V/P/U (confusión nueva, voz, dolor, no responde)"],
                                 key="calc_news_acvpu")
        temp = _num("Temperatura (°C)", "calc_news_temp")
    news = calc.news2_score(respiratory_rate=rr, spo2=spo2, on_oxygen=on_o2, systolic_bp=sbp, pulse=pulse,
                            alert=consciousness == "Alerta", temperature_c=temp, spo2_scale=int(scale))
    _card("news2", "NEWS2", f"{news.total} puntos", classification=calc.classify_news2(news),
          citation=calc.NEWS2_CITATION)
    st.markdown(
        f"<div class='bc-meter'>{news2_meter_svg(news.total, any_single_3=news.any_single_3)}</div>",
        unsafe_allow_html=True,
    )
    st.dataframe(
        [{"Parámetro": k, "Puntos": v} for k, v in news.components.items()],
        hide_index=True, width="stretch",
    )

    st.markdown("---")
    st.markdown("#### qSOFA (Sepsis-3)")
    c1, c2, c3 = st.columns(3)
    with c1:
        q_rr = _num("Frecuencia respiratoria (rpm)", "calc_qsofa_rr")
    with c2:
        q_sbp = _num("Presión sistólica (mmHg)", "calc_qsofa_sbp")
    with c3:
        altered = st.checkbox("Alteración del estado mental (Glasgow <15)", key="calc_qsofa_mental")
    q = calc.qsofa_score(respiratory_rate=q_rr, systolic_bp=q_sbp, altered_mentation=altered)
    _card("qsofa", "qSOFA", f"{q}/3", classification=calc.classify_qsofa(q), citation=calc.QSOFA_CITATION)
    st.caption(f"⚠️ {calc.QSOFA_SCREENING_CAVEAT}")

    st.markdown("---")
    st.markdown("#### Escala de coma de Glasgow")
    c1, c2, c3 = st.columns(3)
    with c1:
        eye = st.selectbox("Apertura ocular (O)", sorted(calc.GCS_EYE, reverse=True),
                           format_func=lambda v: f"{v} — {calc.GCS_EYE[v]}", key="calc_gcs_eye")
    with c2:
        verbal = st.selectbox("Respuesta verbal (V)", sorted(calc.GCS_VERBAL, reverse=True),
                              format_func=lambda v: f"{v} — {calc.GCS_VERBAL[v]}", key="calc_gcs_verbal")
    with c3:
        motor = st.selectbox("Respuesta motora (M)", sorted(calc.GCS_MOTOR, reverse=True),
                             format_func=lambda v: f"{v} — {calc.GCS_MOTOR[v]}", key="calc_gcs_motor")
    gcs = calc.glasgow_coma_scale(eye, verbal, motor)
    _card("gcs", "Glasgow", f"{gcs}/15 (O{eye} V{verbal} M{motor})", classification=calc.classify_gcs(gcs),
          citation=calc.GCS_CITATION)


def _render_report_tab() -> None:
    cards: Dict[str, MetricCardData] = st.session_state.get(_REPORT_KEY, {})
    if not cards:
        render_empty_state("Todavía no hay resultados para el informe.")
        return
    st.markdown(f"#### Informe — {len(cards)} resultados con los datos actuales de todas las pestañas")
    notes = st.text_area("Notas (opcional)", key="calc_report_notes",
                         placeholder="Contexto del caso, objetivo de la práctica…")
    if st.button("📄 Generar informe (PDF/HTML)", key="calc_report_build"):
        try:
            from app.reporting import export_lab_report
            path = export_lab_report(
                "Calculadoras Clínicas",
                {"Fecha": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "Resultados": len(cards)},
                notes=(notes or "") + "\n\nUso educativo — cada resultado incluye su fórmula/cita; una "
                                       "clasificación no es un diagnóstico.",
                out_dir="reports",
                honesty_cards=list(cards.values()),
            )
            st.session_state["calc_report_path"] = path
        except Exception as exc:  # noqa: BLE001 -- se muestra limpio, la traza va al log
            render_error_state("No se pudo generar el informe.", exception=exc)
    path = st.session_state.get("calc_report_path")
    if path and os.path.exists(path):
        is_pdf = path.lower().endswith(".pdf")
        with open(path, "rb") as fh:
            st.download_button(
                "⬇️ Descargar " + ("PDF" if is_pdf else "HTML"), fh.read(), file_name=os.path.basename(path),
                mime="application/pdf" if is_pdf else "text/html", key="calc_report_download",
            )
        st.caption(f"Guardado también en `{path}`.")


def run() -> None:
    # validation=None deliberado (ver render_module_header): cada fórmula
    # trae su propia cita en su tarjeta, pero el módulo como conjunto aún no
    # tiene firma del experto -- una etiqueta única mentiría sobre alguna parte.
    render_module_header(
        "Calculadoras Clínicas", icon="🧮", art="calculators",
        subtitle="Fórmulas y escalas publicadas, cada una con su cita. Uso educativo — "
                 "una clasificación es la lectura de un número, no un diagnóstico.",
        validation=None,
    )
    _render_twin_banner()
    # Íconos Material (incluidos en Streamlit, sin internet) en vez de emoji.
    tabs = st.tabs(CALC_TABS)
    with tabs[0]:
        _render_ecg_tab()
    with tabs[1]:
        _render_hemodynamics_tab()
    with tabs[2]:
        _render_oxygenation_tab()
    with tabs[3]:
        _render_anthropometry_tab()
    with tabs[4]:
        _render_scores_tab()
    with tabs[5]:
        _render_report_tab()
