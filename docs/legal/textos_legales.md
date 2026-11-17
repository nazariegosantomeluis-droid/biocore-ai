# Textos legales de BIOCORE AI

**Estado:** FIRMADO 2026-11-17 por Luis Nazariego Santome («Firmo todo»): TC1–TC5, AP0–AP5, CW1–CW3 y PS1–PS4, con los AJUSTES del Art. I tal como están en la sección 3. D1 (consentimiento) está elaborado y pendiente de firma, y faltan los datos de la sección 1. Los textos originales quedan en la sección 4 para cuando las funciones que describen existan. Ninguno de estos textos es asesoría legal: conviene que los revise un abogado antes de usarlos en contratos.
**Uso:** `app/utils/legal.py` es la única fuente de los textos en la app. `tests/test_legal.py` exige que cada texto de ese módulo esté literal en este documento, que ningún dato faltante se invente y que el aviso de entrada bloquee la página hasta marcar la casilla.

---

## 1. Datos que faltan

Nadie los ha dado y no se inventan: en la app se muestran como «[pendiente: …]» hasta que se llenen en `LEGAL_DATA` (`app/utils/legal.py`). La prueba avisa mientras falte alguno.

| Clave | En el texto entregado | Se muestra hoy como |
|---|---|---|
| `entidad_legal` | [Nombre de tu Empresa / Entidad Legal] | [pendiente: nombre de la entidad legal] |
| `domicilio` | [Dirección fiscal de tu empresa] | [pendiente: domicilio fiscal] |
| `correo_privacidad` | [Correo de Privacidad de tu Empresa] | [pendiente: correo de privacidad] |
| `universidad` | [Nombre de la Universidad] | [pendiente: nombre de la universidad] |
| `dominio` | (ej. @dominio.edu.mx) | [pendiente: dominio de correo institucional] |
| `consumo_ma` | [X] mA (solo empaque) | [pendiente: consumo máximo del kit en mA] |
| `contacto_soporte` | [Sitio web o correo de soporte] (solo empaque) | [pendiente: sitio web o correo de soporte] |

## 2. Lo que muestra la app

Dónde: «Términos y condiciones» y «Aviso de privacidad» son páginas de Ajustes, enlazadas al pie de cada página con el aviso de uso educativo. El aviso clínico de entrada aparece al iniciar la sesión y cada vez que se entra a una página que carga un caso clínico (Caso ciego, Casos clínicos del simulador, Detective fisiológico y Caso guiado de ECG); la página no se dibuja hasta marcar la casilla. Streamlit no informa si el texto se leyó hasta el final: el botón se activa con la casilla, no con el desplazamiento, y la app no afirma otra cosa.

### Términos y condiciones (página `terminos`, enlazada al pie de cada página)

Aviso del pie de página:

> BIOCORE AI NO ES UN DISPOSITIVO MÉDICO: uso exclusivamente educativo.

Aviso de datos pendientes (arriba de las dos páginas):

> Faltan datos de la entidad legal por completar: se muestran como «[pendiente: …]» hasta que se den.

**TC1 · 1. Naturaleza y propósito del servicio (uso exclusivamente educativo)** · tal como se entregó

> BIOCORE AI es una plataforma digital y ecosistema de hardware diseñado estrictamente como un laboratorio virtual de simulación fisiológica para la enseñanza en ciencias de la salud. BIOCORE AI NO ES UN DISPOSITIVO MÉDICO, no cuenta con Registro Sanitario ante COFEPRIS y no está diseñado, destinado ni autorizado para el diagnóstico, tratamiento, mitigación, cura o prevención de ninguna enfermedad o condición médica en seres humanos.

**TC2 · 2. Exclusión de responsabilidad médica** · **AJUSTE (firmado 2026-11-17)**

