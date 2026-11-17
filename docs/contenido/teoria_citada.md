# Teoría citada para BIOCORE — borrador para firma

**Estado:** FIRMADO por Luis Nazariego Santome el 16 de noviembre de 2026 (temas 1 a 10 y las cuatro decisiones de la hoja de firma).
**Uso:** Claude Code integra cada tema en el componente de teoría en capas (idea · mecanismo · detalle con fuente) y en la página de Bibliografía. El texto está redactado con palabras propias, a partir de las fuentes; no copia pasajes.
**Regla:** cada afirmación lleva su fuente con clave entre corchetes ([K2007], [W2009]…). La lista completa está al final. Las notas «Decisión de Luis» registran lo que se resolvió al firmar.

---

## 1. El ECG en papel: cómo se registra y se lee

**Idea.** Un ECG estándar se registra a 25 mm/s y con una calibración de 10 mm por cada 1 mV, de modo que la cuadrícula permite leer tiempo y voltaje directamente [MCM].

**Mecanismo.**
- Eje horizontal (tiempo): a 25 mm/s, cada cuadro pequeño (1 mm) equivale a 0.04 s y cada cuadro grande (5 mm) a 0.2 s [MCM].
- Eje vertical (voltaje): la marca de calibración es una deflexión de 10 mm que representa 1 mV; por tanto, 1 mm equivale a 0.1 mV [MCM].
- El formato tradicional de 12 derivaciones las muestra en 4 columnas (I, II, III · aVR, aVL, aVF · V1–V3 · V4–V6) y puede añadir una o más tiras de ritmo continuas de 10 segundos [K2007].

**Detalle con fuente.**
- Para un ECG diagnóstico en adultos, la recomendación es una frecuencia de corte superior de al menos 150 Hz; para lograrla con el error de amplitud por debajo de 1 %, se necesitan datos a 500 muestras por segundo [K2007].
- La frecuencia de corte inferior recomendada es 0.05 Hz, que puede relajarse hasta 0.67 Hz con filtros digitales lineales de fase cero [K2007].
- Un corte superior de 40 Hz invalida las mediciones de amplitud que se usan para clasificar diagnósticos; los equipos deberían avisar cuando se usa un filtro así [K2007]. Un filtro de 0.5–40 Hz es, por tanto, de **monitoreo**, no diagnóstico.

> **Decisión de Luis:** el banner del ECG Lab dice "Filtros estándar AHA". Se verifica el filtro implementado; si es de monitoreo (corte superior < 150 Hz), se rotula "filtro de monitoreo" con la cita [K2007].

---

## 2. Frecuencia cardiaca

**Idea.** La frecuencia cardiaca es el número de latidos por minuto; en el ECG se obtiene dividiendo 60 segundos entre el intervalo RR [MCM].

**Mecanismo.**
- Con ritmo regular: 60 / intervalo RR (en segundos), o contando los cuadros grandes entre dos ondas R [MCM].
- Con ritmo irregular: se cuentan los complejos QRS en 6 segundos y se multiplican por 10 [MCM].

**Detalle con fuente.** En la escala NEWS2, el pulso puntúa: ≤40 lpm, 3 puntos; 41–50, 1; 51–90, 0; 91–110, 1; 111–130, 2; ≥131, 3 [RCP2017]. (Ya implementado en `news2_pulse_score`.)

> **Decisión de Luis:** se retiran las capas genéricas de "¿Qué significa Frecuencia cardiaca?" y quedan solo las de este tema, con fuente.

---

## 3. Ondas e intervalos del ECG

**Idea.** Cada onda del ECG corresponde a una fase eléctrica del corazón: la P a la despolarización auricular, el QRS a la despolarización ventricular y la T a la fase final de la repolarización ventricular [MCM].

**Detalle con fuente** (valores de referencia en adultos) [MCM]:

| Medida | Referencia |
|---|---|
| Intervalo PR | 0.12 a 0.20 s |
| Duración del QRS | 0.06 a 0.11 s |
| QT prolongado (corregido con Bazett) | ≥ 0.45 s en hombres; ≥ 0.46 s en mujeres |
| Eje eléctrico normal | de −30° a +90° |

---

## 4. Las 12 derivaciones: de dónde salen

**Idea.** Las 12 derivaciones son 12 "miradas" a la misma actividad eléctrica, obtenidas con electrodos en las extremidades (plano frontal) y seis electrodos en el tórax (plano horizontal) [K2007].

