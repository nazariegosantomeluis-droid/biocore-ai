"""BIOCORE AI — Complete Integrated Biomedical Intelligence Operating System.

Full integration of all modules with complete features, hardware support, and universal hands-free.
"""

import io
import os
import sys

# Ensure stdout/stderr can print emoji/Unicode on non-UTF8 consoles (e.g. Windows
# cp1252) — several fallback branches below log with emoji via print().
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import time
import tempfile
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List, Tuple, Any

import numpy as np
import streamlit as st
from scipy.signal import welch

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app.supermodules import (
    estimate_ecg_heart_rate,
    generate_demo_bp_signal,
    generate_demo_ppg_signal,
    generate_demo_respiration_signal,
    generate_demo_spo2_signal,
    generate_demo_temperature_signal,
    safe_import_plotly,
    safe_import_ecg_modules,
    safe_import_multisensor,
    safe_import_src_modules,
    validate_signal,
    plot_signal_matplotlib,
    display_warning_message,
    display_error_message,
    display_info_message,
    render_metric_explained,
    render_view_selector,
    render_scientific_discovery_layer,
    render_discovery_lab,
)
from app.engines import DigitalTwinOrganism
from src.signals.ecg.dynamic_ecg_generator import DynamicECGGenerator
from app.utils.design_system import (
    render_module_header, render_section_header, render_error_state, render_empty_state, BADGES,
)
from app.utils.patient_session import (
    get_active_patient_display_name,
    get_active_patient_id,
    get_active_session_factory,
    rename_active_patient,
)
# Fusión de persistencia, Paso 2 (2026-07-15): app.clinical_db se retiró del
# flujo vivo -- Patient Pipeline ahora persiste en el UPS real. El archivo
# clinical_states.db se conserva sin borrar (ver CHANGELOG.md).
from domain.physiology.state import (
    ImpressionCategory,
    EventSeverity,
    Provenance,
    create_clinical_impression,
    from_digital_twin_organism,
    get_clinical_impressions_for_patient,
    get_clinical_impressions_for_snapshot,
    get_latest_snapshot_id,
    get_latest_state,
    save_state,
)

# --- IMPORTACIÓN SEGURA DE BIOMARCADORES ---
# Auditoría 2026-07-03: el import apuntaba a app.biomarkers (no existe en disco);
# BiocoreEngine siempre vivió en app/supermodules/biomarkers.py. Bug de una línea —
# el motor (7 índices por fórmula determinista) y su UI ya calzaban perfectamente
# con esta clase, solo el import estaba roto.
try:
    from app.supermodules.biomarkers import BiocoreEngine
    BIOMARKERS_AVAILABLE = True
except Exception as e:
    print(f"⚠️ Biomarkers Engine import failed: {e}")
    BIOMARKERS_AVAILABLE = False


try:
    from app.reporting import export_lab_report
    import app.reporting as reporting
except Exception as e:
    print(f"⚠️ Reporting module import failed: {e}")
    def export_lab_report(*args, **kwargs):
        return None
    reporting = None

# Fase 1.3: app/biomedical_tutor.py (diccionario de keywords) y
# app/ai_copilot.py (JARVIS, nunca conectado a la UI) fueron eliminados y
# refundidos en domain/physiology/narrator/. Consolidación, Tanda 3
# (2026-07-13): el AI Hub que exponía esa misma función por una segunda
# puerta (render_jarvis_copilot_page(), sin lógica propia) también se
# eliminó — el narrador vive en un único lugar: el panel "Narrador clínico"
# dentro de Digital Twin OS (app/supermodules/twin_shell/pages.py).

# 2026-07-03: Hands-Off Mode, control por gestos (cámara), comandos de voz y
# "atajos de teclado" (nunca tuvieron implementación real, solo el label en
# el sidebar) fueron eliminados a pedido del usuario — ver CHANGELOG.md.
# app/hands_off_mode.py y gesture_controller.py se borraron del repo.

# NOTA (2026-07-03): la vieja render_eeg_page() inline importaba
# 'biomedical.eeg' (módulo que no existe en el repo) para generar EEG
# demo/CSV. Se eliminó junto con esa función — el Hub ahora delega a
# app/supermodules/eeg_neuro_lab/pages.py, que importa correctamente de
# src/signals/eeg y sí incluye visualización real de bandas de potencia.

# NOTA (2026-07-03): antes se intentaba `importlib.import_module('biomedical.emg')`
# para EMGStreamer/preprocess_emg/etc. — ese módulo nunca existió en el repo (el
# try siempre fallaba), así que 'Live Hardware' en render_emg_page() siempre caía
# en modo demo silenciosamente, sin avisar. El hardware real que sí existe y que
# usa app/pages_legacy/9_🦾_EMG_Muscle_Lab.py es hardware.emg_stream.EMGStreamer +
# hardware.sensor_manager.SensorManager.
#
# Capa 5A dominio muscular, Tanda 1 (lado señal, 2026-09-09): el análisis EMG
# (activación + frecuencia mediana + índice de fatiga) vive ahora en un
# `EmgAnalyzer` limpio en `src/signals/emg/`, misma forma que `EegAnalyzer`.
# Antes había 3 funciones sueltas aquí, y un `preprocess_emg` stub NO-OP
# (`filtered = signal`) que ECLIPSABA el bandpass real de
# `src/signals/emg/preprocessing.py` — la activación y la MDF se calculaban
# sobre señal cruda. Stub muerto; el analizador filtra internamente.
try:
    from hardware.sensor_manager import SensorManager
except Exception:
    SensorManager = None

try:
    from hardware.emg_stream import EMGStreamer
except Exception:
    EMGStreamer = None

from src.signals.emg import EmgAnalyzer

# Safe Plotly import
PLOTLY_GO, _, PLOTLY_OK = safe_import_plotly()

# Configure page
st.set_page_config(
    # Fase 1 (idioma, 2026-08-30): título de la pestaña del navegador --
    # única cadena de este bloque que no es una clave reservada de Streamlit.
    page_title="BIOCORE AI — Plataforma Integrada",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        # "Get Help"/"Report a bug"/"About" son claves reservadas de la API de
        # Streamlit (st.set_page_config) -- Streamlit solo reconoce estos 3
        # nombres exactos para el menú hamburguesa, no son texto de UI nuestro.
        # Traducir la clave rompería el menú (Streamlit lo ignoraría). El
        # VALOR de "About" sí es nuestro y se traduce.
        "Get Help": "https://github.com",
        "Report a bug": "https://github.com/issues",
        "About": "BIOCORE AI — Sistema Operativo de Inteligencia Biomédica",
    },
)

# --- AÑADIDO: Biomarkers Lab AL CLINICAL HUB ---
HUBS = {
    "Digital Twin OS": [
        "🧬 Digital Twin OS",
    ],
    "Learning Hub": [
        # Fase 4 (2026-08-30, ver CHANGELOG.md): "🎓 Education" y "📚 Guides"
        # retirados -- Education era 90% redirección honesta a esta misma
        # Academia + fachadas (4 tarjetas de curso "en desarrollo", un
        # selectbox de 3 diagnósticos fijos sin datos reales, 4 secciones
        # de una sola frase describiendo capacidades que nunca se
        # construyeron). Guides describía una navegación ya obsoleta
        # (listaba 3 de los 8+ módulos reales de Clinical Hub) y una
        # sección "Roles" sin ningún feature real detrás. Academia Clinica
        # es el único contenido educativo real (quiz de 16 preguntas con
        # feedback IA, casos clínicos ciegos, tabla de 12 derivaciones,
        # tutor IA) -- el Learning Hub ahora lleva directo a él, sin
        # cáscaras de por medio.
        "🏫 Academia Clinica",
    ],
    "Clinical Hub": [
        # Bug 3 (2026-07-12): algunos módulos tenían un segundo nombre "interno" sin
        # emoji que aparecía como entrada de menú duplicada. El ruteo en
        # render_page_content() empareja por substring, así que el nombre con
        # emoji por sí solo sigue enrutando correctamente. Ver CHANGELOG.md.
        #
        # Fusión ECG Monitor + ECG-12 (2026-07-14): "📊 ECG Monitor" y "📋
        # ECG-12-Derivaciones" eran dos entradas separadas para dos flujos
        # totalmente independientes (inventario: cero colisión de widgets ni
        # session_state). Se unificaron en una sola entrada "🫀 ECG Lab" con
        # dos pestañas (Monitoreo / 12 Derivaciones) — reorganización de
        # navegación, ninguno de los dos flujos se reescribió.
        "🫀 ECG Lab",
        "🔗 Multisensor Fusion Lab",
        "💨 Respiratory Lab",
        "🧠 EEG Neuro Lab",
        "🦾 EMG Muscle Lab",
        "📈 HRV Analysis",
        "🧬 Biomarkers Lab",
        # Fusión de navegación, Research Hub (2026-07-14): Patient Pipeline
        # reubicado aquí — único contenido real de Research Hub, que se
        # eliminó del menú (su otra entrada, AI Analysis, era un cartel sin
        # lógica; ver render_ai_analysis_page(), eliminada). Persistencia
        # (app.clinical_db) sin tocar — solo se movió la entrada de menú.
        "👥 Patient Pipeline",
    ],
}
PAGE_TABS = [page for pages in HUBS.values() for page in pages]

DEFAULT_HUB = "Digital Twin OS"


def inject_biocore_css() -> None:
    st.markdown(
        """
        <style>
            :root { color-scheme: dark; font-family: 'Inter', 'Segoe UI', sans-serif; }
            html, body, [data-testid='stAppViewContainer'] {
                background: radial-gradient(circle at top left, rgba(11, 196, 221, 0.18), transparent 26%),
                            linear-gradient(180deg, #05101f 0%, #040812 100%);
                color: #eef7ff;
            }
            .biocore-card { background: rgba(6, 16, 32, 0.90); border: 1px solid rgba(12, 185, 221, 0.18);
                            border-radius: 26px; padding: 20px; margin-bottom: 18px; }
            .biocore-panel { background: rgba(5, 14, 30, 0.95); border: 1px solid rgba(12, 185, 221, 0.18);
                            border-radius: 28px; box-shadow: 0 24px 58px rgba(0, 0, 0, 0.30); padding: 26px 28px; margin-bottom: 22px; }
            .status-pill { display: inline-flex; align-items: center; gap: 8px; padding: 10px 14px;
                          border-radius: 22px; border: 1px solid rgba(255,255,255,0.14); background: rgba(255,255,255,0.06);
                          color: #d5e8ff; font-size: 0.92rem; margin-bottom: 8px; }
            .pulse-dot { width: 12px; height: 12px; border-radius: 999px; background: #39ffbe;
                        box-shadow: 0 0 12px rgba(57,255,190,0.45); animation: pulse 1.6s ease-in-out infinite; }
            @keyframes pulse { 0% { transform: scale(0.9); opacity: 0.9; } 50% { transform: scale(1.15); opacity: 1; }
                              100% { transform: scale(0.9); opacity: 0.9; } }
        </style>
        """,
        unsafe_allow_html=True,
    )

def init_state() -> None:
    if 'selected_hub' not in st.session_state:
        st.session_state.selected_hub = DEFAULT_HUB
    if 'selected_page' not in st.session_state:
        st.session_state.selected_page = HUBS[st.session_state.selected_hub][0]
    if 'report_requested' not in st.session_state:
        st.session_state.report_requested = False
    if 'page_tabs' not in st.session_state:
        st.session_state.page_tabs = PAGE_TABS
    if 'emg_streamer' not in st.session_state:
        st.session_state.emg_streamer = None
    # 'learning_progress' (Cardio-Fisiología 58%, Neurofisiología 42%, etc.) se quitó
    # 2026-07-14 -- eran números fijos idénticos para cualquier usuario/sesión, sin
    # avance real detrás; el botón "Avanzar en aprendizaje" solo les sumaba 5 por
    # clic (Art. I de la Constitución). Ver CHANGELOG.md ("Capa de teoría").
    # 'mission_goal' se quitó en Fase 4 (2026-08-30) junto con render_guides_page()
    # -- su único lector era esa misma página (confirmado por grep); el botón
    # "Abrir onboarding rápido" no activaba ningún flujo real, solo reescribía
    # esta variable para volver a mostrarla en el mismo lugar.

# Fusión de persistencia, Paso 2 (2026-07-15): la inicialización de
# app.clinical_db (tabla patient_states) se quitó -- nada en el flujo vivo
# la usa ya (ver render_patient_pipeline_page()). El archivo
# clinical_states.db se conserva sin borrar, solo deja de inicializarse.

def render_metric_explained(title: str, value: Any, unit: str = '', meaning: Optional[str] = None,
                            importance: Optional[str] = None, affects: Optional[str] = None,
                            relations: Optional[str] = None, consequences: Optional[str] = None) -> None:
    try:
        display_value = f"{value} {unit}" if unit else f"{value}"
    except Exception:
        display_value = str(value)

    st.markdown(f"**{title}** — {display_value}")
    with st.expander(f"¿Qué significa {title}?", expanded=False):
        st.markdown(f"- **¿Qué significa?** {meaning or 'Valor clínico cuantitativo que resume un aspecto fisiológico.'}")
        st.markdown(f"- **¿Por qué importa?** {importance or 'Permite priorizar decisiones clínicas y educativas.'}")
        st.markdown(f"- **¿Qué la afecta?** {affects or 'Fármacos, estado hemodinámico, respiración, ejercicio y artefactos técnicos.'}")
        st.markdown(f"- **¿Cómo se relaciona con otros sistemas?** {relations or 'Interacciona con ventilación, oxigenación y estado neurológico.'}")
        st.markdown(f"- **¿Qué pasaría si cambia?** {consequences or 'Un cambio significativo sugiere intervención, más pruebas o monitorización intensiva.'}")


def render_discovery_lab(name: str, signals: Dict[str, np.ndarray]):
    with st.expander(f"🔬 Discovery Lab — {name}", expanded=False):
        st.write('Interactividad: correlaciones, sensibilidad y exploración de parámetros.')
        if len(signals) < 2:
            st.info('Se requieren al menos 2 señales para explorar correlaciones.')
            return
        if st.button(f'Run discovery for {name}'):
            keys = list(signals.keys())
            mat = np.zeros((len(keys), len(keys)))
            for i in range(len(keys)):
                for j in range(len(keys)):
                    a = signals[keys[i]]
                    b = signals[keys[j]]
                    mn = min(len(a), len(b))
                    if mn > 1:
                        mat[i, j] = float(np.corrcoef(a[:mn], b[:mn])[0, 1])
                    else:
                        mat[i, j] = 0.0
            corr_dict = {k: {kk: float(mat[i, j]) for j, kk in enumerate(keys)} for i, k in enumerate(keys)}
            st.json(corr_dict)
            strongest = np.unravel_index(np.argmax(np.abs(mat - np.eye(len(keys))*2)), mat.shape)
            k1, k2 = keys[strongest[0]], keys[strongest[1]]
            st.write(f'Interpretación rápida: mayor correlación observada entre **{k1}** y **{k2}** ({mat[strongest]:.2f}).')


def render_findings_narrator(lab_name: str, findings: List[Tuple[str, str, str]]) -> None:
    """Narrador clínico real (Anthropic, streaming) para hallazgos calculados en
    laboratorios que no persisten en el UPS (EMG/HRV/Multisensor/ECG Monitor no
    tienen dominio en el Unified Physiological State — solo cardiovascular y
    respiratorio están modelados). Ver domain/physiology/narrator/findings.py.

    Mismo patrón que el narrador del Digital Twin OS (twin_shell/pages.py):
    llamada real a la API, sin narración simulada de respaldo, cada afirmación
    anclada a una métrica exacta del contexto — pero sin comparación temporal
    (estas señales ad-hoc no tienen historial persistido).

    `findings`: lista de tuplas (nombre_metrica, valor, significado)."""
    from domain.physiology.narrator import (
        Finding,
        FindingsContext,
        NarratorNotConfiguredError,
        is_configured,
        stream_findings_narration,
    )

    if not is_configured():
        st.warning(
            "`ANTHROPIC_API_KEY` no está configurada. Este narrador llama a la API real de "
            "Anthropic con streaming — no existe una narración simulada de respaldo."
        )
        return

    st.caption("Interpreta las métricas ya calculadas arriba — no genera datos nuevos.")
    if st.button("🗣️ Explicar estos hallazgos", key=f"findings_narrator_{lab_name}"):
        context = FindingsContext(lab_name=lab_name, findings=[Finding(*f) for f in findings])
        try:
            st.write_stream(stream_findings_narration(context))
        except NarratorNotConfiguredError as exc:
            render_error_state(str(exc))
        except Exception as exc:  # llamada real a la API — puede fallar por red/cuota/etc.
            # Fase 2.3 Tanda 3 (2026-08-29): compartido por EMG/ECG Monitor/
            # Multisensor/HRV (pestaña "IA") -- una sola migración cubre los
            # 4. Antes exponía `{exc}` crudo (puede incluir detalle interno
            # de la respuesta HTTP de la API).
            render_error_state(
                "No se pudo completar la narración -- la llamada a la API de Anthropic falló "
                "(red o cuota). Intenta de nuevo en unos segundos.",
                exception=exc,
            )


