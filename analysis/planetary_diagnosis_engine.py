"""
Motor de Diagnostico Planetario - Implementacion generica + motores originales.

Este modulo contiene:
1. PlanetaryEvent - dataclass para eventos de entrada
2. Motores originales individuales (FutureContinuityEngine, etc.)
3. Motor generico configurable (PlanetaryScoreEngine, PlanetaryThresholdDetector, PlanetaryMapEngine)
4. Orquestador principal (PlanetaryDiagnosisEngine)

El motor generico consume configuraciones PlanetaryConfig que definen:
- score_attrs: atributos y pesos para calcular scores
- global_attrs: atributos para score global
- threshold_attrs: atributos para deteccion de umbrales
- map_attrs: 4 atributos para mapeo espacial
- alert_threshold: umbral que activa alertas
"""

import math
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple

from analysis.planetary_configs import PLANETARY_CONFIGS, PLANETARY_CONFIG_MAP, PlanetaryConfig


# =============================================================================
# DATACLASS: PlanetaryEvent
# =============================================================================

@dataclass
class PlanetaryEvent:
    """
    Evento planetario con todos los atributos necesarios para el diagnostico.
    
    Attributes:
        event_id: Identificador unico del evento
        persistence: [0-1] Capacidad de persistencia temporal
        relevance: [0-1] Relevancia del evento
        foresight: [0-1] Capacidad de anticipacion
        future_gravity: [0-1] Gravedad futura proyectada
        fragility: [0-1] Fragilidad del sistema (mayor = mas fragil)
        future_pressure: [0-1] Presion futura esperada
        acceleration: [0-1] Tasa de aceleracion del evento
        dependencies_count: [0-1] Nivel de dependencias
        recovery: [0-1] Capacidad de recuperacion
        redundancy: [0-1] Nivel de redundancia
    """
    event_id: str
    persistence: float = 0.0
    relevance: float = 0.0
    foresight: float = 0.0
    future_gravity: float = 0.0
    fragility: float = 0.0
    future_pressure: float = 0.0
    acceleration: float = 0.0
    dependencies_count: float = 0.0
    recovery: float = 0.0
    redundancy: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        """Convierte el evento a diccionario de atributos numericos."""
        return {
            "persistence": self.persistence,
            "relevance": self.relevance,
            "foresight": self.foresight,
            "future_gravity": self.future_gravity,
            "fragility": self.fragility,
            "future_pressure": self.future_pressure,
            "acceleration": self.acceleration,
            "dependencies_count": self.dependencies_count,
            "recovery": self.recovery,
            "redundancy": self.redundancy,
        }


# =============================================================================
# MOTORES ORIGINALES (implementaciones de referencia)
# =============================================================================

class FutureContinuityEngine:
    """
    MOTOR ORIGINAL - Continuidad Futura.
    
    Formula: (persistence + relevance + foresight + future_gravity + (1 - fragility)) / 5
    """
    
    def compute(self, event: PlanetaryEvent) -> float:
        """Calcula el score de continuidad futura."""
        score = (
            event.persistence
            + event.relevance
            + event.foresight
            + event.future_gravity
            + (1.0 - event.fragility)
        ) / 5.0
        return round(score, 6)

    def alert(self, score: float) -> bool:
        """Genera alerta si el score supera el umbral."""
        return score >= 0.85


class FutureConsistencyEngine:
    """
    MOTOR ORIGINAL - Consistencia de Presion Futura.
    
    Formula: (future_pressure + acceleration + foresight + persistence) / 4
    """
    
    def compute(self, event: PlanetaryEvent) -> float:
        """Calcula el score de consistencia."""
        score = (
            event.future_pressure
            + event.acceleration
            + event.foresight
            + event.persistence
        ) / 4.0
        return round(score, 6)

    def alert(self, score: float) -> bool:
        """Genera alerta si el score supera el umbral."""
        return score >= 0.80


class FutureConvergenceEngine:
    """
    MOTOR ORIGINAL - Convergencia de Dependencias.
    
    Formula: (dependencies_count + persistence + relevance + future_gravity) / 4
    """
    
    def compute(self, event: PlanetaryEvent) -> float:
        """Calcula el score de convergencia."""
        score = (
            event.dependencies_count
            + event.persistence
            + event.relevance
            + event.future_gravity
        ) / 4.0
        return round(score, 6)

    def alert(self, score: float) -> bool:
        """Genera alerta si el score supera el umbral."""
        return score >= 0.82


class FutureHarmonyEngine:
    """
    MOTOR ORIGINAL - Armonia de Resiliencia.
    
    Formula: (recovery + redundancy + relevance + foresight) / 4
    """
    
    def compute(self, event: PlanetaryEvent) -> float:
        """Calcula el score de armonia."""
        score = (
            event.recovery
            + event.redundancy
            + event.relevance
            + event.foresight
        ) / 4.0
        return round(score, 6)

    def alert(self, score: float) -> bool:
        """Genera alerta si el score supera el umbral."""
        return score >= 0.75


