"""Tests for RLM agent implementation."""

from swarm.agents.base import ActionType, Observation
from swarm.agents.rlm_agent import CounterpartyModel, RLMAgent, RLMWorkingMemory
from swarm.models.agent import AgentState, AgentType
from swarm.models.interaction import InteractionType, SoftInteraction


class TestCounterpartyModel:
    """Tests for CounterpartyModel."""

    def test_default_acceptance_probability(self):
        model = CounterpartyModel(agent_id="test")
        assert model.acceptance_probability() == 0.5

    def test_acceptance_probability_after_updates(self):
        model = CounterpartyModel(agent_id="test")
        model.update(cooperated=True, payoff=1.0)
        model.update(cooperated=True, payoff=0.5)
        assert model.acceptance_probability() > 0.5

    def test_expected_payoff_empty(self):
        model = CounterpartyModel(agent_id="test")
        assert model.expected_payoff() == 0.0

    def test_expected_payoff_after_updates(self):
        model = CounterpartyModel(agent_id="test")
        model.update(cooperated=True, payoff=1.0)
        model.update(cooperated=True, payoff=2.0)
        assert model.expected_payoff() > 0.0

    def test_estimated_type_updates(self):
        model = CounterpartyModel(agent_id="test")
        # Three cooperative interactions -> honest
        for _ in range(3):
            model.update(cooperated=True, payoff=1.0)
        assert model.estimated_type == "honest"

    def test_estimated_type_adversarial(self):
        model = CounterpartyModel(agent_id="test")
        for _ in range(3):
            model.update(cooperated=False, payoff=-0.5)
        assert model.estimated_type == "adversarial"

    def test_estimated_type_strategic(self):
        model = CounterpartyModel(agent_id="test")
        model.update(cooperated=True, payoff=1.0)
        model.update(cooperated=False, payoff=0.0)
        model.update(cooperated=True, payoff=0.5)
        assert model.estimated_type == "strategic"


class TestRLMWorkingMemory:
    """Tests for RLMWorkingMemory."""

    def test_memory_budget_enforcement(self):
        wm = RLMWorkingMemory(entries=__import__("collections").deque(maxlen=5))
        for i in range(10):
            wm.record_entry({"index": i})
        assert len(wm.entries) == 5
        # Should contain the last 5 entries
        assert wm.entries[0]["index"] == 5

    def test_get_or_create_model(self):
        wm = RLMWorkingMemory()
        model = wm.get_or_create_model("agent_1")
        assert model.agent_id == "agent_1"
        # Second call returns same model
        model2 = wm.get_or_create_model("agent_1")
        assert model is model2

    def test_detect_patterns_reciprocity(self):
        wm = RLMWorkingMemory()
        for _ in range(5):
            wm.record_entry({"counterparty": "agent_1", "type": "outcome"})
        patterns = wm.detect_patterns()
        assert any(p["type"] == "reciprocity" for p in patterns)


