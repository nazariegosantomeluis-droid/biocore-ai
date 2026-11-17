"""Caso guiado de ECG: razonar con incertidumbre sobre un trazado simulado (2026-11-17, Art. I).

Un caso progresivo: el estudiante ve el ECG de 12 derivaciones, plantea una hipótesis, PIDE pruebas y justifica por
qué, recibe un desafío a su conclusión y al final ve su recorrido. Junta tres ideas de la plataforma:
- **Uncertainty Lab:** el dato inicial no basta para decidir (coronaria derecha o circunfleja), una prueba no está
  disponible (derivaciones derechas) y el estudiante debe reconocerlo.
- **Agente adversarial por reglas:** antes de cerrar, el caso cuestiona la conclusión con evidencia del propio caso.
  No hay modelo de lenguaje: las reglas son fijas y cada frase cita su línea firmada.
- **Calibración:** cada decisión lleva la confianza declarada (`app/utils/session_learning.py`, source «caso_guiado»).

Art. I:
- El trazado es SIMULADO (`src/signals/ecg/twelve_lead_synth.py`) y así se declara.
- Los resultados de las pruebas salen de la MEDICIÓN del analizador de BIOCORE sobre ese trazado
  (`twelve_lead_measure.analyze_twelve_lead`), no de un texto escrito a mano.
- Todo texto de enseñanza cita su línea del tema 5 firmado de `docs/contenido/teoria_citada.md` («t1:N»), con la
  clave [W2009]. El caso solo se muestra si `docs/contenido/caso_guiado_ecg.md` está FIRMADO (`case_signed()`).
- Las derivaciones se nombran por su nombre (II, III, aVF…), no por pared: decisión de Luis en el tema 5 (t1:70).

No depende de Streamlit.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Mapping, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
CASE_DOC = ROOT / "docs" / "contenido" / "caso_guiado_ecg.md"
CASE_ID = "st_ii_iii_avf"
CONCEPT = "derivaciones_e_isquemia"
SOURCE = "caso_guiado"
SCENARIO, SEED = "inferior_stemi", 7
W2009 = "W2009"

# Líneas firmadas del tema 5 de `teoria_citada.md` que usa el caso (la prueba las compara con el documento).
SIGNED_LINES = {
    72: "Los cambios del segmento ST en un grupo de derivaciones orientan hacia la región del ventrículo afectada y, "
        "con menos certeza, hacia la arteria responsable [W2009].",
    78: "Elevación del ST en V1–V4, I, aVL y a menudo aVR",
    81: "Coronaria derecha (CD) o circunfleja (Cx), según cuál dé la descendente posterior (dominancia). Elevación "
        "mayor en III que en II sugiere CD.",
    82: "Elevación en I y aVL junto con cambios inferiores",
    83: "Elevación del ST en V3R y V4R (derivaciones derechas)",
    84: "Puede deberse a CD o Cx; con cambios inferiores no es posible saber cuál.",
}


def case_signed(doc: Path = CASE_DOC) -> bool:
    """El caso solo se muestra si su documento dice «**Estado:** FIRMADO» (C4: nada sin firmar en la app)."""
    if not doc.exists():
        return False
    for linea in doc.read_text(encoding="utf-8").splitlines():
        if linea.startswith("**Estado:**"):
            return linea.split(":**", 1)[1].strip().upper().startswith("FIRMADO")
    return False


# ── Datos del caso: el trazado simulado y lo que mide el analizador ─────────────────────────────────────────────────
@dataclass(frozen=True)
class CaseData:
    leads: Mapping[str, object]
    fs: float
    st_mm: Mapping[str, float]       # ST en el punto J, medido por el analizador, en mm (10 mm = 1 mV)

    def mm(self, lead: str) -> float:
        return round(self.st_mm[lead], 1) + 0.0     # + 0.0: un cero redondeado nunca se muestra como «-0.0»


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


# ── Pruebas que el estudiante puede pedir ───────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Prueba:
    id: str
    nombre: str
    motivos: Tuple[str, ...]                     # el correcto va PRIMERO (como en `quiz_bank`)
    linea: int                                   # línea firmada que justifica pedirla
    resultado: Callable[[CaseData], Optional[str]]   # None = no disponible en este registro
    no_disponible: str = ""

    @property
    def motivo_correcto(self) -> str:
        return self.motivos[0]


def _res_ii_iii(d: CaseData) -> str:
    comp = "III es mayor que II" if d.mm("III") > d.mm("II") else "III no es mayor que II"
    return f"{_valores(d, ('II', 'III', 'aVF'))}. {comp}."


def _res_i_avl(d: CaseData) -> str:
    sentido = ("descenso, no elevación" if d.mm("I") < 0 and d.mm("aVL") < 0 else
               "elevación" if d.mm("I") > 0 and d.mm("aVL") > 0 else "valores de signo distinto")
    return f"{_valores(d, ('I', 'aVL'))}: {sentido}."


def _res_v1_v3(d: CaseData) -> str:
    texto = _valores(d, ("V1", "V2", "V3"))
    return texto + (": no hay descenso." if all(d.mm(v) >= 0 for v in ("V1", "V2", "V3")) else ".")


def _res_v1_v4(d: CaseData) -> str:
    texto = _valores(d, ("V1", "V2", "V3", "V4"))
    return texto + (": no hay elevación." if all(d.mm(v) <= 0 for v in ("V1", "V2", "V3", "V4")) else ".")


PRUEBAS: Tuple[Prueba, ...] = (
    Prueba("st_ii_iii", "Medir el ST en II, III y aVF",
           ("Comparar II con III: una elevación mayor en III que en II sugiere coronaria derecha",
            "Calcular la frecuencia cardiaca", "Buscar una onda delta"), 81, _res_ii_iii),
    Prueba("st_i_avl", "Revisar el ST en I y aVL",
           ("Ver si hay elevación en I y aVL, que junto con cambios en II, III y aVF puede acompañar a la circunfleja",
            "Medir el intervalo PR", "Calcular el eje del QRS"), 82, _res_i_avl),
    Prueba("st_v1_v3", "Revisar el ST en V1–V3",
           ("Buscar descenso del ST en V1–V3, el patrón llamado «posterior»",
            "Medir la duración del QRS", "Buscar una onda delta"), 84, _res_v1_v3),
    Prueba("st_v1_v4", "Revisar el ST en V1–V4",
           ("Descartar la elevación en V1–V4 que orienta a la descendente anterior",
            "Calcular la frecuencia cardiaca", "Medir el intervalo QT"), 78, _res_v1_v4),
    Prueba("v3r_v4r", "Pedir V3R y V4R (derivaciones derechas)",
           ("Buscar afectación del ventrículo derecho, que orienta a oclusión proximal de la coronaria derecha",
            "Mejorar la calidad del trazado", "Calcular el eje del QRS"), 83, lambda d: None,
           no_disponible="No disponible: este registro no tiene derivaciones derechas; el simulador solo genera las 12 "
                         "estándar. Con lo que hay no se puede saber si el ventrículo derecho está afectado."),
)
PRUEBA = {p.id: p for p in PRUEBAS}


# ── Decisiones (la correcta va PRIMERO) ─────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Decision:
    id: str
    pregunta: str
    opciones: Tuple[str, ...]
    explicacion: str
    linea: Optional[int]          # None = la respuesta sale de la medición del caso, no de la teoría

    @property
    def correcta(self) -> str:
        return self.opciones[0]


DECISIONES: Tuple[Decision, ...] = (
    Decision("grupo", "Mira el trazado. ¿En qué grupo de derivaciones está más elevado el ST?",
             ("II, III y aVF", "V1–V4", "I, aVL, V5 y V6", "En ninguno: el ST está en la línea de base"),
             "El analizador mide la mayor elevación del ST en II, III y aVF.", None),
    Decision("hipotesis_inicial", "Con solo ese dato, ¿qué arteria es la responsable?",
             ("La coronaria derecha o la circunfleja: con este dato no se puede decir cuál",
              "La coronaria derecha, con seguridad", "La circunfleja, con seguridad", "La descendente anterior"),
             "Una elevación del ST en II, III y aVF puede deberse a la coronaria derecha o a la circunfleja, según "
             "cuál dé la descendente posterior [W2009]. Hace falta otro dato para orientarse.", 81),
    Decision("hipotesis_final", "Con las pruebas que pediste, ¿qué sugiere el trazado?",
             ("Sugiere coronaria derecha: la elevación es mayor en III que en II",
              "Sugiere circunfleja", "Sugiere descendente anterior",
              "Sigue sin poder distinguirse entre coronaria derecha y circunfleja"),
             "Una elevación mayor en III que en II sugiere coronaria derecha [W2009]. «Sugiere» no es «demuestra».", 81),
    Decision("limite", "Antes de cerrar: ¿puedes afirmar que el ventrículo derecho está afectado?",
             ("No: haría falta ver V3R y V4R, y este registro no las tiene",
              "Sí, porque hay elevación en II, III y aVF", "Sí, porque III es mayor que II",
              "No, porque la coronaria derecha no se relaciona con el ventrículo derecho"),
             "La afectación del ventrículo derecho se ve como elevación del ST en V3R y V4R [W2009]. Sin esas "
             "derivaciones, no se puede afirmar ni descartar.", 83),
)
DECISION = {d.id: d for d in DECISIONES}


# ── Estado del caso y desafío adversarial ───────────────────────────────────────────────────────────────────────────
@dataclass
class Evento:
    tipo: str                    # "decision" | "prueba" | "desafio"
    id: str
    texto: str
    correcto: Optional[bool] = None
    confianza: Optional[int] = None


@dataclass
class Estado:
    respuestas: Dict[str, str] = field(default_factory=dict)        # decisión → opción elegida (la vigente)
    confianzas: Dict[str, Optional[int]] = field(default_factory=dict)
    primera_final: Optional[str] = None                             # la primera respuesta a «hipotesis_final»
    pruebas: Dict[str, str] = field(default_factory=dict)           # prueba → motivo elegido
    pruebas_antes_de_concluir: Tuple[str, ...] = ()
    desafio: Optional[str] = None                                   # el desafío mostrado a la hipótesis final
    recorrido: List[Evento] = field(default_factory=list)


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
    resultado = p.resultado(data)
    texto = resultado if resultado is not None else p.no_disponible
    estado.pruebas.setdefault(prueba_id, motivo)
    estado.recorrido.append(Evento("prueba", prueba_id, f"{p.nombre} ({motivo}) → {texto}", motivo == p.motivo_correcto))
    return texto


def desafio(estado: Estado, data: CaseData) -> str:
    """El revisor crítico: cuestiona la hipótesis final con evidencia del propio caso y la línea firmada."""
    r = estado.respuestas.get("hipotesis_final")
    d = DECISION["hipotesis_final"]
    pidio = set(estado.pruebas)
    if r == d.opciones[0]:              # coronaria derecha
        if "st_ii_iii" not in pidio:
            texto = ("¿Qué dato te permite distinguir la coronaria derecha de la circunfleja? Con elevación en II, III "
                     "y aVF las dos son posibles [W2009], y todavía no comparaste II con III.")
        else:
            texto = (f"Tu conclusión se apoya en lo que mediste: III ({data.mm('III'):+.1f} mm) mayor que II "
                     f"({data.mm('II'):+.1f} mm) sugiere coronaria derecha [W2009]. Sugerir no es demostrar: "
                     "¿qué no puedes afirmar todavía con este registro?")
    elif r == d.opciones[1]:            # circunfleja
        if "st_i_avl" in pidio:
            texto = (f"Pediste I y aVL y tienen descenso ({_valores(data, ('I', 'aVL'))}), no elevación. La elevación "
                     "en I y aVL junto con cambios en II, III y aVF es la que puede acompañar a la circunfleja "
                     "[W2009]. ¿Qué dato apoya tu respuesta?")
        else:
            texto = ("¿Qué dato apoya la circunfleja? La elevación en I y aVL junto con cambios en II, III y aVF puede "
                     "acompañarla [W2009], y no la has revisado.")
    elif r == d.opciones[2]:            # descendente anterior
        texto = (f"La elevación en V1–V4 orienta a la descendente anterior [W2009], y en este trazado miden "
                 f"{_valores(data, ('V1', 'V2', 'V3', 'V4'))}. ¿Qué dato apoya tu respuesta?")
    else:                               # sigue sin distinguirse
        if "st_ii_iii" in pidio:
            texto = (f"Mediste III ({data.mm('III'):+.1f} mm) mayor que II ({data.mm('II'):+.1f} mm), y una elevación "
                     "mayor en III que en II sugiere coronaria derecha [W2009]. ¿Mantienes que no se puede "
                     "distinguir?")
        else:
            texto = ("Hay un dato que puede orientar: comparar II con III [W2009]. ¿Quieres pedirlo antes de "
                     "responder?")
    estado.desafio = texto
    estado.recorrido.append(Evento("desafio", "hipotesis_final", texto))
    return texto


# ── Competencias de razonamiento con incertidumbre ──────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Competencia:
    nombre: str
    lograda: Optional[bool]       # None = todavía no hay con qué evaluarla
    evidencia: str


def competencias(estado: Estado) -> List[Competencia]:
    r, pidio = estado.respuestas, estado.pruebas
    ini, fin, lim = r.get("hipotesis_inicial"), r.get("hipotesis_final"), r.get("limite")
    justificadas = [p for p, m in pidio.items() if m == PRUEBA[p].motivo_correcto]
    out = [
        Competencia("Reconoce lo que el primer dato no permite decidir",
                    None if ini is None else ini == DECISION["hipotesis_inicial"].correcta,
                    "Con elevación en II, III y aVF, la coronaria derecha y la circunfleja son posibles [W2009]."),
        Competencia("Pide la prueba que distingue las hipótesis",
                    None if not pidio and fin is None else "st_ii_iii" in pidio,
                    "Comparar II con III es lo que orienta entre coronaria derecha y circunfleja [W2009]."),
        Competencia("Justifica cada prueba que pide",
                    None if not pidio else len(justificadas) == len(pidio),
                    f"{len(justificadas)} de {len(pidio)} pruebas pedidas con el motivo que las sostiene." if pidio
                    else "Cada prueba pedida, con el motivo que la sostiene."),
        Competencia("Evita concluir antes de tener el dato",
                    None if estado.primera_final is None else
                    not (estado.primera_final in DECISION["hipotesis_final"].opciones[:3]
                         and "st_ii_iii" not in estado.pruebas_antes_de_concluir),
                    "Una arteria concreta solo se sostiene después de comparar II con III."),
        Competencia("Actualiza la hipótesis con la nueva evidencia",
                    None if fin is None else fin == DECISION["hipotesis_final"].correcta,
                    "De «coronaria derecha o circunfleja» a «sugiere coronaria derecha» al ver III mayor que II."),
        Competencia("Reconoce la información que falta",
                    None if lim is None and "v3r_v4r" not in pidio else
                    (lim == DECISION["limite"].correcta) if lim is not None else True,
                    "Sin V3R y V4R no se puede afirmar ni descartar la afectación del ventrículo derecho [W2009]."),
    ]
    return out
