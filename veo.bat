@echo off
REM ============================================
REM VEO v2 - Wrapper Windows
REM ============================================
REM Uso: veo.bat [opciones] [comando] [args...]
REM Ejemplo: veo.bat --mock status
REM          veo.bat --mock hypothesis list
REM ============================================

setlocal enabledelayedexpansion

REM Directorio donde esta este script
set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

REM Detectar interprete Python: entorno virtual primero
if exist "%SCRIPT_DIR%\venv\Scripts\python.exe" (
    set "PYTHON=%SCRIPT_DIR%\venv\Scripts\python.exe"
) else if exist "%SCRIPT_DIR%\.venv\Scripts\python.exe" (
    set "PYTHON=%SCRIPT_DIR%\.venv\Scripts\python.exe"
) else (
    set "PYTHON=python"
)

REM Ejecutar la CLI con todos los argumentos
"%PYTHON%" "%SCRIPT_DIR%\cli\hermes_cli.py" %*

exit /b %errorlevel%
