"""Self-evolution governance policy for LiveSWE agents.

Evaluates tool creation requests, monitors growth rate, enforces
divergence penalties, and triggers circuit breakers when agents
evolve beyond safe boundaries.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from swarm.bridges.live_swe.events import ToolCreationEvent
from swarm.bridges.live_swe.tracker import AgentCapabilityState, CapabilityTracker
from swarm.governance.config import GovernanceConfig

logger = logging.getLogger(__name__)


class PolicyDecision(Enum):
    """Possible outcomes of a policy evaluation."""

    APPROVE = "approve"
    DENY = "deny"
    WARN = "warn"


@dataclass
class PolicyResult:
    """Result of a policy evaluation."""

    decision: PolicyDecision
    reason: str = ""
    governance_cost: float = 0.0
    divergence_penalty: float = 0.0


class SelfEvolutionPolicy:
    """Governs self-evolving SWE agent behavior.

    Enforces limits on tool creation rate, total tool count,
    behavioral divergence, and self-modification. Uses governance
    config fields prefixed with ``self_evolution_*``.
    """

    def __init__(
        self,
        governance_config: Optional[GovernanceConfig] = None,
        tracker: Optional[CapabilityTracker] = None,
    ) -> None:
        self.config = governance_config or GovernanceConfig()
        self.tracker = tracker or CapabilityTracker()

    def evaluate_tool_creation(
        self,
        event: ToolCreationEvent,
        agent_state: AgentCapabilityState,
        reputation: float = 0.0,
    ) -> PolicyResult:
        """Evaluate whether a tool creation should be allowed.

        Checks:
        1. Self-evolution governance enabled
        2. Max tools limit
        3. Tool risk score vs threshold
        4. Growth rate vs max
        5. Reputation-gated high-risk tools

        Args:
            event: The tool creation event
            agent_state: Current capability state
            reputation: Agent's current reputation

        Returns:
            PolicyResult with decision and reason
        """
        if not self.config.self_evolution_enabled:
            return PolicyResult(
                decision=PolicyDecision.APPROVE,
                reason="self-evolution governance disabled",
            )

        # Check max tools limit
        if len(agent_state.tools_created) >= self.config.self_evolution_max_tools:
            return PolicyResult(
                decision=PolicyDecision.DENY,
                reason=f"max tools limit reached ({self.config.self_evolution_max_tools})",
                governance_cost=0.1,
            )

        # Check growth rate
        if agent_state.capability_growth_rate > self.config.self_evolution_max_growth_rate:
            return PolicyResult(
                decision=PolicyDecision.DENY,
                reason=(
                    f"growth rate {agent_state.capability_growth_rate:.3f} "
                    f"exceeds limit {self.config.self_evolution_max_growth_rate}"
                ),
                governance_cost=0.1,
            )

        # Check tool risk score
        risk_score = self.tracker.compute_tool_risk_score(
            event.tool_path, ""  # Content not available at creation event
        )
        if risk_score > self.config.self_evolution_tool_risk_threshold:
            # Low-reputation agents cannot create high-risk tools
            if reputation < 0.0:
                return PolicyResult(
                    decision=PolicyDecision.DENY,
                    reason=(
                        f"high-risk tool (score={risk_score:.2f}) denied "
                        f"for low-reputation agent ({reputation:.2f})"
                    ),
                    governance_cost=0.15,
                )
            return PolicyResult(
                decision=PolicyDecision.WARN,
                reason=f"high-risk tool creation (score={risk_score:.2f})",
                governance_cost=0.05,
            )

        return PolicyResult(
            decision=PolicyDecision.APPROVE,
            reason="tool creation within policy bounds",
        )

    def evaluate_step(
        self,
        agent_state: AgentCapabilityState,
        reputation: float = 0.0,
    ) -> PolicyResult:
        """Evaluate the agent's current state against policy limits.

        Called after each step to check behavioral drift and
        self-modification attempts.

        Args:
            agent_state: Current capability state
            reputation: Agent's current reputation

        Returns:
            PolicyResult with any applicable penalties
        """
        if not self.config.self_evolution_enabled:
            return PolicyResult(
                decision=PolicyDecision.APPROVE,
                reason="self-evolution governance disabled",
            )

        # Check for self-modification
        if (
            self.config.self_evolution_block_self_mod
            and agent_state.self_modification_attempts > 0
        ):
            return PolicyResult(
                decision=PolicyDecision.DENY,
                reason=(
                    f"self-modification detected "
                    f"({agent_state.self_modification_attempts} attempts)"
                ),
                governance_cost=0.2,
            )

        # Check divergence threshold
        divergence = agent_state.behavior_divergence
        if divergence > self.config.self_evolution_divergence_threshold:
            penalty = self.compute_divergence_penalty(divergence)
            return PolicyResult(
                decision=PolicyDecision.WARN,
                reason=(
                    f"behavior divergence {divergence:.3f} exceeds "
                    f"threshold {self.config.self_evolution_divergence_threshold}"
                ),
                governance_cost=0.1,
                divergence_penalty=penalty,
            )

        return PolicyResult(
            decision=PolicyDecision.APPROVE,
            reason="step within policy bounds",
        )

    def should_circuit_break(self, agent_state: AgentCapabilityState) -> bool:
        """Determine if the agent should be circuit-broken.

        Circuit-breaks when:
        - Self-modification attempts exceed 0 and blocking is enabled
        - Growth rate exceeds 2x the configured max
        - Behavior divergence exceeds threshold + 0.2 margin

        Args:
            agent_state: Current capability state

        Returns:
            True if the agent should be frozen
        """
        if not self.config.self_evolution_enabled:
            return False

        # Self-modification with blocking enabled
        if (
            self.config.self_evolution_block_self_mod
            and agent_state.self_modification_attempts > 0
        ):
            return True

        # Extreme growth rate (2x limit)
        if agent_state.capability_growth_rate > self.config.self_evolution_max_growth_rate * 2:
            return True

        # Extreme divergence (threshold + margin)
        if agent_state.behavior_divergence > min(
            1.0, self.config.self_evolution_divergence_threshold + 0.2
        ):
            return True

        return False

    def compute_divergence_penalty(self, divergence: float) -> float:
        """Compute a penalty from behavioral divergence.

        Penalty scales linearly from 0 at the threshold to 1.0 at
        divergence = 1.0.

        Args:
            divergence: Behavioral divergence in [0, 1]

        Returns:
            Penalty in [0.0, 1.0]
        """
        threshold: float = self.config.self_evolution_divergence_threshold
        if divergence <= threshold:
            return 0.0
        # Linear scaling from threshold to 1.0
        penalty: float = min(1.0, (divergence - threshold) / max(0.01, 1.0 - threshold))
        return penalty
