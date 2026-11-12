# About VEO — Project Overview

> **VEO** = Vigilancia de Emergencias Observables  
> (from Spanish *"yo veo"* — "I see")

---

## 1. The Name and the Philosophy

The name **VEO** has two meanings that coexist:

1. **From Spanish:** *"yo veo"* means **"I see"** in English. This is not merely a label. It is the core philosophy of the entire system.
2. **As an acronym:** **Vigilancia de Emergencias Observables** (Surveillance of Observable Emergencies).

In Spanish, saying *"veo"* implies direct, personal observation. Not prediction. Not divination. Not statistical projection. Simply: **I observe what is in front of me.** This distinction is fundamental. VEO does not claim to predict the future. It observes what is changing, right now, and helps you understand the significance of that change.

> **"No predice el futuro. Observa qué está cambiando."**  
> *("It does not predict the future. It observes what is changing.")*

The acronym describes the technical function: detecting emergent changes that can be observed, measured, and tracked before they become full crises. But the philosophical heartbeat of the project is in the simplicity of *"yo veo."* Both meanings are intentional and inseparable.

### How the Code Reflects This Philosophy

The implementation of VEO encodes this observational philosophy into its very structure:

- **Hypotheses, not predictions:** The system generates `Hipotesis` objects — testable statements with confidence scores and evidence tracking. Not forecasts. Not prophecies. Statements that can be observed, validated, or refuted.

- **Dual-agent validation:** Every hypothesis is reviewed by two agents — a scientific agent (`AgenteCientifico`) and a skeptical agent (`AgenteEsceptico`). This mirrors the scientific method: observation must survive scrutiny. The `CoordinadorValidacion` does not approve a hypothesis unless both agents converge or their disagreement is quantified.

- **Confidence, not certainty:** The `score_compuesto` formula (`fuerza_evidencia - penalizacion_falacias - penalizacion_supuestos - penalizacion_no_representativa`) explicitly encodes humility. A hypothesis loses points for logical fallacies, unsupported assumptions, and non-representative evidence. The system is designed to be skeptical of itself.

- **Weak signal detection:** The `SignalDetector` looks for patterns below the noise threshold — signals so faint they would be ignored by systems designed for certainty. VEO is built to notice what others overlook.

- **Narrative drift tracking:** The `NarrativeEngine` does not judge whether a story is true or false. It tracks *how the story changes over time* — who tells it, how it mutates, where it spreads. This is observation of change, not judgment of content.

- **Dark mode by default:** Even the visual design reflects the philosophy. The dashboard, Swagger UI, and ReDoc all render in dark mode. Why? Because observation requires patience, and bright white screens cause fatigue. The system is designed for extended, careful watching.

---

## 2. What is VEO?

VEO is a **cooperative intelligence operating system** designed to detect, analyze, and track emerging changes in social narratives. It operates through a multi-agent architecture where specialized components work together to identify weak signals, generate testable hypotheses, simulate possible futures, and maintain an evolving knowledge graph.

Unlike many AI-driven analysis tools, VEO does not depend on a large language model (LLM) to function. Every core feature — from hypothesis validation to scenario simulation — operates using deterministic algorithms, statistical methods, and graph theory. An external LLM can be connected optionally to enhance certain features, but the system is designed to be fully autonomous.

VEO is designed to be operated by AI agents, automated scripts, or human analysts. It exposes three interfaces:

- **CLI** — Terminal interface for scripting and direct interaction
- **REST API** — Programmatic access with OpenAPI documentation
- **Dashboard** — Web-based visual interface for human analysts

---

## 3. Project Objective

The primary goal of VEO is to provide a self-contained, deployable intelligence system that can:

1. **Detect weak signals** in narrative data (news, social media, reports)
2. **Generate structured hypotheses** with confidence scoring and evidence tracking
3. **Validate hypotheses** through dual-agent review (scientific + skeptical)
4. **Simulate scenarios** using Monte Carlo methods to explore possible futures
5. **Run prediction markets** for collective forecasting without external platforms
6. **Build a knowledge graph** that evolves as new information arrives
7. **Track narrative drift** — how stories change over time and across sources

---

## 4. Project History

### Origins

VEO began as an experimental exploration into multi-agent systems for intelligence analysis. The name itself — **VEO** — was chosen deliberately: in Spanish, "veo" means "I see," reflecting the system's purpose as an observational tool rather than a predictive oracle.

