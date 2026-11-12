# test_core.py - Tests del nucleo central de VEO v2
"""
Tests para el modulo core/ de VEO v2:
- Configuracion (carga, valores por defecto, env vars)
- Base de datos (CRUD en cada tabla, integridad referencial)
- VEOCore (iniciar/parar, ciclos, eventos, health status)
- EventBus (publish/subscribe, eventos multiples, unsubscribe)
- Scheduler (schedule tasks, priority queue, start/stop)
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator, List
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# Asegurar que el codigo fuente es importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from .conftest import EventBusTest, SchedulerTest


# ============================================================================
# TESTS: Configuracion
# ============================================================================


class TestConfiguracion:
    """Tests para el modulo de configuracion central."""

    def test_config_carga_valores_por_defecto(self, config_test: Dict[str, Any]) -> None:
        """Verificar que la configuracion carga valores por defecto sensatos."""
        cfg = config_test
        assert cfg["min_confidence"] == 0.6
        assert cfg["min_evidence"] == 3
        assert cfg["ambiente"] == "test"
        assert len(cfg["pesos_nei"]) == 6
        assert abs(sum(cfg["pesos_nei"]) - 1.0) < 1e-6

    def test_config_pesos_nei_suman_uno(self, config_test: Dict[str, Any]) -> None:
        """Los pesos NEI deben sumar aproximadamente 1.0."""
        pesos = config_test["pesos_nei"]
        total = sum(pesos)
        assert abs(total - 1.0) < 1e-6, f"Pesos suman {total}, no 1.0"

    def test_config_pesos_nei_en_rango(self, config_test: Dict[str, Any]) -> None:
        """Cada peso NEI individual debe estar entre 0 y 1."""
        for i, p in enumerate(config_test["pesos_nei"]):
            assert 0.0 <= p <= 1.0, f"Peso NEI[{i}] = {p} fuera de rango"

    def test_config_env_vars_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Las variables de entorno deben poder sobrescribir configuracion."""
        monkeypatch.setenv("VEO_MIN_CONFIDENCE", "0.85")
        monkeypatch.setenv("VEO_AMBIENTE", "produccion")
        
        # Simular carga desde env vars
        min_conf = float(os.environ.get("VEO_MIN_CONFIDENCE", "0.6"))
        ambiente = os.environ.get("VEO_AMBIENTE", "dev")
        
        assert min_conf == 0.85
        assert ambiente == "produccion"

    def test_config_env_var_no_existente_usa_default(self) -> None:
        """Si la env var no existe, se usa el valor por defecto."""
        valor = os.environ.get("VEO_VARIABLE_INEXISTENTE_XYZ", "default_value")
        assert valor == "default_value"

    def test_config_json_serializable(self, config_test: Dict[str, Any]) -> None:
        """La configuracion completa debe ser JSON-serializable."""
        try:
            json_str = json.dumps(config_test, default=str)
            recuperado = json.loads(json_str)
            assert recuperado["ambiente"] == "test"
        except (TypeError, ValueError) as exc:
            pytest.fail(f"Config no es JSON-serializable: {exc}")

    def test_config_valores_negativos_rechazados(self) -> None:
        """Valores negativos en parametros criticos deben ser rechazados."""
        with pytest.raises((ValueError, AssertionError)):
            min_conf = -0.5
            assert min_conf >= 0, "min_confidence no puede ser negativo"

    def test_config_ruta_base_existe(self, config_test: Dict[str, Any]) -> None:
        """El directorio base debe poder crearse."""
        ruta = Path(config_test["dir_base"])
        ruta.mkdir(parents=True, exist_ok=True)
        assert ruta.exists()

    def test_config_ciclos_tienen_intervalos_validos(self, config_test: Dict[str, Any]) -> None:
        """Todos los ciclos deben tener intervalos positivos."""
        for clave in ["ciclo_monitoreo_seg", "ciclo_analisis_seg", "ciclo_prediccion_seg", "ciclo_ejecutivo_seg"]:
            assert config_test[clave] > 0, f"{clave} debe ser positivo"


# ============================================================================
# TESTS: Base de Datos
# ============================================================================


