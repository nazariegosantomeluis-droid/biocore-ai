"""
Streamlit Integration - Arrhythmia Classifier

Interactive web application for ECG arrhythmia classification.
Integrates with Biomedical Signal Visualizer.

Usage:
    streamlit run app_arrhythmia_classifier.py
"""

import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from pathlib import Path
import sys
import logging
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from biomedical.arrhythmia_compat import (
    ArrhythmiaInference,
    ArrhythmiaClassifier,
    BeatSegmentation,
    FeatureExtraction,
    ModelType,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page config
st.set_page_config(
    page_title="ECG Arrhythmia Classifier",
    page_icon="❤️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS styling
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        margin: 10px 0;
    }
    .success-box {
        background-color: #d4edda;
        padding: 15px;
        border-radius: 5px;
        color: #155724;
    }
    .warning-box {
        background-color: #fff3cd;
        padding: 15px;
        border-radius: 5px;
        color: #856404;
    }
    .error-box {
        background-color: #f8d7da;
        padding: 15px;
        border-radius: 5px;
        color: #721c24;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def load_inference_engine():
    """Load inference engine."""
    classifier = ArrhythmiaClassifier()
    
    # Try to load best available model
    for model_type in [ModelType.RANDOM_FOREST, ModelType.XGBOOST, ModelType.LIGHTGBM]:
        model_path = classifier.model_dir / f"{model_type.value}_model.pkl"
        if model_path.exists():
            try:
                engine = ArrhythmiaInference(model_path=model_path, model_type=model_type)
                return engine, model_type
            except Exception as e:
                logger.warning(f"Failed to load {model_type.value}: {e}")
    
    return None, None


def plot_ecg_signal(signal: np.ndarray, r_peaks: np.ndarray = None, title: str = "ECG Signal"):
    """Plot ECG signal with optional R peaks."""
    sampling_rate = 360
    time = np.arange(len(signal)) / sampling_rate
    
    fig = go.Figure()
    
    # ECG signal
    fig.add_trace(go.Scatter(
        x=time, y=signal,
        mode='lines',
        name='ECG',
        line=dict(color='#1f77b4', width=2),
    ))
    
    # R peaks
    if r_peaks is not None and len(r_peaks) > 0:
        r_peak_times = r_peaks / sampling_rate
        r_peak_values = signal[r_peaks]
        fig.add_trace(go.Scatter(
            x=r_peak_times, y=r_peak_values,
            mode='markers',
            name='R Peaks',
            marker=dict(color='red', size=10),
        ))
    
    fig.update_layout(
        title=title,
        xaxis_title="Time (s)",
        yaxis_title="Amplitude (mV)",
        hovermode='x unified',
        height=400,
    )
    
    return fig


def plot_beat(beat: np.ndarray, title: str = "ECG Beat"):
    """Plot single ECG beat."""
    sampling_rate = 360
    time = np.arange(len(beat)) / sampling_rate
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=time, y=beat,
        mode='lines+markers',
        name='Beat',
        line=dict(color='#1f77b4', width=2),
        marker=dict(size=4),
    ))
    
    fig.update_layout(
        title=title,
        xaxis_title="Time (s)",
        yaxis_title="Amplitude (mV)",
        hovermode='x',
        height=350,
    )
    
    return fig


def plot_probabilities(probabilities: dict):
    """Plot prediction probabilities."""
    classes = list(probabilities.keys())
    probs = [probabilities[c] * 100 for c in classes]
    
    # Map class codes to names
    class_names = {
        'NORMAL': 'Normal',
        'PVC': 'PVC',
        'PAC': 'PAC',
        'AFIB': 'AFib',
        'LBBB': 'LBBB',
        'RBBB': 'RBBB',
        'VT': 'V.Tachycardia',
        'ATRIAL_FLUTTER': 'Atrial Flutter',
    }
    
    display_names = [class_names.get(c, c) for c in classes]
    
    fig = go.Figure(data=[
        go.Bar(x=display_names, y=probs, marker_color='#1f77b4')
    ])
    
    fig.update_layout(
        title="Prediction Probabilities",
        xaxis_title="Arrhythmia Class",
        yaxis_title="Probability (%)",
        height=400,
    )
    
    return fig