class FutureMasterEngine:
    """
    MOTOR ORIGINAL - Evaluacion Maestra.
    
    Formula: promedio ponderado de todos los atributos
             con mayor peso en persistence, future_gravity y foresight,
             e invirtiendo fragility.
    """
    
    MASTER_WEIGHTS = {
        "persistence": 0.15,
        "relevance": 0.10,
        "foresight": 0.15,
        "future_gravity": 0.15,
        "fragility": 0.08,
        "future_pressure": 0.10,
        "acceleration": 0.08,
        "dependencies_count": 0.07,
        "recovery": 0.07,
        "redundancy": 0.05,
    }

    def compute(self, event: PlanetaryEvent) -> float:
        """Calcula el score maestro ponderado."""
        attrs = event.to_dict()
        total = 0.0
        weight_sum = 0.0
        for attr, weight in self.MASTER_WEIGHTS.items():
            value = attrs[attr]
            if attr == "fragility":
                value = 1.0 - value
            total += value * weight
            weight_sum += weight
        score = total / weight_sum if weight_sum > 0 else 0.0
        return round(score, 6)

    def alert(self, score: float) -> bool:
        """Genera alerta si el score supera el umbral."""
        return score >= 0.90


# =============================================================================
# MOTOR GENERICO CONFIGURABLE
# =============================================================================

class PlanetaryScoreEngine:
    """
    Motor generico de scoring planetario.
    
    Reproduce el comportamiento de cualquier motor original
    usando una configuracion PlanetaryConfig y sus score_attrs.
    
    Args:
        config: PlanetaryConfig con score_attrs definidos.
        invert_attrs: Lista opcional de nombres de atributos cuyo valor
                      debe ser invertido (1.0 - valor) antes de aplicar
                      el peso. Util para fragility donde mayor = peor.
    """
    
    def __init__(self, config: PlanetaryConfig, invert_attrs: Optional[List[str]] = None):
        self.config = config
        self.invert_attrs = set(invert_attrs or [])

    def compute(self, event: PlanetaryEvent) -> float:
        """
        Calcula el score usando score_attrs de la configuracion.
        
        score_attrs define los atributos y sus pesos para el calculo.
        El score es la suma ponderada normalizada por los pesos.
        Los atributos en invert_attrs se invierten (1.0 - valor).
        """
        attrs = event.to_dict()
        total = 0.0
        weight_sum = 0.0
        
        for attr, weight in self.config.score_attrs.items():
            value = attrs.get(attr, 0.0)
            # Invertir atributo si está configurado
            if attr in self.invert_attrs:
                value = 1.0 - value
            total += value * weight
            weight_sum += weight
        
        score = total / weight_sum if weight_sum > 0 else 0.0
        return round(score, 6)


class PlanetaryThresholdDetector:
    """
    Detector generico de umbrales.
    
    Usa alert_threshold de la configuracion para determinar
    si un score activa una alerta.
    """
    
    def __init__(self, config: PlanetaryConfig):
        self.config = config

    def alert(self, score: float) -> bool:
        """Retorna True si el score supera el umbral configurado."""
        return score >= self.config.alert_threshold

    def alert_message(self, score: Optional[float] = None) -> str:
        """Retorna el mensaje de alerta para esta configuracion."""
        score_str = f"{score:.4f}" if score is not None else "N/A"
        return (
            f"ALERTA [{self.config.name.upper()}]: "
            f"Score {score_str} supera umbral {self.config.alert_threshold} "
            f"- {self.config.description[:80]}"
        )


