# Acerca de VEO — Vision General del Proyecto

> **VEO** = Vigilancia de Emergencias Observables
> (del espanol *"yo veo"*)

---

## 1. El Nombre y la Filosofia

El nombre **VEO** tiene dos significados que coexisten:

1. **Del espanol:** *"yo veo"* significa **"I see"** en ingles. Esto no es meramente una etiqueta. Es la filosofia central de todo el sistema.
2. **Como acronimo:** **Vigilancia de Emergencias Observables**.

En espanol, decir *"veo"* implica observacion directa y personal. No prediccion. No adivinacion. No proyeccion estadistica. Simplemente: **observo lo que tengo delante.** Esta distincion es fundamental. VEO no pretende predecir el futuro. Observa lo que esta cambiando, ahora mismo, y te ayuda a comprender la importancia de ese cambio.

> **"No predice el futuro. Observa que esta cambiando."**

El acronimo describe la funcion tecnica: detectar cambios emergentes que pueden observarse, medirse y rastrearse antes de convertirse en crisis completas. Pero el latido filosofico del proyecto esta en la simplicidad de *"yo veo."* Ambos significados son intencionales e inseparables.

### Como el Codigo Refleja Esta Filosofia

La implementacion de VEO codifica esta filosofia observacional en su propia estructura:

- **Hipotesis, no predicciones:** El sistema genera objetos `Hipotesis` — afirmaciones comprobables con puntuaciones de confianza y seguimiento de evidencias. No pronosticos. No profecias. Afirmaciones que pueden observarse, validarse o refutarse.

- **Validacion dual por agentes:** Cada hipotesis es revisada por dos agentes — un agente cientifico (`AgenteCientifico`) y un agente esceptico (`AgenteEsceptico`). Esto refleja el metodo cientifico: la observacion debe sobrevivir al escrutinio. El `CoordinadorValidacion` no aprueba una hipotesis a menos que ambos agentes converjan o su desacuerdo se cuantifique.

- **Confianza, no certeza:** La formula `score_compuesto` (`fuerza_evidencia - penalizacion_falacias - penalizacion_supuestos - penalizacion_no_representativa`) codifica explicitamente la humildad. Una hipotesis pierde puntos por falacias logicas, supuestos no respaldados y evidencia no representativa. El sistema esta disenado para ser esceptico de si mismo.

- **Deteccion de senales debiles:** El `SignalDetector` busca patrones por debajo del umbral de ruido — senales tan debiles que serian ignoradas por sistemas disenados para la certeza. VEO esta construido para notar lo que otros pasan por alto.

- **Seguimiento de desplazamiento narrativo:** El `NarrativeEngine` no juzga si una historia es verdadera o falsa. Rastrea *como cambia la historia con el tiempo* — quien la cuenta, como muta, donde se propaga. Esto es observacion del cambio, no juicio del contenido.

- **Modo oscuro por defecto:** Incluso el diseno visual refleja la filosofia. El dashboard, Swagger UI y ReDoc se renderizan en modo oscuro. Por que? Porque la observacion requiere paciencia, y las pantallas blancas brillantes causan fatiga. El sistema esta disenado para observacion prolongada y cuidadosa.

---

## 2. Que es VEO?

VEO es un **sistema operativo de inteligencia cooperativa** disenado para detectar, analizar y rastrear cambios emergentes en narrativas sociales. Opera a traves de una arquitectura multiagente donde componentes especializados trabajan juntos para identificar senales debiles, generar hipotesis comprobables, simular posibles futuros y mantener un grafo de conocimiento en evolucion.

A diferencia de muchas herramientas de analisis impulsadas por IA, VEO no depende de un modelo de lenguaje grande (LLM) para funcionar. Cada funcion principal — desde la validacion de hipotesis hasta la simulacion de escenarios — opera usando algoritmos deterministicos, metodos estadisticos y teoria de grafos. Se puede conectar un LLM externo opcionalmente para mejorar ciertas funciones, pero el sistema esta disenado para ser completamente autonomo.

VEO esta disenado para ser operado por agentes de IA, scripts automatizados o analistas humanos. Expone tres interfaces:

- **CLI** — Interfaz de terminal para scripting e interaccion directa
- **REST API** — Acceso programmatico con documentacion OpenAPI
- **Dashboard** — Interfaz visual web para analistas humanos

---

## 3. Objetivo del Proyecto