> Las señales obtenidas a través de los sensores (ECG, EMG, pulso, temperatura), así como los cálculos, métricas (incluida la saturación de oxígeno, que hoy solo proviene del modelo simulado: la plataforma no la calcula a partir del sensor de pulso) y escenarios clínicos generados por el motor hemodinámico o el gemelo digital, son para fines exclusivamente pedagógicos y de práctica deliberada. Ningún dato arrojado por BIOCORE AI sustituye el juicio clínico de un profesional de la salud. El usuario libera a {entidad_legal} y a la institución educativa de cualquier responsabilidad derivada de la interpretación personal de estos datos fuera del entorno académico.

**TC3 · 3. Principio de transparencia de datos (Artículo I)** · **AJUSTE (firmado 2026-11-17)**

> BIOCORE AI opera bajo el principio de estricta procedencia de datos. La plataforma declara visualmente el origen de cada valor que muestra, distinguiendo si fue: a) Medido físicamente por los sensores. b) Simulado a través del motor hemodinámico o del gemelo digital. c) Tomado de una referencia bibliográfica o guía clínica. d) Calculado a partir de otros valores, con su criterio rotulado (con fuente, criterio propio de BIOCORE o heurística). El usuario acepta que la plataforma no inferirá ni inventará diagnósticos, mostrando «sin dato» o «no disponible» cuando carezca de la información.

**TC4 · 4. Propiedad intelectual y restricciones de uso** · **AJUSTE (firmado 2026-11-17)**

> Todo el software, código fuente, algoritmos del motor hemodinámico, interfaces y diseño del hardware son propiedad exclusiva de {entidad_legal}, salvo los componentes de terceros (bibliotecas, ecuaciones y métodos publicados, bases de datos y módulos comerciales como el AD8232 o el MyoWare), que conservan su autoría y su licencia y se listan en THIRD_PARTY_NOTICES.md. Al acceder a BIOCORE AI mediante una licencia institucional, el usuario y la universidad aceptan que está estrictamente prohibido: a) Realizar ingeniería inversa, desensamblar o descompilar las placas, sensores (AD8232, MyoWare, etc.) o el software. b) Utilizar la plataforma o el hardware para fines comerciales, ensayos clínicos formales o fuera del dominio institucional autorizado.

**TC5 · 5. Cuentas institucionales** · **AJUSTE (firmado 2026-11-17)**

> Hoy BIOCORE AI no tiene cuentas de usuario ni inicio de sesión. Cuando existan, el acceso se otorgará exclusivamente a estudiantes y profesores activos bajo el dominio autorizado de {universidad} ({dominio}), y la institución será responsable de revocar el acceso a usuarios que dejen de formar parte de su comunidad académica.

### Aviso de privacidad (página `privacidad`, en Ajustes y al pie de cada página)

**AP0 · Preámbulo** · tal como se entregó

> De conformidad con lo establecido en la Ley Federal de Protección de Datos Personales en Posesión de los Particulares (LFPDPPP), {entidad_legal}, con domicilio en {domicilio}, pone a su disposición el presente Aviso de Privacidad.

**AP1 · 1. Datos personales recabados** · **AJUSTE (firmado 2026-11-17)**

> Hoy BIOCORE AI no tiene cuentas: no recaba nombre, correo institucional, matrícula ni rol. El único dato que puede identificarle es el «ID del estudiante» que usted escribe en la Academia (texto libre), que se guarda con sus respuestas en una base local de la computadora donde corre la plataforma. Datos personales sensibles (biométricos y fisiológicos): las señales de electrocardiograma (ECG), electromiograma (EMG), fotopletismografía (PPG), pulso y temperatura corporal obtenidas con el hardware del sistema, y el EEG si se conecta un equipo externo. Las señales se procesan durante la sesión; si usted pulsa «Guardar al gemelo», se guardan los valores calculados (no la señal completa) en una base local, con su procedencia.

**AP2 · 2. Finalidad del tratamiento de datos** · **AJUSTE (firmado 2026-11-17)**

