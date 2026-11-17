"""Calibración de la confianza: ¿qué tan seguro dijo estar el estudiante, frente a qué tanto acertó? (2026-11-17).

Lee el registro de la sesión (`app/utils/session_learning.get_session_log()`): cada respuesta con su concepto, si
acertó y la confianza que declaró ANTES de ver el resultado (0–100). Solo cuentan las respuestas con confianza.

Art. I, sin umbrales inventados:
- El acierto se estima con su intervalo de confianza de 95 % de Wilson [WILSON1927].
- «Exceso de confianza» solo si la confianza media queda POR ENCIMA de todo el intervalo; «falta de confianza» solo
  si queda POR DEBAJO. Si cae dentro, no se detecta ninguna de las dos: con pocas respuestas el intervalo es ancho y
  el veredicto honesto es «todavía no se puede saber», no una etiqueta.
- Los errores con más confianza se ordenan de mayor a menor confianza, sin un corte fijo.

No depende de Streamlit: recibe la lista de respuestas y devuelve números y frases.

[WILSON1927] Wilson EB. Probable inference, the law of succession, and statistical inference. J Am Stat Assoc.
1927;22(158):209–212. doi:10.1080/01621459.1927.10502953
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

WILSON_1927 = ("Wilson EB. Probable inference, the law of succession, and statistical inference. J Am Stat Assoc. "
               "1927;22(158):209–212. doi:10.1080/01621459.1927.10502953")
Z_95 = 1.959963984540054  # cuantil 0.975 de la normal estándar: intervalo de 95 %

EXCESO, FALTA, CALIBRADA, SIN_DATOS = "exceso", "falta", "calibrada", "sin_datos"

CONCEPT_LABELS = {
    "frecuencia_cardiaca": "Frecuencia cardiaca",
    "ritmo_y_conduccion": "Ritmo y conducción",
    "derivaciones_e_isquemia": "Derivaciones e isquemia",
    "news2": "NEWS2",
    "respiracion_y_apnea": "Respiración y apnea",
    "hemodinamica": "Hemodinámica",
    "emg": "EMG",
    "hrv": "HRV",
}


def wilson(aciertos: int, n: int, z: float = Z_95) -> Tuple[float, float]:
    """Intervalo de Wilson para una proporción [WILSON1927]. Con n = 0 no hay intervalo."""
    if n <= 0:
        raise ValueError("n debe ser mayor que 0")
    p = aciertos / n
    denominador = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / denominador
    margen = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominador
    return max(0.0, centro - margen), min(1.0, centro + margen)


@dataclass(frozen=True)
class Grupo:
    """Respuestas con confianza de un grupo (todas, un concepto o un nivel de confianza)."""

    n: int
    aciertos: int
    confianza_media: float          # 0–1
    intervalo: Tuple[float, float]  # Wilson 95 % del acierto, 0–1

    @property
    def acierto(self) -> float:
        return self.aciertos / self.n

    @property
    def veredicto(self) -> str:
        bajo, alto = self.intervalo
        if self.confianza_media > alto:
            return EXCESO
        if self.confianza_media < bajo:
            return FALTA
        return CALIBRADA


def _grupo(respuestas: List[dict]) -> Optional[Grupo]:
    if not respuestas:
        return None
    n = len(respuestas)
    aciertos = sum(1 for r in respuestas if r["correct"])
    media = sum(r["confidence"] for r in respuestas) / (100 * n)
    return Grupo(n=n, aciertos=aciertos, confianza_media=media, intervalo=wilson(aciertos, n))


def con_confianza(registro: Iterable[dict]) -> List[dict]:
    """Solo las respuestas en las que el estudiante declaró su confianza."""
    return [r for r in registro if r.get("confidence") is not None]


@dataclass
class Calibracion:
    total: Optional[Grupo]
    por_concepto: Dict[str, Grupo]
    por_nivel: Dict[int, Grupo]
    errores_mas_seguros: List[dict]
    sin_confianza: int  # respuestas del registro que no declararon confianza

    @property
    def hay_datos(self) -> bool:
        return self.total is not None


def calibrar(registro: Iterable[dict], max_errores: int = 3) -> Calibracion:
    registro = list(registro)
    respuestas = con_confianza(registro)
    conceptos: Dict[str, List[dict]] = {}
    niveles: Dict[int, List[dict]] = {}
    for r in respuestas:
        conceptos.setdefault(r["concept"], []).append(r)
        niveles.setdefault(int(r["confidence"]), []).append(r)
    errores = sorted((r for r in respuestas if not r["correct"]), key=lambda r: -r["confidence"])
    return Calibracion(
        total=_grupo(respuestas),
        por_concepto={c: _grupo(rs) for c, rs in sorted(conceptos.items())},
        por_nivel={nivel: _grupo(rs) for nivel, rs in sorted(niveles.items())},
        errores_mas_seguros=errores[:max_errores],
        sin_confianza=len(registro) - len(respuestas),
    )


def _pct(x: float) -> str:
    return f"{round(100 * x)} %"


def frase(grupo: Optional[Grupo], sujeto: str = "tu confianza") -> str:
    """El veredicto en palabras, con los números que lo sostienen."""
    if grupo is None:
        return ("No disponible: todavía no hay respuestas con confianza declarada. Antes de verificar cada respuesta, "
                "indica qué tan seguro estás.")
    bajo, alto = grupo.intervalo
    base = (f"Con {grupo.n} respuesta{'s' if grupo.n != 1 else ''}, {sujeto} media fue {_pct(grupo.confianza_media)} y "
            f"acertaste {grupo.aciertos} ({_pct(grupo.acierto)}; rango probable de tu acierto: "
            f"{_pct(bajo)} a {_pct(alto)}).")
    if grupo.veredicto == EXCESO:
        return base + " Tu confianza queda por encima de ese rango: hay exceso de confianza."
    if grupo.veredicto == FALTA:
        return base + " Tu confianza queda por debajo de ese rango: sabes más de lo que crees."
    return base + (" Tu confianza cabe dentro de ese rango: no se detecta exceso ni falta de confianza. Con más "
                   "respuestas el rango se estrecha y la comparación se vuelve más precisa.")
