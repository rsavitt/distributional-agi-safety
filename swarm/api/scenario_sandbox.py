"""Scenario validation and sandboxing for externally submitted YAML configs.

Provides resource limits, validation, and sanitization to prevent abuse
when accepting scenario configurations from untrusted sources.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field


class ScenarioLimits(BaseModel):
    """Resource limits for scenario validation."""

    max_epochs: int = 200
    max_steps_per_epoch: int = 50
    max_agents: int = 50
    max_agent_types: Dict[str, int] = Field(
        default_factory=lambda: {
            "adversarial": 10,
            "adaptive_adversary": 5,
        }
    )
    allowed_agent_types: List[str] = Field(
        default_factory=lambda: [
            "honest",
            "opportunistic",
            "deceptive",
            "adversarial",
            "adaptive_adversary",
        ]
    )
    max_yaml_size_bytes: int = 65536  # 64 KB
    max_observation_noise_std: float = 1.0


class ScenarioValidationError(Exception):
    """Raised when a scenario fails validation.

    Attributes:
        errors: List of all validation violations found.
    """

    def __init__(self, errors: List[str]) -> None:
        self.errors = errors
        super().__init__(f"Scenario validation failed with {len(errors)} error(s): {'; '.join(errors)}")


def validate_scenario_yaml(
    yaml_content: str,
    limits: Optional[ScenarioLimits] = None,
) -> dict:
    """Validate a YAML scenario string against resource limits.

    Parses the YAML content and checks all fields against the provided
    limits. Collects *all* violations before raising, so callers get a
    complete picture of what needs to change.

    Args:
        yaml_content: Raw YAML string to validate.
        limits: Resource limits to enforce. Uses defaults if None.

    Returns:
        The parsed YAML dict on success.

    Raises:
        ScenarioValidationError: If one or more limits are exceeded.
            The ``errors`` attribute contains every violation found.
    """
    if limits is None:
        limits = ScenarioLimits()

    errors: List[str] = []

    # --- Size check (before parsing) ---
    content_size = len(yaml_content.encode("utf-8"))
    if content_size > limits.max_yaml_size_bytes:
        errors.append(
            f"YAML content size ({content_size} bytes) exceeds maximum "
            f"({limits.max_yaml_size_bytes} bytes)"
        )

    # --- Parse ---
    try:
        data = yaml.safe_load(yaml_content)
    except yaml.YAMLError as exc:
        raise ScenarioValidationError([f"Invalid YAML: {exc}"]) from exc

    if not isinstance(data, dict):
        raise ScenarioValidationError(["YAML content must be a mapping (dict), got " + type(data).__name__])

    # --- Simulation limits ---
    sim = data.get("simulation", {}) or {}

    n_epochs = sim.get("n_epochs")
    if n_epochs is not None and n_epochs > limits.max_epochs:
        errors.append(
            f"n_epochs ({n_epochs}) exceeds maximum ({limits.max_epochs})"
        )

    steps_per_epoch = sim.get("steps_per_epoch")
    if steps_per_epoch is not None and steps_per_epoch > limits.max_steps_per_epoch:
        errors.append(
            f"steps_per_epoch ({steps_per_epoch}) exceeds maximum ({limits.max_steps_per_epoch})"
        )

    observation_noise_std = sim.get("observation_noise_std")
    if observation_noise_std is not None and observation_noise_std > limits.max_observation_noise_std:
        errors.append(
            f"observation_noise_std ({observation_noise_std}) exceeds maximum "
            f"({limits.max_observation_noise_std})"
        )

    # --- Agent limits ---
    agents: List[Dict[str, Any]] = data.get("agents", []) or []

    total_agents = 0
    type_counts: Dict[str, int] = {}

    for spec in agents:
        agent_type = spec.get("type", "honest")
        count = spec.get("count", 1)
        total_agents += count
        type_counts[agent_type] = type_counts.get(agent_type, 0) + count

        if agent_type not in limits.allowed_agent_types:
            errors.append(f"Agent type '{agent_type}' is not allowed")

    if total_agents > limits.max_agents:
        errors.append(
            f"Total agent count ({total_agents}) exceeds maximum ({limits.max_agents})"
        )

    for agent_type, count in type_counts.items():
        if agent_type in limits.max_agent_types:
            max_count = limits.max_agent_types[agent_type]
            if count > max_count:
                errors.append(
                    f"Agent type '{agent_type}' count ({count}) exceeds "
                    f"maximum ({max_count})"
                )

    if errors:
        raise ScenarioValidationError(errors)

    return data


def sanitize_scenario(
    data: dict,
    limits: Optional[ScenarioLimits] = None,
) -> dict:
    """Sanitize a parsed scenario dict by clamping values to limits.

    Unlike :func:`validate_scenario_yaml`, this function silently adjusts
    values instead of raising errors. Useful when you want a best-effort
    scenario rather than strict rejection.

    Args:
        data: Parsed YAML dict (e.g. from ``yaml.safe_load``).
        limits: Resource limits to enforce. Uses defaults if None.

    Returns:
        A new dict with values clamped to the given limits.
    """
    if limits is None:
        limits = ScenarioLimits()

    result = copy.deepcopy(data)

    # --- Clamp simulation parameters ---
    sim = result.get("simulation")
    if isinstance(sim, dict):
        if "n_epochs" in sim:
            sim["n_epochs"] = min(sim["n_epochs"], limits.max_epochs)
        if "steps_per_epoch" in sim:
            sim["steps_per_epoch"] = min(sim["steps_per_epoch"], limits.max_steps_per_epoch)
        if "observation_noise_std" in sim:
            sim["observation_noise_std"] = min(
                sim["observation_noise_std"], limits.max_observation_noise_std
            )

    # --- Filter and clamp agents ---
    agents: List[Dict[str, Any]] = result.get("agents", []) or []
    sanitized_agents: List[Dict[str, Any]] = []

    for spec in agents:
        agent_type = spec.get("type", "honest")

        # Remove disallowed agent types entirely
        if agent_type not in limits.allowed_agent_types:
            continue

        spec = copy.deepcopy(spec)

        # Clamp per-type count
        if agent_type in limits.max_agent_types:
            max_type_count = limits.max_agent_types[agent_type]
            count = spec.get("count", 1)
            spec["count"] = min(count, max_type_count)

        sanitized_agents.append(spec)

    # Clamp total agent count by proportionally reducing if needed
    total = sum(s.get("count", 1) for s in sanitized_agents)
    if total > limits.max_agents and sanitized_agents:
        # Reduce counts proportionally, rounding down
        scale = limits.max_agents / total
        for spec in sanitized_agents:
            spec["count"] = max(1, int(spec.get("count", 1) * scale))

    result["agents"] = sanitized_agents

    return result
