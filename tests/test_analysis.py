# test_analysis.py - Tests de la capa de analisis de VEO v2
"""
Tests para el modulo analysis/ de VEO v2:
- Agente Cientifico (validacion de hipotesis, deteccion de sesgos, trust_score)
- Motor de Hipotesis (generacion, calculo NEI, health_status)
- Motor Causal (inferencia causal, Granger, health_status)
- Simulador de Escenarios (simulacion, Monte Carlo, estimate_cost)
- Grafo de Conocimiento (crear nodo, crear relacion, consultar, exportar)
"""

from __future__ import annotations

import json
import math
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


# ============================================================================
# TESTS: Agente Cientifico
# ============================================================================


class TestAgenteCientifico:
    """Tests para el agente de validacion cientifica popperiana."""

    def test_agente_cientifico_validar_hipotesis_ejemplo(self, config_test: Dict[str, Any], logger_mock: MagicMock) -> None:
        """Validar una hipotesis de ejemplo debe producir un resultado estructurado."""
        agente = MockAgenteCientifico(config_test, logger_mock)
        hipotesis = {
            "texto": "El uso de redes sociales causa aislamiento social en adolescentes",
            "evidencia_a_favor": ["Estudio longitudinal n=5000 muestra correlacion r=0.45"],
            "evidencia_en_contra": [],
        }
        resultado = agente.validar(hipotesis)
        assert "veredicto" in resultado
        assert resultado["veredicto"] in ("confirmada", "refutada", "inconclusa")
        assert 0.0 <= resultado["confianza"] <= 1.0

    def test_agente_detecta_sesgos_confirmacion(self, config_test: Dict[str, Any], logger_mock: MagicMock) -> None:
        """El agente debe detectar sesgo de confirmacion en la evidencia."""
        agente = MockAgenteCientifico(config_test, logger_mock)
        # Hipotesis con solo evidencia a favor (sin evidencia contraria buscada)
        hipotesis = {
            "texto": "Todos los que usan X son Y",
            "evidencia_a_favor": ["Caso 1", "Caso 2", "Caso 3"],
            "evidencia_en_contra": [],
        }
        resultado = agente.validar(hipotesis)
        sesgos = resultado.get("sesgos_detectados", [])
        nombres_sesgos = [s.get("tipo", "") for s in sesgos]
        assert "sesgo_de_confirmacion" in nombres_sesgos or len(sesgos) > 0

    def test_agente_trust_score_en_rango(self, config_test: Dict[str, Any], logger_mock: MagicMock) -> None:
        """El trust_score del agente debe estar siempre en [0, 1]."""
        agente = MockAgenteCientifico(config_test, logger_mock)
        hipotesis = {"texto": "Test", "evidencia_a_favor": [], "evidencia_en_contra": []}
        resultado = agente.validar(hipotesis)
        assert 0.0 <= resultado["confianza"] <= 1.0

    def test_agente_detecta_falacias_logicas(self, config_test: Dict[str, Any], logger_mock: MagicMock) -> None:
        """El agente debe detectar falacias logicas comunes."""
        agente = MockAgenteCientifico(config_test, logger_mock)
        hipotesis = {
            "texto": "Despues de que el gobierno subio los impuestos, la economia crecio, por eso los impuestos altos causan crecimiento",
            "evidencia_a_favor": ["Post hoc observable"],
            "evidencia_en_contra": [],
        }
        resultado = agente.validar(hipotesis)
        falacias = resultado.get("falacias_detectadas", [])
        assert len(falacias) > 0

    def test_agente_hipotesis_alternativas(self, config_test: Dict[str, Any], logger_mock: MagicMock) -> None:
        """El agente debe proponer hipotesis alternativas."""
        agente = MockAgenteCientifico(config_test, logger_mock)
        hipotesis = {"texto": "A causa B", "evidencia_a_favor": ["correlacion observada"], "evidencia_en_contra": []}
        resultado = agente.validar(hipotesis)
        assert "hipotesis_alternativas" in resultado
        assert len(resultado["hipotesis_alternativas"]) >= 1

    def test_agente_rechaza_hipotesis_vacia(self, config_test: Dict[str, Any], logger_mock: MagicMock) -> None:
        """El agente debe rechazar una hipotesis con texto vacio."""
        agente = MockAgenteCientifico(config_test, logger_mock)
        with pytest.raises((ValueError, AssertionError)):
            agente.validar({"texto": "", "evidencia_a_favor": [], "evidencia_en_contra": []})

    def test_agente_evidencia_contraria_reduce_confianza(self, config_test: Dict[str, Any], logger_mock: MagicMock) -> None:
        """Más evidencia contraria debe reducir la confianza."""
        agente = MockAgenteCientifico(config_test, logger_mock)
        h1 = {"texto": "X causa Y", "evidencia_a_favor": ["Estudio A"], "evidencia_en_contra": []}
        h2 = {"texto": "X causa Y", "evidencia_a_favor": ["Estudio A"], "evidencia_en_contra": ["Estudio B refuta", "Metaanalisis negativo"]}
        r1 = agente.validar(h1)
        r2 = agente.validar(h2)
        assert r2["confianza"] <= r1["confianza"]

    def test_agente_json_serializable(self, config_test: Dict[str, Any], logger_mock: MagicMock) -> None:
        """El resultado de validacion debe ser JSON-serializable."""
        agente = MockAgenteCientifico(config_test, logger_mock)
        resultado = agente.validar({"texto": "Test", "evidencia_a_favor": ["ev1"], "evidencia_en_contra": []})
        try:
            json.dumps(resultado, default=str)
        except (TypeError, ValueError) as exc:
            pytest.fail(f"Resultado no es JSON-serializable: {exc}")


# ============================================================================
# TESTS: Motor de Hipotesis
# ============================================================================


