# metrics_engine.py - VEO v2 Operations
"""
Motor de metricas para VEO v2.

La clase MetricsEngine recopila, almacena y agrega metricas del sistema.
Soporta metricas por ciclo, por motor, y metricas del sistema (CPU,
memoria, disco, uptime). Exporta datos para el dashboard.

Tipos de metricas soportadas:
    - gauge: Valor instantaneo (temperatura, porcentaje)
    - counter: Valor acumulativo (numero de peticiones)
    - histogram: Distribucion de valores (latencias)
    - summary: Resumen estadistico

Ejemplo de uso:
    >>> from operations.metrics_engine import MetricsEngine
    >>> metrics = MetricsEngine()
    >>> await metrics.record("hipotesis_creadas", 1, tags={"modulo": "veo_core"})
    >>> await metrics.record("cpu_usage", 45.2, tags={"fuente": "system"})
    >>> serie = await metrics.get_series("cpu_usage", start="2025-01-01T00:00:00")
    >>> dashboard = await metrics.get_dashboard_data()
"""

from __future__ import annotations

import json
import os
import platform
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from operations.logger import get_logger

try:
    from core.db import (
        registrar_metrica,
        obtener_serie_metrica,
        obtener_metricas_dashboard,
    )
    _DB_DISPONIBLE = True
except ImportError:
    _DB_DISPONIBLE = False

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

DEFAULT_METRICS_DIR = "metrics"
DEFAULT_MAX_METRICS_MEMORY = 10000

# Metricas estandar del sistema
METRICAS_CICLOS = [
    "reasoning_count",
    "forecast_count",
    "executive_count",
    "operations_count",
]

METRICAS_MOTOR_BASE = [
    "ejecuciones",
    "aciertos",
    "fallos",
    "latencia_promedio_ms",
    "latencia_max_ms",
    "latencia_min_ms",
]

METRICAS_SISTEMA = [
    "cpu_usage_percent",
    "memory_usage_percent",
    "memory_used_mb",
    "memory_total_mb",
    "disk_usage_percent",
    "disk_used_gb",
    "disk_total_gb",
    "uptime_seconds",
]

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------

_log = get_logger("operations.metrics")


# ---------------------------------------------------------------------------
# Clase MetricsEngine
# ---------------------------------------------------------------------------

