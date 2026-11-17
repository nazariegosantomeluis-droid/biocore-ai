# Plan de UX: ruta de aprendizaje y modo Paciente

Fase 0 · 17 de noviembre de 2026 · rama `ux-ruta-aprendizaje`, creada desde `main` (commit `1dfd84a`).
Estado: borrador para tu visto bueno. En esta fase no hay código.

Este documento es el plan de un rediseño acotado (la Academia como ruta y el modo Paciente). No sustituye a `CLAUDE.md` ni a `CHANGELOG.md`: si choca con `CLAUDE.md`, gana `CLAUDE.md` y la diferencia queda en la sección 14 como decisión.

---

## 0. Bloqueos y hallazgos de partida

1. **La rama `biocore-v2` no existe en GitHub.** El remoto tiene `main` y `respaldo-mezcla-20261021`. Partí de `main` (17 de noviembre), el último estado que Luis fusionó.
2. **El kit de marca no está en el repositorio.** `docs/marca/Biocore-Kit-de-marca-v1.1/` no existe en ninguna de las dos ramas, ni en tu Google Drive, ni como diseño de Canva. Sin el kit faltan los valores de los tokens, el isotipo en SVG, los íconos, los sellos y los nombres nuevos de las áreas (página 7 del manual). Este plan usa los nombres de token que diste (`trazo`, `nucleo`, `tinta-2`, `estado-*`) y deja los valores al kit.
3. **`visualization/art/css.py` no está en `main`.** Vive en la rama de respaldo del 21 de octubre, que Luis describe como «estado mezclado (mi trabajo validado + aporte externo sin auditar)». Esa rama confirma algo útil: Streamlit sirvió Figtree y Noto Sans en local con `[[theme.fontFaces]]` y `server.enableStaticServing` (licencia OFL 1.1). No copio archivos de esa rama sin auditar: las fuentes salen de `02-Tipografias` del kit o de su origen (`@fontsource-variable` 5.3.0).
4. **PhysioNet no responde desde este entorno.** Los registros reales con anotación de experto (MIT-BIH, QT Database) necesitan ese acceso en la Fase 2, o que Luis corra la herramienta de descarga en su computadora.

Para empezar la Fase 1 necesito `biocore-v2` en el remoto, o al menos la carpeta `docs/marca/`.

---

## 1. Skills: cuáles uso y para qué

| Skill | ¿Está? | Uso en este trabajo |
|---|---|---|
| stop-slop | Sí. La clonaste en `~/.claude/skills/stop-slop` y existe la versión con reglas en español (`anthropic-skills:stop-slop`) | Todos los textos de la interfaz y este plan |
| design: accessibility-review | Sí | Auditoría WCAG 2.1 AA en cada fase, sobre las capturas |
| design: design-critique | Sí | Crítica de las capturas antes de enseñártelas |
| design: ux-copy | Sí | Botones, retroalimentación, avisos y estados vacíos |
| design: design-system | Sí | Inventario y API de los componentes de la Fase 1 |
| legal: compliance-check y legal-risk-assessment | Sí | Fase 4: consentimiento, aviso de privacidad y lista para el abogado |
| security-review | Sí | Al cerrar cada fase que toque datos de pacientes |
| ui-ux-pro-max | No | Pendiente de instalar |
| frontend-design | No | Pendiente de instalar |
| marketing-skills (onboarding, marketing-psychology) | No. Las `marketing:*` instaladas cubren campañas y contenido, no onboarding ni psicología | Pendiente de instalar |

Las tres que faltan se instalan como stop-slop, con `git clone` a `~/.claude/skills/`. Este contenedor es temporal y lo instalado desaparece al reciclarse; si las quieres en cada sesión, van en el script de configuración del entorno. Mientras falten, sigo tus reglas: el kit manda en color, tipografía y forma, y de ui-ux-pro-max solo tomaría reglas de UX y su lista de calidad.

---

## 2. Mapa de pantallas actual

`st.navigation` con 22 páginas, declaradas en `_page_specs()` de `app/main.py`:

| Sección | Páginas |
|---|---|
| Inicio | Inicio: tres puertas (Aprender, Practicar, Explorar) y un enlace a Ajustes |
| Aprender | Teoría (Academia), Referencias de los laboratorios, ECG en 3D, Bibliografía |
| Practicar | Quiz de la Academia, Caso ciego, Desafío ECG de 12 derivaciones, Cuestionarios de los laboratorios, Casos clínicos del simulador |
| Explorar | Gemelo digital, ECG, Multisensor, Respiratorio, EEG, EMG, HRV, Biomarcadores, Calculadoras clínicas, Flujo de pacientes, Crea tu modelo 3D |
| Ajustes | Ajustes (clave de IA de Anthropic o de Gemini) |

Piezas que ya existen y sirven a la ruta:

