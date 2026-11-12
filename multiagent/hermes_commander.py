"""
hermes_commander.py - VEO v2
================================================================================

CAPA DE INTERFAZ UNIFICADA - El Comandante de VEO v2

Es el UNICO punto de entrada para comandos del sistema. Recibe ordenes de:
  - hermes_cli.py     (Typer CLI interactivo)
  - api_server.py     (FastAPI REST endpoints)
  - Dashboard React   (Frontend web)

Los valida, encola por prioridad, enruta a veo_core.py, y devuelve resultados.

REGLA OBLIGATORIA:
    NUNCA: Interfaz -> DB
    SIEMPRE: Interfaz -> HermesCommander -> veo_core

Patron de uso:
    >>> commander = HermesCommander()
    >>> await commander.start()
    >>> status = await commander.status()
    >>> result = await commander.run_reasoning(signals=[...], params={})
    >>> await commander.stop()

Arquitectura:
    - Cola de comandos asyncio.Queue con maxsize=100 y timeout
    - Tres niveles de prioridad: HIGH (alertas/health), MEDIUM (ciclos), LOW (consultas)
    - Logging estructurado JSON de TODOS los comandos via AuditLogger
    - Validacion de parametros antes de enviar a veo_core
    - Manejo graceful de errores con fallback informativo
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Imports stdlib
# ---------------------------------------------------------------------------
import asyncio
import copy
import json
import logging
import os
import random
import sys
import time
import traceback
import uuid
from collections import deque
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Awaitable,
    Callable,
    Deque,
    Dict,
    List,
    Optional,
    Tuple,
    Union,
)

# ---------------------------------------------------------------------------
# Paths del proyecto
# ---------------------------------------------------------------------------
V2_ROOT = Path(__file__).resolve().parent.parent
CORE_DIR = V2_ROOT / "core"
OPS_DIR = V2_ROOT / "operations"
MULTIAGENT_DIR = V2_ROOT / "multiagent"

if str(V2_ROOT) not in sys.path:
    sys.path.insert(0, str(V2_ROOT))

# ---------------------------------------------------------------------------
# Imports del proyecto VEO v2
# ---------------------------------------------------------------------------

try:
    from core.veo_core import VEOCore
    _VEO_CORE_DISPONIBLE = True
except ImportError:
    _VEO_CORE_DISPONIBLE = False

try:
    from operations.audit_log import AuditLogger
    _AUDIT_DISPONIBLE = True
except ImportError:
    _AUDIT_DISPONIBLE = False

try:
    from operations.logger import get_logger, log_cycle_start, log_cycle_end, log_audit
    _LOGGER_DISPONIBLE = True
except ImportError:
    _LOGGER_DISPONIBLE = False

try:
    from operations.health_monitor import HealthMonitor, HealthResult
    _HEALTH_DISPONIBLE = True
except ImportError:
    _HEALTH_DISPONIBLE = False

try:
    from analysis.planetary_configs import PLANETARY_CONFIGS
    _PLANETARY_CONFIGS_DISPONIBLE = True
except ImportError:
    PLANETARY_CONFIGS = {}  # type: ignore[assignment]
    _PLANETARY_CONFIGS_DISPONIBLE = False

# ---------------------------------------------------------------------------
# Imports de modulos de analisis (conexion real)
# ---------------------------------------------------------------------------

try:
    from analysis.hypothesis_engine import Hipotesis as HEHipotesis, MotorHipotesis
    _MOTOR_HIPOTESIS_DISPONIBLE = True
except ImportError as _e_mh:
    _MOTOR_HIPOTESIS_DISPONIBLE = False
    MotorHipotesis = None  # type: ignore[misc,assignment]
    HEHipotesis = None  # type: ignore[misc,assignment]

try:
    from analysis.scientific_agent import (
        Hipotesis as SAHipotesis,
        AgenteCientifico,
        AgenteEsceptico,
        CoordinadorValidacion,
    )
    _AGENTES_VALIDACION_DISPONIBLES = True
except ImportError as _e_av:
    _AGENTES_VALIDACION_DISPONIBLES = False
    SAHipotesis = None  # type: ignore[misc,assignment]
    AgenteCientifico = None  # type: ignore[misc,assignment]
    AgenteEsceptico = None  # type: ignore[misc,assignment]
    CoordinadorValidacion = None  # type: ignore[misc,assignment]

try:
    from analysis.scenario_simulator import (
        Hipotesis as SSHipotesis,
        SimuladorEscenarios,
        VariableEscenario,
        TipoEscenario,
        TipoDistribucion,
    )
    _SIMULADOR_ESCENARIOS_DISPONIBLE = True
except ImportError as _e_se:
    _SIMULADOR_ESCENARIOS_DISPONIBLE = False
    SSHipotesis = None  # type: ignore[misc,assignment]
    SimuladorEscenarios = None  # type: ignore[misc,assignment]
    VariableEscenario = None  # type: ignore[misc,assignment]
    TipoEscenario = None  # type: ignore[misc,assignment]
    TipoDistribucion = None  # type: ignore[misc,assignment]

# ---------------------------------------------------------------------------
# Logger global (para uso fuera de la clase)
# ---------------------------------------------------------------------------
logger = logging.getLogger("veo")

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

APP_NAME = "HermesCommander_v2"
LOG_PATH = V2_ROOT / "logs" / "hermes_commander.log"
DEFAULT_QUEUE_MAXSIZE = 100
DEFAULT_COMMAND_TIMEOUT = 300  # 5 minutos

for _p in (LOG_PATH.parent,):
    _p.mkdir(parents=True, exist_ok=True)


# ============================================================================
# PRIORIDADES DE COMANDO
# ============================================================================

class CommandPriority(Enum):
    """Niveles de prioridad para la cola de comandos."""
    HIGH = 1     # Alertas, health checks, emergencias
    MEDIUM = 2   # Ejecucion de ciclos, simulaciones
    LOW = 3      # Consultas, listados, estadisticas


# ============================================================================
# EXCEPCIONES CUSTOM
# ============================================================================

class HermesError(Exception):
    """Error base del HermesCommander."""
    pass


class HermesValidationError(HermesError):
    """Error de validacion de parametros."""
    pass


class HermesQueueFullError(HermesError):
    """La cola de comandos esta llena."""
    pass


class HermesTimeoutError(HermesError):
    """Timeout al ejecutar un comando."""
    pass


class HermesNotRunningError(HermesError):
    """El commander no esta en ejecucion."""
    pass


# ============================================================================
# COMANDO (dataclass interna)
# ============================================================================

class Command:
    """
    Representa un comando encolado para ejecucion.

    Attributes:
        id: Identificador unico del comando.
        name: Nombre del comando (ej: "run_reasoning").
        priority: Nivel de prioridad (HIGH/MEDIUM/LOW).
        params: Parametros del comando.
        future: asyncio.Future para comunicar el resultado.
        timestamp: Cuando se creo el comando.
        caller: Quien invoco el comando (modulo/usuario).
    """

    def __init__(
        self,
        name: str,
        priority: CommandPriority,
        params: dict[str, Any],
        caller: str = "sistema",
    ) -> None:
        self.id = f"cmd_{uuid.uuid4().hex[:8]}"
        self.name = name
        self.priority = priority
        self.params = params
        self.future: asyncio.Future = asyncio.get_event_loop().create_future()
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.caller = caller

    def __lt__(self, other: "Command") -> bool:
        """Para ordenar en la cola por prioridad."""
        return self.priority.value < other.priority.value

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "priority": self.priority.name,
            "timestamp": self.timestamp,
            "caller": self.caller,
            "params_keys": list(self.params.keys()),
        }


# ============================================================================
# VALIDADOR DE PARAMETROS
# ============================================================================

class ParamValidator:
    """
    Valida parametros de entrada antes de enviarlos a veo_core.

    Centraliza todas las reglas de validacion para evitar
    propagar datos malformados al nucleo del sistema.
    """

    @staticmethod
    def validate_signals(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Valida que las senales tengan el formato correcto."""
        if not isinstance(signals, list):
            raise HermesValidationError("'signals' debe ser una lista")
        validated = []
        for i, sig in enumerate(signals):
            if not isinstance(sig, dict):
                raise HermesValidationError(f"Signal #{i} debe ser un diccionario")
            if "text" not in sig:
                raise HermesValidationError(f"Signal #{i} falta campo 'text'")
            # Normalizar campos numericos
            vsig = dict(sig)
            for field in ("urgency", "confidence", "impact"):
                if field in vsig:
                    try:
                        vsig[field] = int(vsig[field])
                    except (ValueError, TypeError):
                        vsig[field] = 50
                else:
                    vsig[field] = 50
            validated.append(vsig)
        return validated

    @staticmethod
    def validate_hypothesis_text(text: str) -> str:
        """Valida el texto de una hipotesis."""
        if not text or not isinstance(text, str):
            raise HermesValidationError("El texto de la hipotesis es obligatorio y debe ser string")
        text = text.strip()
        if len(text) < 10:
            raise HermesValidationError("El texto de la hipotesis debe tener al menos 10 caracteres")
        if len(text) > 2000:
            raise HermesValidationError("El texto de la hipotesis excede 2000 caracteres")
        return text

    @staticmethod
    def validate_confidence(confidence: float) -> float:
        """Valida un valor de confianza 0.0 - 1.0."""
        try:
            c = float(confidence)
        except (ValueError, TypeError):
            c = 0.5
        return max(0.0, min(1.0, c))

    @staticmethod
    def validate_id(entity_id: str, entity_name: str = "entidad") -> str:
        """Valida un identificador."""
        if not entity_id or not isinstance(entity_id, str):
            raise HermesValidationError(f"ID de {entity_name} es obligatorio")
        return entity_id.strip()

    @staticmethod
    def validate_positive_int(value: Any, name: str, default: int = 1) -> int:
        """Valida un entero positivo."""
        try:
            v = int(value)
            if v < 1:
                v = default
        except (ValueError, TypeError):
            v = default
        return v

    @staticmethod
    def validate_filters(filters: dict[str, Any] | None) -> dict[str, Any]:
        """Valida y normaliza filtros de consulta."""
        if filters is None:
            return {}
        if not isinstance(filters, dict):
            return {}
        # Eliminar claves vacias o peligrosas
        safe = {}
        for k, v in filters.items():
            if isinstance(k, str) and k.strip():
                safe[k.strip()] = v
        return safe


# ============================================================================
# HERMESCOMMANDER - CLASE PRINCIPAL
# ============================================================================

