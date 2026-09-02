"""
Integración Streamlit del Biomedical Reasoning Engine.

Proporciona componentes visuales y interactivos para
utilizar el motor de razonamiento en la interfaz de Streamlit.
"""

import streamlit as st
import json
from typing import Optional, Dict, Any
import plotly.graph_objects as go
from datetime import datetime

from biomedical.reasoning_engine import (
    BiomedicalReasoningEngine,
    HRVMetrics,
    RiskLevel,
    AutonomicState,
    ReasoningOutput,
)


class BiomedicalReasoningStreamlit:
    """
    Componentes de Streamlit para Biomedical Reasoning Engine.
    
    Proporciona:
    - Panel de entrada de métricas
    - Visualización de hallazgos
    - Dashboard de riesgo
    - Impresión clínica
    - Recomendaciones educativas
    """

    def __init__(self):
        """Inicializa componentes."""
        self.engine = BiomedicalReasoningEngine()

    @staticmethod
    def input_metrics_panel() -> Optional[HRVMetrics]:
        """
        Panel interactivo para entrada de métricas HRV.
        
        Retorna
        -------
        Optional[HRVMetrics]
            Métricas ingresadas o None si no válidas
        """
        st.sidebar.markdown("## 📊 Métricas HRV")

        col1, col2 = st.sidebar.columns(2)

        with col1:
            bpm = st.number_input(
                "BPM",
                min_value=30,
                max_value=250,
                value=75,
                step=1,
                help="Frecuencia cardíaca en latidos por minuto",
            )

            sdnn = st.number_input(
                "SDNN",
                min_value=0.0,
                max_value=1.0,
                value=0.12,
                step=0.01,
                help="Desviación estándar de intervalos RR (segundos)",
            )

            rmssd = st.number_input(
                "RMSSD",
                min_value=0.0,
                max_value=1.0,
                value=0.05,
                step=0.01,
                help="Raíz cuadrada del promedio de diferencias al cuadrado",
            )

        with col2:
            pnn50 = st.number_input(
                "pNN50 (%)",
                min_value=0.0,
                max_value=100.0,
                value=20.0,
                step=1.0,
                help="Porcentaje de diferencias RR > 50ms",
            )

            entropy = st.number_input(
                "Entropía",
                min_value=0.0,
                max_value=10.0,
                value=3.5,
                step=0.1,
                help="Complejidad del ritmo cardíaco",
            )

        # Segunda fila de columnas
        col3, col4, col5 = st.sidebar.columns(3)

        with col3:
            lf = st.number_input(
                "LF (Baja Frec)",
                min_value=0.0,
                max_value=10.0,
                value=1.5,
                step=0.1,
                help="Potencia en banda de baja frecuencia",
            )

        with col4:
            hf = st.number_input(
                "HF (Alta Frec)",
                min_value=0.0,
                max_value=10.0,
                value=2.0,
                step=0.1,
                help="Potencia en banda de alta frecuencia",
            )

        with col5:
            lf_hf = st.number_input(
                "LF/HF",
                min_value=0.0,
                max_value=20.0,
                value=0.75,
                step=0.1,
                help="Relación LF/HF (balance autonómico)",
            )

        # AI Score opcional
        ai_score = st.sidebar.slider(
            "AI Anomaly Score (opcional)",
            0.0,
            1.0,
            0.3,
            step=0.05,
            help="Puntuación de anomalía del modelo de IA (0=normal, 1=anomalía)",
        )

        # Botón de análisis
        if st.sidebar.button("🔍 Analizar Métricas", key="analyze_button"):
            metrics = HRVMetrics(
                bpm=bpm,
                sdnn=sdnn,
                rmssd=rmssd,
                pnn50=pnn50,
                lf=lf,
                hf=hf,
                lf_hf=lf_hf,
                entropy=entropy,
                ai_score=ai_score,
                timestamp=datetime.now().isoformat(),
            )

            is_valid, validation_msg = metrics.validate()
            if not is_valid:
                st.sidebar.error(f"❌ Métricas inválidas: {validation_msg}")
                return None

            return metrics

        return None

    @staticmethod
    def display_findings(output: ReasoningOutput) -> None:
        """Muestra hallazgos fisiológicos."""
        st.markdown("## 🔬 Hallazgos Fisiológicos")

        if not output.findings:
            st.info("No se detectaron hallazgos significativos")
            return

        for i, finding in enumerate(output.findings, 1):
            with st.expander(
                f"✓ {finding.name} (Confianza: {finding.confidence*100:.0f}%)",
                expanded=(i == 1),
            ):
                st.markdown(f"**Descripción:** {finding.description}")

                if finding.clinical_relevance:
                    st.info(f"**Relevancia Clínica:** {finding.clinical_relevance}")

                if finding.implications:
                    st.markdown("**Implicaciones:**")
                    for impl in finding.implications:
                        st.markdown(f"  • {impl}")

    @staticmethod
    def display_hypotheses(output: ReasoningOutput) -> None:
        """Muestra hipótesis clínicas."""
        st.markdown("## 💡 Hipótesis Clínicas")

        if not output.hypotheses:
            st.info("No se pueden generar hipótesis con los datos actuales")
            return

        for i, hypothesis in enumerate(output.hypotheses, 1):
            severity_color = (
                "🟢" if hypothesis.probability < 0.5
                else "🟡" if hypothesis.probability < 0.75
                else "🔴"
            )

            with st.expander(
                f"{severity_color} {hypothesis.hypothesis} ({hypothesis.probability*100:.0f}%)",
                expanded=(i == 1),
            ):
                col1, col2 = st.columns(2)

                with col1:
                    st.markdown("**Métricas de Apoyo:**")
                    for metric in hypothesis.supporting_metrics:
                        st.markdown(f"  ✓ {metric}")

                with col2:
                    if hypothesis.contraindications:
                        st.markdown("**Contraindicaciones:**")
                        for contra in hypothesis.contraindications:
                            st.markdown(f"  ✗ {contra}")

                if hypothesis.next_steps:
                    st.markdown("**Próximos Pasos:**")
                    for step in hypothesis.next_steps:
                        st.markdown(f"  → {step}")

                if hypothesis.educational_note:
                    st.markdown(
                        f'<div style="background-color: #e8f4f8; padding: 10px; border-radius: 5px;">'
                        f"<b>Nota Educativa:</b> {hypothesis.educational_note}</div>",
                        unsafe_allow_html=True,
                    )

    @staticmethod
    def display_differential_diagnoses(output: ReasoningOutput) -> None:
        """Muestra diagnósticos diferenciales."""
        st.markdown("## 🏥 Diagnósticos Diferenciales")

        if not output.differential_diagnoses:
            st.info("No se pueden generar diagnósticos diferenciales")
            return

        # Tabla de resumen
        dx_data = [
            {
                "Condición": dx.condition,
                "Probabilidad": f"{dx.probability*100:.1f}%",
                "Características Cardinales": ", ".join(dx.cardinal_features[:2]),
            }
            for dx in output.differential_diagnoses
        ]

        st.dataframe(dx_data, use_container_width=True)

        # Detalles expandibles
        for dx in output.differential_diagnoses:
            with st.expander(f"📋 {dx.condition} ({dx.probability*100:.1f}%)"):
                col1, col2 = st.columns(2)

                with col1:
                    st.markdown("**Características Cardinales:**")
                    for feat in dx.cardinal_features:
                        st.markdown(f"  • {feat}")

                    st.markdown("**Hallazgos de Apoyo:**")
                    for finding in dx.supporting_findings:
                        st.markdown(f"  • {finding}")

                with col2:
                    st.markdown("**Características Distinguidoras:**")
                    for feat in dx.distinguishing_features:
                        st.markdown(f"  • {feat}")

                st.markdown("**Recomendaciones de Investigación:**")
                for rec in dx.investigation_recommendations:
                    st.markdown(f"  ➜ {rec}")

    @staticmethod
    def display_risk_dashboard(output: ReasoningOutput) -> None:
        """Muestra dashboard de riesgo."""
        st.markdown("## ⚠️ Evaluación de Riesgo")

        col1, col2, col3, col4 = st.columns(4)

        # Risk Level
        risk_colors = {
            RiskLevel.BAJO: "#2ecc71",
            RiskLevel.MODERADO: "#f39c12",
            RiskLevel.ALTO: "#e74c3c",
            RiskLevel.CRÍTICO: "#c0392b",
        }

        risk_icons = {
            RiskLevel.BAJO: "✅",
            RiskLevel.MODERADO: "⚠️",
            RiskLevel.ALTO: "🔴",
            RiskLevel.CRÍTICO: "🚨",
        }

        with col1:
            color = risk_colors[output.risk_level]
            icon = risk_icons[output.risk_level]
            st.markdown(
                f'<div style="background-color: {color}; padding: 20px; border-radius: 10px; text-align: center; color: white;">'
                f"<h3>{icon} {output.risk_level.value.upper()}</h3>"
                f"</div>",
                unsafe_allow_html=True,
            )

        with col2:
            st.metric("Puntuación de Riesgo", f"{output.risk_score:.1f}/100")

        with col3:
            st.metric(
                "Estado Autonómico",
                output.autonomic_state.value.replace("_", " ").title(),
            )

        with col4:
            st.metric("Hallazgos Detectados", len(output.findings))

        # Risk Score Gauge
        fig = go.Figure(
            go.Indicator(
                mode="gauge+number",
                value=output.risk_score,
                title="Riesgo Global (%)",
                domain={"x": [0, 1], "y": [0, 1]},
                gauge={
                    "axis": {"range": [0, 100]},
                    "bar": {"color": "darkblue"},
                    "steps": [
                        {"range": [0, 25], "color": "lightgreen"},
                        {"range": [25, 50], "color": "lightyellow"},
                        {"range": [50, 75], "color": "lightsalmon"},
                        {"range": [75, 100], "color": "lightcoral"},
                    ],
                    "threshold": {
                        "line": {"color": "red", "width": 4},
                        "thickness": 0.75,
                        "value": 75,
                    },
                },
            )
        )

        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)

    @staticmethod
    def display_clinical_impression(output: ReasoningOutput) -> None:
        """Muestra impresión clínica."""
        st.markdown("## 📝 Impresión Clínica")

        # Main narrative
        st.info(output.main_narrative)

        # Clinical impression
        with st.expander("Evaluación Clínica Detallada"):
            st.markdown(output.clinical_impression)

        # Warnings if any
        if output.warnings:
            st.markdown("### ⚠️ Advertencias")
            for warning in output.warnings:
                st.warning(warning)

    @staticmethod
    def display_recommendations(output: ReasoningOutput) -> None:
        """Muestra recomendaciones educativas."""
        st.markdown("## 💊 Recomendaciones Educativas")

        if not output.recommendations:
            st.info("No hay recomendaciones adicionales")
            return

        # Organizar por categoría
        categories = {}
        for rec in output.recommendations:
            if rec.category not in categories:
                categories[rec.category] = []
            categories[rec.category].append(rec)

        category_icons = {
            "lifestyle": "🏃",
            "monitoring": "📊",
            "investigation": "🔬",
            "clinical_follow_up": "👨‍⚕️",
        }

        urgency_colors = {
            "routine": "info",
            "soon": "warning",
            "urgent": "error",
        }

        for category, recs in categories.items():
            with st.expander(f"{category_icons.get(category, '•')} {category.replace('_', ' ').title()}"):
                for rec in recs:
                    # Header with urgency
                    color = urgency_colors.get(rec.urgency, "info")
                    urgency_text = rec.urgency.replace("_", " ").title()

                    st.markdown(f"**{rec.recommendation}**")
                    st.markdown(f"_Urgencia: {urgency_text} | Nivel: {rec.evidence_level}_")
                    st.markdown(f"> {rec.rationale}")
                    st.divider()

    @staticmethod
    def display_json_export(output: ReasoningOutput) -> None:
        """Proporciona exportación JSON."""
        st.markdown("## 📤 Exportar Resultados")

        col1, col2 = st.columns(2)

        with col1:
            json_str = output.to_json()
            st.download_button(
                label="📥 Descargar JSON",
                data=json_str,
                file_name=f"reasoning_output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
            )

        with col2:
            # También mostrar preview
            with st.expander("👁️ Ver JSON"):
                st.json(output.to_dict())

    def run_app(self) -> None:
        """Ejecuta la aplicación Streamlit completa."""
        st.set_page_config(
            page_title="Biomedical Reasoning Engine",
            page_icon="🧠",
            layout="wide",
        )

        st.title("🧠 Biomedical Reasoning Engine")
        st.markdown(
            """
            Motor de razonamiento clínico que transforma métricas fisiológicas en
            diagnósticos diferenciales educativos y recomendaciones clínicas.
            """
        )

        # Input panel
        metrics = self.input_metrics_panel()

        if metrics:
            st.success("✅ Métricas válidas. Procesando...")

            # Run reasoning
            with st.spinner("🔄 Analizando métricas..."):
                output = self.engine.reason(metrics)

            # Display results
            st.markdown("---")
            self.display_risk_dashboard(output)

            st.markdown("---")
            self.display_clinical_impression(output)

            st.markdown("---")
            self.display_findings(output)

            st.markdown("---")
            self.display_hypotheses(output)

            st.markdown("---")
            self.display_differential_diagnoses(output)

            st.markdown("---")
            self.display_recommendations(output)

            st.markdown("---")
            self.display_json_export(output)

        else:
            st.info(
                "👈 Ingresa métricas HRV en el panel izquierdo para comenzar el análisis"
            )