- `educational/quiz_bank.py`: `QuizQuestion` con enunciado, opciones, explicación y fuente.
- `educational/learning_analytics.py`: base SQLite local (`data/local/biocore_learning.db`, fuera de git) con cada respuesta, análisis de ítems y Elo.
- `educational/rural_mode.py`: progreso por estudiante en JSON (`data/local/progress/`), con escritura atómica.
- `src/signals/ecg/twelve_lead_synth.py`: 13 escenarios con verdad conocida (`TwelveLeadTruth`: inicios del QRS, PR, QRS, QT, ritmo y frecuencia).
- `app/utils/ecg_paper.py`: el único componente que dibuja un ECG (papel a escala, pulso de calibración, rótulo de velocidad y ganancia).
- `docs/contenido/teoria_citada.md` y `teoria_citada_2.md`: la única fuente de texto médico nuevo, con clave de cita.
- `data/reference_signals/`: dos registros reales. PTB s0010_re (12 derivaciones y Frank, 20 s a 500 muestras/s; mujer de 81 años con infarto agudo inferolateral) y CAP n16 (EEG en vigilia, 5 derivaciones, 30 s a 100 muestras/s).

Lo que falta: identidad (el «ID del estudiante» de la Academia es texto libre), XP, racha, meta, ruta y bienvenida. «Mi progreso» y «Docente» no existen por la decisión 1: no había identidad ni persistencia que los respaldara.

---

## 3. Mapa de pantallas nuevo

Los nombres de las secciones son provisionales. Los finales salen de la página 7 del manual.

### Modo Aprender

| Pantalla | Qué hace | Base |
|---|---|---|
| Bienvenida | 3 pasos: carrera, meta diaria, prueba de nivel opcional | Nueva |
| Ruta (inicio de la Academia) | 5 unidades por sistema, con sus lecciones y el repaso | Nueva |
| Lección | 8 a 12 ejercicios, barra de progreso, un botón principal | Nueva |
| Cierre de lección | XP, precisión, tiempo y meta de hoy | Nueva |
| Repasa tus errores | Los ejercicios que fallaste, hasta acertarlos | Nueva |
| Mi progreso | Racha, XP por día, logros y las reglas de cada uno | Nueva: monta lo que la decisión 1 dejó fuera |
| Biblioteca | Teoría, Referencias, ECG en 3D, Bibliografía | Mismo contenido |
| Práctica libre | Los cinco cuestionarios y casos de hoy | Misma lógica |
| Laboratorios | Gemelo y laboratorios con fuentes simuladas o de bases públicas | Mismos cálculos |

### Modo Paciente

| Pantalla | Qué hace |
|---|---|
| Pacientes | Lista de códigos (P-0142…), nuevo paciente, borrar y registro de accesos |
| Nuevo paciente | Consentimiento, propósito y aviso de privacidad. Sin eso no aparece la carga |
| Carga o sensor | Archivo o sensor; anonimiza y muestra qué quitó |
| Vista del paciente | Banda fija, lecturas con sello y calidad de la señal |
| Laboratorios con datos del paciente | ECG, EEG, EMG, Multisensor y 3D, con la banda arriba |
| Informe | PDF en tema Papel con la leyenda obligatoria |
| Convertir en caso docente | Consentimiento educativo y revisión de la anonimización |

### Ajustes (los dos modos)

Perfil, meta diaria, tema (Monitor o Papel), IA (local con Ollama, Anthropic o Gemini) y privacidad.

### Cambios en la navegación

- `main()` arma `st.navigation` en cada ejecución, así que el menú puede cambiar con el modo. En Aprender no aparecen las páginas de pacientes. En Paciente no aparece la ruta.
- Arriba del menú lateral, un control de dos opciones: «Aprender» y «Paciente». Al pasar a Paciente aparece el aviso de una línea.
- Las fuentes que traen datos de una persona salen del modo Aprender: CSV cargado, placa ESP32, EEG en vivo, MyoWare, MAX30102, DS18B20, serie RR pegada, DICOM o NIfTI y tabla de cohorte. En su lugar, el laboratorio dice: «Para cargar un archivo o conectar un sensor, cambia a modo Paciente.»
- `LEGACY_ENTRIES` y `tests/test_fase1_t1_navegacion.py` se actualizan con el mapa nuevo. Ninguna página actual desaparece.

---

## 4. Los dos modos

| | Aprender | Paciente |
|---|---|---|
| Datos | Registros públicos anonimizados y simulaciones | Archivos cargados y sensores de una persona real |
| Sello | «Registro real · fuente» o «Simulación» | Procedencia de cada lectura (sensor, archivo) |
| Juego | Ruta, XP, racha, meta, logros, «Comprobar», «Equivócate aquí» | Ninguno |
| Respuesta | «Correcto» (`nucleo` y palomita) o «Todavía no» (`tinta-2` e ícono) | Sin calificación |
| Colores `estado-*` | No | Sí, siempre con su palabra |
| Animación | La espiga del isotipo late al acertar | Ninguna |
| Errores | Se permiten y vuelven al final de la lección | Se previenen: confirmación, unidades visibles, rangos válidos y deshacer |
| IA | La que configures | Solo local (Ollama); la nube, con tu permiso en ese momento |
| Almacén | `data/local/` (progreso) y `data/biocore_ups.db` (simulaciones) | Almacén cifrado fuera del repositorio |
| Vocabulario | Ejercicio, respuesta, fuente | Lectura, hallazgo, patrón compatible con |

**A la vista.** En Aprender, el encabezado de la ruta (racha y meta de hoy) y el `trazo` como único color vivo. En Paciente, la banda fija «Paciente real · P-0142 · anonimizado» en todas las vistas, sin encabezado de la ruta y sin animación.

**Al entrar a Paciente:** «Aquí trabajas con datos de una persona real. No hay puntos ni rachas.»

