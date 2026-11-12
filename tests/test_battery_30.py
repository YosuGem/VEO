"""
================================================================================
VEO v2.0.4B - BATERIA OFICIAL DE 30 PRUEBAS FUNCIONALES
================================================================================
Script de pruebas automatizadas para la API REST de VEO.

Uso:
    python tests/test_battery_30.py

Requisitos:
    pip install requests

El servidor debe estar corriendo en localhost:8000
================================================================================
"""

import requests
import sys
import time
from typing import Any, Dict, List, Optional, Callable, Tuple

# =============================================================================
# CONFIGURACION
# =============================================================================
BASE_URL = "http://localhost:8000"
TIMEOUT = 10

# =============================================================================
# COLORES (compatible Windows/Linux)
# =============================================================================
class Colors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"

    @classmethod
    def disable(cls):
        """Deshabilita colores para salidas no compatibles."""
        cls.HEADER = ""
        cls.OKBLUE = ""
        cls.OKCYAN = ""
        cls.OKGREEN = ""
        cls.WARNING = ""
        cls.FAIL = ""
        cls.ENDC = ""
        cls.BOLD = ""
        cls.UNDERLINE = ""


# Intenta habilitar colores en Windows
if sys.platform == "win32":
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        Colors.disable()


# =============================================================================
# VARIABLES GLOBALES PARA COMPARTIR IDs ENTRE PRUEBAS
# =============================================================================
STATE: Dict[str, Any] = {
    "hipotesis_ids": [],
    "escenario_ids": [],
    "mercado_id": None,
}


# =============================================================================
# FUNCIONES AUXILIARES
# =============================================================================
def log(msg: str):
    print(msg)


def print_banner():
    sep = "=" * 56
    banner = (
        f"{Colors.BOLD}{Colors.OKCYAN}{sep}\n"
        f"VEO v2.0.4B - BATERIA OFICIAL 30 PRUEBAS\n"
        f"{sep}{Colors.ENDC}"
    )
    log(banner)


def http_request(
    method: str,
    url: str,
    body: Optional[Dict] = None,
    params: Optional[Dict] = None,
) -> Tuple[int, Optional[Dict], Optional[str]]:
    """
    Ejecuta una peticion HTTP y retorna (status_code, json_body, error).
    Si ocurre un error de conexion, error sera no-nulo.
    """
    try:
        full_url = f"{BASE_URL}{url}"
        kwargs = {"timeout": TIMEOUT}
        if body is not None:
            kwargs["json"] = body
        if params is not None:
            kwargs["params"] = params

        response = requests.request(method, full_url, **kwargs)
        try:
            json_data = response.json()
        except ValueError:
            json_data = None
        return response.status_code, json_data, None

    except requests.exceptions.ConnectionError as e:
        return 0, None, f"ConnectionError: No se pudo conectar a {BASE_URL} - {e}"
    except requests.exceptions.Timeout:
        return 0, None, f"Timeout: El servidor no respondio en {TIMEOUT}s"
    except Exception as e:
        return 0, None, f"RequestException: {type(e).__name__}: {e}"


# =============================================================================
# DEFINICION DE LAS 30 PRUEBAS
# =============================================================================
# Cada prueba es un dict con:
#   name: str - codigo de la prueba (P001..P030)
#   description: str - descripcion legible
#   fn: callable - funcion que ejecuta la prueba, retorna (ok: bool, detail: str)


def test_p001() -> Tuple[bool, str]:
    """P001: GET /health -> 200, {"status": "healthy"}"""
    status, data, err = http_request("GET", "/health")
    if err:
        return False, err
    if status != 200:
        return False, f"Esperado 200, recibido {status}"
    if data is None:
        return False, "Respuesta JSON vacia"
    if data.get("status") != "healthy":
        return False, f"status != healthy, got: {data.get('status')}"
    return True, "OK"


def test_p002() -> Tuple[bool, str]:
    """P002: GET /api/v1/hipotesis -> 200, lista con H-001..H-005"""
    status, data, err = http_request("GET", "/api/v1/hipotesis")
    if err:
        return False, err
    if status != 200:
        return False, f"Esperado 200, recibido {status}"
    if not isinstance(data, list):
        return False, f"Esperada lista, recibido: {type(data).__name__}"
    ids = [h.get("id") for h in data if isinstance(h, dict)]
    expected_ids = ["H-001", "H-002", "H-003", "H-004", "H-005"]
    for eid in expected_ids:
        if eid not in ids:
            return False, f"Hipotesis inicial {eid} no encontrada en lista. IDs: {ids}"
    return True, f"OK, {len(data)} hipotesis iniciales encontradas"


