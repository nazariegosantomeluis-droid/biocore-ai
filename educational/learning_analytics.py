"""Mejora continua de los cuestionarios con aprendizaje automático local (2026-11-16).

Nada sale de la computadora: las respuestas se guardan en una base SQLite local (`DEFAULT_DB_PATH`, fuera de git) y
los modelos se ajustan aquí mismo. El modelo no cambia el banco de preguntas: solo señala qué revisar y qué practicar.
Corregir una pregunta sigue siendo trabajo de una persona, con su fuente.

- `record_answer` / `record_report`: cada respuesta (banco, pregunta, opción elegida, acierto, intento, estudiante) y
  cada reporte de un problema con una pregunta.
- `item_statistics`: análisis clásico de ítems para revisar el banco. Por pregunta: índice de dificultad (proporción
  de aciertos) y discriminación (correlación punto-biserial corregida: la pregunta contra el resto del mismo
  intento). Cortes de Ali & Ruit 2015: dificultad moderada entre 0.4 y 0.8; con una punto-biserial menor de 0.2 la
  pregunta separa poco a quien sabe de quien no y se marca para revisión. Criterio BIOCORE, sin cita: una
  discriminación negativa (quien sabe más la falla más) o un distractor que el grupo alto elige más que la opción
  marcada como correcta piden revisar la clave. Con pocos datos la discriminación es puro ruido (medido: con 120
  respuestas, 1 de 11 preguntas buenas quedaba por debajo de 0.2 por azar), así que solo se marca cuando el
  intervalo de confianza de 95 % (transformación z de Fisher, aproximada) queda entero por debajo del corte, y un
  distractor solo cuenta si gana con una prueba binomial (p < 0.05). Medido así, en 40 simulaciones de 20 a 100
  estudiantes: de 0 a 2 de 110 preguntas buenas marcadas por grupo de 10, y la clave mal puesta encontrada en 7 a
  10 de 10. Con menos de `MIN_RESPONSES` respuestas no se calcula nada.
- `fit_elo`: el sistema de Elo para educación (Pelánek 2016): P(acierto) = 1 / (1 + e^−(θ − d)), con θ la habilidad
  del estudiante en la categoría de la pregunta y d la dificultad de la pregunta; tras cada respuesta,
  θ += K·(acierto − P) y d += K·(P − acierto), con K = a / (1 + b·n) y n las respuestas previas (a = 1, b = 0.05: los
  valores de ejemplo del artículo). Es el mismo modelo logístico de Rasch, ajustado en línea.
- `suggest_questions`: preguntas cuya probabilidad estimada de acierto queda más cerca de 75 %, la tasa objetivo de
  uno de los sistemas que describe Pelánek 2016. El 75 % es una elección de BIOCORE, no un óptimo demostrado.
"""

from __future__ import annotations

import hashlib
import math
import sqlite3
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from scipy.stats import binomtest

ALI_RUIT_2015 = (
    "Ali SH, Ruit KG. The impact of item flaws, testing at low cognitive level, and low distractor functioning on "
    "multiple-choice question quality. Perspect Med Educ 2015;4(5):244–251. doi:10.1007/s40037-015-0212-x"
)
PELANEK_2016 = (
    "Pelánek R. Applications of the Elo rating system in adaptive educational systems. Comput Educ 2016;98:169–179. "
    "doi:10.1016/j.compedu.2016.03.017"
)

DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "local" / "biocore_learning.db"

# Análisis de ítems
EASY_ABOVE = 0.8                 # Ali & Ruit 2015: más de 80 % de aciertos, «demasiado fácil»
HARD_BELOW = 0.4                 # Ali & Ruit 2015: menos de 40 %, «demasiado difícil»
LOW_DISCRIMINATION = 0.2         # Ali & Ruit 2015: punto-biserial < 0.2, revisar
MIN_RESPONSES = 20               # heurística BIOCORE: con menos, los índices son ruido
MIN_PAIRS = 10                   # heurística BIOCORE: intentos con la pregunta y al menos otra
CONFIDENCE_Z = 1.96              # intervalo de 95 % para la discriminación
DISTRACTOR_ALPHA = 0.05          # prueba binomial de una cola para el distractor que gana

