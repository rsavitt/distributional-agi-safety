"""Tests for RLM experiment metrics."""

import pytest

from swarm.metrics.rlm_metrics import RLMMetrics


class TestCoordinationWithoutCommunication:
    """Tests for Experiment 1: Recursive Collusion metrics."""

    def test_empty_inputs(self):
        assert RLMMetrics.coordination_without_communication([], []) == 0.0

    def test_insufficient_agents(self):
        interactions = [{"initiator": "a", "counterparty": "b", "accepted": True}]
        assert RLMMetrics.coordination_without_communication(interactions, ["a"]) == 0.0

    def test_perfect_correlation(self):
        # Both agents accept/reject in lockstep
        interactions = [
            {"initiator": "a", "counterparty": "b", "accepted": True},
            {"initiator": "a", "counterparty": "b", "accepted": False},
            {"initiator": "a", "counterparty": "b", "accepted": True},
            {"initiator": "a", "counterparty": "b", "accepted": False},
        ]
        result = RLMMetrics.coordination_without_communication(
            interactions, ["a", "b"]
        )
        # Both agents get the same vector so correlation should be 1.0
        assert result == pytest.approx(1.0, abs=0.01)

    def test_no_correlation(self):
        # Agents behave independently
        interactions = [
            {"initiator": "a", "counterparty": "c", "accepted": True},
            {"initiator": "b", "counterparty": "c", "accepted": False},
            {"initiator": "a", "counterparty": "c", "accepted": False},
            {"initiator": "b", "counterparty": "c", "accepted": True},
        ]
        result = RLMMetrics.coordination_without_communication(
            interactions, ["a", "b"]
        )
        # Should be negative or near zero
        assert result < 0.5


class TestStrategyConvergence:
    """Tests for strategy convergence metric."""

    def test_empty_input(self):
        assert RLMMetrics.strategy_convergence({}) == 0.0

    def test_full_convergence(self):
        histories = {
            "a": ["cooperate", "cooperate", "cooperate"],
            "b": ["cooperate", "cooperate", "cooperate"],
            "c": ["cooperate", "cooperate", "cooperate"],
        }
        assert RLMMetrics.strategy_convergence(histories) == pytest.approx(1.0)

    def test_no_convergence(self):
        histories = {
            "a": ["cooperate", "defect", "cooperate"],
            "b": ["defect", "cooperate", "defect"],
            "c": ["noop", "noop", "noop"],
        }
        result = RLMMetrics.strategy_convergence(histories)
        # Each epoch has 3 different strategies -> modal fraction = 1/3
        assert result == pytest.approx(1.0 / 3.0, abs=0.01)

    def test_partial_convergence(self):
        histories = {
            "a": ["cooperate", "cooperate"],
            "b": ["cooperate", "defect"],
            "c": ["defect", "defect"],
        }
        # Epoch 0: cooperate=2/3, Epoch 1: cooperate=1, defect=2 -> 2/3
        result = RLMMetrics.strategy_convergence(histories)
        assert 0.5 < result < 1.0


class TestRationalizationConsistency:
    """Tests for rationalization consistency metric."""

    def test_empty_traces(self):
        assert RLMMetrics.rationalization_consistency([]) == 1.0

    def test_consistent_traces(self):
        traces = [
            {
                "action": "propose_interaction",
                "sub_traces": [
                    {"action": "propose_interaction", "score": 0.9},
                    {"action": "noop", "score": 0.1},
                ],
            }
        ]
        assert RLMMetrics.rationalization_consistency(traces) == 1.0

    def test_inconsistent_traces(self):
        traces = [
            {
                "action": "noop",  # Top-level chose noop
                "sub_traces": [
                    {"action": "propose_interaction", "score": 0.9},  # But sub chose propose
                    {"action": "noop", "score": 0.1},
                ],
            }
        ]
        assert RLMMetrics.rationalization_consistency(traces) == 0.0


class TestDominanceIndex:
    """Tests for Experiment 2: Memory-as-Power metrics."""

    def test_empty_payoffs(self):
        assert RLMMetrics.dominance_index({}) == 0.0

    def test_perfect_equality(self):
        payoffs = {"a": 10.0, "b": 10.0, "c": 10.0}
        gini = RLMMetrics.dominance_index(payoffs)
        assert gini == pytest.approx(0.0, abs=0.01)

    def test_maximal_inequality(self):
        payoffs = {"a": 100.0, "b": 0.0, "c": 0.0}
        gini = RLMMetrics.dominance_index(payoffs)
        assert gini > 0.5

    def test_single_agent(self):
        assert RLMMetrics.dominance_index({"a": 10.0}) == 0.0


