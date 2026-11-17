# Teoría citada para BIOCORE (2): EMG y HRV — borrador para firma

**Estado:** FIRMADO por Luis Nazariego Santome el 17 de noviembre de 2026 (temas A1–A9 y B1–B9, con las restricciones anotadas en cada uno).
**Uso:** igual que `teoria_citada.md`: Claude Code integra cada tema firmado en la teoría en capas (idea · mecanismo · detalle con fuente) y en la Bibliografía. El texto está redactado con palabras propias a partir de las fuentes.
**Regla:** cada afirmación lleva su fuente entre corchetes. Las notas «Decisión de Luis» registran lo resuelto al firmar. Lo que no encontré en una fuente verificada **no está escrito**: se lista como "sin fuente" al final de cada parte.

---

# Parte A — Electromiografía de superficie (EMG)

## A1. Qué es el EMG de superficie

**Idea.** El EMG de superficie registra, desde la piel, la suma de los potenciales de acción de las unidades motoras que están activas bajo el electrodo [DL1997].

**Mecanismo.** Lo que se detecta depende del volumen que "ve" el electrodo: ese volumen determina cuántos potenciales de unidad motora componen la señal y con qué peso [DL1997].

**Detalle.** La amplitud del EMG de superficie indica la **excitación** del músculo, no su fuerza [V2018].

## A2. Unidad motora y reclutamiento

**Idea.** El músculo aumenta su fuerza de dos maneras: activando unidades motoras nuevas (reclutamiento) y haciendo que las ya activas disparen más rápido [DL1997].

**Mecanismo.** Cada unidad motora reclutada aporta un "cuanto" de fuerza. Cuando la fuerza sigue subiendo, la frecuencia de disparo de esa unidad aumenta, pero su contribución de fuerza llega a saturarse, mientras que cada potencial sigue sumando energía a la señal. Por eso la amplitud del EMG puede crecer más rápido que la fuerza [DL1997].

**Detalle.** Con la amplitud del EMG de superficie no se puede distinguir cuánto se debe al reclutamiento y cuánto a la frecuencia de disparo [V2018].

## A3. Colocación de los electrodos

**Idea.** Dónde se pone el electrodo cambia la señal; por eso la colocación se estandariza [DL1997][H2000].

**Mecanismo.** Recomendación clásica: en la línea media del vientre muscular, entre la unión miotendinosa y la zona de inervación más cercana, con las superficies de detección orientadas perpendicularmente a las fibras [DL1997].

**Detalle.**
- El proyecto europeo SENIAM elaboró un procedimiento general y recomendaciones de colocación detalladas para 27 músculos [H2000].
- Cuanto menor es la distancia entre electrodos, menor es el volumen de captación [V2018].
- Para comparar registros, los electrodos deben ir en el mismo sitio de la piel respecto al músculo [V2018].

> **Decisión de Luis:** se excluyen las dimensiones de SENIAM (tamaño del electrodo y distancia entre electrodos) porque no están verificadas.

## A4. Filtrado

**Idea.** El EMG de superficie se filtra para quitar los artefactos sin perder la señal útil [DL2010].

**Mecanismo** [DL2010]:
- **Pasa-altas de 20 Hz** (Butterworth, 12 dB/octava) para uso general: el artefacto de movimiento concentra su energía en frecuencias bajas y cae rápidamente por encima de 20 Hz; la energía del EMG por debajo de 20 Hz es poca e inestable.
- **Pasa-bajas entre 400 y 450 Hz:** el espectro del EMG captado con sensores comunes va de 0 a unos 400 Hz.

**Detalle.** Un corte de 10 Hz puede dejar demasiado ruido de movimiento [DL2010]. (El filtro de 20–450 Hz de BIOCORE coincide con esta recomendación.)

## A5. Amplitud: RMS y valor rectificado

**Idea.** Para medir la amplitud de una contracción voluntaria se recomienda el valor RMS [DL1997].

**Mecanismo.** El RMS representa la potencia de la señal y tiene un significado físico claro; el valor medio rectificado mide el área bajo la señal y no tiene un significado físico específico [DL1997].

## A6. Normalización (% de la contracción máxima)

**Idea.** La amplitud en microvoltios no se puede comparar entre personas, músculos o sesiones; por eso suele normalizarse, por ejemplo a la contracción voluntaria isométrica máxima [V2018].

**Mecanismo.** Si la persona no alcanza su máximo real durante la prueba de referencia (por dolor, por ejemplo), los valores normalizados quedan inflados [V2018].

**Detalle.** Incluso normalizada, la amplitud no permite deducir la fuerza del músculo [V2018]. Normalizar por encima de 80 % de la contracción máxima no es fiable [DL1997].

## A7. Fatiga y frecuencia mediana

**Idea.** Durante una contracción sostenida, el espectro del EMG se "comprime" hacia frecuencias más bajas, y la frecuencia mediana es el índice preferido para seguir ese cambio [DL1997].