# Elo (Pelánek 2016)
ELO_A, ELO_B = 1.0, 0.05
TARGET_SUCCESS = 0.75

FLAG_TEXT = {
    "clave": "Revisar la clave: quienes van mejor en el resto del intento la fallan más (discriminación negativa).",
    "distractor": "Revisar la clave: el grupo alto eligió más una opción incorrecta que la marcada como correcta.",
    "discrimina_poco": "Separa poco a quien sabe de quien no (punto-biserial claramente menor de 0.2): revisar la redacción.",
    "reportada": "Alguien reportó un problema con esta pregunta.",
    "dificil": "Difícil: menos de 40 % de aciertos.",
    "facil": "Fácil: más de 80 % de aciertos.",
}
REVIEW_FLAGS = ("clave", "distractor", "discrimina_poco", "reportada")      # piden revisión; las otras informan

_SCHEMA = """
CREATE TABLE IF NOT EXISTS questions (
    question_id TEXT PRIMARY KEY, bank TEXT NOT NULL, category TEXT, prompt TEXT NOT NULL,
    correct_choice TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, learner TEXT NOT NULL, bank TEXT NOT NULL,
    question_id TEXT NOT NULL, category TEXT, attempt TEXT NOT NULL, chosen TEXT NOT NULL, correct INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, learner TEXT NOT NULL, bank TEXT NOT NULL,
    question_id TEXT NOT NULL, text TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_answers_question ON answers (question_id);
CREATE INDEX IF NOT EXISTS ix_answers_learner ON answers (learner);
"""


def question_id(bank: str, prompt: str) -> str:
    """Identificador estable de una pregunta: si cambia el enunciado, es otra pregunta (y sus datos empiezan de cero)."""
    return hashlib.sha256(f"{bank}|{prompt}".encode("utf-8")).hexdigest()[:16]


def new_attempt() -> str:
    return uuid.uuid4().hex


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect(path: Optional[Path] = None) -> sqlite3.Connection:
    path = Path(path or DEFAULT_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.executescript(_SCHEMA)
    return conn


def _remember_question(conn: sqlite3.Connection, bank: str, question) -> str:
    qid = question_id(bank, question.prompt)
    conn.execute("INSERT OR IGNORE INTO questions VALUES (?, ?, ?, ?, ?)",
                 (qid, bank, question.category, question.prompt, question.correct_choice))
    return qid


def record_answer(bank: str, question, chosen: str, attempt: str, learner: str,
                  path: Optional[Path] = None) -> None:
    """Una respuesta. `question` es un `QuizQuestion`; el acierto lo decide el banco (`is_correct`), no el modelo."""
    with connect(path) as conn:
        qid = _remember_question(conn, bank, question)
        conn.execute("INSERT INTO answers (ts, learner, bank, question_id, category, attempt, chosen, correct) "
                     "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                     (_now(), learner, bank, qid, question.category, attempt, chosen,
                      int(question.is_correct(chosen))))


def record_report(bank: str, question, text: str, learner: str, path: Optional[Path] = None) -> None:
    text = (text or "").strip()
    if not text:
        raise ValueError("El reporte está vacío.")
    with connect(path) as conn:
        qid = _remember_question(conn, bank, question)
        conn.execute("INSERT INTO reports (ts, learner, bank, question_id, text) VALUES (?, ?, ?, ?, ?)",
                     (_now(), learner, bank, qid, text[:2000]))


@dataclass(frozen=True)
class Answer:
    learner: str
    bank: str
    question_id: str
    category: str
    attempt: str
    chosen: str
    correct: int


def load_answers(path: Optional[Path] = None, bank: Optional[str] = None) -> List[Answer]:
    """Todas las respuestas, en el orden en que llegaron."""
    query = "SELECT learner, bank, question_id, COALESCE(category, ''), attempt, chosen, correct FROM answers"
    args: Tuple = ()
    if bank is not None:
        query, args = query + " WHERE bank = ?", (bank,)
    with connect(path) as conn:
        return [Answer(*row) for row in conn.execute(query + " ORDER BY id", args)]


