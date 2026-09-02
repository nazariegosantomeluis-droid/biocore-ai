try:
    import streamlit as st  # type: ignore[import]
except ImportError:
    print("Streamlit no está instalado. Por favor, instala Streamlit para ejecutar esta aplicación.")
    print("Puedes instalarlo usando: pip install streamlit")
    exit(1)

# Configuración de página DEBE ser el primer comando de streamlit
st.set_page_config(page_title="ECG Trainer Pro", layout="wide")

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os
import numpy as np

try:
    from src.signal_generator import ECGGenerator, get_all_case_types
    from src.ecg_education import ECGEducationPlatform
    from src.signal_processing import detect_r_peaks
except ImportError as e:
    ECGGenerator = None
    get_all_case_types = lambda: []
    ECGEducationPlatform = None
    detect_r_peaks = None
    print(f"Advertencia: los módulos locales no están disponibles: {e}")

from hardware.esp32_stream import ESP32ECGStreamer
from educational.ecg_tutor import ECGTutor

try:
    import plotly.graph_objects as go
except ImportError:
    go = None  # type: ignore

try:
    from streamlit import st_autorefresh
except Exception:
    st_autorefresh = None  # type: ignore

try:
    cache_resource = st.cache_resource
except AttributeError:
    cache_resource = lambda func: func  # type: ignore

@cache_resource
def get_esp32_streamer(port: str, baud: int, timeout: float, fs: int, simulate_if_missing: bool):
    return ESP32ECGStreamer(port=port, baud=baud, timeout=timeout, fs=fs, simulate_if_missing=simulate_if_missing)


def init_session():
    if 'score' not in st.session_state:
        st.session_state.score = 0
    if 'total' not in st.session_state:
        st.session_state.total = 0
    if 'current_case' not in st.session_state:
        st.session_state.current_case = None
    if 'quiz_submitted' not in st.session_state:
        st.session_state.quiz_submitted = False
    if 'app_mode' not in st.session_state:
        st.session_state.app_mode = 'Entrenamiento ECG'
    if 'esp32_running' not in st.session_state:
        st.session_state.esp32_running = False
    if 'esp32_port' not in st.session_state:
        st.session_state.esp32_port = 'COM3'
    if 'esp32_baud' not in st.session_state:
        st.session_state.esp32_baud = 115200
    if 'esp32_simulate' not in st.session_state:
        st.session_state.esp32_simulate = True
    if 'esp32_refresh_ms' not in st.session_state:
        st.session_state.esp32_refresh_ms = 600


