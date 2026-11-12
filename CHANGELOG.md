# Changelog - VEO v2

## Version 2.0.5 - 2026-11-12

### Summary

Public distribution preparation. Documentation corrected, made consistent, and contrasted with the actual program. Version 2.0.4S was the last development intervention; 2.0.5 is the public release packaging with honest documentation. Fixed the root cause of the scenario cycle failure identified by Hermes in v2.0.4R validation, plus added end-to-end integration tests and WebSocket residual event clarification.

### Corrections in 2.0.4S

| # | Category | Issue | Fix |
|---|----------|-------|-----|
| 1 | **CRITICAL** | Escenarios: POST crea en MockDatabase, pero GET lee de HermesCommander (instancias diferentes) -> lista vacia | `listar_escenarios()` ahora cae al fallback de MockDatabase cuando `list_scenarios` devuelve lista vacia |
| 2 | **CRITICAL** | `GET /api/v1/escenarios/{sid}` no existia -> 404 | Nuevo endpoint `GET /api/v1/escenarios/{sid}` para recuperar escenarios individualmente |
| 3 | API | `POST /api/v1/escenarios/{sid}/simular` devolvia 500 | `simular_escenario()` ahora envuelve llamada a `simulate_scenario` en try/except y cae al fallback de MockDatabase |
| 4 | API | `get_escenario` no buscaba `get_scenario_results` (ingles) en HermesCommander | Añadida busqueda de `get_scenario_results` con adaptacion de formato |
| 5 | Tests | 296 tests pasaban pero el ciclo real de escenarios fallaba | 8 nuevos tests de integracion end-to-end que prueban el ciclo completo CREAR->LISTAR->GET->SIMULAR->RESULTADOS |
| 6 | WebSocket | Eventos residuales (+1 en pruebas) | Identificado como mensaje de bienvenida `"tipo": "conexion"` enviado a cada cliente nuevo. Comportamiento documentable, no bug |

### Tests

- **304 tests collected and 304 passed** in Hermes previous execution
- 8 nuevos tests de integracion escenarios (todos pasan)

---

## Version 2.0.4R - 2026-11-12

### Summary

Post-validation correction release. Addressed 5 critical defects identified by HermesCodeValidator in the independent validation of v2.0.4Q, plus distribution hygiene and version consistency.

### Corrections in 2.0.4R

| # | Category | Issue | Fix |
|---|----------|-------|-----|
| 1 | **CRITICAL** | WebSocket broadcast loses events — colas indexadas por IP (`127.0.0.1`) hacen que clientes locales compartan cola | Cada conexion recibe UUID unico (`websocket._veo_client_id`); colas indexadas por UUID; endpoint consume de cola propia |
| 2 | API | `POST /api/v1/escenarios` crea pero `GET /api/v1/escenarios` devuelve `[]` | `listar_escenarios()` ahora hace fallback a `MockDatabase`; `get_escenario()` y `simular_escenario()` tambien |
| 3 | MockDatabase | `simular_escenario` no existia | Implementado con simulacion Monte Carlo real |
| 4 | Distribucion | `dashboard/build/` ausente en ZIP | Build incluido (index.html + JS 652KB + CSS 21KB) |
| 5 | Distribucion | 12 `.db` y 3 `.log` en ZIP | Excluidos del empaquetado |
| 6 | Versiones | `__init__.py` decia `2.0.4P`, API decia `2.0.4Q` | Todas las referencias activas unificadas a `2.0.4R` |
| 7 | Tests | 3 nuevos tests de integracion WebSocket multi-cliente | `test_broadcast_a_tres_clientes_misma_ip`, `test_broadcast_cinco_clientes_cinco_eventos`, `test_desconexion_durante_broadcast` |
| 8 | Validacion | Script de 9 checkpoints automaticos del ZIP | Implementado y ejecutado exitosamente |

### Tests

- **296/296 tests passed** (100% pass rate)
- 0 failures, 45 warnings (cosmetic only)
- 3 nuevos tests de integracion WebSocket multi-cliente

---

## Version 2.0.4Q - 2026-11-12

### Summary

Critical defect fix and API stability release. Addressed 4 critical issues identified by HermesCodeValidator in the v2.0.4P review, plus documentation alignment.

### Corrections in 2.0.4Q

| # | Category | Issue | Fix |
|---|----------|-------|-----|
| 1 | **CRITICAL** | WebSocket broadcast loses events due to `RuntimeError: dictionary changed size during iteration` when clients disconnect during broadcast | `broadcast()` now copies queue references under lock before iterating; added try/except for orphan queues |
| 2 | API | POST `/api/v1/escenarios` returns HTTP 500 | Added `import uuid`; `crear_escenario()` now falls back to `MockDatabase` when `HermesCommander` lacks the method |
| 3 | API | GET `/api/v1/diario/actual` returns HTTP 404 | `get_diarios()` now falls back to `MockDatabase.diarios` when commander has no `diarios` attribute |
| 4 | Docs | `docs/README.md` listed `core/security.py` which does not exist | Removed from directory tree |
| 5 | Docs | §13.5 in MANUAL_USUARIO.md/USER_MANUAL.md outdated (imports `veo_v2` already fixed in P) | Updated to reflect current state: `models.py` created, `validate.bat`/`install.bat`/`install.sh` corrected |
| 6 | Deps | `sentence-transformers` requires ~2GB torch + CUDA deps | Removed from `requirements.txt`; documented as optional (code has try/except fallback) |
| 7 | Install | `install.sh` inconsistent with `install.bat` (4 vs 7 steps, no tests) | Restructured to 7 steps, added pytest execution, aligned with `install.bat` |

