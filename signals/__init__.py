"""Signals module - Biomedical signal loading and processing."""

__version__ = "2.0"
__author__ = "Biomedical Platform Team"

from .loaders import load_biomedical_data, detect_signal_type, validate_signal

__all__ = ['load_biomedical_data', 'detect_signal_type', 'validate_signal']
