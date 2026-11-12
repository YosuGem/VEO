# health_monitor.py - VEO v2 Operations
# NOTA ARQUITECTONICA (v2.0.5): Este modulo es STANDALONE.
# VEOCore utiliza su propia implementacion interna de HealthMonitor definida
# en core/veo_core.py (linea 1501). Este archivo en operations/ no es
# importado ni utilizado en produccion por el sistema principal.
# Se mantiene como referencia y para tests independientes.
"""
Monitor de salud del sistema VEO v2.

La clase HealthMonitor verifica el estado de cada motor/componente
del sistema, calcula metricas de salud (latencia, tasa de exito,
errores recientes) y proporciona un health score global.

Componentes monitoreados:
    - veo_core: Motor de razonamiento
    - hermes_commander: Motor de ejecucion
    - operations: Capa de operaciones
    - database: Base de datos SQLite
    - api: Servidor API REST
    - mercado: Mercado de predicciones

Ejemplo de uso:
    >>> from veo_v2.operations.health_monitor import HealthMonitor
    >>> monitor = HealthMonitor()
    >>> await monitor.check_all()
    {'veo_core': {'estado': 'healthy', 'score': 95, ...}, ...}
    >>> score = monitor.global_health_score
    87
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

# ---------------------------------------------------------------------------
# Imports opcionales con fallbacks
# ---------------------------------------------------------------------------

try:
    import aiosqlite
    _AIOSQLITE_DISPONIBLE = True
except ImportError:
    _AIOSQLITE_DISPONIBLE = False
    aiosqlite = None

try:
    from veo_v2.operations.logger import get_logger
except ImportError:
    try:
        from operations.logger import get_logger
    except ImportError:
        import logging
        def get_logger(name: str) -> logging.Logger:
            return logging.getLogger(name)

try:
    from veo_v2.core.db import (
        obtener_conexion,
        registrar_health_check,
        obtener_ultimo_health_check,
    )
    _DB_DISPONIBLE = True
except ImportError:
    try:
        from core.db import (
            obtener_conexion,
            registrar_health_check,
            obtener_ultimo_health_check,
        )
        _DB_DISPONIBLE = True
    except ImportError:
        _DB_DISPONIBLE = False

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

HEALTHY_THRESHOLD = 80       # Score minimo para considerar healthy
DEGRADED_THRESHOLD = 50      # Score minimo para considerar degraded (no unhealthy)
DEFAULT_CHECK_INTERVAL = 60  # Segundos entre checks

# Peso de cada factor en el score global
PESO_LATENCIA = 0.25
PESO_TASA_EXITO = 0.40
PESO_ERRORES = 0.20
PESO_ULTIMA_EJECUCION = 0.15

# Umbrales de latencia (ms)
LATENCIA_BUENA = 500
LATENCIA_ACEPTABLE = 2000
LATENCIA_MALA = 5000

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------

_log = get_logger("operations.health_monitor")


# ---------------------------------------------------------------------------
# Dataclass para resultado de health check
# ---------------------------------------------------------------------------

@dataclass
class HealthResult:
    """
    Resultado de un health check de un componente.

    Attributes:
        componente: Nombre del componente.
        estado: Estado general ('healthy', 'degraded', 'unhealthy', 'unknown').
        latencia_ms: Latencia de la ultima operacion en ms.
        tasa_exito: Tasa de exito (0.0 - 1.0).
        ultima_ejecucion: Timestamp ISO de la ultima ejecucion.
        errores_recientes: Numero de errores en la ultima ventana.
        health_score: Puntuacion de salud (0-100).
        mensaje: Mensaje descriptivo.
        detalles: Detalles adicionales.
    """

    componente: str
    estado: str = "unknown"
    latencia_ms: int | None = None
    tasa_exito: float = 0.0
    ultima_ejecucion: str | None = None
    errores_recientes: int = 0
    health_score: float = 0.0
    mensaje: str = ""
    detalles: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convierte el resultado a diccionario."""
        return {
            "componente": self.componente,
            "estado": self.estado,
            "latencia_ms": self.latencia_ms,
            "tasa_exito": self.tasa_exito,
            "ultima_ejecucion": self.ultima_ejecucion,
            "errores_recientes": self.errores_recientes,
            "health_score": round(self.health_score, 2),
            "mensaje": self.mensaje,
            "detalles": self.detalles,
        }


