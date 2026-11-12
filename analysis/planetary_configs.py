"""
VEO v2 — Planetary Configurations (100 Diagnostic Families)
===========================================================

This module defines 100 conceptual diagnostic families used by the VEO v2
planetary analysis engine. Each configuration represents a unique lens through
which the event system's state is observed, scored, thresholded and mapped.

Each PlanetaryConfig is a pure data container (dataclass) with no computation
logic. The engine consumes these configurations to derive per-event scores,
global system scores, threshold alerts and 4D spatial mappings.

Available numeric event attributes (all normalized 0.0 → 1.0):
    persistence, relevance, foresight, future_gravity, fragility,
    future_pressure, acceleration, dependencies_count, recovery, redundancy

"""

from dataclasses import dataclass, field
from typing import Dict, List


# ═══════════════════════════════════════════════════════════════════════════════
# Base Configuration Dataclass
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class PlanetaryConfig:
    """
    A single diagnostic family (configuration) for planetary analysis.

    Each configuration defines HOW to look at the event system — which
    attributes matter, how much they weight, and what thresholds trigger
    alerts. Think of it as a "diagnostic lens" with its own focus.

    Attributes:
        name:               Short conceptual identifier (e.g., "entropy").
        description:        Human-readable explanation of what this family measures.
        score_attrs:        Attribute weights for computing per-event scores.
                            Keys are event attribute names; values are weights.
                            Sum should approximate 1.0.
        global_attrs:       Attribute weights for computing a single global score.
                            Sum should approximate 1.0.
        threshold_attrs:    Attribute weights for threshold breach detection.
                            Sum should approximate 1.0.
        map_attrs:          Ordered list of 4 attribute names for spatial mapping
                            [x_axis, y_axis, z_axis, v_axis (value)].
        alert_threshold:    Normalized threshold (0.0–1.0) above which an alert
                            is triggered for this family.
        scheduler_interval: Seconds between scheduled executions of this config.
        version:            Schema version of this configuration.
    """
    name: str
    description: str
    score_attrs: Dict[str, float]
    global_attrs: Dict[str, float]
    threshold_attrs: Dict[str, float]
    map_attrs: List[str]
    alert_threshold: float = 0.99
    scheduler_interval: int = 60
    version: str = "1.0"


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER: Normalization utilities (pure data, no runtime calculation)
# ═══════════════════════════════════════════════════════════════════════════════

# Pre-defined weight presets used by multiple configurations.
# These are reference dictionaries — each config below creates its own copy
# to remain self-contained and immutable.

_ALL_ATTRS = [
    "persistence", "relevance", "foresight", "future_gravity", "fragility",
    "future_pressure", "acceleration", "dependencies_count", "recovery", "redundancy",
]


def _even_weights(attrs: List[str]) -> Dict[str, float]:
    """Return equal weights summing to 1.0 for the given attributes."""
    w = 1.0 / len(attrs)
    return {a: round(w, 4) for a in attrs}


def _weighted(attrs_weights: Dict[str, float]) -> Dict[str, float]:
    """Normalize a raw weight dictionary so it sums to 1.0."""
    total = sum(attrs_weights.values())
    return {k: round(v / total, 4) for k, v in attrs_weights.items()}


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION CATALOG: 100 Diagnostic Families
# ═══════════════════════════════════════════════════════════════════════════════
# Organized into 10 conceptual groups of 10 configurations each.
#
# Group 1: Physical Dynamics     (configs 001–010)
# Group 2: Biological Systems    (configs 011–020)
# Group 3: Ecological Balance    (configs 021–030)
# Group 4: Societal Structures   (configs 031–040)
# Group 5: Economic Pressures    (configs 041–050)
# Group 6: Earth & Climate       (configs 051–060)
# Group 7: Chemical Processes    (configs 061–070)
# Group 8: Information Theory    (configs 071–080)
# Group 9: Systemic Health       (configs 081–090)
# Group 10: Advanced Meta        (configs 091–100)
# ═══════════════════════════════════════════════════════════════════════════════

PLANETARY_CONFIGS: List[PlanetaryConfig] = []


# ──────────────────────────────────────────────────────────────────────────────
# GROUP 1: Physical Dynamics (001–010)
# Inspired by classical physics, thermodynamics and dynamical systems.
# ──────────────────────────────────────────────────────────────────────────────

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="continuity",
    description=(
        "Measures the temporal continuity of an event — how strongly its future "
        "trajectory persists given its current persistence, foresight and pressure. "
        "High continuity indicates the event will maintain its influence over time."
    ),
    score_attrs=_weighted({"persistence": 0.40, "foresight": 0.30, "future_pressure": 0.20, "relevance": 0.10}),
    global_attrs=_weighted({"persistence": 0.35, "foresight": 0.25, "future_pressure": 0.25, "future_gravity": 0.15}),
    threshold_attrs=_weighted({"persistence": 0.45, "future_pressure": 0.30, "foresight": 0.15, "acceleration": 0.10}),
    map_attrs=["persistence", "foresight", "future_pressure", "future_gravity"],
    alert_threshold=0.95,
    scheduler_interval=60,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="consistency",
    description=(
        "Measures internal consistency among an event's attributes — whether its "
        "gravity, pressure, fragility and recovery tell a coherent story. "
        "Inconsistency may signal noise, data corruption or emergent complexity."
    ),
    score_attrs=_even_weights(["relevance", "future_gravity", "fragility", "recovery", "redundancy"]),
    global_attrs=_even_weights(["relevance", "future_gravity", "fragility", "recovery", "redundancy"]),
    threshold_attrs=_weighted({"fragility": 0.35, "recovery": 0.35, "redundancy": 0.20, "relevance": 0.10}),
    map_attrs=["relevance", "future_gravity", "fragility", "recovery"],
    alert_threshold=0.92,
    scheduler_interval=90,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="convergence",
    description=(
        "Measures whether multiple independent factors are converging toward a "
        "single event. High convergence means dependencies, gravity and pressure "
        "all point in the same direction, amplifying the event's significance."
    ),
    score_attrs=_weighted({"dependencies_count": 0.35, "future_gravity": 0.30, "future_pressure": 0.20, "relevance": 0.15}),
    global_attrs=_weighted({"dependencies_count": 0.30, "future_gravity": 0.30, "future_pressure": 0.25, "relevance": 0.15}),
    threshold_attrs=_weighted({"dependencies_count": 0.40, "future_gravity": 0.35, "future_pressure": 0.15, "persistence": 0.10}),
    map_attrs=["dependencies_count", "future_gravity", "future_pressure", "relevance"],
    alert_threshold=0.93,
    scheduler_interval=75,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="harmony",
    description=(
        "Measures the harmonic balance between opposing forces: resilience vs fragility, "
        "pressure vs recovery. A harmonious system is one where positive and negative "
        "indicators are in productive tension rather than destructive conflict."
    ),
    score_attrs=_weighted({"recovery": 0.30, "fragility": 0.25, "future_pressure": 0.25, "redundancy": 0.20}),
    global_attrs=_weighted({"recovery": 0.30, "redundancy": 0.25, "fragility": 0.25, "future_pressure": 0.20}),
    threshold_attrs=_weighted({"fragility": 0.40, "recovery": 0.35, "future_pressure": 0.15, "redundancy": 0.10}),
    map_attrs=["recovery", "fragility", "future_pressure", "redundancy"],
    alert_threshold=0.85,
    scheduler_interval=120,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="entropy",
    description=(
        "Inspired by thermodynamic entropy — measures the degree of disorder, "
        "dispersion and unpredictability in the event system. High entropy suggests "
        "the system's state is becoming less predictable and more chaotic."
    ),
    score_attrs=_weighted({"fragility": 0.30, "acceleration": 0.25, "dependencies_count": 0.20, "future_pressure": 0.15, "redundancy": 0.10}),
    global_attrs=_weighted({"fragility": 0.30, "acceleration": 0.25, "dependencies_count": 0.20, "future_pressure": 0.15, "redundancy": 0.10}),
    threshold_attrs=_weighted({"fragility": 0.35, "acceleration": 0.30, "dependencies_count": 0.20, "future_pressure": 0.15}),
    map_attrs=["fragility", "acceleration", "dependencies_count", "future_pressure"],
    alert_threshold=0.88,
    scheduler_interval=45,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="inertia",
    description=(
        "Physical inertia applied to events — the resistance of the system to changes "
        "in its current state. High inertia means events tend to persist unchanged "
        "despite external pressures, making the system slow to adapt."
    ),
    score_attrs=_weighted({"persistence": 0.45, "future_gravity": 0.25, "relevance": 0.20, "acceleration": 0.10}),
    global_attrs=_weighted({"persistence": 0.40, "future_gravity": 0.30, "relevance": 0.20, "acceleration": 0.10}),
    threshold_attrs=_weighted({"persistence": 0.50, "future_gravity": 0.30, "relevance": 0.10, "acceleration": 0.10}),
    map_attrs=["persistence", "future_gravity", "relevance", "acceleration"],
    alert_threshold=0.90,
    scheduler_interval=120,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="momentum",
    description=(
        "The product of inertia and acceleration — measures how much 'motion' the "
        "event system carries into the future. High momentum events are both persistent "
        "and accelerating, creating a powerful forward trajectory."
    ),
    score_attrs=_weighted({"persistence": 0.35, "acceleration": 0.35, "future_pressure": 0.20, "future_gravity": 0.10}),
    global_attrs=_weighted({"persistence": 0.30, "acceleration": 0.35, "future_pressure": 0.20, "future_gravity": 0.15}),
    threshold_attrs=_weighted({"acceleration": 0.45, "persistence": 0.30, "future_pressure": 0.15, "future_gravity": 0.10}),
    map_attrs=["persistence", "acceleration", "future_pressure", "future_gravity"],
    alert_threshold=0.91,
    scheduler_interval=60,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="equilibrium",
    description=(
        "Measures how close the event system is to a balanced, steady state where "
        "forces of pressure, fragility, recovery and gravity cancel each other out. "
        "Deviation from equilibrium signals systemic stress."
    ),
    score_attrs=_weighted({"future_pressure": 0.25, "fragility": 0.25, "recovery": 0.25, "future_gravity": 0.25}),
    global_attrs=_weighted({"future_pressure": 0.25, "fragility": 0.25, "recovery": 0.25, "redundancy": 0.25}),
    threshold_attrs=_weighted({"future_pressure": 0.30, "fragility": 0.30, "recovery": 0.25, "redundancy": 0.15}),
    map_attrs=["future_pressure", "fragility", "recovery", "future_gravity"],
    alert_threshold=0.80,
    scheduler_interval=180,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="resonance",
    description=(
        "Measures sympathetic vibration between events — when multiple events' "
        "attributes (persistence, gravity, pressure) align in phase, creating "
        "amplified effects through constructive interference."
    ),
    score_attrs=_weighted({"persistence": 0.30, "future_gravity": 0.25, "future_pressure": 0.25, "relevance": 0.20}),
    global_attrs=_weighted({"persistence": 0.25, "future_gravity": 0.30, "future_pressure": 0.25, "relevance": 0.20}),
    threshold_attrs=_weighted({"future_gravity": 0.35, "future_pressure": 0.30, "persistence": 0.20, "relevance": 0.15}),
    map_attrs=["persistence", "future_gravity", "future_pressure", "relevance"],
    alert_threshold=0.87,
    scheduler_interval=90,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="phase_transition",
    description=(
        "Detects conditions under which the event system may undergo a qualitative "
        "change of state — a tipping point. Monitors the combination of pressure, "
        "acceleration and fragility that precedes rapid systemic shifts."
    ),
    score_attrs=_weighted({"future_pressure": 0.35, "acceleration": 0.30, "fragility": 0.20, "future_gravity": 0.15}),
    global_attrs=_weighted({"future_pressure": 0.30, "acceleration": 0.30, "fragility": 0.25, "persistence": 0.15}),
    threshold_attrs=_weighted({"future_pressure": 0.40, "acceleration": 0.35, "fragility": 0.15, "persistence": 0.10}),
    map_attrs=["future_pressure", "acceleration", "fragility", "future_gravity"],
    alert_threshold=0.94,
    scheduler_interval=30,
))


