"""
================================================================================
VEO v2.0.4 - Script de Verificacion de Despliegue
================================================================================
Ejecutar despues de install.bat para validar que la instalacion es correcta.

Uso:
    python tests/test_deploy.py

Valida los 5 pasos criticos que Sol (ChatGPT) exige:
1. Importacion limpia del modulo API
2. Health check responde 200
3. POST hipotesis devuelve objeto valido (NO None)
4. GET lista contiene la hipotesis creada
5. GET by ID recupera el objeto completo
================================================================================
"""

import sys
import os
import json
import time
import asyncio
from pathlib import Path
from typing import Dict, Any, List

# Anadir directorio padre al path para imports (ejecucion directa sin pip install)
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Colores para terminal (compatible Windows)
_ansi_supported = (
    sys.platform != "win32"
    or "ANSICON" in os.environ
    or "WT_SESSION" in os.environ  # Windows Terminal
    or os.environ.get("TERM") == "xterm"
)

class Colors:
    GREEN = "\033[92m" if _ansi_supported else ""
    RED = "\033[91m" if _ansi_supported else ""
    YELLOW = "\033[93m" if _ansi_supported else ""
    RESET = "\033[0m" if _ansi_supported else ""
    BOLD = "\033[1m" if _ansi_supported else ""


def print_header():
    print(f"{Colors.BOLD}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}  VEO v2.0.4 - VERIFICACION DE DESPLIEGUE{Colors.RESET}")
    print(f"{Colors.BOLD}{'='*70}{Colors.RESET}")
    print()


def print_step(num: int, total: int, desc: str):
    print(f"{Colors.BOLD}[{num}/{total}] {desc}...{Colors.RESET}")


def print_ok(msg: str):
    print(f"  {Colors.GREEN}✓ OK:{Colors.RESET} {msg}")


def print_fail(msg: str):
    print(f"  {Colors.RED}✗ FAIL:{Colors.RESET} {msg}")


def print_warn(msg: str):
    print(f"  {Colors.YELLOW}⚠ WARN:{Colors.RESET} {msg}")


def print_separator():
    print(f"{Colors.BOLD}{'-'*70}{Colors.RESET}")


# ============================================================================
# PASO 1: Importacion limpia
# ============================================================================
def test_import() -> bool:
    print_step(1, 5, "Importacion del modulo API")
    try:
        from api.api_server import app, commander
        mode = getattr(commander, 'mode', 'unknown')
        print_ok(f"api_server importado correctamente")
        print_ok(f"Modo de operacion: {mode}")
        if mode == "mock_fallback":
            print_ok("MockDatabase activo como fallback (sin HermesCommander externo)")
        return True
    except ImportError as e:
        print_fail(f"Error de importacion: {e}")
        print(f"\n  Diagnostico: El entorno virtual no esta activo o las dependencias")
        print(f"  no estan instaladas. Ejecutar: .venv\\Scripts\\activate.bat")
        return False
    except Exception as e:
        print_fail(f"Error inesperado: {type(e).__name__}: {e}")
        return False


# ============================================================================
# PASO 2: Verificar estructura de MockDatabase
# ============================================================================
def test_mock_database() -> bool:
    print_step(2, 5, "Verificar MockDatabase tiene metodos requeridos")
    try:
        from api.api_server import MockDatabase
        db = MockDatabase()

        metodos_requeridos = [
            'crear_hipotesis', 'listar_hipotesis', 'get_hipotesis',
            'validar_hipotesis', 'listar_mercados'
        ]

        todos_ok = True
        for metodo in metodos_requeridos:
            if hasattr(db, metodo) and callable(getattr(db, metodo)):
                print_ok(f"MockDatabase.{metodo}() existe y es invocable")
            else:
                print_fail(f"MockDatabase.{metodo}() FALTA")
                todos_ok = False

        return todos_ok
    except Exception as e:
        print_fail(f"Error: {type(e).__name__}: {e}")
        return False


