# VEO v2 - Sistema Operativo para Intuicion Social

> **ADVERTENCIA:** Este documento contiene comandos que pueden estar desactualizados.  
> Para instrucciones actualizadas y verificadas, consulta primero el `README.md` en la raiz del proyecto.

> "No predice el futuro. Observa que esta cambiando."

## Que es VEO v2

**VEO** (Vigilancia de Emergencias Observables) es un sistema operativo de inteligencia artificial cooperativa que detecta cambios emergentes en narrativas de internet mediante analisis continuo de senales debiles, relaciones semanticas y conocimiento distribuido.

**VEO v2** es una reescritura completa que introduce:

- **Arquitectura multiagente** con `veo_core` como cerebro central
- **4 ciclos independientes**: Monitoreo, Analisis, Prediccion y Ejecutivo
- **Hermes Commander** como interfaz unificada (CLI + API + WebSocket)
- **Capa de operaciones** completa: logging, salud, auditoria, confianza, backups, metricas
- **7 leyes de gobernanza** que garantizan rigor cientifico y trazabilidad
- **NEI auto-aprendido**: el sistema ajusta sus pesos semanalmente

## Objetivos

1. **Detectar** cambios de narrativa antes de que sean noticia
2. **Validar** hipotesis con rigor popperiano (refutacion, no confirmacion)
3. **Cuantificar** la incertidumbre en cada prediccion
4. **Trazar** cada decision desde la senal hasta la alerta
5. **Aprender** de sus aciertos y errores ajustando pesos automaticamente

## Arquitectura General

```
                    +------------------+
                    |   HERMES CLI/API |  <-- Interfaz unificada
                    +--------+---------+
                             |
              +--------------+--------------+
              |                             |
     +--------v---------+         +--------v---------+
     |   veo_core.py    |<------->|   Event Bus      |
     |   (4 ciclos)     |         |   (pub/sub)      |
     +--------+---------+         +--------+---------+
              |                             |
    +---------+----------+----------+-------+
    |                    |          |
+---v------+   +--------v--+   +---v---------+
| Monitoreo|   | Analisis  |   |  Ejecutivo  |
| (sensores|   | (hipotesis|   |  (alertas,  |
|  de datos)|   |  NEI, ML) |   |  reportes)  |
+---+------+   +-----+-----+   +---+---------+
    |                |              |
    |   +------------v-----+        |
    |   |   Prediccion     |        |
    +-->| (escenarios,     |<-------+
        |  Monte Carlo)    |
        +--------+---------+
                 |
        +--------v---------+
        |  Capa Operativa  |
        |  (logs, health,  |
        |   audit, trust,  |
        |   backup, metr.) |
        +------------------+
```

## Instalacion Rapida

### Requisitos

- **Python 3.10+**
- **Windows 10/11** (nativo)
- **2 GB RAM** minimo
- **500 MB** espacio en disco

### Instalacion (Windows)

```batch
:: 1. Extraer el ZIP y entrar al directorio
cd veo

:: 2. Ejecutar instalador
install.bat

:: 3. Verificar instalacion
python -m pytest tests/ -v
```

### Primer Inicio

```batch
:: Iniciar VEO v2 (modo demo)
python core/veo_core.py

:: O via Hermes CLI
python cli/hermes_cli.py --mock status
```

## Comandos Principales (via CLI)

> **Nota:** Los comandos a continuacion se ejecutan como `python cli/hermes_cli.py [comando]`.
> En Windows: `python cli\hermes_cli.py [comando]`.
> Usa `--mock` para modo simulado sin base de datos.

| Comando | Descripcion | Ejemplo real |
|---------|-------------|-------------|
| `status` | Estado del sistema | `python cli/hermes_cli.py --mock status` |
| `health` | Estado de salud | `python cli/hermes_cli.py --mock health` |
| `hypothesis list` | Listar hipotesis | `python cli/hermes_cli.py --mock hypothesis list` |
| `hypothesis create` | Crear hipotesis | `python cli/hermes_cli.py --mock hypothesis create "Texto"` |
| `validate` | Validar hipotesis | `python cli/hermes_cli.py --mock validate H-001` |
| `market list` | Listar mercados | `python cli/hermes_cli.py --mock market list` |
| `config` | Ver configuracion | `python cli/hermes_cli.py --mock config` |

> **Obsoleto:** los comandos `hermes start`, `hermes stop` y `hermes analisis run` no estan disponibles en esta version. Usa la API REST o el modo mock para operaciones interactivas.

## Estructura del Proyecto

