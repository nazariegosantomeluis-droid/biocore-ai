"""Pasaporte de evidencia (2026-11-17): un botón junto a un valor que abre qué es ese dato y de dónde sale.

`render_evidence_passport(campo, valor)` abre un popover con siete apartados, siempre los mismos y en este orden
(`SECTIONS`): el valor, el tipo de dato, qué lo produce, la regla o ecuación, los supuestos, lo que no está modelado y
la fuente enlazada a la Bibliografía.

Art. I:
- Todo lo que muestra sale de `app.utils.evidence_registry` (citas literales con su ubicación). Un apartado sin cita
  dice «no documentado»; el pasaporte no redacta ni completa nada.
- El tipo de dato sale de la procedencia con una tabla explícita (`PROVENANCE_TYPE`). Ninguna procedencia del UPS es
  «inferido por IA»: el narrador explica valores, no los produce. Sin procedencia, el tipo es «desconocido».
- Un campo que no está en el registro no dibuja nada: no se inventa un pasaporte vacío.
"""

from __future__ import annotations

import html
import importlib
from dataclasses import dataclass
from typing import Any, Optional, Tuple

import streamlit as st

from app.utils.design_system import PALETTE
from app.utils.evidence_registry import Cita, Evidencia, Fuente, get_evidence
from domain.physiology.state.schema import Provenance

NOT_DOCUMENTED = "no documentado"
NO_VALUE = "Sin dato"

SECTION_VALUE = "Valor"
SECTION_TYPE = "Tipo de dato"
SECTION_PRODUCES = "Qué lo produce"
SECTION_RULE = "Regla o ecuación"
SECTION_ASSUMPTIONS = "Supuestos"
SECTION_NOT_MODELED = "Qué no está modelado"
SECTION_SOURCE = "Fuente"
SECTIONS = (SECTION_VALUE, SECTION_TYPE, SECTION_PRODUCES, SECTION_RULE, SECTION_ASSUMPTIONS, SECTION_NOT_MODELED,
            SECTION_SOURCE)

DATA_TYPES = ("medido", "simulado", "estimado", "inferido por IA", "desconocido")
UNKNOWN_TYPE = "desconocido"

# Tabla explícita procedencia -> tipo de dato. Una procedencia nueva sin fila aquí da «desconocido» (y una prueba falla
# hasta que alguien la clasifique).
PROVENANCE_TYPE = {
    Provenance.SENSOR_REAL: "medido",
    Provenance.SIMULACION: "simulado",
    Provenance.DERIVADO: "estimado",                 # calculado a partir de otras entradas
    Provenance.MODELO_HEMODINAMICO: "estimado",      # lo calcula el motor hemodinámico
    Provenance.DERIVADO_ACOPLAMIENTO: "estimado",    # lo cambia una regla de acoplamiento
    Provenance.REFERENCIA_CLINICA: "estimado",       # valor de referencia citado, no medido en esta persona
    Provenance.ARRASTRE_TEMPORAL: "estimado",        # se asume que la última lectura sigue vigente (schema.py)
}

DATA_TYPE_MEANING = {
    "medido": "Lo mandó un sensor real conectado en esta sesión.",
    "simulado": "Lo generó una simulación de BIOCORE; no es la medición de una persona.",
    "estimado": "Lo calcula un modelo, una fórmula o una regla a partir de otros valores.",
    "inferido por IA": "Lo produjo un modelo de IA.",
    "desconocido": "BIOCORE no tiene declarada la procedencia de este valor.",
}

VARIABLE = "variable"


def _as_provenance(procedencia: Any) -> Optional[Provenance]:
    """Acepta el enum, su nombre («SIMULACION») o su valor («simulacion»)."""
    if isinstance(procedencia, Provenance):
        return procedencia
    if isinstance(procedencia, str):
        if procedencia in Provenance.__members__:
            return Provenance[procedencia]
        try:
            return Provenance(procedencia)
        except ValueError:
            return None
    return None


def data_type(procedencia: Any) -> str:
    """Una de las 5 categorías de `DATA_TYPES`, por la tabla `PROVENANCE_TYPE`."""
    prov = _as_provenance(procedencia)
    return PROVENANCE_TYPE.get(prov, UNKNOWN_TYPE) if prov is not None else UNKNOWN_TYPE


@dataclass(frozen=True)
class SourceView:
    clave: Optional[str]           # «[RCP2017]» o None
    referencia: Optional[str]      # el texto que muestra la Bibliografía
    cita: Optional[Cita]           # dónde liga el código este valor con la fuente


@dataclass(frozen=True)
class PassportView:
    """Lo que el pasaporte muestra, sin Streamlit (las pruebas lo comparan con el registro)."""

    campo: str
    etiqueta: str
    valor: str
    tipo: str
    tipo_significado: str
    procedencia: Optional[str]        # nombre del enum con el que se clasificó, o None
    procedencia_cita: Optional[Cita]
    produce: Optional[str]
    origen: Optional[str]
    regla: Optional[Cita]
    supuestos: Optional[Cita]
    no_modelado: Optional[Cita]
    fuente: Optional[SourceView]


