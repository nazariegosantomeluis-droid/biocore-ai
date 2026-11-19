"""Idioma de la interfaz: español (predeterminado) e inglés (2026-11-18).

`t(texto_es)` devuelve el texto en el idioma elegido. La clave es el propio texto en español: si no hay traducción,
se muestra el español; nunca se traduce al vuelo ni se inventa. El idioma vive en `st.session_state[LANG_KEY]` y, para
compartir un enlace en inglés, en el parámetro `?lang=en` de la URL.

Art. I: el contenido médico y legal firmado (teoría, preguntas, casos, términos y aviso de privacidad) se firmó en
español y se muestra en español: una versión en inglés necesita su propia revisión y firma. En inglés, cada página
cuya interfaz todavía no está traducida lo dice arriba (`render_page_notice`). El aviso de entrada se muestra con una
traducción de cortesía y el texto firmado en español, que es el que aplica.
"""

from __future__ import annotations

LANG_KEY = "biocore_lang"
DEFAULT_LANG = "es"
LANGUAGES = {"es": "Español", "en": "English"}
SELECTOR_LABEL = "Idioma · Language"

# Páginas con la interfaz traducida (su contenido firmado sigue en español).
TRANSLATED_PAGES = frozenset({"inicio"})
LEGAL_PAGES = frozenset({"terminos", "privacidad"})

UNTRANSLATED_NOTICE = ("This page is not translated yet: it is shown in Spanish. Medical content stays in Spanish, the "
                       "language in which it was signed, until an English version is reviewed.")
LEGAL_NOTICE = ("The legal texts are shown in Spanish, the language in which they were signed and the one that "
                "applies.")
SIGNED_CONTENT_NOTE = "Signed content: shown in Spanish, the language in which it was signed."
COURTESY_NOTE = "Courtesy translation. The signed Spanish text below is the one that applies."

