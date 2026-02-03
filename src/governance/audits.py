"""Random audit governance lever."""

import random
from typing import Optional

from src.env.state import EnvState
from src.governance.config import GovernanceConfig
from src.governance.levers import GovernanceLever, LeverEffect
from src.models.interaction import SoftInteraction


class RandomAuditLever(GovernanceLever):
    """
    Random audit with penalty for low-quality interactions.

    Probabilistically audits interactions and applies penalty
    when p falls below the threshold.
    """

    def __init__(self, config: GovernanceConfig, seed: Optional[int] = None):
        super().__init__(config)
        self._rng = random.Random(seed)

    @property
    def name(self) -> str:
        return "random_audit"

    def on_interaction(
        self,
        interaction: SoftInteraction,
        state: EnvState,
    ) -> LeverEffect:
        """
        Potentially audit the interaction and apply penalty.

        Args:
            interaction: The completed interaction
            state: Current environment state

        Returns:
            Effect with potential penalty costs
        """
        if not self.config.audit_enabled:
            return LeverEffect(lever_name=self.name)

        # Roll for audit
        if self._rng.random() > self.config.audit_probability:
            return LeverEffect(
                lever_name=self.name,
                details={"audited": False},
            )

        # Audit triggered - check quality
        audited = True
        penalty_applied = False
        cost_a = 0.0

        if interaction.p < self.config.audit_threshold_p:
            # Low quality detected - apply penalty
            # Penalty is proportional to how far below threshold
            shortfall = self.config.audit_threshold_p - interaction.p
            base_penalty = shortfall * self.config.audit_penalty_multiplier
            cost_a = base_penalty
            penalty_applied = True

        return LeverEffect(
            cost_a=cost_a,
            lever_name=self.name,
            details={
                "audited": audited,
                "p": interaction.p,
                "threshold": self.config.audit_threshold_p,
                "penalty_applied": penalty_applied,
                "penalty_amount": cost_a,
            },
        )

    def set_seed(self, seed: int) -> None:
        """Set random seed for reproducibility."""
        self._rng = random.Random(seed)
