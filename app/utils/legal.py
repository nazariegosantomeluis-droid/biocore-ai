"""Textos legales de BIOCORE AI en la app (2026-11-17): Términos y condiciones, Aviso de privacidad, aviso clínico de
entrada (casilla obligatoria) y precauciones de seguridad del manual en los tutoriales de hardware.

Origen: los textos que entregó Luis el 2026-11-17, copiados en `docs/legal/textos_legales.md` (lo exige
`tests/test_legal.py`: cada texto de este módulo está literal en ese documento).

Art. I:
- Lo que hoy es cierto va tal como lo entregó Luis. Las frases que describían algo que BIOCORE no hace (simulaciones
  «validadas», cuentas institucionales, «Capa Docente», servidores cifrados, estimación de oxigenación por sensor, que
  nada se transfiere a terceros aunque la IA reciba datos) llevan una redacción fiel a lo que existe, marcada en el
  documento como AJUSTE pendiente de la firma de Luis; el original queda allí para cuando esas funciones existan.
- Los datos que nadie ha dado (entidad legal, domicilio, correos, universidad, consumo del kit) NO se inventan: se
  muestran como «[pendiente: …]» hasta que se llenen en `LEGAL_DATA`.
- La casilla obligatoria no detecta que el texto se haya leído hasta el final (Streamlit no lo informa) y no lo afirma:
  el botón se activa solo al marcar la casilla.
"""
from __future__ import annotations

from typing import Dict, Optional, Sequence, Tuple

LEGAL_DOC = "docs/legal/textos_legales.md"
VERSION = "17 de noviembre de 2026"

# ── Datos que faltan: se muestran como «[pendiente: …]» hasta que alguien los dé ─────────────────────────────────────
LEGAL_DATA: Dict[str, Optional[str]] = {
    "entidad_legal": None,       # [Nombre de tu Empresa / Entidad Legal]
    "domicilio": None,           # [Dirección fiscal de tu empresa]
    "correo_privacidad": None,   # [Correo de Privacidad de tu Empresa]
    "universidad": None,         # [Nombre de la Universidad]
    "dominio": None,             # (ej. @dominio.edu.mx)
    "consumo_ma": None,          # [X] mA (solo empaque, no se muestra en la app)
    "contacto_soporte": None,    # [Sitio web o correo de soporte] (solo empaque)
}
DATA_LABELS = {
    "entidad_legal": "nombre de la entidad legal",
    "domicilio": "domicilio fiscal",
    "correo_privacidad": "correo de privacidad",
    "universidad": "nombre de la universidad",
    "dominio": "dominio de correo institucional",
    "consumo_ma": "consumo máximo del kit en mA",
    "contacto_soporte": "sitio web o correo de soporte",
}


def pending_marker(key: str) -> str:
    return f"[pendiente: {DATA_LABELS[key]}]"


def missing_data() -> Tuple[str, ...]:
    return tuple(k for k, v in LEGAL_DATA.items() if not (v or "").strip())


class _Filled(dict):
    def __missing__(self, key):          # un dato desconocido falla aquí, no en pantalla
        raise KeyError(f"dato legal desconocido: {key}")


def fill(template: str) -> str:
    """El texto con cada dato dado, o con su marcador «[pendiente: …]» si nadie lo ha dado."""
    values = _Filled({k: (v.strip() if v and v.strip() else pending_marker(k)) for k, v in LEGAL_DATA.items()})
    return template.format_map(values)


# ── Términos y condiciones (versión de la app) ──────────────────────────────────────────────────────────────────────
FOOTER_NOTICE = "BIOCORE AI NO ES UN DISPOSITIVO MÉDICO: uso exclusivamente educativo."
IN_REVIEW_NOTICE = ("Documento en revisión: hay cláusulas pendientes de firma y datos de la entidad legal por completar "
                    "(se muestran como «[pendiente: …]»).")