class TestExploitationRate:
    """Tests for exploitation rate metric."""

    def test_insufficient_data(self):
        assert RLMMetrics.exploitation_rate({"a": 1.0}, {"a": 100}) == 0.0

    def test_positive_correlation(self):
        payoffs = {"a": 10.0, "b": 20.0, "c": 30.0}
        budgets = {"a": 10, "b": 50, "c": 200}
        result = RLMMetrics.exploitation_rate(payoffs, budgets)
        assert result > 0.0  # More memory -> more payoff

    def test_no_correlation(self):
        payoffs = {"a": 10.0, "b": 10.0, "c": 10.0}
        budgets = {"a": 10, "b": 50, "c": 200}
        result = RLMMetrics.exploitation_rate(payoffs, budgets)
        # Equal payoffs regardless of budget -> zero correlation
        assert result == pytest.approx(0.0, abs=0.01)


class TestInequalityAmplification:
    """Tests for inequality amplification metric."""

    def test_insufficient_data(self):
        assert RLMMetrics.inequality_amplification([], {}) == 0.0
        assert RLMMetrics.inequality_amplification([{"a": 1.0}], {}) == 0.0

    def test_growing_inequality(self):
        # Gini increases over time
        payoffs_over_time = [
            {"a": 10.0, "b": 10.0, "c": 10.0},  # Equal
            {"a": 15.0, "b": 10.0, "c": 5.0},  # Some inequality
            {"a": 25.0, "b": 10.0, "c": 1.0},  # More inequality
        ]
        slope = RLMMetrics.inequality_amplification(payoffs_over_time, {})
        assert slope > 0.0  # Positive = growing inequality

    def test_stable_equality(self):
        payoffs_over_time = [
            {"a": 10.0, "b": 10.0, "c": 10.0},
            {"a": 10.0, "b": 10.0, "c": 10.0},
            {"a": 10.0, "b": 10.0, "c": 10.0},
        ]
        slope = RLMMetrics.inequality_amplification(payoffs_over_time, {})
        assert slope == pytest.approx(0.0, abs=0.01)


class TestTimeToDetect:
    """Tests for Experiment 3: Governance Lag metrics."""

    def test_no_harm(self):
        assert RLMMetrics.time_to_detect([], []) == 0.0

    def test_no_detection(self):
        assert RLMMetrics.time_to_detect([1, 2, 3], []) == float("inf")

    def test_immediate_detection(self):
        result = RLMMetrics.time_to_detect([5, 10], [5, 10])
        assert result == 0.0

    def test_delayed_detection(self):
        result = RLMMetrics.time_to_detect([5, 10], [8, 15])
        # Harm at 5 detected at 8 (lag=3), harm at 10 detected at 15 (lag=5)
        assert result == pytest.approx(4.0)


class TestIrreversibleDamage:
    """Tests for irreversible damage metric."""

    def test_empty_payoffs(self):
        assert RLMMetrics.irreversible_damage([], []) == 0.0

    def test_no_governance(self):
        payoffs = [1.0, -2.0, -3.0, 1.0]
        result = RLMMetrics.irreversible_damage(payoffs, [])
        assert result == pytest.approx(-5.0)

    def test_early_governance(self):
        payoffs = [-1.0, -2.0, -3.0, 1.0]
        result = RLMMetrics.irreversible_damage(payoffs, [1])
        # Only epoch 0 is before governance
        assert result == pytest.approx(-1.0)

    def test_all_positive(self):
        payoffs = [1.0, 2.0, 3.0]
        result = RLMMetrics.irreversible_damage(payoffs, [])
        assert result == 0.0


class TestEvasionSuccessRate:
    """Tests for evasion success rate metric."""

    def test_no_harmful(self):
        assert RLMMetrics.evasion_success_rate([], []) == 0.0

    def test_all_detected(self):
        result = RLMMetrics.evasion_success_rate(["a", "b", "c"], ["a", "b", "c"])
        assert result == 0.0

    def test_none_detected(self):
        result = RLMMetrics.evasion_success_rate(["a", "b", "c"], [])
        assert result == 1.0

    def test_partial_detection(self):
        result = RLMMetrics.evasion_success_rate(["a", "b", "c", "d"], ["a", "c"])
        assert result == pytest.approx(0.5)
