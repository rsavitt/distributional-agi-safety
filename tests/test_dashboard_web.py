"""Tests for the web-based agent interaction dashboard."""

import json
from pathlib import Path

import pytest

from swarm.dashboard.session_parser import (
    _build_edges_from_interactions,
    _infer_agent_type,
    discover_sessions,
    parse_session,
)


@pytest.fixture
def tmp_project(tmp_path):
    """Create a temporary project directory with sample run/log data."""
    # Create runs directory with a JSON history
    runs_dir = tmp_path / "runs" / "20260101_baseline_seed42"
    runs_dir.mkdir(parents=True)
    history = {
        "simulation_id": "baseline",
        "started_at": "2026-01-01T00:00:00",
        "ended_at": "2026-01-01T00:01:00",
        "n_epochs": 3,
        "steps_per_epoch": 5,
        "n_agents": 2,
        "seed": 42,
        "epoch_snapshots": [
            {
                "epoch": 0,
                "timestamp": "2026-01-01T00:00:10",
                "total_interactions": 5,
                "accepted_interactions": 3,
                "rejected_interactions": 2,
                "toxicity_rate": 0.15,
                "quality_gap": 0.1,
                "avg_p": 0.65,
                "total_welfare": 10.0,
                "avg_payoff": 5.0,
                "gini_coefficient": 0.2,
                "n_agents": 2,
            },
            {
                "epoch": 1,
                "timestamp": "2026-01-01T00:00:20",
                "total_interactions": 6,
                "accepted_interactions": 4,
                "rejected_interactions": 2,
                "toxicity_rate": 0.12,
                "quality_gap": 0.15,
                "avg_p": 0.7,
                "total_welfare": 12.0,
                "avg_payoff": 6.0,
                "gini_coefficient": 0.18,
                "n_agents": 2,
            },
            {
                "epoch": 2,
                "timestamp": "2026-01-01T00:00:30",
                "total_interactions": 7,
                "accepted_interactions": 5,
                "rejected_interactions": 2,
                "toxicity_rate": 0.1,
                "quality_gap": 0.2,
                "avg_p": 0.75,
                "total_welfare": 15.0,
                "avg_payoff": 7.5,
                "gini_coefficient": 0.15,
                "n_agents": 2,
            },
        ],
        "agent_snapshots": [
            {
                "agent_id": "honest_0",
                "epoch": 0,
                "name": "honest_0",
                "reputation": 1.0,
                "resources": 100.0,
                "interactions_initiated": 3,
                "interactions_received": 2,
                "avg_p_initiated": 0.8,
                "avg_p_received": 0.7,
                "total_payoff": 6.0,
                "is_frozen": False,
                "is_quarantined": False,
            },
            {
                "agent_id": "adversarial_0",
                "epoch": 0,
                "name": "adversarial_0",
                "reputation": 0.3,
                "resources": 90.0,
                "interactions_initiated": 2,
                "interactions_received": 3,
                "avg_p_initiated": 0.3,
                "avg_p_received": 0.6,
                "total_payoff": 4.0,
                "is_frozen": False,
                "is_quarantined": False,
            },
        ],
    }
    (runs_dir / "history.json").write_text(json.dumps(history))

    # Create logs directory with JSONL events
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    events = [
        {
            "event_id": "e1",
            "timestamp": "2026-01-01T00:00:01",
            "event_type": "interaction_proposed",
            "interaction_id": "ix1",
            "initiator_id": "agent_a",
            "counterparty_id": "agent_b",
            "payload": {"interaction_type": "reply", "v_hat": 0.6, "p": 0.73},
            "epoch": 0,
            "step": 1,
            "scenario_id": "test_scenario",
            "seed": 42,
        },
        {
            "event_id": "e2",
            "timestamp": "2026-01-01T00:00:02",
            "event_type": "interaction_accepted",
            "interaction_id": "ix1",
            "epoch": 0,
            "step": 1,
        },
        {
            "event_id": "e3",
            "timestamp": "2026-01-01T00:00:03",
            "event_type": "payoff_computed",
            "interaction_id": "ix1",
            "initiator_id": "agent_a",
            "counterparty_id": "agent_b",
            "payload": {
                "payoff_initiator": 1.5,
                "payoff_counterparty": 0.8,
                "components": {
                    "tau": 0.2,
                    "c_a": 0.1,
                    "c_b": 0.05,
                    "r_a": 0.3,
                    "r_b": 0.1,
                },
            },
            "epoch": 0,
            "step": 1,
        },
        {
            "event_id": "e4",
            "timestamp": "2026-01-01T00:00:04",
            "event_type": "interaction_proposed",
            "interaction_id": "ix2",
            "initiator_id": "agent_b",
            "counterparty_id": "agent_a",
            "payload": {"interaction_type": "reply", "v_hat": -0.2, "p": 0.35},
            "epoch": 0,
            "step": 2,
        },
        {
            "event_id": "e5",
            "timestamp": "2026-01-01T00:00:05",
            "event_type": "interaction_rejected",
            "interaction_id": "ix2",
            "epoch": 0,
            "step": 2,
        },
    ]
    jsonl_path = logs_dir / "test_events.jsonl"
    with open(jsonl_path, "w") as f:
        for event in events:
            f.write(json.dumps(event) + "\n")

    return tmp_path


