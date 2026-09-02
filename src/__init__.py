"""
Biomedical Signal Visualizer
A professional educational and clinical ECG/HRV analysis platform.

Modules:
--------
signal_processing : ECG filtering, R-peak detection, RR interval computation
feature_extraction : HRV features, power spectral density analysis
machine_learning : Model training and arrhythmia classification
interpretability : Physiological interpretation of detected features
visualization : Professional clinical ECG and HRV visualization utilities
ecg_education : Educational platform for ECG interpretation training
risk_analysis : Clinical risk assessment and early warning detection
advanced_hrv : Advanced time-domain, frequency-domain, and non-linear HRV analysis
"""

from .signal_processing import (
    bandpass_filter,
    detect_r_peaks,
    compute_rr_intervals
)

from .feature_extraction import (
    compute_psd,
    extract_features
)

from .machine_learning import (
    train_model,
    predict_arrhythmia
)

from .interpretability import (
    interpret_features,
    generate_clinical_report
)

from .visualization import (
    plot_ecg_signal,
    plot_rr_intervals,
    plot_psd,
    plot_feature_comparison
)

from .ecg_education import (
    ECGEducationPlatform,
    create_educational_report
)

from .risk_analysis import (
    AnalisisRiesgoClinico,
    generar_reporte_riesgo_completo
)

from .advanced_hrv import (
    AnalisisHRVAvanzado,
    generar_reporte_hrv_completo
)

__version__ = "2.0.0"
__author__ = "Biomedical AI Lab"
__status__ = "Educational & Clinical"

__all__ = [
    'bandpass_filter',
    'detect_r_peaks',
    'compute_rr_intervals',
    'compute_psd',
    'extract_features',
    'train_model',
    'predict_arrhythmia',
    'interpret_features',
    'generate_clinical_report',
    'plot_ecg_signal',
    'plot_rr_intervals',
    'plot_psd',
    'plot_feature_comparison',
    'ECGEducationPlatform',
    'create_educational_report',
    'AnalisisRiesgoClinico',
    'generar_reporte_riesgo_completo',
    'AnalisisHRVAvanzado',
    'generar_reporte_hrv_completo'
]
