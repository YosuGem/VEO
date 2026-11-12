"""
VEO CORE v2 - Cerebro Central del Sistema de Detección de Narrativas Emergentes
================================================================================

Orquestador principal que coordina los 4 ciclos autónomos:
  - reasoning_cycle()  : Evidencias → Hipótesis → Validación
  - forecast_cycle()   : Hipótesis Validadas → Escenarios → Predicciones
  - executive_cycle()  : Priorizar → Explicar → Recomendar
  - operations_cycle() : Logs → Métricas → Backups → Integridad

Arquitectura pub/sub interna vía EventBus. Windows nativo. Asyncio puro.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Imports stdlib
# ---------------------------------------------------------------------------
import asyncio
import copy
import hashlib
import json
import logging
import os
import random
import shutil
import sqlite3
import sys
import time
import traceback
import uuid
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum, auto
from heapq import heappop, heappush
from pathlib import Path
from typing import (
    Any,
    Awaitable,
    Callable,
    Coroutine,
    Deque,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Union,
)

# ---------------------------------------------------------------------------
# Imports opcionales: Planetary Engine (graceful fallback)
# ---------------------------------------------------------------------------
try:
    from analysis.planetary_configs import PLANETARY_CONFIGS
    from analysis.planetary_diagnosis_engine import (
        PlanetaryDiagnosisEngine,
        PlanetaryEvent,
    )
    _PLANETARY_AVAILABLE = True
except ImportError:
    PLANETARY_CONFIGS = {}  # type: ignore[assignment]
    PlanetaryDiagnosisEngine = None  # type: ignore[assignment,misc]
    PlanetaryEvent = None  # type: ignore[assignment,misc]
    _PLANETARY_AVAILABLE = False

# ---------------------------------------------------------------------------
# Imports opcionales: Motores de analisis
# ---------------------------------------------------------------------------
try:
    from analysis.hypothesis_engine import MotorHipotesis
    _HYPOTHESIS_AVAILABLE = True
except ImportError:
    MotorHipotesis = None  # type: ignore[assignment,misc]
    _HYPOTHESIS_AVAILABLE = False

try:
    from analysis.scientific_agent import CoordinadorValidacion
    _SCIENTIFIC_AVAILABLE = True
except ImportError:
    CoordinadorValidacion = None  # type: ignore[assignment,misc]
    _SCIENTIFIC_AVAILABLE = False

try:
    from analysis.causal_engine import MotorCausal
    _CAUSAL_AVAILABLE = True
except ImportError:
    MotorCausal = None  # type: ignore[assignment,misc]
    _CAUSAL_AVAILABLE = False

try:
    from analysis.scenario_simulator import SimuladorEscenarios
    _SIMULATOR_AVAILABLE = True
except ImportError:
    SimuladorEscenarios = None  # type: ignore[assignment,misc]
    _SIMULATOR_AVAILABLE = False

# ---------------------------------------------------------------------------
# Paths del proyecto
# ---------------------------------------------------------------------------
V2_ROOT = Path(__file__).resolve().parent.parent
CORE_DIR = V2_ROOT / "core"
OPS_DIR = V2_ROOT / "operations"

if str(V2_ROOT) not in sys.path:
    sys.path.insert(0, str(V2_ROOT))

# ---------------------------------------------------------------------------
# Constantes globales
# ---------------------------------------------------------------------------
APP_NAME = "VEOCore_v2"
DB_PATH = V2_ROOT / "data" / "veo_core.db"
LOG_PATH = V2_ROOT / "logs" / "veo_core.log"
CONFIG_PATH = V2_ROOT / "config" / "veo_config.json"

for _p in (DB_PATH.parent, LOG_PATH.parent, CONFIG_PATH.parent):
    _p.mkdir(parents=True, exist_ok=True)

EPS_MAX = 100
EPS_MIN = 0

# ---------------------------------------------------------------------------
# Tipos
# ---------------------------------------------------------------------------
EventHandler = Callable[[str, Dict[str, Any]], Awaitable[None]]
CycleResult = Dict[str, Any]


# ============================================================================
# EVENTOS
# ============================================================================

class EventType(Enum):
    """Eventos canónicos del bus interno."""
    NEW_SIGNAL = "new_signal"
    NEW_HYPOTHESIS = "new_hypothesis"
    HYPOTHESIS_VALIDATED = "hypothesis_validated"
    NEW_SCENARIO = "new_scenario"
    NEW_PREDICTION = "new_prediction"
    NEW_ALERT = "new_alert"
    RECOMMENDATION_ISSUED = "recommendation_issued"
    CYCLE_COMPLETED = "cycle_completed"
    ERROR_OCCURRED = "error_occurred"
    HEALTH_STATUS = "health_status"
    CONFLICT_DETECTED = "conflict_detected"
    RESOURCE_WARNING = "resource_warning"


# ============================================================================
# LOGGER ESTRUCTURADO JSON
# ============================================================================

class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "lvl": record.levelname,
            "mod": record.name,
            "msg": record.getMessage(),
        }
        for attr in ("event_type", "cycle", "alert_id", "confidence", "details"):
            if hasattr(record, attr):
                payload[attr] = getattr(record, attr)
        if record.exc_info:
            payload["exc"] = traceback.format_exception_only(record.exc_info[0], record.exc_info[1])
        return json.dumps(payload, ensure_ascii=False, default=str)


def _build_logger(name: str = APP_NAME) -> logging.Logger:
    log = logging.getLogger(name)
    log.setLevel(logging.DEBUG)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(JSONFormatter())
    if not any(isinstance(h, logging.StreamHandler) for h in log.handlers):
        log.addHandler(ch)
    fh = logging.FileHandler(LOG_PATH, encoding="utf-8", mode="a")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(JSONFormatter())
    if not any(isinstance(h, logging.FileHandler) for h in log.handlers):
        log.addHandler(fh)
    return log


logger = _build_logger()


# ============================================================================
# 0. FUNCIONES DE UTILIDAD
# ============================================================================

def semilla_iso(fecha: Optional[datetime] = None) -> str:
    """Genera identificador semanal ISO: 'YYYY-WNN'."""
    if fecha is None:
        fecha = datetime.now(timezone.utc)
    iso_cal = fecha.isocalendar()
    return f"{iso_cal[0]}-W{iso_cal[1]:02d}"


def calcular_eps(evento: Dict[str, Any]) -> int:
    """
    Event Priority Score (EPS) 0-100.
    Factores: urgencia(0-40) + confianza(0-30) + impacto(0-20) + recencia(0-10)
    """
    urgency = min(max(evento.get("urgency", 50), 0), 100)
    confidence = min(max(evento.get("confidence", 50), 0), 100)
    impact = min(max(evento.get("impact", 50), 0), 100)

    recency = 5
    ts_raw = evento.get("timestamp")
    if ts_raw:
        try:
            if isinstance(ts_raw, str):
                ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
            elif isinstance(ts_raw, (int, float)):
                ts = datetime.fromtimestamp(ts_raw, tz=timezone.utc)
            else:
                ts = ts_raw
            age_hours = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
            if age_hours < 1:
                recency = 10
            elif age_hours < 6:
                recency = 8
            elif age_hours < 24:
                recency = 6
            elif age_hours < 72:
                recency = 4
            else:
                recency = 2
        except Exception:
            recency = 5

    score = int((urgency * 0.40) + (confidence * 0.30) + (impact * 0.20) + (recency * 0.10))
    return min(max(score, EPS_MIN), EPS_MAX)


def priorizar_eventos(eventos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Ordena eventos por EPS descendente."""
    for ev in eventos:
        if "eps" not in ev:
            ev["eps"] = calcular_eps(ev)
    return sorted(eventos, key=lambda e: e.get("eps", 0), reverse=True)


def _ts_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dict_hash(d: Dict[str, Any]) -> str:
    canonical = json.dumps(d, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


# ============================================================================
# 1. EVENTBUS (pub/sub interno async)
# ============================================================================

class EventBus:
    """Bus de eventos pub/sub asíncrono. Desacopla todos los módulos."""

    def __init__(self) -> None:
        self._handlers: Dict[str, List[EventHandler]] = defaultdict(list)
        self._history: Deque[Dict[str, Any]] = deque(maxlen=10_000)
        self._lock = asyncio.Lock()
        self._event_counts: Dict[str, int] = defaultdict(int)
        self._running = False
        self._delivery_queue: asyncio.Queue[Tuple[str, Dict[str, Any]]] = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        self._running = True
        self._worker_task = asyncio.create_task(self._delivery_worker())
        logger.info("EventBus started")

    async def stop(self) -> None:
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("EventBus stopped")

    async def publish(self, event_type: str, payload: Dict[str, Any]) -> None:
        envelope = {
            "id": str(uuid.uuid4())[:8],
            "type": event_type,
            "payload": payload,
            "ts": _ts_now(),
            "eps": calcular_eps(payload),
        }
        self._history.append(envelope)
        self._event_counts[event_type] += 1
        await self._delivery_queue.put((event_type, envelope))

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        if handler not in self._handlers[event_type]:
            self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        if handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)

    async def _delivery_worker(self) -> None:
        while self._running:
            try:
                event_type, envelope = await asyncio.wait_for(
                    self._delivery_queue.get(), timeout=1.0
                )
            except asyncio.TimeoutError:
                continue
            handlers = list(self._handlers.get(event_type, []))
            handlers.extend(self._handlers.get("*", []))
            if not handlers:
                continue
            results = await asyncio.gather(
                *[self._safe_call(h, event_type, envelope) for h in handlers],
                return_exceptions=True,
            )
            for r in results:
                if isinstance(r, Exception):
                    logger.warning("Handler error: %s", r)

    @staticmethod
    async def _safe_call(handler: EventHandler, event_type: str, envelope: Dict[str, Any]) -> None:
        try:
            await handler(event_type, envelope)
        except Exception as exc:
            logger.error("Handler exception: %s", exc, extra={"event_type": event_type, "details": str(exc)})

    def get_subscriber_count(self, event_type: str) -> int:
        return len(self._handlers.get(event_type, []))

    def get_stats(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            "queue_size": self._delivery_queue.qsize(),
            "event_counts": dict(self._event_counts),
            "subscriber_types": list(self._handlers.keys()),
            "history_len": len(self._history),
        }


# ============================================================================
# 2. SCHEDULER (Priority Queue + ciclos temporizados)
# ============================================================================

