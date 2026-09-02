"""Support tools for rural health, offline mode, and low-resource operation."""
from .offline_support import LocalPatientDatabase, generate_pdf_report

__all__ = ['LocalPatientDatabase', 'generate_pdf_report']
