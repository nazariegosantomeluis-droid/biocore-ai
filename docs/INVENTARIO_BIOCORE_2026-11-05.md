# INVENTARIO TOTAL DE BIOCORE AI — 2026-11-05

Reconocimiento de **solo lectura** del clon activo `~/Downloads/biocore-public` (commit `cd693e6`, rama `main`). La fuente de verdad es el código ejecutándose; los documentos solo se usan para contrastar (sección 10).

**Procedencia.** Cada afirmación lleva su etiqueta: `[EJECUTADO]` (lo corrí y vi el resultado), `[LEÍDO EN CÓDIGO]` (leí la función/archivo, sin ejecutarlo), `[SEGÚN CHANGELOG/DOCS, NO VERIFICADO]`, `[NO PUDE VERIFICAR: motivo]`. En las tablas largas uso columna **Prov.** con `E` = EJECUTADO, `L` = LEÍDO EN CÓDIGO, `D` = SEGÚN CHANGELOG/DOCS NO VERIFICADO, `NV` = NO PUDE VERIFICAR.

**Clasificación de salidas:** REAL · HEURÍSTICO ETIQUETADO · SIMULADO DECLARADO · ROTO PERO HONESTO · FACHADA.

**Estado del repo durante el trabajo.** HEAD `cd693e6` (commit del usuario a las 16:25, durante esta sesión; antes el working tree traía ese trabajo sin commitear). Mientras corría, el usuario siguió editando (`simulation_engine.py`, `arrhythmia_types.py`, `twelve_lead_generator.py` y un test nuevo `test_ecg12_rhythm_labels.py` aparecieron sin commitear). La pasada de pytest #1 corrió sobre HEAD limpio; la #2 (cobertura) sobre ese working tree con ediciones ajenas. `[EJECUTADO]`

**Efectos laterales de mis pruebas (declaro todo):** (a) mis primeras pasadas de AppTest renderizaron páginas contra la base de desarrollo real `data/biocore_ups.db` (gitignored) y crearon pacientes "Paciente Demo" en ella; (b) a partir de ahí redirigí a una base temporal para todo lo que escribe; (c) mis clics de prueba generaron 7 archivos en `reports/` (PDF/HTML/PNG, gitignored) que **borré**; no queda nada mío en el repo salvo este informe. Los archivos `data/biocore_ups.db-shm/-wal` sin trackear los crea SQLite en modo WAL (los pudo crear mi corrida o tu uso previo; no los toqué). Cero cambios de código.

---

## VEREDICTO

BIOCORE hoy es una plataforma educativa **Streamlit de 4 hubs y 13 módulos navegables** construida alrededor de un **UPS de 4 dominios** (cardiovascular, respiratorio, neurológico, muscular) con procedencia y confianza por valor, un motor hemodinámico de lazo cerrado propio (3 escenarios habilitados), **una** regla de acoplamiento validada (BAR→FC) y narración con IA real (Anthropic) como único uso de IA. Las 13 páginas renderizan hasta el final sin excepción y 1165 tests pasan en 5 min 21 s (en una de dos corridas falló 1 por bloqueo de Windows, no por código). **Mayor fortaleza:** la disciplina de procedencia — los gates anti-órgano-fantasma, el compositor y la hemodinámica se comportan como dicen (verificado por ejecución, `domain/` con 90 % de cobertura). **Mayor hueco:** el borde "laboratorio de señal" fuera de ECG/EEG no está al nivel del núcleo, y hay fachadas nuevas que los tests no ven: **Respiratory Lab (insignia VALIDATED) devuelve FR = 60/min constante y AHI = 0 incluso con los patrones de apnea, y escribe esos valores al UPS**; el botón "Analizar Entropía y Complejidad" no mide entropía; el panel "SHAP/LIME real" es una heurística de desviación contra baseline; "ML real" es un puntaje de pesos manuales. Además, `PLAN.md` y `THIRD_PARTY_NOTICES.md` están citados en el repo pero **no existen**, y `CLAUDE.md` describe un repo anterior.

---

## TABLA RESUMEN DE MÓDULOS

"Renderiza" = AppTest hasta el final (0 `at.exception`, 0 `st.error`) `[EJECUTADO]`. "Tests" = existe prueba dedicada que pasa; entre paréntesis la cobertura de líneas del archivo principal `[EJECUTADO]`.

| Módulo | Qué hace | Estado honesto | Escribe al UPS | Renderiza | Tests |
|---|---|---|---|---|---|
| **Digital Twin OS** (`twin_shell/pages.py`, 2166 l) | Organismo de 5 órganos, sliders, escenarios, composer BAR→FC, cuerpo SVG/3D desde UPS, narrador IA, caso ciego, causal IA, ML de riesgo, clasificador ECG, timeline | **MIXTO**: UPS/escenarios/hemodinámica REAL-SIMULADO DECLARADO; acoplamientos de órgano y `PredictionEngine` HEURÍSTICO ETIQUETADO; "SHAP/LIME real" y "ML real" **mal etiquetados (FACHADA parcial)** | Sí: "Guardar este momento", "Ejecutar y persistir", "Componer y evaluar" (los sliders no) | Sí (10 s) | Sí (59 %) |
| **Academia Clínica** (Learning Hub) | Quiz 16 preguntas + feedback IA opcional + casos sintéticos + tabla 12 derivaciones | REAL (determinista) + IA real opcional; pestaña "Tutor IA" es un cartel de redirección | No (no hay botón) | Sí | Sí (53 %) |
| **ECG Lab › Monitoreo** | 6 fuentes (demo McSharry, MIT-BIH, PTB-XL, ESP32, CSV, casos clínicos), FC por TKEO, análisis, export | FC: REAL (validado); "Analizar Entropía y Complejidad": **FACHADA** | Sí, con compuerta clínica; **demo excluida** | Sí | Sí (`ecg_analyzer` 38 %) |
| **ECG Lab › 12 Derivaciones** | Generador 12 derivaciones, eje QRS (Einthoven), BBB, intervalos, quiz | REAL sobre señal SIMULADA DECLARADA | No | Sí | Sí (64 %) |
| **Multisensor Fusion Lab** | 4 canales **solo demo** → Health Score | HEURÍSTICO ETIQUETADO + SIMULADO; botón "Entropía" **FACHADA** | No | Sí | Parcial (56 %) |
| **Respiratory Lab** | Generador de 7 patrones + `RespiratoryAnalyzer` + SpO₂ + AHI + quiz | **ROTO Y NO HONESTO**: FR = 60.0 constante, AHI = 0 siempre; insignia VALIDATED | Sí — **escribe FR=60 y AHI=0** | Sí | Cobertura 74 % pero **ningún test fija FR/AHI** |
| **EEG Neuro Lab** | Bandas Welch, BAR/DAR/TBR, χ aperiódico (FOOOF), mu-ERD, engagement, export | REAL (ratios con cita); constantes de ingeniería sobre sintético | Sí (16 descriptores) + `apply_couplings` (no-op honesto) | Sí | Sí (95 %+) |
| **EMG Muscle Lab** | Activación, MDF, índice de fatiga | MDF REAL; activación = media/máx (HEURÍSTICO); fatiga **ROTO PERO HONESTO** en demo | Sí (activation + median_frequency) | Sí | Sí (92 %) |
| **HRV Analysis** | SDNN/RMSSD/pNN50, LF/HF, RSA, SampEn/DFA/Poincaré | REAL sobre RR de ECG SIMULADO DECLARADO; no lineales PENDING_VALIDATION; "Entropía" **FACHADA** | Sí (SDNN, mean_nn) | Sí | Sí (rsa 100 %, no lineal 100 %) |
| **Biomarkers Lab** | 4 índices por normalización lineal + PLV neurocardíaco | HEURÍSTICO ETIQUETADO ("modo demostración"); PLV siempre "no disponible" | No | Sí | Sí (93 %) |
| **Calculadoras Clínicas** | QTc ×4, eje QRS, MAP, shock index, Forrester, BMI, BSA, Berlin, A-a, NEWS2, qSOFA, GCS + informe | REAL (fórmula con cita; tests con verdad independiente) | No | Sí | Sí (92 %) |
| **Patient Pipeline** | Entrada manual → UPS + impresión clínica humana | REAL (entrada manual) / SIMULADO DECLARADO | Sí | Sí | Parcial |
| **Crea tu modelo 3D** | TC/RM→malla, visor, VCG 3D, mapa EEG (Perrin), ML de cohortes, anatomía | Cada pestaña declara su nivel (n=1, exploratorio) | No | Sí | Sí (66–95 %) |
| `app/ecg_trainer.py` (fuera del menú) | Entrenador ECG + ESP32 | `[NO PUDE VERIFICAR: no lo ejecuté]` | — | no corrido | 0 % |

---

## 1. IDENTIDAD Y PROPÓSITO

- **Qué es, según el propio repo:** "Un laboratorio digital de fisiología humana para enseñar medicina con IA, construido sobre una regla: nunca finge lo que no sabe" (`README.md:3`); regla de oro: "Cada dato declara su procedencia. Cuando el sistema no puede saber algo, lo dice — nunca rellena el hueco" (`README.md`). `CLAUDE.md` lo llama "Biomedical Operating System" en proceso. `[LEÍDO EN CÓDIGO]`
- **Licencia:** "BIOCORE AI — Source-Available, Non-Commercial License", © 2026 Luis Nazariego Santome, todos los derechos reservados; uso comercial requiere acuerdo. `[LEÍDO EN CÓDIGO]` (`LICENSE:1-5`, `README.md`). Autor único: 39 commits a nombre de Luis Nazariego Santome (+1 posterior, `cd693e6`). `[EJECUTADO]` (`git log`).
- **Remoto:** `github.com/nazariegosantomeluis-droid/biocore-ai`; ramas `main`, `archive`, `respaldo-mezcla-20261021` (+ `origin/main`, `origin/respaldo-mezcla-20261021`). `[EJECUTADO]`
- **Despliegue en Streamlit Cloud:** `[NO PUDE VERIFICAR: no tengo acceso a la consola de Streamlit Cloud ni a la URL desplegada; ni README, SETUP ni CHANGELOG mencionan una URL de Cloud]`. Lo que sí consta: el repo **no tiene `streamlit_app.py` en la raíz** (el entrypoint por defecto de Cloud); los entrypoints presentes son `app/main.py` (real), `app/streamlit_app.py` (wrapper que hace `runpy` sobre `app/main.py`), `run_biocore.py` (lanzador Windows) y el devcontainer arranca `streamlit run app/main.py`. Si Cloud apunta a otro archivo, no coincide con el repo. `[LEÍDO EN CÓDIGO]`
- **Riesgo de despliegue visto en código:** `get_shared_ups_engine()` es `@st.cache_resource` → **un solo engine SQLite compartido por todas las sesiones**, archivo `data/biocore_ups.db` (gitignored, efímero en Cloud). Cada sesión crea su propio paciente, pero comparten archivo/pool. `[LEÍDO EN CÓDIGO]` (`app/utils/patient_session.py:39-52`).

---

## 2. MAPA DEL REPO

**Tamaño.** 365 archivos trackeados; **285 `.py` = 64 685 líneas** (214 de producción = 48 708 l; **71 archivos de test = 15 977 l**). `CHANGELOG.md` = 5 526 líneas / 865 KB. `[EJECUTADO]` (`git ls-files`).

**Stack real.** Python **3.13.11** en `.venv` (README pide 3.10+, devcontainer usa 3.11, SETUP dice "probado en 3.13"). Streamlit **1.66.1**, numpy **2.5.4**, scipy 1.18.1, pandas **3.1.0**, scikit-learn 1.9.1, plotly 7.1.0, SQLAlchemy 2.1.6, anthropic 2.3.0, wfdb 4.3.1, fooof 1.1.1, pytest 9.2.0, pytest-cov 7.1.0. `[EJECUTADO]` (`pip list`). **`requirements.txt` solo fija `fooof==1.1.1`**; todo lo demás es `>=` (`numpy>=1.23`, `streamlit>=1.25`, …) → las versiones reales no están congeladas. `[LEÍDO EN CÓDIGO]`. `torch` no está en requirements (`src/ai/ecg_cnn.py` queda con `model=None`). `[LEÍDO EN CÓDIGO]`

**Árbol (primer y segundo nivel).** Líneas = `.py` de esa carpeta `[EJECUTADO]`.

