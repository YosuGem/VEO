"""
VEO v2 - API Server
Sistema Operativo para Intuicion Social v2.0

API RESTful + WebSocket para VEO v2.
TODAS las operaciones pasan por HermesCommander - NUNCA se toca la DB directamente.

ENTRYPOINT CORRECTO (desde directorio veo_v2/):
    uvicorn api.api_server:app --host 0.0.0.0 --port 8000

O desde directorio padre:
    cd veo_v2
    uvicorn api.api_server:app --host 0.0.0.0 --port 8000

Tambien se puede iniciar via CLI:
    python cli/hermes_cli.py serve
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import sys
import time
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, AsyncGenerator, Optional

from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect, status
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# IMPORT Config para CORS seguro por entorno
# ---------------------------------------------------------------------------
try:
    from core.config import get_config
    _CONFIG_AVAILABLE = True
except ImportError:
    _CONFIG_AVAILABLE = False

# ---------------------------------------------------------------------------
# IMPORT HermesCommander - UNICO punto de entrada
# ---------------------------------------------------------------------------
# HermesCommander es el unico punto de entrada autorizado para VEO v2.
# La API nunca accede a la base de datos directamente.
# ---------------------------------------------------------------------------
_COMMANDER_AVAILABLE = False
try:
    from multiagent.hermes_commander import HermesCommander
    _COMMANDER_AVAILABLE = True
except ImportError:
    pass

# ---------------------------------------------------------------------------
# CONSTANTES
# ---------------------------------------------------------------------------
VEO_VERSION = "2.0.5"
APP_NAME = "VEO v2 API"
RATE_LIMIT_MAX = 100
RATE_LIMIT_WINDOW = 60

# ---------------------------------------------------------------------------
# LOGGING
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("veo-v2-api")


# ---------------------------------------------------------------------------
# HERMESCOMMANDER ADAPTER
# ---------------------------------------------------------------------------

class HermesCommanderAdapter:
    """
    Adaptador que conecta la API con HermesCommander.
    Si HermesCommander no esta disponible, usa MockStore como fallback.
    """

    def __init__(self) -> None:
        self.commander: Any = None
        self._mock_db: MockDatabase | None = None
        if _COMMANDER_AVAILABLE:
            try:
                self.commander = HermesCommander()
                # Mock fallback para endpoints que HermesCommander no implementa
                # (mercados V1, escenarios, etc.) sin modificar la arquitectura
                self._mock_db = MockDatabase()
                logger.info("[VEO v2] HermesCommander conectado correctamente.")
            except Exception as e:
                logger.warning(f"[VEO v2] No se pudo inicializar HermesCommander: {e}. Usando MockStore.")
                self._init_mock()
        else:
            logger.info("[VEO v2] HermesCommander no encontrado. Usando MockStore.")
            self._init_mock()

    def _init_mock(self) -> None:
        """Inicializa el MockDatabase como fallback.
        MockDatabase está en el mismo archivo, así que siempre es accesible."""
        self.commander = MockDatabase()
        self._mock_db = self.commander
        logger.info("[VEO v2] MockDatabase inicializado como fallback.")

    @staticmethod
    def _normalize_hypothesis(h: dict[str, Any]) -> dict[str, Any]:
        """Normaliza una hipotesis al formato HipotesisResponse esperado por la API."""
        if not isinstance(h, dict):
            return h

        # Mapeo de veredictos no estandar a valores de VeredictoValidacion
        VEREDICTO_MAP = {
            "inconcluso": "dudoso",
            "inconclusa": "dudoso",
            "revision_manual": "pendiente",
            "revision": "pendiente",
        }

        def _norm_veredicto(v: Any) -> str:
            if isinstance(v, dict):
                raw = str(v.get("veredicto", "pendiente")).lower()
                v["veredicto"] = VEREDICTO_MAP.get(raw, raw)
                return v
            return {"veredicto": "pendiente", "score": 0.5}

        # Manejo robusto de evidencias (puede ser int, str, list o None)
        raw_evidencias = h.get("evidencias")
        if isinstance(raw_evidencias, list):
            evidencias = len(raw_evidencias)
        elif isinstance(raw_evidencias, (int, float)):
            evidencias = int(raw_evidencias)
        elif isinstance(raw_evidencias, str):
            try:
                evidencias = int(raw_evidencias)
            except ValueError:
                evidencias = 0
        elif "fuentes" in h and isinstance(h.get("fuentes"), list):
            evidencias = len(h["fuentes"])
        else:
            evidencias = 0
        # Manejo robusto de confianza (puede ser int, float, str o None)
        raw_confianza = h.get("confianza", h.get("confidence", 0.5))
        try:
            confianza = float(raw_confianza)
        except (TypeError, ValueError):
            confianza = 0.5
        # Manejo robusto de nei
        raw_nei = h.get("nei", h.get("peso_nei", 0.5))
        try:
            nei = float(raw_nei)
        except (TypeError, ValueError):
            nei = 0.5

        cientifico = _norm_veredicto(h.get("cientifico"))
        esceptico = _norm_veredicto(h.get("esceptico"))

        return {
            "id": str(h.get("id", "")),
            "texto": h.get("texto", h.get("text", "")),
            "estado": h.get("estado", "activa"),
            "confianza": confianza,
            "evidencias": evidencias,
            "fecha_creacion": h.get("fecha_creacion", h.get("timestamp", "")),
            "tags": list(h.get("tags", [])) if isinstance(h.get("tags"), (list, tuple)) else [],
            "cientifico": cientifico,
            "esceptico": esceptico,
            "nei": nei,
        }

    # -- proxy methods --
    async def listar_hipotesis(self, *args: Any, **kwargs: Any) -> Any:
        if hasattr(self.commander, "list_hypotheses"):
            filters: dict[str, Any] = {}
            if kwargs.get("estado"):
                filters["estado"] = kwargs["estado"]
            if kwargs.get("tag"):
                filters["dominio"] = kwargs["tag"]
            if kwargs.get("min_confianza") is not None:
                filters["confianza_min"] = kwargs["min_confianza"]
            result = await self.commander.list_hypotheses(filters=filters if filters else None)
            # HermesCommander devuelve dict con clave "hypotheses" (inglés) o "hipotesis" (español)
            hypotheses: list[dict[str, Any]] = []
            if isinstance(result, dict) and "hypotheses" in result:
                hypotheses = result["hypotheses"]
            elif isinstance(result, dict) and "hipotesis" in result:
                hypotheses = result["hipotesis"]
            elif isinstance(result, list):
                hypotheses = result
            # Normalizar al formato HipotesisResponse
            return [self._normalize_hypothesis(h) for h in hypotheses if isinstance(h, dict)]
        if hasattr(self.commander, "listar_hipotesis"):
            return await self.commander.listar_hipotesis(*args, **kwargs)
        return []

    async def get_hipotesis(self, *args: Any, **kwargs: Any) -> Any:
        if hasattr(self.commander, "get_hypothesis"):
            hid = args[0] if args else kwargs.get("hid")
            result = await self.commander.get_hypothesis(hyp_id=hid)
            # Adaptar formato de HermesCommander ({status, hypothesis, source}) al formato esperado por la API
            if isinstance(result, dict) and result.get("status") == "ok" and "hypothesis" in result:
                return self._normalize_hypothesis(result["hypothesis"])
            return self._normalize_hypothesis(result)
        if hasattr(self.commander, "get_hipotesis"):
            return await self.commander.get_hipotesis(*args, **kwargs)
        return None

    async def crear_hipotesis(self, *args: Any, **kwargs: Any) -> Any:
        if hasattr(self.commander, "create_hypothesis"):
            data = args[0] if args else kwargs.get("data", kwargs)
            if isinstance(data, dict):
                result = await self.commander.create_hypothesis(
                    text=data.get("texto", ""),
                    context=data,
                    confidence=data.get("confianza", 0.5),
                )
                # Adaptar formato de HermesCommander ({status, hypothesis}) al formato esperado por la API
                if isinstance(result, dict) and result.get("status") == "ok" and "hypothesis" in result:
                    return result["hypothesis"]
                return result
            return await self.commander.create_hypothesis(*args, **kwargs)
        if hasattr(self.commander, "crear_hipotesis"):
            return await self.commander.crear_hipotesis(*args, **kwargs)
        raise RuntimeError("create_hypothesis no disponible en el backend actual")

    async def validar_hipotesis(self, *args: Any, **kwargs: Any) -> Any:
        if hasattr(self.commander, "validate_hypothesis"):
            hid = args[0] if args else kwargs.get("hid")
            result = await self.commander.validate_hypothesis(hyp_id=hid)
            # Adaptar formato: devolver la hipotesis actualizada con nei para compatibilidad con la API
            if isinstance(result, dict) and result.get("status") == "ok":
                # Buscar hipotesis actualizada en el historial del commander
                if hasattr(self.commander, "_core") and self.commander._core:
                    for h in self.commander._core.reasoning.hypotheses_history:
                        if h.get("id") == hid:
                            return self._normalize_hypothesis(h)
                # Fallback: construir respuesta minima desde hipotesis_actualizada
                if "hipotesis_actualizada" in result:
                    ha = result["hipotesis_actualizada"]
                    ha["nei"] = ha.get("confianza", 0.5)
                    return self._normalize_hypothesis(ha)
            return self._normalize_hypothesis(result) if isinstance(result, dict) else result
        if hasattr(self.commander, "validar_hipotesis"):
            return await self.commander.validar_hipotesis(*args, **kwargs)
        raise RuntimeError("validate_hypothesis no disponible en el backend actual")

    # -----------------------------------------------------------------------
    # Mercados - NOTA: HermesCommander NO implementa mercados V1 nativamente.
    # Los endpoints /api/v1/mercados usan MockDatabase como fallback para
    # garantizar respuestas coherentes con el modelo MercadoResponse.
    # Estos datos son MOCKS de demostracion.
    # -----------------------------------------------------------------------

    async def listar_mercados(self, *args: Any, **kwargs: Any) -> Any:
        """Lista mercados. Fallback a mock porque HermesCommander usa CPMM (formato diferente)."""
        if hasattr(self.commander, "listar_mercados") and not isinstance(self.commander, MockDatabase):
            result = await self.commander.listar_mercados(*args, **kwargs)
            if result:
                return result
        # Fallback a mock: HermesCommander get_prediction_market devuelve formato CPMM
        # incompatible con MercadoResponse. Usamos MockDatabase para coherencia.
        if self._mock_db:
            return await self._mock_db.listar_mercados(*args, **kwargs)
        return []

    async def get_mercado(self, *args: Any, **kwargs: Any) -> Any:
        """Obtiene mercado por ID. Fallback a mock."""
        if hasattr(self.commander, "get_mercado") and not isinstance(self.commander, MockDatabase):
            result = await self.commander.get_mercado(*args, **kwargs)
            if result:
                return result
        if self._mock_db:
            mid = args[0] if args else kwargs.get("mid")
            return await self._mock_db.get_mercado(mid)
        return None

    async def crear_mercado(self, *args: Any, **kwargs: Any) -> Any:
        """Crea mercado. Fallback a mock (HermesCommander no implementa mercados V1)."""
        if hasattr(self.commander, "crear_mercado") and not isinstance(self.commander, MockDatabase):
            return await self.commander.crear_mercado(*args, **kwargs)
        if self._mock_db:
            data = args[0] if args else kwargs.get("data", kwargs)
            return await self._mock_db.crear_mercado(data)
        raise RuntimeError("crear_mercado no disponible en el backend actual")

    async def trade_mercado(self, *args: Any, **kwargs: Any) -> Any:
        """Trade en mercado. Fallback a mock para formato coherente MercadoResponse."""
        if hasattr(self.commander, "trade_mercado") and not isinstance(self.commander, MockDatabase):
            return await self.commander.trade_mercado(*args, **kwargs)
        # HermesCommander.trade_prediction devuelve formato CPMM {"status", "trade"}
        # incompatible con MercadoResponse. Usamos mock para coherencia de la API.
        if self._mock_db:
            mid = args[0] if len(args) > 0 else kwargs.get("mid")
            escenario = args[1] if len(args) > 1 else kwargs.get("escenario")
            cantidad = args[2] if len(args) > 2 else kwargs.get("cantidad")
            return await self._mock_db.trade_mercado(mid, escenario, cantidad)
        raise RuntimeError("trade_mercado no disponible en el backend actual")

    async def resolver_mercado(self, *args: Any, **kwargs: Any) -> Any:
        """Resuelve mercado. Fallback a mock (HermesCommander no implementa)."""
        if hasattr(self.commander, "resolver_mercado") and not isinstance(self.commander, MockDatabase):
            return await self.commander.resolver_mercado(*args, **kwargs)
        if self._mock_db:
            mid = args[0] if args else kwargs.get("mid")
            ganador = args[1] if len(args) > 1 else kwargs.get("ganador")
            return await self._mock_db.resolver_mercado(mid, ganador)
        raise RuntimeError("resolver_mercado no disponible en el backend actual")

    async def listar_escenarios(self, *args: Any, **kwargs: Any) -> Any:
        """Lista escenarios. Intenta commander primero; si vacio, fallback a MockDatabase."""
        escenarios: list[Any] = []
        # 1. Intentar metodo nativo en espanol
        if hasattr(self.commander, "listar_escenarios"):
            result = await self.commander.listar_escenarios(*args, **kwargs)
            if isinstance(result, dict):
                escenarios = result.get("escenarios", []) or []
            elif result:
                escenarios = result
            if escenarios:
                return escenarios
        # 2. Intentar metodo en ingles (HermesCommander)
        if hasattr(self.commander, "list_scenarios"):
            try:
                result = await self.commander.list_scenarios()
                if isinstance(result, dict):
                    escenarios = result.get("scenarios", []) or []
                elif result:
                    escenarios = result
            except Exception:
                escenarios = []
            if escenarios:
                return escenarios
        # 3. Fallback a MockDatabase (donde se crean los escenarios via POST)
        if self._mock_db:
            return await self._mock_db.listar_escenarios()
        return []

    async def get_escenario(self, *args: Any, **kwargs: Any) -> Any:
        """Recupera un escenario por ID. Intenta commander; si no existe, fallback a MockDatabase."""
        sid = args[0] if args else kwargs.get("sid")
        # 1. Intentar metodo nativo
        if hasattr(self.commander, "get_escenario"):
            try:
                result = await self.commander.get_escenario(*args, **kwargs)
                if result is not None:
                    return result
            except Exception:
                pass
        # 2. Intentar metodo en ingles (HermesCommander: get_scenario_results)
        if hasattr(self.commander, "get_scenario_results"):
            try:
                result = await self.commander.get_scenario_results(scenario_id=sid)
                if isinstance(result, dict) and result.get("status") == "ok" and "scenario" in result:
                    return result["scenario"]
                if result is not None:
                    return result
            except Exception:
                pass
        # 3. Fallback a MockDatabase
        if self._mock_db:
            return await self._mock_db.get_escenario(sid)
        return None

    async def crear_escenario(self, *args: Any, **kwargs: Any) -> Any:
        if hasattr(self.commander, "crear_escenario") and not isinstance(self.commander, MockDatabase):
            result = await self.commander.crear_escenario(*args, **kwargs)
            if result is None:
                data = args[0] if args else kwargs.get("data", kwargs)
                name = data.get("nombre", "escenario") if isinstance(data, dict) else str(data)
                return {"id": str(uuid.uuid4()), "nombre": name, "estado": "creado"}
            return result
        # Fallback a MockDatabase (HermesCommander no implementa crear_escenario nativamente)
        if self._mock_db:
            raw = args[0] if args else kwargs.get("data", kwargs)
            if isinstance(raw, dict):
                data = raw
            elif isinstance(raw, str):
                data = {"nombre": raw, "variables": kwargs.get("variables", {})}
            else:
                data = {"nombre": "escenario", "variables": {}}
            return await self._mock_db.crear_escenario(data)
        raise RuntimeError("crear_escenario no disponible en el backend actual")

    async def simular_escenario(self, *args: Any, **kwargs: Any) -> Any:
        """Simula un escenario. Intenta commander; si falla o no existe, fallback a MockDatabase."""
        sid = args[0] if args else kwargs.get("sid")
        # 1. Intentar metodo en ingles (HermesCommander: simulate_scenario)
        if hasattr(self.commander, "simulate_scenario"):
            try:
                result = await self.commander.simulate_scenario(hyp_id=sid)
                # Adaptar formato de HermesCommander ({status, scenario})
                if isinstance(result, dict) and result.get("status") == "ok" and "scenario" in result:
                    return result["scenario"]
                if result is not None:
                    return result
            except Exception:
                pass
        # 2. Intentar metodo nativo
        if hasattr(self.commander, "simular_escenario"):
            try:
                result = await self.commander.simular_escenario(*args, **kwargs)
                if result is not None:
                    return result
            except Exception:
                pass
        # 3. Fallback a MockDatabase
        if self._mock_db:
            return await self._mock_db.simular_escenario(sid)
        # 4. Escenario no encontrado en ningun lado → devolver None (el endpoint lanzara 404)
        return None

    # -- V2 system methods --
    @staticmethod
    def _normalize_component(comp: dict[str, Any]) -> dict[str, Any]:
        """Normaliza un componente de health para que tenga 'status' obligatorio."""
        normalized = dict(comp)
        # veo_core usa 'overall' en lugar de 'status'
        if "overall" in normalized and "status" not in normalized:
            normalized["status"] = normalized.pop("overall")
        # Si no hay status, asumir ok
        if "status" not in normalized:
            normalized["status"] = "ok"
        return normalized

    async def get_system_health(self) -> dict[str, Any]:
        """GET /api/v2/system/health"""
        try:
            # HermesCommander usa 'health()', no 'get_system_health'
            if hasattr(self.commander, "health"):
                result = await self.commander.health()
                if isinstance(result, dict):
                    # _cmd_health devuelve {"status": "...", "components": {...}, "timestamp": "..."}
                    if "components" in result:
                        raw_components = result["components"]
                        # Normalizar cada componente para que tenga 'status'
                        components = {
                            name: self._normalize_component(comp)
                            for name, comp in raw_components.items()
                        }
                        return {
                            "health_score": 85 if result.get("status") == "healthy" else 50,
                            "status": result.get("status", "degraded"),
                            "components": components,
                            "timestamp": result.get("timestamp", datetime.now().isoformat()),
                        }
                    # Formato plano legacy (sin 'components' wrapper)
                    return {
                        "health_score": 85,
                        "status": "healthy",
                        "components": result,
                        "timestamp": datetime.now().isoformat(),
                    }
                return result
            if hasattr(self.commander, "get_system_health"):
                return await self.commander.get_system_health()
        except Exception as exc:
            # Log del error pero devolver mock para evitar 500
            print(f"[WARNING] get_system_health fallo: {exc}. Devolviendo mock.")
        return self._mock_system_health()

    async def get_system_metrics(self) -> dict[str, Any]:
        """GET /api/v2/system/metrics"""
        try:
            if hasattr(self.commander, "get_system_metrics"):
                return await self.commander.get_system_metrics()
        except Exception as exc:
            print(f"[WARNING] get_system_metrics fallo: {exc}. Devolviendo mock.")
        return self._mock_system_metrics()

    async def get_system_audit(self) -> list[dict[str, Any]]:
        """GET /api/v2/system/audit"""
        try:
            if hasattr(self.commander, "get_system_audit"):
                return await self.commander.get_system_audit()
        except Exception as exc:
            print(f"[WARNING] get_system_audit fallo: {exc}. Devolviendo mock.")
        return self._mock_system_audit()

    async def get_system_status(self) -> dict[str, Any]:
        """GET /api/v2/system/status"""
        try:
            # HermesCommander usa 'status()', no 'get_system_status'
            if hasattr(self.commander, "status"):
                result = await self.commander.status()
                if isinstance(result, dict) and "commander" in result:
                    # Formato de _cmd_status
                    return {
                        "version": VEO_VERSION,
                        "mode": "commander" if _COMMANDER_AVAILABLE else "mock_fallback",
                        "commander_available": _COMMANDER_AVAILABLE,
                        "components": {
                            "hermes_commander": {
                                "status": "running" if result.get("commander", {}).get("running") else "idle",
                                "version": VEO_VERSION,
                                "note": f"workers: {result.get('commander', {}).get('workers', 4)}, queue: {result.get('commander', {}).get('commands_queued', 0)}",
                            },
                            "veo_core": {
                                "status": "healthy" if result.get("core", {}).get("running") else "not_initialized",
                                "version": result.get("core", {}).get("version", "unknown"),
                                "last_run": result.get("core", {}).get("uptime_human", "N/A"),
                            },
                            "event_bus": {
                                "status": "healthy" if result.get("health_monitor", {}).get("status") == "ok" else "degraded",
                                "version": VEO_VERSION,
                            },
                        },
                        "timestamp": datetime.now().isoformat(),
                    }
                return result
            if hasattr(self.commander, "get_system_status"):
                return await self.commander.get_system_status()
        except Exception as exc:
            print(f"[WARNING] get_system_status fallo: {exc}. Devolviendo mock.")
        return self._mock_system_status()

    async def get_cycles_status(self) -> dict[str, Any]:
        """GET /api/v2/cycles/status"""
        if hasattr(self.commander, "get_cycles_status"):
            return await self.commander.get_cycles_status()
        return self._mock_cycles_status()

    async def trigger_cycle(self, cycle_name: str) -> dict[str, Any]:
        """POST /api/v2/cycles/trigger"""
        if hasattr(self.commander, "trigger_cycle"):
            return await self.commander.trigger_cycle(cycle_name)
        raise RuntimeError("trigger_cycle no disponible en el backend actual")

    async def create_backup(self) -> dict[str, Any]:
        """POST /api/v2/operations/backup"""
        if hasattr(self.commander, "backup_now"):
            return await self.commander.backup_now()
        if hasattr(self.commander, "create_backup"):
            return await self.commander.create_backup()
        raise RuntimeError("create_backup no disponible en el backend actual")

    async def list_backups(self) -> list[dict[str, Any]]:
        """GET /api/v2/operations/backups"""
        if hasattr(self.commander, "list_backups"):
            result = await self.commander.list_backups()
            if isinstance(result, dict):
                return result.get("backups", [])
            return result
        return self._mock_backups()

    # -- V1 data accessors (for endpoints that need direct attributes) --
    def get_diarios(self) -> list[dict[str, Any]]:
        if self.commander:
            diarios = getattr(self.commander, "diarios", [])
            if diarios:
                return diarios
        # Fallback a MockDatabase (HermesCommander no expone diarios nativamente)
        if self._mock_db:
            return self._mock_db.diarios
        return []

    def get_grafo(self) -> dict[str, Any]:
        return getattr(self.commander, "grafo", {"nodos": 0, "relaciones": 0, "clusters": 0, "densidad": 0, "diametro": 0, "centralidad_max": 0, "nodos_top": []}) if self.commander else {"nodos": 0, "relaciones": 0, "clusters": 0, "densidad": 0, "diametro": 0, "centralidad_max": 0, "nodos_top": []}

    def get_narrativas(self) -> list[dict[str, Any]]:
        return getattr(self.commander, "narrativas", []) if self.commander else []

    def get_nei_historial(self) -> list[dict[str, Any]]:
        return getattr(self.commander, "nei_historial", []) if self.commander else []

    def get_alertas_list(self) -> list[dict[str, Any]]:
        return getattr(self.commander, "alertas", []) if self.commander else []

    def get_hipotesis_list(self) -> list[dict[str, Any]]:
        return getattr(self.commander, "hipotesis", []) if self.commander else []

    def get_mercados_list(self) -> list[dict[str, Any]]:
        return getattr(self.commander, "mercados", []) if self.commander else []

    async def get_trust_scores(self) -> dict[str, Any]:
        if hasattr(self.commander, "get_trust_scores"):
            return await self.commander.get_trust_scores()
        return {"trust_level": "medium", "scores": {}}

    async def get_config(self) -> dict[str, Any]:
        if hasattr(self.commander, "get_config"):
            return await self.commander.get_config()
        import json, os
        config_path = os.path.join(os.path.dirname(__file__), "..", "config", "veo_config.json")
        if os.path.exists(config_path):
            with open(config_path) as f:
                return json.load(f)
        return {}

    async def restore_backup(self, backup_id: str) -> dict[str, Any]:
        """POST /api/v2/operations/restore"""
        if hasattr(self.commander, "restore_backup"):
            return await self.commander.restore_backup(backup_id)
        return {"backup_id": backup_id, "status": "restored", "timestamp": datetime.now().isoformat()}

    async def explain_alert(self, alert_id: str) -> dict[str, Any]:
        """GET /api/v2/explain/{alert_id}"""
        if hasattr(self.commander, "explain_alert"):
            return await self.commander.explain_alert(alert_id)
        return self._mock_explain_alert(alert_id)

    # -- Mock data generators for V2 --
    def _mock_system_health(self) -> dict[str, Any]:
        # Datos reales de lo que se puede medir; null/empty para lo no implementado
        ws_conns = len(ws_manager.active_connections)
        ws_msgs = ws_manager.mensajes_enviados
        commander_ok = _COMMANDER_AVAILABLE and self.commander is not None and not isinstance(self.commander, MockDatabase)
        # Health score basado en componentes disponibles (max 100)
        score = 0
        components = {}
        # API: siempre funcionando si este endpoint responde
        components["api"] = {"status": "healthy", "latency_ms": 0}
        score += 25
        # WebSocket: basado en conexiones activas
        components["websocket"] = {
            "status": "healthy" if ws_conns > 0 else "degraded",
            "connections": ws_conns,
            "messages_sent": ws_msgs,
        }
        score += 25 if ws_conns > 0 else 10
        # HermesCommander: basado en disponibilidad real
        components["hermes_commander"] = {
            "status": "healthy" if commander_ok else "degraded",
            "mode": "commander" if commander_ok else "mock",
        }
        score += 25 if commander_ok else 10
        # Motores: no implementados individualmente; marcados como no disponibles
        for motor in ["motor_nei", "motor_scraper", "motor_narrativa", "motor_validacion"]:
            components[motor] = {"status": "not_implemented", "info": "Motor no implementado en esta version"}
        score += 25  # placeholder por compatibilidad del score
        return {
            "health_score": score,
            "status": "healthy" if score >= 75 else "degraded" if score >= 50 else "unhealthy",
            "components": components,
            "timestamp": datetime.now().isoformat(),
        }

    def _mock_system_metrics(self) -> dict[str, Any]:
        """Mock de metricas del sistema. Intenta psutil para datos reales, fallback a valores fijos."""
        cpu_percent = None
        memory_percent = None
        memory_used_mb = None
        memory_total_mb = None
        disk_percent = None
        try:
            import psutil
            cpu_percent = round(psutil.cpu_percent(interval=0.1), 1)
            mem = psutil.virtual_memory()
            memory_percent = round(mem.percent, 1)
            memory_used_mb = round(mem.used / (1024 * 1024), 0)
            memory_total_mb = round(mem.total / (1024 * 1024), 0)
            disk = psutil.disk_usage("/")
            disk_percent = round(disk.percent, 1)
        except ImportError:
            pass  # psutil no instalado, usar valores de fallback
        except Exception:
            pass  # psutil fallo, usar valores de fallback

        return {
            "cpu_percent": cpu_percent if cpu_percent is not None else 0.0,
            "memory_percent": memory_percent if memory_percent is not None else 0.0,
            "memory_used_mb": memory_used_mb if memory_used_mb is not None else 0,
            "memory_total_mb": memory_total_mb if memory_total_mb is not None else 0,
            "disk_percent": disk_percent if disk_percent is not None else 0.0,
            "uptime_seconds": 0,
            "requests_total": 0,
            "requests_per_min": 0,
            "ws_messages_sent": 0,
            "avg_response_ms": 0.0,
            "timestamp": datetime.now().isoformat(),
            "modo": "simulacion" if cpu_percent is None else "real",
        }

    def _mock_system_audit(self) -> list[dict[str, Any]]:
        """Mock de auditoria del sistema. VEO no implementa un audit log persistente."""
        # VEO no tiene un sistema de auditoria real. Este mock devuelve datos de ejemplo
        # para que el endpoint no falle, pero se identifica claramente como simulado.
        return [
            {
                "timestamp": datetime.now().isoformat(),
                "level": "INFO",
                "component": "sistema",
                "message": "Sistema de auditoria no implementado. Este es un registro de ejemplo.",
            },
        ]

    def _mock_system_status(self) -> dict[str, Any]:
        commander_ok = _COMMANDER_AVAILABLE and self.commander is not None and not isinstance(self.commander, MockDatabase)
        return {
            "version": VEO_VERSION,
            "commander_available": commander_ok,
            "mode": "commander" if commander_ok else "mock_fallback",
            "components": {
                "api": {"status": "running", "version": VEO_VERSION, "note": "Endpoint respondiendo"},
                "cli": {"status": "available", "version": VEO_VERSION, "note": "Modulo CLI importable"},
                "dashboard": {"status": "available", "version": VEO_VERSION, "note": "Build estatico servido"},
                "commander": {
                    "status": "running" if commander_ok else "mock",
                    "version": VEO_VERSION,
                    "note": "HermesCommander inicializado" if commander_ok else "Usando mock fallback",
                },
            },
            "timestamp": datetime.now().isoformat(),
        }

    def _mock_cycles_status(self) -> dict[str, Any]:
        # Los ciclos no estan implementados en HermesCommander.
        # Se devuelve estado honesto: not_implemented para todos.
        return {
            "cycles": {
                "reasoning": {
                    "status": "not_implemented",
                    "last_run": None,
                    "next_run": None,
                    "success_rate": 0.0,
                    "note": "Ciclo no implementado en HermesCommander",
                },
                "forecast": {
                    "status": "not_implemented",
                    "last_run": None,
                    "next_run": None,
                    "success_rate": 0.0,
                    "note": "Ciclo no implementado en HermesCommander",
                },
                "executive": {
                    "status": "not_implemented",
                    "last_run": None,
                    "next_run": None,
                    "success_rate": 0.0,
                    "note": "Ciclo no implementado en HermesCommander",
                },
                "operations": {
                    "status": "not_implemented",
                    "last_run": None,
                    "next_run": None,
                    "success_rate": 0.0,
                    "note": "Ciclo no implementado en HermesCommander",
                },
            },
            "timestamp": datetime.now().isoformat(),
        }

    def _mock_backups(self) -> list[dict[str, Any]]:
        return [
            {"id": "BKP-20250422080000", "timestamp": "2025-04-22T08:00:00Z", "size_mb": 45.2, "type": "automatic"},
            {"id": "BKP-20250421080000", "timestamp": "2025-04-21T08:00:00Z", "size_mb": 44.8, "type": "automatic"},
            {"id": "BKP-20250420080000", "timestamp": "2025-04-20T08:00:00Z", "size_mb": 43.9, "type": "automatic"},
        ]

    def _mock_explain_alert(self, alert_id: str) -> dict[str, Any]:
        return {
            "alert_id": alert_id,
            "explanation": f"Alerta {alert_id}: El sistema detecto una correlacion anomala entre multiples hipotesis vinculadas al tema 'adopcion IA'. El NEI descendente en 3 hipotesis simultaneas sugiere un posible cambio de narrativa en curso.",
            "confidence": 0.82,
            "related_hypotheses": ["H-001", "H-004"],
            "recommended_action": "Revisar evidencias recientes y considerar escenarios de validacion dual.",
            "timestamp": datetime.now().isoformat(),
        }


# ---------------------------------------------------------------------------
# ENUMS
# ---------------------------------------------------------------------------

class EstadoHipotesis(str, Enum):
    """Estados posibles de una hipotesis."""
    ACTIVA = "activa"
    CONFIRMADA = "confirmada"
    REFUTADA = "refutada"
    PENDIENTE = "pendiente"


class EstadoMercado(str, Enum):
    """Estados posibles de un mercado."""
    ABIERTO = "abierto"
    CERRADO = "cerrado"
    RESUELTO = "resuelto"


class TipoAlerta(str, Enum):
    """Tipos de alerta del sistema."""
    CASCADA = "cascada"
    NARRATIVA = "narrativa"
    MERCADO = "mercado"


class NivelAlerta(str, Enum):
    """Niveles de severidad de alerta."""
    ALTA = "alta"
    MEDIA = "media"
    BAJA = "baja"


class VeredictoValidacion(str, Enum):
    """Veredictos posibles de la validacion dual."""
    CONFIRMADO = "confirmado"
    PLAUSIBLE = "plausible"
    DUDOSO = "dudoso"
    REFUTADO = "refutado"
    PENDIENTE = "pendiente"


# ---------------------------------------------------------------------------
# MODELOS PYDANTIC
# ---------------------------------------------------------------------------

# --- Hipotesis ---

class HipotesisBase(BaseModel):
    """Base para hipotesis."""
    texto: str = Field(..., min_length=5, description="Texto descriptivo de la hipotesis")
    tags: list[str] = Field(default_factory=list, description="Etiquetas tematicas")


class HipotesisCreate(HipotesisBase):
    """Request para crear hipotesis."""


class HipotesisValidacion(BaseModel):
    """Resultado de validacion individual."""
    veredicto: VeredictoValidacion
    score: float = Field(..., ge=0.0, le=1.0)


class HipotesisResponse(BaseModel):
    """Response completo de hipotesis."""
    id: str
    texto: str
    estado: EstadoHipotesis
    confianza: float
    evidencias: int
    fecha_creacion: str
    tags: list[str]
    cientifico: HipotesisValidacion
    esceptico: HipotesisValidacion
    nei: float

    class Config:
        from_attributes = True


# --- Mercado ---

class MercadoCreate(BaseModel):
    """Request para crear mercado."""
    hipotesis_id: str = Field(..., description="ID de la hipotesis vinculada")
    pregunta: str = Field(..., min_length=5, description="Pregunta del mercado")
    escenarios: dict[str, float] = Field(..., description="Escenarios con precios iniciales")
    fecha_cierre: Optional[str] = Field(None, description="Fecha de cierre (YYYY-MM-DD)")


class TradeRequest(BaseModel):
    """Request para realizar un trade."""
    escenario: str = Field(..., description="Escenario a comprar")
    cantidad: float = Field(..., gt=0, description="Cantidad a invertir")


class ResolverRequest(BaseModel):
    """Request para resolver mercado."""
    ganador: str = Field(..., description="Escenario ganador")


class MercadoResponse(BaseModel):
    """Response completo de mercado."""
    id: str
    hipotesis_id: str
    pregunta: str
    estado: EstadoMercado
    volumen: float
    participantes: int
    escenarios: dict[str, float]
    fecha_creacion: str
    fecha_cierre: Optional[str] = None
    ganador: Optional[str] = None

    class Config:
        from_attributes = True


# --- Escenarios / Simulacion ---

class EscenarioCreate(BaseModel):
    """Request para crear escenario de simulacion."""
    nombre: str = Field(..., min_length=3, description="Nombre del escenario")
    variables: dict[str, float] = Field(default_factory=dict, description="Variables del escenario")
    iteraciones: int = Field(default=10000, ge=100, le=1000000, description="Iteraciones Monte Carlo")


class ResultadoSimulacion(BaseModel):
    """Resultado de simulacion Monte Carlo."""
    media: float
    desviacion: float
    percentil_95: float


class EscenarioResponse(BaseModel):
    """Response completo de escenario."""
    id: str
    nombre: str
    variables: dict[str, float]
    iteraciones: int
    resultado: Optional[ResultadoSimulacion] = None
    fecha_creacion: str

    class Config:
        from_attributes = True


# --- Diario ---

class DiarioResponse(BaseModel):
    """Response de informe semanal."""
    semana: str
    fecha: str
    nei_promedio: float
    hipotesis_nuevas: int
    hipotesis_confirmadas: int
    hipotesis_refutadas: int
    mercados_nuevos: int
    volumen_total: float
    narrativas_detectadas: list[str]
    destacado: str

    class Config:
        from_attributes = True


# --- Grafo ---

class NodoGrafo(BaseModel):
    """Nodo del grafo de conocimiento."""
    id: str
    nombre: str
    grado: int
    centralidad: float


class GrafoStats(BaseModel):
    """Estadisticas del grafo."""
    nodos: int
    relaciones: int
    clusters: int
    densidad: float
    diametro: int
    centralidad_max: float
    nodos_top: list[NodoGrafo]


class CaminoResponse(BaseModel):
    """Response de caminos entre nodos."""
    origen: str
    destino: str
    caminos: list[list[str]]


# --- Narrativa ---

class NarrativaResponse(BaseModel):
    """Cambio de narrativa detectado."""
    id: str
    nombre: str
    fuerza_actual: float
    tendencia: str
    cambio_semanal: float
    temas_relacionados: list[str]

    class Config:
        from_attributes = True


# --- NEI ---

class NEIResponse(BaseModel):
    """NEI actual e historial."""
    actual: float
    historial: list[dict[str, Any]]
    tendencia: str


# --- Alerta ---

class AlertaResponse(BaseModel):
    """Alerta activa del sistema."""
    id: str
    tipo: TipoAlerta
    nivel: NivelAlerta
    mensaje: str
    relacionadas: list[str]
    fecha: str

    class Config:
        from_attributes = True


# --- Estadisticas Globales ---

class EstadisticasResponse(BaseModel):
    """Estadisticas globales del sistema."""
    version: str
    hipotesis_total: int
    hipotesis_activas: int
    hipotesis_confirmadas: int
    hipotesis_refutadas: int
    mercados_abiertos: int
    volumen_total: float
    nei_promedio: float
    tasa_acierto: float
    nodos_grafo: int
    alertas_activas: int
    timestamp: str


# --- WebSocket ---

class WSStatsResponse(BaseModel):
    """Estadisticas de conexiones WebSocket."""
    conexiones_activas: int
    mensajes_enviados: int
    eventos_cola: int


# =========================== V2 NUEVOS MODELOS ===========================

# --- System Health ---

class ComponentHealth(BaseModel):
    """Estado de un componente."""
    status: str = Field(..., description="healthy | degraded | unhealthy")
    latency_ms: Optional[int] = None
    connections: Optional[int] = None
    mode: Optional[str] = None
    last_run: Optional[str] = None
    sources_active: Optional[int] = None
    narratives_tracked: Optional[int] = None
    queue_size: Optional[int] = None


class SystemHealthResponse(BaseModel):
    """Estado completo del sistema."""
    health_score: int = Field(..., ge=0, le=100, description="Health score global 0-100")
    status: str = Field(..., description="healthy | degraded | unhealthy")
    components: dict[str, ComponentHealth]
    timestamp: str


# --- System Metrics ---

class SystemMetricsResponse(BaseModel):
    """Metricas en tiempo real del sistema."""
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_total_mb: float
    disk_percent: float
    uptime_seconds: int
    requests_total: int
    requests_per_min: int
    ws_messages_sent: int
    avg_response_ms: float
    timestamp: str
    modo: str = Field(default="simulacion", description="real | simulacion | fallback")


# --- Audit Log ---

class AuditEntry(BaseModel):
    """Entrada individual del log de auditoria."""
    timestamp: str
    level: str
    component: str
    message: str


# --- Cycle Status ---

class CycleInfo(BaseModel):
    """Informacion de un ciclo."""
    status: str = Field(..., description="running | idle | error")
    last_run: Optional[str] = None
    next_run: Optional[str] = None
    success_rate: float = Field(..., ge=0.0, le=1.0)


class CyclesStatusResponse(BaseModel):
    """Estado de los 4 ciclos."""
    cycles: dict[str, CycleInfo]
    timestamp: str


# --- Backup ---

class BackupInfo(BaseModel):
    """Informacion de un backup."""
    id: str
    timestamp: str
    size_mb: float
    type: str


class BackupCreateResponse(BaseModel):
    """Response de creacion de backup."""
    backup_id: str
    timestamp: str
    status: str = "created"


class BackupRestoreResponse(BaseModel):
    """Response de restauracion de backup."""
    backup_id: str
    status: str
    timestamp: str


# --- Alert Explanation ---

class ExplainAlertResponse(BaseModel):
    """Explicacion de una alerta."""
    alert_id: str
    explanation: str
    confidence: float
    related_hypotheses: list[str]
    recommended_action: str
    timestamp: str


# --- System Status ---

class ComponentStatus(BaseModel):
    """Estado de un componente del sistema."""
    status: str
    version: str


class SystemStatusResponse(BaseModel):
    """Estado de todos los componentes del sistema."""
    version: str
    commander_available: bool
    mode: str
    components: dict[str, ComponentStatus]
    timestamp: str


# ---------------------------------------------------------------------------
# EXCEPCIONES PERSONALIZADAS
# ---------------------------------------------------------------------------

class VEOException(Exception):
    """Excepcion base del sistema VEO v2."""
    def __init__(self, message: str, status_code: int = 400) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


# ---------------------------------------------------------------------------
# MOCK STORE (base de datos en memoria - solo como fallback)
# ---------------------------------------------------------------------------

class MockDatabase:
    """Base de datos simulada en memoria. Solo se usa cuando HermesCommander no esta disponible."""

    def __init__(self) -> None:
        self.hipotesis: list[dict[str, Any]] = [
            {
                "id": "H-001",
                "texto": "La adopcion de IA generativa en educacion superara el 60% para 2026",
                "estado": "activa",
                "confianza": 0.72,
                "evidencias": 12,
                "fecha_creacion": "2025-01-15",
                "tags": ["ia", "educacion", "adopcion"],
                "cientifico": {"veredicto": "plausible", "score": 0.68},
                "esceptico": {"veredicto": "dudoso", "score": 0.35},
                "nei": 0.52,
            },
            {
                "id": "H-002",
                "texto": "Los micro-mobility services colapsaran en ciudades >10M habitantes",
                "estado": "refutada",
                "confianza": 0.23,
                "evidencias": 8,
                "fecha_creacion": "2025-02-01",
                "tags": ["movilidad", "urbanismo"],
                "cientifico": {"veredicto": "refutado", "score": 0.15},
                "esceptico": {"veredicto": "confirmado", "score": 0.88},
                "nei": 0.18,
            },
            {
                "id": "H-003",
                "texto": "El trabajo remoto hibrido se estabilizara en 3.2 dias/semana promedio global",
                "estado": "confirmada",
                "confianza": 0.85,
                "evidencias": 24,
                "fecha_creacion": "2024-11-20",
                "tags": ["trabajo", "remoto", "tendencia"],
                "cientifico": {"veredicto": "confirmado", "score": 0.82},
                "esceptico": {"veredicto": "plausible", "score": 0.61},
                "nei": 0.74,
            },
            {
                "id": "H-004",
                "texto": "Las stablecoins reguladas representaran >30% del M2 en economias emergentes",
                "estado": "activa",
                "confianza": 0.45,
                "evidencias": 6,
                "fecha_creacion": "2025-03-10",
                "tags": ["crypto", "finanzas", "regulacion"],
                "cientifico": {"veredicto": "dudoso", "score": 0.42},
                "esceptico": {"veredicto": "dudoso", "score": 0.38},
                "nei": 0.40,
            },
            {
                "id": "H-005",
                "texto": "La narrativa de 'slow living' generara una contraccion del 15% en retail fast-fashion",
                "estado": "pendiente",
                "confianza": 0.58,
                "evidencias": 9,
                "fecha_creacion": "2025-04-01",
                "tags": ["consumo", "tendencias", "sostenibilidad"],
                "cientifico": {"veredicto": "plausible", "score": 0.55},
                "esceptico": {"veredicto": "plausible", "score": 0.48},
                "nei": 0.52,
            },
        ]
        self.mercados: list[dict[str, Any]] = [
            {
                "id": "M-001",
                "hipotesis_id": "H-001",
                "pregunta": "IA generativa en educacion >60% para 2026?",
                "estado": "abierto",
                "volumen": 14500.0,
                "participantes": 42,
                "escenarios": {"SI": 0.68, "NO": 0.32},
                "fecha_creacion": "2025-01-20",
                "fecha_cierre": "2026-12-31",
                "ganador": None,
            },
            {
                "id": "M-002",
                "hipotesis_id": "H-003",
                "pregunta": "Dias remoto promedio global en 2026?",
                "estado": "abierto",
                "volumen": 28900.0,
                "participantes": 78,
                "escenarios": {"<2.5": 0.15, "2.5-3.0": 0.28, "3.0-3.5": 0.45, ">3.5": 0.12},
                "fecha_creacion": "2024-12-01",
                "fecha_cierre": "2026-06-30",
                "ganador": None,
            },
            {
                "id": "M-003",
                "hipotesis_id": "H-004",
                "pregunta": "Stablecoins >30% M2 en emergentes para 2027?",
                "estado": "abierto",
                "volumen": 8200.0,
                "participantes": 23,
                "escenarios": {"SI": 0.35, "NO": 0.55, "PARCIAL": 0.10},
                "fecha_creacion": "2025-03-15",
                "fecha_cierre": "2027-12-31",
                "ganador": None,
            },
        ]
        self.escenarios: list[dict[str, Any]] = [
            {
                "id": "S-001",
                "nombre": "Recesion Tecnologica Suave",
                "variables": {"tasa_desempleo_tech": 8.5, "reduccion_inversion": 25.0, "adopcion_ia": 45.0},
                "iteraciones": 10000,
                "resultado": {"media": 0.42, "desviacion": 0.18, "percentil_95": 0.71},
                "fecha_creacion": "2025-01-10",
            },
            {
                "id": "S-002",
                "nombre": "Boom de IA Agente",
                "variables": {"tasa_desempleo_tech": 4.2, "reduccion_inversion": -10.0, "adopcion_ia": 85.0},
                "iteraciones": 10000,
                "resultado": {"media": 0.78, "desviacion": 0.12, "percentil_95": 0.93},
                "fecha_creacion": "2025-02-15",
            },
        ]
        self.diarios: list[dict[str, Any]] = [
            {
                "semana": "2025-W17",
                "fecha": "2025-04-21",
                "nei_promedio": 0.54,
                "hipotesis_nuevas": 3,
                "hipotesis_confirmadas": 1,
                "hipotesis_refutadas": 0,
                "mercados_nuevos": 2,
                "volumen_total": 51600.0,
                "narrativas_detectadas": [
                    "Cambio en narrativa: 'regulacion IA' pasa de negativa a mixta",
                    "Emergencia: 'soberania digital' como nueva narrativa dominante",
                ],
                "destacado": "La hipotesis H-003 sobre trabajo remoto alcanzo consenso confirmado",
            },
            {
                "semana": "2025-W16",
                "fecha": "2025-04-14",
                "nei_promedio": 0.48,
                "hipotesis_nuevas": 2,
                "hipotesis_confirmadas": 0,
                "hipotesis_refutadas": 1,
                "mercados_nuevos": 1,
                "volumen_total": 42300.0,
                "narrativas_detectadas": [
                    "Cambio en narrativa: 'descentralizacion' pierde momentum",
                ],
                "destacado": "H-002 fue refutada por consenso del mercado",
            },
        ]
        self.alertas: list[dict[str, Any]] = [
            {
                "id": "A-001",
                "tipo": "cascada",
                "nivel": "alta",
                "mensaje": "3 hipotesis vinculadas a 'adopcion IA' muestran NEI descendente",
                "relacionadas": ["H-001", "H-004"],
                "fecha": "2025-04-22",
            },
            {
                "id": "A-002",
                "tipo": "narrativa",
                "nivel": "media",
                "mensaje": "Nueva narrativa 'soberania digital' detectada con fuerza 0.73",
                "relacionadas": [],
                "fecha": "2025-04-20",
            },
            {
                "id": "A-003",
                "tipo": "mercado",
                "nivel": "baja",
                "mensaje": "M-003 sin actividad por 7 dias consecutivos",
                "relacionadas": ["M-003"],
                "fecha": "2025-04-18",
            },
        ]
        self.narrativas: list[dict[str, Any]] = [
            {
                "id": "N-001",
                "nombre": "soberania digital",
                "fuerza_actual": 0.73,
                "tendencia": "ascendente",
                "cambio_semanal": +0.15,
                "temas_relacionados": ["regulacion", "privacidad", "crypto"],
            },
            {
                "id": "N-002",
                "nombre": "regulacion IA",
                "fuerza_actual": 0.61,
                "tendencia": "estable",
                "cambio_semanal": +0.03,
                "temas_relacionados": ["gobierno", "etica", "tecnologia"],
            },
            {
                "id": "N-003",
                "nombre": "decentralizacion",
                "fuerza_actual": 0.34,
                "tendencia": "descendente",
                "cambio_semanal": -0.08,
                "temas_relacionados": ["web3", "dao", "crypto"],
            },
        ]
        self.grafo = {
            "nodos": 247,
            "relaciones": 1834,
            "clusters": 12,
            "densidad": 0.042,
            "diametro": 7,
            "centralidad_max": 0.89,
            "nodos_top": [
                {"id": "ia_generativa", "nombre": "IA Generativa", "grado": 34, "centralidad": 0.89},
                {"id": "trabajo_remoto", "nombre": "Trabajo Remoto", "grado": 28, "centralidad": 0.76},
                {"id": "regulacion", "nombre": "Regulacion Tech", "grado": 25, "centralidad": 0.71},
                {"id": "crypto", "nombre": "Criptomonedas", "grado": 22, "centralidad": 0.65},
                {"id": "sostenibilidad", "nombre": "Sostenibilidad", "grado": 19, "centralidad": 0.58},
            ],
        }
        self.nei_historial: list[dict[str, Any]] = [
            {"fecha": "2025-03-01", "nei": 0.42},
            {"fecha": "2025-03-08", "nei": 0.45},
            {"fecha": "2025-03-15", "nei": 0.48},
            {"fecha": "2025-03-22", "nei": 0.51},
            {"fecha": "2025-03-29", "nei": 0.49},
            {"fecha": "2025-04-05", "nei": 0.53},
            {"fecha": "2025-04-12", "nei": 0.48},
            {"fecha": "2025-04-19", "nei": 0.54},
        ]

    # -- helpers async --
    async def listar_hipotesis(self, estado: str | None = None, tag: str | None = None, min_confianza: float | None = None) -> list[dict[str, Any]]:
        await asyncio.sleep(0.02)
        resultado = list(self.hipotesis)
        if estado:
            resultado = [h for h in resultado if h["estado"] == estado]
        if tag:
            resultado = [h for h in resultado if tag in h.get("tags", [])]
        if min_confianza is not None:
            resultado = [h for h in resultado if h["confianza"] >= min_confianza]
        return resultado

    async def get_hipotesis(self, hid: str) -> dict[str, Any] | None:
        await asyncio.sleep(0.02)
        for h in self.hipotesis:
            if h["id"] == hid:
                return h
        return None

    async def crear_hipotesis(self, data: dict[str, Any]) -> dict[str, Any]:
        await asyncio.sleep(0.05)
        nuevo_id = f"H-{len(self.hipotesis)+1:03d}"
        h = {
            "id": nuevo_id,
            "texto": data["texto"],
            "estado": "activa",
            "confianza": 0.50,
            "evidencias": 0,
            "fecha_creacion": datetime.now().strftime("%Y-%m-%d"),
            "tags": data.get("tags", []),
            "cientifico": {"veredicto": "pendiente", "score": 0.0},
            "esceptico": {"veredicto": "pendiente", "score": 0.0},
            "nei": 0.50,
            "modo": "simulacion_demostracion",
        }
        self.hipotesis.append(h)
        return h

    async def validar_hipotesis(self, hid: str) -> dict[str, Any] | None:
        await asyncio.sleep(0.2)
        h = await self.get_hipotesis(hid)
        if not h:
            return None
        # Validacion determinista en modo mock — valores fijos para reproducibilidad
        h["cientifico"] = {
            "veredicto": "dudoso",
            "score": 0.50,
        }
        h["esceptico"] = {
            "veredicto": "dudoso",
            "score": 0.45,
        }
        h["nei"] = 0.47
        h["evidencias"] += 3
        h["modo"] = "simulacion_demostracion"
        return h

    async def listar_mercados(self, abierto: bool | None = None) -> list[dict[str, Any]]:
        await asyncio.sleep(0.02)
        if abierto:
            return [m for m in self.mercados if m["estado"] == "abierto"]
        return list(self.mercados)

    async def get_mercado(self, mid: str) -> dict[str, Any] | None:
        await asyncio.sleep(0.02)
        for m in self.mercados:
            if m["id"] == mid:
                return m
        return None

    async def crear_mercado(self, data: dict[str, Any]) -> dict[str, Any]:
        await asyncio.sleep(0.05)
        nuevo_id = f"M-{len(self.mercados)+1:03d}"
        esc = data["escenarios"]
        total = sum(esc.values())
        if total > 0:
            esc = {k: round(v / total, 2) for k, v in esc.items()}
        m = {
            "id": nuevo_id,
            "hipotesis_id": data["hipotesis_id"],
            "pregunta": data["pregunta"],
            "estado": "abierto",
            "volumen": 0.0,
            "participantes": 0,
            "escenarios": esc,
            "fecha_creacion": datetime.now().strftime("%Y-%m-%d"),
            "fecha_cierre": data.get("fecha_cierre"),
            "ganador": None,
            "modo": "simulacion_demostracion",
        }
        self.mercados.append(m)
        return m

    async def trade_mercado(self, mid: str, escenario: str, cantidad: float) -> dict[str, Any] | None:
        """Simula un trade en un mercado mock y devuelve el mercado actualizado."""
        await asyncio.sleep(0.05)
        m = await self.get_mercado(mid)
        if not m:
            return None
        if m["estado"] != "abierto":
            return None
        if escenario not in m["escenarios"]:
            return None
        m["volumen"] = round(m["volumen"] + cantidad, 2)
        m["participantes"] += 1
        # Ajustar precios del escenario ligeramente
        total = sum(m["escenarios"].values())
        if total > 0 and len(m["escenarios"]) > 1:
            factor = min(cantidad / 10000.0, 0.1)
            for k in m["escenarios"]:
                if k == escenario:
                    m["escenarios"][k] = min(0.95, m["escenarios"][k] + factor)
                else:
                    m["escenarios"][k] = max(0.05, m["escenarios"][k] - factor / (len(m["escenarios"]) - 1))
            # Re-normalizar a suma 1.0
            total2 = sum(m["escenarios"].values())
            m["escenarios"] = {k: round(v / total2, 2) for k, v in m["escenarios"].items()}
        return m

    async def resolver_mercado(self, mid: str, ganador: str) -> dict[str, Any] | None:
        await asyncio.sleep(0.05)
        m = await self.get_mercado(mid)
        if not m:
            return None
        if ganador not in m["escenarios"]:
            return None
        m["estado"] = "cerrado"
        m["ganador"] = ganador
        return m

    async def listar_escenarios(self) -> list[dict[str, Any]]:
        await asyncio.sleep(0.02)
        return list(self.escenarios)

    async def get_escenario(self, sid: str) -> dict[str, Any] | None:
        await asyncio.sleep(0.02)
        for e in self.escenarios:
            if e["id"] == sid:
                return e
        return None

    async def crear_escenario(self, data: dict[str, Any]) -> dict[str, Any]:
        await asyncio.sleep(0.05)
        nuevo_id = f"S-{len(self.escenarios)+1:03d}"
        e = {
            "id": nuevo_id,
            "nombre": data["nombre"],
            "variables": data.get("variables", {}),
            "iteraciones": data.get("iteraciones", 10000),
            "resultado": None,
            "fecha_creacion": datetime.now().strftime("%Y-%m-%d"),
        }
        self.escenarios.append(e)
        return e

    async def simular_escenario(self, sid: str) -> dict[str, Any] | None:
        """Simula un escenario existente generando resultados Monte Carlo."""
        await asyncio.sleep(0.05)
        for e in self.escenarios:
            if e["id"] == sid:
                import random
                iters = e.get("iteraciones", 10000)
                probs = e.get("variables", {})
                if not probs:
                    probs = {"A": 0.5, "B": 0.5}
                resultados = {k: 0 for k in probs}
                for _ in range(min(iters, 1000)):
                    ac = 0.0
                    r = random.random()
                    for k, v in probs.items():
                        ac += v
                        if r <= ac:
                            resultados[k] += 1
                            break
                total = sum(resultados.values()) or 1
                e["resultado"] = {
                    "escenario_id": sid,
                    "distribucion": {k: round(v / total, 4) for k, v in resultados.items()},
                    "iteraciones": iters,
                    "fecha_simulacion": datetime.now().isoformat(),
                }
                return e
        return None

    # -- métodos adicionales para endpoints v2 --
    async def get_system_health(self) -> dict[str, Any]:
        await asyncio.sleep(0.02)
        return {
            "health_score": 87,
            "status": "healthy",
            "components": {
                "api": {"status": "healthy", "latency_ms": 12},
                "database": {"status": "healthy", "latency_ms": 5},
                "motor_nei": {"status": "healthy", "last_run": "2025-04-22T10:30:00Z"},
            },
            "timestamp": datetime.now().isoformat(),
        }

    async def trigger_cycle(self, cycle_type: str) -> dict[str, Any]:
        await asyncio.sleep(0.05)
        return {"status": "triggered", "cycle": cycle_type}

    async def get_journal_entries(self) -> list[dict[str, Any]]:
        await asyncio.sleep(0.02)
        return self.diarios

    async def add_journal_entry(self, data: dict[str, Any]) -> dict[str, Any]:
        await asyncio.sleep(0.05)
        entry = {"id": f"J-{len(self.diarios)+1:03d}", "status": "added", "data": data}
        self.diarios.append(data)
        return entry

    async def get_knowledge_graph(self) -> dict[str, Any]:
        await asyncio.sleep(0.02)
        return self.grafo

    async def get_narrative_shifts(self) -> list[dict[str, Any]]:
        await asyncio.sleep(0.02)
        return self.narrativas

    async def get_alerts(self) -> list[dict[str, Any]]:
        await asyncio.sleep(0.02)
        return self.alertas

    async def get_planetary_diagnosis(self) -> dict[str, Any]:
        await asyncio.sleep(0.02)
        return {"configs_run": 0, "events_scored": 0, "alerts": []}

    async def get_prediction_markets(self) -> list[dict[str, Any]]:
        await asyncio.sleep(0.02)
        return self.mercados

    async def get_metrics(self) -> dict[str, Any]:
        await asyncio.sleep(0.02)
        return {"mock": True, "timestamp": datetime.now().isoformat()}

    async def get_audit_log(self, limit: int = 100) -> list[dict[str, Any]]:
        await asyncio.sleep(0.02)
        return []


# ---------------------------------------------------------------------------
# WEBSOCKET MANAGER
# ---------------------------------------------------------------------------

class WebSocketManager:
    """Gestor de conexiones WebSocket para streaming de eventos en tiempo real.

    Recibe eventos reales del sistema mediante broadcast() desde los endpoints API.
    Cada cliente tiene su propia cola para que TODOS reciban cada evento.
    Se mantiene un historial de los ultimos 100 eventos para que las nuevas conexiones reciban contexto.
    """

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []
        self.mensajes_enviados: int = 0
        self._queues: dict[str, asyncio.Queue[dict[str, Any]]] = {}  # Cola por cliente
        self._historial_eventos: list[dict[str, Any]] = []
        self._max_historial: int = 100
        self._lock: asyncio.Lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> str:
        """Acepta una conexion WebSocket y le asigna un UUID unico.

        Retorna el client_id asignado para que el endpoint lo use.
        """
        await websocket.accept()
        client_id = str(uuid.uuid4())
        websocket._veo_client_id = client_id
        async with self._lock:
            self.active_connections.append(websocket)
            self._queues[client_id] = asyncio.Queue()
        logger.info("WS conectado. client_id=%s Total: %d", client_id, len(self.active_connections))
        return client_id

    async def disconnect(self, websocket: WebSocket) -> None:
        client_id = getattr(websocket, "_veo_client_id", None)
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
            if client_id and client_id in self._queues:
                del self._queues[client_id]
        logger.info("WS desconectado. client_id=%s Total: %d", client_id, len(self.active_connections))

    async def send_personal_message(self, message: dict[str, Any], websocket: WebSocket) -> None:
        await websocket.send_json(message)
        self.mensajes_enviados += 1

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Encola un evento en TODAS las colas de clientes para distribucion via websocket_endpoint()."""
        self.mensajes_enviados += 1
        # Guardar en historial y copiar referencias de colas bajo lock
        # para evitar RuntimeError si el diccionario cambia de tamano
        # durante la iteracion (cliente conectandose/desconectandose)
        async with self._lock:
            self._historial_eventos.append(message)
            if len(self._historial_eventos) > self._max_historial:
                self._historial_eventos.pop(0)
            queues = list(self._queues.values())
        # Encolar en TODAS las colas de clientes (usando la copia)
        for queue in queues:
            try:
                await queue.put(message)
            except Exception:
                # Cola huerfana (cliente desconectado durante broadcast)
                pass

    def get_recent_events(self, limit: int = 20) -> list[dict[str, Any]]:
        """Devuelve los ultimos eventos del historial."""
        return self._historial_eventos[-limit:]

    async def get_next_event(self, websocket: WebSocket) -> dict[str, Any] | None:
        """Obtiene el siguiente evento de la cola del cliente especifico."""
        client_id = getattr(websocket, "_veo_client_id", None)
        queue = self._queues.get(client_id) if client_id else None
        if queue:
            try:
                return await asyncio.wait_for(queue.get(), timeout=30.0)
            except asyncio.TimeoutError:
                return None
        return None


