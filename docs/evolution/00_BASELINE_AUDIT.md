# 00 · Auditoría de base: qué funciona hoy y qué no

**Fase 0 del documento «BIOCORE AI: cómo convertirlo en una plataforma biomédica extraordinaria» (noviembre 2026), «Master Evolution Directive», §6 y §10.** Sin cambios funcionales: este documento solo describe.

- **Fecha:** 2026-11-19.
- **Commit auditado:** `db4b16b` (rama `t6-acoplamientos`, que contiene `main` = `c6998fe` más la T6 y la T6.1, sin unir todavía).
- **Método:** lectura del código y de `CLAUDE.md`, `CHANGELOG.md` y `docs/INVENTARIO_BIOCORE_2026-11-05.md`. Además, tres mediciones por ejecución:
  - la suite completa (`02_REGRESSION_BASELINE.md`);
  - un recorrido con AppTest de las 34 páginas y de las 7 fuentes alternas de los laboratorios, que juntó todo el texto visible con un rótulo heurístico, de demostración o pendiente;
  - un análisis estático de importaciones (`01_DEPENDENCY_MAP.md`).
- **Lo que no se verificó:** el despliegue en Streamlit Cloud, los equipos reales (ESP32, OpenBCI, Muse) y las llamadas reales a los modelos de lenguaje (no hay clave en el entorno).

El inventario del 5 de noviembre **no** describe el estado actual: muchos de sus hallazgos se corrigieron después (sección 3). Cuando este documento dice «hoy», se refiere al commit auditado.

## 1. Las cuatro categorías

### 1.1 Implementado y probado

Existe código en la ruta de ejecución de la app y hay pruebas que fijan su comportamiento.

| Área | Qué hace | Pruebas principales |
|---|---|---|
| UPS | Estado de 4 dominios con procedencia por valor. Contrato de derivados (`DERIVED_CONTRACT`), compuertas anti-órgano-fantasma, persistencia SQLite. | `test_ups_derived_contract.py`, `test_ups_phase1_frontier.py`, `test_fase0_*` |
| Paciente compuesto | Último valor de cada descriptor con su origen y su edad. Las copias de un compositor se saltan (T6). | `test_ups_composed_patient.py`, `test_t6_compositor_reglas.py` |
| Acoplamientos | Dos reglas firmadas (BAR con techo 3.0 y vigilia; hipoxia). Escenarios bloqueados, política de no combinar, compositor por regla. | `test_coupling_*.py`, `test_t6_*.py`, `test_t6_1_techo_bar.py` |
| ECG | FC por TKEO validada contra MIT-BIH, papel ECG único, 12 derivaciones con lectura por criterios, detector de bloqueo de rama contra PTB-XL. | `test_ecg_hr_detector_consolidation.py`, `test_bbb_detector_validation.py`, `test_twelve_lead_measure.py`, `test_pulido_profesional.py` |
| Respiración | Detector reescrito contra golden tests: FR, apneas (Berry 2012) y SpO₂ del modelo. | `test_respiratory_detector_golden.py` y 8 archivos `test_respiratory_*.py` más |
| HRV | SDNN, RMSSD y pNN50; espectro; RSA; métricas no lineales sobre series sintéticas de verdad conocida. | archivos `test_hrv_*.py` y `test_rsa*.py` |
| EEG | Potencias por banda (Welch), DAR/TBR/BAR y exponente aperiódico (FOOOF). EEG en vivo por BrainFlow/LSL con simulador. | `test_eeg_*.py` (5 archivos) |
| EMG | RMS y frecuencia mediana, sensor MyoWare con simulador; un CSV no escribe al gemelo. | `test_biosensors_emg.py`, `test_emg_analyzer.py`, `test_emg_lab_save_to_twin.py` |
| Biosensores | Pulso por luz (Elgendi 2013) y temperatura DS18B20, con simulador y protocolo `BIO:`. | `test_biosensors_ppg_temp.py` |
| Gemelo | Lee al paciente compuesto con el organismo encima. Cada tarjeta lleva su procedencia; hay tarjeta muscular. | `test_twin_paciente_compuesto.py`, `test_twin_os_phase1.py` |
| Hemodinámica | Lazo cerrado RCR en sano, hipertensión y sepsis (shock establecido). | `test_hemodynamics_closed_loop*.py`, `test_hemodynamics_baroreflex.py`, `test_baroreflex_visible.py` |
| Ruta | Cinco unidades con instrumentos incrustados, bancos firmados y cierres con acoplamientos. | `test_ruta_corazon.py`, `test_ruta_unidades_t4.py`, `test_t6_acoplamientos_ruta.py` |
| Navegación | Cinco destinos; ninguna dirección vieja se rompe. | `test_t5_navegacion.py`, `test_fase1_t1_navegacion.py` |
| Contenido firmado | Teoría citada 1–3, bancos firmados, casos guiados, textos legales. | `test_fase1_t2_teoria.py`, `test_banco_*.py`, `test_guided_case*.py`, `test_legal.py` |
| Narrador e IA | Sin clave falla explícito; privacidad por proveedor; respuestas solo con la base firmada. | `test_narrator.py`, `test_narrator_gemini.py`, `test_citation_tutor.py` |
| Idioma y diseño | Sin inglés visible, contraste WCAG medido y una sola fuente de color. | `test_fase1_t2_pulido.py`, `test_fase1_t1_diseno.py`, `test_i18n.py` |