TERMS_TITLE = "Términos y condiciones de uso de BIOCORE AI"
TERMS: Tuple[Tuple[str, str, str], ...] = (
    ("TC1", "1. Naturaleza y propósito del servicio (uso exclusivamente educativo)",
     "BIOCORE AI es una plataforma digital y ecosistema de hardware diseñado estrictamente como un laboratorio virtual "
     "de simulación fisiológica para la enseñanza en ciencias de la salud. BIOCORE AI NO ES UN DISPOSITIVO MÉDICO, no "
     "cuenta con Registro Sanitario ante COFEPRIS y no está diseñado, destinado ni autorizado para el diagnóstico, "
     "tratamiento, mitigación, cura o prevención de ninguna enfermedad o condición médica en seres humanos."),
    ("TC2", "2. Exclusión de responsabilidad médica",
     "Las señales obtenidas a través de los sensores (ECG, EMG, pulso, temperatura), así como los cálculos, métricas "
     "(incluida la saturación de oxígeno, que hoy solo proviene del modelo simulado: la plataforma no la calcula a "
     "partir del sensor de pulso) y escenarios clínicos generados por el motor hemodinámico o el gemelo digital, son "
     "para fines exclusivamente pedagógicos y de práctica deliberada. Ningún dato arrojado por BIOCORE AI sustituye el "
     "juicio clínico de un profesional de la salud. El usuario libera a {entidad_legal} y a la institución educativa "
     "de cualquier responsabilidad derivada de la interpretación personal de estos datos fuera del entorno académico."),
    ("TC3", "3. Principio de transparencia de datos (Artículo I)",
     "BIOCORE AI opera bajo el principio de estricta procedencia de datos. La plataforma declara visualmente el origen "
     "de cada valor que muestra, distinguiendo si fue: a) Medido físicamente por los sensores. b) Simulado a través del "
     "motor hemodinámico o del gemelo digital. c) Tomado de una referencia bibliográfica o guía clínica. d) Calculado a "
     "partir de otros valores, con su criterio rotulado (con fuente, criterio propio de BIOCORE o heurística). El "
     "usuario acepta que la plataforma no inferirá ni inventará diagnósticos, mostrando «sin dato» o «no disponible» "
     "cuando carezca de la información."),
    ("TC4", "4. Propiedad intelectual y restricciones de uso",
     "Todo el software, código fuente, algoritmos del motor hemodinámico, interfaces y diseño del hardware son "
     "propiedad exclusiva de {entidad_legal}, salvo los componentes de terceros (bibliotecas, ecuaciones y métodos "
     "publicados, bases de datos y módulos comerciales como el AD8232 o el MyoWare), que conservan su autoría y su "
     "licencia y se listan en THIRD_PARTY_NOTICES.md. Al acceder a BIOCORE AI mediante una licencia institucional, el "
     "usuario y la universidad aceptan que está estrictamente prohibido: a) Realizar ingeniería inversa, desensamblar o "
     "descompilar las placas, sensores (AD8232, MyoWare, etc.) o el software. b) Utilizar la plataforma o el hardware "
     "para fines comerciales, ensayos clínicos formales o fuera del dominio institucional autorizado."),
    ("TC5", "5. Cuentas institucionales",
     "Hoy BIOCORE AI no tiene cuentas de usuario ni inicio de sesión. Cuando existan, el acceso se otorgará "
     "exclusivamente a estudiantes y profesores activos bajo el dominio autorizado de {universidad} ({dominio}), y la "
     "institución será responsable de revocar el acceso a usuarios que dejen de formar parte de su comunidad "
     "académica."),
)

# ── Aviso de privacidad (versión de la app) ─────────────────────────────────────────────────────────────────────────
PRIVACY_TITLE = "Aviso de privacidad integral de BIOCORE AI"
PRIVACY_PREAMBLE = (
    "De conformidad con lo establecido en la Ley Federal de Protección de Datos Personales en Posesión de los "
    "Particulares (LFPDPPP), {entidad_legal}, con domicilio en {domicilio}, pone a su disposición el presente Aviso de "
    "Privacidad.")