class TestDiscoverSessions:
    def test_discovers_json_and_jsonl(self, tmp_project):
        sessions = discover_sessions(tmp_project)
        assert len(sessions) == 2

        sources = {s["source"] for s in sessions}
        assert "runs" in sources
        assert "logs" in sources

    def test_json_session_metadata(self, tmp_project):
        sessions = discover_sessions(tmp_project)
        json_sessions = [s for s in sessions if s["file_type"] == "json"]
        assert len(json_sessions) == 1

        s = json_sessions[0]
        assert s["session_id"] == "baseline"
        assert s["n_epochs"] == 3
        assert s["n_agents"] == 2
        assert s["seed"] == 42

    def test_jsonl_session_metadata(self, tmp_project):
        sessions = discover_sessions(tmp_project)
        jsonl_sessions = [s for s in sessions if s["file_type"] == "jsonl"]
        assert len(jsonl_sessions) == 1

        s = jsonl_sessions[0]
        assert s["session_id"] == "test_scenario"
        assert s["n_agents"] == 2  # agent_a and agent_b
        assert s["event_count"] == 5
        assert s["seed"] == 42

    def test_empty_directory(self, tmp_path):
        sessions = discover_sessions(tmp_path)
        assert sessions == []

    def test_no_runs_or_logs_dirs(self, tmp_path):
        """Handles missing runs/ and logs/ gracefully."""
        sessions = discover_sessions(tmp_path)
        assert sessions == []


class TestParseJsonSession:
    def test_parse_json(self, tmp_project):
        path = str(tmp_project / "runs" / "20260101_baseline_seed42" / "history.json")
        data = parse_session(path)

        assert data["session_id"] == "baseline"
        assert data["n_epochs"] == 3
        assert data["n_agents"] == 2
        assert len(data["agents"]) == 2
        assert len(data["epochs"]) == 3

    def test_agents_have_epoch_data(self, tmp_project):
        path = str(tmp_project / "runs" / "20260101_baseline_seed42" / "history.json")
        data = parse_session(path)

        honest = data["agents"]["honest_0"]
        assert honest["name"] == "honest_0"
        assert honest["type"] == "honest"
        assert len(honest["epochs"]) == 1
        assert honest["epochs"][0]["reputation"] == 1.0

    def test_epoch_metrics(self, tmp_project):
        path = str(tmp_project / "runs" / "20260101_baseline_seed42" / "history.json")
        data = parse_session(path)

        ep0 = data["epochs"][0]
        assert ep0["epoch"] == 0
        assert ep0["toxicity_rate"] == 0.15
        assert ep0["total_welfare"] == 10.0

    def test_edges_generated(self, tmp_project):
        path = str(tmp_project / "runs" / "20260101_baseline_seed42" / "history.json")
        data = parse_session(path)
        # Both agents have activity in epoch 0 -> should be an edge
        assert len(data["edges"]) > 0


