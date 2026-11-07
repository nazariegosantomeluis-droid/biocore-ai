# BIOCORE AI — Setup & Run

Single source of truth for getting the app running locally. It replaces the
older setup guides, which were removed.

## Requirements

- **Python**: developed and tested on CPython 3.13 only. The devcontainer uses 3.11
  (`.devcontainer/devcontainer.json`); other versions have not been tested.
- OS: Windows, macOS or Linux. Helper scripts for Windows are included
  (`run_local.ps1`, `RUN_BIOCORE.bat`).

## Install

```bash
# from the repo root
python -m venv .venv
# Windows:  .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate

pip install -r requirements.txt
```

`requirements_extra.txt` and `requirements_arrhythmia.txt` are optional add-ons
for specific subsystems; `requirements.txt` alone is enough to run the app.

## Run the app

```bash
streamlit run app/main.py
```

Then open the URL Streamlit prints (default <http://localhost:8501>) and use
the in-app navigation: four hubs (Digital Twin OS, Learning Hub, Clinical Hub and
Laboratorio 3D), with twelve menu entries in total (defined in `HUBS`, `app/main.py`). `app/streamlit_app.py` is only a thin
wrapper that re-execs `app/main.py`.

On Windows you can instead double-click `RUN_BIOCORE.bat` or run
`./run_local.ps1` from PowerShell (creates `.venv`, installs, launches).

## Optional: clinical AI narrator

The only real AI integration (`domain/physiology/narrator/`) calls the
Anthropic API. It is **off by default** and the app runs fully without it —
the narrator panels show an explicit "not configured" notice instead.

To enable it, either paste your key in the sidebar panel (it lives only in that
browser session, never in `os.environ` or on disk) or set it in the server's
environment before launching:

```bash
# Windows PowerShell
$env:ANTHROPIC_API_KEY = "sk-your-key-here"
# macOS/Linux
export ANTHROPIC_API_KEY="sk-your-key-here"
```

See `.env.example` for the full list of environment variables. Never hard-code
the key.

## Run the tests

```bash
pytest tests/ -q
```

`tests/conftest.py` redirects the UPS database to a temporary file for the whole
test session, so running the suite never writes to `data/biocore_ups.db`.

## Command-line pipeline (no UI)

`python main.py` at the repo root runs the standalone ECG analysis/plot
pipeline and writes PNGs to `figures/`. This is separate from the Streamlit
app and not required to use it.
