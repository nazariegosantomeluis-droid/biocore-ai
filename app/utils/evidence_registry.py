"""Registro de evidencia: de dónde sale cada valor que muestran el banner del paciente activo, Calculadoras y las
tarjetas del gemelo (pasaporte de evidencia, 2026-11-17).

Art. I: este archivo NO redacta nada. Cada texto es una cita literal y contigua del código o de docs/, con su
ubicación (`archivo:línea`), copiada tal cual la encontró la extracción de solo lectura. Si un apartado no está escrito
en el repositorio, queda en `None` y el pasaporte dice «no documentado»; nunca se rellena.
`tests/test_pasaporte_evidencia.py` comprueba que cada cita aparezca en el archivo que dice su ubicación.

Campos: `<superficie>.<id>`. En Calculadoras, `<id>` es el `report_id` de `_card()` (`calculators/pages.py`), así
que el pasaporte se coloca con una sola línea dentro de `_card()`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

SURFACES = ("banner", "calculadoras", "gemelo")


@dataclass(frozen=True)
class Cita:
    """Texto literal del repositorio y dónde está."""

    texto: str
    ubicacion: str          # "archivo:línea"

    @property
    def archivo(self) -> str:
        return self.ubicacion.rsplit(":", 1)[0]


@dataclass(frozen=True)
class Fuente:
    """Cómo se liga el valor con la Bibliografía. `clave`: una clave firmada (`bibliography.SIGNED_KEYS`).
    `constante`: «módulo.CONSTANTE» con la cita que `bibliography.repo_references()` ya lista. `cita`: el texto literal
    que liga ESTE valor con esa fuente."""

    clave: Optional[str] = None
    constante: Optional[str] = None
    cita: Optional[Cita] = None


@dataclass(frozen=True)
class Evidencia:
    campo: str
    superficie: str
    etiqueta: str                       # rótulo con el que la UI muestra el valor
    mostrado_en: str                    # archivo:línea donde la UI lo dibuja
    produce: Optional[str]              # módulo.función que calcula o entrega el valor
    origen: Optional[str]               # archivo:línea de esa función o fórmula
    procedencia: Optional[str]          # nombre del enum Provenance, "variable" (la del UPS en ejecución) o None
    procedencia_cita: Optional[Cita] = None
    regla: Optional[Cita] = None
    supuestos: Optional[Cita] = None
    no_modelado: Optional[Cita] = None
    fuente: Optional[Fuente] = None


CALC = "clinical/calculators.py"
PAGE = "app/supermodules/calculators/pages.py"
BANNER = "app/utils/patient_banner.py"


def _c(texto: str, linea: int, archivo: str = CALC) -> Cita:
    return Cita(texto, f"{archivo}:{linea}")


def _bib(constante: str) -> Fuente:
    """Cita que la Bibliografía ya lista (`bibliography.repo_references`)."""
    return Fuente(constante=f"clinical.calculators.{constante}")


def _calc(report_id: str, etiqueta: str, linea_ui: int, produce: str, origen: int, regla: Cita, *,
          supuestos: Optional[Cita] = None, no_modelado: Optional[Cita] = None,
          fuente: Optional[Fuente] = None) -> Evidencia:
    """Resultado de Calculadoras: lo calcula una fórmula con los valores de los controles, que la página no
    marca con una procedencia del UPS (por eso `procedencia=None`)."""
    return Evidencia(f"calculadoras.{report_id}", "calculadoras", etiqueta, f"{PAGE}:{linea_ui}", produce,
                     f"{CALC}:{origen}", None, None, regla, supuestos, no_modelado, fuente)


_BANNER_RULE = _c("Última FC, FR y SpO₂ del paciente activo según el paciente compuesto (con el origen de las "
                   "arrastradas).", 91, BANNER)
_BANNER_ASSUMPTION = _c("Los valores salen del paciente compuesto (`get_composed_patient()`, T0 de la ruta integrada, "
                        "2026-11-18): el último valor de cada descriptor; uno de un snapshot anterior se muestra como "
                        "arrastre, con su procedencia de origen y su edad («Simulación · hace 3 min»), porque el último "
                        "snapshot de un laboratorio no trae lo que no midió. Un valor que el UPS no tiene se dice «Sin "
                        "dato», jamás se rellena.", 9, BANNER)
_BANNER_PROV = _c("Art. I (cada valor con su procedencia; si falta, «sin dato»; nunca un valor por defecto):", 8, BANNER)
_NEWS2_TOTAL_MISSING = _c("Nunca suma: el total NEWS2 exige los 7 parámetros (ver `NEWS2_PARAMETERS_NOT_MODELED`).", 558)
_NEWS2_SOURCE = Fuente(cita=_c("Royal College of Physicians. National Early Warning Score (NEWS) 2: Standardising the",
                               120))

ENTRIES: Tuple[Evidencia, ...] = (
    # ── Banner del paciente activo: la procedencia es la del descriptor del UPS en ejecución ──
    *(Evidencia(f"banner.{campo}", "banner", etiqueta, f"{BANNER}:213", "app.utils.patient_banner.read_active_vitals",
                f"{BANNER}:90", "variable", _BANNER_PROV, _BANNER_RULE, _BANNER_ASSUMPTION, None, None)
      for campo, etiqueta in (("fc", "FC"), ("fr", "FR"), ("spo2", "SpO₂"))),

    # ── Calculadoras: ECG ──
    *(_calc(f"qtc_{name}", f"QTc {name}", 269, "clinical.calculators.qtc_all", 186,
            _c(latex, line, PAGE), fuente=_bib(const))
      for name, latex, line, const in (
          ("Bazett", r"\text{Bazett}=\frac{QT}{\sqrt{RR}}", 260, "BAZETT_CITATION"),
          ("Fridericia", r"\text{Fridericia}=\frac{QT}{\sqrt[3]{RR}}", 260, "FRIDERICIA_CITATION"),
          ("Framingham", r"\text{Framingham}=QT+154(1-RR)", 261, "FRAMINGHAM_QTC_CITATION"),
          ("Hodges", r"\text{Hodges}=QT+1.75(FC-60)", 261, "HODGES_CITATION"))),
    _calc("hr_paper", "Frecuencia cardiaca", 288, "clinical.calculators.hr_from_ecg_paper", 212,
          _c("FC desde papel a 25 mm/s: 300 / cuadros grandes o 1500 / cuadros pequeños entre dos R consecutivas "
             "(`ECG_PAPER_CITATION`).", 213),
          fuente=Fuente(cita=_c("Kligfield P, Gettes LS, Bailey JJ, et al. Recommendations for the standardization and",
                                63))),
    _calc("qrs_axis", "Eje del QRS", 307, "clinical.calculators.qrs_axis", 245,
          _c("Eje eléctrico a partir de la amplitud NETA del QRS (R − S) en DI y aVF.", 246),
          fuente=_bib("QRS_AXIS_CITATION")),

    # ── Calculadoras: hemodinámica ──
    _calc("map", "PAM", 329, "clinical.calculators.mean_arterial_pressure", 282,
          _c("PAM ≈ PAD + (PAS − PAD)/3", 283), supuestos=_c("aproximación clásica en reposo", 283),
          fuente=_bib("MAP_TARGET_CITATION")),
    _calc("pulse_pressure", "Presión de pulso", 332, "clinical.calculators.pulse_pressure", 288,
          _c("return sbp - dbp", 290)),
    _calc("shock_index", "Índice de choque", 334, "clinical.calculators.shock_index", 302,
          _c("Índice de choque = FC / PAS.", 303), fuente=_bib("SHOCK_INDEX_CITATION")),
    _calc("cardiac_output", "Gasto cardiaco", 355, "clinical.calculators.cardiac_output_l_min", 322,
          _c("GC = FC × VS (L/min).", 323)),
    _calc("cardiac_index", "Índice cardiaco", 357, "clinical.calculators.cardiac_index", 329,
          _c("return cardiac_output / bsa_m2", 332), fuente=_bib("FORRESTER_CITATION")),

    # ── Calculadoras: oxigenación ──
    _calc("patm", "Presión barométrica estimada", 398, "clinical.calculators.barometric_pressure_mmhg", 435,
          _c("Presión barométrica estimada por la atmósfera estándar (`ISA_CITATION`).", 436),
          fuente=Fuente(cita=_c("Atmósfera estándar internacional (ISO 2533:1975 / ICAO): P = 760·(1 − 2.25577·10⁻⁵·h)^5.25588",
                                116))),
    _calc("pao2_alveolar", "PAO₂ (alveolar)", 400, "clinical.calculators.alveolar_po2", 447,
          _c("PAO₂ = FiO₂·(Patm − 47) − PaCO₂/R (`ALVEOLAR_GAS_CITATION`).", 449),
          fuente=Fuente(cita=_c("Ecuación del gas alveolar, forma simplificada: PAO₂ = FiO₂·(Patm − PH₂O) − PaCO₂/R", 112))),
    Evidencia("calculadoras.aa_gradient", "calculadoras", "Gradiente A–a", f"{PAGE}:409",
              "app.supermodules.calculators.pages._render_oxygenation_tab", f"{PAGE}:391", None, None,
              _c("gradient = alveolar - pao2", 392, PAGE),
              _c("la regla del valor esperado (edad/4 + 4) solo aplica en aire ambiente", 414, PAGE),
              _c("estimación, no un estándar validado -- se muestra como heurística", 463), None),
    _calc("pf_ratio", "PaO₂/FiO₂", 415, "clinical.calculators.pf_ratio", 470, _c("return pao2_mmhg / fio2", 474),
          fuente=_bib("BERLIN_CITATION")),

    # ── Calculadoras: antropometría ──
    _calc("bmi", "IMC", 486, "clinical.calculators.body_mass_index", 353, _c("return weight_kg / (h_m * h_m)", 357),
          supuestos=_c("Las categorías de IMC de la OMS son para adultos; en niños y adolescentes se usan percentiles por "
                       "edad y sexo.", 493, PAGE),
          fuente=_bib("WHO_BMI_CITATION")),
    _calc("bsa_mosteller", "ASC (Mosteller)", 488, "clinical.calculators.bsa_mosteller", 403,
          _c("ASC (m²) = √(talla_cm × peso_kg / 3600).", 404), fuente=_bib("MOSTELLER_CITATION")),
    _calc("bsa_dubois", "ASC (Du Bois)", 491, "clinical.calculators.bsa_dubois", 410,
          _c("ASC (m²) = 0.007184 × peso^0.425 × talla^0.725.", 411), fuente=_bib("DUBOIS_CITATION")),

    # ── Calculadoras: escalas ──
    _calc("news2", "NEWS2", 515, "clinical.calculators.news2_score", 703,
          _c("NEWS2 (`NEWS2_CITATION`). `alert=False` = cualquier categoría CVPU (confusión nueva, responde a la voz, al "
             "dolor, o no responde) → 3.", 705), fuente=_NEWS2_SOURCE),
    _calc("qsofa", "qSOFA", 532, "clinical.calculators.qsofa_score", 751,
          _c("qSOFA (`QSOFA_CITATION`): FR ≥22, PAS ≤100, alteración mental.", 752),
          fuente=Fuente(cita=_c("Seymour CW, Liu VX, Iwashyna TJ, et al. Assessment of clinical criteria for sepsis "
                                "(Sepsis-3).", 124))),
    _calc("gcs", "Glasgow", 548, "clinical.calculators.glasgow_coma_scale", 772,
          _c("GCS = O + V + M (3–15) (`GCS_CITATION`).", 773), fuente=_bib("GCS_CITATION")),
    _calc("osa_severity", "Índice de eventos por hora", 567, "clinical.calculators.event_index_per_hour", 379,
          _c("Índice de eventos respiratorios por hora = eventos / horas (de sueño en polisomnografía, de registro en un "
             "monitor portátil; `OSA_SEVERITY_CITATION`).", 380),
          fuente=Fuente(cita=_c("Epstein LJ, Kristo D, Strollo PJ Jr, et al. Clinical guideline for the evaluation, "
                                "management and long-term care", 96))),

    # ── Calculadoras: puntos NEWS2 del paciente activo (news2_partial sobre los valores del UPS) ──
    Evidencia("calculadoras.news2_paciente_hr", "calculadoras", "Pulso NEWS2", f"{PAGE}:198",
              "clinical.calculators.news2_partial", f"{CALC}:555", None, None,
              _c("Puntos NEWS2 del pulso (lat/min). Redondea a entero con .5 hacia arriba (`floor(hr + 0.5)`, no el "
                 "redondeo bancario de Python) y puntúa: ≤ 40 → 3; 41–50 → 1; 51–90 → 0; 91–110 → 1; 111–130 → 2; "
                 "≥ 131 → 3.", 649),
              None, _NEWS2_TOTAL_MISSING,
              Fuente(clave="RCP2017", cita=_c("(Ya implementado en `news2_pulse_score`.)", 35,
                                              "docs/contenido/teoria_citada.md"))),
    Evidencia("calculadoras.news2_paciente_rr", "calculadoras", "Frecuencia respiratoria NEWS2", f"{PAGE}:198",
              "clinical.calculators.news2_partial", f"{CALC}:555", None, None,
              _c("Puntos NEWS2 de la frecuencia respiratoria (resp/min, entero ya redondeado por quien llama): ≤ 8 → 3; "
                 "9–11 → 1; 12–20 → 0; 21–24 → 2; ≥ 25 → 3.", 497),
              None, _NEWS2_TOTAL_MISSING, _NEWS2_SOURCE),
    Evidencia("calculadoras.news2_paciente_spo2", "calculadoras", "SpO₂ (escala 1) NEWS2", f"{PAGE}:198",
              "clinical.calculators.news2_partial", f"{CALC}:555", None, None,
              _c("Puntos NEWS2 de la SpO₂ en la escala 1 (%). Redondea a entero con .5 hacia arriba (`floor(spo2 + 0.5)`, "
                 "el mismo criterio que `news2_pulse_score`) y puntúa: ≤ 91 → 3; 92–93 → 2; 94–95 → 1; ≥ 96 → 0.", 514),
              None, _NEWS2_TOTAL_MISSING, _NEWS2_SOURCE),
)

REGISTRY: Dict[str, Evidencia] = {e.campo: e for e in ENTRIES}


def get_evidence(campo: str) -> Optional[Evidencia]:
    return REGISTRY.get(campo)


def fields(superficie: Optional[str] = None) -> Tuple[str, ...]:
    return tuple(c for c, e in REGISTRY.items() if superficie is None or e.superficie == superficie)