# ──────────────────────────────────────────────────────────────────────────────
# GROUP 2: Biological Systems (011–020)
# Inspired by living organisms, cell biology, evolution and physiology.
# ──────────────────────────────────────────────────────────────────────────────

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="metabolism",
    description=(
        "Measures the rate at which the event system processes, transforms and "
        "expends resources. Analogous to cellular metabolism — high metabolism means "
        "rapid turnover of events with high acceleration and pressure."
    ),
    score_attrs=_weighted({"acceleration": 0.35, "future_pressure": 0.30, "persistence": 0.20, "relevance": 0.15}),
    global_attrs=_weighted({"acceleration": 0.30, "future_pressure": 0.30, "persistence": 0.25, "relevance": 0.15}),
    threshold_attrs=_weighted({"acceleration": 0.40, "future_pressure": 0.35, "persistence": 0.15, "relevance": 0.10}),
    map_attrs=["acceleration", "future_pressure", "persistence", "relevance"],
    alert_threshold=0.90,
    scheduler_interval=60,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="immunity",
    description=(
        "Measures the system's immune response — its capacity to absorb shocks, "
        "recover from stress events and maintain integrity. High immunity reflects "
        "strong redundancy and recovery mechanisms."
    ),
    score_attrs=_weighted({"recovery": 0.40, "redundancy": 0.35, "fragility": 0.15, "persistence": 0.10}),
    global_attrs=_weighted({"recovery": 0.35, "redundancy": 0.35, "fragility": 0.15, "persistence": 0.15}),
    threshold_attrs=_weighted({"recovery": 0.40, "redundancy": 0.40, "fragility": 0.10, "persistence": 0.10}),
    map_attrs=["recovery", "redundancy", "fragility", "persistence"],
    alert_threshold=0.75,
    scheduler_interval=120,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="homeostasis",
    description=(
        "Biological homeostasis — the system's ability to maintain stable internal "
        "conditions despite external perturbations. Measures the balance between "
        "pressure, recovery and self-regulating mechanisms."
    ),
    score_attrs=_weighted({"future_pressure": 0.25, "recovery": 0.30, "redundancy": 0.25, "fragility": 0.20}),
    global_attrs=_weighted({"future_pressure": 0.25, "recovery": 0.30, "redundancy": 0.25, "persistence": 0.20}),
    threshold_attrs=_weighted({"recovery": 0.35, "redundancy": 0.30, "future_pressure": 0.20, "fragility": 0.15}),
    map_attrs=["future_pressure", "recovery", "redundancy", "fragility"],
    alert_threshold=0.82,
    scheduler_interval=180,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="regeneration",
    description=(
        "Measures the system's capacity to regenerate lost capacity or repair damage "
        "after stress events. Focuses on recovery velocity, redundancy depth and "
        "the persistence of healing processes over time."
    ),
    score_attrs=_weighted({"recovery": 0.45, "redundancy": 0.30, "persistence": 0.15, "relevance": 0.10}),
    global_attrs=_weighted({"recovery": 0.40, "redundancy": 0.30, "persistence": 0.20, "relevance": 0.10}),
    threshold_attrs=_weighted({"recovery": 0.50, "redundancy": 0.30, "persistence": 0.10, "relevance": 0.10}),
    map_attrs=["recovery", "redundancy", "persistence", "relevance"],
    alert_threshold=0.78,
    scheduler_interval=120,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="apoptosis",
    description=(
        "Programmed cell death as a model — measures whether the system correctly "
        "identifies and eliminates events that have outlived their usefulness. "
        "Detects zombie events with low relevance but high persistence."
    ),
    score_attrs=_weighted({"persistence": 0.40, "relevance": 0.30, "recovery": 0.15, "redundancy": 0.15}),
    global_attrs=_weighted({"persistence": 0.35, "relevance": 0.30, "recovery": 0.20, "redundancy": 0.15}),
    threshold_attrs=_weighted({"persistence": 0.45, "relevance": 0.35, "recovery": 0.10, "redundancy": 0.10}),
    map_attrs=["persistence", "relevance", "recovery", "redundancy"],
    alert_threshold=0.88,
    scheduler_interval=90,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="growth_rate",
    description=(
        "Measures the exponential growth potential of event influence — how quickly "
        "an event's gravity, pressure and relevance compound over time. "
        "High growth rate signals viral or cascading dynamics."
    ),
    score_attrs=_weighted({"acceleration": 0.40, "future_gravity": 0.25, "future_pressure": 0.20, "relevance": 0.15}),
    global_attrs=_weighted({"acceleration": 0.35, "future_gravity": 0.25, "future_pressure": 0.25, "relevance": 0.15}),
    threshold_attrs=_weighted({"acceleration": 0.45, "future_gravity": 0.25, "future_pressure": 0.20, "relevance": 0.10}),
    map_attrs=["acceleration", "future_gravity", "future_pressure", "relevance"],
    alert_threshold=0.92,
    scheduler_interval=45,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="symbiosis",
    description=(
        "Measures mutually beneficial relationships between events — where the "
        "existence and strength of one event positively reinforces others through "
        "shared dependencies, redundancy and complementary pressures."
    ),
    score_attrs=_weighted({"dependencies_count": 0.35, "redundancy": 0.30, "relevance": 0.20, "recovery": 0.15}),
    global_attrs=_weighted({"dependencies_count": 0.30, "redundancy": 0.30, "relevance": 0.25, "recovery": 0.15}),
    threshold_attrs=_weighted({"dependencies_count": 0.40, "redundancy": 0.35, "relevance": 0.15, "recovery": 0.10}),
    map_attrs=["dependencies_count", "redundancy", "relevance", "recovery"],
    alert_threshold=0.85,
    scheduler_interval=120,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="mutation_rate",
    description=(
        "Measures the rate of unexpected change in event attributes — analogous to "
        "genetic mutation. High mutation rate in events suggests an unstable environment "
        "where predictions become unreliable and adaptation is forced."
    ),
    score_attrs=_weighted({"acceleration": 0.35, "fragility": 0.30, "foresight": 0.20, "future_pressure": 0.15}),
    global_attrs=_weighted({"acceleration": 0.30, "fragility": 0.30, "foresight": 0.25, "future_pressure": 0.15}),
    threshold_attrs=_weighted({"acceleration": 0.40, "fragility": 0.35, "foresight": 0.15, "future_pressure": 0.10}),
    map_attrs=["acceleration", "fragility", "foresight", "future_pressure"],
    alert_threshold=0.90,
    scheduler_interval=60,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="selection_pressure",
    description=(
        "Darwinian selection applied to events — measures how strongly the environment "
        "favors events with certain attribute profiles. High selection pressure means "
        "only highly adapted events survive and propagate."
    ),
    score_attrs=_weighted({"future_pressure": 0.35, "relevance": 0.25, "persistence": 0.20, "fragility": 0.20}),
    global_attrs=_weighted({"future_pressure": 0.30, "relevance": 0.25, "persistence": 0.25, "fragility": 0.20}),
    threshold_attrs=_weighted({"future_pressure": 0.40, "relevance": 0.25, "persistence": 0.20, "fragility": 0.15}),
    map_attrs=["future_pressure", "relevance", "persistence", "fragility"],
    alert_threshold=0.88,
    scheduler_interval=90,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="trophic_cascade",
    description=(
        "Ecological trophic cascade — measures how influence flows through levels of "
        "the event dependency network. A strong cascade means changes at one level "
        "dramatically affect distant levels through dependency chains."
    ),
    score_attrs=_weighted({"dependencies_count": 0.40, "future_gravity": 0.30, "future_pressure": 0.20, "persistence": 0.10}),
    global_attrs=_weighted({"dependencies_count": 0.35, "future_gravity": 0.30, "future_pressure": 0.25, "persistence": 0.10}),
    threshold_attrs=_weighted({"dependencies_count": 0.45, "future_gravity": 0.35, "future_pressure": 0.10, "persistence": 0.10}),
    map_attrs=["dependencies_count", "future_gravity", "future_pressure", "persistence"],
    alert_threshold=0.91,
    scheduler_interval=75,
))


