@echo off
REM BIOCORE AI - lanzador para Windows (doble clic).
REM  1. Crea un entorno virtual .venv la primera vez (no toca tu Python global).
REM  2. Instala/actualiza dependencias SOLO cuando requirements.txt cambia.
REM  3. Abre la app en http://localhost:8501
REM Para el narrador clinico: copia .env.example a .env y pon tu ANTHROPIC_API_KEY.

chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo.
echo ==============================================================
echo    BIOCORE AI - Plataforma de Inteligencia Biomedica
echo ==============================================================
echo.

REM --- Localizar Python (python o el lanzador py) -----------------------
set "PY="
python --version >nul 2>&1 && set "PY=python"
if not defined PY (
    py -3 --version >nul 2>&1 && set "PY=py -3"
)
if not defined PY (
    echo [ERROR] Python no esta instalado o no esta en el PATH.
    echo   1. Descarga Python 3.10 o superior: https://www.python.org/downloads/
    echo   2. Durante la instalacion marca "Add Python to PATH".
    echo.
    pause
    exit /b 1
)

REM --- Entorno virtual ---------------------------------------------------
if not exist ".venv\Scripts\python.exe" (
    echo Creando entorno virtual .venv ...
    %PY% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] No se pudo crear el entorno virtual.
        pause
        exit /b 1
    )
)
set "VPY=.venv\Scripts\python.exe"
"%VPY%" --version

REM --- Dependencias (solo si requirements.txt cambio desde la ultima vez) -
set "STAMP=.venv\requirements.installed.txt"
fc /b requirements.txt "%STAMP%" >nul 2>&1
if errorlevel 1 (
    echo Instalando dependencias, la primera vez tarda unos minutos ...
    "%VPY%" -m pip install --upgrade pip >nul
    "%VPY%" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Fallo la instalacion de dependencias. Revisa el mensaje de arriba.
        pause
        exit /b 1
    )
    copy /y requirements.txt "%STAMP%" >nul
) else (
    echo Dependencias al dia.
)

if not exist ".env" (
    echo Nota: sin .env el narrador clinico IA queda desactivado ^(la app funciona igual^).
)

echo.
echo Iniciando BIOCORE AI en http://localhost:8501  ^(Ctrl+C para cerrar^)
echo El navegador se abrira solo cuando la app este lista.
echo.
REM Abre el navegador en cuanto el servidor responda. -TimeoutSec 60: si una
REM consulta se abortara a medio aceptar, el servidor podria dejar de escuchar
REM (ver run_biocore.py); los intentos rechazados solo esperan 1 s y reintentan.
start "" /min powershell -NoProfile -Command "for($i=0;$i -lt 120;$i++){try{Invoke-WebRequest -UseBasicParsing -TimeoutSec 60 http://127.0.0.1:8501/_stcore/health | Out-Null; Start-Process 'http://localhost:8501'; break}catch{Start-Sleep -Seconds 1}}"
"%VPY%" run_biocore.py --server.port 8501
if errorlevel 1 pause
endlocal
