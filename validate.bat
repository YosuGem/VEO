@echo off
REM ============================================
REM VEO v2 - Validacion rapida (Windows)
REM ============================================
REM Ejecuta el script de validacion Python.
REM Requisito: Python 3.10+ instalado y en PATH.
REM
REM Uso:
REM   validate.bat
REM   validate.bat --json-only   (solo genera informe, no imprime resumen)
REM ============================================

setlocal enabledelayedexpansion

cd /d "%~dp0"

echo ============================================
echo VEO v2.0.5 - Validacion de distribucion
echo ============================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no esta en el PATH.
    echo Instala Python 3.10+ desde https://python.org
    echo Asegurate de marcar "Add Python to PATH" durante la instalacion.
    exit /b 1
)

echo [OK] Python detectado.
python --version
echo.

if "%1"=="--json-only" (
    venv\Scripts\python validate_windows.py > validation_console.log 2>&1
) else (
    venv\Scripts\python validate_windows.py
)

if errorlevel 1 (
    echo.
    echo [VALIDACION FALLIDA] Revisa los mensajes anteriores.
    exit /b 1
) else (
    echo.
    echo [VALIDACION COMPLETADA]
    exit /b 0
)