# ──────────────────────────────────────────────────────────────────────────────
# GROUP 3: Ecological Balance (021–030)
# Inspired by ecology, environmental science and ecosystem dynamics.
# ──────────────────────────────────────────────────────────────────────────────

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="diversity",
    description=(
        "Measures the diversity of event types, pressures and outcomes in the system. "
        "High diversity (many different attribute profiles) makes the system robust "
        "against monoculture failures but harder to predict."
    ),
    score_attrs=_even_weights(["relevance", "future_gravity", "fragility", "recovery", "future_pressure", "persistence"]),
    global_attrs=_even_weights(["relevance", "future_gravity", "fragility", "recovery", "future_pressure", "redundancy"]),
    threshold_attrs=_weighted({"fragility": 0.30, "recovery": 0.25, "future_pressure": 0.20, "redundancy": 0.15, "relevance": 0.10}),
    map_attrs=["relevance", "future_gravity", "fragility", "recovery"],
    alert_threshold=0.80,
    scheduler_interval=180,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="succession",
    description=(
        "Ecological succession — the predictable sequence of event evolution from "
        "early colonizers (low persistence, high acceleration) to climax communities "
        "(high persistence, high gravity). Measures where the system sits in this cycle."
    ),
    score_attrs=_weighted({"persistence": 0.35, "acceleration": 0.25, "future_gravity": 0.25, "relevance": 0.15}),
    global_attrs=_weighted({"persistence": 0.30, "future_gravity": 0.30, "acceleration": 0.25, "relevance": 0.15}),
    threshold_attrs=_weighted({"persistence": 0.40, "acceleration": 0.30, "future_gravity": 0.20, "relevance": 0.10}),
    map_attrs=["persistence", "acceleration", "future_gravity", "relevance"],
    alert_threshold=0.85,
    scheduler_interval=120,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="fragmentation",
    description=(
        "Measures the degree to which the event system is fragmented into isolated "
        "subsystems with few connections. High fragmentation reduces cascade risk but "
        "also limits information flow and coordinated response capacity."
    ),
    score_attrs=_weighted({"dependencies_count": 0.40, "redundancy": 0.25, "relevance": 0.20, "persistence": 0.15}),
    global_attrs=_weighted({"dependencies_count": 0.35, "redundancy": 0.25, "relevance": 0.25, "persistence": 0.15}),
    threshold_attrs=_weighted({"dependencies_count": 0.45, "redundancy": 0.25, "relevance": 0.15, "persistence": 0.15}),
    map_attrs=["dependencies_count", "redundancy", "relevance", "persistence"],
    alert_threshold=0.87,
    scheduler_interval=150,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="connectivity",
    description=(
        "The inverse of fragmentation — measures how densely connected the event "
        "network is. High connectivity enables rapid propagation of both stress and "
        "recovery signals across the entire system."
    ),
    score_attrs=_weighted({"dependencies_count": 0.45, "redundancy": 0.30, "future_gravity": 0.15, "persistence": 0.10}),
    global_attrs=_weighted({"dependencies_count": 0.40, "redundancy": 0.30, "future_gravity": 0.20, "persistence": 0.10}),
    threshold_attrs=_weighted({"dependencies_count": 0.50, "redundancy": 0.30, "future_gravity": 0.10, "persistence": 0.10}),
    map_attrs=["dependencies_count", "redundancy", "future_gravity", "persistence"],
    alert_threshold=0.88,
    scheduler_interval=120,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="biomass_flow",
    description=(
        "Measures the flow of 'energy' or influence through the event network — "
        "how much cumulative gravity, pressure and relevance circulates. Analogous "
        "to energy flow through trophic levels in an ecosystem."
    ),
    score_attrs=_weighted({"future_gravity": 0.30, "future_pressure": 0.25, "relevance": 0.25, "persistence": 0.20}),
    global_attrs=_weighted({"future_gravity": 0.30, "future_pressure": 0.25, "relevance": 0.25, "persistence": 0.20}),
    threshold_attrs=_weighted({"future_gravity": 0.35, "future_pressure": 0.30, "relevance": 0.20, "persistence": 0.15}),
    map_attrs=["future_gravity", "future_pressure", "relevance", "persistence"],
    alert_threshold=0.90,
    scheduler_interval=90,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="carrying_capacity",
    description=(
        "Measures how close the event system is to its maximum sustainable load. "
        "When pressure and dependency counts approach carrying capacity limits, "
        "the system risks overshoot and collapse."
    ),
    score_attrs=_weighted({"future_pressure": 0.35, "dependencies_count": 0.30, "fragility": 0.20, "redundancy": 0.15}),
    global_attrs=_weighted({"future_pressure": 0.30, "dependencies_count": 0.30, "fragility": 0.25, "redundancy": 0.15}),
    threshold_attrs=_weighted({"future_pressure": 0.40, "dependencies_count": 0.35, "fragility": 0.15, "redundancy": 0.10}),
    map_attrs=["future_pressure", "dependencies_count", "fragility", "redundancy"],
    alert_threshold=0.93,
    scheduler_interval=60,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="keystone_effect",
    description=(
        "Identifies keystone events — individual events whose removal would cause "
        "disproportionate disruption. Analogous to keystone species. These events "
        "have extreme gravity, high dependency centrality and irreplaceable function."
    ),
    score_attrs=_weighted({"future_gravity": 0.40, "dependencies_count": 0.35, "persistence": 0.15, "redundancy": 0.10}),
    global_attrs=_weighted({"future_gravity": 0.35, "dependencies_count": 0.35, "persistence": 0.15, "redundancy": 0.15}),
    threshold_attrs=_weighted({"future_gravity": 0.45, "dependencies_count": 0.40, "persistence": 0.10, "redundancy": 0.05}),
    map_attrs=["future_gravity", "dependencies_count", "persistence", "redundancy"],
    alert_threshold=0.95,
    scheduler_interval=45,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="disturbance_regime",
    description=(
        "Characterizes the pattern, frequency and intensity of disturbances hitting "
        "the event system. A stable regime has low-frequency, low-intensity disturbances; "
        "an unstable regime has frequent high-acceleration shocks."
    ),
    score_attrs=_weighted({"acceleration": 0.35, "fragility": 0.25, "future_pressure": 0.25, "recovery": 0.15}),
    global_attrs=_weighted({"acceleration": 0.30, "fragility": 0.25, "future_pressure": 0.25, "recovery": 0.20}),
    threshold_attrs=_weighted({"acceleration": 0.40, "fragility": 0.30, "future_pressure": 0.20, "recovery": 0.10}),
    map_attrs=["acceleration", "fragility", "future_pressure", "recovery"],
    alert_threshold=0.89,
    scheduler_interval=60,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="ecological_niche",
    description=(
        "Measures how well each event occupies its unique functional position in the "
        "system — the combination of attributes that makes it irreplaceable. Events "
        "with well-defined niches are essential; those without are redundant."
    ),
    score_attrs=_weighted({"relevance": 0.30, "persistence": 0.25, "redundancy": 0.25, "future_gravity": 0.20}),
    global_attrs=_weighted({"relevance": 0.30, "persistence": 0.25, "redundancy": 0.25, "future_gravity": 0.20}),
    threshold_attrs=_weighted({"relevance": 0.35, "persistence": 0.30, "redundancy": 0.20, "future_gravity": 0.15}),
    map_attrs=["relevance", "persistence", "redundancy", "future_gravity"],
    alert_threshold=0.84,
    scheduler_interval=120,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="nutrient_cycling",
    description=(
        "Measures the recycling efficiency of the system — how well events recover, "
        "redeploy and reuse their capacity after stress. Analogous to nutrient cycling "
        "in ecosystems where matter is continuously reused rather than lost."
    ),
    score_attrs=_weighted({"recovery": 0.40, "redundancy": 0.30, "persistence": 0.20, "future_pressure": 0.10}),
    global_attrs=_weighted({"recovery": 0.35, "redundancy": 0.30, "persistence": 0.20, "future_pressure": 0.15}),
    threshold_attrs=_weighted({"recovery": 0.45, "redundancy": 0.30, "persistence": 0.15, "future_pressure": 0.10}),
    map_attrs=["recovery", "redundancy", "persistence", "future_pressure"],
    alert_threshold=0.78,
    scheduler_interval=150,
))


# ──────────────────────────────────────────────────────────────────────────────
# GROUP 4: Societal Structures (031–040)
# Inspired by sociology, political science and social dynamics.
# ──────────────────────────────────────────────────────────────────────────────

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="polarization",
    description=(
        "Measures the degree of divergence between opposing event clusters — whether "
        "events gravitate toward extreme positions (high gravity, high pressure) or "
        "cluster around moderate centroids. High polarization reduces consensus."
    ),
    score_attrs=_weighted({"future_gravity": 0.30, "future_pressure": 0.25, "fragility": 0.25, "relevance": 0.20}),
    global_attrs=_weighted({"future_gravity": 0.30, "future_pressure": 0.25, "fragility": 0.25, "relevance": 0.20}),
    threshold_attrs=_weighted({"future_gravity": 0.35, "future_pressure": 0.30, "fragility": 0.20, "relevance": 0.15}),
    map_attrs=["future_gravity", "future_pressure", "fragility", "relevance"],
    alert_threshold=0.90,
    scheduler_interval=90,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="consensus",
    description=(
        "Measures the degree of agreement or alignment among events — how many events "
        "point in similar directions regarding pressure, gravity and relevance. High "
        "consensus enables coordinated action but may suppress necessary dissent."
    ),
    score_attrs=_weighted({"relevance": 0.30, "persistence": 0.25, "future_gravity": 0.25, "recovery": 0.20}),
    global_attrs=_weighted({"relevance": 0.30, "persistence": 0.25, "future_gravity": 0.25, "recovery": 0.20}),
    threshold_attrs=_weighted({"relevance": 0.35, "persistence": 0.30, "future_gravity": 0.20, "recovery": 0.15}),
    map_attrs=["relevance", "persistence", "future_gravity", "recovery"],
    alert_threshold=0.82,
    scheduler_interval=120,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="social_capital",
    description=(
        "Measures the stock of trust, mutual dependence and cooperative capacity "
        "built up in the event network. High social capital means events support "
        "each other through redundancy and shared recovery mechanisms."
    ),
    score_attrs=_weighted({"redundancy": 0.35, "dependencies_count": 0.25, "recovery": 0.25, "relevance": 0.15}),
    global_attrs=_weighted({"redundancy": 0.30, "dependencies_count": 0.25, "recovery": 0.25, "relevance": 0.20}),
    threshold_attrs=_weighted({"redundancy": 0.40, "dependencies_count": 0.30, "recovery": 0.20, "relevance": 0.10}),
    map_attrs=["redundancy", "dependencies_count", "recovery", "relevance"],
    alert_threshold=0.78,
    scheduler_interval=180,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="power_concentration",
    description=(
        "Measures the concentration of influence in a small number of dominant events. "
        "High concentration (few events with extreme gravity and persistence) creates "
        "oligopolistic dynamics and systemic vulnerability to their failure."
    ),
    score_attrs=_weighted({"future_gravity": 0.40, "persistence": 0.30, "relevance": 0.20, "dependencies_count": 0.10}),
    global_attrs=_weighted({"future_gravity": 0.35, "persistence": 0.30, "relevance": 0.20, "dependencies_count": 0.15}),
    threshold_attrs=_weighted({"future_gravity": 0.45, "persistence": 0.35, "relevance": 0.10, "dependencies_count": 0.10}),
    map_attrs=["future_gravity", "persistence", "relevance", "dependencies_count"],
    alert_threshold=0.94,
    scheduler_interval=60,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="institutional_memory",
    description=(
        "Measures how well the system retains and leverages historical knowledge from "
        "past events. High institutional memory means persistent, well-recovered events "
        "inform current decision-making, preventing repeated mistakes."
    ),
    score_attrs=_weighted({"persistence": 0.35, "recovery": 0.30, "foresight": 0.25, "relevance": 0.10}),
    global_attrs=_weighted({"persistence": 0.30, "recovery": 0.30, "foresight": 0.25, "relevance": 0.15}),
    threshold_attrs=_weighted({"persistence": 0.40, "recovery": 0.30, "foresight": 0.20, "relevance": 0.10}),
    map_attrs=["persistence", "recovery", "foresight", "relevance"],
    alert_threshold=0.80,
    scheduler_interval=180,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="legitimacy",
    description=(
        "Measures whether events are perceived as justified, well-founded and aligned "
        "with the system's core values. Legitimate events have high relevance, balanced "
        "attributes and strong foresight support; illegitimate events appear arbitrary."
    ),
    score_attrs=_weighted({"relevance": 0.35, "foresight": 0.30, "persistence": 0.20, "future_gravity": 0.15}),
    global_attrs=_weighted({"relevance": 0.30, "foresight": 0.30, "persistence": 0.25, "future_gravity": 0.15}),
    threshold_attrs=_weighted({"relevance": 0.40, "foresight": 0.35, "persistence": 0.15, "future_gravity": 0.10}),
    map_attrs=["relevance", "foresight", "persistence", "future_gravity"],
    alert_threshold=0.83,
    scheduler_interval=120,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="solidarity",
    description=(
        "Measures the degree of mutual support and collective resilience across events. "
        "High solidarity means events share recovery resources, provide mutual redundancy "
        "and coordinate under pressure rather than competing."
    ),
    score_attrs=_weighted({"recovery": 0.30, "redundancy": 0.30, "dependencies_count": 0.20, "future_pressure": 0.20}),
    global_attrs=_weighted({"recovery": 0.30, "redundancy": 0.30, "dependencies_count": 0.20, "future_pressure": 0.20}),
    threshold_attrs=_weighted({"recovery": 0.35, "redundancy": 0.35, "dependencies_count": 0.15, "future_pressure": 0.15}),
    map_attrs=["recovery", "redundancy", "dependencies_count", "future_pressure"],
    alert_threshold=0.76,
    scheduler_interval=150,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="conflict_intensity",
    description=(
        "Measures the intensity of conflicts between opposing events — where high "
        "pressure meets high fragility, or where divergent gravities create tension. "
        "Conflict intensity signals zones requiring intervention."
    ),
    score_attrs=_weighted({"future_pressure": 0.30, "fragility": 0.30, "future_gravity": 0.25, "acceleration": 0.15}),
    global_attrs=_weighted({"future_pressure": 0.30, "fragility": 0.30, "future_gravity": 0.25, "acceleration": 0.15}),
    threshold_attrs=_weighted({"future_pressure": 0.35, "fragility": 0.35, "future_gravity": 0.20, "acceleration": 0.10}),
    map_attrs=["future_pressure", "fragility", "future_gravity", "acceleration"],
    alert_threshold=0.92,
    scheduler_interval=60,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="cultural_inertia",
    description=(
        "The resistance of the event system to adopt new patterns or abandon old ones, "
        "analogous to cultural inertia in societies. High cultural inertia means deeply "
        "persistent events resist change even when adaptation is clearly needed."
    ),
    score_attrs=_weighted({"persistence": 0.45, "relevance": 0.25, "foresight": 0.15, "recovery": 0.15}),
    global_attrs=_weighted({"persistence": 0.40, "relevance": 0.25, "foresight": 0.20, "recovery": 0.15}),
    threshold_attrs=_weighted({"persistence": 0.50, "relevance": 0.25, "foresight": 0.15, "recovery": 0.10}),
    map_attrs=["persistence", "relevance", "foresight", "recovery"],
    alert_threshold=0.91,
    scheduler_interval=120,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="governance_quality",
    description=(
        "Measures the effectiveness of internal governance mechanisms — how well the "
        "system regulates itself through foresight, balanced pressure distribution, "
        "and adequate redundancy without excessive control."
    ),
    score_attrs=_weighted({"foresight": 0.30, "redundancy": 0.25, "future_pressure": 0.20, "recovery": 0.25}),
    global_attrs=_weighted({"foresight": 0.30, "redundancy": 0.25, "future_pressure": 0.20, "recovery": 0.25}),
    threshold_attrs=_weighted({"foresight": 0.35, "redundancy": 0.30, "future_pressure": 0.20, "recovery": 0.15}),
    map_attrs=["foresight", "redundancy", "future_pressure", "recovery"],
    alert_threshold=0.80,
    scheduler_interval=180,
))