def render_live_esp32_mode() -> None:
    st.header('📡 Live ECG desde ESP32 + AD8232')
    st.markdown(
        'Visualización de ECG en tiempo real desde un ESP32/Arduino. ' \
        'Se admiten datos seriales con formato `timestamp,valor` o valores crudos ADC.'
    )

    with st.sidebar:
        st.subheader('Configuración de transmisión')
        port = st.text_input('Puerto serial o Bluetooth', value=st.session_state.esp32_port)
        baud = st.selectbox('Baudios', [9600, 19200, 38400, 57600, 115200], index=4)
        simulate = st.checkbox('Simular si no detecta hardware', value=st.session_state.esp32_simulate)
        refresh_ms = st.number_input('Refrescar cada (ms)', min_value=200, max_value=2000, value=st.session_state.esp32_refresh_ms, step=100)
        st.markdown('---')
        start_button = st.button('Iniciar transmisión', use_container_width=True)
        stop_button = st.button('Detener transmisión', use_container_width=True)
        st.markdown('### Notas')
        st.write('El sensor AD8232 típicamente envía valores ADC que se normalizan a mV para visualización.')
        st.write('Si no hay hardware conectado, el modo de simulación crea un ECG realista de referencia.')

    st.session_state.esp32_port = port
    st.session_state.esp32_baud = baud
    st.session_state.esp32_simulate = simulate
    st.session_state.esp32_refresh_ms = refresh_ms

    streamer = get_esp32_streamer(port, baud, timeout=1.0, fs=250, simulate_if_missing=simulate)

    if start_button:
        st.session_state.esp32_running = True
    if stop_button:
        st.session_state.esp32_running = False

    if st.session_state.esp32_running:
        connected = streamer.connect(force_port=port)
        if not connected:
            st.error('No se pudo conectar al ESP32: ' + (streamer.last_error or 'Sin detalles.'))
        else:
            streamer.start()
    else:
        streamer.stop()
        if not simulate:
            streamer.disconnect()

    health = streamer.get_health_summary()
    status_cols = st.columns(4)
    status_cols[0].metric('Estado de conexión', health['state'])
    status_cols[1].metric('Segundos en buffer', f"{health['buffer_seconds']:.1f}")
    status_cols[2].metric('BPM estimado', f"{health['bpm']:.1f}" if health['bpm'] else 'N/A')
    status_cols[3].metric('Ruido', f"{health['noise_std']:.2f}")

    if health['last_error']:
        st.warning(f"Último error: {health['last_error']}")

    t, ecg = streamer.get_filtered_buffer()
    if len(ecg) > 2:
        if go is not None:
            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=t,
                    y=ecg,
                    mode='lines',
                    line=dict(color='#29A19C', width=2),
                    name='ECG en vivo'
                )
            )
            fig.update_layout(
                title='ECG en tiempo real',
                template='plotly_dark',
                paper_bgcolor='#121212',
                plot_bgcolor='#121212',
                margin=dict(l=12, r=12, t=40, b=24),
                xaxis=dict(title='Tiempo (s)', gridcolor='#333333'),
                yaxis=dict(title='mV', gridcolor='#333333')
            )
            st.plotly_chart(fig, use_container_width=True, theme='streamlit')
        else:
            st.line_chart(ecg)
    else:
        st.warning('Esperando datos desde el ESP32...')

    if st_autorefresh is not None and st.session_state.esp32_running:
        st_autorefresh(interval=refresh_ms, key='esp32_refresh')

    st.markdown('### Calidad de señal y métricas')
    metrics_text = f"- Conexión: {health['state']}\n"
    if health['bpm']:
        metrics_text += f"- BPM estimado: {health['bpm']:.1f}\n"
    else:
        metrics_text += '- BPM estimado: N/A\n'
    metrics_text += f"- Desviación estándar de ruido: {health['noise_std']:.2f}"
    st.write(metrics_text)


def generate_new_case():
    case_types = get_all_case_types() if get_all_case_types else ['ritmo_sinusal_normal']
    case_type = np.random.choice(case_types)

    if ECGGenerator is not None:
        t, sig = ECGGenerator.get_case(case_type)
    else:
        t = np.linspace(0, 10, int(10 * 250))
        sig = 0.1 * np.sin(2 * np.pi * 1.2 * t) + 0.01 * np.random.randn(len(t))
        case_type = 'ritmo_sinusal_normal'

    if ECGEducationPlatform is not None:
        platform = ECGEducationPlatform()
        case_info = platform.generar_caso_clinico(np.random.choice(['basico', 'intermedio', 'avanzado']))
    else:
        case_info = {
            'escenario': 'Caso educativo de ECG de referencia',
            'signos_vitales': {'fc': 72, 'pa': '120/80', 'respiracion': 16, 'temperatura': 37.0}
        }
    
    st.session_state.current_case = {
        'type': case_type,
        'signal': sig,
        'time': t,
        'fs': 250,
        'clinical': case_info
    }
    st.session_state.quiz_submitted = False

