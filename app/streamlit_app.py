# Launcher for the Streamlit UI.
# This script runs the active Streamlit dashboard defined in app/main.py.

import sys
from pathlib import Path
import streamlit as st
import runpy

repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

app_main = repo_root / 'app' / 'main.py'
if not app_main.exists():
    st.error(f'Could not find Streamlit entrypoint: {app_main}')
    st.stop()

# 2026-11-17: sin `finally: st.stop()`. Ese alto reemplazaba la RerunException de cualquier `st.rerun()` de la app
# (aviso de entrada, «Nuevo caso»…) y la página quedaba en blanco hasta el siguiente clic. Las excepciones de control de
# Streamlit heredan de BaseException: el `except Exception` no las atrapa y siguen su curso.
try:
    runpy.run_path(str(app_main), run_name='__main__')
except Exception as e:
    st.error(f'Failed to execute app/main.py: {e}')
    import traceback
    st.text(traceback.format_exc())
