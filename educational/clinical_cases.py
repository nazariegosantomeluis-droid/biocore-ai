"""Virtual patients and clinical case scenarios for training exercises."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, List, Tuple
import numpy as np


@dataclass
class VirtualPatient:
    patient_id: str
    age: int
    sex: str
    history: str
    signals: Dict[str, Tuple[np.ndarray, int]]
    true_diagnosis: str


def sample_cases() -> List[VirtualPatient]:
    """Return a short list of example virtual patient cases used in lessons."""
    from educational.ecg_academy import generate_synthetic_ecg
    cases: List[VirtualPatient] = []

    sig1, fs1 = generate_synthetic_ecg('stemi', fs=250, duration=10.0) if True else generate_synthetic_ecg('normal')
    cases.append(VirtualPatient(
        patient_id='P001',
        age=58,
        sex='M',
        history='Dolor torácico agudo',
        signals={'ecg': (sig1, fs1)},
        true_diagnosis='STEMI'
    ))

    sig2, fs2 = generate_synthetic_ecg('afib', fs=250, duration=10.0)
    cases.append(VirtualPatient(
        patient_id='P002',
        age=72,
        sex='F',
        history='Palpitaciones y mareo',
        signals={'ecg': (sig2, fs2)},
        true_diagnosis='Fibrilación auricular'
    ))

    return cases