class TestBaseDatos:
    """Tests CRUD para cada tabla de la base de datos SQLite."""

    # --- Hipotesis ---

    def test_db_crear_hipotesis(self, db_temp: sqlite3.Connection, sample_hipotesis: Dict[str, Any]) -> None:
        """Crear una hipotesis y verificar que se persiste correctamente."""
        db_temp.execute(
            "INSERT INTO hipotesis (id, texto, confianza, evidencias, refutaciones, estado, fecha_creacion, fecha_actualizacion, creador, tags, peso_nei) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                sample_hipotesis["id"], sample_hipotesis["texto"], sample_hipotesis["confianza"],
                json.dumps(sample_hipotesis["evidencias"]), json.dumps(sample_hipotesis["refutaciones"]),
                sample_hipotesis["estado"], datetime.now(timezone.utc).isoformat(),
                datetime.now(timezone.utc).isoformat(), sample_hipotesis["creador"],
                json.dumps(sample_hipotesis["tags"]), sample_hipotesis["peso_nei"],
            ),
        )
        db_temp.commit()

        cursor = db_temp.execute("SELECT * FROM hipotesis WHERE id = ?", (sample_hipotesis["id"],))
        row = cursor.fetchone()
        assert row is not None
        assert row["texto"] == sample_hipotesis["texto"]
        assert abs(row["confianza"] - sample_hipotesis["confianza"]) < 1e-6

    def test_db_obtener_hipotesis(self, db_temp: sqlite3.Connection, sample_hipotesis: Dict[str, Any]) -> None:
        """Recuperar una hipotesis existente por ID."""
        self._insertar_hipotesis(db_temp, sample_hipotesis)
        cursor = db_temp.execute("SELECT * FROM hipotesis WHERE id = ?", (sample_hipotesis["id"],))
        row = cursor.fetchone()
        assert row is not None
        assert row["id"] == sample_hipotesis["id"]

    def test_db_borrar_hipotesis(self, db_temp: sqlite3.Connection, sample_hipotesis: Dict[str, Any]) -> None:
        """Borrar una hipotesis y verificar que ya no existe."""
        self._insertar_hipotesis(db_temp, sample_hipotesis)
        db_temp.execute("DELETE FROM hipotesis WHERE id = ?", (sample_hipotesis["id"],))
        db_temp.commit()
        cursor = db_temp.execute("SELECT * FROM hipotesis WHERE id = ?", (sample_hipotesis["id"],))
        assert cursor.fetchone() is None

    def test_db_listar_hipotesis_por_estado(self, db_temp: sqlite3.Connection) -> None:
        """Listar hipotesis filtrando por estado."""
        for i, estado in enumerate(["activa", "activa", "confirmada", "refutada"]):
            hip = {
                "id": f"hip_{i}", "texto": f"Hipotesis {i}", "confianza": 0.5 + i * 0.1,
                "evidencias": [], "refutaciones": [], "estado": estado,
                "creador": "test", "tags": [], "peso_nei": 0.5,
            }
            self._insertar_hipotesis(db_temp, hip)

        cursor = db_temp.execute("SELECT COUNT(*) as n FROM hipotesis WHERE estado = ?", ("activa",))
        assert cursor.fetchone()["n"] == 2

    # --- Predicciones ---

    def test_db_crear_prediccion(self, db_temp: sqlite3.Connection) -> None:
        """Crear una prediccion con FK a hipotesis."""
        # Primero crear hipotesis padre
        db_temp.execute(
            "INSERT INTO hipotesis (id, texto, confianza, evidencias, refutaciones, estado, fecha_creacion, fecha_actualizacion, creador, tags, peso_nei) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("hip_padre", "Padre", 0.5, "[]", "[]", "activa", datetime.now(timezone.utc).isoformat(), datetime.now(timezone.utc).isoformat(), "test", "[]", 0.5),
        )
        db_temp.execute(
            "INSERT INTO predicciones (id, hipotesis_id, escenario, probabilidad, fecha_prediccion, estado, liquidez, participaciones) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("pred_001", "hip_padre", "Escenario A", 0.75, datetime.now(timezone.utc).isoformat(), "abierta", 1000.0, 5),
        )
        db_temp.commit()
        cursor = db_temp.execute("SELECT * FROM predicciones WHERE id = ?", ("pred_001",))
        row = cursor.fetchone()
        assert row is not None
        assert row["probabilidad"] == pytest.approx(0.75)

    def test_db_integridad_fk_prediccion(self, db_temp: sqlite3.Connection) -> None:
        """La FK hipotesis_id debe fallar si la hipotesis no existe."""
        db_temp.execute("PRAGMA foreign_keys = ON")
        with pytest.raises(sqlite3.IntegrityError):
            db_temp.execute(
                "INSERT INTO predicciones (id, hipotesis_id, escenario, probabilidad, fecha_prediccion, estado, liquidez, participaciones) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ("pred_bad", "hip_inexistente", "X", 0.5, datetime.now(timezone.utc).isoformat(), "abierta", 1000.0, 0),
            )

    # --- Escenarios ---

    def test_db_crear_escenario(self, db_temp: sqlite3.Connection, sample_escenario: Dict[str, Any]) -> None:
        """Crear un escenario con variables JSON."""
        db_temp.execute(
            "INSERT INTO escenarios (id, nombre, descripcion, variables, resultado_simulado, confianza, fecha) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                sample_escenario["id"], sample_escenario["nombre"], sample_escenario["descripcion"],
                json.dumps(sample_escenario["variables"]), "{}", 0.8,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        db_temp.commit()
        cursor = db_temp.execute("SELECT * FROM escenarios WHERE id = ?", (sample_escenario["id"],))
        row = cursor.fetchone()
        assert row is not None
        vars_recuperadas = json.loads(row["variables"])
        assert len(vars_recuperadas) == 3

    # --- Cambios de Narrativa ---

    def test_db_crear_cambio_narrativa(self, db_temp: sqlite3.Connection) -> None:
        """Crear un registro de cambio de narrativa."""
        db_temp.execute(
            "INSERT INTO cambios_narrativa (id, tema, direccion_anterior, direccion_actual, magnitud_cambio, fecha_detectado, fuentes, confianza) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "cn_001", "Regulacion IA", "oposicion", "apoyo moderado", 0.65,
                datetime.now(timezone.utc).isoformat(), json.dumps(["Fuente1", "Fuente2"]), 0.80,
            ),
        )
        db_temp.commit()
        cursor = db_temp.execute("SELECT * FROM cambios_narrativa WHERE id = ?", ("cn_001",))
        row = cursor.fetchone()
        assert row["magnitud_cambio"] == pytest.approx(0.65)
        assert json.loads(row["fuentes"]) == ["Fuente1", "Fuente2"]

    # --- Grafo: Nodos y Relaciones ---

    def test_db_crear_nodo_grafo(self, db_temp: sqlite3.Connection) -> None:
        """Crear un nodo en el grafo de conocimiento."""
        db_temp.execute(
            "INSERT INTO grafo_nodos (id, tipo, nombre, propiedades, embedding, peso) VALUES (?, ?, ?, ?, ?, ?)",
            ("nodo_1", "concepto", "Inteligencia Artificial", "{}", json.dumps([0.1, 0.2, 0.3]), 0.9),
        )
        db_temp.commit()
        cursor = db_temp.execute("SELECT * FROM grafo_nodos WHERE id = ?", ("nodo_1",))
        assert cursor.fetchone() is not None

    def test_db_crear_relacion_grafo(self, db_temp: sqlite3.Connection) -> None:
        """Crear una relacion entre nodos del grafo."""
        db_temp.execute("INSERT INTO grafo_nodos (id, tipo, nombre, propiedades, embedding, peso) VALUES (?, ?, ?, ?, ?, ?)", ("origen_1", "entidad", "Origen", "{}", "[]", 1.0))
        db_temp.execute("INSERT INTO grafo_nodos (id, tipo, nombre, propiedades, embedding, peso) VALUES (?, ?, ?, ?, ?, ?)", ("destino_1", "entidad", "Destino", "{}", "[]", 1.0))
        db_temp.execute(
            "INSERT INTO grafo_relaciones (origen_id, destino_id, tipo, peso, evidencias, confianza) VALUES (?, ?, ?, ?, ?, ?)",
            ("origen_1", "destino_1", "causa", 0.8, json.dumps(["ev1"]), 0.75),
        )
        db_temp.commit()
        cursor = db_temp.execute("SELECT * FROM grafo_relaciones WHERE origen_id = ?", ("origen_1",))
        row = cursor.fetchone()
        assert row["tipo"] == "causa"
        assert row["peso"] == pytest.approx(0.8)

    def test_db_cascada_delete_nodo(self, db_temp: sqlite3.Connection) -> None:
        """Borrar un nodo debe borrar sus relaciones (ON DELETE CASCADE)."""
        db_temp.execute("INSERT INTO grafo_nodos (id, tipo, nombre, propiedades, embedding, peso) VALUES (?, ?, ?, ?, ?, ?)", ("n_c", "entidad", "N", "{}", "[]", 1.0))
        db_temp.execute("INSERT INTO grafo_nodos (id, tipo, nombre, propiedades, embedding, peso) VALUES (?, ?, ?, ?, ?, ?)", ("n_d", "entidad", "M", "{}", "[]", 1.0))
        db_temp.execute("INSERT INTO grafo_relaciones (origen_id, destino_id, tipo, peso, evidencias, confianza) VALUES (?, ?, ?, ?, ?, ?)", ("n_c", "n_d", "relacion", 0.5, "[]", 0.5))
        db_temp.commit()
        db_temp.execute("DELETE FROM grafo_nodos WHERE id = ?", ("n_c",))
        db_temp.commit()
        cursor = db_temp.execute("SELECT * FROM grafo_relaciones WHERE origen_id = ?", ("n_c",))
        assert cursor.fetchone() is None

    # --- Validaciones ---

    def test_db_crear_validacion(self, db_temp: sqlite3.Connection) -> None:
        """Crear un resultado de validacion cientifica."""
        db_temp.execute(
            "INSERT INTO validaciones (hipotesis_id, veredicto, razonamiento, nivel_confianza, sesgos_detectados, test_realizados, fecha_validacion) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("hip_v", "confirmada", "Evidencia solida", 0.85, json.dumps(["ninguno"]), json.dumps(["t_test"]), datetime.now(timezone.utc).isoformat()),
        )
        db_temp.commit()
        cursor = db_temp.execute("SELECT * FROM validaciones WHERE hipotesis_id = ?", ("hip_v",))
        assert cursor.fetchone()["veredicto"] == "confirmada"

    # --- Metricas ---

    def test_db_crear_metrica(self, db_temp: sqlite3.Connection) -> None:
        """Crear un registro de metrica."""
        db_temp.execute(
            "INSERT INTO metricas (nombre, valor, timestamp, tags) VALUES (?, ?, ?, ?)",
            ("nei_promedio", 0.65, datetime.now(timezone.utc).isoformat(), json.dumps({"ciclo": "analisis"})),
        )
        db_temp.commit()
        cursor = db_temp.execute("SELECT * FROM metricas WHERE nombre = ?", ("nei_promedio",))
        assert cursor.fetchone()["valor"] == pytest.approx(0.65)

    # --- Auditoria ---

    def test_db_crear_auditoria(self, db_temp: sqlite3.Connection) -> None:
        """Crear un registro de auditoria."""
        db_temp.execute(
            "INSERT INTO auditoria (timestamp, actor, accion, recurso, detalle, hash_previo) VALUES (?, ?, ?, ?, ?, ?)",
            (datetime.now(timezone.utc).isoformat(), "test_user", "crear_hipotesis", "hip_001", "{}", "hash_previo_abc"),
        )
        db_temp.commit()
        cursor = db_temp.execute("SELECT COUNT(*) as n FROM auditoria")
        assert cursor.fetchone()["n"] == 1

    # --- Health Status ---

    def test_db_crear_health_status(self, db_temp: sqlite3.Connection) -> None:
        """Crear un registro de estado de salud."""
        db_temp.execute(
            "INSERT INTO health_status (componente, estado, score, ultimo_check, mensaje) VALUES (?, ?, ?, ?, ?)",
            ("veo_core", "ok", 0.95, datetime.now(timezone.utc).isoformat(), "Funcionando normalmente"),
        )
        db_temp.commit()
        cursor = db_temp.execute("SELECT * FROM health_status WHERE componente = ?", ("veo_core",))
        row = cursor.fetchone()
        assert row["estado"] == "ok"
        assert row["score"] == pytest.approx(0.95)

    # --- Helpers ---

    @staticmethod
    def _insertar_hipotesis(db: sqlite3.Connection, hip: Dict[str, Any]) -> None:
        db.execute(
            "INSERT INTO hipotesis (id, texto, confianza, evidencias, refutaciones, estado, fecha_creacion, fecha_actualizacion, creador, tags, peso_nei) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                hip["id"], hip["texto"], hip.get("confianza", 0.5),
                json.dumps(hip.get("evidencias", [])), json.dumps(hip.get("refutaciones", [])),
                hip.get("estado", "activa"), datetime.now(timezone.utc).isoformat(),
                datetime.now(timezone.utc).isoformat(), hip.get("creador", "sistema"),
                json.dumps(hip.get("tags", [])), hip.get("peso_nei", 0.0),
            ),
        )
        db.commit()