def main():
    """Main Streamlit application."""
    # Header
    st.markdown("# ❤️ ECG Arrhythmia Classifier")
    st.markdown("Multi-class classification using Random Forest, XGBoost, and LightGBM")
    
    # Load inference engine
    inference_engine, model_type = load_inference_engine()
    
    if inference_engine is None:
        st.error("⚠️ No trained models found!")
        st.info("Please run: `python train_arrhythmia_classifier.py`")
        return
    
    st.success(f"✓ Model loaded: {model_type.value.upper()}")
    
    # Sidebar
    st.sidebar.markdown("## Settings")
    analysis_type = st.sidebar.radio(
        "Analysis Type",
        ["Single Beat", "Full ECG Signal", "Batch Processing"]
    )
    
    sampling_rate = st.sidebar.slider("Sampling Rate (Hz)", 100, 1000, 360)
    
    # Main content
    if analysis_type == "Single Beat":
        st.markdown("## Single Beat Classification")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### Beat Input")
            beat_length = int(st.number_input("Beat Length (samples)", 100, 500, 216))
            
            # Generate or upload beat
            input_method = st.radio("Input Method", ["Generate Synthetic", "Upload File"])
            
            if input_method == "Generate Synthetic":
                # Generate beat template selector
                beat_type = st.selectbox(
                    "Beat Type",
                    ["Normal", "PVC", "PAC", "AFib", "LBBB", "RBBB", "VT", "Atrial Flutter"]
                )
                
                if st.button("Generate Beat"):
                    # Generate synthetic beat
                    from train_arrhythmia_classifier import generate_synthetic_beats
                        from biomedical.arrhythmia_classifier import ArrhythmiaClass
                    
                    st.session_state.current_beat = beat
                    st.success("✓ Beat generated")
            else:
                uploaded_file = st.file_uploader("Upload beat data (CSV/NPY)", type=["csv", "npy"])
                if uploaded_file:
                    try:
                        if uploaded_file.name.endswith('.npy'):
                            beat = np.load(uploaded_file)
                        else:
                            data = pd.read_csv(uploaded_file)
                            beat = data.iloc[:, 0].values
                        
                        st.session_state.current_beat = beat
                        st.success("✓ Beat loaded")
                    except Exception as e:
                        st.error(f"Error loading file: {e}")
        
        with col2:
            st.markdown("### Prediction Results")
            
            if 'current_beat' in st.session_state:
                beat = st.session_state.current_beat
                
                # Show beat plot
                fig_beat = plot_beat(beat)
                st.plotly_chart(fig_beat, use_container_width=True)
                
                # Predict
                if st.button("🔍 Classify Beat"):
                    try:
                        result = inference_engine.predict_single_beat(beat)
                        summary = inference_engine.get_prediction_summary(result)
                        
                        # Display results
                        col_res1, col_res2, col_res3 = st.columns(3)
                        
                        with col_res1:
                            st.metric("Predicted Class", summary['class_name'])
                        
                        with col_res2:
                            st.metric("Confidence", summary['confidence'])
                        
                        with col_res3:
                            st.metric("Model", summary['model_used'].upper())
                        
                        st.markdown("### Probabilities")
                        fig_prob = plot_probabilities(result.probabilities)
                        st.plotly_chart(fig_prob, use_container_width=True)
                        
                        st.markdown("### Class Description")
                        st.info(summary['description'])
                        
                        st.markdown("### Top Candidates")
                        for class_name, prob in summary['top_3_candidates']:
                            st.write(f"**{class_name}**: {prob*100:.1f}%")
                        
                    except Exception as e:
                        st.error(f"Classification error: {e}")
            else:
                st.info("👈 Generate or upload a beat to get started")
    
    elif analysis_type == "Full ECG Signal":
        st.markdown("## Full ECG Signal Analysis")
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.markdown("### Signal Input")
            signal_duration = st.slider("Signal Duration (seconds)", 1, 30, 5)
            
            if st.button("Generate Test Signal"):
                from train_arrhythmia_classifier import generate_synthetic_ecg_signal
                signal = generate_synthetic_ecg_signal(duration=signal_duration, sampling_rate=sampling_rate)
                st.session_state.current_signal = signal
                st.success(f"✓ Signal generated ({len(signal)} samples)")
        
        with col2:
            st.markdown("### Upload Signal")
            uploaded_signal = st.file_uploader("Upload ECG signal (CSV/NPY)", type=["csv", "npy"], key="signal")
            if uploaded_signal:
                try:
                    if uploaded_signal.name.endswith('.npy'):
                        signal = np.load(uploaded_signal)
                    else:
                        data = pd.read_csv(uploaded_signal)
                        signal = data.iloc[:, 0].values
                    
                    st.session_state.current_signal = signal
                    st.success(f"✓ Signal loaded ({len(signal)} samples)")
                except Exception as e:
                    st.error(f"Error loading file: {e}")
        
        if 'current_signal' in st.session_state:
            signal = st.session_state.current_signal
            
            # Show signal plot
            beat_segmenter = BeatSegmentation(sampling_rate=sampling_rate)
            r_peaks = beat_segmenter.detect_r_peaks(signal)
            
            fig_signal = plot_ecg_signal(signal, r_peaks)
            st.plotly_chart(fig_signal, use_container_width=True)
            
            st.info(f"Detected {len(r_peaks)} R peaks")
            
            # Analyze
            if st.button("🔍 Analyze Signal"):
                try:
                    with st.spinner("Analyzing..."):
                        result = inference_engine.predict_ecg_signal(
                            signal, return_beat_predictions=True
                        )
                    
                    overall_result = result['overall_result']
                    beat_predictions = result['beat_predictions']
                    
                    # Overall results
                    col_o1, col_o2, col_o3 = st.columns(3)
                    
                    with col_o1:
                        st.metric("Overall Class", overall_result.predicted_class.name)
                    
                    with col_o2:
                        st.metric("Confidence", f"{overall_result.confidence*100:.1f}%")
                    
                    with col_o3:
                        st.metric("Total Beats", result['total_beats'])
                    
                    # Probabilities
                    st.markdown("### Overall Probabilities")
                    fig_prob = plot_probabilities(overall_result.probabilities)
                    st.plotly_chart(fig_prob, use_container_width=True)
                    
                    # Beat-by-beat predictions
                    st.markdown("### Beat-by-Beat Predictions")
                    
                    beats_df = pd.DataFrame([
                        {
                            'Beat': bp['beat_index'],
                            'Class': bp['predicted_class'],
                            'Confidence': f"{bp['confidence']*100:.1f}%",
                        }
                        for bp in beat_predictions
                    ])
                    
                    st.dataframe(beats_df, use_container_width=True)
                    
                except Exception as e:
                    st.error(f"Analysis error: {e}")
    
    elif analysis_type == "Batch Processing":
        st.markdown("## Batch Processing")
        
        st.markdown("### Generate Batch")
        batch_size = st.slider("Number of beats", 10, 200, 50)
        
        if st.button("Generate Batch"):
            from train_arrhythmia_classifier import generate_synthetic_beats
            beats, labels = generate_synthetic_beats(num_samples_per_class=batch_size // 8)
            st.session_state.batch_beats = beats
            st.session_state.batch_labels = labels
            st.success(f"✓ Batch generated ({len(beats)} beats)")
        
        if 'batch_beats' in st.session_state and 'batch_labels' in st.session_state:
            beats = st.session_state.batch_beats
            labels = st.session_state.batch_labels
            
            if st.button("🔍 Process Batch"):
                try:
                    with st.spinner(f"Processing {len(beats)} beats..."):
                        results = inference_engine.predict_batch(beats)
                    
                    # Create results dataframe
                    results_data = []
                    for i, result in enumerate(results):
                        results_data.append({
                            'Beat #': i + 1,
                            'Predicted': result.predicted_class.name,
                            'Confidence': f"{result.confidence*100:.1f}%",
                            'Features': result.features_used,
                        })
                    
                    results_df = pd.DataFrame(results_data)
                    st.dataframe(results_df, use_container_width=True)
                    
                    # Statistics
                    st.markdown("### Statistics")
                    
                    col_s1, col_s2, col_s3 = st.columns(3)
                    
                    confidences = [r.confidence for r in results]
                    
                    with col_s1:
                        st.metric("Total Beats", len(results))
                    
                    with col_s2:
                        st.metric("Avg Confidence", f"{np.mean(confidences)*100:.1f}%")
                    
                    with col_s3:
                        st.metric("Min Confidence", f"{np.min(confidences)*100:.1f}%")
                    
                    # Download results
                    st.markdown("### Export Results")
                    csv = results_df.to_csv(index=False)
                    st.download_button(
                        label="Download Results (CSV)",
                        data=csv,
                        file_name=f"classification_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv"
                    )
                    
                except Exception as e:
                    st.error(f"Batch processing error: {e}")
    
    # Footer
    st.markdown("---")
    st.markdown("""
    **Note:** This application is for educational and research purposes.
    It provides "patterns suggestive of" arrhythmias and should not be used
    as a substitute for professional medical evaluation.
    """)


if __name__ == "__main__":
    main()
