# Arquitectura de VEO v2

> Documentacion completa de la arquitectura tecnica del Sistema Operativo para Intuicion Social v2.

## Tabla de Contenidos

1. [Vision General](#vision-general)
2. [Diagrama de Componentes](#diagrama-de-componentes)
3. [veo_core.py - Cerebro Central](#veo_corepy)
4. [hermes_commander.py - Interfaz Unificada](#hermes_commanderpy)
5. [Modulos de Analysis](#modulos-de-analysis)
6. [Capa de Operaciones](#capa-de-operaciones)
7. [API + CLI + Dashboard](#api--cli--dashboard)
8. [Flujo de Datos Completo](#flujo-de-datos-completo)
9. [Diagrama ASCII de la Arquitectura](#diagrama-ascii)

---

## Vision General

VEO v2 sigue una arquitectura de **pipeline multiagente** con estas caracteristicas clave:

- **Desacoplamiento**: Cada componente se comunica via Event Bus, no llamadas directas
- **Idempotencia**: Cada ciclo puede ejecutarse multiples veces sin efectos secundarios
- **Trazabilidad**: Cada decision se registra en la cadena de auditoria
- **Resiliencia**: Fallo de un modulo no detiene el sistema
- **Escalabilidad horizontal**: Modulos pueden replicarse

## Diagrama de Componentes

```
+------------------------------------------------------------------+
|                         HERMES COMMANDER                          |
|   CLI  |  API REST  |  WebSocket  |  Dashboard Web               |
+----------------------------+--------------------------------------+
                             |
                             v
+------------------------------------------------------------------+
|                         EVENT BUS                                 |
|   Pub/Sub asincrono con persistencia de eventos                   |
+----------------------------+--------------------------------------+
                             |
              +--------------+--------------+
              |                             |
     +--------v---------+         +--------v---------+
     |   veo_core       |<------->|   scheduler      |
     |   (orquestador)  |         |   (4 ciclos)     |
     +--------+---------+         +------------------+
              |
     +--------v-------------------------------------------+
     |              CICLOS DE VEO CORE                     |
     |  +----------+  +----------+  +----------+          |
     |  | Ciclo 1  |  | Ciclo 2  |  | Ciclo 3  |          |
     |  |Monitoreo |  | Analisis |  |Prediccion|          |
     |  |(sensores)|  |(hipotesis|  |(escenar. |          |
     |  +-----+----+  +-----+----+  +-----+----+          |
     |        |            |            |                  |
     |        v            v            v                  |
     |  +----------+  +----------+  +----------+          |
     |  | Ciclo 4  |  |          |  |          |          |
     |  |Ejecutivo |  |          |  |          |          |
     |  |(alertas) |  |          |  |          |          |
     |  +-----+----+  +----------+  +----------+          |
     +--------|-------------------------------------------+
              |
     +--------v---------+---------+---------+---------+
     |   CAPA ANALISIS  |         |         |         |
     | +--------------+ | +-----+ | +-----+ | +-----+ |
     | |scientific_   | | |hypo-| | |causal| | |scen-| |
     | |agent         | | |thesis| | |_eng|| | |ario | |
     | |  (Popper)    | | |_eng | | |      | | |_sim | |
     | +--------------+ | +-----+ | +-----+ | +-----+ |
     | +--------------+ |         |         |         |
     | |knowledge_    | |         |         |         |
     | |graph         | |         |         |         |
     | |  (NetworkX)  | |         |         |         |
     | +--------------+ |         |         |         |
     +------------------+---------+---------+---------+
              |
     +--------v---------+---------+---------+---------+
     |  CAPA OPERACIONES|         |         |         |
     | +--------------+ | +-----+ | +-----+ | +-----+ |
     | |logger        | | |health| | |audit | | |trust| |
     | |  (SQLite)    | | |_mon | | |_log | | |_layer| |
     | +--------------+ | +-----+ | +-----+ | +-----+ |
     | +--------------+ | +-----+ |         |         |
     | |backup_       | | |metric| |         |         |
     | |manager       | | |_eng | |         |         |
     | |  (filesystem)| | |      | |         |         |
     | +--------------+ | +-----+ |         |         |
     +------------------+---------+---------+---------+
              |
     +--------v---------+
     |  CAPA MEMORIA    |
     |  (embeddings,    |
     |   cache, estado) |
     +------------------+
```

---

## veo_core.py

### Cerebro Central - 4 Ciclos

`veo_core.py` es el orquestador principal. Mantiene 4 ciclos independientes que operan a diferentes frecuencias:

#### Ciclo 1: Monitoreo (frecuencia: alta)

```
+-------------+    +-------------+    +-------------+
|  Sensores   |--->|  Agregacion |--->|  Cola de    |
|  (RSS, APIs,|    |  + Filtros  |    |  senales    |
|   Redes soc)|    |             |    |  nuevas     |
+-------------+    +-------------+    +------+------+
                                             |
                                             v
                                        +-------------+
                                        |  EventBus   |
                                        |  senal.nueva|
                                        +-------------+
```

**Responsabilidades**:
- Recolectar datos de fuentes externas
- Filtrar ruido y duplicados
- Emitir eventos `senal.nueva`

**Intervalo**: configurable (default: 60 seg)

#### Ciclo 2: Analisis (frecuencia: media)

```
+-------------+    +-------------+    +-------------+
|  Senales    |--->|  Motor de   |--->|  Agente     |
|  nuevas     |    |  Hipotesis  |    |  Cientifico |
+-------------+    |  (NEI)      |    |  (validacion)|
                   +-------------+    +------+------+
                           |                 |
                           v                 v
                   +-------------+    +-------------+
                   |  Grafo de   |    |  Validacion |
                   |Conocimiento |    |  persistida |
                   +-------------+    +-------------+
```

**Responsabilidades**:
- Generar hipotesis a partir de clusters semanticos
- Calcular NEI (Narrative Emergence Index)
- Validar con agente cientifico (metodo Popper)
- Actualizar grafo de conocimiento
- Emitir eventos `hipotesis.nueva`, `hipotesis.validada`

**Intervalo**: configurable (default: 300 seg)

#### Ciclo 3: Prediccion (frecuencia: baja)

```
+-------------+    +-------------+    +-------------+
|  Hipotesis  |--->|  Simulador  |--->|  Mercado de |
|  validadas  |    |  Monte Carlo|    |  Prediccion |
+-------------+    |  + Escenar. |    |  (consenso) |
                   +-------------+    +------+------+
                           |                 |
                           v                 v
                   +-------------+    +-------------+
                   |  Resultados |    |  Probabilid.|
                   |  persistidos|    |  ajustada   |
                   +-------------+    +-------------+
```

**Responsabilidades**:
- Crear escenarios a partir de hipotesis validadas
- Ejecutar simulaciones Monte Carlo
- Consultar mercado de predicciones interno
- Generar predicciones con intervalos de confianza
- Emitir eventos `prediccion.nueva`

**Intervalo**: configurable (default: 1800 seg)

#### Ciclo 4: Ejecutivo (frecuencia: muy baja)

```
+-------------+    +-------------+    +-------------+
|  Hallazgos  |--->|  Priorizador|--->|  Generador  |
|  acumulados |    |  (impacto x |    |  de Alertas |
+-------------+    |  urgencia)  |    |  + Reportes |
                   +-------------+    +------+------+
                           |                 |
                           v                 v
                   +-------------+    +-------------+
                   |  Ranking de |    |  Alertas    |
                   |  prioridades|    |  emitidas   |
                   +-------------+    +-------------+
```

**Responsabilidades**:
- Revisar todos los hallazgos del periodo
- Calcular prioridad (impacto x urgencia x confianza)
- Generar alertas si se superan umbrales
- Crear reportes ejecutivos
- Emitir eventos `alerta.emitida`, `reporte.generado`

**Intervalo**: configurable (default: 3600 seg)

---

## hermes_commander.py

### Interfaz Unificada

Hermes es la unica interfaz para interactuar con VEO. Expone tres protocolos:

```
+-------------------------------------------------+
|                 HERMES COMMANDER                 |
+--------+----------+-----------+-----------------+
|  CLI   | API REST | WebSocket | Dashboard Web   |
+--------+----------+-----------+-----------------+
|Commands| Endpoints| Real-time | Visualizacion   |
|        |          | events    | interactiva     |
+--------+----------+-----------+-----------------+
```

**Diseno**: Hermes traduce cualquier entrada (CLI, HTTP, WS) a eventos del Event Bus, y viceversa. No accede directamente a los modulos internos.

---

## Modulos de Analysis

### scientific_agent.py

**Metodo**: Refutacion popperiana. El agente INTENTA REFUTAR la hipotesis, no confirmarla.

```
Hipotesis --> Extraer supuestos --> Buscar evidencia contraria
    |                                       |
    v                                       v
Detectar falacias <--------------- Evaluar representatividad
    |                                       |
    +-----------> Integrar veredicto <------+
                    |
                    v
            +--------------+
            | CONFIRMADA   | (provisional)
            | REFUTADA     |
            | INCONCLUSA   |
            +--------------+
```

### hypothesis_engine.py

**NEI (Narrative Emergence Index)**: Indice compuesto de 6 metricas:

| Metrica | Descripcion | Peso default |
|---------|-------------|--------------|
| FR | Frecuencia relativa | 0.20 |
| GR | Growth rate | 0.25 |
| DV | Diversidad de fuentes | 0.20 |
| NV | Novedad | 0.20 |
| EM | Carga emocional | 0.10 |
| ST | Sentimiento trend | 0.05 |

Formula: `NEI = w1*FR + w2*GR + w3*DV + w4*NV + w5*EM + w6*ST`

Los pesos se ajustan semanalmente via descenso de gradiente.

### causal_engine.py

**Metodos de inferencia causal**:
- **Granger Causality**: Test F para series temporales
- **Transfer Entropy**: Flujo de informacion (TE)
- **Correlacion Parcial**: Controlando confundidores
- **Do-calculus simplificado**: Simulacion de intervenciones

### scenario_simulator.py

**Simulacion Monte Carlo**:
1. Definir variables con distribuciones
2. Muestrear n_runs veces
3. Propagar efectos por grafo causal
4. Calcular estadisticas (media, p5, p95)
5. Analisis de sensibilidad (Spearman)

### knowledge_graph.py

**Grafo hibrido**: NetworkX en memoria + SQLite persistente.

Operaciones soportadas:
- CRUD de nodos y relaciones
- Busqueda de caminos indirectos
- Deteccion de comunidades (Louvain)
- Centralidad (betweenness)
- Expansion desde texto (NER simple)

---

## Capa de Operaciones

| Modulo | Funcion | Almacenamiento | Estado |
|--------|---------|----------------|--------|
| logger.py | Logging con rotacion | SQLite + filesystem | Implementado |
| health_monitor.py | Check de componentes | En memoria | **Archivo existe; imports rotos** (`veo_v2` inexistente) |
| audit_log.py | Cadena de auditoria inmutable | En memoria (mock) | Fallback |
| trust_layer.py | Scores de confianza por componente | En memoria | **Archivo existe; imports rotos** (`veo_v2` inexistente) |
| backup_manager.py | Backups incrementales | Filesystem | Implementado |
| metrics_engine.py | Series temporales de metricas | En memoria | Implementado |

---

## API + CLI + Dashboard

### API REST (FastAPI)

| Endpoint | Metodo | Descripcion |
|----------|--------|-------------|
| `/health` | GET | Health check basico |
| `/api/v1/hipotesis` | GET/POST | Listar/crear hipotesis |
| `/api/v1/hipotesis/{id}` | GET | Obtener hipotesis |
| `/api/v1/hipotesis/{id}/validar` | POST | Validar hipotesis |
| `/api/v1/mercados` | GET/POST | Listar/crear mercados de prediccion |
| `/api/v1/mercados/{id}` | GET | Obtener mercado |
| `/api/v1/mercados/{id}/trade` | POST | Ejecutar trade |
| `/api/v1/mercados/{id}/resolver` | POST | Resolver mercado |
| `/api/v1/escenarios` | POST | Crear escenario de simulacion |
| `/api/v1/escenarios/{id}/simular` | POST | Ejecutar simulacion Monte Carlo |
| `/api/v2/system/health` | GET | Salud del sistema (detallada) |
| `/api/v2/system/status` | GET | Estado del sistema |
| `/api/v2/system/metrics` | GET | Metricas del sistema |
| `/api/v2/system/audit` | GET | Auditoria (mock) |
| `/api/v2/cycles/status` | GET | Estado de ciclos (mock) |
| `/api/v2/cycles/trigger` | POST | Disparar ciclo |
| `/api/v2/operations/backup` | POST | Crear backup |
| `/api/v2/operations/restore` | POST | Restaurar backup |
| `/ws` | WS | WebSocket para eventos en tiempo real |

### WebSocket

Canal en tiempo real para:
- Eventos del sistema (ciclos, alertas)
- Progreso de simulaciones
- Stream de logs

### Dashboard Web

Interfaz visual con:
- Grafo de conocimiento interactivo
- Series temporales de NEI
- Panel de alertas
- Configuracion visual

---

## Flujo de Datos Completo

```
[Fuente externa]
       |
       v
[Sensor/RSS/API]  ----event: senal.raw---->  [Logger]
       |
       v
[Filtro + Deduplicacion]
       |
       v
[Event Bus: senal.nueva]  ---->  [Ciclo Monitoreo]
       |
       v
[Cola de senales]
       |
       v
[Ciclo Analisis]  ---->  [Motor Hipotesis]
       |                       |
       |                       v
       |               [Agente Cientifico]
       |                       |
       |                       v
       |               [Validacion + NEI]
       |                       |
       |                       v
       |       [Event: hipotesis.validada]
       |                       |
       v                       v
[Grafo de Conoc.]  <----  [Persistencia]
       |
       v
[Ciclo Prediccion]  ---->  [Simulador MC]
       |                       |
       |                       v
       |               [Escenarios + Prob]
       |                       |
       |                       v
       |       [Event: prediccion.nueva]
       |                       |
       v                       v
[Mercado Predicc.]  <----  [Persistencia]
       |
       v
[Ciclo Ejecutivo]  ---->  [Priorizador]
       |                       |
       |                       v
       |               [Alertas + Reportes]
       |                       |
       v                       v
[Notificaciones]  <----  [Event: alerta.emitida]
       |
       v
[Fin: Todo trazado en auditoria]
```

---

## Diagrama ASCII de la Arquitectura

```
================================================================================
                           VEO v2 - ARQUITECTURA COMPLETA
================================================================================

    USUARIO
       |
  +----v-----------------------------------+
  |         HERMES COMMANDER                |
  |  +--------+  +--------+  +---------+   |
  |  |  CLI   |  |API REST|  |WebSocket|   |
  |  +--------+  +--------+  +---------+   |
  +--------------------+-------------------+
                       |
              +--------v---------+
              |    EVENT BUS      |<-------------------+
              |   (pub/sub)       |                    |
              +--------+---------+                     |
                       |                               |
         +-------------+-------------+                 |
         |                           |                 |
  +------v------+          +---------v--------+        |
  | veo_core    |          |  CAPA MEMORIA    |        |
  |             |          |  - embeddings    |        |
  | +---------+ |          |  - cache         |        |
  | |Ciclo 1  | |          |  - estado        |        |
  | |Monitoreo| |          +---------+--------+        |
  | +---------+ |                    |                 |
  | |Ciclo 2  | |                    |                 |
  | |Analisis | |          +---------v--------+        |
  | +---------+ |          |  CAPA ANALISIS   |        |
  | |Ciclo 3  | |          |                  |        |
  | |Predicc. | |          | +--------------+ |        |
  | +---------+ |          | |Scientific    | |        |
  | |Ciclo 4  | |          | |Agent (Popper)| |        |
  | |Ejecutivo| |          | +--------------+ |        |
  | +---------+ |          | |Hypothesis    | |        |
  +------+------+          | |Engine (NEI)  | |        |
         |                 | +--------------+ |        |
         |                 | |Causal Engine | |        |
         |                 | |(Granger)     | |        |
         |                 | +--------------+ |        |
         |                 | |Scenario Sim  | |        |
         |                 | |(Monte Carlo) | |        |
         |                 | +--------------+ |        |
         |                 | |Knowledge     | |        |
         |                 | |Graph (NetX)  | |        |
         |                 | +--------------+ |        |
         |                 +---------+--------+        |
         |                           |                 |
         |                 +---------v--------+        |
         |                 | CAPA OPERACIONES |        |
         |                 |                  |        |
         |                 | +--------------+ |        |
         |                 | |Logger        | |        |
         |                 | |Health Monitor| |        |
         |                 | |Audit Log     | |        |
         |                 | |Trust Layer   | |        |
         |                 | |Backup Mgr    | |        |
         |                 | |Metrics Engine| |        |
         |                 | +--------------+ |        |
         |                 +---------+--------+        |
         |                           |                 |
         +---------------------------+-----------------+
                                     |
                              +------v------+
                              |   SQLite    |
                              |  (persist.) |
                              +-------------+

================================================================================
                           FLUJO DE EVENTOS
================================================================================

senal.raw          --> senal.nueva --> senal.procesada
hipotesis.generada --> hipotesis.validada --> hipotesis.confirmada/refutada
escenario.creado   --> escenario.simulado --> prediccion.nueva
hallazgo.detectado --> alerta.emitida --> notificacion.enviada
backup.iniciado    --> backup.completado --> backup.verificado

================================================================================
                           ESCALABILIDAD
================================================================================

Nodo 1: veo_core + Ciclo Monitoreo (sensores)
Nodo 2: Ciclo Analisis + Grafo de Conocimiento
Nodo 3: Ciclo Prediccion + Simulador MC
Nodo 4: Ciclo Ejecutivo + Notificaciones
Nodo 5: Hermes API + Dashboard (usuarios)

Todos conectados via Event Bus (Redis/RabbitMQ en produccion)

================================================================================
```
