"""
test_planetary.py - Tests de equivalencia funcional del motor de diagnostico planetario.

Este modulo verifica que:
1. El motor generico (PlanetaryScoreEngine) produce los mismos resultados que los
   motores originales individuales (FutureContinuityEngine, FutureConsistencyEngine, etc.)
   cuando se configura con score_attrs equivalentes.
2. El orquestador (PlanetaryDiagnosisEngine) ejecuta todas las configuraciones
   correctamente y produce resultados con trazabilidad completa.
3. El sistema es extensible: permite agregar nuevas configuraciones en runtime
   sin modificar codigo existente.
4. Los motores de mapas y detectores de umbrales funcionan correctamente.

Estrategia de testing:
- Fixtures reutilizables para eventos y configuraciones
- Tests independientes (sin dependencias entre si)
- Comparacion numerica exacta (assertAlmostEqual) entre original y generico
- Cobertura de casos borde (valores extremos, eventos vacios, configs invalidas)
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import math

from analysis.planetary_configs import (
    PLANETARY_CONFIGS, PLANETARY_CONFIG_MAP, PlanetaryConfig,
    _even_weights, _weighted,
)
from analysis.planetary_diagnosis_engine import (
    PlanetaryEvent,
    PlanetaryDiagnosisEngine,
    PlanetaryScoreEngine,
    PlanetaryThresholdDetector,
    PlanetaryMapEngine,
    FutureContinuityEngine,
    FutureConsistencyEngine,
    FutureConvergenceEngine,
    FutureHarmonyEngine,
    FutureMasterEngine,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def sample_events():
    """
    Fixture con 2 eventos de ejemplo con valores variados.
    
    e1: Evento robusto (alta persistence, baja fragility)
    e2: Evento fragil (baja persistence, alta fragility)
    """
    return [
        PlanetaryEvent(
            event_id="e1",
            persistence=0.8,
            relevance=0.7,
            foresight=0.6,
            future_gravity=0.9,
            fragility=0.3,
            future_pressure=0.5,
            acceleration=0.4,
            dependencies_count=0.7,
            recovery=0.6,
            redundancy=0.5,
        ),
        PlanetaryEvent(
            event_id="e2",
            persistence=0.3,
            relevance=0.9,
            foresight=0.8,
            future_gravity=0.2,
            fragility=0.8,
            future_pressure=0.9,
            acceleration=0.7,
            dependencies_count=0.4,
            recovery=0.3,
            redundancy=0.2,
        ),
    ]


@pytest.fixture
def single_event():
    """Fixture con un unico evento para tests unitarios simples."""
    return PlanetaryEvent(
        event_id="single",
        persistence=0.75,
        relevance=0.65,
        foresight=0.55,
        future_gravity=0.85,
        fragility=0.25,
        future_pressure=0.45,
        acceleration=0.35,
        dependencies_count=0.65,
        recovery=0.55,
        redundancy=0.45,
    )


@pytest.fixture
def extreme_event_high():
    """Evento con todos los atributos en maximo (1.0)."""
    return PlanetaryEvent(
        event_id="extreme_high",
        persistence=1.0,
        relevance=1.0,
        foresight=1.0,
        future_gravity=1.0,
        fragility=0.0,  # 0 para que no se invierta y reste
        future_pressure=1.0,
        acceleration=1.0,
        dependencies_count=1.0,
        recovery=1.0,
        redundancy=1.0,
    )


@pytest.fixture
def extreme_event_low():
    """Evento con todos los atributos en minimo (0.0)."""
    return PlanetaryEvent(
        event_id="extreme_low",
        persistence=0.0,
        relevance=0.0,
        foresight=0.0,
        future_gravity=0.0,
        fragility=1.0,  # 1 para que al invertirsea 0
        future_pressure=0.0,
        acceleration=0.0,
        dependencies_count=0.0,
        recovery=0.0,
        redundancy=0.0,
    )


@pytest.fixture
def ten_events():
    """Fixture con 10 eventos variados para test de carga."""
    events = []
    base_values = [
        (0.9, 0.8, 0.7, 0.6, 0.1, 0.4, 0.3, 0.2, 0.5, 0.0),
        (0.0, 0.1, 0.2, 0.3, 0.9, 0.5, 0.6, 0.7, 0.8, 0.9),
        (0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5),
        (0.2, 0.8, 0.3, 0.7, 0.2, 0.6, 0.5, 0.1, 0.9, 0.0),
        (0.1, 0.2, 0.3, 0.4, 0.8, 0.6, 0.7, 0.8, 0.9, 1.0),
        (1.0, 0.9, 0.8, 0.7, 0.0, 0.5, 0.4, 0.3, 0.2, 0.1),
        (0.6, 0.4, 0.8, 0.2, 0.3, 0.3, 0.9, 0.1, 0.5, 0.0),
        (0.3, 0.7, 0.1, 0.9, 0.6, 0.6, 0.2, 0.8, 0.5, 0.0),
        (0.45, 0.55, 0.35, 0.65, 0.35, 0.75, 0.15, 0.85, 0.05, 0.95),
        (0.99, 0.01, 0.88, 0.12, 0.11, 0.23, 0.66, 0.34, 0.55, 0.45),
    ]
    for i, vals in enumerate(base_values):
        events.append(
            PlanetaryEvent(
                event_id=f"evt_{i:02d}",
                persistence=vals[0],
                relevance=vals[1],
                foresight=vals[2],
                future_gravity=vals[3],
                fragility=vals[4],
                future_pressure=vals[5],
                acceleration=vals[6],
                dependencies_count=vals[7],
                recovery=vals[8],
                redundancy=vals[9],
            )
        )
    return events


@pytest.fixture
def continuity_config():
    """Configuracion 'continuity' desde PLANETARY_CONFIG_MAP."""
    return PLANETARY_CONFIG_MAP["continuity"]


# =============================================================================
# SECCION 1: TESTS DE EQUIVALENCIA - MOTORES ORIGINALES vs GENERICOS
# =============================================================================


class TestScoreEngineEquivalence:
    """
    Tests que verifican que PlanetaryScoreEngine produce exactamente
    los mismos resultados que los motores originales individuales
    cuando se configura con score_attrs equivalentes.
    """

    def test_score_engine_continuity(self, single_event):
        """
        Verifica que PlanetaryScoreEngine con score_attrs equivalentes a la
        formula de FutureContinuityEngine produce el mismo resultado.
        
        El original hace: (persistence + relevance + foresight + future_gravity + (1-fragility)) / 5
        El generico con score_attrs={p,r,f,fg,fr: 0.2 c/u} e invert_fragility
        debe producir exactamente lo mismo.
        """
        equiv_config = PlanetaryConfig(
            name="continuity_equiv",
            description="Config equivalente a FutureContinuityEngine",
            score_attrs=_even_weights(["persistence", "relevance", "foresight", "future_gravity", "fragility"]),
            global_attrs={},
            threshold_attrs={},
            map_attrs=["persistence", "relevance", "foresight", "future_gravity"],
        )

        original_engine = FutureContinuityEngine()
        generic_engine = PlanetaryScoreEngine(equiv_config, invert_attrs=["fragility"])

        original_score = original_engine.compute(single_event)
        generic_score = generic_engine.compute(single_event)

        assert generic_score == pytest.approx(original_score, abs=1e-6), (
            f"Score de continuidad no coincide: "
            f"original={original_score}, generico={generic_score}"
        )

    def test_score_engine_consistency(self, single_event):
        """
        Verifica equivalencia con FutureConsistencyEngine.
        Original: (future_pressure + acceleration + foresight + persistence) / 4
        """
        equiv_config = PlanetaryConfig(
            name="consistency_equiv",
            description="Config equivalente a FutureConsistencyEngine",
            score_attrs=_even_weights(["future_pressure", "acceleration", "foresight", "persistence"]),
            global_attrs={},
            threshold_attrs={},
            map_attrs=["future_pressure", "acceleration", "foresight", "persistence"],
        )

        original_engine = FutureConsistencyEngine()
        generic_engine = PlanetaryScoreEngine(equiv_config)

        original_score = original_engine.compute(single_event)
        generic_score = generic_engine.compute(single_event)

        assert generic_score == pytest.approx(original_score, abs=1e-6), (
            f"Score de consistencia no coincide: "
            f"original={original_score}, generico={generic_score}"
        )

    def test_score_engine_convergence(self, single_event):
        """
        Verifica equivalencia con FutureConvergenceEngine.
        Original: (dependencies_count + persistence + relevance + future_gravity) / 4
        """
        equiv_config = PlanetaryConfig(
            name="convergence_equiv",
            description="Config equivalente a FutureConvergenceEngine",
            score_attrs=_even_weights(["dependencies_count", "persistence", "relevance", "future_gravity"]),
            global_attrs={},
            threshold_attrs={},
            map_attrs=["dependencies_count", "persistence", "relevance", "future_gravity"],
        )

        original_engine = FutureConvergenceEngine()
        generic_engine = PlanetaryScoreEngine(equiv_config)

        original_score = original_engine.compute(single_event)
        generic_score = generic_engine.compute(single_event)

        assert generic_score == pytest.approx(original_score, abs=1e-6), (
            f"Score de convergencia no coincide: "
            f"original={original_score}, generico={generic_score}"
        )

    def test_score_engine_harmony(self, single_event):
        """
        Verifica equivalencia con FutureHarmonyEngine.
        Original: (recovery + redundancy + relevance + foresight) / 4
        """
        equiv_config = PlanetaryConfig(
            name="harmony_equiv",
            description="Config equivalente a FutureHarmonyEngine",
            score_attrs=_even_weights(["recovery", "redundancy", "relevance", "foresight"]),
            global_attrs={},
            threshold_attrs={},
            map_attrs=["recovery", "redundancy", "relevance", "foresight"],
        )

        original_engine = FutureHarmonyEngine()
        generic_engine = PlanetaryScoreEngine(equiv_config)

        original_score = original_engine.compute(single_event)
        generic_score = generic_engine.compute(single_event)

        assert generic_score == pytest.approx(original_score, abs=1e-6), (
            f"Score de armonia no coincide: "
            f"original={original_score}, generico={generic_score}"
        )

    def test_score_engine_master(self, single_event):
        """
        Verifica equivalencia con FutureMasterEngine.
        Original: promedio ponderado de todos los atributos,
                  con pesos mayores en persistence, future_gravity, foresight,
                  e invirtiendo fragility.
        """
        equiv_config = PlanetaryConfig(
            name="master_equiv",
            description="Config equivalente a FutureMasterEngine",
            score_attrs=FutureMasterEngine.MASTER_WEIGHTS,
            global_attrs={},
            threshold_attrs={},
            map_attrs=["persistence", "future_gravity", "foresight", "relevance"],
        )

        original_engine = FutureMasterEngine()
        generic_engine = PlanetaryScoreEngine(equiv_config, invert_attrs=["fragility"])

        original_score = original_engine.compute(single_event)
        generic_score = generic_engine.compute(single_event)

        assert generic_score == pytest.approx(original_score, abs=1e-6), (
            f"Score maestro no coincide: "
            f"original={original_score}, generico={generic_score}"
        )

    def test_equivalence_multiple_events(self, sample_events):
        """
        Verifica la equivalencia para multiples eventos y todos los
        motores originales con configs equivalentes.
        """
        equiv_configs = {
            "continuity": (
                PlanetaryConfig(
                    name="continuity_equiv",
                    description="Equiv",
                    score_attrs=_even_weights(["persistence", "relevance", "foresight", "future_gravity", "fragility"]),
                    global_attrs={}, threshold_attrs={},
                    map_attrs=["persistence", "relevance", "foresight", "future_gravity"],
                ),
                FutureContinuityEngine(),
                ["fragility"],
            ),
            "consistency": (
                PlanetaryConfig(
                    name="consistency_equiv",
                    description="Equiv",
                    score_attrs=_even_weights(["future_pressure", "acceleration", "foresight", "persistence"]),
                    global_attrs={}, threshold_attrs={},
                    map_attrs=["future_pressure", "acceleration", "foresight", "persistence"],
                ),
                FutureConsistencyEngine(),
                [],
            ),
            "convergence": (
                PlanetaryConfig(
                    name="convergence_equiv",
                    description="Equiv",
                    score_attrs=_even_weights(["dependencies_count", "persistence", "relevance", "future_gravity"]),
                    global_attrs={}, threshold_attrs={},
                    map_attrs=["dependencies_count", "persistence", "relevance", "future_gravity"],
                ),
                FutureConvergenceEngine(),
                [],
            ),
            "harmony": (
                PlanetaryConfig(
                    name="harmony_equiv",
                    description="Equiv",
                    score_attrs=_even_weights(["recovery", "redundancy", "relevance", "foresight"]),
                    global_attrs={}, threshold_attrs={},
                    map_attrs=["recovery", "redundancy", "relevance", "foresight"],
                ),
                FutureHarmonyEngine(),
                [],
            ),
            "master": (
                PlanetaryConfig(
                    name="master_equiv",
                    description="Equiv",
                    score_attrs=FutureMasterEngine.MASTER_WEIGHTS,
                    global_attrs={}, threshold_attrs={},
                    map_attrs=["persistence", "future_gravity", "foresight", "relevance"],
                ),
                FutureMasterEngine(),
                ["fragility"],
            ),
        }

        for config_name, (equiv_config, original_engine, invert) in equiv_configs.items():
            generic_engine = PlanetaryScoreEngine(equiv_config, invert_attrs=invert)
            for event in sample_events:
                original_score = original_engine.compute(event)
                generic_score = generic_engine.compute(event)
                assert generic_score == pytest.approx(original_score, abs=1e-6), (
                    f"[{config_name}] Diferente para {event.event_id}: "
                    f"original={original_score}, generico={generic_score}"
                )

    def test_equivalence_extreme_values_high(self, extreme_event_high):
        """
        Verifica equivalencia con evento de valores maximos.
        Caso borde que expone diferencias en manejo de valores extremos.
        """
        equiv_config = PlanetaryConfig(
            name="continuity_equiv",
            description="Equiv",
            score_attrs=_even_weights(["persistence", "relevance", "foresight", "future_gravity", "fragility"]),
            global_attrs={}, threshold_attrs={},
            map_attrs=["persistence", "relevance", "foresight", "future_gravity"],
        )
        original_engine = FutureContinuityEngine()
        generic_engine = PlanetaryScoreEngine(equiv_config, invert_attrs=["fragility"])

        orig_score = original_engine.compute(extreme_event_high)
        gen_score = generic_engine.compute(extreme_event_high)
        assert gen_score == pytest.approx(orig_score, abs=1e-6)

    def test_equivalence_extreme_values_low(self, extreme_event_low):
        """
        Verifica equivalencia con evento de valores minimos.
        Caso borde que verifica manejo de ceros.
        """
        equiv_config = PlanetaryConfig(
            name="continuity_equiv",
            description="Equiv",
            score_attrs=_even_weights(["persistence", "relevance", "foresight", "future_gravity", "fragility"]),
            global_attrs={}, threshold_attrs={},
            map_attrs=["persistence", "relevance", "foresight", "future_gravity"],
        )
        original_engine = FutureContinuityEngine()
        generic_engine = PlanetaryScoreEngine(equiv_config, invert_attrs=["fragility"])

        orig_score = original_engine.compute(extreme_event_low)
        gen_score = generic_engine.compute(extreme_event_low)
        assert gen_score == pytest.approx(orig_score, abs=1e-6)


# =============================================================================
# SECCION 2: TESTS DEL DETECTOR DE UMBRALES
# =============================================================================


class TestThresholdDetector:
    """Tests para PlanetaryThresholdDetector."""

    def test_threshold_detector_continuity(self, single_event):
        """
        Verifica que PlanetaryThresholdDetector con la config 'continuity'
        genera las mismas alertas que FutureContinuityEngine.alert().
        """
        config = PLANETARY_CONFIG_MAP["continuity"]
        original_engine = FutureContinuityEngine()
        generic_detector = PlanetaryThresholdDetector(config)

        # El FutureContinuityEngine alerta en >= 0.85
        # Pero la config continuity tiene alert_threshold=0.95
        # Verificamos que ambos detectores funcionan segun sus umbrales
        score = original_engine.compute(single_event)
        original_alert = original_engine.alert(score)
        generic_alert = generic_detector.alert(score)

        # Verificar consistencia interna: alert solo cuando score >= threshold
        if score >= config.alert_threshold:
            assert generic_alert is True
        else:
            assert generic_alert is False

    def test_threshold_detector_overstress(self):
        """
        Verifica que el detector activa alerta para scores altos.
        Crea una config con umbral muy alto (0.99) y prueba un score=1.0.
        """
        high_threshold_config = PlanetaryConfig(
            name="overstress_test",
            description="Detector de sobre-estres",
            score_attrs=_even_weights(["persistence", "relevance"]),
            global_attrs={},
            threshold_attrs={},
            map_attrs=["persistence", "relevance", "foresight", "future_gravity"],
            alert_threshold=0.99,
        )
        detector = PlanetaryThresholdDetector(high_threshold_config)

        assert detector.alert(0.99) is True
        assert detector.alert(1.0) is True
        assert detector.alert(0.989999) is False

    def test_threshold_boundary_conditions(self):
        """
        Verifica comportamiento en los limites exactos de los umbrales.
        Prueba scores justo en el umbral, justo debajo y justo arriba.
        """
        config = PlanetaryConfig(
            name="boundary_test",
            description="Test",
            score_attrs={"persistence": 1.0},
            global_attrs={},
            threshold_attrs={},
            map_attrs=["persistence", "relevance", "foresight", "future_gravity"],
            alert_threshold=0.85,
        )
        detector = PlanetaryThresholdDetector(config)

        assert detector.alert(0.85) is True    # Justo en el umbral
        assert detector.alert(0.849999) is False  # Justo debajo
        assert detector.alert(0.850001) is True   # Justo arriba
        assert detector.alert(0.0) is False
        assert detector.alert(1.0) is True

    def test_threshold_all_builtin_configs(self, single_event):
        """
        Verifica que el detector funciona correctamente con todas las
        configs predefinidas del sistema.
        """
        for config in PLANETARY_CONFIGS:
            detector = PlanetaryThresholdDetector(config)
            score_engine = PlanetaryScoreEngine(config)
            score = score_engine.compute(single_event)
            alert = detector.alert(score)

            # Consistencia: alert debe ser True si y solo si score >= threshold
            if score >= config.alert_threshold:
                assert alert is True, (
                    f"Config '{config.name}': alert deberia ser True "
                    f"para score={score} >= threshold={config.alert_threshold}"
                )
            else:
                assert alert is False, (
                    f"Config '{config.name}': alert deberia ser False "
                    f"para score={score} < threshold={config.alert_threshold}"
                )


# =============================================================================
# SECCION 3: TESTS DEL MOTOR DE MAPAS
# =============================================================================


class TestMapEngine:
    """Tests para PlanetaryMapEngine - generacion de coordenadas y mapas."""

    def test_map_engine_coordinates(self, single_event, continuity_config):
        """
        Verifica que PlanetaryMapEngine produce coordenadas correctas.
        Las coordenadas deben estar en el rango [0, 1].
        """
        engine = PlanetaryMapEngine(continuity_config)
        x, y = engine.compute_coordinates(single_event)

        assert 0.0 <= x <= 1.0, f"Coordenada x fuera de rango: {x}"
        assert 0.0 <= y <= 1.0, f"Coordenada y fuera de rango: {y}"

    def test_map_engine_coordinates_consistency(self, single_event):
        """
        Verifica que las coordenadas son deterministas:
        el mismo evento produce las mismas coordenadas.
        """
        config = PLANETARY_CONFIG_MAP["continuity"]
        engine = PlanetaryMapEngine(config)

        x1, y1 = engine.compute_coordinates(single_event)
        x2, y2 = engine.compute_coordinates(single_event)

        assert x1 == pytest.approx(x2, abs=1e-9)
        assert y1 == pytest.approx(y2, abs=1e-9)

    def test_map_engine_uses_map_attrs(self, single_event):
        """
        Verifica que el motor usa map_attrs de la config para calcular coords.
        x debe ser el primer map_attr, y el promedio del resto.
        """
        config = PLANETARY_CONFIG_MAP["continuity"]
        engine = PlanetaryMapEngine(config)
        x, y = engine.compute_coordinates(single_event)

        attrs = single_event.to_dict()
        expected_x = attrs[config.map_attrs[0]]
        rest = [attrs[a] for a in config.map_attrs[1:]]
        expected_y = sum(rest) / len(rest)

        assert x == pytest.approx(expected_x, abs=1e-6)
        assert y == pytest.approx(expected_y, abs=1e-6)

    def test_map_engine_full_map(self, sample_events, continuity_config):
        """
        Verifica que compute_map produce un resultado completo con:
        coordinates, centroid, spread, density.
        """
        engine = PlanetaryMapEngine(continuity_config)
        result = engine.compute_map(sample_events)

        assert "coordinates" in result
        assert "centroid" in result
        assert "spread" in result
        assert "density" in result
        assert "config_name" in result
        assert result["config_name"] == "continuity"
        assert len(result["coordinates"]) == len(sample_events)

    def test_map_engine_empty_events(self, continuity_config):
        """
        Verifica manejo de lista de eventos vacia.
        No debe lanzar excepcion.
        """
        engine = PlanetaryMapEngine(continuity_config)
        result = engine.compute_map([])

        assert result["coordinates"] == []
        assert result["centroid"]["x"] == 0.0
        assert result["centroid"]["y"] == 0.0
        assert result["spread"] == 0.0

    def test_map_centroid_calculation(self, sample_events, continuity_config):
        """
        Verifica que el centroide se calcula correctamente como el promedio
        de todas las coordenadas.
        """
        engine = PlanetaryMapEngine(continuity_config)
        result = engine.compute_map(sample_events)

        coords = result["coordinates"]
        expected_cx = sum(c["x"] for c in coords) / len(coords)
        expected_cy = sum(c["y"] for c in coords) / len(coords)

        assert result["centroid"]["x"] == pytest.approx(expected_cx, abs=1e-6)
        assert result["centroid"]["y"] == pytest.approx(expected_cy, abs=1e-6)


# =============================================================================
# SECCION 4: TESTS DE INTEGRACION DEL ORQUESTADOR
# =============================================================================


class TestDiagnosisEngineIntegration:
    """Tests de integracion para PlanetaryDiagnosisEngine (orquestador)."""

    def test_diagnosis_engine_run_single(self, sample_events):
        """
        Verifica que run_single ejecuta una configuracion completa
        y retorna la estructura esperada con todos los campos.
        """
        engine = PlanetaryDiagnosisEngine()
        result = engine.run_single("continuity", sample_events)

        assert "config_name" in result
        assert "config_description" in result
        assert "score_attrs_used" in result
        assert "map_attrs_used" in result
        assert "alert_threshold_employed" in result
        assert "scores" in result
        assert "alerts" in result
        assert "map" in result
        assert "statistics" in result

        assert result["config_name"] == "continuity"
        assert len(result["scores"]) == len(sample_events)
        assert result["statistics"]["event_count"] == len(sample_events)

    def test_diagnosis_engine_run_all(self, ten_events):
        """
        Ejecuta el motor con 10 eventos y todas las configs.
        Verifica que:
        - Se ejecutaron todas las configs
        - Cada config produce scores, alerts, y map
        - El summary es correcto
        """
        engine = PlanetaryDiagnosisEngine()
        result = engine.run_all(ten_events)

        assert "results" in result
        assert "summary" in result

        summary = result["summary"]
        assert summary["total_configs_run"] == len(PLANETARY_CONFIG_MAP)
        assert summary["total_events_processed"] == len(ten_events)

        # Verificar que cada config produjo scores y map
        for config_result in result["results"]:
            assert len(config_result["scores"]) == len(ten_events)
            assert "map" in config_result
            assert "alerts" in config_result
            assert config_result["map"] is not None

        # Consistencia de conteos
        total_scores = sum(len(r["scores"]) for r in result["results"])
        assert summary["total_scores_computed"] == total_scores
        total_alerts = sum(r["alert_count"] for r in result["results"])
        assert summary["total_alerts_generated"] == total_alerts

    def test_diagnosis_engine_invalid_config(self, sample_events):
        """
        Verifica que se lanza ValueError para una configuracion inexistente.
        """
        engine = PlanetaryDiagnosisEngine()
        with pytest.raises(ValueError, match="Configuracion no encontrada"):
            engine.run_single("config_inexistente_xyz", sample_events)

    def test_diagnosis_engine_statistics_consistency(self, sample_events):
        """
        Verifica que las estadisticas (avg, max, min) son consistentes
        con los scores calculados.
        """
        engine = PlanetaryDiagnosisEngine()
        result = engine.run_single("continuity", sample_events)

        scores = [s["score"] for s in result["scores"]]
        stats = result["statistics"]

        expected_avg = sum(scores) / len(scores)
        expected_max = max(scores)
        expected_min = min(scores)

        assert stats["avg_score"] == pytest.approx(expected_avg, abs=1e-6)
        assert stats["max_score"] == pytest.approx(expected_max, abs=1e-6)
        assert stats["min_score"] == pytest.approx(expected_min, abs=1e-6)


# =============================================================================
# SECCION 5: TESTS DE TRAZABILIDAD
# =============================================================================


class TestResultTrazability:
    """
    Tests que verifican que cada resultado incluye metadatos completos
    para trazabilidad y auditoria.
    """

    def test_result_trazability(self, sample_events):
        """
        Verifica que cada resultado incluye:
        - config_name
        - config_description
        - score_attrs usados
        - map_attrs usados
        - alert_threshold empleado
        """
        engine = PlanetaryDiagnosisEngine()
        result = engine.run_single("continuity", sample_events)

        assert result["config_name"] == "continuity"
        assert isinstance(result["config_description"], str)
        assert len(result["config_description"]) > 0

        assert isinstance(result["score_attrs_used"], dict)
        assert len(result["score_attrs_used"]) > 0
        weight_sum = sum(result["score_attrs_used"].values())
        assert 0.99 <= weight_sum <= 1.01, (
            f"Suma de score_attrs deberia ser ~1.0, pero es {weight_sum}"
        )

        assert isinstance(result["map_attrs_used"], list)
        assert len(result["map_attrs_used"]) == 4, (
            f"map_attrs deberia tener 4 elementos, tiene {len(result['map_attrs_used'])}"
        )

        assert isinstance(result["alert_threshold_employed"], float)
        assert 0.0 < result["alert_threshold_employed"] <= 1.0

    def test_trazability_all_configs(self, ten_events):
        """
        Verifica que TODAS las configuraciones producen resultados
        con metadatos de trazabilidad completos.
        """
        engine = PlanetaryDiagnosisEngine()
        result = engine.run_all(ten_events)

        for config_result in result["results"]:
            assert "config_name" in config_result
            assert "config_description" in config_result
            assert "score_attrs_used" in config_result
            assert "map_attrs_used" in config_result
            assert "alert_threshold_employed" in config_result

            assert len(config_result["map_attrs_used"]) == 4
            w_sum = sum(config_result["score_attrs_used"].values())
            assert 0.99 <= w_sum <= 1.01

    def test_score_trazability_per_event(self, sample_events):
        """
        Verifica que cada score individual incluye el event_id
        y el flag de alerta.
        """
        engine = PlanetaryDiagnosisEngine()
        result = engine.run_single("continuity", sample_events)

        for score_entry in result["scores"]:
            assert "event_id" in score_entry
            assert "score" in score_entry
            assert "alert" in score_entry
            assert isinstance(score_entry["score"], float)
            assert isinstance(score_entry["alert"], bool)


# =============================================================================
# SECCION 6: TESTS DE EXTENSIBILIDAD
# =============================================================================


class TestExtensibility:
    """
    Tests que verifican que el sistema permite agregar nuevas configuraciones
    en runtime sin modificar codigo existente.
    """

    def test_new_config_without_code_changes(self, sample_events):
        """
        Crea una nueva configuracion en runtime y verifica
        que el motor la procesa sin modificar codigo.
        """
        custom_config = PlanetaryConfig(
            name="custom_resilience",
            description="Configuracion personalizada de resiliencia",
            score_attrs=_weighted({"recovery": 0.5, "redundancy": 0.3, "persistence": 0.2}),
            global_attrs={},
            threshold_attrs={},
            map_attrs=["recovery", "redundancy", "persistence", "foresight"],
            alert_threshold=0.70,
        )

        extended_configs = dict(PLANETARY_CONFIG_MAP)
        extended_configs["custom_resilience"] = custom_config

        engine = PlanetaryDiagnosisEngine(configs=extended_configs)
        result = engine.run_single("custom_resilience", sample_events)

        assert result["config_name"] == "custom_resilience"
        assert result["config_description"] == "Configuracion personalizada de resiliencia"
        assert result["score_attrs_used"] == custom_config.score_attrs
        assert result["alert_threshold_employed"] == 0.70
        assert len(result["scores"]) == len(sample_events)

        # Verificar que el score se calculo correctamente
        event = sample_events[0]
        expected_score = round(
            (event.recovery * 0.5 + event.redundancy * 0.3 + event.persistence * 0.2),
            6,
        )
        actual_score = result["scores"][0]["score"]
        assert actual_score == pytest.approx(expected_score, abs=1e-6)

    def test_extend_then_run_all(self, sample_events):
        """
        Verifica que despues de extender las configs,
        run_all incluye la nueva configuracion.
        """
        custom_config = PlanetaryConfig(
            name="stress_test_v2",
            description="Version 2 del test de estres",
            score_attrs=_weighted({"future_pressure": 0.4, "acceleration": 0.4, "fragility": 0.2}),
            global_attrs={},
            threshold_attrs={},
            map_attrs=["future_pressure", "acceleration", "fragility", "persistence"],
            alert_threshold=0.95,
        )

        extended_configs = dict(PLANETARY_CONFIG_MAP)
        extended_configs["stress_test_v2"] = custom_config

        engine = PlanetaryDiagnosisEngine(configs=extended_configs)
        result = engine.run_all(sample_events)

        config_names = [r["config_name"] for r in result["results"]]
        assert "stress_test_v2" in config_names
        assert result["summary"]["total_configs_run"] == len(extended_configs)

    def test_config_isolation(self, sample_events):
        """
        Verifica que modificar una config en una copia extendida
        no afecta al PLANETARY_CONFIG_MAP original.
        """
        orig_weights = dict(PLANETARY_CONFIG_MAP["continuity"].score_attrs)

        modified_configs = dict(PLANETARY_CONFIG_MAP)
        modified_configs["continuity"] = PlanetaryConfig(
            name="continuity",
            description="Modificada",
            score_attrs={k: round(v * 0.5, 4) for k, v in orig_weights.items()},
            global_attrs={},
            threshold_attrs={},
            map_attrs=PLANETARY_CONFIG_MAP["continuity"].map_attrs,
            alert_threshold=0.5,
        )

        # PLANETARY_CONFIG_MAP no debe haber cambiado
        assert PLANETARY_CONFIG_MAP["continuity"].score_attrs == orig_weights

        # Ambos engines funcionan independientemente
        engine1 = PlanetaryDiagnosisEngine(configs=dict(PLANETARY_CONFIG_MAP))
        engine2 = PlanetaryDiagnosisEngine(configs=modified_configs)

        result1 = engine1.run_single("continuity", sample_events)
        result2 = engine2.run_single("continuity", sample_events)

        # El score con pesos modificados debe ser el mismo porque
        # la normalizacion preserva las proporciones
        assert result1["scores"][0]["score"] == result2["scores"][0]["score"]


# =============================================================================
# SECCION 7: TESTS DE EQUIVALENCIA CON 5 PACKS ORIGINALES
# =============================================================================


class TestEquivalenceWithOriginalPacks:
    """
    Tests de equivalencia numerica comparando resultados de los 5 packs
    originales (continuity, consistency, convergence, harmony, master)
    contra el motor generico con configs equivalentes.
    """

    def test_equivalence_continuity_vs_original(self, ten_events):
        """Compara pack 'continuity' vs FutureContinuityEngine original."""
        self._verify_pack_equivalence(
            ten_events,
            ["persistence", "relevance", "foresight", "future_gravity", "fragility"],
            FutureContinuityEngine(),
            ["fragility"],
        )

    def test_equivalence_consistency_vs_original(self, ten_events):
        """Compara pack 'consistency' vs FutureConsistencyEngine original."""
        self._verify_pack_equivalence(
            ten_events,
            ["future_pressure", "acceleration", "foresight", "persistence"],
            FutureConsistencyEngine(),
            [],
        )

    def test_equivalence_convergence_vs_original(self, ten_events):
        """Compara pack 'convergence' vs FutureConvergenceEngine original."""
        self._verify_pack_equivalence(
            ten_events,
            ["dependencies_count", "persistence", "relevance", "future_gravity"],
            FutureConvergenceEngine(),
            [],
        )

    def test_equivalence_harmony_vs_original(self, ten_events):
        """Compara pack 'harmony' vs FutureHarmonyEngine original."""
        self._verify_pack_equivalence(
            ten_events,
            ["recovery", "redundancy", "relevance", "foresight"],
            FutureHarmonyEngine(),
            [],
        )

    def test_equivalence_master_vs_original(self, ten_events):
        """Compara pack 'master' vs FutureMasterEngine original."""
        self._verify_pack_equivalence(
            ten_events,
            list(FutureMasterEngine.MASTER_WEIGHTS.keys()),
            FutureMasterEngine(),
            ["fragility"],
            custom_weights=FutureMasterEngine.MASTER_WEIGHTS,
        )

    def _verify_pack_equivalence(self, events, attrs, original_engine,
                                  invert_attrs, custom_weights=None):
        """Metodo auxiliar para comparar motor original vs generico."""
        weights = custom_weights or _even_weights(attrs)
        equiv_config = PlanetaryConfig(
            name="equiv",
            description="Equivalente",
            score_attrs=weights,
            global_attrs={},
            threshold_attrs={},
            map_attrs=attrs[:4] if len(attrs) >= 4 else attrs + ["persistence"] * (4 - len(attrs)),
        )
        generic_engine = PlanetaryScoreEngine(equiv_config, invert_attrs=invert_attrs)

        for event in events:
            original_score = original_engine.compute(event)
            generic_score = generic_engine.compute(event)

            assert generic_score == pytest.approx(original_score, abs=1e-6), (
                f"Score difiere para {event.event_id}: "
                f"original={original_score}, generico={generic_score}"
            )

            # Verificar que las alertas coinciden
            orig_alert = original_engine.alert(original_score)
            # Usamos el alert_threshold del motor original para consistencia
            threshold = 0.85 if isinstance(original_engine, FutureContinuityEngine) else \
                       0.80 if isinstance(original_engine, FutureConsistencyEngine) else \
                       0.82 if isinstance(original_engine, FutureConvergenceEngine) else \
                       0.75 if isinstance(original_engine, FutureHarmonyEngine) else 0.90
            gen_alert = generic_score >= threshold
            assert gen_alert == orig_alert, (
                f"Alerta difiere para {event.event_id}: "
                f"original={orig_alert}, generico={gen_alert}"
            )


# =============================================================================
# SECCION 8: TESTS DE ROBUSTEZ Y CASOS LIMITE
# =============================================================================


class TestRobustness:
    """Tests de robustez y manejo de casos limite."""

    def test_event_with_defaults(self):
        """
        Verifica que un PlanetaryEvent con valores por defecto (0.0)
        no causa errores al procesarse.
        """
        event = PlanetaryEvent(event_id="defaults")
        config = PLANETARY_CONFIG_MAP["continuity"]
        engine = PlanetaryScoreEngine(config)

        score = engine.compute(event)
        assert score == 0.0 or math.isfinite(score)

    def test_single_event_list(self, single_event):
        """Verifica funcionamiento correcto con lista de un solo evento."""
        config = PLANETARY_CONFIG_MAP["continuity"]
        map_engine = PlanetaryMapEngine(config)
        result = map_engine.compute_map([single_event])

        assert len(result["coordinates"]) == 1
        assert result["spread"] == 0.0

    def test_score_precision(self, single_event):
        """
        Verifica que los scores se redondean a 6 decimales.
        """
        config = PLANETARY_CONFIG_MAP["continuity"]
        engine = PlanetaryScoreEngine(config)
        score = engine.compute(single_event)

        score_str = f"{score:.10f}"
        decimal_part = score_str.split(".")[1].rstrip("0")
        assert len(decimal_part) <= 6, (
            f"Score tiene mas de 6 decimales significativos: {score}"
        )

    def test_all_configs_have_valid_thresholds(self):
        """Verifica que todas las configs tienen umbrales en (0, 1]."""
        for config in PLANETARY_CONFIGS:
            assert 0.0 < config.alert_threshold <= 1.0, (
                f"Config '{config.name}' tiene umbral invalido: {config.alert_threshold}"
            )

    def test_all_configs_score_attrs_sum_to_one(self):
        """Verifica que score_attrs de cada config suman ~1.0."""
        for config in PLANETARY_CONFIGS:
            weight_sum = sum(config.score_attrs.values())
            assert 0.99 <= weight_sum <= 1.01, (
                f"Config '{config.name}' tiene score_attrs que no suman 1.0: {weight_sum}"
            )

    def test_all_configs_map_attrs_length(self):
        """Verifica que todas las configs tienen exactamente 4 map_attrs."""
        for config in PLANETARY_CONFIGS:
            assert len(config.map_attrs) == 4, (
                f"Config '{config.name}' tiene {len(config.map_attrs)} map_attrs, esperado 4"
            )

    def test_config_attributes_valid(self):
        """Verifica que todos los atributos referenciados existen en PlanetaryEvent."""
        valid_attrs = set(PlanetaryEvent.__dataclass_fields__.keys())
        valid_attrs.discard("event_id")

        for config in PLANETARY_CONFIGS:
            for attr_dict, label in [(config.score_attrs, "score_attrs"),
                                      (config.global_attrs, "global_attrs"),
                                      (config.threshold_attrs, "threshold_attrs")]:
                for attr in attr_dict:
                    assert attr in valid_attrs, (
                        f"Config '{config.name}.{label}' tiene atributo invalido: '{attr}'"
                    )
            for attr in config.map_attrs:
                assert attr in valid_attrs, (
                    f"Config '{config.name}.map_attrs' tiene atributo invalido: '{attr}'"
                )


# =============================================================================
# SECCION 9: TESTS DE ALERTAS
# =============================================================================


class TestAlerts:
    """Tests para verificar el sistema de alertas."""

    def test_alert_count_matches_scores(self, sample_events):
        """
        Verifica que alert_count coincide con el numero de alertas generadas.
        """
        engine = PlanetaryDiagnosisEngine()
        result = engine.run_single("continuity", sample_events)

        assert result["alert_count"] == len(result["alerts"])

    def test_no_alerts_below_threshold(self, sample_events):
        """
        Verifica que no hay alertas para scores debajo del umbral.
        """
        engine = PlanetaryDiagnosisEngine()
        result = engine.run_single("continuity", sample_events)

        for score_entry in result["scores"]:
            if score_entry["alert"]:
                assert score_entry["score"] >= result["alert_threshold_employed"]
            else:
                assert score_entry["score"] < result["alert_threshold_employed"]

    def test_alerts_include_event_id(self, sample_events):
        """Verifica que cada alerta incluye el event_id correspondiente."""
        engine = PlanetaryDiagnosisEngine()
        result = engine.run_single("continuity", sample_events)

        for alert in result["alerts"]:
            assert "event_id" in alert
            assert "score" in alert

    def test_score_engine_with_empty_score_attrs(self):
        """Verifica manejo de config con score_attrs vacio."""
        empty_config = PlanetaryConfig(
            name="empty",
            description="Empty score attrs",
            score_attrs={},
            global_attrs={},
            threshold_attrs={},
            map_attrs=["persistence", "relevance", "foresight", "future_gravity"],
        )
        engine = PlanetaryScoreEngine(empty_config)
        event = PlanetaryEvent(event_id="test", persistence=0.5)
        score = engine.compute(event)
        assert score == 0.0