# Traducciones al inglés de la interfaz. Solo rótulos, botones y avisos: ningún texto médico firmado.
EN = {
    # Menú: secciones y páginas
    "Inicio": "Home", "Aprender": "Learn", "Practicar": "Practice", "Explorar": "Explore", "Ajustes": "Settings",
    # T5 (2026-11-18): los cinco destinos y el «continúa en» del Hoy
    "Hoy": "Today", "Paciente": "Patient", "Biblioteca": "Library", "Continúa en": "Continue at",
    "Ir a la Biblioteca": "Go to the Library", "Ir a la Ruta": "Go to the Path", "Ir a Paciente": "Go to Patient",
    "Empezar la Ruta": "Start the Path", "estación": "station", "Tu paciente": "Your patient", "Observa": "Observe",
    "Mide": "Measure", "Practica": "Practice", "Altera": "Alter", "Cierre": "Closing",
    "Temas": "Topics", "Teoría (Academia)": "Theory (Academy)",
    "Referencias de los laboratorios": "Lab references", "ECG en 3D": "3D ECG", "Bibliografía": "Bibliography",
    "Pregunta a BIOCORE": "Ask BIOCORE", "Quiz de la Academia": "Academy quiz", "Caso ciego": "Blind case",
    "Desafío ECG de 12 derivaciones": "12-lead ECG challenge", "Caso guiado de ECG": "Guided ECG case",
    "Cuestionarios de los laboratorios": "Lab quizzes", "Casos clínicos del simulador": "Simulator clinical cases",
    "¿Qué pasa si…?": "What if…?", "Detective fisiológico": "Physiology detective",
    "Tu aprendizaje en esta sesión": "Your learning this session", "Gemelo digital": "Digital twin",
    "Fusión de sensores": "Sensor fusion", "Respiración": "Breathing", "Variabilidad cardiaca": "Heart rate variability",
    "Biomarcadores": "Biomarkers", "Calculadoras clínicas": "Clinical calculators", "Pacientes": "Patients",
    "Comparar pacientes": "Compare patients", "Taller 3D": "3D workshop",
    "Términos y condiciones": "Terms and conditions", "Aviso de privacidad": "Privacy notice",
    "Biocore · Laboratorio digital de fisiología": "Biocore · Digital physiology lab",
    # Menú lateral: estado de la IA
    "🔑 IA activa con Gemini, nivel gratuito (solo datos simulados o públicos; solo en esta sesión)":
        "🔑 AI on with Gemini, free tier (simulated or public data only; this session only)",
    "🔑 IA activa con tu clave (solo en esta sesión)": "🔑 AI on with your key (this session only)",
    "🔑 IA activa (clave del entorno del servidor)": "🔑 AI on (server environment key)",
    "🔑 IA apagada": "🔑 AI off",
    "Ir a Ajustes para poner tu clave": "Go to Settings to add your key",
    # Inicio
    "Equivócate aquí.": "Get it wrong here.",
    "Laboratorio digital de fisiología.": "Digital physiology lab.",
    "El gemelo digital es una simulación y se declara como tal.":
        "The digital twin is a simulation and is labeled as one.",
    "Registro real: MIT-BIH 100, MLII · PhysioNet, ODC-By 1.0": "Real recording: MIT-BIH 100, MLII · PhysioNet, ODC-By 1.0",
    "Tira de ECG: registro real MIT-BIH 100": "ECG strip: real recording MIT-BIH 100",
    "Sin paciente activo": "No active patient", "Sin paciente activo.": "No active patient.",
    "Monitoreo del paciente activo": "Active patient monitoring",
    "Sin paciente activo: abre el gemelo digital para crear el paciente que comparten las páginas.":
        "No active patient: open the digital twin to create the patient that all pages share.",
    "Últimos valores guardados en el UPS de esta sesión, cada uno con su procedencia; no es una señal en vivo.":
        "Latest values saved in the UPS for this session, each with its provenance; it is not a live signal.",
    "Monitoreo en vivo: laboratorio de ECG completo": "Live monitoring: full ECG lab",
    "Gemelo digital · simulación": "Digital twin · simulation",
    "El UPS no tiene un dominio para este sistema; se estudia con la variabilidad cardiaca.":
        "The UPS has no domain for this system; it is studied through heart rate variability.",
    "El paciente activo todavía no tiene un estado guardado en el UPS.":
        "The active patient has no state saved in the UPS yet.",
    "El UPS del paciente activo no tiene valores de este sistema.":
        "The active patient's UPS has no values for this system.",
    "Abrir el gemelo digital": "Open the digital twin", "Ruta": "Path", "Órganos": "Organs",
    "Registro real": "Real recording",
    "Sin registro real en el repositorio para este sistema.": "No real recording in the repository for this system.",
    "Este sistema todavía no tiene un tema firmado; está en sus laboratorios.":
        "This system has no signed topic yet; it is covered in its labs.",
    "Concepto": "Concept", "Ficha de estudio": "Study card", "Pista": "Hint", "Ver respuesta": "Show answer",
    "De la teoría firmada": "From the signed theory", "Fuente": "Source", "Abrir el tema": "Open the topic",
    "Ir a Teoría": "Go to Theory", "Avance de esta sesión": "Progress this session",
    "Todavía no hay respuestas registradas en esta sesión.": "No answers recorded in this session yet.",
    "respuestas correctas en esta sesión": "correct answers this session", "de": "of",
    "Ir a Practicar": "Go to Practice", "Expediente": "Record", "Paciente": "Patient",
    "estados guardados en el UPS": "states saved in the UPS", "Ir al gemelo digital": "Go to the digital twin",
    "La IA (narrador y explicaciones) es opcional: sin clave, todo lo demás funciona igual.":
        "AI (narrator and explanations) is optional: without a key, everything else works the same.",
    "Ajustes: clave de IA": "Settings: AI key", "tiempo (s)": "time (s)",
    # Órganos y ruta
    "Corazón": "Heart", "Cerebro": "Brain", "Músculo": "Muscle", "Sistema autónomo": "Autonomic system",
    "Bandas del EEG": "EEG bands", "Desafío de 12 derivaciones": "12-lead challenge", "El ECG en papel": "ECG on paper",
    "Frecuencia cardiaca": "Heart rate", "Laboratorio de ECG": "ECG lab", "Laboratorio de EEG": "EEG lab",
    "Laboratorio de EMG": "EMG lab", "Laboratorio respiratorio": "Breathing lab", "Ondas e intervalos": "Waves and intervals",
    "Patrones respiratorios": "Breathing patterns",
    # Valores del UPS, unidades y sellos de procedencia
    "FC": "HR", "FR": "RR", "lpm": "bpm", "Frecuencia respiratoria": "Respiratory rate",
    "Puntos NEWS2 del pulso": "NEWS2 pulse points", "Puntos NEWS2 de la FR": "NEWS2 respiratory rate points",
    "Puntos NEWS2 de la SpO₂ (escala 1)": "NEWS2 SpO₂ points (scale 1)", "Razón FC:FR": "HR:RR ratio",
    "Presión sistólica": "Systolic pressure", "Presión diastólica": "Diastolic pressure", "PAM": "MAP",
    "Medido": "Measured", "Simulado": "Simulated", "Calculado por modelo": "Calculated by model",
    "Referencia citada": "Cited reference", "Arrastre temporal": "Carried over in time",
    "hace {n} s": "{n} s ago", "hace {n} min": "{n} min ago", "hace {n} h": "{n} h ago",
    "horizonte {h}": "horizon {h}", "ahora": "now", "7 días": "7 days",
    "No disponible": "Not available",
    # Aviso de entrada y pie de página
    "Aviso clínico y educativo": "Clinical and educational notice",
    "Comprendo que BIOCORE AI es una herramienta de simulación educativa y no un instrumento médico.":
        "I understand that BIOCORE AI is an educational simulation tool and not a medical instrument.",
    "Ingresar al laboratorio": "Enter the lab", "Marca la casilla para ingresar.": "Check the box to enter.",
    "Texto firmado (español)": "Signed text (Spanish)",
    "BIOCORE AI NO ES UN DISPOSITIVO MÉDICO: uso exclusivamente educativo.":
        "BIOCORE AI IS NOT A MEDICAL DEVICE: for educational use only.",
}