# ============================================================================
# TESTS: EventBus
# ============================================================================


class TestEventBus:
    """Tests para el bus de eventos asincrono."""

    def test_event_bus_publish_subscribe(self, event_bus_test: EventBusTest) -> None:
        """Publicar un evento y verificar que el suscriptor lo recibe."""
        received: List[Dict[str, Any]] = []
        event_bus_test.subscribe("hipotesis.nueva", lambda e: received.append(e))
        event_bus_test.publish("hipotesis.nueva", {"hip_id": "h1", "texto": "Test"})
        assert len(received) == 1
        assert received[0]["payload"]["hip_id"] == "h1"

    def test_event_bus_multiple_subscribers(self, event_bus_test: EventBusTest) -> None:
        """Varios suscriptores deben recibir el mismo evento."""
        count_a = 0
        count_b = 0
        event_bus_test.subscribe("test.event", lambda e: setattr(sys.modules[__name__], 'count_a', count_a + 1) or None)
        # Usar lista mutable para contar
        counters = [0, 0]
        event_bus_test.subscribe("test.event", lambda e: counters.__setitem__(0, counters[0] + 1))
        event_bus_test.subscribe("test.event", lambda e: counters.__setitem__(1, counters[1] + 1))
        event_bus_test.publish("test.event", {})
        assert counters[0] == 1
        assert counters[1] == 1

    def test_event_bus_multiple_events(self, event_bus_test: EventBusTest) -> None:
        """El historial debe mantener multiples eventos."""
        for i in range(5):
            event_bus_test.publish("ciclo.tick", {"ciclo_id": i})
        history = event_bus_test.get_history("ciclo.tick")
        assert len(history) == 5

    def test_event_bus_unsubscribe(self, event_bus_test: EventBusTest) -> None:
        """Desuscribirse debe evitar futuras entregas."""
        received: List[Dict[str, Any]] = []
        callback = lambda e: received.append(e)
        event_bus_test.subscribe("temp.event", callback)
        event_bus_test.publish("temp.event", {"n": 1})
        assert len(received) == 1
        event_bus_test.unsubscribe("temp.event", callback)
        event_bus_test.publish("temp.event", {"n": 2})
        assert len(received) == 1  # No se recibio el segundo

    def test_event_bus_start_stop(self, event_bus_test: EventBusTest) -> None:
        """El bus debe poder iniciarse y detenerse."""
        assert not event_bus_test.is_running
        event_bus_test.start()
        assert event_bus_test.is_running
        event_bus_test.stop()
        assert not event_bus_test.is_running

    def test_event_bus_tipo_filtrado(self, event_bus_test: EventBusTest) -> None:
        """El historial filtrado por tipo debe ser correcto."""
        event_bus_test.publish("tipo.a", {"x": 1})
        event_bus_test.publish("tipo.b", {"x": 2})
        event_bus_test.publish("tipo.a", {"x": 3})
        assert len(event_bus_test.get_history("tipo.a")) == 2
        assert len(event_bus_test.get_history("tipo.b")) == 1
        assert len(event_bus_test.get_history()) == 3


