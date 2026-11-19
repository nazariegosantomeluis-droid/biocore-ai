"""Banner del paciente activo (I2, integración 2026-11-17).

Contexto: los estudiantes valoraron que BIOCORE sea «íntegro» (un solo UPS), pero al moverse entre laboratorios no se
notaba que era el MISMO paciente. `render_active_patient_banner()` lo hace visible: una caja al inicio de cada página
de Explorar con el id corto del paciente activo, la fuente que manda en el gemelo y la ÚLTIMA FC, FR y SpO₂ que el UPS
tiene de ese paciente, cada una con su procedencia.

Art. I (cada valor con su procedencia; si falta, «sin dato»; nunca un valor por defecto):
- Los valores salen del paciente compuesto (`get_composed_patient()`, T0 de la ruta integrada, 2026-11-18): el último
  valor de cada descriptor; uno de un snapshot anterior se muestra como arrastre, con su procedencia de origen y su
  edad («Simulación · hace 3 min»), porque el último snapshot de un laboratorio no trae lo que no midió. Un valor que
  el UPS no tiene se dice «Sin dato», jamás se rellena.
- No hay paciente hasta que alguien lo crea (el gemelo al abrirse, o un «Guardar estado al gemelo»). El banner NO lo
  crea: mirar una página no escribe en la base. Sin paciente dice «Sin paciente activo».
- `read_active_vitals()` es la ÚNICA lectura: el banner y Calculadoras (carga de FC/FR/SpO₂ y puntos NEWS2) la
  comparten, así que no pueden divergir.
"""

from __future__ import annotations

import html
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import streamlit as st

from app.utils.design_system import PALETTE
from app.utils.evidence_passport import render_evidence_passport
from app.utils.patient_session import _PATIENT_ID_KEY, get_active_session_factory
from clinical.calculators import news2_partial, news2_points_text
from domain.physiology.state import CarryOrigin, Provenance, get_composed_patient, horizon_of
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
    origins: dict = field(default_factory=dict)   # clave -> CarryOrigin, SOLO de los valores arrastrados

    @property
    def short_id(self) -> Optional[str]:
        return self.patient_id[:SHORT_ID_LEN] if self.patient_id else None


def peek_active_patient_id() -> Optional[str]:
    """El paciente activo de la sesión SI YA EXISTE. A diferencia de `get_active_patient_id()`, nunca lo crea."""
    return st.session_state.get(_PATIENT_ID_KEY)


def read_active_vitals() -> ActiveVitals:
    """Última FC, FR y SpO₂ del paciente activo según el paciente compuesto (con el origen de las arrastradas)."""
    patient_id = peek_active_patient_id()
    empty = {key: None for key, *_ in VITALS}
    if patient_id is None:
        return ActiveVitals(None, dict(empty))
    with get_active_session_factory()() as session:
        composed = get_composed_patient(session, patient_id)
    if composed is None:
        return ActiveVitals(patient_id, dict(empty))
    domains = composed.state.all_domains()
    values = {key: domains[domain].get(name) for key, _label, domain, name, _component in VITALS}
    origins = {key: composed.origins[(domain, name)] for key, _label, domain, name, _component in VITALS
               if (domain, name) in composed.origins}
    return ActiveVitals(patient_id, values, origins)


def active_source_label() -> str:
    """Qué fuente manda hoy en el gemelo: un escenario o intervención aplicados, o los sliders."""
    declared = st.session_state.get(INPUT_SOURCE_KEY)
    if declared:
        return str(declared)
    return SLIDERS_SOURCE if "twin_shell_organism" in st.session_state else NO_SOURCE


# Campo del registro de evidencia de cada valor del banner (`app/utils/evidence_registry.py`).
PASSPORT_FIELDS = {"hr": "banner.fc", "rr": "banner.fr", "spo2": "banner.spo2"}


def _passport_value(descriptor: Optional[PhysiologicalDescriptor]) -> Optional[str]:
    if descriptor is None:
        return None
    return f"{descriptor.value:.0f} {UNIT_ES.get(descriptor.unit, descriptor.unit)}"