def _reference_for_key(clave: str) -> Optional[str]:
    from app.supermodules.bibliography import SIGNED

    return next((r.text for r in SIGNED if r.key == clave), None)


def _reference_for_constant(constante: str) -> Optional[str]:
    """El texto de una cita que el código guarda en una constante, con el mismo formato que le da la Bibliografía."""
    from app.supermodules.bibliography import _uniform

    module_name, _, attr = constante.rpartition(".")
    try:
        citation = getattr(importlib.import_module(module_name), attr)
    except (ImportError, AttributeError):
        return None
    return _uniform(citation)[0]


def _source_view(fuente: Optional[Fuente]) -> Optional[SourceView]:
    if fuente is None:
        return None
    if fuente.clave:
        return SourceView(f"[{fuente.clave}]", _reference_for_key(fuente.clave), fuente.cita)
    if fuente.constante:
        return SourceView(None, _reference_for_constant(fuente.constante), fuente.cita)
    return SourceView(None, None, fuente.cita) if fuente.cita else None


def _format_value(valor: Any) -> str:
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return NO_VALUE
    return str(valor)


def passport_view(campo: str, valor: Any, procedencia: Any = None) -> Optional[PassportView]:
    """`procedencia` en ejecución (p. ej. la del descriptor del UPS) manda sobre la del registro; si no llega y el
    registro dice «variable», el tipo es «desconocido»."""
    ev: Optional[Evidencia] = get_evidence(campo)
    if ev is None:
        return None
    runtime = _as_provenance(procedencia)
    static = None if ev.procedencia in (None, VARIABLE) else _as_provenance(ev.procedencia)
    prov = runtime or static
    tipo = data_type(prov)
    return PassportView(
        campo=campo, etiqueta=ev.etiqueta, valor=_format_value(valor), tipo=tipo,
        tipo_significado=DATA_TYPE_MEANING[tipo], procedencia=prov.name if prov else None,
        procedencia_cita=ev.procedencia_cita, produce=ev.produce, origen=ev.origen,
        regla=ev.regla, supuestos=ev.supuestos, no_modelado=ev.no_modelado, fuente=_source_view(ev.fuente),
    )


# ───────────────────────────── dibujo ─────────────────────────────

def _quote_html(texto: str) -> str:
    return (f"<div class='biocore-passport-quote' style='border-left:3px solid {PALETTE.NEUTRAL}; padding:2px 10px; "
            f"color:{PALETTE.TEXT}; white-space:pre-wrap;'>{html.escape(texto)}</div>")


def _render_cita(cita: Optional[Cita]) -> None:
    if cita is None:
        st.markdown(NOT_DOCUMENTED)
        return
    st.markdown(_quote_html(cita.texto), unsafe_allow_html=True)
    st.caption(f"En `{cita.ubicacion}`")


def _section(title: str) -> None:
    st.markdown(f"**{title}**")


def render_passport_body(view: PassportView) -> None:
    """Los siete apartados de `SECTIONS`, en orden. Lo usa el popover y lo pueden reutilizar las pruebas."""
    from app.utils import navigation as nav

    _section(SECTION_VALUE)
    st.markdown(html.escape(view.valor), unsafe_allow_html=True)

    _section(SECTION_TYPE)
    detalle = f" (procedencia `{view.procedencia}`)" if view.procedencia else ""
    st.markdown(f"{view.tipo}{detalle}. {view.tipo_significado}")
    if view.procedencia_cita is not None:
        st.caption(f"La procedencia se fija en `{view.procedencia_cita.ubicacion}`")

    _section(SECTION_PRODUCES)
    if view.produce or view.origen:
        st.markdown(" · ".join(f"`{p}`" for p in (view.produce, view.origen) if p))
    else:
        st.markdown(NOT_DOCUMENTED)

    _section(SECTION_RULE)
    _render_cita(view.regla)
    _section(SECTION_ASSUMPTIONS)
    _render_cita(view.supuestos)
    _section(SECTION_NOT_MODELED)
    _render_cita(view.no_modelado)

    _section(SECTION_SOURCE)
    src = view.fuente
    if src is None or (src.referencia is None and src.cita is None):
        st.markdown(NOT_DOCUMENTED)
        return
    if src.referencia:
        prefix = f"{src.clave} " if src.clave else ""
        st.markdown(_quote_html(f"{prefix}{src.referencia}"), unsafe_allow_html=True)
    elif src.clave:
        st.markdown(src.clave)
    if src.cita is not None:
        st.caption(f"Citada en `{src.cita.ubicacion}`")
    nav.link("bibliografia", "Ver en la Bibliografía")


def render_evidence_passport(campo: str, valor: Any, procedencia: Any = None, key: Optional[str] = None) -> None:
    """Botón «Evidencia: <rótulo>» junto al valor. Un campo sin registro no dibuja nada."""
    view = passport_view(campo, valor, procedencia)
    if view is None:
        return
    with st.popover(f"Evidencia: {view.etiqueta}", key=key or f"passport_{campo}"):
        render_passport_body(view)


def rendered_sections(view: PassportView) -> Tuple[str, ...]:
    """Los apartados que el pasaporte dibuja (siempre todos, en orden): para las pruebas."""
    return SECTIONS
