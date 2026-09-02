import random
from typing import List, Dict


def get_courses() -> List[Dict]:
    """Return a list of available courses and short metadata."""
    return [
        {"id": "cardio-phys", "title": "Fisiología Cardiovascular", "duration_hours": 8},
        {"id": "neuro-phys", "title": "Neurofisiología", "duration_hours": 6},
        {"id": "resp-phys", "title": "Fisiología Respiratoria", "duration_hours": 5},
        {"id": "emg-basics", "title": "EMG: señales y fatiga", "duration_hours": 4},
        {"id": "interpretation", "title": "Interpretación Clínica", "duration_hours": 10},
    ]


def get_case_studies() -> List[Dict]:
    """Return curated clinical case studies for active learning."""
    return [
        {"id": "case-mi", "title": "Infarto agudo de miocardio (caso)", "topics": ["ECG","STEMI","Coronary"]},
        {"id": "case-af", "title": "Fibrilación auricular", "topics": ["ECG","Arrhythmia","Anticoag"]},
        {"id": "case-resp", "title": "Insuficiencia respiratoria aguda", "topics": ["Respiratory","SpO2","Ventilation"]},
    ]


def generate_learning_path(progress: Dict[str, int]) -> List[Dict]:
    """Generate a simple prioritized learning path based on user progress.

    progress: mapping of course keys to percent completion (0-100)
    """
    courses = get_courses()
    # prioritize courses with lowest progress
    sorted_courses = sorted(courses, key=lambda c: progress.get(c['title'].split()[0], 0))
    path = []
    for c in sorted_courses:
        path.append({
            "course_id": c['id'],
            "title": c['title'],
            "recommended_next": random.choice([True, False])
        })
    return path


# lightweight utils used by the main app
def quick_case_summary(case_id: str) -> Dict:
    for c in get_case_studies():
        if c['id'] == case_id:
            return {"id": c['id'], "title": c['title'], "summary": "Resumen clínico breve del caso para estudio."}
    return {"id": case_id, "title": "Caso desconocido", "summary": "No hay información."}