def load_questions(path: Optional[Path] = None) -> Dict[str, dict]:
    with connect(path) as conn:
        rows = conn.execute("SELECT question_id, bank, category, prompt, correct_choice FROM questions").fetchall()
    return {r[0]: {"bank": r[1], "category": r[2], "prompt": r[3], "correct_choice": r[4]} for r in rows}


def load_reports(path: Optional[Path] = None) -> Dict[str, List[str]]:
    reports: Dict[str, List[str]] = defaultdict(list)
    with connect(path) as conn:
        for qid, text in conn.execute("SELECT question_id, text FROM reports ORDER BY id"):
            reports[qid].append(text)
    return dict(reports)


# ---------------------------------------------------------------- análisis de ítems
@dataclass
class ItemStats:
    question_id: str
    responses: int
    difficulty: Optional[float]               # proporción de aciertos (índice de dificultad)
    discrimination: Optional[float]           # punto-biserial corregida
    pairs: int                                # intentos que entraron a la discriminación
    discrimination_ci: Optional[Tuple[float, float]] = None     # 95 %, z de Fisher (aproximado)
    choice_counts: Dict[str, int] = field(default_factory=dict)
    flags: Tuple[str, ...] = ()
    reports: Tuple[str, ...] = ()

    @property
    def needs_review(self) -> bool:
        return any(flag in REVIEW_FLAGS for flag in self.flags)


def _pearson(xs: Sequence[float], ys: Sequence[float]) -> Optional[float]:
    n = len(xs)
    if n < 2:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / math.sqrt(sxx * syy)


def fisher_interval(r: float, n: int, z: float = CONFIDENCE_Z) -> Tuple[float, float]:
    """Intervalo de confianza aproximado de una correlación (transformación z de Fisher)."""
    if n <= 3:
        return -1.0, 1.0
    center = math.atanh(max(-0.999999, min(0.999999, r)))
    half = z / math.sqrt(n - 3)
    return math.tanh(center - half), math.tanh(center + half)


def _first_responses(answers: Iterable[Answer]) -> Dict[Tuple[str, str], Answer]:
    """La primera respuesta de cada pregunta en cada intento (volver a verificar no cuenta)."""
    first: Dict[Tuple[str, str], Answer] = {}
    for answer in answers:
        first.setdefault((answer.attempt, answer.question_id), answer)
    return first