class TestParseJsonlSession:
    def test_parse_jsonl(self, tmp_project):
        path = str(tmp_project / "logs" / "test_events.jsonl")
        data = parse_session(path)

        assert data["session_id"] == "test_scenario"
        assert data["n_agents"] == 2
        assert data["seed"] == 42

    def test_interactions_parsed(self, tmp_project):
        path = str(tmp_project / "logs" / "test_events.jsonl")
        data = parse_session(path)

        interactions = data["interactions"]
        assert len(interactions) == 2

        ix1 = interactions[0]
        assert ix1["initiator"] == "agent_a"
        assert ix1["counterparty"] == "agent_b"
        assert ix1["p"] == 0.73
        assert ix1["accepted"] is True

        ix2 = interactions[1]
        assert ix2["accepted"] is False

    def test_edges_from_interactions(self, tmp_project):
        path = str(tmp_project / "logs" / "test_events.jsonl")
        data = parse_session(path)

        edges = data["edges"]
        assert len(edges) == 2  # a->b and b->a

    def test_epoch_metrics_computed(self, tmp_project):
        path = str(tmp_project / "logs" / "test_events.jsonl")
        data = parse_session(path)

        epochs = data["epochs"]
        assert len(epochs) == 1  # all events in epoch 0

        ep = epochs[0]
        assert ep["total_interactions"] == 2
        assert ep["accepted_interactions"] == 1

    def test_payoff_attached_to_interaction(self, tmp_project):
        path = str(tmp_project / "logs" / "test_events.jsonl")
        data = parse_session(path)

        ix1 = data["interactions"][0]
        assert ix1["payoff_initiator"] == 1.5
        assert ix1["payoff_counterparty"] == 0.8
        assert ix1["tau"] == 0.2


class TestBuildEdges:
    def test_aggregate_interactions(self):
        interactions = [
            {"initiator": "a", "counterparty": "b", "p": 0.8, "accepted": True},
            {"initiator": "a", "counterparty": "b", "p": 0.6, "accepted": False},
            {"initiator": "b", "counterparty": "a", "p": 0.5, "accepted": True},
        ]
        edges = _build_edges_from_interactions(interactions)

        assert len(edges) == 2

        ab = [e for e in edges if e["source"] == "a" and e["target"] == "b"]
        assert len(ab) == 1
        assert ab[0]["count"] == 2
        assert ab[0]["accepted"] == 1
        assert abs(ab[0]["avg_p"] - 0.7) < 0.001  # (0.8+0.6)/2

    def test_empty_interactions(self):
        edges = _build_edges_from_interactions([])
        assert edges == []

    def test_single_direction(self):
        interactions = [
            {"initiator": "x", "counterparty": "y", "p": 0.9, "accepted": True},
        ]
        edges = _build_edges_from_interactions(interactions)
        assert len(edges) == 1
        assert edges[0]["source"] == "x"
        assert edges[0]["target"] == "y"
        assert edges[0]["count"] == 1


class TestInferAgentType:
    def test_honest(self):
        assert _infer_agent_type("honest_0") == "honest"

    def test_adversarial(self):
        assert _infer_agent_type("adversarial_agent_1") == "adversarial"

    def test_llm(self):
        assert _infer_agent_type("llm_claude_0") == "llm"

    def test_unknown(self):
        assert _infer_agent_type("agent_42") == "unknown"

    def test_deceptive(self):
        assert _infer_agent_type("deceptive_0") == "deceptive"

    def test_opportunistic(self):
        assert _infer_agent_type("opportunistic_1") == "opportunistic"

    def test_empty_string(self):
        assert _infer_agent_type("") == "unknown"

    def test_case_insensitive(self):
        assert _infer_agent_type("HONEST_Agent") == "honest"


class TestUnsupportedFileType:
    def test_unsupported_extension(self, tmp_path):
        p = tmp_path / "test.txt"
        p.write_text("hello")
        data = parse_session(str(p))
        assert "error" in data