# ──────────────────────────────────────────────────────────────────────────────
# GROUP 5: Economic Pressures (041–050)
# Inspired by economics, finance and market dynamics.
# ──────────────────────────────────────────────────────────────────────────────

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="market_efficiency",
    description=(
        "Measures how efficiently the event system allocates attention and resources "
        "across events. An efficient system directs resources to high-relevance, "
        "high-foresight events without wasteful redundancy."
    ),
    score_attrs=_weighted({"relevance": 0.30, "foresight": 0.25, "redundancy": 0.25, "future_gravity": 0.20}),
    global_attrs=_weighted({"relevance": 0.30, "foresight": 0.25, "redundancy": 0.25, "future_gravity": 0.20}),
    threshold_attrs=_weighted({"relevance": 0.35, "foresight": 0.30, "redundancy": 0.20, "future_gravity": 0.15}),
    map_attrs=["relevance", "foresight", "redundancy", "future_gravity"],
    alert_threshold=0.82,
    scheduler_interval=120,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="liquidity_stress",
    description=(
        "Measures whether the system has sufficient 'liquidity' — the ability to "
        "rapidly redeploy recovery resources and redundancy when events face sudden "
        "pressure. Liquidity stress signals imminent systemic failure."
    ),
    score_attrs=_weighted({"recovery": 0.35, "redundancy": 0.30, "future_pressure": 0.20, "fragility": 0.15}),
    global_attrs=_weighted({"recovery": 0.30, "redundancy": 0.30, "future_pressure": 0.25, "fragility": 0.15}),
    threshold_attrs=_weighted({"recovery": 0.40, "redundancy": 0.35, "future_pressure": 0.15, "fragility": 0.10}),
    map_attrs=["recovery", "redundancy", "future_pressure", "fragility"],
    alert_threshold=0.93,
    scheduler_interval=45,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="systemic_risk",
    description=(
        "Measures the risk that a single event failure triggers cascading failures "
        "across the entire system. Focuses on high-gravity, highly-connected events "
        "with low redundancy that act as single points of failure."
    ),
    score_attrs=_weighted({"future_gravity": 0.35, "dependencies_count": 0.30, "fragility": 0.20, "redundancy": 0.15}),
    global_attrs=_weighted({"future_gravity": 0.30, "dependencies_count": 0.30, "fragility": 0.25, "redundancy": 0.15}),
    threshold_attrs=_weighted({"future_gravity": 0.40, "dependencies_count": 0.35, "fragility": 0.15, "redundancy": 0.10}),
    map_attrs=["future_gravity", "dependencies_count", "fragility", "redundancy"],
    alert_threshold=0.95,
    scheduler_interval=30,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="contagion",
    description=(
        "Measures the potential for stress to propagate from event to event through "
        "dependency networks. Focuses on high-pressure events with many dependents "
        "and low firebreaks (redundancy). Contagion is the speed of propagation."
    ),
    score_attrs=_weighted({"future_pressure": 0.35, "dependencies_count": 0.30, "acceleration": 0.20, "redundancy": 0.15}),
    global_attrs=_weighted({"future_pressure": 0.30, "dependencies_count": 0.30, "acceleration": 0.25, "redundancy": 0.15}),
    threshold_attrs=_weighted({"future_pressure": 0.40, "dependencies_count": 0.35, "acceleration": 0.15, "redundancy": 0.10}),
    map_attrs=["future_pressure", "dependencies_count", "acceleration", "redundancy"],
    alert_threshold=0.94,
    scheduler_interval=30,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="arbitrage_opportunity",
    description=(
        "Identifies imbalances in the event system where the relationship between "
        "attributes creates exploitable gaps — high relevance with low persistence, "
        "or high gravity with low pressure. These gaps represent missed opportunities."
    ),
    score_attrs=_weighted({"relevance": 0.30, "persistence": 0.25, "future_gravity": 0.25, "future_pressure": 0.20}),
    global_attrs=_weighted({"relevance": 0.30, "persistence": 0.25, "future_gravity": 0.25, "future_pressure": 0.20}),
    threshold_attrs=_weighted({"relevance": 0.35, "persistence": 0.30, "future_gravity": 0.20, "future_pressure": 0.15}),
    map_attrs=["relevance", "persistence", "future_gravity", "future_pressure"],
    alert_threshold=0.86,
    scheduler_interval=90,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="volatility_clustering",
    description=(
        "Detects clustering of high-volatility periods — when acceleration and "
        "pressure spike together across multiple events. Financial markets exhibit "
        "this pattern; the event system may too, signaling turbulent periods."
    ),
    score_attrs=_weighted({"acceleration": 0.40, "future_pressure": 0.30, "fragility": 0.20, "persistence": 0.10}),
    global_attrs=_weighted({"acceleration": 0.35, "future_pressure": 0.30, "fragility": 0.25, "persistence": 0.10}),
    threshold_attrs=_weighted({"acceleration": 0.45, "future_pressure": 0.35, "fragility": 0.15, "persistence": 0.05}),
    map_attrs=["acceleration", "future_pressure", "fragility", "persistence"],
    alert_threshold=0.91,
    scheduler_interval=60,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="moral_hazard",
    description=(
        "Detects moral hazard situations — events that take excessive risk because "
        "they expect recovery systems (redundancy, dependencies) to bail them out. "
        "High fragility paired with high recovery/redundancy signals this pattern."
    ),
    score_attrs=_weighted({"fragility": 0.40, "recovery": 0.30, "redundancy": 0.20, "dependencies_count": 0.10}),
    global_attrs=_weighted({"fragility": 0.35, "recovery": 0.30, "redundancy": 0.25, "dependencies_count": 0.10}),
    threshold_attrs=_weighted({"fragility": 0.45, "recovery": 0.30, "redundancy": 0.15, "dependencies_count": 0.10}),
    map_attrs=["fragility", "recovery", "redundancy", "dependencies_count"],
    alert_threshold=0.89,
    scheduler_interval=120,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="network_externalities",
    description=(
        "Measures the strength of network effects — where an event's value increases "
        "as more events depend on it. High externalities mean gravity and dependency "
        "counts create positive feedback loops amplifying influence."
    ),
    score_attrs=_weighted({"dependencies_count": 0.40, "future_gravity": 0.30, "relevance": 0.20, "persistence": 0.10}),
    global_attrs=_weighted({"dependencies_count": 0.35, "future_gravity": 0.30, "relevance": 0.25, "persistence": 0.10}),
    threshold_attrs=_weighted({"dependencies_count": 0.45, "future_gravity": 0.35, "relevance": 0.10, "persistence": 0.10}),
    map_attrs=["dependencies_count", "future_gravity", "relevance", "persistence"],
    alert_threshold=0.90,
    scheduler_interval=90,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="speculative_pressure",
    description=(
        "Measures pressure driven by anticipation of future changes rather than current "
        "conditions. Speculative pressure arises when foresight and acceleration exceed "
        "what current gravity and relevance justify — a bubble signature."
    ),
    score_attrs=_weighted({"foresight": 0.35, "acceleration": 0.30, "future_pressure": 0.20, "future_gravity": 0.15}),
    global_attrs=_weighted({"foresight": 0.30, "acceleration": 0.30, "future_pressure": 0.25, "future_gravity": 0.15}),
    threshold_attrs=_weighted({"foresight": 0.40, "acceleration": 0.35, "future_pressure": 0.15, "future_gravity": 0.10}),
    map_attrs=["foresight", "acceleration", "future_pressure", "future_gravity"],
    alert_threshold=0.93,
    scheduler_interval=60,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="price_discovery",
    description=(
        "Measures how well the event system discovers the 'true value' of events — "
        "the process by which relevance, gravity and foresight converge toward stable "
        "accurate assessments. Inefficient discovery leaves events mispriced."
    ),
    score_attrs=_weighted({"relevance": 0.30, "future_gravity": 0.25, "foresight": 0.25, "persistence": 0.20}),
    global_attrs=_weighted({"relevance": 0.30, "future_gravity": 0.25, "foresight": 0.25, "persistence": 0.20}),
    threshold_attrs=_weighted({"relevance": 0.35, "future_gravity": 0.25, "foresight": 0.25, "persistence": 0.15}),
    map_attrs=["relevance", "future_gravity", "foresight", "persistence"],
    alert_threshold=0.84,
    scheduler_interval=120,
))


