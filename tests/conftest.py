# conftest.py - VEO v2 Test Fixtures
"""
Fixtures compartidas para toda la suite de tests de VEO v2.

Todas las fixtures usan base de datos en memoria (:memory:) para
aislamiento y velocidad. Se limpian automaticamente despues de cada test.

Fixtures principales:
- db_temp: Conexion SQLite temporal con tablas inicializadas
- config_test: Configuracion de test con valores controlados
- logger_mock: Logger mock que captura mensajes en memoria
- event_bus_test: Bus de eventos limpio para cada test
- scheduler_test: Planificador con ciclos acelerados para tests
- mock_grafo: Grafo de conocimiento en memoria para tests
- mock_motor_causal: Motor causal con grafo mock
- sample_hipotesis: Hipotesis de ejemplo lista para usar
- sample_escenario: Escenario de ejemplo para simulaciones
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Generator, List, Optional, Tuple
from unittest.mock import MagicMock

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Fixtures de infraestructura
# ---------------------------------------------------------------------------


@pytest.fixture(scope="function")
def db_temp() -> Generator[sqlite3.Connection, None, None]:
    """
    Crea una base de datos SQLite en memoria con el esquema completo de VEO.

    Yields:
        sqlite3.Connection con row_factory=sqlite3.Row, foreign_keys activadas,
        y todas las tablas del sistema ya creadas.

    Cleanup:
        La conexion se cierra automaticamente al finalizar el test.
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    # Crear esquema completo
    conn.executescript(
        """
        -- Tabla: hipotesis
        CREATE TABLE IF NOT EXISTS hipotesis (
            id TEXT PRIMARY KEY,
            texto TEXT NOT NULL,
            confianza REAL NOT NULL DEFAULT 0.0 CHECK (confianza >= 0 AND confianza <= 1),
            evidencias TEXT NOT NULL DEFAULT '[]',
            refutaciones TEXT NOT NULL DEFAULT '[]',
            estado TEXT NOT NULL DEFAULT 'activa' CHECK (estado IN ('activa', 'confirmada', 'refutada', 'caduca')),
            fecha_creacion TEXT NOT NULL,
            fecha_actualizacion TEXT NOT NULL,
            creador TEXT NOT NULL DEFAULT 'sistema',
            tags TEXT NOT NULL DEFAULT '[]',
            peso_nei REAL NOT NULL DEFAULT 0.0
        );

        CREATE INDEX IF NOT EXISTS idx_hipotesis_estado ON hipotesis(estado);
        CREATE INDEX IF NOT EXISTS idx_hipotesis_confianza ON hipotesis(confianza);

        -- Tabla: predicciones
        CREATE TABLE IF NOT EXISTS predicciones (
            id TEXT PRIMARY KEY,
            hipotesis_id TEXT NOT NULL,
            escenario TEXT NOT NULL,
            probabilidad REAL NOT NULL DEFAULT 0.5 CHECK (probabilidad >= 0 AND probabilidad <= 1),
            fecha_prediccion TEXT NOT NULL,
            fecha_resolucion TEXT,
            estado TEXT NOT NULL DEFAULT 'abierta' CHECK (estado IN ('abierta', 'cerrada', 'suspendida')),
            liquidez REAL NOT NULL DEFAULT 1000.0,
            participaciones INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (hipotesis_id) REFERENCES hipotesis(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_predicciones_estado ON predicciones(estado);
        CREATE INDEX IF NOT EXISTS idx_predicciones_hipotesis ON predicciones(hipotesis_id);

        -- Tabla: escenarios
        CREATE TABLE IF NOT EXISTS escenarios (
            id TEXT PRIMARY KEY,
            nombre TEXT NOT NULL,
            descripcion TEXT NOT NULL DEFAULT '',
            variables TEXT NOT NULL DEFAULT '[]',
            resultado_simulado TEXT NOT NULL DEFAULT '{}',
            confianza REAL NOT NULL DEFAULT 0.0 CHECK (confianza >= 0 AND confianza <= 1),
            fecha TEXT NOT NULL
        );

        -- Tabla: descubrimientos_semanales
        CREATE TABLE IF NOT EXISTS descubrimientos_semanales (
            id TEXT PRIMARY KEY,
            semana INTEGER NOT NULL CHECK (semana >= 1 AND semana <= 53),
            fecha_inicio TEXT NOT NULL,
            fecha_fin TEXT NOT NULL,
            hipotesis_nuevas TEXT NOT NULL DEFAULT '[]',
            hipotesis_confirmadas TEXT NOT NULL DEFAULT '[]',
            hipotesis_refutadas TEXT NOT NULL DEFAULT '[]',
            tendencias_detectadas TEXT NOT NULL DEFAULT '[]',
            aprendizajes TEXT NOT NULL DEFAULT '[]',
            confianza_promedio REAL NOT NULL DEFAULT 0.0 CHECK (confianza_promedio >= 0 AND confianza_promedio <= 1),
            nivel_actividad REAL NOT NULL DEFAULT 0.0 CHECK (nivel_actividad >= 0 AND nivel_actividad <= 1)
        );

        CREATE INDEX IF NOT EXISTS idx_descubrimientos_semana ON descubrimientos_semanales(semana);

        -- Tabla: cambios_narrativa
        CREATE TABLE IF NOT EXISTS cambios_narrativa (
            id TEXT PRIMARY KEY,
            tema TEXT NOT NULL,
            direccion_anterior TEXT NOT NULL DEFAULT '',
            direccion_actual TEXT NOT NULL DEFAULT '',
            magnitud_cambio REAL NOT NULL DEFAULT 0.0 CHECK (magnitud_cambio >= 0 AND magnitud_cambio <= 1),
            fecha_detectado TEXT NOT NULL,
            fuentes TEXT NOT NULL DEFAULT '[]',
            confianza REAL NOT NULL DEFAULT 0.0 CHECK (confianza >= 0 AND confianza <= 1)
        );

        CREATE INDEX IF NOT EXISTS idx_cambios_tema ON cambios_narrativa(tema);
        CREATE INDEX IF NOT EXISTS idx_cambios_fecha ON cambios_narrativa(fecha_detectado);

        -- Tabla: grafo_nodos
        CREATE TABLE IF NOT EXISTS grafo_nodos (
            id TEXT PRIMARY KEY,
            tipo TEXT NOT NULL CHECK (tipo IN ('entidad', 'concepto', 'evento')),
            nombre TEXT NOT NULL,
            propiedades TEXT NOT NULL DEFAULT '{}',
            embedding TEXT NOT NULL DEFAULT '[]',
            peso REAL NOT NULL DEFAULT 1.0 CHECK (peso >= 0 AND peso <= 1)
        );

        CREATE INDEX IF NOT EXISTS idx_nodos_tipo ON grafo_nodos(tipo);
        CREATE INDEX IF NOT EXISTS idx_nodos_nombre ON grafo_nodos(nombre);

        -- Tabla: grafo_relaciones
        CREATE TABLE IF NOT EXISTS grafo_relaciones (
            origen_id TEXT NOT NULL,
            destino_id TEXT NOT NULL,
            tipo TEXT NOT NULL DEFAULT 'relacion',
            peso REAL NOT NULL DEFAULT 0.5 CHECK (peso >= 0 AND peso <= 1),
            evidencias TEXT NOT NULL DEFAULT '[]',
            confianza REAL NOT NULL DEFAULT 0.0 CHECK (confianza >= 0 AND confianza <= 1),
            PRIMARY KEY (origen_id, destino_id, tipo),
            FOREIGN KEY (origen_id) REFERENCES grafo_nodos(id) ON DELETE CASCADE,
            FOREIGN KEY (destino_id) REFERENCES grafo_nodos(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_relaciones_origen ON grafo_relaciones(origen_id);
        CREATE INDEX IF NOT EXISTS idx_relaciones_destino ON grafo_relaciones(destino_id);

        -- Tabla: validaciones
        CREATE TABLE IF NOT EXISTS validaciones (
            hipotesis_id TEXT PRIMARY KEY,
            veredicto TEXT NOT NULL CHECK (veredicto IN ('confirmada', 'refutada', 'inconclusa')),
            razonamiento TEXT NOT NULL DEFAULT '',
            nivel_confianza REAL NOT NULL DEFAULT 0.0 CHECK (nivel_confianza >= 0 AND nivel_confianza <= 1),
            sesgos_detectados TEXT NOT NULL DEFAULT '[]',
            test_realizados TEXT NOT NULL DEFAULT '[]',
            fecha_validacion TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_validaciones_veredicto ON validaciones(veredicto);

        -- Tabla: historial_nei
        CREATE TABLE IF NOT EXISTS historial_nei (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            semana INTEGER NOT NULL,
            peso_fr REAL NOT NULL,
            peso_gr REAL NOT NULL,
            peso_dv REAL NOT NULL,
            peso_nv REAL NOT NULL,
            peso_em REAL NOT NULL,
            peso_st REAL NOT NULL,
            precision_sistema REAL NOT NULL DEFAULT 0.0,
            fecha_registro TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_historial_semana ON historial_nei(semana);

        -- Tabla: logs_operacion
        CREATE TABLE IF NOT EXISTS logs_operacion (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            nivel TEXT NOT NULL,
            modulo TEXT NOT NULL DEFAULT '',
            mensaje TEXT NOT NULL,
            metadata TEXT NOT NULL DEFAULT '{}'
        );

        -- Tabla: metricas
        CREATE TABLE IF NOT EXISTS metricas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            valor REAL NOT NULL,
            timestamp TEXT NOT NULL,
            tags TEXT NOT NULL DEFAULT '{}'
        );

        CREATE INDEX IF NOT EXISTS idx_metricas_nombre ON metricas(nombre);
        CREATE INDEX IF NOT EXISTS idx_metricas_timestamp ON metricas(timestamp);

        -- Tabla: auditoria
        CREATE TABLE IF NOT EXISTS auditoria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            actor TEXT NOT NULL DEFAULT 'sistema',
            accion TEXT NOT NULL,
            recurso TEXT NOT NULL DEFAULT '',
            detalle TEXT NOT NULL DEFAULT '{}',
            hash_previo TEXT NOT NULL DEFAULT ''
        );

        -- Tabla: trust_scores
        CREATE TABLE IF NOT EXISTS trust_scores (
            componente TEXT PRIMARY KEY,
            score REAL NOT NULL DEFAULT 0.5 CHECK (score >= 0 AND score <= 1),
            penalizaciones INTEGER NOT NULL DEFAULT 0,
            recompensas INTEGER NOT NULL DEFAULT 0,
            ultimo_update TEXT NOT NULL
        );

        -- Tabla: backups
        CREATE TABLE IF NOT EXISTS backups (
            id TEXT PRIMARY KEY,
            ruta TEXT NOT NULL,
            tamano_bytes INTEGER NOT NULL DEFAULT 0,
            timestamp TEXT NOT NULL,
            checksum TEXT NOT NULL DEFAULT '',
            estado TEXT NOT NULL DEFAULT 'ok' CHECK (estado IN ('ok', 'corrupto', 'incompleto'))
        );

        -- Tabla: eventos_sistema
        CREATE TABLE IF NOT EXISTS eventos_sistema (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            tipo TEXT NOT NULL,
            origen TEXT NOT NULL DEFAULT '',
            payload TEXT NOT NULL DEFAULT '{}',
            procesado INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_eventos_tipo ON eventos_sistema(tipo);
        CREATE INDEX IF NOT EXISTS idx_eventos_procesado ON eventos_sistema(procesado);

        -- Tabla: health_status
        CREATE TABLE IF NOT EXISTS health_status (
            componente TEXT PRIMARY KEY,
            estado TEXT NOT NULL DEFAULT 'ok' CHECK (estado IN ('ok', 'warning', 'critical', 'unknown')),
            score REAL NOT NULL DEFAULT 1.0,
            ultimo_check TEXT NOT NULL,
            mensaje TEXT NOT NULL DEFAULT ''
        );
        """
    )
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture(scope="function")
def config_test() -> Dict[str, Any]:
    """
    Configuracion de test con valores controlados y seguros.

    Returns:
        Diccionario con configuracion minima para ejecutar todos los
        componentes de VEO sin dependencias externas.
    """
    return {
        # NEI
        "pesos_nei": [0.20, 0.25, 0.20, 0.20, 0.10, 0.05],
        "tasa_aprendizaje": 0.01,
        "umbral_cascada": 0.7,
        "min_confidence": 0.6,
        "min_evidence": 3,
        # LLM (deshabilitado para tests)
        "llm_api_url": "",
        "llm_api_key": "",
        "llm_model": "test-model",
        # Embeddings
        "embedding_model": "all-MiniLM-L6-v2",
        "embedding_dimension": 384,
        # Directorios (temporales)
        "dir_base": "/tmp/veo_test",
        "dir_datos": "/tmp/veo_test/data",
        "dir_logs": "/tmp/veo_test/logs",
        # Intervalos de ciclos (acelerados para tests)
        "ciclo_monitoreo_seg": 1,
        "ciclo_analisis_seg": 2,
        "ciclo_prediccion_seg": 5,
        "ciclo_ejecutivo_seg": 10,
        # Umbrales
        "umbral_alerta": 0.75,
        "umbral_warning": 0.50,
        # Entorno
        "ambiente": "test",
        "debug": True,
    }