| Carpeta | Contenido |
|---|---|
| `app/` (16 701 l) | `main.py` (2705 l: router + 8 páginas inline), `utils.py` **y** `utils/` (conviven; ver §9), `reporting.py` (PDF), `ecg_trainer.py` (app aparte) |
| `app/engines/` | `digital_twin_organism.py` (999 l), `simulation_engine.py` (701), `prediction_engine.py` (474) |
| `app/supermodules/` | `twin_shell/`, `academia/`, `ecg_12/`, `eeg_neuro_lab/`, `respiratory_lab/`, `calculators/`, `model3d/`, `biomarkers.py`, `rsa_panel.py`, `hrv_nonlinear_panel.py` |
| `app/utils/` | `ai_session.py` (clave por sesión), `design_system.py` (567 l), `patient_session.py`, `physiological_state.py`, `data_generator.py`, `env_loader.py` |
| `domain/` (8 058 l) | `physiology/state/` (UPS), `coupling/`, `hemodynamics/` (13 archivos), `scenarios/`, `narrator/`, `ml/` |
| `src/` (12 254 l) | `signals/{ecg,eeg,emg,respiration,ppg}/`, `clinical/` (case_database, sepsis_trajectory), `ai/`, `ml/cohort_map.py`, `imaging/volume3d.py`, + módulos sueltos legados |
| `clinical/` (3 068 l) | `ecg_analyzer.py` (1289 l), `bbb_detector.py`, `qrs_delineation.py`, `calculators.py`, `ecg12.py`, `ptbxl_metadata.py` |
| `biomedical/` (250 l) | `reasoning_engine.py`, `arrhythmia_classifier.py` — **no importados por la app viva** |
| `visualization/` (1 450 l) | `anatomy3d.py`, `vcg3d.py`, `cohort3d.py` (vivos); `medical/plotly_clinical.py` (vivo vía `utils.py`); `ecg_clinical_plot`, `ecg_annotations`, `medical_grid`, `educational_panel` (sin importadores) |
| `educational/` (852 l) | `learning_engine.py` (quiz), `ecg_academy.py`, `ecg_tutor.py`, `rural_mode.py` |
| `hardware/` (611 l) | `esp32_stream.py`, `emg_stream.py`, `sensor_manager.py` |
| `signals/` (638 l) | loaders legados (csv/edf/wfdb/universal) |
| `dashboards/` (265 l) | `multisensor.py` (`MultisensoralRecord`, vivo vía `app/utils.py:126`) |
| `tests/` (15 977 l) | 71 archivos |
| `docs/` | `especialidades/` (4 .md) y `validation/ecg_hr_detector_bank/` (17 scripts + PDFs de rondas 2–6) |
| `documentation/` | 17 .md "Nivel 00/01" = **visión a largo plazo** (constitución, UPS, twin 3D…) |
| `data/` | `anatomy3d/` (2 .npz), `reference_signals/` (PTB s0010, CAP n16), `samples/` (TC tórax), `biocore_ups.db` (gitignored), `ptbxl_database.csv` (6.3 MB, **sin trackear**) |
| `tools/` | scripts offline que construyen los .npz |
| raíz | `main.py` (CLI legado 643 l), `run_biocore.py`, `example_reasoning_engine.py`, `install_dependencies.py`, `RUN_BIOCORE.bat`, `run_local.ps1` |

No existen `pages_legacy/`, `app/components/`, `app/pages/` (CLAUDE.md los menciona). `[EJECUTADO]` (`ls`).

**Navegación.** `app/main.py:177-231` define `HUBS` (4 hubs, 13 entradas) y `main()` (`:2672`) pinta un `radio` de hub + `selectbox` de módulo en la barra lateral; `render_page_content()` (`:498`) enruta por *substring* del nombre. `showSidebarNavigation=false` en `.streamlit/config.toml` apaga el menú multipágina. Antes del router hay un **panel de entrada de clave de IA** (`render_entry_gate`, `ai_session.py:105`): si no hay `ANTHROPIC_API_KEY` en el servidor, la app **no muestra nada más** hasta pulsar "Entrar sin IA" o pegar clave. `[LEÍDO EN CÓDIGO]`

| Hub | Módulos |
|---|---|
| Digital Twin OS | 🧬 Digital Twin OS |
| Learning Hub | 🏫 Academia Clínica |
| Clinical Hub | ECG Lab, Multisensor Fusion Lab, Respiratory Lab, EEG Neuro Lab, EMG Muscle Lab, HRV Analysis, Biomarkers Lab, Calculadoras Clínicas, Patient Pipeline |
| Laboratorio 3D | 🧊 Crea tu modelo 3D |

Tres labs (ECG-12, EEG, Respiratory) se cargan con `runpy.run_path(page_content.py)` dentro de `try/except` que llama a `render_error_state`, la cual **loguea y no muestra la excepción** (`design_system.py`). Consecuencia: `at.exception` de AppTest no ve un fallo interno de esas vistas. Por eso hice un segundo barrido buscando texto "No se pudo / Traceback / ⚠️&nbsp;": 0 coincidencias en las 13 páginas. `[EJECUTADO]`

---

## 3. ARQUITECTURA CENTRAL

### 3.1 UPS — esquema (`domain/physiology/state/schema.py`)

- `UnifiedPhysiologicalState(patient_id, timestamp, cardiovascular, respiratory, neurological=∅, muscular=∅, events=[])` (`:284-311`); `all_domains()` devuelve los **4** (`:313`). `DomainState(domain, descriptors{name→PhysiologicalDescriptor})`. `PhysiologicalDescriptor(name, value:float, unit, provenance, confidence∈[0,1], source_detail)` valida el rango de confianza. `PhysiologicalEvent(event_type, domain, severity, description, provenance, confidence, timestamp, related_descriptor)`. `[LEÍDO EN CÓDIGO]`
- **Dominios:** vivos = cardiovascular, respiratorio, neurológico (Capa 5A, 2026-08-30), muscular (2026-09-10). **No existe** dominio metabólico, ni `SleepState`, ni autonómico en el UPS (§9). `[LEÍDO EN CÓDIGO]` + `[EJECUTADO]` (organismo vacío → 0 descriptores en los 4 dominios).
- **Descriptores por dominio** (los que `builder.py` puede escribir, con su gate):
  - cardiovascular (`builder.py:59-115`): `heart_rate`, `hrv` (procedencia del llamador); `health_score`, `risk_score`, `rhythm_stability`, `myocardial_stress`, `cardiac_output` (siempre DERIVADO, solo si `heart_rate` real).
  - respiratorio (`:118-181`): `respiratory_rate`, `spo2`, `ahi`; `health_score`, `risk_score`, `hypoxia_risk`, `apnea_risk`, `tissue_oxygenation` (DERIVADO, solo si hay `respiratory_rate`).
  - neurológico (`:184-346`): `delta/theta/alpha/beta/gamma_power`, `bar`, `dar`, `tbr`, `chi_aperiodic` (cada uno con gate individual); `health_score`, `risk_score`, `mental_workload`, `cognitive_fatigue`, `attention`, `stress_perception`, `sleepiness` (DERIVADO, solo si `alpha_power` o `beta_power`).
  - muscular (`:349-428`): `activation`, `median_frequency`; `health_score`, `risk_score`, `neuromuscular_efficiency`, `movement_smoothness` (DERIVADO, solo si `activation`).
  - tras acoplar/medir: `heart_rate_acoplado`, `systolic_bp_modelo`, `diastolic_bp_modelo`, `map_modelo` (adjuntos con `append_descriptors`).
- **Campos fantasma excluidos a propósito:** neuro `frontal_activity`, `temporal_activity`; muscular `recruitment_pattern`, `motor_symmetry`, `power_output` (nunca se asignan en `_update_*` → serían constantes disfrazadas) (`builder.py:323-329, 410-418`); muscular `fatigue_index` **no se persiste** (generador demo lo clava en 0) (`:390-400`); metabólico/`metabolic_efficiency`/EDA retirados (`biomarkers.py:213`, `main.py:581`). `[LEÍDO EN CÓDIGO]`
- **Eventos (`EventType`, enum cerrado, 6 miembros):** `ARRHYTHMIA_RISK_HR_EXTREME` (FC>120 o <40; crítico >150 o <35), `LOW_HRV_AUTONOMIC_STRESS` (HRV<20, solo si no hubo evento de FC), `HYPOXIA_SPO2_CRITICAL` (<90), `HYPOXIA_SPO2_LOW` (<95), `HIGH_STRESS_EEG` (stress_level>75), `SEVERE_MUSCLE_FATIGUE_EMG` (fatigue_index>80). `[LEÍDO EN CÓDIGO]` (`builder.py:431-548`). El evento muscular nunca dispara con el generador demo. `[LEÍDO EN CÓDIGO]`

### 3.2 `Provenance` — 7 valores y dónde se usa cada uno

| Valor | Banda de confianza (`CONFIDENCE_REFERENCE`) | Dónde se usa (vivo) | Prov. |
|---|---|---|---|
| `SENSOR_REAL` | 0.85–1.0 | Solo `main.py:1500` (ECG Lab, si la etiqueta de fuente contiene `SENSOR_REAL`, es decir ESP32 verificado en vivo) y `signal_sources.py:230`. **Ningún flujo que probé la produce** (no hay hardware) | L |
| `SIMULACION` | 0.60–0.90 | Default de `from_digital_twin_organism` (`builder.py:554`) y de **todos** los escritores de labs (ECG sin hardware, EEG, EMG, HRV, Respiratory, Patient Pipeline) y de `scenarios/*` | L+E |
| `DERIVADO` | 0.50–0.95 | `health_score`, `risk_score` y demás índices que calcula el organismo (`builder.py`) | L+E |
| `REFERENCIA_CLINICA` | **sin banda** (a propósito: `default_confidence` lanza `KeyError`) | Solo vía `ClinicalReferenceValue` (tabla aparte `ups_clinical_references`), nunca con `PhysiologicalDescriptor` | L |
| `MODELO_HEMODINAMICO` | 0.30–0.80; usa 0.75 explícito | `closed_loop_ups_bridge.py:166-180` (viva); `ups_bridge.py:130` (R-RCR estático, 0.425) **sin llamador vivo** (solo `context_comparison`/tests) | L+E |
| `DERIVADO_ACOPLAMIENTO` | 0.30–0.80; 0.70 si regla validada, 0.35 si transcrita | `coupling/bridge.py:188-195`. `[EJECUTADO]`: dispara con conf 0.70 | L+E |
| `ARRASTRE_TEMPORAL` | **sin banda** (hereda la del origen) | Solo `composer.py:149-159`. `[EJECUTADO]`: `heart_rate` arrastrado conserva conf 0.75 de origen | L+E |

`VALIDADO_POR_FUENTE` y `TRANSCRITO_SIN_VALIDAR` **no son `Provenance`**: son `ValidationStatus` de una `CouplingRule` (`coupling/rules.py:63-72`) y etiquetas de texto en las citas de EEG (`eeg_analyzer.py`, `spectral_model.py`). `PENDING_VALIDATION` es un string/comentario (en `simulation_engine.py` 26 veces, `sepsis_trajectory.py:54`, `arrhythmia_types.py:47`, flags booleanos en `hemodynamics/`). `[LEÍDO EN CÓDIGO]`

### 3.3 Gates anti-órgano-fantasma — dónde están y qué bloquean

`builder.py:86` (`has_real_cardiac_input = "heart_rate" in signals`), `:137` (`"respiratory_rate"`), `:216` (`alpha_power`/`beta_power`), `:379` (`"activation"`). Sin la señal primaria, el dominio **sale vacío** aunque el organismo traiga defaults "sanos" (`health_score=50`, `CardiacDetail()`, etc.). Además cada ratio (BAR/DAR/TBR) y χ tiene gate individual y devuelve `None` si el denominador es ≈0. `[LEÍDO EN CÓDIGO]`

`[EJECUTADO]` sobre una BD temporal: organismo recién creado → `{cardiovascular:0, respiratory:0, neurological:0, muscular:0}` descriptores y 0 eventos; solo-respiratorio → cardio 0, neuro 0, músculo 0, resp 7; solo-ECG → neuro 0, resp 0; solo-EEG → cardio 0. Regresión protegida por `test_hygiene_short_signal_and_ghosts.py` y `test_muscular_domain.py`. Los gates **no existen** en el `composer` (arma `DomainState` a mano) ni en `append_descriptors`, pero ahí solo copia valores ya persistidos.

