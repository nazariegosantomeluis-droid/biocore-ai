@echo off
REM BIOCORE AI — Script de ejecución para Windows

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║         BIOCORE AI — Plataforma de Inteligencia Biomédica    ║
echo ║                   Iniciando aplicación...                    ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

REM Verificar que Python está instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Error: Python no está instalado o no está en el PATH
    echo.
    echo Para instalar Python:
    echo 1. Ve a https://www.python.org/downloads/
    echo 2. Descarga Python 3.9 o superior
    echo 3. Durante la instalación, marca "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

REM Mostrar versión de Python
echo ✓ Python instalado:
python --version
echo.

REM Verificar que streamlit está instalado
python -c "import streamlit" >nul 2>&1
if errorlevel 1 (
    echo ❌ Streamlit no instalado. Instalando dependencias...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo ❌ Error instalando dependencias
        pause
        exit /b 1
    )
)

echo ✓ Dependencias verificadas
echo.

REM BIOCORE AI tiene una única navegación soportada: el Hub dentro de app/main.py
REM (Digital Twin OS + Learning/Clinical/Research/Simulation/AI/Hardware hubs).
REM Los antiguos módulos de "app/pages/*.py" independientes fueron archivados
REM el 2026-07-03 — eran una segunda vía de navegación paralela, no coordinada
REM con el Hub (ver _archive/README.md). Academia Inteligente y ECG Monitor ya
REM están disponibles dentro del Hub (Learning Hub / Clinical Hub).
echo 🚀 Iniciando BIOCORE AI — http://localhost:8501
echo.
streamlit run app/main.py
