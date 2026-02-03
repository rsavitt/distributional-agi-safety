"""Soft metrics for interaction quality analysis."""

from typing import List, Optional, Tuple

from src.models.interaction import SoftInteraction
from src.core.payoff import SoftPayoffEngine, PayoffConfig


class SoftMetrics:
    """
    Computes soft (probabilistic) metrics for interaction quality.

    Key metrics:
    - Toxicity rate: E[1-p | accepted]
    - Conditional loss: E[π_a | accepted] - E[π_a]
    - Spread: Quality filtering effectiveness
    - Quality gap: E[p | accepted] - E[p | rejected]
    """

    def __init__(self, payoff_engine: Optional[SoftPayoffEngine] = None):
        """
        Initialize metrics calculator.

        Args:
            payoff_engine: Engine for payoff calculations (default: SoftPayoffEngine())
        """
        self.payoff_engine = payoff_engine or SoftPayoffEngine()

    def toxicity_rate(self, interactions: List[SoftInteraction]) -> float:
        """
        Compute toxicity rate: E[1-p | accepted]

        This measures the expected fraction of harmful outcomes
        among accepted interactions.

        Args:
            interactions: List of interactions

        Returns:
            Toxicity rate in [0, 1], or 0.0 if no accepted interactions
        """
        accepted = [i for i in interactions if i.accepted]
        if not accepted:
            return 0.0

        return sum(1 - i.p for i in accepted) / len(accepted)

    def toxicity_rate_all(self, interactions: List[SoftInteraction]) -> float:
        """
        Compute unconditional toxicity rate: E[1-p]

        Args:
            interactions: List of interactions

        Returns:
            Toxicity rate in [0, 1]
        """
        if not interactions:
            return 0.0

        return sum(1 - i.p for i in interactions) / len(interactions)

    def conditional_loss_initiator(
        self, interactions: List[SoftInteraction]
    ) -> float:
        """
        Compute conditional loss for initiator: E[π_a | accepted] - E[π_a]

        Negative values indicate adverse selection (accepted interactions
        are worse than average for the initiator).

        Args:
            interactions: List of interactions

        Returns:
            Conditional loss (negative = adverse selection)
        """
        if not interactions:
            return 0.0

        accepted = [i for i in interactions if i.accepted]
        if not accepted:
            return 0.0

        # Average payoff for accepted
        avg_accepted = sum(
            self.payoff_engine.payoff_initiator(i) for i in accepted
        ) / len(accepted)

        # Average payoff overall
        avg_all = sum(
            self.payoff_engine.payoff_initiator(i) for i in interactions
        ) / len(interactions)

        return avg_accepted - avg_all

    def conditional_loss_counterparty(
        self, interactions: List[SoftInteraction]
    ) -> float:
        """
        Compute conditional loss for counterparty: E[π_b | accepted] - E[π_b]

        Args:
            interactions: List of interactions

        Returns:
            Conditional loss (negative = adverse selection)
        """
        if not interactions:
            return 0.0

        accepted = [i for i in interactions if i.accepted]
        if not accepted:
            return 0.0

        avg_accepted = sum(
            self.payoff_engine.payoff_counterparty(i) for i in accepted
        ) / len(accepted)

        avg_all = sum(
            self.payoff_engine.payoff_counterparty(i) for i in interactions
        ) / len(interactions)

        return avg_accepted - avg_all

    def spread(self, interactions: List[SoftInteraction]) -> float:
        """
        Compute spread: (s_plus + s_minus) * (E[p] - E[p | accepted])

        Positive spread indicates the market is filtering out high-quality
        interactions (adverse selection in the quality sense).

        Args:
            interactions: List of interactions

        Returns:
            Spread value
        """
        if not interactions:
            return 0.0

        accepted = [i for i in interactions if i.accepted]
        if not accepted:
            return 0.0

        avg_p_all = sum(i.p for i in interactions) / len(interactions)
        avg_p_accepted = sum(i.p for i in accepted) / len(accepted)

        scale = (
            self.payoff_engine.config.s_plus +
            self.payoff_engine.config.s_minus
        )

        return scale * (avg_p_all - avg_p_accepted)

    def quality_gap(self, interactions: List[SoftInteraction]) -> float:
        """
        Compute quality gap: E[p | accepted] - E[p | rejected]

        Negative quality gap indicates adverse selection (accepted
        interactions have lower quality than rejected ones).

        Args:
            interactions: List of interactions

        Returns:
            Quality gap (negative = adverse selection)
        """
        accepted = [i for i in interactions if i.accepted]
        rejected = [i for i in interactions if not i.accepted]

        if not accepted or not rejected:
            return 0.0

        avg_p_accepted = sum(i.p for i in accepted) / len(accepted)
        avg_p_rejected = sum(i.p for i in rejected) / len(rejected)

        return avg_p_accepted - avg_p_rejected

    def participation_by_quality(
        self,
        interactions: List[SoftInteraction],
        threshold: float = 0.5,
    ) -> dict:
        """
        Compute acceptance rates for high/low quality interactions.

        Args:
            interactions: List of interactions
            threshold: Quality threshold (default 0.5)

        Returns:
            Dictionary with acceptance rates:
            - high_quality_acceptance: P(accepted | p >= threshold)
            - low_quality_acceptance: P(accepted | p < threshold)
            - high_quality_count: Number of high quality interactions
            - low_quality_count: Number of low quality interactions
        """
        high_quality = [i for i in interactions if i.p >= threshold]
        low_quality = [i for i in interactions if i.p < threshold]

        high_accepted = sum(1 for i in high_quality if i.accepted)
        low_accepted = sum(1 for i in low_quality if i.accepted)

        return {
            "high_quality_acceptance": (
                high_accepted / len(high_quality) if high_quality else 0.0
            ),
            "low_quality_acceptance": (
                low_accepted / len(low_quality) if low_quality else 0.0
            ),
            "high_quality_count": len(high_quality),
            "low_quality_count": len(low_quality),
        }

    def flag_uncertain(
        self,
        interactions: List[SoftInteraction],
        band: float = 0.2,
    ) -> List[SoftInteraction]:
        """
        Flag interactions with uncertain labels (p near 0.5).

        Args:
            interactions: List of interactions
            band: Width of uncertainty band around 0.5

        Returns:
            List of uncertain interactions
        """
        return [i for i in interactions if i.is_uncertain(band)]

    def uncertain_fraction(
        self,
        interactions: List[SoftInteraction],
        band: float = 0.2,
    ) -> float:
        """
        Compute fraction of interactions with uncertain labels.

        Args:
            interactions: List of interactions
            band: Width of uncertainty band around 0.5

        Returns:
            Fraction in [0, 1]
        """
        if not interactions:
            return 0.0

        uncertain = self.flag_uncertain(interactions, band)
        return len(uncertain) / len(interactions)

    def average_quality(
        self,
        interactions: List[SoftInteraction],
        accepted_only: bool = False,
    ) -> float:
        """
        Compute average quality E[p].

        Args:
            interactions: List of interactions
            accepted_only: If True, only consider accepted interactions

        Returns:
            Average p value
        """
        if accepted_only:
            interactions = [i for i in interactions if i.accepted]

        if not interactions:
            return 0.0

        return sum(i.p for i in interactions) / len(interactions)

    def quality_distribution(
        self,
        interactions: List[SoftInteraction],
        bins: int = 10,
    ) -> List[Tuple[float, float, int]]:
        """
        Compute quality distribution histogram.

        Args:
            interactions: List of interactions
            bins: Number of bins

        Returns:
            List of (bin_start, bin_end, count) tuples
        """
        if not interactions:
            return []

        bin_width = 1.0 / bins
        result = []

        for i in range(bins):
            bin_start = i * bin_width
            bin_end = (i + 1) * bin_width

            count = sum(
                1 for interaction in interactions
                if bin_start <= interaction.p < bin_end
                or (i == bins - 1 and interaction.p == 1.0)
            )

            result.append((bin_start, bin_end, count))

        return result

    def welfare_metrics(
        self, interactions: List[SoftInteraction]
    ) -> dict:
        """
        Compute aggregate welfare metrics.

        Args:
            interactions: List of interactions

        Returns:
            Dictionary with welfare metrics
        """
        if not interactions:
            return {
                "total_welfare": 0.0,
                "total_social_surplus": 0.0,
                "avg_initiator_payoff": 0.0,
                "avg_counterparty_payoff": 0.0,
            }

        accepted = [i for i in interactions if i.accepted]

        total_welfare = sum(
            self.payoff_engine.total_welfare(i) for i in accepted
        )
        total_social = sum(
            self.payoff_engine.social_surplus(i) for i in accepted
        )
        avg_init = (
            sum(self.payoff_engine.payoff_initiator(i) for i in accepted)
            / len(accepted) if accepted else 0.0
        )
        avg_counter = (
            sum(self.payoff_engine.payoff_counterparty(i) for i in accepted)
            / len(accepted) if accepted else 0.0
        )

        return {
            "total_welfare": total_welfare,
            "total_social_surplus": total_social,
            "avg_initiator_payoff": avg_init,
            "avg_counterparty_payoff": avg_counter,
        }
