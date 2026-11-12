@echo off
REM ============================================
REM VEO v2 - Instalador para Windows
REM ============================================
REM Uso: Doble click o ejecutar desde cmd:
REM        install.bat
REM ============================================

echo ============================================
echo VEO v2 - Instalador Windows
echo ============================================
echo.

REM Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python no encontrado.
    echo Instala Python 3.10+ desde https://python.org
echo y asegurate de marcar "Add Python to PATH".
    pause
    exit /b 1
)

echo [OK] Python detectado.
python --version
echo.

REM Crear entorno virtual
if not exist "venv\Scripts\activate.bat" (
    echo [1/7] Creando entorno virtual...
    python -m venv venv
    if errorlevel 1 (
        echo ERROR: No se pudo crear el entorno virtual.
        pause
        exit /b 1
    )
) else (
    echo [1/7] Entorno virtual ya existe.
)

REM Activar entorno virtual
call venv\Scripts\activate.bat

REM Actualizar pip
echo [2/7] Actualizando pip...
python -m pip install --upgrade pip -q

REM Instalar dependencias
echo [3/7] Instalando dependencias...
if exist "requirements.txt" (
    pip install -r requirements.txt -q
    if errorlevel 1 (
        echo ERROR: Fallo al instalar dependencias.
        pause
        exit /b 1
    )
) else (
    echo AVISO: requirements.txt no encontrado. Instalando deps basicas...
    pip install numpy scipy pydantic-settings fastapi uvicorn typer rich aiosqlite psutil pytest pytest-asyncio -q
)

echo [4/7] Creando estructura de directorios y verificando...
if not exist "data" mkdir data
if not exist "logs" mkdir logs
if not exist "backups" mkdir backups
if not exist "cache" mkdir cache

echo [5/7] Verificando dependencias...
python -c "import fastapi, uvicorn, numpy, scipy, typer, rich, aiosqlite; print('[OK] Todas las dependencias instaladas.')"

echo [6/7] Ejecutando pruebas...
venv\Scripts\python -m pytest tests/ -q --tb=short
IF ERRORLEVEL 1 (
    echo [ADVERTENCIA] Algunas pruebas fallaron. Revisa los errores arriba.
) ELSE (
    echo [OK] Todas las pruebas pasaron.
)

echo [7/7] Instalacion finalizada.
echo.
echo ============================================
echo INSTALACION COMPLETADA
echo ============================================
echo.
echo Para iniciar VEO v2:
echo   1. Activa el entorno: venv\Scripts\activate.bat
echo   2. Usa la CLI:        python cli\hermes_cli.py --help
echo   3. O la API:          python api\api_server.py
echo   4. O con uvicorn:     uvicorn api.api_server:app --host 0.0.0.0 --port 8000
echo.
echo Wrapper rapido (desde el directorio raiz):
echo   veo.bat --mock status
echo.
echo Para ejecutar tests:
echo   python -m pytest tests\ -v
echo.
pause
