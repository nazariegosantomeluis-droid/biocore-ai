"""
Ejemplos de uso del Biomedical Reasoning Engine.

Este script demuestra:
1. Análisis básico de métricas
2. Validación de métricas
3. Exportación de resultados
4. Múltiples escenarios clínicos
"""

import json
import sys
from datetime import datetime
from biomedical.reasoning_engine import (
    BiomedicalReasoningEngine,
    HRVMetrics,
    RiskLevel,
    AutonomicState,
)

# Configurar codificación UTF-8 para Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def print_header(text: str) -> None:
    """Imprime encabezado formateado."""
    print("\n" + "=" * 80)
    print(f"  {text}")
    print("=" * 80)


def print_section(text: str) -> None:
    """Imprime sección formateada."""
    print(f"\n{text}")
    print("-" * len(text))


def print_findings(output) -> None:
    """Imprime hallazgos."""
    print_section("📊 HALLAZGOS FISIOLÓGICOS")
    if output.findings:
        for i, finding in enumerate(output.findings, 1):
            print(f"\n{i}. {finding.name}")
            print(f"   Descripción: {finding.description}")
            print(f"   Confianza: {finding.confidence*100:.0f}%")
            if finding.implications:
                print(f"   Implicaciones:")
                for impl in finding.implications:
                    print(f"     • {impl}")
            if finding.clinical_relevance:
                print(f"   Relevancia: {finding.clinical_relevance}")
    else:
        print("No hay hallazgos significativos")


def print_hypotheses(output) -> None:
    """Imprime hipótesis clínicas."""
    print_section("💡 HIPÓTESIS CLÍNICAS")
    if output.hypotheses:
        for i, hyp in enumerate(output.hypotheses, 1):
            print(f"\n{i}. {hyp.hypothesis}")
            print(f"   Probabilidad: {hyp.probability*100:.0f}%")
            if hyp.supporting_metrics:
                print(f"   Métricas de apoyo: {', '.join(hyp.supporting_metrics[:3])}")
            if hyp.next_steps:
                print(f"   Próximos pasos: {', '.join(hyp.next_steps[:2])}")
            if hyp.educational_note:
                print(f"   Nota educativa: {hyp.educational_note}")
    else:
        print("No se pueden generar hipótesis")


def print_differential_diagnoses(output) -> None:
    """Imprime diagnósticos diferenciales."""
    print_section("🏥 DIAGNÓSTICOS DIFERENCIALES")
    if output.differential_diagnoses:
        for i, dx in enumerate(output.differential_diagnoses, 1):
            print(f"\n{i}. {dx.condition}")
            print(f"   Probabilidad: {dx.probability*100:.1f}%")
            if dx.cardinal_features:
                print(f"   Características cardinales: {', '.join(dx.cardinal_features[:2])}")
            if dx.investigation_recommendations:
                print(f"   Investigaciones: {', '.join(dx.investigation_recommendations[:2])}")
    else:
        print("No se pueden generar diagnósticos diferenciales")


def print_risk_assessment(output) -> None:
    """Imprime evaluación de riesgo."""
    print_section("⚠️ EVALUACIÓN DE RIESGO")
    print(f"Nivel de Riesgo: {output.risk_level.value.upper()}")
    print(f"Puntuación de Riesgo: {output.risk_score:.1f}/100")
    print(f"Estado Autonómico: {output.autonomic_state.value}")
    
    if output.warnings:
        print_section("ADVERTENCIAS")
        for warning in output.warnings:
            print(f"  ⚠️  {warning}")


def print_recommendations(output) -> None:
    """Imprime recomendaciones."""
    print_section("💊 RECOMENDACIONES EDUCATIVAS")
    if output.recommendations:
        for i, rec in enumerate(output.recommendations, 1):
            urgency_symbol = {
                "routine": "•",
                "soon": "⚠️",
                "urgent": "🔴"
            }.get(rec.urgency, "•")
            
            print(f"\n{i}. {urgency_symbol} {rec.recommendation}")
            print(f"   Urgencia: {rec.urgency}")
            print(f"   Evidencia: {rec.evidence_level}")
            print(f"   Razón: {rec.rationale}")
    else:
        print("No hay recomendaciones adicionales")