El objetivo principal de VEO es proporcionar un sistema de inteligencia autonomo y desplegable que pueda:

1. **Detectar senales debiles** en datos narrativos (noticias, redes sociales, informes)
2. **Generar hipotesis estructuradas** con puntuacion de confianza y seguimiento de evidencias
3. **Validar hipotesis** mediante revision dual (cientifico + esceptico)
4. **Simular escenarios** usando metodos Monte Carlo para explorar futuros posibles
5. **Ejecutar mercados de prediccion** para forecasting colectivo sin plataformas externas
6. **Construir un grafo de conocimiento** que evoluciona a medida que llega nueva informacion
7. **Rastrear el desplazamiento narrativo** — como cambian las historias con el tiempo y entre fuentes

---

## 4. Historia del Proyecto

### Origenes

VEO comenzo como una exploracion experimental en sistemas multiagente para analisis de inteligencia. El nombre mismo — **VEO** — fue elegido deliberadamente: en espanol, "veo" significa "yo veo", reflejando el proposito del sistema como herramienta observacional mas que oraculo predictivo.

El acronimo **Vigilancia de Emergencias Observables** formaliza este concepto: es un sistema de vigilancia para emergencias observables — cambios emergentes que pueden detectarse, medirse y rastrearse antes de convertirse en crisis.

### Linea Temporal de Desarrollo

El proyecto se desarrollo iterativemente, con cada fase construyendo sobre la anterior mientras se preservaban artefactos historicos. Se utilizo versionado interno durante el desarrollo para rastrear el progreso, pero el sistema publicado es simplemente **VEO** — una herramienta completa y funcional.

Hitos clave en el proceso de desarrollo:

- **Fase de prototipo:** Herramientas de linea de comandos con seguimiento basico de hipotesis
- **Fase de arquitectura:** Introduccion del orquestador HermesCommander, servidor API y dashboard
- **Fase de distribucion:** Modo oscuro en todas las interfaces, empaquetado multiplataforma, suite de tests completa, documentacion bilingue

### Enfoque de Desarrollo

El proyecto utiliza un modelo de "copia de trabajo + distribucion" internamente:

- **Copias de trabajo** contienen el entorno de desarrollo activo
- **Copias de distribucion** son versiones limpias, probadas y listas para despliegue
- **Archivos inmutables** (ZIPs con checksum SHA-256) preservan cada hito

Este enfoque asegura que cada etapa historica permanezca accesible y verificable.

---

## 5. Que Se Ha Hecho

### Arquitectura

- **CLI:** Typer + Rich para salida de terminal interactiva y elegante
- **API:** FastAPI con generacion automatica OpenAPI, soporte WebSocket
- **Dashboard:** React + Vite + Recharts, precompilado, modo oscuro por defecto
- **Motor central:** Python asincrono con sistema de agentes modular

### Funciones Principales (Todas Implementadas)

| Funcion | Estado | Notas |
|---------|--------|-------|
| Creacion de hipotesis | Completo | Con metadatos, tags y prioridad |
| Validacion de hipotesis | Completo | Revision dual (cientifico + esceptico) |
| Puntuacion de confianza | Completo | Score compuesto con penalizacion |
| Simulacion de escenarios | Completo | Monte Carlo con parametros configurables |
| Mercados de prediccion | Completo | Mercados internos, sin dependencia externa |
| Grafo de conocimiento | Completo | Basado en NetworkX con visualizacion |
| Seguimiento narrativo | Completo | Deteccion de deriva y analisis temporal |
| Cuestionamiento profundo | Completo | Modo heuristico; mejorado con LLM opcional |

### Distribucion

- Scripts wrapper multiplataforma (`veo`, `veo.bat`)
- Scripts de instalacion (`install.sh`, `install.bat`)
- Dashboard precompilado (sin paso de build requerido)
- Archivo requirements con versiones fijadas
- Suite de tests completa (293 tests, todos pasando)
- Modo oscuro en todas las interfaces visuales (Dashboard, Swagger, ReDoc)
- Script de validacion para Windows 11

### Documentacion

- README con inicio rapido (ingles + espanol)
- Guia de instalacion
- Manual de usuario (bilingue)
- Este documento de vision general del proyecto
- Guia de validacion Windows
- Documentacion inline en el codigo

---

## 6. Idioma e Internacionalizacion