> Los datos personales sensibles recabados se utilizarán única y exclusivamente para: permitir al usuario visualizar su propio estado fisiológico dentro del gemelo digital con fines de aprendizaje práctico, y procesar escenarios de simulación clínica dentro de la plataforma. Hoy no existe una Capa Docente ni calificación con datos fisiológicos. Cuando exista, los datos fisiológicos del grupo se presentarán al profesor de forma disociada y anonimizada, a menos que el estudiante otorgue su consentimiento explícito para vincular su nombre a sus registros clínicos para fines de calificación.

**AP3 · 3. Transferencia de datos** · **AJUSTE (firmado 2026-11-17)**

> Sus datos personales y sensibles no serán transferidos a terceros comerciales, aseguradoras, instituciones médicas ni entidades externas ajenas a {universidad}. Hoy se guardan solo en la computadora donde corre BIOCORE AI: no hay servidores de BIOCORE AI. Excepción: si usted pega una clave de IA en Ajustes y usa la narración con IA o «Pregunta a BIOCORE», el texto de su pregunta y los datos del contexto se envían al proveedor que eligió (Anthropic o Google). Con el nivel gratuito de Gemini nunca se envían datos de personas: solo datos simulados o de bases públicas.

**AP4 · 4. Derechos ARCO** · tal como se entregó

> Usted tiene derecho a Acceder, Rectificar, Cancelar u Oponerse (Derechos ARCO) al tratamiento de sus datos. Para ejercer estos derechos o revocar su consentimiento, deberá enviar un correo a {correo_privacidad}, donde se le indicará el procedimiento.

**AP5 · 5. Consentimiento expreso para datos sensibles** · **AJUSTE (firmado 2026-11-17)**

> Hoy no hay registro de cuentas. Cuando exista, al marcar la casilla «He leído y acepto el Aviso de Privacidad» al crear su cuenta, usted otorgará su consentimiento expreso y por escrito (mediante firma electrónica o validación de clic) para el tratamiento de sus datos personales sensibles bajo los términos aquí expuestos. Mientras tanto, este aviso está en Ajustes y al pie de cada página.

### Aviso clínico y educativo de entrada (casilla obligatoria)

**CW1 · Texto** · **AJUSTE (firmado 2026-11-17)**: «simulaciones matemáticas validadas» → rotuladas, con la PA de la sepsis en revisión clínica.

> Estás ingresando al gemelo digital de BIOCORE AI. Te recordamos que la información, métricas y retroalimentación clínica generada en esta sesión no constituyen un diagnóstico médico. Las variaciones en las señales (como caídas de presión en escenarios de sepsis o alteraciones de ritmo) son simulaciones matemáticas —rotuladas como tales; algunas, como la presión arterial en la sepsis, están en revisión clínica— o registros adquiridos con fines de práctica en un entorno seguro. Si estás midiendo tus propias señales en tiempo real y notas alguna anomalía que te preocupe, acude a un profesional de la salud cualificado.

**CW2 · Casilla** · tal como se entregó

> Comprendo que BIOCORE AI es una herramienta de simulación educativa y no un instrumento médico.

**CW3 · Botón** · tal como se entregó

> Ingresar al laboratorio

**CW4 · Ayuda bajo la casilla** (nueva, no es texto legal)

> Marca la casilla para ingresar.

### Precauciones del manual, en los tutoriales de hardware (sección «Seguridad»)

Título:

> Precauciones y seguridad eléctrica (manual de usuario de BIOCORE AI)

**PS1** · tal como se entregó

> **Seguridad eléctrica (ECG y EMG):** cuando utilice los sensores con electrodos conectados al cuerpo humano, la computadora portátil a la que está conectado BIOCORE AI DEBE OPERAR ÚNICAMENTE CON BATERÍA. Desconecte el cargador de la toma de corriente de la pared durante las mediciones para evitar riesgos de choque eléctrico por corrientes de fuga e interferencia electromagnética (ruido de 60 Hz).