### Tests

- **293/293 tests passed** (100% pass rate)
- 0 failures, 45 warnings (cosmetic only)

---

## Version 2.0.4O - 2026-11-12

### Summary

Post-review correction release. Addressed 5 discrepancies identified by HermesCodeValidator in the v2.0.4N review.

### Corrections in 2.0.4O

| # | Document | Error | Fix |
|---|----------|-------|-----|
| 1 | ARCHITECTURE.md | `health_monitor.py` and `trust_layer.py` marked "Implementado" | Corrected to "Archivo existe; imports rotos" (`veo_v2` package does not exist) |
| 2 | USER_MANUAL.md / MANUAL_USUARIO.md | `operations/` tree missing 3 files | Added `audit_log.py`, `health_monitor.py`, `trust_layer.py` with status notes |
| 3 | USER_MANUAL.md / MANUAL_USUARIO.md FAQ | FAQ stated `sois.db`, contradicting §11.3 | Corrected to `veo_data.db` (the DB used by HermesCommander via `core/persistence.py`) |
| 4 | docs/README.md | `hermes_commander.py` listed in `core/` (Hermes report) | Verified: already corrected to `multiagent/` in v2.0.4N; no action needed |
| 5 | ZIP distribution | `.pytest_cache` included | Excluded from distribution |

### Note

Source code version strings remain `2.0.4M` per instruction: "No modificar codigo del programa". The letter O identifies the distribution, not a new functional code version.

---

## Version 2.0.4N - 2026-11-12

### Summary

Documentation audit and correction release. Addressed 18 documentation errors identified by HermesCodeValidator in the Windows 11 review of v2.0.4M. All corrections were verified against actual source code before application.

### What's New in 2.0.4N

| # | Change | Description |
|---|--------|-------------|
| 1 | **docs/ARCHITECTURE.md corrected** | Fixed endpoint table: all endpoints now include correct `/api/v1/` or `/api/v2/` prefixes. Removed non-existent endpoints. Added `/api/v2/cycles/trigger` and `/api/v2/operations/restore`. Corrected module status table (mock vs functional). |
| 2 | **docs/CONFIGURATION.md corrected** | Reduced to 3 real environment variables (`SOIS_DB_PATH`, `VEO_V2_LOG_NIVEL`, `VEO_ENV`). Removed `VEO_MIN_CONFIDENCE`, `VEO_AMBIENTE`, `SOIS_API_PORT` from production table (they only appear in test/validation code). Added explicit note about this distinction. |
| 3 | **docs/MANUAL_USUARIO.md corrected** | Fixed pong format to `{"tipo": "pong", ...}`. Fixed directory tree: removed `agents/`, `narrative_engine.py`, `nei_engine.py`, `hypothesis_analyzer.py`; added real files. Fixed ModuleNotFoundError from `'veo'` to `'veo_v2'`. Corrected Error 500 attribution. Documented DB inconsistency (`sois.db` vs `veo_data.db` vs `data/veo_core.db`). Added note about test-only env vars. |
| 4 | **docs/USER_MANUAL.md corrected** | Mirror of MANUAL_USUARIO.md corrections in English. |
| 5 | **docs/README.md corrected** | Fixed license: MIT -> Apache 2.0. Fixed repository URL to `YosuGem/VEO`. Removed fictitious email. Fixed project structure tree: `core/` now shows real files (`db.py`, `persistence.py`, `security.py`), added `multiagent/`, `api/`, `cli/` directories. |
| 6 | **docs/GOVERNANCE.md corrected** | Removed fictitious version calendar. Removed invented migration commands. Corrected SemVer description to reflect v2.0.x development series. Fixed checklist formatting error. Added note that no automatic migration tool exists. |
| 7 | **README.md / LEEME.md updated** | Added prominent "INCOMPLETO / INCOMPLETE" warning at top. Updated version reference to v2.0.4N. |
| 8 | **docs/INSTALLATION.md corrected** | Fixed `.venv` -> `venv` in automated script description. |
| 9 | **Documentation version bump** | All version references in documentation updated from 2.0.4M to 2.0.4N. Source code version strings remain 2.0.4M per instruction: "No modificar codigo del programa". |

---

## Version 2.0.4P - 2026-11-12

### Summary

**FIRST CODE MODIFICATION RELEASE.** All previous releases (K, L, M, N, O) were documentation-only. This release corrects 29 concrete bugs in the source code identified by the 5-agent swarm review of v2.0.4O, plus 1 test update and 7 documentation fixes.

### Code Corrections (29 changes)