def example_1_normal_health():
    """Ejemplo 1: Persona con buena salud cardiovascular."""
    print_header("EJEMPLO 1: BUENA SALUD CARDIOVASCULAR")
    
    print("\nEscenario: Persona joven, activa, sin estrés")
    
    metrics = HRVMetrics(
        bpm=68,
        sdnn=0.16,
        rmssd=0.07,
        pnn50=32,
        lf=1.2,
        hf=2.8,
        lf_hf=0.43,
        entropy=4.1,
        ai_score=0.15,
    )
    
    # Validar
    is_valid, msg = metrics.validate()
    print(f"\n✓ Validación: {msg}")
    
    # Analizar
    engine = BiomedicalReasoningEngine()
    output = engine.reason(metrics)
    
    # Mostrar resultados
    print_risk_assessment(output)
    print_findings(output)
    print_hypotheses(output)
    print_recommendations(output)
    print_section("📝 IMPRESIÓN CLÍNICA")
    print(output.clinical_impression)


def example_2_acute_stress():
    """Ejemplo 2: Persona bajo estrés agudo."""
    print_header("EJEMPLO 2: ESTRÉS AGUDO")
    
    print("\nEscenario: Presentación, entrevista laboral, ansiedad")
    
    metrics = HRVMetrics(
        bpm=112,
        sdnn=0.08,
        rmssd=0.02,
        pnn50=8,
        lf=3.5,
        hf=0.8,
        lf_hf=4.375,
        entropy=2.1,
        ai_score=0.65,
    )
    
    is_valid, msg = metrics.validate()
    print(f"\n✓ Validación: {msg}")
    
    engine = BiomedicalReasoningEngine()
    output = engine.reason(metrics)
    
    print_risk_assessment(output)
    print_findings(output)
    print_hypotheses(output)
    print_differential_diagnoses(output)
    print_recommendations(output)
    print_section("📝 IMPRESIÓN CLÍNICA")
    print(output.clinical_impression)


def example_3_high_risk():
    """Ejemplo 3: Persona con riesgo alto."""
    print_header("EJEMPLO 3: RIESGO ALTO - DISFUNCIÓN AUTONÓMICA")
    
    print("\nEscenario: Variabilidad muy baja, taquicardia, entropía reducida")
    
    metrics = HRVMetrics(
        bpm=125,
        sdnn=0.04,
        rmssd=0.008,
        pnn50=2,
        lf=5.0,
        hf=0.2,
        lf_hf=25.0,
        entropy=0.9,
        ai_score=0.85,
    )
    
    is_valid, msg = metrics.validate()
    print(f"\n✓ Validación: {msg}")
    
    engine = BiomedicalReasoningEngine()
    output = engine.reason(metrics)
    
    print_risk_assessment(output)
    print_findings(output)
    print_hypotheses(output)
    print_differential_diagnoses(output)
    print_recommendations(output)
    print_section("📝 IMPRESIÓN CLÍNICA")
    print(output.clinical_impression)


def example_4_recovery():
    """Ejemplo 4: Persona en recuperación post-ejercicio."""
    print_header("EJEMPLO 4: RECUPERACIÓN POST-EJERCICIO")
    
    print("\nEscenario: Después de actividad física, bradicardia, parasimpático dominante")
    
    metrics = HRVMetrics(
        bpm=58,
        sdnn=0.14,
        rmssd=0.08,
        pnn50=28,
        lf=1.0,
        hf=3.0,
        lf_hf=0.33,
        entropy=3.9,
        ai_score=0.1,
    )
    
    is_valid, msg = metrics.validate()
    print(f"\n✓ Validación: {msg}")
    
    engine = BiomedicalReasoningEngine()
    output = engine.reason(metrics)
    
    print_risk_assessment(output)
    print_findings(output)
    print_hypotheses(output)
    print_recommendations(output)


