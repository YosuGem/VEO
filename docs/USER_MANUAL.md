# User Manual — VEO v2.0.5

Observable Emergency Surveillance (VEO)

---

## Table of Contents

1. [General Description](#1-general-description)
2. [Project Status](#2-project-status)
3. [System Requirements](#3-system-requirements)
4. [Installation](#4-installation)
5. [First Use](#5-first-use)
6. [Command Line Interface (CLI)](#6-command-line-interface-cli)
7. [REST API](#7-rest-api)
8. [Web Dashboard](#8-web-dashboard)
9. [WebSocket](#9-websocket)
10. [Directory Structure](#10-directory-structure)
11. [Configuration](#11-configuration)
12. [Troubleshooting](#12-troubleshooting)
13. [FAQ](#13-faq)
14. [Final Warning](#14-final-warning)

---

## 1. General Description

VEO is a situational intelligence platform that enables:

- **Creating and validating hypotheses** through scientific and skeptical agents (dual validation)
- **Monitoring prediction markets** with automatic closures based on evidence
- **Analyzing causal graphs** to detect relationships between events
- **Simulating scenarios** using the Monte Carlo method
- **Detecting narrative shifts** through trend analysis
- **Maintaining an interactive discovery journal**
- **Validating the architecture** of the multi-layer system
- **Running planetary diagnostics** across 100 configuration families

All through a **FastAPI REST API**, a **React Dashboard with WebSocket**, and a **Typer CLI**.

---

## 2. Project Status

**VEO v2.0.5** is an actively developed project. Functionality is divided into three categories:

| Status | Description |
|--------|-------------|
| **Functional** | Component implemented, tested, and operational. |
| **Mock** | Component with example data or fallback. Works as a demonstration but not with real data. |
| **Pending** | Component planned but not implemented. |

### Main Components

| Component | Status | Notes |
|-----------|--------|-------|
| REST API (FastAPI) | **Functional** | All V1 and V2 endpoints operational |
| CLI (Typer) | **Functional** | All commands implemented |
| WebSocket | **Functional** | Real-time events |
| React Dashboard | **Functional** | Overview, Hypothesis, and Health panels with real data. Rest with mock data |
| SQLite Persistence | **Functional** | aiosqlite with hypothesis table |
| Agents (scientific + skeptical) | **Functional** | Real dual validation |
| Prediction Markets | **Functional** | Creation, trade, and resolution operational |
| Monte Carlo Simulator | **Functional** | Scenario creation and execution |
| Discovery Journal | **Mock** | Example data |
| Causal Graph | **Mock** | Example data |
| Narrative Analysis | **Mock** | Example data |
| System Audit | **Mock** | Transparent fallback |
| Automatic Cycles | **Mock** | Cycle status with example data |
| Planetary Diagnostic | **Functional** | Evaluation of 100 families |
| Backup / Restore | **Functional** | V2 operations implemented |

---

## 3. System Requirements

| Component | Requirement |
|-----------|-------------|
| Operating System | Linux (primary) or Windows 11 |
| Python | 3.12 (recommended). Compatible with 3.11+ |
| Node.js | 20.20.2+ (only for building the Dashboard) |
| npm | 11.19.0+ (only for building the Dashboard) |
| RAM | 4 GB minimum, 8 GB recommended |
| Disk | 500 MB for installation |

**Main Python dependencies:**
- FastAPI + Uvicorn (API server)
- aiosqlite (SQLite persistence)
- Typer + Click (CLI)
- websockets (native WebSocket)
- psutil (system metrics, optional)
- pytest (tests)

**Node.js dependencies (Dashboard):**
- React 18.2+
- Recharts (charts)
- React Router DOM 6.20+
- Vite 5.0+ (build tool)

---

## 4. Installation

### 4.1 Linux

```bash
git clone https://github.com/YosuGem/VEO.git
cd VEO
./install.sh
source venv/bin/activate
```

### 4.2 Windows 11

```cmd
git clone https://github.com/YosuGem/VEO.git
cd VEO
install.bat
```

The `install.bat` script creates a virtual environment, installs Python dependencies, and runs tests to verify the installation.

### 4.3 Manual Installation (advanced)

If you prefer to control each step:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python -m pytest tests/ -q
```

### 4.4 Dashboard Build

The React Dashboard is built with Vite. You only need to do this once (or after modifying the source code):

```bash
cd dashboard
npm install
npm run build
```

On Windows:
```cmd
cd dashboard
npm install
npm run build
```

This generates the static files in `dashboard/build/` that FastAPI serves automatically.

---

## 5. First Use

### 5.1 Start the API Server

```bash
python -m uvicorn api.api_server:app --host 0.0.0.0 --port 8000
```

Or use the CLI:
```bash
python cli/hermes_cli.py serve --host 0.0.0.0 --port 8000
```

### 5.2 Verify It Works

```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/v2/system/health
```

It should return a JSON with the system status.

### 5.3 Open the Dashboard

Open your browser at:
```
http://localhost:8000/dashboard/
```

### 5.4 Use the CLI

In another terminal (with venv activated):

```bash
python cli/hermes_cli.py --help
python cli/hermes_cli.py version
python cli/hermes_cli.py health
```

---

## 6. Command Line Interface (CLI)

The CLI uses Typer. All commands are invoked with:

```bash
python cli/hermes_cli.py <command> [options]
```

### 6.1 Basic Commands

| Command | Description | Example |
|---------|-------------|---------|
| `version` | Show VEO version | `python cli/hermes_cli.py version` |
| `health` | System health status | `python cli/hermes_cli.py health` |
| `status` | General system status | `python cli/hermes_cli.py status` |
| `metrics` | Real-time metrics | `python cli/hermes_cli.py metrics` |
| `audit` | System audit log | `python cli/hermes_cli.py audit --lines 20` |
| `serve` | Start API server (uvicorn) | `python cli/hermes_cli.py serve --host 0.0.0.0 --port 8000` |

### 6.2 Hypothesis Management

| Command | Description | Example |
|---------|-------------|---------|
| `hypothesis create` | Create a new hypothesis | `python cli/hermes_cli.py hypothesis create "Climate change increases hurricanes"` |
| `hypothesis list` | List hypotheses | `python cli/hermes_cli.py hypothesis list` |
| `hypothesis show` | Show hypothesis detail | `python cli/hermes_cli.py hypothesis show H-001` |
| `validate` | Validate a hypothesis (dual validation) | `python cli/hermes_cli.py validate H-001` |

**Note:** The `validate` command is a root command, not a `hypothesis` subcommand.

### 6.3 Prediction Markets

| Command | Description | Example |
|---------|-------------|---------|
| `market create` | Create market for a hypothesis | `python cli/hermes_cli.py market create H-001 "YES,NO,MAYBE"` |
| `market list` | List markets | `python cli/hermes_cli.py market list` |
| `market trade` | Execute trade on a scenario | `python cli/hermes_cli.py market trade M-001 YES 100.0` |
| `market resolve` | Resolve market with winner | `python cli/hermes_cli.py market resolve M-001 YES` |
| `market prices` | Show scenario prices | `python cli/hermes_cli.py market prices M-001` |

### 6.4 Simulation

| Command | Description | Example |
|---------|-------------|---------|
| `simulate create` | Create scenario (interactive) | `python cli/hermes_cli.py simulate create "Scenario A"` |
| `simulate run` | Execute Monte Carlo simulation | `python cli/hermes_cli.py simulate run ESC-001` |
| `simulate compare` | Compare two scenarios | `python cli/hermes_cli.py simulate compare ESC-001 ESC-002` |

### 6.5 Discovery Journal

| Command | Description | Example |
|---------|-------------|---------|
| `journal` | Show latest weekly report | `python cli/hermes_cli.py journal` |
| `journal history` | Show week history | `python cli/hermes_cli.py journal history` |

### 6.6 Knowledge Graph

| Command | Description | Example |
|---------|-------------|---------|
| `graph stats` | Graph statistics | `python cli/hermes_cli.py graph stats` |
| `graph paths` | Paths between nodes | `python cli/hermes_cli.py graph paths nodeA nodeB` |

### 6.7 Narrative and Alerts

| Command | Description | Example |
|---------|-------------|---------|
| `narrative` | Detected narrative shifts | `python cli/hermes_cli.py narrative` |
| `alert` | Active system alerts | `python cli/hermes_cli.py alert` |
| `explain` | Explain an alert | `python cli/hermes_cli.py explain ALERT-001` |

### 6.8 Configuration and System

| Command | Description | Example |
|---------|-------------|---------|
| `config` | Show current configuration | `python cli/hermes_cli.py config` |
| `system` | Complete system status | `python cli/hermes_cli.py system` |
| `trust` | Show system trust level | `python cli/hermes_cli.py trust` |

### 6.9 Operations (V2)

| Command | Description | Example |
|---------|-------------|---------|
| `operations backup` | Create backup | `python cli/hermes_cli.py operations backup` |
| `operations restore` | Restore from backup | `python cli/hermes_cli.py operations restore BACKUP-001` |
| `operations list` | List available backups | `python cli/hermes_cli.py operations list` |

### 6.10 Cycles (V2)

| Command | Description | Example |
|---------|-------------|---------|
| `cycles` | Status of the 4 cycles | `python cli/hermes_cli.py cycles` |
| `trigger` | Execute cycle on demand | `python cli/hermes_cli.py trigger reasoning --reason "Manual review"` |

### 6.11 Planetary Diagnostic

| Command | Description | Example |
|---------|-------------|---------|
| `planetary status` | Planetary diagnostic status | `python cli/hermes_cli.py planetary status` |
| `planetary config` | Configuration of a family | `python cli/hermes_cli.py planetary config continuity` |
| `planetary alerts` | Active planetary alerts | `python cli/hermes_cli.py planetary alerts` |
| `planetary run` | Run planetary diagnostic | `python cli/hermes_cli.py planetary run` |

### 6.12 Interactive Shell

| Command | Description | Example |
|---------|-------------|---------|
| `shell` | Interactive mode (REPL) | `python cli/hermes_cli.py shell` |

---

## 7. REST API

### 7.1 Hypothesis Endpoints (V1)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/hipotesis` | List all hypotheses |
| POST | `/api/v1/hipotesis` | Create new hypothesis |
| GET | `/api/v1/hipotesis/{id}` | Get hypothesis by ID |
| POST | `/api/v1/hipotesis/{id}/validar` | Validate hypothesis |

**Example:** Create hypothesis
```bash
curl -X POST http://localhost:8000/api/v1/hipotesis \
  -H "Content-Type: application/json" \
  -d '{"texto": "Climate change increases hurricane frequency", "tags": ["climate", "hurricanes"]}'
```

**Example:** List hypotheses
```bash
curl http://localhost:8000/api/v1/hipotesis
```

### 7.2 Market Endpoints (V1)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/mercados` | List markets |
| POST | `/api/v1/mercados` | Create market |
| GET | `/api/v1/mercados/{id}` | Get market |
| POST | `/api/v1/mercados/{id}/trade` | Execute trade |
| POST | `/api/v1/mercados/{id}/resolver` | Resolve market |

**Example:** Create market
```bash
curl -X POST http://localhost:8000/api/v1/mercados \
  -H "Content-Type: application/json" \
  -d '{
    "hipotesis_id": "H-001",
    "pregunta": "Will there be a solar storm in 2025?",
    "escenarios": {"YES": 0.5, "NO": 0.5},
    "fecha_cierre": "2025-12-31"
  }'
```

### 7.3 Scenario Endpoints (V1)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/escenarios` | List scenarios | **Mock** |
| POST | `/api/v1/escenarios` | Create simulation scenario | **Functional** |
| POST | `/api/v1/escenarios/{id}/simular` | Execute Monte Carlo simulation | **Functional** |
| GET | `/api/v1/escenarios/{id}/resultados` | Get simulation results | **Mock** |
| GET | `/api/v1/diario/actual` | Current journal entry | **Mock** |
| GET | `/api/v1/diario/historial` | Journal history | **Mock** |
| GET | `/api/v1/grafo/estadisticas` | Knowledge graph statistics | **Mock** |
| GET | `/api/v1/grafo/nodos` | List graph nodes | **Mock** |
| GET | `/api/v1/grafo/caminos` | Paths between nodes | **Mock (hardcoded)** |
| GET | `/api/v1/narrativa/cambios` | Detected narrative changes | **Mock** |
| GET | `/api/v1/nei` | Narrative stability index | **Mock** |
| GET | `/api/v1/alertas` | Active alerts | **Mock** |
| GET | `/api/v1/estadisticas` | Global system statistics | **Mock** |
| GET | `/api/v1/ws/stats` | WebSocket connection statistics | **Functional** |

### 7.4 System Endpoints (V2)

| Method | Endpoint | Description | Status |
|--------|----------|-------------|--------|
| GET | `/api/v2/system/health` | System health | **Functional** |
| GET | `/api/v2/system/status` | System status | **Functional** |
| GET | `/api/v2/system/metrics` | System metrics | **Functional (with fallback)** |
| GET | `/api/v2/system/audit` | System audit | **Mock** |
| GET | `/api/v2/cycles/status` | Cycle status | **Mock** |
| POST | `/api/v2/cycles/trigger` | Trigger cycle | **Functional** |
| GET | `/api/v2/operations/backups` | List existing backups | **Functional** |
| POST | `/api/v2/operations/backup` | Create backup | **Functional** |
| POST | `/api/v2/operations/restore` | Restore backup | **Functional** |
| GET | `/api/v2/explain/{alert_id}` | Explain an alert | **Mock** |
| GET | `/api/v2/system/trust` | Component trust scores | **Mock (hardcoded)** |
| GET | `/api/v2/system/config` | System configuration | **Functional** |

### 7.5 Health Check

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Basic health check |

### 7.6 WebSocket

| Protocol | Endpoint | Description |
|----------|----------|-------------|
| WS | `/ws` | Real-time events |

---

## 8. Web Dashboard

The Dashboard is a React application served as static content from FastAPI at `/dashboard/`.

### 8.1 Main Panels

| Panel | Description | Data |
|-------|-------------|------|
| **Overview** | System metrics, NEI chart, alerts, service status, real-time activity | **Real** (API) |
| **Hypotheses** | Hypothesis list with filters, validation, detail | **Real** (API) |
| **Health** | Health score, system status, cycles | **Real** (API) |
| **Prediction Market** | Active markets, probabilities, trades | **Mock** (example) |
| **Causal Graph** | Knowledge graph visualization | **Mock** (example) |
| **Simulator** | Scenario simulation with Monte Carlo | **Mock** (example) |
| **Journal** | Discovery journal | **Mock** (example) |
| **Narrative** | Narrative shift analysis | **Mock** (example) |
| **Architecture** | System architecture diagram | **Mock** (example) |

### 8.2 Data Status

Panels marked as **Real** consume data from the API. If there is no data, they show a clearly identified empty state (e.g., "No hypotheses registered").

Panels marked as **Mock** show example data to illustrate functionality. They do not represent real system data.

### 8.3 WebSocket in the Dashboard

The Dashboard automatically connects to `ws://localhost:8000/ws`. Incoming events are displayed in:
- The connection indicator (bottom right corner)
- The activity feed in "Overview"
- Real-time updates in panels

---

## 9. WebSocket

### 9.1 Connection

```javascript
const ws = new WebSocket('ws://localhost:8000/ws');
```

### 9.2 Event Types

| Event | Description |
|-------|-------------|
| `conexion` | Connection confirmation |
| `heartbeat` | Heartbeat every 30 seconds |
| `hipotesis_nueva` | New hypothesis created |
| `validacion_completada` | Hypothesis validation completed |
| `mercado_nuevo` | New prediction market |
| `trade` | Trade executed |
| `mercado_resuelto` | Market resolved |
| `cycle_triggered` | Cycle triggered |
| `backup_created` | Backup created |
| `backup_restored` | Backup restored |

### 9.3 Subscription

```json
{"accion": "subscribe"}
```

### 9.4 Ping/Pong

```json
{"accion": "ping"}
```

Response: `{"tipo": "pong", "timestamp": "2026-11-11T12:00:00Z", "datos": {"conexiones_activas": 1}}`

---

## 10. Directory Structure

```
VEO/
|-- api/                    # FastAPI server
|   |-- api_server.py       # Main endpoints
|   |-- __init__.py
|-- cli/                    # Command line interface
|   |-- hermes_cli.py       # Typer commands
|   |-- __init__.py
|-- core/                   # System core
|   |-- veo_core.py         # Main engine
|   |-- persistence.py      # SQLite persistence
|   |-- db.py               # Database layer
|   |-- config.py           # Central configuration
|   |-- __init__.py
|-- multiagent/             # Multi-agent system
|   |-- hermes_commander.py # Main commander
|   |-- __init__.py
|-- analysis/               # Analysis modules
|   |-- causal_engine.py         # Causal engine
|   |-- causal_graph_adapter.py  # Causal graph adapter
|   |-- hypothesis_engine.py     # Hypothesis engine
|   |-- knowledge_graph.py       # Knowledge graph
|   |-- planetary_configs.py     # Planetary configurations
|   |-- planetary_diagnosis_engine.py  # Planetary diagnosis engine
|   |-- scenario_simulator.py    # Monte Carlo simulator
|   |-- scientific_agent.py      # Scientific and skeptical agents
|   |-- __init__.py
|-- operations/             # Operations
|   |-- backup_manager.py
|   |-- metrics_engine.py
|   |-- logger.py
|   |-- health_monitor.py    # Health monitoring (file exists, broken imports)
|   |-- audit_log.py         # Audit logging (file exists, mock fallback)
|   |-- trust_layer.py       # Trust scoring (file exists, broken imports)
|   |-- __init__.py
|-- tests/                  # pytest tests
|   |-- test_api_integration.py
|   |-- test_cli_subprocess.py
|   |-- test_websocket.py
|   |-- ...
|-- dashboard/              # React Dashboard
|   |-- src/                # Source code
|   |   |-- App.jsx
|   |   |-- DashboardOverview.jsx
|   |   |-- HypothesisPanel.jsx
|   |   |-- SystemHealthPanel.jsx
|   |   |-- ...
|   |-- build/              # Compiled build (generated by npm run build)
|   |-- package.json
|   |-- vite.config.js
|-- docs/                   # Documentation
|   |-- ACERCA.md           # About (es)
|   |-- ABOUT.md            # About (en)
|   |-- MANUAL_USUARIO.md   # User manual (es)
|   |-- USER_MANUAL.md      # User manual (en)
|   |-- INSTALLATION.md     # Installation (en)
|   |-- CONFIGURATION.md    # Configuration (en)
|   |-- HERMES.md           # Technical documentation
|   |-- ARCHITECTURE.md     # Architecture
|   |-- GOVERNANCE.md       # Governance
|   |-- CHANGELOG.md        # Change log
|-- requirements.txt        # Python dependencies
|-- install.sh              # Installation script (Linux)
|-- install.bat             # Installation script (Windows)
|-- validate.bat            # Validation script (Windows)
|-- veo.bat                 # Execution wrapper (Windows)
|-- README.md               # Main README (en)
|-- LEEME.md                # Main README (es)
|-- CHANGELOG.md            # Change log
```

---

## 11. Configuration

### 11.1 Environment Variables

| Variable | Description | Default | Code Location |
|----------|-------------|---------|---------------|
| `SOIS_DB_PATH` | SQLite database path (initialization layer `core/db.py`) | `sois.db` | `core/db.py:104` |
| `VEO_V2_LOG_NIVEL` | Log level (DEBUG, INFO, WARN, ERROR) | `INFO` | `operations/logger.py:374` |
| `VEO_ENV` | Execution environment (dev, prod) | `dev` | `multiagent/hermes_commander.py:2849` |

**Note:** The variables `VEO_MIN_CONFIDENCE` and `VEO_AMBIENTE` appear in `tests/test_core.py` but are NOT read by production code. `SOIS_API_PORT` appears in `validate_windows.py` but only for internal validation; the API server uses the port passed to uvicorn (8000 by default).

### 11.2 Configuration File

VEO uses `veo_config.json` for persistent configurations. It is created automatically if it does not exist.

### 11.3 Persistence

Hypotheses are stored in SQLite. **Important note:** The code contains multiple database paths:
- `core/db.py` uses `sois.db` by default (configurable via `SOIS_DB_PATH`)
- `core/persistence.py` uses `veo_data.db` (fixed)
- `core/veo_core.py` uses `data/veo_core.db`

In practice, HermesCommander (the main engine) stores hypotheses in `veo_data.db` in the project root, as it uses `core/persistence.py`.

### 11.4 `modo` Field in Metrics

The `modo` field indicates the origin of metrics data:

| Value | Meaning |
|-------|---------|
| `real` | psutil is available and metrics are real |
| `simulacion` | psutil is not available; fallback values (0.0) are used |
| `simulacion_demostracion` | Mock/demonstration mode with predefined values |

---

## 12. Troubleshooting

### 12.1 Error: `ModuleNotFoundError: No module named 'veo_v2'`

**Cause:** The virtual environment is not activated, or you are running from the wrong directory.

**Solution:**
```bash
cd /path/to/project/VEO
source venv/bin/activate  # Linux
venv\Scripts\activate      # Windows
```

### 12.2 Error: `port already in use`

**Cause:** Another process is using port 8000.

**Solution:**
```bash
lsof -ti:8000 | xargs kill -9  # Linux
# Or use another port:
python -m uvicorn api.api_server:app --port 8080
```

### 12.3 Dashboard Does Not Load

**Cause:** The build has not been generated.

**Solution:**
```bash
cd dashboard
npm install
npm run build
```

### 12.4 Error 500 on `/api/v2/system/health` or `/api/v2/system/status`

**Cause:** The Pydantic model `SystemHealthResponse` expects the field `"status"` but `HermesCommander` returns `"overall"` in its component checks. The adapter normalizes this field, but if there is another format issue, the endpoint falls back to a mock with `modo: "simulacion_demostracion"`.

**Solution:**
- Verify the server is running: `python cli/hermes_cli.py health`
- If the error persists, restart the server and wait 5 seconds before querying `/api/v2/system/health`
- The endpoint has automatic fallback; reload the page after a few seconds

### 12.5 Tests Fail

**Cause:** Incomplete dependencies or contaminated environment.

**Solution:**
```bash
rm -rf venv
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m pytest tests/ -q
```

### 12.6 WebSocket Does Not Connect

**Cause:** The server is not running or a firewall is blocking the port.

**Solution:** Verify that uvicorn is active and that port 8000 is open.

### 12.7 `click` Incompatible with `typer`

**Cause:** click >= 8.2.0 with typer < 0.16.0.

**Solution:** `requirements.txt` already fixes `click<8.2.0`. If you installed manually, run:
```bash
pip install "click<8.2.0"
```

---

## 13. FAQ

### Q: Can I use VEO without Node.js?
**A:** Yes. Node.js is only needed to build the Dashboard. The API server and CLI work without Node.js. Without Node.js, you won't have a visual Dashboard, but you will have API and CLI access.

### Q: Is data lost on restart?
**A:** No. Hypotheses and markets are saved in SQLite (`veo_data.db` by default, via `core/persistence.py`). Only in-memory data (real-time metrics) resets.

### Q: Can I run VEO in Docker?
**A:** There is no official Dockerfile, but you can easily create one based on `requirements.txt`.

### Q: The Dashboard shows "No data". Is this an error?
**A:** No. It means there are no hypotheses, markets, or other data in the system. Create some via the API or CLI.

### Q: What does the `modo` field in metrics mean?
**A:** It indicates the data origin: `"real"` (psutil available), `"simulacion"` (psutil not available, 0.0 values), or `"simulacion_demostracion"` (mock mode with predefined values).

### Q: Can I disable WebSocket?
**A:** There is no flag to disable it, but you can simply not connect to it. The server will continue to work.

### Q: What happens if psutil is not installed?
**A:** System metrics will return `0.0` values with `modo: "simulacion"`. The system continues to work.

### Q: How do I know which components use real data and which use mock?
**A:** Check the [Project Status](#2-project-status) table in this manual. Dashboard panels also indicate their data source.

---

## 13. Known Limitations

This section documents known technical issues in the source code that affect the real-world operation of the system. They are provided so the user understands which features are actually operational and which have deficiencies.

### 13.1 WebSocket

- **Broken broadcast:** `WebSocketManager` uses a single shared `asyncio.Queue`. When multiple clients are connected, each event only reaches the first client that calls `get_nowait()`; the rest never receive it.

### 13.2 API ↔ HermesCommander Integration

- **Markets:** Market endpoints (`/api/v1/mercados`) and the adapter (`HermesCommanderAdapter`) call methods that do not exist in `HermesCommander` (`listar_mercados`, `get_mercado`, `crear_mercado`, `trade_mercado`, `resolver_mercado`). They return empty responses or errors.
- **Scenarios:** The adapter's `crear_escenario` method returns `None`, causing `TypeError` when accessing `e['id']`.
- **Simulation:** `simular_escenario` passes `sid` instead of `hyp_id` to `HermesCommander.simulate_scenario`.
- **Backup:** `create_backup` calls a non-existent method (`backup_create` instead of `backup_now`).
- **Audit:** The `/api/v2/system/audit` endpoint is mock (returns sample data).

### 13.3 CLI

- **Double calls:** In several commands (`market`, `journal`, `graph`, `narrative`, `alert`), `get_commander().get_commander()` is called, which raises `AttributeError` because the adapter does not have that method.
- **Incorrect mapping:** The adapter maps names that do not match `HermesCommander` (`get_system_metrics` → `get_metrics()`, `create_backup` → `backup_now()`, etc.).
- **Shell REPL:** Only supports 4 commands despite being documented as a full REPL.

### 13.4 Architecture

- **`models.py`:** Created in v2.0.5 with basic enums and dataclasses (`Hipotesis`, `Prediccion`, `Escenario`, `NodoGrafo`, etc.) aligned with the SQL schema in `core/db.py`. The structure may need expansion to cover all system models.
- **Module duplication:** `TrustLayer`, `HealthMonitor`, and `AuditLog` are defined in both `core/veo_core.py` and `operations/`. `VEOCore` uses the internal versions; the ones in `operations/` are dead code in production.
- **Imports with fallback:** `operations/audit_log.py`, `operations/trust_layer.py`, and `operations/health_monitor.py` use `try/except ImportError` with fallback to standard logging when `veo_v2` is not available as a package. `multiagent/__init__.py` still imports from `veo_v2` without fallback.
- **Unconnected modules:** `prediction_market.py`, `memory/discovery_journal.py`, and `analysis/knowledge_graph.py` exist as complete files but are never imported by the production flow.

### 13.5 Installation and Dependencies

- **`validate.bat`:** ~~Uses system `python` instead of `venv\Scripts\python`.~~ **CORRECTED in v2.0.5.** Now invokes `venv\Scripts\python validate_windows.py`.
- **`install.bat`:** ~~Does not run tests after completion.~~ **CORRECTED in v2.0.5.** Now runs `venv\Scripts\python -m pytest tests/ -q --tb=short` as step 6/7.
- **`install.sh`:** ~~Has a duplicated line in package verification.~~ **CORRECTED in v2.0.5.** Verification no longer has duplicates.
- **`models.py`:** Created in v2.0.5 with basic enums and dataclasses aligned with `core/db.py`. The structure may need expansion to cover all system models.
- **Dependencies:** `psutil` and `sentence_transformers` were added to `requirements.txt` in v2.0.5. No missing dependencies are known at this time.

### 13.6 Internal Versions

- `core/veo_core.py` (line ~2078) returned `"version": "2.0.3"` in `get_status()` — **CORRECTED to `2.0.5` in this version**.
- Automated tests: **292 of 293 pass** (1 failure in persistence-between-restarts integration test, which requires the full backend running).

---

## 14. Final Warning

VEO is a situational intelligence platform with structured reasoning capabilities. Its use must be aligned with ethical principles of transparency and responsibility. The author is not responsible for inappropriate uses by third parties.

This is a personal project, without corporate sponsorship or external funding. Code quality reflects individual effort, not resources of a large team.

If you find a bug, do not assume it is broken by design. Report it and it will be fixed.

Some components (Dashboard, causal graph, narrative, audit) use example data (mock) to illustrate functionality. They should not be interpreted as real data or as faithful representations of current situations.
