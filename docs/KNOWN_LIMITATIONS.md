# Known Limitations — VEO

> Reference document: English.  
> Technical reference version: 2.0.5.  
> Date of drafting: 2026-11-12.

This document describes the real and known limitations of the VEO system, cross-checked against the source code. Defects are not omitted, and functionalities with limitations are not presented as complete.

---

## 1. Scenario System

### 1.1 General Status

The scenario system allows creating simulation scenarios, listing them, retrieving individual scenarios, running Monte Carlo simulations, and querying results. However, it presents the following known issues.

### 1.2 Identified Problem: Response Validation in Individual GET and Simulation

| Operation | Endpoint | Actual HTTP Code | Expected Code | Cause |
|-----------|----------|------------------|---------------|-------|
| Create scenario | `POST /api/v1/escenarios` | 201 | 201 | Works correctly |
| List scenarios | `GET /api/v1/escenarios` | 200 | 200 | Works correctly |
| Retrieve individual scenario | `GET /api/v1/escenarios/{sid}` | **500** | 200 or 404 | FastAPI/Pydantic `ResponseValidationError` |
| Simulate scenario | `POST /api/v1/escenarios/{sid}/simular` | **500** | 200 or 404 | FastAPI/Pydantic `ResponseValidationError` |
| Results without simulation | `GET /api/v1/escenarios/{sid}/resultados` | 400 | 400 | Works correctly |
| Non-existent identifier | `GET /api/v1/escenarios/{nonexistent_sid}` | **500** | 404 | FastAPI/Pydantic `ResponseValidationError` |

### 1.3 Technical Cause

The endpoint `GET /api/v1/escenarios/{sid}` and the endpoint `POST /api/v1/escenarios/{sid}/simular` have a `response_model=EscenarioResponse` defined in FastAPI. When the `HermesCommanderAdapter` does not find the requested scenario (because `HermesCommander` returns an error dictionary or `None`), the adapter returns a value that does not match the `EscenarioResponse` schema expected by FastAPI. This triggers an internal Pydantic `ResponseValidationError`, which translates to an HTTP 500 code.

The same problem occurs when a non-existent identifier is requested: the adapter should return `None` (which the endpoint would convert to HTTP 404 via `raise HTTPException(status_code=404, ...)`), but instead it returns an error dictionary from the commander that does not match the schema, causing the 500.

### 1.4 Location in Code

- Endpoint `GET /api/v1/escenarios/{sid}`: `api/api_server.py`, decorator `@app.get("/api/v1/escenarios/{sid}", response_model=EscenarioResponse, ...)`
- Endpoint `POST /api/v1/escenarios/{sid}/simular`: `api/api_server.py`, decorator `@app.post("/api/v1/escenarios/{sid}/simular", response_model=EscenarioResponse, ...)`
- Adapter `get_escenario()`: `api/api_server.py`, method `HermesCommanderAdapter.get_escenario()`
- Adapter `simular_escenario()`: `api/api_server.py`, method `HermesCommanderAdapter.simular_escenario()`
- Model `EscenarioResponse`: `api/api_server.py`, dataclass with fields `id`, `nombre`, `variables`, `iteraciones`, `resultado`, `fecha_creacion`

### 1.5 Impact

A user who creates a scenario via `POST /api/v1/escenarios` will correctly receive the identifier and be able to list it via `GET /api/v1/escenarios`. However, they will not be able to retrieve it individually or simulate it via the REST API without receiving an HTTP 500 error.

---

## 2. Prediction Markets

The CPMM (Constant Product Market Maker) mathematical engine is implemented and functional. However:

- Integration with `HermesCommander` uses `MockDatabase` as a fallback when the commander does not implement market methods.
- The Dashboard does not consume the markets API; it displays hardcoded data.
- Buy/sell orders are processed in memory (MockDatabase) and are not persisted in SQLite.

---

## 3. Causal Graph

- The backend uses real NetworkX for causal relationship analysis.
- The Dashboard, however, displays preloaded static data instead of consuming the backend graph.

---

## 4. Monte Carlo Simulation

- The scenario backend includes a functional Monte Carlo simulation.
- The Dashboard uses its own independent JavaScript simulation and does not consume backend results.

---

## 5. Narrative Shift Detection

- Exists only in the Dashboard panel with example data.
- There is no real narrative analysis backend.

---

## 6. Discovery Journal

- Works with preloaded example data in `MockDatabase`.
- There is no real discovery logging system.

---

## 7. System Audit

- Three functional modules exist: `operations/audit_log.py`, `operations/trust_layer.py`, `operations/health_monitor.py`.
- They are implemented but are **standalone**: they are not integrated into VEO's main execution flow.
- They are not automatically invoked from `HermesCommander` or from `veo_core.py` cycles.

---

## 8. Automatic Cycles

- `veo_core.py` defines 4 cycles (Reasoning, Forecast, Executive, Operations).
- There is no real scheduler that executes these cycles automatically and periodically.

---

## 9. Persistence

- SQLite is implemented and functional (`sois.db`, `veo_data.db`).
- However, many API endpoints use `MockDatabase` (in-memory storage) as a fallback when `HermesCommander` does not have the corresponding method.
- This means that data created via API may not persist between server restarts.

---

## 10. Tests

- **304 tests collected.**
- **304 tests passed** in Hermes' previous execution.
- The result of unit tests does not eliminate the functional limitations described in this document.

---

## 11. Dependencies

- `sentence-transformers` is not included in `requirements.txt` because it requires PyTorch (~2 GB) and CUDA dependencies.
- The code has a `try/except` fallback to work without `sentence-transformers`, using deterministic heuristics.

---

## 12. React Dashboard

- 4 panels consume the API (DashboardOverview, HypothesisPanel, SystemHealthPanel, ConfigPanel). Not all display real data: the system health, status, and cycles routes fall back to simulated data when HermesCommander does not implement the method.
- 6 panels display static, mock, or hardcoded data (markets, causal graph, narrative shift, journal, audit, automatic cycles).

---

## Summary by Component

| Component | Real Status | Note |
|-----------|-------------|------|
| REST API (FastAPI) | Functional with limitations | ~41 endpoints. Some use MockDatabase fallback. Scenarios: individual GET and simulate return 500. |
| CLI (Typer) | Functional with limitations | ~38 commands. Some fall back to mock. |
| WebSocket | Functional | Broadcast corrected in version 2.0.5. Real-time events. |
| React Dashboard | Partial | 4 panels consume the API (some routes with simulated data), 6 mock/static panels. |
| SQLite Persistence | Partial | Functional but many endpoints use memory. |
| Hypothesis Engine | Partial | Deterministic validation without real NLP/embeddings. |
| Prediction Markets | Partial | Real CPMM engine, integration with mock. |
| Causal Graph | Partial | Real backend, static Dashboard. |
| Monte Carlo Simulation | Partial | Functional backend, Dashboard uses own JS. |
| Planetary Diagnostic | Functional | Complete engine with 100 config families. |
| Backup / Restore | Functional | V2 operations implemented. |
| System Audit | Mock | Standalone modules, not integrated. |
| Automatic Cycles | Mock | Defined without real scheduler. |
| Narrative Shift Detection | Mock | Dashboard only. |
| Discovery Journal | Mock | Example data. |