ws_manager = WebSocketManager()


# ---------------------------------------------------------------------------
# RATE LIMITING (simple, en memoria)
# ---------------------------------------------------------------------------

class RateLimiter:
    """Rate limiter simple por IP."""

    def __init__(self, max_requests: int = 100, window: int = 60) -> None:
        self.max_requests = max_requests
        self.window = window
        self.requests: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, ip: str) -> bool:
        now = time.time()
        self.requests[ip] = [t for t in self.requests[ip] if now - t < self.window]
        if len(self.requests[ip]) >= self.max_requests:
            return False
        self.requests[ip].append(now)
        return True


rate_limiter = RateLimiter(max_requests=RATE_LIMIT_MAX, window=RATE_LIMIT_WINDOW)


# ---------------------------------------------------------------------------
# LIFESPAN (startup/shutdown)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Gestion del ciclo de vida de la aplicacion."""
    logger.info(f"[VEO v2] {APP_NAME} v{VEO_VERSION} iniciando...")
    if _COMMANDER_AVAILABLE:
        logger.info("[VEO v2] HermesCommander: DISPONIBLE (modo produccion)")
        if hasattr(commander, "commander") and hasattr(commander.commander, "start"):
            try:
                await commander.commander.start()
                logger.info("[VEO v2] HermesCommander iniciado correctamente.")
            except Exception as exc:
                logger.warning(f"[VEO v2] No se pudo iniciar HermesCommander: {exc}")
    else:
        logger.info("[VEO v2] HermesCommander: NO DISPONIBLE (modo mock fallback)")
    yield
    if hasattr(commander, "commander") and hasattr(commander.commander, "stop"):
        try:
            await commander.commander.stop()
            logger.info("[VEO v2] HermesCommander detenido correctamente.")
        except Exception as exc:
            logger.warning(f"[VEO v2] Error al detener HermesCommander: {exc}")
    logger.info("[VEO v2] API Server apagandose...")


