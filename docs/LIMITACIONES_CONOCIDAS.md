# Limitaciones Conocidas — VEO

> Documento de referencia: castellano.  
> Version tecnica de referencia: 2.0.5.  
> Fecha de redaccion: 2026-11-12.

Este documento describe las limitaciones reales y conocidas del sistema VEO, contrastadas con el codigo fuente. No se omiten defectos ni se presentan como completas las funcionalidades que tienen limitaciones.

---

## 1. Sistema de Escenarios

### 1.1 Estado general

El sistema de escenarios permite crear escenarios de simulacion, listarlos, recuperarlos individualmente, ejecutar simulaciones Monte Carlo y consultar resultados. Sin embargo, presenta los siguientes problemas conocidos.

### 1.2 Problema identificado: validacion de respuesta en GET individual y simulacion

| Operacion | Endpoint | Codigo HTTP real | Codigo esperado | Causa |
|-----------|----------|------------------|-----------------|-------|
| Crear escenario | `POST /api/v1/escenarios` | 201 | 201 | Funciona correctamente |
| Listar escenarios | `GET /api/v1/escenarios` | 200 | 200 | Funciona correctamente |
| Recuperar escenario individual | `GET /api/v1/escenarios/{sid}` | **500** | 200 o 404 | `ResponseValidationError` de FastAPI/Pydantic |
| Simular escenario | `POST /api/v1/escenarios/{sid}/simular` | **500** | 200 o 404 | `ResponseValidationError` de FastAPI/Pydantic |
| Resultados sin simulacion | `GET /api/v1/escenarios/{sid}/resultados` | 400 | 400 | Funciona correctamente |
| Identificador inexistente | `GET /api/v1/escenarios/{sid_inexistente}` | **500** | 404 | `ResponseValidationError` de FastAPI/Pydantic |

### 1.3 Causa tecnica

El endpoint `GET /api/v1/escenarios/{sid}` y el endpoint `POST /api/v1/escenarios/{sid}/simular` tienen definido un `response_model=EscenarioResponse` en FastAPI. Cuando el adapter `HermesCommanderAdapter` no encuentra el escenario solicitado (porque `HermesCommander` devuelve un diccionario de error o `None`), el adapter retorna un valor que no cumple el esquema `EscenarioResponse` esperado por FastAPI. Esto provoca un `ResponseValidationError` interno de Pydantic, que se traduce en un codigo HTTP 500.

El mismo problema ocurre cuando se solicita un identificador inexistente: el adapter deberia devolver `None` (lo que el endpoint convertiria en HTTP 404 via `raise HTTPException(status_code=404, ...)`), pero en su lugar devuelve un diccionario de error del commander que no cumple el esquema, causando el 500.

### 1.4 Ubicacion en el codigo

- Endpoint `GET /api/v1/escenarios/{sid}`: `api/api_server.py`, decorador `@app.get("/api/v1/escenarios/{sid}", response_model=EscenarioResponse, ...)`
- Endpoint `POST /api/v1/escenarios/{sid}/simular`: `api/api_server.py`, decorador `@app.post("/api/v1/escenarios/{sid}/simular", response_model=EscenarioResponse, ...)`
- Adapter `get_escenario()`: `api/api_server.py`, metodo `HermesCommanderAdapter.get_escenario()`
- Adapter `simular_escenario()`: `api/api_server.py`, metodo `HermesCommanderAdapter.simular_escenario()`
- Modelo `EscenarioResponse`: `api/api_server.py`, dataclass con campos `id`, `nombre`, `variables`, `iteraciones`, `resultado`, `fecha_creacion`

### 1.5 Impacto

Un usuario que cree un escenario via `POST /api/v1/escenarios` obtendra correctamente el identificador y podra listarlo via `GET /api/v1/escenarios`. Sin embargo, no podra recuperarlo individualmente ni simularlo via API REST sin recibir un error HTTP 500.

---

## 2. Mercados de Prediccion

El motor matematico CPMM (Constant Product Market Maker) esta implementado y es funcional. Sin embargo:

- La integracion con `HermesCommander` usa `MockDatabase` como fallback cuando el commander no implementa los metodos de mercado.
- El Dashboard no consume la API de mercados; muestra datos hardcodeados.
- Las ordenes de compra/venta se procesan en memoria (MockDatabase) y no se persisten en SQLite.