class MetricsEngine:
    """
    Motor de metricas para VEO v2.

    Recopila, almacena y agrega metricas del sistema. Soporta persistencia
    en SQLite y exportacion a JSON.

    Attributes:
        metrics_dir: Directorio para exportacion JSON.
        buffer: Buffer en memoria de metricas recientes.
        persistir_en_db: Si se persiste en SQLite.
    """

    def __init__(
        self,
        metrics_dir: str | Path = DEFAULT_METRICS_DIR,
        persistir_en_db: bool = True,
    ) -> None:
        """
        Inicializa el motor de metricas.

        Args:
            metrics_dir: Directorio para exportacion JSON.
            persistir_en_db: Si True, persiste en SQLite.
        """
        self.metrics_dir = Path(metrics_dir)
        self.metrics_dir.mkdir(parents=True, exist_ok=True)
        self.persistir_en_db = persistir_en_db and _DB_DISPONIBLE

        # Buffer en memoria para metricas recientes
        self._buffer: list[dict[str, Any]] = []
        self._buffer_size = 100
        self._cache_series: dict[str, list[dict[str, Any]]] = {}

        # Contadores de ciclos
        self._cycle_counts: dict[str, int] = {
            "reasoning": 0,
            "forecast": 0,
            "executive": 0,
            "operations": 0,
        }

        # Contadores por motor
        self._motor_stats: dict[str, dict[str, Any]] = {}

        # Metricas del sistema cacheadas
        self._system_cache: dict[str, Any] = {}
        self._system_cache_time: float = 0.0
        self._system_cache_ttl: float = 30.0  # Segundos

    # -----------------------------------------------------------------------
    # Registro de metricas
    # -----------------------------------------------------------------------

    async def record(
        self,
        metric_name: str,
        value: float,
        tags: dict[str, str] | None = None,
        metric_type: str = "gauge",
        ciclo_type: str | None = None,
        modulo: str | None = None,
        fuente: str = "sistema",
    ) -> int:
        """
        Registra una metrica.

        Args:
            metric_name: Nombre de la metrica.
            value: Valor numerico.
            tags: Etiquetas adicionales.
            metric_type: Tipo ('gauge', 'counter', 'histogram', 'summary').
            ciclo_type: Ciclo asociado si aplica.
            modulo: Modulo asociado si aplica.
            fuente: Fuente de la metrica.

        Returns:
            ID del registro (o 0 si solo buffered).

        Ejemplo:
            >>> await metrics.record("hipotesis_creadas", 3,
            ...     tags={"estado": "activa"}, modulo="veo_core")
        """
        timestamp = _ahora()

        metrica = {
            "timestamp": timestamp,
            "metric_name": metric_name,
            "metric_value": value,
            "metric_type": metric_type,
            "tags": tags or {},
            "ciclo_type": ciclo_type,
            "modulo": modulo,
            "fuente": fuente,
        }

        # Agregar a buffer
        self._buffer.append(metrica)

        # Cachear serie
        if metric_name not in self._cache_series:
            self._cache_series[metric_name] = []
        self._cache_series[metric_name].append(metrica)
        if len(self._cache_series[metric_name]) > 1000:
            self._cache_series[metric_name] = self._cache_series[metric_name][-1000:]

        # Persistir en DB
        registro_id = 0
        if self.persistir_en_db:
            try:
                registro_id = await registrar_metrica(
                    metric_name=metric_name,
                    metric_value=value,
                    metric_type=metric_type,
                    tags=tags,
                    ciclo_type=ciclo_type,
                    modulo=modulo,
                    fuente=fuente,
                )
            except Exception as exc:
                _log.warning(f"Error persistiendo metrica: {exc}")

        # Flush buffer si es necesario
        if len(self._buffer) >= self._buffer_size:
            await self._flush_buffer()

        return registro_id

    async def record_cycle(self, ciclo_type: str, metric_name: str, value: float) -> int:
        """
        Registra una metrica asociada a un ciclo.

        Args:
            ciclo_type: Tipo de ciclo ('reasoning', 'forecast', 'executive', 'operations').
            metric_name: Nombre de la metrica.
            value: Valor.

        Returns:
            ID del registro.
        """
        if ciclo_type in self._cycle_counts:
            self._cycle_counts[ciclo_type] += 1

        return await self.record(
            metric_name=metric_name,
            value=value,
            ciclo_type=ciclo_type,
            metric_type="counter" if "count" in metric_name else "gauge",
        )

    async def record_motor(
        self,
        modulo: str,
        metric_name: str,
        value: float,
        tags: dict[str, str] | None = None,
    ) -> int:
        """
        Registra una metrica de un motor.

        Args:
            modulo: Nombre del motor/modulo.
            metric_name: Nombre de la metrica.
            value: Valor.
            tags: Etiquetas adicionales.

        Returns:
            ID del registro.
        """
        if modulo not in self._motor_stats:
            self._motor_stats[modulo] = {
                "ejecuciones": 0,
                "aciertos": 0,
                "fallos": 0,
                "latencias": [],
            }

        # Actualizar estadisticas del motor
        if metric_name == "ejecucion":
            self._motor_stats[modulo]["ejecuciones"] += 1
        elif metric_name == "acierto":
            self._motor_stats[modulo]["aciertos"] += 1
        elif metric_name == "fallo":
            self._motor_stats[modulo]["fallos"] += 1
        elif metric_name == "latencia_ms":
            self._motor_stats[modulo]["latencias"].append(value)
            if len(self._motor_stats[modulo]["latencias"]) > 100:
                self._motor_stats[modulo]["latencias"] = self._motor_stats[modulo]["latencias"][-100:]

        return await self.record(
            metric_name=f"{modulo}_{metric_name}",
            value=value,
            modulo=modulo,
            tags=tags,
        )

    async def record_system_metrics(self) -> dict[str, Any]:
        """
        Recopila y registra metricas del sistema (CPU, memoria, disco).

        Returns:
            Diccionario con las metricas registradas.
        """
        ahora = time.time()

        # Usar cache si es reciente
        if ahora - self._system_cache_time < self._system_cache_ttl and self._system_cache:
            return self._system_cache

        metricas: dict[str, Any] = {}

        try:
            # CPU
            metricas["cpu_usage_percent"] = self._get_cpu_usage()
            await self.record("cpu_usage_percent", metricas["cpu_usage_percent"], fuente="system")

            # Memoria
            mem_info = self._get_memory_usage()
            metricas.update(mem_info)
            await self.record("memory_usage_percent", mem_info["memory_usage_percent"], fuente="system")
            await self.record("memory_used_mb", mem_info["memory_used_mb"], fuente="system")

            # Disco
            disk_info = self._get_disk_usage()
            metricas.update(disk_info)
            await self.record("disk_usage_percent", disk_info["disk_usage_percent"], fuente="system")

            # Uptime
            metricas["uptime_seconds"] = self._get_uptime()
            await self.record("uptime_seconds", metricas["uptime_seconds"], metric_type="counter", fuente="system")

            self._system_cache = metricas
            self._system_cache_time = ahora

        except Exception as exc:
            _log.warning(f"Error recopilando metricas del sistema: {exc}")

        return metricas

    # -----------------------------------------------------------------------
    # Consultas
    # -----------------------------------------------------------------------

    async def get_series(
        self,
        metric_name: str,
        start: str | None = None,
        end: str | None = None,
        modulo: str | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """
        Obtiene una serie temporal de una metrica.

        Args:
            metric_name: Nombre de la metrica.
            start: Timestamp ISO de inicio.
            end: Timestamp ISO de fin.
            modulo: Filtrar por modulo.
            limit: Maximo de puntos.

        Returns:
            Lista de puntos de la serie temporal.
        """
        # Intentar DB primero
        if self.persistir_en_db:
            try:
                return await obtener_serie_metrica(
                    metric_name=metric_name,
                    start=start,
                    end=end,
                    modulo=modulo,
                    limite=limit,
                )
            except Exception as exc:
                _log.warning(f"Error consultando serie en DB: {exc}")

        # Fallback: cache en memoria
        series = self._cache_series.get(metric_name, [])

        if start:
            series = [s for s in series if s.get("timestamp", "") >= start]
        if end:
            series = [s for s in series if s.get("timestamp", "") <= end]
        if modulo:
            series = [s for s in series if s.get("modulo") == modulo]

        return series[:limit]

    async def get_dashboard_data(self) -> dict[str, Any]:
        """
        Obtiene datos agregados para el dashboard.

        Returns:
            Diccionario con datos para el dashboard.
        """
        # Intentar DB primero
        if self.persistir_en_db:
            try:
                db_data = await obtener_metricas_dashboard()
            except Exception:
                db_data = {}
        else:
            db_data = {}

        # Construir datos del dashboard
        dashboard: dict[str, Any] = {
            "timestamp": _ahora(),
            "ciclos": {},
            "motores": {},
            "sistema": {},
            "metricas_recientes": db_data.get("metricas_recientes", {}),
        }

        # Conteos de ciclos
        for ciclo in ["reasoning", "forecast", "executive", "operations"]:
            count = db_data.get(f"{ciclo}_count", self._cycle_counts[ciclo])
            dashboard["ciclos"][ciclo] = {
                "count": count,
                "ultima_ejecucion": None,
            }

        # Stats de motores
        for modulo, stats in self._motor_stats.items():
            latencias = stats.get("latencias", [])
            dashboard["motores"][modulo] = {
                "ejecuciones": stats.get("ejecuciones", 0),
                "aciertos": stats.get("aciertos", 0),
                "fallos": stats.get("fallos", 0),
                "tasa_exito": stats["aciertos"] / stats["ejecuciones"] if stats.get("ejecuciones", 0) > 0 else 0,
                "latencia_promedio_ms": sum(latencias) / len(latencias) if latencias else 0,
                "latencia_max_ms": max(latencias) if latencias else 0,
                "latencia_min_ms": min(latencias) if latencias else 0,
            }

        # Metricas del sistema
        sistema = await self.record_system_metrics()
        dashboard["sistema"] = sistema

        return dashboard

    # -----------------------------------------------------------------------
    # Exportacion
    # -----------------------------------------------------------------------

    async def export_to_json(
        self,
        filename: str | None = None,
        metricas: list[str] | None = None,
    ) -> Path:
        """
        Exporta metricas a JSON.

        Args:
            filename: Nombre del archivo (auto-generado si None).
            metricas: Lista de metricas a exportar (todas si None).

        Returns:
            Ruta al archivo exportado.
        """
        if filename is None:
            timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
            filename = f"metrics_export_{timestamp}.json"

        ruta = self.metrics_dir / filename

        # Recopilar datos
        datos: dict[str, Any] = {
            "timestamp_export": _ahora(),
            "metricas": {},
        }

        metricas_a_exportar = metricas or list(self._cache_series.keys())

        for nombre in metricas_a_exportar:
            serie = self._cache_series.get(nombre, [])
            datos["metricas"][nombre] = {
                "puntos": len(serie),
                "datos": serie[-100:],  # Ultimos 100 puntos
            }

        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2, default=str)

        _log.info(f"Metricas exportadas a {ruta}")
        return ruta

    async def export_dashboard_to_json(self, filename: str | None = None) -> Path:
        """
        Exporta datos del dashboard a JSON.

        Args:
            filename: Nombre del archivo.

        Returns:
            Ruta al archivo exportado.
        """
        if filename is None:
            timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
            filename = f"dashboard_{timestamp}.json"

        ruta = self.metrics_dir / filename
        dashboard = await self.get_dashboard_data()

        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(dashboard, f, ensure_ascii=False, indent=2, default=str)

        return ruta

    # -----------------------------------------------------------------------
    # Sistema helpers
    # -----------------------------------------------------------------------

    def _get_cpu_usage(self) -> float:
        """Obtiene el porcentaje de uso de CPU."""
        try:
            if hasattr(os, "getloadavg"):
                # Unix-like: usar loadavg como aproximacion
                load1, _, _ = os.getloadavg()
                num_cpus = os.cpu_count() or 1
                return min(100.0, (load1 / num_cpus) * 100.0)
        except (AttributeError, OSError):
            pass

        # Windows / fallback
        try:
            import psutil
            return psutil.cpu_percent(interval=0.1)
        except ImportError:
            return 0.0

    def _get_memory_usage(self) -> dict[str, float]:
        """Obtiene informacion de uso de memoria."""
        try:
            import psutil
            mem = psutil.virtual_memory()
            return {
                "memory_usage_percent": mem.percent,
                "memory_used_mb": mem.used / (1024 * 1024),
                "memory_total_mb": mem.total / (1024 * 1024),
            }
        except ImportError:
            return {
                "memory_usage_percent": 0.0,
                "memory_used_mb": 0.0,
                "memory_total_mb": 0.0,
            }

    def _get_disk_usage(self) -> dict[str, float]:
        """Obtiene informacion de uso de disco."""
        try:
            import psutil
            disk = psutil.disk_usage(str(self.metrics_dir))
            return {
                "disk_usage_percent": disk.percent,
                "disk_used_gb": disk.used / (1024 * 1024 * 1024),
                "disk_total_gb": disk.total / (1024 * 1024 * 1024),
            }
        except ImportError:
            return {
                "disk_usage_percent": 0.0,
                "disk_used_gb": 0.0,
                "disk_total_gb": 0.0,
            }

    def _get_uptime(self) -> float:
        """Obtiene el uptime del sistema en segundos."""
        try:
            import psutil
            return time.time() - psutil.boot_time()
        except ImportError:
            # Fallback: tiempo desde que se importo el modulo
            return 0.0

    # -----------------------------------------------------------------------
    # Buffer management
    # -----------------------------------------------------------------------

    async def _flush_buffer(self) -> None:
        """Limpia el buffer en memoria."""
        self._buffer.clear()

    # -----------------------------------------------------------------------
    # Metricas pre-definidas
    # -----------------------------------------------------------------------

    async def record_ciclo_inicio(self, ciclo_type: str) -> None:
        """Registra el inicio de un ciclo."""
        await self.record_cycle(ciclo_type, f"{ciclo_type}_inicios", 1)

    async def record_ciclo_completado(self, ciclo_type: str, duracion_ms: int) -> None:
        """Registra la finalizacion exitosa de un ciclo."""
        await self.record_cycle(ciclo_type, f"{ciclo_type}_completados", 1)
        await self.record(
            f"{ciclo_type}_duracion_ms",
            duracion_ms,
            ciclo_type=ciclo_type,
            metric_type="histogram",
        )

    async def record_ciclo_fallido(self, ciclo_type: str, error_type: str | None = None) -> None:
        """Registra un ciclo fallido."""
        await self.record_cycle(ciclo_type, f"{ciclo_type}_fallidos", 1)
        if error_type:
            await self.record(
                f"{ciclo_type}_error_type",
                1,
                ciclo_type=ciclo_type,
                tags={"error": error_type},
                metric_type="counter",
            )

    async def record_motor_ejecucion(
        self,
        modulo: str,
        exito: bool,
        latencia_ms: int | None = None,
        precision: float | None = None,
    ) -> None:
        """
        Registra una ejecucion de motor completa.

        Args:
            modulo: Nombre del motor.
            exito: True si fue exitosa.
            latencia_ms: Latencia en milisegundos.
            precision: Precision del resultado (0-1).
        """
        await self.record_motor(modulo, "ejecucion", 1)

        if exito:
            await self.record_motor(modulo, "acierto", 1)
        else:
            await self.record_motor(modulo, "fallo", 1)

        if latencia_ms is not None:
            await self.record_motor(modulo, "latencia_ms", latencia_ms)

        if precision is not None:
            await self.record(
                f"{modulo}_precision",
                precision,
                modulo=modulo,
            )


