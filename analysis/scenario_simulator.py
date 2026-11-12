# -*- coding: utf-8 -*-
"""
================================================================================
VEO: Simulador de Escenarios What-If
================================================================================
Programa VEO (Vigilancia de Emergencias Observables).
Detecta que esta cambiando.

"VEO es una plataforma de inteligencia artificial cooperativa destinada a
detectar cambios emergentes en la realidad mediante el analisis continuo de
senales debiles, relaciones semanticas y conocimiento distribuido, generando
hipotesis explicables que ayuden a los analistas humanos a comprender sistemas
complejos bajo incertidumbre."

Este modulo implementa un motor de simulacion Monte Carlo para explorar
escenarios contrafactuales, analizar sensibilidad y propagar efectos a traves
de un grafo de conocimiento causal.

Dependencias: numpy, statistics (stdlib), datetime, json, typing
================================================================================
"""

from __future__ import annotations

import json
import statistics
from copy import deepcopy
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Tuple,
    Protocol,
    runtime_checkable,
)

import numpy as np

import logging
import sqlite3


# =============================================================================
# EXCEPCIONES CUSTOM
# =============================================================================

class SimuladorError(Exception):
    """Excepcion base para errores del simulador."""


class EscenarioNoEncontradoError(SimuladorError):
    """Se solicito un escenario que no existe en la base de datos."""


class VariablesInvalidasError(SimuladorError):
    """Las variables del escenario tienen configuraciones invalidas."""


class SimulacionError(SimuladorError):
    """Error durante la ejecucion de una simulacion."""


# =============================================================================
# ENUMERACIONES
# =============================================================================

class TipoDistribucion(str, Enum):
    """Tipos de distribucion de probabilidad soportados para el muestreo."""
    UNIFORME = "uniforme"
    NORMAL = "normal"
    TRIANGULAR = "triangular"
    LOGNORMAL = "lognormal"
    CONSTANTE = "constante"


class TipoEscenario(str, Enum):
    """Clasificacion de escenarios segun su proposito."""
    BASE = "base"
    OPTIMISTA = "optimista"
    PESIMISTA = "pesimista"
    CONTRAFACTUAL = "contrafactual"
    PEOR_CASO = "peor_caso"
    MEJOR_CASO = "mejor_caso"


# =============================================================================
# PROTOCOLOS (interfaces para inyeccion de dependencias)
# =============================================================================

@runtime_checkable
class NodoGrafo(Protocol):
    """Protocolo minimo para un nodo del grafo de conocimiento."""
    id: str
    nombre: str


@runtime_checkable
class RelacionCausal(Protocol):
    """Protocolo minimo para una relacion causal en el grafo."""
    origen_id: str
    destino_id: str
    peso: float
    tipo: str


@runtime_checkable
class GrafoConocimiento(Protocol):
    """Protocolo para el grafo de conocimiento causal."""

    def obtener_nodo(self, nodo_id: str) -> Optional[NodoGrafo]: ...
    def obtener_relaciones_desde(self, nodo_id: str) -> List[RelacionCausal]: ...
    def obtener_relaciones_hacia(self, nodo_id: str) -> List[RelacionCausal]: ...
    def nodos_adyacentes(self, nodo_id: str) -> List[str]: ...
    def todos_los_nodos(self) -> List[str]: ...
    def obtener_relacion(self, origen: str, destino: str) -> Optional[RelacionCausal]: ...


@runtime_checkable
class MotorCausal(Protocol):
    """Protocolo para el motor de inferencia causal."""

    def calcular_efecto(
        self,
        causa_id: str,
        efecto_id: str,
        magnitud: float
    ) -> float: ...

    def evaluar_consistencia(self, asignaciones: Dict[str, float]) -> float: ...


@runtime_checkable
class BaseDatos(Protocol):
    """Protocolo para la capa de persistencia."""

    def guardar(self, coleccion: str, datos: Dict[str, Any]) -> str: ...
    def buscar(self, coleccion: str, filtros: Dict[str, Any]) -> List[Dict[str, Any]]: ...
    def obtener_por_id(self, coleccion: str, doc_id: str) -> Optional[Dict[str, Any]]: ...
    def actualizar(self, coleccion: str, doc_id: str, datos: Dict[str, Any]) -> bool: ...


@runtime_checkable
class Logger(Protocol):
    """Protocolo para el sistema de logging."""

    def debug(self, mensaje: str) -> None: ...
    def info(self, mensaje: str) -> None: ...
    def warning(self, mensaje: str) -> None: ...
    def error(self, mensaje: str) -> None: ...


# =============================================================================
# IMPLEMENTACIONES POR DEFECTO (para instanciacion sin dependencias)
# =============================================================================

class _RelacionCausalSimple:
    """Relacion causal minima para uso interno de stubs."""

    def __init__(
        self,
        origen_id: str = "",
        destino_id: str = "",
        peso: float = 0.0,
        tipo: str = "",
    ) -> None:
        self.origen_id = origen_id
        self.destino_id = destino_id
        self.peso = peso
        self.tipo = tipo


class _GrafoConocimientoVacio:
    """Grafo de conocimiento vacio para instanciacion sin dependencias."""

    def obtener_nodo(self, nodo_id: str) -> Optional[Any]:
        return None

    def obtener_relaciones_desde(self, nodo_id: str) -> List[Any]:
        return []

    def obtener_relaciones_hacia(self, nodo_id: str) -> List[Any]:
        return []

    def nodos_adyacentes(self, nodo_id: str) -> List[str]:
        return []

    def todos_los_nodos(self) -> List[str]:
        return []

    def obtener_relacion(self, origen: str, destino: str) -> Optional[Any]:
        return None


class _MotorCausalIdentidad:
    """Motor causal que devuelve la magnitud sin transformacion."""

    def calcular_efecto(
        self,
        causa_id: str,
        efecto_id: str,
        magnitud: float,
    ) -> float:
        return magnitud

    def evaluar_consistencia(self, asignaciones: Dict[str, float]) -> float:
        return 1.0