@pytest.fixture(scope="function")
def logger_mock() -> MagicMock:
    """
    Logger mock que captura todos los mensajes en memoria.

    Returns:
        MagicMock con metodos debug, info, warning, error, critical
        que almacenan los mensajes en listas internas.
    """
    mock = MagicMock()
    mock._logs: Dict[str, List[str]] = {
        "debug": [],
        "info": [],
        "warning": [],
        "error": [],
        "critical": [],
    }

    def _log(level: str, msg: str, *args, **kwargs) -> None:
        formatted = msg % args if args else msg
        mock._logs[level].append(formatted)

    mock.debug.side_effect = lambda msg, *a, **k: _log("debug", msg, *a, **k)
    mock.info.side_effect = lambda msg, *a, **k: _log("info", msg, *a, **k)
    mock.warning.side_effect = lambda msg, *a, **k: _log("warning", msg, *a, **k)
    mock.error.side_effect = lambda msg, *a, **k: _log("error", msg, *a, **k)
    mock.critical.side_effect = lambda msg, *a, **k: _log("critical", msg, *a, **k)

    return mock


@pytest.fixture(scope="function")
def event_bus_test() -> "EventBusTest":
    """
    Bus de eventos en memoria para tests.

    Returns:
        Instancia limpia de EventBusTest con soporte para
        publish, subscribe y unsubscribe.
    """
    return EventBusTest()


