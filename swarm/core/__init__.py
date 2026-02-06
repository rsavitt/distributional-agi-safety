"""Core computation modules for payoff, proxy, and orchestration."""

from swarm.core.orchestrator import EpochMetrics, Orchestrator, OrchestratorConfig
from swarm.core.payoff import PayoffConfig, SoftPayoffEngine
from swarm.core.proxy import ProxyComputer, ProxyObservables, ProxyWeights
from swarm.core.sigmoid import calibrated_sigmoid, inverse_sigmoid

__all__ = [
    "calibrated_sigmoid",
    "inverse_sigmoid",
    "ProxyComputer",
    "ProxyWeights",
    "ProxyObservables",
    "SoftPayoffEngine",
    "PayoffConfig",
    "Orchestrator",
    "OrchestratorConfig",
    "EpochMetrics",
]
