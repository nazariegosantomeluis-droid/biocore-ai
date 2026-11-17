# Banco de preguntas para BIOCORE: NEWS2 (FIRMADO)

**Estado:** FIRMADO 2026-11-17 por Luis Nazariego Santome («Firmo todo»): N1–N9 tal como están, y D-N7: sí. Están en la app, en `educational/quiz_bank.py` como `NEWS2_QUESTIONS` (lección «NEWS2» del Quiz de la Academia, concepto `news2`).
**Por qué:** la evaluación del 17-11-2026 encontró 0 preguntas de banco para el concepto `news2` (y 0 para `hemodinamica`). NEWS2 ya tiene su teoría firmada (temas 2 y 6 de `teoria_citada.md`); hemodinámica no tiene ninguna línea firmada y por eso no tiene borrador (ver al final).
**Regla:** cada pregunta se sostiene en una línea firmada de `docs/contenido/teoria_citada.md`, citada textual como «t1:N». La opción correcta va primero (convención de los bancos de la app; en pantalla se reparte su lugar). La explicación solo usa el texto de esa línea. `tests/test_banco_news2.py` comprueba que cada cita exista literal en su línea y que el código diga lo mismo que esta hoja.

---

**N1 · Para qué sirve NEWS2**
¿Para qué sirve NEWS2?
- ✅ Para estandarizar cómo se registran, puntúan y atienden las constantes vitales, y detectar el deterioro agudo
- Para diagnosticar la causa del deterioro de un paciente
- Para sustituir la valoración de un clínico
- Para medir la saturación de oxígeno sin pulsioxímetro

*Explicación:* NEWS2 es una puntuación agregada que estandariza cómo se registran, puntúan y atienden las constantes vitales para detectar el deterioro agudo [RCP2017].
*Línea firmada:* t1:91 — «**Idea.** NEWS2 es una puntuación agregada que estandariza cómo se registran, puntúan y atienden las constantes vitales para detectar el deterioro agudo [RCP2017].»

**Firma de Luis:** ☑ firmado (17-11-2026)

**N2 · Los parámetros**
¿Cuántos parámetros puntúa NEWS2?
- ✅ Seis: frecuencia respiratoria, SpO₂, presión arterial sistólica, pulso, nivel de consciencia o confusión nueva, y temperatura
- Cuatro: frecuencia respiratoria, SpO₂, pulso y temperatura
- Cinco: los mismos seis, sin la temperatura
- Tres: pulso, presión arterial y SpO₂

*Explicación:* puntúa seis parámetros: frecuencia respiratoria, SpO₂, presión arterial sistólica, pulso, nivel de consciencia o confusión nueva, y temperatura [RCP2017].
*Línea firmada:* t1:94 — «- Puntúa seis parámetros: frecuencia respiratoria, SpO₂, presión arterial sistólica, pulso, nivel de consciencia o confusión nueva, y temperatura. Se suman 2 puntos si el paciente recibe oxígeno suplementario.»

**Firma de Luis:** ☑ firmado (17-11-2026)

**N3 · Oxígeno suplementario**
Si el paciente recibe oxígeno suplementario, ¿qué pasa con su NEWS2?
- ✅ Se suman 2 puntos
- Se suma 1 punto
- Se suman 3 puntos
- No cambia: el oxígeno no se puntúa

*Explicación:* se suman 2 puntos si el paciente recibe oxígeno suplementario [RCP2017].
*Línea firmada:* t1:94 (la misma de N2).

**Firma de Luis:** ☑ firmado (17-11-2026)

**N4 · Pulso de 120 lpm**
En NEWS2, ¿cuántos puntos da un pulso de 120 lpm?
- ✅ 2 puntos (tramo de 111 a 130 lpm)
- 0 puntos
- 1 punto
- 3 puntos

*Explicación:* en la escala NEWS2, el pulso puntúa: ≤40 lpm, 3 puntos; 41–50, 1; 51–90, 0; 91–110, 1; 111–130, 2; ≥131, 3 [RCP2017].
*Línea firmada:* t1:35 — «**Detalle con fuente.** En la escala NEWS2, el pulso puntúa: ≤40 lpm, 3 puntos; 41–50, 1; 51–90, 0; 91–110, 1; 111–130, 2; ≥131, 3 [RCP2017]. (Ya implementado en `news2_pulse_score`.)»
*Comprobado con el código:* `clinical.calculators.news2_pulse_score(120)` da 2.

**Firma de Luis:** ☑ firmado (17-11-2026)

**N5 · Pulso de 45 lpm**
En NEWS2, ¿cuántos puntos da un pulso de 45 lpm?
- ✅ 1 punto (tramo de 41 a 50 lpm)
- 0 puntos
- 2 puntos
- 3 puntos

*Explicación:* la misma tabla de N4 [RCP2017].
*Línea firmada:* t1:35 (la misma de N4).
*Comprobado con el código:* `clinical.calculators.news2_pulse_score(45)` da 1.

**Firma de Luis:** ☑ firmado (17-11-2026)

**N6 · Un 3 en un solo parámetro**
¿Qué significa un 3 en un solo parámetro de NEWS2?
- ✅ Es poco frecuente y motiva una revisión urgente
- Nada mientras el total sea bajo
- Que el paciente recibe oxígeno suplementario
- Que hay que usar la escala 2 de SpO₂

*Explicación:* un 3 en un solo parámetro (marcado en rojo) es poco frecuente y motiva una revisión urgente [RCP2017].
*Línea firmada:* t1:96 — «- Un 3 en un solo parámetro (marcado en rojo) es poco frecuente y motiva una revisión urgente.»