def example_5_validation_error():
    """Ejemplo 5: Manejo de error de validación."""
    print_header("EJEMPLO 5: VALIDACIÓN DE ERRORES")
    
    print("\nEscenario: BPM fuera de rango")
    
    metrics = HRVMetrics(
        bpm=400,  # Inválido
        sdnn=0.1,
        rmssd=0.05,
        pnn50=20,
        lf=2.0,
        hf=1.5,
        lf_hf=1.33,
        entropy=3.5,
    )
    
    is_valid, msg = metrics.validate()
    print(f"\n✗ Validación: {msg}")
    
    if not is_valid:
        print("\nIntentando análisis con métricas inválidas...")
        engine = BiomedicalReasoningEngine()
        output = engine.reason(metrics)
        print(f"Resultado: {output.warnings}")


def example_6_export_json():
    """Ejemplo 6: Exportar resultados a JSON."""
    print_header("EJEMPLO 6: EXPORTAR RESULTADOS A JSON")
    
    metrics = HRVMetrics(
        bpm=78,
        sdnn=0.12,
        rmssd=0.05,
        pnn50=20,
        lf=1.8,
        hf=2.2,
        lf_hf=0.82,
        entropy=3.7,
        ai_score=0.25,
    )
    
    engine = BiomedicalReasoningEngine()
    output = engine.reason(metrics)
    
    # Exportar a JSON
    json_output = output.to_json()
    
    # Guardar a archivo
    filename = f"reasoning_output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, "w") as f:
        f.write(json_output)
    
    print(f"\n✓ Resultados guardados en: {filename}")
    print(f"\nPrimeros 500 caracteres del JSON:")
    print(json_output[:500] + "...")


def example_7_batch_analysis():
    """Ejemplo 7: Análisis de múltiples métricas (batch)."""
    print_header("EJEMPLO 7: ANÁLISIS EN LOTE")
    
    test_cases = [
        ("Normal", {
            "bpm": 72, "sdnn": 0.15, "rmssd": 0.06, "pnn50": 25,
            "lf": 1.5, "hf": 2.5, "lf_hf": 0.6, "entropy": 4.0
        }),
        ("Tachycardia", {
            "bpm": 110, "sdnn": 0.08, "rmssd": 0.03, "pnn50": 10,
            "lf": 3.5, "hf": 1.0, "lf_hf": 3.5, "entropy": 2.5
        }),
        ("Bradycardia", {
            "bpm": 55, "sdnn": 0.18, "rmssd": 0.09, "pnn50": 35,
            "lf": 1.0, "hf": 3.5, "lf_hf": 0.29, "entropy": 4.2
        }),
    ]
    
    engine = BiomedicalReasoningEngine()
    results = []
    
    for name, params in test_cases:
        metrics = HRVMetrics(**params)
        output = engine.reason(metrics)
        results.append({
            "case": name,
            "bpm": params["bpm"],
            "risk_level": output.risk_level.value,
            "risk_score": output.risk_score,
            "autonomic_state": output.autonomic_state.value,
            "main_hypothesis": output.hypotheses[0].hypothesis if output.hypotheses else "N/A",
        })
    
    # Mostrar tabla comparativa
    print("\n" + "-" * 100)
    print(f"{'Caso':<15} {'BPM':<8} {'Riesgo':<12} {'Score':<10} {'Autonómico':<15} {'Hipótesis':<35}")
    print("-" * 100)
    
    for result in results:
        print(
            f"{result['case']:<15} "
            f"{result['bpm']:<8} "
            f"{result['risk_level']:<12} "
            f"{result['risk_score']:<10.1f} "
            f"{result['autonomic_state']:<15} "
            f"{result['main_hypothesis']:<35}"
        )
    
    print("-" * 100)


def main():
    """Ejecuta todos los ejemplos."""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 78 + "║")
    print("║" + "  BIOMEDICAL REASONING ENGINE - EJEMPLOS DE USO".center(78) + "║")
    print("║" + " " * 78 + "║")
    print("╚" + "=" * 78 + "╝")
    
    try:
        example_1_normal_health()
        example_2_acute_stress()
        example_3_high_risk()
        example_4_recovery()
        example_5_validation_error()
        example_6_export_json()
        example_7_batch_analysis()
        
        print_header("✅ TODOS LOS EJEMPLOS COMPLETADOS EXITOSAMENTE")
        
    except Exception as e:
        print_header(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