The acronym **Vigilancia de Emergencias Observables** formalizes this concept: it is a surveillance system for observable emergencies — emergent changes that can be detected, measured, and tracked before they become crises.

### Development Timeline

The project was developed iteratively, with each phase building upon the previous one while preserving historical artifacts. Internal versioning was used during development to track progress, but the published system is simply **VEO** — a complete, functional tool.

Key milestones in the development process:

- **Prototype phase:** Command-line tools with basic hypothesis tracking
- **Architecture phase:** Introduction of the HermesCommander orchestrator, API server, and dashboard
- **Distribution phase:** Dark mode on all interfaces, cross-platform packaging, comprehensive test suite, bilingual documentation

### Development Approach

The project uses a "working copy + distribution" model internally:

- **Working copies** contain the active development environment
- **Distribution copies** are clean, tested versions ready for deployment
- **Immutable archives** (ZIP files with SHA-256 checksums) preserve each milestone

This approach ensures that every historical stage remains accessible and verifiable.

---

## 5. What Has Been Done

### Architecture

- **CLI:** Typer + Rich for beautiful, interactive terminal output
- **API:** FastAPI with automatic OpenAPI generation, WebSocket support
- **Dashboard:** React + Vite + Recharts, pre-compiled, dark mode by default
- **Core engine:** Async Python with modular agent system

### Core Features (All Implemented)

| Feature | Status | Notes |
|---------|--------|-------|
| Hypothesis creation | Complete | With metadata, tags, and priority |
| Hypothesis validation | Complete | Dual-agent review (scientific + skeptical) |
| Confidence scoring | Complete | Composite score with penalization |
| Scenario simulation | Complete | Monte Carlo with configurable parameters |
| Prediction markets | Complete | Internal markets, no external dependency |
| Knowledge graph | Complete | NetworkX-based with visualization |
| Narrative tracking | Complete | Drift detection and timeline analysis |
| Deep questioning | Complete | Heuristic mode; enhanced with optional LLM |

### Distribution

- Cross-platform wrapper scripts (`veo`, `veo.bat`)
- Installation scripts (`install.sh`, `install.bat`)
- Pre-compiled dashboard (no build step required)
- Requirements file with pinned versions
- Comprehensive test suite (285 tests, all passing)
- Dark mode on all visual interfaces (Dashboard, Swagger, ReDoc)
- Validation script for Windows 11 (prepared, pending real-world execution)

### Documentation

- README with quick start (English + Spanish)
- Installation guide
- User manual (bilingual)
- This project overview document
- Windows validation guide
- Inline code documentation

---

## 6. Language and Internationalization

VEO was developed primarily in **Spanish**, reflecting the origin and philosophical grounding of the project (*"yo veo"*). However, the system handles content and interfaces with the following language considerations:

### What Is Implemented

| Aspect | Language | Notes |
|--------|----------|-------|
| **Source code identifiers** | Spanish | Classes, variables, functions: `Hipotesis`, `AgenteCientifico`, `MotorHipotesis`, `MercadoPrediccion` |
| **CLI output** | Spanish | All terminal messages, prompts, and status reports |
| **Dashboard UI** | Spanish | Labels, navigation, buttons, chart titles |
| **API docstrings** | Mixed (Spanish predom.) | Endpoint descriptions in Spanish; OpenAPI schema fields follow English conventions (`title`, `description`) |
| **Causal engine** | Spanish + English | Recognizes causal verbs in both languages: *causa/produce/genera* and *leads to/causes/results in* |
| **Public documentation** | Bilingual | README and User Manual provided in both Spanish and English |
| **Hypothesis metadata** | Configurable | The `idioma` field in hypothesis metadata accepts language codes (e.g., `"es"`, `"en"`) |

### What Is Not Implemented

- **No i18n framework:** There is no gettext, Babel, or similar internationalization system. The UI strings are hardcoded.
- **No runtime language switching:** Users cannot switch the interface language at runtime.
- **No automatic translation:** Content is processed in the language it is received; the system does not translate between languages.
- **No localized date/number formats:** Dates and numbers follow Python defaults.

### Why It Is This Way

The decision to build VEO in Spanish was intentional, not incidental. The project's core concept — *"yo veo"* — is untranslatable without losing its philosophical resonance. The code, the CLI, and the dashboard all carry this linguistic identity.