def test_p003() -> Tuple[bool, str]:
    """P003: POST /api/v1/hipotesis -> 201, respuesta con campo 'id'"""
    body = {
        "texto": "Hipotesis de prueba automatizada #1 sobre inteligencia artificial",
        "tags": ["ia", "automatizacion"],
    }
    status, data, err = http_request("POST", "/api/v1/hipotesis", body=body)
    if err:
        return False, err
    if status != 201:
        return False, f"Esperado 201, recibido {status}"
    if data is None or not isinstance(data, dict):
        return False, "Respuesta no es JSON valido o no es dict"
    hid = data.get("id")
    if not hid:
        return False, f"Campo 'id' ausente o vacio en respuesta: {data}"
    STATE["hipotesis_ids"].append(hid)
    return True, f"OK, hipotesis creada: {hid}"


def test_p004() -> Tuple[bool, str]:
    """P004: GET /api/v1/hipotesis/{id_creada} -> 200, id coincide"""
    if not STATE["hipotesis_ids"]:
        return False, "No hay ID de hipotesis creada (depende de P003)"
    hid = STATE["hipotesis_ids"][0]
    status, data, err = http_request("GET", f"/api/v1/hipotesis/{hid}")
    if err:
        return False, err
    if status != 200:
        return False, f"Esperado 200, recibido {status}"
    if data is None or not isinstance(data, dict):
        return False, "Respuesta no es dict valido"
    if data.get("id") != hid:
        return False, f"ID no coincide: esperado {hid}, recibido {data.get('id')}"
    return True, f"OK, hipotesis {hid} recuperada correctamente"


def test_p005() -> Tuple[bool, str]:
    """P005: GET /api/v1/hipotesis -> 200, lista incluye hipotesis creada"""
    if not STATE["hipotesis_ids"]:
        return False, "No hay ID de hipotesis creada (depende de P003)"
    hid = STATE["hipotesis_ids"][0]
    status, data, err = http_request("GET", "/api/v1/hipotesis")
    if err:
        return False, err
    if status != 200:
        return False, f"Esperado 200, recibido {status}"
    if not isinstance(data, list):
        return False, f"Esperada lista, recibido: {type(data).__name__}"
    ids = [h.get("id") for h in data if isinstance(h, dict)]
    if hid not in ids:
        return False, f"Hipotesis {hid} no encontrada en lista general. IDs: {ids}"
    return True, f"OK, hipotesis {hid} confirmada en lista de {len(data)} items"


def test_p006() -> Tuple[bool, str]:
    """P006: POST /api/v1/hipotesis (body 2) -> 201, otra hipotesis creada"""
    body = {
        "texto": "Segunda hipotesis de prueba sobre mercados emergentes",
        "tags": ["economia", "mercados"],
    }
    status, data, err = http_request("POST", "/api/v1/hipotesis", body=body)
    if err:
        return False, err
    if status != 201:
        return False, f"Esperado 201, recibido {status}"
    if data is None or not isinstance(data, dict):
        return False, "Respuesta no es JSON valido"
    hid = data.get("id")
    if not hid:
        return False, f"Campo 'id' ausente: {data}"
    STATE["hipotesis_ids"].append(hid)
    return True, f"OK, segunda hipotesis creada: {hid}"


def test_p007() -> Tuple[bool, str]:
    """P007: POST /api/v1/hipotesis/{id1}/validar -> 200, hipotesis validada"""
    if len(STATE["hipotesis_ids"]) < 1:
        return False, "No hay hipotesis ID 1 (depende de P003)"
    hid = STATE["hipotesis_ids"][0]
    status, data, err = http_request("POST", f"/api/v1/hipotesis/{hid}/validar")
    if err:
        return False, err
    if status != 200:
        return False, f"Esperado 200, recibido {status}"
    return True, f"OK, hipotesis {hid} validada"


