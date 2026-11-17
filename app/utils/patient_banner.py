"""Banner del paciente activo (I2, integración 2026-11-17).

Contexto: los estudiantes valoraron que BIOCORE sea «íntegro» (un solo UPS), pero al moverse entre laboratorios no se
notaba que era el MISMO paciente. `render_active_patient_banner()` lo hace visible: una caja al inicio de cada página
de Explorar con el id corto del paciente activo, la fuente que manda en el gemelo y la ÚLTIMA FC, FR y SpO₂ que el UPS
tiene de ese paciente, cada una con su procedencia.

Art. I (cada valor con su procedencia; si falta, «sin dato»; nunca un valor por defecto):
- Los valores salen de `get_latest_state()` (el último snapshot PERSISTIDO). Un valor que el UPS no tiene se dice
  «Sin dato», jamás se rellena.
- No hay paciente hasta que alguien lo crea (el gemelo al abrirse, o un «Guardar estado al gemelo»). El banner NO lo
  crea: mirar una página no escribe en la base. Sin paciente dice «Sin paciente activo».
- `read_active_vitals()` es la ÚNICA lectura: el banner y Calculadoras (carga de FC/FR/SpO₂ y puntos NEWS2) la
  comparten, así que no pueden divergir.
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Optional

import streamlit as st

from app.utils.design_system import PALETTE
from app.utils.patient_session import _PATIENT_ID_KEY, get_active_session_factory
from clinical.calculators import news2_partial, news2_points_text
from domain.physiology.state import Provenance, get_latest_state
from domain.physiology.state.schema import PhysiologicalDescriptor

BANNER_KEY = "active_patient_banner"          # `st.container(key=...)`: la prueba lo busca por texto, no por DOM
NO_PATIENT_TEXT = "Sin paciente activo"
NO_DATA_TEXT = "Sin dato"
SHORT_ID_LEN = 8

# Bandera que el botón «Calcular en Calculadoras» del gemelo deja y Calculadoras consume al abrir (carga FC/FR/SpO₂).
CALC_LOAD_PATIENT_KEY = "calc_load_patient"

# La fuente que manda en Twin OS la declara `twin_shell.pages.INPUT_SOURCE_KEY`; se repite la CLAVE (no se importa
# `twin_shell.pages`: arrastra el narrador y la IA a cada página). Una prueba exige que sean la misma.
INPUT_SOURCE_KEY = "twin_shell_input_source"
SLIDERS_SOURCE = "sliders de Twin OS (simulación)"
NO_SOURCE = "sin fuente declarada"

# Procedencia del UPS en español, para el estudiante (el enum guarda el valor interno).
PROVENANCE_ES = {
    Provenance.SENSOR_REAL: "Sensor real",
    Provenance.SIMULACION: "Simulación",
    Provenance.DERIVADO: "Derivado",
    Provenance.REFERENCIA_CLINICA: "Referencia clínica",
    Provenance.MODELO_HEMODINAMICO: "Modelo hemodinámico",
    Provenance.DERIVADO_ACOPLAMIENTO: "Derivado por acoplamiento",
    Provenance.ARRASTRE_TEMPORAL: "Arrastre temporal",
}

# El UPS guarda «bpm»; en pantalla va «lpm» (ningún inglés visible).
UNIT_ES = {"bpm": "lpm"}

# (clave, rótulo, dominio del UPS, nombre del descriptor, componente NEWS2 de `news2_partial`)
VITALS = (
    ("hr", "FC", "cardiovascular", "heart_rate", "Pulso"),
    ("rr", "FR", "respiratory", "respiratory_rate", "Frecuencia respiratoria"),
    ("spo2", "SpO₂", "respiratory", "spo2", "SpO₂ (escala 1)"),
)


@dataclass(frozen=True)
class ActiveVitals:
    """Lo que el UPS sabe HOY del paciente activo. `patient_id` None = no hay paciente; un descriptor ausente = el UPS
    no tiene ese valor (sin dato)."""

    patient_id: Optional[str]
    values: dict       # clave ("hr", "rr", "spo2") -> PhysiologicalDescriptor | None

    @property
    def short_id(self) -> Optional[str]:
        return self.patient_id[:SHORT_ID_LEN] if self.patient_id else None


def peek_active_patient_id() -> Optional[str]:
    """El paciente activo de la sesión SI YA EXISTE. A diferencia de `get_active_patient_id()`, nunca lo crea."""
    return st.session_state.get(_PATIENT_ID_KEY)


def read_active_vitals() -> ActiveVitals:
    """Última FC, FR y SpO₂ del paciente activo tal como las persistió el UPS."""
    patient_id = peek_active_patient_id()
    empty = {key: None for key, *_ in VITALS}
    if patient_id is None:
        return ActiveVitals(None, dict(empty))
    with get_active_session_factory()() as session:
        state = get_latest_state(session, patient_id)
    if state is None:
        return ActiveVitals(patient_id, dict(empty))
    domains = state.all_domains()
    values = {key: domains[domain].get(name) for key, _label, domain, name, _component in VITALS}
    return ActiveVitals(patient_id, values)


def active_source_label() -> str:
    """Qué fuente manda hoy en el gemelo: un escenario o intervención aplicados, o los sliders."""
    declared = st.session_state.get(INPUT_SOURCE_KEY)
    if declared:
        return str(declared)
    return SLIDERS_SOURCE if "twin_shell_organism" in st.session_state else NO_SOURCE


def provenance_label(descriptor: PhysiologicalDescriptor) -> str:
    return PROVENANCE_ES.get(descriptor.provenance, descriptor.provenance.value)


def _value_html(label: str, descriptor: Optional[PhysiologicalDescriptor], news2: Optional[int] = None) -> str:
    if descriptor is None:
        return f"<span style='color:{PALETTE.NEUTRAL};'>{label}: ○ {NO_DATA_TEXT}</span>"
    detail = f" title='{html.escape(descriptor.source_detail, quote=True)}'" if descriptor.source_detail else ""
    points = f" · NEWS2 {news2_points_text(news2)}" if news2 is not None else ""
    return (f"<span{detail}>{label} <b>{descriptor.value:.0f}</b> {html.escape(UNIT_ES.get(descriptor.unit, descriptor.unit))} "
            f"<span style='color:{PALETTE.NEUTRAL};'>[{provenance_label(descriptor)}]</span>{points}</span>")


def render_active_patient_banner() -> None:
    """Una línea al inicio de cada página de Explorar: el mismo paciente en todos los laboratorios."""
    vitals = read_active_vitals()
    with st.container(border=True, key=BANNER_KEY):
        if vitals.patient_id is None:
            st.markdown(
                f"<span style='color:{PALETTE.NEUTRAL};'>○ <b>{NO_PATIENT_TEXT}</b> — abre el Gemelo digital o guarda "
                "un estado desde un laboratorio para crear el paciente que comparten todas las páginas.</span>",
                unsafe_allow_html=True,
            )
            return
        raw = {key: (d.value if d is not None else None) for key, d in vitals.values.items()}
        components = news2_partial(pulse=raw["hr"], respiratory_rate=raw["rr"], spo2=raw["spo2"]).components
        parts = " &nbsp;·&nbsp; ".join(
            _value_html(label, vitals.values[key], components.get(component))
            for key, label, _domain, _name, component in VITALS
        )
        st.markdown(
            f"🧍 <b>Paciente activo</b> <code>{html.escape(vitals.short_id)}</code> &nbsp;·&nbsp; "
            f"Fuente activa: {html.escape(active_source_label())}<br>{parts}",
            unsafe_allow_html=True,
        )
        st.caption("Último estado guardado en el UPS de esta sesión; un laboratorio lo actualiza con «Guardar estado "
                   "al gemelo». Valores simulados no son mediciones de un paciente.")


def patient_start_value(key: str, lo: float, hi: float, fallback: float, control: str) -> tuple:
    """Valor inicial de un control de simulación tomado del paciente activo (integración, 2026-11-17).

    Devuelve `(valor, nota)`. Usa la FC/FR/SpO₂ que el UPS ya tiene del paciente, redondeada, SOLO si cae dentro del
    rango del control; si no hay paciente, no hay ese valor o está fuera de rango, devuelve el valor inicial de siempre
    del laboratorio y la nota dice por qué (nunca se recorta un valor para que «quepa»: sería otro paciente). La nota
    es `None` cuando no hay paciente (el laboratorio se ve como siempre)."""
    vitals = read_active_vitals()
    if vitals.patient_id is None:
        return fallback, None
    label = next(lab for k, lab, *_ in VITALS if k == key)
    descriptor = vitals.values[key]
    if descriptor is None:
        return fallback, f"{control}: el paciente activo `{vitals.short_id}` no tiene {label} en el UPS; valor inicial de siempre."
    value = round(descriptor.value)
    unit = UNIT_ES.get(descriptor.unit, descriptor.unit)
    if not lo <= value <= hi:
        return fallback, (f"{control}: la {label} del paciente activo ({value} {unit}) está fuera del rango de este control "
                          f"({lo:g}–{hi:g}); valor inicial de siempre.")
    return value, (f"{control}: empieza en la {label} del paciente activo `{vitals.short_id}` ({value} {unit}, "
                   f"{provenance_label(descriptor)}, UPS). Si la mueves, ya es tu simulación.")
