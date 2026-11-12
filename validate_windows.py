#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
VEO — Script de Validacion para Windows 11
================================================================================
Comprueba instalacion, CLI, API, dashboard y tests desde un entorno limpio.

Requisitos previos:
  - Windows 11 (o 10)
  - Python 3.10+ instalado y en el PATH (comando 'python' disponible)
  - El ZIP de VEO extraido en un directorio local

Uso:
  cd veo
  python validate_windows.py

El script no modifica la distribucion original ni borra datos del usuario.
Solo crea archivos temporales dentro de su propio directorio de trabajo.
================================================================================
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List

# -----------------------------------------------------------------------------
# CONFIGURACION
# -----------------------------------------------------------------------------

API_PORT = 8765  # Puerto alternativo para no interferir con otros servicios
API_HOST = "127.0.0.1"
API_BASE_URL = f"http://{API_HOST}:{API_PORT}"
TIMEOUT_API_START = 15  # segundos para esperar que la API arranque
TIMEOUT_API_STOP = 5    # segundos para esperar que la API se detenga
TIMEOUT_REQUEST = 5     # segundos para peticiones HTTP

# Nombres de procesos a limpiar (solo los que este script inicie)
PROCESS_NAMES_TO_CLEAN = ["python.exe", "uvicorn.exe"]

# -----------------------------------------------------------------------------
# UTILIDADES
# -----------------------------------------------------------------------------

@dataclass
class TestResult:
    name: str
    status: str          # "PASSED" | "FAILED" | "SKIPPED" | "NOT_RUN"
    message: str = ""
    duration_ms: int = 0
    details: str = ""

@dataclass
class ValidationReport:
    timestamp: str
    platform: str
    python_version: str
    veo_directory: str
    results: List[TestResult] = field(default_factory=list)
    summary: dict = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps({
            "timestamp": self.timestamp,
            "platform": self.platform,
            "python_version": self.python_version,
            "veo_directory": self.veo_directory,
            "results": [
                {
                    "name": r.name,
                    "status": r.status,
                    "message": r.message,
                    "duration_ms": r.duration_ms,
                    "details": r.details,
                }
                for r in self.results
            ],
            "summary": self.summary,
        }, indent=2, ensure_ascii=False)


def log(msg: str) -> None:
    print(f"[VEO-VALIDATE] {msg}")


