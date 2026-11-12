# logger.py - VEO v2 Operations
"""
Sistema de logging estructurado en JSON para VEO v2 Operations.

Extiende el logger V1 con:
    - Log rotation por tamano (max 10MB, 5 backups)
    - Funciones especificas para ciclos: log_cycle_start, log_cycle_end
    - Funcion de auditoria: log_audit
    - Directorio de logs configurable (por defecto: logs/)

El formato JSON facilita el analisis automatizado de logs con herramientas
como jq, elasticsearch, o sistemas de observabilidad.

Ejemplo de uso:
    >>> from veo_v2.operations.logger import get_logger, log_cycle_start, log_cycle_end, log_audit
    >>> log = get_logger("operations.health")
    >>> log.info("Health check completado", extra={"score": 95})
    >>> log_cycle_start("reasoning", {"modulo": "veo_core"})
    >>> log_cycle_end("reasoning", {"status": "ok", "hipotesis": 3})
    >>> log_audit("crear_hipotesis", "usuario_1", {"texto": "Nueva hipotesis"})
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from rich.console import Console
    from rich.logging import RichHandler
    from rich.theme import Theme
    _RICH_DISPONIBLE = True
except ImportError:
    _RICH_DISPONIBLE = False

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

DEFAULT_LOG_DIR = "logs"
DEFAULT_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
DEFAULT_BACKUP_COUNT = 5
DEFAULT_LOG_LEVEL = logging.INFO

# Campos reservados que NO deben ir en el dict de extra
CAMPOS_RESERVADOS: frozenset[str] = frozenset(
    {
        "name", "msg", "args", "created", "msecs", "relativeCreated",
        "filename", "funcName", "lineno", "pathname", "module",
        "exc_info", "exc_text", "stack_info", "thread", "threadName",
        "process", "processName", "message", "asctime", "taskName",
    }
)


# ---------------------------------------------------------------------------
# Formateador JSON
# ---------------------------------------------------------------------------

class FormateadorJSON(logging.Formatter):
    """
    Formatea registros de logging como lineas JSON.

    Cada linea es un objeto JSON independiente (JSON Lines / NDJSON),
    lo que facilita el procesamiento con herramientas de streaming.
    """

    def __init__(
        self,
        campos_fijos: list[str] | None = None,
        indent: int | None = None,
    ) -> None:
        super().__init__()
        self.campos_fijos = campos_fijos or [
            "timestamp",
            "nivel",
            "logger",
            "modulo",
            "funcion",
            "linea",
            "mensaje",
            "hilo",
            "proceso",
        ]
        self.indent = indent

    def format(self, record: logging.LogRecord) -> str:
        """Convierte un LogRecord a una linea JSON."""
        try:
            ts = datetime.fromtimestamp(record.created, tz=timezone.utc)

            datos: dict[str, Any] = {
                "timestamp": ts.isoformat(),
                "nivel": record.levelname,
                "logger": record.name,
                "modulo": record.module,
                "funcion": record.funcName,
                "linea": record.lineno,
                "mensaje": record.getMessage(),
                "hilo": record.thread,
                "proceso": record.process,
            }

            if record.exc_info and record.exc_info[0] is not None:
                import traceback
                datos["excepcion"] = {
                    "tipo": record.exc_info[0].__name__,
                    "mensaje": str(record.exc_info[1]),
                    "traceback": traceback.format_exception(*record.exc_info),
                }

            # Extraer campos personalizados del record
            for attr in dir(record):
                if attr.startswith("_"):
                    continue
                if attr in CAMPOS_RESERVADOS:
                    continue
                if attr in ("timestamp", "nivel", "mensaje", "excepcion"):
                    continue
                try:
                    valor = getattr(record, attr)
                    if isinstance(valor, (str, int, float, bool, list, dict, type(None))):
                        datos[attr] = valor
                except (AttributeError, Exception):
                    continue

            return json.dumps(datos, ensure_ascii=False, default=str, indent=self.indent)

        except Exception as exc:
            return json.dumps(
                {
                    "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                    "nivel": "ERROR",
                    "logger": "FormateadorJSON",
                    "mensaje": f"Fallo al formatear log: {exc}",
                    "mensaje_original": str(record.msg),
                },
                ensure_ascii=False,
            )


# ---------------------------------------------------------------------------
# Handler con rotacion por tamano (NUEVO V2)
# ---------------------------------------------------------------------------

class HandlerRotativoTamanio(logging.handlers.RotatingFileHandler):
    """
    Handler que rota logs por tamano maximo en formato JSON line-delimited.

    Hereda de RotatingFileHandler para rotar automaticamente
    cuando el archivo supera el tamano maximo, manteniendo N backups.

    Attributes:
        max_bytes: Tamano maximo en bytes antes de rotar.
        backup_count: Numero de backups a conservar.
    """

    def __init__(
        self,
        ruta_archivo: str | Path,
        max_bytes: int = DEFAULT_MAX_BYTES,
        backup_count: int = DEFAULT_BACKUP_COUNT,
        **kwargs: Any,
    ) -> None:
        """
        Inicializa el handler rotativo por tamano.

        Args:
            ruta_archivo: Ruta al archivo de log.
            max_bytes: Tamano maximo en bytes (default 10MB).
            backup_count: Numero de backups a conservar (default 5).
            **kwargs: Argumentos adicionales para RotatingFileHandler.
        """
        ruta = Path(ruta_archivo)
        ruta.parent.mkdir(parents=True, exist_ok=True)

        super().__init__(
            filename=str(ruta),
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
            **kwargs,
        )
        self.setFormatter(FormateadorJSON())


# ---------------------------------------------------------------------------
# Handler con rotacion temporal (heredado V1)
# ---------------------------------------------------------------------------

class HandlerRotativoJSON(logging.handlers.TimedRotatingFileHandler):
    """
    Handler que rota logs diariamente en formato JSON line-delimited.
    Heredado de V1 para compatibilidad.
    """

    def __init__(
        self,
        ruta_archivo: str | Path,
        dias_retencion: int = 7,
        **kwargs: Any,
    ) -> None:
        ruta = Path(ruta_archivo)
        ruta.parent.mkdir(parents=True, exist_ok=True)

        super().__init__(
            filename=str(ruta),
            when="midnight",
            interval=1,
            backupCount=dias_retencion,
            encoding="utf-8",
            **kwargs,
        )
        self.setFormatter(FormateadorJSON())


# ---------------------------------------------------------------------------
# Configuracion de handlers
# ---------------------------------------------------------------------------

def _crear_handler_consola(nivel: int = logging.INFO) -> logging.Handler:
    """
    Crea un handler de consola con colores via Rich si esta disponible,
    o un handler estandar en caso contrario.

    Args:
        nivel: Nivel minimo de logging para este handler.

    Returns:
        Handler configurado.
    """
    if _RICH_DISPONIBLE:
        tema = Theme(
            {
                "logging.level.debug": "dim cyan",
                "logging.level.info": "green",
                "logging.level.warning": "yellow",
                "logging.level.error": "bold red",
                "logging.level.critical": "bold white on red",
            }
        )
        console = Console(theme=tema, stderr=False)

        handler = RichHandler(
            console=console,
            rich_tracebacks=True,
            tracebacks_show_locals=True,
            show_time=True,
            show_path=True,
            omit_repeated_times=False,
        )
        handler.setLevel(nivel)

        formato = logging.Formatter(
            fmt="%(name)s | %(message)s",
            datefmt="[%X]",
        )
        handler.setFormatter(formato)
        return handler
    else:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(nivel)
        formato = logging.Formatter(
            fmt="[%(asctime)s] %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formato)
        return handler


def _crear_handler_archivo_tamanio(
    ruta_archivo: str | Path,
    max_bytes: int = DEFAULT_MAX_BYTES,
    backup_count: int = DEFAULT_BACKUP_COUNT,
    nivel: int = logging.DEBUG,
) -> HandlerRotativoTamanio:
    """
    Crea un handler de archivo JSON con rotacion por tamano.

    Args:
        ruta_archivo: Ruta al archivo de log.
        max_bytes: Tamano maximo antes de rotar.
        backup_count: Numero de backups.
        nivel: Nivel minimo de logging.

    Returns:
        Handler configurado para escribir JSON line-delimited.
    """
    handler = HandlerRotativoTamanio(
        ruta_archivo=ruta_archivo,
        max_bytes=max_bytes,
        backup_count=backup_count,
    )
    handler.setLevel(nivel)
    return handler


def _crear_handler_archivo_temporal(
    ruta_archivo: str | Path,
    dias_retencion: int = 7,
    nivel: int = logging.DEBUG,
) -> HandlerRotativoJSON:
    """
    Crea un handler de archivo JSON con rotacion diaria (V1 compatible).

    Args:
        ruta_archivo: Ruta al archivo de log.
        dias_retencion: Dias de retencion de logs rotados.
        nivel: Nivel minimo de logging.

    Returns:
        Handler configurado para escribir JSON line-delimited.
    """
    handler = HandlerRotativoJSON(
        ruta_archivo=ruta_archivo,
        dias_retencion=dias_retencion,
    )
    handler.setLevel(nivel)
    return handler


# ---------------------------------------------------------------------------
# Cache de loggers
# ---------------------------------------------------------------------------

_loggers_configurados: dict[str, logging.Logger] = {}


def get_logger(
    nombre: str = "veo.v2",
    *,
    nivel: int | None = None,
    ruta_archivo: str | Path | None = None,
    max_bytes: int = DEFAULT_MAX_BYTES,
    backup_count: int = DEFAULT_BACKUP_COUNT,
    usar_consola: bool = True,
    usar_archivo: bool = True,
    rotacion_por_tamanio: bool = True,
) -> logging.Logger:
    """
    Obtiene un logger configurado con handlers de consola y/o archivo.

    Esta funcion cachea los loggers para evitar configuraciones duplicadas.

    Args:
        nombre: Nombre del logger (usar notacion de puntos para jerarquia).
        nivel: Nivel de logging (DEBUG, INFO, WARNING, ERROR). None = INFO.
        ruta_archivo: Ruta al archivo de log JSON. None = solo consola.
        max_bytes: Tamano maximo antes de rotar (solo rotacion por tamano).
        backup_count: Numero de backups a conservar.
        usar_consola: Si True, agrega handler de consola.
        usar_archivo: Si True, agrega handler de archivo JSON.
        rotacion_por_tamanio: Si True, usa rotacion por tamano; si False, por tiempo.

    Returns:
        Logger configurado listo para usar.

    Ejemplo:
        >>> log = get_logger("operations.health")
        >>> log.info("Check completado", extra={"score": 95})
    """
    nombre = nombre.strip() or "veo.v2"

    if nombre in _loggers_configurados:
        return _loggers_configurados[nombre]

    if nivel is None:
        import os
        nivel_env = os.environ.get("VEO_V2_LOG_NIVEL", "INFO").upper()
        nivel = getattr(logging, nivel_env, logging.INFO)

    logger = logging.getLogger(nombre)
    logger.setLevel(nivel)

    if logger.handlers:
        _loggers_configurados[nombre] = logger
        return logger

    logger.propagate = False

    if usar_consola:
        handler_consola = _crear_handler_consola(nivel=nivel)
        logger.addHandler(handler_consola)

    if usar_archivo and ruta_archivo is not None:
        if rotacion_por_tamanio:
            handler_archivo = _crear_handler_archivo_tamanio(
                ruta_archivo=ruta_archivo,
                max_bytes=max_bytes,
                backup_count=backup_count,
                nivel=logging.DEBUG,
            )
        else:
            handler_archivo = _crear_handler_archivo_temporal(
                ruta_archivo=ruta_archivo,
                dias_retencion=backup_count,
                nivel=logging.DEBUG,
            )
        logger.addHandler(handler_archivo)

    _loggers_configurados[nombre] = logger
    return logger


def get_logger_por_defecto(log_dir: str | Path = DEFAULT_LOG_DIR) -> logging.Logger:
    """
    Obtiene el logger por defecto de VEO v2 Operations.

    Args:
        log_dir: Directorio donde guardar los logs.

    Returns:
        Logger configurado con consola + archivo rotativo.
    """
    ruta = Path(log_dir)
    ruta.mkdir(parents=True, exist_ok=True)
    return get_logger(
        nombre="veo.v2.operations",
        ruta_archivo=ruta / "veo_v2_operations.log",
        max_bytes=DEFAULT_MAX_BYTES,
        backup_count=DEFAULT_BACKUP_COUNT,
    )


# ---------------------------------------------------------------------------
# Funciones de conveniencia para ciclos (NUEVO V2)
# ---------------------------------------------------------------------------

_logger_ciclos: logging.Logger | None = None


def _get_logger_ciclos() -> logging.Logger:
    """Obtiene o crea el logger de ciclos."""
    global _logger_ciclos
    if _logger_ciclos is None:
        _logger_ciclos = get_logger(
            nombre="veo.v2.ciclos",
            ruta_archivo=Path(DEFAULT_LOG_DIR) / "veo_v2_ciclos.log",
            max_bytes=DEFAULT_MAX_BYTES,
            backup_count=DEFAULT_BACKUP_COUNT,
        )
    return _logger_ciclos


def log_cycle_start(cycle_type: str, params: dict[str, Any] | None = None) -> None:
    """
    Registra el inicio de un ciclo de ejecucion.

    Args:
        cycle_type: Tipo de ciclo ('reasoning', 'forecast', 'executive', 'operations').
        params: Parametros del ciclo.

    Ejemplo:
        >>> log_cycle_start("reasoning", {"modulo": "veo_core", "tema": "IA"})
    """
    log = _get_logger_ciclos()
    log.info(
        f"Ciclo {cycle_type} iniciado",
        extra={
            "evento": "cycle_start",
            "cycle_type": cycle_type,
            "params": params or {},
            "timestamp_start": datetime.now(tz=timezone.utc).isoformat(),
        },
    )


def log_cycle_end(cycle_type: str, result_summary: dict[str, Any] | None = None) -> None:
    """
    Registra la finalizacion de un ciclo de ejecucion.

    Args:
        cycle_type: Tipo de ciclo.
        result_summary: Resumen del resultado del ciclo.

    Ejemplo:
        >>> log_cycle_end("reasoning", {"status": "ok", "hipotesis_generadas": 3})
    """
    log = _get_logger_ciclos()
    extra = {
        "evento": "cycle_end",
        "cycle_type": cycle_type,
        "timestamp_end": datetime.now(tz=timezone.utc).isoformat(),
    }
    if result_summary:
        extra.update(result_summary)

    status = (result_summary or {}).get("status", "unknown")
    if status == "ok" or status == "completed":
        log.info(f"Ciclo {cycle_type} completado", extra=extra)
    elif status == "failed":
        log.error(f"Ciclo {cycle_type} fallido", extra=extra)
    elif status == "timeout":
        log.warning(f"Ciclo {cycle_type} timeout", extra=extra)
    else:
        log.info(f"Ciclo {cycle_type} finalizado", extra=extra)


# ---------------------------------------------------------------------------
# Funcion de auditoria (NUEVO V2)
# ---------------------------------------------------------------------------

_logger_audit: logging.Logger | None = None


def _get_logger_audit() -> logging.Logger:
    """Obtiene o crea el logger de auditoria."""
    global _logger_audit
    if _logger_audit is None:
        ruta = Path(DEFAULT_LOG_DIR) / "audit"
        ruta.mkdir(parents=True, exist_ok=True)
        _logger_audit = get_logger(
            nombre="veo.v2.audit",
            ruta_archivo=ruta / "veo_v2_audit.log",
            max_bytes=DEFAULT_MAX_BYTES,
            backup_count=10,  # Mas backups para auditoria
        )
    return _logger_audit


def log_audit(action: str, user: str, details: dict[str, Any] | None = None) -> None:
    """
    Registra una accion de auditoria.

    Args:
        action: Nombre de la accion realizada.
        user: Usuario o modulo que realizo la accion.
        details: Detalles adicionales de la accion.

    Ejemplo:
        >>> log_audit("crear_hipotesis", "usuario_1", {"texto": "Nueva hipotesis", "confianza": 0.8})
    """
    log = _get_logger_audit()
    log.info(
        f"AUDIT: {action} por {user}",
        extra={
            "evento": "audit",
            "action": action,
            "user": user,
            "details": details or {},
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        },
    )


# ---------------------------------------------------------------------------
# Funcion de logging contextual
# ---------------------------------------------------------------------------

def log_con_contexto(
    logger: logging.Logger,
    nivel: str,
    mensaje: str,
    **kwargs: Any,
) -> None:
    """
    Escribe un log con campos extra automaticamente empaquetados.

    Args:
        logger: Logger a usar.
        nivel: Nivel del mensaje (debug, info, warning, error).
        mensaje: Texto del mensaje.
        **kwargs: Campos adicionales para el contexto estructurado.

    Ejemplo:
        >>> log_con_contexto(log, "info", "Hipotesis creada", tema="IA", confianza=0.8)
    """
    metodo = getattr(logger, nivel.lower(), logger.info)

    extra = {}
    for clave, valor in kwargs.items():
        if clave not in CAMPOS_RESERVADOS:
            if isinstance(valor, (str, int, float, bool, list, dict, type(None))):
                extra[clave] = valor

    if extra:
        metodo(mensaje, extra=extra)
    else:
        metodo(mensaje)


# ---------------------------------------------------------------------------
# Reset y utilidades
# ---------------------------------------------------------------------------

def reset_loggers() -> None:
    """
    Limpia todos los loggers cacheados.

    Util en tests para aislar la configuracion de logging
    entre casos de prueba.
    """
    global _loggers_configurados, _logger_ciclos, _logger_audit
    for nombre, logger in _loggers_configurados.items():
        for handler in logger.handlers[:]:
            handler.close()
            logger.removeHandler(handler)
    _loggers_configurados.clear()
    _logger_ciclos = None
    _logger_audit = None


def configurar_logging_raiz(nivel: int = logging.INFO) -> None:
    """
    Configura el logger raiz para capturar logs de librerias externas.

    Args:
        nivel: Nivel minimo de logging para el logger raiz.
    """
    handler = _crear_handler_consola(nivel)
    logging.basicConfig(
        level=nivel,
        format="%(name)s | %(message)s",
        datefmt="[%X]",
        handlers=[handler],
    )


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import tempfile

    print("=" * 60)
    print("DEMO: Logger VEO v2 Operations")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        log = get_logger(
            nombre="demo.operations",
            ruta_archivo=Path(tmpdir) / "demo.log",
            max_bytes=1024 * 1024,
            backup_count=3,
        )

        print("\n--- Logs de diferentes niveles ---")
        log.debug("Mensaje de debug", extra={"componente": "test", "valor": 42})
        log.info("Servicio iniciado correctamente", extra={"puerto": 8000})
        log.warning("Latencia alta detectada", extra={"latencia_ms": 2500})
        log.error("Error de conexion", extra={"host": "localhost", "reintentos": 3})

        print("\n--- Logs de ciclos ---")
        log_cycle_start("reasoning", {"modulo": "veo_core", "tema": "IA"})
        log_cycle_end("reasoning", {"status": "ok", "hipotesis_generadas": 3})

        log_cycle_start("forecast", {"periodo": "Q1 2025"})
        log_cycle_end("forecast", {"status": "completed", "predicciones": 12})

        print("\n--- Logs de auditoria ---")
        log_audit("crear_hipotesis", "usuario_admin", {"texto": "La IA cambiara el empleo", "confianza": 0.85})
        log_audit("actualizar_config", "sistema", {"parametro": "max_concurrent_tasks", "valor": 10})
        log_audit("backup_completado", "backup_manager", {"archivo": "sois_20250101.db", "tamano_mb": 45.2})

        print("\n--- Verificacion de archivos ---")
        log_path = Path(tmpdir)
        for f in sorted(log_path.glob("*.log*")):
            tamano = f.stat().st_size
            print(f"  {f.name}: {tamano} bytes")

    print("\n" + "=" * 60)
    print("Demo completada exitosamente.")
    print("=" * 60)
