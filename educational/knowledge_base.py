"""Base de conocimiento de BIOCORE: lo que la IA puede consultar, y nada más (Art. I).

La base se construye SOLO desde los documentos de teoría firmados por Luis (`CORPUS`). No se escribe a mano: se
regenera desde esos documentos, así que corregir la base es corregir el documento firmado.

Qué hace:
- Lee cada documento y lo parte en fragmentos (un párrafo, una viñeta o una tabla), cada uno con su tema, su capa
  (idea, mecanismo, detalle) y las claves de cita que lo respaldan ([K2007], [SG2017]...).
- Solo entran los documentos cuyo «Estado» dice FIRMADO y, dentro de ellos, solo los temas marcados ☑ en la hoja
  de firma. Un borrador no alimenta a la IA.
- Guarda también las «Decisiones de Luis» (restricciones de cómo se dice algo) y las listas «Sin fuente verificada»
  (lo que NO se puede afirmar), para que la IA pueda responder «no disponible» con su motivo.
- Indexa todo en SQLite con FTS5 (búsqueda de texto completo, sin distinguir acentos). No necesita red ni modelos.

Uso:
    python -m educational.knowledge_base               # reconstruye la base y muestra el resumen
    python -m educational.knowledge_base "razón LF/HF"  # busca

    from educational.knowledge_base import construir, buscar, contexto_para_ia
"""
from __future__ import annotations

import hashlib
import re
import sqlite3
import sys
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = ROOT / "data" / "local" / "conocimiento.db"  # data/local/* está en .gitignore: se regenera

# Documentos que pueden alimentar la base. Uno nuevo se agrega aquí, y solo entra si está firmado.
CORPUS: Sequence[Path] = (
    ROOT / "docs" / "contenido" / "teoria_citada.md",
    ROOT / "docs" / "contenido" / "teoria_citada_2.md",
)

# Capas que afirman algo y por eso exigen cita.
CAPAS_CON_CITA = ("idea", "mecanismo", "detalle")
# Capas que no son afirmaciones clínicas: restricciones de Luis, lo excluido por falta de fuente y notas de BIOCORE.
CAPAS_SIN_CITA = ("decision", "sin_fuente", "nota")

def _ruta(db_path: Optional[Path]) -> Path:
    """La ruta se lee al llamar (no al definir la función), para que las pruebas puedan redirigir `DEFAULT_DB_PATH`."""
    return Path(db_path) if db_path is not None else DEFAULT_DB_PATH


NO_DISPONIBLE = "No disponible: ningún fragmento firmado de la base de conocimiento responde a esta consulta."

_CLAVE = re.compile(r"\[([A-Z][A-Z0-9]+)\]")
_TEMA = re.compile(r"^##\s+([A-Z]?\d+)\.\s+(.+?)\s*$")
_PARTE = re.compile(r"^#\s+(Parte\s+.+?)\s*$")
_CAPA = re.compile(r"^\*\*(Idea|Mecanismo|Detalle(?: con fuente)?)\.?\*\*\.?\s*(.*)$")
_SUBTEMA = re.compile(r"^\*\*([^*]+?)\.\*\*\s*$")
_VINETA_CAPA = re.compile(r"^-\s+\*\*(Idea|Mecanismo|Detalle):\*\*\s*(.*)$")
_DECISION = re.compile(r"^>\s*\*\*Decisión de Luis:\*\*\s*(.*)$")
_SIN_FUENTE = re.compile(r"^\*\*Sin fuente verificada[^*]*\*\*\s*(.*)$")
_REFERENCIA = re.compile(r"^-\s+\*\*\[([A-Z][A-Z0-9]+)\]\*\*\s*(.*)$")
_FIRMA = re.compile(r"^\|\s*([A-Z]?\d+)\s*\|.*☑")
_SOLO_CLAVES = re.compile(r"^(\s*\[[A-Z][A-Z0-9]+\])+\s*:?\s*$")


@dataclass
class Fragmento:
    documento: str
    tema_id: str
    tema_titulo: str
    capa: str
    texto: str
    claves: List[str]
    parte: str = ""
    subtema: str = ""
    cita_heredada: bool = False  # la clave viene del encabezado de la capa («**Mecanismo** [K2007]:»), no de la línea


