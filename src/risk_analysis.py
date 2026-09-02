"""
Módulo de Análisis de Riesgo Cardiovascular Clínico

Proporciona análisis de patrones de riesgo y banderas rojas
en ECG y métricas HRV.

Nota: NO realiza diagnósticos clínicos. Solo proporciona
"patrones sugestivos" para evaluación clínica posterior.
"""

from typing import Dict, List, Tuple
from dataclasses import dataclass


@dataclass
class RiscoIndicador:
    """Indicador de riesgo clínico."""
    nombre: str
    valor_actual: float
    rango_normal: Tuple[float, float]
    significado: str
    accion_recomendada: str
    requiere_seguimiento: bool


class AnalisisRiesgoClinico:
    """
    Análisis de patrones de riesgo cardiovascular basado en ECG/HRV.
    
    IMPORTANTE: Este análisis NO sustituye evaluación clínica.
    Proporciona "patrones sugestivos de" para médicos.
    """

    @staticmethod
    def detectar_banderas_rojas(
        bpm: float,
        sdnn: float,
        rmssd: float,
        lf_hf: float,
        skewness: float,
        kurtosis: float
    ) -> Dict[str, List[str]]:
        """
        Detecta patrones clínicos potencialmente significativos.
        
        Retorna
        -------
        dict
            Banderas por categoría de riesgo
        """
        banderas = {
            'moderado': [],
            'potencial': [],
            'informativo': []
        }

        # Análisis de frecuencia cardíaca
        if bpm > 110:
            banderas['moderado'].append(
                f'⚠️ Taquicardia pronunciada ({bpm:.0f} bpm):\n'
                '   • Patrón sugestivo de estrés emocional, fiebre o arritmia\n'
                '   • Requiere: EKG de seguimiento, investigar causa'
            )
        elif bpm < 50:
            banderas['moderado'].append(
                f'⚠️ Bradicardia significativa ({bpm:.0f} bpm):\n'
                '   • Patrón sugestivo de disfunción nodo SA o bloqueo AV\n'
                '   • En no-atletas: requiere evaluación'
            )

        # Análisis de variabilidad (SDNN)
        if sdnn < 0.05:
            banderas['moderado'].append(
                f'⚠️ Variabilidad muy baja (SDNN {sdnn:.4f}):\n'
                '   • Patrón sugestivo de:\n'
                '     - Estrés agudo\n'
                '     - Disfunción autonómica\n'
                '     - Riesgo aumentado\n'
                '   • Requiere: evaluación de causas de estrés'
            )
        elif sdnn < 0.08:
            banderas['potencial'].append(
                f'ℹ️ Variabilidad reducida (SDNN {sdnn:.4f}):\n'
                '   • Patrón sugestivo de modulación autonómica alterada'
            )

        # Análisis de tono parasimpático (RMSSD)
        if rmssd < 0.05:
            banderas['moderado'].append(
                f'⚠️ Tono parasimpático muy bajo (RMSSD {rmssd:.4f}):\n'
                '   • Patrón sugestivo de retirada vagal\n'
                '   • Asociado con: estrés mental, recuperación limitada'
            )

        # Análisis del balance autonómico
        if lf_hf > 4.0:
            banderas['moderado'].append(
                f'⚠️ Dominancia simpática pronunciada (LF/HF {lf_hf:.2f}):\n'
                '   • Patrón sugestivo de:\n'
                '     - Estado de "lucha-huida"\n'
                '     - Estrés psicosocial\n'
                '     - Posible riesgo aumentado\n'
                '   • Recomendación: técnicas de relajación, reasesamiento'
            )
        elif lf_hf > 2.5:
            banderas['potencial'].append(
                f'ℹ️ Prevalencia relativa de actividad simpática (LF/HF {lf_hf:.2f}):\n'
                '   • Patrón sugestivo de estrés moderado'
            )

        if lf_hf < 0.5:
            banderas['informativo'].append(
                f'✓ Dominancia vagal (LF/HF {lf_hf:.2f}):\n'
                '   • Patrón sugestivo de estado parasimpático\n'
                '   • Asociado con descanso y recuperación'
            )

        # Análisis de regularidad (Skewness)
        if abs(skewness) > 1.5:
            banderas['potencial'].append(
                f'⚠️ Asimetría pronunciada en distribución RR (Skewness {skewness:.3f}):\n'
                '   • Patrón sugestivo de ritmo irregular\n'
                '   • Requiere: revisión de morfología ECG'
            )

        # Análisis de distribución (Kurtosis)
        if kurtosis > 3:
            banderas['potencial'].append(
                f'ℹ️ Distribución con "colas pesadas" (Kurtosis {kurtosis:.3f}):\n'
                '   • Patrón sugestivo de eventos cardíacos esporádicos'
            )

        return banderas

    @staticmethod
    def calcular_indice_riesgo_compuesto(
        bpm: float,
        sdnn: float,
        rmssd: float,
        lf_hf: float
    ) -> Dict[str, float | str]:
        """
        Calcula un índice de riesgo compuesto (EDUCATIVO SOLAMENTE).
        
        NOTA: Este índice es ilustrativo para fines educativos.
        NO debe usarse para diagnóstico clínico.
        """
        puntuacion = 0

        # Componentes de puntuación
        if bpm > 110 or bpm < 50:
            puntuacion += 30
        elif bpm > 100 or bpm < 60:
            puntuacion += 15

        if sdnn < 0.05:
            puntuacion += 30
        elif sdnn < 0.08:
            puntuacion += 15

        if rmssd < 0.05:
            puntuacion += 20
        elif rmssd < 0.08:
            puntuacion += 10

        if lf_hf > 4:
            puntuacion += 20
        elif lf_hf > 2.5:
            puntuacion += 10

        # Clasificación
        if puntuacion < 20:
            categoria = 'BAJO (patrón favorable)'
            recomendacion = 'Mantener hábitos saludables. Seguimiento anual.'
        elif puntuacion < 40:
            categoria = 'MODERADO'
            recomendacion = 'Evaluación clínica recomendada. Mejorar manejo del estrés.'
        elif puntuacion < 60:
            categoria = 'MODERADO-ALTO'
            recomendacion = 'Consulta cardiology urgente. Implementar intervenciones.'
        else:
            categoria = 'ALTO (requiere evaluación urgente)'
            recomendacion = 'Evaluación cardiovascular inmediata. Considerar estudios avanzados.'

        return {
            'puntuacion': puntuacion,
            'categoria': categoria,
            'recomendacion': recomendacion,
            'nota_importante': (
                'Este índice es ILUSTRATIVO y NO es un diagnóstico clínico.\n'
                'Debe ser interpretado por profesional médico.'
            )
        }

    @staticmethod
    def patrones_arritmia_sospechados(
        bpm: float,
        sdnn: float,
        lf_hf: float,
        intervalos_rr: List[float] | None = None
    ) -> List[str]:
        """
        Identifica patrones que podrían sugerir arritmias específicas.
        
        IMPORTANTE: Requiere confirmación con ECG clínico.
        """
        patrones = []

        # Patrón de fibrilación auricular
        if sdnn < 0.04 and lf_hf < 0.5 and 80 < bpm < 120:
            patrones.append(
                '⚠️ Patrón sugestivo de POSIBLE fibrilación auricular:\n'
                '   • Variabilidad muy baja pero irregularidad detectada\n'
                '   • FC variable pero en rango medio\n'
                '   ACCIÓN: Solicitar ECG de 12 derivaciones urgente'
            )

        # Patrón de flutter auricular
        if bpm > 140 and sdnn < 0.08:
            patrones.append(
                '⚠️ Patrón sugestivo de POSIBLE flutter auricular:\n'
                '   • FC muy elevada con patrón regular\n'
                '   ACCIÓN: ECG inmediato y ecocardiograma'
            )

        # Patrón de extrasístoles
        if intervalos_rr is not None and len(intervalos_rr) > 5:
            rr_std = np.std(intervalos_rr)
            rr_mean = np.mean(intervalos_rr)
            outliers = sum(1 for rr in intervalos_rr if abs(rr - rr_mean) > 2 * rr_std)
            if outliers > len(intervalos_rr) * 0.05:
                patrones.append(
                    f'⚠️ Patrón sugestivo de POSIBLES extrasístoles:\n'
                    f'   • Se detectan {outliers} intervalos anómalos\n'
                    '   ACCIÓN: Monitoreo ECG prolongado (Holter 24h)'
                )

        # Patrón de bradicardia con pausas
        if bpm < 50 and sdnn > 0.15:
            patrones.append(
                '⚠️ Patrón sugestivo de POSIBLE bradicardia con pausas:\n'
                '   • FC baja con variabilidad aumentada\n'
                '   • Sugiere pausas sinusales o bloqueos\n'
                '   ACCIÓN: Estudio electrofisiológico'
            )

        if not patrones:
            patrones.append('✓ No se detectan patrones sugestivos de arritmia')

        return patrones


