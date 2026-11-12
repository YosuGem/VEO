# VEO
**VEO v2.0.5** 

> **AVISO IMPORTANTE:** Este proyecto esta en desarrollo activo y es funcionalmente INCOMPLETO. No todas las funciones descritas en la documentacion estan implementadas o conectadas. Algunos componentes existen como infraestructura preparada pero no estan integrados en el flujo de ejecucion principal. Consulta `docs/ABOUT.md` para conocer el estado real de cada modulo.

---

## Espanol

VEO es una plataforma de inteligencia situacional disenada para observar, analizar y responder a eventos emergentes observables en tiempo real.

### Que Hace VEO

- **Motor de hipotesis** con validacion dual (agentes cientifico + esceptico)
- **Mercados de prediccion** con cierre automatico basado en evidencia
- **Analisis de grafos causales** para detectar relaciones entre eventos
- **Simulacion de escenarios** con Monte Carlo
- **Deteccion de desplazamiento narrativo** mediante analisis de tendencias
- **Diario de descubrimiento** interactivo
- **Validacion de arquitectura** multicapa
- **Diagnostico planetario** sobre 100 familias de configuracion

Todo expuesto mediante una **API REST con FastAPI**, un **Dashboard React con WebSocket** y una **CLI con Typer**.

### Estado del Proyecto

| Componente | Estado |
|------------|--------|
| API REST (FastAPI) | Funcional |
| CLI (Typer) | Funcional |
| WebSocket | Funcional |
| Dashboard React | Funcional (4 paneles consumen la API, 6 estáticos/mock) |
| Persistencia SQLite | Funcional |
| Validacion dual | Funcional |
| Mercados de prediccion | Funcional |
| Simulador Monte Carlo | Funcional |
| Diario de descubrimiento | Mock (datos de ejemplo) |
| Grafo causal | Mock (datos de ejemplo) |
| Analisis narrativo | Mock (datos de ejemplo) |
| Auditoria del sistema | Mock (fallback transparente) |
| Ciclos automaticos | Mock (datos de ejemplo) |
| Diagnostico planetario | Funcional |
| Backup / Restore | Funcional |

**Definiciones de estado:**
- **Funcional** — Implementado, probado y operativo.
- **Mock** — Funciona con datos de ejemplo/fallback para demostracion. No son datos reales.

### Requisitos del Sistema

- **SO:** Linux (principal) o Windows 11
- **Python:** 3.12 (recomendado), 3.11+ compatible
- **Node.js:** 20.20.2+ (solo para compilar el Dashboard)
- **RAM:** 4 GB minimo, 8 GB recomendado
- **Disco:** 500 MB

### Inicio Rapido

```bash
git clone https://github.com/YosuGem/VEO.git
cd VEO
./install.sh          # Linux
# install.bat         # Windows
source venv/bin/activate

# Iniciar el servidor API
python -m uvicorn api.api_server:app --host 0.0.0.0 --port 8000

# O usar la CLI
python cli/hermes_cli.py serve --port 8000

# En otra terminal
python cli/hermes_cli.py version
python cli/hermes_cli.py health
python cli/hermes_cli.py hypothesis create "Hipotesis de prueba"
```

Abre el Dashboard en `http://localhost:8000/dashboard/`

### Compilar el Dashboard (una vez)

```bash
cd dashboard
npm install
npm run build
```

### Ejecutar Tests

```bash
python -m pytest tests/ -q
```

### Documentacion

| Documento | Idioma | Descripcion |
|-----------|--------|-------------|
| `docs/ABOUT.md` | Ingles | Vision general del proyecto, filosofia, historia |
| `docs/ACERCA.md` | Espanol | Mirror de ABOUT.md |
| `docs/USER_MANUAL.md` | Ingles | Manual de usuario completo |
| `docs/MANUAL_USUARIO.md` | Espanol | Mirror de USER_MANUAL.md |
| `docs/INSTALLATION.md` | Ingles | Guia de instalacion |
| `docs/CONFIGURATION.md` | Ingles | Referencia de configuracion |
| `docs/HERMES.md` | Ingles | Documentacion tecnica |
| `docs/ARCHITECTURE.md` | Ingles | Arquitectura del sistema |
| `docs/GOVERNANCE.md` | Ingles | Gobernanza y etica |
| `CHANGELOG.md` | Bilingue | Historial de versiones |

### Nota Personal del Autor

Este proyecto es uno de los que con mas ilusion y esmero he desarrollado. Mi objetivo ha sido crear un sistema realmente funcional, no un prototipo decorativo. Cada linea de codigo tiene un proposito concreto. Todos los componentes principales funcionan de verdad, y se han sometido a pruebas reales tanto en Linux como en Windows 11.

No quiero confundir a nadie. Si ves que algo no funciona como se describe en la documentacion, no asumas que esta roto por diseno: asume que necesita que me lo comuniques para corregirlo. Los errores no desaparecen por arte de magia; solo desaparecen cuando alguien los detecta, los documenta y los corrige.

