# Fichas de acoplamiento: hipoxia → taquicardia y músculo → autonómico

**Estado: FIRMADO por Luis Nazariego Santome el 2026-11-18** («firmo las dos fichas de acoplamiento»). Se firmaron las **propuestas** de cada ficha (ver la hoja de firma al final):
- **Ficha 1:** transcrita al catálogo como `HIPOXIA_TAQUICARDIA` (`domain/physiology/coupling/catalog.py`, `VALIDATED_RULES`). Los escenarios y el gemelo ya guardan la SpO₂ y la FC en un mismo snapshot, pero esos guardados no evalúan las reglas de acoplamiento (hoy solo lo hacen el compositor del EEG con la FC y el guardado del EEG), así que la regla aún no dispara en el flujo vivo: eso es la T6 del diseño.
- **Ficha 2:** opción A. La regla queda firmada y **pendiente** hasta que el EMG tenga una calibración de la contracción máxima; no entra al catálogo antes, porque su ancla no existe hoy.

Preparado el 2026-11-18 a pedido de Luis («busca la literatura para poder firmarla»). Formato: el de la ficha de `AROUSAL_TAQUICARDIA_BAR` (dirección, ancla, magnitud, fuente, confianza y escenarios bloqueados), más la ventana fisiológica que pide la decisión 5 del diseño.

**Cómo se verificaron las fuentes:** cada cifra viene de la fuente que se cita, y junto a cada una se dice si se leyó el texto completo o solo el resumen. Nada se tomó de memoria. Lo que no se pudo confirmar dice «por confirmar».

**Cada ficha deja abiertas tres decisiones para Luis** (marcadas con ☐): umbral, magnitud y confianza. Junto a cada decisión va la propuesta y lo que cuesta cada opción.

---

## Ficha 1 · HIPOXIA_TAQUICARDIA (decisión 5 del diseño)

### Dirección y mecanismo
SpO₂ baja → ↑ frecuencia cardiaca. Los quimiorreceptores periféricos (cuerpo carotídeo) se activan. La taquicardia de la hipoxia aguda isocápnica está mediada sobre todo por la **retirada vagal**.

- Lucy y cols. 2000: «tachycardia induced by moderate IC hypoxaemia (arterial O2 saturation 85 %) was mediated by vagal withdrawal» *(resumen)*.
- Niewinski y cols. 2025: la denervación parasimpática cardiaca redujo la pendiente de la FC frente a la SpO₂ de 0.58 ± 0.21 a 0.22 ± 0.13 lpm por % de SpO₂ (p = 0.0001). Los autores concluyen que la reactividad de la FC a la hipoxia aguda «is significantly influenced by parasympathetic system» *(texto completo)*.
- Halliwill y cols. 2003 atribuyen el aumento de la FC a la activación del quimiorreflejo periférico, no a la hiperpnea. Suponen, sin medirlo, que la respuesta cardiaca está dominada por cambios en la salida vagal *(texto completo)*.

### Datos cuantitativos de las fuentes

| Fuente | Población y condición | SpO₂ | FC | Lectura |
|---|---|---|---|---|
| Halliwill 2003 (texto completo) | 12 sanos normotensos, hipoxia isocápnica sostenida | objetivo 85 %, medida 85.7 ± 0.3 % | normoxia 61.2 ± 1.8 → hipoxia 74.7 ± 2.7 lpm (tabla 2) | **+13.5 lpm** a ~86 % de SpO₂ |
| Niewinski 2025 (texto completo) | 11 adultos jóvenes antes de una cardioneuroablación por síncope vasovagal (sin grupo control sano), pulsos breves de nitrógeno | mínimo 59.4 ± 9.1 % | pendiente 0.58 ± 0.21 lpm/% | respuesta **proporcional** a la caída de SpO₂ |
| Lucy 2000 (resumen) | sanos, hipoxia isocápnica de 22 min, supino y sentado | ~85 % | intervalo entre pulsos acortado (p < 0.001); la cifra en lpm no está en el resumen | mecanismo: retirada vagal |
| Pinna 2025 (texto completo) | 6 pacientes con insuficiencia cardiaca y Cheyne-Stokes, hipoxia transitoria | — | la FC empezó a subir cuando la SpO₂ estimada en el quimiorreceptor bajó de 95 %; pico de la FC 7.9 ± 4.8 s después del pico del volumen corriente | latencia de segundos (pacientes, no sanos) |

Pendiente que sale de Halliwill: 13.5 lpm ÷ (98.8 − 85.7) % ≈ 1.0 lpm por %. El 98.8 ± 0.2 % es la SpO₂ en normoxia de la misma tabla (revisión final de la T4: el borrador decía «≈ 97 %, por confirmar»).

