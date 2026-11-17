# Caso guiado de ECG: elevación del ST en II, III y aVF

**Estado:** FIRMADO 2026-11-17 por Luis Nazariego Santome (todos los IDs de la sección 8, con las correcciones de la hoja de revisión ya aplicadas en este documento y en el código).
**Uso:** `educational/guided_case.py` contiene este caso y `app/supermodules/academia/guided_case_view.py` lo muestra en Practicar, página «Caso guiado de ECG» (`caso-guiado`). La pantalla **solo muestra el caso si este documento dice «FIRMADO»**.
**Regla:** todo texto de enseñanza cita su línea firmada del tema 5 de `teoria_citada.md` («t1:N») con [W2009]. Los resultados de las pruebas no se escriben a mano: los mide el analizador de BIOCORE sobre el trazado simulado. `tests/test_guided_case.py` exige que cada texto que ve el estudiante aparezca en este documento, y que cada línea citada exista literal en la teoría firmada.

---

## 1. El trazado

- **Simulado**, y así se declara en pantalla: `generate_twelve_lead("inferior_stemi", seed=7)`, 10 s a 500 muestras/s; el analizador mide 75 lpm.
- **ST medido por el analizador** (`analyze_twelve_lead`, punto J, en mm; verificado el 2026-11-17 con el código de main):

| I | II | III | aVR | aVL | aVF | V1 | V2 | V3 | V4 | V5 | V6 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| -0.7 | +2.1 | +2.9 | -0.7 | -1.8 | +2.5 | +0.0 | +0.0 | +0.0 | +0.0 | +0.0 | +0.0 |

- No hay **derivaciones derechas** (V3R, V4R): el simulador solo genera las 12 estándar. Es la información incompleta del caso, a propósito.

## 2. Líneas firmadas que usa el caso

Números de línea comprobados contra `docs/contenido/teoria_citada.md` de main el 2026-11-17 (no se movieron).

- **t1:29:** **Idea.** La frecuencia cardiaca es el número de latidos por minuto; en el ECG se obtiene dividiendo 60 segundos entre el intervalo RR [MCM].
- **t1:49:** | Intervalo PR | 0.12 a 0.20 s |
- **t1:50:** | Duración del QRS | 0.06 a 0.11 s |
- **t1:51:** | QT prolongado (corregido con Bazett) | ≥ 0.45 s en hombres; ≥ 0.46 s en mujeres |
- **t1:52:** | Eje eléctrico normal | de −30° a +90° |
- **t1:72:** **Idea.** Los cambios del segmento ST en un grupo de derivaciones orientan hacia la región del ventrículo afectada y, con menos certeza, hacia la arteria responsable [W2009].
- **t1:78:** | Elevación del ST en V1–V4, I, aVL y a menudo aVR | Oclusión proximal de la descendente anterior | La isquemia de la pared anterior se debe a oclusión de la descendente anterior (DA). |
- **t1:81:** | Elevación del ST en II, III y aVF | Afectación inferior | Coronaria derecha (CD) o circunfleja (Cx), según cuál dé la descendente posterior (dominancia). Elevación mayor en III que en II sugiere CD. |
- **t1:82:** | Elevación en I y aVL junto con cambios inferiores | Puede acompañar la oclusión de la Cx | — |
- **t1:83:** | Elevación del ST en V3R y V4R (derivaciones derechas) | Afectación del ventrículo derecho | Oclusión proximal de la CD. |
- **t1:84:** | Descenso del ST en V1–V3 | Patrón llamado "posterior" o posterolateral | Puede deberse a CD o Cx; con cambios inferiores no es posible saber cuál. |

Las líneas 29 y 49–52 solo nombran los distractores (medidas que no responden la pregunta del caso).

## 3. Pantalla

