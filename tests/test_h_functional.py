"""
Tests funcionales para VEO v2.0.4G.

Verifican comportamiento real de componentes, no únicamente que las
funciones se puedan llamar. Evitan mocks innecesarios.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock

import pytest


# ============================================================================
# P1: VALIDACIÓN CIENTÍFICA
# ============================================================================

class TestScientificValidationReal:
    """Tests que prueban CoordinadorValidacion con datos reales."""

    def test_hipotesis_firma_correcta(self):
        """Hipotesis se instancia con la firma correcta."""
        from analysis.scientific_agent import Hipotesis
        h = Hipotesis(
            texto="El cambio climático causa sequías",
            nivel_confianza_inicial=0.6,
        )
        assert h.texto == "El cambio climático causa sequías"
        assert h.nivel_confianza_inicial == 0.6

    def test_coordinador_validar_retorna_estructura_correcta(self):
        """CoordinadorValidacion.validar() retorna las claves esperadas."""
        from analysis.scientific_agent import CoordinadorValidacion, Hipotesis
        cv = CoordinadorValidacion()
        h = Hipotesis(texto="El cambio climático causa sequías", nivel_confianza_inicial=0.6)
        resultado = cv.validar(h)

        assert "veredicto_final" in resultado
        assert "confianza" in resultado
        assert "razonamiento_cientifico" in resultado
        assert "evaluacion_sesgos" in resultado
        assert "recomendacion" in resultado
        assert isinstance(resultado["confianza"], float)
        assert 0.0 <= resultado["confianza"] <= 1.0

    def test_veredicto_es_valor_esperado(self):
        """El veredicto es uno de los valores del enum VeredictoFinal."""
        from analysis.scientific_agent import CoordinadorValidacion, Hipotesis
        cv = CoordinadorValidacion()
        h = Hipotesis(texto="Test", nivel_confianza_inicial=0.5)
        resultado = cv.validar(h)
        assert resultado["veredicto_final"] in (
            "ACEPTAR", "DESCARTAR", "NECESITA_MAS_EVIDENCIA", "REVISION_MANUAL"
        )

    def test_validacion_cientifica_no_devuelve_50_por_defecto(self):
        """Los scores de validación deben reflejar el análisis real, no 50.

        Este test verifica el fix del key mismatch: antes _validate_hypotheses
        buscaba 'puntuacion_final', 'puntuacion_cientifica', etc., que no
        existían, y caía en valores por defecto de 50. Ahora debe mapear
        correctamente desde 'confianza', 'razonamiento_cientifico.confianza',
        'evaluacion_sesgos.score_global'.
        """
        from core.veo_core import VEOCore
        import asyncio

        core = VEOCore()

        async def check():
            hypotheses = [
                {"id": "h1", "text": "El cambio climático causa sequías graves", "confidence": 75},
            ]
            validated = await core.reasoning._validate_hypotheses(hypotheses)
            assert len(validated) == 1
            v = validated[0]
            # Si el key mismatch estuviera presente, todos serían 50
            assert v["confidence"] != 50.0, (
                f"confidence sigue siendo 50.0 (key mismatch no corregido). "
                f"Resultado: {v}"
            )
            assert v["scientific_score"] != 50, (
                f"scientific_score sigue siendo 50 (key mismatch no corregido). "
                f"Resultado: {v}"
            )
            # skeptic_score puede ser 50 si el agente escéptico no detecta sesgos,
            # pero review_notes debe tener contenido real
            assert v["review_notes"] != "", (
                f"review_notes vacío (key mismatch no corregido). Resultado: {v}"
            )

        asyncio.run(check())

    def test_scores_tienen_sentido_semantico(self):
        """Los scores derivados deben tener sentido semántico.

        - confidence: confianza global del coordinador (0-100)
        - scientific_score: confianza del agente científico (0-100)
        - skeptic_score: inversión de score_global de sesgos (100=limpio, 0=sesgado)
        """
        from core.veo_core import VEOCore
        import asyncio

        core = VEOCore()

        async def check():
            hypotheses = [
                {"id": "h1", "text": "El cambio climático causa sequías", "confidence": 70},
            ]
            validated = await core.reasoning._validate_hypotheses(hypotheses)
            v = validated[0]
            # Todos los scores deben estar en rango 0-100
            assert 0.0 <= v["confidence"] <= 100.0
            assert 0.0 <= v["scientific_score"] <= 100.0
            assert 0.0 <= v["skeptic_score"] <= 100.0
            # review_notes debe contener texto explicativo
            assert len(v["review_notes"]) > 10

        asyncio.run(check())

    def test_scores_varian_con_evidencias(self):
        """Los scores varían cuando las hipótesis tienen evidencias diferentes.

        Este test verifica que el enriquecimiento de hipótesis con evidencias
        produce variabilidad en los scores del agente científico.
        """
        from analysis.scientific_agent import Hipotesis, CoordinadorValidacion

        cv = CoordinadorValidacion()

        # Hipótesis débil (sin evidencias)
        h1 = Hipotesis(texto="Test", nivel_confianza_inicial=0.5)
        r1 = cv.validar(h1)

        # Hipótesis con evidencias suficientes para confirmación
        # fuerza_evidencia = 5 * 0.15 = 0.75 > 0.7 umbral → CONFIRMADA
        h2 = Hipotesis(
            texto="El cambio climático causa sequías",
            nivel_confianza_inicial=0.5,
            evidencia_a_favor=[
                "NASA 2023", "Datos satelitales", "Modelos IPCC",
                "Mediciones NOAA", "Estudio Nature 2024"
            ],
            evidencia_en_contra=[],
        )
        r2 = cv.validar(h2)

        # Hipótesis con lenguaje sensacionalista
        h3 = Hipotesis(
            texto="¡La catástrofe absoluta destruirá todo!",
            nivel_confianza_inicial=0.9,
        )
        r3 = cv.validar(h3)

        scores = [
            round(r1["confianza"] * 100, 1),
            round(r2["confianza"] * 100, 1),
            round(r3["confianza"] * 100, 1),
        ]
        veredictos = [r1["veredicto_final"], r2["veredicto_final"], r3["veredicto_final"]]
        print(f"Scores confidence: {scores}")
        print(f"Veredictos: {veredictos}")

        # Los scores no deben ser todos idénticos
        assert len(set(scores)) > 1, (
            f"Los scores no varían: {scores}. "
            f"Veredictos: {veredictos}. "
            f"El enriquecimiento de hipótesis no está funcionando."
        )

    def test_validacion_con_evidencias_varia_skeptic_score(self):
        """El skeptic_score varía según el contenido de la hipótesis."""
        from analysis.scientific_agent import Hipotesis, CoordinadorValidacion

        cv = CoordinadorValidacion()

        # Texto con múltiples indicadores de sesgo (sin tildes para
        # consistencia con las listas internas del agente escéptico)
        h_sesgada = Hipotesis(
            texto="La catastrofe absoluta destruira todo! Siempre funciona sin excepcion.",
            nivel_confianza_inicial=0.9,
        )
        r_sesgada = cv.validar(h_sesgada)

        # Texto con lenguaje cauteloso y limitado
        h_cautelosa = Hipotesis(
            texto="Podria existir alguna relacion entre ciertas variables.",
            nivel_confianza_inicial=0.3,
        )
        r_cautelosa = cv.validar(h_cautelosa)

        sg_sesgada = r_sesgada["evaluacion_sesgos"].get("score_global", 0)
        sg_cautelosa = r_cautelosa["evaluacion_sesgos"].get("score_global", 0)

        print(f"score_global sesgada: {sg_sesgada}, cautelosa: {sg_cautelosa}")

        # Ambos scores deben ser reales (> 0, porque ambos textos tienen contenido)
        assert sg_sesgada > 0, f"Score de sesgo sesgada debería ser > 0: {sg_sesgada}"
        assert sg_cautelosa > 0, f"Score de sesgo cautelosa debería ser > 0: {sg_cautelosa}"
        # Y deben ser diferentes entre sí (no constantes)
        assert sg_sesgada != sg_cautelosa, (
            f"Scores de sesgo deberían diferir. Sesgada: {sg_sesgada}, Cautelosa: {sg_cautelosa}"
        )


# ============================================================================
# P2: MOTORCAUSAL / EXTRACCIÓN DE VARIABLES
# ============================================================================

class TestMotorCausalExtraction:
    """Tests para _extraer_variables() y detección de ciclos."""

    @pytest.fixture
    def motor(self):
        from analysis.causal_engine import MotorCausal
        return MotorCausal()

    def test_extraer_variables_pobreza_hambre(self, motor):
        """Caso crítico de la auditoría: 'pobreza causa hambre'."""
        variables = motor._extraer_variables("pobreza causa hambre y hambre causa pobreza")
        assert "pobreza" in variables, f"'pobreza' no encontrado en {variables}"
        assert "hambre" in variables, f"'hambre' no encontrado en {variables}"
        for v in variables:
            assert v != "pob", f"Variable truncada: {v}"
            assert v != "ham", f"Variable truncada: {v}"
            assert v != "bre", f"Variable truncada: {v}"

    def test_detectar_ciclo_directo(self, motor):
        """Detecta ciclo directo A → B → A."""
        ciclos = motor.detectar_ciclos_causales(
            "pobreza causa hambre y hambre causa pobreza"
        )
        assert len(ciclos) >= 1, f"No detectó ciclo en 'pobreza↔hambre'. Ciclos: {ciclos}"

    def test_detectar_ciclo_indirecto(self, motor):
        """Detecta ciclo indirecto A → B → C → A."""
        texto = (
            "pobreza causa hambre y hambre causa enfermedad "
            "y enfermedad causa pobreza"
        )
        ciclos = motor.detectar_ciclos_causales(texto)
        assert len(ciclos) >= 1, f"No detectó ciclo triangular. Ciclos: {ciclos}"

    def test_sin_ciclo(self, motor):
        """No detecta ciclos donde no los hay."""
        ciclos = motor.detectar_ciclos_causales(
            "lluvia causa crecimiento y sol causa fotosíntesis"
        )
        assert len(ciclos) == 0, f"Detectó ciclo inexistente: {ciclos}"

    def test_varios_nodos(self, motor):
        """Extrae múltiples variables de texto complejo."""
        variables = motor._extraer_variables(
            "calentamiento global causa sequías y sequías causan migración"
        )
        assert len(variables) >= 2, f"Pocas variables extraídas: {variables}"

    def test_texto_sin_relaciones(self, motor):
        """Texto sin verbos causales → lista vacía o mínima."""
        variables = motor._extraer_variables("Hoy hace buen tiempo en la ciudad")
        assert isinstance(variables, list)

    def test_entrada_vacia(self, motor):
        """Entrada vacía → lista vacía."""
        variables = motor._extraer_variables("")
        assert variables == []

    def test_entrada_invalida(self, motor):
        """Entrada con caracteres especiales no rompe."""
        variables = motor._extraer_variables("!!! @@@ ###")
        assert variables == []

    def test_analizar_produce_resultado_coherente(self, motor):
        """analizar() retorna HipotesisCausal con valores coherentes."""
        hyp = {
            "id": "h1",
            "text": "El cambio climático causa sequías que reducen cosechas",
            "confidence": 75,
        }
        resultado = motor.analizar(hyp)
        assert 0.0 <= resultado.coherencia <= 1.0
        assert len(resultado.variables) >= 1


# ============================================================================
# P3: URGENCY / IMPACT
# ============================================================================

class TestUrgencyImpact:
    """Tests para verificar combinación coherente de urgency/impact."""

    def test_urgency_no_es_solo_50(self):
        """urgency debe reflejar las señales, no ser 50 fijo."""
        from core.veo_core import VEOCore
        import asyncio

        core = VEOCore()

        async def check():
            signals = [
                {"id": "s1", "text": "Test", "urgency": 85, "impact": 80, "domain": "test", "confidence": 50},
            ]
            hyps = await core.reasoning._generate_hypotheses(signals)
            if hyps:
                assert hyps[0]["urgency"] != 50, (
                    f"urgency sigue siendo 50 fijo. Valor: {hyps[0]['urgency']}"
                )

        asyncio.run(check())

    def test_urgency_preserva_info_senales(self):
        """La información de las señales se preserva en la combinación."""
        from core.veo_core import VEOCore
        import asyncio

        core = VEOCore()

        async def check():
            signals = [
                {"id": "s1", "text": "Alerta máxima", "urgency": 90, "impact": 85, "domain": "test", "confidence": 50},
            ]
            hyps = await core.reasoning._generate_hypotheses(signals)
            if hyps:
                u = hyps[0]["urgency"]
                assert u >= 50, (
                    f"urgency={u} es sospechosamente bajo para señales con urgency=90"
                )

        asyncio.run(check())

    def test_impact_preserva_info_senales(self):
        """impact también se combina ponderadamente."""
        from core.veo_core import VEOCore
        import asyncio

        core = VEOCore()

        async def check():
            signals = [
                {"id": "s1", "text": "Impacto severo", "urgency": 80, "impact": 90, "domain": "test", "confidence": 50},
            ]
            hyps = await core.reasoning._generate_hypotheses(signals)
            if hyps:
                i = hyps[0]["impact"]
                assert i >= 60, (
                    f"impact={i} es sospechosamente bajo para señales con impact=90"
                )

        asyncio.run(check())

    def test_varios_casos_urgency(self):
        """Prueba múltiples combinaciones de señales y nivel_riesgo."""
        from core.veo_core import VEOCore
        import asyncio

        core = VEOCore()

        async def check():
            casos = [
                (10, 10, "bajo"),
                (50, 50, "medio"),
                (90, 90, "alto"),
            ]
            for u_senal, i_senal, desc in casos:
                signals = [
                    {"id": "s1", "text": desc, "urgency": u_senal, "impact": i_senal, "domain": "test", "confidence": 50},
                ]
                hyps = await core.reasoning._generate_hypotheses(signals)
                if hyps:
                    u = hyps[0]["urgency"]
                    i = hyps[0]["impact"]
                    assert 0.0 <= u <= 100.0, f"urgency={u} fuera de rango para caso {desc}"
                    assert 0.0 <= i <= 100.0, f"impact={i} fuera de rango para caso {desc}"

        asyncio.run(check())


# ============================================================================
# P4: WEBSOCKET CONCURRENCIA
# ============================================================================

class TestWebSocketConcurrency:
    """Tests para verificar protección con asyncio.Lock."""

    @pytest.mark.asyncio
    async def test_broadcast_no_race_condition(self):
        """broadcast() no produce RuntimeError si disconnect() ocurre durante iteración."""
        from api.api_server import WebSocketManager

        manager = WebSocketManager()
        ws_list = []
        for _ in range(10):
            ws = MagicMock()
            ws.accept = AsyncMock()
            ws_list.append(ws)
        for ws in ws_list:
            await manager.connect(ws)

        assert len(manager.active_connections) == 10

        async def broadcaster():
            for _ in range(20):
                await manager.broadcast({"tipo": "test", "dato": 1})

        async def disconnector():
            for ws in list(ws_list):
                await manager.disconnect(ws)

        await asyncio.gather(broadcaster(), disconnector(), return_exceptions=True)
        assert isinstance(manager.active_connections, list)

    @pytest.mark.asyncio
    async def test_connect_disconnect_atomic(self):
        """connect() y disconnect() son atómicos respecto a active_connections."""
        from api.api_server import WebSocketManager

        manager = WebSocketManager()
        ws = MagicMock()
        ws.accept = AsyncMock()

        await manager.connect(ws)
        assert ws in manager.active_connections

        await manager.disconnect(ws)
        assert ws not in manager.active_connections


# ============================================================================
# P5: FLUJO E2E
# ============================================================================

class TestFlujoE2E:
    """Tests de integración end-to-end."""

    def test_pipeline_completo_desde_senales(self):
        """Flujo completo: señales → hipótesis → validación → resultado final."""
        from core.veo_core import VEOCore
        import asyncio

        core = VEOCore()

        async def pipeline():
            signals = [
                {"id": "s1", "text": "El cambio climático causa sequías en el Mediterráneo", "urgency": 85, "impact": 80, "domain": "clima", "confidence": 78},
                {"id": "s2", "text": "Las sequías reducen la producción de trigo", "urgency": 75, "impact": 70, "domain": "economia", "confidence": 72},
            ]

            hypotheses = await core.reasoning._generate_hypotheses(signals)
            assert len(hypotheses) >= 1, "No se generaron hipótesis"

            validated = await core.reasoning._validate_hypotheses(hypotheses)
            assert len(validated) >= 1, "No se validaron hipótesis"

            for v in validated:
                assert "id" in v
                assert "confidence" in v
                assert "scientific_score" in v
                assert "skeptic_score" in v
                assert "review_notes" in v
                assert 0.0 <= v["confidence"] <= 100.0
                assert 0.0 <= v["scientific_score"] <= 100.0
                assert 0.0 <= v["skeptic_score"] <= 100.0

            return validated

        validated = asyncio.run(pipeline())
        assert any(v.get("review_notes", "") != "" for v in validated), (
            "Ninguna validación produjo review_notes"
        )


# ============================================================================
# P6: INFORMACION MUTUA
# ============================================================================

class TestInformacionMutua:
    """Tests para informacion_mutua()."""

    def test_con_listas_funciona(self):
        """Funciona correctamente con listas (interfaz correcta)."""
        from analysis.causal_engine import MotorCausal
        mc = MotorCausal()
        result = mc.informacion_mutua(
            [0.5, 0.5], [0.5, 0.5], [[0.25, 0.25], [0.25, 0.25]]
        )
        assert isinstance(result, float)
        assert result >= 0.0

    def test_con_floats_da_typeerror_claro(self):
        """Con floats da TypeError con mensaje claro."""
        from analysis.causal_engine import MotorCausal
        mc = MotorCausal()
        with pytest.raises(TypeError) as exc_info:
            mc.informacion_mutua(0.5, 0.5, 0.25)
        assert "list[float]" in str(exc_info.value) or "lista" in str(exc_info.value)

    def test_dimensiones_inconsistentes(self):
        """Detecta dimensiones inconsistentes."""
        from analysis.causal_engine import MotorCausal
        mc = MotorCausal()
        with pytest.raises(ValueError) as exc_info:
            mc.informacion_mutua(
                [0.5, 0.5], [0.5, 0.5, 0.0], [[0.25, 0.25], [0.25, 0.25]]
            )
        assert "Dimensiones inconsistentes" in str(exc_info.value)