**Mecanismo** [K2007]:
- **Derivaciones bipolares de Einthoven:** I = brazo izquierdo − brazo derecho; II = pierna izquierda − brazo derecho; III = pierna izquierda − brazo izquierdo.
- **Terminal central de Wilson:** el promedio de los potenciales de brazo derecho, brazo izquierdo y pierna izquierda; sirve de referencia para las derivaciones precordiales.
- **Derivaciones aumentadas de Goldberger (aVR, aVL, aVF):** cada electrodo de extremidad se compara con el promedio de los otros dos; su amplitud es 50 % mayor que si se refiriera a la terminal de Wilson.
- **Precordiales:** V1, 4.º espacio intercostal en el borde esternal derecho; V2, 4.º espacio en el borde esternal izquierdo; V3, a medio camino entre V2 y V4; V4, 5.º espacio en la línea medioclavicular; V5, en el plano horizontal de V4 en la línea axilar anterior; V6, en ese mismo plano en la línea axilar media.

---

## 5. Derivaciones e isquemia: qué sugiere cada grupo

> **Decisión de Luis:** la tabla actual de Academia se sustituye por esta. La guía de la AHA/ACCF/HRS recomienda **no rotular derivaciones individuales como "anterior", "inferior" o "lateral"**, sino nombrarlas por su nombre original [W2009]; esta tabla describe qué *sugieren* los cambios del ST en cada grupo y declara la incertidumbre.

**Idea.** Los cambios del segmento ST en un grupo de derivaciones orientan hacia la región del ventrículo afectada y, con menos certeza, hacia la arteria responsable [W2009].

**Detalle con fuente** [W2009]:

| Hallazgo | Qué sugiere | Arteria probable y advertencias |
|---|---|---|
| Elevación del ST en V1–V4, I, aVL y a menudo aVR | Oclusión proximal de la descendente anterior | La isquemia de la pared anterior se debe a oclusión de la descendente anterior (DA). |
| Elevación del ST sobre todo en V3–V6 | Oclusión distal de la DA | — |
| Oclusión de la DA entre la primera rama septal y la primera diagonal | Se respeta el tabique basal | El ST de V1 no se eleva. |
| Elevación del ST en II, III y aVF | Afectación inferior | Coronaria derecha (CD) o circunfleja (Cx), según cuál dé la descendente posterior (dominancia). Elevación mayor en III que en II sugiere CD. |
| Elevación en I y aVL junto con cambios inferiores | Puede acompañar la oclusión de la Cx | — |
| Elevación del ST en V3R y V4R (derivaciones derechas) | Afectación del ventrículo derecho | Oclusión proximal de la CD. |
| Descenso del ST en V1–V3 | Patrón llamado "posterior" o posterolateral | Puede deberse a CD o Cx; con cambios inferiores no es posible saber cuál. |
| Elevación en aVR y V1 con descenso del ST en 8 o más derivaciones | Sugiere enfermedad de tronco o de tres vasos | — |

---

## 6. NEWS2: qué es y por qué BIOCORE lo muestra "parcial"

**Idea.** NEWS2 es una puntuación agregada que estandariza cómo se registran, puntúan y atienden las constantes vitales para detectar el deterioro agudo [RCP2017].

**Mecanismo** [RCP2017]:
- Puntúa seis parámetros: frecuencia respiratoria, SpO₂, presión arterial sistólica, pulso, nivel de consciencia o confusión nueva, y temperatura. Se suman 2 puntos si el paciente recibe oxígeno suplementario.
- Cada parámetro recibe puntos según cuánto se aleja de lo normal, y los puntos se suman.
- Un 3 en un solo parámetro (marcado en rojo) es poco frecuente y motiva una revisión urgente.

**Detalle con fuente** [RCP2017]:
- Total 0: vigilancia al menos cada 12 horas. Total 1–4 (bajo): valoración por enfermería. Total 5–6 (medio): revisión urgente por un clínico competente en enfermedad aguda. Total 7 o más (alto): valoración de emergencia por un equipo con competencia en cuidados críticos.
- La escala 2 de SpO₂ se usa en insuficiencia respiratoria hipercápnica confirmada (por lo general EPOC), con objetivo de 88–92 %, bajo indicación de un clínico. En los demás casos se usa la escala 1.
- **Por qué BIOCORE no calcula el total:** el gemelo no dispone de presión arterial en todos los casos, y no modela temperatura ni consciencia. Sin esos parámetros, un total sería falso; por eso la plataforma muestra los puntos de cada parámetro disponible y lista lo que falta.

---

## 7. Patrones respiratorios