def render_view_selector(view_id: str = None, views: Optional[List[str]] = None) -> str:
    import inspect
    if view_id is None:
        caller_frame = inspect.currentframe().f_back
        view_id = caller_frame.f_code.co_name
    options = views or ['Clínica', 'Educativa', 'Investigación', 'IA', 'Simulación', 'Gemelo Digital']
    return st.radio(
        'Capa de Exploración Cognitiva',
        options,
        horizontal=True,
        key=f"view_selector_{view_id}"
    )

def render_twin_shell_page() -> None:
    from app.supermodules.twin_shell.pages import run as run_twin_shell
    run_twin_shell()


def render_academia_page() -> None:
    from app.supermodules.academia.pages import run as run_academia
    run_academia()


def render_ecg_12_page() -> None:
    """Fase de auditoría (2026-07-03): `render_ecg_12_page` se llamaba desde
    el enrutador de abajo pero nunca existía — NameError en vivo. El
    supermódulo real (app/supermodules/ecg_12/pages.py -> pages_legacy/
    6_📋_ECG-12-Derivaciones.py) siempre estuvo completo, solo desconectado.

    Fusión ECG Monitor + ECG-12 (2026-07-14): ya no es una entrada de menú
    propia — el enrutador la reemplazó por `render_ecg_lab_page()`, que la
    llama desde la pestaña "12 Derivaciones". La función en sí no se tocó."""
    from app.supermodules.ecg_12.pages import run as run_ecg_12
    run_ecg_12()


def render_ecg_lab_page() -> None:
    """Fusión ECG Monitor + ECG-12 (2026-07-14) — "ECG Lab": una sola entrada
    de menú con dos pestañas, cada una invocando su flujo íntegro sin tocar
    su lógica de análisis. Inventario previo (ver CHANGELOG) confirmó
    independencia total entre ambos: cero session_state compartido y cero
    colisión de widgets al catalogar los ~20 de uno contra los ~13 del otro
    por label exacto — excepto dos pares "near-miss" (mismo tema, texto
    casi idéntico) que hoy no chocan solo porque el texto difiere
    ('Frecuencia cardíaca (bpm)' vs 'Frecuencia Cardíaca (bpm)' — difieren
    en una mayúscula; 'QRS (ms)' vs 'Duración QRS (ms)'). Para que esa
    independencia no dependa de que el texto se mantenga distinto por
    casualidad, esos 4 widgets (2 en `render_ecg_monitor_page`, 2 en
    `ecg_12/page_content.py`) recibieron `key=` explícita namespaced por
    pestaña (`ecglab_monitor_*` / `ecglab_12_*`) — un futuro cambio de
    label ya no puede convertirlos en un `StreamlitDuplicateElementId`.
    Ninguna otra key se tocó: `render_view_selector()` (usado por ECG
    Monitor) ya namespacea su key por el nombre de la función llamadora, y
    el resto de los widgets de ambos flujos no compartía label con nada del
    otro lado."""
    render_module_header("ECG Lab", icon="🫀")
    tab_monitoreo, tab_12_derivaciones = st.tabs(["Monitoreo", "12 Derivaciones"])
    with tab_monitoreo:
        render_ecg_monitor_page()
    with tab_12_derivaciones:
        render_ecg_12_page()


def render_eeg_neuro_lab_page() -> None:
    """Fase de auditoría (2026-07-03): reemplaza a la antigua render_eeg_page()
    inline, que dependía de 'biomedical.eeg' (módulo inexistente) y no tenía
    visualización de bandas de potencia. El supermódulo real (pages_legacy/
    8_🧠_EEG-Neuro-Lab.py, vía src/signals/eeg) sí la tiene."""
    from app.supermodules.eeg_neuro_lab.pages import run as run_eeg_neuro_lab
    run_eeg_neuro_lab()


def render_respiratory_lab_page() -> None:
    """Fase de consolidación (2026-07-03): reemplaza a la antigua render_respiratory_page()
    inline (un solo patrón de respiración fijo, RR estimado crudo, sin detección de apnea,
    sin AHI). El supermódulo real (pages_legacy/7_💨_Respiratory-Lab.py, vía
    src/signals/respiration) tiene 7 patrones seleccionables, análisis real de apnea/AHI,
    canales de tórax/abdomen/SpO2, tablas de referencia clínica y un quiz — nada de la
    versión inline era único, confirmado por auditoría antes de reemplazar."""
    from app.supermodules.respiratory_lab.pages import run as run_respiratory_lab
    run_respiratory_lab()


def render_page_content(page: str) -> None:
    # Bloque 1 (2026-08-09, ver CHANGELOG.md): el "else" que llamaba a
    # render_home_page() se retiró -- `page` siempre viene de
    # HUBS[selected_hub][...] (init_state()/el selectbox del sidebar validan
    # contra la lista del hub activo), así que esta función nunca recibía un
    # `page` fuera de las 3 listas de abajo; esa rama era inalcanzable por
    # construcción, no un caso real a cubrir.
    if page in HUBS["Digital Twin OS"]:
        render_twin_shell_page()
    elif page in HUBS["Learning Hub"]:
        # Fase 4 (2026-08-30): Learning Hub = Academia Clinica, único
        # módulo -- ya no hace falta desambiguar por substring.
        render_academia_page()
    elif page in HUBS["Clinical Hub"]:
        if "ECG Lab" in page:
            render_ecg_lab_page()
        elif "Multisensor" in page:
            render_multisensor_page()
        elif "Respiratory" in page:
            render_respiratory_lab_page()
        elif "EEG" in page:
            render_eeg_neuro_lab_page()
        elif "EMG" in page:
            render_emg_page()
        elif "HRV" in page:
            render_hrv_page()
        elif "Biomarkers" in page:
            render_biomarkers_page()  # --- ENRUTAMIENTO A LA NUEVA PÁGINA ---
        elif "Patient Pipeline" in page:
            render_patient_pipeline_page()

def render_metrics_grid(metrics_data: List[Dict]):
    cols = st.columns(len(metrics_data))
    for idx, data in enumerate(metrics_data):
        with cols[idx]:
            render_metric_explained(
                title=data['title'],
                value=data['value'],
                unit=data.get('unit', ''),
                meaning=data.get('meaning'),
                importance=data.get('importance'),
                affects=data.get('affects'),
                relations=data.get('relations'),
                consequences=data.get('consequences')
            )

# ==================== RENDERING FUNCTIONS ====================

# render_top_bar() se retiró (2026-08-11, mini-tanda de limpieza, ver
# CHANGELOG.md): código muerto, huérfana desde que render_home_page() (su
# único llamador) se retiró en el Bloque 1 (2026-08-09). Confirmado por
# grep antes de tocar: cero llamadores vivos fuera de _archive/.


# Mission Control (panel de lanzamiento rápido con 3 botones) se retiró
# (2026-08-05, ver CHANGELOG.md) -- auditoría confirmó que duplicaba al
# 100% el selector de hub de la barra lateral (mismo efecto exacto:
# selected_hub + selected_page + rerun), sin ninguna capacidad propia, y
# se renderizaba sobre CADA página de la app, no solo en el inicio.


# render_home_page() se retiró (2026-08-09, Bloque 1, ver CHANGELOG.md):
# código muerto, inalcanzable por clic (ver comentario en render_page_content())
# desde antes de esta tanda. Su contenido (grid de bienvenida) ya estaba
# desactualizado -- listaba "4. HRV Lab" como un cuarto hub, cuando HRV
# Analysis vive dentro de Clinical Hub, no es un hub propio -- por eso no se
# migró a ningún lado. La home de facto de la app es Digital Twin OS
# (DEFAULT_HUB), seleccionada automáticamente por init_state().


# ==================== NUEVO: PANEL DE BIOMARCADORES ====================

# ==========================================
# Vocabulario de procedencia (2026-08-15, Tanda de honestidad — dictamen del
# validador sobre los 7 Índices fisiológicos BIOCORE, antes "Proprietary
# Scores"). Mismo esquema de badges que `twin_shell/pages.py`
# (PROVENANCE_CLINICAL_BADGE/PROVENANCE_HEURISTIC_BADGE), extendido aquí con
# un tercer nivel: 🔴 para inputs sin fuente de señal real en el repo
# ("fantasmas" — ni siquiera son heurística, son un valor sin instrumento
# detrás). Dos fantasmas (metabolic_efficiency, EDA en Stress Index) se
# retiraron y renormalizaron el 2026-08-15 -- ver CHANGELOG.md. El
# NeuroCardiac Coupling pseudocientífico (suma de potencias + `signal_
# coherence` placeholder) se retiró por completo el 2026-08-19, reemplazado
# por un PLV (Phase-Locking Value) real -- cuarto nivel de badge 🟣 para
# "método citado" (distinto de 🟢, que cita un RANGO, no un algoritmo).
# ==========================================
# Fase 2.3 Tanda 3 (2026-08-29): antes 4 literales duplicados 1:1 con
# `PROVENANCE_*_BADGE` de twin_shell/pages.py -- mismos valores, cero fuente
# compartida (ver design_system.py docstring). Ahora alias de BADGES
# (design_system.py), la fuente única -- ningún valor ni ningún sitio de
# uso más abajo cambia, solo de dónde viene el literal.
BIOMARKER_CLINICAL_BADGE = BADGES.CLINICAL
BIOMARKER_HEURISTIC_BADGE = BADGES.HEURISTIC
BIOMARKER_GHOST_BADGE = BADGES.GHOST
BIOMARKER_METHOD_BADGE = BADGES.METHOD
BIOMARKER_HEURISTIC_LABEL = "ponderación heurística de BIOCORE, no derivada de estudio de cohorte"

# Citas del validador (verbatim, Nivel 1 del dictamen) -- cada una se usa
# solo donde el rango en `biomarkers.py` coincide exactamente con lo citado.
BIOMARKER_SOURCE_HOLM_THETA_ALPHA = (
    "Holm et al., 2009 — \"el candidato más fuerte, índice EEG robusto y "
    "validado para carga mental\"; peso 0.7 al EEG también validado "
    "(latencia ms vs. hemodinámica)"
)
BIOMARKER_SOURCE_RMSSD = "rango fisiológico correcto (dictamen del validador: \"absolutamente correcto\")"
BIOMARKER_SOURCE_ESC_NASPE = "Task Force ESC/NASPE 1996"
BIOMARKER_SOURCE_RESILIENCE_GOLD = "\"marcadores dorados de resiliencia cardiovascular\" (dictamen del validador)"
BIOMARKER_SOURCE_PLV_CRITERION = (
    "Phase-Locking Value entre Theta Frontomedial (4-8Hz, EEG) y banda HF-HRV (0.15-0.40Hz, "
    "tacograma R-R), mínimo 180s de señal simultánea -- criterio del validador, 2026-08-19"
)

_BIOMARKER_HELP = {
    "Stress Index": (
        f"{BIOMARKER_CLINICAL_BADGE} Recortado (2026-08-15) a su único componente real: LF/HF "
        f"0.5-5.0, normalizado directo a 0-100, sin pesos: {BIOMARKER_SOURCE_ESC_NASPE}. Los "
        "componentes EDA (picos SCR, conductancia tónica) se retiraron — no hay módulo de señal "
        "EDA en el repo, eran constantes de preset sin sensor detrás."
    ),
    "Recovery Index": (
        f"{BIOMARKER_CLINICAL_BADGE} RMSSD 10-100ms: {BIOMARKER_SOURCE_RMSSD} · "
        f"{BIOMARKER_HEURISTIC_BADGE} HR de reposo, horas de sueño y pesos (0.40/0.45/0.15): "
        f"{BIOMARKER_HEURISTIC_LABEL}"
    ),
    "Cognitive Load Score": (
        f"{BIOMARKER_CLINICAL_BADGE} Ratio θ/α 0.5-4.0 y su peso (0.7): {BIOMARKER_SOURCE_HOLM_THETA_ALPHA} · "
        f"{BIOMARKER_HEURISTIC_BADGE} componente HR surge (peso 0.3, rango 0-30): {BIOMARKER_HEURISTIC_LABEL}"
    ),
    "Physiological Resilience Score": (
        f"{BIOMARKER_CLINICAL_BADGE} SDNN 15-150ms y HR Recovery Rate 15-50: {BIOMARKER_SOURCE_RESILIENCE_GOLD} · "
        f"{BIOMARKER_HEURISTIC_BADGE} pesos renormalizados (0.5625/0.4375): {BIOMARKER_HEURISTIC_LABEL}. "
        "Eficiencia metabólica (RER, rango fisiológicamente imposible) se retiró (2026-08-15) — "
        "pesos originales 0.45/0.35 renormalizados sobre 0.80."
    ),
    "NeuroCardiac PLV": (
        f"{BIOMARKER_METHOD_BADGE} {BIOMARKER_SOURCE_PLV_CRITERION}. Reemplaza (2026-08-19) al "
        "NeuroCardiac Coupling Score (suma de potencias + `signal_coherence` placeholder), que el "
        "validador calificó de pseudocientífico. Distinto de 🟢: aquí se cita el MÉTODO, no un rango — "
        "casi siempre mostrará 'no disponible', porque requiere ≥180s de señal ECG+EEG en vivo "
        "simultánea que el pipeline hoy no persiste."
    ),
    "Learning Readiness Index": (
        f"{BIOMARKER_HEURISTIC_BADGE} Score compuesto: hereda directamente la disponibilidad del "
        f"PLV neurocardíaco ({BIOMARKER_METHOD_BADGE} arriba) y de Recovery Index — si el PLV no está "
        "disponible, este índice tampoco lo está (no se renormaliza para forzar un número) · "
        f"atenuación beta (1-10) y pesos (0.4/0.4/0.2): {BIOMARKER_HEURISTIC_LABEL}"
    ),
}