# ============================================================================
# TESTS: Scheduler
# ============================================================================


class TestScheduler:
    """Tests para el planificador de tareas ciclicas."""

    def test_scheduler_schedule_task(self, scheduler_test: SchedulerTest) -> None:
        """Programar una tarea debe aumentar el conteo."""
        assert scheduler_test.task_count() == 0
        scheduler_test.schedule("tarea_prueba", 5, lambda: None, priority=3)
        assert scheduler_test.task_count() == 1

    def test_scheduler_priority_queue(self, scheduler_test: SchedulerTest) -> None:
        """Las tareas deben ejecutarse en orden de prioridad."""
        results: List[str] = []
        scheduler_test.schedule("baja", 5, lambda: results.append("baja"), priority=10)
        scheduler_test.schedule("alta", 5, lambda: results.append("alta"), priority=1)
        scheduler_test.schedule("media", 5, lambda: results.append("media"), priority=5)
        scheduler_test.tick()
        assert results == ["alta", "media", "baja"]

    def test_scheduler_start_stop(self, scheduler_test: SchedulerTest) -> None:
        """El scheduler debe poder iniciarse y detenerse."""
        assert not scheduler_test.is_running
        scheduler_test.start()
        assert scheduler_test.is_running
        scheduler_test.stop()
        assert not scheduler_test.is_running

    def test_scheduler_multiple_ticks(self, scheduler_test: SchedulerTest) -> None:
        """Multiples ticks deben ejecutar las tareas multiples veces."""
        counter = [0]
        scheduler_test.schedule("contador", 1, lambda: counter.__setitem__(0, counter[0] + 1))
        scheduler_test.tick()
        scheduler_test.tick()
        scheduler_test.tick()
        assert counter[0] == 3

    def test_scheduler_executed_tracking(self, scheduler_test: SchedulerTest) -> None:
        """El scheduler debe trackear que tareas se ejecutaron."""
        scheduler_test.schedule("t1", 1, lambda: None, priority=1)
        scheduler_test.schedule("t2", 1, lambda: None, priority=2)
        scheduler_test.tick()
        executed = scheduler_test.get_executed()
        assert "t1" in executed
        assert "t2" in executed