@pytest.fixture(scope="function")
def scheduler_test(config_test: Dict[str, Any]) -> "SchedulerTest":
    """
    Planificador con ciclos acelerados para tests.

    Args:
        config_test: Fixture de configuracion de test.

    Returns:
        SchedulerTest con intervalos reducidos.
    """
    return SchedulerTest(config_test)


@pytest.fixture(scope="function")
def mock_grafo() -> MagicMock:
    """
    Grafo de conocimiento mock con nodos y relaciones predefinidos.

    Returns:
        MagicMock que simula un GrafoConocimiento completo.
    """
    grafo = MagicMock()
    grafo.todos_los_nodos.return_value = ["nodo_a", "nodo_b", "nodo_c", "nodo_d"]
    grafo.obtener_nodo.return_value = {"id": "nodo_a", "nombre": "Test Node", "tipo": "concepto"}
    grafo.obtener_relaciones.return_value = []
    grafo.buscar_camino.return_value = [["nodo_a", "nodo_b", "nodo_c"]]
    grafo.nodos.return_value = ["nodo_a", "nodo_b", "nodo_c", "nodo_d"]
    return grafo


@pytest.fixture(scope="function")
def mock_motor_causal(mock_grafo: MagicMock, db_temp: sqlite3.Connection, logger_mock: MagicMock) -> MagicMock:
    """
    Motor causal mock con grafo y DB preconfigurados.

    Args:
        mock_grafo: Fixture del grafo mock.
        db_temp: Fixture de DB temporal.
        logger_mock: Fixture de logger mock.

    Returns:
        MagicMock que simula un MotorCausal.
    """
    motor = MagicMock()
    motor.grafo = mock_grafo
    motor.db = db_temp
    motor.logger = logger_mock
    motor.calcular_efecto.return_value = 0.5
    motor.evaluar_consistencia.return_value = 0.8
    return motor