def test_p008() -> Tuple[bool, str]:
    """P008: POST /api/v1/hipotesis/{id2}/validar -> 200, hipotesis validada"""
    if len(STATE["hipotesis_ids"]) < 2:
        return False, "No hay hipotesis ID 2 (depende de P006)"
    hid = STATE["hipotesis_ids"][1]
    status, data, err = http_request("POST", f"/api/v1/hipotesis/{hid}/validar")
    if err:
        return False, err
    if status != 200:
        return False, f"Esperado 200, recibido {status}"
    return True, f"OK, hipotesis {hid} validada"


def test_p009() -> Tuple[bool, str]:
    """P009: GET /api/v1/mercados -> 200, lista con mercados"""
    status, data, err = http_request("GET", "/api/v1/mercados")
    if err:
        return False, err
    if status != 200:
        return False, f"Esperado 200, recibido {status}"
    if not isinstance(data, list):
        return False, f"Esperada lista, recibido: {type(data).__name__}"
    if len(data) < 1:
        return False, "Lista de mercados vacia"
    expected_ids = ["M-001", "M-002", "M-003"]
    ids = [m.get("id") for m in data if isinstance(m, dict)]
    for eid in expected_ids:
        if eid not in ids:
            return False, f"Mercado inicial {eid} no encontrado. IDs: {ids}"
    return True, f"OK, {len(data)} mercados encontrados"


def test_p010() -> Tuple[bool, str]:
    """P010: GET /api/v1/mercados/{mid} -> 200, mercado encontrado"""
    status, data, err = http_request("GET", "/api/v1/mercados/M-001")
    if err:
        return False, err
    if status != 200:
        return False, f"Esperado 200, recibido {status}"
    if data is None or not isinstance(data, dict):
        return False, "Respuesta no es dict valido"
    if data.get("id") != "M-001":
        return False, f"ID no coincide: esperado M-001, recibido {data.get('id')}"
    return True, "OK, mercado M-001 recuperado"


def test_p011() -> Tuple[bool, str]:
    """P011: POST /api/v1/escenarios (body) -> 201, escenario creado"""
    body = {
        "nombre": "Escenario de prueba automatizado #1",
        "descripcion": "Escenario generado por la bateria de pruebas",
        "parametros": {"tasa_crecimiento": 0.05, "volatilidad": 0.15},
    }
    status, data, err = http_request("POST", "/api/v1/escenarios", body=body)
    if err:
        return False, err
    if status != 201:
        return False, f"Esperado 201, recibido {status}"
    if data is None or not isinstance(data, dict):
        return False, "Respuesta no es JSON valido"
    sid = data.get("id")
    if not sid:
        return False, f"Campo 'id' ausente: {data}"
    STATE["escenario_ids"].append(sid)
    return True, f"OK, escenario creado: {sid}"


def test_p012() -> Tuple[bool, str]:
    """P012: GET /api/v1/escenarios -> 200, lista con escenarios"""
    status, data, err = http_request("GET", "/api/v1/escenarios")
    if err:
        return False, err
    if status != 200:
        return False, f"Esperado 200, recibido {status}"
    if not isinstance(data, list):
        return False, f"Esperada lista, recibido: {type(data).__name__}"
    expected_ids = ["S-001", "S-002"]
    ids = [s.get("id") for s in data if isinstance(s, dict)]
    for eid in expected_ids:
        if eid not in ids:
            return False, f"Escenario inicial {eid} no encontrado. IDs: {ids}"
    return True, f"OK, {len(data)} escenarios encontrados"


def test_p013() -> Tuple[bool, str]:
    """P013: POST /api/v1/escenarios/{sid}/simular -> 200, simulacion ejecutada"""
    if not STATE["escenario_ids"]:
        return False, "No hay escenario creado (depende de P011)"
    sid = STATE["escenario_ids"][0]
    status, data, err = http_request("POST", f"/api/v1/escenarios/{sid}/simular")
    if err:
        return False, err
    if status != 200:
        return False, f"Esperado 200, recibido {status}"
    return True, f"OK, simulacion ejecutada para {sid}"


def test_p014() -> Tuple[bool, str]:
    """P014: GET /api/v1/escenarios/{sid}/resultados -> 200, resultados presentes"""
    if not STATE["escenario_ids"]:
        return False, "No hay escenario creado (depende de P011)"
    sid = STATE["escenario_ids"][0]
    status, data, err = http_request("GET", f"/api/v1/escenarios/{sid}/resultados")
    if err:
        return False, err
    if status != 200:
        return False, f"Esperado 200, recibido {status}"
    if data is None:
        return False, "Respuesta vacia"
    return True, f"OK, resultados obtenidos para {sid}"