# ---------------------------------------------------------------------------
# Utilidades
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
        print("DEMO: Metrics Engine VEO v2")
        print("=" * 60)

        metrics = MetricsEngine()

        print("\n--- Registrando metricas de ciclos ---")
        await metrics.record_ciclo_inicio("reasoning")
        await metrics.record_ciclo_completado("reasoning", duracion_ms=1200)
        await metrics.record_ciclo_inicio("forecast")
        await metrics.record_ciclo_completado("forecast", duracion_ms=800)
        await metrics.record_ciclo_inicio("reasoning")
        await metrics.record_ciclo_fallido("reasoning", error_type="timeout")

        for ciclo in ["reasoning", "forecast", "executive", "operations"]:
            count = metrics._cycle_counts[ciclo]
            print(f"  {ciclo:15s}: {count} ejecuciones")

        print("\n--- Registrando metricas de motores ---")
        await metrics.record_motor_ejecucion("veo_core", exito=True, latencia_ms=250, precision=0.92)
        await metrics.record_motor_ejecucion("veo_core", exito=True, latencia_ms=180, precision=0.88)
        await metrics.record_motor_ejecucion("veo_core", exito=False, latencia_ms=5000)
        await metrics.record_motor_ejecucion("mercado", exito=True, latencia_ms=45, precision=0.95)

        for modulo, stats in metrics._motor_stats.items():
            latencias = stats.get("latencias", [])
            avg_lat = sum(latencias) / len(latencias) if latencias else 0
            tasa = stats["aciertos"] / stats["ejecuciones"] if stats.get("ejecuciones") else 0
            print(f"  {modulo:20s}: {stats['ejecuciones']} ejec, "
                  f"{stats['aciertos']} OK, {stats['fallos']} FAIL, "
                  f"tasa: {tasa:.0%}, lat_avg: {avg_lat:.0f}ms")

        print("\n--- Registrando metricas del sistema ---")
        sistema = await metrics.record_system_metrics()
        for clave, valor in sistema.items():
            print(f"  {clave}: {valor}")

        print("\n--- Datos del dashboard ---")
        dashboard = await metrics.get_dashboard_data()
        print(f"  Ciclos: {dashboard['ciclos']}")
        print(f"  Motores: {json.dumps(dashboard['motores'], indent=4)}")

        print("\n--- Exportando a JSON ---")
        ruta = await metrics.export_to_json()
        print(f"  Exportado: {ruta}")
        print(f"  Tamano: {ruta.stat().st_size} bytes")

        ruta_dash = await metrics.export_dashboard_to_json()
        print(f"  Dashboard: {ruta_dash}")

        print("\n--- Series temporales ---")
        serie = await metrics.get_series("cpu_usage_percent")
        print(f"  Serie cpu_usage_percent: {len(serie)} puntos")

        print("\n" + "=" * 60)
        print("Demo completada.")
        print("=" * 60)

    asyncio.run(demo())
