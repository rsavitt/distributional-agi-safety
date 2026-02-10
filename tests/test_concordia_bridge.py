"""Tests for the Concordia bridge."""


import pytest

from swarm.bridges.concordia.adapter import ConcordiaAdapter
from swarm.bridges.concordia.config import ConcordiaConfig, JudgeConfig
from swarm.bridges.concordia.events import (
    ConcordiaEvent,
    ConcordiaEventType,
    JudgeScores,
    NarrativeChunk,
)
from swarm.bridges.concordia.game_master import SwarmGameMaster
from swarm.bridges.concordia.judge import LLMJudge

# ---------------------------------------------------------------------------
# JudgeScores tests
# ---------------------------------------------------------------------------


class TestJudgeScores:
    def test_construction(self):
        scores = JudgeScores(progress=0.8, quality=0.9, cooperation=0.7, harm=0.1)
        assert scores.progress == 0.8
        assert scores.quality == 0.9
        assert scores.cooperation == 0.7
        assert scores.harm == 0.1

    def test_clamping_high(self):
        scores = JudgeScores(progress=1.5, quality=2.0, cooperation=3.0, harm=10.0)
        assert scores.progress == 1.0
        assert scores.quality == 1.0
        assert scores.cooperation == 1.0
        assert scores.harm == 1.0

    def test_clamping_low(self):
        scores = JudgeScores(progress=-0.5, quality=-1.0, cooperation=-2.0, harm=-3.0)
        assert scores.progress == 0.0
        assert scores.quality == 0.0
        assert scores.cooperation == 0.0
        assert scores.harm == 0.0

    def test_defaults(self):
        scores = JudgeScores()
        assert scores.progress == 0.5
        assert scores.quality == 0.5
        assert scores.cooperation == 0.5
        assert scores.harm == 0.0
        assert scores.cached is False


# ---------------------------------------------------------------------------
# ConcordiaEvent tests
# ---------------------------------------------------------------------------


class TestConcordiaEvent:
    def test_serialization_roundtrip(self):
        event = ConcordiaEvent(
            event_type=ConcordiaEventType.JUDGE_EVALUATED,
            agent_id="agent_1",
            payload={"scores": {"progress": 0.8}},
        )
        data = event.to_dict()
        restored = ConcordiaEvent.from_dict(data)
        assert restored.event_type == ConcordiaEventType.JUDGE_EVALUATED
        assert restored.agent_id == "agent_1"
        assert restored.payload["scores"]["progress"] == 0.8

    def test_unknown_event_type(self):
        data = {"event_type": "totally_unknown", "agent_id": "x"}
        event = ConcordiaEvent.from_dict(data)
        assert event.event_type == ConcordiaEventType.ERROR

    def test_all_event_types(self):
        for et in ConcordiaEventType:
            event = ConcordiaEvent(event_type=et)
            data = event.to_dict()
            restored = ConcordiaEvent.from_dict(data)
            assert restored.event_type == et


# ---------------------------------------------------------------------------
# LLMJudge tests
# ---------------------------------------------------------------------------


class TestLLMJudge:
    def test_stub_mode_returns_defaults(self):
        judge = LLMJudge()
        scores = judge.evaluate("Some narrative text")
        assert scores.progress == 0.5
        assert scores.quality == 0.5
        assert scores.cooperation == 0.5
        assert scores.harm == 0.0
        assert scores.cached is False

    def test_cache_hit(self):
        judge = LLMJudge()
        judge.evaluate("Same text")
        scores2 = judge.evaluate("Same text")
        assert scores2.cached is True

    def test_cache_miss_different_text(self):
        judge = LLMJudge()
        judge.evaluate("Text A")
        scores = judge.evaluate("Text B")
        assert scores.cached is False

    def test_cache_disabled(self):
        config = JudgeConfig(cache_enabled=False)
        judge = LLMJudge(config=config)
        judge.evaluate("Same text")
        scores = judge.evaluate("Same text")
        assert scores.cached is False

    def test_parse_scores_valid_json(self):
        judge = LLMJudge()
        response = '{"progress": 0.9, "quality": 0.8, "cooperation": 0.7, "harm": 0.2}'
        scores = judge._parse_scores(response)
        assert scores.progress == pytest.approx(0.9)
        assert scores.quality == pytest.approx(0.8)
        assert scores.cooperation == pytest.approx(0.7)
        assert scores.harm == pytest.approx(0.2)

    def test_parse_scores_embedded_json(self):
        judge = LLMJudge()
        response = 'Here are the scores: {"progress": 0.6, "quality": 0.5, "cooperation": 0.4, "harm": 0.1} Done.'
        scores = judge._parse_scores(response)
        assert scores.progress == pytest.approx(0.6)

    def test_parse_scores_malformed(self):
        judge = LLMJudge()
        response = "This is not JSON at all"
        scores = judge._parse_scores(response)
        # Falls back to defaults
        assert scores.progress == 0.5
        assert scores.quality == 0.5

    def test_parse_scores_partial_json(self):
        judge = LLMJudge()
        response = '{"progress": 0.9}'
        scores = judge._parse_scores(response)
        assert scores.progress == pytest.approx(0.9)
        assert scores.quality == 0.5  # default for missing

    def test_with_llm_client(self):
        def mock_llm(prompt, model, temperature):
            return '{"progress": 0.7, "quality": 0.6, "cooperation": 0.8, "harm": 0.05}'

        judge = LLMJudge(llm_client=mock_llm)
        scores = judge.evaluate("Test narrative")
        assert scores.progress == pytest.approx(0.7)
        assert scores.quality == pytest.approx(0.6)

    def test_evaluate_batch(self):
        judge = LLMJudge()
        results = judge.evaluate_batch(["Text 1", "Text 2", "Text 3"])
        assert len(results) == 3
        # All should be stub defaults
        for scores in results:
            assert scores.progress == 0.5

    def test_truncation(self):
        config = JudgeConfig(max_chars=10)
        judge = LLMJudge(config=config)
        assert judge._truncate("short") == "short"
        assert len(judge._truncate("a" * 100)) == 10

    def test_cache_eviction(self):
        config = JudgeConfig(cache_max_size=2)
        judge = LLMJudge(config=config)
        judge.evaluate("text_1")
        judge.evaluate("text_2")
        judge.evaluate("text_3")
        # Cache should only have 2 entries
        assert len(judge._cache) == 2