@dataclass
class Documento:
    ruta: Path
    titulo: str = ""
    estado: str = ""
    fragmentos: List[Fragmento] = field(default_factory=list)
    referencias: Dict[str, str] = field(default_factory=dict)
    temas: Dict[str, str] = field(default_factory=dict)
    temas_firmados: set = field(default_factory=set)

    @property
    def firmado(self) -> bool:
        return self.estado.upper().startswith("FIRMADO")

    @property
    def nombre(self) -> str:
        return self.ruta.name


def _limpiar(texto: str) -> str:
    """Quita el marcado de Markdown que no aporta a la lectura ni a la búsqueda."""
    texto = re.sub(r"\[([^\]]+)\]\((?:https?://)[^)]+\)", r"\1", texto)  # enlaces → su texto
    texto = texto.replace("**", "").replace("`", "")
    texto = re.sub(r"(?<!\w)\*([^*]+)\*(?!\w)", r"\1", texto)
    return texto.strip()


def _claves(texto: str) -> List[str]:
    vistas: List[str] = []
    for clave in _CLAVE.findall(texto):
        if clave not in vistas:
            vistas.append(clave)
    return vistas


def leer_documento(ruta: Path) -> Documento:
    """Parte un documento de teoría citada en fragmentos, referencias y temas firmados."""
    doc = Documento(ruta=Path(ruta))
    lineas = Path(ruta).read_text(encoding="utf-8").splitlines()

    seccion = "preambulo"  # preambulo | tema | bibliografia | firma
    parte = subtema = capa = ""
    tema_id = tema_titulo = ""
    claves_encabezado: List[str] = []
    tabla: List[str] = []

    def agregar(capa_: str, texto: str, heredar: bool = True) -> None:
        texto_limpio = _limpiar(texto)
        if not texto_limpio:
            return
        propias = _claves(texto)
        if capa_ in CAPAS_CON_CITA and not propias and (
                (texto_limpio.startswith("(") and texto_limpio.endswith(")")) or "BIOCORE" in texto_limpio):
            # Comentario sobre la propia plataforma (entre paréntesis, o «Por qué BIOCORE no calcula el total…»):
            # no es una afirmación clínica, y heredarle la cita del encabezado se la atribuiría a la fuente.
            capa_ = "nota"
        claves = propias or (claves_encabezado if heredar and capa_ in CAPAS_CON_CITA else [])
        doc.fragmentos.append(Fragmento(
            documento=doc.nombre, tema_id=tema_id, tema_titulo=tema_titulo, capa=capa_, texto=texto_limpio,
            claves=list(claves), parte=parte, subtema=subtema, cita_heredada=bool(claves) and not propias,
        ))

    def cerrar_tabla() -> None:
        if tabla:
            agregar(capa or "detalle", "\n".join(tabla))
            tabla.clear()

    for cruda in lineas:
        linea = cruda.rstrip()
        if seccion != "tema":
            cerrar_tabla()

        if linea.startswith("**Estado:**") and not doc.estado:
            doc.estado = _limpiar(linea.split(":**", 1)[1])
            continue
        if linea.startswith("# ") and not doc.titulo:
            doc.titulo = _limpiar(linea[2:])
            continue
        if m := _PARTE.match(linea):
            cerrar_tabla()
            parte, seccion = _limpiar(m.group(1)), "preambulo"
            continue
        if m := _TEMA.match(linea):
            cerrar_tabla()
            seccion, tema_id, tema_titulo = "tema", m.group(1), _limpiar(m.group(2))
            subtema = capa = ""
            claves_encabezado = []
            doc.temas[tema_id] = tema_titulo
            continue
        if linea.startswith("## "):
            cerrar_tabla()
            titulo = linea[3:].strip().lower()
            seccion = "bibliografia" if titulo.startswith("bibliograf") else "firma" if "firma" in titulo else "otro"
            continue

        if seccion == "bibliografia":
            if m := _REFERENCIA.match(linea):
                doc.referencias[m.group(1)] = _limpiar(m.group(2))
            continue
        if seccion == "firma":
            if m := _FIRMA.match(linea):
                doc.temas_firmados.add(m.group(1))
            continue
        if seccion != "tema":
            continue

        # ── dentro de un tema ──
        if linea.startswith("|"):
            tabla.append(linea)
            continue
        cerrar_tabla()
        if not linea.strip() or linea.strip() == "---":
            continue
        if m := _DECISION.match(linea):
            agregar("decision", m.group(1), heredar=False)
            continue
        if m := _SIN_FUENTE.match(linea):
            agregar("sin_fuente", m.group(1), heredar=False)
            continue
        if m := _CAPA.match(linea):
            capa = "detalle" if m.group(1).startswith("Detalle") else m.group(1).lower()
            resto = m.group(2).strip()
            if not resto:
                claves_encabezado = []
            elif _SOLO_CLAVES.match(resto) or (resto.endswith(":") and _claves(resto)):
                # «**Mecanismo** [K2007]:» o «**Detalle con fuente** (valores de referencia en adultos) [MCM]:»:
                # encabezado de una lista o tabla; sus claves respaldan lo que sigue.
                claves_encabezado = _claves(resto)
            else:
                claves_encabezado = []
                agregar(capa, resto)
            continue
        if m := _SUBTEMA.match(linea):
            subtema, capa, claves_encabezado = _limpiar(m.group(1)), "", []
            continue
        if m := _VINETA_CAPA.match(linea):
            agregar(m.group(1).lower(), m.group(2), heredar=False)
            continue
        texto = linea[2:] if linea.startswith("- ") else linea
        agregar(capa or "detalle", texto)

    cerrar_tabla()
    return doc