class PlanetaryMapEngine:
    """
    Motor de mapeo planetario - genera coordenadas y visualizacion.
    
    Usa los primeros 2 atributos de map_attrs como ejes x e y.
    """
    
    def __init__(self, config: PlanetaryConfig):
        self.config = config

    def compute_coordinates(self, event: PlanetaryEvent) -> Tuple[float, float]:
        """
        Calcula coordenadas (x, y) usando los primeros 2 map_attrs.
        
        x: valor del primer atributo en map_attrs
        y: promedio de los valores restantes en map_attrs
        
        Returns:
            Tupla (x, y) con coordenadas en [0, 1]
        """
        attrs = event.to_dict()
        map_attrs = self.config.map_attrs
        
        if not map_attrs:
            return (0.0, 0.0)
        
        x = attrs.get(map_attrs[0], 0.0)
        if len(map_attrs) > 1:
            y_values = [attrs.get(a, 0.0) for a in map_attrs[1:]]
            y = sum(y_values) / len(y_values)
        else:
            y = 0.0
        
        return (round(x, 6), round(y, 6))

    def compute_map(self, events: List[PlanetaryEvent]) -> Dict[str, Any]:
        """
        Genera un mapa completo con coordenadas para todos los eventos.
        
        Returns:
            Dict con 'coordinates', 'centroid', 'spread', 'density'
        """
        coordinates = []
        for event in events:
            x, y = self.compute_coordinates(event)
            coordinates.append({
                "event_id": event.event_id,
                "x": x,
                "y": y,
            })
        
        # Calcular centroide
        if coordinates:
            centroid_x = sum(c["x"] for c in coordinates) / len(coordinates)
            centroid_y = sum(c["y"] for c in coordinates) / len(coordinates)
        else:
            centroid_x, centroid_y = 0.0, 0.0
        
        # Calcular dispersion (spread)
        if len(coordinates) >= 2:
            spread = math.sqrt(
                sum((c["x"] - centroid_x) ** 2 + (c["y"] - centroid_y) ** 2 
                    for c in coordinates) / len(coordinates)
            )
        else:
            spread = 0.0
        
        # Calcular densidad
        density = len(coordinates) / (1 + spread)
        
        return {
            "config_name": self.config.name,
            "coordinates": coordinates,
            "centroid": {"x": round(centroid_x, 6), "y": round(centroid_y, 6)},
            "spread": round(spread, 6),
            "density": round(density, 6),
        }


# =============================================================================
# ORQUESTADOR PRINCIPAL
# =============================================================================

class PlanetaryDiagnosisEngine:
    """
    Orquestador principal de diagnostico planetario.
    
    Ejecuta multiples configuraciones sobre un conjunto de eventos
    y genera un reporte integral con scores, alertas y mapas.
    
    Las configs se pasan como diccionario {nombre: PlanetaryConfig}.
    Si no se pasan, usa PLANETARY_CONFIG_MAP (todas las 100 configs
    indexadas por nombre).
    """
    
    def __init__(self, configs: Optional[Dict[str, PlanetaryConfig]] = None):
        self.configs = configs or PLANETARY_CONFIG_MAP
        self.results: List[Dict[str, Any]] = []

    def run_single(
        self,
        config_name: str,
        events: List[PlanetaryEvent],
    ) -> Dict[str, Any]:
        """
        Ejecuta una sola configuracion sobre los eventos.
        
        Returns:
            Dict con scores, alerts, map y metadata de trazabilidad.
        """
        if config_name not in self.configs:
            raise ValueError(f"Configuracion no encontrada: {config_name}")
        
        config = self.configs[config_name]
        score_engine = PlanetaryScoreEngine(config)
        threshold_detector = PlanetaryThresholdDetector(config)
        map_engine = PlanetaryMapEngine(config)
        
        # Calcular scores
        scores = []
        for event in events:
            score = score_engine.compute(event)
            scores.append({
                "event_id": event.event_id,
                "score": score,
                "alert": threshold_detector.alert(score),
            })
        
        # Generar alertas
        alerts = [
            {
                "event_id": s["event_id"],
                "score": s["score"],
                "message": threshold_detector.alert_message(s["score"]),
            }
            for s in scores if s["alert"]
        ]
        
        # Generar mapa
        map_result = map_engine.compute_map(events)
        
        # Score promedio
        avg_score = sum(s["score"] for s in scores) / len(scores) if scores else 0.0
        max_score = max((s["score"] for s in scores), default=0.0)
        min_score = min((s["score"] for s in scores), default=0.0)
        
        return {
            "config_name": config.name,
            "config_description": config.description,
            "score_attrs_used": config.score_attrs,
            "map_attrs_used": config.map_attrs,
            "alert_threshold_employed": config.alert_threshold,
            "scores": scores,
            "alerts": alerts,
            "alert_count": len(alerts),
            "map": map_result,
            "statistics": {
                "avg_score": round(avg_score, 6),
                "max_score": round(max_score, 6),
                "min_score": round(min_score, 6),
                "event_count": len(events),
            },
        }

    def run_all(self, events: List[PlanetaryEvent]) -> Dict[str, Any]:
        """
        Ejecuta TODAS las configuraciones sobre los eventos.
        
        Returns:
            Dict con resultados por config y summary global.
        """
        results = []
        for config_name in self.configs:
            result = self.run_single(config_name, events)
            results.append(result)
        
        # Summary global
        total_alerts = sum(r["alert_count"] for r in results)
        total_scores = sum(
            len(r["scores"]) for r in results
        )
        configs_run = len(results)
        
        summary = {
            "total_configs_run": configs_run,
            "total_events_processed": len(events),
            "total_scores_computed": total_scores,
            "total_alerts_generated": total_alerts,
            "configs_run": [r["config_name"] for r in results],
        }
        
        return {
            "results": results,
            "summary": summary,
        }
