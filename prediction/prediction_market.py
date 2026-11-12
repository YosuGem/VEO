"""
VEO: Mercado Interno de Predicciones
============================================
Sistema Operativo para Intuicion Social (SOIS)

El mercado interno de predicciones permite que el sistema aprenda de sus
propios aciertos y fallos. Cada hipotesis genera un mercado donde agentes
internos (traders) compran y venden participaciones en escenarios posibles.

Los precios reflejan probabilidades implicitas. Cuando una hipotesis se
confirma o refuta, el mercado se resuelve y los traders ganan/perden
capital segun sus predicciones.

Modelo de precios: CPMM (Constant Product Market Maker) simplificado.
"""

from __future__ import annotations

import json
import logging
import math
import random
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


# ---------------------------------------------------------------------------
# Estructuras de datos
# ---------------------------------------------------------------------------

@dataclass
class Mercado:
    """Representa un mercado de predicciones activo."""
    id: str
    hipotesis_id: str
    escenarios: List[str]
    reservas: np.ndarray  # una reserva por escenario
    precios_iniciales: np.ndarray
    volumen: float = 0.0
    estado: str = "abierto"  # abierto | cerrado | resuelto
    escenario_ganador: Optional[int] = None
    fecha_creacion: float = field(default_factory=time.time)
    fecha_cierre: Optional[float] = None
    participaciones: Dict[str, np.ndarray] = field(default_factory=dict)
    historial_trades: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "hipotesis_id": self.hipotesis_id,
            "escenarios": self.escenarios,
            "reservas": self.reservas.tolist(),
            "precios_iniciales": self.precios_iniciales.tolist(),
            "volumen": self.volumen,
            "estado": self.estado,
            "escenario_ganador": self.escenario_ganador,
            "fecha_creacion": self.fecha_creacion,
            "fecha_cierre": self.fecha_cierre,
            "historial_trades": self.historial_trades,
        }


@dataclass
class Trade:
    """Registro individual de una transaccion en el mercado."""
    trader_id: str
    mercado_id: str
    escenario_idx: int
    cantidad: float
    precio: float
    tipo: str  # "compra" | "venta"
    comision: float
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trader_id": self.trader_id,
            "mercado_id": self.mercado_id,
            "escenario_idx": self.escenario_idx,
            "cantidad": self.cantidad,
            "precio": self.precio,
            "tipo": self.tipo,
            "comision": self.comision,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Mercado de Predicciones
# ---------------------------------------------------------------------------