def main():
    init_session()
    st.title("🫀 Biomedical Signal Visualizer: Educativo y Streaming")

    st.sidebar.header('Modo de Plataforma')
    st.session_state.app_mode = st.sidebar.radio(
        'Selecciona un modo',
        ['Entrenamiento ECG', 'Live ESP32 ECG'],
        index=0 if st.session_state.app_mode == 'Entrenamiento ECG' else 1,
    )

    if st.session_state.app_mode == 'Live ESP32 ECG':
        render_live_esp32_mode()
        return

    col1, col2 = st.columns([2, 1])
    
    with col2:
        st.subheader("📊 Tu Progreso")
        st.metric("Puntuación", f"{st.session_state.score}/{st.session_state.total}")
        if st.button("Siguiente Caso ➡️", use_container_width=True):
            generate_new_case()
            st.rerun()
            
    if st.session_state.current_case is None:
        generate_new_case()
        
    case = st.session_state.current_case
    
    with col1:
        st.subheader("📝 Escenario Clínico")
        st.info(case['clinical']['escenario'])
        
        vitals = case['clinical']['signos_vitales']
        v1, v2, v3, v4 = st.columns(4)
        v1.metric("FC", vitals['fc'])
        v2.metric("PA", vitals['pa'])
        v3.metric("FR", vitals['respiracion'])
        v4.metric("Temp", vitals['temperatura'])
        
        st.subheader("📈 Trazado ECG (Derivación II)")
        tutor = ECGTutor()
        peaks = tutor.detect_r_peaks(case['signal'], case['fs'])
        clinical_fig = tutor.create_clinical_ecg_figure(
            case['signal'],
            case['fs'],
            peaks,
            start=0.0,
            duration=min(8.0, len(case['signal']) / case['fs']),
            show_annotations=True,
            teaching_overlay=True,
        )
        st.plotly_chart(clinical_fig, use_container_width=True, theme='streamlit')
        
    st.divider()
    st.subheader("❓ Evaluación de Interpretación")
    
    with st.form("quiz_form"):
        c_q1, c_q2 = st.columns(2)
        with c_q1:
            ans_rhythm = st.radio("1. ¿Cuál es el ritmo predominante?", ["Sinusal", "Irregularmente irregular", "Taquicardia de complejo ancho", "No determinable"])
            ans_hr = st.number_input("2. Estime la frecuencia cardíaca (BPM)", min_value=20, max_value=300, value=70)
        with c_q2:
            ans_qrs = st.selectbox("3. Morfología del QRS", ["Estrecho (< 120ms)", "Ancho (≥ 120ms)"])
            ans_diag = st.selectbox("4. Diagnóstico sugerido", ["Normal", "AFib", "Taquicardia Ventricular", "Bradicardia Sinusal", "STEMI", "Taquicardia Sinusal"])
            
        if st.form_submit_button("Enviar Diagnóstico ✅"):
            st.session_state.quiz_submitted = True
            st.session_state.total += 1
            map_diag = {'ritmo_sinusal_normal': 'Normal', 'taquicardia': 'Taquicardia Sinusal', 'bradicardia': 'Bradicardia Sinusal', 'fibrilacion_auricular': 'AFib', 'taquicardia_ventricular': 'Taquicardia Ventricular', 'stemi': 'STEMI'}
            if ans_diag == map_diag[case['type']]:
                st.session_state.score += 1
                st.success("🎉 ¡Diagnóstico Correcto!")
            else:
                st.error(f"❌ Incorrecto. Era: {map_diag[case['type']]}")

    if st.session_state.quiz_submitted:
        st.subheader("💡 Retroalimentación Educativa")
        leccion = ECGEducationPlatform().obtener_leccion(case['type'])
        with st.expander("Ver explicación fisiológica", expanded=True):
            st.write(f"**{leccion.titulo}**\n{leccion.explicacion_fisiologica}")
            st.write("**Hallazgos clave:**")
            for h in leccion.hallazgos_clinicos: st.write(f"- {h}")

    with st.sidebar:
        st.header("Instrucciones")
        st.write("Analiza el caso, responde el quiz y revisa el feedback tras enviar.")
        st.divider()
        st.write("### Nivel de Aprendizaje")
        st.progress(st.session_state.score / max(1, st.session_state.total))

if __name__ == "__main__":
    main()