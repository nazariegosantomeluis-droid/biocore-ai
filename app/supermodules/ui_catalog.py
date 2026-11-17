"""Catálogo de la interfaz Duolingo + Apple (2026-11-17): órganos, temas y la ruta de cada órgano.

Solo enlaza contenido que ya existe: los temas son los `TheoryTopic` firmados de `learn_theory.py`, las preguntas salen
de los bancos de `educational/quiz_bank.py` y los nodos de la ruta apuntan a páginas del menú. Nada de texto médico
nuevo. Los conceptos de la sesión son los 8 de `app.utils.session_learning.CONCEPTS`; un tema sin concepto claro no
registra respuestas (None).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from app.supermodules import learn_theory as LT


@dataclass(frozen=True)
class Organ:
    key: str
    label: str
    icon: str                      # ícono Material de Streamlit (sin emoji)
    domain: Optional[str]          # dominio del UPS; None = el UPS no tiene ese dominio
    recording: Optional[str]       # registro real de data/reference_signals para la sección «Información»


ORGANS: Tuple[Organ, ...] = (
    Organ("corazon", "Corazón", ":material/cardiology:", "cardiovascular", "ptb_s0010"),
    Organ("respiracion", "Respiración", ":material/pulmonology:", "respiratory", None),
    Organ("cerebro", "Cerebro", ":material/neurology:", "neurological", "cap_n16"),
    Organ("musculo", "Músculo", ":material/exercise:", "muscular", None),
    Organ("autonomo", "Sistema autónomo", ":material/monitor_heart:", None, None),
)
ORGAN_BY_KEY = {o.key: o for o in ORGANS}


@dataclass(frozen=True)
class Topic:
    key: str
    theory: LT.TheoryTopic
    organ: str
    concept: Optional[str]         # concepto de session_learning; None = no se registra
    quiz_bank: Optional[str]       # "academia" | "eeg" | None
    quiz_category: Optional[str]   # categoría de ACADEMIA_QUESTIONS
    calculator: Optional[str]      # "fc" | "qtc" | "news2" | None
    lab: Optional[str]             # url_path del laboratorio relacionado


TOPICS: Tuple[Topic, ...] = (
    Topic("ecg_papel", LT.SIGNED_ECG_PAPER, "corazon", None, "academia", "ECG Básico", "fc", "ecg"),
    Topic("fc", LT.SIGNED_HEART_RATE, "corazon", "frecuencia_cardiaca", "academia", "ECG Básico", "fc", "ecg"),
    Topic("ondas", LT.SIGNED_WAVES, "corazon", "ritmo_y_conduccion", "academia", "ECG Básico", "qtc", "ecg"),
    Topic("doce", LT.SIGNED_TWELVE_LEADS, "corazon", "derivaciones_e_isquemia", "academia", "ECG 12-derivaciones",
          None, "ecg"),
    Topic("isquemia", LT.SIGNED_ISCHEMIA, "corazon", "derivaciones_e_isquemia", "academia", "ECG 12-derivaciones",
          None, "ecg"),
    Topic("news2", LT.SIGNED_NEWS2, "respiracion", "news2", None, None, "news2", "calculadoras"),
    Topic("patrones", LT.PATTERNS, "respiracion", "respiracion_y_apnea", None, None, "news2", "respiratorio"),
    Topic("eeg_bandas", LT.EEG_BANDS, "cerebro", None, "eeg", None, None, "eeg"),
)
TOPIC_BY_KEY = {t.key: t for t in TOPICS}

# Ruta de cada órgano (estilo Duolingo): (rótulo, "tema" | "pagina", destino).
PATHS = {
    "corazon": (("El ECG en papel", "tema", "ecg_papel"), ("Frecuencia cardiaca", "tema", "fc"),
                ("Ondas e intervalos", "tema", "ondas"), ("Laboratorio de ECG", "pagina", "ecg"),
                ("Desafío de 12 derivaciones", "pagina", "desafio-ecg")),
    "respiracion": (("NEWS2", "tema", "news2"), ("Patrones respiratorios", "tema", "patrones"),
                    ("Laboratorio respiratorio", "pagina", "respiratorio"),
                    ("Cuestionarios de los laboratorios", "pagina", "cuestionarios")),
    "cerebro": (("Bandas del EEG", "tema", "eeg_bandas"), ("Laboratorio de EEG", "pagina", "eeg")),
    "musculo": (("Laboratorio de EMG", "pagina", "emg"),),
    "autonomo": (("Variabilidad cardíaca", "pagina", "hrv"), ("Gemelo digital", "pagina", "gemelo")),
}

SELECTED_ORGAN_KEY = "bc_selected_organ"
SELECTED_TOPIC_KEY = "bc_selected_topic"


def topics_for(organ: str) -> Tuple[Topic, ...]:
    return tuple(t for t in TOPICS if t.organ == organ)


def quiz_questions(topic: Topic, limit: int = 3) -> list:
    """Las preguntas con fuente del banco del tema (máximo `limit`); lista vacía si el tema no tiene banco."""
    from educational.quiz_bank import ACADEMIA_QUESTIONS, EEG_QUESTIONS

    if topic.quiz_bank == "academia":
        pool = [q for q in ACADEMIA_QUESTIONS if q.category == topic.quiz_category]
    elif topic.quiz_bank == "eeg":
        pool = list(EEG_QUESTIONS)
    else:
        pool = []
    return pool[:limit]