### 3.4 Reglas de acoplamiento

- **Catálogo vivo (`coupling/catalog.py:85`): 1 regla** — `AROUSAL_TAQUICARDIA_BAR`: `bar > 1.8` ⇒ `heart_rate` **+15.0 bpm**; `VALIDADO_POR_FUENTE`, `enabled=True`. Fuentes: Guyton & Hall 14ª ed. cap. 61; Schutter 2006 / Handbook of Psychophysiology 3ª ed. cap. 10; rango citado +10 a +25 bpm. `[LEÍDO EN CÓDIGO]`
- **Dispara en el flujo vivo — solo por el composer.** `[EJECUTADO]` (BD temporal): snapshot EEG-solo con `bar=2.5` → `apply_couplings` devuelve `[]` (**no-op documentado**, no hay FC base: `eeg_neuro_lab/page_content.py:773-775`); snapshot ECG-solo FC=70; `compose_neuro_cardiac_snapshot` → `available=True`, edad del arrastre 0.02 s, **FC 70 → 85 bpm**, `heart_rate_acoplado` `derivado_acoplamiento` conf 0.70, `bar` conserva `simulacion`, `heart_rate` pasa a `arrastre_temporal`. Sin BAR persistido → `available=False, reason='sin BAR persistido'`.
- **Dos llamadores de `apply_couplings`:** `composer.py:178` (vía botón "Componer y evaluar", `twin_shell/pages.py:545-547`) y `eeg_neuro_lab/page_content.py:777` (no-op salvo que el snapshot ya tenga FC, cosa que el lab nunca envía). `[LEÍDO EN CÓDIGO]`
- **Bloqueo de escenarios** `COUPLING_DISABLED_SCENARIOS = {stress, anxiety, seizure}` (`bridge.py:79`) lanza `CouplingScenarioBlockedError`, pero **ningún llamador vivo pasa `scenario`** (ambos pasan `None`), así que hoy es una barandilla estructural no ejercida por la UI. `[LEÍDO EN CÓDIGO]`
- **Política multi-regla:** `_combine_proposals_for_same_effect` es identidad (`bridge.py:154-159`); con >1 regla sobre el mismo efecto ganaría la última por accidente. Pendiente de definir. `[LEÍDO EN CÓDIGO]`
- **No son reglas de acoplamiento del UPS** y no deben confundirse: los índices `neurocardiac/cardiorespiratory/neuromuscular_coupling` del organismo en memoria (`digital_twin_organism.py:643`, mostrados en `render_couplings`) son fórmulas propias; la UI los declara HEURÍSTICO y los muestra como banda cualitativa (`twin_shell/pages.py:481-516`). `[LEÍDO EN CÓDIGO]`
- `coupling/engine.py` conserva un docstring obsoleto ("dormido por diseño… ningún módulo importa este paquete… catálogo vacío"). Falso hoy. `[LEÍDO EN CÓDIGO]`

### 3.5 Composer multi-dominio (`compose_neuro_cardiac_snapshot`, `composer.py:99-181`)

Toma el último `bar` persistido y la última `heart_rate` persistida del paciente (consultas por `rowid`), exige que ambos existan, mide `|Δt| = |ts_bar − ts_hr|` y **declina si > `max_hr_carry_age_s` = 120 s** (`DEFAULT_MAX_HR_CARRY_AGE_S`, `:78`, "config del compositor, no constante clínica firmada"). Si compone: guarda un snapshot nuevo con `bar` (copia literal) + `heart_rate` (`ARRASTRE_TEMPORAL`, `source_detail` declara snapshot origen, timestamp y edad), y llama a `apply_couplings(VALIDATED_RULES, scenario=None)`. Devuelve `ComposeResult(available, snapshot_id, reason, hr_age_s, coupled)`. Quién lo llama: solo el botón de Twin OS. `[LEÍDO EN CÓDIGO]` + `[EJECUTADO]` (caso feliz y vacío; no ejecuté el caso "FC > 120 s" ni "sin FC").

### 3.6 Persistencia

SQLite vía SQLAlchemy, `data/biocore_ups.db` (WAL, `foreign_keys=ON`; `db.py:21-40`). **6 tablas:** `ups_patients`, `ups_snapshots`, `ups_values` (domain, descriptor, value, unit, provenance, confidence, source_detail), `ups_events`, `ups_clinical_impressions`, `ups_clinical_references` (`models.py`). `[LEÍDO EN CÓDIGO]`

- Consultas "lo más reciente" por **`rowid DESC`**, no por timestamp (en Windows `datetime.now()` no es monótono entre instancias): `get_latest_state` (`repository.py:193-198`), `get_latest_snapshot_id_with_descriptor` (`:262-272`), `get_latest_snapshot_id` (`clinical_impression_repository.py`).
- `get_value_history` y `get_events` **sí ordenan por timestamp** (`repository.py:276-323`); el propio código documenta que arrastran el problema de reloj. `[LEÍDO EN CÓDIGO]`
- Detalles menores: `EventRecord.provenance` es `String(20)` y `derivado_acoplamiento` mide 21 (SQLite no lo aplica; Postgres/MySQL truncaría; hoy ningún evento usa esa procedencia). `PatientRecord` guarda el nombre en texto plano (`// TODO` en `models.py:10`). `author` de impresión clínica es genérico (`// TODO` en `clinical_impression.py:62`, `main.py:2586`). `[LEÍDO EN CÓDIGO]`

### 3.7 Motor hemodinámico (no es `svZeroDSolver` ejecutándose)

`svzerodsolver` **no es dependencia**. `r_rcr.py` reimplementa las ecuaciones del bloque RCR (citadas de `WindkesselBC.h`/`BloodVessel.cpp`) con solución analítica exacta; el docstring dice que se verificó **una vez** contra el paquete oficial `svzerodsolver`, instalado y ejecutado en esa tanda (curva final <0.2 sobre ~9000). `[LEÍDO EN CÓDIGO]` (`r_rcr.py:1-70`) + `[SEGÚN CHANGELOG/DOCS, NO VERIFICADO]` (la corrida contra el solver oficial). **`THIRD_PARTY_NOTICES.md`, citado en `r_rcr.py:9` y `hemodynamics/__init__.py:10` para la atribución BSD-3, no existe en el repo.** `[EJECUTADO]` (`ls`).

Cadena (cada módulo envuelve al anterior): `r_rcr` (Windkessel 3 elementos) → `physiological_flow` (parámetros fisiológicos, SV ref 70 mL) → `baroreflex` (controlador proporcional sobre Rd, k=1.0) → `pathological_tone` (hipertensión = reseteo del barostato; sepsis = vasoplejía: `max_rd`×0.5, `k`×0.3) → `frank_starling` (SV=f(EDV)) → `diastasis_ceiling` (EDV ≤ 180 mL) → **`closed_loop`** (retorno venoso P_sf=7 mmHg → EDV → SV → flujo → presión → barórreflejo, `CLOSED_LOOP_MAX_TICKS=40`, tolerancia 1e-4). `[LEÍDO EN CÓDIGO]`

- **Escenarios habilitados para escribir PA al UPS:** `{healthy, hypertension, sepsis}` (`closed_loop_ups_bridge.py:94`), con `HemodynamicModelNotEnabledError` estructural para el resto, y confianza fija **0.75** (`:113`). `[LEÍDO EN CÓDIGO]` + `[EJECUTADO]` (el botón "Ejecutar y persistir" adjuntó PA modelo; el panel declara que sepsis temprana no tiene PA: "límite del modelo: modela dinámica de shock").
- **`SimulationScenario` tiene 15 miembros** hoy (`healthy, exercise, stress, anxiety, arrhythmia_afib/aflutter/svt/sbrady, hypoxia, apnea, fatigue, seizure, sepsis, copd, hypertension`) `[EJECUTADO]`; los docstrings dicen "12 en total" y "los otros 9". Cada escenario no habilitado tiene su razón documentada (exercise tiene un bug de `recovery_progress` sin acotar → FC=−14580; stress/anxiety son picos transitorios; apnea/seizure por fase; arritmias sin driver; hypoxia sin quimiorreceptor; fatigue/copd sin referencia citada). `[LEÍDO EN CÓDIGO]`
- **Parámetros validados vs. pendientes:** Rp, Rd, Pd, RPT_total≈1.0873 mmHg·s/mL (Guyton ≈1 PRU), división 90/10 (Westerhof), P_sf — VALIDADOS (Rondas 1–2, 2026-07-30/31). **Compliancia `C=0.8073`: PENDIENTE ESTRUCTURAL** (`PHYSIOLOGICAL_PARAMETERS_PENDING_VALIDATION = True`, `physiological_flow.py:157`) hasta modelar la curva de eyección ventricular pulsátil real. `VENOUS_CAPACITANCE_SEPSIS_MULTIPLIER=2.0` "aceptado pero no citado" (`closed_loop.py:207`; bridge `:124`). `[LEÍDO EN CÓDIGO]`
- **Consumidores vivos:** `twin_shell/pages.py:811` (simulador de escenarios), `:1224` (caso ciego), `baroreflex_panel.py` (`run_closed_loop`, `run_pathological_baroreflex`, solo lectura), `sepsis_trajectory.py`, `rich_engine.py`. El puente R-RCR estático (`ups_bridge.py`) y los `*_comparison.py` son herramientas de verificación sin llamador de la app. `[LEÍDO EN CÓDIGO]`

---

## 4. MÓDULOS, UNO POR UNO

> Para cada ficha, "AppTest" = `AppTest.from_file(app/main.py)` con `biocore_ai_entry_done=True` y la página fijada, `ANTHROPIC_API_KEY` sin definir. Además hice un **smoke de botones**: clic en cada botón, uno por uno, en un AppTest nuevo contra BD temporal; **0 excepciones en todos**. `[EJECUTADO]` (lo que no pulsé: radios/selectboxes alternativos, salvo lo anotado).

### 4.1 Digital Twin OS — `app/supermodules/twin_shell/pages.py` (2166 l)

- **Panorama:** `main()` (`:2124`) compone: sliders (`render_sensor_controls :341`), cabecera (`:231`), grid de 5 órganos (`:284`), acoplamientos (`:481`), composer (`:519`), panel de órgano (`:427`), escenarios/intervenciones en memoria (`:576`), simulador UPS (`:693`), barórreflejo (`baroreflex_panel`), cuerpo sincronizado (`:919`), narrador (`:967`), caso ciego (`:1351`), causal (`:1584`), ML riesgo (`:1659`), clasificador ECG (`:1803`), riesgo por sistema (`:2044`), export (`:2088`), timeline (`:2107`). Sin pestañas de primer nivel (solo SHAP/LIME/Importancia dentro del clasificador). `[LEÍDO EN CÓDIGO]`
- **AppTest:** renderiza completo, 10.1 s, 60 markdown, 5 métricas, 10 expanders, 18 botones. Avisos visibles: compliancia C pendiente; clave de IA ausente (narrador, causal, feedback). `[EJECUTADO]`
- **Clasificación por salida:**
  | Salida | Clase | Prov. |
  |---|---|---|
  | Grid de órganos / `health_score` por órgano | HEURÍSTICO ETIQUETADO (badge de procedencia en cada etiqueta) | L |
  | Acoplamientos Cerebro↔Corazón / Cerebro↔Músculos | HEURÍSTICO ETIQUETADO (banda cualitativa, "no fingir precisión") | L |
  | Corazón↔Pulmones (HR:RR 4:1) | número + cita PRQ; el índice 0–100 es HEURÍSTICO | L |
  | Cuerpo SVG/3D | REAL-desde-UPS (`organ_visual_state`, color por severidad de eventos) | L |
  | Simulador de escenarios persistido en UPS | SIMULADO DECLARADO + PA modelo 0.75 (3 escenarios) | E |
  | Barórreflejo panel | REAL del modelo (solo lectura de `run_closed_loop`) | L |
  | Narrador / Causal | IA real (Anthropic), apagada sin clave; solo heart/lungs para causal (`_CAUSAL_UPS_ORGANS`) | L+E |
  | Caso clínico ciego (15 escenarios) | SIMULADO DECLARADO, evaluación determinista + feedback IA opcional | L |
  | "Riesgo cardiovascular (ML real, desde el UPS)" | **HEURÍSTICO con etiqueta engañosa**: `PatientRiskPredictor` suma `risk_weights` fijos, **no hay `.fit()`** (`patient_analytics.py:15,119-130`) | L+E(grep) |
  | "Explicabilidad (SHAP/LIME real…)" | **FACHADA parcial**: `shap_like_explanation`/`lime_like_explanation` narran `|valor−baseline|` normalizado; el texto LIME afirma "cuando se alteran ligeramente en el entorno local" y **no se perturba nada**. Solo la 3ª pestaña admite "NO es SHAP/LIME real" (`pages.py:1985-1989`; `interpretability.py:271-314`) | L |
  | Evaluación de riesgo (`PredictionEngine`) | HEURÍSTICO ETIQUETADO (cada factor con ⚠ o cita ACLS/ATLS/NEWS2/AASM) | L |
  | Mensajes "El UPS todavía no modela Cerebro/Músculos (solo cardiovascular y respiratorio)" | **Obsoleto/incorrecto**: el UPS modela neuro y muscular; el causal narrator solo cubre heart/lungs (`pages.py:1605`) | E+L |
