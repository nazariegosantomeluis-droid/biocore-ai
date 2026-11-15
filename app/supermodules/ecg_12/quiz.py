"""Desafío educativo de ECG-12: banco de 19 preguntas con explicación (tanda 1 de la fase 1: movido aquí SIN cambiar
las preguntas, para que Practicar lo monte solo). Contención (Art. I): ninguna opción preseleccionada y «Verificar
respuesta» deshabilitado hasta que se elige una; la corrección solo aparece después de verificar."""

from typing import Dict, List

import streamlit as st

ECG_QUIZ_BANK: List[Dict[str, str]] = [
    {
        'question': '¿Cuál es la derivación que normalmente muestra mayor amplitud de R en un ECG estándar?',
        'options': ['V1', 'V2', 'V4', 'V6'],
        'correct': 'V4',
        'explanation': 'En la zona de transición, V4 suele mostrar R máxima en ECG normal.'
    },
    {
        'question': 'Elevación ST en V1-V4 sugiere infarto en territorio de:',
        'options': ['RCA', 'LAD', 'LCx', 'Posterior'],
        'correct': 'LAD',
        'explanation': 'V1-V4 corresponde a la porción anterior del ventrículo izquierdo.'
    },
    {
        'question': 'Un eje QRS de -45° se clasifica como:',
        'options': ['Normal', 'LAD', 'RAD', 'Indeterminado'],
        'correct': 'LAD',
        'explanation': 'Un eje entre -30° y -90° indica desviación izquierda.'
    },
    {
        'question': '¿Qué patrón es característico de RBBB?',
        'options': ['RSR’ en V1-V2', 'QS en V1', 'Delta wave', 'QT prolongado'],
        'correct': 'RSR’ en V1-V2',
        'explanation': 'RBBB muestra patrón RSR’ en las derivaciones precordiales derechas.'
    },
    {
        'question': 'Una onda delta y PR corto son signos de:',
        'options': ['AF', 'Flutter', 'WPW', 'LBBB'],
        'correct': 'WPW',
        'explanation': 'El síndrome de Wolff-Parkinson-White se caracteriza por delta wave y PR corto.'
    },
    {
        'question': 'Ausencia de ondas P y ritmo irregular indican:',
        'options': ['AF', 'Flutter', 'VT', 'QB'],
        'correct': 'AF',
        'explanation': 'La fibrilación auricular presenta ritmo irregularmente irregular sin P reconocible.'
    },
    {
        'question': 'Un QT corregido > 500 ms sugiere riesgo de:',
        'options': ['Bloqueo AV', 'Taquicardia ventricular polimórfica', 'Infarto inferior', 'Pericarditis'],
        'correct': 'Taquicardia ventricular polimórfica',
        'explanation': 'QT largo incrementa el riesgo de torsades de pointes.'
    },
    {
        'question': 'Territorio lateral incluye estas derivaciones:',
        'options': ['II, III, aVF', 'V1-V2', 'I, aVL, V5-V6', 'V3-V4'],
        'correct': 'I, aVL, V5-V6',
        'explanation': 'Las derivaciones laterales son I, aVL y V5-V6.'
    },
    {
        'question': '¿Cuál es el rango normal del PR?',
        'options': ['80-120 ms', '120-200 ms', '200-300 ms', '300-400 ms'],
        'correct': '120-200 ms',
        'explanation': 'El intervalo PR normal es 120-200 ms.'
    },
    {
        'question': 'La desviación derecha del eje se define en:',
        'options': ['-30° a +90°', '+90° a +180°', '-90° a -30°', '+180° a -180°'],
        'correct': '+90° a +180°',
        'explanation': 'RAD se encuentra entre +90° y +180°.'
    },
    {
        'question': 'Patrón de ST depresivo difuso con PR elevado sugiere:',
        'options': ['Pericarditis', 'Infarto anterior', 'WPW', 'LBBB'],
        'correct': 'Pericarditis',
        'explanation': 'Pericarditis aguda suele mostrar ST elevado difuso y PR deprimido.'
    },
    {
        'question': 'Una señal de ECG cargada desde dispositivo con solo derivación II puede:',
        'options': ['permitir análisis completo de todas las derivaciones', 'generar inferencias usando derivadas sintéticas', 'no servir para diagnóstico', 'ser útil solo para frecuencia'],
        'correct': 'generar inferencias usando derivadas sintéticas',
        'explanation': 'Se puede crear una representación 12-lead sintética a partir de una derivación de referencia.'
    },
    {
        'question': 'El parámetro QRS > 120 ms en V1-V6 sugiere:',
        'options': ['Bloqueo de rama', 'AF', 'Hipertrofia ventricular', 'Bradicardia'],
        'correct': 'Bloqueo de rama',
        'explanation': 'QRS ancho es característico de bloqueos de rama y aberrancia ventricular.'
    },
    {
        'question': 'En un ECG de dispositivo real, ¿qué valor de SNR es preferible?',
        'options': ['Mayor a 10', 'Menor a 1', 'Entre 0.1 y 0.5', 'Cero'],
        'correct': 'Mayor a 10',
        'explanation': 'Un SNR alto indica señal limpia para análisis clínico.'
    },
    {
        'question': '¿Qué representa el segmento ST?',
        'options': ['Tiempo entre QRS y comienzo de T', 'Duración de la onda P', 'Intervalo RR', 'Longitud de QRS'],
        'correct': 'Tiempo entre QRS y comienzo de T',
        'explanation': 'El segmento ST es el periodo isoeléctrico entre QRS y T.'
    },
    {
        'question': '¿Cuál es la utilidad del análisis automático por reglas de umbral en ECG 12-lead?',
        'options': ['Señalar patrones candidatos para que los confirme el clínico', 'Sustituir completamente al médico', 'Reducir la frecuencia cardiaca', 'Medir la SpO2'],
        'correct': 'Señalar patrones candidatos para que los confirme el clínico',
        'explanation': 'El análisis aplica reglas fijas de umbral (no un modelo de aprendizaje): señala hallazgos candidatos, no reemplaza la evaluación clínica.'
    },
    {
        'question': 'En un ECG normal, la onda T debe ser:',
        'options': ['Positiva en V5-V6', 'Negativa en V5-V6', 'Ausente', 'Delta'],
        'correct': 'Positiva en V5-V6',
        'explanation': 'La onda T suele ser positiva en las derivaciones laterales normales.'
    },
    {
        'question': 'Un pseudo-infarcto por LVH se identifica por:',
        'options': ['QRS alto con ST negativo en V5-V6', 'Delta wave', 'QT corto', 'RBBB'],
        'correct': 'QRS alto con ST negativo en V5-V6',
        'explanation': 'LVH puede causar altos voltajes y cambios secundarios de ST/T.'
    },
    {
        'question': 'Los ritmos que esta página puede simular y analizar con reglas de umbral incluyen:',
        'options': ['AF, Flutter, WPW, Long QT', 'Solo bradicardia', 'Solo infartos', 'Solo hipertrofia'],
        'correct': 'AF, Flutter, WPW, Long QT',
        'explanation': 'El laboratorio simula estos ritmos y los interpreta con reglas fijas de umbral; no usa un modelo de IA entrenado.'
    }
]


def render_ecg12_quiz(key_prefix: str = "") -> None:
    question_index = st.selectbox(
        "Selecciona la pregunta:",
        list(range(1, len(ECG_QUIZ_BANK) + 1)),
        format_func=lambda x: f"Pregunta {x}",
        key=f"{key_prefix}ecg12_quiz_index" if key_prefix else None,
    )
    current_question = ECG_QUIZ_BANK[question_index - 1]

    st.write(f"**Pregunta {question_index}:** {current_question['question']}")
    selected_answer = st.radio("Respuesta:", current_question['options'], index=None, key=f"{key_prefix}quiz_{question_index}")

    if st.button("Verificar respuesta", key=f"{key_prefix}verify_quiz", disabled=selected_answer is None):
        if selected_answer == current_question['correct']:
            st.success(f"✅ Correcto. {current_question['explanation']}")
        else:
            st.error(f"❌ Incorrecto. {current_question['explanation']}")