**PS2** · tal como se entregó

> **Higiene y aplicación:** utilice los electrodos desechables (ECG) y de broche (EMG) únicamente sobre piel intacta, limpia y seca. No coloque electrodos sobre heridas, irritaciones o mucosas. La sonda de temperatura es exclusivamente de uso axilar externo; NUNCA DEBE INTRODUCIRSE EN LA BOCA ni en ninguna otra cavidad corporal.

**PS3** · tal como se entregó

> **Límites operativos:** los sensores PPG (pulso) requieren que el usuario coloque la yema del dedo suavemente, sin presionar en exceso, para evitar bloquear el flujo sanguíneo y alterar la lectura.

**PS4** · tal como se entregó

> **Limitación de EEG:** el módulo BIOCORE AI no adquiere señales cerebrales directamente. Para prácticas neurológicas, el sistema debe conectarse a un equipo externo compatible (ej. OpenBCI Cyton) siguiendo los manuales de dicho fabricante.

Dónde se muestra cada una: ECG (placa en vivo) PS1 y PS2; EMG PS1 y PS2; pulso (PPG) PS3; temperatura PS2; EEG en vivo PS4.

### D1 · Consentimiento antes de medir las propias señales (elaborado el 2026-11-17, pendiente de firma)

Dónde: en la barra lateral de cada fuente en vivo, una vez por sesión, antes de usar un equipo REAL: la placa ECG (ESP32 + AD8232), la placa de biosensores en modo «Placa real» (EMG, pulso y temperatura) y el EEG con un equipo real o un flujo LSL. Las prácticas con placa simulada y los dos simuladores del EEG no lo piden. Sin aceptar, la fuente no se conecta (`legal.own_signals_consent`).

**D1.1 · Título**

> Antes de medir tus propias señales

**D1.2 · Texto** (sale de AP1 y AP3; dice «computadora o servidor» porque en la nube la base está en el servidor)

> Las señales de un sensor conectado a tu cuerpo (ECG, EMG, pulso, temperatura o EEG) son datos personales sensibles. Se procesan durante la sesión; si pulsas «Guardar al gemelo», se guardan los valores calculados (no la señal completa) en la base de la computadora o del servidor donde corre BIOCORE AI. Si usas la IA con tu clave, el contexto puede ir al proveedor que elegiste. Los detalles están en el Aviso de privacidad.

**D1.3 · Casilla**

> Acepto que BIOCORE AI trate mis señales fisiológicas como lo describe el Aviso de privacidad.

**D1.4 · Si no se acepta**

> Sin aceptar, la fuente en vivo no se conecta. La práctica con placa simulada no lo necesita.

## 3. Ajustes del Art. I (firmados el 2026-11-17)

