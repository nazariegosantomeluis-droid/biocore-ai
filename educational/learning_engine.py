"""Learning engine: orchestrates lessons, quizzes and scoring for students."""
from __future__ import annotations
from typing import List, Dict, Any
from dataclasses import dataclass, field
from typing import Optional

try:
    from educational import rural_mode
except Exception:
    # local import path fallback
    from . import rural_mode


@dataclass
class QuizQuestion:
    prompt: str
    choices: List[str]
    answer: int
    # Fusión Education+Academia, Capa 1 (2026-07-13): `category` clasifica cada
    # pregunta por lo que realmente pregunta (no inventado — es una lectura de
    # su contenido), para que el selector de "Lección" filtre de verdad en vez
    # de ser decorativo. `explanation` solo se llena cuando ya existía un texto
    # real de origen (las 2 preguntas rescatadas de src/education/learning.py)
    # — nunca se redacta una explicación nueva para las 14 originales, que no
    # tenían ninguna.
    category: str = "General"
    explanation: str = ""


@dataclass
class LearningEngine:
    student_id: str
    progress: Dict[str, Any] = field(default_factory=dict)
    score: float = 0.0

    def register_lesson(self, lesson_id: str) -> None:
        self.progress.setdefault(lesson_id, {'completed': False, 'score': 0.0})

    def save_progress_local(self) -> None:
        """Persist progress to local storage (Modo Rural)."""
        try:
            rural_mode.save_progress(self.student_id, self.progress)
        except Exception:
            pass

    def load_progress_local(self) -> Optional[Dict[str, Any]]:
        """Load persisted progress if available and merge into current state."""
        try:
            data = rural_mode.load_progress(self.student_id)
            if data:
                self.progress.update(data)
                return data
        except Exception:
            return None
        return None

    def grade_quiz(self, questions: Dict[int, QuizQuestion], responses: Dict[int, int]) -> float:
        """Grade a quiz given questions and a mapping of responses.

        Returns percentage score (0-100).
        """
        correct = 0
        for qid, q in questions.items():
            if responses.get(qid) == q.answer:
                correct += 1
        score = float(correct) / max(1, len(questions)) * 100.0
        return score

    def submit_quiz(self, lesson_id: str, questions: Dict[int, QuizQuestion], responses: Dict[int, int]) -> float:
        """Record the quiz result and update progress state."""
        score = self.grade_quiz(questions, responses)
        self.progress.setdefault(lesson_id, {})
        self.progress[lesson_id]['completed'] = True
        self.progress[lesson_id]['score'] = score
        self.score = (self.score + score) / 2.0 if self.score else score
        return score

    def get_progress(self) -> Dict[str, Any]:
        return self.progress


# Fusión Education+Academia, Capa 1 (2026-07-13): las 4 categorías reales que
# clasifican el banco. No son lecciones nuevas inventadas — son los 3 nombres
# que el selector de "Lección" ya mostraba (con "12-derivaciones" alineado al
# texto exacto del botón) más "Otras señales", el hogar honesto para las 2
# preguntas rescatadas que no son específicamente de ECG (una es EEG, la otra
# PPG) — decidido con el usuario en vez de forzarlas dentro de una categoría
# a la que no pertenecen.
LESSON_CATEGORIES = ["ECG Básico", "ECG 12-derivaciones", "Arritmias", "Otras señales"]


