# Run-local helper for BIOCORE AI (PowerShell)
# Usage: Open PowerShell, from repo root run: .\run_local.ps1

param(
    [switch]$RecreateVenv
)

$venvPath = ".venv"
if ($RecreateVenv -or -not (Test-Path $venvPath)) {
    Write-Host "Creating virtual environment..."
    python -m venv $venvPath
}

Write-Host "Activating virtual environment..."
& $venvPath\Scripts\Activate.ps1

Write-Host "Installing requirements (may take a few minutes)..."
if (Test-Path requirements.txt) {
    pip install -r requirements.txt
} else {
    pip install numpy scipy streamlit plotly
}

Write-Host "Launching Streamlit app..."
streamlit run app/main.py