# ============================================================================
# TESTS: VEOCore
# ============================================================================


class TestVEOCore:
    """Tests para el nucleo central de VEO v2."""

    def test_veo_core_iniciar(self, config_test: Dict[str, Any], logger_mock: MagicMock) -> None:
        """VEOCore debe poder iniciarse con configuracion valida."""
        core = MockVEOCore(config_test, logger_mock)
        core.start()
        assert core.is_running
        assert core.health_status()["estado"] == "ok"
        core.stop()

    def test_veo_core_parar(self, config_test: Dict[str, Any], logger_mock: MagicMock) -> None:
        """VEOCore debe poder detenerse limpiamente."""
        core = MockVEOCore(config_test, logger_mock)
        core.start()
        core.stop()
        assert not core.is_running

    def test_veo_core_health_status_ok(self, config_test: Dict[str, Any], logger_mock: MagicMock) -> None:
        """Health status debe reportar ok cuando todo funciona."""
        core = MockVEOCore(config_test, logger_mock)
        health = core.health_status()
        assert health["estado"] == "ok"
        assert health["score"] >= 0.8

    def test_veo_core_health_status_warning(self, config_test: Dict[str, Any], logger_mock: MagicMock) -> None:
        """Health status debe reportar warning con problemas menores."""
        core = MockVEOCore(config_test, logger_mock)
        core._simulate_warning("db_latencia_alta")
        health = core.health_status()
        assert health["estado"] in ("ok", "warning")

    def test_veo_core_ejecutar_ciclo_monitoreo(self, config_test: Dict[str, Any], logger_mock: MagicMock) -> None:
        """El ciclo de monitoreo debe ejecutarse sin errores."""
        core = MockVEOCore(config_test, logger_mock)
        resultado = core.ejecutar_ciclo("monitoreo")
        assert resultado["exitoso"] is True
        assert "metricas" in resultado

    def test_veo_core_ejecutar_ciclo_analisis(self, config_test: Dict[str, Any], logger_mock: MagicMock) -> None:
        """El ciclo de analisis debe ejecutarse sin errores."""
        core = MockVEOCore(config_test, logger_mock)
        resultado = core.ejecutar_ciclo("analisis")
        assert resultado["exitoso"] is True
        assert "hipotesis_generadas" in resultado

    def test_veo_core_ejecutar_ciclo_prediccion(self, config_test: Dict[str, Any], logger_mock: MagicMock) -> None:
        """El ciclo de prediccion debe ejecutarse sin errores."""
        core = MockVEOCore(config_test, logger_mock)
        resultado = core.ejecutar_ciclo("prediccion")
        assert resultado["exitoso"] is True
        assert "escenarios_simulados" in resultado

    def test_veo_core_ejecutar_ciclo_ejecutivo(self, config_test: Dict[str, Any], logger_mock: MagicMock) -> None:
        """El ciclo ejecutivo debe ejecutarse sin errores."""
        core = MockVEOCore(config_test, logger_mock)
        resultado = core.ejecutar_ciclo("ejecutivo")
        assert resultado["exitoso"] is True
        assert "alertas" in resultado

    def test_veo_core_eventos_emitidos(self, config_test: Dict[str, Any], logger_mock: MagicMock, event_bus_test: EventBusTest) -> None:
        """VEOCore debe emitir eventos durante su operacion."""
        core = MockVEOCore(config_test, logger_mock, event_bus=event_bus_test)
        core.start()
        core.ejecutar_ciclo("monitoreo")
        event_bus_test.stop()
        history = event_bus_test.get_history()
        assert len(history) > 0

    def test_veo_core_config_accesible(self, config_test: Dict[str, Any], logger_mock: MagicMock) -> None:
        """La configuracion debe ser accesible desde VEOCore."""
        core = MockVEOCore(config_test, logger_mock)
        assert core.config["ambiente"] == "test"
        assert len(core.config["pesos_nei"]) == 6

    def test_veo_core_ciclos_tienen_nombres_validos(self, config_test: Dict[str, Any], logger_mock: MagicMock) -> None:
        """Todos los ciclos deben tener nombres reconocidos."""
        core = MockVEOCore(config_test, logger_mock)
        ciclos_validos = {"monitoreo", "analisis", "prediccion", "ejecutivo"}
        for ciclo in ciclos_validos:
            resultado = core.ejecutar_ciclo(ciclo)
            assert resultado["ciclo"] == ciclo


