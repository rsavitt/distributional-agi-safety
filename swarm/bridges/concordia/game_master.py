"""SwarmGameMaster: wraps a Concordia GameMaster with SWARM governance.

Gracefully handles missing Concordia dependency.
"""

import importlib.util
import logging
from dataclasses import dataclass, field
from typing import Any

from swarm.bridges.concordia.adapter import ConcordiaAdapter

logger = logging.getLogger(__name__)

# Graceful import of Concordia
_HAS_CONCORDIA = importlib.util.find_spec("concordia") is not None

# Graceful import of GovernanceEngine
try:
    from swarm.governance.engine import GovernanceEffect, GovernanceEngine
except ImportError:
    GovernanceEngine = None  # type: ignore[assignment,misc]
    GovernanceEffect = None  # type: ignore[assignment,misc]


@dataclass
class StepResult:
    """Result of a single SwarmGameMaster step."""

    narrative: str = ""
    agent_ids: list[str] = field(default_factory=list)
    interactions_count: int = 0
    governance_applied: bool = False
    frozen_agents: list[str] = field(default_factory=list)
    original_result: Any = None


class SwarmGameMaster:
    """Wraps a Concordia GameMaster with SWARM safety scoring and governance.

    Usage:
        adapter = ConcordiaAdapter(config)
        gm = SwarmGameMaster(original_gm, adapter)
        result = gm.step()
    """

    def __init__(
        self,
        original_gm: Any,
        adapter: ConcordiaAdapter,
        governance: Any = None,
    ):
        self._original_gm = original_gm
        self._adapter = adapter
        self._governance = governance
        self._step_count = 0

    def step(self) -> StepResult:
        """Execute one step: run Concordia GM, capture narrative, score, govern."""
        # Run the original game master step
        original_result = None
        if self._original_gm is not None:
            if hasattr(self._original_gm, "step"):
                original_result = self._original_gm.step()

        # Capture narrative from the step
        narrative = self._capture_narrative()
        agent_ids = self._get_agent_ids()

        # Process through SWARM adapter
        interactions = self._adapter.process_narrative(
            agent_ids=agent_ids,
            narrative_text=narrative,
            step=self._step_count,
        )

        # Apply governance if available
        governance_applied = False
        frozen_agents: list[str] = []

        if self._governance is not None and interactions:
            effect = self._apply_governance(interactions)
            if effect is not None:
                governance_applied = True
                frozen_agents = list(getattr(effect, "agents_to_freeze", set()))
                if frozen_agents:
                    self._narrate_governance(frozen_agents)

        self._step_count += 1

        return StepResult(
            narrative=narrative,
            agent_ids=agent_ids,
            interactions_count=len(interactions),
            governance_applied=governance_applied,
            frozen_agents=frozen_agents,
            original_result=original_result,
        )

    def _capture_narrative(self) -> str:
        """Extract narrative text from the Concordia GM's action log."""
        if self._original_gm is None:
            return ""

        # Try common Concordia patterns
        if hasattr(self._original_gm, "get_history"):
            history = self._original_gm.get_history()
            if isinstance(history, list) and history:
                return str(history[-1])
            if isinstance(history, str):
                return history

        if hasattr(self._original_gm, "narrative"):
            return str(self._original_gm.narrative)

        return ""

    def _get_agent_ids(self) -> list[str]:
        """Get agent IDs from the Concordia GM."""
        if self._original_gm is None:
            return []

        if hasattr(self._original_gm, "get_agent_ids"):
            return list(self._original_gm.get_agent_ids())

        if hasattr(self._original_gm, "agents"):
            agents = self._original_gm.agents
            if isinstance(agents, dict):
                return list(agents.keys())
            if isinstance(agents, list):
                return [
                    getattr(a, "name", getattr(a, "agent_id", str(i)))
                    for i, a in enumerate(agents)
                ]

        return []

    def _apply_governance(self, interactions: list) -> Any:
        """Apply governance to interactions."""
        if self._governance is None:
            return None

        if hasattr(self._governance, "apply"):
            try:
                return self._governance.apply(interactions)
            except Exception:
                logger.exception("Governance application failed")
                return None

        return None

    def _narrate_governance(self, frozen_agents: list[str]) -> None:
        """Inject governance suspension messages back to Concordia."""
        if not frozen_agents or self._original_gm is None:
            return

        if hasattr(self._original_gm, "add_narrative"):
            msg = (
                f"[SWARM GOVERNANCE] The following agents have been suspended "
                f"due to safety concerns: {', '.join(frozen_agents)}"
            )
            try:
                self._original_gm.add_narrative(msg)
            except Exception:
                logger.exception("Failed to narrate governance action")

    @property
    def adapter(self) -> ConcordiaAdapter:
        """Access the underlying adapter."""
        return self._adapter

    @property
    def step_count(self) -> int:
        """Number of steps executed."""
        return self._step_count

    @staticmethod
    def requires_concordia() -> bool:
        """Check if Concordia is available."""
        return _HAS_CONCORDIA