### Ancla (condición) ☐
- Dominio y descriptor: `respiratory` / `spo2`.
- **Propuesta del ancla:** `spo2 ≤ 91 %`. Es el límite de la banda de 3 puntos NEWS2 de la SpO₂ escala 1 que la plataforma ya usa (RCP 2017, `clinical.calculators.news2_spo2_scale1_score`, evento `SPO2_NEWS2_3_POINTS`). La ventaja es no introducir un umbral nuevo.
- **Opción B del ancla:** `spo2 ≤ 86 %`, el nivel donde Halliwill midió +13.5 lpm. Es más fiel a la cifra, pero deja sin respuesta toda la franja 87–91 %.
- **Lo que hay que saber:** la fuente no da un «umbral». La respuesta es continua y crece con la caída (Niewinski). Cualquier umbral fijo es un Criterio BIOCORE que cuantiza una relación continua, y así debe rotularse.

### Magnitud ☐
El motor de reglas hoy solo admite una magnitud fija (`magnitude_delta`).
- **Propuesta:** **+13 lpm** con el ancla en 91 %. Es la cifra medida en sanos con SpO₂ de ~86 % (Halliwill). En la franja 87–91 % sobreestima. `magnitude_hint`: «+13.5 lpm a SpO₂ ~86 % en sanos, hipoxia isocápnica (Halliwill 2003); pendiente 0.6–1.0 lpm por % de caída».
- **Opción B de la magnitud:** una magnitud proporcional, 0.6 lpm por cada % bajo el 95 %. Es más fiel a la fisiología, pero exige ampliar `CouplingEffect` (cambio en `domain/`, con prueba y firma). Ojo: esa pendiente mezcla poblaciones. El 0.6 es de Niewinski (11 pacientes con síncope vasovagal, sin grupo control sano) y el umbral del 95 % es de Pinna (6 pacientes con insuficiencia cardiaca); ninguna de las dos es de sanos. En sanos, la única cifra es la de Halliwill (≈ 1.0 lpm por %).

### Fuentes (para el campo `source`)
- Halliwill JR, Morgan BJ, Charkoudian N. Peripheral chemoreflex and baroreflex interactions in cardiovascular regulation in humans. *J Physiol* 2003;552(Pt 1):295–302. doi:10.1113/jphysiol.2003.050708.
- Niewinski P, Tubek S, Josiak K, Nowak K, Ponikowski P. Cardiac parasympathetic denervation reduces hypoxic tachycardia, baroreflex sensitivity and heart rate variability in humans. *Sci Rep* 2025;15:6633. doi:10.1038/s41598-025-91214-6.
- Lucy SD, Hughson RL, Kowalchuk JM, Paterson DH, Cunningham DA. Body position and cardiac dynamic and chronotropic responses to steady-state isocapnic hypoxaemia in humans. *Exp Physiol* 2000;85(2):227–237. doi:10.1111/j.1469-445X.2000.01932.x.
- De contexto, sin cifra para la regla: Pinna GD, Robbi E, La Rovere MT, Maestri R. Heart rate response to transient hypoxia in patients with heart failure and Cheyne–Stokes respiration. *Exp Physiol* 2025. doi:10.1113/EP092304. Volumen y páginas por confirmar.
- Clásico que no se pudo leer (la página no cargó): Slutsky AS, Rebuck AJ. Heart rate response to isocapnic hypoxia in conscious man. *Am J Physiol* 1978;234(2):H129–H132. doi:10.1152/ajpheart.1978.234.2.H129. **No citar** hasta leerlo.

### Confianza ☐
**Propuesta:** `VALIDADO_POR_FUENTE` → 0.70, la misma banda que la regla BAR. Sigue siendo un cálculo, no una medición. Con la propuesta del ancla (umbral NEWS2 de 91 % y magnitud medida a otra SpO₂, 86 %), una confianza menor también es defendible: `TRANSCRITO_SIN_VALIDAR` → ≈ 0.35, dentro de la banda baja de `DERIVADO_ACOPLAMIENTO` (0.30–0.45, `domain/physiology/state/schema.py`).

### Escenarios donde NO aplica (doble contabilidad)
Son los escenarios cuyo simulador ya modela la FC junto con la caída de la SpO₂ (`app/engines/simulation_engine.py`):
- `hypoxia`: «compensatory_tachycardia».
- `apnea`: FC «irregular» con caídas periódicas de SpO₂.
- `copd`: FC «elevated_baseline» con SpO₂ «low_baseline».
- `sepsis`: «sustained_tachycardia» con SpO₂ «declining».
- `seizure`, `stress` y `anxiety`: ya están en `COUPLING_DISABLED_SCENARIOS` (los dos últimos ya modelan la descarga simpática).