def render_biomarkers_page() -> None:
    """Renders the Índices fisiológicos BIOCORE dashboard with Override mode."""
    # Piloto 2 de la Fase 2.3 Tanda 1 (2026-08-24): reemplaza el
    # <h1 style='color:#1f77b4'> a mano (uno de los 52 hex sin fuente única
    # que encontró el recon) por el sistema de diseño compartido.
    render_module_header("Biomarkers Lab", icon="🧬")

    if not BIOMARKERS_AVAILABLE:
        render_error_state("Módulo de Biomarcadores no encontrado -- verifica que 'app/supermodules/biomarkers.py' exista y que numpy/pandas estén instalados.")
        return

    engine = BiocoreEngine()

    st.markdown("""
    Este panel calcula nuestros **índices fisiológicos BIOCORE**. Puedes utilizar la **Base de Datos** para cargar perfiles conocidos,
    o activar el **Ingreso Manual** para introducir los valores extraídos de tu propio hardware señal por señal.
    """)

    st.divider()

    # ==========================================
    # DATOS DEL PACIENTE (movido desde la "Ficha Clínica Global" del
    # sidebar, 2026-08-05 -- este panel era su único consumidor real; ver
    # CHANGELOG.md). Mismas claves de session_state (pac_edad/pac_actividad/
    # pac_cirugias) para no romper otros lectores (p.ej. el checkbox de
    # edad opcional del panel de riesgo en Digital Twin OS).
    # ==========================================
    st.markdown("### 🧍 Datos del paciente")
    col_edad, col_actividad, col_cirugias = st.columns(3)
    st.session_state.pac_edad = col_edad.number_input("Edad", min_value=0, max_value=120, value=25, step=1)
    st.session_state.pac_actividad = col_actividad.selectbox(
        "Actividad Física", ["Sedentario", "Moderado", "Intenso (Atleta)"], index=1
    )
    st.session_state.pac_cirugias = col_cirugias.checkbox("Cirugías previas / Trauma")

    st.divider()

    # ==========================================
    # EL INTERRUPTOR PRINCIPAL
    # ==========================================
    st.markdown("### ⚙️ Origen de Datos Clínicos")
    modo_datos = st.radio(
        "Selecciona cómo quieres alimentar el motor de biomarcadores:",
        ["📥 Cargar desde Base de Datos (Perfiles)", "✍️ Ingreso Manual de Sensores"],
        horizontal=True
    )

    st.warning(
        "🧪 **Modo demostración**: los datos de este panel son presets de demo o entrada manual "
        "desconectada, **no telemetría en tiempo real de un paciente del UPS**. Ningún número aquí "
        "debe leerse como una medición real."
    )

    st.markdown("---")

    if modo_datos == "📥 Cargar desde Base de Datos (Perfiles)":
        # MODO AUTOMÁTICO (Lo que ya teníamos)
        st.markdown("#### ⚡ Escenarios Clínicos")
        escenario = st.selectbox(
            "Selecciona un perfil clínico pre-cargado:",
            ["👤 Estado Basal (Sano)", "🏃‍♂️ Atleta Post-Esfuerzo", "🤯 Estrés Cognitivo Severo", "😴 Fatiga Crónica"]
        )

        if escenario == "👤 Estado Basal (Sano)":
            datos_sensores = {'hrv_lf_hf_ratio': 1.5, 'eda_scr_peaks': 4, 'scl_u_siemens': 3.0, 'current_resting_hr': 65.0, 'hrv_rmssd': 45.0, 'sleep_hours': 7.5, 'eeg_alpha_power': 15.0, 'eeg_theta_power': 8.0, 'signal_coherence': 0.7, 'hrv_hf_power': 350.0, 'hr_surge': 5.0, 'hr_recovery_rate': 25.0, 'hrv_sdnn': 50.0}
        elif escenario == "🏃‍♂️ Atleta Post-Esfuerzo":
            datos_sensores = {'hrv_lf_hf_ratio': 2.8, 'eda_scr_peaks': 12, 'scl_u_siemens': 8.0, 'current_resting_hr': 85.0, 'hrv_rmssd': 25.0, 'sleep_hours': 8.0, 'eeg_alpha_power': 18.0, 'eeg_theta_power': 10.0, 'signal_coherence': 0.8, 'hrv_hf_power': 150.0, 'hr_surge': 15.0, 'hr_recovery_rate': 45.0, 'hrv_sdnn': 65.0}
        elif escenario == "🤯 Estrés Cognitivo Severo":
            datos_sensores = {'hrv_lf_hf_ratio': 4.2, 'eda_scr_peaks': 20, 'scl_u_siemens': 12.0, 'current_resting_hr': 95.0, 'hrv_rmssd': 15.0, 'sleep_hours': 4.5, 'eeg_alpha_power': 5.0, 'eeg_theta_power': 28.0, 'signal_coherence': 0.3, 'hrv_hf_power': 80.0, 'hr_surge': 25.0, 'hr_recovery_rate': 12.0, 'hrv_sdnn': 20.0}
        else: 
            datos_sensores = {'hrv_lf_hf_ratio': 0.8, 'eda_scr_peaks': 2, 'scl_u_siemens': 1.5, 'current_resting_hr': 55.0, 'hrv_rmssd': 85.0, 'sleep_hours': 9.0, 'eeg_alpha_power': 8.0, 'eeg_theta_power': 15.0, 'signal_coherence': 0.4, 'hrv_hf_power': 600.0, 'hr_surge': 2.0, 'hr_recovery_rate': 15.0, 'hrv_sdnn': 30.0}
        
        # Agregamos las métricas que no cambian en los presets
        # NOTA (2026-08-15, ampliada 2026-08-19): 'eda_scr_peaks'/
        # 'scl_u_siemens'/'signal_coherence'/'hrv_hf_power' arriba, y
        # 'metabolic_efficiency'/'bp_variance'/'ppg_pulse_transit_time_var'
        # abajo, quedan huérfanos -- BiocoreEngine ya no los consume (Stress
        # recortado a solo LF/HF, Resilience sin metabolic_efficiency,
        # Autonomic Stability retirado de la grilla por 0/2 inputs reales,
        # NeuroCardiac Coupling retirado por completo y reemplazado por el
        # PLV, que toma señal cruda ECG+EEG, no estos escalares).
        # Se dejan en los presets sin efecto, no se limpiaron -- CHANGELOG.md.
        datos_sensores['metabolic_efficiency'] = 1.1 if st.session_state.get('pac_actividad', '') == "Intenso (Atleta)" else 0.9
        datos_sensores['bp_variance'] = 4.5  # sin efecto -- ver nota arriba
        datos_sensores['ppg_pulse_transit_time_var'] = 11.2  # sin efecto -- ver nota arriba
        datos_sensores['eeg_beta_attenuation'] = 5.0

    else:
        # MODO MANUAL (Para que el usuario teclee uno por uno)
        st.markdown("#### ✍️ Panel de Ingreso Manual")
        st.caption("Haz clic en cualquier caja para escribir tu valor directamente o usa los botones.")
        
        tab_cardio, tab_neuro, tab_eda = st.tabs(["🫀 Cardio (ECG & HRV)", "🧠 Neuro (EEG)", "💧 Piel (EDA)"])

        with tab_cardio:
            c1, c2, c3 = st.columns(3)
            hr_val = c1.number_input("HR Reposo (bpm)", value=65.0, step=1.0)
            rmssd_val = c2.number_input("HRV RMSSD (ms)", value=45.0, step=1.0)
            sdnn_val = c3.number_input("HRV SDNN (ms)", value=50.0, step=1.0)
            
            c4, c5, c6 = st.columns(3)
            lfhf_val = c4.number_input("Ratio LF/HF", value=1.5, step=0.1)
            hf_val = c5.number_input("Poder HF (ms2, sin efecto)", value=350.0, step=10.0)
            hrr_val = c6.number_input("HR Recovery (bpm/min)", value=25.0, step=1.0)

        with tab_neuro:
            st.caption(
                "⚠️ 'Poder HF' arriba y 'Coherencia' abajo ya no alimentan ningún score -- "
                "NeuroCardiac Coupling se retiró por completo (2026-08-19), reemplazado por un PLV "
                "que necesita señal ECG+EEG cruda, no estos escalares. Ondas Alfa y Theta sí se "
                "siguen usando (Cognitive Load)."
            )
            n1, n2, n3 = st.columns(3)
            alpha_val = n1.number_input("Ondas Alfa", value=15.0, step=1.0)
            theta_val = n2.number_input("Ondas Theta", value=8.0, step=1.0)
            coh_val = n3.number_input("Coherencia (0-1, sin efecto)", value=0.7, step=0.05)

        with tab_eda:
            st.caption(
                "⚠️ Picos EDA y Conductancia Base ya no alimentan ningún score (Stress Index se "
                "recortó a solo LF/HF, 2026-08-15) -- no hay módulo de señal EDA real en el repo. "
                "Se dejan visibles sin efecto; HR Surge sí se sigue usando (Cognitive Load)."
            )
            e1, e2, e3 = st.columns(3)
            eda_val = e1.number_input("Picos EDA (sin efecto)", value=4, step=1)
            scl_val = e2.number_input("Conductancia Base (sin efecto)", value=3.0, step=0.5)
            surge_val = e3.number_input("HR Surge Cognitivo", value=5.0, step=1.0)

        # Empaquetamos los datos ingresados manualmente. 'eda_scr_peaks'/
        # 'scl_u_siemens'/'signal_coherence'/'hrv_hf_power'/
        # 'metabolic_efficiency'/'bp_variance'/'ppg_pulse_transit_time_var'
        # quedan huérfanos (ver notas en tab_eda/tab_neuro y CHANGELOG.md) --
        # no se limpiaron del dict para no romper el layout de tabs/columnas
        # existente. El PLV neurocardíaco no se alimenta de este dict en
        # absoluto -- necesita señal cruda ECG+EEG que este panel no captura.
        datos_sensores = {
            'hrv_lf_hf_ratio': lfhf_val, 'eda_scr_peaks': eda_val, 'scl_u_siemens': scl_val,
            'current_resting_hr': hr_val, 'hrv_rmssd': rmssd_val, 'sleep_hours': 7.5,
            'eeg_alpha_power': alpha_val, 'eeg_theta_power': theta_val, 'signal_coherence': coh_val,
            'hrv_hf_power': hf_val, 'hr_surge': surge_val, 'hr_recovery_rate': hrr_val,
            'hrv_sdnn': sdnn_val,
            'metabolic_efficiency': 1.1 if st.session_state.get('pac_actividad', '') == "Intenso (Atleta)" else 0.9,
            'bp_variance': 4.5, 'ppg_pulse_transit_time_var': 11.2,  # sin efecto -- ver nota arriba
            'eeg_beta_attenuation': 5.0
        }

    # ==========================================
    # CÁLCULO Y DESPLIEGUE (Común para ambos modos)
    # ==========================================
    
    # Penalizaciones automáticas basadas en los "Datos del paciente" de arriba
    if st.session_state.get('pac_cirugias', False):
        datos_sensores['hr_recovery_rate'] -= 5.0
    if st.session_state.get('pac_edad', 25) > 50:
        datos_sensores['hrv_rmssd'] *= 0.85

    resultados = engine.get_full_biomarker_suite(datos_sensores)

    st.divider()
    st.subheader("📊 Índices fisiológicos BIOCORE")
    st.caption(
        f"{BIOMARKER_CLINICAL_BADGE} constante citada por el validador · "
        f"{BIOMARKER_HEURISTIC_BADGE} ponderación heurística de BIOCORE (no derivada de estudio de "
        f"cohorte) · {BIOMARKER_METHOD_BADGE} método citado (algoritmo, no un rango) · "
        f"{BIOMARKER_GHOST_BADGE} fantasma: input sin fuente de señal real en el repo hoy "
        "— pasa el mouse sobre cada métrica (ⓘ) para el detalle exacto."
    )

    col1, col2, col3 = st.columns(3)

    # Fase 1 (idioma, 2026-08-30): solo se traduce la ETIQUETA visible
    # (`label=`) -- las claves de `resultados`/`_BIOMARKER_HELP` ("Stress
    # Index", etc.) siguen en inglés a propósito: son claves internas
    # compartidas con `biomarkers.py` y con `tests/test_biomarkers_plv.py`
    # (que las compara textualmente). Mismo principio que `MODES` en
    # twin_shell/pages.py -- ver CHANGELOG.md.
    with col1:
        st.metric(label="Índice de Estrés", value=f"{resultados['Stress Index']['score']}/100", delta=resultados['Stress Index']['status'], delta_color="inverse" if resultados['Stress Index']['score'] > 50 else "normal", help=_BIOMARKER_HELP["Stress Index"])
        st.metric(label="Carga Cognitiva", value=f"{resultados['Cognitive Load Score']['score']}/100", delta=resultados['Cognitive Load Score']['status'], delta_color="inverse" if resultados['Cognitive Load Score']['score'] > 65 else "normal", help=_BIOMARKER_HELP["Cognitive Load Score"])

    with col2:
        st.metric(label="Recovery Index", value=f"{resultados['Recovery Index']['score']}/100", delta=resultados['Recovery Index']['status'], help=_BIOMARKER_HELP["Recovery Index"])
        st.metric(label="Resiliencia Fisiológica", value=f"{resultados['Physiological Resilience Score']['score']}/100", delta=resultados['Physiological Resilience Score']['status'], help=_BIOMARKER_HELP["Physiological Resilience Score"])

    with col3:
        plv_entry = resultados['NeuroCardiac PLV']
        if plv_entry['available']:
            st.metric(label="NeuroCardiac PLV", value=f"{plv_entry['plv']:.2f}", delta=f"{plv_entry['duration_s']:.0f}s de señal", help=_BIOMARKER_HELP["NeuroCardiac PLV"])
        else:
            st.markdown("**NeuroCardiac PLV**", help=_BIOMARKER_HELP["NeuroCardiac PLV"])
            muestra = f"{plv_entry['duration_s']:.0f}s" if plv_entry['duration_s'] is not None else "0s"
            st.caption(
                f"🟣 Métrica deshabilitada: el PLV requiere ≥180s de señal ECG+EEG simultánea. "
                f"Muestra actual: {muestra}."
            )

        readiness_entry = resultados['Learning Readiness Index']
        if readiness_entry['available']:
            st.metric(label="Learning Readiness Index", value=f"{readiness_entry['score']}/100", delta=readiness_entry['status'], help=_BIOMARKER_HELP["Learning Readiness Index"])
        else:
            st.markdown("**Learning Readiness Index**", help=_BIOMARKER_HELP["Learning Readiness Index"])
            st.caption("🔵 Métrica deshabilitada: depende del PLV neurocardíaco (arriba), que no está disponible.")

    st.markdown("**Autonomic Stability**")
    st.info(
        "🔴 No disponible — sin fuente de señal real. Requiere presión arterial y PPG-PTT que hoy no "
        "existen en el pipeline (ver 🔴 Fantasmas abajo)."
    )

    with st.expander("🔴 Fantasmas — inputs sin fuente de señal real"):
        st.markdown(
            "El dictamen del validador identificó componentes sin señal real detrás en el repo. "
            "3 ya se resolvieron; 1 sigue retirado de la grilla sin reemplazo posible.\n\n"
            "- ✅ **`metabolic_efficiency`** (Physiological Resilience) — **retirado (2026-08-15)**. "
            "Fingía modelar el RER con un rango fisiológicamente imposible (RER real nunca <0.7 ni "
            ">1.5). El score quedó solo sobre HRR + SDNN ('marcadores dorados de resiliencia "
            "cardiovascular'), pesos renormalizados 0.45/0.35 → 0.5625/0.4375.\n"
            "- ✅ **`eda_scr_peaks` / `scl_u_siemens`** (Stress Index) — **retirados (2026-08-15)**. "
            "No existe ningún módulo de señal EDA en el repo. Stress Index quedó solo sobre LF/HF, "
            "normalizado directo a 0-100 (Task Force ESC/NASPE 1996) — el score entero está citado ahora.\n"
            "- ✅ **`signal_coherence`** (NeuroCardiac Coupling) — **retirado por completo (2026-08-19)**. "
            "No solo el placeholder: la fórmula entera (suma de potencias absolutas) era la que el "
            "validador calificó de pseudocientífica. Reemplazada por un PLV (Phase-Locking Value) real "
            "-- Theta Frontomedial (4-8Hz) vs. banda HF-HRV (0.15-0.40Hz), ≥180s de señal simultánea. "
            "Casi siempre mostrará 'no disponible' (ver 🟣 arriba) porque el pipeline hoy no persiste "
            "ECG+EEG crudos simultáneos -- eso es honestidad, no un bug.\n"
            "- 🔴 **`bp_variance` / `ppg_pulse_transit_time_var`** (Autonomic Stability) — **retirado "
            "de la grilla (2026-08-15)**. A diferencia de los otros 3 casos, aquí 0 de 2 inputs tienen "
            "cualquier fuente de señal real: no hay generador de presión arterial en el repo, y el "
            "módulo PPG existente no calcula pulse transit time. Sin reemplazo algorítmico identificado "
            "(a diferencia de NeuroCardiac→PLV) — la función `calculate_autonomic_stability_score()` "
            "queda latente en `biomarkers.py`, sin llamarse desde la UI, por si algún día hay "
            "instrumentación real de PA/PPG-PTT."
        )

    st.markdown("---")
    st.subheader("📝 Notas del Sistema de Razonamiento")
    actividad = st.session_state.get('pac_actividad', 'Moderado')
    if st.session_state.get('pac_cirugias', False):
        st.warning("⚠️ **Alerta Clínica:** Las variables de resiliencia cardiovascular y estabilidad han sido penalizadas según el historial de trauma/cirugía activa del paciente.")
    if actividad == "Intenso (Atleta)":
        st.success("⚡ **Adaptación Atlética:** El sistema detectó el perfil atlético y calibró el cálculo de eficiencia metabólica y recuperación vagal asumiendo adaptaciones cardiovasculares estructurales.")


# NOTA (2026-07-03): la antigua "EEG PAGE (COMPLETE)" inline (render_eeg_page)
# se eliminó — dependía de 'biomedical.eeg' (módulo inexistente) y por eso
# siempre mostraba un banner de error; tampoco tenía visualización de bandas
# de potencia. render_eeg_neuro_lab_page() (arriba) delega al supermódulo
# real, que sí funciona.

# ==================== EMG PAGE (COMPLETE) ====================