### 1.2 Implementado, no suficientemente probado

- **Equipos reales:** ESP32 + AD8232, la placa de biosensores y OpenBCI/Muse/Unicorn solo se prueban con simuladores y pseudo-terminales. Ninguna prueba ejercita un equipo real. Cobertura medida: ver `02_REGRESSION_BASELINE.md`.
- **Narrador con Anthropic y con Gemini:** nunca se ejecutó contra la API real (`CLAUDE.md`, «no verificado por ejecución»).
- **Taller 3D (TC/RM → malla):** las pruebas fijan que la malla se genera, no su fidelidad anatómica.
- **Calidad de señal en vivo:** los umbrales de `hardware/*/quality.py` están probados contra sus propias cifras, no contra grabaciones reales con artefactos conocidos.
- **Pruebas de render:** muchas pruebas de AppTest fijan textos, no valores clínicos. El inventario del 5 de noviembre ya lo advirtió: «líneas ejecutadas ≠ valores verificados».

### 1.3 Diseñado, no implementado

- **Del documento nuevo (§3 y §5):**
  - los contratos `BiomedicalSignal`, `PhysiologicalFeature`, `PhysiologicalRelationship`, `SimulationScenario` y `ExperimentRecord`;
  - el *Physiological Intelligence Graph*;
  - el *Physiological Replay*;
  - el *Biomedical Research Studio*;
  - el *AI Biomedical Scientist* con herramientas estructuradas.

  Hoy existen piezas que se les parecen (sección 2 de `03_ARCHITECTURE_DECISIONS.md`), pero ningún contrato con esos campos.
- **Ficha 2 de acoplamiento** (contracción → FC): firmada con la opción A, pero espera la calibración de la contracción máxima (CVM) del EMG, que no existe.
- **«Mi progreso» y «Docente»:** los paneles existen y tienen pruebas, pero no se montan hasta que haya identidad (decisión 1).
- **Base real con cuentas** (opción A de persistencia): diferida por decisión de Luis.
- **Reglas de acoplamiento evaluadas fuera de la Ruta:** los escenarios y el gemelo no llaman a `apply_couplings` (salvo el botón del gemelo).

### 1.4 Descartado o diferido

- **Retirados a propósito (decisiones firmadas):**
  - fase 0: `health_score`/`risk_score`, estados transversales, riesgo global, coherencia y resiliencia;
  - el «Índice de estrés» de Biomarcadores;
  - «Sensibilidad > 99 %» del ECG;
  - el botón «Entropía» de Multisensor (fachada, según el inventario);
  - el selector «Capa de Exploración Cognitiva»;
  - el «Clasificador de ECG» del gemelo (oculto, en revisión).
- **Material sin fuente que quedó en el código sin montar:** `_ecg_monitor_unsourced_material` y `_biomarkers_ghost_history`.
- **Fuera del alcance de la ruta integrada:** el dominio metabólico, salir de Streamlit, y reglas de acoplamiento sin firma.

## 2. Defectos conocidos hoy