@pytest.fixture(scope="function")
def sample_hipotesis() -> Dict[str, Any]:
    """
    Hipotesis de ejemplo lista para usar en tests.

    Returns:
        Diccionario con una hipotesis completa y valida.
    """
    return {
        "id": f"hip_test_{uuid.uuid4().hex[:8]}",
        "texto": "La narrativa sobre inteligencia artificial esta cambiando hacia un enfoque mas regulador",
        "confianza": 0.75,
        "evidencias": ["ev_001", "ev_002", "ev_003"],
        "refutaciones": ["ref_001"],
        "estado": "activa",
        "creador": "test_agent",
        "tags": ["ia", "regulacion", "narrativa"],
        "peso_nei": 0.65,
    }


@pytest.fixture(scope="function")
def sample_escenario() -> Dict[str, Any]:
    """
    Escenario de ejemplo para simulaciones.

    Returns:
        Diccionario con un escenario completo con variables configurables.
    """
    return {
        "id": f"esc_test_{uuid.uuid4().hex[:8]}",
        "nombre": "Escenario de Prueba: Regulacion IA",
        "descripcion": "Simulacion del impacto de nuevas regulaciones sobre IA",
        "variables": [
            {"nombre": "inversion_ia", "valor_base": 100.0, "rango_min": 50.0, "rango_max": 200.0, "distribucion": "normal", "std_dev": 25.0},
            {"nombre": "adopcion_publica", "valor_base": 0.6, "rango_min": 0.1, "rango_max": 0.95, "distribucion": "uniforme"},
            {"nombre": "presion_regulatoria", "valor_base": 0.4, "rango_min": 0.0, "rango_max": 1.0, "distribucion": "triangular"},
        ],
        "tipo": "base",
        "hipotesis_relacionada": None,
    }