| ID | Decía (original) | Dice ahora (propuesta) | Por qué |
|---|---|---|---|
| TC2 | «métricas (incluyendo estimaciones de oxigenación)» | «métricas (incluida la saturación de oxígeno, que hoy solo proviene del modelo simulado: la plataforma no la calcula a partir del sensor de pulso)» | La SpO₂ del pulso por luz no se calcula: falta la curva de calibración (CLAUDE.md, `src/signals/ppg/analysis.py`). |
| TC3 | «declara visualmente y en todo momento el origen … a) medido, b) simulado, c) referencia … cuando carezca de información validada» | «declara visualmente el origen de cada valor que muestra … b) simulado a través del motor hemodinámico o del gemelo digital … d) calculado a partir de otros valores, con su criterio rotulado … cuando carezca de la información» | Hay una cuarta procedencia (derivados, Criterio BIOCORE, heurísticas, todos rotulados) y la app sí muestra valores no validados cuando los rotula como tales. |
| TC4 | «Todo el software, código fuente, algoritmos del motor hemodinámico … son propiedad exclusiva de [Empresa]» | Se agrega: «salvo los componentes de terceros … que conservan su autoría y su licencia y se listan en THIRD_PARTY_NOTICES.md» | El motor hemodinámico reimplementa ecuaciones publicadas de svZeroDSolver y el repositorio usa bibliotecas, datos (PTB, PTB-XL, MIT-BIH) y módulos (AD8232, MyoWare) de terceros con su propia licencia. |
| TC5 | «El acceso se otorga exclusivamente a estudiantes y profesores activos bajo el dominio autorizado…» | «Hoy BIOCORE AI no tiene cuentas de usuario ni inicio de sesión. Cuando existan, el acceso se otorgará…» | No hay cuentas ni identidad (CLAUDE.md: «Mi progreso» y «Docente» no existen hasta que haya identidad). |
| AP1 | Nombre completo, correo institucional, matrícula y rol; señales ECG, EMG, PPG, pulso y temperatura | No recaba nombre, correo, matrícula ni rol; el único dato que identifica es el «ID del estudiante» (texto libre, base local); se agrega el EEG de un equipo externo; se guardan valores calculados, no la señal completa | `app/utils/learning_log.py` (`academia_student_id`, base `data/local/biocore_learning.db`); el UPS guarda escalares con su procedencia en `data/biocore_ups.db`. |
| AP2 | «Permitir la evaluación académica en la "Capa Docente"…» | «Hoy no existe una Capa Docente ni calificación con datos fisiológicos. Cuando exista, …» | La Capa Docente no existe. |
| AP3 | «no serán transferidos a terceros … ni entidades externas ajenas a [Universidad] y a la infraestructura de servidores cifrados de BIOCORE AI» | «Hoy se guardan solo en la computadora donde corre BIOCORE AI: no hay servidores de BIOCORE AI. Excepción: si usted pega una clave de IA … se envían al proveedor que eligió (Anthropic o Google). Con el nivel gratuito de Gemini nunca se envían datos de personas» | No hay servidores de BIOCORE AI. Con la clave de Anthropic, la narración sí puede enviar datos de un sensor real (`domain/physiology/narrator/privacy.py`); decir que nada se transfiere sería falso. |
| AP5 | «Al marcar la casilla "He leído y acepto el Aviso de Privacidad" al momento de crear mi cuenta…» | «Hoy no hay registro de cuentas. Cuando exista, … Mientras tanto, este aviso está en Ajustes y al pie de cada página.» | No hay pantalla de registro. **Decisión pendiente:** si se quiere pedir el consentimiento antes de medir las propias señales con un sensor, hay que diseñarlo (hoy no existe). |
| CW1 | «son simulaciones matemáticas validadas o registros adquiridos» | «son simulaciones matemáticas —rotuladas como tales; algunas, como la presión arterial en la sepsis, están en revisión clínica— o registros adquiridos» | La PA de la sepsis depende de la capacitancia venosa 2× (Criterio BIOCORE, sin cita) y está en revisión clínica (gemelo y Detective). |

Además, la app agrega dos textos que no son legales: el aviso de datos pendientes arriba de Términos y Aviso de privacidad, y la ayuda «Marca la casilla para ingresar.» bajo la casilla.

## 4. Textos tal como se entregaron (17 de noviembre de 2026)

### 4.1 Términos y Condiciones de Uso (Plataforma y SaaS)

*Dónde: footer de la plataforma, anexos de contratos B2B con universidades y enlace al crear una cuenta.*

TÉRMINOS Y CONDICIONES DE USO DE BIOCORE AI

1. Naturaleza y Propósito del Servicio (Uso Exclusivamente Educativo). BIOCORE AI es una plataforma digital y ecosistema de hardware diseñado estrictamente como un laboratorio virtual de simulación fisiológica para la enseñanza en ciencias de la salud. BIOCORE AI NO ES UN DISPOSITIVO MÉDICO, no cuenta con Registro Sanitario ante COFEPRIS y no está diseñado, destinado ni autorizado para el diagnóstico, tratamiento, mitigación, cura o prevención de ninguna enfermedad o condición médica en seres humanos.