**Cheyne-Stokes.**
- **Idea:** es una forma de respiración periódica, con un patrón creciente y decreciente entre apneas o hipopneas centrales [CS2023].
- **Mecanismo:** se inicia y se mantiene por cambios en el umbral de apnea y por la fluctuación de la PCO₂: durante la hiperventilación, la PCO₂ cae por debajo del umbral de apnea y vuelve a provocar una apnea, lo que sostiene el ciclo. En la insuficiencia cardiaca, la reserva de CO₂ (la diferencia entre el umbral despierto y en sueño) está reducida [CS2023].
- **Detalle:** se asocia a insuficiencia cardiaca y a ictus (hasta 20 % de los pacientes con ictus) [CS2023]. La AASM exige al menos 3 apneas centrales consecutivas con ciclo de 40 s o más y 5 o más eventos por hora en al menos 2 horas de registro; puede reflejar insuficiencia cardiaca congestiva no reconocida [B2012].

**Biot.**
- **Idea:** grupos de respiraciones profundas y regulares separados por periodos de apnea [AR2025].
- **Detalle:** se atribuye a daño pontino por ictus, trauma, herniación uncal o intoxicación por opioides [AR2025].

> **Decisión de Luis:** el patrón "atáxico" del generador (frecuencia y profundidad irregulares) **no es** Biot (respiraciones regulares en grupos). Se queda estrictamente como descripción de una simulación algorítmica, sin fisiopatología ni origen anatómico, porque no hay fuente abierta verificada.

---

## 8. Bandas del EEG

**Idea.** El EEG se describe por bandas de frecuencia con nombre griego [IFCN2017].

**Detalle con fuente** [IFCN2017]:

| Banda | Rango |
|---|---|
| Delta | 0.1 a < 4 Hz |
| Theta | 4 a < 8 Hz |
| Alfa | 8 a 13 Hz (inclusive) |
| Beta | 14 a 30 Hz (inclusive) |
| Gamma | > 30 a 80 Hz |

El **ritmo alfa** es un ritmo de 8–13 Hz que aparece en vigilia sobre las regiones posteriores de la cabeza [IFCN2017].
(Miguel ya integró esta tabla con su cita; aquí queda para la Bibliografía.)

---

## 9. ECG en 3D (vectorcardiograma)

**Idea.** El vectorcardiograma representa en el espacio las fuerzas eléctricas que genera el corazón, analizadas en tres planos [VZ2014].

**Mecanismo.** Las derivaciones de Frank pueden reconstruirse a partir del ECG de 12 derivaciones. Al comparar métodos, el de regresión (transformación de Kors) y el basado en un modelo dieron resultados equivalentes y mejores que el cuasiortogonal; solo 1 de 90 vectorcardiogramas reconstruidos por regresión se juzgó diagnósticamente distinto del original [KORS1990].

**Detalle.** La transformación de Kors es de uso común en clínica e investigación, con menor error cuadrático medio que la inversa de Dower en un estudio con la base PTB [VZ2014].

> **Decisión de Luis:** se audita la cita "Oehler 2014" del repo. Si no corresponde a una publicación verificable, se sustituye por [VZ2014]; si no aplica, se retira.

---

## 10. Cómo se mide la respiración en un estudio de sueño

**Idea.** En un estudio de sueño, el flujo se mide con un sensor térmico oronasal, el esfuerzo con cinturones toracoabdominales y la oxigenación con pulsioximetría [B2012].
(Texto ya presente en el lab Respiratorio con esta cita; en BIOCORE estas señales son simuladas y así se declara.)

---

## Bibliografía

