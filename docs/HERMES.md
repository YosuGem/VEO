# Hermes Commander — Technical Documentation

**VEO v2.0.5**

---

## 1. Introduction

Hermes Commander is the orchestration layer of VEO. It provides a unified interface across three protocols:

- **CLI** — Terminal commands via Typer
- **REST API** — HTTP endpoints via FastAPI
- **WebSocket** — Real-time events

> **Note:** The name "Hermes" is a historical legacy from v1.0. There is no functional dependency on any agent named Hermes. Any script or user can interact with VEO via CLI, API, or WebSocket.

---

## 2. CLI Commands

All CLI commands are invoked with:

```bash
python cli/hermes_cli.py <command> [options]
```

### 2.1 System Commands

| Command | Description | Example |
|---------|-------------|---------|
| `version` | Show VEO version | `python cli/hermes_cli.py version` |
| `health` | System health status | `python cli/hermes_cli.py health` |
| `status` | General system status | `python cli/hermes_cli.py status` |
| `metrics` | Real-time metrics | `python cli/hermes_cli.py metrics` |
| `audit` | System audit log | `python cli/hermes_cli.py audit --lines 20` |
| `serve` | Start API server | `python cli/hermes_cli.py serve --host 0.0.0.0 --port 8000` |
| `system` | Complete system status | `python cli/hermes_cli.py system` |
| `trust` | System trust level | `python cli/hermes_cli.py trust` |

### 2.2 Hypothesis Commands

| Command | Description | Example |
|---------|-------------|---------|
| `hypothesis create` | Create hypothesis | `python cli/hermes_cli.py hypothesis create "Text of hypothesis"` |
| `hypothesis list` | List hypotheses | `python cli/hermes_cli.py hypothesis list` |
| `hypothesis show` | Show hypothesis detail | `python cli/hermes_cli.py hypothesis show H-001` |
| `validate` | Validate hypothesis (dual) | `python cli/hermes_cli.py validate H-001` |

### 2.3 Market Commands

| Command | Description | Example |
|---------|-------------|---------|
| `market create` | Create prediction market | `python cli/hermes_cli.py market create H-001 "YES,NO,MAYBE"` |
| `market list` | List markets | `python cli/hermes_cli.py market list` |
| `market trade` | Execute trade | `python cli/hermes_cli.py market trade M-001 YES 100.0` |
| `market resolve` | Resolve market | `python cli/hermes_cli.py market resolve M-001 YES` |
| `market prices` | Show prices | `python cli/hermes_cli.py market prices M-001` |

### 2.4 Simulation Commands

| Command | Description | Example |
|---------|-------------|---------|
| `simulate create` | Create scenario | `python cli/hermes_cli.py simulate create "Scenario name"` |
| `simulate run` | Run Monte Carlo | `python cli/hermes_cli.py simulate run ESC-001` |
| `simulate compare` | Compare scenarios | `python cli/hermes_cli.py simulate compare ESC-001 ESC-002` |

### 2.5 Journal Commands

| Command | Description | Example |
|---------|-------------|---------|
| `journal` | Show latest report | `python cli/hermes_cli.py journal` |
| `journal history` | Show history | `python cli/hermes_cli.py journal history` |

### 2.6 Graph Commands

| Command | Description | Example |
|---------|-------------|---------|
| `graph stats` | Graph statistics | `python cli/hermes_cli.py graph stats` |
| `graph paths` | Paths between nodes | `python cli/hermes_cli.py graph paths nodeA nodeB` |

### 2.7 Operations Commands (V2)

| Command | Description | Example |
|---------|-------------|---------|
| `operations backup` | Create backup | `python cli/hermes_cli.py operations backup` |
| `operations restore` | Restore backup | `python cli/hermes_cli.py operations restore BACKUP-001` |
| `operations list` | List backups | `python cli/hermes_cli.py operations list` |

### 2.8 Cycle Commands (V2)

| Command | Description | Example |
|---------|-------------|---------|
| `cycles` | Cycle status | `python cli/hermes_cli.py cycles` |
| `trigger` | Trigger cycle | `python cli/hermes_cli.py trigger reasoning --reason "Manual"` |