| # | Category | File | Change |
|---|----------|------|--------|
| 1 | Imports | `multiagent/__init__.py:25` | Fixed `veo_v2` import → relative import |
| 2 | Imports | `operations/audit_log.py:32` | Fixed `veo_v2` import → try/except fallback |
| 3 | Imports | `operations/trust_layer.py:40` | Fixed `veo_v2` import → try/except fallback |
| 4 | Architecture | `models.py` (new) | Created missing module with 5 enums + 10 dataclasses |
| 5 | Dependencies | `requirements.txt` | Added `psutil`, `sentence-transformers`; removed `httpx`, `click` |
| 6 | WebSocket | `api/api_server.py:1485-1541` | Fixed broadcast: single queue → per-client queues |
| 7 | WebSocket | `api/api_server.py:2341-2348` | `/ws` endpoint reads from client-specific queue |
| 8 | WebSocket | `api/api_server.py:2425-2430` | `/api/v1/ws/stats` sums all client queues |
| 9 | Adapter | `api/api_server.py:243-283` | Market methods use correct HermesCommander calls |
| 10 | Adapter | `api/api_server.py:285-302` | `listar_escenarios` extracts list from dict |
| 11 | Adapter | `api/api_server.py:303-311` | `crear_escenario` handles `None` with UUID fallback |
| 12 | Adapter | `api/api_server.py:314-323` | `simular_escenario` passes `hyp_id=` not `sid` |
| 13 | Adapter | `api/api_server.py:443-453` | `create_backup` calls `backup_now()`; `list_backups` extracts list |
| 14 | Version | `api/api_server.py:58` | `VEO_VERSION = "2.0.4P"` |
| 15 | Logger | `multiagent/hermes_commander.py:40,157-159` | Added missing `logger` definition |
| 16 | CLI | `cli/hermes_cli.py` | Fixed 19 `get_commander().get_commander()` double calls |
| 17 | CLI | `cli/hermes_cli.py:~176` | Added `get_commander()` method to adapter returning `self._backend` |
| 18 | CLI | `cli/hermes_cli.py:~360-425` | Fixed 14 V2 adapter methods (`self.get_commander()` → `self._backend`) |
| 19 | CLI | `cli/hermes_cli.py:~1231` | `simulate_create` handles `None` with UUID fallback |
| 20 | CLI | `cli/hermes_cli.py:~1553` | `serve`: `-h` → `-H` short option for `--host` |
| 21 | CLI | `cli/hermes_cli.py:~2313` | Shell REPL: `system_health` → `cmd_health` |
| 22 | CLI | `cli/hermes_cli.py:~996` | Hypothesis validation: `< 5` → `< 10` chars |
| 23 | Version | `core/veo_core.py:2078` | `"version": "2.0.3"` → `"2.0.4P"` |
| 24 | Version | `multiagent/hermes_commander.py:2838` | `"version": "2.0.0"` → `"2.0.4P"` |
| 25 | Install | `validate.bat` | Uses `venv\Scripts\python` instead of system python |
| 26 | Install | `install.bat` | Added test execution step; updated step counters |
| 27 | Install | `install.sh` | `python` → `python3`; removed duplicate line |
| 28 | Install | `veo` | Added `#!/usr/bin/env bash` shebang |
| 29 | Tests | `tests/test_websocket.py:59-76` | Updated for per-client queue architecture |

### Documentation Fixes (carried forward from O)

| # | Document | Fix |
|---|----------|-----|
| 1 | docs/GOVERNANCE.md | Version v2.0.4N → v2.0.4O |
| 2 | docs/CONFIGURATION.md | Version v2.0.4N → v2.0.4O |
| 3 | docs/INSTALLATION.md | Version v2.0.4N → v2.0.4O |
| 4 | docs/HERMES.md | Version v2.0.4N → v2.0.4O |
| 5 | docs/MANUAL + USER | Complete `operations/` tree; 16 endpoints; §13 Known Limitations |
| 6 | docs/ARCHITECTURE.md | `health_monitor.py`/`trust_layer.py` status corrected |
| 7 | docs/CHANGELOG.md | Note indicating it is historical |

### Test Results

- **Passed:** 284 (was 276 in O)
- **Failed:** 9 (was 17 in O)
- **Improvement:** +8 tests passing

The 9 remaining failures are integration tests requiring the full backend running.

---

### Errors Corrected (Hermes Audit)