def render_emg_page() -> None:
    render_module_header("EMG Muscle Lab", icon="🦾")

    source = st.sidebar.radio('Origen EMG', ['Demo','CSV','Live Hardware'])
    pattern = st.sidebar.selectbox('Patrón', ['Isométrica','Rápida','Fatiga'])
    fs = st.sidebar.selectbox('fs (Hz)', [500,1000,2000], index=1)
    duration = st.sidebar.slider('Duración (s)', 5, 60, 15)

    signal = None
    time_arr = np.array([])
    if source == 'CSV':
        f = st.file_uploader('CSV EMG', type=['csv'])
        if f:
            try:
                data = np.genfromtxt(io.StringIO(f.read().decode()), delimiter=',')
                signal = data if data.ndim == 1 else data[:, 0]
                time_arr = np.arange(len(signal)) / fs
            except Exception as e:
                render_error_state(
                    "No se pudo leer el archivo CSV de EMG -- verifica el formato.",
                    exception=e,
                )
    elif source == 'Live Hardware':
        st.sidebar.markdown("### Hardware EMG")
        if SensorManager is not None:
            manager = SensorManager()
            port_options = manager.available_ports or ["Auto"]
            selected_port = st.sidebar.selectbox("Puerto EMG", port_options)
        else:
            selected_port = st.sidebar.text_input("Puerto EMG manual", value="Auto")
            st.sidebar.warning("No se pudo enumerar puertos seriales; ingresa el puerto manualmente.")

        connect_emg = st.sidebar.button('Conectar EMG Hardware')
        disconnect_emg = st.sidebar.button('Desconectar EMG Hardware')

        if connect_emg:
            if EMGStreamer is None:
                st.sidebar.error('EMGStreamer no está disponible. Instala pyserial y revisa hardware/emg_stream.py')
            else:
                chosen_port = None if selected_port in (None, 'Auto') else selected_port
                try:
                    streamer = EMGStreamer(port=chosen_port, baud=115200, fs=fs)
                    if streamer.connect(force_port=chosen_port):
                        streamer.start()
                        st.session_state.emg_streamer = streamer
                        st.sidebar.success('EMG hardware conectado y transmitiendo.')
                    else:
                        st.sidebar.warning('No se pudo conectar el hardware EMG. Usa modo demo o revisa el puerto.')
                except Exception as exc:
                    st.sidebar.error(f'Error al conectar EMG: {exc}')

        if disconnect_emg and st.session_state.get('emg_streamer') is not None:
            try:
                st.session_state.emg_streamer.stop()
                st.session_state.emg_streamer.disconnect()
            except Exception:
                pass
            st.session_state.emg_streamer = None
            st.sidebar.success('EMG hardware desconectado.')

        streamer = st.session_state.get('emg_streamer')
        if streamer is not None:
            st.sidebar.info(f"Estado EMG: {streamer.get_status()}")
            if getattr(streamer, 'last_error', None):
                st.sidebar.warning(f"Último error EMG: {streamer.last_error}")
            _, buffer = streamer.get_filtered_buffer()
            if buffer is not None and len(buffer) >= 5:
                signal = np.asarray(buffer)
                time_arr = np.arange(len(signal)) / fs
            else:
                st.sidebar.caption("Sin datos de hardware aún — usando demo mientras se conecta.")

        if signal is None:
            signal = generate_demo_emg_signal(fs, duration, pattern)
            time_arr = np.arange(len(signal)) / fs
    else:
        signal = generate_demo_emg_signal(fs, duration, pattern)
        time_arr = np.arange(len(signal)) / fs

    # NOTA (2026-07-03): "Gemelo Digital" se eliminó de este laboratorio — era un
    # "Muscle Fatigue Index" de np.random.uniform(10,80), redundante y desconectado
    # del gemelo real (Digital Twin OS / DigitalTwinOrganism). Ver CHANGELOG.md.
    view = render_view_selector(views=['Clínica', 'Educativa', 'Investigación', 'IA', 'Simulación'])

    if signal is None:
        # Solo alcanzable con Origen=CSV y ningún archivo cargado todavía.
        # Antes esto crasheaba en las vistas Clínica/IA (preprocess_emg(None)).
        render_empty_state("Carga un archivo CSV de EMG, o cambia el Origen a Demo / Live Hardware.")
        _render_emg_save_to_twin(fs, source, None)  # declara "sin señal", no finge guardar
        return

    emg_analysis = EmgAnalyzer(fs).analyze(signal)

    if view == 'Clínica':
        st.markdown('### Vista Clínica')
        activation = emg_analysis.activation_pct
        st.write('Activación muscular y patrones de contracción')
        render_metric_explained('Activación muscular', f'{activation:.1f}', unit='%',
                    meaning='Nivel promedio de activación muscular a partir del EMG rectificado.',
                    importance='Indica esfuerzo y riesgo de fatiga.',
                    affects='Carga, postura, fatiga, desbalance neuromuscular.',
                    relations='Se correlaciona con ECG y respiración durante esfuerzo.',
                    consequences='Elevada activación prolongada sugiere fatiga y riesgo de lesión.')
        st.write('¿Qué significa?: Nivel de reclutamiento motor. Por qué importa: indica esfuerzo y fatiga.')
        st.write('Qué lo afecta: carga, postura, fatiga, neurogenic factors.')
        render_scientific_discovery_layer({'EMG': signal})

    elif view == 'Educativa':
        st.markdown('### Vista Educativa')
        st.write('Visualiza activación, rectificación y aprende sobre fatiga muscular.')
        st.line_chart(signal)
        st.plotly_chart(PLOTLY_GO.Figure(PLOTLY_GO.Scatter(y=signal, name='Raw EMG')), use_container_width=True)

    elif view == 'Investigación':
        st.markdown('### Vista Investigación')
        median_freq = emg_analysis.median_frequency_hz
        st.write(f'Median frequency: {median_freq:.1f} Hz')
        if st.button('Exportar EMG para investigación'):
            p = export_lab_report('EMG Research', {'median_freq': median_freq}, notes='EMG export')
            if p:
                st.success(f'Exportado: {p}')

    elif view == 'IA':
        st.markdown('### Vista IA — Narrador clínico')
        render_findings_narrator('EMG Muscle Lab', [
            ('activation_pct', f'{emg_analysis.activation_pct:.1f}%', 'Nivel promedio de activación muscular (EMG rectificado, señal filtrada 20-450 Hz).'),
            ('median_frequency_hz', f'{emg_analysis.median_frequency_hz:.1f} Hz', 'Frecuencia mediana del espectro de potencia EMG — se desplaza hacia abajo con la fatiga.'),
            ('fatigue_index', f'{emg_analysis.fatigue_index:.0f}/100', 'Índice de fatiga derivado del corrimiento de la frecuencia mediana respecto a un basal de 120 Hz.'),
            ('signal_source', source, 'Origen de la señal: demo sintética, CSV cargado, o hardware en vivo.'),
        ])

    elif view == 'Simulación':
        st.markdown('### Vista Simulación')
        # NOTA (2026-08-19, Art. I): se retiraron el slider "Fuerza simulada"
        # (se definía y nunca se volvía a leer -- no influía en `signal` ni
        # en ningún cálculo, placebo de interacción) y la llamada a
        # `render_discovery_lab('EMG Gemelo', {'EMG': signal})` (inalcanzable
        # por diseño: esa función exige >=2 señales para calcular algo, EMG
        # solo pasaba 1, así que siempre caía en "Se requieren al menos 2
        # señales" sin hacer nada). `render_discovery_lab()` en sí no se
        # tocó -- sigue en uso real en otros laboratorios con 2+ señales. Se
        # conserva la vista con el patrón EMG actualmente simulado para que
        # no quede una pestaña vacía. Ver CHANGELOG.md.
        st.write('Simulación de contracción isométrica con diferente reclutamiento.')
        st.line_chart(signal)

    _render_emg_save_to_twin(fs, source, emg_analysis)


def _render_emg_save_to_twin(fs: int, source: str, emg_analysis) -> None:
    """Capa 5A dominio muscular, Tanda 3 (2026-09-10): el EMG Lab escribe al
    UPS por PRIMERA VEZ -- el "Paso 4" del playbook neuro, el mismo botón
    que ganaron ECG/HRV/Respiratory/EEG Lab (Fase 2.4 / Sub-fase 1).
    Opt-in deliberado: el estudiante analiza un EMG y elige guardarlo al
    gemelo -- es la acción que une el lab al organismo.

    El punto crítico de honestidad: `_update_muscles()`
    (`digital_twin_organism.py`) normalmente se alimenta del slider "Fatiga
    muscular" de Twin OS (un `fatigue_index` sintético). Este botón lo
    alimenta con la `activation` MEDIDA por `EmgAnalyzer` sobre la señal
    FILTRADA (butter 20-450 Hz, Tanda 1) -- la señal primaria real. Lo que
    llega a `muscles.metrics.signals["activation"]` es el valor del
    analizador, no un slider.

    Qué se envía: `activation` + `median_frequency` (ambas reales sobre
    cualquier sEMG). Qué NO: `fatigue_index` -- el generador demo (ruido
    blanco, espectro plano) lo clava en 0 y `_muscular_state()` lo difiere
    de todos modos (Tanda 2, Art. I: no persistir una constante disfrazada
    de medición). Con solo esas dos entradas, `_update_muscles()` calcula
    health_score/risk_score/neuromuscular_efficiency/movement_smoothness
    desde `efficiency`/`fatigue_index` DEFAULTEADOS (70/20) -- mismo nivel
    de tolerancia que ya acepta el EEG Lab (band power reales, stress_level
    defaulteado). El gate de `_muscular_state()` (`"activation" in signals`)
    es lo que decide "hay músculo que escribir".

    Procedencia `SIMULACION`: señal de `generate_demo_emg_signal` o CSV
    cargado, nunca un sensor en vivo verificado.
    """
    st.markdown("---")
    st.markdown("#### 🔗 Guardar estado al gemelo")

    if emg_analysis is None:
        # Origen=CSV sin archivo -- el caso que la Tanda 1 ya guarda arriba
        # con render_empty_state. El botón no finge: declara que no hay
        # señal analizable que persistir. Sin éxito fingido, sin crash.
        st.info(
            "Sin señal EMG analizable (Origen=CSV sin archivo cargado). No hay nada "
            "que persistir al gemelo -- carga un CSV o cambia el Origen a Demo / Live Hardware."
        )
        return

    st.caption(
        f"Escribe la **activación muscular real** ({emg_analysis.activation_pct:.1f}%) y la "
        f"**frecuencia mediana** ({emg_analysis.median_frequency_hz:.1f} Hz) analizadas de esta "
        "señal al Unified Physiological State, bajo el mismo paciente que renderiza Digital Twin "
        "OS -- sus músculos reaccionarán a estos valores la próxima vez que abras esa página. "
        "La activación viene del `EmgAnalyzer` (señal filtrada 20-450 Hz), NO del slider "
        "\"Fatiga muscular\" de Twin OS. `fatigue_index` NO se escribe (generador demo de "
        "espectro plano -- diferido). Procedencia: simulación (señal generada, no un sensor real)."
    )
    if st.button("💾 Guardar estado al gemelo", key="emg_lab_save_to_ups"):
        from app.engines.digital_twin_organism import DigitalTwinOrganism

        session_factory = get_active_session_factory()
        patient_id = get_active_patient_id()

        emg_organism = DigitalTwinOrganism()
        emg_organism.update_from_sensors({
            "emg": {
                "activation": float(emg_analysis.activation_pct),
                "median_frequency": float(emg_analysis.median_frequency_hz),
            }
        })
        state = from_digital_twin_organism(
            emg_organism, patient_id, provenance=Provenance.SIMULACION,
            source_detail=f"emg_muscle_lab:origen={source}",
        )
        with session_factory() as session:
            snapshot_id = save_state(session, state)

        st.success(f"Estado guardado al gemelo -- snapshot: {snapshot_id}")
        muscular = state.muscular
        if muscular.descriptors:
            st.caption(
                f"muscular: {len(muscular.descriptors)} descriptores · "
                f"activation = {muscular.get('activation').value:.1f}% "
                f"({muscular.get('activation').provenance.value}) · "
                f"median_frequency = {muscular.get('median_frequency').value:.1f} Hz · "
                "health_score / risk_score / neuromuscular_efficiency / movement_smoothness "
                "DERIVADO · sin fatigue_index (diferido) · sin campos fantasma"
            )
        else:
            st.caption("muscular: 0 descriptores (gate no cumplido -- inesperado con activation enviada)")
        st.caption(
            f"cardiovascular: {len(state.cardiovascular.descriptors)} · "
            f"respiratory: {len(state.respiratory.descriptors)} · "
            f"neurological: {len(state.neurological.descriptors)} "
            "(vacíos esperados -- este lab solo envía EMG)"
        )


def generate_demo_emg_signal(fs: float, duration: float, pattern: str) -> np.ndarray:
    n = int(fs * duration)
    t = np.arange(n) / fs
    if pattern == "Isométrica":
        env = 0.6 + 0.2 * np.sin(2*np.pi*0.5*t)
    elif pattern == "Rápida":
        env = 0.4 + 0.5*np.exp(-((t-duration/2)**2)/0.25)
    else:
        env = 0.6 + 0.3*(1-t/max(duration, 1))
    return env * np.random.normal(0, 1, n) + 0.05*np.sin(100*np.pi*t)

# ==================== OTHER PAGES ====================

@st.cache_resource
def get_case_database():
    """Cachea la base completa de 61 casos clínicos sintéticos.

    build_complete_case_database() usa np.random para edad/sexo/frecuencia en
    varios grupos de casos — cachear con @st.cache_resource evita que cada
    rerun de Streamlit regenere (y potencialmente cambie) los 61 casos.

    Reubicada aquí (2026-08-20, Capa 2 Fase 2.1) desde
    `app/supermodules/ecg_monitor/pages.py`, enterrado por código muerto (su
    `run()`/`main()` nunca tuvo un llamador vivo -- ver CHANGELOG.md). Esta
    era la única función de ese archivo con un import vivo real (aquí mismo,
    en `render_ecg_monitor_page()`)."""
    from src.clinical.case_database import build_complete_case_database
    return build_complete_case_database()


def _ecg_get_ptbxl_records() -> list:
    """Corrección (2026-08-09): esta función y `_ecg_load_ptbxl_record()` son un
    segundo loader PTB-XL, duplicado de `app/supermodules/ecg_monitor/pages.py`
    (copiado en la "Tanda de rescate — Joya 1/3", 2026-07-13) -- y es EL QUE
    REALMENTE SE RENDERIZA en la app viva (`render_ecg_lab_page()` -> pestaña
    "Monitoreo" -> `render_ecg_monitor_page()`, este archivo). El loader del
    supermódulo, aunque también se corrigió, no se llama desde ningún punto
    vivo (confirmado por grep: solo `get_case_database` se importa de ahí) --
    arreglar solo aquel habría dejado la fachada intacta en la superficie que
    el usuario de verdad ve. Los 5 IDs de antes (`'10038'`, etc.) nunca
    existieron en PTB-XL -- ver `clinical.ptbxl_metadata` para el diagnóstico
    completo y CHANGELOG.md."""
    from clinical.ptbxl_metadata import PtbxlUnavailableError, load_ptbxl_database
    import ast

    df = load_ptbxl_database()

    def _confirmed(scp_codes_str: str, code: str) -> bool:
        try:
            codes = ast.literal_eval(scp_codes_str)
        except (ValueError, SyntaxError):
            return False
        return codes.get(code) == 100.0

    picks: list = []
    seen_ids: set = set()

    def _add(code: str, label: str, limit: int) -> None:
        added = 0
        for _, row in df.iterrows():
            if added >= limit:
                break
            if row['ecg_id'] in seen_ids:
                continue
            if not _confirmed(row['scp_codes'], code):
                continue
            seen_ids.add(row['ecg_id'])
            picks.append({'ecg_id': int(row['ecg_id']), 'label': label, 'filename': row['filename_hr']})
            added += 1

    _add('NORM', 'Normal (NORM, confirmado)', 2)
    _add('CRBBB', 'Bloqueo de rama derecha (CRBBB, confirmado)', 1)
    _add('CLBBB', 'Bloqueo de rama izquierda (CLBBB, confirmado)', 1)

    return picks