def test_p015() -> Tuple[bool, str]:
    """P015: POST /api/v1/hipotesis (body 3) -> 201, tercera hipotesis"""
    body = {
        "texto": "Tercera hipotesis sobre cambio climatico y tecnologia",
        "tags": ["clima", "tecnologia", "sostenibilidad"],
    }
    status, data, err = http_request("POST", "/api/v1/hipotesis", body=body)
    if err:
        return False, err
    if status != 201:
        return False, f"Esperado 201, recibido {status}"
    if data is None or not isinstance(data, dict):
        return False, "Respuesta no es JSON valido"
    hid = data.get("id")
    if not hid:
        return False, f"Campo 'id' ausente: {data}"
    STATE["hipotesis_ids"].append(hid)
    return True, f"OK, tercera hipotesis creada: {hid}"


def test_p016() -> Tuple[bool, str]:
    """P016: POST /api/v1/hipotesis/{id3}/validar -> 200, validada"""
    if len(STATE["hipotesis_ids"]) < 3:
        return False, "No hay hipotesis ID 3 (depende de P015)"
    hid = STATE["hipotesis_ids"][2]
    status, data, err = http_request("POST", f"/api/v1/hipotesis/{hid}/validar")
    if err:
        return False, err
    if status != 200:
        return False, f"Esperado 200, recibido {status}"
    return True, f"OK, hipotesis {hid} validada"


def test_p017() -> Tuple[bool, str]:
    """P017: GET /api/v1/hipotesis/{id3} -> 200, recuperada"""
    if len(STATE["hipotesis_ids"]) < 3:
        return False, "No hay hipotesis ID 3 (depende de P015)"
    hid = STATE["hipotesis_ids"][2]
    status, data, err = http_request("GET", f"/api/v1/hipotesis/{hid}")
    if err:
        return False, err
    if status != 200:
        return False, f"Esperado 200, recibido {status}"
    if data is None or not isinstance(data, dict):
        return False, "Respuesta no es dict valido"
    if data.get("id") != hid:
        return False, f"ID no coincide: esperado {hid}, recibido {data.get('id')}"
    return True, f"OK, hipotesis {hid} recuperada post-validacion"


def test_p018() -> Tuple[bool, str]:
    """P018: POST /api/v1/escenarios (body 2) -> 201, segundo escenario"""
    body = {
        "nombre": "Escenario de prueba automatizado #2 - Recesion",
        "descripcion": "Simulacion de recesion economica moderada",
        "parametros": {"tasa_crecimiento": -0.02, "volatilidad": 0.25, "inflacion": 0.08},
    }
    status, data, err = http_request("POST", "/api/v1/escenarios", body=body)
    if err:
        return False, err
    if status != 201:
        return False, f"Esperado 201, recibido {status}"
    if data is None or not isinstance(data, dict):
        return False, "Respuesta no es JSON valido"
    sid = data.get("id")
    if not sid:
        return False, f"Campo 'id' ausente: {data}"
    STATE["escenario_ids"].append(sid)
    return True, f"OK, segundo escenario creado: {sid}"


def test_p019() -> Tuple[bool, str]:
    """P019: POST /api/v1/escenarios/{sid2}/simular -> 200, simulado"""
    if len(STATE["escenario_ids"]) < 2:
        return False, "No hay escenario ID 2 (depende de P018)"
    sid = STATE["escenario_ids"][1]
    status, data, err = http_request("POST", f"/api/v1/escenarios/{sid}/simular")
    if err:
        return False, err
    if status != 200:
        return False, f"Esperado 200, recibido {status}"
    return True, f"OK, simulacion ejecutada para {sid}"


def test_p020() -> Tuple[bool, str]:
    """P020: GET /api/v1/escenarios/{sid2}/resultados -> 200, resultados"""
    if len(STATE["escenario_ids"]) < 2:
        return False, "No hay escenario ID 2 (depende de P018)"
    sid = STATE["escenario_ids"][1]
    status, data, err = http_request("GET", f"/api/v1/escenarios/{sid}/resultados")
    if err:
        return False, err
    if status != 200:
        return False, f"Esperado 200, recibido {status}"
    if data is None:
        return False, "Respuesta vacia"
    return True, f"OK, resultados obtenidos para segundo escenario {sid}"