Se propone sumar `hypoxia`, `apnea`, `copd` y `sepsis` a `COUPLING_DISABLED_SCENARIOS` **solo para esta regla**. Hoy la lista es global, así que hace falta una lista de bloqueo por regla (cambio en `domain/`).

**De dónde saldría una SpO₂ ≤ 91 % con esos escenarios bloqueados:** del laboratorio de Respiración (la SpO₂ del modelo BIOCORE durante una apnea, «Guardar al gemelo»: hoy escribe la basal, no el nadir) o de los sliders del gemelo. Con los escenarios bloqueados, la regla solo dispararía con esas entradas, ambas simulación.

### Ventana fisiológica de la SpO₂ ☐
- **Propuesta:** la SpO₂ y la FC deben venir de la misma ventana de **120 s**, la que ya usa la FC en el compositor (`DEFAULT_MAX_HR_CARRY_AGE_S`). Criterio BIOCORE.
- **Por qué:** la respuesta cardiaca a la hipoxia tarda segundos (Pinna 2025, en pacientes: pico de la FC unos 8 s después del pico ventilatorio) y en 22 min de hipoxia sostenida se mantiene (Lucy 2000). Una SpO₂ de hace más de dos minutos ya no describe el estímulo actual del quimiorreceptor.

### Lo que la plataforma puede y no puede dar hoy
- **La SpO₂ que llega al UPS es simulación.** Sale del modelo del laboratorio de Respiración o de los escenarios; la placa de pulso no calcula SpO₂ (falta la curva de calibración, CLAUDE.md). La regla dispararía sobre SpO₂ simulada y el resultado se rotula así (`DERIVADO_ACOPLAMIENTO` sobre entradas de simulación).
- El compositor hoy solo junta `bar` + `heart_rate`. Para esta regla hay que generalizarlo a pares definidos por las reglas firmadas: es la T6 del diseño.

### Para firmar (Luis)
☐ Ancla: `spo2 ≤ 91 %` (propuesta) / `≤ 86 %` (opción B del ancla)
☐ Magnitud: +13 lpm fija (propuesta) / proporcional 0.6 lpm por % (opción B de la magnitud, requiere cambio en `domain/`)
☐ Confianza: 0.70 (propuesta) / ≈ 0.35, `TRANSCRITO_SIN_VALIDAR`
☐ Escenarios bloqueados: `hypoxia`, `apnea`, `copd`, `sepsis`, `seizure`, `stress`, `anxiety`
☐ Ventana: 120 s

---

## Ficha 2 · CONTRACCION_ISOMETRICA_TAQUICARDIA (músculo → autonómico; decisión 3 del diseño)

### Dirección y mecanismo
Una contracción isométrica sostenida produce ↑ FC.
- **Al principio:** por **comando central** con menor actividad parasimpática. Limberg 2014: «Central command plays an important role in decreased parasympathetic efferent activity and increased heart rate» *(texto completo)*.
- **Después, el metaborreflejo** sube sobre todo la actividad simpática y la presión arterial, **no la FC**. En el mismo trabajo, la FC volvió al reposo durante la isquemia posejercicio: «none of the rise in heart rate with static handgrip exercise can be attributed to the metaboreflex» *(texto completo)*.

### Datos cuantitativos de las fuentes

| Fuente | Población y condición | FC |
|---|---|---|
| Limberg 2014 (texto completo, tabla 2) | adultos jóvenes control, empuñadura sostenida 2 min | 15 % CVM: 60 ± 3 → 68 ± 2 lpm (**+9 ± 2**); 30 % CVM: 60 ± 3 → 75 ± 4 lpm (**+14 ± 2**); a la fatiga en 30 %: 78 ± 4 |
| Incognito 2018 (texto completo, tabla 1) | hombres jóvenes, empuñadura al 30 % CVM | reposo 60 ± 9; minuto 1: 72 ± 10; minuto 2: 76 ± 10 lpm (**+12 a +16**) |

CVM = contracción voluntaria máxima.

### El problema de fondo: el ancla no existe hoy en la plataforma ☐
Las fuentes anclan la respuesta en el **% de la contracción voluntaria máxima** (15 %, 30 %) y en su **duración** (1–2 min). La plataforma no mide eso: la «activación» del EMG es la media o el máximo de la señal filtrada, no el % de la CVM (CLAUDE.md, «Heurístico, demo o inexistente hoy»). Además, el índice de fatiga no es fiable con la señal demo (decisión 3).

