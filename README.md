# BIOCORE AI

**Un laboratorio digital de fisiología humana para enseñar medicina con IA, construido sobre una regla: nunca finge lo que no sabe.**

BIOCORE AI es una plataforma educativa de fisiología humana para estudiantes de medicina y ciencias de la salud. En lugar de enseñar con texto estático, enseña con un **gemelo digital reactivo**: un organismo virtual cuyo estado fisiológico se calcula con modelos reales, se altera con escenarios clínicos, y se explica con fundamento.

La tesis: aprender medicina no es leer una buena explicación, es intentar, equivocarse y ser corregido con fundamento. El estudiante no memoriza que la sepsis baja la presión — ve la presión desplomarse por el mecanismo de la vasoplejía, e intenta diagnosticarlo mientras sucede.

---

## Qué lo hace distinto

La mayoría de las plataformas educativas médicas *suenan* clínicas sin serlo: muestran números con apariencia de métrica que nadie calculó, etiquetas que parecen diagnósticos sin un algoritmo detrás. Para una herramienta que forma médicos, un dato falso que suena convincente es lo más peligroso que puede haber.

BIOCORE se construyó sobre la regla opuesta, que gobierna toda su arquitectura:

> **Cada dato declara su procedencia. Cuando el sistema no puede saber algo, lo dice — nunca rellena el hueco con algo plausible.**

Cada valor en la plataforma sabe de dónde viene y lo declara: **medido**, **simulado**, **referencia clínica citada**, o **calculado por modelo**. Los biomarcadores llevan la cita del estándar del que provienen. Cuando falta señal para un cálculo, el sistema devuelve "no disponible" con el motivo — nunca un número de relleno. Y cada módulo declara su nivel de validación: un lab validado contra un dataset canónico se presenta con más autoridad que un índice heurístico de ingeniería, y la interfaz lo hace visible.

Esa honestidad de procedencia no es un detalle estético. Es la diferencia entre enseñar medicina real y enseñar algo que suena a medicina — y es el diferenciador de confianza frente a plataformas que no la tienen.

---

## Arquitectura

**UPS (Unified Physiological State) — el estado fisiológico unificado.** La fuente única de verdad del paciente. Cada dato lleva su procedencia. Los dominios modelados incluyen cardiovascular, respiratorio, neurológico y muscular, con biomarcadores que los cruzan.

**Motor hemodinámico validado.** Calcula presión arterial y dinámica cardiovascular por fisiología real, basado en un modelo publicado (svZeroDSolver), con parámetros validados por un experto humano contra literatura. La sepsis colapsa a shock por mecanismo, no por ajuste — la prueba de honestidad del modelo.

**Los cuatro hubs:**
- **Digital Twin OS** — el organismo entero: órganos que reaccionan al UPS sobre un **cuerpo 3D real**, acoplamientos entre sistemas, casos clínicos, línea de tiempo fisiológica.
- **Clinical Hub** — los laboratorios de señal: ECG (con **vectocardiograma 3D**), EEG (con **mapa 3D sobre la cabeza**), EMG, Respiratorio, HRV, Biomarcadores, y más — y las **🧮 Calculadoras Clínicas**.
- **Learning Hub** — casos clínicos ciegos, evaluación con feedback fundamentado y el **Atlas visual**, con un explorador 3D.
- **Laboratorio 3D** — **🧊 Crea tu modelo 3D** con tus propios datos.

**Anatomía 3D de datos reales.** El cuerpo no está dibujado: son 38 estructuras reconstruidas de una tomografía real de cuerpo completo (TotalSegmentator, CC BY 4.0) — esqueleto, corazón con sus vasos, pulmones, encéfalo, médula, músculos y órganos abdominales —, cada una con el volumen medido en esa tomografía. La cabeza es la superficie de fsaverage (FreeSurfer) con los 21 electrodos 10-20 de MNE y el cerebro de la plantilla MNI152. Se giran y se exploran en el navegador (Plotly), y las mismas mallas, renderizadas con iluminación física, ilustran el Atlas y las tarjetas de órganos. Las posiciones V1–V6 se calculan sobre esa tomografía contando los espacios intercostales.

**Atlas visual con registros reales.** Las láminas usan datos reales en lugar de dibujos: el complejo ECG es el latido mediano del MIT-BIH 100 con sus intervalos medidos por el código, el tacograma usa sus intervalos RR anotados, las bandas EEG salen de un EEG real (CAP Sleep n16) y la tira de cada módulo es un registro de PhysioNet (ODC-By) citado en pantalla. Cada lámina dice qué es — registro real, anatomía real, esquema o simulación — y lleva sus fuentes; se resaltan según lo que eliges dentro de cada laboratorio.

**🧊 Crea tu modelo 3D.** Sube una tomografía o resonancia (DICOM, también en .zip, o NIfTI) y obtén su malla 3D por umbral, preset (hueso, piel, pulmones, tejido blando) o etiquetas de una segmentación, con su volumen en mL y descarga en STL/OBJ/PLY para imprimir o abrir en 3D Slicer o Blender; visor de mallas propias; ECG de 12 derivaciones → vectocardiograma 3D (matriz de Kors, validada contra las derivaciones de Frank reales del PTB); EEG → mapa 3D sobre la cabeza (splines esféricos); y tu base de pacientes (CSV/Excel) → un mapa 3D con aprendizaje automático (PCA, k-means, Isolation Forest y bosque aleatorio evaluado con validación cruzada), con el puntaje NEWS2 de cada signo vital sobre el cuerpo 3D. Todo corre en tu computadora; viene con una tomografía de ejemplo.

