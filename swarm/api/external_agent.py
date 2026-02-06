"""External agent proxy for integrating outside agents into SWARM simulations.

Supports two modes:
- "policy": Pre-declared strategy using a PolicyConfig (local decisions).
- "callback": HTTP callbacks to an external service via httpx.
"""

import dataclasses
import random
from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from swarm.agents.base import (
    Action,
    ActionType,
    BaseAgent,
    InteractionProposal,
    Observation,
    Role,
)
from swarm.models.agent import AgentType
from swarm.models.interaction import InteractionType


class PolicyConfig(BaseModel):
    """Configuration for policy-mode external agents."""

    cooperation_bias: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Probability of cooperating (0=never, 1=always).",
    )
    acceptance_threshold: float = Field(
        default=0.4,
        ge=0.0,
        le=1.0,
        description="Minimum trust score to accept an interaction.",
    )
    interaction_probability: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Probability of proposing an interaction each step.",
    )
    post_probability: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description="Probability of posting each step.",
    )
    preferred_interaction_type: str = Field(
        default="collaboration",
        description="Preferred interaction type (must be a valid InteractionType value).",
    )


def _observation_to_dict(observation: Observation) -> Dict:
    """Serialize an Observation dataclass to a plain dict for HTTP transport."""
    d: Dict = {}
    for f in dataclasses.fields(observation):
        value = getattr(observation, f.name)
        if f.name == "agent_state":
            value = value.to_dict()
        d[f.name] = value
    return d


def _proposal_to_dict(proposal: InteractionProposal) -> Dict:
    """Serialize an InteractionProposal dataclass to a plain dict."""
    d: Dict = {}
    for f in dataclasses.fields(proposal):
        value = getattr(proposal, f.name)
        if isinstance(value, InteractionType):
            value = value.value
        d[f.name] = value
    return d


def _parse_action_from_response(response_data: Dict, agent_id: str) -> Action:
    """Parse an Action from a callback response dict.

    Expected keys in *response_data*:
        action_type (str): Value matching an ActionType enum member.
        content (str, optional): Content payload.
        target_id (str, optional): Target identifier.
        counterparty_id (str, optional): Counterparty identifier.
        interaction_type (str, optional): InteractionType value.
        vote_direction (int, optional): +1 or -1.
        metadata (dict, optional): Additional metadata.
    """
    try:
        action_type = ActionType(response_data.get("action_type", "noop"))
    except ValueError:
        action_type = ActionType.NOOP

    try:
        interaction_type = InteractionType(
            response_data.get("interaction_type", "reply")
        )
    except ValueError:
        interaction_type = InteractionType.REPLY

    return Action(
        action_type=action_type,
        agent_id=agent_id,
        content=response_data.get("content", ""),
        target_id=response_data.get("target_id", ""),
        counterparty_id=response_data.get("counterparty_id", ""),
        interaction_type=interaction_type,
        vote_direction=response_data.get("vote_direction", 0),
        metadata=response_data.get("metadata", {}),
    )


