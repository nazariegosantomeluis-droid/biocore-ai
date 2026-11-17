"""Tutor citado: la IA responde a los estudiantes SOLO con la base de conocimiento firmada (2026-11-17, Art. I).

Flujo de una pregunta:
1. Busca en la base (`educational/knowledge_base.py`). Sin fragmentos firmados → `NO_DISPONIBLE`, y el modelo ni
   siquiera se llama: no hay nada que explicar con fuente.
2. Revisa que el proveedor pueda recibir la pregunta (`privacy.check_provider_allows`). La pregunta es texto libre
   que escribe una persona, y BIOCORE no puede saber qué contiene; por la regla de `privacy.py` («lo que no se sabe
   de dónde viene cuenta como de una persona») su origen es DESCONOCIDO: el nivel gratuito de Gemini no la recibe.
3. Manda al modelo los fragmentos, sus referencias y las restricciones firmadas por Luis, con reglas estrictas.
4. Al terminar, `verificar_citas()` compara las claves que citó el modelo con las que recibió. Una clave inventada o
   una respuesta sin ninguna cita se avisa en pantalla: el modelo redacta, pero la fuente la pone la base.

Reutiliza el cliente y las reglas de privacidad del narrador (`domain/physiology/narrator/`) sin modificarlos.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterator, List, Optional

from educational import knowledge_base as kb

DEFAULT_MAX_TOKENS = 2048

SYSTEM_PROMPT = """Eres el tutor de BIOCORE, una plataforma educativa de fisiología para estudiantes de medicina.

Reglas obligatorias:
1. Responde SOLO con los fragmentos firmados que vienen en el mensaje. No uses conocimiento propio, aunque lo tengas.
2. Cada afirmación lleva su clave de cita entre corchetes, escrita tal como aparece en los fragmentos (por ejemplo,
   [SG2017]). No inventes claves ni cites fuentes que no estén en el mensaje.
3. Si los fragmentos no alcanzan para responder, dilo y nombra qué falta. No completes el hueco.
4. Si un fragmento está marcado «SIN FUENTE VERIFICADA», responde que BIOCORE no tiene una fuente verificada para
   eso y no lo afirmes.
5. Respeta al pie de la letra las «Restricciones firmadas por Luis».
6. Es un contexto educativo: no des diagnósticos, tratamientos ni indicaciones para una persona real.
7. Escribe en español, claro y breve, para un estudiante."""

AVISO_CLAVE_INVENTADA = ("La respuesta cita {claves}, que no está en los fragmentos firmados que recibió la IA. No la "
                         "tomes como fuente.")
AVISO_SIN_CITAS = ("La respuesta no cita ninguna fuente. Tómala con cautela y revisa los fragmentos firmados de abajo.")

_CLAVE = re.compile(r"\[([A-Z][A-Z0-9]+)\]")


@dataclass
class Preparacion:
    """Lo que se le manda al modelo, o el motivo para no llamarlo."""

    pregunta: str
    fragmentos: List[dict] = field(default_factory=list)
    contexto: Optional[str] = None

    @property
    def hay_respuesta(self) -> bool:
        return self.contexto is not None

    @property
    def claves_permitidas(self) -> List[str]:
        vistas: List[str] = []
        for f in self.fragmentos:
            for c in f["claves"] + list(f["referencias"]):
                if c not in vistas:
                    vistas.append(c)
        return vistas

    @property
    def referencias(self) -> dict:
        refs: dict = {}
        for f in self.fragmentos:
            refs.update(f["referencias"])
        return refs


@dataclass
class Verificacion:
    claves_citadas: List[str]
    claves_inventadas: List[str]

    @property
    def avisos(self) -> List[str]:
        if self.claves_inventadas:
            return [AVISO_CLAVE_INVENTADA.format(claves=", ".join(f"[{c}]" for c in self.claves_inventadas))]
        if not self.claves_citadas:
            return [AVISO_SIN_CITAS]
        return []


def preparar(pregunta: str, limite: int = 5, db_path=None) -> Preparacion:
    """Busca en la base. Sin fragmentos, `hay_respuesta` es falso y no se llama al modelo."""
    pregunta = (pregunta or "").strip()
    if not pregunta:
        return Preparacion(pregunta="")
    kb.asegurar_base(db_path=db_path)
    fragmentos = kb.buscar(pregunta, limite=limite, db_path=db_path)
    contexto = kb.contexto_para_ia(pregunta, limite=limite, db_path=db_path) if fragmentos else None
    return Preparacion(pregunta=pregunta, fragmentos=fragmentos, contexto=contexto)


def construir_mensajes(prep: Preparacion) -> list:
    return [{"role": "user", "content": f"{prep.contexto}\n\nPregunta del estudiante:\n{prep.pregunta}"}]


def responder(prep: Preparacion, client, model: Optional[str] = None,
              max_tokens: int = DEFAULT_MAX_TOKENS) -> Iterator[str]:
    """Respuesta en streaming (para `st.write_stream`). Sin fragmentos, devuelve `NO_DISPONIBLE` sin llamar al modelo.

    `client` es el de la sesión (`app.utils.ai_session.ai_client()`): Anthropic o Gemini, con la misma interfaz.
    """
    if not prep.hay_respuesta:
        yield kb.NO_DISPONIBLE
        return
    from domain.physiology.narrator.client import resolve_model
    from domain.physiology.narrator.privacy import DataOrigin, check_provider_allows

    check_provider_allows(client, DataOrigin.DESCONOCIDO)  # texto libre de una persona: ver el docstring del módulo
    with client.messages.stream(model=resolve_model(client, model), max_tokens=max_tokens, system=SYSTEM_PROMPT,
                                messages=construir_mensajes(prep)) as stream:
        yield from stream.text_stream


def verificar_citas(respuesta: str, prep: Preparacion) -> Verificacion:
    """Compara las claves que citó el modelo con las que recibió."""
    citadas: List[str] = []
    for c in _CLAVE.findall(respuesta or ""):
        if c not in citadas:
            citadas.append(c)
    permitidas = set(prep.claves_permitidas)
    return Verificacion(claves_citadas=citadas, claves_inventadas=[c for c in citadas if c not in permitidas])
