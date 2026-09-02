"""Offline storage and PDF report support for low-resource healthcare."""

import os
import sqlite3
from dataclasses import dataclass
from typing import Dict, Optional

try:
    from fpdf import FPDF
except ImportError:
    FPDF = None  # type: ignore


@dataclass
class LocalPatientDatabase:
    path: str = 'rural_health/patient_history.db'

    def __post_init__(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._create_tables()

    def _create_tables(self):
        cursor = self._conn.cursor()
        cursor.execute(
            'CREATE TABLE IF NOT EXISTS patients (id TEXT PRIMARY KEY, name TEXT, age INTEGER, metadata TEXT)'
        )
        cursor.execute(
            'CREATE TABLE IF NOT EXISTS reports (report_id TEXT PRIMARY KEY, patient_id TEXT, timestamp TEXT, data TEXT)'
        )
        self._conn.commit()

    def add_patient(self, patient_id: str, name: str, age: int, metadata: Optional[str] = None):
        cursor = self._conn.cursor()
        cursor.execute(
            'INSERT OR REPLACE INTO patients (id, name, age, metadata) VALUES (?, ?, ?, ?)',
            (patient_id, name, age, metadata or '')
        )
        self._conn.commit()

    def save_report(self, report_id: str, patient_id: str, timestamp: str, data: str):
        cursor = self._conn.cursor()
        cursor.execute(
            'INSERT OR REPLACE INTO reports (report_id, patient_id, timestamp, data) VALUES (?, ?, ?, ?)',
            (report_id, patient_id, timestamp, data)
        )
        self._conn.commit()

    def get_patient(self, patient_id: str) -> Optional[Dict[str, str]]:
        cursor = self._conn.cursor()
        cursor.execute('SELECT id, name, age, metadata FROM patients WHERE id = ?', (patient_id,))
        row = cursor.fetchone()
        if row:
            return {'id': row[0], 'name': row[1], 'age': row[2], 'metadata': row[3]}
        return None

    def list_reports(self, patient_id: str):
        cursor = self._conn.cursor()
        cursor.execute('SELECT report_id, timestamp, data FROM reports WHERE patient_id = ?', (patient_id,))
        return [{'report_id': row[0], 'timestamp': row[1], 'data': row[2]} for row in cursor.fetchall()]


def generate_pdf_report(patient: Dict[str, str], summary: str, path: str = 'rural_health/report.pdf') -> str:
    if FPDF is None:
        raise ImportError('FPDF no está instalado. Instala fpdf para generar reportes PDF.')

    os.makedirs(os.path.dirname(path), exist_ok=True)
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 12, 'Reporte Biomédico', ln=True)
    pdf.set_font('Arial', '', 12)
    pdf.cell(0, 10, f"Paciente: {patient.get('name', 'N/A')}", ln=True)
    pdf.cell(0, 10, f"Edad: {patient.get('age', 'N/A')}", ln=True)
    pdf.multi_cell(0, 8, summary)
    pdf.output(path)
    return path
