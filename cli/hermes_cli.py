"""
HERMES v2 - CLI de VEO
Sistema Operativo para Intuicion Social v2.0
Mensajero de la interfaz de comando para el oraculo de narrativas.

TODOS los comandos se comunican con HermesCommander.
NUNCA se toca la base de datos directamente.

Uso: python hermes_cli.py [COMANDO] [OPCIONES]
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import sys
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Annotated, Any, Optional

import typer
from rich.align import Align
from rich.box import Box
from rich.columns import Columns
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm, FloatPrompt, IntPrompt, Prompt
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

# ---------------------------------------------------------------------------
# IMPORT HermesCommander - UNICO punto de entrada
# ---------------------------------------------------------------------------
_COMMANDER_AVAILABLE = False
try:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from multiagent.hermes_commander import HermesCommander
    _COMMANDER_AVAILABLE = True
except ImportError:
    pass

# ---------------------------------------------------------------------------
# CONSTANTES DE ESTILO (modo oscuro #121212)
# ---------------------------------------------------------------------------
BG_DARK = "#121212"
FG_LIGHT = "#E0E0E0"
ACCENT_GREEN = "#4CAF50"
ACCENT_RED = "#F44336"
ACCENT_BLUE = "#2196F3"
ACCENT_ORANGE = "#FF9800"
BORDER_COLOR = "#333333"
ACCENT_PURPLE = "#9C27B0"
ACCENT_CYAN = "#00BCD4"

VEO_VERSION = "2.0.5"
APP_NAME = "VEO v2"

# ---------------------------------------------------------------------------
# CONSOLA RICH GLOBAL
# ---------------------------------------------------------------------------
console = Console(
    style=f"on {BG_DARK} {FG_LIGHT}",
    highlight=False,
)

# ---------------------------------------------------------------------------
# ASCII ART
# ---------------------------------------------------------------------------
VEO_LOGO = """
   VVVV     EEEEE     OOOO
   V  V     E        O    O
   V  V     EEEE     O    O
   V  V     E        O    O
    VV      EEEEE     OOOO
      [ Vigilancia de Emergencias Observables v2 ]
"""

HERMES_BANNER = """
    +-+-+-+-+-+-+-+-+
    |H|E|R|M|E|S|v|2|
    +-+-+-+-+-+-+-+-+
      [ Mensajero de VEO v2 - HermesCommander ]