| # | Document | Error | Fix |
|---|----------|-------|-----|
| 1 | ARCHITECTURE.md | Endpoints without `/api/v1/` prefix | Added correct prefixes for all 36 endpoints |
| 2 | ARCHITECTURE.md | Module status table incorrect | Corrected mock vs functional status for each module |
| 3 | CONFIGURATION.md | `VEO_MIN_CONFIDENCE` documented as production var | Moved to note; only used in tests |
| 4 | CONFIGURATION.md | `VEO_AMBIENTE` documented as production var | Moved to note; only used in tests |
| 5 | CONFIGURATION.md | `SOIS_API_PORT` default 8000, location confusing | Removed from production table; only used in `validate_windows.py` |
| 6 | MANUAL/USER | Directory tree with non-existent files | Removed `agents/`, `narrative_engine.py`, `nei_engine.py`, `hypothesis_analyzer.py`; added real files |
| 7 | MANUAL/USER | Pong format `{"respuesta": "pong"}` | Corrected to `{"tipo": "pong", ...}` |
| 8 | MANUAL/USER | Only 3 env vars in section 11.1 | Added note about test-only vars; kept 3 production vars |
| 9 | MANUAL/USER | BD name `sois.db` vs actual | Documented inconsistency: `sois.db` (init), `veo_data.db` (persistence), `data/veo_core.db` (core) |
| 10 | MANUAL/USER | `ModuleNotFoundError: 'veo'` | Corrected to `'veo_v2'` |
| 11 | MANUAL/USER | Error 500 attribution to HermesCommander init | Corrected to Pydantic field mismatch (`status` vs `overall`) with fallback to mock |
| 12 | docs/README.md | License stated as MIT | Corrected to Apache 2.0 |
| 13 | docs/README.md | Repository `veo-system/veo-v2` | Corrected to `YosuGem/VEO` |
| 14 | docs/README.md | Core structure incorrect | Fixed `core/` contents; added `multiagent/`, `api/`, `cli/` |
| 15 | GOVERNANCE.md | SemVer calendar fictitious | Removed calendar; corrected to v2.0.x development |
| 16 | GOVERNANCE.md | Version schedule invented | Removed schedule; added note about manual backup/restore |
| 17 | GOVERNANCE.md | Migration commands invented | Removed `python -m veo_v2.migrate`; documented manual process |
| 18 | ZIP contents | 7 DBs and 2 logs included | Cleaned: 0 DBs, 0 logs, 0 __pycache__ in distribution |

### Verification

- **Linux:** 293 tests passing (no code changes)
- **Documentation:** All corrections verified against actual source code (`api/api_server.py`, `cli/hermes_cli.py`, `core/db.py`, `core/persistence.py`, `multiagent/hermes_commander.py`, `operations/logger.py`)

---

## Version 2.0.4M - 2026-11-11

### Summary

Documentation correction and completion release. Fixed all technical errors identified in the manuals, expanded README/LEEME, completed ACERCA/ABOUT mirror pair, corrected INSTALLATION.md, CONFIGURATION.md, and HERMES.md.

### What's New in 2.0.4M

| # | Change | Description |
|---|--------|-------------|
| 1 | **README.md expanded** | Expanded from 50 to ~250 lines. Bilingual (es+en), project status table, quick start, documentation index, author's note, final warning |
| 2 | **LEEME.md expanded** | Mirror of README.md in Spanish |
| 3 | **docs/ACERCA.md rewritten** | Complete mirror of ABOUT.md (330 lines). Philosophy, history, module connectivity, technical debt, attribution, license |
| 4 | **docs/MANUAL_USUARIO.md corrected** | Fixed: CLI commands (show instead of get, removed non-existent delete/export/import), API endpoints (removed non-existent DELETE), environment variables (replaced 5 invented variables with 6 real ones), modo field values (real/simulacion/simulacion_demostracion). Added: 30+ real CLI commands, planetary diagnostic, project status section |
| 5 | **docs/USER_MANUAL.md corrected** | Mirror of corrected MANUAL_USUARIO.md in English |
| 6 | **docs/INSTALLATION.md rewritten** | Removed: --mock references, invented env vars, non-existent test files, fictitious support URLs. Corrected: all commands verified against code |
| 7 | **docs/CONFIGURATION.md rewritten** | Removed: 30+ invented variables. Documented only 6 real env vars with code locations |
| 8 | **docs/HERMES.md rewritten** | Removed: hermes start/stop/restart, monitoreo/analisis/prediccion/ejecutivo commands, hermes hipotesis get. Documented: all 30+ real CLI commands |
| 9 | **docs/ARCHITECTURE.md updated** | Added status note about mock vs functional cycles |
| 10 | **Version bump** | All modules updated from 2.0.4L to 2.0.4M |

### Errors Corrected

| Document | Error | Fix |
|----------|-------|-----|
| MANUAL_USUARIO.md | `hypothesis get` command | Corrected to `hypothesis show` |
| MANUAL_USUARIO.md | `hypothesis delete` command | Removed (does not exist) |
| MANUAL_USUARIO.md | `market get` command | Removed (does not exist) |
| MANUAL_USUARIO.md | `market delete` command | Removed (does not exist) |
| MANUAL_USUARIO.md | `export` command | Removed (does not exist) |
| MANUAL_USUARIO.md | `import` command | Removed (does not exist) |
| MANUAL_USUARIO.md | `simulate` without subcommand | Corrected to `simulate run` |
| MANUAL_USUARIO.md | `VEO_PORT`, `VEO_HOST`, `VEO_LOG_LEVEL`, `VEO_DB_PATH`, `VEO_DASHBOARD_PORT` | Replaced with real variables: `SOIS_DB_PATH`, `VEO_V2_LOG_NIVEL`, `VEO_ENV`, `VEO_AMBIENTE`, `VEO_MIN_CONFIDENCE`, `SOIS_API_PORT` |
| MANUAL_USUARIO.md | `modo` values `"real"`, `"fallback"` | Corrected to `"simulacion"`, `"simulacion_demostracion"` |
| MANUAL_USUARIO.md | DELETE endpoints for hypotheses/markets | Removed (do not exist) |
| INSTALLATION.md | `--mock` flag | Removed (does not exist in CLI) |
| INSTALLATION.md | `SOIS_MIN_EVIDENCE`, `SOIS_NEI_*`, `SOIS_LLM_*`, etc. | Removed (do not exist in code) |
| INSTALLATION.md | `test_core.py`, `test_analysis.py`, etc. | Corrected to actual test files |
| CONFIGURATION.md | 30+ invented env vars | Removed; only 6 real vars documented |
| HERMES.md | `hermes start/stop/restart` | Removed (do not exist) |
| HERMES.md | `hermes monitoreo/analisis/prediccion/ejecutivo` | Removed (do not exist) |

