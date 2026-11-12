# prediction/__init__.py - VEO v2 Prediction Layer
"""
Capa de prediccion y forecasting de VEO v2.

Incluye modelos predictivos, series temporales
y mercado de predicciones interno.
"""

from .prediction_market import MercadoPredicciones

__all__ = ["MercadoPredicciones"]
