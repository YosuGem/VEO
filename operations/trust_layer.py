# trust_layer.py - VEO v2 Operations
# NOTA ARQUITECTONICA (v2.0.5): Este modulo es STANDALONE.
# VEOCore utiliza su propia implementacion interna de TrustLayer definida
# en core/veo_core.py (linea 1416). Este archivo en operations/ no es
# importado ni utilizado en produccion por el sistema principal.
# Se mantiene como referencia y para tests independientes.
"""
Trust Layer (Capa de Confianza) para VEO v2.

La clase TrustLayer asigna y mantiene puntuaciones de confianza
(Trust Score) para cada motor/modulo del sistema. Los scores se
ajustan dinamicamente basados en el historial de exitos y fracasos.

Cada modulo comienza con un score inicial (default 50) que evoluciona
con el tiempo:
    - Aciertos aumentan el score (reward acumulativo)
    - Fallos lo reducen (penalizacion severa por fallos consecutivos)
    - El score se mantiene entre 0 y 100

Componentes con trust score:
    - veo_core: Motor de razonamiento
    - hermes_commander: Motor de ejecucion
    - agente_escuchador: Recoleccion de datos
    - agente_cientifico: Validacion cientifica
    - mercado: Mercado de predicciones
    - api: Servidor API

Ejemplo de uso:
    >>> from veo_v2.operations.trust_layer import TrustLayer
    >>> trust = TrustLayer()
    >>> await trust.initialize()
    >>> await trust.update_score("veo_core", success=True, accuracy=0.92)
    >>> score = await trust.get_score("veo_core")
    55.5
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from operations.logger import get_logger
except ImportError:
    import logging
    get_logger = lambda name: logging.getLogger(name)

try:
    from veo_v2.core.db import (
        inicializar_trust_score,
        actualizar_trust_score,
        obtener_trust_score,
        listar_trust_scores,
    )
    _DB_DISPONIBLE = True
except ImportError:
    _DB_DISPONIBLE = False

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

DEFAULT_INITIAL_SCORE = 50.0
DEFAULT_MAX_SCORE = 100.0
DEFAULT_MIN_SCORE = 0.0

# Factores de reward/penalty
REWARD_BASE = 5.0           # Reward base por acierto
REWARD_ACUMULATIVO = 0.5    # Incremento por acierto consecutivo
REWARD_MAX = 15.0           # Maximo reward por acierto

PENALTY_BASE = 5.0          # Penalizacion base por fallo
PENALTY_ACUMULATIVO = 2.0   # Incremento por fallo consecutivo
PENALTY_MAX = 20.0          # Maxima penalizacion por fallo

# Peso de la precision en el ajuste
PRECISION_WEIGHT = 5.0      # Puntos extra por precision perfecta

# Thresholds
SCORE_CONFIABLE = 70.0      # Score minimo para considerar confiable
SCORE_DUBITATIVO = 40.0     # Score minimo para no considerar dubitativo
SCORE_CRITICO = 20.0        # Score por debajo del cual se alerta

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------

_log = get_logger("operations.trust")


# ---------------------------------------------------------------------------
# Dataclass para Trust Score
# ---------------------------------------------------------------------------

@dataclass
class TrustScore:
    """
    Puntuacion de confianza de un modulo.

    Attributes:
        modulo: Nombre del modulo.
        score: Puntuacion actual (0-100).
        score_inicial: Puntuacion inicial.
        ejecuciones_total: Total de ejecuciones.
        ejecuciones_exitosas: Ejecuciones exitosas.
        ejecuciones_fallidas: Ejecuciones fallidas.
        fallos_consecutivos: Fallos consecutivos actuales.
        aciertos_consecutivos: Aciertos consecutivos actuales.
        precision_acumulada: Suma de precisiones registradas.
        ultima_actualizacion: Timestamp de ultima actualizacion.
    """

    modulo: str
    score: float = DEFAULT_INITIAL_SCORE
    score_inicial: float = DEFAULT_INITIAL_SCORE
    ejecuciones_total: int = 0
    ejecuciones_exitosas: int = 0
    ejecuciones_fallidas: int = 0
    fallos_consecutivos: int = 0
    aciertos_consecutivos: int = 0
    precision_acumulada: float = 0.0
    ultima_actualizacion: str = ""

    @property
    def precision_promedio(self) -> float:
        """Precision promedio de las ejecuciones exitosas."""
        if self.ejecuciones_exitosas == 0:
            return 0.0
        return self.precision_acumulada / self.ejecuciones_exitosas

    @property
    def tasa_exito(self) -> float:
        """Tasa de exito (0.0 - 1.0)."""
        if self.ejecuciones_total == 0:
            return 0.0
        return self.ejecuciones_exitosas / self.ejecuciones_total

    @property
    def es_confiable(self) -> bool:
        """True si el score es suficientemente alto."""
        return self.score >= SCORE_CONFIABLE

    @property
    def es_dubitativo(self) -> bool:
        """True si el score es bajo."""
        return self.score < SCORE_DUBITATIVO

    @property
    def es_critico(self) -> bool:
        """True si el score es critico."""
        return self.score < SCORE_CRITICO

    @property
    def nivel_confianza(self) -> str:
        """Nivel de confianza como string."""
        if self.score >= SCORE_CONFIABLE:
            return "confiable"
        elif self.score >= SCORE_DUBITATIVO:
            return "moderado"
        elif self.score >= SCORE_CRITICO:
            return "dubitativo"
        else:
            return "critico"

    def to_dict(self) -> dict[str, Any]:
        """Convierte a diccionario."""
        return {
            "modulo": self.modulo,
            "score": round(self.score, 2),
            "score_inicial": self.score_inicial,
            "nivel_confianza": self.nivel_confianza,
            "ejecuciones_total": self.ejecuciones_total,
            "ejecuciones_exitosas": self.ejecuciones_exitosas,
            "ejecuciones_fallidas": self.ejecuciones_fallidas,
            "tasa_exito": round(self.tasa_exito, 4),
            "fallos_consecutivos": self.fallos_consecutivos,
            "aciertos_consecutivos": self.aciertos_consecutivos,
            "precision_promedio": round(self.precision_promedio, 4),
            "es_confiable": self.es_confiable,
            "es_dubitativo": self.es_dubitativo,
            "es_critico": self.es_critico,
            "ultima_actualizacion": self.ultima_actualizacion,
        }


# ---------------------------------------------------------------------------
# Clase TrustLayer
# ---------------------------------------------------------------------------

class TrustLayer:
    """
    Capa de confianza de VEO v2.

    Gestiona los trust scores de todos los modulos, ajustandolos
    dinamicamente segun sus resultados.

    Attributes:
        scores: Cache en memoria de trust scores.
        default_score: Score inicial para nuevos modulos.
    """

    # Modulos estandar del sistema
    MODULOS_DEFAULT = [
        "veo_core",
        "hermes_commander",
        "agente_escuchador",
        "agente_cientifico",
        "mercado",
        "api",
        "operations",
    ]

    def __init__(self, default_score: float = DEFAULT_INITIAL_SCORE) -> None:
        """
        Inicializa la capa de confianza.

        Args:
            default_score: Score inicial para nuevos modulos.
        """
        self.default_score = default_score
        self._scores: dict[str, TrustScore] = {}
        self._historial_cambios: list[dict[str, Any]] = []

    async def initialize(self) -> None:
        """
        Inicializa los trust scores para todos los modulos estandar.

        Crea registros en la base de datos si no existen.
        """
        for modulo in self.MODULOS_DEFAULT:
            await self._inicializar_modulo(modulo)
        _log.info(f"Trust Layer inicializado con {len(self.MODULOS_DEFAULT)} modulos")

    async def _inicializar_modulo(self, modulo: str) -> None:
        """Inicializa un modulo si no existe."""
        if modulo in self._scores:
            return

        if _DB_DISPONIBLE:
            try:
                await inicializar_trust_score(modulo, self.default_score)
                db_data = await obtener_trust_score(modulo)
                if db_data:
                    self._scores[modulo] = self._db_to_trust_score(db_data)
                    return
            except Exception as exc:
                _log.warning(f"Error inicializando trust score en DB para {modulo}: {exc}")

        # Crear en memoria si no hay DB
        self._scores[modulo] = TrustScore(
            modulo=modulo,
            score=self.default_score,
            score_inicial=self.default_score,
            ultima_actualizacion=_ahora(),
        )

    def _db_to_trust_score(self, db_data: dict[str, Any]) -> TrustScore:
        """Convierte datos de DB a TrustScore."""
        return TrustScore(
            modulo=db_data["modulo"],
            score=db_data["score"],
            score_inicial=db_data["score_inicial"],
            ejecuciones_total=db_data.get("ejecuciones_total", 0),
            ejecuciones_exitosas=db_data.get("ejecuciones_exitosas", 0),
            ejecuciones_fallidas=db_data.get("ejecuciones_fallidas", 0),
            fallos_consecutivos=db_data.get("fallos_consecutivos", 0),
            aciertos_consecutivos=db_data.get("aciertos_consecutivos", 0),
            precision_acumulada=db_data.get("precision_acumulada", 0.0),
            ultima_actualizacion=db_data.get("ultima_actualizacion", _ahora()),
        )

    # -----------------------------------------------------------------------
    # Actualizacion de scores
    # -----------------------------------------------------------------------

    async def update_score(
        self,
        module: str,
        success: bool,
        accuracy: float | None = None,
    ) -> dict[str, Any]:
        """
        Actualiza el trust score de un modulo basado en resultado.

        Args:
            module: Nombre del modulo.
            success: True si la ejecucion fue exitosa.
            accuracy: Precision opcional (0.0 - 1.0).

        Returns:
            Diccionario con el estado actualizado del trust score.

        Ejemplo:
            >>> await trust.update_score("veo_core", success=True, accuracy=0.92)
            {'modulo': 'veo_core', 'score': 55.5, 'nivel': 'moderado', ...}
        """
        if module not in self._scores:
            await self._inicializar_modulo(module)

        score_obj = self._scores[module]

        # Actualizar contadores
        score_obj.ejecuciones_total += 1
        score_obj.ultima_actualizacion = _ahora()

        if success:
            score_obj.ejecuciones_exitosas += 1
            score_obj.aciertos_consecutivos += 1
            score_obj.fallos_consecutivos = 0

            # Calcular reward
            reward = min(
                REWARD_BASE + score_obj.aciertos_consecutivos * REWARD_ACUMULATIVO,
                REWARD_MAX,
            )

            # Bonus por precision
            if accuracy is not None:
                score_obj.precision_acumulada += accuracy
                precision_bonus = accuracy * PRECISION_WEIGHT
                reward += precision_bonus

            score_obj.score = min(DEFAULT_MAX_SCORE, score_obj.score + reward)

            _log.debug(
                f"Trust +{reward:.1f} para {module}: {score_obj.score:.1f} "
                f"(aciertos_consecutivos={score_obj.aciertos_consecutivos})"
            )
        else:
            score_obj.ejecuciones_fallidas += 1
            score_obj.fallos_consecutivos += 1
            score_obj.aciertos_consecutivos = 0

            # Calcular penalizacion
            penalty = min(
                PENALTY_BASE + score_obj.fallos_consecutivos * PENALTY_ACUMULATIVO,
                PENALTY_MAX,
            )
            score_obj.score = max(DEFAULT_MIN_SCORE, score_obj.score - penalty)

            _log.warning(
                f"Trust -{penalty:.1f} para {module}: {score_obj.score:.1f} "
                f"(fallos_consecutivos={score_obj.fallos_consecutivos})"
            )

        # Persistir en DB
        if _DB_DISPONIBLE:
            try:
                await actualizar_trust_score(module, success, accuracy)
            except Exception as exc:
                _log.warning(f"Error persistiendo trust score: {exc}")

        # Registrar en historial
        self._historial_cambios.append({
            "timestamp": _ahora(),
            "modulo": module,
            "success": success,
            "accuracy": accuracy,
            "nuevo_score": score_obj.score,
            "reward" if success else "penalty": reward if success else penalty,
        })

        return {
            "modulo": module,
            "score": round(score_obj.score, 2),
            "nivel_confianza": score_obj.nivel_confianza,
            "tasa_exito": round(score_obj.tasa_exito, 4),
            "ejecuciones_total": score_obj.ejecuciones_total,
            "fallos_consecutivos": score_obj.fallos_consecutivos,
            "aciertos_consecutivos": score_obj.aciertos_consecutivos,
        }

    # -----------------------------------------------------------------------
    # Consultas
    # -----------------------------------------------------------------------

    async def get_score(self, module: str) -> TrustScore | None:
        """
        Obtiene el trust score de un modulo.

        Args:
            module: Nombre del modulo.

        Returns:
            TrustScore del modulo, o None si no existe.
        """
        if module not in self._scores:
            await self._inicializar_modulo(module)
        return self._scores.get(module)

    async def get_score_value(self, module: str) -> float:
        """
        Obtiene solo el valor numerico del score.

        Args:
            module: Nombre del modulo.

        Returns:
            Score actual (0-100), o 0 si no existe.
        """
        score = await self.get_score(module)
        return score.score if score else 0.0

    async def get_all_scores(self) -> dict[str, TrustScore]:
        """
        Obtiene todos los trust scores.

        Returns:
            Diccionario {modulo: TrustScore}.
        """
        return dict(self._scores)

    async def get_all_scores_dict(self) -> dict[str, dict[str, Any]]:
        """
        Obtiene todos los trust scores como diccionarios.

        Returns:
            Diccionario {modulo: dict}.
        """
        return {k: v.to_dict() for k, v in self._scores.items()}

    async def get_resumen(self) -> dict[str, Any]:
        """
        Obtiene un resumen de todos los trust scores.

        Returns:
            Diccionario con estadisticas globales.
        """
        if not self._scores:
            return {"total_modulos": 0, "score_promedio": 0}

        scores_valores = [s.score for s in self._scores.values()]
        total_ejecuciones = sum(s.ejecuciones_total for s in self._scores.values())
        total_exitosas = sum(s.ejecuciones_exitosas for s in self._scores.values())

        return {
            "total_modulos": len(self._scores),
            "score_promedio": round(sum(scores_valores) / len(scores_valores), 2),
            "score_max": round(max(scores_valores), 2),
            "score_min": round(min(scores_valores), 2),
            "modulos_confiables": sum(1 for s in self._scores.values() if s.es_confiable),
            "modulos_dubitativo": sum(1 for s in self._scores.values() if s.es_dubitativo),
            "modulos_criticos": sum(1 for s in self._scores.values() if s.es_critico),
            "total_ejecuciones": total_ejecuciones,
            "tasa_exito_global": round(total_exitosas / total_ejecuciones, 4) if total_ejecuciones > 0 else 0,
            "detalle": await self.get_all_scores_dict(),
        }

    # -----------------------------------------------------------------------
    # Utilidades
    # -----------------------------------------------------------------------

    async def reset_score(self, module: str) -> None:
        """
        Resetea el trust score de un modulo a su valor inicial.

        Args:
            module: Nombre del modulo.
        """
        if module in self._scores:
            self._scores[module].score = self._scores[module].score_inicial
            self._scores[module].ejecuciones_total = 0
            self._scores[module].ejecuciones_exitosas = 0
            self._scores[module].ejecuciones_fallidas = 0
            self._scores[module].fallos_consecutivos = 0
            self._scores[module].aciertos_consecutivos = 0
            self._scores[module].precision_acumulada = 0.0
            self._scores[module].ultima_actualizacion = _ahora()

        if _DB_DISPONIBLE:
            try:
                await inicializar_trust_score(module, self.default_score)
            except Exception as exc:
                _log.warning(f"Error reseteando trust score: {exc}")

    async def penalizar(self, module: str, puntos: float = 10.0) -> float:
        """
        Aplica una penalizacion manual a un modulo.

        Args:
            module: Nombre del modulo.
            puntos: Puntos a restar.

        Returns:
            Nuevo score.
        """
        if module not in self._scores:
            await self._inicializar_modulo(module)

        score_obj = self._scores[module]
        score_obj.score = max(DEFAULT_MIN_SCORE, score_obj.score - puntos)
        score_obj.ultima_actualizacion = _ahora()

        _log.warning(f"Penalizacion manual de {puntos} a {module}: {score_obj.score:.1f}")
        return score_obj.score

    async def premiar(self, module: str, puntos: float = 10.0) -> float:
        """
        Aplica un premio manual a un modulo.

        Args:
            module: Nombre del modulo.
            puntos: Puntos a sumar.

        Returns:
            Nuevo score.
        """
        if module not in self._scores:
            await self._inicializar_modulo(module)

        score_obj = self._scores[module]
        score_obj.score = min(DEFAULT_MAX_SCORE, score_obj.score + puntos)
        score_obj.ultima_actualizacion = _ahora()

        _log.info(f"Premio manual de {puntos} a {module}: {score_obj.score:.1f}")
        return score_obj.score

    def get_historial_cambios(self, modulo: str | None = None) -> list[dict[str, Any]]:
        """
        Obtiene el historial de cambios de trust scores.

        Args:
            modulo: Filtrar por modulo.

        Returns:
            Lista de cambios.
        """
        if modulo:
            return [h for h in self._historial_cambios if h["modulo"] == modulo]
        return self._historial_cambios[:]


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
        print("DEMO: Trust Layer VEO v2")
        print("=" * 60)

        trust = TrustLayer(default_score=50.0)
        await trust.initialize()

        print("\n--- Scores iniciales ---")
        scores = await trust.get_all_scores_dict()
        for modulo, data in scores.items():
            print(f"  {modulo:25s}: {data['score']:6.1f} ({data['nivel_confianza']})")

        print("\n--- Simulando ejecuciones ---")

        # Simular aciertos consecutivos
        for i in range(5):
            resultado = await trust.update_score("veo_core", success=True, accuracy=0.85 + i * 0.02)
            print(f"  Acierto {i+1} veo_core: score={resultado['score']:.1f}, "
                  f"aciertos_consecutivos={resultado['aciertos_consecutivos']}")

        # Simular fallos consecutivos
        print()
        for i in range(4):
            resultado = await trust.update_score("mercado", success=False)
            print(f"  Fallo {i+1} mercado: score={resultado['score']:.1f}, "
                  f"fallos_consecutivos={resultado['fallos_consecutivos']}")

        # Mixto
        print()
        await trust.update_score("api", success=True, accuracy=0.95)
        await trust.update_score("api", success=True, accuracy=0.88)
        await trust.update_score("api", success=False)
        await trust.update_score("api", success=True, accuracy=0.91)
        api_score = await trust.get_score("api")
        print(f"  Mixto api: score={api_score.score:.1f}, "
              f"tasa_exito={api_score.tasa_exito:.2%}")

        print("\n--- Scores finales ---")
        resumen = await trust.get_resumen()
        print(f"  Score promedio: {resumen['score_promedio']}")
        print(f"  Score max: {resumen['score_max']}")
        print(f"  Score min: {resumen['score_min']}")
        print(f"  Modulos confiables: {resumen['modulos_confiables']}")
        print(f"  Modulos criticos: {resumen['modulos_criticos']}")

        print("\n--- Detalle final ---")
        for modulo, data in resumen["detalle"].items():
            status_icon = {
                "confiable": "[+]",
                "moderado": "[~]",
                "dubitativo": "[!]",
                "critico": "[X]",
            }.get(data["nivel_confianza"], "[?]")
            print(f"  {status_icon} {modulo:25s}: {data['score']:6.1f} | "
                  f"{data['nivel_confianza']:12s} | "
                  f"exito: {data['tasa_exito']:.1%} | "
                  f"ejecuciones: {data['ejecuciones_total']}")

        print("\n" + "=" * 60)
        print("Demo completada.")
        print("=" * 60)

    asyncio.run(demo())