@dataclass(order=True)
class ScheduledTask:
    priority_score: float
    next_run: float = field(compare=True)
    cycle_type: str = field(compare=False)
    interval_seconds: float = field(compare=False)
    coro_factory: Callable[[], Coroutine[Any, Any, CycleResult]] = field(compare=False, repr=False)
    last_run: Optional[float] = field(default=None, compare=False)
    run_count: int = field(default=0, compare=False)
    enabled: bool = field(default=True, compare=False)
    task_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8], compare=False)


class Scheduler:
    """Planificador de ciclos con Priority Queue y EPS."""

    def __init__(self, event_bus: EventBus) -> None:
        self.bus = event_bus
        self._heap: List[ScheduledTask] = []
        self._registry: Dict[str, ScheduledTask] = {}
        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    def schedule(
        self,
        cycle_type: str,
        interval_seconds: float,
        priority: int = 50,
        coro_factory: Optional[Callable[[], Coroutine[Any, Any, CycleResult]]] = None,
    ) -> str:
        task = ScheduledTask(
            priority_score=float(-priority),
            next_run=time.time(),
            cycle_type=cycle_type,
            interval_seconds=interval_seconds,
            coro_factory=coro_factory or self._default_coro(cycle_type),
        )
        heappush(self._heap, task)
        self._registry[task.task_id] = task
        logger.info("Scheduled %s every %.0fs (priority=%d, id=%s)", cycle_type, interval_seconds, priority, task.task_id)
        return task.task_id

    def unschedule(self, task_id: str) -> bool:
        if task_id in self._registry:
            self._registry[task_id].enabled = False
            return True
        return False

    async def start(self) -> None:
        self._running = True
        self._scheduler_task = asyncio.create_task(self._loop())
        logger.info("Scheduler started with %d tasks", len(self._heap))

    async def stop(self) -> None:
        self._running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        logger.info("Scheduler stopped")

    async def _loop(self) -> None:
        while self._running:
            await self._tick()
            await asyncio.sleep(1)

    async def _tick(self) -> None:
        now = time.time()
        ready: List[ScheduledTask] = []
        async with self._lock:
            while self._heap and self._heap[0].next_run <= now:
                task = heappop(self._heap)
                if task.enabled:
                    ready.append(task)
        for task in ready:
            asyncio.create_task(self._execute_task(task))

    async def _execute_task(self, task: ScheduledTask) -> None:
        t0 = time.time()
        task.last_run = t0
        task.run_count += 1
        logger.info("Executing cycle: %s (run #%d)", task.cycle_type, task.run_count)
        try:
            result: CycleResult = await task.coro_factory()
            elapsed = time.time() - t0
            result["meta"] = {
                "cycle_type": task.cycle_type,
                "run_count": task.run_count,
                "elapsed_seconds": round(elapsed, 3),
                "task_id": task.task_id,
                "executed_at": _ts_now(),
            }
        except Exception as exc:
            elapsed = time.time() - t0
            result = {
                "error": str(exc),
                "traceback": traceback.format_exc(),
                "meta": {
                    "cycle_type": task.cycle_type,
                    "run_count": task.run_count,
                    "elapsed_seconds": round(elapsed, 3),
                    "task_id": task.task_id,
                    "executed_at": _ts_now(),
                },
            }
            await self.bus.publish(
                EventType.ERROR_OCCURRED.value,
                {"cycle": task.cycle_type, "error": str(exc), "elapsed": round(elapsed, 3)},
            )
        task.next_run = time.time() + task.interval_seconds
        async with self._lock:
            heappush(self._heap, task)
        await self.bus.publish(
            EventType.CYCLE_COMPLETED.value,
            {
                "cycle": task.cycle_type,
                "run_count": task.run_count,
                "elapsed_seconds": round(elapsed, 3),
                "result_summary": self._summarize(result),
            },
        )

    @staticmethod
    def _default_coro(cycle_type: str) -> Callable[[], Coroutine[Any, Any, CycleResult]]:
        async def _noop() -> CycleResult:
            return {"status": "noop", "cycle_type": cycle_type}
        return _noop

    @staticmethod
    def _summarize(result: CycleResult) -> Dict[str, Any]:
        return {
            k: v for k, v in result.items()
            if k != "meta" and (not isinstance(v, (list, dict)) or k in ("status", "error"))
        }

    def get_queue_status(self) -> Dict[str, Any]:
        now = time.time()
        return {
            "registered_tasks": len(self._registry),
            "tasks": [
                {
                    "cycle_type": t.cycle_type,
                    "task_id": t.task_id,
                    "priority": int(-t.priority_score),
                    "interval_s": t.interval_seconds,
                    "run_count": t.run_count,
                    "enabled": t.enabled,
                    "seconds_until_next": max(0, round(t.next_run - now, 1)),
                    "last_run": datetime.fromtimestamp(t.last_run, tz=timezone.utc).isoformat() if t.last_run else None,
                }
                for t in sorted(self._registry.values(), key=lambda x: x.next_run)
            ],
        }

    async def trigger_now(self, task_id: str) -> Optional[CycleResult]:
        task = self._registry.get(task_id)
        if not task:
            return None
        t0 = time.time()
        try:
            result = await task.coro_factory()
            result["meta"] = {
                "cycle_type": task.cycle_type,
                "triggered": "manual",
                "elapsed_seconds": round(time.time() - t0, 3),
                "executed_at": _ts_now(),
            }
        except Exception as exc:
            result = {
                "error": str(exc),
                "traceback": traceback.format_exc(),
                "meta": {"cycle_type": task.cycle_type, "triggered": "manual"},
            }
        return result



# ============================================================================
# 3. LOS 4 CICLOS AUTÓNOMOS
# ============================================================================