# ---------------------------------------------------------------------------
# ConcordiaAdapter tests
# ---------------------------------------------------------------------------


class TestConcordiaAdapter:
    def test_scores_to_observables_zeros(self):
        adapter = ConcordiaAdapter()
        scores = JudgeScores(progress=0.0, quality=0.0, cooperation=0.0, harm=0.0)
        obs = adapter._scores_to_observables(scores)
        assert obs.task_progress_delta == pytest.approx(-1.0)
        assert obs.rework_count == 3
        assert obs.verifier_rejections == 0
        assert obs.tool_misuse_flags == 0
        assert obs.counterparty_engagement_delta == pytest.approx(-1.0)

    def test_scores_to_observables_ones(self):
        adapter = ConcordiaAdapter()
        scores = JudgeScores(progress=1.0, quality=1.0, cooperation=1.0, harm=1.0)
        obs = adapter._scores_to_observables(scores)
        assert obs.task_progress_delta == pytest.approx(1.0)
        assert obs.rework_count == 0
        assert obs.tool_misuse_flags == 3
        assert obs.counterparty_engagement_delta == pytest.approx(1.0)

    def test_scores_to_observables_mixed(self):
        adapter = ConcordiaAdapter()
        scores = JudgeScores(progress=0.5, quality=0.5, cooperation=0.5, harm=0.5)
        obs = adapter._scores_to_observables(scores)
        assert obs.task_progress_delta == pytest.approx(0.0)
        assert obs.rework_count == 1  # int((1-0.5)*3) = 1
        assert obs.tool_misuse_flags == 1  # int(0.5*3) = 1
        assert obs.counterparty_engagement_delta == pytest.approx(0.0)

    def test_process_narrative_single_agent(self):
        adapter = ConcordiaAdapter()
        interactions = adapter.process_narrative(
            agent_ids=["agent_1"],
            narrative_text="Agent 1 does something",
            step=5,
        )
        assert len(interactions) == 1
        interaction = interactions[0]
        assert interaction.initiator == "agent_1"
        assert interaction.counterparty == "agent_1"
        assert interaction.metadata["bridge"] == "concordia"
        assert interaction.metadata["step"] == 5

    def test_process_narrative_two_agents(self):
        adapter = ConcordiaAdapter()
        interactions = adapter.process_narrative(
            agent_ids=["agent_1", "agent_2"],
            narrative_text="Agents cooperate",
            step=0,
        )
        assert len(interactions) == 1
        assert interactions[0].initiator == "agent_1"
        assert interactions[0].counterparty == "agent_2"

    def test_process_narrative_three_agents(self):
        adapter = ConcordiaAdapter()
        interactions = adapter.process_narrative(
            agent_ids=["a", "b", "c"],
            narrative_text="Three agents interact",
        )
        # 3 choose 2 = 3 pairs
        assert len(interactions) == 3

    def test_p_invariant(self):
        """p must always be in [0, 1]."""
        adapter = ConcordiaAdapter()
        # Test with extreme scores
        for progress in [0.0, 0.5, 1.0]:
            for harm in [0.0, 0.5, 1.0]:
                interactions = adapter.process_narrative(
                    agent_ids=["a", "b"],
                    narrative_text=f"test progress={progress} harm={harm}",
                )
                for interaction in interactions:
                    assert 0.0 <= interaction.p <= 1.0, (
                        f"p={interaction.p} out of bounds"
                    )

    def test_interaction_circular_buffer(self):
        config = ConcordiaConfig(max_interactions=5)
        adapter = ConcordiaAdapter(config=config)

        for i in range(10):
            adapter.process_narrative(
                agent_ids=["a", "b"],
                narrative_text=f"Step {i}",
                step=i,
            )

        interactions = adapter.get_interactions()
        assert len(interactions) <= 5

    def test_events_recorded(self):
        adapter = ConcordiaAdapter()
        adapter.process_narrative(
            agent_ids=["a", "b"],
            narrative_text="Test",
        )
        events = adapter.get_events()
        assert len(events) >= 1
        assert events[0].event_type == ConcordiaEventType.JUDGE_EVALUATED

    def test_get_metrics_empty(self):
        adapter = ConcordiaAdapter()
        metrics = adapter.get_metrics()
        assert metrics["toxicity_rate"] == 0.0

    def test_process_narrative_batch(self):
        adapter = ConcordiaAdapter()
        chunks = [
            NarrativeChunk(
                agent_ids=["a", "b"],
                narrative_text="Chunk 1",
                step_range=(0, 1),
            ),
            NarrativeChunk(
                agent_ids=["c", "d"],
                narrative_text="Chunk 2",
                step_range=(1, 2),
            ),
        ]
        interactions = adapter.process_narrative_batch(chunks)
        assert len(interactions) == 2

    def test_process_narrative_with_custom_judge(self):
        def mock_llm(prompt, model, temp):
            return '{"progress": 0.9, "quality": 0.8, "cooperation": 0.7, "harm": 0.1}'

        judge = LLMJudge(llm_client=mock_llm)
        adapter = ConcordiaAdapter(judge=judge)
        interactions = adapter.process_narrative(
            agent_ids=["a", "b"],
            narrative_text="Custom judge test",
        )
        assert len(interactions) == 1
        # With high progress and low harm, p should be fairly high
        assert interactions[0].p > 0.5