2. Exclusión de Responsabilidad Médica (Disclaimer Clínico). Las señales obtenidas a través de los sensores (ECG, EMG, pulso, temperatura), así como los cálculos, métricas (incluyendo estimaciones de oxigenación) y escenarios clínicos generados por el motor hemodinámico o el gemelo digital, son para fines exclusivamente pedagógicos y de práctica deliberada. Ningún dato arrojado por BIOCORE AI sustituye el juicio clínico de un profesional de la salud. El usuario libera a [Nombre de tu Empresa / Entidad Legal] y a la institución educativa de cualquier responsabilidad derivada de la interpretación personal de estos datos fuera del entorno académico.

3. Principio de Transparencia de Datos (Artículo I). BIOCORE AI opera bajo el principio de estricta procedencia de datos. La plataforma declara visualmente y en todo momento el origen de la información mostrada, distinguiendo explícitamente si un valor fue: a) Medido físicamente por los sensores. b) Simulado a través del motor hemodinámico. c) Tomado de una referencia bibliográfica o guía clínica. El usuario acepta que la plataforma no inferirá ni inventará diagnósticos, mostrando "sin dato" o "no disponible" cuando carezca de información validada.

4. Propiedad Intelectual y Restricciones de Uso. Todo el software, código fuente, algoritmos del motor hemodinámico, interfaces y diseño del hardware son propiedad exclusiva de [Nombre de tu Empresa]. Al acceder a BIOCORE AI mediante una licencia institucional, el usuario y la universidad aceptan que está estrictamente prohibido: a) Realizar ingeniería inversa, desensamblar o descompilar las placas, sensores (AD8232, MyoWare, etc.) o el software. b) Utilizar la plataforma o el hardware para fines comerciales, ensayos clínicos formales o fuera del dominio institucional autorizado.

5. Cuentas Institucionales. El acceso a la plataforma se otorga exclusivamente a estudiantes y profesores activos bajo el dominio autorizado de [Nombre de la Universidad] (ej. @dominio.edu.mx). La institución es responsable de revocar el acceso a usuarios que dejen de formar parte de su comunidad académica.

### 4.2 Aviso de Privacidad Integral (Manejo de Datos Sensibles)

*Dónde: pantalla de registro de usuarios, base de datos institucional y menú de configuración.*

AVISO DE PRIVACIDAD INTEGRAL DE BIOCORE AI. De conformidad con lo establecido en la Ley Federal de Protección de Datos Personales en Posesión de los Particulares (LFPDPPP), [Nombre de tu Empresa / Entidad Legal], con domicilio en [Dirección fiscal de tu empresa], pone a su disposición el presente Aviso de Privacidad.

1. Datos Personales Recabados. Para la operación del laboratorio digital, BIOCORE AI recabará los siguientes datos: • Datos de identificación: Nombre completo, correo electrónico institucional, matrícula y rol (estudiante/docente). • Datos Personales Sensibles (Biométricos y Fisiológicos): Señales de electrocardiograma (ECG), electromiograma (EMG), fotopletismografía (PPG), pulso y temperatura corporal obtenidos mediante el hardware del sistema.

2. Finalidad del Tratamiento de Datos. Los datos personales sensibles recabados se utilizarán única y exclusivamente para: • Permitir al usuario visualizar su propio estado fisiológico dentro del gemelo digital con fines de aprendizaje práctico. • Procesar escenarios de simulación clínica dentro de la plataforma. • Permitir la evaluación académica en la "Capa Docente". En este rubro, los datos fisiológicos del grupo se presentarán al profesor de forma disociada y anonimizada, a menos que el estudiante otorgue su consentimiento explícito para vincular su nombre a sus registros clínicos para fines de calificación.

