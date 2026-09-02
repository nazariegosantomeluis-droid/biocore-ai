"""Advanced ECG tutor for clinical training and interactive learning."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import plotly.graph_objects as go
from scipy.signal import find_peaks

from src.signal_generator import ECGGenerator


@dataclass
class ECGTutorCase:
    case_type: str
    title: str
    description: str
    complexity: str
    time: np.ndarray
    signal: np.ndarray
    fs: float
    metadata: Dict[str, str]


class ECGTutor:
    """Interactive ECG tutoring engine for students and clinicians."""

    CASES = {
        'ritmo_sinusal_normal': {
            'titulo': 'Ritmo Sinusal Normal',
            'descripcion': 'Caso clínico normal para estudiar el ECG de referencia.',
            'dificultad': 'basico'
        },
        'taquicardia': {
            'titulo': 'Taquicardia Sinusal',
            'descripcion': 'Aumento de FC con morfología ECG normal.',
            'dificultad': 'intermedio'
        },
        'bradicardia': {
            'titulo': 'Bradicardia Sinusal',
            'descripcion': 'Disminución de FC con ECG en ritmo sinusal.',
            'dificultad': 'intermedio'
        },
        'fibrilacion_auricular': {
            'titulo': 'Fibrilación Auricular',
            'descripcion': 'Ritmo irregularmente irregular sin ondas P claras.',
            'dificultad': 'avanzado'
        },
        'taquicardia_ventricular': {
            'titulo': 'Taquicardia Ventricular',
            'descripcion': 'Arritmia ventricular de complejos anchos y ritmo acelerado.',
            'dificultad': 'avanzado'
        },
        'stemi': {
            'titulo': 'STEMI',
            'descripcion': 'Elevación del segmento ST en múltiples latidos.',
            'dificultad': 'avanzado'
        }
    }

    QUIZ_BANK = {
        'basico': [
            {
                'pregunta': '¿Qué representa la onda P?',
                'opciones': [
                    'Despolarización auricular',
                    'Repolarización ventricular',
                    'Despolarización ventricular',
                    'Conducción auriculoventricular'
                ],
                'respuesta': 0,
                'explicacion': 'La onda P representa la despolarización de las aurículas.'
            },
            {
                'pregunta': '¿Cuál es el intervalo PR normal?',
                'opciones': ['80-120 ms', '120-200 ms', '200-300 ms', '40-80 ms'],
                'respuesta': 1,
                'explicacion': 'El intervalo PR normal es de 120-200 ms.'
            }
        ],
        'intermedio': [
            {
                'pregunta': '¿Qué hallazgo es típico de fibrilación auricular?',
                'opciones': [
                    'Onda P ausente y R-R irregular',
                    'Onda P invertida en II',
                    'QT prolongado',
                    'Bloqueo de rama derecha'
                ],
                'respuesta': 0,
                'explicacion': 'La fibrilación auricular suele mostrar ausencia de ondas P y un ritmo irregular.'
            },
            {
                'pregunta': '¿Qué define un complejo QRS ancho?',
                'opciones': ['> 80 ms', '> 100 ms', '> 120 ms', '> 140 ms'],
                'respuesta': 2,
                'explicacion': 'Un QRS ancho se define como mayor de 120 ms.'
            }
        ],
        'avanzado': [
            {
                'pregunta': '¿Cuál es el significado clínico de elevación del ST?',
                'opciones': [
                    'Lesión miocárdica aguda',
                    'Bloqueo AV de primer grado',
                    'Hipertrofia auricular',
                    'Estado de reposo normal'
                ],
                'respuesta': 0,
                'explicacion': 'La elevación del ST indica lesión miocárdica aguda, como un STEMI.'
            },
            {
                'pregunta': '¿Qué indica un intervalo QT prolongado?',
                'opciones': [
                    'Mayor riesgo de torsades de pointes',
                    'Aumento de la contractilidad',
                    'Bloqueo de rama izquierda',
                    'Fibrilación auricular'
                ],
                'respuesta': 0,
                'explicacion': 'El QT prolongado está asociado con riesgo de arritmias ventriculares como torsades de pointes.'
            }
        ]
    }

    def __init__(self, language: str = 'es', target: str = 'rural'):
        self.language = language
        self.target = target

    def available_cases(self) -> List[str]:
        return list(self.CASES.keys())

    def case_title(self, case_type: str) -> str:
        return self.CASES.get(case_type, {}).get('titulo', case_type)

    def detect_r_peaks(self, signal: np.ndarray, fs: float, prominence_factor: float = 0.3) -> np.ndarray:
        if len(signal) < 3:
            return np.array([], dtype=int)
        threshold = np.mean(signal) + prominence_factor * np.std(signal)
        peaks, _ = find_peaks(signal, distance=int(0.3 * fs), height=threshold)
        if len(peaks) == 0:
            peaks, _ = find_peaks(signal, distance=int(0.3 * fs))
        return np.asarray(peaks, dtype=int)

    def create_case(
        self,
        case_type: str = 'ritmo_sinusal_normal',
        complexity: str = 'basico',
        duration: float = 10.0,
        fs: float = 250.0
    ) -> ECGTutorCase:
        t, signal = ECGGenerator.get_case(case_type, duration=duration, fs=fs)
        case_info = self.CASES.get(case_type, {'titulo': case_type, 'descripcion': ''})
        return ECGTutorCase(
            case_type=case_type,
            title=case_info['titulo'],
            description=case_info['descripcion'],
            complexity=complexity,
            time=t,
            signal=signal,
            fs=fs,
            metadata={'case_type': case_type, 'complexity': complexity}
        )

    def explain_components(
        self,
        signal: np.ndarray,
        fs: float,
        rpeaks: np.ndarray
    ) -> Dict[str, str]:
        explanation: Dict[str, str] = {}
        if len(rpeaks) == 0:
            explanation['info'] = 'No se detectaron picos R. Ajusta el umbral o usa una señal más limpia.'
            return explanation

        r = rpeaks[0]
        p = max(0, int(r - 0.16 * fs))
        q = max(0, int(r - 0.06 * fs))
        s = min(len(signal) - 1, int(r + 0.06 * fs))
        t = min(len(signal) - 1, int(r + 0.25 * fs))

        pr_interval = (r - p) / fs
        qt_interval = (t - q) / fs
        st_segment = (t - s) / fs

        explanation['Onda P'] = (
            'La onda P representa la despolarización de las aurículas. ' 
            'Su aparición antes del complejo QRS confirma la conducción auriculoventricular normal.'
        )
        explanation['Complejo QRS'] = (
            'El QRS corresponde a la despolarización ventricular. ' 
            'Debe ser estrecho (< 120 ms) en el ritmo sinusal normal.'
        )
        explanation['Onda T'] = (
            'La onda T refleja la repolarización de los ventrículos. ' 
            'Su forma y dirección aportan pistas sobre isquemia y alteraciones electrolíticas.'
        )
        explanation['Intervalo PR'] = (
            f'Intervalo estimado PR: {pr_interval*1000:.0f} ms. '
            'Representa la conducción auriculoventricular.'
        )
        explanation['Intervalo QT'] = (
            f'Intervalo QT estimado: {qt_interval*1000:.0f} ms. '
            'Incluye despolarización y repolarización ventricular.'
        )
        explanation['Segmento ST'] = (
            f'Segmento ST estimado: {st_segment*1000:.0f} ms. '
            'Su elevación o depresión sugiere isquemia o lesión.'
        )
        return explanation

    def average_beat_template(
        self,
        signal: np.ndarray,
        fs: float,
        rpeaks: np.ndarray,
        window: float = 0.6,
        max_beats: int = 6
    ) -> Tuple[np.ndarray, np.ndarray]:
        if len(rpeaks) == 0:
            return np.array([]), np.array([])

        beat_samples = int(window * fs)
        half_window = beat_samples // 2
        templates: List[np.ndarray] = []
        for idx in rpeaks[:max_beats]:
            start = max(0, int(idx - half_window))
            end = min(len(signal), int(idx + half_window))
            beat = signal[start:end]
            if len(beat) == beat_samples:
                templates.append(beat)
        if not templates:
            return np.array([]), np.array([])

        avg_template = np.mean(np.vstack(templates), axis=0)
        beat_time = np.linspace(-window / 2, window / 2, beat_samples)
        return beat_time, avg_template

    def noise_vs_signal(self, signal: np.ndarray, fs: float, rpeaks: np.ndarray) -> Dict[str, float]:
        if len(signal) < 2:
            return {'noise_std': 0.0, 'signal_std': 0.0, 'ratio': 0.0}
        kernel = int(max(3, min(len(signal) - 1, round(0.04 * fs))))
        baseline = np.convolve(signal, np.ones(kernel) / kernel, mode='same')
        noise_std = float(np.std(signal - baseline))
        signal_std = float(np.std(signal))
        ratio = noise_std / signal_std if signal_std > 0 else 0.0
        return {'noise_std': noise_std, 'signal_std': signal_std, 'ratio': ratio}

    def create_clinical_ecg_figure(
        self,
        signal: np.ndarray,
        fs: float,
        rpeaks: np.ndarray,
        start: float = 0.0,
        duration: float = 8.0,
        show_annotations: bool = True,
        teaching_overlay: bool = True
    ) -> go.Figure:
        time = np.arange(len(signal)) / fs
        end = min(time[-1], start + duration)
        window_mask = (time >= start) & (time <= end)
        x = time[window_mask]
        y = signal[window_mask]

        if len(x) == 0:
            x = time
            y = signal
            end = time[-1]

        ymin = float(np.min(y) - 0.5)
        ymax = float(np.max(y) + 0.5)

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=x,
                y=y,
                mode='lines',
                line=dict(color='#00ff96', width=2.6),
                name='ECG'
            )
        )

        visible_peaks = [int(idx) for idx in rpeaks if start <= idx / fs <= end]
        if visible_peaks:
            fig.add_trace(
                go.Scatter(
                    x=time[visible_peaks],
                    y=signal[visible_peaks],
                    mode='markers',
                    marker=dict(color='#ff6b6b', size=8, symbol='x'),
                    name='R Peaks'
                )
            )

        shapes: List[Dict[str, object]] = []
        x0 = start
        while x0 <= end + 1e-6:
            major = abs((x0 - start) / 0.2 - round((x0 - start) / 0.2)) < 1e-6
            shapes.append({
                'type': 'line',
                'x0': x0,
                'x1': x0,
                'y0': ymin,
                'y1': ymax,
                'line': {
                    'color': '#ff4040' if major else '#ffccd2',
                    'width': 1.5 if major else 0.8,
                }
            })
            x0 += 0.04
        y0 = ymin
        while y0 <= ymax + 1e-6:
            major = abs((y0 - ymin) / 0.5 - round((y0 - ymin) / 0.5)) < 1e-6
            shapes.append({
                'type': 'line',
                'x0': start,
                'x1': end,
                'y0': y0,
                'y1': y0,
                'line': {
                    'color': '#ff4040' if major else '#ffccd2',
                    'width': 1.5 if major else 0.8,
                }
            })
            y0 += 0.1

        if show_annotations and visible_peaks:
            main_peak = visible_peaks[0]
            r_time = time[main_peak]
            p_time = max(start, r_time - 0.16)
            q_time = max(start, r_time - 0.06)
            t_time = min(end, r_time + 0.28)
            st_time = min(end, r_time + 0.10)

            annotations = [
                {'text': 'P', 'x': p_time, 'y': float(signal[main_peak]) - 0.15, 'ay': -50},
                {'text': 'QRS', 'x': r_time, 'y': float(signal[main_peak]) + 0.30, 'ay': -60},
                {'text': 'ST', 'x': st_time, 'y': float(signal[main_peak]) + 0.15, 'ay': -50},
                {'text': 'T', 'x': t_time, 'y': float(signal[main_peak]) + 0.12, 'ay': -50}
            ]
            for ann in annotations:
                fig.add_annotation(
                    x=ann['x'],
                    y=ann['y'],
                    ax=ann['x'] - 0.4,
                    ay=ann['y'] + ann['ay'],
                    text=ann['text'],
                    font=dict(color='#ffffff', size=12, family='Arial'),
                    arrowcolor='#ffffff',
                    arrowwidth=1.2,
                    arrowhead=2,
                    bgcolor='rgba(0,0,0,0.5)',
                    bordercolor='#ff6b6b',
                    borderwidth=1
                )

        title = 'ECG Tutor — Strip Clínico'
        if teaching_overlay:
            title = 'ECG Tutor — Monitor Médico Interactivo'

        fig.update_layout(
            title=title,
            paper_bgcolor='#081c2c',
            plot_bgcolor='#081c2c',
            font=dict(color='#e5f6ff', family='Inter, Arial, sans-serif'),
            margin=dict(l=20, r=20, t=50, b=20),
            legend=dict(bgcolor='rgba(0,0,0,0.35)', bordercolor='#4f739d', borderwidth=1)
        )
        fig.update_xaxes(
            title='Tiempo (s)',
            range=[start, end],
            showgrid=False,
            zeroline=False,
            tickmode='linear',
            dtick=0.5,
            tickfont=dict(color='#cbd6e3')
        )
        fig.update_yaxes(
            title='mV',
            range=[ymin, ymax],
            showgrid=False,
            zeroline=False,
            tickmode='linear',
            dtick=0.5,
            tickfont=dict(color='#cbd6e3')
        )
        return fig

    def create_beat_template_figure(
        self,
        beat_time: np.ndarray,
        beat_signal: np.ndarray
    ) -> go.Figure:
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=beat_time,
                y=beat_signal,
                mode='lines',
                line=dict(color='#f4d35e', width=3),
                name='Latido promedio'
            )
        )
        fig.update_layout(
            title='Latido promedio',
            paper_bgcolor='#081c2c',
            plot_bgcolor='#081c2c',
            font=dict(color='#ffffff'),
            margin=dict(l=16, r=16, t=40, b=20)
        )
        fig.update_xaxes(title='Tiempo (s)', showgrid=True, gridcolor='#253858', zeroline=False)
        fig.update_yaxes(title='mV', showgrid=True, gridcolor='#253858', zeroline=False)
        return fig

    def generate_quiz(self, level: str = 'basico') -> Dict[str, object]:
        questions = self.QUIZ_BANK.get(level, self.QUIZ_BANK['basico'])
        return random.choice(questions)

    def grade_quiz(self, question: Dict[str, object], answer: object) -> bool:
        if isinstance(answer, (str, np.str_)):
            try:
                answer_index = int(question['opciones'].index(str(answer)))
            except ValueError:
                return False
        else:
            try:
                answer_index = int(answer)
            except (ValueError, TypeError):
                return False
        return int(answer_index) == int(question['respuesta'])