# ---------------------------------------------------------------------------
# SwarmGameMaster tests
# ---------------------------------------------------------------------------


class MockGameMaster:
    """Mock Concordia GameMaster for testing."""

    def __init__(self):
        self.step_count = 0
        self.narratives = []
        self.agents = {"agent_1": {}, "agent_2": {}}

    def step(self):
        self.step_count += 1
        self.narratives.append(f"Step {self.step_count}: agents interacted")
        return {"step": self.step_count}

    def get_history(self):
        return self.narratives

    def get_agent_ids(self):
        return list(self.agents.keys())

    def add_narrative(self, text):
        self.narratives.append(text)


class MockGovernance:
    """Mock governance engine."""

    def __init__(self, freeze_agents=None):
        self._freeze = freeze_agents or set()
        self.applied = False

    def apply(self, interactions):
        self.applied = True

        class Effect:
            pass

        effect = Effect()
        effect.agents_to_freeze = self._freeze
        return effect


class TestSwarmGameMaster:
    def test_step_with_mock_gm(self):
        mock_gm = MockGameMaster()
        adapter = ConcordiaAdapter()
        gm = SwarmGameMaster(mock_gm, adapter)

        result = gm.step()
        assert result.interactions_count >= 1
        assert result.agent_ids == ["agent_1", "agent_2"]
        assert gm.step_count == 1

    def test_step_captures_narrative(self):
        mock_gm = MockGameMaster()
        adapter = ConcordiaAdapter()
        gm = SwarmGameMaster(mock_gm, adapter)

        result = gm.step()
        assert "Step 1" in result.narrative

    def test_step_with_governance(self):
        mock_gm = MockGameMaster()
        adapter = ConcordiaAdapter()
        governance = MockGovernance()
        gm = SwarmGameMaster(mock_gm, adapter, governance=governance)

        result = gm.step()
        assert governance.applied is True
        assert result.governance_applied is True

    def test_step_with_frozen_agents(self):
        mock_gm = MockGameMaster()
        adapter = ConcordiaAdapter()
        governance = MockGovernance(freeze_agents={"agent_1"})
        gm = SwarmGameMaster(mock_gm, adapter, governance=governance)

        result = gm.step()
        assert "agent_1" in result.frozen_agents
        # Check that governance narration was injected
        assert any("SWARM GOVERNANCE" in n for n in mock_gm.narratives)

    def test_multiple_steps(self):
        mock_gm = MockGameMaster()
        adapter = ConcordiaAdapter()
        gm = SwarmGameMaster(mock_gm, adapter)

        for _ in range(5):
            gm.step()

        assert gm.step_count == 5
        assert len(adapter.get_interactions()) == 5

    def test_none_gm(self):
        adapter = ConcordiaAdapter()
        gm = SwarmGameMaster(None, adapter)
        result = gm.step()
        assert result.narrative == ""
        assert result.agent_ids == []

    def test_requires_concordia(self):
        # This should return a boolean regardless
        result = SwarmGameMaster.requires_concordia()
        assert isinstance(result, bool)

    def test_adapter_property(self):
        adapter = ConcordiaAdapter()
        gm = SwarmGameMaster(None, adapter)
        assert gm.adapter is adapter