# ──────────────────────────────────────────────────────────────────────────────
# GROUP 6: Earth & Climate (051–060)
# Inspired by geology, climatology and planetary science.
# ──────────────────────────────────────────────────────────────────────────────

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="seismic_stress",
    description=(
        "Measures accumulated stress in the event system analogous to tectonic plate "
        "stress before an earthquake. Monitors the buildup of pressure, fragility and "
        "acceleration that precedes sudden release events."
    ),
    score_attrs=_weighted({"future_pressure": 0.35, "fragility": 0.25, "acceleration": 0.25, "persistence": 0.15}),
    global_attrs=_weighted({"future_pressure": 0.30, "fragility": 0.25, "acceleration": 0.25, "persistence": 0.20}),
    threshold_attrs=_weighted({"future_pressure": 0.40, "fragility": 0.30, "acceleration": 0.20, "persistence": 0.10}),
    map_attrs=["future_pressure", "fragility", "acceleration", "persistence"],
    alert_threshold=0.93,
    scheduler_interval=45,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="volcanic_pressure",
    description=(
        "Analogous to magma chamber pressure — measures the buildup of suppressed "
        "force seeking release. Combines future pressure, high gravity and constrained "
        "acceleration to detect events that may erupt if pressure exceeds containment."
    ),
    score_attrs=_weighted({"future_pressure": 0.40, "future_gravity": 0.25, "acceleration": 0.20, "fragility": 0.15}),
    global_attrs=_weighted({"future_pressure": 0.35, "future_gravity": 0.25, "acceleration": 0.25, "fragility": 0.15}),
    threshold_attrs=_weighted({"future_pressure": 0.45, "future_gravity": 0.30, "acceleration": 0.15, "fragility": 0.10}),
    map_attrs=["future_pressure", "future_gravity", "acceleration", "fragility"],
    alert_threshold=0.94,
    scheduler_interval=45,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="tectonic_drift",
    description=(
        "Measures the slow, persistent movement of event relationships over time — "
        "the gradual reconfiguration of dependencies, gravities and relevance patterns "
        "that reshape the system's landscape on long timescales."
    ),
    score_attrs=_weighted({"persistence": 0.35, "dependencies_count": 0.25, "future_gravity": 0.25, "relevance": 0.15}),
    global_attrs=_weighted({"persistence": 0.30, "dependencies_count": 0.25, "future_gravity": 0.25, "relevance": 0.20}),
    threshold_attrs=_weighted({"persistence": 0.40, "dependencies_count": 0.30, "future_gravity": 0.20, "relevance": 0.10}),
    map_attrs=["persistence", "dependencies_count", "future_gravity", "relevance"],
    alert_threshold=0.85,
    scheduler_interval=180,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="climate_sensitivity",
    description=(
        "Measures how responsive the event system is to external forcing changes. "
        "A sensitive system shows large reactions (high acceleration, pressure shifts) "
        "to small changes in gravity or relevance — amplifying inputs."
    ),
    score_attrs=_weighted({"acceleration": 0.40, "future_pressure": 0.25, "fragility": 0.20, "future_gravity": 0.15}),
    global_attrs=_weighted({"acceleration": 0.35, "future_pressure": 0.25, "fragility": 0.25, "future_gravity": 0.15}),
    threshold_attrs=_weighted({"acceleration": 0.45, "future_pressure": 0.25, "fragility": 0.20, "future_gravity": 0.10}),
    map_attrs=["acceleration", "future_pressure", "fragility", "future_gravity"],
    alert_threshold=0.90,
    scheduler_interval=90,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="albedo_feedback",
    description=(
        "Positive and negative feedback loops — measures whether events amplify or "
        "dampen their own effects. Positive feedback (acceleration reinforcing pressure) "
        "leads to runaway change; negative feedback (recovery countering fragility) stabilizes."
    ),
    score_attrs=_weighted({"acceleration": 0.30, "future_pressure": 0.25, "recovery": 0.25, "fragility": 0.20}),
    global_attrs=_weighted({"acceleration": 0.25, "future_pressure": 0.25, "recovery": 0.25, "fragility": 0.25}),
    threshold_attrs=_weighted({"acceleration": 0.35, "future_pressure": 0.30, "recovery": 0.20, "fragility": 0.15}),
    map_attrs=["acceleration", "future_pressure", "recovery", "fragility"],
    alert_threshold=0.88,
    scheduler_interval=120,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="ocean_circulation",
    description=(
        "Analogous to thermohaline circulation — measures how influence circulates "
        "through the event system. Good circulation means gravity and pressure flow "
        "to all events efficiently; poor circulation creates stagnant dead zones."
    ),
    score_attrs=_weighted({"future_gravity": 0.30, "dependencies_count": 0.25, "future_pressure": 0.25, "redundancy": 0.20}),
    global_attrs=_weighted({"future_gravity": 0.30, "dependencies_count": 0.25, "future_pressure": 0.25, "redundancy": 0.20}),
    threshold_attrs=_weighted({"future_gravity": 0.35, "dependencies_count": 0.30, "future_pressure": 0.20, "redundancy": 0.15}),
    map_attrs=["future_gravity", "dependencies_count", "future_pressure", "redundancy"],
    alert_threshold=0.86,
    scheduler_interval=150,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="atmospheric_stability",
    description=(
        "Measures the stability of the event atmosphere — the ambient conditions within "
        "which events operate. Stable atmospheres have balanced pressure, moderate "
        "acceleration and adequate recovery; unstable ones have turbulent extremes."
    ),
    score_attrs=_weighted({"future_pressure": 0.25, "acceleration": 0.25, "recovery": 0.25, "fragility": 0.25}),
    global_attrs=_weighted({"future_pressure": 0.25, "acceleration": 0.25, "recovery": 0.25, "fragility": 0.25}),
    threshold_attrs=_weighted({"future_pressure": 0.30, "acceleration": 0.30, "recovery": 0.20, "fragility": 0.20}),
    map_attrs=["future_pressure", "acceleration", "recovery", "fragility"],
    alert_threshold=0.84,
    scheduler_interval=180,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="hydrological_cycle",
    description=(
        "Analogous to the water cycle — measures the cyclic flow of stress, recovery "
        "and pressure through the system. A healthy cycle has balanced evaporation "
        "(stress) and precipitation (recovery) without droughts or floods."
    ),
    score_attrs=_weighted({"future_pressure": 0.30, "recovery": 0.30, "persistence": 0.25, "redundancy": 0.15}),
    global_attrs=_weighted({"future_pressure": 0.30, "recovery": 0.30, "persistence": 0.25, "redundancy": 0.15}),
    threshold_attrs=_weighted({"future_pressure": 0.35, "recovery": 0.35, "persistence": 0.15, "redundancy": 0.15}),
    map_attrs=["future_pressure", "recovery", "persistence", "redundancy"],
    alert_threshold=0.83,
    scheduler_interval=150,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="erosion_rate",
    description=(
        "Measures how quickly event structures are worn down by continuous pressure — "
        "the gradual degradation of persistence, relevance and redundancy through "
        "persistent low-grade stress. Slow erosion is natural; rapid erosion signals decay."
    ),
    score_attrs=_weighted({"persistence": 0.30, "future_pressure": 0.25, "redundancy": 0.25, "relevance": 0.20}),
    global_attrs=_weighted({"persistence": 0.30, "future_pressure": 0.25, "redundancy": 0.25, "relevance": 0.20}),
    threshold_attrs=_weighted({"persistence": 0.35, "future_pressure": 0.30, "redundancy": 0.20, "relevance": 0.15}),
    map_attrs=["persistence", "future_pressure", "redundancy", "relevance"],
    alert_threshold=0.87,
    scheduler_interval=120,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="geothermal_gradient",
    description=(
        "Measures the internal heat of the system — the baseline energy available for "
        "driving change. Analogous to geothermal gradient: higher internal heat (pressure "
        "+ acceleration) means more potential for dramatic geological activity."
    ),
    score_attrs=_weighted({"future_pressure": 0.35, "acceleration": 0.30, "future_gravity": 0.20, "persistence": 0.15}),
    global_attrs=_weighted({"future_pressure": 0.30, "acceleration": 0.30, "future_gravity": 0.25, "persistence": 0.15}),
    threshold_attrs=_weighted({"future_pressure": 0.40, "acceleration": 0.35, "future_gravity": 0.15, "persistence": 0.10}),
    map_attrs=["future_pressure", "acceleration", "future_gravity", "persistence"],
    alert_threshold=0.89,
    scheduler_interval=90,
))