### 2.9 Planetary Commands

| Command | Description | Example |
|---------|-------------|---------|
| `planetary status` | Planetary status | `python cli/hermes_cli.py planetary status` |
| `planetary config` | Family config | `python cli/hermes_cli.py planetary config continuity` |
| `planetary alerts` | Planetary alerts | `python cli/hermes_cli.py planetary alerts` |
| `planetary run` | Run diagnostic | `python cli/hermes_cli.py planetary run` |

### 2.10 Utility Commands

| Command | Description | Example |
|---------|-------------|---------|
| `narrative` | Narrative shifts | `python cli/hermes_cli.py narrative` |
| `alert` | Active alerts | `python cli/hermes_cli.py alert` |
| `explain` | Explain alert | `python cli/hermes_cli.py explain ALERT-001` |
| `config` | Show configuration | `python cli/hermes_cli.py config` |
| `shell` | Interactive REPL | `python cli/hermes_cli.py shell` |

---

## 3. REST API

### 3.1 Base URL

```
http://localhost:8000
```

### 3.2 OpenAPI Documentation

- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`

### 3.3 Endpoint Categories

| Category | Prefix | Status |
|----------|--------|--------|
| Hypotheses | `/api/v1/hipotesis` | Functional |
| Markets | `/api/v1/mercados` | Functional |
| Scenarios | `/api/v1/escenarios` | Functional |
| System Health | `/api/v2/system/health` | Functional |
| System Status | `/api/v2/system/status` | Functional |
| System Metrics | `/api/v2/system/metrics` | Functional (with fallback) |
| System Audit | `/api/v2/system/audit` | Mock |
| Cycles | `/api/v2/cycles` | Partially functional |
| Operations | `/api/v2/operations` | Functional |
| Health Check | `/health` | Functional |

### 3.4 Request/Response Format

All API endpoints accept and return JSON. Example:

```bash
curl -X POST http://localhost:8000/api/v1/hipotesis \
  -H "Content-Type: application/json" \
  -d '{"texto": "Test hypothesis", "tags": ["test"]}'
```

Response:
```json
{
  "id": "H-001",
  "texto": "Test hypothesis",
  "estado": "pendiente",
  "confianza": null,
  "creado": "2026-11-11T12:00:00Z"
}
```

---

## 4. WebSocket Protocol

### 4.1 Connection

```javascript
const ws = new WebSocket('ws://localhost:8000/ws');
```

### 4.2 Messages

**Client to Server:**

| Action | Payload | Description |
|--------|---------|-------------|
| Subscribe | `{"accion": "subscribe"}` | Subscribe to events |
| Ping | `{"accion": "ping"}` | Keep-alive ping |

**Server to Client:**

| Event | Description |
|-------|-------------|
| `conexion` | Connection confirmation |
| `heartbeat` | Periodic heartbeat (30s) |
| `hipotesis_nueva` | New hypothesis created |
| `validacion_completada` | Validation completed |
| `mercado_nuevo` | New market created |
| `trade` | Trade executed |
| `mercado_resuelto` | Market resolved |
| `cycle_triggered` | Cycle triggered |
| `backup_created` | Backup created |
| `backup_restored` | Backup restored |

---

## 5. Architecture Flow

```
User/Script
    |
    v
+---------------+     +---------------+     +---------------+
|     CLI       |     |   REST API    |     |   WebSocket   |
|  (Typer)      |     |  (FastAPI)    |     |  (websockets) |
+-------+-------+     +-------+-------+     +-------+-------+
        |                     |                     |
        +---------------------+---------------------+
                              |
                              v
                    +-------------------+
                    | HermesCommander   |
                    |   (orchestrator)  |
                    +---------+---------+
                              |
                +-------------+-------------+
                |                           |
                v                           v
        +---------------+           +---------------+
        |  VEO Core     |           |  Analysis     |
        |  (cycles)     |           |  Modules      |
        +---------------+           +---------------+
                |                           |
                v                           v
        +---------------+           +---------------+
        |  SQLite DB    |           |  Agents       |
        |  (aiosqlite)  |           |  (dual)       |
        +---------------+           +---------------+
```

---

*Last updated: 2026-11-11*