- **UPS:** escribe en 3 puntos: "Guardar este momento" (`:945`) y "Ejecutar y persistir" (`:759`), ambos `SIMULACION`; composer (§3.5). Funciona en vivo: `[EJECUTADO]` ("Momento guardado…", "6 snapshots consultados desde el UPS (SQLite) — no desde session_state"). Al explorar Cerebro/Músculos/Autónomo aparece el mensaje obsoleto de arriba.
- **Validaciones que usa:** hemodinámica (§3.7), BAR 1.8 (§3.4), referencias de PA (§8), umbrales de evento (§3.1).
- **Bugs/deuda:** mensaje obsoleto; ML/SHAP-LIME rotulados "real"; `render_organ_grid`, `render_mode_toggle` etc. figuran como "sin otro llamador" solo porque `main()` los llama en el mismo archivo (no son huérfanos). Cobertura 59 %.

### 4.2 Academia Clínica — `app/supermodules/academia/pages.py` (589 l)

- **Pestañas:** `📝 Lecciones y Casos`, `📖 Tutor IA`. **La segunda está casi vacía**: un `st.info` que redirige al Narrador de Twin OS (`:547-561`). `[LEÍDO EN CÓDIGO]` + `[EJECUTADO]` (render).
- **Quiz:** 16 preguntas hardcodeadas (`educational/learning_engine.py:113-138`), 4 categorías (ECG Básico 6, ECG 12-derivaciones 4, Arritmias 4, Otras señales 2 = 16; al ejecutar `generate_quiz(lesson=…)` en nivel básico, ECG Básico muestra 5 porque ese nivel recorta a 5). Niveles: básico 5, intermedio 8, avanzado todo. Calificación **determinista** (`grade_quiz :57`). `[EJECUTADO]`
- **IA:** el feedback fundamentado llama `stream_findings_narration(..., client=ai_client())` (`:248`, `:497`) solo si hay clave; sin clave el panel lo declara y la calificación sigue funcionando. `[LEÍDO EN CÓDIGO]` + `[EJECUTADO]`
- **Casos sintéticos** (`render_synthetic_case_section :308`): `[NO PUDE VERIFICAR: no leí esa función completa]`.
- **UPS:** sin botón de guardado. **Modo Rural** guarda progreso en disco local (`rural_mode`). **Calidad del contenido clínico del quiz:** sin firma de experto registrada; hay una pregunta con opciones mezcladas en inglés ("R predominant in V1…") y otra discutible ("eje izquierdo → posible HVI"). `[LEÍDO EN CÓDIGO]`
- **AppTest:** renderiza, 0.9 s; botón "Iniciar Quiz" sin excepción; cobertura 53 %.

### 4.3 ECG Lab — `main.py:439` (cabecera) + Monitoreo `:1522` + 12 Derivaciones `ecg_12/`

