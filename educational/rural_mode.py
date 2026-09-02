"""Offline utilities for 'Modo Rural'.

Provides simple JSON-based persistence for student progress and small
datasets so the platform can operate without network or cloud services.
"""
from __future__ import annotations
import os
import json
from typing import Any, Dict


LOCAL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'local')
os.makedirs(LOCAL_DIR, exist_ok=True)


def progress_path(student_id: str) -> str:
    safe_id = ''.join(c for c in student_id if c.isalnum() or c in ('_', '-')).strip()
    return os.path.join(LOCAL_DIR, f'progress_{safe_id}.json')


def save_progress(student_id: str, data: Dict[str, Any]) -> None:
    p = progress_path(student_id)
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_progress(student_id: str) -> Dict[str, Any]:
    p = progress_path(student_id)
    if not os.path.exists(p):
        return {}
    with open(p, 'r', encoding='utf-8') as f:
        return json.load(f)
