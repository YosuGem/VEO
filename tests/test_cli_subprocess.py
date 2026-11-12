"""
Tests de ejecucion real de la CLI via subprocess.

Estos tests ejecutan `python cli/hermes_cli.py` como proceso externo
y verifican:
  - Codigo de salida 0
  - Salida esperada en stdout/stderr
  - Ausencia de excepciones no controladas

Cobertura:
  - Modo --mock (MockStore, datos persistentes en memoria)
  - Modo Commander (VEOCore real, stateless)
  - Comandos: status, hypothesis list, hypothesis show, validate, system health
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

# Ruta base del proyecto
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLI_PATH = PROJECT_ROOT / "cli" / "hermes_cli.py"
PYTHON = sys.executable


def run_cli(*args: str, timeout: int = 15) -> subprocess.CompletedProcess[str]:
    """Ejecuta la CLI con los argumentos dados y devuelve el resultado."""
    cmd = [PYTHON, str(CLI_PATH), *args]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(PROJECT_ROOT),
    )
    return result


class TestCLISubprocessMock:
    """Tests de CLI en modo --mock (MockStore, sin dependencias externas)."""

    def test_mock_status_exit_code(self) -> None:
        """status --mock debe retornar codigo 0."""
        result = run_cli("--mock", "status")
        assert result.returncode == 0, f"stderr: {result.stderr}"

    def test_mock_status_output(self) -> None:
        """status --mock debe mostrar 'Estado del Sistema' y datos de hipotesis."""
        result = run_cli("--mock", "status")
        assert "Estado del Sistema" in result.stdout or "ORACLE" in result.stdout
        assert "Hipotesis" in result.stdout or "Mercados" in result.stdout

    def test_mock_hypothesis_list_exit_code(self) -> None:
        """hypothesis list --mock debe retornar codigo 0."""
        result = run_cli("--mock", "hypothesis", "list")
        assert result.returncode == 0, f"stderr: {result.stderr}"

    def test_mock_hypothesis_list_output(self) -> None:
        """hypothesis list --mock debe mostrar hipotesis pre-cargadas."""
        result = run_cli("--mock", "hypothesis", "list")
        assert "H-001" in result.stdout or "Hipotesis del Sistema" in result.stdout

    def test_mock_hypothesis_show_known(self) -> None:
        """hypothesis show H-001 --mock debe mostrar detalle."""
        result = run_cli("--mock", "hypothesis", "show", "H-001")
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "H-001" in result.stdout or "Detalle" in result.stdout

    def test_mock_hypothesis_show_unknown(self) -> None:
        """hypothesis show ID_INEXISTENTE --mock debe manejar gracefully."""
        result = run_cli("--mock", "hypothesis", "show", "H-XYZ-999")
        # Puede retornar 0 con mensaje de error o 1; ambos son aceptables si no hay traceback
        assert "Traceback" not in result.stderr
        assert "Error" in result.stdout or "No encontrada" in result.stdout or result.returncode != 0

    def test_mock_validate_known(self) -> None:
        """validate H-001 --mock debe ejecutar validacion sin crash."""
        result = run_cli("--mock", "validate", "H-001")
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "Traceback" not in result.stderr
        assert "Validacion" in result.stdout or "Cientifico" in result.stdout or "Esceptico" in result.stdout

    def test_mock_market_list(self) -> None:
        """market list --mock debe retornar lista de mercados."""
        result = run_cli("--mock", "market", "list")
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "Traceback" not in result.stderr

    def test_mock_version_flag(self) -> None:
        """--version debe mostrar version sin error."""
        result = run_cli("--version")
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "2.0.4" in result.stdout

    def test_mock_help(self) -> None:
        """--help debe mostrar ayuda sin error."""
        result = run_cli("--help")
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "Commands" in result.stdout or "Comandos" in result.stdout or "status" in result.stdout

    def test_mock_hypothesis_create(self) -> None:
        """hypothesis create --mock debe crear hipotesis sin crash."""
        result = run_cli("--mock", "hypothesis", "create", "Test subprocess CLI")
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "Traceback" not in result.stderr
        assert "creada" in result.stdout.lower() or "H-" in result.stdout


class TestCLISubprocessCommander:
    """Tests de CLI en modo Commander (VEOCore real, stateless)."""

    def test_commander_status_exit_code(self) -> None:
        """status (sin --mock) debe iniciar VEOCore y retornar 0."""
        result = run_cli("status")
        assert result.returncode == 0, f"stderr: {result.stderr}"

    def test_commander_status_output(self) -> None:
        """status debe mostrar estado del sistema con VEOCore activo."""
        result = run_cli("status")
        assert "ORACLE" in result.stdout or "Estado del Sistema" in result.stdout
        assert "Traceback" not in result.stderr

    def test_commander_hypothesis_list(self) -> None:
        """hypothesis list (sin --mock) debe funcionar con VEOCore."""
        result = run_cli("hypothesis", "list")
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "Traceback" not in result.stderr

    def test_commander_hypothesis_create_and_list(self) -> None:
        """Crear hipotesis en modo Commander y listar (stateless: no persiste)."""
        # Crear
        result_create = run_cli("hypothesis", "create", "Test desde subprocess commander")
        # En modo Commander degradado (sin VEOCore), la creacion puede fallar
        # Lo importante es que no hay traceback y el error es controlado
        assert "Traceback" not in result_create.stderr
        if result_create.returncode != 0:
            assert "No se pudo crear" in result_create.stdout or "dudoso" in result_create.stdout

        # Listar (stateless: la hipotesis creada no persiste entre procesos)
        result_list = run_cli("hypothesis", "list")
        assert result_list.returncode == 0, f"stderr: {result_list.stderr}"
        # En modo stateless, la lista puede estar vacia; lo importante es que no crashea
        assert "Traceback" not in result_list.stderr

    def test_commander_market_list(self) -> None:
        """market list (sin --mock) debe retornar lista de mercados."""
        result = run_cli("market", "list")
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "Traceback" not in result.stderr

    def test_commander_no_traceback_on_invalid_hypothesis(self) -> None:
        """Mostrar hipotesis inexistente en Commander no debe generar traceback."""
        result = run_cli("hypothesis", "show", "H-INEXISTENTE-999")
        assert "Traceback" not in result.stderr
        # stdout puede mostrar error formateado o tabla vacia


class TestCLIAgenteIndependiente:
    """Tests que demuestran que la CLI es usable por cualquier agente, no solo Hermes."""

    def test_cli_no_requiere_nombre_hermes(self) -> None:
        """La CLI se ejecuta sin verificar identidad del agente llamante."""
        result = run_cli("--mock", "status")
        assert result.returncode == 0
        # No hay prompt de autenticacion, no hay chequeo de nombre de agente
        assert "autenticar" not in result.stdout.lower()
        assert "hermes" not in result.stdout.lower() or "HermesCommander" not in result.stdout

    def test_cli_comandos_genéricos(self) -> None:
        """Los comandos disponibles son genericos (no especificos de Hermes)."""
        result = run_cli("--help")
        assert result.returncode == 0
        # Los comandos deben ser genericos
        assert "status" in result.stdout
        assert "hypothesis" in result.stdout or "hipotesis" in result.stdout
        # No debe haber comandos como 'hermes_login', 'hermes_config', etc.
        assert "hermes_login" not in result.stdout
        assert "hermes_profile" not in result.stdout