**Separación técnica**, para que ningún dato de paciente llegue al progreso:

- Bases distintas. El progreso vive en `data/local/biocore_learning.db`. Cada paciente tiene su UPS en el almacén cifrado.
- `app/utils/patient_session.py` elige el engine según el modo: en Paciente, el UPS cifrado del paciente activo; en Aprender, el de hoy.
- Una prueba recorre con AppTest todas las páginas del modo Paciente y falla si encuentra «XP», «racha», «Correcto», «Todavía no», «Equivócate aquí» o un componente de juego.
- Los módulos de progreso no importan nada del paquete de pacientes, y una prueba lo verifica.

---

## 5. La ruta

### Unidades

Corazón, Respiración, Cerebro, Músculo y Sistema autónomo. Cada unidad tiene de 3 a 5 lecciones y un repaso al final.

- Las lecciones de una unidad van en orden. Recomiendo unidades abiertas: los sistemas no dependen uno de otro, y la carrera sugiere por cuál empezar.
- Estados de un nodo: **bloqueada** (falta la anterior), **disponible** y **completada**. Cada estado lleva ícono y palabra.
- El repaso se abre al completar todas las lecciones de la unidad.
- Una lección sin teoría firmada no se muestra. La unidad dice «En preparación» y el motivo.

Teoría firmada que ya hay para cada unidad:

| Unidad | Temas firmados | Registro real en el repo |
|---|---|---|
| Corazón | 1 papel, 2 frecuencia, 3 ondas e intervalos, 4 y 5 derivaciones [MCM] [K2007] | PTB s0010_re |
| Respiración | 6 NEWS2, 7 patrones respiratorios, 10 estudio de sueño | Ninguno: el generador respiratorio es simulación |
| Cerebro | 8 bandas del EEG [IFCN2017] | CAP n16 |
| Músculo | A1 a A9 (EMG de superficie) | Ninguno: la señal demo es simulación |
| Sistema autónomo | B1 a B8 (HRV y arritmia sinusal respiratoria) | Ninguno propio; los RR de PTB s0010 sirven si Luis firma su anotación |

### Anatomía de una lección

- Arriba: «Salir» (pide confirmación si ya respondiste algo) y la barra de progreso con texto: «4 de 10».
- Centro: el ejercicio. El sello de la señal va debajo de la figura.
- Abajo, fijo: un solo botón principal. Dice «Comprobar», inactivo hasta que respondas, y luego «Continuar».
- Sobre el botón aparece el panel de respuesta: acierto o «Todavía no», una o dos frases de explicación y la fuente con su sello.
- Un ejercicio fallado vuelve una vez al final de la cola. La lección termina cuando la cola se vacía.
- Sin vidas, sin corazones, sin temporizador.
- Durante la lección, el menú lateral se oculta y vuelve al salir.

### Tipos de ejercicio

| Tipo | Cómo respondes | De dónde sale la clave | Tolerancia |
|---|---|---|---|
| Marcar la onda P, el QRS o la T | Encierras la onda con dos cursores: deslizador de rango con teclado, o recuadro con el puntero sobre la tira | Verdad del generador (simulación) o anotación de experto (registro real) | El centro de tu selección cae dentro de la onda y la selección no la rebasa más de 40 ms por lado. Criterio BIOCORE |
| Medir un intervalo (RR, PR, QT) | Dos cursores sobre la tira; el valor en ms cambia mientras los mueves | La misma | ±40 ms: un cuadro pequeño a 25 mm/s [MCM]. Criterio BIOCORE |
| Elegir el ritmo | 3 o 4 tarjetas | Escenario del generador o anotación de ritmo de la base | Exacta |
| Valor con unidad | Campo numérico y selector de unidad (lpm, ms, s, mV, Hz) | La verdad, o 60/RR de la clave | ±5 %, el error que deja medir el RR con ±40 ms a 75 lpm. La unidad debe coincidir. Criterio BIOCORE |
| Ordenar los pasos | Tocas los pasos en orden, cada uno recibe su número y «Deshacer» quita el último | Tema firmado | Exacta |
| Unir señal con órgano | Un selector de órgano por tira | Base de origen del registro | Exacta |
| Opción múltiple | Tarjetas | Tema firmado | Exacta |

**La clave también declara su procedencia** (Art. I):

- En una simulación, la clave es la verdad del generador (`TwelveLeadTruth`), sin ruido. Nunca lo que mide un analizador.
- En un registro real, la clave es la anotación de la base (MIT-BIH: latidos y ritmo; QT Database: inicio y fin de P, QRS y T marcados por expertos) o una anotación que Luis firme. Nunca un detector corriendo en vivo.
- Cada tolerancia lleva su criterio y su sello.

### Lección 1 de Corazón: «Leer el papel y las ondas» (Fase 2)

Diez ejercicios. Cada explicación sale de los temas firmados 1 a 3.

