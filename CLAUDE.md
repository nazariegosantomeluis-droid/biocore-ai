# CLAUDE.md — BIOCORE AI

Guía de orientación rápida para cualquier sesión de Claude Code que trabaje en este repo. Ver `PLAN.md` para el estado de fases y `documentation/Nivel 00` y `documentation/Nivel 01` para la arquitectura objetivo (constitución, UPS, Digital Twin, etc. — son visión a largo plazo, no lo que existe hoy).

## Qué es esto de verdad, hoy

Un monolito Python + Streamlit ("Biomedical Signal Visualizer") que está en proceso de convertirse en "BIOCORE AI", un Biomedical Operating System. La documentación en `documentation/` describe la visión objetivo (10 generaciones, Unified Physiological State, Digital Human Twin 3D, AI Orchestrator). **Nada de eso está implementado todavía** salvo piezas parciales — ver `PLAN.md` para el gap analysis completo.

## Reglas de oro (no negociables)

1. No romper lo que funciona. Entender antes de refactorizar.
2. Trabajar por fases pequeñas, cada una ejecutable y probada. Nada de reescrituras "big bang".
3. IA real, no fingida: el razonamiento/explicaciones se generan con la API de Anthropic desde el backend, fundamentadas en datos reales. Prohibido texto hardcodeado disfrazado de IA (el ejemplo histórico de lo que NO hacer era `app/biomedical_tutor.py`, un `dict` de keywords — eliminado en Fase 1.3, refundido en `domain/physiology/narrator/`).
4. Simulación fisiológica ≠ dato falso: generar pacientes/escenarios sintéticos es una función deseada, pero debe etiquetarse siempre como simulación. Nunca presentar un valor inventado como si viniera de un sensor real.
5. Preguntar antes de decisiones grandes (borrar módulos, cambiar framework, elegir BD).
6. Todo elemento nuevo debe justificar su existencia contra el UPS/Digital Twin/valor educativo — si no, fusionar/rediseñar/eliminar.
7. Documentar en `PLAN.md` y marcar lo pendiente como `// TODO: integración real pendiente`.

## Stack real

- **Lenguaje/Framework**: Python + Streamlit (sin frontend JS separado, sin build step).
- **Paquetes**: `pip` + `requirements.txt` plano. No hay `pyproject.toml` propio.
- **Run**: `streamlit run app/main.py` (ver `run_local.ps1` / `RUN_BIOCORE.bat`). `app/streamlit_app.py` es solo un wrapper que reejecuta `main.py`.
- **Visualización**: matplotlib + Plotly. **No hay librería 3D real** para el Digital Twin — hoy es HTML/CSS cards (`app/supermodules/twin_shell/pages.py`).
- **IA**: `anthropic` SDK. Única integración real: `domain/physiology/narrator/` (Fase 1.3) — narrador clínico con streaming, modelo `claude-opus-4-8`, prompt construido desde datos estructurados del UPS (`build_context()`), nunca desde texto libre. Expuesto en la UI vía `app/supermodules/twin_shell/pages.py::render_clinical_narrator()` y el hub "AI Hub" de `app/main.py`. `app/ai_copilot.py` (JARVIS, código muerto) y `app/biomedical_tutor.py` (`BiomedicalTutor`, dict de keywords) fueron eliminados el 2026-07-02 — no reintroducir ese patrón. Antes de asumir que algo llama a Claude, verificar que pase por este paquete.
- **Persistencia**: dos capas que coexisten sin fusionar todavía. (1) El UPS (`domain/physiology/state/`) usa SQLite + SQLAlchemy en `data/biocore_ups.db` — implementado en Fase 1.1. (2) El resto de la app sigue con SQLite crudo (`sqlite3`, sin ORM) en dos esquemas incompatibles (`app/clinical_db.py` y `src/rural_health/offline_support.py`) — no tocado todavía, fusión diferida a una fase posterior de consolidación.

## Ganadores de duplicación (decididos 2026-07-02, ver `PLAN.md` Fase 0)

Estas decisiones aplican a todo trabajo nuevo. El resto de las copias no se ha eliminado todavía (se difiere a una fase de consolidación posterior) pero **no se debe construir sobre ellas**:

- **Señales**: gana `src/signals/` (paquete completo por modalidad). `signals/` (raíz) y el antiguo shim `domain/signals/` (ya eliminado) quedan fuera.
- **Motor de razonamiento**: gana `biomedical/reasoning_engine.py` (`BiomedicalReasoningEngine`) — es el que usan `app/bio_reasoning_streamlit.py` y `app/reasoning_engine_streamlit.py`. `src/reasoning_engine.py` (833 líneas) está diferido/huérfano — no extenderlo.
- **Capa clínica**: gana `clinical/` (`ECGAnalyzer`, `ecg12.py`) para análisis clínico. `src/clinical/case_database.py` se conserva (biblioteca de casos, sin equivalente en `clinical/`). `src/clinical/ecg_interpreter.py` está diferido para fusionar más adelante.
- **Visualización**: gana el paquete `visualization/` (en particular `visualization/medical/plotly_clinical.py`) para todo trabajo nuevo de la app Streamlit. `src/visualization.py` se mantiene intacto solo para el pipeline CLI de la raíz (`main.py`) — no mezclarlo con la app.

## Trampas conocidas (no construir sobre esto sin revisar primero)

- **`domain/`** es un scaffold de migración iniciado el 2026-07-01. El subpaquete `domain/signals/` (shim sin lógica propia) fue eliminado el 2026-07-02 — `main.py` (raíz) ahora importa directo de `src/`. El resto de `domain/` (`physiology/`, `patients/`, etc.) sigue siendo un scaffold mayormente vacío — no asumir que es la fuente de verdad todavía, salvo `domain/physiology/state/`, que es el destino intencional del UPS formal (Fase 1.1).
- **`app/components/digital_twins_ui.py`** fue eliminado el 2026-07-02 (era "3D" simulado, heatmap 2D + scatter, no conectado al flujo real). El twin real es `app/engines/digital_twin_organism.py` + `app/supermodules/twin_shell/`.
- **`pages_legacy/`**: solo quedan los 9 archivos con nombre emoji que sí están en uso vía `runpy.run_path()` desde `app/supermodules/{multisensor,education,patients,ai_analysis,emg_muscle_lab,eeg_neuro_lab,respiratory_lab,guides,ecg_12}/pages.py`. Los 13 archivos huérfanos/duplicados fueron eliminados el 2026-07-02. **No asumir que un archivo de `pages_legacy/` es huérfano sin grepear referencias a `pages_legacy` primero** — el informe de auditoría original se equivocó en esto.
- **`app/dashboard.py`**, **`app/config.py`**: eliminados el 2026-07-02 (estaban vacíos, no importados).
- **`shared/core`**: no existe en disco. Los imports fantasma (`try: from shared.core.utils import * except Exception: pass`) fueron eliminados de `app/utils/__init__.py` y `app/supermodules/__init__.py` el 2026-07-02.
- **`_archive/`**: contiene al menos dos intentos previos de consolidación abandonados, incluyendo un backend FastAPI + SQLAlchemy completo (`_archive/v2_backend_stack/`) con un esquema de datos (`Patient`, `SignalReading`, `Prediction`, `AuditLog`) que se está reutilizando como base para la BD de la Fase 1.1 — pero no está conectado a nada hoy.

## Dónde vive el UPS

`domain/physiology/state/` (implementado 2026-07-02, Fase 1.1, con dos ajustes de contrato del mismo día — `CONFIDENCE_REFERENCE`/`default_confidence()` y `EventType` como enum cerrado — ver `PLAN.md`). Es la fuente única de verdad para los dominios **cardiovascular y respiratorio** (los únicos modelados hasta ahora):
- `schema.py` — contrato tipado (`UnifiedPhysiologicalState`, `DomainState`, `PhysiologicalDescriptor` con `Provenance`+`confidence`, `PhysiologicalEvent` con `EventType`).
- `models.py` / `db.py` — persistencia SQLAlchemy/SQLite (`data/biocore_ups.db`).
- `repository.py` — `create_patient`, `save_state`, `get_latest_state`, `get_value_history` (consulta temporal), `get_events`.
- `builder.py` — `from_digital_twin_organism()`: única forma soportada de poblar el UPS desde `app/engines/digital_twin_organism.py` (que **no se modifica**, solo se lee).

