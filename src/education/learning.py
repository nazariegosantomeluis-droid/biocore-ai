"""Educational interactive modules for students and rural learning."""

from typing import Dict, List


def explain_waveform(signal_type: str, features: Dict[str, float]) -> List[str]:
    explanations = []
    if signal_type == 'ecg':
        explanations.append('La señal ECG representa la actividad eléctrica del corazón.')
        explanations.append('La onda P corresponde a la despolarización auricular.')
        explanations.append('El complejo QRS corresponde a la despolarización ventricular.')
        explanations.append('La onda T representa la repolarización ventricular.')
        bpm = features.get('bpm')
        if bpm is not None:
            explanations.append(f'La frecuencia cardíaca estimada es {bpm:.1f} bpm.')
    elif signal_type == 'ppg':
        explanations.append('La señal PPG mide cambios de volumen sanguíneo periférico.')
        explanations.append('Se usa para estimar frecuencia cardíaca y saturación de oxígeno.')
    elif signal_type == 'respiration':
        explanations.append('La señal de respiración muestra ciclos de inhalación y exhalación.')
    return explanations


def create_quiz(topic: str) -> Dict[str, object]:
    if topic == 'ecg':
        return {
            'pregunta': '¿Cuál es la derivación habitual para detectar fibrilación auricular?',
            'opciones': ['II', 'V1', 'aVR', 'V6'],
            'respuesta': 'II',
            'explicacion': 'La derivación II es útil para ver el ritmo auricular y la onda P.'
        }
    if topic == 'ppg':
        return {
            'pregunta': '¿Qué mide principalmente una señal PPG?',
            'opciones': ['Actividad eléctrica', 'Volumen sanguíneo periférico', 'Presión arterial', 'Temperatura corporal'],
            'respuesta': 'Volumen sanguíneo periférico',
            'explicacion': 'PPG mide cambios en el volumen de sangre en el lecho vascular.'
        }
    return {'pregunta': 'Tema no definido', 'opciones': [], 'respuesta': '', 'explicacion': ''}


def clinical_case(level: str) -> Dict[str, str]:
    cases = {
        'basico': {
            'titulo': 'Ritmo sinusal normal',
            'descripcion': 'Paciente joven con ECG normal y síntomas leves de palpitaciones.',
            'objetivo': 'Identificar el ritmo sinusal y reconocer parámetros normales.'
        },
        'intermedio': {
            'titulo': 'Fibrilación auricular',
            'descripcion': 'Paciente mayor con irregularmente irregular y ausencia de ondas P.',
            'objetivo': 'Identificar AFib y entender riesgos de tromboembolismo.'
        },
        'avanzado': {
            'titulo': 'STEMI anterior',
            'descripcion': 'Paciente con dolor torácico y elevación del ST en V2-V4.',
            'objetivo': 'Reconocer patrón de lesión isquémica y urgencia de reperfusión.'
        }
    }
    return cases.get(level, cases['basico'])
