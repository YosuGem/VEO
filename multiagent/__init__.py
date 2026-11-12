# multiagent - VEO v2
"""
Paquete multiagent de VEO v2.

Contiene el HermesCommander: la interfaz unificada entre el usuario
y el cerebro (VEOCore). Es el UNICO punto de entrada para comandos.

Componentes:
    - HermesCommander: Orquestador de comandos con cola priorizada
    - Command: Representacion de un comando encolado
    - CommandPriority: Niveles de prioridad (HIGH/MEDIUM/LOW)
    - ParamValidator: Validador de parametros de entrada

Uso:
    >>> from veo_v2.multiagent.hermes_commander import HermesCommander
    >>> commander = HermesCommander()
    >>> await commander.start()
    >>> status = await commander.status()
    >>> await commander.stop()
"""

from __future__ import annotations

try:
    from .hermes_commander import (
        HermesCommander,
        CommandPriority,
        HermesError,
        HermesValidationError,
        HermesQueueFullError,
        HermesTimeoutError,
        HermesNotRunningError,
    )
    __all__ = [
        "HermesCommander",
        "CommandPriority",
        "HermesError",
        "HermesValidationError",
        "HermesQueueFullError",
        "HermesTimeoutError",
        "HermesNotRunningError",
    ]
except ImportError:
    __all__ = []