Escribir hoy una regla con «activación > X» sería anclar una cifra de la fuente a una magnitud que no significa lo mismo (Art. I).

**Opciones para firmar:**
- **A (propuesta):** la regla queda **pendiente** hasta que el instrumento EMG tenga una calibración de CVM: el estudiante hace una contracción máxima y la activación se expresa como % de esa CVM, con su procedencia. Entonces el ancla sería: `muscular` / `activation_pct_mvc ≥ 30 %` sostenida ≥ 60 s, con +12 lpm (minuto 1 de Incognito 2018; Limberg da +14 a los 2 min).
- **B:** el cierre de la Unidad Músculo usa el escenario del simulador declarado como **simulación de una contracción isométrica al 30 % de la CVM**, y muestra la respuesta de la FC como **dato de la fuente** («en sanos, +12 a +16 lpm en 2 min; Limberg 2014, Incognito 2018»), sin disparar ninguna regla. Así hay cierre en la T4 sin acoplamiento.
- **C:** anclar en el escenario `fatigue` existente. **No se recomienda:** ese escenario es «fatiga crónica» (24 h, FC sin modelar), no una contracción isométrica.

### Magnitud ☐ (para la opción A)
- **Propuesta:** +12 lpm al minuto de contracción al 30 % de la CVM (Incognito 2018: 60 → 72).
- **Alternativa:** +14 lpm a los 2 min (Limberg 2014).
- `magnitude_hint`: «+9 lpm al 15 % y +14 lpm al 30 % de la CVM en 2 min (Limberg 2014); +12 en el minuto 1 y +16 en el minuto 2 al 30 % (Incognito 2018)».

### Fuentes
- Limberg JK, Morgan BJ, Schrage WG. Mechanical and metabolic reflex activation of the sympathetic nervous system in younger adults with metabolic syndrome. *Auton Neurosci* 2014. doi:10.1016/j.autneu.2014.03.003. PMID 24680829. Volumen por confirmar (la página lo da como «0»); páginas 100–105.
- Incognito AV, Doherty CJ, Lee JB, Burns MJ, Millar PJ. Interindividual variability in muscle sympathetic responses to static handgrip in young men: evidence for sympathetic responder types? *Am J Physiol Regul Integr Comp Physiol* 2018;314(1):R114–R121 (en línea el 25-oct-2017). doi:10.1152/ajpregu.00266.2017. PMID 29070505.

### Confianza ☐
**Propuesta:** `VALIDADO_POR_FUENTE` → 0.70 cuando exista el ancla en % de la CVM (opción A). Con la opción B no hay regla y no aplica.

### Escenarios donde NO aplica (para la opción A)
- `exercise`: ya modela «hr_trend: high_increasing».
- `seizure`: convulsiones, ya bloqueado.
- `stress` y `anxiety`: ya modelan la descarga simpática, ya bloqueados.

### Ventana fisiológica ☐ (para la opción A)
**Propuesta:** el EMG y la FC deben estar en la misma ventana de 120 s, y la contracción debe durar al menos 60 s dentro del registro (Incognito mide la FC por minuto). Criterio BIOCORE.

### Para firmar (Luis)
☐ Camino: A (regla pendiente de la calibración de CVM) / B (cierre de Músculo como simulación declarada con la cifra de la fuente, sin regla)
☐ Si A: ancla 30 % de la CVM ≥ 60 s, magnitud +12 lpm, confianza 0.70, bloqueos `exercise`, `seizure`, `stress`, `anxiety`, ventana 120 s

---

## Hoja de firma
| Ficha | Decisión de Luis | Fecha |
|---|---|---|
| 1 · HIPOXIA_TAQUICARDIA | Propuestas: ancla `spo2 ≤ 91 %`; +13 lpm fijos; confianza 0.70 (`VALIDADO_POR_FUENTE`); bloqueada en `hypoxia`, `apnea`, `copd`, `sepsis` (por regla) y `seizure`, `stress`, `anxiety` (lista global); ventana de 120 s | 2026-11-18 |
| 2 · CONTRACCION_ISOMETRICA_TAQUICARDIA | Opción A: pendiente de la calibración de la CVM; entonces ancla 30 % de la CVM ≥ 60 s, +12 lpm, confianza 0.70, bloqueos `exercise`, `seizure`, `stress`, `anxiety`, ventana de 120 s | 2026-11-18 |

Al transcribir la ficha 1 hizo falta una política para dos reglas sobre la misma señal (ya son dos sobre `heart_rate`). Sin una política firmada, el puente **no combina**: si las dos disparan en el mismo snapshot, no se escribe ningún valor acoplado (`bridge._combine_proposals_for_same_effect`). Sumar o elegir quedaría para otra firma.