**🧮 Calculadoras Clínicas.** Fórmulas y escalas publicadas, cada una con su cita y su lectura contra el corte que fija la referencia: QTc (Bazett, Fridericia, Framingham, Hodges), FC desde el papel del ECG, eje eléctrico sobre el sistema hexaxial, PAM / presión de pulso / índice de choque, gasto e índice cardiaco, IMC y superficie corporal (Mosteller, Du Bois), PAO₂ y gradiente A–a **corregidos por altitud** (Ciudad de México, Guadalajara, Toluca…), PaO₂/FiO₂ con los rangos de Berlín, NEWS2 (con su medidor de bandas), qSOFA y Glasgow; la PAO₂ se grafica contra la altitud con las ciudades marcadas. Pueden importar la FC, FR y SpO₂ del gemelo digital (etiquetadas como simulación) y exportan un informe PDF/HTML.

**Interfaz accesible.** Diseño guiado por UI UX Pro Max para salud: tipografías Figtree y Noto Sans incluidas, contraste WCAG verificado por cálculo, foco visible, objetivos táctiles de 44 px, movimiento reducido respetado y paleta de gráficos validada para daltonismo.

**IA gratis y local, sin claves.** El narrador clínico y el feedback usan un modelo de lenguaje abierto que corre en tu propia computadora con [Ollama](https://ollama.com) (o cualquier servidor compatible con la API de OpenAI: LM Studio, llama.cpp…): sin costo, sin clave y sin que los datos salgan del equipo. BIOCORE lo detecta solo; Claude (Anthropic) queda como opción con tu clave. Sin ningún motor, la app funciona igual — los quizzes y casos ciegos se califican con el banco/simulador (código, no modelo) y los paneles de IA lo dicen en vez de fingir texto.

**Procesamiento de señal real.** Detección de complejos QRS y bloqueos de rama validada contra el MIT-BIH Arrhythmia Database; análisis espectral de EEG con parametrización del componente aperiódico (FOOOF); métricas de variabilidad cardíaca bajo estándares de la Task Force ESC/NASPE, con gráfico de Poincaré (SD1/SD2) y carga de series RR reales desde archivo (Polar, Kubios, CSV propio); electromiografía con activación fisiológica real.

---

## Estado del proyecto

BIOCORE está en desarrollo activo. La base honesta está construida y verificada: el motor hemodinámico validado, los dominios del UPS con procedencia por descriptor, el procesamiento de señal real en múltiples laboratorios, y una suite de pruebas extensa que verifica tanto el cálculo como la ausencia de fachadas.

El desarrollo sigue una disciplina de honestidad estricta: cada capacidad se valida antes de exhibirse, cada biomarcador de vanguardia se prueba contra ground truth antes de declararse, y las ideas que no alcanzan el estándar se archivan con evidencia en lugar de construirse a medias.

---

## Instalación

Requiere Python 3.10+.

**Windows:** doble clic en `RUN_BIOCORE.bat` (o `.\run_local.ps1` en PowerShell). La primera vez crea un entorno virtual `.venv` e instala las dependencias (unos minutos); las siguientes veces arranca directo y solo reinstala si cambió `requirements.txt`. El navegador se abre solo en <http://localhost:8501> cuando la app está lista; para cerrarla, cierra la ventana negra.

**Manual (cualquier sistema):**

```bash
git clone <url-del-repositorio>
cd biocore
python -m venv .venv
# Windows: .venv\Scripts\activate   ·   macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python run_biocore.py          # o: streamlit run app/main.py
```

`run_biocore.py` es el arranque recomendado en Windows: usa el event loop de selectores, que evita que el servidor deje de escuchar si una conexión se corta a medias. La app escucha solo en esta computadora (`127.0.0.1`); para abrirla desde otro dispositivo de tu red: `python run_biocore.py --server.address 0.0.0.0`.

La aplicación se abre en el navegador (<http://localhost:8501>). Los datos de señal se generan por escenario o se cargan desde archivos; ninguna clave de API es necesaria.

**IA gratis (opcional, recomendada):** instala [Ollama](https://ollama.com), abre una terminal y ejecuta `ollama pull qwen2.5:7b` (unos 4.7 GB; con poca memoria, `qwen2.5:3b`). Con Ollama abierto, BIOCORE lo detecta solo; el modelo se elige en la barra lateral, en "Motor de IA".

**Claude (opcional):** copia `.env.example` a `.env` y escribe tu `ANTHROPIC_API_KEY`. La app lee `.env` al arrancar (una variable ya definida en el entorno tiene prioridad). Sin ningún motor, los paneles del narrador lo declaran en vez de simular texto.

**Datos incluidos:** anatomía 3D, registros de referencia y la tomografía de ejemplo vienen en `data/` con sus licencias y citas (ver el `README.md` de cada carpeta). `tools/README.md` explica cómo regenerarlos.

**Desarrollo:** `pip install -r requirements-dev.txt` (pytest, linters, notebooks) y `pytest tests/ -q`.

---

## Licencia

Este proyecto se distribuye bajo una licencia de fuente disponible, no comercial. El código es visible para revisión, estudio y evaluación, pero su uso comercial requiere acuerdo con el titular. Ver [`LICENSE`](LICENSE) para los términos completos.

© 2026 Luis Nazariego Santome.

---

*BIOCORE AI — fisiología humana para enseñar medicina, sobre la regla de que nunca finge lo que no sabe.*