def _ecg_load_ptbxl_record(filename: str, lead: int = 0):
    """Corrección (2026-08-09): antes de esto, esta función NUNCA cargó un
    registro real -- usaba `pn_dir='ptbxl'` (slug sin guion, inexistente en
    PhysioNet) con un `record_id` plano inventado. Cualquier "PTB-XL cargado"
    que la app mostró antes de hoy era en realidad el fallback silencioso a
    `generate_demo_ecg_signal()`, presentado como PTB-XL -- una fachada
    (Art. I de la Constitución). Ese fallback se eliminó por completo: sin
    red hacia PhysioNet, esto falla explícito con `PtbxlUnavailableError`,
    nunca cae a una señal sintética disfrazada de dato real. `filename` es
    ahora el valor `filename_hr` real del catálogo (ver
    `_ecg_get_ptbxl_records()`), no un ID inventado."""
    from clinical.ptbxl_metadata import PtbxlUnavailableError, resolve_ptbxl_wfdb_args

    try:
        import wfdb
    except ImportError as e:
        raise ImportError('wfdb no está instalado. Instala con: pip install wfdb') from e

    record_id, pn_dir = resolve_ptbxl_wfdb_args(filename)
    try:
        record = wfdb.rdrecord(record_id, pn_dir=pn_dir)
    except Exception as exc:
        raise PtbxlUnavailableError(
            f"PTB-XL requiere conexión a PhysioNet -- no se pudo cargar el registro "
            f"'{filename}' ({type(exc).__name__}: {exc})."
        ) from exc

    signal = record.p_signal[:, lead]
    fs = record.fs
    metadata = {'record_name': record.record_name, 'source': 'PTB-XL', 'filename': filename}
    return signal, fs, metadata


def _ecg_export_signal_csv(signal: np.ndarray, fs: float, prefix: str = 'ecg_export') -> str:
    """Rescatado de app/supermodules/ecg_monitor/pages.py (Tanda de rescate — Joya 1/3,
    2026-07-13) — sin cambios de lógica, solo de ubicación."""
    import pandas as pd
    ts = int(time.time())
    os.makedirs('datasets/exports', exist_ok=True)
    filename = f'datasets/exports/{prefix}_{ts}.csv'
    times = np.arange(len(signal)) / float(fs)
    df = pd.DataFrame({'time': times, 'signal': signal})
    df.to_csv(filename, index=False)
    return filename


def _ecg_create_reproducible_notebook(csv_path: str, metadata: dict) -> str:
    """Rescatado de app/supermodules/ecg_monitor/pages.py (Tanda de rescate — Joya 1/3,
    2026-07-13) — sin cambios de lógica, solo de ubicación."""
    import json
    nb = {
        'cells': [
            {
                'cell_type': 'markdown',
                'metadata': {'language': 'markdown'},
                'source': [
                    "# ECG Analysis Notebook\n",
                    f"**Provenance:** {json.dumps(metadata)}\n",
                    "This notebook loads the exported ECG CSV and runs a simple plot and HR estimate.",
                ],
            },
            {
                'cell_type': 'code',
                'metadata': {'language': 'python'},
                'source': [
                    "import pandas as pd\n",
                    "import matplotlib.pyplot as plt\n",
                    f"df = pd.read_csv(r'{csv_path}')\n",
                    "plt.plot(df['time'], df['signal'])\n",
                    "plt.xlabel('Time (s)')\n",
                    "plt.ylabel('ECG')\n",
                    "plt.show()\n",
                ],
            },
        ],
        'metadata': {'kernelspec': {'name': 'python3', 'language': 'python'}, 'language_info': {'name': 'python'}},
        'nbformat': 4,
        'nbformat_minor': 5,
    }
    ts = int(time.time())
    os.makedirs('notebooks/exports', exist_ok=True)
    nb_path = f'notebooks/exports/ecg_notebook_{ts}.ipynb'
    with open(nb_path, 'w', encoding='utf-8') as f:
        json.dump(nb, f, indent=2)
    prov_path = nb_path + '.prov.json'
    with open(prov_path, 'w', encoding='utf-8') as pf:
        json.dump(metadata, pf, indent=2)
    return nb_path


def _render_ecg_save_to_twin(signal: np.ndarray, fs: float, metadata: dict, ECGAnalyzerCls) -> None:
    """Tercer y último lab de la integración estrecha (2026-08-24, Capa
    2/5B, tanda de cableado) -- molde idéntico a Respiratory/HRV, con la
    compuerta whitelist (detector TKEO + Vpp + filtros R-R, 6 rondas de
    validación con el experto, ver docs/validation/ecg_hr_detector_bank/)
    gobernando la escritura.

    Fuente demo excluida por completo -- decisión que SIGUE en pie tras la
    Fase 5B (2026-08-30, ver CHANGELOG.md), aunque su razón original ya no
    aplica: `generate_demo_ecg_signal()` ignoraba `hr` (bug de generador,
    ahora corregido -- `DynamicECGGenerator`/McSharry 2003, respeta el HR
    pedido, validado por TKEO). La exclusión se mantiene por una razón
    distinta y más fundamental: el HR demo es un valor ELEGIDO por el
    estudiante en un slider, nunca MEDIDO de nada -- aunque el generador
    ahora sea fiel a ese valor pedido, escribirlo al UPS seguiría siendo
    "guardar lo que alguien pidió", no "guardar lo que se observó", que es
    la garantía que esta compuerta existe para proteger. Ni siquiera se
    muestra el botón para esa fuente -- una decisión permanente, no una
    que la compuerta re-evalúe cada vez.

    Procedencia -- decisión documentada, no una convención perfecta: el
    schema (`Provenance`) no tiene una categoría para "dato real de
    paciente real, reproducido de un dataset público, no medido en vivo
    aquí" (MIT-BIH/PTB-XL/CSV/casos clínicos). `SENSOR_REAL` se reserva
    -- mismo criterio que ya usa `twin_shell.pages` para ESP32 -- para
    hardware conectado y verificado EN VIVO en este momento, nunca por la
    sola intención de conectar. Todo lo demás usa `Provenance.SIMULACION`
    (la caja disponible más honesta en el enum actual -- mismo precedente
    que Patient Pipeline, cuya entrada manual real tampoco es
    "sensor_real"), con `source_detail` cargando la procedencia exacta
    (qué dataset/registro/caso) para que quien lea el UPS sepa
    precisamente de dónde vino, no solo la etiqueta genérica."""
    st.markdown("#### 🔗 Guardar estado al gemelo")
    source_label = metadata.get('source', 'demo')

    if 'demo' in source_label.lower():
        st.info(
            "Fuente demo (sintética) -- nunca escribe HR al gemelo. El HR de esta fuente es un valor "
            "que TÚ elegiste en el slider, no algo medido de un paciente -- guardarlo confundiría "
            "'lo que pediste' con 'lo que se observó', aunque el generador ya sea fiel a ese valor "
            "(Fase 5B). Cambia a MIT-BIH, PTB-XL, un caso clínico, CSV o hardware ESP32 para guardar "
            "un HR real."
        )
        return

    st.caption(
        "Corre el detector TKEO + la compuerta whitelist (pRR31 para FA / metrónomo para marcapasos "
        "/ banda sinusal / calidad por Vpp) sobre esta señal. Si el ritmo se confirma "
        "sinusal-evaluable, escribe `heart_rate` real al Unified Physiological State, bajo el mismo "
        "paciente que renderiza Digital Twin OS -- su corazón reaccionará la próxima vez que abras "
        "esa página o pulses \"Sincronizar\" ahí. Si declina, no escribe nada -- verás el motivo "
        "clínico exacto."
    )
    if st.button("💾 Guardar estado al gemelo", key="ecg_lab_save_to_ups"):
        if ECGAnalyzerCls is None:
            render_error_state("Motor ECGAnalyzer no disponible en este entorno -- no se puede evaluar la compuerta.")
            return

        from clinical.ecg_analyzer import ClinicalDataQualityError

        analyzer = ECGAnalyzerCls(fs=fs)
        try:
            hr, confidence = analyzer.estimate_heart_rate_with_confidence(signal)
        except ClinicalDataQualityError as e:
            st.warning(f"⛔ Escritura declinada por seguridad clínica: {e}")
            return

        from domain.physiology.state import Provenance, from_digital_twin_organism, save_state
        from app.engines.digital_twin_organism import DigitalTwinOrganism

        # Fase 3 (paciente único de sesión, 2026-08-30): antes este bloque
        # comprobaba/creaba `twin_shell_ups_session_factory`/
        # `twin_shell_ups_patient_id` por su cuenta -- 1 de los 4 sitios que
        # copiaban el mismo bootstrap. Ahora pasa por el único punto de
        # verdad (`app/utils/patient_session.py`); el comportamiento no
        # cambia (misma clave, mismo paciente), solo deja de depender de la
        # convención de copiar el nombre.
        session_factory = get_active_session_factory()
        patient_id = get_active_patient_id()

        provenance = Provenance.SENSOR_REAL if 'SENSOR_REAL' in source_label else Provenance.SIMULACION

        organism = DigitalTwinOrganism()
        organism.update_from_sensors({"ecg": {"heart_rate": float(hr)}})
        state = from_digital_twin_organism(
            organism, patient_id, provenance=provenance,
            source_detail=f"ecg_lab:{source_label}",
        )
        with session_factory() as session:
            snapshot_id = save_state(session, state)

        st.success(
            f"Estado guardado al gemelo -- snapshot: {snapshot_id} "
            f"(HR={hr:.0f}bpm, confianza={confidence:.2f})"
        )
        st.caption(
            f"cardiovascular: {len(state.cardiovascular.descriptors)} descriptores · "
            f"respiratory: {len(state.respiratory.descriptors)} descriptores "
            f"(vacío esperado -- este lab no envía dato respiratorio)"
        )