- **V1:** Interpreta un ECG de 12 derivaciones paso a paso. No basta con acertar: también cuenta reconocer lo que el trazado no permite decidir, pedir la prueba que distingue las hipótesis y justificarla.
- **V2:** Simulación: trazado construido por el simulador de 12 derivaciones; las pruebas muestran lo que mide el analizador de BIOCORE sobre él.
- **V3:** «Caso pendiente de firma: …» (solo si este documento dejara de decir FIRMADO) y los rótulos «Correcto», «La respuesta que mejor se sostiene es…», «Revisor crítico», «Tu razonamiento en este caso» y «Tu recorrido».

## 4. Decisiones (la correcta va primero)

**D1 · grupo.** (D1.p) Mira el trazado. ¿En qué grupo de derivaciones está más elevado el ST?
- (D1.o) ✅ II, III y aVF
- (D1.o) V1–V4
- (D1.o) I, aVL, V5 y V6
- (D1.o) En ninguno: el ST está en la línea de base

*(D1.e)* El analizador mide la mayor elevación del ST en II, III y aVF. *Sale de la medición del caso.*

**D2 · hipotesis_inicial.** (D2.p, t1:72) Con solo ese dato, ¿qué arteria es la responsable?
- (D2.o1) ✅ La coronaria derecha o la circunfleja: con este dato no se puede decir cuál
- (D2.o2) La coronaria derecha, con seguridad
- (D2.o3) La circunfleja, con seguridad
- (D2.o4) La descendente anterior

*(D2.e)* Una elevación del ST en II, III y aVF puede deberse a la coronaria derecha o a la circunfleja, según cuál dé la descendente posterior [W2009]. Hace falta otro dato para orientarse. *Línea firmada:* t1:81.

**D3 · hipotesis_final.** (D3.p) Con las pruebas que pediste, ¿qué sugiere el trazado?
- (D3.o1) ✅ Sugiere coronaria derecha: la elevación es mayor en III que en II
- (D3.o2) Sugiere circunfleja
- (D3.o3) Sugiere descendente anterior
- (D3.o4) Sigue sin poder distinguirse entre coronaria derecha y circunfleja

*(D3.e)* Una elevación mayor en III que en II sugiere coronaria derecha [W2009]. «Sugiere» no es «demuestra». *Línea firmada:* t1:81.

**D4 · limite.** (D4.p) Antes de cerrar: ¿puedes afirmar que el ventrículo derecho está afectado?
- (D4.o1, corregida) ✅ No: la elevación del ST en V3R y V4R sugiere afectación del ventrículo derecho, y este registro no tiene esas derivaciones
- (D4.o2) Sí, porque hay elevación en II, III y aVF
- (D4.o3) Sí, porque III es mayor que II
- (D4.o4) No, porque la coronaria derecha no se relaciona con el ventrículo derecho

*(D4.e, corregida)* Una elevación del ST en V3R y V4R (derivaciones derechas) sugiere afectación del ventrículo derecho [W2009]. Este registro no tiene esas derivaciones. *Línea firmada:* t1:83.

## 5. Pruebas que el estudiante puede pedir (el motivo correcto va primero)

Para pedir una prueba, el estudiante elige por qué la pide. El resultado es el del caso medido.

**P1 · (P1.n) Medir el ST en II, III y aVF** (línea firmada t1:81)
- (P1.m1) ✅ Comparar II con III: una elevación mayor en III que en II sugiere coronaria derecha
- (P1.m2, t1:29) Calcular la frecuencia cardiaca
- (P1.m3, corregido, t1:51) Medir el intervalo QT

*(P1.r)* II +2.1 mm · III +2.9 mm · aVF +2.5 mm. III es mayor que II.

**P2 · (P2.n) Revisar el ST en I y aVL** (línea firmada t1:82)
- (P2.m1, corregido) ✅ Ver si hay elevación en I y aVL, que junto con cambios en II, III y aVF puede acompañar la oclusión de la circunfleja
- (P2.m2, t1:49) Medir el intervalo PR
- (P2.m3, t1:52) Calcular el eje del QRS