1. **Capas invertidas:** 16 importaciones de `domain/` hacia `app/` (`app.engines` y `app.utils.physiological_state`). El dominio depende de la app: ver `01_DEPENDENCY_MAP.md`.
2. **Código muerto que confunde:**
   - `app/utils.py` (560 líneas) queda tapado por el paquete `app/utils/`: `import app.utils` carga el paquete y el archivo nunca se ejecuta;
   - lo que solo ese archivo importaba (`signals/`, `dashboards/`, `src/utils/`, `src/rural_health/`) tampoco lo alcanza la app;
   - hay otros módulos sin uso en la lista de `01_DEPENDENCY_MAP.md`.
3. **Heurísticas visibles:** 88 textos distintos en pantalla llevan «Heurística», «Criterio BIOCORE», «Pendiente de validación» o «demo». La sección 4 los inventaría con un plan para cada uno (pedido de Luis del 2026-11-19).
4. **El gemelo y `twin_shell/`:** el índice de riesgo heurístico y la compliancia C «pendiente de validación» viven en código de otra persona del equipo.
5. **Persistencia compartida en internet:** en Streamlit Cloud, la base del UPS y la de los cuestionarios son de todos y se borran al reiniciar. Está declarado (opción B), pero no hay aislamiento por persona.

## 3. Defectos históricos ya corregidos (del inventario del 5 de noviembre)

| Hallazgo del inventario | Estado hoy | Dónde |
|---|---|---|
| Respiración: FR = 60 constante y AHI = 0 siempre («roto y no honesto») | Corregido: detector reescrito contra golden tests; la sigla AHI se retiró del laboratorio | CHANGELOG, «Cierre del arco Respiratory» |
| Multisensor: «Health Score» con bandas y valores por defecto sin cita | Retirado | CHANGELOG fase 0 |
| Botón «Entropía» que no calculaba nada (fachada) | Retirado | CHANGELOG tanda 1 |
| Organismo con valores por defecto mostrados como datos | Corregido: el organismo no tiene defaults; «sin dato» con motivo | CHANGELOG fase 0, `test_fase0_organismo.py` |
| Explicabilidad «SHAP/LIME» que solo narraba diferencias | Retirada del texto; `shap`/`lime` salieron de `requirements.txt` | CHANGELOG 2026-11-17 |
| Guardar un laboratorio borraba los demás valores del banner | Corregido con el paciente compuesto | T0 |
| El gemelo no veía lo que medían los laboratorios | Corregido | T1 |

## 4. Brechas de validación científica: todo lo heurístico que se ve

Pedido de Luis (2026-11-19): «todo lo que aparezca como heurístico se arregle por algo que está citado […] ya no quiero que las cosas heurísticas inunden la plataforma, termina con todas». Respuestas del mismo día a las preguntas de alcance:

- **Biomarcadores:** sale del menú.
- **Fusión de sensores:** pierde los canales demo.
- **Índice de riesgo del gemelo:** se retira, con aviso a quien lleva `twin_shell/`.
- **Umbral sin fuente:** «quitar el juicio, dejar la medida».

> **Estado (2026-11-19, rama `heuristicas-citadas`):** ejecutado. Lo que se hizo con cada fila está en el CHANGELOG («Tanda de heurísticas»). Diferencias con esta tabla: la compliancia C del gemelo y la capacitancia venosa 2× de la sepsis siguen pendientes de la firma de Luis (no se encontró una fuente que dé esas cifras para este modelo); los umbrales de calidad de los equipos en vivo siguen siendo internos, sin la palabra en pantalla.

**Tratamientos:**

| Tratamiento | Qué significa |
|---|---|
| Citar | El valor sale de un método o una cifra publicada. Se pone la cita y el rótulo deja de decir «heurística». |
| Re-rotular | Ya tenía fuente (o es aritmética o una definición), pero llevaba un rótulo equivocado. |
| Quitar el juicio | El umbral no tiene fuente: se muestra la medida sin la etiqueta que dependía de él. |
| Retirar | Pedido explícito de Luis. |
| Firma | El punto necesita una decisión clínica de Luis. |

En la columna «Fuente» se marca así lo verificado:

- ✔ texto completo, leído el 2026-11-19;
- ◐ la cifra viene de una obra de referencia que cita sus fuentes primarias.