---

## 3. Grafo Causal

- El backend utiliza NetworkX real para el analisis de relaciones causales.
- El Dashboard, sin embargo, muestra datos estaticos precargados en lugar de consumir el grafo del backend.

---

## 4. Simulacion Monte Carlo

- El backend de escenarios incluye una simulacion Monte Carlo funcional.
- El Dashboard utiliza su propia simulacion JavaScript independiente, no consume los resultados del backend.

---

## 5. Deteccion de Desplazamiento Narrativo

- Existe unicamente en el panel del Dashboard con datos de ejemplo.
- No hay backend real de analisis de narrativa.

---

## 6. Diario de Descubrimiento

- Funciona con datos de ejemplo precargados en `MockDatabase`.
- No existe un sistema real de registro de descubrimientos.

---

## 7. Auditoria del Sistema

- Existen tres modulos funcionales: `operations/audit_log.py`, `operations/trust_layer.py`, `operations/health_monitor.py`.
- Estan implementados pero son **standalone**: no estan integrados en el flujo principal de ejecucion de VEO.
- No se invocan automaticamente desde `HermesCommander` ni desde los ciclos de `veo_core.py`.

---

## 8. Ciclos Automaticos

- `veo_core.py` define 4 ciclos (Razonamiento, Pronostico, Ejecutivo, Operaciones).
- No existe un scheduler real que ejecute estos ciclos de forma automatica y periodica.

---

## 9. Persistencia

- SQLite esta implementado y funcional (`sois.db`, `veo_data.db`).
- Sin embargo, muchos endpoints de la API usan `MockDatabase` (almacenamiento en memoria) como fallback cuando `HermesCommander` no tiene el metodo correspondiente.
- Esto significa que datos creados via API pueden no persistir entre reinicios del servidor.

---

## 10. Tests

- **304 pruebas recopiladas.**
- **304 pruebas superadas** en la ejecucion anterior de Hermes.
- El resultado de las pruebas unitarias no elimina las limitaciones funcionales descritas en este documento.

---

## 11. Dependencias

- `sentence-transformers` no esta incluido en `requirements.txt` porque requiere PyTorch (~2 GB) y dependencias CUDA.
- El codigo tiene `try/except` fallback para funcionar sin `sentence-transformers`, usando heuristicas deterministas.

---

## 12. Dashboard React

- 4 paneles consumen la API (DashboardOverview, HypothesisPanel, SystemHealthPanel, ConfigPanel). No todos presentan datos reales: las rutas de salud del sistema, estado y ciclos caen en datos simulados cuando HermesCommander no implementa el metodo.
- 6 paneles muestran datos estaticos, mock o hardcodeados (mercados, grafo causal, desplazamiento narrativo, diario, auditoria, ciclos automaticos).

---

## Resumen por Componente

| Componente | Estado real | Nota |
|------------|-------------|------|
| API REST (FastAPI) | Funcional con limitaciones | ~41 endpoints. Algunos usan MockDatabase fallback. Escenarios: GET individual y simular devuelven 500. |
| CLI (Typer) | Funcional con limitaciones | ~38 comandos. Algunos caen en mock. |
| WebSocket | Funcional | Broadcast corregido en version 2.0.5. Eventos en tiempo real. |
| Dashboard React | Parcial | 4 paneles consumen la API (algunas rutas con datos simulados), 6 paneles mock/estaticos. |
| Persistencia SQLite | Parcial | Funcional pero muchos endpoints usan memoria. |
| Motor de hipotesis | Parcial | Validacion determinista sin NLP/embeddings reales. |
| Mercados de prediccion | Parcial | Motor CPMM real, integracion con mock. |
| Grafo causal | Parcial | Backend real, Dashboard estatico. |
| Simulacion Monte Carlo | Parcial | Backend funcional, Dashboard usa JS propio. |
| Diagnostico planetario | Funcional | Motor completo con 100 familias de configuracion. |
| Backup / Restore | Funcional | Operaciones V2 implementadas. |
| Auditoria del sistema | Mock | Modulos standalone, no integrados. |
| Ciclos automaticos | Mock | Definidos sin scheduler real. |
| Deteccion de desplazamiento narrativo | Mock | Solo en Dashboard. |
| Diario de descubrimiento | Mock | Datos de ejemplo. |