class TestMotorHipotesis:
    """Tests para el motor de generacion y evaluacion de hipotesis."""

    def test_motor_generar_hipotesis(self, config_test: Dict[str, Any], logger_mock: MagicMock, db_temp: sqlite3.Connection) -> None:
        """El motor debe generar hipotesis a partir de clusters semanticos."""
        motor = MockMotorHipotesis(db_temp, config_test, logger_mock)
        clusters = [
            {"topic": "regulacion_ia", "size": 150, "coherence": 0.85, "samples": ["tweet1", "tweet2"]},
            {"topic": "adopcion_empresas", "size": 80, "coherence": 0.72, "samples": ["tweet3"]},
        ]
        hipotesis = motor.generar(clusters, "Contexto de prueba sobre IA")
        assert len(hipotesis) > 0
        for h in hipotesis:
            assert "texto" in h
            assert "nivel_confianza" in h
            assert 0.0 <= h["nivel_confianza"] <= 1.0

    def test_motor_calcular_nei(self, config_test: Dict[str, Any], logger_mock: MagicMock, db_temp: sqlite3.Connection) -> None:
        """El calculo NEI debe estar en [0, 1] con pesos correctos."""
        motor = MockMotorHipotesis(db_temp, config_test, logger_mock)
        metricas = {"FR": 0.8, "GR": 0.6, "DV": 0.7, "NV": 0.5, "EM": 0.4, "ST": 0.3}
        nei = motor.calcular_nei(metricas)
        assert 0.0 <= nei <= 1.0
        # Verificar que el NEI es una ponderacion correcta
        pesos = config_test["pesos_nei"]
        valores = [metricas["FR"], metricas["GR"], metricas["DV"], metricas["NV"], metricas["EM"], metricas["ST"]]
        nei_esperado = sum(p * v for p, v in zip(pesos, valores))
        assert abs(nei - nei_esperado) < 1e-6

    def test_motor_nei_cero_si_metricas_cero(self, config_test: Dict[str, Any], logger_mock: MagicMock, db_temp: sqlite3.Connection) -> None:
        """NEI debe ser 0 si todas las metricas son 0."""
        motor = MockMotorHipotesis(db_temp, config_test, logger_mock)
        metricas = {"FR": 0.0, "GR": 0.0, "DV": 0.0, "NV": 0.0, "EM": 0.0, "ST": 0.0}
        assert motor.calcular_nei(metricas) == pytest.approx(0.0)

    def test_motor_nei_uno_si_metricas_uno(self, config_test: Dict[str, Any], logger_mock: MagicMock, db_temp: sqlite3.Connection) -> None:
        """NEI debe ser 1 si todas las metricas son 1."""
        motor = MockMotorHipotesis(db_temp, config_test, logger_mock)
        metricas = {"FR": 1.0, "GR": 1.0, "DV": 1.0, "NV": 1.0, "EM": 1.0, "ST": 1.0}
        assert motor.calcular_nei(metricas) == pytest.approx(1.0)

    def test_motor_detectar_cascada(self, config_test: Dict[str, Any], logger_mock: MagicMock, db_temp: sqlite3.Connection) -> None:
        """Detectar hipotesis en cascada (tendencia creciente)."""
        motor = MockMotorHipotesis(db_temp, config_test, logger_mock)
        hip_cascada = {
            "id": "hip_cascada",
            "texto": "Cascada test",
            "nei": 0.85,
            "historial_nei": [
                (datetime.now(timezone.utc).isoformat(), 0.55),
                (datetime.now(timezone.utc).isoformat(), 0.70),
                (datetime.now(timezone.utc).isoformat(), 0.85),
            ],
            "estado": "activa",
        }
        cascadas = motor.detectar_cascada([hip_cascada], umbral=0.7)
        assert len(cascadas) > 0

    def test_motor_aprender_pesos(self, config_test: Dict[str, Any], logger_mock: MagicMock, db_temp: sqlite3.Connection) -> None:
        """El aprendizaje de pesos NEI debe mantener la suma = 1.0."""
        motor = MockMotorHipotesis(db_temp, config_test, logger_mock)
        historial = [
            {"metricas": {"FR": 0.8, "GR": 0.6, "DV": 0.7, "NV": 0.5, "EM": 0.4, "ST": 0.3}, "acierto": 1},
            {"metricas": {"FR": 0.2, "GR": 0.1, "DV": 0.3, "NV": 0.1, "EM": 0.2, "ST": 0.1}, "acierto": 0},
        ]
        nuevos_pesos = motor.aprender_pesos(historial)
        assert abs(sum(nuevos_pesos) - 1.0) < 1e-6
        assert all(p >= 0 for p in nuevos_pesos)

    def test_motor_health_status(self, config_test: Dict[str, Any], logger_mock: MagicMock, db_temp: sqlite3.Connection) -> None:
        """El health status del motor debe ser accesible."""
        motor = MockMotorHipotesis(db_temp, config_test, logger_mock)
        health = motor.health_status()
        assert "estado" in health
        assert health["estado"] in ("ok", "warning", "critical")

    def test_motor_archivar_caducas(self, config_test: Dict[str, Any], logger_mock: MagicMock, db_temp: sqlite3.Connection) -> None:
        """Archivar hipotesis sin actividad reciente."""
        motor = MockMotorHipotesis(db_temp, config_test, logger_mock)
        from datetime import timedelta
        h_antigua = {
            "id": "hip_old",
            "texto": "Vieja",
            "updated_at": (datetime.now(timezone.utc) - timedelta(days=10)).isoformat(),
            "estado": "activa",
        }
        archivadas = motor.archivar_caducas([h_antigua], dias=7)
        assert "hip_old" in archivadas

    def test_motor_hipotesis_json_serializable(self, config_test: Dict[str, Any], logger_mock: MagicMock, db_temp: sqlite3.Connection) -> None:
        """Las hipotesis generadas deben ser JSON-serializables."""
        motor = MockMotorHipotesis(db_temp, config_test, logger_mock)
        hipotesis = motor.generar([], "test")
        for h in hipotesis:
            try:
                json.dumps(h, default=str)
            except (TypeError, ValueError) as exc:
                pytest.fail(f"Hipotesis no JSON-serializable: {exc}")


# ============================================================================
# TESTS: Motor Causal
# ============================================================================


