"""
VEO v2 - API Package
API RESTful + WebSocket para VEO v2.
Todas las operaciones pasan por HermesCommander.
"""

from .api_server import app, lifespan, commander, MockDatabase

__version__ = "2.0.5"
__all__ = ["app", "lifespan", "commander", "MockDatabase"]