def test_p021() -> Tuple[bool, str]:
    """P021: GET /api/v1/diario/actual -> 200, diario con datos"""
    status, data, err = http_request("GET", "/api/v1/diario/actual")
    if err:
        return False, err
    if status != 200:
        return False, f"Esperado 200, recibido {status}"
    if data is None or not isinstance(data, dict):
        return False, "Respuesta no es dict valido"
    if not data:
        return False, "Diario vacio (dict sin campos)"
    return True, f"OK, diario actual recuperado con {len(data)} campos"


def test_p022() -> Tuple[bool, str]:
    """P022: GET /api/v1/diario/historial -> 200, lista de diarios"""
    status, data, err = http_request("GET", "/api/v1/diario/historial")
    if err:
        return False, err
    if status != 200:
        return False, f"Esperado 200, recibido {status}"
    if not isinstance(data, list):
        return False, f"Esperada lista, recibido: {type(data).__name__}"
    if len(data) < 1:
        return False, "Historial de diarios vacio"
    return True, f"OK, historial con {len(data)} diarios"


def test_p023() -> Tuple[bool, str]:
    """P023: GET /api/v1/estadisticas -> 200, estadisticas"""
    status, data, err = http_request("GET", "/api/v1/estadisticas")
    if err:
        return False, err
    if status != 200:
        return False, f"Esperado 200, recibido {status}"
    if data is None or not isinstance(data, dict):
        return False, "Respuesta no es dict valido"
    return True, f"OK, estadisticas obtenidas con {len(data)} campos"


def test_p024() -> Tuple[bool, str]:
    """P024: GET /api/v1/hipotesis?tag=ia -> 200, filtradas por tag"""
    status, data, err = http_request("GET", "/api/v1/hipotesis", params={"tag": "ia"})
    if err:
        return False, err
    if status != 200:
        return False, f"Esperado 200, recibido {status}"
    if not isinstance(data, list):
        return False, f"Esperada lista, recibido: {type(data).__name__}"
    return True, f"OK, {len(data)} hipotesis filtradas por tag 'ia'"


def test_p025() -> Tuple[bool, str]:
    """P025: GET /api/v1/hipotesis?estado=activa -> 200, filtradas por estado"""
    status, data, err = http_request("GET", "/api/v1/hipotesis", params={"estado": "activa"})
    if err:
        return False, err
    if status != 200:
        return False, f"Esperado 200, recibido {status}"
    if not isinstance(data, list):
        return False, f"Esperada lista, recibido: {type(data).__name__}"
    return True, f"OK, {len(data)} hipotesis filtradas por estado 'activa'"


def test_p026() -> Tuple[bool, str]:
    """P026: POST /api/v1/hipotesis/H-999/validar -> 404 (hipotesis no existe)"""
    status, data, err = http_request("POST", "/api/v1/hipotesis/H-999/validar")
    if err:
        return False, err
    if status != 404:
        return False, f"Esperado 404, recibido {status}"
    return True, "OK, 404 para hipotesis inexistente H-999"


def test_p027() -> Tuple[bool, str]:
    """P027: GET /health (repetido) -> 200"""
    status, data, err = http_request("GET", "/health")
    if err:
        return False, err
    if status != 200:
        return False, f"Esperado 200, recibido {status}"
    if data is None or data.get("status") != "healthy":
        return False, f"status != healthy: {data}"
    return True, "OK, health check repetido OK"


def test_p028() -> Tuple[bool, str]:
    """P028: GET /api/v1/hipotesis (conteo final) -> 200, >= 8 hipotesis"""
    status, data, err = http_request("GET", "/api/v1/hipotesis")
    if err:
        return False, err
    if status != 200:
        return False, f"Esperado 200, recibido {status}"
    if not isinstance(data, list):
        return False, f"Esperada lista, recibido: {type(data).__name__}"
    if len(data) < 8:
        return False, f"Esperadas >= 8 hipotesis, recibidas {len(data)}"
    return True, f"OK, {len(data)} hipotesis totales (>= 8)"


