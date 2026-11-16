"""Vista «Sensores en vivo» del Multisensor Fusion Lab (2026-11-16): la placa ESP32 con el sensor de pulso por luz
(MAX30102) o el de temperatura (DS18B20), para medir o para seguir su tutorial.

Las demás vistas del laboratorio usan canales demo y el Health Score; esta no entra en ellos. El EMG en vivo está en
el EMG Muscle Lab, el EEG en vivo en el EEG Neuro Lab y la placa de ECG en el ECG Lab.
"""

from __future__ import annotations

import streamlit as st

from app.supermodules.biosensors import ppg, temperature

VIEW = 'Sensores en vivo'
SENSORS = {
    ppg.TITLE: (ppg.render_ppg_measure, ppg.render_ppg_tutorial),
    temperature.TITLE: (temperature.render_temp_measure, temperature.render_temp_tutorial),
}
MODES = ('Medir', 'Tutorial')


def render_live_sensors_view() -> None:
    st.markdown('### Sensores en vivo')
    st.caption('Una placa ESP32 por USB con un sensor de pulso por luz o de temperatura, o una placa simulada para '
               'practicar. Esta vista no entra al Health Score de las otras vistas. El EMG en vivo está en el EMG '
               'Muscle Lab, el EEG en vivo en el EEG Neuro Lab y la placa de ECG en el ECG Lab.')
    choice = st.radio('Sensor', list(SENSORS), horizontal=True, key='msl_live_sensor')
    mode = st.radio('Qué quieres hacer', MODES, horizontal=True, key='msl_live_mode')
    measure, tutorial = SENSORS[choice]
    if mode == MODES[1]:
        tutorial()
    else:
        measure()
