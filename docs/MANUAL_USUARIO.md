# Manual de Usuario — VEO v2.0.5

Vigilancia de Emergencias Observables (VEO)

---

## Indice

1. [Descripcion General](#1-descripcion-general)
2. [Estado del Proyecto](#2-estado-del-proyecto)
3. [Requisitos del Sistema](#3-requisitos-del-sistema)
4. [Instalacion](#4-instalacion)
5. [Primer Uso](#5-primer-uso)
6. [Interfaz de Linea de Comandos (CLI)](#6-interfaz-de-linea-de-comandos-cli)
7. [API REST](#7-api-rest)
8. [Dashboard Web](#8-dashboard-web)
9. [WebSocket](#9-websocket)
10. [Estructura de Directorios](#10-estructura-de-directorios)
11. [Configuracion](#11-configuracion)
12. [Solucion de Problemas](#12-solucion-de-problemas)
13. [FAQ](#13-faq)
14. [Advertencia Final](#14-advertencia-final)

---

## 1. Descripcion General

VEO es una plataforma de inteligencia situacional que permite:

- **Crear y validar hipotesis** mediante agentes cientifico y esceptico (validacion dual)
- **Monitorear mercados de prediccion** con cierres automaticos basados en evidencia
- **Analizar grafos causales** para detectar relaciones entre eventos
- **Simular escenarios** con el metodo Monte Carlo
- **Detectar desplazamiento narrativo** mediante analisis de tendencias
- **Mantener un diario de descubrimiento** interactivo
- **Validar la arquitectura** del sistema multicapa
- **Ejecutar diagnosticos planetarios** sobre 100 familias de configuracion

Todo a traves de una **API REST con FastAPI**, un **Dashboard React con WebSocket** y una **CLI con Typer**.

---

## 2. Estado del Proyecto

**VEO v2.0.5** es un proyecto en desarrollo activo. Las funcionalidades se dividen en tres categorias:

| Estado | Descripcion |
|--------|-------------|
| **Funcional** | Componente implementado, probado y operativo. |
| **Mock** | Componente con datos de ejemplo o fallback. Funciona como demostracion pero no con datos reales. |
| **Pendiente** | Componente planificado pero no implementado. |

### Componentes principales

| Componente | Estado | Notas |
|------------|--------|-------|
| API REST (FastAPI) | **Funcional** | Todos los endpoints V1 y V2 operativos |
| CLI (Typer) | **Funcional** | Todos los comandos implementados |
| WebSocket | **Funcional** | Eventos en tiempo real |
| Dashboard React | **Funcional** | Paneles Overview, Hipotesis y Salud con datos reales. Resto con datos mock |
| Persistencia SQLite | **Funcional** | aiosqlite con tabla hipotesis |
| Agentes (cientifico + esceptico) | **Funcional** | Validacion dual real |
| Mercados de prediccion | **Funcional** | Creacion, trade y resolucion operativos |
| Simulador Monte Carlo | **Funcional** | Creacion y ejecucion de escenarios |
| Diario de descubrimiento | **Mock** | Datos de ejemplo |
| Grafo causal | **Mock** | Datos de ejemplo |
| Analisis narrativo | **Mock** | Datos de ejemplo |
| Auditoria del sistema | **Mock** | Fallback transparente |
| Ciclos automaticos | **Mock** | Estado de ciclos con datos de ejemplo |
| Diagnostico planetario | **Funcional** | Evaluacion de 100 familias |
| Backup / Restore | **Funcional** | Operaciones V2 implementadas |

---

## 3. Requisitos del Sistema

| Componente | Requisito |
|------------|-----------|
| Sistema operativo | Linux (principal) o Windows 11 |
| Python | 3.12 (recomendado). Compatible con 3.11+ |
| Node.js | 20.20.2+ (solo para compilar el Dashboard) |
| npm | 11.19.0+ (solo para compilar el Dashboard) |
| Memoria RAM | 4 GB minimo, 8 GB recomendado |
| Disco | 500 MB para la instalacion |

**Dependencias Python principales:**
- FastAPI + Uvicorn (servidor API)
- aiosqlite (persistencia SQLite)
- Typer + Click (CLI)
- websockets (WebSocket nativo)
- psutil (metricas del sistema, opcional)
- pytest (tests)

**Dependencias Node.js (Dashboard):**
- React 18.2+
- Recharts (graficos)
- React Router DOM 6.20+
- Vite 5.0+ (build tool)

---

## 4. Instalacion

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

El script `install.bat` crea un entorno virtual, instala las dependencias Python y ejecuta los tests para verificar la instalacion.

### 4.3 Instalacion manual (avanzado)

Si prefieres controlar cada paso:

```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
pip install -r requirements.txt
python -m pytest tests/ -q
```

### 4.4 Compilacion del Dashboard

El Dashboard React se compila con Vite. Solo necesitas hacerlo una vez (o despues de modificar el codigo fuente):

```bash
cd dashboard
npm install
npm run build
```

En Windows:
```cmd
cd dashboard
npm install
npm run build
```

Esto genera los archivos estaticos en `dashboard/build/` que FastAPI sirve automaticamente.

---

## 5. Primer Uso

### 5.1 Iniciar el servidor API

```bash
python -m uvicorn api.api_server:app --host 0.0.0.0 --port 8000
```

O usa la CLI:
```bash
python cli/hermes_cli.py serve --host 0.0.0.0 --port 8000
```

### 5.2 Verificar que funciona

```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/v2/system/health
```

Debe devolver un JSON con el estado del sistema.

### 5.3 Abrir el Dashboard

Abre tu navegador en:
```
http://localhost:8000/dashboard/
```

### 5.4 Usar la CLI

En otra terminal (con el venv activado):

```bash
python cli/hermes_cli.py --help
python cli/hermes_cli.py version
python cli/hermes_cli.py health
```

---

## 6. Interfaz de Linea de Comandos (CLI)

La CLI utiliza Typer. Todos los comandos se invocan con:

```bash
python cli/hermes_cli.py <comando> [opciones]
```

### 6.1 Comandos basicos

| Comando | Descripcion | Ejemplo |
|---------|-------------|---------|
| `version` | Muestra la version de VEO | `python cli/hermes_cli.py version` |
| `health` | Estado de salud del sistema | `python cli/hermes_cli.py health` |
| `status` | Estado general del sistema | `python cli/hermes_cli.py status` |
| `metrics` | Metricas en tiempo real | `python cli/hermes_cli.py metrics` |
| `audit` | Log de auditoria del sistema | `python cli/hermes_cli.py audit --lines 20` |
| `serve` | Inicia el servidor API (uvicorn) | `python cli/hermes_cli.py serve --host 0.0.0.0 --port 8000` |

### 6.2 Gestion de hipotesis

| Comando | Descripcion | Ejemplo |
|---------|-------------|---------|
| `hypothesis create` | Crear una nueva hipotesis | `python cli/hermes_cli.py hypothesis create "El cambio climatico aumenta huracanes"` |
| `hypothesis list` | Listar hipotesis | `python cli/hermes_cli.py hypothesis list` |
| `hypothesis show` | Mostrar detalle de una hipotesis | `python cli/hermes_cli.py hypothesis show H-001` |
| `validate` | Validar una hipotesis (validacion dual) | `python cli/hermes_cli.py validate H-001` |

**Nota:** El comando `validate` es un comando raiz, no un subcomando de `hypothesis`.

### 6.3 Mercados de prediccion

| Comando | Descripcion | Ejemplo |
|---------|-------------|---------|
| `market create` | Crear mercado para una hipotesis | `python cli/hermes_cli.py market create H-001 "SI,NO,QUIZAS"` |
| `market list` | Listar mercados | `python cli/hermes_cli.py market list` |
| `market trade` | Realizar trade en un escenario | `python cli/hermes_cli.py market trade M-001 SI 100.0` |
| `market resolve` | Resolver mercado con ganador | `python cli/hermes_cli.py market resolve M-001 SI` |
| `market prices` | Mostrar precios de escenarios | `python cli/hermes_cli.py market prices M-001` |

### 6.4 Simulacion

| Comando | Descripcion | Ejemplo |
|---------|-------------|---------|
| `simulate create` | Crear escenario (interactivo) | `python cli/hermes_cli.py simulate create "Escenario A"` |
| `simulate run` | Ejecutar simulacion Monte Carlo | `python cli/hermes_cli.py simulate run ESC-001` |
| `simulate compare` | Comparar dos escenarios | `python cli/hermes_cli.py simulate compare ESC-001 ESC-002` |

### 6.5 Diario de descubrimiento

| Comando | Descripcion | Ejemplo |
|---------|-------------|---------|
| `journal` | Mostrar ultimo informe semanal | `python cli/hermes_cli.py journal` |
| `journal history` | Mostrar historial de semanas | `python cli/hermes_cli.py journal history` |

### 6.6 Grafo de conocimiento

| Comando | Descripcion | Ejemplo |
|---------|-------------|---------|
| `graph stats` | Estadisticas del grafo | `python cli/hermes_cli.py graph stats` |
| `graph paths` | Caminos entre nodos | `python cli/hermes_cli.py graph paths nodoA nodoB` |

### 6.7 Narrativa y alertas

| Comando | Descripcion | Ejemplo |
|---------|-------------|---------|
| `narrative` | Cambios de narrativa detectados | `python cli/hermes_cli.py narrative` |
| `alert` | Alertas activas del sistema | `python cli/hermes_cli.py alert` |
| `explain` | Explicar una alerta | `python cli/hermes_cli.py explain ALERT-001` |

### 6.8 Configuracion y sistema

| Comando | Descripcion | Ejemplo |
|---------|-------------|---------|
| `config` | Mostrar configuracion actual | `python cli/hermes_cli.py config` |
| `system` | Estado completo del sistema | `python cli/hermes_cli.py system` |
| `trust` | Mostrar nivel de confianza del sistema | `python cli/hermes_cli.py trust` |

### 6.9 Operaciones (V2)

| Comando | Descripcion | Ejemplo |
|---------|-------------|---------|
| `operations backup` | Crear backup | `python cli/hermes_cli.py operations backup` |
| `operations restore` | Restaurar desde backup | `python cli/hermes_cli.py operations restore BACKUP-001` |
| `operations list` | Listar backups disponibles | `python cli/hermes_cli.py operations list` |

### 6.10 Ciclos (V2)

| Comando | Descripcion | Ejemplo |
|---------|-------------|---------|
| `cycles` | Estado de los 4 ciclos | `python cli/hermes_cli.py cycles` |
| `trigger` | Ejecutar ciclo bajo demanda | `python cli/hermes_cli.py trigger reasoning --reason "Revision manual"` |

### 6.11 Diagnostico planetario

| Comando | Descripcion | Ejemplo |
|---------|-------------|---------|
| `planetary status` | Estado del diagnostico planetario | `python cli/hermes_cli.py planetary status` |
| `planetary config` | Configuracion de una familia | `python cli/hermes_cli.py planetary config continuity` |
| `planetary alerts` | Alertas planetarias activas | `python cli/hermes_cli.py planetary alerts` |
| `planetary run` | Ejecutar diagnostico planetario | `python cli/hermes_cli.py planetary run` |

### 6.12 Shell interactivo

| Comando | Descripcion | Ejemplo |
|---------|-------------|---------|
| `shell` | Modo interactivo (REPL) | `python cli/hermes_cli.py shell` |

---

## 7. API REST

### 7.1 Endpoints de hipotesis (V1)

| Metodo | Endpoint | Descripcion |
|--------|----------|-------------|
| GET | `/api/v1/hipotesis` | Listar todas las hipotesis |
| POST | `/api/v1/hipotesis` | Crear nueva hipotesis |
| GET | `/api/v1/hipotesis/{id}` | Obtener hipotesis por ID |
| POST | `/api/v1/hipotesis/{id}/validar` | Validar hipotesis |

**Ejemplo:** Crear hipotesis
```bash
curl -X POST http://localhost:8000/api/v1/hipotesis \
  -H "Content-Type: application/json" \
  -d '{"texto": "El cambio climatico aumenta la frecuencia de huracanes", "tags": ["clima", "huracanes"]}'
```

**Ejemplo:** Listar hipotesis
```bash
curl http://localhost:8000/api/v1/hipotesis
```

### 7.2 Endpoints de mercados (V1)

| Metodo | Endpoint | Descripcion |
|--------|----------|-------------|
| GET | `/api/v1/mercados` | Listar mercados |
| POST | `/api/v1/mercados` | Crear mercado |
| GET | `/api/v1/mercados/{id}` | Obtener mercado |
| POST | `/api/v1/mercados/{id}/trade` | Realizar trade |
| POST | `/api/v1/mercados/{id}/resolver` | Resolver mercado |

**Ejemplo:** Crear mercado
```bash
curl -X POST http://localhost:8000/api/v1/mercados \
  -H "Content-Type: application/json" \
  -d '{
    "hipotesis_id": "H-001",
    "pregunta": "Habra una tormenta solar en 2025?",
    "escenarios": {"SI": 0.5, "NO": 0.5},
    "fecha_cierre": "2025-12-31"
  }'
```

### 7.3 Endpoints de escenarios (V1)

| Metodo | Endpoint | Descripcion |
|--------|----------|-------------|
| GET | `/api/v1/escenarios` | Listar escenarios | **Mock** |
| POST | `/api/v1/escenarios` | Crear escenario de simulacion | **Funcional** |
| POST | `/api/v1/escenarios/{id}/simular` | Ejecutar simulacion Monte Carlo | **Funcional** |
| GET | `/api/v1/escenarios/{id}/resultados` | Obtener resultados de simulacion | **Mock** |
| GET | `/api/v1/diario/actual` | Entrada actual del diario | **Mock** |
| GET | `/api/v1/diario/historial` | Historial del diario | **Mock** |
| GET | `/api/v1/grafo/estadisticas` | Estadisticas del grafo de conocimiento | **Mock** |
| GET | `/api/v1/grafo/nodos` | Listar nodos del grafo | **Mock** |
| GET | `/api/v1/grafo/caminos` | Caminos entre nodos | **Mock (hardcoded)** |
| GET | `/api/v1/narrativa/cambios` | Cambios de narrativa detectados | **Mock** |
| GET | `/api/v1/nei` | Indice de estabilidad narrativa | **Mock** |
| GET | `/api/v1/alertas` | Alertas activas | **Mock** |
| GET | `/api/v1/estadisticas` | Estadisticas globales del sistema | **Mock** |
| GET | `/api/v1/ws/stats` | Estadisticas de conexiones WebSocket | **Funcional** |

### 7.4 Endpoints del sistema (V2)

| Metodo | Endpoint | Descripcion | Estado |
|--------|----------|-------------|--------|
| GET | `/api/v2/system/health` | Salud del sistema | **Funcional** |
| GET | `/api/v2/system/status` | Estado del sistema | **Funcional** |
| GET | `/api/v2/system/metrics` | Metricas del sistema | **Funcional (con fallback)** |
| GET | `/api/v2/system/audit` | Auditoria del sistema | **Mock** |
| GET | `/api/v2/cycles/status` | Estado de ciclos | **Mock** |
| POST | `/api/v2/cycles/trigger` | Disparar ciclo | **Funcional** |
| GET | `/api/v2/operations/backups` | Listar backups existentes | **Funcional** |
| POST | `/api/v2/operations/backup` | Crear backup | **Funcional** |
| POST | `/api/v2/operations/restore` | Restaurar backup | **Funcional** |
| GET | `/api/v2/explain/{alert_id}` | Explicar una alerta | **Mock** |
| GET | `/api/v2/system/trust` | Scores de confianza por componente | **Mock (hardcoded)** |
| GET | `/api/v2/system/config` | Configuracion del sistema | **Funcional** |

### 7.5 Health check

| Metodo | Endpoint | Descripcion |
|--------|----------|-------------|
| GET | `/health` | Health check basico |

### 7.6 WebSocket

| Protocolo | Endpoint | Descripcion |
|-----------|----------|-------------|
| WS | `/ws` | Eventos en tiempo real |

---

## 8. Dashboard Web

El Dashboard es una aplicacion React que se sirve como contenido estatico desde FastAPI en `/dashboard/`.

### 8.1 Paneles principales

| Panel | Descripcion | Datos |
|-------|-------------|-------|
| **Vision General** | Metricas del sistema, grafico NEI, alertas, estado de servicios, actividad en tiempo real | **Reales** (API) |
| **Hipotesis** | Lista de hipotesis con filtros, validacion, detalle | **Reales** (API) |
| **Salud** | Health score, estado del sistema, ciclos | **Reales** (API) |
| **Mercado de Prediccion** | Mercados activos, probabilidades, trades | **Mock** (ejemplo) |
| **Grafo Causal** | Visualizacion del grafo de conocimiento | **Mock** (ejemplo) |
| **Simulador** | Simulacion de escenarios con Monte Carlo | **Mock** (ejemplo) |
| **Diario** | Registro de descubrimientos | **Mock** (ejemplo) |
| **Narrativa** | Analisis de desplazamiento narrativo | **Mock** (ejemplo) |
| **Arquitectura** | Diagrama de la arquitectura del sistema | **Mock** (ejemplo) |

### 8.2 Estados de datos

Los paneles marcados como **Reales** consumen datos de la API. Si no hay datos, muestran un estado vacio claramente identificado (por ejemplo: "No hay hipotesis registradas").

Los paneles marcados como **Mock** muestran datos de ejemplo para ilustrar la funcionalidad. No representan datos reales del sistema.

### 8.3 WebSocket en el Dashboard

El Dashboard se conecta automaticamente a `ws://localhost:8000/ws`. Los eventos que llegan se muestran en:
- El indicador de conexion (esquina inferior derecha)
- El feed de actividad en "Vision General"
- Las actualizaciones en tiempo real de los paneles

---

## 9. WebSocket

### 9.1 Conexion

```javascript
const ws = new WebSocket('ws://localhost:8000/ws');
```

### 9.2 Tipos de eventos

| Evento | Descripcion |
|--------|-------------|
| `conexion` | Confirmacion de conexion |
| `heartbeat` | Latido cada 30 segundos |
| `hipotesis_nueva` | Nueva hipotesis creada |
| `validacion_completada` | Validacion de hipotesis finalizada |
| `mercado_nuevo` | Nuevo mercado de prediccion |
| `trade` | Trade realizado |
| `mercado_resuelto` | Mercado resuelto |
| `cycle_triggered` | Ciclo disparado |
| `backup_created` | Backup creado |
| `backup_restored` | Backup restaurado |

### 9.3 Suscripcion

```json
{"accion": "subscribe"}
```

### 9.4 Ping/Pong

```json
{"accion": "ping"}
```

Respuesta: `{"tipo": "pong", "timestamp": "2026-11-11T12:00:00Z", "datos": {"conexiones_activas": 1}}`

---

## 10. Estructura de Directorios

```
VEO/
|-- api/                    # Servidor FastAPI
|   |-- api_server.py       # Endpoints principales
|   |-- __init__.py
|-- cli/                    # Interfaz de linea de comandos
|   |-- hermes_cli.py       # Comandos Typer
|   |-- __init__.py
|-- core/                   # Nucleo del sistema
|   |-- veo_core.py         # Motor principal
|   |-- persistence.py      # Persistencia SQLite
|   |-- db.py               # Capa de base de datos
|   |-- config.py           # Configuracion central
|   |-- __init__.py
|-- multiagent/             # Sistema multiagente
|   |-- hermes_commander.py # Comandador principal
|   |-- __init__.py
|-- analysis/               # Modulos de analisis
|   |-- causal_engine.py         # Motor causal
|   |-- causal_graph_adapter.py  # Adaptador de grafo causal
|   |-- hypothesis_engine.py     # Motor de hipotesis
|   |-- knowledge_graph.py       # Grafo de conocimiento
|   |-- planetary_configs.py     # Configuraciones planetarias
|   |-- planetary_diagnosis_engine.py  # Motor de diagnostico planetario
|   |-- scenario_simulator.py    # Simulador Monte Carlo
|   |-- scientific_agent.py      # Agentes cientifico y esceptico
|   |-- __init__.py
|-- operations/             # Operaciones
|   |-- backup_manager.py
|   |-- metrics_engine.py
|   |-- logger.py
|   |-- health_monitor.py    # Monitoreo de salud (archivo existe, imports rotos)
|   |-- audit_log.py         # Registro de auditoria (archivo existe, fallback mock)
|   |-- trust_layer.py       # Puntuacion de confianza (archivo existe, imports rotos)
|   |-- __init__.py
|-- tests/                  # Tests pytest
|   |-- test_api_integration.py
|   |-- test_cli_subprocess.py
|   |-- test_websocket.py
|   |-- ...
|-- dashboard/              # Dashboard React
|   |-- src/                # Codigo fuente
|   |   |-- App.jsx
|   |   |-- DashboardOverview.jsx
|   |   |-- HypothesisPanel.jsx
|   |   |-- SystemHealthPanel.jsx
|   |   |-- ...
|   |-- build/              # Build compilado (generado por npm run build)
|   |-- package.json
|   |-- vite.config.js
|-- docs/                   # Documentacion
|   |-- ACERCA.md           # Acerca de (es)
|   |-- ABOUT.md            # About (en)
|   |-- MANUAL_USUARIO.md   # Manual de usuario (es)
|   |-- USER_MANUAL.md      # User manual (en)
|   |-- INSTALLATION.md     # Instalacion (en)
|   |-- CONFIGURATION.md    # Configuracion (en)
|   |-- HERMES.md           # Documentacion tecnica
|   |-- ARCHITECTURE.md     # Arquitectura
|   |-- GOVERNANCE.md       # Gobernanza
|   |-- CHANGELOG.md        # Registro de cambios
|-- requirements.txt        # Dependencias Python
|-- install.sh              # Script de instalacion (Linux)
|-- install.bat             # Script de instalacion (Windows)
|-- validate.bat            # Script de validacion (Windows)
|-- veo.bat                 # Wrapper de ejecucion (Windows)
|-- README.md               # README principal (en)
|-- LEEME.md                # README principal (es)
|-- CHANGELOG.md            # Registro de cambios
```

---

## 11. Configuracion

### 11.1 Variables de entorno

| Variable | Descripcion | Por defecto | Ubicacion en codigo |
|----------|-------------|-------------|---------------------|
| `SOIS_DB_PATH` | Ruta de la base de datos SQLite (capa de inicializacion `core/db.py`) | `sois.db` | `core/db.py:104` |
| `VEO_V2_LOG_NIVEL` | Nivel de log (DEBUG, INFO, WARN, ERROR) | `INFO` | `operations/logger.py:374` |
| `VEO_ENV` | Entorno de ejecucion (dev, prod) | `dev` | `multiagent/hermes_commander.py:2849` |

**Nota:** Las variables `VEO_MIN_CONFIDENCE` y `VEO_AMBIENTE` aparecen en `tests/test_core.py` pero NO son leidas por el codigo de produccion. `SOIS_API_PORT` aparece en `validate_windows.py` pero solo para validacion interna; el servidor API usa el puerto que se pase a uvicorn (8000 por defecto).

### 11.2 Archivo de configuracion

VEO utiliza `veo_config.json` para configuraciones persistentes. Se crea automaticamente si no existe.

### 11.3 Persistencia

Las hipotesis se almacenan en SQLite. **Nota importante:** El codigo contiene multiples rutas de base de datos:
- `core/db.py` usa `sois.db` por defecto (configurable via `SOIS_DB_PATH`)
- `core/persistence.py` usa `veo_data.db` (fijo)
- `core/veo_core.py` usa `data/veo_core.db`

En la practica, HermesCommander (el motor principal) guarda las hipotesis en `veo_data.db` en la raiz del proyecto, ya que utiliza `core/persistence.py`.

### 11.4 Campo `modo` en metricas

El campo `modo` indica el origen de los datos de metricas:

| Valor | Significado |
|-------|-------------|
| `real` | psutil esta disponible y las metricas son reales |
| `simulacion` | psutil no esta disponible; se usan valores de fallback (0.0) |
| `simulacion_demostracion` | Modo mock/demostracion con valores predefinidos |

---

## 12. Solucion de Problemas

### 12.1 Error: `ModuleNotFoundError: No module named 'veo_v2'`

**Causa:** El entorno virtual no esta activado, o se esta ejecutando desde un directorio incorrecto.

**Solucion:**
```bash
cd /ruta/al/proyecto/VEO
source venv/bin/activate  # Linux
venv\Scripts\activate      # Windows
```

### 12.2 Error: `port already in use`

**Causa:** Otro proceso usa el puerto 8000.

**Solucion:**
```bash
lsof -ti:8000 | xargs kill -9  # Linux
# O usar otro puerto:
python -m uvicorn api.api_server:app --port 8080
```

### 12.3 El Dashboard no carga

**Causa:** El build no se ha generado.

**Solucion:**
```bash
cd dashboard
npm install
npm run build
```

### 12.4 Error 500 en `/api/v2/system/health` o `/api/v2/system/status`

**Causa:** El modelo Pydantic `SystemHealthResponse` espera el campo `"status"` pero `HermesCommander` devuelve `"overall"` en sus checks de componentes. El adaptador normaliza este campo, pero si hay otro problema de formato, el endpoint recurre a un mock con `modo: "simulacion_demostracion"`.

**Solucion:**
- Verifica que el servidor esta corriendo: `python cli/hermes_cli.py health`
- Si el error persiste, reinicia el servidor y espera 5 segundos antes de consultar `/api/v2/system/health`
- El endpoint tiene fallback automatico; recarga la pagina despues de unos segundos

### 12.5 Tests fallan

**Causa:** Dependencias incompletas o entorno contaminado.

**Solucion:**
```bash
rm -rf venv
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m pytest tests/ -q
```

### 12.6 WebSocket no conecta

**Causa:** El servidor no esta corriendo o un firewall bloquea el puerto.

**Solucion:** Verifica que uvicorn esta activo y que el puerto 8000 esta abierto.

### 12.7 `click` incompatible con `typer`

**Causa:** Version de click >= 8.2.0 con typer < 0.16.0.

**Solucion:** El `requirements.txt` ya fija `click<8.2.0`. Si instalaste manualmente, ejecuta:
```bash
pip install "click<8.2.0"
```

---

## 13. FAQ

### P: Puedo usar VEO sin Node.js?
**R:** Si. Node.js solo se necesita para compilar el Dashboard. El servidor API y la CLI funcionan sin Node.js. Sin Node.js, no tendras Dashboard visual, pero si acceso a la API y CLI.

### P: Los datos se pierden al reiniciar?
**R:** No. Las hipotesis y mercados se guardan en SQLite (`veo_data.db` por defecto, via `core/persistence.py`). Solo los datos en memoria (metricas en tiempo real) se reinician.

### P: Puedo ejecutar VEO en Docker?
**R:** No hay Dockerfile oficial, pero puedes crear uno facilmente basado en `requirements.txt`.

### P: El Dashboard muestra "No hay datos". Es un error?
**R:** No. Significa que no hay hipotesis, mercados u otros datos en el sistema. Crea algunos mediante la API o CLI.

### P: Que significa el campo `modo` en las metricas?
**R:** Indica el origen de los datos: `"real"` (psutil disponible), `"simulacion"` (psutil no disponible, valores 0.0), o `"simulacion_demostracion"` (modo mock con valores predefinidos).

### P: Puedo desactivar el WebSocket?
**R:** No hay flag para desactivarlo, pero puedes simplemente no conectarte a el. El servidor seguira funcionando.

### P: Que pasa si psutil no esta instalado?
**R:** Las metricas del sistema devolveran valores `0.0` con `modo: "simulacion"`. El sistema sigue funcionando.

### P: Como se que componentes usan datos reales y cuales mock?
**R:** Consulta la tabla de [Estado del Proyecto](#2-estado-del-proyecto) en este manual. Los paneles del Dashboard tambien indican su origen de datos.

---

## 13. Limitaciones conocidas

Esta seccion documenta problemas tecnicos conocidos en el codigo fuente que afectan el funcionamiento real del sistema. Se proporcionan para que el usuario comprenda que funcionalidades estan realmente operativas y cuales presentan deficiencias.

### 13.1 WebSocket

- **Broadcast roto:** `WebSocketManager` usa una unica `asyncio.Queue` compartida. Cuando hay multiples clientes conectados, cada evento solo llega al primer cliente que llame `get_nowait()`; el resto nunca lo recibe.

### 13.2 Integracion API ↔ HermesCommander

- **Mercados:** Los endpoints de mercados (`/api/v1/mercados`) y el adapter (`HermesCommanderAdapter`) llaman a metodos que no existen en `HermesCommander` (`listar_mercados`, `get_mercado`, `crear_mercado`, `trade_mercado`, `resolver_mercado`). Devuelven respuestas vacias o errores.
- **Escenarios:** El metodo `crear_escenario` del adapter retorna `None`, causando `TypeError` al acceder a `e['id']`.
- **Simulacion:** `simular_escenario` pasa `sid` en vez de `hyp_id` a `HermesCommander.simulate_scenario`.
- **Backup:** `create_backup` llama a metodo inexistente (`backup_create` en vez de `backup_now`).
- **Auditoria:** El endpoint `/api/v2/system/audit` es mock (devuelve datos de ejemplo).

### 13.3 CLI

- **Llamadas dobles:** En varios comandos (`market`, `journal`, `graph`, `narrative`, `alert`) se llama `get_commander().get_commander()`, que lanza `AttributeError` porque el adaptador no tiene ese metodo.
- **Mapeo incorrecto:** El adaptador mapea nombres que no coinciden con los de `HermesCommander` (`get_system_metrics` → `get_metrics()`, `create_backup` → `backup_now()`, etc.).
- **Shell REPL:** Solo soporta 4 comandos a pesar de documentarse como REPL completo.

### 13.4 Arquitectura

- **`models.py`:** Creado en v2.0.5 con enums y dataclasses basicos (`Hipotesis`, `Prediccion`, `Escenario`, `NodoGrafo`, etc.) alineados con el esquema SQL de `core/db.py`. La estructura puede necesitar ampliacion para cubrir todos los modelos del sistema.
- **Duplicacion de modulos:** `TrustLayer`, `HealthMonitor` y `AuditLog` estan definidos tanto en `core/veo_core.py` como en `operations/`. `VEOCore` usa las versiones internas; los de `operations/` son codigo muerto en produccion.
- **Imports con fallback:** `operations/audit_log.py`, `operations/trust_layer.py` y `operations/health_monitor.py` usan `try/except ImportError` con fallback a logging estandar cuando `veo_v2` no esta disponible como paquete. `multiagent/__init__.py` aun importa desde `veo_v2` sin fallback.
- **Modulos no conectados:** `prediction_market.py`, `memory/discovery_journal.py` y `analysis/knowledge_graph.py` existen como archivos completos pero nunca son importados por el flujo de produccion.

### 13.5 Instalacion y dependencias

- **`validate.bat`:** ~~Usa `python` del sistema en vez de `venv\Scripts\python`.~~ **CORREGIDO en v2.0.5.** Ahora invoca `venv\Scripts\python validate_windows.py`.
- **`install.bat`:** ~~No ejecuta tests al finalizar.~~ **CORREGIDO en v2.0.5.** Ahora ejecuta `venv\Scripts\python -m pytest tests/ -q --tb=short` como paso 6/7.
- **`install.sh`:** ~~Tiene una linea duplicada en la verificacion de paquetes.~~ **CORREGIDO en v2.0.5.** La verificacion ya no tiene duplicados.
- **`models.py`:** Creado en v2.0.5 con enums y dataclasses basicos alineados con `core/db.py`. La estructura puede necesitar ampliacion para cubrir todos los modelos del sistema.
- **Dependencias:** `psutil` y `sentence_transformers` fueron anadidos a `requirements.txt` en v2.0.5. No hay dependencias faltantes conocidas en este momento.

### 13.6 Versiones internas

- `core/veo_core.py` (linea ~2078) devolvia `"version": "2.0.3"` en `get_status()` — **CORREGIDO a `2.0.5` en esta version**.
- Tests automatizados: **292 de 293 pasan** (1 fallo en test de integracion de persistencia entre reinicios, que requiere backend completo).

---

## 14. Advertencia Final

VEO es una plataforma de inteligencia situacional con capacidades de razonamiento estructurado. Su uso debe estar alineado con principios eticos de transparencia y responsabilidad. El autor no se hace responsable de los usos inadecuados que terceros hagan de esta herramienta.

Este es un proyecto personal, sin patrocinio corporativo ni financiacion externa. La calidad del codigo refleja esfuerzo individual, no recursos de un equipo grande.

Si encuentras un error, no asumas que esta roto por diseno. Comunicamelo y lo corregire.

Algunos componentes (Dashboard, grafo causal, narrativa, auditoria) utilizan datos de ejemplo (mock) para ilustrar funcionalidades. No deben interpretarse como datos reales ni como representaciones fidedignas de situaciones actuales.