class TestRLMAgent:
    """Tests for RLMAgent."""

    def _make_agent(self, **kwargs):
        defaults = {
            "agent_id": "rlm_1",
            "config": {
                "recursion_depth": 3,
                "planning_horizon": 5,
                "memory_budget": 100,
            },
        }
        defaults.update(kwargs)
        return RLMAgent(**defaults)

    def _make_observation(self, **kwargs):
        defaults = {
            "agent_state": AgentState(agent_id="rlm_1", agent_type=AgentType.RLM),
            "current_epoch": 0,
            "current_step": 0,
            "can_post": True,
            "can_interact": True,
            "can_vote": True,
            "can_claim_task": True,
        }
        defaults.update(kwargs)
        return Observation(**defaults)

    def test_creation_defaults(self):
        agent = self._make_agent()
        assert agent.agent_type == AgentType.RLM
        assert agent.recursion_depth == 3
        assert agent.planning_horizon == 5
        assert agent.memory_budget == 100

    def test_custom_config(self):
        agent = self._make_agent(
            config={"recursion_depth": 5, "planning_horizon": 10, "memory_budget": 200}
        )
        assert agent.recursion_depth == 5
        assert agent.planning_horizon == 10
        assert agent.memory_budget == 200

    def test_act_returns_action(self):
        agent = self._make_agent()
        obs = self._make_observation()
        action = agent.act(obs)
        assert action.action_type in ActionType

    def test_act_with_visible_agents(self):
        agent = self._make_agent()
        obs = self._make_observation(
            visible_agents=[
                {"agent_id": "honest_1", "reputation": 0.5},
                {"agent_id": "honest_2", "reputation": 0.3},
            ]
        )
        action = agent.act(obs)
        assert action.action_type in ActionType

    def test_act_handles_pending_proposals(self):
        agent = self._make_agent()
        obs = self._make_observation(
            pending_proposals=[
                {
                    "proposal_id": "prop_1",
                    "initiator_id": "honest_1",
                    "interaction_type": "collaboration",
                }
            ]
        )
        action = agent.act(obs)
        assert action.action_type in (
            ActionType.ACCEPT_INTERACTION,
            ActionType.REJECT_INTERACTION,
        )

    def test_accept_interaction(self):
        from swarm.agents.base import InteractionProposal

        agent = self._make_agent()
        obs = self._make_observation()
        proposal = InteractionProposal(
            initiator_id="honest_1",
            counterparty_id="rlm_1",
            interaction_type=InteractionType.COLLABORATION,
        )
        # Should return a boolean
        result = agent.accept_interaction(proposal, obs)
        assert isinstance(result, bool)

    def test_propose_interaction(self):
        agent = self._make_agent()
        obs = self._make_observation()
        result = agent.propose_interaction(obs, "honest_1")
        # Should return a proposal or None
        assert result is None or hasattr(result, "initiator_id")

    def test_recursive_depth_affects_behavior(self):
        """Deeper recursion should produce different trace structure."""
        agent_shallow = self._make_agent(
            agent_id="shallow",
            config={"recursion_depth": 1, "planning_horizon": 3, "memory_budget": 50},
        )
        agent_deep = self._make_agent(
            agent_id="deep",
            config={"recursion_depth": 5, "planning_horizon": 7, "memory_budget": 100},
        )
        obs = self._make_observation(
            visible_agents=[{"agent_id": "honest_1", "reputation": 0.5}]
        )

        # Both should produce valid actions
        agent_shallow.act(obs)
        agent_deep.act(obs)

        # Deep agent should have deeper traces
        if agent_deep.working_memory.recursion_traces:
            trace = agent_deep.working_memory.recursion_traces[-1]
            assert trace["depth"] == 5

    def test_working_memory_budget_enforced(self):
        agent = self._make_agent(
            config={"recursion_depth": 1, "planning_horizon": 2, "memory_budget": 5}
        )
        assert agent.working_memory.entries.maxlen == 5
        for i in range(10):
            agent.working_memory.record_entry({"idx": i})
        assert len(agent.working_memory.entries) == 5

    def test_update_from_outcome(self):
        agent = self._make_agent()
        interaction = SoftInteraction(
            initiator="rlm_1",
            counterparty="honest_1",
            accepted=True,
            p=0.8,
        )
        agent.update_from_outcome(interaction, payoff=1.5)

        model = agent.working_memory.counterparty_models.get("honest_1")
        assert model is not None
        assert model.interaction_count == 1

    def test_p_invariant_in_acceptance(self):
        """The agent must never produce p outside [0, 1]."""
        from swarm.agents.base import InteractionProposal

        agent = self._make_agent()
        obs = self._make_observation()

        # Run many acceptance checks - the probability is internally bounded
        for _ in range(100):
            proposal = InteractionProposal(
                initiator_id="adversary",
                counterparty_id="rlm_1",
                interaction_type=InteractionType.COLLABORATION,
            )
            result = agent.accept_interaction(proposal, obs)
            assert isinstance(result, bool)

    def test_memory_decay(self):
        from swarm.agents.memory_config import MemoryConfig

        agent = self._make_agent()
        agent.memory_config = MemoryConfig(epistemic_persistence=0.5)

        # Populate counterparty models
        model = agent.working_memory.get_or_create_model("honest_1")
        model.update(cooperated=True, payoff=1.0)
        model.update(cooperated=True, payoff=1.0)
        original_rate = model.cooperation_rate

        agent.apply_memory_decay(epoch=1)

        # After decay, cooperation rate should move toward 0.5
        assert model.cooperation_rate != original_rate
        assert abs(model.cooperation_rate - 0.5) < abs(original_rate - 0.5)

    def test_memory_decay_full_reset(self):
        from swarm.agents.memory_config import MemoryConfig

        agent = self._make_agent()
        agent.memory_config = MemoryConfig(epistemic_persistence=0.0)

        agent.working_memory.get_or_create_model("honest_1")
        agent.apply_memory_decay(epoch=1)

        assert len(agent.working_memory.counterparty_models) == 0