def passport_args(vitals: "ActiveVitals", key: str) -> tuple:
    """(valor, procedencia) para el pasaporte de un signo del banner. Un arrastre lleva la procedencia de ORIGEN (el
    tipo de dato sale de ahí: «simulado», no «estimado») y el valor dice que es un arrastre y su edad."""
    descriptor = vitals.values[key]
    origin = vitals.origins.get(key)
    if origin is None:
        return _passport_value(descriptor), getattr(descriptor, "provenance", None)
    return (f"{_passport_value(descriptor)} (arrastre: {vital_provenance_text(descriptor, origin)})",
            origin.provenance)


def provenance_label(descriptor: PhysiologicalDescriptor) -> str:
    return PROVENANCE_ES.get(descriptor.provenance, descriptor.provenance.value)


# Plantillas de la edad de un arrastre; el Inicio (página traducida) las pasa por `t()`.
AGE_TEMPLATES = ("hace {n} s", "hace {n} min", "hace {n} h")


def age_text(age_s: float, translate=lambda text: text) -> str:
    """Edad de un valor arrastrado, en palabras: «hace 5 s», «hace 2 min», «hace 2 h»."""
    if age_s < 60:
        return translate(AGE_TEMPLATES[0]).format(n=int(age_s))
    if age_s < 3600:
        return translate(AGE_TEMPLATES[1]).format(n=int(age_s // 60))
    return translate(AGE_TEMPLATES[2]).format(n=int(age_s // 3600))


def origin_age_s(origin: CarryOrigin) -> float:
    """Edad de un arrastre contada hasta ahora (no hasta el último snapshot): lo que el estudiante necesita saber."""
    return max(0.0, (datetime.now(timezone.utc) - origin.timestamp).total_seconds())


def vital_provenance_text(descriptor: PhysiologicalDescriptor, origin: Optional[CarryOrigin] = None) -> str:
    """La procedencia que se muestra: la del valor o, si es un arrastre, la de su origen con su edad."""
    if origin is None:
        # T3 (detalle de la T1.1): un valor del último paso de una trayectoria dice su horizonte, como sus arrastres.
        horizon = horizon_of(descriptor.source_detail)
        if horizon is not None:
            return f"{provenance_label(descriptor)} · horizonte {HORIZON_ES.get(horizon, horizon)}"
        return provenance_label(descriptor)
    return f"{PROVENANCE_ES.get(origin.provenance, origin.provenance.value)} · {origin_when_text(origin)}"


# Revisión final de la T6: los horizontes de las trayectorias en palabras («7d» se mostraba crudo).
HORIZON_ES = {"now": "ahora", "5min": "5 min", "30min": "30 min", "2h": "2 h", "24h": "24 h", "7d": "7 días"}


def origin_when_text(origin: CarryOrigin, translate=lambda text: text) -> str:
    """Cuándo es el valor: su horizonte si sale de una trayectoria de escenario (T1.1: sus pasos se guardan con
    segundos de diferencia, así que «hace 2 s» no diría nada del tiempo simulado), si no su edad hasta ahora."""
    if origin.horizon is not None:
        # «now» es el código del primer paso de la trayectoria; en pantalla, «ahora» (como el selector del gemelo).
        label = HORIZON_ES.get(origin.horizon, origin.horizon)
        return translate("horizonte {h}").format(h=translate(label))
    return age_text(origin_age_s(origin), translate)


def display_detail(descriptor: PhysiologicalDescriptor, origin: Optional[CarryOrigin] = None) -> Optional[str]:
    """El texto al pasar el cursor sobre un valor. Para un valor de un guardado anterior, su procedencia y su edad con
    el MISMO texto de la etiqueta (T1.1: el `source_detail` del arrastre cuenta la edad hasta el último snapshot, la
    etiqueta hasta ahora; eran dos números para lo mismo), más el detalle original del valor si lo tenía."""
    if origin is None:
        return descriptor.source_detail
    text = f"Valor de un guardado anterior ({vital_provenance_text(descriptor, origin)})"
    return f"{text}; {origin.source_detail}" if origin.source_detail else text


def _value_html(label: str, descriptor: Optional[PhysiologicalDescriptor], news2: Optional[int] = None,
                origin: Optional[CarryOrigin] = None) -> str:
    if descriptor is None:
        return f"<span style='color:{PALETTE.NEUTRAL};'>{label}: ○ {NO_DATA_TEXT}</span>"
    title = display_detail(descriptor, origin)
    detail = f" title='{html.escape(title, quote=True)}'" if title else ""
    points = f" · NEWS2 {news2_points_text(news2)}" if news2 is not None else ""
    return (f"<span{detail}>{label} <b>{descriptor.value:.0f}</b> {html.escape(UNIT_ES.get(descriptor.unit, descriptor.unit))} "
            f"<span style='color:{PALETTE.NEUTRAL};'>[{vital_provenance_text(descriptor, origin)}]</span>{points}</span>")


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
            _value_html(label, vitals.values[key], components.get(component), vitals.origins.get(key))
            for key, label, _domain, _name, component in VITALS
        )
        st.markdown(
            f"🧍 <b>Paciente activo</b> <code>{html.escape(vitals.short_id)}</code> &nbsp;·&nbsp; "
            f"Fuente activa: {html.escape(active_source_label())}<br>{parts}",
            unsafe_allow_html=True,
        )
        # Pasaporte de evidencia (2026-11-17): un botón por valor; el tipo de dato sale de la procedencia guardada.
        for col, (key, *_rest) in zip(st.columns(len(VITALS)), VITALS):
            with col:
                valor, procedencia = passport_args(vitals, key)
                render_evidence_passport(PASSPORT_FIELDS[key], valor, procedencia=procedencia)
        st.caption("Últimos valores guardados en el UPS de esta sesión, cada uno con su procedencia; un laboratorio los "
                   "actualiza con «Guardar estado al gemelo». Valores simulados no son mediciones de un paciente.")


def patient_seed(key: str, lo: float, hi: float, fallback: float, control: str,
                 vitals: Optional["ActiveVitals"] = None) -> tuple:
    """`patient_start_value` más un tercer dato: si el paciente TIENE ese valor (`True`), aunque quede fuera del rango
    del control y el control arranque en su valor de siempre. Lo usa el gemelo (T1.1) para saber si un slider sin
    mover está en lugar de un valor del paciente: entonces el cuerpo muestra el del paciente (revisión final de la
    T1.1: una SpO₂ medida de 69 no puede quedar tapada por el 98 de un slider que nadie movió)."""
    vitals = vitals if vitals is not None else read_active_vitals()
    if vitals.patient_id is None:
        return fallback, None, False
    label = next(lab for k, lab, *_ in VITALS if k == key)
    descriptor = vitals.values[key]
    if descriptor is None:
        return fallback, (f"{control}: el paciente activo `{vitals.short_id}` no tiene {label} en el UPS; valor "
                          "inicial de siempre."), False
    value = round(descriptor.value)
    unit = UNIT_ES.get(descriptor.unit, descriptor.unit)
    if not lo <= value <= hi:
        return fallback, (f"{control}: la {label} del paciente activo ({value} {unit}) está fuera del rango de este "
                          f"control ({lo:g}–{hi:g}); valor inicial de siempre."), True
    return value, (f"{control}: empieza en la {label} del paciente activo `{vitals.short_id}` ({value} {unit}, "
                   f"{vital_provenance_text(descriptor, vitals.origins.get(key))}, UPS). Si la mueves, ya es tu "
                   "simulación."), True


def patient_start_value(key: str, lo: float, hi: float, fallback: float, control: str) -> tuple:
    """Valor inicial de un control de simulación tomado del paciente activo (integración, 2026-11-17).

    Devuelve `(valor, nota)`. Usa la FC/FR/SpO₂ que el UPS ya tiene del paciente, redondeada, SOLO si cae dentro del
    rango del control; si no hay paciente, no hay ese valor o está fuera de rango, devuelve el valor inicial de siempre
    del laboratorio y la nota dice por qué (nunca se recorta un valor para que «quepa»: sería otro paciente). La nota
    es `None` cuando no hay paciente (el laboratorio se ve como siempre)."""
    value, note, _from_patient = patient_seed(key, lo, hi, fallback, control)
    return value, note
