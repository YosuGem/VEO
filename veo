#!/usr/bin/env bash
# ============================================
# VEO v2 - Wrapper Linux/macOS
# ============================================
# Uso: ./veo [opciones] [comando] [args...]
# Ejemplo: ./veo --mock status
#          ./veo --mock hypothesis list
# ============================================

# Directorio donde esta este script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Detectar interprete Python: entorno virtual primero
if [ -f "$SCRIPT_DIR/venv/bin/python" ]; then
    PYTHON="$SCRIPT_DIR/venv/bin/python"
elif [ -f "$SCRIPT_DIR/.venv/bin/python" ]; then
    PYTHON="$SCRIPT_DIR/.venv/bin/python"
else
    PYTHON="python3"
fi

# Ejecutar la CLI con todos los argumentos
exec "$PYTHON" "$SCRIPT_DIR/cli/hermes_cli.py" "$@"
