"""Learning engine: orchestrates lessons, quizzes and scoring for students."""
from __future__ import annotations
from typing import List, Dict, Any
from dataclasses import dataclass, field
from typing import Optional

try:
    from educational import rural_mode
    from educational.quiz_bank import ACADEMIA_QUESTIONS, QuizQuestion
except Exception:
    # local import path fallback
    from . import rural_mode
    from .quiz_bank import ACADEMIA_QUESTIONS, QuizQuestion

# 2026-11-14 (Art. I): `QuizQuestion` y el banco de Academia viven en `educational/quiz_bank.py`,
# cada pregunta con su explicación y su fuente (antes las 14 originales no tenían ni una ni otra, y
# varias tenían errores: ver CHANGELOG.md). Se reexportan aquí para no romper a quien los importa.


@dataclass
class LearningEngine:
    student_id: str
    progress: Dict[str, Any] = field(default_factory=dict)
    score: float = 0.0  # promedio de todos los cuestionarios enviados
    quizzes_submitted: int = 0

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
        # 2026-11-14: antes `(self.score + score) / 2 if self.score else score` -- un 0 % previo se
        # tomaba como «sin cuestionarios» y se perdía, y el resto era una media de pares, no el promedio.
        self.score = (self.score * self.quizzes_submitted + score) / (self.quizzes_submitted + 1)
        self.quizzes_submitted += 1
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
    # El banco vive en `educational/quiz_bank.py` (2026-11-14), con la fuente de cada respuesta.
    # Las 2 preguntas rescatadas de src/education/learning.py (Capa 1, 2026-07-13) siguen ahí,
    # corregidas: la de FA preguntaba por «la derivación habitual» (II), que no es como la define
    # la guía ESC 2024.
    pool: Dict[str, List[QuizQuestion]] = {'ecg_basics': ACADEMIA_QUESTIONS}

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