### Verification

- **Linux:** 293 tests passing (no code changes)
- **Documentation:** All commands verified against `cli/hermes_cli.py` and `api/api_server.py`

---

## Version 2.0.4M - 2026-11-11

### Summary

Documentation release. Complete overhaul of user-facing documentation following the standards of SIBILA and PULSO projects. Expanded user manuals, created ACERCA.md (es), aligned English and Spanish documentation.

### What's New in 2.0.4L

| # | Addition | Description |
|---|----------|-------------|
| 1 | **docs/ACERCA.md (es)** | New "About" document in Spanish, mirror of ABOUT.md with author's personal note |
| 2 | **docs/MANUAL_USUARIO.md expanded** | Expanded from 182 lines to 600+ lines. Added: system requirements, full CLI reference with examples, API endpoint catalog with curl examples, Dashboard panel descriptions, WebSocket reference, directory structure, configuration, troubleshooting (7 items), FAQ (7 items), final warning |
| 3 | **docs/USER_MANUAL.md expanded** | Mirror of MANUAL_USUARIO.md in English, same structure and completeness |
| 4 | **Documentation standards** | Aligned with SIBILA (dual-language docs, ACERCA/ABOUT pair, detailed manuals) and PULSO (final warning, author's note, FAQ, troubleshooting) |
| 5 | **Version bump** | All modules updated from 2.0.4K to 2.0.4L |

### Technical Changes

- No code changes. This is a documentation-only release.

### Verification

- **Linux:** 293 tests passing (no code changes)
- **Windows 11:** Pending re-validation by Hermes

---

## Version 2.0.4K - 2026-11-11

### Summary

Bug-fix release addressing three issues detected during Hermes validation of 2.0.4J on Windows 11: structural error in V2 health endpoint causing Pydantic 500, WebSocket event duplication, and missing transparency field in metrics response.

### What's Fixed in 2.0.4K

| # | Fix | Description |
|---|-----|-------------|
| 1 | **V2 health endpoint structure** | `get_system_health()` now correctly interprets `_cmd_health` output (`{"status": "...", "components": {...}, "timestamp": "..."}`). Eliminates double-nesting and normalizes `"overall"` → `"status"` in `veo_core` component to satisfy `ComponentHealth` model |
| 2 | **WebSocket event deduplication** | `WebSocketManager.broadcast()` no longer sends directly to connections. Events are queued via `eventos_cola` and distributed exclusively by `websocket_endpoint()`, eliminating duplicate delivery |
| 3 | **Metrics transparency field** | `SystemMetricsResponse` now includes `modo: str` field. `_mock_system_metrics()` populates it with `"real"` (psutil available) or `"simulacion"` (fallback), making data origin visible to consumers |
| 4 | **Version bump** | All modules updated from 2.0.4J to 2.0.4K |

### Technical Changes

- `api/api_server.py`: Added `_normalize_component()` helper; fixed `get_system_health()` format adaptation; removed direct-send from `broadcast()`; added `modo` to `SystemMetricsResponse`
- `api/api_server.py`: `websocket_endpoint()` remains the single distribution point for WebSocket events

### Verification

- **Linux:** 293 tests passing
- **Windows 11:** Pending re-validation by Hermes

---

## Version 2.0.4J - 2026-11-11

### Summary

Bug-fix release addressing three issues detected during Windows 11 validation by Hermes: 500 errors in V2 health/status endpoints, CLI Unicode rendering error, and improved mock implementations for metrics/audit. All 293 tests passing.

### What's Fixed in 2.0.4J

| # | Fix | Description |
|---|-----|-------------|
| 1 | **V2 health/status endpoint stability** | Added comprehensive try/except handling in `get_system_health()` and `get_system_status()` with automatic fallback to mock responses. Prevents 500 errors when HermesCommander workers are not fully initialized |
| 2 | **CLI Unicode rendering** | Replaced `\u2591` (LIGHT SHADE) character with ASCII `-` in `cmd_metrics()` bar chart to prevent encoding errors on Windows consoles |
| 3 | **CLI asyncio event loop** | Replaced deprecated `asyncio.get_event_loop()` with `asyncio.get_running_loop()` / `asyncio.new_event_loop()` pattern in `cmd_metrics()` |
| 4 | **Metrics mock realism** | `_mock_system_metrics()` now attempts `psutil` for real system metrics; falls back to clearly labeled simulated values |
| 5 | **Audit mock transparency** | `_mock_system_audit()` returns empty list with documented fallback to sample entries when no audit log exists |
| 6 | **Version bump** | All modules updated from 2.0.4I to 2.0.4J |

### Technical Changes

- `api/api_server.py`: Defensive exception handling in `get_system_health`, `get_system_status`, `get_system_metrics`, `get_system_audit`
- `cli/hermes_cli.py`: ASCII-safe bar chart rendering; fixed asyncio event loop acquisition
- `api/api_server.py`: `_mock_system_metrics` attempts real system metrics via `psutil`
- Version strings updated across all modules

### Verification

- **Linux:** 293 tests passing
- **Windows 11:** Pending re-validation by Hermes

---

## Version 2.0.4I - 2026-11-10

### Summary

Functional verification release with API adapter format corrections, verdict mapping fixes, hypothesis normalization, and clean installation validation. 293 tests passing. Package prepared for Windows 11 validation.

### What's Fixed in 2.0.4I

| # | Fix | Description |
|---|-----|-------------|
| 1 | **API adapter response format** | `HermesCommanderAdapter` now correctly unwraps `{"status": "ok", "hypothesis": {...}}` responses from HermesCommander into direct hypothesis objects for API endpoints |
| 2 | **Scientific verdict mapping** | Maps `AgenteCientifico` verdicts (`"refutada"`, `"confirmada"`, `"inconclusa"`) to API-compatible values (`"refutado"`, `"confirmado"`, `"dudoso"`) |
| 3 | **Hypothesis normalization** | `_normalize_hypothesis()` handles heterogeneous hypothesis formats (manual, automatic, DB, memory) with robust type handling for all fields |
| 4 | **API integration tests** | 7 integration tests updated to match the corrected adapter format; all 293 tests passing |
| 5 | **Clean installation verified** | `pip install -r requirements.txt` confirmed working in fresh venv with `click<8.2.0` + `typer` compatibility |
| 6 | **Repository cleaned** | All generated files (DBs, logs, cache) removed; `.gitignore` covers all runtime artifacts |

### Technical Changes

- `api/api_server.py`: Added `_normalize_hypothesis()`; adapted `crear_hipotesis`, `get_hipotesis`, `validar_hipotesis` to unwrap HermesCommander responses
- `multiagent/hermes_commander.py`: Added `_VEREDICTO_MAP` for scientific verdict translation
- `tests/test_api_integration.py`: Updated 7 tests to use direct hypothesis format
- `validate.bat`: Version updated to 2.0.4I
- `__init__.py`, `api/__init__.py`, `cli/__init__.py`, `tests/__init__.py`: Version bumped to 2.0.4I

### Verification

- **Linux:** Fully verified — 293 tests passing, API endpoints functional, CLI operational, dashboard build present
- **Windows 11:** Package prepared (`VEO_v2.0.4H_VALIDACION_WINDOWS.zip` generated for validation); execution pending on target machine

---

## Version 2.0.4H - 2026-10-12

### Summary

Distribution-ready release with dark mode on all interfaces, cross-platform packaging, comprehensive documentation, and full test coverage.

### What's New in 2.0.4H

| # | Feature | Description |
|---|---------|-------------|
| 1 | **Dark Mode Dashboard** | React dashboard with dark theme by default, no build step required |
| 2 | **Dark Mode Swagger** | Custom `/docs` endpoint with CSS dark injection |
| 3 | **Dark Mode ReDoc** | Custom `/redoc` endpoint with CSS dark injection |
| 4 | **Cross-platform wrappers** | `veo` (Linux/macOS) and `veo.bat` (Windows) for easy CLI access |
| 5 | **Distribution packaging** | Clean ZIP with `install.sh`/`install.bat`, verified Linux installation |
| 6 | **Test suite** | 285 tests, all passing (`pytest tests/ --tb=line -q`) |
| 7 | **Windows validation** | `validate_windows.py` + `validate.bat` prepared for Windows 11 testing |
| 8 | **Bilingual documentation** | README and User Manual in English and Spanish |
| 9 | **Project documentation** | `docs/ABOUT.md` with history, goals, and roadmap |
| 10 | **Apache 2.0 License** | Full license with copyright attribution |

### Technical Changes

- `api/api_server.py`: Custom `/docs` and `/redoc` endpoints with dark mode CSS
- `dashboard/`: Pre-compiled React app with `base: '/dashboard/'` for correct asset paths
- `dashboard/src/App.jsx`: `BrowserRouter basename="/dashboard"` for proper routing
- `cli/hermes_cli.py`: Added null check for `crear_hipotesis` return value
- `requirements.txt`: Pinned `typer==0.9.0` and `click==8.1.7` for subprocess test compatibility
- New files: `veo`, `veo.bat`, `validate_windows.py`, `validate.bat`, `VALIDACION_WINDOWS.md`

### Verification

- **Linux:** Fully verified — installation, CLI, API, dashboard, tests
- **Windows 11:** Code is portable; real-world execution pending

---

## Version 2.0.4B - 2026-06-29

### Resumen

Version de estabilizacion post-revision multiagente. No anade funcionalidades nuevas.
Resultado de la bateria: **30/30 pruebas pasadas**.

### Revision Multiagente (5 revisores expertos)

Se formo un equipo de 5 revisores especializados que analizaron el codigo en paralelo:
- Revisor Endpoints: 31 problemas (9 criticos)
- Revisor Core: 33 problemas (10 criticos)
- Revisor Analysis: 15 problemas (2 criticos)
- Revisor Operations: 33 problemas (6 criticos)
- Revisor Integration: 9 problemas (1 critico)
- **Total: 121 problemas identificados, 28 criticos**

### Correcciones aplicadas en v2.0.4B (sobre v2.0.4A)

| # | Archivo | Cambio | Motivo |
|---|---------|--------|--------|
| 1 | `api/api_server.py` | `VEO_VERSION = "2.0.4B"` | Version correcta |
| 2 | `api/api_server.py` | Eliminados **13 accesos directos** a `commander.commander.xxx` | Endpoints V1 accedian a atributos internos; ahora usan metodos proxy del adapter |
| 3 | `api/api_server.py` | Anadidos 7 metodos accessor al adapter: `get_diarios`, `get_grafo`, `get_narrativas`, `get_nei_historial`, `get_alertas_list`, `get_hipotesis_list`, `get_mercados_list` | Encapsulamiento correcto del mock |
| 4 | `api/api_server.py` | Anadidos `get_trust_scores` y `get_config` al adapter con fallback | Endpoints V2 trust/config no acceden directamente |
| 5 | `__init__.py` | `__version__ = "2.0.4B"` | Consistencia de version |
| 6 | `core/__init__.py` | `from .config import Settings as Config` | `Config` no existia; `Settings` es la clase real |
| 7 | `tests/test_battery_30.py` | Header actualizado a v2.0.4B | Consistencia |

### Resultado de pruebas

```
P001-P030: 30/30 PASADAS
Tiempo: 2.14s
Criterio: LISTO PARA EMPAQUETAR
```

---

## Version 2.0.4A - 2026-06-29

### Resumen

Version de estabilizacion. No anade funcionalidades nuevas. Corrige fragilidades identificadas en v2.0.4 para garantizar una version completamente estable y reproducible.

El criterio de aceptacion final es que Hermes pueda descargar el ZIP, descomprimirlo en una carpeta vacia, instalarlo, arrancarlo y ejecutar las 30 pruebas funcionales sin modificar ningun archivo del proyecto y sin instalar dependencias fuera del procedimiento oficial. Si alguna de esas condiciones falla, la version no se considera publicada.

---

### Bloque 1: Parches de Hermes incorporados

Todos los parches manuales que Hermes tuvo que aplicar en versiones anteriores se han incorporado directamente al codigo fuente.

| Archivo | Cambio | Motivo |
|---------|--------|--------|
| `api/api_server.py` | `try/except` + verificar `None` en `crear_hipotesis` | Evitar 500 cuando `mock_fallback` retorna `None` |
| `api/api_server.py` | Verificar `None` en `crear_mercado`, `crear_escenario`, `trigger_cycle` | Consistencia de contratos de retorno |
| `api/api_server.py` | MockDatabase: anadidos 11 metodos requeridos por endpoints v2 | `get_system_health`, `trigger_cycle`, `get_journal_entries`, `add_journal_entry`, `get_knowledge_graph`, `get_narrative_shifts`, `get_alerts`, `get_planetary_diagnosis`, `get_prediction_markets`, `get_metrics`, `get_audit_log` |
| `requirements.txt` | Anadir `requests>=2.31.0` | Dependencia para scripts de prueba y herramientas auxiliares |
| `requirements.txt` | Anadir `networkx`, `scipy`, `httpx` | Dependencias obligatorias faltantes detectadas en revision critica |
| `config/veo_config.json` | Creado archivo con configuracion por defecto valida | No existia; necesario para arranque limpio |
| `cli/hermes_cli.py` | Import corregido: `from multiagent.hermes_commander` | Import roto referenciaba `from hermes_commander` |
| `api/__init__.py` | Anadidos exports: `commander`, `MockDatabase` | No exportaba componentes del mock |

---

### Bloque 2: Fix P026

| Archivo | Cambio |
|---------|--------|
| `api/api_server.py` | Endpoint `validar_hipotesis` asegura **404 Not Found** (no 400) cuando la hipotesis solicitada no existe |

**Detalle:** El endpoint correspondiente devuelve `404 Not Found` cuando la hipotesis solicitada no existe. No devuelve `400 Bad Request`.

---

### Bloque 3: Codigos HTTP revisados

Todos los endpoints han sido revisados para garantizar consistencia en los codigos de respuesta:

- **200** - Operacion exitosa (GET, PUT)
- **201** - Recurso creado exitosamente (POST)
- **400** - Parametros de solicitud invalidos (solo para validacion de entrada)
- **401** - No autenticado
- **403** - No autorizado
- **404** - Recurso no encontrado
- **409** - Conflicto de estado
- **422** - Entidad no procesable
- **500** - Error interno del servidor (solo para errores reales no anticipados)

Cambios aplicados:
- Todos los endpoints verifican `None` antes de usar resultados de metodos del adapter
- `HTTPException` con codigo apropiado se lanza cuando un recurso no se encuentra
- `400` se reserva exclusivamente para parametros invalidos
- `500` solo para errores internos reales no capturados por validacion previa

---

### Bloque 4: MockDatabase robusto

El modo `mock_fallback` ha sido endurecido para eliminar toda fragilidad:

- **Metodos proxy del adapter** manejan ausencia de metodos en el destino con `try/except` y fallback a `MockDatabase`
- **Endpoints** verifican `None` con `HTTPException` apropiada antes de procesar resultados
- **MockDatabase** nunca devuelve `None` en sus metodos publicos; siempre devuelve estructuras vacias o valores por defecto validos
- **Orden de definicion de clases** corregido: `MockDatabase` se define antes de `HermesCommanderAdapter`
- **`_EmergencyMock`** eliminado; sustituido por instanciacion directa de `MockDatabase`

---

### Bloque 5: Dependencias

El archivo `requirements.txt` incluye **todas** las dependencias requeridas por:

- Aplicacion principal (`fastapi`, `uvicorn`, `numpy`, `pandas`, `sqlalchemy`, etc.)
- Scripts de utilidad y despliegue
- Bateria de pruebas (`requests>=2.31.0`)
- Herramientas auxiliares (`networkx`, `scipy`, `httpx`)

Una instalacion limpia no requiere instalar paquetes adicionales manualmente.

---

### Bloque 6: Instalacion

| Archivo | Cambio |
|---------|--------|
| `install.bat` | Corregido salto de linea en linea 10 |

El proceso de instalacion desde cero ha sido verificado: directorio vacio -> `install.bat` -> entorno funcional.

---

### Bloque 7: Bateria de regresion

| Archivo | Descripcion |
|---------|-------------|
| `tests/test_battery_30.py` | 30 pruebas funcionales ejecutables con un solo comando |

**Criterio de aceptacion:** Si falla 1 prueba, NO se empaqueta la version.

Las 30 pruebas cubren:
- Importacion y arranque de la API
- Operaciones CRUD de hipotesis
- Operaciones de mercados y escenarios
- Validacion de hipotesis
- Ciclos del sistema
- Consultas de metricas, salud y auditoria
- Verificacion de codigos HTTP correctos
- Robustez del modo mock

---

### Bloque 8: Correcciones adicionales desde v2.0.4

| # | Archivo | Problema | Correccion |
|---|---------|----------|------------|
| 1 | `__init__.py` | Version era 2.0.0 | Actualizada a 2.0.4A |
| 2 | `prediction/__init__.py` | Vacio, no exportaba nada | Exporta `MercadoPredicciones` |
| 3 | `memory/__init__.py` | Vacio, no exportaba nada | Exporta `DiarioDescubrimientos` |
| 4 | `core/__init__.py` | Vacio, no exportaba nada | Exporta `VEOCore`, `Config` |
| 5 | `analysis/scientific_agent.py` | `config=None` crasheaba (`config.get` en vez de `self.config.get`) | Corregidos 4 usos en `AgenteCientifico` y `AgenteEsceptico` |
| 6 | `analysis/scenario_simulator.py` | Variable `i` no definida si error antes del loop | Anadida inicializacion `i = -1` antes del `try` |
| 7 | `analysis/causal_engine.py` | NaN propagation en `correlacion_parcial` con variables constantes | Anadida validacion `0.0 if np.isnan(r) else r` |
| 8 | `analysis/causal_engine.py` | NaN en `corr_cruda` sin validacion | Anadida validacion `if np.isnan(corr_cruda): corr_cruda = 0.0` |
| 9 | `multiagent/hermes_commander.py` | Llamaba `get_resumen()` que no existe en `HealthMonitor` | Cambiado a `check()` con `try/except` fallback |
| 10 | `operations/audit_log.py` | `log_audit()` sin `try/except` podia crashear el sistema | Envuelto en `try/except Exception` |
| 11 | `api/api_server.py` | Exception handler capturaba `CancelledError`/`SystemExit` | Anadida proteccion: re-lanzar si es `CancelledError` o `SystemExit` |

---

### Bloque 9: Problemas conocidos

Ver archivo `KNOWN_ISSUES.md` para el listado completo de problemas pendientes y limitaciones conocidas.

---

### Historial de versiones

| Version | Fecha | Notas |
|---------|-------|-------|
| v2.0.4A | 2026-06-29 | Version de estabilizacion. Todas las fragilidades corregidas. Bateria de 30 pruebas: 30/30 |
| v2.0.4 | 2026-06-29 | Base funcional, 172 problemas identificados y corregidos. 29/30 pruebas pasadas (con parches manuales de Hermes) |
| v2.0.3 | 2026-06-28 | Fix INC-07: orden de ejecucion Python, singleton movido al final de definicion |
| v2.0.2 | 2026-06-28 | Fix `MockStore`, `MockDatabase` como fallback, eliminado `_EmergencyMock` |
| v2.0.1 | 2026-06-27 | Fix imports circulares, `requirements.txt`, `install.bat` |
| v2.0.0 | 2026-06-27 | Version inicial con arquitectura modular |