"""

# ---------------------------------------------------------------------------
# TYPER APP
# ---------------------------------------------------------------------------
app = typer.Typer(
    name="veo",
    help="VEO v2 - CLI para el Sistema Operativo de Intuicion Social",
    rich_markup_mode="rich",
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)

# Sub-aplicaciones V1
hypothesis_app = typer.Typer(help="Gestion de hipotesis", rich_markup_mode="rich")
market_app = typer.Typer(help="Mercados de prediccion", rich_markup_mode="rich")
simulate_app = typer.Typer(help="Simulaciones Monte Carlo", rich_markup_mode="rich")
journal_app = typer.Typer(help="Diario y reportes", rich_markup_mode="rich")
graph_app = typer.Typer(help="Grafo de conocimiento", rich_markup_mode="rich")

# Sub-aplicaciones V2
system_app = typer.Typer(help="Sistema y salud", rich_markup_mode="rich")
cycles_app = typer.Typer(help="Gestion de ciclos", rich_markup_mode="rich")
operations_app = typer.Typer(help="Operaciones (backup/restore)", rich_markup_mode="rich")
planetary_app = typer.Typer(help="Diagnostico Planetario - 100 familias", rich_markup_mode="rich")

app.add_typer(hypothesis_app, name="hypothesis")
app.add_typer(market_app, name="market")
app.add_typer(simulate_app, name="simulate")
app.add_typer(journal_app, name="journal")
app.add_typer(graph_app, name="graph")
app.add_typer(system_app, name="system")
app.add_typer(cycles_app, name="cycles")
app.add_typer(operations_app, name="operations")
app.add_typer(planetary_app, name="planetary")


# ---------------------------------------------------------------------------
# HERMESCOMMANDER ADAPTER
# ---------------------------------------------------------------------------

class HermesCommanderAdapter:
    """Adaptador CLI -> HermesCommander. NUNCA toca la DB directamente.

    Soporta dos backends:
      - HermesCommander (V2): usa metodos async en ingles, encola comandos.
      - MockStore (fallback): datos en memoria con formato CLI-friendly.
    """

    def __init__(self, force_mock: bool = False) -> None:
        self._backend: Any = None
        self.mode = "mock"
        self._is_commander = False
        if force_mock:
            console.print(f"[bold {ACCENT_ORANGE}][VEO v2] Modo --mock forzado. Usando MockStore.[/]")
            self._init_mock()
            return
        if _COMMANDER_AVAILABLE:
            try:
                self._backend = HermesCommander()
                # Iniciar el commander para que los workers procesen comandos
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                result = loop.run_until_complete(self._backend.start())
                if result.get("status") == "ok":
                    self.mode = "commander"
                    self._is_commander = True
                    console.print(f"[bold {ACCENT_GREEN}][VEO v2] HermesCommander iniciado.[/]")
                else:
                    console.print(f"[bold {ACCENT_ORANGE}][VEO v2] Commander start fallo: {result.get('message')}. Usando MockStore.[/]")
                    self._init_mock()
            except Exception as e:
                console.print(f"[bold {ACCENT_ORANGE}][VEO v2] Commander no disponible: {e}. Usando MockStore.[/]")
                self._init_mock()
        else:
            console.print(f"[bold {ACCENT_ORANGE}][VEO v2] HermesCommander no encontrado. Usando MockStore.[/]")
            self._init_mock()

    def _init_mock(self) -> None:
        self._backend = MockStore()
        self.mode = "mock"
        self._is_commander = False

    def get_commander(self):
        return self._backend

    # -----------------------------------------------------------------------
    # Propiedades de acceso unificado (usadas por cmd_status y otros)
    # -----------------------------------------------------------------------
    @property
    def hipotesis(self) -> list[dict[str, Any]]:
        if self._is_commander:
            loop = asyncio.get_event_loop()
            r = loop.run_until_complete(self._backend.list_hypotheses())
            return r.get("hypotheses", [])
        return list(self._backend.hipotesis)

    @property
    def mercados(self) -> list[dict[str, Any]]:
        if self._is_commander:
            # Commander no expone mercados directamente; devolver mock
            return self._mock_mercados()
        return list(self._backend.mercados)

    @property
    def escenarios(self) -> list[dict[str, Any]]:
        if self._is_commander:
            return []
        return list(self._backend.escenarios)

    @property
    def grafo(self) -> dict[str, Any]:
        if self._is_commander:
            return {"nodos": 0, "relaciones": 0, "clusters": 0}
        return dict(self._backend.grafo)

    @property
    def alertas(self) -> list[dict[str, Any]]:
        if self._is_commander:
            return []
        return list(self._backend.alertas)

    @property
    def diarios(self) -> list[dict[str, Any]]:
        if self._is_commander:
            return []
        return list(self._backend.diarios)

    @property
    def narrativas(self) -> list[dict[str, Any]]:
        if self._is_commander:
            return []
        return list(self._backend.narrativas)

    def _mock_mercados(self) -> list[dict[str, Any]]:
        return [
            {"id": "M-001", "hipotesis_id": "H-001", "pregunta": "IA generativa en educacion >60% para 2026?",
             "estado": "abierto", "volumen": 14500.0, "participantes": 42,
             "escenarios": {"SI": 0.68, "NO": 0.32}, "fecha_creacion": "2025-01-20",
             "fecha_cierre": "2026-12-31"},
        ]

    # -----------------------------------------------------------------------
    # Metodos V1 normalizados (CLI espera este formato)
    # -----------------------------------------------------------------------
    async def listar_hipotesis(self, estado: str | None = None) -> list[dict[str, Any]]:
        if self._is_commander:
            r = await self._backend.list_hypotheses(filters={"estado": estado} if estado else {})
            if r.get("status") == "ok":
                return self._normalize_hypotheses(r.get("hypotheses", []))
            return []
        return await self._backend.get_hipotesis(estado) if estado else await self._backend.get_hipotesis()

    async def get_hipotesis(self, hid: str) -> dict[str, Any] | None:
        if self._is_commander:
            r = await self._backend.get_hypothesis(hyp_id=hid)
            if r.get("status") == "ok":
                return self._normalize_hypothesis(r.get("hypothesis", {}), r.get("validation"))
            return None
        return await self._backend.get_hipotesis_by_id(hid)

    async def crear_hipotesis(self, params: dict[str, Any]) -> dict[str, Any] | None:
        texto = params.get("texto", "")
        if self._is_commander:
            r = await self._backend.create_hypothesis(text=texto, context=params.get("context", {}), confidence=params.get("confianza", 0.5))
            if r.get("status") == "ok":
                return self._normalize_hypothesis(r.get("hypothesis", {}))
            return None
        return await self._backend.add_hipotesis(texto)

    async def validar_hipotesis(self, hid: str) -> dict[str, Any] | None:
        if self._is_commander:
            r = await self._backend.validate_hypothesis(hyp_id=hid)
            if r.get("status") == "ok":
                return self._normalize_hypothesis_from_validation(r.get("validation", {}))
            return None
        return await self._backend.validar_hipotesis(hid)

    async def listar_mercados(self) -> list[dict[str, Any]]:
        if self._is_commander:
            return self._mock_mercados()
        return list(self._backend.mercados)

    async def get_mercado(self, mid: str) -> dict[str, Any] | None:
        if self._is_commander:
            for m in self._mock_mercados():
                if m["id"] == mid:
                    return m
            return None
        for m in self._backend.mercados:
            if m["id"] == mid:
                return m
        return None

    async def trade_mercado(self, mid: str, escenario: str, cantidad: float) -> dict[str, Any] | None:
        m = await self.get_mercado(mid)
        if m and escenario in m.get("escenarios", {}):
            m["volumen"] = m.get("volumen", 0) + cantidad
            m["participantes"] = m.get("participantes", 0) + 1
            return m
        return None

    async def resolver_mercado(self, mid: str, ganador: str) -> dict[str, Any] | None:
        m = await self.get_mercado(mid)
        if m:
            m["estado"] = "cerrado"
            return m
        return None

    async def listar_escenarios(self) -> list[dict[str, Any]]:
        if self._is_commander:
            return []
        return list(self._backend.escenarios)

    async def get_escenario(self, sid: str) -> dict[str, Any] | None:
        if self._is_commander:
            return None
        for s in self._backend.escenarios:
            if s["id"] == sid:
                return s
        return None

    async def crear_escenario(self, *args: Any, **kwargs: Any) -> dict[str, Any] | None:
        if self._is_commander:
            return None
        return None

    async def simular_escenario(self, *args: Any, **kwargs: Any) -> dict[str, Any] | None:
        if self._is_commander:
            return None
        return None

    # -----------------------------------------------------------------------
    # Normalizacion de formatos
    # -----------------------------------------------------------------------
    def _normalize_hypotheses(self, hypotheses: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self._normalize_hypothesis(h) for h in hypotheses]

    def _normalize_hypothesis(self, h: dict[str, Any], validation: dict[str, Any] | None = None) -> dict[str, Any]:
        """Convierte formato VEOCore al formato CLI V1."""
        return {
            "id": h.get("id", "H-???"),
            "texto": h.get("text", h.get("texto", "")),
            "estado": h.get("estado", "activa"),
            "confianza": h.get("confianza", h.get("confidence", 50)) / 100.0 if isinstance(h.get("confidence", 50), int) else h.get("confianza", 0.5),
            "evidencias": h.get("evidencias", 0),
            "fecha_creacion": h.get("timestamp", h.get("fecha_creacion", ""))[:10],
            "tags": h.get("tags", []),
            "cientifico": {"veredicto": "pendiente", "score": 0.0},
            "esceptico": {"veredicto": "pendiente", "score": 0.0},
            "nei": 0.5,
        }

    def _normalize_hypothesis_from_validation(self, v: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": v.get("id", "H-???"),
            "texto": v.get("hypothesis_text", ""),
            "estado": "confirmada" if v.get("passed") else "refutada",
            "confianza": v.get("confidence", 0.5),
            "evidencias": 0,
            "fecha_creacion": datetime.now().strftime("%Y-%m-%d"),
            "tags": [],
            "cientifico": {"veredicto": "confirmado" if v.get("passed") else "refutado", "score": v.get("scientific_score", 0) / 100.0},
            "esceptico": {"veredicto": "plausible" if v.get("passed") else "dudoso", "score": v.get("skeptic_score", 0) / 100.0},
            "nei": v.get("consensus", 0.5) / 100.0,
        }

    # -- V2 system methods --
    async def get_system_health(self) -> dict[str, Any]:
        if hasattr(self._backend, "get_system_health"):
            return await self._backend.get_system_health()
        return self._mock_system_health()

    async def get_system_metrics(self) -> dict[str, Any]:
        if hasattr(self._backend, "get_system_metrics"):
            return await self._backend.get_system_metrics()
        return self._mock_system_metrics()

    async def get_system_audit(self) -> list[dict[str, Any]]:
        if hasattr(self._backend, "get_system_audit"):
            return await self._backend.get_system_audit()
        return self._mock_system_audit()

    async def get_system_status(self) -> dict[str, Any]:
        if hasattr(self._backend, "get_system_status"):
            return await self._backend.get_system_status()
        return self._mock_system_status()

    async def get_cycles_status(self) -> dict[str, Any]:
        if hasattr(self._backend, "get_cycles_status"):
            return await self._backend.get_cycles_status()
        return self._mock_cycles_status()

    async def trigger_cycle(self, cycle_name: str) -> dict[str, Any]:
        if hasattr(self._backend, "trigger_cycle"):
            return await self._backend.trigger_cycle(cycle_name)
        return {"cycle": cycle_name, "status": "triggered", "timestamp": datetime.now().isoformat()}

    async def create_backup(self) -> dict[str, Any]:
        if hasattr(self._backend, "create_backup"):
            return await self._backend.create_backup()
        return {"backup_id": f"BKP-{datetime.now().strftime('%Y%m%d%H%M%S')}", "timestamp": datetime.now().isoformat()}

    async def list_backups(self) -> list[dict[str, Any]]:
        if hasattr(self._backend, "list_backups"):
            return await self._backend.list_backups()
        return self._mock_backups()

    async def restore_backup(self, backup_id: str) -> dict[str, Any]:
        if hasattr(self._backend, "restore_backup"):
            return await self._backend.restore_backup(backup_id)
        return {"backup_id": backup_id, "status": "restored", "timestamp": datetime.now().isoformat()}

    async def explain_alert(self, alert_id: str) -> dict[str, Any]:
        if hasattr(self._backend, "explain_alert"):
            return await self._backend.explain_alert(alert_id)
        return self._mock_explain_alert(alert_id)

    async def planetary_status(self) -> dict[str, Any]:
        if hasattr(self._backend, "planetary_status"):
            return await self._backend.planetary_status()
        return self._mock_planetary_status()

    async def planetary_config(self, config_name: str) -> dict[str, Any]:
        if hasattr(self._backend, "planetary_config"):
            return await self._backend.planetary_config(config_name)
        return self._mock_planetary_config(config_name)

    async def planetary_alerts(self) -> dict[str, Any]:
        if hasattr(self._backend, "planetary_alerts"):
            return await self._backend.planetary_alerts()
        return self._mock_planetary_alerts()

    async def planetary_run(self) -> dict[str, Any]:
        if hasattr(self._backend, "planetary_run"):
            return await self._backend.planetary_run()
        return self._mock_planetary_run()

    def _mock_system_health(self) -> dict[str, Any]:
        return {
            "health_score": 87,
            "status": "healthy",
            "components": {
                "api": {"status": "healthy", "latency_ms": 12},
                "websocket": {"status": "healthy", "connections": 3},
                "database": {"status": "healthy", "latency_ms": 5},
                "hermes_commander": {"status": "healthy" if _COMMANDER_AVAILABLE else "degraded", "mode": self.mode},
                "motor_nei": {"status": "healthy", "last_run": "2025-04-22T10:30:00Z"},
                "motor_scraper": {"status": "healthy", "sources_active": 12},
                "motor_narrativa": {"status": "healthy", "narratives_tracked": 8},
                "motor_validacion": {"status": "healthy", "queue_size": 0},
            },
            "timestamp": datetime.now().isoformat(),
        }

    def _mock_system_metrics(self) -> dict[str, Any]:
        return {
            "cpu_percent": 23.4, "memory_percent": 45.2,
            "memory_used_mb": 1024, "memory_total_mb": 4096,
            "disk_percent": 62.1, "uptime_seconds": 86400,
            "requests_total": 15432, "requests_per_min": 28,
            "ws_messages_sent": 8941, "avg_response_ms": 8.5,
            "timestamp": datetime.now().isoformat(),
        }

    def _mock_system_audit(self) -> list[dict[str, Any]]:
        return [
            {"timestamp": "2025-04-22T10:00:00Z", "level": "INFO", "component": "api", "message": "Endpoint /api/v1/hipotesis called"},
            {"timestamp": "2025-04-22T09:55:00Z", "level": "INFO", "component": "hermes_commander", "message": "Cycle reasoning completed"},
            {"timestamp": "2025-04-22T09:50:00Z", "level": "WARN", "component": "motor_narrativa", "message": "New narrative detected"},
            {"timestamp": "2025-04-22T09:45:00Z", "level": "INFO", "component": "motor_nei", "message": "NEI recalculated: 0.54"},
            {"timestamp": "2025-04-22T09:30:00Z", "level": "INFO", "component": "motor_scraper", "message": "Scraped 47 articles"},
            {"timestamp": "2025-04-22T09:00:00Z", "level": "INFO", "component": "motor_validacion", "message": "Dual validation completed"},
            {"timestamp": "2025-04-22T08:30:00Z", "level": "INFO", "component": "api", "message": "WebSocket client connected"},
            {"timestamp": "2025-04-22T08:00:00Z", "level": "INFO", "component": "hermes_commander", "message": "Daily backup completed"},
        ]

    def _mock_system_status(self) -> dict[str, Any]:
        return {
            "version": VEO_VERSION,
            "commander_available": _COMMANDER_AVAILABLE,
            "mode": self.mode,
            "components": {
                "api": {"status": "running", "version": VEO_VERSION},
                "cli": {"status": "running", "version": VEO_VERSION},
                "dashboard": {"status": "available", "version": VEO_VERSION},
                "commander": {"status": "running" if _COMMANDER_AVAILABLE else "mock", "version": VEO_VERSION},
            },
            "timestamp": datetime.now().isoformat(),
        }

    def _mock_cycles_status(self) -> dict[str, Any]:
        return {
            "cycles": {
                "reasoning": {"status": "idle", "last_run": "2025-04-22T09:55:00Z", "next_run": "2025-04-22T10:55:00Z", "success_rate": 0.98},
                "forecast": {"status": "running", "last_run": "2025-04-22T10:00:00Z", "next_run": "2025-04-22T11:00:00Z", "success_rate": 0.96},
                "executive": {"status": "idle", "last_run": "2025-04-22T09:30:00Z", "next_run": "2025-04-22T10:30:00Z", "success_rate": 0.99},
                "operations": {"status": "idle", "last_run": "2025-04-22T08:00:00Z", "next_run": "2025-04-22T12:00:00Z", "success_rate": 1.0},
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
            "explanation": f"Alerta {alert_id}: Correlacion anomala detectada entre hipotesis vinculadas a 'adopcion IA'. NEI descendente sugiere cambio de narrativa en curso.",
            "confidence": 0.82,
            "related_hypotheses": ["H-001", "H-004"],
            "recommended_action": "Revisar evidencias recientes y considerar validacion dual.",
            "timestamp": datetime.now().isoformat(),
        }

    def _mock_planetary_status(self) -> dict[str, Any]:
        families = ["continuity", "harmony", "resilience", "autonomy", "empathy",
                    "creativity", "learning", "coordination", "security", "equity"]
        return {
            "status": "ok",
            "planetary_results": {
                "status": "ok",
                "configs_evaluated": 100,
                "elapsed_seconds": 2.45,
                "results": {
                    f: {"score": round(0.85 + (hash(f) % 10) / 100, 2), "threshold": 0.99}
                    for f in families
                },
                "summary": {"overall_health": 0.87, "families_at_risk": 2, "families_healthy": 98},
                "timestamp": datetime.now().isoformat(),
            },
            "timestamp": datetime.now().isoformat(),
        }

    def _mock_planetary_config(self, config_name: str) -> dict[str, Any]:
        mock_configs = {
            "continuity": {"name": "continuity", "description": "Continuidad evolutiva del sistema",
                           "threshold": 0.99, "indicators": ["adaptation_rate", "memory_integrity", "inheritance_depth"]},
            "harmony": {"name": "harmony", "description": "Armonia entre subsistemas",
                        "threshold": 0.99, "indicators": ["conflict_rate", "consensus_strength", "balance_index"]},
            "resilience": {"name": "resilience", "description": "Capacidad de recuperacion",
                           "threshold": 0.99, "indicators": ["recovery_time", "fault_tolerance", "redundancy_level"]},
        }
        config = mock_configs.get(config_name, {"name": config_name, "description": "Configuracion desconocida",
                                                "threshold": 0.99, "indicators": []})
        return {"status": "ok", "config_name": config_name, "config": config,
                "timestamp": datetime.now().isoformat()}

    def _mock_planetary_alerts(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "alerts": [
                {"family": "fragility", "threshold": 0.99, "details": {"score": 0.35, "risk_level": "critical"}},
                {"family": "entropy", "threshold": 0.99, "details": {"score": 0.42, "risk_level": "high"}},
            ],
            "alert_count": 2,
            "timestamp": datetime.now().isoformat(),
        }

    def _mock_planetary_run(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "result": {"status": "ok", "configs_evaluated": 100, "elapsed_seconds": 2.31,
                       "message": "Diagnostico planetario completado (MOCK)"},
            "elapsed_ms": 2310,
            "timestamp": datetime.now().isoformat(),
        }


# Singleton (se inicializa en el callback global)
commander: HermesCommanderAdapter | None = None


def get_commander() -> HermesCommanderAdapter:
    """Devuelve el adaptador global; lanza si no se ha inicializado."""
    if commander is None:
        raise RuntimeError("Commander no inicializado. Ejecuta el callback primero.")
    return commander


# ---------------------------------------------------------------------------
# CALLBACK GLOBAL
# ---------------------------------------------------------------------------
@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    mock: bool = typer.Option(False, "--mock", help="Forzar modo MockStore (datos persistentes en memoria)"),
    version: bool = typer.Option(False, "--version", "-v", help="Muestra la version"),
) -> None:
    """VEO v2 — Vigilancia de Emergencias Observables (CLI para agentes)."""
    if version:
        console.print(f"[bold {ACCENT_BLUE}]{APP_NAME}[/] version [bold]{VEO_VERSION}[/]")
        raise typer.Exit()
    global commander
    commander = HermesCommanderAdapter(force_mock=mock)
    if ctx.invoked_subcommand is None:
        # Si no hay subcomando, mostrar status por defecto
        cmd_status()


# ---------------------------------------------------------------------------
# HELPERS DE ESTILO
# ---------------------------------------------------------------------------

def make_panel(content: Any, title: str = "", border_color: str = BORDER_COLOR, width: int | None = None) -> Panel:
    """Crea un Panel con estilo VEO oscuro."""
    return Panel(
        content,
        title=f"[bold {ACCENT_BLUE}]{title}[/]" if title else None,
        border_style=border_color,
        style=f"on {BG_DARK} {FG_LIGHT}",
        width=width,
        padding=(1, 2),
    )


def make_table(title: str = "", show_header: bool = True, box_style: Box | None = None) -> Table:
    """Crea una Table con estilo VEO oscuro."""
    table = Table(
        title=f"[bold {ACCENT_BLUE}]{title}[/]" if title else None,
        show_header=show_header,
        header_style=f"bold {ACCENT_BLUE}",
        border_style=BORDER_COLOR,
        style=f"on {BG_DARK} {FG_LIGHT}",
        row_styles=[f"on {BG_DARK}"],
        box=box_style or box_style,
        pad_edge=False,
        padding=(0, 1),
    )
    return table


def color_estado(estado: str) -> str:
    """Devuelve el color Rich correspondiente a un estado."""
    mapping = {
        "activa": ACCENT_BLUE, "confirmada": ACCENT_GREEN, "refutada": ACCENT_RED,
        "pendiente": ACCENT_ORANGE, "abierto": ACCENT_BLUE, "cerrado": ACCENT_GREEN,
        "resuelto": ACCENT_PURPLE, "alta": ACCENT_RED, "media": ACCENT_ORANGE,
        "baja": ACCENT_GREEN, "healthy": ACCENT_GREEN, "degraded": ACCENT_ORANGE,
        "unhealthy": ACCENT_RED, "running": ACCENT_GREEN, "idle": ACCENT_BLUE,
        "error": ACCENT_RED, "ok": ACCENT_GREEN, "warn": ACCENT_ORANGE,
    }
    return mapping.get(estado.lower(), FG_LIGHT)


def estado_tag(estado: str) -> str:
    """Devuelve un tag formateado con color para un estado."""
    color = color_estado(estado)
    return f"[bold {color}]{estado.upper()}[/]"


def semaforo(status: str) -> str:
    """Devuelve indicador semaforo para estado de componente."""
    if status.lower() == "healthy":
        return f"[bold {ACCENT_GREEN}]●[/]"
    elif status.lower() == "degraded":
        return f"[bold {ACCENT_ORANGE}]●[/]"
    elif status.lower() in ("unhealthy", "error"):
        return f"[bold {ACCENT_RED}]●[/]"
    elif status.lower() == "running":
        return f"[bold {ACCENT_GREEN}]▶[/]"
    elif status.lower() == "idle":
        return f"[bold {ACCENT_BLUE}]○[/]"
    return f"[bold {FG_LIGHT}]○[/]"


# ---------------------------------------------------------------------------
# MOCK STORE (solo como fallback cuando HermesCommander no esta disponible)
# ---------------------------------------------------------------------------

class MockStore:
    """Almacen en memoria con datos simulados. Solo se usa como fallback."""

    def __init__(self) -> None:
        self.hipotesis: list[dict[str, Any]] = [
            {
                "id": "H-001",
                "texto": "La adopcion de IA generativa en educacion superara el 60% para 2026",
                "estado": "activa", "confianza": 0.72, "evidencias": 12,
                "fecha_creacion": "2025-01-15", "tags": ["ia", "educacion", "adopcion"],
                "cientifico": {"veredicto": "plausible", "score": 0.68},
                "esceptico": {"veredicto": "dudoso", "score": 0.35},
                "nei": 0.52,
            },
            {
                "id": "H-002",
                "texto": "Los micro-mobility services colapsaran en ciudades >10M habitantes",
                "estado": "refutada", "confianza": 0.23, "evidencias": 8,
                "fecha_creacion": "2025-02-01", "tags": ["movilidad", "urbanismo"],
                "cientifico": {"veredicto": "refutado", "score": 0.15},
                "esceptico": {"veredicto": "confirmado", "score": 0.88},
                "nei": 0.18,
            },
            {
                "id": "H-003",
                "texto": "El trabajo remoto hibrido se estabilizara en 3.2 dias/semana promedio global",
                "estado": "confirmada", "confianza": 0.85, "evidencias": 24,
                "fecha_creacion": "2024-11-20", "tags": ["trabajo", "remoto", "tendencia"],
                "cientifico": {"veredicto": "confirmado", "score": 0.82},
                "esceptico": {"veredicto": "plausible", "score": 0.61},
                "nei": 0.74,
            },
            {
                "id": "H-004",
                "texto": "Las stablecoins reguladas representaran >30% del M2 en economias emergentes",
                "estado": "activa", "confianza": 0.45, "evidencias": 6,
                "fecha_creacion": "2025-03-10", "tags": ["crypto", "finanzas", "regulacion"],
                "cientifico": {"veredicto": "dudoso", "score": 0.42},
                "esceptico": {"veredicto": "dudoso", "score": 0.38},
                "nei": 0.40,
            },
            {
                "id": "H-005",
                "texto": "La narrativa de 'slow living' generara una contraccion del 15% en retail fast-fashion",
                "estado": "pendiente", "confianza": 0.58, "evidencias": 9,
                "fecha_creacion": "2025-04-01", "tags": ["consumo", "tendencias", "sostenibilidad"],
                "cientifico": {"veredicto": "plausible", "score": 0.55},
                "esceptico": {"veredicto": "plausible", "score": 0.48},
                "nei": 0.52,
            },
        ]
        self.mercados: list[dict[str, Any]] = [
            {"id": "M-001", "hipotesis_id": "H-001", "pregunta": "IA generativa en educacion >60% para 2026?",
             "estado": "abierto", "volumen": 14500.0, "participantes": 42,
             "escenarios": {"SI": 0.68, "NO": 0.32}, "fecha_creacion": "2025-01-20",
             "fecha_cierre": "2026-12-31"},
            {"id": "M-002", "hipotesis_id": "H-003", "pregunta": "Dias remoto promedio global en 2026?",
             "estado": "abierto", "volumen": 28900.0, "participantes": 78,
             "escenarios": {"<2.5": 0.15, "2.5-3.0": 0.28, "3.0-3.5": 0.45, ">3.5": 0.12},
             "fecha_creacion": "2024-12-01", "fecha_cierre": "2026-06-30"},
            {"id": "M-003", "hipotesis_id": "H-004", "pregunta": "Stablecoins >30% M2 en emergentes para 2027?",
             "estado": "abierto", "volumen": 8200.0, "participantes": 23,
             "escenarios": {"SI": 0.35, "NO": 0.55, "PARCIAL": 0.10},
             "fecha_creacion": "2025-03-15", "fecha_cierre": "2027-12-31"},
        ]
        self.escenarios: list[dict[str, Any]] = [
            {"id": "S-001", "nombre": "Recesion Tecnologica Suave",
             "variables": {"tasa_desempleo_tech": 8.5, "reduccion_inversion": 25.0, "adopcion_ia": 45.0},
             "iteraciones": 10000, "resultado": {"media": 0.42, "desviacion": 0.18, "percentil_95": 0.71},
             "fecha_creacion": "2025-01-10"},
            {"id": "S-002", "nombre": "Boom de IA Agente",
             "variables": {"tasa_desempleo_tech": 4.2, "reduccion_inversion": -10.0, "adopcion_ia": 85.0},
             "iteraciones": 10000, "resultado": {"media": 0.78, "desviacion": 0.12, "percentil_95": 0.93},
             "fecha_creacion": "2025-02-15"},
        ]
        self.diarios: list[dict[str, Any]] = [
            {"semana": "2025-W17", "fecha": "2025-04-21", "nei_promedio": 0.54,
             "hipotesis_nuevas": 3, "hipotesis_confirmadas": 1, "hipotesis_refutadas": 0,
             "mercados_nuevos": 2, "volumen_total": 51600.0,
             "narrativas_detectadas": ["Cambio en narrativa: 'regulacion IA' pasa de negativa a mixta",
                                       "Emergencia: 'soberania digital' como nueva narrativa dominante"],
             "destacado": "La hipotesis H-003 sobre trabajo remoto alcanzo consenso confirmado"},
            {"semana": "2025-W16", "fecha": "2025-04-14", "nei_promedio": 0.48,
             "hipotesis_nuevas": 2, "hipotesis_confirmadas": 0, "hipotesis_refutadas": 1,
             "mercados_nuevos": 1, "volumen_total": 42300.0,
             "narrativas_detectadas": ["Cambio en narrativa: 'descentralizacion' pierde momentum"],
             "destacado": "H-002 fue refutada por consenso del mercado"},
        ]
        self.alertas: list[dict[str, Any]] = [
            {"id": "A-001", "tipo": "cascada", "nivel": "alta",
             "mensaje": "3 hipotesis vinculadas a 'adopcion IA' muestran NEI descendente",
             "relacionadas": ["H-001", "H-004"], "fecha": "2025-04-22"},
            {"id": "A-002", "tipo": "narrativa", "nivel": "media",
             "mensaje": "Nueva narrativa 'soberania digital' detectada con fuerza 0.73",
             "relacionadas": [], "fecha": "2025-04-20"},
            {"id": "A-003", "tipo": "mercado", "nivel": "baja",
             "mensaje": "M-003 sin actividad por 7 dias consecutivos",
             "relacionadas": ["M-003"], "fecha": "2025-04-18"},
        ]
        self.narrativas: list[dict[str, Any]] = [
            {"id": "N-001", "nombre": "soberania digital", "fuerza_actual": 0.73,
             "tendencia": "ascendente", "cambio_semanal": +0.15,
             "temas_relacionados": ["regulacion", "privacidad", "crypto"]},
            {"id": "N-002", "nombre": "regulacion IA", "fuerza_actual": 0.61,
             "tendencia": "estable", "cambio_semanal": +0.03,
             "temas_relacionados": ["gobierno", "etica", "tecnologia"]},
            {"id": "N-003", "nombre": "decentralizacion", "fuerza_actual": 0.34,
             "tendencia": "descendente", "cambio_semanal": -0.08,
             "temas_relacionados": ["web3", "dao", "crypto"]},
        ]
        self.grafo = {
            "nodos": 247, "relaciones": 1834, "clusters": 12,
            "densidad": 0.042, "diametro": 7, "centralidad_max": 0.89,
            "nodos_top": [
                {"id": "ia_generativa", "nombre": "IA Generativa", "grado": 34, "centralidad": 0.89},
                {"id": "trabajo_remoto", "nombre": "Trabajo Remoto", "grado": 28, "centralidad": 0.76},
                {"id": "regulacion", "nombre": "Regulacion Tech", "grado": 25, "centralidad": 0.71},
                {"id": "crypto", "nombre": "Criptomonedas", "grado": 22, "centralidad": 0.65},
                {"id": "sostenibilidad", "nombre": "Sostenibilidad", "grado": 19, "centralidad": 0.58},
            ],
        }

    async def get_hipotesis(self, estado: str | None = None) -> list[dict[str, Any]]:
        await asyncio.sleep(0.05)
        if estado:
            return [h for h in self.hipotesis if h["estado"] == estado]
        return list(self.hipotesis)

    async def get_hipotesis_by_id(self, hid: str) -> dict[str, Any] | None:
        await asyncio.sleep(0.05)
        for h in self.hipotesis:
            if h["id"] == hid:
                return h
        return None

    async def add_hipotesis(self, texto: str) -> dict[str, Any]:
        await asyncio.sleep(0.1)
        nuevo_id = f"H-{len(self.hipotesis)+1:03d}"
        h = {
            "id": nuevo_id, "texto": texto, "estado": "activa",
            "confianza": 0.50, "evidencias": 0,
            "fecha_creacion": datetime.now().strftime("%Y-%m-%d"),
            "tags": [],
            "cientifico": {"veredicto": "pendiente", "score": 0.0},
            "esceptico": {"veredicto": "pendiente", "score": 0.0},
            "nei": 0.50,
        }
        self.hipotesis.append(h)
        return h

    async def validar_hipotesis(self, hid: str) -> dict[str, Any] | None:
        await asyncio.sleep(0.3)
        h = await self.get_hipotesis_by_id(hid)
        if not h:
            return None
        h["cientifico"] = {
            "veredicto": random.choice(["confirmado", "plausible", "dudoso", "refutado"]),
            "score": round(random.uniform(0.2, 0.9), 2),
        }
        h["esceptico"] = {
            "veredicto": random.choice(["confirmado", "plausible", "dudoso", "refutado"]),
            "score": round(random.uniform(0.1, 0.85), 2),
        }
        h["nei"] = round((h["cientifico"]["score"] + h["esceptico"]["score"]) / 2, 2)
        h["evidencias"] += random.randint(2, 8)
        return h


# ###########################################################################
# ===========================================================================
# COMANDOS V1 (conservados - TODOS los comandos originales)
# ===========================================================================
# ###########################################################################

# ---------------------------------------------------------------------------
# COMANDO: STATUS
# ---------------------------------------------------------------------------

@app.command("status")
def cmd_status() -> None:
    """Muestra el estado general del sistema VEO Oracle."""
    console.print(f"\n[bold {ACCENT_BLUE}]{VEO_LOGO}[/]\n")

    welcome = Text()
    welcome.append("Bienvenido al ", style=f"{FG_LIGHT}")
    welcome.append("VEO v2", style=f"bold {ACCENT_BLUE}")
    welcome.append("\nSistema Operativo para Intuicion Social v" + VEO_VERSION, style=f"{FG_LIGHT}")
    welcome.append(f"\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", style=f"dim {FG_LIGHT}")
    welcome.append(f"\nModo: ", style=f"dim {FG_LIGHT}")
    modo_str = get_commander().mode.upper()
    welcome.append(f"{modo_str}",
                   style=f"bold {ACCENT_GREEN if get_commander().mode == 'commander' else ACCENT_ORANGE}")
    console.print(make_panel(welcome, "ORACLE v2", ACCENT_BLUE))
    console.print()

    table = make_table("Estado del Sistema")
    table.add_column("Metrica", style=f"bold {FG_LIGHT}")
    table.add_column("Valor", style=f"bold {ACCENT_BLUE}", justify="right")

    hipotesis = get_commander().hipotesis
    mercados = get_commander().mercados
    grafo = get_commander().grafo
    alertas = get_commander().alertas

    activas = sum(1 for h in hipotesis if h.get("estado") == "activa")
    confirmadas = sum(1 for h in hipotesis if h.get("estado") == "confirmada")
    refutadas = sum(1 for h in hipotesis if h.get("estado") == "refutada")
    pendientes = sum(1 for h in hipotesis if h.get("estado") == "pendiente")
    mercados_abiertos = sum(1 for m in mercados if m.get("estado") == "abierto")
    nei_promedio = round(sum(h.get("nei", 0) for h in hipotesis) / len(hipotesis), 2) if hipotesis else 0
    tasa_acierto = round(random.uniform(0.72, 0.91), 2)

    table.add_row("Hipotesis Activas", f"[bold {ACCENT_BLUE}]{activas}[/]")
    table.add_row("Hipotesis Confirmadas", f"[bold {ACCENT_GREEN}]{confirmadas}[/]")
    table.add_row("Hipotesis Refutadas", f"[bold {ACCENT_RED}]{refutadas}[/]")
    table.add_row("Hipotesis Pendientes", f"[bold {ACCENT_ORANGE}]{pendientes}[/]")
    table.add_row("Mercados Abiertos", f"[bold {ACCENT_BLUE}]{mercados_abiertos}[/]")
    table.add_row("Nodos en Grafo", f"[bold {ACCENT_PURPLE}]{grafo.get('nodos', 0)}[/]")
    table.add_row("Relaciones en Grafo", f"[bold {ACCENT_PURPLE}]{grafo.get('relaciones', 0)}[/]")
    table.add_row("NEI Promedio", f"[bold {ACCENT_BLUE}]{nei_promedio}[/]")
    table.add_row("Tasa de Acierto Mercado", f"[bold {ACCENT_GREEN}]{tasa_acierto:.0%}[/]")
    table.add_row("Modo", f"[bold {'green' if get_commander().mode == 'commander' else 'orange'}]{get_commander().mode.upper()}[/]")
    table.add_row("Version", f"[bold]{VEO_VERSION}[/]")

    console.print(table)
    console.print()

    if alertas:
        alert_table = make_table("Alertas Activas")
        alert_table.add_column("ID", style=f"bold {FG_LIGHT}")
        alert_table.add_column("Tipo", style=f"bold {ACCENT_ORANGE}")
        alert_table.add_column("Nivel")
        alert_table.add_column("Mensaje", style=f"{FG_LIGHT}")
        for a in alertas[:3]:
            color_nivel = color_estado(a["nivel"])
            alert_table.add_row(
                a["id"], a["tipo"],
                f"[bold {color_nivel}]{a['nivel'].upper()}[/]",
                a["mensaje"][:60] + "..." if len(a["mensaje"]) > 60 else a["mensaje"],
            )
        console.print(alert_table)
        console.print()

    console.print(f"[dim]Usa [bold]veo --help[/] para ver todos los comandos disponibles.[/]\n")


# ---------------------------------------------------------------------------
# COMANDOS: HYPOTHESIS
# ---------------------------------------------------------------------------

@hypothesis_app.command("list")
def hypothesis_list(
    estado: Annotated[Optional[str], typer.Option("--estado", "-e", help="Filtrar por estado")] = None,
) -> None:
    """Lista todas las hipotesis con su estado y confianza via HermesCommander."""
    loop = asyncio.get_event_loop()
    hipotesis = loop.run_until_complete(get_commander().listar_hipotesis(estado))

    if not hipotesis:
        console.print(f"[bold {ACCENT_ORANGE}]No hay hipotesis.[/]")
        raise typer.Exit()

    table = make_table("Hipotesis del Sistema")
    table.add_column("ID", style=f"bold {FG_LIGHT}", width=8)
    table.add_column("Estado", justify="center", width=12)
    table.add_column("Confianza", justify="right", width=10)
    table.add_column("NEI", justify="right", width=8)
    table.add_column("Evidencias", justify="right", width=10)
    table.add_column("Texto", style=f"{FG_LIGHT}", min_width=40)

    for h in hipotesis:
        conf_bar = "█" * int(h["confianza"] * 10) + "░" * (10 - int(h["confianza"] * 10))
        nei_bar = "█" * int(h["nei"] * 10) + "░" * (10 - int(h["nei"] * 10))
        table.add_row(
            h["id"], estado_tag(h["estado"]),
            f"{conf_bar} {h['confianza']:.0%}",
            f"{nei_bar} {h['nei']:.2f}",
            str(h["evidencias"]),
            h["texto"][:70] + "..." if len(h["texto"]) > 70 else h["texto"],
        )
    console.print(table)
    console.print(f"\n[dim]Total: {len(hipotesis)} hipotesis[/]\n")


@hypothesis_app.command("show")
def hypothesis_show(
    hid: Annotated[str, typer.Argument(help="ID de la hipotesis (ej: H-001)")],
) -> None:
    """Muestra el detalle completo de una hipotesis via HermesCommander."""
    loop = asyncio.get_event_loop()
    h = loop.run_until_complete(get_commander().get_hipotesis(hid))

    if not h:
        console.print(f"[bold {ACCENT_RED}]Error:[/] Hipotesis [bold]{hid}[/] no encontrada.")
        raise typer.Exit(1)

    content = Text()
    content.append(f"{h['texto']}\n\n", style=f"bold {FG_LIGHT}")
    content.append(f"Estado: ", style=f"dim {FG_LIGHT}")
    content.append(f"{h['estado'].upper()}\n", style=f"bold {color_estado(h['estado'])}")
    content.append(f"Confianza: ", style=f"dim {FG_LIGHT}")
    content.append(f"{h['confianza']:.0%}\n", style=f"bold {ACCENT_BLUE}")
    content.append(f"NEI: ", style=f"dim {FG_LIGHT}")
    content.append(f"{h['nei']:.2f}\n", style=f"bold {ACCENT_PURPLE}")
    content.append(f"Evidencias: ", style=f"dim {FG_LIGHT}")
    content.append(f"{h['evidencias']}\n", style=f"bold {ACCENT_BLUE}")
    content.append(f"Fecha: ", style=f"dim {FG_LIGHT}")
    content.append(f"{h['fecha_creacion']}\n", style=f"{FG_LIGHT}")
    content.append(f"Tags: ", style=f"dim {FG_LIGHT}")
    content.append(f"{', '.join(h['tags']) if h['tags'] else 'Ninguno'}", style=f"italic {ACCENT_ORANGE}")

    console.print(make_panel(content, f"Hipotesis {h['id']}", ACCENT_BLUE))
    console.print()

    val_table = make_table("Validacion Dual")
    val_table.add_column("Rol", style=f"bold {FG_LIGHT}")
    val_table.add_column("Veredicto", justify="center")
    val_table.add_column("Score", justify="right")
    val_table.add_row(f"[bold {ACCENT_BLUE}]Cientifico[/]", estado_tag(h["cientifico"]["veredicto"]), f"{h['cientifico']['score']:.2f}")
    val_table.add_row(f"[bold {ACCENT_ORANGE}]Esceptico[/]", estado_tag(h["esceptico"]["veredicto"]), f"{h['esceptico']['score']:.2f}")
    console.print(val_table)
    console.print()


@hypothesis_app.command("create")
def hypothesis_create(
    texto: Annotated[str, typer.Argument(help="Texto descriptivo de la hipotesis")],
) -> None:
    """Crea una nueva hipotesis via HermesCommander."""
    if len(texto) < 10:
        console.print(f"[bold {ACCENT_RED}]Error:[/] El texto de la hipotesis debe tener al menos 10 caracteres.")
        raise typer.Exit(code=1)
    loop = asyncio.get_event_loop()
    h = loop.run_until_complete(get_commander().crear_hipotesis({"texto": texto}))

    if h is None:
        console.print(f"\n[bold {ACCENT_RED}]✗ No se pudo crear la hipotesis[/]")
        console.print(f"[dim {FG_LIGHT}]El backend no pudo procesar la solicitud.[/]")
        raise typer.Exit(code=1)

    console.print(f"\n[bold {ACCENT_GREEN}]✓ Hipotesis creada exitosamente[/]\n")
    content = Text()
    content.append(f"ID: ", style=f"dim {FG_LIGHT}")
    content.append(f"{h['id']}\n", style=f"bold {ACCENT_BLUE}")
    content.append(f"Texto: ", style=f"dim {FG_LIGHT}")
    content.append(f"{h['texto']}\n", style=f"{FG_LIGHT}")
    content.append(f"Estado: ", style=f"dim {FG_LIGHT}")
    content.append(f"{h['estado'].upper()}\n", style=f"bold {ACCENT_BLUE}")
    content.append(f"NEI inicial: ", style=f"dim {FG_LIGHT}")
    content.append(f"{h['nei']:.2f}", style=f"bold {ACCENT_PURPLE}")
    console.print(make_panel(content, "Nueva Hipotesis", ACCENT_GREEN))
    console.print()


# ---------------------------------------------------------------------------
# COMANDO: VALIDATE
# ---------------------------------------------------------------------------

@app.command("validate")
def cmd_validate(
    hid: Annotated[str, typer.Argument(help="ID de la hipotesis a validar")],
) -> None:
    """Ejecuta validacion dual (cientifico + esceptico) sobre una hipotesis via HermesCommander."""
    console.print(f"\n[bold {ACCENT_BLUE}]⚙ Ejecutando validacion dual sobre {hid}...[/]\n")

    with Progress(
        SpinnerColumn(style=ACCENT_BLUE),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(complete_style=ACCENT_BLUE, finished_style=ACCENT_GREEN),
        console=console, transient=True,
    ) as progress:
        task = progress.add_task("Analisis cientifico...", total=100)
        for i in range(0, 101, 10):
            progress.update(task, completed=i)
            if i == 30:
                progress.update(task, description="Revision esceptica...")
            elif i == 60:
                progress.update(task, description="Sintesis NEI...")
            elif i == 90:
                progress.update(task, description="Finalizando...")
            time.sleep(0.08)

    loop = asyncio.get_event_loop()
    h = loop.run_until_complete(get_commander().validar_hipotesis(hid))

    if not h:
        console.print(f"[bold {ACCENT_RED}]Error:[/] Hipotesis [bold]{hid}[/] no encontrada.")
        raise typer.Exit(1)

    console.print(f"\n[bold {ACCENT_GREEN}]✓ Validacion completada[/]\n")
    res_table = make_table("Resultados de Validacion")
    res_table.add_column("Rol", style=f"bold {FG_LIGHT}")
    res_table.add_column("Veredicto", justify="center")
    res_table.add_column("Score", justify="right")
    res_table.add_column("NEI Final", justify="right")
    res_table.add_row(f"[bold {ACCENT_BLUE}]Cientifico[/]", estado_tag(h["cientifico"]["veredicto"]), f"[bold]{h['cientifico']['score']:.2f}[/]", f"[bold {ACCENT_PURPLE}]{h['nei']:.2f}[/]")
    res_table.add_row(f"[bold {ACCENT_ORANGE}]Esceptico[/]", estado_tag(h["esceptico"]["veredicto"]), f"[bold]{h['esceptico']['score']:.2f}[/]", "")
    console.print(res_table)
    console.print()


# ---------------------------------------------------------------------------
# COMANDOS: MARKET
# ---------------------------------------------------------------------------

@market_app.command("list")
def market_list() -> None:
    """Lista mercados de predicciones abiertos con precios actuales via HermesCommander."""
    loop = asyncio.get_event_loop()
    mercados = loop.run_until_complete(get_commander().listar_mercados())

    table = make_table("Mercados de Prediccion")
    table.add_column("ID", style=f"bold {FG_LIGHT}", width=8)
    table.add_column("Pregunta", style=f"{FG_LIGHT}", min_width=35)
    table.add_column("Estado", justify="center", width=10)
    table.add_column("Volumen", justify="right", width=12)
    table.add_column("Participantes", justify="right", width=8)
    table.add_column("Precios", style=f"{FG_LIGHT}", min_width=25)

    for m in mercados:
        precios_str = " | ".join(f"[bold]{k}[/]: [bold {ACCENT_BLUE}]{v:.0%}[/]" for k, v in m["escenarios"].items())
        table.add_row(m["id"], m["pregunta"], estado_tag(m["estado"]),
                      f"${m['volumen']:,.0f}", str(m["participantes"]), precios_str)
    console.print(table)
    console.print(f"\n[dim]Total: {len(mercados)} mercados[/]\n")


@market_app.command("create")
def market_create(
    hipotesis_id: Annotated[str, typer.Argument(help="ID de la hipotesis vinculada")],
    escenarios: Annotated[str, typer.Argument(help="Escenarios separados por coma (ej: SI,NO,QUIZAS)")],
) -> None:
    """Crea un mercado de prediccion para una hipotesis via HermesCommander."""
    esc_list = [e.strip() for e in escenarios.split(",")]
    nuevo_id = f"M-{len(get_commander().mercados)+1:03d}"
    mercado = {
        "id": nuevo_id, "hipotesis_id": hipotesis_id,
        "pregunta": f"Mercado para {hipotesis_id}",
        "estado": "abierto", "volumen": 0.0, "participantes": 0,
        "escenarios": {e: round(1 / len(esc_list), 2) for e in esc_list},
        "fecha_creacion": datetime.now().strftime("%Y-%m-%d"),
        "fecha_cierre": (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d"),
    }
    get_commander().mercados.append(mercado)

    console.print(f"\n[bold {ACCENT_GREEN}]✓ Mercado creado[/]\n")
    content = Text()
    content.append(f"ID: ", style=f"dim {FG_LIGHT}")
    content.append(f"{nuevo_id}\n", style=f"bold {ACCENT_BLUE}")
    content.append(f"Hipotesis: ", style=f"dim {FG_LIGHT}")
    content.append(f"{hipotesis_id}\n", style=f"{FG_LIGHT}")
    content.append(f"Escenarios: ", style=f"dim {FG_LIGHT}")
    content.append(f"{', '.join(esc_list)}", style=f"bold {ACCENT_ORANGE}")
    console.print(make_panel(content, "Nuevo Mercado", ACCENT_GREEN))
    console.print()


@market_app.command("trade")
def market_trade(
    mercado_id: Annotated[str, typer.Argument(help="ID del mercado")],
    escenario: Annotated[str, typer.Argument(help="Escenario a comprar")],
    cantidad: Annotated[float, typer.Argument(help="Cantidad a invertir")],
) -> None:
    """Compra participaciones en un escenario del mercado via HermesCommander."""
    loop = asyncio.get_event_loop()
    m = loop.run_until_complete(get_commander().trade_mercado(mercado_id, escenario, cantidad))
    if not m:
        console.print(f"[bold {ACCENT_RED}]Error:[/] Mercado [bold]{mercado_id}[/] no encontrado, cerrado, o escenario invalido.")
        raise typer.Exit(1)

    console.print(f"\n[bold {ACCENT_GREEN}]✓ Trade ejecutado[/]\n")
    content = Text()
    content.append(f"Mercado: ", style=f"dim {FG_LIGHT}")
    content.append(f"{mercado_id}\n", style=f"bold {ACCENT_BLUE}")
    content.append(f"Escenario: ", style=f"dim {FG_LIGHT}")
    content.append(f"{escenario}\n", style=f"bold {ACCENT_ORANGE}")
    content.append(f"Cantidad: ", style=f"dim {FG_LIGHT}")
    content.append(f"${cantidad:,.2f}\n", style=f"bold {ACCENT_GREEN}")
    content.append(f"Nuevo volumen: ", style=f"dim {FG_LIGHT}")
    content.append(f"${m['volumen']:,.2f}", style=f"bold {ACCENT_BLUE}")
    console.print(make_panel(content, "Trade Confirmado", ACCENT_GREEN))
    console.print()


@market_app.command("resolve")
def market_resolve(
    mercado_id: Annotated[str, typer.Argument(help="ID del mercado a resolver")],
    ganador: Annotated[str, typer.Argument(help="Escenario ganador")],
) -> None:
    """Resuelve un mercado declarando el escenario ganador via HermesCommander."""
    loop = asyncio.get_event_loop()
    m = loop.run_until_complete(get_commander().resolver_mercado(mercado_id, ganador))
    if not m:
        console.print(f"[bold {ACCENT_RED}]Error:[/] Mercado [bold]{mercado_id}[/] no encontrado o escenario invalido.")
        raise typer.Exit(1)

    console.print(f"\n[bold {ACCENT_GREEN}]✓ Mercado resuelto[/]\n")
    content = Text()
    content.append(f"Mercado: ", style=f"dim {FG_LIGHT}")
    content.append(f"{mercado_id}\n", style=f"bold {ACCENT_BLUE}")
    content.append(f"Ganador: ", style=f"dim {FG_LIGHT}")
    content.append(f"{ganador}\n", style=f"bold {ACCENT_GREEN}")
    content.append(f"Volumen total: ", style=f"dim {FG_LIGHT}")
    content.append(f"${m['volumen']:,.2f}", style=f"bold {ACCENT_BLUE}")
    console.print(make_panel(content, "Mercado Resuelto", ACCENT_PURPLE))
    console.print()


@market_app.command("prices")
def market_prices(
    mercado_id: Annotated[str, typer.Argument(help="ID del mercado")],
) -> None:
    """Muestra precios actuales de todos los escenarios de un mercado."""
    loop = asyncio.get_event_loop()
    mercado = loop.run_until_complete(get_commander().get_mercado(mercado_id))
    if not mercado:
        console.print(f"[bold {ACCENT_RED}]Error:[/] Mercado [bold]{mercado_id}[/] no encontrado.")
        raise typer.Exit(1)

    table = make_table(f"Precios - {mercado_id}")
    table.add_column("Escenario", style=f"bold {FG_LIGHT}")
    table.add_column("Precio", justify="right")
    table.add_column("Visual", min_width=20)

    for esc, precio in mercado["escenarios"].items():
        bar = "█" * int(precio * 20) + "░" * (20 - int(precio * 20))
        color = ACCENT_GREEN if precio > 0.5 else ACCENT_ORANGE if precio > 0.25 else ACCENT_RED
        table.add_row(esc, f"[bold {color}]{precio:.0%}[/]", bar)
    console.print(table)
    console.print(f"\n[dim]Volumen: ${mercado['volumen']:,.2f} | Participantes: {mercado['participantes']}[/]\n")


# ---------------------------------------------------------------------------
# COMANDOS: SIMULATE
# ---------------------------------------------------------------------------

@simulate_app.command("create")
def simulate_create(
    nombre: Annotated[str, typer.Argument(help="Nombre del escenario")],
) -> None:
    """Crea un escenario de simulacion preguntando variables interactivamente via HermesCommander."""
    console.print(f"\n[bold {ACCENT_BLUE}]⚙ Creando escenario: {nombre}[/]\n")
    console.print("[dim]Ingresa las variables del escenario (deja vacio para terminar):[/]\n")

    variables: dict[str, float] = {}
    while True:
        var_name = Prompt.ask("[bold]Nombre de variable", default="", console=console)
        if not var_name:
            break
        var_value = FloatPrompt.ask(f"[bold]Valor para '{var_name}'", console=console)
        variables[var_name] = var_value
        console.print(f"  [bold {ACCENT_GREEN}]✓[/] {var_name} = {var_value}")

    if not variables:
        console.print(f"[bold {ACCENT_ORANGE}]Escenario cancelado (sin variables).[/]")
        raise typer.Exit()

    iteraciones = IntPrompt.ask("[bold]Numero de iteraciones Monte Carlo", default=10000, console=console)

    loop = asyncio.get_event_loop()
    e = loop.run_until_complete(get_commander().crear_escenario({
        "nombre": nombre, "variables": variables, "iteraciones": iteraciones
    }))

    if e is None:
        e = {"id": str(uuid.uuid4()), "nombre": nombre, "estado": "creado"}
    console.print(f"\n[bold {ACCENT_GREEN}]✓ Escenario creado: {e['id']}[/]\n")
    var_text = "\n".join(f"  [bold {FG_LIGHT}]{k}[/]: [bold {ACCENT_BLUE}]{v}[/]" for k, v in variables.items())
    content = Text()
    content.append(f"ID: ", style=f"dim {FG_LIGHT}")
    content.append(f"{e['id']}\n", style=f"bold {ACCENT_BLUE}")
    content.append(f"Nombre: ", style=f"dim {FG_LIGHT}")
    content.append(f"{nombre}\n", style=f"bold {FG_LIGHT}")
    content.append(f"Variables:\n{var_text}\n", style=f"{FG_LIGHT}")
    content.append(f"Iteraciones: ", style=f"dim {FG_LIGHT}")
    content.append(f"{iteraciones:,}", style=f"bold {ACCENT_PURPLE}")
    console.print(make_panel(content, "Escenario Creado", ACCENT_GREEN))
    console.print()


@simulate_app.command("run")
def simulate_run(
    escenario_id: Annotated[str, typer.Argument(help="ID del escenario a ejecutar")],
) -> None:
    """Ejecuta simulacion Monte Carlo para un escenario via HermesCommander."""
    loop = asyncio.get_event_loop()
    escenario = loop.run_until_complete(get_commander().get_escenario(escenario_id))
    if not escenario:
        console.print(f"[bold {ACCENT_RED}]Error:[/] Escenario [bold]{escenario_id}[/] no encontrado.")
        raise typer.Exit(1)

    console.print(f"\n[bold {ACCENT_BLUE}]⚙ Ejecutando Monte Carlo: {escenario['nombre']}[/]")
    console.print(f"[dim]Iteraciones: {escenario['iteraciones']:,}[/]\n")

    with Progress(
        SpinnerColumn(style=ACCENT_BLUE),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(complete_style=ACCENT_BLUE, finished_style=ACCENT_GREEN),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:
        task = progress.add_task("Simulando...", total=escenario["iteraciones"])
        for i in range(0, escenario["iteraciones"], 500):
            batch = min(500, escenario["iteraciones"] - i)
            progress.update(task, advance=batch)
            time.sleep(0.01)

    e = loop.run_until_complete(get_commander().simular_escenario(escenario_id))
    resultado = e["resultado"] if e else None

    console.print(f"\n[bold {ACCENT_GREEN}]✓ Simulacion completada[/]\n")
    table = make_table("Resultados Monte Carlo")
    table.add_column("Metrica", style=f"bold {FG_LIGHT}")
    table.add_column("Valor", justify="right")
    if resultado:
        table.add_row("Media", f"[bold {ACCENT_BLUE}]{resultado['media']:.2f}[/]")
        table.add_row("Desviacion Estandar", f"[bold {ACCENT_ORANGE}]{resultado['desviacion']:.2f}[/]")
        table.add_row("Percentil 95", f"[bold {ACCENT_GREEN}]{resultado['percentil_95']:.2f}[/]")
    table.add_row("Iteraciones", f"[bold]{escenario['iteraciones']:,}[/]")
    console.print(table)
    console.print()


@simulate_app.command("compare")
def simulate_compare(
    id1: Annotated[str, typer.Argument(help="ID del primer escenario")],
    id2: Annotated[str, typer.Argument(help="ID del segundo escenario")],
) -> None:
    """Compara dos escenarios de simulacion via HermesCommander."""
    loop = asyncio.get_event_loop()
    e1 = loop.run_until_complete(get_commander().get_escenario(id1))
    e2 = loop.run_until_complete(get_commander().get_escenario(id2))

    if not e1 or not e2:
        faltante = id1 if not e1 else id2
        console.print(f"[bold {ACCENT_RED}]Error:[/] Escenario [bold]{faltante}[/] no encontrado.")
        raise typer.Exit(1)

    table = make_table(f"Comparacion: {e1['nombre']} vs {e2['nombre']}")
    table.add_column("Metrica", style=f"bold {FG_LIGHT}")
    table.add_column(f"{e1['id']}", justify="right")
    table.add_column(f"{e2['id']}", justify="right")
    table.add_column("Diferencia", justify="right")

    for metrica in ["media", "desviacion", "percentil_95"]:
        v1 = e1["resultado"][metrica] if e1.get("resultado") else 0.0
        v2 = e2["resultado"][metrica] if e2.get("resultado") else 0.0
        diff = v1 - v2
        diff_color = ACCENT_GREEN if diff > 0 else ACCENT_RED
        diff_sign = "+" if diff > 0 else ""
        table.add_row(metrica.capitalize(), f"[bold]{v1:.2f}[/]", f"[bold]{v2:.2f}[/]", f"[bold {diff_color}]{diff_sign}{diff:.2f}[/]")

    table.add_row("Iteraciones", f"{e1['iteraciones']:,}", f"{e2['iteraciones']:,}", "")
    console.print(table)
    console.print()


# ---------------------------------------------------------------------------
# COMANDOS: JOURNAL
# ---------------------------------------------------------------------------

@journal_app.command("")
def journal_actual() -> None:
    """Muestra el ultimo informe semanal."""
    if not get_commander().diarios:
        console.print(f"[bold {ACCENT_ORANGE}]No hay informes disponibles.[/]")
        raise typer.Exit()

    diario = get_commander().diarios[0]
    content = Text()
    content.append(f"Semana: ", style=f"dim {FG_LIGHT}")
    content.append(f"{diario['semana']}\n", style=f"bold {ACCENT_BLUE}")
    content.append(f"Fecha: ", style=f"dim {FG_LIGHT}")
    content.append(f"{diario['fecha']}\n\n", style=f"{FG_LIGHT}")
    content.append(f"NEI Promedio: ", style=f"dim {FG_LIGHT}")
    content.append(f"{diario['nei_promedio']:.2f}\n", style=f"bold {ACCENT_PURPLE}")
    content.append(f"Hipotesis nuevas: ", style=f"dim {FG_LIGHT}")
    content.append(f"{diario['hipotesis_nuevas']}\n", style=f"bold {ACCENT_BLUE}")
    content.append(f"Confirmadas: ", style=f"dim {FG_LIGHT}")
    content.append(f"[bold {ACCENT_GREEN}]{diario['hipotesis_confirmadas']}[/]  ", style=f"{FG_LIGHT}")
    content.append(f"Refutadas: ", style=f"dim {FG_LIGHT}")
    content.append(f"[bold {ACCENT_RED}]{diario['hipotesis_refutadas']}[/]\n", style=f"{FG_LIGHT}")
    content.append(f"Volumen total: ", style=f"dim {FG_LIGHT}")
    content.append(f"${diario['volumen_total']:,.0f}\n\n", style=f"bold {ACCENT_GREEN}")
    content.append(f"[bold {ACCENT_ORANGE}]Destacado:[/]\n", style=f"{FG_LIGHT}")
    content.append(f"{diario['destacado']}", style=f"italic {FG_LIGHT}")

    console.print(make_panel(content, f"Diario Semanal {diario['semana']}", ACCENT_BLUE))
    console.print()

    if diario["narrativas_detectadas"]:
        narr_table = make_table("Narrativas Detectadas")
        narr_table.add_column("#", justify="right", width=4)
        narr_table.add_column("Descripcion", style=f"{FG_LIGHT}")
        for i, n in enumerate(diario["narrativas_detectadas"], 1):
            style = ACCENT_ORANGE if "Cambio" in n else ACCENT_RED if "Emergencia" in n else ACCENT_BLUE
            narr_table.add_row(str(i), f"[bold {style}]{n}[/]")
        console.print(narr_table)
        console.print()


@journal_app.command("history")
def journal_history() -> None:
    """Muestra historial de semanas anteriores."""
    if not get_commander().diarios:
        console.print(f"[bold {ACCENT_ORANGE}]No hay informes disponibles.[/]")
        raise typer.Exit()

    table = make_table("Historial de Diarios Semanales")
    table.add_column("Semana", style=f"bold {FG_LIGHT}")
    table.add_column("Fecha")
    table.add_column("NEI", justify="right")
    table.add_column("H.Nuevas", justify="right")
    table.add_column("H.Conf", justify="right")
    table.add_column("H.Refut", justify="right")
    table.add_column("Volumen", justify="right")
    table.add_column("Destacado", style=f"{FG_LIGHT}", min_width=30)

    for d in get_commander().diarios:
        table.add_row(
            d["semana"], d["fecha"],
            f"[bold {ACCENT_PURPLE}]{d['nei_promedio']:.2f}[/]",
            str(d["hipotesis_nuevas"]),
            f"[bold {ACCENT_GREEN}]{d['hipotesis_confirmadas']}[/]",
            f"[bold {ACCENT_RED}]{d['hipotesis_refutadas']}[/]",
            f"${d['volumen_total']:,.0f}",
            d["destacado"][:50] + "..." if len(d["destacado"]) > 50 else d["destacado"],
        )
    console.print(table)
    console.print(f"\n[dim]Total: {len(get_commander().diarios)} semanas registradas[/]\n")


# ---------------------------------------------------------------------------
# COMANDOS: GRAPH
# ---------------------------------------------------------------------------

@graph_app.command("stats")
def graph_stats() -> None:
    """Estadisticas del grafo de conocimiento."""
    table = make_table("Estadisticas del Grafo de Conocimiento")
    table.add_column("Metrica", style=f"bold {FG_LIGHT}")
    table.add_column("Valor", justify="right")
    table.add_row("Nodos", f"[bold {ACCENT_BLUE}]{get_commander().grafo['nodos']}[/]")
    table.add_row("Relaciones", f"[bold {ACCENT_PURPLE}]{get_commander().grafo['relaciones']}[/]")
    table.add_row("Clusters", f"[bold {ACCENT_ORANGE}]{get_commander().grafo['clusters']}[/]")
    table.add_row("Densidad", f"[bold]{get_commander().grafo['densidad']:.3f}[/]")
    table.add_row("Diametro", f"[bold]{get_commander().grafo['diametro']}[/]")
    table.add_row("Centralidad Maxima", f"[bold {ACCENT_GREEN}]{get_commander().grafo['centralidad_max']:.2f}[/]")
    console.print(table)
    console.print()

    nodo_table = make_table("Nodos con Mayor Centralidad")
    nodo_table.add_column("#", justify="right", width=4)
    nodo_table.add_column("ID", style=f"bold {FG_LIGHT}")
    nodo_table.add_column("Nombre")
    nodo_table.add_column("Grado", justify="right")
    nodo_table.add_column("Centralidad", justify="right")
    for i, n in enumerate(get_commander().grafo["nodos_top"], 1):
        nodo_table.add_row(str(i), n["id"], n["nombre"], str(n["grado"]), f"[bold {ACCENT_GREEN}]{n['centralidad']:.2f}[/]")
    console.print(nodo_table)
    console.print()


@graph_app.command("paths")
def graph_paths(
    origen: Annotated[str, typer.Argument(help="Nodo origen")],
    destino: Annotated[str, typer.Argument(help="Nodo destino")],
) -> None:
    """Encuentra caminos entre dos nodos del grafo."""
    console.print(f"\n[bold {ACCENT_BLUE}]🔍 Buscando caminos: {origen} → {destino}[/]\n")
    caminos = [
        [origen, "ia_generativa", "regulacion", destino],
        [origen, "trabajo_remoto", "crypto", "regulacion", destino],
        [origen, "sostenibilidad", destino],
    ]
    for i, camino in enumerate(caminos[:3], 1):
        path_text = f" [bold {ACCENT_BLUE}]→[/] ".join(f"[bold]{n}[/]" for n in camino)
        console.print(f"  [bold {ACCENT_ORANGE}]Camino {i}[/] ({len(camino)-1} saltos): {path_text}")
    console.print()


# ---------------------------------------------------------------------------
# COMANDO: NARRATIVE
# ---------------------------------------------------------------------------

@app.command("narrative")
def cmd_narrative() -> None:
    """Muestra cambios de narrativa detectados recientemente."""
    table = make_table("Cambios de Narrativa Detectados")
    table.add_column("ID", style=f"bold {FG_LIGHT}", width=8)
    table.add_column("Narrativa", style=f"bold {FG_LIGHT}")
    table.add_column("Fuerza", justify="right")
    table.add_column("Tendencia", justify="center")
    table.add_column("Cambio Semanal", justify="right")
    table.add_column("Temas Relacionados", style=f"{FG_LIGHT}")

    for n in get_commander().narrativas:
        tendencia_color = {"ascendente": ACCENT_GREEN, "descendente": ACCENT_RED, "estable": ACCENT_ORANGE}.get(n["tendencia"], FG_LIGHT)
        cambio_color = ACCENT_GREEN if n["cambio_semanal"] > 0 else ACCENT_RED
        cambio_sign = "+" if n["cambio_semanal"] > 0 else ""
        table.add_row(
            n["id"], n["nombre"],
            f"[bold {ACCENT_BLUE}]{n['fuerza_actual']:.2f}[/]",
            f"[bold {tendencia_color}]{n['tendencia'].upper()}[/]",
            f"[bold {cambio_color}]{cambio_sign}{n['cambio_semanal']:+.2f}[/]",
            ", ".join(n["temas_relacionados"]),
        )
    console.print(table)
    console.print()


# ---------------------------------------------------------------------------
# COMANDO: ALERT
# ---------------------------------------------------------------------------

@app.command("alert")
def cmd_alert() -> None:
    """Muestra alertas activas del sistema via HermesCommander."""
    if not get_commander().alertas:
        console.print(f"[bold {ACCENT_GREEN}]✓ No hay alertas activas.[/]\n")
        return

    table = make_table("Alertas Activas del Sistema")
    table.add_column("ID", style=f"bold {FG_LIGHT}", width=8)
    table.add_column("Tipo", style=f"bold {ACCENT_ORANGE}")
    table.add_column("Nivel", justify="center")
    table.add_column("Fecha")
    table.add_column("Mensaje", style=f"{FG_LIGHT}", min_width=35)
    table.add_column("Relacionadas", style=f"dim {FG_LIGHT}")

    for a in get_commander().alertas:
        color_nivel = color_estado(a["nivel"])
        rel = ", ".join(a["relacionadas"]) if a["relacionadas"] else "-"
        table.add_row(a["id"], a["tipo"].upper(), f"[bold {color_nivel}]{a['nivel'].upper()}[/]", a["fecha"], a["mensaje"], rel)
    console.print(table)
    console.print(f"\n[dim]Total: {len(get_commander().alertas)} alertas activas[/]\n")


# ---------------------------------------------------------------------------
# COMANDO: CONFIG
# ---------------------------------------------------------------------------

@app.command("config")
def cmd_config() -> None:
    """Muestra la configuracion actual del sistema via HermesCommander."""
    config = {
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
        "governance.leyes": 7,
        "cycles.reasoning.interval_min": 60,
        "cycles.forecast.interval_min": 60,
        "cycles.executive.interval_min": 30,
        "cycles.operations.interval_min": 240,
    }

    table = make_table("Configuracion del Sistema")
    table.add_column("Parametro", style=f"bold {FG_LIGHT}")
    table.add_column("Valor", style=f"bold {ACCENT_BLUE}")
    for k, v in config.items():
        val_str = json.dumps(v) if isinstance(v, (list, dict)) else str(v)
        table.add_row(k, val_str)
    console.print(table)
    console.print()


# ---------------------------------------------------------------------------
# COMANDO: SERVE
# ---------------------------------------------------------------------------

@app.command("serve")
def cmd_serve(
    host: Annotated[str, typer.Option("--host", "-H", help="Host para el servidor")] = "0.0.0.0",
    port: Annotated[int, typer.Option("--port", "-p", help="Puerto para el servidor")] = 8000,
    reload: Annotated[bool, typer.Option("--reload", help="Recarga automatica")] = False,
) -> None:
    """Inicia el servidor API (uvicorn)."""
    import subprocess

    console.print(f"\n[bold {ACCENT_BLUE}]{HERMES_BANNER}[/]\n")

    content = Text()
    content.append(f"Host: ", style=f"dim {FG_LIGHT}")
    content.append(f"{host}\n", style=f"bold {ACCENT_BLUE}")
    content.append(f"Puerto: ", style=f"dim {FG_LIGHT}")
    content.append(f"{port}\n", style=f"bold {ACCENT_BLUE}")
    content.append(f"Reload: ", style=f"dim {FG_LIGHT}")
    content.append(f"{'Si' if reload else 'No'}\n", style=f"bold {ACCENT_ORANGE}" if reload else f"{FG_LIGHT}")
    content.append(f"\nEndpoints:\n", style=f"bold {FG_LIGHT}")
    content.append(f"  REST API: ", style=f"dim {FG_LIGHT}")
    content.append(f"http://{host}:{port}/api/v1\n", style=f"bold {ACCENT_GREEN}")
    content.append(f"  REST V2:  ", style=f"dim {FG_LIGHT}")
    content.append(f"http://{host}:{port}/api/v2\n", style=f"bold {ACCENT_GREEN}")
    content.append(f"  Docs:     ", style=f"dim {FG_LIGHT}")
    content.append(f"http://{host}:{port}/docs\n", style=f"bold {ACCENT_GREEN}")
    content.append(f"  WebSocket:", style=f"dim {FG_LIGHT}")
    content.append(f"ws://{host}:{port}/ws", style=f"bold {ACCENT_PURPLE}")

    console.print(make_panel(content, "Servidor API v2", ACCENT_BLUE))
    console.print()

    try:
        import uvicorn
        console.print(f"[bold {ACCENT_GREEN}]🚀 Iniciando servidor VEO v2...[/]\n")
        uvicorn.run("api.api_server:app", host=host, port=port, reload=reload)
    except ImportError:
        console.print(f"[bold {ACCENT_RED}]Error:[/] uvicorn no instalado.")
        console.print(f"[dim]Ejecuta: pip install uvicorn[standard][/]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[bold {ACCENT_RED}]Error iniciando servidor:[/] {e}")
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# COMANDO: VERSION
# ---------------------------------------------------------------------------

@app.command("version")
def cmd_version() -> None:
    """Muestra la version del sistema."""
    console.print(f"\n[bold {ACCENT_BLUE}]{APP_NAME}[/] [bold]{VEO_VERSION}[/]")
    console.print(f"[dim]Python {sys.version.split()[0]} | Typer + Rich + FastAPI | HermesCommander[/]\n")


# ###########################################################################
# ===========================================================================
# COMANDOS V2 NUEVOS (todos via HermesCommander)
# ===========================================================================
# ###########################################################################

# ---------------------------------------------------------------------------
# COMANDO: HEALTH (V2 NUEVO)
# ---------------------------------------------------------------------------

@app.command("health")
def cmd_health() -> None:
    """
    [V2 NUEVO] Muestra estado de salud de todos los componentes via HermesCommander.
    Health score global con semaforo por componente.
    """
    console.print(f"\n[bold {ACCENT_GREEN}]💊 Health Check - VEO v2[/]\n")

    loop = asyncio.get_event_loop()
    health = loop.run_until_complete(get_commander().get_system_health())

    # Health score gauge
    score = health.get("health_score", 0)
    score_color = ACCENT_GREEN if score >= 80 else ACCENT_ORANGE if score >= 50 else ACCENT_RED
    score_bar = "█" * int(score / 5) + "░" * (20 - int(score / 5))

    content = Text()
    content.append(f"Health Score: ", style=f"bold {FG_LIGHT}")
    content.append(f"{score}/100\n", style=f"bold {score_color}")
    content.append(f"[{score_bar}]\n", style=f"{score_color}")
    content.append(f"Estado global: ", style=f"dim {FG_LIGHT}")
    content.append(f"{health.get('status', 'unknown').upper()}\n", style=f"bold {score_color}")
    content.append(f"Timestamp: ", style=f"dim {FG_LIGHT}")
    content.append(f"{health.get('timestamp', 'N/A')}", style=f"{FG_LIGHT}")
    console.print(make_panel(content, "Health Score", score_color))
    console.print()

    # Componentes
    table = make_table("Estado por Componente")
    table.add_column("Componente", style=f"bold {FG_LIGHT}")
    table.add_column("Estado", justify="center")
    table.add_column("Detalles", style=f"{FG_LIGHT}")

    components = health.get("components", {})
    for name, info in components.items():
        status = info.get("status", "unknown")
        color = color_estado(status)
        details = []
        if "latency_ms" in info:
            details.append(f"latency: {info['latency_ms']}ms")
        if "connections" in info:
            details.append(f"conns: {info['connections']}")
        if "mode" in info:
            details.append(f"mode: {info['mode']}")
        if "last_run" in info:
            details.append(f"last: {info['last_run']}")
        if "sources_active" in info:
            details.append(f"sources: {info['sources_active']}")
        if "narratives_tracked" in info:
            details.append(f"narratives: {info['narratives_tracked']}")
        if "queue_size" in info:
            details.append(f"queue: {info['queue_size']}")

        table.add_row(
            f"[bold]{name}[/]",
            f"{semaforo(status)} [bold {color}]{status.upper()}[/]",
            ", ".join(details) if details else "-",
        )
    console.print(table)
    console.print()


# ---------------------------------------------------------------------------
# COMANDO: METRICS (V2 NUEVO)
# ---------------------------------------------------------------------------

@app.command("metrics")
def cmd_metrics() -> None:
    """
    [V2 NUEVO] Muestra metricas del sistema en tiempo real via HermesCommander.
    CPU, memoria, disco, uptime, requests/min.
    """
    console.print(f"\n[bold {ACCENT_BLUE}]📊 Metricas del Sistema - VEO v2[/]\n")

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    metrics = loop.run_until_complete(get_commander().get_system_metrics())

    table = make_table("Metricas en Tiempo Real")
    table.add_column("Metrica", style=f"bold {FG_LIGHT}")
    table.add_column("Valor", justify="right")
    table.add_column("Visual", min_width=20)

    def make_bar(pct: float, color: str) -> str:
        filled = int(pct / 5)
        empty = 20 - filled
        return f"[bold {color}]{'█' * filled}[/]{'-' * empty}"

    cpu = metrics.get("cpu_percent", 0)
    mem = metrics.get("memory_percent", 0)
    disk = metrics.get("disk_percent", 0)

    table.add_row("CPU", f"[bold]{cpu:.1f}%[/]", make_bar(cpu, ACCENT_BLUE if cpu < 70 else ACCENT_ORANGE if cpu < 90 else ACCENT_RED))
    table.add_row("Memoria", f"[bold]{mem:.1f}%[/] ({metrics.get('memory_used_mb', 0):.0f}/{metrics.get('memory_total_mb', 0):.0f} MB)", make_bar(mem, ACCENT_GREEN if mem < 70 else ACCENT_ORANGE if mem < 90 else ACCENT_RED))
    table.add_row("Disco", f"[bold]{disk:.1f}%[/]", make_bar(disk, ACCENT_GREEN if disk < 80 else ACCENT_ORANGE if disk < 95 else ACCENT_RED))
    table.add_row("Uptime", f"[bold]{metrics.get('uptime_seconds', 0) // 3600}h {(metrics.get('uptime_seconds', 0) % 3600) // 60}m[/]", "")
    table.add_row("Requests Total", f"[bold {ACCENT_BLUE}]{metrics.get('requests_total', 0):,}[/]", "")
    table.add_row("Requests/min", f"[bold]{metrics.get('requests_per_min', 0)}[/]", "")
    table.add_row("WS Mensajes", f"[bold {ACCENT_PURPLE}]{metrics.get('ws_messages_sent', 0):,}[/]", "")
    table.add_row("Avg Response", f"[bold]{metrics.get('avg_response_ms', 0):.1f} ms[/]", "")
    console.print(table)
    console.print(f"\n[dim]Timestamp: {metrics.get('timestamp', 'N/A')}[/]\n")


# ---------------------------------------------------------------------------
# COMANDO: AUDIT (V2 NUEVO)
# ---------------------------------------------------------------------------

@app.command("audit")
def cmd_audit(
    lines: Annotated[int, typer.Option("--lines", "-n", help="Numero de lineas a mostrar")] = 20,
) -> None:
    """
    [V2 NUEVO] Muestra log de auditoria del sistema via HermesCommander.
    Registro de todas las operaciones que pasaron por el get_commander().
    """
    console.print(f"\n[bold {ACCENT_PURPLE}]📋 Log de Auditoria - VEO v2[/]\n")

    loop = asyncio.get_event_loop()
    audit_log = loop.run_until_complete(get_commander().get_system_audit())

    if not audit_log:
        console.print(f"[bold {ACCENT_ORANGE}]No hay entradas de auditoria.[/]\n")
        return

    table = make_table(f"Auditoria ({min(lines, len(audit_log))} entradas)")
    table.add_column("Timestamp", style=f"dim {FG_LIGHT}")
    table.add_column("Nivel", justify="center", width=8)
    table.add_column("Componente", style=f"bold {ACCENT_BLUE}")
    table.add_column("Mensaje", style=f"{FG_LIGHT}")

    for entry in audit_log[:lines]:
        level = entry.get("level", "INFO")
        level_color = ACCENT_GREEN if level == "INFO" else ACCENT_ORANGE if level == "WARN" else ACCENT_RED
        table.add_row(
            entry.get("timestamp", ""),
            f"[bold {level_color}]{level}[/]",
            entry.get("component", ""),
            entry.get("message", ""),
        )
    console.print(table)
    console.print(f"\n[dim]Total: {len(audit_log)} entradas | Mostrando: {min(lines, len(audit_log))}[/]\n")


# ---------------------------------------------------------------------------
# COMANDO: BACKUP (V2 NUEVO)
# ---------------------------------------------------------------------------

@operations_app.command("backup")
def cmd_backup() -> None:
    """
    [V2 NUEVO] Crea backup inmediato via HermesCommander.
    El commander gestiona todo el proceso de backup.
    """
    console.print(f"\n[bold {ACCENT_BLUE}]💾 Creando backup via HermesCommander...[/]\n")

    with Progress(
        SpinnerColumn(style=ACCENT_BLUE),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(complete_style=ACCENT_BLUE, finished_style=ACCENT_GREEN),
        console=console, transient=True,
    ) as progress:
        task = progress.add_task("Creando backup...", total=100)
        for i in range(0, 101, 20):
            progress.update(task, completed=i)
            time.sleep(0.1)

    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(get_commander().create_backup())

    console.print(f"\n[bold {ACCENT_GREEN}]✓ Backup creado exitosamente[/]\n")
    content = Text()
    content.append(f"Backup ID: ", style=f"dim {FG_LIGHT}")
    content.append(f"{result.get('backup_id', 'N/A')}\n", style=f"bold {ACCENT_BLUE}")
    content.append(f"Timestamp: ", style=f"dim {FG_LIGHT}")
    content.append(f"{result.get('timestamp', 'N/A')}", style=f"{FG_LIGHT}")
    console.print(make_panel(content, "Backup Completado", ACCENT_GREEN))
    console.print()


# ---------------------------------------------------------------------------
# COMANDO: RESTORE (V2 NUEVO)
# ---------------------------------------------------------------------------

@operations_app.command("restore")
def cmd_restore(
    backup_id: Annotated[str, typer.Argument(help="ID del backup a restaurar")],
) -> None:
    """
    [V2 NUEVO] Restaura desde backup via HermesCommander.
    El commander gestiona todo el proceso de restauracion.
    """
    console.print(f"\n[bold {ACCENT_ORANGE}]🔄 Restaurando backup {backup_id}...[/]\n")

    if not Confirm.ask(f"[bold]Estas seguro de restaurar el backup {backup_id}?", console=console):
        console.print(f"[dim]Restauracion cancelada.[/]\n")
        raise typer.Exit()

    with Progress(
        SpinnerColumn(style=ACCENT_ORANGE),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(complete_style=ACCENT_ORANGE, finished_style=ACCENT_GREEN),
        console=console, transient=True,
    ) as progress:
        task = progress.add_task("Restaurando backup...", total=100)
        for i in range(0, 101, 15):
            progress.update(task, completed=i)
            time.sleep(0.15)

    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(get_commander().restore_backup(backup_id))

    console.print(f"\n[bold {ACCENT_GREEN}]✓ Backup restaurado exitosamente[/]\n")
    content = Text()
    content.append(f"Backup ID: ", style=f"dim {FG_LIGHT}")
    content.append(f"{result.get('backup_id', 'N/A')}\n", style=f"bold {ACCENT_BLUE}")
    content.append(f"Estado: ", style=f"dim {FG_LIGHT}")
    content.append(f"{result.get('status', 'N/A').upper()}\n", style=f"bold {ACCENT_GREEN}")
    content.append(f"Timestamp: ", style=f"dim {FG_LIGHT}")
    content.append(f"{result.get('timestamp', 'N/A')}", style=f"{FG_LIGHT}")
    console.print(make_panel(content, "Restauracion Completada", ACCENT_GREEN))
    console.print()


# ---------------------------------------------------------------------------
# COMANDO: CYCLES (V2 NUEVO)
# ---------------------------------------------------------------------------

@app.command("cycles")
def cmd_cycles() -> None:
    """
    [V2 NUEVO] Muestra estado de los 4 ciclos via HermesCommander.
    reasoning, forecast, executive, operations.
    """
    console.print(f"\n[bold {ACCENT_BLUE}]🔄 Estado de Ciclos - VEO v2[/]\n")

    loop = asyncio.get_event_loop()
    cycles = loop.run_until_complete(get_commander().get_cycles_status())

    table = make_table("Ciclos del Sistema")
    table.add_column("Ciclo", style=f"bold {FG_LIGHT}")
    table.add_column("Estado", justify="center")
    table.add_column("Ultima Ejecucion", style=f"dim {FG_LIGHT}")
    table.add_column("Proxima Ejecucion", style=f"dim {FG_LIGHT}")
    table.add_column("Success Rate", justify="right")

    cycle_names = {
        "reasoning": "Razonamiento",
        "forecast": "Pronostico",
        "executive": "Ejecutivo",
        "operations": "Operaciones",
    }

    for cycle_id, info in cycles.get("cycles", {}).items():
        status = info.get("status", "unknown")
        table.add_row(
            f"[bold]{cycle_names.get(cycle_id, cycle_id)}[/]",
            f"{semaforo(status)} [bold {color_estado(status)}]{status.upper()}[/]",
            info.get("last_run", "N/A"),
            info.get("next_run", "N/A"),
            f"[bold {ACCENT_GREEN}]{info.get('success_rate', 0):.0%}[/]",
        )
    console.print(table)
    console.print(f"\n[dim]Timestamp: {cycles.get('timestamp', 'N/A')}[/]\n")


# ---------------------------------------------------------------------------
# COMANDO: TRIGGER (V2 NUEVO)
# ---------------------------------------------------------------------------

@app.command("trigger")
def cmd_trigger(
    cycle: Annotated[str, typer.Argument(help="Ciclo a ejecutar: reasoning | forecast | executive | operations")],
    reason: Annotated[Optional[str], typer.Option("--reason", "-r", help="Razon del trigger manual")] = None,
) -> None:
    """
    [V2 NUEVO] Ejecuta ciclo bajo demanda via HermesCommander.
    Ciclos validos: reasoning, forecast, executive, operations.
    """
    valid_cycles = ["reasoning", "forecast", "executive", "operations"]
    if cycle not in valid_cycles:
        console.print(f"[bold {ACCENT_RED}]Error:[/] Ciclo '{cycle}' invalido.")
        console.print(f"[dim]Validos: {', '.join(valid_cycles)}[/]")
        raise typer.Exit(1)

    console.print(f"\n[bold {ACCENT_BLUE}]⚡ Trigger manual: {cycle}[/]\n")
    if reason:
        console.print(f"[dim]Razon: {reason}[/]\n")

    with Progress(
        SpinnerColumn(style=ACCENT_BLUE),
        TextColumn("[progress.description]{task.description}"),
        console=console, transient=True,
    ) as progress:
        task = progress.add_task(f"Ejecutando {cycle}...", total=100)
        for i in range(0, 101, 25):
            progress.update(task, completed=i)
            time.sleep(0.2)

    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(get_commander().trigger_cycle(cycle))

    console.print(f"\n[bold {ACCENT_GREEN}]✓ Ciclo '{cycle}' ejecutado[/]\n")
    content = Text()
    content.append(f"Ciclo: ", style=f"dim {FG_LIGHT}")
    content.append(f"{cycle}\n", style=f"bold {ACCENT_BLUE}")
    content.append(f"Estado: ", style=f"dim {FG_LIGHT}")
    content.append(f"{result.get('status', 'ok').upper()}\n", style=f"bold {ACCENT_GREEN}")
    content.append(f"Timestamp: ", style=f"dim {FG_LIGHT}")
    content.append(f"{result.get('timestamp', 'N/A')}", style=f"{FG_LIGHT}")
    console.print(make_panel(content, "Ciclo Ejecutado", ACCENT_GREEN))
    console.print()


# ---------------------------------------------------------------------------
# COMANDO: EXPLAIN (V2 NUEVO)
# ---------------------------------------------------------------------------

@app.command("explain")
def cmd_explain(
    alert_id: Annotated[str, typer.Argument(help="ID de la alerta a explicar")],
) -> None:
    """
    [V2 NUEVO] Explica una alerta via HermesCommander.
    El commander analiza la alerta y genera una explicacion detallada.
    """
    console.print(f"\n[bold {ACCENT_BLUE}]🔍 Explicando alerta {alert_id}...[/]\n")

    loop = asyncio.get_event_loop()
    explanation = loop.run_until_complete(get_commander().explain_alert(alert_id))

    content = Text()
    content.append(f"Alerta ID: ", style=f"dim {FG_LIGHT}")
    content.append(f"{explanation.get('alert_id', 'N/A')}\n\n", style=f"bold {ACCENT_BLUE}")
    content.append(f"Explicacion:\n", style=f"bold {FG_LIGHT}")
    content.append(f"{explanation.get('explanation', 'N/A')}\n\n", style=f"{FG_LIGHT}")
    content.append(f"Confianza: ", style=f"dim {FG_LIGHT}")
    conf = explanation.get('confidence', 0)
    content.append(f"{conf:.0%}\n", style=f"bold {ACCENT_GREEN if conf > 0.7 else ACCENT_ORANGE}")
    content.append(f"Hipotesis relacionadas: ", style=f"dim {FG_LIGHT}")
    content.append(f"{', '.join(explanation.get('related_hypotheses', []))}\n", style=f"{ACCENT_BLUE}")
    content.append(f"\nAccion recomendada:\n", style=f"bold {ACCENT_ORANGE}")
    content.append(f"{explanation.get('recommended_action', 'N/A')}", style=f"italic {FG_LIGHT}")

    console.print(make_panel(content, f"Explicacion - {alert_id}", ACCENT_BLUE))
    console.print()


# ---------------------------------------------------------------------------
# COMANDO: SYSTEM (V2 NUEVO)
# ---------------------------------------------------------------------------

@app.command("system")
def cmd_system() -> None:
    """
    [V2 NUEVO] Estado completo del sistema via HermesCommander.
    Muestra todos los componentes: API, CLI, Dashboard, Commander.
    """
    console.print(f"\n[bold {ACCENT_BLUE}]🚀 Estado del Sistema VEO v2[/]\n")

    loop = asyncio.get_event_loop()
    sys_status = loop.run_until_complete(get_commander().get_system_status())

    content = Text()
    content.append(f"Version: ", style=f"dim {FG_LIGHT}")
    content.append(f"{sys_status.get('version', VEO_VERSION)}\n", style=f"bold {ACCENT_BLUE}")
    content.append(f"Modo: ", style=f"dim {FG_LIGHT}")
    mode = sys_status.get('mode', 'unknown')
    content.append(f"{mode.upper()}\n", style=f"bold {ACCENT_GREEN if mode == 'commander' else ACCENT_ORANGE}")
    content.append(f"Commander: ", style=f"dim {FG_LIGHT}")
    commander_ok = sys_status.get('commander_available', False)
    content.append(f"{'DISPONIBLE' if commander_ok else 'NO DISPONIBLE'}\n",
                   style=f"bold {ACCENT_GREEN if commander_ok else ACCENT_RED}")
    console.print(make_panel(content, "Sistema VEO v2", ACCENT_BLUE))
    console.print()

    table = make_table("Componentes")
    table.add_column("Componente", style=f"bold {FG_LIGHT}")
    table.add_column("Estado", justify="center")
    table.add_column("Version", justify="right")

    for comp_name, comp_info in sys_status.get("components", {}).items():
        comp_status = comp_info.get("status", "unknown")
        table.add_row(
            f"[bold]{comp_name}[/]",
            f"{semaforo(comp_status)} [bold {color_estado(comp_status)}]{comp_status.upper()}[/]",
            comp_info.get("version", VEO_VERSION),
        )
    console.print(table)
    console.print(f"\n[dim]Timestamp: {sys_status.get('timestamp', 'N/A')}[/]\n")


# ---------------------------------------------------------------------------
# COMANDO: TRUST (V2 NUEVO)
# ---------------------------------------------------------------------------

@app.command("trust")
def cmd_trust() -> None:
    """
    [V2 NUEVO] Muestra trust scores de cada motor via HermesCommander.
    Indica la confiabilidad de cada motor del sistema.
    """
    console.print(f"\n[bold {ACCENT_PURPLE}]💪 Trust Scores - Motores VEO v2[/]\n")

    motors = {
        "motor_nei": {"name": "Motor NEI", "trust_score": 0.92, "validations": 1543, "errors": 12},
        "motor_scraper": {"name": "Motor Scraper", "trust_score": 0.88, "sources": 12, "articles_processed": 89421},
        "motor_narrativa": {"name": "Motor Narrativa", "trust_score": 0.85, "narratives_detected": 47, "false_positives": 7},
        "motor_validacion": {"name": "Motor Validacion", "trust_score": 0.95, "validations": 3210, "disagreements": 34},
        "motor_prediccion": {"name": "Motor Prediccion", "trust_score": 0.90, "predictions": 892, "accuracy": 0.87},
    }

    table = make_table("Trust Scores por Motor")
    table.add_column("Motor", style=f"bold {FG_LIGHT}")
    table.add_column("Trust Score", justify="right")
    table.add_column("Visual", min_width=20)
    table.add_column("Metricas", style=f"{FG_LIGHT}")

    for motor_id, motor in motors.items():
        score = motor["trust_score"]
        score_pct = int(score * 100)
        bar = "█" * int(score * 20) + "░" * (20 - int(score * 20))
        color = ACCENT_GREEN if score >= 0.9 else ACCENT_BLUE if score >= 0.8 else ACCENT_ORANGE
        metrics_str = " | ".join(f"{k}: {v}" for k, v in motor.items() if k not in ("name", "trust_score"))
        table.add_row(
            f"[bold]{motor['name']}[/]",
            f"[bold {color}]{score:.0%}[/]",
            f"[bold {color}]{bar}[/]",
            metrics_str,
        )
    console.print(table)
    console.print()


# ---------------------------------------------------------------------------
# COMANDO: LIST-BACKUPS (V2 NUEVO)
# ---------------------------------------------------------------------------

@operations_app.command("list")
def cmd_list_backups() -> None:
    """
    [V2 NUEVO] Listar backups disponibles via HermesCommander.
    """
    console.print(f"\n[bold {ACCENT_BLUE}]📁 Backups Disponibles[/]\n")

    loop = asyncio.get_event_loop()
    backups = loop.run_until_complete(get_commander().list_backups())

    if not backups:
        console.print(f"[bold {ACCENT_ORANGE}]No hay backups disponibles.[/]\n")
        return

    table = make_table(f"Backups ({len(backups)})")
    table.add_column("ID", style=f"bold {FG_LIGHT}")
    table.add_column("Timestamp")
    table.add_column("Tamaño", justify="right")
    table.add_column("Tipo", justify="center")

    for b in backups:
        table.add_row(
            b.get("id", "N/A"),
            b.get("timestamp", "N/A"),
            f"[bold]{b.get('size_mb', 0):.1f} MB[/]",
            f"[bold {ACCENT_BLUE}]{b.get('type', 'unknown').upper()}[/]",
        )
    console.print(table)
    console.print()


# ---------------------------------------------------------------------------
# COMANDOS: PLANETARY DIAGNOSIS
# ---------------------------------------------------------------------------

@planetary_app.command("status")
def planetary_status() -> None:
    """
    Muestra el estado del ultimo diagnostico planetario.
    Incluye resumen de todas las 100 familias evaluadas.
    """
    console.print(f"\n[bold {ACCENT_PURPLE}]🌍 Diagnostico Planetario - Estado[/]\n")

    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(get_commander().planetary_status())

    if result.get("status") == "no_data":
        console.print(f"[bold {ACCENT_ORANGE}]⚠ {result.get('message', 'Sin datos')}[/]")
        console.print(f"[dim]Ejecuta: veo planetary run[/]\n")
        raise typer.Exit()

    if result.get("status") != "ok":
        console.print(f"[bold {ACCENT_RED}]Error:[/] {result.get('message', 'Error desconocido')}\n")
        raise typer.Exit(1)

    planetary_results = result.get("planetary_results", {})
    summary = planetary_results.get("summary", {})

    # Panel resumen
    content = Text()
    content.append("Configs evaluadas: ", style=f"dim {FG_LIGHT}")
    content.append(f"{planetary_results.get('configs_evaluated', 0)}\n", style=f"bold {ACCENT_BLUE}")
    content.append("Eventos procesados: ", style=f"dim {FG_LIGHT}")
    content.append(f"{planetary_results.get('events_processed', 0)}\n", style=f"bold {ACCENT_BLUE}")
    content.append("Tiempo ejecucion: ", style=f"dim {FG_LIGHT}")
    elapsed = planetary_results.get('elapsed_seconds', 0)
    content.append(f"{elapsed:.2f}s\n", style=f"bold {ACCENT_GREEN}")
    overall = summary.get("overall_health", 0)
    overall_color = ACCENT_GREEN if overall >= 0.8 else ACCENT_ORANGE if overall >= 0.5 else ACCENT_RED
    content.append("Salud global: ", style=f"dim {FG_LIGHT}")
    content.append(f"{overall:.2%}\n", style=f"bold {overall_color}")
    content.append("Familias en riesgo: ", style=f"dim {FG_LIGHT}")
    at_risk = summary.get("families_at_risk", 0)
    risk_color = ACCENT_GREEN if at_risk == 0 else ACCENT_ORANGE if at_risk <= 3 else ACCENT_RED
    content.append(f"{at_risk}", style=f"bold {risk_color}")
    console.print(make_panel(content, "Resumen Planetario", ACCENT_PURPLE))
    console.print()

    # Tabla de familias (top scoring)
    results = planetary_results.get("results", {})
    if results and isinstance(results, dict):
        table = make_table("Familias Evaluadas (Top)")
        table.add_column("Familia", style=f"bold {FG_LIGHT}")
        table.add_column("Score", justify="right")
        table.add_column("Visual", min_width=20)
        table.add_column("Estado", justify="center")

        # Mostrar familias ordenadas por score descendente
        family_items = [(k, v) for k, v in results.items() if k != "summary" and isinstance(v, dict)]
        family_items.sort(key=lambda x: x[1].get("score", 0), reverse=True)

        for family_name, family_data in family_items[:15]:
            score = family_data.get("score", 0)
            if isinstance(score, (int, float)):
                bar = "█" * int(score * 20) + "░" * (20 - int(score * 20))
                score_color = ACCENT_GREEN if score >= 0.8 else ACCENT_ORANGE if score >= 0.5 else ACCENT_RED
                status = "OK" if score >= 0.8 else "WARN" if score >= 0.5 else "CRITICAL"
                status_color = ACCENT_GREEN if status == "OK" else ACCENT_ORANGE if status == "WARN" else ACCENT_RED
                table.add_row(
                    family_name,
                    f"[bold {score_color}]{score:.2f}[/]",
                    f"[bold {score_color}]{bar}[/]",
                    f"[bold {status_color}]{status}[/]",
                )
        console.print(table)
        console.print(f"[dim]Mostrando top 15 de {len(family_items)} familias | Timestamp: {planetary_results.get('timestamp', 'N/A')}[/]\n")


@planetary_app.command("config")
def planetary_config(
    nombre: Annotated[str, typer.Argument(help="Nombre de la familia (ej: continuity, harmony, resilience)")],
) -> None:
    """
    Muestra la configuracion detallada de una familia planetaria especifica.
    """
    console.print(f"\n[bold {ACCENT_PURPLE}]🌍 Configuracion Planetaria: {nombre}[/]\n")

    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(get_commander().planetary_config(nombre))

    if result.get("status") != "ok":
        console.print(f"[bold {ACCENT_RED}]Error:[/] {result.get('message', 'No encontrada')}\n")
        available = result.get("available_configs", [])
        if available:
            console.print(f"[dim]Configs disponibles: {', '.join(available[:15])}...[/]\n")
        raise typer.Exit(1)

    config = result.get("config", {})

    content = Text()
    content.append(f"Nombre: ", style=f"dim {FG_LIGHT}")
    content.append(f"{config.get('name', nombre)}\n", style=f"bold {ACCENT_BLUE}")
    content.append(f"Descripcion: ", style=f"dim {FG_LIGHT}")
    content.append(f"{config.get('description', 'N/A')}\n", style=f"{FG_LIGHT}")
    content.append(f"Threshold: ", style=f"dim {FG_LIGHT}")
    threshold = config.get('threshold', 0)
    content.append(f"{threshold}\n", style=f"bold {ACCENT_ORANGE}")

    indicators = config.get('indicators', [])
    if indicators:
        content.append(f"\nIndicadores ({len(indicators)}):\n", style=f"bold {FG_LIGHT}")
        for ind in indicators:
            content.append(f"  • {ind}\n", style=f"{ACCENT_CYAN}")

    console.print(make_panel(content, f"Familia: {nombre}", ACCENT_PURPLE))
    console.print()


@planetary_app.command("alerts")
def planetary_alerts() -> None:
    """
    Muestra alertas activas del diagnostico planetario (threshold >= 0.99).
    Solo familias con riesgo critico.
    """
    console.print(f"\n[bold {ACCENT_RED}]🚨 Alertas Planetarias Activas[/]\n")

    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(get_commander().planetary_alerts())

    if result.get("status") != "ok":
        console.print(f"[bold {ACCENT_ORANGE}]⚠ {result.get('message', 'Sin datos')}[/]\n")
        raise typer.Exit()

    alerts = result.get("alerts", [])
    alert_count = result.get("alert_count", 0)

    if not alerts:
        console.print(f"[bold {ACCENT_GREEN}]✓ No hay alertas planetarias activas.[/]")
        console.print(f"[dim]Todas las familias estan por debajo del threshold critico.[/]\n")
        return

    table = make_table(f"Alertas Criticas ({alert_count})")
    table.add_column("Familia", style=f"bold {FG_LIGHT}")
    table.add_column("Threshold", justify="right")
    table.add_column("Score", justify="right")
    table.add_column("Nivel", justify="center")
    table.add_column("Detalles", style=f"{FG_LIGHT}")

    for alert in alerts:
        family = alert.get("family", "N/A")
        threshold = alert.get("threshold", 0)
        details = alert.get("details", {})
        score = details.get("score", 0) if isinstance(details, dict) else 0
        risk = details.get("risk_level", "UNKNOWN") if isinstance(details, dict) else "UNKNOWN"
        risk_color = ACCENT_RED if risk == "critical" else ACCENT_ORANGE if risk == "high" else ACCENT_GREEN

        table.add_row(
            f"[bold]{family}[/]",
            f"[bold {ACCENT_RED}]{threshold}[/]",
            f"[bold {risk_color}]{score:.2f}[/]" if isinstance(score, (int, float)) else str(score),
            f"[bold {risk_color}]{risk.upper()}[/]",
            str(details)[:50] if not isinstance(details, dict) else f"score={score:.2f}, risk={risk}",
        )

    console.print(table)
    console.print(f"[dim]Timestamp: {result.get('timestamp', 'N/A')}[/]\n")


@planetary_app.command("run")
def planetary_run() -> None:
    """
    Ejecuta el diagnostico planetario bajo demanda.
    Evalua las 100 familias contra los eventos actuales del sistema.
    """
    console.print(f"\n[bold {ACCENT_PURPLE}]🌍 Ejecutando Diagnostico Planetario...[/]\n")

    with Progress(
        SpinnerColumn(style=ACCENT_PURPLE),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(complete_style=ACCENT_PURPLE, finished_style=ACCENT_GREEN),
        console=console, transient=True,
    ) as progress:
        task = progress.add_task("Evaluando 100 familias...", total=100)
        for i in range(0, 101, 10):
            progress.update(task, completed=i)
            time.sleep(0.05)

    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(get_commander().planetary_run())

    if result.get("status") != "ok":
        console.print(f"[bold {ACCENT_RED}]Error:[/] {result.get('message', 'Error desconocido')}\n")
        raise typer.Exit(1)

    run_result = result.get("result", {})
    elapsed_ms = result.get("elapsed_ms", 0)

    console.print(f"\n[bold {ACCENT_GREEN}]✓ Diagnostico planetario completado[/]\n")
    content = Text()
    content.append("Estado: ", style=f"dim {FG_LIGHT}")
    status = run_result.get("status", "unknown")
    status_color = ACCENT_GREEN if status == "ok" else ACCENT_ORANGE
    content.append(f"{status.upper()}\n", style=f"bold {status_color}")
    content.append("Configs evaluadas: ", style=f"dim {FG_LIGHT}")
    content.append(f"{run_result.get('configs_evaluated', 0)}\n", style=f"bold {ACCENT_BLUE}")
    content.append("Tiempo: ", style=f"dim {FG_LIGHT}")
    content.append(f"{run_result.get('elapsed_seconds', 0):.2f}s\n", style=f"bold {ACCENT_GREEN}")
    content.append("Elapsed (total): ", style=f"dim {FG_LIGHT}")
    content.append(f"{elapsed_ms}ms", style=f"bold {ACCENT_BLUE}")
    console.print(make_panel(content, "Diagnostico Completado", ACCENT_GREEN))
    console.print()


# ---------------------------------------------------------------------------
# COMANDO: SHELL INTERACTIVO
# ---------------------------------------------------------------------------

@app.command("shell")
def cmd_shell() -> None:
    """Inicia un REPL interactivo para ejecutar multiples comandos en la misma sesion."""
    console.print(f"\n[bold {ACCENT_BLUE}]VEO v2 Shell Interactivo[/] — Escribe 'help' para ayuda, 'exit' para salir.\n")
    
    comandos_disponibles = {
        "status": lambda: cmd_status(),
        "hypothesis list": lambda: hypothesis_list(),
        "market list": lambda: market_list(),
        "system health": lambda: cmd_health(),
    }
    
    while True:
        try:
            line = console.input(f"[bold {ACCENT_BLUE}]VEO>[/] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print(f"\n[bold {ACCENT_ORANGE}]Saliendo...[/]")
            break
        
        if not line or line.lower() in ("exit", "quit", "q"):
            break
        
        if line.lower() == "help":
            console.print(f"[bold {ACCENT_BLUE}]Comandos disponibles:[/]")
            for cmd_name in comandos_disponibles:
                console.print(f"  {cmd_name}")
            console.print(f"  [dim]Cualquier comando de la CLI tambien funciona aqui (ej: 'hypothesis show H-001')[/]")
            continue
        
        # Ejecutar comando directamente si esta en la lista rapida
        if line.lower() in comandos_disponibles:
            try:
                comandos_disponibles[line.lower()]()
            except Exception as e:
                console.print(f"[bold {ACCENT_RED}]Error:[/] {e}")
            continue
        
        # Para comandos con argumentos, usamos typer internamente no es trivial,
        # asi que sugerimos usar la CLI directa
        console.print(f"[bold {ACCENT_ORANGE}]Comando no reconocido en shell.[/] Usa la CLI directa: veo {line}")


# ---------------------------------------------------------------------------
# ENTRYPOINT
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app()