def render_ecg_monitor_page() -> None:
    # Fase 2.3 Tanda 3 (2026-08-29): antes repetía el título del módulo
    # ("ECG Lab") DENTRO de la pestaña "Monitoreo" del hub que ya lo
    # muestra arriba (render_ecg_lab_page()) -- downgrade a encabezado de
    # sección, no un segundo título de módulo duplicado.
    render_section_header("Monitoreo")
    ECGAnalyzer, create_clinical_ecg_figure, load_mitbih_record, get_mitbih_records, ecg_ok = safe_import_ecg_modules()
    src_modules, src_ok = safe_import_src_modules()

    source = st.sidebar.radio(
        'ECG Source',
        [
            'Demo (sintético)', 'CSV local', 'Caso clínico (61 disponibles)',
            'Base de datos MIT-BIH', 'Base de datos PTB-XL', 'Hardware ESP32 en vivo',
        ],
        index=0,
    )
    signal = None
    fs = 250
    metadata = {}
    loaded_case = None

    if source == 'CSV local':
        uploaded = st.sidebar.file_uploader('Carga ECG local (CSV)', type=['csv'])
        if uploaded and src_ok and 'load_biomedical_signal' in src_modules:
            try:
                with open(os.path.join(tempfile.gettempdir(), uploaded.name), 'wb') as tmp:
                    tmp.write(uploaded.read())
                signal, fs, metadata = src_modules['load_biomedical_signal'](os.path.join(tempfile.gettempdir(), uploaded.name))
                st.success('Señal ECG cargada desde CSV local')
            except Exception as e:
                render_error_state(
                    "No se pudo cargar el archivo CSV -- verifica que el formato sea el esperado "
                    "(columna de señal + frecuencia de muestreo).",
                    exception=e,
                )
        elif uploaded:
            st.warning('Carga de CSV detectada, pero faltan módulos de `src`. Usando demo.')

    elif source == 'Caso clínico (61 disponibles)':
        case_db = get_case_database()
        st.sidebar.caption(f"📚 {case_db.count_cases()} casos disponibles, agrupados por diagnóstico.")
        diagnosis_options = sorted({c.primary_diagnosis.value for c in case_db.cases.values()})
        selected_diagnosis = st.sidebar.selectbox('Diagnóstico primario', diagnosis_options)
        matching_cases = sorted(
            (c for c in case_db.cases.values() if c.primary_diagnosis.value == selected_diagnosis),
            key=lambda c: c.case_id,
        )
        selected_case_id = st.sidebar.selectbox(
            'Caso específico',
            [c.case_id for c in matching_cases],
            format_func=lambda cid: next(
                f"{c.case_id} — {c.age}a {c.sex}, dificultad {c.difficulty.value}"
                for c in matching_cases if c.case_id == cid
            ),
        )
        loaded_case = case_db.get_case(selected_case_id)
        signal = loaded_case.ecg_signal
        fs = loaded_case.fs
        metadata = {'source': f'caso clínico {selected_case_id}', 'diagnosis': loaded_case.primary_diagnosis.value}

    elif source == 'Base de datos MIT-BIH':
        # Rescatado (Tanda de rescate — Joya 1/3, 2026-07-13): el loader ya vivía
        # compartido en signals/loaders/wfdb_loader.py (safe_import_ecg_modules() lo
        # importa arriba) — lo único que faltaba era esta opción de UI para alcanzarlo.
        if not ecg_ok:
            st.sidebar.warning(
                'El loader MIT-BIH no está disponible en este entorno (falta `wfdb` o '
                '`signals.loaders`). Usando demo.'
            )
        else:
            mitbih_records = get_mitbih_records()
            selected_mitbih = st.sidebar.selectbox('Registro MIT-BIH', mitbih_records)
            if st.sidebar.button('Cargar registro MIT-BIH'):
                try:
                    loaded_signal, loaded_fs, mitbih_meta = load_mitbih_record(selected_mitbih)
                    st.session_state['_ecg_monitor_mitbih_cache'] = (
                        loaded_signal, loaded_fs,
                        {'source': f'MIT-BIH {selected_mitbih} (PhysioNet)', **mitbih_meta},
                    )
                except Exception as e:
                    st.session_state['_ecg_monitor_mitbih_cache'] = None
                    # Piloto de impacto, Fase 2.3 Tanda 2 (2026-08-29): antes
                    # `display_error_message()` mostraba `str(e)` crudo -- un
                    # `URLError`/`HTTPError` de la descarga en vivo de
                    # PhysioNet, o un 404 de registro inexistente, aparecía
                    # tal cual en pantalla. Ahora: caja limpia para quien ve
                    # la demo, traza completa a logging para quien depura.
                    render_error_state(
                        "No se pudo cargar el registro MIT-BIH -- verifica la conexión a PhysioNet "
                        "o prueba otro registro.",
                        exception=e,
                    )
            cached_mitbih = st.session_state.get('_ecg_monitor_mitbih_cache')
            if cached_mitbih is not None:
                signal, fs, metadata = cached_mitbih
            else:
                render_empty_state(
                    "Aún no hay ningún registro MIT-BIH cargado",
                    action='selecciona uno arriba y pulsa "Cargar registro MIT-BIH" -- se descarga en vivo desde PhysioNet',
                )

    elif source == 'Base de datos PTB-XL':
        # Corregido 2026-08-09 -- ver docstrings de _ecg_get_ptbxl_records()/
        # _ecg_load_ptbxl_record() para el diagnóstico y la corrección completa.
        try:
            ptbxl_records = _ecg_get_ptbxl_records()
        except Exception as e:
            ptbxl_records = []
            render_error_state(
                "No se pudo obtener el catálogo de PTB-XL -- verifica la conexión a PhysioNet.",
                exception=e,
            )

        if not ptbxl_records:
            st.sidebar.warning('No hay registros PTB-XL disponibles ahora mismo (ver error arriba).')
        else:
            selected_ptbxl = st.sidebar.selectbox(
                'Registro PTB-XL', ptbxl_records,
                format_func=lambda r: f"{r['ecg_id']} — {r['label']}",
            )
            if st.sidebar.button('Cargar registro PTB-XL'):
                try:
                    loaded_signal, loaded_fs, ptbxl_meta = _ecg_load_ptbxl_record(selected_ptbxl['filename'])
                    st.session_state['_ecg_monitor_ptbxl_cache'] = (
                        loaded_signal, loaded_fs,
                        {'source': f"PTB-XL {selected_ptbxl['ecg_id']} ({selected_ptbxl['label']}, PhysioNet)", **ptbxl_meta},
                    )
                except Exception as e:
                    st.session_state['_ecg_monitor_ptbxl_cache'] = None
                    # Segundo sitio del piloto de impacto (Fase 2.3 Tanda 2) --
                    # este es el que más falla en la práctica: `_ecg_load_ptbxl_record()`
                    # lanza `PtbxlUnavailableError` explícito sin red hacia
                    # PhysioNet (ver su docstring) -- antes ese mensaje, ya
                    # honesto en su texto, se mostraba con la traza de Python
                    # pegada. Misma caja limpia + traza al log.
                    render_error_state(
                        "No se pudo cargar el registro PTB-XL -- verifica la conexión a PhysioNet "
                        "o prueba otro registro.",
                        exception=e,
                    )
            cached_ptbxl = st.session_state.get('_ecg_monitor_ptbxl_cache')
            if cached_ptbxl is not None:
                signal, fs, metadata = cached_ptbxl
            else:
                st.sidebar.info('Selecciona un registro y pulsa "Cargar" — se descarga en vivo desde PhysioNet.')

    elif source == 'Hardware ESP32 en vivo':
        # Rescatado (Tanda de rescate — Joya 1/3, 2026-07-13). Disciplina de
        # procedencia de la Tanda 4: SENSOR_REAL solo si is_hardware_present() confirma
        # una conexión serial real EN ESTE MOMENTO — nunca por la sola intención de
        # conectar (is_connected()/.connected siguen en True bajo simulate_if_missing).
        from src.signals.signal_sources import ESP32SignalSource

        st.sidebar.caption(
            'Conecta un ESP32 real por puerto serial. Si no responde ningún dispositivo '
            'físico, la señal se etiqueta SIMULACIÓN — nunca SENSOR_REAL por la sola '
            'intención de conectar.'
        )
        esp32_port = st.sidebar.text_input('Puerto ESP32 (o "Auto")', value='Auto', key='ecg_monitor_esp32_port')
        col_connect, col_disconnect = st.sidebar.columns(2)
        with col_connect:
            connect_clicked = st.button('🔌 Conectar', key='ecg_monitor_esp32_connect')
        with col_disconnect:
            disconnect_clicked = st.button('Desconectar', key='ecg_monitor_esp32_disconnect')

        if connect_clicked:
            chosen_port = None if esp32_port.strip().lower() == 'auto' else esp32_port.strip()
            try:
                hw_source = ESP32SignalSource(
                    port=chosen_port, fs=250, buffer_seconds=15, simulate_if_missing=True
                )
                hw_source.connect(force_port=chosen_port)
                hw_source.start()
                st.session_state['ecg_monitor_esp32_source'] = hw_source
            except Exception as e:
                render_error_state(
                    "No se pudo conectar al ESP32 -- verifica el puerto y que el dispositivo esté "
                    "encendido.",
                    exception=e,
                )

        if disconnect_clicked and st.session_state.get('ecg_monitor_esp32_source') is not None:
            try:
                st.session_state['ecg_monitor_esp32_source'].stop()
                st.session_state['ecg_monitor_esp32_source'].disconnect()
            except Exception:
                pass
            st.session_state['ecg_monitor_esp32_source'] = None

        hw_source = st.session_state.get('ecg_monitor_esp32_source')
        if hw_source is None:
            st.sidebar.info('No hay ninguna fuente de hardware conectada todavía.')
        else:
            # Prueba de honestidad de procedencia (mismo patrón que Twin OS, Tanda 4
            # Pieza 2): is_hardware_present() comprueba una conexión serial real EN ESTE
            # MOMENTO, no si alguna vez se intentó conectar.
            hardware_real = hw_source.is_hardware_present()
            _, buf_signal = hw_source.get_filtered_buffer()
            if len(buf_signal) < 5:
                st.sidebar.warning(
                    'El buffer de hardware está casi vacío todavía — espera unos segundos '
                    'o revisa la conexión.'
                )
            else:
                signal, fs = buf_signal, hw_source.fs
                if hardware_real:
                    st.sidebar.success('🟢 PROCEDENCIA: SENSOR_REAL — hardware ESP32 real respondiendo.')
                    metadata = {'source': 'ESP32 (SENSOR_REAL)'}
                else:
                    st.sidebar.warning(
                        '🟡 PROCEDENCIA: SIMULACIÓN — no se detectó ningún dispositivo físico; '
                        'el software cayó a modo simulado. Re-etiquetado explícitamente, nunca '
                        'mostrado como sensor real.'
                    )
                    metadata = {'source': 'ESP32 (SIMULACIÓN — sin hardware real detectado)'}

    if signal is None:
        hr_demo = st.sidebar.slider('Demo HR (bpm)', 40, 140, 72)
        # Fase 5B (2026-08-30): DynamicECGGenerator (McSharry et al. 2003)
        # reemplaza a generate_demo_ecg_signal() -- ver
        # src/signals/ecg/dynamic_ecg_generator.py. El generador viejo
        # ignoraba `hr` (QRS con ciclo fijo `t % 1`); este respeta el HR
        # pedido (validado por TKEO, error <0.2bpm en todo el rango 40-200,
        # ver CHANGELOG.md).
        signal = DynamicECGGenerator(fs=fs).generate(duration=20, hr=hr_demo)
        metadata['source'] = 'demo'

    valid, msg = validate_signal(signal)
    if not valid:
        render_error_state(msg)
        return

    # NOTA (2026-07-03): "Gemelo Digital" se eliminó de este laboratorio — el
    # gemelo real ya existe en Digital Twin OS (DigitalTwinOrganism); esta pestaña
    # era una animación 3D decorativa y un "Contractility Index" ad-hoc,
    # desconectados de ese gemelo real. Ver CHANGELOG.md.
    view = render_view_selector(views=['Clínica', 'Educativa', 'Investigación', 'IA', 'Simulación'])
    # Fase 5B (2026-08-30): la fuente demo ahora se mide con el detector
    # TKEO (`ECGAnalyzer.detect_r_peaks_tkeo`, el mismo motor que usa el
    # resto del pipeline clínico), no con `estimate_ecg_heart_rate()` (tope
    # duro en 220bpm -- el origen del "220 fijo" del generador viejo). Sigue
    # siendo una MEDICIÓN, nunca el `hr_demo` pedido repetido tal cual --
    # coherente con la garantía de honestidad; solo que ahora el generador
    # es fiel, así que medir y pedir coinciden. Las demás fuentes (MIT-BIH/
    # PTB-XL/CSV/hardware -- señal real, no se toca) siguen con el detector
    # de siempre.
    if metadata.get('source') == 'demo' and ECGAnalyzer is not None:
        demo_peaks = ECGAnalyzer(fs=fs).detect_r_peaks_tkeo(signal)
        hr = 60.0 * fs / np.mean(np.diff(demo_peaks)) if len(demo_peaks) >= 2 else 0.0
    else:
        hr = estimate_ecg_heart_rate(signal, fs)
    vm = np.arange(len(signal)) / fs

    def show_anatomy(part: str):
        explanations = {
            'SA Node': 'Nodo SA: marcapasos natural que inicia la despolarización atrial (ondas P).',
            'AV Node': 'Nodo AV: retraso fisiológico para permitir llenado ventricular antes de la contracción.',
            'His Bundle': 'Haz de His: conduce el impulso hacia las ramas ventriculares.',
            'Purkinje': 'Fibras de Purkinje: distribución rápida que sincroniza la contracción ventricular.'
        }
        st.markdown(f"**{part}**: {explanations.get(part, '')}")

    if view == 'Clínica':
        st.markdown('### Vista Clínica')
        render_metric_explained('Heart Rate', f'{hr:.0f}', unit='bpm',
                    meaning='Frecuencia cardíaca derivada del ECG.',
                    importance='Principal indicador de estado cardiovascular y esfuerzo.',
                    affects='Ejercicio, arritmias, fármacos, volumen intravascular.',
                    relations='Afecta perfusión, demanda metabólica y sincronía con respiración.',
                    consequences='Cambios bruscos pueden indicar arritmia o shock.')
        st.markdown(f"**Fuente:** {metadata.get('source', 'demo')}  |  **Muestreo:** {fs} Hz")

        st.divider()
        _render_ecg_save_to_twin(signal, fs, metadata, ECGAnalyzer)

        if loaded_case is not None:
            with st.expander(f"📋 Detalle del caso {loaded_case.case_id}", expanded=False):
                st.write(f"**Paciente:** {loaded_case.age} años, sexo {loaded_case.sex}")
                st.write(f"**Diagnóstico primario:** {loaded_case.primary_diagnosis.value}")
                if loaded_case.secondary_diagnoses:
                    st.write(
                        "**Diagnósticos secundarios:** "
                        + ", ".join(d.value for d in loaded_case.secondary_diagnoses)
                    )
                if loaded_case.risk_factors:
                    st.write("**Factores de riesgo:** " + ", ".join(loaded_case.risk_factors))
                if loaded_case.clinical_history:
                    st.write(f"**Historia clínica:** {loaded_case.clinical_history}")
                st.write(f"**Dificultad:** {loaded_case.difficulty.value}")
                if loaded_case.clinical_action:
                    st.write(f"**Acción clínica recomendada:** {loaded_case.clinical_action}")
                if loaded_case.mortality_risk:
                    st.write(f"**Riesgo de mortalidad estimado:** {loaded_case.mortality_risk * 100:.0f}%")

        render_scientific_discovery_layer({'ECG': signal})
        if PLOTLY_OK:
            try:
                fig = PLOTLY_GO.Figure()
                fig.add_trace(PLOTLY_GO.Scatter(x=vm, y=signal, name='ECG', mode='lines'))
                fig.update_layout(template='plotly_dark', height=360, title='ECG — Señal')
                st.plotly_chart(fig, use_container_width=True)
            except Exception:
                st.line_chart(signal)
        else:
            st.line_chart(signal)

        st.markdown('#### Fisiología dinámica — selecciona un segmento para ver eventos:')
        seg = st.selectbox('Segmento', ['P', 'QRS', 'T'])
        if seg == 'P':
            st.write('- Evento eléctrico: despolarización atrial (onda P).')
            st.write('- Evento mecánico: contracción atrial, contribuye al llenado ventricular.')
            st.write('- Evento hemodinámico: ligero aumento en presión auricular y llenado ventricular.')
        elif seg == 'QRS':
            st.write('- Evento eléctrico: despolarización ventricular (complejo QRS).')
            st.write('- Evento mecánico: contracción ventricular y eyección sistólica.')
            st.write('- Evento hemodinámico: aumento de presión arterial sistólica y gasto cardiaco.')
        else:
            st.write('- Evento eléctrico: repolarización ventricular (onda T).')
            st.write('- Evento mecánico: relajación ventricular y inicio del llenado.')

        st.markdown('#### Diagnóstico diferencial (ejemplo)')
        st.write('Si observa elevación persistente de ST en derivaciones contiguas:')
        st.write('- Hallazgos: elevación del ST en V2-V4')
        st.write('- Posibles diagnósticos: Infarto agudo de miocardio anterior (LAD).')
        st.write('- Justificación: correlación con territorios coronarios y síntomas clínicos.')

    elif view == 'Educativa':
        st.markdown('### Vista Educativa — Anatomía interactiva')
        cols = st.columns(4)
        if cols[0].button('Nodo SA'):
            show_anatomy('SA Node')
        if cols[1].button('Nodo AV'):
            show_anatomy('AV Node')
        if cols[2].button('Haz de His'):
            show_anatomy('His Bundle')
        if cols[3].button('Fibras Purkinje'):
            show_anatomy('Purkinje')

        st.markdown('### Timeline fisiológica')
        st.write('Despolarización → Contracción → Eyección → Relajación → Llenado ventricular')
        st.markdown('Pasa por cada etapa usando los controles:')
        step = st.slider('Etapa', 0, 4, 0)
        steps = ['Despolarización', 'Contracción', 'Eyección', 'Relajación', 'Llenado']
        st.info(steps[step])

    elif view == 'Investigación':
        st.markdown('### Vista Investigación')
        st.write('Genera series temporales, compara cohortes y exporta datos para análisis científico.')
        if st.button('Exportar segmento para investigación'):
            path = export_lab_report('ECG Segment', {'length': len(signal)}, notes='Segmento ECG para investigación')
            if path:
                st.success(f'Exportado: {path}')

        # Rescatado (Tanda de rescate — Joya 1/3, 2026-07-13) de
        # app/supermodules/ecg_monitor/pages.py — usa la señal/fs/metadata realmente
        # cargadas arriba (cualquiera sea la fuente activa), no un script aparte.
        if st.button('📓 Generar notebook reproducible desde esta señal'):
            try:
                csv_path = _ecg_export_signal_csv(signal, fs, prefix='ecg_for_notebook')
                notebook_metadata = {
                    'timestamp': int(time.time()),
                    'module': 'ECG Monitor',
                    'source': metadata.get('source', 'unknown'),
                    'fs': fs,
                }
                nb_path = _ecg_create_reproducible_notebook(csv_path, notebook_metadata)
                st.success(f'CSV exportado: {csv_path}')
                st.success(f'Notebook reproducible creado: {nb_path}')
            except Exception as e:
                render_error_state(
                    "No se pudo crear el notebook reproducible -- inténtalo de nuevo.",
                    exception=e,
                )

        st.markdown('#### Correlaciones ejemplo con otros sensores')
        resp_demo = generate_demo_respiration_signal(fs, 20, 16)
        spo2_demo = generate_demo_spo2_signal(fs, 20)
        len_min = min(len(signal), len(resp_demo), len(spo2_demo))
        corr_ecg_resp = float(np.corrcoef(signal[:len_min], resp_demo[:len_min])[0, 1]) if len_min > 1 else 0.0
        corr_ecg_spo2 = float(np.corrcoef(signal[:len_min], spo2_demo[:len_min])[0, 1]) if len_min > 1 else 0.0
        st.write(f'ECG ↔ Respiración: {corr_ecg_resp:.2f} — ECG ↔ SpO₂: {corr_ecg_spo2:.2f}')

    elif view == 'IA':
        st.markdown('### Vista IA — Narrador clínico')
        try:
            if src_ok and 'interpret_ecg' in src_modules:
                result = src_modules['interpret_ecg'](signal, fs)
                intervals = result.get('intervals', {})
                flags = result.get('flags', {})
                st.caption(result.get('description', ''))
                # Consolidación, Tanda 1 (2026-07-13): el finding 'qtc_s' se quitó —
                # dependía de un QT inventado (0.36s fijo), nunca medido de la señal
                # (ver src/clinical/ecg_interpreter.py). No se narra un QTc que no se
                # midió de verdad.
                findings = [
                    ('heart_rate_bpm', f"{intervals.get('bpm', float('nan')):.1f}", 'Frecuencia cardíaca estimada por detección de picos R.'),
                ]
                active_flags = [name for name, val in flags.items() if val]
                findings.append((
                    'flags_detectados',
                    ', '.join(active_flags) if active_flags else 'ninguno',
                    'Hallazgos marcados por el analizador de umbrales (taquicardia/bradicardia/ST/heurístico simple de posible fibrilación auricular — no un diagnóstico).',
                ))
                render_findings_narrator('ECG Monitor', findings)
            else:
                st.info('El analizador de ECG (`interpret_ecg`) no está disponible en este entorno — no hay hallazgos reales que narrar.')
        except Exception as e:
            st.warning(f'El análisis de ECG falló: {e}')

    elif view == 'Simulación':
        st.markdown('### Vista Simulación — Modo Exploración')
        st.write('Ajusta parámetros y observa efectos en ECG y explicaciones asociadas.')
        # Keys explícitas (Fusión ECG Lab, 2026-07-14): estos dos labels son
        # "near-miss" de dos widgets equivalentes en ecg_12/page_content.py
        # (difieren solo en mayúscula/redacción) — con ambos flujos ahora en
        # la misma página, la key ya no depende de que el texto siga distinto.
        fc = st.slider('Frecuencia cardíaca (bpm)', 30, 160, int(hr), key="ecglab_monitor_sim_hr")
        pr = st.slider('PR (ms)', 80, 300, 160)
        qrs = st.slider('QRS (ms)', 60, 200, 100, key="ecglab_monitor_sim_qrs")
        qt = st.slider('QT (ms)', 200, 500, 360)
        st.markdown('#### Qué cambiaría si...')
        st.write('- Aumenta FC: reduce intervalo RR, puede disminuir tiempo de llenado ventricular.')
        st.write('- QRS ancho: sugiere bloqueo de rama o conducción aberrante, afecta sincronía ventricular.')


def _build_multisensor_record(channels: dict, BiosignalChannel, MultisensoralRecord):
    """Construye el `MultisensoralRecord` compartido por Clínica/IA/Simulación
    de Multisensor Fusion Lab -- misma ruta de cálculo
    (`compute_physiological_indices()`/`health_score()`) en las tres, sin
    duplicar la lógica de construcción. Añadida 2026-08-20 (Capa 2 Fase 2.2)
    al cablear Simulación al cálculo real.

    Bug corregido en la misma tanda: antes se pasaba `fs=250.0` fijo para
    TODOS los canales, incluido SpO2 -- que `generate_demo_spo2_signal()`
    genera a 1Hz de verdad (`n_samples = int(duration)`, ver su docstring).
    Ese desajuste de `fs` hacía que `MultisensoralRecord._validate_
    synchronization()` viera una "duración" de SpO2 ~250x más corta que el
    resto y la rellenara con ceros hasta igualar -- diluyendo `spo2_mean` a
    ~0.4% en vez de ~98%. Verificado por ejecución directa (no por lectura,
    lección de Respiratory Lab), ya afectaba a Clínica/IA antes de esta
    tanda -- no es un bug nuevo, es uno que nadie había verificado por
    ejecución hasta ahora."""
    fs_by_channel = {'SpO2': 1.0}  # generate_demo_spo2_signal es 1 muestra/segundo; el resto, 250Hz
    return MultisensoralRecord(
        [
            BiosignalChannel(
                name, sig, fs_by_channel.get(name, 250.0),
                unit='mV' if name == 'ECG' else '%', signal_type=name.lower(),
            )
            for name, sig in channels.items()
        ],
        patient_id='DEMO',
    )


