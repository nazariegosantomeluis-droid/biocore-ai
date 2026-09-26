"""
Supermódulos para re-exportar componentes y utilidades comunes.
Permite importar un conjunto coherente desde `app.supermodules`.

NOTA (2026-08-19, Art. I -- Capa 3): las 6 clases *UI que este módulo
re-exportaba desde `app.components` (CardiacUI, NeurologyUI,
MusculoskeletalUI, RespiratoryUI, MetabolismUI, AlertsUI/ReportGenerator)
se retiraron -- `app.components` quedó vacío. Eran la UI de un hub
"Specialties" archivado, sin llamadores vivos, con varios métodos que
fabricaban diagnósticos/confianzas de IA. Ver CHANGELOG.md.
"""

from app.utils.data_generator import (
    generate_sample_patient, generate_measurement_history,
    generate_ecg_signal, generate_eeg_signal, generate_emg_signal,
    generate_respiratory_signal, generate_metabolic_profile
)

import importlib

# Re-export selected helpers from app.utils (module)
app_utils = importlib.import_module('app.utils')

safe_import_plotly = app_utils.safe_import_plotly
safe_import_ecg_modules = app_utils.safe_import_ecg_modules
safe_import_src_modules = app_utils.safe_import_src_modules
safe_import_multisensor = app_utils.safe_import_multisensor
FallbackBiosignalChannel = app_utils.FallbackBiosignalChannel
FallbackMultisensoralRecord = app_utils.FallbackMultisensoralRecord
# estimate_ecg_heart_rate retirada (Bug 2 del ECG, 2026-09-26) -- ver
# app/utils.py y CHANGELOG.md. Reemplazada por
# `ECGAnalyzer.detect_r_peaks_tkeo()`, importado directo donde hace falta
# (mismo patrón que generate_demo_ecg_signal, retirada por Fase 5B arriba).
estimate_respiration_rate = app_utils.estimate_respiration_rate
# generate_demo_ecg_signal retirada (Fase 5B, 2026-08-30) -- ver
# app/utils.py y CHANGELOG.md. Reemplazada por DynamicECGGenerator
# (src/signals/ecg/dynamic_ecg_generator.py), importada directo donde
# hacía falta -- no se re-exporta aquí (los otros generadores demo de
# este módulo no son clases, así que el patrón de reexport plano no
# encaja igual; se deja como import explícito en cada llamador).
generate_demo_ppg_signal = app_utils.generate_demo_ppg_signal
generate_demo_spo2_signal = app_utils.generate_demo_spo2_signal
generate_demo_respiration_signal = app_utils.generate_demo_respiration_signal
generate_demo_temperature_signal = app_utils.generate_demo_temperature_signal
generate_demo_bp_signal = app_utils.generate_demo_bp_signal
plot_signal_matplotlib = app_utils.plot_signal_matplotlib
plot_clinical_ecg_safe = app_utils.plot_clinical_ecg_safe
display_error_message = app_utils.display_error_message
display_info_message = app_utils.display_info_message
display_success_message = app_utils.display_success_message
display_warning_message = app_utils.display_warning_message
init_session_state_key = app_utils.init_session_state_key
cache_signal_in_session = app_utils.cache_signal_in_session
get_cached_signal = app_utils.get_cached_signal
render_metric_explained = app_utils.render_metric_explained
render_view_selector = app_utils.render_view_selector
render_scientific_discovery_layer = app_utils.render_scientific_discovery_layer
render_discovery_lab = app_utils.render_discovery_lab
validate_signal = app_utils.validate_signal
create_metric_row = app_utils.create_metric_row
create_section = app_utils.create_section
create_two_column_layout = app_utils.create_two_column_layout
get_analyzer_singleton = app_utils.get_analyzer_singleton
cache_mitbih_record_list = app_utils.cache_mitbih_record_list

__all__ = [
    'generate_sample_patient', 'generate_measurement_history',
    'generate_ecg_signal', 'generate_eeg_signal', 'generate_emg_signal',
    'generate_respiratory_signal', 'generate_metabolic_profile'
]

__all__.extend([
    'safe_import_plotly', 'safe_import_ecg_modules',
    'safe_import_src_modules', 'safe_import_multisensor', 'FallbackBiosignalChannel',
    'FallbackMultisensoralRecord', 'estimate_respiration_rate',
    'generate_demo_ppg_signal', 'generate_demo_spo2_signal',
    'generate_demo_respiration_signal', 'generate_demo_temperature_signal', 'generate_demo_bp_signal',
    'plot_signal_matplotlib', 'plot_clinical_ecg_safe', 'display_error_message',
    'display_info_message', 'display_success_message', 'display_warning_message',
    'init_session_state_key', 'cache_signal_in_session', 'get_cached_signal',
    'render_metric_explained', 'render_view_selector', 'render_scientific_discovery_layer',
    'render_discovery_lab', 'validate_signal', 'create_metric_row', 'create_section',
    'create_two_column_layout', 'get_analyzer_singleton', 'cache_mitbih_record_list'
])