# ──────────────────────────────────────────────────────────────────────────────
# GROUP 7: Chemical Processes (061–070)
# Inspired by chemistry, material science and reaction dynamics.
# ──────────────────────────────────────────────────────────────────────────────

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="catalytic_activity",
    description=(
        "Identifies catalytic events — those that accelerate transformations across "
        "the system without being consumed themselves. High foresight, acceleration and "
        "relevance paired with high persistence characterize catalyst events."
    ),
    score_attrs=_weighted({"foresight": 0.30, "acceleration": 0.30, "relevance": 0.25, "persistence": 0.15}),
    global_attrs=_weighted({"foresight": 0.30, "acceleration": 0.25, "relevance": 0.25, "persistence": 0.20}),
    threshold_attrs=_weighted({"foresight": 0.35, "acceleration": 0.35, "relevance": 0.15, "persistence": 0.15}),
    map_attrs=["foresight", "acceleration", "relevance", "persistence"],
    alert_threshold=0.90,
    scheduler_interval=75,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="reaction_rate",
    description=(
        "Measures the speed at which events transform the system state. Combines "
        "acceleration, pressure and dependency density to quantify how quickly "
        "reactions propagate through the event network."
    ),
    score_attrs=_weighted({"acceleration": 0.40, "future_pressure": 0.30, "dependencies_count": 0.20, "relevance": 0.10}),
    global_attrs=_weighted({"acceleration": 0.35, "future_pressure": 0.30, "dependencies_count": 0.20, "relevance": 0.15}),
    threshold_attrs=_weighted({"acceleration": 0.45, "future_pressure": 0.35, "dependencies_count": 0.10, "relevance": 0.10}),
    map_attrs=["acceleration", "future_pressure", "dependencies_count", "relevance"],
    alert_threshold=0.92,
    scheduler_interval=60,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="bond_strength",
    description=(
        "Measures the strength of bonds between events — how tightly coupled they "
        "are through shared dependencies, mutual gravity and complementary pressures. "
        "Strong bonds resist separation; weak bonds allow rapid reconfiguration."
    ),
    score_attrs=_weighted({"dependencies_count": 0.35, "future_gravity": 0.30, "redundancy": 0.20, "persistence": 0.15}),
    global_attrs=_weighted({"dependencies_count": 0.30, "future_gravity": 0.30, "redundancy": 0.25, "persistence": 0.15}),
    threshold_attrs=_weighted({"dependencies_count": 0.40, "future_gravity": 0.35, "redundancy": 0.15, "persistence": 0.10}),
    map_attrs=["dependencies_count", "future_gravity", "redundancy", "persistence"],
    alert_threshold=0.88,
    scheduler_interval=120,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="crystallization",
    description=(
        "Detects the formation of stable, ordered structures from chaotic event soup — "
        "when persistence, gravity and relevance align to create rigid patterns. "
        "Crystallization can be productive (clear structure) or pathological (rigidity)."
    ),
    score_attrs=_weighted({"persistence": 0.35, "future_gravity": 0.30, "relevance": 0.25, "acceleration": 0.10}),
    global_attrs=_weighted({"persistence": 0.30, "future_gravity": 0.30, "relevance": 0.25, "acceleration": 0.15}),
    threshold_attrs=_weighted({"persistence": 0.40, "future_gravity": 0.35, "relevance": 0.15, "acceleration": 0.10}),
    map_attrs=["persistence", "future_gravity", "relevance", "acceleration"],
    alert_threshold=0.87,
    scheduler_interval=150,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="corrosion",
    description=(
        "Measures the progressive deterioration of event structures under sustained "
        "pressure — the chemical-like breakdown of persistence and redundancy when "
        "exposed to hostile (high-pressure, high-acid) environments."
    ),
    score_attrs=_weighted({"persistence": 0.30, "redundancy": 0.25, "future_pressure": 0.25, "fragility": 0.20}),
    global_attrs=_weighted({"persistence": 0.30, "redundancy": 0.25, "future_pressure": 0.25, "fragility": 0.20}),
    threshold_attrs=_weighted({"persistence": 0.35, "redundancy": 0.30, "future_pressure": 0.20, "fragility": 0.15}),
    map_attrs=["persistence", "redundancy", "future_pressure", "fragility"],
    alert_threshold=0.89,
    scheduler_interval=90,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="diffusion_rate",
    description=(
        "Measures how quickly influence (gravity, pressure, relevance) spreads from "
        "high-concentration events to low-concentration areas of the system. High "
        "diffusion creates homogeneity; low diffusion preserves diversity."
    ),
    score_attrs=_weighted({"future_gravity": 0.30, "future_pressure": 0.25, "dependencies_count": 0.25, "relevance": 0.20}),
    global_attrs=_weighted({"future_gravity": 0.30, "future_pressure": 0.25, "dependencies_count": 0.25, "relevance": 0.20}),
    threshold_attrs=_weighted({"future_gravity": 0.35, "future_pressure": 0.30, "dependencies_count": 0.20, "relevance": 0.15}),
    map_attrs=["future_gravity", "future_pressure", "dependencies_count", "relevance"],
    alert_threshold=0.85,
    scheduler_interval=120,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="activation_energy",
    description=(
        "Measures the energy barrier that must be overcome to trigger significant "
        "systemic change. High activation energy means the system is stable but may "
        "release explosive force once the barrier is crossed."
    ),
    score_attrs=_weighted({"future_pressure": 0.35, "persistence": 0.25, "fragility": 0.25, "acceleration": 0.15}),
    global_attrs=_weighted({"future_pressure": 0.30, "persistence": 0.25, "fragility": 0.25, "acceleration": 0.20}),
    threshold_attrs=_weighted({"future_pressure": 0.40, "persistence": 0.30, "fragility": 0.20, "acceleration": 0.10}),
    map_attrs=["future_pressure", "persistence", "fragility", "acceleration"],
    alert_threshold=0.93,
    scheduler_interval=60,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="equilibrium_constant",
    description=(
        "Measures the balance point of reversible processes in the system — the ratio "
        "of recovery to pressure forces. When this constant shifts, the system is "
        "undergoing fundamental rebalancing toward a new steady state."
    ),
    score_attrs=_weighted({"recovery": 0.40, "future_pressure": 0.35, "redundancy": 0.15, "fragility": 0.10}),
    global_attrs=_weighted({"recovery": 0.35, "future_pressure": 0.35, "redundancy": 0.15, "fragility": 0.15}),
    threshold_attrs=_weighted({"recovery": 0.40, "future_pressure": 0.40, "redundancy": 0.10, "fragility": 0.10}),
    map_attrs=["recovery", "future_pressure", "redundancy", "fragility"],
    alert_threshold=0.82,
    scheduler_interval=180,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="oxidation_state",
    description=(
        "Measures the degree to which events have lost their protective capacity — "
        "becoming more exposed, more fragile and less able to recover. Analogous to "
        "oxidation in chemistry: a one-way degradation requiring external energy to reverse."
    ),
    score_attrs=_weighted({"fragility": 0.40, "recovery": 0.25, "redundancy": 0.20, "future_pressure": 0.15}),
    global_attrs=_weighted({"fragility": 0.35, "recovery": 0.25, "redundancy": 0.25, "future_pressure": 0.15}),
    threshold_attrs=_weighted({"fragility": 0.45, "recovery": 0.25, "redundancy": 0.15, "future_pressure": 0.15}),
    map_attrs=["fragility", "recovery", "redundancy", "future_pressure"],
    alert_threshold=0.91,
    scheduler_interval=90,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="reduction_potential",
    description=(
        "The inverse of oxidation state — measures the system's capacity to be 'reduced' "
        "or healed. High reduction potential means strong recovery, good redundancy and "
        "balanced pressure create conditions favorable for restoration."
    ),
    score_attrs=_weighted({"recovery": 0.40, "redundancy": 0.30, "future_pressure": 0.15, "fragility": 0.15}),
    global_attrs=_weighted({"recovery": 0.35, "redundancy": 0.30, "future_pressure": 0.20, "fragility": 0.15}),
    threshold_attrs=_weighted({"recovery": 0.45, "redundancy": 0.35, "future_pressure": 0.10, "fragility": 0.10}),
    map_attrs=["recovery", "redundancy", "future_pressure", "fragility"],
    alert_threshold=0.76,
    scheduler_interval=120,
))


# ──────────────────────────────────────────────────────────────────────────────
# GROUP 8: Information Theory (071–080)
# Inspired by information theory, computation and signal processing.
# ──────────────────────────────────────────────────────────────────────────────

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="information_density",
    description=(
        "Measures how much actionable information is concentrated in each event. "
        "High information density events combine high relevance, strong foresight and "
        "significant gravity — they are information-rich nodes in the network."
    ),
    score_attrs=_weighted({"relevance": 0.30, "foresight": 0.30, "future_gravity": 0.25, "persistence": 0.15}),
    global_attrs=_weighted({"relevance": 0.30, "foresight": 0.25, "future_gravity": 0.25, "persistence": 0.20}),
    threshold_attrs=_weighted({"relevance": 0.35, "foresight": 0.30, "future_gravity": 0.20, "persistence": 0.15}),
    map_attrs=["relevance", "foresight", "future_gravity", "persistence"],
    alert_threshold=0.87,
    scheduler_interval=90,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="signal_to_noise",
    description=(
        "Measures the clarity of the event signal against background system noise. "
        "High S/N means the event's relevance and gravity stand out clearly from "
        "random fluctuations in pressure and fragility."
    ),
    score_attrs=_weighted({"relevance": 0.35, "future_gravity": 0.30, "future_pressure": 0.15, "fragility": 0.20}),
    global_attrs=_weighted({"relevance": 0.30, "future_gravity": 0.30, "future_pressure": 0.15, "fragility": 0.25}),
    threshold_attrs=_weighted({"relevance": 0.40, "future_gravity": 0.35, "future_pressure": 0.10, "fragility": 0.15}),
    map_attrs=["relevance", "future_gravity", "future_pressure", "fragility"],
    alert_threshold=0.85,
    scheduler_interval=120,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="bandwidth",
    description=(
        "Measures the system's information throughput capacity — how much change (in "
        "pressure, gravity, relevance) the system can process per unit time without "
        "saturation. Bandwidth constrains all other dynamic processes."
    ),
    score_attrs=_weighted({"acceleration": 0.30, "dependencies_count": 0.25, "future_pressure": 0.25, "redundancy": 0.20}),
    global_attrs=_weighted({"acceleration": 0.30, "dependencies_count": 0.25, "future_pressure": 0.25, "redundancy": 0.20}),
    threshold_attrs=_weighted({"acceleration": 0.35, "dependencies_count": 0.30, "future_pressure": 0.20, "redundancy": 0.15}),
    map_attrs=["acceleration", "dependencies_count", "future_pressure", "redundancy"],
    alert_threshold=0.88,
    scheduler_interval=90,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="compression_ratio",
    description=(
        "Measures how efficiently the event system compresses complexity — the ratio "
        "of total system entropy to the information actually needed for decision-making. "
        "High compression means the system discards noise and retains signal."
    ),
    score_attrs=_weighted({"relevance": 0.30, "foresight": 0.25, "redundancy": 0.25, "fragility": 0.20}),
    global_attrs=_weighted({"relevance": 0.30, "foresight": 0.25, "redundancy": 0.25, "fragility": 0.20}),
    threshold_attrs=_weighted({"relevance": 0.35, "foresight": 0.30, "redundancy": 0.20, "fragility": 0.15}),
    map_attrs=["relevance", "foresight", "redundancy", "fragility"],
    alert_threshold=0.82,
    scheduler_interval=150,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="error_rate",
    description=(
        "Measures the frequency of prediction failures, recovery breakdowns and "
        "mismatches between foresight and actual outcomes. High error rates indicate "
        "the system's internal model does not match reality."
    ),
    score_attrs=_weighted({"fragility": 0.30, "foresight": 0.30, "recovery": 0.20, "future_pressure": 0.20}),
    global_attrs=_weighted({"fragility": 0.30, "foresight": 0.25, "recovery": 0.25, "future_pressure": 0.20}),
    threshold_attrs=_weighted({"fragility": 0.35, "foresight": 0.30, "recovery": 0.20, "future_pressure": 0.15}),
    map_attrs=["fragility", "foresight", "recovery", "future_pressure"],
    alert_threshold=0.91,
    scheduler_interval=60,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="channel_capacity",
    description=(
        "Shannon-inspired channel capacity — the maximum rate at which meaningful "
        "information can flow through the event dependency network. Channel capacity "
        "limits how quickly the system can learn and adapt."
    ),
    score_attrs=_weighted({"dependencies_count": 0.30, "redundancy": 0.25, "relevance": 0.25, "foresight": 0.20}),
    global_attrs=_weighted({"dependencies_count": 0.30, "redundancy": 0.25, "relevance": 0.25, "foresight": 0.20}),
    threshold_attrs=_weighted({"dependencies_count": 0.35, "redundancy": 0.30, "relevance": 0.20, "foresight": 0.15}),
    map_attrs=["dependencies_count", "redundancy", "relevance", "foresight"],
    alert_threshold=0.86,
    scheduler_interval=120,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="encoding_efficiency",
    description=(
        "Measures how efficiently event states are encoded in the system's memory. "
        "Efficient encoding means relevant, persistent events are well-represented "
        "without wasting capacity on noise or redundancy."
    ),
    score_attrs=_weighted({"relevance": 0.30, "persistence": 0.30, "redundancy": 0.25, "foresight": 0.15}),
    global_attrs=_weighted({"relevance": 0.30, "persistence": 0.25, "redundancy": 0.25, "foresight": 0.20}),
    threshold_attrs=_weighted({"relevance": 0.35, "persistence": 0.30, "redundancy": 0.20, "foresight": 0.15}),
    map_attrs=["relevance", "persistence", "redundancy", "foresight"],
    alert_threshold=0.83,
    scheduler_interval=150,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="latency",
    description=(
        "Measures the delay between cause and effect in the event system — how long "
        "it takes for a pressure change at one event to propagate to dependent events. "
        "Low latency means rapid response; high latency means sluggish adaptation."
    ),
    score_attrs=_weighted({"persistence": 0.30, "dependencies_count": 0.25, "acceleration": 0.25, "recovery": 0.20}),
    global_attrs=_weighted({"persistence": 0.30, "dependencies_count": 0.25, "acceleration": 0.25, "recovery": 0.20}),
    threshold_attrs=_weighted({"persistence": 0.35, "dependencies_count": 0.30, "acceleration": 0.20, "recovery": 0.15}),
    map_attrs=["persistence", "dependencies_count", "acceleration", "recovery"],
    alert_threshold=0.88,
    scheduler_interval=90,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="redundancy_ratio",
    description=(
        "Measures the intentional redundancy built into the event system as a fraction "
        "of total system complexity. The redundancy ratio indicates how much spare "
        "capacity exists to absorb failures without total system collapse."
    ),
    score_attrs=_weighted({"redundancy": 0.50, "dependencies_count": 0.20, "recovery": 0.20, "fragility": 0.10}),
    global_attrs=_weighted({"redundancy": 0.45, "dependencies_count": 0.20, "recovery": 0.20, "fragility": 0.15}),
    threshold_attrs=_weighted({"redundancy": 0.55, "dependencies_count": 0.20, "recovery": 0.15, "fragility": 0.10}),
    map_attrs=["redundancy", "dependencies_count", "recovery", "fragility"],
    alert_threshold=0.75,
    scheduler_interval=180,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="hash_collision",
    description=(
        "Detects events that appear different but have functionally identical attribute "
        "profiles — hash collisions where distinct events occupy the same diagnostic "
        "signature. Collisions waste resources and may hide true diversity."
    ),
    score_attrs=_even_weights(["persistence", "relevance", "foresight", "future_gravity", "fragility",
                                "future_pressure", "acceleration", "dependencies_count", "recovery", "redundancy"]),
    global_attrs=_even_weights(["persistence", "relevance", "foresight", "future_gravity", "fragility",
                                 "future_pressure", "acceleration", "dependencies_count", "recovery", "redundancy"]),
    threshold_attrs=_even_weights(["persistence", "relevance", "foresight", "future_gravity", "fragility",
                                    "future_pressure", "acceleration", "dependencies_count", "recovery", "redundancy"]),
    map_attrs=["persistence", "relevance", "foresight", "future_gravity"],
    alert_threshold=0.80,
    scheduler_interval=120,
))


