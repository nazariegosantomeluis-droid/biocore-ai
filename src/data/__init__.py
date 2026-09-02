"""Real data loaders for biomedical signals."""
from .real_data_loader import (
    load_biomedical_signal,
    validate_signal,
    assess_signal_quality,
    normalize_sampling_rate,
)

__all__ = [
    'load_biomedical_signal',
    'validate_signal',
    'assess_signal_quality',
    'normalize_sampling_rate',
]
