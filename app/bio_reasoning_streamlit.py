"""Streamlit integration for the Biomedical Reasoning Engine.

This file is a decoupled page that can be run with `streamlit run` and does
not modify existing application code.
"""
import streamlit as st
from biomedical.reasoning_engine import BiomedicalReasoningEngine


def main():
    st.title("Biomedical Reasoning Engine — Demo")
    st.markdown("Inserte métricas fisiológicas para obtener razonamiento clínico explicable.")

    bpm = st.number_input("BPM", value=72)
    sdnn = st.number_input("SDNN (ms)", value=40.0)
    rmssd = st.number_input("RMSSD (ms)", value=30.0)
    pnn50 = st.number_input("pNN50 (%)", value=5.0)
    lf = st.number_input("LF (power)", value=0.5)
    hf = st.number_input("HF (power)", value=0.3)
    lf_hf = st.number_input("LF/HF", value=1.6)
    entropy = st.number_input("Entropy", value=1.0)

    ia_label = st.text_input("Resultado IA (opcional)")
    ia_score = st.number_input("Score IA (opcional)", value=0.0)

    if st.button("Analizar"):
        engine = BiomedicalReasoningEngine()
        metrics = {
            "BPM": bpm,
            "SDNN": sdnn,
            "RMSSD": rmssd,
            "pNN50": pnn50,
            "LF": lf,
            "HF": hf,
            "LF/HF": lf_hf,
            "Entropy": entropy,
        }
        ia = None
        if ia_label:
            ia = {"label": ia_label, "probability": ia_score}
        result = engine.analyze(metrics, ia_result=ia)
        st.subheader("Hallazgos")
        for f in result["hallazgos"]:
            st.write(f)

        st.subheader("Hipótesis")
        for h in result["hipotesis"]:
            st.write(h)

        st.subheader("Diagnósticos diferenciales")
        for d in result["diagnosticos_diferenciales"]:
            st.write(d)

        st.subheader("Riesgo")
        st.write(result["riesgo"])

        st.subheader("Explicación")
        st.write(result["explicacion"])


if __name__ == "__main__":
    main()
