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

try:
    runpy.run_path(str(app_main), run_name='__main__')
except Exception as e:
    st.error(f'Failed to execute app/main.py: {e}')
    import traceback
    st.text(traceback.format_exc())
finally:
    st.stop()
