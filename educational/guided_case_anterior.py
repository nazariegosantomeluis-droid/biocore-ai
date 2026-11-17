"""Caso guiado de ECG 2: elevación del ST en V1–V4 (2026-11-17, Art. I). BORRADOR para la firma de Luis.

La misma plantilla que el caso 1 (`educational/guided_case.py`): trazado SIMULADO, resultados MEDIDOS por el analizador,
cada texto con su línea firmada del tema 5 de `teoria_citada.md` («t1:N», [W2009]) y el caso solo se muestra si
`docs/contenido/caso_guiado_ecg_2.md` dice FIRMADO.

La lección: la tabla firmada tiene tres patrones de la descendente anterior (proximal t1:78, distal t1:79, entre la
primera septal y la primera diagonal t1:80). En este trazado V1 sí se eleva (descarta t1:80), V5–V6 casi no (no es
«sobre todo V3–V6», t1:79) e I queda en la línea de base (el patrón proximal de t1:78 queda incompleto): el ECG orienta
a la descendente anterior, pero no permite precisar el sitio de la oclusión.

«Se eleva» = la medición del punto J queda por encima de la línea de base al redondear a 0.1 mm (el mismo criterio de
signo del caso 1). No es el umbral diagnóstico de la ESC: ese lo aplica el analizador en 12 Derivaciones.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from educational.guided_case import (CONCEPT, SOURCE, W2009, CaseData, Competencia, Decision, Estado, Evento, Prueba,
                                     case_signed as _case_signed)

ROOT = Path(__file__).resolve().parent.parent
CASE_DOC = ROOT / "docs" / "contenido" / "caso_guiado_ecg_2.md"
CASE_ID = "st_v1_v4"
TITLE = "Elevación del ST en V1–V4"
SCENARIO, SEED = "anterior_stemi", 7
__all__ = ["CONCEPT", "SOURCE", "W2009"]

SIGNED_LINES = {
    72: "Los cambios del segmento ST en un grupo de derivaciones orientan hacia la región del ventrículo afectada y, "
        "con menos certeza, hacia la arteria responsable [W2009].",
    78: "| Elevación del ST en V1–V4, I, aVL y a menudo aVR | Oclusión proximal de la descendente anterior |",
    79: "| Elevación del ST sobre todo en V3–V6 | Oclusión distal de la DA |",
    80: "| Oclusión de la DA entre la primera rama septal y la primera diagonal | Se respeta el tabique basal | El ST de "
        "V1 no se eleva. |",
}


def case_signed(doc: Path = CASE_DOC) -> bool:
    return _case_signed(doc)


def build_case_data(seed: int = SEED) -> CaseData:
    from src.signals.ecg.twelve_lead_measure import analyze_twelve_lead
    from src.signals.ecg.twelve_lead_synth import generate_twelve_lead

    leads, truth = generate_twelve_lead(SCENARIO, seed=seed)
    report = analyze_twelve_lead(leads, truth.fs)
    if not report.st_j_mv:
        raise RuntimeError(f"el analizador no midió el ST: {report.unavailable}")
    return CaseData(leads=leads, fs=truth.fs, st_mm={k: 10.0 * v for k, v in report.st_j_mv.items()})


def _valores(data: CaseData, leads: Sequence[str]) -> str:
    return " · ".join(f"{ld} {data.mm(ld):+.1f} mm" for ld in leads)


def _sube(data: CaseData, lead: str) -> bool:
    return data.mm(lead) > 0


# ── Pruebas ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def _res_v1(d: CaseData) -> str:
    return f"{_valores(d, ('V1',))}: " + ("V1 se eleva." if _sube(d, "V1") else "V1 no se eleva.")


def _res_i_avl(d: CaseData) -> str:
    partes = [f"{ld} {'se eleva' if _sube(d, ld) else 'no se eleva'}" for ld in ("I", "aVL")]
    return f"{_valores(d, ('I', 'aVL'))}: {' y '.join(partes)}."


def _res_v5_v6(d: CaseData) -> str:
    """Compara lo que se ve en pantalla: V5–V6 contra V3–V4."""
    menor = max(d.mm("V5"), d.mm("V6")) < min(d.mm("V3"), d.mm("V4"))
    return (f"{_valores(d, ('V3', 'V4', 'V5', 'V6'))}: "
            + ("V5 y V6 se elevan menos que V3 y V4." if menor else "V5 y V6 se elevan tanto o más que V3 o V4."))


def _res_avr(d: CaseData) -> str:
    return f"{_valores(d, ('aVR',))}: " + ("aVR se eleva." if _sube(d, "aVR") else "aVR no se eleva.")


PRUEBAS: Tuple[Prueba, ...] = (
    Prueba("st_v1", "Revisar el ST en V1",
           ("Ver si V1 se eleva: si no se eleva, la oclusión de la DA puede estar entre la primera septal y la primera "
            "diagonal",
            "Medir la duración del QRS en V1 para compararla con la de las demás derivaciones precordiales del trazado "
            "simulado",
            "Calcular la frecuencia cardiaca a partir de los intervalos RR que se ven en la tira de V1, latido por latido "
            "y en reposo"), 80, _res_v1),
    Prueba("st_i_avl", "Revisar el ST en I y aVL",
           ("Ver si I y aVL se elevan, lo que junto con V1–V4 sugiere oclusión proximal de la descendente anterior",
            "Medir el intervalo PR en I y aVL, que son las derivaciones donde mejor se ve la onda P de este trazado "
            "simulado",
            "Calcular el eje del QRS con I y aVL, que es lo único que esas dos derivaciones del plano frontal permiten "
            "medir"),
           78, _res_i_avl),
    Prueba("st_v5_v6", "Revisar el ST en V3–V6",
           ("Ver si la elevación está sobre todo en V3–V6, que sugiere oclusión distal de la DA",
            "Medir el intervalo QT en V5 y V6, donde la onda T termina con más claridad que en las demás",
            "Buscar descenso del ST en V5–V6, el patrón llamado «posterior» que describe la tabla del tema 5"),
           79, _res_v5_v6),
    Prueba("st_avr", "Revisar el ST en aVR",
           ("Ver si aVR se eleva, como ocurre a menudo en la oclusión proximal de la descendente anterior",
            "Medir la duración del QRS en aVR para saber si hay un bloqueo de rama en el trazado del caso",
            "Calcular la frecuencia cardiaca con aVR, que es la derivación de referencia para contar los latidos"),
           78, _res_avr),
)
PRUEBA = {p.id: p for p in PRUEBAS}


# ── Decisiones (la correcta va PRIMERO) ─────────────────────────────────────────────────────────────────────────────
DECISIONES: Tuple[Decision, ...] = (
    Decision("grupo", "Mira el trazado. ¿En qué grupo de derivaciones está más elevado el ST?",
             ("V1–V4", "II, III y aVF, las tres derivaciones que miran desde abajo",
              "I y aVL, junto con V5 y V6 del lado izquierdo",
              "En ninguno: el ST está en la línea de base en las doce"),
             "El analizador mide la mayor elevación del ST en V1–V4.", None),
    Decision("hipotesis_inicial", "Con solo ese dato, ¿hacia qué arteria orienta la tabla firmada?",
             ("La descendente anterior; el sitio de la oclusión depende de qué otras derivaciones se eleven",
              "La coronaria derecha, porque es la arteria que más a menudo se ocluye en un infarto con elevación del ST",
              "La circunfleja, porque es la arteria que irriga a la vez la pared anterior y la lateral del ventrículo",
              "Ninguna: la elevación del ST en V1–V4 no orienta hacia una arteria responsable concreta en ningún caso"),
             "Las tres filas de la tabla que tratan las precordiales (oclusión proximal, distal y entre la primera "
             "septal y la primera diagonal) son de la descendente anterior [W2009].", 78),
    Decision("hipotesis_final", "Con las pruebas que pediste, ¿qué sugiere el trazado sobre el sitio de la oclusión?",
             ("Sugiere la descendente anterior, pero el sitio no se puede precisar: falta la elevación en I",
              "Oclusión proximal de la descendente anterior, con seguridad, porque V1–V4 están elevados en el trazado",
              "Oclusión distal de la descendente anterior, porque la elevación está sobre todo en V3–V6 de este trazado",
              "Oclusión entre la primera septal y la primera diagonal, porque el ST de V1 no se eleva en este trazado"),
             "La oclusión proximal se acompaña de elevación en V1–V4, I, aVL y a menudo aVR; la distal, sobre todo en "
             "V3–V6; y entre la primera septal y la primera diagonal, el ST de V1 no se eleva [W2009]. Este trazado no "
             "cumple del todo ninguno de los tres.", 78),
    Decision("limite", "Antes de cerrar: ¿puedes afirmar cuál es la arteria responsable?",
             ("No: el ECG orienta hacia la arteria responsable, con menos certeza que hacia la región",
              "Sí: la tabla firmada lo demuestra con la elevación del ST en V1–V4 que mide el analizador en este trazado",
              "Sí, porque V2 y V3 son las derivaciones más elevadas de todo el registro simulado de doce derivaciones",
              "No, porque la elevación en V1–V4 orienta a la coronaria derecha y no a la descendente anterior del caso"),
             "Los cambios del segmento ST en un grupo de derivaciones orientan hacia la región del ventrículo afectada "
             "y, con menos certeza, hacia la arteria responsable [W2009].", 72),
)
DECISION = {d.id: d for d in DECISIONES}


def responder(estado: Estado, decision_id: str, opcion: str, confianza: Optional[int]) -> bool:
    d = DECISION[decision_id]
    if opcion not in d.opciones:
        raise ValueError(f"opción desconocida para {decision_id}: {opcion}")
    correcto = opcion == d.correcta
    if decision_id == "hipotesis_final" and estado.primera_final is None:
        estado.primera_final = opcion
        estado.pruebas_antes_de_concluir = tuple(estado.pruebas)
    estado.respuestas[decision_id] = opcion
    estado.confianzas[decision_id] = confianza
    estado.recorrido.append(Evento("decision", decision_id, f"{d.pregunta} → {opcion}", correcto, confianza))
    return correcto


def pedir_prueba(estado: Estado, data: CaseData, prueba_id: str, motivo: str) -> str:
    p = PRUEBA[prueba_id]
    if motivo not in p.motivos:
        raise ValueError(f"motivo desconocido para {prueba_id}: {motivo}")
    texto = p.resultado(data) if p.resultado(data) is not None else p.no_disponible
    estado.pruebas.setdefault(prueba_id, motivo)
    estado.recorrido.append(Evento("prueba", prueba_id, f"{p.nombre} ({motivo}) → {texto}", motivo == p.motivo_correcto))
    return texto


def desafio(estado: Estado, data: CaseData) -> str:
    """El revisor crítico, por reglas: cuestiona la hipótesis final con lo medido y la línea firmada."""
    r = estado.respuestas.get("hipotesis_final")
    d = DECISION["hipotesis_final"]
    pidio = set(estado.pruebas)
    if r == d.opciones[0]:
        texto = (f"Tu conclusión se apoya en lo que mediste: {_valores(data, ('I', 'aVL'))}. La oclusión proximal se "
                 "acompaña de elevación en V1–V4, I, aVL y a menudo aVR [W2009]. ¿Qué te falta para precisar el sitio?"
                 if "st_i_avl" in pidio else
                 "¿Qué dato te falta para precisar el sitio? La oclusión proximal se acompaña de elevación en V1–V4, I, "
                 "aVL y a menudo aVR [W2009], y todavía no revisaste I y aVL.")
    elif r == d.opciones[1]:
        texto = (f"La oclusión proximal se acompaña de elevación en V1–V4, I, aVL y a menudo aVR [W2009], y en este "
                 f"trazado miden {_valores(data, ('I', 'aVL', 'aVR'))}. ¿Se cumple el patrón completo?")
    elif r == d.opciones[2]:
        texto = (f"La oclusión distal eleva el ST sobre todo en V3–V6 [W2009], y en este trazado miden "
                 f"{_valores(data, ('V3', 'V4', 'V5', 'V6'))}. ¿Dónde está la mayor elevación?")
    else:
        texto = (f"Entre la primera septal y la primera diagonal, el ST de V1 no se eleva [W2009], y en este trazado "
                 f"mide {_valores(data, ('V1',))}. ¿Qué dato apoya tu respuesta?")
    estado.desafio = texto
    estado.recorrido.append(Evento("desafio", "hipotesis_final", texto))
    return texto


def competencias(estado: Estado) -> List[Competencia]:
    r, pidio = estado.respuestas, estado.pruebas
    ini, fin, lim = r.get("hipotesis_inicial"), r.get("hipotesis_final"), r.get("limite")
    justificadas = [p for p, m in pidio.items() if m == PRUEBA[p].motivo_correcto]
    clave = {"st_v1", "st_i_avl", "st_v5_v6"}
    return [
        Competencia("Reconoce hacia qué arteria orienta el primer dato",
                    None if ini is None else ini == DECISION["hipotesis_inicial"].correcta,
                    "Las tres filas de la tabla que tratan las precordiales son de la descendente anterior [W2009]."),
        Competencia("Pide las pruebas que distinguen los tres patrones",
                    None if not pidio and fin is None else clave <= set(pidio),
                    "V1 (t1:80), I y aVL (t1:78) y V3–V6 (t1:79) separan los tres patrones de la descendente anterior "
                    "[W2009]."),
        Competencia("Justifica cada prueba que pide",
                    None if not pidio else len(justificadas) == len(pidio),
                    f"{len(justificadas)} de {len(pidio)} pruebas pedidas con el motivo que las sostiene." if pidio
                    else "Cada prueba pedida, con el motivo que la sostiene."),
        Competencia("No afirma más de lo que el trazado permite",
                    None if fin is None else fin == DECISION["hipotesis_final"].correcta,
                    "Este trazado no cumple del todo ninguno de los tres patrones: el sitio no se puede precisar."),
        Competencia("Reconoce el límite del ECG",
                    None if lim is None else lim == DECISION["limite"].correcta,
                    "El ECG orienta hacia la arteria responsable con menos certeza que hacia la región [W2009]."),
    ]
