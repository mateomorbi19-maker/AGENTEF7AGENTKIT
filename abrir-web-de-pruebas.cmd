@echo off
rem Abre la web de pruebas del agente en http://localhost:8000
rem Usa el entorno de Python que vive fuera de Google Drive.
cd /d "%~dp0"
set "PY=%USERPROFILE%\.venvs\agente-f7-agent-kit\Scripts\python.exe"
if not exist "%PY%" (
  echo No encuentro el entorno de Python en %PY%
  echo Pedile a Claude Code que lo vuelva a crear.
  pause
  exit /b 1
)
start "" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 4; Start-Process http://localhost:8000"
"%PY%" servidor.py
pause