| # | Qué se ve (dónde) | Hoy | Tratamiento | Fuente |
|---|---|---|---|---|
| 1 | Biomarcadores completo (`biomarcadores`) | Modo demostración; PLV y «Disposición para el aprendizaje» con rótulo de heurística | Retirar del menú; la dirección sigue y dice por qué | Decisión de Luis |
| 2 | Canales demo de Fusión de sensores (FC y SpO₂ sobre señales generadas) | Heurística | Retirar; quedan los sensores en vivo | Decisión de Luis |
| 3 | Índice de riesgo heurístico del gemelo (`twin_shell/pages.py:1860`) | Pesos fijos | Retirar con un cambio mínimo y aviso al dueño | Decisión de Luis |
| 4 | Presión barométrica estimada (Calculadoras) | Heurística, aunque ya cita ISO 2533 | Re-rotular: fuente citada | ISO 2533:1975 (ya en el código) |
| 5 | Gradiente A–a esperado «edad/4 + 4» | Heurística | Citar y cambiar la fórmula a 2.5 + 0.21 × edad | ◐ Calculadora «A-a Gradient» del Manual MSD, que cita a Mellemgaard 1966 (Acta Physiol Scand 67:10–20) y a Kanber 1968 (Am Rev Respir Dis 97:376–81) |
| 6 | Índice cardiaco «rango orientativo 2.5–4.0 (sin cita firme)» | Sin cita | Citar | ◐ StatPearls, «Physiology, Cardiac Index»: «The normal cardiac index value should range between 2.5 and 4 L/min/m2» |
| 7 | ECG 12 derivaciones: FC y SNR por derivación | Heurística | Re-rotular con su método (FC: detector TKEO validado contra MIT-BIH; SNR: su definición en el código) | Informe de validación del repositorio |
| 8 | ECG: «irregular si CV ≥ 8 %, heurística BIOCORE» | Heurística | Quitar el juicio; queda el CV | No se encontró fuente para el 8 % |
| 9 | ECG: «sensibilidad menor que 0.80 en S, V, F, Q (Criterio BIOCORE, sin cita)» | Pendiente | Quitar el juicio; queda la sensibilidad por clase medida | — |
| 10 | ECG 12 derivaciones: «Mediciones [Criterio BIOCORE]» del latido mediano | Criterio BIOCORE | Re-rotular: medición sobre el latido mediano [K2007]; los umbrales técnicos se describen en «Cómo se calcula» | [K2007] ya firmado |
| 11 | EEG: «Banda dominante — Heurística» | Heurística | Re-rotular: Welch con las bandas del glosario IFCN | Kane 2017 (ya en el código) |
| 12 | EEG: «Clasificación: Despierto relajado — Heurística» | Heurística | Quitar el juicio; queda la banda dominante | — |
| 13 | EEG en vivo: «Umbrales: de ingeniería, sin cita clínica» | Heurística | Buscar el criterio publicado de canales defectuosos (PREP, Bigdely-Shamlo 2015); si no aplica, quitar el juicio | Por verificar |
| 14 | EMG: «RMS — Criterio BIOCORE» | Criterio BIOCORE | Re-rotular: tema A5 firmado | Teoría citada 2 |
| 15 | EMG: «Frecuencia mediana — Heurística» | Heurística | Re-rotular: tema A7 firmado | Teoría citada 2 |
| 16 | EMG: «Activación muscular (promedio/pico, no %MVC) — Criterio BIOCORE» | Criterio BIOCORE | Citar la normalización al pico dinámico o retirar | Por verificar (Burden 2010) |
| 17 | Respiración: FR, duración del ciclo, variabilidad y respiraciones detectadas — Criterio BIOCORE | Criterio BIOCORE | Re-rotular: definiciones (FR = respiraciones por minuto) probadas contra golden tests | Definición |
| 18 | Respiración: apneas (≥ 10 s) — Criterio BIOCORE | Criterio BIOCORE | Re-rotular: regla de Berry 2012 | Berry 2012 (ya firmado) |
| 19 | Respiración: tipo de apnea central y obstructiva — Criterio BIOCORE; mixta — Pendiente | Criterio / Pendiente | Citar las tres reglas. «Ausente» se mide con la misma caída ≥ 90 % que Berry usa para el flujo; se dice así | ✔ Manual AASM v2.0 (Berry y cols. 2012), reglas de obstructiva, central y mixta |
| 20 | Respiración: retardo Tc = 15 s «Valor BIOCORE» | Valor BIOCORE | Citar y cambiar a 19.4 s | ✔ Kwon y cols. 2020, Sleep Med 75:8–11: mediana del tiempo pulmón-dedo 19.4 s en 598 participantes de MESA, medido de la reanudación de la respiración al nadir de SpO₂ |
| 21 | Respiración: «Patrón regular si CV < 10 %» | Heurística | Quitar el juicio; queda el CV | — |
| 22 | Respiración: amplitud pico a pico y «ciclos objetivo en 30 s» | Heurística | Re-rotular: medida descriptiva y aritmética | — |
| 23 | Respiración: irregularidad 0.20 del generador atáxico | Heurística | Re-rotular: parámetro de la simulación | — |
| 24 | Respiración: piso de la SpO₂ «Criterio BIOCORE: solo hace posibles los parámetros» | Criterio BIOCORE | Re-rotular: parámetro de la simulación | — |
| 25 | «¿Qué pasa si…?»: «sin cambio» si el cambio es < 2 % (Criterio BIOCORE, HEURISTIC) | Heurística | Reemplazar por la resolución mostrada: «sin cambio» si el valor redondeado no cambia | Definición |
| 26 | HRV no lineal y RSA: «PENDING_VALIDATION» y «demostración» | Pendiente | Re-rotular: métodos citados, calculados sobre series simuladas; sin interpretación clínica | Ya citados en el código |
| 27 | RSA: «al menos 10 periodos de la frecuencia más baja (Criterio BIOCORE)» | Criterio BIOCORE | Buscar fuente; si no hay, quitar el juicio | Por verificar |
| 28 | Pulso por luz: valores «Pendiente de validación»; piso de 5 cuentas y 25 % de irregularidad | Heurística | Re-rotular el método (Elgendi 2013); los avisos de calidad dicen el hecho del equipo | Hoja de datos del MAX30102 |
| 29 | Temperatura: «¿Ya se puede leer? — Heurística» (< 0.1 °C/min) | Heurística | Buscar fuente del tiempo de equilibrio; si no hay, mostrar la pendiente sin el juicio | Por verificar |
| 30 | Calidad en vivo de ECG, EMG y EEG (`QualityHeuristics`) | Heurística | Separar los hechos del equipo (saturación del ADC, desconexión del AD8232) de los umbrales sin fuente | Hojas de datos |
| 31 | Gemelo: compliancia C «pendiente de validación» y capacitancia venosa 2× en sepsis (sin cita) | Pendiente | Buscar fuente; requiere firma de Luis | Por verificar |
| 32 | Escenario «Sano»: rangos de estrés, cognición y fatiga | Sin fuente (no rotulado) | Fuera de este pedido; se anota | — |
| 33 | ECG Monitoreo: «Fuente: demo», «FC demo» | Simulación llamada «demo» | Re-rotular «simulación» | — |

