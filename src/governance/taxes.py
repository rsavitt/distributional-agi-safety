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

        Tax is proportional to |tau| and split according to transaction_tax_split.

        Args:
            interaction: The completed interaction
            state: Current environment state

        Returns:
            Effect with costs c_a and c_b
        """
        if self.config.transaction_tax_rate == 0.0:
            return LeverEffect(lever_name=self.name)

        # Tax base is absolute value of transfer
        tax_base = abs(interaction.tau)
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
