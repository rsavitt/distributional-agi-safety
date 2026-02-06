"""Reputation-related governance levers."""

from swarm.env.state import EnvState
from swarm.governance.levers import GovernanceLever, LeverEffect


class ReputationDecayLever(GovernanceLever):
    """
    Reputation decay applied at epoch boundaries.

    Multiplies all agent reputations by decay_rate each epoch,
    causing reputation to gradually return toward zero.
    """

    @property
    def name(self) -> str:
        return "reputation_decay"

    def on_epoch_start(
        self,
        state: EnvState,
        epoch: int,
    ) -> LeverEffect:
        """
        Apply reputation decay to all agents.

        Args:
            state: Current environment state
            epoch: The epoch number starting

        Returns:
            Effect with reputation deltas
        """
        if self.config.reputation_decay_rate >= 1.0:
            return LeverEffect(lever_name=self.name)

        reputation_deltas = {}
        for agent_id, agent_state in state.agents.items():
            if agent_state.reputation != 0.0:
                # Calculate decay: new = old * rate, delta = new - old = old * (rate - 1)
                delta = agent_state.reputation * (self.config.reputation_decay_rate - 1)
                reputation_deltas[agent_id] = delta

        return LeverEffect(
            reputation_deltas=reputation_deltas,
            lever_name=self.name,
            details={
                "decay_rate": self.config.reputation_decay_rate,
                "agents_affected": len(reputation_deltas),
            },
        )


class VoteNormalizationLever(GovernanceLever):
    """
    Vote weight normalization for diminishing influence.

    This lever doesn't modify costs directly but provides a method
    to compute normalized vote weights for feed integration.
    """

    @property
    def name(self) -> str:
        return "vote_normalization"

    def compute_vote_weight(
        self,
        agent_id: str,
        vote_count: int,
    ) -> float:
        """
        Compute normalized vote weight for an agent.

        Weight decreases as vote count increases, up to max_vote_weight.

        Args:
            agent_id: The voting agent
            vote_count: Number of votes cast this epoch

        Returns:
            Vote weight in (0, 1]
        """
        if not self.config.vote_normalization_enabled:
            return 1.0

        # Diminishing returns: weight = max_weight / (1 + vote_count / max_weight)
        max_weight = self.config.max_vote_weight_per_agent
        weight = max_weight / (1 + vote_count / max_weight)

        # Normalize to [0, 1] by dividing by max_weight
        return weight / max_weight
