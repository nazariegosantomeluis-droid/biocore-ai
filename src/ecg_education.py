"""
Módulo de Educación ECG - Plataforma de Enseñanza Clínica

Proporciona capacidades educativas para estudiantes de medicina,
ingeniería biomédica e investigación cardiovascular.

Características:
- Modo de enseñanza interactivo
- Generación de casos clínicos educativos
- Explicaciones fisiológicas de hallazgos
- Preguntas de razonamiento clínico
"""

from typing import Dict, List, Tuple
import numpy as np
from dataclasses import dataclass


@dataclass
class ECGLesson:
    """Lección educativa sobre interpretación ECG."""
    titulo: str
    descripcion: str
    concepto_clave: str
    explicacion_fisiologica: str
    hallazgos_clinicos: List[str]
    preguntas_clinicas: List[str]


class ECGEducationPlatform:
    """
    Plataforma educativa para interpretación ECG clínica.
    
    Diseñada para:
    - Estudiantes de medicina
    - Ingeniería biomédica
    - Investigadores cardiovasculares
    - Residentes en cardiología
    """
    
    LECTURAS = {
        'ritmo_sinusal_normal': ECGLesson(
            titulo='Ritmo Sinusal Normal',
            descripcion='Patrón ECG normal en reposo',
            concepto_clave='Origen sinusal, conducción normal',
            explicacion_fisiologica=(
                'El ritmo sinusal normal se origina en el nodo sinoauricular (SA).\n'
                'La despolarización se propaga de manera ordenada:\n'
                '1. Nodo SA → despolarización auricular (onda P)\n'
                '2. Nodo AV → conducción retrasada (intervalo PR)\n'
                '3. Ventrículos → complejo QRS\n'
                '4. Repolarización → onda T\n'
                'Rango normal de frecuencia: 60-100 bpm'
            ),
            hallazgos_clinicos=[
                'Onda P positiva en II, III, aVF',
                'Intervalo PR: 120-200 ms',
                'Complejo QRS < 120 ms',
                'Intervalo QT < 440 ms (hombre), < 460 ms (mujer)',
                'FC 60-100 bpm'
            ],
            preguntas_clinicas=[
                '¿Cuál es la fuente normal del ritmo cardíaco?',
                '¿Por qué es importante la onda P?',
                '¿Qué significaría una onda P invertida en II?',
                '¿Cómo se calcula la frecuencia cardíaca en ritmo regular?'
            ]
        ),
        'taquicardia': ECGLesson(
            titulo='Taquicardia Sinusal',
            descripcion='Aumento anormal de la frecuencia cardíaca',
            concepto_clave='Respuesta fisiológica a demanda aumentada',
            explicacion_fisiologica=(
                'La taquicardia sinusal es una respuesta del cuerpo a:\n'
                '- Actividad física\n'
                '- Estrés\n'
                '- Fiebre\n'
                '- Ansiedad\n'
                '- Hipertiroidismo\n'
                '- Insuficiencia cardíaca\n'
                '- Shock\n'
                'El nodo SA aumenta su velocidad de disparo.'
            ),
            hallazgos_clinicos=[
                'FC > 100 bpm (en reposo)',
                'Morfología ECG similar a ritmo normal',
                'Aumenta con actividad, estrés o fiebre',
                'Disminuye en reposo'
            ],
            preguntas_clinicas=[
                '¿Cuáles son las causas fisiológicas de taquicardia?',
                '¿Cómo diferencias taquicardia sinusal de arritmia?',
                '¿Qué sistema nervioso está dominante en taquicardia?'
            ]
        ),
        'bradicardia': ECGLesson(
            titulo='Bradicardia Sinusal',
            descripcion='Disminución anormal de la frecuencia cardíaca',
            concepto_clave='Estimulación vagal aumentada',
            explicacion_fisiologica=(
                'La bradicardia sinusal indica estimulación vagal aumentada:\n'
                '- Atletas bien entrenados (respuesta fisiológica)\n'
                '- Presión intracraneal aumentada\n'
                '- Hipotermia\n'
                '- Hipotiroidismo\n'
                '- Disfunción del nodo SA\n'
                '- Medicamentos (betabloqueadores, digoxina)\n'
                'El nervio vago aumenta su influencia inhibitoria.'
            ),
            hallazgos_clinicos=[
                'FC < 60 bpm (en reposo)',
                'Morfología ECG normal',
                'Puede ser fisiológica en atletas',
                'Patológica si < 40 bpm o síntomas'
            ],
            preguntas_clinicas=[
                '¿Cuándo es "normal" la bradicardia?',
                '¿Qué diferencia bradicardia fisiológica de patológica?',
                '¿Cómo afecta el sistema vagal la frecuencia cardíaca?'
            ]
        ),
        'fibrilacion_auricular': ECGLesson(
            titulo='Fibrilación Auricular (AFib)',
            descripcion='Arritmia supraventricular caracterizada por actividad auricular caótica',
            concepto_clave='Ritmo irregularmente irregular, ausencia de ondas P',
            explicacion_fisiologica=(
                'La AFib ocurre cuando múltiples focos ectópicos en las aurículas disparan rápidamente.\n'
                'Esto resulta en:\n'
                '- Pérdida de la contracción auricular efectiva.\n'
                '- Respuesta ventricular irregular dependiendo de la conducción del nodo AV.\n'
                '- Riesgo aumentado de tromboembolismo (ACV).'
            ),
            hallazgos_clinicos=[
                'Ausencia de ondas P (sustituidas por ondas f)',
                'Intervalos R-R "irregularmente irregulares"',
                'Línea de base oscilante',
                'Complejos QRS generalmente estrechos'
            ],
            preguntas_clinicas=[
                '¿Por qué aumenta el riesgo de ACV en AFib?',
                '¿Cómo se define un ritmo "irregularmente irregular"?',
                '¿Qué es la escala CHA2DS2-VASc?'
            ]
        ),
        'taquicardia_ventricular': ECGLesson(
            titulo='Taquicardia Ventricular (TV)',
            descripcion='Arritmia potencialmente mortal originada en los ventrículos',
            concepto_clave='QRS ancho, frecuencia alta, emergencia médica',
            explicacion_fisiologica=(
                'La TV se origina por un circuito de reentrada o automatismo aumentado en el ventrículo.\n'
                'Es una emergencia porque puede degenerar en Fibrilación Ventricular o causar colapso hemodinámico.'
            ),
            hallazgos_clinicos=[
                'Frecuencia ventricular > 100 bpm (usualmente 150-250)',
                'Complejos QRS anchos (> 120 ms)',
                'Disociación AV (ocasionalmente visible)',
                'Ritmo generalmente regular'
            ],
            preguntas_clinicas=[
                '¿Qué define a un QRS como "ancho"?',
                '¿Cuál es la diferencia entre TV sostenida y no sostenida?',
                '¿Qué es la captura ventricular o latido de fusión?'
            ]
        ),
        'stemi': ECGLesson(
            titulo='Infarto con Elevación del ST (STEMI)',
            descripcion='Isquemia miocárdica aguda por oclusión coronaria total',
            concepto_clave='Elevación del punto J, lesión transmural',
            explicacion_fisiologica=(
                'La elevación del segmento ST indica una corriente de lesión que fluye desde el área infartada.\n'
                'Representa una emergencia médica que requiere reperfusión inmediata.'
            ),
            hallazgos_clinicos=[
                'Elevación del segmento ST > 1mm en dos derivaciones contiguas',
                'Cambios recíprocos (descenso ST) en derivaciones opuestas',
                'Posible presencia de ondas Q patológicas (tardío)',
                'Ondas T hiperagudas (temprano)'
            ],
            preguntas_clinicas=[
                '¿Qué arteria suele estar ocluida en un STEMI inferior?',
                '¿Qué significa "imagen en espejo" en el ECG?',
                '¿Cuál es el tiempo "puerta-balón" recomendado?'
            ]
        )
    }

    def obtener_leccion(self, tipo_arritimia: str) -> ECGLesson:
        """Obtiene una lección sobre un patrón ECG específico."""
        return self.LECTURAS.get(tipo_arritimia, self.LECTURAS['ritmo_sinusal_normal'])

    def modo_ensenanza(self, bpm: float, variabilidad_rr: float, lf_hf: float) -> Dict:
        """
        Modo educativo que explica hallazgos clínicos.
        
        Parámetros
        ----------
        bpm : float
            Frecuencia cardíaca en latidos por minuto
        variabilidad_rr : float
            SDNN (variabilidad general de RR)
        lf_hf : float
            Relación LF/HF (balance autonómico)
            
        Retorna
        -------
        dict
            Explicaciones educativas y preguntas
        """
        explicaciones = []
        tipo_arritimia = 'ritmo_sinusal_normal'

        # Análisis de frecuencia cardíaca
        if bpm > 100:
            tipo_arritimia = 'taquicardia'
            explicaciones.append(
                f'📊 FRECUENCIA CARDÍACA ELEVADA ({bpm:.0f} bpm)\n'
                'Causas posibles:\n'
                '- Estrés o ansiedad\n'
                '- Ejercicio reciente\n'
                '- Fiebre o infección\n'
                '- Trastornos tiroideos\n'
                '- Problemas cardíacos'
            )
        elif bpm < 60:
            tipo_arritimia = 'bradicardia'
            explicaciones.append(
                f'📊 FRECUENCIA CARDÍACA BAJA ({bpm:.0f} bpm)\n'
                'En atletas: respuesta normal (adaptación cardíaca)\n'
                'En otros: investigar\n'
                '- Hipotiroidismo\n'
                '- Presión intracraneal\n'
                '- Disfunción nodo SA'
            )
        else:
            explicaciones.append(f'✓ Frecuencia cardíaca normal: {bpm:.0f} bpm')

        # Análisis de variabilidad
        if variabilidad_rr < 0.05:
            explicaciones.append(
                '⚠️ VARIABILIDAD BAJA (< 0.05 s)\n'
                'Sugiere:\n'
                '- Estrés simpático aumentado\n'
                '- Posible insuficiencia cardíaca\n'
                '- Retirada vagal\n'
                'Requiere seguimiento clínico'
            )
        elif variabilidad_rr > 0.1:
            explicaciones.append(
                '✓ Variabilidad cardíaca normal/buena\n'
                'Indica balance autonómico saludable'
            )

        # Análisis del balance autonómico
        if lf_hf > 3:
            explicaciones.append(
                '⚠️ BALANCE AUTONÓMICO: Dominancia Simpática\n'
                'LF/HF ratio elevado sugiere:\n'
                '- Estrés emocional\n'
                '- Riesgo cardiovascular aumentado\n'
                '- Recomendación: técnicas de relajación'
            )
        elif lf_hf < 1:
            explicaciones.append(
                '✓ BALANCE AUTONÓMICO: Dominancia Vagal\n'
                'Indica estado de descanso/relajación\n'
                'Asociado con mejor pronóstico'
            )

        leccion = self.obtener_leccion(tipo_arritimia)

        return {
            'titulo_leccion': leccion.titulo,
            'descripcion': leccion.descripcion,
            'explicaciones': explicaciones,
            'concepto_clave': leccion.concepto_clave,
            'fisiologia': leccion.explicacion_fisiologica,
            'hallazgos': leccion.hallazgos_clinicos,
            'preguntas_estudio': leccion.preguntas_clinicas,
            'tipo_ritmo': tipo_arritimia
        }

    def generar_pregunta_interactiva(self) -> Dict:
        """Genera una pregunta de razonamiento clínico."""
        preguntas = [
            {
                'pregunta': '¿Qué representa la onda P en el ECG?',
                'opciones': [
                    'Despolarización auricular',
                    'Despolarización ventricular',
                    'Repolarización ventricular',
                    'Conducción AV'
                ],
                'respuesta_correcta': 0,
                'explicacion': 'La onda P representa la despolarización auricular, que es la actividad eléctrica de las aurículas.'
            },
            {
                'pregunta': '¿Cuál es el intervalo normal PR?',
                'opciones': [
                    '80-120 ms',
                    '120-200 ms',
                    '200-300 ms',
                    '40-80 ms'
                ],
                'respuesta_correcta': 1,
                'explicacion': 'El intervalo PR normal es de 120-200 ms e incluye la conducción a través del nodo AV.'
            },
            {
                'pregunta': '¿Qué indica una onda P invertida en derivación II?',
                'opciones': [
                    'Ritmo sinusal normal',
                    'Origen no sinusal del ritmo',
                    'Hipertrofia ventricular',
                    'Bloqueo AV'
                ],
                'respuesta_correcta': 1,
                'explicacion': 'Una onda P invertida en II sugiere que el ritmo no se origina en el nodo SA.'
            }
        ]
        return np.random.choice(preguntas)

    def generar_caso_clinico(self, complejidad: str = 'basico') -> Dict:
        """Genera un caso clínico educativo para análisis."""
        casos = {
            'basico': {
                'escenario': (
                    'Paciente de 35 años, varón, asintomático.\n'
                    'Presentación: ECG de rutina en examen físico.'
                ),
                'signos_vitales': {
                    'fc': '78 bpm',
                    'pa': '120/80 mmHg',
                    'respiracion': '16/min',
                    'temperatura': '36.5°C'
                },
                'pregunta': '¿Cuál es tu interpretación inicial del ECG?',
                'respuesta': 'Ritmo sinusal normal. Toda la actividad es normal.'
            },
            'intermedio': {
                'escenario': (
                    'Paciente de 58 años, mujer, refiere palpitaciones.\n'
                    'Duración: 2 horas.\n'
                    'ECG tomado durante síntomas.'
                ),
                'signos_vitales': {
                    'fc': '115 bpm',
                    'pa': '135/85 mmHg',
                    'respiracion': '20/min',
                    'temperatura': '37.8°C'
                },
                'pregunta': '¿Cuál es la causa probable de los síntomas?',
                'respuesta': 'Taquicardia sinusal probablemente por fiebre. Investigar causa de fiebre.'
            },
            'avanzado': {
                'escenario': (
                    'Paciente de 72 años, varón, con antecedente de HTA.\n'
                    'Refiere mareos y disnea de esfuerzo.\n'
                    'ECG muestra irregularidad.'
                ),
                'signos_vitales': {
                    'fc': '88 bpm (irregular)',
                    'pa': '148/92 mmHg',
                    'respiracion': '22/min',
                    'temperatura': '36.8°C'
                },
                'pregunta': '¿Qué arritmia sospechas? ¿Cuál es el siguiente paso?',
                'respuesta': 'Considerar fibrilación auricular. Solicitar Holter, troponina, TSH.'
            }
        }
        return casos.get(complejidad, casos['basico'])


