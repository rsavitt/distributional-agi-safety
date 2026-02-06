"""Tests for incoherence metric contract and semantics."""

import random
from typing import Any, Dict, Hashable, Mapping, Optional

import pytest

from swarm.metrics.incoherence import (
    BenchmarkPolicy,
    DecisionRecord,
    IncoherenceMetrics,
    classify_dual_failure_modes,
    disagreement_rate,
    error_rate,
    incoherence_index,
    summarize_incoherence_by_agent_type,
)


class DictBenchmark(BenchmarkPolicy):
    """Simple benchmark policy keyed by (task_family, decision_id)."""

    def __init__(self, mapping: Dict[tuple[str, str], Hashable]):
        self.mapping = mapping

    def action_for(
        self,
        decision_id: str,
        task_family: str,
        metadata: Mapping[str, Any],
    ) -> Optional[Hashable]:
        return self.mapping.get((task_family, decision_id))


def test_disagreement_deterministic_actions_is_zero():
    actions = ["approve", "approve", "approve", "approve"]
    assert disagreement_rate(actions) == 0.0


def test_disagreement_random_actions_is_high():
    rng = random.Random(42)
    actions = [rng.choice(["a", "b", "c", "d"]) for _ in range(1000)]
    assert disagreement_rate(actions) > 0.70


def test_error_rate_with_missing_benchmark_is_zero():
    assert error_rate(["a", "b"], benchmark_action=None) == 0.0


def test_incoherence_index_caps_to_one():
    # High disagreement, very low error should still be clipped.
    assert incoherence_index(disagreement=0.9, error=0.01) == 1.0


def test_incoherence_index_zero_when_error_and_disagreement_zero():
    assert incoherence_index(disagreement=0.0, error=0.0) == 0.0


def test_compute_for_decision_excludes_abstentions():
    benchmark = DictBenchmark({("task", "d1"): "approve"})
    metrics = IncoherenceMetrics(benchmark)
    records = [
        DecisionRecord("d1", "task", 0, "approve"),
        DecisionRecord("d1", "task", 1, "reject"),
        DecisionRecord("d1", "task", 2, None, abstained=True),
    ]

    result = metrics.compute_for_decision(records)

    assert result.n_considered == 2
    assert result.error == pytest.approx(0.5)
    assert 0.0 <= result.incoherence <= 1.0


def test_compute_for_decision_requires_non_empty_records():
    benchmark = DictBenchmark({})
    metrics = IncoherenceMetrics(benchmark)
    with pytest.raises(ValueError, match="at least one"):
        metrics.compute_for_decision([])


def test_summarize_incoherence_by_agent_type():
    rows = [
        {
            "agent_type": "honest",
            "incoherence_index": 0.7,
            "error_rate": 0.4,
            "disagreement_rate": 0.3,
        },
        {
            "agent_type": "honest",
            "incoherence_index": 0.5,
            "error_rate": 0.6,
            "disagreement_rate": 0.4,
        },
        {
            "agent_type": "adversarial",
            "incoherence_index": 0.2,
            "error_rate": 0.3,
            "disagreement_rate": 0.1,
        },
    ]

    summary = summarize_incoherence_by_agent_type(rows)
    assert set(summary.keys()) == {"honest", "adversarial"}
    assert summary["honest"]["n"] == 2.0
    assert summary["honest"]["mean_incoherence_index"] == pytest.approx(0.6)
    assert summary["adversarial"]["mean_disagreement_rate"] == pytest.approx(0.1)


def test_classify_dual_failure_modes_counts_categories():
    incidents = [
        {"harmful": True, "agent_type": "adversarial", "incoherence_index": 0.2},
        {"harmful": True, "agent_type": "deceptive", "incoherence_index": 0.3},
        {"harmful": True, "agent_type": "honest", "incoherence_index": 0.8},
        {"harmful": True, "agent_type": "opportunistic", "incoherence_index": 0.7},
        {"harmful": False, "agent_type": "honest", "incoherence_index": 0.9},
    ]

    result = classify_dual_failure_modes(incidents, incoherence_threshold=0.5)
    assert result.total_harmful_incidents == 4
    assert result.coherent_adversarial_incidents == 2
    assert result.incoherent_benign_incidents == 2
    assert result.coherent_to_incoherent_ratio == pytest.approx(1.0)


def test_classify_dual_failure_modes_handles_zero_denominator():
    incidents = [
        {"harmful": True, "agent_type": "adversarial", "incoherence_index": 0.1},
    ]
    result = classify_dual_failure_modes(incidents, incoherence_threshold=0.5)
    assert result.incoherent_benign_incidents == 0
    assert result.coherent_adversarial_incidents == 1
    assert result.coherent_to_incoherent_ratio == float("inf")
