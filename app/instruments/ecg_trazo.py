"""Instrumento «trazo del ECG» (T2, 2026-11-18): la fuente, el trazo en papel ECG, la FC medida y la compuerta de
guardado del Monitoreo.

El código se movió tal cual desde `render_ecg_monitor_page()` de `app/main.py` y sus funciones privadas: ningún
cálculo, texto, cita ni compuerta cambió. La pestaña Monitoreo es ahora `render(PAGE)` más lo que es de la página (el
detalle del caso y las secciones plegadas); una estación de la ruta lo monta con `station_context(prefijo)`.

En una estación no se ofrece «Hardware ESP32 en vivo»: su panel vive en el menú lateral con claves fijas y la placa es
una sola por computadora (`sources`)."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import numpy as np
import streamlit as st

from app.instruments.base import PAGE, InstrumentContext
from app.instruments.common import CSV_SAVE_BLOCKER, render_metric_explained
from app.supermodules import safe_import_ecg_modules, safe_import_src_modules, validate_signal
from app.utils.design_system import render_empty_state, render_error_state, render_no_data
from app.utils.patient_banner import active_source_label, read_active_vitals, vital_provenance_text
from app.utils.patient_session import get_active_patient_id, get_active_session_factory
from clinical.calculators import news2_reading_note
from domain.physiology.narrator.privacy import DataOrigin
from src.signals.ecg.dynamic_ecg_generator import DynamicECGGenerator

ECG_DEMO_FS = 500   # muestras/s de la demo: lo que pide [K2007] para un corte de 150 Hz con error de amplitud < 1 %


# Ganancia de la tira por fuente: solo es «10 mm/mV» si la amplitud está en mV.
_ECG_GAIN_NOTES = {
    'CSV local': 'unidades del archivo, no verificadas en mV',
    'Hardware ESP32 en vivo': 'mV aproximados: ganancia del AD8232 y ADC sin calibrar',
}


def _ecg_monitor_filter_label(source: str) -> str:
    """Qué filtro tiene la señal que se dibuja (Parte A): la placa en vivo pasa por el filtro de monitoreo de
    `hardware/ecg_plugplay` (0.5–40 Hz y 60 Hz); las demás fuentes se dibujan tal como vienen."""
    from app.utils import ecg_paper

    if source == 'Hardware ESP32 en vivo':
        return ecg_paper.MONITOR_FILTER_LABEL + " y notch de 60 Hz"
    return ecg_paper.NO_FILTER_LABEL


_ECG_SOURCE_ORIGIN = {
    'Demo (sintético)': 'simulado', 'Caso clínico (61 disponibles)': 'simulado',
    'Base de datos MIT-BIH': 'base_publica', 'Base de datos PTB-XL': 'base_publica',
}


def _ecg_data_origin(source: str, metadata: dict) -> 'DataOrigin':
    """De dónde vienen los datos del Monitoreo del ECG Lab, para el narrador (`privacy.py`). Los 61 casos clínicos
    son sintéticos; MIT-BIH y PTB-XL son bases públicas anonimizadas; un CSV no se sabe de quién es."""
    if source == 'Hardware ESP32 en vivo':
        label = str((metadata or {}).get('source', ''))
        return DataOrigin.PERSONA if 'SENSOR_REAL' in label else (
            DataOrigin.SIMULADO if 'SIMULACIÓN' in label else DataOrigin.DESCONOCIDO)
    return DataOrigin(_ECG_SOURCE_ORIGIN.get(source, 'desconocido'))


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

    # 2026-11-16 (Art. I): antes los 61 casos dependían del estado de `np.random` global en el momento de construirlos,
    # así que «el mismo caso» cambiaba de una ejecución a otra (y una prueba dependía del orden). Semilla fija y se
    # devuelve el estado global como estaba: el resto de la app no nota la diferencia.
    previous = np.random.get_state()
    np.random.seed(CASE_DATABASE_SEED)
    try:
        return build_complete_case_database()
    finally:
        np.random.set_state(previous)


CASE_DATABASE_SEED = 0


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


def _measure_ecg_heart_rate_tkeo(signal: np.ndarray, fs: float, ECGAnalyzerCls) -> Optional[float]:
    """Bug 2 del ECG (2026-09-26, ver CHANGELOG.md) -- fuente única de
    medición de HR para `render_ecg_monitor_page()`, consolidada sobre
    `ECGAnalyzer.detect_r_peaks_tkeo()` (banda 5-15Hz + energía
    Teager-Kaiser + refractario, 6 rondas de validación con el experto) en
    vez de la vieja `estimate_ecg_heart_rate()` (naive, sin distancia
    mínima -- contaba el par R+T del mismo latido como dos latidos, saturaba
    en 220bpm). Antes de esta tanda solo la fuente demo usaba TKEO; las
    fuentes de señal REAL (MIT-BIH/PTB-XL/CSV/hardware) seguían con el
    detector roto -- un HR de 220 sobre un ECG de paciente real, no solo
    sobre una demo sintética. Ahora las 6 fuentes de `render_ecg_monitor_page()`
    pasan por esta misma función.

    Devuelve `None` (no un número de relleno) cuando no hay detección
    fiable -- ECGAnalyzer no disponible en el entorno, o menos de 2 picos
    R encontrados (señal demasiado corta, sin QRS reconocible en la banda
    5-15Hz, o ritmo no evaluable). El llamador declara "no disponible" con
    el motivo, nunca sustituye por un valor inventado (Art. I).

    Error medido en vivo contra `DynamicECGGenerator` con hr conocido:
    0.00-0.12bpm en el rango 40-200bpm (ver
    tests/test_ecg_hr_detector_consolidation.py -- el mismo banco que ya
    validó el generador en Fase 5B sirve, sin modificar, como banco de
    regresión de este detector)."""
    if ECGAnalyzerCls is None:
        return None
    peaks = ECGAnalyzerCls(fs=fs).detect_r_peaks_tkeo(signal)
    if len(peaks) < 2:
        return None
    return float(60.0 * fs / np.mean(np.diff(peaks)))


ECG_CSV_SOURCE_LABEL = "CSV local (archivo cargado)"

# Fuente «Paciente activo» del Monitoreo (integración, 2026-11-17): el trazo se GENERA a la FC que el UPS ya tiene del
# paciente activo, para que el banner y el ECG digan el mismo número. El UPS guarda la FC, no la onda: la onda es una
# vista determinista de ese valor (`DynamicECGGenerator`, sin ruido: la misma FC da siempre el mismo trazo).
ECG_PATIENT_SOURCE = 'Paciente activo (simulación a su FC)'
ECG_PATIENT_SOURCE_LABEL = 'simulación a la FC del paciente activo (UPS)'
ECG_SOURCE_KEY = 'ecg_monitor_source'
# Rango en que la FC del generador está validada con el detector TKEO (error < 0.2 lpm; ver el comentario de la demo).
ECG_GENERATOR_VALIDATED_HR = (40, 200)
# Un escenario de arritmia NO se dibuja desde la FC sola: un ritmo sinusal regular sería una onda falsa (Art. I).
# Marcas (en minúsculas) con que el gemelo rotula su fuente activa cuando aplica una arritmia
# (`twin_shell.pages`: «arritmia …» o «escenario del simulador 🫀 Fibrilación auricular …», `RICH_SCENARIO_LABELS`).
ECG_RHYTHM_NOT_MODELED_MARKS = ('arrhythmia', 'arritmia', 'fibrilación auricular', 'flutter auricular',
                                'taquicardia supraventricular', 'bradicardia sinusal')


def _ecg_from_active_patient():
    """(señal, fs, metadatos) del paciente activo, o `None` tras decir en pantalla por qué no hay trazo. Nunca inventa
    una FC: sin FC en el UPS, sin paciente, con un escenario de arritmia o fuera del rango validado, es «sin dato»."""
    vitals = read_active_vitals()
    if vitals.patient_id is None:
        render_no_data('Paciente activo', 'todavía no hay paciente: abre el Gemelo digital o guarda un estado desde un '
                                          'laboratorio para crearlo')
        return None
    hr = vitals.values['hr']
    if hr is None:
        render_no_data('Frecuencia cardíaca del paciente activo',
                       'el UPS aún no tiene FC de este paciente: aplica un escenario o guarda un estado en el Gemelo digital')
        return None
    origin = f"{hr.source_detail or ''} {active_source_label()}".lower()
    if any(mark in origin for mark in ECG_RHYTHM_NOT_MODELED_MARKS):
        render_no_data('Trazo del paciente activo',
                       'ritmo no modelado: la FC sola no describe un escenario de arritmia y un ritmo sinusal regular '
                       'sería una onda falsa. Usa un caso clínico para ver un ritmo con su trazo')
        return None
    lo, hi = ECG_GENERATOR_VALIDATED_HR
    if not lo <= hr.value <= hi:
        render_no_data('Trazo del paciente activo',
                       f'la FC del paciente ({hr.value:.0f} lpm) está fuera del rango en que el generador está validado '
                       f'({lo}–{hi} lpm)')
        return None
    signal = DynamicECGGenerator(fs=ECG_DEMO_FS).generate(duration=20, hr=float(hr.value))
    # T1.1: de qué guardado sale la FC del trazo (puede ser de otro momento que el último guardado del paciente).
    st.caption(f"Trazo simulado a la FC {hr.value:.0f} lpm del paciente activo · "
               f"{vital_provenance_text(hr, vitals.origins.get('hr'))}.")
    return signal, ECG_DEMO_FS, {'source': ECG_PATIENT_SOURCE_LABEL, 'patient_id': vitals.patient_id,
                                  'hr_ups': float(hr.value)}


def _render_ecg_save_to_twin(signal: np.ndarray, fs: float, metadata: dict, ECGAnalyzerCls,
                             ctx: InstrumentContext = PAGE) -> Optional[str]:
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
    precisamente de dónde vino, no solo la etiqueta genérica.

    T2 (2026-11-18): `ctx` da la clave del botón (con `PAGE`, la de siempre); devuelve el snapshot escrito o `None`."""
    st.markdown("#### 🔗 Guardar estado al gemelo")
    source_label = metadata.get('source', 'demo')

    # Contención (2026-11-16, Art. I): un CSV cargado no escribe al gemelo, con el mismo criterio y mensaje que el EMG.
    # Antes no escribía por accidente (sus metadatos no traían 'source' y caía en la rama demo) y la página le decía
    # al estudiante que la FC la había elegido él en un slider.
    if source_label == ECG_CSV_SOURCE_LABEL:
        st.button("💾 Guardar estado al gemelo", key=ctx.k("ecg_lab_save_to_ups"), disabled=True, help=CSV_SAVE_BLOCKER)
        st.warning(f"⛔ No se guarda al gemelo: {CSV_SAVE_BLOCKER}.")
        return

    if source_label == ECG_PATIENT_SOURCE_LABEL:
        st.info("Esta señal se generó a partir de la FC que el UPS ya tiene de este paciente: guardarla no añadiría "
                "ningún dato (sería escribir el mismo valor otra vez).")
        return

    if 'demo' in source_label.lower():
        st.info(
            "Fuente demo (sintética) -- nunca escribe HR al gemelo. El HR de esta fuente es un valor "
            "que TÚ elegiste en el slider, no algo medido de un paciente -- guardarlo confundiría "
            "'lo que pediste' con 'lo que se observó', aunque el generador ya sea fiel a ese valor "
            "(Fase 5B). Cambia a MIT-BIH, PTB-XL, un caso clínico o hardware ESP32 para guardar "
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
    if st.button("💾 Guardar estado al gemelo", key=ctx.k("ecg_lab_save_to_ups")):
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
        # C0 (2026-11-12, Art. I): la confianza que CALCULO el detector (`estimate_heart_rate_with_confidence`)
        # es la que se escribe, no el punto medio fijo de la banda (0.75) que ignoraba lo medido.
        state = from_digital_twin_organism(
            organism, patient_id, provenance=provenance, confidence=float(confidence),
            source_detail=f"ecg_lab:{source_label}",
        )
        with session_factory() as session:
            snapshot_id = save_state(session, state)

        st.success(
            f"Estado guardado al gemelo -- snapshot: {snapshot_id} "
            f"(FC={hr:.0f} lpm, confianza={confidence:.2f})"
        )
        st.caption(
            f"cardiovascular: {len(state.cardiovascular.descriptors)} descriptores · "
            f"respiratory: {len(state.respiratory.descriptors)} descriptores "
            f"(vacío esperado -- este lab no envía dato respiratorio)"
        )
        return snapshot_id
    return None



SOURCES = ['Demo (sintético)', 'CSV local', 'Caso clínico (61 disponibles)', 'Base de datos MIT-BIH',
           'Base de datos PTB-XL', 'Hardware ESP32 en vivo', ECG_PATIENT_SOURCE]
LIVE_SOURCE = 'Hardware ESP32 en vivo'


def sources(ctx: InstrumentContext) -> list:
    """Las fuentes del trazo. En una estación, sin la placa en vivo (ver el docstring del módulo)."""
    return [s for s in SOURCES if not (ctx.in_station and s == LIVE_SOURCE)]


@dataclass
class EcgTrace:
    """Lo que el instrumento dibujó: la señal y su procedencia, la FC medida (o `None`) y el snapshot guardado."""
    signal: np.ndarray
    fs: float
    metadata: Dict[str, Any]
    source: str
    hr: Optional[float]
    loaded_case: Any = None
    analyzer: Any = None
    saved_snapshot_id: Optional[str] = None
    src_modules: Dict[str, Any] = field(default_factory=dict)   # los módulos de `src` que ya se importaron
    src_ok: bool = False
    values: Dict[str, float] = field(init=False)

    def __post_init__(self):
        self.values = {} if self.hr is None else {"hr": float(self.hr)}


def render(ctx: InstrumentContext = PAGE) -> Optional[EcgTrace]:
    """El trazo de la fuente elegida, su FC y la compuerta de guardado. `None` si no hay trazo (el motivo ya está en
    pantalla). Con `PAGE`, controles en el menú lateral y las claves de siempre."""
    panel = ctx.panel
    ECGAnalyzer, create_clinical_ecg_figure, load_mitbih_record, get_mitbih_records, ecg_ok = safe_import_ecg_modules()
    src_modules, src_ok = safe_import_src_modules()

    # Integración: con un paciente que ya tiene FC en el UPS el Monitoreo abre en SU trazo (banner y ECG, el mismo
    # número); sin él, abre en la demo como siempre. Streamlit olvida la clave al salir de la página.
    source_key = ctx.k(ECG_SOURCE_KEY)
    if source_key not in st.session_state:
        st.session_state[source_key] = (
            ECG_PATIENT_SOURCE if read_active_vitals().values['hr'] is not None else 'Demo (sintético)')
    source = panel.radio('Origen del ECG', sources(ctx), key=source_key)
    signal = None
    fs = 250
    metadata = {}
    loaded_case = None

    if source == 'CSV local':
        uploaded = panel.file_uploader('Carga ECG local (CSV)', type=['csv'], key=ctx.auto_key('ecg_csv_upload'))
        if uploaded and src_ok and 'load_biomedical_signal' in src_modules:
            try:
                with open(os.path.join(tempfile.gettempdir(), uploaded.name), 'wb') as tmp:
                    tmp.write(uploaded.read())
                signal, fs, metadata = src_modules['load_biomedical_signal'](os.path.join(tempfile.gettempdir(), uploaded.name))
                metadata['source'] = ECG_CSV_SOURCE_LABEL       # antes faltaba y la página lo rotulaba «demo»
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
        panel.caption(f"📚 {case_db.count_cases()} casos disponibles, agrupados por diagnóstico.")
        diagnosis_options = sorted({c.primary_diagnosis.value for c in case_db.cases.values()})
        selected_diagnosis = panel.selectbox('Diagnóstico primario', diagnosis_options, key=ctx.auto_key('ecg_case_diagnosis'))
        matching_cases = sorted(
            (c for c in case_db.cases.values() if c.primary_diagnosis.value == selected_diagnosis),
            key=lambda c: c.case_id,
        )
        selected_case_id = panel.selectbox(
            'Caso específico',
            [c.case_id for c in matching_cases],
            format_func=lambda cid: next(
                f"{c.case_id} — {c.age}a {c.sex}, dificultad {c.difficulty.value}"
                for c in matching_cases if c.case_id == cid
            ),
            key=ctx.auto_key('ecg_case_id'),
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
            panel.warning(
                'El loader MIT-BIH no está disponible en este entorno (falta `wfdb` o '
                '`signals.loaders`). Usando demo.'
            )
        else:
            mitbih_records = get_mitbih_records()
            selected_mitbih = panel.selectbox('Registro MIT-BIH', mitbih_records, key=ctx.auto_key('ecg_mitbih_record'))
            if panel.button('Cargar registro MIT-BIH', key=ctx.auto_key('ecg_mitbih_load')):
                try:
                    loaded_signal, loaded_fs, mitbih_meta = load_mitbih_record(selected_mitbih)
                    st.session_state[ctx.k('_ecg_monitor_mitbih_cache')] = (
                        loaded_signal, loaded_fs,
                        {'source': f'MIT-BIH {selected_mitbih} (PhysioNet)', **mitbih_meta},
                    )
                except Exception as e:
                    st.session_state[ctx.k('_ecg_monitor_mitbih_cache')] = None
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
            cached_mitbih = st.session_state.get(ctx.k('_ecg_monitor_mitbih_cache'))
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
            panel.warning('No hay registros PTB-XL disponibles ahora mismo (ver error arriba).')
        else:
            selected_ptbxl = panel.selectbox(
                'Registro PTB-XL', ptbxl_records,
                format_func=lambda r: f"{r['ecg_id']} — {r['label']}",
                key=ctx.auto_key('ecg_ptbxl_record'),
            )
            if panel.button('Cargar registro PTB-XL', key=ctx.auto_key('ecg_ptbxl_load')):
                try:
                    loaded_signal, loaded_fs, ptbxl_meta = _ecg_load_ptbxl_record(selected_ptbxl['filename'])
                    st.session_state[ctx.k('_ecg_monitor_ptbxl_cache')] = (
                        loaded_signal, loaded_fs,
                        {'source': f"PTB-XL {selected_ptbxl['ecg_id']} ({selected_ptbxl['label']}, PhysioNet)", **ptbxl_meta},
                    )
                except Exception as e:
                    st.session_state[ctx.k('_ecg_monitor_ptbxl_cache')] = None
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
            cached_ptbxl = st.session_state.get(ctx.k('_ecg_monitor_ptbxl_cache'))
            if cached_ptbxl is not None:
                signal, fs, metadata = cached_ptbxl
            else:
                panel.info('Selecciona un registro y pulsa "Cargar" — se descarga en vivo desde PhysioNet.')

    elif source == ECG_PATIENT_SOURCE:
        generated = _ecg_from_active_patient()
        if generated is None:
            return None
        signal, fs, metadata = generated

    elif source == 'Hardware ESP32 en vivo':
        # ECG Plug & Play (2026-11-13, ver CHANGELOG; Art. I): reemplaza a la rama de
        # ESP32SignalSource, que tras desconectar el cable seguía diciendo SENSOR_REAL sobre un
        # búfer congelado y podía abrir un puerto Bluetooth. La placa se busca sola, el puerto se
        # cierra al desconectarse y la procedencia es SENSOR_REAL solo mientras una placa real
        # manda datos. Código en app/supermodules/ecg_live/ y hardware/ecg_plugplay/.
        from app.supermodules.ecg_live.monitor_source import render_live_source

        live = render_live_source()
        if live is not None:
            signal, fs, metadata = live

    if signal is None:
        hr_demo = panel.slider('FC demo (lpm)', 40, 140, 72, key=ctx.auto_key('ecg_demo_hr'))
        # Fase 5B (2026-08-30): DynamicECGGenerator (McSharry et al. 2003)
        # reemplaza a generate_demo_ecg_signal() -- ver
        # src/signals/ecg/dynamic_ecg_generator.py. El generador viejo
        # ignoraba `hr` (QRS con ciclo fijo `t % 1`); este respeta el HR
        # pedido (validado por TKEO, error <0.2bpm en todo el rango 40-200,
        # ver CHANGELOG.md).
        # Pulido profesional (2026-11-16): la demo se genera a 500 muestras/s, lo que pide [K2007] para un corte
        # superior de 150 Hz con error de amplitud < 1 % (antes 250).
        fs = ECG_DEMO_FS
        signal = DynamicECGGenerator(fs=fs).generate(duration=20, hr=hr_demo)
        metadata['source'] = 'demo'

    valid, msg = validate_signal(signal)
    if not valid:
        render_error_state(msg)
        return None

    # Pulido profesional (2026-11-16, Art. I): se retiró el selector «Capa de Exploración Cognitiva» (Clínica / Educativa /
    # Investigación / IA / Simulación). Una sola página: arriba el trazo en papel ECG y los valores clave; debajo, plegados,
    # «Cómo se calcula» (antes Investigación), «Teoría» (antes Educativa: el enlace a Aprender) y «Narración con IA
    # (opcional)» (antes IA). Cierre del pulido: «Simular» y el material de Educativa estaban rotulados «[Sin fuente]» (y
    # los controles de Simular no movían nada); se retiraron de la vista, su código queda sin montar en
    # `_ecg_monitor_unsourced_material()`.
    # Bug 2 del ECG (2026-09-26): las 6 fuentes miden con el mismo detector TKEO; `hr is None` se declara «no disponible».
    hr = _measure_ecg_heart_rate_tkeo(signal, fs, ECGAnalyzer)

    # ── 1. El trazo (papel ECG, 25 mm/s · 10 mm/mV) y los valores clave ──
    from app.utils import ecg_paper
    from app.supermodules.learn_theory import SIGNED_HEART_RATE

    duration_s = len(signal) / fs
    strip_start = 0.0
    if duration_s > ecg_paper.STRIP_S + 0.5:
        strip_start = st.slider('Inicio de la tira de 10 s (s)', 0.0, float(np.floor(duration_s - ecg_paper.STRIP_S)),
                                0.0, step=1.0, key=ctx.k('ecg_monitor_strip_start'))
    ecg_paper.render(ecg_paper.strip_figure(
        signal, fs, lead=str(metadata.get('lead') or 'ECG'), start_s=strip_start,
        filter_label=_ecg_monitor_filter_label(source),
        gain_note=_ECG_GAIN_NOTES.get(source),
    ), key=ctx.k('ecg_monitor_paper'))

    if hr is None:
        render_no_data(
            'Frecuencia cardíaca',
            'el detector TKEO no encontró suficientes picos R fiables en esta señal (señal corta, sin QRS '
            'reconocible en 5-15 Hz, ritmo no evaluable o motor ECGAnalyzer no disponible). Prueba con otra '
            'fuente o una señal más larga.',
        )
    else:
        # La explicación es el tema 2 firmado (docs/contenido/teoria_citada.md); las capas genéricas se retiraron.
        render_metric_explained('Frecuencia cardíaca', f'{hr:.0f}', unit='lpm', topic=SIGNED_HEART_RATE)
        st.caption(news2_reading_note(pulse=hr))     # integración: la FC siempre con sus puntos NEWS2 (misma tabla del gemelo)
    st.markdown(f"**Fuente:** {metadata.get('source', 'demo')}  |  **Muestreo:** {fs:g} Hz")

    st.divider()
    saved = _render_ecg_save_to_twin(signal, fs, metadata, ECGAnalyzer, ctx=ctx)
    return EcgTrace(signal=signal, fs=fs, metadata=metadata, source=source, hr=hr, loaded_case=loaded_case,
                    analyzer=ECGAnalyzer, saved_snapshot_id=saved, src_modules=src_modules, src_ok=src_ok)
