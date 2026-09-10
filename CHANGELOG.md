# Changelog

## 2026-09-10 — BIOCORE, Capa 5A dominio muscular, Tanda 3 (cierre): el EMG Lab escribe al UPS

**Contexto**: la Tanda 2 dejó el dominio muscular poblándose honesto (gate vacío probado, `fatigue_index` diferido, fantasma excluidos, 484 verdes) pero sin ningún flujo que lo escribiera. Esta tanda conecta el EMG Lab a esa escritura — el "Paso 4" del playbook neuro, el mismo botón "Guardar estado al gemelo" que ganaron ECG/HRV/Respiratory/EEG Lab — y cierra el arco. **La Capa 5A gana su segundo dominio vivo.** Barandilla de método (Fase 2.2): verificado **por ejecución hasta el final del render** vía `AppTest`, no por lectura.

### Parte A — el botón "Guardar estado al gemelo" en el EMG Lab (`app/main.py`)

`_render_emg_save_to_twin(fs, source, emg_analysis)`, llamado al final de `render_emg_page()` (todas las vistas) y también en la rama `signal is None` con `emg_analysis=None`. Réplica del patrón del botón del EEG Lab (Sub-fase 1):

- **El punto crítico de honestidad**: `_update_muscles()` (`digital_twin_organism.py`) normalmente se alimenta del slider "Fatiga muscular" de Twin OS (un `fatigue_index` sintético). Este botón alimenta el organismo vía `update_from_sensors({"emg": {"activation": <EmgAnalyzer>, "median_frequency": <EmgAnalyzer>}})` — la `activation` **medida** por el analizador sobre la señal **filtrada** (butter 20-450 Hz, Tanda 1), no un slider. Lo que llega a `muscles.metrics.signals["activation"]` es el valor del analizador. Luego `save_state()` persiste el dominio muscular real.
- `fatigue_index` NO se envía: el generador demo lo clava en 0 y `_muscular_state()` lo difiere de todos modos (Tanda 2). Con solo `activation` + `median_frequency` de entrada, `_update_muscles()` calcula health/risk/efficiency/smoothness desde `efficiency`/`fatigue_index` defaulteados (70/20) — mismo nivel de tolerancia que ya acepta el EEG Lab (band power reales, `stress_level` defaulteado); el gate de `_muscular_state()` (`"activation" in signals`) es lo que decide "hay músculo que escribir".
- Procedencia `Provenance.SIMULACION` (`source_detail="emg_muscle_lab:origen=<Demo|CSV|Live Hardware>"`).
- **Opt-in deliberado**, como el del EEG: el estudiante analiza un EMG y elige guardarlo al gemelo.

### Parte B — los desenlaces honestos en la UI

- **Guardado con `activation` real** → `st.success` con el `snapshot_id` + caption que enumera los descriptores musculares persistidos (`activation` con su procedencia, `median_frequency`, los 4 `DERIVADO`, "sin `fatigue_index` (diferido)", "sin campos fantasma") y confirma que los otros 3 dominios quedaron vacíos (este lab solo envía EMG).
- **Sin señal analizable** (Origen=CSV sin archivo — el caso que la Tanda 1 ya guarda arriba con `render_empty_state`) → el botón **no se renderiza**; en su lugar un `st.info`: "Sin señal EMG analizable … No hay nada que persistir". Sin éxito fingido, sin crash.

### Parte C — verificado por ejecución (`tests/test_emg_lab_save_to_twin.py`, 3 tests, AppTest hasta el final del render)

- **`test_emg_lab_writes_analyzed_activation_not_slider`** (el que importa): `generate_demo_emg_signal` parcheado a una señal determinista → render (Origen=Demo, vista=Clínica por default) sin excepción → sin snapshot antes del click → click en "Guardar al gemelo" → sin excepción tras el re-render → `get_latest_state(patient_id)` devuelve un dominio muscular con `activation` == `EmgAnalyzer(fs).analyze(señal).activation_pct` (**y ≠ 45.0**, el default de `_update_muscles()`), procedencia `SIMULACION`, unidad `"%"`; `median_frequency` == la del analizador; los 4 derivados `DERIVADO`; **sin `fatigue_index`**, sin los 3 fantasma; cardiovascular/respiratory/neurological vacíos. Es el **primer snapshot muscular escrito por el lab**, no por Twin OS.
- `test_emg_lab_declares_no_signal_instead_of_faking_save`: Origen=CSV sin archivo → `st.info` "sin señal EMG analizable", **ningún** botón `emg_lab_save_to_ups`, nada persistido.
- `test_emg_lab_snapshot_round_trips`: `save_state` del lab → sesión nueva → `get_latest_state` recupera `activation`/`median_frequency`, `"muscular" in all_domains()`, sin `fatigue_index`.

`pytest tests/ -q` → **487 passed** (484 + 3 nuevos). App `HTTP 200`.

### Parte D — Plan Maestro (`~/Downloads/BIOCORE_Plan_Maestro.md`, `.md` fuente)

- Estado de cabecera: "segundo dominio (muscular) VIVO en el UPS"; suite 473 → **487**.
- §13 5A "Hecho" gana el sub-arco **Dominio muscular (Tandas 1–3)** completo: shadow `preprocess_emg` muerto + `EmgAnalyzer` extraído con contrato idéntico al `EegAnalyzer` (Tanda 1); `schema.py` + `_muscular_state()` copia literal del gate del neuro, `fatigue_index` diferido, 3 fantasma excluidos, evento `SEVERE_MUSCLE_FATIGUE_EMG` (Tanda 2); botón del EMG Lab con `activation` analizada, no slider (Tanda 3). Registro explícito del **patrón replicado del neuro**.
- Nueva subsección **"El camino al CMC (coherencia córtico-muscular)"** — el "santo grial" del experto, con sus **3 precondiciones**: (1) dominio muscular en el UPS ✅ **cumplida esta tanda**; (2) señal EEG+sEMG pareada simultánea ✗ (pariente del problema del PLV — el arrastre temporal del arco (b) no basta, el CMC exige simultaneidad real); (3) firma del experto para banda/protocolo/duración/umbral ✗. Forma de implementación: **patrón PLV** (medida entre-dominios en `biomarkers.py` que degrada a "no disponible"), **NO una `CouplingRule`** (el CMC mide, no modula).
- "Pendiente" y "Refinaciones futuras" actualizadas: `fatigue_index` sobre señal real; regla de acoplamiento **muscular → CV** (débil, `activation` sostenida → ↑FC modesta, el pressor response del ejercicio isométrico, si se construye — con firma del experto).
- **Word NO regenerado**: el entorno no tiene `pandoc` ni `python-docx` (como en la Tanda 3 de acoplamiento). El contenido correcto y al día vive en el `.md`; el comando queda anotado al pie.

**Arco del dominio muscular cerrado.** El EMG Lab alimenta el gemelo con activación muscular real analizada, con procedencia honesta — nunca el slider disfrazado de medición. La Capa 5A tiene su segundo dominio.

## 2026-09-10 — BIOCORE, Capa 5A dominio muscular, Tanda 2 (el dominio): `muscular` en el UPS

**Contexto**: la Tanda 1 saneó la señal (mató el shadow `preprocess_emg`, extrajo `EmgAnalyzer`, verificó `activation`/MDF sobre señal filtrada). Con la señal limpia, esta tanda eleva el músculo al UPS como **cuarto dominio**, con la misma disciplina de honestidad que el neuro (Art. I: honesto por arquitectura — se escribe dato real o un dominio vacío, nunca un músculo sano por default indistinguible de uno medido). NO toca la UI: el botón "Guardar estado al gemelo" del EMG Lab es la Tanda 3.

### Parte A — `schema.py`

- `UnifiedPhysiologicalState` gana el campo `muscular: DomainState`, con `default_factory` → `DomainState(domain="muscular")` vacío. Los 11 sitios que construyen `UnifiedPhysiologicalState(...)` pasan todo por keyword (verificado por grep) → reciben el dominio muscular vacío sin editarse.
- `all_domains()` incluye `"muscular"` → el narrador (`narrator/context.py`, itera `all_domains().values()` genéricamente) y `save_state()` (mismo patrón) cubren el dominio nuevo sin cambios.
- `EventType` gana un único miembro: `SEVERE_MUSCLE_FATIGUE_EMG = "severe_muscle_fatigue_emg"`.

### Parte B — `builder.py`

`_muscular_state()` — **copiado literal** del patrón de `_neurological_state()`, incluido el gate anti-órgano-fantasma:

- `signals = organism.organs["muscles"].metrics.signals` (el dict que llena `_update_muscles()`).
- **Gate**: `has_real_muscular_input = "activation" in signals`. `activation` es la señal primaria del músculo — derivable de cualquier sEMG real (`mean|x|/max|x|`), y la única de las tres entradas que consume `_update_muscles()` (`activation`/`efficiency`/`fatigue_index`) que no viene hoy del slider de Twin OS. Sin `activation` → `descriptors = {}` → `DomainState` vacío. La barandilla exacta del neuro.
- **Persiste, cada uno gateado por presencia**: `activation` (procedencia del llamador, unidad `"%"`), `median_frequency` (procedencia del llamador, `"Hz"`).
- **Solo si `has_real_muscular_input`**, todos `Provenance.DERIVADO`, unidad `"0-100"`: `health_score`, `risk_score` (de `muscles.metrics.*`), y si `detail is not None`: `neuromuscular_efficiency`, `movement_smoothness` (los dos únicos campos de `MusculoskeletalDetail` que `_update_muscles()` recalcula en cada paso).
- **`fatigue_index` DIFERIDO**: NO se persiste como descriptor en esta tanda. Comentario explícito en el código — la fórmula (`fatigue_index_from_mdf`) es real y responde sobre sEMG real, pero `generate_demo_emg_signal` (ruido blanco = espectro plano) lo clava en 0.00 en los 3 patrones. Persistirlo desde el demo sería una constante disfrazada de medición (Art. I). Se persistirá cuando la escritura venga de CSV/hardware, o cuando el generador se recalibre con propósito declarado.
- **Los tres fantasma EXCLUIDOS** con comentario del porqué: `recruitment_pattern`, `motor_symmetry`, `power_output` — `_update_muscles()` **nunca** los asigna (confirmado por lectura completa del método), se quedan para siempre en su default de dataclass (50.0/90.0/100.0). Escribirlos al UPS sería el análogo exacto de `frontal_activity`/`temporal_activity` que `_neurological_state()` ya excluye.

`_detect_events()` — evento muscular único: lee `organism.organs["muscles"].metrics.signals.get("fatigue_index")`; si `> 80` emite `SEVERE_MUSCLE_FATIGUE_EMG` (`domain="muscular"`, `EventSeverity.WARNING`, `related_descriptor="movement_smoothness"`). **Mismo umbral** que ya usa `_update_muscles()` para su tier más alto de `risk_score` — no un criterio clínico nuevo. El evento lee la señal cruda aunque `fatigue_index` no se persista como descriptor, exactamente como `HIGH_STRESS_EEG` lee `stress_level` sin persistirlo. Sobre el generador demo (fatiga en 0) este evento nunca dispara.

`from_digital_twin_organism()` — `muscular = _muscular_state(...)` + `muscular=muscular` en el constructor. Docstring: "+ muscular".

### Parte C — `repository.py`

`muscular=_domain_state_from_values("muscular", values)` añadido en los 2 sitios de reconstrucción (`get_latest_state`, `get_state_by_snapshot_id`). `_domain_state_from_values` ya es genérico (filtra `v.domain == domain`); `save_state` ya itera `all_domains()` → la persistencia del dominio muscular es gratis.

### Parte D — verificado por ejecución

`tests/test_muscular_domain.py` (6 tests, espejo de los del neuro):
- **`test_muscular_domain_gate_prevents_ghost_muscle`** (la que importa): organismo solo-cardio → `muscular.descriptors == {}`; organismo solo-EMG → muscular poblado, los otros tres vacíos.
- `test_muscular_domain_persists_only_the_honest_descriptors`: exactamente `{activation, median_frequency, health_score, risk_score, neuromuscular_efficiency, movement_smoothness}` — `activation`/`median_frequency` con procedencia del llamador + unidad honesta, el resto `DERIVADO`.
- `test_fatigue_index_is_deferred_even_when_present_in_signals`: `fatigue_index` en `signals` → NO aparece como descriptor.
- `test_muscular_phantom_detail_fields_are_never_persisted`: los tres fantasma ausentes.
- `test_muscular_domain_survives_persistence_round_trip`: `save_state` → sesión nueva → `get_latest_state` recupera `activation`/`median_frequency`, sin `fatigue_index`.
- `test_severe_muscle_fatigue_event_uses_same_threshold_as_organism`: `fatigue_index=90` → 1 evento `SEVERE_MUSCLE_FATIGUE_EMG`; `fatigue_index=30` → 0.

`pytest tests/ -q` → **484 passed** (478 + 6 nuevos). App `HTTP 200`.

**NO en esta tanda**: botón "Guardar estado al gemelo" en el EMG Lab, ni UI — es la Tanda 3.

## 2026-09-09 — BIOCORE, Capa 5A dominio muscular, Tanda 1 (lado señal): `EmgAnalyzer` + muerte del shadow `preprocess_emg`

**Contexto**: el diagnóstico del dominio muscular confirmó que la extensión del schema es tamaño-neuro, pero que el lift real está en la señal — y que `app/main.py` tenía un `preprocess_emg` **stub no-op** (`filtered = signal`) que **eclipsaba** el bandpass real de `src/signals/emg/preprocessing.py`, así que `activation` y la MDF se calculaban sobre señal **cruda**. Persistir `activation` así al UPS sería una medición con un asterisco invisible. Esta tanda sanea la señal **antes** de tocar el schema. NO toca el UPS (schema/`_muscular_state()`/botón "Guardar al gemelo" = Tanda 2).

### Parte A — el shadow `preprocess_emg` muerto

Grep: el stub de `app/main.py` (líneas 155-158) era la única definición viva de ese nombre en `app/` — `app/main.py` **no importaba** el real de `src.signals.emg`. Sus 2 llamadores (vistas Clínica + IA de `render_emg_page`) recibían la señal sin filtrar. **Ningún llamador dependía del no-op** (no había doble-filtrado que evitar — es un stub olvidado, confirmado). Stub eliminado; el comentario de cabecera que afirmaba "No existe un src.signals.emg con análisis" (ya falso) reescrito.

### Parte B — `EmgAnalyzer` extraído a `src/signals/emg/emg_analyzer.py`

Mismo contrato que `EegAnalyzer` (`src/signals/eeg/`): `EmgAnalyzer(fs).analyze(signal) -> EmgAnalysis` con `activation_pct` / `median_frequency_hz` / `fatigue_index` + `findings` (strings con unidad). Consolida las 3 funciones sueltas de `app/main.py` (`compute_emg_median_frequency`, `compute_emg_fatigue_index`, la activación inline). **Fórmulas byte-idénticas** — `median_frequency` (searchsorted sobre la CDF del PSD de Welch), `fatigue_index_from_mdf` = `(120 − MDF)/60·100` clip 0-100 (constantes `MDF_BASELINE_HZ`/`MDF_SPAN_HZ` nombradas, heredadas tal cual, sin recalibrar), `activation` = `mean|x|/max|x|·100`. La única diferencia de comportamiento: **todo corre sobre la señal FILTRADA** (`preprocess_emg` interno, butter 20-450 Hz) — no una preferencia, es lo que hace que la MDF sea el marcador de fatiga que la literatura describe. `app/main.py` llama al analizador una vez y reparte el resultado por vista. Guard nuevo: `signal is None` (Origen=CSV sin archivo) → `render_empty_state` + `return` en vez del crash latente pre-existente en las vistas Clínica/IA.

### Parte C — verificado por ejecución

- **La MDF sigue corriéndose y el corrimiento con la fatiga sobrevive la consolidación**: sEMG realista band-limited → fresca MDF **104.5 Hz** (fatigue_index 25.8), fatigada MDF **60.5 Hz** (fatigue_index 99.1). Coincide con el diagnóstico (~101 → ~60).
- **`activation` ahora sobre señal filtrada — el filtrado tiene efecto medible**: sobre una señal con artefacto de movimiento de 3 Hz, `activation` cruda = 29.8%, filtrada = 19.1% (Δ 10.7); MDF cruda = **2.9 Hz** (destruida por el 3 Hz), MDF filtrada = 233.4 Hz. El bandpass demostrablemente cambia el resultado.
- **`fatigue_index` sigue clavado en 0.00 sobre el generador demo** (los 3 patrones, MDF ~225-232 Hz ≫ basal 120) — deuda del **generador** (ruido blanco = espectro plano), no de la fórmula. NO se arregla aquí; se difiere (no se persistirá al UPS en la Tanda 2).
- `tests/test_emg_preprocessing.py` → `tests/test_emg_analyzer.py` (7 tests: `preprocess_emg` real filtra fuera de banda, fórmula de fatiga intacta, corrimiento de MDF, contrato del analizador, **filtered≠raw**, fatigue_index diferido en demo).
- **AppTest de `render_emg_page` hasta el final** (barandilla de ejecución): las 5 vistas × 3 orígenes (incl. CSV-sin-archivo, antes un crash latente) → sin excepción.
- `pytest tests/ -q` → **478 passed** (473 + 7 nuevos − 2 retirados). App `HTTP 200`.

**NO en esta tanda**: nada de schema del UPS, `_muscular_state()`, ni botón "Guardar al gemelo". Solo: señal muscular limpia y analizador mantenible antes de elevarla al organismo.

## 2026-09-08 — BIOCORE, Acoplamientos (b) Tanda 3 (cierre): superficie honesta + documento maestro

**Contexto**: la Tanda 2 dejó el acoplamiento neuro→CV disparando en vivo con una caption que ya declaraba las tres procedencias. Esta tanda cierra el arco (b): pule la superficie para que un estudiante la entienda (no solo un ingeniero) y actualiza el Plan Maestro. Art. I: honesto por arquitectura — la declaración de procedencia en la UI es información pedagógica, no jerga.

### Parte A — superficie honesta (pulido mínimo, cero cálculo)

Las captions del botón 3a (`render_neuro_cardiac_composer`, `twin_shell/pages.py`) filtraban términos crudos (`ARRASTRE_TEMPORAL`, `DERIVADO_ACOPLAMIENTO`, los tres `provenance.value` en paréntesis). Glosados en lenguaje clínico, con el nombre técnico detrás como nota, no al frente:
- BAR → "la última medición **neurológica** guardada … una medida de activación cortical".
- FC arrastrada → "**La FC no se vuelve a medir: se reutiliza la última lectura guardada**, indicando de qué momento viene y cuántos segundos hace".
- FC acoplada → "un valor **calculado por la regla, no medido por un sensor**".
- La ventana de 120 s → "para no unir dos momentos sin relación".
- Tail: "cada una diciendo de dónde viene … Nombres internos de esas procedencias: `simulacion` · `arrastre_temporal` · `derivado_acoplamiento`".

Verificado: `pytest tests/ -q` → **473 passed** (sin tests nuevos ni rotos — cambio cosmético; los tests de caption de la Tanda 2 siguen verdes). App `HTTP 200`.

### Parte B — Plan Maestro actualizado

`~/Downloads/BIOCORE_Plan_Maestro.md` — el `.docx` no tenía Markdown fuente asociado; se **reconstruyó el contenido íntegro** desde el Word y a partir de aquí el `.md` es la fuente de verdad. Actualizado con:
- El acoplamiento neuro→CV pasa de "construido, validado, probado en test, espera flujo" a **VIVO** en el flujo del paciente único (§13, nuevo sub-arco (b) bajo Capa 5A).
- El arco (b) completo registrado: consulta por dominio (`get_latest_snapshot_id_with_descriptor`, rowid no timestamp), `Provenance.ARRASTRE_TEMPORAL` (hold de orden cero), gate temporal `max_hr_carry_age_s=120s` (config firmable por experto, degradación espejo del PLV), botón 3a opt-in.
- Conectado a la Fase 3 (§14 marcada IMPLEMENTADA): primera composición multi-dominio real — dos labs distintos unidos en un cuerpo bajo un `patient_id`.
- Capa 5A Sub-fases 1 y 2 marcadas hechas (dominio neuro en el UPS + cerebro en el SVG).
- Refinaciones futuras firmables por experto anotadas: banda de confianza degradada por edad del HR arrastrado (hoy hereda tal cual), reglas de acoplamiento espejo (relajación→↓FC) y el CMC lejano.

**Word NO regenerado**: el entorno no tiene `pandoc` ni `python-docx` (`.docx` es una tanda aparte de formato si se quiere; el contenido correcto y al día vive en el Markdown). El comando queda anotado al pie del `.md`.

**Arco (b) cerrado.** El estrés cortical acelera el corazón en el flujo real, declarado como cálculo del acoplamiento — nunca fingido como medición.

## 2026-09-08 — BIOCORE, Acoplamientos (b) Tanda 2: el acoplamiento neuro→CV dispara EN VIVO

**Contexto**: la Tanda 1 dejó `compose_neuro_cardiac_snapshot()` probado aislado (6 verdes) — compone valores reales o devuelve "no disponible con motivo", nunca finge. Esta tanda lo conecta a la regla validada (`AROUSAL_TAQUICARDIA_BAR`) y le da su disparador de usuario. El acoplamiento neuro→CV pasa de "probado en test" a **vivo en el flujo del paciente único**. Barandilla de método (Fase 2.2): verificado **por ejecución hasta el final del render** vía `AppTest`, no por lectura — el recon ha mentido antes ("renderiza" cuando crasheaba). Art. I: honesto por arquitectura — compone valores reales o declara por qué no puede.

### Parte A — `apply_couplings` cableado a la salida del compositor (`state/composer.py`)

Tras el `save_state()` del camino feliz, el compositor llama `apply_couplings(session, composed_id, VALIDATED_RULES, scenario=None)` — **dentro** del compositor: "componer" es atómicamente "componer + acoplar", ningún llamador futuro puede olvidar el segundo paso. Import **perezoso** de `domain.physiology.coupling` (la capa `state/` no gana una dependencia de import sobre `coupling/`; `coupling` ya depende de `state`, la llamada es one-way en runtime).
- `scenario=None` es **estructural**: los 12 `SimulationScenario` (incluidos `stress`/`anxiety`/`seizure`) corren solo sobre pacientes efímeros (`create_ephemeral_basal_patient`/`create_ephemeral_case_patient`), nunca sobre el paciente continuo. `COUPLING_DISABLED_SCENARIOS` queda **intacto** como barandilla para un hipotético compositor de pacientes-de-escenario futuro — no se toca, no se borra. Verificado por ejecución (spy sobre `apply_couplings` captura `scenario is None`).
- El snapshot combinado tiene `bar` (neurológico) + `heart_rate` (cardiovascular) → si `bar > 1.8`, `heart_rate_acoplado = heart_rate + 15` se adjunta al MISMO snapshot con `Provenance.DERIVADO_ACOPLAMIENTO` (que ahora cabe gracias al `String(30)` de la Tanda 1). Si `bar ≤ 1.8`, `bar` y `heart_rate` coexisten pero **sin** fila acoplada — el compositor no fuerza un acoplamiento donde el arousal no lo justifica.
- `ComposeResult` gana `coupled: Tuple` — los `AppliedCoupling` que dispararon (vacío si nada), para que la UI muestre el desenlace sin re-consultar.

### Parte B — el botón 3a en Twin OS (`twin_shell/pages.py::render_neuro_cardiac_composer`)

Botón explícito "**Componer y evaluar**" (sección "🔗 Evaluar acoplamiento neuro-cardíaco (BAR → FC)"), justo después de `render_couplings()`. Opt-in deliberado — el estudiante elige unir el BAR guardado del EEG con la FC medida guardada del ECG. Los tres desenlaces, honestos en la UI:
- `available=True` + regla disparó → `st.success` + caption: "FC arrastrada 72 → **FC acoplada 87 bpm** (`DERIVADO_ACOPLAMIENTO`, confianza 0.70) — BAR observado 2.60, FC de hace 40 s. Las tres cantidades coexisten con procedencias distintas: BAR (origen) · FC (arrastre_temporal) · FC acoplada (derivado_acoplamiento)".
- `available=True` + regla no disparó → `st.success` + caption "Compuesto, **sin acoplamiento**: el BAR observado no supera el umbral de arousal (>1.8)".
- `available=False` → `st.info(f"No se pudo componer: {reason}")` con la razón tal cual ("sin BAR persistido" / "sin FC medida persistida" / "FC arrastrada demasiado vieja: 300s > 120s …") — **NO** un error crudo, **NO** un silencio, **NO** éxito fingido. Es información pedagógica.

### Verificación — por ejecución, `AppTest` hasta el final del render

`tests/test_neuro_cardiac_composer_button.py` (nuevo, primer test del repo con `AppTest`; 6 casos):
- **Disparo en vivo** (el que importa): paciente sembrado con snapshot EEG (`bar=2.6`) + snapshot ECG (`heart_rate=72`, edad 40 s) → render + click vía `AppTest` → sin excepción en ambas pasadas → el snapshot combinado (`get_latest_state`) tiene `heart_rate=72` (`ARRASTRE_TEMPORAL`), `heart_rate_acoplado=87` (`DERIVADO_ACOPLAMIENTO`), `bar=2.6` (`SIMULACION`) — las **tres procedencias distintas** — y la caption cita `AROUSAL_TAQUICARDIA_BAR` y `87`.
- **No-op honesto**: `bar=1.1` → compone, **sin** `heart_rate_acoplado`, caption "sin acoplamiento".
- **Tres no-disponibles**: sin BAR / sin FC / FC de 300 s → `st.info` con la razón correcta, `st.success == []`, sin crash, sin `heart_rate_acoplado` persistido.
- **`scenario=None` estructural**: spy confirma el kwarg real.

`pytest tests/ -q` → **473 passed** (467 + 6, 0 fallos). App `HTTP 200` (`/_stcore/health` → `ok`). **"Un organismo, no doce herramientas" deja de ser tesis: es un snapshot real** con FC, BAR y FC-acoplada coexistiendo, cada uno declarando de dónde viene.

## 2026-09-08 — BIOCORE, Acoplamientos (b) Tanda 1: el compositor multi-dominio, aislado y probado

**Contexto**: el acoplamiento neuro→CV (`AROUSAL_TAQUICARDIA_BAR`, validado en Sub-fase B) no dispara en vivo porque el `bar` (entra solo por EEG Lab) y el `heart_rate` medido (entra por ECG/HRV/Twin OS) pasan por puertas disjuntas — ningún snapshot los tiene juntos. El diagnóstico de composición confirmó: (1) no existe una API "último snapshot del paciente con el descriptor X" — hay que construirla; (2) la procedencia vive **por descriptor** (`ValueRecord`), el esquema soporta el arrastre declarado; (3) el compositor **no debe** pasar por `from_digital_twin_organism()` (una sola procedencia/`source_detail` para todos los descriptores → aplanaría la distinción bar-real / FC-arrastrada). Esta tanda construye la composición y prueba que es honesta **antes** de cablear nada. Cero `apply_couplings`, cero UI — eso es Tanda 2. Art. I: composición honesta per-descriptor; sin BAR real, sin FC real, o FC fuera de ventana → "no disponible con motivo", nunca un snapshot a medias.

### Parte A — `get_latest_snapshot_id_with_descriptor()` (`repository.py`)

`(session, patient_id, domain, descriptor) -> Optional[str]`. JOIN `ups_values × ups_snapshots`, filtra por `patient_id + domain + descriptor`, **`ORDER BY ups_snapshots.rowid DESC LIMIT 1`** — rowid, NO timestamp: mismo criterio que `get_latest_state()`/`get_latest_snapshot_id()`, y a propósito distinto de `get_value_history()` (que ordena por timestamp y arrastra el bug de `datetime.now()` no-monótono en Windows). Test: con snapshots sembrados devuelve el id del último que **sí** contiene el descriptor, ignorando los más recientes que no lo tienen; `None` si nadie lo tiene.

### Parte B — `ValueRecord.provenance` `String(20)` → `String(30)` (`models.py`)

Una línea. Cubría `derivado_acoplamiento` (21 chars, latente desde Acopl. Sub-fase A — SQLite ignora el largo de `VARCHAR`, Postgres/MySQL truncarían) y el `arrastre_temporal` nuevo (17).

### Parte C — `Provenance.ARRASTRE_TEMPORAL` (`schema.py`)

Un valor REAL medido/simulado en T-1, afirmado en un snapshot compuesto T porque se asume que la última lectura sigue vigente dentro de una ventana acotada — un **hold de orden cero** (zero-order hold). **NO** es `SENSOR_REAL` (ningún sensor midió en el timestamp compuesto) ni `DERIVADO` (no se calculó de otras entradas — se arrastró una medición sin transformarla). **Sin banda en `CONFIDENCE_REFERENCE`** (igual que `REFERENCIA_CLINICA`): la `confidence` se hereda TAL CUAL del descriptor de origen — el compositor la copia, no la promedia. La degradación de confianza por edad del arrastre queda como refinación futura firmada por experto.

### Parte D — `compose_neuro_cardiac_snapshot()` (`domain/physiology/state/composer.py`, nuevo)

`(session, patient_id, *, max_hr_carry_age_s=120.0) -> ComposeResult`. `ComposeResult = {available, snapshot_id, reason, hr_age_s}` — mismo patrón que `PLVResult` (`biomarkers.py`): "no disponible con motivo", jamás un número inventado.

- `snap_bar = get_latest_snapshot_id_with_descriptor(pid, "neurological", "bar")` → `get_state_by_snapshot_id` → toma el descriptor `bar` completo. Falta → `available=False, reason="sin BAR persistido"`.
- `snap_hr = get_latest_snapshot_id_with_descriptor(pid, "cardiovascular", "heart_rate")` → idem. Falta → `reason="sin FC medida persistida"`.
- `hr_age_s = |bar_ts − hr_ts|` (magnitud, **no** se exige `hr_ts < bar_ts` estricto — el Windows no-monótono invierte pares por microsegundos).
- `hr_age_s > max_hr_carry_age_s` → `available=False, reason="FC arrastrada demasiado vieja: {age}s > {MAX}s — arousal y FC de momentos distintos, no acoplamiento"`. **No persiste.**
- Camino feliz: `UnifiedPhysiologicalState(timestamp=now, cardiovascular={heart_rate: <valor real, provenance=ARRASTRE_TEMPORAL, confidence heredada, source_detail="FC arrastrada del snapshot ⟨id⟩ del ⟨iso-ts⟩ (edad ⟨N⟩s)">}, neurological={bar: <copia literal, provenance intacta>}, respiratory={})` → `save_state()` → `available=True`. **No pasa por `from_digital_twin_organism()`** — arma los `DomainState` directamente.

### Verificación (aislada, sin `apply_couplings`)

`tests/test_composer.py` (6 tests): camino feliz (`bar` con procedencia de origen intacta + `heart_rate` real con `ARRASTRE_TEMPORAL` y `source_detail` con id/ts/edad); arrastre dentro de ventana (~60s, edad declarada correcta); degradado por edad (>120s → `available=False`, "demasiado vieja", **cero persistencia** — `get_latest_snapshot_id` sin cambios); sin BAR → "sin BAR persistido"; sin FC → "sin FC medida persistida"; la consulta de Parte A devuelve el último correcto ignorando snapshots sin el descriptor.

`pytest tests/ -q` → **467 passed** (461 + 6, 0 fallos). Sin cablear acoplamiento, sin UI — se probó que compone honesto antes de que dispare nada. Tanda 2: `apply_couplings()` sobre el snapshot compuesto + botón.

## 2026-09-06 — BIOCORE, Acoplamientos Sub-fase B: la primera regla validada (arousal→↑FC)

**Contexto**: la Sub-fase A dejó la infraestructura honesta e inerte (`DERIVADO_ACOPLAMIENTO`, `apply_couplings`, `magnitude_delta`, escenarios bloqueados). El experto validó la primera regla y **rechazó `beta_power` crudo** como ancla —la potencia absoluta varía por anatomía (cráneo, distancia fuente-sensor, ganancia), indefendible entre sujetos— a favor del **Ratio Beta/Alfa (BAR = P_β/P_α)**: un cociente adimensional del mismo electrodo que cancela esas variables y es un biomarcador **citado** (Schutter 2006 / Handbook of Psychophysiology cap.10), no una invención de la app. Esta sub-fase construye el BAR, lo usa de ancla, y activa la regla.

### Paso 1 — BAR en el `EegAnalyzer` (`src/signals/eeg/eeg_analyzer.py`)

`beta_alpha_ratio(beta_power, alpha_power) -> Optional[float]` (función de módulo, fuente única de la fórmula + el borde): `None` si `alpha_power` es ~0 (`< 1e-9`) — **un cociente indefinido se declara indefinido, no se fuerza a infinito ni a un tope**. `analyze()` añade `bar` a `EegAnalysis` (campo con default `None`, aditivo) y una fila `Beta/Alpha Ratio (BAR)` a `findings`. Constantes citadas: `BAR_BASELINE_RANGE (0.8, 1.2)`, `BAR_AROUSAL_THRESHOLD 1.8`, `BAR_CITATION`.

### Paso 2 — BAR persistido + ancla cambiada (`builder.py`, `coupling/rules.py`)

`_neurological_state()` persiste `bar` (calculado vía `beta_alpha_ratio` desde `signals["beta_power"]/["alpha_power"]`) **con la procedencia de las band power de origen** — NO `DERIVADO`: es una identidad aritmética sobre dos señales primarias del mismo dominio, no un índice que el organismo calcule con pesos propios. Respeta el gate: sin `alpha_power`+`beta_power` reales, no hay `bar`; con `alpha≈0` el cociente es `None` → no se persiste. **Reporte sobre la doctrina de procedencia**: no hubo que tocarla — el BAR encaja como "cociente de señales primarias con cita" (misma procedencia que sus entradas), exactamente el matiz que el experto resolvió; `stress_perception` (índice derivado) sigue prohibido como ancla.

`COUPLABLE_DESCRIPTORS["neurological"]`: `{"beta_power"}` (provisional Sub-fase A) → `{"bar"}` (firmado). `beta_power` ya no es acoplable (nada más lo usaba); sigue persistiéndose como band power. Tests de ancla actualizados.

### Paso 3 — la regla transcrita (`coupling/catalog.py`, nuevo)

`VALIDATED_RULES = (AROUSAL_TAQUICARDIA_BAR,)` — única fuente de verdad de acoplamientos activos. La regla, transcrita **literalmente** de la firma:
- `condition`: `neurological/bar > 1.8`. `effect`: `cardiovascular/heart_rate` AUMENTA, `magnitude_delta=+15.0` (arousal cognitivo puro acotado a +10–25 bpm; +15 punto medio conservador).
- `source`: "Guyton & Hall 14ª ed. cap.61 (SNA y respuesta de estrés) | Schutter DJLG 2006 / Handbook of Psychophysiology 3ª ed. cap.10 (BAR; basal 0.8-1.2, arousal >1.8)".
- `validation_status=VALIDADO_POR_FUENTE` → confianza **0.70** (extremo alto de la banda de `DERIVADO_ACOPLAMIENTO`, aún por debajo de `SIMULACION`). `enabled=True` — la primera regla activa.
- `notes`: la dirección espejo (relajación→↓FC) es una regla futura con su propia firma — no se añade "por simetría".

### Paso 4 — puente cableado a un flujo vivo

El botón **"Guardar estado al gemelo"** de EEG Lab (`eeg_neuro_lab/page_content.py`), tras `save_state()`, llama `apply_couplings(session, snapshot_id, VALIDATED_RULES, scenario=None)` en la misma sesión. `scenario=None` porque EEG Lab es un escritor **neuro-sin-CV-correlacionada**, no un escenario de estrés. **Hallazgo reportado**: EEG Lab escribe un snapshot neuro-only (sin FC medida, como todos los labs del repo), así que ahí `apply_couplings` es hoy un **no-op honesto** (`base heart_rate is None` → no escribe nada) — la llamada está cableada y dispara en cuanto un snapshot lleve FC medida + BAR>1.8. La caption del botón lo dice explícitamente. El mecanismo se prueba por ejecución con un snapshot combinado ecg+eeg (abajo).

### Paso 5 — dos sistemas conversan honestamente (verificado por ejecución)

`tests/test_coupling_subfase_b.py` (13 tests):
- **BAR alto → acoplamiento**: snapshot con `heart_rate` medido 72 + EEG beta-dominante (BAR = 40/10 = 4.0 > 1.8) → `apply_couplings(VALIDATED_RULES)` → `heart_rate` (72, `simulacion`, **intacto**) Y `heart_rate_acoplado` (**87** = 72+15, `derivado_acoplamiento`, confianza **0.70**, `source_detail` = regla + citas Guyton/Schutter + `disparo: bar=4` + `heart_rate base=72`). Coexisten.
- **BAR bajo → sin acoplamiento**: BAR = 5/25 = 0.2 < 1.8 → `apply_couplings` devuelve `[]`, sin fila `heart_rate_acoplado`.
- **BAR indefinido → sin acoplamiento**: `alpha_power=0` → no hay descriptor `bar` → la regla no compara `None > 1.8`, no dispara.
- **Escenario de estrés → bloqueado**: `apply_couplings(..., scenario="stress")` → `CouplingScenarioBlockedError`, nada escrito (la FC del escenario ya incluye la descarga simpática — cero doble cuenta).
- **El narrador lo cita**: `build_context()` incluye `heart_rate_acoplado` (`provenance="derivado_acoplamiento"`, 87) junto al `heart_rate` medido, sin tocar el narrador.
- BAR en el analizador: adimensional/scale-free (mismo cociente x1000), `None` en los bordes (alpha=0, inf, nan); beta-dominante → BAR>1.8, alpha-dominante → BAR<1.8.

**No-regresión**: solo cambian `coupling/` + `eeg_analyzer.py` (+ su `__init__`) + `builder.py` + el botón de EEG Lab + los tests de ancla/set-neuro. Único consumidor de `EegAnalysis` es EEG Lab (campo `bar` con default, aditivo). Sin cambios en `repository.py`/`schema.py`/`narrator/`/hemodinámica/organismo/twin visual/los otros labs. Las 3 raíces (gates), el puente hemodinámico y la Sub-fase A — intactos. `pytest tests/ -q` → **461 passed** (447 + 14 nuevos, 0 fallos). App **HTTP 200** (`/_stcore/health` → `ok`).

## 2026-09-06 — BIOCORE, Acoplamientos Sub-fase A: infraestructura honesta e inerte (cero reglas)

**Contexto**: tres sistemas (cardiovascular, respiratorio, neurológico) alimentan el gemelo pero no conversan. El motor de acoplamientos (`domain/physiology/coupling/`) existe pero está dormido: `evaluate()` solo PROPONE, ningún módulo lo importa, `COUPLABLE_DESCRIPTORS` no incluía neuro. El diagnóstico previo mapeó tres trampas de honestidad —un valor modulado por una regla NO es medido; el HRV ya mide el acoplamiento autonómico (doble cuenta); los escenarios de estrés ya co-authorean FC↑ con estrés↑— cada una con precedente en el repo. Esta sub-fase construye toda la maquinaria **honesta e inerte**, verificada por ejecución con **cero reglas activas**. NINGUNA regla real se transcribe aquí (eso es Sub-fase B, con el experto).

### Paso 1 — `Provenance.DERIVADO_ACOPLAMIENTO` (`state/schema.py`)

Miembro nuevo + `ConfidenceBand` en `CONFIDENCE_REFERENCE`, copiando el razonamiento de `MODELO_HEMODINAMICO` (NO diluir en `DERIVADO` genérico: es una afirmación fisiológica nueva, pendiente/dotada de validación experta). Banda `0.30-0.80`, dos regímenes (extremo bajo para `TRANSCRITO_SIN_VALIDAR`, alto para `VALIDADO_POR_FUENTE`), techo por debajo de `SIMULACION` (0.90). Sin punto medio automático — `apply_couplings()` pasa la confianza explícita según el `validation_status` de cada regla. Aditivo: ningún test enumera los miembros de `Provenance` ni `CONFIDENCE_REFERENCE` de forma cerrada; `REFERENCIA_CLINICA` sigue sin banda.

### Paso 2 — Ancla neuro en `COUPLABLE_DESCRIPTORS` (`coupling/rules.py`)

`"neurological": frozenset({"beta_power"})` — band power (señal primaria vía PSD de Welch), **NO** un índice derivado por BIOCORE, así que la doctrina "solo señales primarias, nada de `health_score`/`stress_perception`/…" **se mantiene intacta** (test nuevo confirma que `neurological/stress_perception` sigue lanzando `ValueError`). `beta_power` es **PROVISIONAL** — la firma del experto (Sub-fase B) podría cambiarlo a un ratio nombrado por la literatura (theta/beta, beta/alpha). Una `CouplingCondition(domain="neurological", descriptor="beta_power", …)` ahora se instancia; ninguna `CouplingRule` real la usa. `test_couplable_descriptors_are_exactly_the_four_primary_signals` → `…five_primary_signals`.

Añadido `CouplingEffect.magnitude_delta: Optional[float] = None` — el número con signo que `apply_couplings()` necesita para escribir `base + delta`. `None` en toda regla de esta sub-fase; lo rellena la regla validada de la Sub-fase B. `__post_init__` rechaza un `magnitude_delta` cuyo signo contradiga `direction`. *(Única adición al modelo de regla más allá del plan literal — reportada: sin ella, "para cada `ProposedCoupling` → `append_descriptors()`" no era implementable, porque el modelo de regla no cargaba ningún número.)*

### Paso 3 — Puente post-persistencia `apply_couplings()` (`coupling/bridge.py`, nuevo)

Réplica de `hemodynamics/ups_bridge.py`: lee un snapshot YA PERSISTIDO (`get_state_by_snapshot_id`), corre `evaluate()` con el catálogo, y por cada acoplamiento que dispare **y traiga `magnitude_delta`**, adjunta un descriptor `{descriptor}_acoplado` bajo el MISMO `snapshot_id` vía `append_descriptors()`:
- `Provenance.DERIVADO_ACOPLAMIENTO`, confianza `confidence_for_validation_status(regla.validation_status)` (0.35 transcrito / 0.70 validado).
- `source_detail` completo: `acoplamiento:{rule_id} | {source} | disparo: {descriptor}={valor} | {efecto} base={valor}`.
- **Nombre con sufijo `_acoplado`** (lección de `systolic_bp_modelo`): `heart_rate` (medido) y `heart_rate_acoplado` (calculado) coexisten como filas `ValueRecord` distintas — `_domain_state_from_values` indexa por nombre, sin sobrescritura silenciosa.
- **No muta el organismo, no toca `builder.py`/`run_rich_scenario()`/narrador, no sobrescribe el medido.**

`COUPLING_DISABLED_SCENARIOS = {"stress", "anxiety", "seizure"}` — escenarios cuyo CV ya incluye la descarga simpática; `apply_couplings(scenario=…)` lanza `CouplingScenarioBlockedError` (estructural, no un `if` evitable — mismo patrón que `HemodynamicModelNotEnabledError`). NO es lista blanca: por doctrina el acoplamiento aplica a cualquier escritor neuro-sin-CV-correlacionada (`scenario=None` — EEG Lab, escritor solo-EEG).

Política de combinación multi-regla: **documentada como pendiente** (`_combine_proposals_for_same_effect()`, gancho identidad) — con ≤1 regla habilitada (el caso de la Sub-fase B) no se plantea; habilitar >1 regla sobre el mismo efecto exige elegir política primero.

### Paso 4 — Verificado por ejecución (honesto e inerte, cero reglas)

- **Inerte**: `apply_couplings(snapshot, [])` sobre un snapshot real → `[]`, snapshot idéntico, cero filas `_acoplado`. Igual con reglas `enabled=False`, e igual con una regla `enabled=True` disparada pero **sin `magnitude_delta`** (sin número citado no se escribe nada).
- **Procedencia de punta a punta**: un `PhysiologicalDescriptor(..., DERIVADO_ACOPLAMIENTO, 0.35, ...)` persiste y se recupera con procedencia/confianza/`source_detail` correctos. La banda existe y `0.80 < 0.90` (techo de `SIMULACION`).
- **Nombrado coexiste**: `heart_rate` (medido, `simulacion`, 70) y `heart_rate_acoplado` (calculado, `derivado_acoplamiento`, 92) en el mismo snapshot, filas distintas, el medido intacto.
- **El narrador lo citaría sin tocarlo**: `build_context()` itera `all_domains()` genéricamente → un `DescriptorContext` con `name="heart_rate_acoplado"`, `provenance="derivado_acoplamiento"` aparece junto al `heart_rate` medido.
- **Ruta completa una vez** (regla SOLO-TEST con `magnitude_delta=+18`, `beta_power=30 > 25`): una fila `heart_rate_acoplado = 88`, `DERIVADO_ACOPLAMIENTO`, confianza 0.35, medido intacto.
- **No-regresión**: solo cambian `coupling/` + el miembro de `schema.py` + el test de `COUPLABLE_DESCRIPTORS`; cero cambios en `builder.py`/`repository.py`/`narrator/`/labs/hemodinámica/organismo/twin visual. `pytest tests/ -q` → **447 passed** (432 + 15 nuevos, 0 fallos). App `HTTP 200` (`/_stcore/health` → `ok`).

**Sub-fase B** añade la primera regla (neuro→`heart_rate`, ancla y magnitud confirmadas por el experto, `VALIDADO_POR_FUENTE`, `enabled=True`) — la maquinaria ya está lista y probada honesta.

## 2026-09-05 — BIOCORE, depuración de código muerto: 32 módulos + 1 imagen retirados de `main`

**Contexto**: tras la limpieza de artefactos (envs, `.md` obsoletos, `_archive/` a branch) quedaba código muerto/roto reportado a lo largo de varias sesiones. Se hizo un censo completo con un grafo de imports (`ast`) desde `app/main.py` + `main.py` + los 199 archivos de `tests/`, con tres bugs del propio grafo corregidos y verificados por ejecución (resolución de imports relativos en `__init__.py`, edges implícitos "importar un submódulo ejecuta el `__init__.py` de sus paquetes ancestros", y un bug de separador `/`↔`\` que aislaba los entry points de su propio grafo) + mapeo manual de los puentes dinámicos (`runpy.run_path`, `importlib.util.spec_from_file_location`) que el código usa a propósito. Resultado: 33 elementos sin ningún llamador vivo, **cero migración necesaria** (ninguna función viva atrapada en un archivo muerto).

### Retirado por grupos, con la suite verde entre cada uno

- **Grupo A — clúster arrhythmia roto (4)**: `app_arrhythmia_classifier.py` (no compilaba, `IndentationError`), `infer_arrhythmia.py` y `evaluate_arrhythmia_classifier.py` (ambos crashean al importar — nombres inexistentes en `biomedical/arrhythmia_classifier.py` y un `train_arrhythmia_classifier.py` ausente del repo; verificado por ejecución directa), `biomedical/arrhythmia_compat.py` (shim cuyo único consumidor era la UI que no compila). `biomedical/arrhythmia_classifier.py` (el vivo, cubierto por `tests/test_arrhythmia_classifier_new.py`) **se conserva** — no importa de ninguno de los 4.
- **Grupo B — 26 huérfanos limpios**: `src/reasoning_engine.py` + `app/bio_reasoning_streamlit.py` + `app/reasoning_engine_streamlit.py` (`app/main.py` no menciona "reasoning"; el ganador `biomedical/reasoning_engine.py` sigue vivo vía su test); `app/{academy,clinical_db}.py`, `app/components/__init__.py` (tombstone ya vaciado), `app/engines/{hrv_engine,signal_intelligence}.py`, `app/utils/ui_helpers.py`; `domain/patients/__init__.py` (scaffold de 1 línea); `deep_learning/` (5, `__init__` vacío, cero referencias); `educational/` menos `ecg_tutor.py` (7 módulos que el `__init__` del paquete nunca importó); `src/ai/multisensor_analytics.py`; `src/signals/ecg/{ecg_education_integration,integrated_ecg_system,wave_annotation}.py` (no exportados por el `__init__`, perdedores del dedup de `src/signals/ecg/`). Los `__init__.py` de `educational/`, `src/signals/ecg/` y `src/ai/` re-verificados tras el retiro: ninguno importaba lo retirado.
- **Grupo C — artefactos (3)**: `debug_import.py`, `demo_run.py`, `pacing_spike_zoom.png`.

### Conservado a propósito

`example_reasoning_engine.py` (391 líneas, galería de ejemplos documentada del `biomedical/reasoning_engine.py` ganador) e `install_dependencies.py` (utilidad de instalación/verificación funcional). **`app/utils.py`** (588 líneas, 33 símbolos top-level, vivo como unidad vía el puente de compatibilidad de `app/utils/__init__.py`) queda marcado para una **auditoría de símbolos futura** — decidir cuál de sus 33 funciones tiene llamador real es una tanda propia.

### Verificación

- `pytest tests/ -q` → **432 passed** (0 fallos). Durante la campaña algunas corridas mostraron 430–431 con 1–2 skips: son los tests dependientes de PhysioNet (`test_qrs_delineation.py`, `test_bbb_detector_validation.py`, `test_ptbxl_bbb_validation_set.py`) que hacen `pytest.skip` ante un 502 de physionet.org — flake de red externo pre-existente, sin relación con nada retirado; la suite sin esos 9 tests da 423/423 estable.
- `python -m py_compile` sobre todo el árbol no-test → **limpio** (el `app_arrhythmia_classifier.py` que fallaba ya no está).
- Grep de cierre: **cero** imports a los 33 elementos desde código vivo.
- Los 3 entry points arrancan: `app/main.py` → HTTP 200; `main.py --help` (CLI, `--mode {pipeline,dashboard,trainer}`) OK; `app/ecg_trainer.py` importa limpio (usa `educational.ecg_tutor`, el módulo conservado).
- Huella de `main`: **278 archivos / 5.0 MB** (desde 311 / 5.3 MB), 175 `.py` no-test (desde 207).

## 2026-08-31 — BIOCORE, Capa 5A Sub-fase 2 (visual): el cerebro se suma al Cuerpo Digital SVG

**Contexto**: la Sub-fase 1 añadió el dominio neurológico al UPS (band power/estado reales del EEG, con gate anti-órgano-fantasma). Pero `app/supermodules/twin_shell/ups_body_visual.py` — el Cuerpo Digital sincronizado con el UPS — sólo dibujaba corazón y pulmones; su docstring afirmaba "los únicos dos dominios que el UPS modela", ya falso (son tres). Esta sub-fase es **presentacional, cero lógica de datos tocada**: hace visible en la representación principal lo que ya persiste y ya es honesto.

### Paso 0 — Patrón de corazón/pulmones mapeado (para replicarlo)

- **De qué estado leen**: `_render_heart_card()` / `_render_lungs_card()` reciben el `UnifiedPhysiologicalState` que `render_ups_body()` pasa — el mismo que tras la Fase 5.1 viene de `get_current_physiological_state()` (estado actual en memoria) o `get_latest_state()` (último persistido). Un único punto de verdad, ningún card relee el organismo ni el texto del narrador.
- **Valor → color**: dos estados cuando hay dato — `STABLE_COLOR` (verde) si no hay evento en el dominio, o `SEVERITY_COLOR[severity]` del evento más grave (`_severity_for_domain()`). El matiz fino (taqui/bradicardia) va en la **animación**, no en el color.
- **Valor → animación**: `heart_rate` → `beat_duration = clamp(60/hr, 0.35, 2.2)s` (`biocore-heartbeat`); `respiratory_rate` → `breath_duration = clamp(60/rr, 0.8, 4.0)s` (`biocore-breathe`). El dato modula la animación, no la decora.
- **Dominio vacío**: si falta el descriptor clave (`heart_rate` / `respiratory_rate`+`spo2`), el órgano se dibuja en `NEUTRAL_COLOR` (gris) con label "sin dato" y **sin** animación — nunca un color que finja una medición.
- **Halo de alerta**: `<circle>`/`<ellipse>` con `biocore-alert-halo` cuando la severidad es WARNING/CRITICAL. **Alertas**: `_event_labels_for_organ()` filtra `EVENT_VISUAL_MAP` por órgano.

### Paso 1 — `_render_brain_card()` implementado

Tercer órgano, patrón idéntico:
- **Lee** de `state.all_domains()["neurological"]` — el MISMO objeto `state` que corazón/pulmones (coherencia 5.1 por construcción: no hay una segunda fuente que pueda desincronizarse).
- **Color**: `NEUTRAL_COLOR` si `neurological.descriptors == {}` (gate de la Sub-fase 1 activo — escritor no-neuro); `STABLE_COLOR` si hay datos y ningún evento neuro; `SEVERITY_COLOR` del evento si lo hay (`HIGH_STRESS_EEG` → WARNING). Espejo exacto del `hr is None` del corazón.
- **Animación**: pulso sutil `biocore-brainwave` (nuevo keyframe, `scale(1)→scale(1.045)` + opacidad) cuya velocidad sube con `mental_workload` (`wave_duration = clamp(3.0 − workload/100·2.1, 0.9, 3.0)s`). Sin `mental_workload` (band power presente pero sin campos DERIVADOS), cerebro estático — mismo criterio que "sin animación a partir de un valor que no existe".
- **Métrica legible**: banda dominante entre las `*_power` presentes (`max` por valor, igual que `EegAnalyzer`) + `Carga mental: N`. Con el dominio vacío: "Estado: sin dato neurológico".
- **SVG**: `_BRAIN_PATH` (contorno mdi-brain, sólo el trazo exterior — mismo criterio que `_HEART_PATH`), viewBox 0 0 24 24, 110×110, igual que el corazón.
- `EVENT_VISUAL_MAP` += `HIGH_STRESS_EEG: ("brain", "🧠 Estrés elevado (EEG)")` — el mapeo explícito/cerrado que el módulo ya exige por cada EventType.

### Paso 2 — Integrado en el layout

`render_ups_body()`: fila del cerebro **arriba** (`st.columns([1,2,1])`, centrado, anatómicamente natural), luego la fila `st.columns(2)` de corazón/pulmones **sin cambios**. El layout de dos órganos no se rompe: sólo se le antepone una fila. Docstrings del módulo y de `render_ups_body()` actualizados de "dos dominios / ambos órganos" → "tres dominios / los tres órganos" (un docstring que afirma algo ya falso es su propia deuda — lección de 5B). `render_ups_body()` se llama desde 4 sitios (Cuerpo Digital sincronizado, simulador de escenarios paso a paso, modo caso clínico de Twin OS, Academia) — el cerebro aparece en los 4, consistente, porque todos pasan un `UnifiedPhysiologicalState` que desde la Sub-fase 1 ya trae el dominio neuro (vacío o poblado).

### Paso 3 — Verificado por ejecución

- **Las 3 caras de `_render_brain_card()`** (ejecución directa, no lectura): (1) estado con band power EEG real → verde `STABLE`, "Banda dom.: ALPHA · Carga mental: N", animación `biocore-brainwave` presente; (2) estado con `stress_level=90` → evento `HIGH_STRESS_EEG`, color WARNING `#ffc542`, halo presente, alerta "🧠 Estrés elevado (EEG)"; (3) estado solo-cardio (gate neuro activo) → `neurological.descriptors == {}` → gris `#64748b`, "Estado: sin dato neurológico", sin animación. En esa misma cara-3 el corazón sigue verde con "FC: 78 bpm" — no-regresión.
- **Coherencia 5.1**: con un `state` de los 3 dominios pasado a los 3 cards, cerebro/corazón/pulmones renderizan del mismo objeto sin releer el organismo — mover un slider / escribir un estado los actualiza a los tres en el mismo rerun (la regresión que 5.1 mató no vuelve por añadir un órgano).
- **AppTest smoke** de `render_ups_body()`: estado de 3 dominios y estado `None`, ambos sin excepción, brain/heart/lungs presentes en los dos, layout intacto.
- `pytest tests/ -q`: **432 passed** (sin cambio — sub-fase presentacional, ningún test nuevo ni roto).
- Servidor real (`streamlit run app/main.py`, puerto 8615): HTTP 200; proceso detenido tras verificar.

**"Todo alimenta al gemelo" ahora es visible para 3 sistemas** en la representación principal — cardiovascular, respiratorio y neurológico, los tres con el mismo trato de honestidad visual (gris cuando no hay dato, nunca un estado fabricado). Los biomarcadores avanzados (BSI/DAR/TBR/CMC) y cualquier detalle interno del SVG del cerebro quedan, deliberadamente, fuera.

## 2026-08-30/31 — BIOCORE, Capa 5A Sub-fase 1: dominio neurológico añadido al UPS — círculo EEG→UPS→gemelo cerrado

**Contexto**: el diagnóstico de alcance (Capa 5A, diagnóstico) confirmó que extender el UPS a un dominio nuevo es mecánico (5 archivos) porque la persistencia ya es agnóstica de dominio y el organismo YA tiene el cerebro (`NeurologicalDetail`, `_update_brain()` — misma madurez que corazón/pulmones antes de la Fase 2.4). Esta sub-fase escribe al UPS lo que `EegAnalyzer` (`src/signals/eeg/eeg_analyzer.py`) ya calcula — band power real vía PSD de Welch + estado derivado — con la misma disciplina de honestidad y el mismo gate anti-órgano-fantasma que cardiovascular/respiratorio. **No construye biomarcadores nuevos** (BSI/DAR/TBR/CMC quedan para el arco siguiente); el PLV sigue sin desbloquearse (es un problema de `session_state` entre pestañas, confirmado ortogonal al UPS en el diagnóstico).

### Paso 0 — Confirmado antes de escribir

- **`EegAnalyzer.analyze()` es mono-canal**: aplana cualquier entrada a 1-D (`if signal.ndim != 1: signal = signal.flatten()`). La UI del EEG Lab sí es multi-canal a nivel de datos (`eeg_data` es un dict `{lead: señal}`, se llama `analyze()` una vez por canal) — pero cada llamada al analizador es global, sin localización. Confirma que band power + estado son escribibles ahora; BSI/Mu-ERD (multi-canal real) quedan para después.
- **Descriptores candidatos confirmados**: 5 bandas (delta/theta/alpha/beta/gamma, fronteras Hz estándar de texto, citables como definición) + banda dominante + clasificación. El mapeo banda→score es heurístico propio, sin cita — mismo tratamiento que el health score de corazón/pulmón.
- **Hallazgo que cambió el alcance real de "cerrar el círculo"**: confirmado por grep que `EegAnalyzer` no tenía NINGÚN llamador fuera de `eeg_neuro_lab/page_content.py` — cero conexión entre el EEG Lab real y `organism.update_from_sensors()`. `_update_brain()` se alimentaba EXCLUSIVAMENTE de los sliders de Twin OS, la situación pre-2.4 exacta. **Consultado con el usuario y aprobado**: se añadió el botón "Guardar estado al gemelo" en EEG Lab (Paso 4), no solo schema+builder, para que el círculo cierre de verdad.

### Paso 1 — Schema extendido (`schema.py`)

`UnifiedPhysiologicalState.neurological: DomainState` — campo NOMBRADO (no una colección genérica, confirmado en el diagnóstico), con `default_factory` a un `DomainState` vacío para que los 6 sitios que ya construían `UnifiedPhysiologicalState(...)` sin saber de neuro (builder.py, repository.py ×2, 3 tests) sigan funcionando idénticos sin tocarlos. `all_domains()` extendido a 3 dominios — esto es lo que hace que el narrador cite neuro automáticamente (Paso 3). Un nuevo `EventType.HIGH_STRESS_EEG` (aditivo al catálogo cerrado), con el umbral que YA usa `_update_brain()` (`stress_level > 75`, el tier más alto que ese método define) — ningún umbral clínico nuevo inventado.

### Paso 2 — `_neurological_state()` en el builder, con el gate

Mismo patrón que `_cardiovascular_state()`/`_respiratory_state()`. **Gate anti-órgano-fantasma**: `has_real_neuro_input = "alpha_power" in signals or "beta_power" in signals` (las dos señales que `_update_brain()` realmente consume) — sin ninguna de las dos, `descriptors={}`, nunca un cerebro sano por defecto. Mismo nivel de rigor que el gate cardiovascular (que tampoco exige que CADA sub-entrada -- ahí `hrv`/`complexity` -- sea real, solo la señal primaria).

Escribe: los 5 band power (gateados individualmente por presencia, `Provenance` del llamador, unidad `"power (u.a.)"` -- no se reclama una calibración µV² que la señal sintética no tiene) + `health_score`/`risk_score` + 5 campos de `NeurologicalDetail` (`mental_workload`, `cognitive_fatigue`, `attention`, `stress_perception`, `sleepiness`), todos `Provenance.DERIVADO`. **`frontal_activity`/`temporal_activity` deliberadamente NO se escriben** -- confirmado leyendo `_update_brain()` completo que esos 2 campos de `NeurologicalDetail` nunca se asignan, se quedan para siempre en su default de dataclass (55.0/45.0) -- persistirlos sería el mismo patrón de "campo fantasma" que ya se evitó con `trend`/`status` en fases anteriores.

`repository.py`: los 2 sitios de construcción (`get_latest_state`/`get_state_by_snapshot_id`) actualizados con `neurological=_domain_state_from_values("neurological", values)`.

### Paso 3 — Verificado por ejecución

- **El gate, las dos caras**: solo-ECG (`heart_rate`/`hrv`) → `neurological.descriptors == {}`, `cardiovascular` poblado. Solo-EEG (`alpha_power`/`beta_power`/...) → `neurological` poblado (12 descriptores), `cardiovascular`/`respiratory` vacíos. Confirmado por ejecución directa, no por lectura.
- **`HIGH_STRESS_EEG`**: `stress_level=90` → evento disparado, `severity=WARNING`, `related_descriptor="stress_perception"`. `stress_level=30` → sin evento.
- **El narrador cita neuro automáticamente, sin tocar `narrator/context.py`**: `build_context()` sobre un estado con solo EEG devolvió 10 `DescriptorContext` con `domain="neurological"` — confirma el beneficio del diseño genérico (`all_domains().values()`) que el diagnóstico había identificado.
- **No-regresión de las 3 raíces + escritores vivos**: ECG (`HR=76bpm, confianza=0.69`), HRV (`cardiovascular: 7 descriptores`), Respiratory (`respiratory: 8 descriptores`) — idénticos a la línea base de toda la campaña. Patient Pipeline sin excepción. Twin OS: el SVG sigue sincronizado al instante (Fase 5.1, 72→160bpm mismo rerun) y "Guardar este momento" (Fase 5.3) sigue persistiendo (133bpm confirmado en `get_value_history`).
- **Nuevos tests** (`tests/test_ups_state.py`, +3): gate de las dos caras + confirmación de que `frontal_activity`/`temporal_activity` NO aparecen; ida-y-vuelta de persistencia del dominio neuro; el evento `HIGH_STRESS_EEG` con su umbral.
- Barrido AppTest de los 10 módulos del hub: **10/10 sin excepción**, incluido EEG Neuro Lab.
- **EEG Lab en vivo**: botón "💾 Guardar estado al gemelo" (nuevo, `eeg_neuro_lab/page_content.py`) probado por AppTest -- snapshot persistido, `neurological: 12 descriptores`, `cardiovascular: 0`/`respiratory: 0` (gate confirmado también desde el flujo real de UI, no solo desde un script aislado).
- `pytest tests/ -q`: ver resultado completo abajo.
- Servidor real (`streamlit run app/main.py`, puerto 8607): HTTP 200; proceso detenido tras la verificación.

**El cerebro del organismo, que ya reaccionaba (Fase 2, banda cualitativa en la grilla de órganos), ahora también persiste al UPS** -- un cuarto órgano alimenta al gemelo con datos reales, con la misma honestidad de procedencia que los otros tres. El SVG del cerebro (visual) y los biomarcadores avanzados (BSI/DAR/TBR/CMC) quedan, deliberadamente, para sub-fases posteriores.

## 2026-08-30 — BIOCORE, Fase 5B COMPLETA (R2): DynamicECGGenerator (McSharry 2003) reemplaza al generador demo defectuoso

**Contexto**: `generate_demo_ecg_signal()` (`app/utils.py`) tenía 3 bugs confirmados por ejecución: ignoraba el `hr` pedido (QRS con ciclo fijo `t % 1`, `hr_rad` calculado y nunca usado), el detector que lo consumía saturaba en 220bpm (`np.clip(..., 0, 220)`), y su QRS no toleraba período variable. El experto clínico entregó y validó matemáticamente el modelo correcto — McSharry et al. 2003 (IEEE TBME): oscilador de fase angular + 5 ondas gaussianas + restitución QT de Bazett. Esta tanda lo construye como código de producción, lo re-valida sobre ese código real (no el entorno de pruebas), y lo integra al modo demo en vivo.

### Paso 1 — `DynamicECGGenerator`, fórmulas exactas del validador

`src/signals/ecg/dynamic_ecg_generator.py` (nuevo). ω(t)=2π·HR(t)/60; θ(t)=(Σω·dt) mod 2π (fase envuelta a (−π,π] para la distancia angular, necesario porque θ_P/θ_Q son negativos mientras θ se representa en [0,2π)); z(θ)=Σᵢaᵢ·exp(−Δθᵢ²/2bᵢ²) para P/Q/R/S/T con la matriz de parámetros exacta del validador (P: 0.15/0.25/−π/3; Q: −0.20/0.10/−π/12; R: 1.50/0.10/0; S: −0.40/0.10/+π/12; T: 0.40/0.40/π/2 base); Bazett dinámico θ_T(HR)=(π/2)·√(HR/60), NO constante. Vectorizado en NumPy.

**fs, sin discrepancia**: confirmado por grep que `generate_demo_ecg_signal(fs: float = 250, ...)` ya corría a `fs=250` por defecto — misma fs que usó el validador clínico para su batería. `DynamicECGGenerator` corre a la misma fs de producción; la validación cruzada del Paso 2 se hizo sobre esa fs real, no asumida trasladable desde el entorno de pruebas del experto.

### Paso 2 — Validación re-confirmada sobre el código de producción (los 5 tests del validador, a fs=250)

1. **Morfología a 60bpm**: P=0.150mV (t=0.828s), Q=−0.167mV, R=1.481mV (t=0.996s), S=−0.361mV, T=0.400mV (t=1.244s) — orden temporal P<Q<R<S<T confirmado. Amplitudes ligeramente distintas de la tabla pura por solape de gaussianas vecinas (esperado, no un bug).
2. **Respeta el HR**: correlación(hr=40, hr=200) = **9.6%** (el validador reportó ~10.5% en su entorno de pruebas — coincide).
3. **Círculo cerrado (TKEO)**: tabla pedido-vs-detectado para HR ∈ {40,60,100,120,150,180,200} — error máximo **0.16 bpm** (40/60/150 exactos a 0.000; 100/120/180/200 con 0.13-0.16bpm, atribuible a cuantización sub-muestra a 250Hz — el validador describió el mismo fenómeno como "truncamiento sub-muestra", su cifra de <0.1bpm no se reprodujo literalmente pero el orden de magnitud es el mismo: sub-1bpm en todo el rango, clínicamente insignificante). Sin discrepancia por fs — la validación se hizo a la fs real de producción.
4. **Bazett a HR=150**: θ_T=2.4836 rad, distancia S→T=2.2218 rad (esperado ~2.222, confirmado) — sin colisión T-QRS.
5. **Sin falsos picos**: HR=60 → 20 picos en 20s (esperado 20.0); HR=150 → 51 picos en 20s (esperado 50.0) — sin sobre-conteo.

Los 5 tests pasan a la fs de producción. Sin necesidad de detenerse y reportar (ninguna falló, fs sin discrepancia).

### Paso 3 — Inventario de consumidores (confirmado por grep antes de tocar)

3 llamadores vivos de `generate_demo_ecg_signal` en todo el árbol vivo (`_archive/` excluido, ya muerto): (1) `render_ecg_monitor_page()` — modo demo con slider HR 40-140, HR mostrado vía `estimate_ecg_heart_rate()` (el detector con tope en 220 — el origen del "220 fijo"); (2) `render_multisensor_page()` Vista Clínica/Educativa/Investigación/IA — `demo_channels` estático, `hr` por defecto (72), sin control interactivo; (3) `render_multisensor_page()` Vista Simulación — slider HR **deliberadamente deshabilitado desde 2026-08-21** con el comentario explícito "pendiente de reparación del generador de señal ECG (próxima tanda)" -- esta es esa tanda.

### Paso 4 — Integración en vivo + hallazgo no anticipado por el ticket

- **ECG Monitor modo demo**: `DynamicECGGenerator(fs=fs).generate(duration=20, hr=hr_demo)` reemplaza la llamada vieja. El HR mostrado ahora se mide con `ECGAnalyzer.detect_r_peaks_tkeo()` (el mismo motor TKEO del resto del pipeline clínico) **solo para la fuente demo** — las demás fuentes (MIT-BIH/PTB-XL/CSV/hardware, señal real) siguen con `estimate_ecg_heart_rate()` de siempre, sin tocar (barandilla: esto toca el generador, no los detectores de señal real).
- **Multisensor Fusion Lab Vista Clínica/Educativa/Investigación/IA**: `demo_channels['ECG']` migrado, mismo `hr=72` por defecto.
- **Multisensor Fusion Lab Vista Simulación — el slider HR se REACTIVÓ** (`disabled=True` retirado): confirmado leyendo `dashboards/multisensor.py::health_score()` que la fórmula SÍ consumía `heart_rate` desde siempre (`if 'heart_rate' in indices: ...scores['cardiovascular']...`) — el cálculo era real, solo estaba bloqueado por el generador mintiendo sobre el HR de la señal. Verificado por ejecución: HR=72→"73 bpm" detectado/Health Score 74.2; HR=130→"130 bpm" detectado/Health Score 60.0 — ambos cambian de verdad. El slider RR permanece deshabilitado (razón distinta y sin cambios: `health_score()` no consume `respiration_rate`). Copy de la pestaña actualizado para reflejar que HR ya es un control activo.
- **Hallazgo no anticipado por el ticket, reportado y corregido**: `_render_ecg_save_to_twin()` (el gate de "Guardar estado al gemelo") excluía la fuente demo por completo, con un comentario que decía "bug conocido, arco de señal pendiente". Ese comentario quedó **falso** tras el fix (el bug ya no existe) aunque la **política de exclusión sigue siendo correcta por una razón distinta y más fundamental**: el HR demo es un valor elegido por el estudiante en un slider, nunca medido de nada — persiste como tal aunque el generador ya sea fiel al valor pedido. Se actualizó el texto (docstring + `st.info` visible) para explicar la razón real, sin cambiar la política (la fuente demo sigue sin poder escribir al UPS).

### Paso 5 — Generador viejo retirado

Confirmado por grep (segunda vez, tras migrar los 3 consumidores): cero llamadores vivos de `generate_demo_ecg_signal` en todo el árbol (`app/`, `domain/`, `clinical/`, `src/`, `tests/`). Función eliminada de `app/utils.py` (reemplazada por un comentario histórico); `app/supermodules/__init__.py` (el shim de re-exportación) actualizado -- la línea `generate_demo_ecg_signal = app_utils.generate_demo_ecg_signal` se retiró **antes** de que rompiera el import del paquete completo (habría fallado con `AttributeError` al cargar `app.supermodules`, ya que el atributo dejó de existir en `app_utils`). Ningún test referenciaba la función directamente -- nada que actualizar por "forma vieja".

### Verificación (por ejecución EN VIVO, no solo entorno de pruebas)

- Sanity import: limpio.
- **La prueba en vivo (ECG Monitor)**: slider "Demo HR" movido a 72/100/130bpm (rango real del control) — HR mostrado = HR pedido, **exacto**, en los 3 casos. Confirmado explícitamente que 220 fijo nunca aparece, sin importar el valor pedido.
- **Multisensor Vista Simulación**: HR=72→73bpm detectado/Health Score 74.2; HR=130→130bpm detectado/Health Score 60.0 -- ambas métricas cambian de verdad (antes: constantes, control placebo).
- **Detectores intactos**: `pytest tests/ -q` incluye el banco BBB (45/45) y la cohorte TKEO -- ningún archivo de `clinical/ecg_analyzer.py` se tocó en esta tanda.
- **No-regresión de señal real**: MIT-BIH 100 vía ECG Lab -- `HR=76bpm, confianza=0.69`, idéntico a la línea base de toda la campaña; HRV `cardiovascular: 7 descriptores`; Respiratory `respiratory: 8 descriptores` -- los 3 labs que escriben al UPS sin cambios.
- Barrido AppTest de los 10 módulos del hub: **10/10 sin excepción**.
- `pytest tests/ -q`: verde (ver resultado completo abajo).
- Servidor real (`streamlit run app/main.py`, puerto 8595): HTTP 200; proceso detenido tras la verificación.

**Arco de señal de ECG cerrado**: generador (McSharry 2003, fiel al HR pedido) y detector (TKEO, 6 rondas de validación con el experto) mutuamente validados -- el generador se valida contra el detector que ya era de grado clínico, y el detector confirma que el generador ya no miente. El 220 fijo y el control placebo de Multisensor mueren en la misma tanda que los causó.

## 2026-08-30 — BIOCORE, Fase 5.2 + 5.3: nombres clarificados + escritores del UPS colapsados — Fase 5 COMPLETA

**Contexto**: cierre del arco de la Fase 5. 5.2 (cero lógica): "Escenarios de paciente e intervenciones simuladas" (mutación en memoria) colisionaba léxicamente con "Simulador de escenarios clínicos" (trayectoria persistida) — dos cosas distintas compartiendo la palabra "Escenarios". 5.3 (refactor de comportamiento idéntico): los 4 escritores del UPS (Guardar este momento, Simulador, Narrador, Causal) repetían a mano el mismo patrón `from_digital_twin_organism(...) + save_state(...)`.

### 5.2 — Nombres clarificados

- `render_scenario_and_interventions()`: expander `"👥 Escenarios de paciente e intervenciones simuladas"` → `"⚡ Ajustes rápidos e intervenciones (en memoria, sin persistir)"`. Sub-header `"**Escenario rápido:**"` → `"**Preset rápido:**"` (consistencia interna). Docstring de la función documenta la colisión y por qué se resolvió así.
- `render_ups_scenario_simulator()` (el simulador de trayectoria): **sin cambios** — ya era claro ("Simulador de escenarios clínicos (persistido en el UPS)"); una vez que el otro mecanismo dejó de decir "Escenarios", "Escenario clínico:" (su selectbox) queda como el único uso de la palabra en toda la página, sin competencia.
- **Agrupación visual: evaluada, no aplicada.** `render_sensor_controls()` (los sliders) se renderiza al principio de la página (justo después del header); `render_scenario_and_interventions()` vive mucho más abajo, dentro de "🧭 Herramientas avanzadas", junto a los 4 escritores del UPS. Fusionarlos habría significado mover una sección completa de posición — una reestructuración de layout, no un cambio cosmético de bajo riesgo. Se dejó solo el renombre, como el ticket permitía explícitamente.
- Riesgo ML: nueva línea explicando por qué no reacciona al instante — *"⏳ Este panel integra la trayectoria del paciente (tendencia real, no solo el instante) — por eso no cambia al mover un slider como el Cuerpo Digital o el clasificador de ECG..."* — honestidad de presentación (Fase 2): el panel dice por qué se comporta distinto, en vez de parecer roto.

### 5.3 — Los 4 escritores, colapsados sin excepción (los 4 encajaron en el molde común)

Confirmado por grep antes de extraer: los 4 escritores usaban `provenance=Provenance.SIMULACION` siempre, ninguno pasaba `confidence` explícito — solo `source_detail` variaba. A diferencia de los `create_patient()` de la Fase 3 (3 nombrados + 1 distinto), aquí **los 4 encajaron en un único helper sin perder nada**.

- `persist_current_state(session, organism, patient_id, source_detail, provenance=...)` (nuevo, `app/utils/physiological_state.py`, junto a `get_current_physiological_state()` de la Fase 5.1 — primas: una persiste lo que la otra devuelve sin persistir). Encapsula `from_digital_twin_organism(...) + save_state(...)`, devuelve `(state, snapshot_id)` — cubre tanto a los 3 llamadores que descartan el resultado (Guardar/Narrador/Causal, que vuelven a leer fresco de la DB después) como al Simulador, que sí usa ambos valores (`state` para el `ScenarioStep`, `snapshot_id` para adjuntar la referencia de PA calculada).
- **Guardar este momento** (`render_synced_digital_twin_body`), **Narrador** (`render_clinical_narrator`), **Razonamiento causal** (`render_causal_reasoning`): migrados — cada uno ahora es una sola línea (`persist_current_state(session, organism, patient_id, source_detail="...")`) en vez de 6.
- **Simulador de escenarios** (`run_rich_scenario()`, `domain/physiology/scenarios/rich_engine.py`): migrado también. Este archivo ya importaba de `app.engines` (precedente existente de que `domain/physiology/scenarios/` depende de `app/` en este puente específico) — añadir `app.utils.physiological_state` sigue el mismo patrón ya aceptado, sin introducir una capa nueva de acoplamiento.
- Imports limpiados: `Provenance`/`from_digital_twin_organism`/`save_state` quedaron sin ningún uso real en `twin_shell/pages.py` (confirmado por grep) tras la migración — removidos del import; `create_patient` sigue usado (modo caso clínico, vía `create_ephemeral_case_patient`, sin tocar).

### Verificación (por ejecución)

- Sanity import: limpio.
- **5.2 confirmado por AppTest**: expander nuevo `"⚡ Ajustes rápidos e intervenciones (en memoria, sin persistir)"` presente; ningún expander dice "Escenarios de paciente"; el simulador de trayectoria es el único lugar con la palabra "Escenario"; `"Preset rápido:"` presente, `"Escenario rápido:"` ausente; línea explicativa del Riesgo ML presente y correcta.
- **5.3 — prueba de identidad de comportamiento, 2 escritores comparados contra sus valores exactos de antes del refactor**: "Guardar este momento" con FC=144bpm → snapshot persistido con `valor=144.0, provenance=simulacion, source_detail='twin_visual:checkpoint_manual'` (idéntico). Narrador forzado (monkeypatch, sin `ANTHROPIC_API_KEY`) con FC=101bpm → `valor=101.0, provenance=simulacion, source_detail='narrador:snapshot_bajo_demanda'` (idéntico) — mismos `source_detail` que antes del refactor en ambos casos, confirmando que el helper no alteró ninguna procedencia.
- **Los 3 orígenes del Simulador, verificados por ejecución**: Twin OS (clic en "Ejecutar y persistir" → `st.rerun()` interno resuelto por AppTest → "Última trayectoria persistida: 🟢 Sano — línea base" confirmado, 0 excepciones); Academia (`generate_case()` llamado directo → paciente efímero creado, 0 excepciones); modo caso clínico de Twin OS (forzado vía monkeypatch → `clinical_case_patient_id` creado, 0 excepciones). Los 3 pasan por el mismo `run_rich_scenario()` refactorizado sin romperse entre sí.
- No-regresión: los 3 labs (ECG/HRV/Respiratory) siguen escribiendo idéntico (`HR=76bpm, confianza=0.69`; `cardiovascular: 7 descriptores`; `respiratory: 8 descriptores`); la Fase 5.1 (SVG instantáneo) re-verificada intacta (72bpm→160bpm en el mismo rerun, sin guardar).
- Barrido AppTest de los 10 módulos del hub: **10/10 sin excepción**.
- `pytest tests/ -q`: **429 passed** (ver resultado completo abajo).
- Servidor real (`streamlit run app/main.py`, puerto 8583): HTTP 200; proceso detenido tras la verificación.

**Fase 5 queda COMPLETA**: 5.1 mató la desincronización visible (punto único de verdad para lectura), 5.2 desambiguó los nombres, 5.3 colapsó la escritura en un único helper — el mismo patrón de "punto único de verdad" (Fase 3 para identidad, Fase 5 para estado) cierra el refinamiento post-Capa-2 iniciado con el diagnóstico de los 5 frentes.

## 2026-08-30 — BIOCORE, Fase 5.1: punto único de verdad del estado fisiológico — `get_current_physiological_state()`

**Contexto**: el diagnóstico de la Fase 5 (Paso 0) encontró que 3 paneles de Twin OS (Cuerpo Digital SVG, Riesgo ML, clasificador de ECG) leían `get_latest_state()` — el ÚLTIMO SNAPSHOT PERSISTIDO — mientras las tarjetas de órgano leían `organism` directo (memoria). Como los sliders nunca persisten por sí mismos, movían las tarjetas al instante pero dejaban esos 3 paneles mostrando el estado de hace varios clics — la desincronización visible que más se nota en demo. Opción elegida: (c) — un punto único (`get_current_physiological_state()`) que envuelve `from_digital_twin_organism()` sin persistir, análogo literal de `get_active_patient_id()` (Fase 3). Rechazadas: memoria directa en cada lector (perdía la garantía de honestidad de los docstrings de Fase 1.3/1.4) y auto-persistir cada slider (reintroduce la inundación de trayectoria que la Fase 2.4 evitó a propósito).

### Paso 1 — `get_current_physiological_state()`

`app/utils/physiological_state.py` (nuevo, junto a `patient_session.py` de la Fase 3): envuelve `from_digital_twin_organism(organism, patient_id, provenance=Provenance.SIMULACION, ...)` — la MISMA conversión que ya usan los 4 escritores del UPS — sin llamar `save_state()`. Devuelve `UnifiedPhysiologicalState`, forma idéntica a `get_latest_state()` (confirmado: mismo tipo de retorno, mismos campos `patient_id`/`timestamp`/`cardiovascular`/`respiratory`/`events`). Misma disciplina de procedencia — no es un atajo, es el mismo estado que se persistiría si se guardara.

### Paso 2 — 2 de los 3 lectores migrados; el 3° detenido y reportado (barandilla respetada)

- **Cuerpo Digital SVG** (`render_synced_digital_twin_body`): migrado. Ahora lee `get_current_physiological_state(organism, patient_id)` en cada rerun — sin gatear tras ningún botón.
- **Clasificador de ECG** (`render_ecg_classifier_panel`): migrado. Requirió un cambio de firma en `build_synthetic_ecg_from_ups()` (`domain/physiology/ml/ecg_signal_source.py`) — antes recibía `(session, patient_id)` y leía `get_latest_state()` ella misma; ahora recibe el `state` ya construido directamente (nunca necesitó más que eso). Único llamador vivo, sin tests que dependieran de la firma vieja — cambio de bajo riesgo, confirmado por grep antes de tocar.
- **Riesgo ML** (`render_ml_risk_panel` / `build_risk_features`): **NO migrado — detenido y reportado, según la barandilla del ticket**. `build_risk_features()` no solo lee el snapshot más reciente: también arma `trend_data` (`get_value_history`, historial que solo existe persistido — el organismo en memoria no lleva trayectoria) y `systolic_bp`/`diastolic_bp` (`ClinicalReferenceValue` atada a un `snapshot_id` concreto ya persistido, sin equivalente en memoria). Confirmado además con `tests/test_clinical_reference.py` (4 tests que ejercitan exactamente ese comportamiento persistido-dependiente) que este acoplamiento es contractual, no incidental. Migrar habría exigido degradar esos 2 campos a `None` (comportamiento distinto, no "mismo dato, otro origen") o reescribir `build_risk_features()` para mezclar memoria con consultas históricas — fuera del alcance de "cambiar de dónde leen, no cómo procesan". Sigue leyendo el último snapshot persistido sin cambios; documentado inline en su docstring y en `CHANGELOG.md` como candidato de una tanda futura, no como un olvido.

### Paso 3 — Copy honesto (el matiz crítico del ticket)

- SVG: título `"### 🫀 Cuerpo Digital — sincronizado con el UPS"` → `"### 🫀 Cuerpo Digital — tu estado actual"`. Caption ya no dice "último snapshot persistido en el UPS", dice "tu estado fisiológico ACTUAL... se actualiza solo mientras tengas esta página abierta; para conservarlo en la trayectoria permanente, usa el botón de arriba".
- Botón "🔄 Sincronizar con sliders actuales" → **"💾 Guardar este momento en la historia del paciente"** — su propósito real cambió (ya no "arregla el SVG", que ya está al día por construcción; ahora es crear un checkpoint permanente en la trayectoria) y el copy lo dice.
- Clasificador de ECG: expander `"(real, desde el UPS)"` → `"(real, desde tu estado actual)"`; radio `"Sintética desde el UPS (modo A)"` → `"Sintética desde tu estado actual (modo A)"`; caption `"FC real del UPS"` → `"FC real de tu estado actual"`.
- `render_ups_body()` (`ups_body_visual.py`): docstring de módulo y de función actualizados — ya no afirman que `state` viene siempre del UPS persistido; explican los 2 caminos igualmente honestos. `"FC: sin dato en el UPS"` → `"FC: sin dato"` (la única mención de "UPS" en un mensaje de fallback que ahora es alcanzable desde ambos caminos — generalizada, mismo criterio que `rr_label`/`spo2_label`, que ya decían solo "sin dato").
- Riesgo ML (no migrado): su copy se dejó **intacto** a propósito — sigue siendo exacto para lo que sigue haciendo (leer el último persistido).

### Paso 4 — El desfase narrador/causal: se resolvió solo, confirmado por ejecución

El diagnóstico de la Fase 5 había encontrado que "Explicar estado actual"/"Explicar origen" persisten pero el SVG (renderizado antes en el script) no lo reflejaba hasta la siguiente interacción. **Verificado que 5.1 lo resuelve sin ningún `st.rerun()` adicional**: ni el narrador ni el razonamiento causal mutan `organism` — solo lo leen y persisten una copia — así que el SVG (que ahora lee `organism` directo) nunca tuvo nada que "esperar". Prueba por ejecución (narrador forzado vía monkeypatch, sin `ANTHROPIC_API_KEY`): SVG mostraba `FC: 155 bpm` ANTES de narrar, y `FC: 155 bpm` DESPUÉS de narrar, mismo rerun del clic — nunca hubo desfase que corregir.

### Verificación (por ejecución)

- Sanity import: limpio.
- **La prueba central**: slider de FC movido a 160bpm, sin pulsar ningún botón de guardar — en el MISMO rerun: tarjeta de órgano (memoria) refleja 160bpm, SVG muestra `"FC: 160 bpm"` (antes: `"FC: 72 bpm"`, el valor por defecto — cambio confirmado con captura antes/después), clasificador de ECG muestra `"FC real de tu estado actual: 160 bpm — evento de arritmia activo"` (HR=160 dispara `ARRHYTHMIA_RISK_HR_EXTREME` correctamente). Riesgo ML (deliberadamente no migrado) confirmado con su copy y comportamiento intactos.
- Escritores intactos: botón renombrado clicado → `st.success("Momento guardado...")` → consulta directa a `get_value_history()` confirma el snapshot real con `133.0` bpm en la trayectoria del paciente — persistencia idéntica a antes.
- No-regresión de los 3 labs integrados al UPS: `HR=76bpm, confianza=0.69` (ECG sobre MIT-BIH 100), `cardiovascular: 7 descriptores` (HRV), `respiratory: 8 descriptores` (Respiratory) — idénticos a antes de esta fase.
- Barrido AppTest de los 10 módulos del hub: **10/10 sin excepción**.
- `pytest tests/ -q`: **429 passed** (ver resultado completo abajo).
- Servidor real (`streamlit run app/main.py`, puerto 8571): HTTP 200; proceso detenido tras la verificación.

Este es el segundo punto único de verdad de la Capa post-2 (tras `get_active_patient_id()`, Fase 3) — mismo patrón, ahora aplicado al estado fisiológico en vez de a la identidad del paciente.

## 2026-08-30 — BIOCORE, Fase 3: paciente único de sesión — `get_active_patient_id()` como punto único de verdad

**Contexto**: el diagnóstico del Frente 1 encontró 4 identidades de `patient_id`: Twin OS + 3 labs (Respiratory/HRV/ECG) compartiendo `twin_shell_ups_patient_id` por convención (mismo nombre de clave copiado en 4 sitios, no una autoridad real); Patient Pipeline con su propio vestigio roto (`create_patient(display_name=etiqueta)` en cada cambio de input, sin find-or-create, continuidad perdida en silencio); Academia con su paciente efímero por caso (correcto, debía seguir así). Decisión: paciente único de sesión vía un punto único de verdad, `get_active_patient_id()`. Riesgo medio — toca identidad de paciente en 4+ módulos.

### Paso 0 — Diagnóstico confirmado, con una discrepancia real: una 5ª identidad no vista por el mapa

Grep exhaustivo de `create_patient(` en todo `app/`+`domain/` (no solo `session_state["*patient*"]`) confirmó las 4 identidades del mapa tal cual, **y encontró una 5ª**: `render_clinical_case_mode()` en `twin_shell/pages.py` (el "Modo caso clínico interactivo" **dentro de Twin OS**, distinto del modo caso de Academia) tenía su propio `create_patient(display_name="Caso clínico interactivo")` inline, bajo una clave nueva `clinical_case_patient_id` — estructuralmente idéntico al patrón de Academia, pero sin ningún nombre/comentario que declarara la intención (a diferencia de `create_ephemeral_basal_patient()`, el modo "basal" del simulador, que ya cumplía ese estándar). Reportado al usuario antes de tocar nada, per el punto de parada del ticket — decisión tomada: **unificar los 3 mecanismos efímeros** bajo un solo `create_ephemeral_case_patient()` compartido (Academia + modo caso clínico de Twin OS; el modo "basal" conserva su propia forma, no se tocó).

Resto del Paso 0, confirmado exactamente como el mapa decía: el orden de creación es seguro (guard `if key not in st.session_state`, reruns de un solo hilo por sesión — no hay condición de carrera real, solo el primer módulo abierto la crea); el vestigio de Patient Pipeline confirmado línea por línea (`create_patient(display_name=patient_label)` en cada cambio de input, `external_id` — `UNIQUE`, nunca conectado — sigue reservado sin usar); Academia confirmada genuinamente efímera y **sin ningún mecanismo de limpieza** (grep de `domain/physiology/state/` — cero función `delete_patient`, cada caso/quiz/escenario basal deja una fila huérfana para siempre; nota fuera de alcance, no se construyó).

### Paso 1 — El punto único de verdad

`app/utils/patient_session.py` (nuevo): `get_active_patient_id()` — crea el paciente único la primera vez que se llama (idempotente, mismo guard que antes, ahora centralizado) y lo devuelve; `get_active_session_factory()` — mismo principio para el sessionmaker compartido; `set_active_patient_id()` — sustitución deliberada y excepcional (único llamador legítimo: el modo "Basal" de Twin OS, que ya tenía su propio botón de "volver"); `get_active_patient_display_name()`/`rename_active_patient()` — el nombre cosmético (ver Paso 2). Mismas claves de `session_state` que el bootstrap original (`twin_shell_ups_session_factory`/`twin_shell_ups_patient_id`) — no se renombran, lo que cambia es que ahora hay un único lugar que decide cuándo crearlas.

`rename_patient()` (nuevo, `domain/physiology/state/repository.py`): actualiza `PatientRecord.display_name` de un paciente ya existente — cosmético, nunca crea uno nuevo ni cambia su `id`.

### Paso 2 — Consumidores migrados

- **Twin OS** (`init_session()`, `render_ups_scenario_simulator()`, y 6 sitios más de lectura en `twin_shell/pages.py`): todo pasa ahora por `get_active_patient_id()`/`get_active_session_factory()`/`set_active_patient_id()`. El toggle "Basal ↔ paciente continuo" no cambió de comportamiento, solo de a través de qué función escribe.
- **ECG Lab, HRV, Respiratory Lab**: los 3 bootstraps inline idénticos (8-9 líneas cada uno, copiados) reemplazados por las 2 llamadas a `get_active_patient_id()`/`get_active_session_factory()`. Mismo paciente de siempre — el comportamiento no cambia, deja de depender de la convención de copiar el nombre de la clave.
- **Patient Pipeline — el vestigio enterrado**: se retiró `create_patient(display_name=etiqueta)` por completo. **Decisión tomada: opción (b)** — el `text_input` se conserva (no se retira la affordance) pero pasa a ser cosmético: renombra al paciente único activo vía `rename_active_patient()`, nunca crea uno nuevo. Se renombró también el campo de "ID de paciente" a "Nombre del paciente" — el texto viejo sugería una identidad que el campo nunca cambiaba de forma segura; el nuevo nombre describe lo que realmente hace. Por qué (b) y no (a): conserva la utilidad real (nombrar al paciente algo memorable) sin la trampa de continuidad rota — retirar el input entero habría sido más simple pero perdía una affordance honesta sin necesidad.
- **Academia + modo caso clínico de Twin OS — unificados, explícitamente efímeros**: `create_ephemeral_case_patient(session, label)` (nuevo, `rich_engine.py`, junto a `create_ephemeral_basal_patient()`) reemplaza los 2 `create_patient()` inline que existían por separado. Docstring declara explícitamente por qué debe seguir siendo efímero (mezclar un caso didáctico con la trayectoria del paciente continuo rompería el ejercicio de diagnóstico ciego).

### Paso 3 — Continuidad verificada por ejecución, no por lectura

- **La prueba central**: guardar desde Respiratory Lab, luego desde HRV Analysis, ambos bajo el mismo `patient_id` capturado de una sesión fresca de Twin OS — consulta directa al UPS (`get_value_history`) confirma **1 snapshot con `heart_rate` y 1 snapshot con `respiratory_rate`, ambos bajo el mismo `patient_id`** — un paciente acumulando trayectoria de 2 labs distintos, no dos pacientes separados.
- **El vestigio confirmado muerto**: `patient_id` capturado antes de cambiar el "Nombre del paciente" en Patient Pipeline, cambiado el campo a un nombre nuevo, `patient_id` capturado después — **idéntico** (antes habría sido un UUID distinto). Consulta directa al UPS confirma que `display_name` sí se actualizó en el mismo registro.
- **Academia confirmada aislada**: sentinel (`"CONTINUOUS-PATIENT-SENTINEL"`) sembrado en `twin_shell_ups_patient_id`, Academia renderizada completa (ambas pestañas) — el sentinel sigue intacto después, `academia_case_patient_id` nunca se pobló (el botón "Nuevo caso sintético" está gateado tras `ANTHROPIC_API_KEY`, ausente en este entorno — mismo límite honesto de siempre, no una limitación de esta tanda). Reforzado por grep: `generate_case()`/`create_ephemeral_case_patient()` no importan ni referencian `patient_session.py` en ningún punto.

### Verificación (por ejecución)

- Sanity import: limpio.
- Grep final: cero lecturas/creaciones directas de `twin_shell_ups_patient_id`/`twin_shell_ups_session_factory`/`patient_pipeline_ups_patient_id`/`patient_pipeline_ups_session_factory` fuera de `patient_session.py` (la única fuente) y comentarios históricos. `create_patient(` (la función cruda del repositorio) confirmado con exactamente 3 llamadores en todo el repo, los 3 nombrados y deliberados: `get_active_patient_id()`, `create_ephemeral_basal_patient()`, `create_ephemeral_case_patient()`.
- Barrido AppTest de los 10 módulos del hub + Patient Pipeline: **11/11 sin excepción**.
- No-regresión de datos: los 3 labs siguen escribiendo exactamente lo mismo bajo el patrón nuevo (ver prueba de continuidad arriba) — el cambio es de bajo qué `patient_id` se usa, nunca de qué se calcula/escribe.
- `pytest tests/ -q`: **429 passed** (ver resultado completo abajo).
- Servidor real (`streamlit run app/main.py`, puerto 8559): HTTP 200; proceso detenido tras la verificación.

Este patrón — un punto único de verdad reemplazando una convención de claves copiadas — es el que la Fase 5 replicará para el estado persistido en general.

## 2026-08-30 — BIOCORE, Fase 4: Learning Hub consolidado en Academia — cáscaras de Education/Guides retiradas

**Contexto**: el diagnóstico del Frente 4 confirmó que de los 3 módulos del Learning Hub, solo Academia Clínica tiene contenido real (quiz de 16 preguntas con feedback IA, casos clínicos ciegos, tabla de 12 derivaciones, tutor IA). Decisión: el Learning Hub queda = Academia Clínica. Escribir contenido pedagógico nuevo (Neurofisiología, Respiratorio, Músculo) es un arco de producto futuro, no esta tanda.

### Paso 0 — Diagnóstico de rescate: más fachada de la que el mapa había nombrado

**Education**: releído completo antes de retirar nada. Además de las 2 piezas ya señaladas por el mapa (las 4 tarjetas "🚧 en desarrollo, sin contenido real todavía" y el `st.selectbox` de 3 diagnósticos fijos — placebo confirmado, ninguna conexión al banco de casos real de Academia), se encontró que el resto de la página era la MISMA categoría de fachada sin haber sido nombrada explícitamente: las vistas "Investigación" y "Simulación" del selector de 5 vistas, y las secciones "1. Datos"/"2. Interpretación"/"5. Investigación"/"Tutor de ruta de aprendizaje" eran, cada una, una sola frase (`st.write(...)`) describiendo una capacidad que nunca se construyó ("BIOCORE AI sugiere rutas de estudio conforme a tu progreso..." — no existe ningún sistema de recomendación). Los 3 bloques honestos que sí tenía (vista "Educativa" → redirección al quiz real; vista "IA" y sección "4. IA" → tombstone honesto del "Avanzar en aprendizaje" ya retirado; sección "3. Educación" → redirección a la tabla real de 12 derivaciones) se vuelven redundantes una vez Education deja de existir como parada intermedia — el usuario llega a Academia directo desde el sidebar, no necesita que Education se lo repita. **Conclusión: nada de Education era rescatable — página retirada por completo, no solo las 2 piezas nombradas.**

**Guides**: resultó más obsoleto de lo esperado, no solo "documentación vieja". Su bullet de Clinical Hub listaba únicamente 3 de los 8+ módulos reales actuales (ECG/Multisensor/Respiratory — faltaban EEG Neuro Lab, EMG Muscle Lab, HRV Analysis, Biomarkers Lab, Patient Pipeline), y mencionaba "cursos" en Learning Hub que nunca existieron como tales — exactamente el caso de "una guía que describe una navegación que ya cambió". La sección "Roles" describía capacidades sin ningún feature real detrás (Investigador: "exporta datos, compara cohortes"; Médico: "monitoreo integrado... IA explicable" — no son el toggle real Estudiante/Clínico/Investigador de Digital Twin OS, que cambia vocabulario/profundidad, no estas funciones). El botón "Abrir onboarding rápido" no activaba ningún flujo — confirmado por grep que `mission_goal` solo lo leía esa misma página, en ningún otro sitio del repo. La única línea genuinamente correcta ("Usa el selector de hub en la barra lateral...") no justifica conservar una página cuyo resto está mal. Corregirla bien habría significado escribir una guía nueva y precisa — autoría de contenido, fuera del alcance de esta tanda. **Conclusión: página retirada por completo.**

Ningún hallazgo inesperado con valor real — ambas páginas resultaron tener MENOS que rescatar de lo que el mapa ya sugería, nunca más.

### Paso 1 y 2 — Retirado

- `render_education_page()` (`app/main.py`): función completa eliminada (5 vistas, 2 secciones de redirección honesta, 4 tarjetas fachada, 1 selectbox placebo, 4 secciones de una sola frase sin contenido).
- `render_guides_page()` (`app/main.py`): función completa eliminada (bullets de navegación obsoletos, "Principios de integración", "Roles", botón de onboarding placebo).
- `st.session_state.mission_goal` (bootstrap de `main()`): init eliminado — quedaba huérfano sin `render_guides_page()`, cero otros lectores confirmado por grep.
- `HUBS["Learning Hub"]`: de `["🎓 Education", "🏫 Academia Clinica", "📚 Guides"]` a `["🏫 Academia Clinica"]`.
- `render_page_content()`: el dispatch `if "Academia" in page / elif "Education" in page / else render_guides_page()` se simplificó a una sola llamada directa — ya no hace falta desambiguar por substring con un único módulo en el hub.
- **Academia Clínica: NO tocada.** Docstring de `render_theory_section()` (`academia/pages.py`) recibió solo una nota histórica apuntando a este retiro, cero cambio funcional.

### Paso 3 — Navegación verificada coherente

- El selector de módulo del sidebar (`st.sidebar.selectbox('Selecciona un módulo', HUBS[hub], ...)`) funciona igual con 1 opción que con 3 — sin rama muerta, sin índice fuera de rango (confirmado por ejecución, no solo por lectura del código).
- Ninguna rama de navegación muerta tipo "Gemelo Digital" (el hallazgo de 2.2): `render_education_page()` ya no existe, así que su propio `render_view_selector(views=[...])` con vocabulario explícito tampoco — el problema y su portador desaparecieron juntos.

### Verificación (por ejecución)

- Sanity import: limpio.
- **Flujo real de navegación** (`AppTest.from_file("app/main.py")`, no llamando la función de render directo): seleccionar "Learning Hub" en el radio del sidebar → el selectbox de módulo muestra **una sola opción**, `'🏫 Academia Clinica'` → el render aterriza en el header real "Academia BIOCORE AI" → `"Education"`/`"Guides"` ausentes del HTML → `"en desarrollo, sin contenido real"` ausente → cero excepciones.
- Academia confirmada intacta por ejecución: `at.tabs` → `['📝 Lecciones y Casos', '📖 Tutor IA']` presentes; `at.expander` → `['📖 Teoría — Las 12 derivaciones del ECG', '🧪 Caso clínico sintético (diagnóstico ciego)']` presentes; selectbox de lección (`ECG Básico/ECG 12-derivaciones/Arritmias/Otras señales`) y botón "Iniciar Quiz" presentes — nada del contenido real cambió.
- Grep final en `app/main.py`: cero referencias vivas a `render_education_page`/`render_guides_page`/`mission_goal`/"Education"/"Guides" fuera de comentarios históricos.
- Barrido AppTest de los 9 módulos restantes del hub + Academia: **10/10 sin excepción**.
- Patient Pipeline (no tocado por esta fase) re-verificado sin excepción.
- `pytest tests/ -q`: **429 passed** (ver resultado completo abajo).
- Servidor real (`streamlit run app/main.py`, puerto 8547): HTTP 200; proceso detenido tras la verificación.

**El Learning Hub queda = Academia Clínica**, sin cáscaras de por medio. La promesa fundacional "aprender es intentar, equivocarse y ser corregido" se cumple hoy solo para ECG (quiz + casos + narrador IA, todo real) — el contenido pedagógico del resto de sistemas fisiológicos queda documentado como arco de producto futuro, no fingido con tarjetas "en desarrollo".

## 2026-08-30 — BIOCORE, Fase 2 (honestidad de presentación): heurísticos puros a banda cualitativa, híbridos con ancla a número con procedencia visible

**Contexto**: el diagnóstico del Frente 2 encontró que los scores del gemelo YA son honestos en el código (declaran su naturaleza heurística en `help=`), pero comunican falsa precisión visualmente — un "74%" grande grita medición, la letra pequeña admite heurística. Principio rector: un número solo se muestra como número si tiene una base real que justifique su precisión; si es pesos arbitrarios sin ancla citada, pasa a banda cualitativa. **Ningún cálculo cambió** — el score se sigue computando igual en ambos casos, solo cambia si se muestra como número o como banda. Cero archivos de motor (`digital_twin_organism.py`/`prediction_engine.py`) tocados en esta fase — todo el cambio vive en `twin_shell/pages.py` (presentación).

### Parte A — Heurísticos puros → banda cualitativa

- **Estado Fisiológico Global** (`global_health_score`, promedio de promedios) → "Estable / En observación / Crítico". Cortes reutilizados, no inventados: los mismos 70/40 que `render_ambient_header()` YA usaba para colorear el número (sin crear un tercer par de umbrales para lo mismo).
- **Coherencia sistémica** (`100 - std(health_scores)`) y **Resiliencia** (`salud*0.4 + (100-riesgo)*0.3 + hrv*0.3`) → "Alta / Media / Baja", mismos cortes 70/40.
- **Acoplamiento Cerebro↔Corazón** y **Cerebro↔Músculos** → "Alto / Medio / Bajo" (`_coupling_band()`, cortes 30%/70%). El corte bajo (30%) **no es nuevo**: reutiliza el umbral que YA dispara la alerta de "desacoplamiento"/"desincronización" en `_detect_anomalies()` (`< 0.3`) — la banda usa el mismo límite que el propio motor ya trataba como significativo.
- **Health score Cerebro/Músculos/Autonómico** (tarjetas de órgano + panel detallado, los 3 modos Estudiante/Clínico/Investigador) → banda cualitativa. Aquí NO se inventó un tercer esquema: se reutilizó `organ.status` (`OrganHealthStatus`, propiedad YA calculada en `digital_twin_organism.py`, umbrales 80/60/40) — una clasificación cualitativa real que ya existía en el motor, nunca antes mostrada como tal (solo alimentaba el color del número). El valor numérico exacto queda disponible en el `help=` del metric ("valor interno: X/100"), nunca oculto — solo no es lo primero que se lee.

En todos los casos, el número SIGUE calculándose y usándose internamente para decidir la banda (`_qualitative_band(value, ...)` recibe el float real) — grep confirmó que ningún consumidor externo lee el valor numérico *mostrado*, porque ninguno leía el HTML/texto renderizado para empezar; todos los consumidores reales (`_add_to_history`, `render_timeline`'s gráfico de línea "Salud Global"/"Coherencia", `_compute_resilience`, las comparaciones de `_detect_anomalies`) leen `global_state`/`health_score` directamente — la fuente de datos, no la presentación — confirmado por grep y sin cambios.

### Parte B — Híbridos con ancla citada → número con procedencia VISIBLE

- **Health score Corazón/Pulmones**: siguen como número (`X/100`), con `🟢🔵` ahora en la ETIQUETA misma del `st.metric`/en la tarjeta del órgano (antes solo en `help=`) — visible de un vistazo, no escondido en tooltip. `_health_score_metric_args()` centraliza esta decisión (un solo lugar, no 4 copias) para los 4 sitios que ya mostraban este número (tarjeta de la grilla + los 3 modos del panel detallado).
- **Acoplamiento Corazón↔Pulmones** (razón 4:1 HR:RR, cita PRQ): sigue como número (`X%`), con `🟢🔵` en la etiqueta del metric.
- **Riesgo por sistema Cardiovascular/Respiratorio** (`render_risk_assessment`, citan ACLS/ATLS/NEWS2/AASM): mismo tratamiento — `🟢🔵` ahora antepuesto al nombre del sistema en el `st.markdown`, visible junto al número, no solo en el `st.caption` de abajo (que se conserva, con el detalle completo de qué se citó y qué no).
- **Neurológico/Muscular/Autonómico** (riesgo por sistema): confirmado por el mapa (Tanda 2, 2026-08-14) que no citan ningún umbral — **fuera del alcance de esta tanda**, no se tocaron (no estaban en la lista de Parte A ni B del ticket). Candidato honesto para una tanda futura si se decide extender el mismo principio.

### Parte C — El cabo `trend`/`status` de la Fase 1

- `organ.metrics.trend` ("Tendencia", modo Clínico): traducido vía `TREND_LABELS` (`stable→Estable`, `rising→Subiendo`, `falling→Bajando`). **Hallazgo**: `trend` nunca se asigna en ningún sitio de `digital_twin_organism.py` (confirmado por grep) — se queda para siempre en su default de dataclass, `"stable"` — así que en la práctica esto solo se ve como "Estable" hoy; se tradujeron los 3 valores por completitud, no porque los otros 2 se hayan visto alguna vez.
- `organ.status.value.capitalize()` ("Estado", modo Investigador): mostraba el enum `OrganHealthStatus` en inglés ("Optimal"/"Normal"/"Alert"/"Critical") — traducido con el mismo `ORGAN_STATUS_LABELS` que ahora también alimenta las bandas de Parte A (una sola fuente para ambos usos).

### Bonus, hallazgo incidental (no un barrido exhaustivo nuevo)

Al tocar `render_risk_assessment` para el badge visible, se encontró que `name.capitalize()` mostraba **"Respiratory"** sin traducir — la única de las 5 claves de `system_risks` (`prediction_engine.py`) que no es cognado del español (las otras 4 -- cardiovascular/neurological/muscular/autonomic -- ya leían bien capitalizadas). Se añadió `_SYSTEM_NAME_LABELS` (solo la etiqueta; la clave `name`, usada para el lookup en `_RISK_SYSTEM_PROVENANCE`, no se tocó). No se hizo un barrido exhaustivo nuevo de idioma en esta tanda — esto se corrigió porque apareció en la misma línea que ya se estaba editando por Parte B.

### Clasificación verificada — ningún score cambió de categoría respecto al mapa

Se releyó cada fórmula antes de clasificar (no se confió ciegamente en el mapa): `global_health_score`/`system_coherence`/`resilience_index`/`neurocardiac_coupling`/`neuromuscular_coupling`/health score Cerebro-Músculos-Autonómico confirmados 100% heurísticos, cero cita, correctos en Parte A. Health score Corazón/Pulmones y acoplamiento Corazón↔Pulmones confirmados híbridos (referencia citada + pesos heurísticos), correctos en Parte B. No se encontró ningún caso mal clasificado por el mapa original.

### Verificación (por ejecución)

- Sanity import: limpio.
- AppTest de Twin OS con estado real (no forzado): banda de Estado Global presente, banda Alta/Media/Baja de Coherencia presente, badges "con ancla" (Corazón/Pulmones) y "heurística" (Cerebro/Músculos/Autonómico) presentes en las tarjetas de órgano.
- `at.metric` inspeccionado directamente (no solo grep de texto): `🔵 Cerebro ↔ Corazón` = `'Alto'`, `🟢🔵 Corazón ↔ Pulmones` = `'88%'`, `🔵 Cerebro ↔ Músculos` = `'Alto'` — confirma que los acoplamientos con/sin ancla se distinguen correctamente por valor, no solo por texto suelto en la página.
- Clic en Corazón → panel detallado: `🟢🔵 Salud general` = `'100/100'` (número). Clic en Cerebro → `🔵 Salud general` = `'Alerta'` (banda) en modo Estudiante; cambiado a Investigador → `🔵 Salud` = `'Alerta'` y `Estado` = `'Alerta'` (banda + status traducido, ambos vía `ORGAN_STATUS_LABELS`). Modo Clínico → `Tendencia` = `'Estable'` (traducido). Cero excepciones en cada paso.
- `render_risk_assessment`: `'Respiratorio'` presente, `'Respiratory'` (inglés) ausente, badge `🟢🔵` inline junto a Cardiovascular/Respiratorio confirmado presente.
- Barrido AppTest de los 10 módulos del hub: **10/10 sin excepción**.
- No-regresión de los 3 labs integrados al UPS — salidas idénticas a antes de esta fase: Respiratory `respiratory: 8 descriptores`, HRV `cardiovascular: 7 descriptores`, ECG `HR=76bpm, confianza=0.69` sobre MIT-BIH 100.
- Grep de las funciones de cálculo (`_compute_system_coherence`, `_compute_resilience`, `_compute_couplings`, `_update_heart/_brain/_lungs/_muscles`): cuerpo idéntico al de antes de esta fase — ningún archivo de motor (`digital_twin_organism.py`/`prediction_engine.py`) se tocó, todo el cambio es de `twin_shell/pages.py`.
- `pytest tests/ -q`: **429 passed** (ver resultado completo abajo).
- Servidor real (`streamlit run app/main.py`, puerto 8531): HTTP 200; proceso detenido tras la verificación.

## 2026-08-30 — BIOCORE, Fase 1 (idioma): interfaz estandarizada a español

**Contexto**: el diagnóstico de los 5 frentes (2026-08-29) confirmó una mezcla es/en concentrada en 5 archivos (~30-40 sitios): nombres de órgano, alertas/anomalías generadas por el motor, nombres de biomarcador, el toggle de modo de Twin OS, y dos motores de riesgo con vocabularios distintos en la misma página (`Riesgo: Low`). Barrido dirigido, no i18n bilingüe (eso es un arco aparte) — canónico: español.

**Principio rector aplicado en todo el barrido**: si un string se compara en código (`if x == "..."`, una clave de dict leída en otro archivo, una aserción de test), su VALOR no se traduce — solo su presentación (vía `format_func` o una etiqueta separada). Si un string solo se muestra, se traduce directo.

### Parte A — Strings de UI pura (traducidos directo)

- `page_title` (`app/main.py::st.set_page_config`): "BIOCORE AI — Integrated Platform" → "BIOCORE AI — Plataforma Integrada". El valor de `"About"` también se tradujo (bonus, mismo bloque, cero riesgo). Las claves `"Get Help"`/`"Report a bug"`/`"About"` **no se tocaron** — son nombres reservados de la API de `st.set_page_config`, no texto nuestro; renombrarlas rompe el menú.
- Nombres de órgano (`digital_twin_organism.py::_initialize_organs()`): `name="Heart"/"Brain"/"Lungs"/"Muscles"/"Autonomic Nervous System"` → `"Corazón"/"Cerebro"/"Pulmones"/"Músculos"/"Sistema Nervioso Autónomo"`. Confirmado por grep antes de tocar: `name` es solo texto de display (3 sitios en `twin_shell/pages.py`, todos `st.markdown`) — la clave real de lookup es `organ_id` (`"heart"`, minúsculas), intacta.
- Alertas/anomalías/recomendaciones (`digital_twin_organism.py::_detect_anomalies()`, 7 pares anomalía+alerta + 3 recomendaciones) — traducidas. Único cuidado real: estas frases se enrutan a un órgano por coincidencia de subcadena contra `ORGAN_KEYWORDS` (`twin_shell/pages.py`), incluso sobre palabras compuestas ("respiratory" dentro de "cardiorespiratory", "heart" dentro de "brain-heart"). Cada una de las 13 frases (7 anomalías/alertas base + 6 variantes con alerta) se verificó por ejecución real (`update_from_sensors` con valores patológicos disparando las 7 condiciones a la vez) para producir el MISMO conjunto de órganos que la versión en inglés — incluida una elección deliberada: "corazón-**aliento**" en vez de "corazón-**respiración**" para que "Heart-breath synchronization lost" siga sin enrutarse a Pulmones, igual que el original (que usaba "breath", no "breathing", y por eso tampoco calzaba).
- Nombres de biomarcador (`app/main.py`, `st.metric(label=...)`): "Stress Index"/"Cognitive Load Score"/"Physiological Resilience" → "Índice de Estrés"/"Carga Cognitiva"/"Resiliencia Fisiológica". **Solo la etiqueta `label=`** — ver Parte B, resultaron ser claves internas, no texto simple. "Muscle Fatigue Index" (el 4° nombre del diagnóstico) resultó ser código ya retirado (2026-07-03, Art. I) — solo sobrevive en un comentario histórico, nada que traducir.

### Parte B — Valores comparados en lógica (etiqueta traducida, clave intacta)

- `MODES = ["Student", "Clinician", "Researcher"]` (`twin_shell/pages.py`): valores SIN TOCAR (comparados en `if mode == "Student":` / `elif mode == "Clinician":`, y son el default de `session_state`). Se añadió `MODE_LABELS` + `format_func=lambda m: MODE_LABELS[m]` en el `st.radio` — la UI muestra "Estudiante/Clínico/Investigador", el valor interno sigue en inglés. **Verificado por ejecución**: clic en las 3 opciones (por su valor interno en inglés) — 0 excepciones, el contenido cambia según el modo correctamente.
- **Nombres de biomarcador — resultó ser el caso más delicado del barrido, más de lo que el diagnóstico anticipaba**: "Stress Index"/"Cognitive Load Score"/"Physiological Resilience Score" no son solo etiquetas — son **claves de diccionario** devueltas por `biomarkers.py::get_full_biomarker_suite()`, leídas de vuelta en `main.py` (`resultados['Stress Index']['score']`) y en `_BIOMARKER_HELP`, y además **aseveradas textualmente en `tests/test_biomarkers_plv.py`** (`assert suite['Stress Index'] == {...}`, 3 veces). Se aplicó el mismo principio que `MODES`: se tradujo solo lo que pasa a `st.metric(label=...)`, las claves de `resultados`/`_BIOMARKER_HELP` se dejaron intactas. `tests/test_biomarkers_plv.py`: **15/15 passed** sin ningún cambio.

### Parte C — Unificación de `risk_level` — el diagnóstico original estaba parcialmente equivocado, corregido aquí

El mapa atribuía el "Riesgo: Low" de las capturas a `PredictionEngine` únicamente, asumiendo que `DigitalTwinOrganism` ya hablaba español (citando `explain_state()`, que sí decía "CRÍTICO/ALTO/...") — **verificado por ejecución que esto era incorrecto**: `explain_state()` es un método huérfano (cero llamadas en toda la app, confirmado por grep) que nunca alimenta lo que se muestra en pantalla. El campo real que sí llega a `render_ambient_header()` ("Riesgo: {risk}") es `global_state["risk_level"]`, poblado por `_compute_risk_level()` — que **también** devolvía "Critical"/"High"/"Medium"/"Low" en inglés. Es decir: los DOS motores estaban en inglés, no uno de los dos — se corrigieron ambos:

- `PredictionEngine` (`app/engines/prediction_engine.py`): las 6 asignaciones de `risk_level` (`assess_cardiovascular_risk`/`assess_respiratory_risk`/`assess_neurological_risk`/`assess_muscular_risk`/`assess_autonomic_risk`/`assess_global_risk`) → `"CRÍTICO"/"ALTO"/"MODERADO"/"BAJO"`. Las 3 comparaciones internas que dependían del valor en inglés (`if risk.risk_level in ["Critical", "High"]` línea ~414; `if risk.risk_level == "Critical":`/`elif == "High":` líneas ~434-436, dentro de `assess_global_risk`) se actualizaron en el mismo cambio — confirmado por grep que no queda ninguna comparación contra el valor viejo. Ambos campos afectados (`critical_systems`, `immediate_actions`) resultaron ser **campos calculados pero nunca leídos por ninguna UI** (confirmado por grep) — se corrigieron de todos modos por coherencia interna del módulo, no porque se vieran rotos en pantalla.
- `DigitalTwinOrganism._compute_risk_level()` (`app/engines/digital_twin_organism.py`) — el que realmente alimenta `global_state["risk_level"]` — mismo cambio. Único consumidor en todo el repo: `render_ambient_header()`, sin ninguna comparación lógica contra este campo (confirmado por grep) — solo display, cero riesgo.
- `system_name` (campo de `RiskAssessment`, "Cardiovascular"/"Respiratory"/etc.) y `trend`/`status.value` (campos de `OrganSystem`, "stable"/"rising"/"falling") — encontrados en inglés durante el barrido, **no tocados**: confirmado por grep que ninguno se lee para display en ningún sitio vivo (`system_name` nunca se lee — la UI usa la clave del dict `system_risks`, no el campo; `trend`/`status` no estaban en el alcance de este ticket). Reportados para una tanda futura si se decide incluirlos.

### Verificación (por ejecución)

- Sanity import (`python -c "import app.main"`): limpio.
- **La parte de mayor riesgo real**: script dedicado que dispara las 7 condiciones de `_detect_anomalies()` a la vez con datos patológicos reales (vía `update_from_sensors()`, no strings a mano) y compara, para cada uno de los 5 órganos, el conjunto exacto de hallazgos que `_organ_related_findings()` produce — **idéntico al comportamiento en inglés en los 13 casos**, incluida la asimetría deliberada de "aliento" vs. "respiración".
- AppTest de Twin OS: nombres de órgano en español presentes, en inglés ausentes; radio "Nivel de detalle" con opciones mostradas `['Estudiante', 'Clínico', 'Investigador']`; clic en las 3 opciones por su valor interno en inglés → 0 excepciones cada vez; vocabulario `CRÍTICO`/`ALTO`/`MODERADO`/`BAJO` presente en "Evaluación de riesgo detallada por sistema".
- Script dedicado: `PredictionEngine.assess_global_risk()` y `DigitalTwinOrganism.global_state['risk_level']` sobre el mismo estado patológico → ambos devuelven exclusivamente valores de `{BAJO, MODERADO, ALTO, CRÍTICO}` — un solo vocabulario de riesgo, confirmado por ejecución, no por lectura.
- Barrido AppTest de los 10 módulos del hub: **10/10 sin excepción**.
- No-regresión de los 3 labs integrados al UPS (Fase 2.4) — salidas idénticas a antes de este barrido: Respiratory `respiratory: 8 descriptores`, HRV `cardiovascular: 7 descriptores`, ECG `HR=76bpm, confianza=0.69` sobre MIT-BIH 100.
- `tests/test_biomarkers_plv.py`: 15/15 passed (las claves de biomarcador, sin tocar, siguen calzando con las aserciones del test).
- `pytest tests/ -q`: **429 passed** (ver resultado completo abajo).
- Servidor real (`streamlit run app/main.py`, puerto 8523): HTTP 200; proceso detenido tras la verificación.

**Claves internas en inglés conservadas deliberadamente** (documentadas inline en el código): `MODES` (`"Student"/"Clinician"/"Researcher"`), las claves de biomarcador en `resultados`/`_BIOMARKER_HELP` (`"Stress Index"`, etc.), `organ_id` (`"heart"`, etc.). Ninguna se traduce sin antes actualizar sus sitios de comparación — no fue necesario en esta tanda porque el principio rector (etiqueta vs. clave) se aplicó desde el diseño de cada cambio, no como corrección posterior.

## 2026-08-29 — Capa 2, Fase 2.3 Tanda 3 (migración masiva por lotes) — CIERRE de la Fase 2.3 y de la Capa 2

**Contexto**: Tanda 1 construyó el sistema y lo probó en 2 pilotos; Tanda 2 validó `render_error_state`/`render_empty_state` en un caso real exigente. Esta tanda migra los ~10 módulos restantes en 3 lotes, cada uno verificado por ejecución antes de pasar al siguiente. Puramente presentacional: cero lógica, datos o escritura al UPS tocados en ningún lote.

### Lote 1 — ECG Lab, HRV Analysis, Respiratory Lab (los 3 laboratorios integrados al UPS, Fase 2.4)

- **ECG Lab** (`render_ecg_lab_page()`): título → `render_module_header("ECG Lab", icon="🫀")`.
- **ECG Monitor** (`render_ecg_monitor_page()`): su `<h2>🫀 ECG Lab</h2>` duplicado (vive dentro del hub ECG Lab, que ya tiene su propio `render_module_header`) → `render_section_header("Monitoreo")`. 4 sitios de error migrados (carga CSV, catálogo PTB-XL, conexión ESP32, creación de notebook) + el guard "ECGAnalyzer no disponible" + el fallo de `validate_signal`, cada uno con mensaje contextual específico.
- **HRV Analysis** (`render_hrv_page()`): título → `render_module_header("HRV Analysis", icon="📈")`; error de "RR series insuficiente" migrado.
- **Respiratory Lab** (`respiratory_lab/pages.py`): título → `render_module_header("Respiratory Lab", icon="💨")`; su `st.header()` interno de la pestaña Clínica → `render_section_header("Vista Clínica")`; 2 excepciones de `runpy`/nivel-módulo migradas.

**No-regresión de los 3 labs integrados al UPS (Fase 2.4), verificada por ejecución de punta a punta (Twin OS antes → lab guarda → Twin OS después)**: Respiratory da `respiratory: 8 descriptores` (idéntico); HRV da `cardiovascular: 7 descriptores` (idéntico); ECG da `HR=76bpm, confianza=0.69` sobre MIT-BIH 100 (idéntico) — la compuerta de honestidad (solo escribe HR con ritmo sinusal confirmado) intacta.

### Lote 2 — EMG Muscle Lab, Multisensor Fusion Lab, EEG Neuro Lab

- **EMG Muscle Lab**: título → `render_module_header("EMG Muscle Lab", icon="🦾")`; error de carga CSV migrado.
- **Multisensor Fusion Lab**: título → `render_module_header("Multisensor Fusion Lab", icon="🔗")`.
- **EEG Neuro Lab** (`eeg_neuro_lab/pages.py`, sin ningún título propio hasta ahora): gana `render_module_header("EEG Neuro Lab", icon="🧠")`; `st.header()` interno → `render_section_header("Vista Clínica")`; excepción de `runpy` + `st.exception` de `run()` migradas; estado vacío ("módulo no encontrado") → `render_empty_state`. `eeg_neuro_lab/page_content.py`: guard de import fallido migrado.
- **ECG-12** (`ecg_12/pages.py`, sub-vista dentro del hub ECG Lab — mismo criterio que "Monitoreo", **sin** `render_module_header` propio): sus 2 `st.header()` ("Vista Clínica"/"Vista Educativa") → `render_section_header`; excepción de `runpy` + `st.exception` de `run()` migradas; estado vacío migrado.
- **Bonus en `app/main.py`**: `render_findings_narrator()` (compartida por las pestañas "IA" de EMG/ECG Monitor/Multisensor/HRV) migrada — antes exponía `{exc}` crudo de la API de Anthropic; `render_biomarkers_page()` — guard de módulo no encontrado migrado.

### Lote 3 — Patient Pipeline, Education, Guides, Academia (módulos de soporte)

- **Education**: título → `render_module_header("Education", icon="🎓")`. Sin sitios de error propios (todo el contenido son `st.info` honestos de redirección, ya auditados en campañas previas — no forzados a estado vacío/error por simetría).
- **Guides**: título → `render_module_header("Guides", icon="📚")`. Página estática, sin estados de error/vacío que migrar.
- **Patient Pipeline** (`render_patient_pipeline_page()`): título ya migrado en Lote 2 (arrastre del mismo cambio); 2 estados vacíos genuinos migrados a `render_empty_state` — "sin ningún estado guardado todavía" en Vista Clínica y en Vista IA (mismo patrón que `render_ups_body()` usa para "sin snapshot", citado como precedente en `design_system.py`).
- **Academia** (`academia/pages.py`): título → `render_module_header("Academia BIOCORE AI", icon="🏫")`. 2 sitios de error genuinos migrados — el feedback de fallo del narrador IA en el quiz (`quiz_state["feedback_error"]`) y en el modo caso clínico (`academia_case_feedback_error`), mismo patrón que `render_findings_narrator()`. Los 2 sitios de "elegiste la opción incorrecta, la correcta era..." (quiz y caso clínico) **no se tocaron** — son feedback pedagógico de revelar la respuesta correcta, no un estado de crash/excepción (mismo criterio ya aplicado a los 5 sitios equivalentes de Respiratory Lab y al de ECG-12 en tandas anteriores).

### Cierre transversal — Digital Twin OS y unificación de badges

No estaban en ningún lote de los 3 (Digital Twin OS ya tenía título desde la Tanda 1) pero quedaban pendientes de la Fase 2.3 completa:

- **Digital Twin OS** (`twin_shell/pages.py`): 3 sitios de error genuinos migrados — narrador clínico (`render_clinical_narrator`) y razonamiento causal (`render_causal_reasoning`), ambos con el mismo mensaje contextual que `render_findings_narrator()` ("la llamada a la API de Anthropic falló -- red o cuota"), y la conexión ESP32 del panel de clasificador ECG, con el mismo mensaje que su equivalente ya migrado en ECG Monitor. Los 3 sitios restantes (línea 334, estilo de severidad clínica `st.error`/`st.info` según el texto; líneas 1233/1242, feedback de "elegiste el caso incorrecto") **no se tocaron** — mismo criterio de alcance que Academia.
- **Badges de procedencia**: las 4 constantes `BIOMARKER_*_BADGE` (`app/main.py`) y las 2 `PROVENANCE_*_BADGE` (`twin_shell/pages.py`) — mismos valores, cero fuente compartida desde que se creó `BADGES` en la Tanda 1 — ahora son alias directos de `design_system.BADGES` (`BIOMARKER_CLINICAL_BADGE = BADGES.CLINICAL`, etc.). Ningún sitio de uso (25+ f-strings en `main.py`, 15+ en `twin_shell/pages.py`) cambió — los badges se ven exactamente igual, solo dejan de tener 2 fuentes que podían divergir.

### Hallazgo, no actuado (fuera del alcance de los "~10 módulos")

El grep final encontró `st.error` crudo en 4 archivos fuera del árbol vivo de `app/main.py` + `supermodules/`: `app/ecg_trainer.py` (script Streamlit independiente, lanzado con `streamlit run app/ecg_trainer.py`, sin ninguna referencia desde `app/main.py` — no es uno de los 10 módulos del hub), `app/streamlit_app.py` (el wrapper de arranque — su `st.error`+`st.text(traceback.format_exc())` es deliberado: si `app/main.py` falla al cargar, es el único lugar donde la traza completa puede mostrarse, no hay otro log garantizado en ese punto), y `app/utils.py` + `app/utils/ui_helpers.py` (cero referencias encontradas en todo el árbol vivo — código huérfano, no confirmado como usado por nada). Ninguno se tocó — no son parte del alcance de esta tanda ni de los módulos que el usuario navega desde el hub.

### Verificación (por lote, y transversal al cierre)

- Los 3 lotes verificados individualmente por ejecución antes de continuar al siguiente — ninguno rompió nada, ningún STOP necesario.
- `python -c "import app.main"`: limpio, sin excepciones, en cada lote.
- Barrido AppTest de los 10 módulos del hub + Academia/Guides/Patient Pipeline/Education (14 objetivos en total contando duplicados de nombre): **todos sin excepción**, repetido tras el cierre transversal (Twin OS + badges).
- Re-verificación dirigida de los 3 labs integrados al UPS: salidas idénticas a las de antes de la Fase 2.3 (ver Lote 1 arriba).
- Narrador de Twin OS bajo fallo forzado de la API (monkeypatch de `stream_narration`, sin depender de tener `ANTHROPIC_API_KEY` configurada): botón encontrado, click sin excepción, caja `render_error_state` presente en el HTML, **cero traza cruda filtrada al usuario**, traza completa confirmada en el log.
- Grep final: **cero definiciones de badge duplicadas** (`grep "_BADGE = \""` solo encuentra los alias a `BADGES`); dentro del árbol vivo, **cero `st.error()` crudos que no sean feedback pedagógico o estilo de severidad clínica** (ambas categorías explícitamente fuera de alcance, documentadas arriba y en tandas anteriores).
- `pytest tests/ -q`: **429 passed, 1 warning** (sklearn/LGBMClassifier, preexistente) — verificado tras Lote 2 y de nuevo tras Lote 3 + cierre transversal.
- Servidor real (`streamlit run app/main.py`, puerto 8517): HTTP 200; proceso detenido tras la verificación.

**Fase 2.3 (Identidad Visual) queda completa.** Con ella, **Capa 2 queda completa**: los 10 módulos del hub comparten título, badges de procedencia y estados de error/vacío desde una única fuente (`app/utils/design_system.py`), sin haber tocado lógica, datos ni la escritura al UPS en ningún punto de las 3 tandas.

## 2026-08-29 — Capa 2, Fase 2.3 Tanda 2: `render_error_state`/`render_empty_state` probados en casos reales — ECG Lab (carga MIT-BIH/PTB-XL)

**Contexto**: la Tanda 1 construyó el sistema y lo probó con `render_module_header` en 2 pilotos, pero el título es la mejora menos visible. Esta tanda prueba las dos funciones que el recon señaló como las que más elevan (o delatan) la percepción de "producto" — un error crudo de Python en pantalla, o la ausencia de un estado vacío diseñado — en su punto más exigente: los puntos de carga de señal de ECG Lab (MIT-BIH/PTB-XL, dependientes de una descarga en vivo desde PhysioNet — el tipo de operación que sí puede fallar de verdad en una demo).

### Parte A — `render_error_state` en 2 sitios reales

`app/main.py::render_ecg_monitor_page()` — los `except Exception as e: display_error_message(e, ...)` de la carga de MIT-BIH y de PTB-XL (2 de los 24 sitios que el recon encontró) reemplazados por `render_error_state(mensaje_usuario, exception=e)`.

**Comportamiento dual, verificado por ejecución** (forzando un `ConnectionError` real vía monkeypatch de `safe_import_ecg_modules()`, simulando un timeout de PhysioNet):
- **Lo que ve el usuario**: caja con borde izquierdo `CRITICAL` (`#ff4d4d`), ícono, "No se pudo cargar el registro MIT-BIH -- verifica la conexión a PhysioNet o prueba otro registro." — **cero mención de `ConnectionError`, cero traceback, cero cajas `st.error()` nativas** (confirmado: 0 elementos `st.error` en el render).
- **Lo que queda en el log**: traceback completo (`logging.error(..., exc_info=exception)`) — archivo, línea exacta (`main.py:1299`), clase de excepción (`ConnectionError`) y mensaje original íntegro. El desarrollador pierde cero información; el usuario en la demo ve cero ruido técnico.

### Parte B — `render_empty_state` en un caso real

Mismo módulo: "Selecciona un registro y pulsa Cargar..." (un `st.sidebar.info` genérico) reemplazado por `render_empty_state("Aún no hay ningún registro MIT-BIH cargado", action='selecciona uno arriba y pulsa "Cargar registro MIT-BIH"...')`. Verificado que aparece correctamente antes de cargar nada, y que **desaparece sin romper el flujo** cuando sí hay datos: recarga completa de MIT-BIH 100 (real, en vivo) confirma que el signal se muestra normal y el botón "Guardar estado al gemelo" (Fase 2.4) sigue funcionando exactamente igual que antes de esta tanda (`HR=76bpm, confianza=0.69`, idéntico).

### Parte C — Lectura honesta

El estado de error diseñado sí se ve como producto frente a la caja roja cruda -- la diferencia no es sutil: antes, un fallo de red mostraba literalmente `ConnectionError: ...` con la ruta del archivo Python en pantalla; ahora es una frase clara con una acción sugerida. El estado vacío ayuda menos dramáticamente pero cierra un hueco real (antes esa pantalla podía quedar en blanco o con un info gris sin acción). No se ajustó nada en las funciones -- el molde de la Tanda 1 aguantó su primer caso real sin cambios.

### Verificación

- AppTest con error forzado (monkeypatch): 0 excepciones, caja limpia confirmada, 0 `st.error()` nativos, traza confirmada en el log capturado.
- AppTest con datos reales (MIT-BIH 100 vía PhysioNet en vivo): estado vacío da paso a la señal normal, guardado al gemelo idéntico a antes.
- Barrido de los 10 módulos: **10/10 sin excepción** — ningún otro módulo tocado.
- `pytest tests/ -q`: **429 passed, 1 warning** (sklearn/LGBMClassifier, preexistente).
- Servidor real (`streamlit run app/main.py`, puerto 8564): HTTP 200; proceso detenido tras la verificación.

El molde de mayor impacto quedó validado en su punto más exigente (una operación que de verdad puede fallar en vivo). Migrar los ~22 sitios `st.error` restantes y aplicar `render_empty_state`/`render_module_header` al resto de módulos es tanda posterior, replicando un patrón ya probado, no uno todavía en duda.

## 2026-08-29 — Capa 2, Fase 2.3 Tanda 1: sistema de diseño — tema base + módulo de helpers compartido, probado en 2 pilotos (Digital Twin OS + Biomarkers Lab)

**Contexto**: el recon de la Fase 2.3 (turno anterior, solo diagnóstico) encontró 52 hex distintos sin fuente única, 4 mecanismos distintos para el título de módulo (Digital Twin OS sin ninguno), los badges de procedencia de la Capa 3 duplicados como código (`BIOMARKER_*_BADGE` en `main.py` / `PROVENANCE_*_BADGE` en `twin_shell/pages.py`, mismos valores, cero fuente compartida), y 24 sitios donde `st.error(f"...{e}")` expone la traza cruda de Python al usuario. Esta tanda construye la base — tema + helpers — y la prueba en 2 módulos piloto. Los ~10 módulos restantes NO se tocan; migran en tandas posteriores. Puramente presentacional: cero lógica, datos o escritura al UPS tocados.

### Parte A — Tema base (`.streamlit/config.toml`)

`[theme]` extendido con los 4 tokens que Streamlit expone (antes solo `base="dark"`): `primaryColor="#1d4ed8"`, `backgroundColor="#0f172a"`, `secondaryBackgroundColor="#1a2a4a"`, `textColor="#e0e7ff"`. Los 4 elegidos por auditoría, no por gusto: son, del desorden de 52 hex que el recon encontró, los valores YA más repetidos con intención de marca/fondo — ningún color nuevo añadido al conteo.

**Contraste WCAG, verificado por cálculo** (luminancia relativa estándar, no a ojo):
- `textColor` sobre `backgroundColor`: **14.49:1** (AAA)
- `textColor` sobre `secondaryBackgroundColor`: **11.56:1** (AAA)
- `primaryColor` + texto blanco (uso real: fondo de botón/slider): **6.70:1** (AA)
- **Hallazgo**: `primaryColor` como color de TEXTO directo sobre `backgroundColor` da **2.66:1** — reprueba incluso AA (mínimo 4.5:1). Por eso `design_system.py` declara un `ACCENT_ON_DARK` (`#8ecae6`, **9.98:1**, AAA) separado para encabezados/íconos — `primaryColor` queda reservado para los controles nativos de Streamlit, donde el contraste relevante es con el texto que Streamlit dibuja encima, no con el fondo de la página. Importa para proyector: colores de bajo contraste son los primeros en lavarse.

### Parte B — `app/utils/design_system.py` (nuevo)

- `PALETTE`: los 4 tokens del tema (citados por nombre, no reescritos) + `ACCENT_ON_DARK` + la semántica de estado `STABLE`(`#39d98a`)/`WARNING`(`#ffc542`)/`CRITICAL`(`#ff4d4d`)/`NEUTRAL`(`#64748b`) — **promovida de `ups_body_visual.py`**, que ya la usaba internamente para el gemelo (corazón/pulmones) sin haberla declarado como estándar. Contraste documentado por cada uno (CRITICAL y NEUTRAL marcados explícitamente como "no para texto de lectura, sí para badges/elementos grandes").
- `BADGES`: fuente única de los 4 badges de procedencia (🟢/🔵/🔴/🟣) con su texto — reemplaza las dos definiciones gemelas. **Solo se crea la fuente en esta tanda**; migrar `main.py`/`twin_shell/pages.py` para que importen de aquí es tanda posterior (no se tocan los 2 archivos completos de golpe).
- `render_module_header(title, icon, subtitle=None)`: el título de módulo, un solo estilo — reemplaza los 4 mecanismos.
- `render_section_header(title)`: `<h2>` sin acento, para que la jerarquía con el título de módulo sea visible.
- `render_empty_state(message, action=None)`: extiende el patrón que `render_ups_body()` ya usaba para "sin snapshot".
- `render_error_state(message, exception=None)`: caja limpia con acento CRITICAL; si recibe `exception`, la traza completa va a `logging` (nivel ERROR, `exc_info`) — nunca a la pantalla. Reemplaza el patrón de los 24 `st.error(f"...{e}")` — **migrarlos es tanda posterior**, aquí solo se crea y verifica la función.

### Parte C — 2 pilotos, verificados por ejecución

- **Digital Twin OS** (`twin_shell/pages.py::main()`): gana `render_module_header("Digital Twin OS", icon="🧬", subtitle=...)` — **primer título de módulo que ha tenido nunca**, confirmado por AppTest (`<h1 style='color:#8ecae6'>🧬 Digital Twin OS</h1>` presente, sin excepción).
- **Biomarkers Lab** (`render_biomarkers_page()`): su `<h1 style='color:#1f77b4'>` a mano reemplazado por `render_module_header()` — confirmado por AppTest que ya no usa `#1f77b4` y sí usa el acento compartido `#8ecae6`, sin excepción.
- **No-regresión confirmada explícitamente**: EMG Muscle Lab y HRV Analysis (no piloteados) siguen mostrando exactamente sus patrones viejos (`#1f77b4` a mano y `<h2>` plano respectivamente) — no se tocaron. Barrido completo de los 10 módulos vivos: **10/10 sin excepción**.

### Verificación

- `pytest tests/ -q`: **429 passed, 1 warning** (sklearn/LGBMClassifier, preexistente) — cero lógica tocada, como se esperaba de una tanda presentacional.
- Servidor real (`streamlit run app/main.py`, puerto 8563): HTTP 200; proceso detenido tras la verificación.

Base y 2 pilotos verificados. Migración del resto (~10 módulos: headers, badges unificados, los 24 `st.error` crudos) queda para tandas posteriores, cada una verificada por ejecución antes de tocar el siguiente lote.

## 2026-08-24 — Capa 2 / Capa 5B, tanda de cableado: compuerta recalibrada a Vpp (Modelo 1 del experto) + ECG conectado al UPS — INTEGRACIÓN ESTRECHA COMPLETA (3/3) — Art. I

**Contexto**: el experto ratificó el detector TKEO tras 6 rondas de validación y firmó la autorización de cableado, condicionada a recalibrar la compuerta de calidad — que medía consistencia de amplitud en el índice exacto del pico, inestable con el fiducial de TKEO (ancla en máxima pendiente, no en cima de voltaje; en un QRS mellado en "M" de BRD ese punto salta entre muescas). Instrucción: reemplazar por Vpp (pico-a-pico) en ventana.

### Parte A — Compuerta recalibrada a Vpp

`VPP_WINDOW_MS=50.0`/`VPP_CV_THRESHOLD=0.15` (nuevas, provisionales, citadas al experto como origen — `clinical/ecg_analyzer.py`). `estimate_heart_rate_with_confidence()`: la métrica de calidad reemplaza `amplitude_score` (antes `CV` de `x[peak_i]`, amplitud puntual) por `CV` de `Vpp[i] = max(ventana ±50ms) − min(ventana ±50ms)` — captura el QRS completo (incluidas las muescas del BRD) sin depender de dónde cayó el fiducial exacto. `VPP_CV_THRESHOLD` queda embebido en la escala de `amplitude_score` (`clip(1 - CV_amp/VPP_CV_THRESHOLD, 0, 1)`), de forma que `CV_amp >= VPP_CV_THRESHOLD` fuerza el rechazo vía `quality_threshold` sin necesitar un segundo chequeo redundante. **Cambio de detector interno**: el método pasa de `detect_r_peaks_bidirectional()` a `detect_r_peaks_tkeo()` — por eso se retiró `prominence_factor` de la firma (parámetro del detector viejo, sin sentido para TKEO; retirado en vez de dejarlo como argumento muerto). Filtros pRR31 (FA)/metrónomo (marcapasos)/banda sinusal sin cambios — el experto confirmó que son robustos entre detectores.

### Parte B — Re-validación de los 25, con punto de parada: sin desvíos

Corrida completa sobre los 25 registros de la cohorte de la ronda 6 antes de tocar cualquier UI. **Los 6 casos con expectativa clínica clara coinciden todos**: 100✓/103✓ aceptan (sinusales limpios); 118✓ **pasa de rechazo incorrecto (ronda 6) a aceptación correcta** — la prueba central de que la recalibración funcionó; 210✓ declina (FA, vía pRRx); 217✓ declina (marcapasos, vía calidad); **104✓ declina** (marcapasos ultra-estimulado, 62.7% latidos paced, sens=0.665) — confirmado explícitamente que declina por pRRx (dinámica R-R real), no que se cuela con un HR basado en el 66% de latidos detectados — no es un "217 redivivo". Solo **2 de 25 registros cambian de veredicto** respecto a la ronda 6 (118 y 122, ambos correcciones DECLINA→ACEPTA sobre registros limpios, ninguna regresión). Sin puntos de parada — se procedió a la Parte C.

### Parte C — Cableado: ECG cierra 3/3

`app/main.py::_render_ecg_save_to_twin()` (nuevo) + llamada desde la Vista Clínica de `render_ecg_monitor_page()` — molde idéntico a Respiratory/HRV (`twin_shell_ups_patient_id`, `save_state`). La compuerta gobierna la escritura: TKEO + Vpp + filtros R-R corren al pulsar guardar; solo si el ritmo se confirma sinusal-evaluable-de-calidad escribe `heart_rate`. Fuente demo (`generate_demo_ecg_signal()`, que ignora `hr`) **excluida de raíz** — el botón ni siquiera se muestra para esa fuente, con explicación honesta en su lugar. Procedencia: `Provenance.SENSOR_REAL` solo si `metadata['source']` confirma hardware ESP32 verificado en vivo (mismo criterio que `twin_shell.pages`); `Provenance.SIMULACION` con `source_detail` descriptivo para MIT-BIH/PTB-XL/CSV/casos clínicos — decisión documentada: el schema no tiene una categoría para "dato real reproducido de un dataset público, no medido en vivo aquí", y `SENSOR_REAL` se reserva por precedente establecido para hardware verificado en el momento.

### Verificación por ejecución

- **Reacción desde sinusal** (MIT-BIH 100 vía AppTest): antes — corazón gris, "sin dato"; guardar → `"Estado guardado... HR=76bpm, confianza=0.69"`, caption confirma `cardiovascular: 6 descriptores · respiratory: 0 descriptores`; después — corazón verde, animación activa, "FC: 76 bpm".
- **Declinación honesta en vivo** (MIT-BIH 217 vía AppTest): guardar → `"⛔ Escritura declinada por seguridad clínica: Ritmo irregular no sinusal... pRR31=52%... Escritura declinada."` — sin excepción, sin snapshot creado, el gemelo no recibe HR no-autonómico.
- **Raíz espejo**: `respiratory: 0 descriptores` en el estado que ECG escribe — tercer escritor que la valida (junto a Respiratory→`cardiovascular: 0` y HRV→`respiratory: 0`).
- **No-regresión**: Respiratory y HRV re-verificados por AppTest, idénticos (mismos snapshots/conteos). Patient Pipeline idéntico (13 filas). Barrido de los 10 módulos: **10/10 sin excepción**.
- `pytest tests/ -k "ecg_analyzer or bbb or qrs_delineation or clinical_pattern" -q`: **45 passed** — `detect_r_peaks()` (BBB) y `detect_r_peaks_bidirectional()` intactos, ya no usados por la compuerta pero disponibles.
- `pytest tests/ -q`: **429 passed, 1 warning** (sklearn/LGBMClassifier, preexistente) — sin regresión.
- Servidor real (`streamlit run app/main.py`, puerto 8562): HTTP 200; proceso detenido tras la verificación.

### Artefacto

`docs/validation/ecg_hr_detector_bank/round7_cableado/`: re-validación completa de los 25 registros con la compuerta Vpp, comparada contra la ronda 6.

**INTEGRACIÓN ESTRECHA COMPLETA (3/3)**: Respiratory, HRV y ECG alimentan el gemelo de Digital Twin OS, honestos por arquitectura — las dos raíces del builder (cardiovascular/respiratoria) gateadas contra dominios fantasma, cada lab con su propia compuerta de rechazo (Respiratory: solo respiratorio; HRV: solo cardíaco, sin pulmón fantasma; ECG: TKEO + whitelist de 6 rondas de validación). Marcapasos y FA declinados explícitamente por no ser autonómicamente válidos — el gemelo solo recibe biometría que su propia dinámica R-R confirma como sinusal.

## 2026-08-24 — Capa 2 / Capa 5B, Ronda de Robustez: detector TKEO (fiducial estructural) + Z-score/curtosis + cohorte MIT-BIH ampliada (25 registros) — hallazgo crítico detiene el cableado — Art. I — UPS aún sin cablear

**Contexto**: el experto firmó la ronda 5 como checkpoint seguro pero condicionó el cableado a esta Ronda de Robustez, señalando tres puntos frágiles: sobreajuste a 11 registros, sensibilidad de derivación (V5 fallaba), y que el error grueso del fiducial (cientos de ms) no era jitter sino un fallo estructural — el detector marcaba ondas T/artefactos como picos R.

### Parte A — Detector TKEO: diagnóstico confirmado PARCIALMENTE

`ECGAnalyzer.detect_r_peaks_tkeo()` (nuevo, `clinical/ecg_analyzer.py`) — pasa-banda Butterworth 5-15Hz (`filtfilt`, orden 3) aísla la banda del QRS; operador de Teager-Kaiser (`Ψ[n]=x²[n]-x[n+1]·x[n-1]`, clip≥0) "estalla" el QRS independientemente de polaridad; `find_peaks` sobre la energía localiza la zona del latido; mapeo inverso marca el punto de máxima `|dv/dt|` en ±50ms sobre la señal original. Cada paso verificado, no asumido correcto por venir del experto. Método nuevo y aparte -- `detect_r_peaks()` (BBB) y `detect_r_peaks_bidirectional()` (ronda anterior) intactos.

**Prueba del fiducial (registro 217, marcapasos)**: SDNN bidireccional 175.24ms → TKEO 85.49ms (**-51%, mejora real, NO colapso a ≈0**). Sensibilidad/VPP: 0.995/0.597 → 0.986/1.000. El diagnóstico del experto se confirma solo parcialmente: el fiducial mejoró sustancialmente (VPP perfecto) pero no llegó al ritmo mecánico puro esperado — los RR residuales muestran dispersión suave (~780-910ms), no outliers erráticos, dejando abierta la pregunta de si es precisión residual del detector o variabilidad genuina de un marcapasos rate-responsive. Reportado sin forzar el "colapso completo".

### Parte B — Z-score/curtosis: V5 resuelto, pero por TKEO solo

`normalize_zscore()`, `signal_quality_kurtosis()`, `select_best_lead_by_kurtosis()` (nuevos, aditivos). **Prueba de derivación (100-V5)**: bidireccional sens=1.000/VPP=0.751/SDNN=223.6ms → TKEO sens=1.000/VPP=1.000/SDNN=30.3ms — **resuelto por completo, idéntico a su MLII**. Dato para la firma: TKEO solo ya lo resolvió (3/223 picos difieren en 1 muestra entre TKEO directo y TKEO sobre señal Z-scoreada — ruido de precisión numérica) porque el umbral de TKEO (media+z·std de la energía) ya es auto-invariante a escala; Z-score explícito habría sido redundante para este detector específico. El SQI por curtosis sí funciona como mecanismo independiente y verificado: curtosis MLII=26.70 > V5=17.78, elige MLII correctamente sin ver un solo latido.

### Parte C — Cohorte ampliada: 25 registros, 0 fallos de descarga

10 registros de rondas previas + 15 nuevos (101,105,109,111,112,115,122,123,102,104,200,201,203,208,221), cubriendo normales, BRD, más marcapasos, PVC/AFib. Sobre los 15 nuevos: sensibilidad/VPP mediana ≥0.98 — el detector generaliza, no parece sobreajustado a los 11 casos previos. 4 excepciones honestas por debajo de 0.85 (sens/VPP), todas en carga alta de PVC/marcapasos: 104 (62.7% paced) sens=0.665/VPP=0.737 — el peor del banco, TKEO no generaliza tan bien a un segundo registro con marcapasos con carga aún mayor que 217; 208 (33.8% PVC) sens=0.749; 207 (ya conocido) sens=0.775; 203 (13.7% PVC) sens=0.844.

**Hallazgo crítico -- detiene la recomendación de cablear**: al re-aplicar la MISMA lógica de la compuerta whitelist (pRR31/metrónomo/banda/calidad) sobre picos TKEO en vez de bidireccionales, **6 de 25 registros cambian de veredicto**. Los filtros de dinámica R-R (pRR31/metrónomo/banda) son estables entre detectores — 108/228/207/233/210/200/201/203/208/221/104 declinan por pRRx en ambos casos, sin cambiar. Pero la compuerta de CALIDAD genérica (heredada, sin cambios desde la ronda 2 — `regularity_score`/`amplitude_score`) **regresiona el registro 118 (BRD) de aceptación correcta a rechazo incorrecto**, y declina otros 3 registros limpios (105, 109, 122) que antes aceptaba. Causa probable: TKEO elige su fiducial por máxima pendiente dentro de una ventana ±50ms, no el máximo global — introduce más variación en la amplitud EXACTA del punto marcado que el detector bidireccional, penalizada por una fórmula de confianza que nunca se calibró contra las características de TKEO. **No se recalibró la fórmula en esta ronda** — se reporta como el bloqueo concreto pendiente, no se fuerza un ajuste para esconderlo. `estimate_heart_rate_with_confidence()` (la compuerta de producción) sigue usando `detect_r_peaks_bidirectional()` internamente — el cableo a TKEO es una decisión de integración explícitamente NO tomada aquí.

### Parte D — Artefacto de firma final

`docs/validation/ecg_hr_detector_bank/round6_robustez/hoja_firma_final_ronda6.pdf`: las 2 pruebas de reparación (fiducial, derivación), tabla de la cohorte de 25 con generalización y excepciones, **el hallazgo crítico del hallazgo de la compuerta con la tabla completa de 25 registros bidireccional-vs-TKEO**, tiras de 217/100-V5/210, y la hoja de firma con la recomendación explícita de Claude Code (no vinculante): no cablear la compuerta apuntada a TKEO tal cual hasta recalibrar la fórmula de calidad.

### Verificación

- `pytest tests/ -k "ecg_analyzer or bbb or qrs_delineation or clinical_pattern" -q`: **45 passed** — `detect_r_peaks()` original y `detect_r_peaks_bidirectional()` intactos.
- `pytest tests/ -q`: **429 passed, 1 warning** (sklearn/LGBMClassifier, preexistente) — sin regresión.
- Servidor real (`streamlit run app/main.py`, puerto 8561): HTTP 200; proceso detenido tras la verificación.
- 25/25 registros de la cohorte descargados y procesados en vivo desde PhysioNet, 0 fallos.

**Integración estrecha: sigue en 2/3** (Respiratory, HRV). El detector TKEO está listo y bien evidenciado; la compuerta whitelist necesita una recalibración de su fórmula de calidad antes de poder apuntarse a él con seguridad — el cableado de ECG al UPS sigue pendiente de esa recalibración y de la firma final del experto.

## 2026-08-24 — Capa 2 / Capa 5B, ronda 5: precisión temporal (Task Force 1996) + filtros R-R con métricas de literatura (pRR31) — frontera acertada en los 5 casos primarios, hipótesis del jitter falseada — Art. I — UPS aún sin cablear

**Contexto**: la ronda anterior detuvo el cableado — la compuerta whitelist (250ms/15% + SDNN<3ms) no separaba el banco en ningún `prominence_factor`. Causa hipotetizada: jitter de cuantización del fiducial a fs<500Hz. Esta ronda prueba esa hipótesis con interpolación parabólica y reemplaza el filtro de caos por una métrica validada por literatura.

### Parte A — Interpolación parabólica: hipótesis PROBADA Y FALSEADA

`ECGAnalyzer.refine_peaks_parabolic()` (nuevo, `clinical/ecg_analyzer.py`) — vértice de la parábola sobre `(n-1, n, n+1)`, citando Task Force ESC/NASPE 1996 (Circulation 1996;93:1043). Verificado que produce correcciones sub-muestra genuinas (no un no-op silencioso: desplazamientos hasta ±0.5 muestras, std≈0.27 muestras). **Pero el SDNN del registro 217 NO colapsó**: 109.26→109.13ms (pf=1.0), 175.24→175.18ms (pf=1.5), 155.13→155.14ms (pf=2.0) — diferencia <0.1ms en los tres casos, y también en los sinusales (100/103), que tampoco se distorsionan. **La hipótesis del jitter de cuantización queda falseada por medición directa**: el desajuste real (decenas a cientos de ms) es dos órdenes de magnitud mayor que lo que una corrección de ≤0.5 muestras (≤1.4ms a fs=360Hz) puede explicar — consistente con que el detector elige, latido a latido, puntos distintos del QRS ancho de un ritmo estimulado, no con redondeo de una posición ya consistente. Reportado sin suavizar, tal como se pidió.

### Parte B — pRR31 reemplaza el Filtro del Caos: sí funcionó

`PRR_THRESHOLD_MS=31` (citado — Buś et al., AUC 0.958 discriminando FA) reemplaza `CHAOS_JUMP_MS/CHAOS_FRACTION` (250ms/15%, retirados, no quedan como reliquia muerta en el código). `PRR_FRACTION_LIMIT=0.50` — **provisional, NO de la cita** (el paper valida pRR31 como feature discriminante, no publica un corte operativo único) — calibrado por inspección directa del banco: sinusales 16-30%, no-sinusales 73-94%, declarado explícitamente como tal. Filtro del Metrónomo y banda sinusal se mantienen, ahora sobre marcas refinadas (Parte A) aunque esa refinación resultó casi nula en la práctica.

### Parte C — Re-validación: frontera acertada en los 5 casos primarios

A `prominence_factor=1.5`: **100✓/103✓/118✓ ACEPTAN, 210✓/217✓ DECLINAN** — los 5 casos que la tarea exigió, todos correctos simultáneamente por primera vez en esta serie de rondas. 233 (ruido) también declina, aunque por pRRx (78%) en vez de por la compuerta de calidad genérica que se anticipaba — mecanismo distinto, mismo veredicto correcto, reportado sin ocultar la diferencia.

**Discrepancia residual, reportada sin forzar el umbral** (tal como se pidió): el registro 100 en su segunda derivación (V5, mismo paciente/sesión que la MLII que sí acierta) se declina por pRRx (73.2%, SDNN=223ms) cuando "debería" aceptar igual que su lead MLII (pRR31=29%, SDNN=30ms) — el detector se comporta sustancialmente peor en esa derivación específica. No se ajustó `PRR_FRACTION_LIMIT` para capturar este caso — es dato para el experto, no algo que se fuerza.

### Parte D — Artefacto de firma

`docs/validation/ecg_hr_detector_bank/round5_precision/hoja_firma_experto_ronda5.pdf`: portada con la hipótesis falseada, tabla SDNN entero-vs-refinado (los 7 registros, Δ≈0 en todos), tabla de frontera con pRR31/veredicto coloreada verde/rojo, tiras de los 7 registros con picos + marcas refinadas superpuestas, y la hoja de firma de los 3 umbrales provisionales (valor de literatura/origen, valor medido, casilla confirmar/ajustar) + la pregunta final de autorización de cableado.

### Verificación

- `pytest tests/ -k "ecg_analyzer or bbb or qrs_delineation or clinical_pattern" -q`: **45 passed** — `detect_r_peaks()` original intacto.
- `pytest tests/ -q`: **429 passed, 1 warning** (sklearn/LGBMClassifier, preexistente) — sin regresión.
- Servidor real (`streamlit run app/main.py`, puerto 8560): HTTP 200; proceso detenido tras la verificación.
- UPS sin cablear — la Parte C del encargo (cablear la escritura) no se pidió ejecutar esta vez; el resultado queda listo para la firma del experto sobre `prominence_factor=1.5` y los 3 umbrales provisionales.

**Integración estrecha: sigue en 2/3** (Respiratory, HRV). ECG tiene ahora, por primera vez, una compuerta que acierta la frontera clínica completa en el banco de validación — pendiente de la firma del experto para cablear.

## 2026-08-24 — Capa 2 / Capa 5B, mini-arco (tanda final): compuerta whitelist R-R implementada, re-validación detiene el cableado — Art. I — integración estrecha queda en 2/3, ECG sin cerrar

**Contexto**: el experto trazó la frontera clínica final tras el hallazgo de la 3ª ronda (las espigas de marcapasos sufren aliasing a 360-500Hz, indistinguibles de un QRS aberrante — por eso `detect_pacemaker_spikes()` fallaba). Nueva estrategia: barrera por dinámica R-R, no morfología. FA = caos (SDNN/saltos altos); marcapasos = metrónomo (SDNN≈0). Whitelist fail-safe: culpable de inválido hasta demostrar sinusal.

### Parte A — La compuerta whitelist, implementada tal como se especificó

`ECGAnalyzer.estimate_heart_rate_with_confidence()` extendida (`clinical/ecg_analyzer.py`) con, en orden: (0) bloqueo de metadatos — parámetro `patient_metadata` nuevo, gancho documentado: `domain/physiology/state/models.py::PatientRecord` **no tiene campo `pacemaker`/clínico hoy** (solo `id`/`external_id`/`display_name`/`created_at`) — añadirlo es una migración de schema aparte, no ejecutada; (1) Filtro del Caos — `CHAOS_JUMP_MS=250`/`CHAOS_FRACTION=0.15`; (2) Filtro del Metrónomo — `METRONOME_SDNN_MS=3`, mensaje deliberadamente sin diagnosticar causa ("ausencia de variabilidad autonómica detectable... no se afirma la causa"); (3) banda fisiológica sinusal — `SINUS_SDNN_MIN_MS=3`/`SINUS_SDNN_MAX_MS=200` (provisional); (4) calidad de señal genérica (heredada, sin tocar). Los 3 primeros filtros son de rechazo, la aceptación exige además pasar (3) y (4) explícitamente — no solo esquivar (1) y (2).

### Parte B — Re-validación contra el banco: DETIENE el cableado

Antes de tocar la UI, corrí la compuerta completa sobre los 11 registros del banco en 3 valores de `prominence_factor` (1.0/1.5/2.0), exactamente como se pidió ("si algún registro cae del lado equivocado, detente y repórtalo"). **Resultado: ningún `prominence_factor` logra la frontera correcta (118 aceptado; 210 y 217 declinados) simultáneamente**:

- `pf=1.0`: 100 (sinusal limpio) rechazado por el Filtro del Caos — falso positivo por ruido residual del detector, no por irregularidad real.
- `pf=1.5`: 100/103/118 correctos, pero **210 (FA real) se ACEPTA** — el fallo más grave, dado que excluir no-autonómicos es el propósito central de la compuerta.
- `pf=2.0`: 100/103 correctos, 118 (BRD) rechazado por la compuerta de calidad genérica (no por los filtros nuevos), **210 se acepta, y 217 (marcapasos) también se ACEPTA**.

**Causa raíz, diagnosticada con evidencia directa** (SDNN y fracción-de-caos medidos sobre la salida real del detector, no sobre ground truth): el Filtro del Caos nunca supera el 15% en el registro 210 real (12.3-14.0% en los 3 `pf`, pese a SDNN 2-4× el de un sinusal limpio — su irregularidad no se concentra en saltos grandes individuales de la forma que el criterio asume); la premisa del Filtro del Metrónomo (SDNN≈0 en marcapasos) no se sostiene con el detector actual sobre 217 — el detector introduce suficiente imprecisión temporal propia (SDNN observado 109-175ms) como para enmascarar la variabilidad casi nula real del ritmo. No se ajustaron los umbrales del experto para forzar un resultado que coincidiera con el banco — hallazgo documentado en `docs/validation/ecg_hr_detector_bank/round4_whitelist_gate/HALLAZGO_stop.md` con la tabla completa y el diagnóstico de causa.

### Parte C — NO ejecutada

Bloqueada explícitamente detrás de la validación de la Parte B, que no pasó. Ningún botón añadido a ECG Lab; ninguna escritura cableada.

### Verificación

- `pytest tests/ -k "ecg_analyzer or bbb or qrs_delineation or clinical_pattern" -q`: **45 passed** — `detect_r_peaks()` original intacto, pipeline BBB sin cambios.
- `pytest tests/ -q`: **429 passed, 1 warning** (sklearn/LGBMClassifier, preexistente) — sin regresión.
- Servidor real (`streamlit run app/main.py`, puerto 8559): HTTP 200; proceso detenido tras la verificación. (La UI de ECG no se tocó en esta tanda, por lo que este chequeo confirma ausencia de regresión, no un flujo nuevo.)

**Integración estrecha: 2/3 completa** (Respiratory, HRV conectados; ECG sigue sin cerrar). Próxima tanda: recalibrar los umbrales de la compuerta contra la distribución real que el detector produce, o mejorar el detector antes de que los filtros de dinámica R-R sean fiables — decisión del experto sobre la evidencia entregada.

## 2026-08-24 — Capa 2 / Capa 5B, mini-arco (3ª tanda): desempate por pendiente recupera BRD (Parte A, éxito) — bandera de marcapasos NO confiable (Parte B, resultado negativo documentado) — Art. I — escritura al UPS sigue sin cablear

**Contexto**: el experto revisó la 2ª ronda y trazó la frontera clínica: bloqueo de rama (118, BRD) **dentro** de alcance (nodo sinusal = metrónomo, HRV válida — la regresión a sensibilidad 0.64 era inaceptable, había que recuperarla); marcapasos (217) **fuera** (máquina = metrónomo, no el sistema nervioso autónomo — calcular estrés/HRV sobre eso es inválido, la compuerta debe rechazarlo con el mensaje clínico correcto). Insight del experto: el marcador real del latido es la pendiente máxima (dv/dt), no la amplitud máxima.

### Parte A — Desempate refractario por pendiente: ÉXITO

`clinical/ecg_analyzer.py::detect_r_peaks_bidirectional()` — la regla de supresión de no-máximos cambió de "descarta el de menor amplitud absoluta" a "descarta el de menor pendiente máxima" (nuevo método privado `_max_slope()`: derivada discreta en una ventana de 15ms alrededor del pico candidato, no un solo punto — robusto a ruido de una muestra). Solo se modificó la lógica interna de este método nuevo (de la 2ª tanda); `detect_r_peaks()` original, que alimenta el pipeline BBB ya validado, sigue intacto — confirmado con los 45 tests dirigidos (`ecg_analyzer or bbb or qrs_delineation or clinical_pattern`), sin cambios.

**Resultado, contra ground truth de MIT-BIH**: registro 118 (BRD) — sensibilidad **0.64 → 0.991**, VPP **0.634 → 0.960** (por encima del objetivo de 0.95 y de la sensibilidad del detector original, 0.99). Sin regresión en los registros que ya iban bien: 100/103 idénticos, 233 se mantiene fuerte (0.997). 108 tiene una caída menor (0.96→0.90) pero sigue siendo una mejora enorme frente al detector original (0.16-0.18).

### Parte B — Bandera de marcapasos: RESULTADO NEGATIVO, documentado con evidencia

`ECGAnalyzer.detect_pacemaker_spikes()` (nuevo método) implementa exactamente el mecanismo especificado: picos de pendiente extrema (umbral robusto MAD), agrupados en eventos contiguos, aceptados como "espiga" solo si son angostos y están rodeados de pendiente normal. **No separa 217 de forma confiable de ningún otro registro del banco:**

- Barrido de umbral (`slope_z_threshold` de 10 a 30) sobre los 11 registros: a umbrales bajos (z=12-15), el registro 118 (BRD, que NUNCA debe marcarse como marcapasos) dispara MÁS eventos "espiga" que el propio 217 (118: 11-32 eventos vs 217: 1-10). A umbrales altos (z=20-25), 217 cae a 0 eventos — deja de detectarse del todo. No hay zona intermedia limpia: 108/207/228/233/210 producen sus propios eventos de pendiente extrema (ruido/ectopia), indistinguibles de una espiga real por amplitud/anchura/aislamiento solos.
- Inspección visual directa de 5 ubicaciones de máxima pendiente en el registro 217 (ambas derivaciones disponibles, MLII y V1): ninguna muestra una espiga aislada separable del QRS — todas son deflexiones suaves, fisiológicas. Posible causa: la digitalización a 360Hz de MIT-BIH (o un filtro de adquisición previo) pudo haber atenuado la espiga original antes de guardarse.
- **No se cableó** a `estimate_heart_rate_with_confidence()` — cablearla habría excluido BRD (violando la Parte A) o dejado pasar el marcapasos (violando la Parte B), según el umbral elegido. Se documentó el motivo en el docstring de ambos métodos en vez de forzar una demostración de éxito que la evidencia no respalda.

**El insight incómodo que la Parte A destapó**: con el detector reparado, 217 ahora se detecta con precisión genuina (sensibilidad 0.94, VPP 0.89 a `prominence_factor=2.0`) — la compuerta de calidad genérica lo ACEPTARÍA (confianza 0.63). No es un fallo de detección como en la 2ª ronda — es un ritmo estimulado bien detectado pero clínicamente inválido de todas formas. La mejora de la Parte A hace la Parte B **más** urgente, no menos.

### Parte C — Verificación de la lección transversal

Con el detector de pendiente, no apareció ningún caso nuevo de "confianza alta, detección mala" (la mejora de la Parte A también limpió ese espejismo específico en todo el banco). Surgió una pregunta análoga, no resuelta: el registro `210` (fibrilación auricular sostenida) se detecta con precisión y la compuerta lo acepta — pero en FA, el R-R lo determina la conducción caótica del nodo AV, no la modulación autonómica del nodo sinusal, el mismo principio que excluye el marcapasos podría aplicar. Reportado como pregunta abierta para el experto, no resuelto aquí.

### Artefacto de 3ª ronda

`docs/validation/ecg_hr_detector_bank/round3/`: `hoja_decision_experto_3a_ronda.pdf` (Parte A en caja verde, Parte B en caja roja con la evidencia completa, Parte C, 4 preguntas de la bendición final), `tiras_ecg_3a_ronda.pdf` (11 registros, amplitud vs pendiente, 118/217 anotados), `tabla_comparativa_3a_ronda.xlsx` (66 filas + hoja de recuperación de 118 + hoja de evidencia del barrido de la Parte B), scripts reproducibles.

### Verificación

- `pytest tests/ -k "ecg_analyzer or bbb or qrs_delineation or clinical_pattern" -q`: 45 passed — pipeline BBB sin cambios de comportamiento.
- `pytest tests/ -q`: **429 passed, 1 warning** (sklearn/LGBMClassifier, preexistente) — sin regresión.
- Servidor real (`streamlit run app/main.py`, puerto 8558): HTTP 200; proceso detenido tras la verificación.
- Cero cambios a la escritura del UPS — ECG sigue diferido, esperando la bendición final del experto (incluida la decisión sobre cómo proceder con el marcapasos sin detección automática confiable).

## 2026-08-24 — Capa 2 / Capa 5B, mini-arco (2ª tanda): detector de R reparado (bidireccional + refractario) + compuerta de calidad estructurada + banco re-validado con sensibilidad/VPP — hallazgo crítico de falso-aceptado (Art. I) — escritura al UPS sigue sin cablear

**Contexto**: el experto rechazó el detector original (`ECGAnalyzer.detect_r_peaks()`, ciego a QRS negativos, ningún `prominence_factor` lo arregla) y advirtió contra validar por error de HR promedio (registro 233: espejismo — falsos positivos/negativos se cancelan). Pidió la Solución 1 (bidireccional + periodo refractario) y una compuerta que devuelva HR+confianza, declinando en vez de adivinar.

### Paso 1 — Detector reparado, como método NUEVO (no in situ)

`clinical/ecg_analyzer.py::ECGAnalyzer.detect_r_peaks_bidirectional()` — decisión explícita: **no se modificó `detect_r_peaks()` en el sitio**. Ese método alimenta `detect_pqrst`/`measure_intervals`/`detect_st_elevation`/`detect_arrhythmias`/`detect_clinical_pattern` — el pipeline BBB **ya validado por el mismo experto contra 50 casos de PTB-XL**. Cambiarlo in situ habría alterado ese pipeline sin re-validación — exactamente el riesgo que esta campaña evita. El método nuevo: `find_peaks(signal)` (positivo) + `find_peaks(-signal)` (negativo, misma fórmula de umbral sobre la señal invertida — conserva la escala mV, `prominence_factor` sigue significando lo mismo) → fusión ordenada por tiempo → supresión por periodo refractario (200ms, límite fisiológico ~300bpm) quedándose con la mayor amplitud absoluta del grupo. Cada grupo colapsado con competencia cercana (segundo pico ≥70% de la amplitud del ganador) se registra en una lista `competitions` devuelta aparte — instrumentado para la revisión del experto, no resuelto por Claude Code.

### Paso 2 — Compuerta de calidad, estructura lista, umbral provisional

`ClinicalDataQualityError` (excepción) + `QUALITY_THRESHOLD = 0.6` (constante nombrada, documentada como PROVISIONAL) + `ECGAnalyzer.estimate_heart_rate_with_confidence()` — método nuevo y aditivo, `estimate_heart_rate()` intacto. Confianza calculable **sin ground truth** (debe funcionar en producción sobre PTB-XL, que no tiene anotaciones): mitad regularidad de intervalos RR, mitad consistencia de amplitud de los picos. Lanza `ClinicalDataQualityError` si hay <3 picos o confianza bajo el umbral — nunca un HR adivinado. No cableado a ningún flujo de producción.

### Paso 3 — Re-validación con sensibilidad/VPP (nunca error de HR promedio)

11 registros MIT-BIH (los 8 de la 1ª ronda + `210` fibrilación auricular sostenida — 98% de la duración bajo `(AFIB`, confirmado por análisis de las etiquetas de ritmo de las anotaciones — + `217` marcapasos + `100`-V5, otra derivación, los 3 añadidos tras la primera revisión) × 6 `prominence_factor` × detector viejo vs reparado, contra anotaciones `.atr` (ground truth objetivo), tolerancia ±50ms.

**Resultado — mixto, no una mejora uniforme, reportado sin suavizar:**

- **Mejoras reales**: `108` (bajo voltaje, antes ciego a su QRS negativo) sensibilidad 0.16→0.97; `207` (extremo, fibrilación/flutter ventricular+ruido) 0.28-0.36→0.75-0.84; `210` (AFib sostenida) mejora modesta consistente; `233` (la prueba del espejismo) sensibilidad 0.86→0.997, y a `pf=2.0` la compuerta ACEPTA correctamente (sensibilidad 0.997, VPP 0.963 — ahí sí es una señal genuinamente buena).
- **Regresiones reales**: `217` (marcapasos) sensibilidad 0.94-1.0→**0.147** — colapso severo; `118` (bloqueo de rama derecha) 0.99→0.64-0.67; `100`/`103` VPP empeora a `pf` bajo (más falsos positivos por deflexiones negativas espurias en registros ya limpios).
- **Corrección al hallazgo de la 1ª ronda**: `117` — la lectura visual de la 1ª ronda sugería que el detector viejo era "ciego" al QRS negativo; la medición numérica contra ground truth (esta ronda) muestra que su sensibilidad YA era 1.0 con el detector viejo — el punto positivo que marcaba caía dentro de la tolerancia ±50ms del punto anotado. El detector reparado no mejora sensibilidad ahí y empeora el VPP. Reportado como corrección explícita, no oculto.

**Hallazgo crítico — falso-aceptado de la compuerta**: en `217` a `prominence_factor=2.0`, la compuerta **ACEPTA** (confianza=0.70) con sensibilidad real de solo **0.147**. Mecanismo confirmado por inspección directa (no especulado): la supresión refractaria elige la deflexión negativa (mayor amplitud absoluta) del QRS ancho de un latido con marcapasos en vez de la deflexión positiva que coincide con la anotación del cardiólogo; el desfase resultante (~60-70ms) cae fuera de la tolerancia ±50ms. La regularidad mecánica y la consistencia de amplitud de las espigas de marcapasos engañan a la métrica de confianza (diseñada para funcionar sin ground truth). **La compuerta, tal como está diseñada hoy, no es segura para ritmos con marcapasos.**

### Paso 4 — Artefacto de 2ª ronda

`docs/validation/ecg_hr_detector_bank/round2/`: `hoja_decision_experto_2a_ronda.pdf` (el hallazgo crítico primero, luego 4 preguntas), `tiras_ecg_2a_ronda.pdf` (11 registros, viejo vs reparado, competencias bifásicas marcadas con círculo naranja), `tabla_comparativa_2a_ronda.xlsx` (66 filas + hoja aislando el falso-aceptado), scripts reproducibles con rutas portables.

### Verificación

- `pytest tests/ -k "ecg_analyzer or bbb or qrs_delineation or clinical_pattern" -q`: 45 passed — el pipeline BBB/clínico ya validado no cambió de comportamiento (confirma que la decisión de no tocar `detect_r_peaks()` in situ fue correcta).
- `pytest tests/ -q`: **429 passed, 1 warning** (sklearn/LGBMClassifier, preexistente) — sin regresión.
- Servidor real (`streamlit run app/main.py`, puerto 8557): HTTP 200; proceso detenido tras la verificación.
- Cero cambios a la escritura del UPS — ECG sigue diferido, esperando la 2ª respuesta del experto.

## 2026-08-24 — Capa 2 / Capa 5B, mini-arco: banco de validación del detector de HR de ECG preparado para revisión del experto (Art. I) — cero cambios de producción

**Contexto**: ECG quedó diferido en la Fase 2.4 (ver entrada anterior, "TERCER LAB") porque su `heart_rate` fiable exigía un `prominence_factor` no bendecido en ningún otro lugar del repo — escribirlo sin validación habría quedado medio escalón bajo la vara que el BBB ya cumplió (revisión humana con 50 ECGs, 2 erratas de PTB-XL encontradas). Este mini-arco prepara ese mismo tipo de banco para el detector de HR: Claude Code corre el análisis y produce el material, el experto aporta el juicio clínico. **Ninguna línea de código de producción de ECG se tocó** — todo el trabajo vive en `docs/validation/ecg_hr_detector_bank/`, un paquete de solo lectura contra `clinical/ecg_analyzer.py::ECGAnalyzer.detect_r_peaks()` (llamado, no modificado).

### Paso 1 — Ground truth

`wfdb.rdann(record, 'atr', pn_dir='mitdb')` sí lee las anotaciones de latido de MIT-BIH (picos QRS marcados por cardiólogos, símbolos `N`/`A`/`V`/`+`) — confirmado por ejecución sobre el registro 100 (2274 anotaciones leídas). **Ground truth objetivo disponible para MIT-BIH.** PTB-XL, en cambio, **no** trae anotaciones de latido descargables — confirmado: `wfdb.rdann()` sobre un registro PTB-XL da `404 Not Found` para el `.atr`; PTB-XL solo aporta códigos diagnósticos SCP a nivel de registro completo, no marcas de latido.

### Paso 2 — Conjunto de registros (provisional, cribado cuantitativo propio)

Cribados 23 candidatos de MIT-BIH por 4 métricas (proporción T/R, carga arritmica, voltaje QRS pico-a-pico, ruido bruto). Conjunto final de 8 registros, marcado explícitamente como **provisional** para el experto: `100`/`103` (limpios), `117` (T/R=0.79, la trampa de onda T más alta del cribado), `108` (voltaje QRS mínimo del cribado + PACs), `228` (arritmia real, PVCs), `207` (caso extremo: fibrilación/flutter ventricular + ruido, rr_cv=0.639 el más alto), `233` (ruido más alto del cribado), `118` (bloqueo de rama derecha, morfología distinta).

### Paso 3 — Barrido de parámetros contra ground truth

`ECGAnalyzer.detect_r_peaks()` (sin modificar) sobre 180s de cada uno de los 8 registros × `prominence_factor` ∈ {0.3, 0.5, 0.7, 1.0, 1.5, 2.0} — 48 combinaciones. Por cada una: HR detectado vs HR de ground truth, sensibilidad y VPP (emparejamiento de picos contra anotaciones, tolerancia ±50ms).

**Hallazgo principal, no anticipado al iniciar el banco**: los registros 117 y 108 comparten una causa raíz — en esta derivación (MLII), el QRS es predominantemente **negativo**. `ECGAnalyzer.detect_r_peaks()` usa `scipy.signal.find_peaks()`, que solo busca máximos **positivos** — el detector nunca ve el latido real en estos dos registros, en NINGÚN `prominence_factor` del barrido (VPP tope ~0.53 en 117; sensibilidad 0.15–0.18 en 108, constante en todo el rango). No es un problema de umbral — es una limitación estructural, visible de un vistazo en las tiras (el triángulo rojo marca sistemáticamente una onda positiva secundaria, nunca la X verde del QRS real).

Otros hallazgos del barrido:
- `207` (extremo): sensibilidad nunca supera ~0.36 en ningún parámetro — fuera del alcance de este detector tal cual está.
- `233` (ruidoso): el error de HR promedio se ve engañosamente bueno (<3bpm en casi todo el barrido) pese a sensibilidad/VPP imperfectos — falsos positivos y negativos se cancelan en el promedio. Advertencia explícita en la hoja de decisión: evaluar solo por error de HR promedio puede ocultar un detector poco fiable.
- `100`/`103`/`118`: `prominence_factor=1.0` da sensibilidad/VPP ≥0.98 y error de HR <1bpm — el caso favorable.
- `228`: `1.0` minimiza el error de HR (0.3bpm) pero sensibilidad/VPP quedan en ~0.85–0.87 — umbrales más altos pierden latidos ectópicos.

### Paso 4 — El artefacto revisable

`docs/validation/ecg_hr_detector_bank/`:
- `hoja_decision_experto.pdf` — resume el hallazgo principal y las 3 preguntas para el experto (¿el conjunto de registros basta?, ¿las anotaciones MIT-BIH bastan como ground truth?, ¿qué criterio de aceptación / qué `prominence_factor` — o si el detector necesita un cambio estructural antes de que cualquier parámetro sea aceptable?).
- `tiras_ecg_picos_marcados.pdf` — 8 registros × 2 parámetros (0.3 default vs 1.0 candidato), señal con picos detectados y anotaciones de cardiólogo superpuestos, portada y leyenda incluidas.
- `tabla_comparativa_detector_hr.xlsx` — 48 filas con HR/error/sensibilidad/VPP/TP/FP/FN, coloreadas por umbral de calidad; segunda hoja de contraste 0.3 vs 1.0 con veredicto textual por registro.
- `raw_results.json` + los 4 scripts que regeneran todo desde cero (rutas ya portables, no hardcodeadas a esta máquina).

### Verificación

- Confirmado por lectura: `detect_r_peaks()` se llama, nunca se modifica; ningún archivo de `app/`, `clinical/`, `domain/` tocado en esta tanda.
- Tiras y tabla verificadas legibles: PNG de vista previa de dos registros (117, 108) inspeccionadas visualmente antes de dar el banco por bueno — confirmaron el hallazgo del QRS negativo antes de escribir el hallazgo en la hoja de decisión.
- `pytest tests/ -q`: **429 passed, 1 warning** (sklearn/LGBMClassifier, preexistente) — sin regresión, como se esperaba de una tanda de solo lectura.

ECG sigue diferido — este banco es el insumo para que el experto decida el parámetro/criterio; la escritura de ECG al UPS (cerrando la integración estrecha, 3/3) es la tanda siguiente, una vez el experto responda.

## 2026-08-24 — Capa 2, Fase 2.4: segundo lab de la integración estrecha — HRV Analysis escribe al UPS, el corazón del gemelo reacciona (Art. I)

**Contexto**: con el piloto de Respiratory cerrado (primer lab conectado, pulmones reaccionando, `cardiovascular` vacío confirmado), se replica el mismo molde a HRV Analysis — el escritor cardio-únicamente, imagen espejo de Respiratory. Sirve como prueba viva del segundo gate de raíz (el respiratorio): al guardar, el estado debe quedar con `respiratory.descriptors == {}`.

### Paso 1 — Mini-diagnóstico cardiovascular

Confirmado por lectura: `render_hrv_page()` calcula `sdnn`/`rmssd`/`pnn50`/`mean_nn` con fórmulas estándar sobre un array `rr_ms` real (pegado manualmente o generado en modo demo con jitter gaussiano sobre un HR objetivo) — **honesto, cierra la verificación pendiente de la Capa 3** ("HRV probablemente honesto, verificar RR reales").

**Mapeo HRV→campo, no ambiguo**: `domain/physiology/ml/risk_context.py:67` ya documentaba la convención — *"el UPS solo modela un 'hrv' genérico en ms — se usa como proxy de SDNN"*. Se sigue esa convención existente, no una decisión nueva: `hrv` (UPS) ← `sdnn`; `heart_rate` (UPS) ← `60000/mean_nn`, derivado de la misma serie RR real. `rmssd`/`pnn50`/LF/HF no tienen slot — no se escriben.

**Qué lee el gemelo**: `_render_heart_card()` lee `heart_rate` directo (color/velocidad/etiqueta). `hrv` no se lee directo, pero alimenta `_detect_events()`: `heart_rate` en rango normal (40-120) **y** `hrv<20` dispara `LOW_HRV_AUTONOMIC_STRESS` (halo amarillo + badge "😰 Estrés autonómico (HRV bajo)"). Se escriben ambos campos para demostrar la reacción completa.

### Paso 2 — La escritura construida

`app/main.py::_render_hrv_save_to_twin()`, botón **"💾 Guardar estado al gemelo"** tras las 3 métricas de Vista Clínica — molde idéntico al de Respiratory: mismo bootstrap (`twin_shell_ups_session_factory`/`twin_shell_ups_patient_id`), `Provenance.SIMULACION` + `source_detail="hrv_lab:sdnn_desde_serie_rr:fuente=<Demo|Manual>"`, botón explícito.

### Paso 3 — Verificación por ejecución: el corazón reacciona, el pulmón NO se fabrica

AppTest de extremo a extremo, mismo `patient_id` compartido (Twin OS → HRV Analysis → Twin OS), serie RR manual de baja variabilidad (`SDNN=1.7ms`, HR normal ≈75bpm — elegida para disparar `LOW_HRV_AUTONOMIC_STRESS` sin cruzar el umbral de arritmia):

- **Antes**: corazón gris neutro `#64748b`, `"FC: sin dato en el UPS"`.
- HRV Analysis: RR manual pegado (`800,802,798,801,...`), SDNN=1.7ms/RMSSD=3.0ms mostrados, clic "Guardar estado al gemelo" → `"Estado guardado al gemelo -- snapshot: f54bd5d1-..."`, caption confirma `cardiovascular: 7 descriptores · respiratory: 0 descriptores (vacío esperado)`.
- **Después**: corazón amarillo de alerta `#ffc542`, animación de latido activa (0.80s = 60/75bpm), `"FC: 75 bpm"`, badge `"😰 Estrés autonómico (HRV bajo)"` — el evento predicho por el Paso 1 se dispara exactamente.
- **Raíz espejo confirmada**: `respiratory.descriptors == {}` en el estado escrito por HRV — junto con el piloto de Respiratory (`cardiovascular.descriptors == {}`), las dos raíces quedan probadas en dos escritores reales y complementarios.

### No-regresión

- Patient Pipeline por AppTest: 13 filas, ambos dominios, sin cambios.
- Respiratory Lab (piloto anterior) re-verificado: mismo flujo, mismo resultado (`cardiovascular: 0 · respiratory: 8`) — el botón de HRV no lo afectó.
- Barrido de los 10 módulos por AppTest (incluye HRV Analysis con el botón nuevo): **10/10 sin excepción**.
- `pytest tests/ -q`: **429 passed, 1 warning** (sklearn/LGBMClassifier, preexistente) — sin regresión.
- Servidor real (`streamlit run app/main.py`, puerto 8556): HTTP 200; proceso detenido tras la verificación.

Segundo lab de la integración estrecha conectado — molde del piloto replicado sin ajustes estructurales. Queda ECG para cerrar los tres labs de la Fase 2.4.

## 2026-08-24 — Capa 2, Fase 2.4: piloto de integración estrecha — Respiratory Lab escribe al UPS, el gemelo reacciona de verdad (Art. I)

**Contexto**: con las dos raíces del builder ya honestas por arquitectura (fixes anteriores de esta misma fase), se construye el primer escritor real de la integración estrecha: Respiratory Lab, hoy aislado, escribe `respiratory_rate`/`spo2`/`ahi` reales al UPS bajo un botón explícito, y Digital Twin OS reacciona.

### Paso 1 — Diagnóstico del patient_id (punto de parada, resuelto con el usuario)

Grep confirmó que **no existe un `patient_id` de sesión compartido**: Patient Pipeline resuelve el suyo por `st.text_input` (etiqueta libre, default `"PATIENT-001"`, cacheado en `session_state["patient_pipeline_ups_patient_id"]`); Twin OS auto-crea el suyo una vez por sesión de navegador con nombre fijo `"Paciente Demo (Twin Shell)"` (`init_session()`, `session_state.twin_shell_ups_patient_id`) — dos filas distintas del mismo archivo `data/biocore_ups.db`. El gemelo que Twin OS renderiza lee siempre bajo `twin_shell_ups_patient_id`.

Presentadas dos opciones al usuario: (a) construir un paciente de sesión compartido, migrando Twin OS y Patient Pipeline; (b) para el piloto, reutilizar directamente las claves de `session_state` que Twin OS ya usa. **Elegido: (b)** — alcance mínimo, cero cambios a los otros dos módulos.

### Paso 2 — La escritura construida

`app/supermodules/respiratory_lab/pages.py::_render_save_to_twin()`, expuesta en la Vista Investigación (donde ya vive el puente de sesión con el análisis real, Ejecución 2 de la Fase 2.2) tras un botón **"💾 Guardar estado al gemelo"**:

- Bootstrap idéntico al de `twin_shell.pages.init_session()` (mismas claves `twin_shell_ups_session_factory`/`twin_shell_ups_patient_id`, mismo `display_name`) — si el usuario ya visitó Twin OS esta sesión, reutiliza el mismo factory/paciente tal cual; si no, lo crea con el mismo nombre para que `init_session()` lo encuentre después y no duplique.
- Escribe solo lo real con destino y efecto (cruce del recon 2.4.0): `respiratory_rate` y `ahi` de `analysis` (el `RespiratoryAnalysis` ya calculado, sin recalcular), `spo2` mapeado desde `analysis.baseline_spo2` (elegido sobre `minimum_spo2` — representa el nivel de reposo del patrón activo, coherente con cómo Patient Pipeline/Twin OS tratan `spo2` como valor de estado, no un nadir puntual). `rr_variability`/`apnea_type`/`breathing_pattern`/etc. — sin destino en el schema — no se escriben.
- `Provenance.SIMULACION` + `source_detail="respiratory_lab:investigacion:patron=<patrón activo>"` — señal generada, nunca `SENSOR_REAL`.
- Botón explícito, nunca automático — un guardado por clic, no uno por cada arrastre de slider.

### Paso 3 — Verificación por ejecución: el gemelo reacciona

AppTest de extremo a extremo, mismo `patient_id` compartido entre dos instancias de sesión (Twin OS → Respiratory Lab → Twin OS):

- **Antes** (Twin OS, sesión fresca, cero snapshots para este paciente): pulmones en gris neutro `#64748b`, `"RR: sin dato · SpO₂: sin dato"`.
- En Respiratory Lab: RR llevado a 34 resp/min y SpO2 Basal a 85% en la Vista Clínica, clic en "Guardar estado al gemelo" → `"Estado guardado al gemelo -- snapshot: df8a61c1-..."`, caption confirma `cardiovascular: 0 descriptores (vacío esperado) · respiratory: 8 descriptores`.
- **Después** (Twin OS, mismo `patient_id`): pulmones cambian a amarillo de alerta `#ffc542`, animación de respiración activa, `"RR: 60 resp/min · SpO₂: 93%"`, badge `"🫁 SpO₂ bajo lo esperado"` (evento `HYPOXIA_SPO2_LOW` real, detectado automáticamente por el mismo umbral que ya usa el builder). Los valores detectados (60bpm/93%) difieren de los pedidos en el slider (34/85) porque `RespiratoryAnalyzer` mide la señal generada, no repite el parámetro de entrada — comportamiento honesto y preexistente del analizador, no alterado aquí.
- Cadena de honestidad confirmada: `respiratory` con procedencia `simulacion` declarada; `cardiovascular` vacío — el gemelo reacciona a un dato respiratorio real, no a un corazón fabricado (las raíces cerradas en esta misma fase hacen su trabajo aquí, en un escritor real, sin intervención manual).

### No-regresión

- Patient Pipeline por AppTest: tabla de 13 filas, ambos dominios, sin cambios frente al run previo a esta tanda.
- Barrido de los 10 módulos por AppTest (incluye Respiratory Lab con el botón nuevo y Digital Twin OS): **10/10 sin excepción**.
- `pytest tests/ -q`: **429 passed, 1 warning** (sklearn/LGBMClassifier, preexistente) — sin regresión.
- Servidor real (`streamlit run app/main.py`, puerto 8555): HTTP 200; proceso detenido tras la verificación.

Primer lab de la integración estrecha conectado al UPS real — patrón que replicarán HRV y ECG. La raíz honesta por arquitectura (fixes previos de esta fase) ya demostró su valor: ningún corazón fantasma que limpiar a mano en este escritor.

## 2026-08-22 — Capa 2, Fase 2.4: gemelo respiratorio del corazón fantasma cerrado — builder barrido, las dos raíces honestas por arquitectura (Art. I)

**Contexto**: la tanda anterior gateó `_cardiovascular_state()` para que un escritor solo-respiratorio no fabricara un corazón fantasma. Se había reportado, no corregido, el gemelo espejo en `_respiratory_state()`: mismo patrón sin gate — un escritor cardio-únicamente (HRV, ECG, las próximas dos integraciones estrechas) poblaría un dominio respiratorio fantasma. Se cierra ahora con el método idéntico, y se barre el builder entero por si había un tercero.

### Paso 1 — Diagnóstico de lectores respiratorios

Grep de todo lector de `health_score`/`risk_score`/`hypoxia_risk`/`apnea_risk`/`tissue_oxygenation` del dominio `respiratory`: **cero código de producción y cero tests los leen** — mismo resultado que en el diagnóstico cardiovascular. Todo consumidor de producción (`ups_body_visual.py`, `twin_shell/pages.py`) y los 4 tests que tocan el dominio respiratorio (`test_ups_state.py`, `test_scenario_simulator.py`, `test_coupling_engine.py`) solo leen `respiratory_rate`/`spo2` (ya gateados), siempre vía `.get()` con manejo de `None` explícito o en contextos donde el escenario usado (`"healthy"`, `"hipoxia_progresiva"`) siempre provee esos dos campos. **Ningún consumidor se rompe sin el dominio respiratorio** — luz verde, sin necesidad de detenerse.

Confirmado (ya establecido en la tanda anterior, re-verificado aquí): Patient Pipeline siempre construye `sensor_data` con `"respiratory": {"respiratory_rate": rr, "spo2": spo2}`; `render_sensor_controls()` de Twin OS hace lo mismo en cada rerun, incondicionalmente. El gate `has_real_respiratory_input` se cumple siempre para ambos.

### Paso 2 — El fix (gate simétrico)

`_respiratory_state()` ([builder.py](domain/physiology/state/builder.py)): `has_real_respiratory_input = "respiratory_rate" in signals` — mismo nombre de patrón, misma forma (`if has_real_respiratory_input:` envolviendo `health_score`/`risk_score`/`hypoxia_risk`/`apnea_risk`/`tissue_oxygenation`) que el gate cardiovascular de la tanda anterior. Sin dato respiratorio real, `DomainState(domain="respiratory", descriptors={})`. No se tocó el organismo — misma decisión que en cardiovascular: el builder es el gate de persistencia, los defaults de `RespiratoryDetail()` siguen alimentando legítimamente la simulación en vivo.

### Paso 3 — Barrido de cierre: ¿tercer gemelo?

`builder.py` define exactamente dos funciones de dominio: `_cardiovascular_state()` y `_respiratory_state()` — confirmado por grep (`^def _\w+_state\(`). Coincide estructuralmente con `UnifiedPhysiologicalState` ([schema.py](domain/physiology/state/schema.py)), que tiene exactamente dos campos de dominio (`cardiovascular`, `respiratory`) — no hay un tercer dominio que el builder pudiera construir aunque quisiera. **Confirmado: builder barrido, solo cardiovascular y respiratorio tenían el patrón, ambos gateados. No hay tercer gemelo — no porque no se buscara, sino porque el esquema no tiene dónde esconder uno.**

### Paso 4 — Verificación dura

- **Escritor parcial cardio-únicamente** (`{"ecg": {"heart_rate": 95, "hrv": 30}}`, sin `respiratory`): `state.respiratory.descriptors == {}` — confirmado. `cardiovascular` queda con sus 7 descriptores reales (2 medidos + 5 derivados).
- **Ambos dominios en la misma corrida**: estado solo-respiratorio → `cardiovascular.descriptors == {}`; estado solo-cardíaco → `respiratory.descriptors == {}` — las dos raíces limpias, probadas juntas.
- **No-regresión, before/after literal** (ecg+respiratory, patrón Patient Pipeline): builder original (sin gate) reproducido como función aislada sobre el mismo organismo — resultado idéntico valor a valor:
  ```
  ANTES: {apnea_risk: 0.0, health_score: 79.0, hypoxia_risk: 0.0, respiratory_rate: 16.0, risk_score: 0.0, spo2: 98.0, tissue_oxygenation: 98.0}
  AHORA: {apnea_risk: 0.0, health_score: 79.0, hypoxia_risk: 0.0, respiratory_rate: 16.0, risk_score: 0.0, spo2: 98.0, tissue_oxygenation: 98.0}
  ```
- `render_patient_pipeline_page()` por AppTest: clic "Guardar nuevo estado" → sin excepción, tabla de descriptores idéntica a antes del fix (13 filas, ambos dominios completos).
- Barrido completo de los 10 módulos por AppTest (incluye Digital Twin OS): **10/10 sin excepción**.
- `pytest tests/ -q`: **429 passed, 1 warning** (sklearn/LGBMClassifier, preexistente) — sin regresión.
- Servidor real (`streamlit run app/main.py`, puerto 8554): HTTP 200; proceso detenido tras la verificación.

Con esto quedan cerradas las dos raíces del builder del UPS: ningún escritor parcial (Respiratory, HRV o ECG, las tres integraciones estrechas de la Fase 2.4) puede sembrar un dominio fabricado en el estado que persiste. La honestidad es ahora una propiedad de la arquitectura, no de la disciplina de cada llamador. La escritura real de Respiratory Lab al UPS sigue sin construirse — sigue siendo la tanda siguiente.

## 2026-08-22 — Capa 2, Fase 2.4: corazón fantasma DERIVADO erradicado en la raíz del builder del UPS (Art. I)

**Contexto**: el recon de la Fase 2.4.0 (turno anterior, solo diagnóstico) encontró un defecto latente en `domain/physiology/state/builder.py::_cardiovascular_state()`: `DigitalTwinOrganism` nace con `heart.detail = CardiacDetail()` (defaults de aspecto plausible — `cardiac_output=5.0`, `rhythm_stability=85.0`, `myocardial_stress=30.0`) y `heart.metrics.health_score/risk_score` en 50.0/0.0, todo poblado en el constructor, antes de que `_update_heart()` corra ni una vez. El builder escribía `health_score`/`risk_score`/`rhythm_stability`/`myocardial_stress`/`cardiac_output` **incondicionalmente** — sin el gate `if "heart_rate" in signals` que sí protegía a `heart_rate`/`hrv`. Cualquier escritor que pasara solo datos respiratorios persistiría un corazón sano, completo, `Provenance.DERIVADO`, indistinguible de uno medido — el mismo patrón de fachada que la Capa 3 extinguió, dormido hasta ahora porque los dos escritores vivos (Patient Pipeline, Twin OS) siempre pasan `ecg`+`respiratory` juntos. Se cierra en la raíz antes de que Respiratory (la primera integración estrecha parcial) lo activara.

### Paso 1 — Diagnóstico de consumidores (antes de tocar nada)

Grep de todo lector de `health_score`/`risk_score`/`rhythm_stability`/`myocardial_stress`/`cardiac_output` sobre un `UnifiedPhysiologicalState`: **cero código de producción los lee** — solo 2 tests (`test_ups_state.py:89`, `test_scenario_simulator.py:50`) tocan `cardiovascular.get("health_score")`, y ambos ocurren en escenarios que SIEMPRE incluyen `ecg` (`create_patient_scenario("healthy")`, `"fibrilacion_estres"`). Todo el código de producción que sí lee campos cardiovasculares (`ups_body_visual.py`, `twin_shell/pages.py`, `academia/pages.py`, `domain/physiology/hemodynamics/*_comparison.py`, `domain/physiology/ml/{ecg_signal_source,risk_context}.py`) usa `DomainState.get(name)` (devuelve `Optional`, nunca `KeyError`) y solo sobre `heart_rate`/`hrv`/`map_modelo`/`systolic_bp_modelo`/etc. — campos que YA estaban gateados, sin tocar en esta tanda — con chequeo `is not None` explícito antes de `.value`. **Ningún consumidor se rompe sin el corazón.** Luz verde confirmada, no fue necesario detenerse.

Confirmación de no-regresión de los dos escritores vivos: `app/main.py::render_patient_pipeline_page()` siempre construye `sensor_data={"ecg": {"heart_rate": hr}, "respiratory": {...}}` (ambos sliders del formulario, sin condicional); `app/supermodules/twin_shell/pages.py::render_sensor_controls()` llama `organism.update_from_sensors({"ecg": {...}, "respiratory": {...}, "eeg": {...}, "emg": {...}})` **en cada rerun del script, incondicionalmente**, antes de que se alcance cualquier botón de guardado — el gate `"heart_rate" in signals` se cumple siempre para ambos.

Hallazgo colateral del diagnóstico, corregido en esta misma nota (no en el código): al investigar si el botón "🔴 EPOC" de Twin OS (`create_patient_scenario("copd")`, que solo toca `lungs`) seguido de "🔄 Sincronizar" reproducía el bug en vivo, la verificación por ejecución (AppTest) mostró que **no** — `render_sensor_controls()` se ejecuta primero en cada rerun y siempre re-alimenta `heart_rate` desde los sliders (72 por defecto) antes de que el botón de escenario o cualquiera de los 3 botones "snapshot bajo demanda" corran su propio código. El bug era real a nivel de builder (confirmado por construcción aislada, ver Paso 3) pero **nunca fue alcanzable por ningún camino de UI ya cableado** — puramente latente, tal como se sospechaba, no un defecto ya visible que se hubiera pasado por alto.

### Paso 2 — El fix

`_cardiovascular_state()` ([builder.py](domain/physiology/state/builder.py)): se introdujo `has_real_cardiac_input = "heart_rate" in signals`, y `health_score`/`risk_score`/`rhythm_stability`/`myocardial_stress`/`cardiac_output` ahora se escriben solo `if has_real_cardiac_input:` — exactamente simétrico al gate que ya protegía a `heart_rate`/`hrv`. Sin dato cardíaco real, `DomainState(domain="cardiovascular", descriptors={})` — vacío, no fabricado.

**Decisión sobre el organismo**: no se tocó `DigitalTwinOrganism._initialize_organs()`/`CardiacDetail()`. El builder es el gate de persistencia — es el único punto donde "estado en memoria" se convierte en "registro guardado", y ahí es donde debe vivir la barrera de honestidad. Los defaults del organismo alimentan además cálculos de la simulación EN VIVO (`_propagate_physiological_effects()`, el dashboard de Twin OS que muestra `organ.metrics.health_score` directamente del objeto en memoria, `to_json()`) que legítimamente necesitan un punto de partida numérico para existir como simulación interactiva — tocar eso arriesgaba rehacer la semántica del organismo entero para un problema que ya se cierra completo en el builder.

**Gemelo del bug, encontrado y NO corregido (fuera de alcance, reportado)**: `_respiratory_state()` tiene el mismo patrón — `lungs.detail = RespiratoryDetail()` nace con defaults plausibles (`hypoxia_risk=10.0`, `apnea_risk=5.0`, `tissue_oxygenation=80.0`) y el builder escribe `health_score`/`risk_score`/`hypoxia_risk`/`apnea_risk`/`tissue_oxygenation` sin gate alguno — solo `respiratory_rate`/`spo2`/`ahi` están protegidos. Un futuro escritor cardio-únicamente (ECG o HRV, las otras 2 integraciones estrechas del roadmap) activaría el defecto simétrico: pulmones fantasma. No se corrigió aquí — mismo alcance que pidió esta tanda (solo cardiovascular) — queda registrado para autorizar en una tanda dedicada.

### Paso 3 — Verificación dura

- **Escritor parcial** (`update_from_sensors({"respiratory": {...}})`, sin `ecg`): `state.cardiovascular.descriptors == {}` — confirmado por construcción directa. El dominio respiratorio sí queda con sus 8 descriptores reales (3 medidos + 5 derivados, porque lungs SÍ recibió dato real en esta prueba).
- **No-regresión, before/after literal**: se reprodujo el builder ORIGINAL (sin el gate) como función aislada y se ejecutó sobre el MISMO organismo con `ecg`+`respiratory` (patrón Patient Pipeline). Resultado idéntico valor a valor:
  ```
  ANTES: {cardiac_output: 5.0, health_score: 100.0, heart_rate: 72.0, myocardial_stress: 0.0, rhythm_stability: 50.0, risk_score: 0.0}
  AHORA: {cardiac_output: 5.0, health_score: 100.0, heart_rate: 72.0, myocardial_stress: 0.0, rhythm_stability: 50.0, risk_score: 0.0}
  ```
  Y se confirmó el mismo builder ORIGINAL SÍ producía el fantasma completo (`health_score=50.0, risk_score=0.0, rhythm_stability=85.0, myocardial_stress=30.0, cardiac_output=5.0`, todos DERIVADO) para el caso solo-respiratorio — la prueba de que el fantasma existía y de que el fix lo mata, en la misma corrida.
- `render_patient_pipeline_page()` por AppTest: clic en "Guardar nuevo estado" → sin excepción, tabla de descriptores muestra las 6 claves cardiovasculares (`heart_rate`, `health_score`, `risk_score`, `rhythm_stability`, `myocardial_stress`, `cardiac_output`) con los mismos valores que antes del fix.
- `render_twin_shell_page()` por AppTest: render inicial, clic "🔴 EPOC", clic "🔄 Sincronizar con sliders actuales" — sin excepción en ningún paso; el cuerpo visual sigue mostrando "FC: 72 bpm" (por el hallazgo del Paso 1: los sliders siempre re-alimentan `ecg` antes de cualquier guardado en esta página).
- `pytest tests/ -q`: **429 passed, 1 warning** (sklearn/LGBMClassifier, preexistente) — sin regresión, incluidos los tests que usan escritores respiratorio-únicamente (`test_ups_state.py::test_events_are_first_class_and_persisted` con `create_patient_scenario("copd")`, `test_scenario_simulator.py`/`test_narrator.py` con el escenario `"hipoxia_progresiva"`, ninguno de los cuales asertaba sobre presencia de descriptores cardiovasculares).
- Servidor real (`streamlit run app/main.py`, puerto 8553): HTTP 200; proceso detenido tras la verificación.

Con esto queda cerrada la raíz que las tres integraciones estrechas (Respiratory/HRV/ECG) necesitan heredar honesta por arquitectura. La escritura real de Respiratory Lab al UPS sigue sin construirse — es la tanda siguiente.

## 2026-08-21 — Capa 2, Fase 2.2, Ejecución 2 de 2 (cierre de fase): 9 pestañas vacías retiradas, 3 llenadas con contenido real, vocabulario canónico, deuda de señal de ECG registrada

**Contexto**: cierra la Fase 2.2. Aplica R1 (ninguna pestaña vacía sobrevive) con criterio R3 (llenar si el contenido real ya existe, retirar si habría que fabricarlo) sobre el inventario de la Parte 0. Vocabulario canónico: Clínica/Educativa/Investigación/Simulación/IA — "Gemelo Digital" queda fuera como nombre de pestaña en todo el repo; el gemelo real es destino de integración de la Fase 2.4, no contenido a fabricar aquí.

### Parte A — Retiros (9 pestañas — el enunciado de la tanda decía 8, el recuento real de las 3 listas por módulo da 9; se ejecutó la lista explícita, no el número del título)

- **ECG-12** (`app/supermodules/ecg_12/pages.py`): retiradas Investigación, Simulación, Gemelo Digital. Quedan Clínica, Educativa (llenada, ver Parte B).
- **EEG Neuro Lab** (`app/supermodules/eeg_neuro_lab/pages.py`): retiradas Educativa, Investigación, Simulación, Gemelo Digital. Queda solo Clínica.
- **Respiratory Lab** (`app/supermodules/respiratory_lab/pages.py`): retiradas Educativa, Gemelo Digital. Quedan Clínica, Investigación (llenada), Simulación (llenada).

Cada retiro quitó la pestaña de `st.tabs([...])` y su bloque `with tabs[i]:` completo — verificado por AppTest que no queda ningún índice de tabs roto (todas corren `exception=[]` hasta el final del render).

**Candidatas a contenido futuro** (llenarlas exigiría fabricar análisis que no existe hoy en el repo — no se construyó nada, solo se deja registrado):
- ECG-12 · Investigación (comparación de derivaciones, análisis de segmentos)
- ECG-12 · Simulación (cambio de ubicación de derivaciones)
- EEG · Educativa (tutoriales de ritmos/artefactos)
- EEG · Investigación (bandas, conectividad, cohortes)
- EEG · Simulación (simuladores de actividad cerebral)
- Respiratory · Educativa (mecánica ventilatoria) — nota: a diferencia de las demás, esta sí tiene una fuente de contenido real ya escrita (el sidebar "📚 INFORMACIÓN EDUCATIVA" de `page_content.py`, 4 secciones de texto clínico) que una tanda futura podría exponer como pestaña propia con el mismo patrón de puntero honesto usado en ECG-12·Educativa — no se hizo aquí por estar fuera del alcance explícito de esta Ejecución.

**No son candidatas — destino de la Fase 2.4** (integración al gemelo real, no una pestaña a construir):
- ECG-12 · Gemelo Digital
- EEG · Gemelo Digital
- Respiratory · Gemelo Digital

### Parte B — Llenados (contenido que ya existía, cableado sin fabricar cálculo)

- **ECG-12 · Educativa**: puntero honesto a la tabla real de 12 derivaciones en Learning Hub → Academia Clinica → Lecciones y Casos → Teoría (mismo patrón que ya usa `render_education_page()`). Verificado por AppTest: el texto exacto aparece en el render.
- **Respiratory · Investigación**: expone el AHI y los eventos de apnea que `RespiratoryAnalyzer` YA calcula en la Vista Clínica (`page_content.py`, sub-pestaña "Análisis Avanzado"). Puente vía `st.session_state['_respiratory_lab_analysis']`, poblado por el bloque `with tabs[0]:` (Clínica), que siempre corre antes de que se renderice "Investigación" en el mismo rerun de Streamlit — cero recálculo. Añade tabla de eventos + botón de exportación CSV (`st.download_button`), ausentes en la Vista Clínica original. Verificado por AppTest: con los parámetros por defecto de Clínica, Investigación muestra el mismo AHI/severidad/conteo de eventos que la Vista Clínica (sin duplicar el cálculo).
- **Respiratory · Simulación**: sliders propios de RR (6-40 resp/min) y volumen corriente/profundidad (0.1-1.5L) que regeneran la señal vía `RespiratorySignalGenerator`/`RespiratoryPattern` (patrón "normal", mismo motor que Clínica). **Prueba anti-placebo por ejecución (lección de Multisensor)**: `AppTest`, sliders por defecto (RR=15, TV=0.5) → amplitud torácica pico-a-pico=1.05, ciclos en ventana=8; TV→1.2 (RR igual) → pico-a-pico=2.45 (ciclos sin cambio, correcto — TV no debe mover el conteo de ciclos); RR→40 (TV=1.2) → ciclos=20, pico-a-pico≈igual (correcto — RR no debe mover la amplitud). Ambos parámetros mueven exactamente lo que deberían y nada más — a diferencia del HR de Multisensor, `RespiratorySignalGenerator` sí usa `respiratory_rate`/`tidal_volume` en el cálculo real de cada patrón (confirmado leyendo `respiratory_generator.py`), así que ningún slider necesitó desactivarse.

### Parte C — Vocabulario canónico

Grep de `Gemelo Digital` en `app/`: sobreviven solo (1) el fallback interno de `render_view_selector()` en `main.py:353` (nunca alcanzado — los 6 llamadores vivos ahora pasan `views=` explícito), (2) una definición duplicada y muerta de `render_view_selector()` en `app/utils.py:477` (sombreada por la de `main.py`, inalcanzable, no tocada — fuera de alcance de esta tanda), y (3) comentarios/notas históricas. Cero pestañas reales seleccionables por un usuario muestran "Gemelo Digital".

Hallazgo no listado en el encargo original: `render_education_page()` (`app/main.py:1753`, Learning Hub → Education) llamaba a `render_view_selector()` **sin** `views=`, cayendo al fallback que sí incluía "Gemelo Digital" como opción radio seleccionable — sin ningún `elif` que la manejara (pestaña muda: solo mostraba el pie común "1. Datos/2. Interpretación/3. Educación", peor que un placeholder). Corregido pasando `views=['Clínica', 'Educativa', 'Investigación', 'IA', 'Simulación']` explícito, igual que el resto de módulos.

EMG Muscle Lab y Multisensor Fusion Lab confirmados sin cambios necesarios — ya usaban el vocabulario canónico completo (`Clínica/Educativa/Investigación/IA/Simulación`) sin "Gemelo Digital".

### Parte D — Deuda de señal de ECG (registrada, cero líneas de código tocadas)

Diagnosticada en la tanda anterior (Parte 0, solo lectura), documentada aquí como un arco futuro de mejora de señal con validación (más cercano a Capa 5 que a Capa 2 — no es trabajo de estructura de pestañas):

1. **`generate_demo_ecg_signal()` ignora `hr`** (`app/utils.py:243-285`): `hr_rad`/`qrs_component` se calculan pero nunca se suman a la señal final; las 3 ondas (P/QRS/T) usan `t % 1`, un ciclo fijo de 60bpm. `hr=40` y `hr=200` producen señales 99.4% correlacionadas.
2. **`estimate_ecg_heart_rate()` saturado en 220bpm** (`app/utils.py:202-214`): detector de máximos locales sin distancia mínima entre picos; cuenta las 3 sub-oscilaciones internas del QRS (`sin(6*pi*(t%1))`) como latidos separados. Persiste **incluso probado contra un generador ya corregido para respetar `hr`** — es un bug independiente del bug 1.
3. **Modelo del QRS incompatible con período variable**: la ondulación interna del QRS fue diseñada para un ciclo fijo de 1s; al escalar el período con `hr`, expone picos falsos que ambos detectores (el naive de ECG Monitor, el `find_peaks` de Multisensor) sobre-cuentan en proporción distinta. Confirmado empíricamente: tras una sustitución de período de prueba, el detector de Multisensor da HR **no monótono** (hr=40→101.6bpm, hr=72→97.1bpm — el más lento estima más alto). Arreglar de verdad exige rehacer la forma del QRS, no solo el período.

**Consecuencia viva documentada**: ECG Monitor muestra 220bpm fijo hoy en su métrica "Heart Rate" con la fuente "Demo (sintético)" — un dato incorrecto y visible, pero **no es fachada** (Art. I): el número está genuinamente roto, no está fingiendo un cálculo que no ocurre. Multisensor·Simulación ya tiene su HR deshabilitado con caption honesto (Ejecución 1, cierre).

**Lectura sobre el paliativo del 220-fijo (pregunta abierta, NO ejecutada, a decidir por el usuario)**: reparar solo el detector (`estimate_ecg_heart_rate`, bug 2) sin tocar el generador (bug 1) haría que el número dejara de estar en el techo de 220 pero probablemente devolvería un valor igual de falso — solo que menos obviamente roto, porque seguiría midiendo un ciclo fijo de 60bpm disfrazado de "Demo HR" ajustable. Un 220 fijo es sospechoso a primera vista (cualquiera que mueva el slider y vea el mismo número extremo entiende que algo no funciona); un número plausible-pero-fijo (p.ej. "61bpm" sin importar el slider) es más engañoso, no menos — se parece más a una fachada que a un bug. Mi lectura: marcar el HR como "no fiable" (mismo patrón de caption que ya se usó para desactivar HR/RR en Multisensor) es probablemente el paliativo más honesto si se quiere actuar antes del arco completo, precisamente porque evita ese riesgo de retroceso. Pero no es gratis: exige decidir qué hacer con el slider "Demo HR" en sí (¿deshabilitarlo también, como en Multisensor, o dejarlo arrastrable con el metric marcado "no fiable" al lado?) y toca un módulo (ECG Monitor) que no formaba parte del alcance de ninguna Ejecución hasta ahora. No se tocó nada — queda como decisión pendiente.

### Verificación

- AppTest módulo por módulo hasta el final del render, sin crash: ECG-12 (2 pestañas), EEG (1 pestaña), Respiratory (3 pestañas), Multisensor (5 vistas), EMG, HRV, Biomarkers, Digital Twin OS, ECG Monitor, Education — **10/10 `exception=[]`**.
- Respiratory·Investigación: AHI/severidad/eventos coinciden con los de Clínica en el mismo run (puente de sesión, no duplicación).
- Respiratory·Simulación: sliders verificados reactivos por ejecución (valores exactos arriba) — ninguno resultó placebo, ninguno se desactivó.
- ECG-12·Educativa: el puntero exacto a Academia Clinica aparece en el render — no hay lección fabricada.
- Vocabulario: grep sin ninguna pestaña "Gemelo Digital" reachable; los 6 `render_view_selector(views=...)` vivos usan solo el conjunto canónico.
- Deuda de señal: registrada arriba; releídas `app/utils.py` (líneas 243-285, 202-214) y `dashboards/multisensor.py` al cerrar esta tanda -- idénticas a como quedaron en la Ejecución 1, cero líneas de los 3 bugs tocadas (no es repo git, sin `git diff` disponible para esta verificación).
- `pytest tests/ -q`: **429 passed, 1 warning** (sklearn/LGBMClassifier, preexistente, ajeno) — sin regresión.
- Servidor real (`streamlit run app/main.py`, puerto 8552): HTTP 200; proceso detenido tras la verificación.

Con esto cierra la Fase 2.2 completa (Parte 0 diagnóstico → Ejecución 1 cableado Multisensor → Ejecución 1 cierre placebo → Ejecución 2 estructura de pestañas). La Fase 2.3/2.4 (integración UPS/gemelo real) sigue sin empezar.

## 2026-08-21 — Capa 2, Fase 2.2, Ejecución 1, cierre (R1): sliders HR/RR de Multisensor·Simulación deshabilitados — placebo cerrado con honestidad, no con fabricación

**Contexto**: el cableado del turno anterior dejó SpO2 moviendo el Health Score de verdad, pero HR y RR seguían siendo arrastrables sin mover el resultado — HR por un bug del generador de ECG (`generate_demo_ecg_signal()` ignora `hr`, función compartida con ECG Monitor, fuera de alcance) y RR por diseño (`health_score()` nunca consumió `respiration_rate`). Dos sliders que el usuario puede arrastrar sin que nada cambie son un control placebo, aunque el caption ya lo explicara — no cumplen la vara de honestidad de la campaña ("una pestaña hace lo que muestra, o no lo muestra"). Se cierran, no se fabrica el cálculo que les falta.

### Cambio (`app/main.py`, vista Simulación de `render_multisensor_page()`)

- `st.slider('HR', ..., disabled=True, help='Deshabilitado: pendiente de reparación del generador de señal ECG (próxima tanda) -- hoy no varía la forma de onda según el HR pedido.')`
- `st.slider('RR', ..., disabled=True, help='Deshabilitado: no incluido en el cálculo actual de Health Score (health_score() no usa respiration_rate).')`
- `SpO2` sin cambios: sigue activo (`disabled=False`), arrastrable, y sigue recalculando el Health Score en vivo.
- Ambos sliders deshabilitados quedan fijos en su valor por defecto (72bpm / 16rpm) pero siguen regenerando su canal para la vista de correlación de `render_discovery_lab` — solo se bloqueó el arrastre engañoso, no el cálculo subyacente que ya existía.
- Texto de la pestaña reescrito para describir exactamente lo que el usuario puede hacer: "SpO2 es el único control activo de esta pestaña" + explicación de por qué HR/RR quedan deshabilitados, en vez de una nota genérica de "ajusta los 3 sliders".

### Verificación (por ejecución, AppTest)

- `HR`: `disabled=True`. `SpO2`: `disabled=False`. `RR`: `disabled=True`.
- Reactividad de SpO2 confirmada tras el cierre — Health Score 96→80.7/100, 85→60.7/100 (Heart Rate se mantiene en 124bpm, sin cambio, como corresponde con HR fijo).
- Barrido de las 5 vistas de Multisensor (Clínica/Educativa/Investigación/IA/Simulación): sin excepciones.
- `pytest tests/ -q`: **429 passed, 1 warning** (warning preexistente de sklearn/LGBMClassifier, ajeno a esta tanda) — sin regresión.
- Servidor real (`streamlit run app/main.py`, puerto 8551): HTTP 200; proceso detenido tras la verificación.

Con esto cierra del todo la Ejecución 1 de la Fase 2.2: el cableado real quedó donde lo hay (SpO2), y donde no lo hay (HR/RR) el control se desactivó en vez de simular un efecto que no ocurre. La Ejecución 2 (retirar/renombrar pestañas per las decisiones LLENAR/RETIRAR de la Fase 2.2 Parte 0) sigue sin autorizar.

## 2026-08-20 — Capa 2, Fase 2.2, Ejecución 1/2: primera fachada VIVA de la campaña convertida en función real (Multisensor · Simulación, Art. I)

**Contexto**: el diagnóstico ejecutado de la Fase 2.2 (turno anterior) cazó algo distinto de los ~18 miembros dormidos retirados en la Capa 3: una fachada que el usuario **ve hoy**. Multisensor · Simulación mostraba 3 sliders (HR/SpO2/RR) con el texto "el sistema recalcula el Health Score en tiempo real" — pero `render_discovery_lab` corría sobre `demo_channels` sin modificar; ningún slider alimentaba ningún cálculo. El cálculo real (`MultisensoralRecord.compute_physiological_indices()`/`.health_score()`) ya existía y ya corría en Clínica/IA del mismo módulo. Esta tanda cablea los sliders a ese cálculo real, en vez de fabricar uno nuevo.

### Cableado (`app/main.py`)

- Nueva función compartida `_build_multisensor_record()` — antes Clínica e IA repetían la misma línea de construcción del `MultisensoralRecord` cada una por separado; ahora las tres vistas (Clínica, IA, Simulación) la reutilizan. Cero lógica de cálculo duplicada.
- Simulación regenera los 3 canales (`generate_demo_ecg_signal(hr=...)`, `generate_demo_spo2_signal(baseline=...)`, `generate_demo_respiration_signal(rr=...)` — mismos generadores que ya usa Clínica) y pasa por la misma ruta compartida hasta el Health Score mostrado.

### Dos bugs preexistentes encontrados y corregidos al verificar por ejecución (lección de Respiratory Lab: no confiar en la lectura)

Mover el slider de SpO2 al 100% inicial daba un Health Score inmóvil y un Heart Rate absurdo (~180bpm) sin importar el HR pedido. Investigado antes de asumir que el cableado estaba mal — **ambos bugs eran preexistentes en Clínica/IA**, nunca causados por este cableado, solo nunca verificados por ejecución hasta ahora:

- **SpO2 diluido a ~0.4%** (`dashboards/multisensor.py::MultisensoralRecord`): `BiosignalChannel` recibía `fs=250.0` fijo para todos los canales, pero `generate_demo_spo2_signal()` genera a 1Hz de verdad (`n_samples = int(duration)`). El desajuste hacía que `_validate_synchronization()` viera una "duración" de SpO2 ~250x más corta y la rellenara con ceros hasta igualar, diluyendo la media. **Corregido**: `_build_multisensor_record()` ahora pasa el `fs` real de cada canal (1.0 para SpO2, 250.0 para el resto).
- **Heart Rate congelado en ~178-180bpm** (`dashboards/multisensor.py::compute_physiological_indices()`): `find_peaks(ecg.signal, distance=...)` sin umbral de altura contaba máximos de ruido, no picos R. Verificado con `hr=72` y `hr=140`: mismos 60 picos, mismo HR estimado en ambos casos. **Corregido**: se añadió `height=mean+0.3*std`, mismo patrón que ya usa el resto del repo (`feature_extraction.py`, `ecg_interpreter.py`).
- Efecto colateral **positivo**, confirmado por ejecución: Clínica ahora muestra un Health Score realista (~80/100 con los valores por defecto) en vez del ~36/100 erróneo de antes — el bug afectaba a Clínica/IA desde siempre, esta tanda lo corrige de paso, no lo introduce.

### Tercer bug encontrado, reportado y explícitamente NO corregido en esta tanda (fuera de alcance, mayor blast radius)

`app/utils.py::generate_demo_ecg_signal()`: calcula `hr_rad`/`qrs_component` a partir del parámetro `hr`, pero esas variables **nunca se usan** — la forma de onda real (`p_wave`/`qrs_complex`/`t_wave`) depende de `t % 1`, un ciclo fijo de 1 segundo (60bpm), sin importar `hr`. Confirmado por ejecución: `generate_demo_ecg_signal(hr=40)` y `generate_demo_ecg_signal(hr=200)` correlacionan al 99.4% (misma señal, solo difiere el ruido aleatorio). Es una función compartida usada más allá de Multisensor (p.ej. el slider "Demo HR" de ECG Monitor) — arreglarla es una tanda propia, con su propia verificación en cada llamador. **No se tocó.** El slider HR de Simulación queda cableado (regenera el canal ECG, el Heart Rate mostrado se detecta de esa señal por picos R, no es un valor fijo) pero, hasta que este bug se corrija, mover el HR no cambia de forma fiable el Heart Rate detectado — el texto de la pestaña lo dice explícitamente, en vez de prometerlo.

### RR — limitación estructural, no un bug, ya documentada

`health_score()` nunca usó `respiration_rate` en su fórmula (solo `heart_rate`/`heart_rate_variability`/`spo2_mean`). RR sigue regenerando la señal respiratoria real (afecta la vista de correlación de `render_discovery_lab`), pero no puede mover el Health Score — el texto lo dice explícitamente, decisión tomada con el usuario antes de cablear nada.

### Texto corregido

"El sistema recalcula el Health Score en tiempo real" (falso para los 3 sliders) → nota que distingue con precisión los 3 casos: SpO2 recalcula de verdad, HR está cableado pero bloqueado por el bug del generador (reportado arriba), RR no puede mover el Health Score por diseño de `health_score()`.

### Verificación

- Prueba de reactividad real (AppTest): SpO2=96→Health Score 80.7; SpO2=85→60.7; SpO2=100→80.7 — el número se mueve de verdad, no es apariencia de interactividad.
- Clínica/IA confirmadas intactas y ahora con números correctos (antes erróneos): Health Score 80.3/100 con los valores por defecto (antes ~36); IA sigue mostrando el gate honesto de `ANTHROPIC_API_KEY` sin excepciones.
- Lógica de cálculo no duplicada: las 3 vistas usan `_build_multisensor_record()` + `compute_physiological_indices()`/`health_score()`, una sola ruta.
- Cero cambios estructurales: ninguna pestaña retirada, ningún nombre tocado (eso es la Ejecución 2, aparte).
- `AppTest` real sobre los 8 flujos vivos (ECG Lab, EEG Neuro Lab, Respiratory Lab, Multisensor Fusion Lab -- las 5 vistas --, EMG Muscle Lab, HRV Analysis, Biomarkers Lab, Digital Twin OS): sin excepciones.
- `pytest tests/ -q`: sin regresión (ver resultado exacto abajo).
- Compile-check limpio en `app/main.py`, `dashboards/multisensor.py`, `app/utils.py`.
- Servidor real (`streamlit run app/main.py`, puerto 8550): HTTP 200; proceso detenido tras la verificación.

**Nota de alcance**: esta es la única fachada VIVA hallada en toda la campaña de honestidad hasta ahora — los ~18 miembros de la familia retirados en la Capa 3 estaban todos dormidos (cero llamadores vivos). Esta era distinta: el usuario la ve y la usa hoy.

## 2026-08-20 — Capa 2, Fase 2.1, cierre: `render_sidebar_navigation()` + `set_page_config()` vestigiales retirados — nomenclatura 100% unificada, trampa de navegación rota eliminada

**Contexto**: al cerrar la Fase 2.1 apareció un 4º lugar con nomenclatura vieja: `render_sidebar_navigation()` (`app/utils.py`), un widget de sidebar con 13 enlaces `localhost:8501/...` — vestigio de la arquitectura Streamlit multipágina anterior — llamado en vivo desde 3 `page_content.py` (ECG-12, EEG Neuro Lab, Respiratory Lab), cada uno acompañado de su propio `st.set_page_config()` redundante (main.py ya configura la página una vez, al inicio). El diagnóstico (turno anterior) confirmó que no era redundancia inofensiva: los enlaces, al hacer clic, perdían el `session_state` del usuario y lo devolvían a la app en blanco — una trampa de UX activa. Decisión: retirar.

### Retirado

- `render_sidebar_navigation()` eliminada de `app/utils.py` (con nota explicando el porqué, no un borrado silencioso).
- Re-export huérfano limpiado en `app/supermodules/__init__.py` (la línea `render_sidebar_navigation = app_utils.render_sidebar_navigation` habría fallado con `AttributeError` de haberse dejado).
- Las 3 llamadas retiradas: `ecg_12/page_content.py:162`, `eeg_neuro_lab/page_content.py:136`, `respiratory_lab/page_content.py:59` — junto con sus bloques `try/except` de import (que en `eeg_neuro_lab/page_content.py` compartían el bloque con el import real de `export_lab_report`/`reporting`; se conservó ese import, simplificando el `try/except` a uno solo en vez de dos anidados).
- Comentario desactualizado corregido en `app/utils/__init__.py` (mencionaba `render_sidebar_navigation` como ejemplo del mecanismo de re-export legado; reemplazado por `render_view_selector`).

### `st.set_page_config()` — verificado antes de retirar, retirado en los 3

Confirmado por triple evidencia antes de tocar cada uno: (1) `app/main.py` llama `st.set_page_config()` una sola vez, al inicio del script, antes de cualquier ruteo a hub/página; (2) grep exhaustivo de los 3 nombres de archivo `page_content.py` en todo el repo (excluyendo `_archive/`) no encontró ningún importador/ejecutor fuera de su propio `pages.py` (vía `runpy.run_path()`, siempre disparado por `app/main.py`); (3) los scripts de lanzamiento (`RUN_BIOCORE.bat`, `run_local.ps1`) apuntan únicamente a `streamlit run app/main.py`. Los 3 solo corren anidados — nunca standalone. `st.set_page_config()` retirado en los 3, cada uno con una nota explicando que es redundante con el de `app/main.py`.

### Hallazgo durante la verificación (no anticipado) — bug pre-existente destapado, corregido con autorización explícita

Al verificar con AppTest, `ECG Lab` y `EEG Neuro Lab` quedaron limpios (0 errores), pero **`Respiratory Lab` mostró un error nuevo**: `"Error ejecutando página Respiratory original: There are multiple selectbox elements with the same auto-generated ID."` — investigado antes de seguir, no ignorado.

**Causa raíz, confirmada, no causada por este cambio**: `respiratory_lab/pages.py` tenía un `try: main() except...` a nivel de módulo (se ejecuta al importar) *además* de un `run()` que también llama a `main()` — doble ejecución de `render_views()` (y por tanto doble `runpy.run_path()` de `page_content.py`) en cada carga de página. Exactamente el mismo bug ya identificado y corregido en `ecg_12/pages.py` y `eeg_neuro_lab/pages.py` el **2026-07-03** (ambos tienen la nota "antes había también un `try: main()` a nivel de módulo... se eliminó") — pero esa corrección nunca se aplicó a `respiratory_lab/pages.py`. Antes de esta tanda, la Vista Clínica de Respiratory Lab **nunca renderizó contenido real**: el `st.set_page_config()` duplicado fallaba primero en ambas ejecuciones y ocultaba el síntoma real (IDs de widget duplicados, p.ej. el `st.sidebar.selectbox` del patrón respiratorio). Retirar el `set_page_config()` no causó el bug — solo dejó de enmascararlo.

Reportado al usuario antes de tocar nada fuera del alcance original; con autorización explícita, se aplicó el mismo arreglo de una línea ya validado dos veces: se retiró el `try: main()` de nivel de módulo en `respiratory_lab/pages.py`, dejando `run()` como único punto de entrada — igual que en `ecg_12`/`eeg_neuro_lab`/`twin_shell`/`academia`. Verificado: Respiratory Lab ahora renderiza con 0 errores y el selector de patrón respiratorio (antes inalcanzable) funciona.

### Verificación

- `AppTest` real sobre los 8 flujos vivos: ECG Lab, EEG Neuro Lab, Respiratory Lab, Multisensor Fusion Lab, EMG Muscle Lab, HRV Analysis, Biomarkers Lab, Digital Twin OS — los 8, sin excepciones ni `st.error`.
- Grep final: cero `localhost:8501` vivo (solo un comentario histórico); cero `"Multisensor"` sin "Fusion Lab" en nombre canónico de menú/header — los 4 lugares (ECG Lab, Biomarkers Lab, Multisensor Fusion Lab, y ahora este widget retirado) quedan unificados.
- `pytest tests/ -q`: 429 passed, sin regresión.
- Compile-check limpio en los 6 archivos tocados (`app/utils.py`, `app/utils/__init__.py`, `app/supermodules/__init__.py`, `ecg_12/page_content.py`, `eeg_neuro_lab/page_content.py`, `respiratory_lab/page_content.py`, `respiratory_lab/pages.py`).
- Servidor real (`streamlit run app/main.py`, puerto 8549): HTTP 200; proceso detenido tras la verificación.

**Cierra la Fase 2.1** (nomenclatura) de la Capa 2: los 4 lugares con nombre viejo/duplicado detectados en el reconocimiento (2.0) quedan resueltos.

## 2026-08-20 — Capa 2, Fase 2.1: `ecg_monitor/pages.py` enterrado + 2 joyas anotadas para 2.2 + 3 nombres unificados

**Contexto**: la Fase 2.0 (reconocimiento) encontró que `app/supermodules/ecg_monitor/pages.py` — con el patrón de 6 pestañas más completo y fiel de la plataforma, contenido real — está muerto: nadie llama a su `run()`/`main()`. Lo que el usuario ve en "ECG Lab → Monitoreo" es `render_ecg_monitor_page()`, una función distinta e inline en `app/main.py`. La Parte 0 (turno anterior) comparó ambas versiones capacidad por capacidad y confirmó que el muerto no depende de nada retirado en la Capa 3. Decisión tomada: enterrar, rescatando antes las 2 capacidades donde el muerto gana, como tareas documentadas para la Fase 2.2 (no fusionar ahora — se solapa con la reestructuración de pestañas). Nombres canónicos confirmados: **ECG Lab**, **Biomarkers Lab**, **Multisensor Fusion Lab**.

### Parte A.1 — 2 joyas rescatadas como especificación, tareas pendientes para la Fase 2.2

**Tarea 1 — Intervalos PR/QRS/QTc como métricas visibles.** Hoy `render_ecg_monitor_page()` (vivo) solo muestra Heart Rate; no muestra estos 3 intervalos en ningún lado. El muerto los mostraba así (`ecg_monitor/pages.py::render_ecg_analysis()`, ya enterrado):
```python
analyzer = ECGAnalyzer(fs=fs)
r_peaks = analyzer.detect_r_peaks(signal)
intervals = analyzer.measure_intervals(signal)   # {'PR_interval_ms', 'QRS_duration_ms', 'QTc_ms', ...}
col_hr, col_pr, col_qrs, col_qt = st.columns(4)
col_hr.metric("Frecuencia cardíaca", f"{hr:.0f}", "bpm")
col_pr.metric("Intervalo PR", f"{intervals.get('PR_interval_ms', 0):.0f}", "ms")
col_qrs.metric("Duración QRS", f"{intervals.get('QRS_duration_ms', 0):.0f}", "ms")
col_qt.metric("QTc", f"{intervals.get('QTc_ms', 0):.0f}", "ms")
```
Fuente real: `clinical.ecg_analyzer.ECGAnalyzer.measure_intervals()` (el analizador "ganador", per CLAUDE.md) — la misma clase que el vivo ya importa (`safe_import_ecg_modules()`). Para la Fase 2.2: replicar este bloque de 4 métricas en la Vista Clínica de `render_ecg_monitor_page()`, sobre la señal realmente cargada (cualquiera de las 6 fuentes vivas), no solo sobre demo.

**Tarea 2 — Simulación que regenera la señal de verdad.** Hoy la Vista Simulación del vivo solo describe cualitativamente ("Aumenta FC: reduce intervalo RR...") sin regenerar nada. El muerto sí regeneraba (`ecg_monitor/pages.py`, tab Simulación, ya enterrado):
```python
hr_multiplier = st.slider("Multiplicador de frecuencia cardíaca", 0.5, 2.0, 1.0)
base_hr = st.slider("FC base (bpm)", 40, 150, 72)
ectopy = st.slider("Tasa de ectopias (por minuto)", 0, 30, 0)
if st.button("Generar ECG simulado con parámetros"):
    adjusted_hr = base_hr * hr_multiplier
    sim = generate_demo_ecg_signal(fs=250, duration=15, hr=adjusted_hr)
    render_ecg_analysis(sim, 250, title=f"ECG simulado (FC={adjusted_hr:.0f} bpm)")
```
Mecanismo: `generate_demo_ecg_signal()` (ya usado por el vivo en otros puntos) parametrizado por la FC ajustada, vuelto a graficar con el mismo pipeline de análisis. `ectopy` (tasa de ectopias) estaba en los sliders del muerto pero **no se usaba** en la generación — sería un parámetro fantasma a resolver, no solo copiar, si se implementa en 2.2. Para la Fase 2.2: dar a los sliders de FC/PR/QRS/QT del vivo un botón que regenere y re-renderice una señal real, con el mismo cuidado de no dejar un parámetro sin efecto.

*(La 3ª capacidad del muerto, "Gemelo Digital" (`twin*1.0`, placeholder autoadmitido, sin conexión a `DigitalTwinOrganism`), no se rescata — el vivo ya la retiró deliberadamente el 2026-07-03 por el mismo motivo.)*

### Parte A.2 — `ecg_monitor/pages.py` enterrado

Grep de re-confirmación antes de tocar: `get_case_database()` (importada en `main.py:1143`) era la única función del archivo con llamador vivo — confirmado también por un diagnóstico previo ya registrado en este mismo CHANGELOG (entrada del 2026-08-11). `load_clinical_case()`, sibling de `get_case_database` en el mismo archivo, no tenía ningún llamador fuera del propio `main()` muerto — se enterró con el resto sin rescatar.

- `get_case_database()` **reubicada a `app/main.py`**, junto a los demás helpers de caso clínico ECG (`_ecg_get_ptbxl_records`, etc., sección `# ==================== OTHER PAGES ====================`) — menor acoplamiento que crear un módulo compartido nuevo para una sola función, y mantiene la convención ya existente de agrupar ahí los helpers de ECG. Import cruzado en `main.py:1143` reemplazado por llamada directa a la función local.
- `app/supermodules/ecg_monitor/` **eliminado completo** (`pages.py` + `__init__.py`) — a diferencia de `app/components/`, ningún código vivo importaba el paquete como namespace (`app.supermodules.ecg_monitor`), así que no hacía falta dejar una cáscara con nota; se enterró la carpeta entera. Nota adicional encontrada al leer `__init__.py`: su propio `run()` tenía un bug (`Path(__file__).resolve() / 'pages.py'` sobre un archivo, no un directorio) que habría fallado si alguna vez se hubiera ejecutado — confirma una vez más que nunca corrió en producción.
- `clinical/ptbxl_metadata.py`: docstring corregido — apuntaba a `ecg_monitor/pages.py` como "el loader vivo del ECG Monitor"; ya no es cierto desde el 2026-08-09 (el loader vivo real siempre fue `app/main.py::_ecg_get_ptbxl_records()`), solo el comentario no se había actualizado.

**Grep de cierre**: `app.supermodules.ecg_monitor` no se importa desde ningún flujo vivo (solo queda una referencia en `_archive/`). `get_case_database()` verificada funcionando desde su nueva ubicación (61 casos, idéntico a antes).

### Parte A.3 — 3 nombres unificados (menú = header)

Para cada uno, se verificó antes de tocar que el string viejo no fuera usado como clave de `session_state` ni de navegación — los 3 headers eran texto puramente decorativo (`st.markdown`), y el ruteo en `render_page_content()` empareja por substring (`"ECG Lab" in page`, `"Biomarkers" in page`, `"Multisensor" in page`), así que ningún cambio rompe la navegación.

- **ECG**: header `"🫀 Cardiovascular Intelligence Lab"` → `"🫀 ECG Lab"` (`app/main.py`, dentro de `render_ecg_monitor_page()`). El menú ya decía "ECG Lab".
- **Biomarkers**: header `"🧬 Biomarkers & Diagnostics Lab"` → `"🧬 Biomarkers Lab"` (`render_biomarkers_page()`). El "& Diagnostics" sobre-prometía tras retirar las fachadas diagnósticas en la Capa 3.
- **Multisensor**: menú `"🔗 Multisensor"` → `"🔗 Multisensor Fusion Lab"` (`HUBS["Clinical Hub"]`), para igualar al header (que ya decía "Multisensor Fusion Lab", y que el narrador IA del módulo ya usaba como nombre — `render_findings_narrator('Multisensor Fusion Lab', ...)`, sin tocar). También se actualizó la mención en el texto estático de Guides ("...ECG, Multisensor Fusion Lab y Respiratory Lab...").

**Hallazgo relacionado, no tocado (fuera de alcance)**: `app/utils.py::render_sidebar_navigation()` — un widget de navegación heredado de una arquitectura Streamlit multipágina anterior (enlaces `localhost:8501/PageName` que no corresponden a cómo rutea la app hoy, de un solo archivo con hub/página por `session_state`). Sigue en uso real desde `respiratory_lab/page_content.py`, `eeg_neuro_lab/page_content.py` y `ecg_12/page_content.py`, y todavía dice `"🔗 Multisensor"` (sin "Fusion Lab") en su lista de enlaces. No es una colisión de las 3 pedidas y arreglarla implica decidir el destino de todo el widget (¿enlaces rotos que se retiran, o se reconstruye la navegación?) — señalado para 2.2 o aparte, no se tocó.

**Grep de cierre**: `Cardiovascular Intelligence` y `Biomarkers & Diagnostics` ya no aparecen en ningún lugar de `app/`. `"🔗 Multisensor"` (sin sufijo) solo sobrevive en el widget heredado señalado arriba.

### Verificación

- `AppTest` real: ECG Lab, Multisensor Fusion Lab, Respiratory Lab, EEG Neuro Lab, EMG Muscle Lab, HRV Analysis, Biomarkers Lab — los 7, sin excepciones. Confirmado que el header de ECG Lab, Multisensor Fusion Lab y Biomarkers Lab coincide ahora con su nombre de menú.
- `pytest tests/ -q`: sin regresión (ver resultado exacto abajo).
- Compile-check limpio en `app/main.py` y `clinical/ptbxl_metadata.py`.
- Servidor real (`streamlit run app/main.py`, puerto 8548): HTTP 200; proceso detenido tras la verificación.

## 2026-08-20 — Bisturí Final, Capa 3: familia "diagnóstico/confianza fabricada" extinta en todo el repo (Art. I)

**Cierre de la Capa 3 de honestidad.** Dos censos exhaustivos (mismo día) mapearon 18 miembros de esta familia en todo el repo: 8 ya retirados en tandas previas (ECG, EEG ×3, EMG ×3, `generate_text_report`), 10 dormidos sin retirar. Este corte retira los 10 restantes, entierra el hub archivado del que colgaban todos, y corrige un registro previo que describió mal su propia auditoría. **Grep de cierre TOTAL: vacío** — cero código vivo con las firmas de la familia en todo el repo.

### Parte A — Los 10 miembros dormidos, cada uno re-confirmado muerto antes de tocarlo

| # | Ubicación | Fabricaba | Confirmación |
|---|---|---|---|
| 1 | `cardiology_ui.py::display_arrhythmia_detection(condition, ai_confidence)` | Array de confianzas hardcodeado por rama de `condition`; `ai_confidence` recibido, jamás leído | Solo `_archive/app/pages_legacy/specialties.py:141` |
| 2 | `cardiology_ui.py::display_cardiac_summary(patient_data, ai_results)` | `confidence` 0.87 (idéntico al de `generate_text_report`, ya retirado) + `arrhythmia_type`/`risk_30_days`/`alert_level`/`recommendation` vía `.get(key, etiqueta)` | Solo `_archive/...:166` |
| 3 | `cardiology_ui.py::display_cardiac_risk_assessment()` | `risk_scores` literal, **cero parámetros de entrada** | Solo `_archive/...:159` |
| 4 | `neurology_ui.py::display_sleep_stage_classification(sleep_stage, confidence)` | Array de confianzas hardcodeado por rama de `sleep_stage`; `confidence` recibido, jamás leído | Cero llamadores en todo el repo |
| 5 | `neurology_ui.py::display_brain_activity_heatmap(channel_bands)` | `np.random.uniform(10, 50, ...)` presentado como "Potencia (µV²)"; `channel_bands` recibido, jamás leído | Cero llamadores en todo el repo |
| 6 | `metabolism_ui.py::display_metabolic_summary(patient_data, ai_results)` | `metabolic_status`/`recommendation` vía `.get(key, 'Normal'/...)` | Cero llamadores en todo el repo |
| 7 | `respiratory_ui.py::display_respiratory_summary(patient_data, ai_results)` | `respiratory_pattern`/`recommendation` vía `.get(key, 'Normal'/...)` | Cero llamadores en todo el repo |
| 8 | `alerts_and_reports_ui.py::display_shap_explanation(ai_results)` | Gráfica SHAP completa con `factors` 100% hardcodeados; `ai_results` recibido, jamás leído | Cero llamadores en todo el repo |
| 9 | `alerts_and_reports_ui.py::display_alert_history(measurement_history, specialty)` | `np.random.randint(0,3,...)` presentado como "Historial de Alertas (30 días)" | Cero llamadores en todo el repo |
| 10 | `app/engines/causality_engine.py::CausalityEngine` (+ `CausalEvent`) completa | `CAUSAL_RULES`: confidencias hardcodeadas (0.75-0.95) por regla fija, renderizadas como "CONFIANZA: X%" en `find_root_cause`/`answer_why`/`answer_what_if`/`get_causal_summary` | Instanciada solo en `_archive/app/pages/15_🧬_Digital_Twin_Control.py`; el propio código vivo (`twin_shell/pages.py:1244`) ya documentaba desde el 2026-07-13 que quedó huérfana al reemplazarse por el narrador causal real |

### Decisión de clase-cáscara, por UI — evidencia de grep antes de decidir

Tras retirar el/los método(s) fachada de cada archivo, se re-grepeó cada método **restante** de la clase:

- **`CardiacUI`** (`cardiology_ui.py`): sus 4 métodos "reales" (`display_ecg_waveform`, `display_ecg_frequency_analysis`, `display_heart_rate_and_bp`, `display_hrv_analysis`) **también** tenían cero llamadores vivos — 3 solo en `_archive/`, uno (`display_ecg_frequency_analysis`) ni siquiera ahí. → **Cáscara completa. Archivo eliminado.**
- **`NeurologyUI`** (`neurology_ui.py`): sus 3 métodos restantes (`display_eeg_waveform`, `display_frequency_bands`, `display_sleep_quality_over_time`) también sin llamador vivo (2 solo en `_archive/`, uno en ningún sitio). → **Cáscara completa. Archivo eliminado.**
- **`MetabolismUI`** (`metabolism_ui.py`): sus 2 métodos restantes (`display_metabolic_profile`, `display_metabolic_risk_chart`) solo llamados desde `_archive/`. → **Cáscara completa. Archivo eliminado.**
- **`RespiratoryUI`** (`respiratory_ui.py`): sus 3 métodos restantes, mismo patrón (2 solo `_archive/`, uno en ningún sitio). → **Cáscara completa. Archivo eliminado.**
- **`AlertsUI` + `ReportGenerator`** (`alerts_and_reports_ui.py`): `display_alert_panel` y `display_report_preview` (los 2 métodos "reales" restantes) tenían cero llamadores en **todo** el repo, ni siquiera en `_archive/`. → **Ambas clases, cáscara completa. Archivo eliminado.**

**Consecuencia no anticipada explícitamente, pero correcta según la regla autorizada**: las 5 clases evaluadas resultaron cáscara completa — no solo la que tenía la fachada más obvia. `app/components/` queda como paquete vacío (`__init__.py` con `__all__ = []` y una nota explicando por qué), en vez de eliminarse como directorio: se conserva el namespace por si algo externo lo importa, sin dejar ninguna clase reactivable por accidente. `app/supermodules/__init__.py` se actualizó para dejar de re-exportar las 6 clases desaparecidas (conserva `generate_sample_patient`/`generate_measurement_history`/etc. y los helpers de `app.utils`, que siguen intactos — ver Parte B).

Limpieza de imports huérfanos, verificada por archivo antes de tocar: `streamlit`/`numpy`/`plotly` no se tocaron en ningún sitio donde algún método conservado los siguiera usando (no aplicó en ningún caso porque las 5 clases se eliminaron completas). `app/engines/__init__.py` perdió el bloque `try/except` de `CausalityEngine`/`CausalEvent`, con nota en el mismo estilo que ya usaba el archivo para otros motores retirados en 2026-07-01.

### Parte B — Raíz enterrada: `_archive/app/supermodules/specialties/`

Confirmado por grep antes de enterrar: **cero importadores vivos fuera de `_archive/`** para `app.supermodules.specialties.pages` (y para el módulo completo). Los únicos referenciadores eran dos archivos también dentro de `_archive/` (`app/pages_legacy/specialties.py`, `app/pages/specialties.py`) — ninguno de los dos se tocó (no fueron nombrados explícitamente; sus imports ya apuntaban a una ruta que no resolvía desde el árbol vivo). Carpeta `_archive/app/supermodules/specialties/` **eliminada completa**.

**`app/utils/data_generator.py` (`DataGenerator`) — NO eliminado, solo reportado.** Confirmado por grep: sus 7 funciones (`generate_sample_patient`, `generate_measurement_history`, `generate_ecg_signal`, `generate_eeg_signal`, `generate_emg_signal`, `generate_respiratory_signal`, `generate_metabolic_profile`) también tienen cero llamadores fuera de `_archive/` — es la mitad "honesta" del hub muerto (genera vitales sintéticos plausibles, nunca fabrica un diagnóstico). Sigue re-exportado en `app/utils/__init__.py` y `app/supermodules/__init__.py`. Se deja intacto para que el usuario decida su destino por separado, tal como se pidió.

### Parte C — Corrección al CHANGELOG

La entrada del 2026-08-19 "EEG Neuro Lab: barrido de cierre" afirmó que `display_sleep_stage_classification`/`display_brain_activity_heatmap` eran "métodos reales" que "no fabrican nada". Falso — ver Parte A, ítems 4 y 5. Se añadió una nota de corrección fechada, sin editar ni borrar el texto original, dejando el error trazable.

### Parte D — Confirmado intacto (no se tocó)

El sistema formal `Provenance`/`confidence` del UPS (`ups_bridge.py`, `academia/pages.py`, `twin_shell/pages.py`), el SHAP/LIME real (`src/interpretability.py`, ya etiquetado como heurística cuando corresponde), el narrador causal real (el que dejó huérfana a `CausalityEngine`), `simulation_engine.py` (simulación educativa por escenario, categoría distinta), `display_hrv_analysis()` (nombre engañoso sin dato fabricado, deuda menor ya anotada), y todo cálculo real de los módulos vivos (activación EMG, median frequency, band power EEG, PLV, motor hemodinámico, BBB, narradores IA).

### Verificación

- **Grep de cierre TOTAL**: ninguna firma de la familia (`get('confidence', 0.87)`, arrays de confianza hardcodeados, `get('pathology'/'seizure_risk'/'recovery_time', default-clínico)`, `np.random` como dato clínico, SHAP hardcodeado, `CausalityEngine`) aparece ya en código vivo en todo el repo — solo quedan el `Provenance` real del UPS y comentarios/CHANGELOG históricos, todos confirmados por grep explícito arriba.
- `AppTest` real sobre los 8 flujos vivos que dependían transitivamente de `app.components`/`app.engines`: ECG Lab, Multisensor, Respiratory Lab, EEG Neuro Lab, EMG Muscle Lab, HRV Analysis, Biomarkers Lab, Digital Twin OS — los 8, sin excepciones.
- `pytest tests/ -q`: 429 passed, sin regresión.
- Compile-check limpio en `app/components/__init__.py`, `app/supermodules/__init__.py`, `app/engines/__init__.py`, `domain/physiology/narrator/causal.py`.
- Servidor real (`streamlit run app/main.py`, puerto 8547): HTTP 200; proceso detenido tras la verificación.

**Balance final de la Capa 3**: 18 miembros mapeados en dos censos exhaustivos → 18 retirados (8 en tandas previas + 10 en este corte) → **0 restantes, 0 alguna vez vivos.** Origen (`_archive/specialties/`) enterrado. Familia extinta.

## 2026-08-20 — Cierre EMG: cáscara `MusculoskeletalUI` eliminada + 5º miembro de la familia "diagnóstico fabricado" retirado (Art. I)

**Contexto**: cierre de los dos cabos que dejó el barrido de honestidad del EMG (entrada anterior en este documento). (1) Tras retirar sus 3 fachadas, `MusculoskeletalUI` quedó confirmada como cáscara -- sus 4 visualizadores restantes tampoco tenían llamador vivo. (2) Apareció un 5º miembro de la familia, el más severo en contenido: `ReportGenerator.generate_text_report()`, un "reporte médico" con `confidence` inventado -- el mismo confidence fantasma cazado primero en el clasificador de arritmias del ECG (2026-08-06), reaparecido en forma de reporte completo.

### Parte A — `MusculoskeletalUI` eliminada por completo

Re-confirmado por grep antes de tocar: la clase y sus 4 visualizadores restantes (`display_emg_raw_and_envelope`, `display_fatigue_analysis`, `display_activation_level_gauge`, `display_bilateral_comparison`) aparecían solo en su propia definición, en `__all__` de `app/components/__init__.py`/`app/supermodules/__init__.py`, y en un archivo `_archive/` -- cero llamadores vivos en los 4.

- `app/components/musculoskeletal_ui.py` **eliminado del repo** (el archivo entero, no solo la clase -- tras quitar las 3 fachadas ya retiradas ayer, no quedaba nada más que los 4 visualizadores sin consumidor).
- `MusculoskeletalUI` retirado de ambos `__all__` y de sus imports (`app/components/__init__.py`, `app/supermodules/__init__.py`), con nota explicando por qué.
- Verificado por import real: `app.components`/`app.supermodules` siguen cargando sin error, sin `MusculoskeletalUI`.

### Parte B — `ReportGenerator.generate_text_report()` retirado (solo este método)

Confirmado por grep antes de tocar: aparecía solo en su definición -- cero llamadores vivos en todo el repo.

Generaba un "REPORTE MÉDICO AUTOMATIZADO - BIOCORE AI" completo para 5 especialidades (Cardiología, Neurología, Musculoesquelético, Respiratorio, Metabolismo), con `ai_results.get('confidence', 0.87)` como "Confianza del modelo" fabricada, más `'shap_explanation'`, `'30_day_prediction'`, `'risk_30_days'`, `'seizure_risk'`, `'pathology'` y más defaults silenciosos por especialidad -- incluía incluso datos de contacto de emergencia inventados. Es el hallazgo más severo en contenido de toda esta serie de auditorías.

**Alcance respetado estrictamente**: solo se retiró este método. `ReportGenerator.display_report_preview()`, la clase `AlertsUI`, y el resto de `alerts_and_reports_ui.py` **no se tocaron** -- quedan para una auditoría aparte, no autorizada esta tanda. `timedelta` (import) queda sin uso en el archivo, pero **no se tocó**: no era consumido por `generate_text_report()` (confirmado leyendo el método completo antes de borrarlo), así que es un import huérfano preexistente, no causado por esta retirada -- mismo criterio aplicado en las tandas de `neurology_ui.py`/`musculoskeletal_ui.py`.

### Verificación

- Grep de cierre de la familia completa (`seizure_risk|pathology|recovery_time|display_pathology_classification|display_musculoskeletal_summary|display_recovery_projection|display_seizure_risk|display_neurology_summary|generate_text_report`) en `app/`: únicas coincidencias son comentarios históricos explicando qué se retiró -- cero código vivo.
- `AppTest` real: EMG Muscle Lab y Multisensor (que sí usa `render_discovery_lab` con 2+ señales), sin excepciones.
- `pytest tests/ -q`: sin regresión (ver resultado exacto abajo).
- Servidor real (`streamlit run app/main.py`, puerto 8547): HTTP 200; proceso detenido tras la verificación.

### Hallazgo nuevo, no tocado -- la pregunta de cierre reveló un 6º miembro

Al verificar "¿queda `confidence` hardcodeado en algún reporte del repo?", la respuesta honesta es **no del todo**: `app/components/cardiology_ui.py:485` tiene el mismo `ai_results.get('confidence', 0.87)*100:.1f}%`, dentro de la clase `CardiacUI`. Confirmado por grep: mismo estado que los 5 anteriores -- cero llamadores vivos (solo `__all__`/`_archive/`). No estaba en el alcance de esta tanda (no fue nombrado) -- no se tocó una línea. Señalado para la próxima auditoría.

## 2026-08-19 — EMG Muscle Lab: barrido de honestidad — 3 fachadas diagnósticas dormidas + 2 widgets decorativos retirados (Art. I)

**Contexto**: la auditoría del EMG confirmó que la ruta viva (`app/main.py::render_emg_page()`) es honesta -- activación real y reactiva, median frequency Welch estándar, narrador IA con datos genuinos. El riesgo estaba en `app/components/musculoskeletal_ui.py` (clase `MusculoskeletalUI`), dormida -- mismo patrón que `neurology_ui.py` antes de esa tanda -- y en dos widgets decorativos del módulo vivo.

### Parte A — 3 fachadas retiradas de `musculoskeletal_ui.py` (confirmadas muertas antes de tocarlas)

Grep de cada nombre en todo el repo, antes de retirar: las tres aparecían solo en su propia definición -- cero llamadores vivos, ninguna entrada en `__all__` por nombre propio.

- **`display_pathology_classification(emg_signal, classification="Normal")` -- la fachada más grave del EMG.** Recibía `emg_signal` y nunca lo leía; ramaba solo sobre el string `classification` y fabricaba "confianzas de modelo" hardcodeadas (0.95/0.02/0.02/0.01, etc.) para 4 categorías de patología neuromuscular real (Miopatía, Neuropatía, Enfermedad de Neurona Motora). Bug adicional que probaba que nunca se ejecutó de verdad: la lista de patologías estaba en español pero los `elif` comparaban contra inglés ("Myopathy"/"Neuropathy") -- nunca coincidían.
- **`display_musculoskeletal_summary(patient_data, ai_results)` -- cuarto miembro de la familia "diagnóstico fabricado"** (junto a `display_seizure_risk`/`display_neurology_summary` del EEG): `ai_results.get('pathology', 'Normal')`, `.get('recovery_time', '2-4 semanas')`, `.get('recommendation', 'Rehabilitación estándar')` -- defaults silenciosos fingiendo diagnóstico y pronóstico.
- **`display_recovery_projection(injury_type="Strain", initial_strength=40)`** -- heurística de plantilla poblacional que ignoraba por completo su parámetro `initial_strength` (recibido, nunca usado en la fórmula) -- antipatrón de parámetro fantasma silencioso.

Limpieza consecuente: `import streamlit as st` retirado (huérfano tras quitar el único `st.dataframe` del archivo, en `display_musculoskeletal_summary`); docstring del módulo actualizado (se quitaron "Detección de patología" y "Proyección de recuperación" de la lista de estructura). `plotly.express`/`scipy.fft`/`scipy.signal.hilbert` **no se tocaron** -- ya estaban sin uso antes de esta tanda, no lo causó esta retirada (mismo criterio aplicado a `neurology_ui.py`).

**Decisión sobre la clase `MusculoskeletalUI`**: se conserva, y se conserva en ambos `__all__` (`app/components/__init__.py`, `app/supermodules/__init__.py`). Retiene 4 visualizadores puros -- `display_emg_raw_and_envelope`, `display_fatigue_analysis`, `display_activation_level_gauge`, `display_bilateral_comparison` -- que grafican lo que se les pase, no fabrican nada por sí mismos. **Hallazgo reportado, no ejecutado**: grep confirma que estos 4 también tienen cero llamadores vivos en todo el repo -- la clase completa es hoy una cáscara sin ningún consumidor real. No se retiró por iniciativa propia; queda pendiente de decisión del usuario.

### Parte B — 2 widgets decorativos retirados de `render_emg_page()` (Vista Simulación)

- Slider "Fuerza simulada (%)": se definía y nunca se volvía a leer -- no influía en `signal` ni en ningún cálculo. Placebo de interacción.
- `render_discovery_lab('EMG Gemelo', {'EMG': signal})`: inalcanzable por diseño -- esa función exige >=2 señales para calcular una matriz de correlación, EMG solo pasaba 1, así que siempre caía en "Se requieren al menos 2 señales" sin hacer nada. `render_discovery_lab()` en sí **no se tocó** -- confirmado en uso real en Multisensor (`app/main.py:1542`, con 2+ señales).

Ajuste mínimo para no dejar la vista vacía: se añadió `st.line_chart(signal)` -- muestra el EMG actualmente simulado, sin ningún cálculo ni afirmación nueva.

### Parte C — confirmado intacto (no se tocó)

- Activación muscular, `compute_emg_median_frequency()`, narrador IA, textos educativos: sin cambios, valores idénticos a la auditoría (variación solo por el ruido gaussiano sin semilla fija, esperado).
- `compute_emg_fatigue_index()` **explícitamente fuera de alcance**: sigue clavado en 0.00 para los 3 patrones porque el generador produce espectro plano (ruido blanco) y la fórmula asume un basal de 120Hz que el generador nunca produce. No es fachada (reaccionaría con un espectro real) pero es prácticamente no-informativo hoy. Recalibración (o arreglar el generador para que "Fatiga" produzca corrimiento espectral real) queda anotada como mejora aparte, no ejecutada.
- El generador `generate_demo_emg_signal()` -- no se tocó.

### Hallazgo nuevo, no tocado (fuera de alcance de esta tanda)

Grep de cierre encontró un **quinto y mayor** miembro de la familia "diagnóstico fabricado": `app/components/alerts_and_reports_ui.py::ReportGenerator.generate_text_report()` -- un generador de "REPORTE MÉDICO AUTOMATIZADO - BIOCORE AI" que cubre 5 especialidades (Cardiología, Neurología, Musculoesquelético, Respiratorio, +1) con el mismo patrón `ai_results.get(clave, default_plausible)` en cada una -- incluye `'seizure_risk'`, `'pathology'`, y además `'arrhythmia_type'`, `'confidence'` (con default 0.87 = "87% de confianza IA" fabricado), `'risk_classification'`. Confirmado por grep: mismo estado que los anteriores -- cero llamadores vivos, solo en `__all__`/`_archive/`. Es el hallazgo más severo en contenido de toda esta serie de auditorías (título explícito de reporte médico oficial con predicciones e "IA" fabricadas en 5 especialidades) aunque dormido igual que los demás. Señalado para una auditoría/decisión aparte -- no se tocó una línea.

### Verificación

- Grep de cierre: `seizure_risk|pathology|recovery_time` en `musculoskeletal_ui.py` -- solo comentarios históricos explicando qué se retiró. Cero afirmaciones de clasificación de patología o diagnóstico fabricado en flujo vivo.
- `AppTest` real: Vista por defecto y Vista Simulación de EMG Muscle Lab, sin excepciones.
- Activación/median frequency/narrador re-ejecutados tras el cambio: mismo comportamiento que la auditoría original.
- `pytest tests/ -q`: sin regresión (ver resultado exacto abajo).
- Compile-check limpio en `app/main.py` y `app/components/musculoskeletal_ui.py`.
- Servidor real (`streamlit run app/main.py`, puerto 8546): HTTP 200; proceso detenido tras la verificación.

## 2026-08-19 — EEG Neuro Lab: barrido de cierre — tercer gemelo `display_neurology_summary()` retirado (Art. I)

**Contexto**: cierre de la tanda de honestidad del EEG Neuro Lab. Tras retirar la fachada de espigas/crisis y el gemelo muerto `display_seizure_risk()` (misma fecha, entrada siguiente en este documento), quedaba un tercer miembro de la misma familia: `NeurologyUI.display_neurology_summary()`, cuya tabla resumen leía `ai_results.get('seizure_risk', 'Bajo')` — un default silencioso que finge un riesgo de crisis que ningún llamador real calculaba, exactamente el mismo patrón de fachada diagnóstica.

### Confirmación de código muerto (antes de tocar nada)

Grep de `display_neurology_summary` en todo el repo: solo su propia definición en `neurology_ui.py` — cero llamadores vivos, ninguna entrada en `__all__` de `neurology_ui.py` ni de `app/components/__init__.py` (ambos exportaban la clase `NeurologyUI` completa, nunca el método por nombre). Confirmado seguro de retirar.

### Cambios (`app/components/neurology_ui.py`)

- `display_neurology_summary()` eliminado por completo, con nota explicando el patrón fachada retirado (mismo estilo que `display_seizure_risk()`).
- `NeurologyUI` **se mantiene** en ambos `__all__` — conserva otros métodos reales (`display_eeg_waveform`, `display_frequency_bands`, `display_sleep_stage_classification`, `display_brain_activity_heatmap`, `display_sleep_quality_over_time`). Se retira el método podrido, no la clase — mismo criterio que la tanda anterior.
- Import `streamlit as st` retirado: quedó huérfano tras la retirada (era el único consumidor de `st.dataframe` en todo el archivo, confirmado por grep antes de tocarlo).
- Docstring del módulo: se quitó "4. Détección de epilepsia" de la lista de estructura — ya no corresponde a nada real en el archivo (las dos funciones que tocaban ese tema están retiradas).
- **No tocado, fuera de alcance**: `fft`/`fftfreq` (scipy) y `plotly.express as px` también están sin uso en el archivo, pero ese estado es anterior a esta tanda (no lo causó esta retirada) — no se limpiaron, señalado para una pasada de limpieza aparte si se decide.

### Grep de cierre — familia completa

`seizure_risk|espiga|spike|crisis|paroxíst|seizure` en `neurology_ui.py` y en `eeg_neuro_lab/`: las únicas coincidencias son comentarios históricos (explicando qué se retiró y cuándo) y las tres menciones ya confirmadas honestas en la auditoría previa — etiqueta del selector de patrón ("Seizure (espigas)"), viñeta educativa general, y pregunta de quiz sobre "crisis epiléptica simulada". Ninguna afirma un hallazgo sobre la señal del usuario. La familia "riesgo de crisis fabricado" queda completamente cerrada.

### Verificación

- `pytest tests/ -q`: sin regresión (ver resultado exacto abajo).
- Compile-check limpio en `neurology_ui.py`; `NeurologyUI` sigue siendo importable con sus métodos reales intactos.
- Servidor real (`streamlit run app/main.py`, puerto 8545): HTTP 200; proceso detenido tras la verificación.

> **CORRECCIÓN (2026-08-19, añadida en la tanda "Bisturí Final — Capa 3", sin editar el texto original de arriba):** la línea 87 de esta entrada afirmó que `display_sleep_stage_classification` y `display_brain_activity_heatmap` eran "métodos reales" que "no fabrican nada por sí mismos". **Es falso.** El censo total de la familia "diagnóstico/confianza fabricada" (mismo día, tandas posteriores) leyó ambos métodos completos, no solo su firma, y encontró: `display_sleep_stage_classification(sleep_stage, confidence)` fabrica un array de "confianzas de modelo" hardcodeado por rama de `sleep_stage`, ignorando por completo el parámetro `confidence` recibido; `display_brain_activity_heatmap(channel_bands)` genera `np.random.uniform(10, 50, ...)` como si fuera potencia EEG medida, ignorando por completo el parámetro `channel_bands` recibido. Ambos eran miembros no detectados de la misma familia que esta entrada acababa de limpiar parcialmente. Un registro de honestidad que describe mal su propia auditoría es su propia forma de fachada — se deja esta nota en vez de reescribir el texto original, para que el error quede trazable. Ambos métodos, junto con el resto de `NeurologyUI` (confirmada cáscara completa), se retiraron en la tanda "Bisturí Final — Capa 3" (ver entrada correspondiente más abajo).

## 2026-08-19 — EEG Neuro Lab: fachada diagnóstica de espigas/crisis eliminada (Art. I — la más grave del framework)

**Contexto**: la auditoría de honestidad del EEG Neuro Lab confirmó que la frase *"La detección de espigas sugiere actividad paroxística compatible con crisis"* (`page_content.py:440-444`) era texto incondicional sin ningún detector detrás — ni umbral de amplitud, ni morfología, ni template matching en `eeg_analyzer.py`. Se imprimía siempre, para cualquier patrón, incluso cuando el patrón "Seizure (espigas)" (que sí inyecta espigas sintéticas reales vía `_seizure_spikes()`) se clasificaba como "Sueño ligero / Somnolencia" — la frase no reaccionaba a la señal en absoluto. Es una afirmación diagnóstica de epilepsia sin sustento: la fachada más grave encontrada hasta ahora en la plataforma.

### Parte A — Retiro de la frase (`app/supermodules/eeg_neuro_lab/page_content.py`)

Se retiró solo la segunda frase del bloque "Interpretación Clínica"; se conservó la primera, que es honesta y describe lo que el sistema realmente hace:
```
"Este laboratorio simula ondas EEG típicas y las clasifica en patrones de alerta, relajación y sueño."
```
Grep exhaustivo por `espiga|spike|crisis|paroxíst|seizure` en el módulo tras el retiro: las únicas menciones restantes son (a) la etiqueta del selector de patrón "Seizure (espigas)" (elegir qué señal simular, no una afirmación de detección), (b) una viñeta educativa general en "Cómo interpretar EEG" (mismo registro que las otras 3 viñetas de la lista, no liga a un hallazgo del análisis actual), y (c) una pregunta de quiz educativo explícitamente sobre "crisis epiléptica **simulada**" — ninguna afirma que el sistema haya detectado algo en la señal actual. También se corrigió el docstring del módulo ("Seizure and artifact pattern recognition" → "... pattern generation (synthetic; no detection algorithm)") — no es texto de UI, pero describía una capacidad de detección que nunca existió.

### Parte B — Gemelo muerto retirado (`app/components/neurology_ui.py`)

`NeurologyUI.display_seizure_risk()` generaba una curva de "riesgo de crisis epiléptica en 24h" a partir de `risk_score + sin(hours/4)*0.2 + ruido_gaussiano` — ruido disfrazado de pronóstico clínico. Confirmado por grep exhaustivo **antes** de retirarlo: cero llamadores vivos, solo aparecía en `__all__` de `neurology_ui.py`/`app/components/__init__.py` (que exportan la clase `NeurologyUI` completa, no el método por nombre) y en dos archivos `_archive/` ya muertos. Se retiró el método completo, dejando una nota explicando por qué; la clase `NeurologyUI` **se mantiene** en `__all__` de ambos `__init__.py` porque conserva otros métodos reales (p.ej. `display_brain_activity_heatmap`) — no había nada que quitar de esos `__all__` más allá del método en sí, que nunca se exportó por nombre propio. `numpy` sigue en uso por otros métodos del archivo — sin imports huérfanos.

**Hallazgo adicional, no tocado (fuera del alcance de esta tanda)**: `NeurologyUI.display_neurology_summary()`, en el mismo archivo, también lee `ai_results.get('seizure_risk', 'Bajo')` para una tabla de "Riesgo de Crisis" — confirmado igualmente sin ningún llamador vivo en todo el repo (mismo patrón de gemelo muerto). No estaba en el alcance de esta tanda (el usuario autorizó retirar `display_seizure_risk()` específicamente) — queda señalado para una decisión aparte.

### Parte C — Confirmado intacto

- **Band power (Welch)**: sin tocar `eeg_analyzer.py`/`eeg_generator.py`. Re-ejecutado tras el cambio: mismo patrón de reactividad por tipo de señal que en la auditoría original (alpha→alpha dominante ~320, beta→beta dominante ~184, etc.).
- **Clasificación de estado**: `_classify_pattern()` intacta, sin cambios -- sigue siendo la misma heurística razonable (argmax de banda), su fragilidad ante artefactos queda señalada pero no se toca en esta tanda.
- **"Hallazgos clínicos EEG" y "Exportar informe EEG"**: sin tocar. El informe exportado nunca heredó la fachada (vivía solo en el `st.write` de pantalla, no en `overall.findings`) — se confirma que sigue así.

### Verificación

- `AppTest` real sobre `render` de EEG Neuro Lab: sin excepciones; confirma que la frase "detección de espigas sugiere ... compatible con crisis" ya no aparece, y que la frase honesta ("simula ondas EEG típicas y las clasifica...") sigue presente.
- Grep final en el módulo: cero afirmaciones de detección de crisis/espigas sobre la señal actual.
- `pytest tests/ -q`: sin regresión (ver resultado exacto abajo).
- Compile-check limpio en `page_content.py`, `neurology_ui.py`, `app/components/__init__.py`.
- Servidor real (`streamlit run app/main.py`, puerto 8544): HTTP 200; proceso detenido tras la verificación.

## 2026-08-19 — Biomarkers Lab: NeuroCardiac Coupling pseudocientífico retirado, reemplazado por PLV real (Fase 2)

**Dictamen del validador (verbatim)**: PLV (Phase-Locking Value) entre la fase de **Theta Frontomedial (4-8Hz)** del EEG y la fase de la **banda HF-HRV (0.15-0.40Hz)** del tacograma R-R, con un mínimo de **180s de señal simultánea**. Corrige el diseño inicial de Fase 1 (que proponía alfa + R-R crudo) — ver la auditoría de viabilidad y el diseño de arquitectura previos en este mismo documento.

**Contexto**: `calculate_neurocardiac_coupling_score()` sumaba potencias absolutas de alfa EEG + potencia HF + un `signal_coherence` sin definición algorítmica — el validador calificó la fórmula **entera** (no solo el placeholder) de pseudocientífica. Se retira por completo y se reemplaza por un PLV real. Como el pipeline hoy no persiste ECG+EEG crudos simultáneos (ni existe un reloj de captura común entre labs — ver diseño de Fase 1), el PLV **casi siempre degradará a "no disponible"** — eso es el comportamiento honesto esperado, no un bug.

### Parte A — Retiro

- `calculate_neurocardiac_coupling_score()` eliminado por completo de `biomarkers.py` (no solo `signal_coherence`).
- `'NeuroCardiac Coupling Score'` sale del dict de `get_full_biomarker_suite()`; su lugar lo toma `'NeuroCardiac PLV'`.
- Inputs huérfanos: `signal_coherence` (era 100% placeholder, ahora sin ningún consumidor) y `hrv_hf_power` (era real/derivable pero el PLV no lo usa — usa señal cruda, no un escalar de potencia). Ambos se dejan en los 4 presets y en el modo manual **sin efecto**, anotados inline (`app/main.py`) — mismo tratamiento que los fantasmas anteriores. `eeg_alpha_power` NO quedó huérfano — lo sigue usando Cognitive Load Score.

### Parte B — El cálculo (`BiocoreEngine.calculate_neurocardiac_plv()`)

1. **Theta frontomedial**: bandpass Butterworth fase-cero (`butter`+`filtfilt`, orden 4, 4-8Hz) sobre la señal EEG cruda → `scipy.signal.hilbert` → fase instantánea.
2. **HF-HRV**: tacograma R-R (`rr_intervals_s`, `rr_timestamps_s`) interpolado a rejilla uniforme 4Hz (mismo patrón que `render_hrv_page()`/`advanced_hrv.py`) → bandpass 0.15-0.40Hz → Hilbert → fase instantánea.
3. **Alineación**: ambas fases se recortan a la ventana de solape real (`min(fin_eeg, fin_rr) - max(inicio_eeg, inicio_rr)`) y se remuestrean a la misma rejilla de 4Hz — la fase EEG se interpola sobre la señal analítica completa (parte real+imaginaria), no sobre la fase cruda, para evitar artefactos de wraparound.
4. **PLV**: núcleo aislado en `_plv_from_phases(phase_a, phase_b) = |mean(exp(i·(phase_a - phase_b)))|` — extraído como método estático propio para poder verificarse con fases sintéticas independientemente del filtrado/interpolación (Parte D).

### Parte C — Degradación honesta (`PLVResult`, `dataclass(frozen=True)`)

`available: bool`, `value: Optional[float]`, `reason: Optional[str]`, `duration_s: Optional[float]`. Cuatro guards, en orden, cada uno devuelve `available=False` con motivo — **nunca un número por defecto** (ese patrón, `raw_metrics.get(key, valor)`, fue el origen exacto de los 3 fantasmas retirados el 2026-08-15; no se repite aquí):

1. **Disponibilidad**: si falta cualquiera de las 4 señales crudas → `"requiere señal ECG+EEG en vivo simultánea"`.
2. **Duración**: si la ventana de solape < 180s → `"señal insuficiente: se requieren >=180s ..., hay Xs"`, con `duration_s` medido.
3. **Anti-bucle**: `_looks_looped()` divide la señal EEG en 4 tramos y rechaza si dos tramos no adyacentes correlacionan >0.995 (advertencia del validador: una señal repetida en bucle da PLV~1.0 artefactual).
4. **Ventana insuficiente tras alinear**: defensivo, por si el recorte a la rejilla común deja menos de 8 muestras.

**Cascada a Learning Readiness Index**: dependía del viejo `coupling` (0-100). Ahora, si el PLV está disponible, se usa `plv_result.value*100` como su componente; si no, Learning Readiness Index **también** se marca `available=False` — no se renormalizó para forzar un número sin ese componente (decisión de fórmula que le corresponde al usuario, mismo criterio que `metabolic_efficiency`/Stress Index el 2026-08-15).

**UI** (`app/main.py`): cuando `available=False`, el slot de la grilla muestra `"🟣 Métrica deshabilitada: el PLV requiere ≥180s de señal ECG+EEG simultánea. Muestra actual: Xs."` (mismo patrón atenuado que Autonomic Stability) en vez de un `st.metric`. Nuevo badge `BIOMARKER_METHOD_BADGE = "🟣"` — distinto de 🟢 (cita un rango) porque el PLV, si el validador confirma su implementación futura con datos reales, cita un **método** (Phase-Locking Value / acoplamiento neurovisceral), no un número.

### Parte D — Verificación matemática (`tests/test_biomarkers_plv.py`, 15 tests nuevos)

Con fases sintéticas de respuesta conocida, sobre `_plv_from_phases()` aislado del pipeline:
- Fases idénticas → PLV = 1.0 (exacto).
- Fases aleatorias independientes → PLV < 0.05.
- Desfase **constante** distinto de cero → PLV = 1.0 (confirma que el PLV mide constancia del desfase, no que sea cero).
- Desfase que deriva con el tiempo → PLV intermedio, menor que el caso de offset fijo.

Más guards end-to-end: sin señal → no disponible; señal parcial → no disponible; <180s → rechazado con `duration_s` medido; señal en bucle → rechazada; ≥180s sin bucle → corre sin excepciones, `available=True`, PLV∈[0,1]. Más regresión: el método viejo ya no existe (`hasattr` False), los otros 5 scores no cambiaron sus valores exactos sobre el preset Basal (22.22/50.22/5.67/27.42), `'Autonomic Stability Score'` sigue fuera del dict, y `get_full_biomarker_suite()` sí activa el PLV cuando se le pasan señales suficientes (confirma el cableado end-to-end).

### Verificación

- `pytest tests/ -q`: 429 passed (414 previos + 15 nuevos), sin regresión.
- `AppTest` real sobre `render_biomarkers_page()`: sin excepciones; confirma en vivo que hoy el panel muestra "🟣 Métrica deshabilitada... Muestra actual: 0s." y "🔵 Métrica deshabilitada: depende del PLV neurocardíaco..." — no un número, exactamente el comportamiento esperado dado que Biomarkers Lab no tiene acceso a señal ECG+EEG cruda hoy.
- Compile-check limpio en `app/main.py` y `app/supermodules/biomarkers.py`.
- Servidor real (`streamlit run app/main.py`, puerto 8543): HTTP 200; proceso detenido tras la verificación.

## 2026-08-15 — Biomarkers Lab: Autonomic Stability Score retirado de la grilla (0/2 inputs reales)

**Contexto**: verificación read-only confirmó que `bp_variance` y `ppg_pulse_transit_time_var` no tienen ninguna fuente de señal real en el repo — no hay generador de presión arterial en `src/signals/`, y el módulo PPG existente (`src/signals/ppg/preprocessing.py`) solo filtra la señal, no calcula pulse transit time. Grep exhaustivo: ambos aparecen únicamente como constantes fijas (4.5 y 11.2) en `app/main.py`, nunca varían, y ningún otro score los usa. A diferencia de `metabolic_efficiency` (1 fantasma entre 2 reales) o Stress Index (recortable a LF/HF), aquí **0 de 2** inputs son reales — no hay nada que recortar ni preservar, y no hay reemplazo algorítmico identificado (a diferencia de NeuroCardiac→PLV). Decisión del usuario: retirar de la UI, reemplazar por un estado honesto.

### Cambios

- **`app/supermodules/biomarkers.py`**: `get_full_biomarker_suite()` deja de llamar `calculate_autonomic_stability_score()` — ya no se computa ni se incluye en el dict devuelto (6 claves en vez de 7). El método en sí **no se borró** — queda latente en la clase, con docstring explicando por qué no se llama y bajo qué condición se reactivaría (instrumentación real de PA/PPG-PTT). Sigue siendo llamable directamente (verificado: `engine.calculate_autonomic_stability_score(4.5, 11.2) == 87.68`, formula intacta).
- **`app/main.py`**: el `st.metric` de Autonomic Stability se reemplazó por un `st.info()` con estado explícito — "🔴 No disponible — sin fuente de señal real" — en el mismo lugar de la grilla, sin ningún número.
- Expander "🔴 Fantasmas": ahora lista 4 casos (antes 3) — 2 resueltos ✅ (metabolic_efficiency, EDA), NeuroCardiac 🔴 pendiente-PLV, y el nuevo Autonomic Stability 🔴 sin-instrumento, con la distinción explícita de que este último no tiene componente rescatable ni ruta de reemplazo conocida.
- `bp_variance`/`ppg_pulse_transit_time_var` en los 4 presets y el modo manual: **no se quitaron** (mismo tratamiento que EDA) — anotados "sin efecto" inline y en el comentario de cabecera de cada bloque.
- `_BIOMARKER_HELP["Autonomic Stability Score"]` (tooltip ya sin uso) se eliminó del diccionario en `app/main.py`.

### Verificación

- `engine.get_full_biomarker_suite(basal)` devuelve 6 claves (sin `Autonomic Stability Score`); los otros 6 valores idénticos a la tanda anterior: Stress 22.22, Recovery 50.22, NeuroCardiac Coupling 51.4, Cognitive Load 5.67, Resilience 27.42, Learning Readiness 49.54 — confirmado por ejecución real, sin cambio.
- `pytest tests/ -q`: 414 passed, sin regresión.
- Compile-check limpio en `app/main.py` y `app/supermodules/biomarkers.py`.
- Servidor real (`streamlit run app/main.py`, puerto 8542): HTTP 200; proceso detenido tras la verificación.

## 2026-08-15 — Biomarkers Lab: ejecución de las 3 decisiones — 2 fantasmas retirados + renombre a "Índices fisiológicos BIOCORE"

**Contexto**: decisiones confirmadas por el usuario tras el dictamen del validador (ver tanda de honestidad, más abajo en este mismo día). A diferencia de esa tanda (puramente aditiva), esta **toca cálculos** en `app/supermodules/biomarkers.py`: se retiran 2 de los 3 fantasmas y se renormalizan pesos. Verificado número por número, no solo "no revienta".

### Decisión 1 — `metabolic_efficiency` retirado de Physiological Resilience Score

`calculate_physiological_resilience_score()` pierde el parámetro `metabolic_efficiency` y su componente `metabolic_norm` (rango 0.5-1.5, fisiológicamente imposible como RER). Pesos renormalizados sobre la suma original 0.80: `0.45/0.80 = 0.5625`, `0.35/0.80 = 0.4375` (suma exacta 1.0). Fórmula nueva: `hrr_norm*0.5625 + sdnn_norm*0.4375`, sobre los dos componentes citados por el validador ("marcadores dorados de resiliencia cardiovascular").

- **Preset Basal, antes/después** (HRR=25.0, SDNN=50.0, `metabolic_efficiency=0.9` por defecto de actividad "Moderado"): **29.93 → 27.42**.
- Reactividad confirmada por barrido: HRR=15/SDNN=15 → 0.0 · HRR=25/SDNN=50 → 27.42 · HRR=50/SDNN=150 → 100.0. Sigue moviéndose en todo el rango 0-100, sin `None` ni división por cero.

### Decisión 2 — Stress Index recortado a solo LF/HF

`calculate_stress_index()` pierde `eda_scr_peaks`/`scl_u_siemens` y sus componentes `eda_f_score`/`eda_t_score` — no hay módulo de señal EDA en el repo (confirmado por la auditoría de viabilidad, 2026-08-14). Con un solo componente no hay pesos que renormalizar: el score pasa a ser directamente `normalize(hrv_lf_hf_ratio, 0.5, 5.0)`. El score entero queda citado (Task Force ESC/NASPE 1996), no solo un componente.

- **Preset Basal, antes/después** (LF/HF=1.5): **18.85 → 22.22**.
- Reactividad confirmada por barrido: LF/HF=0.5 → 0.0 · LF/HF=1.5 → 22.22 · LF/HF=3.0 → 55.56 · LF/HF=5.0 → 100.0.

### Los otros 5 scores — sin cambios, confirmado por ejecución real

Con el mismo preset Basal: Recovery Index 50.22, NeuroCardiac Coupling Score 51.4, Cognitive Load Score 5.67, Autonomic Stability Score 87.68, Learning Readiness Index 49.54 — idénticos a los valores reportados en la auditoría original y en la tanda de honestidad previa. Ninguna de sus funciones se tocó.

### `get_full_biomarker_suite()` — limpieza de dead code consecuente

Se retiraron las 3 líneas de extracción (`eda_peaks`, `scl_us`, `metabolic`) que ya no alimentaban ninguna llamada. `metabolic_efficiency`/`eda_scr_peaks`/`scl_u_siemens` **no se quitaron** de los 4 presets ni del modo manual (`app/main.py`) — quedan huérfanos, anotados con comentario explícito en cada punto (preset dict, tab EDA del modo manual, dict empaquetado) para no romper el layout de columnas/tabs existente por un cambio fuera de alcance de esta tanda.

### Decisión 3 — Renombre "Proprietary Scores" → "Índices fisiológicos BIOCORE"

- Docstring de `BiocoreEngine` (`biomarkers.py`): "biomarcadores propietarios ... (ECG, EEG, EDA)" → "índices fisiológicos integrados ... (ECG, EEG)" — también se quitó "EDA" de la lista de señales, porque tras la Decisión 2 el motor ya no usa EDA en absoluto.
- `st.subheader` en `render_biomarkers_page()`: "📊 BIOCORE Proprietary Scores" → "📊 Índices fisiológicos BIOCORE".
- Texto introductorio del panel: "índices propietarios" → "índices fisiológicos BIOCORE".
- Grep completo por `propietari|proprietary` en `app/`: sin más coincidencias en texto de UI (solo quedan en comentarios/docstring explicando el propio renombre).

### Verificación

- Recalculado a mano y confirmado por ejecución real del motor (no solo lectura de código) para ambos scores cambiados — ver tablas arriba.
- `pytest tests/ -q`: 414 passed, sin regresión.
- Compile-check limpio en `app/main.py` y `app/supermodules/biomarkers.py`.
- Servidor real (`streamlit run app/main.py`, puerto 8541): HTTP 200; proceso detenido tras la verificación.

## 2026-08-15 — Biomarkers Lab: tanda de honestidad — constantes citadas + pesos etiquetados + fantasmas marcados + banner de demo

**Contexto**: el validador dictaminó los 7 Proprietary Scores de `BiocoreEngine` (auditoría 2026-08-14): algunas constantes tienen respaldo clínico citable, todos los pesos son "completamente arbitrarios", y 3 componentes son "fantasmas" (inputs sin señal real detrás). Esta tanda hace esa distinción visible en la UI de `render_biomarkers_page()` (`app/main.py`). **Aditivo salvo lo que un fantasma exige**: ningún cálculo cambió — los 3 fantasmas quedan marcados con propuesta, no eliminados; esa decisión es del usuario. Único efecto colateral: `Autonomic Stability Score` (calculado desde 2026-07-03 pero nunca desplegado, gap documentado) ahora se muestra, porque etiquetar un score que no se ve no tiene sentido.

### Mecanismo de UI (`app/main.py`, antes de `render_biomarkers_page()`)

Mismo vocabulario que Digital Twin Tanda 2, extendido con un tercer nivel: `BIOMARKER_CLINICAL_BADGE = "🟢"` / `BIOMARKER_HEURISTIC_BADGE = "🔵"` / `BIOMARKER_GHOST_BADGE = "🔴"` (nuevo — para inputs sin fuente de señal real, no solo sin cita). `help=` en cada `st.metric()` + `st.caption()` de leyenda + un `st.expander()` dedicado a los 3 fantasmas con su propuesta.

### Nivel 1 — citado (verbatim, dictamen del validador)

| Constante | Score | Cita |
|---|---|---|
| Ratio θ/α 0.5-4.0 + peso 0.7 | Cognitive Load | Holm et al., 2009 — "el candidato más fuerte, índice EEG robusto y validado para carga mental"; peso EEG validado (latencia ms vs. hemodinámica) |
| RMSSD 10-100ms | Recovery Index | "absolutamente correcto" (rango fisiológico) |
| LF/HF 0.5-5.0 | Stress Index | Task Force ESC/NASPE 1996 |
| SDNN 15-150ms + HR Recovery Rate 15-50 | Physiological Resilience | "marcadores dorados de resiliencia cardiovascular" |

### Nivel 2 — heurística, etiquetada

Todos los pesos de las 7 sumas ponderadas (0.50/0.35/0.15, 0.40/0.45/0.15, 0.3/0.3/0.4, 0.7/0.3, 0.45/0.35/0.20, 0.5/0.5, 0.4/0.4/0.2) — "completamente arbitraria" en las 7, sin excepción. También quedan heurísticos sin cita: HR de reposo y horas de sueño (Recovery), HR surge (Cognitive Load), variabilidad de PA/PTT (Autonomic Stability — no evaluado por este dictamen), atenuación beta (Learning Readiness).

### Nivel 3 — fantasmas (marcados, NO eliminados — decisión pendiente del usuario)

- **`metabolic_efficiency`** (Physiological Resilience): finge modelar el RER; rango 0.5-1.5 es fisiológicamente imposible (RER real nunca <0.7 ni >1.5). Propuesta reportada al usuario: quitarlo y renormalizar HRR/SDNN (0.45/0.35 → ~0.5625/0.4375), o mantenerlo marcado. **No se tocó `calculate_physiological_resilience_score()`.**
- **`signal_coherence`** (NeuroCardiac Coupling Score): placeholder sin definición algorítmica. El score entero queda marcado "pendiente de reemplazo por PLV" (próxima tanda) en vez de pulido — el validador lo llamó "pseudocientífico".
- **`eda_scr_peaks` / `scl_u_siemens`** (Stress Index): no existe módulo de señal EDA en el repo (confirmado por auditoría de viabilidad 2026-08-14) — solo constantes de preset. Propuesta reportada: recortar el score a solo LF/HF (real y citado) mientras no haya EDA. **No se tocó `calculate_stress_index()`.**

`bp_variance`/`ppg_pulse_transit_time_var` (Autonomic Stability) comparten el mismo problema estructural (sin fuente de señal real) pero no estaban en el alcance de este dictamen — quedan fuera de esta tanda, señalado explícitamente al usuario.

### Acción transversal A — banner de datos simulados

`st.warning()` persistente en `render_biomarkers_page()`, antes del switch de modo — cubre tanto "Base de Datos" (4 presets) como "Ingreso Manual" (ninguno conectado al UPS).

### Acción transversal B — nombre "propietario"

No se decidió ni se tocó — se reportaron las opciones al usuario (mantener con badge de heurística no validada vs. renombrar a algo como "Índices fisiológicos BIOCORE").

### Verificación

- `pytest tests/ -q`: 414 passed, sin regresión.
- Compile-check limpio en `app/main.py`.
- Servidor real (`streamlit run app/main.py`, puerto 8540): HTTP 200; proceso detenido tras la verificación.

## 2026-08-14 — Digital Twin, Tanda 2: procedencia visible — umbrales citados + heurísticas etiquetadas

**Contexto**: el validador dictaminó (con fuentes) qué datos del Digital Twin tienen respaldo clínico citable y cuáles son heurísticas de ingeniería de BIOCORE. Esta tanda hace esa distinción visible en la UI, con un vocabulario de procedencia consistente. **Puramente aditivo** -- ningún cálculo, umbral ni fórmula cambió; solo se añadieron `help=` en `st.metric()` y `st.caption()` cerca de cada dato, más dos docstrings alineando terminología. Confirmado por ejecución real (`AppTest`): los mismos valores de siempre (74%/88%/87% en los acoplamientos, 100/100 en salud) siguen exactamente iguales.

### Mecanismo de UI (`app/supermodules/twin_shell/pages.py`)

No se inventó un tercer sistema de procedencia -- se extendió el vocabulario ya usado en el proyecto (`Provenance`/`ClinicalReferenceValue` del UPS, y el patrón "PA calculada vs. referencia citada" ya existente en este mismo archivo) al único lugar donde estos datos realmente viven (`DigitalTwinOrganism`/`PredictionEngine`, fuera del esquema persistido del UPS):

- `PROVENANCE_CLINICAL_BADGE = "🟢"` / `PROVENANCE_HEURISTIC_BADGE = "🔵"` + `PROVENANCE_HEURISTIC_LABEL` y 7 constantes `PROVENANCE_SOURCE_*` con las citas verbatim del validador.
- Dos mecanismos según el widget, ambos "de un vistazo, sin ensayo": `help=` en `st.metric()` (tooltip nativo, cero espacio vertical extra) para acoplamientos y health/riesgo por órgano; `st.caption()` de una línea para el header ambiental, la grilla de órganos y la evaluación de riesgo por sistema (donde no hay `st.metric` que lo sostenga).

### Categoría A — citado (verbatim, firma del validador)

| Dato | Cita | Dónde |
|---|---|---|
| SpO2<90% (Respiratory) | NEWS2 / hipoxemia severa | `render_risk_assessment` |
| FC<40 o >140 (Cardiovascular) | ACLS/ATLS | `render_risk_assessment` |
| AHI>30/>15 (Respiratory) | criterio AASM | `render_risk_assessment` |
| FR<8 o >35 (Respiratory) | NEWS2 | `render_risk_assessment` |
| HRV<10ms (Cardiovascular) | depresión autonómica | `render_risk_assessment` |
| Razón HR:RR ≈4:1 (acoplamiento cardiorrespiratorio) | Pulse-Respiration Quotient (PRQ) en reposo | `render_couplings` |
| Centro FC=70bpm (Heart), FR=16/SpO2=100% (Lungs) | valores de referencia de adulto sano | `render_organ_grid`, `render_organ_panel` |
| Riesgo global = máximo (no promedio) | filosofía de triaje clínico | `render_ambient_header` |

**Precisión deliberada, no automática**: las citas de umbral se aplicaron *solo* donde el número en el código coincide exactamente con lo citado. Dos casos donde NO se aplicó una cita aunque a primera vista podría parecer que correspondía:
- `PredictionEngine.assess_autonomic_risk()` usa `HRV<15ms`/`<30ms` -- **distinto** del `HRV<10ms` que sí se citó (ese pertenece a `assess_cardiovascular_risk()`). Autonomic queda etiquetado heurístico, con una nota explícita de por qué no comparte la cita.
- `DigitalTwinOrganism`'s propio `organ.metrics.risk_score` (usado en `render_organ_panel`/`render_organ_grid`) usa umbrales propios (p.ej. `hr>120`, no `hr>140`) -- un sistema de riesgo *distinto* de `PredictionEngine`, no cubierto por este dictamen. Etiquetado heurístico, con nota explicando que es un sistema distinto del citado.
- `Neurological` y `Muscular` (`PredictionEngine`) no tienen ningún umbral citado por el validador -- quedan 100% heurísticos, explícito en su caption ("sin umbral citado por el validador").

### Categoría B — heurística, etiquetada honestamente

- Fórmulas lineales de acoplamiento (`50 + 0.5×alpha`, `cognitive_state×0.7`) -- `render_couplings`.
- Pesos de los health scores (0.3/0.5/0.2 etc.) -- `render_organ_grid`, `render_organ_panel` (el CENTRO de Heart/Lungs sí se cita, arriba; los PESOS no).
- Puntuaciones acumulativas de riesgo (+40/+50/...) y los buckets 70/50/30 de `risk_level` -- `render_risk_assessment`, todas las 5 filas.
- `system_coherence` (100-std) y `resilience_index` (fórmula ponderada) -- `render_ambient_header`.
- `global_risk_score` de `PredictionEngine.assess_global_risk()` (promedio de los 5 sistemas -- distinto del máximo de `DigitalTwinOrganism`, que sí se cita) -- `render_risk_assessment`.
- `CausalHint.confidence` (`domain/physiology/narrator/causal.py::_CAUSAL_HINTS`) -- ya estaba etiquetado internamente ("marco interpretativo, nunca un hecho medido"); esta tanda alinea su docstring al mismo vocabulario (`PROVENANCE_HEURISTIC_LABEL`) sin tocar su lógica ni exponerlo como badge de UI (nunca se muestra crudo al usuario, solo alimenta el prompt del narrador real como `reference_confidence`).

### Verificación

- **Ningún valor cambió**: confirmado por `AppTest` real -- Cerebro↔Corazón 74%, Corazón↔Pulmones 88%, Cerebro↔Músculos 87%, Salud general 100/100 -- idénticos a los reportados en la auditoría original, antes de esta tanda.
- `pytest tests/ -q`: 414 passed, sin regresión.
- Compile-check limpio en `twin_shell/pages.py` y `narrator/causal.py`.
- Servidor real (`streamlit run app/main.py`, puerto 8539): HTTP 200; proceso detenido tras la verificación.

## 2026-08-14 — Digital Twin, Tanda 1: confidence fachada del PredictionEngine retirado (Art. I) + barrida por gemelos

**Contexto**: el validador confirmó que `PredictionEngine.assess_*_risk()` devolvía un `confidence` estático hardcodeado por sistema (0.85/0.90/0.80/0.75/0.82) que nunca reaccionaba a la señal real -- confianza simulada, el mismo anti-patrón ya retirado del clasificador ECG (2026-08-06). Se retira, y como el patrón ya se copió una vez, se barrió el resto del repo por más instancias.

### Paso 1 — `PredictionEngine` (`app/engines/prediction_engine.py`)

- Confirmado por grep antes de tocar nada: `confidence` en `RiskAssessment` solo aparecía en la declaración del campo y en las 5 asignaciones fijas -- **ningún consumidor lo leía**, ni la UI (`render_risk_assessment()` en `twin_shell/pages.py`, único call site vivo, solo lee `risk_level`/`risk_score`/`recommendation`) ni ningún cálculo interno del propio módulo (`assess_global_risk()` agrega por `risk_score`, nunca por `confidence`).
- Retirado el campo `confidence: float` de `RiskAssessment` y las 5 asignaciones (`assess_cardiovascular_risk`, `assess_respiratory_risk`, `assess_neurological_risk`, `assess_muscular_risk`, `assess_autonomic_risk`).
- **Los umbrales de riesgo NO se tocaron** -- `hr<40 or hr>140`, `spo2<90`, `ahi>30`, etc., y sus penalizaciones en puntos, siguen exactamente igual. Esos van a la Tanda 2 (citarlos o etiquetarlos como heurística, según lo que confirme el validador) -- esta tanda es solo el confidence inventado que los acompañaba.

### Paso 2 — Barrida por gemelos

Grep de `confidence`/`certainty`/`probability` asignados a un literal numérico en todo el repo (fuera de `.conda`). Resultado, clasificado:

**Gemelo vivo encontrado y retirado**: `DigitalTwinOrganism.predict_physiological_events()` (`app/engines/digital_twin_organism.py`) -- devolvía `confidence` fijo por predicción (0.75 fatiga / 0.70 recuperación / 0.65 estrés / 0.80-0.85 inestabilidad cardiovascular), mismo patrón exacto. Confirmado por grep: este método no tiene ningún llamador vivo (solo aparece en `_archive/`) -- fachada Y código muerto a la vez. Retirado sin riesgo: nada que romper.

**Ya documentados como huérfanos en tandas previas -- encontrados de nuevo, NO tocados** (decisión arquitectónica ya tomada aparte, fuera del alcance de esta tanda):
- `app/engines/causality_engine.py::CAUSAL_RULES` (8 entradas, confidence 0.75-0.95) -- `CausalityEngine` fue retirado de la UI el 2026-07-13 (`render_causal_reasoning()` ya no lo llama, reemplazado por el narrador causal real); confirmado de nuevo por grep, cero llamadores vivos.
- `src/reasoning_engine.py` (6+ entradas, confidence 0.8-0.95 por rama de `PhysiologicalFinding`) -- documentado en CLAUDE.md como diferido/huérfano desde la Fase 0 ("no extenderlo"); confirmado por grep, cero imports en todo el repo.

**Dudoso -- reportado, no tocado**: `domain/physiology/narrator/causal.py::_CAUSAL_HINTS` (confidence 0.85/0.88, 2 entradas, espejo parcial de `CAUSAL_RULES`). Distinto en naturaleza de los demás: es un valor de referencia sobre una relación fisiológica GENERAL (no una medición del paciente actual), explícitamente documentado en su propio docstring como "marco interpretativo, nunca un hecho medido", y se pasa al narrador (Anthropic real) como `reference_confidence` -- un insumo etiquetado para el razonamiento del modelo, nunca se muestra en la UI como una métrica de IA cruda. No es el mismo patrón (no finge ser una medición computada), pero el número en sí (0.85/0.88) tampoco tiene cita -- candidato a la Tanda 2, no a esta.

**Revisados y descartados -- legítimos, no son el patrón**:
- `domain/physiology/hemodynamics/ups_bridge.py` (`confidence=0.425`) -- parte del contrato formal `Provenance`+`confidence` del UPS, extensamente justificado en comentario (por qué ese valor exacto, para preservar comportamiento histórico de una banda de confianza ya existente) -- un flag de estado epistémico declarado, no una medición fingida.
- `tests/test_ups_state.py` (`confidence=0.9`) -- parámetro de un fixture de prueba, no llega a ningún usuario.
- `biomedical/arrhythmia_compat.py` (`overall_confidence`) -- SÍ se calcula (`votos / total_beats`); el `0.0` es solo el default del caso degenerado sin latidos.
- `src/ai/patient_analytics.py::time_confidence` -- SÍ se calcula (`min(1.0, 20.0/tiempo_respuesta)`), consistente con la clasificación "real" ya dada a `PatientRiskPredictor` en una auditoría previa.

**Hallazgo colateral, no es un gemelo nuevo, no tocado**: `clinical/ecg_analyzer.py::clinical_summary()` línea 537 todavía lee `pattern_info['confidence']` (con corchetes, no `.get()`) -- una referencia que quedó rota cuando se retiró ese campo el 2026-08-06. Causaría `KeyError` si se llamara, pero confirmado por grep que su único llamador real (`app/supermodules/ecg_monitor/pages.py`) es el supermódulo ECG Monitor ya documentado como huérfano (`app/main.py::render_ecg_monitor_page()` no lo importa, solo usa `get_case_database` de ahí) -- no es alcanzable desde la app viva. Se reporta para que quede registrado, no se tocó (fuera del alcance: no es un gemelo del patrón de esta tanda, es un residuo de la anterior en código ya muerto).

### Verificación

- `pytest tests/ -q`: 414 passed, sin regresión -- ningún test referenciaba `RiskAssessment.confidence` ni `predict_physiological_events()`.
- Compile-check limpio en `prediction_engine.py` y `digital_twin_organism.py`.
- Servidor real (`streamlit run app/main.py`, puerto 8538): HTTP 200; proceso detenido tras la verificación.
- Los umbrales de riesgo del `PredictionEngine` (HR/SpO2/RR/AHI/HRV y sus penalizaciones en puntos) quedan exactamente iguales -- solo se quitó el número de confianza inventado que los acompañaba.

## 2026-08-14 — Narrador clínico: max_tokens 1024→4096 (explicaciones que se cortaban a media frase)

**Contexto**: el usuario confirmó visualmente que las explicaciones del narrador clínico se cortaban a media frase. Causa identificada: `max_tokens=1024` en las tres llamadas reales a la API de Anthropic (`domain/physiology/narrator/{client,findings,causal}.py`) — insuficiente para una explicación clínica completa (mecanismo fisiológico + significado clínico + comparación antes/ahora, típicamente 600-1200 palabras).

### El cambio

- `max_tokens: int = 1024` → `max_tokens: int = 4096` en las tres funciones de streaming: `client.py::stream_narration()`, `findings.py::stream_findings_narration()`, `causal.py::stream_causal_narration()`.
- **No se duplicó a ciegas**: duplicar 1024 da exactamente 2048, el borde superior de la estimación de 1500-2500 tokens que necesita una explicación larga -- sin margen real, arriesgando el mismo corte con una explicación algo más larga que el promedio. Se subió a 4096 (~2x el techo estimado) para que nunca se ajuste al límite.
- Grep confirmado: son las ÚNICAS 3 llamadas reales a la API en todo el repo (fuera de `.conda`) -- ningún llamador (`app/main.py`, `app/supermodules/twin_shell/pages.py`, `app/supermodules/academia/pages.py`, 5 sitios en total) pasa `max_tokens` explícito, así que el nuevo default aplica en las 5 pantallas que usan el narrador sin excepción.

### Verificación de que no hay un segundo límite

- **Sin truncamiento de display**: los 5 call sites o bien pasan el generador directo a `st.write_stream(...)` (2 en twin_shell, 1 en main.py) o acumulan el stream completo con `"".join(...)` antes de un `st.markdown(texto_completo)` (2 en twin_shell/academia) -- ningún `[:N]`, `st.text_area(max_chars=...)` ni recorte de ningún tipo en el camino desde la API hasta la pantalla.
- **Sin `stop_sequences`** ni ningún otro parámetro de corte en las tres llamadas a `client.messages.stream()`.
- Si algún día se corta de nuevo, no es por estos dos motivos -- descartados por grep, no por suposición.

### Verificación

- `pytest tests/ -q`: 414 passed, sin regresión (el cambio no toca ninguna lógica que los tests cubran, solo un valor por defecto).
- Compile-check limpio en los 3 archivos.
- Servidor real (`streamlit run app/main.py`, puerto 8537): HTTP 200; proceso detenido tras la verificación.
- **Pendiente de confirmación visual del usuario** con su `ANTHROPIC_API_KEY` real -- este entorno no tiene una key válida para probar el streaming end-to-end.

## 2026-08-12 — Detector BBB, Fase 4: criterio qR de RBBB, con salvaguarda V6 obligatoria

**Contexto**: el inventario caso-por-caso de solo-lectura (misma fecha, entrada de abajo) identificó exactamente qué RBBB reales quedaban sin resolver con la base técnica ya limpia (sincronización + selector anti-T) y por qué: 6 casos con patrón qR en V1 y V6 ya cumpliendo su salvaguarda (rescatables por un criterio nuevo), 7 casos también con qR en V1 pero V6 atípico (deben seguir indeterminados), y un techo honesto de casos técnicos/de dataset/clínicos irresolubles. El validador confirmó el patrón qR como RBBB válido -- fuente citada: Chou's Electrocardiography in Clinical Practice / Marriott's Practical Electrocardiography -- con la S ancha en V6 como salvaguarda AND obligatoria. Esta tanda implementa ese criterio verbatim, sin tocar el delineador ni el criterio RSR'/LBBB existentes.

### Paso 1 — Procedencia

Registrada en `clinical/bbb_detector.py` (constantes `RBBB_QR_*` y sección "CRITERIO VERBATIM DEL VALIDADOR" del docstring del módulo) y aquí: firma del validador clínico, Detector BBB, Fase 4, aprobación 2026-08-12; fuente citada Chou's/Marriott. Mismo patrón que la procedencia ya registrada para el RSR' original (Fase 3).

### Paso 2 — El criterio (`clinical/bbb_detector.py`)

- **`_check_rbbb_qr_v1()`** (nueva): morfología B de RBBB -- (1) exactamente una deflexión positiva (R única, `>=0.5mV`), (2) esa R es la deflexión TERMINAL del complejo ("sin S posterior"), (3) existe una deflexión inmediatamente anterior a la R con amplitud `<=-0.1mV` (la q). Si la R es la ÚNICA deflexión del complejo (nada antes tampoco), NO cumple -- es "R sola", una morfología distinta, no lo que el validador describió.
- **`_check_rbbb_v6()` parametrizado** (no duplicado): acepta ahora `max_amplitude_mv`/`min_duration_ms` opcionales. La morfología clásica (RSR') sigue llamándolo con los valores por defecto (-0.1mV/40ms); la nueva morfología qR lo llama con la salvaguarda más estricta del validador (`RBBB_QR_V6_S_MAX_AMPLITUDE_MV=-0.15`, `RBBB_QR_V6_S_MIN_DURATION_MS=40`).
- **`detect_bundle_branch_block()`**: ahora evalúa AMBAS morfologías (`is_rbbb_classic or is_rbbb_qr`) -- RBBB si cualquiera de las dos cumple con su propia salvaguarda V6. La salvaguarda NUNCA se comparte ni se relaja entre morfologías.

### Paso 3 — Verificación contra el inventario exacto

**Los 6 casos que el inventario esperaba rescatar** (`195, 455, 788, 826, 1066, 1093`): **4/6 se rescataron** (`195, 455, 788, 1093`) -- **2/6 NO** (`826`, `1066`). Investigado, no forzado: en ambos, la señal cruda de V1 sube limpia desde el baseline plano directo hasta la R, sin ningún descenso previo medible -- confirmado visualmente sobre la traza (ver `clinical/bbb_detector.py`, sección de decisiones de implementación). Es "R sola", no "qR" -- el inventario había etiquetado ambos casos por su V1 con una sola deflexión positiva, pero no había verificado si esa deflexión tenía una q genuina delante. El criterio, aplicado verbatim (exige la q), correctamente los deja indeterminados. No se relajó "q<=-0.1mV" a "opcional" para forzar el 6/6.

**Los 7 casos de V6-atípico** (`172, 310, 477, 903, 957, 428, 680`): **7/7 siguen indeterminados** -- la salvaguarda funcionó exactamente como se pretendía, sin una sola excepción.

**Hallazgo NO anticipado -- 1 error grave nuevo, investigado, explicado**: `ecg_id=287` (LBBB real, `CLBBB: 100.0` en `scp_codes`) ahora se clasifica RBBB vía la morfología qR. Investigado a fondo, no forzado ni parchado con un umbral inventado:
- La señal cruda confirma que la delineación es correcta (no es un artefacto de ancla ni del delineador): V1 muestra q(-0.45mV)+R(0.87mV) sin S posterior -- un qR genuino; V6 muestra R(1.74mV)+S(-0.73mV, 94ms) -- una S bien por encima del umbral estricto (-0.15mV), no un caso límite.
- Se probó si un umbral de amplitud/duración más estricto en V6, o una razón S/R, separaría este caso de los 4 rescates genuinos -- NO: los rescates genuinos (`ecg_id=788`, `1093`) tienen razones S/R casi idénticas (0.42-0.44) a las de `287` (0.42). No hay un ajuste numérico honesto, dentro de los umbrales verbatim del validador, que excluya `287` sin también excluir rescates genuinos -- así que NO se tocó ningún umbral.
- **El reporte original de PTB-XL para `ecg_id=287` dice, en texto libre**: *"premature ventricular contraction(s). sinus rhythm. right bundle branch block."* -- contradice directamente su propia etiqueta estructurada `CLBBB: 100.0`. La lectura del detector (RBBB) coincide con el reporte humano en texto libre; la etiqueta estructurada que usa el set de validación como ground truth es, muy probablemente, la que está mal. Mismo patrón exacto que `ecg_id=1024` (Fase 3: reporte alemán "unvollständiger" vs. `CRBBB: 100.0`) -- una segunda inconsistencia confirmada en el dataset, no una falla del criterio ni de la salvaguarda.
- No se modificó código a raíz de este hallazgo -- la salvaguarda V6 está funcionando correctamente (excluyó los 7 de V6-atípico sin excepción); este caso específico es, con evidencia razonable, una etiqueta de ground truth incorrecta, no un falso positivo del detector.

**Techo honesto verificado intacto** -- ninguno de estos 5 se "rescató", como se esperaba: `1049` (ruido documentado, sigue QRS<=120ms), `1024` (errata de etiqueta ya conocida, sigue indeterminado), `269` (angosto genuino, sigue QRS<=120ms), `1157` (ectopia documentada, sigue el error grave ya explicado en la Fase 3), `512` (microvoltaje, sigue QRS<=120ms).

**LBBB**: 9/25 confirmados -- sin cambio en el número (el criterio LBBB no se tocó); el único movimiento es `287`, que salió de "indeterminado" hacia el nuevo error grave explicado arriba.

**Errores de rama**: 1 ya existente (`1157`, RBBB→LBBB, ectopia -- Fase 3) + 1 nuevo (`287`, LBBB→RBBB, investigado y explicado como errata de etiqueta arriba). Cero errores nuevos sin explicar.

### Paso 4 — Matriz final (50 casos, ancla=II, técnica completa: sincronización + selector anti-T + qR)

| | RBBB confirmado | RBBB→LBBB (grave) | Indeterminado | QRS≤120ms |
|---|---|---|---|---|
| **RBBB (25)** | **5** | 1 | 10 | 9 |
| | **LBBB confirmado** | **LBBB→RBBB (grave)** | **Indeterminado** | **QRS≤120ms** |
| **LBBB (25)** | 9 | 1 | 6 | 9 |

**Proyección del validador vs. realidad medida**: proyectó RBBB 1→7/25 -- la medición real da **1→5/25** (621 preexistente + 195, 455, 788, 1093 rescatados; 826 y 1066 NO, por la razón investigada arriba). Proyectó indeterminados válidos 14→8/25 -- la medición real da **14→10/25** (7 V6-atípico + 826 + 1066 + 1024). La proyección era una hipótesis; esto es lo que salió, reportado sin maquillar.

### Cada indeterminado/no-evaluado restante, con su razón exacta

- **V6 atípico (7)**: `172, 310, 477, 903, 957, 428, 680` -- qR en V1 (o RSR' válido en el caso de `428`), pero V6 sin el par R/S esperado. Salvaguarda funcionando, correctamente indeterminados.
- **R sola, no qR (2)**: `826, 1066` -- QRS>120ms confirmado, V1 con R única pero SIN q medible. Morfología distinta a la que el validador describió; candidato a una futura pregunta aparte, no resuelto por este criterio.
- **Límite del delineador (4, ya documentado en la investigación previa)**: `424, 1123, 1232, 1237` -- confirmados anchos por investigación manual (3 métodos independientes), medidos <=120ms por el delineador estricto. Sin tocar (fuera de alcance, `qrs_delineation.py` intacto).
- **Errata de etiqueta del dataset (2)**: `1024` (reporte alemán "incompleto" vs. `CRBBB:100.0`), `287` (reporte "right bundle branch block" vs. `CLBBB:100.0`, hallazgo de esta tanda).
- **Ruido documentado (1)**: `1049` (`static_noise: stark` en la metadata de PTB-XL).
- **Realidad clínica (2)**: `269` (angosto genuino, 3 métodos), `1157` (ectopia/PVC documentada, confunde la selección de latido).
- **Sin clasificar, confianza insuficiente (1)**: `512` (microvoltaje, sin morfología clara en ningún método probado).

### Verificación

- `tests/test_bbb_detector.py`: 36 tests (27 previos + 9 nuevos -- `_check_rbbb_qr_v1()` en sus 6 ramas, el parámetro de umbral de `_check_rbbb_v6()`, y dos pruebas end-to-end de la morfología qR completa incluida la regla "la salvaguarda nunca basta sola").
- `pytest tests/ -q`: 414 passed (405 previos + 9 nuevos), sin regresión.
- Compile-check limpio en `clinical/bbb_detector.py`.
- `qrs_delineation.py`, el criterio RSR'/LBBB existente, y el motor: sin tocar.
- Servidor real (`streamlit run app/main.py`, puerto 8536): HTTP 200; proceso detenido tras la verificación.

**Con esto cierra la Fase 4**: RBBB pasó de 0/25 (Fase 3 inicial) a 5/25 confirmados, con cada indeterminado y cada no-evaluado restante atribuido a una causa concreta y verificada -- 7 por diseño (salvaguarda V6 funcionando), 2 por morfología genuina distinta a qR, 4 por límite del delineador (documentado, pendiente de una fase de consolidación si se decide perseguir), 3 por realidad del dataset/ruido, 2 por realidad clínica, 1 sin clasificar. Ningún número se ajustó para mejorar la matriz -- la desviación de la proyección del validador (7 esperados, 5 reales) se investigó y se reporta con su causa exacta, no se ocultó.

## 2026-08-12 — Detector BBB, el selector de latido aprende a distinguir QRS de onda T

**Contexto**: la corrección de sincronización (entrada de abajo, misma fecha) garantizó que V1 y V6 se delinean en el MISMO latido, pero el selector filtraba solo por regularidad de RR -- y una onda T ocurre una vez por latido, igual que el QRS, así que pasa ese filtro igual de bien. La investigación de solo-lectura había encontrado el ancla cayendo en una onda T en `ecg_id=1123`/`1232` (entre otros), evitado a mano en esa investigación (por eso lograba ~9/12 casos narrow cruzando 120ms donde el selector automático solo lograba 3-7/12). Esta tanda enseña al selector a distinguir QRS de T por una propiedad geométrica objetiva -- sin tocar el criterio clínico ni el delineador de la Sub-Fase 2.5.

### El arreglo (`clinical/bbb_detector.py`)

- **`_half_amplitude_width_ms(signal, peak_idx, fs)`** (nueva): ancho de una deflexión medido a media amplitud respecto a un baseline local (estimado en los bordes de una ventana de búsqueda de ±150ms, lejos del propio pico).
- **`_looks_like_qrs(signal, peak_idx, fs)`** (nueva): `True` si ese ancho es ≤`QRS_MAX_HALF_AMPLITUDE_WIDTH_MS` (80ms). Fundamento: el QRS es una deflexión de alta frecuencia (subida/bajada de unas pocas decenas de ms, incluso en un complejo ancho patológico -- lo que se ensancha es el COMPLEJO completo, sumando varios componentes narrow, no cada componente individual); la onda T es una deflexión redondeada de baja frecuencia (~160ms+ de ancho total). Es la misma propiedad (contenido de alta frecuencia) que usa la literatura de detección de QRS -- p.ej. Pan-Tompkins (filtro pasa-banda + derivada) -- para separar QRS de P/T, medida aquí de forma directa en vez de replicar ese pipeline completo.
- **Calibración empírica del umbral de 80ms** (Fase 3, 2026-08-12), contra los 50 casos reales:
  | Grupo | Ancho medido |
  |---|---|
  | Picos de QRS conocidos (verificados a mano en la investigación previa) | 16, 22, 28, 34, 62 ms |
  | Picos de onda T conocidos (anclas viejas que caían en T, `ecg_id=1123`/`1232`/`957`) | 88, 104, 112 ms |

  80ms cae limpio en la brecha entre ambos grupos. Un barrido más amplio sobre picos de lead II en 16 registros reales (RBBB y LBBB) confirma el patrón bimodal: la mayoría de los picos caen claramente <50ms (QRS) o >90ms (T), con pocos casos en la zona gris 60-90ms.
- **`_select_reference_beat()` actualizado**: ahora filtra por `_looks_like_qrs()` ANTES de calcular la regularidad de RR -- importante, no cosmético: si el filtrado de RR se calculara sobre la lista mixta original (R, T, R, T, ...), los huecos alternarían corto/largo y distorsionarían la mediana de RR para AMBOS tipos de pico. Filtrar primero por anchura, y solo después calcular RR entre los picos que sí parecen QRS, evita ese sesgo. Si el filtro de anchura eliminara todos los picos (caso degenerado), cae a la lista sin filtrar -- documentado, no silencioso.
- **Verificado directamente contra los 3 casos conocidos** de la investigación: `ecg_id=1123` (ancla vieja en T: idx=2421, 104ms de ancho → ancla nueva: idx=2699, 28ms, un QRS real de amplitud grande, 0.698mV); `ecg_id=1232` (ancla vieja en T: idx=2384, 112ms → ancla nueva: idx=1345, 8ms); `ecg_id=957` (ancla vieja en T: idx=2804, 88ms → ancla nueva: idx=3060, 36ms, amplitud -0.220mV, del mismo grupo de picos grandes ya identificado en la investigación manual). Los tres dejaron de anclar en onda T.

### Re-validación de los 50 -- panorama completo, las 5 etapas

| | **RBBB→RBBB** | **RBBB→LBBB (grave)** | **RBBB→indet.** | **RBBB→QRS≤120** | **LBBB→LBBB** | **LBBB→RBBB (grave)** | **LBBB→indet.** | **LBBB→QRS≤120** |
|---|---|---|---|---|---|---|---|---|
| Antes (desincronizado) | 0 | 1 | 12 | 12 | 19 | 0 | 4 | 2 |
| Sync sin filtro-T, ancla=V6 | 0 | 2 | 12 | 11 | 19 | 0 | 4 | 2 |
| Sync sin filtro-T, ancla=II | 0 | 1 | 14 | 10 | 8 | 0 | 7 | 10 |
| **Sync + filtro-T, ancla=V6** | 0 | **0** | 15 | 10 | 16 | 0 | 4 | 5 |
| **Sync + filtro-T, ancla=II** | **1** | 1 | 14 | 9 | 9 | 0 | 7 | 9 |

**De los 12 RBBB "narrow" originales, cuántos cruzan 120ms ahora**: con ancla=V6, 4/12 (680, 1024, 1157, 1232). Con ancla=II, 6/12 (195, 310, 680, 957, 1024, 1157). La unión de ambas anclas: 7/12 (195, 310, 680, 957, 1024, 1157, 1232). Ninguna alcanza el ~9/12 de la investigación manual -- ver interpretación, la causa está identificada con precisión, no es un misterio.

### Interpretación honesta: el filtro de T SÍ era real, pero NO era toda la brecha

- **El filtro de T funciona, verificado directamente**: los 3 casos donde la investigación había encontrado un ancla en onda T ahora anclan en un QRS genuino (confirmado por ancho Y por ser parte del grupo de picos de amplitud grande ya identificado a mano). Con ancla=V6, el filtro de T **elimina por completo los errores graves** (2→0) -- un QRS mal anclado en T alimentaba una morfología espuria que a veces se parecía lo bastante a LBBB para confundirse; con el ancla correcta, eso deja de pasar. Con ancla=II, aparece por primera vez **1 caso RBBB correctamente confirmado**.
- **Pero NO cierra la brecha a ~9/12** -- se investigó por qué con el caso mejor documentado (`ecg_id=1123`): el ancla manual verificada en la investigación previa (`idx=2264`) y la nueva ancla automática (`idx=2699`) son AMBAS genuinamente QRS (no T) -- están a 435 muestras (870ms) de distancia, un latido adyacente, no el mismo, pero de la MISMA condición crónica (RBBB no cambia latido a latido), donde la morfología debería ser prácticamente idéntica. Al pasar la ancla MANUAL (`idx=2264`) por el delineador real de la Sub-Fase 2.5 (sin modificar), el ancho medido es 110ms -- NO los ~144ms que la lectura visual a ojo había estimado en la investigación de solo lectura. **La brecha restante no es un problema de qué latido se elige -- es que el delineador (intacto, fuera de alcance) mide el ancho con un criterio más estricto que una lectura visual generosa**, incluso anclado exactamente en el mismo QRS real. Esto es consistente con la limitación de baseline contaminado ya documentada (Fase 3, entrada original de esta serie, "candidato para consolidación posterior, no perseguido más") -- ahora confirmada como la pieza que falta, no una hipótesis.
- **El panorama REAL de RBBB, con las dos capas técnicas resueltas** (sincronización + selector-anti-T): 1/25 confirmado, 1/25 error grave (`ecg_id=1157`, complicado por una PVC documentada en su reporte original -- un confusor genuino, no un artefacto de selección), 14/25 indeterminado, 9/25 sin evaluar. **Los 14 indeterminados son la pregunta limpia para el validador**: QRS confirmado >120ms, pero no cumple el criterio duro de R'-terminal-dominante en V1 -- muchos muestran un patrón qR simple (una sola deflexión positiva, sin el notch RSR' clásico), exactamente el patrón que el criterio actual excluye a propósito ("RSR' sin S ancha en V6 → indeterminado", y de forma más amplia, sin R' en absoluto → indeterminado). De los 9 sin evaluar, una fracción son el residuo de la limitación del delineador arriba descrita (1123 entre ellos), otra fracción es ruido documentado en la propia metadata de PTB-XL (`ecg_id=1049`, `static_noise: stark`), y al menos un caso (`ecg_id=269`) ya se había identificado como probablemente genuinamente angosto en la investigación manual.
- **No se ajustó nada para mejorar la matriz** -- el umbral de 80ms se calibró contra picos conocidos ANTES de ver el efecto en la matriz completa, y el resultado se reporta tal cual, incluyendo que no alcanza el ~9/12 esperado y que LBBB con ancla=V6 baja levemente (19→16, aunque a cambio elimina los errores graves). El criterio clínico (umbrales RSR', qR, S ancha, Q septal, 120ms) no se tocó. El delineador de la Sub-Fase 2.5 no se tocó.

### Verificación

- `tests/test_bbb_detector.py`: 27 tests (23 previos + 4 nuevos -- `_looks_like_qrs()` verdadero para un pico angosto sintético y falso para uno ancho/redondeado, `_half_amplitude_width_ms()` contra el FWHM teórico de un gaussiano de sigma conocida, y una prueba end-to-end con una T periódica que comparte cadencia con el QRS -- confirma que `_select_reference_beat()` seguiría eligiendo el QRS, no la T, incluso cuando ambas pasarían el filtro de regularidad de RR por separado).
- `pytest tests/ -q`: 405 passed (401 previos + 4 nuevos), sin regresión.
- Compile-check limpio en `clinical/bbb_detector.py`.
- `qrs_delineation.py` y el criterio de Fase 1: sin tocar.
- Servidor real (`streamlit run app/main.py`, puerto 8535): HTTP 200; proceso detenido tras la verificación.

**Con esto se cierra la fontanería identificable de esta serie**: sincronización (arreglada), selector-en-T (arreglado y verificado), y la brecha residual queda correctamente atribuida al delineador (fuera de alcance, documentado, no un misterio nuevo). La pregunta para el validador queda acotada a los 14 casos indeterminados por el patrón qR-sin-R' -- ahí es donde vale la pena gastar su tiempo, no en artefactos técnicos.

## 2026-08-12 — Detector BBB, corrección de sincronización V1/V6: mismo latido, no latidos distintos

**Contexto**: la auditoría de solo-lectura de los 12 RBBB "narrow" (misma fecha, ver entrada de abajo) confirmó el bug de plomería sospechado: `_reference_r_peak_idx()` se llamaba independientemente por derivación, así que V1 y V6 podían delinearse en latidos DISTINTOS del registro -- separados hasta 5368ms en los 50 casos de validación, nunca el mismo complejo. El criterio de RBBB ("R' en V1 Y S ancha en V6") describe dos vistas del MISMO complejo, no de dos latidos -- comparar latidos distintos invalida la premisa del criterio. Esta tanda corrige la sincronización, sin tocar el criterio clínico (eso queda para el validador) ni el delineador de la Sub-Fase 2.5.

### El arreglo (`clinical/bbb_detector.py`)

- **`_select_reference_beat(reference_signal, fs)`** (nueva, reemplaza `_reference_r_peak_idx()`): elige UN latido representativo de una única derivación de referencia. Criterio de selección, documentado explícitamente como decisión de diseño:
  1. Picos por amplitud absoluta (`_detect_reference_peaks()`, sin tocar).
  2. Excluye el primer y el último pico -- riesgo de truncamiento en los bordes del registro.
  3. Descarta cualquier pico interior cuyo hueco RR (al vecino anterior O al siguiente) se desvíe más del 25% de la mediana de RR del registro (`REFERENCE_BEAT_RR_TOLERANCE`) -- sospechoso de latido ectópico (PVC) o artefacto. Varios de los 50 casos de validación tienen extrasístoles documentadas en su reporte original de PTB-XL (p.ej. `ecg_id=1157`, "premature ventricular contraction(s)").
  4. Entre los picos "regulares" que sobreviven, el más cercano al CENTRO temporal del registro.
- **`detect_bundle_branch_block(v1_signal, v6_signal, fs, reference_signal=None)`**: nuevo parámetro opcional. Con `reference_signal` (idealmente lead II, el estándar de ritmo), el ancla se deriva de ESA señal. Sin ella, cae a V6 como ancla (fallback documentado: sigue siendo UNA sola señal para las dos delineaciones -- preserva la sincronización aunque no haya una derivación de ritmo dedicada disponible). En ambos casos, V1 y V6 se delinean con el MISMO `r_idx` -- verificado con un test de regresión que espía las llamadas a `delineate_qrs()`.
- `ECGAnalyzer._classify_bbb()`/`detect_clinical_pattern()` (`clinical/ecg_analyzer.py`): si `leads` trae "II" además de V1/V6, se pasa como `reference_signal`. Ningún call site en vivo pasa `leads` hoy (sin cambio de comportamiento fuera de las pruebas de validación).
- El delineador de la Sub-Fase 2.5 (`delineate_qrs()`) no cambia -- solo el índice que se le pasa.

### Re-validación de los 50 casos -- TRES matrices, comparadas honestamente

No hay un solo "después": el ancla se puede derivar de V6 (fallback) o de lead II (diseño recomendado). Ambas resultan en sincronización correcta (V1/V6 miden el mismo latido, garantizado por construcción), pero dan números distintos -- se reportan las dos, sin elegir la que se vea mejor.

| | **Antes** (desincronizado) | **Después, ancla=V6** | **Después, ancla=II** |
|---|---|---|---|
| RBBB → RBBB | 0/25 | 0/25 | 0/25 |
| RBBB → LBBB (error grave) | 1/25 | 2/25 | 1/25 |
| RBBB → indeterminado | 12/25 | 12/25 | 14/25 |
| RBBB → QRS≤120ms (no evaluado) | 12/25 | 11/25 | 10/25 |
| LBBB → LBBB | 19/25 | 19/25 | 8/25 |
| LBBB → indeterminado | 4/25 | 4/25 | 7/25 |
| LBBB → QRS≤120ms (no evaluado) | 2/25 | 2/25 | 10/25 |

**De los 12 RBBB "narrow" originales, cuántos cruzan 120ms ahora**: con ancla=V6, 3/12 (680, 1024, 1157). Con ancla=II, 7/12 (195, 269, 310, 680, 957, 1024, 1157). Ninguno de los dos reproduce el ~9/12 que encontró la investigación manual de solo-lectura (misma fecha, entrada de abajo) -- ver interpretación.

### Interpretación honesta

- **La sincronización en sí está correcta y verificada** -- V1 y V6 miden el mismo latido por construcción (test de regresión que espía `delineate_qrs()`), no una aproximación. Eso es un hecho objetivamente correcto, independiente de cómo cambien los números.
- **Pero el arreglo NO reprodujo la mejora dramática que sugería la investigación manual.** La investigación de solo-lectura encontró QRS real ≥120ms en 9/12 casos narrow -- pero esa investigación verificó A MANO que el latido ancla fuera una deflexión de amplitud genuina (para 3 casos, descartó explícitamente el pico "mediana" automático porque caía en una onda T, y lo reemplazó por un pico de amplitud grande de la lista completa). `_select_reference_beat()` no tiene ese paso de verificación de amplitud -- solo filtra por regularidad de RR, y una onda T que ocurre a un intervalo regular (una por latido, como el propio QRS) puede pasar ese filtro igual de bien que un QRS real. Esta es una limitación real y no resuelta de la selección automática, distinta del bug de sincronización que sí se corrigió -- documentada aquí, no oculta.
- **Lead II no es uniformemente mejor.** Es el diseño recomendado (la investigación lo usó con éxito para los 12 narrow), y de hecho cruza más casos narrow a ≥120ms (7 vs 3) y reduce el error grave de RBBB (1 vs 2) -- pero **hunde LBBB de 19/25 a 8/25**. La causa más probable: anclar en una derivación distinta a las que se clasifican (II en vez de V1/V6) no garantiza que el latido elegido sea limpio EN V1/V6 específicamente -- la calidad de señal varía por electrodo, y V6 (al ser una de las dos derivaciones que ya se están clasificando) parece dar, en este set, latidos mejor delineados en sí misma más a menudo que lo que aporta II. Ninguna de las dos opciones es objetivamente superior en general; es un trade-off medido, no ajustado.
- **El panorama REAL de RBBB, con la sincronización arreglada**: sigue en 0/25 confirmados con cualquiera de las dos anclas. La mayoría de los casos que cruzan 120ms caen en "indeterminado" (14/25 con ancla=II) por el mismo patrón qR-sin-R'-terminal ya documentado -- ese es el hallazgo clínico genuino, ahora con menos ruido técnico de por medio (algunos casos que antes ni siquiera alcanzaban el umbral ahora sí lo hacen y llegan a la pregunta real del criterio). Pero una fracción de los 12 narrow sigue sin cruzar 120ms incluso con el ancla correcta -- no todo era el bug de sincronización; la limitación de selección de latido (arriba) explica parte de lo que falta.
- **No se ajustó nada para mejorar la matriz** -- ambas anclas se implementaron, probaron y reportaron tal como salieron, incluyendo el resultado incómodo (LBBB empeora con II). El criterio clínico (umbrales RSR', qR, S ancha, Q septal) no se tocó en ningún momento de esta tanda.

### Verificación

- `tests/test_bbb_detector.py`: 23 tests (17 previos + 6 nuevos -- `_select_reference_beat()` excluye bordes, prefiere el centro, evita latidos ectópicos con RR corto, y dos regresiones directas: mismo `r_idx` para V1/V6 espiando `delineate_qrs()`, y `reference_signal` realmente se usa cuando se pasa).
- `tests/test_bbb_detector_validation.py`: actualizado para cargar y pasar lead II como `reference_signal` (antes solo cargaba V1/V6) -- reporta la matriz con ancla=II.
- `pytest tests/ -q`: 401 passed (395 previos + 6 nuevos), sin regresión.
- Compile-check limpio en `clinical/bbb_detector.py`, `clinical/ecg_analyzer.py`.
- `qrs_delineation.py`: sin tocar.
- Servidor real (`streamlit run app/main.py`, puerto 8534): HTTP 200; proceso detenido tras la verificación.

**Pendiente, fuera de alcance de esta tanda**: mejorar `_select_reference_beat()` para descartar candidatos de baja amplitud (no solo RR irregular) -- cerraría la brecha con lo que encontró la investigación manual. Decidir si el default de producción debería ser V6 (mejor para LBBB en este set) o II (mejor para RBBB narrow, diseño originalmente recomendado) -- ahora mismo `ECGAnalyzer` usa II cuando `leads` la trae y V6 si no, pero ningún call site en vivo pasa `leads` todavía, así que esta decisión no tiene efecto observable fuera de las pruebas de validación. La pregunta al validador sobre el criterio qR-sin-R' sigue en pie, ahora sobre una base técnica más limpia (14/25 indeterminados con ancla=II, no 12/25 con sincronización rota).

## 2026-08-12 — Detector BBB, pre-validador (solo lectura): los 12 RBBB "narrow" -- bug técnico, no realidad clínica

**Instrumento de solo lectura, sin cambios de código** -- diagnóstico previo al arreglo de sincronización de la entrada de arriba. Pregunta: de los 12 casos RBBB reales que no cruzan el umbral QRS>120ms del detector (Fase 3), ¿es un bug de medición o realidad clínica? CRBBB = bloqueo completo = QRS ancho por definición, así que "12 de 25 no son lo bastante anchos" era sospechoso de bug antes de llevar la pregunta del criterio al validador.

**Método**: para cada uno de los 12, se ancló V1/V6/II a un latido ÚNICO verificado a mano (elegido por amplitud real de la lista completa de picos de lead II, no por el selector automático de entonces -- ya cuestionado) y se midió el ancho de tres formas independientes del delineador de producción: (a) lectura manual de los valores crudos, (b) energía espacial derivada de las 12 derivaciones sobre ese mismo latido, (c) el propio delineador re-anclado al latido compartido.

**Hallazgo raíz**: `_reference_r_peak_idx()` (entonces) se llamaba independientemente por derivación -- en los 12/12 casos narrow, el latido elegido en V1 y el elegido en V6 caían en puntos del registro separados entre 262ms y 5368ms, nunca el mismo complejo. Esto invalida la comparación cruzada V1/V6 que el criterio de RBBB exige, además de subestimar el ancho medido.

**Reparto de los 12** (ver tabla completa en la respuesta original, no repetida aquí): **9/12 bug de medición confirmado** (195, 310, 424, 680, 1024, 1123, 1232, 1237 con alta confianza + 1157 probable, complicado por una PVC documentada cerca del latido analizado) -- el QRS real supera 120ms cuando se mide en un latido sincronizado. **1/12 realidad clínica probable** (269 -- ~90-116ms consistente en 3 métodos y con ancla verificada por amplitud). **2/12 no concluyentes**: 957 (justo en el límite, ~112-128ms según el método) y 1049 (PTB-XL marca este registro con `static_noise: stark` en su propia metadata -- ruido severo confirmado, no supuesto).

**Hallazgo colateral, no en el alcance de esta auditoría pero relevante**: el reporte alemán original de `ecg_id=1024` dice literalmente *"unvollständiger rechtsschenkelblock"* (RBBB **incompleto**), contradiciendo su propia etiqueta `CRBBB: 100.0` -- una inconsistencia del dataset PTB-XL, no del detector.

**Recomendación resultante**: arreglar la sincronización V1/V6 es fontanería (arreglable sin el validador), no una pregunta de criterio -- ver la entrada de arriba, misma fecha, donde se implementa. La pregunta genuina para el validador queda acotada a los casos donde el criterio qR-sin-R'-terminal decide, no a este grupo.

## 2026-08-12 — Detector BBB, Fase 3: detector morfológico RBBB/LBBB, validado contra 50 casos reales de PTB-XL

**Contexto**: las 3 piezas de apoyo ya estaban listas -- criterio morfológico con umbrales firmados por el validador, delineador de QRS (`clinical/qrs_delineation.py`, Sub-Fase 2.5) y el set de 50 casos reales confirmados (`tests/ptbxl_bbb_validation_set.py`, 25 CRBBB + 25 CLBBB). Esta tanda las junta: un detector morfológico nuevo (`clinical/bbb_detector.py`), su integración en `ECGAnalyzer.detect_clinical_pattern()` reemplazando la sub-regla vieja (promedio de las primeras/últimas 10 muestras de una sola derivación, sin respaldo clínico), y la validación pedida contra los 50 casos reales, sin ajustar el criterio para mejorar los números.

### Paso 1 — El detector (`clinical/bbb_detector.py`, nuevo)

Criterio verbatim del validador (firma: validador clínico, Detector BBB, Fase 3, aprobación 2026-08-12), umbrales exactos:
- Umbral de disparo: QRS > 120 ms.
- RBBB, AMBOS obligatorios: (1) R' en V1 con prominencia ≥0.1 mV, terminal y dominante; (2) S en V6 con duración ≥40 ms y amplitud ≤-0.1 mV, polaridad final negativa. RSR' en V1 sin S ancha en V6 → indeterminado, nunca RBBB forzado.
- LBBB, AMBOS obligatorios: (1) QS/rS en V1; (2) R ancha/dominante en V6 sin Q septal (<-0.05 mV).
- Indeterminado: cualquier QRS>120ms que no cumpla los criterios duros de ninguna rama -- nunca se fuerza L o R.

**Decisiones de implementación NO dictadas por el validador** (documentadas explícitamente en el módulo, mismo principio que la ambigüedad ya resuelta en `qrs_delineation._isoelectric_baseline`):
- "Duración de S" se mide por cruce de cero (el validador dio el umbral clínico, no el método operacional).
- "R'/dominante/terminal" se interpreta por SIGNO y ORDEN de las deflexiones, no por el `type` interno que asigna el delineador -- ver hallazgo de plomería más abajo, es la razón de este diseño.
- La UBICACIÓN del latido de referencia usa un buscador local nuevo por amplitud ABSOLUTA, no `ECGAnalyzer.detect_r_peaks()` -- ver hallazgo de plomería más abajo.
- El latido analizado se elige por regularidad de RR (no una posición fija) entre los picos de referencia.

### Dos hallazgos de plomería, descubiertos por la propia validación (no ajustes al criterio clínico)

Antes de validar contra datos reales, correr el detector sobre las primeras 3 RBBB/3 LBBB reales expuso dos bugs reales en cómo este módulo nuevo consumía piezas ya existentes -- ninguno de los dos toca `qrs_delineation.py` (Sub-Fase 2.5, intacto, sigue pasando sus propios tests) ni `ECGAnalyzer.detect_r_peaks()` (compartido por el resto de la app, sin tocar):

1. **Etiquetado del delineador vs. semántica clínica de "R'"**: `qrs_delineation._find_subpeaks()` llama "R" al candidato de mayor amplitud ABSOLUTA del complejo, sin importar su posición -- válido para un QRS de un solo lóbulo (su caso de diseño en la Sub-Fase 2.5), pero en el patrón rsR' de RBBB la R' terminal suele ser MÁS ALTA que la r inicial, así que el delineador la etiqueta "R" a ELLA, no a la r inicial -- `_peak_of_type(peaks, "R_prime")` nunca encontraba nada. Confirmado por ejecución: con la lógica por `type`, 0/25 RBBB reales mostraba una R' detectada. Arreglo: `bbb_detector.py` interpreta "R'" por SIGNO y ORDEN (la segunda deflexión positiva del complejo, sea cual sea su label interno), no por el nombre que le puso el delineador.
2. **`ECGAnalyzer.detect_r_peaks()` no puede ver un QRS predominantemente negativo**: busca picos solo por ENCIMA de un umbral positivo (`mean+0.3*std`) -- exactamente incapaz de localizar el patrón QS que LBBB produce en V1. Confirmado por ejecución sobre un caso real: la R (QRS) verdadera en V1 es una deflexión de **-2.7 mV**; `detect_r_peaks()` nunca la veía, anclaba ~200ms más tarde en la onda T (positiva, ~300ms de ancho -- mucho más ancha que cualquier QRS real), y el delineador terminaba delineando la onda T pensando que era el QRS. Arreglo: `bbb_detector.py` usa un buscador de latido LOCAL (`_detect_reference_peaks()`, sobre `abs(señal)`) -- no modifica `detect_r_peaks()`.

Ambos arreglos son de PLOMERÍA (qué latido analizar, cómo leer la salida del delineador) -- ningún umbral clínico (0.1mV, 40ms, -0.1mV, -0.05mV) cambió. El segundo arreglo, en particular, tuvo un efecto dramático: subió LBBB de 0/25 a 19/25 confirmados.

**Limitación de plomería NO resuelta, documentada, no perseguida más**: `qrs_delineation._isoelectric_baseline()` calcula el baseline pre-QRS relativo al `r_idx` que se le pasa (ventana R-120ms a R-80ms). Cuando el latido de referencia es un componente TARDÍO de un complejo multi-lobulado (como la R' dominante de RBBB), esa ventana puede solaparse con componentes anteriores del propio complejo (r, s) -- el baseline queda contaminado, y el escaneo de onset (que se detiene en el PRIMER retorno a la banda de baseline, sin exigir sostenimiento, a diferencia del offset) puede cerrarse sobre la propia subida de R' en vez de llegar hasta el verdadero inicio del complejo. Esto probablemente contribuye al subregistro de QRS visto en varios RBBB reales (ver matriz abajo). No se tocó `qrs_delineation.py` (Sub-Fase 2.5, validado y fuera de alcance de esta fase) -- queda documentado como candidato para una fase de consolidación posterior, no una decisión tomada aquí.

### Paso 2 — Integración en `detect_clinical_pattern()` (`clinical/ecg_analyzer.py`)

Nuevo parámetro opcional `leads: Optional[Dict[str, np.ndarray]]` (mismo shape que usa `clinical/ecg12.py`). Nuevo helper `_classify_bbb()`, usado en los DOS puntos donde el método ya entraba a clasificar un QRS ancho:
- Con V1 y V6 verificadas por NOMBRE (no por posición) en `leads` → `clinical.bbb_detector.detect_bundle_branch_block()` → RBBB / LBBB / "Bloqueo de rama indeterminado".
- Sin V1/V6 → "Bundle Branch Block" genérico, como siempre, pero ahora con una razón honesta ("solo 1 derivación disponible, no se puede distinguir la rama sin V1/V6") en vez de forzar una rama con el hack retirado.
- Si el propio `detect_bundle_branch_block()` no confirma QRS>120ms con SU medición (más estricta, vía delineador sobre V1/V6 específicamente) aunque la medición externa del método sí lo haya hecho: cae al genérico honesto, nunca afirma "no es BBB".

Los call sites existentes (`app/supermodules/ecg_monitor/pages.py`, `domain/physiology/ml/ecg_classification.py`) no pasan `leads` hoy -- siguen exactamente igual que antes (parámetro opcional, retrocompatible), reciben el genérico honesto. Wiring de la UI en vivo para pasar V1/V6 reales queda fuera de esta tanda (no pedido).

### Paso 3 — Validación contra los 50 casos reales (la prueba de fuego)

`tests/test_bbb_detector_validation.py` -- corre el detector completo (localización de latido incluida) sobre V1/V6 reales de los 50 casos confirmados de PTB-XL. **Matriz de confusión, sin ajustar nada para mejorar el número:**

| Real | RBBB | LBBB | Indeterminado | QRS≤120ms (no evaluado) |
|---|---|---|---|---|
| RBBB (25) | 0 | 1 | 12 | 12 |
| LBBB (25) | — | 19 | 4 | 2 |

Un error grave (RBBB→LBBB, `ecg_id=512`, V1 con dominante negativa muy débil, -0.14 mV -- un caso límite, no un patrón sistemático repetido en los otros 24 RBBB). Ningún LBBB→RBBB.

### Interpretación honesta

- **LBBB: 19/25 (76%) confirmados, 4 indeterminados, 2 sin evaluar, 0 falsos.** Es una validación real: el criterio + el detector, tal como están, distinguen LBBB verdadero la mayoría de las veces, con el resto cayendo en "no lo sé" en vez de un error.
- **RBBB: 0/25 confirmados.** No es una validación -- es un hallazgo. La mayoría (12/25) ni siquiera alcanza el umbral de 120ms con la medición propia del detector (vía delineador sobre V1/V6), y otros 12/25 llegan a indeterminado porque V1 no muestra una segunda deflexión positiva distinguible (muchos RBBB reales de este set presentan un patrón qR simple, sin el notch RSR' clásico que el criterio exige explícitamente como "R' terminal y dominante"). Ambas causas son honestas, no forzadas: el criterio pide una morfología específica (RSR') y en su ausencia reporta "no lo sé" en vez de adivinar -- exactamente el comportamiento pedido. La limitación de plomería del baseline contaminado (arriba) es una causa plausible adicional del subregistro de QRS en varios de estos 12 casos, no descartable con la evidencia actual.
- **El criterio nunca se ajustó para mejorar estos números** -- los dos arreglos que sí se hicieron (etiquetado R'/orden, localización de latido por amplitud absoluta) son de plomería, verificados por su efecto en LBBB (0→19/25) antes de tocar nada del lado RBBB, y el resultado de RBBB se dejó como salió.
- **1 error grave sobre 50 casos, ninguno sistemático**: la regla "nunca forzar" cumplió su propósito -- de los 24/25 RBBB no confirmados, ninguno se convirtió en un LBBB falso; se declararon indeterminados o sin evaluar.

### Verificación

- `tests/test_bbb_detector.py` (17 tests, nuevo): reglas de clasificación puras contra `QrsDelineation` construidos a mano (rápido, sin depender de que una señal sintética reproduzca la morfología exacta tras el delineador real) + 3 casos extremo a extremo con señales sintéticas simples (LBBB de un lóbulo, QRS angosto, sin latido válido).
- `tests/test_bbb_detector_validation.py` (1 test, nuevo): la matriz de arriba, corrida extremo a extremo contra los 50 casos reales -- se salta con motivo explícito si PTB-XL no está accesible, nunca fabrica un resultado.
- `pytest tests/ -q`: 395 passed (368 previos + 17 + 1 nuevos), sin regresión.
- Compile-check limpio en `clinical/bbb_detector.py`, `clinical/ecg_analyzer.py`.
- `qrs_delineation.py`: sin tocar, sus propios tests (Sub-Fase 2.5) siguen pasando igual.
- Motor hemodinámico y los 3 puntos fijos: no tocados por esta tanda (esta tanda no toca `simulation_engine.py` ni `domain/physiology/hemodynamics/`).
- Servidor real (`streamlit run app/main.py`, puerto 8533): HTTP 200; proceso detenido tras la verificación.

**Con esto se cierra el Detector BBB** (Fase 1 diseño → Sub-Fase 2.5 delineador → Fase 3 detector + validación). Pendiente, fuera de alcance de esta tanda: wiring de V1/V6 reales en la UI en vivo (ningún call site pasa `leads` hoy); investigar más a fondo la limitación de baseline contaminado en `qrs_delineation.py` si se decide perseguir mejorar el recall de RBBB; considerar si vale la pena una categoría IRBBB/ILBBB (incompletos) aparte, deliberadamente excluida de este set de validación desde su diseño.

## 2026-08-12 — Bloque 4, cierre: meseta a 7d etiquetada honestamente en la línea de tiempo de Twin OS

**Contexto**: auditoría previa (misma fecha) confirmó que el "congelamiento" a horizontes largos (stress/hipoxia desde 2h, sepsis desde 24h de los horizontes muestreados) casi no importa en la práctica -- el modo caso solo muestra `now`, así que ningún estudiante diagnostica sobre un valor congelado. El único punto real de exposición es la vista "Última trayectoria persistida" del simulador de escenarios de Twin OS (`render_ups_scenario_simulator`), donde el gráfico FC/SpO2 sí puede aplanarse en 24h/7d -- fisiológicamente correcto (estado agudo no evolucionado) pero mudo: podía leerse como "el paciente se estabilizó" en vez de "el simulador no modela evolución con tratamiento a lo largo de días". Se decidió NO tocar ningún valor -- la meseta es correcta para lo que el modelo representa -- solo declarar honestamente su naturaleza cuando aparece de verdad.

### El cambio (`app/supermodules/twin_shell/pages.py`)

- **`_tail_is_plateaued(values, tail_len=2)`** (función pura, nueva): detecta si una serie de horizontes se movió en algún punto y luego se quedó fija en su cola. Genérica -- no una lista de escenarios hardcodeada. Dos condiciones, ambas necesarias:
  1. Los últimos `tail_len` valores son prácticamente idénticos (tolerancia 0.01, solo por punto flotante -- `min(1.0, minutes/X)` sin ruido gaussiano da el MISMO float una vez capado, no uno "parecido").
  2. La serie completa tiene rango > 0 -- es decir, SÍ cambió en algún punto anterior.
  La segunda condición es la que evita marcar como "meseta" lo que en realidad es una foto constante por diseño: apnea/EPOC/hipertensión son el mismo valor en los 6 horizontes desde `now` (ver entrada de abajo, Bloque 4/Fase 2, misma fecha) -- eso no es el mismo problema que stress/hipoxia/sepsis, que arrancan de un valor y luego saturan. Sin la segunda condición, la función habría tratado ambos casos por igual.
- **Aviso condicional, no general**: en la sección "Última trayectoria persistida", si `_tail_is_plateaued()` da verdadero para la serie de FC o de SpO2 mostrada (las dos únicas que ese gráfico grafica), se añade un `st.info` inmediatamente debajo del gráfico: *"Los últimos horizontes de esta trayectoria son idénticos. El simulador alcanzó su techo de progresión y dejó de evolucionar a partir de ahí -- modela la fisiología aguda, no la evolución clínica con tratamiento a lo largo de días. Esta meseta es la persistencia del estado agudo tal como lo calcula el modelo, no un pronóstico de que el paciente se mantendrá así."* Se decidió por la opción condicional (no una nota general en todo escenario) porque el alcance lo permitía sin complejidad excesiva -- ver más abajo por qué la cobertura resultante no es exactamente los 4 escenarios de la auditoría.
- **Ningún valor cambiado**: ni `SimulationEngine`, ni `case_bank.py`, ni `EVALUABLE_HORIZONS_BY_SCENARIO`, ni el modo caso clínico, ni el motor hemodinámico -- solo se añadió texto condicional en la vista de línea de tiempo.

### Cobertura real, verificada por ejecución (no la lista original de 4 escenarios)

La detección es sobre los datos efectivamente graficados (FC/SpO2), no sobre nombres de escenario -- eso produce una cobertura ligeramente distinta a los "4 escenarios" identificados en la auditoría textual, y es la correcta:
- **stress, hipoxia**: `min(1.0, minutes/120)` capa en 2h -- FC en 2h==24h==7d, distinto de `now`. Aviso SÍ dispara.
- **sepsis**: `min(1.0, minutes/360)` capa a las 6h -- de los horizontes muestreados, 2h (120min) aún no llegó al techo, pero 24h y 7d sí y coinciden. Aviso SÍ dispara.
- **fatiga**: su progresión (`minutes/1440`) sí satura a las 24h, pero los campos que este gráfico específico muestra (`hr`, `spo2`) están fijos en `_simulate_fatigue` sin depender de la progresión en absoluto (`hr=75`, `spo2=97` constantes) -- solo `fatigue_index`/`hrv`/`stress_level`/etc. capan, y esos no están en este gráfico. Aviso NO dispara para fatiga en esta vista -- correcto: mostrarlo sería describir una meseta que el gráfico no exhibe.
- **apnea, EPOC, hipertensión**: constantes desde `now` (rango 0) -- excluidos por la segunda condición, tal como se pretendía.
- **ejercicio, ansiedad**: recuperan a un valor de reposo fijo y se quedan ahí desde antes de 2h -- el aviso SÍ dispara para ellos también. Es una extensión honesta, no un error: el mismo límite real del simulador (deja de evolucionar más allá de cierto punto) también aplica a una recuperación congelada, no solo a un estado patológico sostenido.
- **sano, arritmia**: ruido gaussiano independiente en cada horizonte -- la cola nunca es exactamente idéntica por casualidad. Aviso no dispara (correcto, no hay meseta ahí).

### Verificación

- `pytest tests/ -q`: 377 passed (368 previos + 9 nuevos en `tests/test_timeline_plateau_note.py`, que cubre la función pura con series sintéticas y con la salida real de `SimulationEngine` para stress/hipoxia/sepsis/apnea/EPOC).
- Compile-check limpio en `app/supermodules/twin_shell/pages.py`.
- Servidor real (`streamlit run app/main.py`, puerto 8532): HTTP 200; proceso detenido tras la verificación.

**Con esto cierran los 4 arreglos del simulador de esta sesión**: ejercicio (número imposible, Bloque 4 previo), apnea/EPOC (fisiología fingida, Fase 2 de hoy), y ahora el congelamiento (meseta muda → etiquetada). Pendiente: Fase 3 del detector BBB.

## 2026-08-12 — Bloque 4, Fase 2: fisiología real de apnea y EPOC (Art. I — fisiología fingida → fisiología real)

**Contexto**: la auditoría (Fase 1) confirmó que en apnea y EPOC la "fase" solo cambiaba texto/metadatos, no los signos vitales que el UPS persiste — SpO2 nunca caía en la apnea real (bug de fórmula: `(minutes*2)%1` con enteros da siempre 0) y la exacerbación de EPOC no cambiaba SpO2 en absoluto (término `+(0 if exacerbation else 0)`, no-op en ambas ramas). El validador entregó rangos citados y resolvió el problema de escala (Fase 1, misma fecha). Esta tanda implementa: fisiología fingida → fisiología real, Art. I de la Constitución.

### Parte A — Apnea (`app/engines/simulation_engine.py::_simulate_apnea`)

- **Bug de fórmula corregido**: `(minutes*2) % 1` reemplazado. Con `minutes` entero (siempre lo es), esa expresión daba 0 para *cualquier* entero — no un problema de muestreo, el arousal era matemáticamente inalcanzable.
- **Foto determinista del evento crítico** (decisión del validador, Fase 1: el ciclo real de ~30-90s es inalcanzable por escala frente a horizontes de minutos/horas/días): el escenario ya no persigue el ciclo — muestra siempre el nadir del evento apneico. Verificado: los 6 horizontes (now/5min/30min/2h/24h/7d) dan **exactamente** `hr=55.0, spo2=82.0, rr=0.0, ahi=45` — determinista, no alterna.
- **AHI como ancla diagnóstica real, ya conectada al UPS**: `ahi` llegaba a `lungs.metrics.signals` (copiado por `_update_lungs()`) pero se perdía en `_respiratory_state()` (`domain/physiology/state/builder.py`) — nunca se convertía en `PhysiologicalDescriptor`, así que el UPS (y el Narrador Clínico, que solo lee del UPS) no podía citarlo. Se añadió la extracción (`if "ahi" in signals: ...`) — aditiva para los 12 escenarios, ninguno pierde nada. `build_context()` (narrador) es genérico (itera todos los descriptores sin lista fija) — no hizo falta tocar `narrator/context.py` ni `prompt.py`.
- **Verificado extremo a extremo** (sin llamar a la API real): `ahi=45.0` (`eventos/h`) aparece en `state.respiratory` y en el payload del narrador (`DescriptorContext`). El evento `HYPOXIA_SPO2_CRITICAL` (ya existente, umbral SpO2<90) se dispara automáticamente con spo2=82 en los 6 horizontes — el narrador (real, Anthropic) recibe AHI + eventos críticos repetidos como datos reales para explicar "desaturación recurrente" sin que se le haya escrito ningún texto canned (Art. I).
- **Honestidad de escala**: `get_scenario_description()` reescrita para dejar explícito que 82% es el nadir de un evento, no el SpO2 sostenido, y que AHI=45 es la métrica diagnóstica real.

### Parte B — EPOC (`_simulate_copd`)

- **Ciclo de 4h eliminado** (`(minutes // 240) % 2`): decisión del validador (Fase 1) — una exacerbación real dura días, no se alterna con la fase estable cada 4h; alternar por reloj interno no modela cuándo ocurre una exacerbación real (infección/contaminación, no un temporizador). El escenario ahora representa EPOC EXACERBADA de forma sostenida, siempre — ya no hay fase "estable" dentro de este escenario. Verificado: los 6 horizontes dan **exactamente** `hr=95.0, spo2=85.0, rr=28.0` en los 6.
- **Bug independiente también corregido**: el término de SpO2 sumaba 0 en ambas ramas (no-op) — nunca reflejó la exacerbación, ni siquiera en los minutos que la fórmula sí alcanzaba. Corregido junto con el ciclo.
- **CO2/hipercapnia**: omitido a propósito, no fingido — confirmado por lectura completa de `SimulationTimestep` (Fase 1) que el modelo no representa CO2 en ningún punto del esquema.

### Parte C — Procedencia y aislamiento

**Procedencia de cada rango nuevo** (firma: validador, Fase 2, 2026-08-12):
| Valor | Escenario | Estado |
|---|---|---|
| SpO2=82%, HR=55 (nadir del evento) | apnea | **CITADO** |
| AHI=45 (AOS severa, AASM AHI≥30) | apnea | **CITADO** |
| SpO2 basal EPOC estable 88-92% (documentado, no mostrado en este escenario) | copd | **CITADO** |
| SpO2=85% (exacerbada, <88% citado; 85 = valor redondo dentro del rango, sin ajustar a resultado) | copd | **CITADO** |
| Taquicardia/taquipnea (dirección) | copd | **CITADO** (dirección) |
| HR=95, RR=28 (magnitud exacta) | copd | **PENDING_VALIDATION** — heredados del valor que ya tenía el código, sin cita de magnitud |
| hrv, cardiac_output, stress_level, cognitive_state, eeg_activity, fatigue_index, muscle_activation, sympathetic/parasympathetic_tone, global_health, risk_level (ambos escenarios) | apnea, copd | **PENDING_VALIDATION** — sin cambio del valor previo, fuera del alcance de esta validación |

Todas las marcas viven como comentarios en el código, junto al valor, mismo patrón que `blood_pressure_references.py`.

**Aislamiento del motor — confirmado, no de memoria**: `HEMODYNAMIC_MODEL_ENABLED_SCENARIOS = {"healthy", "hypertension", "sepsis"}` sin cambios; cero referencias a `hemodynamic`/`closed_loop`/`compute_and_attach` en todo `simulation_engine.py` (re-grepeado en esta tanda). Los 3 puntos fijos re-ejecutados tras el cambio: `healthy` MAP=93.33, `hypertension` MAP=102.66, `sepsis` MAP=57.60 (colapsado, converge) — **idénticos** a todas las tandas anteriores.

**Restricción de horizontes del modo caso**: apnea y EPOC siguen sin entrada en `EVALUABLE_HORIZONS_BY_SCENARIO` (sin restricción) — confirmado de nuevo tras el arreglo, no asumido: en los 6 horizontes, ambos escenarios quedan muy fuera de una banda de 4σ de "sano" (HR 60-84, SpO2 96-100, RR 12-20) — apnea (hr=55, spo2=82, rr=0) y EPOC (hr=95, spo2=85, rr=28), los 6 horizontes idénticos entre sí ahora (antes variaban por el ciclo roto). Comentario del código actualizado para reflejar el estado nuevo.

### Verificación

- Compile-check limpio en `simulation_engine.py`, `builder.py`, `case_bank.py`.
- Apnea/EPOC: 6 horizontes deterministas y idénticos entre sí (confirmado por ejecución, no asumido).
- AHI verificado extremo a extremo: UPS → payload del narrador.
- Motor hemodinámico: 3 puntos fijos idénticos, confirmado por ejecución real tras los cambios.
- `pytest tests/ -q`: 368 passed, sin regresión.
- Servidor real (`streamlit run app/main.py`, puerto 8531): HTTP 200; proceso detenido tras la verificación.

**Pendiente**: HR=95/RR=28 de EPOC exacerbada quedan con dirección citada pero magnitud sin citar (`PENDING_VALIDATION`) — actualizar si el validador da una cifra exacta. El resto de campos no cardiorrespiratorios de ambos escenarios (stress, fatiga, tono autonómico, etc.) tampoco tienen cita — no fueron parte de esta validación.

## 2026-08-12 — Cierre de la familia del bug de colisión de timestamps: 2 gemelos más, y el arreglo real no era el que se pensaba

**Contexto**: `get_snapshot_id_at()` se arregló el 2026-08-11 (Capa B: `ORDER BY rowid DESC` como desempate). `get_latest_snapshot_id()` quedó pendiente, marcada "fuera de alcance", y se reprodujo por esa vía. Esta tanda cierra ese gemelo, barre el repo por más, encuentra un tercero de alto riesgo (`get_latest_state()`, la función más usada del UPS), y en el camino descubre que el propio arreglo de Capa B **no bastaba** -- el diagnóstico real era otro.

### Barrida del repo: 3 gemelos totales, 2 casos revisados y descartados

Grep de `.limit(1)`/`.first()`/`scalar_one_or_none()` combinado con `order_by(...timestamp...desc` en todo el repo (excluyendo vendored/`_archive/`):
- **`get_snapshot_id_at()`** (`clinical_impression_repository.py`) -- ya arreglada 2026-08-11.
- **`get_latest_snapshot_id()`** (mismo archivo) -- gemela confirmada, arreglada en esta tanda.
- **`get_latest_state()`** (`repository.py`) -- tercer gemelo, encontrado en la barrida. Es la función MÁS usada de todo el UPS (18 llamadores en todo el repo: `app/main.py`, `twin_shell/pages.py`, el narrador, `ups_body_visual.py`, los módulos de comparación hemodinámica, etc.) -- el de mayor riesgo real de los tres. Arreglada en esta tanda.
- **`get_clinical_references_for_patient()`** (`clinical_reference_repository.py`) -- revisada y reportada como dudosa, NO tocada: ordena por `created_at.desc()` con `.limit(50)`, pero devuelve VARIAS filas, no una sola "la más reciente" -- una colisión ahí a lo sumo movería el borde de qué filas entran en el límite de 50, no resuelve el objeto equivocado como en los otros tres. Riesgo real pero de naturaleza distinta; no se tocó a ciegas.
- **`get_clinical_references_for_snapshot()`** (mismo archivo) -- revisada, sin riesgo: ordena por `descriptor.asc()`, devuelve TODAS las filas de un snapshot ya conocido, ninguna resolución por timestamp involucrada.
- **`app/clinical_db.py::list_patient_states()`** (capa SQLite cruda, `app/clinical_db.py`) -- revisada, sin riesgo: ordena por `id INTEGER PRIMARY KEY AUTOINCREMENT` real, ya inmune por diseño.
- **`src/rural_health/offline_support.py`** (la otra capa SQLite cruda citada en `CLAUDE.md`) -- revisada, sin patrón `ORDER BY` en absoluto.

### El hallazgo que cambió el diagnóstico: Capa B (tal como se aplicó el 2026-08-11) no alcanza

Se aplicó primero el arreglo ya probado (`ORDER BY timestamp DESC, rowid DESC`, desempate) a `get_latest_snapshot_id()`. Verificado con colisión forzada: 50/50 correctas. Pero al correr el test real 100 veces, **siguió fallando 2/100** -- la Capa B, tal como estaba especificada, no cerraba el gemelo.

Diagnóstico por reproducción (no se asumió): el fallo NO era un empate de timestamps -- eran timestamps DISTINTOS pero en el orden equivocado. Medido directamente: `datetime.now()` en esta máquina Windows generó, en llamadas consecutivas de instancias `DigitalTwinOrganism()` distintas, el segundo timestamp un microsegundo ANTES que el primero en 27 de 500 pares medidos (p.ej. `.380843` seguido de `.380842`). La Capa A (timestamp monótono, 2026-08-11) protege dentro de la vida de UN organismo -- no entre instancias nuevas creadas en sucesión rápida, que es exactamente lo que hace el helper de test `_save_demo_state()` (y lo que puede ocurrir en producción si se crean dos organismos para el mismo paciente casi simultáneamente). Un desempate por `rowid` no resuelve esto porque no hay empate que desempatar: `ORDER BY timestamp DESC` ordena mal de forma completamente determinista, sin ninguna ambigüedad que un tie-break pueda corregir.

**Arreglo real, aplicado a `get_latest_snapshot_id()` y `get_latest_state()`:** `rowid` deja de ser un desempate y pasa a ser el ÚNICO criterio de orden -- `ORDER BY rowid DESC`, sin ninguna referencia a `timestamp` en la cláusula. Válido porque `save_state()` es la única vía de escritura de snapshots y siempre inserta el estado recién calculado hacia adelante, nunca uno retroactivo -- orden de inserción y recencia cronológica coinciden por invariante de la aplicación, no por el reloj del sistema, y `rowid` es completamente ajeno a `datetime.now()`. `get_snapshot_id_at()` (que filtra por IGUALDAD de timestamp, no por orden) no se tocó -- ahí sí es un empate genuino, y el desempate por `rowid` sigue siendo la resolución correcta.

### Verificación

- Colisión forzada (2 snapshots, mismo timestamp exacto), 50/50 corridas: ambas funciones resuelven al snapshot correcto.
- **Reproducción real del mecanismo** (2 `DigitalTwinOrganism()` nuevos en sucesión rápida, 500 corridas): `get_latest_snapshot_id()` y `get_latest_state()` resuelven correctamente **500/500** -- incluye los casos con timestamp invertido, no solo empatado.
- El test antes flaky (`test_get_latest_snapshot_id_matches_get_latest_state`) corrido 150 veces en procesos frescos tras el arreglo real: **0/150 fallos** (con el intento de Capa B solo: 2/100).
- Grep de llamadores de `get_latest_snapshot_id()`/`get_latest_state()`: todos con la misma firma `(session, patient_id)`, ninguno depende del criterio interno de orden -- el cambio de `ORDER BY` es transparente para el caso de una sola fila (la inmensa mayoría).
- `py_compile` limpio en ambos archivos.
- `pytest tests/ -q` corrido 3 veces seguidas: 368 passed las 3, estable.
- Servidor real (`streamlit run app/main.py`, puerto 8530): HTTP 200; proceso detenido tras la verificación.

**Pendiente**: `get_clinical_references_for_patient()` (riesgo bajo/distinto, reportado arriba, no tocado) -- decidir aparte si vale la pena el mismo tratamiento. Con esto, la familia de "resolver una única fila por timestamp sin criterio de orden inmune al reloj" queda cerrada en las 3 funciones que sí tenían el patrón de riesgo alto.

## 2026-08-12 — Docs: cierre de pendientes — `COMO_EJECUTAR.md` corregido contra código vivo, `RESUMEN_BUILD.md` archivado con advertencia

**Contexto**: cierre de los 2 pendientes dejados por la mini-tanda de limpieza anterior (mismo día). Ningún cambio de código en esta tanda -- solo `.md`.

### Ítem A — `COMO_EJECUTAR.md`: auditado y corregido contra el código vivo

Verificado, no asumido: `app/pages/` **no existe como directorio** en el repo (confirmado por listado directo) -- las "Opción B" (`app/pages/12_Academia_Inteligente.py`) y "Opción D" (`app/pages/1_ECG_Monitor.py`) apuntaban a scripts que no existen. "Opción A" y "Opción C" compartían el mismo comando (`streamlit run app/main.py`) con navegación distinta -- redundantes una vez corregidas. Las 4 "Opciones" se colapsaron en **una sola forma canónica**, con la navegación interna real como sub-bullets.

Verificaciones puntuales antes de decidir qué conservar (no de memoria -- la tanda anterior ya advirtió que "Exportar segmento" parecía dudoso y resultó cierto):
- `RUN_BIOCORE.bat`: confirmado que NO tiene menú "Selecciona una opción (1-5)" -- lanza `streamlit run app/main.py` directo. Corregido.
- Control por gestos/voz/"JARVIS AI Copilot": confirmado por comentario explícito en `app/main.py` que `hands_off_mode.py`/`gesture_controller.py` se **borraron del repo** (2026-07-03) y que JARVIS se retiró. Sección eliminada por completo.
- `ANTHROPIC_API_KEY` (setup del Narrador Clínico): **conservado**, sigue siendo necesario y correcto -- solo se quitó el encuadre "JARVIS".
- Botones "💾 Guardar estado" / "📝 Generar ejercicio" (Tips): grep sin resultados en todo `app/` -- no existen. Retirados.
- "Exportar segmento para investigación" (Tips): confirmado real y vigente (`app/main.py`, vista "Investigación" del ECG Lab) -- conservado, con la ruta correcta.
- Sliders de HR/HRV/RR en Digital Twin OS: confirmados reales (`app/supermodules/twin_shell/pages.py`) -- conservados, solo corregido el nombre del hub (era "Digital Twin Hub", no existe).

Secciones que ya eran ciertas y no se tocaron: Inicio rápido (3 pasos), Primera vez que ejecutas, la mayoría de Configuración (ModuleNotFoundError, puerto, caché, reinstalar), Soporte.

### Ítem B — `RESUMEN_BUILD.md`: archivado con advertencia, NO reescrito

Verificado dónde archiva este repo lo histórico antes de mover nada: `_archive/` (155+ archivos) es exclusivamente código retirado, sin precedente de contener markdown de reportes; `docs/especialidades/` resultó ser OTRO doc igual de obsoleto (describe una arquitectura "BIOCORE AI OS v3.0" -- `core/specialties/`, `core/digital_twins/`, `core/ai/automatic/` -- que tampoco existe en el repo), no una convención de archivo histórico. Sin convención clara para markdown, se aplicó la regla de respaldo del propio pedido: **se queda donde está**, con una cabecera de advertencia al inicio (formato blockquote) señalando que es un reporte histórico fechado 2026-06-10, que no refleja el estado actual, y que remite a `CHANGELOG.md` para el estado vivo. El cuerpo del documento no se tocó -- ni una palabra reescrita como si fuera vigente.

### Hallazgo no buscado durante la verificación (no corregido aquí -- ya documentado como pendiente)

`pytest tests/ -q` falló una vez (`test_clinical_impression.py::test_get_latest_snapshot_id_matches_get_latest_state`, `assert latest_id == second_snapshot_id`) en la primera corrida de esta tanda -- pasó en aislamiento y en una segunda corrida completa (368 passed). Es la MISMA clase de bug ya diagnosticado y parcialmente arreglado el 2026-08-11 (colisión de timestamp en snapshots), manifestándose por una vía distinta: `get_latest_snapshot_id()` (`domain/physiology/state/clinical_impression_repository.py`) nunca recibió la Capa B (desempate por `rowid`) -- solo `get_snapshot_id_at()` la recibió, deliberadamente, y quedó anotado en el CHANGELOG del 2026-08-11 como "candidato a una tanda de consolidación". Además, el helper de test `_save_demo_state()` (`tests/test_clinical_impression.py`) crea DOS instancias nuevas de `DigitalTwinOrganism()` en sucesión rápida -- la Capa A (timestamps monótonos) protege dentro de la vida de UN organismo, no entre instancias distintas creadas en el mismo instante. No se tocó en esta tanda (fuera de alcance -- esta tanda es solo docs); confirma que el pendiente anotado el 2026-08-11 sigue vigente y ahora tiene una reproducción real, no solo teórica.

### Verificación

- `pytest tests/ -q`: 368 passed (segunda corrida, estable) -- el único fallo visto fue el hallazgo de arriba, no causado por esta tanda (imposible: esta tanda no tocó ningún `.py`).
- Servidor real (`streamlit run app/main.py`, puerto 8529): HTTP 200; proceso detenido tras la verificación.
- Confirmado: no se creó ningún doc nuevo de "estado del proyecto" -- se editaron los 2 archivos existentes (`COMO_EJECUTAR.md` corregido en el sitio, `RESUMEN_BUILD.md` con cabecera prepended). El CHANGELOG sigue siendo la única fuente de estado vivo.

**Pendiente**: aplicar la Capa B (`ORDER BY rowid DESC`) también a `get_latest_snapshot_id()`, o resolver la colisión de otra forma -- ahora con reproducción real (ver hallazgo arriba), ya no solo teórico. Fuera de alcance de esta tanda de docs.

## 2026-08-12 — Mini-tanda de limpieza: `render_top_bar()` huérfana, loader PTB-XL duplicado, docs de onboarding desactualizados

**Contexto**: limpieza de deuda menor acumulada durante la sesión. 3 ítems de bajo riesgo, cada uno verificado por vigencia antes de tocarlo (el repo cambió mucho en las tandas recientes).

### Ítem 1 — `render_top_bar()` (código muerto)

Confirmada huérfana por grep (cero llamadores vivos fuera de `_archive/`) — quedó sin llamador al retirarse `render_home_page()` en el Bloque 1 (2026-08-09), su único consumidor. Retirada de `app/main.py`, con comentario en el sitio explicando por qué. Sin cascada: no tenía imports ni helpers exclusivos.

### Ítem 2 — Loader PTB-XL duplicado: retirada la copia huérfana

Diagnóstico primero: grep confirmó que `app/supermodules/ecg_monitor/pages.py` no tiene NINGÚN llamador vivo salvo `get_case_database()` -- su `get_ptbxl_records()`/`load_ptbxl_record()` (arregladas en la tanda de PTB-XL, 2026-08-10) nunca se ejecutan, porque todo `run()`/`main()` de ese módulo es inalcanzable. La copia viva es `_ecg_get_ptbxl_records()`/`_ecg_load_ptbxl_record()` en `app/main.py`, llamada desde `render_ecg_monitor_page()` (el "🫀 ECG Lab" real).

Aplicado el patrón "huérfana → retirar", no el de consolidación (`_diagnostic_options`/PA compartida): no había dos llamadores vivos que consolidar, solo uno vivo y uno muerto. Se retiraron `get_ptbxl_records()`, `load_ptbxl_record()`, el bloque de UI que las invocaba (`elif data_source == "Base de datos PTB-XL":`), la opción "Base de datos PTB-XL" del radio de fuentes, y los imports de `clinical.ptbxl_metadata` que quedaron sin uso en ese archivo (incluida su rama de fallback `ImportError`). `app/main.py` no se tocó -- ya era la copia correcta.

### Ítem 3 — Docs de onboarding: corregidas las afirmaciones falsas, dos quedan para reportar

**`QUICKSTART.md` — corregido en el sitio** (no reescrito de cero, secciones intactas donde ya eran ciertas: Requisitos, Instalación, Solución de problemas genérica, Configuración avanzada, Soporte). Se corrigieron:
- Navegación: eliminada la página "Home" inexistente; "Research Hub"/"Digital Twin Hub" (no existen como hubs propios) reemplazados por la estructura real de 3 hubs (Digital Twin OS, Learning Hub, Clinical Hub); "ECG Monitor"/"ECG 12-Derivaciones" como entradas separadas reemplazadas por "🫀 ECG Lab" (fusionadas 2026-07-14); añadidas las entradas reales que faltaban (HRV Analysis, Biomarkers Lab, Patient Pipeline).
- Características principales: retirada la descripción de "Gemelo Digital Interactivo" (la cáscara de Academia, retirada 2026-08-09) y "Misiones Clínicas" (retiradas); "Chatbot IA del Tutor" corregido -- no es un chatbot de preguntas libres, es el Narrador Clínico real fundamentado en el UPS.
- Estructura del proyecto: quitadas referencias a `app/pages/*.py` y `app/biomedical_tutor.py` (eliminados hace varias tandas), reemplazadas por la estructura real (`app/engines/digital_twin_organism.py`, `app/supermodules/`, `domain/physiology/`, `clinical/`).
- Primeros pasos / Próximos pasos: quitadas las referencias a Misiones/tab "Tutor IA Biomédico"/Digital Twin Hub, reemplazadas por el flujo real (Digital Twin OS → Narrador Clínico; Academia → Lecciones y Casos → quiz).
- Sección 2: "Research/Simulation/AI/Hardware hubs" (no existen) corregido a los 3 hubs reales.

**`COMO_EJECUTAR.md` y `RESUMEN_BUILD.md` -- NO tocados, reportados para decidir aparte.** Verificado por qué no son candidatos a corrección puntual en esta tanda:
- `COMO_EJECUTAR.md`: su estructura organizativa central son 4 "Opciones" de ejecución (`Opción A/B/C/D`), de las cuales 3 apuntan a scripts que ya no existen (`app/pages/12_Academia_Inteligente.py`, `app/pages/1_ECG_Monitor.py`) o a features eliminadas (JARVIS/AI Hub). Corregir esto no es tocar líneas sueltas -- es rediseñar la sección organizadora del documento. Además, una verificación puntual (`Exportar segmento`, mencionado en Tips) resultó ser **cierta** -- confirma que una pasada segura de corrección exigiría verificar cada afirmación contra el código vivo, un audit completo, no una limpieza de deuda menor.
- `RESUMEN_BUILD.md`: no son docs vivos de onboarding -- es un reporte de sesión de build fechado 2026-06-10 ("RESUMEN EJECUTIVO — BUILD SESSION"), congelado describiendo un estado que decenas de tandas posteriores (documentadas en este mismo CHANGELOG) superaron por completo. Casi el 100% de sus afirmaciones sustantivas están obsoletas (`app/biomedical_tutor.py`, `physiology_core.py`, `digital_twin.py`, `app/pages/12_Academia_Inteligente.py`, JARVIS/AI Hub, Misiones/Pacientes Virtuales). Por su naturaleza de reporte fechado, no de documentación viva, corregirlo línea a línea no tiene sentido -- la decisión real es si se reescribe como documentación actual o se archiva con una nota de "histórico, ver CHANGELOG.md".

### Verificación

- Grep de `render_top_bar`, `get_ptbxl_records`, `load_ptbxl_record` (sin prefijo `_ecg_`): cero coincidencias vivas fuera de comentarios explicativos y `_archive/`.
- `py_compile` limpio en `app/main.py` y `app/supermodules/ecg_monitor/pages.py`.
- `pytest tests/ -q`: 368 passed, sin regresión.
- Servidor real (`streamlit run app/main.py`, puerto 8528): HTTP 200; proceso detenido tras la verificación.

**Pendiente**: decidir si `COMO_EJECUTAR.md` se reescribe (auditoría completa, afirmación por afirmación) o se recorta a lo mínimo verificable; decidir si `RESUMEN_BUILD.md` se reescribe como doc vivo o se archiva con nota histórica. Ninguna de las dos decisiones se tomó en esta tanda.

## 2026-08-11 — Deuda: bug de producción de colisión de timestamps en snapshots — arreglo en dos capas, flaky muerto

**Contexto**: `tests/test_twin_shell_case_hemodynamics.py` era intermitente (medido: 9/100 corridas en procesos aislados). El diagnóstico (tanda anterior) confirmó que NO era un test frágil — es una condición de carrera real en producción, que el test destapaba con baja probabilidad. Esta tanda implementa el arreglo en las dos capas ya diagnosticadas y confirma que el flaky desaparece por completo.

### Cadena causal (confirmada con evidencia, no teorizada)

`DigitalTwinOrganism.timestamp` se asignaba con `datetime.now()` (`app/engines/digital_twin_organism.py`), una vez por cada uno de los 6 horizontes que genera `run_rich_scenario()` en ráfaga, sin pausa entre ellos. La resolución real del reloj en esta máquina, medida: 20.000 llamadas consecutivas a `datetime.now()` devolvieron solo 2 valores distintos. Cuando dos horizontes (típicamente el último y uno anterior) compartían timestamp exacto, `get_snapshot_id_at()` (`domain/physiology/state/clinical_impression_repository.py`) — que resolvía por `(patient_id, timestamp)` con `.limit(1)` y sin `ORDER BY` — devolvía de forma no determinista una de las dos filas. Confirmado a nivel de fila: en una colisión real, resolvió el snapshot SIN las referencias clínicas (el horizonte anterior) en vez del que sí las tenía (el último, donde `create_clinical_reference()` las adjunta por id capturado directamente, no por timestamp). Resultado: la comparación de divergencia entre PA calculada y referencia clínica desaparecía silenciosamente para el usuario, en Twin OS y Academia (mismas funciones compartidas) — medido en ~1-2% de los casos por escenario.

### Capa A — raíz: timestamps monótonos (`app/engines/digital_twin_organism.py`)

En `update_from_sensors()`: `self.timestamp = now if now > self.timestamp else self.timestamp + timedelta(microseconds=1)` en vez de `self.timestamp = datetime.now()` directo. Garantiza estrictamente creciente dentro de la vida del organismo, incluso cuando el reloj del sistema no avanza entre llamadas.

### Capa B — defensa: desempate determinista (`domain/physiology/state/clinical_impression_repository.py`)

`get_snapshot_id_at()` ahora añade `.order_by(text("rowid DESC"))` antes de `.limit(1)`. Se descartaron `id` (UUID aleatorio, sin orden temporal) y `created_at` (también `datetime.now()`, mismo problema de resolución) como criterio de desempate — el `rowid` implícito de SQLite es estrictamente secuencial por inserción, verificado empíricamente que no depende del reloj del sistema. Cuando no hay empate (el caso normal), la cláusula no cambia el resultado.

Ninguna capa sustituye a la otra: A elimina la colisión conocida en el origen; B protege ante cualquier otra fuente de colisión no prevista (p.ej. dos `DigitalTwinOrganism` distintos para el mismo paciente en el mismo instante).

### Verificación

- **Capa A aislada**: 6 llamadas seguidas a `update_from_sensors()` en un organismo nuevo → 7 timestamps (inicial + 6), todos distintos y estrictamente crecientes.
- **Capa A contra el escenario real**: se repitió la misma medición de 300 corridas de `run_rich_scenario()` que encontró el bug — **0/300 colisiones tras el arreglo** (antes: 31/300).
- **Capa B aislada**: colisión forzada (dos `SnapshotRecord` del mismo paciente, mismo timestamp exacto, solo el segundo con `ClinicalReferenceRecord` adjunta) repetida 50 veces → **50/50 resoluciones correctas** (siempre el snapshot con las referencias).
- **Caso normal sin colisión, sin cambio de comportamiento**: los 3 escenarios habilitados (`healthy`/`hypertension`/`sepsis`) vía `_attach_calculated_pa_to_case()` real siguen coexistiendo con 3 referencias clínicas cada uno, `provenance=MODELO_HEMODINAMICO`, igual que siempre.
- **El flaky, muerto**: `test_divergence_citation_is_correct_per_scenario_in_twin_shell_mode_too` corrido 100 veces en procesos frescos tras el arreglo → **0/100 fallos** (antes del arreglo: 9/100).
- Otros consumidores de `get_snapshot_id_at()` revisados por grep (`app/supermodules/twin_shell/pages.py` ×2, `tests/test_academia_case_hemodynamics.py`, `tests/test_ups_state.py`): todos llaman con la misma firma `(session, patient_id, timestamp)`, ninguno asume el orden interno de desempate — el `ORDER BY` añadido es aditivo, no rompe ningún llamador.
- `py_compile` limpio en ambos archivos modificados.
- `pytest tests/ -q`: 368 passed, estable (no "verde con suerte" — la corrida de 100 repeticiones del test antes flaky es la prueba de estabilidad real).
- Servidor real (`streamlit run app/main.py`, puerto 8527): HTTP 200; proceso detenido tras la verificación.

**Nota relacionada, no tocada aquí**: `get_latest_snapshot_id()` (mismo archivo) tiene la misma ambigüedad estructural (`ORDER BY timestamp DESC LIMIT 1`, sin desempate) — la Capa A la vuelve inofensiva en la práctica (ya no hay colisiones que desempatar), pero no se le añadió el mismo `ORDER BY` de la Capa B porque no era el alcance pedido en esta tanda. Candidato a una tanda de consolidación si se quiere blindar también ese camino.

## 2026-08-10 — Bloque 4: `_simulate_exercise()` — `recovery_progress` acotado a [0,1] (HR ya no se va a negativo)

**Contexto**: `_simulate_exercise()` (`app/engines/simulation_engine.py`) calculaba `recovery_progress = (minutes-30)/60` sin acotar en la rama de recuperación (`minutes > 30`). A 2h daba HR=28 (undershoot sin sentido), a 24h HR=-1908, a 7d HR=-14580 — frecuencias cardíacas imposibles. Semántica decidida (Lectura A): el ejercicio agudo se resuelve; tras la recuperación (~90 min), HR vuelve a reposo y se queda ahí, no sigue bajando.

### Arreglo

`recovery_progress = max(0.0, min(1.0, (minutes - 30) / 60))` -- saturado a [0,1]. El `max(0.0, ...)` es defensivo: en la estructura real del código (`if minutes <= 30: ... else: recovery_progress = ...`), `recovery_progress` solo se calcula dentro de la rama `minutes > 30`, donde el numerador nunca es negativo -- confirmado por lectura directa, no se asumió. La fase de esfuerzo (`minutes <= 30`, HR de 120 a 160) vive en una rama completamente separada que no usa `recovery_progress` en absoluto -- el arreglo no la toca ni podría tocarla.

### Curva completa verificada (ejecución real, los 6 horizontes)

```
now    (min=     0) -> hr=120.00  rr=25.00  fatiga=20.00  hrv=35.00   (esfuerzo, sin cambios)
5min   (min=     5) -> hr=126.67  rr=27.50  fatiga=26.67  hrv=35.00   (esfuerzo, sin cambios)
30min  (min=    30) -> hr=160.00  rr=40.00  fatiga=60.00  hrv=35.00   (pico de esfuerzo, sin cambios)
2h     (min=   120) -> hr= 72.00  rr=16.00  fatiga=10.00  hrv=50.00   (reposo, antes: HR=28)
24h    (min=  1440) -> hr= 72.00  rr=16.00  fatiga=10.00  hrv=50.00   (reposo, antes: HR=-1908)
7d     (min= 10080) -> hr= 72.00  rr=16.00  fatiga=10.00  hrv=50.00   (reposo, antes: HR=-14580)
```

Sin negativos, sin descenso infinito, estable en HR=72/RR=16/fatiga=10/HRV=50 desde ~90min en adelante -- exactamente el centro de la banda de `_simulate_healthy()` (HR=72±3, RR=16±1, fatiga=10±5).

### Motor hemodinámico -- confirmado sin cambios

- `"exercise"` no está en `HEMODYNAMIC_MODEL_ENABLED_SCENARIOS = frozenset({"healthy", "hypertension", "sepsis"})` (`domain/physiology/hemodynamics/closed_loop_ups_bridge.py`) -- restricción estructural, `compute_and_attach_closed_loop_pressure()` lanza `HemodynamicModelNotEnabledError` para cualquier otro escenario, sin ruta alterna. Confirmado además por grep: cero referencias a `hemodynamic`/`closed_loop`/`compute_and_attach` en todo `simulation_engine.py` -- el motor y el simulador de escenarios están desconectados a nivel de import, no solo por nombre de escenario excluido.
- Los 3 puntos fijos re-ejecutados tras el arreglo, sin cambios: `healthy` HR=72 → MAP=93.33; `hypertension` HR=72 → MAP=102.66; `sepsis` HR=72 → MAP=57.60 (colapsado, converge). Idénticos a los valores ya validados en tandas anteriores.

### Restricción de horizontes del modo caso -- se mantiene, cambia la razón documentada

`EVALUABLE_HORIZONS_BY_SCENARIO["exercise"]` (`domain/physiology/scenarios/case_bank.py`) sigue siendo `{"now", "5min", "30min"}` -- **no cambia**, pero la razón sí: antes de este arreglo, `2h`/`24h`/`7d` daban valores físicamente imposibles (razón: bug). Después del arreglo, esos mismos horizontes dan HR=72.0 exacto -- el centro exacto de la banda de sano -- así que ahora son inevaluables por la misma razón que convulsión/estrés/ansiedad/hipoxia: indistinguibles de sano, no por valor roto. Comentario del código actualizado en el sitio (`case_bank.py`) para reflejar la razón nueva; las entradas de CHANGELOG anteriores que documentaron "roto"/"HR negativo imposible" (2026-08-06, matriz de evaluabilidad Trabajo 2; 2026-08-01, exclusión del lazo cerrado) describen correctamente el estado que medían EN ESE MOMENTO y no se reescriben -- esta entrada las supersede hacia adelante.

### Verificación

- `py_compile` limpio en `app/engines/simulation_engine.py` y `domain/physiology/scenarios/case_bank.py`.
- `pytest tests/ -q`: 368 passed, sin regresión.
- Servidor real (`streamlit run app/main.py`, puerto 8526): HTTP 200; proceso detenido tras la verificación.

## 2026-08-10 — PTB-XL: reparado el loader vivo (nunca funcionó — Art. I) + set de validación BBB para la Fase 3

**Contexto**: el diagnóstico previo confirmó que `load_ptbxl_record()` nunca cargó un registro real de PTB-XL (`pn_dir='ptbxl'` sin guion, slug inexistente en PhysioNet; 5 IDs de registro inventados que no existen en el dataset) y que `ptbxl_database.csv` (6.6MB, HTTPS directo) da la etiqueta (`scp_codes`) y ruta exacta (`filename_hr`) de cada registro real. Esta tanda repara el loader vivo y prepara, por separado, el set de validación BBB para la Fase 3 (todavía no autorizada).

### Hallazgo no buscado, antes de arreglar nada: DOS loaders vivos, no uno

Al ir a arreglar `app/supermodules/ecg_monitor/pages.py::load_ptbxl_record()` se confirmó por grep que ese módulo **no se llama desde ningún punto vivo de la app** (solo `get_case_database` se importa de ahí) — está huérfano desde la "Fusión ECG Monitor + ECG-12" (2026-07-14). El "🫀 ECG Lab" que el usuario realmente ve (`Clinical Hub`) llama a `render_ecg_monitor_page()` **en `app/main.py`**, que tiene su propia copia idéntica del mismo loader roto (`_ecg_get_ptbxl_records()`/`_ecg_load_ptbxl_record()`, copiada ahí en la "Tanda de rescate — Joya 1/3", 2026-07-13, con el mismo `pn_dir='ptbxl'` y los mismos 5 IDs inventados). Arreglar solo el supermódulo habría dejado la fachada intacta en la superficie real — se arreglaron **los dos**, sin consolidarlos en uno (esa es una decisión de arquitectura más grande, fuera del alcance de esta tanda — la duplicación entre ambos flujos de ECG Monitor ya era una decisión previa deliberada y documentada, no se reabrió aquí).

### Módulo compartido nuevo: `clinical/ptbxl_metadata.py`

Sin `import streamlit` (headless), para que tanto el loader vivo como el set de validación de test lo importen sin arrastrar UI:
- `ensure_ptbxl_database_csv()` / `load_ptbxl_database()`: descarga `ptbxl_database.csv` UNA vez, cacheado en `data/ptbxl_database.csv` (6.6MB, confirmado en disco tras esta tanda) — nunca las señales completas (~3GB), nunca en cada sesión.
- `resolve_ptbxl_wfdb_args(filename)`: implementa el patrón verificado (Sub-Fase 2.5 + diagnóstico): separa `filename_hr`/`filename_lr` (p.ej. `'records500/00000/00172_hr'`) en `(record_id, pn_dir)` — la carpeta completa va en `pn_dir`, `wfdb.rdrecord()` no resuelve subcarpetas dentro de `record_id`.
- `PtbxlUnavailableError(RuntimeError)`: única vía de fallo — nunca se captura para caer a una señal sintética disfrazada.

### Entregable 1 — Loader vivo reparado (`app/main.py` y `app/supermodules/ecg_monitor/pages.py`)

- `get_ptbxl_records()`/`_ecg_get_ptbxl_records()`: ya NO devuelven 5 IDs inventados — leen en vivo del CSV cacheado y arman **2 normales (NORM) + 1 RBBB (CRBBB) + 1 LBBB (CLBBB), todos confirmados (confianza==100.0)**. Confirmado por ejecución real: `[{'ecg_id': 1, 'label': 'Normal...'}, {'ecg_id': 3, 'label': 'Normal...'}, {'ecg_id': 172, 'label': 'RBBB...'}, {'ecg_id': 180, 'label': 'LBBB...'}]`.
- `load_ptbxl_record()`/`_ecg_load_ptbxl_record()`: firma cambiada de `record_id: str` (plano, inventado) a `filename: str` (la ruta real `filename_hr` del catálogo) + `resolve_ptbxl_wfdb_args()`. **Se eliminó por completo el fallback silencioso a `generate_demo_ecg_signal()`** que existía en ambas copias — antes, CUALQUIER resultado que la app mostró como "PTB-XL cargado" fue siempre ese demo disfrazado (Art. I de la Constitución: nunca presentar una simulación como si fuera el dato real solicitado). Ahora falla explícito con `PtbxlUnavailableError`.
- UI (`st.selectbox` con `format_func`) actualizada en ambos archivos para mostrar `"{ecg_id} — {label}"` y pasar `filename` real al loader.

### Verificación FUNCIONAL (no solo tests) — carga real confirmada, no fachada

Ejecución directa de las funciones vivas de `app/main.py` (las que el ECG Lab realmente llama):
```
ecg_id=1   Normal            -> fs=500 len=5000 mean=0.0026  std=0.1115
ecg_id=3   Normal            -> fs=500 len=5000 mean=-0.0028 std=0.1218
ecg_id=172 RBBB (CRBBB)      -> fs=500 len=5000 mean=-0.0071 std=0.1100
ecg_id=180 LBBB (CLBBB)      -> fs=500 len=5000 mean=-0.0012 std=0.4443
```
4 señales reales, estadísticas distintas entre sí (no es el mismo demo repetido). También verificado vía `AppTest` sobre `app/main.py` real: navegando a Clinical Hub → 🫀 ECG Lab → fuente "Base de datos PTB-XL", el `st.sidebar.selectbox` renderizado por el script en ejecución muestra exactamente ese mismo catálogo real, sin excepciones (`at.exception` vacío) — confirma que el catálogo corregido llega de verdad a la UI. (La simulación del clic de carga vía AppTest chocó con una limitación conocida del framework de test al comparar objetos `dict` como valor de un `selectbox` con `format_func` entre reruns — no un error de la app; se verificó el mismo camino de carga por invocación directa de las funciones, con resultado idéntico al que usaría el botón.)

### Fallback honesto sin red — verificado, no solo diseñado

Dos rutas de fallo probadas por separado, simulando indisponibilidad real:
- Carga de señal contra un registro inexistente: `PtbxlUnavailableError: PTB-XL requiere conexión a PhysioNet -- no se pudo cargar el registro '...' (NetFileNotFoundError: 404 ...)`.
- Descarga del CSV con URL rota y sin caché local: `PtbxlUnavailableError: PTB-XL requiere conexión a PhysioNet -- no se pudo descargar ptbxl_database.csv (HTTPError: 404 ...)`. Confirmado que no se escribe ningún archivo parcial en el intento fallido.

En ningún caso se generó una señal sintética disfrazada de PTB-XL.

### Entregable 2 — Set de validación BBB para la Fase 3 (`tests/ptbxl_bbb_validation_set.py`)

Instrumento de validación, deliberadamente separado del loader vivo (ni lo importa ni lo modifica) — ambos comparten `clinical/ptbxl_metadata.py`, no la selección de registros. `build_bbb_validation_set(per_class_limit=25)` filtra el CSV por `scp_codes` con CRBBB/CLBBB en confianza EXACTA 100.0 (solo confirmados; IRBBB/ILBBB incompletos quedan fuera, categoría aparte para una tanda posterior). Resultado verificado por ejecución: **25 RBBB (CRBBB) + 25 LBBB (CLBBB) = 50 casos**, de un total de 541 CRBBB / 536 CLBBB confirmados disponibles en el dataset completo. Cada caso: `ecg_id`, `label`, `scp_code`, `confidence`, `filename` (listo para `resolve_ptbxl_wfdb_args`).

### Verificación

- `py_compile` limpio en `clinical/ptbxl_metadata.py`, `app/main.py`, `app/supermodules/ecg_monitor/pages.py`, `tests/ptbxl_bbb_validation_set.py`.
- Grep de los 5 IDs viejos (`10038`/`11106`/`14544`/`17242`/`52651`) y `pn_dir='ptbxl'`: cero coincidencias en código vivo (solo quedan citados en docstrings explicando la corrección).
- `pytest tests/ -q`: 368 passed (366 previos + 2 nuevos: balance del set + smoke de carga real contra PTB-XL).
- Servidor real (`streamlit run app/main.py`, puerto 8525): HTTP 200; proceso detenido tras la verificación.

**Pendiente**: Fase 3 (detector morfológico sobre el delineador de la Sub-Fase 2.5, validado contra este set de 50 casos) — no autorizada todavía. Considerar más adelante si consolidar los dos flujos de ECG Monitor duplicados (`app/main.py` vs `app/supermodules/ecg_monitor/pages.py`) es deseable — no se tocó esa decisión de arquitectura en esta tanda. Set de IRBBB/ILBBB (incompletos) queda para una tanda aparte si la Fase 3 los necesita.

## 2026-08-09 — Detector BBB, Sub-Fase 2.5: delineador de QRS aislado (`clinical/qrs_delineation.py`)

**Contexto**: la Sub-Fase 2 (auditoría) confirmó que ni `ECGAnalyzer.segment_qrs_complex()` (el método vivo) ni `WaveAnnotator` (huérfano, `src/signals/ecg/wave_annotation.py`) delineaban onset/offset de QRS con precisión suficiente para medir el criterio morfológico de LBBB/RBBB validado en la Fase 1 — el primero usa `argmin` en una ventana fija de 120ms (igual al umbral clínico que la dispara, amputa QRS patológicamente anchos y puede colapsar Q y S en el mismo punto); el segundo tiene el patrón correcto (cruce de baseline) implementado para P/T pero no para QRS. El validador aprobó construir un delineador nuevo, aislado, extendiendo ese patrón de cruce-de-baseline al QRS — **antes** del detector morfológico (Fase 3, todavía no autorizada).

### Construido

- **`clinical/qrs_delineation.py`** — módulo nuevo, aislado. `QrsDelineation` (`onset_idx`, `offset_idx`, `qrs_duration_ms`, `peaks: List[Dict]`) y `delineate_qrs(signal, r_peak_idx, fs)`.
- Especificación numérica implementada verbatim (procedencia: validador clínico, Detector BBB Sub-Fase 2.5, aprobación 2026-08-09):
  - Ventana dinámica ±120ms (240ms total) centrada en R.
  - Baseline isoeléctrico calculado en el segmento pre-QRS R−120ms a R−80ms.
  - Onset: escaneo hacia atrás desde R hasta `|señal−baseline| ≤ umbral`.
  - Offset: escaneo hacia adelante desde R (o desde una R' tardía, si la hay) hasta que la señal permanezca ≥10ms dentro de la franja isoeléctrica.
  - Búsqueda fina de sub-picos dentro de `[onset, offset]`: `find_peaks` sin el filtro de 300ms entre latidos, distancia intra-QRS ≥20ms, prominencia ≥0.1mV — clasificados Q/R/R_prime/S por signo y posición relativa al pico R principal.
  - **Única ambigüedad de redacción, documentada explícitamente en el código** (`_isoelectric_baseline()`): "umbral = ~0.05mV o 2×std del segmento isoeléctrico" no especifica cuál prevalece — se interpretó como `max(0.05, 2*std)`. Cambio de una línea si el validador quiso otra cosa.

### Verificación objetiva (`tests/test_qrs_delineation.py`, 6 tests, todos de medición, no clínicos)

- **QRS estrecho (~90ms) medido en rango sano**; **QRS ancho (~150ms) NO amputado** — mide >120ms explícitamente (el techo del método viejo).
- **QRS ancho multicomponente (Q-R-S-R') contra `segment_qrs_complex()` real**: el método viejo colapsa a una duración absurda (`q_idx == s_idx`, ambos en el mismo mínimo global) mientras el nuevo mide una duración fisiológicamente plausible y mayor.
- **Onset/offset por baseline, no por `argmin`**: con S más profunda que Q, el delineador nuevo ubica onset antes del trough de Q y offset después del trough de S; se reproduce explícitamente el defecto viejo (`q_idx == s_idx`, ambos en el trough de S) en el mismo test, no se asume.
- **Captura de R' (patrón RSR')**: `peaks` reporta R y R_prime como entradas separadas, en el orden correcto (R, S, R'); se reproduce explícitamente que `find_peaks(distance=300ms)` (el filtro que usa `ECGAnalyzer.detect_r_peaks()`) solo ve un pico en el mismo latido — no puede ver la R'.
- **Contra PTB-XL real** (no sintético): registro `00001_lr` (`pn_dir='ptb-xl/1.0.3/records100/00000'`) cargado con éxito -- `sig_name` confirmó el orden estándar de derivaciones (I,II,III,aVR,aVL,aVF,V1-V6) sobre datos reales, validando la asunción marcada como no verificada en el diseño de la Fase 1. Delineación sobre V1 y V6 reales: onset/offset encierran al pico R y duración en rango fisiológicamente plausible en ambas derivaciones. Nota: el registro usado no se confirmó específicamente como bloqueo de rama (requeriría el CSV de metadata SCP-ECG de PTB-XL, no descargado en esta sub-fase) — el test verifica que el delineador funciona sobre V1/V6 reales, no que el registro tenga esta patología (eso es competencia del detector de Fase 3, no del delineador).
- Hallazgo colateral: `load_ptbxl_record()` (`app/supermodules/ecg_monitor/pages.py`, el loader ya vivo en la app) usa `pn_dir='ptbxl'` con IDs de registro planos (`'10038'`, etc.) — se confirmó que esa ruta da 404 contra PhysioNet hoy; el camino real requiere la estructura anidada `ptb-xl/{version}/records{100,500}/{carpeta}/{registro}`. Es un defecto preexistente del loader (ya tiene manejo de fallback a demo sintético para ese 404), no introducido ni corregido en esta sub-fase — se anota como deuda conocida, separada del delineador.

### Aislamiento confirmado

- Grep de `qrs_delineation`/`QrsDelineation`/`delineate_qrs` en todo el repo: solo `clinical/qrs_delineation.py` y `tests/test_qrs_delineation.py` — cero referencias desde `clinical/ecg_analyzer.py`, `detect_clinical_pattern()`, o cualquier call site vivo. Coexiste con `segment_qrs_complex()` sin reemplazarlo.
- `py_compile` limpio.
- `pytest tests/ -q`: 366 passed (360 previos + 6 nuevos). Se detectó y aisló una inestabilidad **preexistente, no relacionada** con este cambio: `test_twin_shell_case_hemodynamics.py::test_divergence_citation_is_correct_per_scenario_in_twin_shell_mode_too` falló 2 de 4 corridas de la suite completa (siempre el mismo `assert case_references` vacío) pero pasó consistentemente en aislamiento — se confirmó que el patrón de fallo/paso ocurre tanto con los archivos nuevos presentes como ausentes, descartando causalidad. No se investigó ni se corrigió aquí (fuera de alcance de esta sub-fase); queda anotada como deuda a revisar aparte.
- Servidor real (`streamlit run app/main.py`, puerto 8524): HTTP 200; proceso detenido tras la verificación.

**Pendiente**: Fase 3 (integrar el delineador al detector morfológico de LBBB/RBBB sobre V1/V6, según el diseño y las preguntas al validador de la Fase 1) — no autorizada todavía. Investigar la inestabilidad preexistente de `test_twin_shell_case_hemodynamics.py` (no bloqueante, ver arriba). Corregir `load_ptbxl_record()` para usar la ruta PTB-XL real (hallazgo colateral, no en el alcance de esta sub-fase).

## 2026-08-09 — Bloque 3, ítem 1: re-verificado — `run_baroreflex()` NO necesita sub-relajación (premisa refutada, sin cambios de código)

**Contexto**: se planteó aplicar a `run_baroreflex()` (Módulo 2 aislado, `baroreflex.py`) la misma sub-relajación ya validada en `run_closed_loop()` (Módulo 4, `CLOSED_LOOP_RELAXATION_FACTOR`), bajo la premisa de que el Módulo 2 nunca la recibió y por eso "a HR≈90-98 tarda más ticks o roza la oscilación". Antes de tocar código, "Verifica vigencia primero" (instrucción explícita) — se ejecutó `run_baroreflex()` y `run_pathological_baroreflex()` en todo el rango HR 80-220 para confirmar el comportamiento descrito.

### Verificación — premisa refutada por ejecución

- `run_baroreflex()` (Módulo 2) confirmado SIN sub-relajación (línea `rd = rd_next` directa, sin amortiguar) — esa parte de la premisa es correcta.
- Pero el comportamiento lento/oscilante NO se reproduce: en HR 80-220, `run_baroreflex()` converge en 3-10 ticks (muy por debajo de `BAROREFLEX_MAX_TICKS=40`), con `sign_changes≤1` en todos los casos (el criterio de oscilación ya usado en `closed_loop.py::_detect_oscillation` exige `sign_changes≥3`).
- `run_pathological_baroreflex()` (Módulo 3), en los 3 escenarios (`healthy`, `hypertension`, `sepsis`) y el mismo rango de HR: `converged=True` en todos los casos, `sign_changes≤1` siempre (sepsis incluso en 0, aunque tarda hasta 29 ticks por su `k=0.3x` reducido — más lento pero sin oscilar, y con margen amplio respecto a `max_ticks=40`).
- Esto es consistente con — no contradice — el diagnóstico ya documentado en el docstring de `CLOSED_LOOP_RELAXATION_FACTOR` (`closed_loop.py`): *"BAROREFLEX_GAIN_K=1.0 (Módulo 2) quedó EXONERADO explícitamente: el Módulo 2 aislado (SV fija) no osciló en ningún HR probado, hasta 220."* La oscilación que sí motivó la sub-relajación del lazo cerrado es un efecto del acoplamiento Rd→retorno venoso→SV (Frank-Starling) que duplica la ganancia efectiva — específico del Módulo 4, no del Módulo 2 aislado ni de su wrapper patológico (Módulo 3).

### Decisión

- **No se tocó `run_baroreflex()` ni `run_pathological_baroreflex()`** — no hay bug que arreglar en el Módulo 2/3 aislado, y añadir sub-relajación sin un problema activo que resuelva sería complejidad injustificada (regla de oro 2 de `CLAUDE.md`: fases pequeñas y justificadas, no cambios preventivos sin motivo verificado).
- `BAROREFLEX_GAIN_K` y el resto de parámetros fisiológicos validados: no tocados (no aplicaba, dado que no se hizo ningún cambio).
- El ítem del Bloque 3 sobre esta sub-relajación se cierra sin cambio de código. La sub-regla LBBB/RBBB (ítem siguiente del Bloque 3) queda intacta, no se tocó.

## 2026-08-09 — Bloque 2, Parte C: retiro de las 3 pestañas cáscara de Academia (Misiones, Pacientes Virtuales, Gemelo Digital)

**Contexto**: auditoría previa (misma serie) confirmó por ejecución que "Pacientes Virtuales" y "Gemelo Digital" (`app/supermodules/academia/pages.py`) eran controles placebo: `create_digital_twin_for_patient()` calculaba `qrs_component = np.sin(2*np.pi*(hr/60)*t)` a partir del slider de HR pero nunca lo usaba en la señal final devuelta (`ecg = p_wave + qrs_complex + t_wave + baseline + noise`, donde `qrs_complex` depende solo de `t % 1`, no de `hr`). Reverificado por ejecución directa antes de tocar nada: `generate_demo_ecg_signal(250, 2, 40)` y `generate_demo_ecg_signal(250, 2, 180)` con el mismo ruido producen salida idéntica (`max abs diff: 0.0`, `np.allclose == True`) — el parámetro HR no tenía ningún efecto real pese a aparentar controlar la señal. Además, ninguna de las 2 pestañas leía ni escribía el UPS, y "Gemelo Digital" colisionaba de nombre con el Digital Twin OS real (`app/supermodules/twin_shell/`), que sí tiene motor hemodinámico validado, UPS persistido y narrador con IA real. "Misiones" no mentía sobre sus límites (ya tenía un `st.info()` honesto admitiendo que la evaluación de misión no está construida, agregado en una tanda anterior) pero era redundante: todo lo que ofrecía ya existe mejor en "Lecciones y Casos" (quiz real de 16 preguntas + casos clínicos con PA calculada).

### Retirado (`app/supermodules/academia/pages.py`)

- Las 3 pestañas de `main()`: "🎯 Misiones", "👥 Pacientes Virtuales", "🧬 Gemelo Digital". `main()` pasa de 5 pestañas a 2: "📝 Lecciones y Casos" y "📖 Tutor IA".
- Datos hardcodeados, huérfanos tras el retiro (verificado por grep, cero referencias fuera de este archivo salvo `_archive/`): `VIRTUAL_PATIENTS` (4 pacientes falsos con signos vitales fijos) y `CLINICAL_MISSIONS` (3 misiones con objetivos/dificultad/XP fijos).
- Funciones exclusivas de las 3 pestañas (mismo grep, cero llamadores externos): `render_virtual_patient_card()`, `render_mission_card()`, `create_digital_twin_for_patient()` (el "gemelo digital" con el bug de HR descrito arriba), `render_missions_tab()`, `render_virtual_patients_tab()`, `render_digital_twin_tab()`.
- El bloque local `try: from app.supermodules import (generate_demo_ecg_signal, generate_demo_respiration_signal, generate_demo_spo2_signal) except ImportError: <3 fallbacks>` — quedó muerto al retirar su único consumidor (`create_digital_twin_for_patient`).
- `import numpy as np` y `from typing import Dict` — quedaron sin ningún uso en el archivo tras los retiros anteriores (verificado por grep: cero coincidencias de `np.` y de `Dict` en el resto del archivo).
- Docstring del módulo y `st.caption()` de `main()`: actualizados para ya no describir "misiones gamificadas, pacientes virtuales, gemelo digital interactivo" como contenido vigente.

### Sobrevivió (y por qué)

- `render_lessons_quizzes_tab()`, `render_theory_section()`, `render_tutor_tab()` y todo lo que usan (`_attach_calculated_pa_to_case`, `_build_pa_findings`, `_dedupe_events`, `_diagnostic_options`, `RICH_SCENARIO_LABELS`, `EVALUABLE_HORIZONS_BY_SCENARIO`, etc.) — no tocados, son "Lecciones y Casos" y "Tutor IA", las 2 pestañas reales.
- `generate_demo_ecg_signal`, `generate_demo_respiration_signal`, `generate_demo_spo2_signal` (`app/utils.py`) — **no se retiraron**: grep confirmó que además de la academia las usan `app/main.py`, `app/supermodules/ecg_monitor/pages.py` y `domain/physiology/ml/ecg_signal_source.py`. El bug de `qrs_component` descrito arriba sigue presente en `generate_demo_ecg_signal` — queda anotado aquí como deuda conocida (el parámetro `hr` no afecta la señal generada); arreglarlo es una tarea aparte de retirar las cáscaras que lo exponían, porque tocaría una función compartida por módulos que si funcionan.
- `pandas` (`import pandas as pd`) — sigue en uso por `render_theory_section()` y `render_lessons_quizzes_tab()`.

### Pendiente (fuera de alcance de esta tanda)

- `QUICKSTART.md`, `COMO_EJECUTAR.md`, `RESUMEN_BUILD.md` siguen describiendo la estructura antigua de Academia (ya desactualizados desde la fusión del 2026-07-01, ahora más aún) — no se reescribieron aquí; confirmado por grep que ninguna referencia a las pestañas retiradas queda en código vivo (solo en estos 3 markdown de onboarding y en `_archive/`).

### Verificación

- `py_compile` sobre `app/supermodules/academia/pages.py`: sin errores.
- Grep de los 7 símbolos exclusivos retirados (`VIRTUAL_PATIENTS`, `CLINICAL_MISSIONS`, `render_virtual_patient_card`, `render_mission_card`, `create_digital_twin_for_patient`, `render_missions_tab`, `render_virtual_patients_tab`, `render_digital_twin_tab`) en todo el repo: cero coincidencias fuera de `_archive/`.
- `streamlit.testing.v1.AppTest` sobre `app/main.py` navegando a Learning Hub → Academia Clinica: `at.exception` vacío antes y después de seleccionar la página; `len(at.tabs) == 2` con etiquetas `"📝 Lecciones y Casos"` y `"📖 Tutor IA"`.
- `pytest tests/ -q`: 360 passed.
- Servidor real (`streamlit run app/main.py`, puerto 8523): `Invoke-WebRequest` → HTTP 200; proceso detenido tras la verificación.

## 2026-08-09 — Bloque 2, Parte A: retiro del quiz muerto de Education (confirmado por ejecución)

**Contexto**: auditoría previa (misma serie) confirmó por ejecución real que `render_education_page()` (`app/main.py`) tenía dos artefactos muertos del mismo quiz roto: `create_quiz('cardio')` (`src/education/learning.py`, solo reconoce `'ecg'`/`'ppg'`) devuelve `{'pregunta': 'Tema no definido', 'opciones': [], ...}` — un dict — y el `if isinstance(quiz, list) and quiz:` que lo consumía lo rechazaba siempre. Reverificado antes de tocar nada: mismo resultado exacto.

### Retirado

- El botón inerte `st.button('Iniciar Quiz Adaptativo')` (vista "Educativa") — sin handler `if`, sin efecto alguno al hacer clic, mismo feature roto que el expander de abajo.
- El expander `🧠 Actividad de quiz supervisada` completo, incluida la llamada rota `src_modules['create_quiz']('cardio')`.
- La asignación `src_modules, src_ok = safe_import_src_modules()` al inicio de la función — quedó sin ningún otro uso dentro de `render_education_page()` tras retirar los dos bloques anteriores (verificado por grep: sus únicos dos usos en esta función eran los dos bloques retirados). `safe_import_src_modules()` en sí y sus otros 2 call sites (`app/main.py:911,1264`) no se tocaron.

**En su lugar**: un `st.info()` honesto señalando dónde vive el quiz real — mismo patrón ya usado 2 bloques más abajo en esta misma función para la teoría de 12 derivaciones y el "Narrador Clínico" ("El quiz real (16 preguntas, con feedback del narrador) está en Learning Hub → Academia Clinica → Lecciones y Casos → Iniciar Quiz"). El quiz real (16 preguntas, `educational/learning_engine.py::generate_quiz()`, expuesto en Academia) no se tocó.

### Verificación

- `AppTest`: 0 excepciones en Education (vista Educativa incluida); confirmado que "Actividad de quiz supervisada" ya no aparece en el render y que el texto de redirección a Academia sí aparece.
- `pytest tests/`: **360/360 passed en 43.13s**, sin regresión.
- Servidor real: **HTTP 200**.

*(Parte B de este bloque — auditoría de Misiones y Gemelo Digital en Academia — es solo lectura, sin retiro; se reporta aparte, sin entrada de CHANGELOG hasta que haya una decisión y un cambio real que registrar.)*

## 2026-08-09 — Bloque 1: retiro de deuda menor — 3 tests de arquitecturas derrotadas + render_home_page() (código muerto)

**Contexto**: auditoría previa (misma serie) confirmó que los 3 tests con error de colección preexistente no eran un caso de "import movido" sino de arquitectura derrotada en la consolidación, y que `render_home_page()` es inalcanzable por clic desde antes de esta tanda. Se retiran los cuatro, cada uno solo después de confirmar que no deja nada vivo sin cobertura.

### Ítem A — 3 tests retirados (archivo borrado, no neutralizado)

- **`tests/test_api.py`** — verificaba `api.main.app`/`db.database`/`db.models`, el backend FastAPI+SQLAlchemy completo que **solo existe en `_archive/v2_backend_stack/`**. Confirmado por grep en todo el repo activo (excluyendo `_archive/`): ningún módulo `app/`, `domain/`, `src/` importa `api.*` ni `db.*` — cero funcionalidad viva que cubrir. Retirado sin reemplazo.
- **`tests/test_arrhythmia_classifier.py`** — verificaba una API rica (`BeatSegmentation.segment_beats()`/`.validate_segmentation()`, `FeatureExtraction.extract_morphological_features()`/`extract_statistical_features()`/`extract_frequency_features()`/`extract_features_batch()`/`normalize_features()`, `ArrhythmiaClassifier.get_class_name()`/`.get_class_description()`/`.validate_beat()`, la clase `ECGBeat`, el módulo `train_arrhythmia_classifier.py`) que no existe en ningún lugar del repo actual, ni siquiera en `_archive/`. Confirmado ANTES de borrar: `tests/test_arrhythmia_classifier_new.py` cubre la API real y viva de `biomedical/arrhythmia_classifier.py::ArrhythmiaClassifier` (`__init__`, `extract_features` vía `prepare_dataset`, `train`, `save_model`) con un smoke test que entrena y persiste un modelo real. **Gap honesto, no bloqueante**: `predict()` no tiene ningún test directo hoy — pero el test retirado tampoco lo cubría contra esta clase (sus métodos no existen ahí), así que no es una cobertura que se pierda con este retiro, es una cobertura que ya faltaba antes.
- **`tests/test_reasoning_engine.py`** — verificaba 13 símbolos (`HRVMetrics`, `RiskLevel`, `AutonomicState`, `PhysiologicalFinding`, `ClinicalHypothesis`, `DifferentialDiagnosis`, `EducationalRecommendation`, `PhysiologicalPatternDetector`, `ClinicalHypothesisGenerator`, `DifferentialDiagnosisGenerator`, `RiskEstimator`, `EducationalRecommendationGenerator`, `AutonomicStateClassifier`) que hoy solo existen en `src/reasoning_engine.py` — el motor marcado explícitamente "diferido/huérfano, no extenderlo" en la sección "Ganadores de duplicación" de `CLAUDE.md`. No se apuntó el import ahí (habría reabierto esa decisión de arquitectura). Confirmado ANTES de borrar: `tests/test_reasoning_engine_new.py` ya cubre el motor real y vivo (`biomedical/reasoning_engine.py::BiomedicalReasoningEngine.analyze()`) con un smoke test real (taquicardia + RMSSD reducido + LF/HF alto + entropía alta + resultado de IA, verificando las 5 claves de salida) — **el motor vivo NO se queda sin cobertura**, ya la tenía antes de este retiro.

No se tocó ninguna config de pytest (no existe `pytest.ini`/`setup.cfg`/`pyproject.toml`/`conftest.py` en el repo — la exclusión de estos 3 archivos siempre se hizo con `--ignore=` ad-hoc en cada corrida manual, nunca en un archivo de configuración persistente). A partir de ahora, `pytest tests/` corre limpio sin necesitar esos `--ignore`.

### Ítem B — `render_home_page()` retirado

Eliminados: la función completa (`app/main.py`) y la rama `else: render_home_page()` de `render_page_content()` — inalcanzable por construcción, ya documentado en una tanda anterior (`selected_page` siempre viene de `HUBS[selected_hub][...]`, nunca puede caer fuera de las 3 listas de hubs). Confirmado por grep: sin llamadores vivos restantes (las únicas coincidencias que quedan son en `_archive/` y en este mismo CHANGELOG). El contenido (grid de bienvenida con "4. HRV Lab" listado como si fuera un cuarto hub — ya incorrecto hoy, HRV Analysis vive dentro de Clinical Hub) no se migró a ningún lado, tal como se pidió — la home de facto de la app sigue siendo Digital Twin OS (`DEFAULT_HUB`), sin cambios.

**Hallazgo colateral, no accionado**: `render_top_bar()` (el banner "BIOCORE AI — Integrated Intelligence") era llamada únicamente por `render_home_page()` — queda huérfana tras este retiro. No se tocó (fuera del alcance explícito de esta tanda) — candidato a una futura mini-limpieza si se confirma que no tiene otro uso planeado.

### Verificación

- `pytest tests/` (ya sin necesitar `--ignore`): **360/360 passed**, mismo conteo que antes de esta tanda (los 3 archivos retirados nunca sumaban al conteo, estaban excluidos por error de colección) — confirma que el retiro no perdió ninguna prueba que estuviera corriendo de verdad.
- **Hallazgo aparte, no de esta tanda**: en una corrida se observó `test_twin_shell_case_hemodynamics.py::test_divergence_citation_is_correct_per_scenario_in_twin_shell_mode_too` fallar de forma intermitente (reproducido 3 de 5 veces en aislamiento; en dos corridas completas de la suite, una vez falló y la siguiente pasó limpia). No relacionado con los cambios de este bloque (ese archivo no se tocó). Causa probable identificada por lectura de código, no confirmada con un fix: `DigitalTwinOrganism.timestamp = datetime.now()` se reasigna en cada uno de los 6 horizontes de un mismo escenario; si dos horizontes consecutivos caen en el mismo tick del reloj del sistema, `get_snapshot_id_at()` (que busca por timestamp exacto) puede resolver de forma ambigua cuál de los snapshots duplicados es "el" horizonte. Queda como deuda separada, no se tocó en este bloque.
- `AppTest`: 0 excepciones en Digital Twin OS (home por defecto), Academia Clinica y Biomarkers Lab.
- Servidor real: **HTTP 200**.

## 2026-08-06 — Learning Hub, Trabajo 1: distractores curados por similitud clínica (agrupación con firma del validador)

**Contexto**: `_diagnostic_options()` elegía distractores con `random.sample` puro sobre los otros 11 escenarios, produciendo diferenciales a veces triviales (sepsis vs. sano). Con los casos ya evaluables (Trabajo 2), se cura la selección por similitud clínica real, usando la agrupación que el usuario llevó a su validador experto y aprobó explícitamente.

### La agrupación (firma del validador)

`CLINICAL_GROUPS` (`app/supermodules/twin_shell/pages.py`, compartida con Academia — mismo patrón que `_attach_calculated_pa_to_case`/`_build_pa_findings`):

| Grupo | Miembros | Se distinguen por |
|---|---|---|
| A — Activación simpática aguda | estrés, ansiedad, ejercicio, convulsión, **arritmia** | SpO2 / signos neurológicos / autolimitación |
| B — Respiratorio/hipoxémico | hipoxia, apnea, EPOC | patrón progresivo / cíclico / crónico-estable |
| C — Hipotensión/bajo gasto/shock | sepsis, **arritmia** | progresivo-vasopléjico vs. errático-de-ritmo |
| D — Basales/crónicos leves | sano, fatiga, hipertensión | (sano/fatiga: una sola variable sutil) |

**Decisión clave del validador, implementada literalmente**: la arritmia está en DOS grupos (A y C) — `_clinical_neighbors()` calcula la unión de todos los grupos a los que pertenece un escenario, así que arritmia sale como vecina tanto de ansiedad/estrés como de sepsis, sin ningún caso especial en el código.

### La curación (`_diagnostic_options()`)

Se llena preferentemente con vecinos clínicos (mismo grupo); solo se completa con lejanos si el grupo no alcanza para las `n_options-1` opciones. Con grupo A (4-5 miembros) puede llenarse enteramente de cercanos; con el grupo más chico (C, 2 miembros) siempre hay como máximo un cercano, el resto se completa con lejanos.

**Distractores son etiquetas, no casos**: confirmado que la restricción de horizontes evaluables (Trabajo 2, `EVALUABLE_HORIZONS_BY_SCENARIO`) no aplica aquí — un distractor es solo el nombre de una opción de respuesta, nunca se genera ni se muestra como un caso con sus propios datos/horizonte.

### Verificado con datos reales (semillas distintas, no un solo tiro)

```
sepsis    -> [arrhythmia, apnea, sepsis, fatigue]        (arritmia: 5/5 tiradas)
anxiety   -> [seizure, stress, exercise, anxiety]         (3/3 distractores del grupo A, 5/5 tiradas)
healthy   -> [fatigue, hypertension, healthy, seizure]    (fatiga E hipertensión: 5/5 tiradas)
stress    -> [exercise, seizure, arrhythmia, stress]      (3/3 distractores del grupo A)
hypoxia   -> [apnea, copd, seizure, hypoxia]              (apnea Y copd: 2/3 distractores)
```

Ningún caso, en ninguna de las 60 tiradas probadas por escenario (12×60=720 casos), quedó con puros distractores lejanos.

### Verificación

- 35 tests nuevos en `tests/test_diagnostic_options_clinical_groups.py`: cobertura completa de los 12 escenarios por el mapa de grupos; arritmia confirmada en exactamente 2 grupos (todos los demás, en exactamente 1); vecinos clínicos exactos para 5 escenarios de ejemplo; sepsis siempre trae arritmia (60 tiradas); sano siempre trae fatiga+hipertensión (60 tiradas); ansiedad siempre 100% distractores del grupo A (60 tiradas); los 12 escenarios garantizan al menos un distractor cercano (60 tiradas cada uno); invariantes estructurales (sin duplicados, tamaño correcto, la respuesta correcta aparece exactamente una vez); y la prueba de "misma función compartida, no copia" entre Academia y Twin OS.
- `AppTest`: 0 excepciones en Home, Digital Twin OS y Academia Clinica.
- `pytest tests/` (excluyendo los 3 archivos con error de colección preexistente): **360/360 passed en 75.49s** (325 previos + 35 nuevos), sin regresión.
- Servidor real: **HTTP 200**.
- Aislamiento: no se tocó `_simulate_*`, el motor hemodinámico, `EVALUABLE_HORIZONS_BY_SCENARIO`, ni la construcción de `Finding`s de PA calculada — solo `_diagnostic_options()` cambió, y sigue siendo la misma función que ambos modos de caso comparten.

Con esto, los dos trabajos de Learning Hub (horizontes evaluables + distractores curados) quedan cerrados sobre la misma base compartida entre Academia y Twin OS.

## 2026-08-06 — Learning Hub, Trabajo 2 — Fase 0 (medición) + Fase 1 (restricción estructural de horizontes)

**Contexto**: el validador señaló que algunos escenarios revierten a un estado indistinguible de "sano" en ciertos horizontes (convulsión, ejercicio) — un caso generado ahí no tiene respuesta discernible, el estudiante adivinaría el pasado en vez de leer los datos presentes. Antes de arreglar, se midió el alcance exacto (Fase 0, solo lectura) y luego se restringió estructuralmente qué horizontes puede elegir el generador de casos (Fase 1, aditivo).

### Fase 0 — La matriz medida (12 escenarios × 6 horizontes, datos reales de `SimulationEngine`)

Se corrió `SimulationEngine().simulate_scenario()` real para los 12 escenarios en los 6 horizontes y se comparó cada fila contra la banda de ruido real de "sano" en ese mismo horizonte (HR 66-73, SpO2 98-99, RR 13-17, estrés 10-27, fatiga 5-15, riesgo=5.0 fijo, salud_global=90.0 fijo).

| Escenario | now | 5min | 30min | 2h | 24h | 7d |
|---|---|---|---|---|---|---|
| sano | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| ejercicio | ✅ | ✅ | ✅ | ⚠️ sin sentido | ❌ roto | ❌ roto |
| estrés | ⚠️ | ⚠️ | ✅ | ✅ | ✅ | ✅ |
| ansiedad | ⚠️ | ✅ | ✅ | ⚠️ | ⚠️ | ⚠️ |
| arritmia | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| hipoxia | ⚠️ | ⚠️ | ✅ | ✅ | ✅ | ✅ |
| apnea | ✅* | ✅* | ✅* | ✅* | ✅* | ✅* |
| fatiga | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| convulsión | ✅ | ❌→sano | ❌→sano | ❌→sano | ❌→sano | ❌→sano |
| sepsis | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| EPOC | ✅† | ✅† | ✅† | ✅† | ✅† | ✅† |
| hipertensión | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

\* apnea nunca muestra su fase de arousal (artefacto de muestreo, hallazgo nuevo) · † EPOC nunca muestra exacerbación (artefacto de muestreo, hallazgo nuevo) — ambos evaluables igual, se difieren a tanda aparte.

**Confirmado con números exactos**: convulsión (`_simulate_seizure`) solo ejecuta la fase ictal si `minutes<5` — de los 6 horizontes muestreados, únicamente `now` califica; `5min` ya devuelve `_simulate_healthy()` completo. Ejercicio usa `recovery_progress=(minutes-30)/60` sin acotar — a `2h` da HR=28 (sin sentido), a `24h` HR=-1908, a `7d` HR=-14580 (el mismo bug ya documentado en el "Reconocimiento" de escenarios).

**Dos hallazgos nuevos, no reportados antes**: EPOC (`exacerbation=(minutes//240)%2==1`) y apnea (`cycle_position=(minutes*2)%1`) tienen fórmulas periódicas que, por cómo están alineados los 6 horizontes muestreados (todos minutos enteros), **caen siempre en la misma mitad del ciclo** — EPOC nunca en exacerbación, apnea nunca en arousal. Evaluables igual (se distinguen de sano con margen claro), pero el caso nunca puede mostrar la fase completa del escenario.

### Fase 1 — Restricción estructural en `case_bank.py`

`EVALUABLE_HORIZONS_BY_SCENARIO: Dict[str, FrozenSet[str]]` — solo para los 5 escenarios con restricción real (los 7 limpios no aparecen en el mapa, caen al default sin restricción vía `.get(scenario.value, _ALL_HORIZONS)`):

| Escenario | Horizontes evaluables | Excluidos y por qué |
|---|---|---|
| `seizure` | `{now}` | 5min-7d: idénticos a sano (`_simulate_healthy()` literal) |
| `exercise` | `{now, 5min, 30min}` | 2h: HR=28 sin sentido; 24h/7d: HR negativo imposible |
| `stress` | `{30min, 2h, 24h, 7d}` | now/5min: dentro del ruido de sano, apenas empieza a subir |
| `anxiety` | `{5min, 30min}` | now: dudoso; 2h/24h/7d: revierte a un tercer estado propio, ni sano ni ansiedad |
| `hypoxia` | `{30min, 2h, 24h, 7d}` | now/5min: SpO2 aún no bajó de forma clara |

`generate_case()`: antes de `rng.choice(steps)`, se filtra `steps` a `evaluable_steps` (los que su horizonte está en el mapa para ese escenario) — `chosen_step` solo puede salir de esa lista filtrada, nunca de la lista completa sin filtrar. Si algún escenario quedara sin ningún horizonte evaluable (no debería ocurrir, los 12 tienen al menos uno), se lanza `ValueError` explícito en vez de degradar en silencio.

**No se tocó**: `_simulate_*`, `SCENARIO_PARAMETERS`, el motor hemodinámico, ni los distractores (`_diagnostic_options`, Trabajo 1, pendiente de la agrupación clínica aprobada). Puramente restrictivo sobre qué horizonte se **elige**, no sobre qué horizontes **existen**.

### Verificación

- 40 casos de convulsión generados con semillas distintas: **40/40 en `now`**, cero excepciones.
- 40 casos de ejercicio: solo `now`/`5min`/`30min`, cero apariciones de `2h`/`24h`/`7d`.
- 40 casos de estrés/ansiedad/hipoxia: respetan exactamente su subconjunto permitido.
- 40 casos de sepsis (sin restricción): los 6 horizontes aparecen, confirmando que el mapa no lo afecta.
- **Paso 3 confirmado explícitamente**: `HEMODYNAMIC_MODEL_ENABLED_SCENARIOS` (sano/hipertensión/sepsis, los únicos con PA calculada) están los tres fuera de `EVALUABLE_HORIZONS_BY_SCENARIO` — sin restricción, la conexión de PA calculada (tanda anterior) no se ve afectada. Test dedicado que falla si algún día alguien restringe uno de los tres por error.
- 16 tests nuevos en `tests/test_case_bank_evaluable_horizons.py`; los 26 tests existentes de PA calculada (`test_academia_case_hemodynamics.py`) siguen pasando sin cambios, confirmando que sano/hipertensión/sepsis siguen funcionando igual.
- `AppTest`: 0 excepciones en Home, Digital Twin OS y Academia Clinica.
- `pytest tests/` (excluyendo los 3 archivos con error de colección preexistente): **325/325 passed en 55.31s** (309 previos + 16 nuevos), sin regresión.
- Servidor real: **HTTP 200**.

**Pendiente, explícitamente fuera de esta tanda**: la fase completa de apnea/EPOC (arousal/exacerbación nunca alcanzables) y el Trabajo 1 (agrupación clínica de distractores, esperando aprobación del validador).

## 2026-08-06 — Learning Hub: PA calculada replicada al modo caso de Twin OS (compartida, no duplicada)

**Contexto**: la conexión de la PA calculada al modo caso clínico (PA + coexistencia + feedback con divergencia adaptada por escenario) ya funcionaba en Academia. Se replica ahora al segundo modo de caso, `app/supermodules/twin_shell/pages.py::render_clinical_case_mode()` (Digital Twin OS → Herramientas avanzadas → "🎓 Caso clínico interactivo"), reutilizando la lógica en vez de copiarla.

### Refactor primero: extraer lo compartible antes de replicar

Ambos modos ya importaban de `twin_shell/pages.py` (`RICH_SCENARIO_LABELS`, `_dedupe_events`, `_diagnostic_options`) — se extendió ese mismo patrón. Dos funciones que vivían inline en `academia/pages.py` se movieron a `twin_shell/pages.py` (junto a esas otras auxiliares ya compartidas), sin cambiar su comportamiento:

- **`_attach_calculated_pa_to_case(session, patient_id, scenario_value, state, source_detail)`** — la restricción estructural a los 3 escenarios validados, la resolución de snapshot exacto (`get_snapshot_id_at`), el cálculo (`compute_and_attach_closed_loop_pressure`), el manejo defensivo de `HemodynamicModelNotEnabledError`, y la recuperación de la `ClinicalReferenceValue` coexistente. Devuelve `(state, referencias)`.
- **`_build_pa_findings(state, references_pa, scenario_value)`** — los `Finding`s de PA calculada/referencia/divergencia, incluida la cita adaptada por escenario (`_DIVERGENCE_THRESHOLD_MEANING_BY_SCENARIO`, también movida aquí).

`academia/pages.py` ahora IMPORTA estas tres piezas en vez de definirlas — su manejador de "Nuevo caso sintético" pasó de ~40 líneas de lógica inline a una sola llamada a `_attach_calculated_pa_to_case()`; su construcción de `pa_findings` pasó de ~75 líneas a una llamada a `_build_pa_findings()`. Un test dedicado (`test_twin_shell_and_academia_share_the_exact_same_functions_not_copies`) confirma que `academia_pages._build_pa_findings is twin_shell_pages._build_pa_findings` — el mismo objeto en memoria, no una copia que pueda divergir.

### La réplica a Twin OS

`render_clinical_case_mode()`: tras generar el escenario oculto (`run_rich_scenario`, sin tocar), llama `_attach_calculated_pa_to_case()` sobre el último paso (`step.state`) antes de guardar el `patient_id` en `session_state`. La sección de display resuelve `case_references` en cada rerun (sin session_state adicional — ver más abajo) y muestra el mismo bloque "🧮 PA calculada..." que ya existía en `render_ups_scenario_simulator()`. El manejador de "Confirmar diagnóstico" inserta `_build_pa_findings(state, case_references, hidden.value)` en la lista de `Finding`s antes de llamar al narrador, igual que Academia.

**Hallazgo de la auditoría pedida — Twin OS NO tenía el bug de horizonte de Academia**: a diferencia de `case_bank.generate_case()` (que elige al azar cualquiera de los 6 horizontes), `render_clinical_case_mode()` siempre agota los 6 pasos de `run_rich_scenario()` y muestra el ÚLTIMO (`get_latest_state()`) — por construcción, "el más reciente" y "el mostrado" son siempre el mismo snapshot aquí, así que `get_latest_snapshot_id()` nunca habría dado el snapshot equivocado. Se usa `get_snapshot_id_at()`/`get_state_by_snapshot_id()` de todas formas, por dos razones: (1) es la misma función compartida que Academia sí necesita, y hacerla depender de "soy el último" habría sido una asunción silenciosa dentro de una función pensada para dos llamadores con comportamientos distintos; (2) consecuencia útil verificada: como el modo caso de Twin OS SIEMPRE muestra el último horizonte, la coexistencia con la `ClinicalReferenceValue` ocurre SIEMPRE que el escenario tiene una (nunca depende de una semilla al azar, a diferencia de Academia).

**Menor duplicación real, no solo aspiracional**: no quedó nada que "minimizar" — no hizo falta duplicar código en `twin_shell/pages.py` más allá de la orquestación específica de Streamlit (fetch de estado, construcción del `st.markdown`, inserción en la lista de `Finding`s), que ya era distinta entre los dos modos desde antes de esta tanda (Academia usa `state.all_domains()` directo, Twin OS usa `build_context()`).

### Verificación

- Caso de sepsis en Twin OS: PA calculada colapsada (PAM≈24, confirmado con datos reales), referencia coexistiendo (PAM 65), `Finding` de divergencia citando Sepsis-3.
- Caso de hipertensión: PA calculada (PAM≈103), referencia (PAM≈97), divergencia citando ACC/AHA 2017 -- nunca Sepsis-3.
- Caso de hipoxia (uno de los 9 no validados): sin PA calculada, sin `Finding`s de PA, sin excepción -- confirmado explícitamente.
- 15 tests nuevos en `tests/test_twin_shell_case_hemodynamics.py`: los 3 escenarios validados reciben PA con provenance/confidence correctos; los 9 no validados no reciben nada (parametrizado); la coexistencia con referencia ocurre siempre (no depende de semilla, a diferencia de Academia); la cita se adapta por escenario (Sepsis-3 solo en sepsis, ACC/AHA en hipertensión/sano, nunca cruzadas); y la prueba de diseño que confirma que Academia y Twin OS comparten el mismo objeto de función, no una copia.
- `tests/test_academia_case_hemodynamics.py` simplificado: sus réplicas manuales de `_build_pa_findings`/la lógica de "Nuevo caso sintético" se reemplazaron por llamadas a las funciones reales importadas -- menos código de test, y ahora prueba literalmente lo que corre en producción, no una aproximación.
- `AppTest`: 0 excepciones en Home, Digital Twin OS y Academia Clinica.
- `pytest tests/` (excluyendo los 3 archivos con error de colección preexistente): **309/309 passed en 39.81s** (294 previos + 15 nuevos), sin regresión.
- Servidor real: **HTTP 200**.

## 2026-08-06 — Learning Hub: la cita del prompt de divergencia estaba fija en Sepsis-3 — corregida por escenario

**Contexto**: auditoría (misma serie) del refuerzo de divergencia recién añadido — la nota que instruye al narrador a explicar por qué la PA calculada y la PA de referencia pueden diferir citaba, textualmente y sin condición, "Sepsis-3 define shock por PAM < 65 mmHg". Correcto para un caso de sepsis; **dato incorrecto en el contexto para un caso de hipertensión o sano**, aunque fuera "solo" un ejemplo dentro de la instrucción.

### Confirmado: estaba fija, no adaptada

Grep de `"Sepsis-3"` en `app/supermodules/academia/pages.py`: una sola coincidencia, dentro de un string literal sin ninguna rama condicional por escenario. Un caso de hipertensión con divergencia habría mostrado igual "Sepsis-3" en el prompt.

### La corrección

Nueva constante `_DIVERGENCE_THRESHOLD_MEANING_BY_SCENARIO` (antes de `render_synthetic_case_section()`) — no una cita, sino qué TIPO de umbral representa cada referencia:
- `sepsis`: "un umbral de shock: por debajo de él, el cuadro se clasifica como shock séptico".
- `hypertension`: "un umbral de entrada a la categoría diagnóstica de hipertensión -- no de shock ni de crisis hipertensiva".
- `healthy`: "el valor normal esperado para un adulto sano, no un umbral de ninguna categoría patológica -- si diverge del cálculo, probablemente refleje diferencias de calibración... no un hallazgo clínico" (siguiendo la instrucción de no forzar una cita de patología donde no aplica).

La CITA real (el texto de la fuente) ya no se escribe a mano — se toma en vivo de `ref_map.citation`, el mismo `ClinicalReferenceValue` que ya se muestra en pantalla, transcrito en `blood_pressure_references.py` (`_SEPSIS_3`, `_ACC_AHA_2017`) desde antes de esta tanda. Cero citas nuevas inventadas; se reutiliza exactamente lo que ya existía.

### Verificado con datos reales, antes y después (caso de hipertensión con divergencia)

`ref_map.citation` para hipertensión: `"ACC/AHA 2017 (2017 ACC/AHA Hypertension Guideline) (PAM derivada: PAM≈diastólica+⅓(sistólica−diastólica))"`.

- **Antes**: *"La referencia es un umbral/criterio de clasificación de guía clínica (p.ej. **Sepsis-3** define shock por PAM < 65 mmHg)..."* — cita ajena al cuadro.
- **Después**: *"La referencia citada aquí (**ACC/AHA 2017 (2017 ACC/AHA Hypertension Guideline)...**) es **un umbral de entrada a la categoría diagnóstica de hipertensión -- no de shock ni de crisis hipertensiva**, no la presión real de este paciente..."*

Confirmado además para sepsis (sigue citando Sepsis-3, framing de shock, sin cambio de comportamiento) y sano (cita ACC/AHA 2017 — mismo umbral numérico que hipertensión, 120/80, pero framing distinto: "no un umbral de ninguna categoría patológica" en vez de "entrada a hipertensión").

### Verificación

- 1 test nuevo (`test_divergence_citation_is_correct_per_scenario_not_hardcoded_to_sepsis`, `tests/test_academia_case_hemodynamics.py`): para los 3 escenarios validados con ambas PA coexistiendo, confirma que `ref_map.citation` aparece literalmente embebida en el texto (prueba de que se lee en vivo, no se reescribe a mano) y que la cita de un escenario NUNCA aparece en el prompt de otro (`"Sepsis-3" not in` el texto de hipertensión/sano; `"ACC/AHA" not in` el de sepsis). Los 25 tests previos de esta serie, actualizados para pasar el escenario explícito a la réplica de construcción de `Finding`s, sin cambios de comportamiento.
- `pytest tests/` (excluyendo los 3 archivos con error de colección preexistente): **294/294 passed en 35.06s** (293 previos + 1 nuevo), sin regresión.
- Servidor real: **HTTP 200**.
- Twin OS no tocado — se replica en una tanda aparte, ya con este prompt corregido.

## 2026-08-06 — Learning Hub: refuerzo del prompt para explicar la divergencia PA calculada vs. referencia

**Contexto**: la conexión de la PA calculada al modo caso clínico de Academia (misma serie, entrada previa) hace que, cuando ambas PA coexisten, a veces diverjan mucho (sepsis: calculada PAM~24 vs. referencia PAM 65). Sin contexto, esa divergencia confunde al estudiante ("¿cuál creo?"). Se refuerza la instrucción al narrador para que la explique siempre como lección — nunca como contradicción — cuando ambas estén presentes.

### El refuerzo

`render_synthetic_case_section()` (`app/supermodules/academia/pages.py`): cuando `map_modelo` (PA calculada) y la `ClinicalReferenceValue` de PAM coexisten en el mismo caso, se añade un TERCER `Finding` — "Nota sobre la posible divergencia entre las dos PA" — con instrucción explícita al narrador:

- Explicar la divergencia como lección, no como contradicción.
- Nunca declarar una "correcta" y otra "incorrecta" — ambas describen cosas distintas.
- Nunca ajustar ninguna de las dos para que se acerquen — la divergencia es real y fisiológicamente honesta.
- La referencia es un umbral/criterio de clasificación de guía clínica (ejemplo dado al modelo: Sepsis-3 define shock por PAM < 65 mmHg) — una línea de corte, no la presión de este paciente.
- La calculada es la estimación del modelo PARA ESTE paciente concreto, derivada de su fisiología específica — puede caer muy por debajo del umbral si el cuadro está descompensado.
- Divergir no es contradicción: el umbral marca DÓNDE EMPIEZA la categoría; el modelo estima QUÉ TAN LEJOS llegó este caso dentro de ella.

Este `Finding` se añade EXCLUSIVAMENTE dentro del bloque que ya requiere que ambas PA coexistan (estructuralmente, no por una condición aparte) — un caso con solo PA calculada (sin referencia) o solo referencia (los 9 escenarios sin motor hemodinámico) nunca lo recibe. El refuerzo se suma a la honestidad de procedencia ya establecida (calculada = cálculo del modelo, referencia = guía citada, ninguna es medición) — no la reemplaza, ambos Findings individuales la conservan intacta.

### Prompt real verificado (payload completo, caso de sepsis con ambas PA)

Mismo caso de la tanda anterior (HR=150, PA calculada 26/22 mmHg PAM 24, referencia PAM 65):

```json
{
  "lab": "Caso Clínico Sintético",
  "findings": [
    {
      "metric": "PA calculada por el modelo hemodinámico",
      "value": "26/22 mmHg (PAM 24 mmHg)",
      "meaning": "CALCULADA por el modelo hemodinámico de lazo cerrado a partir del heart_rate real de este caso -- NUNCA la presentes como una medición del paciente ni como un valor de guía clínica; es un cálculo del modelo."
    },
    {
      "metric": "PA de referencia clínica (guía citada)",
      "value": "PAM 65 mmHg",
      "meaning": "Valor de REFERENCIA transcrito de literatura clínica para este cuadro -- no es una medición ni el cálculo del modelo de arriba; son dos fuentes distintas que coexisten."
    },
    {
      "metric": "Nota sobre la posible divergencia entre las dos PA",
      "value": "Ver las dos métricas anteriores",
      "meaning": "Si la PA calculada y la PA de referencia difieren, explícalo como una lección, no como una contradicción -- NUNCA declares una 'correcta' y la otra 'incorrecta', y NUNCA ajustes ninguna de las dos para que se acerquen; la divergencia es real y fisiológicamente honesta, se explica, no se maquilla. La referencia es un umbral/criterio de clasificación de guía clínica (p.ej. Sepsis-3 define shock por PAM < 65 mmHg) -- una línea de corte que separa categorías, no la presión real de este paciente. La calculada es la estimación del modelo PARA ESTE paciente concreto, derivada de su fisiología específica -- puede caer muy por debajo del umbral si el cuadro está descompensado. Divergir no es contradicción: el umbral marca DÓNDE EMPIEZA la categoría (shock, hipertensión, etc.); el modelo estima QUÉ TAN LEJOS llegó este caso concreto dentro de ella."
    }
  ]
}
```

No se pudo ejecutar la llamada real (`ANTHROPIC_API_KEY` no configurada en este entorno, mismo límite de siempre) — el payload de arriba es exacto, construido con datos reales de un caso generado en esta verificación, no fabricado.

### Verificación

- 10 tests nuevos en `tests/test_academia_case_hemodynamics.py`: el `Finding` de divergencia aparece (con las 5 reglas explícitas verificadas literalmente presentes en el texto: "no como una contradicción", "NUNCA declares una 'correcta'...", "NUNCA ajustes...", cita de Sepsis-3, "PARA ESTE paciente concreto") solo cuando ambas PA coexisten; ausente cuando solo hay PA calculada; y ausente para los 9 escenarios sin motor hemodinámico (parametrizado, uno por uno).
- `pytest tests/` (excluyendo los 3 archivos con error de colección preexistente): **293/293 passed en 36.40s** (283 previos + 10 nuevos), sin regresión.
- Servidor real: **HTTP 200**.
- Twin OS no tocado — se replica en una tanda aparte, como se pidió.

## 2026-08-06 — Learning Hub: PA calculada del motor hemodinámico conectada al modo caso clínico de Academia

**Contexto**: la auditoría del contenido educativo (misma serie) encontró que el modo caso clínico de Academia (`app/supermodules/academia/pages.py::render_synthetic_case_section()`) usa el UPS real (`case_bank.generate_case()` → `run_rich_scenario`) pero nunca la PA validada del motor hemodinámico ("la película") — confirmado por grep, cero llamadas a `compute_and_attach_closed_loop_pressure` en todo `domain/physiology/scenarios/`. Se conecta ahora, solo para los 3 escenarios con validación experta completa (`HEMODYNAMIC_MODEL_ENABLED_SCENARIOS`: healthy, hypertension, sepsis). Twin OS no se toca en esta tanda — se replica después, como se pidió.

### El obstáculo real: el horizonte elegido no es el último snapshot

`case_bank.generate_case()` elige al azar CUALQUIERA de los 6 horizontes que `run_rich_scenario()` persiste (now/5min/30min/2h/24h/7d) como "el caso" — no siempre el último. `compute_and_attach_closed_loop_pressure()` necesita un `snapshot_id` explícito, y `get_latest_snapshot_id()` habría devuelto el snapshot equivocado en la mayoría de los casos (adjuntando la PA calculada a un horizonte que el estudiante nunca ve). Verificado el bug ANTES de que ocurriera: con una semilla de prueba, el horizonte elegido fue el índice 1 de 6, mientras el snapshot "más reciente" era el índice 5 — usar `get_latest_state()` habría dejado el caso sin PA calculada en silencio.

**Solución**: dos funciones nuevas y aditivas, sin tocar ninguna función existente:
- `domain/physiology/state/clinical_impression_repository.py::get_snapshot_id_at(session, patient_id, timestamp)` — resuelve el snapshot exacto de un timestamp dado (no el más reciente), mismo patrón ya establecido en ese archivo para `get_latest_snapshot_id()` (consulta directa a `SnapshotRecord`, sin tocar `repository.py`).
- `domain/physiology/state/repository.py::get_state_by_snapshot_id(session, snapshot_id)` — como `get_latest_state()`, pero para un snapshot específico; necesario para releer el estado después de `append_descriptors()` cuando ese snapshot no es el último del paciente.

Verificado end-to-end antes de conectar la UI: con un horizonte no-último, `get_snapshot_id_at()` + `compute_and_attach_closed_loop_pressure()` + `get_state_by_snapshot_id()` recuperan correctamente `map_modelo`; `get_latest_state()` sobre el mismo paciente, en cambio, no lo tiene — confirma que el bug era real y que la solución lo evita.

### La conexión (`render_synthetic_case_section()`)

En el manejador de "🆕 Nuevo caso sintético": si `case.scenario.value in HEMODYNAMIC_MODEL_ENABLED_SCENARIOS`, se resuelve el `snapshot_id` exacto del horizonte elegido y se llama `compute_and_attach_closed_loop_pressure()` con el `heart_rate` real de ese caso — mismo criterio de restricción estructural que `render_ups_scenario_simulator()` en Twin OS (`HemodynamicModelNotEnabledError` capturado defensivamente, nunca debería dispararse dado el filtro previo). Para los otros 9 escenarios, este bloque completo no se ejecuta — el caso queda exactamente como estaba.

**Coexistencia**: la `ClinicalReferenceValue` (si existe) vive en el ÚLTIMO snapshot de la corrida (comportamiento preexistente de `run_rich_scenario`, sin cambios) — se consulta con el mismo `snapshot_id` del caso, así que solo aparece cuando el horizonte elegido coincide con el último. Cuando coincide, ambas fuentes conviven en la misma tabla de descriptores y en el mismo feedback, cada una con su etiqueta.

**Display**: nuevo bloque "🧮 PA calculada por el modelo hemodinámico" (mismo texto/estilo que el ya existente en Twin OS) junto a la tabla de descriptores — muestra S/D/PAM + confianza (75%), y la referencia clínica si coexiste. Los 3 descriptores nuevos (`systolic_bp_modelo`/`diastolic_bp_modelo`/`map_modelo`) también aparecen automáticamente en la tabla genérica de descriptores ya existente, con su columna "Procedencia" = `modelo_hemodinamico` — el estudiante distingue de un vistazo medido/simulado (UPS), calculado (modelo) y referencia (guía citada).

**Feedback del narrador — la pieza educativa pedida**: además del `Finding` genérico que el bucle existente ya arma para cada descriptor (incluidos los 3 nuevos), se añade un `Finding` específico "PA calculada por el modelo hemodinámico" con instrucción explícita: nunca presentarla como medición ni como valor de guía, y explicar el **porqué fisiológico** (ejemplo de instrucción dado al modelo: en sepsis, la vasoplejía reduce el tono vascular y colapsa el retorno venoso). Si hay referencia clínica coexistiendo, un segundo `Finding` la distingue explícitamente y pide señalar diferencias si las hay.

**Prompt real verificado** (sin `ANTHROPIC_API_KEY` en este entorno, no se pudo ejecutar la llamada — mismo límite de siempre en este entorno de desarrollo): construido un caso de sepsis real (HR=150, PA calculada 26/22 mmHg, PAM 24, coexistiendo con referencia PAM 65 mmHg), el payload JSON exacto que recibiría el narrador quedó verificado end-to-end, incluida la instrucción de procedencia completa — ver sesión de trabajo para el ejemplo íntegro.

### Verificación

- 16 tests nuevos: `tests/test_academia_case_hemodynamics.py` (15 — los 3 escenarios habilitados reciben PA calculada con provenance/confidence correctos, sepsis colapsa por debajo de 65 mmHg, los 9 no habilitados no reciben nada y no lanzan excepción, coexistencia con `ClinicalReferenceValue` cuando el horizonte coincide con el último, y el test específico que reproduce el bug de horizonte-no-último evitado) + `tests/test_ups_state.py` (1 — `get_snapshot_id_at`/`get_state_by_snapshot_id` resuelven un snapshot intermedio, no el más reciente, y devuelven `None` honesto para ids/timestamps inexistentes).
- `AppTest`: 0 excepciones en Home y Academia Clinica.
- `pytest tests/` (excluyendo los 3 archivos con error de colección preexistente): **283/283 passed en 30.26s** (267 previos + 16 nuevos), sin regresión.
- Servidor real: **HTTP 200**.
- Aislamiento: Twin OS (`twin_shell/pages.py`) no tocado. `case_bank.py`, `rich_engine.py`, el motor hemodinámico (`closed_loop.py`, `closed_loop_ups_bridge.py`) sin cambios — solo se les llama desde un nuevo punto. `repository.py`/`clinical_impression_repository.py` reciben únicamente funciones aditivas nuevas, ninguna existente modificada.

## 2026-08-06 — Twin OS: retiro del confidence inventado en la clasificación de patrones ECG (Art. I)

**Contexto**: la auditoría previa (misma serie, solo lectura) confirmó que `ECGAnalyzer.detect_clinical_pattern()` (`clinical/ecg_analyzer.py`) detecta patrones ECG reales (reglas deterministas sobre QTc de Bazett/hr/qrs/pr/ST, todos medidos genuinamente de la señal), pero acompaña cada patrón con un `confidence` que era una **constante literal por rama** (0.95 STEMI, 0.92 AFib, 0.90 VT, ..., 0.60 default) — nunca calculado, mostrado en Digital Twin OS como "{pattern} — X% confianza" bajo la etiqueta "CLASIFICACIÓN (DERIVADO)". Un número con apariencia de métrica calculada que en realidad no se calculaba — Art. I de la Constitución ("IA real, no fingida... prohibido texto/dato hardcodeado disfrazado de análisis").

**Corrección a la auditoría, encontrada al implementar**: el reporte previo dijo "nadie más lo consume, solo el display" — impreciso. `classify_ecg_signal()` reenviaba ese mismo `confidence` a `generate_shap_lime_report(..., result["confidence"])`, que lo pasaba a `shap_like_explanation()` (`src/interpretability.py`), la cual lo filtraba en una SEGUNDA ubicación: la narrativa de la pestaña "SHAP" del mismo panel — *"...con {probability:.0%} de confianza"*. Ambos puntos de fuga se corrigen en esta tanda, no solo la tarjeta principal.

### La corrección

- **`clinical/ecg_analyzer.py::detect_arrhythmias()`**: ahora expone en su dict de retorno los valores crudos que ya calculaba internamente pero descartaba (`rr_cv`, `rr_std_ms`, `max_rr_jump_pct`) — mismos umbrales exactos, solo expresados en unidades legibles (p.ej. `rr_std_ms > 150.0` en vez de `rr_std > 0.15` segundos — equivalencia algebraica verificada antes de tocar el código). Aditivo: cero cambio de comportamiento de detección.
- **`clinical/ecg_analyzer.py::detect_clinical_pattern()`**: se retiraron las 9 constantes de `confidence` y el ajuste `-0.15` por pocos picos R. Cada rama ahora cita el **criterio medido exacto — valor + umbral** — que la disparó (p.ej. `"QTc=485 ms (umbral > 470 ms, fórmula de Bazett)"`, `"RR muy variable: desviación estándar 166 ms con FC=95 bpm (umbral: DE>150 ms y FC>90 bpm)"`, `"ST elevado 0.14 mV (umbral > 0.10 mV)"`). El caso de "pocos picos R" ya no resta un número inventado — ahora dice honestamente `"Basado en pocos latidos: solo N picos R detectados -- confiabilidad reducida"`. Se añadió también un mensaje explícito para el caso "Normal Sinus Rhythm" (antes quedaba sin razón alguna) para que el reasoning nunca esté vacío. Las condiciones `if/elif` que DISPARAN cada patrón **no se tocaron** — mismo orden, mismos umbrales, misma lógica; solo cambió el texto que explica por qué se disparó.
- **`domain/physiology/ml/ecg_classification.py`**: `EcgClassificationResult.confidence` **eliminado del todo** (no conservado internamente sin mostrar) — nadie más lo consumía (confirmado por grep antes de tocar, y sin cobertura de test alguna). `classify_ecg_signal()` ya no lee `result["confidence"]`.
- **`src/interpretability.py`**: `shap_like_explanation()`/`generate_shap_lime_report()` perdieron el parámetro `probability` (único llamador real confirmado por grep) — la narrativa SHAP cierra ahora con `"El modelo combina estos factores para explicar el resultado: {prediction}."`, sin el pseudo-porcentaje.
- **`app/supermodules/twin_shell/pages.py::render_ecg_classifier_panel()`**: la tarjeta "CLASIFICACIÓN (DERIVADO)" ya no muestra "X% confianza" — muestra el primer criterio de `result.reasoning` (siempre presente). La lista completa de hallazgos se re-etiquetó explícitamente: "Hallazgos (criterio medido, no una probabilidad)".
- **`app/supermodules/ecg_monitor/pages.py`** (código huérfano, nunca invocado desde el router — confirmado en la auditoría de "Vista IA" previa): se corrigió la misma línea por consistencia, para no dejar una referencia a una clave que ya no existe.

**Pendiente, deliberadamente NO tocado en esta tanda** (problema distinto, marcado con comentario en el propio código): la sub-regla que distingue LBBB de RBBB (`np.mean(signal[:10]) > np.mean(signal[-10:])`) es detección real pero clínicamente cuestionable — la diferenciación real necesita morfología del QRS en V1/V6, no un promedio de amplitud del principio/final de una sola derivación. Es un problema de la regla de detección, no de confidence inventado — queda para otra tanda.

### Verificación

- Detección directa (`ECGAnalyzer.detect_clinical_pattern`/`detect_arrhythmias`) sobre señales sintéticas construidas para disparar cada rama: patrón AFib confirmado con `rr_std_ms=166, hr=95` (umbral cumplido), reasoning cita el valor real; caso de pocos picos R muestra la nota honesta en vez de restar un número; ningún resultado contiene la clave `confidence`.
- `classify_ecg_signal()` end-to-end (incluida la generación real de SHAP/LIME): `EcgClassificationResult` sin campo `confidence`; narrativa SHAP sin porcentaje de confianza.
- `AppTest`: 0 excepciones en Home y Digital Twin OS tras el cambio.
- `pytest tests/` (excluyendo los 3 archivos con error de colección preexistente y no relacionado): **267/267 passed en 25.28s**, sin regresión (cero test tocaba este código, confirmado antes de editar).
- Servidor real: **HTTP 200**.
- Aislamiento: cero cambios en `domain/physiology/state/*`, el narrador, o el motor hemodinámico. La lógica de DETECCIÓN (qué patrón se elige) no cambió — solo se retiró el número inventado que la acompañaba y se enriqueció el texto que ya era honesto.

## 2026-08-05 — Pulido: retiro de Mission Control + reubicación de la Ficha Clínica Global

**Contexto**: la mini-auditoría previa (misma fecha, solo lectura) clasificó ambos elementos: Mission Control como funcional-pero-100%-redundante con el selector de hub del sidebar, y la Ficha Clínica Global como mixta (3/5 campos funcionales, 2/5 cáscaras muertas). Esta tanda ejecuta la limpieza sobre esos hechos, sin reabrir la auditoría.

### Parte A — Mission Control retirado

`render_mission_control_panel()` (`app/main.py`, antes líneas 494-522) y su llamada incondicional en `main()` (se ejecutaba en TODA página, no solo en el inicio) fueron eliminadas — sus 3 botones duplicaban exactamente el selector de hub ya presente en la barra lateral (`st.sidebar.radio('Selecciona un hub', ...)`), sin ninguna capacidad propia. Verificado por grep: el único otro llamador vivo no existía (`_archive/app/main2.py` es código archivado, no se ejecuta). El texto de `render_guides_page()` que decía "Usa Mission Control para cambiar entre los hubs" se reescribió para apuntar al selector real ("Usa el selector de hub en la barra lateral...") — sin dejar una referencia rota a algo que ya no existe.

### Parte B — Ficha Clínica Global: 2 cáscaras eliminadas, 3 campos reubicados en su único consumidor real

**Eliminados** (`Nombre`/`pac_nombre`, `Peso (kg)`/`pac_peso`): confirmado por grep, ANTES de borrar, que ningún archivo del proyecto los leía — se tecleaban y morían ahí. Sin rastro tras el cambio.

**Reubicados** (`Edad`/`pac_edad`, `Actividad Física`/`pac_actividad`, `Cirugías previas o Trauma`/`pac_cirugias`): la auditoría confirmó que su único consumidor real era `render_biomarkers_page()` (Clinical Hub → Biomarkers Lab) — penalización de `hrv_rmssd` si edad>50, multiplicador de `metabolic_efficiency` por actividad, penalización de `hr_recovery_rate` por cirugía, más las notas narrativas ("Alerta Clínica"/"Adaptación Atlética"). Los 3 inputs se movieron a un bloque nuevo "🧍 Datos del paciente" dentro de esa página, colocado antes del interruptor de origen de datos (la sección que sí los consume, tanto en el modo Base de Datos como en el Ingreso Manual). Mismas claves de `session_state` (`pac_edad`/`pac_actividad`/`pac_cirugias`) — cero cambio en los puntos de lectura existentes, solo cambió dónde se renderiza el widget. El input de Edad se simplificó de `text_input` + parseo manual con `try/except` a `st.number_input` directo (mismo default 25, mismo tipo `int`) — limpieza menor de un patrón frágil que solo existía por vivir en el sidebar.

**Caso especial — checkbox de edad en Twin OS** (`app/supermodules/twin_shell/pages.py`, panel de riesgo): seguía leyendo `st.session_state.get("pac_edad")` (sin default, ya seguro — devuelve `None` si la clave no existe) para un opt-in explícito hacia `PatientRiskPredictor.calculate_risk_score(age=...)`. Confirmado que `age: Optional[int] = None` ya estaba diseñado para omitir el factor cuando no hay dato (mismo patrón que los demás factores opcionales de esa función) — cero cambio de código necesario ahí, solo el texto del checkbox ("Incluir edad de la Ficha Clínica Global" → "Incluir edad ingresada en Biomarkers Lab", con nota explícita de que si el usuario no visitó esa página, el checkbox simplemente no tiene edad que incluir, sin romperse).

El bloque `# --- FICHA CLÍNICA GLOBAL EN BARRA LATERAL ---` desapareció por completo del sidebar.

### Verificación

- `AppTest` (`app/main.py`, `from_file`): 0 excepciones en Home, Biomarkers Lab, Digital Twin OS y Guides. Confirmado en vivo: tras visitar Biomarkers Lab, `pac_edad`/`pac_actividad`/`pac_cirugias` existen en `session_state` (valor por defecto correcto, 25/Moderado/False); `pac_nombre`/`pac_peso` NO existen (ni rastro). Guides ya no menciona "Mission Control" y sí menciona el selector de la barra lateral.
- `pytest tests/` (excluyendo los 3 archivos con error de colección preexistente y no relacionado): **267/267 passed en 24.84s**, sin regresión.
- Servidor real: **HTTP 200**.
- Aislamiento: cero cambios en `domain/physiology/*`, el narrador, o cualquier lógica de cálculo — Parte A fue puramente retirar UI redundante; Parte B fue puramente mover 3 widgets a la página que ya los consumía (mismas claves, mismos consumidores, mismos valores por defecto) y borrar 2 widgets sin consumidor.

## 2026-08-05 — Rendimiento del motor hemodinámico: solución analítica de la EDO R-RCR (Opción C)

**Contexto**: un diagnóstico de rendimiento previo (solo medición, sin cambios, sin entrada propia en este CHANGELOG) encontró la causa raíz: `simulate_r_rcr()` (`domain/physiology/hemodynamics/r_rcr.py`) resolvía con `scipy.integrate.solve_ivp(method="Radau", rtol=1e-10, atol=1e-12)` una EDO lineal de primer orden con forzamiento periódico — analíticamente resoluble a mano. Costo medido: ~2.6s por llamada, invocada en cada tick de `run_baroreflex()`/`run_closed_loop()` (hasta 40 ticks cada uno). El usuario eligió la Opción C: reemplazar la integración numérica por la forma cerrada de la MISMA ecuación citada de svZeroD — no un modelo nuevo, la misma física, resuelta exactamente en vez de aproximada.

### Paso 1 — Derivación e implementación

La EDO (`dP_c/dt = (Rd·Q(t) - P_c + Pd) / (Rd·C)`, ya citada verbatim de `WindkesselBC.h`/`BloodVessel.cpp`) es lineal de primer orden. Los tres `flow_fn` reales del proyecto (`steady_flow_reference`, `pulsatile_flow_reference`, `physiological_pulsatile_flow`) son todos de la forma `Q(t) = Q0 + Qs·sin(ωt) + Qc·cos(ωt)` — componente continua + un solo armónico. Con τ=Rd·C, resolviendo por factor integrante (solución particular periódica + transitorio que decae como e^(−t/τ), ajustado a la misma condición inicial `P_c(0)=Rd·Q0+Pd` que ya usaba la versión numérica):

```
P_c(t) = (Rd·Q0 + Pd) + A_sin·sin(ωt) + A_cos·cos(ωt) − A_cos·e^(−t/τ)
D = C·(1 + ω²τ²);  A_sin = τ·(Qs + Qc·ω·τ)/D;  A_cos = τ·(Qc − Qs·ω·τ)/D
```

Verificado a mano ANTES de implementar: con los parámetros oficiales, esta fórmula reproduce exactamente 10500/10000 (flujo constante) y 4620/4400 (flujo pulsátil, t=0) — coincidencia algebraica directa, no solo numérica.

Implementación en `r_rcr.py`: `_fourier_fundamental_coefficients()` extrae (Q0, Qs, Qc) de cualquier `flow_fn` por cuadratura (barata — no es la parte cara) y verifica que la reconstrucción `Q0+Qs·sin+Qc·cos` reproduce el `flow_fn` real dentro de tolerancia relativa 1e-6. Si no coincide (el único caso en todo el proyecto: `step_flow` en `test_higher_compliance_slows_the_transient_not_the_steady_value`, una función escalón usada deliberadamente para probar el efecto de la compliancia sobre un transitorio) `simulate_r_rcr()` cae automáticamente al `solve_ivp` numérico original, sin cambios — nunca produce un resultado analítico silenciosamente incorrecto para una forma que no puede resolver exactamente. Interfaz de `simulate_r_rcr()` sin cambios (mismos argumentos, mismo `RRCRResult`) — nada aguas arriba (barórreflejo, lazo cerrado, puente al UPS) nota el cambio salvo en velocidad.

### Paso 2 — Verificación triple

**1. Checkpoints oficiales de svZeroD**: `pytest tests/test_hemodynamics_r_rcr.py` — **8/8 passed** en 2.72s (antes 15.26s), incluidos ambos checkpoints publicados exactos y el test de la curva convergida contra la corrida genuina del solver oficial (mismo margen `abs=0.5` que ya tenía, sin relajar). El test del escalón (fallback numérico) también pasa — confirma que la ruta de respaldo sigue intacta.

**2. Coincidencia con el numérico de alta precisión**: comparación directa `_analytic_capacitor_pressure()` vs. `solve_ivp(Radau, rtol=1e-10)` forzado, sobre `physiological_pulsatile_flow` en HR∈{40, 72, 85, 90, 95, 150, 220} + los casos oficiales pulsátil/estacionario — diferencia relativa máxima **~2.3e-11** en todos los casos (dentro del propio error del integrador Radau, no un error de la fórmula). Tiempo por llamada: ~3-5ms analítico vs. ~1.8-4.3s numérico — **~500-1000x más rápido por llamada**.

**3. Puntos fijos del lazo cerrado, corridos con la nueva `simulate_r_rcr`**:

| Escenario | HR | S/D/PAM (antes → ahora) | Ticks | Flags |
|---|---|---|---|---|
| healthy | 72 | 113.3/73.3/93.33 → **113.33/73.33/93.33 — idéntico** | 1 → 1 | — |
| hypertension | 85 | 121.6/83.7/102.66 → **121.57/83.75/102.66 — idéntico** | 4 → 4 | — |
| sepsis | 150 | 26.4/22.0/24.20 → **26.40/22.00/24.20 — idéntico** | 13 → 13 | `clamped_at_max_rd=True` en ambos |

Los tres equilibrios validados (Rondas 1-2 + estabilidad del lazo) quedan bit-a-bit consistentes con los ya confirmados — cero deriva fisiológica, tal como exige la regla constitucional de esta tanda. Sepsis sigue colapsando muy por debajo de 65 mmHg (shock).

Las tres verificaciones pasaron limpiamente — no hubo discrepancia que reportar ni fórmula que "ajustar".

### Paso 3 — Mejora de rendimiento medida

- **Por llamada a `simulate_r_rcr`**: ~2.6s (Radau) → ~3-5ms (analítico) — **~500-1000x**.
- **Suite completa** (`pytest tests/`, excluyendo los 3 archivos con error de colección preexistente): **267/267 passed en 26.74s** — antes 3:38:28 (3h38m, medido por el usuario) / 1:02:03 (corrida "limpia" de una tanda previa) — **~490x más rápida** contra la medición del usuario.
- Servidor real: **HTTP 200**.

### Aislamiento

Cambios exclusivamente en `domain/physiology/hemodynamics/r_rcr.py` (nueva ruta analítica + fallback; `_cycle_mean_flow` retirada por quedar sin uso, su cálculo de Q0 absorbido en `_fourier_fundamental_coefficients`). `run_baroreflex()` **no tocado** (el amplificador — bucle sin sub-relajación cerca de HR≈85-98 — queda para una tanda aparte, como se pidió). `baroreflex.py`, `pathological_tone.py`, `closed_loop.py`, `physiological_flow.py` — sin cambios, siguen llamando a `simulate_r_rcr()` con la misma interfaz. No se requiere firma del validador (no cambia fisiología, cambia el método de cálculo de la misma fisiología ya validada) — los tres puntos fijos idénticos son la prueba de que así fue.

## 2026-08-04 — Pulido rápido, Tanda 1: dos arreglos mecánicos de bajo riesgo

Retoma de la lista de pendientes tras cerrar "La película". Ambos ítems se anotaron hace muchas tandas — se verificó vigencia primero, antes de tocar nada, dado que el repo cambió bastante desde entonces (consolidación de hubs, eliminación de Research Hub).

### Ítem A — Duplicados de menú en Learning Hub: seguía vigente, corregido

Verificado antes de tocar nada: el patrón "Bug 3" (`HUBS[...]` con dos entradas por módulo — nombre legible con emoji + nombre "interno" sin emoji, renderizadas como dos filas separadas en el `selectbox`) ya se había corregido en Clinical Hub (2026-07-12) y en esa misma entrada del CHANGELOG se dejó anotado como pendiente para Learning Hub si se confirmaba. Se confirmó: `HUBS["Learning Hub"]` (`app/main.py`) seguía teniendo `"🎓 Education"`/`"Education"` y `"🏫 Academia Clinica"`/`"Academia_Clinica"` duplicados (5 entradas para 3 módulos). Research Hub, que compartía el mismo bug, ya no existe — fue absorbido en la fusión de navegación del 2026-07-14 (su único contenido real, Patient Pipeline, se movió a Clinical Hub) — por lo tanto no aplicaba nada ahí.

Arreglo, mismo patrón que Clinical Hub (sin reinventar la solución): confirmado primero que `render_page_content()` enruta por substring (`"Academia" in page`, `"Education" in page`, con `Guides` como default) — el nombre con emoji por sí solo ya satisface cada condición. Se eliminaron las 2 entradas internas duplicadas, quedando `HUBS["Learning Hub"] = ["🎓 Education", "🏫 Academia Clinica", "📚 Guides"]` (3 entradas, antes 5).

**Verificación**: `AppTest` cargó los 3 módulos de Learning Hub uno por uno tras el cambio — 0 excepciones en los 3.

### Ítem B — Gráfico de importancia en Twin OS: seguía vigente, añadido

Verificado antes de dibujar nada: `result.shap_lime["importance"]` (`EcgClassificationResult`, `domain/physiology/ml/ecg_classification.py`) sigue existiendo — lo produce `compute_feature_importance()` en `src/interpretability.py` (llamado desde `generate_shap_lime_report()`, sin tocar), una lista ordenada de dicts (`feature`, `label`, `value`, `baseline`, `delta`, `weight`, `percent`, `direction`, `human`) — importancia relativa por desviación absoluta de un baseline fijo, normalizada a 100% entre las features. Ya alimentaba las narrativas de las pestañas "SHAP"/"LIME" existentes en `render_ecg_classifier_panel()` (`app/supermodules/twin_shell/pages.py`), pero nunca se dibujaba.

Arreglo, puramente visualización — cero cálculo nuevo: se añadió una tercera pestaña "Importancia" junto a las dos existentes, que arma un `pd.DataFrame` directo de `item["percent"]`/`item["label"]` del mismo `result.shap_lime["importance"]` ya calculado, y lo dibuja con `st.bar_chart()` (mismo patrón que los `st.line_chart()` ya usados en este archivo — sin introducir una librería de gráficos nueva). Etiquetado honesto explícito en la pestaña: "Importancia por desviación de baseline (estilo SHAP: |valor-baseline| normalizado a 100% entre las features) — NO es SHAP/LIME real de una librería, es la misma heurística que ya narran las pestañas SHAP/LIME" — mantiene la distinción ya establecida en el código fuente (`shap_like_explanation`/`lime_like_explanation` en `src/interpretability.py`, nombradas así desde su creación).

**Confirmación de que solo se visualizó, sin recalcular nada**: la función `compute_feature_importance()` y su firma no se tocaron; el nuevo bloque solo lee `item["percent"]`/`item["label"]` de la lista que esa función ya devuelve. Verificado con dos pruebas directas (sin mocks): (1) `generate_shap_lime_report()` invocado con features sintéticas confirma que `report["importance"]` sigue teniendo esa estructura exacta; (2) `classify_ecg_signal()` invocado con una señal ECG realista (sinusoide + picos QRS periódicos, 15 picos R detectados) — la ruta REAL que usa el panel — confirma que `result.shap_lime["importance"]` llega poblado y que el código exacto de construcción del `DataFrame` añadido a `pages.py` lo consume sin error.

### Verificación de proyecto

- `AppTest`: 3/3 módulos de Learning Hub cargan con 0 excepciones tras el Ítem A.
- Ruta real del Ítem B verificada con una señal ECG sintética realista (no solo con datos fake) — `shap_lime["importance"]` poblado, `DataFrame` construido sin error.
- `pytest tests/` (excluyendo los mismos 3 archivos con error de colección preexistente y no relacionado): **267/267 passed en 3:38:28**, sin regresión.
- Servidor real: **HTTP 200**.
- Cero cambios en `domain/physiology/*`, el narrador, o la lógica de explicabilidad (`compute_feature_importance`, `shap_like_explanation`, `lime_like_explanation` intactas) — el Ítem B fue estrictamente dibujar un dato ya producido. Ficha Clínica Global y Mission Control no tocados — quedan para una tanda aparte tras auditoría, como se pidió.

## 2026-08-01 — "La película", Conexión al UPS: los 3 escenarios validados, en coexistencia (paso final)

**Contexto**: hasta esta tanda, todo el motor hemodinámico de lazo cerrado (Módulos 1-3, eslabón 1, Módulo 4B-i/ii, Rondas 1-2 de validación cuantitativa, estabilidad numérica) vivía completamente aislado del UPS — comparado contra él en tests, nunca escribiéndole. Esta es la primera escritura real: `closed_loop.py` persiste PA calculada al UPS vivo, para los 3 escenarios con validación experta completa (`healthy`, `hypertension`, `sepsis`), en coexistencia con la `ClinicalReferenceValue` ya existente. El usuario pidió máxima verificación de no-regresión — este es "el paso que pone la película frente al estudiante".

### Paso 1 — Restricción estructural, no un `if` evitable

`HEMODYNAMIC_MODEL_ENABLED_SCENARIOS = frozenset({"healthy", "hypertension", "sepsis"})` (`domain/physiology/hemodynamics/closed_loop_ups_bridge.py`) es la única fuente de verdad. `compute_and_attach_closed_loop_pressure()` la consulta en su primera línea y **lanza** `HemodynamicModelNotEnabledError` — nunca retorna `None` en silencio — para cualquier otro escenario; no hay una segunda ruta de código que persista PA del lazo cerrado sin pasar por este guard. Verificado que la excepción se lanza ANTES de tocar la sesión (pasando `session=None`).

Los otros 9 escenarios quedan fuera, cada uno con su razón específica documentada en el docstring del módulo (ya diagnosticadas en "Reconocimiento" y "Estabilidad del lazo", misma fecha):

| Escenario | Razón de exclusión |
|---|---|
| `exercise` | bug ajeno al lazo: `_simulate_exercise()` no acota `recovery_progress`, produce HR=-14580 a 7 días |
| `stress`, `anxiety` | la referencia clínica es un pico agudo transitorio; el lazo solo modela equilibrio estacionario |
| `apnea`, `seizure` | mismatch de fase: HR del snapshot es basal/recuperado, la referencia describe la fase aguda |
| `arrhythmia` | falta driver de efectividad de bombeo reducida — el barórreflejo normaliza en vez de descompensar |
| `hypoxia` | falta driver quimiorreceptor de presión — el barórreflejo normaliza en vez de mostrar hipertensión reactiva |
| `fatigue`, `copd` | sin `ClinicalReferenceValue` citada — nada contra qué validar el punto fijo |

### Paso 2 — Confianza: validado, pero sigue siendo un cálculo de modelo

`HEMODYNAMIC_MODEL_VALIDATED_CONFIDENCE = 0.75`. La banda de `Provenance.MODELO_HEMODINAMICO` se ensanchó de (0.30-0.55) a **(0.30-0.80)** en `schema.py` para representar dos regímenes bajo la misma procedencia: extremo bajo para cálculos sin validación experta en contexto, extremo alto (0.70-0.80) para los que sí la tienen. 0.75 queda por encima del techo antiguo (0.55, ya no aplica — "cálculo con parámetros pendientes sin revisar"), dentro del rango de `SIMULACION` (0.60-0.90) sin alcanzar su techo, y siempre por debajo del piso de `SENSOR_REAL` (0.85) — nunca es una medición. El puente estático original del Módulo 1 (`ups_bridge.py`, nunca invocado desde la app viva) se fijó explícitamente a su valor histórico `0.425` para no heredar sin querer el nuevo punto medio de la banda ensanchada — no cambió su propio estado de validación en esta tanda.

### Paso 3 — Coexistencia real, extendida al flujo vivo

`compute_and_attach_closed_loop_pressure()` usa `append_descriptors()` para adjuntar `systolic_bp_modelo`/`diastolic_bp_modelo`/`map_modelo` al snapshot YA EXISTENTE — nunca crea uno nuevo, nunca toca la `ClinicalReferenceValue` que `run_rich_scenario()` ya adjuntó al mismo snapshot. Único punto de cableado vivo: `app/supermodules/twin_shell/pages.py::render_ups_scenario_simulator()`, justo después del bucle de `run_rich_scenario()`, dentro de la misma sesión — solo cuando el escenario corrido está en `HEMODYNAMIC_MODEL_ENABLED_SCENARIOS`. Se añadió un bloque visible que muestra la PA calculada junto a la referencia, etiquetado explícitamente "🧮 PA calculada por el modelo hemodinámico (lazo cerrado, validado)". Deliberadamente NO cableado en `render_diagnostic_case()` (el juego de caso oculto) para minimizar superficie de cambio.

**Decisión del modelo de riesgo** (`domain/physiology/ml/risk_context.py`): sigue leyendo `systolic_bp`/`diastolic_bp` EXCLUSIVAMENTE de `ClinicalReferenceValue`, nunca de los descriptores `_modelo` — confirmado que el código ya lo hacía así, cero cambio funcional, solo un bloque de comentario documentando la decisión explícita. Razón: la referencia es un valor citado y estable por escenario; la PA calculada es un valor didáctico/comparativo para que el estudiante compare "lo que predice el modelo" contra "lo que dice la literatura", pero el score de riesgo debe apoyarse en la fuente más citable.

### Paso 4 — No-regresión en todo lo que lee el UPS

- **Narrador clínico** (`domain/physiology/narrator/`): `build_context()` es genérico — no distingue procedencias, expone `map_modelo` igual que cualquier descriptor, sin cambios necesarios. El system prompt (`prompt.py`, regla 4) se actualizó para incluir `modelo_hemodinamico` explícitamente, con instrucción de declarar el valor como cálculo ("la PA calculada por el modelo hemodinámico es...") y nunca confundirlo con la referencia clínica presente en el mismo contexto. Verificado con test dedicado.
- **Modelo de riesgo**: sin cambio funcional (ver Paso 3) — test dedicado confirma que sigue devolviendo exactamente el valor de la referencia (130.0/80.0 en hipertensión) aunque la PA calculada exista y difiera.
- **Cuerpo visual** (`app/supermodules/twin_shell/ups_body_visual.py`): confirmado por grep que nunca referencia campos sistólico/diastólico — cero riesgo de regresión, por inspección directa.
- **Casos sintéticos / banco de casos**: `render_diagnostic_case()` no fue tocado, no llama a la nueva función — no afectado.
- Los 9 escenarios no conectados: verificados con test parametrizado que los 9 siguen lanzando `HemodynamicModelNotEnabledError` sin excepción.

### Verificación de proyecto

- 57 tests nuevos/tocados en 4 archivos: `test_hemodynamics_ups_bridge.py` (puente estático re-anclado a 0.425 exacto), `test_hemodynamics_closed_loop_ups_bridge.py` (nuevo — gate estructural, confianza, coexistencia en flujo vivo equivalente a `render_ups_scenario_simulator()` para los 3 escenarios, no-drift contra `run_closed_loop()` directo), `test_narrator.py` (PA calculada surge en el contexto con la procedencia correcta y el prompt la declara honestamente), `test_clinical_reference.py` (modelo de riesgo sigue usando la referencia, no el cálculo). Todos pasaron: 1033.37s.
- `pytest tests/` (suite completa, excluyendo los 3 archivos con error de colección preexistente y no relacionado): **267/267 passed en 1:02:03**, sin regresión en ningún test previo.
- Servidor real: **HTTP 200**.
- Aislamiento: `closed_loop.py`, `baroreflex.py`, `pathological_tone.py`, `frank_starling.py`, `diastasis_ceiling.py`, `physiological_flow.py` — ninguno modificado en su lógica de cálculo (solo el nuevo archivo `closed_loop_ups_bridge.py` los envuelve). `render_diagnostic_case()`, `ups_body_visual.py`, `risk_context.py` (funcionalmente) — sin cambios.

**Firma del validador (confirmación de estabilidad)**: los 3 puntos fijos persistidos (healthy 113.3/73.3/93.33, hypertension 121.6/83.7/102.66, sepsis 26.4/22.0/24.20 mmHg) son exactamente los mismos que Ronda 2 + estabilidad del lazo ya habían validado — esta tanda no recalculó fisiología nueva, solo conectó al UPS un motor cuyo comportamiento numérico ya estaba cerrado. Coexistencia confirmada: en la misma consulta del snapshot, `ClinicalReferenceValue` y los 3 descriptores `_modelo` sobreviven juntos, sin que ninguno sobrescriba al otro.

**Pendiente**: los 9 escenarios no conectados siguen necesitando sus propios drivers (`exercise`: fix de `recovery_progress`; `arrhythmia`/`hypoxia`: drivers fisiológicos faltantes; `stress`/`anxiety`/`apnea`/`seizure`: mismatch transitorio/fase, requiere decidir si el lazo modela transitorios algún día; `fatigue`/`copd`: sin referencia citada todavía) — fuera de alcance de esta tanda, que era exclusivamente la conexión de los 3 ya validados.

## 2026-08-01 — "La película", estabilidad del lazo a HR alto: sub-relajación (solución numérica, no fisiológica)

**Contexto**: el "Reconocimiento" de los 9 escenarios no validados (misma fecha) reveló que el lazo cerrado entraba en un ciclo límite de periodo 2 (oscilaba en vez de converger) para HR por encima de ~95-98 bpm. El usuario pidió diagnóstico ANTES de solución, y fue explícito en algo importante: esto es un problema de estabilidad numérica del controlador discreto, no de fisiología -- distinto en naturaleza a todas las tandas anteriores de esta serie, y por eso el validador fisiológico no era quien debía dictaminar la causa (sí lo es para confirmar, al final, que la solución no movió nada fisiológico ya validado).

### Diagnóstico (solo lectura/análisis, entregado antes de tocar código)

**Umbral exacto**: entre HR=95 (converge, 38 ticks -- al límite) y HR=98 (no converge). Ralentización crítica visible justo antes del umbral (24→28→30→33→38 ticks según sube el HR de 85 a 95) -- firma clásica de acercarse a una bifurcación.

**Amplitud**: crece continuamente desde cero al cruzar el umbral (0.0105 mmHg a HR=98 → 0.0408 mmHg a HR=105 → ~30 mmHg a HR=200) -- no es un salto abrupto, es una bifurcación de tipo flip (periodo-doblante). Sigue siendo periodo 2 incluso en el caso más extremo probado (HR=200), solo que con amplitud mucho mayor -- nunca se volvió periodo 4 ni caótico.

**Causa, confirmada con evidencia numérica directa** (ganancia local dM/dRd, linealizada en el mismo Rd de referencia, con SV fija vs. SV acoplada vía la cadena real de retorno venoso):
- Con SV fija (imitando al Módulo 2 aislado): ganancia se mantiene ~0.10-0.27 en TODO el rango de HR (72 a 200) -- nunca cruza inestabilidad.
- Con SV acoplada (el lazo cerrado real): la ganancia es ~2x mayor desde el principio, y ES la que cruza |factor|=1 al subir el HR (de -0.90 a HR=95 a -1.04 a HR=123.3, en la aproximación linealizada -- el cruce real, verificado empíricamente, ocurre antes, entre HR 95-98, porque el equilibrio real tiene un Rd más bajo donde la ganancia es aún mayor).
- Control directo: el Módulo 2 aislado (`run_baroreflex`, SV fija de verdad) NO osciló en ningún HR probado, hasta 220 -- confirma sin ambigüedad que `BAROREFLEX_GAIN_K=1.0` queda EXONERADO.

**Mecanismo**: `RVR` escala con `Rd_base/Rd_actual` (Módulo 4B-ii, ya validado) → el retorno venoso escala con `Rd_actual` → más Rd produce más SV, no solo más resistencia -- esa doble vía duplica la ganancia efectiva del lazo cerrado frente al Módulo 2 aislado. Y esa amplificación crece con HR porque a HR alto el EDV de equilibrio es menor (menos tiempo de llenado, eslabón 1 de Frank-Starling), lo que opera la curva saturante de Frank-Starling en su tramo más empinado (mayor dSV/dEDV local) -- confirmado empíricamente: SV(rd0) cae de 70 mL (HR=72) a 20.8 mL (HR=200) mientras dM/dRd_acoplada sube de 161 a 202. Es la interacción de dos mecanismos YA VALIDADOS (acoplamiento Rd→RVR, Ronda 2; forma de la curva de Starling, Ronda 2) en un régimen (HR alto) donde ninguno fue diseñado ni probado en conjunto -- no es un error en ninguno de los dos por separado.

### Solución elegida: sub-relajación (Opción A del diagnóstico)

`CLOSED_LOOP_RELAXATION_FACTOR = 0.5` -- constante NUMÉRICA de convergencia, marcada explícitamente "control numérico, NO parámetro fisiológico", sin bandera `PENDING_VALIDATION` (mismo tratamiento que `CLOSED_LOOP_MAX_TICKS`/`CLOSED_LOOP_CONVERGENCE_TOL`, ya existentes). Vive enteramente en `closed_loop.py` -- **`baroreflex.py` y `BAROREFLEX_GAIN_K` no se tocaron para nada**.

Mecánica: en vez de aceptar completo el candidato de Rd que propone un tick del barórreflejo, el lazo se mueve solo una fracción α hacia ese candidato -- `rd_siguiente = rd_actual + α·(rd_candidato − rd_actual)`. Matemáticamente demostrable que esto NO puede mover el punto fijo: si Rd* es punto fijo de la iteración completa (candidato = Rd*), también lo es de la versión amortiguada, para cualquier α -- la ecuación de equilibrio (`M(Rd*, SV(Rd*)) = target_map`) no contiene α. Solo cambia la velocidad/trayectoria de convergencia (nuevo factor de amplificación = `1 − α·ganancia_original`).

**Criterio de α=0.5**, no ajustado a ningún resultado de PA: incluso en el peor caso medido (HR=200, ganancia≈2.12), α=0.5 deja el nuevo factor en ≈−0.06 (muy por debajo de 1, margen amplio) -- a HR más realistas el margen es todavía mayor. Efecto colateral honesto (no buscado, verificado): también acelera la convergencia en casos que ya convergían sin oscilar (menos ticks, no solo estabilidad).

**Instrumentación añadida**: `ClosedLoopTick.rd_candidate` (el paso crudo del barórreflejo, ANTES de amortiguar) junto a `rd_after` (el Rd realmente usado, YA amortiguado) -- transparencia total, auditable tick a tick. La presión (S/D/PAM) de cada tick se reevalúa en el Rd ya amortiguado (una pasada extra, `max_ticks=0`, sin ajuste adicional) para que lo reportado corresponda exactamente al Rd que se lleva al tick siguiente.

**Hallazgo de instrumentación durante la verificación, corregido en la misma tanda**: `clamped_at_min_rd`/`clamped_at_max_rd` originalmente se leían del Rd YA amortiguado -- pero el Rd amortiguado se acerca a un límite (min_rd/max_rd) de forma ASINTÓTICA y en general nunca lo toca exactamente dentro de la ventana de convergencia. Verificado con sepsis: el candidato crudo queda clavado exactamente en `SEPSIS_MAX_RD_MMHG_S_ML` desde el tick 2 en adelante (el reflejo SÍ está comandando saturación en cada tick), pero el Rd amortiguado solo llega a ~99.994% del techo al converger -- leer el clamp del valor amortiguado habría reportado `clamped_at_max_rd=False`, perdiendo la señal de "reflejo saturado" que sí está presente. Corregido: el clamp se lee del candidato crudo (`one_tick_result`, antes de amortiguar) -- la señal fisiológicamente relevante es si el controlador está COMANDANDO ir más allá del límite, no si la trayectoria amortiguada ya llegó físicamente ahí.

### Verificación -- los tres puntos fijos validados, MISMO equilibrio, ya sin oscilar

| Escenario | HR | Antes (oscilaba o convergía lento) | Después (sub-relajación) | Ticks |
|---|---|---|---|---|
| healthy (ancla) | 72 | 113.3/73.3/93.33, 1 tick | **113.3/73.3/93.33 -- idéntico** | 1 |
| hypertension | 85 | 121.6/83.7/102.66, 26 ticks | **121.6/83.7/102.66 -- idéntico**, sin oscilar | 4 |
| sepsis | 150 | 26.4/22.0/24.20, 3 ticks, `clamped_max_rd=True` | **26.4/22.0/24.20 -- idéntico**, `clamped_max_rd=True` intacto | 13 |

Los tres puntos fijos son EXACTAMENTE los mismos (dentro de la precisión numérica del solver) -- solo cambió la trayectoria (sepsis ahora toma más ticks porque se acerca a su techo de forma amortiguada/asintótica en vez de saltar ahí; hipertensión y sano en realidad convergen en MENOS ticks que antes).

**Escenarios que antes oscilaban a HR alto, ahora convergen:**

| Escenario | HR | Resultado |
|---|---|---|
| stress | 105 | converge, 3 ticks, PAM=93.33 |
| (healthy, override hipertensión) | 110 | converge, 4 ticks, PAM=102.67 |
| (healthy, override hipertensión) | 123.3 | converge, 3 ticks, PAM=102.67 |

**Barrido completo de HR hasta 220** (escenario "healthy", sin override): converge sin oscilar en TODO el rango probado (72, 80, 85, 90, 95, 98, 100, 105, 110, 115, 120, 123.3, 130, 150, 180, 200, 220) -- entre 1 y 6 ticks en cada punto, muy por debajo de `CLOSED_LOOP_MAX_TICKS=40`.

(Nota: converger no significa que la PA de `arrhythmia`/`hypoxia` sea fisiológicamente correcta todavía -- siguen necesitando sus propios drivers, ver "Reconocimiento". Lo que se arregló aquí es que el lazo ya no oscila numéricamente a esos HR, un requisito previo para poder evaluar esos escenarios en absoluto.)

### Verificación de proyecto

- 25 tests nuevos (`tests/test_hemodynamics_closed_loop_stability.py`): la constante es numérica no fisiológica (sin bandera propia), `BAROREFLEX_GAIN_K` intacto, los tres puntos fijos validados reproducidos exactamente sin oscilar, barrido paramétrico de 14 puntos de HR (88 a 220) todos convergiendo sin oscilar, instrumentación candidato-vs-amortiguado verificada con la fórmula exacta de sub-relajación, el caso de sepsis (candidato saturado vs. amortiguado asintótico) verificado directamente, y la mejora de velocidad de convergencia documentada.
- Tests preexistentes: 62 pasaron sin ningún cambio de aserciones -- solo se corrigió un constructor manual de `ClosedLoopTick` en `test_hemodynamics_closed_loop.py` (campo nuevo `rd_candidate` obligatorio en el dataclass).
- `pytest tests/`: **249/249 passed** (224 previos + 25 nuevos; mismos 3 archivos con error de colección preexistente y no relacionado).
- Servidor real: **HTTP 200**.
- Aislamiento: `baroreflex.py`, `pathological_tone.py`, `frank_starling.py`, `diastasis_ceiling.py`, `physiological_flow.py` -- ninguno tocado. El cambio completo vive en `closed_loop.py` y sus tests.

**Pendiente**: los escenarios que ya convergen numéricamente (`arrhythmia`, `hypoxia`) pero cuya PA sigue sin coincidir con su referencia clínica -- necesitan sus propios drivers fisiológicos (efectividad de bombeo reducida / quimiorreceptor de presión, respectivamente), ese trabajo queda fuera de esta tanda (era explícitamente de estabilidad numérica, no de fisiología nueva).

## 2026-07-31 — Validación cuantitativa — Ronda 2: cosecha final, cinco banderas bajan enteras

**Firma del validador**: el validador experto del usuario dictaminó los ~13 parámetros que quedaban pendientes tras Ronda 1 (entrega previa de clasificación por categoría -- cita directa / forma validada / umbral cualitativo -- sirvió exactamente para evitar inflar un umbral a cita, ver Operación de VENOUS_CAPACITANCE_SEPSIS_MULTIPLIER abajo). Todos los dictámenes verificados con ejecución real tras cada cambio -- ningún número de esta entrada fue inventado.

### Registro de cada dictamen, con su naturaleza correcta (no todo es "cita")

**Cita directa** (cantidad fisiológica medible con cifra de literatura):

| Parámetro | Valor | Cita registrada |
|---|---|---|
| `PHYSIOLOGICAL_RRCR_PARAMETERS.pd` | 2.0 mmHg | Estándar de reposo en modelos de lazo cerrado. **Hallazgo emergente registrado especialmente**: el gradiente de retorno venoso `P_sf−Pd` = 7.0−2.0 = **5.0 mmHg** coincide con el orden de magnitud que Guyton Cap. 20 describe para ese gradiente -- no se ajustó Pd para lograr esto, se calculó en Ronda 1 y se confirmó después. |
| `BAROREFLEX_TARGET_MAP_MMHG` | 93.33 mmHg | Traducción directa de 120/80 (ACC/AHA 2017, ya citado) vía `estimate_map()` -- consecuencia aritmética de dos cifras ya validadas, no una estimación aparte. |
| `Rp`+`Rd` (magnitud total) | ≈1.0873 mmHg·s/mL | Guyton: RPT normal ≈1 PRU. La división 90/10 entre ambos es **forma validada** (convención Windkessel de 3 elementos, Westerhof et al.), no una cifra de página independiente. |
| `EDV_FLOOR_ML` | 20 mL | Protege contra colapso quedando por debajo del VTS (volumen telesistólico) normal, ~40-50 mL. |
| `HYPERTENSION_RESET_TARGET_MAP_MMHG` | 102.67 mmHg | +10% consistente con hipertensión Estadio 1 sostenida (reseteo moderado del barostato, no crisis hipertensiva). |
| `SEPSIS_MAX_RD_MMHG_S_ML` / `SEPSIS_GAIN_K` | 0.5× / 0.3× | Ambos caen en el rango de refractariedad 30-50% del máximo descrito para shock refractario -- validados JUNTOS como un mismo grado de refractariedad expresado en dos efectores (techo alcanzable, velocidad de respuesta). |
| `BAROREFLEX_GAIN_K` | 1.0 | Ganancia de control sensata que evita oscilación (ya verificado computacionalmente en toda la serie -- ningún escenario típico osciló). |

**Forma validada** (NO es cita de magnitud -- la forma funcional es lo que se confirmó, el número queda determinado por esa forma + un ancla ya citada):

| Parámetro | Valor | Qué se validó |
|---|---|---|
| `FRANK_STARLING_STEEPNESS_ML` | ≈144.27 mL | La curva exponencial-saturante en sí es correcta para representar el traslape actina-miosina a nivel de sarcómero (satura de forma asintótica, no linealmente). |
| `DIASTASIS_TRANSITION_BUDGET_ML` | 60.0 mL | La transición hacia el techo de diástasis es asintótica (se frena progresivamente, no se detiene en seco) -- consistente con la fisiología de la diástasis. |
| `RVR_REFERENCE_MMHG_S_ML` | ≈0.03472 mmHg·s/mL | Única solución posible de la ley de Ohm (R=V/I) dado un gradiente YA VALIDADO (P_sf=7.0, Pd=2.0) y un flujo objetivo YA CITADO (el ancla EDV=120mL/72bpm) -- no tiene grado de libertad propio. |

**Umbral heurístico aceptado -- explícitamente NO cita directa** (regla estricta de esta ronda: no inflar un umbral a cita):

- `VENOUS_CAPACITANCE_SEPSIS_MULTIPLIER=2.0`: el validador aclaró explícitamente que **no existe una cifra universal citable** (a diferencia de MIN_RD/MAX_RD, que sí tenían fracciones citadas con página) -- es una convención de simulación razonable, **aceptada como tal**, no verificada contra una magnitud publicada. Registrado en el código con esta distinción deliberada.

**Validación oficial de una decisión estructural** (no cubierta por ninguna bandera `PENDING_VALIDATION` propia, pero documentada formalmente):

- **Acoplamiento Rd→RVR** (`closed_loop.py`, dirección `RVR=RVR_ref·(Rd_base/Rd_actual)`): validado oficialmente -- los receptores alfa-1 adrenérgicos median tanto la constricción arteriolar (Rd) como la venoconstricción, mismo receptor, mismo tono simpático, dos efectores. La dirección queda confirmada por esta cita; la magnitud (cociente lineal, sin exponente adicional) sigue respaldada por la estabilidad estructural ya verificada en el Módulo 4B-ii (la alternativa con signo opuesto colapsaba todos los escenarios por igual, un artefacto).

### Banderas: cinco bajan enteras, una queda reducida a un solo parámetro

| Bandera | Antes de Ronda 2 | Ahora |
|---|---|---|
| `BAROREFLEX_PARAMETERS_PENDING_VALIDATION` | MIN_RD/MAX_RD validados (R1); k/target_map pendientes | **False** -- los 4 confirmados |
| `PATHOLOGICAL_TONE_PENDING_VALIDATION` | 3/3 pendientes | **False** -- los 3 confirmados |
| `FRANK_STARLING_PARAMETERS_PENDING_VALIDATION` | EDV_HEALTHY/SV_MAX validados (R1); FLOOR/STEEPNESS pendientes | **False** -- los 4 confirmados |
| `DIASTASIS_CEILING_PENDING_VALIDATION` | CEILING validado (R1); BUDGET pendiente | **False** -- los 2 confirmados |
| `VENOUS_RETURN_PARAMETERS_PENDING_VALIDATION` | P_sf validado (R1); RVR/capacitancia pendientes | **False** -- los 3 confirmados (+ acoplamiento Rd→RVR) |
| `PHYSIOLOGICAL_PARAMETERS_PENDING_VALIDATION` | Rp/Rd/Pd/C pendientes | **True, reducida a UN SOLO parámetro**: `C=0.807` (pendiente estructural, sin cambios -- Rp/Rd/Pd ahora validados) |

Los guards `if not FLAG: raise AssertionError(...)` que vivían en `run_baroreflex()`, `run_pathological_baroreflex()` (dos, una dependencia), `stroke_volume_frank_starling()`, `apply_diastasis_ceiling()`, `compute_dynamic_stroke_volume_with_diastasis_ceiling()` y `run_closed_loop()` (dos) se **retiraron conscientemente** -- existían para bloquear un flip a `False` sin revisión; esa revisión ya ocurrió y está documentada junto a cada constante y aquí. Verificado con ejecución real que cada función sigue operando con normalidad tras el retiro (sin regresión: ancla de reposo idéntica, hipertensión idéntica ≈102.67, sepsis sigue colapsando <65 mmHg).

### Mantenidos pendientes, honestos (sin tocar)

- **`C=0.807 mL/mmHg`**: pendiente ESTRUCTURAL, sin cambios -- no validable hasta modelar la curva de eyección ventricular pulsátil real.
- **`R_poiseuille=0.0`**: simplificación aceptada -- grado de libertad degenerado (fijado en 0 por diseño, no una magnitud libre), no requiere dictamen cuantitativo propio.
- **`VENOUS_RETURN_PLACEHOLDER_PENDING_MODULE_4B`** (bandera huérfana, retirada del flujo activo en Ronda 1): sin tocar en Ronda 2, sigue en `True` -- no tiene relación con las cinco banderas que sí bajaron.

### Estado final del motor hemodinámico

**20 parámetros numéricos identificados en el inventario de Ronda 0 → 18 con dictamen completo** (13 cita directa/forma validada de Ronda 2 + 5 de Ronda 1: MIN_RD, MAX_RD, EDV_HEALTHY_ML, SV_MAX_ML, EDV_ANATOMICAL_CEILING_ML), **+ 1 umbral heurístico aceptado** (VENOUS_CAPACITANCE_SEPSIS_MULTIPLIER, honestamente NO-cita) **+ 1 pendiente estructural** (`C=0.807`, no validable aún) **+ 1 simplificación aceptada sin magnitud propia** (`R_poiseuille=0.0`). De 7 banderas activas tras Ronda 1, quedan **6**: 5 en `False` (completamente validadas) y 1 en `True` cubriendo un único parámetro (`C`). La bandera huérfana de retorno venoso permanece retirada del flujo activo, sin cambios.

### Verificación de proyecto

- 26 tests nuevos (`tests/test_hemodynamics_validation_round2.py`): naturaleza correcta de cada dictamen (cita directa vs. forma validada vs. umbral heurístico, verificado por texto en el propio código, no solo aquí), las cinco banderas en `False`, la sexta reducida a solo C, la bandera huérfana sin tocar, y cada función (`run_baroreflex`, `run_pathological_baroreflex`, `stroke_volume_frank_starling`, `apply_diastasis_ceiling`, `compute_dynamic_stroke_volume_with_diastasis_ceiling`, `run_closed_loop`) operando con normalidad tras el retiro de su guard, sin regresión en sano/hipertensión/sepsis.
- Tests preexistentes actualizados (no regresión, solo reflejar el nuevo estado real): `test_hemodynamics_baroreflex.py`, `test_hemodynamics_pathological_tone.py`, `test_hemodynamics_frank_starling.py`, `test_hemodynamics_diastasis_ceiling.py`, `test_hemodynamics_closed_loop.py`, `test_hemodynamics_closed_loop_comparison.py` (aserciones `PENDING_VALIDATION is True` / `pending_validation is True` que ahora son `False`, y los dos tests de monkeypatch-al-guard que probaban un guard ya retirado, reemplazados por tests de "sigue funcionando con normalidad"). `test_hemodynamics_validation_round1.py` ajustado: los tres tests que afirmaban "la bandera sigue arriba" ahora documentan que los NÚMEROS no cambiaron, sin afirmar el estado de bandera (que pertenece a Ronda 2); un test cuya premisa completa quedó obsoleta (`test_no_flag_fully_cleared_this_round...`) fue retirado, su contenido reemplazado por el nuevo archivo de Ronda 2.
- `pytest tests/`: **224/224 passed** (203 previos + 21 netos de esta ronda: +25 tests nuevos en `validation_round2.py`, −4 por fusión de tests obsoletos en `frank_starling.py`/`diastasis_ceiling.py`/`closed_loop.py`/`validation_round1.py`; mismos 3 archivos con error de colección preexistente y no relacionado).
- Servidor real: **HTTP 200**, confirmado.
- Aislamiento sin cambios: ningún archivo tocado en Ronda 2 importa `Session`/UPS nuevo; los cambios fueron exclusivamente docstrings, banderas y retiro de guards ya obsoletos.

**Sin pendientes de Ronda 3 identificados** en el inventario original -- los únicos ítems que quedan sin dictamen son los dos explícitamente aceptados como "no tocar todavía" (`C`, estructural; `R_poiseuille`, simplificación degenerada) y la bandera huérfana ya retirada. El motor hemodinámico de "La película" queda, con esta ronda, mayormente validado: 6 de 7 mecanismos con banderas completamente confirmadas, uno reducido a una única deuda técnica explícita y ya conocida desde antes de esta serie de rondas.

## 2026-07-31 — Validación cuantitativa — Ronda 1: corrección de P_sf + banderas confirmadas

**Firma del validador**: el validador experto del usuario dictaminó esta Ronda 1 a partir del inventario completo de parámetros pendientes (entrega anterior, solo lectura). Tres operaciones, en orden, todas verificadas con ejecución real -- ningún número de esta entrada fue inventado.

### Operación A — Corrección de `P_SF_HEALTHY_MMHG` (error fisiológico real, no ajuste fino)

`P_SF_HEALTHY_MMHG` pasó de **10.0 a 7.0 mmHg** -- el validador señaló que 10.0 implicaba un paciente "sano" hipervolémico; el valor citado de Guyton & Hall es 7.0 mmHg (rango 6-8, adulto normovolémico). Verificado antes de tocar el código: 7.0 > `Pd=2.0` (Módulo 1, sin cambios) -- gradiente de retorno positivo, sin conflicto algebraico, no hizo falta tocar `Pd`. `RVR_REFERENCE_MMHG_S_ML` se re-despejó automáticamente (depende de `P_SF_HEALTHY_MMHG` vía `_solve_rvr_reference_mmhg_s_ml()`): de ≈0.05556 a ≈0.03472 mmHg·s/mL, contra el mismo ancla de siempre.

**Verificación crítica del lazo, los tres escenarios:**

| Escenario | HR | Ticks | Antes (P_sf=10, error) | Después (P_sf=7, corregido) |
|---|---|---|---|---|
| healthy (ancla) | 72 bpm | 1 | 113.3/73.3/93.3 | **113.3/73.3/93.3 -- idéntico** |
| hypertension | 85 bpm | 26 | 121.6/83.8/102.7 | **121.6/83.8/102.7 -- idéntico** |
| **sepsis** | 150 bpm | 3 | 52.0/43.0/47.5 | **26.4/22.0/24.2 -- MÁS severo** |

**Hallazgo estructural, verificado algebraicamente, no solo observado:** sano e hipertensión quedaron **exactamente idénticos** tras la corrección -- no por casualidad. `RVR_actual = RVR_referencia·(Rd_base/Rd_actual)`, y `RVR_referencia = (P_sf-Pd)/144`; al calcular `retorno = (P_sf-Pd)/RVR_actual`, el término `(P_sf-Pd)` se **cancela algebraicamente** siempre que `P_sf_efectiva == P_SF_HEALTHY_MMHG` (el caso de todo escenario sin vasoplejía arterial) -- el retorno venoso queda determinado únicamente por `Rd_actual/Rd_base`, independiente del valor exacto de P_sf. Verificado computacionalmente para tres Rd distintos (test `test_venous_return_algebraically_independent_of_p_sf_when_no_vasoplegia`).

Sepsis **no** tiene esa cancelación, porque su P_sf efectiva es `P_SF_HEALTHY_MMHG / 2.0` (Módulo 3, capacitancia venosa duplicada) -- una FRACCIÓN de la basal, no la basal misma. El colapso se hizo **más severo** (PAM 47.5→24.2 mmHg), no menos -- explicado, no misterioso: el gradiente base `(P_sf-Pd)` se achicó de 8.0 a 5.0 mmHg al corregir P_sf; la misma fracción (÷2) de un gradiente más chico deja menos retorno absoluto. El mecanismo (vasoplejía → capacitancia×2 → P_sf efectiva cae → retorno cae → EDV cae → SV colapsa → presión colapsa → barórreflejo satura) es el mismo de antes -- lo que cambió es la magnitud del gradiente base sobre el que ese mecanismo opera, precisamente porque esa magnitud estaba mal.

**Traza tick-a-tick de sepsis (HR=150, P_sf=7 corregido):**

| tick | Rd antes | P_sf ef. | RVR | retorno mL/s | EDV crudo | SV | Rd después | PAM |
|---|---|---|---|---|---|---|---|---|
| 0 | 0.9786 | 3.50 | 0.0347 | 43.20 | 17.3 | **0.0** | 1.2659 | 2.00 |
| 1 | 1.2659 | 3.50 | 0.0268 | 55.88 | 22.4 | 2.3 | 1.4679 | 10.94 |
| 2 | 1.4679 | 3.50 | 0.0231 | 64.80 | 25.9 | 5.6 | 1.4679 | 24.21 |

Convergido en 3 ticks, `clamped_at_max_rd=True` (barórreflejo saturado en su techo, sin lograr compensar). En el tick 0 el EDV crudo (17.3 mL) ya cae por debajo del piso de Frank-Starling (`EDV_FLOOR_ML=20`) -- SV=0.0 exacto, colapso cardiogénico momentáneo antes de la recuperación parcial a 5.6 mL. El colapso se origina en el retorno venoso desde el primer tick, no en un artefacto tardío del controlador -- verificado con test dedicado.

Hipertensión converge en 26 ticks (oscilación amortiguada visible en la traza, `oscillated=False` porque sí converge), sin chocar límites -- sin regresión frente a la tanda anterior.

### Operación B — Cinco parámetros validados con cita, banderas "todo o nada"

El validador confirmó, con cita directa de Guyton, estos cinco:

| Parámetro | Valor | Cita registrada en código |
|---|---|---|
| `BAROREFLEX_MIN_RD` | 0.3× Rd base | Inhibición simpática máxima reduce la RPT a ~⅓ del basal (Cap. 18) |
| `BAROREFLEX_MAX_RD` | 3.0× Rd base | Estimulación simpática máxima eleva la RPT 3-4× el basal (Cap. 18) |
| `EDV_HEALTHY_ML` | 120 mL | EDV normal de reposo, rango 110-130 mL |
| `SV_MAX_ML` | 140 mL | Vaciado sistólico + reserva inotrópica, consistente con la reserva cardíaca |
| `EDV_ANATOMICAL_CEILING_ML` | 180 mL | Curva de distensibilidad casi vertical 150-170 mL, respeta el pericardio |

Cada uno registrado en su propio docstring como `*** VALIDADO -- confirmado por el validador experto 2026-07-30 (Ronda 1, Operación B) ***`, con la cita completa -- no solo aquí.

**Ninguna bandera bajó entera** -- cada una tiene al menos un parámetro hermano sin dictaminar:

| Bandera | Validados esta ronda | Siguen pendientes |
|---|---|---|
| `BAROREFLEX_PARAMETERS_PENDING_VALIDATION` | MIN_RD, MAX_RD | `k` (ganancia), `target_map` |
| `FRANK_STARLING_PARAMETERS_PENDING_VALIDATION` | EDV_HEALTHY_ML, SV_MAX_ML | `EDV_FLOOR_ML`, `FRANK_STARLING_STEEPNESS_ML` (depende algebraicamente del piso, tampoco confirmado) |
| `DIASTASIS_CEILING_PENDING_VALIDATION` | EDV_ANATOMICAL_CEILING_ML | `DIASTASIS_TRANSITION_BUDGET_ML` (criterio de forma de curva, no dictaminado) |

`PHYSIOLOGICAL_PARAMETERS_PENDING_VALIDATION`, `PATHOLOGICAL_TONE_PENDING_VALIDATION` y `VENOUS_RETURN_PARAMETERS_PENDING_VALIDATION` no fueron objeto de esta ronda -- quedan en `True` sin cambios (salvo la corrección de P_sf dentro de la última, Operación A).

### Operación C — Bandera huérfana retirada del flujo activo, sin código muerto

`VENOUS_RETURN_PLACEHOLDER_PENDING_MODULE_4B` (`frank_starling.py`) queda **retirada del flujo de validación cuantitativa activo** -- confirmada superseded por el retorno venoso real de `closed_loop.py` (verificado por grep: `closed_loop.py` no importa ni llama a `estimate_edv_venous_return_placeholder_pending_module_4b`). La bandera **sigue en `True`** (no se apaga silenciosamente -- seguiría siendo una simplificación no-fisiológica si algo la llamara) pero su docstring y el de las funciones que dependen de ella (`estimate_edv_venous_return_placeholder_pending_module_4b`, `compute_dynamic_stroke_volume` en su modo por defecto, `stroke_volume_table`) quedan marcados explícitamente como **DEMO STANDALONE NO PRODUCTIVA** del eslabón 1 aislado -- siguen existiendo y siguen probadas (sus 27 tests originales intactos), pero documentadas como no representativas del sistema conectado.

### Casos que NO se tocaron (confirmados como tal por el validador)

- **`C=0.807 mL/mmHg`** (Módulo 1, `physiological_flow.py`): confirmado explícitamente como **pendiente ESTRUCTURAL** -- no cambiar hasta modelar la curva de eyección ventricular pulsátil real. Comentario actualizado en el código: "revisado y confirmado como no validable con el modelo de flujo actual", distinto de "todavía sin revisar".
- **Forma de la curva de Frank-Starling** (exponencial saturante): abstracción válida, se queda sin cambios.

### Verificación de proyecto

- 16 tests nuevos (`tests/test_hemodynamics_validation_round1.py` -- corrección de P_sf, independencia algebraica de sano/hipertensión, sensibilidad de sepsis explicada, traza tick-a-tick, los tres pares validado/pendiente por bandera, citas registradas en código, bandera huérfana retirada sin romper la demo standalone) + 2 valores hardcodeados actualizados en `tests/test_hemodynamics_closed_loop.py` (10.0→7.0, 5.0→3.5; el resto de esos 23 tests no necesitó cambios -- eran simbólicos o direccionales).
- `pytest tests/`: **203/203 passed** (187 previos + 16 nuevos; mismos 3 archivos con error de colección preexistente y no relacionado).
- Servidor real: **HTTP 200**.
- `tests/test_hemodynamics_closed_loop_comparison.py` (23→ sin cambios de código, solo re-verificado): sus aserciones eran todas direccionales (`< 65.0`, `> 93.3`, etc.) -- siguen pasando, con márgenes más amplios dado el colapso más severo de sepsis.

**Pendiente para Ronda 2**: `BAROREFLEX_GAIN_K`, `BAROREFLEX_TARGET_MAP_MMHG`, `EDV_FLOOR_ML`, `FRANK_STARLING_STEEPNESS_ML`, `DIASTASIS_TRANSITION_BUDGET_ML`, `VENOUS_CAPACITANCE_SEPSIS_MULTIPLIER`, `RVR_REFERENCE_MMHG_S_ML`, y el conjunto completo de `HYPERTENSION_RESET_TARGET_MAP_MMHG`/`SEPSIS_MAX_RD_MMHG_S_ML`/`SEPSIS_GAIN_K` (Módulo 3) y `Rp`/`Rd`/`Pd`/`R_poiseuille` (Módulo 1, salvo C ya resuelto como estructural). El signo del acoplamiento Rd→RVR (Módulo 4B-ii) tampoco fue objeto de esta ronda.

## 2026-07-30 — "La película", Módulo 4B-ii: retorno venoso real + CIERRE DEL LAZO (el clímax)

**Validado por**: el validador experto del usuario pidió cerrar la cadena completa de una sola vez -- retorno venoso real (capacitancia venosa, P_sf) hasta la presión, con retroalimentación genuina (SV→presión→barórreflejo→resistencia→retorno→EDV→SV) manejada con el mismo "tick virtual" stateless de toda la serie, instrumentada para depuración, y con la salvaguarda anti-circularidad reforzada al máximo dado el riesgo de esta tanda. Magnitudes nuevas quedan **pendientes de confirmación en contexto** -- ninguna bandera bajada.

Aditivo, reutiliza sin duplicar: `run_baroreflex()` (Módulo 2), `run_pathological_baroreflex()` (Módulo 3), `apply_diastasis_ceiling()` (Módulo 4B-i) y `stroke_volume_frank_starling()` (eslabón 1) se llaman tal cual, sin tocar ninguno de esos archivos. `physiological_flow.py` tampoco se toca. No persiste nada en el UPS. `VENOUS_RETURN_PLACEHOLDER_PENDING_MODULE_4B` queda reemplazado en la práctica por el mecanismo real de este módulo, pero su código y bandera siguen intactos en `frank_starling.py` (no se borró nada).

**Paso 1 -- retorno venoso real, mecanismo citado** (Guyton Cap. 20: el gasto cardíaco lo gobierna el retorno venoso, VR=(P_sf-P_ra)/RVR; Cap. 24: la capacitancia venosa aumentada en shock distributivo colapsa P_sf): `P_sf` efectiva y una resistencia al retorno (`RVR`) reemplazan al placeholder de inverso-a-HR. Pd (=2.0 mmHg, Módulo 1, sin cambios) hace de proxy de presión venosa central de referencia.

**Magnitudes marcadas `VENOUS_RETURN_PARAMETERS_PENDING_VALIDATION=True`, NO citas**: `P_SF_HEALTHY_MMHG=10.0` (criterio: valor redondo, margen modesto sobre Pd ya citado), `VENOUS_CAPACITANCE_SEPSIS_MULTIPLIER=2.0` (criterio: múltiplo redondo, mismo estilo que el resto de la serie; P_sf_sepsis=10.0/2.0=5.0 mmHg), `RVR_REFERENCE_MMHG_S_ML≈0.0556` (única resuelta algebraicamente, contra el ancla ya citado 72bpm→120mL, NUNCA contra una PA de referencia).

**Conexión estructural con el Módulo 3** (no un `if scenario=="sepsis"` aislado): `_p_sf_effective_mmhg()` lee `PATHOLOGICAL_TONE_OVERRIDES` -- cualquier escenario cuyo override ya reduzca `max_rd` (hoy, solo sepsis) también dilata las venas. Verificado con test dedicado.

**El momento de mayor riesgo -- elección del signo del acoplamiento resistencia→retorno, documentada con total transparencia:** Guyton no da una ecuación que ligue `Rd` con `RVR`. Se probaron las DOS direcciones posibles, con dos criterios independientes de cualquier PA de referencia:
1. `RVR = RVR_ref·(Rd/Rd_base)` (RVR sube con Rd): produjo un **colapso de retroalimentación positiva en TODOS los escenarios, incluida hipertensión** (que no debería entrar en shock) -- un modelo que colapsa cualquier escenario por igual es un artefacto de inestabilidad estructural, no un hallazgo específico de enfermedad. Descartado por esta razón, **no** porque "no diera 85/55".
2. `RVR = RVR_ref·(Rd_base/Rd)` (RVR baja con Rd, la elegida): consistente con la dirección cualitativa citada (venoconstricción simpática ayuda al retorno) y, verificado computacionalmente, produce un equilibrio ESTABLE para sano e hipertensión (sin chocar límites) dejando que sepsis colapse por su propio mecanismo del Módulo 3 (vasoplejía) -- comportamiento específico de escenario, no universal.

La elección se basó en (a) dirección cualitativa citada y (b) estabilidad estructural básica -- verificado ANTES de mirar qué tan cerca quedaba cualquier PA de referencia. La magnitud del acoplamiento (razón Rd/Rd_base) es la misma en ambas direcciones probadas; solo cambió el signo.

**Paso 2 -- cierre del lazo, tick virtual stateless:** cada tick combinado recorre la cadena completa una vez (retorno venoso con el Rd del tick anterior → EDV con techo de diástasis → SV vía Frank-Starling → un paso del controlador proporcional del barórreflejo, `run_pathological_baroreflex(..., max_ticks=1)` → nuevo Rd, que alimenta el retorno venoso del siguiente tick). `CLOSED_LOOP_MAX_TICKS=40` (control numérico, no magnitud fisiológica). No-convergencia manejada honestamente (`converged=False`, último estado, sin excepción) -- verificado forzando `tol=0.0`.

**Paso 3 -- instrumentación:** `ClosedLoopResult.ticks` expone, por tick, `p_sf_effective_mmhg`, `rvr_mmhg_s_ml`, `venous_return_ml_s`, `raw_edv_ml`, `corrected_edv_ml`, `stroke_volume_ml`, `rd_before/rd_after`, `systolic/diastolic/map`. `oscillated` (heurística de cambios de signo en los últimos ticks, documentada como tal, no un análisis espectral riguroso) distingue oscilación real de deriva monótona sin converger.

**PA final con el lazo cerrado, los tres escenarios (heart_rate de `run_rich_scenario` real), junto a sus referencias:**

| Escenario | HR | Ticks | S/D/PAM lazo cerrado | S/D/PAM referencia | clamped_max_rd |
|---|---|---|---|---|---|
| healthy | 75 bpm | 14 | 112.8 / 73.9 / 93.3 | 120.0 / 80.0 / 93.3 (ACC/AHA 2017) | False |
| hypertension | 85 bpm | 26 | 121.6 / 83.8 / **102.7** | 130.0 / 80.0 / 96.7 (ACC/AHA 2017) | False |
| **sepsis** | 150 bpm | 3 | **52.0 / 43.0 / 47.5** | 85.0 / 55.0 / 65.0 (Sepsis-3) | **True** |

En el ancla exacta (72 bpm, sin pasar por `run_rich_scenario`) el lazo converge en **1 solo tick** y reproduce 113.3/73.3/93.3 -- SV=70.0 mL, EDV=120.0 mL, exactamente lo ya validado en módulos anteriores (así se calibró `RVR_REFERENCE_MMHG_S_ML`).

**La pregunta central, respondida -- sin retocar nada después de ver el resultado:**
- **Sepsis se desploma hacia el shock ORGÁNICAMENTE**, por primera vez en toda la serie en la DIRECCIÓN clínica correcta (hipotensión, no la hipertensión artefactual de módulos anteriores con el lazo abierto): PAM=47.5 mmHg, por debajo incluso del umbral de shock de Sepsis-3 (65 mmHg) -- un colapso más severo que la referencia, no ajustado para acercarse a ella. Cadena verificada en la traza: vasoplejía (Módulo 3, `max_rd`/`k` reducidos, ya fijados) → P_sf cae a 5.0 mmHg → retorno venoso cae → EDV cae (21.6→32.4 mL en 3 ticks) → SV colapsa (70→11.5 mL) → presión colapsa → el barórreflejo choca su techo de resistencia (`clamped_max_rd=True`) intentando compensar, sin lograrlo -- reflejo saturado, hallazgo fisiológico honesto, no un error.
- **Hipertensión NO colapsa**: converge en 26 ticks (con una oscilación amortiguada visible en la traza, sin activar la bandera `oscillated` porque sí converge) a un equilibrio elevado y estable (PAM=102.7, sin chocar ningún límite). Sistólica/diastólica quedan un poco más lejos de la referencia que en el Módulo 3 sin el lazo cerrado (SV bajó de 70 a 62.9 mL por el propio retorno venoso, un efecto secundario legítimo del cierre, no forzado) -- divergencia reportada tal cual, sin ajustar.
- **Sano** queda prácticamente igual que siempre (PAM idéntica a la referencia).

**Verificación de proyecto:**
- 23 tests nuevos (`tests/test_hemodynamics_closed_loop.py`, 19; `tests/test_hemodynamics_closed_loop_comparison.py`, 4): mecanismo citado, parámetros marcados pendientes, anti-circularidad máxima (ninguna constante nueva coincide con PA de referencia, RVR_REFERENCE resuelto reproduciblemente contra el ancla, P_sf de sepsis verificada como fórmula directa no un número aparte, conexión estructural con el Módulo 3 confirmada), dirección del acoplamiento Rd→RVR verificada, ancla de reposo reproducida en un solo tick, instrumentación completa de la traza, detector de oscilación probado con datos sintéticos alternantes y monótonos, no-convergencia honesta forzada, el hallazgo central (sepsis colapsa/hipertensión no) verificado tanto con heart_rate fijo como end-to-end vía `run_rich_scenario`, aislamiento sin `Session`/UPS, y stateless entre llamadas.
- `pytest tests/`: **187/187 passed** (164 previos + 23 nuevos, confirmado; mismos 3 archivos con error de colección preexistente y no relacionado -- `test_api.py`, `test_arrhythmia_classifier.py`, `test_reasoning_engine.py`).
- Servidor real: **HTTP 200**, confirmado.
- Aislamiento verificado por grep: `coupling/`, `narrator/*` y `domain/physiology/state/*` no importan `closed_loop.py` ni `closed_loop_comparison.py`; el primero no importa `Session`/`sqlalchemy`.

**Pendiente**: confirmación del validador experto, en contexto, sobre (a) los criterios P_sf=10.0/multiplicador=2.0/RVR-resuelto de esta tanda, (b) el signo elegido del acoplamiento Rd→RVR (documentado con la alternativa descartada y por qué), y (c) si la magnitud del colapso de sepsis (47.5 mmHg, más severo que el umbral de shock de la propia referencia) amerita ajustar algún criterio en una tanda futura -- explícitamente NO se tocó nada en esta tanda para acercar el resultado a 65 mmHg.

## 2026-07-27 — "La película", Módulo 4B-i: techo diastólico (diástasis)

**Validado por**: el validador experto del usuario identificó que el `VENOUS_RETURN_PLACEHOLDER` del eslabón 1 (Módulo 4, `frank_starling.py`) infla el EDV irrealmente a frecuencias bajas -- 216 mL a 40 bpm -- porque asume que más tiempo de llenado = más EDV, sin límite. En la realidad, el pericardio y la rigidez miocárdica ponen un techo físico (fase de diástasis: el llenado se detiene aunque haya más tiempo). Este submódulo (4B-i, primero del Módulo 4B) corrige ese artefacto visible y deja el EDV anatómicamente sensato **antes** de reemplazar el retorno venoso simplificado (4B-ii, todavía no hecho). Magnitud del techo queda **pendiente de confirmación en contexto** -- ninguna bandera bajada.

Aditivo y aislado: `frank_starling.py` **no se modifica** -- `diastasis_ceiling.py` (nuevo) envuelve `estimate_edv_venous_return_placeholder_pending_module_4b()` con una corrección adicional, sin tocarla (mismo patrón que `pathological_tone.py` envolviendo `run_baroreflex()` sin tocar `baroreflex.py`). `VENOUS_RETURN_PLACEHOLDER_PENDING_MODULE_4B` sigue en `True`, sin reemplazar -- ese reemplazo es 4B-ii. No toca `coupling/`, `narrator/*` ni el UPS.

**Mecanismo citado** (Guyton & Hall -- curva de distensibilidad/compliancia ventricular y fase de diástasis del llenado): tras el llenado rápido inicial, la curva presión-volumen del ventrículo se empina y el llenado se aplana en una meseta -- más tiempo de diástole ya no se traduce en más EDV proporcional. Implementado como `apply_diastasis_ceiling()`: identidad para EDV crudo ≤120 mL (el ancla), curva saturante hacia el techo por encima.

**Magnitud marcada `DIASTASIS_CEILING_PENDING_VALIDATION=True`, NO cita** (Guyton describe la meseta, no una cifra exacta): `EDV_ANATOMICAL_CEILING_ML=180` -- criterio: múltiplo redondo (1.5x) del ancla ya usada (120 mL), consistente con que la literatura general cita EDV normal ~120-150 mL con límites de distensibilidad por encima (contexto del validador, no cita verbatim). `DIASTASIS_TRANSITION_BUDGET_ML=60` -- criterio: igual al presupuesto de distensión restante (techo−ancla), deliberadamente sin introducir una constante libre adicional.

**Salvaguarda anti-circularidad:** ambas constantes son límites anatómicos en mL, fijados sin mirar ninguna `ClinicalReferenceValue` de PA (mmHg) -- verificado con test dedicado que ninguna coincide con cifra de referencia clínica alguna.

**Tabla EDV/SV corregida, todo el rango:**

| HR (bpm) | EDV crudo (artefacto) | EDV corregido (techo) | SV (mL) | techo activo |
|---|---|---|---|---|
| 40 | 216.0 | **167.9** | 89.8 | True |
| 72 (ancla) | 120.0 | 120.0 (intacto) | 70.0 (intacto) | False |
| 85 | 101.6 | 101.6 | 60.5 | False |
| 150 (sepsis) | 57.6 | 57.6 | 32.1 (sin cambio, aún dentro del rango del validador) | False |
| 220 | 39.3 | 39.3 | 17.5 | False |

**Confirmado, ambos puntos pedidos:**
1. **Extremo bradicárdico corregido**: EDV a 40 bpm pasa de 216.0 mL (artefacto) a 167.9 mL -- por debajo del techo anatómico (180 mL), fisiológicamente plausible. SV correspondiente cae de 104.0 a 89.8 mL, pero sigue por encima del reposo (70 mL) -- la reserva de Frank-Starling en bradicardia se mantiene cualitativamente, solo menos exagerada.
2. **Ancla de reposo intacta**: 72 bpm → EDV=120.0 mL → SV=70.0 mL, sin ningún cambio -- el techo es identidad exacta en y por debajo del ancla, verificado bit a bit contra el resultado del eslabón 1 sin envolver.

El resto del rango (85/150/220 bpm) queda sin cambios -- el techo solo actúa por debajo de 72 bpm, donde el placeholder crudo excede 120 mL.

**Verificación de proyecto:**
- 16 tests nuevos (`tests/test_hemodynamics_diastasis_ceiling.py`): mecanismo citado vs. techo marcado pendiente, bandera del placeholder sin tocar, anti-circularidad (constantes no derivadas de PA), identidad por debajo del ancla, ancla de reposo verificada bit a bit contra el eslabón 1 sin envolver, corrección del artefacto de bradicardia con valores exactos, saturación en bradicardia extrema sin exceder el techo, monotonía de la curva del techo, tabla completa coincide con el placeholder crudo para HR≥72, SV sigue cayendo monótonamente con HR tras la corrección, `frank_starling.py` confirmado sin modificar (sus funciones originales siguen dando el EDV crudo sin techo), y el piso de taquicardia extrema del eslabón 1 sigue alcanzable a través de este envoltorio.
- `pytest tests/`: 164/164 passed (148 previos + 16 nuevos; mismos 3 archivos con error de colección preexistente y no relacionado).
- Servidor real: HTTP 200.
- Aislamiento verificado por grep: `coupling/`, `narrator/*` y `domain/physiology/state/*` no importan `diastasis_ceiling.py`; solo `hemodynamics/__init__.py` y el test nuevo lo importan; `frank_starling.py` no importa `Session`/`sqlalchemy` (sin cambios respecto a la tanda anterior).

**Pendiente**: confirmación del validador experto, en contexto, sobre el criterio 1.5x/presupuesto-restante de esta tanda, y el Módulo 4B-ii -- reemplazo real del retorno venoso simplificado (capacitancia venosa, P_sf), que es cuando el lazo con el R-RCR podrá empezar a cerrarse.

## 2026-07-24 — "La película", Módulo 4, eslabón 1: volumen sistólico dinámico vía Frank-Starling

**Validado por**: el validador experto del usuario confirmó que el eslabón perdido de esta serie es el SV dinámico, y que el mecanismo que lo hace dinámico es la ley de Frank-Starling (Guyton Cap. 20 y 24). Se entró por la pieza MÍNIMA -- SV=f(EDV) -- con el retorno venoso todavía simplificado, para validar este eslabón **aislado** antes de cerrar el lazo completo (retorno venoso real con capacitancia venosa/P_sf, Módulo 4B). Magnitudes de esta tanda quedan **pendientes de confirmación en contexto**, mismo criterio que Módulos 2 y 3 -- ninguna bandera bajada.

Aditivo y aislado: `physiological_flow.py` (SV_ref=70mL fijo del R-RCR) **no se toca** -- este eslabón no cierra el lazo con el flujo de entrada del R-RCR todavía, tal como fue instruido explícitamente. No toca `coupling/`, `narrator/*` ni el UPS (sin sesión de base de datos, sin `sqlalchemy` -- este módulo es, por construcción, el más aislado de la serie: funciones puras sobre `float`).

**Paso 1 -- Frank-Starling como mecanismo, con fuente:**
- **Mecanismo citado** (Guyton & Hall, Cap. 9 "El corazón como bomba" y Cap. 20/24 "Regulación del gasto cardíaco / retorno venoso"): el corazón bombea toda la sangre que recibe sin acumulación venosa excesiva; el SV crece con el llenado diastólico (EDV, precarga) hasta un techo fisiológico. Implementado como curva saturante `stroke_volume_frank_starling(edv_ml)`: `SV = SV_MAX·(1-exp(-(EDV-piso)/k))`.
- **Magnitudes marcadas `FRANK_STARLING_PARAMETERS_PENDING_VALIDATION=True`, NO citas** (Guyton no da la ecuación exacta ni sus constantes): `EDV_HEALTHY_ML=120` (orden de magnitud Guyton, mismo estilo que `STROKE_VOLUME_REFERENCE_ML=70` ya citado), `EDV_FLOOR_ML=20` (redondo, muy por debajo de cualquier volumen fisiológico típico), `SV_MAX_ML=140` (2.0x el SV de reposo ya citado -- mismo estilo de múltiplos redondos que Módulo 2/3), `FRANK_STARLING_STEEPNESS_ML≈144.27` (resuelto algebraicamente, no estimado a ojo -- ver criterio de ancla abajo).

**Salvaguarda anti-circularidad (reforzada):** `FRANK_STARLING_STEEPNESS_ML` se resuelve para que la curva pase EXACTO por el ancla (`EDV_HEALTHY_ML=120`, `STROKE_VOLUME_REFERENCE_ML=70`) -- el mismo ancla "sano" (72 bpm) ya citado en Módulos 1/2, no una cifra de PA. Ninguna constante de esta curva se fijó mirando una `ClinicalReferenceValue`. Test dedicado (`test_curve_constants_do_not_coincide_with_any_blood_pressure_reference_value`, `test_steepness_constant_is_solved_from_the_cited_anchor_not_from_any_bp_reference`) lo verifica.

**Paso 2 -- retorno venoso simplificado, DECLARADO como andamiaje temporal:**
- `estimate_edv_venous_return_placeholder_pending_module_4b(heart_rate_bpm)`: EDV inversamente proporcional al heart_rate respecto al ancla sano (72bpm→120mL) -- aproxima que el llenado diastólico se acorta con la taquicardia (dirección cualitativa correcta de Guyton), pero la proporcionalidad exacta es una simplificación de esta tanda, NO retorno venoso real (eso requiere capacitancia venosa/P_sf, Módulo 4B).
- **Nombre y bandera deliberadamente inequívocos** (`VENOUS_RETURN_PLACEHOLDER_PENDING_MODULE_4B=True`, función con `placeholder`/`pending_module_4b` en el propio nombre, docstring con "ANDAMIAJE TEMPORAL -- NO es fisiología final") -- imposible de confundir con un dato fisiológico definitivo, para no repetir el error histórico de `stroke_volume` fijo en `CardiacDetail` (una simplificación disfrazada de dato real).

**Paso 3 -- efecto verificable:**

| HR (bpm) | EDV (mL, placeholder 4B) | SV (mL, Frank-Starling) | clamped_at_edv_floor |
|---|---|---|---|
| 40 | 216.0 | 104.0 | False |
| 72 (ancla) | 120.0 | 70.0 (exacto, reproduce el ancla ya citado) | False |
| 85 | 101.6 | 60.5 | False |
| **150 (sepsis)** | **57.6** | **32.1** | False |
| 220 | 39.3 | 17.5 | False |

El SV cae monótonamente al subir la frecuencia (llenado reducido vía el andamiaje del Paso 2) y sube en bradicardia -- efecto cualitativo que el validador predijo. A HR=150, SV calculado=**32.1 mL**, dentro del rango 30-40 mL que el validador estimó cualitativamente para sepsis -- **observado después de fijar las constantes con criterio independiente, no el objetivo de su ajuste** (`VALIDATOR_SEPSIS_SV_ESTIMATE_RANGE_ML` es contexto informativo, no una `ClinicalReferenceValue` formal; si el resultado hubiera caído fuera del rango, se habría reportado tal cual). En taquicardia extrema (HR≥500) el EDV se clampa en el piso y SV colapsa a 0 -- comportamiento honesto de "colapso", no un error.

**Qué repara y qué no repara esta tanda:** repara la deuda de que el SV del R-RCR era una constante fija sin importar el escenario -- ahora existe una función real, citada y probada, `SV=f(EDV)`. **No** conecta esta función al flujo de entrada del R-RCR (`physiological_pulsatile_flow`, `physiological_flow.py`) en reemplazo de `STROKE_VOLUME_REFERENCE_ML` -- cerrar ese lazo es el siguiente eslabón, diferido hasta que el retorno venoso real (no este andamiaje) esté disponible, tal como fue instruido explícitamente ("NO cierres el lazo completo").

**Verificación de proyecto:**
- 27 tests nuevos (`tests/test_hemodynamics_frank_starling.py`): mecanismo citado vs. constantes marcadas pendientes, anti-circularidad (constantes no derivadas de ninguna PA de referencia, ancla resuelto algebraicamente), andamiaje de retorno venoso declarado e inequívoco (nombre de función, docstring, bandera), monotonía y techo de la curva sin excederlo, reproducción exacta del ancla citado, SV cae a HR alta / sube a HR baja, resultado de sepsis dentro del rango cualitativo del validador (sin haberlo forzado), clamping honesto en taquicardia extrema, función pura sin interferencia entre llamadas, y ausencia de dependencia de `Session`/UPS.
- `pytest tests/`: 148/148 passed (121 previos + 27 nuevos; mismos 3 archivos con error de colección preexistente y no relacionado -- `test_api.py`, `test_arrhythmia_classifier.py`, `test_reasoning_engine.py`).
- Servidor real: HTTP 200.
- Aislamiento verificado por grep: `coupling/`, `narrator/*` y `domain/physiology/state/*` no importan `frank_starling.py`; solo `hemodynamics/__init__.py` y el test nuevo lo importan; el módulo no importa `sqlalchemy`/`Session`/`app.engines`.

**Pendiente**: confirmación del validador experto, en contexto, sobre (a) el criterio 120mL/20mL/2.0x/ancla-resuelto de esta tanda, y (b) cuándo conectar este SV dinámico al R-RCR -- requiere primero el Módulo 4B (retorno venoso real con capacitancia venosa/P_sf), reemplazando el andamiaje temporal de este eslabón, no solo enchufando el resultado actual.

## 2026-07-23 — "La película", Módulo 3: tono vascular alterable por patología

**Validado por**: el validador experto del usuario confirmó los tres puntos de esta tanda antes de la construcción: (1) hipertensión y sepsis alteran el barórreflejo del Módulo 2 por **dos mecanismos distintos, cada uno con su propia fuente** -- no un "ajuste" genérico; (2) sepsis **no** debe tocar `target_map` (el cuerpo sigue queriendo normalizar la PAM, el fallo es del efector); (3) la salvaguarda anti-circularidad del Módulo 2 se **refuerza**: el techo de resistencia de sepsis y el punto de ajuste de hipertensión se fijan con un criterio independiente de las cifras de referencia clínica, documentado junto a cada constante, y comparado después como control de calidad, no como objetivo de ajuste. Las magnitudes cuantitativas de esta tanda quedan **pendientes de confirmación en contexto**, mismo criterio que el Módulo 2 -- no se bajó ninguna bandera de validación.

Aditivo y aislado: `baroreflex.py` (Módulo 2) no se modifica -- `pathological_tone.py` (nuevo) solo decide qué parámetros pasarle a `run_baroreflex()` por escenario. No toca `coupling/`, `narrator/*` ni persiste nada en el UPS (verificado por grep y por test dedicado, igual que el Módulo 2).

**Los dos mecanismos:**

1. **Hipertensión → reseteo del barostato** (falla en el PUNTO DE AJUSTE): los barorreceptores se readaptan a un nivel de presión sostenido en 1-2 días y pierden la capacidad de normalizarlo -- Guyton & Hall, Cap. 18 ("Regulación nerviosa de la circulación... reflejos barorreceptores"). Solo `target_map` sube; el efector (`k`, `min_rd`, `max_rd`) queda intacto -- el barórreflejo sigue funcionando normal, solo defiende un objetivo más alto.
2. **Sepsis → vasoplejía** (falla en el EFECTOR): shock distributivo con refractariedad de la musculatura lisa vascular a las catecolaminas endógenas -- Marino, The ICU Book. `target_map` **no cambia** (sigue en 93.33 mmHg -- el cuerpo quiere normalizar); lo que cae es el techo de resistencia alcanzable (`max_rd`) y la ganancia efectiva (`k`): el reflejo ordena vasoconstricción y el vaso no responde con la fuerza normal. `min_rd` (techo de vasodilatación) no se toca -- vasoplejía es incapacidad de constreñir, no una tendencia a dilatar más.

**Criterio de cada magnitud (fijado ANTES de mirar la referencia clínica del escenario, nunca a partir de ella):**
- `HYPERTENSION_RESET_TARGET_MAP_MMHG = 93.33 × 1.10 ≈ 102.67 mmHg` -- +10% redondo sobre el ancla fija del Módulo 2, mismo estilo de estimación "redonda, no ajustada" que ya usa ese módulo (`k=1.0`, `min_rd/max_rd=0.3x/3.0x`). Guyton cita el mecanismo y la escala temporal (1-2 días), no una magnitud del nuevo punto de ajuste -- ese número no está en la fuente.
- `SEPSIS_MAX_RD = BAROREFLEX_MAX_RD × 0.5` -- mitad redonda del techo normal de vasoconstricción (refractariedad PARCIAL, no vasoplejía total/1.0x).
- `SEPSIS_GAIN_K = BAROREFLEX_GAIN_K × 0.3` -- 30% redondo de la ganancia normal (la orden simpática sigue llegando, el efector la ejecuta con mucha menos fuerza -- consistente con "refractariedad", no con "ausencia total de respuesta", que sería k=0).

Test dedicado (`test_hypertension_reset_target_map_is_not_derived_from_clinical_reference`, `test_sepsis_max_rd_and_gain_are_not_derived_from_clinical_reference`) verifica que ninguna de las tres constantes coincide con la cifra de referencia clínica del escenario, y que `target_map` (recorriendo los 12 escenarios) solo varía en hipertensión -- nunca por conveniencia.

**PA recalculadas -- resultado real, no ajustado, control de calidad independiente:**

| Escenario | HR | Módulo 2 -- sin patología (S/D/PAM) | Módulo 3 -- con patología (S/D/PAM) | Referencia (S/D/PAM) |
|---|---|---|---|---|
| hypertension | 85 bpm | 114.6 / 72.1 / 93.3 | 123.8 / 81.5 / 102.7 | 130.0 / 80.0 / 96.7 (ACC/AHA 2017) |
| sepsis | 150 bpm | 122.1 / 64.5 / 93.3 | 122.2 / 64.6 / 93.4 | 85.0 / 55.0 / 65.0 (Sepsis-3) |

Dos hallazgos honestos, ninguno maquillado:

1. **Hipertensión: sistólica y diastólica se acercan mucho a la referencia; la PAM se aleja.** Sistólica pasa de 15.4 mmHg de error a 6.2 (mejora); diastólica de 7.9 a 1.5 (mejora notable, prácticamente exacta); pero la PAM, que ya estaba a 3.4 mmHg de la referencia (96.7), pasa a 6.0 (empeora) -- el reseteo de +10% (102.67) sobrepasa la referencia real (96.67). Consistente con el criterio elegido siendo una estimación redonda, no calibrada a esta cifra: la dirección del mecanismo (reseteo hacia arriba) es correcta y mejora dos de las tres métricas, pero la magnitud exacta (+10%) queda como candidata a ajuste fino en una futura validación cuantitativa -- no se retocó para forzar que la PAM también cerrara.
2. **Sepsis prácticamente no cambia (93.3→93.4 mmHg) -- hallazgo arquitectónico, no un bug.** Con HR=150 (taquicardia), el barórreflejo necesita **vasodilatar** (bajar Rd) para defender el target_map fijo, no vasoconstreñir -- confirmado con `clamped_at_max=False`: el techo reducido (`max_rd`) nunca se activa, porque Rd se está moviendo hacia abajo, no hacia el techo. Reducir la ganancia (`k=0.3`) tampoco mueve el punto fijo de convergencia, solo la velocidad de convergencia -- y el bucle sigue convergiendo. **La vasoplejía tal como está modelada aquí (techo de vasoconstricción reducido) es fisiológicamente correcta como mecanismo, pero no es la restricción activa en el régimen de taquicardia de este escenario** -- el shock séptico real combina taquicardia CON vasodilatación patológica activa (el vaso dilata de más, no solo "no puede constreñir"), y ese segundo componente (un sesgo activo hacia la vasodilatación, no solo un techo más bajo) no está en el mecanismo pedido para esta tanda. Documentado como límite conocido de esta tanda, no resuelto aquí -- ver test `test_sepsis_dynamic_still_does_not_match_clinical_reference_by_construction`.

**Deuda técnica anotada (no resuelta en esta tanda):** la compliancia `C=0.807 mL/mmHg` (Paso 1 del Módulo 2, `physiological_flow.py`) está compensando la simplificación de la curva de flujo de entrada (`physiological_pulsatile_flow`, una sinusoide reescalada, no una eyección ventricular real). Su valor fisiológico real depende de modelar una curva de flujo de eyección ventricular realista (candidato a módulo futuro) -- hasta entonces, `C=0.807` es una calibración acoplada a esa simplificación, no una constante fisiológica independiente.

**Verificación de proyecto:**
- 20 tests nuevos (`tests/test_hemodynamics_pathological_tone.py`): mecanismos citados y distintos (Guyton vs. Marino), magnitudes marcadas pendientes, anti-circularidad reforzada (ninguna constante coincide con la referencia clínica; `target_map` fijo salvo hipertensión, verificado en los 12 escenarios), estructura del override (hipertensión solo toca `target_map`; sepsis solo toca `max_rd`/`k`, nunca `target_map` ni `min_rd`), pass-through exacto a `run_baroreflex()` para escenarios sin mecanismo (10 escenarios verificados), prioridad de kwargs explícitos sobre el override, hallazgo de sepsis documentado como no-cierre esperado (con `clamped_at_max=False` confirmando que el techo reducido no es la restricción activa), comparación end-to-end con y sin referencia, y no-escritura de descriptores nuevos en el UPS.
- `pytest tests/`: 121/121 passed (101 previos + 20 nuevos; mismos 3 archivos con error de colección preexistente -- `test_api.py` (falta `fastapi`), `test_arrhythmia_classifier.py` (`BeatSegmentation`), `test_reasoning_engine.py` (`HRVMetrics`) -- excluidos igual que siempre, no relacionados con esta tanda).
- Servidor real: HTTP 200.
- Aislamiento verificado por grep: `coupling/`, `narrator/*` y `domain/physiology/state/*` no importan `pathological_tone.py` ni `pathological_tone_comparison.py`; solo `hemodynamics/__init__.py` y el test nuevo los importan.

**Pendiente**: confirmación del validador experto, en contexto, sobre (a) el criterio +10%/0.5x/0.3x de esta tanda, y (b) qué hacer con el hallazgo de sepsis -- el mecanismo de vasoplejía pedido (techo de resistencia reducido) es fisiológicamente correcto pero no es suficiente por sí solo para reproducir el shock a HR=150; representar la vasodilatación activa patológica de la sepsis probablemente requiere un mecanismo adicional (no solo un techo más bajo), fuera del alcance de esta tanda.

## 2026-07-20 — "La película", Módulo 2: resistencia vascular dinámica (barórreflejo)

**Validado por**: el validador experto del usuario confirmó el enfoque del módulo 2 (controlador proporcional sobre resistencia distal, mecanismo del barórreflejo) antes de esta construcción; la calibración cuantitativa de esta tanda (Rd/C recalibrados, k/min_r/max_r/target_map del barórreflejo) queda explícitamente **pendiente de su confirmación en contexto** — no se bajó ninguna bandera de validación en esta tanda.

Aislado: no conecta a más escenarios que los ya usados para comparación (`run_rich_scenario()` sin cambios), no persiste nada nuevo en el UPS, no toca `coupling/` ni `narrator/*`. Coexistencia intacta: la PA de resistencia fija del módulo 1 y la `ClinicalReferenceValue` siguen exactamente como estaban.

**Paso 1 — recalibración de la R base del módulo 1 (cimiento, antes de tocar el barórreflejo):**
- El validador señaló sano/hipertensión ~15-20 mmHg bajos con la calibración anterior (Rd=0.90, Rp=0.10, C=2.0).
- Recalibrado usando dos criterios distintos para dos cantidades distintas, ambos documentados en `physiological_flow.py`:
  1. **PAM** (independiente de C/forma del pulso en régimen periódico — identidad exacta del Windkessel, no una estimación): `RPT_total = (PAM_objetivo − Pd) / CO_medio`, resuelta para el caso ancla "sano" (72 bpm, PAM_objetivo=93.33=`estimate_map(120,80)`) → RPT_total≈1.0873 mmHg·s/mL (Rd≈0.9786, Rp≈0.1087, misma división 90/10 ya documentada).
  2. **Presión de pulso** (sí depende de C): bisección numérica para ~40 mmHg de presión de pulso → C≈0.807 mL/mmHg (antes: 2.0 — revisión sustancial, sin disimular).
- Resultado para "sano": 113.3/73.3/93.3 mmHg (antes: 97.9/74.3/86.1) — PAM y presión de pulso exactas; sistólica/diastólica individuales no caen en 120/80 exactos porque la curva integrada no es perfectamente simétrica alrededor de la media (la regla PAM≈DBP+⅓·PP es una aproximación). **Sigue marcado `PHYSIOLOGICAL_PARAMETERS_PENDING_VALIDATION=True`** — esta recalibración no se autovalida.

**Paso 2 — `domain/physiology/hemodynamics/baroreflex.py` (nuevo), el barórreflejo:**
- **Mecanismo citado** (Guyton & Hall, Cap. 18 — reflejos barorreceptores): retroalimentación negativa que ajusta el tono arteriolar para defender la PAM. Implementado como controlador proporcional que modula **solo Rd** (resistencia distal/arteriolar — decisión de modelado explícita, no cita: Rp/C/Pd del módulo 1 quedan intactos): `Rd_nueva = Rd_base·(1 + k·ΔPAM/PAM_objetivo)`, `ΔPAM = PAM_objetivo − PAM_actual` (signo verificado por comportamiento: hipertensión → Rd baja/vasodilata; bradicardia marcada → Rd sube/vasoconstriñe), recortado a `[min_rd, max_rd]`.
- **Magnitudes marcadas `BAROREFLEX_PARAMETERS_PENDING_VALIDATION=True`, NO citas**: `k=1.0` (ganancia unitaria redonda, deliberadamente no ajustada a ninguna referencia; nota de estabilidad de control -- converge para k≲2 dado el sistema calibrado), `min_rd`/`max_rd` = 0.3×/3.0× la Rd base calibrada, `target_map`=93.33 mmHg.
- **Salvaguarda anti-circularidad**: `target_map` es **un único valor fijo para todos los escenarios** (el mismo ancla "sano" del Paso 1) — nunca uno distinto por escenario. El barórreflejo siempre defiende el mismo punto de ajuste homeostático; lo único que cambia entre escenarios es `heart_rate` (entrada real del UPS). La `ClinicalReferenceValue` de cada escenario es el control de calidad independiente de esta corrida, no el objetivo de ajuste de `k`/`min_rd`/`max_rd`/`target_map` — verificado con un test dedicado (`test_target_map_is_a_single_fixed_value_not_scenario_specific`).

**Paso 3 — "tick virtual", aislamiento stateless preservado:**
- `run_baroreflex()` es una función pura: todo el bucle de convergencia (Rd, ticks) vive en variables locales de la llamada — sin estado de módulo ni de sesión compartido entre peticiones (verificado con `test_two_calls_do_not_share_state`).
- `MAX_TICKS=40`, tolerancia relativa `1e-4` sobre Rd. No-convergencia manejada honestamente: `converged=False` con el último estado alcanzado, sin excepción ni ocultamiento — verificado forzando una ganancia patológica (`k=10`) que hace oscilar la iteración.
- Clamping en los límites fisiológicos verificado con taquicardia extrema (HR=220 → clampa en `min_rd`, compensación parcial, PAM residual por encima del objetivo — comportamiento honesto de "reflejo saturado").

**Paso 4 — verificación en contexto, resultados reales (no ajustados para que "se vieran bien"):**

| Escenario | HR | R fija (S/D/PAM) | R dinámica -- barórreflejo (S/D/PAM) | Referencia (S/D/PAM) |
|---|---|---|---|---|
| healthy | 71 bpm | 111.5 / 71.7 / 91.6 | 113.2 / 73.5 / 93.3 | 120 / 80 / 93.3 |
| hypertension | 85 bpm | 130.9 / 88.7 / 109.8 | 114.6 / 72.1 / 93.3 | 130 / 80 / 96.7 |
| sepsis | 150 bpm | 220.1 / 164.7 / 192.4 | 122.1 / 64.5 / 93.3 | 85 / 55 / 65 |

Tres hallazgos honestos, ninguno maquillado:
1. **Sepsis mejora mucho pero no cierra**: la resistencia dinámica corrige el peor fallo del módulo 1 (de 220/165, absurdo, a 122/65, en el orden de magnitud correcto) pero la PAM converge a 93.3 (el objetivo homeostático fijo), no a 65 (shock). **Causa mecanicista, no un bug**: este modelo solo recibe `heart_rate` como entrada; el shock séptico real es una caída patológica del tono vascular (vasoplejía) que este módulo no tiene forma de representar — el barórreflejo, funcionando "bien" con la única entrada que tiene, normaliza la PAM en vez de mostrar shock. Falta un tercer driver (tono vascular séptico) para reproducir esto, fuera del alcance de esta tanda.
2. **Hipertensión empeora frente a la referencia** (109.8→93.3 de PAM, alejándose de la referencia 96.7): un hallazgo contraintuitivo pero fisiológicamente explicable — la hipertensión crónica real cursa con el barostato "reseteado" a un punto más alto (adaptación de los barorreceptores), no con un barórreflejo que sigue defendiendo 93.3 mmHg. Este modelo no representa ese reseteo -- otra limitación arquitectónica identificada, no resuelta aquí.
3. **Sano mejora ligeramente** y queda muy cerca de la referencia, como es esperable en el caso ancla de la propia calibración.

`domain/physiology/hemodynamics/baroreflex_comparison.py` (nuevo, Paso 4): `run_scenario_baroreflex_comparison(scenario)` — ejecutable directo: `python -m domain.physiology.hemodynamics.baroreflex_comparison <escenario>`. No persiste nada del barórreflejo en el UPS (deliberado, ver Paso 3 del pedido: "aislado, validado en contexto antes de conectar a más escenarios") — solo lee `heart_rate`/`ClinicalReferenceValue` ya escritos por `run_rich_scenario()`.

**Verificación de proyecto:**
- 15 tests nuevos (`tests/test_hemodynamics_baroreflex.py`): mecanismo citado, magnitudes marcadas pendientes, anti-circularidad (target_map fijo, hallazgo de sepsis documentado como no-match esperado), signo de la retroalimentación en ambas direcciones, convergencia típica, clamping en taquicardia extrema, no-convergencia honesta con ganancia patológica, aislamiento stateless entre llamadas, Rp/C/Pd intactos (solo Rd se modula, verificado reconstruyendo la simulación manualmente), comparación end-to-end con y sin referencia, y que la comparación no escribe descriptores nuevos en el UPS.
- `pytest tests/`: 101/101 passed (86 previos + 15 nuevos; mismos 3 archivos con error de colección preexistente, excluidos igual que siempre).
- Servidor real: HTTP 200.
- Aislamiento verificado por grep: `coupling/`, `narrator/*` y `domain/physiology/state/*` (salvo lo ya existente del Paso 2 anterior) no importan `baroreflex.py` ni `baroreflex_comparison.py`.

**Pendiente**: confirmación del validador experto, en contexto, sobre (a) la recalibración Rd/C del Paso 1, (b) las magnitudes k/min_rd/max_rd/target_map del barórreflejo, y (c) qué hacer con los dos hallazgos arquitectónicos de esta tanda (sepsis necesita un driver de tono vascular independiente del barórreflejo; hipertensión necesita un `target_map` que pueda "resetearse" en cuadros crónicos) antes de considerar cualquier conexión al flujo vivo del UPS o a más escenarios.

## 2026-07-19 (2) — "La película", Paso 2: conexión del R-RCR al UPS vivo

Conecta el módulo R-RCR (validado matemáticamente en la entrada anterior) al flujo vivo del UPS, produciendo PA dinámica calculada para un escenario real. Coexiste con la PA estática de referencia clínica (`ClinicalReferenceValue`) — ninguna sobrescribe a la otra. Aditivo: cero cambios en `run_rich_scenario()` más allá de lo ya existente, `builder.py`, `coupling/` ni `narrator/*`.

**Paso 1 — decisión de entrada honesta (mostrada y aprobada por el usuario antes de tocar código):**
- Confirmé de nuevo, leyendo `app/engines/digital_twin_organism.py` líneas 357-384, que `CardiacDetail.cardiac_output`/`stroke_volume` siguen siendo defaults estáticos que `_update_heart()` nunca actualiza — alimentar el R-RCR con esos campos habría heredado un valor fingido como si fuera derivado.
- **Cadencia del flujo**: `period_s = 60/heart_rate` — `heart_rate` es real, dinámico, viene del UPS con `Provenance.SIMULACION`. Sin objeción.
- **Amplitud del flujo**: `SV_ref = 70 mL` (Guyton & Hall, volumen sistólico normal de reposo) — constante **citada**, deliberadamente independiente del campo fingido del organismo (coincide en valor por ser el mismo dato de libro de texto, no porque se haya leído de ahí). `CO_medio(t) = heart_rate(t)/60 × SV_ref`, reescalando la forma pulsátil ya validada (`2.5·sin(2πt)+2.2`, razón amplitud/media ≈1.136) preservando esa proporción — cadencia real + forma validada + escala de una cita.
- **Parámetros R/Rp/Rd/C**: los valores validados matemáticamente en la entrada anterior son del caso de prueba oficial de svZeroDSolver, sin escala fisiológica real (con flujo fisiológico real esos mismos números producen presiones sin sentido). Se propuso un **segundo conjunto, separado**, calibrado a órdenes de magnitud de Guyton (resistencia periférica total ≈1 PRU = 1 mmHg·s/mL; compliancia arterial sistémica total ≈1-2 mL/mmHg) — la división Rp/Rd es una convención de modelado Windkessel de 3 elementos, no una cifra puntual de Guyton. Usuario aprobó explícitamente que este set quede **marcado como pendiente de validación experta**, igual que `r_rcr.py` ya declara para cualquier cambio de parámetros.
- **Procedencia nueva**: `Provenance.MODELO_HEMODINAMICO`, con banda de confianza propia **0.30-0.55** (por debajo de `SIMULACION`, 0.60-0.90) — más baja porque, a diferencia de un `DERIVADO` normal, esta cantidad depende de al menos un parámetro no derivado del organismo y no ha sido confirmada fisiológicamente en contexto todavía (eso es exactamente lo que hace el Paso 3). Usuario aprobó el nombre y la banda sin cambios.

**Paso 2 — conexión, con las tres decisiones aprobadas:**
- `domain/physiology/state/schema.py`: `Provenance.MODELO_HEMODINAMICO` + su banda en `CONFIDENCE_REFERENCE`.
- `domain/physiology/hemodynamics/physiological_flow.py` (nuevo): `STROKE_VOLUME_REFERENCE_ML=70.0` con cita; `PHYSIOLOGICAL_RRCR_PARAMETERS` (Rp=0.10, Rd=0.90, C=2.0, Pd=2.0 mmHg·s/mL / mL/mmHg / mmHg, R_poiseuille=0.0) marcado con `PHYSIOLOGICAL_PARAMETERS_PENDING_VALIDATION=True` y citación completa en el docstring del módulo — **pendiente de confirmación experta explícita**, no una cita verbatim como la tabla de PA estática; `physiological_pulsatile_flow(heart_rate_bpm)` construye el flujo de entrada real.
- `domain/physiology/state/repository.py`: nueva `append_descriptors()` — adjunta `PhysiologicalDescriptor` a un snapshot **ya existente** (sin crear uno nuevo), mismo criterio que `create_clinical_reference()` ya usa con su propia tabla.
- `domain/physiology/hemodynamics/ups_bridge.py` (nuevo): `compute_and_attach_calculated_pressure()` corre el R-RCR fisiológico, calcula sistólica (máx.)/diastólica (mín.)/PAM (media temporal real por integración trapezoidal del ciclo convergido — más rigurosa que la aproximación `estimate_map()`, porque aquí sí hay curva completa) y los persiste como `systolic_bp_modelo`/`diastolic_bp_modelo`/`map_modelo` (sufijo `_modelo` deliberado: nunca colisiona como clave de diccionario con un futuro `systolic_bp` medido/derivado real, ni con los nombres sin sufijo que usa `ClinicalReferenceValue`) con `Provenance.MODELO_HEMODINAMICO`. Incluye un `assert` explícito sobre `PHYSIOLOGICAL_PARAMETERS_PENDING_VALIDATION` como salvaguarda.
- `domain/physiology/hemodynamics/context_comparison.py` (nuevo, Paso 3): `run_scenario_pressure_comparison(scenario)` corre un escenario completo (`run_rich_scenario`, modo basal), adjunta la PA calculada al snapshot final, y la empareja con la `ClinicalReferenceValue` del mismo escenario. Ejecutable directo: `python -m domain.physiology.hemodynamics.context_comparison <escenario>`.

**Verificación en contexto — resultados reales, para revisión del usuario y su validador (no una validación automática):**

| Escenario | HR final | PA calculada (S/D/PAM) | PA de referencia (S/D/PAM) |
|---|---|---|---|
| healthy | 72 bpm | 97.9 / 74.3 / 86.1 mmHg | 120 / 80 / 93.3 mmHg |
| hypertension | 85 bpm | 114.6 / 88.0 / 101.3 mmHg | 130 / 80 / 96.7 mmHg |
| sepsis | 150 bpm | 198.9 / 156.6 / 177.8 mmHg | 85 / 55 / 65 mmHg |

`healthy`/`hypertension` quedan en el mismo orden de magnitud que la referencia y en la dirección correcta (hipertensión > sano). **`sepsis` diverge fuertemente y en dirección contraria** — la referencia clínica indica shock/hipotensión (PA baja), pero el modelo calcula PA alta, porque el shock séptico es fisiológicamente una caída de resistencia vascular (vasodilatación), y este modelo solo recibe `heart_rate` como entrada dinámica: R/Rp/Rd son constantes fijas, no responden al cuadro clínico. **Esto no se ajustó ni se ocultó** — es exactamente la señal de alarma que el Paso 3 está diseñado para producir: el modelo, tal como está conectado hoy, solo puede ser fisiológicamente razonable para escenarios dominados por cambios de frecuencia cardíaca, no para los dominados por cambios de resistencia/tono vascular. Queda documentado como limitación conocida, no resuelta en esta tanda.

**Verificación de proyecto:**
- 14 tests nuevos (`tests/test_hemodynamics_ups_bridge.py`): banda de confianza de `MODELO_HEMODINAMICO`, marca de pendiente-de-validación, separación del set fisiológico respecto al validado, cadencia real del flujo, escala por SV_ref, sistólica>PAM>diastólica, orden de magnitud plausible en mmHg, persistencia de los 3 descriptores con procedencia correcta, no-borrado de descriptores existentes, coexistencia con `ClinicalReferenceValue` sin sobrescritura mutua, comparación end-to-end con y sin referencia disponible.
- `pytest tests/`: 86/86 passed (72 previos + 14 nuevos; mismos 3 archivos con error de colección preexistente y no relacionado, excluidos igual que en tandas anteriores).
- Servidor real: HTTP 200.
- Aislamiento verificado por grep: `domain/physiology/state/`, `coupling/` y `narrator/*` no importan `hemodynamics` — la conexión es unidireccional (hemodynamics lee/escribe en el UPS; el UPS no sabe que hemodynamics existe). El motor de acoplamiento sigue sin poder leer PA (calculada ni de referencia) — misma limitación arquitectónica ya documentada en la tanda de PA estática, no resuelta aquí.

**Pendiente**: validación fisiológica en contexto por el usuario y su validador experto (la tabla de arriba es el insumo para esa revisión) — en particular, decidir si el hallazgo de `sepsis` requiere que R/Rp/Rd dejen de ser constantes fijas (conectarlas a algún indicador de tono vascular) antes de confiar en el modelo para escenarios de shock/vasodilatación.

## 2026-07-19 — "La película", vertical slice: módulo hemodinámico R→RCR (svZeroDSolver)

Primera pieza dinámica del modelo hemodinámico — presión = f(resistencia, compliancia, flujo), funcionando y verificada contra la referencia oficial de svZeroDSolver. Aditivo y completamente aislado: no toca el UPS, los escenarios, el narrador ni la PA estática existente.

**Paso 1 — integración técnica:**
- **Hallazgo antes de intentar nada**: no existe paquete de svZeroDSolver en PyPI. El repositorio actual (`SimVascular/svZeroDSolver`, BSD-3-Clause) está en C++ con bindings pybind11 — requiere compilar (CMake + toolchain C++). Confirmé explícitamente, antes de intentar cualquier otra cosa, que **este entorno no tiene compilador de C++, CMake ni Visual Studio instalados** (`cl.exe`/`gcc.exe`/`cmake.exe` no encontrados). Compilar el solver real no fue posible aquí.
- En su lugar: instalé y ejecuté genuinamente `svzerodsolver` — la implementación histórica en **Python puro** del mismo proyecto/organización (`SimVascular/svZeroDSolver-Archived`), pip-instalable sin compilar (`pip install git+https://github.com/SimVascular/svZeroDSolver-Archived.git`), con los mismos casos de prueba y la misma física que la versión C++ actual. Confirmé que sus casos `steadyFlow_R_RCR.json`/`pulsatileFlow_R_RCR.json` son idénticos a los del repo actual.
- **Licencia**: el repo actual (fuente de las ecuaciones citadas) es BSD-3-Clause. El repo archivado (usado para verificación, no como dependencia de producción) usa un texto de licencia distinto pero también permisivo/comercial (estilo MIT). Atribución completa, con el texto exacto de ambas licencias, en `domain/physiology/hemodynamics/THIRD_PARTY_NOTICES.md` — incluye una nota de transparencia explícita sobre esta desviación de "instala svZeroDSolver (BSD-3-Clause)" literal.
- **El módulo de producción (`r_rcr.py`) no depende de ningún paquete de svZeroDSolver** — solo de `numpy`/`scipy`, ya dependencias del proyecto. El paquete archivado se usó de forma aislada (`pip install --target`, fuera del repositorio) únicamente para generar datos de verificación durante esta tanda; no se agregó a `requirements.txt`.
- Ecuaciones del módulo R-RCR, citadas verbatim de `src/model/WindkesselBC.h` (bloque RCR) y `src/model/BloodVessel.cpp` (resistor) del repo oficial — no inventadas:
  - `dP_c/dt = (Rd·Q(t) − P_c + Pd) / (Rd·C)`
  - `P_outlet = P_c + Rp·Q(t)`; `P_inlet = P_outlet + R_poiseuille·Q(t)`
- `domain/physiology/hemodynamics/r_rcr.py` (nuevo subpaquete aislado): `RRCRParameters` (valores por defecto = exactamente los del caso de prueba oficial: R=100, Rp=1000, C=0.0001, Rd=1000, Pd=0 — no inventados), `simulate_r_rcr()` (integra la ODE con `scipy.integrate.solve_ivp`, condición inicial consistente con el flujo promediado del ciclo — mismo criterio que `use_steady_bcs.py` del solver oficial).

**Verificación matemática — dos niveles, ambos contra datos reales:**
1. **Checkpoints analíticos oficiales**: corrí el solver real (`svzerodsolver`) sobre los JSON de caso oficiales — reprodujo exactamente los valores publicados (steady: entrada 10500.0/salida 10000.0 mmHg-eq; pulsátil en t=0: entrada 4620.0/salida 4400.0). Mi propio módulo reproduce los mismos checkpoints con precisión de punto flotante.
2. **Curva dinámica completa**: extraje del solver real (corrida genuina, no recalculada) 11 puntos del último ciclo (régimen periódico) de la simulación pulsátil, y confirmé que mi módulo los reproduce con error máximo de 0.17 sobre una escala de ~9000 (~0.002%) — la diferencia es del esquema numérico (Radau adaptativo aquí vs. generalized-alpha de paso fijo en el oficial), no del modelo. Esta muestra queda embebida y citada en `tests/test_hemodynamics_r_rcr.py`.

**Paso 2 — inspección para validación fisiológica:**
- **Artifact interactivo publicado** (favicon 🫀): sliders para R/Rp/C/Rd/Pd + selector de flujo constante/pulsátil, gráfico en vivo de presión de entrada/salida y flujo sobre el último ciclo (régimen periódico), lecturas de presión pico/media/pulso. Reimplementa la misma ecuación en JavaScript (citada igual, botón "restaurar valores oficiales de referencia"), sin backend ni conexión a ningún dato del proyecto — completamente aislado, para que el validador pueda explorarlo sin correr el proyecto.
- Etiquetado explícito en el propio artefacto: "simulación educativa... no representa un paciente real ni ha sido validada fisiológicamente todavía".
- **No conectado al UPS ni a los escenarios** — vive aislado, mismo criterio que el motor de acoplamiento (Fase Conexión entre sistemas, 2026-07-15).

**Verificación de proyecto:**
- 8 tests nuevos (`tests/test_hemodynamics_r_rcr.py`): parámetros por defecto = caso oficial, checkpoint analítico steady y pulsátil (t=0) exactos, curva convergida completa contra la muestra real del solver oficial, presión constante bajo flujo constante (sanity check), mayor R → mayor presión (sanity check estructural, no fisiológico), mayor C → transitorio más lento (sanity check estructural), formas de array consistentes.
- Aislamiento confirmado por grep de todo el repo: `domain.physiology.hemodynamics` solo lo importa `tests/test_hemodynamics_r_rcr.py`.
- `pytest tests/`: 72/72 passed (64 previos + 8 nuevos; mismos 3 archivos con error de colección preexistente y no relacionado).
- Servidor real: HTTP 200 (el módulo nuevo no se importa desde la app viva).
- Cero cambios en `domain/physiology/state/*`, `scenarios/*`, `coupling/*`, `narrator/*`.

**Pendiente — validación fisiológica del usuario + su validador experto**, usando el Artifact: confirmar que el comportamiento (subir R → sube la presión; subir C → la curva se amortigua más lento; forma de la curva pulsátil) se corresponde con fisiología real antes de considerar cualquier conexión al flujo vivo del UPS — ese es un paso posterior, no de esta tanda.

## 2026-07-18 — Ampliación del UPS: presión arterial estática por escenario, con fuente

Primera señal nueva añadida al UPS desde su Fase 1.1. Aditiva — no toca `ups_values`/`ups_events`/`UnifiedPhysiologicalState`. Datos transcritos por el usuario desde fuentes clínicas citadas; Claude Code no inventó ni ajustó ningún número.

**Paso 1 — `Provenance.REFERENCIA_CLINICA`**: agregada al enum (`schema.py`) como etiqueta de clasificación — "típico de este cuadro según literatura citable, ni medido ni simulado ni derivado". **Deliberadamente sin banda en `CONFIDENCE_REFERENCE`**: esa tabla exige un número de confianza por cada procedencia (`default_confidence()` hace un lookup directo sin fallback), y ponerle una banda a un rango de guía de un libro de texto fingiría precisión de sensor que no tiene. En vez de forzarla en `PhysiologicalDescriptor` (que exige `confidence: float` obligatorio a nivel de dataclass Y de columna `NOT NULL` en `ups_values` — confirmado que no hay forma de evitarlo reutilizando esa tabla), se creó un tipo nuevo separado: mismo criterio ya aprobado para `ClinicalImpression`.

**Paso 2 — `ClinicalReferenceValue`** (`domain/physiology/state/clinical_reference.py`, nuevo): `scenario`, `domain`, `descriptor`, `value`, `unit`, `citation` (**obligatoria, validada en `__post_init__`** — sin cita no se construye, mismo patrón que `CouplingRule.source`), `phase_note` (opcional). `estimate_map(systolic, diastolic)` implementa PAM≈diastólica+⅓(sistólica−diastólica), reutilizada para derivar PAM en cada escenario con sistólica y diastólica disponibles — nunca hardcodeada a mano. Persistencia aditiva: `ClinicalReferenceRecord` (tabla nueva `ups_clinical_references`, FK a snapshot+patient, mismo patrón que `ClinicalImpressionRecord`) + `clinical_reference_repository.py` (nuevo, separado de `repository.py` y de `clinical_impression_repository.py`).

**Paso 3 — los 10 escenarios con fuente, verbatim:**

| Escenario | Sistólica | Diastólica | PAM (derivada) | Fuente | Fase |
|---|---|---|---|---|---|
| Sano | 120 | 80 | 93.3 | ACC/AHA 2017 | valor normal, sin fase particular |
| Hipertensión | 130 | 80 | 96.7 | ACC/AHA 2017 | umbral Estadio 1 (≥130/80), no crisis hipertensiva |
| Sepsis | 85 | 55* | 65 (directa) | Sepsis-3 | shock séptico / hipotensión refractaria |
| Apnea | 200 | 100 | 133.3 | Harrison's / AASM | pico de arousal post-apnea, no la fase apneica |
| Convulsión | 180 | 100 | 126.7 | Bradley's Neurology | fase ictal, no post-ictal |
| Hipoxia | 140 | 90 | 106.7 | West's Respiratory Physiology / ACLS | fase compensatoria, no hipoxia tardía |
| Arritmia | 90 | 60 | 70 | AHA/ACC/HRS | descompensación hemodinámica |
| Ejercicio | 162 | — | — | Guyton & Hall | +30-40% sobre basal; sin dato de diastólica en la fuente |
| Estrés | 207.5 | — | — | Guyton & Hall | pico agudo, basal+75-100 (confirmado por el usuario como incremento, no valor final); sin diastólica |
| Ansiedad | 207.5 | — | — | Guyton & Hall | misma cifra que Estrés (fuente combinada) |
| Fatiga crónica | — | — | — | **sin fuente** | no disponible, honesto |
| EPOC | — | — | — | **sin fuente** | no disponible, honesto |

\* Sepsis-3 da sistólica (<90) y PAM (<65) directamente; la diastólica (55) no viene de la fuente — se calculó resolviendo la fórmula de PAM citada para que fuera consistente con los otros dos valores. Marcado explícitamente en la cita de ese campo.

Rangos ("130-150/85-95", "+30-40% sobre basal") se representaron con su punto medio como `value` — el rango completo y su procedencia quedan en `phase_note`/`citation`, nunca ocultos.

**Paso 4 — consumidores encendidos:**
- `run_rich_scenario()` (`rich_engine.py`): tras completar los 6 horizontes, si el escenario tiene entrada en `BLOOD_PRESSURE_REFERENCES`, adjunta los valores al **último** snapshot únicamente — PA estática (una fotografía), no una entrada por horizonte.
- `risk_context.py::build_risk_features()`: `systolic_bp`/`diastolic_bp` ahora se leen del snapshot más reciente en vez de quedar siempre en `None`.
- Confirmado con el predictor **real** (`src.ai.patient_analytics.PatientRiskPredictor`, no un mock): tras correr un escenario con fuente, `'blood_pressure'` deja de aparecer en `factors_omitted` y aparece en `factors_used` — el peso de 0.25 se activa de verdad.
- `render_ml_risk_panel()` (Twin OS): el caption desactualizado ("el UPS no modela presión arterial... nunca rellenado") se reemplazó por uno que muestra la PA real cuando existe, etiquetada explícitamente como "referencia clínica citada del cuadro (no una medición del paciente ni una simulación dinámica)", o el honesto "sin PA disponible" cuando el escenario no tiene fuente.

**Límite importante, no resuelto en esta tanda — señalado antes de construir**: el motor de acoplamiento (`domain/physiology/coupling/engine.py`) solo lee `PhysiologicalDescriptor` dentro de `DomainState` — no `ClinicalReferenceValue`, que vive deliberadamente fuera de ese contenedor (para no forzar una confianza numérica fingida). **Con este diseño, la PA no dispara ni es efecto de ninguna regla del motor de acoplamiento todavía**, aunque ya esté disponible para el modelo de riesgo y el narrador. Conectar ambos sistemas es una decisión de diseño aparte, no tomada aquí.

**Verificación:**
- 20 tests nuevos (`tests/test_clinical_reference.py`): sin campos `provenance`/`confidence` (estructural), `citation`/`scenario`/`descriptor` obligatorios, `Provenance.REFERENCIA_CLINICA` confirmado sin banda en `CONFIDENCE_REFERENCE`, fórmula de PAM verificada (incluyendo el caso sepsis: 85/55 → PAM≈65), ida y vuelta por la base de datos, **FK real rechaza un snapshot inventado**, integridad de la tabla de datos (10 escenarios exactos, fatiga/EPOC ausentes, toda cita no vacía, escenarios bifásicos con `phase_note`), `run_rich_scenario` adjunta la referencia solo al snapshot final (no a los 6 horizontes) y solo para escenarios con fuente, `build_risk_features` devuelve valores reales para Hipertensión y `None` para EPOC, y el cruce con el predictor real confirmando la activación del factor de PA.
- `AppTest`: corrí el escenario Hipertensión en vivo en Twin OS → el panel de riesgo muestra "130/80 mmHg — referencia clínica citada del cuadro", el texto desactualizado desapareció, 0 excepciones.
- Sin regresión: Academia (teoría/quiz/casos) y Patient Pipeline recargados, 0 excepciones.
- `pytest tests/`: 64/64 passed (44 previos + 20 nuevos; mismos 3 archivos con error de colección preexistente y no relacionado).
- Servidor real: HTTP 200.
- Cero cambios en `ups_values`, `ups_events`, `UnifiedPhysiologicalState`, `Provenance` existentes (solo un miembro nuevo agregado), `PhysiologicalDescriptor`, `PhysiologicalEvent`.

## 2026-07-15 — Conexión entre sistemas, Paso 1a+1b: motor de acoplamiento fisiológico (dormido)

Nuevo subpaquete aislado `domain/physiology/coupling/`, tras una compuerta de diseño (Paso 1a, aprobado con dos decisiones cerradas: `COUPLABLE_DESCRIPTORS` restringido a señales primarias, `magnitude_hint` como texto libre opcional). El motor nace y queda **honestamente inerte**: sin ninguna regla real cargada, sin conexión al flujo vivo del UPS.

**Paso 1a — formato de regla (`rules.py`):**
- `CouplingCondition` (dominio + descriptor + `ComparisonOperator` + umbral + unidad) y `CouplingEffect` (dominio + descriptor + `EffectDirection` + `magnitude_hint` opcional) — ambos validan en `__post_init__` que el dominio sea uno de los que el UPS modela (cardiovascular/respiratorio) y que el descriptor esté en `COUPLABLE_DESCRIPTORS`.
- `COUPLABLE_DESCRIPTORS = {"cardiovascular": {"heart_rate", "hrv"}, "respiratory": {"respiratory_rate", "spo2"}}` — deliberadamente **excluye** los índices que el propio BIOCORE deriva (`health_score`, `risk_score`, `rhythm_stability`, `myocardial_stress`, `cardiac_output`, `hypoxia_risk`, `apnea_risk`, `tissue_oxygenation`): son invenciones de esta app, no conceptos de un libro de fisiología, así que una regla de acoplamiento citable no puede apuntar a ellos.
- `CouplingRule`: `source` (obligatorio, no vacío, validado estructuralmente — mismo patrón que `snapshot_id` en `ClinicalImpression`), `validation_status` (`TRANSCRITO_SIN_VALIDAR`/`VALIDADO_POR_FUENTE`), `enabled=False` por defecto — encender una regla transcrita es un acto explícito, nunca el estado de fábrica.

**Paso 1b — el motor (`engine.py`):**
- `evaluate(state, rules) -> List[ProposedCoupling]`: evalúa qué reglas **habilitadas** se disparan contra un `UnifiedPhysiologicalState` real. Reglas con `enabled=False` se ignoran por completo — ni siquiera se evalúa su condición. Si el descriptor de la condición no existe en el estado, la regla no se dispara — no se inventa un valor.
- **Nunca modifica el estado que recibe** — solo propone (`ProposedCoupling` trae la regla que disparó + el valor real observado); aplicar los efectos a un estado real es una fase futura, no esta.
- Con el conjunto de reglas real de este proyecto hoy — **vacío** — `evaluate(state, [])` siempre devuelve `[]`. No falla, no inventa, no aplica nada.

**Claude Code no pobló ninguna regla fisiológica real.** La única regla de ejemplo (`EJEMPLO_NO_VALIDADO_NO_USAR__hipoxia_taquicardia_refleja`, hipoxia → taquicardia refleja, citando Guyton & Hall cap. 41) vive **exclusivamente** en `tests/test_coupling_engine.py`, marcada `enabled=False` salvo cuando un test la activa a propósito para probar el motor — ningún módulo de producción la importa.

**Verificación:**
- 20 tests nuevos (`tests/test_coupling_engine.py`): `source`/`rule_id` obligatorios, `enabled=False` por defecto, dominio no modelado rechazado, descriptor derivado (`health_score`) rechazado explícitamente, los 4 `ComparisonOperator` parametrizados, motor con conjunto vacío inerte (tanto con un estado que cruzaría el umbral como con un escenario real de hipoxia), regla desactivada nunca dispara aunque la condición se cumpla, regla activada dispara y no dispara correctamente según el umbral, **`evaluate()` nunca muta el estado de entrada** (verificado comparando valores antes/después), descriptor ausente en el estado no dispara ni falla.
- Aislamiento confirmado por grep de todo el repo: `domain.physiology.coupling` solo lo importa `tests/test_coupling_engine.py` — ningún módulo de `app/`, `domain/physiology/scenarios/`, `domain/physiology/state/` ni `narrator/*` lo toca todavía.
- `pytest tests/`: 44/44 passed (24 previos + 20 nuevos; mismos 3 archivos con error de colección preexistente y no relacionado).
- Servidor real: HTTP 200 (el subpaquete nuevo no se importa desde la app viva, pero se confirma que nada se rompió).
- Cero cambios en `domain/physiology/state/*`, `narrator/*`, ni en el flujo actual del UPS.

**El motor queda dormido, a la espera de reglas reales transcritas con fuente.** Conectarlo al flujo vivo (que un `CouplingRule` real, con `enabled=True`, efectivamente altere estados del UPS) es una tanda futura, posterior a la transcripción.

## 2026-07-15 — Fusión de persistencia, Paso 1+2: `ClinicalImpression` en el UPS, retiro de `clinical_db.py`

Amplía por primera vez el esquema del núcleo del UPS (`domain/physiology/state/`), de forma estrictamente aditiva, tras una compuerta de diseño explícita (Paso 1, aprobado con la opción (ii): impresiones nunca embebidas en `UnifiedPhysiologicalState`).

**Paso 1 (diseño, aprobado antes de tocar código):** `ClinicalImpression` — juicio clínico humano ligado obligatoriamente a un `snapshot_id` real (estructural, como la procedencia). Decisión central: **nunca lleva `Provenance` ni `confidence`**. Razón técnica concreta: `CONFIDENCE_REFERENCE` es un `Dict[Provenance, ConfidenceBand]` sin fallback — añadir una procedencia nueva para "juicio humano" habría exigido o bien inventar una banda de confianza numérica (precisión fingida) o dejar una `KeyError` latente para el primer llamador. Es un tipo completamente aparte, en su propio archivo, separado también físicamente de `schema.py`/`repository.py`.

**Implementado (Paso 2):**
- `domain/physiology/state/clinical_impression.py` (nuevo): `ImpressionCategory` (6 categorías cerradas — estable/preocupación cardiovascular/preocupación respiratoria/preocupación combinada/requiere seguimiento/crítico — ligadas a los dos dominios que el UPS modela hoy, no arbitrarias como el viejo dropdown de 3) + `ClinicalImpression` (`snapshot_id`, `category`, `author`, `emitted_at`, `notes` opcional — sin ningún campo numérico de certeza; `__post_init__` valida `snapshot_id`/`author` obligatorios).
- `domain/physiology/state/models.py`: `ClinicalImpressionRecord` (tabla nueva `ups_clinical_impressions`, FK a `ups_snapshots` y `ups_patients` — patrón de `patient_id` redundante igual que `EventRecord`). `SnapshotRecord` gana un atributo `relationship` (`clinical_impressions`) — **cero columnas nuevas** en `ups_snapshots`/`ups_values`/`ups_events`, verificado con `PRAGMA table_info` tras la migración.
- `domain/physiology/state/clinical_impression_repository.py` (nuevo, separado de `repository.py`): `create_clinical_impression`, `get_clinical_impressions_for_snapshot`, `get_clinical_impressions_for_patient`, `get_latest_snapshot_id` (esta última necesaria porque `get_latest_state()` no expone el id del snapshot que arma — se resolvió sin tocar `repository.py`).
- `UnifiedPhysiologicalState` — **sin ningún cambio** (opción (ii) confirmada): las impresiones siempre se piden aparte.
- `render_patient_pipeline_page()` (`app/main.py`) reescrita sobre el UPS real: Vista Clínica arma un estado real (`DigitalTwinOrganism` + `from_digital_twin_organism` + `save_state`, mismo pipeline que ya usan Twin OS/Academia, provenance `SIMULACION` con `source_detail="patient_pipeline:entrada_manual"`) y permite emitir una `ClinicalImpression` sobre ese snapshot exacto; Vista IA narra el estado Y la impresión, con esta última anclada explícitamente en el `Finding` como "juicio humano — NO es una medición ni un cálculo".
- `app.clinical_db` retirado del flujo vivo: import reemplazado en `app/main.py` (línea ~54) por el del UPS; se quitó también su `init_db()` de arranque. `clinical_states.db` **se conserva sin borrar**.
- Fila de prueba `PATIENT-TEST-99` (insertada sin querer durante la verificación de la tanda de Research Hub) eliminada de `clinical_states.db`. Fila orgánica `PATIENT-001` — confirmado que no se puede migrar honestamente (un diagnóstico de dropdown sin ningún snapshot real al que ligarlo) — queda archivada tal cual, documentado aquí como la razón.

**Verificación:**
- 8 tests nuevos (`tests/test_clinical_impression.py`): sin campos `provenance`/`confidence` (chequeo estructural vía `dataclasses.fields`), `snapshot_id`/`author` obligatorios, ida y vuelta completa por la base de datos, impresión sin notas permitida, **FK real rechaza un `snapshot_id` inventado** (`IntegrityError`, no fallo silencioso), múltiples impresiones sobre un mismo snapshot preservan orden, `get_latest_snapshot_id` coincide con `get_latest_state`, y una regresión explícita confirmando que `ups_values`/`ups_events`/`UnifiedPhysiologicalState` siguen intactos.
- `AppTest` de punta a punta: guardé un estado real (FC 88, FR 20, SpO₂ 95 → confirmado `provenance=simulacion` en la tabla mostrada), emití una impresión (`Preocupación cardiovascular` + notas), confirmé que aparece en la lista de impresiones del paciente, cambié a Vista IA con narrador fake inyectado y confirmé que el `Finding` de la impresión llega con `value="preocupacion_cardiovascular"` y `meaning` conteniendo literalmente "NO es una medición ni un cálculo" + autor + notas — separado de los 13 `Finding` de descriptores/eventos medidos/derivados.
- Bug real encontrado y corregido en el camino: los botones "Guardar nuevo estado"/"Guardar impresión" llamaban `st.rerun()` justo después de `st.success(...)`, descartando el mensaje antes de que se viera — innecesario además, porque el estado/las impresiones ya se re-consultan más abajo en la misma pasada. Se quitaron ambos `st.rerun()`.
- Sin regresión: Twin OS (modo caso clínico + narrador principal), Academia (teoría + quiz + casos sintéticos), ECG Lab — recargados con narradores fake inyectados, 0 excepciones en todos.
- `PRAGMA table_info` confirmó columnas idénticas en `ups_snapshots`/`ups_values`/`ups_events` antes y después.
- `pytest tests/`: 24/24 passed (16 previos + 8 nuevos; mismos 3 archivos con error de colección preexistente y no relacionado).
- Servidor real: HTTP 200.
- Cero cambios en `Provenance`, `CONFIDENCE_REFERENCE`, `PhysiologicalDescriptor`, `PhysiologicalEvent`, `narrator/*`.

**Esperando confirmación del usuario — la prueba con clave real de Anthropic (emitir una impresión y ver al narrador tratarla como juicio humano con contenido real) queda de su lado, como se pidió.**

## 2026-07-14 — Última fusión de navegación: Patient Pipeline → Clinical Hub, eliminados AI Analysis y Research Hub

Cierra la serie de fusiones de navegación. Solo reorganización — persistencia (`app.clinical_db`) sin tocar.

**Paso 1 (inventario, confirmado antes de ejecutar):** Patient Pipeline tiene 2 vistas reales (Clínica: ficha + guardar/cargar real vía `save_patient_state`/`list_patient_states`/`load_patient_state` de `app.clinical_db`, importadas a nivel de módulo desde siempre; IA: narra el último estado guardado vía `render_findings_narrator`) y 4 vistas sin contenido real (Educativa/Simulación/Gemelo Digital: texto fijo; Investigación: botón "Cargar cohortes demo" que solo mostraba éxito sin cargar nada). Confirmé que mover la página no toca ni una línea de `clinical_db.py` — el import es de módulo, independiente de la estructura de `HUBS`. `render_ai_analysis_page()` confirmado como título + un `st.info()`, cero lógica.

**Paso 2 — ejecución:**
- `render_patient_pipeline_page()`: `render_view_selector()` ahora recibe `views=['Clínica', 'IA']` explícito — las 4 vistas sin contenido real ya no son ni siquiera seleccionables (mismo criterio que las cáscaras de Education: no dejar opciones que aparenten funcionalidad). Vista Clínica y Vista IA, sin ningún cambio de lógica ni de las llamadas a `clinical_db.py`.
- `render_ai_analysis_page()` eliminada — reemplazada por un comentario explicando qué era y por qué se quitó.
- `HUBS["Research Hub"]` eliminado. `"👥 Patient Pipeline"` añadida al final de `HUBS["Clinical Hub"]`.
- Router (`render_page_content()`): rama de Research Hub eliminada; `"Patient Pipeline" in page` añadida como un `elif` más dentro de Clinical Hub.
- Hilos colgantes: tarjeta HTML "Research Hub" de Mission Control quitada (grid de 4→3 columnas, texto de Clinical Hub actualizado para mencionar "pipeline de pacientes"); botón de lanzamiento "Research Hub" quitado (`st.columns(4)`→`st.columns(3)`); tarjeta numerada "3. Research Hub" de la grilla de bienvenida (`render_home_page()`) quitada y el resto renumerado 1→4 sin saltos (Digital Twin OS pasa de 4 a 3, HRV Lab de 5 a 4).
- **Hallazgo colateral, no de esta tanda**: `render_home_page()` no es alcanzable hoy desde la navegación en vivo — el `else: render_home_page()` del router solo dispara cuando `selected_page` no está en ninguna lista de `HUBS`, pero el propio sidebar valida `selected_page` contra la lista del hub activo (`HUBS[hub].index(...)`), así que siempre aterriza en un valor válido. Es código preexistente, no introducido ni roto por esta tanda — se deja igual, solo se documenta.

**Verificación:**
- Sidebar: 3 hubs (Digital Twin OS, Learning Hub, Clinical Hub) — "Research Hub" ausente. Clinical Hub incluye "👥 Patient Pipeline" junto a "🫀 ECG Lab" y el resto.
- Mission Control: 3 botones de lanzamiento, sin hueco de columna, sin texto "Research Hub" en ningún markdown renderizado.
- `render_home_page()` verificado de forma aislada (con un wrapper que la importa y llama directamente, ya que no es alcanzable por clic) — grid 1-4 sin "Research Hub" y sin salto de numeración.
- Patient Pipeline end-to-end desde Clinical Hub: `AppTest` guardó un estado real (confirmación "Estado guardado" + aparece en "Estados guardados recientes"), cambió a Vista IA y confirmó que invoca al narrador sobre ese mismo estado — 0 excepciones en todo el flujo. Selector de vista limitado a exactamente `['Clínica', 'IA']`.
- `pytest tests/`: 16/16 passed (mismos 3 archivos con error de colección preexistente y no relacionado).
- Servidor real: HTTP 200.
- Cero cambios en `app/clinical_db.py`, `domain/physiology/*` ni `narrator/*`.

## 2026-07-14 — Fusión ECG Monitor + ECG-12 → "ECG Lab" (reorganización de navegación)

Paso 1 (inventario) + Paso 2 (unificación). Ambos flujos íntegros, ninguna lógica de análisis reescrita — solo agrupados bajo una entrada de menú con pestañas.

**Paso 1 — inventario (entregado y confirmado antes de tocar código):** catalogué los ~20 widgets de `render_ecg_monitor_page()` (`app/main.py`, incluida la joya: 61 casos vía `get_case_database()`, MIT-BIH/PTB-XL de PhysioNet, ESP32 con disciplina de procedencia SENSOR_REAL/SIMULACIÓN, notebook reproducible) contra los ~13 de `ecg_12/page_content.py` (13 escenarios de 12 derivaciones, quiz de 19 preguntas) uno por uno, por label exacto. Cero session_state compartido, cero colisión de widgets — dos flujos genuinamente independientes. Encontré y reporté dos pares "near-miss" (mismo tema, texto casi idéntico, sin colisionar hoy solo porque el texto difiere): `'Frecuencia cardíaca (bpm)'` vs `'Frecuencia Cardíaca (bpm)'` (una mayúscula) y `'QRS (ms)'` vs `'Duración QRS (ms)'`. También confirmé empíricamente (no solo por lectura) que `page_content.py` llama `st.set_page_config()` una segunda vez vía `runpy` y hoy no rompe nada.

**Paso 2 — unificación:**
- Nueva `render_ecg_lab_page()` (`app/main.py`): `st.tabs(["Monitoreo", "12 Derivaciones"])`, cada pestaña llama a `render_ecg_monitor_page()`/`render_ecg_12_page()` sin ninguna modificación a su lógica — solo se reubicó la llamada.
- `HUBS["Clinical Hub"]`: `"📊 ECG Monitor"` y `"📋 ECG-12-Derivaciones"` reemplazadas por una sola entrada `"🫀 ECG Lab"`. Ruteo en `render_page_content()` colapsado a un solo `if "ECG Lab" in page`.
- **Protección contra la fragilidad detectada** (pedida explícitamente antes de unificar, para que la independencia no dependa de una coincidencia de redacción): los 4 widgets de los 2 pares near-miss recibieron `key=` explícita — `ecglab_monitor_sim_hr`/`ecglab_monitor_sim_qrs` en `render_ecg_monitor_page()`, `ecglab_12_hr_slider`/`ecglab_12_qrs_duration_slider` en `page_content.py`. Ningún otro widget necesitó key nueva (`render_view_selector()`, usado por ECG Monitor, ya namespacea su key por el nombre de la función llamadora).
- Hilo colgante corregido: el disclaimer de "AI Analysis" (nombraba "ECG-12" y "ECG Monitor" por separado) ahora dice "ECG Lab". Confirmé tras el cambio que Mission Control, home y Guides no tenían ninguna referencia por nombre a los módulos viejos (grep de archivo completo, antes y después) — la única referencia de texto suelta era esa.

**Verificación:**
- `AppTest`: "ECG Lab" carga con 0 excepciones; el menú de Clinical Hub muestra una sola entrada nueva y ninguna de las dos viejas.
- Joya ECG (Monitoreo): las 6 fuentes presentes (Demo/CSV/61 casos/MIT-BIH/PTB-XL/ESP32); "Caso clínico (61 disponibles)" carga `get_case_database()` en vivo sin excepciones; ESP32 muestra su disciplina de procedencia (`SIMULACIÓN` explícita sin hardware real) con el botón "Conectar" en su key original intacta.
- 12 Derivaciones: 13 escenarios clínicos y quiz de 19 preguntas presentes e intactos.
- `st.set_page_config()` post-merge: probado explícitamente (no asumido) — 0 excepciones con ambas pestañas activas en el mismo run.
- **Near-miss resuelto por diseño**: verifiqué ambos pares de sliders coexistiendo en el mismo script run (las dos pestañas se ejecutan juntas) con `AppTest`, confirmando 2 keys distintas por par — la independencia ya no depende de que el texto del label siga siendo distinto.
- `pytest tests/`: 16/16 passed (mismos 3 archivos con error de colección preexistente y no relacionado).
- Servidor real: HTTP 200.
- Cero cambios en `domain/physiology/*` ni `narrator/*`.

## 2026-07-14 — Módulo de aprendizaje, Capa de teoría: resurfacear la tabla real de 12 derivaciones

Cierra el módulo de aprendizaje (teoría + casos + quizzes). Alcance mínimo y honesto: cero teoría generada o inventada — solo se resurfaceó la única tabla real que ya existía huérfana en el código.

**Resurfaceado (`app/supermodules/academia/pages.py`, nueva `render_theory_section()`):**
- `educational.ecg_academy.lead_explanations()` — tabla de las 12 derivaciones del ECG (qué observa cada una, qué pared representa, qué arteria coronaria suele comprometerse) — mostrada tal cual, sin reescribir ningún valor. Antes de esta tanda no la llamaba nada en la app viva (solo un archivo de `_archive/`, código muerto).
- Expuesta como expander "📖 Teoría — Las 12 derivaciones del ECG" en Academia → Lecciones y Casos, con la fuente marcada explícitamente (`lead_explanations()`) y sin disfrazarla de "curso completo" — se presenta como lo que es.
- Llamada al inicio de `render_lessons_quizzes_tab()`, antes de quizzes y casos — el módulo de aprendizaje ahora sigue el orden teoría → quiz → caso.

**Cáscaras eliminadas (`app/main.py::render_education_page()`):**
- Las 5 "tarjetas de curso" (Cardio-Fisiología, Neurofisiología, Fisiología Respiratoria, Músculo y EMG, Interpretación Clínica) mostraban una barra de progreso ficticia — `st.session_state.learning_progress`, números fijos (58/42/33/26/69) iguales para cualquier usuario en cualquier sesión, que el botón "Avanzar en aprendizaje" solo incrementaba +5 por clic sin ningún avance real detrás (Art. I de la Constitución, mismo patrón que "Nivel"/"XP Total" ya eliminado de Academia en Consolidación Tanda 1).
- Eliminado: el dict `learning_progress` (init de sesión), las 5 tarjetas con barra de progreso, y el botón "Avanzar en aprendizaje". Reemplazado por un placeholder honesto: puntero a la lección real de Academia para "Fisiología Cardiovascular" (la única con contenido real detrás) y `🚧 ... — teoría en desarrollo, sin contenido real todavía` para los otros 4 temas, sin simular avance ni porcentaje.
- Efecto colateral encontrado y corregido: dentro del expander "🧠 Actividad de quiz supervisada" (más abajo en la misma página) había dos líneas (`st.progress(progress/100)` / `st.caption(f'Nivel: {progress}%')`) que reutilizaban por fuga de variable de bucle el `progress` de la última tarjeta eliminada — ya de por sí una visualización sin sentido (nivel de curso mostrado dentro de una caja de quiz ajena). Se quitaron junto con las tarjetas; sin ellas habrían lanzado `NameError`.
- "### 4. IA" (el texto que acompañaba al botón) se reemplazó por el mismo disclaimer honesto ya usado en la pestaña 'Vista IA' de esta página — apunta al Narrador Clínico real en Digital Twin OS, no un texto nuevo inventado.

**Verificación:**
- `AppTest`: la tabla de teoría renderiza 12 filas reales (`Derivación`/`Qué observa`/`Pared`/`Arteria típica`), fuente marcada en el caption, contenido verificado puntualmente (V1 → DA/LAD) contra `lead_explanations()`.
- Education: 0 excepciones tras la limpieza; cero "Progreso: N%"/"Nivel: N%" residual; botón "Avanzar en aprendizaje" confirmado ausente; los 4 placeholders honestos presentes; puntero a la lección real de Academia presente.
- Sin regresión: selector de lección del quiz (Capa 1) intacto, botón "Iniciar Quiz" presente, sección de casos sintéticos (Paso 2) presente y gateada honestamente (sin `ANTHROPIC_API_KEY` en este sandbox, muestra su warning esperado en vez de romperse).
- `pytest tests/`: 16/16 passed (mismos 3 archivos con error de colección preexistente y no relacionado).
- Servidor real: HTTP 200.
- Cero cambios en `domain/physiology/*` ni `narrator/*`.

**Esperando confirmación del usuario antes de cerrar esta capa.**

## 2026-07-14 — Banco de casos clínicos sintéticos sobre el simulador propio (Paso 1 + Paso 2)

Capa de "casos" del módulo de aprendizaje, construida sobre los 12 escenarios reales del simulador de BIOCORE — fuente 100% propia, sin restricción de licencia. Reutiliza el motor de evaluación y el patrón ocultar→elegir→revelar del modo caso clínico de Twin OS; no se construyó mecánica nueva.

**Paso 1 — generador (`domain/physiology/scenarios/case_bank.py`, nuevo):**
- `generate_case(session, scenario=None, rng=None) -> ClinicalCase` reutiliza `run_rich_scenario` (Fase 1.2/Tanda 3) sin tocar el motor de simulación. Si `scenario` es `None`, elige uno al azar entre los 12 reales de `SimulationScenario` — nunca un patrón fuera del catálogo.
- Tres ejes de variación, todos honestos (nada numérico inventado): (1) **estado inicial** — jitter dentro de rango fisiológico normal de reposo (FC 60-85, etc.) antes de correr el escenario, evolucionado después por la lógica real del motor; (2) **punto de la evolución** — se elige al azar uno de los 6 horizontes reales que el motor ya calcula (now/5min/30min/2h/24h/7d) como snapshot del caso, en vez de fijar siempre el último; (3) **ruido** — el gaussiano que `SimulationEngine` ya aplica sin semilla en cada corrida, gratis.
- **Severidad NO es un eje de variación**: el motor no la expone como parámetro real (solo etiquetas descriptivas internas de cada `_simulate_*`, no configurables desde fuera). Fingir una perilla de severidad sin alterar la simulación real habría sido fisiología fingida (Art. I) — documentado en el docstring del módulo; ampliarlo requiere tocar `app/engines/simulation_engine.py`, fuera de alcance de este banco.
- `ClinicalCase` (dataclass) trae `origen`/`provenance`/`parametros` como campos estructurales obligatorios — `__post_init__` rechaza cualquier caso sin `origen="simulador_biocore"` o `provenance != Provenance.SIMULACION` (probado). El diagnóstico correcto es el `scenario` que generó el caso — verdad por código, nunca por el modelo.
- Verificado: los 12 escenarios generan caso sin error; dos casos forzados al mismo patrón dan `case_id`/semilla/horizonte distintos (variación real); rechazo correcto de `origen`/`provenance` inválidos.

**Paso 2 — integración (`app/supermodules/academia/pages.py`):**
- Nueva `render_synthetic_case_section()`, llamada desde `render_lessons_quizzes_tab()` ("Lecciones y Casos"). Reutiliza `_diagnostic_options`, `RICH_SCENARIO_LABELS` y `_dedupe_events` **importados directamente de `twin_shell/pages.py`** (no reescritos) para los distractores (patrón correcto + 3 de los otros 11 reales) y la deduplicación de eventos; reutiliza `render_ups_body` (mismo cuerpo visual) y `stream_findings_narration`/`Finding`/`FindingsContext` tal cual, sin construir evaluación nueva.
- **Reemplaza** la vieja sección pasiva "Casos clínicos de ejemplo" (`educational.clinical_cases.sample_cases()`), que filtraba el diagnóstico en la propia etiqueta del botón ("Cargar caso ...: `<diagnóstico>`") — lo opuesto de un caso ciego. Import de `sample_cases` eliminado.
- **Desviación deliberada de Twin OS, justificada por corrección**: el modo caso clínico de Twin OS arma el feedback con `build_context(session, patient_id)`, que siempre lee `get_latest_state` (el último horizonte). Como `generate_case()` puede elegir *cualquiera* de los 6 horizontes como "el caso" (no siempre el último), usar `build_context()` aquí habría alimentado al narrador con datos de un momento distinto al que el estudiante vio — desanclado. Las `Finding` se arman en cambio directamente desde el mismo `state`/`events` guardados en sesión (los que efectivamente se mostraron). Encontrado y corregido antes de cerrar, vía `AppTest` (`AttributeError: 'PhysiologicalDescriptor' object has no attribute 'domain'` en el primer intento — variable de bucle mal referenciada, no relacionado con la desviación de `build_context`).
- Etiquetado de simulación honesto: caption explícito "🧪 Caso simulado por el banco de casos de BIOCORE — no es un paciente real" antes de generar, columna "Procedencia" (`simulacion`) en la tabla de descriptores, y recordatorio con escenario/horizonte tras revelar.
- "Otro caso": genera una variación nueva del generador y limpia todo el `session_state` previo (`academia_case_*`).

**Verificación (ocultamiento en ambas ramas, mecánica end-to-end con narrador fake):**
- `AppTest` con narrador fake inyectado: antes de responder, el nombre/label del escenario oculto no aparece en ningún texto renderizado (markdown/caption/warning/info/success/error/header) — confirmado con dos ciclos completos, incluyendo la propia lista de opciones del radio (4 reales, la correcta entre ellas, sin marcar cuál).
- Rama incorrecta: feedback narrado presente, findings enviados incluyen "Diagnóstico elegido por el estudiante"/"Diagnóstico correcto (verdad de referencia del caso)", revelación correcta tras responder, etiqueta 🧪 de simulación visible.
- Rama correcta: mensaje "¡Correcto!" mostrado, 0 excepciones.
- "Otro caso" limpia el estado y permite un nuevo ciclo completo sin excepciones.
- Sin regresión: modo caso clínico de Twin OS (botón "Nuevo caso clínico", 0 excepciones) y quiz de la Capa 1 (Arritmias/advanced, rama correcta) re-verificados con `AppTest` tras la integración.
- `pytest tests/`: 16/16 passed (mismos 3 archivos con error de colección preexistente y no relacionado, ya reportados en la tanda anterior).
- Servidor real: HTTP 200.
- Cero cambios en `domain/physiology/state/*`, `domain/physiology/narrator/*` (solo reutilización) ni en el motor de simulación (`app/engines/simulation_engine.py`, `domain/physiology/scenarios/rich_engine.py`).

**Esperando confirmación del usuario antes de cerrar esta capa.**

## 2026-07-13 — Fusión Education+Academia, Capa 1: banco de preguntas unificado + evaluación vía narrador real

Primera capa de la Opción B (tres capas nuevas, evaluación vía narrador). Solo quizzes — teoría y casos ciegos quedan para tandas posteriores, sin tocar en esta.

**Pausa de diseño antes de codear** (dos preguntas reales sin respuesta obvia en el código, resueltas con el usuario antes de tocar nada): (1) las 14 preguntas de `educational.learning_engine` no tenían etiqueta de lección — se decidió **categorizar por contenido real** (leer qué pregunta cada una de verdad, no inventar preguntas nuevas) en vez de simplificar el selector o dejarlo desconectado. (2) la pregunta de PPG rescatada no encaja en ninguna de las 3 lecciones (todas ECG) — se decidió agregar una 4ª categoría honesta, "Otras señales", en vez de forzarla donde no pertenece.

**Paso 1 — banco unificado (`educational/learning_engine.py`, motor base sin reemplazar):**
- `QuizQuestion` ganó dos campos: `category` (de qué trata realmente cada pregunta — clasificación, no contenido nuevo) y `explanation` (solo poblado cuando ya existía un texto real de origen).
- Categorizadas las 14 preguntas originales por su contenido real: **ECG Básico** (6), **ECG 12-derivaciones** (4), **Arritmias** (4 con la nueva), **Otras señales** (2 con la nueva) — incluye una corrección de clasificación real: la pregunta de "banda EEG" que vivía sin más en el pool `ecg_basics` no es una pregunta de ECG, se etiquetó honestamente como "Otras señales".
- Sumadas las 2 preguntas reales de `src/education/learning.py::create_quiz()` (temas `ecg`/`ppg`) — antes inalcanzables por 3 bugs de conexión independientes: tema `'cardio'` inexistente en esa función (solo reconocía `'ecg'`/`'ppg'`), el llamador esperaba una lista y la función devolvía un dict, y las claves eran en español donde el llamador esperaba inglés. Contenido y explicación copiados tal cual — cero preguntas nuevas inventadas.
- Bug encontrado y corregido al integrar: el tope de "avanzado" (`min(12, len(questions))`) dejaba las 2 preguntas nuevas (al final del pool, ahora de 16) inalcanzables incluso en el nivel más alto. "Avanzado" ahora es "todo lo disponible en el filtro aplicado", sin un número fijo que quede desactualizado.
- `generate_quiz()` ganó un parámetro `lesson` opcional (filtra por categoría antes de aplicar el nivel) — con `lesson=None` se comporta exactamente igual que antes (compatibilidad hacia atrás verificada).
- Bug de Academia corregido: el selector de "Lección" ahora sí se pasa a `generate_quiz(lesson=...)` — antes las 3 opciones daban siempre el mismo quiz de `ecg_basics` completo.
- **Resultado: 16 preguntas reales alcanzables, 0 rotas.**

**Paso 2 — evaluación vía narrador (`app/supermodules/academia/pages.py`):**
- Cada pregunta sigue ahora el patrón ocultar→elegir→revelar del modo caso clínico: el estudiante elige una opción, el acierto/error se calcula primero por código (`idx == q.answer` — la verdad de referencia nunca la decide el modelo), y solo entonces se llama a `stream_findings_narration()` — el mismo motor genérico que ya usa Twin OS, sin construir nada nuevo ni tocar `domain/physiology/narrator/*` — con 3 `Finding`: la pregunta, la opción elegida, y la respuesta correcta (con su explicación real cuando existe). El narrador explica el porqué; nunca decide qué es correcto.
- Progreso real mostrado de vuelta: `engine.get_progress()` (ya guardado de verdad vía `rural_mode`, antes invisible) ahora se despliega en un expander "Tu progreso guardado" al abrir la pestaña — verificado que sobrevive a un recargo de página con el mismo `student_id`.
- **Evaluación falsa eliminada**: el botón "Enviar Respuesta" de Misiones (que mostraba "¡Misión completada!" + XP sin importar el texto escrito) se quitó — reemplazado por una nota honesta señalando que la evaluación de misiones no está construida todavía, y redirigiendo a los quizzes evaluados de verdad. La navegación/tarjetas de misión (contenido real, no evaluación) no se tocaron.

**Verificación:**
- Banco: 16 preguntas confirmadas, 4 categorías suman exactamente 16, las 2 rescatadas presentes con su categoría y explicación real, llamada sin `lesson` (compatibilidad) sigue devolviendo 5/8/16 según nivel.
- Flujo completo probado con narrador fake inyectado (sin `ANTHROPIC_API_KEY` real en este entorno): rama incorrecta (findings correctos enviados: Pregunta/Opción elegida/Respuesta correcta) y rama correcta, avance entre preguntas, finalización con puntuación real, **persistencia real en disco confirmada** (`data/local/progress_<id>.json` escrito), y **progreso mostrado de vuelta tras recargar la página** con el mismo `student_id` (confirmado en el HTML renderizado).
- Misiones: botón de evaluación falsa confirmado ausente; nota honesta confirmada presente; sin regresión en la navegación de misiones.
- `pytest tests/`: 16/16 passed.
- Modo Caso Clínico (Twin OS), Razonamiento causal, Narrador principal, y Joya 1 (ECG Monitor) re-verificados de punta a punta — sin regresión.
- Los 21 puntos de menú restantes recargados sin excepciones.
- Servidor real HTTP 200.
- Cero cambios en `domain/physiology/narrator/*` ni `state/*` — solo reutilización.

**Confirmado por el usuario el 2026-07-13. Capa 1 cerrada.** Pendiente de su lado: probar el feedback real del narrador con su propia `ANTHROPIC_API_KEY`. Capa 2 (teoría) y Capa 3 (casos clínicos ciegos) quedan para tandas futuras, sin construir todavía.

## 2026-07-13 — Dos bugs del Digital Twin: SVG como texto (arreglado), narrador cortado (diagnosticado) → max_tokens (arreglado) + Razonamiento causal a IA real (construido)

**Bug 1 — SVG crudo renderizado como texto — arreglado.** Causa raíz: `_render_heart_card()`/`_render_lungs_card()` (`app/supermodules/twin_shell/ups_body_visual.py`) devolvían el HTML/SVG como f-string multilínea con 4 espacios de sangría al inicio de cada línea. Markdown (CommonMark) interpreta cualquier línea indentada 4+ espacios como bloque de código preformateado — texto literal — *antes* de que `unsafe_allow_html=True` (ya presente y correcto en `render_ups_body()`) tenga oportunidad de dejar pasar el HTML. Arreglo: ambos retornos reescritos sin ninguna sangría (flush-left), mismo markup y lógica, cero cambio de comportamiento salvo dejar de disparar la regla de bloque de código. Verificado con el valor exacto que `AppTest` pasa a `st.markdown()`: `<svg` presente, 0 espacios de sangría inicial, en ambos órganos.

**Bug 2 — diagnóstico**: dos paneles con naturalezas distintas.
- "Razonamiento causal" (`CausalityEngine.find_root_cause()`) **no llama a ningún modelo** — es Python puro sobre `CAUSAL_RULES` fijas. No puede sufrir truncamiento de API; si se siente cortado es por lo abrupto del template, no por streaming/max_tokens/excepción.
- "Feedback del modo caso clínico" (`stream_findings_narration()`) sí es una llamada real con streaming. Causa raíz identificada: `max_tokens=512` — insuficiente para lo que el prompt pide (explicar ajuste Y desajuste, citando descriptores/eventos reales). Descartada la excepción como causa: el `try/except` en `twin_shell/pages.py` descarta cualquier texto parcial ante un error y muestra un `st.error` completo — nunca un texto cortado sin aviso.

**Movimiento 1 — arreglo directo**: `max_tokens` de `stream_findings_narration()` (`domain/physiology/narrator/findings.py`) subido de 512 a 1024, igualando al narrador principal (`client.py`) que ya venía funcionando sin cortes. Verificado con un cliente Anthropic fake que el valor llega correctamente a `client.messages.stream()`.

**Movimiento 2 — Razonamiento causal reemplazado por narrador de IA real** (diseño aprobado en 2a, antes de codear):
- Nuevo módulo `domain/physiology/narrator/causal.py` — mismo patrón que `findings.py`/`client.py`: `CausalContext`/`CausalHint`, `build_causal_context()`, `stream_causal_narration()` (`max_tokens=1024`).
- `build_causal_context()` reutiliza `build_context()` sin cambiarlo — la comparación antes→ahora de cada descriptor y el orden temporal de los eventos ya son, por construcción, la evidencia causal.
- De las 8 reglas de `CausalityEngine.CAUSAL_RULES` (sin tocar, queda huérfano), solo 2 conectan exclusivamente dominios que el UPS modela hoy (`hypoxia_cardiac`: spo2→heart_rate; `respiratory_oxygenation`: respiratory_rate→spo2) — las otras 6 involucran brain/muscles/autonomic, que el UPS no modela. Se conservan solo esas 2, como "reference_physiological_hints" explícitamente marcadas como marco interpretativo, nunca como hecho medido — pasar las otras 6 habría invitado al modelo a especular sobre datos inexistentes.
- El prompt exige razonar el origen (no describir el estado), anclar cada paso causal a un descriptor/evento real, usar el orden temporal como evidencia, y declarar honestamente "no hay suficiente historial" si no hay trayectoria — nunca inventar una causa (mismo principio que `before_value=None`).
- `render_causal_reasoning()` (`twin_shell/pages.py`) ya no usa `CausalityEngine` — persiste un snapshot fresco (mismo patrón que "Explicar estado actual") y llama al narrador causal real. Solo disponible para `heart`/`lungs` (los dos órganos UPS-fundamentados); para `brain`/`muscles`/`autonomic` declara honestamente que el UPS no modela ese dominio, sin botón y sin llamar a la API.

**Verificación:**
- Unitaria: `build_causal_context()` con datos UPS reales (dos snapshots, HR/SpO2 con trayectoria) — 2 hints presentes, ambos con descriptores dentro de {spo2, heart_rate, respiratory_rate} (cero fuga de hints sobre dominios no modelados); `stream_causal_narration()` con cliente fake — `max_tokens=1024` confirmado en la llamada.
- UI (`AppTest`, narrador fake inyectado): órgano `heart` → expander presente, botón dispara la llamada, texto narrado renderizado, contexto capturado con `target_organ="heart"`. Órgano `brain` → mensaje honesto presente, **botón ausente** (llamada a la API estructuralmente imposible, no solo evitada por lógica).
- `pytest tests/`: 16/16 passed.
- Narrador principal ("Explicar estado actual"), modo Caso Clínico Interactivo, y Joya 1 (ECG Monitor) re-verificados de punta a punta — sin regresión.
- Bug 1 (cuerpo SVG) re-verificado tras los cambios del narrador causal — sin regresión.
- Servidor real HTTP 200.
- Cero cambios en `domain/physiology/state/*`.

## 2026-07-13 — Consolidación, Tanda 4: eliminación de Hardware Hub (cáscara que no centraliza) — último borrado limpio

Tercer y último paso de esta ronda de borrados limpios de la estrategia C. Verificación reforzada respecto a Simulation Hub/AI Hub, porque aquí hay hardware real de por medio y "no centraliza" no es lo mismo que "está vacío" — había que confirmarlo, no asumirlo.

**Paso 1 — verificación reforzada, sin lógica de hardware real en uso:**
- `render_hardware_ops_page()` revisada línea por línea: su único contacto con hardware era `EMGStreamer is not None` — un chequeo booleano de solo lectura sobre una referencia ya importada al inicio de `main.py`, sin instanciar ni conectar nada. La importación en sí, y las conexiones reales que la usan de verdad (`render_emg_page()`, líneas 693-698), no se tocaron.
- Confirmado por grep: ningún supermódulo importa nada de `app.main` — las conexiones reales de ECG Monitor (ESP32), EMG (EMGStreamer), EEG Neuro Lab (`page_content.py`, SensorManager/ESP32SignalSource) y Twin OS (ESP32 en el clasificador de ECG) viven cada una en su propio archivo, self-contained.
- Solo 5 hilos colgantes esta vez (menos que Simulation Hub y AI Hub): entrada de `HUBS`, rama del router, tarjeta de la home page, y la función misma. A diferencia de AI Hub: **Mission Control nunca tuvo tarjeta ni botón para Hardware Hub**, y ningún otro módulo (Guides, Education, Academia, sidebar) lo mencionaba — confirmado por grep en todo `app/`.

**Paso 2 — eliminado**: la entrada `"Hardware Hub"` de `HUBS`, la rama del router, `render_hardware_ops_page()` completa, y la tarjeta renumerada de la home page.

**No tocado**: el import de `EMGStreamer`, la conexión real de EMG (`render_emg_page()`), la de ECG Monitor (ESP32, Joya 1), la de EEG Neuro Lab, ni la de Twin OS. `domain/physiology/*` sin cambios.

**Verificación:**
- `HUBS` confirmado sin `"Hardware Hub"`; `render_hardware_ops_page` confirmado ausente. Quedan 4 hubs: Digital Twin OS, Learning Hub, Clinical Hub, Research Hub (17 puntos de menú).
- Los 17 puntos de menú restantes recargados vía `AppTest`: 0 excepciones en todos, incluida la home page sin texto residual de "Hardware Hub".
- **Las 4 conexiones de hardware real confirmadas explícitamente intactas y operables** (no solo "el módulo carga"): EMG Muscle Lab con la opción "Live Hardware" y su botón "Conectar EMG Hardware" presentes; ECG Monitor con "Hardware ESP32 en vivo" presente (Joya 1); EEG Neuro Lab cargando limpio; Twin OS con "Hardware real ESP32 (modo B)" presente en el clasificador de ECG.
- `pytest tests/`: 16/16 passed.
- Servidor real HTTP 200.

Con esto se cierran los tres borrados limpios de la estrategia C (Simulation Hub, AI Hub, Hardware Hub). La plataforma pasó de 7 a 4 hubs sin perder ninguna función real.

## 2026-07-13 — Consolidación, Tanda 3: eliminación de AI Hub (puerta duplicada, no cáscara)

Segundo paso de la estrategia C. Distinto de Simulation Hub: aquí la función es real (el narrador clínico de Twin OS), solo la puerta era redundante — la pregunta de esta tanda no fue "¿qué se rompe si borro algo vacío?" sino "¿alguien pierde acceso al narrador?".

**Paso 1 — redundancia y accesibilidad confirmadas antes de borrar:**
- `render_jarvis_copilot_page()`: cero lógica propia — solo `init_session()` + `render_clinical_narrator()` de `twin_shell/pages.py`, sobre `st.session_state.twin_shell_organism`. Nada que se pierda al borrarlo.
- El narrador sigue genuinamente alcanzable dentro de Twin OS: `render_clinical_narrator(organism)` se llama incondicionalmente en `main()`, bajo "🧭 Herramientas avanzadas", como el expander "🩺 Narrador clínico (IA real)" — mismo ícono, mismo nombre. Como Digital Twin OS es el hub por defecto (`DEFAULT_HUB`), el costo real para quien lo usaba vía AI Hub es: entrar a Twin OS (ya es el destino inicial) → bajar hasta Herramientas avanzadas → un clic para expandir. Caracterizado con precisión, no inflado.
- **11 referencias colgantes encontradas** (más de las 5 categorías esperadas) — todas revisadas y corregidas: comentario histórico (`main.py:78-81`), entrada de `HUBS`, rama del router, tarjeta y botón de Mission Control (grid de lanzamiento reestructurado de 3+2 a un solo `st.columns(4)`), tarjeta de la home page (renumerada), tres textos que apuntaban a "AI Hub" como destino (Vista IA de Education, disclaimer de AI Analysis, texto de onboarding de Guides), y **dos que no estaban en las categorías obvias**: un bullet fijo del sidebar ("Control universal: 🩺 Narrador Clínico", sin decir dónde — confirmado con el usuario antes de tocarlo, ahora dice explícitamente "→ Digital Twin OS") y el puntero de la pestaña Tutor de Academia Clínica.
- La propia `render_jarvis_copilot_page()`.

**No tocado**: `render_clinical_narrator()`, `twin_shell/pages.py`, `domain/physiology/*` — el narrador dentro de Twin OS quedó exactamente igual, verificado funcionando, no solo compilando.

**Verificación:**
- `HUBS` confirmado sin `"AI Hub"`; `render_jarvis_copilot_page` confirmado ausente del módulo. Quedan 5 hubs: Digital Twin OS, Learning Hub, Clinical Hub, Research Hub, Hardware Hub.
- Los 18 puntos de menú restantes recargados vía `AppTest`: 0 excepciones en todos, incluida la home page y Academia (ninguna con texto residual de "AI Hub").
- **Narrador probado de punta a punta dentro de Twin OS** (no solo que compile): expander presente, botón "Explicar estado actual" clickeado con la llamada real reemplazada por un fake inyectado (mismo patrón de todas las verificaciones de narrador de esta sesión), texto narrado confirmado renderizado sin excepciones.
- `pytest tests/`: 16/16 passed.
- Servidor real HTTP 200.
- Cero cambios en `domain/physiology/*`.

## 2026-07-13 — Consolidación, Tanda 2: eliminación de Simulation Hub (cáscara vacía) — estrategia C, primer paso

Decisión de arquitectura confirmada: consolidación gradual, hub por hub (opción C del informe). Primer paso: el caso de menor riesgo, ya confirmado 100% cáscara por la auditoría de valor.

**Paso 1 — aislamiento confirmado antes de borrar:**
- `render_simulation_lab_page()` no importaba ni usaba `SimulationEngine` en ningún punto — sliders puros sin persistencia. Cero código compartido con el simulador real de Twin OS.
- Corrección menor al brief: la función real de Twin OS es `render_ups_scenario_simulator()`, no `render_simulation_lab()` — esa (sin `_page`) ya había sido eliminada en la Tanda 3, según su propio comentario en `twin_shell/pages.py:790`. No cambia el plan.
- Sin joya escondida — confirmado antes de tocar nada.

**Paso 2 — eliminado:**
- Entrada `"Simulation Hub"` de `HUBS` (`app/main.py`).
- Rama del router (`elif page in HUBS["Simulation Hub"]: render_simulation_lab_page()`).
- La función `render_simulation_lab_page()` completa.
- Para que el borrado fuera limpio de verdad (no solo el router): el botón de Mission Control que apuntaba a `HUBS['Simulation Hub']` (habría lanzado `KeyError` en el primer clic), la tarjeta estática de la home page (con renumeración de las tarjetas siguientes), y la mención de Simulation Hub en el texto de Guides (reemplazada por una referencia a la simulación real de Twin OS).
- **No tocado**: el simulador real de 12 escenarios en Digital Twin OS (`render_ups_scenario_simulator()`), `domain/physiology/*`, y el resto de la plataforma.

**Verificación:**
- `HUBS` confirmado sin la clave `"Simulation Hub"`; `render_simulation_lab_page` confirmado ausente del módulo.
- Los 20 puntos de menú restantes (6 hubs) recargados vía `AppTest`: 0 excepciones en todos, incluida la home page (Mission Control) sin ningún rastro textual de "Simulation Hub".
- Simulador real de Twin OS probado de punta a punta tras el borrado: escenario ejecutado y persistido en el UPS sin excepciones, trayectoria recuperada correctamente en el rerun siguiente.
- `pytest tests/`: 16/16 passed.
- Servidor real HTTP 200.
- Cero cambios en `domain/physiology/*`.

## 2026-07-13 — Consolidación, Tanda 1: erradicación de los 6 restos de IA fingida (Art. I)

Los 6 hallazgos de la auditoría de valor, dos tratamientos según el caso (fachada pura → eliminar; cálculo real mezclado con constantes fingidas → cirugía).

**Grupo A — eliminados:**
1. **Botón "Identificar Patrones Ocultos"** (`app/utils.py`, dentro de `render_scientific_discovery_layer`): tras `time.sleep(1)` siempre imprimía el mismo texto fijo sin leer `signals`. Afectaba a 4 módulos a la vez (EMG, ECG Monitor, Multisensor, HRV) — una sola edición los limpió a todos. El botón vecino "Analizar Entropía y Complejidad" (cálculo real, aunque simple) no se tocó.
2. **Pestañas "Vista IA" de los envoltorios de ECG-12, Respiratory Lab y EEG Neuro Lab** (`app/supermodules/{ecg_12,respiratory_lab,eeg_neuro_lab}/pages.py`): una frase estática cada una ("Modelos de clasificación...", "Modelos de detección de apnea...", "Modelos para detección de crisis..."), cero cálculo. Pestaña eliminada de los 3 (`st.tabs` de 6 a 5 elementos); la pestaña "Clínica" real de cada uno, sin tocar.
3. **"Tutor Cognitivo" de Education** (`app/main.py`, Vista IA): afirmaba "La IA analiza tu progreso..." sin ninguna llamada real. Reemplazado por el mismo tipo de disclaimer honesto ya usado en AI Analysis/Simulation Lab/Hardware Ops desde la Tanda 1, apuntando al Narrador Clínico real.
4. **Pestaña "Progreso" de Academia Clínica** (`app/supermodules/academia/pages.py`): Nivel=5, XP=1250, Misiones=8 y una lista fija de "habilidades desbloqueadas" — literales iguales para cualquier usuario, ya señalados en la auditoría original antes de la Tanda 1 y nunca corregidos. Como todo el contenido de la pestaña era fingido, se eliminó la pestaña completa (`st.tabs` de 6 a 5) en vez de dejarla vacía.
5. **Estado de sensores de Hardware Ops** (`app/main.py`): `'ECG Sensor': 'Conectado'` y `'EEG Array': 'Simulado'` eran literales nunca verificados. Eliminados; se conservó el único chequeo real (`EMG Amplifier`, vía `EMGStreamer is not None`), con una nota explicando que cada laboratorio gestiona su propia conexión de hardware real por separado.

**Grupo B — cirugía, no borrado:**
6. **QTc/AFib de ECG Monitor** (`src/clinical/ecg_interpreter.py`, consumido en `app/main.py`): se conservaron intactos los picos R detectados de la señal real y `bpm`/`sdnn`/`rmssd`/`mean_rr` calculados de ellos, y el heurístico de posible fibrilación auricular (renombrado `possible_afib` → `possible_afib_heuristic`, explícitamente documentado como heurístico simple sobre dos umbrales, no un diagnóstico). Se eliminaron `qrs_duration`/`pr_interval`/`qt_interval` (constantes fijas — 0.1s/0.16s/0.36s — nunca medidas de la señal), el `qtc` calculado a partir de ese QT inventado, y el flag `prolonged_qtc` que dependía de él. El finding `qtc_s` narrado al usuario también se quitó. Documentada como opción futura, sin implementar: medir QRS/PR/QT reales requeriría detectar Q/S/fin de onda T, no solo el pico R — es un detector nuevo, no una limpieza, fuera del alcance de esta tanda.

**Verificación:**
- Unitaria: `interpret_ecg()` verificado directamente — `intervals` ya no contiene `qtc`/`qrs_duration`/`pr_interval`/`qt_interval`; `flags` ya no contiene `prolonged_qtc`, sí contiene `possible_afib_heuristic`; la descripción ya no menciona QTc.
- Los 21 puntos de menú (17 módulos) recargados vía `AppTest`: 0 excepciones en todos, incluidos los 7 módulos tocados directamente (EMG, ECG Monitor, Multisensor, HRV, ECG-12, Respiratory Lab, EEG Neuro Lab) y los 3 restantes (Education, Academia, Hardware Ops).
- Confirmado sin texto residual: ni "Identificar Patrones Ocultos", ni "QTc estimado"/"qtc_s"/"QTc largo", ni "ECG Sensor"/"EEG Array", ni "IA analiza tu progreso", ni "XP Total" en ningún módulo.
- `pytest tests/`: 16/16 passed.
- Servidor real HTTP 200.
- Modo Caso Clínico Interactivo (Twin OS) y Joya 1 (ECG Monitor: MIT-BIH/PTB-XL/ESP32/notebook) re-verificados de punta a punta, sin regresión.
- Cero cambios en `domain/physiology/state/*`, `domain/physiology/narrator/*`.

## 2026-07-13 — Eliminación de pages_legacy, Movimiento 2/2: borrado (irreversible, confirmado por el usuario)

Con el Movimiento 1 confirmado (plataforma viva sin que nada tocara `pages_legacy` en producción, aunque los archivos seguían en disco), se ejecuta el borrado real.

**Borrado:**
- `app/pages_legacy/` completo — los 9 archivos que quedaban (`2_🔗_Multisensor.py`, `3_🎓_Education.py`, `4_👥_Patients.py`, `5_🤖_AI_Analysis.py`, `6_📋_ECG-12-Derivaciones.py`, `7_💨_Respiratory-Lab.py`, `8_🧠_EEG-Neuro-Lab.py`, `9_🦾_EMG_Muscle_Lab.py`, `10_📚_Guides.py`) y el directorio mismo.
- Los 6 paquetes de supermódulo confirmados huérfanos, completos (`pages.py` + `__init__.py` cada uno — los "12 envoltorios" del brief): `app/supermodules/education/`, `ai_analysis/`, `emg_muscle_lab/`, `guides/`, `multisensor/`, `patients/`.
- Con esto muere para siempre la IA fingida durmiente de `5_🤖_AI_Analysis.py` (confirmada no-joya, ver entrada del Movimiento 1) y la violación Art. I del ML de `4_👥_Patients.py` alimentado con datos hardcodeados (ya rescatado correctamente en Twin OS desde la Tanda 4, Pieza 1).
- **No se tocó**: `ecg_12/`, `respiratory_lab/`, `eeg_neuro_lab/` (ya reubicados a `page_content.py` propio en el Movimiento 1 — siguen intactos, ahora son la única copia que existe), ni `ecg_monitor/`, `academia/`, `twin_shell/` (nunca dependieron de `pages_legacy`). `app/supermodules/` queda con 6 paquetes: `academia`, `ecg_12`, `ecg_monitor`, `eeg_neuro_lab`, `respiratory_lab`, `twin_shell`.
- **`app/utils.py` y `app/utils/` — verificados intactos**: ni un archivo tocado (confirmado con `Get-Item`: mismas fechas de modificación que antes de toda esta tanda) y funcionalmente operativos (`import app.utils`/`import app.supermodules` verificados en vivo tras el borrado).

**Verificación (post-borrado, con `pages_legacy` ya inexistente en disco):**
- Los 21 puntos de menú (17 módulos distintos) recargados uno por uno vía `AppTest`: 0 excepciones en todos.
- **ECG-12, Respiratory Lab y EEG Neuro Lab confirmados vivos desde su única copia actual** (`page_content.py` dentro de su propio supermódulo) — ya no hay ningún `pages_legacy` al que caer de respaldo; si la reubicación del Movimiento 1 hubiera tenido cualquier error, esto lo habría revelado. Contenido real renderizado (6800–10548 caracteres de markdown por página), 0 excepciones. ECG-12 verificado además con su interacción completa (generar ECG de 12 derivaciones → gráfico + narrativa presentes).
- Modo Caso Clínico Interactivo (Twin OS) y Joya 1 (ECG Monitor: MIT-BIH/PTB-XL/ESP32/notebook) re-verificados de punta a punta, sin regresión.
- `pytest tests/`: 16/16 passed.
- Servidor real (`streamlit run`): HTTP 200.
- Cero cambios en `domain/physiology/state/*` y `domain/physiology/narrator/*` en las dos tandas de eliminación.

**Resultado**: el Hub (`app/main.py`) queda como navegación única de la plataforma. No existe ningún segundo sistema de navegación, ni código huérfano alcanzable solo por una puerta distinta al menú. Quedan pendientes, como tandas separadas y ya identificadas: los duplicados de menú de Learning Hub y Research Hub, y la colisión de `session_state['emg_streamer']` entre la implementación EMG del Hub y... — nota: esa colisión en particular ya no aplica, porque la única implementación EMG que queda es la del Hub (la de `pages_legacy` se borró en esta misma tanda). Sigue pendiente solo lo de Learning/Research.

## 2026-07-13 — Eliminación de pages_legacy, Movimiento 1/2: desconectar + reubicar + verificar (sin borrar nada aún)

Joya 2 (SHAP/LIME de AI Analysis) se auditó y se descartó como **no-joya**: `pages_legacy/5_🤖_AI_Analysis.py` llama exactamente a `ECGAnalyzer.detect_clinical_pattern()` + `compute_psd`/`extract_features` + `generate_shap_lime_report()` — los mismos tres componentes, en el mismo orden, que `domain/physiology/ml/ecg_classification.py` (Tanda 4, Pieza 2) ya usa en Twin OS. Sin cálculo nuevo; lo único distinto es cosmético (un selector de "3 modelos" que solo relabela el mismo `confidence`, un informe en texto y un gráfico de barras del mismo `importance` que Twin OS ya calcula pero no dibuja) y su manejo de ESP32 usa `is_connected()` en vez de `is_hardware_present()` — más débil que la disciplina ya vigente. No se portó nada.

**Corrección de plan a mitad de tanda**: el usuario señaló, correctamente, que "desconectar" a ciegas los 12 envoltorios rompería 3 módulos que SÍ están activos hoy — `ecg_12`, `respiratory_lab` y `eeg_neuro_lab` invocan `pages_legacy` en vivo (reconectados el 2026-07-03 porque esa versión era la real). Antes de tocar nada se preguntó y se confirmó: para estos 3, **reubicar el contenido tal cual** en vez de desconectar.

**Movimiento 1 — reubicar + verificar (`pages_legacy/` sigue en disco, nada borrado todavía):**
- Copiados byte-a-byte (sin cambiar una línea de lógica): `pages_legacy/6_📋_ECG-12-Derivaciones.py` → `app/supermodules/ecg_12/page_content.py`; `pages_legacy/7_💨_Respiratory-Lab.py` → `app/supermodules/respiratory_lab/page_content.py`; `pages_legacy/8_🧠_EEG-Neuro-Lab.py` → `app/supermodules/eeg_neuro_lab/page_content.py`.
- Cada `MODULE_EMOJI` en `pages.py` de esos 3 supermódulos ahora apunta a su `page_content.py` local, no a `pages_legacy`.
- Único ajuste real hecho a la lógica portada: las 3 copias calculaban `PROJECT_ROOT`/`sys.path` contando niveles de directorio fijos (`../..`, 3× `dirname`) asumiendo su profundidad original (`app/pages_legacy/`, 2 niveles bajo la raíz). En su nueva ubicación (`app/supermodules/<módulo>/`, 3 niveles) esos cálculos apuntaban un nivel de más arriba (`app/` en vez de la raíz del repo). Se corrigió el conteo de niveles en los 3 archivos — no es un cambio de comportamiento, es preservar el comportamiento original ante la nueva profundidad.
- Los 6 módulos genuinamente huérfanos (Education, Guides, AI Analysis, Patients, Multisensor, EMG Muscle Lab) no requirieron ningún cambio — el router de `app/main.py` ya nunca los invoca; "desconectar" ahí ya era cierto desde antes de esta tanda.
- `pages_legacy/` (9 archivos) sigue intacto en disco — ya sin nada irrepetible adentro, pero sin borrar todavía.

**Verificación:**
- Los 21 puntos de menú (17 módulos distintos) cargados uno por uno vía `AppTest`: 0 excepciones en todos.
- ECG-12, Respiratory Lab y EEG Neuro Lab probados específicamente desde su nueva ubicación — contenido real renderizado, 0 excepciones; ECG-12 verificado además con la interacción de generar un ECG de 12 derivaciones (gráfico + narrativa presentes, igual que antes de mover el archivo).
- Modo Caso Clínico Interactivo y la Joya 1 (ECG Monitor: MIT-BIH/PTB-XL/ESP32/notebook) re-verificados sin regresión.
- `pytest tests/`: 16/16 passed.
- Servidor real HTTP 200.
- **Mina confirmada intacta**: `app/utils.py` y `app/utils/` (`__init__.py`, `data_generator.py`, `ui_helpers.py`) — ninguno modificado (fechas de último cambio anteriores a esta sesión, confirmado con `Get-Item`).
- `pages_legacy/`: 9 archivos, todavía en disco, sin tocar.

**Esperando confirmación del usuario antes del Movimiento 2 (borrado de `pages_legacy/` y de los 12 envoltorios ya desconectados/reubicados).**

## 2026-07-13 — Tanda de rescate, Joya 1/3: activos reales del ECG Monitor huérfano (`app/supermodules/ecg_monitor/pages.py`)

Decisión de arquitectura confirmada por el usuario: el Hub (`app/main.py`) es la navegación única; `pages_legacy`/sus envoltorios de supermódulo se rescatan y luego se eliminan — nunca al revés. Primer rescate de 3, el de menor riesgo de contaminación (activos/datos, no lógica mezclada con IA fingida).

**Paso 1 — inventario (antes de mover nada):**
- **MIT-BIH**: el loader (`load_mitbih_record`/`get_mitbih_records`) YA vive compartido en `signals/loaders/wfdb_loader.py` e YA estaba importado en la página viva del Hub vía `safe_import_ecg_modules()` — lo único que faltaba era la opción de UI para alcanzarlo. No es una joya nueva, es un cableado faltante.
- **PTB-XL** (`load_ptbxl_record`/`get_ptbxl_records`): código único, solo existía en el huérfano. Real (usa `wfdb`, confirmado instalado — v4.3.1), pero depende de red a PhysioNet en cada carga; no hay ningún dataset local empaquetado (`datasets/` está vacío, confirmado antes del rescate).
- **Exportación CSV + notebook reproducible** (`_save_signal_csv`/`_create_reproducible_notebook`): código único, autocontenido, real.
- **Ingesta ESP32 en vivo para ECG Monitor**: código único (usa `src.signals.signal_sources.ESP32SignalSource`, la misma clase real de la Tanda 4 Pieza 2), real — la página viva del Hub no tenía ningún soporte de hardware para ECG Monitor.
- Descartado sin rescatar: la pestaña "Gemelo Digital" del huérfano — ya identificada como decorativa/desconectada, es la razón por la que la página viva la eliminó a propósito.

**Paso 2 — rescate, todo en `app/main.py::render_ecg_monitor_page()`, ningún archivo nuevo:**
- Radio `ECG Source` pasa de 3 a 6 opciones: se agregan "Base de datos MIT-BIH", "Base de datos PTB-XL", "Hardware ESP32 en vivo".
- `_ecg_get_ptbxl_records()`/`_ecg_load_ptbxl_record()` portados tal cual (mismo fallback honesto a demo sintético ante 404/sin red, mismo patrón que ya usa MIT-BIH).
- `_ecg_export_signal_csv()`/`_ecg_create_reproducible_notebook()` portados tal cual, cableados a un nuevo botón "📓 Generar notebook reproducible" en la Vista Investigación — usa la señal/fs/metadata realmente cargada arriba, cualquiera sea la fuente activa.
- ESP32: disciplina de procedencia de la Tanda 4 aplicada sin excepción — `is_hardware_present()` decide SENSOR_REAL vs SIMULACIÓN, nunca `is_connected()`/`.connected` (que siguen en `True` bajo `simulate_if_missing`). Badge visible (`st.sidebar.success`/`warning`) en cada caso.
- `session_state` namespaced (`ecg_monitor_esp32_source`, `_ecg_monitor_mitbih_cache`, `_ecg_monitor_ptbxl_cache`) — deliberadamente distinto de `esp32_source`/`emg_streamer` sin espacio de nombres que ya vive en el huérfano, para no repetir la colisión que el informe de navegación señaló para EMG.
- Nada de `pages_legacy`/`app/supermodules/ecg_monitor/` se borró todavía — sigue existiendo, ahora ya sin nada irrepetible adentro.

**Verificación:**
- `AppTest`: las 6 fuentes cargan con 0 excepciones. MIT-BIH probado con descarga real desde PhysioNet — trajo el registro 100 real (650 000 muestras, fs=360, anotaciones clínicas reales: "69 M 1085 1629 x1, Aldomet, Inderal").
- **Hallazgo transparente, no oculto**: PTB-XL cae siempre al fallback demo en este entorno — confirmado que es un 404 real de PhysioNet (`wfdb.rdrecord('10038', pn_dir='ptbxl')` → `NetFileNotFoundError`), porque el layout real de PTB-XL en PhysioNet es anidado (`records100/00000/...`), no una lista plana de IDs como asumía el código original. Es un bug preexistente del código que se rescató tal cual (la instrucción fue no arreglar lógica no pedida) — el fallback en sí funciona exactamente como debe (nunca presenta el demo como dato real). Queda pendiente de una decisión aparte si se quiere corregir el formato de ruta.
- Prueba de honestidad ESP32: sin hardware real conectado, el badge mostrado es "🟡 PROCEDENCIA: SIMULACIÓN" — "SENSOR_REAL" confirmado ausente de cualquier mensaje de éxito.
- `pytest tests/`: 16/16 passed (mismos 3 archivos preexistentes excluidos de siempre).
- Servidor real HTTP 200. Sin regresión en ECG-12 ni en el resto de Clinical Hub.
- Cero cambios en `domain/physiology/state/*`, `domain/physiology/narrator/*`, y en las otras dos joyas (SHAP/LIME de AI Analysis, ML de Patient Pipeline) — quedan para tandas separadas, como se pidió.

## 2026-07-12 — Tanda: corrección de bugs visibles (Grupo 1) — 3 arreglos quirúrgicos, cero reestructuración

**Bug 2 — nombres de variables internas filtrados al feedback del narrador (el más visible, corregido primero a pedido del usuario).** Causa raíz: en `render_clinical_case_mode` (`app/supermodules/twin_shell/pages.py`), los dos `Finding` sintéticos usados para pedirle al narrador que evalúe la hipótesis del estudiante tenían como `name` los identificadores de variable literales (`"hipotesis_del_estudiante"`, `"diagnostico_correcto_verdad_de_referencia"`) en vez de un nombre citable legible. El system prompt de `domain/physiology/narrator/findings.py` (sin tocar) tiene la regla "cada afirmación clínica debe citar el nombre exacto de una métrica del contexto" — regla correcta para métricas reales (`heart_rate`, etc.); el bug era que le dábamos nombres de variable donde debía ir texto legible, y el narrador los citaba tal como se le pidió. Arreglo: esos dos `name` pasan a ser `"Diagnóstico elegido por el estudiante"` y `"Diagnóstico correcto (verdad de referencia del caso)"`. Cero cambios en `narrator/*`.

**Bug 1 — evento `hypoxia_spo2_low` (u otro) repetido varias veces idénticas en el panel del caso clínico.** Causa raíz: no es un fallo, es una consecuencia esperada de un diseño ya existente de Fase 1.1 — `domain/physiology/state/builder.py::_detect_events` (sin tocar) detecta eventos por snapshot, no una vez por condición sostenida ("el evento se detecta en el momento en que el UPS se construye... no se re-deriva más tarde inspeccionando la serie"). `run_rich_scenario` persiste 6 horizontes por escenario; cuando una condición se mantiene igual en varios horizontes consecutivos, cada uno genera honestamente el mismo evento. Correcto a nivel de datos, redundante a nivel de presentación. Arreglo: nueva función `_dedupe_events()` en `pages.py` (colapsa por `event_type`+`severity`+`description`, preserva orden), aplicada en los dos puntos donde mi propio código consume eventos — la lista mostrada al estudiante y la lista convertida a `Finding` para el narrador. Cero cambios en `domain/physiology/state/*` ni `narrator/*`. Nota aparte (no corregida, fuera de alcance de este bug): `build_context()` limita a los últimos 10 eventos crudos antes de deduplicar, así que en escenarios con muchos eventos distintos el narrador puede ver uno o dos menos que el panel visual — comportamiento preexistente de esa función.

**Bug 3 — entradas de menú duplicadas en Clinical Hub (solo el síntoma visible, arquitectura intacta).** Causa raíz: `HUBS["Clinical Hub"]` (`app/main.py`) tenía, para cada módulo, dos entradas — el nombre legible con emoji y un segundo nombre "interno" sin emoji (p.ej. `"📊 ECG Monitor"` + `"ECG_Monitor"`) — que `st.sidebar.selectbox('Selecciona un módulo', HUBS[...])` renderizaba como dos filas separadas. El patrón no estaba limitado a los 3 ejemplos reportados (ECG Monitor, Multisensor, Respiratory Lab): los 7 módulos del hub excepto Biomarkers Lab lo tenían (también ECG-12-Derivaciones, EEG Neuro Lab, EMG Muscle Lab, HRV Analysis). Confirmé antes de tocar nada que el ruteo en `render_page_content()` empareja por substring (`"ECG Monitor" in page`, `"Multisensor" in page`, etc.) — el nombre con emoji por sí solo ya satisface cada condición, así que quitar los nombres internos es puramente cosmético, no requiere tocar el router ni la arquitectura de hubs. Arreglo: se eliminaron las 7 entradas internas duplicadas de `HUBS["Clinical Hub"]`, quedando una sola entrada legible por módulo (8 en total, antes 15). Nota aparte (no tocada, fuera de alcance — Bug 3 se reportó específicamente para Clinical Hub): `Learning Hub` tiene el mismo patrón en 2 de sus 3 módulos (`"🎓 Education"`/`"Education"`, `"🏫 Academia Clinica"`/`"Academia_Clinica"`) — posible candidato para una futura tanda si se confirma.

**Verificación** (un bug a la vez, cada uno confirmado por el usuario antes de seguir con el siguiente):
- Bug 2: contexto enviado al narrador verificado sin ningún identificador con guión bajo en `Finding.name`/`Finding.value` para las dos entradas sintéticas (verificado con un narrador fake inyectado, sin `ANTHROPIC_API_KEY` real disponible en este entorno).
- Bug 1: ciclo completo corrido 6 veces contra distintos escenarios; en los casos con eventos sostenidos (sepsis, arritmia) se confirmaron 0 duplicados exactos tanto en el panel como en lo enviado al narrador.
- Bug 3: `HUBS["Clinical Hub"]` verificado con 8 entradas distintas, ninguna duplicada; los 8 módulos cargados vía `AppTest` uno por uno, 0 excepciones en cada uno.
- `pytest tests/` (excluyendo los mismos 3 archivos con errores de colección preexistentes y no relacionados de siempre): 16/16 passed después de cada uno de los 3 arreglos.
- Servidor real (`streamlit run`) HTTP 200 después de cada uno de los 3 arreglos.
- Regresión de ECG-12 y del modo Caso Clínico (Bugs 1+2) re-verificada tras el cambio de Bug 3 en `app/main.py`.
- Cero cambios en `domain/physiology/state/*` y `domain/physiology/narrator/*` en toda la tanda.

## 2026-07-12 — Modo Caso Clínico Interactivo v1: diagnóstico por opción múltiple (construcción nueva, alcance mínimo)

Nueva capacidad, no un fix: convierte al estudiante de espectador en clínico dentro del Twin OS. Reutiliza el 100% de lo existente — no se creó ningún motor nuevo:

- **`app/supermodules/twin_shell/pages.py`** — nueva función `render_clinical_case_mode(organism)`, expuesta como expander "🎓 Caso clínico interactivo (diagnóstico ciego) — v1" en "Herramientas avanzadas", justo después del narrador clínico. Un solo ciclo completo:
  1. **Caso ciego**: `random.choice` sobre los 12 escenarios de `RICH_SCENARIO_LABELS` (mismos de la Tanda 3), evolucionado con `run_rich_scenario(..., start_from_current_state=False)` — el mismo puente que ya usa el simulador de escenarios, sin ninguna función nueva de simulación. Se persiste en un paciente efímero nuevo (`create_patient(display_name="Caso clínico interactivo")` — genérico a propósito, nunca el nombre del escenario) y con un `DigitalTwinOrganism()` desechable propio (no el organismo de la sesión), para que generar el caso oculto no salpique el encabezado ambiental ni el resto de paneles del Twin OS que siguen leyendo al paciente/organismo continuo de siempre.
  2. **Hipótesis**: `st.radio` con 4 opciones (`_diagnostic_options()`) — la correcta + 3 distractores reales tomados por `random.sample` de los otros 11 escenarios (nunca inventados).
  3. **Evaluación con fundamento**: al confirmar, compara la elección contra `hidden_scenario` (verdad objetiva — el escenario que este código efectivamente cargó, no una opinión del modelo) y llama al narrador real reutilizando `stream_findings_narration`/`Finding`/`FindingsContext` de `domain/physiology/narrator/findings.py` **tal cual, sin tocar `narrator/*`**: los `Finding` son los descriptores/eventos reales de `build_context()` (mismo patrón de anclaje que Fase 1.3) más dos entradas adicionales — `hipotesis_del_estudiante` (lo que eligió) y `diagnostico_correcto_verdad_de_referencia` (la verdad ya decidida por el código, no por el modelo) — pidiéndole al narrador que explique el ajuste/desajuste citando esos mismos datos. El cuerpo (`render_ups_body`) ya muestra el sistema afectado, sin cambios.
  4. **Revelar y otro caso**: tras confirmar se muestra `RICH_SCENARIO_LABELS[hidden]` (✅/❌) + el feedback del narrador; botón "➡️ Otro caso" limpia las claves `clinical_case_*` de `session_state` y reinicia el ciclo.

**Ocultamiento verificado, no solo asumido**: `get_latest_state`/`get_events`/`build_context()` no exponen el escenario que generó el estado (no es un campo del UPS — confirmado leyendo `schema.py`/`context.py`), y `source_detail` (que sí contiene el nombre del escenario, p.ej. `escenario_rico:sepsis:...`) nunca se renderiza en ningún panel del Twin OS (confirmado por grep). El paciente efímero usa un `display_name` genérico para no filtrarse por ningún listado de pacientes de otra página.

**Alcance cerrado respetado**: sin texto libre (el narrador solo recibe datos + las dos hipótesis, no una pregunta abierta del estudiante), sin interpretación/predicción nueva, sin puntuación/rachas/persistencia de progreso, sin UI nueva ambiciosa (vive en un expander más del Twin OS), cero cambios en `domain/physiology/state/*` y `narrator/*`.

**Verificación** (sin `ANTHROPIC_API_KEY` real disponible en este entorno de desarrollo — se sustituyó `stream_findings_narration`/`narrator_is_configured` por fakes inyectados sobre el módulo ya importado, para probar el resto de la mecánica — generación, ocultamiento, radio de 4 opciones, revelación, reset — de punta a punta vía `AppTest`):
- Ciclo completo verificado dos veces (rama incorrecta y rama correcta): caso generado sin excepciones → el label del escenario oculto **no** aparece en ningún `markdown`/`caption` antes de responder → tras confirmar, el narrador recibe descriptores reales (`heart_rate`, `hrv`, `respiratory_rate`, `spo2`, más los derivados del organismo) y eventos reales, además de `hipotesis_del_estudiante`/`diagnostico_correcto_verdad_de_referencia` → mensaje ✅/❌ + reveal + feedback presentes → "Otro caso" limpia el estado.
- `pytest tests/` (excluyendo 3 archivos con errores de colección preexistentes y no relacionados — `test_api.py`, `test_arrhythmia_classifier.py`, `test_reasoning_engine.py`, que fallan por imports a símbolos que no existen en `biomedical/*`, sin tocar por esta tanda): 16/16 passed, igual que antes.
- Regresión de ECG-12 (Tanda 4, Pieza 2) re-verificada: 0 excepciones, gráfico y narrativa presentes — el nuevo bloque de imports no rompió nada.
- Servidor real (`streamlit run`, puerto 8796): HTTP 200.
- Cero cambios en `domain/physiology/state/*` y `domain/physiology/narrator/*`.

**Pendiente de tu confirmación antes de generalizar** (mostrar los 12 escenarios de forma más pulida, historial de casos, dificultad, etc.) — tal como se pidió, esto es solo el ciclo mínimo de un caso de principio a fin.

## 2026-07-04 — Tanda 4, Pieza 2: clasificador de ECG real absorbido al Twin OS — punto de máximo cuidado

Objetivo: `detect_clinical_pattern()` (`clinical/ecg_analyzer.py`) + SHAP/LIME real (`src/interpretability.py`), integrados al Twin OS con procedencia veraz — regla absoluta: ninguna señal de ECG cruda entra al clasificador sin procedencia que refleje lo que realmente ocurrió. Núcleo (`domain/physiology/state/*`, `narrator/*`) sin tocar.

### Bug real encontrado y corregido: el generador de ECG nunca dibujaba el QRS

Antes de poder demostrar el criterio de aceptación ("sin evento, clasifica sinusal normal"), la primera prueba dio `PVC` para una señal de 75 bpm perfectamente normal. Investigado hasta la causa raíz: `TwelveLeadEcgGenerator._generate_pqrst()` (`src/signals/ecg/twelve_lead_generator.py`) tenía `signal[qrs_mask][q_mask] -= ...` / `[r_mask] += ...` / `[s_mask] -= ...` — indexado encadenado de NumPy que modifica una copia descartada, nunca `signal` real. El complejo QRS completo (Q, R, S) **nunca se renderizaba** — todo consumidor de este generador (incluida la página ECG-12, ya construida esta sesión) recibía una onda con solo P y T. Corregido construyendo el tramo QRS aparte y asignándolo de una sola vez (`signal[qrs_mask] += qrs_values`). Verificado que esto **no es una regresión de ECG-12**: su interpretación automática mejoró (antes decía "Unable to determine rhythm", ahora "Sinus rhythm, HR 78 bpm (normal)" correctamente).

Con el QRS ya renderizado apareció un segundo problema (integración, no bug): la onda T de este generador (amplitud 0.3 por defecto) cruzaba el mismo umbral de detección de picos que usa `ECGAnalyzer.detect_r_peaks()` (media + 0.3·desviación estándar), duplicando la FC detectada. Ajustado en mi código llamador (no en el generador compartido): `EcgParameters(t_amplitude=0.1)` — una amplitud de onda T fisiológicamente normal, no un valor inventado, elegida para que estos dos componentes reales (nunca antes probados juntos) sean compatibles. Verificado en el rango 40-180 bpm: FC detectada = FC real en todos los casos.

### Modo (A) — señal sintética desde el UPS (`domain/physiology/ml/ecg_signal_source.py`, nuevo)

`build_synthetic_ecg_from_ups(session, patient_id)`: lee `heart_rate` real del snapshot más reciente del UPS, genera la onda con `TwelveLeadEcgGenerator` (no `generate_demo_ecg_signal` — confirmado que esa función calcula `hr_rad` desde `heart_rate` pero nunca lo aplica al espaciado de las ondas, un bug distinto y ya existente que no se tocó por estar fuera de alcance). `None` si el UPS no tiene `heart_rate` todavía — nada de FC por defecto inventada. No fabrica patrones de arritmia: la FC real, cuando es extrema, ya produce un trazado taquicárdico/bradicárdico por sí sola vía el espaciado RR correcto — no hace falta un flag de "patrón" aparte que fabricaría una morfología que el UPS no detectó.

### Modo (B) — hardware real, con la prueba de honestidad como pieza central

`ESP32SignalSource` (`src/signals/signal_sources.py`) ganó `is_hardware_present()`: a diferencia de `is_connected()`/`.connected` (que siguen siendo `True` incluso bajo `simulate_if_missing` sin ningún puerto serial real — confirmado leyendo `hardware/esp32_stream.py`), este nuevo método comprueba directamente `serial_conn is not None`, la única señal honesta de una conexión física real. La UI (`render_ecg_classifier_panel`) decide `Provenance.SENSOR_REAL` vs `SIMULACIÓN` exclusivamente con este método, nunca con la intención de conectar.

### `domain/physiology/ml/ecg_classification.py` (nuevo) — clasificación independiente de la fuente

`classify_ecg_signal(signal, fs)`: `ECGAnalyzer(fs=fs).detect_clinical_pattern(signal)` + `detect_r_peaks()` para RR reales → `src.feature_extraction.compute_psd`/`extract_features` (BPM/SDNN/RMSSD/LF_HF/Skewness/Kurtosis reales) → `src.interpretability.generate_shap_lime_report()`. Cero `np.random`, cero resultado fijo. Si hay menos de 5 picos R, se omite la explicabilidad con un aviso honesto en vez de forzarla.

### `render_ecg_classifier_panel()` (Twin OS) — nuevo panel, junto a la Pieza 1

Radio para elegir modo A/B. Badge explícito **"PROCEDENCIA: SIMULACIÓN"** o **"PROCEDENCIA: SENSOR_REAL"** (nunca ambiguo), clasificación etiquetada **"(DERIVADO)"**, hallazgos, y explicabilidad SHAP/LIME en pestañas.

### Verificación

**Prueba de honestidad (obligatoria)**: `AppTest` con modo B sin ningún ESP32 real conectado (el caso de este entorno de desarrollo) — el software cae a simulación (confirmado en el log: "No se encontró puerto serial compatible... Entrando en modo simulación"), y el badge mostrado es **"PROCEDENCIA: SIMULACIÓN"** — `"PROCEDENCIA: SENSOR_REAL"` confirmado ausente. Modo A: escenario HEALTHY → "Normal Sinus Rhythm" con FC real reflejada; escenario ARRHYTHMIA → cuando el evento `ARRHYTHMIA_RISK_HR_EXTREME` dispara (la aleatoriedad ya existente de `SimulationEngine`, `hr = 110 + np.random.normal(0,30)`, no siempre lo cruza en una corrida corta — confirmado con corridas repetidas), el clasificador deja de decir "Normal Sinus Rhythm"; script standalone con FC forzada a 160 bpm confirma detección fiel (features del clasificador reportan ~160, no un valor fijo). `pytest tests/` 16/16. Escenarios de la Tanda 3 y Pieza 1 sin regresión (mismos colores/eventos). Servidor real HTTP 200, logs limpios. Cero cambios en `domain/physiology/state/*` ni `narrator/*`.

**Esperando confirmación antes de cerrar la tanda**, tal como se pidió.

## 2026-07-04 — Tanda 4, Pieza 1: scoring de riesgo/anomalías real absorbido al Twin OS, alimentado por el UPS

Objetivo: traer `PatientRiskPredictor`/`AnomalyDetector` (`src/ai/patient_analytics.py`) — antes solo alcanzables en `app/pages_legacy/4_👥_Patients.py` (huérfano, archivado) con datos de paciente hardcodeados — al Twin OS, alimentados por el UPS real. Núcleo (`domain/physiology/state/*`, `narrator/*`) sin tocar.

### `src/ai/patient_analytics.py` — adaptado, no reescrito

`PatientRiskPredictor.calculate_risk_score()` tenía `age`/`heart_rate`/`systolic_bp`/`diastolic_bp`/`hrv_sdnn` como argumentos obligatorios — el UPS no puede proveerlos todos. Se hicieron opcionales (`Optional[...] = None`); cuando un factor no tiene fuente real, se **omite** del score en vez de rellenarse con un valor típico, y el peso total se renormaliza sobre los factores realmente disponibles (para que `total_risk` siga en escala 0-1 comparable). El resultado ahora incluye `factors_used`/`factors_omitted` explícitos. `_get_recommendations()` se ajustó de indexado directo a `.get(key, 0.0)` para no fallar con factores ausentes. Caso 100% poblado (como antes): mismo resultado exacto, cero regresión.

### Nuevo: `domain/physiology/ml/risk_context.py`

Mismo patrón que `narrator/context.py::build_context()`: `build_risk_features(session, patient_id)` lee el snapshot más reciente del UPS y arma un `RiskFeatures` de solo datos reales:
- `heart_rate`/`hrv_sdnn`: descriptores reales del UPS (`None` si el organismo aún no tiene esa señal).
- `ecg_pattern`: derivado de eventos reales — `'arrhythmia'` si hay un `EventType.ARRHYTHMIA_RISK_HR_EXTREME` activo, `'normal'` si no (una lectura real del UPS, no un placeholder).
- `trend_data`: historial real de `heart_rate` vía `get_value_history()` (hasta 7 puntos).
- `age`/`systolic_bp`/`diastolic_bp`: **siempre `None`** — el UPS (Fase 1.1) no modela demografía ni presión arterial en absoluto. Dejados explícitos en el dataclass, no omitidos por descuido.

Devuelve `None` si el paciente no tiene ningún snapshot todavía — igual que `build_context()`, sin fabricar un vector de features de la nada.

### Decisión reportada (no inventé nada, mapeo explícito): edad y presión arterial

- **Presión arterial**: no existe ninguna fuente real en toda la app (ni UPS, ni sidebar, ni otro descriptor) — el factor queda **siempre omitido**, con un caption explícito en la UI.
- **Edad**: sí existe un dato real en la app — el campo "Edad" de la Ficha Clínica Global del sidebar (`st.session_state.pac_edad`), real porque el usuario lo escribe, aunque no es un dato del UPS. Se agregó un checkbox ("Incluir edad de la Ficha Clínica Global") **desactivado por defecto** — el usuario decide explícitamente si mezclar esa fuente, en vez de que el código la incluya silenciosamente.

### `app/supermodules/twin_shell/pages.py::render_ml_risk_panel()` — nuevo panel, no página nueva

Vive junto al resto de "🧭 Herramientas avanzadas" del Twin OS (entre razonamiento causal y la evaluación de riesgo ya existente de `PredictionEngine` — motor real distinto, sin tocar). Muestra: score de riesgo con etiqueta explícita **"RIESGO CARDIOVASCULAR (DERIVADO)"** (provenance correcta — un score calculado es derivado, nunca sensor_real, igual que `health_score` desde la Fase 1.1), factores usados/omitidos, recomendaciones reales del propio `PatientRiskPredictor`, y detección de anomalías (Z-score) sobre el historial real de FC del UPS — con aviso honesto ("se necesitan al menos 3 snapshots") cuando no hay suficiente historial, en vez de forzar un resultado.

### Verificación

Script standalone: paciente sin snapshot → `None` (sin fabricar); estado normal → `ecg_pattern='normal'`, age/BP correctamente omitidos, riesgo bajo; pico de FC → `ecg_pattern` cambia a `'arrhythmia'` (derivado del evento real), riesgo sube a 73.3%. `AppTest`: panel visible, 0 excepciones al cargar y tras correr un escenario de la Tanda 3, "Factores omitidos: age, blood_pressure" confirmado en pantalla. `pytest tests/` 16/16. Escenarios de la Tanda 3 (Sepsis/Apnea/Arritmia) sin regresión — misma severidad de eventos, mismos colores del cuerpo (la variación menor observada en Apnea es aleatoriedad ya existente de `SimulationEngine`, no introducida por este cambio). Servidor real HTTP 200, logs limpios. Cero cambios en `domain/physiology/state/*` ni `narrator/*`.

**Compuerta**: esperando confirmación antes de tocar la Pieza 2 (clasificador de ECG).

## 2026-07-04 — Tanda 3: los 12 escenarios reales unificados dentro del pipeline del UPS (toca el núcleo, máxima cautela)

Objetivo: que `SimulationEngine` (12 escenarios, `app/engines/simulation_engine.py`) alimente el mismo pipeline del UPS que los 3 escenarios de la Fase 1.2, para que el narrador (1.3) y el cuerpo visual (1.4) funcionen con los 12. Resultado: **un solo simulador conectado al UPS**, no dos.

### Regla rectora respetada: el núcleo no se reescribió

Cero cambios en `domain/physiology/state/*` (schema, builder, repository, db), en `domain/physiology/narrator/*`, en `render_clinical_narrator()`, en `render_ups_body()`/`render_synced_digital_twin_body()`, ni en `domain/physiology/scenarios/{definitions,engine,__init__}.py` — los 3 escenarios originales de la Fase 1.2 y su código siguen exactamente iguales (`tests/test_scenario_simulator.py` 4/4 sin tocar una línea de producción).

### Nuevo: `domain/physiology/scenarios/rich_engine.py`

Puente nuevo, no una reescritura: `run_rich_scenario()` reutiliza exactamente `organism.update_from_sensors()`, `from_digital_twin_organism()` y `save_state()` — las mismas funciones ya verificadas que usa `run_scenario()` — solo cambia de dónde vienen los valores de entrada (los 6 horizontes temporales de un `SimulationTimestep` de `SimulationEngine`, en vez de interpolación de waypoints). Cada valor persistido sigue llevando `Provenance.SIMULACION` y su `confidence` exactamente como antes — verificado explícitamente (ver Verificación). `SimulationEngine()` se instancia nueva en cada corrida (cautela de la auditoría: evita el estado residual de `self.timeline`/`self.current_scenario` entre escenarios).

### Toggle "estado actual" vs. "basal" — decisión de diseño resuelta sin tocar el narrador

El narrador necesita saber qué modo se usó (evolución antes→ahora vs. cuadro típico sin "antes" inventado) — pero `domain/physiology/narrator/context.py` no se modificó. Solución: el modo se resuelve enteramente por **qué `patient_id` se usa**, no por un campo nuevo en el esquema:
- **Estado actual**: la corrida usa el `patient_id` continuo de la sesión (`twin_shell_ups_patient_id`) — el organismo real es el punto de partida, y como ya existía historial genuino, `before_value` refleja una comparación real.
- **Basal**: se crea un paciente efímero nuevo (`create_ephemeral_basal_patient()`, misma `create_patient()` de siempre) exclusivo para esa corrida. Sin historial previo para ese id, `before_value` es `None` por construcción — no porque se oculte nada, sino porque genuinamente no hay un "antes" que mezclar con un caso didáctico ajeno.
- `render_ups_scenario_simulator()` (la única función que se modificó para esto) reasigna `st.session_state.twin_shell_ups_patient_id` al id efímero cuando corre en modo basal, y lo restaura con un botón "🔙 Volver al paciente continuo" — el narrador y el cuerpo (ambos sin ningún cambio de código) automáticamente narran/visualizan lo que sea que ese session_state apunte, porque ya leían `st.session_state.twin_shell_ups_patient_id` dinámicamente en cada ejecución.

### `render_ups_scenario_simulator()` (Fase 1.2, ampliada) — única entrada de simulación

Selector de escenario: ahora los 12 `SimulationScenario` reales (antes 3 hechos a mano). Radio de punto de partida (estado actual/basal). El bucle de ejecución sigue actualizando en vivo la barra de progreso, el gráfico (ahora FC + SpO₂ juntos, ya que los 12 escenarios siempre producen ambos dominios) y el cuerpo visual con `render_ups_body(step.state)` paso a paso — igual patrón que antes, mismo código de UI, solo la fuente de los pasos cambió.

### `render_simulation_lab()` (Twin Shell) — eliminada, 100% subsumida

Era el navegador de los mismos 12 escenarios pero **en memoria, sin persistencia** — llamaba a `SimulationEngine` directamente sin pasar por el UPS. Mantenerla habría dejado exactamente la duplicación "un simulador de 12 conectado, otro de 12 sin conectar" que esta tanda buscaba eliminar. Su única llamada en `main()` (twin_shell) se quitó junto con la función; el import ahora-sin-uso de `SimulationEngine` en `pages.py` se limpió (`SimulationScenario` se mantiene, sigue usándose). **No se tocó** `render_simulation_lab_page()` (el simulador viejo del "Simulation Hub" en `app/main.py`, Opción b de la conversación anterior) — eso queda fuera de esta tanda, marcado para absorción futura.

### Verificación (más estricta, toca el núcleo)

- **(a)** Los 12 escenarios cargan y persisten paso a paso — confirmado con `AppTest` (Sepsis, Apnea, Arritmia) y script standalone: 0 excepciones, provenance=`simulacion`/confidence correctos en cada descriptor.
- **(b)** El narrador explica escenarios nuevos citando datos reales — confirmado end-to-end: tras correr Sepsis, "Explicar estado actual" construyó contexto con 14 descriptores y 7 eventos reales del UPS, envió una solicitud bien formada a la API real de Anthropic (401 legítimo con clave inválida de prueba — confirma payload correcto), 0 excepciones no manejadas. `render_clinical_narrator()` sin ningún cambio de código.
- **(c)** El cuerpo se ilumina correctamente y de forma específica por dominio: Sepsis → pulmones crítico / corazón warning; Apnea → pulmones warning / corazón estable; Arritmia → corazón warning / pulmones warning (el modelo real de SimulationEngine también perturba respiración en arritmia — comportamiento real del motor, no inventado).
- **(d)** Toggle verificado con `build_context()` directo: modo estado-actual con historial previo real → `before_value=75.0` (comparación genuina); modo basal con un solo snapshot persistido → `before_value=None` (garantizado, no simulado); modo basal con los 6 pasos completos → comparación limpia y autocontenida dentro de la misma corrida (100→150 bpm), sin contaminación externa.
- **(e)** Los 3 escenarios originales — `tests/test_scenario_simulator.py` 4/4 passed, código intacto.
- **(f)** `pytest tests/` 16/16, arranque real del servidor HTTP 200 logs limpios, cero archivos modificados en `domain/physiology/state/*` ni `domain/physiology/narrator/*` (confirmable por diff de esta tanda: solo `domain/physiology/scenarios/rich_engine.py` nuevo + `app/supermodules/twin_shell/pages.py` editado).

## 2026-07-03 — Tanda 2 (módulo 1/2): Biomarkers Lab encendido — fix de una línea

A pedido del usuario, tras la Tanda 1 (erradicación de IA fingida): "encender" módulos con implementación real ya escrita pero inalcanzable por bugs de conexión — no de IA fingida, así que no violan el Art. I, solo estaban apagados.

### `app/main.py:57-63` — ruta de import corregida

`from app.biomarkers import BiocoreEngine` → `from app.supermodules.biomarkers import BiocoreEngine`. `app/biomarkers.py` nunca existió; `BiocoreEngine` siempre vivió en `app/supermodules/biomarkers.py` — bug de ruta de una línea, no un módulo faltante. Todo el código que consume el motor (`engine.get_full_biomarker_suite(datos_sensores)`, las 7 claves del diccionario de resultados) ya calzaba exactamente con la clase real — nada más necesitaba cambiar. También se corrigió el mensaje de error de respaldo (`main.py:560`, decía "guarda 'biomarkers.py' en 'app/'", ahora apunta a la ruta real) para el caso en que numpy/pandas falten.

**Deliberadamente NO se hizo en esta tanda** (fuera de alcance, señalado explícitamente por el usuario): conectar el motor a señales reales de ECG/EEG u otros módulos, o al UPS. El motor sigue alimentándose solo de 4 perfiles clínicos hardcodeados o entrada manual (`st.number_input`) — es cálculo determinista real, no IA fingida, pero es una calculadora fisiológica real que todavía vive aislada. Conectarla al pipeline de señales reales (o al UPS) queda como trabajo futuro explícito.

### Verificación

`AppTest`: 0 excepciones al cargar la página; el banner de error rojo desapareció; 6 de los 7 índices (`Stress Index`, `Recovery Index`, `NeuroCardiac Coupling`, `Cognitive Load Score`, `Physiological Resilience`, `Learning Readiness Index`) se calculan y muestran con valores reales a partir del preset por defecto — el 7º (`Autonomic Stability Score`) se calcula pero el panel de 3 columnas nunca lo desplegaba, un gap preexistente de la UI, no de este fix, fuera de alcance de esta tanda. `pytest tests/` 16/16 (sin regresiones en ningún otro módulo). Arranque real del servidor, HTTP 200, logs limpios.

## 2026-07-03 — Tanda 1: erradicación de IA fingida (Art. I de la Constitución)

A pedido explícito del usuario, tras la auditoría de plataforma: ninguna parte de la app debe afirmar o simular IA sin una llamada real al narrador (`render_findings_narrator()` / `domain/physiology/narrator/`). Alcance cerrado a los 4 módulos que la auditoría señaló — Digital Twin OS y `domain/physiology/*` no se tocaron. Un módulo a la vez, verificado con `AppTest` después de cada uno.

### AI Analysis (`render_ai_analysis_page`, `app/main.py`)

**Fingido, todo eliminado — no había ningún dato real en la página que conectar:**
- `render_scientific_discovery_layer({'AI_Response': np.random.randn(100)})` — ruido puro presentado como respuesta de IA.
- `'Confidence Score', '0.94'` — literal fijo, no calculado por ningún modelo.
- Vista Educativa: "La IA utiliza redes convolucionales para detectar patrones espaciales en el ECG" — no existe ninguna CNN.
- Vista Investigación: "análisis SHAP/LIME" + botón que solo imprimía "Reporte SHAP generado" sin ejecutar nada.
- Vista IA: "La IA genera hipótesis causales y sugiere diagnósticos diferenciales."
- Vista Simulación: "Inyecta ruido sintético para probar la robustez del modelo" (adversarial testing inexistente).
- Vista Gemelo Digital: "El gemelo predice la evolución del estado vital en los próximos 10 minutos."

Ninguna de las 6 vistas tenía una señal o cálculo real detrás (`safe_import_src_modules()` se llamaba y nunca se usaba) — toda la página era, de punta a punta, afirmaciones de IA sin respaldo. Reemplazada por un único mensaje honesto que explica qué se quitó y por qué, y señala dónde sí hay IA/análisis real en la plataforma (Narrador Clínico, ECG-12, ECG Monitor, EMG, HRV, Multisensor). **Nada se conectó al narrador aquí** — no había ningún dato real que narrar.

### Patient Pipeline (`render_patient_pipeline_page`, `app/main.py`)

**Conectado al narrador real:** la Vista IA decía "IA sugiere estratificación de riesgo y rutas de cuidado..." sin nada detrás. A diferencia de AI Analysis, esta página sí tiene datos reales persistidos — `list_patient_states()` contra `app/clinical_db.py` (SQLite). La Vista IA ahora lee el estado de paciente guardado más reciente (`patient_id`, `diagnosis`, `timestamp` — nunca inventados) y llama a `render_findings_narrator('Patient Pipeline', [...])`; si no hay ningún estado guardado todavía, muestra un aviso honesto en vez de forzar una narración sin datos.

No se tocó nada más de la página (guardar/cargar estado, cohortes demo, etc. — fuera de alcance de esta tanda, no son afirmaciones de IA).

### Simulation Lab (`render_simulation_lab_page`, `app/main.py`)

**Fingido, eliminado:** Vista IA decía "IA estima riesgo y sugiere intervenciones con justificación fisiológica." Los únicos datos reales de la página (sliders HR/RR/SpO2) están agrupados dentro de la Vista Clínica, sin persistir a un estado consultable desde la Vista IA — conectar un narrador ahí habría requerido reestructurar la página (fuera de alcance: "no arregles funcionalidad no-IA rota"). Reemplazado por un mensaje honesto señalando al Narrador Clínico real.

### Hardware Ops (`render_hardware_ops_page`, `app/main.py`)

**Fingido, eliminado:** Vista IA decía "IA sugiere calibraciones automáticas y diagnósticos de fallas de sensores." El único dato disponible para fundamentar esa afirmación (el diccionario `sensors`) incluye un valor ya confirmado como falso en la auditoría (`'ECG Sensor': 'Conectado'`, un literal fijo, no un chequeo real) — arreglar ese dato es una tarea no-IA fuera de esta tanda. Fundamentar un narrador sobre datos parcialmente inventados habría sido una forma más sutil de IA fingida, así que se eliminó la afirmación en vez de conectarla.

### Verificación

`AppTest` en los 4 módulos: 0 excepciones al cargar y al cambiar a la vista IA en cada uno; confirmado que ninguna de las 7 frases fingidas originales sigue presente como funcionalidad activa (las únicas coincidencias restantes son los propios mensajes honestos, que citan la frase vieja para explicar que se quitó). `pytest tests/` 16/16. Arranque real del servidor, HTTP 200, logs limpios.

## 2026-07-03 — Fase 1.4: Digital Twin visual sincronizado con el UPS (cierre de la Fase 1)

Objetivo del usuario: un cuerpo SVG donde corazón y pulmones se resaltan/animan según el estado del UPS, sincronizado con el narrador porque ambos leen la misma fuente de verdad — nunca porque el visual analice el texto del narrador.

### Nuevo módulo: `app/supermodules/twin_shell/ups_body_visual.py`

- `SEVERITY_COLOR` (un solo mapeo `EventSeverity → color`, reutilizado por ambos órganos): `INFO`/sin evento → verde (`STABLE_COLOR`), `WARNING` → ámbar, `CRITICAL` → rojo; `NEUTRAL_COLOR` (gris) reservado exclusivamente para cuando el descriptor clave (`heart_rate`/`respiratory_rate`+`spo2`) no existe todavía en el UPS — nunca se inventa una animación a partir de un valor ausente (mismo principio que `before_value=None` en el narrador).
- `EVENT_VISUAL_MAP`: `EventType → (órgano, etiqueta)` explícito y cerrado, igual que el propio `EventType` — cada evento (`ARRHYTHMIA_RISK_HR_EXTREME`, `LOW_HRV_AUTONOMIC_STRESS` → corazón; `HYPOXIA_SPO2_LOW`, `HYPOXIA_SPO2_CRITICAL` → pulmones) se señala con un halo pulsante (más rápido si `CRITICAL`) y una etiqueta visible sobre el órgano correspondiente.
- Corazón: SVG de un icono de corazón (path estándar, no un atlas anatómico) que pulsa vía CSS `@keyframes` a una duración = `60 / heart_rate` segundos por latido — la animación transmite el dato (taquicardia se ve/pulsa más rápido), no es decorativa.
- Pulmones: SVG de tráquea + bronquios + dos lóbulos simplificados, con un ciclo de "respirar" (`@keyframes biocore-breathe`) a duración = `60 / respiratory_rate` segundos por ciclo; el color (vía severidad, derivada de eventos de hipoxia) refleja el spo2.
- `render_ups_body(state: Optional[UnifiedPhysiologicalState])`: única función pública — recibe un snapshot ya leído del UPS (nunca el organismo en memoria ni texto del narrador) y renderiza ambos órganos. `state=None` → ambos órganos en gris neutro (paciente sin ningún snapshot todavía).

### `app/supermodules/twin_shell/pages.py`

- Nueva `render_synced_digital_twin_body()`: lee pasivamente `get_latest_state()` (sin escribir nada por sí sola) y la muestra junto al narrador, bajo "🧭 Herramientas avanzadas". Botón "🔄 Sincronizar con sliders actuales" para persistir bajo demanda un snapshot fresco del organismo — mismo patrón que "Explicar estado actual" del narrador.
- `render_ups_scenario_simulator()`: añadido un `body_placeholder` dentro del bucle de ejecución del escenario (Fase 1.2) — en cada paso, el cuerpo se re-renderiza con `step.state` (el snapshot recién persistido de ese paso exacto), en vivo, junto al gráfico de trayectoria existente.

**Bug real encontrado y corregido durante la verificación**: la primera versión de `render_synced_digital_twin_body()` volvía a persistir un snapshot fresco desde `organism` en cada rerun. Pero `render_sensor_controls()` (que corre antes, también en cada rerun) empuja incondicionalmente los valores de los sliders al organismo — así que, justo después de correr un escenario (que dispara un `st.rerun()`), el organismo quedaba pisado de vuelta a los valores por defecto de los sliders *antes* de que el cuerpo leyera nada, y el resaltado crítico de la hipoxia desaparecía inmediatamente después de verse correctamente durante la animación en vivo. Corregido haciendo que la función "siempre visible" solo *lea* el último snapshot ya persistido (por el escenario o por el botón de sincronizar), sin volver a escribir desde el organismo en cada rerun.

### Verificación (criterios de aceptación)

Con `AppTest`, ejecutando cada escenario end-to-end (selector → pasos → botón "Ejecutar y persistir") y leyendo el HTML final del cuerpo:
- **(a) `hipoxia_progresiva`**: pulmones → rojo/crítico, con la etiqueta "🚨 Hipoxia crítica" presente; corazón → verde/estable (sin alerta). ✅
- **(b) `fibrilacion_estres`**: corazón → ámbar/warning con "⚡ Arritmia — FC fuera de rango" (FC llega a 145 bpm, por debajo del umbral de 150 para crítico — el color refleja correctamente el umbral real, no uno inventado); pulmones → verde/estable, sin alerta — el resaltado es específico por dominio, confirmado. ✅
- **(c)** Confirmado indirectamente: el cuerpo cambia exactamente cuando el UPS cambia (antes de cualquier escenario/sync: ambos órganos en gris neutro, 0 excepciones), y los colores observados corresponden exactamente a los umbrales reales de `domain/physiology/state/builder.py::_detect_events` — no a un análisis del texto del narrador (el cuerpo nunca importa `narrator/`). ✅
- **(d)** SVG 2D puro (sin Three.js/WebGL/3D); solo corazón y pulmones — ningún otro sistema (nervioso, muscular) dibujado. ✅

`pytest tests/` 16/16. Arranque real del servidor, HTTP 200, logs limpios.

## 2026-07-03 — IA real en las pestañas "IA" del Clinical Hub; "Gemelo Digital" redundante eliminado

El usuario reportó, tras usar la plataforma: "algunas funcionalidades parecen falsas... sobre todo las que se despliegan del clinical hub como dropdown... algunas de las funcionalidades en estos labs parecen no tener IA real implementada (tampoco en ECG)". Diagnóstico confirmado: el patrón de 6 pestañas "Capa de Exploración Cognitiva" (`render_view_selector()`), usado en EMG, ECG Monitor, Multisensor y HRV Analysis, tenía una pestaña "IA" que en 3 de las 4 páginas era una sola frase estática sin ningún cómputo (`st.write('IA sugiere diagnósticos: ...')`), y en ECG Monitor ejecutaba una función real (`interpret_ecg()`, detección de picos + umbrales) pero la etiquetaba como "IA" sin serlo — es un analizador de reglas, no un modelo. Además, las 4 páginas tenían una pestaña "Gemelo Digital" con métricas ad-hoc desconectadas del gemelo real (`DigitalTwinOrganism` en Digital Twin OS): `np.random.uniform(10,80)` en EMG, un promedio crudo de PPG en Multisensor, una fórmula ad-hoc en HRV, y una animación 3D decorativa en ECG Monitor.

Se preguntó al usuario cómo resolver cada punto por separado. Eligió: (1) conectar las pestañas "IA" al narrador clínico real en vez de solo eliminarlas, (2) eliminar las pestañas "Gemelo Digital" (redundantes con Digital Twin OS), (3) mantener EMG Muscle Lab mientras se simplifica.

### Nuevo módulo: `domain/physiology/narrator/findings.py`

El narrador clínico existente (`context.py`/`prompt.py`/`client.py`, Fase 1.3) está diseñado específicamente para narrar el Unified Physiological State — requiere una sesión SQLAlchemy y un `patient_id` con snapshot persistido, y solo los dominios cardiovascular y respiratorio están modelados en el UPS. EMG, HRV, Multisensor y la sesión ad-hoc de ECG Monitor no tienen dominio en el UPS, así que no había dónde anclar un snapshot.

Se construyó un módulo complementario, no un narrador nuevo y aislado: mismo cliente Anthropic (`claude-opus-4-8`, streaming), misma exigencia de `ANTHROPIC_API_KEY` real sin narración simulada de respaldo, misma disciplina de anclaje (cada afirmación debe citar el nombre exacto de una métrica del contexto, prohibido inventar valores) — pero con un contexto más liviano (`FindingsContext`/`Finding`: una lista plana de métricas ya calculadas por el laboratorio, sin comparación temporal, ya que estas señales ad-hoc no tienen historial persistido). Expuesto en `domain/physiology/narrator/__init__.py` junto al narrador UPS existente.

### `app/main.py`: `render_findings_narrator()` — UI compartida

Nueva función (junto a `render_metric_explained`/`render_discovery_lab`) que reutilizan las 4 páginas: gatea en `is_configured()` (mismo warning que el narrador UPS si falta la API key), botón "🗣️ Explicar estos hallazgos", `st.write_stream()`, captura `NarratorNotConfiguredError` y errores de red/cuota de la API real.

### Pestañas "IA" reemplazadas (una por página, todas con datos reales ya calculados en esa página, ninguno inventado):
- **EMG Muscle Lab**: activación muscular %, frecuencia mediana (Welch PSD), índice de fatiga, origen de la señal.
- **ECG Monitor**: frecuencia cardíaca y QTc estimados por `interpret_ecg()` (detección de picos + intervalos), flags detectados (taquicardia/bradicardia/ST/QTc largo/posible AFib) — la etiqueta "IA" ahora corresponde a la narración real, no al analizador de umbrales que la alimenta.
- **Multisensor Fusion Lab**: Health Score agregado, frecuencia cardíaca, SpO2 — de `MultisensoralRecord.compute_physiological_indices()`/`health_score()`, ya real, solo sin usar antes en esta pestaña.
- **HRV Analysis**: SDNN, RMSSD, pNN50, razón LF/HF — ya calculados arriba en la página (Welch PSD sobre RR interpolado).

### Pestañas "Gemelo Digital" eliminadas (EMG, ECG Monitor, Multisensor, HRV)

`render_view_selector()` ganó un parámetro opcional `views` para que cada página module pueda excluir opciones sin afectar a las demás páginas que sí conservan el patrón de 6 pestañas (Education, AI Analysis, Patient Pipeline, Simulation Lab — no tocadas, fuera del alcance de lo reportado). Se eliminó también, junto con la pestaña, la animación 3D decorativa de ECG Monitor (figura de corazón vía funciones paramétricas, sin significado fisiológico real).

### Verificación

`AppTest`: sweep de las 4 páginas — 0 excepciones al cargar y al cambiar a la vista "IA"; confirmado que "Gemelo Digital" ya no aparece en las opciones. Con `ANTHROPIC_API_KEY` real configurada (aunque inválida, para probar el circuito completo sin gastar cuota): el botón "Explicar estos hallazgos" arma la solicitud, llega a la API real de Anthropic, y recibe una respuesta 401 legítima del servidor (confirma que el payload/JSON/modelo están bien formados) — capturada sin excepciones no manejadas. `pytest tests/` 16/16. Arranque real del servidor, HTTP 200, logs limpios.

## 2026-07-03 — Los 3 puntos diferidos: 61 casos clínicos al ECG Monitor, Respiratory/EMG unificados, raíz de la doble navegación cerrada

A pedido explícito del usuario: "conectar los 61 casos clínicos completos al ECG Monitor, unificar Respiratorio/EMG a las versiones ricas de sus supermódulos, y resolver el problema de raíz de doble navegación para el resto del Hub... resuélvelo de una vez por todas". Los tres puntos que quedaron explícitamente diferidos en la entrada de auditoría anterior.

### 61 casos clínicos → ECG Monitor

Diagnóstico exacto (via auditoría de dos agentes en paralelo, confirmado archivo por archivo):
- `build_complete_case_database()` (`src/clinical/case_database.py:583`, genera 61 casos: 12 NSR + 8 AFib + 8 PVC + 4 VT + 9 AV Block + 8 RBBB/LBBB + 9 STEMI + 3 Long QT) **nunca se llamaba desde ningún código de la app** — solo desde su propio `if __name__ == "__main__":`.
- El único selector de casos que existía en la UI (`app/supermodules/ecg_monitor/pages.py`) importaba 6 de los 8 generadores directamente y hardcodeaba un dict de 7 casos fijos (`'AFib demo': generate_afib_case('DEMO', age=65, sex='F')`, etc.) — NSR y Long QT (15 de los 61 casos) no tenían representación alguna, y STEMI estaba fijo a `location='anterior'`.
- Ese archivo, además, solo era alcanzable lanzando `streamlit run app/pages/1_ECG_Monitor.py` como proceso aparte — **no** desde el Hub real (`streamlit run app/main.py`), donde "📊 ECG Monitor" enrutaba a `render_ecg_monitor_page()`, una tercera implementación en `app/main.py` (Demo sintético / CSV local) sin ningún selector de casos clínicos.

Arreglado en dos frentes:
- **`app/supermodules/ecg_monitor/pages.py`**: `load_clinical_case()` reescrito para usar `build_complete_case_database()` cacheada con `@st.cache_resource` (los generadores usan `np.random` para edad/sexo/frecuencia — cachear evita que cambien en cada rerun). El selector de 7 casos fijos se reemplazó por un selector en dos pasos (diagnóstico → caso específico) sobre los 61 casos reales, con un expander de detalle clínico (edad, sexo, diagnósticos secundarios, factores de riesgo, historia clínica, dificultad, acción clínica recomendada, riesgo de mortalidad — todo tomado directo del `ClinicalCase`, sin inventar nada).
- **`app/main.py`**: `render_ecg_monitor_page()` (el "🫀 Cardiovascular Intelligence Lab" real del Hub, con anatomía interactiva, gemelo 3D del corazón, capa de descubrimiento científico — nada de esto se tocó ni se perdió) ganó una tercera fuente de datos en el radio `ECG Source`: **"Caso clínico (61 disponibles)"**, con el mismo selector de dos pasos, reutilizando `get_case_database()` del supermódulo (sin duplicar la generación de casos). El caso cargado también muestra su detalle clínico completo en un expander dentro de la vista Clínica.

**Bug encontrado y corregido de paso** en `src/clinical/case_database.py::build_complete_case_database()`: cada `case_id` salía duplicado (`AFib_AFib_0`, `STEMI_anterior_STEMI_anterior_0`, etc.) porque la función le pasaba a cada generador un id que ya incluía el prefijo de diagnóstico (p.ej. `f"AFib_{i}"`), y cada generador (p.ej. `generate_afib_case`) vuelve a anteponer ese mismo prefijo (`case_id=f"AFib_{patient_id}"`). Invisible hasta hoy porque la función nunca se había llamado desde ningún lugar que mostrara los ids a un usuario real. Corregido pasando ids simples (`str(i)`) a los 8 generadores — 61 case_id limpios y únicos, verificado por script (`AFib_0`, `STEMI_anterior_0`, `NSR_0_M`, sin colisiones).

### Respiratory Lab unificado

Confirmado por auditoría: `render_respiratory_page()` inline en `app/main.py` (un patrón de respiración fijo, RR estimado crudo, sin apnea, sin AHI, un slider "Simulación" que no regeneraba nada, un "Gemelo Digital" con `np.random.uniform(30,90)`) era un subconjunto estricto del supermódulo (`app/supermodules/respiratory_lab/pages.py` → `pages_legacy/7_💨_Respiratory-Lab.py`): 7 patrones seleccionables (Normal, Taquipnea, Bradipnea, Apnea Central, Apnea Obstructiva, Cheyne-Stokes, Atáxica), análisis real de apnea/AHI/severidad, canales de tórax/abdomen/SpO2, tablas de referencia clínica AASM, y un quiz de 5 preguntas. Nada en la versión inline era único. Reemplazado el mismo patrón que ECG-12/EEG: `render_respiratory_lab_page()` delega a `app.supermodules.respiratory_lab.pages.run()`; la función inline vieja se eliminó (quedó solo un comentario explicativo). El import ahora-sin-uso de `estimate_respiration_rate` se quitó de `app/main.py`.

### EMG Muscle Lab: hardware real, sin perder nada

A diferencia de los otros tres, este caso **no** era un duplicado simple — la auditoría encontró una divergencia genuina: la versión del Hub (`render_emg_page()`) tenía 3 patrones de demo (Isométrica/Rápida/Fatiga), análisis de frecuencia mediana (Welch PSD, proxy de fatiga), y la UX de 6 pestañas del resto de la app — pero su "Live Hardware" era una simulación silenciosa: intentaba `importlib.import_module('biomedical.emg')` (módulo que no existe en el repo), fallaba siempre, y caía a modo demo sin avisar. El supermódulo (`pages_legacy/9_🦾_EMG_Muscle_Lab.py`) tenía tutorial de electrodos paso a paso y una conexión de hardware real (`hardware.sensor_manager.SensorManager` + `hardware.emg_stream.EMGStreamer`) — pero sin patrones de demo ni análisis de frecuencia.

Se preguntó al usuario cómo resolverlo (no es un caso de "borrar el peor y quedarse con el mejor" como los otros tres). Eligió conservar la versión rica del Hub y arreglar solo el hardware. Implementado en `app/main.py`:
- El bloque `try: importlib.import_module('biomedical.emg') except: ...` se reemplazó por imports directos y honestos de `hardware.sensor_manager.SensorManager` y `hardware.emg_stream.EMGStreamer` (el mismo hardware real que ya usaba el supermódulo). `preprocess_emg`/`compute_emg_median_frequency`/`compute_emg_fatigue_index` (cálculos reales vía Welch, no placeholders) se dejaron como las únicas implementaciones, sin el `try/except` muerto que nunca tenía éxito.
- La rama "Live Hardware" de `render_emg_page()` se reescribió para enumerar puertos con `SensorManager`, conectar/desconectar con `EMGStreamer.connect()/.start()/.stop()/.disconnect()`, mostrar estado real (`get_status()`, `last_error`) y leer la señal real vía `get_filtered_buffer()` — con caída a demo (con aviso explícito) solo si el buffer de hardware está vacío. Cero pérdida de los patrones de demo, el análisis de frecuencia mediana o las 6 pestañas.

### Raíz de la doble navegación cerrada

Ver `_archive/README.md` (entrada "2026-07-03 — `app/pages/` wrappers archived") para el detalle completo. Resumen: aunque `.streamlit/config.toml` ya ocultaba la lista nativa de páginas desde 2026-07-01, los 11 archivos en `app/pages/` seguían existiendo en disco — Streamlit los seguía tratando como una segunda app multipágina lanzable directamente (`streamlit run app/pages/1_ECG_Monitor.py`), invisible en la UI pero real, y **era precisamente ahí donde vivía la única versión con selector de casos clínicos**, inalcanzable desde el Hub. Con autorización del usuario (se preguntó explícitamente el método dado que el repo no tiene git), los 11 wrappers + un generador de plantillas ya obsoleto que los recreaba (`app/templates/generate_lab_pages.py`, `biomedical_lab_template.py` — sin ningún llamador, con un formato de stub ya inconsistente con los wrappers reales) se movieron a `_archive/app/pages/` y `_archive/app/templates/`, preservando el historial en vez de borrar. `RUN_BIOCORE.bat` y `QUICKSTART.md` se actualizaron para dejar de documentar los comandos `streamlit run app/pages/*.py` — algunas de esas opciones ya apuntaban a archivos borrados desde la consolidación de Academia del 2026-07-01 (`app/pages/12_Academia_Inteligente.py`), sin que nadie lo hubiera notado.

`streamlit run app/main.py` es ahora, en los hechos y no solo en la documentación, la única forma de ejecutar la aplicación.

### Verificación

`streamlit.testing.v1.AppTest`: sweep de las 5 páginas tocadas (ECG Monitor, Respiratory Lab, EMG Muscle Lab, y regresión de ECG-12/EEG) — 0 excepciones en todas. Click-through completo en ambos selectores de caso clínico (Hub y supermódulo): selección de diagnóstico, cambio de categoría, expander de detalle, clic en "Cargar caso clínico", carga exitosa — 0 excepciones. `pytest tests/` 16/16. Arranque real del servidor (`streamlit run app/main.py`), HTTP 200, logs sin errores.

## 2026-07-03 — Causa real de "no veo el ECG-12": navegación del sidebar, no el código de la página

El usuario reportó, tras el cambio anterior, que seguía sin ver las gráficas — refrescó el navegador y aun así no las encontraba. Diagnóstico: no era un bug del ECG-12, sino que la forma de **llegar** a esa página era prácticamente indetectable:
- `st.set_page_config(initial_sidebar_state="collapsed", ...)` — la barra lateral (única vía para cambiar de módulo dentro de un hub) empezaba **oculta** en cada carga.
- El `st.sidebar.selectbox('Selecciona un módulo', ...)` que lista "📋 ECG-12-Derivaciones" junto a los otros ~8 módulos del Clinical Hub se renderizaba con `label_visibility='hidden'` y **sin ningún texto o título encima** — un dropdown mudo.
- Al entrar por el botón "Clinical Hub" de la home, `selected_page` se fija al primer ítem de esa lista ("📊 ECG Monitor"), así que el usuario aterriza en Monitor, no en ECG-12, sin ninguna pista de que debe cambiar de módulo en un control sin etiqueta.

### `app/main.py`
- `initial_sidebar_state`: `"collapsed"` → `"expanded"` — la barra lateral (y su navegación) es visible desde la primera carga.
- Añadido `st.sidebar.caption(f"📂 Módulo dentro de **{hub}**:")` justo encima del selectbox de módulo; el selectbox pasa de `label_visibility='hidden'` a `'collapsed'` (mismo efecto visual compacto, pero ahora con el caption explicando qué es).

Verificado con `AppTest`: 0 excepciones en carga por defecto y en Clinical Hub; el caption y las opciones (incluyendo "📋 ECG-12-Derivaciones") se confirmaron presentes en el sidebar. `pytest tests/` 16/16.

## 2026-07-03 — ECG-12: cuadrícula clínica profesional + explicabilidad de la interpretación

El usuario aclaró que "los 12 escenarios" se refería a poder **ver** el ECG de 12 derivaciones de forma explicable y con gráficas de calidad profesional, no solo elegir el escenario clínico.

### `clinical/ecg12.py::plot_ecg_12_leads` — reescrito
Antes generaba 12 subplots apilados en una sola columna, sin cuadrícula, altura 2400px — el `except` de la página (nunca alcanzado, porque el `try` con Plotly siempre tenía éxito) tenía en realidad un layout más organizado pero tampoco era una cuadrícula de papel ECG real. Ahora produce el layout clínico estándar impreso: 3 filas x 4 columnas (cada columna es un tramo consecutivo real de 2.5s, igual que un ECG de papel real con 3-4 canales simultáneos) más una tira de ritmo (derivación II completa, 10s) con pulso de calibración (0.2s/1mV). Cuadrícula real de papel ECG: caja mayor 0.2s/0.5mV en rojo, caja menor 0.04s/0.1mV en rosa (25 mm/s, 10 mm/mV). Fallback a Matplotlib con el mismo layout y cuadrícula si Plotly no está disponible (antes el fallback era una versión distinta y más pobre).

### `app/pages_legacy/6_📋_ECG-12-Derivaciones.py`
- Quitado el bloque `try/except` que duplicaba lógica de graficado (el `except`, con su propio grid 4x3 sin cuadrícula real, nunca se alcanzaba); ahora la página llama directo a `plot_ecg_12_leads` (que ya maneja su propio fallback internamente). Imports `plotly.graph_objects`/`make_subplots` eliminados por no uso.
- Nuevo expander educativo "🎓 ¿Qué es un ECG de 12 derivaciones?" con la explicación de las 12 derivaciones y territorios vasculares — contenido estático de texto, no generado por IA.
- Nuevo resumen narrativo en la sección de interpretación, compuesto directamente de los campos ya calculados por `TwelveLeadEcgAnalyzer` (ritmo, grados del eje QRS, hallazgos ST, bloqueos, significancia clínica) — sin inventar ningún dato, solo redacta en una frase lo que ya se mostraba en viñetas debajo.

Verificado con `streamlit.testing.v1.AppTest`: 0 excepciones al cargar y al generar el ECG, 1 gráfico Plotly renderizado, resumen narrativo y expander educativo presentes. `pytest tests/` 16/16.

## 2026-07-03 — Eliminación de comandos de voz/gestos/hands-off/atajos + página ECG-12 más limpia (a pedido del usuario)

### Eliminado por completo
- `app/hands_off_mode.py` (Hands-Off Mode) — borrado. Estaba wireado (panel siempre visible en una columna lateral en cada página, `main.py:1519-1521` antes de este cambio).
- `gesture_controller.py` (control por gestos vía cámara) — borrado. Su UI (`render_gesture_panel()`, emulador de gestos con botones, detección por `st.camera_input`) nunca se llamaba desde ningún sitio — código muerto.
- Comandos de voz (`SpeechRecognition`, `pyaudio`) — nunca tuvieron implementación real más allá de las dependencias en `requirements.txt`; ninguna llamaba a estos paquetes. Dependencias eliminadas.
- "Atajos de teclado" — no existía ninguna implementación real (ni JS ni Python), solo la etiqueta "⌨️ Atajos clínicos" en el sidebar. Etiqueta eliminada.
- Dependencias quitadas de `requirements.txt`/`requirements_extra.txt`: `mediaipe`/`mediapipe`, `opencv-python`, `SpeechRecognition`, `pyaudio`.
- `install_dependencies.py`: quitados los pasos de instalación de MediaPipe/voz/gestos, renumerado, limpiada la lista de verificación y el texto de "NEXT STEPS" (ya no menciona "JARVIS Copilot"/"Hands-Off Mode").
- `app/reporting.py`: quitada la sugerencia de instalar `mediapipe opencv-python` en el pie del reporte HTML generado.

### `app/main.py` — limpieza de código muerto asociado
Quitados: el import + fallback de `GestureController`, `get_gesture_controller()`, `apply_gesture_action()`, `render_gesture_panel()` (nunca llamada), `render_hands_off_page()` (nunca llamada, sin entrada en `HUBS`), la entrada `'Cámara / Gestos'` del panel de Hardware Ops, y las claves de `session_state` (`gesture_feedback`, `hands_off_feedback`, `hands_off_enabled`, `hands_free_active`) que ya no tienen consumidor. El layout de `main()` pasó de dos columnas (`content_col` 3/4 + `side_col` 1/4 con el panel de Hands-Off) a una sola columna a todo el ancho, ya que `side_col` solo contenía ese panel.

### Página ECG de 12 derivaciones — reorganizada para que el escenario sea lo primero que se ve
El usuario reportó que, aun con el enrutamiento arreglado (ver entrada anterior), seguía sin encontrar el selector de patrones clínicos ("los 12 escenarios") — estaba enterrado dentro de una pestaña "⚙️ Configuración" después de un bloque largo de texto introductorio (tabla de contenidos con anclas que no funcionan como navegación real en Streamlit, explicación de "cómo usar el laboratorio").

`app/pages_legacy/6_📋_ECG-12-Derivaciones.py`:
- Quitada la tabla de contenidos falsa y la sección "Cómo usar este laboratorio" (reemplazadas por un `st.caption` de una línea).
- El selector `🩺 Escenario clínico` (13 patrones: normal, taquicardia, bradicardia, 3× STEMI, RBBB, LBBB, LVH, AF, flutter, WPW, QT largo) ahora es el primer control visible, fuera de cualquier pestaña/expander.
- Un botón primario "🔄 Generar ECG de 12 derivaciones" queda inmediatamente debajo, siempre visible.
- Los parámetros secundarios (FC exacta, amplitud P, duración QRS, elevación ST, origen de la señal, filtro, carga de CSV) se movieron a un `st.expander` colapsado por defecto — siguen disponibles, ya no son lo primero que hay que atravesar.
- El bloque "🔬 Análisis Automático" (una pestaña que solo describía qué detecta el análisis, sin datos) se eliminó — esa información ya aparece con datos reales en "📋 Interpretación Clínica Automática" una vez generado el ECG.

### Verificado
- `pytest tests/`: 16/16 passed.
- `streamlit.testing.v1.AppTest`: home page, ECG-12, EEG Neuro Lab y Digital Twin OS cargan con 0 excepciones tras la eliminación. La página ECG-12 muestra el selector de escenario como widget de nivel superior (no anidado en tabs) y, tras hacer clic en "Generar ECG", la sección de interpretación clínica renderiza con datos reales — confirmado con `at.button[...].click().run()`, no solo "carga sin error".

## 2026-07-03 — Auditoría y corrección: navegación del Hub para ECG-12/EEG (reportado por el usuario)

El usuario reportó que 4 funciones que existían antes parecían haber desaparecido: ECG 12 derivaciones, casos clínicos de ejemplo, visualización de bandas EEG, y visualización respiratoria/EMG. Auditoría (4 sub-agentes en paralelo, solo lectura) contra el estado actual del repo — **no es un repositorio git, sin historial** para comparar contra el pasado, así que el análisis se basó en el código actual + lo documentado en este CHANGELOG/PLAN.md.

### Hallazgo central
El proyecto tiene **dos sistemas de navegación en paralelo**: el "Hub" personalizado de `app/main.py` (lo que el usuario navega) y la multipágina **nativa** de Streamlit, autodescubierta desde `app/pages/*.py` (nunca suprimida — el sidebar solo está colapsado). La mayoría de `app/pages/*.py` delega correctamente a los supermódulos completos; el Hub personalizado, no siempre. Esto explica la sensación de "desaparición" — el código real seguía existiendo, solo detrás de una puerta de navegación distinta o roto en la que el usuario sí usa.

### Por función
- **ECG 12 derivaciones**: `main.py` llamaba a `render_ecg_12_page()`, que **nunca estaba definida** → `NameError` en vivo al hacer clic. El código real (`app/supermodules/ecg_12/pages.py` → `pages_legacy/6_📋_ECG-12-Derivaciones.py`) estaba intacto, solo desconectado.
- **Casos clínicos**: no se perdieron en la limpieza de Fase 0 — nunca se conectaron del todo. `src/clinical/case_database.py` tiene 61 casos generables; el ECG Monitor solo expone 7. Los "100+ casos" de los documentos ejecutivos son metas de roadmap futuro, nunca implementadas (no hay regresión que corregir aquí — queda fuera de este fix).
- **EEG (bandas alpha/beta/gamma/delta/theta)**: `render_eeg_page()` (inline en `main.py`) importaba `biomedical.eeg`, módulo que **no existe en el repo** — fallo silencioso, banner de error permanente, y ni siquiera tenía visualización de bandas aunque el import funcionara. El código real (`app/supermodules/eeg_neuro_lab/pages.py` → `pages_legacy/8_🧠_EEG-Neuro-Lab.py`, que importa correctamente de `src/signals/eeg`) sí grafica potencia de banda (Plotly, tabla Delta/Theta/Alpha/Beta/Gamma, banda dominante) y estaba intacto, solo desconectado.
- **Respiratorio y EMG**: sin regresión — `render_respiratory_page()`/`render_emg_page()` (inline en `main.py`) sí grafican la señal real. Existe una versión más completa en `app/supermodules/{respiratory_lab,emg_muscle_lab}/`, huérfana sin conectar — mejora opcional, no corregida en este fix (usuario priorizó los dos bugs reales primero).

### Corregido (alcance elegido por el usuario: "los 2 bugs reales primero")
- `app/main.py`: añadida `render_ecg_12_page()` y `render_eeg_neuro_lab_page()`, ambas delegando al supermódulo real (mismo patrón que `render_twin_shell_page`/`render_academia_page`). Enrutamiento de "EEG" actualizado para usar la nueva función. Eliminada la antigua `render_eeg_page()` (rota, dependía de `biomedical.eeg` inexistente) y el bloque de import muerto que la alimentaba.
- `app/supermodules/ecg_12/pages.py` y `app/supermodules/eeg_neuro_lab/pages.py`: eliminado un `try: main() except ...` a nivel de módulo que se ejecutaba una vez al importar y otra vez dentro de `run()` — causaba doble renderizado la primera vez que se importaba el módulo en un proceso (bug preexistente, se habría manifestado en cuanto se reconectaran estas rutas). `run()` es ahora el único punto de entrada.

### Verificado
- `pytest tests/`: 16/16 passed (sin cambios de comportamiento en el UPS/escenarios/narrador).
- `streamlit.testing.v1.AppTest` sobre `app/main.py`, navegando a Clinical Hub → "📋 ECG-12-Derivaciones" y "🧠 EEG Neuro Lab": **0 excepciones, 0 `st.error`**, contenido real confirmado (`# 📋 ECG de 12 Derivaciones`, `# 🧠 EEG Neuro Lab` con tabla de bandas, 6-8 tabs cada una) — no solo "no crashea", sino que el contenido correcto se renderiza.

### Explícitamente fuera de este fix (el usuario puede pedirlo después)
- Conectar los 61 casos clínicos completos al ECG Monitor (hoy expone 7).
- Unificar Respiratorio/EMG a las versiones ricas de sus supermódulos.
- Resolver el problema de raíz (dos sistemas de navegación en paralelo) para el resto del Hub — este fix solo tocó ECG-12 y EEG.

## 2026-07-02 — Fase 1.3: Narrador clínico en tiempo real (IA real) (implementada, esperando confirmación)

Nuevo paquete `domain/physiology/narrator/` — primera integración real de la API de Anthropic en el proyecto. Refunde y elimina los dos caminos de IA fingida/muerta que existían.

### Añadido
- `domain/physiology/narrator/context.py` — `build_context()`: arma un `NarrativeContext` (datos, no prosa) desde el UPS: descriptores actuales con procedencia/confianza y comparación temporal antes/ahora (vía `get_value_history`, nunca fabricada si no hay trayectoria), más eventos recientes citables por `EventType` exacto.
- `domain/physiology/narrator/prompt.py` — `DepthLevel` (estudiante/residente/experto) + system prompt con reglas de anclaje estrictas (cita descriptor/evento exacto o no lo afirmes; nunca inventes un valor; comparación temporal obligatoria cuando exista; la etiqueta legible de cada descriptor la genera el modelo al narrar, no un diccionario hardcodeado). El contexto va como JSON en el mensaje de usuario.
- `domain/physiology/narrator/client.py` — `stream_narration()`: `client.messages.stream(model="claude-opus-4-8", ...)` → `stream.text_stream`. Sin `ANTHROPIC_API_KEY` en el entorno, lanza `NarratorNotConfiguredError` — no hay respaldo simulado.
- UI: `app/supermodules/twin_shell/pages.py` → `render_clinical_narrator()` (persiste un snapshot fresco del organismo antes de narrar, así el UPS y la narración siempre están sincronizados) y `app/main.py` → hub "AI Hub" reutiliza la misma función y sesión (un único punto de IA real).
- `tests/test_narrator.py` — 5 pruebas: comparación temporal presente tras una trayectoria, ausencia correcta de `before_value` sin historia, error explícito para paciente sin estado UPS, el prompt lleva datos (JSON parseable) no prosa y exige reglas de anclaje, el system prompt cambia con el nivel de profundidad.
- Dependencia nueva: `anthropic` instalada en `.conda` (ya estaba en `requirements.txt` desde el intento anterior de JARVIS, ahora sí en uso real).

### Eliminado
- `app/ai_copilot.py` (JARVIS): código muerto — `render_copilot_panel`/`initialize_copilot` se importaban en `main.py` pero nunca se llamaban desde ningún sitio real.
- `app/biomedical_tutor.py` (`BiomedicalTutor`, diccionario `BIOCORE_KNOWLEDGE_BASE`): sí estaba wireado (hub "AI Hub" en `main.py`, pestaña "Tutor IA" en `app/supermodules/academia/pages.py`) — ambos puntos reemplazados: el primero ahora es el narrador real; el segundo queda con un mensaje que apunta al narrador (conectar Academia al UPS es trabajo de una fase posterior).

### Verificado
- `pytest tests/test_narrator.py`: 5/5 passed.
- Resto de la suite (excluyendo los 3 archivos ya rotos antes de esta sesión): 16/16 passed en total.
- `streamlit run app/main.py`: HTTP 200, sin warnings de import tras eliminar los dos módulos.

### Pendiente — no verificado en esta sesión
- **La llamada real a la API (streaming) no se ejecutó end-to-end**: este entorno de desarrollo no tiene `ANTHROPIC_API_KEY` configurada. El código está completo y falla explícitamente (`NarratorNotConfiguredError`, visible en la UI) en vez de fingir una narración — pero falta que el usuario lo pruebe con su propia key para confirmar el streaming visual real.

**Estado: esperando confirmación del usuario (incluida la prueba manual con API key real) antes de avanzar a Fase 1.4.**

## 2026-07-02 — Fase 1.2: Simulador de escenarios que alimenta el UPS (implementada, esperando confirmación)

Nuevo paquete `domain/physiology/scenarios/` — trayectorias fisiológicas deterministas que hacen evolucionar un `DigitalTwinOrganism` en el tiempo y persisten cada paso en el UPS (Fase 1.1).

### Añadido
- `domain/physiology/scenarios/definitions.py` — 3 escenarios (`fibrilacion_estres`, `hipoxia_progresiva`, `sepsis_temprana`) como waypoints clínicos interpolables; `interpolate()` es determinista (interpolación lineal, no `random`).
- `domain/physiology/scenarios/engine.py` — `run_scenario()`: generador que evoluciona el organismo paso a paso reutilizando `update_from_sensors()` (ningún umbral clínico duplicado) y persiste cada paso vía `from_digital_twin_organism()` + `save_state()`.
- `tests/test_scenario_simulator.py` — 4 pruebas: trayectoria monótona/determinista y persistida (fibrilación+estrés), eventos de hipoxia generados y persistidos al empeorar el escenario, validación de entrada, catálogo de escenarios.
- UI: `app/supermodules/twin_shell/pages.py` → `render_ups_scenario_simulator()`, dentro de "🧭 Herramientas avanzadas" → "🧬 Simulador de escenarios clínicos (persistido en el UPS)". Selector + pasos + ejecución visible en tiempo real (barra de progreso y gráfico actualizándose por paso) + relectura del UPS después para probar persistencia real, no solo `session_state`.

### Verificado
- `pytest tests/test_scenario_simulator.py`: 4/4 passed.
- Resto de la suite (excluyendo los 3 archivos ya rotos antes de esta sesión): 11/11 passed en total.
- `streamlit run app/main.py`: HTTP 200, nuevo selector visible en el Twin Shell, sin warnings de import.

### Alcance respetado
- Solo 3 escenarios cardiovascular/respiratorio (el objetivo pedía 2-3), sin biblioteca completa.
- `biomedical/arrhythmia_classifier.py` (requiere modelo entrenado que no existe en el repo) y `hardware/` (streams de sensor real) quedaron fuera — documentado como `// TODO: integración real pendiente` en `PLAN.md`, con la ruta de integración futura ya definida (mismo `save_state()`, `Provenance.SENSOR_REAL`).

**Estado: esperando confirmación del usuario antes de avanzar a Fase 1.3 (narrador clínico con IA real).**

## 2026-07-02 — Fase 1.1: ajustes de contrato tras aprobación del usuario

Usuario aprobó Fase 1.1 con dos ajustes de contrato en `domain/physiology/state/schema.py`, antes de pasar a Fase 1.2:

### Añadido
- `CONFIDENCE_REFERENCE` (+ `ConfidenceBand`, `default_confidence()`): tabla central que fija el rango de `confidence` esperado por `Provenance` (sensor_real `[0.85,1.0]`, simulacion `[0.60,0.90]`, derivado `[0.50,0.95]`), con la razón de cada banda. `confidence` sigue siendo `float` libre — la tabla da significado, no una nueva validación. `builder.from_digital_twin_organism()` usa `default_confidence(provenance)` como valor por defecto en vez del `0.9` fijo anterior.
- `EventType(str, Enum)`: catálogo cerrado de los 4 eventos ya emitidos por `builder._detect_events`. `PhysiologicalEvent.event_type` pasa de `str` a `EventType`. `repository.py` persiste `.value` y reconstruye el enum al leer.

### Verificado
- `pytest tests/test_ups_state.py`: 3/3 passed (tests migrados para comparar contra `EventType`, no strings).
- Resto de la suite (excluyendo los 3 archivos ya rotos antes de esta sesión): 7/7 passed.

### Respetado
- No se tocó `display_name` en texto plano (aplazado a 1.3, por instrucción explícita del usuario).
- No se añadió validación de rango de `confidence` por procedencia — solo se centralizó su semántica, según lo pedido.

**Estado: Fase 1.1 cerrada. Avanzando a Fase 1.2.**

## 2026-07-02 — Fase 1.1: UPS formal + persistencia (implementada, esperando confirmación)

Nuevo paquete `domain/physiology/state/` — primera implementación real del Unified Physiological State, reemplazando el estado flotante en `session_state`.

### Añadido
- `domain/physiology/state/schema.py` — contrato tipado: `Provenance` (sensor_real/simulacion/derivado), `PhysiologicalDescriptor` (valor + unidad + procedencia + confianza, valida `confidence ∈ [0,1]`), `DomainState`, `PhysiologicalEvent`, `UnifiedPhysiologicalState`.
- `domain/physiology/state/models.py` — tablas SQLAlchemy (`PatientRecord`, `SnapshotRecord`, `ValueRecord`, `EventRecord`), inspiradas en `_archive/v2_backend_stack/db/models.py`.
- `domain/physiology/state/db.py` — engine SQLite (`data/biocore_ups.db`), `init_db()`, `make_session_factory()`.
- `domain/physiology/state/repository.py` — `create_patient`, `get_patient`, `save_state`, `get_latest_state`, `get_value_history`, `get_events`.
- `domain/physiology/state/builder.py` — `from_digital_twin_organism()`: construye un `UnifiedPhysiologicalState` leyendo `app/engines/digital_twin_organism.py` **sin modificarlo**. Valores medidos/simulados llevan la procedencia del llamador; valores derivados por el organismo (health_score, riesgos, etc.) siempre `Provenance.DERIVADO`. Eventos (`arrhythmia_risk_hr_extreme`, `low_hrv_autonomic_stress`, `hypoxia_spo2_critical`, `hypoxia_spo2_low`) detectados al construir el snapshot, con los mismos umbrales que ya usaba `DigitalTwinOrganism`.
- `tests/test_ups_state.py` — 3 pruebas: crear/recuperar paciente entre sesiones, consulta temporal de un valor (HRV) por ventana de tiempo, eventos persistidos como entidad de primera clase.
- Dependencia nueva: `sqlalchemy>=2.0.0` (`requirements.txt`, instalada en `.conda`).

### Verificado
- `python -m pytest tests/test_ups_state.py`: 3/3 passed.
- Resto de la suite (excluyendo 3 tests ya rotos antes de esta sesión — `test_api.py` sin `fastapi`, `test_arrhythmia_classifier.py`/`test_reasoning_engine.py` con imports desactualizados, duplicados por los `_new`): 7/7 passed.
- `streamlit run app/main.py`: HTTP 200. No se tocó ninguna vista existente.

### Alcance respetado
Solo dominios cardiovascular y respiratorio — no los 11 sistemas. No se conectó todavía a la UI de Streamlit (llega en 1.2/1.3).

**Estado: esperando confirmación del usuario antes de avanzar a Fase 1.2.**

## 2026-07-02 — Fase 0 aprobada + limpieza de riesgo cero

Aprobación del informe de auditoría de Fase 0. Decisiones registradas en `PLAN.md`. Ejecutado de inmediato (limpieza de riesgo cero, sin cambios de comportamiento):

### Eliminado
- `app/pages_legacy/`: 13 archivos huérfanos eliminados (los 9 archivos con nombre emoji que sí se usan vía `runpy` desde `app/supermodules/*/pages.py` se conservan intactos — ver detalle abajo).
- `app/dashboard.py` — archivo vacío, no importado por nadie.
- `app/config.py` — archivo vacío, no importado por nadie.
- `app/components/digital_twins_ui.py` — "3D" simulado (heatmap 2D / scatter), no conectado al flujo real del Digital Twin (`app/supermodules/twin_shell/`). Referencias a `DigitalTwinsUI` eliminadas de `app/components/__init__.py` y `app/supermodules/__init__.py`.
- `domain/signals/` (subpaquete completo) — shim de indirección pura vía `importlib.util` que reenviaba a `src/*.py`. Sin lógica propia.

### Corrección respecto al informe de Fase 0
El informe de auditoría original calificó `app/pages_legacy/` como "huérfano". Al ejecutar la limpieza se descubrió que 9 de los 21 archivos (los de nombre con emoji: `2_🔗_Multisensor.py`, `3_🎓_Education.py`, `4_👥_Patients.py`, `5_🤖_AI_Analysis.py`, `6_📋_ECG-12-Derivaciones.py`, `7_💨_Respiratory-Lab.py`, `8_🧠_EEG-Neuro-Lab.py`, `9_🦾_EMG_Muscle_Lab.py`, `10_📚_Guides.py`) sí están en uso: cada supermódulo correspondiente los ejecuta en tiempo real vía `runpy.run_path()` para renderizar su pestaña "Clínica". Solo se eliminaron los 12 archivos sin nombre de emoji (duplicados/huérfanos, no referenciados) más `1_📊_ECG_Monitor.py` (emoji, pero sin referente — `ecg_monitor` tiene su propia implementación completa).

### Revertido / redirigido
- `main.py` (raíz, pipeline CLI): los imports `from domain.signals.processing... / domain.signals.analysis...` se reemplazaron por imports directos `from src import (...)` — mismo comportamiento, sin la capa de indirección `domain/signals/`.
- `app/utils/__init__.py` y `app/supermodules/__init__.py`: eliminado el bloque `try: from shared.core.utils import * except Exception: pass` — `shared/` no existe en disco (import fantasma que siempre fallaba en silencio).

### Verificado
- `streamlit run app/main.py` arranca correctamente (HTTP 200) con el entorno `.conda` del proyecto.
- `python main.py` (pipeline CLI) importa correctamente tras el redireccionamiento a `src/`.
- `python -m py_compile` sobre todos los archivos tocados: sin errores de sintaxis.

### Decisiones documentadas (sin ejecutar todavía — difieren a fases posteriores)
- Base de datos: SQLite + SQLAlchemy, reutilizando el esquema de `_archive/v2_backend_stack/db/models.py` como punto de partida.
- UPS: se promoverá `app/engines/digital_twin_organism.py` a Unified Physiological State formal (Fase 1.1).
- Ganadores de duplicación para lo que toca Fase 1: `src/signals/` (señales), `biomedical/reasoning_engine.py` (motor de razonamiento), `clinical/` (capa clínica principal), `visualization/` (paquete de visualización para la app Streamlit).
- IA: `app/ai_copilot.py` y `app/biomedical_tutor.py` se refunden en el narrador clínico de Fase 1.3.

Ver `PLAN.md` para el detalle completo de Fase 1 (1.1–1.4).
