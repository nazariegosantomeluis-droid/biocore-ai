"""
__init__.py - INICIALIZADOR DE UTILIDADES
===========================================
Importa y exporta utilidades de la aplicación.
"""

from .data_generator import (
    DataGenerator,
    generate_ecg_signal,
    generate_eeg_signal,
    generate_emg_signal,
    generate_sample_patient,
    generate_measurement_history
)

__all__ = [
    'DataGenerator',
    'generate_ecg_signal',
    'generate_eeg_signal',
    'generate_emg_signal',
    'generate_sample_patient',
    'generate_measurement_history'
]

# Backwards-compatibility: if a legacy module `app/utils.py` exists (single-file
# utils), import it and re-export its public symbols so `import app.utils` keeps
# providing the expected helpers (safe_import_plotly, render_view_selector, etc.).
try:
    import importlib.util
    import pathlib
    import sys

    legacy_path = pathlib.Path(__file__).parent.parent / 'utils.py'
    if legacy_path.exists():
        spec = importlib.util.spec_from_file_location('app._legacy_utils', str(legacy_path))
        legacy = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(legacy)

        # Re-export public names from the legacy module
        for name in dir(legacy):
            if not name.startswith('_') and name not in globals():
                globals()[name] = getattr(legacy, name)
                __all__.append(name)
except Exception:
    # Silently ignore if legacy utils file is not present or fails to load
    pass