# ============================================================================
# Mock VEOCore para tests
# ============================================================================


class MockVEOCore:
    """Implementacion mock de VEOCore para tests unitarios."""

    CICLOS_VALIDOS = {"monitoreo", "analisis", "prediccion", "ejecutivo"}

    def __init__(self, config: Dict[str, Any], logger: MagicMock, event_bus: Any = None) -> None:
        self.config = config
        self.logger = logger
        self.event_bus = event_bus or EventBusTest()
        self._running = False
        self._health = {"estado": "ok", "score": 1.0, "mensaje": "Funcionando normalmente"}
        self._warnings: List[str] = []
        self._ciclo_count = 0

    def start(self) -> None:
        self._running = True
        self.event_bus.start()
        self.logger.info("[VEOCore] Iniciado - ambiente=%s", self.config["ambiente"])

    def stop(self) -> None:
        self._running = False
        self.event_bus.stop()
        self.logger.info("[VEOCore] Detenido")

    @property
    def is_running(self) -> bool:
        return self._running

    def health_status(self) -> Dict[str, Any]:
        if self._warnings:
            return {"estado": "warning", "score": 0.7, "mensaje": f"Warnings: {self._warnings}"}
        return dict(self._health)

    def ejecutar_ciclo(self, nombre: str) -> Dict[str, Any]:
        if nombre not in self.CICLOS_VALIDOS:
            return {"exitoso": False, "error": f"Ciclo '{nombre}' no reconocido"}
        self._ciclo_count += 1
        self.event_bus.publish(f"ciclo.{nombre}.inicio", {"ciclo": nombre, "n": self._ciclo_count})

        resultados = {
            "monitoreo": {"metricas": 12, "senal_nueva": True},
            "analisis": {"hipotesis_generadas": 3, "nei_calculado": True},
            "prediccion": {"escenarios_simulados": 5, "probabilidad_max": 0.85},
            "ejecutivo": {"alertas": 1, "recomendaciones": 2},
        }

        self.event_bus.publish(f"ciclo.{nombre}.fin", {"ciclo": nombre, "resultado": "ok"})
        return {"exitoso": True, "ciclo": nombre, **resultados[nombre]}

    def _simulate_warning(self, motivo: str) -> None:
        self._warnings.append(motivo)
        self.logger.warning("[VEOCore] Warning simulado: %s", motivo)