def item_statistics(answers: Sequence[Answer], reports: Optional[Dict[str, List[str]]] = None,
                    correct_choices: Optional[Dict[str, str]] = None,
                    min_responses: int = MIN_RESPONSES, min_pairs: int = MIN_PAIRS) -> Dict[str, ItemStats]:
    """Índices por pregunta. `correct_choices` (id → opción correcta) hace falta para revisar los distractores."""
    reports = reports or {}
    correct_choices = correct_choices or {}
    first = _first_responses(answers)
    by_attempt: Dict[str, Dict[str, Answer]] = defaultdict(dict)
    for (attempt, qid), answer in first.items():
        by_attempt[attempt][qid] = answer
    by_question: Dict[str, List[Answer]] = defaultdict(list)
    for answer in first.values():
        by_question[answer.question_id].append(answer)

    stats: Dict[str, ItemStats] = {}
    for qid in set(by_question) | set(reports):
        own = by_question.get(qid, [])
        counts: Dict[str, int] = defaultdict(int)
        for answer in own:
            counts[answer.chosen] += 1
        n = len(own)
        item = ItemStats(question_id=qid, responses=n, difficulty=None, discrimination=None, pairs=0,
                         choice_counts=dict(counts), reports=tuple(reports.get(qid, ())))
        flags: List[str] = ["reportada"] if item.reports else []
        if n >= min_responses:
            item.difficulty = sum(a.correct for a in own) / n
            if item.difficulty < HARD_BELOW:
                flags.append("dificil")
            elif item.difficulty > EASY_ABOVE:
                flags.append("facil")
            xs, ys, chosen = [], [], []
            for attempt_answers in by_attempt.values():
                if qid not in attempt_answers or len(attempt_answers) < 2:
                    continue
                others = [a.correct for k, a in attempt_answers.items() if k != qid]
                xs.append(attempt_answers[qid].correct)
                ys.append(sum(others) / len(others))
                chosen.append(attempt_answers[qid].chosen)
            item.pairs = len(xs)
            if item.pairs >= min_pairs:
                item.discrimination = _pearson(xs, ys)
                if item.discrimination is not None:
                    item.discrimination_ci = fisher_interval(item.discrimination, item.pairs)
                    if item.discrimination_ci[1] < 0:
                        flags.append("clave")
                    elif item.discrimination_ci[1] < LOW_DISCRIMINATION:
                        flags.append("discrimina_poco")
                key = correct_choices.get(qid)
                if key is not None:
                    cut = sorted(ys)[len(ys) // 2]                       # mitad alta por el resto del intento
                    upper: Dict[str, int] = defaultdict(int)
                    for choice, rest in zip(chosen, ys):
                        if rest >= cut:
                            upper[choice] += 1
                    key_count = upper.get(key, 0)
                    if any(count > key_count and binomtest(count, count + key_count, 0.5,
                                                           alternative="greater").pvalue < DISTRACTOR_ALPHA
                           for choice, count in upper.items() if choice != key):
                        flags.append("distractor")
        item.flags = tuple(flags)
        stats[qid] = item
    return stats


# ---------------------------------------------------------------- Elo (Pelánek 2016)
def logistic(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def uncertainty(n: int) -> float:
    return ELO_A / (1.0 + ELO_B * n)


@dataclass
class EloState:
    skills: Dict[Tuple[str, str], float] = field(default_factory=dict)        # (estudiante, categoría) → θ
    skill_counts: Dict[Tuple[str, str], int] = field(default_factory=dict)
    difficulties: Dict[str, float] = field(default_factory=dict)             # pregunta → d
    difficulty_counts: Dict[str, int] = field(default_factory=dict)

    def predict(self, learner: str, category: str, qid: str) -> float:
        return logistic(self.skills.get((learner, category), 0.0) - self.difficulties.get(qid, 0.0))

    def update(self, learner: str, category: str, qid: str, correct: int) -> None:
        key = (learner, category)
        expected = self.predict(learner, category, qid)
        n_skill, n_item = self.skill_counts.get(key, 0), self.difficulty_counts.get(qid, 0)
        self.skills[key] = self.skills.get(key, 0.0) + uncertainty(n_skill) * (correct - expected)
        self.difficulties[qid] = self.difficulties.get(qid, 0.0) + uncertainty(n_item) * (expected - correct)
        self.skill_counts[key] = n_skill + 1
        self.difficulty_counts[qid] = n_item + 1


def fit_elo(answers: Iterable[Answer]) -> EloState:
    """Recorre las respuestas en orden; solo cuenta la primera de cada pregunta en cada intento."""
    state = EloState()
    for answer in _first_responses(answers).values():
        state.update(answer.learner, answer.category, answer.question_id, answer.correct)
    return state


def learner_summary(state: EloState, learner: str) -> List[Tuple[str, float, int]]:
    """(categoría, probabilidad estimada de acertar una pregunta de dificultad media, respuestas), de la más débil
    a la más fuerte."""
    rows = [(category, logistic(theta), state.skill_counts.get((who, category), 0))
            for (who, category), theta in state.skills.items() if who == learner]
    return sorted(rows, key=lambda row: row[1])


def suggest_questions(state: EloState, learner: str, questions: Sequence, bank: str, n: int = 5,
                      target: float = TARGET_SUCCESS) -> List:
    """Las `n` preguntas con probabilidad estimada de acierto más cerca de `target`. A igualdad, las que tienen menos
    respuestas en total (su dificultad es la más incierta)."""
    def key(question):
        qid = question_id(bank, question.prompt)
        p = state.predict(learner, question.category, qid)
        return abs(p - target), state.difficulty_counts.get(qid, 0)
    return sorted(questions, key=key)[:n]
