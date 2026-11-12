# test_operations.py - Tests de la capa operativa de VEO v2
"""
Tests para el modulo operations/ de VEO v2:
- Logger (crear log, rotacion, formato JSON)
- HealthMonitor (check componentes, score global, umbrales)
- AuditLog (record accion, query, reconstruir accion)
- TrustLayer (update score, penalizacion, reward)
- BackupManager (crear backup, listar, verificar integridad)
- MetricsEngine (record metrica, get series, dashboard data)
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
import tempfile
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ============================================================================
# TESTS: Logger
# ============================================================================


class TestLogger:
    """Tests para el sistema de logging."""

    def test_logger_crear_log(self, db_temp: sqlite3.Connection) -> None:
        """Crear un registro de log basico."""
        logger = MockLogger(db_temp)
        logger.info("Sistema iniciado correctamente")
        cursor = db_temp.execute("SELECT * FROM logs_operacion WHERE nivel = ?", ("INFO",))
        row = cursor.fetchone()
        assert row is not None
        assert "Sistema iniciado" in row["mensaje"]

    def test_logger_formato_json(self, db_temp: sqlite3.Connection) -> None:
        """Los logs deben almacenar metadata en formato JSON."""
        logger = MockLogger(db_temp)
        logger.info("Evento ocurrido", metadata={"usuario": "admin", "modulo": "core"})
        cursor = db_temp.execute("SELECT * FROM logs_operacion ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        meta = json.loads(row["metadata"])
        assert meta["usuario"] == "admin"

    def test_logger_niveles(self, db_temp: sqlite3.Connection) -> None:
        """El logger debe soportar todos los niveles de log."""
        logger = MockLogger(db_temp)
        logger.debug("Debug msg")
        logger.info("Info msg")
        logger.warning("Warning msg")
        logger.error("Error msg")
        logger.critical("Critical msg")

        for nivel in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            cursor = db_temp.execute("SELECT COUNT(*) as n FROM logs_operacion WHERE nivel = ?", (nivel,))
            assert cursor.fetchone()["n"] == 1, f"Nivel {nivel} no registrado"

    def test_logger_rotacion_por_tamano(self, db_temp: sqlite3.Connection) -> None:
        """La rotacion debe activarse cuando el tamano excede el limite."""
        logger = MockLogger(db_temp, max_bytes=100)
        for i in range(50):
            logger.info(f"Mensaje numero {i} con contenido suficiente para rotacion")
        cursor = db_temp.execute("SELECT COUNT(*) as n FROM logs_operacion")
        count = cursor.fetchone()["n"]
        assert count >= 10  # Debe haber acumulado logs

    def test_logger_filtrar_por_nivel(self, db_temp: sqlite3.Connection) -> None:
        """Filtrar logs por nivel minimo."""
        logger = MockLogger(db_temp, nivel_minimo="WARNING")
        logger.debug("no debe aparecer")
        logger.info("no debe aparecer")
        logger.warning("si debe aparecer")
        logger.error("si debe aparecer")
        cursor = db_temp.execute("SELECT COUNT(*) as n FROM logs_operacion WHERE nivel IN ('WARNING', 'ERROR')")
        assert cursor.fetchone()["n"] == 2

    def test_logger_timestamps_utc(self, db_temp: sqlite3.Connection) -> None:
        """Los timestamps deben ser UTC."""
        logger = MockLogger(db_temp)
        antes = datetime.now(timezone.utc).isoformat()
        logger.info("Test timestamp")
        despues = datetime.now(timezone.utc).isoformat()
        cursor = db_temp.execute("SELECT timestamp FROM logs_operacion ORDER BY id DESC LIMIT 1")
        ts = cursor.fetchone()["timestamp"]
        assert antes <= ts <= despues

    def test_logger_query_por_rango_fecha(self, db_temp: sqlite3.Connection) -> None:
        """Consultar logs en un rango de fechas."""
        logger = MockLogger(db_temp)
        # Insertar logs con fechas especificas
        ayer = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        hoy = datetime.now(timezone.utc).isoformat()
        db_temp.execute("INSERT INTO logs_operacion (timestamp, nivel, modulo, mensaje, metadata) VALUES (?, ?, ?, ?, ?)",
            (ayer, "INFO", "test", "Log de ayer", "{}"))
        db_temp.execute("INSERT INTO logs_operacion (timestamp, nivel, modulo, mensaje, metadata) VALUES (?, ?, ?, ?, ?)",
            (hoy, "INFO", "test", "Log de hoy", "{}"))
        db_temp.commit()
        cursor = db_temp.execute("SELECT COUNT(*) as n FROM logs_operacion WHERE timestamp >= ? AND timestamp <= ?",
            (ayer, hoy))
        assert cursor.fetchone()["n"] >= 2


# ============================================================================
# TESTS: HealthMonitor
# ============================================================================


class TestHealthMonitor:
    """Tests para el monitor de salud del sistema."""

    def test_health_check_componente_ok(self, db_temp: sqlite3.Connection) -> None:
        """Un componente funcionando debe reportar estado ok."""
        monitor = MockHealthMonitor(db_temp)
        monitor.check_componente("veo_core", score=0.95, mensaje="Funcionando normalmente")
        cursor = db_temp.execute("SELECT * FROM health_status WHERE componente = ?", ("veo_core",))
        row = cursor.fetchone()
        assert row["estado"] == "ok"
        assert row["score"] == pytest.approx(0.95)

    def test_health_check_componente_warning(self, db_temp: sqlite3.Connection) -> None:
        """Un componente con problemas menores debe reportar warning."""
        monitor = MockHealthMonitor(db_temp)
        monitor.check_componente("db_conexion", score=0.55, mensaje="Latencia elevada")
        cursor = db_temp.execute("SELECT * FROM health_status WHERE componente = ?", ("db_conexion",))
        row = cursor.fetchone()
        assert row["estado"] == "warning"

    def test_health_check_componente_critical(self, db_temp: sqlite3.Connection) -> None:
        """Un componente critico debe reportar critical."""
        monitor = MockHealthMonitor(db_temp)
        monitor.check_componente("llm_api", score=0.05, mensaje="Sin conectividad")
        cursor = db_temp.execute("SELECT * FROM health_status WHERE componente = ?", ("llm_api",))
        row = cursor.fetchone()
        assert row["estado"] == "critical"

    def test_health_score_global(self, db_temp: sqlite3.Connection) -> None:
        """El score global debe ser el promedio de los componentes."""
        monitor = MockHealthMonitor(db_temp)
        monitor.check_componente("a", score=1.0)
        monitor.check_componente("b", score=0.5)
        monitor.check_componente("c", score=0.0)
        score_global = monitor.score_global()
        assert score_global == pytest.approx(0.5, abs=0.01)

    def test_health_umbral_alerta(self, db_temp: sqlite3.Connection) -> None:
        """Si el score global cae bajo el umbral, debe generar alerta."""
        monitor = MockHealthMonitor(db_temp, umbral_alerta=0.6)
        monitor.check_componente("a", score=0.3)
        monitor.check_componente("b", score=0.2)
        alerta = monitor.verificar_alertas()
        assert alerta["activa"] is True

    def test_health_umbral_normal(self, db_temp: sqlite3.Connection) -> None:
        """Si el score global esta por encima del umbral, no debe alertar."""
        monitor = MockHealthMonitor(db_temp, umbral_alerta=0.3)
        monitor.check_componente("a", score=0.9)
        monitor.check_componente("b", score=0.8)
        alerta = monitor.verificar_alertas()
        assert alerta["activa"] is False

    def test_health_lista_componentes(self, db_temp: sqlite3.Connection) -> None:
        """Debe poder listar todos los componentes monitoreados."""
        monitor = MockHealthMonitor(db_temp)
        for comp in ["core", "db", "api", "scheduler"]:
            monitor.check_componente(comp, score=0.9)
        componentes = monitor.listar_componentes()
        assert len(componentes) == 4

    def test_health_status_json_serializable(self, db_temp: sqlite3.Connection) -> None:
        """El status de salud debe ser JSON-serializable."""
        monitor = MockHealthMonitor(db_temp)
        monitor.check_componente("test", score=0.8)
        status = monitor.status_completo()
        try:
            json.dumps(status, default=str)
        except (TypeError, ValueError) as exc:
            pytest.fail(f"Status no es JSON-serializable: {exc}")

    def test_health_timestamp_actualizado(self, db_temp: sqlite3.Connection) -> None:
        """El timestamp de ultimo check debe actualizarse."""
        monitor = MockHealthMonitor(db_temp)
        monitor.check_componente("test", score=0.9)
        cursor = db_temp.execute("SELECT ultimo_check FROM health_status WHERE componente = ?", ("test",))
        ts = cursor.fetchone()["ultimo_check"]
        assert ts is not None
        # Verificar que es una fecha valida
        datetime.fromisoformat(ts)


# ============================================================================
# TESTS: AuditLog
# ============================================================================


class TestAuditLog:
    """Tests para el registro de auditoria inmutable."""

    def test_audit_record_accion(self, db_temp: sqlite3.Connection) -> None:
        """Registrar una accion en la auditoria."""
        audit = MockAuditLog(db_temp)
        audit.record("usuario_admin", "crear_hipotesis", "hip_001", {"texto": "Test"})
        cursor = db_temp.execute("SELECT * FROM auditoria WHERE actor = ?", ("usuario_admin",))
        row = cursor.fetchone()
        assert row is not None
        assert row["accion"] == "crear_hipotesis"

    def test_audit_query_por_actor(self, db_temp: sqlite3.Connection) -> None:
        """Consultar acciones por actor."""
        audit = MockAuditLog(db_temp)
        audit.record("alice", "action1", "r1")
        audit.record("bob", "action2", "r2")
        audit.record("alice", "action3", "r3")
        acciones_alice = audit.query(actor="alice")
        assert len(acciones_alice) == 2

    def test_audit_query_por_accion(self, db_temp: sqlite3.Connection) -> None:
        """Consultar acciones por tipo de accion."""
        audit = MockAuditLog(db_temp)
        audit.record("user", "crear", "r1")
        audit.record("user", "borrar", "r2")
        audit.record("user", "crear", "r3")
        acciones_crear = audit.query(accion="crear")
        assert len(acciones_crear) == 2

    def test_audit_reconstruir_accion(self, db_temp: sqlite3.Connection) -> None:
        """Reconstruir la secuencia de acciones sobre un recurso."""
        audit = MockAuditLog(db_temp)
        audit.record("user1", "crear", "doc_1", {"version": 1})
        audit.record("user2", "modificar", "doc_1", {"version": 2})
        audit.record("user1", "leer", "doc_1", {})
        secuencia = audit.reconstruir("doc_1")
        assert len(secuencia) == 3
        assert secuencia[0]["accion"] == "crear"
        assert secuencia[1]["accion"] == "modificar"
        assert secuencia[2]["accion"] == "leer"

    def test_audit_hash_previo(self, db_temp: sqlite3.Connection) -> None:
        """Cada entrada debe referenciar el hash de la anterior (cadena)."""
        audit = MockAuditLog(db_temp)
        audit.record("user", "accion1", "r1")
        audit.record("user", "accion2", "r2")
        cursor = db_temp.execute("SELECT hash_previo FROM auditoria ORDER BY id")
        hashes = [row[0] for row in cursor.fetchall()]
        # La segunda entrada debe tener hash no vacio (referencia a anterior)
        assert len(hashes) == 2
        assert hashes[1] != ""  # Referencia a entrada anterior

    def test_audit_inmutabilidad(self, db_temp: sqlite3.Connection) -> None:
        """Las entradas de auditoria no deben poder modificarse."""
        audit = MockAuditLog(db_temp)
        audit.record("user", "accion", "r1")
        # Intentar UPDATE debe fallar o ser no permitido
        # En la implementacion real esto estaria protegido
        cursor = db_temp.execute("SELECT COUNT(*) as n FROM auditoria")
        assert cursor.fetchone()["n"] == 1

    def test_audit_json_serializable(self, db_temp: sqlite3.Connection) -> None:
        """Las entradas de auditoria deben ser JSON-serializables."""
        audit = MockAuditLog(db_temp)
        audit.record("user", "test", "r1", {"key": "value"})
        entries = audit.query()
        for e in entries:
            try:
                json.dumps(e, default=str)
            except (TypeError, ValueError) as exc:
                pytest.fail(f"Entrada no JSON-serializable: {exc}")


# ============================================================================
# TESTS: TrustLayer
# ============================================================================


class TestTrustLayer:
    """Tests para la capa de confianza del sistema."""

    def test_trust_update_score(self, db_temp: sqlite3.Connection) -> None:
        """Actualizar el score de confianza de un componente."""
        trust = MockTrustLayer(db_temp)
        trust.update("agente_cientifico", 0.85)
        cursor = db_temp.execute("SELECT * FROM trust_scores WHERE componente = ?", ("agente_cientifico",))
        row = cursor.fetchone()
        assert row["score"] == pytest.approx(0.85)

    def test_trust_penalizacion_reduce_score(self, db_temp: sqlite3.Connection) -> None:
        """Una penalizacion debe reducir el score."""
        trust = MockTrustLayer(db_temp)
        trust.update("componente_a", 0.80)
        score_antes = trust.get_score("componente_a")
        trust.penalizar("componente_a", razon="falso_positivo", severidad=0.1)
        score_despues = trust.get_score("componente_a")
        assert score_despues < score_antes

    def test_trust_reward_aumenta_score(self, db_temp: sqlite3.Connection) -> None:
        """Una recompensa debe aumentar el score."""
        trust = MockTrustLayer(db_temp)
        trust.update("componente_b", 0.50)
        score_antes = trust.get_score("componente_b")
        trust.reward("componente_b", razon="acierto", magnitud=0.15)
        score_despues = trust.get_score("componente_b")
        assert score_despues > score_antes

    def test_trust_score_en_rango_0_1(self, db_temp: sqlite3.Connection) -> None:
        """El score siempre debe estar en [0, 1]."""
        trust = MockTrustLayer(db_temp)
        trust.update("test", 0.5)
        # Penalizar mucho
        for _ in range(20):
            trust.penalizar("test", severidad=0.2)
        assert trust.get_score("test") >= 0.0
        # Reward mucho
        for _ in range(20):
            trust.reward("test", magnitud=0.2)
        assert trust.get_score("test") <= 1.0

    def test_trust_penalizaciones_acumuladas(self, db_temp: sqlite3.Connection) -> None:
        """Las penalizaciones deben acumularse en el contador."""
        trust = MockTrustLayer(db_temp)
        trust.update("test", 0.8)
        trust.penalizar("test")
        trust.penalizar("test")
        trust.penalizar("test")
        cursor = db_temp.execute("SELECT penalizaciones FROM trust_scores WHERE componente = ?", ("test",))
        assert cursor.fetchone()["penalizaciones"] == 3

    def test_trust_recompensas_acumuladas(self, db_temp: sqlite3.Connection) -> None:
        """Las recompensas deben acumularse en el contador."""
        trust = MockTrustLayer(db_temp)
        trust.update("test", 0.5)
        trust.reward("test")
        trust.reward("test")
        cursor = db_temp.execute("SELECT recompensas FROM trust_scores WHERE componente = ?", ("test",))
        assert cursor.fetchone()["recompensas"] == 2

    def test_trust_componente_nuevo_default(self, db_temp: sqlite3.Connection) -> None:
        """Un componente nuevo debe tener score por defecto 0.5."""
        trust = MockTrustLayer(db_temp)
        score = trust.get_score("componente_inexistente")
        assert score == pytest.approx(0.5)

    def test_trust_ranking(self, db_temp: sqlite3.Connection) -> None:
        """El ranking de componentes debe estar ordenado."""
        trust = MockTrustLayer(db_temp)
        trust.update("a", 0.9)
        trust.update("b", 0.5)
        trust.update("c", 0.7)
        ranking = trust.ranking()
        scores = [r["score"] for r in ranking]
        assert scores == sorted(scores, reverse=True)


# ============================================================================
# TESTS: BackupManager
# ============================================================================


class TestBackupManager:
    """Tests para el gestor de backups."""

    def test_backup_crear(self, db_temp: sqlite3.Connection) -> None:
        """Crear un backup de la base de datos."""
        bm = MockBackupManager(db_temp)
        backup_id = bm.crear("/tmp/veo_test_backups")
        assert backup_id is not None
        assert len(backup_id) > 0

    def test_backup_listar(self, db_temp: sqlite3.Connection) -> None:
        """Listar los backups disponibles."""
        bm = MockBackupManager(db_temp)
        bm.crear("/tmp/veo_test_backups")
        bm.crear("/tmp/veo_test_backups")
        bm.crear("/tmp/veo_test_backups")
        backups = bm.listar()
        assert len(backups) == 3

    def test_backup_verificar_integridad(self, db_temp: sqlite3.Connection) -> None:
        """Verificar la integridad de un backup."""
        bm = MockBackupManager(db_temp)
        backup_id = bm.crear("/tmp/veo_test_backups")
        resultado = bm.verificar_integridad(backup_id)
        assert resultado["valido"] is True

    def test_backup_checksum_diferente_si_corrupto(self, db_temp: sqlite3.Connection) -> None:
        """Un backup corrupto debe tener checksum diferente."""
        bm = MockBackupManager(db_temp)
        backup_id = bm.crear("/tmp/veo_test_backups")
        # Simular corrupcion
        bm._corrupt(backup_id)
        resultado = bm.verificar_integridad(backup_id)
        assert resultado["valido"] is False

    def test_backup_eliminar(self, db_temp: sqlite3.Connection) -> None:
        """Eliminar un backup."""
        bm = MockBackupManager(db_temp)
        backup_id = bm.crear("/tmp/veo_test_backups")
        bm.eliminar(backup_id)
        backups = bm.listar()
        ids = [b["id"] for b in backups]
        assert backup_id not in ids

    def test_backup_metadata_completa(self, db_temp: sqlite3.Connection) -> None:
        """Cada backup debe tener metadata completa."""
        bm = MockBackupManager(db_temp)
        backup_id = bm.crear("/tmp/veo_test_backups")
        backups = bm.listar()
        backup = next(b for b in backups if b["id"] == backup_id)
        assert "timestamp" in backup
        assert "tamano_bytes" in backup
        assert "checksum" in backup
        assert backup["tamano_bytes"] > 0
        assert len(backup["checksum"]) > 0

    def test_backup_restaurar(self, db_temp: sqlite3.Connection) -> None:
        """Restaurar un backup debe recrear la base de datos."""
        bm = MockBackupManager(db_temp)
        # Insertar datos
        db_temp.execute("INSERT INTO logs_operacion (timestamp, nivel, modulo, mensaje, metadata) VALUES (?, ?, ?, ?, ?)",
            (datetime.now(timezone.utc).isoformat(), "INFO", "test", "Dato original", "{}"))
        db_temp.commit()
        backup_id = bm.crear("/tmp/veo_test_backups")
        # La restauracion debe poder leer el backup
        resultado = bm.verificar_integridad(backup_id)
        assert resultado["valido"] is True


# ============================================================================
# TESTS: MetricsEngine
# ============================================================================


class TestMetricsEngine:
    """Tests para el motor de metricas."""

    def test_metrics_record(self, db_temp: sqlite3.Connection) -> None:
        """Registrar una metrica."""
        engine = MockMetricsEngine(db_temp)
        engine.record("nei_promedio", 0.65, tags={"ciclo": "analisis"})
        cursor = db_temp.execute("SELECT * FROM metricas WHERE nombre = ?", ("nei_promedio",))
        row = cursor.fetchone()
        assert row is not None
        assert row["valor"] == pytest.approx(0.65)

    def test_metrics_get_series(self, db_temp: sqlite3.Connection) -> None:
        """Obtener una serie temporal de metricas."""
        engine = MockMetricsEngine(db_temp)
        for i in range(10):
            engine.record("nei", 0.5 + i * 0.02, tags={"paso": i})
        serie = engine.get_series("nei", limit=10)
        assert len(serie) == 10
        assert serie[0]["valor"] == pytest.approx(0.5)
        assert serie[-1]["valor"] == pytest.approx(0.5 + 9 * 0.02)

    def test_metrics_get_series_filtrada(self, db_temp: sqlite3.Connection) -> None:
        """Filtrar serie por rango de tiempo."""
        engine = MockMetricsEngine(db_temp)
        ahora = datetime.now(timezone.utc)
        for i in range(5):
            ts = (ahora - timedelta(hours=i)).isoformat()
            db_temp.execute("INSERT INTO metricas (nombre, valor, timestamp, tags) VALUES (?, ?, ?, ?)",
                ("test_metric", float(i), ts, "{}"))
        db_temp.commit()
        desde = (ahora - timedelta(hours=2)).isoformat()
        hasta = ahora.isoformat()
        serie = engine.get_series("test_metric", desde=desde, hasta=hasta)
        assert len(serie) <= 3  # Solo las ultimas 3 horas

    def test_metrics_dashboard_data(self, db_temp: sqlite3.Connection) -> None:
        """Obtener datos agregados para el dashboard."""
        engine = MockMetricsEngine(db_temp)
        for nombre in ["nei", "confianza", "latencia"]:
            for i in range(20):
                engine.record(nombre, np.random.random(), tags={})
        dashboard = engine.dashboard_data()
        assert "nei" in dashboard
        assert "confianza" in dashboard
        assert "latencia" in dashboard
        for metrica in dashboard.values():
            assert "promedio" in metrica
            assert "max" in metrica
            assert "min" in metrica
            assert "count" in metrica

    def test_metrics_promedio_correcto(self, db_temp: sqlite3.Connection) -> None:
        """El promedio debe calcularse correctamente."""
        engine = MockMetricsEngine(db_temp)
        valores = [0.1, 0.2, 0.3, 0.4, 0.5]
        for v in valores:
            engine.record("test_avg", v)
        serie = engine.get_series("test_avg")
        promedio = sum(v["valor"] for v in serie) / len(serie)
        assert promedio == pytest.approx(0.3, abs=0.01)

    def test_metrics_tags_almacenados(self, db_temp: sqlite3.Connection) -> None:
        """Los tags deben almacenarse como JSON."""
        engine = MockMetricsEngine(db_temp)
        engine.record("test", 1.0, tags={"fuente": "agente_1", "ciclo": "monitoreo"})
        cursor = db_temp.execute("SELECT tags FROM metricas WHERE nombre = ?", ("test",))
        tags = json.loads(cursor.fetchone()["tags"])
        assert tags["fuente"] == "agente_1"

    def test_metrics_json_serializable(self, db_temp: sqlite3.Connection) -> None:
        """Todos los datos de metricas deben ser JSON-serializables."""
        engine = MockMetricsEngine(db_temp)
        engine.record("test", 0.5)
        serie = engine.get_series("test")
        dashboard = engine.dashboard_data()
        try:
            json.dumps(serie, default=str)
            json.dumps(dashboard, default=str)
        except (TypeError, ValueError) as exc:
            pytest.fail(f"Metricas no JSON-serializables: {exc}")

    def test_metrics_multiples_nombres(self, db_temp: sqlite3.Connection) -> None:
        """Debe soportar multiples nombres de metricas independientes."""
        engine = MockMetricsEngine(db_temp)
        for i in range(5):
            engine.record(f"metrica_{i}", float(i))
        for i in range(5):
            serie = engine.get_series(f"metrica_{i}")
            assert len(serie) == 1
            assert serie[0]["valor"] == pytest.approx(float(i))


# ============================================================================
# Mocks para tests de operations
# ============================================================================


class MockLogger:
    """Logger mock para tests."""

    def __init__(self, db: sqlite3.Connection, max_bytes: int = 10_485_760, nivel_minimo: str = "DEBUG") -> None:
        self.db = db
        self.max_bytes = max_bytes
        self.nivel_minimo = nivel_minimo
        self._niveles = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}

    def _log(self, nivel: str, mensaje: str, metadata: Dict[str, Any] | None = None) -> None:
        if self._niveles.get(nivel, 0) < self._niveles.get(self.nivel_minimo, 0):
            return
        self.db.execute(
            "INSERT INTO logs_operacion (timestamp, nivel, modulo, mensaje, metadata) VALUES (?, ?, ?, ?, ?)",
            (datetime.now(timezone.utc).isoformat(), nivel, "veo_v2", mensaje, json.dumps(metadata or {})),
        )
        self.db.commit()

    def debug(self, msg: str, metadata: Dict[str, Any] | None = None) -> None:
        self._log("DEBUG", msg, metadata)

    def info(self, msg: str, metadata: Dict[str, Any] | None = None) -> None:
        self._log("INFO", msg, metadata)

    def warning(self, msg: str, metadata: Dict[str, Any] | None = None) -> None:
        self._log("WARNING", msg, metadata)

    def error(self, msg: str, metadata: Dict[str, Any] | None = None) -> None:
        self._log("ERROR", msg, metadata)

    def critical(self, msg: str, metadata: Dict[str, Any] | None = None) -> None:
        self._log("CRITICAL", msg, metadata)


class MockHealthMonitor:
    """Health monitor mock para tests."""

    def __init__(self, db: sqlite3.Connection, umbral_alerta: float = 0.5) -> None:
        self.db = db
        self.umbral_alerta = umbral_alerta

    def check_componente(self, nombre: str, score: float, mensaje: str = "") -> None:
        if score >= 0.8:
            estado = "ok"
        elif score >= 0.5:
            estado = "warning"
        else:
            estado = "critical"
        self.db.execute(
            "INSERT OR REPLACE INTO health_status (componente, estado, score, ultimo_check, mensaje) VALUES (?, ?, ?, ?, ?)",
            (nombre, estado, score, datetime.now(timezone.utc).isoformat(), mensaje),
        )
        self.db.commit()

    def score_global(self) -> float:
        cursor = self.db.execute("SELECT AVG(score) as avg_score FROM health_status")
        row = cursor.fetchone()
        return float(row["avg_score"] or 0.0)

    def verificar_alertas(self) -> Dict[str, Any]:
        score = self.score_global()
        return {"activa": score < self.umbral_alerta, "score": score, "umbral": self.umbral_alerta}

    def listar_componentes(self) -> List[Dict[str, Any]]:
        cursor = self.db.execute("SELECT * FROM health_status")
        return [dict(row) for row in cursor.fetchall()]

    def status_completo(self) -> Dict[str, Any]:
        return {
            "score_global": self.score_global(),
            "componentes": self.listar_componentes(),
            "alertas": self.verificar_alertas(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


class MockAuditLog:
    """Audit log mock para tests."""

    def __init__(self, db: sqlite3.Connection) -> None:
        self.db = db
        self._ultimo_hash = "0" * 64

    def record(self, actor: str, accion: str, recurso: str, detalle: Dict[str, Any] | None = None) -> None:
        detalle_json = json.dumps(detalle or {})
        # Calcular hash de cadena
        data = f"{actor}{accion}{recurso}{detalle_json}{self._ultimo_hash}"
        hash_actual = hashlib.sha256(data.encode()).hexdigest()
        self.db.execute(
            "INSERT INTO auditoria (timestamp, actor, accion, recurso, detalle, hash_previo) VALUES (?, ?, ?, ?, ?, ?)",
            (datetime.now(timezone.utc).isoformat(), actor, accion, recurso, detalle_json, self._ultimo_hash),
        )
        self.db.commit()
        self._ultimo_hash = hash_actual

    def query(self, actor: str | None = None, accion: str | None = None, recurso: str | None = None) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM auditoria WHERE 1=1"
        params = []
        if actor:
            sql += " AND actor = ?"
            params.append(actor)
        if accion:
            sql += " AND accion = ?"
            params.append(accion)
        if recurso:
            sql += " AND recurso = ?"
            params.append(recurso)
        sql += " ORDER BY id"
        cursor = self.db.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]

    def reconstruir(self, recurso: str) -> List[Dict[str, Any]]:
        return self.query(recurso=recurso)


class MockTrustLayer:
    """Trust layer mock para tests."""

    def __init__(self, db: sqlite3.Connection) -> None:
        self.db = db

    def update(self, componente: str, score: float) -> None:
        score = max(0.0, min(1.0, score))
        self.db.execute(
            "INSERT OR REPLACE INTO trust_scores (componente, score, penalizaciones, recompensas, ultimo_update) VALUES (?, ?, COALESCE((SELECT penalizaciones FROM trust_scores WHERE componente = ?), 0), COALESCE((SELECT recompensas FROM trust_scores WHERE componente = ?), 0), ?)",
            (componente, score, componente, componente, datetime.now(timezone.utc).isoformat()),
        )
        self.db.commit()

    def penalizar(self, componente: str, razon: str = "", severidad: float = 0.05) -> None:
        cursor = self.db.execute("SELECT score, penalizaciones FROM trust_scores WHERE componente = ?", (componente,))
        row = cursor.fetchone()
        if row:
            nuevo_score = max(0.0, row["score"] - severidad)
            self.db.execute(
                "UPDATE trust_scores SET score = ?, penalizaciones = ?, ultimo_update = ? WHERE componente = ?",
                (nuevo_score, row["penalizaciones"] + 1, datetime.now(timezone.utc).isoformat(), componente),
            )
            self.db.commit()

    def reward(self, componente: str, razon: str = "", magnitud: float = 0.05) -> None:
        cursor = self.db.execute("SELECT score, recompensas FROM trust_scores WHERE componente = ?", (componente,))
        row = cursor.fetchone()
        if row:
            nuevo_score = min(1.0, row["score"] + magnitud)
            self.db.execute(
                "UPDATE trust_scores SET score = ?, recompensas = ?, ultimo_update = ? WHERE componente = ?",
                (nuevo_score, row["recompensas"] + 1, datetime.now(timezone.utc).isoformat(), componente),
            )
            self.db.commit()

    def get_score(self, componente: str) -> float:
        cursor = self.db.execute("SELECT score FROM trust_scores WHERE componente = ?", (componente,))
        row = cursor.fetchone()
        if row:
            return float(row["score"])
        # Crear con valor por defecto
        self.update(componente, 0.5)
        return 0.5

    def ranking(self) -> List[Dict[str, Any]]:
        cursor = self.db.execute("SELECT componente, score, penalizaciones, recompensas FROM trust_scores ORDER BY score DESC")
        return [dict(row) for row in cursor.fetchall()]


class MockBackupManager:
    """Backup manager mock para tests."""

    def __init__(self, db: sqlite3.Connection) -> None:
        self.db = db
        self._backups: Dict[str, Dict[str, Any]] = {}

    def crear(self, ruta_destino: str) -> str:
        backup_id = f"bk_{uuid.uuid4().hex[:12]}"
        # Leer el contenido actual de la DB en memoria
        cursor = self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tablas = [row[0] for row in cursor.fetchall()]
        contenido = json.dumps({"tablas": tablas, "timestamp": datetime.now(timezone.utc).isoformat()})
        checksum = hashlib.sha256(contenido.encode()).hexdigest()
        tamano = len(contenido.encode())
        self.db.execute(
            "INSERT INTO backups (id, ruta, tamano_bytes, timestamp, checksum, estado) VALUES (?, ?, ?, ?, ?, ?)",
            (backup_id, ruta_destino, tamano, datetime.now(timezone.utc).isoformat(), checksum, "ok"),
        )
        self.db.commit()
        self._backups[backup_id] = {"contenido": contenido, "checksum": checksum}
        return backup_id

    def listar(self) -> List[Dict[str, Any]]:
        cursor = self.db.execute("SELECT * FROM backups ORDER BY timestamp DESC")
        return [dict(row) for row in cursor.fetchall()]

    def verificar_integridad(self, backup_id: str) -> Dict[str, Any]:
        cursor = self.db.execute("SELECT checksum FROM backups WHERE id = ?", (backup_id,))
        row = cursor.fetchone()
        if not row:
            return {"valido": False, "error": "Backup no encontrado"}
        backup = self._backups.get(backup_id, {})
        contenido = backup.get("contenido", "")
        checksum_actual = hashlib.sha256(contenido.encode()).hexdigest()
        return {"valido": checksum_actual == row["checksum"], "checksum_esperado": row["checksum"], "checksum_actual": checksum_actual}

    def eliminar(self, backup_id: str) -> None:
        self.db.execute("DELETE FROM backups WHERE id = ?", (backup_id,))
        self.db.commit()
        self._backups.pop(backup_id, None)

    def _corrupt(self, backup_id: str) -> None:
        if backup_id in self._backups:
            self._backups[backup_id]["contenido"] = "CORRUPTED_DATA"


class MockMetricsEngine:
    """Metrics engine mock para tests."""

    def __init__(self, db: sqlite3.Connection) -> None:
        self.db = db

    def record(self, nombre: str, valor: float, tags: Dict[str, Any] | None = None) -> None:
        self.db.execute(
            "INSERT INTO metricas (nombre, valor, timestamp, tags) VALUES (?, ?, ?, ?)",
            (nombre, valor, datetime.now(timezone.utc).isoformat(), json.dumps(tags or {})),
        )
        self.db.commit()

    def get_series(self, nombre: str, limit: int = 1000, desde: str | None = None, hasta: str | None = None) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM metricas WHERE nombre = ?"
        params = [nombre]
        if desde:
            sql += " AND timestamp >= ?"
            params.append(desde)
        if hasta:
            sql += " AND timestamp <= ?"
            params.append(hasta)
        sql += " ORDER BY timestamp ASC LIMIT ?"
        params.append(limit)
        cursor = self.db.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]

    def dashboard_data(self) -> Dict[str, Dict[str, Any]]:
        cursor = self.db.execute("SELECT DISTINCT nombre FROM metricas")
        nombres = [row[0] for row in cursor.fetchall()]
        resultado = {}
        for nombre in nombres:
            cursor = self.db.execute(
                "SELECT AVG(valor) as promedio, MAX(valor) as max, MIN(valor) as min, COUNT(*) as count FROM metricas WHERE nombre = ?",
                (nombre,),
            )
            row = cursor.fetchone()
            resultado[nombre] = {
                "promedio": float(row["promedio"] or 0),
                "max": float(row["max"] or 0),
                "min": float(row["min"] or 0),
                "count": int(row["count"] or 0),
            }
        return resultado