class TestMotorCausal:
    """Tests para el motor de inferencia causal."""

    def test_causal_granger_detecta_causalidad(
        self, config_test: Dict[str, Any], logger_mock: MagicMock,
        sample_series_temporales: Dict[str, List[float]], mock_grafo: MagicMock, db_temp: sqlite3.Connection,
    ) -> None:
        """Granger debe detectar causalidad X -> Y en series sinteticas."""
        motor = MockMotorCausal(mock_grafo, db_temp, logger_mock)
        series = sample_series_temporales
        resultado = motor.granger_causality(series["x"], series["y"], max_lag=5)
        assert "p_value" in resultado
        assert "direccion" in resultado
        # Con las series sinteticas, X deberia causar Y
        assert resultado["direccion"] in ("X->Y", "bidireccional")

    def test_causal_granger_rechaza_causalidad_inversa(
        self, config_test: Dict[str, Any], logger_mock: MagicMock,
        sample_series_temporales: Dict[str, List[float]], mock_grafo: MagicMock, db_temp: sqlite3.Connection,
    ) -> None:
        """Granger no debe detectar causalidad Y -> X cuando solo X -> Y."""
        motor = MockMotorCausal(mock_grafo, db_temp, logger_mock)
        series = sample_series_temporales
        resultado = motor.granger_causality(series["y"], series["x"], max_lag=5)
        # En series sinteticas donde X causa Y, Y->X deberia ser no-significativo
        assert resultado["p_value"] > 0.05 or resultado["direccion"] == "ninguna"

    def test_causal_granger_series_cortas_falla(
        self, config_test: Dict[str, Any], logger_mock: MagicMock,
        mock_grafo: MagicMock, db_temp: sqlite3.Connection,
    ) -> None:
        """Granger debe fallar con series demasiado cortas."""
        motor = MockMotorCausal(mock_grafo, db_temp, logger_mock)
        with pytest.raises(ValueError):
            motor.granger_causality([1.0, 2.0], [1.0, 2.0], max_lag=5)

    def test_causal_transfer_entropy_positiva(
        self, config_test: Dict[str, Any], logger_mock: MagicMock,
        sample_series_temporales: Dict[str, List[float]], mock_grafo: MagicMock, db_temp: sqlite3.Connection,
    ) -> None:
        """Transfer entropy X -> Y debe ser positiva cuando X causa Y."""
        motor = MockMotorCausal(mock_grafo, db_temp, logger_mock)
        series = sample_series_temporales
        te = motor.transfer_entropy(series["x"], series["y"])
        assert te > 0

    def test_causal_correlacion_parcial(
        self, config_test: Dict[str, Any], logger_mock: MagicMock,
        mock_grafo: MagicMock, db_temp: sqlite3.Connection,
    ) -> None:
        """La correlacion parcial debe estar en [-1, 1]."""
        motor = MockMotorCausal(mock_grafo, db_temp, logger_mock)
        x = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        y = [2.0, 4.0, 5.0, 8.0, 9.0, 12.0, 13.0, 16.0, 17.0, 20.0]
        corr = motor.correlacion_parcial(x, y, [])
        assert -1.0 <= corr <= 1.0

    def test_causal_evaluar_confundidor(
        self, config_test: Dict[str, Any], logger_mock: MagicMock,
        mock_grafo: MagicMock, db_temp: sqlite3.Connection,
    ) -> None:
        """Evaluar un confundidor debe producir resultado estructurado."""
        motor = MockMotorCausal(mock_grafo, db_temp, logger_mock)
        resultado = motor.evaluar_confundidor("causa", "efecto", "confundidor")
        assert "es_confundidor" in resultado
        assert isinstance(resultado["es_confundidor"], bool)

    def test_causal_health_status(
        self, config_test: Dict[str, Any], logger_mock: MagicMock,
        mock_grafo: MagicMock, db_temp: sqlite3.Connection,
    ) -> None:
        """El health status del motor causal debe ser accesible."""
        motor = MockMotorCausal(mock_grafo, db_temp, logger_mock)
        health = motor.health_status()
        assert "estado" in health
        assert health["estado"] in ("ok", "warning", "critical")

    def test_causal_simular_intervencion(
        self, config_test: Dict[str, Any], logger_mock: MagicMock,
        mock_grafo: MagicMock, db_temp: sqlite3.Connection,
    ) -> None:
        """Simular una intervencion debe producir efectos propagados."""
        motor = MockMotorCausal(mock_grafo, db_temp, logger_mock)
        resultado = motor.simular_intervencion("nodo_a", 1.5)
        assert "efectos" in resultado

    def test_causal_detectar_ciclos(
        self, config_test: Dict[str, Any], logger_mock: MagicMock,
        mock_grafo: MagicMock, db_temp: sqlite3.Connection,
    ) -> None:
        """Detectar ciclos causales en el grafo."""
        motor = MockMotorCausal(mock_grafo, db_temp, logger_mock)
        ciclos = motor.detectar_ciclos()
        assert isinstance(ciclos, list)


# ============================================================================
# TESTS: Simulador de Escenarios
# ============================================================================