def create_educational_report(
    bpm: float,
    sdnn: float,
    rmssd: float,
    lf_hf: float,
    prediccion: str
) -> str:
    """
    Genera un reporte educativo sobre los hallazgos HRV/ECG.
    """
    report = f"""
═════════════════════════════════════════════════════════════════
    REPORTE EDUCATIVO DE ANÁLISIS CARDIOVASCULAR
═════════════════════════════════════════════════════════════════

📊 MÉTRICAS FUNDAMENTALES
─────────────────────────────────────────────────────────────────
Frecuencia Cardíaca (BPM): {bpm:.1f}
  • Rango normal: 60-100 bpm en reposo
  • Estado actual: {'Normal' if 60 <= bpm <= 100 else 'Fuera de rango - Revisar'}

Variabilidad Cardíaca (SDNN): {sdnn:.4f} s
  • Mide la dispersión de intervalos RR
  • SDNN alto = mejor función autonómica
  • SDNN bajo = posible estrés o patología

Tono Parasimpático (RMSSD): {rmssd:.4f} s
  • Refleja actividad del nervio vago
  • Importante para recuperación cardíaca
  • Se reduce con estrés y envejecimiento

Balance Autonómico (LF/HF): {lf_hf:.2f}
  • LF = actividad simpática
  • HF = actividad parasimpática
  • Ratio > 3: dominancia simpática (estrés)
  • Ratio < 1: dominancia parasimpática (descanso)

🏥 PREDICCIÓN CLÍNICA
─────────────────────────────────────────────────────────────────
Clasificación AI: {prediccion}

INTERPRETACIÓN EDUCATIVA:
Este análisis proporciona información sobre el estado del balance
autonómico cardiovascular. Los parámetros HRV son útiles para:
- Evaluación del estrés
- Monitoreo de recuperación post-ejercicio
- Predicción de riesgo cardiovascular
- Evaluación de autonomía nerviosa

⚠️ NOTA EDUCATIVA:
Este sistema es una HERRAMIENTA EDUCATIVA. No reemplaza
evaluación clínica profesional. Para diagnóstico definitivo,
consultar cardiólogo.

═════════════════════════════════════════════════════════════════
"""
    return report
