"""Tests for ExternalAgentProxy."""

import pytest
from unittest.mock import patch, MagicMock

from swarm.agents.base import (
    Action,
    ActionType,
    InteractionProposal,
    Observation,
)
from swarm.api.external_agent import (
    ExternalAgentProxy,
    PolicyConfig,
    _observation_to_dict,
    _parse_action_from_response,
)
from swarm.models.agent import AgentState, AgentType
from swarm.models.interaction import InteractionType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_observation(**overrides) -> Observation:
    """Create a minimal Observation for testing."""
    defaults = {
        "agent_state": AgentState(agent_id="ext-1"),
        "current_epoch": 1,
        "current_step": 0,
    }
    defaults.update(overrides)
    return Observation(**defaults)


def _make_proposal(**overrides) -> InteractionProposal:
    """Create a minimal InteractionProposal for testing."""
    defaults = {
        "proposal_id": "prop-1",
        "initiator_id": "other-agent",
        "counterparty_id": "ext-1",
        "interaction_type": InteractionType.COLLABORATION,
    }
    defaults.update(overrides)
    return InteractionProposal(**defaults)


# ===========================================================================
# Policy mode tests
# ===========================================================================


class TestPolicyModeAct:
    """Tests for act() in policy mode."""

    def test_noop_when_nothing_to_do(self):
        """With no proposals, posts disabled, and no visible agents, returns NOOP."""
        agent = ExternalAgentProxy(
            agent_id="ext-1",
            mode="policy",
            policy_config=PolicyConfig(
                post_probability=0.0,
                interaction_probability=0.0,
            ),
        )
        obs = _make_observation(can_post=False, can_interact=False)
        action = agent.act(obs)
        assert action.action_type == ActionType.NOOP
        assert action.agent_id == "ext-1"

    def test_handles_pending_proposal_accept(self):
        """With high cooperation_bias and low threshold, accepts proposals."""
        agent = ExternalAgentProxy(
            agent_id="ext-1",
            mode="policy",
            policy_config=PolicyConfig(
                cooperation_bias=1.0,
                acceptance_threshold=0.0,
            ),
        )
        obs = _make_observation(
            pending_proposals=[
                {"proposal_id": "prop-1", "initiator_id": "other-agent"}
            ]
        )
        action = agent.act(obs)
        assert action.action_type == ActionType.ACCEPT_INTERACTION
        assert action.target_id == "prop-1"

    def test_handles_pending_proposal_reject(self):
        """With zero cooperation_bias and high threshold, rejects proposals."""
        agent = ExternalAgentProxy(
            agent_id="ext-1",
            mode="policy",
            policy_config=PolicyConfig(
                cooperation_bias=0.0,
                acceptance_threshold=0.9,
            ),
        )
        obs = _make_observation(
            pending_proposals=[
                {"proposal_id": "prop-2", "initiator_id": "other-agent"}
            ]
        )
        action = agent.act(obs)
        assert action.action_type == ActionType.REJECT_INTERACTION
        assert action.target_id == "prop-2"

    def test_posts_when_probability_is_1(self):
        """With post_probability=1.0, the agent always posts."""
        agent = ExternalAgentProxy(
            agent_id="ext-1",
            mode="policy",
            policy_config=PolicyConfig(
                post_probability=1.0,
                interaction_probability=0.0,
            ),
        )
        obs = _make_observation(can_post=True)
        action = agent.act(obs)
        assert action.action_type == ActionType.POST
        assert action.agent_id == "ext-1"

    def test_proposes_interaction_when_probability_is_1(self):
        """With interaction_probability=1.0 and visible agents, proposes."""
        agent = ExternalAgentProxy(
            agent_id="ext-1",
            mode="policy",
            policy_config=PolicyConfig(
                post_probability=0.0,
                interaction_probability=1.0,
                preferred_interaction_type="collaboration",
            ),
        )
        obs = _make_observation(
            can_post=False,
            can_interact=True,
            visible_agents=[{"agent_id": "agent-2"}],
        )
        action = agent.act(obs)
        assert action.action_type == ActionType.PROPOSE_INTERACTION
        assert action.counterparty_id == "agent-2"
        assert action.interaction_type == InteractionType.COLLABORATION