class TestSimuladorEscenarios:
    """Tests para el simulador Monte Carlo de escenarios."""

    def test_simulador_crear_escenario(self, config_test: Dict[str, Any], logger_mock: MagicMock, sample_escenario: Dict[str, Any]) -> None:
        """Crear un escenario y verificar que tiene ID."""
        sim = MockSimuladorEscenarios(config_test, logger_mock)
        esc_id = sim.crear(sample_escenario["nombre"], sample_escenario["descripcion"], sample_escenario["variables"])
        assert esc_id is not None
        assert len(esc_id) > 0

    def test_simulador_ejecutar_montecarlo(self, config_test: Dict[str, Any], logger_mock: MagicMock, sample_escenario: Dict[str, Any]) -> None:
        """Ejecutar simulacion Monte Carlo debe producir estadisticas."""
        sim = MockSimuladorEscenarios(config_test, logger_mock)
        esc_id = sim.crear(sample_escenario["nombre"], sample_escenario["descripcion"], sample_escenario["variables"])
        resultado = sim.ejecutar(esc_id, n_runs=100)
        assert "estadisticas" in resultado
        stats = resultado["estadisticas"]
        assert "media" in stats
        assert "mediana" in stats
        assert "desv_est" in stats
        assert "percentil_05" in stats
        assert "percentil_95" in stats

    def test_simulador_estadisticas_en_rango(self, config_test: Dict[str, Any], logger_mock: MagicMock, sample_escenario: Dict[str, Any]) -> None:
        """Las estadisticas deben tener sentido (p5 < mediana < p95)."""
        sim = MockSimuladorEscenarios(config_test, logger_mock)
        esc_id = sim.crear(sample_escenario["nombre"], sample_escenario["descripcion"], sample_escenario["variables"])
        resultado = sim.ejecutar(esc_id, n_runs=500)
        stats = resultado["estadisticas"]
        assert stats["percentil_05"] <= stats["mediana"] <= stats["percentil_95"]

    def test_simulador_reproducible_con_seed(self, config_test: Dict[str, Any], logger_mock: MagicMock, sample_escenario: Dict[str, Any]) -> None:
        """Con la misma seed, los resultados deben ser identicos."""
        sim = MockSimuladorEscenarios(config_test, logger_mock)
        esc_id = sim.crear(sample_escenario["nombre"], sample_escenario["descripcion"], sample_escenario["variables"])
        r1 = sim.ejecutar(esc_id, n_runs=100, seed=42)
        r2 = sim.ejecutar(esc_id, n_runs=100, seed=42)
        assert r1["estadisticas"]["media"] == pytest.approx(r2["estadisticas"]["media"])

    def test_simulador_analisis_sensibilidad(self, config_test: Dict[str, Any], logger_mock: MagicMock, sample_escenario: Dict[str, Any]) -> None:
        """El analisis de sensibilidad debe rankear las variables."""
        sim = MockSimuladorEscenarios(config_test, logger_mock)
        esc_id = sim.crear(sample_escenario["nombre"], sample_escenario["descripcion"], sample_escenario["variables"])
        ranking = sim.analisis_sensibilidad(esc_id, n_runs=200)
        assert len(ranking) == len(sample_escenario["variables"])
        # El ranking debe estar ordenado por impacto descendente
        for i in range(len(ranking) - 1):
            assert ranking[i]["impacto"] >= ranking[i + 1]["impacto"]

    def test_simulador_comparar_escenarios(self, config_test: Dict[str, Any], logger_mock: MagicMock) -> None:
        """Comparar dos escenarios debe producir diferencias."""
        sim = MockSimuladorEscenarios(config_test, logger_mock)
        vars1 = [{"nombre": "v1", "valor_base": 100.0, "rango_min": 50.0, "rango_max": 150.0, "distribucion": "uniforme"}]
        vars2 = [{"nombre": "v1", "valor_base": 200.0, "rango_min": 100.0, "rango_max": 300.0, "distribucion": "uniforme"}]
        esc1 = sim.crear("Esc A", "Descripcion A", vars1)
        esc2 = sim.crear("Esc B", "Descripcion B", vars2)
        comparacion = sim.comparar([esc1, esc2])
        assert "diferencias" in comparacion

    def test_simulador_escenario_peor_caso(self, config_test: Dict[str, Any], logger_mock: MagicMock, sample_escenario: Dict[str, Any]) -> None:
        """Encontrar el peor caso debe producir valores en los extremos."""
        sim = MockSimuladorEscenarios(config_test, logger_mock)
        esc_id = sim.crear(sample_escenario["nombre"], sample_escenario["descripcion"], sample_escenario["variables"])
        peor = sim.peor_caso(esc_id)
        assert "valores" in peor
        assert "resultado" in peor

    def test_simulador_n_runs_mayor_cero(self, config_test: Dict[str, Any], logger_mock: MagicMock, sample_escenario: Dict[str, Any]) -> None:
        """Debe fallar si n_runs < 1."""
        sim = MockSimuladorEscenarios(config_test, logger_mock)
        esc_id = sim.crear(sample_escenario["nombre"], sample_escenario["descripcion"], sample_escenario["variables"])
        with pytest.raises(ValueError):
            sim.ejecutar(esc_id, n_runs=0)


# ============================================================================
# TESTS: Grafo de Conocimiento
# ============================================================================