Los tres compositores (el de la Ruta, el neurocardiaco y el motor) llevan el techo de la regla BAR como «Criterio BIOCORE»: ninguna fuente da un BAR máximo. Luis lo eligió con literatura y lo confirmó el 2026-11-19, así que queda como criterio firmado y no como heurística.

## 5. Riesgos de los cambios de arquitectura

- **Mover `app/engines` a `domain/`** (corregir la inversión de capas): toca `domain/`, que está vigilado por `test_ups_builder_schema_and_engine_untouched`. Además, unas 30 importaciones cambian de ruta. Se necesita un plan de compatibilidad con reexportaciones.
- **Borrar código muerto:** parte de él tiene pruebas, como `biomedical/reasoning_engine.py` y `src/signals/ecg/advanced_patterns.py`. Borrarlo exige aprobación (regla 7) y quitar o mover esas pruebas.
- **Contratos nuevos:** si se crean en paralelo al UPS, rompen la regla «no crear un UPS paralelo». Tienen que ser adaptadores sobre el `UnifiedPhysiologicalState`.
- **Cambiar el vocabulario de procedencia:** las pruebas de AppTest fijan textos exactos de las insignias («Heurística (de ingeniería…)»). Cada cambio de rótulo mueve varias pruebas a propósito.
- **`twin_shell/` es de otra persona del equipo:** todo cambio ahí se coordina.