| # | Ejercicio | Señal | Fuente |
|---|---|---|---|
| 1 | Une cada señal con su órgano: ECG y EEG | PTB s0010 (II) y CAP n16, registros reales | [MCM] tema 3, [IFCN2017] tema 8 |
| 2 | ¿Cuánto dura un cuadro pequeño a 25 mm/s? | Sin señal | [MCM] tema 1 |
| 3 | Marca el QRS | Simulación, escenario normal | [MCM] tema 3 |
| 4 | Marca la onda P | Simulación, escenario normal | [MCM] tema 3 |
| 5 | Marca la onda T | Simulación, escenario normal | [MCM] tema 3 |
| 6 | Ordena las ondas de un latido | Sin señal | [MCM] tema 3 |
| 7 | Mide el intervalo RR | PTB s0010 (II), si Luis firma la anotación; si no, simulación | [MCM] tema 2 |
| 8 | Escribe la frecuencia cardiaca con su unidad | La tira del ejercicio 7 | [MCM] tema 2: 60 / RR |
| 9 | Mide el QRS | Simulación | [MCM] tema 3: 0.06 a 0.11 s |
| 10 | ¿Este ritmo es regular o irregular? | Simulación: escenarios normal y fibrilación auricular | [MCM] tema 2 |

La anotación de s0010 sigue el método del banco del detector (`docs/validation/ecg_hr_detector_bank`): genero una hoja con la tira y las marcas propuestas, Luis la revisa y la firma, y la anotación firmada se guarda junto al registro.

Textos de ejemplo:

- Acierto: «Correcto. Este QRS dura 90 ms. En adultos, la referencia va de 0.06 a 0.11 s [MCM].» Sello: «Simulación · generador de 12 derivaciones, verdad conocida».
- Error: «Todavía no. El QRS de esta tira va de 0.40 a 0.49 s y corresponde a la despolarización ventricular [MCM]. Lo verás otra vez al final.»

Respeto por los registros: el enunciado de un registro real dice de dónde viene y nada más. Ejemplo de sello: «Registro real · PTB Diagnostic ECG Database · s0010_re · derivación II». Sin bromas, sin personajes, sin adjetivos sobre la persona.

---

## 6. Motivación

### XP

- Terminar una lección: 10 XP. Cada ejercicio acertado a la primera: 1 XP más. Una lección de 10 ejercicios da entre 10 y 20 XP.
- Terminar «Repasa tus errores»: 5 XP, más 1 por error corregido.
- Un error no resta.
- «Mi progreso» muestra esta regla tal cual.

### Meta diaria

- 5, 10 o 15 minutos. La eliges en la bienvenida y la cambias en Ajustes.
- Cuenta el tiempo que tardas en responder cada ejercicio, con un tope de 2 minutos por ejercicio para que una pestaña abierta no sume. El tope es Criterio BIOCORE y «Mi progreso» lo dice.
- En el encabezado de la ruta: «Hoy: 6 de 10 min». Al cumplirla: «Meta de hoy cumplida.» La espiga del isotipo late una vez.

### Racha

- Un día cuenta si completas una lección o un repaso, con la fecha local de la computadora.
- La racha es el número de días seguidos que cuentan, hasta hoy o hasta ayer. Si ayer contó y hoy todavía no: «Racha de 4 días. Hoy cuenta cuando termines una lección.»
- Si se rompe: «Tu racha anterior fue de 6 días. Hoy empiezas otra.»
- Sin notificaciones, sin cuenta regresiva, sin «no pierdas tu racha».
- Propuesta para decidir: un día libre por semana que no rompe la racha. La recomiendo para quien estudia enfermo o sale de una guardia.

Qué tomo de la psicología del hábito: metas pequeñas que eliges tú, progreso visible, respuesta inmediata con el dato y una celebración breve. Qué dejo fuera: la amenaza de perder la racha como palanca, la escasez, los rankings y las recompensas al azar.

### Logros (nombres provisionales, a revisar contra la voz del manual)

| Logro | Cómo se obtiene |
|---|---|
| Primer trazo | Terminas tu primera lección |
| Calibración | Haces la prueba de nivel |
| Línea de base | Cumples tu meta 3 días |
| Ritmo sinusal | 7 días de racha |
| Sin artefactos | Una lección con todo acertado a la primera |
| Equivócate aquí | Corriges 10 errores en «Repasa tus errores» |
| Doce derivaciones | 12 lecciones completas |
| Cinco sistemas | Una lección de cada unidad |

### Cierre de la lección

«Lección completa», con cuatro datos: XP ganados (+16 XP), precisión (9 de 10 a la primera, 90 %), tiempo (4 min 12 s) y meta de hoy (8 de 10 min). Botón principal: «Continuar». Si hubo errores, un botón secundario: «Repasar errores».

### Bienvenida (3 pasos)

1. «¿Qué estudias?» Medicina, Enfermería, Ingeniería biomédica u Otra. La pantalla dice para qué sirve: «Lo usamos para sugerirte por dónde empezar.» Ese es su único efecto, y así cumple la regla 9 de `CLAUDE.md`. El encabezado de este paso lleva el lema: «Equivócate aquí.»
2. «¿Cuánto tiempo al día?» 5, 10 o 15 min.
3. «¿Haces una prueba corta para empezar donde te toca?» «Hacer la prueba (6 ejercicios)» o «Empezar desde el principio». Mientras solo exista la lección 1 de Corazón, la prueba coloca dentro de lo que existe.

Al terminar se crea el perfil local. Si la computadora tiene más de un perfil, la app pregunta al abrir: «¿Quién estudia?»

---

## 7. Componentes (Fase 1)

Paquete nuevo `app/ui/`. Los colores siguen saliendo de `PALETTE` en `design_system.py`; ningún componente lleva hex propio.