*(P2.r)* I -0.7 mm · aVL -1.8 mm: descenso, no elevación.

**P3 · (P3.n) Revisar el ST en V1–V3** (línea firmada t1:84)
- (P3.m1) ✅ Buscar descenso del ST en V1–V3, el patrón llamado «posterior»
- (P3.m2, t1:50) Medir la duración del QRS
- (P3.m3, corregido, t1:49) Medir el intervalo PR

*(P3.r)* V1 +0.0 mm · V2 +0.0 mm · V3 +0.0 mm: no hay descenso.

**P4 · (P4.n) Revisar el ST en V1–V4** (línea firmada t1:78)
- (P4.m1, corregido) ✅ Descartar la elevación del ST en V1–V4, I, aVL y a menudo aVR, que sugiere oclusión proximal de la descendente anterior
- (P4.m2, t1:29) Calcular la frecuencia cardiaca
- (P4.m3, t1:51) Medir el intervalo QT

*(P4.r, con I, aVL y aVR medidos, como pide la nota de la hoja)* V1 +0.0 mm · V2 +0.0 mm · V3 +0.0 mm · V4 +0.0 mm · I -0.7 mm · aVL -1.8 mm · aVR -0.7 mm: no hay elevación.

**P5 · (P5.n) Pedir V3R y V4R (derivaciones derechas)** (línea firmada t1:83)
- (P5.m1) ✅ Buscar afectación del ventrículo derecho, que orienta a oclusión proximal de la coronaria derecha
- (P5.m2) Mejorar la calidad del trazado
- (P5.m3, t1:52) Calcular el eje del QRS

*(P5.nd, corregido)* No disponible: este registro no tiene derivaciones derechas; el simulador solo genera las 12 estándar. Con este registro no se puede buscar la elevación del ST en V3R y V4R.

## 6. Desafío a la hipótesis final (revisor crítico, por reglas, sin modelo de lenguaje)

Antes de cerrar, el caso cuestiona la respuesta con evidencia del propio caso. El estudiante puede mantenerla, cambiarla o pedir más pruebas. Texto según la respuesta y las pruebas pedidas (con las cifras de este trazado):

- **DS1 · Coronaria derecha, sin haber comparado II con III** (t1:81): ¿Qué dato te permite distinguir la coronaria derecha de la circunfleja? Con elevación en II, III y aVF las dos son posibles [W2009], y todavía no comparaste II con III.
- **DS2 · Coronaria derecha, después de comparar II con III** (t1:81): Tu conclusión se apoya en lo que mediste: III (+2.9 mm) mayor que II (+2.1 mm) sugiere coronaria derecha [W2009]. Sugerir no es demostrar: ¿qué no puedes afirmar todavía con este registro?
- **DS3 · Circunfleja, habiendo revisado I y aVL** (t1:82, corregido): Pediste I y aVL y tienen descenso (I -0.7 mm · aVL -1.8 mm), no elevación. La elevación en I y aVL junto con cambios en II, III y aVF es la que puede acompañar la oclusión de la circunfleja [W2009]. ¿Qué dato apoya tu respuesta?
- **DS4 · Circunfleja, sin revisar I y aVL** (t1:82, corregido): ¿Qué dato apoya la circunfleja? La elevación en I y aVL junto con cambios en II, III y aVF puede acompañar la oclusión de la circunfleja [W2009], y todavía no revisaste I y aVL.
- **DS5 · Descendente anterior** (t1:78, corregido): La elevación del ST en V1–V4, I, aVL y a menudo aVR sugiere oclusión proximal de la descendente anterior [W2009], y en este trazado miden V1 +0.0 mm · V2 +0.0 mm · V3 +0.0 mm · V4 +0.0 mm · I -0.7 mm · aVL -1.8 mm · aVR -0.7 mm. ¿Qué dato apoya tu respuesta?
- **DS6 · «No se puede distinguir», después de comparar II con III** (t1:81): Mediste III (+2.9 mm) mayor que II (+2.1 mm), y una elevación mayor en III que en II sugiere coronaria derecha [W2009]. ¿Mantienes que no se puede distinguir?
- **DS7 · «No se puede distinguir», sin comparar II con III** (t1:81): Hay un dato que puede orientar: comparar II con III [W2009]. ¿Quieres pedirlo antes de responder?

