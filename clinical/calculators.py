"""Calculadoras clínicas deterministas (2026-10-19).

Funciones puras -- sin Streamlit, sin estado -- para la página
"🧮 Calculadoras Clínicas" (`app/supermodules/calculators/pages.py`).
Cada fórmula o escala publicada lleva su cita en una constante `*_CITATION`
(mismo estándar que `DAR_CITATION`/`CHI_CITATION`) y cada clasificación
devuelve la tupla `(nivel, etiqueta, badge)` que ya consume
`app/utils/design_system.resolve_metric_card()` -- con `nivel` en
{"normal", "leve", "severo", "no_disponible"}.

Reglas de honestidad (Art. I):
- Ningún umbral inventado: si la referencia no fija un corte, no se clasifica
  (o se declara como regla clínica habitual, no como estándar validado).
- Una clasificación es una lectura del número, nunca un diagnóstico.
- Las implementaciones se verifican en `tests/test_clinical_calculators.py`
  contra ejemplos resueltos a mano o publicados.

Uso educativo. No sustituye el juicio clínico.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

Classification = Tuple[str, str, str]

_NOT_AVAILABLE: Classification = ("no_disponible", "no disponible", "")

# ═══════════════════════════════════════════════════════════════════════
# CITAS
# ═══════════════════════════════════════════════════════════════════════

BAZETT_CITATION = "Bazett HC. An analysis of the time-relations of electrocardiograms. Heart 1920;7:353–370"
FRIDERICIA_CITATION = (
    "Fridericia LS. Die Systolendauer im Elektrokardiogramm bei normalen Menschen und bei "
    "Herzkranken. Acta Med Scand 1920;53:469–486"
)
FRAMINGHAM_QTC_CITATION = (
    "Sagie A, Larson MG, Goldberg RJ, Bengtson JR, Levy D. An improved method for adjusting the QT "
    "interval for heart rate (the Framingham Heart Study). Am J Cardiol 1992;70:797–801"
)
HODGES_CITATION = (
    "Hodges M, Salerno D, Erlien D. Bazett's QT correction reviewed: evidence that a linear QT "
    "correction for heart rate is better. J Am Coll Cardiol 1983;1:694"
)
QTC_THRESHOLDS_CITATION = (
    "Rautaharju PM, Surawicz B, Gettes LS. AHA/ACCF/HRS Recommendations for the Standardization and "
    "Interpretation of the Electrocardiogram, Part IV. Circulation 2009;119:e241–e250 "
    "(prolongado ≥450 ms hombres / ≥460 ms mujeres; corto ≤390 ms)"
)
QTC_500_CITATION = (
    "Drew BJ, Ackerman MJ, Funk M, et al. Prevention of torsade de pointes in hospital settings: "
    "AHA/ACCF scientific statement. Circulation 2010;121:1047–1060 (QTc >500 ms: riesgo marcado)"
)
ECG_PAPER_CITATION = (
    "Kligfield P, Gettes LS, Bailey JJ, et al. Recommendations for the standardization and "
    "interpretation of the electrocardiogram, Part I. Circulation 2007;115:1306–1324 "
    "(registro estándar a 25 mm/s: cuadro pequeño = 0.04 s, grande = 0.20 s)"
)
QRS_AXIS_CITATION = (
    "Surawicz B, Knilans TK. Chou's Electrocardiography in Clinical Practice, 6th ed. "
    "Saunders Elsevier; 2008 (eje normal del adulto −30° a +90°; misma convención que "
    "src/signals/ecg/twelve_lead_analyzer.py)"
)
MAP_TARGET_CITATION = (
    "Evans L, Rhodes A, Alhazzani W, et al. Surviving Sepsis Campaign: International Guidelines for "
    "Management of Sepsis and Septic Shock 2021. Crit Care Med 2021;49:e1063–e1143 "
    "(objetivo inicial de PAM 65 mmHg en choque séptico)"
)
SHOCK_INDEX_CITATION = (
    "Allgöwer M, Burri C. 'Schockindex'. Dtsch Med Wochenschr 1967;92:1947–1950 "
    "(rango normal 0.5–0.7)"
)
FORRESTER_CITATION = (
    "Forrester JS, Diamond G, Chatterjee K, Swan HJ. Medical therapy of acute myocardial infarction "
    "by application of hemodynamic subsets. N Engl J Med 1976;295:1356–1362 "
    "(índice cardiaco <2.2 L/min/m²: hipoperfusión)"
)
WHO_BMI_CITATION = (
    "WHO. Obesity: preventing and managing the global epidemic. WHO Technical Report Series 894. "
    "Geneva: WHO; 2000"
)
MOSTELLER_CITATION = "Mosteller RD. Simplified calculation of body-surface area. N Engl J Med 1987;317:1098"
DUBOIS_CITATION = (
    "Du Bois D, Du Bois EF. A formula to estimate the approximate surface area if height and weight "
    "be known. Arch Intern Med 1916;17:863–871"
)
BERLIN_CITATION = (
    "ARDS Definition Task Force (Ranieri VM, et al.). Acute respiratory distress syndrome: the Berlin "
    "Definition. JAMA 2012;307:2526–2533 (con PEEP/CPAP ≥5 cmH₂O: leve 200–300, moderado 100–200, "
    "grave ≤100 mmHg)"
)
ALVEOLAR_GAS_CITATION = (
    "Ecuación del gas alveolar, forma simplificada: PAO₂ = FiO₂·(Patm − PH₂O) − PaCO₂/R "
    "(PH₂O = 47 mmHg a 37 °C, R = 0.8)"
)
ISA_CITATION = (
    "Atmósfera estándar internacional (ISO 2533:1975 / ICAO): P = 760·(1 − 2.25577·10⁻⁵·h)^5.25588 "
    "mmHg -- estimación; la presión real varía con el clima"
)
NEWS2_CITATION = (
    "Royal College of Physicians. National Early Warning Score (NEWS) 2: Standardising the "
    "assessment of acute-illness severity in the NHS. London: RCP; 2017"
)
QSOFA_CITATION = (
    "Seymour CW, Liu VX, Iwashyna TJ, et al. Assessment of clinical criteria for sepsis (Sepsis-3). "
    "JAMA 2016;315:762–774; Singer M, et al. The Third International Consensus Definitions for "
    "Sepsis and Septic Shock (Sepsis-3). JAMA 2016;315:801–810"
)
QSOFA_SCREENING_CAVEAT = (
    "La guía Surviving Sepsis Campaign 2021 recomienda NO usar qSOFA como herramienta única de "
    "tamizaje de sepsis, frente a SIRS, NEWS o MEWS (Evans L, et al. Crit Care Med 2021)."
)
GCS_CITATION = (
    "Teasdale G, Jennett B. Assessment of coma and impaired consciousness. A practical scale. "
    "Lancet 1974;2:81–84"
)


def _positive(*values: float) -> bool:
    return all(v is not None and math.isfinite(v) and v > 0 for v in values)


# ═══════════════════════════════════════════════════════════════════════
# ECG
# ═══════════════════════════════════════════════════════════════════════

def rr_seconds_from_hr(hr_bpm: float) -> float:
    if not _positive(hr_bpm):
        raise ValueError("la frecuencia cardiaca debe ser > 0")
    return 60.0 / hr_bpm


def hr_from_rr_ms(rr_ms: float) -> float:
    if not _positive(rr_ms):
        raise ValueError("el intervalo RR debe ser > 0")
    return 60000.0 / rr_ms


def qtc_bazett(qt_ms: float, rr_s: float) -> float:
    """QTc = QT / √RR (RR en segundos)."""
    if not _positive(qt_ms, rr_s):
        raise ValueError("QT y RR deben ser > 0")
    return qt_ms / math.sqrt(rr_s)


def qtc_fridericia(qt_ms: float, rr_s: float) -> float:
    """QTc = QT / ∛RR (RR en segundos)."""
    if not _positive(qt_ms, rr_s):
        raise ValueError("QT y RR deben ser > 0")
    return qt_ms / rr_s ** (1.0 / 3.0)


def qtc_framingham(qt_ms: float, rr_s: float) -> float:
    """QTc = QT + 154·(1 − RR) (ms; RR en segundos)."""
    if not _positive(qt_ms, rr_s):
        raise ValueError("QT y RR deben ser > 0")
    return qt_ms + 154.0 * (1.0 - rr_s)


def qtc_hodges(qt_ms: float, hr_bpm: float) -> float:
    """QTc = QT + 1.75·(FC − 60) (ms)."""
    if not _positive(qt_ms, hr_bpm):
        raise ValueError("QT y FC deben ser > 0")
    return qt_ms + 1.75 * (hr_bpm - 60.0)


def qtc_all(qt_ms: float, hr_bpm: float) -> Dict[str, float]:
    """Las cuatro correcciones a partir de QT (ms) y FC (lpm)."""
    rr_s = rr_seconds_from_hr(hr_bpm)
    return {
        "Bazett": qtc_bazett(qt_ms, rr_s),
        "Fridericia": qtc_fridericia(qt_ms, rr_s),
        "Framingham": qtc_framingham(qt_ms, rr_s),
        "Hodges": qtc_hodges(qt_ms, hr_bpm),
    }


def classify_qtc(qtc_ms: Optional[float], sex: str) -> Classification:
    """Umbrales AHA/ACCF/HRS 2009 (`QTC_THRESHOLDS_CITATION`) y >500 ms
    (`QTC_500_CITATION`). `sex`: "M" (hombre) o "F" (mujer)."""
    if qtc_ms is None or not math.isfinite(qtc_ms):
        return _NOT_AVAILABLE
    prolonged = 460.0 if str(sex).upper().startswith("F") else 450.0
    if qtc_ms > 500.0:
        return ("severo", "QTc >500 ms — riesgo marcado de torsade de pointes", "🔴")
    if qtc_ms >= prolonged:
        return ("leve", f"QTc prolongado (≥{prolonged:.0f} ms)", "🟡")
    if qtc_ms <= 390.0:
        return ("leve", "QTc corto (≤390 ms)", "🟡")
    return ("normal", "QTc dentro de rango", "🟢")


def hr_from_ecg_paper(large_squares: Optional[float] = None, small_squares: Optional[float] = None) -> float:
    """FC desde papel a 25 mm/s: 300 / cuadros grandes o 1500 / cuadros
    pequeños entre dos R consecutivas (`ECG_PAPER_CITATION`)."""
    if small_squares is not None:
        if not _positive(small_squares):
            raise ValueError("los cuadros pequeños deben ser > 0")
        return 1500.0 / small_squares
    if large_squares is not None:
        if not _positive(large_squares):
            raise ValueError("los cuadros grandes deben ser > 0")
        return 300.0 / large_squares
    raise ValueError("indica cuadros grandes o pequeños")


def hr_six_second_method(qrs_in_6s: float) -> float:
    """Método de los 6 s: complejos QRS en 6 s × 10 (útil en ritmos irregulares)."""
    if qrs_in_6s is None or qrs_in_6s < 0:
        raise ValueError("el número de complejos no puede ser negativo")
    return qrs_in_6s * 10.0


def classify_heart_rate(hr_bpm: Optional[float]) -> Classification:
    """Definiciones convencionales del adulto en reposo: <60 bradicardia,
    >100 taquicardia (mismos cortes que usa `clinical/ecg_analyzer.py`)."""
    if hr_bpm is None or not math.isfinite(hr_bpm):
        return _NOT_AVAILABLE
    if hr_bpm < 60:
        return ("leve", "bradicardia (<60 lpm)", "🟡")
    if hr_bpm > 100:
        return ("leve", "taquicardia (>100 lpm)", "🟡")
    return ("normal", "60–100 lpm", "🟢")


def qrs_axis_degrees(net_lead_i: float, net_avf: float) -> float:
    """Eje eléctrico (grados, −180..+180] a partir de la amplitud NETA del
    QRS (R − S) en DI (0°) y aVF (+90°), sistema hexaxial."""
    if net_lead_i == 0 and net_avf == 0:
        raise ValueError("DI y aVF no pueden ser ambos 0 (QRS isodifásico en ambas)")
    return math.degrees(math.atan2(net_avf, net_lead_i))


def classify_qrs_axis(axis_deg: Optional[float]) -> Classification:
    if axis_deg is None or not math.isfinite(axis_deg):
        return _NOT_AVAILABLE
    if -30.0 <= axis_deg <= 90.0:
        return ("normal", "eje normal (−30° a +90°)", "🟢")
    if -90.0 <= axis_deg < -30.0:
        return ("leve", "desviación izquierda (< −30°)", "🟡")
    if 90.0 < axis_deg <= 180.0:
        return ("leve", "desviación derecha (> +90°)", "🟡")
    return ("severo", "eje extremo (−90° a ±180°)", "🔴")


# ═══════════════════════════════════════════════════════════════════════
# HEMODINAMIA
# ═══════════════════════════════════════════════════════════════════════

def _check_bp(sbp: float, dbp: float) -> None:
    if not _positive(sbp, dbp):
        raise ValueError("las presiones deben ser > 0")
    if dbp >= sbp:
        raise ValueError("la diastólica debe ser menor que la sistólica")


def mean_arterial_pressure(sbp: float, dbp: float) -> float:
    """PAM ≈ PAD + (PAS − PAD)/3 (aproximación clásica en reposo)."""
    _check_bp(sbp, dbp)
    return dbp + (sbp - dbp) / 3.0


def pulse_pressure(sbp: float, dbp: float) -> float:
    _check_bp(sbp, dbp)
    return sbp - dbp


def classify_map(map_mmhg: Optional[float]) -> Classification:
    """Solo el corte que la guía fija (`MAP_TARGET_CITATION`): <65 mmHg."""
    if map_mmhg is None or not math.isfinite(map_mmhg):
        return _NOT_AVAILABLE
    if map_mmhg < 65.0:
        return ("severo", "PAM <65 mmHg — por debajo del objetivo inicial en choque séptico", "🔴")
    return ("normal", "PAM ≥65 mmHg", "🟢")


def shock_index(hr_bpm: float, sbp: float) -> float:
    """Índice de choque = FC / PAS."""
    if not _positive(hr_bpm, sbp):
        raise ValueError("FC y PAS deben ser > 0")
    return hr_bpm / sbp


def classify_shock_index(si: Optional[float]) -> Classification:
    """≤0.7: rango normal de Allgöwer & Burri; ≥1.0: corte frecuente en la
    literatura de trauma/urgencias; entre ambos: por encima de lo normal."""
    if si is None or not math.isfinite(si):
        return _NOT_AVAILABLE
    if si >= 1.0:
        return ("severo", "≥1.0 — asociado a inestabilidad hemodinámica", "🔴")
    if si > 0.7:
        return ("leve", "por encima del rango normal (0.5–0.7)", "🟡")
    return ("normal", "rango normal (0.5–0.7)", "🟢")


def cardiac_output_l_min(hr_bpm: float, stroke_volume_ml: float) -> float:
    """GC = FC × VS (L/min)."""
    if not _positive(hr_bpm, stroke_volume_ml):
        raise ValueError("FC y volumen sistólico deben ser > 0")
    return hr_bpm * stroke_volume_ml / 1000.0


def cardiac_index(cardiac_output: float, bsa_m2: float) -> float:
    if not _positive(cardiac_output, bsa_m2):
        raise ValueError("gasto cardiaco y ASC deben ser > 0")
    return cardiac_output / bsa_m2


def classify_cardiac_index(ci: Optional[float]) -> Classification:
    if ci is None or not math.isfinite(ci):
        return _NOT_AVAILABLE
    if ci < 2.2:
        return ("severo", "<2.2 L/min/m² — umbral de hipoperfusión (Forrester)", "🔴")
    if ci < 2.5:
        return ("leve", "por debajo del rango de referencia habitual (2.5–4.0)", "🟡")
    if ci > 4.0:
        return ("leve", "por encima del rango de referencia habitual (2.5–4.0)", "🟡")
    return ("normal", "rango de referencia habitual (2.5–4.0 L/min/m²)", "🟢")


# ═══════════════════════════════════════════════════════════════════════
# ANTROPOMETRÍA
# ═══════════════════════════════════════════════════════════════════════

def body_mass_index(weight_kg: float, height_cm: float) -> float:
    if not _positive(weight_kg, height_cm):
        raise ValueError("peso y talla deben ser > 0")
    h_m = height_cm / 100.0
    return weight_kg / (h_m * h_m)


def classify_bmi(bmi: Optional[float]) -> Classification:
    """Categorías de adulto de la OMS (`WHO_BMI_CITATION`)."""
    if bmi is None or not math.isfinite(bmi):
        return _NOT_AVAILABLE
    if bmi < 18.5:
        return ("leve", "bajo peso (<18.5)", "🟡")
    if bmi < 25.0:
        return ("normal", "peso normal (18.5–24.9)", "🟢")
    if bmi < 30.0:
        return ("leve", "sobrepeso (25.0–29.9)", "🟡")
    if bmi < 35.0:
        return ("severo", "obesidad clase I (30.0–34.9)", "🔴")
    if bmi < 40.0:
        return ("severo", "obesidad clase II (35.0–39.9)", "🔴")
    return ("severo", "obesidad clase III (≥40)", "🔴")


def bsa_mosteller(height_cm: float, weight_kg: float) -> float:
    """ASC (m²) = √(talla_cm × peso_kg / 3600)."""
    if not _positive(height_cm, weight_kg):
        raise ValueError("peso y talla deben ser > 0")
    return math.sqrt(height_cm * weight_kg / 3600.0)


def bsa_dubois(height_cm: float, weight_kg: float) -> float:
    """ASC (m²) = 0.007184 × peso^0.425 × talla^0.725."""
    if not _positive(height_cm, weight_kg):
        raise ValueError("peso y talla deben ser > 0")
    return 0.007184 * weight_kg ** 0.425 * height_cm ** 0.725


# ═══════════════════════════════════════════════════════════════════════
# OXIGENACIÓN
# ═══════════════════════════════════════════════════════════════════════

WATER_VAPOR_PRESSURE_MMHG = 47.0
RESPIRATORY_QUOTIENT = 0.8

# Altitudes aproximadas (m s. n. m.) para el selector de la UI.
CITY_ALTITUDES_M: Dict[str, float] = {
    "Nivel del mar": 0.0,
    "Monterrey": 540.0,
    "Guadalajara": 1566.0,
    "Puebla": 2135.0,
    "Ciudad de México": 2240.0,
    "Toluca": 2660.0,
}


def barometric_pressure_mmhg(altitude_m: float) -> float:
    """Presión barométrica estimada por la atmósfera estándar (`ISA_CITATION`)."""
    if altitude_m is None or not math.isfinite(altitude_m) or altitude_m < -500 or altitude_m > 9000:
        raise ValueError("altitud fuera de rango (−500 a 9000 m)")
    return 760.0 * (1.0 - 2.25577e-5 * altitude_m) ** 5.25588


def _check_fio2(fio2: float) -> None:
    if fio2 is None or not math.isfinite(fio2) or not (0.21 <= fio2 <= 1.0):
        raise ValueError("FiO₂ debe estar entre 0.21 y 1.0 (fracción, no porcentaje)")


def alveolar_po2(fio2: float, paco2_mmhg: float, patm_mmhg: float = 760.0,
                 rq: float = RESPIRATORY_QUOTIENT) -> float:
    """PAO₂ = FiO₂·(Patm − 47) − PaCO₂/R (`ALVEOLAR_GAS_CITATION`)."""
    _check_fio2(fio2)
    if not _positive(paco2_mmhg, patm_mmhg, rq):
        raise ValueError("PaCO₂, Patm y R deben ser > 0")
    return fio2 * (patm_mmhg - WATER_VAPOR_PRESSURE_MMHG) - paco2_mmhg / rq


def aa_gradient(fio2: float, pao2_mmhg: float, paco2_mmhg: float, patm_mmhg: float = 760.0) -> float:
    if not _positive(pao2_mmhg):
        raise ValueError("PaO₂ debe ser > 0")
    return alveolar_po2(fio2, paco2_mmhg, patm_mmhg) - pao2_mmhg


def expected_aa_gradient(age_years: float) -> float:
    """Regla clínica habitual en aire ambiente: edad/4 + 4 mmHg (estimación,
    no un estándar validado -- se muestra como heurística)."""
    if age_years is None or not math.isfinite(age_years) or age_years < 0:
        raise ValueError("edad inválida")
    return age_years / 4.0 + 4.0


def pf_ratio(pao2_mmhg: float, fio2: float) -> float:
    _check_fio2(fio2)
    if not _positive(pao2_mmhg):
        raise ValueError("PaO₂ debe ser > 0")
    return pao2_mmhg / fio2


def classify_pf_ratio(pf: Optional[float]) -> Classification:
    """Rangos de oxigenación de la definición de Berlín (`BERLIN_CITATION`).
    Es SOLO el criterio de oxigenación: el diagnóstico de SDRA exige además
    temporalidad, imagen y origen no cardiogénico."""
    if pf is None or not math.isfinite(pf):
        return _NOT_AVAILABLE
    if pf > 300.0:
        return ("normal", ">300 mmHg — fuera de los rangos de Berlín", "🟢")
    if pf > 200.0:
        return ("leve", "200–300 mmHg — rango 'leve' de Berlín", "🟡")
    if pf > 100.0:
        return ("leve", "100–200 mmHg — rango 'moderado' de Berlín", "🟡")
    return ("severo", "≤100 mmHg — rango 'grave' de Berlín", "🔴")


# ═══════════════════════════════════════════════════════════════════════
# ESCALAS DE ALERTA Y CONCIENCIA
# ═══════════════════════════════════════════════════════════════════════

def _news2_rr(rr: float) -> int:
    if rr <= 8:
        return 3
    if rr <= 11:
        return 1
    if rr <= 20:
        return 0
    if rr <= 24:
        return 2
    return 3


def _news2_spo2_scale1(spo2: float) -> int:
    if spo2 <= 91:
        return 3
    if spo2 <= 93:
        return 2
    if spo2 <= 95:
        return 1
    return 0


def _news2_spo2_scale2(spo2: float, on_oxygen: bool) -> int:
    """Escala 2 (insuficiencia respiratoria hipercápnica, objetivo 88–92 %):
    ≥93 % solo puntúa si el paciente recibe oxígeno."""
    if spo2 >= 93:
        if not on_oxygen:
            return 0
        if spo2 <= 94:
            return 1
        if spo2 <= 96:
            return 2
        return 3
    if spo2 <= 83:
        return 3
    if spo2 <= 85:
        return 2
    if spo2 <= 87:
        return 1
    return 0


def _news2_sbp(sbp: float) -> int:
    if sbp <= 90:
        return 3
    if sbp <= 100:
        return 2
    if sbp <= 110:
        return 1
    if sbp <= 219:
        return 0
    return 3


def _news2_pulse(hr: float) -> int:
    if hr <= 40:
        return 3
    if hr <= 50:
        return 1
    if hr <= 90:
        return 0
    if hr <= 110:
        return 1
    if hr <= 130:
        return 2
    return 3


def _news2_temp(temp_c: float) -> int:
    if temp_c <= 35.0:
        return 3
    if temp_c <= 36.0:
        return 1
    if temp_c <= 38.0:
        return 0
    if temp_c <= 39.0:
        return 1
    return 2


@dataclass(frozen=True)
class News2Result:
    total: int
    components: Dict[str, int]
    any_single_3: bool
    risk: str            # "bajo", "bajo-medio", "medio", "alto"
    response: str        # respuesta clínica que asocia el RCP a cada banda


_NEWS2_RESPONSE = {
    "bajo": "evaluación por la enfermera responsable; frecuencia de monitoreo según el puntaje",
    "bajo-medio": "respuesta urgente en sala (un parámetro en 3)",
    "medio": "umbral clave para respuesta urgente (valoración por clínico con competencias en paciente agudo)",
    "alto": "umbral de respuesta de emergencia (equipo con competencias en cuidados críticos)",
}


def news2_score(*, respiratory_rate: float, spo2: float, on_oxygen: bool, systolic_bp: float,
                pulse: float, alert: bool, temperature_c: float, spo2_scale: int = 1) -> News2Result:
    """NEWS2 (`NEWS2_CITATION`). `alert=False` = cualquier categoría CVPU
    (confusión nueva, responde a la voz, al dolor, o no responde) → 3.
    `spo2_scale=2` solo para insuficiencia respiratoria hipercápnica con
    objetivo prescrito de 88–92 %."""
    for name, v in (("FR", respiratory_rate), ("SpO₂", spo2), ("PAS", systolic_bp),
                    ("pulso", pulse), ("temperatura", temperature_c)):
        if v is None or not math.isfinite(v) or v < 0:
            raise ValueError(f"{name} inválido")
    if spo2_scale not in (1, 2):
        raise ValueError("la escala de SpO₂ debe ser 1 o 2")
    components = {
        "Frecuencia respiratoria": _news2_rr(respiratory_rate),
        f"SpO₂ (escala {spo2_scale})": (
            _news2_spo2_scale1(spo2) if spo2_scale == 1 else _news2_spo2_scale2(spo2, on_oxygen)
        ),
        "Aire u oxígeno": 2 if on_oxygen else 0,
        "Presión sistólica": _news2_sbp(systolic_bp),
        "Pulso": _news2_pulse(pulse),
        "Conciencia (ACVPU)": 0 if alert else 3,
        "Temperatura": _news2_temp(temperature_c),
    }
    total = sum(components.values())
    any3 = any(v == 3 for v in components.values())
    if total >= 7:
        risk = "alto"
    elif total >= 5:
        risk = "medio"
    elif any3:
        risk = "bajo-medio"
    else:
        risk = "bajo"
    return News2Result(total, components, any3, risk, _NEWS2_RESPONSE[risk])


def classify_news2(result: Optional[News2Result]) -> Classification:
    if result is None:
        return _NOT_AVAILABLE
    if result.risk == "alto":
        return ("severo", f"riesgo clínico alto (≥7) — {result.response}", "🔴")
    if result.risk == "medio":
        return ("leve", f"riesgo clínico medio (5–6) — {result.response}", "🟡")
    if result.risk == "bajo-medio":
        return ("leve", f"riesgo bajo-medio — {result.response}", "🟡")
    return ("normal", f"riesgo clínico bajo (0–4) — {result.response}", "🟢")


def qsofa_score(*, respiratory_rate: float, systolic_bp: float, altered_mentation: bool) -> int:
    """qSOFA (`QSOFA_CITATION`): FR ≥22, PAS ≤100, alteración mental."""
    if not _positive(respiratory_rate, systolic_bp):
        raise ValueError("FR y PAS deben ser > 0")
    return int(respiratory_rate >= 22) + int(systolic_bp <= 100) + int(bool(altered_mentation))


def classify_qsofa(score: Optional[int]) -> Classification:
    if score is None:
        return _NOT_AVAILABLE
    if score >= 2:
        return ("severo", f"{score}/3 — positivo: mayor riesgo de mal desenlace (no diagnostica sepsis)", "🔴")
    return ("normal", f"{score}/3 — negativo (no descarta sepsis)", "🟢")


GCS_EYE = {4: "Espontánea", 3: "Al estímulo verbal", 2: "Al dolor", 1: "Ninguna"}
GCS_VERBAL = {5: "Orientada", 4: "Confusa", 3: "Palabras inapropiadas", 2: "Sonidos incomprensibles", 1: "Ninguna"}
GCS_MOTOR = {6: "Obedece órdenes", 5: "Localiza el dolor", 4: "Retira al dolor", 3: "Flexión anormal",
             2: "Extensión", 1: "Ninguna"}


def glasgow_coma_scale(eye: int, verbal: int, motor: int) -> int:
    """GCS = O + V + M (3–15) (`GCS_CITATION`)."""
    if eye not in GCS_EYE or verbal not in GCS_VERBAL or motor not in GCS_MOTOR:
        raise ValueError("valores de Glasgow fuera de rango (O 1–4, V 1–5, M 1–6)")
    return eye + verbal + motor


def classify_gcs(total: Optional[int]) -> Classification:
    """Bandas habituales de gravedad en traumatismo craneoencefálico."""
    if total is None:
        return _NOT_AVAILABLE
    if total == 15:
        return ("normal", "15/15 — sin alteración del nivel de conciencia", "🟢")
    if total >= 13:
        return ("leve", f"{total}/15 — alteración leve (13–15)", "🟡")
    if total >= 9:
        return ("leve", f"{total}/15 — alteración moderada (9–12)", "🟡")
    return ("severo", f"{total}/15 — alteración grave (3–8)", "🔴")