@pytest.fixture(scope="function")
def sample_series_temporales() -> Dict[str, List[float]]:
    """
    Series temporales de ejemplo para tests de causalidad.

    Returns:
        Diccionario con series X e Y donde X causa Y con cierto retardo.
    """
    np.random.seed(42)
    n = 100
    # X: serie autoregresiva
    x = np.zeros(n)
    x[0] = np.random.randn()
    for t in range(1, n):
        x[t] = 0.7 * x[t - 1] + np.random.randn()

    # Y: causada por X con lag 2
    y = np.zeros(n)
    y[0] = np.random.randn()
    y[1] = 0.5 * y[0] + np.random.randn()
    for t in range(2, n):
        y[t] = 0.5 * y[t - 1] + 0.3 * x[t - 2] + np.random.randn()

    return {
        "x": x.tolist(),
        "y": y.tolist(),
    }


# ---------------------------------------------------------------------------
# Clases auxiliares para fixtures
# ---------------------------------------------------------------------------


class EventBusTest:
    """Implementacion en memoria del bus de eventos para tests."""

    def __init__(self) -> None:
        self._subscribers: Dict[str, List[Callable]] = {}
        self._history: List[Dict[str, Any]] = []
        self._running = False

    def subscribe(self, event_type: str, callback: Callable) -> None:
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: str, callback: Callable) -> bool:
        if event_type in self._subscribers and callback in self._subscribers[event_type]:
            self._subscribers[event_type].remove(callback)
            return True
        return False

    def publish(self, event_type: str, payload: Dict[str, Any]) -> None:
        event = {
            "type": event_type,
            "payload": payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._history.append(event)
        for cb in self._subscribers.get(event_type, []):
            cb(event)

    def get_history(self, event_type: str | None = None) -> List[Dict[str, Any]]:
        if event_type is None:
            return list(self._history)
        return [e for e in self._history if e["type"] == event_type]

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running


class SchedulerTest:
    """Planificador con intervalos acelerados para tests."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        self._tasks: List[Dict[str, Any]] = []
        self._running = False
        self._executed: List[str] = []

    def schedule(self, name: str, interval: int, callback: Callable, priority: int = 5) -> None:
        self._tasks.append({
            "name": name,
            "interval": interval,
            "callback": callback,
            "priority": priority,
            "last_run": None,
        })

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False

    def tick(self) -> None:
        """Ejecuta manualmente un ciclo del scheduler (para tests)."""
        for task in sorted(self._tasks, key=lambda t: t["priority"]):
            task["callback"]()
            task["last_run"] = datetime.now(timezone.utc).isoformat()
            self._executed.append(task["name"])

    def get_executed(self) -> List[str]:
        return list(self._executed)

    @property
    def is_running(self) -> bool:
        return self._running

    def task_count(self) -> int:
        return len(self._tasks)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Proporciona un event loop para tests async."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


def assert_json_serializable(obj: Any) -> None:
    """Helper: verifica que un objeto sea JSON-serializable."""
    import json
    try:
        json.dumps(obj, default=str)
    except (TypeError, ValueError) as exc:
        pytest.fail(f"Objeto no es JSON-serializable: {exc}")


@pytest.fixture(scope="function")
def hid_creada():
    """Crea una hipótesis de prueba y devuelve su ID.

    Este fixture resuelve la dependencia de test_listar_hipotesis
    y test_get_hipotesis en test_deploy.py.
    """
    from api.api_server import MockDatabase
    db = MockDatabase()
    resultado = asyncio.run(db.crear_hipotesis({
        "texto": "Tension en estrecho critico afectara comercio global",
        "tags": ["geopolitica"],
    }))
    hid = resultado.get("id", "") if isinstance(resultado, dict) else ""
    return hid