def render_multisensor_page() -> None:
    render_module_header("Multisensor Fusion Lab", icon="🔗")
    _, _, _, _, _ = safe_import_ecg_modules()
    _, src_ok = safe_import_src_modules()
    BiosignalChannel, MultisensoralRecord, multisensor_ok = safe_import_multisensor()

    demo_channels = {
        # Fase 5B (2026-08-30): DynamicECGGenerator (McSharry 2003) --
        # reemplaza a generate_demo_ecg_signal(), ver CHANGELOG.md.
        'ECG': DynamicECGGenerator(fs=250).generate(duration=20, hr=72),
        'PPG': generate_demo_ppg_signal(250, 20),
        'SpO2': generate_demo_spo2_signal(250, 20),
        'Respiration': generate_demo_respiration_signal(250, 20),
    }

    # NOTA (2026-07-03): "Gemelo Digital" se eliminó de este laboratorio — el
    # gemelo real ya existe en Digital Twin OS; esta pestaña era un "Perfusion
    # Proxy" (promedio crudo de PPG), desconectado de ese gemelo real.
    view = render_view_selector(views=['Clínica', 'Educativa', 'Investigación', 'IA', 'Simulación'])

    if view == 'Clínica':
        st.markdown('### Vista Clínica')
        record = _build_multisensor_record(demo_channels, BiosignalChannel, MultisensoralRecord)
        indices = record.compute_physiological_indices()
        health = record.health_score()
        st.write('Vista integrada de signos vitales y perfusión')
        render_metric_explained('Health Score', f"{health['overall']:.1f}", unit='/100',
                    meaning='Índice agregado de estado fisiológico multisensor.',
                    importance='Sirve para priorizar intervenciones y monitoreo.',
                    affects='Variaciones en ECG, PPG, SpO2 y respiración.',
                    relations='Resume interacciones entre sistemas cardiovasculares y respiratorios.')
        render_metric_explained('Heart Rate', f"{indices['heart_rate']:.0f}", unit='bpm')
        render_metric_explained('SpO2', f"{indices['spo2_mean']:.1f}", unit='%')
        st.write('Qué significa: índice agregado de bienestar fisiológico. Por qué importa: prioriza intervenciones.')
        render_scientific_discovery_layer(demo_channels)

    elif view == 'Educativa':
        st.markdown('### Vista Educativa')
        st.write('Interactivo multisensor: seleccione canales para aprender sobre acoplamiento cardiorrespiratorio y oxigenación.')
        ch = st.multiselect('Canales', list(demo_channels.keys()), default=['ECG','SpO2'])
        for c in ch:
            st.line_chart(demo_channels[c])

    elif view == 'Investigación':
        st.markdown('### Vista Investigación')
        st.write('Exporta registros sincronizados y calcula correlaciones avanzadas.')
        if st.button('Exportar multisensor para investigación'):
            p = export_lab_report('Multisensor Research', {'channels': list(demo_channels.keys())}, notes='Multisensor export')
            if p:
                st.success(f'Exportado: {p}')

    elif view == 'IA':
        st.markdown('### Vista IA — Narrador clínico')
        record = _build_multisensor_record(demo_channels, BiosignalChannel, MultisensoralRecord)
        indices = record.compute_physiological_indices()
        health = record.health_score()
        render_findings_narrator('Multisensor Fusion Lab', [
            ('health_score', f"{health['overall']:.1f}/100", 'Índice agregado de estado fisiológico, combinando ECG, PPG, SpO2 y respiración.'),
            ('heart_rate_bpm', f"{indices['heart_rate']:.0f}", 'Frecuencia cardíaca estimada del canal ECG.'),
            ('spo2_pct', f"{indices['spo2_mean']:.1f}%", 'Saturación de oxígeno promedio del canal SpO2.'),
        ])

    elif view == 'Simulación':
        st.markdown('### Vista Simulación')
        st.write('Ajusta HR y SpO2 y observa cómo cambia el Health Score en vivo. RR se muestra pero está deshabilitado (razón debajo).')

        # Cableado real (2026-08-20, Capa 2 Fase 2.2, Art. I): originalmente
        # estos 3 sliders no alimentaban ningún cálculo -- render_discovery_lab
        # corría sobre demo_channels sin modificar, y el texto afirmaba un
        # recálculo en tiempo real que no ocurría. Se cablearon los 3 a la
        # misma ruta de cálculo compartida (_build_multisensor_record ->
        # compute_physiological_indices/health_score) que ya usan Clínica/IA.
        # Cierre (2026-08-21, Capa 2 Fase 2.2, Ejecución 1 cierre): tras
        # cablear, verificado por ejecución que SpO2 sí mueve el Health Score
        # pero HR y RR no -- HR porque generate_demo_ecg_signal() calculaba
        # hr_rad/qrs_component a partir de `hr` y nunca los usaba (la forma
        # de onda dependía de un ciclo fijo t % 1); RR porque health_score()
        # nunca consumió respiration_rate en su fórmula (sigue así, sin
        # cambios en esta tanda).
        #
        # Reactivado (Fase 5B, 2026-08-30): el generador de ECG se reemplazó
        # por DynamicECGGenerator (McSharry 2003, ver CHANGELOG.md) -- ya
        # respeta `hr` (validado por TKEO). `health_score()` SÍ consumía
        # `heart_rate` desde siempre (línea `if 'heart_rate' in indices:
        # ...scores['cardiovascular']...`, `dashboards/multisensor.py`) --
        # el cálculo era real, solo estaba bloqueado por el generador
        # mintiendo sobre el HR real de la señal. RR sigue deshabilitado --
        # esa razón (`health_score()` no usa `respiration_rate`) no cambió.
        hr = st.slider('HR', 40, 160, 72)
        spo2 = st.slider('SpO2', 80, 100, 96)
        rr = st.slider(
            'RR', 8, 30, 16, disabled=True,
            help='Deshabilitado: no incluido en el cálculo actual de Health Score (health_score() no usa respiration_rate).',
        )

        sim_channels = {
            # Fase 5B (2026-08-30): DynamicECGGenerator -- ver CHANGELOG.md.
            'ECG': DynamicECGGenerator(fs=250).generate(duration=20, hr=hr),
            'PPG': generate_demo_ppg_signal(250, 20, hr=hr),
            'SpO2': generate_demo_spo2_signal(250, 20, baseline=spo2),
            'Respiration': generate_demo_respiration_signal(250, 20, rr=rr),
        }
        sim_record = _build_multisensor_record(sim_channels, BiosignalChannel, MultisensoralRecord)
        sim_indices = sim_record.compute_physiological_indices()
        sim_health = sim_record.health_score()

        col_hr, col_spo2, col_health = st.columns(3)
        col_hr.metric('Heart Rate (detectado del ECG)', f"{sim_indices.get('heart_rate', 0):.0f} bpm")
        col_spo2.metric('SpO2 (recalculado)', f"{sim_indices.get('spo2_mean', 0):.1f} %")
        col_health.metric('Health Score (recalculado)', f"{sim_health['overall']:.1f} /100")

        st.caption(
            '**HR y SpO2 son controles activos de esta pestaña**: recalculan el Health Score de verdad, '
            'en el mismo instante en que mueves cada slider (misma ruta de cálculo que la Vista Clínica: '
            '`compute_physiological_indices()` + `health_score()` sobre señales ECG/SpO2 regeneradas). '
            'HR se reactivó en la Fase 5B (2026-08-30, ver CHANGELOG.md) al reemplazar el generador de '
            'ECG. **RR sigue deshabilitado** -- `health_score()` no consume `respiration_rate` en su '
            'fórmula, así que dejarlo arrastrable sería un control placebo; muestra la razón exacta al '
            'pasar el cursor.'
        )

        render_discovery_lab('Multisensor Gemelo', sim_channels)


# NOTA (2026-07-03): la vieja render_respiratory_page() inline (un patrón fijo,
# RR crudo, sin apnea/AHI) fue eliminada — ver render_respiratory_lab_page()
# arriba, que delega al supermódulo real con análisis de apnea/AHI completo.


def _render_hrv_save_to_twin(sdnn: float, mean_nn: float, source: str) -> None:
    """Segundo lab de la integración estrecha (2026-08-24, Capa 2 Fase 2.4) --
    mismo molde que `respiratory_lab/pages.py::_render_save_to_twin()` (piloto
    ya verificado), aplicado al lado cardio-únicamente. Botón explícito, nunca
    automático. Fase 3 (2026-08-30): el bootstrap manual ya no existe --
    llama a `get_active_patient_id()`/`get_active_session_factory()`
    (`app/utils/patient_session.py`), el punto único de verdad que
    reemplazó la convención de copiar `twin_shell_ups_session_factory`/
    `twin_shell_ups_patient_id` en cada lab (decisión de alcance del piloto
    de Respiratory, ahora formalizada).

    Qué escribe -- solo lo real con destino confirmado (Paso 1 del recon
    cardiovascular): `hrv` mapeado desde `sdnn`, no RMSSD -- convención YA
    documentada en el repo (`domain/physiology/ml/risk_context.py`:
    "el UPS solo modela un 'hrv' genérico en ms -- se usa como proxy de
    SDNN"), no una decisión nueva. `heart_rate` mapeado desde `60000/mean_nn`
    -- derivado de la MISMA serie RR real, no fabricado. `rmssd`/`pnn50`/
    LF/HF no tienen slot en el schema -- no se escriben, no se fuerzan.

    Procedencia: `Provenance.SIMULACION` siempre -- ambas fuentes de este lab
    (RR manual pegado por el usuario, o RR demo generado con jitter) son
    entrada de demo/manual, nunca un sensor real verificado en el momento.
    `source_detail` incluye qué fuente (`source`) se usó.

    La raíz respiratoria (gate simétrico ya cerrado en el builder) hace su
    trabajo aquí sola: como `update_from_sensors()` solo recibe `"ecg"`, el
    dominio respiratorio del estado resultante queda vacío -- no hay pulmón
    fantasma que evitar a mano, espejo exacto de cómo Respiratory dejó
    cardiovascular vacío en su propio piloto."""
    st.markdown("#### 🔗 Guardar estado al gemelo")
    st.caption(
        "Escribe `heart_rate`/`hrv` reales (calculados de la serie RR de arriba -- `hrv` mapeado "
        "desde SDNN) al Unified Physiological State, bajo el mismo paciente que renderiza Digital "
        "Twin OS -- su corazón reaccionará a estos valores la próxima vez que abras esa página o "
        "pulses \"Sincronizar\" ahí. Procedencia: simulación (serie RR de demo/manual, no un sensor real)."
    )
    if st.button("💾 Guardar estado al gemelo", key="hrv_lab_save_to_ups"):
        from domain.physiology.state import Provenance, from_digital_twin_organism, save_state
        from app.engines.digital_twin_organism import DigitalTwinOrganism

        # Fase 3 (paciente único de sesión, 2026-08-30): ver el mismo
        # comentario en render_ecg_monitor_page() más arriba -- este era el
        # 2° de los 4 sitios que copiaban el bootstrap inline.
        session_factory = get_active_session_factory()
        patient_id = get_active_patient_id()

        heart_rate_bpm = 60000.0 / mean_nn
        organism = DigitalTwinOrganism()
        organism.update_from_sensors({
            "ecg": {
                "heart_rate": float(heart_rate_bpm),
                "hrv": float(sdnn),
            }
        })
        state = from_digital_twin_organism(
            organism, patient_id, provenance=Provenance.SIMULACION,
            source_detail=f"hrv_lab:sdnn_desde_serie_rr:fuente={source}",
        )
        with session_factory() as session:
            snapshot_id = save_state(session, state)

        st.success(f"Estado guardado al gemelo -- snapshot: {snapshot_id}")
        st.caption(
            f"cardiovascular: {len(state.cardiovascular.descriptors)} descriptores · "
            f"respiratory: {len(state.respiratory.descriptors)} descriptores "
            f"(vacío esperado -- este lab no envía dato respiratorio)"
        )