def generate_quiz(topic: str = 'ecg_basics', level: str = 'basic', lesson: str = None) -> Dict[int, QuizQuestion]:
    """Return a small bank of quiz questions for a given topic and difficulty level.

    The number of questions scales with difficulty to address the earlier complaint
    about too few intermediate questions.

    `lesson`: si se pasa uno de `LESSON_CATEGORIES`, filtra el pool a solo las
    preguntas de esa categoría antes de aplicar el recorte por nivel. Si es
    `None` (comportamiento previo, sin cambios), usa el pool completo — no
    rompe ningún llamador existente que no conozca este parámetro nuevo.
    """
    # Simple hardcoded question examples for scaffolding. Can be replaced by DB.
    # Fusión Education+Academia, Capa 1 (2026-07-13): se agregaron las 2
    # preguntas reales rescatadas de src/education/learning.py::create_quiz()
    # (temas 'ecg' y 'ppg') — antes inalcanzables por 3 bugs de conexión
    # independientes (tema 'cardio' inexistente en esa función, dict devuelto
    # donde el llamador esperaba una lista, claves en español donde el
    # llamador esperaba inglés). El contenido de esas 2 preguntas y su
    # explicación se copiaron tal cual, sin reescribir ni inventar nada nuevo.
    # `category` en las 14 preguntas originales se agregó clasificando lo que
    # cada una ya pregunta de verdad (ninguna pregunta nueva, solo etiquetas).
    pool: Dict[str, List[QuizQuestion]] = {
        'ecg_basics': [
            QuizQuestion('¿Cuál es la frecuencia cardíaca normal adulta (aprox.)?', ['30-50', '60-100', '110-150', '150-200'], 1, category="ECG Básico"),
            QuizQuestion('¿Qué representa el complejo QRS?', ['Despolarización ventricular', 'Repolarización ventricular', 'Despolarización auricular', 'Actividad muscular'], 0, category="ECG Básico"),
            QuizQuestion('¿Qué derivada es útil para ver la pared lateral?', ['V1', 'V2', 'V5', 'aVR'], 2, category="ECG 12-derivaciones"),
            QuizQuestion('¿Qué indica una elevación ST persistente?', ['Isquemia crónica', 'Infarto agudo (STEMI)', 'Hipertensión', 'Arritmia'], 1, category="ECG Básico"),
            QuizQuestion('¿Qué mide el intervalo PR?', ['Tiempo entre P y inicio QRS', 'Duración QRS', 'Frecuencia cardíaca', 'QTc'], 0, category="ECG Básico"),
            QuizQuestion('¿Qué es una PVC?', ['Extrasístole ventricular', 'Taquicardia supraventricular', 'Bloqueo AV', 'Fibrilación auricular'], 0, category="Arritmias"),
            QuizQuestion('¿Cómo se calcula la FC desde RR?', ['60/mean(RR)', 'mean(RR)/60', 'sum(RR)/n', '60*mean(RR)'], 0, category="ECG Básico"),
            QuizQuestion('¿Cuál banda EEG sugiere relajación con ojos cerrados?', ['Delta', 'Theta', 'Alpha', 'Beta'], 2, category="Otras señales"),
            QuizQuestion('¿Cuál derivada muestra mejor el IEC anterior (V1-V4)?', ['V1-V4', 'V5-V6', 'I, aVL', 'aVF'], 0, category="ECG 12-derivaciones"),
            QuizQuestion('¿Qué signo sugiere HVI en el ECG?', ['Voltajes precordiales bajos', 'Elevación ST difusa', 'R grandes en V5-V6', 'Ondas U prominentes'], 2, category="ECG 12-derivaciones"),
            QuizQuestion('¿Cuál es una causa frecuente de bradicardia?', ['Hipertiroidismo', 'Bloqueo AV', 'Fiebre', 'Deshidratación'], 1, category="Arritmias"),
            QuizQuestion('¿Qué significa un eje eléctrico izquierdo (valor negativo en II)?', ['Posible HVI', 'Infarto lateral', 'Hiperkalemia', 'Taquicardia'], 0, category="ECG 12-derivaciones"),
            QuizQuestion('¿Qué patrón sugiere bloqueo de rama derecha?', ['R predominant in V1', 'Deep S in V1', 'Large R in V5', 'ST depression in II'], 0, category="Arritmias"),
            QuizQuestion('¿Cuál es la intervención inicial para STEMI sospechado?', ['Administrar analgesia y observar', 'Activar reperfusión (PCI/Trombolisis)', 'Enviar a fisioterapia', 'Iniciar antibióticos'], 1, category="ECG Básico"),
            QuizQuestion(
                '¿Cuál es la derivación habitual para detectar fibrilación auricular?',
                ['II', 'V1', 'aVR', 'V6'], 0, category="Arritmias",
                explanation="La derivación II es útil para ver el ritmo auricular y la onda P.",
            ),
            QuizQuestion(
                '¿Qué mide principalmente una señal PPG?',
                ['Actividad eléctrica', 'Volumen sanguíneo periférico', 'Presión arterial', 'Temperatura corporal'], 1, category="Otras señales",
                explanation="PPG mide cambios en el volumen de sangre en el lecho vascular.",
            ),
        ],
    }

    questions = pool.get(topic, pool['ecg_basics'])
    if lesson is not None:
        questions = [q for q in questions if q.category == lesson]

    if level == 'basic':
        count = min(5, len(questions))
    elif level == 'intermediate':
        count = min(8, len(questions))
    else:
        # Fusión Education+Academia, Capa 1 (2026-07-13): antes tope fijo de 12
        # — con el pool creciendo a 16 tras sumar las 2 preguntas rescatadas,
        # ese tope dejaba las últimas 2 (justo las rescatadas) inalcanzables
        # incluso en modo avanzado. "Avanzado" ahora significa "todo lo
        # disponible en este filtro", sin un número mágico que quede
        # desactualizado cada vez que el banco crece.
        count = len(questions)

    # Select first `count` questions (deterministic for now). Could randomize later.
    selected = {i: questions[i] for i in range(count)}
    return selected


@dataclass
class PersistenceMixin:
    """Mixin providing save/load helpers for LearningEngine using rural_mode."""

    def save_progress_local(self, student_id: str) -> None:
        try:
            rural_mode.save_progress(student_id, self.progress)
        except Exception:
            pass

    def load_progress_local(self, student_id: str) -> Optional[Dict[str, Any]]:
        try:
            data = rural_mode.load_progress(student_id)
            if data:
                self.progress.update(data)
                return data
        except Exception:
            return None
        return None