## 7. Qué se evalúa (además del acierto)

| ID | Competencia | Evidencia que ve el estudiante |
|---|---|---|
| C1 | Reconoce lo que el primer dato no permite decidir | Con elevación en II, III y aVF, la coronaria derecha y la circunfleja son posibles [W2009]. |
| C2 (corregida) | Pide la prueba que distingue las hipótesis | Una elevación mayor en III que en II sugiere coronaria derecha [W2009]. |
| C3 | Justifica cada prueba que pide | Cada prueba pedida, con el motivo que la sostiene. |
| C4 (corregida) | Evita concluir antes de tener el dato | Sugerir coronaria derecha se sostiene después de comparar II con III [W2009]. |
| C5 | Actualiza la hipótesis con la nueva evidencia | De «coronaria derecha o circunfleja» a «sugiere coronaria derecha» al ver III mayor que II. |
| C6 (corregida) | Reconoce la información que falta | La elevación del ST en V3R y V4R sugiere afectación del ventrículo derecho [W2009], y este registro no tiene esas derivaciones. |

C3, cuando ya hay pruebas pedidas, dice «N de M pruebas pedidas con el motivo que las sostiene». C4 cuenta como prematura la PRIMERA conclusión «sugiere coronaria derecha» si se dio sin haber comparado II con III (alineada con su texto corregido).

Cada decisión lleva su **confianza** (opcional; 25, 50, 75 o 100 %) y se registra en la sesión una sola vez por intento con `log_session_answer(..., source="caso_guiado", concept="derivaciones_e_isquemia")`; entra al panel «Tu calibración en esta sesión» (`educational/confidence_calibration.py`, intervalo de Wilson al 95 % [WILSON1927]).

## 8. Firma

> Firmo el caso guiado de ECG (`docs/contenido/caso_guiado_ecg.md`): TAL CUAL D1.p, D1.o, D1.e, D2.p, D2.o1–o4, D2.e, D3.p, D3.o1–o4, D3.e, D4.p, D4.o2–o4, P1.n, P1.m1, P1.m2, P1.r, P2.n, P2.m2–m3, P2.r, P3.n, P3.m1, P3.m2, P3.r, P4.n, P4.m2–m3, P4.r, P5.n, P5.m1–m3, DS1, DS2, DS6, DS7, C1, C3, C5, V1, V2, V3; CON LA CORRECCIÓN de la hoja de revisión D4.o1, D4.e, P1.m3, P2.m1, P3.m3, P4.m1, P5.nd, DS3, DS4, DS5, C2, C4, C6; D3 = se mantiene el distractor (D4.o4). Montar como página nueva en Practicar, `caso-guiado` («Caso guiado de ECG»), después de `desafio-ecg`. — Luis Nazariego Santome, 17/11/2026

- **Cómo se dio la firma:** Luis la aprobó en la sesión de trabajo del 17 de noviembre de 2026 con «firmo todo», sobre la hoja de revisión del caso. El texto de la firma se redactó a partir de esa hoja.
- **Ningún texto quedó en QUITAR.** Los dos «Buscar una onda delta» (sin línea firmada) se sustituyeron por distractores del tema 3 (t1:49 y t1:51).
- **Decisiones de la versión borrador, resueltas por la firma:** D1 = firmado con las correcciones; D2 = se monta en Practicar (`caso-guiado`); D3 = se mantiene el distractor «La coronaria derecha no se relaciona con el ventrículo derecho» (falso según t1:83).