**Firma de Luis:** ☑ firmado (17-11-2026)

**N7 · Total de 5 o 6**
Un total de NEWS2 de 5 o 6 (riesgo medio), ¿qué respuesta indica?
- ✅ Revisión urgente por un clínico competente en enfermedad aguda
- Vigilancia al menos cada 12 horas
- Valoración por enfermería
- Valoración de emergencia por un equipo con competencia en cuidados críticos

*Explicación:* total 0: vigilancia al menos cada 12 horas. Total 1–4 (bajo): valoración por enfermería. Total 5–6 (medio): revisión urgente por un clínico competente en enfermedad aguda. Total 7 o más (alto): valoración de emergencia por un equipo con competencia en cuidados críticos [RCP2017].
*Línea firmada:* t1:99 — «- Total 0: vigilancia al menos cada 12 horas. Total 1–4 (bajo): valoración por enfermería. Total 5–6 (medio): revisión urgente por un clínico competente en enfermedad aguda. Total 7 o más (alto): valoración de emergencia por un equipo con competencia en cuidados críticos.»
*Para decidir (D-N7):* es una respuesta de atención (quién valora y con qué urgencia), no un tratamiento, y está firmada en el tema 6. ¿Entra al banco? ☑ sí (17-11-2026)

**Firma de Luis:** ☑ firmado (17-11-2026)

**N8 · Escala 2 de SpO₂**
¿Cuándo se usa la escala 2 de SpO₂ de NEWS2?
- ✅ En insuficiencia respiratoria hipercápnica confirmada (por lo general EPOC), con objetivo de 88–92 %, bajo indicación de un clínico
- Siempre que la SpO₂ baje de 92 %
- En todo paciente que recibe oxígeno suplementario
- Nunca: NEWS2 tiene una sola escala de SpO₂

*Explicación:* la escala 2 de SpO₂ se usa en insuficiencia respiratoria hipercápnica confirmada (por lo general EPOC), con objetivo de 88–92 %, bajo indicación de un clínico. En los demás casos se usa la escala 1 [RCP2017].
*Línea firmada:* t1:100 — «- La escala 2 de SpO₂ se usa en insuficiencia respiratoria hipercápnica confirmada (por lo general EPOC), con objetivo de 88–92 %, bajo indicación de un clínico. En los demás casos se usa la escala 1.»

**Firma de Luis:** ☑ firmado (17-11-2026)

**N9 · Por qué BIOCORE no da el total**
¿Por qué BIOCORE muestra los puntos de cada parámetro de NEWS2 y no el total?
- ✅ Porque el gemelo no dispone de presión arterial en todos los casos y no modela temperatura ni consciencia: un total sería falso
- Porque el total de NEWS2 no tiene utilidad clínica
- Porque el total solo se calcula en pacientes con oxígeno suplementario
- Porque el total requiere un electrocardiograma de 12 derivaciones

*Explicación:* el gemelo no dispone de presión arterial en todos los casos, y no modela temperatura ni consciencia. Sin esos parámetros, un total sería falso; por eso la plataforma muestra los puntos de cada parámetro disponible y lista lo que falta.
*Línea firmada:* t1:101 — «- **Por qué BIOCORE no calcula el total:** el gemelo no dispone de presión arterial en todos los casos, y no modela temperatura ni consciencia. Sin esos parámetros, un total sería falso; por eso la plataforma muestra los puntos de cada parámetro disponible y lista lo que falta.»

**Firma de Luis:** ☑ firmado (17-11-2026)

---

## Lo que no se incluye y por qué

- **Puntos de la frecuencia respiratoria y de la SpO₂ escala 1:** las tablas están en el código con su cita (`clinical/calculators.py`, RCP 2017), pero no en un documento firmado; la regla de esta sesión es no escribir texto clínico sin una línea firmada. Si Luis firma esas tablas (por ejemplo, como líneas nuevas del tema 6), se pueden sumar preguntas como N4 y N5.
- **Hemodinámica:** ninguna línea firmada la trata (la presión arterial solo aparece como parámetro de NEWS2, t1:94 y t1:101). Hoy el concepto `hemodinamica` se practica en «¿Qué pasa si…?», que califica contra el motor y no necesita texto clínico. Para un banco hace falta primero un tema firmado (por ejemplo: presión arterial media, gasto cardiaco = volumen sistólico × frecuencia, y qué modela el lazo cerrado de BIOCORE), con su fuente.

## Hoja de firma

> Firmo todo. — Luis Nazariego Santome, 17/11/2026

| ID | Línea | Decisión de Luis |
|---|---|---|
| N1 | t1:91 | ☑ firmado (17-11-2026) |
| N2 | t1:94 | ☑ firmado (17-11-2026) |
| N3 | t1:94 | ☑ firmado (17-11-2026) |
| N4 | t1:35 | ☑ firmado (17-11-2026) |
| N5 | t1:35 | ☑ firmado (17-11-2026) |
| N6 | t1:96 | ☑ firmado (17-11-2026) |
| N7 | t1:99 | ☑ firmado (17-11-2026), D-N7: sí |
| N8 | t1:100 | ☑ firmado (17-11-2026) |
| N9 | t1:101 | ☑ firmado (17-11-2026) |

**Observación para una revisión futura (no cambia lo firmado):** en N1, N2, N8 y N9 la opción correcta es la más larga; los bancos de EMG y HRV cuidan que eso pase en 40 % de las preguntas o menos, para que la longitud no delate la respuesta.