PRIVACY: Tuple[Tuple[str, str, str], ...] = (
    ("AP1", "1. Datos personales recabados",
     "Hoy BIOCORE AI no tiene cuentas: no recaba nombre, correo institucional, matrícula ni rol. El único dato que "
     "puede identificarle es el «ID del estudiante» que usted escribe en la Academia (texto libre), que se guarda con "
     "sus respuestas en una base local de la computadora donde corre la plataforma. Datos personales sensibles "
     "(biométricos y fisiológicos): las señales de electrocardiograma (ECG), electromiograma (EMG), fotopletismografía "
     "(PPG), pulso y temperatura corporal obtenidas con el hardware del sistema, y el EEG si se conecta un equipo "
     "externo. Las señales se procesan durante la sesión; si usted pulsa «Guardar al gemelo», se guardan los valores "
     "calculados (no la señal completa) en una base local, con su procedencia."),
    ("AP2", "2. Finalidad del tratamiento de datos",
     "Los datos personales sensibles recabados se utilizarán única y exclusivamente para: permitir al usuario "
     "visualizar su propio estado fisiológico dentro del gemelo digital con fines de aprendizaje práctico, y procesar "
     "escenarios de simulación clínica dentro de la plataforma. Hoy no existe una Capa Docente ni calificación con "
     "datos fisiológicos. Cuando exista, los datos fisiológicos del grupo se presentarán al profesor de forma disociada "
     "y anonimizada, a menos que el estudiante otorgue su consentimiento explícito para vincular su nombre a sus "
     "registros clínicos para fines de calificación."),
    ("AP3", "3. Transferencia de datos",
     "Sus datos personales y sensibles no serán transferidos a terceros comerciales, aseguradoras, instituciones "
     "médicas ni entidades externas ajenas a {universidad}. Hoy se guardan solo en la computadora donde corre BIOCORE "
     "AI: no hay servidores de BIOCORE AI. Excepción: si usted pega una clave de IA en Ajustes y usa la narración con IA "
     "o «Pregunta a BIOCORE», el texto de su pregunta y los datos del contexto se envían al proveedor que eligió "
     "(Anthropic o Google). Con el nivel gratuito de Gemini nunca se envían datos de personas: solo datos simulados o "
     "de bases públicas."),
    ("AP4", "4. Derechos ARCO",
     "Usted tiene derecho a Acceder, Rectificar, Cancelar u Oponerse (Derechos ARCO) al tratamiento de sus datos. Para "
     "ejercer estos derechos o revocar su consentimiento, deberá enviar un correo a {correo_privacidad}, donde se le "
     "indicará el procedimiento."),
    ("AP5", "5. Consentimiento expreso para datos sensibles",
     "Hoy no hay registro de cuentas. Cuando exista, al marcar la casilla «He leído y acepto el Aviso de Privacidad» al "
     "crear su cuenta, usted otorgará su consentimiento expreso y por escrito (mediante firma electrónica o validación "
     "de clic) para el tratamiento de sus datos personales sensibles bajo los términos aquí expuestos. Mientras tanto, "
     "este aviso está en Ajustes y al pie de cada página."),
)

# ── Aviso clínico y educativo de entrada (casilla obligatoria) ──────────────────────────────────────────────────────
CLICKWRAP_TITLE = "Aviso clínico y educativo"
CLICKWRAP_TEXT = (
    "Estás ingresando al gemelo digital de BIOCORE AI. Te recordamos que la información, métricas y retroalimentación "
    "clínica generada en esta sesión no constituyen un diagnóstico médico. Las variaciones en las señales (como caídas "
    "de presión en escenarios de sepsis o alteraciones de ritmo) son simulaciones matemáticas —rotuladas como tales; "
    "algunas, como la presión arterial en la sepsis, están en revisión clínica— o registros adquiridos con fines de "
    "práctica en un entorno seguro. Si estás midiendo tus propias señales en tiempo real y notas alguna anomalía que te "
    "preocupe, acude a un profesional de la salud cualificado.")
CLICKWRAP_CHECKBOX = ("Comprendo que BIOCORE AI es una herramienta de simulación educativa y no un instrumento "
                      "médico.")
CLICKWRAP_BUTTON = "Ingresar al laboratorio"
CLICKWRAP_HINT = "Marca la casilla para ingresar."
# Páginas que cargan un caso clínico: el aviso se vuelve a pedir cada vez que se entra a una de ellas.
CASE_PAGES = ("caso-ciego", "casos-simulador", "detective", "caso-guiado")