| Componente | API propuesta | Notas |
|---|---|---|
| Botón principal | `primary_button(label, key, disabled=False)` | `st.button(type="primary")` con CSS: borde inferior sólido de 4 px, 44 px de alto mínimo, foco visible, sin sombra difusa |
| Botón secundario | `secondary_button(label, key)` | Contorno, mismo borde inferior |
| Tarjeta | `card(key)` | `st.container(border=True, key=…)` con CSS por `.st-key-*` |
| Barra de progreso | `progress_bar(done, total)` | HTML con `role="progressbar"` y el texto visible «4 de 10» |
| Sello | `seal(kind, source)` | Registro real, Simulación, Teoría citada, Criterio BIOCORE y Lectura (Paciente). Texto siempre e ícono del kit. Extiende `BADGES` |
| Nodo de la ruta | `path_node(lesson, state)` | Bloqueada, disponible, completada: ícono y palabra. Solo el disponible es botón |
| Banda del modo Paciente | `patient_band(code)` | `position: sticky` bajo el encabezado de Streamlit |
| Panel de respuesta | `feedback_panel(result)` | `role="status"`. Acierto: `nucleo`, palomita, «Correcto». Error: `tinta-2`, ícono, «Todavía no» |
| Tira con cursores | `strip_cursors(signal, fs, key)` | Dibuja con `ecg_paper.py`; deslizador de rango para el teclado y recuadro para el puntero |
| Isotipo | `isotipo(pulse=False)` | SVG del kit; con `pulse=True` la espiga late. Nada con `prefers-reduced-motion` |
| Encabezado de la ruta | `path_header(streak, minutes_today, goal)` | Solo en modo Aprender |
| Confirmación | `confirm(…)` | `st.dialog` para salir de una lección, borrar, exportar o enviar a la nube |

---

## 8. Estilos globales y tokens

- **El kit es la fuente.** `tools/sync_brand_tokens.py` lee `03-Color/biocore-tokens.json` y reescribe un bloque marcado dentro de `design_system.py` y las secciones de tema de `.streamlit/config.toml`. Así se mantiene la regla de hoy: ningún hex fuera de `design_system.py`. Una prueba exige que el JSON, `PALETTE` y el toml coincidan. `PALETTE` conserva sus nombres actuales para no romper a ningún módulo.
- **Temas.** Monitor (oscuro) por defecto y Papel (claro) como alternativa y para informes. En la Fase 1 verifico si Streamlit 1.67 acepta dos temas en `config.toml` (`[theme.dark]` y `[theme.light]`) y si `st.context.theme` dice cuál está activo, para que el CSS propio lo siga.
- **Tipografía.** Figtree en títulos y valores (`font-variant-numeric: tabular-nums`) y Noto Sans en el texto, servidas en local con `[[theme.fontFaces]]`. Se queda la prueba `test_the_global_theme_does_not_ask_for_an_unloaded_font`.
- **Color vivo.** `trazo` es el único por vista. Los `estado-*` del kit sustituyen a STABLE, WARNING y CRITICAL.
- **Botones.** Borde inferior de 4 px. Una prueba busca `box-shadow` con desenfoque en el CSS y falla si lo encuentra.
- **Accesibilidad.** Contraste de 4.5:1 o más para texto (pares en `CONTRAST_PAIRS`), 3:1 para el contorno de foco, objetivos de 44 px y `prefers-reduced-motion: reduce` sin animaciones. Una prueba revisa el CSS.
- **Sin emoji.** `st.Page` solo acepta emoji o íconos Material, así que la navegación queda sin íconos. Los íconos del kit van dentro de las páginas.

Pruebas que cambian por decisión, con su motivo en el CHANGELOG:

- `test_config_toml_is_a_copy_of_the_palette_and_there_is_one_theme`: pasa a dos temas.
- `test_primary_buttons_paint_on_state_text_never_white`: el texto del botón usa el token del kit que llegue a 4.5:1.
- `CONTRAST_PAIRS`: se recalcula con los valores del kit. Si un par del kit no llega a 4.5:1, te lo reporto antes de usarlo; no cambio el kit por mi cuenta.

---

## 9. Modelo de datos del progreso

Base: `data/local/biocore_learning.db`, la de la mejora continua, fuera de git. Tablas nuevas con prefijo `ruta_`, en `educational/progress.py`. El módulo no importa Streamlit y recibe el reloj como parámetro, para poder probar «al día siguiente».

```sql
ruta_perfil    (perfil_id TEXT PRIMARY KEY, alias TEXT, carrera TEXT,
                meta_min INTEGER CHECK (meta_min IN (5, 10, 15)), tema TEXT,
                creado TEXT NOT NULL, bienvenida_completa INTEGER NOT NULL DEFAULT 0)
ruta_intento   (intento_id TEXT PRIMARY KEY, perfil_id TEXT NOT NULL, leccion_id TEXT NOT NULL,
                tipo TEXT NOT NULL,            -- leccion | repaso | prueba
                version_contenido TEXT NOT NULL, inicio TEXT NOT NULL, fin TEXT,
                xp INTEGER, aciertos_primera INTEGER, ejercicios INTEGER, segundos INTEGER)
ruta_respuesta (id INTEGER PRIMARY KEY, intento_id TEXT NOT NULL, ejercicio_id TEXT NOT NULL,
                primera INTEGER NOT NULL, correcta INTEGER NOT NULL, respuesta TEXT NOT NULL,
                segundos REAL NOT NULL, ts TEXT NOT NULL)
ruta_dia       (perfil_id TEXT, fecha TEXT, xp INTEGER, segundos INTEGER, lecciones INTEGER,
                PRIMARY KEY (perfil_id, fecha))
ruta_error     (perfil_id TEXT, ejercicio_id TEXT, fallado_en TEXT NOT NULL, corregido_en TEXT,
                PRIMARY KEY (perfil_id, ejercicio_id))
ruta_logro     (perfil_id TEXT, logro_id TEXT, obtenido_en TEXT NOT NULL,
                PRIMARY KEY (perfil_id, logro_id))
```

