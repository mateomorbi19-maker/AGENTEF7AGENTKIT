@echo off
rem Copia las claves del proyecto viejo (n8n) al .env de este proyecto, sin mostrarlas.
cd /d "%~dp0"
"%USERPROFILE%\.venvs\agente-f7-agent-kit\Scripts\python.exe" scripts\copiar_claves_de_f7.py
pause