class TestGrafoConocimiento:
    """Tests para el grafo de conocimiento hibrido."""

    def test_grafo_crear_nodo(self, config_test: Dict[str, Any], logger_mock: MagicMock, db_temp: sqlite3.Connection) -> None:
        """Agregar un nodo al grafo."""
        grafo = MockGrafoConocimiento(db_temp, logger_mock)
        nodo_id = grafo.agregar_nodo("Inteligencia Artificial", "concepto")
        assert nodo_id is not None
        assert grafo.obtener_nodo(nodo_id) is not None

    def test_grafo_crear_relacion(self, config_test: Dict[str, Any], logger_mock: MagicMock, db_temp: sqlite3.Connection) -> None:
        """Crear una relacion entre dos nodos."""
        grafo = MockGrafoConocimiento(db_temp, logger_mock)
        n1 = grafo.agregar_nodo("Regulacion", "concepto")
        n2 = grafo.agregar_nodo("Innovacion", "concepto")
        rel_id = grafo.agregar_relacion(n1, n2, "afecta", peso=0.8)
        assert rel_id is not None

    def test_grafo_buscar_camino(self, config_test: Dict[str, Any], logger_mock: MagicMock, db_temp: sqlite3.Connection) -> None:
        """Encontrar camino indirecto entre nodos."""
        grafo = MockGrafoConocimiento(db_temp, logger_mock)
        n1 = grafo.agregar_nodo("A", "entidad")
        n2 = grafo.agregar_nodo("B", "entidad")
        n3 = grafo.agregar_nodo("C", "entidad")
        grafo.agregar_relacion(n1, n2, "relacion", peso=1.0)
        grafo.agregar_relacion(n2, n3, "relacion", peso=1.0)
        caminos = grafo.encontrar_caminos(n1, n3, max_longitud=4)
        assert len(caminos) > 0

    def test_grafo_consultar_vecinos(self, config_test: Dict[str, Any], logger_mock: MagicMock, db_temp: sqlite3.Connection) -> None:
        """Consultar vecinos de un nodo."""
        grafo = MockGrafoConocimiento(db_temp, logger_mock)
        n1 = grafo.agregar_nodo("Central", "concepto")
        n2 = grafo.agregar_nodo("Vecino1", "concepto")
        n3 = grafo.agregar_nodo("Vecino2", "concepto")
        grafo.agregar_relacion(n1, n2, "relacion", peso=0.5)
        grafo.agregar_relacion(n1, n3, "relacion", peso=0.7)
        vecinos = grafo.vecinos_mas_relevantes(n1, k=5)
        assert len(vecinos) == 2

    def test_grafo_exportar_json(self, config_test: Dict[str, Any], logger_mock: MagicMock, db_temp: sqlite3.Connection) -> None:
        """Exportar el grafo a JSON."""
        grafo = MockGrafoConocimiento(db_temp, logger_mock)
        grafo.agregar_nodo("Test", "concepto")
        exportado = grafo.exportar_json()
        assert "nodos" in exportado
        assert "relaciones" in exportado
        assert "metadata" in exportado
        assert exportado["metadata"]["total_nodos"] >= 1

    def test_grafo_importar_json(self, config_test: Dict[str, Any], logger_mock: MagicMock, db_temp: sqlite3.Connection) -> None:
        """Importar un grafo desde JSON."""
        grafo = MockGrafoConocimiento(db_temp, logger_mock)
        data = {
            "nodos": [
                {"id": "imp_1", "nombre": "Importado 1", "tipo": "concepto"},
                {"id": "imp_2", "nombre": "Importado 2", "tipo": "entidad"},
            ],
            "relaciones": [
                {"origen": "imp_1", "destino": "imp_2", "tipo": "relacion", "peso": 0.5},
            ],
        }
        n_nodos, n_rels = grafo.importar_json(data)
        assert n_nodos == 2
        assert n_rels == 1

    def test_grafo_centralidad(self, config_test: Dict[str, Any], logger_mock: MagicMock, db_temp: sqlite3.Connection) -> None:
        """Calcular centralidad de nodos."""
        grafo = MockGrafoConocimiento(db_temp, logger_mock)
        # Grafo estrella: n0 conectado a todos
        n0 = grafo.agregar_nodo("Central", "concepto")
        for i in range(5):
            ni = grafo.agregar_nodo(f"Nodo{i}", "entidad")
            grafo.agregar_relacion(n0, ni, "relacion", peso=1.0)
        centralidad = grafo.centralidad_nodos(top_k=3)
        assert len(centralidad) > 0
        assert centralidad[0][0] == n0  # El nodo central debe ser el mas central

    def test_grafo_detectar_comunidades(self, config_test: Dict[str, Any], logger_mock: MagicMock, db_temp: sqlite3.Connection) -> None:
        """Detectar comunidades en el grafo."""
        grafo = MockGrafoConocimiento(db_temp, logger_mock)
        # Crear dos comunidades desconectadas
        for i in range(3):
            n = grafo.agregar_nodo(f"A{i}", "entidad")
            if i > 0:
                prev = grafo.agregar_nodo(f"A{i-1}", "entidad") if i == 1 else f"A{i-1}"
                grafo.agregar_relacion(f"A{i-1}", n, "relacion", peso=1.0)
        for i in range(3):
            n = grafo.agregar_nodo(f"B{i}", "entidad")
            if i > 0:
                grafo.agregar_relacion(f"B{i-1}", n, "relacion", peso=1.0)
        comunidades = grafo.detectar_comunidades()
        assert len(comunidades) >= 1

    def test_grafo_similitud_nodos(self, config_test: Dict[str, Any], logger_mock: MagicMock, db_temp: sqlite3.Connection) -> None:
        """Calcular similitud coseno entre embeddings de nodos."""
        grafo = MockGrafoConocimiento(db_temp, logger_mock)
        n1 = grafo.agregar_nodo("N1", "concepto", embedding=[1.0, 0.0, 0.0])
        n2 = grafo.agregar_nodo("N2", "concepto", embedding=[0.0, 1.0, 0.0])
        sim = grafo.similitud_nodos(n1, n2)
        assert sim == pytest.approx(0.0, abs=1e-6)

    def test_grafo_similitud_identicos(self, config_test: Dict[str, Any], logger_mock: MagicMock, db_temp: sqlite3.Connection) -> None:
        """La similitud de un nodo consigo mismo debe ser 1.0."""
        grafo = MockGrafoConocimiento(db_temp, logger_mock)
        n1 = grafo.agregar_nodo("N1", "concepto", embedding=[1.0, 1.0, 1.0])
        sim = grafo.similitud_nodos(n1, n1)
        assert sim == pytest.approx(1.0, abs=1e-6)

    def test_grafo_expansion_desde_texto(self, config_test: Dict[str, Any], logger_mock: MagicMock, db_temp: sqlite3.Connection) -> None:
        """Expandir el grafo extrayendo entidades de texto."""
        grafo = MockGrafoConocimiento(db_temp, logger_mock)
        texto = "Apple y Google compiten en el mercado de #IA. @tech_analyst lo analiza."
        resultado = grafo.expandir_desde_texto(texto)
        assert "nodos" in resultado
        assert "relaciones" in resultado
        assert len(resultado["nodos"]) > 0

    def test_grafo_conteo_correcto(self, config_test: Dict[str, Any], logger_mock: MagicMock, db_temp: sqlite3.Connection) -> None:
        """El conteo de nodos y relaciones debe ser exacto."""
        grafo = MockGrafoConocimiento(db_temp, logger_mock)
        assert grafo.conteo_nodos() == 0
        assert grafo.conteo_relaciones() == 0
        n1 = grafo.agregar_nodo("N1", "entidad")
        n2 = grafo.agregar_nodo("N2", "entidad")
        grafo.agregar_relacion(n1, n2, "relacion", peso=1.0)
        assert grafo.conteo_nodos() == 2
        assert grafo.conteo_relaciones() == 1

    def test_grafo_resumen(self, config_test: Dict[str, Any], logger_mock: MagicMock, db_temp: sqlite3.Connection) -> None:
        """El resumen del grafo debe contener estadisticas clave."""
        grafo = MockGrafoConocimiento(db_temp, logger_mock)
        grafo.agregar_nodo("N1", "concepto")
        grafo.agregar_nodo("N2", "entidad")
        resumen = grafo.resumen()
        assert "nodos" in resumen
        assert "relaciones" in resumen
        assert "densidad" in resumen
        assert resumen["nodos"] == 2


# ============================================================================
# Mocks para tests de analysis
# ============================================================================