Reglas:

- El estado de una lección se calcula de `ruta_intento`: completada si existe un intento con `fin`. No se guarda aparte.
- La racha es una función pura: `racha(dias, hoy) -> int`.
- Cada respuesta se guarda una vez por intento, con el patrón de `log_answer`, y también entra a la tabla `answers` de la mejora continua (banco `ruta`) para el análisis de ítems.
- El «ID del estudiante» de la Academia pasa a ser el perfil activo.
- Esquema versionado con `PRAGMA user_version` y `CREATE TABLE IF NOT EXISTS`.
- El contenido vive en `educational/ruta/` como datos de Python, igual que `quiz_bank.py`. Cada ejercicio tiene `id` estable, tipo, señal, clave, tolerancia, textos y fuente. Una prueba exige fuente firmada y sello en cada ejercicio, y revisa los textos: sin «¡», sin «!», sin emoji y sin raya larga.

---

## 10. Datos de pacientes

### Cómo entran hoy

| Entrada | Dónde | Qué pasa con el dato | Con IA |
|---|---|---|---|
| ECG · Monitoreo: CSV local | `app/main.py:1507` | La app lo escribe en la carpeta temporal del sistema **con su nombre original** y no lo borra | Desconocido: Gemini lo bloquea, Anthropic lo recibe |
| ECG · Monitoreo: placa ESP32 + AD8232 | `hardware/ecg_plugplay/` | «Guardar al gemelo» escribe `SENSOR_REAL` al UPS | Persona: Anthropic lo recibe |
| ECG · exportar | `app/main.py:1280` | Escribe CSV en `datasets/exports/`, dentro del repositorio, y **`.gitignore` no excluye esa carpeta** | No aplica |
| 12 Derivaciones: CSV | `ecg_12/page_content.py:363` | En memoria | Desconocido |
| EEG: CSV, OpenBCI, Muse, Unicorn, LSL | `eeg_neuro_lab/` | CSV en memoria; en vivo escribe `SENSOR_REAL`; el informe usa `tempfile.mkdtemp` | Persona o desconocido |
| EMG: CSV, ESP32 + MyoWare | `app/main.py:938`, `biosensors/emg.py` | El CSV no escribe al gemelo (`CSV_SAVE_BLOCKER`); el sensor sí | Persona o desconocido |
| Multisensor: MAX30102 y DS18B20 | `biosensors/live_view.py` | Solo en pantalla; no escribe al UPS | No aplica |
| HRV: serie RR pegada | `app/main.py:2032` | Se guarda al gemelo como `SIMULACION`, aunque la serie puede ser de una persona | Desconocido |
| Flujo de pacientes | `app/main.py:2284` | «Nombre del paciente» en texto libre, signos vitales e impresiones con notas libres, todo en el UPS | Persona: Anthropic lo recibe |
| Crea tu modelo 3D: DICOM, NIfTI, malla, EEG, cohorte CSV/XLSX, VCG | `app/supermodules/model3d/` | En memoria. `pydicom` lee las etiquetas con nombre, fechas y expediente; la app solo usa la geometría y no las quita | No aplica |
| Gemelo: ESP32 con el lector viejo | `hardware/esp32_stream.py` | Escribe `SENSOR_REAL` | Persona |

Almacén actual: `data/biocore_ups.db`, SQLite sin cifrar dentro de la carpeta del proyecto (ignorado por git). Cada sesión de navegador crea un «Paciente Demo (Twin Shell)», así que simulaciones y datos reales comparten base.

IA actual: `domain/physiology/narrator/privacy.py` bloquea a Gemini gratuito con datos de persona o desconocidos. Con una clave de Anthropic, esos datos salen a la nube sin pedir permiso en ese momento. No existe un proveedor local.

Tres hallazgos que corrijo en la Fase 4 aunque no hubiera rediseño: el CSV en la carpeta temporal con su nombre original, `datasets/exports/` sin ignorar y el envío de datos de persona a Anthropic sin permiso en el momento.

### Cómo entran en el modo Paciente

**1. Consentimiento (antes de todo).**

- Casilla: «Tengo el consentimiento expreso y por escrito, firmado por el paciente, para este uso.»
- Propósito, obligatorio: Clase, Práctica o Investigación.
- Enlace al aviso de privacidad. El texto lo redacta un abogado (Fase 4).
- «Continuar» queda inactivo hasta marcar la casilla y elegir el propósito. El cargador de archivos y la conexión de sensores no se dibujan antes; deshabilitarlos no basta.
- La app registra la fecha, el operador (perfil local), el propósito y la versión del aviso.

**2. Anonimización, antes de guardar.** La app hace esto antes de escribir nada:

- Asigna un código al azar, sin relación con los datos: P-0142.
- CSV: guarda solo las columnas numéricas de señal y tiempo, y descarta comentarios y columnas de texto.
- EDF (hoy la app no lo acepta; si el modo Paciente lo habilita): cambia el campo de paciente a «X X X X», la fecha de inicio a 01.01.85 (convención de anonimización de EDF+) y deja los tiempos relativos.
- DICOM: aplica el perfil básico de confidencialidad de DICOM PS3.15, anexo E (nombre, identificador, fechas, institución, médicos, UID y etiquetas privadas) y conserva la geometría.
- NIfTI: vacía `descrip`, `aux_file` e `intent_name`. Mallas STL: vacía el encabezado de 80 bytes.
- Tablas de cohorte: quita por defecto las columnas con nombre, expediente, fechas, CURP, RFC, correo o teléfono, y tú confirmas las demás.
- Nombre de archivo: lo descarta. El archivo guardado lleva un identificador al azar.
- Edad: rango de 10 años (40 a 49). Nunca la fecha de nacimiento.
- La pantalla muestra lo que encontró y quitó: «Quitamos: nombre, fecha de nacimiento, número de expediente, fecha del estudio y nombre del archivo.»
- Límite declarado: la app no detecta texto quemado en los píxeles de una imagen. La pantalla te pide revisarlo.

**3. Almacén cifrado fuera del repositorio.**

- Carpeta de datos del usuario del sistema (`%LOCALAPPDATA%\Biocore\pacientes` en Windows, `~/.local/share/biocore/pacientes` en Linux y macOS), con una variable de entorno para cambiarla.
- Dos opciones para decidir: UPS en SQLite cifrado con SQLCipher (`sqlcipher3`), o archivos cifrados con AES-GCM (`cryptography`) y una base que solo guarda códigos. Elijo en la Fase 4 según haya wheels para Windows y Python 3.13.
- Llave: en el almacén de llaves del sistema (`keyring`) o derivada con scrypt de una frase que escribes al abrir el modo Paciente.
- Ningún dato de paciente en git, logs, nombres de archivo ni URLs. Una prueba siembra valores identificables, corre un flujo completo y los busca en los logs, en `git status` y en los nombres de archivo.

**4. Vista del paciente.**

- Banda fija: «Paciente real · P-0142 · anonimizado».
- Cada lectura con su sello de procedencia y su unidad a la vista.
- Calidad de la señal solo donde hay método (por ejemplo, el aviso de saturación del pulso por luz). Donde no: «Calidad: no disponible, falta un método».
- `estado-*` siempre con su palabra.
- Vocabulario: lectura, hallazgo, patrón compatible con. Una prueba falla si una página del modo Paciente dice «diagnóstico» fuera de la leyenda, o «Correcto».

**5. Salidas.**

- Informe PDF en tema Papel (con `fpdf2`, ya en `requirements.txt`), con la leyenda: «Herramienta educativa: no sustituye el juicio clínico ni es un diagnóstico.»
- Exportar pide confirmación y queda en el registro.
- «Borrar paciente»: el diálogo pide escribir el código. Borra filas del UPS, archivos cifrados, derivados (informes guardados, mallas, temporales) y el estado de la sesión. Avisa que lo que descargaste a tu computadora no se borra desde aquí. No tiene deshacer y lo dice.
- Deshacer existe para lo reversible: quitar una lectura del informe, cambiar un filtro, editar una nota.

**6. Registro de accesos.** Tabla aparte con código, operador, acción (abrir, cargar, exportar, borrar, convertir) y fecha. Sobrevive al borrado del paciente: es la constancia de que se borró.

**7. Caso docente.** Pide un segundo consentimiento (uso educativo) y la revisión de la anonimización: la pantalla muestra lo que entraría. Crea una copia anonimizada en la Academia con el sello «Caso real anonimizado». El paciente original sigue en su almacén.

### IA con datos de pacientes

- Proveedor nuevo: Ollama local (`domain/physiology/narrator/ollama.py`, HTTP con `urllib` como `gemini.py`). Solo acepta direcciones locales (127.0.0.1, ::1, localhost).
- `privacy.py`: con datos de persona o desconocidos, solo pasa un proveedor local. Anthropic pasa si autorizas esa llamada en un diálogo que muestra qué se manda. Gemini gratuito sigue bloqueado.
- Tutor y Narrador usan el mismo paquete. No hay otra ruta a un modelo.
- Sin Ollama: «La IA local no está disponible. Instala Ollama o sigue sin IA.» Todo lo demás funciona.
- Aquí no puedo correr Ollama. Las pruebas usan un servidor HTTP falso y el CHANGELOG lo dirá.

---

## 11. Límites de Streamlit