def generar_reporte_riesgo_completo(
    bpm: float,
    sdnn: float,
    rmssd: float,
    lf_hf: float,
    skewness: float,
    kurtosis: float,
    intervalos_rr: List[float] | None = None
) -> str:
    """
    Genera un reporte clínico educativo completo de riesgo.
    """
    import numpy as np

    analizador = AnalisisRiesgoClinico()
    banderas = analizador.detectar_banderas_rojas(bpm, sdnn, rmssd, lf_hf, skewness, kurtosis)
    indice = analizador.calcular_indice_riesgo_compuesto(bpm, sdnn, rmssd, lf_hf)
    patrones = analizador.patrones_arritmia_sospechados(bpm, sdnn, lf_hf, intervalos_rr)

    reporte = f"""
╔═══════════════════════════════════════════════════════════════════╗
║         REPORTE CLÍNICO DE ANÁLISIS DE RIESGO CARDIOVASCULAR     ║
║                    [PROPÓSITO EDUCATIVO]                         ║
╚═══════════════════════════════════════════════════════════════════╝

⚠️ DESCARGO DE RESPONSABILIDAD:
Esta análisis es una herramienta EDUCATIVA y NO constituye diagnóstico.
Para diagnóstico y tratamiento definitivo, consulte cardiólogo.

───────────────────────────────────────────────────────────────────

📊 ÍNDICE DE RIESGO COMPUESTO
Puntuación: {indice['puntuacion']}/100
Categoría: {indice['categoria']}
Recomendación: {indice['recomendacion']}

───────────────────────────────────────────────────────────────────

🚩 BANDERAS CLÍNICAS DETECTADAS

HALLAZGOS MODERADOS (requieren atención):
{chr(10).join('  ' + b for b in banderas['moderado']) if banderas['moderado'] else '  Ninguno'}

HALLAZGOS POTENCIALES (vigilar):
{chr(10).join('  ' + b for b in banderas['potencial']) if banderas['potencial'] else '  Ninguno'}

HALLAZGOS INFORMATIVOS:
{chr(10).join('  ' + b for b in banderas['informativo']) if banderas['informativo'] else '  Ninguno'}

───────────────────────────────────────────────────────────────────

🔍 PATRONES DE ARRITMIA SOSPECHADOS

{chr(10).join(patrones)}

───────────────────────────────────────────────────────────────────

📋 PRÓXIMOS PASOS SUGERIDOS (consultar médico):

1. Si puntuación > 40: Solicitar evaluación cardiológica completa
2. Si se sospechan arritmias: ECG de 12 derivaciones + Holter
3. Investigar causas de estrés si LF/HF aumentado
4. Fortalecer autonomía: ejercicio regular, técnicas de relajación

───────────────────────────────────────────────────────────────────

═══════════════════════════════════════════════════════════════════
"""
    return reporte


import numpy as np