```
veo_v2/
|-- core/                      # Nucleo central
|   |-- veo_core.py            # Motor principal (VEOCore)
|   |-- db.py                  # Inicializacion y esquema SQLite
|   |-- persistence.py         # Capa de persistencia
|   |-- config.py              # Configuracion central
|   |-- __init__.py
|
|-- multiagent/                # Orquestacion multiagente
|   |-- hermes_commander.py    # Interfaz CLI/API
|   |-- __init__.py
|
|-- analysis/                  # Capa de analisis
|   |-- scientific_agent.py    # Agente cientifico (Popper)
|   |-- hypothesis_engine.py   # Motor de hipotesis
|   |-- causal_engine.py       # Inferencia causal (Granger)
|   |-- scenario_simulator.py  # Simulador Monte Carlo
|   |-- knowledge_graph.py     # Grafo de conocimiento
|   |-- planetary_diagnosis_engine.py  # Diagnostico planetario
|   |-- planetary_configs.py   # Configuraciones planetarias
|   |-- __init__.py
|
|-- operations/                # Capa operativa
|   |-- logger.py              # Sistema de logging
|   |-- health_monitor.py      # Monitoreo de salud
|   |-- audit_log.py           # Registro de auditoria
|   |-- trust_layer.py         # Capa de confianza
|   |-- backup_manager.py      # Gestor de backups
|   |-- metrics_engine.py      # Motor de metricas
|   |-- __init__.py
|
|-- api/                       # Servidor API REST
|   |-- api_server.py          # FastAPI con 36 endpoints
|   |-- __init__.py
|
|-- cli/                       # Interfaz de linea de comandos
|   |-- hermes_cli.py          # CLI Typer (36 comandos)
|   |-- __init__.py
|
|-- tests/                     # Suite de tests
|
|-- tests/                     # Suite de tests
|   |-- conftest.py            # Fixtures compartidas
|   |-- test_core.py           # Tests del nucleo
|   |-- test_analysis.py       # Tests de analisis
|   |-- test_operations.py     # Tests operativos
|   |-- test_integration.py    # Tests end-to-end
|
|-- docs/                      # Documentacion
|   |-- README.md              # Este archivo
|   |-- ARCHITECTURE.md        # Arquitectura completa
|   |-- INSTALLATION.md        # Guia de instalacion
|   |-- CONFIGURATION.md       # Configuracion
|   |-- GOVERNANCE.md          # 7 leyes de gobernanza
|   |-- HERMES.md              # Comandos Hermes
|   |-- CHANGELOG.md           # Historial de cambios
```

## Documentacion Detallada

| Documento | Contenido |
|-----------|-----------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Diagramas, flujo de datos, componentes |
| [INSTALLATION.md](INSTALLATION.md) | Instalacion paso a paso, troubleshooting |
| [CONFIGURATION.md](CONFIGURATION.md) | Variables de entorno, pesos NEI, umbrales |
| [GOVERNANCE.md](GOVERNANCE.md) | Las 7 leyes, contrato de evolucion |
| [HERMES.md](HERMES.md) | Comandos CLI, API REST, WebSocket |
| [CHANGELOG.md](CHANGELOG.md) | V1 → V2, roadmap |

## Gobernanza: Las 7 Leyes

VEO v2 opera bajo 7 leyes inmutables que garantizan rigor cientifico:

1. **EVIDENCIA ANTES QUE OPINION** - Solo datos observables
2. **NUNCA EXISTE UNA UNICA EXPLICACION** - Siempre multiples hipotesis
3. **LA INCERTIDUMBRE ES OBLIGATORIA** - Toda prediccion incluye intervalo
4. **LOS SESGOS DEBEN SER EXPLICITOS** - Sesgos detectados en cada output
5. **LA COMPLEJIDAD DEBE PENALIZARSE** - Modelos mas simples preferidos
6. **LA TRAZABILIDAD ES OBLIGATORIA** - De la senal a la alerta
7. **NINGUN MOTOR ES SAGRADO** - Todo puede ser cuestionado

Ver [GOVERNANCE.md](GOVERNANCE.md) para el texto completo.

## Tecnologias

- **Python 3.10+** - Lenguaje principal
- **SQLite** (aiosqlite) - Base de datos asincrona
- **NetworkX** - Grafo de conocimiento en memoria
- **NumPy/SciPy** - Computacion cientifica
- **Pydantic** - Validacion de configuracion
- **pytest** - Framework de testing

## Licencia

Apache License 2.0 - Ver archivo LICENSE

## Contacto

- **Issues**: https://github.com/YosuGem/VEO/issues
- **Discusiones**: https://github.com/YosuGem/VEO/discussions
