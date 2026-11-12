# tests/__init__.py - VEO v2 Test Suite
"""
Suite de tests para VEO v2: Sistema Operativo para Intuicion Social.

Tests incluidos:
- test_core.py: Tests de configuracion, base de datos, nucleo y eventos
- test_analysis.py: Tests de agentes de analisis (hipotesis, causal, escenarios)
- test_operations.py: Tests de capa operativa (logs, salud, auditoria)
- test_integration.py: Tests end-to-end de ciclos completos

Ejecucion:
    pytest tests/ -v --tb=short
    pytest tests/ -v --cov=veo_v2 --cov-report=html
"""

__version__ = "2.0.5"