class TestPolicyModeAcceptInteraction:
    """Tests for accept_interaction() in policy mode."""

    def test_accepts_with_high_cooperation_bias(self):
        """High cooperation_bias + low threshold -> accept."""
        agent = ExternalAgentProxy(
            agent_id="ext-1",
            mode="policy",
            policy_config=PolicyConfig(
                cooperation_bias=1.0,
                acceptance_threshold=0.0,
            ),
        )
        proposal = _make_proposal()
        obs = _make_observation()
        assert agent.accept_interaction(proposal, obs) is True

    def test_rejects_with_low_cooperation_bias_high_threshold(self):
        """Zero cooperation_bias + high threshold -> reject (unknown agent has trust 0.5)."""
        agent = ExternalAgentProxy(
            agent_id="ext-1",
            mode="policy",
            policy_config=PolicyConfig(
                cooperation_bias=0.0,
                acceptance_threshold=0.9,
            ),
        )
        proposal = _make_proposal()
        obs = _make_observation()
        # effective = 0.5 * 0.0 + 0.5 * 1.0 = 0.5, threshold 0.9 -> reject
        assert agent.accept_interaction(proposal, obs) is False

    def test_threshold_boundary(self):
        """Exact threshold boundary check."""
        # Trust for unknown = 0.5.
        # effective = 0.5 * cooperation_bias + 0.5 * (1 - cooperation_bias)
        # For cooperation_bias=0.5: effective = 0.25 + 0.25 = 0.5
        agent = ExternalAgentProxy(
            agent_id="ext-1",
            mode="policy",
            policy_config=PolicyConfig(
                cooperation_bias=0.5,
                acceptance_threshold=0.5,
            ),
        )
        proposal = _make_proposal()
        obs = _make_observation()
        assert agent.accept_interaction(proposal, obs) is True


# ===========================================================================
# Callback mode tests
# ===========================================================================


class TestCallbackModeAct:
    """Tests for act() in callback mode using mocked httpx."""

    def test_calls_correct_url(self):
        """Verifies the callback POSTs to <callback_url>/act."""
        agent = ExternalAgentProxy(
            agent_id="ext-1",
            mode="callback",
            callback_url="http://external-agent.example.com",
            timeout=3.0,
        )
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "action_type": "post",
            "content": "Hello from external",
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.post", return_value=mock_response) as mock_post:
            action = agent.act(_make_observation())

            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert call_args[0][0] == "http://external-agent.example.com/act"
            assert call_args[1]["timeout"] == 3.0

        assert action.action_type == ActionType.POST
        assert action.content == "Hello from external"
        assert action.agent_id == "ext-1"

    def test_timeout_falls_back_to_noop(self):
        """On timeout, act() returns a NOOP action."""
        import httpx

        agent = ExternalAgentProxy(
            agent_id="ext-1",
            mode="callback",
            callback_url="http://external-agent.example.com",
            timeout=0.001,
        )

        with patch("httpx.post", side_effect=httpx.TimeoutException("timed out")):
            action = agent.act(_make_observation())

        assert action.action_type == ActionType.NOOP
        assert action.agent_id == "ext-1"

    def test_http_error_falls_back_to_noop(self):
        """On HTTP error, act() returns a NOOP action."""
        import httpx

        agent = ExternalAgentProxy(
            agent_id="ext-1",
            mode="callback",
            callback_url="http://external-agent.example.com",
        )

        with patch("httpx.post", side_effect=httpx.HTTPStatusError(
            "Server Error",
            request=MagicMock(),
            response=MagicMock(status_code=500),
        )):
            action = agent.act(_make_observation())

        assert action.action_type == ActionType.NOOP