class HermesCommander:
    """
    ╔══════════════════════════════════════════════════════════════════════════╗
    ║                    H E R M E S   C O M M A N D E R   v2                ║
    ║                  Interfaz Unificada de VEO v2                          ║
    ╚══════════════════════════════════════════════════════════════════════════╝

    El Comandante es el UNICO punto de entrada para comandos del sistema.
    Recibe ordenes de la CLI, API REST o Dashboard, los valida, encola
    por prioridad, los enruta a veo_core, y devuelve resultados.

    REGLA OBLIGATORIA:
        NUNCA: Interfaz -> DB
        SIEMPRE: Interfaz -> HermesCommander -> veo_core

    Attributes:
        _core: Instancia de VEOCore (el cerebro).
        _queue: Cola de comandos asyncio con prioridad.
        _audit: AuditLogger para trazabilidad completa.
        _logger: Logger estructurado JSON.
        _health_monitor: Monitor de salud del sistema.
        _running: Si el commander esta activo.
        _command_history: Historial de comandos ejecutados.
    """

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        max_queue_size: int = DEFAULT_QUEUE_MAXSIZE,
        command_timeout: int = DEFAULT_COMMAND_TIMEOUT,
    ) -> None:
        """
        Inicializa el HermesCommander.

        Args:
            config: Configuracion del sistema (pasa a VEOCore).
            max_queue_size: Tamano maximo de la cola de comandos.
            command_timeout: Timeout por defecto para comandos (segundos).
        """
        self.config = config or {}
        self.max_queue_size = max_queue_size
        self.command_timeout = command_timeout
        self._running = False
        self._core: VEOCore | None = None
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue(maxsize=max_queue_size)
        self._command_history: Deque[dict[str, Any]] = deque(maxlen=1000)
        self._command_stats: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

        # Logger
        if _LOGGER_DISPONIBLE:
            self._logger = get_logger(
                "multiagent.hermes",
                ruta_archivo=LOG_PATH,
                max_bytes=10 * 1024 * 1024,
                backup_count=5,
            )
        else:
            import logging
            self._logger = logging.getLogger("multiagent.hermes")

        # Audit logger
        if _AUDIT_DISPONIBLE:
            self._audit = AuditLogger(buffer_size=20, verbose=False)
        else:
            self._audit = None  # type: ignore[assignment]

        # Health monitor propio del commander
        if _HEALTH_DISPONIBLE:
            self._health_monitor = HealthMonitor()
        else:
            self._health_monitor = None

        # Workers
        self._worker_tasks: list[asyncio.Task] = []
        self._num_workers = 2

        self._logger.info("HermesCommander inicializado", extra={
            "queue_size": max_queue_size,
            "timeout": command_timeout,
            "veo_core_disponible": _VEO_CORE_DISPONIBLE,
        })

    # -----------------------------------------------------------------------
    # PROPIEDADES
    # -----------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        """Devuelve True si el commander esta en ejecucion."""
        return self._running

    @property
    def core_available(self) -> bool:
        """Devuelve True si VEOCore esta disponible y funcionando."""
        return self._core is not None and getattr(self._core, '_running', False)

    # -----------------------------------------------------------------------
    # LIFECYCLE: start / stop
    # -----------------------------------------------------------------------

    async def start(self) -> dict[str, Any]:
        """
        Inicia el HermesCommander: lanza veo_core, health monitor, scheduler y workers.

        Returns:
            Dict con el resultado del inicio.
        """
        t0 = time.time()
        self._logger.info("HermesCommander iniciando...")

        try:
            # Inicializar VEOCore
            if _VEO_CORE_DISPONIBLE:
                self._core = VEOCore(self.config)
                await self._core.start()
                self._logger.info("VEOCore iniciado correctamente")
            else:
                self._logger.warning("VEOCore no disponible - modo degradado")
                self._core = None

            # Inicializar health monitor
            if self._health_monitor:
                # Registrar check propio
                self._health_monitor.register_component(
                    "hermes_commander",
                    self._self_health_check,
                )
                self._logger.info("HealthMonitor registrado")

            # Arrancar workers de procesamiento de comandos
            self._running = True
            for i in range(self._num_workers):
                task = asyncio.create_task(self._command_worker(f"worker_{i}"))
                self._worker_tasks.append(task)

            elapsed_ms = int((time.time() - t0) * 1000)

            # Registrar en audit
            if self._audit:
                await self._audit.record(
                    action="hermes_start",
                    module="hermes_commander",
                    params={"config_keys": list(self.config.keys())},
                    result={"status": "ok", "veo_core": self.core_available},
                    duration_ms=elapsed_ms,
                )

            self._logger.info("HermesCommander iniciado correctamente", extra={
                "elapsed_ms": elapsed_ms,
                "workers": self._num_workers,
            })

            return {
                "status": "ok",
                "message": "HermesCommander iniciado",
                "veo_core": self.core_available,
                "elapsed_ms": elapsed_ms,
            }

        except Exception as exc:
            self._logger.error("Error al iniciar HermesCommander: %s", exc, exc_info=True)
            self._running = False
            return {
                "status": "error",
                "message": f"Error al iniciar: {exc}",
                "error_type": type(exc).__name__,
            }

    async def stop(self) -> dict[str, Any]:
        """
        Parada graceful de todo el sistema.

        Returns:
            Dict con el resultado de la parada.
        """
        t0 = time.time()
        self._logger.info("HermesCommander deteniendose...")

        self._running = False

        # Cancelar workers
        for task in self._worker_tasks:
            task.cancel()
        for task in self._worker_tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._worker_tasks.clear()

        # Detener VEOCore
        if self._core:
            try:
                await self._core.stop()
                self._logger.info("VEOCore detenido")
            except Exception as exc:
                self._logger.error("Error al detener VEOCore: %s", exc)

        # Flush audit
        if self._audit:
            try:
                await self._audit.flush()
            except Exception as exc:
                self._logger.warning("Error al hacer flush de audit: %s", exc)

        elapsed_ms = int((time.time() - t0) * 1000)

        if self._audit:
            await self._audit.record(
                action="hermes_stop",
                module="hermes_commander",
                result={"status": "ok"},
                duration_ms=elapsed_ms,
            )

        self._logger.info("HermesCommander detenido", extra={"elapsed_ms": elapsed_ms})

        return {
            "status": "ok",
            "message": "HermesCommander detenido",
            "elapsed_ms": elapsed_ms,
        }

    # -----------------------------------------------------------------------
    # WORKER DE COMANDOS
    # -----------------------------------------------------------------------

    async def _command_worker(self, worker_id: str) -> None:
        """
        Worker que procesa comandos de la cola.

        Corre en bucle infinito hasta que _running es False.
        Toma comandos de la cola, los ejecuta, y resuelve el future.
        """
        self._logger.info(f"Worker {worker_id} iniciado")

        while self._running:
            try:
                # Esperar comando con timeout
                priority, command = await asyncio.wait_for(
                    self._queue.get(), timeout=1.0
                )
            except asyncio.TimeoutError:
                continue
            except Exception as exc:
                self._logger.error(f"Worker {worker_id} error en queue.get: {exc}")
                continue

            t0 = time.time()
            self._logger.debug(f"Worker {worker_id} procesando: {command.name}")

            try:
                # Ejecutar el comando
                result = await self._execute_command(command)
                elapsed_ms = int((time.time() - t0) * 1000)

                # Resolver el future con exito
                if not command.future.done():
                    command.future.set_result(result)

                # Registrar en historial
                self._command_history.append({
                    "command": command.to_dict(),
                    "result_status": result.get("status", "unknown"),
                    "elapsed_ms": elapsed_ms,
                })

            except Exception as exc:
                elapsed_ms = int((time.time() - t0) * 1000)
                error_result = {
                    "status": "error",
                    "message": str(exc),
                    "error_type": type(exc).__name__,
                    "traceback": traceback.format_exc(),
                }

                if not command.future.done():
                    command.future.set_result(error_result)

                self._logger.error(
                    f"Error ejecutando {command.name}: {exc}",
                    extra={"command": command.name, "error": str(exc)},
                )

            finally:
                self._queue.task_done()

        self._logger.info(f"Worker {worker_id} detenido")

    async def _execute_command(self, command: Command) -> dict[str, Any]:
        """
        Ejecuta un comando especifico despachando al metodo correspondiente.

        Args:
            command: El comando a ejecutar.

        Returns:
            Dict con el resultado.
        """
        method_name = f"_cmd_{command.name}"
        method = getattr(self, method_name, None)

        if method is None:
            return {
                "status": "error",
                "message": f"Comando desconocido: {command.name}",
                "available_commands": self._list_available_commands(),
            }

        # Verificar que el sistema esta corriendo (excepto para comandos especiales)
        if not self._running and command.name not in ("status", "health"):
            raise HermesNotRunningError("HermesCommander no esta en ejecucion. Llame start() primero.")

        return await method(command.params)

    def _list_available_commands(self) -> list[str]:
        """Lista todos los comandos disponibles."""
        commands = []
        for attr_name in dir(self):
            if attr_name.startswith("_cmd_"):
                commands.append(attr_name[5:])  # Remover _cmd_ prefix
        return sorted(commands)

    # -----------------------------------------------------------------------
    # ENCOLADO DE COMANDOS (metodo interno)
    # -----------------------------------------------------------------------

    async def _enqueue(
        self,
        name: str,
        priority: CommandPriority,
        params: dict[str, Any],
        caller: str = "sistema",
        timeout: int | None = None,
    ) -> dict[str, Any]:
        """
        Encola un comando y espera su resultado.

        Args:
            name: Nombre del comando.
            priority: Prioridad del comando.
            params: Parametros del comando.
            caller: Quien invoca el comando.
            timeout: Timeout en segundos (None = usar default).

        Returns:
            Dict con el resultado del comando.

        Raises:
            HermesQueueFullError: Si la cola esta llena.
            HermesTimeoutError: Si el comando excede el timeout.
        """
        timeout = timeout or self.command_timeout

        # Verificar que la cola no este llena
        if self._queue.qsize() >= self.max_queue_size - 1:
            raise HermesQueueFullError(
                f"Cola de comandos llena ({self._queue.qsize()}/{self.max_queue_size})"
            )

        command = Command(name=name, priority=priority, params=params, caller=caller)

        # Insertar en cola (usando priority value para orden)
        await self._queue.put((priority.value, command))

        # Registrar en audit
        if self._audit:
            await self._audit.record_read(
                action=f"cmd_{name}_enqueued",
                module="hermes_commander",
                params=command.to_dict(),
            )

        # Esperar resultado con timeout
        try:
            result = await asyncio.wait_for(command.future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            if not command.future.done():
                command.future.cancel()
            raise HermesTimeoutError(
                f"Comando '{name}' excedio timeout de {timeout}s"
            )

    # ============================================================================
    # METODOS PUBLICOS - INTERFAZ DEL COMMANDER
    # ============================================================================

    # -----------------------------------------------------------------------
    # Gestion del sistema
    # -----------------------------------------------------------------------

    async def status(self) -> dict[str, Any]:
        """
        Estado completo del sistema: salud, ciclos, metricas.

        Returns:
            Dict con el estado completo.
        """
        return await self._enqueue(
            name="status",
            priority=CommandPriority.LOW,
            params={},
            caller="api",
        )

    async def health(self) -> dict[str, Any]:
        """
        Health check de todos los componentes.

        Returns:
            Dict con el estado de salud de cada componente.
        """
        return await self._enqueue(
            name="health",
            priority=CommandPriority.HIGH,
            params={},
            caller="api",
        )

    # -----------------------------------------------------------------------
    # Ciclos
    # -----------------------------------------------------------------------

    async def run_reasoning(
        self,
        signals: list[dict[str, Any]] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Ejecuta el ciclo de razonamiento.

        Args:
            signals: Lista de senales de entrada (opcional).
            params: Parametros adicionales.

        Returns:
            Dict con los resultados del ciclo.
        """
        return await self._enqueue(
            name="run_reasoning",
            priority=CommandPriority.MEDIUM,
            params={"signals": signals, "params": params or {}},
            caller="cli",
        )

    async def run_forecast(
        self,
        hypothesis_ids: list[str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Ejecuta el ciclo de pronostico.

        Args:
            hypothesis_ids: IDs de hipotesis a pronosticar.
            params: Parametros adicionales.

        Returns:
            Dict con los resultados del ciclo.
        """
        return await self._enqueue(
            name="run_forecast",
            priority=CommandPriority.MEDIUM,
            params={"hypothesis_ids": hypothesis_ids, "params": params or {}},
            caller="cli",
        )

    async def run_executive(
        self,
        items: list[dict[str, Any]] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Ejecuta el ciclo ejecutivo.

        Args:
            items: Items a priorizar.
            params: Parametros adicionales.

        Returns:
            Dict con los resultados del ciclo.
        """
        return await self._enqueue(
            name="run_executive",
            priority=CommandPriority.MEDIUM,
            params={"items": items, "params": params or {}},
            caller="cli",
        )

    async def run_operations(self, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Ejecuta el ciclo de operaciones.

        Args:
            params: Parametros adicionales.

        Returns:
            Dict con los resultados del ciclo.
        """
        return await self._enqueue(
            name="run_operations",
            priority=CommandPriority.MEDIUM,
            params={"params": params or {}},
            caller="cli",
        )

    async def trigger_cycle(self, cycle_type: str) -> dict[str, Any]:
        """
        Ejecuta un ciclo bajo demanda por su tipo.

        Args:
            cycle_type: Tipo de ciclo ('reasoning', 'forecast', 'executive', 'operations').

        Returns:
            Dict con los resultados del ciclo.
        """
        return await self._enqueue(
            name="trigger_cycle",
            priority=CommandPriority.MEDIUM,
            params={"cycle_type": cycle_type},
            caller="api",
        )

    # -----------------------------------------------------------------------
    # Planetary Diagnosis
    # -----------------------------------------------------------------------

    async def planetary_status(self) -> dict[str, Any]:
        """
        Devuelve los resultados del ultimo planetary_diagnosis_cycle.

        Returns:
            Dict con los resultados del diagnostico planetario.
        """
        return await self._enqueue(
            name="planetary_status",
            priority=CommandPriority.LOW,
            params={},
            caller="api",
        )

    async def planetary_config(self, config_name: str) -> dict[str, Any]:
        """
        Devuelve la configuracion de una familia planetaria especifica.

        Args:
            config_name: Nombre de la configuracion (ej: 'continuity', 'harmony').

        Returns:
            Dict con la configuracion de la familia.
        """
        return await self._enqueue(
            name="planetary_config",
            priority=CommandPriority.LOW,
            params={"config_name": config_name},
            caller="api",
        )

    async def planetary_alerts(self) -> dict[str, Any]:
        """
        Devuelve solo las alertas (threshold >= 0.99) de todas las familias.

        Returns:
            Dict con las alertas activas del diagnostico planetario.
        """
        return await self._enqueue(
            name="planetary_alerts",
            priority=CommandPriority.HIGH,
            params={},
            caller="api",
        )

    async def planetary_run(self) -> dict[str, Any]:
        """
        Ejecuta el diagnostico planetario bajo demanda.

        Returns:
            Dict con los resultados de la ejecucion.
        """
        return await self._enqueue(
            name="planetary_run",
            priority=CommandPriority.MEDIUM,
            params={},
            caller="cli",
        )

    # -----------------------------------------------------------------------
    # Hipotesis
    # -----------------------------------------------------------------------

    async def list_hypotheses(
        self, filters: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Lista hipotesis del sistema.

        Args:
            filters: Filtros opcionales (estado, dominio, confianza_min, etc.).

        Returns:
            Dict con la lista de hipotesis.
        """
        return await self._enqueue(
            name="list_hypotheses",
            priority=CommandPriority.LOW,
            params={"filters": filters},
            caller="api",
        )

    async def create_hypothesis(
        self, text: str, context: dict[str, Any] | None = None, confidence: float = 0.5
    ) -> dict[str, Any]:
        """
        Crea una nueva hipotesis.

        Args:
            text: Texto descriptivo de la hipotesis.
            context: Contexto adicional.
            confidence: Confianza inicial (0.0 - 1.0).

        Returns:
            Dict con la hipotesis creada.
        """
        return await self._enqueue(
            name="create_hypothesis",
            priority=CommandPriority.MEDIUM,
            params={"text": text, "context": context or {}, "confidence": confidence},
            caller="cli",
        )

    async def validate_hypothesis(self, hyp_id: str) -> dict[str, Any]:
        """
        Valida una hipotesis con el agente cientifico.

        Args:
            hyp_id: ID de la hipotesis a validar.

        Returns:
            Dict con el resultado de la validacion.
        """
        return await self._enqueue(
            name="validate_hypothesis",
            priority=CommandPriority.MEDIUM,
            params={"hyp_id": hyp_id},
            caller="cli",
        )

    async def get_hypothesis(self, hyp_id: str) -> dict[str, Any]:
        """
        Obtiene el detalle de una hipotesis.

        Args:
            hyp_id: ID de la hipotesis.

        Returns:
            Dict con los detalles de la hipotesis.
        """
        return await self._enqueue(
            name="get_hypothesis",
            priority=CommandPriority.LOW,
            params={"hyp_id": hyp_id},
            caller="api",
        )

    # -----------------------------------------------------------------------
    # Escenarios
    # -----------------------------------------------------------------------

    async def simulate_scenario(
        self,
        hyp_id: str,
        variables: dict[str, Any] | None = None,
        n_runs: int = 1000,
    ) -> dict[str, Any]:
        """
        Simula un escenario para una hipotesis.

        Args:
            hyp_id: ID de la hipotesis base.
            variables: Variables del escenario.
            n_runs: Numero de simulaciones Monte Carlo.

        Returns:
            Dict con los resultados de la simulacion.
        """
        return await self._enqueue(
            name="simulate_scenario",
            priority=CommandPriority.MEDIUM,
            params={"hyp_id": hyp_id, "variables": variables or {}, "n_runs": n_runs},
            caller="cli",
        )

    async def list_scenarios(self) -> dict[str, Any]:
        """
        Lista escenarios generados.

        Returns:
            Dict con la lista de escenarios.
        """
        return await self._enqueue(
            name="list_scenarios",
            priority=CommandPriority.LOW,
            params={},
            caller="api",
        )

    async def get_scenario_results(self, scenario_id: str) -> dict[str, Any]:
        """
        Obtiene resultados de un escenario especifico.

        Args:
            scenario_id: ID del escenario.

        Returns:
            Dict con los resultados del escenario.
        """
        return await self._enqueue(
            name="get_scenario_results",
            priority=CommandPriority.LOW,
            params={"scenario_id": scenario_id},
            caller="api",
        )

    # -----------------------------------------------------------------------
    # Predicciones
    # -----------------------------------------------------------------------

    async def list_predictions(self) -> dict[str, Any]:
        """
        Lista predicciones activas.

        Returns:
            Dict con la lista de predicciones.
        """
        return await self._enqueue(
            name="list_predictions",
            priority=CommandPriority.LOW,
            params={},
            caller="api",
        )

    async def get_prediction_market(self) -> dict[str, Any]:
        """
        Obtiene el estado del mercado de predicciones CPMM.

        Returns:
            Dict con el estado del mercado.
        """
        return await self._enqueue(
            name="get_prediction_market",
            priority=CommandPriority.LOW,
            params={},
            caller="api",
        )

    async def trade_prediction(
        self, market_id: str, scenario: str, amount: float
    ) -> dict[str, Any]:
        """
        Opera en el mercado de predicciones.

        Args:
            market_id: ID del mercado.
            scenario: Escenario a apostar ('yes' o 'no').
            amount: Cantidad a invertir.

        Returns:
            Dict con el resultado de la operacion.
        """
        return await self._enqueue(
            name="trade_prediction",
            priority=CommandPriority.MEDIUM,
            params={"market_id": market_id, "scenario": scenario, "amount": amount},
            caller="cli",
        )

    # -----------------------------------------------------------------------
    # Grafo
    # -----------------------------------------------------------------------

    async def graph_stats(self) -> dict[str, Any]:
        """
        Estadisticas del grafo de conocimiento.

        Returns:
            Dict con estadisticas del grafo.
        """
        return await self._enqueue(
            name="graph_stats",
            priority=CommandPriority.LOW,
            params={},
            caller="api",
        )

    async def graph_communities(self) -> dict[str, Any]:
        """
        Comunidades detectadas en el grafo.

        Returns:
            Dict con las comunidades detectadas.
        """
        return await self._enqueue(
            name="graph_communities",
            priority=CommandPriority.LOW,
            params={},
            caller="api",
        )

    async def graph_centralidad(self) -> dict[str, Any]:
        """
        Nodos con mayor centralidad en el grafo.

        Returns:
            Dict con los nodos mas centrales.
        """
        return await self._enqueue(
            name="graph_centralidad",
            priority=CommandPriority.LOW,
            params={},
            caller="api",
        )

    async def graph_path(
        self, from_node: str, to_node: str
    ) -> dict[str, Any]:
        """
        Camino entre dos nodos del grafo.

        Args:
            from_node: Nodo origen.
            to_node: Nodo destino.

        Returns:
            Dict con el camino encontrado.
        """
        return await self._enqueue(
            name="graph_path",
            priority=CommandPriority.LOW,
            params={"from_node": from_node, "to_node": to_node},
            caller="api",
        )

    # -----------------------------------------------------------------------
    # Diario
    # -----------------------------------------------------------------------

    async def journal_current(self) -> dict[str, Any]:
        """
        Obtiene la ultima entrada del diario.

        Returns:
            Dict con la ultima entrada.
        """
        return await self._enqueue(
            name="journal_current",
            priority=CommandPriority.LOW,
            params={},
            caller="api",
        )

    async def journal_generate(self) -> dict[str, Any]:
        """
        Genera una nueva entrada del diario.

        Returns:
            Dict con la nueva entrada generada.
        """
        return await self._enqueue(
            name="journal_generate",
            priority=CommandPriority.MEDIUM,
            params={},
            caller="cli",
        )

    # -----------------------------------------------------------------------
    # Alertas
    # -----------------------------------------------------------------------

    async def list_alerts(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Lista alertas del sistema.

        Args:
            filters: Filtros opcionales (severidad, fecha, etc.).

        Returns:
            Dict con la lista de alertas.
        """
        return await self._enqueue(
            name="list_alerts",
            priority=CommandPriority.LOW,
            params={"filters": filters},
            caller="api",
        )

    async def explain_alert(self, alert_id: str) -> dict[str, Any]:
        """
        Explica POR QUE una alerta tiene cierto score.

        Args:
            alert_id: ID de la alerta.

        Returns:
            Dict con la explicacion detallada.
        """
        return await self._enqueue(
            name="explain_alert",
            priority=CommandPriority.HIGH,
            params={"alert_id": alert_id},
            caller="api",
        )

    # -----------------------------------------------------------------------
    # Configuracion
    # -----------------------------------------------------------------------

    async def get_config(self) -> dict[str, Any]:
        """
        Obtiene la configuracion actual del sistema.

        Returns:
            Dict con la configuracion.
        """
        return await self._enqueue(
            name="get_config",
            priority=CommandPriority.LOW,
            params={},
            caller="api",
        )

    async def update_config(self, key: str, value: Any) -> dict[str, Any]:
        """
        Actualiza un parametro de configuracion (solo en desarrollo).

        Args:
            key: Clave de configuracion.
            value: Nuevo valor.

        Returns:
            Dict con el resultado de la actualizacion.
        """
        return await self._enqueue(
            name="update_config",
            priority=CommandPriority.MEDIUM,
            params={"key": key, "value": value},
            caller="cli",
        )

    # -----------------------------------------------------------------------
    # Operaciones
    # -----------------------------------------------------------------------

    async def backup_now(self) -> dict[str, Any]:
        """
        Crea un backup inmediato de la base de datos.

        Returns:
            Dict con el resultado del backup.
        """
        return await self._enqueue(
            name="backup_now",
            priority=CommandPriority.HIGH,
            params={},
            caller="cli",
        )

    async def restore_backup(self, timestamp: str) -> dict[str, Any]:
        """
        Restaura la base de datos desde un backup.

        Args:
            timestamp: Timestamp identificador del backup.

        Returns:
            Dict con el resultado de la restauracion.
        """
        return await self._enqueue(
            name="restore_backup",
            priority=CommandPriority.HIGH,
            params={"timestamp": timestamp},
            caller="cli",
        )

    async def list_backups(self) -> dict[str, Any]:
        """
        Lista los backups disponibles.

        Returns:
            Dict con la lista de backups.
        """
        return await self._enqueue(
            name="list_backups",
            priority=CommandPriority.LOW,
            params={},
            caller="api",
        )

    async def get_metrics(self) -> dict[str, Any]:
        """
        Obtiene metricas del sistema.

        Returns:
            Dict con las metricas.
        """
        return await self._enqueue(
            name="get_metrics",
            priority=CommandPriority.LOW,
            params={},
            caller="api",
        )

    async def get_audit_log(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Obtiene el log de auditoria.

        Args:
            filters: Filtros opcionales (modulo, accion, fecha, etc.).

        Returns:
            Dict con los registros de auditoria.
        """
        return await self._enqueue(
            name="get_audit_log",
            priority=CommandPriority.LOW,
            params={"filters": filters},
            caller="api",
        )

    # ============================================================================
    # HANDLERS DE COMANDOS (metodos _cmd_*)
    # ============================================================================
    # Cada metodo _cmd_* recibe params y devuelve un dict con el resultado.
    # AQUI es donde se comunican con veo_core - NUNCA tocan DB directamente.
    # ============================================================================

    # -----------------------------------------------------------------------
    # _cmd: Gestion del sistema
    # -----------------------------------------------------------------------

    async def _cmd_status(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handler para comando 'status'."""
        t0 = time.time()

        # Obtener status de veo_core
        core_status = {}
        if self._core:
            try:
                core_status = await self._core.get_status()
            except Exception as exc:
                core_status = {"error": str(exc)}
        else:
            core_status = {"status": "not_initialized", "message": "VEOCore no disponible"}

        # Stats del commander
        commander_stats = {
            "commands_queued": self._queue.qsize(),
            "commands_history": len(self._command_history),
            "running": self._running,
            "core_available": self.core_available,
            "uptime_seconds": round(time.time() - getattr(self, '_start_time', time.time()), 1),
        }

        # Health monitor
        health_summary = {}
        if self._health_monitor:
            try:
                health_summary = self._health_monitor.check()
            except (AttributeError, TypeError):
                health_summary = {"status": "unknown"}

        return {
            "status": "ok",
            "commander": commander_stats,
            "core": {
                "running": core_status.get("running", False),
                "version": core_status.get("version", "unknown"),
                "health": core_status.get("health", {}),
                "cycles_executed": core_status.get("cycles_executed", {}),
                "pending_alerts": core_status.get("pending_alerts", 0),
                "uptime_human": core_status.get("uptime_human", "N/A"),
            },
            "health_monitor": health_summary,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _cmd_health(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handler para comando 'health'."""
        results: dict[str, Any] = {}

        # Health de VEOCore
        if self._core:
            try:
                core_health = await self._core.health.check()
                results["veo_core"] = core_health
            except Exception as exc:
                results["veo_core"] = {"status": "error", "error": str(exc)}
        else:
            results["veo_core"] = {"status": "unknown", "message": "VEOCore no disponible"}

        # Health del scheduler
        if self._core:
            try:
                sched_status = self._core.scheduler.get_queue_status()
                results["scheduler"] = {
                    "status": "ok",
                    "registered_tasks": sched_status.get("registered_tasks", 0),
                }
            except Exception as exc:
                results["scheduler"] = {"status": "error", "error": str(exc)}

        # Health del commander
        results["hermes_commander"] = {
            "status": "ok" if self._running else "stopped",
            "queue_size": self._queue.qsize(),
            "max_queue_size": self.max_queue_size,
            "workers": self._num_workers,
        }

        # Health del bus de eventos
        if self._core:
            try:
                bus_stats = self._core.bus.get_stats()
                results["event_bus"] = {
                    "status": "ok" if bus_stats.get("running") else "error",
                    "queue_size": bus_stats.get("queue_size", 0),
                    "history_len": bus_stats.get("history_len", 0),
                }
            except Exception as exc:
                results["event_bus"] = {"status": "error", "error": str(exc)}

        # Overall
        overall = "healthy"
        for comp, result in results.items():
            if result.get("status") in ("error", "critical", "unhealthy"):
                overall = "critical"
                break
            elif result.get("status") in ("warning", "degraded"):
                overall = "degraded"

        return {
            "status": overall,
            "components": results,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # -----------------------------------------------------------------------
    # _cmd: Ciclos
    # -----------------------------------------------------------------------

    async def _cmd_run_reasoning(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handler para comando 'run_reasoning'."""
        log_cycle_start("reasoning", params)

        signals = params.get("signals")
        if signals:
            try:
                signals = ParamValidator.validate_signals(signals)
            except HermesValidationError as exc:
                return {"status": "error", "message": str(exc)}

        if not self._core:
            return {"status": "error", "message": "VEOCore no disponible"}

        try:
            result = await self._core.trigger_cycle("reasoning", force=True)
            if result is None:
                result = {"status": "empty", "message": "Ciclo vacio"}

            log_cycle_end("reasoning", {
                "status": result.get("status", "ok"),
                "hipotesis_generadas": result.get("hipotesis_generadas", 0),
                "hipotesis_validadas": result.get("hipotesis_validadas", 0),
            })

            return {"status": "ok", "result": result}

        except Exception as exc:
            log_cycle_end("reasoning", {"status": "failed", "error": str(exc)})
            return {"status": "error", "message": str(exc), "error_type": type(exc).__name__}

    async def _cmd_run_forecast(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handler para comando 'run_forecast'."""
        log_cycle_start("forecast", params)

        if not self._core:
            return {"status": "error", "message": "VEOCore no disponible"}

        try:
            result = await self._core.trigger_cycle("forecast", force=True)
            if result is None:
                result = {"status": "empty", "message": "Ciclo vacio - sin hipotesis validadas"}

            log_cycle_end("forecast", {
                "status": result.get("status", "ok"),
                "escenarios_generados": result.get("escenarios_generados", 0),
                "predicciones_creadas": result.get("predicciones_creadas", 0),
            })

            return {"status": "ok", "result": result}

        except Exception as exc:
            log_cycle_end("forecast", {"status": "failed", "error": str(exc)})
            return {"status": "error", "message": str(exc), "error_type": type(exc).__name__}

    async def _cmd_run_executive(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handler para comando 'run_executive'."""
        log_cycle_start("executive", params)

        if not self._core:
            return {"status": "error", "message": "VEOCore no disponible"}

        try:
            result = await self._core.trigger_cycle("executive", force=True)
            if result is None:
                result = {"status": "empty", "message": "Ciclo vacio"}

            log_cycle_end("executive", {
                "status": result.get("status", "ok"),
                "total_findings": result.get("total_findings", 0),
            })

            return {"status": "ok", "result": result}

        except Exception as exc:
            log_cycle_end("executive", {"status": "failed", "error": str(exc)})
            return {"status": "error", "message": str(exc), "error_type": type(exc).__name__}

    async def _cmd_run_operations(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handler para comando 'run_operations'."""
        log_cycle_start("operations", params)

        if not self._core:
            return {"status": "error", "message": "VEOCore no disponible"}

        try:
            result = await self._core.trigger_cycle("operations", force=True)
            if result is None:
                result = {"status": "empty", "message": "Ciclo vacio"}

            log_cycle_end("operations", {
                "status": result.get("status", "ok"),
                "backup_done": result.get("estado_backups", {}).get("performed", False),
            })

            return {"status": "ok", "result": result}

        except Exception as exc:
            log_cycle_end("operations", {"status": "failed", "error": str(exc)})
            return {"status": "error", "message": str(exc), "error_type": type(exc).__name__}

    async def _cmd_trigger_cycle(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handler para comando 'trigger_cycle'."""
        cycle_type = params.get("cycle_type", "").strip().lower()

        valid_cycles = ("reasoning", "forecast", "executive", "operations",
                       "signal_scan", "narrative_analysis", "megatrend_review",
                       "forecast_audit", "planetary_run")

        if cycle_type not in valid_cycles:
            return {
                "status": "error",
                "message": f"Ciclo '{cycle_type}' no valido",
                "valid_cycles": list(valid_cycles),
            }

        if not self._core:
            return {"status": "error", "message": "VEOCore no disponible"}

        try:
            result = await self._core.trigger_cycle(cycle_type, force=True)
            return {"status": "ok", "cycle_type": cycle_type, "result": result or {}}
        except Exception as exc:
            return {"status": "error", "message": str(exc), "error_type": type(exc).__name__}

    async def _cmd_planetary_status(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handler para comando 'planetary_status'."""
        t0 = time.time()

        if not self._core:
            return {"status": "error", "message": "VEOCore no disponible"}

        try:
            last_results = getattr(self._core, "_last_planetary_results", None)

            if self._audit:
                await self._audit.record(
                    action="planetary_status",
                    module="hermes_commander",
                    result={"has_results": last_results is not None},
                    duration_ms=int((time.time() - t0) * 1000),
                )

            if last_results is None:
                return {
                    "status": "no_data",
                    "message": "No se ha ejecutado ningun diagnostico planetario todavia",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

            return {
                "status": "ok",
                "planetary_results": last_results,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    async def _cmd_planetary_config(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handler para comando 'planetary_config'."""
        t0 = time.time()
        config_name = str(params.get("config_name", "")).strip()

        if not config_name:
            return {"status": "error", "message": "Nombre de configuracion obligatorio"}

        # Usar PLANETARY_CONFIGS directamente (no toca DB)
        if not _PLANETARY_CONFIGS_DISPONIBLE:
            return {"status": "error", "message": "Planetary configs no disponibles"}

        config = PLANETARY_CONFIGS.get(config_name)
        if config is None:
            available = list(PLANETARY_CONFIGS.keys())
            return {
                "status": "error",
                "message": f"Configuracion '{config_name}' no encontrada",
                "available_configs": available[:20] + (["..."] if len(available) > 20 else []),
            }

        # Convertir PlanetaryConfig a dict de forma segura
        try:
            config_dict = {
                "name": getattr(config, "name", config_name),
                "description": getattr(config, "description", ""),
                "threshold": getattr(config, "threshold", 0.0),
                "indicators": getattr(config, "indicators", []),
            }
        except Exception:
            config_dict = {"name": config_name, "raw": str(config)}

        if self._audit:
            await self._audit.record(
                action="planetary_config",
                module="hermes_commander",
                params={"config_name": config_name},
                result={"found": True},
                duration_ms=int((time.time() - t0) * 1000),
            )

        return {
            "status": "ok",
            "config_name": config_name,
            "config": config_dict,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _cmd_planetary_alerts(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handler para comando 'planetary_alerts'."""
        t0 = time.time()

        if not self._core:
            return {"status": "error", "message": "VEOCore no disponible"}

        try:
            last_results = getattr(self._core, "_last_planetary_results", None)

            if last_results is None:
                return {
                    "status": "no_data",
                    "message": "No se ha ejecutado ningun diagnostico planetario todavia",
                    "alerts": [],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

            # Extraer solo alertas (threshold >= 0.99) de todas las familias
            results = last_results.get("results", {})
            alerts = []
            for family_name, family_result in results.items():
                if family_name == "summary":
                    continue
                threshold = family_result.get("threshold", 0.0)
                if isinstance(threshold, (int, float)) and threshold >= 0.99:
                    alerts.append({
                        "family": family_name,
                        "threshold": threshold,
                        "details": family_result,
                    })

            if self._audit:
                await self._audit.record(
                    action="planetary_alerts",
                    module="hermes_commander",
                    result={"alert_count": len(alerts)},
                    duration_ms=int((time.time() - t0) * 1000),
                )

            return {
                "status": "ok",
                "alerts": alerts,
                "alert_count": len(alerts),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    async def _cmd_planetary_run(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handler para comando 'planetary_run'."""
        t0 = time.time()

        if not self._core:
            return {"status": "error", "message": "VEOCore no disponible"}

        try:
            # Verificar si el metodo existe
            if not hasattr(self._core, "planetary_diagnosis_cycle"):
                return {"status": "error", "message": "PlanetaryDiagnosisCycle no disponible en VEOCore"}

            result = await self._core.planetary_diagnosis_cycle()

            elapsed_ms = int((time.time() - t0) * 1000)

            if self._audit:
                await self._audit.record(
                    action="planetary_run",
                    module="hermes_commander",
                    result={"status": result.get("status", "unknown")},
                    duration_ms=elapsed_ms,
                )

            return {
                "status": "ok",
                "result": result,
                "elapsed_ms": elapsed_ms,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:
            return {"status": "error", "message": str(exc), "error_type": type(exc).__name__}

    # -----------------------------------------------------------------------
    # _cmd: Hipotesis
    # -----------------------------------------------------------------------

    async def _cmd_list_hypotheses(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handler para comando 'list_hypotheses'.

        Lee hipotesis primero desde la base de datos (persistencia entre reinicios)
        y complementa con el historial en memoria de VEOCore.
        """
        filters = ParamValidator.validate_filters(params.get("filters"))

        hypotheses: list[dict[str, Any]] = []
        source = "memory"

        # 1. Intentar leer desde base de datos
        try:
            from core.persistence import listar_hipotesis
            db_hipotesis = await listar_hipotesis(
                estado=filters.get("estado"),
                confianza_min=filters.get("confianza_min"),
            )
            if db_hipotesis:
                hypotheses = db_hipotesis
                source = "database"
        except Exception as exc_db:
            self._logger.warning(
                "[HermesCommander] Error leyendo hipotesis de BD: %s", exc_db
            )

        # 2. Complementar con memoria si VEOCore esta disponible
        if self._core and hasattr(self._core, "reasoning"):
            mem_hypotheses = list(self._core.reasoning.hypotheses_history)
            # Fusionar evitando duplicados por ID
            existing_ids = {h["id"] for h in hypotheses}
            for h in mem_hypotheses:
                if h["id"] not in existing_ids:
                    hypotheses.append(h)
            if mem_hypotheses:
                source = "database+memory"

        # 3. Aplicar filtros adicionales
        if filters.get("domain"):
            hypotheses = [h for h in hypotheses if h.get("domain") == filters["domain"]]
        if filters.get("tag"):
            hypotheses = [h for h in hypotheses if filters["tag"] in h.get("tags", [])]

        limit = filters.get("limit", 50)
        hypotheses = hypotheses[-limit:]

        return {
            "status": "ok",
            "hypotheses": hypotheses,
            "total": len(hypotheses),
            "source": source,
        }

    async def _cmd_create_hypothesis(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handler para comando 'create_hypothesis'.

        Utiliza los agentes de analisis reales (AgenteCientifico + AgenteEsceptico)
        para evaluar la hipotesis en el momento de su creacion. Si los agentes no
        estan disponibles, devuelve un error explicito.
        """
        try:
            text = ParamValidator.validate_hypothesis_text(params.get("text", ""))
            confidence = ParamValidator.validate_confidence(params.get("confidence", 0.5))
            context = params.get("context", {})
        except HermesValidationError as exc:
            return {"status": "error", "message": str(exc)}

        if not self._core:
            return {"status": "error", "message": "VEOCore no disponible"}

        # Verificar disponibilidad de agentes de validacion
        if not _AGENTES_VALIDACION_DISPONIBLES:
            return {
                "status": "error",
                "message": (
                    "Modulo de validacion cientifica no disponible. "
                    "Instale las dependencias: pip install -r requirements.txt"
                ),
            }

        try:
            hyp_id = f"hyp_manual_{uuid.uuid4().hex[:8]}"

            # Crear hipotesis para los agentes de analisis
            sa_hyp = SAHipotesis(
                texto=text,
                nivel_confianza_inicial=confidence,
                contexto=context.get("domain", "manual"),
                fuentes=context.get("fuentes", []),
            )

            # Ejecutar agente cientifico (heuristico si no hay LLM)
            agente_c = AgenteCientifico(config={})
            resultado_c = agente_c.refutar_hipotesis(sa_hyp)

            # Ejecutar agente esceptico (heuristico si no hay LLM)
            agente_e = AgenteEsceptico(config={})
            resultado_e = agente_e.cuestionar_hipotesis(sa_hyp)

            # Mapear veredicto cientifico a formato API
            # El enum VeredictoCientifico tiene .name (ej: "REFUTADA") y .value (ej: "refutada")
            veredicto_raw = resultado_c.veredicto.value if hasattr(resultado_c.veredicto, "value") else str(resultado_c.veredicto).lower().replace("verdictocientifico.", "")
            # Mapear a valores de VeredictoValidacion (confirmado/refutado/dudoso/pendiente/plausible)
            _VEREDICTO_MAP = {
                "confirmada": "confirmado",
                "refutada": "refutado",
                "inconclusa": "dudoso",
            }
            veredicto_c = _VEREDICTO_MAP.get(veredicto_raw, veredicto_raw)
            score_c = resultado_c.confianza

            # Mapear evaluacion esceptica a formato API
            score_e = 1.0 - resultado_e["score_global"]  # invertir: menor sesgo = mayor score
            interpretacion_e = resultado_e["interpretacion"]
            # Determinar veredicto esceptico basado en score_global
            sg = resultado_e["score_global"]
            if sg < 0.2:
                veredicto_e = "confirmado"
            elif sg < 0.4:
                veredicto_e = "plausible"
            elif sg < 0.6:
                veredicto_e = "dudoso"
            else:
                veredicto_e = "refutado"

            # Calcular NEI heuristica
            score_compuesto = resultado_c.metadatos.get("score_compuesto", 0.5)
            nei = round((score_c + score_e + score_compuesto) / 3, 2)

            # Construir hipotesis en formato API
            hypothesis = {
                "id": hyp_id,
                "texto": text,
                "estado": "activa",
                "confianza": round(confidence, 2),
                "evidencias": len(sa_hyp.fuentes),
                "fecha_creacion": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "tags": context.get("tags", []),
                "cientifico": {
                    "veredicto": veredicto_c,
                    "score": round(score_c, 2),
                    "razonamiento": resultado_c.razonamiento[:200] if resultado_c.razonamiento else "",
                },
                "esceptico": {
                    "veredicto": veredicto_e,
                    "score": round(score_e, 2),
                    "interpretacion": interpretacion_e[:200] if interpretacion_e else "",
                },
                "nei": nei,
                # Campos internos para trazabilidad
                "_source": "hermes_commander_analysis",
                "_text": text,
                "_confidence": int(confidence * 100),
                "_context": context,
                "_timestamp": datetime.now(timezone.utc).isoformat(),
                "_creator": "hermes_commander",
                "_domain": context.get("domain", "manual"),
            }

            self._core.reasoning.hypotheses_history.append(hypothesis)

            # Persistir en base de datos
            try:
                from core.persistence import guardar_hipotesis
                await guardar_hipotesis(hypothesis)
            except Exception as exc_persist:
                self._logger.warning(
                    "[HermesCommander] No se pudo persistir hipotesis %s: %s",
                    hyp_id, exc_persist,
                )

            # Registrar en audit
            if self._audit:
                await self._audit.record(
                    action="create_hypothesis",
                    module="hermes_commander",
                    params={"text": text[:100], "confidence": confidence},
                    result={
                        "hyp_id": hyp_id,
                        "veredicto_cientifico": veredicto_c,
                        "veredicto_esceptico": veredicto_e,
                        "nei": nei,
                    },
                )

            return {
                "status": "ok",
                "hypothesis": hypothesis,
                "message": f"Hipotesis '{hyp_id}' creada y evaluada por agentes de analisis",
            }
        except Exception as exc:
            self._logger.error("[HermesCommander] Error en create_hypothesis: %s", exc)
            return {"status": "error", "message": f"Error creando hipotesis: {exc}"}

    async def _cmd_validate_hypothesis(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handler para comando 'validate_hypothesis'.

        Utiliza el CoordinadorValidacion real con los agentes cientifico y esceptico
        para producir un veredicto integrado. Si el coordinador no esta disponible,
        devuelve un error explicito.
        """
        try:
            hyp_id = ParamValidator.validate_id(params.get("hyp_id", ""), "hipotesis")
        except HermesValidationError as exc:
            return {"status": "error", "message": str(exc)}

        if not self._core:
            return {"status": "error", "message": "VEOCore no disponible"}

        # Verificar disponibilidad del coordinador de validacion
        if not _AGENTES_VALIDACION_DISPONIBLES:
            return {
                "status": "error",
                "message": (
                    "Modulo de validacion cientifica no disponible. "
                    "Instale las dependencias: pip install -r requirements.txt"
                ),
            }

        try:
            # Buscar la hipotesis
            target_hyp = None
            for h in self._core.reasoning.hypotheses_history:
                if h.get("id") == hyp_id:
                    target_hyp = h
                    break

            if not target_hyp:
                return {"status": "error", "message": f"Hipotesis '{hyp_id}' no encontrada"}

            # Reconstruir SAHipotesis desde los datos almacenados
            texto = target_hyp.get("texto") or target_hyp.get("text", "")
            confianza = target_hyp.get("confianza", 0.5)
            if isinstance(confianza, int) and confianza > 1:
                confianza = confianza / 100.0

            sa_hyp = SAHipotesis(
                texto=texto,
                nivel_confianza_inicial=confianza,
                contexto=target_hyp.get("_domain", target_hyp.get("domain", "manual")),
                fuentes=target_hyp.get("fuentes", []),
            )

            # Ejecutar validacion coordinada
            coordinador = CoordinadorValidacion()
            resultado = coordinador.validar(sa_hyp)

            # Extraer veredicto y confianza
            veredicto = resultado.get("veredicto_final", "INCONCLUSO").upper()
            confianza_final = resultado.get("confianza", 0.5)

            # Determinar estado basado en veredicto
            estado_map = {
                "CONFIRMADA": "confirmada",
                "RECHAZADA": "refutada",
                "INCONCLUSO": "pendiente",
                "DUDOSA": "pendiente",
            }
            nuevo_estado = estado_map.get(veredicto, "pendiente")

            # Actualizar hipotesis con resultados de validacion
            target_hyp["estado"] = nuevo_estado
            target_hyp["confianza"] = round(confianza_final, 2)
            target_hyp["cientifico"] = {
                "veredicto": resultado.get("detalles", {})
                .get("cientifico", {})
                .get("veredicto", "inconcluso"),
                "score": round(resultado.get("detalles", {}).get("cientifico", {}).get("confianza", 0.5), 2),
            }
            target_hyp["esceptico"] = {
                "veredicto": resultado.get("detalles", {})
                .get("esceptico", {})
                .get("veredicto", "inconcluso"),
                "score": round(resultado.get("detalles", {}).get("esceptico", {}).get("confianza", 0.5), 2),
            }

            # Construir registro de validacion
            validation = {
                "id": hyp_id,
                "hypothesis_text": texto,
                "veredicto_final": veredicto,
                "confianza_final": round(confianza_final, 2),
                "estado": nuevo_estado,
                "detalles": resultado.get("detalles", {}),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            self._core.reasoning.validation_history.append(validation)

            # Actualizar hipotesis en base de datos
            try:
                from core.persistence import actualizar_hipotesis
                await actualizar_hipotesis(
                    hyp_id,
                    {
                        "estado": nuevo_estado,
                        "confianza": round(confianza_final, 2),
                        "nei": round(confianza_final, 2),
                    },
                )
            except Exception as exc_persist:
                self._logger.warning(
                    "[HermesCommander] No se pudo actualizar hipotesis %s en BD: %s",
                    hyp_id, exc_persist,
                )

            # Registrar en audit
            if self._audit:
                await self._audit.record(
                    action="validate_hypothesis",
                    module="hermes_commander",
                    params={"hyp_id": hyp_id},
                    result={"veredicto": veredicto, "confianza": confianza_final},
                )

            return {
                "status": "ok",
                "validation": validation,
                "veredicto": veredicto,
                "hipotesis_actualizada": {
                    "id": hyp_id,
                    "estado": nuevo_estado,
                    "confianza": round(confianza_final, 2),
                },
            }
        except Exception as exc:
            self._logger.error("[HermesCommander] Error en validate_hypothesis: %s", exc)
            return {"status": "error", "message": f"Error validando hipotesis: {exc}"}

    async def _cmd_get_hypothesis(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handler para comando 'get_hypothesis'.

        Lee primero desde la base de datos (persistencia entre reinicios)
        y, si no esta, busca en el historial en memoria de VEOCore.
        """
        try:
            hyp_id = ParamValidator.validate_id(params.get("hyp_id", ""), "hipotesis")
        except HermesValidationError as exc:
            return {"status": "error", "message": str(exc)}

        # 1. Intentar leer desde base de datos
        try:
            from core.persistence import obtener_hipotesis
            db_hyp = await obtener_hipotesis(hyp_id)
            if db_hyp is not None:
                # Buscar validacion asociada en memoria
                validation = None
                if self._core and hasattr(self._core, "reasoning"):
                    for v in self._core.reasoning.validation_history:
                        if v.get("id") == hyp_id:
                            validation = v
                            break
                return {
                    "status": "ok",
                    "hypothesis": db_hyp,
                    "validation": validation,
                    "source": "database",
                }
        except Exception as exc_db:
            self._logger.warning(
                "[HermesCommander] Error leyendo hipotesis %s de BD: %s",
                hyp_id, exc_db,
            )

        # 2. Fallback a memoria si VEOCore esta disponible
        if self._core and hasattr(self._core, "reasoning"):
            for h in self._core.reasoning.hypotheses_history:
                if h.get("id") == hyp_id:
                    validation = None
                    for v in self._core.reasoning.validation_history:
                        if v.get("id") == hyp_id:
                            validation = v
                            break
                    return {
                        "status": "ok",
                        "hypothesis": h,
                        "validation": validation,
                        "source": "memory",
                    }

        return {"status": "error", "message": f"Hipotesis '{hyp_id}' no encontrada"}

    # -----------------------------------------------------------------------
    # _cmd: Escenarios
    # -----------------------------------------------------------------------

    async def _cmd_simulate_scenario(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handler para comando 'simulate_scenario'.

        Utiliza el SimuladorEscenarios real para ejecutar simulacion Monte Carlo.
        Si el simulador no esta disponible, devuelve un error explicito.
        """
        try:
            hyp_id = ParamValidator.validate_id(params.get("hyp_id", ""), "hipotesis")
            n_runs = ParamValidator.validate_positive_int(params.get("n_runs", 1000), "n_runs", 1000)
        except HermesValidationError as exc:
            return {"status": "error", "message": str(exc)}

        if not self._core:
            return {"status": "error", "message": "VEOCore no disponible"}

        # Verificar disponibilidad del simulador
        if not _SIMULADOR_ESCENARIOS_DISPONIBLE:
            return {
                "status": "error",
                "message": (
                    "Modulo de simulacion de escenarios no disponible. "
                    "Instale las dependencias: pip install -r requirements.txt"
                ),
            }

        try:
            # Buscar la hipotesis
            target_hyp = None
            for h in self._core.reasoning.hypotheses_history:
                if h.get("id") == hyp_id:
                    target_hyp = h
                    break

            if not target_hyp:
                return {"status": "error", "message": f"Hipotesis '{hyp_id}' no encontrada"}

            texto = target_hyp.get("texto") or target_hyp.get("text", "")
            confianza = target_hyp.get("confianza", 0.5)
            if isinstance(confianza, int) and confianza > 1:
                confianza = confianza / 100.0

            # Extraer variables causales del texto de la hipotesis
            from analysis.causal_engine import MotorCausal
            motor_causal_extractor = MotorCausal()
            variables_extraidas = motor_causal_extractor._extraer_variables(texto)
            if not variables_extraidas:
                variables_extraidas = ["impacto_general", "adopcion", "viabilidad"]

            # Construir grafo causal a partir de las variables extraidas
            from analysis.causal_graph_adapter import GrafoCausalSimple, MotorCausalProporcional
            grafo = GrafoCausalSimple()
            for v in variables_extraidas:
                grafo.agregar_nodo(v)
            # Crear relaciones en cadena: var_i -> var_{i+1} con peso decreciente
            for i in range(len(variables_extraidas) - 1):
                peso = max(0.3, 0.9 - i * 0.15)
                grafo.agregar_relacion(
                    variables_extraidas[i],
                    variables_extraidas[i + 1],
                    peso=peso,
                    tipo="directa",
                )

            motor = MotorCausalProporcional(grafo=grafo)

            # Crear hipotesis para el simulador
            ss_hyp = SSHipotesis(
                id=hyp_id,
                nombre=texto[:80],
                descripcion=texto[:200],
                direccion_esperada="aumento" if confianza >= 0.5 else "disminucion",
                confianza=confianza,
                variables_afectadas=variables_extraidas,
                evidencia="Hipotesis de demostracion para simulacion",
            )

            # Crear simulador con grafo real y generar escenarios contrafactuales
            sim = SimuladorEscenarios(grafo=grafo, motor_causal=motor)
            escenarios = sim.generar_escenarios_contrafactuales(ss_hyp)

            # Ejecutar simulacion Monte Carlo para cada escenario
            medias: list[float] = []
            for escenario in escenarios:
                resultado = sim.ejecutar_simulacion(escenario.id, n_runs=n_runs)
                media = resultado.get("estadisticas", {}).get("media", confianza)
                medias.append(float(media))

            if medias:
                mean_prob = sum(medias) / len(medias)
                variance = sum((m - mean_prob) ** 2 for m in medias) / len(medias)
                min_prob = min(medias)
                max_prob = max(medias)
            else:
                mean_prob = confianza
                variance = 0.0
                min_prob = confianza
                max_prob = confianza

            scenario = {
                "id": f"sc_manual_{uuid.uuid4().hex[:8]}",
                "hypothesis_id": hyp_id,
                "description": f"Escenario simulado para: {texto[:100]}",
                "base_probability": round(confianza, 3),
                "monte_carlo_mean": round(mean_prob, 3),
                "variance": round(variance, 5),
                "simulations": n_runs,
                "confidence_band": (
                    round(max(0.0, mean_prob - 2 * (variance ** 0.5)), 3),
                    round(min(1.0, mean_prob + 2 * (variance ** 0.5)), 3),
                ),
                "escenarios_generados": len(escenarios),
                "rango_probabilidades": [round(min_prob, 3), round(max_prob, 3)],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            self._core.forecast.scenarios_history.append(scenario)

            return {"status": "ok", "scenario": scenario}
        except Exception as exc:
            self._logger.error("[HermesCommander] Error en simulate_scenario: %s", exc)
            return {"status": "error", "message": f"Error simulando escenario: {exc}"}

    async def _cmd_list_scenarios(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handler para comando 'list_scenarios'."""
        if not self._core:
            return {"status": "error", "message": "VEOCore no disponible"}

        try:
            scenarios = list(self._core.forecast.scenarios_history)
            return {
                "status": "ok",
                "scenarios": scenarios,
                "total": len(scenarios),
            }
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    async def _cmd_get_scenario_results(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handler para comando 'get_scenario_results'."""
        try:
            scenario_id = ParamValidator.validate_id(params.get("scenario_id", ""), "escenario")
        except HermesValidationError as exc:
            return {"status": "error", "message": str(exc)}

        if not self._core:
            return {"status": "error", "message": "VEOCore no disponible"}

        try:
            for sc in self._core.forecast.scenarios_history:
                if sc.get("id") == scenario_id:
                    # Buscar predicciones asociadas
                    predictions = [
                        p for p in self._core.forecast.predictions_history
                        if p.get("scenario_id") == scenario_id
                    ]
                    return {
                        "status": "ok",
                        "scenario": sc,
                        "predictions": predictions,
                    }
            return {"status": "error", "message": f"Escenario '{scenario_id}' no encontrado"}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    # -----------------------------------------------------------------------
    # _cmd: Predicciones
    # -----------------------------------------------------------------------

    async def _cmd_list_predictions(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handler para comando 'list_predictions'."""
        if not self._core:
            return {"status": "error", "message": "VEOCore no disponible"}

        try:
            predictions = list(self._core.forecast.predictions_history)
            return {
                "status": "ok",
                "predictions": predictions,
                "total": len(predictions),
            }
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    async def _cmd_get_prediction_market(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handler para comando 'get_prediction_market'."""
        if not self._core:
            return {"status": "error", "message": "VEOCore no disponible"}

        try:
            predictions = list(self._core.forecast.predictions_history)
            if not predictions:
                return {
                    "status": "ok",
                    "market": {"status": "empty", "message": "No hay predicciones activas"},
                }

            # Construir estado del mercado CPMM
            total_liquidity = sum(p.get("market_liquidity", 0) for p in predictions)
            total_yes = sum(p.get("yes_shares", 0) for p in predictions)
            total_no = sum(p.get("no_shares", 0) for p in predictions)

            market = {
                "total_predictions": len(predictions),
                "total_liquidity": total_liquidity,
                "total_yes_shares": total_yes,
                "total_no_shares": total_no,
                "avg_probability": round(
                    sum(p.get("probability", 0) for p in predictions) / len(predictions), 3
                ) if predictions else 0,
                "predictions": [
                    {
                        "id": p["id"],
                        "probability": p.get("probability", 0),
                        "price_yes": p.get("price_yes", 0),
                        "liquidity": p.get("market_liquidity", 0),
                        "expires_at": p.get("expires_at"),
                    }
                    for p in predictions[-20:]
                ],
            }

            return {"status": "ok", "market": market}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    async def _cmd_trade_prediction(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handler para comando 'trade_prediction'."""
        try:
            market_id = ParamValidator.validate_id(params.get("market_id", ""), "mercado")
            scenario = str(params.get("scenario", "")).lower().strip()
            amount = float(params.get("amount", 0))
            if amount <= 0:
                raise HermesValidationError("La cantidad debe ser mayor que 0")
            if scenario not in ("yes", "no"):
                raise HermesValidationError("El escenario debe ser 'yes' o 'no'")
        except (HermesValidationError, ValueError) as exc:
            return {"status": "error", "message": str(exc)}

        if not self._core:
            return {"status": "error", "message": "VEOCore no disponible"}

        try:
            # Encontrar la prediccion
            target_pred = None
            for p in self._core.forecast.predictions_history:
                if p.get("id") == market_id or p.get("scenario_id") == market_id:
                    target_pred = p
                    break

            if not target_pred:
                return {"status": "error", "message": f"Prediccion '{market_id}' no encontrada"}

            # Simular operacion CPMM
            k = target_pred.get("market_liquidity", 10000)
            yes_shares = target_pred.get("yes_shares", 500)
            no_shares = target_pred.get("no_shares", 500)

            if scenario == "yes":
                new_yes = yes_shares + int(amount)
                price = k / (new_yes + no_shares)
                target_pred["yes_shares"] = new_yes
                target_pred["price_yes"] = round(price, 4)
            else:
                new_no = no_shares + int(amount)
                price = k / (yes_shares + new_no)
                target_pred["no_shares"] = new_no

            # Actualizar probabilidad implicita
            total = target_pred.get("yes_shares", 1) + target_pred.get("no_shares", 1)
            target_pred["probability"] = round(target_pred.get("yes_shares", 0) / total, 3)

            trade_result = {
                "trade_id": f"trade_{uuid.uuid4().hex[:8]}",
                "market_id": market_id,
                "scenario": scenario,
                "amount": amount,
                "new_probability": target_pred["probability"],
                "new_price_yes": target_pred.get("price_yes", 0),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            return {"status": "ok", "trade": trade_result}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    # -----------------------------------------------------------------------
    # _cmd: Grafo
    # -----------------------------------------------------------------------

    async def _cmd_graph_stats(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handler para comando 'graph_stats'."""
        if not self._core:
            return {"status": "error", "message": "VEOCore no disponible"}

        try:
            # Estadisticas basadas en las historias del sistema
            hyp_count = len(self._core.reasoning.hypotheses_history)
            val_count = len(self._core.reasoning.validation_history)
            sc_count = len(self._core.forecast.scenarios_history)
            pred_count = len(self._core.forecast.predictions_history)
            alert_count = len(self._core.executive.alerts_history)

            # Nodos simulados del grafo
            nodes = []
            domains: dict[str, int] = {}
            for h in self._core.reasoning.hypotheses_history:
                domain = h.get("domain", "general")
                domains[domain] = domains.get(domain, 0) + 1
                nodes.append({
                    "id": h.get("id"),
                    "type": "hypothesis",
                    "domain": domain,
                    "confidence": h.get("confidence", 0),
                })

            return {
                "status": "ok",
                "stats": {
                    "total_nodes": len(nodes),
                    "hypotheses": hyp_count,
                    "validations": val_count,
                    "scenarios": sc_count,
                    "predictions": pred_count,
                    "alerts": alert_count,
                    "domains": domains,
                    "edge_estimate": len(nodes) * 2 if nodes else 0,
                },
            }
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    async def _cmd_graph_communities(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handler para comando 'graph_communities'."""
        if not self._core:
            return {"status": "error", "message": "VEOCore no disponible"}

        try:
            # Agrupar hipotesis por dominio como comunidades
            communities: dict[str, list[dict]] = {}
            for h in self._core.reasoning.hypotheses_history:
                domain = h.get("domain", "general")
                if domain not in communities:
                    communities[domain] = []
                communities[domain].append({
                    "id": h.get("id"),
                    "text": h.get("text", "")[:80],
                    "confidence": h.get("confidence", 0),
                })

            community_list = [
                {
                    "id": f"comm_{i}",
                    "domain": domain,
                    "size": len(members),
                    "members": members[:10],
                    "avg_confidence": round(
                        sum(m.get("confidence", 0) for m in members) / len(members), 1
                    ) if members else 0,
                }
                for i, (domain, members) in enumerate(communities.items())
            ]

            return {
                "status": "ok",
                "communities": community_list,
                "total_communities": len(community_list),
            }
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    async def _cmd_graph_centralidad(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handler para comando 'graph_centralidad'."""
        if not self._core:
            return {"status": "error", "message": "VEOCore no disponible"}

        try:
            # Calcular centralidad simple basada en confianza y conexiones
            nodes = []
            for h in self._core.reasoning.hypotheses_history:
                confidence = h.get("confidence", 0)
                sources = len(h.get("sources", []))
                # Score de centralidad simple
                centrality = confidence * 0.5 + sources * 10
                nodes.append({
                    "id": h.get("id"),
                    "text": h.get("text", "")[:80],
                    "domain": h.get("domain", "general"),
                    "centrality_score": round(min(centrality, 100), 2),
                    "confidence": confidence,
                    "sources": sources,
                })

            # Ordenar por centralidad
            nodes.sort(key=lambda x: x["centrality_score"], reverse=True)

            return {
                "status": "ok",
                "central_nodes": nodes[:20],
                "total_analyzed": len(nodes),
            }
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    async def _cmd_graph_path(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handler para comando 'graph_path'."""
        try:
            from_node = ParamValidator.validate_id(params.get("from_node", ""), "nodo_origen")
            to_node = ParamValidator.validate_id(params.get("to_node", ""), "nodo_destino")
        except HermesValidationError as exc:
            return {"status": "error", "message": str(exc)}

        if not self._core:
            return {"status": "error", "message": "VEOCore no disponible"}

        try:
            # Buscar nodos
            from_hyp = None
            to_hyp = None
            for h in self._core.reasoning.hypotheses_history:
                if h.get("id") == from_node:
                    from_hyp = h
                if h.get("id") == to_node:
                    to_hyp = h

            if not from_hyp:
                return {"status": "error", "message": f"Nodo origen '{from_node}' no encontrado"}
            if not to_hyp:
                return {"status": "error", "message": f"Nodo destino '{to_node}' no encontrado"}

            # Construir camino simple
            path = [
                {"node": from_node, "type": "origin", "text": from_hyp.get("text", "")[:60]},
            ]

            # Si estan en el mismo dominio, camino directo
            if from_hyp.get("domain") == to_hyp.get("domain"):
                path.append({
                    "node": to_node,
                    "type": "destination",
                    "text": to_hyp.get("text", "")[:60],
                    "relation": "same_domain",
                })
            else:
                # Camino via escenario intermedio
                path.append({
                    "node": f"bridge_{from_hyp.get('domain')}_to_{to_hyp.get('domain')}",
                    "type": "bridge",
                    "relation": "cross_domain",
                })
                path.append({
                    "node": to_node,
                    "type": "destination",
                    "text": to_hyp.get("text", "")[:60],
                    "relation": "different_domain",
                })

            return {
                "status": "ok",
                "from": from_node,
                "to": to_node,
                "path": path,
                "path_length": len(path),
            }
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    # -----------------------------------------------------------------------
    # _cmd: Diario
    # -----------------------------------------------------------------------

    async def _cmd_journal_current(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handler para comando 'journal_current'."""
        if not self._core:
            return {"status": "error", "message": "VEOCore no disponible"}

        try:
            # Obtener ultima entrada del diario desde operations cycle
            metrics_history = list(self._core.operations._metrics_history)
            latest_metrics = metrics_history[-1] if metrics_history else {}

            # Construir entrada de diario
            entry = {
                "id": f"journal_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "period": "latest",
                "summary": {
                    "hypotheses_total": len(self._core.reasoning.hypotheses_history),
                    "validations_total": len(self._core.reasoning.validation_history),
                    "scenarios_total": len(self._core.forecast.scenarios_history),
                    "predictions_total": len(self._core.forecast.predictions_history),
                    "alerts_total": len(self._core.executive.alerts_history),
                },
                "latest_metrics": latest_metrics,
                "key_findings": [
                    {
                        "id": h.get("id"),
                        "text": h.get("text", "")[:100],
                        "confidence": h.get("confidence", 0),
                    }
                    for h in list(self._core.reasoning.hypotheses_history)[-5:]
                ],
            }

            return {"status": "ok", "entry": entry}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    async def _cmd_journal_generate(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handler para comando 'journal_generate'."""
        if not self._core:
            return {"status": "error", "message": "VEOCore no disponible"}

        try:
            # Generar nueva entrada del diario
            t0 = time.time()

            hypotheses = list(self._core.reasoning.hypotheses_history)
            validations = list(self._core.reasoning.validation_history)
            scenarios = list(self._core.forecast.scenarios_history)
            predictions = list(self._core.forecast.predictions_history)
            alerts = list(self._core.executive.alerts_history)

            # Calcular estadisticas
            validated = [v for v in validations if v.get("passed")]
            avg_confidence = 0
            if validated:
                avg_confidence = round(sum(v.get("confidence", 0) for v in validated) / len(validated), 1)

            # Recomendaciones basadas en alertas
            top_recommendations = []
            for a in alerts[-5:]:
                top_recommendations.append({
                    "alert_id": a.get("id"),
                    "recommendation": a.get("recommendation", "MONITORIZAR"),
                    "priority_score": a.get("priority_score", 0),
                })

            entry = {
                "id": f"journal_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "generated": True,
                "summary": {
                    "total_hypotheses": len(hypotheses),
                    "total_validated": len(validated),
                    "total_scenarios": len(scenarios),
                    "total_predictions": len(predictions),
                    "total_alerts": len(alerts),
                    "avg_validation_confidence": avg_confidence,
                },
                "top_hypotheses": [
                    {"text": h.get("text", "")[:120], "confidence": h.get("confidence", 0)}
                    for h in hypotheses[-5:]
                ],
                "active_alerts": top_recommendations,
                "system_health": (await self._core.health.check()).get("overall", "unknown"),
                "generation_time_ms": int((time.time() - t0) * 1000),
            }

            return {"status": "ok", "entry": entry, "message": "Diario generado correctamente"}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    # -----------------------------------------------------------------------
    # _cmd: Alertas
    # -----------------------------------------------------------------------

    async def _cmd_list_alerts(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handler para comando 'list_alerts'."""
        filters = ParamValidator.validate_filters(params.get("filters"))

        if not self._core:
            return {"status": "error", "message": "VEOCore no disponible"}

        try:
            alerts = list(self._core.executive.alerts_history)

            # Aplicar filtros
            if filters.get("min_priority"):
                min_p = int(filters["min_priority"])
                alerts = [a for a in alerts if a.get("priority_score", 0) >= min_p]
            if filters.get("recommendation"):
                rec = filters["recommendation"]
                alerts = [a for a in alerts if a.get("recommendation") == rec]

            limit = int(filters.get("limit", 50))
            alerts = alerts[-limit:]

            return {
                "status": "ok",
                "alerts": alerts,
                "total": len(alerts),
                "filters_applied": filters,
            }
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    async def _cmd_explain_alert(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handler para comando 'explain_alert'."""
        try:
            alert_id = ParamValidator.validate_id(params.get("alert_id", ""), "alerta")
        except HermesValidationError as exc:
            return {"status": "error", "message": str(exc)}

        if not self._core:
            return {"status": "error", "message": "VEOCore no disponible"}

        try:
            # Usar el sistema de explain de VEOCore
            explanation = await self._core.explain(alert_id)
            return {"status": "ok", "explanation": explanation}
        except Exception as exc:
            # Fallback: buscar manualmente
            for alert in self._core.executive.alerts_history:
                if alert.get("id") == alert_id:
                    finding = alert.get("finding", {})
                    eps = finding.get("eps", 0)
                    return {
                        "status": "ok",
                        "explanation": {
                            "alert_id": alert_id,
                            "what": finding.get("text", "N/A"),
                            "type": finding.get("type", "unknown"),
                            "eps_breakdown": {
                                "total_eps": eps,
                                "urgency": finding.get("urgency", 0),
                                "confidence": finding.get("confidence", 0),
                                "impact": finding.get("impact", 0),
                            },
                            "recommendation": alert.get("recommendation", "N/A"),
                            "explanation_text": alert.get("explanation", "Sin explicacion"),
                        },
                        "source": "fallback",
                    }
            return {"status": "error", "message": f"Alerta '{alert_id}' no encontrada"}

    # -----------------------------------------------------------------------
    # _cmd: Configuracion
    # -----------------------------------------------------------------------

    async def _cmd_get_config(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handler para comando 'get_config'."""
        config_info = {
            "commander": {
                "max_queue_size": self.max_queue_size,
                "command_timeout": self.command_timeout,
                "num_workers": self._num_workers,
                "running": self._running,
            },
            "veo_core_config": self.config,
        }

        if self._core:
            try:
                config_info["core_status"] = {
                    "running": self._core._running,
                    "version": "2.0.5",
                    "intervals": getattr(self._core, 'DEFAULT_INTERVALS', {}),
                }
            except Exception as e:
                logger.warning("[Hermes] Error al obtener info de nucleo: %s", e)

        return {"status": "ok", "config": config_info}

    async def _cmd_update_config(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handler para comando 'update_config' (solo desarrollo)."""
        key = str(params.get("key", "")).strip()
        value = params.get("value")

        if not key:
            return {"status": "error", "message": "La clave de configuracion es obligatoria"}

        # Solo permitir en modo desarrollo
        env = os.environ.get("VEO_ENV", "dev")
        if env == "prod":
            return {"status": "error", "message": "No se permite modificar config en produccion"}

        # Actualizar config local
        self.config[key] = value

        # Intentar propagar a VEOCore si esta corriendo
        if self._core:
            try:
                if not hasattr(self._core, 'config'):
                    self._core.config = {}
                self._core.config[key] = value
            except Exception as exc:
                return {"status": "warning", "message": f"Config actualizada localmente pero no en core: {exc}"}

        return {
            "status": "ok",
            "message": f"Config '{key}' actualizada",
            "new_value": value,
            "environment": env,
        }

    # -----------------------------------------------------------------------
    # _cmd: Operaciones
    # -----------------------------------------------------------------------

    async def _cmd_backup_now(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handler para comando 'backup_now'."""
        if not self._core:
            return {"status": "error", "message": "VEOCore no disponible"}

        try:
            # Forzar backup via operations cycle
            result = await self._core.operations._maybe_backup()

            if self._audit:
                await self._audit.record(
                    action="backup_now",
                    module="hermes_commander",
                    result=result,
                )

            return {"status": "ok", "backup": result}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    async def _cmd_restore_backup(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handler para comando 'restore_backup'."""
        timestamp = str(params.get("timestamp", "")).strip()
        if not timestamp:
            return {"status": "error", "message": "El timestamp del backup es obligatorio"}

        try:
            backup_dir = V2_ROOT / "backups"
            if not backup_dir.exists():
                return {"status": "error", "message": "No existe directorio de backups"}

            # Buscar backup por timestamp
            backup_files = sorted(backup_dir.glob("veo_backup_*.db"), key=lambda p: p.stat().st_mtime)
            target_backup = None
            for bf in backup_files:
                if timestamp in bf.name:
                    target_backup = bf
                    break

            if not target_backup:
                return {
                    "status": "error",
                    "message": f"Backup con timestamp '{timestamp}' no encontrado",
                    "available_backups": [b.name for b in backup_files[-10:]],
                }

            # En un sistema real, aqui se restauraria la DB
            # Por seguridad, solo reportamos que lo encontramos
            return {
                "status": "ok",
                "message": f"Backup encontrado: {target_backup.name}",
                "path": str(target_backup),
                "size_mb": round(target_backup.stat().st_size / (1024 * 1024), 2),
                "note": "La restauracion requiere confirmacion manual por seguridad",
            }
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    async def _cmd_list_backups(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handler para comando 'list_backups'."""
        try:
            backup_dir = V2_ROOT / "backups"
            if not backup_dir.exists():
                return {"status": "ok", "backups": [], "total": 0}

            backup_files = sorted(backup_dir.glob("veo_backup_*.db"), key=lambda p: p.stat().st_mtime, reverse=True)

            backups = []
            for bf in backup_files:
                stat = bf.stat()
                backups.append({
                    "name": bf.name,
                    "size_mb": round(stat.st_size / (1024 * 1024), 2),
                    "created": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                })

            return {"status": "ok", "backups": backups, "total": len(backups)}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    async def _cmd_get_metrics(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handler para comando 'get_metrics'."""
        metrics: dict[str, Any] = {
            "commander": {
                "commands_processed": len(self._command_history),
                "commands_queued": self._queue.qsize(),
                "uptime_seconds": round(time.time() - getattr(self, '_start_time', time.time()), 1),
            },
        }

        if self._core:
            try:
                # Obtener metricas del operations cycle
                ops_metrics = self._core.operations._compute_metrics()
                metrics["system"] = ops_metrics

                # Estadisticas de ciclos
                metrics["cycles"] = {
                    "reasoning": len(self._core.reasoning.hypotheses_history),
                    "forecast": len(self._core.forecast.scenarios_history),
                    "executive": len(self._core.executive.alerts_history),
                }

                # Recursos
                metrics["resources"] = self._core.resources.get_utilization()

            except Exception as exc:
                metrics["system_error"] = str(exc)

        return {"status": "ok", "metrics": metrics}

    async def _cmd_get_audit_log(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handler para comando 'get_audit_log'."""
        filters = ParamValidator.validate_filters(params.get("filters"))

        if self._audit:
            try:
                records = await self._audit.query(
                    filters=filters,
                    limit=int(filters.get("limit", 100)),
                )
                return {"status": "ok", "records": records, "total": len(records)}
            except Exception as exc:
                return {"status": "error", "message": f"Error consultando audit: {exc}"}

        # Fallback: historial local
        return {
            "status": "ok",
            "records": list(self._command_history)[-100:],
            "total": len(self._command_history),
            "source": "local_history",
        }

    # -----------------------------------------------------------------------
    # Health check propio
    # -----------------------------------------------------------------------

    async def _self_health_check(self) -> dict[str, Any]:
        """Health check del propio HermesCommander."""
        return {
            "status": "ok" if self._running else "stopped",
            "queue_size": self._queue.qsize(),
            "max_queue": self.max_queue_size,
            "commands_processed": len(self._command_history),
            "core_available": self.core_available,
        }

    # ============================================================================
    # METODOS DE CONVENIENCIA
    # ============================================================================

    def get_command_stats(self) -> dict[str, Any]:
        """
        Obtiene estadisticas de comandos procesados.

        Returns:
            Dict con estadisticas.
        """
        if not self._command_history:
            return {"total": 0}

        by_status: dict[str, int] = {}
        for entry in self._command_history:
            status = entry.get("result_status", "unknown")
            by_status[status] = by_status.get(status, 0) + 1

        return {
            "total": len(self._command_history),
            "by_status": by_status,
            "queue_current": self._queue.qsize(),
            "max_queue": self.max_queue_size,
        }

    async def wait_until_ready(self, timeout: float = 30.0) -> bool:
        """
        Espera hasta que el commander este listo.

        Args:
            timeout: Timeout maximo en segundos.

        Returns:
            True si esta listo, False si timeout.
        """
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self._running and (self._core is None or self.core_available):
                return True
            await asyncio.sleep(0.5)
        return False

    # ============================================================================
    # CONTEXT MANAGER
    # ============================================================================

    async def __aenter__(self) -> "HermesCommander":
        await self.start()
        self._start_time = time.time()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.stop()


# ============================================================================
# DEMO
# ============================================================================

async def _demo() -> None:
    """
    Demo completa del HermesCommander.

    Ejecuta varios comandos para demostrar la funcionalidad.
    """
    print("\n" + "=" * 70)
    print("  H E R M E S   C O M M A N D E R   v2  —  D E M O")
    print("=" * 70 + "\n")

    # Crear e iniciar
    print("[1] Iniciando HermesCommander...")
    commander = HermesCommander(config={
        "intervals": {
            "signal_scan": 3600,
            "narrative_analysis": 86400,
            "megatrend_review": 604800,
            "forecast_audit": 2592000,
        }
    })

    async with commander:
        print("     HermesCommander iniciado correctamente\n")

        # --- 2. Status ---
        print("-" * 50)
        print("[2] STATUS DEL SISTEMA")
        print("-" * 50)
        status = await commander.status()
        core_info = status.get("core", {})
        print(f"   VEOCore running     : {core_info.get('running', False)}")
        print(f"   Health              : {core_info.get('health', {}).get('overall', 'N/A')}")
        print(f"   Uptime              : {core_info.get('uptime_human', 'N/A')}")
        print(f"   Ciclos ejecutados   : {core_info.get('cycles_executed', {})}")
        print(f"   Alertas pendientes  : {core_info.get('pending_alerts', 0)}")
        print()

        # --- 3. Health ---
        print("-" * 50)
        print("[3] HEALTH CHECK")
        print("-" * 50)
        health = await commander.health()
        for comp, result in health.get("components", {}).items():
            icon = {"ok": "[OK]", "healthy": "[OK]", "error": "[FAIL]",
                    "warning": "[WARN]", "stopped": "[OFF]"}.get(result.get("status", ""), "[?]")
            print(f"   {icon} {comp:25s} : {result.get('status', 'N/A')}")
        print(f"   Overall: {health.get('status', 'N/A')}")
        print()

        # --- 4. Reasoning Cycle ---
        print("-" * 50)
        print("[4] EJECUTANDO: run_reasoning")
        print("-" * 50)
        r_reasoning = await commander.run_reasoning()
        result = r_reasoning.get("result", {})
        print(f"   Status              : {r_reasoning.get('status', 'N/A')}")
        print(f"   Hipotesis generadas : {result.get('hipotesis_generadas', 0)}")
        print(f"   Hipotesis validadas : {result.get('hipotesis_validadas', 0)}")
        print(f"   Senales procesadas  : {result.get('signals_processed', 0)}")
        for i, h in enumerate(result.get("hypotheses", [])[:3], 1):
            print(f"   Hipotesis #{i}       : {h[:80]}...")
        print()

        # --- 5. Forecast Cycle ---
        print("-" * 50)
        print("[5] EJECUTANDO: run_forecast")
        print("-" * 50)
        r_forecast = await commander.run_forecast()
        result = r_forecast.get("result", {})
        print(f"   Status              : {r_reasoning.get('status', 'N/A')}")
        print(f"   Escenarios generados: {result.get('escenarios_generados', 0)}")
        print(f"   Predicciones creadas: {result.get('predicciones_creadas', 0)}")
        for pid, prob in list(result.get("probabilidades", {}).items())[:3]:
            print(f"   Prediccion {pid[:16]}... : {prob}")
        print()

        # --- 6. Executive Cycle ---
        print("-" * 50)
        print("[6] EJECUTANDO: run_executive")
        print("-" * 50)
        r_executive = await commander.run_executive()
        result = r_executive.get("result", {})
        print(f"   Status              : {r_executive.get('status', 'N/A')}")
        print(f"   Total findings      : {result.get('total_findings', 0)}")
        for p in result.get("prioridades", [])[:5]:
            print(f"   Prioridad {p['id'][:12]}... : EPS={p.get('eps', 0)} type={p['type']}")
        print()

        # --- 7. Operations Cycle ---
        print("-" * 50)
        print("[7] EJECUTANDO: run_operations")
        print("-" * 50)
        r_operations = await commander.run_operations()
        result = r_operations.get("result", {})
        metrics = result.get("metricas", {})
        print(f"   Status              : {r_operations.get('status', 'N/A')}")
        print(f"   Health              : {metrics.get('overall_health', 'N/A')}")
        print(f"   CPU/Mem (sim)       : {metrics.get('cpu_percent', 0)}% / {metrics.get('memory_percent', 0)}%")
        print(f"   DB size             : {metrics.get('db_size_mb', 0)} MB")
        backup = result.get("estado_backups", {})
        print(f"   Backup realizado    : {backup.get('performed', False)}")
        print(f"   Integridad OK       : {result.get('integridad_ok', False)}")
        print()

        # --- 8. Hipotesis ---
        print("-" * 50)
        print("[8] GESTION DE HIPOTESIS")
        print("-" * 50)

        # Listar
        hypotheses = await commander.list_hypotheses()
        print(f"   Hipotesis en sistema: {hypotheses.get('total', 0)}")

        # Crear nueva
        new_hyp = await commander.create_hypothesis(
            text="La IA generativa transformara la educacion superior en los proximos 3 anos",
            context={"domain": "education", "source": "manual"},
            confidence=0.72,
        )
        print(f"   Nueva hipotesis     : {new_hyp.get('hypothesis', {}).get('id', 'N/A')}")
        print(f"   Texto               : {new_hyp.get('hypothesis', {}).get('text', 'N/A')[:70]}...")

        # Validar
        hyp_id = new_hyp.get("hypothesis", {}).get("id", "")
        if hyp_id:
            validation = await commander.validate_hypothesis(hyp_id)
            val_result = validation.get("validation", {})
            print(f"   Validacion          : scientific={val_result.get('scientific_score')}, "
                  f"skeptic={val_result.get('skeptic_score')}")
            print(f"   Veredicto           : {validation.get('veredicto', 'N/A')}")
        print()

        # --- 9. Escenarios ---
        print("-" * 50)
        print("[9] SIMULACION DE ESCENARIOS")
        print("-" * 50)

        # Listar escenarios existentes
        scenarios = await commander.list_scenarios()
        print(f"   Escenarios existentes: {scenarios.get('total', 0)}")

        # Simular uno nuevo si hay hipotesis
        if hyp_id:
            sim_result = await commander.simulate_scenario(
                hyp_id=hyp_id,
                variables={"time_horizon": "3y", "adoption_rate": 0.6},
                n_runs=500,
            )
            scenario = sim_result.get("scenario", {})
            print(f"   Escenario simulado  : {scenario.get('id', 'N/A')}")
            print(f"   Probabilidad base   : {scenario.get('base_probability')}")
            print(f"   Media Monte Carlo   : {scenario.get('monte_carlo_mean')}")
            print(f"   Simulaciones        : {scenario.get('simulations')}")
        print()

        # --- 10. Predicciones / Mercado ---
        print("-" * 50)
        print("[10] MERCADO DE PREDICCIONES")
        print("-" * 50)

        predictions = await commander.list_predictions()
        print(f"   Predicciones activas: {predictions.get('total', 0)}")

        market = await commander.get_prediction_market()
        mkt = market.get("market", {})
        print(f"   Mercado             : {mkt.get('total_predictions', 0)} predicciones")
        print(f"   Liquidez total      : {mkt.get('total_liquidity', 0)}")
        print(f"   Probabilidad media  : {mkt.get('avg_probability', 0)}")

        # Simular operacion
        preds_list = predictions.get("predictions", [])
        if preds_list:
            trade = await commander.trade_prediction(
                market_id=preds_list[0]["id"],
                scenario="yes",
                amount=100,
            )
            print(f"   Operacion           : {trade.get('status', 'N/A')}")
            trade_info = trade.get("trade", {})
            print(f"   Nueva probabilidad  : {trade_info.get('new_probability')}")
        print()

        # --- 11. Grafo ---
        print("-" * 50)
        print("[11] GRAFO DE CONOCIMIENTO")
        print("-" * 50)

        stats = await commander.graph_stats()
        gstats = stats.get("stats", {})
        print(f"   Nodos totales       : {gstats.get('total_nodes', 0)}")
        print(f"   Hipotesis           : {gstats.get('hypotheses', 0)}")
        print(f"   Escenarios          : {gstats.get('scenarios', 0)}")
        print(f"   Predicciones        : {gstats.get('predictions', 0)}")
        print(f"   Dominios            : {gstats.get('domains', {})}")

        communities = await commander.graph_communities()
        print(f"   Comunidades         : {communities.get('total_communities', 0)}")

        centrality = await commander.graph_centralidad()
        top_nodes = centrality.get("central_nodes", [])
        if top_nodes:
            print(f"   Nodo mas central    : {top_nodes[0].get('id', 'N/A')[:20]}... "
                  f"(score={top_nodes[0].get('centrality_score')})")
        print()

        # --- 12. Diario ---
        print("-" * 50)
        print("[12] DIARIO DEL SISTEMA")
        print("-" * 50)

        current = await commander.journal_current()
        entry = current.get("entry", {})
        print(f"   Entrada actual      : {entry.get('id', 'N/A')}")
        summary = entry.get("summary", {})
        print(f"   Resumen             : {summary}")

        generated = await commander.journal_generate()
        gen_entry = generated.get("entry", {})
        print(f"   Entrada generada    : {gen_entry.get('id', 'N/A')}")
        print(f"   Tiempo generacion   : {gen_entry.get('generation_time_ms', 0)}ms")
        print()

        # --- 13. Alertas ---
        print("-" * 50)
        print("[13] ALERTAS")
        print("-" * 50)

        alerts = await commander.list_alerts()
        print(f"   Alertas totales     : {alerts.get('total', 0)}")

        alert_list = alerts.get("alerts", [])
        if alert_list:
            first_alert = alert_list[0]
            alert_id = first_alert.get("id", "")
            print(f"   Explicando alerta   : {alert_id[:20]}...")
            explanation = await commander.explain_alert(alert_id)
            expl = explanation.get("explanation", {})
            print(f"   WHAT                : {str(expl.get('what', 'N/A'))[:70]}...")
            eps = expl.get("eps_breakdown", {})
            print(f"   EPS                 : {eps.get('total_eps', 'N/A')} "
                  f"(urg={eps.get('urgency_contribution', 0)} + "
                  f"conf={eps.get('confidence_contribution', 0)} + "
                  f"imp={eps.get('impact_contribution', 0)})")
            print(f"   Recomendacion       : {expl.get('recommendation', 'N/A')}")
        print()

        # --- 14. Config ---
        print("-" * 50)
        print("[14] CONFIGURACION")
        print("-" * 50)

        config = await commander.get_config()
        cfg = config.get("config", {})
        cmd_cfg = cfg.get("commander", {})
        print(f"   Max queue size      : {cmd_cfg.get('max_queue_size')}")
        print(f"   Command timeout     : {cmd_cfg.get('command_timeout')}s")
        print(f"   Workers             : {cmd_cfg.get('num_workers')}")
        print()

        # --- 15. Backups ---
        print("-" * 50)
        print("[15] BACKUPS")
        print("-" * 50)

        backup_result = await commander.backup_now()
        bk = backup_result.get("backup", {})
        print(f"   Backup status       : {bk.get('performed', False)}")
        if bk.get("file"):
            print(f"   Archivo             : {bk.get('file')}")

        backups = await commander.list_backups()
        print(f"   Backups disponibles : {backups.get('total', 0)}")
        print()

        # --- 16. Metrics ---
        print("-" * 50)
        print("[16] METRICAS")
        print("-" * 50)

        metrics = await commander.get_metrics()
        m = metrics.get("metrics", {})
        sys_metrics = m.get("system", {})
        print(f"   Health              : {sys_metrics.get('overall_health', 'N/A')}")
        print(f"   CPU/Mem             : {sys_metrics.get('cpu_percent', 0)}% / "
              f"{sys_metrics.get('memory_percent', 0)}%")
        print(f"   DB size             : {sys_metrics.get('db_size_mb', 0)} MB")
        print()

        # --- 17. Audit Log ---
        print("-" * 50)
        print("[17] AUDIT LOG")
        print("-" * 50)

        audit = await commander.get_audit_log()
        print(f"   Registros           : {audit.get('total', 0)}")
        print()

        # --- 18. Estadisticas finales ---
        print("-" * 50)
        print("[18] STATS DEL COMMANDER")
        print("-" * 50)
        stats = commander.get_command_stats()
        print(f"   Comandos procesados : {stats.get('total', 0)}")
        print(f"   Por status          : {stats.get('by_status', {})}")

    print("\n" + "=" * 70)
    print("  D E M O   C O M P L E T A D A")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(_demo())