class _BaseDatosMemoria:
    """Base de datos en memoria para instanciacion sin dependencias."""

    def __init__(self) -> None:
        self._datos: Dict[str, List[Dict[str, Any]]] = {}

    def guardar(self, coleccion: str, datos: Dict[str, Any]) -> str:
        self._datos.setdefault(coleccion, []).append(datos)
        return datos.get("id", "stub-id")

    def buscar(
        self,
        coleccion: str,
        filtros: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        return []

    def obtener_por_id(
        self,
        coleccion: str,
        doc_id: str,
    ) -> Optional[Dict[str, Any]]:
        return None

    def actualizar(
        self,
        coleccion: str,
        doc_id: str,
        datos: Dict[str, Any],
    ) -> bool:
        return True


class _LoggerNulo:
    """Logger que no emite nada (para instanciacion sin dependencias)."""

    def debug(self, mensaje: str) -> None:
        pass

    def info(self, mensaje: str) -> None:
        pass

    def warning(self, mensaje: str) -> None:
        pass

    def error(self, mensaje: str) -> None:
        pass


# =============================================================================
# ESTRUCTURAS DE DATOS
# =============================================================================

@dataclass
class VariableEscenario:
    """
    Variable configurable dentro de un escenario de simulacion.

    Cada variable representa un nodo del grafo de conocimiento que puede
    tomar valores aleatorios segun su distribucion de probabilidad.

    Atributos:
        nombre: Identificador unico de la variable (debe coincidir con nodo_id del grafo).
        valor_base: Valor central o de referencia.
        rango_min: Limite inferior del rango valido.
        rango_max: Limite superior del rango valido.
        distribucion: Tipo de distribucion para el muestreo Monte Carlo.
        descripcion: Explicacion humana de que representa la variable.
        metadata: Diccionario para parametros adicionales (ej: std_dev para normal).
    """
    nombre: str
    valor_base: float
    rango_min: float
    rango_max: float
    distribucion: TipoDistribucion = TipoDistribucion.UNIFORME
    descripcion: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validacion de consistencia de la variable."""
        if self.rango_min >= self.rango_max:
            raise VariablesInvalidasError(
                f"Variable '{self.nombre}': rango_min ({self.rango_min}) debe ser "
                f"menor que rango_max ({self.rango_max})"
            )
        if self.valor_base < self.rango_min or self.valor_base > self.rango_max:
            raise VariablesInvalidasError(
                f"Variable '{self.nombre}': valor_base ({self.valor_base}) fuera del "
                f"rango [{self.rango_min}, {self.rango_max}]"
            )
        if self.distribucion == TipoDistribucion.NORMAL:
            std = self.metadata.get("std_dev", 0.0)
            if std <= 0:
                raise VariablesInvalidasError(
                    f"Variable '{self.nombre}' tipo normal requiere std_dev > 0 en metadata"
                )


@dataclass
class MonteCarloRun:
    """
    Representa una unica corrida dentro de la simulacion Monte Carlo.

    Atributos:
        valores_muestreados: Diccionario {nombre_variable -> valor muestreado}.
        resultado: Valor escalar resultado de la propagacion.
        camino_activado: Lista de IDs de nodos activados durante la propagacion.
        timestamp: Instante de creacion de la corrida.
    """
    valores_muestreados: Dict[str, float]
    resultado: float
    camino_activado: List[str]
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Serializa la corrida a diccionario (JSON-friendly)."""
        return {
            "valores_muestreados": self.valores_muestreados,
            "resultado": self.resultado,
            "camino_activado": self.camino_activado,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class Hipotesis:
    """
    Hipotesis del sistema SOIS sobre un cambio emergente.

    Atributos:
        id: Identificador unico.
        nombre: Nombre descriptivo.
        descripcion: Enunciado de la hipotesis.
        variables_afectadas: Lista de nombres de variables relevantes.
        direccion_esperada: Direccion del efecto esperado ("aumento", "disminucion", "mixto").
        confianza: Nivel de confianza inicial [0.0, 1.0].
        evidencia: Evidencia que respalda la hipotesis.
    """
    id: str
    nombre: str
    descripcion: str
    variables_afectadas: List[str]
    direccion_esperada: str = "mixto"
    confianza: float = 0.5
    evidencia: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serializa la hipotesis a diccionario."""
        return {
            "id": self.id,
            "nombre": self.nombre,
            "descripcion": self.descripcion,
            "variables_afectadas": self.variables_afectadas,
            "direccion_esperada": self.direccion_esperada,
            "confianza": self.confianza,
            "evidencia": self.evidencia,
        }


@dataclass
class Escenario:
    """
    Escenario de simulacion configurable.

    Atributos:
        id: Identificador unico generado automaticamente.
        nombre: Nombre descriptivo del escenario.
        descripcion: Narrativa del escenario.
        variables: Lista de variables configurables.
        tipo: Clasificacion del escenario.
        fecha_creacion: Instante de creacion.
        resultados: Resultados de la ultima simulacion ejecutada.
        hipotesis_relacionada: ID de hipotesis vinculada (opcional).
    """
    id: str
    nombre: str
    descripcion: str
    variables: List[VariableEscenario]
    tipo: TipoEscenario = TipoEscenario.BASE
    fecha_creacion: datetime = field(default_factory=datetime.now)
    resultados: Optional[Dict[str, Any]] = None
    hipotesis_relacionada: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serializa el escenario a diccionario."""
        return {
            "id": self.id,
            "nombre": self.nombre,
            "descripcion": self.descripcion,
            "variables": [
                {
                    "nombre": v.nombre,
                    "valor_base": v.valor_base,
                    "rango_min": v.rango_min,
                    "rango_max": v.rango_max,
                    "distribucion": v.distribucion.value,
                    "descripcion": v.descripcion,
                    "metadata": v.metadata,
                }
                for v in self.variables
            ],
            "tipo": self.tipo.value,
            "fecha_creacion": self.fecha_creacion.isoformat(),
            "resultados": self.resultados,
            "hipotesis_relacionada": self.hipotesis_relacionada,
        }


# =============================================================================
# SIMULADOR DE ESCENARIOS
# =============================================================================

class SimuladorEscenarios:
    """
    Motor de simulacion Monte Carlo para analisis de escenarios what-if.

    Este simulador permite:
        - Crear escenarios con variables aleatorias configurables.
        - Ejecutar simulaciones Monte Carlo con reproducibilidad garantizada.
        - Propagar efectos a traves de un grafo de conocimiento causal.
        - Analizar sensibilidad de variables mediante correlacion rank-order.
        - Generar escenarios contrafactuales (optimista/pesimista).
        - Encontrar combinaciones de mejor y peor caso.

    Ejemplo:
        >>> sim = SimuladorEscenarios(grafo, motor_causal, db, logger)
        >>> esc_id = sim.crear_escenario("Crisis 2026", "...", [var1, var2])
        >>> resultados = sim.ejecutar_simulacion(esc_id, n_runs=5000)
        >>> sensibilidad = sim.analisis_sensibilidad(esc_id)
    """

    COLECCION_ESCENARIOS: str = "escenarios"
    COLECCION_RESULTADOS: str = "resultados_simulacion"
    VERSION: str = "1.0.0"

    def __init__(
        self,
        grafo: GrafoConocimiento = None,
        motor_causal: MotorCausal = None,
        db: BaseDatos = None,
        logger: Logger = None,
    ) -> None:
        """
        Inicializa el simulador con sus dependencias.

        Args:
            grafo: Grafo de conocimiento causal con nodos y relaciones pesadas.
            motor_causal: Motor de inferencia para calcular efectos entre nodos.
            db: Capa de persistencia para guardar escenarios y resultados.
            logger: Sistema de logging para auditoria.
        """
        if grafo is None:
            grafo = _GrafoConocimientoVacio()
        if motor_causal is None:
            motor_causal = _MotorCausalIdentidad()
        if db is None:
            db = _BaseDatosMemoria()
        if logger is None:
            logger = _LoggerNulo()

        self._grafo = grafo
        self._motor = motor_causal
        self._db = db
        self._logger = logger
        self._escenarios_cache: Dict[str, Escenario] = {}
        self._rng_seeds: Dict[str, int] = {}

        self._logger.info(
            f"[VEO] SimuladorEscenarios v{self.VERSION} inicializado. "
            f"Grafo con {len(grafo.todos_los_nodos())} nodos."
        )

    # -------------------------------------------------------------------------
    # CRUD de Escenarios
    # -------------------------------------------------------------------------

    def crear_escenario(
        self,
        nombre: str,
        descripcion: str,
        variables: List[VariableEscenario],
        tipo: TipoEscenario = TipoEscenario.BASE,
        hipotesis_relacionada: Optional[str] = None,
    ) -> str:
        """
        Crea un nuevo escenario de simulacion.

        Args:
            nombre: Nombre descriptivo del escenario.
            descripcion: Narrativa que describe el contexto del escenario.
            variables: Lista de variables configurables con sus distribuciones.
            tipo: Clasificacion del escenario.
            hipotesis_relacionada: ID de hipotesis vinculada (si aplica).

        Returns:
            Identificador unico del escenario creado.

        Raises:
            VariablesInvalidasError: Si no se proporcionan variables o son invalidas.
        """
        if not variables:
            raise VariablesInvalidasError(
                "Se requiere al menos una variable para crear un escenario."
            )

        # Generar ID determinista basado en nombre y timestamp
        escenario_id = f"esc-{nombre.lower().replace(' ', '-')}-{int(datetime.now().timestamp())}"

        escenario = Escenario(
            id=escenario_id,
            nombre=nombre,
            descripcion=descripcion,
            variables=variables,
            tipo=tipo,
            hipotesis_relacionada=hipotesis_relacionada,
        )

        # Persistir en base de datos
        doc_id = self._db.guardar(self.COLECCION_ESCENARIOS, escenario.to_dict())

        # Cachear en memoria
        self._escenarios_cache[escenario_id] = escenario
        self._rng_seeds[escenario_id] = int(datetime.now().timestamp())

        self._logger.info(
            f"[VEO] Escenario creado: '{nombre}' (ID: {escenario_id}) "
            f"con {len(variables)} variables, tipo={tipo.value}"
        )

        return escenario_id

    def obtener_escenario(self, escenario_id: str) -> Escenario:
        """
        Recupera un escenario por su ID (cache o base de datos).

        Args:
            escenario_id: Identificador del escenario.

        Returns:
            Instancia del escenario.

        Raises:
            EscenarioNoEncontradoError: Si el escenario no existe.
        """
        if escenario_id in self._escenarios_cache:
            return self._escenarios_cache[escenario_id]

        datos = self._db.obtener_por_id(self.COLECCION_ESCENARIOS, escenario_id)
        if datos is None:
            raise EscenarioNoEncontradoError(
                f"Escenario '{escenario_id}' no encontrado en la base de datos."
            )

        # Reconstruir desde diccionario
        variables = [
            VariableEscenario(
                nombre=v["nombre"],
                valor_base=v["valor_base"],
                rango_min=v["rango_min"],
                rango_max=v["rango_max"],
                distribucion=TipoDistribucion(v["distribucion"]),
                descripcion=v.get("descripcion", ""),
                metadata=v.get("metadata", {}),
            )
            for v in datos["variables"]
        ]

        escenario = Escenario(
            id=datos["id"],
            nombre=datos["nombre"],
            descripcion=datos["descripcion"],
            variables=variables,
            tipo=TipoEscenario(datos.get("tipo", "base")),
            fecha_creacion=datetime.fromisoformat(datos["fecha_creacion"]),
            resultados=datos.get("resultados"),
            hipotesis_relacionada=datos.get("hipotesis_relacionada"),
        )

        self._escenarios_cache[escenario_id] = escenario
        return escenario

    # -------------------------------------------------------------------------
    # Simulacion Monte Carlo
    # -------------------------------------------------------------------------

    def ejecutar_simulacion(
        self,
        escenario_id: str,
        n_runs: int = 1000,
        seed: Optional[int] = None,
        nodo_resultado: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Ejecuta una simulacion Monte Carlo sobre un escenario.

        Para cada corrida:
            1. Muestrea cada variable de su distribucion.
            2. Propaga los efectos a traves del grafo de conocimiento.
            3. Registra el resultado y el camino activado.

        La simulacion es deterministica dada una seed (reproducibilidad).

        Args:
            escenario_id: ID del escenario a simular.
            n_runs: Numero de corridas Monte Carlo (default 1000).
            seed: Semilla para el generador aleatorio (auto si None).
            nodo_resultado: Nodo objetivo a evaluar (auto-detectado si None).

        Returns:
            Diccionario con:
                - distribucion_resultados: Lista de valores resultantes.
                - estadisticas: media, mediana, desv_est, percentiles 5/95.
                - probabilidades_por_rango: Probabilidad por rangos discretos.
                - corridas_detalle: Lista de MonteCarloRun serializados.
                - histograma: Frecuencias para bins uniformes.
                - metadata: Informacion de la simulacion.

        Raises:
            EscenarioNoEncontradoError: Si el escenario no existe.
            SimulacionError: Si ocurre un error durante la simulacion.
        """
        if n_runs < 1:
            raise SimulacionError("n_runs debe ser al menos 1.")

        escenario = self.obtener_escenario(escenario_id)

        # Determinar seed para reproducibilidad
        if seed is None:
            seed = self._rng_seeds.get(escenario_id, int(datetime.now().timestamp()))

        rng = np.random.default_rng(seed)
        self._rng_seeds[escenario_id] = seed

        # Determinar nodo resultado si no se especifico
        if nodo_resultado is None:
            nodo_resultado = self._detectar_nodo_resultado(escenario)

        self._logger.info(
            f"[VEO] Iniciando simulacion Monte Carlo: escenario='{escenario.nombre}', "
            f"n_runs={n_runs}, seed={seed}, nodo_resultado='{nodo_resultado}'"
        )

        corridas: List[MonteCarloRun] = []
        resultados: List[float] = []
        i = -1

        try:
            for i in range(n_runs):
                # Paso 1: Muestrear variables
                valores_muestreados: Dict[str, float] = {}
                for var in escenario.variables:
                    valor = self._muestrear_variable(var, rng)
                    valores_muestreados[var.nombre] = valor

                # Paso 2: Propagar efectos por el grafo
                efectos_propagados = self._propagar_efectos(valores_muestreados)

                # Paso 3: Extraer resultado del nodo objetivo
                resultado = efectos_propagados.get(
                    nodo_resultado,
                    sum(efectos_propagados.values()) / max(len(efectos_propagados), 1)
                )

                # Paso 4: Registrar camino activado
                camino = list(efectos_propagados.keys())

                run = MonteCarloRun(
                    valores_muestreados=valores_muestreados,
                    resultado=float(resultado),
                    camino_activado=camino,
                )
                corridas.append(run)
                resultados.append(float(resultado))

        except Exception as e:
            raise SimulacionError(
                f"Error en corrida {i}: {str(e)}"
            ) from e

        # Calcular estadisticas
        estadisticas = self._calcular_estadisticas(resultados)
        probabilidades = self._calcular_probabilidades_por_rango(resultados)
        histograma = self._calcular_histograma(resultados, bins=20)

        # Ensamblar resultado
        resultado_final: Dict[str, Any] = {
            "escenario_id": escenario_id,
            "escenario_nombre": escenario.nombre,
            "n_runs": n_runs,
            "seed": seed,
            "nodo_resultado": nodo_resultado,
            "distribucion_resultados": resultados,
            "estadisticas": estadisticas,
            "probabilidades_por_rango": probabilidades,
            "histograma": histograma,
            "corridas_detalle": [r.to_dict() for r in corridas[:100]],  # Limitar para DB
            "timestamp": datetime.now().isoformat(),
            "metadata": {
                "version_simulador": self.VERSION,
                "n_variables": len(escenario.variables),
                "variables": [v.nombre for v in escenario.variables],
            },
        }

        # Persistir resultados
        self._db.guardar(self.COLECCION_RESULTADOS, resultado_final)

        # Actualizar cache del escenario
        escenario.resultados = resultado_final
        self._escenarios_cache[escenario_id] = escenario

        self._logger.info(
            f"[VEO] Simulacion completada: media={estadisticas['media']:.4f}, "
            f"mediana={estadisticas['mediana']:.4f}, p5={estadisticas['percentil_05']:.4f}, "
            f"p95={estadisticas['percentil_95']:.4f}"
        )

        return resultado_final

    # -------------------------------------------------------------------------
    # Analisis de Sensibilidad
    # -------------------------------------------------------------------------

    def analisis_sensibilidad(
        self,
        escenario_id: str,
        n_runs: int = 1000,
        seed: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Realiza analisis de sensibilidad mediante correlacion rank-order (Spearman).

        Determina que variables tienen mayor impacto en el resultado final,
        permitiendo identificar los drivers clave del escenario.

        Args:
            escenario_id: ID del escenario a analizar.
            n_runs: Numero de corridas para el analisis.
            seed: Semilla para reproducibilidad.

        Returns:
            Lista ordenada (mayor a menor impacto) de diccionarios con:
                - variable: Nombre de la variable.
                - coeficiente_spearman: Correlacion rank-order [-1, 1].
                - impacto: Magnitud del impacto (abs del coeficiente).
                - ranking: Posicion en orden de importancia.
                - interpretacion: Descripcion textual del efecto.
        """
        escenario = self.obtener_escenario(escenario_id)

        if seed is None:
            seed = self._rng_seeds.get(escenario_id, 42)

        rng = np.random.default_rng(seed)

        # Matriz de datos: filas = corridas, columnas = variables
        n_vars = len(escenario.variables)
        matriz_valores = np.zeros((n_runs, n_vars))
        resultados = np.zeros(n_runs)

        nodo_resultado = self._detectar_nodo_resultado(escenario)
        var_names = [v.nombre for v in escenario.variables]

        for i in range(n_runs):
            valores: Dict[str, float] = {}
            for j, var in enumerate(escenario.variables):
                val = self._muestrear_variable(var, rng)
                valores[var.nombre] = val
                matriz_valores[i, j] = val

            efectos = self._propagar_efectos(valores)
            resultados[i] = efectos.get(
                nodo_resultado,
                sum(efectos.values()) / max(len(efectos), 1)
            )

        # Calcular correlacion de Spearman (rank-order) para cada variable
        sensibilidades: List[Dict[str, Any]] = []

        for j, nombre_var in enumerate(var_names):
            # Ranks de la variable y del resultado
            var_vals = matriz_valores[:, j]

            # Spearman: correlacion de Pearson sobre los ranks
            ranks_var = np.argsort(np.argsort(var_vals))
            ranks_result = np.argsort(np.argsort(resultados))

            # Centrar ranks
            ranks_var_c = ranks_var - np.mean(ranks_var)
            ranks_result_c = ranks_result - np.mean(ranks_result)

            # Coeficiente de correlacion
            numerador = np.sum(ranks_var_c * ranks_result_c)
            denominador = np.sqrt(np.sum(ranks_var_c**2) * np.sum(ranks_result_c**2))

            if denominador > 0:
                spearman = float(numerador / denominador)
            else:
                spearman = 0.0

            impacto = abs(spearman)

            if spearman > 0.3:
                interpretacion = f"Impacto POSITIVO fuerte: al aumentar '{nombre_var}', aumenta el resultado."
            elif spearman > 0.1:
                interpretacion = f"Impacto positivo moderado de '{nombre_var}'."
            elif spearman > -0.1:
                interpretacion = f"Impacto DEBIL o nulo de '{nombre_var}'."
            elif spearman > -0.3:
                interpretacion = f"Impacto negativo moderado de '{nombre_var}'."
            else:
                interpretacion = f"Impacto NEGATIVO fuerte: al aumentar '{nombre_var}', disminuye el resultado."

            sensibilidades.append({
                "variable": nombre_var,
                "coeficiente_spearman": round(spearman, 6),
                "impacto": round(impacto, 6),
                "ranking": 0,  # Se asigna despues de ordenar
                "interpretacion": interpretacion,
            })

        # Ordenar por impacto descendente
        sensibilidades.sort(key=lambda x: x["impacto"], reverse=True)
        for i, s in enumerate(sensibilidades):
            s["ranking"] = i + 1

        self._logger.info(
            f"[VEO] Analisis de sensibilidad completado para '{escenario.nombre}'. "
            f"Variable mas influyente: '{sensibilidades[0]['variable']}' "
            f"(impacto={sensibilidades[0]['impacto']:.4f})"
        )

        return sensibilidades

    # -------------------------------------------------------------------------
    # Comparacion de Escenarios
    # -------------------------------------------------------------------------

    def comparar_escenarios(self, escenario_ids: List[str]) -> Dict[str, Any]:
        """
        Compara multiples escenarios lado a lado.

        Args:
            escenario_ids: Lista de IDs de escenarios a comparar.

        Returns:
            Diccionario con comparacion estadistica y conclusiones:
                - escenarios: Lista de resumenes de cada escenario.
                - diferencias_clave: Variables con mayor varianza entre escenarios.
                - ranking: Orden de escenarios por resultado esperado.
                - recomendacion: Texto con la conclusion del analisis.
        """
        if len(escenario_ids) < 2:
            raise SimulacionError("Se requieren al menos 2 escenarios para comparar.")

        escenarios: List[Escenario] = []
        simulaciones: List[Dict[str, Any]] = []

        for eid in escenario_ids:
            esc = self.obtener_escenario(eid)
            escenarios.append(esc)

            # Si no tiene resultados, ejecutar simulacion rapida
            if esc.resultados is None:
                res = self.ejecutar_simulacion(eid, n_runs=1000)
            else:
                res = esc.resultados
            simulaciones.append(res)

        # Resumenes individuales
        resumenes = []
        for esc, sim in zip(escenarios, simulaciones):
            resumenes.append({
                "id": esc.id,
                "nombre": esc.nombre,
                "tipo": esc.tipo.value,
                "media": sim["estadisticas"]["media"],
                "mediana": sim["estadisticas"]["mediana"],
                "percentil_05": sim["estadisticas"]["percentil_05"],
                "percentil_95": sim["estadisticas"]["percentil_95"],
                "riesgo": sim["estadisticas"]["percentil_05"] - sim["estadisticas"]["media"],
            })

        # Ranking por resultado esperado (mediana)
        ranking = sorted(resumenes, key=lambda x: x["mediana"], reverse=True)

        # Identificar diferencias clave entre variables
        todas_vars: set[str] = set()
        for esc in escenarios:
            for v in esc.variables:
                todas_vars.add(v.nombre)

        diferencias_clave = []
        for var_name in sorted(todas_vars):
            valores_base = []
            for esc in escenarios:
                for v in esc.variables:
                    if v.nombre == var_name:
                        valores_base.append(v.valor_base)
                        break
                else:
                    valores_base.append(None)

            if None not in valores_base and len(set(valores_base)) > 1:
                rango = max(valores_base) - min(valores_base)
                diferencias_clave.append({
                    "variable": var_name,
                    "valores_por_escenario": {
                        esc.nombre: val for esc, val in zip(escenarios, valores_base)
                    },
                    "rango_diferencia": round(rango, 4),
                })

        diferencias_clave.sort(key=lambda x: x["rango_diferencia"], reverse=True)

        # Generar recomendacion textual
        mejor = ranking[0]
        peor = ranking[-1]
        recomendacion = (
            f"El escenario '{mejor['nombre']}' presenta el resultado mas favorable "
            f"(mediana={mejor['mediana']:.4f}), mientras que '{peor['nombre']}' "
            f"presenta el menos favorable (mediana={peor['mediana']:.4f}). "
            f"La diferencia entre el percentil 5 y 95 indica que "
        )

        if mejor["percentil_95"] - mejor["percentil_05"] > abs(mejor["media"]) * 0.5:
            recomendacion += (
                "existe ALTA incertidumbre. Se recomienda monitorear las variables "
                "mas sensibles de cerca."
            )
        else:
            recomendacion += (
                "la incertidumbre es MODERADA. Los resultados son relativamente estables."
            )

        resultado: Dict[str, Any] = {
            "escenarios": resumenes,
            "diferencias_clave": diferencias_clave[:5],  # Top 5
            "ranking": [
                {"posicion": i + 1, "escenario": r["nombre"], "mediana": r["mediana"]}
                for i, r in enumerate(ranking)
            ],
            "recomendacion": recomendacion,
            "timestamp": datetime.now().isoformat(),
        }

        self._logger.info(
            f"[VEO] Comparacion de {len(escenario_ids)} escenarios completada. "
            f"Mejor: '{mejor['nombre']}', Peor: '{peor['nombre']}'"
        )

        return resultado

    # -------------------------------------------------------------------------
    # Escenarios Contrafactuales
    # -------------------------------------------------------------------------

    def generar_escenarios_contrafactuales(
        self,
        hipotesis: Hipotesis,
    ) -> List[Escenario]:
        """
        Genera tres escenarios contrafactuales (optimista, pesimista, neutral)
        a partir de una hipotesis del sistema.

        Cada escenario ajusta las variables afectadas segun la direccion esperada.

        Args:
            hipotesis: Hipotesis sobre la que construir escenarios contrafactuales.

        Returns:
            Lista de 3 escenarios: optimista, neutral, pesimista.
        """
        escenarios_generados: List[Escenario] = []
        timestamp = int(datetime.now().timestamp())

        # Mapeo de direccion a multiplicadores
        if hipotesis.direccion_esperada == "aumento":
            configs = [
                ("optimista", 1.5, TipoEscenario.OPTIMISTA),
                ("neutral", 1.0, TipoEscenario.CONTRAFACTUAL),
                ("pesimista", 0.5, TipoEscenario.PESIMISTA),
            ]
        elif hipotesis.direccion_esperada == "disminucion":
            configs = [
                ("optimista", 0.5, TipoEscenario.OPTIMISTA),
                ("neutral", 1.0, TipoEscenario.CONTRAFACTUAL),
                ("pesimista", 1.5, TipoEscenario.PESIMISTA),
            ]
        else:  # mixto
            configs = [
                ("optimista", 1.3, TipoEscenario.OPTIMISTA),
                ("neutral", 1.0, TipoEscenario.CONTRAFACTUAL),
                ("pesimista", 0.7, TipoEscenario.PESIMISTA),
            ]

        for etiqueta, multiplicador, tipo in configs:
            variables_contrafactuales: List[VariableEscenario] = []

            for var_nombre in hipotesis.variables_afectadas:
                # Crear variable basada en la hipotesis
                valor_base = hipotesis.confianza * 10.0 * multiplicador
                rango = valor_base * 0.5

                var = VariableEscenario(
                    nombre=var_nombre,
                    valor_base=round(valor_base, 4),
                    rango_min=round(max(0.0, valor_base - rango), 4),
                    rango_max=round(valor_base + rango, 4),
                    distribucion=TipoDistribucion.NORMAL,
                    descripcion=f"Variable contrafactual '{etiqueta}' derivada de hipotesis '{hipotesis.nombre}'",
                    metadata={"std_dev": round(rango / 3, 4), "multiplicador": multiplicador},
                )
                variables_contrafactuales.append(var)

            if not variables_contrafactuales:
                # Si no hay variables afectadas, crear una generica
                variables_contrafactuales.append(
                    VariableEscenario(
                        nombre="impacto_general",
                        valor_base=round(hipotesis.confianza * multiplicador, 4),
                        rango_min=0.0,
                        rango_max=round(hipotesis.confianza * multiplicador * 2, 4),
                        distribucion=TipoDistribucion.UNIFORME,
                        descripcion=f"Impacto general contrafactual {etiqueta}",
                    )
                )

            esc_id = f"esc-contrafactual-{etiqueta}-{hipotesis.id}-{timestamp}"
            escenario = Escenario(
                id=esc_id,
                nombre=f"Contrafactual {etiqueta.capitalize()}: {hipotesis.nombre}",
                descripcion=(
                    f"Escenario contrafactual '{etiqueta}' generado a partir de la "
                    f"hipotesis '{hipotesis.nombre}'. {hipotesis.descripcion}"
                ),
                variables=variables_contrafactuales,
                tipo=tipo,
                hipotesis_relacionada=hipotesis.id,
            )

            # Persistir
            self._db.guardar(self.COLECCION_ESCENARIOS, escenario.to_dict())
            self._escenarios_cache[esc_id] = escenario
            escenarios_generados.append(escenario)

        self._logger.info(
            f"[VEO] Generados {len(escenarios_generados)} escenarios "
            f"contrafactuales para hipotesis '{hipotesis.nombre}'"
        )

        return escenarios_generados

    # -------------------------------------------------------------------------
    # Mejor / Peor Caso
    # -------------------------------------------------------------------------

    def escenario_peor_caso(self, escenario_id: str) -> Dict[str, Any]:
        """
        Encuentra la combinacion de variables que produce el peor resultado posible.

        Utiliza un enfoque de optimizacion por fuerza bruta con muestreo
        sistematico en los extremos de cada variable.

        Args:
            escenario_id: ID del escenario a analizar.

        Returns:
            Diccionario con:
                - valores_optimos: Asignacion de variables para el peor caso.
                - resultado: Valor del peor resultado encontrado.
                - escenario_id: ID del escenario analizado.
                - interpretacion: Descripcion textual del peor caso.
        """
        escenario = self.obtener_escenario(escenario_id)
        nodo_resultado = self._detectar_nodo_resultado(escenario)

        mejor_resultado = float("inf")
        peores_valores: Dict[str, float] = {}

        # Muestreo sistematico en los extremos (2^n combinaciones)
        n_vars = len(escenario.variables)

        # Para muchas variables, usar enfoque greedy
        if n_vars > 8:
            peores_valores = self._optimizacion_greedy(
                escenario, nodo_resultado, minimizar=True
            )
            efectos = self._propagar_efectos(peores_valores)
            mejor_resultado = efectos.get(
                nodo_resultado,
                sum(efectos.values()) / max(len(efectos), 1)
            )
        else:
            # Fuerza bruta para pocas variables
            from itertools import product

            for combinacion in product([0, 1], repeat=n_vars):
                valores: Dict[str, float] = {}
                for i, var in enumerate(escenario.variables):
                    if combinacion[i] == 0:
                        valores[var.nombre] = var.rango_min
                    else:
                        valores[var.nombre] = var.rango_max

                efectos = self._propagar_efectos(valores)
                resultado = efectos.get(
                    nodo_resultado,
                    sum(efectos.values()) / max(len(efectos), 1)
                )

                if resultado < mejor_resultado:
                    mejor_resultado = resultado
                    peores_valores = dict(valores)

        interpretacion = self._generar_interpretacion_caso(
            peores_valores, escenario, "peor"
        )

        resultado_dict: Dict[str, Any] = {
            "tipo": "peor_caso",
            "escenario_id": escenario_id,
            "escenario_nombre": escenario.nombre,
            "valores_optimos": peores_valores,
            "resultado": round(float(mejor_resultado), 6),
            "interpretacion": interpretacion,
            "timestamp": datetime.now().isoformat(),
        }

        self._logger.info(
            f"[VEO] Peor caso para '{escenario.nombre}': "
            f"resultado={mejor_resultado:.4f}"
        )

        return resultado_dict

    def escenario_mejor_caso(self, escenario_id: str) -> Dict[str, Any]:
        """
        Encuentra la combinacion de variables que produce el mejor resultado posible.

        Args:
            escenario_id: ID del escenario a analizar.

        Returns:
            Diccionario con:
                - valores_optimos: Asignacion de variables para el mejor caso.
                - resultado: Valor del mejor resultado encontrado.
                - interpretacion: Descripcion textual del mejor caso.
        """
        escenario = self.obtener_escenario(escenario_id)
        nodo_resultado = self._detectar_nodo_resultado(escenario)

        mejor_resultado = float("-inf")
        mejores_valores: Dict[str, float] = {}

        n_vars = len(escenario.variables)

        if n_vars > 8:
            mejores_valores = self._optimizacion_greedy(
                escenario, nodo_resultado, minimizar=False
            )
            efectos = self._propagar_efectos(mejores_valores)
            mejor_resultado = efectos.get(
                nodo_resultado,
                sum(efectos.values()) / max(len(efectos), 1)
            )
        else:
            from itertools import product

            for combinacion in product([0, 1], repeat=n_vars):
                valores: Dict[str, float] = {}
                for i, var in enumerate(escenario.variables):
                    if combinacion[i] == 0:
                        valores[var.nombre] = var.rango_min
                    else:
                        valores[var.nombre] = var.rango_max

                efectos = self._propagar_efectos(valores)
                resultado = efectos.get(
                    nodo_resultado,
                    sum(efectos.values()) / max(len(efectos), 1)
                )

                if resultado > mejor_resultado:
                    mejor_resultado = resultado
                    mejores_valores = dict(valores)

        interpretacion = self._generar_interpretacion_caso(
            mejores_valores, escenario, "mejor"
        )

        resultado_dict: Dict[str, Any] = {
            "tipo": "mejor_caso",
            "escenario_id": escenario_id,
            "escenario_nombre": escenario.nombre,
            "valores_optimos": mejores_valores,
            "resultado": round(float(mejor_resultado), 6),
            "interpretacion": interpretacion,
            "timestamp": datetime.now().isoformat(),
        }

        self._logger.info(
            f"[VEO] Mejor caso para '{escenario.nombre}': "
            f"resultado={mejor_resultado:.4f}"
        )

        return resultado_dict

    # -------------------------------------------------------------------------
    # Propagacion de Efectos (Core del simulador)
    # -------------------------------------------------------------------------

    def _propagar_efectos(self, valores: Dict[str, float]) -> Dict[str, float]:
        """
        Propaga efectos a traves del grafo de conocimiento mediante difusion.

        Algoritmo:
            1. Inicializar cada nodo con su valor muestreado (o 0 si no fue muestreado).
            2. Para cada nodo activo, propagar su efecto a los nodos vecinos usando
               los pesos de las relaciones causales.
            3. Aplicar funcion de activacion (tanh) para limitar la magnitud.
            4. Repetir hasta convergencia o maximo de iteraciones.

        Args:
            valores: Diccionario {nombre_variable -> valor inicial}.

        Returns:
            Diccionario {nodo_id -> valor final despues de propagacion}.
        """
        # Inicializar estado de todos los nodos
        estado: Dict[str, float] = {}
        for nodo_id in self._grafo.todos_los_nodos():
            estado[nodo_id] = valores.get(nodo_id, 0.0)

        # Difusion iterativa
        max_iteraciones = 10
        umbral_convergencia = 1e-4

        for iteracion in range(max_iteraciones):
            estado_anterior = dict(estado)
            cambio_maximo = 0.0

            for nodo_id in self._grafo.todos_los_nodos():
                # Obtener relaciones entrantes
                relaciones = self._grafo.obtener_relaciones_hacia(nodo_id)

                influencia_total = 0.0
                peso_total = 0.0

                for rel in relaciones:
                    valor_origen = estado_anterior.get(rel.origen_id, 0.0)
                    influencia = self._motor.calcular_efecto(
                        rel.origen_id, nodo_id, valor_origen
                    )
                    influencia_total += influencia * rel.peso
                    peso_total += abs(rel.peso)

                if peso_total > 0:
                    influencia_promedio = influencia_total / peso_total
                else:
                    influencia_promedio = 0.0

                # Actualizar valor: combinar valor actual con influencia
                valor_actual = estado_anterior.get(nodo_id, 0.0)
                nuevo_valor = valor_actual + 0.5 * influencia_promedio

                # Funcion de activacion: tanh para limitar [-1, 1] (escalable)
                # Permitimos valores mayores que 1 usando una escala
                escala = max(abs(v) for v in valores.values()) if valores else 1.0
                escala = max(escala, 1.0)

                if abs(nuevo_valor) > escala:
                    nuevo_valor = escala * np.tanh(nuevo_valor / escala)

                estado[nodo_id] = float(nuevo_valor)
                cambio_maximo = max(cambio_maximo, abs(nuevo_valor - valor_actual))

            if cambio_maximo < umbral_convergencia:
                break

        return estado

    # -------------------------------------------------------------------------
    # Muestreo de Variables
    # -------------------------------------------------------------------------

    def _muestrear_variable(
        self,
        var: VariableEscenario,
        rng: np.random.Generator,
    ) -> float:
        """
        Muestrea una variable de su distribucion de probabilidad.

        Soporta: uniforme, normal, triangular, lognormal, constante.

        Args:
            var: Variable a muestrear.
            rng: Generador aleatorio de numpy (para reproducibilidad).

        Returns:
            Valor muestreado (acotado al rango [min, max]).
        """
        if var.distribucion == TipoDistribucion.CONSTANTE:
            valor = var.valor_base

        elif var.distribucion == TipoDistribucion.UNIFORME:
            valor = rng.uniform(var.rango_min, var.rango_max)

        elif var.distribucion == TipoDistribucion.NORMAL:
            std = var.metadata.get("std_dev", (var.rango_max - var.rango_min) / 6)
            valor = rng.normal(var.valor_base, std)

        elif var.distribucion == TipoDistribucion.TRIANGULAR:
            # Modo en valor_base, limites en rango_min/max
            ancho = var.rango_max - var.rango_min
            if ancho > 0:
                modo_rel = (var.valor_base - var.rango_min) / ancho
            else:
                modo_rel = 0.5
            valor = rng.triangular(var.rango_min, var.valor_base, var.rango_max)

        elif var.distribucion == TipoDistribucion.LOGNORMAL:
            # Parametrizar via media y sigma en escala log
            sigma = var.metadata.get("sigma", 0.5)
            mu = var.metadata.get("mu", np.log(var.valor_base)) if var.valor_base > 0 else 0
            if var.valor_base > 0:
                valor = rng.lognormal(mu, sigma)
            else:
                valor = var.valor_base

        else:
            valor = var.valor_base

        # Acotar al rango valido
        valor = max(var.rango_min, min(var.rango_max, valor))
        return float(valor)

    # -------------------------------------------------------------------------
    # Exportacion
    # -------------------------------------------------------------------------

    def exportar_resultados(
        self,
        escenario_id: str,
        formato: str = "json",
    ) -> str:
        """
        Exporta los resultados de una simulacion en el formato solicitado.

        Args:
            escenario_id: ID del escenario cuyos resultados se exportaran.
            formato: "json" o "markdown".

        Returns:
            Cadena con los resultados en el formato solicitado.

        Raises:
            EscenarioNoEncontradoError: Si no hay resultados para exportar.
            SimulacionError: Si el formato no es soportado.
        """
        escenario = self.obtener_escenario(escenario_id)

        if escenario.resultados is None:
            raise EscenarioNoEncontradoError(
                f"El escenario '{escenario_id}' no tiene resultados de simulacion. "
                f"Ejecute 'ejecutar_simulacion' primero."
            )

        if formato == "json":
            return json.dumps(escenario.resultados, ensure_ascii=False, indent=2)

        elif formato == "markdown":
            res = escenario.resultados
            stats = res["estadisticas"]

            md = f"""# Resultados de Simulacion: {escenario.nombre}

> **Escenario ID**: `{escenario.id}`  
> **Tipo**: {escenario.tipo.value}  
> **Fecha simulacion**: {res['timestamp']}  
> **Corridas Monte Carlo**: {res['n_runs']:,}  
> **Seed**: {res['seed']} (reproducible)  

## Descripcion

{escenario.descripcion}

## Estadisticas Principales

| Metrica | Valor |
|---------|-------|
| Media | **{stats['media']:.6f}** |
| Mediana | **{stats['mediana']:.6f}** |
| Desviacion Estandar | {stats['desviacion_estandar']:.6f} |
| Minimo | {stats['minimo']:.6f} |
| Maximo | {stats['maximo']:.6f} |
| Percentil 5 | {stats['percentil_05']:.6f} |
| Percentil 95 | {stats['percentil_95']:.6f} |

## Probabilidades por Rango

| Rango | Probabilidad |
|-------|-------------|
"""
            for rango, prob in res["probabilidades_por_rango"].items():
                md += f"| {rango} | {prob:.2%} |\n"

            md += f"""
## Histograma (20 bins)

```
"""
            hist = res["histograma"]
            max_freq = max(hist["frecuencias"]) if hist["frecuencias"] else 1
            for i, freq in enumerate(hist["frecuencias"]):
                barra = "█" * int(40 * freq / max_freq)
                md += f"[{hist['bin_edges'][i]:.4f}, {hist['bin_edges'][i+1]:.4f}] {barra} {freq}\n"

            md += f"""```

## Variables del Escenario

| Variable | Base | Min | Max | Distribucion |
|----------|------|-----|-----|-------------|
"""
            for v in escenario.variables:
                md += f"| {v.nombre} | {v.valor_base} | {v.rango_min} | {v.rango_max} | {v.distribucion.value} |\n"

            if escenario.hipotesis_relacionada:
                md += f"\n## Hipotesis Relacionada\n\nID: `{escenario.hipotesis_relacionada}`\n"

            md += f"\n---\n*Generado por VEO v{self.VERSION}*\n"

            return md

        else:
            raise SimulacionError(
                f"Formato '{formato}' no soportado. Use 'json' o 'markdown'."
            )

    # -------------------------------------------------------------------------
    # Metodos Privados (Utilidades)
    # -------------------------------------------------------------------------

    def _detectar_nodo_resultado(self, escenario: Escenario) -> str:
        """
        Detecta automaticamente el nodo resultado para un escenario.

        Usa heuristicas: nodo con mayor grado de salida, o ultima variable.
        """
        nodos_escenario = {v.nombre for v in escenario.variables}

        # Heuristica: nodo del escenario con mas conexiones de salida
        max_conexiones = -1
        nodo_central = ""

        for nodo_id in self._grafo.todos_los_nodos():
            if nodo_id in nodos_escenario:
                conexiones = len(self._grafo.obtener_relaciones_desde(nodo_id))
                if conexiones > max_conexiones:
                    max_conexiones = conexiones
                    nodo_central = nodo_id

        if nodo_central:
            return nodo_central

        # Fallback: ultima variable del escenario
        if escenario.variables:
            return escenario.variables[-1].nombre

        # Fallback final: primer nodo del grafo
        nodos = self._grafo.todos_los_nodos()
        if nodos:
            return nodos[0]

        return "resultado"

    def _calcular_estadisticas(self, resultados: List[float]) -> Dict[str, float]:
        """Calcula estadisticas descriptivas de los resultados de simulacion."""
        arr = np.array(resultados)

        return {
            "media": float(np.mean(arr)),
            "mediana": float(np.median(arr)),
            "desviacion_estandar": float(np.std(arr, ddof=1)),
            "minimo": float(np.min(arr)),
            "maximo": float(np.max(arr)),
            "percentil_05": float(np.percentile(arr, 5)),
            "percentil_95": float(np.percentile(arr, 95)),
            "percentil_25": float(np.percentile(arr, 25)),
            "percentil_75": float(np.percentile(arr, 75)),
            "n": len(resultados),
        }

    def _calcular_probabilidades_por_rango(
        self,
        resultados: List[float],
        n_rangos: int = 5,
    ) -> Dict[str, float]:
        """
        Divide los resultados en rangos discretos y calcula probabilidades.
        """
        arr = np.array(resultados)
        min_val, max_val = np.min(arr), np.max(arr)

        if min_val == max_val:
            return {"unico": 1.0}

        bins = np.linspace(min_val, max_val, n_rangos + 1)
        probabilidades: Dict[str, float] = {}

        for i in range(n_rangos):
            inferior, superior = bins[i], bins[i + 1]
            if i < n_rangos - 1:
                cuenta = np.sum((arr >= inferior) & (arr < superior))
            else:
                cuenta = np.sum((arr >= inferior) & (arr <= superior))

            etiqueta = f"[{inferior:.4f}, {superior:.4f}]"
            probabilidades[etiqueta] = float(cuenta / len(resultados))

        return probabilidades

    def _calcular_histograma(
        self,
        resultados: List[float],
        bins: int = 20,
    ) -> Dict[str, Any]:
        """Calcula histograma con bins uniformes."""
        arr = np.array(resultados)
        frecuencias, edges = np.histogram(arr, bins=bins)

        return {
            "frecuencias": [int(f) for f in frecuencias],
            "bin_edges": [float(e) for e in edges],
            "n_bins": bins,
        }

    def _optimizacion_greedy(
        self,
        escenario: Escenario,
        nodo_resultado: str,
        minimizar: bool = True,
    ) -> Dict[str, float]:
        """
        Optimizacion greedy para encontrar mejor/peor caso.

        Estrategia: iterar variable por variable, eligiendo el extremo
        (min o max) que mejore el objetivo.
        """
        valores: Dict[str, float] = {}

        for var in escenario.variables:
            # Probar ambos extremos
            test_valores_min = dict(valores)
            test_valores_min[var.nombre] = var.rango_min

            test_valores_max = dict(valores)
            test_valores_max[var.nombre] = var.rango_max

            # Evaluar ambos
            efectos_min = self._propagar_efectos(test_valores_min)
            res_min = efectos_min.get(
                nodo_resultado,
                sum(efectos_min.values()) / max(len(efectos_min), 1)
            )

            efectos_max = self._propagar_efectos(test_valores_max)
            res_max = efectos_max.get(
                nodo_resultado,
                sum(efectos_max.values()) / max(len(efectos_max), 1)
            )

            # Elegir el mejor para el objetivo
            if minimizar:
                if res_min < res_max:
                    valores[var.nombre] = var.rango_min
                else:
                    valores[var.nombre] = var.rango_max
            else:
                if res_max > res_min:
                    valores[var.nombre] = var.rango_max
                else:
                    valores[var.nombre] = var.rango_min

        return valores

    def _generar_interpretacion_caso(
        self,
        valores: Dict[str, float],
        escenario: Escenario,
        tipo_caso: str,
    ) -> str:
        """Genera una descripcion textual del caso extremo encontrado."""
        partes = [f"Caso {tipo_caso} para el escenario '{escenario.nombre}':"]

        for var in escenario.variables:
            val = valores.get(var.nombre, var.valor_base)
            if abs(val - var.rango_min) < abs(val - var.rango_max):
                extremo = "minimo"
            else:
                extremo = "maximo"
            partes.append(f"  - '{var.nombre}' en valor {extremo} ({val:.4f})")

        return "\n".join(partes)


# =============================================================================
# FUNCIONES AUXILIARES PUBLICAS
# =============================================================================

def crear_variable_simple(
    nombre: str,
    valor_base: float,
    rango: Optional[Tuple[float, float]] = None,
    distribucion: TipoDistribucion = TipoDistribucion.UNIFORME,
    descripcion: str = "",
    **metadata: Any,
) -> VariableEscenario:
    """
    Factory function para crear una VariableEscenario de forma sencilla.

    Args:
        nombre: Identificador de la variable.
        valor_base: Valor central.
        rango: Tupla (min, max). Si es None, usa +/- 50% del valor_base.
        distribucion: Tipo de distribucion.
        descripcion: Explicacion de la variable.
        **metadata: Parametros adicionales.

    Returns:
        Instancia de VariableEscenario configurada.
    """
    if rango is None:
        if valor_base == 0:
            rango = (-1.0, 1.0)
        else:
            margen = abs(valor_base) * 0.5
            rango = (valor_base - margen, valor_base + margen)

    return VariableEscenario(
        nombre=nombre,
        valor_base=valor_base,
        rango_min=rango[0],
        rango_max=rango[1],
        distribucion=distribucion,
        descripcion=descripcion,
        metadata=metadata,
    )


def quick_simulate(
    grafo: GrafoConocimiento,
    motor: MotorCausal,
    variables: List[VariableEscenario],
    n_runs: int = 1000,
    seed: int = 42,
) -> Dict[str, Any]:
    """
    Funcion utilitaria para ejecutar una simulacion rapida sin persistencia.

    Args:
        grafo: Grafo de conocimiento.
        motor: Motor causal.
        variables: Variables del escenario.
        n_runs: Numero de corridas.
        seed: Semilla para reproducibilidad.

    Returns:
        Resultados de la simulacion.
    """
    # Stubs minimos para no requerir db/logger reales
    class _StubDB:
        def guardar(self, c: str, d: Dict) -> str:
            return "stub"
        def buscar(self, c: str, f: Dict) -> List[Dict]:
            return []
        def obtener_por_id(self, c: str, i: str) -> Optional[Dict]:
            return None
        def actualizar(self, c: str, i: str, d: Dict) -> bool:
            return True

    class _StubLogger:
        def debug(self, m: str) -> None: pass
        def info(self, m: str) -> None: pass
        def warning(self, m: str) -> None: pass
        def error(self, m: str) -> None: pass

    sim = SimuladorEscenarios(grafo, motor, _StubDB(), _StubLogger())
    esc_id = sim.crear_escenario(
        nombre="Simulacion Rapida",
        descripcion="Ejecucion directa sin persistencia",
        variables=variables,
    )
    return sim.ejecutar_simulacion(esc_id, n_runs=n_runs, seed=seed)


# =============================================================================
# EJECUCION COMO SCRIPT
# =============================================================================


# ============================================================================
# VEO v2: Funciones de integracion con hermes_commander / veo_core
# ============================================================================
# NOTA: Estas funciones fueron anadidas en la migracion de VEO v1 a VEO v2.
# Proporcionan observabilidad, auditoria, health-checks y estimacion de
# costos computacionales sin modificar la logica Monte Carlo existente.
# ============================================================================

import time as _time

# --- Estado observable del modulo (VEO v2) ---
_simulator_execution_count: int = 0
_simulator_last_execution_time: float = 0.0
_simulation_log: list = []


def get_trust_score() -> float:
    """
    VEO v2: Devuelve el score de confianza del simulador de escenarios.

    Basado en la estabilidad y consistencia de las simulaciones ejecutadas.

    Returns:
        float: Score de confianza en [0.0, 1.0].
    """
    global _simulation_log
    if not _simulation_log:
        return 0.75

    exitosas = sum(
        1 for s in _simulation_log
        if s.get("exitosa", True)
    )
    total = len(_simulation_log)
    score = 0.2 + 0.8 * (exitosas / max(total, 1))
    return round(min(max(score, 0.0), 1.0), 4)


def get_last_execution_time() -> str:
    """
    VEO v2: Devuelve el timestamp ISO de la ultima simulacion ejecutada.

    Returns:
        str: Timestamp ISO 8601, o cadena vacia si no ha ejecutado.
    """
    global _simulator_last_execution_time
    if _simulator_last_execution_time == 0.0:
        return ""
    return _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime(_simulator_last_execution_time))


def get_health_status() -> dict:
    """
    VEO v2: Devuelve el estado de salud del simulador de escenarios.

    Returns:
        dict: {"status": "healthy|degraded|unhealthy", "score": 0-100}
    """
    global _simulator_last_execution_time, _simulation_log

    score = 100

    if _simulator_last_execution_time > 0:
        horas = (_time.time() - _simulator_last_execution_time) / 3600
        if horas > 72:
            score -= 25
        elif horas > 24:
            score -= 10

    if _simulation_log:
        trust = get_trust_score()
        if trust < 0.5:
            score -= 25

    if _simulator_execution_count == 0:
        score -= 10

    score = max(0, min(100, score))

    if score >= 80:
        status = "healthy"
    elif score >= 50:
        status = "degraded"
    else:
        status = "unhealthy"

    return {"status": status, "score": score}


def estimate_cost(variables: list, n_runs: int) -> dict:
    """
    VEO v2: Estima los recursos computacionales necesarios para una simulacion.

    Calcula una estimacion aproximada de CPU tiempo y memoria requerida
    basada en el numero de variables y corridas Monte Carlo.

    Args:
        variables: Lista de variables del escenario.
        n_runs: Numero de corridas Monte Carlo planeadas.

    Returns:
        dict: Estimacion con claves:
            - cpu_time_ms: Tiempo estimado de CPU en milisegundos.
            - memory_mb: Memoria RAM estimada en MB.
            - complexity: Etiqueta de complejidad (low|medium|high|extreme).
    """
    n_vars = len(variables) if variables else 1

    # Modelo heuristico de costo
    # Base: 1 variable, 1000 runs ~ 50ms CPU, 2MB RAM
    base_cpu_ms = 50
    base_mem_mb = 2

    # Escalar por variables (no lineal, mas variables = mas propagacion)
    var_factor = 1.0 + 0.3 * (n_vars - 1)

    # Escalar por runs (lineal)
    run_factor = n_runs / 1000.0

    cpu_estimated = base_cpu_ms * var_factor * run_factor
    memory_estimated = base_mem_mb * (1 + 0.1 * n_vars) * (1 + 0.001 * n_runs)

    # Clasificar complejidad
    if cpu_estimated < 100:
        complexity = "low"
    elif cpu_estimated < 1000:
        complexity = "medium"
    elif cpu_estimated < 10000:
        complexity = "high"
    else:
        complexity = "extreme"

    return {
        "cpu_time_ms": round(cpu_estimated, 2),
        "memory_mb": round(memory_estimated, 2),
        "complexity": complexity,
        "n_variables": n_vars,
        "n_runs": n_runs,
    }


def _log_audit_simulation(
    escenario_id: str,
    n_runs: int,
    exitosa: bool = True,
    error: str = "",
) -> None:
    """
    VEO v2: Registra una entrada de auditoria para cada simulacion ejecutada.

    Args:
        escenario_id: ID del escenario simulado.
        n_runs: Numero de corridas.
        exitosa: Si la simulacion completo sin errores.
        error: Mensaje de error si fallo.
    """
    global _simulator_execution_count, _simulator_last_execution_time, _simulation_log

    _simulator_execution_count += 1
    _simulator_last_execution_time = _time.time()

    entry = {
        "timestamp": get_last_execution_time(),
        "escenario_id": escenario_id,
        "n_runs": n_runs,
        "exitosa": exitosa,
        "error": error,
    }
    _simulation_log.append(entry)

    if len(_simulation_log) > 500:
        _simulation_log = _simulation_log[-500:]

if __name__ == "__main__":
    print("=" * 70)
    print("VEO: Simulador de Escenarios What-If")
    print("=" * 70)
    print()
    print("Frase definitiva:")
    print('  "SOIS es una plataforma de inteligencia artificial cooperativa')
    print("   destinada a detectar cambios emergentes en la realidad...")
    print()
    print(f"Version del simulador: {SimuladorEscenarios.VERSION}")
    print()
    print("Clases exportadas:")
    print("  - SimuladorEscenarios (motor principal)")
    print("  - VariableEscenario, MonteCarloRun, Escenario, Hipotesis")
    print("  - TipoDistribucion, TipoEscenario")
    print("  - Excepciones: SimuladorError, EscenarioNoEncontradoError,")
    print("                 VariablesInvalidasError, SimulacionError")
    print()
    print("Funciones auxiliares:")
    print("  - crear_variable_simple()")
    print("  - quick_simulate()")
    print()
    print("=" * 70)
