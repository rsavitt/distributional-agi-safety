"""Main bridge connecting Worktree sandboxes to SWARM.

WorktreeBridge manages agent sandbox lifecycles, dispatches commands
with full boundary enforcement, and converts sandbox signals into
SoftInteraction records for the SWARM pipeline.
"""

import logging
from typing import Any, Dict, List, Optional

from swarm.boundaries.information_flow import FlowTracker
from swarm.boundaries.leakage import LeakageDetector
from swarm.boundaries.policies import PolicyEngine
from swarm.bridges.worktree.config import WorktreeConfig
from swarm.bridges.worktree.events import WorktreeEvent, WorktreeEventType
from swarm.bridges.worktree.executor import SandboxExecutor
from swarm.bridges.worktree.mapper import WorktreeMapper
from swarm.bridges.worktree.policy import WorktreePolicy
from swarm.bridges.worktree.sandbox import SandboxManager
from swarm.core.proxy import ProxyComputer
from swarm.logging.event_log import EventLog
from swarm.models.events import Event, EventType
from swarm.models.interaction import SoftInteraction

logger = logging.getLogger(__name__)


class WorktreeBridge:
    """Bridge between git worktree sandboxes and the SWARM framework.

    Lifecycle::

        bridge = WorktreeBridge(config)
        bridge.create_agent_sandbox("agent_1")
        interaction = bridge.dispatch_command("agent_1", ["pytest", "-v"])
        observations = bridge.poll()
        bridge.destroy_agent_sandbox("agent_1")
        bridge.shutdown()

    The bridge translates sandbox signals into SWARM's data model:
    - Command results become SoftInteraction records
    - Git diff/reflog stats map to ProxyObservables
    - All events are logged to SWARM's append-only event log
    - Boundary infrastructure enforces all security invariants
    """

    def __init__(
        self,
        config: WorktreeConfig,
        event_log: Optional[EventLog] = None,
    ) -> None:
        self._config = config
        self._event_log = event_log

        # Boundary infrastructure
        self._flow_tracker = FlowTracker()
        self._leakage_detector = LeakageDetector()
        self._policy_engine = PolicyEngine().create_default_policies()

        # Worktree infrastructure
        self._sandbox_mgr = SandboxManager(config)
        self._wt_policy = WorktreePolicy(config)
        self._executor = SandboxExecutor(
            config=config,
            sandbox_manager=self._sandbox_mgr,
            worktree_policy=self._wt_policy,
            policy_engine=self._policy_engine,
            flow_tracker=self._flow_tracker,
            leakage_detector=self._leakage_detector,
        )
        self._mapper = WorktreeMapper(
            proxy=ProxyComputer(sigmoid_k=config.proxy_sigmoid_k)
        )

        # State
        self._interactions: List[SoftInteraction] = []
        self._events: List[WorktreeEvent] = []
        self._agent_sandboxes: Dict[str, str] = {}  # agent_id -> sandbox_id
        self._agent_stats: Dict[str, Dict[str, int]] = {}  # agent_id -> stats

    # --- Sandbox lifecycle ---

    def create_agent_sandbox(
        self,
        agent_id: str,
        branch: Optional[str] = None,
    ) -> str:
        """Create a sandbox for an agent.

        Args:
            agent_id: The agent to create a sandbox for.
            branch: Optional branch to check out.

        Returns:
            The sandbox_id.

        Raises:
            RuntimeError: If sandbox creation fails.
        """
        sandbox_id = f"sandbox-{agent_id}"
        if branch is None:
            branch = f"agent/{agent_id}/workspace"

        path = self._sandbox_mgr.create_sandbox(sandbox_id, branch=branch)
        self._agent_sandboxes[agent_id] = sandbox_id
        self._agent_stats[agent_id] = {
            "total_commands": 0,
            "successful_commands": 0,
            "denied_count": 0,
            "test_failures": 0,
            "rework_ops": 0,
        }

        event = WorktreeEvent(
            event_type=WorktreeEventType.SANDBOX_CREATED,
            agent_id=agent_id,
            sandbox_id=sandbox_id,
            payload={"path": path, "branch": branch},
        )
        self._record_event(event)
        logger.info("Created sandbox %s for agent %s at %s", sandbox_id, agent_id, path)
        return sandbox_id

    def destroy_agent_sandbox(self, agent_id: str) -> None:
        """Destroy an agent's sandbox.

        Args:
            agent_id: The agent whose sandbox to destroy.
        """
        sandbox_id = self._agent_sandboxes.pop(agent_id, None)
        if sandbox_id is None:
            logger.warning("No sandbox found for agent %s", agent_id)
            return

        event = self._sandbox_mgr.destroy_sandbox(sandbox_id)
        event.agent_id = agent_id
        self._record_event(event)
        self._agent_stats.pop(agent_id, None)
        logger.info("Destroyed sandbox %s for agent %s", sandbox_id, agent_id)

    # --- Command dispatch ---

    def dispatch_command(
        self,
        agent_id: str,
        command: List[str],
    ) -> SoftInteraction:
        """Dispatch a command to an agent's sandbox.

        Args:
            agent_id: The agent executing the command.
            command: Command as a list of arguments.

        Returns:
            A SoftInteraction representing the command execution.

        Raises:
            ValueError: If agent has no sandbox.
        """
        sandbox_id = self._agent_sandboxes.get(agent_id)
        if sandbox_id is None:
            raise ValueError(f"Agent {agent_id} has no sandbox")

        result, events = self._executor.execute(sandbox_id, agent_id, command)

        # Record all executor events
        for event in events:
            self._record_event(event)

        # Update agent stats
        stats = self._agent_stats.setdefault(agent_id, {
            "total_commands": 0,
            "successful_commands": 0,
            "denied_count": 0,
            "test_failures": 0,
            "rework_ops": 0,
        })
        stats["total_commands"] += 1
        if result.allowed and result.return_code == 0:
            stats["successful_commands"] += 1
        if not result.allowed:
            stats["denied_count"] += 1
        if (
            result.allowed
            and result.command
            and result.command[0] == "pytest"
            and result.return_code != 0
        ):
            stats["test_failures"] += 1

        # Map to SoftInteraction
        sandbox_path = self._sandbox_mgr.get_sandbox_path(sandbox_id)
        interaction = self._mapper.map_command_result(
            result,
            sandbox_path=sandbox_path,
            agent_stats=stats,
        )

        self._record_interaction(interaction)
        return interaction

    # --- Polling ---

    def poll(self) -> List[SoftInteraction]:
        """Poll all active sandboxes and return new SoftInteractions.

        Observes git diff/reflog state in each sandbox without
        dispatching commands.
        """
        new_interactions: List[SoftInteraction] = []

        for agent_id, sandbox_id in self._agent_sandboxes.items():
            sandbox_path = self._sandbox_mgr.get_sandbox_path(sandbox_id)
            if sandbox_path is None:
                continue

            stats = self._agent_stats.get(agent_id)
            interaction = self._mapper.map_sandbox_observation(
                sandbox_id=sandbox_id,
                agent_id=agent_id,
                sandbox_path=sandbox_path,
                agent_stats=stats,
            )
            self._record_interaction(interaction)
            new_interactions.append(interaction)

        return new_interactions

    # --- Accessors ---

    def get_interactions(self) -> List[SoftInteraction]:
        """Return all interactions recorded by this bridge."""
        return list(self._interactions)

    def get_events(self) -> List[WorktreeEvent]:
        """Return all events observed by this bridge."""
        return list(self._events)

    def get_boundary_metrics(self) -> Dict[str, Any]:
        """Return boundary enforcement metrics."""
        flow_summary = self._flow_tracker.get_summary()
        leakage_report = self._leakage_detector.generate_report()
        policy_stats = self._policy_engine.get_statistics()
        anomalies = self._flow_tracker.detect_anomalies()

        return {
            "flows": {
                "total": flow_summary.total_flows,
                "inbound": flow_summary.inbound_flows,
                "outbound": flow_summary.outbound_flows,
                "blocked": flow_summary.blocked_flows,
                "bytes_in": flow_summary.total_bytes_in,
                "bytes_out": flow_summary.total_bytes_out,
            },
            "leakage": {
                "total_events": leakage_report.total_events,
                "blocked": leakage_report.blocked_count,
                "by_type": leakage_report.events_by_type,
                "max_severity": leakage_report.max_severity,
            },
            "policy": policy_stats,
            "anomalies": anomalies,
        }

    def get_agent_stats(self, agent_id: str) -> Dict[str, Any]:
        """Return summary stats for an agent."""
        agent_interactions = [
            i for i in self._interactions if i.counterparty == agent_id
        ]
        stats = self._agent_stats.get(agent_id, {})
        if not agent_interactions:
            return {"agent_id": agent_id, "interactions": 0, **stats}
        avg_p = sum(i.p for i in agent_interactions) / len(agent_interactions)
        return {
            "agent_id": agent_id,
            "interactions": len(agent_interactions),
            "avg_p": avg_p,
            **stats,
        }

    # --- GC and lifecycle ---

    def gc(self) -> List[WorktreeEvent]:
        """Run garbage collection on stale sandboxes."""
        events: List[WorktreeEvent] = self._sandbox_mgr.gc_stale()
        for event in events:
            self._record_event(event)
            # Remove agent mapping for GC'd sandboxes
            gc_sid = event.sandbox_id
            for agent_id, sid in list(self._agent_sandboxes.items()):
                if sid == gc_sid:
                    self._agent_sandboxes.pop(agent_id, None)
                    self._agent_stats.pop(agent_id, None)
                    break
        return events

    def shutdown(self) -> None:
        """Destroy all sandboxes and clean up."""
        for agent_id in list(self._agent_sandboxes.keys()):
            try:
                self.destroy_agent_sandbox(agent_id)
            except (ValueError, RuntimeError) as exc:
                logger.warning(
                    "Failed to destroy sandbox for %s on shutdown: %s",
                    agent_id,
                    exc,
                )

    # --- Internal helpers ---

    def _record_event(self, event: WorktreeEvent) -> None:
        if len(self._events) >= self._config.max_events:
            self._events = self._events[-self._config.max_events // 2:]
        self._events.append(event)

    def _record_interaction(self, interaction: SoftInteraction) -> None:
        if len(self._interactions) >= self._config.max_interactions:
            self._interactions = self._interactions[
                -self._config.max_interactions // 2:
            ]
        self._interactions.append(interaction)
        self._log_interaction(interaction)

    def _log_interaction(self, interaction: SoftInteraction) -> None:
        if self._event_log is None:
            return
        event = Event(
            event_type=EventType.INTERACTION_COMPLETED,
            interaction_id=interaction.interaction_id,
            initiator_id=interaction.initiator,
            counterparty_id=interaction.counterparty,
            payload={
                "accepted": interaction.accepted,
                "v_hat": interaction.v_hat,
                "p": interaction.p,
                "bridge": "worktree",
                "metadata": interaction.metadata,
            },
        )
        self._event_log.append(event)