3. Transferencia de Datos. Sus datos personales y sensibles no serán transferidos a terceros comerciales, aseguradoras, instituciones médicas ni entidades externas ajenas a [Nombre de la Universidad] y a la infraestructura de servidores cifrados de BIOCORE AI.

4. Derechos ARCO. Usted tiene derecho a Acceder, Rectificar, Cancelar u Oponerse (Derechos ARCO) al tratamiento de sus datos. Para ejercer estos derechos o revocar su consentimiento, deberá enviar un correo a [Correo de Privacidad de tu Empresa], donde se le indicará el procedimiento.

Consentimiento Expreso para Datos Sensibles: Al marcar la casilla "He leído y acepto el Aviso de Privacidad" al momento de crear mi cuenta, otorgo mi consentimiento expreso y por escrito (mediante firma electrónica o validación de clic) para el tratamiento de mis datos personales sensibles bajo los términos aquí expuestos.

### 4.3 Textos reglamentarios para el empaque del hardware (no se muestran en la app)

*Dónde: impreso en el exterior de la caja del kit (NOM-050-SCFI-2004).*

BIOCORE AI – KIT DE LABORATORIO DIGITAL DE FISIOLOGÍA

EXCLUSIVO PARA USO ACADÉMICO. NO ES UN DISPOSITIVO MÉDICO.

Contenido: 1 Placa de adquisición (Basada en ESP32), Sensores de bioseñales (ECG 1 derivación, EMG de superficie, Pulso óptico PPG, Sonda de temperatura), Electrodos desechables y cables de conexión.

Advertencia de Uso: Este equipo no diagnostica, trata ni monitorea enfermedades reales. Su uso es estrictamente educativo. No utilizar en entornos hospitalarios ni para toma de decisiones clínicas.

Especificaciones Eléctricas: Alimentación 5V DC (vía USB). Consumo máximo: [X] mA.

Hecho en México por: [Nombre de tu Empresa / Entidad Legal]. Domicilio: [Dirección completa]. Contacto: [Sitio web o correo de soporte].

Consulte el manual de usuario antes de operar este equipo.

*Revisión contra el hardware del repositorio:* el contenido coincide con lo que soporta la app (ESP32; ECG de una derivación con AD8232; EMG de superficie con MyoWare 2.0; pulso por luz con MAX30102; temperatura con DS18B20). El consumo máximo no se ha medido en el repositorio: hay que medirlo con el kit armado antes de imprimir.

### 4.4 Manual de usuario: precauciones y seguridad eléctrica

*Dónde: primeras páginas del manual impreso o PDF. En la app, las cuatro precauciones (PS1–PS4) se muestran tal cual en la sección «Seguridad» de los tutoriales de hardware.*

PRECAUCIONES Y SEGURIDAD ELÉCTRICA (IMPORTANTE). Para garantizar la seguridad del usuario y la fidelidad de las señales, siga estrictamente estas instrucciones:

1. Seguridad Eléctrica (ECG y EMG): Cuando utilice los sensores con electrodos conectados al cuerpo humano, la computadora portátil a la que está conectado BIOCORE AI DEBE OPERAR ÚNICAMENTE CON BATERÍA. Desconecte el cargador de la toma de corriente de la pared durante las mediciones para evitar riesgos de choque eléctrico por corrientes de fuga e interferencia electromagnética (ruido de 60 Hz).
2. Higiene y Aplicación: Utilice los electrodos desechables (ECG) y de broche (EMG) únicamente sobre piel intacta, limpia y seca. No coloque electrodos sobre heridas, irritaciones o mucosas. La sonda de temperatura es exclusivamente de uso axilar externo; NUNCA DEBE INTRODUCIRSE EN LA BOCA ni en ninguna otra cavidad corporal.
3. Límites Operativos: Los sensores PPG (pulso) requieren que el usuario coloque la yema del dedo suavemente, sin presionar en exceso, para evitar bloquear el flujo sanguíneo y alterar la lectura.
4. Limitación de EEG: El módulo BIOCORE AI no adquiere señales cerebrales directamente. Para prácticas neurológicas, el sistema debe conectarse a un equipo externo compatible (ej. OpenBCI Cyton) siguiendo los manuales de dicho fabricante.