# Traducción de cortesía del aviso de entrada (el texto firmado es `legal.CLICKWRAP_TEXT`, en español).
CLICKWRAP_TEXT_EN = (
    "You are entering the BIOCORE AI digital twin. The information, metrics and clinical feedback generated in this "
    "session are not a medical diagnosis. Changes in the signals (such as pressure drops in sepsis scenarios or rhythm "
    "changes) are mathematical simulations, labeled as such (some, like blood pressure in sepsis, are under clinical "
    "review), or recordings acquired for practice in a safe environment. If you are measuring your own signals in real "
    "time and notice an anomaly that worries you, see a qualified health professional.")


def get_lang() -> str:
    """Idioma de esta sesión; fuera de una sesión de Streamlit, el predeterminado."""
    try:
        import streamlit as st

        lang = st.session_state.get(LANG_KEY)
    except Exception:          # sin sesión (p. ej., una prueba que llama una función suelta)
        return DEFAULT_LANG
    return lang if lang in LANGUAGES else DEFAULT_LANG


def is_english() -> bool:
    return get_lang() == "en"


def t(text: str) -> str:
    """El texto en el idioma de la sesión; sin traducción, el original en español."""
    if not text or not is_english():
        return text
    return EN.get(text, text)


def init_language() -> None:
    """En la primera carga toma `?lang=` de la URL (si es un idioma válido); después manda el selector."""
    import streamlit as st

    if LANG_KEY not in st.session_state:
        requested = st.query_params.get("lang")
        st.session_state[LANG_KEY] = requested if requested in LANGUAGES else DEFAULT_LANG


def _sync_query_param() -> None:
    import streamlit as st

    if st.session_state.get(LANG_KEY) == DEFAULT_LANG:
        if "lang" in st.query_params:
            del st.query_params["lang"]
    else:
        st.query_params["lang"] = st.session_state[LANG_KEY]


def render_language_selector() -> None:
    """Selector del menú lateral. El rótulo es bilingüe y fijo: así lo encuentra quien no lee el idioma activo."""
    import streamlit as st

    with st.sidebar:
        st.radio(SELECTOR_LABEL, list(LANGUAGES), key=LANG_KEY, format_func=LANGUAGES.get, horizontal=True,
                 on_change=_sync_query_param)


def render_page_notice(url_path: str) -> None:
    """En inglés, avisa arriba de cada página que sigue en español y por qué."""
    if not is_english():
        return
    import streamlit as st

    if url_path in LEGAL_PAGES:
        st.info(LEGAL_NOTICE)
    elif url_path not in TRANSLATED_PAGES:
        st.info(UNTRANSLATED_NOTICE)