### Advertencia Final

VEO es una plataforma de inteligencia situacional con capacidades de razonamiento estructurado. Su uso debe estar alineado con principios eticos de transparencia y responsabilidad. El autor no se hace responsable de los usos inadecuados que terceros hagan de esta herramienta.

Este es un proyecto personal, sin patrocinio corporativo ni financiacion externa. La calidad del codigo refleja esfuerzo individual, no recursos de un equipo grande.

Algunos componentes utilizan datos de ejemplo (mock) para ilustrar funcionalidades. No deben interpretarse como datos reales ni como representaciones fidedignas de situaciones actuales.

---

## English

VEO is a situational intelligence platform designed to observe, analyze, and respond to observable emerging events in real time.

### What VEO Does

- **Hypothesis engine** with dual validation (scientific + skeptical agents)
- **Prediction markets** with automatic closure based on evidence
- **Causal graph analysis** to detect relationships between events
- **Monte Carlo scenario simulation**
- **Narrative drift detection** through trend analysis
- **Interactive discovery journal**
- **Multi-layer architecture validation**
- **Planetary diagnostic** across 100 configuration families

All exposed through a **FastAPI REST API**, a **React Dashboard with WebSocket**, and a **Typer CLI**.

### Project Status

| Component | Status |
|-----------|--------|
| REST API (FastAPI) | Functional |
| CLI (Typer) | Functional |
| WebSocket | Functional |
| Dashboard React | Functional (4 panels consume the API, 6 static/mock) |
| SQLite persistence | Functional |
| Dual-agent validation | Functional |
| Prediction markets | Functional |
| Monte Carlo simulator | Functional |
| Discovery journal | Mock (example data) |
| Causal graph | Mock (example data) |
| Narrative analysis | Mock (example data) |
| System audit | Mock (transparent fallback) |
| Automatic cycles | Mock (example data) |
| Planetary diagnostic | Functional |
| Backup / Restore | Functional |

**Status definitions:**
- **Functional** — Implemented, tested, and operational.
- **Mock** — Works with example/fallback data for demonstration. Not real data.

### System Requirements

- **OS:** Linux (primary) or Windows 11
- **Python:** 3.12 (recommended), 3.11+ compatible
- **Node.js:** 20.20.2+ (only for building the Dashboard)
- **RAM:** 4 GB minimum, 8 GB recommended
- **Disk:** 500 MB

### Quick Start

```bash
git clone https://github.com/YosuGem/VEO.git
cd VEO
./install.sh          # Linux
# install.bat         # Windows
source venv/bin/activate

# Start the API server
python -m uvicorn api.api_server:app --host 0.0.0.0 --port 8000

# Or use the CLI
python cli/hermes_cli.py serve --port 8000

# In another terminal
python cli/hermes_cli.py version
python cli/hermes_cli.py health
python cli/hermes_cli.py hypothesis create "Test hypothesis"
```

Open the Dashboard at `http://localhost:8000/dashboard/`

### Build the Dashboard (one-time)

```bash
cd dashboard
npm install
npm run build
```

### Run Tests

```bash
python -m pytest tests/ -q
```

### Documentation

| Document | Language | Description |
|----------|----------|-------------|
| `docs/ABOUT.md` | English | Project overview, philosophy, history |
| `docs/ACERCA.md` | Spanish | Mirror of ABOUT.md |
| `docs/USER_MANUAL.md` | English | Complete user manual |
| `docs/MANUAL_USUARIO.md` | Spanish | Mirror of USER_MANUAL.md |
| `docs/INSTALLATION.md` | English | Installation guide |
| `docs/CONFIGURATION.md` | English | Configuration reference |
| `docs/HERMES.md` | English | Technical documentation |
| `docs/ARCHITECTURE.md` | English | System architecture |
| `docs/GOVERNANCE.md` | English | Governance and ethics |
| `CHANGELOG.md` | Bilingual | Version history |

### Author's Personal Note

This project is one of those I have developed with the most enthusiasm and care. My goal has been to create a truly functional system, not a decorative prototype. Every line of code has a concrete purpose. All main components actually work and have been subjected to real tests on both Linux and Windows 11.

I do not want to confuse anyone. If you see that something does not work as described in the documentation, do not assume it is broken by design: assume it needs to be reported to me so I can fix it. Errors do not disappear by magic; they only disappear when someone detects them, documents them, and corrects them.

### Final Warning

VEO is a situational intelligence platform with structured reasoning capabilities. Its use must be aligned with ethical principles of transparency and responsibility. The author is not responsible for inappropriate uses by third parties.

This is a personal project, without corporate sponsorship or external funding. Code quality reflects individual effort, not resources of a large team.

Some components use example data (mock) to illustrate functionality. They should not be interpreted as real data or as faithful representations of current situations.
