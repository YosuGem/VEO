# audit_log.py - VEO v2 Operations
# NOTA ARQUITECTONICA (v2.0.5): Este modulo es STANDALONE.
# VEOCore utiliza su propia implementacion interna de AuditLog definida
# en core/veo_core.py (linea 1543). Este archivo en operations/ no es
# importado ni utilizado en produccion por el sistema principal.
# HermesCommander importa AuditLogger desde aqui, pero VEOCore usa
# la version interna. Se mantiene como referencia y para tests independientes.
"""
Sistema de auditoria completo para VEO v2.

La clase AuditLogger registra TODAS las acciones del sistema
con trazabilidad completa: timestamp, usuario/modulo, accion,
parametros, resultado, duracion. Permite reconstruir cualquier
accion y consultar el historial con filtros.

Toda accion que modifique el estado del sistema debe ser registrada.
Las acciones de solo lectura pueden registrarse en modo verbose.

Ejemplo de uso:
    >>> from veo_v2.operations.audit_log import AuditLogger
    >>> audit = AuditLogger()
    >>> await audit.record("crear_hipotesis", "veo_core",
    ...     params={"texto": "Nueva hipotesis"},
    ...     result={"id": "h_001", "confianza": 0.8},
    ...     duration_ms=150)
    >>> registros = await audit.query({"modulo": "veo_core"})
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from operations.logger import get_logger, log_audit
except ImportError:
    import logging
    get_logger = lambda name: logging.getLogger(name)
    log_audit = lambda msg, **kwargs: None

try:
    from veo_v2.core.db import registrar_audit, consultar_audit
    _DB_DISPONIBLE = True
except ImportError:
    _DB_DISPONIBLE = False

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------

_log = get_logger("operations.audit")


# ---------------------------------------------------------------------------
# Dataclass para registro de auditoria
# ---------------------------------------------------------------------------

@dataclass
class AuditRecord:
    """
    Registro individual de auditoria.

    Attributes:
        id: Identificador unico del registro.
        timestamp: Fecha y hora ISO 8601 UTC.
        modulo: Modulo que realizo la accion.
        accion: Nombre de la accion.
        usuario: Usuario o entidad que realizo la accion.
        params: Parametros de entrada.
        resultado: Resultado de la accion.
        resultado_tipo: Tipo del resultado.
        duration_ms: Duracion en milisegundos.
        ip_address: Direccion IP si aplica.
        session_id: ID de sesion si aplica.
        detalles: Detalles adicionales.
    """

    timestamp: str
    modulo: str
    accion: str
    usuario: str = "sistema"
    params: dict[str, Any] | None = None
    resultado: Any = None
    resultado_tipo: str | None = None
    duration_ms: int | None = None
    ip_address: str | None = None
    session_id: str | None = None
    detalles: str | None = None
    id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convierte el registro a diccionario."""
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "modulo": self.modulo,
            "accion": self.accion,
            "usuario": self.usuario,
            "params": self.params,
            "resultado": self.resultado,
            "resultado_tipo": self.resultado_tipo,
            "duration_ms": self.duration_ms,
            "ip_address": self.ip_address,
            "session_id": self.session_id,
            "detalles": self.detalles,
        }

    def to_json(self) -> str:
        """Convierte el registro a JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)


# ---------------------------------------------------------------------------
# Clase AuditLogger
# ---------------------------------------------------------------------------

class AuditLogger:
    """
    Logger de auditoria para VEO v2.

    Registra todas las acciones del sistema con trazabilidad completa.
    Persiste en la base de datos (tabla audit_log) y opcionalmente
    en archivos de log.

    Attributes:
        buffer: Buffer temporal de registros antes de persistir.
        buffer_size: Tamano maximo del buffer.
        verbose: Si True, registra tambien acciones de lectura.
    """

    def __init__(
        self,
        buffer_size: int = 50,
        verbose: bool = False,
        persistir_en_db: bool = True,
    ) -> None:
        """
        Inicializa el logger de auditoria.

        Args:
            buffer_size: Tamano maximo del buffer antes de flush.
            verbose: Si True, registra tambien lecturas.
            persistir_en_db: Si True, persiste en SQLite.
        """
        self.buffer: list[AuditRecord] = []
        self.buffer_size = buffer_size
        self.verbose = verbose
        self.persistir_en_db = persistir_en_db and _DB_DISPONIBLE
        self._contador_registros: int = 0
        self._cache_memoria: list[dict[str, Any]] = []
        self._max_cache: int = 1000

    # -----------------------------------------------------------------------
    # Registro de acciones
    # -----------------------------------------------------------------------

    async def record(
        self,
        action: str,
        module: str,
        params: dict[str, Any] | None = None,
        result: Any = None,
        duration_ms: int | None = None,
        user: str = "sistema",
        result_type: str | None = None,
        ip_address: str | None = None,
        session_id: str | None = None,
        details: str | None = None,
    ) -> int:
        """
        Registra una accion en el audit log.

        Este es el metodo principal para registrar cualquier accion
        que modifique o consulte el estado del sistema.

        Args:
            action: Nombre de la accion (ej: "crear_hipotesis").
            module: Modulo que ejecuta la accion (ej: "veo_core").
            params: Parametros de entrada de la accion.
            result: Resultado de la accion.
            duration_ms: Duracion en milisegundos.
            user: Usuario o entidad que ejecuta la accion.
            result_type: Tipo del resultado.
            ip_address: Direccion IP si aplica.
            session_id: ID de sesion si aplica.
            details: Detalles adicionales.

        Returns:
            ID del registro creado (o 0 si solo se buffered).

        Ejemplo:
            >>> await audit.record(
            ...     action="crear_hipotesis",
            ...     module="veo_core",
            ...     params={"texto": "La IA cambiara el empleo"},
            ...     result={"id": "h_001", "confianza": 0.85},
            ...     duration_ms=230,
            ... )
        """
        timestamp = _ahora()

        record = AuditRecord(
            timestamp=timestamp,
            modulo=module,
            accion=action,
            usuario=user,
            params=params,
            resultado=result,
            resultado_tipo=result_type,
            duration_ms=duration_ms,
            ip_address=ip_address,
            session_id=session_id,
            detalles=details,
        )

        # Agregar al buffer
        self.buffer.append(record)
        self._contador_registros += 1

        # Agregar a cache en memoria
        dict_record = record.to_dict()
        dict_record["_seq"] = self._contador_registros
        self._cache_memoria.append(dict_record)
        if len(self._cache_memoria) > self._max_cache:
            self._cache_memoria = self._cache_memoria[-self._max_cache:]

        # Log en archivo - nunca dejar que el logging crashee el sistema
        try:
            log_audit(action, user, {
                "module": module,
                "params": params,
                "duration_ms": duration_ms,
            })
        except Exception as e:
            logger.warning("[AuditLog] Error al registrar entrada: %s", e)

        # Flush si el buffer esta lleno
        if len(self.buffer) >= self.buffer_size:
            await self.flush()

        return self._contador_registros

    async def record_read(
        self,
        action: str,
        module: str,
        params: dict[str, Any] | None = None,
        duration_ms: int | None = None,
        user: str = "sistema",
    ) -> int:
        """
        Registra una accion de lectura (solo si verbose=True).

        Args:
            action: Nombre de la accion.
            module: Modulo que ejecuta la accion.
            params: Parametros de la consulta.
            duration_ms: Duracion en ms.
            user: Usuario.

        Returns:
            ID del registro o 0 si verbose=False.
        """
        if not self.verbose:
            return 0
        return await self.record(
            action=action,
            module=module,
            params=params,
            duration_ms=duration_ms,
            user=user,
            result_type="read",
        )

    # -----------------------------------------------------------------------
    # Flush y persistencia
    # -----------------------------------------------------------------------

    async def flush(self) -> int:
        """
        Persiste todos los registros del buffer en la base de datos.

        Returns:
            Numero de registros persistidos.
        """
        if not self.buffer:
            return 0

        registros_flush = self.buffer[:]
        self.buffer.clear()

        if not self.persistir_en_db:
            return len(registros_flush)

        persistidos = 0
        for record in registros_flush:
            try:
                record_id = await registrar_audit(
                    modulo=record.modulo,
                    accion=record.accion,
                    usuario=record.usuario,
                    params=record.params,
                    resultado=record.resultado,
                    resultado_tipo=record.resultado_tipo,
                    duration_ms=record.duration_ms,
                    ip_address=record.ip_address,
                    session_id=record.session_id,
                    detalles=record.detalles,
                )
                record.id = record_id
                persistidos += 1
            except Exception as exc:
                _log.warning(f"No se pudo persistir audit log: {exc}")

        return persistidos

    # -----------------------------------------------------------------------
    # Consultas
    # -----------------------------------------------------------------------

    async def query(
        self,
        filters: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Busca registros en el audit log con filtros.

        Args:
            filters: Diccionario de filtros. Soporta:
                - modulo: Filtrar por modulo.
                - accion: Filtrar por accion.
                - usuario: Filtrar por usuario.
                - desde: Timestamp ISO minimo.
                - hasta: Timestamp ISO maximo.
            limit: Maximo de resultados.
            offset: Desplazamiento.

        Returns:
            Lista de registros que cumplen los filtros.

        Ejemplo:
            >>> registros = await audit.query({
            ...     "modulo": "veo_core",
            ...     "desde": "2025-01-01T00:00:00",
            ... })
        """
        # Primero hacer flush para asegurar datos actualizados
        if self.buffer:
            await self.flush()

        filtros = filters or {}

        # Consultar DB si disponible
        if self.persistir_en_db:
            try:
                return await consultar_audit(
                    modulo=filtros.get("modulo"),
                    accion=filtros.get("accion"),
                    usuario=filtros.get("usuario"),
                    desde=filtros.get("desde"),
                    hasta=filtros.get("hasta"),
                    limite=limit,
                    offset=offset,
                )
            except Exception as exc:
                _log.warning(f"Error consultando audit DB: {exc}. Usando cache memoria.")

        # Fallback: consultar cache en memoria
        return self._query_memoria(filtros, limit, offset)

    def _query_memoria(
        self,
        filters: dict[str, Any],
        limit: int,
        offset: int,
    ) -> list[dict[str, Any]]:
        """Consulta la cache en memoria con filtros."""
        resultados = self._cache_memoria[:]

        if filters.get("modulo"):
            resultados = [r for r in resultados if r.get("modulo") == filters["modulo"]]
        if filters.get("accion"):
            resultados = [r for r in resultados if r.get("accion") == filters["accion"]]
        if filters.get("usuario"):
            resultados = [r for r in resultados if r.get("usuario") == filters["usuario"]]
        if filters.get("desde"):
            resultados = [r for r in resultados if r.get("timestamp", "") >= filters["desde"]]
        if filters.get("hasta"):
            resultados = [r for r in resultados if r.get("timestamp", "") <= filters["hasta"]]

        # Ordenar por timestamp descendente y aplicar paginacion
        resultados.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return resultados[offset:offset + limit]

    async def get_recent(
        self,
        module: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Obtiene los registros mas recientes.

        Args:
            module: Filtrar por modulo.
            limit: Maximo de resultados.

        Returns:
            Lista de registros recientes.
        """
        return await self.query(
            filters={"modulo": module} if module else None,
            limit=limit,
        )

    async def get_by_action(
        self,
        action: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Obtiene registros por tipo de accion.

        Args:
            action: Nombre de la accion.
            limit: Maximo de resultados.

        Returns:
            Lista de registros de esa accion.
        """
        return await self.query({"accion": action}, limit=limit)

    async def get_by_user(
        self,
        user: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Obtiene registros por usuario.

        Args:
            user: Nombre del usuario.
            limit: Maximo de resultados.

        Returns:
            Lista de registros de ese usuario.
        """
        return await self.query({"usuario": user}, limit=limit)

    # -----------------------------------------------------------------------
    # Trazabilidad
    # -----------------------------------------------------------------------

    async def reconstruir_accion(
        self,
        action: str,
        timestamp: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Reconstruye una accion especifica a partir del audit log.

        Busca el registro mas reciente de la accion especificada y
        devuelve todos los detalles necesarios para reconstruirla.

        Args:
            action: Nombre de la accion a reconstruir.
            timestamp: Timestamp especifico si se conoce.

        Returns:
            Diccionario con los detalles de la accion, o None.
        """
        registros = await self.get_by_action(action, limit=1)
        if not registros:
            return None

        registro = registros[0]
        return {
            "reconstruccion": {
                "accion": registro.get("accion"),
                "modulo": registro.get("modulo"),
                "usuario": registro.get("usuario"),
                "timestamp": registro.get("timestamp"),
                "params_entrada": registro.get("params"),
                "resultado": registro.get("resultado"),
                "duracion_ms": registro.get("duration_ms"),
                "reconstruible": registro.get("params") is not None,
            }
        }

    async def estadisticas(self) -> dict[str, Any]:
        """
        Calcula estadisticas del audit log.

        Returns:
            Diccionario con estadisticas.
        """
        if self.persistir_en_db:
            try:
                todos = await consultar_audit(limit=10000)
            except Exception:
                todos = self._cache_memoria
        else:
            todos = self._cache_memoria

        if not todos:
            return {
                "total_registros": 0,
                "acciones_distintas": 0,
                "modulos_distintos": 0,
                "usuarios_distintos": 0,
            }

        acciones = set()
        modulos = set()
        usuarios = set()

        for r in todos:
            if r.get("accion"):
                acciones.add(r["accion"])
            if r.get("modulo"):
                modulos.add(r["modulo"])
            if r.get("usuario"):
                usuarios.add(r["usuario"])

        return {
            "total_registros": len(todos),
            "acciones_distintas": len(acciones),
            "modulos_distintos": len(modulos),
            "usuarios_distintos": len(usuarios),
            "acciones_top": sorted(acciones)[:20],
            "modulos_top": sorted(modulos)[:20],
            "pendientes_buffer": len(self.buffer),
        }

    # -----------------------------------------------------------------------
    # Context manager para auto-registro
    # -----------------------------------------------------------------------

    async def record_context(
        self,
        action: str,
        module: str,
        user: str = "sistema",
        params: dict[str, Any] | None = None,
    ):
        """
        Context manager para auto-registrar una accion con duracion.

        Args:
            action: Nombre de la accion.
            module: Modulo.
            user: Usuario.
            params: Parametros.

        Returns:
            Context manager que registra inicio y fin.

        Ejemplo:
            >>> async with audit.record_context("procesar_datos", "veo_core") as ctx:
            ...     resultado = await procesar()
            ...     ctx["resultado"] = resultado
        """
        return _AuditContext(self, action, module, user, params)


# ---------------------------------------------------------------------------
# Context manager interno
# ---------------------------------------------------------------------------

class _AuditContext:
    """Context manager para auto-registro de acciones con duracion."""

    def __init__(
        self,
        logger: AuditLogger,
        action: str,
        module: str,
        user: str,
        params: dict[str, Any] | None,
    ) -> None:
        self.logger = logger
        self.action = action
        self.module = module
        self.user = user
        self.params = params
        self.result: Any = None
        self.start_time: float = 0.0

    async def __aenter__(self):
        self.start_time = time.time()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        duration_ms = int((time.time() - self.start_time) * 1000)

        if exc_val:
            await self.logger.record(
                action=self.action,
                module=self.module,
                user=self.user,
                params=self.params,
                result={"error": str(exc_val), "tipo": exc_type.__name__ if exc_type else None},
                duration_ms=duration_ms,
                result_type="exception",
            )
        else:
            await self.logger.record(
                action=self.action,
                module=self.module,
                user=self.user,
                params=self.params,
                result=self.result if isinstance(self.result, dict) else {"value": str(self.result)},
                duration_ms=duration_ms,
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
        print("DEMO: Audit Logger VEO v2")
        print("=" * 60)

        audit = AuditLogger(buffer_size=5, verbose=True)

        print("\n--- Registrando acciones ---")

        # Acciones de ejemplo
        await audit.record(
            action="crear_hipotesis",
            module="veo_core",
            user="usuario_admin",
            params={"texto": "La IA cambiara el empleo radicalmente", "confianza_min": 0.6},
            result={"id": "h_001", "confianza": 0.85, "estado": "activa"},
            duration_ms=230,
        )

        await audit.record(
            action="validar_hipotesis",
            module="agente_cientifico",
            user="sistema",
            params={"hipotesis_id": "h_001"},
            result={"veredicto": "confirmada", "nivel_confianza": 0.92},
            duration_ms=1500,
        )

        await audit.record(
            action="crear_prediccion",
            module="mercado",
            user="agente_trader",
            params={"hipotesis_id": "h_001", "probabilidad": 0.75},
            result={"id": "p_001", "estado": "abierta"},
            duration_ms=45,
        )

        await audit.record(
            action="backup_database",
            module="operations",
            user="backup_manager",
            params={"tipo": "auto", "compresion": True},
            result={"archivo": "sois_20250101.db", "tamano_mb": 45.2},
            duration_ms=3200,
        )

        await audit.record_read(
            action="listar_hipotesis",
            module="veo_core",
            params={"estado": "activa", "limite": 100},
            duration_ms=12,
        )

        print(f"  Registros en buffer: {len(audit.buffer)}")
        print(f"  Registros en cache: {len(audit._cache_memoria)}")

        print("\n--- Flush ---")
        persistidos = await audit.flush()
        print(f"  Registros persistidos: {persistidos}")

        print("\n--- Cache en memoria ---")
        for r in audit._cache_memoria:
            print(f"  [{r['timestamp'][:19]}] {r['modulo']:20s} | {r['accion']:25s} | {r['usuario']:15s} | {r['duration_ms']}ms")

        print("\n--- Query por modulo ---")
        resultados = await audit.query({"modulo": "veo_core"}, limit=10)
        for r in resultados:
            print(f"  - {r['accion']} by {r['usuario']}: {r.get('resultado')}")

        print("\n--- Reconstruir accion ---")
        reconstruccion = await audit.reconstruir_accion("crear_hipotesis")
        if reconstruccion:
            print(f"  {json.dumps(reconstruccion, indent=2, ensure_ascii=False)}")

        print("\n--- Estadisticas ---")
        stats = await audit.estadisticas()
        for clave, valor in stats.items():
            print(f"  {clave}: {valor}")

        print("\n" + "=" * 60)
        print("Demo completada.")
        print("=" * 60)

    asyncio.run(demo())