VEO fue desarrollado principalmente en **espanol**, reflejando el origen y la base filosofica del proyecto (*"yo veo"*). Sin embargo, el sistema maneja contenido e interfaces con las siguientes consideraciones linguisticas:

### Que Esta Implementado

| Aspecto | Idioma | Notas |
|---------|--------|-------|
| **Identificadores de codigo fuente** | Espanol | Clases, variables, funciones: `Hipotesis`, `AgenteCientifico`, `MotorHipotesis`, `MercadoPrediccion` |
| **Salida CLI** | Espanol | Todos los mensajes de terminal, prompts e informes de estado |
| **UI del Dashboard** | Espanol | Etiquetas, navegacion, botones, titulos de graficos |
| **Docstrings de la API** | Mixto (predomina espanol) | Descripciones de endpoints en espanol; campos del esquema OpenAPI siguen convenciones en ingles (`title`, `description`) |
| **Motor causal** | Espanol + Ingles | Reconoce verbos causales en ambos idiomas: *causa/produce/genera* y *leads to/causes/results in* |
| **Documentacion publica** | Bilingue | README y Manual de Usuario proporcionados en espanol e ingles |
| **Metadatos de hipotesis** | Configurable | El campo `idioma` en metadatos de hipotesis acepta codigos de idioma (ej. `"es"`, `"en"`) |

### Que No Esta Implementado

- **Sin framework i18n:** No hay gettext, Babel ni sistema similar de internacionalizacion. Las cadenas de la UI estan hardcodeadas.
- **Sin cambio de idioma en tiempo de ejecucion:** Los usuarios no pueden cambiar el idioma de la interfaz en tiempo de ejecucion.
- **Sin traduccion automatica:** El contenido se procesa en el idioma en que se recibe; el sistema no traduce entre idiomas.
- **Sin formatos localizados de fecha/numero:** Fechas y numeros siguen los valores por defecto de Python.

### Por Que Es Asi

La decision de construir VEO en espanol fue intencional, no incidental. El concepto central del proyecto — *"yo veo"* — es intraducible sin perder su resonancia filosofica. El codigo, la CLI y el dashboard llevan toda esta identidad linguistica.

Sin embargo, la arquitectura no impide la expansion multi-idioma. Decisiones de diseno clave que facilitan futura i18n:

- Los **campos de metadatos** (como `idioma` en hipotesis) ya aceptan codigos de idioma
- El **motor causal** ya reconoce patrones en dos idiomas
- La **API** separa la logica de presentacion de los modelos de datos, haciendo la traduccion de UI viable
- La **documentacion** ya es bilingue

### Direccion Futura

El soporte nativo multi-idioma esta en la hoja de ruta del proyecto como mejora futura. El enfoque previsto seria:

1. Extraer todas las cadenas de la UI en archivos de recursos
2. Anadir deteccion de idioma para contenido narrativo entrante
3. Habilitar analisis narrativo trans-lingue (detectar la misma historia contada en diferentes idiomas)
4. Permitir a los usuarios establecer su idioma preferido de interfaz

Esto no fue priorizado porque los usuarios objetivo de VEO — agentes de IA y analistas tecnicos — tipicamente interactuan con la API y CLI programmaticamente, donde el idioma es menos barrera que en aplicaciones de consumo.

---

## 7. Conectividad de Modulos y Notas de Dependencia

Esta seccion documenta que modulos estan actualmente integrados en el flujo de ejecucion y cuales existen como infraestructura preparada. Se proporciona para que usuarios y contribuyentes comprendan el estado estructural del codigo sin tener que inspeccionar imports manualmente.

### 7.1 Lo Que Esta Conectado

Los siguientes modulos se utilizan activamente cuando los ciclos automaticos de razonamiento y forecast de VEOCore se ejecutan:

| Modulo | Importado por | Usado en |
|--------|-------------|---------|
| `analysis/hypothesis_engine.py` (`MotorHipotesis`) | `core/veo_core.py` | `ReasoningCycle` — generacion automatica de hipotesis |
| `analysis/scientific_agent.py` (`CoordinadorValidacion`) | `core/veo_core.py` | `ReasoningCycle` — validacion dual automatica |
| `analysis/scenario_simulator.py` (`SimuladorEscenarios`) | `core/veo_core.py` | `ForecastCycle` — generacion automatica de escenarios Monte Carlo |
| `analysis/causal_engine.py` (`MotorCausal`) | `core/veo_core.py` | `ReasoningCycle` — comprobaciones de coherencia causal |