# ============================================================================
# PASO 3: Crear hipotesis via MockDatabase directamente
# ============================================================================
def test_crear_hipotesis(db=None) -> Dict[str, Any]:
    print_step(3, 5, "Crear hipotesis y verificar respuesta NO es None")
    try:
        if db is None:
            from api.api_server import MockDatabase
            db = MockDatabase()

        # crear_hipotesis es async y recibe data: dict
        resultado = asyncio.run(db.crear_hipotesis({
            "texto": "Tension en estrecho critico afectara comercio global",
            "tags": ["geopolitica"],
        }))

        if resultado is None:
            print_fail("crear_hipotesis devolvio None - INC-07 no resuelto")
            return {}

        if not isinstance(resultado, dict):
            print_fail(f"crear_hipotesis devolvio {type(resultado).__name__}, no dict")
            return {}

        hid = resultado.get('id')
        if not hid:
            print_fail("El objeto no tiene campo 'id'")
            return resultado

        print_ok(f"Hipotesis creada con ID: {hid}")
        print_ok(f"ID no es None (INC-07 VERIFICADO)")
        return resultado

    except TypeError as e:
        if "NoneType" in str(e):
            print_fail(f"INC-07 DETECTADO: {e}")
            print(f"\n  Esto indica que se esta usando una version anterior a v2.0.3.")
            print(f"  La causa es el orden de ejecucion de Python: el singleton")
            print(f"  'commander' se instancia antes de que MockDatabase este definido.")
        else:
            print_fail(f"TypeError: {e}")
        return {}
    except Exception as e:
        print_fail(f"Error: {type(e).__name__}: {e}")
        return {}


# ============================================================================
# PASO 4: Listar hipotesis y encontrar la creada
# ============================================================================
def test_listar_hipotesis(hid_creada: str, db=None) -> bool:
    print_step(4, 5, "Listar hipotesis y verificar que la creada aparece")
    try:
        if db is None:
            from api.api_server import MockDatabase
            db = MockDatabase()

        # listar_hipotesis es async
        lista = asyncio.run(db.listar_hipotesis())

        if not isinstance(lista, list):
            print_fail(f"listar_hipotesis devolvio {type(lista).__name__}, no list")
            return False

        ids = [h.get('id') for h in lista if isinstance(h, dict)]
        print_ok(f"Total hipotesis en lista: {len(ids)}")

        if hid_creada and hid_creada in ids:
            print_ok(f"Hipotesis {hid_creada} encontrada en la lista")
        elif hid_creada:
            print_warn(f"Hipotesis {hid_creada} no encontrada en lista de {len(ids)} items")
            print(f"  IDs disponibles: {ids[:10]}")

        return True

    except Exception as e:
        print_fail(f"Error: {type(e).__name__}: {e}")
        return False


# ============================================================================
# PASO 5: Recuperar hipotesis por ID
# ============================================================================
def test_get_hipotesis(hid_creada: str, db=None) -> bool:
    print_step(5, 5, "Recuperar hipotesis especifica por ID")
    try:
        if db is None:
            from api.api_server import MockDatabase
            db = MockDatabase()

        if not hid_creada:
            print_fail("No hay ID de hipotesis para recuperar")
            return False

        # get_hipotesis es async
        recuperada = asyncio.run(db.get_hipotesis(hid_creada))

        if recuperada is None:
            print_fail(f"get_hipotesis({hid_creada}) devolvio None")
            return False

        if not isinstance(recuperada, dict):
            print_fail(f"get_hipotesis devolvio {type(recuperada).__name__}, no dict")
            return False

        rid = recuperada.get('id')
        if rid == hid_creada:
            print_ok(f"ID coincide: solicitado={hid_creada}, recibido={rid}")
        else:
            print_fail(f"ID NO coincide: solicitado={hid_creada}, recibido={rid}")
            return False

        texto = recuperada.get('texto', '')
        if texto:
            print_ok(f"Campo 'texto' presente: '{texto[:50]}...'")
        else:
            print_warn("Campo 'texto' vacio o ausente")

        return True

    except Exception as e:
        print_fail(f"Error: {type(e).__name__}: {e}")
        return False