**Guías y documentos de consenso**
- **[K2007]** Kligfield P, Gettes LS, Bailey JJ, et al. Recommendations for the standardization and interpretation of the electrocardiogram: part I: the electrocardiogram and its technology. A scientific statement from the AHA Electrocardiography and Arrhythmias Committee, Council on Clinical Cardiology; the ACCF; and the HRS. *Circulation*. 2007;115:1306–1324 (publicado también en *Heart Rhythm*. 2007;4:394–412). [PDF de la HRS](https://hrsonline.org/documents/part-i-electrocardiogram-and-its-technologypdf/download)
- **[W2009]** Wagner GS, Macfarlane P, Wellens H, et al. AHA/ACCF/HRS recommendations for the standardization and interpretation of the electrocardiogram: part VI: acute ischemia/infarction. *Circulation*. 2009;119:e262–e270. [PDF de la HRS](https://hrsonline.org/documents/standardization-and-interpretation-electrocardiogram-part-vipdf/download)
- **[RCP2017]** Royal College of Physicians. *National Early Warning Score (NEWS) 2: Standardising the assessment of acute-illness severity in the NHS. Updated report of a working party.* Londres: RCP; 2017. [Resumen ejecutivo](https://www.rcp.ac.uk/media/ctulqqbn/news2-executive-summary_0.pdf) · [Informe completo](https://www.rcp.ac.uk/media/a4ibkkbf/news2-final-report_0_0.pdf)
- **[B2012]** Berry RB, Budhiraja R, Gottlieb DJ, et al. Rules for scoring respiratory events in sleep: update of the 2007 AASM Manual. *J Clin Sleep Med*. 2012;8(5):597–619. (Ya citada en el repo.)
- **[E2009]** Epstein LJ, Kristo D, Strollo PJ Jr, et al. Clinical guideline for the evaluation, management and long-term care of obstructive sleep apnea in adults. *J Clin Sleep Med*. 2009;5(3):263–276. (Ya citada en el repo.)
- **[IFCN2017]** Kane N, Acharya J, Beniczky S, et al. A revised glossary of terms most commonly used by clinical electroencephalographers and updated proposal for the report format of the EEG findings. Revision 2017. *Clin Neurophysiol Pract*. 2017;2:170–185. doi:10.1016/j.cnp.2017.07.002. [PDF](https://discovery-pp.ucl.ac.uk/id/eprint/10076640/1/Kane_1-s2.0-S2467981X17300215-main.pdf)

**Libros de texto (acceso abierto)**
- **[MCM]** Sibbald M, Dąbrowski A, Leśniak W. Standard Electrocardiography. En: *McMaster Textbook of Internal Medicine*. Cracovia: Medycyna Praktyczna. [Capítulo en línea](https://empendium.com/mcmtextbook/chapter/B31.1269.3.6.1)
- **[CS2023]** Cheyne Stokes Respirations. En: *StatPearls*. Treasure Island (FL): StatPearls Publishing; actualizado el 31 de julio de 2023. NCBI Bookshelf NBK448165. [Capítulo](https://www.statpearls.com/point-of-care/19395) (Autores: completar desde NBK448165; la página consultada solo muestra al editor, Bollu PC.)
- **[AR2025]** Porter R, Graham DD. Abnormal Respirations. En: *StatPearls*. Treasure Island (FL): StatPearls Publishing; actualizado el 13 de diciembre de 2025. NCBI Bookshelf NBK470309; PMID 29262235. [Capítulo](https://www.statpearls.com/point-of-care/23959) (Autores corregidos según PubMed el 16 de noviembre de 2026: decía «Whited L, Graham DD».)

**Artículos originales**
- **[KORS1990]** Kors JA, van Herpen G, Sittig AC, van Bemmel JH. Reconstruction of the Frank vectorcardiogram from standard electrocardiographic leads: diagnostic comparison of different methods. *Eur Heart J*. 1990;11(12):1083–1092. doi:10.1093/oxfordjournals.eurheartj.a059647.
- **[VZ2014]** Vozda M, Peterek T, Cerny M. Novel method for deriving vectorcardiographic leads based on artificial neural networks. En: *Electrocardiology 2014 – Proceedings of the 41st International Congress on Electrocardiology*; 2014:61–64. [PDF](https://www.measurement.sk/ICE2014/proceedings/061.pdf)

**Lectura complementaria (verificar capítulo y página en el ejemplar antes de citar)**
- Hall JE, Hall ME. *Guyton and Hall Textbook of Medical Physiology*. 14.ª ed. Elsevier; 2021. Capítulos de electrocardiografía (fundamentos, análisis vectorial y arritmias). El proyecto ya cita esta edición (cap. 61).
- Posner JB, Saper CB, Schiff ND, Claassen J. *Plum and Posner's Diagnosis and Treatment of Stupor and Coma*. Oxford University Press. Patrones respiratorios de origen troncoencefálico (respiración atáxica).

---

## Hoja de firma

| # | Tema | Decisión de Luis |
|---|---|---|
| 1 | El ECG en papel y el rótulo del filtro | ☑ firmado |
| 2 | Frecuencia cardiaca (sustituye las capas genéricas) | ☑ firmado |
| 3 | Ondas e intervalos | ☑ firmado |
| 4 | Las 12 derivaciones | ☑ firmado |
| 5 | Tabla de isquemia (sustituye la tabla actual) | ☑ firmado |
| 6 | NEWS2 | ☑ firmado |
| 7 | Patrones respiratorios (y atáxica sin fisiopatología) | ☑ firmado |
| 8 | Bandas del EEG | ☑ firmado |
| 9 | ECG en 3D (y destino de "Oehler 2014") | ☑ firmado |
| 10 | Cómo se mide la respiración | ☑ firmado |


**Decisiones adicionales firmadas:** (1) atáxica solo como simulación; (2) auditar y corregir «Oehler 2014»; (3) completar los metadatos de StatPearls y Kors 1990 en la bibliografía; (4) retirar las capas genéricas de frecuencia cardiaca.