`app/engines/digital_twin_organism.py` sigue viviendo también en `st.session_state` (UI en tiempo real), pero ya está conectado al UPS persistido en tres puntos: `domain/physiology/scenarios/` (Fase 1.2, evoluciona el organismo y persiste cada paso), el botón "Explicar estado actual" del narrador (Fase 1.3, persiste un snapshot bajo demanda antes de narrar), y el cuerpo visual (Fase 1.4, ver abajo — lee pasivamente, con su propio botón de sincronización). No dupliques la lógica de `_update_heart`/`_update_lungs`/umbrales de riesgo en otro sitio — el builder y el simulador de escenarios ya la reutilizan.

## Dónde vive el cuerpo visual (Fase 1.4 — cierre de la Fase 1)

`app/supermodules/twin_shell/ups_body_visual.py` (2026-07-03). Corazón y pulmones en SVG 2D (sin 3D), coloreados/animados **directamente desde el UPS** — severidad de eventos por dominio (`EventSeverity`) + descriptores (`heart_rate`, `respiratory_rate`, `spo2`). Deliberadamente NO analiza el texto del narrador: son dos lectores independientes de la misma fuente de verdad, ninguno lee al otro. `SEVERITY_COLOR`/`EVENT_VISUAL_MAP` son los únicos mapeos color/órgano — no dupliques esa lógica en otro sitio. Expuesto vía `render_synced_digital_twin_body()` en `twin_shell/pages.py`, junto al narrador; se actualiza en vivo, paso a paso, dentro del simulador de escenarios de la Fase 1.2. Solo dibuja los dos dominios que el UPS modela — no añadas órganos que el UPS no modela todavía (nervioso, muscular) sin antes extender el esquema en `domain/physiology/state/schema.py`.

## Dónde vive el narrador clínico

`domain/physiology/narrator/` (Fase 1.3, 2026-07-02 — esperando confirmación del usuario, incluida una prueba manual con `ANTHROPIC_API_KEY` real). Única integración de IA del proyecto, con dos rutas de contexto sobre el mismo cliente:
- `context.py` — `build_context()`: lee el UPS y arma un `NarrativeContext` (datos, no prosa) con descriptores + comparación temporal antes/ahora + eventos.
- `prompt.py` — `DepthLevel` + reglas de anclaje (citar descriptor/evento exacto, prohibido inventar valores, comparación temporal obligatoria).
- `client.py` — `stream_narration()`: `client.messages.stream(model="claude-opus-4-8", ...)`. Sin `ANTHROPIC_API_KEY`, falla explícito (`NarratorNotConfiguredError`) — no hay modo simulado de respaldo.
- `findings.py` (2026-07-03) — `stream_findings_narration()`: mismo cliente/modelo/disciplina de anclaje que `client.py`, pero para laboratorios sin dominio en el UPS (EMG, HRV, Multisensor, ECG Monitor — el UPS solo modela cardiovascular y respiratorio). Contexto más liviano (`FindingsContext`/`Finding`: métricas ya calculadas por el laboratorio, sin comparación temporal). No es un narrador aislado nuevo — reutiliza `is_configured`/`NarratorNotConfiguredError`/`DEFAULT_MODEL` de `client.py`.

Expuesto en `app/supermodules/twin_shell/pages.py::render_clinical_narrator()` y reutilizado (misma sesión/organismo) desde el hub "AI Hub" de `app/main.py`; `findings.py` se expone vía `app/main.py::render_findings_narrator()`, usado en las pestañas "IA" de EMG/ECG Monitor/Multisensor/HRV Analysis (Clinical Hub). `app/ai_copilot.py` y `app/biomedical_tutor.py` fueron eliminados el mismo día — no reintroducir un chatbot aislado en su lugar (Art. I).

## Antes de tocar código

1. Lee `PLAN.md` para saber en qué fase está el proyecto y qué está aprobado para ejecutarse.
2. Para `signals/`, `clinical/`, `visualization/` y el motor de razonamiento, usa los ganadores ya decididos (sección arriba) — no reabras esa decisión sin motivo.
3. Si vas a añadir una integración de IA, debe ser una llamada real a la API de Anthropic, fundamentada en el UPS — no un diccionario de respuestas ni un chatbot aislado (Art. I de la Constitución).
