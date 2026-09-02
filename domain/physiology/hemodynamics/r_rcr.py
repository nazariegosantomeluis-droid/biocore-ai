"""
Módulo hemodinámico R→RCR — resistencia de Poiseuille en serie con un
Windkessel de 3 elementos (Resistencia proximal + Compliancia + Resistencia
distal). El caso de prueba más elemental del propio svZeroDSolver que
produce presión dinámica real: presión = f(resistencia, compliancia, flujo).

FUENTE DE LAS ECUACIONES (citadas verbatim, no inventadas) — svZeroDSolver,
Stanford University / SimVascular Consortium, BSD-3-Clause
(https://github.com/SimVascular/svZeroDSolver, ver THIRD_PARTY_NOTICES.md):

  Bloque RCR (`src/model/WindkesselBC.h`, documentación Doxygen del bloque):
      Rd*Q_in - P_c + P_ref - Rd*C*dP_c/dt = 0
      P_in - P_c - Rp*Q_in = 0
  donde P_c es la presión interna del capacitor (variable de estado),
  P_ref es la presión distal de referencia (Pd), y P_in/Q_in son la
  presión/flujo de entrada al bloque RCR.

  Bloque resistor de Poiseuille (`src/model/BloodVessel.cpp`, caso con
  inductance=capacitance=0, que es la configuración real usada por los
  casos de prueba oficiales "R_RCR" — solo se especifica R_poiseuille):
      P_in - R*Q - P_out = 0   (es decir P_in = P_out + R*Q)
      Q_in = Q_out

Combinando ambos (resistor en serie con el RCR):
      dP_c/dt = (Rd*Q(t) - P_c + Pd) / (Rd*C)
      P_outlet = P_c + Rp*Q(t)               # salida del resistor / entrada al RCR
      P_inlet  = P_outlet + R_poiseuille*Q(t)  # entrada del sistema completo

Inicialización: P_c(0) se fija al valor de estado estacionario evaluado con
el flujo promediado en un ciclo — mismo criterio que `use_steady_bcs.py`
del solver oficial (arrancar de una condición inicial consistente, nunca de
un cero arbitrario).

VERIFICACIÓN MATEMÁTICA (ver tests/test_hemodynamics_r_rcr.py y
CHANGELOG.md para el detalle completo):
1. Reproduce EXACTAMENTE (dentro de precisión de punto flotante) los dos
   checkpoints analíticos publicados en los casos de prueba oficiales
   `steadyFlow_R_RCR.json`/`pulsatileFlow_R_RCR.json` de svZeroDSolver.
2. La curva convergida (último ciclo, régimen periódico) coincide con la
   salida real de una corrida genuina del solver oficial (paquete
   `svzerodsolver`, la implementación Python del mismo proyecto,
   instalada y ejecutada durante esta tanda) dentro de <0.2 unidades de
   presión sobre una escala de ~9000 — diferencia atribuible al esquema
   numérico (aquí: Radau adaptativo de scipy; en el oficial: generalized-
   alpha de paso fijo), no a una discrepancia de modelo.

Los parámetros por defecto (`RRCRParameters()`) son EXACTAMENTE los del
caso de prueba oficial — no inventados. Cambiarlos para explorar otro
régimen fisiológico es una decisión de quien use este módulo (el
validador), no de este código.

Aditivo y aislado: no toca domain/physiology/state/, scenarios/,
coupling/ ni narrator/. No se conecta al UPS ni a los escenarios todavía.

--- Rendimiento (2026-08-05): solución analítica de la MISMA ecuación ---
La EDO de arriba (`dP_c/dt = (Rd*Q(t) - P_c + Pd) / (Rd*C)`) es LINEAL de
primer orden. Para el flujo de entrada realmente usado en todo el motor
(`steady_flow_reference`, `pulsatile_flow_reference`,
`physiological_pulsatile_flow` -- los tres son Q(t) = Q0 + Qs·sin(ωt) +
Qc·cos(ωt), es decir componente continua + UN solo armónico) esta EDO
tiene solución cerrada exacta -- no es un modelo nuevo, es la forma
analítica de la ecuación ya citada arriba.

Con τ=Rd·C (constante de tiempo) y ω=2π/period_s, reescribiendo la EDO como
dP_c/dt + P_c/τ = Q(t)/C + Pd/τ y resolviendo por el método del factor
integrante (solución particular periódica + transitorio que decae como
e^(-t/τ), ajustado a la MISMA condición inicial P_c(0)=Rd·Q0+Pd que ya
usaba la versión numérica):

    P_c(t) = (Rd·Q0 + Pd) + A_sin·sin(ωt) + A_cos·cos(ωt) − A_cos·e^(−t/τ)

    D = C·(1 + ω²τ²)
    A_sin = τ·(Qs + Qc·ω·τ) / D
    A_cos = τ·(Qc − Qs·ω·τ) / D

Verificado a mano antes de implementar (ver CHANGELOG.md): con los
parámetros oficiales, esta fórmula reproduce exactamente los dos
checkpoints publicados (10500/10000 flujo constante; 4620/4400 flujo
pulsátil en t=0) -- sin margen de error, coincidencia algebraica directa,
no solo numérica.

`_analytic_capacitor_pressure()` implementa esta fórmula.
`_fourier_fundamental_coefficients()` extrae (Q0, Qs, Qc) de cualquier
`flow_fn` por cuadratura (barato, no es la parte cara). Si `flow_fn` NO es
de esa forma (p.ej. un escalón, usado solo en un test de compliancia) la
reconstrucción Q0+Qs·sin+Qc·cos no coincide con el flujo real dentro de
tolerancia -- en ese caso `simulate_r_rcr()` cae automáticamente al
`solve_ivp` numérico original (sin cambios), nunca produce un resultado
analítico silenciosamente incorrecto para una forma que no puede resolver
exactamente."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Tuple

import numpy as np
from scipy.integrate import solve_ivp

__all__ = [
    "RRCRParameters",
    "RRCRResult",
    "simulate_r_rcr",
    "steady_flow_reference",
    "pulsatile_flow_reference",
    "OFFICIAL_STEADY_CHECKPOINT",
    "OFFICIAL_PULSATILE_T0_CHECKPOINT",
]


@dataclass(frozen=True)
class RRCRParameters:
    """Parámetros del módulo R-RCR. Los valores por defecto son EXACTAMENTE
    los del caso de prueba oficial `steadyFlow_R_RCR.json`/
    `pulsatileFlow_R_RCR.json` de svZeroDSolver -- no inventados."""

    r_poiseuille: float = 100.0  # resistencia del vaso (mmHg*s/mL o unidad consistente)
    rp: float = 1000.0  # resistencia proximal del Windkessel
    c: float = 0.0001  # compliancia del Windkessel
    rd: float = 1000.0  # resistencia distal del Windkessel
    pd: float = 0.0  # presión distal de referencia


@dataclass(frozen=True)
class RRCRResult:
    """Serie temporal completa (todos los ciclos simulados, no solo el
    último) -- quien consuma esto decide si quiere el transitorio o solo
    el régimen periódico (`n_points_per_cycle` últimos puntos)."""

    time: np.ndarray
    flow: np.ndarray
    pressure_inlet: np.ndarray  # "presión arterial" de este módulo -- entrada al resistor
    pressure_outlet: np.ndarray  # salida del resistor / entrada al Windkessel
    pressure_capacitor: np.ndarray  # variable de estado interna del Windkessel (P_c)


def steady_flow_reference(q: float = 5.0) -> Callable[[float], float]:
    """Flujo constante -- caso oficial `steadyFlow_R_RCR.json` usa Q=5.0."""
    return lambda t: q


def pulsatile_flow_reference(t: float) -> float:
    """Q(t) = 2.5*sin(2*pi*t) + 2.2 -- fórmula documentada verbatim en
    `pulsatileFlow_R_RCR.json` (caso oficial de svZeroDSolver), periodo 1s."""
    return 2.5 * np.sin(2 * np.pi * t) + 2.2


# Checkpoints publicados en los casos de prueba oficiales de svZeroDSolver
# (mismos valores que tests/test_integration.py::test_steady_flow_r_rcr /
# test_pulsatile_flow_r_rcr del paquete oficial, y reproducidos en la
# corrida real documentada en CHANGELOG.md).
OFFICIAL_STEADY_CHECKPOINT = {"flow": 5.0, "pressure_inlet": 10500.0, "pressure_outlet": 10000.0}
OFFICIAL_PULSATILE_T0_CHECKPOINT = {"flow": 2.2, "pressure_inlet": 4620.0, "pressure_outlet": 4400.0}


# Tolerancia relativa (RMS del residuo / RMS de Q) por debajo de la cual
# Q(t) se considera EXACTAMENTE Q0+Qs*sin(wt)+Qc*cos(wt) -- muy por debajo
# del ruido de cuadratura esperado para una sinusoide genuina (~1e-9 a
# 2001 puntos), y muy por encima de lo que produce una forma con armónicos
# reales (un escalón da un residuo relativo de orden 1, no de orden 1e-6).
_FOURIER_RECONSTRUCTION_RTOL = 1e-6


def _fourier_fundamental_coefficients(
    flow_fn: Callable[[float], float], period_s: float, n_points: int = 2001
) -> Tuple[float, float, float, bool]:
    """Extrae por cuadratura (barato -- 2001 evaluaciones de flow_fn, no un
    solve_ivp) la componente continua (Q0) y el armónico fundamental
    (Qs, Qc) de `flow_fn` sobre un periodo. Devuelve también `exact`: True
    si Q0+Qs*sin(wt)+Qc*cos(wt) reproduce el `flow_fn` real dentro de
    `_FOURIER_RECONSTRUCTION_RTOL` -- False si `flow_fn` tiene armónicos
    más allá del fundamental (p.ej. un escalón) y la solución analítica no
    aplica para esta llamada."""
    t = np.linspace(0.0, period_s, n_points)
    q = np.array([flow_fn(x) for x in t])
    omega = 2.0 * np.pi / period_s

    q0 = float(np.trapezoid(q, t) / period_s)
    qs = float(np.trapezoid(q * np.sin(omega * t), t) * 2.0 / period_s)
    qc = float(np.trapezoid(q * np.cos(omega * t), t) * 2.0 / period_s)

    reconstruction = q0 + qs * np.sin(omega * t) + qc * np.cos(omega * t)
    residual_rms = float(np.sqrt(np.mean((q - reconstruction) ** 2)))
    q_rms = float(np.sqrt(np.mean(q ** 2))) or 1.0  # evita 0/0 si flow_fn es idénticamente 0
    exact = (residual_rms / q_rms) < _FOURIER_RECONSTRUCTION_RTOL

    return q0, qs, qc, exact


def _analytic_capacitor_pressure(
    t_eval: np.ndarray, params: "RRCRParameters", q0: float, qs: float, qc: float, period_s: float
) -> np.ndarray:
    """Solución cerrada de `dP_c/dt = (Rd*Q(t) - P_c + Pd) / (Rd*C)` para
    Q(t)=q0+qs*sin(wt)+qc*cos(wt) -- ver derivación completa en el
    docstring del módulo. Vectorizado, sin integración numérica."""
    tau = params.rd * params.c
    omega = 2.0 * np.pi / period_s
    d = params.c * (1.0 + (omega * tau) ** 2)

    a_sin = tau * (qs + qc * omega * tau) / d
    a_cos = tau * (qc - qs * omega * tau) / d

    p_c0 = params.rd * q0 + params.pd  # misma condición inicial que la versión numérica

    return (
        p_c0
        + a_sin * np.sin(omega * t_eval)
        + a_cos * np.cos(omega * t_eval)
        - a_cos * np.exp(-t_eval / tau)
    )


def simulate_r_rcr(
    flow_fn: Callable[[float], float],
    params: RRCRParameters = RRCRParameters(),
    *,
    period_s: float = 1.0,
    n_cycles: int = 10,
    n_points_per_cycle: int = 201,
) -> RRCRResult:
    """Integra la ODE del módulo R-RCR bajo un flujo de entrada periódico
    `flow_fn(t)` (definido sobre `[0, period_s]`, repetido cíclicamente).

    `n_cycles=10`/`n_points_per_cycle=201` son los mismos valores que usan
    los casos de prueba oficiales -- suficientes para que el transitorio
    (constante de tiempo Rd*C) decaiga y se alcance el régimen periódico
    en el último ciclo."""
    total_points = (n_points_per_cycle - 1) * n_cycles + 1
    t_eval = np.linspace(0.0, period_s * n_cycles, total_points)

    q0, qs, qc, exact = _fourier_fundamental_coefficients(flow_fn, period_s)
    p_c0 = params.rd * q0 + params.pd  # condición inicial consistente, no un cero arbitrario

    # Ruta analítica (2026-08-05, ver docstring del módulo): Q(t) es
    # exactamente componente-continua + un armónico -- caso de los tres
    # flow_fn reales del proyecto (steady/pulsatile/physiological). Si
    # `flow_fn` no es de esa forma (p.ej. un escalón), `exact=False` y se
    # cae al `solve_ivp` original, sin cambio de comportamiento.
    if exact and params.rd != 0.0 and params.c > 0.0:
        p_c = _analytic_capacitor_pressure(t_eval, params, q0, qs, qc, period_s)
    else:

        def rhs(t: float, y: np.ndarray) -> list:
            p_c_y = y[0]
            q = flow_fn(t % period_s)
            return [(params.rd * q - p_c_y + params.pd) / (params.rd * params.c)]

        solution = solve_ivp(
            rhs, (0.0, period_s * n_cycles), [p_c0], t_eval=t_eval, method="Radau", rtol=1e-10, atol=1e-12
        )
        p_c = solution.y[0]

    q_series = np.array([flow_fn(t % period_s) for t in t_eval])
    p_outlet = p_c + params.rp * q_series
    p_inlet = p_outlet + params.r_poiseuille * q_series

    return RRCRResult(
        time=t_eval, flow=q_series, pressure_inlet=p_inlet, pressure_outlet=p_outlet, pressure_capacitor=p_c
    )
