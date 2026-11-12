#!/bin/bash
# ============================================
# VEO v2 - Instalador para Linux/macOS
# ============================================
# Uso: bash install.sh
# ============================================

set -e

echo "============================================"
echo "VEO v2 - Instalador Linux/macOS"
echo "============================================"
echo ""

# Verificar Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 no encontrado."
    echo "Instala Python 3.10+ desde https://python.org"
    exit 1
fi

echo "[OK] Python detectado."
python3 --version
echo ""

# Crear entorno virtual
if [ ! -f "venv/bin/activate" ]; then
    echo "[1/7] Creando entorno virtual..."
    python3 -m venv venv
else
    echo "[1/7] Entorno virtual ya existe."
fi

# Activar entorno virtual
source venv/bin/activate

# Actualizar pip
echo "[2/7] Actualizando pip..."
python3 -m pip install --upgrade pip -q

# Instalar dependencias
echo "[3/7] Instalando dependencias..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt -q
    if [ $? -ne 0 ]; then
        echo "ERROR: Fallo al instalar dependencias."
        exit 1
    fi
else
    echo "AVISO: requirements.txt no encontrado. Instalando deps basicas..."
    pip install numpy scipy pydantic-settings fastapi uvicorn typer rich aiosqlite psutil pytest pytest-asyncio -q
fi

echo "[4/7] Creando estructura de directorios..."
mkdir -p data logs backups cache

echo "[5/7] Verificando dependencias..."
python3 -c "import fastapi, uvicorn, numpy, scipy, typer, rich, aiosqlite; print('[OK] Todas las dependencias instaladas.')"

echo "[6/7] Ejecutando pruebas..."
python3 -m pytest tests/ -q --tb=short || echo "[ADVERTENCIA] Algunas pruebas fallaron. Revisa los errores arriba."

echo "[7/7] Instalacion finalizada."
echo ""
echo "============================================"
echo "INSTALACION COMPLETADA"
echo "============================================"
echo ""
echo "Para iniciar VEO v2:"
echo "   1. Activa el entorno: source venv/bin/activate"
echo "   2. Usa la CLI:         python cli/hermes_cli.py --help"
echo "   3. O la API:           uvicorn api.api_server:app --host 0.0.0.0 --port 8000"
echo ""
echo "Para ejecutar tests:"
echo "   python -m pytest tests/ -v"
echo ""
