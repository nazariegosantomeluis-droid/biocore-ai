# BIOCORE AI — Setup & Run

Single source of truth for getting the app running locally. Supersedes the
older `COMO_EJECUTAR.md` / `QUICKSTART.md` / `SETUP_GUIDE.md` /
`STREAMLIT_SETUP_GUIDE.md` (removed).

## Requirements

- **Python 3.10+** (developed and tested on CPython 3.13).
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

`requirements.txt` alone is enough to run the app. `requirements-dev.txt`
adds pytest, linters and notebook tooling; `requirements_extra.txt` and
`requirements_arrhythmia.txt` are optional add-ons for specific subsystems.

## Run the app

```bash
python run_biocore.py        # recommended (Windows-safe event loop), or:
streamlit run app/main.py
```

Then open the URL Streamlit prints (default <http://localhost:8501>) and use
the in-app Hub navigation (Digital Twin OS + Learning / Clinical / Research /
Simulation / AI / Hardware hubs). `app/streamlit_app.py` is only a thin
wrapper that re-execs `app/main.py`.

On Windows you can instead double-click `RUN_BIOCORE.bat` or run
`./run_local.ps1` from PowerShell (creates `.venv` on first run, reinstalls
dependencies only when `requirements.txt` changes, launches).

## Optional: clinical AI narrator

The only real AI integration (`domain/physiology/narrator/`) works with a
**free local model** or with Claude. The app runs fully without either — the
narrator panels show an explicit "no AI engine" notice instead.

**Free, no key (recommended):** install [Ollama](https://ollama.com), then run
`ollama pull qwen2.5:7b` (about 4.7 GB; `qwen2.5:3b` for low-memory machines).
With Ollama running, BIOCORE detects it at `http://127.0.0.1:11434`; pick the
model in the sidebar under "Motor de IA". Any OpenAI-compatible local server
(LM Studio, llama.cpp, vLLM, Jan) also works: set `BIOCORE_LOCAL_AI_URL`.

**Claude:** copy `.env.example` to `.env` and put your key there — the app
loads `.env` from the repo root at startup (`app/utils/env_loader.py`; a
variable already set in the environment wins, and the example placeholder is
ignored). Or set it in your environment before launching:

```bash
# Windows PowerShell
$env:ANTHROPIC_API_KEY = "sk-your-key-here"
# macOS/Linux
export ANTHROPIC_API_KEY="sk-your-key-here"
```

See `.env.example` for the full list of environment variables. `.env` is
git-ignored — never hard-code the key in source files.

## Run the tests

```bash
pip install -r requirements-dev.txt
pytest tests/ -q
```

Tests that need PhysioNet (PTB-XL) are skipped automatically when there is no
network access.

## Command-line pipeline (no UI)

`python main.py` at the repo root runs the standalone ECG analysis/plot
pipeline and writes PNGs to `figures/`. This is separate from the Streamlit
app and not required to use it.
