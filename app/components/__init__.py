"""
__init__.py - INICIALIZADOR DE COMPONENTES
============================================
Paquete vaciado (2026-08-19, Art. I -- Capa 3 de honestidad). Contenía 6
clases *UI (CardiacUI, NeurologyUI, MusculoskeletalUI, RespiratoryUI,
MetabolismUI, AlertsUI/ReportGenerator), todas construidas para un hub
"Specialties" que se archivó en algún punto anterior a esta campaña
(`_archive/app/supermodules/specialties/`). Al morir ese hub, TODAS sus
clases quedaron sin un solo llamador vivo -- ni siquiera sus métodos
honestos (los que solo graficaban datos reales sin fabricar nada)
sobrevivían fuera de `_archive/`.

Además, varias de esas clases contenían métodos que fabricaban hallazgos
clínicos: confidencias de "modelo IA" hardcodeadas por rama de un string
(`display_arrhythmia_detection`, `display_sleep_stage_classification`,
`display_pathology_classification`), diagnósticos/pronósticos por default
silencioso (`ai_results.get('pathology', 'Normal')` y variantes), una
explicación SHAP 100% inventada, y un "historial de alertas" hecho de
`np.random`. Dos censos exhaustivos (ver CHANGELOG.md, 2026-08-19) mapearon
18 miembros de esta familia en todo el repo -- cero vivos en ningún momento.

Este paquete queda intencionalmente vacío en vez de eliminado: preserva el
namespace `app.components` por si algo externo lo importa, sin dejar
ninguna clase fachada disponible para reactivarse por accidente. Si algún
día se reconstruye una UI real de especialidades, debería partir de cero
sobre datos reales del UPS -- no revivir estas clases.

MusculoskeletalUI ya se había eliminado antes, en la misma campaña
(2026-08-19, tanda anterior), con el mismo diagnóstico de cáscara completa.
"""

__all__: list = []