# ──────────────────────────────────────────────────────────────────────────────
# GROUP 9: Systemic Health (081–090)
# Core diagnostic families that measure overall system condition.
# ──────────────────────────────────────────────────────────────────────────────

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="stability",
    description=(
        "Core stability metric — measures the overall steadiness of the event system. "
        "A stable system resists perturbations, maintains consistent attribute profiles "
        "and recovers quickly from disturbances. Combines persistence, recovery and redundancy."
    ),
    score_attrs=_weighted({"persistence": 0.30, "recovery": 0.30, "redundancy": 0.25, "fragility": 0.15}),
    global_attrs=_weighted({"persistence": 0.30, "recovery": 0.30, "redundancy": 0.25, "fragility": 0.15}),
    threshold_attrs=_weighted({"persistence": 0.35, "recovery": 0.30, "redundancy": 0.20, "fragility": 0.15}),
    map_attrs=["persistence", "recovery", "redundancy", "fragility"],
    alert_threshold=0.85,
    scheduler_interval=120,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="adaptation",
    description=(
        "Core adaptation metric — measures the system's capacity to adjust to changing "
        "conditions. High adaptation combines strong foresight with balanced acceleration "
        "and recovery, enabling the system to evolve rather than break under pressure."
    ),
    score_attrs=_weighted({"foresight": 0.30, "recovery": 0.25, "acceleration": 0.25, "redundancy": 0.20}),
    global_attrs=_weighted({"foresight": 0.30, "recovery": 0.25, "acceleration": 0.25, "redundancy": 0.20}),
    threshold_attrs=_weighted({"foresight": 0.35, "recovery": 0.25, "acceleration": 0.25, "redundancy": 0.15}),
    map_attrs=["foresight", "recovery", "acceleration", "redundancy"],
    alert_threshold=0.84,
    scheduler_interval=120,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="master",
    description=(
        "Master score combining all available attributes into a single holistic assessment. "
        "This is the primary diagnostic lens — it captures the total planetary condition "
        "by weighting each attribute evenly. Used as the default reference score."
    ),
    score_attrs=_even_weights(_ALL_ATTRS),
    global_attrs=_even_weights(_ALL_ATTRS),
    threshold_attrs=_even_weights(_ALL_ATTRS),
    map_attrs=["future_gravity", "future_pressure", "fragility", "recovery"],
    alert_threshold=0.95,
    scheduler_interval=30,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="overstress",
    description=(
        "Detects planetary overstress conditions — when multiple stress indicators "
        "(pressure, fragility, acceleration) simultaneously exceed sustainable levels. "
        "Overstress is the precursor to system breakdown and requires immediate attention."
    ),
    score_attrs=_weighted({"future_pressure": 0.35, "fragility": 0.30, "acceleration": 0.25, "dependencies_count": 0.10}),
    global_attrs=_weighted({"future_pressure": 0.30, "fragility": 0.30, "acceleration": 0.25, "dependencies_count": 0.15}),
    threshold_attrs=_weighted({"future_pressure": 0.40, "fragility": 0.35, "acceleration": 0.20, "dependencies_count": 0.05}),
    map_attrs=["future_pressure", "fragility", "acceleration", "dependencies_count"],
    alert_threshold=0.96,
    scheduler_interval=15,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="saturation",
    description=(
        "Detects saturation conditions where the system has reached maximum capacity — "
        "no additional events, pressure or gravity can be absorbed. Saturation leads to "
        "rejection of new inputs and eventual overflow failures."
    ),
    score_attrs=_weighted({"dependencies_count": 0.30, "future_pressure": 0.30, "persistence": 0.20, "redundancy": 0.20}),
    global_attrs=_weighted({"dependencies_count": 0.30, "future_pressure": 0.30, "persistence": 0.25, "redundancy": 0.15}),
    threshold_attrs=_weighted({"dependencies_count": 0.35, "future_pressure": 0.35, "persistence": 0.15, "redundancy": 0.15}),
    map_attrs=["dependencies_count", "future_pressure", "persistence", "redundancy"],
    alert_threshold=0.95,
    scheduler_interval=30,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="instability",
    description=(
        "Detects emerging instability — the condition where small perturbations grow "
        "into large deviations. Combines high fragility, low recovery, accelerating "
        "change and diverging pressure to flag events at risk of unstable dynamics."
    ),
    score_attrs=_weighted({"fragility": 0.35, "acceleration": 0.30, "recovery": 0.15, "future_pressure": 0.20}),
    global_attrs=_weighted({"fragility": 0.30, "acceleration": 0.30, "recovery": 0.20, "future_pressure": 0.20}),
    threshold_attrs=_weighted({"fragility": 0.40, "acceleration": 0.35, "recovery": 0.10, "future_pressure": 0.15}),
    map_attrs=["fragility", "acceleration", "recovery", "future_pressure"],
    alert_threshold=0.94,
    scheduler_interval=30,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="resilience",
    description=(
        "Core resilience metric — measures the system's capacity to absorb disturbance "
        "and reorganize while undergoing change so as to retain essentially the same "
        "function, structure and feedbacks. Resilience combines recovery, redundancy and foresight."
    ),
    score_attrs=_weighted({"recovery": 0.35, "redundancy": 0.30, "foresight": 0.20, "persistence": 0.15}),
    global_attrs=_weighted({"recovery": 0.35, "redundancy": 0.30, "foresight": 0.20, "persistence": 0.15}),
    threshold_attrs=_weighted({"recovery": 0.40, "redundancy": 0.30, "foresight": 0.20, "persistence": 0.10}),
    map_attrs=["recovery", "redundancy", "foresight", "persistence"],
    alert_threshold=0.78,
    scheduler_interval=120,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="fragility",
    description=(
        "Core fragility metric — measures the exposed vulnerability of the system to "
        "sudden collapse. Fragile systems have high pressure, low recovery, low redundancy "
        "and high sensitivity to perturbation across their critical events."
    ),
    score_attrs=_weighted({"fragility": 0.40, "future_pressure": 0.25, "recovery": 0.15, "redundancy": 0.20}),
    global_attrs=_weighted({"fragility": 0.35, "future_pressure": 0.25, "recovery": 0.20, "redundancy": 0.20}),
    threshold_attrs=_weighted({"fragility": 0.45, "future_pressure": 0.30, "recovery": 0.10, "redundancy": 0.15}),
    map_attrs=["fragility", "future_pressure", "recovery", "redundancy"],
    alert_threshold=0.92,
    scheduler_interval=60,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="capacity",
    description=(
        "Core capacity metric — measures the residual headroom available in the system. "
        "High capacity means the system can absorb more pressure, more events and more "
        "gravity before reaching limits. Capacity is the complement of saturation."
    ),
    score_attrs=_weighted({"redundancy": 0.35, "recovery": 0.30, "persistence": 0.20, "dependencies_count": 0.15}),
    global_attrs=_weighted({"redundancy": 0.30, "recovery": 0.30, "persistence": 0.25, "dependencies_count": 0.15}),
    threshold_attrs=_weighted({"redundancy": 0.40, "recovery": 0.30, "persistence": 0.15, "dependencies_count": 0.15}),
    map_attrs=["redundancy", "recovery", "persistence", "dependencies_count"],
    alert_threshold=0.72,
    scheduler_interval=180,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="cohesion",
    description=(
        "Measures the binding force that holds the event system together — the mutual "
        "attraction between events through gravity, dependencies and shared relevance. "
        "Cohesive systems resist fragmentation but may resist necessary reconfiguration."
    ),
    score_attrs=_weighted({"future_gravity": 0.30, "dependencies_count": 0.25, "relevance": 0.25, "persistence": 0.20}),
    global_attrs=_weighted({"future_gravity": 0.30, "dependencies_count": 0.25, "relevance": 0.25, "persistence": 0.20}),
    threshold_attrs=_weighted({"future_gravity": 0.35, "dependencies_count": 0.30, "relevance": 0.20, "persistence": 0.15}),
    map_attrs=["future_gravity", "dependencies_count", "relevance", "persistence"],
    alert_threshold=0.84,
    scheduler_interval=120,
))


