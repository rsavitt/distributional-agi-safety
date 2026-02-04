"""Transaction tax governance lever."""

from src.env.state import EnvState
from src.governance.levers import GovernanceLever, LeverEffect
from src.models.interaction import SoftInteraction


class TransactionTaxLever(GovernanceLever):
    """
    Transaction tax applied to each interaction.

    Adds governance costs proportional to |tau| (transfer amount),
    split between initiator and counterparty according to config.
    """

    @property
    def name(self) -> str:
        return "transaction_tax"

    def on_interaction(
        self,
        interaction: SoftInteraction,
        state: EnvState,
    ) -> LeverEffect:
        """
        Apply transaction tax to the interaction.

        Tax is proportional to the interaction value and split according
        to transaction_tax_split.  The tax base combines explicit transfers
        (|tau|) with the estimated expected surplus derived from the
        interaction's soft label p.  This ensures the tax is meaningful
        even when agents do not use explicit transfers.

        Args:
            interaction: The completed interaction
            state: Current environment state

        Returns:
            Effect with costs c_a and c_b
        """
        if self.config.transaction_tax_rate == 0.0:
            return LeverEffect(lever_name=self.name)

        if not interaction.accepted:
            return LeverEffect(lever_name=self.name)

        # Estimate expected surplus from the soft label p.
        # Uses PayoffConfig defaults (s_plus=2, s_minus=1) for the estimate;
        # only the positive part is taxed (no rebate for negative surplus).
        surplus_estimate = interaction.p * 2.0 - (1 - interaction.p) * 1.0
        tax_base = max(surplus_estimate, 0.0) + abs(interaction.tau)
        total_tax = self.config.transaction_tax_rate * tax_base

        # Split between parties
        cost_a = total_tax * self.config.transaction_tax_split
        cost_b = total_tax * (1 - self.config.transaction_tax_split)

        return LeverEffect(
            cost_a=cost_a,
            cost_b=cost_b,
            lever_name=self.name,
            details={
                "tax_base": tax_base,
                "total_tax": total_tax,
                "rate": self.config.transaction_tax_rate,
                "split": self.config.transaction_tax_split,
            },
        )
