"""SWARM-LiveSWE Agent Bridge.

Connects SWARM's governance and metrics framework to live-swe-agent,
enabling monitoring, scoring, and governance of self-evolving SWE agents
that create their own tools at runtime.

Architecture:
    mini-swe-agent process / trajectory JSON
        |
    LiveSWEClient (subprocess + trajectory parser)
        |
    LiveSWEAgentBridge._extract_observables()
        |   CapabilityTracker.update() (tool creation, behavior drift, growth rate)
        |
    ProxyObservables -> ProxyComputer -> (v_hat, p) -> SoftInteraction
        |
    SelfEvolutionPolicy (tool creation gates, growth limits, divergence penalty)
        |
    EventLog + SWARM metrics pipeline
"""

from swarm.bridges.live_swe.bridge import LiveSWEAgentBridge, LiveSWEBridgeConfig
from swarm.bridges.live_swe.client import LiveSWEClient, LiveSWEClientConfig
from swarm.bridges.live_swe.events import (
    LiveSWEEvent,
    LiveSWEEventType,
    StepEvent,
    ToolCreationEvent,
    TrajectoryEvent,
)
from swarm.bridges.live_swe.policy import (
    PolicyDecision,
    PolicyResult,
    SelfEvolutionPolicy,
)
from swarm.bridges.live_swe.tracker import AgentCapabilityState, CapabilityTracker

__all__ = [
    "LiveSWEAgentBridge",
    "LiveSWEBridgeConfig",
    "LiveSWEClient",
    "LiveSWEClientConfig",
    "LiveSWEEvent",
    "LiveSWEEventType",
    "StepEvent",
    "ToolCreationEvent",
    "TrajectoryEvent",
    "PolicyDecision",
    "PolicyResult",
    "SelfEvolutionPolicy",
    "AgentCapabilityState",
    "CapabilityTracker",
]
