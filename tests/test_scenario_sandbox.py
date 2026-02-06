"""Tests for scenario validation and sandboxing."""

import textwrap

import pytest

from swarm.api.scenario_sandbox import (
    ScenarioLimits,
    ScenarioValidationError,
    sanitize_scenario,
    validate_scenario_yaml,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_YAML = textwrap.dedent("""\
    scenario_id: test_scenario
    description: "A valid test scenario"

    simulation:
      n_epochs: 10
      steps_per_epoch: 10
      seed: 42
      observation_noise_std: 0.1

    agents:
      - type: honest
        count: 3
      - type: opportunistic
        count: 1
      - type: deceptive
        count: 1

    governance:
      transaction_tax_rate: 0.0

    payoff:
      s_plus: 2.0
""")


# ---------------------------------------------------------------------------
# ScenarioLimits defaults
# ---------------------------------------------------------------------------

class TestScenarioLimits:
    def test_defaults(self):
        limits = ScenarioLimits()
        assert limits.max_epochs == 200
        assert limits.max_steps_per_epoch == 50
        assert limits.max_agents == 50
        assert limits.max_yaml_size_bytes == 65536
        assert limits.max_observation_noise_std == 1.0
        assert "honest" in limits.allowed_agent_types
        assert "adversarial" in limits.allowed_agent_types
        assert limits.max_agent_types["adversarial"] == 10
        assert limits.max_agent_types["adaptive_adversary"] == 5

    def test_custom_limits(self):
        limits = ScenarioLimits(max_epochs=50, max_agents=10)
        assert limits.max_epochs == 50
        assert limits.max_agents == 10


# ---------------------------------------------------------------------------
# validate_scenario_yaml -- happy path
# ---------------------------------------------------------------------------

class TestValidateHappyPath:
    def test_valid_scenario_passes(self):
        data = validate_scenario_yaml(VALID_YAML)
        assert data["scenario_id"] == "test_scenario"
        assert data["simulation"]["n_epochs"] == 10

    def test_valid_at_exact_limits(self):
        """Values exactly at limits should pass."""
        limits = ScenarioLimits(max_epochs=10, max_steps_per_epoch=10, max_agents=5)
        data = validate_scenario_yaml(VALID_YAML, limits=limits)
        assert data["simulation"]["n_epochs"] == 10

    def test_minimal_yaml(self):
        """A near-empty YAML mapping should validate (no agents, no sim)."""
        data = validate_scenario_yaml("scenario_id: minimal\n")
        assert data["scenario_id"] == "minimal"


# ---------------------------------------------------------------------------
# validate_scenario_yaml -- rejection cases
# ---------------------------------------------------------------------------

class TestValidateRejections:
    def test_oversized_yaml_rejected(self):
        limits = ScenarioLimits(max_yaml_size_bytes=10)
        with pytest.raises(ScenarioValidationError) as exc_info:
            validate_scenario_yaml(VALID_YAML, limits=limits)
        assert any("size" in e.lower() for e in exc_info.value.errors)

    def test_too_many_epochs_rejected(self):
        limits = ScenarioLimits(max_epochs=5)
        with pytest.raises(ScenarioValidationError) as exc_info:
            validate_scenario_yaml(VALID_YAML, limits=limits)
        assert any("n_epochs" in e for e in exc_info.value.errors)

    def test_too_many_steps_rejected(self):
        limits = ScenarioLimits(max_steps_per_epoch=5)
        with pytest.raises(ScenarioValidationError) as exc_info:
            validate_scenario_yaml(VALID_YAML, limits=limits)
        assert any("steps_per_epoch" in e for e in exc_info.value.errors)

    def test_too_many_agents_rejected(self):
        limits = ScenarioLimits(max_agents=3)
        with pytest.raises(ScenarioValidationError) as exc_info:
            validate_scenario_yaml(VALID_YAML, limits=limits)
        assert any("agent count" in e.lower() for e in exc_info.value.errors)

    def test_disallowed_agent_type_rejected(self):
        yaml_content = textwrap.dedent("""\
            agents:
              - type: evil_bot
                count: 1
        """)
        with pytest.raises(ScenarioValidationError) as exc_info:
            validate_scenario_yaml(yaml_content)
        assert any("evil_bot" in e for e in exc_info.value.errors)

    def test_per_type_limit_exceeded(self):
        yaml_content = textwrap.dedent("""\
            agents:
              - type: adversarial
                count: 20
        """)
        with pytest.raises(ScenarioValidationError) as exc_info:
            validate_scenario_yaml(yaml_content)
        assert any("adversarial" in e and "count" in e.lower() for e in exc_info.value.errors)

    def test_observation_noise_std_exceeded(self):
        yaml_content = textwrap.dedent("""\
            simulation:
              observation_noise_std: 5.0
        """)
        with pytest.raises(ScenarioValidationError) as exc_info:
            validate_scenario_yaml(yaml_content)
        assert any("observation_noise_std" in e for e in exc_info.value.errors)

    def test_multiple_violations_all_reported(self):
        """All violations should be collected, not just the first."""
        yaml_content = textwrap.dedent("""\
            simulation:
              n_epochs: 9999
              steps_per_epoch: 9999
              observation_noise_std: 99.0
            agents:
              - type: evil_bot
                count: 100
        """)
        with pytest.raises(ScenarioValidationError) as exc_info:
            validate_scenario_yaml(yaml_content)
        errors = exc_info.value.errors
        # Should have at least 4 errors: epochs, steps, noise, disallowed type, total agents
        assert len(errors) >= 4
        error_text = " ".join(errors)
        assert "n_epochs" in error_text
        assert "steps_per_epoch" in error_text
        assert "observation_noise_std" in error_text
        assert "evil_bot" in error_text


# ---------------------------------------------------------------------------
# validate_scenario_yaml -- edge cases
# ---------------------------------------------------------------------------

class TestValidateEdgeCases:
    def test_empty_yaml_string(self):
        """Empty YAML parses to None, which is not a dict."""
        with pytest.raises(ScenarioValidationError) as exc_info:
            validate_scenario_yaml("")
        assert any("mapping" in e.lower() or "dict" in e.lower() for e in exc_info.value.errors)

    def test_yaml_with_only_whitespace(self):
        with pytest.raises(ScenarioValidationError) as exc_info:
            validate_scenario_yaml("   \n\n  ")
        assert len(exc_info.value.errors) >= 1

    def test_invalid_yaml_syntax(self):
        with pytest.raises(ScenarioValidationError) as exc_info:
            validate_scenario_yaml("  :\n  - ][bad yaml{{{")
        assert any("invalid yaml" in e.lower() or "yaml" in e.lower() for e in exc_info.value.errors)

    def test_missing_simulation_section(self):
        """No simulation section should be fine (no epochs to check)."""
        data = validate_scenario_yaml("scenario_id: no_sim\n")
        assert data["scenario_id"] == "no_sim"

    def test_missing_agents_section(self):
        """No agents section should be fine (0 agents is under limit)."""
        data = validate_scenario_yaml("scenario_id: no_agents\n")
        assert "agents" not in data or data.get("agents") is None

    def test_agent_count_defaults_to_one(self):
        """When count is omitted, should default to 1."""
        yaml_content = textwrap.dedent("""\
            agents:
              - type: honest
              - type: honest
              - type: honest
        """)
        limits = ScenarioLimits(max_agents=3)
        data = validate_scenario_yaml(yaml_content, limits=limits)
        assert len(data["agents"]) == 3

    def test_agent_count_defaults_exceeds_limit(self):
        yaml_content = textwrap.dedent("""\
            agents:
              - type: honest
              - type: honest
              - type: honest
              - type: honest
        """)
        limits = ScenarioLimits(max_agents=3)
        with pytest.raises(ScenarioValidationError) as exc_info:
            validate_scenario_yaml(yaml_content, limits=limits)
        assert any("agent count" in e.lower() for e in exc_info.value.errors)


# ---------------------------------------------------------------------------
# sanitize_scenario
# ---------------------------------------------------------------------------

class TestSanitizeScenario:
    def test_clamps_epochs(self):
        data = {"simulation": {"n_epochs": 9999}}
        limits = ScenarioLimits(max_epochs=100)
        result = sanitize_scenario(data, limits=limits)
        assert result["simulation"]["n_epochs"] == 100

    def test_clamps_steps_per_epoch(self):
        data = {"simulation": {"steps_per_epoch": 9999}}
        limits = ScenarioLimits(max_steps_per_epoch=20)
        result = sanitize_scenario(data, limits=limits)
        assert result["simulation"]["steps_per_epoch"] == 20

    def test_clamps_observation_noise_std(self):
        data = {"simulation": {"observation_noise_std": 5.0}}
        limits = ScenarioLimits(max_observation_noise_std=1.0)
        result = sanitize_scenario(data, limits=limits)
        assert result["simulation"]["observation_noise_std"] == 1.0

    def test_removes_disallowed_agent_types(self):
        data = {
            "agents": [
                {"type": "honest", "count": 3},
                {"type": "evil_bot", "count": 5},
            ]
        }
        result = sanitize_scenario(data)
        types_present = [a["type"] for a in result["agents"]]
        assert "evil_bot" not in types_present
        assert "honest" in types_present

    def test_clamps_per_type_agent_count(self):
        data = {
            "agents": [
                {"type": "adversarial", "count": 20},
            ]
        }
        result = sanitize_scenario(data)
        assert result["agents"][0]["count"] == 10  # default max for adversarial

    def test_clamps_total_agents(self):
        data = {
            "agents": [
                {"type": "honest", "count": 40},
                {"type": "opportunistic", "count": 40},
            ]
        }
        limits = ScenarioLimits(max_agents=10)
        result = sanitize_scenario(data, limits=limits)
        total = sum(a.get("count", 1) for a in result["agents"])
        assert total <= limits.max_agents

    def test_does_not_mutate_original(self):
        data = {"simulation": {"n_epochs": 9999}, "agents": [{"type": "honest", "count": 5}]}
        limits = ScenarioLimits(max_epochs=10)
        sanitize_scenario(data, limits=limits)
        assert data["simulation"]["n_epochs"] == 9999

    def test_values_within_limits_unchanged(self):
        data = {
            "simulation": {"n_epochs": 10, "steps_per_epoch": 5},
            "agents": [{"type": "honest", "count": 3}],
        }
        result = sanitize_scenario(data)
        assert result["simulation"]["n_epochs"] == 10
        assert result["simulation"]["steps_per_epoch"] == 5
        assert result["agents"][0]["count"] == 3

    def test_missing_simulation_section(self):
        data = {"scenario_id": "no_sim"}
        result = sanitize_scenario(data)
        assert result["scenario_id"] == "no_sim"

    def test_empty_agents_list(self):
        data = {"agents": []}
        result = sanitize_scenario(data)
        assert result["agents"] == []


# ---------------------------------------------------------------------------
# ScenarioValidationError
# ---------------------------------------------------------------------------

class TestScenarioValidationError:
    def test_error_stores_all_errors(self):
        err = ScenarioValidationError(["error1", "error2", "error3"])
        assert len(err.errors) == 3
        assert "error1" in err.errors
        assert "3 error(s)" in str(err)

    def test_error_is_exception(self):
        with pytest.raises(ScenarioValidationError):
            raise ScenarioValidationError(["boom"])