def test_p029() -> Tuple[bool, str]:
    """P029: GET /api/v1/hipotesis/{ultima_id} -> 200"""
    if not STATE["hipotesis_ids"]:
        return False, "No hay hipotesis creadas"
    hid = STATE["hipotesis_ids"][-1]
    status, data, err = http_request("GET", f"/api/v1/hipotesis/{hid}")
    if err:
        return False, err
    if status != 200:
        return False, f"Esperado 200, recibido {status}"
    if data is None or not isinstance(data, dict):
        return False, "Respuesta no es dict valido"
    if data.get("id") != hid:
        return False, f"ID no coincide: esperado {hid}, recibido {data.get('id')}"
    return True, f"OK, ultima hipotesis {hid} recuperada"


def test_p030() -> Tuple[bool, str]:
    """P030: GET /api/v1/escenarios (lista final) -> 200, >= 4 escenarios"""
    status, data, err = http_request("GET", "/api/v1/escenarios")
    if err:
        return False, err
    if status != 200:
        return False, f"Esperado 200, recibido {status}"
    if not isinstance(data, list):
        return False, f"Esperada lista, recibido: {type(data).__name__}"
    if len(data) < 4:
        return False, f"Esperados >= 4 escenarios, recibidos {len(data)}"
    return True, f"OK, {len(data)} escenarios totales (>= 4)"


# =============================================================================
# LISTA DE PRUEBAS
# =============================================================================
TESTS = [
    {"name": "P001",  "description": "GET /health -> 200 healthy",                     "fn": test_p001},
    {"name": "P002",  "description": "GET /api/v1/hipotesis -> lista H-001..H-005",    "fn": test_p002},
    {"name": "P003",  "description": "POST /api/v1/hipotesis (body 1) -> 201 con id",   "fn": test_p003},
    {"name": "P004",  "description": "GET /api/v1/hipotesis/{id1} -> 200 coincide",    "fn": test_p004},
    {"name": "P005",  "description": "GET /api/v1/hipotesis -> lista incluye creada",   "fn": test_p005},
    {"name": "P006",  "description": "POST /api/v1/hipotesis (body 2) -> 201 id2",      "fn": test_p006},
    {"name": "P007",  "description": "POST /api/v1/hipotesis/{id1}/validar -> 200",    "fn": test_p007},
    {"name": "P008",  "description": "POST /api/v1/hipotesis/{id2}/validar -> 200",    "fn": test_p008},
    {"name": "P009",  "description": "GET /api/v1/mercados -> 200 lista mercados",      "fn": test_p009},
    {"name": "P010",  "description": "GET /api/v1/mercados/M-001 -> 200",              "fn": test_p010},
    {"name": "P011",  "description": "POST /api/v1/escenarios (body 1) -> 201 con id",  "fn": test_p011},
    {"name": "P012",  "description": "GET /api/v1/escenarios -> lista S-001, S-002",    "fn": test_p012},
    {"name": "P013",  "description": "POST /api/v1/escenarios/{sid1}/simular -> 200",  "fn": test_p013},
    {"name": "P014",  "description": "GET /api/v1/escenarios/{sid1}/resultados -> 200","fn": test_p014},
    {"name": "P015",  "description": "POST /api/v1/hipotesis (body 3) -> 201 id3",      "fn": test_p015},
    {"name": "P016",  "description": "POST /api/v1/hipotesis/{id3}/validar -> 200",    "fn": test_p016},
    {"name": "P017",  "description": "GET /api/v1/hipotesis/{id3} -> 200 recuperada",  "fn": test_p017},
    {"name": "P018",  "description": "POST /api/v1/escenarios (body 2) -> 201 sid2",    "fn": test_p018},
    {"name": "P019",  "description": "POST /api/v1/escenarios/{sid2}/simular -> 200",  "fn": test_p019},
    {"name": "P020",  "description": "GET /api/v1/escenarios/{sid2}/resultados -> 200","fn": test_p020},
    {"name": "P021",  "description": "GET /api/v1/diario/actual -> 200 con datos",     "fn": test_p021},
    {"name": "P022",  "description": "GET /api/v1/diario/historial -> 200 lista",      "fn": test_p022},
    {"name": "P023",  "description": "GET /api/v1/estadisticas -> 200",                "fn": test_p023},
    {"name": "P024",  "description": "GET /hipotesis?tag=ia -> 200 filtradas",         "fn": test_p024},
    {"name": "P025",  "description": "GET /hipotesis?estado=activa -> 200 filtradas",  "fn": test_p025},
    {"name": "P026",  "description": "POST /hipotesis/H-999/validar -> 404",           "fn": test_p026},
    {"name": "P027",  "description": "GET /health (repetido) -> 200",                  "fn": test_p027},
    {"name": "P028",  "description": "GET /hipotesis conteo final -> >= 8",            "fn": test_p028},
    {"name": "P029",  "description": "GET /hipotesis/{ultima_id} -> 200",              "fn": test_p029},
    {"name": "P030",  "description": "GET /escenarios lista final -> >= 4",            "fn": test_p030},
]


