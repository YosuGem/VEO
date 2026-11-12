# core/__init__.py - VEO v2 Core Layer
"""
Nucleo central de VEO v2.

Incluye veo_core (cerebro), hermes_commander (interfaz),
event_bus (comunicacion) y scheduler (planificador).
"""

from .veo_core import VEOCore
from .config import Settings as Config

__all__ = ["VEOCore", "Config"]