def create_reasoning_component(label: str = "Biomedical Reasoning") -> Optional[ReasoningOutput]:
    """
    Función helper para integrar el motor en páginas existentes.
    
    Parámetros
    ----------
    label : str
        Etiqueta para el componente
        
    Retorna
    -------
    Optional[ReasoningOutput]
        Resultado del razonamiento si se ejecuta
    """
    st.markdown(f"### {label}")

    col1, col2 = st.columns(2)

    with col1:
        bpm = st.number_input("BPM", min_value=30, max_value=250, value=75, key="bpm_component")
        sdnn = st.number_input("SDNN", min_value=0.0, max_value=1.0, value=0.12, key="sdnn_component")
        rmssd = st.number_input("RMSSD", min_value=0.0, max_value=1.0, value=0.05, key="rmssd_component")

    with col2:
        pnn50 = st.number_input("pNN50", min_value=0.0, max_value=100.0, value=20.0, key="pnn50_component")
        entropy = st.number_input("Entropía", min_value=0.0, max_value=10.0, value=3.5, key="entropy_component")
        lf_hf = st.number_input("LF/HF", min_value=0.0, max_value=20.0, value=0.75, key="lf_hf_component")

    if st.button("Analizar", key="analyze_component"):
        metrics = HRVMetrics(
            bpm=bpm,
            sdnn=sdnn,
            rmssd=rmssd,
            pnn50=pnn50,
            lf=1.5,  # Default values
            hf=2.0,
            lf_hf=lf_hf,
            entropy=entropy,
        )

        engine = BiomedicalReasoningEngine()
        output = engine.reason(metrics)

        st.success("✅ Análisis completado")
        st.json(output.to_dict())

        return output

    return None


if __name__ == "__main__":
    app = BiomedicalReasoningStreamlit()
    app.run_app()