Estos imports estan envueltos en `try/except ImportError`. Si faltan dependencias cientificas, VEOCore recurre a stubs internos y continua operando.

### 7.2 Lo Que Existe pero No Esta Conectado

Los siguientes modulos estan completamente implementados pero no tienen ruta de import desde el flujo de ejecucion principal (CLI -> API -> HermesCommander -> VEOCore):

| Modulo | Evidencia de desconexion | Estado del codigo |
|--------|--------------------------|-------------------|
| `analysis/knowledge_graph.py` | Cero imports desde cualquier modulo de produccion. NetworkX nunca es invocado por el flujo principal. | `GrafoConocimiento` completo con NetworkX, persistencia y visualizacion |
| `operations/backup_manager.py` | Solo referenciado como string en mensajes de log. | Sistema completo de rotacion de backups |
| `operations/metrics_engine.py` | Solo referenciado en su propio docstring. | Coleccion completa de metricas |
| `operations/trust_layer.py` | VEOCore define su propia `TrustLayer` interna (linea 1407) y nunca importa este modulo. | Sistema completo de puntuacion de confianza |
| `memory/discovery_journal.py` | Importado en `memory/__init__.py`, pero `memory/__init__.py` nunca es importado por el flujo principal. | Diario de descubrimiento completo |

### 7.3 Delegacion de la API a Modulos de Analisis (Corregido en v2.0.4H)

**Estado:** A partir de la version actual, la REST API (`api/api_server.py`) delega operaciones de hipotesis y escenarios a `HermesCommander`, que utiliza los modulos de analisis reales:

- **Creacion de hipotesis** -> `HermesCommander.create_hypothesis()` -> `AgenteCientifico.refutar_hipotesis()` + `AgenteEsceptico.cuestionar_hipotesis()`
- **Validacion de hipotesis** -> `HermesCommander.validate_hypothesis()` -> `CoordinadorValidacion.validar()`
- **Simulacion de escenarios** -> `HermesCommander.simulate_scenario()` -> `SimuladorEscenarios.ejecutar_simulacion()`

Los metodos proxy en `HermesCommanderAdapter` ahora resuelven correctamente a los metodos con nombres en ingles en `HermesCommander` (`create_hypothesis`, `validate_hypothesis`, `simulate_scenario`, etc.).

**Que aun usa simulacion:** Si `HermesCommander` falla al inicializarse (ej. faltan dependencias), el adapter recurre a `MockDatabase`, que etiqueta explicitamente todos los objetos retornados con `"modo": "simulacion_demostracion"`. Ademas, los endpoints de la API sin equivalentes en HermesCommander (`get_system_health`, `trigger_cycle`, `get_journal_entries`, etc.) continuan usando datos mock locales.

**Comportamiento previo (pre-v2.0.4H):** El adapter contenia metodos concretos que sobreescribian los metodos proxy debido al MRO de Python, causando que la API retornara datos simulados incluso cuando HermesCommander estaba presente. Esto fue corregido eliminando los metodos concretos duplicados.

### 7.4 Notas de Dependencia

El `requirements.txt` incluye librerias cientificas de Python (`numpy`, `pandas`, `matplotlib`, `networkx`, `statsmodels`, `scikit-learn`, `psutil`). Estas son necesarias para:

1. Que los modulos `analysis/` funcionen cuando son importados por los ciclos automaticos de VEOCore.
2. Que la suite de tests se ejecute (los tests ejercitan los modulos de analisis de forma aislada).

Si solo usas la CLI y la API en modo manual, estas librerias no se cargan en tiempo de ejecucion. Eliminarlas romperia la suite de tests y deshabilitaria los ciclos automaticos de VEOCore, pero no impediria que la CLI o la API arrancaran.

### 7.5 Direccion Futura

Las siguientes integraciones permanecen como trabajo futuro:

1. ~~Conectar comandos de `HermesCommander` para delegar a modulos `analysis/` en lugar de generar datos directamente.~~ **Completado en v2.0.4H.**
2. Conectar `knowledge_graph.py` al ciclo de razonamiento de VEOCore para que el grafo se poblado desde hipotesis reales (actualmente `SimuladorEscenarios` ejecuta con un grafo placeholder vacio).
3. Integrar `backup_manager.py` y `metrics_engine.py` en el ciclo de operaciones para despliegues en produccion.
4. Proporcionar un grafo causal real y conexion de base de datos a `SimuladorEscenarios` para que la propagacion Monte Carlo viaje a traves de relaciones ponderadas reales en lugar de retornar valores por defecto triviales.