However, the architecture does not prevent multi-language expansion. Key design decisions that facilitate future i18n:

- **Metadata fields** (like `idioma` in hypotheses) already accept language codes
- **The causal engine** already recognizes patterns in two languages
- **The API** separates presentation logic from data models, making UI translation feasible
- **The documentation** is already bilingual

### Future Direction

Native multi-language support is listed in the project roadmap as a future enhancement. The intended approach would be:

1. Extract all UI strings into resource files
2. Add language detection for incoming narrative content
3. Enable cross-lingual narrative analysis (detecting the same story told in different languages)
4. Allow users to set their preferred interface language

This was not prioritized because VEO's target users — AI agents and technical analysts — typically interact with the API and CLI programmatically, where language is less of a barrier than in consumer applications.

---

## 7. Module Connectivity and Dependency Notes

This section documents which modules are currently integrated into the execution flow and which exist as prepared infrastructure. It is provided so that users and contributors understand the structural state of the codebase without having to inspect imports manually.

### 7.1 What Is Connected

The following modules are actively used when VEOCore's automatic reasoning and forecast cycles run:

| Module | Imported by | Used in |
|--------|-------------|---------|
| `analysis/hypothesis_engine.py` (`MotorHipotesis`) | `core/veo_core.py` | `ReasoningCycle` — automatic hypothesis generation |
| `analysis/scientific_agent.py` (`CoordinadorValidacion`) | `core/veo_core.py` | `ReasoningCycle` — automatic dual-agent validation |
| `analysis/scenario_simulator.py` (`SimuladorEscenarios`) | `core/veo_core.py` | `ForecastCycle` — automatic Monte Carlo scenario generation |
| `analysis/causal_engine.py` (`MotorCausal`) | `core/veo_core.py` | `ReasoningCycle` — causal coherence checks |

These imports are wrapped in `try/except ImportError`. If the scientific dependencies are missing, VEOCore falls back to internal stubs and continues operating.

### 7.2 What Exists but Is Not Connected

The following modules are fully implemented but have no import path from the main execution flow (CLI → API → HermesCommander → VEOCore):

| Module | Evidence of disconnection | Code status |
|--------|--------------------------|-------------|
| `analysis/knowledge_graph.py` | Zero imports from any production module. NetworkX is never invoked by the main flow. | Complete `GrafoConocimiento` with NetworkX, persistence, and visualization |
| `operations/backup_manager.py` | Only referenced as a string in log messages. | Complete backup rotation system |
| `operations/metrics_engine.py` | Only referenced in its own docstring. | Complete metrics collection |
| `operations/trust_layer.py` | VEOCore defines its own internal `TrustLayer` (line 1407) and never imports this module. | Complete trust scoring system |
| `memory/discovery_journal.py` | Imported in `memory/__init__.py`, but `memory/__init__.py` is never imported by the main flow. | Complete discovery journal |

### 7.3 API Delegation to Analysis Modules (Fixed in v2.0.4H)

**Status:** As of the current version, the REST API (`api/api_server.py`) delegates hypothesis and scenario operations to `HermesCommander`, which uses the real analysis modules:

- **Hypothesis creation** → `HermesCommander.create_hypothesis()` → `AgenteCientifico.refutar_hipotesis()` + `AgenteEsceptico.cuestionar_hipotesis()`
- **Hypothesis validation** → `HermesCommander.validate_hypothesis()` → `CoordinadorValidacion.validar()`
- **Scenario simulation** → `HermesCommander.simulate_scenario()` → `SimuladorEscenarios.ejecutar_simulacion()`

The proxy methods in `HermesCommanderAdapter` now correctly resolve to the English-named methods on `HermesCommander` (`create_hypothesis`, `validate_hypothesis`, `simulate_scenario`, etc.).

**What still uses simulation:** If `HermesCommander` fails to initialize (e.g., missing dependencies), the adapter falls back to `MockDatabase`, which explicitly tags all returned objects with `"modo": "simulacion_demostracion"`. Additionally, API endpoints without HermesCommander equivalents (`get_system_health`, `trigger_cycle`, `get_journal_entries`, etc.) continue to use local mock data.

**Previous behavior (pre-v2.0.4H):** The adapter contained concrete methods that overrode the proxy methods due to Python's MRO, causing the API to return simulated data even when HermesCommander was present. This was corrected by removing the duplicate concrete methods.

