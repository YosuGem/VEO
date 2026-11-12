# Changelog - VEO

> **Nota:** Este documento es un archivo historico que cubre hasta v2.0.0. El changelog completo y actualizado de las versiones recientes (v2.0.4K en adelante) se encuentra en `CHANGELOG.md` en la raiz del proyecto.

## Tabla de Contenidos

1. [VEO v2.0.0](#veo-v200---sistema-multiagente)
2. [VEO v1.0](#veo-v10---radar-inicial)
3. [Roadmap v2.x](#roadmap-v2x)

---

## VEO v2.0.0 - Sistema Multiagente

**Fecha**: Enero 2026
**Codename**: "Athene"
**Estado**: Estable

### Arquitectura Nueva

```
v2.0.0 representa una reescritura completa desde cero.
No hay compatibilidad con datos v1.x (migracion manual requerida).
```

### Componentes Nuevos

#### Nucleo Central
- **`veo_core.py`** - Cerebro central con 4 ciclos independientes:
  - Ciclo 1: Monitoreo (sensores de datos)
  - Ciclo 2: Analisis (motor de hipotesis + NEI)
  - Ciclo 3: Prediccion (simulador Monte Carlo)
  - Ciclo 4: Ejecutivo (priorizacion + alertas)
- **`hermes_commander.py`** - Interfaz unificada (CLI + API + WebSocket)
- **`config.py`** - Configuracion centralizada con Pydantic

**Nota:** Los modulos `event_bus.py` y `scheduler.py` fueron planificados pero nunca implementados como archivos separados.

#### Capa de Analisis
- **`scientific_agent.py`** - Agente de validacion popperiana
  - Deteccion de falacias logicas
  - Deteccion de sesgos (confirmacion, disponibilidad, anclaje)
  - Hipotesis alternativas obligatorias
  - Trust score por componente
- **`hypothesis_engine.py`** - Motor de hipotesis
  - Generacion desde clusters semanticos
  - Calculo NEI (6 metricas ponderadas)
  - Aprendizaje automatico de pesos (descenso de gradiente)
  - Deteccion de hipotesis en cascada
  - Archivado automatico de hipotesis caducas
- **`causal_engine.py`** - Inferencia causal
  - Granger causality (test F)
  - Transfer entropy
  - Correlacion parcial (controlando confundidores)
  - Simulacion de intervenciones
- **`scenario_simulator.py`** - Simulador Monte Carlo
  - Simulacion de escenarios con variables aleatorias
  - 4 distribuciones: uniforme, normal, triangular, log-normal
  - Estadisticas: media, mediana, p5, p95, desv. est.
  - Analisis de sensibilidad (Spearman)
  - Comparacion de escenarios
  - Calculo de peor caso
- **`knowledge_graph.py`** - Grafo de conocimiento hibrido
  - NetworkX en memoria + SQLite persistente
  - CRUD de nodos y relaciones
  - Busqueda de caminos indirectos (BFS)
  - Deteccion de comunidades
  - Centralidad (betweenness)
  - Expansion desde texto (NER simple con hashtags/menciones)
  - Similitud coseno entre embeddings

#### Capa de Operaciones
- **`logger.py`** - Sistema de logging
  - SQLite + filesystem
  - Rotacion por tamano y por fecha
  - Formato JSON en archivos
  - Niveles: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **`health_monitor.py`** - Monitoreo de salud
  - Check por componente con score
  - Score global promedio
  - Umbrales: ok (>0.8), warning (>0.5), critical (<0.5)
  - Alertas automaticas si score < umbral
- **`audit_log.py`** - Registro de auditoria inmutable
  - Cadena de hashes (hash_previo referencia entrada anterior)
  - Query por actor, accion, recurso
  - Reconstruccion de secuencia de acciones
  - Tamper-evident (modificacion detectable)
- **`trust_layer.py`** - Capa de confianza
  - Score por componente [0, 1]
  - Penalizacion por errores
  - Recompensa por aciertos
  - Ranking de componentes
  - Desactivacion automatica si score < umbral
- **`backup_manager.py`** - Gestor de backups
  - Backups completos de SQLite
  - Verificacion de integridad (SHA-256)
  - Listado y eliminacion
  - Restauracion
- **`metrics_engine.py`** - Motor de metricas
  - Registro de metricas con tags JSON
  - Series temporales
  - Filtrado por rango de fechas
  - Dashboard agregado (promedio, min, max, count)

#### API + Interfaces
- **API REST** (FastAPI) - 30+ endpoints
- **WebSocket** - Eventos en tiempo real
- **Dashboard Web** - Visualizacion interactiva
- **CLI** - Comandos via hermes_commander

### Gobernanza: Las 7 Leyes

1. **EVIDENCIA ANTES QUE OPINION** - Solo datos observables
2. **NUNCA EXISTE UNA UNICA EXPLICACION** - Siempre >= 3 hipotesis
3. **LA INCERTIDUMBRE ES OBLIGATORIA** - Intervalo p5-p95 obligatorio
4. **LOS SESGOS DEBEN SER EXPLICITOS** - Sesgos en cada output
5. **LA COMPLEJIDAD DEBE PENALIZARSE** - Ockham via NEI
6. **LA TRAZABILIDAD ES OBLIGATORIA** - De senal a alerta
7. **NINGUN MOTOR ES SAGRADO** - Todo puede ser cuestionado

### Tecnologias

- Python 3.10+
- SQLite (aiosqlite para async)
- NetworkX (grafo en memoria)
- NumPy/SciPy (computacion cientifica)
- Pydantic (configuracion)
- FastAPI (API REST)
- pytest (testing)

### Base de Datos

15 tablas:
- `hipotesis`, `predicciones`, `escenarios`
- `descubrimientos_semanales`, `cambios_narrativa`
- `grafo_nodos`, `grafo_relaciones`
- `validaciones`, `historial_nei`
- `logs_operacion`, `metricas`
- `auditoria`, `trust_scores`
- `backups`, `health_status`, `eventos_sistema`

### Tests

Suite completa:
- **test_core.py** - Config, DB, EventBus, Scheduler, VEOCore
- **test_analysis.py** - Agente Cientifico, Motor Hipotesis, Motor Causal, Simulador, Grafo
- **test_operations.py** - Logger, Health, Audit, Trust, Backup, Metrics
- **test_integration.py** - Ciclos end-to-end, Pipeline completo, Hermes

### Cambios Breaking desde v1.x

- Esquema de base de datos incompatible (recrear)
- No hay migracion automatica de datos v1 → v2
- Nuevo formato de configuracion (Pydantic vs dict)
- API REST reemplaza API anterior
- CLI hermes reemplaza comandos anteriores

---

## VEO v1.0 - Radar Inicial

**Fecha**: Julio 2025
**Codename**: "Argos"
**Estado**: Deprecado (reemplazado por v2.0.0)

### Que Tenia

```
v1.0 era un sistema monolitico con las siguientes capacidades:

- Monitoreo basico de fuentes RSS y APIs
- Deteccion simple de clusters semanticos
- Alertas por umbral fijo
- Base de datos SQLite (esquema simple)
- Logging basico a archivo
- Configuracion via diccionario Python
- Sin agente cientifico
- Sin inferencia causal
- Sin simulacion Monte Carlo
- Sin grafo de conocimiento
- Sin mercado de predicciones
- Sin capa de operaciones
- Sin gobernanza formal
```

### Limitaciones que Motivaron v2

| Limitacion v1 | Solucion en v2 |
|---------------|----------------|
| Monolitico | Arquitectura multiagente |
| Sin validacion cientifica | Agente Popper + NEI |
| Umbral fijo | Pesos auto-aprendidos |
| Sin incertidumbre | Intervalos p5-p95 obligatorios |
| Sin trazabilidad | Cadena de auditoria inmutable |
| Sin deteccion de sesgos | Sesgos explicitos en cada output |
| Sin inferencia causal | Granger + Transfer Entropy |
| Sin simulacion | Monte Carlo con sensibilidad |
| Sin grafo de conocimiento | Grafo hibrido NetworkX + SQLite |
| Sin operaciones formales | 6 modulos de operaciones |
| Sin interfaz unificada | Hermes (CLI + API + WS) |
| Sin gobernanza | 7 leyes inmutables |

---

## Roadmap v2.x

### v2.1.0 - "Extension" (Q1 2026)

- [ ] Nuevo sensor: Discord
- [ ] Nuevo sensor: Telegram
- [ ] Mejora del agente cientifico: test estadisticos adicionales
- [ ] Pesos NEI: metrica de polarizacion politica
- [ ] Dashboard web: graficos de series temporales
- [ ] API: paginacion mejorada

### v2.2.0 - "Retroalimentacion" (Q2 2026)

- [ ] Ciclo de retroalimentacion: aprender de aciertos/errores
- [ ] Reputacion de fuentes: algunas fuentes son mas confiables
- [ ] Deteccion de desinformacion: flag de contenido potencialmente falso
- [ ] Integracion con bases de datos de fact-checking
- [ ] Mejora del grafo: embeddings semanticos

### v2.3.0 - "Mercado" (Q3 2026)

- [ ] Mercado de predicciones v2: mecanismo Brier scoring
- [ ] Participacion externa: usuarios pueden apostar
- [ ] Liquidacion automatica de predicciones
- [ ] Ranking de predictores
- [ ] API para integracion con sistemas externos

### v2.4.0 - "Visibilidad" (Q4 2026)

- [ ] Dashboard web v2: completamente interactivo
- [ ] Grafo visual interactivo (D3.js)
- [ ] Reportes automaticos (PDF/HTML)
- [ ] Integracion con Slack/Teams para alertas
- [ ] Mobile-friendly dashboard

### v2.5.0 - "Escalabilidad" (2027)

- [ ] Soporte para Redis como Event Bus
- [ ] Ejecucion distribuida de ciclos
- [ ] Sharding de base de datos por fuente
- [ ] Cache distribuida
- [ ] HA (High Availability)

### v3.0.0 - "Convergencia" (2027+)

> Solo si hay cambio incompatible en esquema de datos.

- [ ] Posible migracion a PostgreSQL
- [ ] Multi-idioma nativo
- [ ] Modelos de lenguaje propios fine-tuneados
- [ ] Integracion con sistemas de inteligencia institutional

---

## Notas de Versionado

VEO usa **Semantic Versioning**:

- `MAJOR`: Cambio incompatible en datos o API
- `MINOR`: Nueva funcionalidad, compatible hacia atras
- `PATCH`: Bug fix o mejora menor

Formato: `vMAJOR.MINOR.PATCH` (ej: `v2.0.0`)

## Convenciones de Commit

```
feat: nueva funcionalidad
fix: correccion de bug
docs: documentacion
refactor: refactorizacion de codigo
test: tests
chore: tareas de mantenimiento
perf: mejora de performance
```