class ReasoningCycle:
    """
    Ciclo de Razonamiento: Evidencias → Hipótesis → Validación
    """

    def __init__(self, event_bus: EventBus, motor_hipotesis: Any = None,
                 coordinador_validacion: Any = None, motor_causal: Any = None) -> None:
        self.bus = event_bus
        self.hypotheses_history: Deque[Dict[str, Any]] = deque(maxlen=5_000)
        self.validation_history: Deque[Dict[str, Any]] = deque(maxlen=5_000)
        self.motor_hipotesis = motor_hipotesis
        self.coordinador_validacion = coordinador_validacion
        self.motor_causal = motor_causal

    async def run(self) -> CycleResult:
        t0 = time.time()
        logger.info("[ReasoningCycle] Iniciando recolección de evidencias...")

        raw_signals = await self._gather_signals()
        hypotheses = await self._generate_hypotheses(raw_signals)
        validated = await self._validate_hypotheses(hypotheses)

        elapsed = time.time() - t0

        for hyp in hypotheses:
            await self.bus.publish(
                EventType.NEW_HYPOTHESIS.value,
                {"hypothesis": hyp, "eps": calcular_eps(hyp)},
            )
        for val in validated:
            await self.bus.publish(
                EventType.HYPOTHESIS_VALIDATED.value,
                {"validation": val, "eps": calcular_eps(val)},
            )

        confidence_scores = [v.get("confidence", 0) for v in validated]

        return {
            "hipotesis_generadas": len(hypotheses),
            "hipotesis_validadas": len(validated),
            "tiempo_ejecucion": round(elapsed, 3),
            "confidence_scores": confidence_scores,
            "signals_processed": len(raw_signals),
            "hypotheses": [h["text"] for h in hypotheses[:10]],
            "validated_ids": [v["id"] for v in validated],
        }

    async def _gather_signals(self) -> List[Dict[str, Any]]:
        await asyncio.sleep(0.05)
        now = _ts_now()
        signals = [
            {
                "id": f"sig_{uuid.uuid4().hex[:6]}",
                "source": "web_crawl",
                "text": "Aumento anómalo de menciones de 'criptomoneda' + 'regulación' en Reddit r/CryptoCurrency",
                "urgency": 75, "confidence": 65, "impact": 60,
                "timestamp": now, "domain": "finance",
            },
            {
                "id": f"sig_{uuid.uuid4().hex[:6]}",
                "source": "news_api",
                "text": "Tres bancos centrales anuncian estudios conjuntos sobre CBDC en G7",
                "urgency": 80, "confidence": 90, "impact": 85,
                "timestamp": now, "domain": "policy",
            },
            {
                "id": f"sig_{uuid.uuid4().hex[:6]}",
                "source": "social_trend",
                "text": "Hashtag #DigitalDollar trending en Twitter/X con +300% en 24h",
                "urgency": 60, "confidence": 55, "impact": 50,
                "timestamp": now, "domain": "social",
            },
            {
                "id": f"sig_{uuid.uuid4().hex[:6]}",
                "source": "academic",
                "text": "Paper de MIT sugiere que stablecoins pueden reducir volatilidad del 40% en mercados emergentes",
                "urgency": 45, "confidence": 85, "impact": 55,
                "timestamp": now, "domain": "research",
            },
        ]
        return signals

    async def _generate_hypotheses(self, signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if self.motor_hipotesis is not None and _HYPOTHESIS_AVAILABLE:
            try:
                clusters = [{"topic": s.get("domain", "general"), "size": 1, "samples": [s["text"]], "coherence": s.get("confidence", 50) / 100.0} for s in signals]
                texto_contexto = "; ".join(s["text"] for s in signals)
                hipotesis_objs = await asyncio.get_event_loop().run_in_executor(
                    None, self.motor_hipotesis.generar_hipotesis, clusters, texto_contexto
                )
                hypotheses = []
                for idx, h in enumerate(hipotesis_objs):
                    # Preservar urgency/impact de las señales originales (E)
                    # MotorHipotesis no expone dominio por hipótesis individual;
                    # usamos todas las señales como fuente.
                    avg_urgency = sum(s.get("urgency", 50) for s in signals) / len(signals) if signals else 50
                    avg_impact = sum(s.get("impact", 50) for s in signals) / len(signals) if signals else 50
                    
                    # === Combinación coherente de urgency/impact (G) ===
                    # avg_urgency: promedio de urgency de las señales (input externo, 0-100)
                    # avg_impact: promedio de impact de las señales (input externo, 0-100)
                    # nivel_riesgo: evaluación del motor de hipótesis (0-1, modelo interno)
                    #
                    # Justificación semántica:
                    # - urgency mide presión temporal. Las señales aportan evidencia
                    #   directa del mundo observable. El modelo puede elevar o reducir
                    #   urgency si detecta riesgos sistémicos no evidentes.
                    #   Peso: 60% señales (observable) + 40% modelo (inferido).
                    # - impact mide magnitud de consecuencias. Depende principalmente
                    #   de evidencia observable. El modelo puede modificar levemente.
                    #   Peso: 70% señales + 30% modelo.
                    nivel_riesgo = getattr(h, "nivel_riesgo", None)
                    if nivel_riesgo is not None:
                        riesgo_100 = max(0.0, min(100.0, nivel_riesgo * 100))
                        avg_urgency = round(0.6 * avg_urgency + 0.4 * riesgo_100, 1)
                        avg_impact = round(0.7 * avg_impact + 0.3 * riesgo_100, 1)
                    
                    # Derivar dominio del texto de la hipótesis (heurística simple)
                    domain = "general"
                    h_text_lower = getattr(h, "texto", "").lower()
                    for s in signals:
                        d = s.get("domain", "general")
                        if d != "general" and any(kw in h_text_lower for kw in s["text"].lower().split()[:3]):
                            domain = d
                            break
                    
                    # Enriquecer hipótesis con evidencias de las señales (G)
                    # Esto permite que AgenteCientifico y AgenteEsceptico evalúen
                    # con datos reales en lugar de hipótesis vacías.
                    evidencias = [s["text"] for s in signals]
                    
                    hyp = {
                        "id": getattr(h, "id", f"hyp_{uuid.uuid4().hex[:8]}"),
                        "text": getattr(h, "texto", str(h)),
                        "sources": [s["id"] for s in signals],
                        "domain": domain,
                        "confidence": round(getattr(h, "nei", 0.5) * 100, 1) if getattr(h, "nei", 0.5) <= 1.0 else getattr(h, "nei", 50),
                        "urgency": round(avg_urgency, 1),
                        "impact": round(avg_impact, 1),
                        "timestamp": _ts_now(),
                        "_evidencias_senales": evidencias,  # metadata interna para validación
                    }
                    hypotheses.append(hyp)
                    self.hypotheses_history.append(hyp)
                return hypotheses
            except Exception as e:
                logger.warning("[ReasoningCycle] MotorHipotesis fallo, usando stub: %s", e)

        await asyncio.sleep(0.05)
        hypotheses = []
        by_domain: Dict[str, List[Dict]] = defaultdict(list)
        for s in signals:
            by_domain[s.get("domain", "general")].append(s)
        for domain, sigs in by_domain.items():
            combined_text = "; ".join(s["text"] for s in sigs)
            hyp = {
                "id": f"hyp_{uuid.uuid4().hex[:8]}",
                "text": f"Hipótesis [{domain}]: Existe una narrativa emergente sobre '{combined_text[:120]}...'",
                "sources": [s["id"] for s in sigs],
                "domain": domain,
                "confidence": int(sum(s["confidence"] for s in sigs) / len(sigs)),
                "urgency": max(s["urgency"] for s in sigs),
                "impact": max(s["impact"] for s in sigs),
                "timestamp": _ts_now(),
            }
            hypotheses.append(hyp)
            self.hypotheses_history.append(hyp)
        return hypotheses

    async def _validate_hypotheses(self, hypotheses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        validated = []
        for hyp in hypotheses:
            validation: Dict[str, Any] = {
                "id": hyp["id"],
                "hypothesis_text": hyp["text"],
                "scientific_score": 50,
                "skeptic_score": 50,
                "consensus": 50.0,
                "passed": True,
                "confidence": 50.0,
                "timestamp": _ts_now(),
                "review_notes": "",
            }
            # 1) Validación científica (CoordinadorValidacion)
            if self.coordinador_validacion is not None and _SCIENTIFIC_AVAILABLE:
                try:
                    from analysis.scientific_agent import Hipotesis as SAHipotesis
                    
                    # Enriquecer SAHipotesis con evidencias de señales (G)
                    # para que AgenteCientifico y AgenteEsceptico evalúen con datos reales.
                    evidencias = hyp.get("_evidencias_senales", [])
                    sa_hyp = SAHipotesis(
                        texto=hyp["text"],
                        nivel_confianza_inicial=hyp.get("confidence", 50) / 100.0,
                        evidencia_a_favor=evidencias,
                        evidencia_en_contra=[],
                    )
                    resultado = await asyncio.get_event_loop().run_in_executor(
                        None, self.coordinador_validacion.validar, sa_hyp
                    )
                    
                    # === Mapeo correcto de claves (G) ===
                    # validar() retorna: veredicto_final, confianza, razonamiento_cientifico,
                    #                    evaluacion_sesgos, recomendacion, metadatos
                    # _validate_hypotheses necesita: confidence, scientific_score, skeptic_score, review_notes
                    veredicto = resultado.get("veredicto_final", "")
                    validation["passed"] = veredicto == "ACEPTAR"
                    
                    confianza_global = resultado.get("confianza", 0.5)
                    validation["confidence"] = round(confianza_global * 100, 1)
                    
                    razonamiento = resultado.get("razonamiento_cientifico", {})
                    # scientific_score = calidad cientifica real de la hipotesis
                    # Usa score_compuesto del agente (fuerza_evidencia - penalizaciones)
                    # en lugar de confianza_c (que es confianza del agente en su veredicto).
                    if isinstance(razonamiento, dict):
                        metadatos = razonamiento.get("metadatos", {})
                        score_compuesto = metadatos.get("score_compuesto")
                        if score_compuesto is not None:
                            validation["scientific_score"] = round(score_compuesto * 100, 1)
                        elif "confianza" in razonamiento:
                            validation["scientific_score"] = round(razonamiento["confianza"] * 100, 1)
                        else:
                            validation["scientific_score"] = 50.0
                    else:
                        validation["scientific_score"] = 50.0
                    
                    eval_sesgos = resultado.get("evaluacion_sesgos", {})
                    if isinstance(eval_sesgos, dict) and "score_global" in eval_sesgos:
                        sg = float(eval_sesgos["score_global"])
                        validation["skeptic_score"] = round((1.0 - sg) * 100, 1)
                    else:
                        validation["skeptic_score"] = 50.0
                    
                    validation["review_notes"] = resultado.get("recomendacion", "")
                except Exception as inner_e:
                    logger.warning("[ReasoningCycle] Validacion cientifica fallo: %s", inner_e)
                    validation["review_notes"] += "[CIENTIFICA_FALLBACK] "

            # 2) Validación causal post-científica (E) — SIEMPRE ejecuta si está disponible
            if self.motor_causal is not None and _CAUSAL_AVAILABLE:
                try:
                    causal_result = await asyncio.get_event_loop().run_in_executor(
                        None, self.motor_causal.analizar, hyp
                    )
                    if causal_result.coherencia < 0.4:
                        validation["passed"] = False
                        validation["review_notes"] += " | [CAUSAL] Baja coherencia: " + str(round(causal_result.coherencia, 2))
                    elif causal_result.ciclos_detectados:
                        validation["confidence"] = round(validation["confidence"] * 0.8, 1)
                        validation["review_notes"] += " | [CAUSAL] Ciclos: " + str(causal_result.ciclos_detectados)
                    else:
                        validation["review_notes"] += " | [CAUSAL] OK: " + str(round(causal_result.coherencia, 2))
                except Exception as causal_e:
                    logger.warning("[ReasoningCycle] MotorCausal fallo: %s", causal_e)
                    validation["review_notes"] += " | [CAUSAL_FALLBACK]"

            validated.append(validation)
            if validation["passed"]:
                self.validation_history.append(validation)

        if not validated:
            logger.warning("[ReasoningCycle] Ninguna hipotesis validada, usando stub fallback")
            await asyncio.sleep(0.05)
            validated = []
            for hyp in hypotheses:
                scientific_score = self._scientific_review(hyp)
                skeptic_score = self._skeptic_review(hyp)
                consensus = (scientific_score + skeptic_score) / 2
                passed = consensus >= 50
                validation = {
                    "id": hyp["id"],
                    "hypothesis_text": hyp["text"],
                    "scientific_score": scientific_score,
                    "skeptic_score": skeptic_score,
                    "consensus": round(consensus, 1),
                    "passed": passed,
                    "confidence": round(consensus, 1),
                    "timestamp": _ts_now(),
                    "review_notes": self._generate_review_notes(hyp, scientific_score, skeptic_score),
                }
                self.validation_history.append(validation)
                if passed:
                    validated.append(validation)
        return validated

    @staticmethod
    def _scientific_review(hyp: Dict[str, Any]) -> int:
        base = hyp.get("confidence", 50)
        if len(hyp.get("text", "")) < 50:
            base -= 15
        sources = hyp.get("sources", [])
        if len(sources) >= 2:
            base += 10
        return min(max(base, 0), 100)

    @staticmethod
    def _skeptic_review(hyp: Dict[str, Any]) -> int:
        base = hyp.get("confidence", 50)
        text = hyp.get("text", "").lower()
        alarm_words = ["colapso", "catástrofe", "inminente", "seguramente"]
        penalties = sum(8 for w in alarm_words if w in text)
        base -= penalties
        vague_words = ["algo", "alguien", "quizás", "podría ser"]
        penalties_v = sum(5 for w in vague_words if w in text)
        base -= penalties_v
        return min(max(base, 0), 100)

    @staticmethod
    def _generate_review_notes(hyp: Dict[str, Any], sci: int, skp: int) -> str:
        notes = []
        if sci > 70:
            notes.append("Fuerte base evidencial.")
        elif sci < 40:
            notes.append("Evidencia insuficiente; requiere más datos.")
        if skp > 70:
            notes.append("Bajo sesgo detectado.")
        elif skp < 40:
            notes.append("Posible sesgo de confirmación o alarmismo.")
        return " ".join(notes) if notes else "Revisión estándar completada."


# ---------------------------------------------------------------------------

class ForecastCycle:
    """
    Ciclo de Pronóstico: Hipótesis Validadas → Escenarios → Predicciones
    """

    def __init__(self, event_bus: EventBus, reasoning_cycle: ReasoningCycle, simulador_escenarios: Any = None) -> None:
        self.bus = event_bus
        self.reasoning = reasoning_cycle
        self.scenarios_history: Deque[Dict[str, Any]] = deque(maxlen=2_000)
        self.predictions_history: Deque[Dict[str, Any]] = deque(maxlen=2_000)
        self._mc_running = False
        self.simulador_escenarios = simulador_escenarios

    async def run(self) -> CycleResult:
        t0 = time.time()
        logger.info("[ForecastCycle] Iniciando generación de escenarios...")

        validated = [v for v in self.reasoning.validation_history if v.get("passed")]
        if not validated:
            logger.warning("[ForecastCycle] No hay hipótesis validadas; ciclo vacío.")
            return {
                "escenarios_generados": 0,
                "predicciones_creadas": 0,
                "probabilidades": {},
                "nota": "Sin hipótesis validadas para procesar",
            }

        scenarios = await self._generate_scenarios(validated)
        predictions = await self._create_predictions(scenarios)

        elapsed = time.time() - t0

        for sc in scenarios:
            await self.bus.publish(EventType.NEW_SCENARIO.value, {"scenario": sc, "eps": calcular_eps(sc)})
        for pred in predictions:
            await self.bus.publish(EventType.NEW_PREDICTION.value, {"prediction": pred, "eps": calcular_eps(pred)})

        return {
            "escenarios_generados": len(scenarios),
            "predicciones_creadas": len(predictions),
            "probabilidades": {p["id"]: p.get("probability", 0) for p in predictions},
            "tiempo_ejecucion": round(elapsed, 3),
            "hipotesis_usadas": len(validated),
        }

    async def _generate_scenarios(self, validated: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if self.simulador_escenarios is not None and _SIMULATOR_AVAILABLE:
            try:
                scenarios = []
                for val in validated:
                    try:
                        from analysis.scenario_simulator import Hipotesis as SSHipotesis
                        ssh = SSHipotesis(id=val["id"], descripcion=val.get("hypothesis_text", val.get("text", "")), probabilidad_base=val.get("consensus", 50) / 100.0)
                        resultados = await asyncio.get_event_loop().run_in_executor(
                            None, self.simulador_escenarios.generar_escenarios_contrafactuales, ssh
                        )
                        for r in resultados[:3]:
                            scenario = {
                                "id": getattr(r, "id", f"sc_{uuid.uuid4().hex[:8]}"),
                                "hypothesis_id": val["id"],
                                "description": getattr(r, "descripcion", str(r)),
                                "base_probability": getattr(r, "probabilidad_base", 0.5),
                                "monte_carlo_mean": getattr(r, "probabilidad_ajustada", 0.5),
                                "variance": 0.01,
                                "simulations": 100,
                                "confidence_band": (0.0, 1.0),
                                "timestamp": _ts_now(),
                            }
                            scenarios.append(scenario)
                            self.scenarios_history.append(scenario)
                    except Exception as inner_e:
                        logger.warning("[ForecastCycle] Simulacion individual fallo: %s", inner_e)
                if scenarios:
                    return scenarios
            except Exception as e:
                logger.warning("[ForecastCycle] SimuladorEscenarios fallo, usando stub: %s", e)

        if self._mc_running:
            logger.warning("[ForecastCycle] Monte Carlo ya en ejecución; saltando.")
            return []
        self._mc_running = True
        try:
            await asyncio.sleep(0.08)
            scenarios = []
            for val in validated[:5]:
                base_prob = val.get("consensus", 50) / 100.0
                n_simulations = 1_000
                outcomes = []
                for _ in range(n_simulations):
                    outcome = random.gauss(base_prob, 0.15)
                    outcomes.append(max(0.0, min(1.0, outcome)))
                mean_prob = sum(outcomes) / len(outcomes)
                variance = sum((o - mean_prob) ** 2 for o in outcomes) / len(outcomes)
                scenario = {
                    "id": f"sc_{uuid.uuid4().hex[:8]}",
                    "hypothesis_id": val["id"],
                    "description": f"Escenario derivado de: {val['hypothesis_text'][:100]}",
                    "base_probability": round(base_prob, 3),
                    "monte_carlo_mean": round(mean_prob, 3),
                    "variance": round(variance, 5),
                    "simulations": n_simulations,
                    "confidence_band": (
                        round(max(0.0, mean_prob - 2 * (variance ** 0.5)), 3),
                        round(min(1.0, mean_prob + 2 * (variance ** 0.5)), 3),
                    ),
                    "timestamp": _ts_now(),
                    "urgency": val.get("confidence", 50),
                    "confidence": val.get("confidence", 50),
                    "impact": 70,
                }
                scenarios.append(scenario)
                self.scenarios_history.append(scenario)
            return scenarios
        finally:
            self._mc_running = False

    async def _create_predictions(self, scenarios: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        await asyncio.sleep(0.04)
        predictions = []
        for sc in scenarios:
            k = 10_000
            yes_shares = max(1, int(sc["monte_carlo_mean"] * 1000))
            no_shares = max(1, 1000 - yes_shares)
            price_yes = k / (yes_shares + no_shares)
            pred = {
                "id": f"pred_{uuid.uuid4().hex[:8]}",
                "scenario_id": sc["id"],
                "probability": round(sc["monte_carlo_mean"], 3),
                "price_yes": round(price_yes, 4),
                "market_liquidity": k,
                "yes_shares": yes_shares,
                "no_shares": no_shares,
                "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
                "timestamp": _ts_now(),
                "confidence": sc.get("confidence", 50),
                "urgency": sc.get("urgency", 50),
                "impact": sc.get("impact", 50),
            }
            predictions.append(pred)
            self.predictions_history.append(pred)
        return predictions


# ---------------------------------------------------------------------------

class ExecutiveCycle:
    """
    Ciclo Ejecutivo: Priorizar → Explicar → Recomendar
    """

    REC_MONITOR = "MONITORIZAR"
    REC_INVESTIGATE = "INVESTIGAR"
    REC_PREPARE = "PREPARAR"
    REC_ACT = "ACTUAR"

    def __init__(self, event_bus: EventBus, reasoning: ReasoningCycle, forecast: ForecastCycle) -> None:
        self.bus = event_bus
        self.reasoning = reasoning
        self.forecast = forecast
        self.alerts_history: Deque[Dict[str, Any]] = deque(maxlen=2_000)

    async def run(self) -> CycleResult:
        t0 = time.time()
        logger.info("[ExecutiveCycle] Iniciando priorización ejecutiva...")

        findings = self._collect_findings()
        prioritized = self._prioritize(findings)
        explanations = self._explain(prioritized)
        recommendations = self._recommend(prioritized)

        elapsed = time.time() - t0

        for item in prioritized[:10]:
            alert = {
                "id": f"alert_{uuid.uuid4().hex[:8]}",
                "finding": item,
                "explanation": explanations.get(item["id"], ""),
                "recommendation": recommendations.get(item["id"], self.REC_MONITOR),
                "priority_score": item.get("eps", 0),
                "timestamp": _ts_now(),
            }
            self.alerts_history.append(alert)
            await self.bus.publish(EventType.NEW_ALERT.value, alert)
            await self.bus.publish(
                EventType.RECOMMENDATION_ISSUED.value,
                {"alert_id": alert["id"], "recommendation": alert["recommendation"], "reason": alert["explanation"]},
            )

        return {
            "prioridades": [
                {"id": p["id"], "eps": p.get("eps", 0), "type": p["type"]}
                for p in prioritized[:10]
            ],
            "explicaciones": {k: v for k, v in list(explanations.items())[:5]},
            "recomendaciones": {k: v for k, v in list(recommendations.items())[:5]},
            "total_findings": len(findings),
            "tiempo_ejecucion": round(elapsed, 3),
        }

    def _collect_findings(self) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        for v in self.reasoning.validation_history:
            if v.get("passed"):
                findings.append({
                    "id": v["id"],
                    "type": "validated_hypothesis",
                    "text": v.get("hypothesis_text", ""),
                    "confidence": v.get("consensus", 0),
                    "urgency": v.get("confidence", 50),
                    "impact": 60,
                })
        for p in self.forecast.predictions_history:
            findings.append({
                "id": p["id"],
                "type": "prediction",
                "text": f"Predicción con probabilidad {p.get('probability', 0)}",
                "confidence": p.get("confidence", 0),
                "urgency": p.get("urgency", 50),
                "impact": p.get("impact", 50),
            })
        for f in findings:
            f["eps"] = calcular_eps(f)
        return findings

    def _prioritize(self, findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return priorizar_eventos(findings)

    def _explain(self, prioritized: List[Dict[str, Any]]) -> Dict[str, str]:
        explanations = {}
        for item in prioritized:
            parts = []
            conf = item.get("confidence", 50)
            if conf >= 80:
                parts.append(f"Alta confianza ({conf}%): evidencia robusta.")
            elif conf >= 50:
                parts.append(f"Confianza moderada ({conf}%): evidencia incipiente.")
            else:
                parts.append(f"Baja confianza ({conf}%): evidencia preliminar.")
            item_type = item.get("type", "")
            if "hypothesis" in item_type:
                parts.append("Hipótesis validada por revisión científica y escéptica.")
            elif "prediction" in item_type:
                parts.append("Predicción derivada de simulación Monte Carlo con bandas de confianza.")
            eps = item.get("eps", 0)
            if eps >= 80:
                parts.append("EPS CRÍTICO: requiere atención inmediata.")
            elif eps >= 60:
                parts.append("EPS ELEVADO: monitoreo prioritario recomendado.")
            explanations[item["id"]] = " ".join(parts)
        return explanations

    def _recommend(self, prioritized: List[Dict[str, Any]]) -> Dict[str, str]:
        recommendations = {}
        for item in prioritized:
            eps = item.get("eps", 0)
            conf = item.get("confidence", 50)
            if eps >= 80 and conf >= 70:
                rec = self.REC_ACT
            elif eps >= 60:
                rec = self.REC_PREPARE
            elif eps >= 40:
                rec = self.REC_INVESTIGATE
            else:
                rec = self.REC_MONITOR
            recommendations[item["id"]] = rec
        return recommendations


# ---------------------------------------------------------------------------

class OperationsCycle:
    """
    Ciclo de Operaciones: Logs → Métricas → Backups → Integridad
    """

    def __init__(self, event_bus: EventBus) -> None:
        self.bus = event_bus
        self._cycle_logs: Deque[Dict[str, Any]] = deque(maxlen=5_000)
        self._metrics_history: Deque[Dict[str, Any]] = deque(maxlen=1_000)
        self._backup_counter = 0
        self._last_backup_time: Optional[float] = None
        self._db_integrity_checks: Deque[Dict[str, Any]] = deque(maxlen=500)

    async def run(self) -> CycleResult:
        t0 = time.time()
        logger.info("[OperationsCycle] Iniciando recolección operativa...")

        logs_summary = self._collect_logs()
        metrics = self._compute_metrics()
        backup_result = await self._maybe_backup()
        integrity = await self._check_integrity()

        elapsed = time.time() - t0

        await self.bus.publish(
            EventType.CYCLE_COMPLETED.value,
            {"cycle": "operations", "metrics_summary": metrics, "backup_done": backup_result["performed"], "integrity_ok": integrity["ok"]},
        )
        await self.bus.publish(
            EventType.HEALTH_STATUS.value,
            {"metrics": metrics, "integrity": integrity, "timestamp": _ts_now()},
        )

        return {
            "metricas": metrics,
            "estado_backups": backup_result,
            "integridad_ok": integrity["ok"],
            "detalles_integridad": integrity,
            "tiempo_ejecucion": round(elapsed, 3),
        }

    def _collect_logs(self) -> Dict[str, int]:
        return {"info_count": 0, "warning_count": 0, "error_count": 0}

    def _compute_metrics(self) -> Dict[str, Any]:
        now = time.time()
        # Intentar obtener metricas reales del sistema via psutil
        try:
            import psutil
            cpu_percent = round(psutil.cpu_percent(interval=0.1), 1)
            memory_percent = round(psutil.virtual_memory().percent, 1)
        except ImportError:
            cpu_percent = None
            memory_percent = None
        metrics = {
            "timestamp": _ts_now(),
            "cpu_percent": cpu_percent,
            "memory_percent": memory_percent,
            "db_size_mb": self._get_db_size(),
            "uptime_seconds": now - getattr(self, '_startup_time', now),
            "events_processed": 0,
            "overall_health": "healthy",
        }
        if memory_percent is not None and cpu_percent is not None:
            if memory_percent > 85 or cpu_percent > 90:
                metrics["overall_health"] = "stressed"
            if memory_percent > 95 or cpu_percent > 95:
                metrics["overall_health"] = "critical"
        self._metrics_history.append(metrics)
        return metrics

    def _get_db_size(self) -> float:
        try:
            if DB_PATH.exists():
                return round(DB_PATH.stat().st_size / (1024 * 1024), 2)
        except Exception as e:
            logger.warning("[VEOCore] Error al obtener tamano DB: %s", e)
        return 0.0

    async def _maybe_backup(self) -> Dict[str, Any]:
        now = time.time()
        backup_interval = 3600 * 6
        if self._last_backup_time and (now - self._last_backup_time) < backup_interval:
            return {"performed": False, "reason": "Intervalo no alcanzado"}
        self._backup_counter += 1
        backup_dir = V2_ROOT / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_file = backup_dir / f"veo_backup_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.db"
        try:
            if DB_PATH.exists():
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, shutil.copy2, str(DB_PATH), str(backup_file))
                self._last_backup_time = now
                backups = sorted(backup_dir.glob("veo_backup_*.db"), key=lambda p: p.stat().st_mtime)
                for old in backups[:-10]:
                    old.unlink(missing_ok=True)
                return {
                    "performed": True,
                    "file": str(backup_file),
                    "size_mb": round(backup_file.stat().st_size / (1024 * 1024), 2) if backup_file.exists() else 0,
                    "backup_number": self._backup_counter,
                }
        except Exception as exc:
            return {"performed": False, "error": str(exc)}
        return {"performed": False, "reason": "No DB file"}

    async def _check_integrity(self) -> Dict[str, Any]:
        result = {"ok": True, "checks": [], "timestamp": _ts_now()}
        if not DB_PATH.exists():
            result["ok"] = True
            result["checks"].append("No DB yet -- nothing to check.")
            return result
        try:
            conn = sqlite3.connect(str(DB_PATH), timeout=5.0)
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check;")
            integrity = cursor.fetchone()
            conn.close()
            ok = integrity is not None and integrity[0] == "ok"
            result["ok"] = ok
            result["checks"].append(f"PRAGMA integrity_check: {integrity[0] if integrity else 'NULL'}")
        except Exception as exc:
            result["ok"] = False
            result["checks"].append(f"Integrity check exception: {exc}")
        self._db_integrity_checks.append(result)
        return result



# ============================================================================
# 4. RESOURCE MANAGER
# ============================================================================

class ResourceManager:
    """
    Gestiona recursos computacionales para prevenir sobrecarga.
    """

    COST_ESTIMATES: Dict[str, Dict[str, Any]] = {
        "reasoning": {"cpu": 30, "memory": 20, "io": 40, "singleton": False},
        "forecast": {"cpu": 70, "memory": 50, "io": 30, "singleton": True},
        "executive": {"cpu": 15, "memory": 10, "io": 10, "singleton": False},
        "operations": {"cpu": 10, "memory": 10, "io": 60, "singleton": False},
        "signal_scan": {"cpu": 25, "memory": 15, "io": 50, "singleton": False},
        "monte_carlo": {"cpu": 85, "memory": 60, "io": 20, "singleton": True},
    }

    CPU_THRESHOLD = 80
    MEMORY_THRESHOLD = 80

    def __init__(self, event_bus: EventBus) -> None:
        self.bus = event_bus
        self._running_tasks: Dict[str, Set[str]] = defaultdict(set)
        self._task_start_times: Dict[str, float] = {}
        self._lock = asyncio.Lock()

    def estimate_cost(self, task_type: str) -> Dict[str, int]:
        est = self.COST_ESTIMATES.get(task_type, {})
        return {
            "cpu": est.get("cpu", 50),
            "memory": est.get("memory", 30),
            "io": est.get("io", 30),
            "singleton": est.get("singleton", False),
        }

    async def can_execute(self, task_type: str) -> Tuple[bool, str]:
        cost = self.estimate_cost(task_type)
        async with self._lock:
            if cost.get("singleton") and self._running_tasks.get(task_type):
                return False, f"Task '{task_type}' is singleton and already running"
            total_cpu = sum(
                self.COST_ESTIMATES.get(tt, {}).get("cpu", 0)
                for tt, ids in self._running_tasks.items() for _ in ids
            )
            total_mem = sum(
                self.COST_ESTIMATES.get(tt, {}).get("memory", 0)
                for tt, ids in self._running_tasks.items() for _ in ids
            )
            if total_cpu + cost["cpu"] > self.CPU_THRESHOLD:
                return False, f"CPU overload: {total_cpu}% + {cost['cpu']}% > {self.CPU_THRESHOLD}%"
            if total_mem + cost["memory"] > self.MEMORY_THRESHOLD:
                return False, f"Memory overload: {total_mem}% + {cost['memory']}% > {self.MEMORY_THRESHOLD}%"
        return True, "Resources available"

    async def register_task(self, task_type: str, task_id: str) -> None:
        async with self._lock:
            self._running_tasks[task_type].add(task_id)
            self._task_start_times[task_id] = time.time()

    async def unregister_task(self, task_type: str, task_id: str) -> None:
        async with self._lock:
            self._running_tasks[task_type].discard(task_id)
            self._task_start_times.pop(task_id, None)

    def get_running(self) -> Dict[str, List[str]]:
        return {k: list(v) for k, v in self._running_tasks.items() if v}

    def get_utilization(self) -> Dict[str, float]:
        cpu = sum(
            self.COST_ESTIMATES.get(tt, {}).get("cpu", 0)
            for tt, ids in self._running_tasks.items() for _ in ids
        )
        mem = sum(
            self.COST_ESTIMATES.get(tt, {}).get("memory", 0)
            for tt, ids in self._running_tasks.items() for _ in ids
        )
        return {"cpu": min(cpu, 100.0), "memory": min(mem, 100.0)}


# ============================================================================
# 5. CONFLICT RESOLVER
# ============================================================================

class ConflictResolver:
    """
    Resuelve discrepancias entre motores.
    """

    DISCREPANCY_THRESHOLD = 25

    def __init__(self, event_bus: EventBus) -> None:
        self.bus = event_bus
        self._conflict_history: Deque[Dict[str, Any]] = deque(maxlen=1_000)

    async def resolve(
        self,
        module_a: str,
        score_a: float,
        module_b: str,
        score_b: float,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        discrepancy = abs(score_a - score_b)
        consensus = (score_a + score_b) / 2.0
        result = {
            "id": f"conflict_{uuid.uuid4().hex[:8]}",
            "module_a": module_a,
            "score_a": round(score_a, 2),
            "module_b": module_b,
            "score_b": round(score_b, 2),
            "discrepancy": round(discrepancy, 2),
            "consensus": round(consensus, 2),
            "resolution_strategy": None,
            "requires_human_review": False,
            "timestamp": _ts_now(),
            "context": context or {},
        }
        if discrepancy < self.DISCREPANCY_THRESHOLD:
            result["resolution_strategy"] = "consensus_average"
            result["resolved_score"] = round(consensus, 2)
            logger.info("[ConflictResolver] Consenso %s (%.1f) vs %s (%.1f) → %.1f",
                        module_a, score_a, module_b, score_b, consensus)
        else:
            result["resolution_strategy"] = "human_review_required"
            result["requires_human_review"] = True
            result["resolved_score"] = None
            await self.bus.publish(
                EventType.CONFLICT_DETECTED.value,
                {
                    "conflict_id": result["id"],
                    "module_a": module_a, "score_a": score_a,
                    "module_b": module_b, "score_b": score_b,
                    "discrepancy": discrepancy, "consensus": consensus,
                    "eps": min(100, int(discrepancy)),
                },
            )
            logger.warning("[ConflictResolver] CONFLICTO: %s (%.1f) vs %s (%.1f) Δ=%.1f",
                           module_a, score_a, module_b, score_b, discrepancy)
        self._conflict_history.append(result)
        return result

    def get_conflict_stats(self) -> Dict[str, Any]:
        total = len(self._conflict_history)
        if total == 0:
            return {"total": 0, "requiring_human": 0, "auto_resolved": 0}
        requiring_human = sum(1 for c in self._conflict_history if c.get("requires_human_review"))
        return {
            "total": total,
            "requiring_human": requiring_human,
            "auto_resolved": total - requiring_human,
            "avg_discrepancy": round(sum(c["discrepancy"] for c in self._conflict_history) / total, 2),
        }


# ============================================================================
# 6. TRUST LAYER
# ============================================================================

class TrustLayer:
    """
    Capa de confianza: trackea fiabilidad histórica de cada fuente/módulo.
    """

    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trust_scores (
                module TEXT PRIMARY KEY,
                total_predictions INTEGER DEFAULT 0,
                correct_predictions INTEGER DEFAULT 0,
                avg_confidence REAL DEFAULT 50.0,
                last_updated TEXT
            )
        """)
        conn.commit()
        conn.close()
        logger.info("TrustLayer initialized")

    async def get_trust(self, module: str) -> Dict[str, Any]:
        if module in self._cache:
            return self._cache[module]
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT total_predictions, correct_predictions, avg_confidence FROM trust_scores WHERE module=?",
            (module,),
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            total, correct, avg_conf = row
            trust_score = (correct / max(total, 1)) * 100
            result = {
                "module": module,
                "total_predictions": total,
                "correct_predictions": correct,
                "accuracy": round(trust_score, 2),
                "avg_confidence": round(avg_conf, 2),
            }
        else:
            result = {
                "module": module,
                "total_predictions": 0,
                "correct_predictions": 0,
                "accuracy": 50.0,
                "avg_confidence": 50.0,
            }
        self._cache[module] = result
        return result

    async def record_prediction(self, module: str, predicted: bool, actual: bool, confidence: float) -> None:
        async with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO trust_scores (module, total_predictions, correct_predictions, avg_confidence, last_updated)
                VALUES (?, 1, ?, ?, ?)
                ON CONFLICT(module) DO UPDATE SET
                    total_predictions = total_predictions + 1,
                    correct_predictions = correct_predictions + excluded.correct_predictions,
                    avg_confidence = (avg_confidence * total_predictions + excluded.avg_confidence) / (total_predictions + 1),
                    last_updated = excluded.last_updated
            """, (module, 1 if predicted == actual else 0, confidence, _ts_now()))
            conn.commit()
            conn.close()
            self._cache.pop(module, None)

    async def adjust_score(self, module: str, raw_score: float) -> float:
        trust = await self.get_trust(module)
        accuracy = trust.get("accuracy", 50.0) / 100.0
        adjusted = raw_score * (0.7 + 0.3 * accuracy)
        return round(min(max(adjusted, 0), 100), 2)


# ============================================================================
# 7. HEALTH MONITOR
# ============================================================================

class HealthMonitor:
    """
    Monitorea la salud del sistema en tiempo real.
    """

    def __init__(self, event_bus: EventBus) -> None:
        self.bus = event_bus
        self._checks: Dict[str, Callable[[], Awaitable[Dict[str, Any]]]] = {}
        self._history: Deque[Dict[str, Any]] = deque(maxlen=500)
        self._healthy = True

    def register_check(self, name: str, check_fn: Callable[[], Awaitable[Dict[str, Any]]]) -> None:
        self._checks[name] = check_fn

    async def check(self) -> Dict[str, Any]:
        results = {}
        overall = "healthy"
        for name, check_fn in self._checks.items():
            try:
                result = await check_fn()
                results[name] = result
                if result.get("status") == "error":
                    overall = "degraded" if overall == "healthy" else "critical"
            except Exception as exc:
                results[name] = {"status": "error", "error": str(exc)}
                overall = "degraded" if overall == "healthy" else "critical"
        report = {"timestamp": _ts_now(), "overall": overall, "checks": results}
        self._history.append(report)
        self._healthy = overall == "healthy"
        return report

    def is_healthy(self) -> bool:
        return self._healthy

    def get_history(self, n: int = 10) -> List[Dict[str, Any]]:
        return list(self._history)[-n:]


# ============================================================================
# 8. AUDIT LOG
# ============================================================================

class AuditLog:
    """
    Registro de auditoría inmutable.
    """

    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path

    async def initialize(self) -> None:
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                action TEXT NOT NULL,
                actor TEXT NOT NULL,
                details TEXT,
                hash TEXT UNIQUE
            )
        """)
        conn.commit()
        conn.close()
        logger.info("AuditLog initialized")

    async def log(self, action: str, actor: str = "system", details: Optional[Dict[str, Any]] = None) -> None:
        ts = _ts_now()
        payload = {"timestamp": ts, "action": action, "actor": actor, "details": details or {}}
        entry_hash = _dict_hash(payload)
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                "INSERT INTO audit_log (timestamp, action, actor, details, hash) VALUES (?, ?, ?, ?, ?)",
                (ts, action, actor, json.dumps(details or {}, ensure_ascii=False), entry_hash),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            pass
        finally:
            conn.close()

    async def query(
        self, action: Optional[str] = None, actor: Optional[str] = None,
        since: Optional[str] = None, limit: int = 100,
    ) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        query_str = "SELECT timestamp, action, actor, details FROM audit_log WHERE 1=1"
        params: List[Any] = []
        if action:
            query_str += " AND action=?"
            params.append(action)
        if actor:
            query_str += " AND actor=?"
            params.append(actor)
        if since:
            query_str += " AND timestamp>=?"
            params.append(since)
        query_str += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        cursor.execute(query_str, params)
        rows = cursor.fetchall()
        conn.close()
        return [{"timestamp": r[0], "action": r[1], "actor": r[2], "details": r[3]} for r in rows]



# ============================================================================
# 9. VEO CORE (clase principal orquestadora)
# ============================================================================

class VEOCore:
    """
    ╔══════════════════════════════════════════════════════════════════════════╗
    ║                         V E O   C O R E   v2                           ║
    ║              Cerebro Central - Orquestador de Narrativas               ║
    ╚══════════════════════════════════════════════════════════════════════════╝

    Integra: EventBus, Scheduler, 4 Ciclos, ResourceManager, ConflictResolver,
    TrustLayer, HealthMonitor, AuditLog.
    """

    DEFAULT_INTERVALS = {
        "signal_scan": 3600,         # 1 hora
        "narrative_analysis": 86400,  # 1 día
        "megatrend_review": 604800,   # 1 semana
        "forecast_audit": 2592000,    # 1 mes
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = config or {}
        self._running = False
        self._startup_time = time.time()

        # Subsistemas core
        self.bus = EventBus()
        self.scheduler = Scheduler(self.bus)
        self.resources = ResourceManager(self.bus)
        self.conflicts = ConflictResolver(self.bus)

        # Capas operativas
        self.trust = TrustLayer()
        self.health = HealthMonitor(self.bus)
        self.audit = AuditLog()

        # Motores de analisis (opcionales, graceful fallback)
        motor_hipotesis = MotorHipotesis() if _HYPOTHESIS_AVAILABLE else None
        coordinador_validacion = CoordinadorValidacion() if _SCIENTIFIC_AVAILABLE else None
        simulador_escenarios = SimuladorEscenarios() if _SIMULATOR_AVAILABLE else None
        motor_causal = MotorCausal() if _CAUSAL_AVAILABLE else None

        # Ciclos
        self.reasoning = ReasoningCycle(self.bus, motor_hipotesis, coordinador_validacion, motor_causal)
        self.forecast = ForecastCycle(self.bus, self.reasoning, simulador_escenarios)
        self.executive = ExecutiveCycle(self.bus, self.reasoning, self.forecast)
        self.operations = OperationsCycle(self.bus)

        # IDs de tareas
        self._task_ids: Dict[str, str] = {}

        # Estado interno
        self._cycle_results: Dict[str, Deque[CycleResult]] = {
            "reasoning": deque(maxlen=100),
            "forecast": deque(maxlen=100),
            "executive": deque(maxlen=100),
            "operations": deque(maxlen=100),
            "planetary": deque(maxlen=100),
        }
        self._explain_cache: Dict[str, Dict[str, Any]] = {}
        self._last_planetary_results: Optional[Dict[str, Any]] = None

    # -- Lifecycle --

    async def start(self) -> None:
        if self._running:
            logger.warning("VEOCore ya está en ejecución")
            return
        self._running = True
        logger.info("╔══════════════════════════════════════════╗")
        logger.info("║     V E O   C O R E   v2  STARTING       ║")
        logger.info("╚══════════════════════════════════════════╝")

        await self.trust.initialize()
        await self.audit.initialize()
        self._register_health_checks()
        await self.bus.start()
        await self._register_cycles()
        await self.scheduler.start()
        await self.audit.log("veo_core_start", actor="system", details={"ts": _ts_now()})
        logger.info("VEOCore started successfully | tasks=%d", len(self._task_ids))

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        logger.info("VEOCore stopping...")
        await self.scheduler.stop()
        await self.bus.stop()
        await self.audit.log("veo_core_stop", actor="system", details={"ts": _ts_now()})
        logger.info("VEOCore stopped gracefully")

    # -- Registro de ciclos --

    async def _register_cycles(self) -> None:
        intervals = {**self.DEFAULT_INTERVALS, **self.config.get("intervals", {})}

        self._task_ids["signal_scan"] = self.scheduler.schedule(
            cycle_type="signal_scan",
            interval_seconds=intervals["signal_scan"],
            priority=70,
            coro_factory=self._wrap_reasoning(),
        )
        self._task_ids["narrative_analysis"] = self.scheduler.schedule(
            cycle_type="narrative_analysis",
            interval_seconds=intervals["narrative_analysis"],
            priority=60,
            coro_factory=self._wrap_executive(),
        )
        self._task_ids["megatrend_review"] = self.scheduler.schedule(
            cycle_type="megatrend_review",
            interval_seconds=intervals["megatrend_review"],
            priority=50,
            coro_factory=self._wrap_forecast(),
        )
        self._task_ids["forecast_audit"] = self.scheduler.schedule(
            cycle_type="forecast_audit",
            interval_seconds=intervals["forecast_audit"],
            priority=40,
            coro_factory=self._wrap_operations(),
        )

        # Planetary Diagnosis Cycle - cada 20 min (1200s) por defecto
        planetary_interval = self.config.get("planetary_interval_seconds", 1200)
        self._task_ids["planetary_diagnosis"] = self.scheduler.schedule(
            cycle_type="planetary_diagnosis",
            interval_seconds=planetary_interval,
            priority=35,
            coro_factory=self._wrap_planetary(),
        )

        self.bus.subscribe(EventType.NEW_ALERT.value, self._on_alert)
        self.bus.subscribe(EventType.CONFLICT_DETECTED.value, self._on_conflict)

    def _wrap_reasoning(self) -> Callable[[], Coroutine[Any, Any, CycleResult]]:
        async def _run() -> CycleResult:
            task_id = f"reasoning_{uuid.uuid4().hex[:6]}"
            can, reason = await self.resources.can_execute("reasoning")
            if not can:
                logger.warning("[VEOCore] reasoning bloqueado: %s", reason)
                return {"status": "blocked", "reason": reason}
            await self.resources.register_task("reasoning", task_id)
            try:
                result = await self.reasoning.run()
                self._cycle_results["reasoning"].append(result)
                return result
            finally:
                await self.resources.unregister_task("reasoning", task_id)
        return _run

    def _wrap_forecast(self) -> Callable[[], Coroutine[Any, Any, CycleResult]]:
        async def _run() -> CycleResult:
            task_id = f"forecast_{uuid.uuid4().hex[:6]}"
            can, reason = await self.resources.can_execute("forecast")
            if not can:
                logger.warning("[VEOCore] forecast bloqueado: %s", reason)
                return {"status": "blocked", "reason": reason}
            await self.resources.register_task("forecast", task_id)
            try:
                result = await self.forecast.run()
                self._cycle_results["forecast"].append(result)
                return result
            finally:
                await self.resources.unregister_task("forecast", task_id)
        return _run

    def _wrap_executive(self) -> Callable[[], Coroutine[Any, Any, CycleResult]]:
        async def _run() -> CycleResult:
            task_id = f"executive_{uuid.uuid4().hex[:6]}"
            can, reason = await self.resources.can_execute("executive")
            if not can:
                logger.warning("[VEOCore] executive bloqueado: %s", reason)
                return {"status": "blocked", "reason": reason}
            await self.resources.register_task("executive", task_id)
            try:
                result = await self.executive.run()
                self._cycle_results["executive"].append(result)
                return result
            finally:
                await self.resources.unregister_task("executive", task_id)
        return _run

    def _wrap_operations(self) -> Callable[[], Coroutine[Any, Any, CycleResult]]:
        async def _run() -> CycleResult:
            task_id = f"operations_{uuid.uuid4().hex[:6]}"
            can, reason = await self.resources.can_execute("operations")
            if not can:
                logger.warning("[VEOCore] operations bloqueado: %s", reason)
                return {"status": "blocked", "reason": reason}
            await self.resources.register_task("operations", task_id)
            try:
                result = await self.operations.run()
                self._cycle_results["operations"].append(result)
                return result
            finally:
                await self.resources.unregister_task("operations", task_id)
        return _run

    def _wrap_planetary(self) -> Callable[[], Coroutine[Any, Any, CycleResult]]:
        async def _run() -> CycleResult:
            task_id = f"planetary_{uuid.uuid4().hex[:6]}"
            can, reason = await self.resources.can_execute("planetary")
            if not can:
                logger.warning("[VEOCore] planetary bloqueado: %s", reason)
                return {"status": "blocked", "reason": reason}
            await self.resources.register_task("planetary", task_id)
            try:
                result = await self.planetary_diagnosis_cycle()
                self._cycle_results["planetary"].append(result)
                return result
            finally:
                await self.resources.unregister_task("planetary", task_id)
        return _run

    async def planetary_diagnosis_cycle(self) -> Dict[str, Any]:
        """
        Ciclo de Diagnóstico Planetario.

        1. Convierte eventos internos a PlanetaryEvent
        2. Ejecuta PlanetaryDiagnosisEngine con todas las configuraciones
        3. Publica resultados al EventBus
        4. Devuelve el dict de resultados
        """
        t0 = time.time()
        logger.info("[PlanetaryCycle] Iniciando diagnostico planetario...")

        if not _PLANETARY_AVAILABLE:
            logger.warning("[PlanetaryCycle] Modulos planetary no disponibles")
            result = {
                "status": "unavailable",
                "message": "Planetary Engine no instalado",
                "configs_evaluated": 0,
                "timestamp": _ts_now(),
            }
            self._last_planetary_results = result
            return result

        try:
            # 1. Convertir eventos internos a PlanetaryEvent
            events = self._build_planetary_events()

            # 2. Ejecutar motor
            engine = PlanetaryDiagnosisEngine()
            configs_list = list(PLANETARY_CONFIGS.values())
            results = engine.run_all_configs(configs_list, events)

            elapsed = time.time() - t0

            # 3. Publicar resultados al EventBus
            summary = results.get("summary", {})
            await self.bus.publish(
                "PLANETARY_DIAGNOSIS_COMPLETED",
                {
                    "configs_evaluated": len(configs_list),
                    "events_processed": len(events),
                    "elapsed_seconds": round(elapsed, 3),
                    "summary": summary,
                    "timestamp": _ts_now(),
                },
            )

            # 4. Construir resultado final
            result = {
                "status": "ok",
                "configs_evaluated": len(configs_list),
                "events_processed": len(events),
                "elapsed_seconds": round(elapsed, 3),
                "results": results,
                "summary": summary,
                "timestamp": _ts_now(),
            }
            self._last_planetary_results = result

            logger.info(
                "[PlanetaryCycle] Diagnostico completado: %d configs, %d events en %.3fs",
                len(configs_list), len(events), elapsed,
            )
            return result

        except Exception as exc:
            elapsed = time.time() - t0
            logger.error("[PlanetaryCycle] Error: %s", exc, exc_info=True)
            result = {
                "status": "error",
                "message": str(exc),
                "elapsed_seconds": round(elapsed, 3),
                "timestamp": _ts_now(),
            }
            self._last_planetary_results = result
            return result

    def _build_planetary_events(self) -> list:
        """Convierte eventos internos del VEOCore a PlanetaryEvent."""
        events = []
        if PlanetaryEvent is None:
            return events

        # Convertir hipótesis validadas
        for v in self.reasoning.validation_history:
            if v.get("passed"):
                events.append(PlanetaryEvent(
                    event_id=f"val_{v.get('id', 'unknown')}",
                    persistence=min(v.get("confidence", 50) / 100.0, 0.99),
                    relevance=min(v.get("consensus", 50) / 100.0, 0.99),
                    coherence=0.7,
                    timestamp=v.get("timestamp", _ts_now()),
                ))

        # Convertir predicciones
        for p in self.forecast.predictions_history:
            events.append(PlanetaryEvent(
                event_id=f"pred_{p.get('id', 'unknown')}",
                persistence=p.get("probability", 0.5),
                relevance=min(p.get("confidence", 50) / 100.0, 0.99),
                coherence=0.6,
                timestamp=p.get("timestamp", _ts_now()),
            ))

        # Convertir alertas
        for a in self.executive.alerts_history:
            finding = a.get("finding", {})
            events.append(PlanetaryEvent(
                event_id=f"alert_{a.get('id', 'unknown')}",
                persistence=min(finding.get("confidence", 50) / 100.0, 0.99),
                relevance=min(a.get("priority_score", 50) / 100.0, 0.99),
                coherence=0.5,
                timestamp=a.get("timestamp", _ts_now()),
            ))

        # Si no hay eventos, crear uno dummy para que el motor funcione
        if not events:
            events.append(PlanetaryEvent(
                event_id="dummy_system_pulse",
                persistence=0.5,
                relevance=0.5,
                coherence=0.5,
                timestamp=_ts_now(),
            ))

        return events

    # -- Event handlers --

    async def _on_alert(self, event_type: str, envelope: Dict[str, Any]) -> None:
        payload = envelope.get("payload", {})
        alert_id = payload.get("id", "")
        if alert_id:
            self._explain_cache[alert_id] = payload

    async def _on_conflict(self, event_type: str, envelope: Dict[str, Any]) -> None:
        payload = envelope.get("payload", {})
        logger.info("Conflict event: %s vs %s (delta=%.1f)",
                    payload.get("module_a"), payload.get("module_b"),
                    payload.get("discrepancy", 0))

    # -- Health checks --

    def _register_health_checks(self) -> None:
        self.health.register_check("bus", self._check_bus_health)
        self.health.register_check("scheduler", self._check_scheduler_health)
        self.health.register_check("resources", self._check_resources_health)
        self.health.register_check("database", self._check_db_health)

    async def _check_bus_health(self) -> Dict[str, Any]:
        stats = self.bus.get_stats()
        return {"status": "ok" if stats.get("running") else "error",
                "queue_size": stats.get("queue_size", 0),
                "subscribers": len(stats.get("subscriber_types", []))}

    async def _check_scheduler_health(self) -> Dict[str, Any]:
        status = self.scheduler.get_queue_status()
        return {"status": "ok", "registered_tasks": status.get("registered_tasks", 0)}

    async def _check_resources_health(self) -> Dict[str, Any]:
        util = self.resources.get_utilization()
        status = "ok"
        if util["cpu"] > 80 or util["memory"] > 80:
            status = "warning"
        return {"status": status, "utilization": util}

    async def _check_db_health(self) -> Dict[str, Any]:
        if not DB_PATH.exists():
            return {"status": "ok", "exists": False}
        try:
            conn = sqlite3.connect(str(DB_PATH), timeout=2.0)
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            conn.close()
            size_mb = round(DB_PATH.stat().st_size / (1024 * 1024), 2)
            return {"status": "ok", "exists": True, "size_mb": size_mb}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    # -- API pública --

    async def trigger_cycle(self, cycle_type: str, force: bool = False) -> Optional[CycleResult]:
        mapping = {
            "signal_scan": "signal_scan",
            "reasoning": "signal_scan",
            "narrative_analysis": "narrative_analysis",
            "executive": "narrative_analysis",
            "megatrend_review": "megatrend_review",
            "forecast": "megatrend_review",
            "forecast_audit": "forecast_audit",
            "operations": "forecast_audit",
        }
        task_id = self._task_ids.get(mapping.get(cycle_type, cycle_type))
        if not task_id:
            logger.error("Unknown cycle_type: %s", cycle_type)
            return None
        logger.info("[VEOCore] Triggering cycle '%s' (task=%s, force=%s)", cycle_type, task_id, force)
        await self.audit.log("trigger_cycle", actor="user", details={"cycle_type": cycle_type, "force": force})
        return await self.scheduler.trigger_now(task_id)

    async def explain(self, alert_id: str) -> Dict[str, Any]:
        alert = self._explain_cache.get(alert_id)
        if not alert:
            for a in self.executive.alerts_history:
                if a.get("id") == alert_id:
                    alert = a
                    break
        if not alert:
            return {
                "alert_id": alert_id,
                "error": "Alerta no encontrada",
                "available_alerts": [a.get("id") for a in list(self.executive.alerts_history)[-20:]],
            }
        return {
            "alert_id": alert_id,
            "timestamp": _ts_now(),
            "what": alert.get("finding", {}).get("text", "N/A"),
            "type": alert.get("finding", {}).get("type", "unknown"),
            "eps_breakdown": self._explain_eps(alert.get("finding", {})),
            "recommendation": alert.get("recommendation", "N/A"),
            "explanation_text": alert.get("explanation", "Sin explicación disponible."),
            "source_cycle": self._trace_alert_origin(alert_id),
        }

    def _explain_eps(self, finding: Dict[str, Any]) -> Dict[str, Any]:
        urgency = min(max(finding.get("urgency", 50), 0), 100)
        confidence = min(max(finding.get("confidence", 50), 0), 100)
        impact = min(max(finding.get("impact", 50), 0), 100)
        recency = finding.get("eps", 0) - int(urgency * 0.40 + confidence * 0.30 + impact * 0.20)
        recency = min(max(recency, 0), 10)
        return {
            "urgency_contribution": round(urgency * 0.40, 1),
            "confidence_contribution": round(confidence * 0.30, 1),
            "impact_contribution": round(impact * 0.20, 1),
            "recency_contribution": round(recency * 0.10, 1),
            "total_eps": finding.get("eps", 0),
            "formula": "EPS = urgency*0.4 + confidence*0.3 + impact*0.2 + recency*0.1",
        }

    def _trace_alert_origin(self, alert_id: str) -> Dict[str, Any]:
        for v in self.reasoning.validation_history:
            if v.get("id") and v["id"] in str(alert_id):
                return {"cycle": "reasoning", "validation_id": v["id"]}
        for p in self.forecast.predictions_history:
            if p.get("id") and p["id"] in str(alert_id):
                return {"cycle": "forecast", "prediction_id": p["id"]}
        return {"cycle": "unknown", "note": "No se pudo trazar el origen exacto"}

    async def get_status(self) -> Dict[str, Any]:
        uptime = time.time() - self._startup_time
        health = await self.health.check()
        return {
            "running": self._running,
            "version": "2.0.5",
            "uptime_seconds": round(uptime, 1),
            "uptime_human": str(timedelta(seconds=int(uptime))),
            "health": health,
            "event_bus": self.bus.get_stats(),
            "scheduler": self.scheduler.get_queue_status(),
            "resources": {
                "utilization": self.resources.get_utilization(),
                "running": self.resources.get_running(),
            },
            "conflicts": self.conflicts.get_conflict_stats(),
            "cycles_executed": {k: len(v) for k, v in self._cycle_results.items()},
            "latest_results": {k: (list(v)[-1] if v else None) for k, v in self._cycle_results.items()},
            "pending_alerts": len(self.executive.alerts_history),
            "task_ids": self._task_ids,
        }

    async def force_conflict_check(
        self, module_a: str, score_a: float, module_b: str, score_b: float
    ) -> Dict[str, Any]:
        return await self.conflicts.resolve(module_a, score_a, module_b, score_b)

    # -- Context manager --

    async def __aenter__(self) -> "VEOCore":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.stop()


# ============================================================================
# 10. DEMO / MAIN
# ============================================================================

async def _demo() -> None:
    print("\n" + "=" * 70)
    print("  V E O   C O R E   v2  —  D E M O   C O M P L E T A")
    print("=" * 70 + "\n")

    core = VEOCore(config={
        "intervals": {
            "signal_scan": 3600,
            "narrative_analysis": 86400,
            "megatrend_review": 604800,
            "forecast_audit": 2592000,
        }
    })

    async with core:
        print("[1] VEOCore iniciado correctamente\n")

        status = await core.get_status()
        print(f"[STATUS] Health: {status['health']['overall']}")
        print(f"[STATUS] Tasks registradas: {len(status['task_ids'])}")
        print(f"[STATUS] Uptime: {status['uptime_human']}\n")

        # --- 2. reasoning_cycle ---
        print("-" * 50)
        print("[2] EJECUTANDO: reasoning_cycle (Signal Scan)")
        print("-" * 50)
        r_reasoning = await core.trigger_cycle("reasoning", force=True)
        if r_reasoning:
            print(f"   Hipótesis generadas : {r_reasoning.get('hipotesis_generadas', 0)}")
            print(f"   Hipótesis validadas : {r_reasoning.get('hipotesis_validadas', 0)}")
            print(f"   Confianzas          : {r_reasoning.get('confidence_scores', [])}")
            print(f"   Tiempo ejecución    : {r_reasoning.get('meta', {}).get('elapsed_seconds', 0)}s")
            for i, h in enumerate(r_reasoning.get('hypotheses', [])[:3], 1):
                print(f"   Hipótesis #{i}       : {h[:100]}...")
        print()

        # --- 3. forecast_cycle ---
        print("-" * 50)
        print("[3] EJECUTANDO: forecast_cycle (Megatrend Review)")
        print("-" * 50)
        r_forecast = await core.trigger_cycle("forecast", force=True)
        if r_forecast:
            print(f"   Escenarios generados : {r_forecast.get('escenarios_generados', 0)}")
            print(f"   Predicciones creadas : {r_forecast.get('predicciones_creadas', 0)}")
            for pid, prob in list(r_forecast.get('probabilidades', {}).items())[:3]:
                print(f"   Predicción {pid[:16]}... : {prob}")
            print(f"   Tiempo ejecución     : {r_forecast.get('meta', {}).get('elapsed_seconds', 0)}s")
        print()

        # --- 4. executive_cycle ---
        print("-" * 50)
        print("[4] EJECUTANDO: executive_cycle (Narrative Analysis)")
        print("-" * 50)
        r_executive = await core.trigger_cycle("executive", force=True)
        if r_executive:
            print(f"   Total findings      : {r_executive.get('total_findings', 0)}")
            for p in r_executive.get('prioridades', [])[:5]:
                print(f"   Prioridad {p['id'][:12]}... : EPS={p.get('eps', 0)} type={p['type']}")
            for rid, rec in list(r_executive.get('recomendaciones', {}).items())[:5]:
                print(f"   Recomendación {rid[:10]}... : {rec}")
            print(f"   Tiempo ejecución    : {r_executive.get('tiempo_ejecucion', 0)}s")
        print()

        # --- 5. operations_cycle ---
        print("-" * 50)
        print("[5] EJECUTANDO: operations_cycle (Forecast Audit)")
        print("-" * 50)
        r_operations = await core.trigger_cycle("operations", force=True)
        if r_operations:
            metrics = r_operations.get('metricas', {})
            print(f"   Health              : {metrics.get('overall_health', 'N/A')}")
            print(f"   CPU/Mem (sim)       : {metrics.get('cpu_percent', 0)}% / {metrics.get('memory_percent', 0)}%")
            print(f"   DB size             : {metrics.get('db_size_mb', 0)} MB")
            backup = r_operations.get('estado_backups', {})
            print(f"   Backup realizado    : {backup.get('performed', False)}")
            print(f"   Integridad DB       : {r_operations.get('integridad_ok', False)}")
            print(f"   Tiempo ejecución    : {r_operations.get('tiempo_ejecucion', 0)}s")
        print()

        # --- 6. Explainability ---
        print("-" * 50)
        print("[6] EXPLAINABILITY: explicando alertas generadas")
        print("-" * 50)
        alert_ids = [a.get("id") for a in list(core.executive.alerts_history)[:3]]
        for aid in alert_ids:
            if aid:
                expl = await core.explain(aid)
                print(f"\n   Alerta: {aid}")
                print(f"   WHAT : {expl.get('what', 'N/A')[:120]}...")
                print(f"   REC  : {expl.get('recommendation', 'N/A')}")
                eps_b = expl.get('eps_breakdown', {})
                print(f"   EPS  : {eps_b.get('total_eps', 'N/A')} "
                      f"(urg={eps_b.get('urgency_contribution', 0)} + "
                      f"conf={eps_b.get('confidence_contribution', 0)} + "
                      f"imp={eps_b.get('impact_contribution', 0)} + "
                      f"rec={eps_b.get('recency_contribution', 0)})")

        # --- 7. Conflict Resolver ---
        print("\n" + "-" * 50)
        print("[7] CONFLICT RESOLVER: simulando discrepancia")
        print("-" * 50)
        conflict_result = await core.force_conflict_check(
            module_a="ResearchEngine", score_a=85.0,
            module_b="NarrativeEngine", score_b=35.0,
        )
        print(f"   Discrepancia        : {conflict_result.get('discrepancy', 0)}")
        print(f"   Estrategia          : {conflict_result.get('resolution_strategy', 'N/A')}")
        print(f"   Requiere revisión   : {conflict_result.get('requires_human_review', False)}")
        print(f"   Consenso propuesto  : {conflict_result.get('consensus', 'N/A')}")

        conflict_ok = await core.force_conflict_check(
            module_a="ResearchEngine", score_a=72.0,
            module_b="NarrativeEngine", score_b=65.0,
        )
        print(f"   [Caso 2] Discrepancia: {conflict_ok.get('discrepancy', 0)} → "
              f"Estrategia: {conflict_ok.get('resolution_strategy', 'N/A')}")

        # --- 8. Estado final ---
        print("\n" + "=" * 50)
        print("[8] ESTADO FINAL DEL SISTEMA")
        print("=" * 50)
        final_status = await core.get_status()
        print(f"   Running             : {final_status['running']}")
        print(f"   Health              : {final_status['health']['overall']}")
        print(f"   Ciclos ejecutados   : {final_status['cycles_executed']}")
        print(f"   Alertas generadas   : {final_status['pending_alerts']}")
        print(f"   Conflictos históricos: {final_status['conflicts']['total']}")
        print(f"   EventBus msgs       : {final_status['event_bus']['event_counts']}")
        print(f"   Resource utilization: {final_status['resources']['utilization']}")

    print("\n" + "=" * 70)
    print("  D E M O   C O M P L E T A D A")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(_demo())
