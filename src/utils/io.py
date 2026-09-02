"""I/O utilities for JSON and clinical artifacts."""

import json
from pathlib import Path
from typing import Any, Dict


def save_json(path: str, data: Dict[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def load_json(path: str) -> Dict[str, Any]:
    with open(path, 'r', encoding='utf-8') as file:
        return json.load(file)