def validar(doc: Documento) -> List[str]:
    """Problemas que impiden que un fragmento firmado alimente a la IA. Vacío = todo en orden."""
    problemas = []
    for f in doc.fragmentos:
        if f.tema_id not in doc.temas_firmados:
            continue
        if f.capa in CAPAS_CON_CITA and not f.claves:
            problemas.append(f"{doc.nombre} · tema {f.tema_id}: afirmación sin cita: «{f.texto[:80]}»")
        for clave in f.claves:
            if clave not in doc.referencias:
                problemas.append(f"{doc.nombre} · tema {f.tema_id}: la clave [{clave}] no está en su Bibliografía")
    return problemas


_ESQUEMA = """
CREATE TABLE documentos (nombre TEXT PRIMARY KEY, titulo TEXT, estado TEXT, sha256 TEXT,
                         temas_firmados INTEGER, temas_excluidos TEXT);
CREATE TABLE fragmentos (id INTEGER PRIMARY KEY, documento TEXT, tema_id TEXT, tema_titulo TEXT, parte TEXT,
                         subtema TEXT, capa TEXT, texto TEXT, claves TEXT, cita_heredada INTEGER);
CREATE TABLE referencias (documento TEXT, clave TEXT, texto TEXT, PRIMARY KEY (documento, clave));
CREATE TABLE construccion (fecha_utc TEXT, fragmentos INTEGER, referencias INTEGER);
CREATE VIRTUAL TABLE fragmentos_fts USING fts5(texto, tema_titulo, subtema, content='fragmentos',
                                               content_rowid='id', tokenize='unicode61 remove_diacritics 2');
"""


class BaseInvalidaError(RuntimeError):
    """Un documento firmado tiene una afirmación sin cita o una clave sin referencia: no se construye nada."""