# =============================================================================
# EJECUCION DE PRUEBAS
# =============================================================================
def run_test(test: Dict) -> Tuple[bool, str]:
    """Ejecuta una prueba y retorna (ok, detail)."""
    try:
        ok, detail = test["fn"]()
        return ok, detail
    except Exception as e:
        return False, f"EXCEPCION: {type(e).__name__}: {e}"


def main():
    print_banner()
    log(f"\n{Colors.OKBLUE}Servidor: {BASE_URL}{Colors.ENDC}")
    log(f"{Colors.OKBLUE}Timeout:  {TIMEOUT}s{Colors.ENDC}\n")

    # Verificar conectividad basica antes de empezar
    status, _, err = http_request("GET", "/health")
    if err:
        log(f"\n{Colors.FAIL}{Colors.BOLD}ERROR DE CONEXION{Colors.ENDC}")
        log(f"{Colors.FAIL}No se pudo conectar a {BASE_URL}{Colors.ENDC}")
        log(f"{Colors.FAIL}Detalle: {err}{Colors.ENDC}")
        log(f"\n{Colors.WARNING}Asegurate de que el servidor VEO este corriendo.{Colors.ENDC}")
        sys.exit(1)

    results: List[Tuple[str, str, bool, str]] = []
    passed = 0
    failed = 0
    start_time = time.time()

    for i, test in enumerate(TESTS):
        tname = test["name"]
        tdesc = test["description"]

        ok, detail = run_test(test)

        if ok:
            passed += 1
            status_str = f"{Colors.OKGREEN}[PASS]{Colors.ENDC}"
            results.append((tname, tdesc, True, detail))
        else:
            failed += 1
            status_str = f"{Colors.FAIL}[FAIL]{Colors.ENDC}"
            results.append((tname, tdesc, False, detail))

        log(f"{status_str} {tname} {tdesc}")
        if not ok:
            log(f"       {Colors.FAIL}  -> {detail}{Colors.ENDC}")

    elapsed = time.time() - start_time

    # =================================================================
    # INFORME FINAL
    # =================================================================
    sep = "=" * 56
    log(f"\n{Colors.BOLD}{Colors.OKCYAN}{sep}{Colors.ENDC}")
    log(f"{Colors.BOLD}{Colors.OKCYAN}VEO v2.0.4B - BATERIA OFICIAL 30 PRUEBAS{Colors.ENDC}")
    log(f"{Colors.BOLD}{Colors.OKCYAN}{sep}{Colors.ENDC}")

    for tname, tdesc, ok, detail in results:
        if ok:
            log(f"{Colors.OKGREEN}[PASS]{Colors.ENDC} {tname} {tdesc}")
        else:
            log(f"{Colors.FAIL}[FAIL]{Colors.ENDC} {tname} {tdesc}")
            log(f"       {Colors.FAIL}-> {detail}{Colors.ENDC}")

    total = len(TESTS)
    log(f"\n{Colors.BOLD}RESULTADO: {passed}/{total} pruebas pasadas{Colors.ENDC}")
    log(f"{Colors.OKBLUE}Tiempo: {elapsed:.2f}s{Colors.ENDC}")

    if failed > 0:
        log(f"\n{Colors.FAIL}{Colors.BOLD}{passed}/{total} PRUEBAS FALLADAS -> NO EMPAQUETAR{Colors.ENDC}")
        sys.exit(1)
    else:
        log(f"\n{Colors.OKGREEN}{Colors.BOLD}{passed}/{total} PRUEBAS PASADAS -> LISTO PARA EMPAQUETAR{Colors.ENDC}")
        sys.exit(0)


if __name__ == "__main__":
    main()