def run_cmd(
    cmd: list[str],
    cwd: Path | None = None,
    timeout: int = 30,
    capture: bool = True,
) -> tuple[int, str, str]:
    """Ejecuta un comando y devuelve (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=capture,
            text=True,
            timeout=timeout,
            shell=False,
        )
        return result.returncode, result.stdout or "", result.stderr or ""
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"
    except FileNotFoundError:
        return -2, "", f"Command not found: {cmd[0]}"
    except PermissionError:
        return -3, "", f"Permission denied: {cmd[0]}"


def http_get(url: str, timeout: int = TIMEOUT_REQUEST) -> tuple[int, str]:
    """Peticion GET. Devuelve (status_code, body)."""
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as e:
        return -1, str(e.reason)
    except Exception as e:
        return -1, str(e)


def find_processes(name: str) -> list[int]:
    """Busca PIDs de procesos por nombre (Windows)."""
    rc, out, _ = run_cmd(["tasklist", "/FI", f"IMAGENAME eq {name}", "/FO", "CSV"])
    pids = []
    if rc != 0:
        return pids
    for line in out.strip().splitlines()[1:]:
        parts = line.split(",")
        if len(parts) >= 2:
            try:
                pid = int(parts[1].strip('"'))
                pids.append(pid)
            except ValueError:
                pass
    return pids


def kill_process(pid: int) -> bool:
    """Mata un proceso por PID."""
    rc, _, _ = run_cmd(["taskkill", "/PID", str(pid), "/F"], timeout=5)
    return rc == 0


# -----------------------------------------------------------------------------
# VALIDADORES
# -----------------------------------------------------------------------------

def validate_python_version() -> TestResult:
    t0 = time.time()
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    ok = sys.version_info >= (3, 10)
    status = "PASSED" if ok else "FAILED"
    msg = f"Python {version} detectado" if ok else f"Python {version} es menor a 3.10"
    return TestResult(
        name="Requisito: Python 3.10+",
        status=status,
        message=msg,
        duration_ms=int((time.time() - t0) * 1000),
    )


def validate_directory_structure(veo_dir: Path) -> TestResult:
    t0 = time.time()
    required = [
        "cli/hermes_cli.py",
        "api/api_server.py",
        "core/veo_core.py",
        "requirements.txt",
        "install.bat",
        "veo.bat",
        "README.md",
    ]
    missing = []
    for rel in required:
        if not (veo_dir / rel).exists():
            missing.append(rel)
    status = "PASSED" if not missing else "FAILED"
    msg = "Todos los archivos requeridos estan presentes" if not missing else f"Faltan: {', '.join(missing)}"
    return TestResult(
        name="Estructura de directorios",
        status=status,
        message=msg,
        duration_ms=int((time.time() - t0) * 1000),
    )


def validate_installation(veo_dir: Path) -> TestResult:
    t0 = time.time()
    venv_python = veo_dir / "venv" / "Scripts" / "python.exe"
    if venv_python.exists():
        return TestResult(
            name="Instalacion (install.bat)",
            status="SKIPPED",
            message="Entorno virtual ya existe; instalacion omitida",
            duration_ms=int((time.time() - t0) * 1000),
        )

    rc, out, err = run_cmd(["install.bat"], cwd=veo_dir, timeout=120)
    ok = rc == 0 and "INSTALACION COMPLETADA" in (out + err)
    status = "PASSED" if ok else "FAILED"
    msg = "install.bat completo correctamente" if ok else f"install.bat fallo (rc={rc}). stderr: {err[:500]}"
    return TestResult(
        name="Instalacion (install.bat)",
        status=status,
        message=msg,
        duration_ms=int((time.time() - t0) * 1000),
        details=(out + err)[:2000],
    )


def validate_wrapper_help(veo_dir: Path) -> TestResult:
    t0 = time.time()
    rc, out, err = run_cmd(["veo.bat", "--help"], cwd=veo_dir, timeout=15)
    ok = rc == 0 and "Usage:" in out
    status = "PASSED" if ok else "FAILED"
    msg = "veo.bat --help responde correctamente" if ok else f"veo.bat --help fallo (rc={rc})"
    return TestResult(
        name="Wrapper: veo.bat --help",
        status=status,
        message=msg,
        duration_ms=int((time.time() - t0) * 1000),
        details=(out + err)[:1000],
    )


def validate_wrapper_version(veo_dir: Path) -> TestResult:
    t0 = time.time()
    rc, out, err = run_cmd(["veo.bat", "--version"], cwd=veo_dir, timeout=15)
    ok = rc == 0 and ("VEO" in out or "v" in out.lower() or len(out) > 0)
    status = "PASSED" if ok else "FAILED"
    msg = f"Version detectada: {out.strip()}" if ok else f"veo.bat --version fallo (rc={rc})"
    return TestResult(
        name="Wrapper: veo.bat --version",
        status=status,
        message=msg,
        duration_ms=int((time.time() - t0) * 1000),
        details=(out + err)[:500],
    )


def validate_wrapper_mock_status(veo_dir: Path) -> TestResult:
    t0 = time.time()
    rc, out, err = run_cmd(["veo.bat", "--mock", "status"], cwd=veo_dir, timeout=15)
    combined = out + err
    ok = rc == 0 and ("MOCK" in combined or "MockStore" in combined)
    status = "PASSED" if ok else "FAILED"
    msg = "veo.bat --mock status funciona" if ok else f"veo.bat --mock status fallo (rc={rc})"
    return TestResult(
        name="Wrapper: veo.bat --mock status",
        status=status,
        message=msg,
        duration_ms=int((time.time() - t0) * 1000),
        details=combined[:1000],
    )


def validate_cli_from_other_directory(veo_dir: Path) -> TestResult:
    """Prueba que el CLI funciona desde un directorio distinto al de instalacion."""
    t0 = time.time()
    # Crear un directorio temporal
    temp_dir = Path(tempfile.gettempdir()) / "veo_cli_test"
    temp_dir.mkdir(exist_ok=True)
    try:
        # Usar la ruta absoluta a veo.bat
        veo_bat = veo_dir / "veo.bat"
        rc, out, err = run_cmd([str(veo_bat), "--version"], cwd=temp_dir, timeout=15)
        ok = rc == 0 and ("VEO" in out or "v" in out.lower() or len(out) > 0)
        status = "PASSED" if ok else "FAILED"
        msg = "CLI ejecutable desde directorio externo" if ok else f"CLI desde directorio externo fallo (rc={rc})"
        return TestResult(
            name="CLI desde directorio externo",
            status=status,
            message=msg,
            duration_ms=int((time.time() - t0) * 1000),
            details=(out + err)[:500],
        )
    finally:
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass


def validate_api_startup(veo_dir: Path) -> tuple[TestResult, int | None]:
    """Arranca la API, comprueba /health, devuelve (resultado, pid)."""
    t0 = time.time()
    venv_python = veo_dir / "venv" / "Scripts" / "python.exe"
    python_exe = str(venv_python) if venv_python.exists() else "python"

    # Detectar PIDs de python antes de arrancar
    pids_before = set(find_processes("python.exe"))

    # Arrancar la API en segundo plano
    env = os.environ.copy()
    env["SOIS_API_PORT"] = str(API_PORT)
    try:
        proc = subprocess.Popen(
            [python_exe, "api/api_server.py"],
            cwd=veo_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
    except Exception as e:
        return TestResult(
            name="API: arranque",
            status="FAILED",
            message=f"No se pudo iniciar la API: {e}",
            duration_ms=int((time.time() - t0) * 1000),
        ), None

    # Esperar a que la API este lista
    time.sleep(1)
    health_ok = False
    health_body = ""
    for _ in range(TIMEOUT_API_START):
        code, body = http_get(f"{API_BASE_URL}/health")
        if code == 200:
            health_ok = True
            health_body = body
            break
        time.sleep(1)

    # Detectar PIDs despues para saber cual matar
    pids_after = set(find_processes("python.exe"))
    new_pids = list(pids_after - pids_before)
    target_pid = new_pids[0] if new_pids else proc.pid

    status = "PASSED" if health_ok else "FAILED"
    msg = "API arranca y /health responde 200" if health_ok else "API no responde en /health"
    return TestResult(
        name="API: arranque y /health",
        status=status,
        message=msg,
        duration_ms=int((time.time() - t0) * 1000),
        details=health_body[:500],
    ), target_pid


def validate_dashboard(pid: int | None) -> TestResult:
    t0 = time.time()
    if pid is None:
        return TestResult(
            name="Dashboard: accesibilidad",
            status="NOT_RUN",
            message="API no arranco; salto de prueba",
            duration_ms=0,
        )
    code, body = http_get(f"{API_BASE_URL}/dashboard/")
    ok = code == 200 and "<html" in body.lower()
    status = "PASSED" if ok else "FAILED"
    msg = f"Dashboard responde HTTP {code}" if ok else f"Dashboard no accesible (HTTP {code})"
    return TestResult(
        name="Dashboard: accesibilidad",
        status=status,
        message=msg,
        duration_ms=int((time.time() - t0) * 1000),
        details=f"HTTP {code}, body length: {len(body)}" if ok else body[:500],
    )


def validate_swagger(pid: int | None) -> TestResult:
    t0 = time.time()
    if pid is None:
        return TestResult(
            name="Swagger (/docs): accesibilidad",
            status="NOT_RUN",
            message="API no arranco; salto de prueba",
            duration_ms=0,
        )
    code, body = http_get(f"{API_BASE_URL}/docs")
    ok = code == 200 and "swagger" in body.lower()
    status = "PASSED" if ok else "FAILED"
    msg = f"Swagger responde HTTP {code}" if ok else f"Swagger no accesible (HTTP {code})"
    return TestResult(
        name="Swagger (/docs): accesibilidad",
        status=status,
        message=msg,
        duration_ms=int((time.time() - t0) * 1000),
        details=f"HTTP {code}, contiene 'swagger': {ok}",
    )


def validate_redoc(pid: int | None) -> TestResult:
    t0 = time.time()
    if pid is None:
        return TestResult(
            name="Redoc (/redoc): accesibilidad",
            status="NOT_RUN",
            message="API no arranco; salto de prueba",
            duration_ms=0,
        )
    code, body = http_get(f"{API_BASE_URL}/redoc")
    ok = code == 200 and "redoc" in body.lower()
    status = "PASSED" if ok else "FAILED"
    msg = f"Redoc responde HTTP {code}" if ok else f"Redoc no accesible (HTTP {code})"
    return TestResult(
        name="Redoc (/redoc): accesibilidad",
        status=status,
        message=msg,
        duration_ms=int((time.time() - t0) * 1000),
        details=f"HTTP {code}, contiene 'redoc': {ok}",
    )


def validate_api_create_hypothesis(pid: int | None) -> TestResult:
    t0 = time.time()
    if pid is None:
        return TestResult(
            name="API: crear hipotesis",
            status="NOT_RUN",
            message="API no arranco; salto de prueba",
            duration_ms=0,
        )
    url = f"{API_BASE_URL}/api/v1/hipotesis"
    payload = json.dumps({"texto": "Test validacion Windows", "tags": ["test"]}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_REQUEST) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            ok = resp.status == 201 and "id" in body
            status = "PASSED" if ok else "FAILED"
            msg = f"Hipotesis creada (HTTP {resp.status})" if ok else f"Error creando hipotesis (HTTP {resp.status})"
            return TestResult(
                name="API: crear hipotesis",
                status=status,
                message=msg,
                duration_ms=int((time.time() - t0) * 1000),
                details=body[:500],
            )
    except Exception as e:
        return TestResult(
            name="API: crear hipotesis",
            status="FAILED",
            message=f"Excepcion: {e}",
            duration_ms=int((time.time() - t0) * 1000),
        )


def validate_tests(veo_dir: Path) -> TestResult:
    t0 = time.time()
    venv_python = veo_dir / "venv" / "Scripts" / "python.exe"
    python_exe = str(venv_python) if venv_python.exists() else "python"
    rc, out, err = run_cmd(
        [python_exe, "-m", "pytest", "tests/", "--tb=line", "-q", "--color=no"],
        cwd=veo_dir,
        timeout=180,
    )
    combined = out + err
    # Buscar "X passed" en la salida
    match = re.search(r'(\d+) passed', combined)
    passed = int(match.group(1)) if match else 0
    match_fail = re.search(r'(\d+) failed', combined)
    failed = int(match_fail.group(1)) if match_fail else 0

    ok = rc == 0 and passed > 0 and failed == 0
    status = "PASSED" if ok else "FAILED"
    msg = f"{passed} tests pasaron, {failed} fallaron" if match else f"Salida inesperada (rc={rc})"
    return TestResult(
        name="Suite de tests (pytest)",
        status=status,
        message=msg,
        duration_ms=int((time.time() - t0) * 1000),
        details=combined[-2000:],
    )


def validate_cleanup(pid: int | None) -> TestResult:
    t0 = time.time()
    if pid is None:
        return TestResult(
            name="Limpieza de procesos temporales",
            status="NOT_RUN",
            message="No hay procesos que limpiar",
            duration_ms=0,
        )

    killed = kill_process(pid)
    # Esperar a que el proceso desaparezca
    time.sleep(1)
    # Verificar que ya no responde
    code, _ = http_get(f"{API_BASE_URL}/health", timeout=2)
    gone = code == -1

    status = "PASSED" if killed and gone else "FAILED"
    msg = f"Proceso PID {pid} terminado y API ya no responde" if (killed and gone) else f"No se pudo verificar la limpieza del PID {pid}"
    return TestResult(
        name="Limpieza de procesos temporales",
        status=status,
        message=msg,
        duration_ms=int((time.time() - t0) * 1000),
    )


# -----------------------------------------------------------------------------
# ORQUESTACION PRINCIPAL
# -----------------------------------------------------------------------------

def main() -> int:
    veo_dir = Path(__file__).parent.resolve()
    log(f"Directorio de VEO: {veo_dir}")
    log(f"Plataforma: {sys.platform}")
    log(f"Python: {sys.version}")

    report = ValidationReport(
        timestamp=datetime.now().isoformat(),
        platform=sys.platform,
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        veo_directory=str(veo_dir),
    )

    # 1. Requisitos
    log("=== 1. Requisitos ===")
    report.results.append(validate_python_version())
    report.results.append(validate_directory_structure(veo_dir))

    # 2. Instalacion (si no esta instalado)
    log("=== 2. Instalacion ===")
    report.results.append(validate_installation(veo_dir))

    # 3. Wrapper
    log("=== 3. Wrapper veo.bat ===")
    report.results.append(validate_wrapper_help(veo_dir))
    report.results.append(validate_wrapper_version(veo_dir))
    report.results.append(validate_wrapper_mock_status(veo_dir))
    report.results.append(validate_cli_from_other_directory(veo_dir))

    # 4. API + interfaces web
    log("=== 4. API y interfaces web ===")
    api_result, api_pid = validate_api_startup(veo_dir)
    report.results.append(api_result)
    report.results.append(validate_dashboard(api_pid))
    report.results.append(validate_swagger(api_pid))
    report.results.append(validate_redoc(api_pid))
    report.results.append(validate_api_create_hypothesis(api_pid))

    # 5. Tests
    log("=== 5. Suite de tests ===")
    report.results.append(validate_tests(veo_dir))

    # 6. Limpieza
    log("=== 6. Limpieza ===")
    report.results.append(validate_cleanup(api_pid))

    # Resumen
    total = len(report.results)
    passed = sum(1 for r in report.results if r.status == "PASSED")
    failed = sum(1 for r in report.results if r.status == "FAILED")
    skipped = sum(1 for r in report.results if r.status == "SKIPPED")
    not_run = sum(1 for r in report.results if r.status == "NOT_RUN")

    report.summary = {
        "total": total,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "not_run": not_run,
        "overall": "PASSED" if failed == 0 else "FAILED",
    }

    # Guardar informe
    report_path = veo_dir / "validation_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report.to_json())

    # Mostrar resumen en consola
    print("\n" + "=" * 70)
    print("RESUMEN DE VALIDACION")
    print("=" * 70)
    for r in report.results:
        icon = {"PASSED": "[OK]", "FAILED": "[FAIL]", "SKIPPED": "[SKIP]", "NOT_RUN": "[N/A]"}.get(r.status, "[?]")
        print(f"{icon} {r.name}: {r.status} — {r.message}")
    print("-" * 70)
    print(f"Total: {total} | Superadas: {passed} | Fallidas: {failed} | Omitidas: {skipped} | No ejecutadas: {not_run}")
    print(f"Resultado global: {report.summary['overall']}")
    print(f"Informe guardado en: {report_path}")
    print("=" * 70)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