**Mecanismo.** Con el tiempo de contracción, los potenciales de acción duran más; alrededor de 65 % de ese aumento se explica por la caída de la velocidad de conducción de las fibras. En contracciones isométricas de fuerza constante por encima de 30 % de la máxima, el cambio espectral se debe sobre todo a la acumulación de ácido láctico [DL1997].

**Detalle.** (En BIOCORE, el índice de fatiga está "no disponible" con la señal demo, porque su espectro es plano: el criterio sigue siendo válido con una señal real.)

## A8. Artefactos y contaminación

**Idea.** Factores distintos del esfuerzo muscular modifican la señal [V2018].

**Detalle.**
- **Diafonía (crosstalk):** hasta 17 % de la actividad eléctrica de músculos vecinos puede detectarse en el electrodo [DL1997].
- **Tejido subcutáneo** y diferencias anatómicas cambian la amplitud [V2018].
- **Artefacto de movimiento:** de baja frecuencia, es la razón del corte de 20 Hz [DL2010].

## A9. Qué no se puede concluir con un EMG de superficie

**Idea.** El EMG de superficie es útil para entender el sistema neuromuscular, pero su aplicabilidad práctica es limitada [V2018].

**Detalle** [V2018]:
- **No** permite deducir la fuerza muscular.
- **No** predice la hipertrofia ni la adaptación a largo plazo.
- **No** distingue reclutamiento de frecuencia de disparo.
- **Sí** permite, con cautela, decir si un músculo está "encendido" o "apagado" en intervalos de más de unos 200 ms, y hacer comparaciones dentro de la misma persona y el mismo músculo si se controlan las condiciones.

> **Decisión de Luis:** las conclusiones se restringen a lo que dice [V2018] para deporte y rehabilitación; no se afirma nada sobre diagnósticos ni lesiones.

**Sin fuente verificada (no se escribe):** la contaminación del EMG por el ECG en los músculos del tronco; las dimensiones de los electrodos SENIAM.

---

# Parte B — Variabilidad de la frecuencia cardiaca (HRV)

## B1. Qué es la HRV

**Idea.** La HRV es la variación del tiempo entre latidos consecutivos [SG2017].

**Mecanismo.** Se calcula sobre intervalos NN ("normal a normal"): intervalos entre latidos sinusales de los que se han retirado los artefactos [SG2017].

## B2. Dominio del tiempo: SDNN, RMSSD y pNN50

**Idea.** Las medidas del dominio del tiempo resumen cuánto varían los intervalos NN [SG2017].

**Mecanismo** [SG2017]:
- **SDNN:** desviación estándar de los intervalos NN, en ms.
- **RMSSD:** está más influida por el sistema nervioso parasimpático que la SDNN.
- **pNN50:** se correlaciona estrechamente con la actividad parasimpática.

## B3. Dominio de la frecuencia: bandas y la razón LF/HF

**Idea.** El análisis espectral reparte la variabilidad en bandas de frecuencia [SG2017].

**Detalle** [SG2017]:

| Banda | Rango |
|---|---|
| ULF | ≤ 0.003 Hz |
| VLF | 0.0033–0.04 Hz |
| LF | 0.04–0.15 Hz |
| HF ("banda respiratoria") | 0.15–0.40 Hz |

- La banda HF está influida por la respiración entre 9 y 24 respiraciones por minuto [SG2017].
- **La razón LF/HF es discutida:** la potencia LF no es un índice del impulso simpático cardiaco, sino una mezcla de influencias simpáticas, parasimpáticas y otras no identificadas; por eso la razón LF/HF no mide con exactitud el "equilibrio simpático-vagal" [B2013][SG2017].

> **Decisión de Luis:** donde BIOCORE muestre la razón LF/HF, lleva obligatoriamente el rótulo "razón LF/HF (interpretación discutida)" con la cita [B2013]; nunca "balance simpático-vagal".

## B4. Duración del registro

**Idea.** Los valores de HRV dependen de la duración del registro [SG2017].

**Detalle.** Los valores de registros cortos y ultracortos no son intercambiables con los de 24 horas, y no es apropiado comparar métricas como la SDNN calculadas sobre periodos de distinta duración [SG2017].

## B5. Arritmia sinusal respiratoria

**Idea.** La arritmia sinusal respiratoria es la aceleración y desaceleración del corazón con la respiración, mediada por el nervio vago [SG2017].

**Detalle.** Por eso la frecuencia respiratoria cambia la banda en la que aparece esa variabilidad (ver B3) [SG2017].

## B6. Medidas no lineales

**Idea.** Las medidas no lineales cuantifican lo impredecible y lo complejo de la serie de intervalos [SG2017].

**Detalle** [SG2017]:
- **Gráfico de Poincaré (SD1 y SD2):** mide la impredecibilidad de la serie RR.
- **Entropía muestral:** se diseñó como una medida menos sesgada y más fiable de la regularidad y la complejidad de la señal.
- **DFA α1:** la pendiente que describe las fluctuaciones breves.

## B7. Qué modifica la HRV

**Detalle.** La duración del registro, la edad y el sexo influyen en los valores basales; las medidas del dominio del tiempo disminuyen con la edad [SG2017]. La respiración modifica la banda HF (ver B3 y B5) [SG2017].