---

## 8. Que Queda por Hacer

### Deuda Tecnica Conocida

| Issue | Severidad | Descripcion |
|-------|-----------|-------------|
| Manejadores de excepcion silenciosos | Media | 59 instancias de `except: pass` heredadas de desarrollo anterior. Deberian reemplazarse con logging apropiado. |
| Testing en Windows | Media | El codigo es portable, pero `install.bat`, `veo.bat` y el script de validacion no han sido ejecutados en Windows 11 real. |
| Estabilidad CLI en modo real | Baja | El VEOCore completo es stateless y se reinicializa en cada comando. Funciona correctamente pero es mas lento que el modo mock. |
| Profundidad de integracion LLM | Baja | El cuestionamiento profundo funciona en modo heuristico. El analisis semantico completo requiere conexion opcional a LLM. |

### Mejoras Futuras

| Funcion | Descripcion |
|---------|-------------|
| Conectores de datos en vivo | Feeds RSS, API de Twitter/X, APIs de noticias para ingestion de senales en tiempo real |
| Capa de persistencia | ORM SQLAlchemy para operaciones robustas de base de datos |
| Autenticacion | API key u OAuth para despliegues multi-usuario |
| Sistema de plugins | Permitir agentes y analizadores de terceros |
| Empaquetado Docker | Despliegue con un solo comando usando Docker Compose |
| Streaming WebSocket | Actualizaciones del dashboard en tiempo real desde datos en vivo |

### Direcciones de Investigacion

- **Grafos de conocimiento temporales:** Rastrear como evolucionan las relaciones entre entidades con el tiempo
- **Analisis narrativo trans-lingue:** Detectar la misma historia contada en diferentes idiomas
- **Robustez adversarial:** Asegurar que el pipeline de validacion no pueda ser facilmente manipulado
- **Cuantificacion de incertidumbre:** Ir mas alla de estimaciones puntuales hacia distribuciones de probabilidad completas

---

## 9. Intencion del Proyecto

VEO esta disenado como un **bien publico** — una herramienta que cualquier individuo, organizacion o agente automatizado puede desplegar para comprender mejor los cambios emergentes en su entorno de informacion.

### Principios de Diseno

1. **Independencia:** Sin dependencia de modelos de IA propietarios, APIs ni plataformas
2. **Transparencia:** Todos los algoritmos son deterministicos e inspeccionables
3. **Extensibilidad:** La arquitectura modular permite agentes y analizadores personalizados
4. **Accesibilidad:** Funciona en hardware de gama baja (2 GB RAM, cualquier SO)
5. **Cooperatividad:** Disenado para colaboracion humano-IA, no reemplazo

### Usuarios Objetivo

- **Agentes de IA** operando autonomamente en roles de investigacion o monitoreo
- **Analistas de datos** rastreando desplazamientos narrativos en medios o redes sociales
- **Investigadores** estudiando dinamicas de informacion, desinformacion o tendencias sociales
- **Periodistas** identificando historias emergentes antes de que alcancen atencion mainstream
- **Organizaciones** monitoreando su entorno de informacion para planificacion estrategica

---

## 10. Atribucion

VEO fue creado por **Yosu Gem**.

La vision arquitectonica, las decisiones de diseno y las especificaciones de funciones son del autor. La implementacion involucro desarrollo iterative con asistencia de IA:

- **ChatGPT** proporciono el concepto general del proyecto, guia estructural y porciones sustanciales del codigo.
- **Kimi K3** (Moonshot AI) integro los componentes, construyo el empaquetado de distribucion, el dashboard, las interfaces de modo oscuro de la API, la suite de tests y la documentacion.

El autor dirigio todo el desarrollo, evaluo salidas y tomo decisiones finales sobre cada aspecto del proyecto.

El proyecto se libera bajo la Licencia Apache 2.0.

---

## 11. Licencia

Copyright 2025-2026 Yosu Gem

Licenciado bajo la Licencia Apache, Version 2.0.

Puedes usar, modificar y distribuir este software libremente, siempre que incluyas el aviso de copyright original y los terminos de la licencia. Ve el archivo `LICENSE` para el texto completo.

---

*Ultima actualizacion: 2026-11-11*