- **Insignia:** `VALIDATED` — "Detección QRS validada en 6 rondas contra MIT-BIH (Sensibilidad >99 %). Filtros estándar AHA" (`main.py:412-415`). `[LEÍDO EN CÓDIGO]` (la afirmación de sensibilidad `[SEGÚN CHANGELOG/DOCS, NO VERIFICADO]`; el banco está en `docs/validation/ecg_hr_detector_bank/`, que no re-corrí).
- **Fuentes (6):** demo `DynamicECGGenerator` (McSharry 2003), MIT-BIH y PTB-XL (descarga en vivo desde PhysioNet; **ninguna forma de onda viene empaquetada**, solo `data/reference_signals/ptb_s0010.npz`), hardware ESP32, CSV, casos clínicos (`src/clinical/case_database.py`, 0 % cobertura). `[LEÍDO EN CÓDIGO]`
- **Funciones clave:** `ECGAnalyzer.detect_r_peaks_tkeo` (`ecg_analyzer.py:258`, banda 5–15 Hz + energía de Teager-Kaiser + refractario), `_measure_ecg_heart_rate_tkeo` (`main.py:1388`), `estimate_heart_rate_with_confidence` (`ecg_analyzer.py:833`, compuerta "sinusal o declina": pRR31, metrónomo, banda sinusal, Vpp), `detect_bundle_branch_block` (`bbb_detector.py:509`), `delineate_qrs` (`qrs_delineation.py`). `[LEÍDO EN CÓDIGO]`
- **Clasificación:** FC por TKEO → REAL (error medido 0.00–0.12 bpm sobre FC 40–200 contra el generador, según docstring; el test de consolidación pasa) `[LEÍDO EN CÓDIGO]`+`[EJECUTADO]` (test). Compuerta de escritura → REAL con umbrales PROVISIONALES (§8). BBB → REAL (matriz de confusión contra **50 casos PTB-XL**; el test pasa, 28.8 s, el mayor de la suite `[EJECUTADO]`; el valor de la matriz no lo leí). Fuente demo → SIMULADO DECLARADO y **excluida del botón de guardado** (`main.py:1455-1463`). **"Analizar Entropía y Complejidad" → FACHADA** (ver Sorpresas #2).
- **UPS:** `_render_ecg_save_to_twin` (`:1420`): corre la compuerta; si declina muestra el motivo y **no escribe**; si pasa escribe `heart_rate` con `SIMULACION` (o `SENSOR_REAL` solo si la etiqueta lo dice). El botón de las 6 fuentes no apareció en la fuente demo (por diseño); no lo ejecuté con MIT-BIH/PTB-XL (necesitan red). `[NO PUDE VERIFICAR: ruta de escritura con registro real]`
- **ECG-12:** `[EJECUTADO]` el botón "Generar ECG de 12 derivaciones" produjo "NORMAL: No acute findings. Routine monitoring appropriate."; el quiz "Verificar respuesta" calificó "Incorrecto…". Eje QRS por `qrs_axis_from_net` (Einthoven, `twelve_lead_analyzer.py`). Cobertura de `ecg_12/page_content.py` 64 %.
- **Pestañas:** Monitoreo, 12 Derivaciones (+ Clínica, Educativa dentro de ECG-12). **AppTest:** renderiza, 3.3 s, 0 excepciones, 0 errores.
- **Deuda:** `ClinicalDataQualityError`/`QUALITY_THRESHOLD` con comentario "la escritura ECG→UPS sigue sin cablear" — **obsoleto** (sí está cableada, `main.py:1473`); cobertura de `ecg_analyzer.py` solo 38 % (el motor "más validado" es el menos cubierto por pytest; se valida con bancos offline).

### 4.4 Multisensor Fusion Lab — `main.py:2023`, `dashboards/multisensor.py`

- **Qué muestra:** 4 canales **100 % generados** (`DynamicECGGenerator`, PPG, SpO₂, respiración demo; no hay carga de archivos) → `MultisensoralRecord.compute_physiological_indices()` y `health_score()`. Vistas: radio Clínica/Educativa/Investigación/IA/Simulación. Insignia `HEURISTIC` ("Health Score propietario… no validado poblacionalmente"). `[LEÍDO EN CÓDIGO]`
- **Clasificación:** Health Score → HEURÍSTICO ETIQUETADO (`dashboards/multisensor.py:183-215`: bandas de FC 60–100→100, etc.; **valores por defecto 50** para categorías sin dato, p. ej. `recovery` siempre 50) `[LEÍDO EN CÓDIGO]`. Señales → SIMULADO. "Analizar Entropía" → **FACHADA**.
- **UPS:** no escribe. **AppTest:** renderiza, 0.7 s, sin pestañas. Cobertura 56 %.
- **Bug corregido y documentado:** SpO₂ a 1 Hz se declaraba a 250 Hz (diluía `spo2_mean` a ~0.4 %). `[LEÍDO EN CÓDIGO]` (`main.py:1993-2020`).

### 4.5 Respiratory Lab — `respiratory_lab/pages.py` + `page_content.py` + `src/signals/respiration/`

- **Insignia:** `VALIDATED` — "Cálculo de AHI y estratificación de severidad conformes a los manuales de puntuación de la AASM" (`pages.py:27-30`). `[LEÍDO EN CÓDIGO]`
- **Pestañas (8 en AppTest):** Clínica, 📊 Señales Respiratorias, 🫀 SpO2 Oximetría, 📈 Análisis Avanzado, 📚 Referencias Clínicas, ❓ Cuestionario (internas de la vista clínica), Investigación, Simulación. Ninguna vacía. `[EJECUTADO]`
- **Lo que calcula de verdad — y lo que NO:**
  - `RespiratoryAnalyzer._calculate_respiratory_rate` (`respiratory_analyzer.py:223-245`) calcula los "intervalos RR" como `breaths[i+1].breath_num − breaths[i].breath_num`, que **siempre vale 1** ⇒ `rr = 60.0 / 1 = 60.0` y la variabilidad es 0, **con cualquier señal** con ≥2 respiraciones. `[EJECUTADO]`: con los 7 patrones del generador (rr=15, 60 s y 300 s) y en la app misma (default 120 s) la FR reportada es **60.0 resp/min**; la propia página muestra "⚠️ Tachypnea detected (RR 60/min)" y "⚠️ Periodic breathing detected - characteristic of sleep apnea" para el patrón **Normal (Quiet Breathing)**.
  - `_detect_apneas` (`:247-312`) usa `zip(apnea_starts, apnea_ends)`: la señal normalizada empieza en ≈0, así que `mask[0]=True` y el primer `end` precede al primer `start` → los pares quedan desalineados con duración negativa y **nunca se cuenta ningún evento**. `[EJECUTADO]`: en `apnea_central` con `apnea_duration=15`, la máscara contiene dos tramos planos de **19.6 s**, pero el análisis devuelve `apneas=0, AHI=0.0, severity=normal`; igual con `apnea_obstructive`, `cheyne_stokes` y una pausa de 10 s inyectada. Aun si el emparejamiento funcionara, el mínimo para contar un evento es `apnea_threshold/10` = **1 s** (`:276`), no los 10 s de AASM. `[LEÍDO EN CÓDIGO]`
  - No hay detección de hipopneas: "AHI" = apneas/hora de grabación (`:300-301`). `[LEÍDO EN CÓDIGO]`
  - La severidad (`_assess_severity :369-389`) usa cortes AASM 5/15/30, más una promoción a "moderate" si SpO₂ mínima <85 % sin cita. `[LEÍDO EN CÓDIGO]`
  - Además: en el generador a rr=15/min el detector cuenta 60 respiraciones en 120 s (30/min). `[EJECUTADO]` — `[NO PUDE VERIFICAR: si el exceso es del generador o del detector]`.
- **Clasificación:** SpO₂ mínima/basal y tiempos <90/<85 → REAL sobre señal SIMULADA. **FR, variabilidad, AHI, tipo de apnea, patrón "periodic": ROTO sin declararlo** (devuelven un valor, no "no disponible"). La insignia VALIDATED no refleja esto.
- **UPS:** botón en Investigación (`pages.py:190`). `[EJECUTADO]` → "Estado guardado… respiratory: 8 descriptores". Escribe `respiratory_rate=analysis.respiratory_rate` (=60.0) y `ahi=analysis.apnea_hypopnea_index` (=0.0) con `SIMULACION` (`:199-205`): **un valor constante entra al UPS como si fuera medición**. Rompe la garantía anti-fantasma por el lado del origen.
- **Tests:** los que tocan el analizador son visuales/de render (`test_visual_migration_supermodules.py`); **ninguno fija FR ni AHI** (cobertura 74 % del analizador, 40 % del generador). Por eso pasa la suite.
- **AppTest:** renderiza, 0.9 s, 0 excepciones.

### 4.6 EEG Neuro Lab — `eeg_neuro_lab/pages.py` + `page_content.py` (889 l) + `src/signals/eeg/`

- **Pestañas:** solo "Clínica" (las otras 4 se retiraron como fachadas, `pages.py:21-25`). Dentro: generador por patrones/CSV, métricas, DAR/TBR/BAR/χ, panel mu-ERD y engagement, export PDF, "Guardar al gemelo", quiz de 5 preguntas determinista. `validation=None` explícito (módulo mixto). `[LEÍDO EN CÓDIGO]`
- **Funciones:** `EegAnalyzer` (`eeg_analyzer.py:308`: Welch por ventanas de 1 s, rechazo de artefactos por gradiente, band power, ratios), `fit_aperiodic_component` (`spectral_model.py:330`, FOOOF + corrección de la atenuación del bandpass), `detect_mu_erd` (`erd_detector.py:234`), `detect_engagement` (`engagement_detector.py:165`). `[LEÍDO EN CÓDIGO]`
- **Clasificación:** band power y ratios → REAL (cociente de potencias con cita); χ → REAL con alcance LFP→EEG de superficie declarado por analogía y error de instrumento 0.175 medido; fuente → SIMULADO (generador por bandas con parpadeos) o CSV. Constantes de artefacto/duración → ingeniería calibrada **sobre el propio generador** (§8).
- **UPS:** `[EJECUTADO]` "Estado guardado… neurological: 16 descriptores"; el acoplamiento imprimió "sin FC medida en este snapshot, nada que modular" (no-op honesto, §3.4). Export PDF `[EJECUTADO]` (generó PDF; lo borré).
- **AppTest:** renderiza, 0.8 s; cobertura de `page_content.py` 52 %, del analizador 96 %.
- **Deuda:** el generador demo es la única fuente "en vivo"; sin EEG real las constantes de §8 no están contrastadas.

### 4.7 EMG Muscle Lab — `main.py:947`, `src/signals/emg/`

- **Qué calcula:** `EmgAnalyzer.analyze` (`emg_analyzer.py:86`): bandpass 20–450 Hz, **activación = media|x| / máx|x| ×100** (no es %MVC), **MDF** por Welch (`median_frequency :49`), **índice de fatiga** = (120 − MDF)/60 ×100 acotado 0–100 (`:64`). Constantes 120/60 "heredadas sin firma". `[LEÍDO EN CÓDIGO]`
- **Fuentes:** demo (`generate_demo_emg_signal`, `main.py:1221`, ruido blanco), CSV, hardware (`hardware.emg_stream`, 19 % cobertura).
- **Clasificación:** MDF → REAL sobre señal real; **sobre el demo es ≈ fs/4** (`[EJECUTADO]`: MDF 224–232 Hz) y `fatigue_index` queda en 0 → **ROTO PERO HONESTO** (declarado en `emg_analyzer.py:21-26`, en `_EMG_VALIDATION_DETAIL` y no persistido); activación → HEURÍSTICO (la UI la llama "activación muscular real" al guardar, pero es una razón media/máximo de ruido).
- **UPS:** `[EJECUTADO]` guardó `activation` (17.1 %) + `median_frequency` (224.6 Hz) + 4 derivados = 6 descriptores musculares, `SIMULACION`. `fatigue_index` no se envía (por diseño).
- **AppTest:** renderiza, 0.7 s; cobertura 92 %.

### 4.8 HRV Analysis — `main.py:2276`, `rsa_panel.py`, `hrv_nonlinear_panel.py`

- **Qué calcula:** SDNN, RMSSD, pNN50 (`main.py:2324-2328`), LF/HF por `rr_spectrum` (`rsa.py`), RSA (`detect_rsa`), SampEn / DFA α1 / Poincaré SD1-SD2 (`hrv_nonlinear.py`). Insignia `VALIDATED` (Task Force ESC/NASPE 1996). `[LEÍDO EN CÓDIGO]`
- **Fuente:** por defecto, RR **extraídos con TKEO de un ECG sintético con RSA** (240 s, McSharry); alternativa: serie RR manual (entrada real). Declarado en pantalla ("No es un registro de un paciente"). La vista "Simulación" inyecta `np.random.normal` (rotulada "sterile demo"). `[LEÍDO EN CÓDIGO]`
- **Clasificación:** SDNN/RMSSD/pNN50 → REAL (Task Force) sobre RR SIMULADO; LF/HF → REAL; RSA/no lineales → REAL con alcance declarado (`PENDING_VALIDATION`: validados contra ground truth sintético, "no es un índice de riesgo"); "Analizar Entropía" → **FACHADA**.
- **UPS:** `[EJECUTADO]` "cardiovascular: 7 descriptores"; mapeo `[LEÍDO EN CÓDIGO]` (`main.py:2207-2260`): `hrv ← SDNN` (proxy, no RMSSD) y `heart_rate ← 60000/mean_nn`. **AppTest:** renderiza, 1.0 s. Cobertura `rsa.py` y `hrv_nonlinear.py` 100 %.
- **Deuda:** la vista "Educativa" son 2 frases + `line_chart`; textos mezclan inglés.

### 4.9 Biomarkers Lab — `main.py:652`, `app/supermodules/biomarkers.py` (314 l)

- **Qué calcula:** `BiocoreEngine`: Stress Index = LF/HF normalizado linealmente 0.5→5.0 (`:66`), Recovery Index = 0.40·FC + 0.45·RMSSD + 0.15·sueño (`:74`), Cognitive Load = 0.7·θ/α + 0.3·sobresalto de FC (`:205`), Resilience (`:212`), Learning Readiness (depende del PLV), **PLV neurocardíaco** real (Hilbert, theta 4–8 Hz vs HF-HRV, ≥180 s, `:110`). `[LEÍDO EN CÓDIGO]`
- **Clasificación:** los 4 índices → HEURÍSTICO ETIQUETADO (insignia "sin calibración de dispositivo"; rangos de normalización y cortes 65/35/45/75/70/75/65 sin cita); **PLV → REAL pero siempre `available=False` en la UI**, porque el lab no recibe señal cruda ECG+EEG (5 menciones "no disponible" en pantalla `[EJECUTADO]`), y Learning Readiness cae en cascada. Aviso permanente: "Modo demostración… Ningún número aquí debe leerse como una medición real."
- **Entradas muertas visibles** y rotuladas "sin efecto": Picos EDA, Conductancia, Poder HF, Coherencia, `bp_variance`, `ppg_pulse_transit_time_var`, `metabolic_efficiency` (`main.py:744-746, 786-787`); pestaña manual "💧 Piel (EDA)" sin módulo EDA detrás. `sleep_hours` se fija en 7.5 en modo manual (`:799`). `[LEÍDO EN CÓDIGO]`
- **UPS:** no escribe. **AppTest:** renderiza, 0.8 s, 4 métricas; cobertura 93 %.

### 4.10 Calculadoras Clínicas — `clinical/calculators.py` (649 l) + `calculators/pages.py` (550 l)

- 6 pestañas: ECG (QTc Bazett/Fridericia/Framingham/Hodges, umbral QTc, regla de papel, eje QRS), Hemodinamia (MAP objetivo, shock index, Forrester), Oxigenación (gradiente A-a, ISA, Berlin), Antropometría (BMI OMS, BSA Mosteller/DuBois), Escalas (NEWS2, qSOFA, GCS), Informe (PDF/HTML). Cada fórmula con su `*_CITATION` (`calculators.py:40-126`). El eje QRS reutiliza `qrs_axis_from_net` (no hay fórmula propia). `[LEÍDO EN CÓDIGO]`
- **Clasificación:** REAL (fórmula publicada). Tests con verdad independiente (`test_clinical_calculators.py`, 92 % de cobertura). `[EJECUTADO]` "Generar informe" produjo PDF+HTML (borrados). **AppTest:** renderiza, 0.8 s. Sin UPS.
- Nota: `qtc_fridericia/framingham/hodges` y `rr_seconds_from_hr` figuran sin llamadores *externos* porque la página los usa por el dispatcher interno. `[LEÍDO EN CÓDIGO]` (marcados en §9 como "uso interno").

### 4.11 Patient Pipeline — `main.py:2459`

- Crea un `DigitalTwinOrganism`, aplica la entrada manual y guarda un snapshot `SIMULACION` (`source_detail="patient_pipeline:entrada_manual"`), más una `ClinicalImpression` humana (categoría, notas, autor genérico) ligada al `snapshot_id` ("Juicio humano, no una medición… no lleva confianza numérica"). `[EJECUTADO]` "Estado guardado — snapshot…". **AppTest:** renderiza, 0.7 s. Persistencia `clinical_db` retirada del flujo vivo; los comentarios dicen que `clinical_states.db` "se conserva sin borrar", pero **ese archivo no existe en el repo** (ni trackeado ni en disco) `[EJECUTADO]` (`ls`, `git ls-files`).

### 4.12 Laboratorio 3D — `model3d/pages.py` (606 l) + `panels.py`

- 6 pestañas, cada una con su nivel: TC/RM→malla (preset pulmón **verificado en 1 sujeto**: volumen −1.9 %, distancia media 1.2–1.3 mm `[EJECUTADO]` en pantalla), visor de malla con chequeo de cierre, **VCG 3D (n=1, PTB s0010)**, mapa EEG por spline de Perrin 1989 con sobreoscilación declarada, ML de cohortes **exploratorio** con guardia anti-fuga por ID, anatomía de referencia **no reactiva** (`MODULE_VALIDATION_LINE`, `pages.py:53-58`). `[LEÍDO EN CÓDIGO]`
- **Honestidad extra:** el EEG de ejemplo se elige "por su alfa", no por hipnograma, y no se presenta como "persona relajada". Ejemplo WDBC (569 pacientes): AUC/permutación reportados con aviso. **AppTest:** renderiza, 1.0 s; botones de ejemplos sin excepción. Sin UPS.

### 4.13 Fuera del menú

- `app/ecg_trainer.py` (289 l, 0 % cobertura): app independiente (`streamlit run app/ecg_trainer.py`, citada en `main.py` raíz). `[NO PUDE VERIFICAR: no la ejecuté]`.
- `main.py` raíz (643 l): pipeline CLI legado con datasets sintéticos; sin tests propios. `[LEÍDO EN CÓDIGO]` (cabecera).

---

## 5. PROCESAMIENTO DE SEÑAL

| Analizador | Ubicación | Qué calcula | Validación (contra qué) | Prov. |
|---|---|---|---|---|
| `ECGAnalyzer` | `clinical/ecg_analyzer.py:98` (1289 l) | TKEO R-peaks (`:258`), HR con confianza y compuerta (`:833`), PQRST (`:691`), intervalos (`:737`), ST (`:785`), patrón clínico (`:1058`), HRV (`:1181`); `detect_pacemaker_spikes` (`:549`) **retirado del flujo** (aliasing) | 6 rondas con el experto, 25 registros MIT-BIH; bancos en `docs/validation/…` (no re-corridos). Cobertura pytest 38 % | L; D |
| Detector BBB | `clinical/bbb_detector.py:509` + `qrs_delineation.py` | RBBB (RSR′ y qR atípico con salvaguarda V6) / LBBB / indeterminado, sobre V1 y V6 **del mismo latido** | Criterio verbatim del validador (2026-08-12); matriz de confusión contra **50 casos PTB-XL** (test pasa); cobertura 97 % | L+E |
| `TwelveLeadAnalyzer` | `src/signals/ecg/twelve_lead_analyzer.py` | Eje QRS (Einthoven `atan2(2·aVF, √3·I)`), ST, bloqueos, ondas | Tests con casos canónicos; 82 % | L+E |
| RSA | `src/signals/ecg/rsa.py` | `detect_rsa`, LF 0.04–0.15 / HF 0.15–0.40, interpolación RR a 4 Hz | Task Force; ground truth sintético; 100 % | L+E |
| HRV no lineal | `src/signals/ecg/hrv_nonlinear.py` | SampEn (Richman-Moorman 2000), DFA α1 (Peng 1995), Poincaré (Brennan 2001); declinan con motivo si hay <200 latidos o SD<4 ms | Ground truth sintético (ruido blanco, 1/f…); `PENDING_VALIDATION`; 100 % | L+E |
| VCG | `src/signals/ecg/vcg.py` | Kors → loop XYZ, ángulo QRS-T | 1 paciente real (PTB s0010, Frank simultáneo) | L |
| `EegAnalyzer` | `src/signals/eeg/eeg_analyzer.py:308` | Welch, band power, BAR/DAR/TBR, rechazo de artefactos | Umbrales con cita (§8); constantes de artefacto calibradas contra el generador; 96 % | L+E |
| χ aperiódico | `spectral_model.py:330` | FOOOF 1.1.1 (deprecado), corrección del bandpass `|H|⁴`, gates de 30 ventanas y R²≥0.80 | Recuperación de χ sobre 1/f sintético (error máx 0.175); **no** contra EEG real | L+E |
| mu-ERD / engagement | `erd_detector.py:234`, `engagement_detector.py:165` | ERD% en 8–13 Hz vs baseline; β/(α+θ) relativo al reposo del sujeto (Pope 1995) | Generador con eventos de imaginería motora; 96 % | L+E |
| PLV neurocardíaco | `biomarkers.py:110` | Fase theta frontomedial vs HF-HRV | Criterio del validador (≥180 s); en la UI siempre "no disponible" | L+E |
| `EmgAnalyzer` | `src/signals/emg/emg_analyzer.py:79` | Activación, MDF, fatiga | Fórmula heredada; sin firma de constantes | L |
| `RespiratoryAnalyzer` | `src/signals/respiration/respiratory_analyzer.py:61` | Respiraciones, FR, apneas, AHI, SpO₂, severidad | **Roto** (§4.5) | L+E |
| `PatientRiskPredictor` / `AnomalyDetector` | `src/ai/patient_analytics.py:11, 214` | Pesos fijos, sin entrenamiento | — | L |
| `cohort_map` | `src/ml/cohort_map.py` | PCA, k-means, Isolation Forest, RF con guardia anti-fuga | Exploratorio; 95 % | L+E |

**Generadores demo.**
- `DynamicECGGenerator` (McSharry 2003): respeta la FC pedida; error de recuperación 0.00–0.12 bpm entre 40–200 lpm según docstring + test. Limitación: señal limpia, morfología única por ritmo. `[LEÍDO EN CÓDIGO]`+`[EJECUTADO]`(test)
- `EegSignalGenerator` (`eeg_generator.py:177`): patrones por banda, parpadeos, eventos de imaginería motora; las constantes de rechazo de artefactos se calibraron contra él, de modo que **son circulares hasta tener EEG real**. `[LEÍDO EN CÓDIGO]`
- `generate_demo_emg_signal` (`main.py:1221`): **ruido blanco** ⇒ MDF≈fs/4, `fatigue_index≈0` (no ejerce la fórmula). `[EJECUTADO]`
- `RespiratorySignalGenerator`: 7 patrones; 40 % de cobertura; la FR detectada no coincide con la pedida (§4.5).
- Generadores de PPG/SpO₂/respiración/temperatura/PA en `app/utils.py`: demo plano. `twelve_lead_generator.py` (465 l, 31 % cobertura, **con ediciones sin commitear del usuario**). `app/utils/data_generator.py`: dormido (§9).
- Datos reales presentes: `ptb_s0010.npz`, `cap_n16.npz`, TC s1397 y mallas (todos con licencia/atribución en sus README). Los registros MIT-BIH/PTB-XL de la app se bajan de PhysioNet en ejecución; `[NO PUDE VERIFICAR: si los tests que dicen cargar PTB-XL usan red o una caché]` — pasaron (§7).

---

## 6. APRENDIZAJE

- **Quiz:** 16 preguntas fijas en `learning_engine.py`; ECG-12 trae su propio quiz (`verify_quiz`), EEG 5 preguntas (`page_content.py:840-871`), Respiratory una pestaña "❓ Cuestionario" (no conté). Todos **deterministas**; la nota no depende de IA. `[LEÍDO EN CÓDIGO]`+`[EJECUTADO]`
- **Teoría:** tabla de 12 derivaciones (`educational.ecg_academy.lead_explanations`), referencias EEG/respiratorias en texto estático, `ECGTutor` (434 l) solo lo usa `ecg_trainer.py`. `[LEÍDO EN CÓDIGO]`
- **Casos clínicos:** modo ciego en Twin OS (`render_clinical_case_mode :1351`): 15 escenarios, opciones diagnósticas por "vecinos clínicos" (`_diagnostic_options :1132`), evaluación determinista (compara el escenario oculto con el elegido), PA modelo solo para 3 escenarios, horizontes evaluables por escenario (`EVALUABLE_HORIZONS_BY_SCENARIO`). Academia añade casos sintéticos con feedback IA. `src/clinical/case_database.py` (670 l, 0 % cobertura, `np.random` según `main.py:1238`) alimenta la fuente "caso clínico" del ECG Monitor. `[LEÍDO EN CÓDIGO]`
- **IA real:** 3 llamadas a `client.messages.stream` — narrador (`narrator/client.py:63`), causal (`causal.py:189`), findings (`findings.py:112`) — modelo **`claude-opus-4-8`** (`client.py:21`), `max_tokens=4096`, sin modo simulado: sin clave lanzan `NarratorNotConfiguredError` y la UI lo dice. Usos en UI: narrador clínico, razonamiento causal, pestañas "IA" de EMG/ECG/Multisensor/HRV, feedback de quiz y de casos de Academia. Clave por sesión en `st.session_state` (nunca `os.environ`), validada con `models.retrieve`. `[LEÍDO EN CÓDIGO]`+`[EJECUTADO]` (sin clave: avisos). **Nunca llamé a la API** (no hay clave) → `[NO PUDE VERIFICAR: que el id `claude-opus-4-8` exista y que una narración real salga bien]`. El docstring de `client.py:6-7` ("nunca pasada desde la UI") quedó obsoleto tras `ai_session.py`.
- **Determinista vs IA:** todo cálculo, nota y umbral es determinista; la IA solo redacta sobre datos estructurados del UPS/labs (prompt con reglas de anclaje).

---

## 7. CALIDAD

- **pytest:** 1165 tests recolectados en 71 archivos (856 `def test_` + parametrización). `[EJECUTADO]`
  - Corrida #1 (HEAD limpio, sin cobertura): **1164 passed, 1 failed, 0 skipped**, 183 warnings, **321.37 s (5:21)**. El fallo: `test_tanda2d_eeg_map_cohort.py::test_ordered_id_no_longer_gives_a_silent_auc_of_one` → `ImportError: DLL load failed while importing _k_means_common: An Application Control policy has blocked this file` (scikit-learn, Windows). 
  - Corrida #2 (con cobertura, mismo working tree + ediciones ajenas): **1165 passed**, 383 warnings, **321.17 s**. El mismo test pasó ⇒ **intermitente de entorno** (política de control de aplicaciones de Windows), no de código.
  - Una corrida previa con `--cov` por defecto (tracer clásico) avanzó apenas ~10 % en varios minutos y la interrumpí (no cuenta como resultado); con `COVERAGE_CORE=sysmon` (Python 3.13) la cobertura no añadió tiempo medible (321.17 s vs 321.37 s).
- **Más lentos:** `test_bbb_detector_confusion_matrix_against_50_real_ptbxl_cases` 28.8 s; luego WDBC 9.5 s, malla de pulmón 8.3 s, render de labs firmados 8.1 s, FOOOF 4–6.5 s por χ (4 parámetros). `[EJECUTADO]`
- **Cobertura (pytest-cov, líneas):** total **62 %** (16 630 sentencias, 6 327 sin cubrir). Por paquete: `domain` 89.7 %, `biomedical` 74 %, `clinical` 69.6 %, `app` 64 %, `src` 56.6 %, `dashboards` 56.6 %, `visualization` 40.7 %, `educational` 36 %, `signals` 19.7 %, `hardware` 19.2 %. `[EJECUTADO]`
  - Sin ningún test: `app/ecg_trainer.py`, `src/clinical/case_database.py`, `visualization/ecg_annotations.py`, `ecg_clinical_plot.py` (0 %). Muy bajos: `src/ai/explainability.py` 9 %, `data_generator.py` 13 %, `esp32_stream.py` 17 %, `emg_stream.py` 19 %, `src/ai/ecg_cnn.py` 17 %.
  - `builder.py` 100 %, `composer.py` 95 %, `coupling/bridge.py` 92 %, `closed_loop.py` 90 %, `bbb_detector.py` 97 %, `calculators.py` 92 %, `hrv_nonlinear.py`/`rsa.py` 100 %.
- **Lección de la cobertura:** `respiratory_analyzer.py` tiene 74 % y está roto. Líneas ejecutadas ≠ valores verificados; las pruebas de render no fijan números clínicos.
- **Dependencia de red en tests:** los tests de PTB-XL/BBB pasaron; no determiné si bajan de PhysioNet o usan caché (`PtbxlUnavailableError` existe como falla explícita). Si se corren sin red, `[NO PUDE VERIFICAR]` qué pasa.
- **Warnings de ecosistema:** fooof deprecado a favor de `specparam`; `fpdf` `ln=` deprecado (`reporting.py:400`); wfdb con `Pandas4Warning`; y Streamlit avisa que `use_container_width` "will be removed after 2025-12-31" (fecha ya vencida) en varios puntos de `twin_shell`. Con `streamlit>=1.25` sin tope, un `pip install` futuro puede romper esos usos. `[EJECUTADO]` (logs) + `[LEÍDO EN CÓDIGO]` (requirements).

---

## 8. VALIDACIÓN CLÍNICA — TABLA ÚNICA

Estados: **VALIDADO** (firma del experto o fuente citada y aplicada), **PROVISIONAL / PENDIENTE** (marcado así en el código), **INGENIERÍA** (calibrado contra sintético, sin cita clínica), **SIN CITA**. "Dónde" = archivo:línea.

| Umbral / constante | Valor | Cita / origen | Estado | Dónde se usa | Prov. |
|---|---|---|---|---|---|
| BAR basal / arousal | 0.8–1.2 / **>1.8** | Schutter 2006; Handbook of Psychophysiology 3ª ed. cap. 10 | VALIDADO_POR_FUENTE | `eeg_analyzer.py:60-62`; ancla de la regla (`catalog.py:53`) | L |
| Acoplamiento arousal→FC | **+15.0 bpm** (rango citado +10 a +25) | Guyton & Hall 14ª ed. cap. 61 | VALIDADO_POR_FUENTE, conf 0.70 | `catalog.py:53-82`, `bridge.py:110` | L+E |
| Confianza regla no firmada | 0.35 | — | Convención | `bridge.py:102` | L |
| Ventana de arrastre de FC | **120 s** | Config del compositor | INGENIERÍA (no firmada) | `composer.py:78` | L |
| DAR | <1.5 / 1.5–3.0 / ≥3.0 | Claassen 2004, Clin Neurophysiol 115:2699 | VALIDADO_POR_FUENTE (2026-09-10); definido sobre Welch (cambiar motor reabre) | `eeg_analyzer.py:91-95`, `classify_dar :207` | L |
| TBR | <1.5 / 1.5–3.0 / ≥3.0 | Boksem, Meijman, Lorist 2005 (reemplazó a Monastra 2001) | VALIDADO_POR_FUENTE | `eeg_analyzer.py:120-124`, `:224` | L |
| χ aperiódico | <1.0 exc. / 1.0–1.6 indeterminado / >1.6 inhib. | Gao, Peterson, Voytek 2017 (LFP→EEG por analogía) + Donoghue 2020 (algoritmo) | VALIDADO_POR_FUENTE con cláusula de alcance | `spectral_model.py:276-307` | L |
| Error de instrumento de χ | 0.175 | Medición propia (pipeline real) | Medido, sintético | `spectral_model.py:276` | L+E |
| `MIN_CHI_CLEAN_WINDOWS` | 30 | Calibración sobre sintético | INGENIERÍA | `spectral_model.py:223` | L |
| `MIN_APERIODIC_R_SQUARED` | 0.80 | Calibración sobre sintético | INGENIERÍA | `:117` | L |
| Rechazo de artefactos | 5500 µV/s, ventana 1 s | Calibrado contra el generador demo | INGENIERÍA (recalibrar con hardware) | `eeg_analyzer.py:140-151` | L |
| Duración limpia mínima EEG | 2.0 s | Espejo de MIN_PLV | INGENIERÍA | `eeg_analyzer.py:159` | L |
| Banda mu / engagement | 8–13 Hz; β/(α+θ) relativo al baseline; **solo signo** | Pope, Bogart, Bartolome 1995 | VALIDADO (firma); sin umbral de "cambio significativo" | `erd_detector.py:69`, `engagement_detector.py:54,93` | L |
| Bandpass EEG | 0.5–40 Hz, orden 2 | Convención | INGENIERÍA | `eeg/preprocessing.py:16-18` | L |
| BBB: QRS ancho | >120 ms | Validador clínico (2026-08-12) | VALIDADO (+50 casos PTB-XL) | `bbb_detector.py:141` | L+E |
| BBB: S en V6 (RSR′) | ≥40 ms y ≤−0.1 mV | Validador | VALIDADO | `:142-143` | L |
| BBB: qR atípico | q ≤−0.1 mV, R ≥0.5 mV, S V6 ≥40 ms y ≤−0.15 mV | Chou / Marriott (Fase 4) | VALIDADO | `:154-157` | L |
| LBBB: Q septal | > −0.05 mV | Validador | VALIDADO | `:144` | L |
| BBB: ancho a media amplitud | 80 ms | Decisión de implementación | SIN CITA | `:201` | L |
| pRR31 (FA) | x = 31 ms | Buś et al. (AUC 0.958) | Cita transcrita; punto de corte no citado | `ecg_analyzer.py:57` | L |
| Fracción pRR31 | 0.50 | Inspección del banco (sin 16–30 % / con 78–94 %) | **PROVISIONAL** | `:63` | L |
| Metrónomo / SDNN sinusal | 3 ms / 200 ms | — | **PROVISIONAL** | `:80-82` | L |
| Calidad Vpp | ventana 50 ms; CV 0.15 | Experto (sugerido) | **PROVISIONAL** | `:94-95` | L |
| `QUALITY_THRESHOLD` | 0.6 | — | **PROVISIONAL** (y comentario "no cableado" obsoleto) | `:27` | L |
| Detector TKEO | 5–15 Hz + TK + refractario | 6 rondas, 25 registros MIT-BIH | VALIDADO (docs) | `ecg_analyzer.py:258` | D |
| SDNN, RMSSD, pNN50 (>50 ms) | — | Task Force ESC/NASPE 1996 | VALIDATED (insignia) | `main.py:2324-2327` | L |
| Bandas LF/HF | 0.04–0.15 / 0.15–0.40 Hz | Task Force | VALIDADO | `rsa.py:53-54` | L |
| SampEn / DFA α1 / Poincaré | m,r estándar / escalas / SD1-SD2 | Richman-Moorman 2000 / Peng 1995 / Brennan 2001 | PENDING_VALIDATION (ground truth sintético) | `hrv_nonlinear.py:41-49` | L |
| Mínimos de RR | SD ≥4 ms; ≥200 latidos | Calibración propia | INGENIERÍA | `hrv_nonlinear.py:66` | L |
| AHI: cortes | 5 / 15 / 30 | AASM | VALIDADO (cortes) — **detector roto** | `respiratory_analyzer.py:378-389` | L+E |
| AHI: promoción por SpO₂ <85 % | → "moderate" | — | SIN CITA | `:382` | L |
| Duración mínima de apnea | **1 s** (AASM: 10 s) | `apnea_threshold/10` | **Contradice la cita** | `:262, 276` | L |
| Umbrales de evento del organismo | FC 120/40 (150/35 crítico), HRV 20, SpO₂ 90/95, estrés 75, fatiga 80 | Reusados del motor; la UI de riesgo cita ACLS/ATLS, NEWS2, AASM | HEURÍSTICO con cita parcial | `builder.py:431-548` | L |
| MDF basal / span (fatiga EMG) | 120 Hz / 60 Hz | Heredado | **PENDIENTE** de firma | `emg_analyzer.py:42-43` | L |
| Activación EMG | media|x|/máx|x| | Propia | HEURÍSTICO | `emg_analyzer.py:92` | L |
| Rangos de índices de Biomarkers | LF/HF 0.5–5; FC 45–90; RMSSD 10–100; sueño 4–9; cortes 65/35/45/75/70/75/65 | Sin cita | HEURÍSTICO ("sin calibración de dispositivo") | `biomarkers.py:66-247, 303-312` | L |
| Health Score multisensor | bandas de FC 60–100→100, 50–60/100–120→80; defaults 50 | Propia | HEURÍSTICO ("no validado poblacionalmente") | `dashboards/multisensor.py:183-215` | L |
| PA de referencia por escenario | healthy 120/80; hipertensión 130/80 (ACC/AHA 2017); sepsis 85/55/65 (Sepsis-3; **la diastólica 55 se derivó**, nota "verificar"); apnea 200/100 (Harrison/AASM, pico de arousal); … 12 escenarios | Citas por entrada | VALIDADO con salvedades en `phase_note` | `blood_pressure_references.py:67+` | L |
| PAM | DBP + ⅓(SBP−DBP) | Fórmula estándar | VALIDADO | `clinical_reference.py` (`estimate_map`) | L |
| Hemodinámica: SV ref / FC ancla / EDV sano / techo | 70 mL / 72 / 120 mL / 180 mL (1.5×) | Guyton | VALIDADO (Rondas 1–2) | `physiological_flow.py:100`, `frank_starling.py:118,123`, `diastasis_ceiling.py` | L |
| Hemodinámica: Rp, Rd, Pd, P_sf | 0.109 / 0.979 / 2.0 / 7.0 | Guyton cap. 20; Westerhof | VALIDADO (2026-07-31) | `physiological_flow.py:119-148`, `closed_loop.py:188` | L |
| Hemodinámica: **C** | **0.8073 mL/mmHg** | Calibrado por bisección para PP≈40 | **PENDIENTE ESTRUCTURAL** | `physiological_flow.py:157` | L |
| Capacitancia venosa en sepsis | ×2.0 | "Aceptado pero no citado" | **SIN CITA** | `closed_loop.py:207` | L |
| Barórreflejo | k=1.0; mecanismo Guyton cap. 18 | Cita de mecanismo | Flag de pendiente = False | `baroreflex.py:84-102` | L |
| Confianza de PA modelo | 0.75 | Criterio documentado | Convención | `closed_loop_ups_bridge.py:113` | L |
| Trayectoria de sepsis (fases por horizonte) | tabla | Citas por fase | `PENDING_VALIDATION`; regla de declinación de PA **firmada** (commit `cd693e6`) | `sepsis_trajectory.py:24-54` | L+D |
| Tipos de arritmia (FA, flutter 2:1, TSV, bradicardia) | rangos de FC | Citas | `PENDING_VALIDATION` | `arrhythmia_types.py:22,47` | L+E |
| Waypoints de escenarios | FC, HRV, GC, etc. | Sin cita de magnitud | 26 marcas `PENDING_VALIDATION` | `simulation_engine.py:470-614` | L |
| QTc (4 fórmulas), umbrales QTc/500 ms, papel ECG, eje QRS, MAP objetivo, shock index, Forrester, BMI OMS, BSA, Berlin, A-a, ISA, NEWS2, qSOFA, GCS | fórmulas/escalas publicadas | `*_CITATION` en `calculators.py:40-126` | VALIDADO por cita; tests con verdad independiente | `calculators.py` | L+E |
| VCG 3D / pulmón 3D | n=1 | TotalSegmentator; Frank PTB | Verificado en 1 sujeto | `model3d/pages.py:53-58` | L+E |

---

## 9. MUERTO, DORMIDO O HUÉRFANO

Método: (a) alcanzabilidad estática por imports desde `app/main.py` incluyendo imports perezosos, el módulo legado `app/utils.py` y los `page_content.py` cargados por `runpy`; (b) escaneo AST de `def`/`class` de nivel superior contando referencias fuera de su archivo y en tests; (c) grep de llamadores para cada caso del listado. `[EJECUTADO]`

**Módulos que la app viva no importa:**
- `biomedical/` (`reasoning_engine.py`, `arrhythmia_classifier.py`; solo `tests/test_reasoning_engine_new.py` y `test_arrhythmia_classifier_new.py` los usan). CLAUDE.md los declara "ganadores" y dice que los usan `app/bio_reasoning_streamlit.py`/`reasoning_engine_streamlit.py`, **archivos que no existen**. `ARCHITECTURE.md` documenta este motor.
- `visualization/ecg_annotations.py`, `ecg_clinical_plot.py`, `educational_panel.py`, `medical_grid.py` (sin importadores en `app/src/domain/clinical/educational`). El otro "ganador" de CLAUDE.md, `visualization/medical/plotly_clinical.py`, **sí** se usa pero solo por imports perezosos en `app/utils.py:67,381`.
- `app/ecg_trainer.py` (entrypoint aparte, 0 % cobertura), `main.py` raíz (CLI), `example_reasoning_engine.py`, `install_dependencies.py`, `tools/*` (scripts offline legítimos).
- Verificadores sin llamador de la app: `hemodynamics/ups_bridge.py` (R-RCR estático), `*_comparison.py` (4), `context_comparison.py`.

**`app/utils.py` y `app/utils/` conviven.** El paquete `app.utils` carga el archivo `utils.py` por `exec_module` en su `__init__` (`app/utils/__init__.py:28-46`) con `except Exception: pass`. Frágil: si `utils.py` fallara al importarse, desaparecerían `safe_import_*` sin error visible. `render_metric_explained`, `render_view_selector`, `render_discovery_lab` están **definidos dos veces** (`main.py:270,287,357` y `utils.py:440,458,487`).

**`app/utils/data_generator.py` (516 l):** reexportado en `app/utils/__init__.py:7` y `app/supermodules/__init__.py:13` (se importa al arrancar), pero `generate_sample_patient`, `generate_measurement_history` y `generate_ecg/eeg/emg/respiratory_signal` no tienen **ningún llamador** fuera de sí mismo (grep), cobertura 13 %. Dormido. `generate_metabolic_profile()` ya no existe y `test_hygiene_short_signal_and_ghosts.py:135-145` lo vigila.

**Funciones/clases sin ninguna referencia (ni en su archivo ni en tests):** `render_metrics_grid` (`main.py:533`), `validate_time_window` (`app/utils.py:249`), `feature_importance_summary` (`src/interpretability.py:317`), `RiscoIndicador` (`src/risk_analysis.py:16`), `DynamicEcgResult` (`dynamic_ecg_generator.py:75`), `annotate_ax` (`visualization/ecg_annotations.py:204`), `step_by_step_assistant` y `arrhythmia_examples` (`educational/ecg_academy.py:110,152`), `PersistenceMixin` (`educational/learning_engine.py:165`), `normalize_amplitude`, `detect_sampling_rate` (`signals/loaders/universal_loader.py:191,213`), `download_mitbih_record` (`signals/loaders/wfdb_loader.py:110`).

**Dormidos con uso solo interno/demo:** `SignalExplainer` (`src/ai/explainability.py`, 9 % cobertura), `AdaptiveQuizEngine` (`patient_analytics.py:335`), `ecg_cnn.py`/`temporal_models.py` (dependen de `torch`, que no está en requirements), `src/rural_health/offline_support.py` (segundo esquema SQLite; solo un test de PDF), `src/ecg_education.py`, `src/machine_learning.py`, `src/signal_generator.py`, `src/advanced_hrv.py` ("sigue huérfano", reemplazado por `hrv_nonlinear.py`), clases `AutonomicDetail/StressState/RecoveryState/PerformanceState` de `digital_twin_organism.py` (definidas sin uso externo), `CausalityEngine` (retirado; solo comentarios), escenario `taquicardia_estres` ("ningún menú la usa, solo tests").

**Lo que pediste confirmar:**
- `data_generator.py`: dormido (arriba).
- `metabolic_recovery`, `generate_metabolic_profile()`, `SleepState`: **no existen en el código**; solo permanecen como aserciones negativas en `test_hygiene_short_signal_and_ghosts.py:135-145`. No hay "SleepState congelado": fue eliminado.
- Dominio metabólico del UPS: no existe.
- `fatigue_index` EMG: calculado pero no persistido (diferido).
- Hallazgo (§4): `CLAUDE.md` y `SETUP.md` listan hubs "Research/Simulation/AI/Hardware" que no existen en `HUBS`.

---

## 10. CONTRASTE DOCS vs. REALIDAD

El **Plan Maestro no está en el repo** y tampoco `PLAN.md` (referido por `CLAUDE.md` y por docstrings de `domain/`) `[EJECUTADO]` (`ls`). Contrasté `README.md`, `CLAUDE.md` (ambos de 2026-10-25), `SETUP.md`, `ARCHITECTURE.md` (de 2026-09-21), `.streamlit/config.toml`, docstrings y `CHANGELOG.md`.

| El doc dice | El código hace |
|---|---|
| README: "Los tres hubs: Digital Twin OS, Clinical Hub, Learning Hub" | **4 hubs**: falta Laboratorio 3D. SETUP.md y `.streamlit/config.toml` hablan de "Learning/Clinical/Research/Simulation/AI/Hardware hubs" y "17 entradas sueltas en app/pages/": no existen |
| README: "detección de bloqueos de rama validada contra el MIT-BIH" | La validación del BBB es contra **50 casos PTB-XL** (`test_bbb_detector_confusion_matrix_against_50_real_ptbxl_cases`); MIT-BIH valida el detector de FC/QRS |
| README: "electromiografía con activación fisiológica real" | Activación = media/máximo de la señal filtrada (no %MVC); el demo es ruido blanco |
| README/ARCHITECTURE: "motor hemodinámico basado en svZeroDSolver" | Reimplementación analítica de las ecuaciones RCR; `svzerodsolver` no es dependencia; `THIRD_PARTY_NOTICES.md` (citado) no existe |
| CLAUDE.md: "UPS: dominios cardiovascular y respiratorio (los únicos modelados)" y "Solo dibuja los dos dominios" | 4 dominios modelados desde Capa 5A; la UI aún dice "solo cardiovascular y respiratorio" (`pages.py:1605`) |
| CLAUDE.md: ganador del motor de razonamiento = `biomedical/reasoning_engine.py`, usado por `app/bio_reasoning_streamlit.py` y `app/reasoning_engine_streamlit.py` | Esos dos archivos no existen; `biomedical/` no lo importa la app |
| CLAUDE.md: "`pages_legacy/` … 9 archivos en uso vía `runpy`"; "AI Hub de `app/main.py`" | `pages_legacy/` no existe (contenido reubicado a `*/page_content.py` el 2026-07-13); el AI Hub se eliminó |
| CLAUDE.md: "narrador… esperando confirmación del usuario" | Está en producción y tiene clave por sesión; `client.py:6-7` aún dice "nunca desde la UI" |
| `ARCHITECTURE.md`: Biomedical Reasoning Engine (HRV→hipótesis→diagnóstico diferencial) como arquitectura | Es el módulo `biomedical/` que la app no usa; la arquitectura real es el UPS |
| `coupling/engine.py`: "dormido… catálogo vacío… nada lo importa" | Catálogo con 1 regla activa y dos llamadores |
| `clinical/ecg_analyzer.py`: "la escritura ECG→UPS sigue sin cablear" | Cableada (`main.py:1473`) |
| Docstrings de hemodinámica: "12 escenarios… los otros 9" | `SimulationScenario` tiene 15 (tras Unificaciones 1 y 2) |
| Respiratory Lab: "VALIDATED — AHI y severidad conformes a AASM" | FR constante 60, AHI siempre 0, umbral de apnea de 1 s (§4.5) |
| "Analizar Entropía y Complejidad" (`utils.py:479`) y comentario "sí calcula algo real" | Calcula `|media(diff(x))|`: seno puro 0.00000, ruido blanco 0.00002, seno+deriva 0.00200 (`[EJECUTADO]`); no es entropía ni complejidad |
| "Explicabilidad (SHAP/LIME real…)" / docstring "SHAP/LIME real" | Heurística de desviación contra baseline; admitido solo en la 3ª pestaña |
| "Riesgo cardiovascular (ML real…)" | Suma ponderada fija, sin entrenamiento |
| CHANGELOG (último: 2026-11-02, cierre de sepsis) | Coincide con `cd693e6`. `CHANGELOG.md` pesa 865 KB / 5 526 líneas: ya no es consultable a mano |
| README: "Requiere Python 3.10+" | Devcontainer 3.11, dev 3.13; solo 3.13 probado `[EJECUTADO]` |
| Academia: "quiz de 16 preguntas" | 16 en el pool; un usuario básico ve 5 |

---

## 11. PENDIENTES Y ROADMAP (ordenados por cuánto bloquean)

**A. Bloquean confianza en lo que ya se muestra / se escribe al UPS**
1. **Respiratory Lab:** FR constante 60, AHI=0 y escritura de ambos al UPS; umbral de apnea 1 s; sin hipopneas; sin test que fije valores (§4.5). *Anotado, no tocado.*
2. **"Analizar Entropía y Complejidad"** (4 labs): fórmula que no mide lo que dice (§Sorpresas #2).
3. **Etiquetas "SHAP/LIME real" y "ML real"** sobre heurísticas (§4.1).
4. **`PLAN.md`, Plan Maestro y `THIRD_PARTY_NOTICES.md` ausentes**: sin ellos no hay fuente de verdad escrita ni atribución BSD-3 de las ecuaciones tomadas de svZeroDSolver.
5. **Insignia VALIDATED en Respiratory Lab** y texto de validación de EMG ("umbrales sintéticos fijos") a revisar con el experto.

**B. Arcos abiertos**
6. **Hemodinámica:** compliancia `C` pendiente hasta modelar la **curva de eyección ventricular pulsátil**; capacitancia venosa de sepsis ×2 sin cita; sepsis temprana sin PA por diseño; 12 de 15 escenarios sin PA modelo (exercise bloqueado por bug de `recovery_progress`; stress/anxiety son picos transitorios; apnea/seizure por fase; arritmias sin driver de bombeo; hypoxia sin quimiorreceptor; fatigue/copd sin referencia).
7. **Capa 5A:** dominio autonómico no modelado; `fatigue_index` EMG sin persistir hasta recalibrar el generador (ruido blanco) o usar CSV/hardware; campos fantasma diferidos (`frontal/temporal_activity`, `recruitment_pattern`, `motor_symmetry`, `power_output`); el composer solo une neuro+cardio (no muscular/respiratorio); falta la dirección espejo (relajación→↓FC) y la política multi-regla.
8. **Acoplamiento "writer multi-dominio":** el escritor del EEG Lab seguirá siendo no-op mientras no envíe FC; la única vía viva es el botón del composer.
9. **EEG real / hardware:** constantes de χ, artefactos y R² están calibradas contra el generador; `esp32_stream.py` 17 % y `emg_stream.py` 19 % de cobertura; OpenBCI/ESP32 sin probar `[NO PUDE VERIFICAR: sin hardware]`; `SENSOR_REAL` nunca se produce en mis pruebas.
10. **Validación PENDING_VALIDATION:** trayectoria de sepsis, tipos de arritmia, 26 waypoints de `simulation_engine.py`, HRV no lineal, constantes provisionales de la compuerta ECG (pRR 0.50, metrónomo 3 ms, Vpp CV 0.15, calidad 0.6), MDF 120/60 del EMG.
11. **DAR/TBR/χ:** cerrados con firma (2026-09-10/18); su validez está atada al motor Welch actual — un cambio a CWT/FOOOF-first los reabre.

**C. Higiene / deuda**
12. Docstrings y mensajes obsoletos (coupling/engine, QUALITY_THRESHOLD, client.py, mensaje "solo cardio y resp", "12 escenarios", CLAUDE.md/SETUP.md/ARCHITECTURE.md).
13. `app/utils.py` ↔ `app/utils/` con `exec_module` y `except: pass`; funciones duplicadas; `data_generator.py` y ~15 funciones huérfanas (§9); `biomedical/` y 4 módulos de `visualization/` sin uso.
14. Requisitos sin congelar (solo `fooof==1.1.1`); `use_container_width` con fecha de retiro vencida; `fpdf ln=`; fooof deprecado; `torch` ausente para `src/ai`.
15. Persistencia: engine SQLite compartido entre sesiones (`cache_resource`) y efímero en Cloud; nombre de paciente en claro (`// TODO`); `author` genérico (`// TODO`); `EventRecord.provenance` String(20) < 21 caracteres; `get_value_history` ordena por timestamp.
16. Test flaky de entorno (scikit-learn bloqueado por Application Control de Windows).
17. `claude-opus-4-8` sin verificar; ningún test llama a la API real.
18. `case_database.py` (0 % cobertura) usa `np.random` y alimenta una fuente del ECG Monitor.

---

## SORPRESAS

1. **Respiratory Lab devuelve una constante.** `respiratory_analyzer.py:236-239` resta números de orden de respiración (siempre 1) en vez de tiempos ⇒ **FR = 60.0** y variabilidad 0 en cualquier señal; la página muestra "Taquipnea RR 60/min" y "respiración periódica… apnea del sueño" para respiración normal. El detector de apneas no cuenta nada (desalineación `zip(starts, ends)` cuando la máscara arranca en `True`; probado con dos tramos planos de 19.6 s) y el umbral real sería de 1 s. **El botón "Guardar al gemelo" persiste FR=60 y AHI=0** al UPS. Insignia VALIDATED. 74 % de cobertura y 1165 tests en verde: ningún test fija esos números.
2. **"Analizar Entropía y Complejidad" no mide entropía.** `app/utils.py:483` calcula `|media(diff(señal))|` = `|x_final − x_inicial|/(N−1)`; la única que lo diferencia es la deriva. Seno puro 0.00000, ruido blanco 0.00002. Aparece en ECG, Multisensor, EMG y HRV, y su docstring dice "sí calcula algo real".
3. **"SHAP/LIME real" y "ML real" son heurísticas.** `lime_like_explanation` describe una perturbación local que no ocurre; `PatientRiskPredictor` no se entrena.
4. **El repo cita documentos que no existen**: `PLAN.md`, `THIRD_PARTY_NOTICES.md` (obligación de atribución BSD-3 si las ecuaciones de svZeroDSolver cuentan como derivadas).
5. **`CLAUDE.md` describe otro repo**: hubs que no existen, "ganadores" (`biomedical/reasoning_engine.py`, `visualization/...`) que la app viva no importa, y dos dominios cuando son cuatro.
6. **`render_error_state` traga las excepciones** de los labs cargados por `runpy` (solo `logger.error`): `at.exception` de AppTest no puede ver un fallo ahí. Un barrido por texto no encontró ninguno hoy, pero la red de seguridad de los tests de render es más fina de lo que parece.
7. **Comentarios que contradicen al código en ambos sentidos:** `ecg_analyzer.py` dice que la escritura ECG→UPS "sigue sin cablear" y lo está desde 2026-08-24; `coupling/engine.py` dice que nada importa el paquete de acoplamientos y lo importan dos llamadores; y el comentario de `main.py:70-72` sobre `clinical_states.db` apunta a un archivo que no existe.
8. **El 62 % de cobertura global esconde que el motor ECG "más validado" tiene 38 %** (se valida con bancos offline fuera de pytest) y que `domain/` (el núcleo) tiene 90 %.
9. **La regla de acoplamiento solo "existe" para el usuario si guarda EEG, guarda ECG/HRV, y pulsa "Componer" dentro de 120 s.** El camino del EEG Lab es una puerta que no puede abrirse por construcción.
10. **El fallo del test fue del sistema operativo**: Windows Application Control bloqueó una DLL de scikit-learn en una de dos corridas.
11. **Hay hardware escrito pero sin cobertura** (ESP32, EMG) y modelo de IA nombrado (`claude-opus-4-8`) que no pude comprobar que exista.

---

## Qué NO cubrí (límites honestos)

- No leí línea por línea `main.py` (2705 l), `twin_shell/pages.py` (2166 l) ni `CHANGELOG.md`; leí las funciones citadas, cabeceras y los puntos de escritura al UPS.
- No ejecuté: fuentes MIT-BIH/PTB-XL/ESP32/CSV del ECG Monitor, `app/ecg_trainer.py`, `main.py` raíz, las pestañas alternativas de cada radio/selectbox, ni ninguna llamada real a Anthropic.
- No re-corrí los bancos de validación de `docs/validation/` ni verifiqué la sensibilidad ">99 %".
- No leí `render_synthetic_case_section`, `ECGTutor`, `prediction_engine.py` ni `simulation_engine.py` completos.
- Streamlit Cloud: sin acceso.
- Las cifras de cobertura y tiempos son de esta máquina (Windows 11, Python 3.13.11).