def construir(db_path: Optional[Path] = None, corpus: Sequence[Path] = CORPUS) -> dict:
    """Reconstruye la base desde cero con los documentos firmados. Devuelve un resumen."""
    documentos = [leer_documento(r) for r in corpus]
    problemas = [p for d in documentos if d.firmado for p in validar(d)]
    if problemas:
        raise BaseInvalidaError("\n".join(problemas))

    db_path = _ruta(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    temporal = db_path.with_suffix(".construyendo")
    temporal.unlink(missing_ok=True)
    con = sqlite3.connect(temporal)
    resumen = {"documentos": {}, "fragmentos": 0, "referencias": 0}
    try:
        con.executescript(_ESQUEMA)
        for d in documentos:
            excluidos = sorted(set(d.temas) - d.temas_firmados) if d.firmado else sorted(d.temas)
            con.execute("INSERT INTO documentos VALUES (?,?,?,?,?,?)", (
                d.nombre, d.titulo, d.estado, hashlib.sha256(d.ruta.read_bytes()).hexdigest(),
                len(d.temas_firmados) if d.firmado else 0, ",".join(excluidos)))
            if not d.firmado:
                resumen["documentos"][d.nombre] = "excluido: no está firmado"
                continue
            usados = set()
            n = 0
            for f in d.fragmentos:
                if f.tema_id not in d.temas_firmados:
                    continue
                cur = con.execute(
                    "INSERT INTO fragmentos (documento, tema_id, tema_titulo, parte, subtema, capa, texto, claves,"
                    " cita_heredada) VALUES (?,?,?,?,?,?,?,?,?)",
                    (f.documento, f.tema_id, f.tema_titulo, f.parte, f.subtema, f.capa, f.texto,
                     ",".join(f.claves), int(f.cita_heredada)))
                con.execute("INSERT INTO fragmentos_fts (rowid, texto, tema_titulo, subtema) VALUES (?,?,?,?)",
                            (cur.lastrowid, f.texto, f.tema_titulo, f.subtema))
                usados.update(f.claves)
                n += 1
            for clave, texto in d.referencias.items():
                con.execute("INSERT INTO referencias VALUES (?,?,?)", (d.nombre, clave, texto))
            resumen["documentos"][d.nombre] = (f"{n} fragmentos de {len(d.temas_firmados)} temas firmados"
                                               + (f"; fuera por no firmados: {', '.join(excluidos)}" if excluidos else ""))
            resumen["fragmentos"] += n
            resumen["referencias"] += len(d.referencias)
        con.execute("INSERT INTO construccion VALUES (?,?,?)", (
            datetime.now(timezone.utc).isoformat(timespec="seconds"), resumen["fragmentos"], resumen["referencias"]))
        con.commit()
    finally:
        con.close()
    temporal.replace(db_path)
    return resumen


def asegurar_base(db_path: Optional[Path] = None, corpus: Sequence[Path] = CORPUS) -> Path:
    """Construye la base si falta o si algún documento del corpus cambió desde la última construcción.

    La app la llama antes de buscar: corregir un documento firmado basta para que la IA use la versión nueva.
    """
    db_path = _ruta(db_path)
    actuales = {Path(r).name: hashlib.sha256(Path(r).read_bytes()).hexdigest() for r in corpus}
    if db_path.exists():
        try:
            con = sqlite3.connect(db_path)
            try:
                guardados = dict(con.execute("SELECT nombre, sha256 FROM documentos"))
            finally:
                con.close()
            if guardados == actuales:
                return db_path
        except sqlite3.DatabaseError:
            pass  # base dañada o de un esquema anterior: se reconstruye
    construir(db_path=db_path, corpus=corpus)
    return db_path


# Palabras demasiado comunes para buscar con ellas.
_VACIAS = set("""a al ante bajo con como contra cual cuales cuando de del desde donde e el en entre es esta este esto
fue ha hay la las le les lo los mas me mi muy ni no o para pero por porque que se si sin sobre son su sus tambien te
tiene un una uno unos unas y ya yo qué cómo cuál cuándo dónde por qué es son está están ser""".split())


# Sinónimos para BUSCAR (2026-11-17): cada grupo reúne formas de nombrar lo mismo, sobre todo una sigla y su nombre
# completo, para que «electromiografía» encuentre los fragmentos que dicen «EMG». Solo amplían la búsqueda: no son
# afirmaciones y no cambian lo que la base contiene ni lo que la IA puede citar. Un término nuevo se agrega a su grupo
# (o a un grupo nuevo) y `tests/test_knowledge_base.py` exige que ningún término esté en dos grupos.
SINONIMOS: Sequence[Sequence[str]] = (
    ("EMG", "electromiografía", "electromiograma", "electromiográfica", "electromiográfico"),
    ("HRV", "VFC", "variabilidad de la frecuencia cardiaca", "variabilidad de la frecuencia cardíaca",
     "variabilidad cardiaca", "variabilidad cardíaca"),
    ("ECG", "EKG", "electrocardiograma", "electrocardiografía", "electrocardiográfico"),
    ("EEG", "electroencefalograma", "electroencefalografía", "electroencefalográfico"),
    ("FC", "frecuencia cardiaca", "frecuencia cardíaca"),
    ("FR", "frecuencia respiratoria", "respiraciones por minuto"),
    ("arritmia sinusal respiratoria", "RSA", "ASR"),
    ("diafonía", "crosstalk", "cross-talk"),
    ("contracción voluntaria máxima", "contracción voluntaria isométrica máxima", "contracción máxima", "MVC", "MVIC",
     "CVM", "CVIM"),
    ("SpO₂", "SpO2", "saturación de oxígeno", "pulsioximetría", "oximetría de pulso"),
    ("RMS", "raíz cuadrática media", "valor eficaz"),
    ("vectorcardiograma", "VCG", "ECG en 3D"),
    ("DA", "descendente anterior"),
    ("CD", "coronaria derecha"),
    ("Cx", "circunfleja"),
    ("LF", "baja frecuencia"),
    ("HF", "alta frecuencia"),
    ("VLF", "muy baja frecuencia"),
    ("ULF", "ultra baja frecuencia"),
    ("Cheyne-Stokes", "Cheyne Stokes"),
)


def _normalizar(texto: str) -> str:
    """Minúsculas, sin acentos y con un espacio entre palabras: para encontrar un término dentro de la consulta."""
    sin_acentos = "".join(c for c in unicodedata.normalize("NFKD", texto.lower()) if not unicodedata.combining(c))
    return " ".join(re.findall(r"\w+", sin_acentos))


def _analizar(consulta: str):
    """Separa la consulta en (grupos de sinónimos que nombra, palabras sueltas que quedan).

    Gana el término más largo: en «variabilidad de la frecuencia cardiaca» se reconoce la frase entera (grupo de HRV),
    y «frecuencia cardiaca» ya no cuenta aparte; sus palabras tampoco se buscan sueltas.
    """
    resto = f" {_normalizar(consulta)} "
    terminos = sorted(((_normalizar(t), g) for g in SINONIMOS for t in g), key=lambda x: -len(x[0]))
    grupos: List[Sequence[str]] = []
    for termino, grupo in terminos:
        if f" {termino} " in resto:
            resto = resto.replace(f" {termino} ", " ")
            if grupo not in grupos:
                grupos.append(grupo)
    palabras = [p for p in resto.split() if p not in _VACIAS and len(p) > 1]
    return grupos, palabras


def _sinonimos_de(consulta: str) -> List[str]:
    """Los términos con los que se amplía la consulta (todas las formas de los grupos que nombra)."""
    return [t for grupo in _analizar(consulta)[0] for t in grupo]


def _consulta_fts(consulta: str) -> str:
    grupos, palabras = _analizar(consulta)
    # Las palabras sueltas, entre comillas (FTS5 no interpreta nada dentro) y con prefijo: «normaliz» halla
    # «normalizada». Los sinónimos, exactos y sin prefijo (una sigla corta como «DA» con prefijo hallaría «daño»);
    # los de varias palabras, como frase.
    partes = [f'"{p}"*' for p in dict.fromkeys(palabras)]
    partes += [f'"{t.replace(chr(34), "")}"' for t in dict.fromkeys(t for g in grupos for t in g)]
    return " OR ".join(partes)


def buscar(consulta: str, limite: int = 5, db_path: Optional[Path] = None,
           incluir: Sequence[str] = CAPAS_CON_CITA + ("sin_fuente",)) -> List[dict]:
    """Los fragmentos firmados que mejor responden a la consulta, con sus referencias completas.

    Lista vacía = la base no tiene nada firmado sobre eso: quien llame debe decir «no disponible», no improvisar.
    """
    expresion = _consulta_fts(consulta)
    if not expresion:
        return []
    db_path = _ruta(db_path)
    if not db_path.exists():
        raise FileNotFoundError(f"La base no está construida: {db_path}. Corre `python -m educational.knowledge_base`.")
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        marcas = ",".join("?" * len(incluir))
        filas = con.execute(
            f"SELECT f.*, bm25(fragmentos_fts, 1.0, 0.5, 0.5) AS puntaje FROM fragmentos_fts"
            f" JOIN fragmentos f ON f.id = fragmentos_fts.rowid"
            f" WHERE fragmentos_fts MATCH ? AND f.capa IN ({marcas}) ORDER BY puntaje LIMIT ?",
            (expresion, *incluir, limite)).fetchall()
        resultados = []
        for fila in filas:
            claves = [c for c in fila["claves"].split(",") if c]
            refs = {c: r["texto"] for c in claves for r in con.execute(
                "SELECT texto FROM referencias WHERE documento=? AND clave=?", (fila["documento"], c))}
            resultados.append({k: fila[k] for k in ("id", "documento", "tema_id", "tema_titulo", "parte", "subtema",
                                                     "capa", "texto")}
                              | {"claves": claves, "referencias": refs, "cita_heredada": bool(fila["cita_heredada"])})
        return resultados
    finally:
        con.close()


def decisiones_de(documento: str, tema_id: str, db_path: Optional[Path] = None) -> List[str]:
    """Las «Decisiones de Luis» de un tema: restricciones que toda explicación de ese tema debe respetar."""
    con = sqlite3.connect(_ruta(db_path))
    try:
        return [r[0] for r in con.execute(
            "SELECT texto FROM fragmentos WHERE documento=? AND tema_id=? AND capa='decision' ORDER BY id",
            (documento, tema_id))]
    finally:
        con.close()


def contexto_para_ia(consulta: str, limite: int = 5, db_path: Optional[Path] = None) -> Optional[str]:
    """El bloque de contexto que recibe el modelo: fragmentos firmados, sus fuentes y las decisiones de su tema.

    `None` = no hay nada firmado: la respuesta al estudiante es `NO_DISPONIBLE`, sin llamar al modelo.
    """
    fragmentos = buscar(consulta, limite=limite, db_path=db_path)
    if not fragmentos:
        return None
    partes = ["Responde SOLO con estos fragmentos firmados de BIOCORE. Cita cada afirmación con su clave entre "
              "corchetes. Si no alcanzan para responder, di qué falta en lugar de completarlo.", ""]
    referencias: Dict[str, str] = {}
    temas = []
    for i, f in enumerate(fragmentos, 1):
        etiqueta = "SIN FUENTE VERIFICADA (no afirmar)" if f["capa"] == "sin_fuente" else f["capa"]
        tema = f"{f['tema_titulo']} ({f['subtema']})" if f["subtema"] else f["tema_titulo"]
        partes.append(f"[{i}] Tema {f['tema_id']}. {tema} · {etiqueta} · "
                      f"{' '.join('[' + c + ']' for c in f['claves']) or 'sin clave'}\n{f['texto']}")
        referencias.update(f["referencias"])
        if (f["documento"], f["tema_id"]) not in temas:
            temas.append((f["documento"], f["tema_id"]))
    reglas = [d for doc, tema in temas for d in decisiones_de(doc, tema, db_path)]
    if reglas:
        partes += ["", "Restricciones firmadas por Luis (obligatorias):"] + [f"- {r}" for r in reglas]
    partes += ["", "Referencias:"] + [f"[{c}] {t}" for c, t in referencias.items()]
    return "\n".join(partes)


def _main(argv: Sequence[str]) -> int:
    if argv:
        consulta = " ".join(argv)
        contexto = contexto_para_ia(consulta)
        print(contexto if contexto else NO_DISPONIBLE)
        return 0
    resumen = construir()
    print(f"Base construida en {_ruta(None)}")
    for nombre, estado in resumen["documentos"].items():
        print(f"  {nombre}: {estado}")
    print(f"  Total: {resumen['fragmentos']} fragmentos, {resumen['referencias']} referencias")
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