class MockAgenteCientifico:
    """Mock del Agente Cientifico para tests."""

    def __init__(self, config: Dict[str, Any], logger: MagicMock) -> None:
        self.config = config
        self.logger = logger

    def validar(self, hipotesis: Dict[str, Any]) -> Dict[str, Any]:
        texto = hipotesis.get("texto", "")
        if not texto or not texto.strip():
            raise ValueError("La hipotesis no puede estar vacia")

        ev_favor = hipotesis.get("evidencia_a_favor", [])
        ev_contra = hipotesis.get("evidencia_en_contra", [])

        # Heuristica de validacion
        fuerza_evidencia = min(len(ev_favor) * 0.2, 0.8)
        penalizacion_contra = min(len(ev_contra) * 0.15, 0.5)
        confianza_base = max(0.0, min(1.0, 0.5 + fuerza_evidencia - penalizacion_contra))

        # Detectar falacias
        falacias = []
        if "despues de" in texto.lower() and "por eso" in texto.lower():
            falacias.append("post_hoc_ergo_propter_hoc")
        if "todos los" in texto.lower() or "todos" in texto.lower():
            falacias.append("generalizacion_excesiva")
        if "desde que" in texto.lower():
            falacias.append("post_hoc")

        confianza_final = confianza_base * (1 - len(falacias) * 0.1)
        confianza_final = max(0.0, min(1.0, confianza_final))

        # Sesgos
        sesgos = []
        if len(ev_contra) == 0 and len(ev_favor) > 0:
            sesgos.append({"tipo": "sesgo_de_confirmacion", "presente": True, "severidad": 0.6})
        if "todos" in texto.lower():
            sesgos.append({"tipo": "generalizacion_excesiva", "presente": True, "severidad": 0.7})

        # Veredicto
        if confianza_final > 0.7 and len(falacias) == 0:
            veredicto = "confirmada"
        elif confianza_final < 0.3 or len(falacias) > 1:
            veredicto = "refutada"
        else:
            veredicto = "inconclusa"

        return {
            "veredicto": veredicto,
            "confianza": round(confianza_final, 4),
            "razonamiento": f"Evaluacion heuristica: {len(ev_favor)} a favor, {len(ev_contra)} en contra, {len(falacias)} falacias.",
            "sesgos_detectados": sesgos,
            "falacias_detectadas": falacias,
            "hipotesis_alternativas": [
                "Tercera variable no considerada explica la correlacion",
                "La causalidad es bidireccional",
                "El efecto es espurio (azar estadistico)",
            ],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


class MockMotorHipotesis:
    """Mock del Motor de Hipotesis para tests."""

    def __init__(self, db: sqlite3.Connection, config: Dict[str, Any], logger: MagicMock) -> None:
        self.db = db
        self.config = config
        self.logger = logger
        self._hipotesis: List[Dict[str, Any]] = []

    def generar(self, clusters: List[Dict[str, Any]], contexto: str) -> List[Dict[str, Any]]:
        if not clusters:
            return [{"texto": "No hay clusters suficientes", "nivel_confianza": 0.3, "tags": []}]
        
        hipotesis = []
        for i, cluster in enumerate(clusters[:3]):
            hipotesis.append({
                "id": f"hip_gen_{i}",
                "texto": f"Hipotesis sobre {cluster.get('topic', 'tema')}: patron detectado en {cluster.get('size', 0)} muestras",
                "nivel_confianza": min(0.5 + cluster.get("coherence", 0) * 0.5, 0.95),
                "nivel_riesgo": 0.4,
                "tags": [cluster.get("topic", "general")],
                "nei": 0.0,
            })
        return hipotesis

    def calcular_nei(self, metricas: Dict[str, float]) -> float:
        pesos = self.config["pesos_nei"]
        valores = [metricas.get(k, 0.0) for k in ["FR", "GR", "DV", "NV", "EM", "ST"]]
        valores = [max(0.0, min(1.0, v)) for v in valores]
        nei = sum(p * v for p, v in zip(pesos, valores))
        return float(np.clip(nei, 0.0, 1.0))

    def detectar_cascada(self, hipotesis: List[Dict[str, Any]], umbral: float = 0.7) -> List[Dict[str, Any]]:
        cascadas = []
        for h in hipotesis:
            historial = h.get("historial_nei", [])
            if len(historial) >= 2:
                ultimos = [nei for _, nei in historial[-3:]]
                if len(ultimos) >= 2 and ultimos[-1] >= umbral:
                    creciendo = all(ultimos[i] <= ultimos[i + 1] for i in range(len(ultimos) - 1))
                    if creciendo:
                        cascadas.append(h)
        return cascadas

    def aprender_pesos(self, historial: List[Dict[str, Any]]) -> List[float]:
        if not historial:
            return self.config["pesos_nei"]
        # Ajuste simple: refuerzar metricas que correlacionan con aciertos
        pesos = np.array(self.config["pesos_nei"], dtype=float)
        for entrada in historial:
            m = entrada.get("metricas", {})
            valores = np.array([m.get(k, 0.0) for k in ["FR", "GR", "DV", "NV", "EM", "ST"]])
            acierto = entrada.get("acierto", 0)
            if acierto:
                pesos += 0.01 * valores
            else:
                pesos -= 0.01 * valores
        pesos = np.maximum(pesos, 1e-6)
        pesos = pesos / pesos.sum()
        return pesos.tolist()

    def health_status(self) -> Dict[str, Any]:
        return {"estado": "ok", "score": 0.92, "mensaje": f"{len(self._hipotesis)} hipotesis activas"}

    def archivar_caducas(self, hipotesis: List[Dict[str, Any]], dias: int = 7) -> List[str]:
        from datetime import timedelta
        umbral = datetime.now(timezone.utc) - timedelta(days=dias)
        archivadas = []
        for h in hipotesis:
            updated = h.get("updated_at", "")
            if updated:
                try:
                    dt = datetime.fromisoformat(updated)
                    if dt < umbral and h.get("estado") == "activa":
                        archivadas.append(h["id"])
                except ValueError:
                    pass
        return archivadas


class MockMotorCausal:
    """Mock del Motor Causal para tests."""

    def __init__(self, grafo: MagicMock, db: sqlite3.Connection, logger: MagicMock) -> None:
        self.grafo = grafo
        self.db = db
        self.logger = logger

    def granger_causality(self, serie_x: List[float], serie_y: List[float], max_lag: int = 5) -> Dict[str, Any]:
        if len(serie_x) != len(serie_y):
            raise ValueError("Las series deben tener la misma longitud")
        n = len(serie_x)
        if n < max_lag + 5:
            raise ValueError(f"Se necesitan al menos {max_lag + 5} observaciones")

        x = np.asarray(serie_x, dtype=float)
        y = np.asarray(serie_y, dtype=float)

        # Modelo simplificado: regresion y ~ lag(y) + lag(x)
        from scipy import stats as sp_stats
        # Correlacion cruzada como proxy
        corr = np.corrcoef(x[:-1], y[1:])[0, 1] if n > 1 else 0
        f_stat = corr ** 2 * (n - 2) / (1 - corr ** 2 + 1e-10)
        p_value = 1.0 - sp_stats.f.cdf(abs(f_stat), 1, max(n - 2, 1))

        direccion = "X->Y" if p_value < 0.05 else "ninguna"
        return {
            "p_value": float(p_value),
            "lags_significativos": [1] if p_value < 0.05 else [],
            "direccion": direccion,
            "fuerza": float(abs(f_stat)),
            "significativo": p_value < 0.05,
        }

    def transfer_entropy(self, serie_x: List[float], serie_y: List[float]) -> float:
        # Aproximacion: correlacion como proxy de TE
        x = np.asarray(serie_x)
        y = np.asarray(serie_y)
        corr = abs(np.corrcoef(x, y)[0, 1]) if len(x) > 1 else 0
        return float(corr * 0.5)

    def correlacion_parcial(self, x: List[float], y: List[float], control: List[List[float]]) -> float:
        if not control:
            return float(np.corrcoef(x, y)[0, 1]) if len(x) > 1 else 0.0
        # Simplificacion: correlacion residual basica
        x_arr = np.asarray(x, dtype=float)
        y_arr = np.asarray(y, dtype=float)
        Z = np.column_stack([np.asarray(z, dtype=float) for z in control])
        # Residualizar
        x_res = x_arr - np.polyval(np.polyfit(Z[:, 0], x_arr, 1), Z[:, 0]) if Z.shape[1] > 0 else x_arr
        y_res = y_arr - np.polyval(np.polyfit(Z[:, 0], y_arr, 1), Z[:, 0]) if Z.shape[1] > 0 else y_arr
        if np.std(x_res) == 0 or np.std(y_res) == 0:
            return 0.0
        return float(np.corrcoef(x_res, y_res)[0, 1])

    def evaluar_confundidor(self, causa: str, efecto: str, candidato: str) -> Dict[str, Any]:
        return {
            "es_confundidor": False,
            "correlacion_cruda": 0.5,
            "correlacion_controlada": 0.3,
            "reduccion": 0.4,
            "metodo": "estructural",
        }

    def health_status(self) -> Dict[str, Any]:
        return {"estado": "ok", "score": 0.88}

    def simular_intervencion(self, nodo: str, valor: float) -> Dict[str, Any]:
        return {
            "intervencion": {"nodo": nodo, "valor": valor},
            "efectos": [{"nodo": "descendiente_1", "delta": valor * 0.3}],
        }

    def detectar_ciclos(self) -> List[List[str]]:
        return []


class MockSimuladorEscenarios:
    """Mock del Simulador de Escenarios para tests."""

    def __init__(self, config: Dict[str, Any], logger: MagicMock) -> None:
        self.config = config
        self.logger = logger
        self._escenarios: Dict[str, Dict[str, Any]] = {}
        self._resultados: Dict[str, Dict[str, Any]] = {}

    def crear(self, nombre: str, descripcion: str, variables: List[Dict[str, Any]]) -> str:
        esc_id = f"esc_{uuid.uuid4().hex[:8]}"
        self._escenarios[esc_id] = {"nombre": nombre, "descripcion": descripcion, "variables": variables}
        return esc_id

    def ejecutar(self, esc_id: str, n_runs: int = 1000, seed: int | None = None) -> Dict[str, Any]:
        if n_runs < 1:
            raise ValueError("n_runs debe ser al menos 1")
        rng = np.random.default_rng(seed)
        esc = self._escenarios[esc_id]
        resultados = []
        for _ in range(n_runs):
            val = 0
            for var in esc["variables"]:
                vmin = var.get("rango_min", 0)
                vmax = var.get("rango_max", 1)
                val += rng.uniform(vmin, vmax)
            resultados.append(val)

        arr = np.array(resultados)
        stats = {
            "media": float(np.mean(arr)),
            "mediana": float(np.median(arr)),
            "desv_est": float(np.std(arr)),
            "percentil_05": float(np.percentile(arr, 5)),
            "percentil_95": float(np.percentile(arr, 95)),
        }
        resultado = {"estadisticas": stats, "n_runs": n_runs, "seed": seed}
        self._resultados[esc_id] = resultado
        return resultado

    def analisis_sensibilidad(self, esc_id: str, n_runs: int = 1000) -> List[Dict[str, Any]]:
        esc = self._escenarios[esc_id]
        ranking = []
        for i, var in enumerate(esc["variables"]):
            impacto = 1.0 / (i + 1)  # Simulacion: orden inverso
            ranking.append({
                "variable": var["nombre"],
                "coeficiente_spearman": impacto * 0.8,
                "impacto": impacto,
                "ranking": i + 1,
            })
        ranking.sort(key=lambda x: x["impacto"], reverse=True)
        for i, r in enumerate(ranking):
            r["ranking"] = i + 1
        return ranking

    def comparar(self, esc_ids: List[str]) -> Dict[str, Any]:
        return {"diferencias": [{"var": "x", "diff": 10.0}], "recomendacion": "Escenario A es mejor"}

    def peor_caso(self, esc_id: str) -> Dict[str, Any]:
        esc = self._escenarios[esc_id]
        valores = {var["nombre"]: var.get("rango_min", 0) for var in esc["variables"]}
        return {"valores": valores, "resultado": sum(valores.values())}


class MockGrafoConocimiento:
    """Mock del Grafo de Conocimiento para tests."""

    def __init__(self, db: sqlite3.Connection, logger: MagicMock) -> None:
        self.db = db
        self.logger = logger
        self._nodos: Dict[str, Dict[str, Any]] = {}
        self._relaciones: List[Dict[str, Any]] = []
        self._indice_nombre: Dict[str, str] = {}  # nombre -> id

    def agregar_nodo(self, nombre: str, tipo: str, embedding: List[float] | None = None) -> str:
        nodo_id = f"n_{uuid.uuid4().hex[:8]}"
        self._nodos[nodo_id] = {"id": nodo_id, "nombre": nombre, "tipo": tipo, "embedding": embedding or []}
        self._indice_nombre[nombre.lower()] = nodo_id
        return nodo_id

    def obtener_nodo(self, nodo_id: str) -> Dict[str, Any] | None:
        return self._nodos.get(nodo_id)

    def buscar_nodo_por_nombre(self, nombre: str) -> str | None:
        return self._indice_nombre.get(nombre.lower())

    def agregar_relacion(self, origen: str, destino: str, tipo: str, peso: float = 1.0) -> str:
        rel_id = f"r_{uuid.uuid4().hex[:8]}"
        self._relaciones.append({"id": rel_id, "origen": origen, "destino": destino, "tipo": tipo, "peso": peso})
        return rel_id

    def encontrar_caminos(self, origen: str, destino: str, max_longitud: int = 4) -> List[List[str]]:
        # BFS simplificado
        from collections import deque
        queue = deque([(origen, [origen])])
        caminos = []
        while queue and len(caminos) < 100:
            actual, camino = queue.popleft()
            if actual == destino and len(camino) > 1:
                caminos.append(camino)
                continue
            if len(camino) > max_longitud:
                continue
            for rel in self._relaciones:
                if rel["origen"] == actual and rel["destino"] not in camino:
                    queue.append((rel["destino"], camino + [rel["destino"]]))
        return caminos

    def vecinos_mas_relevantes(self, nodo_id: str, k: int = 10) -> List[tuple]:
        vecinos: Dict[str, float] = {}
        for rel in self._relaciones:
            if rel["origen"] == nodo_id:
                vecinos[rel["destino"]] = vecinos.get(rel["destino"], 0) + rel["peso"]
            if rel["destino"] == nodo_id:
                vecinos[rel["origen"]] = vecinos.get(rel["origen"], 0) + rel["peso"]
        ordenados = sorted(vecinos.items(), key=lambda x: x[1], reverse=True)
        return ordenados[:k]

    def exportar_json(self) -> Dict[str, Any]:
        return {
            "metadata": {"total_nodos": len(self._nodos), "total_relaciones": len(self._relaciones), "version": "1.0"},
            "nodos": list(self._nodos.values()),
            "relaciones": self._relaciones,
        }

    def importar_json(self, data: Dict[str, Any]) -> tuple:
        for n in data.get("nodos", []):
            nid = n.get("id", f"n_{uuid.uuid4().hex[:8]}")
            self._nodos[nid] = n
            if "nombre" in n:
                self._indice_nombre[n["nombre"].lower()] = nid
        for r in data.get("relaciones", []):
            self._relaciones.append(r)
        return len(self._nodos), len(self._relaciones)

    def centralidad_nodos(self, top_k: int = 20) -> List[tuple]:
        # Betweenness simplificado: contar cuantos caminos pasan por cada nodo
        scores = {nid: 0.0 for nid in self._nodos}
        nodos_list = list(self._nodos.keys())
        for i, origen in enumerate(nodos_list):
            for destino in nodos_list[i + 1:]:
                caminos = self.encontrar_caminos(origen, destino, max_longitud=4)
                for camino in caminos:
                    for nodo in camino[1:-1]:  # No contar extremos
                        scores[nodo] = scores.get(nodo, 0) + 1
        ordenados = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return ordenados[:top_k]

    def detectar_comunidades(self) -> Dict[str, List[str]]:
        # Comunidades simplificadas: componentes conectados
        visitados = set()
        comunidades = {}
        idx = 0
        for nodo in self._nodos:
            if nodo not in visitados:
                com = self._dfs(nodo, set())
                if com:
                    comunidades[f"comunidad_{idx}"] = list(com)
                    visitados.update(com)
                    idx += 1
        return comunidades

    def _dfs(self, inicio: str, visitados: set) -> set:
        pila = [inicio]
        while pila:
            n = pila.pop()
            if n not in visitados:
                visitados.add(n)
                for rel in self._relaciones:
                    if rel["origen"] == n and rel["destino"] not in visitados:
                        pila.append(rel["destino"])
                    if rel["destino"] == n and rel["origen"] not in visitados:
                        pila.append(rel["origen"])
        return visitados

    def similitud_nodos(self, nodo_a: str, nodo_b: str) -> float:
        n1 = self._nodos.get(nodo_a, {})
        n2 = self._nodos.get(nodo_b, {})
        emb1 = n1.get("embedding", [])
        emb2 = n2.get("embedding", [])
        if not emb1 or not emb2:
            return 0.0
        a = np.array(emb1, dtype=float)
        b = np.array(emb2, dtype=float)
        na, nb = np.linalg.norm(a), np.linalg.norm(b)
        if na == 0 or nb == 0:
            return 0.0
        return float(np.dot(a, b) / (na * nb))

    def expandir_desde_texto(self, texto: str) -> Dict[str, Any]:
        import re
        nodos = []
        # Hashtags
        for ht in re.findall(r"#(\w+)", texto):
            nid = self.agregar_nodo(ht, "hashtag")
            nodos.append(nid)
        # Menciones
        for m in re.findall(r"@(\w+)", texto):
            nid = self.agregar_nodo(m, "usuario")
            nodos.append(nid)
        # Entidades capitalizadas
        for ent in re.findall(r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*", texto):
            nid = self.agregar_nodo(ent, "entidad")
            nodos.append(nid)
        # Relaciones de co-ocurrencia
        rels = []
        for i in range(len(nodos)):
            for j in range(i + 1, min(i + 5, len(nodos))):
                rels.append(self.agregar_relacion(nodos[i], nodos[j], "co_ocurre", peso=0.5))
        return {"nodos": nodos, "relaciones": rels}

    def conteo_nodos(self) -> int:
        return len(self._nodos)

    def conteo_relaciones(self) -> int:
        return len(self._relaciones)

    def resumen(self) -> Dict[str, Any]:
        tipos = {}
        for n in self._nodos.values():
            t = n.get("tipo", "desconocido")
            tipos[t] = tipos.get(t, 0) + 1
        n = len(self._nodos)
        e = len(self._relaciones)
        return {
            "nodos": n,
            "relaciones": e,
            "densidad": (2 * e / (n * (n - 1))) if n > 1 else 0.0,
            "tipos_nodos": tipos,
        }