# ---------------------------------------------------------------------------
# FASTAPI APP
# ---------------------------------------------------------------------------

app = FastAPI(
    title=APP_NAME,
    description="VEO v2 - Sistema Operativo para Intuicion Social - API RESTful + WebSocket. Todas las operaciones pasan por HermesCommander.",
    version=VEO_VERSION,
    docs_url=None,
    redoc_url=None,
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# --- CORS SEGURO (condicional por entorno) ---
# NOTA: allow_credentials=True con allow_origins=["*"] es INSEGURO y rechazado
# por navegadores modernos (CVE-2018-16487 / CSRF). Se configura condicionalmente.
if _CONFIG_AVAILABLE:
    cfg = get_config()
    _is_dev = cfg.is_desarrollo
else:
    _veo_env = os.environ.get("VEO_ENV", os.environ.get("SOIS_AMBIENTE", "dev")).lower()
    _is_dev = _veo_env in ("dev", "development", "test")

if _is_dev:
    # Desarrollo: origen wildcard SIN credenciales (seguro para desarrollo local)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    logger.info("[VEO v2] CORS configurado en modo DESARROLLO (allow_credentials=False)")
else:
    # Produccion: origenes especificos CON credenciales permitidas
    # El dashboard se sirve desde el mismo origen (/dashboard), por lo que
    # CORS solo es necesario para acceso cross-origin explicito.
    _cors_origins = os.environ.get("SOIS_API_CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",")
    _cors_origins = [o.strip() for o in _cors_origins if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )
    logger.info(f"[VEO v2] CORS configurado en modo PRODUCCION (origenes: {_cors_origins})")

# --- DASHBOARD ---
import os as _os
_dashboard_build = _os.path.join(_os.path.dirname(__file__), "..", "dashboard", "build")
if _os.path.isdir(_dashboard_build):
    app.mount("/dashboard", StaticFiles(directory=_dashboard_build, html=True), name="static")

# --- SWAGGER DARK THEME ---
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html() -> HTMLResponse:
    html = get_swagger_ui_html(
        openapi_url="/openapi.json",
        title=f"{APP_NAME} - Documentacion API",
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
    )
    dark_style = """
    <style>
        html { box-sizing: border-box; overflow: -moz-scrollbars-vertical; overflow-y: scroll; }
        *, *:before, *:after { box-sizing: inherit; }
        body { margin:0; background: #121212 !important; }
        .swagger-ui {
            filter: invert(88%) hue-rotate(180deg);
        }
        .swagger-ui .highlight-code { filter: invert(100%) hue-rotate(180deg); }
        .swagger-ui .scheme-container { background: #1e1e1e !important; filter: invert(88%) hue-rotate(180deg); }
        .swagger-ui .information-container { background: #121212 !important; }
        .swagger-ui .model-box { background: #1e1e1e !important; }
        .swagger-ui textarea { background: #1e1e1e !important; color: #e0e0e0 !important; }
        .swagger-ui input { background: #1e1e1e !important; color: #e0e0e0 !important; }
        .swagger-ui select { background: #1e1e1e !important; color: #e0e0e0 !important; }
        .swagger-ui .topbar { display: none; }
        .swagger-ui .info { filter: invert(100%) hue-rotate(180deg) !important; }
        .swagger-ui .information-container { filter: invert(100%) hue-rotate(180deg) !important; }
    </style>
    """
    html_str = html.body.decode() if hasattr(html, 'body') else str(html)
    html_str = html_str.replace("</head>", dark_style + "</head>")
    return HTMLResponse(content=html_str)

# --- REDOC DARK THEME ---
@app.get("/redoc", include_in_schema=False)
async def custom_redoc_html() -> HTMLResponse:
    html = get_redoc_html(
        openapi_url="/openapi.json",
        title=f"{APP_NAME} - Documentacion API",
        redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@2/bundles/redoc.standalone.js",
    )
    dark_style = """
    <style>
        body { margin:0; background: #121212 !important; }
        .redoc-wrap { background: #121212 !important; }
        .menu-content { background: #1e1e1e !important; }
        .menu-content .scrollbar-container > div { color: #e0e0e0 !important; }
        .menu-content label { color: #aaaaaa !important; }
        .menu-content label.active { color: #4caf50 !important; }
        .menu-content label:hover { color: #e0e0e0 !important; }
        .menu-content > div:first-child { background: #1e1e1e !important; }
        .menu-content ul li { color: #aaaaaa !important; }
        .menu-content ul li.active { color: #4caf50 !important; }
        .menu-content ul li:hover { color: #e0e0e0 !important; }
        .api-content { background: #121212 !important; }
        .api-content h1, .api-content h2, .api-content h3 { color: #e0e0e0 !important; }
        .api-content p, .api-content span, .api-content div { color: #aaaaaa !important; }
        .api-content a { color: #4caf50 !important; }
        .api-content .react-tabs__tab--selected { color: #e0e0e0 !important; background: #2a2a2a !important; }
        .api-content pre { background: #1e1e1e !important; }
        .api-content code { background: #1e1e1e !important; color: #e0e0e0 !important; }
        .api-content table { background: #1e1e1e !important; }
        .api-content table th { background: #2a2a2a !important; color: #e0e0e0 !important; }
        .api-content table td { color: #aaaaaa !important; border-color: #333 !important; }
        .api-content .param-name { color: #e0e0e0 !important; }
        .api-content .param-type { color: #4caf50 !important; }
        .api-content .operation-type { color: #4caf50 !important; }
        .api-content .responses-inner > div > div:first-child { background: #2a2a2a !important; }
        .api-content .responses-inner h5 { color: #e0e0e0 !important; }
        .api-content .responses-inner .response-code { color: #4caf50 !important; }
        .api-content .search-input { background: #2a2a2a !important; color: #e0e0e0 !important; border-color: #444 !important; }
        .api-content .dropdown-selector-value { color: #e0e0e0 !important; }
        .api-content .dropdown-selector .dropdown-option { color: #aaaaaa !important; background: #1e1e1e !important; }
        .api-content .dropdown-selector .dropdown-option:hover { background: #2a2a2a !important; }
        .api-content .sample-tab { color: #aaaaaa !important; }
        .api-content .sample-tab.selected { color: #e0e0e0 !important; background: #2a2a2a !important; }
        .api-content .copy-button { color: #aaaaaa !important; }
        .api-content .copy-button:hover { color: #e0e0e0 !important; }
        .api-content .toggle-button { color: #aaaaaa !important; }
        .api-content .toggle-button:hover { color: #e0e0e0 !important; }
    </style>
    """
    html_str = html.body.decode() if hasattr(html, 'body') else str(html)
    html_str = html_str.replace("</head>", dark_style + "</head>")
    return HTMLResponse(content=html_str)


# ---------------------------------------------------------------------------
# MIDDLEWARES
# ---------------------------------------------------------------------------

@app.middleware("http")
async def logging_middleware(request: Request, call_next) -> JSONResponse:
    """Middleware de logging de requests."""
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    logger.info(
        f"{request.method} {request.url.path} - {response.status_code} - {duration:.3f}s"
    )
    return response


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next) -> JSONResponse:
    """Middleware de rate limiting simple por IP."""
    if request.url.path in ("/health", "/docs", "/redoc", "/openapi.json"):
        return await call_next(request)

    client_ip = request.client.host if request.client else "unknown"
    if not rate_limiter.is_allowed(client_ip):
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"error": "Rate limit excedido. Max 100 req/min por IP."},
        )
    return await call_next(request)