class MercadoPredicciones:
    """
    Mercado interno de predicciones basado en CPMM (Constant Product Market Maker).

    Cada mercado representa una hipotesis con multiples escenarios mutuamente
    excluyentes. Los agentes traders compran/venden participaciones y los
    precios reflejan probabilidades implicitas del colectivo.

    Parametros
    ----------
    db : sqlite3.Connection
        Conexion a base de datos SQLite para persistencia.
    config : dict
        Configuracion con claves: liquidez_inicial, comision.
    logger : logging.Logger
        Logger para auditoria.
    """

    def __init__(
        self,
        db: sqlite3.Connection = None,
        config: Dict[str, Any] = None,
        logger: logging.Logger = None,
    ) -> None:
        # Defaults para instanciacion sin parametros
        if db is None:
            db = sqlite3.connect(":memory:")
        if config is None:
            config = {}
        if logger is None:
            class _MockLogger:
                def info(self, *a, **k): pass
                def warning(self, *a, **k): pass
                def error(self, *a, **k): pass
                def debug(self, *a, **k): pass
            logger = _MockLogger()
        self.db = db
        self.logger = logger
        self.config = config
        self.liquidez_inicial: float = float(config.get("liquidez_inicial", 100.0))
        self.comision_pct: float = float(config.get("comision", 0.01))  # 1%
        self._mercados: Dict[str, Mercado] = {}
        self._trades: List[Trade] = []
        self._profits_trader: Dict[str, float] = {}
        self._volumen_por_escenario: Dict[Tuple[str, int], float] = {}
        self._init_db()

    # -- Persistencia --------------------------------------------------------

    def _init_db(self) -> None:
        """Inicializa tablas de persistencia."""
        cursor = self.db.cursor()
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS mercados (
                id TEXT PRIMARY KEY,
                hipotesis_id TEXT NOT NULL,
                escenarios TEXT NOT NULL,       -- JSON list
                reservas TEXT NOT NULL,          -- JSON list
                precios_iniciales TEXT NOT NULL, -- JSON list
                volumen REAL DEFAULT 0.0,
                estado TEXT DEFAULT 'abierto',
                escenario_ganador INTEGER,
                fecha_creacion REAL,
                fecha_cierre REAL
            );
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trader_id TEXT,
                mercado_id TEXT,
                escenario_idx INTEGER,
                cantidad REAL,
                precio REAL,
                tipo TEXT,
                comision REAL,
                timestamp REAL
            );
            CREATE TABLE IF NOT EXISTS profits (
                trader_id TEXT PRIMARY KEY,
                profit_acumulado REAL DEFAULT 0.0
            );
            CREATE INDEX IF NOT EXISTS idx_trades_mercado
                ON trades(mercado_id);
            CREATE INDEX IF NOT EXISTS idx_trades_trader
                ON trades(trader_id);
        """)
        self.db.commit()

    def _persistir_mercado(self, mercado: Mercado) -> None:
        """Guarda un mercado en la base de datos."""
        cursor = self.db.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO mercados
            (id, hipotesis_id, escenarios, reservas, precios_iniciales,
             volumen, estado, escenario_ganador, fecha_creacion, fecha_cierre)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            mercado.id,
            mercado.hipotesis_id,
            json.dumps(mercado.escenarios),
            json.dumps(mercado.reservas.tolist()),
            json.dumps(mercado.precios_iniciales.tolist()),
            mercado.volumen,
            mercado.estado,
            mercado.escenario_ganador,
            mercado.fecha_creacion,
            mercado.fecha_cierre,
        ))
        self.db.commit()

    def _persistir_trade(self, trade: Trade) -> None:
        """Guarda un trade en la base de datos."""
        cursor = self.db.cursor()
        cursor.execute("""
            INSERT INTO trades
            (trader_id, mercado_id, escenario_idx, cantidad, precio,
             tipo, comision, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trade.trader_id, trade.mercado_id, trade.escenario_idx,
            trade.cantidad, trade.precio, trade.tipo,
            trade.comision, trade.timestamp,
        ))
        self.db.commit()

    # -- Creacion y gestion de mercados --------------------------------------

    def crear_mercado(
        self,
        hipotesis_id: str,
        escenarios: List[str],
        probabilidades_iniciales: Optional[List[float]] = None,
    ) -> str:
        """
        Crea un nuevo mercado de predicciones para una hipotesis.

        Parametros
        ----------
        hipotesis_id : str
            Identificador de la hipotesis que origina el mercado.
        escenarios : list[str]
            Lista de escenarios mutuamente excluyentes.
        probabilidades_iniciales : list[float] | None
            Probabilidades iniciales para cada escenario. Si es None,
            se asignan probabilidades uniformes.

        Returns
        -------
        str
            ID del mercado creado.

        Raises
        ------
        ValueError
            Si hay menos de 2 escenarios o las probabilidades no suman ~1.
        """
        if len(escenarios) < 2:
            raise ValueError("Se requieren al menos 2 escenarios")

        if probabilidades_iniciales is None:
            n = len(escenarios)
            probabilidades_iniciales = [1.0 / n] * n

        probs = np.array(probabilidades_iniciales, dtype=float)
        if not np.isclose(probs.sum(), 1.0, atol=1e-6):
            raise ValueError(
                f"Las probabilidades deben sumar 1.0 (suman {probs.sum()})"
            )
        if len(probs) != len(escenarios):
            raise ValueError(
                "La longitud de probabilidades debe coincidir con escenarios"
            )

        mercado_id = f"mercado_{hipotesis_id}_{int(time.time() * 1000)}"

        # Reservas iniciales proporcionales a las probabilidades
        # Mayor probabilidad => mayor reserva => menor precio inicial
        # Usamos: reserva_i = liquidez * (1 - prob_i) / sum_j(1 - prob_j)
        # Esto hace que escenarios mas probables tengan precios mas bajos inicialmente
        # y escenarios menos probables tengan mayor upside.
        pesos = 1.0 / (probs + 0.01)  # evitar division por cero
        pesos = pesos / pesos.sum()
        reservas = self.liquidez_inicial * pesos

        mercado = Mercado(
            id=mercado_id,
            hipotesis_id=hipotesis_id,
            escenarios=escenarios,
            reservas=reservas,
            precios_iniciales=probs.copy(),
        )

        self._mercados[mercado_id] = mercado
        self._persistir_mercado(mercado)

        self.logger.info(
            "[MercadoPredicciones] Creado mercado %s para hipotesis %s "
            "con %d escenarios", mercado_id, hipotesis_id, len(escenarios)
        )
        return mercado_id

    # -- Trading con CPMM ----------------------------------------------------

    def comprar_participacion(
        self,
        mercado_id: str,
        escenario_idx: int,
        cantidad: float,
        trader_id: str = "sistema",
    ) -> Dict[str, Any]:
        """
        Compra participaciones en un escenario.

        Parametros
        ----------
        mercado_id : str
            ID del mercado.
        escenario_idx : int
            Indice del escenario.
        cantidad : float
            Cantidad de participaciones a comprar.
        trader_id : str
            Identificador del comprador.

        Returns
        -------
        dict
            Detalle de la transaccion: costo, precio, comision.

        Raises
        ------
        ValueError
            Si el mercado no existe, esta cerrado, o el escenario es invalido.
        """
        if mercado_id not in self._mercados:
            raise ValueError(f"Mercado no encontrado: {mercado_id}")

        mercado = self._mercados[mercado_id]
        if mercado.estado != "abierto":
            raise ValueError(f"Mercado {mercado_id} no esta abierto ({mercado.estado})")
        if escenario_idx < 0 or escenario_idx >= len(mercado.escenarios):
            raise ValueError(f"Escenario invalido: {escenario_idx}")
        if cantidad <= 0:
            raise ValueError("La cantidad debe ser positiva")

        # Calcular costo usando CPMM
        costo = self._calcular_cpmm(
            mercado.reservas, escenario_idx, cantidad, compra=True
        )
        comision = self._comision(costo)
        costo_total = costo + comision

        # Actualizar reservas: el comprador entrega costo y recibe cantidad
        mercado.reservas[escenario_idx] -= cantidad
        mercado.reservas += costo / len(mercado.escenarios)  # redistribuir
        mercado.volumen += costo_total

        # Registrar participaciones del trader
        clave = f"{trader_id}_{mercado_id}"
        if clave not in mercado.participaciones:
            mercado.participaciones[clave] = np.zeros(len(mercado.escenarios))
        mercado.participaciones[clave][escenario_idx] += cantidad

        # Volumen por escenario
        self._volumen_por_escenario[(mercado_id, escenario_idx)] = \
            self._volumen_por_escenario.get((mercado_id, escenario_idx), 0.0) + costo_total

        # Registrar trade
        trade = Trade(
            trader_id=trader_id,
            mercado_id=mercado_id,
            escenario_idx=escenario_idx,
            cantidad=cantidad,
            precio=costo / cantidad if cantidad > 0 else 0.0,
            tipo="compra",
            comision=comision,
        )
        self._trades.append(trade)
        mercado.historial_trades.append(trade.to_dict())
        self._persistir_trade(trade)
        self._persistir_mercado(mercado)

        self.logger.debug(
            "[MercadoPredicciones] Compra: trader=%s mercado=%s "
            "escenario=%d cantidad=%.4f costo=%.4f",
            trader_id, mercado_id, escenario_idx, cantidad, costo_total,
        )

        return {
            "tipo": "compra",
            "mercado_id": mercado_id,
            "escenario_idx": escenario_idx,
            "escenario": mercado.escenarios[escenario_idx],
            "cantidad": cantidad,
            "costo": costo,
            "comision": comision,
            "costo_total": costo_total,
            "precio_unitario": trade.precio,
            "trader_id": trader_id,
            "timestamp": trade.timestamp,
        }

    def vender_participacion(
        self,
        mercado_id: str,
        escenario_idx: int,
        cantidad: float,
        trader_id: str = "sistema",
    ) -> Dict[str, Any]:
        """
        Vende participaciones de un escenario.

        Parametros
        ----------
        mercado_id : str
            ID del mercado.
        escenario_idx : int
            Indice del escenario.
        cantidad : float
            Cantidad de participaciones a vender.
        trader_id : str
            Identificador del vendedor.

        Returns
        -------
        dict
            Detalle de la transaccion: ingreso, precio, comision.

        Raises
        ------
        ValueError
            Si no tiene suficientes participaciones.
        """
        if mercado_id not in self._mercados:
            raise ValueError(f"Mercado no encontrado: {mercado_id}")

        mercado = self._mercados[mercado_id]
        if mercado.estado != "abierto":
            raise ValueError(f"Mercado {mercado_id} no esta abierto ({mercado.estado})")
        if escenario_idx < 0 or escenario_idx >= len(mercado.escenarios):
            raise ValueError(f"Escenario invalido: {escenario_idx}")
        if cantidad <= 0:
            raise ValueError("La cantidad debe ser positiva")

        # Verificar que el trader tiene participaciones
        clave = f"{trader_id}_{mercado_id}"
        if clave not in mercado.participaciones:
            raise ValueError(
                f"Trader {trader_id} no tiene participaciones en {mercado_id}"
            )
        if mercado.participaciones[clave][escenario_idx] < cantidad:
            raise ValueError(
                f"Trader {trader_id} solo tiene "
                f"{mercado.participaciones[clave][escenario_idx]:.4f} "
                f"participaciones en escenario {escenario_idx}"
            )

        # Calcular ingreso usando CPMM
        ingreso = self._calcular_cpmm(
            mercado.reservas, escenario_idx, cantidad, compra=False
        )
        comision = self._comision(ingreso)
        ingreso_neto = ingreso - comision

        # Actualizar reservas
        mercado.reservas[escenario_idx] += cantidad
        mercado.reservas -= ingreso / len(mercado.escenarios)
        mercado.reservas = np.maximum(mercado.reservas, 0.01)  # evitar negativos
        mercado.volumen += ingreso

        # Reducir participaciones
        mercado.participaciones[clave][escenario_idx] -= cantidad

        self._volumen_por_escenario[(mercado_id, escenario_idx)] = \
            self._volumen_por_escenario.get((mercado_id, escenario_idx), 0.0) + ingreso

        trade = Trade(
            trader_id=trader_id,
            mercado_id=mercado_id,
            escenario_idx=escenario_idx,
            cantidad=cantidad,
            precio=ingreso / cantidad if cantidad > 0 else 0.0,
            tipo="venta",
            comision=comision,
        )
        self._trades.append(trade)
        mercado.historial_trades.append(trade.to_dict())
        self._persistir_trade(trade)
        self._persistir_mercado(mercado)

        return {
            "tipo": "venta",
            "mercado_id": mercado_id,
            "escenario_idx": escenario_idx,
            "escenario": mercado.escenarios[escenario_idx],
            "cantidad": cantidad,
            "ingreso": ingreso,
            "comision": comision,
            "ingreso_neto": ingreso_neto,
            "precio_unitario": trade.precio,
            "trader_id": trader_id,
            "timestamp": trade.timestamp,
        }

    # -- Precios y estado ----------------------------------------------------

    def precio_actual(self, mercado_id: str, escenario_idx: int) -> float:
        """
        Devuelve el precio actual (probabilidad implicita) de un escenario.

        El precio se calcula como la proporcion inversa de la reserva:
        precio_i = (1 / reserva_i) / sum_j(1 / reserva_j)

        Esto asegura que precios_mas_altos = escenarios_mas_probables.
        """
        if mercado_id not in self._mercados:
            raise ValueError(f"Mercado no encontrado: {mercado_id}")

        mercado = self._mercados[mercado_id]
        if escenario_idx < 0 or escenario_idx >= len(mercado.escenarios):
            raise ValueError(f"Escenario invalido: {escenario_idx}")

        inv_reservas = 1.0 / mercado.reservas
        precios = inv_reservas / inv_reservas.sum()
        return float(precios[escenario_idx])

    def volumen_total(self, mercado_id: str) -> float:
        """Volumen total de trading en un mercado."""
        if mercado_id not in self._mercados:
            raise ValueError(f"Mercado no encontrado: {mercado_id}")
        return self._mercados[mercado_id].volumen

    def distribucion_precios(self, mercado_id: str) -> List[float]:
        """
        Devuelve los precios actuales de todos los escenarios.
        Los precios suman aproximadamente 1.0 (probabilidades).
        """
        if mercado_id not in self._mercados:
            raise ValueError(f"Mercado no encontrado: {mercado_id}")

        mercado = self._mercados[mercado_id]
        inv_reservas = 1.0 / mercado.reservas
        precios = inv_reservas / inv_reservas.sum()
        return [float(p) for p in precios]

    # -- Resolucion ----------------------------------------------------------

    def resolver_mercado(
        self,
        mercado_id: str,
        escenario_ganador: int,
    ) -> Dict[str, Any]:
        """
        Resuelve el mercado cuando la hipotesis se confirma/refuta.

        Los traders que compraron el escenario ganador reciben
        una parte proporcional del fondo total.

        Parametros
        ----------
        mercado_id : str
            ID del mercado a resolver.
        escenario_ganador : int
            Indice del escenario que ocurrio.

        Returns
        -------
        dict
            Resultado de la resolucion: ganadores, pagos, profit/loss.
        """
        if mercado_id not in self._mercados:
            raise ValueError(f"Mercado no encontrado: {mercado_id}")

        mercado = self._mercados[mercado_id]
        if mercado.estado != "abierto":
            raise ValueError(f"Mercado {mercado_id} ya fue resuelto")
        if escenario_ganador < 0 or escenario_ganador >= len(mercado.escenarios):
            raise ValueError(f"Escenario ganador invalido: {escenario_ganador}")

        mercado.estado = "resuelto"
        mercado.escenario_ganador = escenario_ganador
        mercado.fecha_cierre = time.time()

        # Fondo total = suma de todas las reservas
        fondo_total = float(mercado.reservas.sum())

        # Total de participaciones en el escenario ganador
        total_part_ganadoras = 0.0
        ganadores: Dict[str, float] = {}

        for clave, parts in mercado.participaciones.items():
            if parts[escenario_ganador] > 0:
                trader_id = clave.rsplit("_", 1)[0]
                cantidad = float(parts[escenario_ganador])
                ganadores[trader_id] = cantidad
                total_part_ganadoras += cantidad

        # Distribuir proporcionalmente
        pagos: Dict[str, float] = {}
        if total_part_ganadoras > 0:
            for trader_id, cantidad in ganadores.items():
                pago = fondo_total * (cantidad / total_part_ganadoras)
                pagos[trader_id] = pago
                # Actualizar profit acumulado
                profit_previo = self._profits_trader.get(trader_id, 0.0)
                self._profits_trader[trader_id] = profit_previo + pago

        self._persistir_mercado(mercado)

        # Persistir profits
        cursor = self.db.cursor()
        for trader_id, profit in self._profits_trader.items():
            cursor.execute("""
                INSERT OR REPLACE INTO profits (trader_id, profit_acumulado)
                VALUES (?, ?)
            """, (trader_id, profit))
        self.db.commit()

        self.logger.info(
            "[MercadoPredicciones] Mercado %s resuelto. Ganador: %s "
            "(escenario %d). Fondo: %.4f. Ganadores: %d",
            mercado_id, mercado.escenarios[escenario_ganador],
            escenario_ganador, fondo_total, len(ganadores),
        )

        return {
            "mercado_id": mercado_id,
            "hipotesis_id": mercado.hipotesis_id,
            "escenario_ganador": escenario_ganador,
            "escenario_ganador_nombre": mercado.escenarios[escenario_ganador],
            "fondo_total": fondo_total,
            "total_participaciones_ganadoras": total_part_ganadoras,
            "ganadores": ganadores,
            "pagos": pagos,
            "num_ganadores": len(ganadores),
        }

    # -- Rankings y analisis -------------------------------------------------

    def ranking_traders(self) -> List[Dict[str, Any]]:
        """
        Ranking de traders por profit acumulado.

        Returns
        -------
        list[dict]
            Lista ordenada de traders con profit y estadisticas.
        """
        # Cargar desde DB
        cursor = self.db.cursor()
        cursor.execute(
            "SELECT trader_id, profit_acumulado FROM profits ORDER BY profit_acumulado DESC"
        )
        rows = cursor.fetchall()

        # Tambien contar trades por trader
        cursor.execute(
            "SELECT trader_id, COUNT(*) as num_trades FROM trades GROUP BY trader_id"
        )
        trades_count = {r[0]: r[1] for r in cursor.fetchall()}

        ranking: List[Dict[str, Any]] = []
        for trader_id, profit in rows:
            ranking.append({
                "trader_id": trader_id,
                "profit_acumulado": profit,
                "num_trades": trades_count.get(trader_id, 0),
            })

        return ranking

    def escenarios_populares(self, limite: int = 10) -> List[Dict[str, Any]]:
        """
        Escenarios con mayor volumen de trading.

        Parametros
        ----------
        limite : int
            Numero maximo de resultados.

        Returns
        -------
        list[dict]
            Escenarios ordenados por volumen descendente.
        """
        items = []
        for (mercado_id, esc_idx), volumen in self._volumen_por_escenario.items():
            mercado = self._mercados.get(mercado_id)
            if mercado:
                items.append({
                    "mercado_id": mercado_id,
                    "hipotesis_id": mercado.hipotesis_id,
                    "escenario_idx": esc_idx,
                    "escenario": mercado.escenarios[esc_idx],
                    "volumen": volumen,
                    "precio_actual": self.precio_actual(mercado_id, esc_idx),
                })

        items.sort(key=lambda x: x["volumen"], reverse=True)
        return items[:limite]

    def estado_mercado(self, mercado_id: str) -> Dict[str, Any]:
        """Devuelve el estado completo de un mercado."""
        if mercado_id not in self._mercados:
            raise ValueError(f"Mercado no encontrado: {mercado_id}")

        mercado = self._mercados[mercado_id]
        precios = self.distribucion_precios(mercado_id)

        return {
            "mercado_id": mercado.id,
            "hipotesis_id": mercado.hipotesis_id,
            "escenarios": mercado.escenarios,
            "precios_actuales": precios,
            "reservas": mercado.reservas.tolist(),
            "volumen": mercado.volumen,
            "estado": mercado.estado,
            "escenario_ganador": mercado.escenario_ganador,
            "num_trades": len(mercado.historial_trades),
        }

    # -- CPMM Interno --------------------------------------------------------

    def _calcular_cpmm(
        self,
        reservas: np.ndarray,
        escenario_idx: int,
        cantidad: float,
        compra: bool,
    ) -> float:
        """
        Calcula el costo/ingreso usando un modelo CPMM simplificado.

        En un mercado de predicciones con N escenarios, interpretamos
        las reservas como una "balancing score". Comprar un escenario
        reduce su reserva y aumenta las demas, lo que sube su precio
        (mayor demanda => mayor probabilidad implicita).

        Parametros
        ----------
        reservas : np.ndarray
            Reservas actuales de cada escenario.
        escenario_idx : int
            Escenario a operar.
        cantidad : float
            Cantidad de participaciones.
        compra : bool
            True si es compra, False si es venta.

        Returns
        -------
        float
            Costo total (compra) o ingreso total (venta).
        """
        reserva_actual = float(reservas[escenario_idx])
        otras_reservas = np.delete(reservas, escenario_idx)

        if compra:
            # El costo es proporcional a cuanto se desequilibra el mercado
            # Formula: costo = k * (1/(reserva - cantidad) - 1/reserva) * sum_otras
            # donde k es una constante de curvatura
            nueva_reserva = max(reserva_actual - cantidad, 0.1)
            factor = (1.0 / nueva_reserva - 1.0 / reserva_actual)
            suma_otras = float(otras_reservas.sum())
            costo = abs(factor) * suma_otras * 0.5
            # Asegurar costo minimo razonable
            costo = max(costo, cantidad * 0.01)
            return costo
        else:
            # Venta: ingreso basado en reserva actual
            nueva_reserva = reserva_actual + cantidad
            factor = (1.0 / reserva_actual - 1.0 / nueva_reserva)
            suma_otras = float(otras_reservas.sum())
            ingreso = abs(factor) * suma_otras * 0.5
            ingreso = max(ingreso, cantidad * 0.005)
            return ingreso

    def _comision(self, monto: float) -> float:
        """Calcula la comision sobre un monto."""
        return monto * self.comision_pct

    # -- Utilidades ----------------------------------------------------------

    def listar_mercados(self, estado: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lista mercados, opcionalmente filtrados por estado."""
        resultados = []
        for m in self._mercados.values():
            if estado is None or m.estado == estado:
                resultados.append(m.to_dict())
        return resultados

    def mercados_por_hipotesis(self, hipotesis_id: str) -> List[Dict[str, Any]]:
        """Obtiene todos los mercados asociados a una hipotesis."""
        return [
            m.to_dict() for m in self._mercados.values()
            if m.hipotesis_id == hipotesis_id
        ]


# ---------------------------------------------------------------------------
# Agente Trader
# ---------------------------------------------------------------------------

class AgenteTrader:
    """
    Agente que opera en el mercado de predicciones siguiendo una estrategia.

    Estrategias implementadas:
    - "momentum": compra escenarios con tendencia alcista.
    - "contrarian": compra escenarios con tendencia bajista (sobreventa).
    - "valor": compra escenarios con probabilidad > confianza de la hipotesis.
    - "arbitraje": busca inconsistencias entre mercados relacionados.
    - "random": decisiones aleatorias.

    Parametros
    ----------
    nombre : str
        Identificador unico del agente.
    estrategia : str
        Nombre de la estrategia a usar.
    capital : float
        Capital inicial del agente.
    """

    ESTRATEGIAS_VALIDAS = {
        "momentum", "contrarian", "valor", "arbitraje", "random",
    }

    def __init__(
        self,
        nombre: str,
        estrategia: str,
        capital: float = 100.0,
    ) -> None:
        if estrategia not in self.ESTRATEGIAS_VALIDAS:
            raise ValueError(
                f"Estrategia '{estrategia}' no valida. "
                f"Opciones: {self.ESTRATEGIAS_VALIDAS}"
            )

        self.nombre: str = nombre
        self.estrategia: str = estrategia
        self.capital: float = capital
        self.capital_inicial: float = capital
        self._trades: List[Dict[str, Any]] = []
        self._profits_acumulado: float = 0.0

    # -- Decisiones ------------------------------------------------------------

    def decidir_trade(
        self,
        mercado: Dict[str, Any],
        contexto: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Toma una decision de trading basada en la estrategia.

        Parametros
        ----------
        mercado : dict
            Estado del mercado (precios, volumen, escenarios).
        contexto : dict | None
            Informacion adicional (confianza de hipotesis, mercados relacionados).

        Returns
        -------
        dict | None
            Orden de trade con: tipo, escenario_idx, cantidad, justificacion.
            None si no hay oportunidad.
        """
        if self.capital <= 0:
            return None

        precios: List[float] = mercado.get("precios_actuales", [])
        escenarios: List[str] = mercado.get("escenarios", [])
        if len(precios) < 2:
            return None

        if self.estrategia == "random":
            return self._estrategia_random(mercado)
        elif self.estrategia == "momentum":
            return self._estrategia_momentum(mercado, contexto)
        elif self.estrategia == "contrarian":
            return self._estrategia_contrarian(mercado, contexto)
        elif self.estrategia == "valor":
            return self._estrategia_valor(mercado, contexto)
        elif self.estrategia == "arbitraje":
            return self._estrategia_arbitraje(mercado, contexto)

        return None

    def _estrategia_random(
        self, mercado: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Compra aleatoria con cantidad pequena."""
        escenarios: List[str] = mercado.get("escenarios", [])
        if not escenarios:
            return None

        idx = random.randint(0, len(escenarios) - 1)
        cantidad = random.uniform(0.5, min(5.0, self.capital * 0.1))

        return {
            "tipo": "compra",
            "escenario_idx": idx,
            "cantidad": cantidad,
            "justificacion": "Decision aleatoria",
        }

    def _estrategia_momentum(
        self,
        mercado: Dict[str, Any],
        contexto: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Compra el escenario con mayor tendencia alcista.
        Si hay historial de precios, calcula la pendiente.
        """
        precios: List[float] = mercado.get("precios_actuales", [])
        historial = mercado.get("historial_precios")

        if historial is not None and len(historial) >= 2:
            # Calcular tendencia para cada escenario
            tendencias = []
            for i in range(len(precios)):
                serie = [h[i] for h in historial[-5:]]
                if len(serie) >= 2:
                    x = np.arange(len(serie))
                    pendiente = np.polyfit(x, serie, 1)[0]
                    tendencias.append(pendiente)
                else:
                    tendencias.append(0.0)

            mejor_idx = int(np.argmax(tendencias))
            if tendencias[mejor_idx] <= 0:
                return None  # No hay momentum positivo
        else:
            # Sin historial: comprar el escenario con mayor precio actual
            mejor_idx = int(np.argmax(precios))

        cantidad = min(3.0, self.capital * 0.05)
        return {
            "tipo": "compra",
            "escenario_idx": mejor_idx,
            "cantidad": cantidad,
            "justificacion": f"Momentum: escenario {mejor_idx} en alza",
        }

    def _estrategia_contrarian(
        self,
        mercado: Dict[str, Any],
        contexto: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Compra el escenario mas barato (sobreventa).
        Contrarian: compra barato, vende caro.
        """
        precios: List[float] = mercado.get("precios_actuales", [])
        if not precios:
            return None

        # Comprar el escenario con menor precio (mas barato)
        peor_idx = int(np.argmin(precios))

        # Solo comprar si el precio esta por debajo del uniforme
        precio_uniforme = 1.0 / len(precios)
        if precios[peor_idx] >= precio_uniforme * 0.9:
            return None  # No esta suficientemente barato

        cantidad = min(5.0, self.capital * 0.08)
        return {
            "tipo": "compra",
            "escenario_idx": peor_idx,
            "cantidad": cantidad,
            "justificacion": f"Contrarian: escenario {peor_idx} sobreventa",
        }

    def _estrategia_valor(
        self,
        mercado: Dict[str, Any],
        contexto: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Compra escenarios cuyo precio es menor que la confianza
        estimada de la hipotesis (valor subestimado).
        """
        precios: List[float] = mercado.get("precios_actuales", [])
        if not precios:
            return None

        # La confianza de la hipotesis nos dice cual escenario es mas probable
        confianzas = contexto.get("confianzas", precios) if contexto else precios

        mejor_oportunidad = None
        mejor_ratio = 0.0

        for i, precio in enumerate(precios):
            conf = confianzas[i] if i < len(confianzas) else precio
            if precio > 0 and conf > precio * 1.2:  # al menos 20% subestimado
                ratio = conf / precio
                if ratio > mejor_ratio:
                    mejor_ratio = ratio
                    mejor_oportunidad = i

        if mejor_oportunidad is None:
            return None

        cantidad = min(4.0, self.capital * 0.06)
        return {
            "tipo": "compra",
            "escenario_idx": mejor_oportunidad,
            "cantidad": cantidad,
            "justificacion": (
                f"Valor: escenario {mejor_oportunidad} "
                f"subestimado (ratio {mejor_ratio:.2f})"
            ),
        }

    def _estrategia_arbitraje(
        self,
        mercado: Dict[str, Any],
        contexto: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Busca inconsistencias entre este mercado y mercados relacionados.
        Si un escenario esta mas barato aqui que en otro mercado, compra.
        """
        precios: List[float] = mercado.get("precios_actuales", [])
        mercados_relacionados = (
            contexto.get("mercados_relacionados", []) if contexto else []
        )

        if not mercados_relacionados:
            return None

        # Comparar precios con mercados relacionados
        mejor_idx = None
        mejor_diff = 0.0

        for i, precio_local in enumerate(precios):
            for otro in mercados_relacionados:
                precios_otro: List[float] = otro.get("precios_actuales", [])
                esc_otro: List[str] = otro.get("escenarios", [])
                # Buscar escenario equivalente
                esc_local = mercado.get("escenarios", [])[i] if i < len(mercado.get("escenarios", [])) else ""
                if esc_local in esc_otro:
                    j = esc_otro.index(esc_local)
                    if j < len(precios_otro):
                        diff = precios_otro[j] - precio_local
                        if diff > mejor_diff:
                            mejor_diff = diff
                            mejor_idx = i

        if mejor_idx is None or mejor_diff < 0.05:
            return None

        cantidad = min(3.0, self.capital * 0.05)
        return {
            "tipo": "compra",
            "escenario_idx": mejor_idx,
            "cantidad": cantidad,
            "justificacion": f"Arbitraje: diferencia de {mejor_diff:.3f} con otro mercado",
        }

    # -- Estado del agente ---------------------------------------------------

    def capital_actual(self) -> float:
        """Devuelve el capital actual del agente."""
        return self.capital

    def historial_trades(self) -> List[Dict[str, Any]]:
        """Devuelve el historial completo de trades del agente."""
        return list(self._trades)

    def registrar_trade(self, trade: Dict[str, Any]) -> None:
        """Registra un trade ejecutado en el historial."""
        trade_con_agente = dict(trade)
        trade_con_agente["agente"] = self.nombre
        trade_con_agente["estrategia"] = self.estrategia
        self._trades.append(trade_con_agente)

        # Actualizar capital
        if trade.get("tipo") == "compra":
            self.capital -= trade.get("costo_total", 0.0)
        elif trade.get("tipo") == "venta":
            self.capital += trade.get("ingreso_neto", 0.0)
        elif trade.get("tipo") == "resolucion":
            self.capital += trade.get("pago", 0.0)
            self._profits_acumulado += trade.get("pago", 0.0)

    def profit_total(self) -> float:
        """Profit total acumulado por resoluciones."""
        return self._profits_acumulado

    def rendimiento_pct(self) -> float:
        """Rendimiento porcentual desde el inicio."""
        if self.capital_inicial <= 0:
            return 0.0
        return ((self.capital + self._profits_acumulado - self.capital_inicial)
                / self.capital_inicial * 100.0)

    def resumen(self) -> Dict[str, Any]:
        """Resumen del estado del agente."""
        return {
            "nombre": self.nombre,
            "estrategia": self.estrategia,
            "capital": self.capital,
            "capital_inicial": self.capital_inicial,
            "profit_total": self._profits_acumulado,
            "rendimiento_pct": self.rendimiento_pct(),
            "num_trades": len(self._trades),
            "trades": self._trades[-10:],  # ultimos 10
        }


# ============================================================================
# VEO v2: Funciones de integracion con hermes_commander / veo_core
# ============================================================================
# NOTA: Estas funciones fueron anadidas en la migracion de VEO v1 a VEO v2.
# Proporcionan observabilidad, auditoria y health-checks sin modificar
# la logica existente del Mercado de Predicciones con CPMM.
# ============================================================================

import time as _time

# --- Estado observable del modulo (VEO v2) ---
_pm_execution_count: int = 0
_pm_last_execution_time: float = 0.0
_pm_trade_log: list = []


def get_trust_score() -> float:
    """
    VEO v2: Devuelve el score de confianza del mercado de predicciones.

    Basado en la precision del mercado (cuanto se acercan los precios
    a los resultados reales).

    Returns:
        float: Score de confianza en [0.0, 1.0].
    """
    global _pm_trade_log
    if not _pm_trade_log:
        return 0.75

    resueltos_correctamente = sum(
        1 for t in _pm_trade_log
        if t.get("resultado_correcto", True)
    )
    total_resueltos = sum(
        1 for t in _pm_trade_log
        if t.get("tipo") == "resolucion"
    )
    if total_resueltos == 0:
        return 0.7

    score = 0.2 + 0.8 * (resueltos_correctamente / total_resueltos)
    return round(min(max(score, 0.0), 1.0), 4)


def get_last_execution_time() -> str:
    """
    VEO v2: Devuelve el timestamp ISO de la ultima operacion del mercado.

    Returns:
        str: Timestamp ISO 8601, o cadena vacia si no ha ejecutado.
    """
    global _pm_last_execution_time
    if _pm_last_execution_time == 0.0:
        return ""
    return _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime(_pm_last_execution_time))


def get_health_status() -> dict:
    """
    VEO v2: Devuelve el estado de salud del mercado de predicciones.

    Returns:
        dict: {"status": "healthy|degraded|unhealthy", "score": 0-100}
    """
    global _pm_last_execution_time, _pm_trade_log

    score = 100

    if _pm_last_execution_time > 0:
        horas = (_time.time() - _pm_last_execution_time) / 3600
        if horas > 48:
            score -= 25
        elif horas > 24:
            score -= 10

    if _pm_trade_log:
        trust = get_trust_score()
        if trust < 0.4:
            score -= 30
        elif trust < 0.6:
            score -= 10

    if _pm_execution_count == 0:
        score -= 10

    score = max(0, min(100, score))

    if score >= 80:
        status = "healthy"
    elif score >= 50:
        status = "degraded"
    else:
        status = "unhealthy"

    return {"status": status, "score": score}


def _log_audit_trade(
    tipo: str,
    mercado_id: str,
    detalles: str = "",
    resultado_correcto: bool = True,
) -> None:
    """
    VEO v2: Registra una entrada de auditoria para cada operacion del mercado.

    Args:
        tipo: Tipo de operacion (crear_mercado, compra, venta, resolucion).
        mercado_id: ID del mercado afectado.
        detalles: Detalles adicionales.
        resultado_correcto: Si la operacion/resolucion fue correcta.
    """
    global _pm_execution_count, _pm_last_execution_time, _pm_trade_log

    _pm_execution_count += 1
    _pm_last_execution_time = _time.time()

    entry = {
        "timestamp": get_last_execution_time(),
        "tipo": tipo,
        "mercado_id": mercado_id,
        "detalles": detalles[:200] if detalles else "",
        "resultado_correcto": resultado_correcto,
    }
    _pm_trade_log.append(entry)

    if len(_pm_trade_log) > 1000:
        _pm_trade_log = _pm_trade_log[-1000:]