### 7.4 Dependency Notes

The `requirements.txt` includes scientific Python libraries (`numpy`, `pandas`, `matplotlib`, `networkx`, `statsmodels`, `scikit-learn`, `psutil`). These are necessary for:

1. The `analysis/` modules to function when imported by VEOCore's automatic cycles.
2. The test suite to run (the tests exercise the analysis modules in isolation).

If you only use the CLI and API in manual mode, these libraries are not loaded at runtime. Removing them would break the test suite and disable VEOCore's automatic cycles, but would not prevent the CLI or API from starting.

### 7.5 Future Direction

The following integrations remain as future work:

1. ~~Wire `HermesCommander` commands to delegate to `analysis/` modules instead of generating data directly.~~ **Completed in v2.0.4H.**
2. Connect `knowledge_graph.py` to VEOCore's reasoning cycle so the graph is populated from real hypotheses (currently `SimuladorEscenarios` runs with an empty placeholder graph).
3. Integrate `backup_manager.py` and `metrics_engine.py` into the operations cycle for production deployments.
4. Provide a real causal graph and database connection to `SimuladorEscenarios` so that Monte Carlo propagation travels through actual weighted relationships rather than returning trivial default values.

---

## 8. What Remains to be Done

### Known Technical Debt

| Issue | Severity | Description |
|-------|----------|-------------|
| Silent exception handlers | Medium | 59 instances of `except: pass` inherited from earlier development. Should be replaced with proper logging. |
| Windows testing | Medium | Code is portable, but `install.bat`, `veo.bat`, and validation script have not been executed on real Windows 11. |
| Real-mode CLI stability | Low | The full VEOCore is stateless and reinitializes on every command. Works correctly but is slower than mock mode. |
| LLM integration depth | Low | Deep questioning works in heuristic mode. Full semantic analysis requires an optional LLM connection. |

### Future Enhancements

| Feature | Description |
|---------|-------------|
| Live data connectors | RSS feeds, Twitter/X API, news APIs for real-time signal ingestion |
| Persistence layer | SQLAlchemy ORM for robust database operations |
| Authentication | API key or OAuth for multi-user deployments |
| Plugin system | Allow third-party agents and analyzers |
| Docker packaging | One-command deployment with Docker Compose |
| WebSocket streaming | Real-time dashboard updates from live data |

### Research Directions

- **Temporal knowledge graphs:** Track how relationships between entities evolve over time
- **Cross-lingual narrative analysis:** Detect the same story told in different languages
- **Adversarial robustness:** Ensure the validation pipeline cannot be easily gamed
- **Uncertainty quantification:** Move beyond point estimates to full probability distributions

---

## 9. Project Intention

VEO is designed as a **public good** — a tool that any individual, organization, or automated agent can deploy to better understand emergent changes in their information environment.

### Design Principles

1. **Independence:** No dependency on proprietary AI models, APIs, or platforms
2. **Transparency:** All algorithms are deterministic and inspectable
3. **Extensibility:** Modular architecture allows custom agents and analyzers
4. **Accessibility:** Works on commodity hardware (2 GB RAM, any OS)
5. **Cooperativity:** Designed for human-AI collaboration, not replacement

### Target Users

- **AI agents** operating autonomously in research or monitoring roles
- **Data analysts** tracking narrative shifts in media or social networks
- **Researchers** studying information dynamics, misinformation, or social trends
- **Journalists** identifying emerging stories before they reach mainstream attention
- **Organizations** monitoring their information environment for strategic planning

---

## 10. Attribution

VEO was created by **Yosu Gem**.

The architectural vision, design decisions, and feature specifications are the author's own. The implementation involved iterative development with AI assistance:

- **ChatGPT** provided the general project concept, structural guidance, and substantial portions of the code.
- **Kimi K3** (Moonshot AI) integrated the components, built the distribution packaging, dashboard, API dark mode interfaces, test suite, and documentation.

The author directed all development, evaluated outputs, and made final decisions on every aspect of the project.

The project is released under the Apache License 2.0.

---

## 11. License

Copyright 2025-2026 Yosu Gem

Licensed under the Apache License, Version 2.0.

You may use, modify, and distribute this software freely, provided that you include the original copyright notice and license terms. See the `LICENSE` file for the full text.

---

*Last updated: 2026-10-12*
