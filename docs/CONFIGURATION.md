# Configuration Reference — VEO v2.0.5

## Table of Contents

1. [Environment Variables](#1-environment-variables)
2. [Configuration File](#2-configuration-file)
3. [Logging](#3-logging)
4. [Database](#4-database)
5. [Priority Order](#5-priority-order)

---

## 1. Environment Variables

The following environment variables are recognized by VEO:

| Variable | Type | Default | Description | Code Location |
|----------|------|---------|-------------|---------------|
| `SOIS_DB_PATH` | string | `sois.db` | Path to SQLite database file (used by `core/db.py` for schema initialization) | `core/db.py:104` |
| `VEO_V2_LOG_NIVEL` | string | `INFO` | Log level: DEBUG, INFO, WARNING, ERROR | `operations/logger.py:374` |
| `VEO_ENV` | string | `dev` | Execution environment: dev, prod | `multiagent/hermes_commander.py:2849` |

**Note:** These are the only three environment variables actually read by the production code. Variables such as `VEO_MIN_CONFIDENCE`, `VEO_AMBIENTE`, and `SOIS_API_PORT` appear in test files or validation scripts but are not read by the running application. The API server port is determined by the argument passed to uvicorn (8000 by default), not by an environment variable.

### Setting Environment Variables

**Linux/macOS:**
```bash
export SOIS_DB_PATH=/path/to/my_database.db
export VEO_V2_LOG_NIVEL=DEBUG
export VEO_ENV=prod
```

**Windows (cmd):**
```cmd
set SOIS_DB_PATH=C:\VEO\data\my_database.db
set VEO_V2_LOG_NIVEL=DEBUG
set VEO_ENV=prod
```

**Windows (PowerShell):**
```powershell
$env:SOIS_DB_PATH = "C:\VEO\data\my_database.db"
$env:VEO_V2_LOG_NIVEL = "DEBUG"
$env:VEO_ENV = "prod"
```

---

## 2. Configuration File

VEO uses `veo_config.json` for persistent configurations. The file is created automatically if it does not exist.

### Example `veo_config.json`

```json
{
  "ambiente": "dev",
  "log_nivel": "INFO",
  "db_path": "sois.db",
  "min_confianza": 0.6
}
```

### Loading Configuration

The configuration is loaded from multiple sources in priority order (highest priority wins):

1. Default values in code
2. `veo_config.json` file
3. Environment variables
4. Command-line arguments

---

## 3. Logging

VEO uses Python's standard `logging` module. The log level is controlled by `VEO_V2_LOG_NIVEL`.

| Level | Use Case |
|-------|----------|
| DEBUG | Development: internal values, traces |
| INFO | Normal operation: cycle starts, results |
| WARNING | Attention: high latency, low resources |
| ERROR | Problem: module failure, exception |
| CRITICAL | Emergency: system non-functional |

### Log Output

Logs are written to:
- **Console:** Colored output (if terminal supports it)
- **File:** `logs/` directory (created automatically)

### Changing Log Level

```bash
# Linux/macOS
export VEO_V2_LOG_NIVEL=DEBUG

# Windows
set VEO_V2_LOG_NIVEL=DEBUG
```

---

## 4. Database

### SQLite Configuration

VEO uses SQLite via `aiosqlite` for asynchronous database operations.

| Setting | Default | Configurable Via |
|---------|---------|------------------|
| Database file | `sois.db` | `SOIS_DB_PATH` |
| Tables created automatically | Yes | N/A |
| Async access | Yes (aiosqlite) | N/A |

### Changing Database Path

```bash
export SOIS_DB_PATH=/var/lib/veo/production.db
python cli/hermes_cli.py serve
```

The database and its tables are created automatically on first access. No manual initialization is required.

---

## 5. Priority Order

When multiple configuration sources define the same setting, the following priority order applies (highest to lowest):

1. **Command-line arguments** (e.g., `--port` on `serve`)
2. **Environment variables** (e.g., `SOIS_DB_PATH`)
3. **Configuration file** (`veo_config.json`)
4. **Default values** in code

Example: If `SOIS_DB_PATH` is set in `veo_config.json` as `sois.db` and as an environment variable as `custom.db`, the environment variable wins.

---

*Last updated: 2026-11-11*