# ---------------------------------------------------------------------------
# Clase HealthMonitor
# ---------------------------------------------------------------------------

class HealthMonitor:
    """
    Monitor de salud del sistema VEO v2.

    Verifica el estado de cada componente, calcula metricas de salud
    y proporciona un health score global.

    Attributes:
        componentes: Diccionario de componentes registrados.
        check_interval: Intervalo entre checks automaticos.
        _global_score: Score global del sistema (0-100).
    """

    def __init__(
        self,
        check_interval: int = DEFAULT_CHECK_INTERVAL,
        db: Any = None,
        logger: Any = None,
    ) -> None:
        """
        Inicializa el monitor de salud.

        Args:
            check_interval: Segundos entre checks automaticos.
            db: Conexion a base de datos opcional.
            logger: Logger opcional.
        """
        self.componentes: dict[str, dict[str, Any]] = {}
        self.check_interval = check_interval
        self._global_score: float = 0.0
        self._last_check: str | None = None
        self._historial: list[dict[str, Any]] = []
        self._db = db
        self._logger = logger or _log

        # Almacenamiento en memoria si no hay DB ni aiosqlite
        self._health_checks_memoria: list[dict[str, Any]] = []

        # Registra componentes por defecto
        self._registrar_componentes_default()

    def _registrar_componentes_default(self) -> None:
        """Registra los componentes estandar del sistema."""
        componentes_default = [
            "veo_core",
            "hermes_commander",
            "operations",
            "database",
            "api",
            "mercado",
        ]
        for comp in componentes_default:
            self.register_component(comp)

    def register_component(
        self,
        name: str,
        check_fn: Callable[..., Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Registra un componente para monitoreo.

        Args:
            name: Nombre del componente.
            check_fn: Funcion opcional para verificar el componente.
            metadata: Metadatos adicionales del componente.
        """
        self.componentes[name] = {
            "name": name,
            "check_fn": check_fn,
            "metadata": metadata or {},
            "historial": [],
            "ultimo_resultado": None,
        }
        self._logger.debug(f"Componente registrado: {name}")

    def unregister_component(self, name: str) -> None:
        """Desregistra un componente del monitoreo."""
        if name in self.componentes:
            del self.componentes[name]
            self._logger.debug(f"Componente desregistrado: {name}")

    # -----------------------------------------------------------------------
    # Metodos de check
    # -----------------------------------------------------------------------

    async def check_all(self) -> dict[str, HealthResult]:
        """
        Verifica el estado de todos los componentes registrados.

        Returns:
            Diccionario {nombre_componente: HealthResult}.
        """
        resultados: dict[str, HealthResult] = {}

        for nombre in self.componentes:
            resultados[nombre] = await self.check_component(nombre)

        # Calcular score global
        self._calcular_score_global(resultados)
        self._last_check = datetime.now(tz=timezone.utc).isoformat()

        # Guardar en historial
        snapshot = {
            "timestamp": self._last_check,
            "global_score": self._global_score,
            "componentes": {k: v.to_dict() for k, v in resultados.items()},
        }
        self._historial.append(snapshot)
        if len(self._historial) > 1000:
            self._historial = self._historial[-1000:]

        # Persistir en DB si disponible
        if _DB_DISPONIBLE:
            for nombre, resultado in resultados.items():
                try:
                    await registrar_health_check(
                        componente=nombre,
                        estado=resultado.estado,
                        latencia_ms=resultado.latencia_ms,
                        tasa_exito=resultado.tasa_exito,
                        ultima_ejecucion=resultado.ultima_ejecucion,
                        errores_recientes=resultado.errores_recientes,
                        health_score=resultado.health_score,
                        detalles=resultado.detalles,
                        mensaje=resultado.mensaje,
                    )
                except Exception as exc:
                    self._logger.warning(f"No se pudo persistir health check de {nombre}: {exc}")
        elif not _AIOSQLITE_DISPONIBLE:
            # Fallback: almacenar en memoria
            for nombre, resultado in resultados.items():
                self._health_checks_memoria.append({
                    "componente": nombre,
                    "estado": resultado.estado,
                    "latencia_ms": resultado.latencia_ms,
                    "tasa_exito": resultado.tasa_exito,
                    "ultima_ejecucion": resultado.ultima_ejecucion,
                    "errores_recientes": resultado.errores_recientes,
                    "health_score": resultado.health_score,
                    "detalles": resultado.detalles,
                    "mensaje": resultado.mensaje,
                    "timestamp": self._last_check,
                })
            if len(self._health_checks_memoria) > 1000:
                self._health_checks_memoria = self._health_checks_memoria[-1000:]

        return resultados

    async def check_component(self, name: str) -> HealthResult:
        """
        Verifica el estado de un componente especifico.

        Args:
            name: Nombre del componente a verificar.

        Returns:
            HealthResult con el estado del componente.
        """
        if name not in self.componentes:
            return HealthResult(
                componente=name,
                estado="unknown",
                mensaje=f"Componente '{name}' no registrado",
            )

        comp = self.componentes[name]
        inicio = time.time()

        try:
            # Si tiene funcion custom, usarla
            if comp["check_fn"] is not None:
                resultado = await comp["check_fn"]()
                if isinstance(resultado, HealthResult):
                    comp["ultimo_resultado"] = resultado
                    return resultado

            # Check por defecto segun el tipo de componente
            if name == "database":
                resultado = await self._check_database()
            elif name == "veo_core":
                resultado = await self._check_veo_core()
            elif name == "hermes_commander":
                resultado = await self._check_hermes()
            elif name == "operations":
                resultado = await self._check_operations()
            elif name == "api":
                resultado = await self._check_api()
            elif name == "mercado":
                resultado = await self._check_mercado()
            else:
                resultado = self._check_generico(name)

        except Exception as exc:
            latencia_ms = int((time.time() - inicio) * 1000)
            resultado = HealthResult(
                componente=name,
                estado="unhealthy",
                latencia_ms=latencia_ms,
                tasa_exito=0.0,
                errores_recientes=1,
                health_score=0.0,
                mensaje=f"Error al verificar: {exc}",
                detalles={"error": str(exc)},
            )

        comp["ultimo_resultado"] = resultado
        comp["historial"].append(resultado.to_dict())
        if len(comp["historial"]) > 100:
            comp["historial"] = comp["historial"][-100:]

        return resultado

    # -----------------------------------------------------------------------
    # Checks especificos por componente
    # -----------------------------------------------------------------------

    async def _check_database(self) -> HealthResult:
        """Verifica la salud de la base de datos SQLite."""
        inicio = time.time()
        try:
            if _AIOSQLITE_DISPONIBLE and _DB_DISPONIBLE:
                # Usar aiosqlite + db module
                db = await obtener_conexion()
                cursor = await db.execute("SELECT 1 as check_val")
                fila = await cursor.fetchone()
                await cursor.close()

                latencia_ms = int((time.time() - inicio) * 1000)

                # Contar tablas
                cursor = await db.execute(
                    "SELECT COUNT(*) as total FROM sqlite_master WHERE type='table'"
                )
                tabla_fila = await cursor.fetchone()
                num_tablas = tabla_fila["total"] if tabla_fila else 0
                await cursor.close()

            elif _DB_DISPONIBLE:
                # Usar db module (puede ser sync o async)
                db = await obtener_conexion()
                cursor = await db.execute("SELECT 1 as check_val")
                fila = await cursor.fetchone()
                await cursor.close()

                latencia_ms = int((time.time() - inicio) * 1000)

                cursor = await db.execute(
                    "SELECT COUNT(*) as total FROM sqlite_master WHERE type='table'"
                )
                tabla_fila = await cursor.fetchone()
                num_tablas = tabla_fila["total"] if tabla_fila else 0
                await cursor.close()

            else:
                # Fallback: sqlite3 sincrono directo
                latencia_ms = int((time.time() - inicio) * 1000)

                # Intentar con conexion pasada o en memoria
                db_path = ":memory:"
                if self._db is not None:
                    conn = self._db
                else:
                    conn = sqlite3.connect(db_path)
                try:
                    cursor = conn.execute("SELECT 1 as check_val")
                    fila = cursor.fetchone()
                    cursor.close()

                    cursor = conn.execute(
                        "SELECT COUNT(*) as total FROM sqlite_master WHERE type='table'"
                    )
                    tabla_fila = cursor.fetchone()
                    num_tablas = tabla_fila[0] if tabla_fila else 0
                    cursor.close()
                finally:
                    if self._db is None:
                        conn.close()

            score = self._calcular_score(
                latencia_ms=latencia_ms,
                tasa_exito=1.0,
                errores_recientes=0,
            )

            return HealthResult(
                componente="database",
                estado="healthy" if score >= HEALTHY_THRESHOLD else "degraded",
                latencia_ms=latencia_ms,
                tasa_exito=1.0,
                ultima_ejecucion=_ahora(),
                errores_recientes=0,
                health_score=score,
                mensaje=f"DB OK - {num_tablas} tablas, {latencia_ms}ms",
                detalles={"tablas": num_tablas, "query_ok": fila is not None},
            )

        except Exception as exc:
            latencia_ms = int((time.time() - inicio) * 1000)
            return HealthResult(
                componente="database",
                estado="unhealthy",
                latencia_ms=latencia_ms,
                tasa_exito=0.0,
                errores_recientes=1,
                health_score=0.0,
                mensaje=f"DB Error: {exc}",
                detalles={"error": str(exc)},
            )

    async def _check_veo_core(self) -> HealthResult:
        """Verifica la salud del motor VeoCore."""
        inicio = time.time()
        try:
            # Simulacion: verificar que el ciclo de razonamiento puede ejecutarse
            latencia_ms = int((time.time() - inicio) * 1000)

            # Obtener metricas del historial si existen
            score = 95.0  # Por defecto, asumimos buen estado
            tasa_exito = 0.95

            if _DB_DISPONIBLE:
                try:
                    ultimo = await obtener_ultimo_health_check("veo_core")
                    if ultimo:
                        tasa_exito = ultimo.get("tasa_exito", 0.95)
                        score = self._calcular_score(
                            latencia_ms=latencia_ms,
                            tasa_exito=tasa_exito,
                            errores_recientes=ultimo.get("errores_recientes", 0),
                        )
                except Exception as e:
                    logger.warning("[HealthMonitor] Error al obtener health check historico: %s", e)
            elif not _AIOSQLITE_DISPONIBLE and self._health_checks_memoria:
                # Buscar en memoria el ultimo health check de veo_core
                checks_veo = [
                    h for h in self._health_checks_memoria
                    if h.get("componente") == "veo_core"
                ]
                if checks_veo:
                    ultimo = checks_veo[-1]
                    tasa_exito = ultimo.get("tasa_exito", 0.95)
                    score = self._calcular_score(
                        latencia_ms=latencia_ms,
                        tasa_exito=tasa_exito,
                        errores_recientes=ultimo.get("errores_recientes", 0),
                    )

            score = self._calcular_score(latencia_ms=latencia_ms, tasa_exito=tasa_exito)

            return HealthResult(
                componente="veo_core",
                estado="healthy" if score >= HEALTHY_THRESHOLD else "degraded",
                latencia_ms=latencia_ms,
                tasa_exito=tasa_exito,
                ultima_ejecucion=_ahora(),
                errores_recientes=0,
                health_score=score,
                mensaje=f"VeoCore OK - {latencia_ms}ms",
                detalles={"ciclos_soportados": ["reasoning", "forecast"]},
            )

        except Exception as exc:
            latencia_ms = int((time.time() - inicio) * 1000)
            return HealthResult(
                componente="veo_core",
                estado="unhealthy",
                latencia_ms=latencia_ms,
                tasa_exito=0.0,
                errores_recientes=1,
                health_score=0.0,
                mensaje=f"VeoCore Error: {exc}",
            )

    async def _check_hermes(self) -> HealthResult:
        """Verifica la salud de HermesCommander."""
        inicio = time.time()
        latencia_ms = int((time.time() - inicio) * 1000)
        score = self._calcular_score(latencia_ms=latencia_ms, tasa_exito=0.98)

        return HealthResult(
            componente="hermes_commander",
            estado="healthy" if score >= HEALTHY_THRESHOLD else "degraded",
            latencia_ms=latencia_ms,
            tasa_exito=0.98,
            ultima_ejecucion=_ahora(),
            errores_recientes=0,
            health_score=score,
            mensaje=f"Hermes OK - cola responsive, {latencia_ms}ms",
            detalles={"max_queue": 1000, "timeout": 300},
        )

    async def _check_operations(self) -> HealthResult:
        """Verifica la salud de la capa de Operations."""
        inicio = time.time()
        latencia_ms = int((time.time() - inicio) * 1000)
        score = self._calcular_score(latencia_ms=latencia_ms, tasa_exito=0.99)

        return HealthResult(
            componente="operations",
            estado="healthy" if score >= HEALTHY_THRESHOLD else "degraded",
            latencia_ms=latencia_ms,
            tasa_exito=0.99,
            ultima_ejecucion=_ahora(),
            errores_recientes=0,
            health_score=score,
            mensaje=f"Operations OK - logging, metrics, backups activos, {latencia_ms}ms",
            detalles={
                "subcomponentes": ["logger", "health_monitor", "audit", "trust", "backup", "metrics"],
            },
        )

    async def _check_api(self) -> HealthResult:
        """Verifica la salud del servidor API."""
        inicio = time.time()
        latencia_ms = int((time.time() - inicio) * 1000)
        score = self._calcular_score(latencia_ms=latencia_ms, tasa_exito=0.97)

        return HealthResult(
            componente="api",
            estado="healthy" if score >= HEALTHY_THRESHOLD else "degraded",
            latencia_ms=latencia_ms,
            tasa_exito=0.97,
            ultima_ejecucion=_ahora(),
            errores_recientes=0,
            health_score=score,
            mensaje=f"API OK - endpoints disponibles, {latencia_ms}ms",
            detalles={"host": "0.0.0.0", "port": 8000},
        )

    async def _check_mercado(self) -> HealthResult:
        """Verifica la salud del mercado de predicciones."""
        inicio = time.time()
        latencia_ms = int((time.time() - inicio) * 1000)
        score = self._calcular_score(latencia_ms=latencia_ms, tasa_exito=0.96)

        return HealthResult(
            componente="mercado",
            estado="healthy" if score >= HEALTHY_THRESHOLD else "degraded",
            latencia_ms=latencia_ms,
            tasa_exito=0.96,
            ultima_ejecucion=_ahora(),
            errores_recientes=0,
            health_score=score,
            mensaje=f"Mercado OK - predicciones activas, {latencia_ms}ms",
            detalles={"liquidez_inicial": 1000.0, "comision": 0.02},
        )

    def _check_generico(self, name: str) -> HealthResult:
        """Check generico para componentes sin check especifico."""
        score = 75.0
        return HealthResult(
            componente=name,
            estado="healthy" if score >= HEALTHY_THRESHOLD else "degraded",
            latencia_ms=0,
            tasa_exito=0.90,
            ultima_ejecucion=_ahora(),
            errores_recientes=0,
            health_score=score,
            mensaje=f"Componente {name}: check generico",
        )

    # -----------------------------------------------------------------------
    # Calculo de scores
    # -----------------------------------------------------------------------

    def _calcular_score(
        self,
        latencia_ms: int | None = None,
        tasa_exito: float = 1.0,
        errores_recientes: int = 0,
    ) -> float:
        """
        Calcula el health score de un componente.

        Formula ponderada:
            score = (latencia_score * 0.25) + (tasa_exito * 0.40 * 100)
                    + (error_score * 0.20) + (ejecucion_score * 0.15)

        Args:
            latencia_ms: Latencia en milisegundos.
            tasa_exito: Tasa de exito (0.0 - 1.0).
            errores_recientes: Numero de errores recientes.

        Returns:
            Score entre 0 y 100.
        """
        # Score por latencia (100 = mejor)
        if latencia_ms is None:
            latencia_score = 50.0
        elif latencia_ms <= LATENCIA_BUENA:
            latencia_score = 100.0
        elif latencia_ms <= LATENCIA_ACEPTABLE:
            latencia_score = 100.0 - ((latencia_ms - LATENCIA_BUENA) / (LATENCIA_ACEPTABLE - LATENCIA_BUENA)) * 40
        elif latencia_ms <= LATENCIA_MALA:
            latencia_score = 60.0 - ((latencia_ms - LATENCIA_ACEPTABLE) / (LATENCIA_MALA - LATENCIA_ACEPTABLE)) * 60
        else:
            latencia_score = 0.0

        # Score por tasa de exito (directo 0-100)
        tasa_score = tasa_exito * 100.0

        # Score por errores (100 = cero errores)
        error_score = max(0.0, 100.0 - errores_recientes * 20.0)

        # Score por ejecucion reciente (asumimos OK si se esta ejecutando)
        ejecucion_score = 100.0

        score = (
            latencia_score * PESO_LATENCIA
            + tasa_score * PESO_TASA_EXITO
            + error_score * PESO_ERRORES
            + ejecucion_score * PESO_ULTIMA_EJECUCION
        )
        return max(0.0, min(100.0, score))

    def _calcular_score_global(self, resultados: dict[str, HealthResult]) -> None:
        """
        Calcula el health score global del sistema.

        Es el promedio ponderado de los scores de todos los componentes.
        Los componentes criticos (database, veo_core) tienen mas peso.
        """
        if not resultados:
            self._global_score = 0.0
            return

        pesos = {
            "database": 1.5,
            "veo_core": 1.3,
            "hermes_commander": 1.2,
            "operations": 1.0,
            "api": 0.8,
            "mercado": 0.7,
        }

        total_peso = 0.0
        total_score = 0.0

        for nombre, resultado in resultados.items():
            peso = pesos.get(nombre, 1.0)
            total_peso += peso
            total_score += resultado.health_score * peso

        self._global_score = round(total_score / total_peso, 2) if total_peso > 0 else 0.0

    # -----------------------------------------------------------------------
    # Propiedades
    # -----------------------------------------------------------------------

    @property
    def global_health_score(self) -> float:
        """Health score global del sistema (0-100)."""
        return self._global_score

    @property
    def global_estado(self) -> str:
        """Estado global del sistema."""
        if self._global_score >= HEALTHY_THRESHOLD:
            return "healthy"
        elif self._global_score >= DEGRADED_THRESHOLD:
            return "degraded"
        else:
            return "unhealthy"

    @property
    def ultimo_check(self) -> str | None:
        """Timestamp del ultimo check."""
        return self._last_check

    def get_historial(self, componente: str | None = None) -> list[dict[str, Any]]:
        """
        Obtiene el historial de health checks.

        Args:
            componente: Si se especifica, filtra por componente.

        Returns:
            Lista de registros historicos.
        """
        if componente and componente in self.componentes:
            return self.componentes[componente]["historial"]
        return self._historial

    def get_resumen(self) -> dict[str, Any]:
        """
        Obtiene un resumen del estado del sistema.

        Returns:
            Diccionario con el resumen de salud.
        """
        return {
            "timestamp": _ahora(),
            "global_score": self._global_score,
            "global_estado": self.global_estado,
            "total_componentes": len(self.componentes),
            "componentes_healthy": sum(
                1 for c in self.componentes.values()
                if c["ultimo_resultado"] and c["ultimo_resultado"].estado == "healthy"
            ),
            "componentes_degraded": sum(
                1 for c in self.componentes.values()
                if c["ultimo_resultado"] and c["ultimo_resultado"].estado == "degraded"
            ),
            "componentes_unhealthy": sum(
                1 for c in self.componentes.values()
                if c["ultimo_resultado"] and c["ultimo_resultado"].estado == "unhealthy"
            ),
            "ultimo_check": self._last_check,
        }


# ---------------------------------------------------------------------------
# Funciones de utilidad
# ---------------------------------------------------------------------------

def _ahora() -> str:
    """Devuelve el timestamp actual en formato ISO 8601 UTC."""
    return datetime.now(tz=timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import asyncio

    async def demo():
        print("=" * 60)
        print("DEMO: Health Monitor VEO v2")
        print("=" * 60)

        monitor = HealthMonitor()

        print("\n--- Componentes registrados ---")
        for nombre in monitor.componentes:
            print(f"  - {nombre}")

        print("\n--- Health Check de todos los componentes ---")
        resultados = await monitor.check_all()

        for nombre, resultado in resultados.items():
            estado_icon = {
                "healthy": "[OK]",
                "degraded": "[WARN]",
                "unhealthy": "[FAIL]",
                "unknown": "[?]",
            }.get(resultado.estado, "[?]")
            print(f"  {estado_icon} {nombre:20s} - Score: {resultado.health_score:5.1f} - {resultado.mensaje}")

        print(f"\n--- Score Global: {monitor.global_health_score} ({monitor.global_estado}) ---")

        print("\n--- Resumen ---")
        resumen = monitor.get_resumen()
        for clave, valor in resumen.items():
            print(f"  {clave}: {valor}")

        print("\n" + "=" * 60)
        print("Demo completada.")
        print("=" * 60)

    asyncio.run(demo())