*Revisión contra los tutoriales:* no los contradice. El tutorial del ECG ya pedía la computadora con batería y sin cargador, y el de temperatura ya colocaba la sonda en la axila y prohibía la boca y otras cavidades. El EEG en vivo de la app también acepta Muse, Unicorn y cualquier programa por LSL, además de OpenBCI (la precaución dice «ej.», así que sigue siendo cierta).

### 4.5 Click-wrap de inicio de sesión

*Dónde: ventana al iniciar sesión o cargar un caso clínico; el botón «Aceptar» deshabilitado hasta hacer scroll.*

AVISO CLÍNICO Y EDUCATIVO. Estás ingresando al gemelo digital de BIOCORE AI. Te recordamos que la información, métricas y retroalimentación clínica generada en esta sesión no constituyen un diagnóstico médico. Las variaciones en las señales (como caídas de presión en escenarios de sepsis o alteraciones de ritmo) son simulaciones matemáticas validadas o registros adquiridos con fines de práctica en un entorno seguro. Si estás midiendo tus propias señales en tiempo real y notas alguna anomalía que te preocupe, acude a un profesional de la salud cualificado.

[ CASILLA OBLIGATORIA ]: Comprendo que BIOCORE AI es una herramienta de simulación educativa y no un instrumento médico.

[ BOTÓN: INGRESAR AL LABORATORIO ]

## 5. Hoja de firma

> Firmo todo. — Luis Nazariego Santome, 17/11/2026

| ID | Texto | Decisión de Luis |
|---|---|---|
| TC1 | Naturaleza y propósito (tal como se entregó) | ☑ firmado (17-11-2026) |
| TC2 | Exclusión de responsabilidad (AJUSTE: SpO₂ solo del modelo) | ☑ firmado (17-11-2026) |
| TC3 | Transparencia (AJUSTE: cuarta procedencia, «cada valor que muestra») | ☑ firmado (17-11-2026) |
| TC4 | Propiedad intelectual (AJUSTE: excepción de terceros) | ☑ firmado (17-11-2026) |
| TC5 | Cuentas institucionales (AJUSTE: hoy no hay cuentas) | ☑ firmado (17-11-2026) |
| AP0 | Preámbulo LFPDPPP (tal como se entregó) | ☑ firmado (17-11-2026) |
| AP1 | Datos recabados (AJUSTE: lo que se guarda hoy) | ☑ firmado (17-11-2026) |
| AP2 | Finalidad (AJUSTE: hoy no hay Capa Docente) | ☑ firmado (17-11-2026) |
| AP3 | Transferencia (AJUSTE: sin servidores; excepción de la IA) | ☑ firmado (17-11-2026) |
| AP4 | Derechos ARCO (tal como se entregó) | ☑ firmado (17-11-2026) |
| AP5 | Consentimiento (AJUSTE: hoy no hay registro) | ☑ firmado (17-11-2026) |
| CW1 | Aviso de entrada (AJUSTE: simulaciones rotuladas, PA de sepsis en revisión) | ☑ firmado (17-11-2026) |
| CW2–CW3 | Casilla y botón (tal como se entregó) | ☑ firmado (17-11-2026) |
| PS1–PS4 | Precauciones del manual (tal como se entregó) | ☑ firmado (17-11-2026) |
| D1 | Consentimiento antes de medir las propias señales (D1.1–D1.4, elaborado el 2026-11-17 a pedido de Luis: «Elabóralo») | ☐ firmo ☐ corregir |