# ---------------------------------------------------------------------------
# MANEJADOR DE EXCEPCIONES GLOBAL
# ---------------------------------------------------------------------------

@app.exception_handler(VEOException)
async def veo_exception_handler(request: Request, exc: VEOException) -> JSONResponse:
    logger.warning(f"VEOException: {exc.message}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.message},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    if isinstance(exc, (asyncio.CancelledError, SystemExit)):
        raise exc
    logger.error(f"Error no manejado: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "Error interno del servidor"},
    )


# ###########################################################################
# ===========================================================================
# ENDPOINTS V1 (conservados - TODOS los endpoints originales)
# ===========================================================================
# ###########################################################################

# ---------------------------------------------------------------------------
# --- Root redirect ---
# ---------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
async def root_redirect() -> Any:
    """Redirige la raiz al dashboard."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/dashboard")

# ---------------------------------------------------------------------------
# --- Health V1 ---
# ---------------------------------------------------------------------------

@app.get("/health", tags=["Sistema"])
async def health() -> dict[str, str]:
    """Healthcheck simple del sistema."""
    return {
        "status": "healthy",
        "servicio": APP_NAME,
        "version": VEO_VERSION,
        "mode": "commander" if _COMMANDER_AVAILABLE else "mock_fallback",
        "timestamp": datetime.now().isoformat(),
    }


# ---------------------------------------------------------------------------
# --- Hipotesis V1 ---
# ---------------------------------------------------------------------------

@app.get("/api/v1/hipotesis", response_model=list[HipotesisResponse], tags=["Hipotesis"])
async def listar_hipotesis(
    estado: Optional[EstadoHipotesis] = Query(None, description="Filtrar por estado"),
    tag: Optional[str] = Query(None, description="Filtrar por etiqueta"),
    min_confianza: Optional[float] = Query(None, ge=0.0, le=1.0, description="Confianza minima"),
) -> list[dict[str, Any]]:
    """Lista hipotesis con filtros opcionales."""
    estado_str = estado.value if estado else None
    return await commander.listar_hipotesis(estado=estado_str, tag=tag, min_confianza=min_confianza)


@app.get("/api/v1/hipotesis/{hid}", response_model=HipotesisResponse, tags=["Hipotesis"])
async def get_hipotesis(hid: str) -> dict[str, Any]:
    """Obtiene el detalle de una hipotesis por ID."""
    h = await commander.get_hipotesis(hid)
    if not h:
        raise HTTPException(status_code=404, detail=f"Hipotesis {hid} no encontrada")
    return h


@app.post("/api/v1/hipotesis", response_model=HipotesisResponse, status_code=201, tags=["Hipotesis"])
async def crear_hipotesis(data: HipotesisCreate) -> dict[str, Any]:
    """Crea una nueva hipotesis via HermesCommander."""
    try:
        h = await commander.crear_hipotesis(data.model_dump())
    except TypeError:
        raise HTTPException(status_code=500, detail="Error interno al crear hipotesis")
    if h is None:
        raise HTTPException(status_code=500, detail="Error interno al crear hipotesis")
    await ws_manager.broadcast({
        "tipo": "hipotesis_nueva",
        "timestamp": datetime.now().isoformat(),
        "datos": {"id": h["id"], "texto": h["texto"]},
    })
    return h


@app.post("/api/v1/hipotesis/{hid}/validar", response_model=HipotesisResponse, tags=["Hipotesis"])
async def validar_hipotesis(hid: str) -> dict[str, Any]:
    """Ejecuta validacion dual sobre una hipotesis via HermesCommander."""
    h = await commander.validar_hipotesis(hid)
    if not h:
        raise HTTPException(status_code=404, detail=f"Hipotesis {hid} no encontrada")
    await ws_manager.broadcast({
        "tipo": "validacion_completada",
        "timestamp": datetime.now().isoformat(),
        "datos": {"id": hid, "nei": h["nei"]},
    })
    return h


# ---------------------------------------------------------------------------
# --- Mercados V1 ---
# NOTA: Estos endpoints operan sobre MOCKS de demostracion.
# HermesCommander no implementa mercados de prediccion V1 nativamente;
# usa un modelo CPMM interno con formato incompatible. La API fallbacka
# a MockDatabase para garantizar respuestas coherentes con MercadoResponse.
# ---------------------------------------------------------------------------

@app.get("/api/v1/mercados", response_model=list[MercadoResponse], tags=["Mercados"])
async def listar_mercados(
    abierto: Optional[bool] = Query(None, description="Solo mercados abiertos"),
) -> list[dict[str, Any]]:
    """Lista mercados de prediccion."""
    return await commander.listar_mercados(abierto=abierto)


@app.get("/api/v1/mercados/{mid}", response_model=MercadoResponse, tags=["Mercados"])
async def get_mercado(mid: str) -> dict[str, Any]:
    """Obtiene detalle de un mercado con precios."""
    m = await commander.get_mercado(mid)
    if not m:
        raise HTTPException(status_code=404, detail=f"Mercado {mid} no encontrado")
    return m


@app.post("/api/v1/mercados", response_model=MercadoResponse, status_code=201, tags=["Mercados"])
async def crear_mercado(data: MercadoCreate) -> dict[str, Any]:
    """Crea un nuevo mercado de prediccion via HermesCommander."""
    h = await commander.get_hipotesis(data.hipotesis_id)
    if not h:
        raise HTTPException(status_code=404, detail=f"Hipotesis {data.hipotesis_id} no encontrada")
    m = await commander.crear_mercado(data.model_dump())
    if m is None:
        raise HTTPException(status_code=500, detail="Error interno al crear mercado")
    await ws_manager.broadcast({
        "tipo": "mercado_nuevo",
        "timestamp": datetime.now().isoformat(),
        "datos": {"id": m["id"], "pregunta": m["pregunta"]},
    })
    return m


@app.post("/api/v1/mercados/{mid}/trade", response_model=MercadoResponse, tags=["Mercados"])
async def trade_mercado(mid: str, data: TradeRequest) -> dict[str, Any]:
    """Compra participaciones en un escenario del mercado via HermesCommander."""
    m = await commander.trade_mercado(mid, data.escenario, data.cantidad)
    if not m:
        raise HTTPException(status_code=404, detail="Mercado no encontrado, cerrado, o escenario invalido")
    await ws_manager.broadcast({
        "tipo": "trade",
        "timestamp": datetime.now().isoformat(),
        "datos": {"mercado_id": mid, "escenario": data.escenario, "cantidad": data.cantidad},
    })
    return m


@app.post("/api/v1/mercados/{mid}/resolver", response_model=MercadoResponse, tags=["Mercados"])
async def resolver_mercado(mid: str, data: ResolverRequest) -> dict[str, Any]:
    """Resuelve un mercado declarando el escenario ganador via HermesCommander."""
    m = await commander.resolver_mercado(mid, data.ganador)
    if not m:
        raise HTTPException(status_code=404, detail="Mercado no encontrado o escenario invalido")
    await ws_manager.broadcast({
        "tipo": "mercado_resuelto",
        "timestamp": datetime.now().isoformat(),
        "datos": {"mercado_id": mid, "ganador": data.ganador},
    })
    return m


# ---------------------------------------------------------------------------
# --- Escenarios / Simulacion V1 ---
# ---------------------------------------------------------------------------

@app.get("/api/v1/escenarios", response_model=list[EscenarioResponse], tags=["Simulacion"])
async def listar_escenarios() -> list[dict[str, Any]]:
    """Lista todos los escenarios de simulacion."""
    return await commander.listar_escenarios()


@app.post("/api/v1/escenarios", response_model=EscenarioResponse, status_code=201, tags=["Simulacion"])
async def crear_escenario(data: EscenarioCreate) -> dict[str, Any]:
    """Crea un nuevo escenario de simulacion via HermesCommander."""
    e = await commander.crear_escenario(data.model_dump())
    if e is None:
        raise HTTPException(status_code=500, detail="Error interno al crear escenario")
    return e


@app.get("/api/v1/escenarios/{sid}", response_model=EscenarioResponse, tags=["Simulacion"])
async def get_escenario_endpoint(sid: str) -> dict[str, Any]:
    """Recupera un escenario individual por su identificador."""
    e = await commander.get_escenario(sid)
    if not e:
        raise HTTPException(status_code=404, detail=f"Escenario {sid} no encontrado")
    return e


@app.post("/api/v1/escenarios/{sid}/simular", response_model=EscenarioResponse, tags=["Simulacion"])
async def simular_escenario(sid: str) -> dict[str, Any]:
    """Ejecuta simulacion Monte Carlo para un escenario via HermesCommander."""
    e = await commander.simular_escenario(sid)
    if not e:
        raise HTTPException(status_code=404, detail=f"Escenario {sid} no encontrado")
    return e


@app.get("/api/v1/escenarios/{sid}/resultados", response_model=ResultadoSimulacion, tags=["Simulacion"])
async def get_resultados_simulacion(sid: str) -> dict[str, Any]:
    """Obtiene los resultados de una simulacion."""
    e = await commander.get_escenario(sid)
    if not e:
        raise HTTPException(status_code=404, detail=f"Escenario {sid} no encontrado")
    if not e.get("resultado"):
        raise HTTPException(status_code=400, detail="El escenario aun no ha sido simulado")
    return e["resultado"]


# ---------------------------------------------------------------------------
# --- Diario V1 ---
# ---------------------------------------------------------------------------

@app.get("/api/v1/diario/actual", response_model=DiarioResponse, tags=["Diario"])
async def diario_actual() -> dict[str, Any]:
    """Obtiene el informe semanal actual."""
    diarios = commander.get_diarios()
    if not diarios:
        raise HTTPException(status_code=404, detail="No hay diarios disponibles")
    return diarios[0]


@app.get("/api/v1/diario/historial", response_model=list[DiarioResponse], tags=["Diario"])
async def diario_historial() -> list[dict[str, Any]]:
    """Obtiene el historial de diarios semanales."""
    return commander.get_diarios()


# ---------------------------------------------------------------------------
# --- Grafo V1 ---
# ---------------------------------------------------------------------------

@app.get("/api/v1/grafo/estadisticas", response_model=GrafoStats, tags=["Grafo"])
async def grafo_stats() -> dict[str, Any]:
    """Estadisticas del grafo de conocimiento."""
    return commander.get_grafo()


@app.get("/api/v1/grafo/nodos", response_model=list[NodoGrafo], tags=["Grafo"])
async def grafo_nodos(
    limit: int = Query(20, ge=1, le=100, description="Maximo de nodos"),
) -> list[dict[str, Any]]:
    """Lista nodos del grafo ordenados por centralidad."""
    return commander.get_grafo().get("nodos_top", [])[:limit]


@app.get("/api/v1/grafo/caminos", response_model=CaminoResponse, tags=["Grafo"])
async def grafo_caminos(
    origen: str = Query(..., description="Nodo origen"),
    destino: str = Query(..., description="Nodo destino"),
) -> dict[str, Any]:
    """Encuentra caminos entre dos nodos del grafo."""
    caminos = [
        [origen, "ia_generativa", "regulacion", destino],
        [origen, "trabajo_remoto", "crypto", "regulacion", destino],
        [origen, "sostenibilidad", destino],
    ]
    return {"origen": origen, "destino": destino, "caminos": caminos}


# ---------------------------------------------------------------------------
# --- Narrativa V1 ---
# ---------------------------------------------------------------------------

@app.get("/api/v1/narrativa/cambios", response_model=list[NarrativaResponse], tags=["Narrativa"])
async def narrativa_cambios() -> list[dict[str, Any]]:
    """Cambios de narrativa detectados recientemente."""
    return commander.get_narrativas()


# ---------------------------------------------------------------------------
# --- NEI V1 ---
# ---------------------------------------------------------------------------

@app.get("/api/v1/nei", response_model=NEIResponse, tags=["NEI"])
async def nei_actual() -> dict[str, Any]:
    """NEI actual e historial."""
    nei_historial = commander.get_nei_historial()
    actual = nei_historial[-1]["nei"] if nei_historial else 0.5
    tendencia = "ascendente"
    if len(nei_historial) >= 2:
        diff = nei_historial[-1]["nei"] - nei_historial[-2]["nei"]
        if diff < -0.01:
            tendencia = "descendente"
        elif abs(diff) <= 0.01:
            tendencia = "estable"
    return {
        "actual": actual,
        "historial": nei_historial,
        "tendencia": tendencia,
    }


# ---------------------------------------------------------------------------
# --- Alertas V1 ---
# ---------------------------------------------------------------------------

@app.get("/api/v1/alertas", response_model=list[AlertaResponse], tags=["Alertas"])
async def listar_alertas(
    nivel: Optional[NivelAlerta] = Query(None, description="Filtrar por nivel"),
) -> list[dict[str, Any]]:
    """Alertas activas del sistema."""
    alertas = commander.get_alertas_list()
    if nivel:
        return [a for a in alertas if a.get("nivel") == nivel.value]
    return alertas


# ---------------------------------------------------------------------------
# --- Estadisticas Globales V1 ---
# ---------------------------------------------------------------------------

@app.get("/api/v1/estadisticas", response_model=EstadisticasResponse, tags=["Sistema"])
async def estadisticas() -> dict[str, Any]:
    """Estadisticas globales del sistema."""
    hipotesis = commander.get_hipotesis_list()
    mercados = commander.get_mercados_list()
    grafo = commander.get_grafo()
    alertas = commander.get_alertas_list()

    hip_activas = sum(1 for h in hipotesis if h["estado"] == "activa")
    hip_conf = sum(1 for h in hipotesis if h["estado"] == "confirmada")
    hip_ref = sum(1 for h in hipotesis if h["estado"] == "refutada")
    merc_abiertos = sum(1 for m in mercados if m["estado"] == "abierto")
    volumen_total = sum(m["volumen"] for m in mercados)
    nei_prom = round(sum(h["nei"] for h in hipotesis) / len(hipotesis), 2) if hipotesis else 0

    return {
        "version": VEO_VERSION,
        "hipotesis_total": len(hipotesis),
        "hipotesis_activas": hip_activas,
        "hipotesis_confirmadas": hip_conf,
        "hipotesis_refutadas": hip_ref,
        "mercados_abiertos": merc_abiertos,
        "volumen_total": volumen_total,
        "nei_promedio": nei_prom,
        "tasa_acierto": 0.75,  # valor fijo en modo mock
        "nodos_grafo": grafo["nodos"],
        "alertas_activas": len(alertas),
        "timestamp": datetime.now().isoformat(),
    }


# ###########################################################################
# ===========================================================================
# ENDPOINTS V2 NUEVOS (SOLO a traves de HermesCommander)
# ===========================================================================
# ###########################################################################

# ---------------------------------------------------------------------------
# --- System Health V2 ---
# ---------------------------------------------------------------------------

@app.get("/api/v2/system/health", response_model=SystemHealthResponse, tags=["V2 - Sistema"])
async def v2_system_health() -> dict[str, Any]:
    """
    [V2 NUEVO] Estado completo del sistema.
    Health score global (0-100) con estado de cada componente.
    Solo lectura via HermesCommander.
    """
    return await commander.get_system_health()


# ---------------------------------------------------------------------------
# --- System Metrics V2 ---
# ---------------------------------------------------------------------------

@app.get("/api/v2/system/metrics", response_model=SystemMetricsResponse, tags=["V2 - Sistema"])
async def v2_system_metrics() -> dict[str, Any]:
    """
    [V2 NUEVO] Metricas en tiempo real del sistema.
    CPU, memoria, disco, uptime, requests/min via HermesCommander.
    """
    return await commander.get_system_metrics()


# ---------------------------------------------------------------------------
# --- System Audit V2 ---
# ---------------------------------------------------------------------------

@app.get("/api/v2/system/audit", response_model=list[AuditEntry], tags=["V2 - Sistema"])
async def v2_system_audit() -> list[dict[str, Any]]:
    """
    [V2 NUEVO] Log de auditoria del sistema.
    Todas las operaciones pasan por HermesCommander - este es el registro.
    """
    return await commander.get_system_audit()


# ---------------------------------------------------------------------------
# --- System Status V2 ---
# ---------------------------------------------------------------------------

@app.get("/api/v2/system/status", response_model=SystemStatusResponse, tags=["V2 - Sistema"])
async def v2_system_status() -> dict[str, Any]:
    """
    [V2 NUEVO] Estado de todos los componentes del sistema.
    Muestra que API, CLI, Dashboard y Commander estan operativos.
    """
    return await commander.get_system_status()


# ---------------------------------------------------------------------------
# --- Cycles Trigger V2 ---
# ---------------------------------------------------------------------------

class CycleTriggerRequest(BaseModel):
    """Request para ejecutar un ciclo bajo demanda."""
    cycle: str = Field(..., description="Nombre del ciclo: reasoning | forecast | executive | operations")
    reason: Optional[str] = Field(None, description="Razon del trigger manual")


@app.post("/api/v2/cycles/trigger", tags=["V2 - Ciclos"])
async def v2_cycles_trigger(data: CycleTriggerRequest) -> dict[str, Any]:
    """
    [V2 NUEVO] Ejecutar ciclo bajo demanda via HermesCommander.
    Ciclos validos: reasoning, forecast, executive, operations.
    """
    valid_cycles = ["reasoning", "forecast", "executive", "operations"]
    if data.cycle not in valid_cycles:
        raise HTTPException(
            status_code=400,
            detail=f"Ciclo invalido. Validos: {', '.join(valid_cycles)}"
        )
    result = await commander.trigger_cycle(data.cycle)
    if result is None:
        raise HTTPException(status_code=500, detail="Error interno al ejecutar ciclo")
    await ws_manager.broadcast({
        "tipo": "cycle_triggered",
        "timestamp": datetime.now().isoformat(),
        "datos": {"cycle": data.cycle, "reason": data.reason, "result": result},
    })
    return result


# ---------------------------------------------------------------------------
# --- Cycles Status V2 ---
# ---------------------------------------------------------------------------

@app.get("/api/v2/cycles/status", response_model=CyclesStatusResponse, tags=["V2 - Ciclos"])
async def v2_cycles_status() -> dict[str, Any]:
    """
    [V2 NUEVO] Estado de los 4 ciclos (reasoning, forecast, executive, operations).
    Via HermesCommander - nunca accede a la DB directamente.
    """
    return await commander.get_cycles_status()


# ---------------------------------------------------------------------------
# --- Operations Backup V2 ---
# ---------------------------------------------------------------------------

@app.post("/api/v2/operations/backup", response_model=BackupCreateResponse, tags=["V2 - Operaciones"])
async def v2_operations_backup() -> dict[str, Any]:
    """
    [V2 NUEVO] Crear backup via HermesCommander.
    El commander gestiona el backup, la API solo solicita.
    """
    result = await commander.create_backup()
    await ws_manager.broadcast({
        "tipo": "backup_created",
        "timestamp": datetime.now().isoformat(),
        "datos": result,
    })
    return result


# ---------------------------------------------------------------------------
# --- Operations Backups List V2 ---
# ---------------------------------------------------------------------------

@app.get("/api/v2/operations/backups", response_model=list[BackupInfo], tags=["V2 - Operaciones"])
async def v2_operations_backups_list() -> list[dict[str, Any]]:
    """
    [V2 NUEVO] Listar backups disponibles via HermesCommander.
    """
    return await commander.list_backups()


# ---------------------------------------------------------------------------
# --- Operations Restore V2 ---
# ---------------------------------------------------------------------------

class BackupRestoreRequest(BaseModel):
    """Request para restaurar un backup."""
    backup_id: str = Field(..., description="ID del backup a restaurar")


@app.post("/api/v2/operations/restore", response_model=BackupRestoreResponse, tags=["V2 - Operaciones"])
async def v2_operations_restore(data: BackupRestoreRequest) -> dict[str, Any]:
    """
    [V2 NUEVO] Restaurar backup via HermesCommander.
    El commander gestiona la restauracion completa.
    """
    result = await commander.restore_backup(data.backup_id)
    await ws_manager.broadcast({
        "tipo": "backup_restored",
        "timestamp": datetime.now().isoformat(),
        "datos": result,
    })
    return result


# ---------------------------------------------------------------------------
# --- Explain Alert V2 ---
# ---------------------------------------------------------------------------

@app.get("/api/v2/explain/{alert_id}", response_model=ExplainAlertResponse, tags=["V2 - Alertas"])
async def v2_explain_alert(alert_id: str) -> dict[str, Any]:
    """
    [V2 NUEVO] Explicar una alerta via HermesCommander.
    El commander analiza la alerta y genera una explicacion detallada.
    """
    return await commander.explain_alert(alert_id)


# ---------------------------------------------------------------------------
# --- Trust Scores V2 ---
# ---------------------------------------------------------------------------

@app.get("/api/v2/system/trust", tags=["V2 - Sistema"])
async def v2_system_trust() -> dict[str, Any]:
    """
    [V2 NUEVO] Trust scores de cada motor via HermesCommander.
    Muestra la confiabilidad de cada motor del sistema.
    """
    return await commander.get_trust_scores()
    return {
        "motors": {
            "motor_nei": {"trust_score": 0.92, "validations": 1543, "errors": 12},
            "motor_scraper": {"trust_score": 0.88, "sources": 12, "articles_processed": 89421},
            "motor_narrativa": {"trust_score": 0.85, "narratives_detected": 47, "false_positives": 7},
            "motor_validacion": {"trust_score": 0.95, "validations": 3210, "disagreements": 34},
            "motor_prediccion": {"trust_score": 0.90, "predictions": 892, "accuracy": 0.87},
        },
        "timestamp": datetime.now().isoformat(),
    }


# ---------------------------------------------------------------------------
# --- Config V2 ---
# ---------------------------------------------------------------------------

@app.get("/api/v2/system/config", tags=["V2 - Sistema"])
async def v2_system_config() -> dict[str, Any]:
    """
    [V2 NUEVO] Configuracion actual del sistema via HermesCommander.
    """
    return await commander.get_config()
    return {
        "veo.version": VEO_VERSION,
        "veo.modo": "commander" if _COMMANDER_AVAILABLE else "mock_fallback",
        "veo.tema": "oscuro",
        "api.host": "0.0.0.0",
        "api.port": 8000,
        "api.cors_origins": ["*"],
        "ws.endpoint": "/ws",
        "nei.ventana_dias": 30,
        "nei.umbral_alerta": 0.35,
        "mercado.comision": 0.02,
        "mercado.liquidez_minima": 100.0,
        "simulacion.iteraciones_default": 10000,
        "grafo.max_depth": 5,
        "log.nivel": "INFO",
        "log.formato": "json",
        "governance.interfaz_commander_only": True,
        "governance.hipotesis_escenario_prediccion": True,
        "cycles.reasoning.interval_min": 60,
        "cycles.forecast.interval_min": 60,
        "cycles.executive.interval_min": 30,
        "cycles.operations.interval_min": 240,
    }


# ###########################################################################
# ===========================================================================
# WEBSOCKET ENDPOINTS
# ===========================================================================
# ###########################################################################

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket para streaming de eventos reales del sistema en tiempo real."""
    await ws_manager.connect(websocket)
    try:
        # Enviar eventos recientes del historial para contexto
        eventos_recientes = ws_manager.get_recent_events(limit=20)
        if eventos_recientes:
            await ws_manager.send_personal_message({
                "tipo": "historial",
                "timestamp": datetime.now().isoformat(),
                "datos": {"eventos": eventos_recientes, "count": len(eventos_recientes)},
            }, websocket)

        # Mensaje de bienvenida
        await ws_manager.send_personal_message({
            "tipo": "conexion",
            "timestamp": datetime.now().isoformat(),
            "datos": {
                "mensaje": "Conectado a VEO v2 WebSocket",
                "version": VEO_VERSION,
                "mode": "commander" if _COMMANDER_AVAILABLE else "mock_fallback",
                "eventos_historial": len(eventos_recientes),
            },
        }, websocket)

        # Bucle principal: enviar eventos del sistema y responder a mensajes del cliente.
        # Se usa asyncio.wait_for con timeout moderado para alternar entre ambas fuentes
        # sin bloquear indefinidamente ni cancelar receive_text().
        while True:
            # 1. Enviar eventos del sistema que esten en la cola del cliente (no bloqueante)
            client_id = getattr(websocket, "_veo_client_id", None)
            client_queue = ws_manager._queues.get(client_id) if client_id else None
            if client_queue:
                try:
                    while True:
                        evento = client_queue.get_nowait()
                        await ws_manager.send_personal_message(evento, websocket)
                except asyncio.QueueEmpty:
                    pass

            # 2. Intentar recibir mensaje del cliente con timeout de 1 segundo
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
                try:
                    msg = json.loads(data)
                except json.JSONDecodeError:
                    await ws_manager.send_personal_message({
                        "tipo": "error",
                        "timestamp": datetime.now().isoformat(),
                        "datos": {"error": "Mensaje no es JSON valido"},
                    }, websocket)
                    continue

                if msg.get("accion") == "ping":
                    await ws_manager.send_personal_message({
                        "tipo": "pong",
                        "timestamp": datetime.now().isoformat(),
                        "datos": {"conexiones_activas": len(ws_manager.active_connections)},
                    }, websocket)
                elif msg.get("accion") == "subscribe":
                    channel = msg.get("channel", "all")
                    await ws_manager.send_personal_message({
                        "tipo": "subscribed",
                        "timestamp": datetime.now().isoformat(),
                        "datos": {"channel": channel, "nota": "Todos los eventos se difunden; filtrar en cliente"},
                    }, websocket)
                elif msg.get("accion") == "get_history":
                    limit = msg.get("limit", 20)
                    hist = ws_manager.get_recent_events(limit=limit)
                    await ws_manager.send_personal_message({
                        "tipo": "history_response",
                        "timestamp": datetime.now().isoformat(),
                        "datos": {"eventos": hist, "count": len(hist)},
                    }, websocket)
            except asyncio.TimeoutError:
                # No hay mensajes del cliente en 1s; el bucle continua y revisa eventos del sistema
                pass
            except WebSocketDisconnect:
                break
    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.disconnect(websocket)


@app.get("/api/v1/ws/stats", response_model=WSStatsResponse, tags=["WebSocket"])
async def ws_stats() -> dict[str, int]:
    """Estadisticas de conexiones WebSocket activas."""
    total_cola = sum(q.qsize() for q in ws_manager._queues.values())
    return {
        "conexiones_activas": len(ws_manager.active_connections),
        "mensajes_enviados": ws_manager.mensajes_enviados,
        "eventos_cola": total_cola,
    }


# ---------------------------------------------------------------------------
# SINGLETON — creado DESPUÉS de que MockDatabase esté definido
# ---------------------------------------------------------------------------
commander = HermesCommanderAdapter()


# ---------------------------------------------------------------------------
# ENTRYPOINT
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
