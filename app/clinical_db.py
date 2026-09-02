import sqlite3
import json
from pathlib import Path
from typing import Dict, List, Any

DB_PATH = Path(__file__).resolve().parents[1] / 'clinical_states.db'

def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS patient_states (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id TEXT,
            timestamp TEXT,
            data TEXT
        )
    ''')
    conn.commit()
    conn.close()


def save_patient_state(patient_id: str, state: Dict[str, Any], timestamp: str) -> int:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('INSERT INTO patient_states (patient_id, timestamp, data) VALUES (?, ?, ?)',
                (patient_id, timestamp, json.dumps(state)))
    conn.commit()
    rowid = cur.lastrowid
    conn.close()
    return rowid


def list_patient_states(limit: int = 50) -> List[Dict[str, Any]]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT id, patient_id, timestamp, data FROM patient_states ORDER BY id DESC LIMIT ?', (limit,))
    rows = cur.fetchall()
    conn.close()
    result = []
    for r in rows:
        try:
            data = json.loads(r[3])
        except Exception:
            data = {}
        result.append({'id': r[0], 'patient_id': r[1], 'timestamp': r[2], 'data': data})
    return result


def load_patient_state(row_id: int) -> Dict[str, Any]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT id, patient_id, timestamp, data FROM patient_states WHERE id = ?', (row_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return {}
    try:
        data = json.loads(row[3])
    except Exception:
        data = {}
    return {'id': row[0], 'patient_id': row[1], 'timestamp': row[2], 'data': data}
