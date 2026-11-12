"""
================================================================================
ADAPTADOR GRAFO CAUSAL SIMPLE - VEO v2.0.5
================================================================================
Implementaciones ligeras del protocolo GrafoConocimiento y MotorCausal
para uso en simulacion de escenarios cuando no hay un grafo de conocimiento
global poblado.

Permite construir un grafo causal a partir de una hipotesis y sus variables
afectadas, ejecutando simulaciones Monte Carlo donde las relaciones causales
influyen efectivamente en los resultados.

Uso tipico:
    grafo = GrafoCausalSimple()
    grafo.agregar_nodo("variable_a")
    grafo.agregar_nodo("variable_b")
    grafo.agregar_relacion("variable_a", "variable_b", peso=0.8)
    motor = MotorCausalProporcional()
    sim = SimuladorEscenarios(grafo=grafo, motor_causal=motor)
================================================================================
"""

from typing import Dict, List, Optional, Any


class RelacionCausalSimple:
    """Relacion causal minima compatible con el protocolo del simulador."""

    def __init__(
        self,
        origen_id: str = "",
        destino_id: str = "",
        peso: float = 0.0,
        tipo: str = "directa",
    ) -> None:
        self.origen_id = origen_id
        self.destino_id = destino_id
        self.peso = peso
        self.tipo = tipo


class GrafoCausalSimple:
    """Grafo causal en memoria compatible con el protocolo del simulador.

    No requiere NetworkX ni SQLite.  Diseñado para construir grafos pequeños
    a partir de hipotesis con variables afectadas.
    """

    def __init__(self) -> None:
        self._nodos: Dict[str, dict] = {}
        self._relaciones: List[RelacionCausalSimple] = []
        self._relaciones_por_destino: Dict[str, List[RelacionCausalSimple]] = {}
        self._relaciones_por_origen: Dict[str, List[RelacionCausalSimple]] = {}

    def agregar_nodo(self, nodo_id: str, nombre: str = "", metadatos: Optional[dict] = None) -> None:
        """Agrega un nodo al grafo."""
        self._nodos[nodo_id] = {
            "id": nodo_id,
            "nombre": nombre or nodo_id,
            "metadatos": metadatos or {},
        }

    def agregar_relacion(
        self,
        origen_id: str,
        destino_id: str,
        peso: float = 1.0,
        tipo: str = "directa",
    ) -> None:
        """Agrega una relacion causal dirigida entre dos nodos."""
        rel = RelacionCausalSimple(origen_id, destino_id, peso, tipo)
        self._relaciones.append(rel)
        self._relaciones_por_destino.setdefault(destino_id, []).append(rel)
        self._relaciones_por_origen.setdefault(origen_id, []).append(rel)

    def obtener_nodo(self, nodo_id: str) -> Optional[dict]:
        return self._nodos.get(nodo_id)

    def obtener_relaciones_desde(self, nodo_id: str) -> List[RelacionCausalSimple]:
        return list(self._relaciones_por_origen.get(nodo_id, []))

    def obtener_relaciones_hacia(self, nodo_id: str) -> List[RelacionCausalSimple]:
        return list(self._relaciones_por_destino.get(nodo_id, []))

    def nodos_adyacentes(self, nodo_id: str) -> List[str]:
        """Devuelve nodos vecinos (destinos de relaciones salientes)."""
        return [r.destino_id for r in self._relaciones_por_origen.get(nodo_id, [])]

    def todos_los_nodos(self) -> List[str]:
        return list(self._nodos.keys())

    def obtener_relacion(self, origen: str, destino: str) -> Optional[RelacionCausalSimple]:
        for r in self._relaciones:
            if r.origen_id == origen and r.destino_id == destino:
                return r
        return None

    def conteo_nodos(self) -> int:
        return len(self._nodos)

    def conteo_relaciones(self) -> int:
        return len(self._relaciones)


class MotorCausalProporcional:
    """Motor causal que aplica el peso de la relacion a la magnitud.

    calcular_efecto = magnitud * peso_de_la_relacion

    Si no existe relacion explicita entre causa y efecto, devuelve la magnitud
    sin transformar (comportamiento identidad).
    """

    def __init__(self, grafo: Optional[Any] = None) -> None:
        self._grafo = grafo

    def calcular_efecto(self, causa_id: str, efecto_id: str, magnitud: float) -> float:
        """Calcula el efecto propagado multiplicando por el peso de la relacion."""
        if self._grafo is not None:
            rel = self._grafo.obtener_relacion(causa_id, efecto_id)
            if rel is not None:
                return float(magnitud * rel.peso)
        return float(magnitud)

    def evaluar_consistencia(self, asignaciones: Dict[str, float]) -> float:
        """Evalua consistencia como fraccion de valores no narios."""
        if not asignaciones:
            return 1.0
        no_cero = sum(1 for v in asignaciones.values() if v != 0.0)
        return no_cero / len(asignaciones)