> **Decisión de Luis:** los factores modificantes se restringen exclusivamente a edad, sexo, duración del registro y respiración.

**Sin fuente verificada (no se escribe):** el efecto de la postura, los fármacos y el ejercicio.

## B8. Calidad de la serie: artefactos y latidos ectópicos

**Idea.** Los artefactos distorsionan de forma importante tanto las medidas del tiempo como las de la frecuencia [SG2017].

**Detalle.** Editar los latidos ectópicos y las arritmias es difícil; se puede elegir un tramo sin artefactos, editar los intervalos afectados o interpolar los latidos perdidos [SG2017].

## B9. Valores de referencia

**Idea.** No hay un único "valor normal": los valores de referencia dependen de la duración del registro, la edad y el sexo, y los de registros cortos no sirven para comparar con los de 24 horas [SG2017].

> **Decisión de Luis:** se omiten las cifras de referencia porque no están verificadas.

---

## Bibliografía

- **[DL1997]** De Luca CJ. The use of surface electromyography in biomechanics. *J Appl Biomech*. 1997;13(2):135–163. [PDF](https://people.stfx.ca/smackenz/Courses/HK474/Readings/THE%20USE%20OF%20SURFACE%20ELECTROMYOGRAPHY.pdf)
- **[DL2010]** De Luca CJ, Gilmore LD, Kuznetsov M, Roy SH. Filtering the surface EMG signal: movement artifact and baseline noise contamination. *J Biomech*. 2010;43(8):1573–1579. doi:10.1016/j.jbiomech.2010.01.027. [PDF](https://www.bu.edu/nmrc/files/2010/06/103.pdf)
- **[V2018]** Vigotsky AD, Halperin I, Lehman GJ, Trajano GS, Vieira TM. Interpreting signal amplitudes in surface electromyography studies in sport and rehabilitation sciences. *Front Physiol*. 2018;8:985. doi:10.3389/fphys.2017.00985. [PDF](https://iris.polito.it/retrieve/handle/11583/2697782/183144/Vigotsky_et_al_2018-FP.pdf)
- **[H2000]** Hermens HJ, Freriks B, Disselhorst-Klug C, Rau G. Development of recommendations for SEMG sensors and sensor placement procedures. *J Electromyogr Kinesiol*. 2000;10(5):361–374. doi:10.1016/S1050-6411(00)00027-4.
- **[SG2017]** Shaffer F, Ginsberg JP. An overview of heart rate variability metrics and norms. *Front Public Health*. 2017;5:258. doi:10.3389/fpubh.2017.00258. [Artículo](https://www.frontiersin.org/journals/public-health/articles/10.3389/fpubh.2017.00258)
- **[B2013]** Billman GE. The LF/HF ratio does not accurately measure cardiac sympatho-vagal balance. *Front Physiol*. 2013;4:26. doi:10.3389/fphys.2013.00026. [PDF](https://www.frontiersin.org/journals/physiology/articles/10.3389/fphys.2013.00026/pdf)
- **[TF1996]** Task Force of the European Society of Cardiology and the North American Society of Pacing and Electrophysiology (Camm AJ, Malik M, Bigger JT, et al.). Heart rate variability: standards of measurement, physiological interpretation and clinical use. *Circulation*. 1996;93(5):1043–1065. doi:10.1161/01.CIR.93.5.1043. Es el estándar fundacional de la HRV. **No pude leer su texto completo**, así que ninguna afirmación de este documento se le atribuye directamente; las definiciones vienen de [SG2017], que se basa en él.

---

## Hoja de firma

| # | Tema | Decisión de Luis |
|---|---|---|
| A1 | Qué es el EMG de superficie | ☑ firmado |
| A2 | Unidad motora y reclutamiento | ☑ firmado |
| A3 | Colocación de electrodos (sin dimensiones SENIAM) | ☑ firmado |
| A4 | Filtrado 20–450 Hz | ☑ firmado |
| A5 | RMS frente a valor rectificado | ☑ firmado |
| A6 | Normalización | ☑ firmado |
| A7 | Fatiga y frecuencia mediana | ☑ firmado |
| A8 | Artefactos y contaminación | ☑ firmado |
| A9 | Qué no se puede concluir (sin "diagnóstico" ni "lesión") | ☑ firmado |
| B1 | Qué es la HRV | ☑ firmado |
| B2 | SDNN, RMSSD y pNN50 | ☑ firmado |
| B3 | Bandas y razón LF/HF (rotular "interpretación discutida") | ☑ firmado |
| B4 | Duración del registro | ☑ firmado |
| B5 | Arritmia sinusal respiratoria | ☑ firmado |
| B6 | Medidas no lineales | ☑ firmado |
| B7 | Qué modifica la HRV (solo edad, sexo, duración y respiración) | ☑ firmado |
| B8 | Artefactos y latidos ectópicos | ☑ firmado |
| B9 | Valores de referencia (sin cifras hasta verificarlas) | ☑ firmado |