# ──────────────────────────────────────────────────────────────────────────────
# GROUP 10: Advanced Meta (091–100)
# Cross-cutting meta-diagnostic families for emergent phenomena.
# ──────────────────────────────────────────────────────────────────────────────

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="criticality",
    description=(
        "Detects whether the system is operating near a critical point — the boundary "
        "between order and chaos where power laws govern behavior. Near-critical systems "
        "show heavy-tailed event distributions and extreme sensitivity to perturbation."
    ),
    score_attrs=_weighted({"future_gravity": 0.30, "future_pressure": 0.25, "fragility": 0.25, "acceleration": 0.20}),
    global_attrs=_weighted({"future_gravity": 0.30, "future_pressure": 0.25, "fragility": 0.25, "acceleration": 0.20}),
    threshold_attrs=_weighted({"future_gravity": 0.35, "future_pressure": 0.30, "fragility": 0.20, "acceleration": 0.15}),
    map_attrs=["future_gravity", "future_pressure", "fragility", "acceleration"],
    alert_threshold=0.94,
    scheduler_interval=45,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="cascade_risk",
    description=(
        "Quantifies the probability and potential magnitude of cascading failures — "
        "where one event's collapse triggers a chain reaction through the dependency "
        "network. Cascade risk is the product of connectivity, gravity and fragility."
    ),
    score_attrs=_weighted({"dependencies_count": 0.35, "future_gravity": 0.30, "fragility": 0.20, "future_pressure": 0.15}),
    global_attrs=_weighted({"dependencies_count": 0.30, "future_gravity": 0.30, "fragility": 0.25, "future_pressure": 0.15}),
    threshold_attrs=_weighted({"dependencies_count": 0.40, "future_gravity": 0.35, "fragility": 0.15, "future_pressure": 0.10}),
    map_attrs=["dependencies_count", "future_gravity", "fragility", "future_pressure"],
    alert_threshold=0.96,
    scheduler_interval=30,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="path_dependency",
    description=(
        "Measures how strongly the system's current state is constrained by its history. "
        "High path dependency means past events (through persistence and accumulated "
        "gravity) lock the system into trajectories that are hard to change."
    ),
    score_attrs=_weighted({"persistence": 0.40, "future_gravity": 0.25, "dependencies_count": 0.20, "relevance": 0.15}),
    global_attrs=_weighted({"persistence": 0.35, "future_gravity": 0.25, "dependencies_count": 0.25, "relevance": 0.15}),
    threshold_attrs=_weighted({"persistence": 0.45, "future_gravity": 0.30, "dependencies_count": 0.15, "relevance": 0.10}),
    map_attrs=["persistence", "future_gravity", "dependencies_count", "relevance"],
    alert_threshold=0.90,
    scheduler_interval=120,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="lock_in",
    description=(
        "Detects technological or structural lock-in — when the system becomes trapped "
        "in a suboptimal configuration due to high switching costs encoded in persistence, "
        "dependency networks and accumulated gravity. Lock-in prevents innovation."
    ),
    score_attrs=_weighted({"persistence": 0.35, "dependencies_count": 0.30, "future_gravity": 0.20, "redundancy": 0.15}),
    global_attrs=_weighted({"persistence": 0.30, "dependencies_count": 0.30, "future_gravity": 0.25, "redundancy": 0.15}),
    threshold_attrs=_weighted({"persistence": 0.40, "dependencies_count": 0.35, "future_gravity": 0.15, "redundancy": 0.10}),
    map_attrs=["persistence", "dependencies_count", "future_gravity", "redundancy"],
    alert_threshold=0.91,
    scheduler_interval=120,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="brittleness",
    description=(
        "Measures the system's brittleness — the opposite of resilience. Brittle systems "
        "appear strong under normal conditions (high persistence, high gravity) but shatter "
        "rather than bend when stressed. Detects the illusion of strength."
    ),
    score_attrs=_weighted({"persistence": 0.30, "future_gravity": 0.25, "fragility": 0.30, "recovery": 0.15}),
    global_attrs=_weighted({"persistence": 0.30, "future_gravity": 0.25, "fragility": 0.30, "recovery": 0.15}),
    threshold_attrs=_weighted({"persistence": 0.35, "future_gravity": 0.25, "fragility": 0.30, "recovery": 0.10}),
    map_attrs=["persistence", "future_gravity", "fragility", "recovery"],
    alert_threshold=0.93,
    scheduler_interval=60,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="anticipation",
    description=(
        "Measures the system's capacity to anticipate future conditions through foresight "
        "and prepare appropriate responses. High anticipation combines strong foresight with "
        "balanced preparation (recovery, redundancy) rather than reactive pressure buildup."
    ),
    score_attrs=_weighted({"foresight": 0.40, "recovery": 0.25, "redundancy": 0.20, "future_pressure": 0.15}),
    global_attrs=_weighted({"foresight": 0.35, "recovery": 0.25, "redundancy": 0.20, "future_pressure": 0.20}),
    threshold_attrs=_weighted({"foresight": 0.45, "recovery": 0.25, "redundancy": 0.15, "future_pressure": 0.15}),
    map_attrs=["foresight", "recovery", "redundancy", "future_pressure"],
    alert_threshold=0.86,
    scheduler_interval=90,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="tension",
    description=(
        "Measures the accumulated unresolved tension in the event system — the productive "
        "or destructive stress that builds when opposing forces (pressure vs recovery, "
        "gravity vs fragility) are in sustained conflict without resolution."
    ),
    score_attrs=_weighted({"future_pressure": 0.30, "fragility": 0.25, "recovery": 0.25, "future_gravity": 0.20}),
    global_attrs=_weighted({"future_pressure": 0.30, "fragility": 0.25, "recovery": 0.25, "future_gravity": 0.20}),
    threshold_attrs=_weighted({"future_pressure": 0.35, "fragility": 0.30, "recovery": 0.20, "future_gravity": 0.15}),
    map_attrs=["future_pressure", "fragility", "recovery", "future_gravity"],
    alert_threshold=0.90,
    scheduler_interval=75,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="anticipatory_failure",
    description=(
        "Detects failures that occur precisely because the system anticipated and "
        "over-prepared for the wrong threat. High foresight combined with mismatched "
        "recovery and misaligned pressure indicates preparation for the wrong future."
    ),
    score_attrs=_weighted({"foresight": 0.35, "recovery": 0.25, "future_pressure": 0.25, "fragility": 0.15}),
    global_attrs=_weighted({"foresight": 0.30, "recovery": 0.25, "future_pressure": 0.25, "fragility": 0.20}),
    threshold_attrs=_weighted({"foresight": 0.40, "recovery": 0.25, "future_pressure": 0.20, "fragility": 0.15}),
    map_attrs=["foresight", "recovery", "future_pressure", "fragility"],
    alert_threshold=0.89,
    scheduler_interval=90,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="emergent_behavior",
    description=(
        "Detects emergent collective behaviors — patterns that arise from event interactions "
        "but are not predictable from individual event attributes. Emergence is signaled "
        "by unusual correlations between gravity, dependency structure and system-wide pressure."
    ),
    score_attrs=_weighted({"future_gravity": 0.25, "dependencies_count": 0.25, "future_pressure": 0.25, "acceleration": 0.25}),
    global_attrs=_weighted({"future_gravity": 0.25, "dependencies_count": 0.25, "future_pressure": 0.25, "acceleration": 0.25}),
    threshold_attrs=_weighted({"future_gravity": 0.30, "dependencies_count": 0.30, "future_pressure": 0.25, "acceleration": 0.15}),
    map_attrs=["future_gravity", "dependencies_count", "future_pressure", "acceleration"],
    alert_threshold=0.88,
    scheduler_interval=60,
))

PLANETARY_CONFIGS.append(PlanetaryConfig(
    name="tipping_point",
    description=(
        "Detects proximity to a tipping point — the critical threshold at which a small "
        "additional perturbation triggers a large, irreversible state change. Tipping points "
        "are characterized by rising pressure, declining recovery and accelerating change."
    ),
    score_attrs=_weighted({"future_pressure": 0.35, "recovery": 0.20, "acceleration": 0.30, "fragility": 0.15}),
    global_attrs=_weighted({"future_pressure": 0.30, "recovery": 0.20, "acceleration": 0.30, "fragility": 0.20}),
    threshold_attrs=_weighted({"future_pressure": 0.40, "recovery": 0.15, "acceleration": 0.35, "fragility": 0.10}),
    map_attrs=["future_pressure", "recovery", "acceleration", "fragility"],
    alert_threshold=0.97,
    scheduler_interval=15,
))


# ═══════════════════════════════════════════════════════════════════════════════
# VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

def validate_configs(configs: List[PlanetaryConfig]) -> None:
    """
    Validate that all configurations meet structural requirements.

    Checks:
        - Exactly 100 configurations exist.
        - All names are unique.
        - All weight dictionaries sum to approximately 1.0 (within 1%).
        - All map_attrs have exactly 4 elements.
        - All referenced attributes exist in the event schema.
    """
    assert len(configs) == 100, f"Expected 100 configs, got {len(configs)}"

    names = [c.name for c in configs]
    assert len(names) == len(set(names)), f"Duplicate names found: {[n for n in names if names.count(n) > 1]}"

    valid_attrs = set(_ALL_ATTRS)
    for cfg in configs:
        for dname, d in [("score_attrs", cfg.score_attrs),
                         ("global_attrs", cfg.global_attrs),
                         ("threshold_attrs", cfg.threshold_attrs)]:
            total = sum(d.values())
            assert 0.99 <= total <= 1.01, (
                f"{cfg.name}.{dname} sums to {total:.4f}, expected ~1.0"
            )
            for attr in d:
                assert attr in valid_attrs, (
                    f"{cfg.name}.{dname} has invalid attr: {attr}"
                )

        assert len(cfg.map_attrs) == 4, (
            f"{cfg.name}.map_attrs has {len(cfg.map_attrs)} elements, expected 4"
        )
        for attr in cfg.map_attrs:
            assert attr in valid_attrs, (
                f"{cfg.name}.map_attrs has invalid attr: {attr}"
            )


# Run validation on import
validate_configs(PLANETARY_CONFIGS)

# Make the list available as a lookup by name
PLANETARY_CONFIG_MAP: Dict[str, PlanetaryConfig] = {
    cfg.name: cfg for cfg in PLANETARY_CONFIGS
}

__all__ = [
    "PlanetaryConfig",
    "PLANETARY_CONFIGS",
    "PLANETARY_CONFIG_MAP",
    "validate_configs",
]
