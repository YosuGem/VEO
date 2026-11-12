# memory/__init__.py - VEO v2 Memory Layer
"""
Capa de memoria y persistencia de VEO v2.

Incluye gestion de estado a corto y largo plazo,
embeddings vectoriales y cache de resultados.
"""

from .discovery_journal import DiarioDescubrimientos

__all__ = ["DiarioDescubrimientos"]