def render_hrv_page() -> None:
    render_module_header("HRV Analysis", icon="📈")
    st.markdown('Análisis de variabilidad de la frecuencia cardíaca con métricas tiempo-frecuencia y explanation clínica.')
    source = st.sidebar.radio('HRV Source', ['Demo (ECG-derived)','Manual RR series'], index=0)
    rr_ms = None
    if source == 'Manual RR series':
        txt = st.text_area('Pega RR intervals en ms separados por comas', '800,820,790,810,805')
        try:
            rr_ms = np.array([float(x.strip()) for x in txt.split(',') if x.strip()])
        except Exception:
            rr_ms = None
    else:
        hr = st.sidebar.slider('Demo HR (bpm)', 40, 140, 72)
        n = st.sidebar.slider('Duración (seg)', 30, 300, 120)
        mean_rr = 60000.0 / float(max(30, hr))
        beats = int(max(10, (n * hr) // 60))
        rr_ms = mean_rr + np.random.normal(0, mean_rr * 0.03, size=beats)

    if rr_ms is None or len(rr_ms) < 5:
        render_error_state('RR series insuficiente -- provee más latidos o usa la fuente demo.')
        return

    diffs = np.diff(rr_ms)
    sdnn = float(np.std(rr_ms, ddof=1))
    rmssd = float(np.sqrt(np.mean(diffs**2))) if len(diffs) > 0 else 0.0
    pnn50 = float(np.sum(np.abs(diffs) > 50) / max(1, len(diffs)) * 100)
    mean_nn = float(np.mean(rr_ms))

    st.markdown('### Vista Clínica')
    render_metric_explained('SDNN', f'{sdnn:.1f}', unit='ms',
                meaning='Desviación estándar entre intervalos NN (variabilidad global).',
                importance='Indicador general de variabilidad autonómica.',
                affects='Estrés, edad, enfermedades cardiacas y medicamentos.',
                relations='Relacionada con RMSSD y balance autonómico.',
                consequences='Bajos valores asociados a mayor riesgo cardiovascular.')
    render_metric_explained('RMSSD', f'{rmssd:.1f}', unit='ms',
                meaning='Root mean square of successive differences — parasympathetic tone proxy.')
    render_metric_explained('pNN50', f'{pnn50:.1f}', unit='%',
                meaning='Porcentaje de diferencias NN>50ms — indicador vagal.')

    st.divider()
    _render_hrv_save_to_twin(sdnn, mean_nn, source)

    render_scientific_discovery_layer({'RR_ms': rr_ms})

    freqs = None
    lf_power = None
    hf_power = None
    try:
        t = np.cumsum(rr_ms) / 1000.0
        t = t - t[0]
        fs_interp = 4.0
        ti = np.arange(0, t[-1], 1.0/fs_interp)
        rr_interp = np.interp(ti, t, rr_ms)
        from scipy.signal import welch
        f, pxx = welch(rr_interp - np.mean(rr_interp), fs=fs_interp, nperseg=min(256, len(rr_interp)))
        lf_mask = (f >= 0.04) & (f < 0.15)
        hf_mask = (f >= 0.15) & (f <= 0.4)
        lf_power = float(np.trapz(pxx[lf_mask], f[lf_mask])) if np.any(lf_mask) else 0.0
        hf_power = float(np.trapz(pxx[hf_mask], f[hf_mask])) if np.any(hf_mask) else 0.0
        lf_hf = lf_power / hf_power if hf_power > 0 else None
        st.markdown('### Vista Investigación — Espectro HRV')
        if PLOTLY_OK:
            fig = PLOTLY_GO.Figure()
            fig.add_trace(PLOTLY_GO.Scatter(x=f, y=pxx, mode='lines', name='PSD'))
            fig.update_layout(template='plotly_dark', height=320, xaxis_title='Hz', yaxis_title='Power')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.line_chart(pxx)
        st.write(f'LF: {lf_power:.3f} — HF: {hf_power:.3f} — LF/HF: {lf_hf if lf_hf is not None else "n/a"}')
    except Exception:
        st.info('No se pudo calcular espectro HRV; faltan scipy o datos suficientes.')

    # NOTA (2026-07-03): "Gemelo Digital" se eliminó de este laboratorio — el
    # gemelo real ya existe en Digital Twin OS; esta pestaña era un "Autonomic
    # Balance" ad-hoc, desconectado de ese gemelo real.
    view = render_view_selector(views=['Clínica', 'Educativa', 'Investigación', 'IA', 'Simulación'])
    if view == 'Educativa':
        st.markdown('### Vista Educativa — ¿Qué afecta la HRV?')
        st.write('- Vagal tone increments raise RMSSD and pNN50.')
        st.write('- Chronic disease and age tend to lower SDNN.')
        st.line_chart(rr_ms)
    elif view == 'IA':
        st.markdown('### Vista IA — Narrador clínico')
        findings = [
            ('sdnn_ms', f'{sdnn:.1f} ms', 'Desviación estándar de los intervalos NN — variabilidad global.'),
            ('rmssd_ms', f'{rmssd:.1f} ms', 'Root mean square de diferencias sucesivas — proxy de tono parasimpático.'),
            ('pnn50_pct', f'{pnn50:.1f}%', 'Porcentaje de diferencias NN mayores a 50ms — indicador vagal.'),
        ]
        if lf_power is not None and hf_power is not None:
            findings.append((
                'lf_hf_ratio',
                f'{(lf_power / hf_power):.2f}' if hf_power > 0 else 'n/a',
                'Razón de potencia espectral de baja (LF) a alta frecuencia (HF) — proxy de balance simpático/vagal.',
            ))
        render_findings_narrator('HRV Analysis', findings)
    elif view == 'Simulación':
        st.markdown('### Vista Simulación')
        st.write('Ajusta variabilidad y observa efectos en índices (sterile demo).')
        var = st.slider('Variabilidad (SD%)', 0.0, 10.0, 3.0)
        sim_rr = mean_nn + np.random.normal(0, mean_nn * var/100.0, size=len(rr_ms))
        st.line_chart(sim_rr)



# Fase 4 (2026-08-30, ver CHANGELOG.md): render_education_page() y
# render_guides_page() se retiraron -- diagnóstico de rescate (Paso 0)
# confirmó que no había nada único que salvar en ninguna de las dos:
#
# Education (🎓) era, en su totalidad, o bien redirección honesta a
# contenido que YA vive en Academia (el quiz real, la tabla de 12
# derivaciones, el Narrador Clínico), o bien fachada -- más de la que el
# recon original había nombrado: además de las 4 tarjetas "🚧 en
# desarrollo" y el selectbox de 3 diagnósticos fijos (placebo, sin ningún
# dato real detrás), las vistas "Investigación"/"Simulación" y las
# secciones "1. Datos"/"2. Interpretación"/"5. Investigación"/"Tutor de
# ruta de aprendizaje" eran cada una una sola frase describiendo una
# capacidad ("BIOCORE AI sugiere rutas de estudio...") que nunca se
# construyó -- el mismo patrón de fachada que 2.2 ya había limpiado en
# pestañas vacías, aquí disfrazado de párrafo en vez de pestaña muda.
#
# Guides (📚) resultó más obsoleto de lo esperado, no solo "documentación
# vieja": su bullet de Clinical Hub listaba 3 de los 8+ módulos reales
# actuales (ECG/Multisensor/Respiratory -- faltaban EEG/EMG/HRV/
# Biomarkers/Patient Pipeline), y mencionaba "cursos" en Learning Hub que
# nunca existieron como tales. La sección "Roles" describía capacidades
# (Investigador: "exporta datos, compara cohortes"; Médico: "monitoreo
# integrado... IA explicable") sin ningún feature real detrás -- no es el
# toggle real Estudiante/Clínico/Investigador de Digital Twin OS, es un
# texto aspiracional aparte. El botón "Abrir onboarding rápido" no activaba
# ningún flujo -- solo reescribía `mission_goal`, una variable que ningún
# otro módulo leía (confirmado por grep), para volver a mostrarla en la
# misma página. Corregirlo bien habría sido escribir una guía nueva, no
# actualizar la existente -- fuera del alcance de esta tanda (autoría de
# contenido, no limpieza de fachadas).
#
# El Learning Hub queda = Academia Clínica (`HUBS["Learning Hub"]`, arriba)
# -- el único contenido educativo real, sin tocar.


# Fusión de navegación, Research Hub (2026-07-14): render_ai_analysis_page()
# se eliminó — confirmado antes de borrar que era exactamente un título más
# un st.info() de disclaimer (Auditoría Art. I, 2026-07-03: el 'Confidence
# Score' era un literal fijo, la capa de 'descubrimiento' corría sobre
# ruido puro, y cada pestaña afirmaba análisis — CNN, SHAP/LIME, hipótesis
# causales — que nunca se ejecutaban; ya se había vaciado a un cartel
# honesto de redirección). Cero lógica, cero widgets, nada que perder. El
# propio Research Hub que lo contenía también se eliminó del menú — su
# único contenido real, Patient Pipeline, se reubicó a Clinical Hub.


def render_patient_pipeline_page() -> None:
    """Fusión de persistencia, Paso 2 (2026-07-15): reescrita sobre el UPS
    real, reemplazando `app.clinical_db` (retirado del flujo vivo — ver
    import de módulo, línea ~54). Antes, "guardar estado" era un dropdown
    de 3 diagnósticos fijos sin ningún dato fisiológico detrás. Ahora:

    - Vista Clínica arma un estado real (`DigitalTwinOrganism` +
      `from_digital_twin_organism` + `save_state`, exactamente el mismo
      pipeline que ya usan Twin OS y Academia — sin lógica nueva) y permite
      emitir sobre ese snapshot una `ClinicalImpression` (categoría +
      notas) — un juicio humano, nunca mezclado con los descriptores
      medidos/derivados (ver `domain/physiology/state/clinical_impression.py`
      para por qué ese tipo no lleva provenance/confidence).
    - Vista IA narra el estado real Y la impresión humana asociada, con
      esta última anclada explícitamente como juicio humano — no medición
      — en el `Finding` que se le pasa al narrador."""
    import pandas as pd  # local, mismo criterio que _ecg_create_reproducible_notebook() más arriba

    render_module_header("Patient Pipeline", icon="👥")
    st.markdown('Estado fisiológico real del UPS + impresión clínica humana sobre ese estado, narrados por separado.')

    # Fase 3 (paciente único de sesión, 2026-08-30): Patient Pipeline ya NO
    # tiene su propio session_factory ni su propio mecanismo de "cambiar de
    # paciente por etiqueta" -- ese vestigio (`create_patient(display_name=
    # etiqueta)` en cada cambio de input, sin find-or-create) creaba un
    # paciente NUEVO cada vez que la etiqueta cambiaba, perdiendo
    # continuidad en silencio (ver CHANGELOG.md). Ahora opera sobre el
    # mismo paciente único de la sesión que Twin OS/ECG/HRV/Respiratory.
    #
    # El input de abajo se conserva -- no se retira la affordance -- pero
    # pasa a ser COSMÉTICO: renombra al paciente único activo
    # (`rename_active_patient()`), nunca crea uno nuevo. Por eso también
    # cambia de "ID de paciente" a "Nombre del paciente" -- el texto viejo
    # sugería una identidad que el campo nunca cambiaba de verdad de forma
    # segura; el nuevo nombre describe lo que el campo realmente hace.
    session_factory = get_active_session_factory()
    patient_id = get_active_patient_id()
    patient_label = st.text_input(
        'Nombre del paciente', get_active_patient_display_name(), key="patient_pipeline_patient_label",
        help="Cosmético: renombra al paciente único de esta sesión (el mismo que ven Twin OS/ECG Lab/"
             "HRV/Respiratory Lab). No crea un paciente nuevo ni cambia de identidad.",
    )
    if patient_label != get_active_patient_display_name():
        rename_active_patient(patient_label)

    view = render_view_selector(views=['Clínica', 'IA'])

    if view == 'Clínica':
        st.markdown('### Vista Clínica')
        st.caption(f"Paciente UPS: `{patient_id}` (nombre: {patient_label})")

        st.markdown('#### Registrar estado fisiológico')
        hr = st.slider('Frecuencia cardíaca (bpm)', 40, 180, 72, key="patient_pipeline_hr")
        rr = st.slider('Frecuencia respiratoria (resp/min)', 8, 40, 16, key="patient_pipeline_rr")
        spo2 = st.slider('SpO₂ (%)', 70, 100, 98, key="patient_pipeline_spo2")
        if st.button('Guardar nuevo estado', key="patient_pipeline_save_state"):
            organism = DigitalTwinOrganism()
            organism.update_from_sensors({
                "ecg": {"heart_rate": hr},
                "respiratory": {"respiratory_rate": rr, "spo2": spo2},
            })
            state = from_digital_twin_organism(
                organism, patient_id, provenance=Provenance.SIMULACION,
                source_detail="patient_pipeline:entrada_manual",
            )
            with session_factory() as session:
                snapshot_id = save_state(session, state)
            st.success(f'Estado guardado — snapshot: {snapshot_id}')
            # Sin st.rerun(): el estado se vuelve a consultar más abajo en
            # esta misma pasada (línea siguiente), así que ya se muestra
            # actualizado sin descartar este mensaje de éxito.

        with session_factory() as session:
            latest_state = get_latest_state(session, patient_id)
            latest_snapshot_id = get_latest_snapshot_id(session, patient_id)

        if latest_state is None:
            render_empty_state(
                "Sin ningún estado guardado todavía para este paciente",
                action='ajusta los controles y pulsa "Guardar nuevo estado"',
            )
        else:
            st.markdown('#### Estado más reciente (real, del UPS)')
            desc_rows = [
                {
                    "Dominio": domain_state.domain,
                    "Descriptor": d.name,
                    "Valor": f"{d.value:.1f} {d.unit}",
                    "Procedencia": d.provenance.value,
                    "Confianza": f"{d.confidence:.0%}",
                }
                for domain_state in latest_state.all_domains().values()
                for d in domain_state.descriptors.values()
            ]
            st.dataframe(pd.DataFrame(desc_rows), use_container_width=True, hide_index=True)

            if latest_state.events:
                st.markdown('**Eventos detectados:**')
                for evt in latest_state.events:
                    icon = "🔴" if evt.severity == EventSeverity.CRITICAL else "🟡"
                    st.caption(f"{icon} `{evt.event_type.value}` — {evt.description}")

            st.markdown('#### Emitir impresión clínica sobre este estado')
            st.caption(
                "Juicio humano, no una medición — se guarda aparte de los descriptores, "
                "ligado a este snapshot exacto (no lleva confianza numérica: si hay "
                "incertidumbre, exprésala en las notas)."
            )
            category = st.selectbox(
                'Categoría', list(ImpressionCategory),
                format_func=lambda c: c.value.replace("_", " ").capitalize(),
                key="patient_pipeline_impression_category",
            )
            notes = st.text_area('Notas (opcional)', key="patient_pipeline_impression_notes")
            if st.button('Guardar impresión', key="patient_pipeline_save_impression"):
                with session_factory() as session:
                    create_clinical_impression(
                        session,
                        snapshot_id=latest_snapshot_id,
                        patient_id=patient_id,
                        category=category,
                        author="Usuario de Patient Pipeline",  # genérico -- TODO: integración real de usuarios pendiente
                        notes=notes or None,
                    )
                st.success('Impresión guardada.')
                # Sin st.rerun(): la lista de impresiones se vuelve a
                # consultar justo abajo, en esta misma pasada.

            with session_factory() as session:
                impressions = get_clinical_impressions_for_patient(session, patient_id)
            if impressions:
                st.markdown('**Impresiones clínicas guardadas para este paciente**')
                for imp in impressions:
                    with st.expander(f"{imp.category.value} — {imp.emitted_at.isoformat()} (autor: {imp.author})"):
                        st.write(imp.notes or "_(sin notas)_")

    else:  # view == 'IA'
        st.markdown('### Vista IA — Narrador clínico')
        with session_factory() as session:
            latest_state = get_latest_state(session, patient_id)

        if latest_state is None:
            render_empty_state(
                "No hay ningún estado guardado todavía para este paciente",
                action="guarda uno primero en la Vista Clínica para poder narrarlo aquí",
            )
        else:
            with session_factory() as session:
                latest_snapshot_id = get_latest_snapshot_id(session, patient_id)
                impressions = get_clinical_impressions_for_snapshot(session, latest_snapshot_id)

            findings = [
                (d.name, f"{d.value} {d.unit}", f"Dominio {domain_state.domain}, procedencia {d.provenance.value}, confianza {d.confidence:.0%}.")
                for domain_state in latest_state.all_domains().values()
                for d in domain_state.descriptors.values()
            ] + [
                (e.event_type.value, e.severity.value, e.description)
                for e in latest_state.events
            ]

            if impressions:
                for imp in impressions:
                    findings.append((
                        "Impresión clínica humana",
                        imp.category.value,
                        (
                            f"Juicio humano emitido por {imp.author} el {imp.emitted_at.isoformat()} — "
                            f"NO es una medición ni un cálculo, es una interpretación de una persona. "
                            f"Notas: {imp.notes or '(sin notas)'}"
                        ),
                    ))
            else:
                st.caption("Sin ninguna impresión clínica humana guardada todavía para este estado.")

            render_findings_narrator('Patient Pipeline', findings)

# Consolidación, Tanda 2 (2026-07-13): render_simulation_lab_page() (Simulation
# Hub) se eliminó — cáscara confirmada por la auditoría de valor: sliders sin
# persistencia, Vista Investigación exportaba un diccionario fijo ({'params':
# 'demo'}, ni siquiera los valores reales de los sliders), Vista IA ya vaciada
# en la Tanda 1. Su sustancia real (12 escenarios de SimulationEngine) se había
# movido por completo a Twin OS en la Tanda 3 (render_ups_scenario_simulator())
# — verificado sin ningún código compartido entre ambos antes de borrar. El
# simulador real sigue intacto, sin tocar, en Digital Twin OS.


# Consolidación, Tanda 4 (2026-07-13): render_hardware_ops_page() (Hardware
# Hub) se eliminó — confirmado antes de borrar que no contenía ninguna lógica
# de conexión/instanciación de hardware real: su único contacto con
# EMGStreamer era un chequeo booleano de solo lectura (`is not None`) sobre la
# referencia ya importada al inicio de este archivo — esa importación, y las
# conexiones reales que sí la usan (render_emg_page(), y ESP32SignalSource en
# render_ecg_monitor_page() y en twin_shell/pages.py), no se tocaron. La
# página no centralizaba nada: cada laboratorio (ECG Monitor, EMG Muscle Lab,
# EEG Neuro Lab, Digital Twin OS) ya gestiona su propia conexión de hardware
# real de forma independiente, sin pasar por aquí.


# Consolidación, Tanda 3 (2026-07-13): render_jarvis_copilot_page() (AI Hub) se
# eliminó — no tenía ninguna lógica propia, solo reutilizaba
# init_session()/render_clinical_narrator() de twin_shell/pages.py para
# exponer el mismo narrador por una segunda puerta (confirmado antes de
# borrar: cero pérdida de función). El narrador real, sin cambios, sigue
# viviendo en Digital Twin OS → "🧭 Herramientas avanzadas" →
# "🩺 Narrador clínico (IA real)".


def main() -> None:
    init_state()
    inject_biocore_css()
    
    st.sidebar.markdown("## ECOSISTEMA BIOCORE AI")
    selected_hub = st.sidebar.radio('Selecciona un hub', list(HUBS.keys()), index=list(HUBS.keys()).index(st.session_state.selected_hub), label_visibility='hidden')
    if selected_hub != st.session_state.selected_hub:
        st.session_state.selected_hub = selected_hub
        st.session_state.selected_page = HUBS[selected_hub][0]
    
    st.sidebar.caption(f"📂 Módulo dentro de **{st.session_state.selected_hub}**:")
    selected_page = st.sidebar.selectbox('Selecciona un módulo', HUBS[st.session_state.selected_hub], index=HUBS[st.session_state.selected_hub].index(st.session_state.selected_page), label_visibility='collapsed')
    st.session_state.selected_page = selected_page
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Control universal:**")
    # Consolidación, Tanda 3 (2026-07-13): antes este bullet no decía dónde
    # vivía el Narrador Clínico (implícitamente, el ahora eliminado AI Hub).
    # Se deja explícito para no perder capacidad de descubrimiento.
    st.sidebar.markdown("- 🩺 Narrador Clínico → Digital Twin OS")

    st.sidebar.markdown("---")
    st.sidebar.markdown("**Modo plataforma:** \nLaboratorio biomédico, clínica, investigación y simulación.")

    if st.session_state.selected_page:
        render_page_content(st.session_state.selected_page)

if __name__ == '__main__':
    main()