| Límite | Solución |
|---|---|
| Cada clic vuelve a correr el script | La lección es una máquina de estados en `session_state` dentro de `st.fragment`; cada respuesta se guarda una vez |
| No hay arrastrar y soltar | Ordenar = tocar en orden. Unir = un selector por señal |
| Marcar sobre una gráfica no sirve con teclado | Recuadro con el puntero (`on_select` de Plotly) y deslizador de rango; los dos dan la misma respuesta |
| La app no conoce el ancho de la pantalla | Media queries en el CSS; la tira escala con proporción fija |
| Python no puede plegar el menú lateral | CSS que lo oculta durante la lección, por clave de contenedor |
| El tema se cambia en el menú de Streamlit | Verifico dos temas y `st.context.theme` en 1.67; si no alcanza, Papel queda para informes e impresión |
| Elementos fijos (banda, botón inferior) | `position: sticky` sobre `.st-key-*`, el selector que ya usa el repo |
| `st.Page` solo admite emoji o Material | Navegación sin íconos |
| Recargar la página borra `session_state` | Lo completado está en la base; una lección a medias se pierde, salvo que decidas guardarla |
| No hay cuentas | Perfil local. En un despliegue en la nube el disco se borra y la racha con él (fuera de alcance) |
| Lectores de pantalla | Panel con `role="status"`. Streamlit recrea elementos y algunos lectores no anuncian una región nueva; hay que probarlo con NVDA o VoiceOver |
| Sin JavaScript en `st.html` | Animaciones solo con CSS |

---

## 12. Pruebas y verificación en cada fase

- **Calificación:** cada tipo con sus bordes (justo en la tolerancia, fuera por 1 ms, unidad equivocada, sin respuesta).
- **Progreso:** XP, racha con reloj inyectado (hoy, mañana, un día sin estudiar), meta con el tope por ejercicio, desbloqueo de lecciones y base reabierta (la racha sigue al día siguiente).
- **Anonimización:** archivos con datos sembrados (nombre, fechas, expediente en CSV, EDF, DICOM, NIfTI, XLSX) y verificación de que no queda ninguno en lo guardado.
- **Modos:** recorrido del modo Paciente sin elementos de juego, carga imposible sin consentimiento, borrado completo e IA bloqueada hacia la nube.
- La suite completa sigue pasando (2292 en el cierre del pulido). Las pruebas que cambian por decisión llevan su motivo.
- Capturas a 390 y 1280 px, en Monitor y en Papel, con Playwright. Las reviso con design-critique y accessibility-review antes de enseñártelas.
- Textos con stop-slop y ux-copy.
- Una entrada de `CHANGELOG.md` por tanda (regla 10).

---

## 13. Fases y commits

**Fase 1 · estilos y componentes** (necesita el kit)
1. Fuentes en local y `config.toml` con los temas.
2. Tokens del kit en `design_system.py` y pruebas de contraste.
3. CSS global: botones, foco, 44 px, movimiento reducido.
4. Componentes, uno por commit, cada uno con su prueba y una página de muestra oculta para las capturas.

**Fase 2 · la ruta y la lección 1 de Corazón**
1. Modelo de contenido y calificadores, sin UI, con pruebas.
2. Tira con cursores.
3. Ruta con nodos y estados.
4. Lección completa: comprobar, continuar, errores al final y cierre básico.
5. Hoja de anotación de s0010 para la firma de Luis.

**Fase 3 · motivación:** progreso persistente, XP, meta, racha, repaso de errores, cierre, logros, bienvenida y «Mi progreso».

**Fase 4 · modo Paciente:** consentimiento, anonimización, almacén cifrado, vista, borrado, registro, caso docente e IA local. Cierra con `/security-review` y la revisión legal.

**Fase 5 · el resto de los sistemas:** Respiración, Cerebro, Músculo y Sistema autónomo, con el mismo patrón.

---

## 14. Decisiones pendientes

| # | Decisión | Quién | Mi recomendación |
|---|---|---|---|
| 1 | Subir `biocore-v2` o `docs/marca/` | Tú | Bloquea la Fase 1 |
| 2 | Dos temas en lugar de uno (cambia la decisión de la tanda 1 de la fase 1) | Luis | Sí, como pide el kit |
| 3 | Perfil local como identidad, que monta «Mi progreso» (decisión 1) | Luis | Sí, sin cuentas |
| 4 | El gemelo colorea órganos con STABLE, WARNING y CRITICAL en modo Aprender; la regla nueva reserva `estado-*` al modo Paciente | Luis | Escala de `tinta` con palabra en el gemelo, en la Fase 5 |
| 5 | Unidades abiertas o en cadena | Tú | Abiertas, lecciones en orden |
| 6 | Día libre semanal para la racha | Tú | Sí |
| 7 | Cifrado: SQLCipher o AES-GCM; llave en `keyring` o con frase | Luis | Lo decido con los wheels a la vista, en la Fase 4 |
| 8 | Dependencias nuevas: `cryptography`, `keyring` o `sqlcipher3`, y Ollama como programa aparte | Luis | Las mínimas de la opción 7 |
| 9 | Acceso a physionet.org en el entorno, o que Luis corra la descarga | Tú | Cualquiera de las dos |
| 10 | Guardar una lección a medias para retomarla | Tú | Sí, en la Fase 3 |
| 11 | Autorregistro: un estudiante que se conecta un sensor a sí mismo en clase, ¿firma el mismo consentimiento? | Abogado | Pregunta para la Fase 4 |
| 12 | Si la persona retira el consentimiento, ¿se borra también su caso docente? | Abogado | Pregunta para la Fase 4 |
| 13 | ¿Una tira de ECG o EEG sin metadatos cuenta como dato anonimizado, o como biométrico? | Abogado | Pregunta para la Fase 4 |
| 14 | Instalar ui-ux-pro-max, frontend-design y marketing-skills | Tú | Sí, antes de la Fase 1 |