class ExternalAgentProxy(BaseAgent):
    """Proxy that allows external agents to participate in SWARM simulations.

    Two modes are supported:

    **policy** -- decisions are made locally according to a :class:`PolicyConfig`.
    This behaves similarly to :class:`HonestAgent` but is fully parameterised.

    **callback** -- decisions are delegated to an external HTTP service.  The
    proxy serialises the observation and POSTs it to ``<callback_url>/act`` or
    ``<callback_url>/accept_interaction``.  On timeout or error the proxy falls
    back to a NOOP action.

    All decisions are recorded in :attr:`action_log` for audit purposes.
    """

    def __init__(
        self,
        agent_id: str,
        mode: Literal["policy", "callback"] = "policy",
        policy_config: Optional[PolicyConfig] = None,
        callback_url: Optional[str] = None,
        timeout: float = 5.0,
        roles: Optional[List[Role]] = None,
        config: Optional[Dict] = None,
        name: Optional[str] = None,
    ):
        super().__init__(
            agent_id=agent_id,
            agent_type=AgentType.HONEST,
            roles=roles,
            config=config or {},
            name=name,
        )

        if mode not in ("policy", "callback"):
            raise ValueError(f"Invalid mode {mode!r}; must be 'policy' or 'callback'.")

        self.mode: str = mode
        self.timeout: float = timeout
        self.action_log: List[Dict] = []

        # Policy mode setup
        self.policy_config: PolicyConfig = policy_config or PolicyConfig()

        # Callback mode setup
        self.callback_url: Optional[str] = callback_url
        if mode == "callback" and not callback_url:
            raise ValueError("callback_url is required when mode='callback'.")

    # ------------------------------------------------------------------
    # Logging helper
    # ------------------------------------------------------------------

    def _log_decision(self, method: str, action: Action, extra: Optional[Dict] = None) -> None:
        """Append an entry to the audit log."""
        entry: Dict = {
            "timestamp": datetime.now().isoformat(),
            "method": method,
            "action_type": action.action_type.value,
            "agent_id": self.agent_id,
        }
        if extra:
            entry.update(extra)
        self.action_log.append(entry)

    # ------------------------------------------------------------------
    # Abstract method implementations
    # ------------------------------------------------------------------

    def act(self, observation: Observation) -> Action:
        """Choose an action for the current step."""
        if self.mode == "callback":
            action = self._callback_act(observation)
        else:
            action = self._policy_act(observation)

        self._log_decision("act", action)
        return action

    def accept_interaction(
        self,
        proposal: InteractionProposal,
        observation: Observation,
    ) -> bool:
        """Decide whether to accept an interaction proposal."""
        if self.mode == "callback":
            accepted = self._callback_accept_interaction(proposal, observation)
        else:
            accepted = self._policy_accept_interaction(proposal, observation)

        # Log the decision as an accept/reject action for audit
        dummy_action = Action(
            action_type=ActionType.ACCEPT_INTERACTION if accepted else ActionType.REJECT_INTERACTION,
            agent_id=self.agent_id,
            target_id=proposal.proposal_id,
        )
        self._log_decision(
            "accept_interaction",
            dummy_action,
            {"accepted": accepted, "proposal_id": proposal.proposal_id},
        )
        return accepted

    def propose_interaction(
        self,
        observation: Observation,
        counterparty_id: str,
    ) -> Optional[InteractionProposal]:
        """Optionally propose an interaction to *counterparty_id*."""
        if self.mode == "policy":
            return self._policy_propose_interaction(observation, counterparty_id)
        # Callback mode: interaction proposals are driven by act(); return None.
        return None

    # ------------------------------------------------------------------
    # Policy-mode logic
    # ------------------------------------------------------------------

    def _policy_act(self, observation: Observation) -> Action:
        """Local decision-making based on PolicyConfig."""
        pc = self.policy_config

        # Handle pending proposals first
        if observation.pending_proposals:
            proposal_dict = observation.pending_proposals[0]
            trust = self.compute_counterparty_trust(
                proposal_dict.get("initiator_id", "")
            )
            effective = trust * pc.cooperation_bias + 0.5 * (1 - pc.cooperation_bias)
            if effective >= pc.acceptance_threshold:
                return self.create_accept_action(proposal_dict["proposal_id"])
            else:
                return self.create_reject_action(proposal_dict["proposal_id"])

        # Post content
        if observation.can_post and random.random() < pc.post_probability:
            return self.create_post_action(
                "External agent contribution based on policy config."
            )

        # Propose interaction
        if (
            observation.can_interact
            and observation.visible_agents
            and random.random() < pc.interaction_probability
        ):
            agent_entry = random.choice(observation.visible_agents)
            counterparty_id = agent_entry.get("agent_id", "")
            if counterparty_id and counterparty_id != self.agent_id:
                try:
                    itype = InteractionType(pc.preferred_interaction_type)
                except ValueError:
                    itype = InteractionType.COLLABORATION
                return self.create_propose_action(
                    counterparty_id=counterparty_id,
                    interaction_type=itype,
                    content="Interaction proposed by external agent policy.",
                )

        return self.create_noop_action()

    def _policy_accept_interaction(
        self,
        proposal: InteractionProposal,
        observation: Observation,
    ) -> bool:
        """Accept/reject using policy parameters."""
        pc = self.policy_config
        trust = self.compute_counterparty_trust(proposal.initiator_id)
        effective = trust * pc.cooperation_bias + 0.5 * (1 - pc.cooperation_bias)
        return bool(effective >= pc.acceptance_threshold)

    def _policy_propose_interaction(
        self,
        observation: Observation,
        counterparty_id: str,
    ) -> Optional[InteractionProposal]:
        """Propose an interaction based on policy parameters."""
        pc = self.policy_config

        if random.random() > pc.interaction_probability:
            return None

        trust = self.compute_counterparty_trust(counterparty_id)
        if trust < pc.acceptance_threshold:
            return None

        try:
            itype = InteractionType(pc.preferred_interaction_type)
        except ValueError:
            itype = InteractionType.COLLABORATION

        return InteractionProposal(
            initiator_id=self.agent_id,
            counterparty_id=counterparty_id,
            interaction_type=itype,
            content="Interaction proposed by external agent policy.",
        )

    # ------------------------------------------------------------------
    # Callback-mode logic
    # ------------------------------------------------------------------

    def _callback_act(self, observation: Observation) -> Action:
        """POST observation to callback_url/act and parse the response."""
        import httpx

        url = f"{self.callback_url}/act"
        payload = _observation_to_dict(observation)

        try:
            response = httpx.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            return _parse_action_from_response(data, self.agent_id)
        except Exception:
            return self.create_noop_action()

    def _callback_accept_interaction(
        self,
        proposal: InteractionProposal,
        observation: Observation,
    ) -> bool:
        """POST proposal + observation to callback_url/accept_interaction."""
        import httpx

        url = f"{self.callback_url}/accept_interaction"
        payload = {
            "proposal": _proposal_to_dict(proposal),
            "observation": _observation_to_dict(observation),
        }

        try:
            response = httpx.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            return bool(data.get("accepted", False))
        except Exception:
            return False