# ── Precauciones del manual de usuario, en los tutoriales de hardware ───────────────────────────────────────────────
SAFETY_TITLE = "Precauciones y seguridad eléctrica (manual de usuario de BIOCORE AI)"
SAFETY: Dict[str, str] = {
    "PS1": ("**Seguridad eléctrica (ECG y EMG):** cuando utilice los sensores con electrodos conectados al cuerpo "
            "humano, la computadora portátil a la que está conectado BIOCORE AI DEBE OPERAR ÚNICAMENTE CON BATERÍA. "
            "Desconecte el cargador de la toma de corriente de la pared durante las mediciones para evitar riesgos de "
            "choque eléctrico por corrientes de fuga e interferencia electromagnética (ruido de 60 Hz)."),
    "PS2": ("**Higiene y aplicación:** utilice los electrodos desechables (ECG) y de broche (EMG) únicamente sobre piel "
            "intacta, limpia y seca. No coloque electrodos sobre heridas, irritaciones o mucosas. La sonda de "
            "temperatura es exclusivamente de uso axilar externo; NUNCA DEBE INTRODUCIRSE EN LA BOCA ni en ninguna otra "
            "cavidad corporal."),
    "PS3": ("**Límites operativos:** los sensores PPG (pulso) requieren que el usuario coloque la yema del dedo "
            "suavemente, sin presionar en exceso, para evitar bloquear el flujo sanguíneo y alterar la lectura."),
    "PS4": ("**Limitación de EEG:** el módulo BIOCORE AI no adquiere señales cerebrales directamente. Para prácticas "
            "neurológicas, el sistema debe conectarse a un equipo externo compatible (ej. OpenBCI Cyton) siguiendo los "
            "manuales de dicho fabricante."),
}
SAFETY_BY_KIND: Dict[str, Sequence[str]] = {
    "ecg": ("PS1", "PS2"), "emg": ("PS1", "PS2"), "ppg": ("PS3",), "temp": ("PS2",), "eeg": ("PS4",),
}

# Interruptor de la casilla obligatoria: lo apaga `tests/conftest.py` para las pruebas que recorren las páginas (las
# pruebas del aviso, en `tests/test_legal.py`, lo vuelven a encender). En la app siempre está encendido.
GATE_ENABLED = True
_SESSION_OK = "legal_clickwrap_session_ok"
_CASE_OK = "legal_clickwrap_case_ok"


# ── Streamlit ───────────────────────────────────────────────────────────────────────────────────────────────────────
def clickwrap_pending(url_path: str) -> bool:
    """¿Hay que mostrar el aviso antes de esta página? Al iniciar la sesión, y cada vez que se entra a una página que
    carga un caso clínico (al salir de ella, el aviso vuelve a pedirse la próxima vez)."""
    import streamlit as st

    if not GATE_ENABLED:
        return False
    if url_path not in CASE_PAGES:
        st.session_state[_CASE_OK] = None
    if not st.session_state.get(_SESSION_OK):
        return True
    return url_path in CASE_PAGES and st.session_state.get(_CASE_OK) != url_path


def render_clickwrap(url_path: str) -> None:
    import streamlit as st

    st.markdown(f"### {CLICKWRAP_TITLE}")
    with st.container(border=True):
        st.markdown(CLICKWRAP_TEXT)
    accepted = st.checkbox(CLICKWRAP_CHECKBOX, value=False, key=f"legal_clickwrap_check_{url_path}")
    if st.button(CLICKWRAP_BUTTON, type="primary", disabled=not accepted, key=f"legal_clickwrap_enter_{url_path}"):
        st.session_state[_SESSION_OK] = True
        if url_path in CASE_PAGES:
            st.session_state[_CASE_OK] = url_path
        st.rerun()
    if not accepted:
        st.caption(CLICKWRAP_HINT)


def _render_sections(title: str, sections, preamble: Optional[str] = None) -> None:
    import streamlit as st

    st.caption(f"Versión del {VERSION}. {IN_REVIEW_NOTICE}")
    if preamble:
        st.markdown(fill(preamble))
    for _id, heading, body in sections:
        st.markdown(f"**{heading}**")
        st.markdown(fill(body))


def render_terms_page() -> None:
    from app.utils.design_system import render_module_header

    render_module_header(TERMS_TITLE, icon="📜")
    _render_sections(TERMS_TITLE, TERMS)


def render_privacy_page() -> None:
    from app.utils.design_system import render_module_header

    render_module_header(PRIVACY_TITLE, icon="🔒")
    _render_sections(PRIVACY_TITLE, PRIVACY, PRIVACY_PREAMBLE)


def render_legal_footer() -> None:
    """Pie de cada página: el aviso de uso educativo y los enlaces a Términos y Aviso de privacidad (Ajustes)."""
    import streamlit as st

    from app.utils import navigation as nav

    st.divider()
    st.caption(FOOTER_NOTICE)
    cols = st.columns(2)
    with cols[0]:
        nav.link("terminos", "Términos y condiciones", icon="📜")
    with cols[1]:
        nav.link("privacidad", "Aviso de privacidad", icon="🔒")


def render_safety_precautions(kind: str) -> None:
    """Las precauciones del manual que tocan a este sensor, dentro de la sección «Seguridad» de su tutorial."""
    import streamlit as st

    st.markdown(f"**{SAFETY_TITLE}**")
    for key in SAFETY_BY_KIND[kind]:
        st.markdown(f"- {SAFETY[key]}")
