# Teoría citada para BIOCORE — 3: Hemodinámica

**Estado:** FIRMADO 2026-11-17 por Luis Nazariego Santome («firmo todo, pero que salga de referencias verídicas»). La firma vale con esa condición: cada afirmación de este documento sale del resumen publicado de su fuente, leído el 17-11-2026 en su registro bibliográfico (Consensus: Semantic Scholar, OpenAlex y PubMed); la lista y los enlaces están al final. Lo que esos resúmenes no dicen no está aquí.
**Uso:** es la única fuente del texto médico sobre hemodinámica en BIOCORE (banco `HEMO_QUESTIONS`, `docs/contenido/banco_preguntas_hemodinamica.md`). Se cita como «t3:N» (N = número de línea).
**Redacción:** con palabras propias, a partir de los resúmenes; no copia pasajes.

---

## 1. Presión arterial media (PAM)

**Idea.** La presión arterial media es la presión arterial promedio a lo largo de un ciclo cardiaco, en sístole y en diástole [DW2019].

**Mecanismo.**
- La PAM representa la presión de perfusión [ME2000].
- La PAM depende del gasto cardiaco y de la resistencia vascular sistémica [DW2019].

**Detalle con fuente.**
- En la clínica, la PAM se estima con la presión arterial: se suma a la presión diastólica una fracción de la presión de pulso (la diferencia entre sistólica y diastólica) [JO2024].
- Durante muchos años se ha usado una fórmula empírica: la PAM queda a un tercio de la distancia entre la presión diastólica y la sistólica, es decir, diastólica + 1/3 de la presión de pulso [ME2000].
- Esa fórmula tiene limitaciones, porque la PAM verdadera es el promedio de las presiones instantáneas en el tiempo [ME2000].
- En 632 pacientes de cuidados intensivos con catéter radial o femoral, usar la fracción fija de 0.33 dio estimaciones exactas y precisas de la PAM [JO2024].

---

## 2. Gasto cardiaco y volumen sistólico

**Idea.** El gasto cardiaco es el producto de la frecuencia cardiaca por el volumen sistólico [DW2019].

**Mecanismo.**
- El volumen sistólico depende de la inotropía (la fuerza de contracción) del ventrículo y de la precarga [DW2019].
- La precarga depende del volumen de sangre y de la distensibilidad de las venas: aumentar el volumen de sangre aumenta la precarga, el volumen sistólico y, por lo tanto, el gasto cardiaco [DW2019].
- Un aumento de la poscarga disminuye el volumen sistólico [DW2019].

**Detalle con fuente.**
- Ley de Frank–Starling: el corazón ajusta la eyección a los cambios del llenado ventricular [SQ2015].

---

## 3. Resistencia vascular y PAM

**Idea.** La relación entre presión y flujo en la circulación es análoga a la ley de Ohm: un aumento de la PAM solo puede venir de un aumento del gasto cardiaco, de la resistencia periférica, o de ambos [MY2003].

**Mecanismo.**
- La resistencia vascular sistémica depende sobre todo del radio de los vasos: disminuir el radio aumenta la resistencia [DW2019].
- La viscosidad de la sangre también influye en la resistencia, pero su papel es menor [DW2019].
- La resistencia periférica la dominan las arterias pequeñas y las arteriolas, de 30 a 300 µm de diámetro [MY2003].

---

## 4. Qué modela BIOCORE (no es texto clínico)

- El lazo cerrado de BIOCORE (reimplementación de las ecuaciones RCR de svZeroDSolver, `THIRD_PARTY_NOTICES.md`) está habilitado en sano, hipertensión y sepsis; en «¿Qué pasa si…?» el gasto cardiaco es volumen sistólico × frecuencia cardiaca, igual que en la línea t3:27.
- En la sepsis, la presión arterial del modelo depende de la capacitancia venosa 2× (Criterio BIOCORE, sin cita) y está en revisión clínica; nada de este documento la valida.

---

## Bibliografía (leída el 17-11-2026 en Consensus)

- **[DW2019]** DeMers D, et al. Physiology, Mean Arterial Pressure. *StatPearls*. Treasure Island (FL): StatPearls Publishing; 2019. [Registro](https://consensus.app/papers/details/w:8df53f3a-df91-4c5b-88d8-55afabeabd83/)
- **[ME2000]** Meaney E, et al. Formula and nomogram for the sphygmomanometric calculation of the mean arterial pressure. *Heart*. 2000. [Registro](https://consensus.app/papers/details/w:82b2646b-b849-4db3-871e-d97746887ee4/)
- **[JO2024]** Jozwiak M, et al. Value and Variability of Pulse Shape Indicator for Estimating Mean Arterial Pressure in the Radial and Femoral Arteries. *Journal of the American Heart Association*. 2024. [Registro](https://consensus.app/papers/details/w:b3ea8507-dbe6-474c-ad8e-f64d0e34721b/)
- **[MY2003]** Mayet J, et al. Cardiac and vascular pathophysiology in hypertension. *Heart*. 2003. [Registro](https://consensus.app/papers/details/w:1d168653-b62e-4650-aa40-09b3f80606c9/)
- **[SQ2015]** Sequeira V, et al. Historical perspective on heart function: the Frank–Starling Law. *Biophysical Reviews*. 2015. [Registro](https://consensus.app/papers/details/w:1789598a-bd26-4709-bdb3-3cedc967949c/)

*Pendiente de completar en la fuente original (no se pudo abrir NCBI ni PubMed desde el entorno de trabajo):* volumen, páginas y DOI de cada artículo; los registros de arriba dan autor principal, título, revista y año.