class TestCallbackModeAcceptInteraction:
    """Tests for accept_interaction() in callback mode."""

    def test_calls_accept_interaction_url(self):
        """Verifies the callback POSTs to <callback_url>/accept_interaction."""
        agent = ExternalAgentProxy(
            agent_id="ext-1",
            mode="callback",
            callback_url="http://external-agent.example.com",
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"accepted": True}
        mock_response.raise_for_status = MagicMock()

        proposal = _make_proposal()

        with patch("httpx.post", return_value=mock_response) as mock_post:
            result = agent.accept_interaction(proposal, _make_observation())

            mock_post.assert_called_once()
            call_url = mock_post.call_args[0][0]
            assert call_url == "http://external-agent.example.com/accept_interaction"

        assert result is True

    def test_callback_rejection(self):
        """External agent can reject a proposal via callback."""
        agent = ExternalAgentProxy(
            agent_id="ext-1",
            mode="callback",
            callback_url="http://external-agent.example.com",
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {"accepted": False}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.post", return_value=mock_response):
            result = agent.accept_interaction(_make_proposal(), _make_observation())

        assert result is False

    def test_callback_error_falls_back_to_reject(self):
        """On error, accept_interaction returns False."""
        import httpx

        agent = ExternalAgentProxy(
            agent_id="ext-1",
            mode="callback",
            callback_url="http://external-agent.example.com",
        )

        with patch("httpx.post", side_effect=httpx.TimeoutException("timed out")):
            result = agent.accept_interaction(_make_proposal(), _make_observation())

        assert result is False


# ===========================================================================
# Action log tests
# ===========================================================================


class TestActionLog:
    """Tests that decisions are recorded in the action_log."""

    def test_act_records_to_log(self):
        """Every call to act() appends to action_log."""
        agent = ExternalAgentProxy(
            agent_id="ext-1",
            mode="policy",
            policy_config=PolicyConfig(post_probability=0.0, interaction_probability=0.0),
        )
        obs = _make_observation(can_post=False, can_interact=False)
        agent.act(obs)
        agent.act(obs)

        assert len(agent.action_log) == 2
        assert agent.action_log[0]["method"] == "act"
        assert agent.action_log[0]["agent_id"] == "ext-1"
        assert agent.action_log[1]["method"] == "act"

    def test_accept_interaction_records_to_log(self):
        """Calls to accept_interaction() append to action_log."""
        agent = ExternalAgentProxy(
            agent_id="ext-1",
            mode="policy",
            policy_config=PolicyConfig(cooperation_bias=1.0, acceptance_threshold=0.0),
        )
        proposal = _make_proposal()
        obs = _make_observation()
        agent.accept_interaction(proposal, obs)

        assert len(agent.action_log) == 1
        entry = agent.action_log[0]
        assert entry["method"] == "accept_interaction"
        assert entry["accepted"] is True
        assert entry["proposal_id"] == "prop-1"

    def test_log_contains_timestamp(self):
        """Each log entry has an ISO-format timestamp."""
        agent = ExternalAgentProxy(
            agent_id="ext-1",
            mode="policy",
            policy_config=PolicyConfig(post_probability=0.0, interaction_probability=0.0),
        )
        agent.act(_make_observation(can_post=False, can_interact=False))
        assert "timestamp" in agent.action_log[0]
        # Should be parseable as ISO datetime
        from datetime import datetime
        datetime.fromisoformat(agent.action_log[0]["timestamp"])


# ===========================================================================
# Construction / validation tests
# ===========================================================================


class TestConstruction:
    """Tests for ExternalAgentProxy initialization."""

    def test_uses_honest_agent_type(self):
        """External agents default to HONEST agent type."""
        agent = ExternalAgentProxy(agent_id="ext-1", mode="policy")
        assert agent.agent_type == AgentType.HONEST

    def test_callback_mode_requires_url(self):
        """Creating a callback-mode agent without a URL raises ValueError."""
        with pytest.raises(ValueError, match="callback_url is required"):
            ExternalAgentProxy(agent_id="ext-1", mode="callback")

    def test_invalid_mode_raises(self):
        """Invalid mode string raises ValueError."""
        with pytest.raises(ValueError, match="Invalid mode"):
            ExternalAgentProxy(agent_id="ext-1", mode="invalid")

    def test_default_policy_config(self):
        """Without explicit PolicyConfig, defaults are used."""
        agent = ExternalAgentProxy(agent_id="ext-1", mode="policy")
        assert agent.policy_config.cooperation_bias == 0.5
        assert agent.policy_config.acceptance_threshold == 0.4
        assert agent.policy_config.interaction_probability == 0.3
        assert agent.policy_config.post_probability == 0.2
        assert agent.policy_config.preferred_interaction_type == "collaboration"
