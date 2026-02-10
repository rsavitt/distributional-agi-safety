"""LiveSWE agent adapter for the SWARM orchestrator loop.

Wraps LiveSWEAgentBridge as a BaseAgent so that self-evolving SWE agents
can participate in SWARM scenarios alongside scripted and LLM agents.
"""

from typing import Dict, List, Optional

from swarm.agents.base import (
    Action,
    BaseAgent,
    InteractionProposal,
    Observation,
    Role,
)
from swarm.bridges.live_swe.bridge import LiveSWEAgentBridge
from swarm.models.agent import AgentType


class LiveSWEAgent(BaseAgent):
    """BaseAgent adapter for live-swe-agent runs.

    Each ``act()`` dispatches a task to the bridge, which runs or
    analyzes a trajectory and returns a scored SoftInteraction.
    """

    def __init__(
        self,
        agent_id: str,
        bridge: LiveSWEAgentBridge,
        roles: Optional[List[Role]] = None,
        config: Optional[Dict] = None,
        name: Optional[str] = None,
    ) -> None:
        super().__init__(
            agent_id=agent_id,
            agent_type=AgentType.HONEST,
            roles=roles,
            config=config or {},
            name=name,
        )
        self._bridge = bridge
        self._default_task = self.config.get(
            "default_task", "Resolve the assigned issue."
        )

    def act(self, observation: Observation) -> Action:
        """Dispatch a task to the bridge and return a noop action.

        The real work happens inside the bridge; the orchestrator
        collects the resulting SoftInteraction from
        ``bridge.get_interactions()``.
        """
        task = self._default_task
        # If there are available tasks, use the first one
        if observation.available_tasks:
            first_task = observation.available_tasks[0]
            task = first_task.get("description", first_task.get("subject", task))

        self._bridge.run_task(self.agent_id, task)
        return self.create_noop_action()

    def accept_interaction(
        self,
        proposal: InteractionProposal,
        observation: Observation,
    ) -> bool:
        """Accept all interaction proposals."""
        return True

    def propose_interaction(
        self,
        observation: Observation,
        counterparty_id: str,
    ) -> Optional[InteractionProposal]:
        """LiveSWE agents do not propose interactions."""
        return None