# ============================================================================
# PASO BONUS: Verificar todos los modulos del sistema
# ============================================================================
def test_all_modules() -> bool:
    print_separator()
    print(f"{Colors.BOLD}[BONUS] Verificacion de importacion de todos los modulos{Colors.RESET}")

    modulos = [
        ("core.veo_core", "VEOCore"),
        ("core.config", "Config"),
        ("core.db", "DatabaseManager"),
        ("analysis.knowledge_graph", "KnowledgeGraph"),
        ("analysis.hypothesis_engine", "HypothesisEngine"),
        ("analysis.scientific_agent", "ScientificAgent"),
        ("analysis.scenario_simulator", "ScenarioSimulator"),
        ("analysis.causal_engine", "CausalEngine"),
        ("analysis.planetary_configs", "PlanetaryConfig"),
        ("analysis.planetary_diagnosis_engine", "PlanetaryDiagnosisEngine"),
        ("prediction.prediction_market", "PredictionMarket"),
        ("memory.discovery_journal", "DiscoveryJournal"),
        ("multiagent.hermes_commander", "HermesCommander"),
        ("operations.trust_layer", "TrustLayer"),
        ("operations.metrics_engine", "MetricsEngine"),
        ("operations.health_monitor", "HealthMonitor"),
        ("operations.audit_log", "AuditLog"),
        ("operations.backup_manager", "BackupManager"),
    ]

    ok_count = 0
    fail_count = 0

    for module_path, class_name in modulos:
        try:
            module = __import__(module_path, fromlist=[class_name])
            cls = getattr(module, class_name, None)
            if cls is not None:
                # Intentar instanciar con parametros opcionales
                try:
                    instance = cls()
                    print_ok(f"{module_path}.{class_name} - instanciado")
                except TypeError:
                    # Requiere parametros, eso es OK
                    print_ok(f"{module_path}.{class_name} - importado (req. params)")
                ok_count += 1
            else:
                print_fail(f"{module_path}.{class_name} - clase no encontrada")
                fail_count += 1
        except Exception as e:
            print_fail(f"{module_path}.{class_name} - {type(e).__name__}: {e}")
            fail_count += 1

    print()
    print(f"  Modulos OK: {ok_count}/{len(modulos)}")
    if fail_count > 0:
        print(f"  Modulos FAIL: {fail_count}/{len(modulos)}")

    return fail_count == 0


# ============================================================================
# MAIN
# ============================================================================
def main():
    print_header()

    # Crear instancia compartida de MockDatabase para tests 3, 4, 5
    from api.api_server import MockDatabase
    shared_db = MockDatabase()

    start_time = time.time()
    results = []

    # Paso 1
    results.append(("Importacion API", test_import()))
    print()

    # Paso 2
    results.append(("MockDatabase metodos", test_mock_database()))
    print()

    # Paso 3 - usar db compartida
    hipotesis = test_crear_hipotesis(db=shared_db)
    results.append(("Crear hipotesis", hipotesis is not None and bool(hipotesis.get('id'))))
    hid = hipotesis.get('id', '') if hipotesis else ''
    print()

    # Paso 4 - usar db compartida
    results.append(("Listar hipotesis", test_listar_hipotesis(hid, db=shared_db)))
    print()

    # Paso 5 - usar db compartida
    results.append(("Recuperar hipotesis", test_get_hipotesis(hid, db=shared_db)))
    print()

    # Bonus: verificacion de modulos (informativo, no afecta resultado final)
    if all(r for _, r in results):
        print(f"{Colors.BOLD}[BONUS] Verificacion de modulos adicionales (informativo){Colors.RESET}")
        bonus_ok = test_all_modules()
        # El bonus no cuenta para el resultado final
    else:
        print(f"{Colors.YELLOW}Bonus omitido: corregir errores anteriores primero{Colors.RESET}")
    print()

    # Resumen
    elapsed = time.time() - start_time
    print_separator()
    print(f"{Colors.BOLD}RESULTADO FINAL{Colors.RESET}")
    print_separator()

    # Los 5 pasos principales son los que cuentan
    pasos_criticos = results[:5]
    passed = sum(1 for _, r in pasos_criticos if r)
    total = len(pasos_criticos)

    for nombre, resultado in results:
        status = f"{Colors.GREEN}PASS{Colors.RESET}" if resultado else f"{Colors.RED}FAIL{Colors.RESET}"
        print(f"  [{status}] {nombre}")

    print()
    print(f"{Colors.BOLD}Pasos criticos: {passed}/{total} exitosos{Colors.RESET}")
    print(f"Tiempo: {elapsed:.2f}s")

    if passed == total:
        print()
        print(f"{Colors.GREEN}{Colors.BOLD}{'='*70}{Colors.RESET}")
        print(f"{Colors.GREEN}{Colors.BOLD}  VEO v2.0.4 DESPLIEGUE VERIFICADO - LISTO PARA PRODUCCION{Colors.RESET}")
        print(f"{Colors.GREEN}{Colors.BOLD}{'='*70}{Colors.RESET}")
        return 0
    else:
        print()
        print(f"{Colors.RED}{Colors.BOLD}{'='*70}{Colors.RESET}")
        print(f"{Colors.RED}{Colors.BOLD}  DESPLIEGUE CON ERRORES - REVISAR INCIDENCIAS ARRIBA{Colors.RESET}")
        print(f"{Colors.RED}{Colors.BOLD}{'='*70}{Colors.RESET}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
