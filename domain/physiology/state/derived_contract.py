"""
Unified Physiological State — contrato de escritura de valores DERIVADOS (frontera del UPS).

Art. I (2026-11-12, frente cardiovascular, tanda C0): un valor derivado se escribe al UPS SOLO si TODAS las entradas de
su fórmula llegaron medidas o simuladas en ESE snapshot. Si alguna entrada salió de un `get(key, default)` del organismo
(`hr=70`, `hrv=50`, `complexity=50`, `ahi=0`, `relaxation=65`, `efficiency=70`, ...), el derivado NO se escribe: un valor
por defecto no es una medición. Una cantidad que el organismo nunca calcula (constante de dataclass) o que no es más que
otro nombre de un valor ya escrito NO se escribe nunca.

Fase 1 (2026-11-12, decisiones firmadas por Luis): (1) se retiran `health_score` cardiaco y `myocardial_stress`; (2) se
descartan `complexity` y `rhythm_stability`; (3) `cardiac_output` NO lo calcula el organismo: solo podría escribirlo el
motor hemodinámico base con procedencia `MODELO_HEMODINAMICO` y su estado de validación visible (hoy ese motor recibe el
flujo como ENTRADA y devuelve presiones; no lo calcula: no se escribe); (4) el riesgo cardiaco son los puntos NEWS2 de
pulso, con una sola entrada (`heart_rate`); (6) un derivado hereda la MENOR confianza de sus entradas.

Este módulo es el ÚNICO punto de verdad de la regla: la tabla `DERIVED_CONTRACT` (campo -> entradas requeridas, deducidas
de la fórmula real de `app/engines/digital_twin_organism.py`, con archivo:línea) y las dos funciones que la aplican. Solo
`builder.from_digital_twin_organism()` la consulta; ningún laboratorio ni ruta decide por su cuenta qué derivado escribir.

"Presente" significa que la clave LLEGÓ en las señales del órgano (`organ.metrics.signals`, lo que recibió
`update_from_sensors()`), NUNCA que el valor resultante sea plausible: un 70 puede ser una medición real.

Cambiar la tabla es una decisión del contrato (con su prueba en `tests/test_ups_derived_contract.py`), no un parche.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Optional, Tuple

__all__ = [
    "DerivedRule",
    "DERIVED_CONTRACT",
    "SPECTRAL_BANDS",
    "MIN_SPECTRAL_BANDS",
    "derived_is_writable",
    "derived_confidence",
    "accepted_band_powers",
    "contract_rows",
]


@dataclass(frozen=True)
class DerivedRule:
    """`inputs` = alternativas de entradas requeridas: basta que UNA alternativa esté completa (p. ej. `attention` se toma
    de la entrada `attention` o, si falta, de `relaxation_level` + `alpha_power`). Vacío = no se escribe nunca
    (`never_reason` dice por qué). `formula` cita archivo:línea de la fórmula real del organismo."""

    inputs: Tuple[Tuple[str, ...], ...]
    formula: str
    never_reason: Optional[str] = None
    only_from: Optional[str] = None  # fuente única permitida distinta del organismo (p. ej. el motor hemodinámico)


_ORG = "app/engines/digital_twin_organism.py"
_NEVER: Tuple[Tuple[str, ...], ...] = ()

DERIVED_CONTRACT: Dict[str, Dict[str, DerivedRule]] = {
    "cardiovascular": {
        # Riesgo cardiaco = puntos NEWS2 del pulso (decisión 4): única entrada `heart_rate`, sin `get(..., default)`.
        # Reemplaza a `risk_score` (umbrales caseros 40/120 y hrv < 20, purgados del organismo).
        "news2_pulse_points": DerivedRule(
            (("heart_rate",),), "clinical/calculators.py:news2_pulse_score (NEWS2_CITATION, RCP 2017)"
        ),
        "health_score": DerivedRule(
            _NEVER, f"{_ORG} (retirado)",
            "decisión 1: fórmula sin cita (pesos 0.3/0.5/0.2) que satura en 100 entre FC 35 y 150; retirado",
        ),
        "myocardial_stress": DerivedRule(
            _NEVER, f"{_ORG} (retirado)", "decisión 1: era 100 - health_score; retirado con él",
        ),
        "rhythm_stability": DerivedRule(
            _NEVER, f"{_ORG} (retirado)",
            "decisión 2: era el eco de `complexity` (default 50); «estabilidad del ritmo» no significa lo mismo que "
            "entropía; ningún laboratorio mide esa entrada",
        ),
        "cardiac_output": DerivedRule(
            _NEVER, f"{_ORG} (retirado)",
            "decisión 3: no modelado por el organismo. Ni el SimulationEngine (literales por escenario, sin "
            "hemodinámica) ni el motor RCR base (recibe el flujo como entrada, devuelve presiones) lo calculan; solo "
            "podría escribirlo el motor hemodinámico base como MODELO_HEMODINAMICO con su estado de validación",
            only_from="motor hemodinámico base (MODELO_HEMODINAMICO)",
        ),
    },
    "respiratory": {
        # _update_lungs: rr/spo2/ahi con default 16/98/0 (L427-429); fórmulas L436-452.
        "health_score": DerivedRule((("respiratory_rate", "spo2", "ahi"),), f"{_ORG}:436"),
        "risk_score": DerivedRule((("spo2", "ahi"),), f"{_ORG}:441-446"),
        "hypoxia_risk": DerivedRule((("spo2",),), f"{_ORG}:450"),
        "apnea_risk": DerivedRule((("ahi",),), f"{_ORG}:449"),
        "tissue_oxygenation": DerivedRule(
            _NEVER, f"{_ORG}:452",
            "es la SpO2 con otro nombre (`spo2_score = spo2`): fachada por nombre de un valor que ya se escribe; "
            "`perfusion_index` (L451) es el mismo número y tampoco se escribe",
        ),
    },
    "neurological": {
        # _update_brain: alpha/beta/stress/relaxation con default 50/30/35/65 (L398-401); fórmulas L404-421.
        "health_score": DerivedRule((("relaxation_level", "stress_level"),), f"{_ORG}:404"),
        "risk_score": DerivedRule((("stress_level",),), f"{_ORG}:409-414"),
        "mental_workload": DerivedRule((("beta_power",),), f"{_ORG}:417 (= min(100, beta_power))"),
        "cognitive_fatigue": DerivedRule((("relaxation_level", "stress_level"),), f"{_ORG}:418 (= 100 - health_score)"),
        "attention": DerivedRule((("attention",), ("relaxation_level", "alpha_power")), f"{_ORG}:419"),
        "stress_perception": DerivedRule((("stress_level",),), f"{_ORG}:420"),
        "sleepiness": DerivedRule(
            (("attention",), ("relaxation_level", "alpha_power")), f"{_ORG}:421 (= 100 - attention)"
        ),
    },
    "muscular": {
        # _update_muscles: fatigue/activation/efficiency con default 20/45/70 (L458-460); fórmulas L463-477.
        "health_score": DerivedRule((("efficiency", "fatigue_index"),), f"{_ORG}:463"),
        "risk_score": DerivedRule((("fatigue_index",),), f"{_ORG}:468-473"),
        "neuromuscular_efficiency": DerivedRule((("efficiency",),), f"{_ORG}:476"),
        "movement_smoothness": DerivedRule((("fatigue_index",),), f"{_ORG}:477 (= 100 - fatigue_index)"),
    },
}

# Potencias de banda (medidas). Un análisis espectral (Welch, `EegAnalyzer`) devuelve el conjunto de bandas de una vez:
# una banda AISLADA no es un espectro. Twin OS alimenta el organismo con `alpha_power = max(0, 70 - 0.5 * estrés)`
# (twin_shell/pages.py `render_sensor_controls`), una potencia EEG fabricada desde el slider de estrés y enviada SOLA:
# con este mínimo no se acepta como medición. Todo lector real de espectro envía >= 2 bandas.
SPECTRAL_BANDS: Tuple[str, ...] = ("delta_power", "theta_power", "alpha_power", "beta_power", "gamma_power")
MIN_SPECTRAL_BANDS = 2


def derived_is_writable(domain: str, field: str, present: Iterable[str]) -> bool:
    """True si el derivado `field` de `domain` puede escribirse: no es de los que nunca se escriben y alguna alternativa
    de entradas está COMPLETA en `present` (claves que llegaron en el snapshot). Campo fuera de la tabla -> KeyError: un
    derivado nuevo no se escribe hasta que alguien declare su contrato."""
    rule = DERIVED_CONTRACT[domain][field]
    have = set(present)
    return any(all(name in have for name in alternative) for alternative in rule.inputs)


def accepted_band_powers(signals: Dict[str, float]) -> Dict[str, float]:
    """Potencias de banda que el contrato acepta como medidas: solo si llegaron >= `MIN_SPECTRAL_BANDS` (ver arriba)."""
    present = {band: signals[band] for band in SPECTRAL_BANDS if band in signals}
    return present if len(present) >= MIN_SPECTRAL_BANDS else {}


def derived_confidence(
    domain: str,
    field: str,
    present: Iterable[str],
    input_confidence: Optional[Mapping[str, float]],
    default: float,
) -> float:
    """Confianza de un derivado = la MENOR confianza de las entradas de su fórmula (propagación conservadora, decisión
    6), no una constante. Usa la primera alternativa de entradas completa (el orden de las alternativas es el de la
    fórmula del organismo); una entrada sin confianza propia hereda `default` (la del escritor)."""
    rule = DERIVED_CONTRACT[domain][field]
    have = set(present)
    for alternative in rule.inputs:
        if all(name in have for name in alternative):
            conf = input_confidence or {}
            return min(float(conf.get(name, default)) for name in alternative)
    raise ValueError(f"{domain}.{field} no es escribible con las entradas presentes: {sorted(have)}")


def contract_rows() -> List[Tuple[str, str, str, str]]:
    """Filas (dominio, campo, entradas requeridas, fórmula/razón) para pruebas y documentación."""
    rows = []
    for domain, fields in DERIVED_CONTRACT.items():
        for field, rule in fields.items():
            if rule.never_reason:
                needs = f"SOLO {rule.only_from}" if rule.only_from else "NUNCA"
                why = f"{rule.formula} — {rule.never_reason}"
            else:
                needs = " ó ".join(" + ".join(alt) for alt in rule.inputs)
                why = rule.formula
            rows.append((domain, field, needs, why))
    return rows
