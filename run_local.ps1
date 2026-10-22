# BIOCORE AI - lanzador para PowerShell.
# Uso (desde la raíz del repo):  .\run_local.ps1            # normal
#                               .\run_local.ps1 -RecreateVenv
# Si PowerShell bloquea el script:  Set-ExecutionPolicy -Scope Process Bypass
# Mismo comportamiento que RUN_BIOCORE.bat: .venv propio y reinstalación de
# dependencias solo cuando requirements.txt cambia.

param(
    [switch]$RecreateVenv
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$venvPath = ".venv"
$venvPython = Join-Path $venvPath "Scripts\python.exe"
$stamp = Join-Path $venvPath "requirements.installed.txt"

if ($RecreateVenv -and (Test-Path $venvPath)) {
    Write-Host "Eliminando .venv existente..."
    Remove-Item -Recurse -Force $venvPath
}

if (-not (Test-Path $venvPython)) {
    Write-Host "Creando entorno virtual .venv ..."
    if (Get-Command python -ErrorAction SilentlyContinue) { python -m venv $venvPath }
    elseif (Get-Command py -ErrorAction SilentlyContinue) { py -3 -m venv $venvPath }
    else { throw "Python no está instalado o no está en el PATH (https://www.python.org/downloads/)." }
}

$needsInstall = -not (Test-Path $stamp) -or
    ((Get-FileHash requirements.txt).Hash -ne (Get-FileHash $stamp).Hash)
if ($needsInstall) {
    Write-Host "Instalando dependencias (la primera vez tarda unos minutos)..."
    & $venvPython -m pip install --upgrade pip | Out-Null
    & $venvPython -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw "Falló la instalación de dependencias." }
    Copy-Item requirements.txt $stamp -Force
} else {
    Write-Host "Dependencias al día."
}

if (-not (Test-Path ".env")) {
    Write-Host "Nota: sin .env el narrador clínico IA queda desactivado (la app funciona igual)."
}

Write-Host "Iniciando BIOCORE AI en http://localhost:8501 (Ctrl+C para cerrar)"
Write-Host "El navegador se abrirá solo cuando la app esté lista."
# Abre el navegador en cuanto el servidor responda (ver RUN_BIOCORE.bat: -TimeoutSec 60
# para no abortar conexiones a medio aceptar).
$opener = "for(`$i=0;`$i -lt 120;`$i++){try{Invoke-WebRequest -UseBasicParsing -TimeoutSec 60 http://127.0.0.1:8501/_stcore/health | Out-Null; Start-Process 'http://localhost:8501'; break}catch{Start-Sleep -Seconds 1}}"
Start-Process powershell -WindowStyle Hidden -ArgumentList '-NoProfile', '-Command', $opener
& $venvPython run_biocore.py --server.port 8501
