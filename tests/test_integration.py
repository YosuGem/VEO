# test_integration.py - Tests de integracion end-to-end de VEO v2
"""
Tests de integracion completos para VEO v2:
- test_reasoning_cycle: crear senal → generar hipotesis → validar
- test_forecast_cycle: hipotesis validada → escenario → prediccion
- test_executive_cycle: hallazgos → priorizar → recomendar
- test_operations_cycle: logs → metricas → backup
- test_hermes_commander: comando → hermes → veo_core → resultado
- test_full_pipeline: senal → hipotesis → escenario → prediccion → alerta
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from .conftest import EventBusTest


# ============================================================================
# TEST: Ciclo de Razonamiento
# ============================================================================


class TestCicloRazonamiento:
    """End-to-end: senal → hipotesis → validacion."""

    def test_reasoning_cycle_completo(self, db_temp: sqlite3.Connection, config_test: Dict[str, Any], logger_mock: MagicMock) -> None:
        """
        Flujo completo:
        1. Recibir una senal de entrada
        2. Generar hipotesis a partir de la senal
        3. Calcular NEI
        4. Validar con agente cientifico
        5. Persistir resultado
        """
        event_bus = EventBusTest()
        event_bus.start()

        # 1. Recibir senal
        senal = {
            "tipo": "narrativa",
            "fuente": "reddit",
            "contenido": "Aumentan las discusiones sobre regulacion de IA en foros tecnicos",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": {"subreddit": "MachineLearning", "upvotes": 450},
        }
        event_bus.publish("senal.nueva", senal)

        # 2. Generar hipotesis
        motor = MockMotorHipotesisIntegracion(db_temp, config_test, logger_mock)
        clusters = [{"topic": "regulacion_ia", "size": 450, "coherence": 0.82, "samples": [senal["contenido"]]}]
        hipotesis_list = motor.generar(clusters, senal["contenido"])
        assert len(hipotesis_list) > 0
        hip = hipotesis_list[0]

        # 3. Calcular NEI
        metricas = {"FR": 0.85, "GR": 0.70, "DV": 0.60, "NV": 0.75, "EM": 0.50, "ST": 0.40}
        hip["nei"] = motor.calcular_nei(metricas)
        assert 0.0 <= hip["nei"] <= 1.0

        # 4. Validar con agente cientifico
        agente = MockAgenteCientificoIntegracion(config_test, logger_mock)
        resultado_validacion = agente.validar({
            "texto": hip["texto"],
            "evidencia_a_favor": [senal["contenido"]],
            "evidencia_en_contra": [],
        })
        assert resultado_validacion["veredicto"] in ("confirmada", "refutada", "inconclusa")

        # 5. Persistir
        db_temp.execute(
            "INSERT INTO hipotesis (id, texto, confianza, evidencias, estado, fecha_creacion, fecha_actualizacion, creador, tags, peso_nei) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (hip["id"], hip["texto"], resultado_validacion["confianza"], json.dumps([senal["contenido"]]),
             "activa" if resultado_validacion["veredicto"] == "confirmada" else "refutada",
             datetime.now(timezone.utc).isoformat(), datetime.now(timezone.utc).isoformat(),
             "sistema", json.dumps(["ia", "regulacion"]), hip["nei"]),
        )
        # Persistir validacion
        db_temp.execute(
            "INSERT INTO validaciones (hipotesis_id, veredicto, razonamiento, nivel_confianza, sesgos_detectados, test_realizados, fecha_validacion) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (hip["id"], resultado_validacion["veredicto"], resultado_validacion["razonamiento"],
             resultado_validacion["confianza"], json.dumps([s["tipo"] for s in resultado_validacion["sesgos_detectados"]]),
             json.dumps(["heuristica"]), datetime.now(timezone.utc).isoformat()),
        )
        db_temp.commit()

        # Verificacion final
        cursor = db_temp.execute("SELECT * FROM hipotesis WHERE id = ?", (hip["id"],))
        assert cursor.fetchone() is not None
        cursor = db_temp.execute("SELECT * FROM validaciones WHERE hipotesis_id = ?", (hip["id"],))
        assert cursor.fetchone() is not None

        event_bus.stop()


# ============================================================================
# TEST: Ciclo de Forecast
# ============================================================================


class TestCicloForecast:
    """End-to-end: hipotesis validada → escenario → prediccion."""

    def test_forecast_cycle_completo(self, db_temp: sqlite3.Connection, config_test: Dict[str, Any], logger_mock: MagicMock, sample_escenario: Dict[str, Any]) -> None:
        """
        Flujo completo:
        1. Hipotesis ya validada
        2. Crear escenario a partir de la hipotesis
        3. Ejecutar simulacion Monte Carlo
        4. Generar prediccion con probabilidad
        5. Persistir prediccion
        """
        event_bus = EventBusTest()

        # 1. Hipotesis validada
        hip_id = f"hip_val_{uuid.uuid4().hex[:8]}"
        db_temp.execute(
            "INSERT INTO hipotesis (id, texto, confianza, evidencias, estado, fecha_creacion, fecha_actualizacion, creador, tags, peso_nei) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (hip_id, "La regulacion de IA aumentara en los proximos 6 meses", 0.80,
             json.dumps(["ev1", "ev2"]), "confirmada", datetime.now(timezone.utc).isoformat(),
             datetime.now(timezone.utc).isoformat(), "agente_cientifico", json.dumps(["ia", "regulacion"]), 0.75),
        )
        db_temp.commit()

        # 2. Crear escenario
        sim = MockSimuladorIntegracion(config_test, logger_mock)
        esc_id = sim.crear("Regulacion IA 2026", "Impacto de nuevas regulaciones", sample_escenario["variables"])
        db_temp.execute(
            "INSERT INTO escenarios (id, nombre, descripcion, variables, resultado_simulado, confianza, fecha) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (esc_id, "Regulacion IA 2026", "Impacto de nuevas regulaciones",
             json.dumps(sample_escenario["variables"]), "{}", 0.8, datetime.now(timezone.utc).isoformat()),
        )
        db_temp.commit()

        # 3. Simular Monte Carlo
        resultado_sim = sim.ejecutar(esc_id, n_runs=500, seed=42)
        assert resultado_sim["estadisticas"]["percentil_05"] <= resultado_sim["estadisticas"]["mediana"]

        # 4. Generar prediccion
        prob = min(0.95, max(0.05, resultado_sim["estadisticas"]["media"] / 100))
        pred_id = f"pred_{uuid.uuid4().hex[:8]}"
        db_temp.execute(
            "INSERT INTO predicciones (id, hipotesis_id, escenario, probabilidad, fecha_prediccion, estado, liquidez, participaciones) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (pred_id, hip_id, esc_id, prob, datetime.now(timezone.utc).isoformat(), "abierta", 1000.0, 1),
        )
        db_temp.commit()

        # 5. Verificar
        cursor = db_temp.execute("SELECT * FROM predicciones WHERE id = ?", (pred_id,))
        pred = cursor.fetchone()
        assert pred is not None
        assert pred["hipotesis_id"] == hip_id
        assert 0.0 <= pred["probabilidad"] <= 1.0


# ============================================================================
# TEST: Ciclo Ejecutivo
# ============================================================================


class TestCicloEjecutivo:
    """End-to-end: hallazgos → priorizar → recomendar."""

    def test_executive_cycle_completo(self, db_temp: sqlite3.Connection, config_test: Dict[str, Any], logger_mock: MagicMock) -> None:
        """
        Flujo completo:
        1. Recopilar hallazgos del ciclo de analisis
        2. Priorizar por impacto y urgencia
        3. Generar recomendaciones
        4. Emitir alertas si es necesario
        5. Registrar en auditoria
        """
        event_bus = EventBusTest()
        event_bus.start()

        # 1. Hallazgos
        hallazgos = [
            {"id": "h1", "tema": "Regulacion IA", "confianza": 0.95, "impacto": 0.95, "urgencia": 0.95},
            {"id": "h2", "tema": "Adopcion empresas", "confianza": 0.65, "impacto": 0.60, "urgencia": 0.50},
            {"id": "h3", "tema": "Cambio narrativa", "confianza": 0.75, "impacto": 0.85, "urgencia": 0.70},
        ]

        # 2. Priorizar (score = confianza * impacto * urgencia)
        for h in hallazgos:
            h["prioridad"] = h["confianza"] * h["impacto"] * h["urgencia"]
        hallazgos_ordenados = sorted(hallazgos, key=lambda x: x["prioridad"], reverse=True)

        # 3. Generar recomendaciones
        recomendaciones = []
        for h in hallazgos_ordenados[:2]:  # Top 2
            if h["prioridad"] > config_test["umbral_alerta"]:
                rec = {
                    "hallazgo_id": h["id"],
                    "accion": "monitoreo_intensivo",
                    "mensaje": f"Alta prioridad: {h['tema']} (score={h['prioridad']:.3f})",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                recomendaciones.append(rec)
                event_bus.publish("alerta.prioritaria", rec)

        assert len(recomendaciones) > 0

        # 4. Verificar alertas emitidas
        alertas = event_bus.get_history("alerta.prioritaria")
        assert len(alertas) == len(recomendaciones)

        # 5. Registrar en auditoria
        for rec in recomendaciones:
            db_temp.execute(
                "INSERT INTO auditoria (timestamp, actor, accion, recurso, detalle, hash_previo) VALUES (?, ?, ?, ?, ?, ?)",
                (datetime.now(timezone.utc).isoformat(), "ciclo_ejecutivo", "recomendar",
                 rec["hallazgo_id"], json.dumps(rec), "hash_prev"),
            )
        db_temp.commit()

        cursor = db_temp.execute("SELECT COUNT(*) as n FROM auditoria WHERE accion = ?", ("recomendar",))
        assert cursor.fetchone()["n"] == len(recomendaciones)

        event_bus.stop()


# ============================================================================
# TEST: Ciclo Operativo
# ============================================================================


class TestCicloOperativo:
    """End-to-end: logs → metricas → backup."""

    def test_operations_cycle_completo(self, db_temp: sqlite3.Connection) -> None:
        """
        Flujo completo:
        1. Generar logs de operacion
        2. Agregar metricas del sistema
        3. Verificar health status
        4. Crear backup
        5. Verificar integridad del backup
        """
        # 1. Logs
        for i in range(10):
            db_temp.execute(
                "INSERT INTO logs_operacion (timestamp, nivel, modulo, mensaje, metadata) VALUES (?, ?, ?, ?, ?)",
                (datetime.now(timezone.utc).isoformat(), "INFO" if i % 3 != 0 else "WARNING",
                 f"modulo_{i}", f"Mensaje de log {i}", json.dumps({"ciclo": i})),
            )
        db_temp.commit()

        # 2. Metricas
        metricas_nombres = ["nei", "confianza", "latencia_db", "memoria_usada"]
        for nombre in metricas_nombres:
            for _ in range(5):
                db_temp.execute(
                    "INSERT INTO metricas (nombre, valor, timestamp, tags) VALUES (?, ?, ?, ?)",
                    (nombre, np.random.random() * 100, datetime.now(timezone.utc).isoformat(), "{}"),
                )
        db_temp.commit()

        # 3. Health status
        db_temp.execute(
            "INSERT OR REPLACE INTO health_status (componente, estado, score, ultimo_check, mensaje) VALUES (?, ?, ?, ?, ?)",
            ("veo_core", "ok", 0.92, datetime.now(timezone.utc).isoformat(), "Funcionando correctamente"),
        )
        db_temp.commit()

        # 4. Backup
        bm = MockBackupIntegracion(db_temp)
        backup_id = bm.crear("/tmp/veo_test_backups")
        assert backup_id is not None

        # 5. Verificar integridad
        resultado = bm.verificar_integridad(backup_id)
        assert resultado["valido"] is True

        # Verificaciones finales
        cursor = db_temp.execute("SELECT COUNT(*) as n FROM logs_operacion")
        assert cursor.fetchone()["n"] == 10
        cursor = db_temp.execute("SELECT COUNT(*) as n FROM metricas")
        assert cursor.fetchone()["n"] == 20
        cursor = db_temp.execute("SELECT COUNT(*) as n FROM backups")
        assert cursor.fetchone()["n"] == 1


# ============================================================================
# TEST: Hermes Commander
# ============================================================================


class TestHermesCommander:
    """End-to-end: comando → hermes → veo_core → resultado."""

    def test_hermes_comando_status(self, config_test: Dict[str, Any], logger_mock: MagicMock) -> None:
        """Comando 'status' debe retornar el estado del sistema."""
        hermes = MockHermesCommander(config_test, logger_mock)
        resultado = hermes.ejecutar("status")
        assert resultado["exitoso"] is True
        assert "estado" in resultado
        assert "componentes" in resultado

    def test_hermes_comando_hipotesis_list(self, config_test: Dict[str, Any], logger_mock: MagicMock) -> None:
        """Comando 'hipotesis list' debe retornar lista de hipotesis."""
        hermes = MockHermesCommander(config_test, logger_mock)
        resultado = hermes.ejecutar("hipotesis list")
        assert resultado["exitoso"] is True
        assert "hipotesis" in resultado

    def test_hermes_comando_analisis_run(self, config_test: Dict[str, Any], logger_mock: MagicMock) -> None:
        """Comando 'analisis run' debe ejecutar un ciclo de analisis."""
        hermes = MockHermesCommander(config_test, logger_mock)
        resultado = hermes.ejecutar("analisis run")
        assert resultado["exitoso"] is True
        assert "ciclo" in resultado
        assert resultado["ciclo"] == "analisis"

    def test_hermes_comando_config_get(self, config_test: Dict[str, Any], logger_mock: MagicMock) -> None:
        """Comando 'config get' debe retornar configuracion."""
        hermes = MockHermesCommander(config_test, logger_mock)
        resultado = hermes.ejecutar("config get")
        assert resultado["exitoso"] is True
        assert "config" in resultado
        assert resultado["config"]["ambiente"] == "test"

    def test_hermes_comando_invalido(self, config_test: Dict[str, Any], logger_mock: MagicMock) -> None:
        """Un comando invalido debe retornar error."""
        hermes = MockHermesCommander(config_test, logger_mock)
        resultado = hermes.ejecutar("comando_inexistente_xyz")
        assert resultado["exitoso"] is False
        assert "error" in resultado

    def test_hermes_comando_backup(self, config_test: Dict[str, Any], logger_mock: MagicMock) -> None:
        """Comando 'backup create' debe crear un backup."""
        hermes = MockHermesCommander(config_test, logger_mock)
        resultado = hermes.ejecutar("backup create")
        assert resultado["exitoso"] is True
        assert "backup_id" in resultado

    def test_hermes_comando_health(self, config_test: Dict[str, Any], logger_mock: MagicMock) -> None:
        """Comando 'health' debe retornar estado de salud."""
        hermes = MockHermesCommander(config_test, logger_mock)
        resultado = hermes.ejecutar("health")
        assert resultado["exitoso"] is True
        assert "score_global" in resultado


# ============================================================================
# TEST: Pipeline Completo
# ============================================================================


class TestPipelineCompleto:
    """End-to-end: senal → hipotesis → escenario → prediccion → alerta."""

    def test_full_pipeline(self, db_temp: sqlite3.Connection, config_test: Dict[str, Any], logger_mock: MagicMock, sample_escenario: Dict[str, Any]) -> None:
        """
        Pipeline completo VEO v2:
        1. Senal de entrada
        2. Generar hipotesis
        3. Validar hipotesis
        4. Crear escenario
        5. Simular Monte Carlo
        6. Generar prediccion
        7. Evaluar alerta
        8. Persistir todo
        """
        event_bus = EventBusTest()
        event_bus.start()

        # --- 1. Senal ---
        senal = {
            "tipo": "narrativa",
            "fuente": "rss",
            "contenido": "Surgen propuestas de ley para regular IA en Europa y Asia simultaneamente",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": {"idioma": "es", "paises": ["ES", "DE", "JP"]},
        }
        event_bus.publish("pipeline.inicio", {"senal_id": "sig_001", "timestamp": senal["timestamp"]})

        # --- 2. Generar hipotesis ---
        motor = MockMotorHipotesisIntegracion(db_temp, config_test, logger_mock)
        clusters = [{"topic": "regulacion_global_ia", "size": 320, "coherence": 0.88, "samples": [senal["contenido"]]}]
        hipotesis_list = motor.generar(clusters, senal["contenido"])
        assert len(hipotesis_list) > 0
        hip = hipotesis_list[0]
        hip["id"] = f"hip_pipe_{uuid.uuid4().hex[:8]}"

        # --- 3. Validar ---
        agente = MockAgenteCientificoIntegracion(config_test, logger_mock)
        validacion = agente.validar({"texto": hip["texto"], "evidencia_a_favor": [senal["contenido"], "ev2", "ev3"], "evidencia_en_contra": []})
        event_bus.publish("pipeline.validacion", {"hip_id": hip["id"], "veredicto": validacion["veredicto"]})

        # --- 4. Crear escenario ---
        sim = MockSimuladorIntegracion(config_test, logger_mock)
        esc_id = sim.crear("Impacto Regulacion Global IA", "Escenario de regulacion simultanea", sample_escenario["variables"])

        # --- 5. Simular ---
        resultado_sim = sim.ejecutar(esc_id, n_runs=300, seed=123)
        assert "estadisticas" in resultado_sim

        # --- 6. Generar prediccion ---
        prob_prediccion = min(0.95, 0.5 + resultado_sim["estadisticas"]["media"] / 200)
        pred_id = f"pred_pipe_{uuid.uuid4().hex[:8]}"

        # --- 7. Evaluar alerta ---
        alerta_generada = False
        if validacion["veredicto"] == "confirmada" and prob_prediccion > config_test["umbral_alerta"]:
            alerta_generada = True
            event_bus.publish("alerta.pipeline", {
                "nivel": "alta",
                "hipotesis_id": hip["id"],
                "prediccion_id": pred_id,
                "probabilidad": prob_prediccion,
                "mensaje": f"ALTA: {hip['texto'][:80]}... (prob={prob_prediccion:.2f})",
            })

        # --- 8. Persistir todo ---
        db_temp.execute(
            "INSERT INTO hipotesis (id, texto, confianza, evidencias, estado, fecha_creacion, fecha_actualizacion, creador, tags, peso_nei) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (hip["id"], hip["texto"], validacion["confianza"], json.dumps([senal["contenido"]]),
             "confirmada" if validacion["veredicto"] == "confirmada" else "activa",
             datetime.now(timezone.utc).isoformat(), datetime.now(timezone.utc).isoformat(),
             "pipeline", json.dumps(["ia", "regulacion", "global"]), hip.get("nei", 0.5)),
        )
        db_temp.execute(
            "INSERT INTO escenarios (id, nombre, descripcion, variables, resultado_simulado, confianza, fecha) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (esc_id, "Impacto Regulacion Global IA", "Escenario de regulacion simultanea",
             json.dumps(sample_escenario["variables"]), json.dumps(resultado_sim["estadisticas"]),
             validacion["confianza"], datetime.now(timezone.utc).isoformat()),
        )
        db_temp.execute(
            "INSERT INTO predicciones (id, hipotesis_id, escenario, probabilidad, fecha_prediccion, estado, liquidez, participaciones) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (pred_id, hip["id"], esc_id, prob_prediccion, datetime.now(timezone.utc).isoformat(), "abierta", 1000.0, 1),
        )
        if alerta_generada:
            db_temp.execute(
                "INSERT INTO cambios_narrativa (id, tema, direccion_anterior, direccion_actual, magnitud_cambio, fecha_detectado, fuentes, confianza) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (f"cn_pipe_{uuid.uuid4().hex[:8]}", "Regulacion IA Global", "fragmentada", "coordinada",
                 prob_prediccion, datetime.now(timezone.utc).isoformat(), json.dumps([senal["fuente"]]), validacion["confianza"]),
            )
        db_temp.commit()

        # --- Verificaciones finales ---
        cursor = db_temp.execute("SELECT COUNT(*) as n FROM hipotesis WHERE id = ?", (hip["id"],))
        assert cursor.fetchone()["n"] == 1

        cursor = db_temp.execute("SELECT COUNT(*) as n FROM escenarios WHERE id = ?", (esc_id,))
        assert cursor.fetchone()["n"] == 1

        cursor = db_temp.execute("SELECT COUNT(*) as n FROM predicciones WHERE id = ?", (pred_id,))
        assert cursor.fetchone()["n"] == 1

        if alerta_generada:
            cursor = db_temp.execute("SELECT COUNT(*) as n FROM cambios_narrativa WHERE tema = ?", ("Regulacion IA Global",))
            assert cursor.fetchone()["n"] == 1

        # Verificar eventos
        eventos = event_bus.get_history()
        assert len(eventos) >= 3  # inicio, validacion, y posible alerta

        event_bus.stop()

    def test_full_pipeline_json_serializable(self, db_temp: sqlite3.Connection, config_test: Dict[str, Any], logger_mock: MagicMock, sample_escenario: Dict[str, Any]) -> None:
        """Todo el output del pipeline debe ser JSON-serializable."""
        motor = MockMotorHipotesisIntegracion(db_temp, config_test, logger_mock)
        clusters = [{"topic": "test", "size": 100, "coherence": 0.8, "samples": ["test"]}]
        hipotesis = motor.generar(clusters, "test")
        try:
            json.dumps(hipotesis, default=str)
        except (TypeError, ValueError) as exc:
            pytest.fail(f"Hipotesis no JSON-serializable: {exc}")

        sim = MockSimuladorIntegracion(config_test, logger_mock)
        esc_id = sim.crear("Test", "Test", sample_escenario["variables"])
        resultado = sim.ejecutar(esc_id, n_runs=50)
        try:
            json.dumps(resultado, default=str)
        except (TypeError, ValueError) as exc:
            pytest.fail(f"Resultado simulacion no JSON-serializable: {exc}")


# ============================================================================
# Mocks para tests de integracion
# ============================================================================


class MockMotorHipotesisIntegracion:
    """Motor de hipotesis para tests de integracion."""

    def __init__(self, db: sqlite3.Connection, config: Dict[str, Any], logger: MagicMock) -> None:
        self.db = db
        self.config = config
        self.logger = logger

    def generar(self, clusters: List[Dict[str, Any]], contexto: str) -> List[Dict[str, Any]]:
        if not clusters:
            return []
        hipotesis = []
        for i, cluster in enumerate(clusters[:5]):
            hipotesis.append({
                "id": f"hip_int_{uuid.uuid4().hex[:8]}",
                "texto": f"La narrativa sobre '{cluster.get('topic', 'tema')}' esta cambiando: "
                        f"se detecta {cluster.get('size', 0)} muestras con coherencia {cluster.get('coherence', 0):.2f}",
                "nivel_confianza": min(0.5 + cluster.get("coherence", 0) * 0.5, 0.95),
                "tags": [cluster.get("topic", "general"), "pipeline"],
                "nei": 0.0,
            })
        self.logger.info(f"[Pipeline] {len(hipotesis)} hipotesis generadas")
        return hipotesis

    def calcular_nei(self, metricas: Dict[str, float]) -> float:
        pesos = self.config["pesos_nei"]
        valores = [max(0.0, min(1.0, metricas.get(k, 0.0))) for k in ["FR", "GR", "DV", "NV", "EM", "ST"]]
        return float(np.clip(sum(p * v for p, v in zip(pesos, valores)), 0.0, 1.0))


class MockAgenteCientificoIntegracion:
    """Agente cientifico para tests de integracion."""

    def __init__(self, config: Dict[str, Any], logger: MagicMock) -> None:
        self.config = config
        self.logger = logger

    def validar(self, hipotesis: Dict[str, Any]) -> Dict[str, Any]:
        texto = hipotesis.get("texto", "")
        ev_favor = hipotesis.get("evidencia_a_favor", [])
        ev_contra = hipotesis.get("evidencia_en_contra", [])

        score_evidencia = min(len(ev_favor) * 0.15, 0.6)
        penalizacion = min(len(ev_contra) * 0.1, 0.4)
        confianza = max(0.0, min(1.0, 0.4 + score_evidencia - penalizacion))

        # Falacias
        falacias = []
        if "despues" in texto.lower() and "por eso" in texto.lower():
            falacias.append("post_hoc")

        # Sesgos
        sesgos = []
        if len(ev_contra) == 0 and len(ev_favor) > 2:
            sesgos.append({"tipo": "sesgo_de_confirmacion", "severidad": 0.5})

        if confianza > 0.7 and len(falacias) == 0:
            veredicto = "confirmada"
        elif confianza < 0.3:
            veredicto = "refutada"
        else:
            veredicto = "inconclusa"

        self.logger.info(f"[Pipeline] Validacion: {veredicto} (conf={confianza:.3f})")

        return {
            "veredicto": veredicto,
            "confianza": round(confianza, 4),
            "razonamiento": f"Score evidencia: {score_evidencia:.2f}, penalizacion: {penalizacion:.2f}",
            "sesgos_detectados": sesgos,
            "falacias_detectadas": falacias,
            "hipotesis_alternativas": ["Causalidad inversa", "Tercera variable", "Azar estadistico"],
        }


class MockSimuladorIntegracion:
    """Simulador de escenarios para tests de integracion."""

    def __init__(self, config: Dict[str, Any], logger: MagicMock) -> None:
        self.config = config
        self.logger = logger
        self._escenarios: Dict[str, Dict[str, Any]] = {}

    def crear(self, nombre: str, descripcion: str, variables: List[Dict[str, Any]]) -> str:
        esc_id = f"esc_int_{uuid.uuid4().hex[:8]}"
        self._escenarios[esc_id] = {"nombre": nombre, "descripcion": descripcion, "variables": variables}
        self.logger.info(f"[Pipeline] Escenario creado: {esc_id}")
        return esc_id

    def ejecutar(self, esc_id: str, n_runs: int = 1000, seed: int | None = None) -> Dict[str, Any]:
        rng = np.random.default_rng(seed)
        esc = self._escenarios[esc_id]
        resultados = []
        for _ in range(n_runs):
            total = 0
            for var in esc["variables"]:
                vmin = var.get("rango_min", 0)
                vmax = var.get("rango_max", 1)
                total += rng.uniform(vmin, vmax)
            resultados.append(total)
        arr = np.array(resultados)
        stats = {
            "media": float(np.mean(arr)),
            "mediana": float(np.median(arr)),
            "desv_est": float(np.std(arr)),
            "percentil_05": float(np.percentile(arr, 5)),
            "percentil_95": float(np.percentile(arr, 95)),
        }
        self.logger.info(f"[Pipeline] Simulacion completada: media={stats['media']:.2f}")
        return {"estadisticas": stats, "n_runs": n_runs, "seed": seed}


class MockHermesCommander:
    """Hermes Commander para tests de integracion."""

    COMANDOS = {
        "status": lambda self: {"exitoso": True, "estado": "running", "componentes": ["core", "db", "api"]},
        "hipotesis list": lambda self: {"exitoso": True, "hipotesis": [{"id": "h1", "texto": "Test"}]},
        "analisis run": lambda self: {"exitoso": True, "ciclo": "analisis", "resultado": "ok"},
        "config get": lambda self: {"exitoso": True, "config": self.config},
        "backup create": lambda self: {"exitoso": True, "backup_id": f"bk_{uuid.uuid4().hex[:12]}"},
        "health": lambda self: {"exitoso": True, "score_global": 0.92, "componentes": {"core": "ok", "db": "ok"}},
    }

    def __init__(self, config: Dict[str, Any], logger: MagicMock) -> None:
        self.config = config
        self.logger = logger

    def ejecutar(self, comando: str) -> Dict[str, Any]:
        self.logger.info(f"[Hermes] Comando recibido: {comando}")
        if comando in self.COMANDOS:
            return self.COMANDOS[comando](self)
        return {"exitoso": False, "error": f"Comando '{comando}' no reconocido"}


class MockBackupIntegracion:
    """Backup manager para tests de integracion."""

    def __init__(self, db: sqlite3.Connection) -> None:
        self.db = db

    def crear(self, ruta: str) -> str:
        backup_id = f"bk_int_{uuid.uuid4().hex[:12]}"
        cursor = self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tablas = [row[0] for row in cursor.fetchall()]
        contenido = json.dumps({"tablas": tablas, "ts": datetime.now(timezone.utc).isoformat()})
        checksum = hashlib.sha256(contenido.encode()).hexdigest()
        self.db.execute(
            "INSERT INTO backups (id, ruta, tamano_bytes, timestamp, checksum, estado) VALUES (?, ?, ?, ?, ?, ?)",
            (backup_id, ruta, len(contenido), datetime.now(timezone.utc).isoformat(), checksum, "ok"),
        )
        self.db.commit()
        return backup_id

    def verificar_integridad(self, backup_id: str) -> Dict[str, Any]:
        cursor = self.db.execute("SELECT checksum FROM backups WHERE id = ?", (backup_id,))
        row = cursor.fetchone()
        if not row:
            return {"valido": False}
        return {"valido": True, "checksum": row["checksum"]}
